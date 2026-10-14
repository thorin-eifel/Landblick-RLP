import json

import numpy as np
import pytest

pytest.importorskip("skimage"); pytest.importorskip("shapely"); pytest.importorskip("mapbox_vector_tile"); pytest.importorskip("pyproj")

from tools import build_hang_rlp as hr
from tools import build_klippen_dgm as kd


def _corner_cone(tmp_path):
    """3 x 3 Kilometerkacheln (291..293 Ost, 5547..5549 Nord) mit einem 30-Grad-Kegel (Radius 150 m) genau auf der Ecke
    zwischen vier 1-km-Blöcken: bei 292000 Ost, 5548000 Nord."""
    raw = tmp_path / "raw"; raw.mkdir()
    yy, xx = np.mgrid[0:3000, 0:3000]
    r = np.hypot(xx - 1000, yy - 2000)          # Zeile 0 = Nordrand (5550000), also Nord 5548000 bei Zeile 2000
    h = 300 + np.clip(150 - r, 0, None) * np.tan(np.radians(30))
    q = np.rint((h + kd.OFFSET) * kd.SCALE).astype(np.uint16)
    for i in range(3):
        for j in range(3):
            np.savez_compressed(raw / f"{291 + i}_{5549 - j}.npz", a=q[j * 1000:(j + 1) * 1000, i * 1000:(i + 1) * 1000])
    return raw


def test_blocks_cover_present_tiles_only(tmp_path):
    raw = _corner_cone(tmp_path)
    jobs = hr.block_jobs(raw, 2, None)
    assert jobs == [(290, 5546), (290, 5548), (292, 5546), (292, 5548)]
    assert hr.block_jobs(raw, 1, None)[0] == (291, 5547) and len(hr.block_jobs(raw, 1, None)) == 9


def test_cone_on_block_corner_becomes_one_seamless_polygon(tmp_path):
    import mapbox_vector_tile as mvt
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    raw = _corner_cone(tmp_path)
    out = tmp_path / "hang"
    meta = hr.build(raw, out, 2, 1, [15, 25], 1.0, 1.5, 40.0, 14, False, None)
    assert meta["kacheln"] >= 1 and meta["bytes_gzip"] > 0 and (out / "meta.json").exists()
    assert not (tmp_path / "hang_parts").exists()                       # Teilstücke aufgeräumt
    polys = []
    for f in (out / "14").glob("*/*.pbf"):
        tx, ty = int(f.parent.name), int(f.stem)
        for layer in mvt.decode(f.read_bytes(), default_options={"y_coord_down": True}).get("ab15", {}).get("features", []):
            g = layer["geometry"]
            rings = g["coordinates"] if g["type"] == "Polygon" else [r for p in g["coordinates"] for r in p]
            for ring in (g["coordinates"] if g["type"] == "Polygon" else g["coordinates"]):
                outer = ring[0] if g["type"] == "MultiPolygon" else ring
                polys.append(Polygon([(tx + x / 4096, ty + y / 4096) for x, y in outer]).buffer(0))
            break
    u = unary_union(polys)
    parts = list(u.geoms) if hasattr(u, "geoms") else [u]
    assert len(parts) == 1, "Naht zwischen den Blöcken"
    assert json.loads((out / "meta.json").read_text())["klassen_grad"] == [15, 25]


def test_resume_skips_done_blocks(tmp_path):
    raw = _corner_cone(tmp_path)
    parts = tmp_path / "p"; (parts / "_done").mkdir(parents=True)
    (parts / "_done" / "292_5548").write_text("ok")
    assert hr.process_block((raw, 292, 5548, 1, [15], 1.0, 1.5, 40.0, 14, parts))[2] == -1
