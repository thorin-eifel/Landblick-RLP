#!/usr/bin/env python3
"""Gesundheitsprüfung der Sammelstelle: Zustand je Quelle, je Region und des Exports.

Zweck:      Eine Stelle, die Cron, systemd oder ein Monitoring (Nagios-Stil) abfragen kann. Die Quellen-Zustände
            kommen aus app.payloads.source_status, also aus derselben Regel wie Statusseite und web/js/rules.js
            (down / stale / degraded / ok / pending / disabled). Region = region_tag der aktiven Ereignisse einer Quelle;
            Quellen ohne aktive Ereignisse (Messreihen, ruhige Lage) stehen unter "ohne".
Parameter:  --db PFAD         SQLite (Standard $OSINT_DB_PATH oder data/osint.sqlite)
            --export PFAD     Ordner mit meta.json (Standard <web>/data)
            --json            Ausgabe als JSON statt Text
            --warn-down N     Anzahl ausgefallener Quellen ab Warnung (Standard 1)
            --crit-down-pct P Anteil ausgefallener Quellen in Prozent ab kritisch (Standard 50)
            --export-warn MIN / --export-crit MIN   Alter des Exports (Standard 20 / 60 Minuten)
Beispiel:   python tools/gesundheit.py
            python tools/gesundheit.py --json | jq .overall
Exit-Code:  0 = OK, 1 = Warnung (Quelle veraltet/ausgefallen, Export alt), 2 = kritisch (Datenbank oder Export fehlt,
            Export sehr alt, mindestens die Hälfte der Quellen ausgefallen), 3 = Prüfung selbst fehlgeschlagen
Nur lesend: öffnet die Datenbank schreibgeschützt, schreibt nichts.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR  # noqa: E402
from app.db import Storage  # noqa: E402
from app.models import utcnow  # noqa: E402
from app.payloads import parse_ts, source_status  # noqa: E402
from app.registry import Registry  # noqa: E402

log = logging.getLogger("gesundheit")

RANG = {"ok": 0, "pending": 0, "disabled": 0, "degraded": 1, "stale": 1, "down": 2}
LEVEL = ("OK", "WARNUNG", "KRITISCH")


def worst(statuses: list[str]) -> str:
    """Schlechtester Zustand einer Gruppe (leer = ok)."""
    return max(statuses, key=lambda s: RANG.get(s, 0), default="ok")


def export_age_min(export_dir: Path, now: datetime) -> float | None:
    """Alter des letzten Exports in Minuten aus generated_at in meta.json; None, wenn Datei fehlt oder unlesbar."""
    try:
        meta = json.loads((export_dir / "meta.json").read_text(encoding="utf-8"))
        ts = parse_ts(meta["generated_at"])
    except (OSError, ValueError, KeyError):
        return None
    return None if ts is None else max(0.0, (now - ts).total_seconds() / 60)


def evaluate(storage: Storage, registry: Registry, export_dir: Path | None, now: datetime | None = None,
             warn_down: int = 1, crit_down_pct: float = 50.0, export_warn: float = 20.0, export_crit: float = 60.0) -> dict[str, Any]:
    now = now or utcnow()
    regionen: dict[str, set[str]] = {}
    for r in storage._query("SELECT source_id, region_tag FROM events WHERE active=1 GROUP BY source_id, region_tag"):
        regionen.setdefault(r["source_id"], set()).add(r["region_tag"])
    quellen: list[dict[str, Any]] = []
    for e in registry.entries:
        if e.art != "collector":
            continue
        st = source_status(e, storage.get_state(e.id), storage.count_active(e.id), now)
        quellen.append({"id": e.id, "status": st["status"], "age_s": st["age_s"], "interval_s": st["interval_s"],
                        "consecutive_failures": st["consecutive_failures"], "regions": sorted(regionen.get(e.id, ())) or ["ohne"]})
    aktiv = [q for q in quellen if q["status"] != "disabled"]
    zaehl = {s: sum(1 for q in aktiv if q["status"] == s) for s in ("ok", "pending", "degraded", "stale", "down")}
    gruppen: dict[str, list[dict[str, Any]]] = {}
    for q in aktiv:
        for r in q["regions"]:
            gruppen.setdefault(r, []).append(q)
    regionen_out = {r: {"sources": len(qs), "worst": worst([q["status"] for q in qs]),
                        "problem": sorted(q["id"] for q in qs if RANG[q["status"]] > 0)} for r, qs in sorted(gruppen.items())}
    age = export_age_min(export_dir, now) if export_dir is not None else None
    level, gruende = 0, []
    if zaehl["down"] >= max(1, warn_down):
        level = max(level, 1)
        gruende.append(f"{zaehl['down']} Quelle(n) ausgefallen")
    if zaehl["stale"] + zaehl["degraded"]:
        level = max(level, 1)
        gruende.append(f"{zaehl['stale']} veraltet, {zaehl['degraded']} gestört")
    if aktiv and zaehl["down"] * 100 / len(aktiv) >= crit_down_pct:
        level = 2
        gruende.append(f"mindestens {crit_down_pct:g} % der Quellen ausgefallen")
    if export_dir is not None:
        if age is None:
            level = 2
            gruende.append("Export fehlt oder ist unlesbar")
        elif age >= export_crit:
            level = 2
            gruende.append(f"Export {age:.0f} min alt")
        elif age >= export_warn:
            level = max(level, 1)
            gruende.append(f"Export {age:.0f} min alt")
    return {"overall": LEVEL[level], "exit": level, "reasons": gruende, "checked_at": now.isoformat().replace("+00:00", "Z"),
            "export_age_min": None if age is None else round(age, 1), "counts": zaehl, "regions": regionen_out, "sources": quellen}


def render_text(r: dict[str, Any]) -> str:
    z = r["counts"]
    zeilen = [f"{r['overall']}: " + ("; ".join(r["reasons"]) or "alles im Rahmen"),
              f"Quellen: {z['ok']} ok, {z['degraded']} gestört, {z['stale']} veraltet, {z['down']} ausgefallen, {z['pending']} offen"
              + ("" if r["export_age_min"] is None else f" · Export {r['export_age_min']:.0f} min alt")]
    for tag, g in r["regions"].items():
        zeilen.append(f"  {tag:8} {g['sources']:3} Quellen, schlechtester Zustand {g['worst']}" + (f" ({', '.join(g['problem'])})" if g["problem"] else ""))
    return "\n".join(zeilen)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.environ.get("OSINT_DB_PATH", str(BASE_DIR / "data" / "osint.sqlite")))
    ap.add_argument("--export", default=os.environ.get("OSINT_EXPORT_DIR", str(Path(os.environ.get("OSINT_WEB_DIR", BASE_DIR / "web")) / "data")))
    ap.add_argument("--sources", default=os.environ.get("OSINT_SOURCES", str(BASE_DIR / "sources.yaml")))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--warn-down", type=int, default=1)
    ap.add_argument("--crit-down-pct", type=float, default=50.0)
    ap.add_argument("--export-warn", type=float, default=20.0)
    ap.add_argument("--export-crit", type=float, default=60.0)
    args = ap.parse_args(argv)
    logging.basicConfig(level="WARNING", format="%(levelname)s %(name)s: %(message)s")
    db = Path(args.db)
    if not db.exists():
        print(f"{LEVEL[2]}: Datenbank fehlt ({db})")
        return 2
    try:
        storage = Storage(db, readonly=True)
        try:
            res = evaluate(storage, Registry.load(Path(args.sources)), Path(args.export), None, args.warn_down,
                           args.crit_down_pct, args.export_warn, args.export_crit)
        finally:
            storage.close()
    except Exception as exc:  # noqa: BLE001
        print(f"Prüfung fehlgeschlagen: {exc}")
        return 3
    print(json.dumps(res, ensure_ascii=False, indent=2) if args.json else render_text(res))
    return res["exit"]


if __name__ == "__main__":
    sys.exit(main())
