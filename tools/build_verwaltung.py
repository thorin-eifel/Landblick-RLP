#!/usr/bin/env python3
"""Verwaltungsflächen für die Rechtsklick-Auskunft der Karte: Gemeinde, Verbandsgemeinde, Kreis und Ortsteile als eine kleine JSON-Datei.

Zweck:      Die Karte kennt bisher nur Kreisumrisse und Grenzlinien ohne Namen. Für "Was liegt unter dem Zeiger?" braucht der Browser
            Flächen mit Namen. Diese Datei bringt sie mit, damit die Abfrage lokal läuft (Punkt-in-Fläche im Browser, keine Anfrage
            an Dritte).
Quelle:     LVermGeo Rheinland-Pfalz, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet]
            - dlkm_au.zip (INSPIRE Verwaltungseinheiten aus dem Liegenschaftskataster, GML, EPSG:4258):
              https://geobasis-rlp.de/data/inspire-annexi/current/xml/dlkm_au.zip
            - WOHNPLATZVERZEICHNIS_RP.zip (Ortsteile und Wohnplätze, CSV, UTM 32):
              https://geobasis-rlp.de/data/wohnplatz/current/zip/WOHNPLATZVERZEICHNIS_RP.zip
Datenschutz: Flächen und Ortsnamen; keine Personen, keine Adressen, keine Flurstücke. Das Wohnplatzverzeichnis enthält Einwohnerzahlen
            je Ortsteil (Zahlen, keine Personen); sie werden nicht übernommen.
Ablauf:     1. Verwaltungseinheiten lesen (Stufe 4 Kreis/Stadt, 5 Verbandsgemeinde, 6 Gemeinde), Hierarchie über upperLevelUnit
            2. Gemeindeflächen vereinfachen (Toleranz --tol Grad) und als ganzzahlige Deltas (1e-5 Grad) ablegen
            3. Ortsteile (Zeile der Gemeinde selbst und Wohnplatznummer auf 00) und Wohnplätze nach Gemeinde einsortieren (Punkt in Fläche)
Ausgabe:    web/geo/verwaltung.json (siehe docs/betrieb.md, Abschnitt Rechtsklick)
Aufruf:     python tools/build_verwaltung.py --au dlkm_au.gml --wohnplatz WOHNPLATZ_RP_wohnplcsv.CSV --out web/geo/verwaltung.json
Parameter:  --tol 0.00005   Vereinfachung in Grad (rund 5 m); --stand "Dezember 2025" für den Vermerk
Exit:       0 = fertig, 1 = Fehler
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

log = logging.getLogger("osint.verwaltung")

A = "{http://inspire.ec.europa.eu/schemas/au/5.0}"
G = "{http://www.opengis.net/gml/3.2}"
GN = "{http://inspire.ec.europa.eu/schemas/gn/4.0}"
XL = "{http://www.w3.org/1999/xlink}"
STUFE = {"4thOrder": "kreis", "5thOrder": "vg", "6thOrder": "gemeinde"}
SCALE = 100000   # 1e-5 Grad je Einheit (rund 1 m)
ATTRIBUTION = "© GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet]"


def ring_ints(coords: list[tuple[float, float]]) -> list[int]:
    """Ring (lon, lat) → [x0, y0, dx1, dy1, ...] in Einheiten von 1e-5 Grad; letzter Punkt (= erster) entfällt."""
    pts = [(round(x * SCALE), round(y * SCALE)) for x, y in coords]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    out: list[int] = []
    px = py = 0
    for x, y in pts:
        out += [x - px, y - py]
        px, py = x, y
    return out


def read_au(path: Path) -> dict[str, dict]:
    """Verwaltungseinheiten der Stufen 4 bis 6: gml:id → {code, name, art, upper, polys[[(lon, lat)...]]} (nur Außenringe)."""
    out: dict[str, dict] = {}
    for _, el in ET.iterparse(path):
        if el.tag != A + "AdministrativeUnit":
            continue
        href = (el.find(A + "nationalLevel").get(XL + "href") or "") if el.find(A + "nationalLevel") is not None else ""
        art = STUFE.get(href.rsplit("/", 1)[-1])
        if art:
            polys = []
            for poly in el.iter(G + "Polygon"):
                ext = poly.find(f"{G}exterior/{G}LinearRing/{G}posList")
                if ext is None or not ext.text:
                    continue
                v = [float(t) for t in ext.text.split()]
                polys.append([(v[i + 1], v[i]) for i in range(0, len(v) - 1, 2)])   # posList ist Breite Länge (EPSG:4258)
            up = el.find(A + "upperLevelUnit")
            out[el.get(G + "id")] = {
                "code": el.findtext(A + "nationalCode"), "name": el.findtext(f".//{GN}text"), "art": art,
                "upper": (up.get(XL + "href") or "").lstrip("#") if up is not None else "", "polys": polys,
            }
        el.clear()
    return out


def read_wohnplatz(path: Path) -> list[dict]:
    """Wohnplatzverzeichnis (Latin-1, ; getrennt) → [{name, lon, lat, ortsteil}]. UTM-32-Rechtswert trägt die Zonennummer vorweg."""
    from pyproj import Transformer
    tr = Transformer.from_crs(25832, 4326, always_xy=True)
    out = []
    with open(path, encoding="latin-1", newline="") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            try:
                e, n = int(r["UTM_Rechtswert"]) - 32_000_000, int(r["UTM_Hochwert"])
            except (KeyError, ValueError):
                continue
            nr = (r.get("WpNr") or "").strip()
            lon, lat = tr.transform(e, n)
            name = r["Gemeinde_Gemeindeteile"].split("(")[0].strip()
            if nr == "":      # Zeile der Gemeinde: der Zusatz nach dem Komma ist die Verwaltungsart ("Kreisfreie Stadt", "große kreisangehörige Stadt" ...)
                name = name.split(",")[0]
            name = re.sub(r",\s*Stadt$", "", name)      # Ortsteile tragen es teils auch ("Alzey, Stadt")
            out.append({"name": " ".join(name.split()), "lon": lon, "lat": lat, "ortsteil": nr == "" or nr.endswith("00")})
    return out


def build(au: dict[str, dict], wohn: list[dict], tol: float) -> dict:
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    kreise = {u["code"]: u["name"] for u in au.values() if u["art"] == "kreis"}
    vg_by_id = {i: u for i, u in au.items() if u["art"] == "vg"}
    kreis_by_id = {i: u for i, u in au.items() if u["art"] == "kreis"}
    vgs: dict[str, int] = {}
    vg_liste: list[dict] = []
    gemeinden: list[dict] = []
    flaechen = []
    for gid, u in sorted(((i, u) for i, u in au.items() if u["art"] == "gemeinde"), key=lambda t: t[1]["code"]):
        vg = vg_by_id.get(u["upper"])
        kreis = kreis_by_id.get(vg["upper"] if vg else u["upper"])
        if vg and vg["code"] not in vgs:
            vgs[vg["code"]] = len(vg_liste)
            vg_liste.append({"c": vg["code"], "n": vg["name"]})
        rings = []
        shp = []
        for p in u["polys"]:
            poly = Polygon(p)
            if not poly.is_valid:
                poly = poly.buffer(0)
            simp = poly.simplify(tol, preserve_topology=True)
            if simp.is_empty or simp.geom_type != "Polygon":
                simp = poly
            rings.append(ring_ints(list(simp.exterior.coords)))
            shp.append(simp)
        gemeinden.append({"c": u["code"], "n": u["name"], "vg": vgs[vg["code"]] if vg else -1, "k": kreis["code"] if kreis else u["code"][:5], "r": rings})
        flaechen.append(prep(shp[0] if len(shp) == 1 else unary_union(shp)))
    orte = []
    for w in wohn:
        pt = Point(w["lon"], w["lat"])
        gi = next((i for i, f in enumerate(flaechen) if f.contains(pt)), -1)
        orte.append([w["name"], round(w["lon"] * SCALE), round(w["lat"] * SCALE), gi, 1 if w["ortsteil"] else 0])
    log.info("%d Gemeinden, %d Verbandsgemeinden, %d Kreise, %d Orte (%d ohne Gemeinde)", len(gemeinden), len(vg_liste), len(kreise), len(orte), sum(1 for o in orte if o[3] < 0))
    return {"version": 1, "scale": SCALE, "attribution": ATTRIBUTION, "kreise": kreise, "vg": vg_liste, "gemeinden": gemeinden, "orte": orte}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--au", type=Path, required=True, help="dlkm_au.gml")
    ap.add_argument("--wohnplatz", type=Path, required=True, help="WOHNPLATZ_RP_wohnplcsv.CSV")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tol", type=float, default=0.00005)
    ap.add_argument("--stand", default="")
    args = ap.parse_args(argv)
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    au = read_au(args.au)
    data = build(au, read_wohnplatz(args.wohnplatz), args.tol)
    if args.stand:
        data["stand"] = args.stand
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(args.out)
    log.info("geschrieben: %s (%.2f MB)", args.out, args.out.stat().st_size / 1e6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
