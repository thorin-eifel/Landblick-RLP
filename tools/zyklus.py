#!/usr/bin/env python3
"""Ein Durchlauf der Sammelstelle: fällige Quellen abrufen, exportieren, optional hochladen. Läuft auf Windows, Linux und macOS.

Zweck:      Portable Fassung von deploy/run-cycle.sh (die bleibt für Cron/launchd auf Unix). Ein Zeitplaner startet dieses Skript
            im Fünf-Minuten-Takt (siehe install.py).
Parameter:  --erst     Erstlauf: jede Quelle einmal (außer den langsamen, erstlauf: spaeter), danach Export
            --spaet    nur die langsamen Quellen (erstlauf: spaeter, z. B. große OSM-Abfragen), fällig nach Intervall
            --ohne-export   nach dem Abruf nicht exportieren
Umgebung:   Aus .env (app.config lädt sie). LANDBLICK_LIVE=1 (Standard): Quellen mit params.live holt das Livemodul, nicht dieser Lauf.
            PUBLISH_ENABLED=1: danach deploy/publish.sh --delta (braucht bash und lftp; unter Windows meist nicht vorhanden).
Sperre:     Läuft schon ein Durchlauf, endet dieser sofort mit Code 0. Verwaiste Sperren (älter als 30 Minuten) werden verworfen.
Exit:       0 = Export erzeugt, 1 = Export oder Upload fehlgeschlagen (ein Fehler einer Quelle zählt nicht)
Beispiel:   python tools/zyklus.py
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import config  # noqa: E402,F401  (lädt .env)

log = logging.getLogger("zyklus")
STALE_LOCK_S = 30 * 60


def lock_dir(name: str) -> Path:
    return Path(tempfile.gettempdir()) / f"landblick-{name}.lock"


def acquire(lock: Path, now: float | None = None) -> bool:
    """mkdir ist auf allen Systemen atomar. Verwaiste Sperre nach 30 Minuten verwerfen."""
    now = now or time.time()
    try:
        lock.mkdir()
        return True
    except FileExistsError:
        try:
            if now - lock.stat().st_mtime > STALE_LOCK_S:
                log.warning("Verwaiste Sperre entfernt: %s", lock)
                lock.rmdir()
                lock.mkdir()
                return True
        except OSError:
            pass
        return False


def step(args: list[str], timeout: int) -> int:
    cmd = [sys.executable, "-m", *args]
    log.info("→ %s", " ".join(args))
    try:
        return subprocess.run(cmd, cwd=ROOT, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        log.error("Zeitlimit (%d s): %s", timeout, " ".join(args))
        return 124


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--erst", action="store_true")
    ap.add_argument("--spaet", action="store_true")
    ap.add_argument("--ohne-export", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    name = "spaet" if a.spaet else "zyklus"
    lock = lock_dir(name)
    if not acquire(lock):
        log.info("Vorheriger Durchlauf läuft noch, überspringe")
        return 0
    try:
        collect = ["app.collect"]
        if a.spaet:
            collect += ["--due", "--only-later"]
        else:
            collect += ["--once" if a.erst else "--due", "--skip-later"]
            if os.environ.get("LANDBLICK_LIVE", "1") == "1":
                collect.append("--skip-live")
        if step(collect, 3 * 3600 if a.spaet else 40 * 60) != 0:
            log.warning("mindestens eine Quelle ist fehlgeschlagen (steht im Status)")
        if a.ohne_export:
            return 0
        if step(["app.export"], 20 * 60) != 0:
            log.error("Export fehlgeschlagen")
            return 1
        if os.environ.get("PUBLISH_ENABLED") == "1":
            bash = shutil.which("bash")
            if not bash:
                log.warning("Upload ist an, aber bash fehlt: übersprungen")
            elif subprocess.run([bash, str(ROOT / "deploy" / "publish.sh"), "--delta"], cwd=ROOT).returncode != 0:
                log.error("Upload fehlgeschlagen, der nächste Durchlauf versucht es erneut")
                return 1
        log.info("fertig")
        return 0
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
