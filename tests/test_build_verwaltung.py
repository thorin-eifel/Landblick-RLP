"""Tests für tools/build_verwaltung.py: INSPIRE-Verwaltungseinheiten und Wohnplatzverzeichnis → verwaltung.json."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from pyproj import Transformer

SPEC = importlib.util.spec_from_file_location("build_verwaltung", Path(__file__).resolve().parent.parent / "tools" / "build_verwaltung.py")
bv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bv)

LVL = "http://inspire.ec.europa.eu/codelist/AdministrativeHierarchyLevel/"


def _unit(gid: str, code: str, name: str, stufe: str, upper: str, quadrat: tuple[float, float, float] | None) -> str:
    """Eine Verwaltungseinheit im Aufbau der LVermGeo-Datei (posList ist Breite Länge)."""
    geom = ""
    if quadrat:
        lon, lat, s = quadrat
        pts = [(lat, lon), (lat, lon + s), (lat + s, lon + s), (lat + s, lon), (lat, lon)]
        pl = " ".join(f"{a} {b}" for a, b in pts)
        geom = (f'<au:geometry><gml:MultiSurface><gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>{pl}'
                '</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface></au:geometry>')
    return (f'<wfs:member><au:AdministrativeUnit gml:id="{gid}">{geom}<au:nationalCode>{code}</au:nationalCode>'
            f'<au:nationalLevel xlink:href="{LVL}{stufe}"/><au:name><gn:GeographicalName><gn:spelling><gn:SpellingOfName><gn:text>{name}</gn:text>'
            f'</gn:SpellingOfName></gn:spelling></gn:GeographicalName></au:name>'
            f'<au:upperLevelUnit xlink:href="#{upper}"/></au:AdministrativeUnit></wfs:member>')


def _gml(path: Path, lon: float, lat: float) -> None:
    ns = ('xmlns:au="http://inspire.ec.europa.eu/schemas/au/5.0" xmlns:gml="http://www.opengis.net/gml/3.2" '
          'xmlns:gn="http://inspire.ec.europa.eu/schemas/gn/4.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:wfs="http://www.opengis.net/wfs/2.0"')
    body = (_unit("K1", "07232", "Eifelkreis Bitburg-Prüm", "4thOrder", "RB", None)
            + _unit("V1", "0723205", "Südeifel", "5thOrder", "K1", None)
            + _unit("G1", "07232063", "Irrel", "6thOrder", "V1", (lon, lat, 0.02))
            + _unit("G2", "07232999", "Verbandsfrei", "6thOrder", "K1", (lon + 0.02, lat, 0.02))
            + _unit("L1", "07", "Rheinland-Pfalz", "2ndOrder", "X", None))
    path.write_text(f'<?xml version="1.0"?><wfs:FeatureCollection {ns}>{body}</wfs:FeatureCollection>', encoding="utf-8")


def _csv(path: Path, zeilen: list[tuple[str, str, float, float]]) -> None:
    tr = Transformer.from_crs(4326, 25832, always_xy=True)
    kopf = "GemSchlNr;WpNr;Gemeinde_Gemeindeteile;Landkreis;Verbandsgemeinde;TK_Nr;Fläche_ha;Einwohner;PLZ;UTM_Rechtswert;UTM_Hochwert\n"
    rows = []
    for nr, name, lon, lat in zeilen:
        e, n = tr.transform(lon, lat)
        rows.append(f"23205063;{nr};{name};;;6104;;1674;;{32_000_000 + round(e)};{round(n)}")
    path.write_bytes((kopf + "\n".join(rows) + "\n").encode("latin-1"))


@pytest.fixture()
def daten(tmp_path):
    lon, lat = 6.44, 49.84
    gml, csv = tmp_path / "au.gml", tmp_path / "w.csv"
    _gml(gml, lon, lat)
    _csv(csv, [("", "Irrel", lon + 0.01, lat + 0.01), ("0100", "Hof Beispiel (Weiler)", lon + 0.005, lat + 0.005), ("0101", "Forsthaus", lon + 0.015, lat + 0.015),
               ("", "Trier, Kreisfreie Stadt", lon + 0.03, lat + 0.01)])
    out = tmp_path / "v.json"
    assert bv.main(["--au", str(gml), "--wohnplatz", str(csv), "--out", str(out), "--stand", "Test"]) == 0
    return json.loads(out.read_text(encoding="utf-8")), (lon, lat)


def test_nur_gemeinden_kommen_als_flaechen_mit(daten):
    d, _ = daten
    assert [g["n"] for g in d["gemeinden"]] == ["Irrel", "Verbandsfrei"]
    assert d["kreise"] == {"07232": "Eifelkreis Bitburg-Prüm"}
    assert d["stand"] == "Test" and "dl-de/by-2-0" in d["attribution"]


def test_hierarchie_ueber_upperlevelunit(daten):
    d, _ = daten
    irrel, frei = d["gemeinden"]
    assert d["vg"][irrel["vg"]]["n"] == "Südeifel" and irrel["k"] == "07232"
    assert frei["vg"] == -1 and frei["k"] == "07232"          # direkt unter dem Kreis


def test_ring_deltas_ergeben_die_ecken(daten):
    d, (lon, lat) = daten
    ring = d["gemeinden"][0]["r"][0]
    x = y = 0
    pts = []
    for i in range(0, len(ring), 2):
        x += ring[i]; y += ring[i + 1]
        pts.append((x / d["scale"], y / d["scale"]))
    assert len(pts) == 4                                      # geschlossener Ring ohne Doppelpunkt am Ende
    assert min(p[0] for p in pts) == pytest.approx(lon, abs=2e-5) and max(p[1] for p in pts) == pytest.approx(lat + 0.02, abs=2e-5)


def test_orte_nach_gemeinde_und_art(daten):
    d, _ = daten
    nach = {o[0]: (o[3], o[4]) for o in d["orte"]}
    assert nach["Irrel"] == (0, 1)                            # Zeile der Gemeinde selbst zählt als Ortsteil
    assert nach["Hof Beispiel"] == (0, 1)                     # WpNr 0100: Ortsteil, Klammerzusatz entfällt
    assert nach["Forsthaus"] == (0, 0)                        # WpNr 0101: Wohnplatz
    assert nach["Trier"] == (1, 1)                            # ", Kreisfreie Stadt" entfällt


def test_utm_umrechnung_der_orte(daten):
    d, (lon, lat) = daten
    irrel = next(o for o in d["orte"] if o[0] == "Irrel")
    assert irrel[1] / d["scale"] == pytest.approx(lon + 0.01, abs=2e-5) and irrel[2] / d["scale"] == pytest.approx(lat + 0.01, abs=2e-5)
