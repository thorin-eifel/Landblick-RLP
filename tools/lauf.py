#!/usr/bin/env python3
"""Startet einen Befehl und schreibt seine Ausgabe mit Zeitstempel in eine rotierende Logdatei.

Zweck:      Zeitplaner (Windows-Aufgabenplanung, systemd, launchd, Cron) sollen ohne Shell-Umleitung auskommen. Dieses Skript
            ersetzt `>> datei.log 2>&1`, rotiert die Datei (damit sie nicht ohne Ende wächst) und läuft unter Windows ohne
            Konsolenfenster. Der Rückgabecode ist der des Befehls.
Aufruf:     python tools/lauf.py --log data/logs/zyklus.log [--max-mb 2] [--keep 5] [--timeout SEK] -- python tools/zyklus.py
Hinweis:    "python" als erstes Wort heißt: der Interpreter, der dieses Skript startet (unter Windows python.exe neben pythonw.exe).
            Die Kindprozesse laufen mit PYTHONUTF8=1, damit Umlaute auch unter Windows ohne Codepage-Fehler im Log landen.
Beispiel:   python tools/lauf.py --log /tmp/t.log -- python -c "print('Grüße')"
"""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import subprocess
import sys
import time
from pathlib import Path


def interpreter() -> str:
    """python.exe statt pythonw.exe (pythonw hat keine Standardausgabe)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        cand = exe.with_name("python.exe")
        if cand.exists():
            return str(cand)
    return str(exe)


def build_logger(path: Path, max_mb: float, keep: int) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger(f"lauf.{path}")
    lg.setLevel(logging.INFO)
    lg.propagate = False
    if not lg.handlers:
        h = logging.handlers.RotatingFileHandler(path, maxBytes=int(max_mb * 1024 * 1024), backupCount=keep, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        lg.addHandler(h)
    return lg


def run(cmd: list[str], log_path: Path, max_mb: float = 2, keep: int = 5, timeout: float | None = None) -> int:
    lg = build_logger(log_path, max_mb, keep)
    if cmd and cmd[0] == "python":
        cmd = [interpreter(), *cmd[1:]]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    started = time.monotonic()
    lg.info("[start] %s", " ".join(cmd))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, creationflags=flags)
    except OSError as exc:
        lg.error("[ende] Start fehlgeschlagen: %s", exc)
        return 127
    deadline = None if timeout is None else started + timeout
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            lg.info("%s", raw.decode("utf-8", errors="replace").rstrip())
            if deadline and time.monotonic() > deadline:
                proc.kill()
                lg.error("[ende] Zeitlimit von %.0f s überschritten, beendet", timeout)
                proc.wait()
                return 124
        rc = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        rc = proc.wait()
    lg.info("[ende] Code %d nach %.1f s", rc, time.monotonic() - started)
    return rc


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--" not in argv:
        print("Aufruf: lauf.py --log DATEI -- BEFEHL …", file=sys.stderr)
        return 2
    i = argv.index("--")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--max-mb", type=float, default=2)
    ap.add_argument("--keep", type=int, default=5)
    ap.add_argument("--timeout", type=float)
    a = ap.parse_args(argv[:i])
    if not argv[i + 1:]:
        print("Kein Befehl nach --", file=sys.stderr)
        return 2
    return run(argv[i + 1:], a.log, a.max_mb, a.keep, a.timeout)


if __name__ == "__main__":
    sys.exit(main())
