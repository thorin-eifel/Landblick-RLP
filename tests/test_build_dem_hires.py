"""Tests für tools/build_dem_hires.py: Abtasten der 1-m-Rohkacheln, Lücken, Kachelgrenzen, Rundung."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pyproj")
pytest.importorskip("scipy")
pytest.importorskip("PIL")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location("build_dem_hires", ROOT / "tools" / "build_dem_hires.py")
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)

E0, N0 = 360, 5540          # Rohkachel 360000 / 5540000 (UTM 32), liegt bei rund 6,6 E / 50,0 N


def roh(tmp, e, n, f):
    """Rohkachel mit Höhe f(x_m, y_m) in Metern, Zeile 0 = Nord."""
    ys, xs = np.mgrid[0:1000, 0:1000]
    h = f(xs + 0.5, 1000 - ys - 0.5)
    np.savez_compressed(tmp / f"{e}_{n}.npz", a=np.round((h + H.OFFSET) * H.SCALE).astype(np.uint16))


def lonlat(e, n):
    from pyproj import Transformer
    return Transformer.from_crs(25832, 4326, always_xy=True).transform(e, n)


def test_ebene_wird_bilinear_getroffen(tmp_path):
    roh(tmp_path, E0, N0, lambda x, y: 300 + 0.1 * x + 0.2 * y)          # 0,1 m je m nach Osten, 0,2 nach Norden
    lon, lat = lonlat(E0 * 1000 + 400.0, N0 * 1000 + 600.0)
    h = H.sample(tmp_path, np.array([[lon]]), np.array([[lat]]), {})
    assert abs(float(h[0, 0]) - (300 + 40 + 120)) < 0.05


def test_ueber_kachelgrenze_ohne_sprung(tmp_path):
    f = lambda x, y: 300 + 0.05 * x                                       # noqa: E731
    roh(tmp_path, E0, N0, f)
    roh(tmp_path, E0 + 1, N0, lambda x, y: 300 + 0.05 * (x + 1000))
    lon, lat = lonlat(E0 * 1000 + 999.5, N0 * 1000 + 500)
    lon2, lat2 = lonlat(E0 * 1000 + 1000.5, N0 * 1000 + 500)
    h = H.sample(tmp_path, np.array([[lon, lon2]]), np.array([[lat, lat2]]), {})
    assert abs(float(h[0, 1] - h[0, 0]) - 0.05) < 0.02


def test_luecke_gibt_nan_und_keine_nullmischung(tmp_path):
    roh(tmp_path, E0, N0, lambda x, y: np.full_like(x, 300.0))
    a = np.load(tmp_path / f"{E0}_{N0}.npz")["a"]
    a[:, :500] = 0                                                         # westliche Hälfte ohne Daten
    np.savez_compressed(tmp_path / f"{E0}_{N0}.npz", a=a)
    lo, la = lonlat(E0 * 1000 + 200, N0 * 1000 + 500)
    lo2, la2 = lonlat(E0 * 1000 + 499.5, N0 * 1000 + 500)                  # direkt an der Lücke
    lo3, la3 = lonlat(E0 * 1000 + 800, N0 * 1000 + 500)
    h = H.sample(tmp_path, np.array([[lo, lo2, lo3]]), np.array([[la, la2, la3]]), {})
    assert np.isnan(h[0, 0]) and np.isnan(h[0, 1]) and abs(float(h[0, 2]) - 300) < 0.02


def test_fehlende_rohkachel_ist_nan(tmp_path):
    lon, lat = lonlat(E0 * 1000 + 500, N0 * 1000 + 500)
    assert np.isnan(H.sample(tmp_path, np.array([[lon]]), np.array([[lat]]), {})).all()


def test_rundung_auf_sechzehntel():
    q = H.quantize(np.array([100.01, 100.04, 100.07]), 16)
    assert np.allclose(q * 16, np.round(q * 16)) and abs(q[1] - 100.0625) < 1e-9


def test_kachel_wird_geschrieben_und_gelesen(tmp_path):
    from build_dem_rlp import pixel_lonlat, read_png, tile_xy
    raw = tmp_path / "raw"
    raw.mkdir()
    for dn in (-1, 0, 1):
        for de in (-1, 0, 1):
            roh(raw, E0 + de, N0 + dn, lambda x, y: np.full_like(x, 321.5))
    lon, lat = lonlat(E0 * 1000 + 500, N0 * 1000 + 500)
    x, y = tile_xy(lon, lat, 16)
    out = tmp_path / "dem"
    assert H.work((str(raw), str(out), 16, x, y, 16, False, False))[1] == 1
    h = read_png(out / "16" / str(x) / f"{y}.png")
    assert h.shape == (256, 256) and abs(float(h.mean()) - 321.5) < 0.07
    assert H.work((str(raw), str(out), 16, x + 40, y, 16, False, False))[1] == 0      # weit weg: keine Landesdaten, keine Kachel


def test_elternfuellung_ohne_stufe_an_elterngrenze(tmp_path):
    """Kindkacheln unter verschiedenen Eltern müssen an der Grenze nahtlos anschließen (sonst Linie in der Schummerung)."""
    k, px, py = 0.5, 8500, 5500                       # 0,5 m je Elternpixel in beide Richtungen
    jj, ii = np.mgrid[0:256, 0:256]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            h = 300 + k * (dx * 256 + ii + 0.5) + k * (dy * 256 + jj + 0.5)      # lokal gezählt, Terrarium reicht nur bis 32 km
            H.write_tile(tmp_path / "14" / str(px + dx) / f"{py + dy}.png", h.astype(np.float32))
    a = H.parent_fill(tmp_path, 15, 2 * px + 1, 2 * py, 256)           # rechts am Rand der Eltern
    b = H.parent_fill(tmp_path, 15, 2 * px + 2, 2 * py, 256)           # links in der Nachbarelternkachel
    step = b[:, 0] - a[:, -1]
    assert np.allclose(step, k / 2, atol=0.02), step[:3]                # ein Kindpixel = halber Elternpixel
    # absolute Lage: Kindpixel (0, 0) der Kachel a liegt bei Elternkoordinate (px*256 + 128 + 0.25)
    want = 300 + k * (128 + 0.25) + k * 0.25
    assert abs(float(a[0, 0]) - want) < 0.02


def test_elternfuellung_fehlende_nachbarn_ergibt_keine_nan(tmp_path):
    H.write_tile(tmp_path / "14" / "100" / "100.png", np.full((256, 256), 200.0, np.float32))
    f = H.parent_fill(tmp_path, 15, 200, 200, 256)
    assert f is not None and not np.isnan(f).any() and abs(float(f.mean()) - 200) < 0.05
    assert H.parent_fill(tmp_path, 15, 2, 2, 256) is None
