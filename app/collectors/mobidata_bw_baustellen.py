"""Baustellen und Sperrungen Baden-Württemberg (MobiData BW, Baustelleninformationen, GeoJSON).

Quelle:     https://api.mobidata-bw.de/datasets/traffic/roadworks/roadworks_geojson.json  (GeoJSON, CIFS-Felder)
Betreiber:  Land Baden-Württemberg, Baustellen- und Ereignismanagementsystem BEMaS; Daten bereitgestellt über MobiData BW
Lizenz:     Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2.0), laut Datensatzbeschreibung auf mobidata-bw.de
Intervall:  600 s (Datensatz wird laufend aktualisiert, ca. 1 MB)
Beispiel:   python -m app.collect --once --only mobidata_bw_baustellen

Inhalt: geplante und laufende Arbeiten auf Bundes-, Landes- und Kreisstraßen in BW (Autobahnen kommen über den Autobahn-
Collector; Einträge mit Autobahnnummer werden verworfen, sonst stünden sie doppelt in der Karte). Typ ROAD_CLOSED
(Vollsperrung bzw. Sperrung einer Richtung) wird zur Sperrung, CONSTRUCTION zur Baustelle. Verlauf als Linie.
Die Datei umfasst ganz BW; der Radiusfilter passiert am Rand. Die Beschreibungen sind Straßen- und Ortsangaben ohne
Personenbezug; E-Mail-Adressen und Telefonnummern werden trotzdem entfernt.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from ..models import Event, Severity, utcnow
from ..sanitize import clean_text
from .base import Collector, CollectResult, SourceError

_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|(?:\+|00)?\d[\d\s/()-]{7,}\d")
_AUTOBAHN = re.compile(r"^A\s?\d{1,3}\b")


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _round(c: Any) -> Any:
    return round(float(c), 5) if isinstance(c, (int, float)) else [_round(x) for x in c]


class MobidataBwBaustellenCollector(Collector):
    async def collect(self) -> CollectResult:
        doc = await self.fetch_json(self.entry.url)
        feats = doc.get("features") if isinstance(doc, dict) else None
        if not isinstance(feats, list):
            raise SourceError("Schlüssel 'features' fehlt (Schema geändert?)")
        now = utcnow()
        events: dict[str, Event] = {}
        for f in feats:
            ev = self._normalize(f, now)
            if ev is not None:
                events[ev.id] = ev
        if feats and not events and len(feats) > 50:
            self.log.info("%d Einträge, keiner in der Region", len(feats))
        return CollectResult(events=list(events.values()), complete=True)

    def _normalize(self, f: Any, now: datetime) -> Event | None:
        if not isinstance(f, dict) or not isinstance(f.get("properties"), dict) or not isinstance(f.get("geometry"), dict):
            return None
        p, g = f["properties"], f["geometry"]
        fid = str(p.get("id") or "")
        if not fid or g.get("type") not in ("Point", "LineString", "MultiLineString"):
            return None
        street = str(p.get("street") or "").strip()
        if _AUTOBAHN.match(street):
            return None
        geometry = {"type": g["type"], "coordinates": _round(g.get("coordinates"))}
        if not self.keep(geometry):
            return None
        closed = str(p.get("type") or "").upper() == "ROAD_CLOSED"
        both = str(p.get("direction") or "").upper() == "BOTH_DIRECTIONS"
        severity: Severity = "warning" if closed else "notice"
        what = "Sperrung" if closed else "Baustelle"
        desc = clean_text(_CONTACT.sub("", str(p.get("description") or "")), 300)
        title = clean_text(f"{street or 'Straße'}: {what}" + (f", {desc}" if desc and desc.lower() not in street.lower() else ""), 200)
        attrs: dict[str, Any] = {"kind": "sperrung" if closed else "baustelle"}
        if closed:
            attrs["sperr"] = "voll" if both else "richtung"
        return Event(
            id="bwbau:" + hashlib.sha1(fid.encode()).hexdigest()[:16], source_id=self.entry.id, type="traffic",
            title=title, summary=clean_text(f"{what} auf {street or 'einer Straße'}" + (" in beiden Richtungen" if both else " in einer Richtung") + ". Quelle: MobiData BW.", 300),
            severity=severity, attrs=attrs, geometry=geometry, region_tag="DE-BW",
            valid_from=_dt(p.get("starttime")), valid_to=_dt(p.get("endtime")), fetched_at=now, raw_ref="https://www.mobidata-bw.de/dataset/baustelleninformationen-baden-wurttemberg",
        )


COLLECTOR = MobidataBwBaustellenCollector
