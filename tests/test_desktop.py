import json
import logging
import subprocess
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError

import pytest

from app import desktop


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    web = tmp_path / "web"; (web / "data").mkdir(parents=True); (web / "index.html").write_text("<p>hi</p>")
    (web / "data" / "alt.json").write_text("{}")          # Beispieldaten der App dürfen nie ausgeliefert werden
    d = tmp_path / "d"
    app = desktop.App(d, web, tmp_path / "pmtiles", tmp_path)
    started = []
    monkeypatch.setattr(app, "start", lambda: started.append(1) or True)
    box = [0]
    s = ThreadingHTTPServer(("127.0.0.1", 0), desktop.make_handler(app, box)); box[0] = s.server_address[1]
    threading.Thread(target=s.serve_forever, daemon=True).start()
    (d / "tiles" / "x.pmtiles").write_bytes(bytes(range(256)) * 4)
    yield app, box[0], started
    s.shutdown()


def call(port, path, method="GET", body=None, headers=None, host=None):
    h = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode() if body is not None else None, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read(), dict(r.headers)
    except HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test_state_has_no_center_choice(srv):
    _, port, _ = srv
    st, body, _ = call(port, "/api/state")
    j = json.loads(body)
    assert st == 200 and j["configured"] is True and "center" not in j and j["job"]["phase"] == "idle"


def test_foreign_host_rejected(srv):
    _, port, _ = srv
    assert call(port, "/api/state", host="evil.example")[0] == 403


def test_setup_and_geocode_are_gone(srv):
    _, port, _ = srv
    assert call(port, "/api/setup", "POST", {"lat": 49.8, "lon": 6.4}, {"X-Landblick": "1"})[0] == 404
    assert call(port, "/api/geocode?q=Irrel")[0] == 404
    assert not hasattr(desktop, "geocode")


def test_tiles_missing_until_all_three_files_exist(srv):
    app, _, _ = srv
    assert app.tiles_fehlen()
    for n in ("region", "core", "ring"):
        (app.data_dir / "tiles" / f"{n}.pmtiles").write_bytes(b"x")
    assert not app.tiles_fehlen()


def test_data_comes_only_from_data_dir_and_range_works(srv):
    _, port, _ = srv
    assert call(port, "/data/alt.json")[0] == 404
    st, body, hd = call(port, "/tiles/x.pmtiles", headers={"Range": "bytes=2-5"})
    assert st == 206 and body == bytes([2, 3, 4, 5]) and hd["Content-Range"] == "bytes 2-5/1024"


def test_no_path_traversal(srv):
    _, port, _ = srv
    assert call(port, "/tiles/..%2f..%2fetc%2fpasswd")[0] == 404


def test_use_certifi_sets_bundle_and_respects_user_value(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    path = desktop.use_certifi()
    assert path and path.endswith("cacert.pem") and desktop.os.environ["SSL_CERT_FILE"] == path
    monkeypatch.setenv("SSL_CERT_FILE", "/etc/eigenes.pem")
    assert desktop.use_certifi() == "/etc/eigenes.pem"


def test_user_agent_has_real_contact_by_default(monkeypatch):
    monkeypatch.delenv("LANDBLICK_CONTACT", raising=False)
    assert ".invalid" not in desktop.ua() and desktop.PROJECT_URL in desktop.ua()    # Nominatim: 403 bei Platzhalteradresse
    monkeypatch.setenv("LANDBLICK_CONTACT", "mail@beispiel.de")
    assert "mail@beispiel.de" in desktop.ua()


# --- Kachelpakete: Relief und Felswände aus einer PMTiles-Datei unter der alten Ordner-URL -----------------------------

def _make_pack(tmp_path, name, ext, tiles, meta=None):
    """Packt Kacheln {(z,x,y): bytes} mit tools/pack_tiles.py nach <tmp>/<name>.pmtiles."""
    from tools import pack_tiles
    src = tmp_path / f"src_{name}"
    for (z, x, y), data in tiles.items():
        p = src / str(z) / str(x) / f"{y}.{ext}"
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    out = tmp_path / f"{name}.pmtiles"
    pack_tiles.pack(src, out, meta or {})
    return out


def test_pack_serves_tiles_readme_and_meta(srv, tmp_path):
    app, port, _ = srv
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 40
    pk = _make_pack(tmp_path, "dem", "png", {(12, 2145, 1380): png, (6, 33, 21): b"\x89PNGklein"}, {"attribution": "DGM1 test"})
    (app.data_dir / "tiles" / "dem.pmtiles").write_bytes(pk.read_bytes())
    st, body, h = call(port, "/tiles/dem/12/2145/1380.png")
    assert st == 200 and body == png and h["Content-Type"] == "image/png" and "Content-Encoding" not in h
    assert call(port, "/tiles/dem/README.txt")[0] == 200
    st, body, _ = call(port, "/tiles/dem/meta.json")
    assert st == 200 and json.loads(body)["attribution"] == "DGM1 test"
    assert call(port, "/tiles/dem/12/1/1.png")[0] == 404
    assert call(port, "/tiles/dem/12/2145/1380.png", method="HEAD")[0] == 200


def test_pack_gzip_vector_tiles_keep_encoding(srv, tmp_path):
    import gzip
    app, port, _ = srv
    raw = b"vektor" * 20
    pk = _make_pack(tmp_path, "klippen", "pbf", {(13, 4290, 2760): gzip.compress(raw)})
    (app.data_dir / "tiles" / "klippen.pmtiles").write_bytes(pk.read_bytes())
    st, body, h = call(port, "/tiles/klippen/13/4290/2760.pbf")
    assert st == 200 and h.get("Content-Encoding") == "gzip" and gzip.decompress(body) == raw


def test_pack_missing_and_folder_priority(srv, tmp_path):
    app, port, _ = srv
    assert call(port, "/tiles/dem/README.txt")[0] == 404               # weder Ordner noch Paket
    pk = _make_pack(tmp_path, "dem", "png", {(12, 1, 1): b"aus-dem-paket"})
    (app.data_dir / "tiles" / "dem.pmtiles").write_bytes(pk.read_bytes())
    d = app.data_dir / "tiles" / "dem" / "12" / "1"; d.mkdir(parents=True); (d / "1.png").write_bytes(b"aus-dem-ordner")
    assert call(port, "/tiles/dem/12/1/1.png")[1] == b"aus-dem-ordner"  # vorhandene Datei hat Vorrang


def test_pack_rejects_odd_paths_and_broken_files(srv):
    app, port, _ = srv
    (app.data_dir / "tiles" / "dem.pmtiles").write_bytes(b"kein pmtiles")
    assert call(port, "/tiles/dem/12/1/1.png")[0] == 404
    assert call(port, "/tiles/dem/../../etc/passwd")[0] in (400, 403, 404)
    assert call(port, "/tiles/other/1/1/1.png")[0] == 404


def test_pack_more_serves_higher_zoom_from_second_file(srv, tmp_path):
    app, port, _ = srv
    base = _make_pack(tmp_path, "dem", "png", {(12, 1, 1): b"niedrig"})
    more = _make_pack(tmp_path, "dem-hoch", "png", {(13, 2, 2): b"hoch"})
    (app.data_dir / "tiles" / "dem.pmtiles").write_bytes(base.read_bytes())
    (app.data_dir / "tiles" / "dem-hoch.pmtiles").write_bytes(more.read_bytes())
    assert call(port, "/tiles/dem/12/1/1.png")[1] == b"niedrig"
    assert call(port, "/tiles/dem/13/2/2.png")[1] == b"hoch"
    assert call(port, "/tiles/dem/13/9/9.png")[0] == 404


def test_nachladen_aus_ohne_manifest(srv, monkeypatch):
    app, port, _ = srv
    monkeypatch.delenv("LANDBLICK_PAKETE_MANIFEST", raising=False)
    monkeypatch.setattr("app.desktop.PAKETE_MANIFEST", "")
    assert app.start_nachladen() is False
    assert json.loads(call(port, "/api/state")[1])["nachladen"]["phase"] == "idle"


def test_nachladen_holt_paket_und_meldet_zustand(srv, tmp_path, monkeypatch):
    from tests.test_pakete import Srv, paket
    app, port, _ = srv
    data, man, files = paket(tmp_path)
    s = Srv(files)
    try:
        monkeypatch.setenv("LANDBLICK_PAKETE_MANIFEST", s.url + "dem-hoch.pmtiles.manifest.json")
        assert app.start_nachladen() is True
        app.nachlade_thread.join(10)
        assert (app.data_dir / "tiles" / "dem-hoch.pmtiles").read_bytes() == data
        assert json.loads(call(port, "/api/state")[1])["nachladen"]["phase"] == "ready"
        assert app.start_nachladen() is False      # schon da: kein zweiter Abruf
    finally:
        s.close()


def test_nachladen_fehler_bleibt_sichtbar(srv, tmp_path, monkeypatch):
    from tests.test_pakete import Srv
    app, _, _ = srv
    s = Srv({})
    try:
        monkeypatch.setenv("LANDBLICK_PAKETE_MANIFEST", s.url + "fehlt.json")
        app.start_nachladen()
        app.nachlade_thread.join(10)
        j = app.nachladen.snapshot()
        assert j["phase"] == "error" and j["error"]
    finally:
        s.close()


def test_mitgelieferte_pakete_werden_gelesen(srv, tmp_path):
    app, port, _ = srv
    res = tmp_path / "res"
    (res / "tiles").mkdir(parents=True); (res / "data").mkdir()
    (res / "tiles" / "gebaeude.pmtiles").write_bytes(b"PMTiles-ish" * 10)
    (res / "data" / "suche_geo.json").write_text("[1]")
    (res / "data" / "geheim.json").write_text("[2]")
    app.pack_dirs = [res.resolve()]
    assert call(port, "/tiles/gebaeude.pmtiles", headers={"Range": "bytes=0-3"})[0] == 206
    assert call(port, "/data/suche_geo.json")[1] == b"[1]"
    assert call(port, "/data/geheim.json")[0] == 404          # nur der feste Suchindex kommt aus dem Installer


def test_tiles_fehlen_zaehlt_mitgelieferte(srv, tmp_path):
    app, _, _ = srv
    res = tmp_path / "res"; (res / "tiles").mkdir(parents=True)
    for n in ("region", "core", "ring"):
        (res / "tiles" / f"{n}.pmtiles").write_bytes(b"x")
    assert app.tiles_fehlen()
    app.pack_dirs = [res.resolve()]
    assert not app.tiles_fehlen()


def _raw_get(port, path):
    """Roher Pfad ohne Normalisierung (wie curl --path-as-is); urllib würde '..' nicht entfernen, http.client schickt ihn unverändert."""
    import http.client
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse(); body = r.read(); c.close()
    return r.status, body


def test_traversal_erreicht_zugang_und_datenbank_nicht(srv):
    """Befund H1: /data/../zugang.json lag vorher innerhalb des Datenordners und wurde ausgeliefert."""
    app, port, _ = srv
    (app.data_dir / "zugang.json").write_text('{"TANKERKOENIG_API_KEY": "geheim"}')
    (app.data_dir / "landblick.sqlite").write_bytes(b"SQLite format 3\0")
    (app.data_dir / "data").mkdir(exist_ok=True); (app.data_dir / "data" / "ok.json").write_text("{}")
    for p in ("/data/../zugang.json", "/data/%2e%2e/zugang.json", "/tiles/../landblick.sqlite", "/tiles/..%2fzugang.json", "/data/..%2flandblick.sqlite"):
        st, body = _raw_get(port, p)
        assert st == 404 and b"geheim" not in body and b"SQLite" not in body, p
    assert _raw_get(port, "/data/ok.json")[0] == 200


def test_datenordner_wird_aufgeloest(tmp_path):
    """Befund M1: relativer oder über Symlink angegebener Datenordner darf Dateien nicht aussperren."""
    import os
    real = tmp_path / "real"; (real / "data").mkdir(parents=True)
    link = tmp_path / "link"; link.symlink_to(real, target_is_directory=True)
    web = tmp_path / "web"; web.mkdir(); (web / "index.html").write_text("x")
    app = desktop.App(link, web, tmp_path / "pm", tmp_path)
    assert app.data_dir == real.resolve()


def test_data_verzeichnis_wird_nicht_aufgelistet(srv):
    app, port, _ = srv
    (app.data_dir / "data").mkdir(exist_ok=True)
    assert _raw_get(port, "/data/")[0] == 404
    assert _raw_get(port, "/tiles/")[0] == 404


def test_work_ueberlebt_timeout_und_exportfehler(tmp_path, monkeypatch):
    """Befund H2: TimeoutExpired oder Exportfehler beendet den Takt nicht."""
    import subprocess
    web = tmp_path / "web"; web.mkdir()
    app = desktop.App(tmp_path / "d", web, tmp_path / "pm", tmp_path)
    monkeypatch.setattr(app, "tiles_fehlen", lambda: False)
    monkeypatch.setattr(app, "start_nachladen", lambda: True)
    monkeypatch.setattr(app, "start_later", lambda: None)
    calls = []

    def fake_run(args, progress=None, timeout=1800):
        calls.append(args[0])
        n = len(calls)
        if n == 1:
            raise subprocess.TimeoutExpired(args, timeout)       # Sammler hängt
        if n == 3:
            return 1                                              # Export scheitert
        return 0

    class Stop(BaseException):
        pass

    sleeps = []

    def fake_sleep(s):
        sleeps.append(s)
        if len(sleeps) >= 3:
            raise Stop

    monkeypatch.setattr(app, "_run", fake_run)
    monkeypatch.setattr(desktop.time, "sleep", fake_sleep)
    with pytest.raises(Stop):
        app.work()
    assert len(sleeps) == 3 and calls.count("app.collect") >= 2
    assert app.job.snapshot()["phase"] in ("ready", "error")


# ---- Protokolldatei im Datenordner ----
# Unter Windows läuft die App ohne Konsole: ohne diese Datei ist jeder Fehler des Dienstes unauffindbar.


@pytest.fixture()
def log_sauber():
    """Handler, die ein Test an den Wurzel-Logger hängt, wieder abnehmen und schließen (sonst bleibt die Datei offen)."""
    wurzel = logging.getLogger()
    vorher = list(wurzel.handlers)
    yield
    for h in [h for h in wurzel.handlers if h not in vorher]:
        wurzel.removeHandler(h)
        h.close()


def test_logdatei_nimmt_meldungen_auf(tmp_path, log_sauber):
    datei = desktop.log_in_datei(tmp_path)
    assert datei == tmp_path / "logs" / "dienst.log"
    logging.getLogger("landblick.desktop").warning("Prüfzeile mit Umlaut: Höhe")
    assert "Prüfzeile mit Umlaut: Höhe" in datei.read_text(encoding="utf-8")


def test_logdatei_rotiert_und_begrenzt_sich(tmp_path, monkeypatch, log_sauber):
    monkeypatch.setattr(desktop, "LOG_BYTES", 2000)
    monkeypatch.setattr(desktop, "LOG_KEEP", 2)
    datei = desktop.log_in_datei(tmp_path)
    for i in range(400):
        logging.getLogger("landblick.desktop").warning("Zeile %d %s", i, "x" * 80)
    stand = sorted(p.name for p in (tmp_path / "logs").iterdir())
    assert stand == ["dienst.log", "dienst.log.1", "dienst.log.2"]     # nicht mehr als LOG_KEEP Sicherungen
    assert all(p.stat().st_size < 10_000 for p in (tmp_path / "logs").iterdir())


def test_unbeschreibbarer_ordner_stoppt_den_dienst_nicht(tmp_path, log_sauber):
    (tmp_path / "logs").write_text("keine Datei, sondern ein Ordnerplatz")   # mkdir scheitert daran
    assert desktop.log_in_datei(tmp_path) is None


def test_fehlerausgabe_des_kindes_steht_im_log(srv, caplog, monkeypatch):
    """Die Ausgabe der Kindprozesse (app.collect, app.export) muss durch das Log laufen, nicht ins geerbte stderr."""
    app, _, _ = srv
    fertig = subprocess.CompletedProcess(args=[], returncode=1, stderr="erste Zeile\nZDM-Fehler: Quelle kaputt\n")
    monkeypatch.setattr(desktop.subprocess, "run", lambda *a, **k: fertig)
    schwanz: list[str] = []
    with caplog.at_level(logging.WARNING, logger="landblick.desktop"):
        assert app._run(["app.collect"], err_tail=schwanz) == 1
    assert "ZDM-Fehler: Quelle kaputt" in caplog.text and "[app.collect]" in caplog.text
    assert schwanz == ["erste Zeile", "ZDM-Fehler: Quelle kaputt"]


def test_kindausgabe_auch_ohne_err_tail_im_log(srv, caplog, monkeypatch):
    app, _, _ = srv
    fertig = subprocess.CompletedProcess(args=[], returncode=0, stderr="Export geschrieben\n")
    monkeypatch.setattr(desktop.subprocess, "run", lambda *a, **k: fertig)
    with caplog.at_level(logging.INFO, logger="landblick.desktop"):
        assert app._run(["app.export"]) == 0
    assert "Export geschrieben" in caplog.text


def test_state_sagt_ob_der_erste_export_schon_da_ist(srv):
    """Daran entscheidet die Oberfläche, ob sie die Aufbauseite zeigt: ohne data/meta.json hat die Karte nichts anzuzeigen."""
    app, port, _ = srv
    j = json.loads(call(port, "/api/state")[1])
    assert j["daten"] is False
    (app.data_dir / "data" / "meta.json").write_text("{}", encoding="utf-8")
    assert json.loads(call(port, "/api/state")[1])["daten"] is True
