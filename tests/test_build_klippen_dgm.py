"""Tests für tools/build_klippen_dgm.py: Wandfläche im 1-m-Höhenfeld, Oberkante, Striche in Fallrichtung, Kacheln mit Löchern."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("skimage")
pytest.importorskip("mapbox_vector_tile")
pytest.importorskip("shapely")

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_klippen_dgm", ROOT / "tools" / "build_klippen_dgm.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)


def feld(n=240):
    """Hochfläche im Norden (400 m), Tiefland im Süden (370 m), dazwischen eine Wand (Zeilen 118..127, 30 m auf 10 m)."""
    h = np.full((n, n), 400.0, np.float32)
    h[128:, :] = 370.0
    h[118:128, :] = np.linspace(400.0, 370.0, 10)[:, None]
    return h


def test_wand_wird_als_flaeche_gefunden():
    found = K.derive(feld())
    assert len(found) == 1
    w = found[0]
    assert 25 < w["drop"] < 35
    minx, miny, maxx, maxy = w["poly"].bounds
    assert maxx - minx > 200 and 5 < maxy - miny < 25
    assert 100 < (miny + maxy) / 2 < 130                    # y Nord: Zeile 123 von 240 → y ≈ 116


def test_sanfter_hang_gibt_nichts():
    h = np.tile(np.linspace(400, 300, 240, dtype=np.float32)[:, None], (1, 240))
    assert K.derive(h) == []


def test_niedrige_stufe_faellt_unter_mindesthoehe():
    h = feld()
    h = 395 + (h - 370) / 30 * 5                              # gleiche Form, nur 5 m statt 30 m → knapp unter min_drop 6
    assert K.derive(h.astype(np.float32), min_drop=6.0) == []


def test_oberkante_liegt_oben_und_wand_rechts():
    w = K.derive(feld())[0]
    assert w["kante"], "keine Oberkante"
    line = max(w["kante"], key=len)
    _, miny, _, maxy = w["poly"].bounds
    assert line[:, 1].mean() > (miny + maxy) / 2              # Norden = Oberkante
    assert line[-1, 0] > line[0, 0]                           # Laufrichtung Ost, Süden (Wand) rechts


def test_striche_laufen_bergab_nicht_quer():
    w = K.derive(feld())[0]
    s = w["schraffur"]
    assert len(s) > 50
    d = np.array([x[-1] - x[0] for x in s])
    assert (d[:, 1] < 0).mean() > 0.95                        # nach Süden
    assert np.abs(d[:, 1]).mean() > 3 * np.abs(d[:, 0]).mean()
    for x in s[:20]:
        assert w["poly"].buffer(0.01).contains(__import__("shapely").geometry.LineString(x))


def test_loch_bleibt_loch():
    h = feld()
    h[119:127, 60:120] = 385.0                                # ebene Stufe mitten in der Wand: Loch in der Steilzone
    found = K.derive(h)
    assert any(len(list(w["poly"].interiors)) >= 1 for w in found)


def test_nodata_rand_ist_keine_wand():
    h = feld()
    h[:, 150:] = np.nan
    for w in K.derive(h):
        assert w["poly"].bounds[2] < 150


def test_kacheln_mit_loechern_und_richtung(tmp_path):
    import mapbox_vector_tile as mvt
    lon0, lat0 = 7.73, 50.12
    ext = np.array([[lon0, lat0], [lon0 + 0.002, lat0], [lon0 + 0.002, lat0 + 0.001], [lon0, lat0 + 0.001], [lon0, lat0]])
    hole = np.array([[lon0 + 0.0005, lat0 + 0.0003], [lon0 + 0.0005, lat0 + 0.0007], [lon0 + 0.0015, lat0 + 0.0007],
                     [lon0 + 0.0015, lat0 + 0.0003], [lon0 + 0.0005, lat0 + 0.0003]])
    item = {"drop": 15.0, "wand": [(ext, [hole])],
            "kante": [np.array([[lon0, lat0 + 0.001], [lon0 + 0.002, lat0 + 0.001]])],
            "schraffur": [np.array([[lon0 + 0.0002, lat0 + 0.0009], [lon0 + 0.0002, lat0 + 0.00086]])]}
    n = K.write_tiles([item], tmp_path)
    assert n >= 1
    tiles = [mvt.decode(f.read_bytes()) for f in tmp_path.glob("13/*/*.pbf")]      # die Wand darf über eine Kachelgrenze reichen
    assert tiles and all(len(t) >= 1 for t in tiles)
    feats = {k: [f for t in tiles for f in t.get(k, {}).get("features", [])] for k in ("wand", "kante", "schraffur")}
    assert all(feats.values())
    # Außenring + Loch bleiben in der Kachel erhalten, in der das Loch liegt
    assert any(len(f["geometry"]["coordinates"]) == 2 for f in feats["wand"])
    k = feats["kante"][0]
    assert k["geometry"]["coordinates"][-1][0] > k["geometry"]["coordinates"][0][0]     # Richtung Ost bleibt erhalten
    assert k["properties"]["drop"] == 15.0


def test_tif_wird_auf_1000_gekappt_und_nodata_erkannt():
    tifffile = pytest.importorskip("tifffile")
    import io
    a = np.full((1001, 1001), 250.0, np.float32)
    a[:10, :10] = -9999
    b = io.BytesIO()
    tifffile.imwrite(b, a)
    q = K.tif_to_u16(b.getvalue())
    assert q.shape == (1000, 1000) and q[0, 0] == 0 and abs(q[500, 500] / K.SCALE - K.OFFSET - 250.0) < 0.02


def test_rohkacheln_npz_und_npy_werden_gelesen(tmp_path):
    a = np.full((1000, 1000), int((300 + K.OFFSET) * K.SCALE), np.uint16)
    np.savez_compressed(tmp_path / "100_5500.npz", a=a)
    np.save(tmp_path / "101_5500.npy", a)
    h = K.load_block(tmp_path, 100, 5500, 102, 5500)
    assert h.shape == (1000, 3000)
    assert abs(float(h[0, 10]) - 300) < 0.02 and abs(float(h[0, 1500]) - 300) < 0.02 and np.isnan(h[0, 2500])
