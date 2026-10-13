"""Tests für tools/mvt.py: Linien und Punkte mit getypten Attributen kodieren, wieder lesen, als PMTiles schreiben."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from pmtiles.reader import MmapSource, Reader

SPEC = importlib.util.spec_from_file_location("mvt", Path(__file__).resolve().parent.parent / "tools" / "mvt.py")
mvt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mvt)


def test_linie_roundtrip_mit_attributen():
    lay = mvt.Layer("abfluss")
    lay.add(2, mvt.line_geometry([[(10, 20), (30, 25), (-5, 4100)]]), {"k": 3, "ha": 120, "name": "Bach", "f": 1.5, "neg": -2, "ok": True})
    lay.add(2, mvt.line_geometry([[(0, 0), (1, 1)], [(5, 5), (9, 5)]]), {"k": 3})
    got = mvt.read_layers(mvt.tile_bytes([lay]))["abfluss"]
    assert got[0]["props"] == {"k": 3, "ha": 120, "name": "Bach", "f": 1.5, "neg": -2, "ok": True}
    assert mvt.decode_line(got[0]["geom"]) == [[(10, 20), (30, 25), (-5, 4100)]]
    assert mvt.decode_line(got[1]["geom"]) == [[(0, 0), (1, 1)], [(5, 5), (9, 5)]]
    assert got[1]["props"] == {"k": 3}


def test_werte_werden_geteilt():
    lay = mvt.Layer("x")
    for i in range(5):
        lay.add(1, mvt.point_geometry(i, i), {"k": 7})
    assert len(lay.values) == 1 and len(lay.keys) == 1


def test_zu_kurze_linien_und_leere_geometrie_entfallen():
    lay = mvt.Layer("x")
    lay.add(2, mvt.line_geometry([[(1, 1)]]), {"k": 1})
    assert lay.features == []


def test_punkt():
    lay = mvt.Layer("senken")
    lay.add(1, mvt.point_geometry(100, 200), {"v": 350})
    (f,) = mvt.read_layers(mvt.tile_bytes([lay]))["senken"]
    assert f["type"] == 1 and f["props"] == {"v": 350}


def test_pmtiles(tmp_path):
    lay = mvt.Layer("abfluss")
    lay.add(2, mvt.line_geometry([[(0, 0), (4000, 4000)]]), {"k": 1})
    out = tmp_path / "a.pmtiles"
    res = mvt.write_pmtiles({(12, 2125, 1390): mvt.tile_bytes([lay])}, out, {"name": "t", "attribution": "A"})
    assert res["kacheln"] == 1
    with open(out, "rb") as fh:
        rd = Reader(MmapSource(fh))
        assert rd.metadata()["attribution"] == "A" and rd.header()["min_zoom"] == 12
        assert mvt.read_layers(rd.get(12, 2125, 1390))["abfluss"][0]["props"] == {"k": 1}
