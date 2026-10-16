"""Windenergieanlagen und Freiflächen-Photovoltaik aus dem Raumordnungskataster der SGD Nord (Land Rheinland-Pfalz).

Quelle:     Geoportal RLP, OGC API Features "oeffentliche Energiethemen SGD Nord"
            https://www.geoportal.rlp.de/spatial-objects/539/collections/{ms:windenergieanlagen_an,ms:fotovoltaikanlagen_an}/items?f=json
Betreiber:  Struktur- und Genehmigungsdirektion Nord (Obere Landesplanungsbehörde), Raumordnungskataster ROK25 Online
Lizenz:     Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2.0), Quellenvermerk "Quelle: Raumordnungskataster ROK25 Online SGD Nord Koblenz"
Intervall:  einmal je Tag (86400 s); das Kataster ändert sich mit Genehmigungen, nicht stündlich
Gebiet:     Verwaltungsbereich der SGD Nord (Norden von Rheinland-Pfalz). Der Süden (SGD Süd) bietet keinen vergleichbaren offenen Dienst;
            dort füllt OpenStreetMap (osm_energie, osm_infra) auf.
Ablage:     Cache-Eintrag "energie_rok" (Listen "wind" und "solar"), kein Ereignis. Export über energie.json und infrastruktur.json.
Beispiel:   python -m app.collect --once --only sgdnord_energie

Gespeichert werden nur technische Sachwerte: Wind (Koordinate, Nennleistung kW, Nabenhöhe, Gesamthöhe, Stand des Verfahrens, Gemeinde),
Solar (Schwerpunkt, vereinfachter Außenring, Nennleistung kW, Fläche, Stand). Betreiber, Typbezeichnung, Aktenlinks und Daten der Anträge
bleiben weg (Betreiber können Privatpersonen sein; das Lagebild zeigt Anlagen, keine Eigentümer).
Stände "aufgegeben", "abgelehnt", "rueckgebaut" und "stillgelegt" erscheinen nicht auf der Karte; sie gibt es nicht (mehr).
"""
from __future__ import annotations

import math
from typing import Any

from .. import geo
from ..sanitize import clean_text
from .base import Collector, CollectResult, SourceError
from .osm_routen import simplify

BASE = "https://www.geoportal.rlp.de/spatial-objects/539/collections"
WIND = "ms:windenergieanlagen_an"
SOLAR = "ms:fotovoltaikanlagen_an"
PAGE = 4000                 # größte erlaubte Seitengröße der Schnittstelle (1, 5, 10 … 4000)
MAX_PAGES = 6
KEEP_STATES = {"am Netz": "netz", "genehmigt": "genehmigt", "beantragt": "beantragt"}
RING_TOL = 0.0002           # Grad, ca. 15 bis 20 m


def _num(v: Any, lo: float, hi: float) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and lo < x <= hi else None


def parse_wind(data: Any) -> list[dict[str, Any]]:
    """GeoJSON der Windenergieanlagen in kompakte Punkte im Radius. Reine Funktion für Fixtures."""
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise SourceError("SGD Nord Wind: unerwartete Antwort (kein 'features')")
    out: dict[str, dict[str, Any]] = {}
    for f in data["features"]:
        if not isinstance(f, dict):
            continue
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        status = KEEP_STATES.get(str(p.get("planstd") or ""))
        if not status or g.get("type") != "Point":
            continue
        try:
            lon, lat = float(g["coordinates"][0]), float(g["coordinates"][1])
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if not geo.in_region(lat, lon):
            continue
        gid = p.get("gid")
        if gid is None:
            continue
        item: dict[str, Any] = {"id": f"rok/wind/{gid}", "kind": "wind", "src": "rok", "lat": round(lat, 5), "lon": round(lon, 5), "state": status}
        kw = _num(p.get("nennleist"), 0, 30000)
        if kw:
            item["kw"] = int(round(kw))
        hub, top = _num(p.get("nabenhoehe"), 0, 400), _num(p.get("gesamthoeh"), 0, 500)
        if hub:
            item["hub"] = int(round(hub))
        if top:
            item["top"] = int(round(top))
        place = clean_text(str(p.get("gemeinde") or ""), 60)
        if place:
            item["place"] = place
        out[item["id"]] = item
    return sorted(out.values(), key=lambda i: i["id"])


def _ring(geom: dict[str, Any]) -> list[list[float]] | None:
    """Größter Außenring eines (Multi-)Polygons, vereinfacht und gerundet."""
    t, c = geom.get("type"), geom.get("coordinates")
    rings: list[Any] = []
    if t == "Polygon" and isinstance(c, list) and c:
        rings = [c[0]]
    elif t == "MultiPolygon" and isinstance(c, list):
        rings = [poly[0] for poly in c if isinstance(poly, list) and poly]
    best: list[tuple[float, float]] = []
    for r in rings:
        try:
            pts = [(float(a[0]), float(a[1])) for a in r]
        except (TypeError, ValueError, IndexError):
            continue
        if len(pts) >= 4 and len(pts) > len(best):
            best = pts
    if not best:
        return None
    s = simplify(best[:-1], RING_TOL)
    if len(s) < 3:
        return None
    s.append(s[0])
    return [[round(a, 5), round(b, 5)] for a, b in s]


def _centroid(ring: list[list[float]]) -> tuple[float, float]:
    """Mittelpunkt der Randpunkte (für die Zeichen und die Zellenzuordnung genügt das)."""
    pts = ring[:-1]
    return sum(p[1] for p in pts) / len(pts), sum(p[0] for p in pts) / len(pts)


def parse_solar(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise SourceError("SGD Nord Photovoltaik: unerwartete Antwort (kein 'features')")
    out: dict[str, dict[str, Any]] = {}
    for f in data["features"]:
        if not isinstance(f, dict):
            continue
        p = f.get("properties") or {}
        status = KEEP_STATES.get(str(p.get("planstd") or ""))
        ring = _ring(f.get("geometry") or {}) if status else None
        if not status or not ring or p.get("id") is None:
            continue
        lat, lon = _centroid(ring)
        if not geo.in_region(lat, lon):
            continue
        item: dict[str, Any] = {"id": f"rok/solar/{p['id']}", "kind": "solar", "src": "rok", "lat": round(lat, 5), "lon": round(lon, 5), "state": status, "ring": ring}
        kw = _num(p.get("nennleistg"), 0, 2_000_000)
        if kw:
            item["kw"] = int(round(kw))
        area = _num(p.get("standortfl"), 0, 50_000_000)
        if area:
            item["ha"] = round(area / 10000, 1)
        place = clean_text(str(p.get("gdename") or ""), 60)
        if place:
            item["place"] = place
        out[item["id"]] = item
    return sorted(out.values(), key=lambda i: i["id"])


class SgdNordEnergieCollector(Collector):
    async def _all(self, name: str) -> dict[str, Any]:
        """Alle Seiten einer Sammlung; die Schnittstelle erlaubt höchstens 4000 je Seite."""
        feats: list[Any] = []
        total = None
        for page in range(MAX_PAGES):
            data = await self.fetch_json(f"{BASE}/{name}/items", {"f": "json", "limit": PAGE, "offset": page * PAGE})
            if not isinstance(data, dict) or not isinstance(data.get("features"), list):
                raise SourceError(f"{name}: unerwartete Antwort (kein 'features')")
            feats.extend(data["features"])
            total = data.get("numberMatched", total)
            if not data["features"] or (isinstance(total, int) and len(feats) >= total):
                break
        return {"features": feats}

    async def collect(self) -> CollectResult:
        old = (self.storage.cache_get("energie_rok") or {}).get("payload", {})
        wind, solar, failed = old.get("wind", []), old.get("solar", []), []
        first = ""
        try:
            wind = parse_wind(await self._all(WIND))
        except SourceError as exc:
            failed.append("Wind")
            first = str(exc)
        try:
            solar = parse_solar(await self._all(SOLAR))
        except SourceError as exc:
            failed.append("Photovoltaik")
            first = first or str(exc)
        if len(failed) == 2:
            raise SourceError(f"SGD Nord: keine Sammlung lieferbar ({first})")
        self.log.info("%d Windräder, %d Solarparks (SGD Nord)", len(wind), len(solar))
        note = f"teilweise: {', '.join(failed)} fehlgeschlagen, letzter Stand bleibt" if failed else (None if wind or solar else "keine Anlagen im Radius gefunden")
        return CollectResult(cache={"energie_rok": {"wind": wind, "solar": solar}}, complete=not failed, note=note, writes_events=False)


COLLECTOR = SgdNordEnergieCollector
