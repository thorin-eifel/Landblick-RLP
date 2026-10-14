import json

import numpy as np
import pytest

pytest.importorskip("skimage"); pytest.importorskip("shapely"); pytest.importorskip("mapbox_vector_tile"); pytest.importorskip("pyproj")

from tools import build_hang_probe as hp
from tools import build_klippen_dgm as kd


def _cone_raw(tmp_path):
    """3 x 3 Kilometerkacheln um (292,5548) mit einem Kegel von 30 Grad Neigung in der Mitte, sonst eben."""
    raw = tmp_path / "raw"; raw.mkdir()
    yy, xx = np.mgrid[0:3000, 0:3000]
    r = np.hypot(xx - 1500, yy - 1500)
    h = 300 + np.clip(150 - r, 0, None) * np.tan(np.radians(30))
    q = np.rint((h + kd.OFFSET) * kd.SCALE).astype(np.uint16)
    for i in range(3):
        for j in range(3):
            np.savez_compressed(raw / f"{291 + i}_{5549 - j}.npz", a=q[j * 1000:(j + 1) * 1000, i * 1000:(i + 1) * 1000])
    return raw


def test_slope_of_cone_is_30_degrees(tmp_path):
    raw = _cone_raw(tmp_path)
    h = kd.load_block(raw, 291, 5547, 293, 5549)
    s = hp.slope_deg(h, 1.0)
    assert abs(float(s[1500, 1500 + 80]) - 30.0) < 1.0
    assert float(s[100, 100]) < 0.5


def test_build_reports_classes_and_writes_tiles(tmp_path):
    from pyproj import Transformer
    raw = _cone_raw(tmp_path)
    lon, lat = Transformer.from_crs(kd.CRS_UTM, "EPSG:4326", always_xy=True).transform(292500, 5548500)
    st = hp.build(raw, (lon, lat), 1.0, [15, 25, 35], 1.0, 1.5, 40.0, 14, tmp_path / "out")
    k = st["klassen"]
    assert k["ab15"]["flaechen"] >= 1 and k["ab25"]["flaechen"] >= 1       # Kegelmantel hat 30 Grad
    assert k["ab35"]["flaechen"] == 0                                      # nichts steiler
    assert st["kacheln"] >= 1 and st["bytes_gzip"] > 0 and st["hochrechnung_rlp_mb_gzip"] > 0
    assert json.loads((tmp_path / "out" / "stats.json").read_text())["km2"] == 4          # Mitte auf Kachelgrenze: auf ganze Kilometerkacheln aufgerundet
    assert list((tmp_path / "out" / "14").glob("*/*.pbf"))


def test_build_without_raw_tiles_exits(tmp_path):
    (tmp_path / "raw").mkdir()
    with pytest.raises(SystemExit):
        hp.build(tmp_path / "raw", (6.45, 49.85), 1.0, [15], 1.0, 1.5, 40.0, 14, tmp_path / "o")
