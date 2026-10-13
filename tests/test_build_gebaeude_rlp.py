"""Tests für tools/build_gebaeude_rlp.py: Hausumringe → MVT, OSM nur außerhalb der Landesgrenze, PMTiles-Ausgabe."""
from __future__ import annotations

import importlib.util
import json
import struct
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest
from pmtiles.reader import MmapSource, Reader
from pyproj import Transformer
from shapely.geometry import box, mapping

SPEC = importlib.util.spec_from_file_location("build_gebaeude_rlp", Path(__file__).resolve().parent.parent / "tools" / "build_gebaeude_rlp.py")
bg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bg)

TX, TY = 16971, 11134          # Zoom-15-Kachel mit Irrel
TO_UTM = Transformer.from_crs(4326, 25832, always_xy=True)


def _shp(path: Path, polys: list[list[list[tuple[float, float]]]]) -> None:
    """Minimale Shapefile-Datei (nur .shp): je Merkmal eine Liste von Ringen in UTM."""
    body = b""
    for i, rings in enumerate(polys, 1):
        pts = [p for r in rings for p in r]
        parts = []
        k = 0
        for r in rings:
            parts.append(k)
            k += len(r)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        rec = struct.pack("<i4d2i", 5, min(xs), min(ys), max(xs), max(ys), len(rings), len(pts))
        rec += struct.pack(f"<{len(parts)}i", *parts) + b"".join(struct.pack("<2d", *p) for p in pts)
        body += struct.pack(">2i", i, len(rec) // 2) + rec
    head = struct.pack(">i", 9994) + b"\0" * 20 + struct.pack(">i", (100 + len(body)) // 2) + b"\0" * 72
    path.write_bytes(head + body)


def _dbf(path: Path, gfk: list[str]) -> None:
    """Minimale .dbf mit den Spalten AGS (8), GFK (10), OI (16) – nur zum Prüfen, dass genau GFK gelesen wird."""
    felder = [("AGS", 8), ("GFK", 10), ("OI", 16)]
    rlen = 1 + sum(n for _, n in felder)
    hlen = 32 + 32 * len(felder) + 1
    kopf = struct.pack("<B3BIHH20x", 3, 126, 1, 1, len(gfk), hlen, rlen)
    desc = b"".join(n.encode().ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([ln]) + b"\0" * 15 for n, ln in felder)
    body = b"".join(b" " + b"07232001".ljust(8) + g.encode().ljust(10) + b"X" * 16 for g in gfk)
    path.write_bytes(kopf + desc + b"\r" + body)


def _quadrat(e0: float, n0: float, s: float, *, uhrzeigersinn: bool = True) -> list[tuple[float, float]]:
    """Quadrat in UTM, geschlossen; Standard Uhrzeigersinn (y nach oben) wie Außenringe im Shapefile."""
    r = [(e0, n0), (e0, n0 + s), (e0 + s, n0 + s), (e0 + s, n0), (e0, n0)]
    return r if uhrzeigersinn else r[::-1]


def _irrel_utm() -> tuple[float, float]:
    lon, lat = bg.tile_lonlat(15, TX, TY, 2048, 2048)
    return TO_UTM.transform(lon, lat)


def _grenze(path: Path, geom) -> Path:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(geom)}]}))
    return path


def _lese(pm: Path, z: int, x: int, y: int):
    with open(pm, "rb") as fh:
        data = Reader(MmapSource(fh)).get(z, x, y)
    return None if data is None else bg.read_buildings(data)


def _ring_flaechen(geom: list[int]) -> list[float]:
    """Doppelte Flächen aller Ringe einer Befehlsliste (Vorzeichen: positiv = Außenring)."""
    out, ring, x, y, i = [], [], 0, 0, 0
    while i < len(geom):
        cmd, cnt = geom[i] & 7, geom[i] >> 3
        i += 1
        if cmd == 7:
            out.append(bg.ring_area2([p[0] for p in ring], [p[1] for p in ring]))
            ring = []
            continue
        for _ in range(cnt):
            x += (geom[i] >> 1) ^ -(geom[i] & 1)
            y += (geom[i + 1] >> 1) ^ -(geom[i + 1] & 1)
            i += 2
            ring.append((x, y))
    return out


def test_geometrie_aussenring_positiv_loch_negativ():
    aussen = ([0, 100, 100, 0], [0, 0, 100, 100], True)
    loch = ([20, 20, 40, 40], [20, 40, 40, 20], False)
    for a_rev in (False, True):
        for l_rev in (False, True):      # Eingabe in beliebiger Laufrichtung: Ausgabe folgt der Rolle, nicht der Eingabe
            a = tuple(list(v)[::-1] if a_rev and isinstance(v, list) else v for v in aussen)
            lo = tuple(list(v)[::-1] if l_rev and isinstance(v, list) else v for v in loch)
            f = _ring_flaechen(bg.geometry_ints([a, lo]))
            assert f[0] > 0 and f[1] < 0


def test_geometrie_entartete_ringe_fallen_weg():
    assert bg.geometry_ints([([1, 1, 1], [2, 2, 2], True)]) == []
    assert bg.geometry_ints([([0, 5], [0, 5], True)]) == []


def test_kachel_roundtrip_und_attribut():
    g = bg.geometry_ints([([10, 110, 110, 10], [10, 10, 90, 90], True)])
    tile = bg.tile_bytes([bg.feature_bytes(g), bg.feature_bytes(g)])
    extent, geoms = bg.read_buildings(tile)
    assert extent == 4096 and geoms == [g, g]


def test_fremde_arten_werden_nicht_gelesen():
    """kind=address (Hausnummern, Punkte) und Nicht-Gebäude kommen nicht mit."""
    g = bg.geometry_ints([([0, 10, 10, 0], [0, 0, 10, 10], True)])
    ft = b"\x12" + bg.varint(2) + bg.packed([0, 1]) + b"\x18\x03" + b"\x22" + bg.varint(len(bg.packed(g))) + bg.packed(g)
    body = b"\x0a\x09buildings" + b"\x12" + bg.varint(len(ft)) + ft + b"\x1a\x04kind" + b"\x22\x09\x0a\x07address" + b"\x28\x80\x20\x78\x02"
    assert bg.read_buildings(b"\x1a" + bg.varint(len(body)) + body)[1] == []


def test_hausumring_landet_an_der_richtigen_stelle(tmp_path):
    e, n = _irrel_utm()
    shp = tmp_path / "hu.shp"
    _shp(shp, [[_quadrat(e, n, 12.0)]])
    grenze = _grenze(tmp_path / "g.geojson", box(0, 0, 1, 1))
    out = tmp_path / "geb.pmtiles"
    assert bg.main(["--hu", str(shp), "--grenze", str(grenze), "--out", str(out)]) == 0
    extent, geoms = _lese(out, 15, TX, TY)
    assert extent == 4096 and len(geoms) == 1
    pts = bg.first_ring_points(geoms[0])
    assert len(pts) == 4
    back = [TO_UTM.transform(*bg.tile_lonlat(15, TX, TY, px, py)) for px, py in pts]
    soll = {(round(e), round(n)), (round(e), round(n + 12)), (round(e + 12), round(n + 12)), (round(e + 12), round(n))}
    for be, bn in back:
        assert min(abs(be - se) + abs(bn - sn) for se, sn in soll) < 1.0       # eine Rasterzelle ist 0,3 m
    (fl,) = _ring_flaechen(geoms[0])
    assert fl > 0                                                             # Außenring


def test_zoom14_nur_groessere(tmp_path):
    e, n = _irrel_utm()
    shp = tmp_path / "hu.shp"
    _shp(shp, [[_quadrat(e, n, 8.0)], [_quadrat(e + 50, n, 20.0)]])      # 64 m² und 400 m²
    grenze = _grenze(tmp_path / "g.geojson", box(0, 0, 1, 1))
    out = tmp_path / "geb.pmtiles"
    bg.main(["--hu", str(shp), "--grenze", str(grenze), "--out", str(out), "--min-z14", "120"])
    assert len(_lese(out, 15, TX, TY)[1]) == 2
    assert len(_lese(out, 14, TX >> 1, TY >> 1)[1]) == 1


def test_loch_im_hausumring(tmp_path):
    e, n = _irrel_utm()
    shp = tmp_path / "hu.shp"
    _shp(shp, [[_quadrat(e, n, 30.0), _quadrat(e + 10, n + 10, 8.0, uhrzeigersinn=False)]])
    grenze = _grenze(tmp_path / "g.geojson", box(0, 0, 1, 1))
    out = tmp_path / "geb.pmtiles"
    bg.main(["--hu", str(shp), "--grenze", str(grenze), "--out", str(out)])
    (geom,) = _lese(out, 15, TX, TY)[1]
    f = _ring_flaechen(geom)
    assert len(f) == 2 and f[0] > 0 > f[1]


def _osm_archiv(pfad: Path, merkmale: list[tuple[float, float]]) -> None:
    """Zoom-15-Kachel TX/TY mit Quadraten (Eckpunkt in Kachelpixeln)."""
    tiles = defaultdict(list)
    for px, py in merkmale:
        tiles[(15, TX, TY)].append(bg.feature_bytes(bg.geometry_ints([([int(px), int(px) + 60, int(px) + 60, int(px)], [int(py), int(py), int(py) + 60, int(py) + 60], True)])))
    bg.write_pmtiles(tiles, pfad, "Test")


def test_osm_nur_ausserhalb_der_grenze(tmp_path):
    west, nord = bg.tile_lonlat(15, TX, TY, 0, 0)
    mitte, _ = bg.tile_lonlat(15, TX, TY, 2048, 0)
    grenze = box(west - 1, 0, mitte, 90)            # linke Kachelhälfte liegt „im Land“
    core = tmp_path / "core.pmtiles"
    _osm_archiv(core, [(500, 500), (3000, 500)])    # links drinnen, rechts draußen
    tiles = defaultdict(list)
    keep, drop = bg.add_osm(core, {15}, grenze, tiles)
    assert (keep, drop) == (1, 1)
    (feat,) = tiles[(15, TX, TY)]
    extent, geoms = bg.read_buildings(bg.tile_bytes([feat]))
    assert bg.first_ring_points(geoms[0])[0][0] == 3000


def test_osm_kachel_ganz_im_land_wird_uebersprungen(tmp_path):
    core = tmp_path / "core.pmtiles"
    _osm_archiv(core, [(500, 500)])
    tiles = defaultdict(list)
    assert bg.add_osm(core, {15}, box(0, 0, 20, 80), tiles) == (0, 1)
    assert not tiles


def test_osm_kachel_ganz_ausserhalb_wird_uebernommen(tmp_path):
    core = tmp_path / "core.pmtiles"
    _osm_archiv(core, [(500, 500), (3000, 3000)])
    tiles = defaultdict(list)
    assert bg.add_osm(core, {15}, box(100, 0, 101, 1), tiles) == (2, 0)


def test_ausgabe_traegt_quellenvermerk_und_zoomgrenzen(tmp_path):
    e, n = _irrel_utm()
    shp = tmp_path / "hu.shp"
    _shp(shp, [[_quadrat(e, n, 20.0)]])
    grenze = _grenze(tmp_path / "g.geojson", box(0, 0, 1, 1))
    out = tmp_path / "geb.pmtiles"
    bg.main(["--hu", str(shp), "--grenze", str(grenze), "--out", str(out)])
    with open(out, "rb") as fh:
        rd = Reader(MmapSource(fh))
        h, m = rd.header(), rd.metadata()
    assert (h["min_zoom"], h["max_zoom"]) == (14, 15)
    assert "dl-de/by-2-0" in m["attribution"] and "OpenStreetMap" in m["attribution"]
    assert m["vector_layers"][0]["id"] == "buildings"


def test_ohne_dbf_geht_es_ohne_klassen(tmp_path):
    """Die .dbf darf fehlen: Umrisse kommen trotzdem, ohne Attribut klasse."""
    e, n = _irrel_utm()
    shp = tmp_path / "hu.shp"
    _shp(shp, [[_quadrat(e, n, 20.0)]])
    assert not (tmp_path / "hu.dbf").exists()
    assert bg.read_gfk(shp) is None
    (stapel,) = list(bg.read_shp(shp))
    assert len(stapel) == 1
    out = tmp_path / "geb.pmtiles"
    bg.main(["--hu", str(shp), "--grenze", str(_grenze(tmp_path / "g.geojson", box(0, 0, 1, 1))), "--out", str(out)])
    with open(out, "rb") as fh:
        (g, k), = bg.read_buildings_klasse(Reader(MmapSource(fh)).get(15, TX, TY))[1]
    assert k is None


def test_klassen_aus_gfk_landen_am_richtigen_haus(tmp_path):
    e, n = _irrel_utm()
    shp = tmp_path / "hu.shp"
    _shp(shp, [[_quadrat(e, n, 20.0)], [_quadrat(e + 50, n, 20.0)], [_quadrat(e + 100, n, 20.0)]])
    _dbf(tmp_path / "hu.dbf", ["31001_1000", "31001_3041", "31001_2463"])
    out = tmp_path / "geb.pmtiles"
    bg.main(["--hu", str(shp), "--grenze", str(_grenze(tmp_path / "g.geojson", box(0, 0, 1, 1))), "--out", str(out)])
    with open(out, "rb") as fh:
        rd = Reader(MmapSource(fh))
        merkmale = bg.read_buildings_klasse(rd.get(15, TX, TY))[1]
        meta = rd.metadata()
    by_x = {bg.first_ring_points(g)[0][0]: k for g, k in merkmale}
    assert [by_x[x] for x in sorted(by_x)] == ["wohnen", "religion", "garage"]      # Reihenfolge West nach Ost wie im Shapefile
    assert meta["vector_layers"][0]["fields"]["klasse"] == "String"


def test_klassen_bleiben_bei_ausschnitt_ausgerichtet(tmp_path):
    """Datensätze außerhalb des Ausschnitts werden übersprungen, die dbf-Zeile bleibt trotzdem die richtige."""
    e, n = _irrel_utm()
    shp = tmp_path / "hu.shp"
    _shp(shp, [[_quadrat(e + 30000, n, 20.0)], [_quadrat(e, n, 20.0)]])
    _dbf(tmp_path / "hu.dbf", ["31001_1000", "31001_3021"])
    lon, lat = bg.tile_lonlat(15, TX, TY, 2048, 2048)
    out = tmp_path / "geb.pmtiles"
    bg.main(["--hu", str(shp), "--grenze", str(_grenze(tmp_path / "g.geojson", box(0, 0, 1, 1))), "--out", str(out),
             "--bbox", str(lon - 0.01), str(lat - 0.01), str(lon + 0.01), str(lat + 0.01)])
    with open(out, "rb") as fh:
        ((g, k),) = bg.read_buildings_klasse(Reader(MmapSource(fh)).get(15, TX, TY))[1]
    assert k == "oeffentlich"


@pytest.mark.parametrize("gfk,soll", [
    ("31001_1000", "wohnen"), ("31001_1022", "wohnen"), ("31001_2000", "wirtschaft"), ("31001_2740", "wirtschaft"),
    ("31001_2463", "garage"), ("31001_2461", "garage"), ("51009_1610", "ueberdachung"), ("31001_2523", "technik"),
    ("31001_2611", "technik"), ("51001_1001", "technik"), ("31001_3021", "oeffentlich"), ("31001_3072", "oeffentlich"),
    ("31001_3041", "religion"), ("31001_3081", "religion"), ("31001_3043", "religion"), ("51006_1440", "sonst"),
    ("", "sonst"), (None, "sonst"), ("müll", "sonst"), ("31001_x", "sonst"),
])
def test_klasse_von_gfk(gfk, soll):
    assert bg.klasse_von_gfk(gfk) == soll


def test_alle_klassen_im_mapping_sind_bekannt():
    assert set(bg.CODE_KLASSE.values()) <= set(bg.KLASSEN)


def test_osm_merkmale_tragen_keine_klasse(tmp_path):
    core = tmp_path / "core.pmtiles"
    _osm_archiv(core, [(3000, 3000)])
    tiles = defaultdict(list)
    bg.add_osm(core, {15}, box(100, 0, 101, 1), tiles)
    ((g, k),) = bg.read_buildings_klasse(bg.tile_bytes(tiles[(15, TX, TY)]))[1]
    assert k is None


def test_ausschnitt_filtert(tmp_path):
    e, n = _irrel_utm()
    shp = tmp_path / "hu.shp"
    _shp(shp, [[_quadrat(e, n, 20.0)], [_quadrat(e + 20000, n, 20.0)]])
    lon, lat = bg.tile_lonlat(15, TX, TY, 2048, 2048)
    stapel = list(bg.read_shp(shp, TO_UTM.transform(lon - 0.01, lat - 0.01) + TO_UTM.transform(lon + 0.01, lat + 0.01)))
    assert sum(len(s) for s in stapel) == 1
