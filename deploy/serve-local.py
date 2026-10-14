#!/usr/bin/env python3
"""Lokaler Webserver mit Teilabrufen (HTTP Range) für die Vorschau, auch für PMTiles.

Zweck:    Ersatz für `python -m http.server`, der keine Range-Anfragen versteht und damit
          Kartenkacheln aus einer .pmtiles-Datei nicht liefern kann.
Aufruf:   python deploy/serve-local.py --dir web --port 8080 [--bind 127.0.0.1]
Beispiel: curl -s -H 'Range: bytes=0-15' -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/tiles/region.pmtiles
Hinweis:  Nur für die lokale Ansicht. Der Betrieb läuft auf dem Webspace (Apache).
Zugang:   Auf Loopback (127.0.0.1, ::1) nimmt der Server wie die Desktop-App unter /api/zugang Zugangsdaten (API-Schlüssel) für die Quellen
          entgegen und legt sie in data/zugang.json ab (--zugang ändert den Pfad, Rechte 600). Die Sammler lesen die Datei über app/config.py.
          Auf anderen Adressen (--bind 0.0.0.0) gibt es den Weg nicht.
"""
from __future__ import annotations

import argparse
import functools
import logging
import os
import re
import sys
import json
from pathlib import Path
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("osint.serve")
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class RangeHandler(SimpleHTTPRequestHandler):
    zugang = None   # ZugangStore, nur auf Loopback gesetzt
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript", ".json": "application/json", ".geojson": "application/geo+json",
        ".pmtiles": "application/octet-stream", ".css": "text/css", ".html": "text/html; charset=utf-8",
    }

    def end_headers(self) -> None:
        # Vorschau: Browser fragen bei jeder Datei nach (ETag/Last-Modified), sonst hängen sie an altem JavaScript
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _host_ok(self) -> bool:
        port = self.server.server_address[1]
        return (self.headers.get("Host") or "") in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    def _json(self, obj: object, code: int = 200) -> None:
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/zugang" and self.zugang is not None:
            if not self._host_ok():
                return self._json({"error": "host"}, 403)
            return self._json({"quellen": self.zugang.status()})   # nur gesetzt/nicht gesetzt, nie Werte
        return super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/zugang" or self.zugang is None:
            return self._json({"error": "unbekannt"}, 404)
        port = self.server.server_address[1]
        if not self._host_ok() or self.headers.get("X-OSINT") != "1":
            return self._json({"error": "verweigert"}, 403)
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}", f"http://[::1]:{port}"}:
            return self._json({"error": "herkunft"}, 403)
        from app.zugang import handle_post
        n = int(self.headers.get("Content-Length") or 0)
        code, obj = handle_post(self.zugang, self.rfile.read(min(n, 4096)))
        return self._json(obj, code)

    def log_message(self, fmt: str, *args) -> None:  # ruhiger als der Standard, keine IP im Log
        log.info("%s", fmt % args)

    def send_head(self):
        header = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not header or not os.path.isfile(path):
            return super().send_head()
        m = _RANGE.match(header.strip())
        size = os.path.getsize(path)
        if not m or (m.group(1) == "" and m.group(2) == ""):
            return super().send_head()  # nicht unterstützte Form: ganze Datei
        if m.group(1) == "":  # letzte n Bytes
            n = int(m.group(2))
            start, end = max(0, size - n), size - 1
        else:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
        if start >= size or start > end:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self._remaining = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(self._remaining))
        self.end_headers()
        return f

    def copyfile(self, source, outputfile) -> None:
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self._remaining = None


class _Server(ThreadingHTTPServer):
    # Standard ist eine Warteschlange von 5: Karte, Relief und Kacheln öffnen viele Verbindungen auf einmal, der Rest bekäme "connection reset"
    request_queue_size = 128


def make_zugang(path: str | None, sources: str | None) -> object | None:
    """ZugangStore für /api/zugang; None, wenn das Quellenregister fehlt (dann bleibt die Seite ohne Eingabefelder)."""
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))
    try:
        from app.registry import Registry
        from app.zugang import ZugangStore
        entries = Registry.load(Path(sources) if sources else root / "sources.yaml").entries
    except Exception as err:   # noqa: BLE001  fehlendes yaml, kaputtes Register: Server läuft ohne Zugangsweg weiter
        log.warning("Zugangsdaten nicht verfügbar: %s", err)
        return None
    return ZugangStore(Path(path) if path else root / "data" / "zugang.json", entries, dotenv=root / ".env")


def make_server(directory: str, port: int, bind: str = "127.0.0.1", zugang: object | None = None) -> ThreadingHTTPServer:
    if zugang is not None and bind not in LOOPBACK:
        log.warning("Zugangsdaten werden nur auf Loopback angenommen, nicht auf %s", bind)
        zugang = None
    cls = type("ZugangHandler", (RangeHandler,), {"zugang": zugang})
    return _Server((bind, port), functools.partial(cls, directory=directory))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default="web")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--zugang", default=None, help="Datei für Zugangsdaten (Standard: data/zugang.json); nur auf Loopback")
    ap.add_argument("--sources", default=None, help="Quellenregister (Standard: sources.yaml)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not os.path.isdir(args.dir):
        log.error("Ordner fehlt: %s", args.dir)
        return 2
    srv = make_server(args.dir, args.port, args.bind, make_zugang(args.zugang, args.sources) if args.bind in LOOPBACK else None)
    log.info("Vorschau auf http://%s:%d (Ordner %s)", args.bind, args.port, args.dir)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
