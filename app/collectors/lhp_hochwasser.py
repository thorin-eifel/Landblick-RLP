"""Pegel und Hochwasserwarnungen der Länder über das Länderübergreifende Hochwasserportal (LHP-PublicAPI).

Quelle:     https://api.hochwasserzentralen.de/public/v1/data/{stations,alerts}  (OpenAPI: hochwasserzentralen.de/developers)
Betreiber:  Länderübergreifendes Hochwasserportal der Hochwasserzentralen (Geschäftsstelle LfU Bayern und LUBW)
Lizenz:     CC BY 4.0. Pflicht: „Datenquelle: www.hochwasserzentralen.de“ und der Stand der Daten („updated“) gut sichtbar.
            Die Daten sind minütlich aktuell; bei Weitergabe mindestens alle 10 Minuten holen.
Intervall:  600 s
Hinweis:    Accept muss application/geo+json sein, sonst liefert der Server eine andere Struktur ("data" statt "features").
Beispiel:   python -m app.collect --once --only lhp_hochwasser

Parameter (sources.yaml): `states` Länderkürzel, die hier abgefragt werden (NW, HE, BW, BY, SL). Rheinland-Pfalz kommt aus
hochwasser_rlp (Messwerte, Verlauf), WSV-Pegel zusätzlich aus PEGELONLINE; ein Pegel an Rhein, Main, Neckar oder Mosel kann
deshalb in zwei Quellen vorkommen (verschiedene Kennungen, gleiche Lage).
Pegel: Die API liefert nur die Hochwasserklasse am Pegel, keine Wasserstände. Klasse 0 (kein Hochwasser) ergibt kein Ereignis.
Warnungen: Flächen (Kreise, Regionen) mit Klasse. Die Beschreibung der Warnungen ist nach dem dokumentierten Beispiel
(OpenAPI 1.0 beta) gebaut; zum Bauzeitpunkt war keine Warnung aktiv, das echte Format wurde nicht gesehen. Der Parser nimmt darum
Felder aus `properties` oder, wie im Beispiel, direkt am Eintrag. „Entwarnung“ (Klasse 1) bleibt ohne Ereignis.
Kein Personenbezug.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ..models import Event, Severity, utcnow
from ..sanitize import clean_text
from .base import Collector, CollectResult, SourceError

BASE = "https://api.hochwasserzentralen.de/public/v1/data"
BERLIN = ZoneInfo("Europe/Berlin")
# lhpClass am Pegel: 1 kleines, 2 mittleres, 3 großes, 4 sehr großes Hochwasser
STATION_SEVERITY: dict[int, Severity] = {1: "notice", 2: "warning", 3: "critical", 4: "critical"}
# lhpClass bei Warnungen: 2 Vorwarnung, 4 Hochwasser, 5 großes, 6 sehr großes Hochwasser (1 = Entwarnung)
ALERT_SEVERITY: dict[int, Severity] = {2: "notice", 4: "warning", 5: "critical", 6: "critical"}
STATE_TAG = {"NW", "HE", "BW", "BY", "SL", "RP", "NI", "TH", "SN", "ST", "BB", "MV", "SH", "BE", "HB", "HH"}


def _local(value: Any) -> datetime | None:
    """„2026-10-12 09:00:00“ (Ortszeit Deutschland) → UTC."""
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=BERLIN).astimezone(timezone.utc)
    except ValueError:
        return None


def _stand(doc: dict[str, Any]) -> str:
    try:
        d = datetime.fromisoformat(str(doc.get("updated"))).astimezone(BERLIN)
        return d.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return "unbekannt"


def _tag(state_id: Any) -> str:
    s = str(state_id or "").upper()
    return s if s.startswith("DE-") and s[3:] in STATE_TAG else "DE"


def _round(c: Any) -> Any:
    return round(float(c), 4) if isinstance(c, (int, float)) else [_round(x) for x in c]


def _https(url: Any) -> str | None:
    u = str(url or "")
    return u if u.startswith("https://") and len(u) < 300 else None


class LhpHochwasserCollector(Collector):
    async def _get(self, what: str, states: str) -> dict[str, Any]:
        # Der Server wählt das Format nach Accept; mit application/json kommt eine andere Struktur ("data" statt "features").
        resp = await self._request(f"{BASE}/{what}", {"format": "geojson", "states": states}, "application/geo+json", False, ())
        try:
            doc = resp.json()
        except ValueError as exc:
            raise SourceError(f"{what}: kein gültiges JSON") from exc
        feats = doc.get("features") if isinstance(doc, dict) else None
        if not isinstance(feats, list) or doc.get("status") not in (None, "success"):
            raise SourceError(f"{what}: Schlüssel 'features' fehlt oder Status nicht success")
        return doc

    async def collect(self) -> CollectResult:
        states = ",".join(self.entry.params.get("states") or ["NW", "HE", "BW", "BY", "SL"])
        now = utcnow()
        st_doc = await self._get("stations", states)
        events: dict[str, Event] = {}
        for f in st_doc["features"]:
            ev = self._station(f, _stand(st_doc), now)
            if ev is not None:
                events[ev.id] = ev
        note = None
        try:
            al_doc = await self._get("alerts", states)
            for f in al_doc["features"]:
                ev = self._alert(f, _stand(al_doc), now)
                if ev is not None:
                    events[ev.id] = ev
        except SourceError as exc:
            self.log.warning("Warnungen nicht erreichbar: %s", exc)
            note = "Warnungen nicht erreichbar, nur Pegel"
        return CollectResult(events=list(events.values()), complete=note is None, note=note)

    def _station(self, f: Any, stand: str, now: datetime) -> Event | None:
        if not isinstance(f, dict) or not isinstance(f.get("geometry"), dict):
            return None
        p = f.get("properties") or {}
        try:
            cls = int(p.get("lhpClass"))
        except (TypeError, ValueError):
            return None
        sev = STATION_SEVERITY.get(cls)
        fid = str(f.get("id") or "")
        if sev is None or not fid:
            return None
        geometry = {"type": "Point", "coordinates": _round(f["geometry"].get("coordinates", [])[:2])}
        if not self.keep(geometry):
            return None
        ts = _local(p.get("timestamp")) or now
        name, water = clean_text(p.get("name"), 80), clean_text(p.get("water"), 80)
        klass = clean_text(p.get("stateClassName"), 60) or f"Hochwasserklasse {cls}"
        return Event(
            id=f"lhp:{fid}", source_id=self.entry.id, type="flood",
            title=clean_text(f"Hochwasser: Pegel {name}" + (f" ({water})" if water else ""), 200),
            summary=clean_text(f"{klass}, Messung {ts.astimezone(BERLIN):%d.%m. %H:%M} Uhr. Datenquelle: www.hochwasserzentralen.de, Stand {stand}.", 400),
            severity=sev, geometry=geometry, region_tag=_tag(p.get("stateId")), valid_from=ts, valid_to=ts + timedelta(hours=3),
            fetched_at=now, raw_ref=_https(p.get("stationLink")) or "https://www.hochwasserzentralen.de/", attrs={"kind": "hochwasser"},
        )

    def _alert(self, f: Any, stand: str, now: datetime) -> Event | None:
        if not isinstance(f, dict) or not isinstance(f.get("geometry"), dict):
            return None
        p = f.get("properties") if isinstance(f.get("properties"), dict) else f
        try:
            cls = int(p.get("lhpClass"))
        except (TypeError, ValueError):
            return None
        sev = ALERT_SEVERITY.get(cls)
        fid = str(f.get("id") or p.get("id") or "")
        g = f["geometry"]
        if sev is None or not fid or g.get("type") not in ("Polygon", "MultiPolygon"):
            return None
        geometry = {"type": g["type"], "coordinates": _round(g.get("coordinates", []))}
        if not self.keep(geometry):
            return None
        area = clean_text(p.get("areaDesc"), 120)
        head = clean_text(p.get("alertHeadline"), 160) or "Hochwasserwarnung"
        klass = clean_text(p.get("lhpClassName"), 60)
        state = fid.split("_", 1)[0].upper()
        return Event(
            id=f"lhpwarn:{fid}", source_id=self.entry.id, type="flood",
            title=clean_text(f"{head}: {area}" if area else head, 240),
            summary=clean_text(f"{klass}. Warnung des Landes laut LHP. Datenquelle: www.hochwasserzentralen.de, Stand {stand}.", 400),
            severity=sev, geometry=geometry, region_tag=_tag(f"DE-{state}"), valid_from=now, fetched_at=now,
            raw_ref=_https(p.get("alertLink")) or "https://www.hochwasserzentralen.de/warnungen", attrs={"kind": "hochwasserwarnung"},
        )


COLLECTOR = LhpHochwasserCollector
