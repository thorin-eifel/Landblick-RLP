#!/usr/bin/env python3
"""Rohdaten der Kartenwerkzeuge entfernen, aber erst, wenn alles fertig ist und die App läuft.

Zweck:      Die Werkzeuge build_dem_rlp.py und build_klippen_dgm.py legen im Arbeitsordner (Standard _scratch/dgm1)
            Rohdaten ab: raw/ (1-m-Kacheln, rund 22 GB für RLP) und red/ (4-m-Raster) samt Dateiliste. Danach braucht sie
            niemand mehr; für Anwender, die lokal installieren, sind das Gigabytes ohne Nutzen.
            Dieses Skript löscht den Arbeitsordner, und nur dann, wenn ALLE Prüfungen bestehen:
              1. Relief fertig:   web/tiles/dem/ mit README.txt, meta.json und Kacheln auf der höchsten Zoomstufe
              2. Felswände fertig: web/tiles/klippen/ mit meta.json und Kacheln
              3. Basiskarte da:   web/tiles/region.pmtiles
              4. App läuft:       die Seite antwortet mit 200 und web/data/manifest.json ist gültiges JSON
              5. Kein Schutzvermerk: liegt BEHALTEN.txt im Arbeitsordner, wird nichts gelöscht, bis jemand sie von Hand entfernt
            Ohne --ja wird nur geprüft und angezeigt, was gelöscht würde (Probelauf, Standard).
Löscht:     ausschließlich den Arbeitsordner und nur bekannte Inhalte (raw/, red/, Dateiliste *.meta4, BEHALTEN.txt).
            Liegt dort etwas anderes, bricht das Skript ab. Pfade wie Home, Wurzel oder Projektordner werden abgelehnt.
Parameter:  --work DIR   Arbeitsordner (Standard _scratch/dgm1)
            --web DIR    Webordner mit tiles/ und data/ (Standard web)
            --url URL    Adresse der laufenden App (Standard http://127.0.0.1:8080/)
            --ja         wirklich löschen
Exit:       0 geprüft bzw. gelöscht, 1 eine Prüfung fehlgeschlagen, 2 abgelehnt (Schutzvermerk, fremde Inhalte, unsicherer Pfad)
Beispiel:   python tools/rohdaten_aufraeumen.py              # Probelauf
            python tools/rohdaten_aufraeumen.py --ja         # prüfen und löschen
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("rohdaten")
MARKER = "BEHALTEN.txt"
BEKANNT_ORDNER = {"raw", "red"}


def groesse(p: Path) -> int:
    """Summe der Dateigrößen unter p (Bytes); Links werden nicht verfolgt."""
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


def fmt(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def hat_kacheln(ordner: Path, zoom: int | None = None) -> bool:
    """Mindestens eine Kachel (.png/.pbf/.mvt) im Ordner, auf Wunsch in der Zoomstufe zoom."""
    wurzel = ordner / str(zoom) if zoom is not None else ordner
    return wurzel.is_dir() and any(f.suffix in (".png", ".pbf", ".mvt") for f in wurzel.rglob("*") if f.is_file())


def pruefe_relief(web: Path) -> str | None:
    dem = web / "tiles" / "dem"
    for name in ("README.txt", "meta.json"):
        if not (dem / name).is_file():
            return f"Relief unvollständig: {dem / name} fehlt"
    try:
        meta = json.loads((dem / "meta.json").read_text(encoding="utf-8"))
        maxz = int(meta["max_zoom"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        return f"Relief: meta.json unlesbar ({e})"
    if not hat_kacheln(dem, maxz):
        return f"Relief unvollständig: keine Kacheln auf Zoom {maxz} in {dem}"
    return None


def pruefe_klippen(web: Path) -> str | None:
    kl = web / "tiles" / "klippen"
    if not (kl / "meta.json").is_file():
        return f"Felswände nicht fertig: {kl / 'meta.json'} fehlt"
    if not hat_kacheln(kl):
        return f"Felswände nicht fertig: keine Kacheln in {kl}"
    return None


def pruefe_basiskarte(web: Path) -> str | None:
    p = web / "tiles" / "region.pmtiles"
    return None if p.is_file() and p.stat().st_size > 0 else f"Basiskarte fehlt: {p}"


def pruefe_app(url: str, web: Path, timeout: float = 10.0) -> str | None:
    """Seite antwortet mit 200, und die Manifestdatei im Webordner ist gültiges JSON."""
    import httpx
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=False)
    except httpx.HTTPError as e:
        return f"App nicht erreichbar unter {url} ({e.__class__.__name__})"
    if r.status_code != 200:
        return f"App antwortet mit HTTP {r.status_code} unter {url}"
    man = web / "data" / "manifest.json"
    try:
        json.loads(man.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return f"Export fehlt oder ist kaputt: {man} ({e.__class__.__name__})"
    return None


def pruefe_pfad(work: Path) -> str | None:
    """Ablehnen, was nach etwas anderem als einem Arbeitsordner aussieht."""
    w = work.resolve()
    if w in (Path("/"), Path.home().resolve(), ROOT) or w.parent == w or len(w.parts) < 3:
        return f"unsicherer Pfad: {w}"
    if w in ROOT.parents:
        return f"unsicherer Pfad (enthält das Projekt): {w}"
    return None


def pruefe_inhalt(work: Path) -> str | None:
    """Nur bekannte Einträge: raw/, red/, *.meta4, BEHALTEN.txt."""
    for e in sorted(work.iterdir()):
        if e.name == MARKER or (e.is_dir() and not e.is_symlink() and e.name in BEKANNT_ORDNER) or (e.is_file() and e.suffix == ".meta4"):
            continue
        return f"unbekannter Inhalt im Arbeitsordner: {e.name}"
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, default=ROOT / "_scratch" / "dgm1")
    ap.add_argument("--web", type=Path, default=ROOT / "web")
    ap.add_argument("--url", default="http://127.0.0.1:8080/")
    ap.add_argument("--ja", action="store_true", help="wirklich löschen (ohne: Probelauf)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    work = a.work
    if not work.exists():
        log.info("Nichts zu tun: %s existiert nicht.", work)
        return 0
    if (msg := pruefe_pfad(work)):
        log.error("ABGELEHNT: %s", msg)
        return 2
    if not work.is_dir():
        log.error("ABGELEHNT: %s ist kein Ordner", work)
        return 2
    if (work / MARKER).exists():
        log.error("ABGELEHNT: %s liegt im Arbeitsordner. Die Rohdaten sollen bleiben; Datei von Hand entfernen, wenn alles abgenommen ist.", MARKER)
        return 2
    if (msg := pruefe_inhalt(work)):
        log.error("ABGELEHNT: %s", msg)
        return 2

    for name, fn in (("Relief", lambda: pruefe_relief(a.web)), ("Felswände", lambda: pruefe_klippen(a.web)),
                     ("Basiskarte", lambda: pruefe_basiskarte(a.web)), ("App", lambda: pruefe_app(a.url, a.web))):
        if (msg := fn()):
            log.error("NICHT GELÖSCHT: %s", msg)
            return 1
        log.info("Prüfung bestanden: %s", name)

    gesamt = groesse(work)
    for e in sorted(work.iterdir()):
        log.info("  %s  %s", fmt(groesse(e)).rjust(8), e.name)
    if not a.ja:
        log.info("Probelauf: %s würden freigegeben (%s). Zum Löschen --ja angeben.", fmt(gesamt), work)
        return 0
    shutil.rmtree(work)
    log.info("Gelöscht: %s (%s freigegeben).", work, fmt(gesamt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
