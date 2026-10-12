#!/usr/bin/env python3
"""Klippen und Felswände aus dem Landes-DGM1 ableiten und als Vektorkacheln (Zoom 12) ablegen.

Zweck:      Die Klippen der Basiskarte stammen aus OpenStreetMap und sind lückenhaft und grob. Das Geländemodell
            kennt jede Steilwand: wo das 4-m-Raster steiler als ~55 Grad fällt, steht eine Wand. Dieses Werkzeug
            zieht daraus Linien mit Laufrichtung (Abbruchseite rechts der Linie, wie bei den OSM-Klippen) und die
            Wandhöhe als Attribut `drop`. Die Karte zeichnet sie mit denselben Schraffen wie die OSM-Klippen.
Quelle:     Landes-DGM1 RLP (© GeoBasis-DE / LVermGeoRP, dl-de/by-2-0, Daten bearbeitet) über das 4-m-Raster aus
            tools/build_dem_rlp.py (work/red/*.npy). Es entsteht eine abgeleitete Datenbasis; der Vermerk steht in meta.json.
Ablauf:     1. Blöcke von 8 x 8 km (+ 1 km Rand) zum Höhenfeld zusammensetzen, glätten, Neigung rechnen
            2. steile Zellen (>= --slope) zu Flecken, kleine Flecken (< --min-cells) verwerfen
            3. Flecken auf Mittellinien ausdünnen (Skelett), zu Linien verfolgen, vereinfachen, glätten
            4. Laufrichtung so, dass die Abbruchseite rechts liegt; `drop` = Höhenunterschied beidseits (± 8 m)
            5. nach Web-Mercator Zoom 12 kacheln (MVT, Ebene `klippen`) nach <out>/12/<x>/<y>.pbf
Aufruf:     python tools/build_klippen_dgm.py --work ~/Claude/OSINT/dgm1-work --out perf-rlp/tiles/klippen
            python tools/build_klippen_dgm.py --work ... --out ... --bbox 6.3 49.75 6.6 49.95      Ausschnitt (Test)
            python tools/build_klippen_dgm.py --work ... --out ... --slope 50 --min-drop 5 -v      Schwellen ändern
Exit:       0 = fertig, 1 = Fehler / keine Kacheln
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

log = logging.getLogger("osint.klippen")

CELL = 250                    # Zellen je km Kantenlänge (4-m-Raster aus build_dem_rlp.py)
RES = 1000 / CELL             # 4 m
OFFSET, SCALE = 200.0, 10.0   # uint16 = (h + 200) * 10, 0 = keine Daten (wie build_dem_rlp.py)
TILE_Z = 12
EXTENT = 4096
CRS_UTM = "EPSG:25832"


# ------------------------------------------------------------------ Höhenfeld
def load_block(red: Path, e0: int, n0: int, e1: int, n1: int) -> np.ndarray:
    """Höhen in m für die Kilometerkacheln e0..e1, n0..n1 (einschließlich); Zeile 0 = Nordrand, NaN = keine Daten."""
    rows, cols = (n1 - n0 + 1) * CELL, (e1 - e0 + 1) * CELL
    mos = np.zeros((rows, cols), np.uint16)
    for a in range(e0, e1 + 1):
        for b in range(n0, n1 + 1):
            p = red / f"{a}_{b}.npy"
            if p.exists():
                r0, c0 = (n1 - b) * CELL, (a - e0) * CELL
                mos[r0:r0 + CELL, c0:c0 + CELL] = np.load(p)
    h = mos.astype(np.float32) / SCALE - OFFSET
    h[mos == 0] = np.nan
    return h


def slope_deg(h: np.ndarray, sigma: float) -> np.ndarray:
    """Neigung in Grad; leichte Glättung gegen Rauschen, Lücken bleiben NaN."""
    from scipy import ndimage as ndi
    bad = ~np.isfinite(h)
    if bad.all():
        return np.full_like(h, np.nan)
    idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
    filled = h[tuple(idx)]
    if sigma > 0:
        filled = ndi.gaussian_filter(filled, sigma, mode="nearest")
    gy, gx = np.gradient(filled, RES)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    # eine Zelle Rand um Lücken ausblenden (Ränder von Wasser/Nodata sehen sonst wie Wände aus)
    s[ndi.binary_dilation(bad, iterations=2)] = np.nan
    return s


# ------------------------------------------------------------------ Skelett → Linien
def _neighbours(pix: set[tuple[int, int]]) -> dict[tuple[int, int], list[tuple[int, int]]]:
    """8er-Nachbarschaft; eine Diagonale entfällt, wenn beide Enden einen gemeinsamen orthogonalen Nachbarn haben (Treppenecke)."""
    nb: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for (r, c) in pix:
        out = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if (dr or dc) and (r + dr, c + dc) in pix:
                    if dr and dc and ((r + dr, c) in pix or (r, c + dc) in pix):
                        continue
                    out.append((r + dr, c + dc))
        nb[(r, c)] = out
    # Symmetrie herstellen (die Diagonalregel kann einseitig greifen)
    for p, lst in nb.items():
        nb[p] = [q for q in lst if p in nb.get(q, ())]
    return nb


def trace(skel: np.ndarray) -> list[list[tuple[int, int]]]:
    """Skelett (bool) zu Pixelketten. Knoten = Enden und Verzweigungen."""
    pix = set(zip(*np.nonzero(skel)))
    nb = _neighbours(pix)
    node = {p for p, l in nb.items() if len(l) != 2}
    seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    chains: list[list[tuple[int, int]]] = []

    def walk(u, v):
        path = [u, v]
        seen.add((u, v)); seen.add((v, u))
        prev, cur = u, v
        while cur not in node:
            nxt = [q for q in nb[cur] if q != prev]
            if not nxt:
                break
            q = nxt[0]
            if (cur, q) in seen:
                break
            seen.add((cur, q)); seen.add((q, cur))
            path.append(q)
            prev, cur = cur, q
        return path

    for u in node:
        for v in nb[u]:
            if (u, v) not in seen:
                chains.append(walk(u, v))
    for u in pix:                                  # reine Schleifen ohne Knoten
        for v in nb[u]:
            if (u, v) not in seen and u not in node:
                chains.append(walk(u, v))
    return chains


def chaikin(pts: np.ndarray, rounds: int = 2) -> np.ndarray:
    for _ in range(rounds):
        if len(pts) < 3:
            break
        q = 0.75 * pts[:-1] + 0.25 * pts[1:]
        r = 0.25 * pts[:-1] + 0.75 * pts[1:]
        mid = np.empty((2 * len(q), 2))
        mid[0::2], mid[1::2] = q, r
        pts = np.vstack([pts[:1], mid, pts[-1:]])
    return pts


def sample(h: np.ndarray, rc: np.ndarray) -> np.ndarray:
    from scipy import ndimage as ndi
    filled = np.where(np.isfinite(h), h, np.nan)
    return ndi.map_coordinates(filled, [rc[:, 0], rc[:, 1]], order=1, mode="nearest", cval=np.nan)


def orient(pts_rc: np.ndarray, h: np.ndarray, off_m: float = 8.0) -> tuple[np.ndarray, float] | None:
    """Linie (Zeile, Spalte) so drehen, dass die tiefere Seite rechts liegt; liefert (Linie, Höhenunterschied in m)."""
    t = np.gradient(pts_rc, axis=0)
    ln = np.hypot(t[:, 0], t[:, 1])
    ln[ln == 0] = 1
    t = t / ln[:, None]
    # in Zeile/Spalte läuft die Zeile nach Süden; rechts der Laufrichtung (Norden oben) ist (dr, dc) → (dc, -dr)... in (r, c): rechts = (t_c, -t_r)
    right = np.stack([t[:, 1], -t[:, 0]], axis=1)
    k = off_m / RES
    hr = sample(h, pts_rc + right * k)
    hl = sample(h, pts_rc - right * k)
    d = np.nanmean(hl - hr) if np.isfinite(hl - hr).any() else np.nan
    if not np.isfinite(d):
        return None
    if d < 0:
        return pts_rc[::-1], float(-d)
    return pts_rc, float(d)


def block_lines(h: np.ndarray, slope: float, min_cells: int, min_len_m: float, min_drop: float,
                sigma: float, simplify_m: float) -> list[tuple[np.ndarray, float]]:
    """Linien eines Höhenfelds: Liste von (Punkte als (Zeile, Spalte)-Feld in Zellen, Höhenunterschied m)."""
    from scipy import ndimage as ndi
    from skimage.morphology import skeletonize
    from shapely.geometry import LineString

    s = slope_deg(h, sigma)
    steep = np.nan_to_num(s, nan=0.0) >= slope
    if not steep.any():
        return []
    lab, n = ndi.label(steep, structure=np.ones((3, 3)))
    sizes = ndi.sum(steep, lab, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= min_cells
    steep = keep[lab]
    steep = ndi.binary_closing(steep, structure=np.ones((3, 3)))
    skel = skeletonize(steep)
    out = []
    for ch in trace(skel):
        pts = np.array(ch, float)
        if len(pts) < 3:
            continue
        ls = LineString(pts[:, ::-1]).simplify(simplify_m / RES)
        if ls.length * RES < min_len_m:
            continue
        pts = chaikin(np.array(ls.coords)[:, ::-1])
        res = orient(pts, h)
        if res is None or res[1] < min_drop:
            continue
        out.append(res)
    return out


# ------------------------------------------------------------------ Blöcke und Kacheln
def process_block(args: tuple) -> list[tuple[list[list[float]], float]]:
    red, e0, n0, e1, n1, halo, kw = args
    from pyproj import Transformer
    h = load_block(Path(red), e0 - halo, n0 - halo, e1 + halo, n1 + halo)
    if not np.isfinite(h).any():
        return []
    lines = block_lines(h, **kw)
    if not lines:
        return []
    top = (n1 + halo + 1) * 1000.0
    left = (e0 - halo) * 1000.0
    core = (e0 * 1000.0, (n0) * 1000.0, (e1 + 1) * 1000.0, (n1 + 1) * 1000.0)
    tr = Transformer.from_crs(CRS_UTM, "EPSG:4326", always_xy=True)
    res = []
    for pts, drop in lines:
        e = left + (pts[:, 1] + 0.5) * RES
        n = top - (pts[:, 0] + 0.5) * RES
        m = len(pts) // 2
        if not (core[0] <= e[m] < core[2] and core[1] <= n[m] < core[3]):
            continue                                  # gehört zum Nachbarblock (Rand), dort wird sie gezählt
        lon, lat = tr.transform(e, n)
        res.append((np.round(np.stack([lon, lat], 1), 6).tolist(), round(drop, 1)))
    return res


def merc(lon: np.ndarray, lat: np.ndarray, z: int = TILE_Z) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / math.pi) / 2 * n
    return x, y


def write_tiles(lines: list[tuple[list[list[float]], float]], out: Path) -> int:
    from shapely.geometry import LineString, box
    import mapbox_vector_tile as mvt
    buckets: dict[tuple[int, int], list[tuple[LineString, float]]] = defaultdict(list)
    for coords, drop in lines:
        a = np.array(coords)
        x, y = merc(a[:, 0], a[:, 1])
        ls = LineString(np.stack([x, y], 1))
        x0, y0, x1, y1 = ls.bounds
        for tx in range(int(math.floor(x0)), int(math.floor(x1)) + 1):
            for ty in range(int(math.floor(y0)), int(math.floor(y1)) + 1):
                buckets[(tx, ty)].append((ls, drop))
    pad = 64 / EXTENT
    n = 0
    for (tx, ty), items in buckets.items():
        feats = []
        win = box(tx - pad, ty - pad, tx + 1 + pad, ty + 1 + pad)
        for ls, drop in items:
            g = ls.intersection(win)
            if g.is_empty:
                continue
            parts = list(g.geoms) if g.geom_type == "MultiLineString" else [g]
            for p in parts:
                if p.geom_type != "LineString" or len(p.coords) < 2:
                    continue
                px = [((cx - tx) * EXTENT, (cy - ty) * EXTENT) for cx, cy in p.coords]
                feats.append({"geometry": LineString(px), "properties": {"drop": drop}})
        if not feats:
            continue
        data = mvt.encode([{"name": "klippen", "features": feats}], default_options={"extents": EXTENT, "y_coord_down": True})
        d = out / str(TILE_Z) / str(tx)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{ty}.pbf").write_bytes(data)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, required=True, help="Arbeitsordner von build_dem_rlp.py (enthält red/)")
    ap.add_argument("--out", type=Path, required=True, help="Zielordner der Kacheln, z. B. web/tiles/klippen")
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("LON0", "LAT0", "LON1", "LAT1"), help="nur dieser Ausschnitt")
    ap.add_argument("--chunk", type=int, default=8, help="Blockgröße in km")
    ap.add_argument("--slope", type=float, default=55.0, help="Mindestneigung in Grad")
    ap.add_argument("--min-cells", type=int, default=8, help="kleinste Steilfläche in Zellen (16 m²)")
    ap.add_argument("--min-len", type=float, default=24.0, help="kürzeste Linie in m")
    ap.add_argument("--min-drop", type=float, default=6.0, help="kleinster Höhenunterschied beidseits in m")
    ap.add_argument("--sigma", type=float, default=0.6, help="Glättung des Höhenfelds in Zellen")
    ap.add_argument("--simplify", type=float, default=3.0, help="Vereinfachung in m")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    red = a.work / "red"
    have = {tuple(int(v) for v in p.stem.split("_")) for p in red.glob("*_*.npy") if not p.name.endswith(".tmp.npy")}
    if not have:
        log.error("keine Kacheln in %s", red)
        return 1
    if a.bbox:
        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", CRS_UTM, always_xy=True)
        xs, ys = t.transform([a.bbox[0], a.bbox[2], a.bbox[0], a.bbox[2]], [a.bbox[1], a.bbox[1], a.bbox[3], a.bbox[3]])
        box_km = (int(min(xs) // 1000), int(min(ys) // 1000), int(max(xs) // 1000), int(max(ys) // 1000))
        have = {k for k in have if box_km[0] <= k[0] <= box_km[2] and box_km[1] <= k[1] <= box_km[3]}
    es, ns = [k[0] for k in have], [k[1] for k in have]
    kw = dict(slope=a.slope, min_cells=a.min_cells, min_len_m=a.min_len, min_drop=a.min_drop, sigma=a.sigma, simplify_m=a.simplify)
    jobs = []
    for e0 in range(min(es) - min(es) % a.chunk, max(es) + 1, a.chunk):
        for n0 in range(min(ns) - min(ns) % a.chunk, max(ns) + 1, a.chunk):
            e1, n1 = e0 + a.chunk - 1, n0 + a.chunk - 1
            if any(e0 <= e <= e1 and n0 <= n <= n1 for e, n in have):
                jobs.append((str(red), e0, n0, e1, n1, 1, kw))
    log.info("%d Kilometerkacheln, %d Blöcke, %d Prozesse", len(have), len(jobs), a.jobs)
    lines: list[tuple[list[list[float]], float]] = []
    with ProcessPoolExecutor(a.jobs) as ex:
        for i, res in enumerate(ex.map(process_block, jobs), 1):
            lines.extend(res)
            if i % 10 == 0 or i == len(jobs):
                log.info("  Block %d/%d, bisher %d Linien", i, len(jobs), len(lines))
    log.info("%d Linien, schreibe Kacheln", len(lines))
    if a.out.exists():
        import shutil
        shutil.rmtree(a.out)
    n = write_tiles(lines, a.out)
    meta = {
        "attribution": "Wandlinien abgeleitet aus dem DGM1: © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet]",
        "zoom": TILE_Z, "layer": "klippen", "attributes": {"drop": "Höhenunterschied beidseits der Wand in m (± 8 m)"},
        "params": {"slope_deg": a.slope, "min_cells": a.min_cells, "min_len_m": a.min_len, "min_drop_m": a.min_drop, "sigma": a.sigma, "simplify_m": a.simplify},
        "lines": len(lines), "tiles": n,
    }
    (a.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.out / "README.txt").write_text("Klippen aus dem Geländemodell (tools/build_klippen_dgm.py). Vektorkacheln Zoom 12, Ebene klippen.\n", encoding="utf-8")
    log.info("fertig: %d Kacheln, %d Linien", n, len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
