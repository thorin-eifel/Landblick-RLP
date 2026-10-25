#!/usr/bin/env python3
"""Konsistente Sicherung der SQLite-Datenbank (Online-Backup-API, auch bei laufendem Collector).

Zweck:      Tägliche Kopie nach BACKUP_DIR, ältere Sicherungen werden nach --keep aufgeräumt,
            die Kopie wird auf Integrität geprüft (PRAGMA integrity_check).
Parameter:  --db PFAD      Quelle (Standard $LANDBLICK_DB_PATH oder data/landblick.sqlite)
            --dir PFAD     Ziel (Standard $LANDBLICK_BACKUP_DIR oder data/backup)
            --keep N       Anzahl aufzubewahrender Sicherungen (Standard 14)
            --loop SEK     Dauerbetrieb: alle SEK Sekunden wiederholen (Standard: einmalig)
Beispiel:   python tools/backup.py --keep 7
            --verify-after nach der Sicherung gleich den Wiederherstellungstest laufen lassen (Aufruf für Zeitplaner)
            --verify       keine neue Sicherung: die neueste Sicherung in einen Wegwerf-Ordner zurückspielen und prüfen
                           (Integrität, Tabellen- und Zeilenzahlen gegen die Prüfsummendatei, lesbar über Storage)
Beispiel:   python tools/backup.py --keep 7
            python tools/backup.py --verify          # Wiederherstellungstest, z. B. wöchentlich
Prüfsumme:  Zu jeder Sicherung liegt <name>.sqlite.json mit sha256, Größe und Zeilenzahlen je Tabelle.
Exit-Code:  0 = Sicherung ok und geprüft, 1 = Fehler
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import tempfile
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import ro_uri  # noqa: E402

log = logging.getLogger("backup")


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}  # Namen stammen aus sqlite_master


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sidecar(target: Path) -> Path:
    return target.with_name(target.name + ".json")


def backup_once(db: Path, out_dir: Path, keep: int) -> Path:
    if not db.exists():
        raise FileNotFoundError(f"Datenbank nicht gefunden: {db}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = out_dir / f"landblick-{stamp}.sqlite"
    tmp = target.with_suffix(".tmp")
    src = sqlite3.connect(ro_uri(db), uri=True)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
            result = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dst.close()
    finally:
        src.close()
    if result != "ok":
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Integritätsprüfung der Sicherung fehlgeschlagen: {result}")
    ro = sqlite3.connect(ro_uri(tmp), uri=True)
    try:
        counts = table_counts(ro)
    finally:
        ro.close()
    tmp.replace(target)
    sidecar(target).write_text(json.dumps({"sha256": sha256_of(target), "bytes": target.stat().st_size, "tables": counts}, indent=1), encoding="utf-8")
    old = sorted(out_dir.glob("landblick-*.sqlite"))[:-keep] if keep > 0 else []
    for f in old:
        f.unlink()
        sidecar(f).unlink(missing_ok=True)
        log.info("alte Sicherung entfernt: %s", f.name)
    log.info("Sicherung ok: %s (%d Bytes)", target.name, target.stat().st_size)
    return target


def verify_latest(out_dir: Path) -> dict:
    """Spielt die neueste Sicherung in einen Wegwerf-Ordner zurück und prüft sie.

    Prüft: Prüfsumme der Datei, PRAGMA integrity_check der Kopie, Zeilenzahlen je Tabelle gegen die Prüfsummendatei und
    Lesbarkeit über die Anwendungsschicht (Storage, schreibgeschützt). Wirft RuntimeError bei jeder Abweichung."""
    files = sorted(out_dir.glob("landblick-*.sqlite"))
    if not files:
        raise FileNotFoundError(f"Keine Sicherung in {out_dir}")
    latest = files[-1]
    meta_file = sidecar(latest)
    if not meta_file.exists():
        raise RuntimeError(f"Prüfsummendatei fehlt: {meta_file.name}")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if sha256_of(latest) != meta["sha256"]:
        raise RuntimeError(f"Prüfsumme stimmt nicht: {latest.name}")
    with tempfile.TemporaryDirectory(prefix="landblick-restore-") as tmp:
        restored = Path(tmp) / "landblick.sqlite"
        shutil.copy2(latest, restored)
        conn = sqlite3.connect(ro_uri(restored), uri=True)
        try:
            check = conn.execute("PRAGMA integrity_check").fetchone()[0]
            counts = table_counts(conn)
        finally:
            conn.close()
        if check != "ok":
            raise RuntimeError(f"Integritätsprüfung der Wiederherstellung fehlgeschlagen: {check}")
        if counts != meta["tables"]:
            diff = sorted(k for k in set(counts) | set(meta["tables"]) if counts.get(k) != meta["tables"].get(k))
            raise RuntimeError(f"Zeilenzahlen weichen ab in: {', '.join(diff)}")
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app.db import Storage
        st = Storage(restored, readonly=True)
        try:
            st.ping()
            st.data_version()
            aktiv = st.count_active("autobahn")  # beliebige Abfrage über die Anwendungsschicht
        finally:
            st.close()
    log.info("Wiederherstellungstest ok: %s (%d Tabellen, %d Ereignisse)", latest.name, len(counts), counts.get("events", 0))
    return {"file": latest.name, "tables": counts, "active_probe": aktiv}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("LANDBLICK_DB_PATH", "data/landblick.sqlite"))
    ap.add_argument("--dir", default=os.environ.get("LANDBLICK_BACKUP_DIR", "data/backup"))
    ap.add_argument("--keep", type=int, default=14)
    ap.add_argument("--loop", type=int, default=0, metavar="SEK")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--verify-after", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.verify:
        try:
            verify_latest(Path(args.dir))
            return 0
        except Exception as exc:  # noqa: BLE001
            log.error("Wiederherstellungstest fehlgeschlagen: %s", exc)
            return 1
    rc = 0
    while True:
        try:
            backup_once(Path(args.db), Path(args.dir), args.keep)
            if args.verify_after:
                verify_latest(Path(args.dir))
            rc = 0
        except Exception as exc:  # noqa: BLE001
            log.error("Sicherung fehlgeschlagen: %s", exc)
            rc = 1
        if not args.loop:
            return rc
        time.sleep(args.loop)


if __name__ == "__main__":
    sys.exit(main())
