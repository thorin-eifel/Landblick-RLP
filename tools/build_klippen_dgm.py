#!/usr/bin/env python3
"""Felswände aus dem Landes-DGM1 (1 m) ableiten und als Vektorkacheln (Zoom 13) ablegen.

Zweck:      Die Klippen der Basiskarte stammen aus OpenStreetMap und sind lückenhaft und grob. Das 1-m-Gelände kennt
            jede Steilwand. Eine Wand ist hier eine Fläche, keine Linie: breite, zerklüftete Felsen (Loreley) lassen sich
            nicht auf eine Mittellinie ausdünnen. Je Wand entstehen drei Ebenen:
              wand       Fläche der Steilzone (Polygon, Löcher bleiben), Attribut drop = Wandhöhe in m
              kante      Oberkante, Laufrichtung so, dass die Wand rechts der Linie liegt, Attribut drop
              schraffur  kurze Striche in Fallrichtung (von oben nach unten, nicht quer zum Hang)
Quelle:     Landes-DGM1 RLP, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 (Daten bearbeitet), 1 m, Rohkacheln von
            https://geobasis-rlp.de/data/dgm1/current/ . Standard: nur Kacheln laden, in denen das 4-m-Raster
            (work/red, siehe tools/build_dem_rlp.py) Steilhänge zeigt, plus Nachbarn; mit --all-tiles das ganze Land (rund 32 GB).
Ablauf:     1. Kandidatenkacheln aus dem 4-m-Raster wählen (Neigung >= --cand-slope), Nachbarn dazu
            2. fehlende Rohkacheln laden (Prüfsumme aus der Dateiliste), als komprimiertes uint16 (.npz) in work/raw/ ablegen (wieder aufnehmbar)
            3. Blöcke von --chunk km (+ 1 km Rand): glätten, Neigung, Steilmaske mit Hysterese, Löcher füllen, öffnen,
               kleine Flächen verwerfen, Umriss als Polygon, Oberkante, Striche entlang des Gefälles
            4. Kacheln Zoom 13 (MVT) nach <out>/13/<x>/<y>.pbf, dazu meta.json
Aufruf:     python tools/build_klippen_dgm.py --work ~/Claude/OSINT/dgm1-work --out perf-rlp/tiles/klippen
            python tools/build_klippen_dgm.py --work ... --out ... --bbox 7.70 50.10 7.76 50.14      Ausschnitt (Loreley)
            python tools/build_klippen_dgm.py --work ... --out ... --all-tiles                       ganz Rheinland-Pfalz
            python tools/build_klippen_dgm.py --work ... --out ... --no-fetch                        nur was schon da ist
Exit:       0 = fertig, 1 = Fehler / keine Kacheln
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import logging
import math
import os
import sys
import time
import warnings
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np

log = logging.getLogger("osint.klippen")
warnings.filterwarnings("ignore", category=FutureWarning)      # scikit-image 0.26 kündigt Parameternamen an, die bis 0.28 gelten

RES = 1.0                     # Rasterweite der Rohkacheln in m
OFFSET, SCALE = 200.0, 50.0   # uint16 = (h + 200) * 50 (2 cm), 0 = keine Daten
TILE_Z = 13
EXTENT = 4096
CRS_UTM = "EPSG:25832"
RED_CELL = 250                # Zellen je km im 4-m-Raster


# ------------------------------------------------------------------ Rohkacheln laden
def _dem_module():
    spec = importlib.util.spec_from_file_location("build_dem_rlp", Path(__file__).with_name("build_dem_rlp.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tif_to_u16(content: bytes) -> np.ndarray:
    """GeoTIFF-Bytes (1000 x 1000 oder 1001 x 1001, Float32, -9999 = keine Daten) → uint16 (1000 x 1000), 0 = keine Daten."""
    import tifffile
    a = tifffile.imread(io.BytesIO(content)).astype(np.float32)
    if a.shape == (1001, 1001):
        a = a[:1000, :1000]
    if a.shape != (1000, 1000):
        raise ValueError(f"unerwartete Größe {a.shape}")
    bad = (a <= -9000) | ~np.isfinite(a)
    q = np.rint((np.where(bad, 0, a) + OFFSET) * SCALE)
    q[bad | (q < 1)] = 0
    return np.clip(q, 0, 65535).astype(np.uint16)


def raw_path(raw: Path, e: int, n: int) -> Path | None:
    """Rohkachel im Cache: .npz (komprimiert) oder .npy (älterer Lauf)."""
    for ext in ("npz", "npy"):
        p = raw / f"{e}_{n}.{ext}"
        if p.exists():
            return p
    return None


def read_raw(p: Path) -> np.ndarray:
    a = np.load(p)
    return a["a"] if p.suffix == ".npz" else a


def fetch_raw(client, item: dict, raw: Path) -> str:
    dest = raw / f"{item['e']}_{item['n']}.npz"
    if raw_path(raw, item["e"], item["n"]):
        return "skip"
    for attempt in range(4):
        try:
            r = client.get(item["url"])
            if r.status_code != 200:
                raise OSError(f"HTTP {r.status_code}")
            if hashlib.sha256(r.content).hexdigest() != item["sha"]:
                raise OSError("Prüfsumme stimmt nicht")
            tmp = raw / f".{item['e']}_{item['n']}.tmp.npz"
            np.savez_compressed(tmp, a=tif_to_u16(r.content))
            os.replace(tmp, dest)
            return "ok"
        except Exception as e:  # noqa: BLE001 - Netz, Datei, Format: alles wird gezählt und beim nächsten Lauf wiederholt
            log.warning("%s: %s (Versuch %d)", item["name"], e, attempt + 1)
            time.sleep(2 * (attempt + 1))
    return "fail"


def candidates(red: Path, cand_slope: float, min_cells: int) -> set[tuple[int, int]]:
    """Kilometerkacheln, in denen das 4-m-Raster mindestens min_cells Zellen mit Neigung >= cand_slope hat."""
    out = set()
    for p in red.glob("*_*.npy"):
        if p.name.endswith(".tmp.npy"):
            continue
        a = np.load(p).astype(np.float32)
        ok = a > 0
        if not ok.any():
            continue
        h = a / 10.0 - 200.0
        gy, gx = np.gradient(np.where(ok, h, np.nan), 1000 / RED_CELL)
        s = np.degrees(np.arctan(np.hypot(gx, gy)))
        if int(np.nansum(s >= cand_slope)) >= min_cells:
            e, n = (int(v) for v in p.stem.split("_"))
            out.add((e, n))
    return out


def with_neighbours(tiles: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return {(e + de, n + dn) for e, n in tiles for de in (-1, 0, 1) for dn in (-1, 0, 1)}


# ------------------------------------------------------------------ Höhenfeld
def load_block(raw: Path, e0: int, n0: int, e1: int, n1: int) -> np.ndarray:
    """Höhen in m für die Kilometerkacheln e0..e1, n0..n1 (einschließlich); Zeile 0 = Nordrand, NaN = keine Daten."""
    rows, cols = (n1 - n0 + 1) * 1000, (e1 - e0 + 1) * 1000
    mos = np.zeros((rows, cols), np.uint16)
    for a in range(e0, e1 + 1):
        for b in range(n0, n1 + 1):
            p = raw_path(raw, a, b)
            if p:
                r0, c0 = (n1 - b) * 1000, (a - e0) * 1000
                mos[r0:r0 + 1000, c0:c0 + 1000] = read_raw(p)
    h = mos.astype(np.float32) / SCALE - OFFSET
    h[mos == 0] = np.nan
    return h


# ------------------------------------------------------------------ Wandflächen
def _filled(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lücken mit dem nächsten Nachbarn füllen; liefert (gefüllt, Lückenmaske)."""
    from scipy import ndimage as ndi
    bad = ~np.isfinite(h)
    if not bad.any():
        return h, bad
    idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
    return h[tuple(idx)], bad


def _rings(mask: np.ndarray, r0: int, c0: int, rows: int, simplify_m: float):
    """Umrisse einer Maske als Polygone in lokalen Metern (x Ost, y Nord, Ursprung links unten im Block)."""
    from shapely.geometry import Polygon
    from skimage import measure
    polys = []
    for c in measure.find_contours(np.pad(mask, 1).astype(np.float32), 0.5):
        if len(c) < 8:
            continue
        x = (c[:, 1] - 1 + c0 + 0.5) * RES
        y = rows * RES - (c[:, 0] - 1 + r0 + 0.5) * RES
        p = Polygon(np.stack([x, y], 1))
        if not p.is_valid:
            p = p.buffer(0)
        p = p.simplify(simplify_m)
        if not p.is_empty and p.geom_type == "Polygon" and p.area > 60:
            polys.append(p)
    polys.sort(key=lambda p: p.area, reverse=True)
    outers: list = []
    holes: list[list] = []
    for p in polys:
        for i, o in enumerate(outers):
            if o.contains(p):
                holes[i].append(p)
                break
        else:
            outers.append(p)
            holes.append([])
    return [(o, [list(h.exterior.coords) for h in hs]) for o, hs in zip(outers, holes)]


def crest_lines(poly, height, spacing: float = 2.0, off_m: float = 3.0, min_pts: int = 5) -> list[np.ndarray]:
    """Oberkante: die Teile des Außenrands, an denen das Gelände außen höher liegt als innen.
    Laufrichtung: die Wand (Innenseite) liegt rechts der Linie."""
    import shapely
    from scipy import ndimage as ndi
    ring = poly.exterior
    n = max(int(ring.length / spacing), 8)
    pts = shapely.get_coordinates(shapely.line_interpolate_point(ring, np.linspace(0, ring.length, n, endpoint=False)))
    t = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
    t /= np.maximum(np.hypot(t[:, 0], t[:, 1]), 1e-9)[:, None]
    right = np.stack([t[:, 1], -t[:, 0]], 1)
    ccw = ring.is_ccw
    out_n = right if ccw else -right                    # nach außen (gegen den Uhrzeigersinn liegt rechts = außen)
    up = ndi.uniform_filter1d((height(pts + out_n * off_m) > height(pts - out_n * off_m)).astype(float), 5, mode="wrap") > 0.5
    if not up.any():
        return []
    if up.all():
        closed = np.vstack([pts, pts[:1]])
        return [closed[::-1] if ccw else closed]
    s = int(np.argmin(up))                                # an einer Nicht-Kante beginnen, damit Läufe nicht am Nahtpunkt reißen
    pts, up = np.roll(pts, -s, 0), np.roll(up, -s)
    lines, i = [], 0
    while i < len(pts):
        if up[i]:
            j = i
            while j + 1 < len(pts) and up[j + 1]:
                j += 1
            if j - i + 1 >= min_pts:
                seg = pts[i:j + 1]
                lines.append(seg[::-1] if ccw else seg)      # gegen den Uhrzeigersinn liegt die Innenseite links → umdrehen
            i = j + 1
        else:
            i += 1
    return lines


def fall_strokes(poly, gfield, rng, spacing: float = 3.5, step: float = 1.1, n_steps: int = 4) -> list[np.ndarray]:
    """Striche in Fallrichtung: Saatpunkte auf verwürfeltem Raster, je 3 bis n_steps Schritte bergab, an der Flächengrenze gekappt.
    gfield(pts) liefert den Gradienten (dz/dx, dz/dy) in x Ost, y Nord."""
    import shapely
    minx, miny, maxx, maxy = poly.bounds
    xs, ys = np.meshgrid(np.arange(minx, maxx, spacing), np.arange(miny, maxy, spacing))
    sx = xs.ravel() + rng.uniform(-0.4, 0.4, xs.size) * spacing
    sy = ys.ravel() + rng.uniform(-0.4, 0.4, ys.size) * spacing
    keep = shapely.contains_xy(poly, sx, sy)
    if not keep.any():
        return []
    p = np.stack([sx[keep], sy[keep]], 1)
    steps = rng.integers(3, n_steps + 1, len(p))
    path = [p]
    for _ in range(n_steps):
        gx, gy = gfield(p)
        d = -np.stack([gx, gy], 1)                         # bergab
        nrm = np.hypot(d[:, 0], d[:, 1])
        d = d / np.maximum(nrm, 1e-9)[:, None]
        p = p + d * step * (nrm > 1e-6)[:, None]
        path.append(p)
    path = np.stack(path, 1)                                # (N, n_steps+1, 2)
    inside = shapely.contains_xy(poly, path[..., 0].ravel(), path[..., 1].ravel()).reshape(path.shape[:2])
    cnt = np.minimum(np.cumprod(inside, axis=1).sum(axis=1), steps + 1)
    return [path[i, :c] for i, c in enumerate(cnt) if c >= 3]


def derive(h: np.ndarray, slope_hi: float = 55.0, slope_lo: float = 47.0, sigma: float = 1.5, dir_sigma: float = 4.0,
           min_area: float = 200.0, min_drop: float = 5.0, simplify_m: float = 0.8, spacing: float = 3.5, seed: int = 7) -> list[dict]:
    """Wandflächen eines Höhenfelds (1-m-Raster, Zeile 0 = Nord). Koordinaten lokal in m: x Ost, y Nord, Ursprung links unten.
    Je Wand: poly (shapely, mit Löchern), drop, kante (Linienliste), schraffur (Linienliste)."""
    from scipy import ndimage as ndi
    from shapely.geometry import Polygon
    from skimage import morphology
    from skimage.filters import apply_hysteresis_threshold
    rows = h.shape[0]
    filled, bad = _filled(h)
    if bad.all():
        return []
    g = ndi.gaussian_filter(filled, sigma / RES, mode="nearest")
    gy, gx = np.gradient(g, RES)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    if bad.any():
        slope[ndi.binary_dilation(bad, iterations=3)] = 0.0
    del gx, gy
    steep = apply_hysteresis_threshold(slope, slope_lo, slope_hi)
    del slope
    if not steep.any():
        return []
    steep = morphology.remove_small_holes(steep, int(60 / RES ** 2))
    steep = morphology.binary_opening(steep, morphology.disk(max(1, int(round(1.5 / RES)))))
    steep = morphology.remove_small_objects(steep, int(min_area / RES ** 2))
    lab, n_lab = ndi.label(steep)
    if n_lab == 0:
        return []
    g4 = ndi.gaussian_filter(filled, dir_sigma / RES, mode="nearest")
    g4y, g4x = np.gradient(g4, RES)                         # g4y: je Zeile (nach Süden)

    def height(pts: np.ndarray) -> np.ndarray:
        return ndi.map_coordinates(g, [rows - pts[:, 1] / RES - 0.5, pts[:, 0] / RES - 0.5], order=1, mode="nearest")

    def gfield(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        rc = [rows - pts[:, 1] / RES - 0.5, pts[:, 0] / RES - 0.5]
        return (ndi.map_coordinates(g4x, rc, order=1, mode="nearest"), -ndi.map_coordinates(g4y, rc, order=1, mode="nearest"))

    rng = np.random.default_rng(seed)
    out = []
    for k, sl in enumerate(ndi.find_objects(lab), 1):
        if sl is None:
            continue
        r0, c0 = sl[0].start, sl[1].start
        mk = lab[sl] == k
        z = g[sl][mk]
        drop = float(np.percentile(z, 98) - np.percentile(z, 2))
        if drop < min_drop:
            continue
        for poly, holes in _rings(mk, r0, c0, rows, simplify_m):
            pg = Polygon(poly.exterior.coords, holes)
            if not pg.is_valid:
                pg = pg.buffer(0)
            if pg.is_empty or pg.geom_type != "Polygon":
                continue
            out.append({"poly": pg, "drop": round(drop, 1), "kante": crest_lines(pg, height),
                        "schraffur": fall_strokes(pg, gfield, rng, spacing=spacing)})
    return out


# ------------------------------------------------------------------ Blöcke
def process_block(args: tuple) -> list[dict]:
    raw, e0, n0, e1, n1, halo, kw = args
    from pyproj import Transformer
    h = load_block(Path(raw), e0 - halo, n0 - halo, e1 + halo, n1 + halo)
    if not np.isfinite(h).any():
        return []
    left, bottom = (e0 - halo) * 1000.0, (n0 - halo) * 1000.0
    core = (e0 * 1000.0 - left, n0 * 1000.0 - bottom, (e1 + 1) * 1000.0 - left, (n1 + 1) * 1000.0 - bottom)
    found = derive(h, **kw)
    del h
    tr = Transformer.from_crs(CRS_UTM, "EPSG:4326", always_xy=True)

    def ll(arr) -> np.ndarray:
        a = np.asarray(arr, float)
        lon, lat = tr.transform(a[:, 0] + left, a[:, 1] + bottom)
        return np.round(np.stack([lon, lat], 1), 7)

    res = []
    for w in found:
        c = w["poly"].representative_point()
        if not (core[0] <= c.x < core[2] and core[1] <= c.y < core[3]):
            continue                                   # gehört zum Nachbarblock, dort wird sie gezählt
        res.append({"drop": w["drop"],
                    "wand": [(ll(w["poly"].exterior.coords), [ll(i.coords) for i in w["poly"].interiors])],
                    "kante": [ll(k) for k in w["kante"]],
                    "schraffur": [ll(s) for s in w["schraffur"]]})
    return res


# ------------------------------------------------------------------ Kacheln
def merc(lon: np.ndarray, lat: np.ndarray, z: int = TILE_Z) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / math.pi) / 2 * n
    return x, y


def write_tiles(items: list[dict], out: Path) -> int:
    """Items → MVT-Kacheln Zoom 13. Flächen und Kanten werden an der Kachel (+ Rand) beschnitten,
    Striche gehören ganz der Kachel ihres Anfangspunkts."""
    from shapely.affinity import affine_transform
    from shapely.geometry import LineString, Polygon, box
    import mapbox_vector_tile as mvt

    def proj(coords) -> np.ndarray:
        c = np.asarray(coords, float)
        x, y = merc(c[:, 0], c[:, 1])
        return np.stack([x, y], 1)

    buckets: dict[tuple[int, int], dict[str, list]] = defaultdict(lambda: defaultdict(list))

    def put(layer: str, geom, props: dict) -> None:
        x0, y0, x1, y1 = geom.bounds
        for tx in range(int(math.floor(x0)), int(math.floor(x1)) + 1):
            for ty in range(int(math.floor(y0)), int(math.floor(y1)) + 1):
                buckets[(tx, ty)][layer].append((geom, props))

    for it in items:
        props = {"drop": it["drop"]}
        for ext, holes in it["wand"]:
            put("wand", Polygon(proj(ext), [proj(h) for h in holes]), props)
        for k in it["kante"]:
            if len(k) >= 2:
                put("kante", LineString(proj(k)), props)
        for s in it["schraffur"]:
            p = proj(s)
            buckets[(int(math.floor(p[0, 0])), int(math.floor(p[0, 1])))]["schraffur"].append((LineString(p), {}))
    pad = 64 / EXTENT
    n = 0
    for (tx, ty), layers in buckets.items():
        win = box(tx - pad, ty - pad, tx + 1 + pad, ty + 1 + pad)
        mat = [EXTENT, 0, 0, EXTENT, -tx * EXTENT, -ty * EXTENT]
        out_layers = []
        for name, entries in layers.items():
            feats = []
            for geom, props in entries:
                g = geom if name == "schraffur" else geom.intersection(win)
                if g.is_empty:
                    continue
                for p in (list(g.geoms) if hasattr(g, "geoms") else [g]):
                    if p.is_empty:
                        continue
                    if name == "wand":
                        if p.geom_type != "Polygon":
                            continue
                    elif p.geom_type != "LineString" or len(p.coords) < 2:
                        continue
                    px = affine_transform(p, mat)
                    if name == "schraffur":
                        px = LineString(np.rint(np.array(px.coords)))
                        if len(set(px.coords)) < 2:
                            continue
                    feats.append({"geometry": px, "properties": props})
            if feats:
                out_layers.append({"name": name, "features": feats})
        if not out_layers:
            continue
        data = mvt.encode(out_layers, default_options={"extents": EXTENT, "y_coord_down": True})
        d = out / str(TILE_Z) / str(tx)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{ty}.pbf").write_bytes(data)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, required=True, help="Arbeitsordner von build_dem_rlp.py (enthält red/, dgm1_tif_07.meta4); raw/ entsteht hier")
    ap.add_argument("--out", type=Path, required=True, help="Zielordner der Kacheln, z. B. web/tiles/klippen")
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("LON0", "LAT0", "LON1", "LAT1"), help="nur dieser Ausschnitt")
    ap.add_argument("--no-fetch", action="store_true", help="nichts herunterladen, nur vorhandene Rohkacheln verwenden")
    ap.add_argument("--all-tiles", action="store_true", help="alle Kacheln des 4-m-Rasters verarbeiten (keine Vorauswahl nach Steilheit, rund 32 GB Download)")
    ap.add_argument("--cand-slope", type=float, default=35.0, help="Kandidatenwahl: Neigung im 4-m-Raster in Grad")
    ap.add_argument("--cand-cells", type=int, default=3, help="Kandidatenwahl: Mindestzahl steiler Zellen je Kilometerkachel")
    ap.add_argument("--chunk", type=int, default=2, help="Blockgröße in km (zzgl. 1 km Rand)")
    ap.add_argument("--slope", type=float, default=55.0, help="Kern der Steilzone in Grad")
    ap.add_argument("--low", type=float, default=47.0, help="Rand der Steilzone in Grad (Hysterese)")
    ap.add_argument("--sigma", type=float, default=1.5, help="Glättung für die Neigung in m")
    ap.add_argument("--min-area", type=float, default=200.0, help="kleinste Wandfläche in m²")
    ap.add_argument("--min-drop", type=float, default=5.0, help="kleinste Wandhöhe in m")
    ap.add_argument("--spacing", type=float, default=3.5, help="Abstand der Schraffurstriche in m")
    ap.add_argument("--simplify", type=float, default=0.8, help="Vereinfachung der Umrisse in m")
    ap.add_argument("--jobs", type=int, default=max(1, min(4, (os.cpu_count() or 2) - 1)))
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    red, raw = a.work / "red", a.work / "raw"
    if not any(red.glob("*_*.npy")):
        log.error("keine Kacheln in %s (erst tools/build_dem_rlp.py laufen lassen)", red)
        return 1
    raw.mkdir(parents=True, exist_ok=True)
    if a.all_tiles:
        cand = {tuple(int(v) for v in p.stem.split("_")) for p in red.glob("*_*.npy") if not p.name.endswith(".tmp.npy")}
    else:
        cand = candidates(red, a.cand_slope, a.cand_cells)
    if a.bbox:
        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", CRS_UTM, always_xy=True)
        xs, ys = t.transform([a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
        bk = (int(min(xs) // 1000), int(min(ys) // 1000), int(max(xs) // 1000), int(max(ys) // 1000))
        cand = {k for k in cand if bk[0] <= k[0] <= bk[2] and bk[1] <= k[1] <= bk[3]}
    need = with_neighbours(cand)
    log.info("%d Kandidatenkacheln, mit Nachbarn %d", len(cand), len(need))

    if not a.no_fetch:
        dem = _dem_module()
        listing = a.work / "dgm1_tif_07.meta4"
        if not listing.exists():
            import httpx
            r = httpx.get(dem.LIST_URL, headers={"User-Agent": dem.UA}, timeout=120)
            r.raise_for_status()
            listing.write_text(r.text, encoding="utf-8")
        newest: dict[tuple[int, int], dict] = {}
        for it in dem.parse_meta4(listing.read_text(encoding="utf-8")):
            k = (it["e"], it["n"])
            if k in need and (k not in newest or it["year"] > newest[k]["year"]):
                newest[k] = it
        todo = [it for k, it in newest.items() if not raw_path(raw, *k)]
        log.info("%d Rohkacheln fehlen, %.1f GB Download", len(todo), sum(i["size"] for i in todo) / 1e9)
        if todo:
            import httpx
            stats: dict[str, int] = defaultdict(int)
            with httpx.Client(headers={"User-Agent": dem.UA}, timeout=120, follow_redirects=False) as client, ThreadPoolExecutor(4) as pool:
                for i, res in enumerate(pool.map(lambda it: fetch_raw(client, it, raw), todo), 1):
                    stats[res] += 1
                    if i % 250 == 0 or i == len(todo):
                        log.info("  geladen %d/%d (%s)", i, len(todo), dict(stats))
            if stats["fail"]:
                log.warning("%d Kacheln nicht geladen, nächster Lauf holt sie nach", stats["fail"])

    have = {k for k in need if raw_path(raw, *k)}
    core_tiles = {k for k in cand if k in have}
    if not core_tiles:
        log.error("keine Rohkacheln vorhanden")
        return 1
    kw = dict(slope_hi=a.slope, slope_lo=a.low, sigma=a.sigma, min_area=a.min_area, min_drop=a.min_drop, simplify_m=a.simplify, spacing=a.spacing)
    es, ns = [k[0] for k in core_tiles], [k[1] for k in core_tiles]
    jobs = []
    for e0 in range(min(es) - min(es) % a.chunk, max(es) + 1, a.chunk):
        for n0 in range(min(ns) - min(ns) % a.chunk, max(ns) + 1, a.chunk):
            e1, n1 = e0 + a.chunk - 1, n0 + a.chunk - 1
            if any(e0 <= e <= e1 and n0 <= n <= n1 for e, n in core_tiles):
                jobs.append((str(raw), e0, n0, e1, n1, 1, kw))
    log.info("%d Blöcke, %d Prozesse", len(jobs), a.jobs)
    items: list[dict] = []
    strokes = 0
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, res in enumerate(ex.map(process_block, jobs), 1):
            items.extend(res)
            strokes += sum(len(r["schraffur"]) for r in res)
            if i % 5 == 0 or i == len(jobs):
                log.info("  Block %d/%d, bisher %d Wände, %d Striche", i, len(jobs), len(items), strokes)
    log.info("%d Wände, schreibe Kacheln", len(items))
    if a.out.exists():
        import shutil
        shutil.rmtree(a.out)
    a.out.mkdir(parents=True)
    n = write_tiles(items, a.out)
    meta = {
        "attribution": "Wandflächen abgeleitet aus dem DGM1: © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet]",
        "zoom": TILE_Z, "layers": ["wand", "kante", "schraffur"], "attributes": {"drop": "Wandhöhe in m (2.–98. Perzentil der Höhen in der Fläche)"},
        "params": {"slope_deg": a.slope, "low_deg": a.low, "sigma_m": a.sigma, "min_area_m2": a.min_area, "min_drop_m": a.min_drop,
                   "spacing_m": a.spacing, "simplify_m": a.simplify},
        "walls": len(items), "strokes": strokes, "tiles": n,
    }
    (a.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.out / "README.txt").write_text("Felswände aus dem Geländemodell (tools/build_klippen_dgm.py). Vektorkacheln Zoom 13, Ebenen wand, kante, schraffur.\n", encoding="utf-8")
    log.info("fertig: %d Kacheln, %d Wände", n, len(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
