"""Tests für tools/build_dem_rlp.py: Terrarium-Kodierung, Dateiliste, Reduktion, Abtastung, Mitteln der Kinder."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("tifffile")
pytest.importorskip("PIL")
pytest.importorskip("pyproj")

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_dem_rlp", ROOT / "tools" / "build_dem_rlp.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

META = """<?xml version="1.0"?><metalink><file name="dgm1_32_337_5553_1_rp_2025.tif">
        <size>1624730</size>
        <hash type="sha-256">fb0bae91965a68dfe026eef3830df1551cb6084b55e7791946fcec41472e0059</hash>
        <url>https://geobasis-rlp.de/data/dgm1/current/tif/dgm1_32_337_5553_1_rp_2025.tif</url>
    </file><file name="dgm1_32_337_5553_1_rp_2025.tfw">
        <size>100</size>
        <hash type="sha-256">fb0bae91965a68dfe026eef3830df1551cb6084b55e7791946fcec41472e0059</hash>
        <url>https://geobasis-rlp.de/data/dgm1/current/tfw/x.tfw</url>
    </file><file name="dgm1_32_419_5490_1_rp_2022.tif">
        <size>1</size>
        <hash type="sha-256">00b19b3dc396f7f5055b005f2e3422087534d5fc48162079ee7e57d900873dd0</hash>
        <url>https://evil.example/x.tif</url>
    </file></metalink>"""


def test_terrarium_roundtrip():
    h = np.array([[0.0, 1.5, 499.99609375, -12.25, 816.0]], np.float32)
    back = B.decode_terrarium(B.encode_terrarium(h))
    assert np.abs(back - h).max() <= 1 / 256 + 1e-6


def test_meta4_nur_tif_und_nur_geobasis():
    items = B.parse_meta4(META)
    assert [(i["e"], i["n"], i["year"]) for i in items] == [(337, 5553, 2025)]   # tfw und fremder Host fallen heraus
    assert len(items[0]["sha"]) == 64


def test_attribution_jahre():
    assert "2025," in B.attribution([2025]) and "2022–2025" in B.attribution([2022, 2025, 2023])
    assert "dl-de/by-2-0" in B.attribution([2024]) and "Daten bearbeitet" in B.attribution([2024])


def test_reduce_tif_mittelt_und_markiert_luecken(tmp_path):
    import tifffile
    a = np.full((1000, 1000), 400.0, np.float32)
    a[:, :500] += np.arange(500, dtype=np.float32)[None, :] * 0.1          # Hang links
    a[:8, :8] = B.NODATA                                                     # 2 x 2 Blöcke ohne Daten
    p = tmp_path / "k.tif"
    tifffile.imwrite(p, a)
    r = B.reduce_tif(p)
    assert r.shape == (250, 250) and r.dtype == np.uint16
    assert r[0, 0] == 0 and r[1, 1] == 0 and r[2, 2] != 0                     # Lücke bleibt Lücke
    assert abs(r[100, 200] / B.SCALE - B.OFFSET - 400.0) < 0.11
    assert abs((r[100, 50] / B.SCALE - B.OFFSET) - (400.0 + 0.1 * (50 * 4 + 1.5))) < 0.2


def _red_with_plane(tmp_path, e_km, n_km):
    """4-m-Raster einer Ebene h = 300 + 0,05 * (E - E0) + 0,02 * (N - N0), E/N in UTM-Metern."""
    red = tmp_path / "red"
    red.mkdir()
    have = set()
    for a in range(e_km - 1, e_km + 2):
        for b in range(n_km - 1, n_km + 2):
            c = (np.arange(250) + 0.5) * 4 + a * 1000          # Spaltenmitten (E)
            r = (b + 1) * 1000 - (np.arange(250) + 0.5) * 4    # Zeilenmitten (N)
            h = 300 + 0.05 * (c[None, :] - e_km * 1000) + 0.02 * (r[:, None] - n_km * 1000)
            np.save(red / f"{a}_{b}.npy", np.rint((h + B.OFFSET) * B.SCALE).astype(np.uint16))
            have.add((a, b))
    return red, have


def test_sample_state_trifft_die_ebene(tmp_path):
    from pyproj import Transformer
    e0, n0 = 316000, 5525000
    red, have = _red_with_plane(tmp_path, 316, 5525)
    lon, lat = Transformer.from_crs(25832, 4326, always_xy=True).transform(e0 + 500, n0 + 500)
    x, y = B.tile_xy(lon, lat, 14)
    v = B.sample_state(red, 14, x, y, have)
    assert v is not None and v.shape == (256, 256) and np.isfinite(v).all()
    lo, la = B.pixel_lonlat(14, x, y)
    e, n = Transformer.from_crs(4326, 25832, always_xy=True).transform(lo, la)
    want = 300 + 0.05 * (e - e0) + 0.02 * (n - n0)
    assert np.abs(v - want).max() < 0.25      # Quantisierung 0,1 m plus Bilinearfehler


def test_sample_state_ohne_daten_ist_none_und_luecke_ist_nan(tmp_path):
    from pyproj import Transformer
    red, have = _red_with_plane(tmp_path, 316, 5525)
    lon, lat = Transformer.from_crs(25832, 4326, always_xy=True).transform(316500, 5525500)
    x, y = B.tile_xy(lon, lat, 14)
    assert B.sample_state(red, 14, x, y, set()) is None
    (red / "316_5525.npy").write_bytes(b"")                                     # nur ein Nachbar fehlt …
    have2 = have - {(316, 5525)}
    v = B.sample_state(red, 14, x, y, have2)
    assert v is not None and np.isnan(v).any()                                  # … dann gibt es NaN statt erfundener Höhen


def test_touches():
    from pyproj import Transformer
    lon, lat = Transformer.from_crs(25832, 4326, always_xy=True).transform(316500, 5525500)
    x, y = B.tile_xy(lon, lat, 14)
    assert B.touches(14, x, y, {(316, 5525)}) and not B.touches(14, x, y, {(100, 100)})


def test_merge_children_mittelt(tmp_path):
    out, base = tmp_path / "out", tmp_path / "base"
    for dx in (0, 1):
        for dy in (0, 1):
            B.write_png(out / "13" / str(2 * 5 + dx) / f"{2 * 7 + dy}.png", np.full((256, 256), 100.0 * (1 + dx + 2 * dy), np.float32))
    m = B.merge_children(out, base, 12, 5, 7)
    assert m.shape == (256, 256)
    assert abs(m[10, 10] - 100.0) < 0.01 and abs(m[10, 250] - 200.0) < 0.01 and abs(m[250, 10] - 300.0) < 0.01 and abs(m[250, 250] - 400.0) < 0.01
    assert B.merge_children(out, base, 12, 9, 9) is None      # Zoom 13 ohne Datei und ohne Mapzen-Basis: nichts zu mitteln


def test_pixel_lonlat_mitte_der_kachel():
    lon, lat = B.pixel_lonlat(14, 8512, 5500)
    n = 2**14
    assert abs(lon[0, 0] - ((8512 + 0.5 / 256) / n * 360 - 180)) < 1e-9
    assert lat[0, 0] > lat[-1, 0] and math.isfinite(lat[0, 0])
