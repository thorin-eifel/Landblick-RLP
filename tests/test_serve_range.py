"""Lokaler Vorschauserver und Range-Prüfwerkzeug gegeneinander getestet."""
import importlib.util
import sys
import threading
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


serve = _load("serve_local", "deploy/serve-local.py")
check_range = _load("check_range", "tools/check_range.py")


@pytest.fixture
def server(tmp_path):
    (tmp_path / "tiles").mkdir()
    (tmp_path / "tiles" / "region.pmtiles").write_bytes(b"PMTiles" + bytes(range(256)) * 8)
    (tmp_path / "index.html").write_text("<p>hallo</p>")
    srv = serve.make_server(str(tmp_path), 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_range_partial_and_suffix(server):
    data = b"PMTiles" + bytes(range(256)) * 8
    r = httpx.get(f"{server}/tiles/region.pmtiles", headers={"Range": "bytes=0-6"})
    assert r.status_code == 206 and r.content == b"PMTiles"
    assert r.headers["content-range"] == f"bytes 0-6/{len(data)}"
    r = httpx.get(f"{server}/tiles/region.pmtiles", headers={"Range": "bytes=100-199"})
    assert r.status_code == 206 and r.content == data[100:200]
    r = httpx.get(f"{server}/tiles/region.pmtiles", headers={"Range": "bytes=-10"})
    assert r.status_code == 206 and r.content == data[-10:]
    r = httpx.get(f"{server}/tiles/region.pmtiles", headers={"Range": f"bytes={len(data) - 5}-"})
    assert r.status_code == 206 and r.content == data[-5:]


def test_range_edge_cases(server):
    r = httpx.get(f"{server}/tiles/region.pmtiles", headers={"Range": "bytes=999999-"})
    assert r.status_code == 416
    r = httpx.get(f"{server}/tiles/region.pmtiles")  # ohne Range: ganze Datei
    assert r.status_code == 200 and r.content.startswith(b"PMTiles")
    r = httpx.get(f"{server}/index.html", headers={"Range": "bytes=0-2"})
    assert r.status_code == 206 and r.content == b"<p>"
    assert httpx.get(f"{server}/gibtsnicht", headers={"Range": "bytes=0-2"}).status_code == 404


def test_check_range_tool_ok_and_detects_missing_range(server, tmp_path):
    assert check_range.check(f"{server}/tiles/region.pmtiles") == []

    def no_range(request: httpx.Request) -> httpx.Response:  # Server, der Range ignoriert (wie ein schlechter Proxy)
        return httpx.Response(200, content=b"PMTiles" + b"x" * 500)

    with httpx.Client(transport=httpx.MockTransport(no_range)) as c:
        problems = check_range.check("https://example.invalid/x.pmtiles", client=c)
    assert problems and "ignoriert Range" in problems[0]

    def wrong_file(request: httpx.Request) -> httpx.Response:
        return httpx.Response(206, content=b"<html>Fehlerseite!", headers={"content-range": "bytes 0-15/900"})

    with httpx.Client(transport=httpx.MockTransport(wrong_file)) as c:
        problems = check_range.check("https://example.invalid/x.pmtiles", n=16, client=c)
    assert any("PMTiles-Kennung" in p or "Bytes" in p for p in problems)


# --- Zugangsdaten (API-Schlüssel) über /api/zugang, nur auf Loopback -------------------------------------------------------------

@pytest.fixture
def zserver(tmp_path):
    (tmp_path / "w").mkdir()
    store = serve.make_zugang(str(tmp_path / "zugang.json"), str(ROOT / "sources.yaml"))
    srv = serve.make_server(str(tmp_path / "w"), 0, "127.0.0.1", store)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path / "zugang.json"
    srv.shutdown()
    srv.server_close()


def test_zugang_status_setzen_loeschen(zserver):
    base, datei = zserver
    st = httpx.get(f"{base}/api/zugang").json()["quellen"]
    felder = {f["env"]: f["gesetzt"] for q in st for f in q["felder"]}
    assert felder["TANKERKOENIG_API_KEY"] is False
    r = httpx.post(f"{base}/api/zugang", json={"env": "TANKERKOENIG_API_KEY", "wert": "geheim-123"}, headers={"X-OSINT": "1"})
    assert r.status_code == 200 and "geheim-123" not in r.text
    assert "geheim-123" not in httpx.get(f"{base}/api/zugang").text
    assert datei.exists() and (datei.stat().st_mode & 0o777) == 0o600
    r = httpx.post(f"{base}/api/zugang", json={"env": "TANKERKOENIG_API_KEY", "loeschen": True}, headers={"X-OSINT": "1"})
    assert r.status_code == 200
    assert all(not f["gesetzt"] for q in r.json()["quellen"] for f in q["felder"])


def test_zugang_verweigert_ohne_header_fremder_host_unbekannte_variable(zserver):
    base, _ = zserver
    assert httpx.post(f"{base}/api/zugang", json={"env": "TANKERKOENIG_API_KEY", "wert": "x"}).status_code == 403
    assert httpx.post(f"{base}/api/zugang", json={"env": "TANKERKOENIG_API_KEY", "wert": "x"}, headers={"X-OSINT": "1", "Origin": "http://evil.example"}).status_code == 403
    assert httpx.get(f"{base}/api/zugang", headers={"Host": "evil.example"}).status_code == 403
    assert httpx.post(f"{base}/api/zugang", json={"env": "PATH", "wert": "x"}, headers={"X-OSINT": "1"}).status_code == 400


def test_zugang_nicht_ausserhalb_von_loopback(tmp_path):
    store = serve.make_zugang(str(tmp_path / "zugang.json"), str(ROOT / "sources.yaml"))
    srv = serve.make_server(str(tmp_path), 0, "0.0.0.0", store)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = httpx.post(f"http://127.0.0.1:{srv.server_address[1]}/api/zugang", json={"env": "TANKERKOENIG_API_KEY", "wert": "x"}, headers={"X-OSINT": "1"})
        assert r.status_code == 404
    finally:
        srv.shutdown()
        srv.server_close()


def test_config_liest_zugang_datei(tmp_path, monkeypatch):
    from app import config
    f = tmp_path / "zugang.json"
    f.write_text('{"TANKERKOENIG_API_KEY": "abc", "kaputt name": "x", "PATH": "wird-nicht-gesetzt-weil-gesetzt"}')
    monkeypatch.delenv("TANKERKOENIG_API_KEY", raising=False)
    assert config.load_zugang(f) == 1
    import os
    assert os.environ["TANKERKOENIG_API_KEY"] == "abc"
    monkeypatch.delenv("TANKERKOENIG_API_KEY")


def test_zugang_zeigt_schluessel_aus_env_datei_als_extern(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TANKERKOENIG_API_KEY=abc\nFIRMS_MAP_KEY=\n")
    from app.registry import Registry
    from app.zugang import ZugangStore
    st = ZugangStore(tmp_path / "z.json", Registry.load(ROOT / "sources.yaml").entries, dotenv=env)
    felder = {f["env"]: f for q in st.status() for f in q["felder"]}
    assert felder["TANKERKOENIG_API_KEY"]["extern"] and not felder["TANKERKOENIG_API_KEY"]["gesetzt"]
    assert not felder["FIRMS_MAP_KEY"]["extern"]
    assert "abc" not in str(st.status())
