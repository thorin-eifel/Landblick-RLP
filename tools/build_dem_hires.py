#!/usr/bin/env python3
"""Hochauflösende Höhenkacheln (Zoom 15 und 16) direkt aus dem 1-m-DGM1 bauen, Terrarium-Kodierung.

Zweck:      build_dem_rlp.py endet bei Zoom 14 (4-m-Raster, rund 6 m je Pixel). Dieses Werkzeug setzt darüber
            Zoom 15 (ca. 3,1 m je Pixel) und Zoom 16 (ca. 1,5 m je Pixel) aus den 1-m-Rohkacheln auf, die
            build_klippen_dgm.py in dgm1-work/raw/ ablegt. relief.js liest sie wie die übrigen Höhenkacheln.
Quelle:     Landesamt für Vermessung und Geobasisinformation RLP, DGM1, dl-de/by-2-0 [Daten bearbeitet]
            (Vermerk steht schon in tiles/dem/meta.json).
Ablauf:     Je Zielkachel die Pixelmitten nach UTM 32 (EPSG:25832) umrechnen, bilinear im 1-m-Gitter abtasten.
            Pixel ohne Landesdaten (Rand, Lücken) kommen aus der Elternkachel (Zoom 14 bzw. 15), sofern vorhanden.
            Kacheln ohne einen einzigen Landespixel werden nicht geschrieben.
Aufruf:     python tools/build_dem_hires.py --raw dgm1-work/raw --out web/tiles/dem --bbox 7.05 50.10 7.20 50.18
            python tools/build_dem_hires.py ... --zooms 15 --quant 16       # nur Zoom 15, Höhe auf 1/16 m runden
            python tools/build_dem_hires.py ... --measure                  # nichts schreiben, Größe hochrechnen
Exit:       0 = fertig, 1 = Fehler (z. B. keine Rohkacheln im Ausschnitt)
"""
from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_dem_rlp import encode_terrarium, pixel_lonlat, read_png, tile_xy  # noqa: E402

log = logging.getLogger("dem_hires")
OFFSET, SCALE = 200.0, 50.0       # Rohkacheln: uint16 = (h + 200) * 50, 0 = keine Daten
KM = 1000


def read_raw(raw: Path, e: int, n: int) -> np.ndarray | None:
    """Eine Rohkachel (1000 x 1000, Zeile 0 = Nord) als float32 mit NaN für keine Daten; None, wenn es sie nicht gibt."""
    for f in (raw / f"{e}_{n}.npz", raw / f"{e}_{n}.npy"):
        if f.exists():
            a = np.load(f)["a"] if f.suffix == ".npz" else np.load(f)
            h = a.astype(np.float32) / SCALE - OFFSET
            h[a == 0] = np.nan
            return h
    return None


def sample(raw: Path, lon: np.ndarray, lat: np.ndarray, cache: dict) -> np.ndarray:
    """Bilinear aus dem 1-m-Gitter abtasten; NaN, wo keine Landesdaten liegen."""
    from pyproj import Transformer
    from scipy.ndimage import map_coordinates
    tr = Transformer.from_crs(4326, 25832, always_xy=True)
    x, y = tr.transform(lon, lat)
    e0, e1 = int(x.min() // KM), int(x.max() // KM)
    n0, n1 = int(y.min() // KM), int(y.max() // KM)
    rows = []
    for n in range(n1, n0 - 1, -1):                       # Norden oben
        row = []
        for e in range(e0, e1 + 1):
            key = (e, n)
            if key not in cache:
                if len(cache) > 24:
                    cache.pop(next(iter(cache)))
                cache[key] = read_raw(raw, e, n)
            t = cache[key]
            row.append(t if t is not None else np.full((KM, KM), np.nan, np.float32))
        rows.append(np.concatenate(row, axis=1))
    if not rows:
        return np.full(lon.shape, np.nan, np.float32)
    m = np.concatenate(rows, axis=0)
    if np.isnan(m).all():
        return np.full(lon.shape, np.nan, np.float32)
    col = x - e0 * KM - 0.5                               # Pixelmitte der Rohzelle liegt bei +0,5 m
    row_ = (n1 + 1) * KM - y - 0.5
    bad = np.isnan(m)
    out = map_coordinates(np.where(bad, 0, m), [row_, col], order=1, mode="nearest", prefilter=False)
    # Zellen, die an Lücken grenzen, nicht mit Nullen mischen: NaN-Maske mit abtasten
    mask = map_coordinates(bad.astype(np.float32), [row_, col], order=1, mode="nearest", prefilter=False)
    out = out.astype(np.float32)
    out[mask > 0.001] = np.nan
    return out


def parent_fill(out: Path, z: int, x: int, y: int, shape: int = 256) -> np.ndarray | None:
    """Elternkachel hochrechnen (bilinear) auf die Auflösung von (z, x, y); None, wenn es sie nicht gibt."""
    from scipy.ndimage import zoom
    p = read_png(out / str(z - 1) / str(x // 2) / f"{y // 2}.png")
    if p is None:
        return None
    big = zoom(p, 2, order=1)                             # 512 x 512, davon der Viertelausschnitt dieser Kachel
    r, c = (y % 2) * shape, (x % 2) * shape
    return big[r:r + shape, c:c + shape]


def quantize(h: np.ndarray, quant: int) -> np.ndarray:
    """Höhe auf 1/quant m runden – senkt das Rauschen im B-Kanal, PNG wird deutlich kleiner."""
    return np.round(h * quant) / quant


def write_tile(path: Path, h: np.ndarray) -> int:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    Image.fromarray(encode_terrarium(h), "RGB").save(tmp, format="PNG", compress_level=9)
    tmp.replace(path)
    return path.stat().st_size


def work(job: tuple) -> tuple[int, int, int, int]:
    """(z, x, y) → (z, 1 = geschrieben, Bytes, Pixel mit Landesdaten)."""
    raw, out, z, x, y, quant, measure, cover = job
    raw, out = Path(raw), Path(out)
    cache = _CACHE
    lon, lat = pixel_lonlat(z, x, y)
    h = sample(raw, lon, lat, cache)
    ok = ~np.isnan(h)
    if not ok.any():
        if not cover:
            return z, 0, 0, 0
        fill = parent_fill(out, z, x, y)                  # außerhalb des Landes: nur hochgerechnete Elternkachel, damit kein Loch entsteht
        if fill is None:
            return z, 0, 0, 0
        return z, 1, write_tile(out / str(z) / str(x) / f"{y}.png", quantize(fill, quant)) if not measure else 0, 0
    if not ok.all():
        fill = parent_fill(out, z, x, y)
        if fill is None:
            from scipy.ndimage import distance_transform_edt
            idx = distance_transform_edt(~ok, return_distances=False, return_indices=True)
            fill = h[tuple(idx)]
        h = np.where(ok, h, fill)
    h = quantize(h, quant)
    if measure:
        from io import BytesIO
        from PIL import Image
        b = BytesIO()
        Image.fromarray(encode_terrarium(h), "RGB").save(b, format="PNG", compress_level=9)
        return z, 1, b.tell(), int(ok.sum())
    return z, 1, write_tile(out / str(z) / str(x) / f"{y}.png", h), int(ok.sum())


_CACHE: dict = {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", required=True, type=Path, help="Ordner mit {e}_{n}.npz (1-m-Rohkacheln)")
    ap.add_argument("--out", required=True, type=Path, help="Kachelordner (Zoom 14 muss dort liegen)")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"), required=True)
    ap.add_argument("--zooms", nargs="+", type=int, default=[15, 16])
    ap.add_argument("--quant", type=int, default=16, help="Höhe auf 1/quant m runden (Standard 16 = 6 cm)")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--cover", action="store_true",
                    help="auch Kacheln ohne Landesdaten schreiben (aus der Elternkachel hochgerechnet), damit relief.js dort nicht ins Leere fragt")
    ap.add_argument("--measure", action="store_true", help="nur messen, nichts schreiben")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not a.raw.is_dir():
        log.error("Rohordner fehlt: %s", a.raw)
        return 1
    w, s, e, n = a.bbox
    t0 = time.time()
    for z in sorted(a.zooms):
        x0, y1 = tile_xy(w, s, z)
        x1, y0 = tile_xy(e, n, z)
        jobs = [(str(a.raw), str(a.out), z, x, y, a.quant, a.measure, a.cover)
                for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
        log.info("Zoom %d: %d Kacheln im Ausschnitt", z, len(jobs))
        with ProcessPoolExecutor(a.jobs) as ex:
            res = list(ex.map(work, jobs, chunksize=4))
        k = [r for r in res if r[1]]
        size = sum(r[2] for r in k)
        land = sum(r[3] for r in k) / (256 * 256) if k else 0
        log.info("Zoom %d: %d Kacheln %s, %.1f MB, %.1f KB je Kachel, %.1f Kachelflächen mit Landesdaten",
                 z, len(k), "gemessen" if a.measure else "geschrieben", size / 1e6, size / max(len(k), 1) / 1e3, land)
    log.info("fertig in %.0f s", time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
