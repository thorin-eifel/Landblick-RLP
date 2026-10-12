"""Verkehrsmeldungen Baden-Württemberg (Landesmeldestelle LMS BW über MobiData BW, DATEX II).

Quelle:     https://api.mobidata-bw.de/datasets/traffic/incidents/incidents_lmsbw.datex2.xml  (DATEX II 2.0, ca. 1,7 MB)
Betreiber:  Landesmeldestelle Baden-Württemberg (Ministerium des Inneren, für Digitalisierung und Kommunen), über MobiData BW
Lizenz:     Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2.0), laut Datensatzbeschreibung auf mobidata-bw.de
Intervall:  300 s
Beispiel:   python -m app.collect --once --only mobidata_bw_meldungen

Übernommen werden Unfälle, Verkehrsstörungen (Stau), Hindernisse, Schäden an der Infrastruktur, Sperrungen und Betriebsmeldungen.
Weggelassen:
  * Baustellen (MaintenanceWorks, ConstructionWorks und Sperrungen, deren Text „Baustelle“ nennt): die kommen aus
    mobidata_bw_baustellen, sonst stünden sie doppelt in der Karte.
  * Meldungen mit Autobahnnummer am Textanfang: die deckt der Autobahn-Collector ab.
Geometrie: die Linie von/bis (TPEG) bzw. der Anzeigepunkt. Texte sind Orts- und Straßenangaben der Leitstellen ohne Personen;
Telefonnummern und E-Mail-Adressen werden entfernt. Kein Abruf von Bildern.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from ..models import Event, EventType, Severity, utcnow
from ..sanitize import clean_text
from .base import Collector, CollectResult, SourceError

D2 = "{http://datex2.eu/schema/2/2_0}"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"
_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|(?:\+|00)?\d[\d\s/()-]{7,}\d")
_AUTOBAHN = re.compile(r"^\s*A\s?\d{1,3}\b")
_BAUSTELLE = re.compile(r"baustelle|bauarbeiten|arbeitsstelle", re.I)

# DATEX-Typ → (kind, Bezeichnung, Typ, Grundstufe); None = weglassen
KINDS: dict[str, tuple[str, str, EventType, Severity] | None] = {
    "Accident": ("unfall", "Unfall", "traffic", "warning"),
    "AbnormalTraffic": ("stau", "Verkehrsstörung", "congestion", "notice"),
    "GeneralObstruction": ("warnung", "Hindernis", "traffic", "notice"),
    "VehicleObstruction": ("warnung", "Fahrzeug auf der Fahrbahn", "traffic", "notice"),
    "InfrastructureDamageObstruction": ("warnung", "Schaden an der Straße", "traffic", "notice"),
    "AuthorityOperation": ("warnung", "Einsatz", "traffic", "notice"),
    "RoadOrCarriagewayOrLaneManagement": ("sperrung", "Sperrung", "traffic", "warning"),
    "GeneralNetworkManagement": ("warnung", "Verkehrsregelung", "traffic", "info"),
    "NonWeatherRelatedRoadConditions": ("warnung", "Straßenzustand", "traffic", "notice"),
    "GeneralInstructionOrMessageToRoadUsers": ("warnung", "Hinweis", "traffic", "info"),
    "MaintenanceWorks": None, "ConstructionWorks": None, "ReroutingManagement": None,
}


def _dt(text: str | None) -> datetime | None:
    try:
        d = datetime.fromisoformat((text or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _pt(el: ET.Element | None) -> list[float] | None:
    if el is None:
        return None
    try:
        return [round(float(el.findtext(f"{D2}longitude")), 5), round(float(el.findtext(f"{D2}latitude")), 5)]
    except (TypeError, ValueError):
        return None


def _geometry(rec: ET.Element) -> dict[str, Any] | None:
    loc = rec.find(f"{D2}groupOfLocations")
    if loc is None:
        return None
    a = _pt(loc.find(f"{D2}tpegLinearLocation/{D2}from/{D2}pointCoordinates"))
    b = _pt(loc.find(f"{D2}tpegLinearLocation/{D2}to/{D2}pointCoordinates"))
    if a and b and a != b:
        return {"type": "LineString", "coordinates": [a, b]}
    p = _pt(loc.find(f"{D2}locationForDisplay")) or a or b
    return {"type": "Point", "coordinates": p} if p else None


def _comment(rec: ET.Element, kind: str) -> str:
    for c in rec.findall(f"{D2}generalPublicComment"):
        if c.findtext(f"{D2}commentType") == kind:
            v = c.find(f"{D2}comment/{D2}values/{D2}value")
            if v is not None and v.text:
                return v.text
    return ""


def parse_situations(data: bytes, source_id: str, keep, now: datetime) -> tuple[list[Event], dict[str, int]]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise SourceError(f"XML nicht lesbar: {exc}") from exc
    sits = root.findall(f".//{D2}situation")
    if not sits and root.find(f".//{D2}payloadPublication") is None:
        raise SourceError("kein payloadPublication (Schema geändert?)")
    stats = {"gesehen": len(sits), "ereignisse": 0, "baustelle": 0, "autobahn": 0, "ausserhalb": 0, "unbekannt": 0}
    events: dict[str, Event] = {}
    for s in sits:
        rec = s.find(f"{D2}situationRecord")
        if rec is None:
            continue
        typ = (rec.get(XSI) or "").split(":")[-1]
        if typ not in KINDS:
            stats["unbekannt"] += 1
            continue
        spec = KINDS[typ]
        desc = _CONTACT.sub("", _comment(rec, "description"))
        if spec is None or (typ == "RoadOrCarriagewayOrLaneManagement" and _BAUSTELLE.search(desc)):
            stats["baustelle"] += 1
            continue
        if _AUTOBAHN.match(desc):
            stats["autobahn"] += 1
            continue
        geometry = _geometry(rec)
        if geometry is None or not keep(geometry):
            stats["ausserhalb"] += 1
            continue
        kind, label, etype, sev = spec
        if kind == "stau" and rec.findtext(f"{D2}impact/{D2}trafficConstrictionType") in ("roadBlocked", "carriagewayBlocked"):
            sev = "warning"
        where = clean_text(_comment(rec, "locationDescriptor"), 160)
        one_line = clean_text(desc, 400)
        sid = s.get("id") or ""
        ev = Event(
            id="lmsbw:" + hashlib.sha1(sid.encode()).hexdigest()[:16], source_id=source_id, type=etype,
            title=clean_text(f"{label}: {where}" if where else label, 200), summary=clean_text(f"{one_line} Quelle: Landesmeldestelle BW.", 700),
            severity=sev, attrs={"kind": kind, **({"sperr": "voll"} if kind == "sperrung" else {})}, geometry=geometry, region_tag="DE-BW",
            valid_from=_dt(rec.findtext(f"{D2}validity/{D2}validityTimeSpecification/{D2}overallStartTime")),
            valid_to=_dt(rec.findtext(f"{D2}validity/{D2}validityTimeSpecification/{D2}overallEndTime")),
            fetched_at=now, raw_ref="https://www.mobidata-bw.de/dataset/meldung",
        )
        events[ev.id] = ev
    stats["ereignisse"] = len(events)
    return list(events.values()), stats


class MobidataBwMeldungenCollector(Collector):
    async def collect(self) -> CollectResult:
        data = await self.fetch_bytes(self.entry.url, timeout=60.0)
        events, stats = parse_situations(data, self.entry.id, self.keep, utcnow())
        self.log.info("Meldungen BW: %s", stats)
        return CollectResult(events=events, complete=True, note=None)


COLLECTOR = MobidataBwMeldungenCollector
