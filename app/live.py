"""Live-Schleife: Luftverkehr im Sekundentakt, Rest bleibt im Fünf-Minuten-Zyklus.

Zweck:      Holt die Quellen mit `params.live: true` (derzeit adsb.lol) in kurzem Abstand, schreibt danach
            nur `aircraft.json` und `status.json`. „live“ heißt hier: Die Oberfläche holt alle 15 Sekunden die kleine Datei.
Aufruf:     python -m app.live                 Dauerlauf (Zeitplaner, siehe install.py)
            python -m app.live --once          ein Durchlauf, dann Ende (Test)
Parameter:  --interval S   Sekunden zwischen zwei Abrufen (Standard: Intervall aus sources.yaml, mindestens 10)
Höflichkeit: Untergrenze 10 s je Quelle. Fehler lassen den Circuit Breaker der Collector-Basis greifen.
Datenschutz: unverändert wie adsblol.py: keine Kennungen, keine Spuren; Zusatzangaben nur Kurs und Tempo.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
import signal
import sys
import time

import httpx

from .collect import _on_signal, build_collectors
from .config import Settings
from .db import Storage
from .export import build_live, write_all
from .registry import Registry

log = logging.getLogger("landblick.live")
MIN_INTERVAL_S = 10.0


async def run(settings: Settings, interval: float | None, once: bool) -> int:
    registry = Registry.load(settings.sources_path)
    live_ids = [e.id for e in registry.active() if e.params.get("live")]
    if not live_ids:
        log.error("Keine Quelle mit params.live im Register")
        return 1
    storage = Storage(settings.db_path)
    out = settings.web_dir / "data"
    stop = asyncio.Event()
    if not once:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            _on_signal(loop, sig, stop)
    async with httpx.AsyncClient(follow_redirects=False) as client:
        collectors = build_collectors(settings, storage, client, live_ids)
        wait_s = max(MIN_INTERVAL_S, interval or min(c.entry.intervall for c in collectors))
        log.info("Live-Schleife: %s alle %.0f s", ", ".join(live_ids), wait_s)
        while not stop.is_set():
            started = time.monotonic()
            await asyncio.gather(*(c.run_once() for c in collectors))
            try:
                sizes = await asyncio.to_thread(lambda: write_all(build_live(storage, registry), out))
                log.debug("geschrieben: %s", sizes)
            except Exception:  # noqa: BLE001 — ein Schreibfehler darf die Schleife nicht beenden
                log.exception("Export fehlgeschlagen")
            if once:
                break
            pause = max(1.0, wait_s - (time.monotonic() - started)) + random.uniform(0, wait_s * 0.1)
            try:
                await asyncio.wait_for(stop.wait(), timeout=pause)
            except asyncio.TimeoutError:
                pass
    storage.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", type=float, help="Sekunden zwischen zwei Abrufen (mindestens 10)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = ap.parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return asyncio.run(run(Settings.from_env(), args.interval, args.once))


if __name__ == "__main__":
    sys.exit(main())
