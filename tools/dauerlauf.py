#!/usr/bin/env python3
"""Dauerlauf-Protokoll: Gesundheit regelmäßig abtasten, am Ende ein Bericht.

Zweck:      R6 verlangt sieben Tage ohne Handeingriff. Dieses Werkzeug misst das, statt es zu behaupten: es ruft
            tools/gesundheit.py auf, hängt jede Probe als Zeile an eine JSONL-Datei und schreibt auf Wunsch einen Markdown-Bericht
            (Laufzeit, Anteil Proben je Zustand, Lücken zwischen den Proben, längste Störung je Quelle, Handeingriffe).
Parameter:  sample           eine Probe nehmen und anhängen (für Cron/launchd, z. B. alle 10 Minuten)
            report           Bericht aus der JSONL-Datei erzeugen
            note TEXT        Handeingriff oder Besonderheit vermerken (z. B. "Neustart Mac", "Quelle X Schlüssel erneuert")
            --file PFAD      JSONL-Datei (Standard data/dauerlauf.jsonl)
            --db / --export  an gesundheit.py durchgereicht
            --luecke MIN     ab dieser Pause zwischen zwei Proben gilt der Lauf als unterbrochen (Standard 30)
            --out PFAD       Bericht schreiben statt auf die Konsole
Beispiel:   python tools/dauerlauf.py sample
            python tools/dauerlauf.py note "Mac nach Update neu gestartet"
            python tools/dauerlauf.py report --out docs/rlp/r6-bericht.md
Bestanden:  Der Bericht nennt drei Kriterien: mindestens 7 Tage Laufzeit, keine Lücke über --luecke, keine Handeingriffe.
            Er entscheidet nichts; ob R6 damit fertig ist, entscheidet der Mensch.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gesundheit  # noqa: E402
from app.config import BASE_DIR  # noqa: E402
from app.db import Storage  # noqa: E402
from app.registry import Registry  # noqa: E402

ZIEL_TAGE = 7


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def stamp(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def take_sample(db: Path, export: Path, sources: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or now_utc()
    if not db.exists():
        return {"t": stamp(now), "overall": "KRITISCH", "exit": 2, "reasons": ["Datenbank fehlt"], "counts": {}, "problem": {}, "export_age_min": None}
    st = Storage(db, readonly=True)
    try:
        r = gesundheit.evaluate(st, Registry.load(sources), export, now)
    finally:
        st.close()
    return {"t": stamp(now), "overall": r["overall"], "exit": r["exit"], "reasons": r["reasons"], "counts": r["counts"],
            "export_age_min": r["export_age_min"],
            "problem": {q["id"]: q["status"] for q in r["sources"] if gesundheit.RANG[q["status"]] > 0}}


def append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load(path: Path) -> list[dict[str, Any]]:
    rows = []
    for z in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(z))
        except ValueError:
            continue     # halbe Zeile nach Stromausfall: ignorieren, nicht abbrechen
    return rows


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def analyse(rows: list[dict[str, Any]], luecke_min: float = 30) -> dict[str, Any]:
    proben = sorted((r for r in rows if "overall" in r), key=lambda r: r["t"])
    notizen = [r for r in rows if "note" in r]
    if not proben:
        return {"proben": 0, "notizen": notizen}
    t0, t1 = _t(proben[0]["t"]), _t(proben[-1]["t"])
    luecken = []
    for a, b in zip(proben, proben[1:]):
        d = (_t(b["t"]) - _t(a["t"])).total_seconds() / 60
        if d > luecke_min:
            luecken.append({"von": a["t"], "bis": b["t"], "minuten": round(d)})
    anteile = {k: sum(1 for p in proben if p["overall"] == k) for k in ("OK", "WARNUNG", "KRITISCH")}
    # längste zusammenhängende Störung je Quelle (Zeit zwischen erster und letzter Probe in Folge mit Problemstatus)
    laengste: dict[str, dict[str, Any]] = {}
    lauf: dict[str, str] = {}
    letzte_t = None
    for p in proben:
        for sid in list(lauf):
            if sid not in p["problem"]:
                del lauf[sid]
        for sid, status in p["problem"].items():
            lauf.setdefault(sid, p["t"])
            dauer = (_t(p["t"]) - _t(lauf[sid])).total_seconds() / 60
            if dauer >= laengste.get(sid, {}).get("minuten", -1):
                laengste[sid] = {"minuten": round(dauer), "seit": lauf[sid], "status": status}
        letzte_t = p["t"]
    laufzeit = t1 - t0
    kriterien = {
        "laufzeit": laufzeit >= timedelta(days=ZIEL_TAGE),
        "ohne_luecke": not luecken,
        "ohne_handeingriff": not notizen,
    }
    return {"proben": len(proben), "von": proben[0]["t"], "bis": proben[-1]["t"], "laufzeit_h": round(laufzeit.total_seconds() / 3600, 1),
            "anteile": anteile, "luecken": luecken, "laengste_stoerung": dict(sorted(laengste.items(), key=lambda kv: -kv[1]["minuten"])),
            "notizen": notizen, "kriterien": kriterien}


def render(a: dict[str, Any], luecke_min: float) -> str:
    if not a["proben"]:
        return "# Dauerlauf-Bericht\n\nKeine Proben vorhanden.\n"
    k = a["kriterien"]
    jn = lambda b: "erfüllt" if b else "nicht erfüllt"  # noqa: E731
    z = [f"# Dauerlauf-Bericht", "",
         f"Zeitraum: {a['von']} bis {a['bis']} ({a['laufzeit_h']} h, {a['proben']} Proben, UTC).", "",
         "## Kriterien R6", "",
         f"- Mindestens {ZIEL_TAGE} Tage Laufzeit: {jn(k['laufzeit'])}",
         f"- Keine Pause über {luecke_min:g} Minuten zwischen zwei Proben: {jn(k['ohne_luecke'])}",
         f"- Keine Handeingriffe vermerkt: {jn(k['ohne_handeingriff'])}", "",
         "## Zustand über die Proben", ""]
    n = a["proben"]
    for key in ("OK", "WARNUNG", "KRITISCH"):
        z.append(f"- {key}: {a['anteile'][key]} ({a['anteile'][key] * 100 / n:.1f} %)")
    z += ["", "## Pausen", ""]
    z += [f"- {l['von']} bis {l['bis']}: {l['minuten']} min" for l in a["luecken"]] or ["Keine."]
    z += ["", "## Längste Störung je Quelle", ""]
    z += [f"- {sid}: {v['minuten']} min seit {v['seit']} ({v['status']})" for sid, v in list(a["laengste_stoerung"].items())[:15]] or ["Keine."]
    z += ["", "## Handeingriffe und Vermerke", ""]
    z += [f"- {x['t']}: {x['note']}" for x in a["notizen"]] or ["Keine."]
    z += ["", "Der Bericht misst, er entscheidet nicht. Ob R6 damit fertig ist, entscheidet der Mensch."]
    return "\n".join(z) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["sample", "report", "note"])
    ap.add_argument("text", nargs="?", default="")
    ap.add_argument("--file", default=os.environ.get("LANDBLICK_DAUERLAUF_FILE", str(BASE_DIR / "data" / "dauerlauf.jsonl")))
    ap.add_argument("--db", default=os.environ.get("LANDBLICK_DB_PATH", str(BASE_DIR / "data" / "landblick.sqlite")))
    ap.add_argument("--export", default=os.environ.get("LANDBLICK_EXPORT_DIR", str(Path(os.environ.get("LANDBLICK_WEB_DIR", BASE_DIR / "web")) / "data")))
    ap.add_argument("--sources", default=os.environ.get("LANDBLICK_SOURCES", str(BASE_DIR / "sources.yaml")))
    ap.add_argument("--luecke", type=float, default=30)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    f = Path(args.file)
    if args.cmd == "sample":
        row = take_sample(Path(args.db), Path(args.export), Path(args.sources))
        append(f, row)
        print(f"{row['t']} {row['overall']}")
        return 0
    if args.cmd == "note":
        if not args.text:
            print("note braucht einen Text", file=sys.stderr)
            return 1
        append(f, {"t": stamp(now_utc()), "note": args.text})
        return 0
    if not f.exists():
        print(f"Keine Datei: {f}", file=sys.stderr)
        return 1
    text = render(analyse(load(f), args.luecke), args.luecke)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
