#!/usr/bin/env python3
"""Klippen und Felswände aus dem Landes-DGM1 ableiten und als Vektorkacheln (Zoom 12) ablegen.

Zweck:      Die Klippen der Basiskarte stammen aus OpenStreetMap und sind lückenhaft und grob. Das Geländemodell
            kennt jede Steilwand: wo das 4-m-Raster steiler als ~48 Grad fällt, steht eine Wand. Dieses Werkzeug
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


def gradient_field(h: np.ndarray, sigma: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Gefälle (Zeile, Spalte) einer stärker geglätteten Fläche; einmal je Block rechnen."""
    from scipy import ndimage as ndi
    bad = ~np.isfinite(h)
    idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
    g = ndi.gaussian_filter(h[tuple(idx)], sigma, mode="nearest")
    gy, gx = np.gradient(g, RES)
    return gy, gx


def along_contour(grad: tuple[np.ndarray, np.ndarray], pts_rc: np.ndarray, tol_deg: float) -> np.ndarray:
    """Je Stützpunkt: läuft die Linie entlang der Höhenlinie (Tangente quer zum Gefälle)? Wände, die quer über Höhenlinien
    laufen, widersprechen dem Gelände und fliegen raus."""
    from scipy import ndimage as ndi
    gy, gx = grad
    t = np.gradient(pts_rc, axis=0)
    nt = np.hypot(t[:, 0], t[:, 1])
    t /= np.where(nt == 0, 1, nt)[:, None]
    ay = ndi.map_coordinates(gy, [pts_rc[:, 0], pts_rc[:, 1]], order=1, mode="nearest")
    ax = ndi.map_coordinates(gx, [pts_rc[:, 0], pts_rc[:, 1]], order=1, mode="nearest")
    gn = np.hypot(ay, ax)
    cosang = np.abs(t[:, 0] * ay + t[:, 1] * ax) / np.where(gn == 0, np.inf, gn)
    ok = cosang < np.sin(np.radians(tol_deg))
    # Ausreißer glätten (Mehrheit über 5 Punkte), damit eine Ecke die Linie nicht zerhackt
    return ndi.uniform_filter1d(ok.astype(float), 5, mode="nearest") >= 0.5


def runs(ok: np.ndarray) -> list[tuple[int, int]]:
    out, i, n = [], 0, len(ok)
    while i < n:
        if ok[i]:
            j = i
            while j + 1 < n and ok[j + 1]:
                j += 1
            out.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return out


def block_lines(h: np.ndarray, slope: float, min_cells: int, min_len_m: float, min_drop: float,
                sigma: float, simplify_m: float, low: float = 40.0, tol: float = 35.0) -> list[tuple[np.ndarray, float]]:
    """Linien eines Höhenfelds: Liste von (Punkte als (Zeile, Spalte)-Feld in Zellen, Höhenunterschied m).
    Hysterese: Kerne ab `slope` Grad, verbunden über Hang ab `low` Grad (hält Kanten zusammen). Stücke, die quer zu den
    Höhenlinien laufen (mehr als `tol` Grad Abweichung), werden verworfen."""
    from scipy import ndimage as ndi
    from skimage.filters import apply_hysteresis_threshold
    from skimage.morphology import skeletonize
    from shapely.geometry import LineString

    s = np.nan_to_num(slope_deg(h, sigma), nan=0.0)
    steep = apply_hysteresis_threshold(s, min(low, slope), slope)
    if not steep.any():
        return []
    lab, n = ndi.label(steep, structure=np.ones((3, 3)))
    sizes = ndi.sum(steep, lab, index=np.arange(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = sizes >= min_cells
    steep = keep[lab]
    steep = ndi.binary_closing(steep, structure=np.ones((3, 3)))
    skel = skeletonize(steep)
    grad = gradient_field(h)
    out = []
    for ch in trace(skel):
        pts = np.array(ch, float)
        if len(pts) < 3:
            continue
        ls = LineString(pts[:, ::-1]).simplify(simplify_m / RES)
        if ls.length * RES < min_len_m:
            continue
        # vereinfachte Linie wieder dicht besetzen (alle ~2 Zellen), damit Glättung und Richtungsprüfung greifen
        ls = LineString(chaikin(np.array(ls.coords)[:, ::-1], 3)[:, ::-1])
        k = max(int(ls.length / 2.0), 2)
        pts = np.array([ls.interpolate(i / k, normalized=True).coords[0] for i in range(k + 1)])[:, ::-1]
        ok = along_contour(grad, pts, tol)
        for a, b in runs(ok):
            part = pts[a:b]
            if len(part) < 3 or LineString(part[:, ::-1]).length * RES < min_len_m:
                continue
            res = orient(part, h)
            if res is None or res[1] < min_drop:
                continue
            out.append(res)
    return out


# ------------------------------------------------------------------ Wandgeometrie
def wall_geometry(e: np.ndarray, n: np.ndarray, drop: float) -> dict[str, list]:
    """Wand als gezeichnete Felsflanke (Meter, UTM): Fläche unterhalb der Oberkante, geneigte unregelmäßige Striche
    (Schraffur) und gebrochene Schichtlinien. Die Oberkante ist die Linie selbst, die tiefere Seite liegt rechts der Laufrichtung.
    Zufall ist deterministisch (aus der Lage der Linie), damit ein Neubau dieselben Kacheln ergibt."""
    from shapely.geometry import LineString, Polygon
    crest = LineString(np.stack([e, n], 1))
    length = crest.length
    if length < 6:
        return {"wand": [], "schraffur": [], "schicht": []}
    rng = np.random.default_rng(int(abs(e[0] * 131 + n[0] * 17)) % (2 ** 32))
    step = 2.0
    k = max(int(length / step), 3)
    ss = np.linspace(0.0, length, k + 1)
    pts = np.array([crest.interpolate(x).coords[0] for x in ss])
    t = np.gradient(pts, axis=0)
    t /= np.where(np.hypot(t[:, 0], t[:, 1]) == 0, 1, np.hypot(t[:, 0], t[:, 1]))[:, None]
    right = np.stack([t[:, 1], -t[:, 0]], 1)
    width0 = float(np.clip(0.4 * drop, 3.0, 11.0))
    ph = rng.uniform(0, 2 * math.pi, 2)
    w = width0 * (0.8 + 0.12 * np.sin(ss / 17.0 + ph[0]) + 0.08 * np.sin(ss / 5.3 + ph[1]))
    w = np.minimum(w, width0 * 1.0)
    low = pts + right * w[:, None]
    ring = np.vstack([pts, low[::-1]])
    poly = Polygon(ring)
    if not poly.is_valid:
        poly = poly.buffer(0)
    face = []
    if not poly.is_empty:
        for g in (list(poly.geoms) if poly.geom_type == "MultiPolygon" else [poly]):
            if g.geom_type == "Polygon" and g.area > 4:
                face.append(np.array(g.exterior.coords))
    strokes = []
    pos = rng.uniform(0.5, 2.5)
    while pos < length - 0.5:
        i = min(int(pos / step), k)
        lean = math.radians(rng.uniform(-14, 14))
        c, sn = math.cos(lean), math.sin(lean)
        d = np.array([right[i, 0] * c - right[i, 1] * sn, right[i, 0] * sn + right[i, 1] * c])
        ln = w[i] * rng.uniform(0.5, 1.0)
        a = pts[i] + right[i] * 0.3
        mid = a + d * ln * 0.5 + t[i] * rng.uniform(-0.4, 0.4)
        strokes.append(np.array([a, mid, a + d * ln]))
        pos += rng.uniform(3.0, 6.0)
    layers = []
    if width0 >= 5:
        for f in (0.38, 0.68):
            s0 = rng.uniform(0, 6)
            while s0 < length - 4:
                run = rng.uniform(6, 18)
                a, b = int(s0 / step), min(int((s0 + run) / step), k)
                if b - a >= 2:
                    layers.append(pts[a:b + 1] + right[a:b + 1] * (w[a:b + 1] * f)[:, None])
                s0 += run + rng.uniform(3, 8)
    return {"wand": face, "schraffur": strokes, "schicht": layers}


# ------------------------------------------------------------------ Blöcke und Kacheln
def process_block(args: tuple) -> list[dict]:
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

    def ll(arr: np.ndarray) -> list[list[float]]:
        lon, lat = tr.transform(arr[:, 0], arr[:, 1])
        return np.round(np.stack([lon, lat], 1), 6).tolist()

    res = []
    for pts, drop in lines:
        e = left + (pts[:, 1] + 0.5) * RES
        n = top - (pts[:, 0] + 0.5) * RES
        m = len(pts) // 2
        if not (core[0] <= e[m] < core[2] and core[1] <= n[m] < core[3]):
            continue                                  # gehört zum Nachbarblock (Rand), dort wird sie gezählt
        wg = wall_geometry(e, n, drop)
        res.append({"crest": ll(np.stack([e, n], 1)), "drop": round(drop, 1),
                    "wand": [ll(r) for r in wg["wand"]], "schraffur": [ll(r) for r in wg["schraffur"]],
                    "schicht": [ll(r) for r in wg["schicht"]]})
    return res


def merc(lon: np.ndarray, lat: np.ndarray, z: int = TILE_Z) -> tuple[np.ndarray, np.ndarray]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / math.pi) / 2 * n
    return x, y


def write_tiles(items: list[dict], out: Path) -> int:
    from shapely.geometry import LineString, MultiLineString, Polygon, box
    import mapbox_vector_tile as mvt

    def proj(coords):
        c = np.array(coords)
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
        put("klippen", LineString(proj(it["crest"])), props)
        for r in it["wand"]:
            put("wand", Polygon(proj(r)), props)
        if it["schraffur"]:
            put("schraffur", MultiLineString([proj(r) for r in it["schraffur"]]), props)
        if it["schicht"]:
            put("schicht", MultiLineString([proj(r) for r in it["schicht"]]), props)
    pad = 64 / EXTENT
    n = 0
    for (tx, ty), layers in buckets.items():
        win = box(tx - pad, ty - pad, tx + 1 + pad, ty + 1 + pad)
        out_layers = []
        for name, entries in layers.items():
            feats = []
            for geom, props in entries:
                g = geom.intersection(win)
                if g.is_empty:
                    continue
                for p in (list(g.geoms) if hasattr(g, "geoms") else [g]):
                    if p.geom_type not in ("LineString", "Polygon") or p.is_empty:
                        continue
                    if p.geom_type == "LineString" and len(p.coords) < 2:
                        continue
                    if p.geom_type == "LineString":
                        px = LineString([((cx - tx) * EXTENT, (cy - ty) * EXTENT) for cx, cy in p.coords])
                    else:
                        px = Polygon([((cx - tx) * EXTENT, (cy - ty) * EXTENT) for cx, cy in p.exterior.coords])
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
    ap.add_argument("--work", type=Path, required=True, help="Arbeitsordner von build_dem_rlp.py (enthält red/)")
    ap.add_argument("--out", type=Path, required=True, help="Zielordner der Kacheln, z. B. web/tiles/klippen")
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("LON0", "LAT0", "LON1", "LAT1"), help="nur dieser Ausschnitt")
    ap.add_argument("--chunk", type=int, default=8, help="Blockgröße in km")
    ap.add_argument("--slope", type=float, default=48.0, help="Mindestneigung in Grad")
    ap.add_argument("--min-cells", type=int, default=6, help="kleinste Steilfläche in Zellen (16 m² je Zelle)")
    ap.add_argument("--min-len", type=float, default=20.0, help="kürzeste Linie in m")
    ap.add_argument("--min-drop", type=float, default=5.0, help="kleinster Höhenunterschied beidseits in m")
    ap.add_argument("--low", type=float, default=40.0, help="untere Hysterese-Schwelle in Grad")
    ap.add_argument("--tol", type=float, default=35.0, help="größte Abweichung der Linie von der Höhenlinie in Grad")
    ap.add_argument("--sigma", type=float, default=0.6, help="Glättung des Höhenfelds in Zellen")
    ap.add_argument("--simplify", type=float, default=4.0, help="Vereinfachung in m")
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
    kw = dict(slope=a.slope, min_cells=a.min_cells, min_len_m=a.min_len, min_drop=a.min_drop, sigma=a.sigma, simplify_m=a.simplify, low=a.low, tol=a.tol)
    jobs = []
    for e0 in range(min(es) - min(es) % a.chunk, max(es) + 1, a.chunk):
        for n0 in range(min(ns) - min(ns) % a.chunk, max(ns) + 1, a.chunk):
            e1, n1 = e0 + a.chunk - 1, n0 + a.chunk - 1
            if any(e0 <= e <= e1 and n0 <= n <= n1 for e, n in have):
                jobs.append((str(red), e0, n0, e1, n1, 1, kw))
    log.info("%d Kilometerkacheln, %d Blöcke, %d Prozesse", len(have), len(jobs), a.jobs)
    lines: list[dict] = []
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
        "params": {"slope_deg": a.slope, "min_cells": a.min_cells, "min_len_m": a.min_len, "min_drop_m": a.min_drop, "sigma": a.sigma, "simplify_m": a.simplify, "low_deg": a.low, "tol_deg": a.tol},
        "lines": len(lines), "tiles": n,
    }
    (a.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.out / "README.txt").write_text("Klippen aus dem Geländemodell (tools/build_klippen_dgm.py). Vektorkacheln Zoom 12, Ebene klippen.\n", encoding="utf-8")
    log.info("fertig: %d Kacheln, %d Linien", n, len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
