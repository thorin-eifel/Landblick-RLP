"""Zeitzonen ohne Zonendatenbank des Systems: Windows hat keine, dort muss das Paket `tzdata` einspringen.

Hintergrund: Mehrere Sammler legen schon beim Import eine feste Zone an (`autobahn`, `lhp_hochwasser`, `lu_pegel`).
Fehlt die Zonendatenbank, scheitert der Import — und weil `build_collectors` alle Module in einer Schleife lädt,
fällt damit der ganze Sammellauf aus, nicht nur diese drei Quellen. Unter Linux und macOS fällt das nie auf,
weil dort `/usr/share/zoneinfo` liegt.

Der Test stellt den Windows-Fall nach: ein Unterprozess mit leerem `PYTHONTZPATH` findet keine Systemzonen und
ist damit allein auf `tzdata` angewiesen.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ohne_systemzonen(code: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONTZPATH": "", "OSINT_NO_DOTENV": "1", "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT)


def test_tzdata_liefert_die_zonen_ohne_system():
    r = ohne_systemzonen(
        "from zoneinfo import ZoneInfo\n"
        "for z in ('Europe/Berlin', 'Europe/Luxembourg'):\n"
        "    ZoneInfo(z)\n"
        "print('ok')\n"
    )
    assert r.returncode == 0, f"Zonen ohne Systemdatenbank nicht auffindbar (tzdata fehlt?):\n{r.stderr}"


def test_jeder_aktive_sammler_importiert_ohne_systemzonen():
    """Wie build_collectors, nur ohne Netz und Datenbank: jedes Modul muss sich laden lassen."""
    r = ohne_systemzonen(
        "from app.collectors import load_collector_class\n"
        "from app.config import Settings\n"
        "from app.registry import Registry\n"
        "for e in Registry.load(Settings.from_env().sources_path).active():\n"
        "    load_collector_class(e.collector)\n"
        "print('ok')\n"
    )
    assert r.returncode == 0, f"Mindestens ein Sammler lässt sich ohne Systemzonen nicht laden:\n{r.stderr}"
