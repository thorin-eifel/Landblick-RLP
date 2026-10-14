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


def test_reduce_tif_nimmt_1001er_kacheln(tmp_path):
    import tifffile
    a = np.full((1001, 1001), 400.0, np.float32)
    p = tmp_path / "k.tif"
    tifffile.imwrite(p, a)
    assert B.reduce_tif(p).shape == (250, 250)
    tifffile.imwrite(p, np.full((999, 999), 400.0, np.float32))
    with pytest.raises(ValueError):
        B.reduce_tif(p)


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


def _base_rampe(tmp_path, bx, by, k=2.0):
    """Mapzen-Zoom-12-Kacheln (3 x 3 um bx, by) mit linearer Rampe: k Meter je Basispixel nach Osten und Süden."""
    jj, ii = np.mgrid[0:256, 0:256]
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            h = 300 + k * (dx * 256 + ii + 0.5) + k * (dy * 256 + jj + 0.5)
            B.write_png(tmp_path / "12" / str(bx + dx) / f"{by + dy}.png", h.astype(np.float32))


def test_upsample_base_schliesst_an_der_kachelgrenze_ohne_stufe(tmp_path):
    """Zwei Zoom-14-Nachbarn unter verschiedenen Zoom-12-Kacheln: ein Pixel Abstand, kein Sprung (sonst Linie in der Schummerung)."""
    bx, by, k = 2100, 1400, 2.0
    _base_rampe(tmp_path, bx, by, k)
    x = 4 * bx + 3                                         # letzte Spalte unter der Basiskachel
    a = B.upsample_base(tmp_path, 14, x, 4 * by + 1)
    b = B.upsample_base(tmp_path, 14, x + 1, 4 * by + 1)   # erste Spalte unter der Nachbarkachel
    step = b[:, 0] - a[:, -1]
    assert np.allclose(step, k / 4, atol=0.02), step[:3]    # ein Zoom-14-Pixel = ein Viertel Basispixel
    want = 300 + k * (192.125) + k * (64.125)               # Pixel (0, 0) von a: Mitte bei 192,125 Basispixeln nach Osten, 64,125 nach Süden
    assert abs(float(a[0, 0]) - want) < 0.05


def test_upsample_base_ohne_nachbarn_und_ohne_basis(tmp_path):
    B.write_png(tmp_path / "12" / "10" / "10.png", np.full((256, 256), 150.0, np.float32))
    f = B.upsample_base(tmp_path, 13, 20, 20)
    assert f is not None and not np.isnan(f).any() and abs(float(f.mean()) - 150) < 0.05
    assert B.upsample_base(tmp_path, 13, 2, 2) is None


def test_fetch_one_legt_rohkachel_im_klippen_format_ab(tmp_path):
    """--keep-raw: eine Datei laden, 4-m-Kachel und 1-m-Rohkachel (uint16, Maßstab 50) schreiben; ohne raw_dir keine Rohkachel."""
    import hashlib
    import io

    import tifffile
    h = np.full((1000, 1000), 300.0, np.float32)
    h[0, 0] = -9999.0
    buf = io.BytesIO()
    tifffile.imwrite(buf, h)
    content = buf.getvalue()

    class Antwort:
        status_code = 200

    Antwort.content = content

    class Client:
        def get(self, url):
            return Antwort()

    item = {"e": 337, "n": 5553, "url": "https://geobasis-rlp.de/x.tif", "sha": hashlib.sha256(content).hexdigest(), "name": "x.tif"}
    red, raw = tmp_path / "red", tmp_path / "raw"
    red.mkdir()
    raw.mkdir()
    assert B.fetch_one(Client(), item, red, raw) == "ok"
    r = np.load(raw / "337_5553.npz")["a"]
    assert r.shape == (1000, 1000) and r.dtype == np.uint16
    assert r[500, 500] == round((300.0 + B.OFFSET) * B.RAW_SCALE) and r[0, 0] == 0
    assert np.load(red / "337_5553.npy").shape == (250, 250)
    red2 = tmp_path / "red2"
    red2.mkdir()
    assert B.fetch_one(Client(), item, red2) == "ok" and not list(raw.glob(".*")) and len(list(raw.glob("*.npz"))) == 1


def test_rohkachel_format_gleich_klippen():
    """RAW_SCALE und OFFSET müssen mit tools/build_klippen_dgm.py übereinstimmen (sonst lesen die Felswände falsche Höhen)."""
    import re
    src = (ROOT / "tools" / "build_klippen_dgm.py").read_text()
    m = re.search(r"^OFFSET, SCALE = ([\d.]+), ([\d.]+)", src, re.M)
    assert (float(m.group(1)), float(m.group(2))) == (B.OFFSET, B.RAW_SCALE)


# ---------------------------------------------------------------- Ausgleich am Rand der Landesdaten
def test_blend_bias_ohne_stufe_am_rand():
    """Landesdaten links (100 m), Mapzen überall 90 m: am Rand keine Stufe, nach FADE_PX Pixeln wieder Mapzen."""
    fade = 40
    st = np.full((64, 200), np.nan, np.float32)
    st[:, :100] = 100.0
    fb = np.full((64, 200), 90.0, np.float32)
    out = B.blend_bias(st, fb, fade)
    assert np.allclose(out[:, :100], 100.0)                                     # Landesdaten bleiben unverändert
    assert abs(float(out[32, 100]) - 100.0) < 0.6                               # erster Pixel außen: kaum Stufe (< 0,6 statt 10 m)
    assert np.abs(np.diff(out[32, 99:150])).max() < 0.5                         # Übergang ohne Sprung
    assert np.allclose(out[:, 100 + fade:], 90.0)                               # danach wieder reines Mapzen
    assert np.all(np.diff(out[32, 100:100 + fade]) <= 1e-4)                     # monoton fallend


def test_blend_bias_unveraendert_ohne_rand():
    fb = np.full((32, 32), 5.0, np.float32)
    assert np.allclose(B.blend_bias(np.full((32, 32), 7.0, np.float32), fb, 10), 7.0)           # alles Landesdaten
    assert np.allclose(B.blend_bias(np.full((32, 32), np.nan, np.float32), fb, 10), 5.0)        # nichts Landesdaten


def test_blend_bias_kacheln_schliessen_aneinander_an():
    """Zwei Kacheln mit Rand, gerechnet aus demselben Gelände: an der gemeinsamen Kante kein Sprung."""
    fade, T = 30, 64
    rng = np.random.default_rng(1)
    world_st = np.full((T + 2 * fade, 2 * T + 2 * fade), np.nan, np.float32)
    world_st[:, : T + fade + 10] = 200 + rng.normal(0, 3, (T + 2 * fade, T + fade + 10)).cumsum(axis=1) * 0.1
    world_fb = (180 + 0.05 * np.arange(world_st.shape[1]))[None, :].repeat(world_st.shape[0], 0).astype(np.float32)
    full = B.blend_bias(world_st, world_fb, fade)
    a = B.blend_bias(world_st[:, : T + 2 * fade], world_fb[:, : T + 2 * fade], fade)[:, fade:fade + T]
    b = B.blend_bias(world_st[:, T: 2 * T + 2 * fade], world_fb[:, T: 2 * T + 2 * fade], fade)[:, fade:fade + T]
    assert np.abs(a - full[:, fade:fade + T]).max() < 0.35
    assert np.abs(b - full[:, fade + T:fade + 2 * T]).max() < 0.35
    assert abs(float(b[30, 0]) - float(a[30, -1])) < 0.6                         # gemeinsame Kante (ein Pixel Abstand)


def test_sample_state_und_upsample_mit_rand(tmp_path):
    from pyproj import Transformer
    red, have = _red_with_plane(tmp_path, 316, 5525)
    lon, lat = Transformer.from_crs(25832, 4326, always_xy=True).transform(316500, 5525500)
    x, y = B.tile_xy(lon, lat, 14)
    v = B.sample_state(red, 14, x, y, have, margin=20)
    assert v.shape == (296, 296)
    assert np.array_equal(B.sample_state(red, 14, x, y, have)[:, :], v[20:276, 20:276], equal_nan=True)
    lo, la = B.pixel_lonlat(14, x, y, margin=20)
    assert lo.shape == (296, 296) and lo[0, 20] == B.pixel_lonlat(14, x, y)[0][0, 0]
    _base_rampe(tmp_path, 2100, 1400, 2.0)
    f = B.upsample_base(tmp_path, 14, 4 * 2100 + 1, 4 * 1400 + 1, margin=20)
    assert f.shape == (296, 296)
    assert np.allclose(f[20:276, 20:276], B.upsample_base(tmp_path, 14, 4 * 2100 + 1, 4 * 1400 + 1))


def test_build_top_gleicht_die_stufe_am_rand_aus(tmp_path):
    """Landesdaten (Ebene bei 300 m) treffen auf Mapzen mit 20 m Versatz: am Rand der Daten springt das Ergebnis nicht."""
    from pyproj import Transformer
    red, have = _red_with_plane(tmp_path, 316, 5525)
    lon, lat = Transformer.from_crs(25832, 4326, always_xy=True).transform(316500, 5525500)
    x, y = B.tile_xy(lon, lat, 14)
    base = tmp_path / "base"
    for bx in range(x // 4 - 1, x // 4 + 2):
        for by in range(y // 4 - 1, y // 4 + 2):
            B.write_png(base / "12" / str(bx) / f"{by}.png", np.full((256, 256), 280.0, np.float32))
    out = tmp_path / "out"
    kinds = {}
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            kinds[(dx, dy)] = B.build_top((x + dx, y + dy, str(red), str(base), str(out), have, True, False))[2]
    assert kinds[(0, 0)] in ("state", "edge")
    a = B.read_png(out / "14" / str(x) / f"{y}.png")
    assert a is not None and np.isfinite(a).all()
