"""Tests für tools/build_klippen_dgm.py: Wand im Höhenfeld finden, Laufrichtung (tiefe Seite rechts), Kacheln schreiben."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
pytest.importorskip("mapbox_vector_tile")

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_klippen_dgm", ROOT / "tools" / "build_klippen_dgm.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)

KW = dict(slope=55.0, min_cells=8, min_len_m=24.0, min_drop=6.0, sigma=0.6, simplify_m=3.0)


def feld(n=300):
    """Hochfläche im Norden (400 m), Tiefland im Süden (380 m), dazwischen eine 20 m hohe Wand auf Zeile 150 (West-Ost)."""
    h = np.full((n, n), 400.0, np.float32)
    h[150:, :] = 380.0
    h[148:152, :] = np.linspace(400.0, 380.0, 4)[:, None]      # 20 m auf 4 Zellen = 16 m: sehr steil
    return h


def test_wand_wird_gefunden_und_zeigt_nach_osten():
    lines = K.block_lines(feld(), **KW)
    assert lines, "keine Linie gefunden"
    pts, drop = max(lines, key=lambda x: len(x[0]))
    assert 12 < drop < 24
    # Norden oben (Zeile 0), Hochfläche oben: Laufrichtung Ost, tiefe Seite (Süden) rechts
    assert pts[-1, 1] > pts[0, 1]
    assert 146 < pts[:, 0].mean() < 154


def test_sanfter_hang_gibt_keine_linie():
    h = np.tile(np.linspace(400, 300, 300, dtype=np.float32)[:, None], (1, 300))   # 100 m auf 1200 m = 5 Grad
    assert K.block_lines(h, **KW) == []


def test_nodata_rand_ist_keine_wand():
    h = feld()
    h[:, 200:] = np.nan
    lines = K.block_lines(h, **KW)
    for pts, _ in lines:
        assert pts[:, 1].max() < 199


def test_kacheln_behalten_laufrichtung(tmp_path):
    import mapbox_vector_tile as mvt
    lon0, lat = 6.40, 49.85
    coords = [[lon0 + i * 0.0003, lat] for i in range(40)]
    n = K.write_tiles([(coords, 15.0)], tmp_path)
    assert n >= 1
    f = next(tmp_path.glob("12/*/*.pbf"))
    layer = mvt.decode(f.read_bytes())["klippen"]
    g = layer["features"][0]["geometry"]["coordinates"]
    assert g[-1][0] > g[0][0]                      # Richtung Ost bleibt erhalten
    assert layer["features"][0]["properties"]["drop"] == 15.0


def test_trace_loest_staffelecken():
    sk = np.zeros((10, 10), bool)
    for i in range(6):
        sk[5, i] = True
    sk[4, 5] = True                                    # Treppenecke
    ch = K.trace(sk)
    assert len(ch) == 1 and len(ch[0]) == 7


def test_wand_quer_zu_den_hoehenlinien_wird_verworfen():
    """Eine Linie, die dem Gefälle folgt (statt der Höhenlinie), widerspricht dem Gelände."""
    h = np.tile(np.linspace(400, 300, 300, dtype=np.float32)[:, None], (1, 300))     # Gefälle nach Süden
    laengs = np.array([[r, 150.0] for r in range(40, 260, 2)])                       # Nord-Süd, mit dem Gefälle
    quer = np.array([[150.0, c] for c in range(40, 260, 2)])                         # West-Ost, entlang der Höhenlinie
    assert not K.along_contour(K.gradient_field(h), laengs, 35.0).any()
    assert K.along_contour(K.gradient_field(h), quer, 35.0).all()
