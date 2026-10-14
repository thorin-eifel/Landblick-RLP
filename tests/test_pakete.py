"""Nachladepakete: Download in Teilen mit Wiederaufnahme, Prüfsummen, Abbruch. Lokaler HTTP-Server mit Range-Unterstützung."""
from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import pakete
from tools import pack_tiles


class Srv:
    def __init__(self, files: dict[str, bytes], ranges: bool = True) -> None:
        self.files, self.ranges, self.hits, self.cut_after = files, ranges, [], None
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): ...

            def do_GET(self):
                name = self.path.lstrip("/")
                data = outer.files.get(name)
                if data is None:
                    self.send_error(404)
                    return
                rng = self.headers.get("Range")
                outer.hits.append((name, rng))
                start = 0
                if rng and outer.ranges:
                    start = int(rng.split("=")[1].rstrip("-"))
                    self.send_response(206)
                else:
                    self.send_response(200)
                body = data[start:]
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if outer.cut_after is not None and name.endswith("part02"):
                    body, outer.cut_after = body[: outer.cut_after], None   # einmal mittendrin abbrechen
                    self.wfile.write(body)
                    self.wfile.flush()
                    self.connection.close()
                    return
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def paket(tmp_path, size=3500, part=1000):
    data = bytes((i * 7 + i // 251) % 256 for i in range(size))
    src = tmp_path / "src"
    src.mkdir()
    (src / "dem-hoch.pmtiles").write_bytes(data)
    man = pack_tiles.split(src / "dem-hoch.pmtiles", part)
    files = {p["file"]: (src / p["file"]).read_bytes() for p in man["parts"]}
    files["dem-hoch.pmtiles.manifest.json"] = (src / "dem-hoch.pmtiles.manifest.json").read_bytes()
    return data, man, files


@pytest.fixture
def srv_factory():
    made = []

    def mk(files, **kw):
        s = Srv(files, **kw)
        made.append(s)
        return s
    yield mk
    for s in made:
        s.close()


def test_download_komplett(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    s = srv_factory(files)
    seen = []
    out = pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", tmp_path / "dest", lambda d, t: seen.append((d, t)))
    assert out.read_bytes() == data
    assert not (tmp_path / "dest" / "dem-hoch.pmtiles.part").exists()
    assert seen[-1] == (len(data), len(data))


def test_vorhanden_ist_noop(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    s = srv_factory(files)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "dem-hoch.pmtiles").write_bytes(data)
    pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", dest)
    assert all(h[0].endswith("manifest.json") for h in s.hits)


def test_wiederaufnahme_mit_range(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    s = srv_factory(files)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "dem-hoch.pmtiles.part").write_bytes(data[:1400])   # Teil 1 fertig, Teil 2 halb
    pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", dest)
    assert (dest / "dem-hoch.pmtiles").read_bytes() == data
    assert ("dem-hoch.pmtiles.part01", None) not in s.hits
    assert ("dem-hoch.pmtiles.part02", "bytes=400-") in s.hits


def test_abbruch_mitten_im_teil_wird_wiederholt(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    s = srv_factory(files)
    s.cut_after = 300
    out = pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", tmp_path / "dest", backoff=0.01)
    assert out.read_bytes() == data


def test_server_ohne_range_holt_teil_von_vorn(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    s = srv_factory(files, ranges=False)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "dem-hoch.pmtiles.part").write_bytes(data[:1400])
    assert pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", dest).read_bytes() == data


def test_beschaedigter_halbfertiger_teil_wird_neu_geholt(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    s = srv_factory(files)
    dest = tmp_path / "dest"
    dest.mkdir()
    bad = bytearray(data[:1400])
    bad[10] ^= 0xFF                                            # Teil 1 kaputt
    (dest / "dem-hoch.pmtiles.part").write_bytes(bytes(bad))
    assert pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", dest).read_bytes() == data


def test_falsche_pruefsumme_auf_dem_server(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    files["dem-hoch.pmtiles.part01"] = b"x" * 1000
    s = srv_factory(files)
    with pytest.raises(pakete.PaketError, match="Prüfsumme"):
        pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", tmp_path / "dest", backoff=0.01)
    assert not (tmp_path / "dest" / "dem-hoch.pmtiles").exists()


def test_teil_fehlt(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    del files["dem-hoch.pmtiles.part03"]
    s = srv_factory(files)
    with pytest.raises(pakete.PaketError, match="nicht gefunden"):
        pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", tmp_path / "dest", backoff=0.01)
    assert not (tmp_path / "dest" / "dem-hoch.pmtiles").exists()


def test_abbrechen_per_event(tmp_path, srv_factory):
    data, man, files = paket(tmp_path)
    s = srv_factory(files)
    ev = threading.Event()
    ev.set()
    with pytest.raises(pakete.PaketError, match="abgebrochen"):
        pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", tmp_path / "dest", cancel=ev)


@pytest.mark.parametrize("url", ["http://example.com/m.json", "ftp://x/y", "file:///etc/passwd", "https://u:p@example.com/m.json"])
def test_adresse_nur_https(url):
    with pytest.raises(pakete.PaketError):
        pakete.check_url(url)


def good():
    p = {"file": "a.part01", "bytes": 5, "sha256": "0" * 64}
    return {"name": "dem-hoch.pmtiles", "bytes": 5, "sha256": "0" * 64, "parts": [p]}


def test_manifest_gueltig():
    assert pakete.parse_manifest(json.dumps(good()).encode())["name"] == "dem-hoch.pmtiles"


@pytest.mark.parametrize("mut", [
    lambda m: m.update(name="../x.pmtiles"),
    lambda m: m.update(name="x.exe"),
    lambda m: m["parts"][0].update(file="../a.part01"),
    lambda m: m["parts"][0].update(file="a/b"),
    lambda m: m.update(bytes=6),
    lambda m: m.update(sha256="zz"),
    lambda m: m.update(parts=[]),
    lambda m: m["parts"][0].update(bytes=-5),
])
def test_manifest_ungueltig(mut):
    m = good()
    mut(m)
    with pytest.raises(pakete.PaketError):
        pakete.parse_manifest(json.dumps(m).encode())


def test_zu_wenig_platz(tmp_path, srv_factory, monkeypatch):
    data, man, files = paket(tmp_path)
    s = srv_factory(files)
    monkeypatch.setattr(pakete.shutil, "disk_usage", lambda p: type("U", (), {"free": 10})())
    with pytest.raises(pakete.PaketError, match="Platz"):
        pakete.download(s.url + "dem-hoch.pmtiles.manifest.json", tmp_path / "dest")
