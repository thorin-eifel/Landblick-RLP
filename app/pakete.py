"""Nachladepakete der Desktop-App: große Kachelpakete in Teilen laden, prüfen und zu einer Datei zusammenwachsen lassen.

Zweck:     Das Relief für Zoom 13/14 (rund 4,3 GB) steckt nicht im Installer. Die App holt es beim ersten Start im Hintergrund
           von einer Adresse, die auf ein Manifest zeigt (erzeugt von tools/pack_tiles.py --split-mb). Bis dahin läuft die Karte
           mit dem Relief bis Zoom 12. Der Download setzt nach Abbruch, Neustart oder Netzausfall dort fort, wo er stand.
Manifest:  {"name": "dem-hoch.pmtiles", "bytes": N, "sha256": "…", "parts": [{"file": "….part01", "bytes": N, "sha256": "…"}]}
           Die Teile liegen im selben Verzeichnis wie das Manifest (relative Dateinamen, keine Pfade).
Verfahren: Die Teile werden nacheinander in EINE Datei <name>.part geschrieben (kein Zusammenfügen danach, Spitzenbedarf = Paketgröße).
           Die Dateigröße ist der Fortschritt. Beim Wiederaufnehmen werden fertige Teile erneut geprüft, ein halbes Teil wird mit
           Range-Abruf fortgesetzt. Erst nach bestandener Gesamtprüfsumme wird in <name> umbenannt; vorher sieht der Server nichts.
Aufruf:    python -m app.pakete --manifest https://…/dem-hoch.pmtiles.manifest.json --dest ~/.local/share/landblick/tiles
Sicherheit: nur https (http nur für localhost), Dateinamen aus dem Manifest werden gegen ein enges Muster geprüft, es wird nichts
           ausgeführt und nichts außerhalb von --dest geschrieben. Der Abruf trägt keine Nutzerdaten (nur User-Agent mit Projektlink).
Exit:      0 fertig oder schon vorhanden, 1 Fehler
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import logging
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

log = logging.getLogger("landblick.pakete")

CHUNK = 1024 * 1024
MAX_MANIFEST = 256 * 1024
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}\.pmtiles$")
PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
RESERVE = 200 * 1024 * 1024        # Platz, der nach dem Download noch frei bleiben soll
RETRIES = 5

Progress = Callable[[int, int], None]


class PaketError(Exception):
    """Download oder Prüfung gescheitert; Text ist für die Anzeige gedacht."""


def check_url(url: str) -> str:
    u = urllib.parse.urlsplit(url)
    if u.scheme == "https" or (u.scheme == "http" and u.hostname in LOCAL_HOSTS):
        if u.hostname and not u.username:
            return url
    raise PaketError("Adresse nicht zulässig (nur https)")


def parse_manifest(raw: bytes) -> dict:
    """Manifest lesen und streng prüfen. Wirft PaketError."""
    try:
        man = json.loads(raw.decode("utf-8"))
        name, parts = man["name"], man["parts"]
        if not NAME_RE.match(name) or not SHA_RE.match(man["sha256"]) or not isinstance(parts, list) or not parts or len(parts) > 200:
            raise ValueError("Felder")
        total = 0
        for p in parts:
            if not PART_RE.match(p["file"]) or not SHA_RE.match(p["sha256"]) or type(p["bytes"]) is not int or p["bytes"] <= 0:
                raise ValueError("Teil")
            total += p["bytes"]
        if type(man["bytes"]) is not int or man["bytes"] != total:
            raise ValueError("Summe")
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as err:
        raise PaketError(f"Manifest ungültig ({err})") from err
    return man


def _request(url: str, ua: str, start: int = 0) -> urllib.request.Request:
    h = {"User-Agent": ua}
    if start:
        h["Range"] = f"bytes={start}-"
    return urllib.request.Request(url, headers=h)


def fetch_manifest(url: str, ua: str, timeout: float = 30) -> dict:
    check_url(url)
    try:
        with urllib.request.urlopen(_request(url, ua), timeout=timeout) as r:
            raw = r.read(MAX_MANIFEST + 1)
    except (urllib.error.URLError, OSError) as err:
        raise PaketError(f"Manifest nicht erreichbar: {err}") from err
    if len(raw) > MAX_MANIFEST:
        raise PaketError("Manifest zu groß")
    return parse_manifest(raw)


def _hash_region(fh, start: int, end: int) -> str:
    h = hashlib.sha256()
    fh.seek(start)
    left = end - start
    while left > 0:
        b = fh.read(min(CHUNK, left))
        if not b:
            break
        h.update(b)
        left -= len(b)
    return h.hexdigest()


def _fetch_part(url: str, ua: str, fh, start: int, resume_at: int, end: int, cancel: threading.Event | None,
                tick: Callable[[int], None], timeout: float) -> None:
    """Teil [start, end) holen, ab resume_at fortsetzend. Schreibt an die aktuelle Stelle von fh."""
    fh.seek(resume_at)
    fh.truncate()
    with urllib.request.urlopen(_request(url, ua, resume_at - start), timeout=timeout) as r:
        if resume_at > start and r.status != 206:      # Server ignoriert Range: Teil von vorn
            fh.seek(start)
            fh.truncate()
            tick(-(resume_at - start))
        pos = fh.tell()
        while pos < end:
            if cancel and cancel.is_set():
                raise PaketError("abgebrochen")
            b = r.read(min(CHUNK, end - pos))
            if not b:
                raise ConnectionError("Verbindung vorzeitig beendet")
            fh.write(b)
            pos += len(b)
            tick(len(b))


def download(manifest_url: str, dest: Path, progress: Progress | None = None, cancel: threading.Event | None = None,
             ua: str = "Landblick/1.0", timeout: float = 60, backoff: float = 2.0) -> Path:
    """Paket vollständig nach dest/<name> bringen. Ist es schon da, passiert nichts. Wirft PaketError."""
    man = fetch_manifest(manifest_url, ua)
    name, total = man["name"], man["bytes"]
    final, tmp = dest / name, dest / f"{name}.part"
    if final.exists() and final.stat().st_size == total:
        return final
    dest.mkdir(parents=True, exist_ok=True)
    have0 = tmp.stat().st_size if tmp.exists() else 0
    free = shutil.disk_usage(dest).free
    if free < max(0, total - have0) + RESERVE:
        raise PaketError(f"Zu wenig Platz: {total / 1e9:.1f} GB nötig, {free / 1e9:.1f} GB frei")
    base = manifest_url.rsplit("/", 1)[0] + "/"
    state = {"done": 0, "last": 0.0}

    def tick(n: int) -> None:
        state["done"] += n
        now = time.monotonic()
        if progress and now - state["last"] > 0.5:
            state["last"] = now
            progress(max(0, state["done"]), total)

    if not tmp.exists():
        tmp.touch()
    if tmp.stat().st_size > total:
        with tmp.open("r+b") as fh:
            fh.truncate(total)
    with tmp.open("r+b") as fh:
        start = 0
        for part in man["parts"]:
            end = start + part["bytes"]
            url = check_url(urllib.parse.urljoin(base, part["file"]))
            fails = 0
            while True:
                if cancel and cancel.is_set():
                    raise PaketError("abgebrochen")
                size = fh.seek(0, os.SEEK_END)
                if size >= end:
                    if _hash_region(fh, start, end) == part["sha256"]:
                        state["done"] = max(state["done"], end)
                        break
                    log.warning("Teil %s: Prüfsumme falsch, wird neu geholt", part["file"])
                    fh.truncate(start)
                    size = start
                    fails += 1
                    if fails > 2:
                        raise PaketError(f"Prüfsumme falsch: {part['file']}")
                state["done"] = max(size, start)
                try:
                    _fetch_part(url, ua, fh, start, max(size, start), end, cancel, tick, timeout)
                except PaketError:
                    raise
                except (urllib.error.URLError, OSError, http.client.HTTPException) as err:
                    if isinstance(err, urllib.error.HTTPError) and err.code in (403, 404):
                        raise PaketError(f"Teil nicht gefunden: {part['file']} (HTTP {err.code})") from err
                    fails += 1
                    if fails > RETRIES:
                        raise PaketError(f"Abruf scheitert: {part['file']}: {err}") from err
                    log.warning("Teil %s: %s, neuer Versuch %d/%d", part["file"], err, fails, RETRIES)
                    fh.flush()
                    time.sleep(backoff * fails)
                    continue
                fh.flush()
                # Schleife prüft oben die Prüfsumme des fertigen Teils
            start = end
        fh.flush()
        got = _hash_region(fh, 0, total)
    if got != man["sha256"]:
        tmp.unlink(missing_ok=True)
        raise PaketError("Gesamtprüfsumme falsch, Datei verworfen")
    tmp.replace(final)
    if progress:
        progress(total, total)
    return final


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dest", type=Path, required=True)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        out = download(a.manifest, a.dest, lambda d, t: print(f"\r{100 * d // t:3d} %  {d / 1e6:,.0f} / {t / 1e6:,.0f} MB", end="", file=sys.stderr))
    except PaketError as err:
        log.error("%s", err)
        return 1
    print(f"\n{out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
