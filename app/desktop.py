"""Lokaler Dienst der Desktop-App: Weboberfläche, Kartenabruf und Sammler in einem Prozess.

Zweck:     Die Tauri-Hülle startet diesen Dienst als Begleitprozess (Sidecar). Er liefert web/ auf 127.0.0.1 aus (mit Teilabrufen
           für PMTiles), lädt beim ersten Start die Karte für das ganze Gebiet (region.yaml: Rheinland-Pfalz plus 80 km) und läuft
           als Sammelzyklus weiter. Es gibt keine Auswahl eines Mittelpunkts: das Gebiet steht fest.
Aufruf:    python -m app.desktop --data-dir ~/.local/share/osint [--port 0] [--pmtiles /pfad/pmtiles]
Beispiel:  python -m app.desktop --data-dir /tmp/osint-demo --port 8765   → http://127.0.0.1:8765/
Ablauf:    Start → Zeile "OSINT_READY port=N" auf stdout → Seite einrichtung.html (nur Fortschritt), solange Karte und Daten fehlen.
Sicherheit: nur 127.0.0.1, Host-Prüfung gegen DNS-Rebinding, schreibende Aufrufe nur mit Header X-OSINT und gleicher Herkunft.
           Nach außen geht: Kartenabruf bei Protomaps, die Quellen laut sources.yaml.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("osint.desktop")


def use_certifi() -> str | None:
    """Zertifikatsbündel für urllib setzen. Im gebündelten Programm (PyInstaller, macOS) findet Python sonst keine Stammzertifikate
    (CERTIFICATE_VERIFY_FAILED). Eine vom Nutzer gesetzte SSL_CERT_FILE bleibt unberührt; Kindprozesse erben die Variable."""
    if os.environ.get("SSL_CERT_FILE"):
        return os.environ["SSL_CERT_FILE"]
    try:
        import certifi
        path = certifi.where()
    except ImportError:
        return None
    if not Path(path).is_file():
        log.warning("certifi-Bündel fehlt: %s", path)
        return None
    os.environ["SSL_CERT_FILE"] = path
    return path


use_certifi()
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
CYCLE_S = 300


class Job:
    """Zustand der Einrichtung, thread-sicher lesbar."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.phase, self.msg, self.pct, self.error = "idle", "", 0, ""

    def set(self, phase: str, msg: str = "", pct: int | None = None, error: str = "") -> None:
        with self.lock:
            self.phase, self.msg, self.error = phase, msg, error
            if pct is not None:
                self.pct = pct

    def snapshot(self) -> dict:
        with self.lock:
            return {"phase": self.phase, "msg": self.msg, "pct": self.pct, "error": self.error}


class App:
    def __init__(self, data_dir: Path, web_dir: Path, pmtiles: Path, repo_dir: Path, sources_path: Path | None = None) -> None:
        self.data_dir, self.web_dir, self.pmtiles, self.repo_dir = data_dir, web_dir.resolve(), pmtiles, repo_dir
        self.job = Job()
        self.progress_path = data_dir / ".collect-progress.json"      # Fortschritt des Sammellaufs (app/collect.py), nur Quellennamen
        self.later_progress_path = data_dir / ".collect-later.json"   # Nachlauf der langsamen Quellen im Hintergrund
        self.worker: threading.Thread | None = None
        self.later: threading.Thread | None = None
        try:
            from app.registry import Registry
            entries = Registry.load(sources_path or repo_dir / "sources.yaml").entries
        except (OSError, ValueError) as err:   # ohne Register keine Zugangsfelder, der Rest der App läuft
            log.warning("Quellenregister nicht lesbar, keine Zugangsfelder: %s", err)
            entries = []
        from app.zugang import ZugangStore
        self.zugang = ZugangStore(data_dir / "zugang.json", entries)
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "data").mkdir(exist_ok=True)
        (data_dir / "tiles").mkdir(exist_ok=True)
        self._packs: dict[str, tuple[tuple[str, float], object]] = {}
        self._packs_lock = threading.Lock()

    def pack(self, name: str):
        """Kachelpaket tiles/<name>.pmtiles (erst Datenordner, dann App) als PackArchive oder None. Öffnet neu, wenn die Datei sich ändert."""
        from app.tilepack import PackArchive, PackError
        for root in (self.data_dir, self.web_dir):
            f = root / "tiles" / f"{name}.pmtiles"
            try:
                st = f.stat()
            except OSError:
                continue
            key = (str(f), st.st_mtime)
            with self._packs_lock:
                hit = self._packs.get(name)
                if hit and hit[0] == key:
                    return hit[1]
                try:
                    pk = PackArchive(f)
                except (OSError, PackError) as err:
                    log.warning("Kachelpaket %s unlesbar: %s", f, err)
                    continue
                if hit:
                    hit[1].close()
                self._packs[name] = (key, pk)
                return pk
        return None

    def env(self, progress: Path | None = None) -> dict:
        e = dict(os.environ)
        e.update(OSINT_DB_PATH=str(self.data_dir / "osint.sqlite"), OSINT_WEB_DIR=str(self.web_dir), OSINT_NO_DOTENV="1")
        e.update(self.zugang.env())   # Zugangsdaten aus der Quellenübersicht, nur freigegebene Namen
        if progress:
            e["OSINT_PROGRESS_FILE"] = str(progress)
        return e

    def _run(self, args: list[str], progress: Path | None = None, timeout: int = 1800) -> int:
        """Sammler und Export als Kindprozess. Im gebündelten Programm (PyInstaller) ruft es sich selbst mit --run auf."""
        cmd = [sys.executable, "--run", *args] if getattr(sys, "frozen", False) else [sys.executable, "-m", *args]
        return subprocess.run(cmd, cwd=self.repo_dir, env=self.env(progress), timeout=timeout).returncode

    def job_snapshot(self) -> dict:
        """Zustand des Aufbaus. Im Sammellauf kommt "n von m, läuft noch: <Namen>" aus der Fortschrittsdatei des Sammlers."""
        j = self.job.snapshot()
        if j["phase"] == "collect":
            try:
                p = json.loads(self.progress_path.read_text(encoding="utf-8"))
                total, done = int(p["total"]), int(p["done"])
                names = [str(x)[:40] for x in p.get("running", [])][:4]
                j["msg"] = f"Quellen: {done} von {total} abgerufen" + (f", läuft noch: {', '.join(names)}" if names else "")
                j["pct"] = 70 + int(20 * done / total) if total > 0 else j["pct"]
            except (OSError, ValueError, KeyError, TypeError):
                pass   # Datei fehlt noch oder wird gerade ersetzt: die letzte Meldung bleibt stehen
        return j

    def start(self) -> bool:
        if self.worker and self.worker.is_alive():
            return False
        self.worker = threading.Thread(target=self.work, daemon=True, name="osint-worker")
        self.worker.start()
        return True

    def tiles_fehlen(self) -> bool:
        return not all((self.data_dir / "tiles" / n).exists() for n in ("region.pmtiles", "core.pmtiles", "ring.pmtiles"))

    def holen_tiles(self) -> None:
        """Karte für das ganze Gebiet (tools/build_region_tiles.py): in Stücken, jeder Lauf macht dort weiter, wo der vorige aufhörte.
        Fortschritt: fertige Stücke in tiles-work/chunks (Gesamtzahl bei der Fläche rund 150, die Anzeige wächst darauf zu)."""
        work = self.data_dir / "tiles-work"
        args = ["tools.build_region_tiles", "--pmtiles", str(self.pmtiles), "--work", str(work), "--out", str(self.data_dir / "tiles"),
                "--region", str(self.repo_dir / "region.yaml"), "--budget-s", "600"]
        for versuch in range(60):
            n = len(list((work / "chunks").glob("*/*.pmtiles"))) if (work / "chunks").exists() else 0
            self.job.set("tiles", f"Karte wird geholt ({n} Stücke fertig, einmalig rund 1,5 GB)", 5 + min(60, int(60 * n / 150)))
            rc = self._run(args, timeout=1500)
            if rc == 0:
                return
            if rc != 2:
                raise RuntimeError(f"Kartenabruf fehlgeschlagen (Code {rc})")
        raise RuntimeError("Karte nach 60 Läufen noch nicht vollständig")

    def work(self) -> None:
        """Karte holen (einmalig), danach Sammeln und Exportieren im Takt. Fehler stoppen den Aufbau sichtbar, nie still."""
        try:
            if self.tiles_fehlen():
                self.holen_tiles()
            first = True
            while True:
                self.job.set("collect", "Daten werden abgerufen", 70)
                # Erster Lauf: alle Quellen außer den langsamen (erstlauf: spaeter), danach nur, was fällig ist
                if self._run(["app.collect", "--once" if first else "--due", "--skip-later"], self.progress_path) != 0:
                    log.warning("Sammelzyklus mit Fehlern beendet")
                self.job.set("export", "Daten werden aufbereitet", 90)
                if self._run(["app.export", "--out", str(self.data_dir / "data")]) != 0:
                    raise RuntimeError("Export fehlgeschlagen")
                self.job.set("ready", "Bereit", 100)
                self.start_later()
                first = False
                time.sleep(CYCLE_S)
        except Exception as err:   # sichtbar machen, nicht verschlucken
            log.exception("Aufbau abgebrochen")
            self.job.set("error", "Abbruch", error=str(err)[:300])

    def start_later(self) -> None:
        """Langsame Quellen (erstlauf: spaeter, z. B. OSM-Abfragen) im Hintergrund; ihre Daten kommen mit dem nächsten Export dazu.
        --due holt sie beim ersten Mal (nie versucht = fällig) und danach nur im Intervall, auch nach einem Neustart der App."""
        if self.later and self.later.is_alive():
            return

        def run() -> None:
            try:
                self._run(["app.collect", "--due", "--only-later"], self.later_progress_path, timeout=3 * 3600)
            except (subprocess.SubprocessError, OSError) as err:
                log.warning("Nachlauf der langsamen Quellen abgebrochen: %s", err)

        self.later = threading.Thread(target=run, daemon=True, name="osint-later")
        self.later.start()


PROJECT_URL = "https://github.com/thorin-eifel/maps"


def ua() -> str:
    """User-Agent mit Kontakt. Ohne OSINT_CONTACT der Projektlink: Nominatim weist Platzhalteradressen (example.invalid) mit 403 ab."""
    return f"Landblick/1.0 (+{os.environ.get('OSINT_CONTACT') or PROJECT_URL})"


_PACK_URL = re.compile(r"^/tiles/(dem|klippen|hang)/(README\.txt|meta\.json|(\d{1,2})/(\d{1,8})/(\d{1,8})\.(png|pbf))$")
_PACK_TYPES = {"png": "image/png", "pbf": "application/x-protobuf"}


def make_handler(app: App, port_box: list[int]):
    class H(SimpleHTTPRequestHandler):
        extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".json": "application/json", ".pmtiles": "application/octet-stream",
                          ".css": "text/css", ".html": "text/html; charset=utf-8", ".mjs": "text/javascript"}

        def log_message(self, fmt: str, *a) -> None:
            log.debug(fmt, *a)

        def end_headers(self) -> None:
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            super().end_headers()

        def host_ok(self) -> bool:
            return (self.headers.get("Host") or "") in {f"127.0.0.1:{port_box[0]}", f"localhost:{port_box[0]}"}

        def json(self, obj: object, code: int = 200) -> None:
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def translate_path(self, path: str) -> str:
            """/data/ nur aus dem Datenordner (nie Beispieldaten eines anderen Ortes), /tiles/ erst dort, dann aus der App."""
            p = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
            roots = [app.data_dir] if p.startswith("/data/") else [app.data_dir, app.web_dir] if p.startswith("/tiles/") else [app.web_dir]
            for root in roots:
                cand = (root / p.lstrip("/")).resolve()
                if (cand == root or root in cand.parents) and (cand.is_file() or cand.is_dir()):
                    return str(cand)
            return str(app.web_dir / "__nicht_da__")

        def do_GET(self) -> None:
            if not self.host_ok():
                return self.json({"error": "host"}, 403)
            u = urllib.parse.urlsplit(self.path)
            if u.path == "/api/state":
                return self.json({"configured": True, "job": app.job_snapshot()})
            if u.path == "/api/zugang":
                return self.json({"quellen": app.zugang.status()})   # nur gesetzt/nicht gesetzt, nie Werte
            if u.path.startswith("/api/"):
                return self.json({"error": "unbekannt"}, 404)
            if self.serve_pack(u.path, head=False):
                return
            return self.serve_range()

        def serve_pack(self, path: str, head: bool) -> bool:
            """tiles/dem/… und tiles/klippen/… aus dem Kachelpaket, wenn es den Ordner nicht gibt. Ein vorhandener Ordner hat Vorrang.

            README.txt und meta.json sind die Prüfdateien der Karte; meta.json kommt aus den Metadaten des Pakets.
            True, wenn die Anfrage hier beantwortet wurde (auch mit 404 für eine Kachel, die das Paket nicht enthält).
            """
            m = _PACK_URL.match(path)
            if not m or os.path.isfile(self.translate_path(path)):
                return False
            pk = app.pack(m.group(1))
            if pk is None:
                return False
            if m.group(3) is None:
                body = (b"Kachelpaket, gelesen aus " + pk.path.name.encode() + b"\n") if m.group(2) == "README.txt" else json.dumps(pk.metadata(), ensure_ascii=False).encode()
                ctype = "text/plain; charset=utf-8" if m.group(2) == "README.txt" else "application/json"
                got, gz = body, False
            else:
                try:
                    hit = pk.get(int(m.group(3)), int(m.group(4)), int(m.group(5)))
                except (OSError, ValueError):
                    log.exception("Kachelpaket %s: Lesefehler", pk.path)
                    self.send_error(500)
                    return True
                if hit is None:
                    self.send_error(404)
                    return True
                got, gz = hit
                ctype = _PACK_TYPES[m.group(6)]
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            if gz:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(got)))
            self.end_headers()
            if not head:
                self.wfile.write(got)
            return True

        def do_POST(self) -> None:
            if not self.host_ok() or self.headers.get("X-OSINT") != "1":
                return self.json({"error": "verweigert"}, 403)
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{port_box[0]}", f"http://localhost:{port_box[0]}"}:
                return self.json({"error": "herkunft"}, 403)
            if self.path == "/api/zugang":
                return self.post_zugang()
            return self.json({"error": "unbekannt"}, 404)

        def post_zugang(self) -> None:
            """{"env": "NAME", "wert": "…"} setzt, {"env": "NAME", "loeschen": true} entfernt. Antworten enthalten nie den Wert."""
            from app.zugang import ZugangError
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
                env = body["env"]
                if not isinstance(env, str):
                    raise ZugangError("Unbekannte Zugangsvariable")
                if body.get("loeschen") is True:
                    app.zugang.delete(env)
                else:
                    app.zugang.set(env, body.get("wert"))
            except ZugangError as err:
                return self.json({"error": str(err)}, 400)
            except (ValueError, KeyError, TypeError):
                return self.json({"error": "Eingabe ungültig"}, 400)
            except OSError:
                log.exception("Zugangsdatei nicht schreibbar")
                return self.json({"error": "Datei im Datenordner nicht schreibbar"}, 500)
            self.json({"ok": True, "quellen": app.zugang.status()})

        def serve_range(self) -> None:
            header, path = self.headers.get("Range"), self.translate_path(self.path)
            m = _RANGE.match(header.strip()) if header else None
            if not m or not os.path.isfile(path) or (m.group(1) == "" and m.group(2) == ""):
                return SimpleHTTPRequestHandler.do_GET(self)
            size = os.path.getsize(path)
            if m.group(1) == "":
                start, end = max(0, size - int(m.group(2))), size - 1
            else:
                start, end = int(m.group(1)), min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
            if start >= size or start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                return self.end_headers()
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        def do_HEAD(self) -> None:
            if not self.host_ok():
                return self.json({"error": "host"}, 403)
            if self.serve_pack(urllib.parse.urlsplit(self.path).path, head=True):
                return
            super().do_HEAD()
    return H


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--run"] and len(argv) >= 2:   # Kindaufruf im gebündelten Programm: python -m <modul> <args>
        import runpy
        sys.argv = [argv[1], *argv[2:]]
        runpy.run_module(argv[1], run_name="__main__")
        return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))   # gebündelt: Entpackordner von PyInstaller
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--web-dir", type=Path, default=root / "web")
    ap.add_argument("--pmtiles", type=Path, default=Path("pmtiles"))
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--log-level", default="INFO")
    a = ap.parse_args(argv)
    logging.basicConfig(level=a.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    app = App(a.data_dir, a.web_dir, a.pmtiles, root)
    box = [0]
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(app, box))
    box[0] = srv.server_address[1]
    app.start()
    print(f"OSINT_READY port={box[0]}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
