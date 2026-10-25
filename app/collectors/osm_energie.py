"""Energieanlagen aus OpenStreetMap: Kraftwerke, Solarparks, Umspannwerke, Transformatoren und Hochspannungsleitungen.

Quelle:     Overpass API (https://overpass-api.de/api/interpreter), je Art eine Abfrage je Kachel
Betreiber:  OpenStreetMap-Mitwirkende, Overpass-Instanz von Roland Olbricht (Fair-Use-Richtlinie, keine Schlüssel)
Lizenz:     ODbL 1.0, Namensnennung "© OpenStreetMap-Mitwirkende"
Intervall:  einmal je Woche (604800 s); Anlagen und Trassen ändern sich selten
Auswahl:    plant        power=plant (Kraftwerke aller Energieträger außer Wind; Solarparks als eigene Art "solar")
            substation   power=substation, nur Übertragungsnetz (substation=transmission oder Spannung ab 110 kV)
            transformer  power=transformer ab 110 kV (Maste und Ortsnetzstationen fehlen mit Absicht: Menge, kein Lagebild-Nutzen)
            line         power=line ab 110 kV (110, 220, 380 kV); Mittelspannung, Erdkabel und Bahnstrom fehlen
Ablage:     Cache-Eintrag "energie_osm" (Liste kompakter Objekte), kein Ereignis. Export über energie.json.
Beispiel:   python -m app.collect --once --only osm_energie
            OSM_ENERGIE_ONLY=line python -m app.collect --once --only osm_energie   (nur diese Art neu abfragen, der Rest bleibt vom letzten Stand)

Gespeichert werden Art, Koordinate bzw. vereinfachte Linie, OSM-Kennung und je Art ein Sachwert: Kraftwerk (Energieträger, Leistung in kW),
Solarpark (Leistung, Fläche nur über die Quelle SGD Nord), Umspannwerk und Transformator und Leitung (Spannung in kV).
Namen bleiben nur bei technischen Bezeichnungen (Kraftwerk, Umspannwerk, Talsperre usw.); Betreiber, Kontakt, Freitext und Bearbeiternamen
werden nicht übernommen, Solar- und Biogasanlagen bekommen nie einen Namen (häufig Familien- oder Hofnamen).
Kein Ersatz für die Netzauskunft der Betreiber: Die Angaben stammen von Mitwirkenden, sind unvollständig und nicht amtlich.
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from .. import config, geo
from ..sanitize import clean_text
from .base import Collector, CollectResult, SourceError
from .osm_routen import simplify
from .osm_tiles import tiles

ENDPOINT = "https://overpass-api.de/api/interpreter"
MIRRORS = ("https://z.overpass-api.de/api/interpreter", ENDPOINT, "https://overpass.private.coffee/api/interpreter")
TIMEOUT_S = 120.0
PAUSE_S = 4.0
MAX_ITEMS = 60000
MAX_LINE_POINTS = 400000
LINE_TOL = 0.0004          # Grad, ca. 25 m

HV = r"(^|;)(110|220|380)[0-9]{3}($|;)"      # 110000, 220000, 380000, auch als Liste "380000;110000"
# Art -> Abfrageteile; "nwr" liefert Punkte, Flächen (Mittelpunkt) und Relationen
QUERIES: dict[str, str] = {
    "plant": 'nwr["power"="plant"]["plant:source"!="wind"]{box};out center tags;',
    "substation": f'(nwr["power"="substation"]["substation"="transmission"]{{box}};nwr["power"="substation"]["voltage"~"{HV}"]{{box}};);out center tags;',
    "transformer": f'nwr["power"="transformer"]["voltage"~"{HV}"]{{box}};out center tags;',
    "line": f'way["power"="line"]["voltage"~"{HV}"]{{box}};out geom tags;',
}
KINDS = tuple(QUERIES)
TECH_NAME = re.compile(r"Kraftwerk|Heizkraftwerk|Müllheizkraftwerk|Pumpspeicher|Talsperre|Staustufe|Stausee|Umspannwerk|Schaltanlage|Konverter|\bHKW\b|\bGuD\b|\bUW\b|Wasserkraftwerk|Gaskraftwerk|Kohlekraftwerk|Zentrale", re.I)
SOURCES = {"solar": "solar", "hydro": "hydro", "water": "hydro", "gas": "gas", "coal": "coal", "oil": "oil", "diesel": "oil", "nuclear": "nuclear",
           "biomass": "biomass", "biogas": "biomass", "biofuel": "biomass", "waste": "waste", "geothermal": "geothermal", "wind": "wind", "battery": "battery"}
NO_NAME = {"solar", "biomass"}


def build_query(kind: str, box: tuple[float, float, float, float] | None = None) -> str:
    s, w, n, e = box or config.BBOX
    return "[out:json][timeout:110];" + QUERIES[kind].replace("{box}", f"({s},{w},{n},{e})")   # replace, nicht format: die Regex enthält {3}


def _kw(raw: str) -> int | None:
    """'120 MW', '2500 kW', '1.2 GW', '3000000 W' in Kilowatt; alles andere None. Obergrenze 5 GW (Kraftwerke, anders als Windräder)."""
    m = re.match(r"^\s*(\d{1,9}(?:[.,]\d+)?)\s*(GW|MW|kW|W)?\s*$", raw or "", re.I)
    if not m:
        return None
    unit = (m.group(2) or "W").lower()
    kw = float(m.group(1).replace(",", ".")) * {"gw": 1_000_000, "mw": 1000, "kw": 1, "w": 0.001}[unit]
    return int(round(kw)) if 0 < kw <= 5_000_000 else None


def _kv(raw: str) -> int | None:
    """Höchste Spannung eines OSM-Werts ("380000;110000") in kV; nur Zahlen, sonst None."""
    vals = [int(v) for v in re.findall(r"\d{4,7}", raw or "")]
    return max(vals) // 1000 if vals else None


def _class(kv: int | None) -> int | None:
    return 380 if kv and kv >= 380 else 220 if kv and kv >= 220 else 110 if kv and kv >= 110 else None


def _source(tags: dict[str, str]) -> str:
    raw = (tags.get("plant:source") or tags.get("generator:source") or "").split(";")[0].strip().lower()
    return SOURCES.get(raw, "other")


def parse_elements(data: Any, kind: str) -> list[dict[str, Any]]:
    """Overpass-JSON in kompakte Objekte im Radius. Reine Funktion, damit sie sich mit Fixtures testen lässt."""
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        raise SourceError("Overpass: unerwartete Antwort (kein 'elements')")
    out: dict[str, dict[str, Any]] = {}
    for el in data["elements"]:
        if not isinstance(el, dict):
            continue
        tags = el.get("tags") or {}
        if not isinstance(tags, dict):
            continue
        oid = f"{el.get('type', 'node')}/{el.get('id')}"
        if kind == "line":
            kv = _class(_kv(str(tags.get("voltage") or "")))
            geom = el.get("geometry")
            if not kv or not isinstance(geom, list):
                continue
            pts: list[tuple[float, float]] = []
            for g in geom:
                try:
                    pts.append((float(g["lon"]), float(g["lat"])))
                except (KeyError, TypeError, ValueError):
                    continue
            if len(pts) < 2 or not any(geo.in_region(la, lo) for lo, la in pts):
                continue
            out[oid] = {"id": oid, "kind": "line", "kv": kv, "lines": [[[round(lo, 4), round(la, 4)] for lo, la in simplify(pts, LINE_TOL)]]}
            continue
        c = el.get("center") or el
        try:
            lat, lon = float(c["lat"]), float(c["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not geo.in_region(lat, lon):
            continue
        item: dict[str, Any] = {"id": oid, "kind": kind, "src": "osm", "lat": round(lat, 5), "lon": round(lon, 5)}
        if kind == "plant":
            source = _source(tags)
            if source == "wind":
                continue
            if source == "solar":
                item["kind"] = "solar"
            else:
                item["source"] = source
            kw = _kw(tags.get("plant:output:electricity", ""))
            if kw:
                item["kw"] = kw
            name = clean_text(tags.get("name") or "", 80)
            if name and source not in NO_NAME and TECH_NAME.search(name):
                item["name"] = name
        else:
            kv = _kv(str(tags.get("voltage") or ""))
            if kv:
                item["kv"] = kv
            name = clean_text(tags.get("name") or "", 80)
            if kind == "substation" and name and TECH_NAME.search(name):
                item["name"] = name
        out[oid] = item
    return sorted(out.values(), key=lambda i: (i["kind"], i["id"]))[:MAX_ITEMS]


class OsmEnergieCollector(Collector):
    async def _one(self, kind: str) -> list[dict[str, Any]]:
        """Eine Art über alle Kacheln; fällt eine Kachel aus, fällt die Art aus (kein halber Stand)."""
        found: dict[str, dict[str, Any]] = {}
        for n, box in enumerate(tiles()):
            if n:
                await asyncio.sleep(PAUSE_S)
            for it in await self._one_box(kind, box):
                found[it["id"]] = it
        return list(found.values())

    async def _one_box(self, kind: str, box: tuple[float, float, float, float]) -> list[dict[str, Any]]:
        last: SourceError | None = None
        for url in MIRRORS:
            try:
                resp = await self._request(url, {"data": build_query(kind, box)}, "application/json", False, (), TIMEOUT_S)
                assert resp is not None
                try:
                    data = resp.json()
                except ValueError as exc:
                    raise SourceError("Overpass: keine JSON-Antwort (Instanz überlastet?)") from exc
                if isinstance(data, dict) and data.get("remark") and not data.get("elements"):
                    raise SourceError(f"Overpass: {clean_text(str(data['remark']), 120)}")
                return parse_elements(data, kind)
            except SourceError as exc:
                last = exc
                self.log.warning("%s: %s, nächster Spiegel", url, exc)
        assert last is not None
        raise last

    async def collect(self) -> CollectResult:
        old = (self.storage.cache_get("energie_osm") or {}).get("payload", {}).get("items", [])
        only = {k.strip() for k in os.environ.get("OSM_ENERGIE_ONLY", "").split(",") if k.strip()}
        todo = [k for k in KINDS if not only or k in only]
        keep_kinds = {"solar" if k == "plant" else k for k in KINDS if k not in todo}   # nicht abgefragte Arten behalten den letzten Stand
        items: dict[str, dict[str, Any]] = {}
        failed: list[str] = []
        first_err = ""
        for n, kind in enumerate(todo):
            if n:
                await asyncio.sleep(PAUSE_S)
            try:
                for it in await self._one(kind):
                    items[it["id"]] = it
            except SourceError as exc:
                failed.append(kind)
                first_err = first_err or str(exc)
                self.log.warning("%s: %s", kind, exc)
        if len(failed) == len(todo):
            raise SourceError(f"Overpass: keine Abfrage lieferbar ({first_err})")
        stale = set(failed) | keep_kinds | ({"solar"} if "plant" in failed else set())
        for it in old:            # ausgefallene oder nicht abgefragte Art: letzter Stand bleibt
            if it["kind"] in stale:
                items.setdefault(it["id"], it)
        out = sorted(items.values(), key=lambda i: (i["kind"], i["id"]))[:MAX_ITEMS]
        points = sum(len(line) for i in out for line in i.get("lines", []))
        if points > MAX_LINE_POINTS:
            raise SourceError(f"Leitungen zu groß ({points} Punkte), Abfrage prüfen")
        counts: dict[str, int] = {}
        for i in out:
            counts[i["kind"]] = counts.get(i["kind"], 0) + 1
        self.log.info("%d Energieobjekte, %d Leitungspunkte: %s", len(out), points, counts)
        note = f"teilweise: {', '.join(failed)} fehlgeschlagen, letzter Stand bleibt" if failed else (None if out else "keine Objekte im Radius gefunden")
        return CollectResult(cache={"energie_osm": {"items": out, "counts": counts}}, complete=not failed, note=note, writes_events=False)


COLLECTOR = OsmEnergieCollector
