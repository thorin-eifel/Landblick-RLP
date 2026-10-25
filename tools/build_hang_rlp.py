#!/usr/bin/env python3
"""Hangneigungsklassen für ganz Rheinland-Pfalz aus dem Landes-DGM1 (1 m) als Vektorkacheln Zoom 14 bauen.

Zweck:      Die Karte zeigt neben Schummerung und Felswänden die Hangneigung als durchscheinende Flächen (ab 15, 25, 35 Grad).
            tools/build_hang_probe.py misst das an einem Ausschnitt; dieses Werkzeug rechnet das ganze Land in Blöcken, parallel,
            wiederaufnehmbar. Ergebnis sind Kacheln <out>/14/<x>/<y>.pbf (Ebenen ab15, ab25, ab35) und <out>/meta.json.
Quelle:     Rohkacheln aus tools/build_klippen_dgm.py (work/raw, uint16-npz). Landes-DGM1 RLP, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0
            (Daten bearbeitet).
Ablauf:     1. Blöcke von --block-km (Standard 4) über alle vorhandenen Rohkacheln, je Block +1 km Rand zum Glätten
            2. je Block: Neigung, Klassenmasken, Umrisse, Zuschnitt an die Zoom-14-Kacheln, Teilstück nach <out>_parts/<x>_<y>/<block>.pkl
               (Masken reichen 1 m über den Blockrand, damit benachbarte Blöcke sich überlappen und keine Naht bleibt)
            3. je Kachel: Teilstücke je Klasse vereinigen, an die Kachel beschneiden, als MVT schreiben
            Schritt 2 ist wiederaufnehmbar (fertige Blöcke tragen eine Marke in <out>_parts/_done).
Aufruf:     python tools/build_hang_rlp.py --raw _scratch/dgm1/raw --out web/tiles/hang --workers 6
            python tools/build_hang_rlp.py ... --bbox 6.3 49.7 6.6 49.95        Ausschnitt in Grad (Länge, Breite, Länge, Breite)
Parameter:  --raw DIR --out DIR --workers N (Standard: Kerne minus 2) --block-km N --classes 15 25 35 --sigma 1.0 --simplify 1.5
            --min-area 40 --zoom 14 --keep-parts (Teilstücke behalten) --bbox LON0 LAT0 LON1 LAT1
Speicher:   je Arbeiter rund 1 GB bei 4-km-Blöcken. Platz: Teilstücke kurzzeitig etwa so groß wie das Ergebnis.
Exit:       0 fertig, 1 Fehler (keine Rohkacheln)
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import math
import os
import pickle
import shutil
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # Aufruf als Skript: Projektwurzel auffindbar machen
from tools import build_hang_probe as hp  # noqa: E402
from tools import build_klippen_dgm as kd  # noqa: E402

log = logging.getLogger("landblick.hang_rlp")
EXTENT = 4096
PAD = 64 / EXTENT
ATTRIBUTION = "© GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 (Daten bearbeitet)"
_TR = None


def to_merc(x: np.ndarray, y: np.ndarray, z: int) -> tuple[np.ndarray, np.ndarray]:
    """UTM 32N (m) → Kachelkoordinaten (Bruchteile) bei Zoom z; Transformer je Prozess nur einmal."""
    global _TR
    if _TR is None:
        from pyproj import Transformer
        _TR = Transformer.from_crs(kd.CRS_UTM, "EPSG:4326", always_xy=True)
    lon, lat = _TR.transform(x, y)
    return kd.merc(np.asarray(lon), np.asarray(lat), z)


def block_jobs(raw: Path, block_km: int, bbox_utm: tuple[float, float, float, float] | None) -> list[tuple[int, int]]:
    """Blockursprünge (Ost km, Nord km) aller Blöcke, die mindestens eine Rohkachel enthalten (und in bbox liegen)."""
    keys = set()
    for p in raw.iterdir():
        stem = p.stem
        if p.suffix not in (".npz", ".npy") or "_" not in stem:
            continue
        try:
            e, n = (int(v) for v in stem.split("_"))
        except ValueError:
            continue
        if bbox_utm and not (bbox_utm[0] - 1000 <= e * 1000 <= bbox_utm[2] and bbox_utm[1] - 1000 <= n * 1000 <= bbox_utm[3]):
            continue
        keys.add((e // block_km * block_km, n // block_km * block_km))
    return sorted(keys)


def process_block(a: tuple) -> tuple[int, int, int]:
    """Ein Block: schreibt Teilstücke je Kachel. Rückgabe (e0, n0, Zahl Kacheln mit Inhalt)."""
    from shapely.geometry import Polygon, box
    from shapely import wkb
    raw, e0, n0, bk, classes, sigma, simplify, min_area, zoom, parts = a
    done = parts / "_done" / f"{e0}_{n0}"
    if done.exists():
        return e0, n0, -1
    h = kd.load_block(raw, e0 - 1, n0 - 1, e0 + bk, n0 + bk)
    rows = h.shape[0]
    s = hp.slope_deg(h, sigma)
    lo, hi = 1000 - 1, 1000 + bk * 1000 + 1
    ox, oy = (e0 - 1) * 1000.0, (n0 - 1) * 1000.0
    buckets: dict[tuple[int, int], dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for thr in classes:
        m = hp.class_mask(s, thr, min_area)
        m[:lo] = False
        m[hi:] = False
        m[:, :lo] = False
        m[:, hi:] = False
        if not m.any():
            continue
        name = f"ab{int(thr) if float(thr).is_integer() else thr}"
        for ext, holes in kd._rings(m, 0, 0, rows, simplify):
            def pr(coords):
                c = np.asarray(coords, float)
                tx, ty = to_merc(c[:, 0] + ox, c[:, 1] + oy, zoom)
                return np.stack([tx, ty], 1)
            g = Polygon(pr(ext.exterior.coords), [pr(hc) for hc in holes])
            if not g.is_valid:
                g = g.buffer(0)
            x0, y0, x1, y1 = g.bounds
            for tx in range(int(math.floor(x0)), int(math.floor(x1)) + 1):
                for ty in range(int(math.floor(y0)), int(math.floor(y1)) + 1):
                    c = g.intersection(box(tx - PAD, ty - PAD, tx + 1 + PAD, ty + 1 + PAD))
                    if not c.is_empty:
                        buckets[(tx, ty)][name].append(wkb.dumps(c))
    for (tx, ty), layers in buckets.items():
        d = parts / f"{tx}_{ty}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{e0}_{n0}.pkl").write_bytes(pickle.dumps(dict(layers)))
    done.parent.mkdir(parents=True, exist_ok=True)
    done.write_text("ok\n")
    return e0, n0, len(buckets)


def finish_tile(a: tuple) -> tuple[int, int, int, dict[str, int]]:
    """Eine Kachel: Teilstücke vereinigen, zuschneiden, als MVT schreiben. Rückgabe (tx, ty, Bytes gzip, Bytes je Klasse)."""
    from shapely import wkb
    from shapely.affinity import affine_transform
    from shapely.geometry import box
    from shapely.ops import unary_union
    import mapbox_vector_tile as mvt
    tdir, out, zoom = a
    tx, ty = (int(v) for v in tdir.name.split("_"))
    per: dict[str, list] = defaultdict(list)
    for f in sorted(tdir.glob("*.pkl")):
        for name, items in pickle.loads(f.read_bytes()).items():
            per[name].extend(wkb.loads(b) for b in items)
    win = box(tx - PAD, ty - PAD, tx + 1 + PAD, ty + 1 + PAD)
    mat = [EXTENT, 0, 0, EXTENT, -tx * EXTENT, -ty * EXTENT]
    layers = []
    sizes: dict[str, int] = {}
    for name in sorted(per):
        u = unary_union(per[name]).intersection(win)
        feats = [{"geometry": affine_transform(p, mat), "properties": {}}
                 for p in (list(u.geoms) if hasattr(u, "geoms") else [u]) if not p.is_empty and p.geom_type == "Polygon"]
        if feats:
            layers.append({"name": name, "features": feats})
            sizes[name] = len(gzip.compress(mvt.encode([layers[-1]], default_options={"extents": EXTENT, "y_coord_down": True}), 6))
    if not layers:
        return tx, ty, 0, {}
    data = mvt.encode(layers, default_options={"extents": EXTENT, "y_coord_down": True})
    d = out / str(zoom) / str(tx)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{ty}.pbf").write_bytes(data)
    return tx, ty, len(gzip.compress(data, 6)), sizes


def build(raw: Path, out: Path, workers: int, block_km: int, classes: list[float], sigma: float, simplify: float,
          min_area: float, zoom: int, keep_parts: bool, bbox: tuple[float, float, float, float] | None) -> dict:
    bbox_utm = None
    if bbox:
        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", kd.CRS_UTM, always_xy=True)
        x0, y0 = t.transform(bbox[0], bbox[1])
        x1, y1 = t.transform(bbox[2], bbox[3])
        bbox_utm = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    jobs = block_jobs(raw, block_km, bbox_utm)
    if not jobs:
        log.error("Keine Rohkacheln unter %s", raw)
        raise SystemExit(1)
    parts = out.parent / (out.name + "_parts")
    parts.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log.info("%d Blöcke à %d km, %d Arbeiter", len(jobs), block_km, workers)
    args = [(raw, e, n, block_km, classes, sigma, simplify, min_area, zoom, parts) for e, n in jobs]
    with ProcessPoolExecutor(workers) as ex:
        for i, (e, n, k) in enumerate(ex.map(process_block, args, chunksize=1), 1):
            if i % 20 == 0 or i == len(jobs):
                el = time.time() - t0
                log.info("Blöcke %d/%d, vergangen %.0f min, Rest ca. %.0f min", i, len(jobs), el / 60, el / i * (len(jobs) - i) / 60)
        tiles = [d for d in parts.iterdir() if d.is_dir() and not d.name.startswith("_")]
        log.info("Kacheln zusammenführen: %d", len(tiles))
        total = 0
        per_class: dict[str, int] = defaultdict(int)
        ntiles = 0
        for tx, ty, nbytes, sizes in ex.map(finish_tile, [(d, out, zoom) for d in tiles], chunksize=8):
            if nbytes:
                ntiles += 1
                total += nbytes
                for k, v in sizes.items():
                    per_class[k] += v
    meta = {"name": "Hangneigung", "attribution": ATTRIBUTION, "minzoom": zoom, "maxzoom": zoom, "zoom": zoom,
            "klassen_grad": classes, "sigma_m": sigma, "simplify_m": simplify, "min_area_m2": min_area, "kacheln": ntiles,
            "bytes_gzip": total, "bytes_gzip_je_klasse": dict(per_class), "bloecke": len(jobs),
            "gebaut_am": time.strftime("%Y-%m-%d"), "minuten": round((time.time() - t0) / 60, 1)}
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not keep_parts:
        shutil.rmtree(parts, ignore_errors=True)
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--block-km", type=int, default=4)
    ap.add_argument("--classes", type=float, nargs="+", default=[15.0, 25.0, 35.0])
    ap.add_argument("--sigma", type=float, default=1.0)
    ap.add_argument("--simplify", type=float, default=1.5)
    ap.add_argument("--min-area", type=float, default=40.0)
    ap.add_argument("--zoom", type=int, default=14)
    ap.add_argument("--keep-parts", action="store_true")
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("LON0", "LAT0", "LON1", "LAT1"))
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not (1 <= a.block_km <= 8) or a.classes != sorted(a.classes) or not (0 < a.zoom <= 17) or a.workers < 1:
        log.error("Ungültige Parameter")
        return 1
    meta = build(a.raw, a.out, a.workers, a.block_km, a.classes, a.sigma, a.simplify, a.min_area, a.zoom, a.keep_parts,
                 tuple(a.bbox) if a.bbox else None)
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
