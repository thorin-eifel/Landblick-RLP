#!/usr/bin/env python3
"""Höhenkacheln aus dem Landes-DGM1 bauen (Terrarium-Kodierung, Zoom 6 bis 14), Mapzen nur als Rückfall.

Zweck:      Das Landesamt für Vermessung und Geobasisinformation RLP gibt sein Geländemodell DGM1 (1 m Gitter,
            Laserscanning) als offene Daten ab. Dieses Werkzeug rechnet es auf Web-Mercator-Kacheln um, die
            relief.js genauso liest wie bisher die Mapzen-Kacheln: Schummerung, Höhenfärbung, Höhenlinien, Höhe unter
            dem Zeiger. Innerhalb von Rheinland-Pfalz stammt jede Höhe vom Land, außerhalb bleibt Mapzen
            (EU-DEM/SRTM, rund 30 m), bis dort gleichwertige offene Daten eingebaut sind.
Quelle:     https://geobasis-rlp.de/data/dgm1/current/  (Dateiliste: meta4/dgm1_tif_07.meta4, rund 21 000 Kacheln
            zu 1 km², GeoTIFF Float32, EPSG:25832, zusammen rund 32 GB).
Lizenz:     Datenlizenz Deutschland, Namensnennung 2.0 (dl-de/by-2-0). Vermerk, der in die Karte kommt:
            „© GeoBasis-DE / LVermGeoRP <Jahre>, dl-de/by-2-0, www.lvermgeo.rlp.de [Daten bearbeitet]“ (meta.json).
Ablauf:     1. reduce   – jede 1-km-Kachel laden, Prüfsumme prüfen, auf 4 m mitteln, kompakt ablegen (work/red/).
                          Die Originale werden nicht aufgehoben. Wiederaufnehmbar, 4 Abrufe gleichzeitig.
            2. tiles    – Zoom 14 aus dem 4-m-Raster, Lücken und Außenbereich aus Mapzen (Zoom 12 hochgerechnet);
                          Zoom 13 bis 6 durch Mitteln der Kinder, wo es Landesdaten gibt, sonst Mapzen unverändert.
Aufruf:     python tools/build_dem_rlp.py --check                      zählen, Größe schätzen
            python tools/build_dem_rlp.py --bbox 6.3 49.75 6.6 49.95   nur ein Ausschnitt (Test)
            python tools/build_dem_rlp.py                              alles (Stunden, Exit 2 = wiederholen)
            python tools/build_dem_rlp.py --budget-s 600               in Portionen
            python tools/build_dem_rlp.py --no-fetch --force --only-gaps   Rand und Außenbereich neu, ohne Download (nach Änderung am Hochrechnen)
Voraussetzung: web/tiles/dem-base/ mit Mapzen-Kacheln Zoom 6 bis 12 (python tools/build_dem.py), pip install
            -r requirements-tools.txt (numpy, pillow, pyproj, tifffile, imagecodecs).
Höflichkeit: ehrlicher User-Agent, 4 gleichzeitige Abrufe, vorhandene Dateien werden übersprungen.
Exit:       0 = fertig, 1 = Fehler/Kacheln fehlen, 2 = Zeitbudget aufgebraucht, bitte wiederholen
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import re
import shutil
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LIST_URL = "https://geobasis-rlp.de/data/dgm1/current/meta4/dgm1_tif_07.meta4"
UA = "Landblick/1.0 (DGM1 one-off fetch; contact via www.ctw.example)"
NODATA = -9999.0
STEP = 4              # Mittelung 4 x 4 Pixel: 1 m -> 4 m; Zoom 14 hat rund 6 m je Pixel
CELL = 1000 // STEP   # 250 Pixel je Kilometer
OFFSET, SCALE = 200.0, 10.0   # uint16 = (h + 200) * 10, 0 = keine Daten
RAW_SCALE = 50.0              # Rohkacheln für die Felswände (--keep-raw): uint16 = (h + 200) * 50, wie in build_klippen_dgm.py
MAXZ, MINZ, BASEZ = 14, 6, 12
log = logging.getLogger("dem_rlp")


# ------------------------------------------------------------------ Terrarium
def encode_terrarium(h: np.ndarray) -> np.ndarray:
    """Höhen (m) → RGB-Bytes (H, W, 3); v = h + 32768, R = v/256, G = v mod 256, B = Bruchteil."""
    v = np.clip(h.astype(np.float64) + 32768.0, 0, 65535.996)
    r = np.floor(v / 256.0)
    g = np.floor(v - r * 256.0)
    b = np.floor((v - np.floor(v)) * 256.0)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def decode_terrarium(rgb: np.ndarray) -> np.ndarray:
    a = rgb[..., :3].astype(np.float64)
    return (a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0).astype(np.float32)


def read_png(path: Path) -> np.ndarray | None:
    from PIL import Image
    try:
        with Image.open(path) as im:
            return decode_terrarium(np.asarray(im.convert("RGB")))
    except (OSError, ValueError):
        return None


def write_png(path: Path, h: np.ndarray) -> None:
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    Image.fromarray(encode_terrarium(h), "RGB").save(tmp, format="PNG", compress_level=3)
    tmp.replace(path)


# ------------------------------------------------------------------ Kachelgeometrie
def tile_xy(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def pixel_lonlat(z: int, x: int, y: int, size: int = 256, margin: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Pixelmitten einer Kachel als (lon, lat), je (size + 2 * margin) im Quadrat. `margin` Pixel Rand rundum (Nachbarkacheln)."""
    n = 2**z
    f = (np.arange(-margin, size + margin) + 0.5) / size
    lon = (x + f) / n * 360.0 - 180.0
    ys = math.pi * (1 - 2 * (y + f) / n)
    lat = np.degrees(np.arctan(np.sinh(ys)))
    side = size + 2 * margin
    return np.broadcast_to(lon[None, :], (side, side)), np.broadcast_to(lat[:, None], (side, side))


# ------------------------------------------------------------------ Dateiliste
FILE_RE = re.compile(
    r'<file name="(?P<name>dgm1_32_(?P<e>\d+)_(?P<n>\d+)_1_rp_\d{4}\.tif)">\s*<size>(?P<size>\d+)</size>\s*'
    r'<hash type="sha-256">(?P<sha>[0-9a-f]{64})</hash>\s*<url>(?P<url>https://geobasis-rlp\.de/[^<]+)</url>')


def parse_meta4(text: str) -> list[dict]:
    """Dateiliste lesen. Nur Adressen auf geobasis-rlp.de werden übernommen."""
    out = []
    for m in FILE_RE.finditer(text):
        out.append({"name": m["name"], "e": int(m["e"]), "n": int(m["n"]), "size": int(m["size"]), "sha": m["sha"], "url": m["url"],
                    "year": int(m["name"][-8:-4])})
    return out


def utm_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """(lon0, lat0, lon1, lat1) → (E0, N0, E1, N1) in EPSG:25832, Rand abgetastet."""
    from pyproj import Transformer
    t = Transformer.from_crs(4326, 25832, always_xy=True)
    lon0, lat0, lon1, lat1 = bbox
    ls = np.linspace(0, 1, 21)
    lon = np.concatenate([lon0 + (lon1 - lon0) * ls, np.full(21, lon1), lon0 + (lon1 - lon0) * ls, np.full(21, lon0)])
    lat = np.concatenate([np.full(21, lat0), lat0 + (lat1 - lat0) * ls, np.full(21, lat1), lat0 + (lat1 - lat0) * ls])
    e, n = t.transform(lon, lat)
    return float(min(e)), float(min(n)), float(max(e)), float(max(n))


# ------------------------------------------------------------------ Stufe 1: reduzieren
def read_tif(path: Path) -> np.ndarray:
    """GeoTIFF → Float32 (1000 x 1000), Meter, -9999 = keine Daten (unverändert)."""
    import tifffile
    a = tifffile.imread(path).astype(np.float32)
    if a.shape == (1001, 1001):      # Lieferungen ab 2024: eine Zeile/Spalte Überlapp → unten/rechts abschneiden (≤ 1 m Versatz)
        a = a[:1000, :1000]
    if a.shape != (1000, 1000):
        raise ValueError(f"unerwartete Größe {a.shape}")
    return a


def raw_u16(a: np.ndarray) -> np.ndarray:
    """1-m-Raster → uint16 (1000 x 1000) im Format der Rohkacheln von tools/build_klippen_dgm.py (RAW_SCALE muss dort stimmen), 0 = keine Daten."""
    bad = (a <= -9000) | ~np.isfinite(a)
    q = np.rint((np.where(bad, 0, a) + OFFSET) * RAW_SCALE)
    q[bad | (q < 1)] = 0
    return np.clip(q, 0, 65535).astype(np.uint16)


def reduce_tif(path: Path) -> np.ndarray:
    """GeoTIFF (1000 x 1000, Float32) → uint16 (250 x 250), 0 = keine Daten."""
    return reduce_array(read_tif(path))


def reduce_array(a: np.ndarray) -> np.ndarray:
    """Float32 (1000 x 1000) → uint16 (250 x 250). Ändert a nicht."""
    a = a.copy()
    a[(a <= -9000) | ~np.isfinite(a)] = np.nan
    blocks = a.reshape(CELL, STEP, CELL, STEP)
    ok = np.isfinite(blocks).sum(axis=(1, 3))
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # Blöcke ganz ohne Daten ergeben NaN, gewollt
        mean = np.where(ok >= (STEP * STEP) // 2 + 1, np.nanmean(blocks, axis=(1, 3)), np.nan)
    q = np.rint((mean + OFFSET) * SCALE)
    q[~np.isfinite(q) | (q < 1)] = 0
    return np.clip(q, 0, 65535).astype(np.uint16)


def fetch_one(client, item: dict, red_dir: Path, raw_dir: Path | None = None) -> str:
    dest = red_dir / f"{item['e']}_{item['n']}.npy"
    if dest.exists():
        return "skip"   # Kacheln ohne Rohkachel holt build_klippen_dgm.py bei Bedarf selbst nach
    for attempt in range(4):
        try:
            r = client.get(item["url"])
            if r.status_code != 200:
                raise OSError(f"HTTP {r.status_code}")
            if hashlib.sha256(r.content).hexdigest() != item["sha"]:
                raise OSError("Prüfsumme stimmt nicht")
            tmp = red_dir / f".{item['e']}_{item['n']}.tif"
            tmp.write_bytes(r.content)
            try:
                full = read_tif(tmp)
            finally:
                tmp.unlink(missing_ok=True)
            arr = reduce_array(full)
            if raw_dir is not None:     # dieselben Bytes auch als Rohkachel ablegen: spart den zweiten Download für die Felswände
                rtmp = raw_dir / f".{item['e']}_{item['n']}.tmp.npz"
                np.savez_compressed(rtmp, a=raw_u16(full))
                os.replace(rtmp, raw_dir / f"{item['e']}_{item['n']}.npz")
            np.save(str(dest) + ".tmp.npy", arr)
            os.replace(str(dest) + ".tmp.npy", dest)
            return "ok"
        except Exception as e:  # noqa: BLE001 - Netz, Datei, Format: alles wird gezählt und später wiederholt
            log.warning("%s: %s (Versuch %d)", item["name"], e, attempt + 1)
            time.sleep(2 * (attempt + 1))
    return "fail"


def stage_reduce(items: list[dict], work: Path, budget_s: float, keep_raw: bool = False) -> tuple[int, int, bool]:
    import httpx
    red = work / "red"
    red.mkdir(parents=True, exist_ok=True)
    raw = work / "raw" if keep_raw else None
    if raw is not None:
        raw.mkdir(parents=True, exist_ok=True)
    todo = [i for i in items if not (red / f"{i['e']}_{i['n']}.npy").exists()]
    log.info("Stufe 1: %d von %d Kacheln fehlen", len(todo), len(items))
    t0, ok, fail = time.monotonic(), 0, 0
    with httpx.Client(headers={"User-Agent": UA}, timeout=120, follow_redirects=False) as client, ThreadPoolExecutor(4) as pool:
        futs = []
        for it in todo:
            futs.append(pool.submit(lambda i=it: fetch_one(client, i, red, raw) if not (budget_s and time.monotonic() - t0 > budget_s) else "later"))
        for k, f in enumerate(futs, 1):
            res = f.result()
            ok += res == "ok"
            fail += res == "fail"
            if k % 200 == 0:
                log.info("  %d/%d (%.0f MB/min geladen)", k, len(todo), ok * 1.5 / max((time.monotonic() - t0) / 60, 1e-9))
    later = sum(1 for i in todo if not (red / f"{i['e']}_{i['n']}.npy").exists())
    return ok, fail, later > 0 and fail == 0 and bool(budget_s)


# ------------------------------------------------------------------ Stufe 2: Kacheln
def sample_state(red: Path, z: int, x: int, y: int, have: set[tuple[int, int]], margin: int = 0) -> np.ndarray | None:
    """Zoom-14-Kachel aus dem 4-m-Raster; NaN, wo keine Landesdaten. None, wenn die Kachel (mit `margin` Pixel Rand) gar nichts trifft."""
    from pyproj import Transformer
    lon, lat = pixel_lonlat(z, x, y, margin=margin)
    e, n = Transformer.from_crs(4326, 25832, always_xy=True).transform(lon, lat)
    k0, k1 = int(math.floor((e.min() - STEP) / 1000)), int(math.floor((e.max() + STEP) / 1000))
    m0, m1 = int(math.floor((n.min() - STEP) / 1000)), int(math.floor((n.max() + STEP) / 1000))
    if not any((a, b) in have for a in range(k0, k1 + 1) for b in range(m0, m1 + 1)):
        return None
    w, h = (k1 - k0 + 1) * CELL, (m1 - m0 + 1) * CELL
    mos = np.zeros((h, w), np.uint16)
    for a in range(k0, k1 + 1):
        for b in range(m0, m1 + 1):
            if (a, b) in have:
                c0, r0 = (a - k0) * CELL, (m1 - b) * CELL
                mos[r0:r0 + CELL, c0:c0 + CELL] = np.load(red / f"{a}_{b}.npy")
    fl = mos.astype(np.float32)
    fl[mos == 0] = np.nan
    fl = fl / SCALE - OFFSET
    fc = (e - k0 * 1000) / STEP - 0.5
    fr = ((m1 + 1) * 1000 - n) / STEP - 0.5
    c0, r0 = np.clip(np.floor(fc).astype(int), 0, w - 2), np.clip(np.floor(fr).astype(int), 0, h - 2)
    dx, dy = np.clip(fc - c0, 0, 1), np.clip(fr - r0, 0, 1)
    v = (fl[r0, c0] * (1 - dx) * (1 - dy) + fl[r0, c0 + 1] * dx * (1 - dy) + fl[r0 + 1, c0] * (1 - dx) * dy + fl[r0 + 1, c0 + 1] * dx * dy)
    return v.astype(np.float32)


_BCACHE: dict = {}


def _base_png(base: Path, x: int, y: int) -> np.ndarray | None:
    key = (str(base), x, y)
    if key not in _BCACHE:
        if len(_BCACHE) > 48:
            _BCACHE.pop(next(iter(_BCACHE)))
        _BCACHE[key] = read_png(base / str(BASEZ) / str(x) / f"{y}.png")
    return _BCACHE[key]


def upsample_base(base: Path, z: int, x: int, y: int, margin: int = 0) -> np.ndarray | None:
    """Kachel (z > 12) aus den Mapzen-Kacheln Zoom 12 hochgerechnet (bilinear); None, wenn die Basis fehlt.

    Die Pixelmitten der Zielkachel werden im Pixelraster der Basis gesucht, in einem Mosaik aus der Basiskachel und ihren
    acht Nachbarn. So schließen benachbarte Zielkacheln ohne Stufe aneinander an. (Ein Hochskalieren der einzelnen Kachel
    mit scipy.ndimage.zoom richtet Eck- statt Mittelpunkte aus und liefert an jeder Kachelgrenze einen Sprung, den die
    Schummerung als gerade Linie zeigt.)"""
    from scipy.ndimage import distance_transform_edt, map_coordinates
    s = 2 ** (z - BASEZ)
    bx, by = x // s, y // s
    if _base_png(base, bx, by) is None:
        return None
    rows = []
    for dy in (-1, 0, 1):
        row = []
        for dx in (-1, 0, 1):
            t = _base_png(base, bx + dx, by + dy)
            row.append(t if t is not None else np.full((256, 256), np.nan, np.float32))
        rows.append(np.concatenate(row, axis=1))
    m = np.concatenate(rows, axis=0)
    bad = np.isnan(m)
    if bad.any():                                         # Nachbar fehlt (Rand der Abdeckung): nächsten gültigen Wert fortsetzen
        idx = distance_transform_edt(bad, return_distances=False, return_indices=True)
        m = m[tuple(idx)]
    f = (np.arange(-margin, 256 + margin) + 0.5) / s - 0.5   # Pixelmitte der Zielkachel (mit Rand) im Raster der Basis
    col = 256 + (x - bx * s) * (256 // s) + f
    row_ = 256 + (y - by * s) * (256 // s) + f
    rr, cc = np.meshgrid(row_, col, indexing="ij")
    return map_coordinates(m, [rr, cc], order=1, mode="nearest", prefilter=False).astype(np.float32)


def touches(z: int, x: int, y: int, have: set[tuple[int, int]], margin_m: float = STEP) -> bool:
    """Trifft die Kachel (grob, 5 x 5 Stützpunkte plus Rand von `margin_m` Metern) mindestens eine 1-km-Kachel mit Landesdaten?"""
    from pyproj import Transformer
    n = 2**z
    fx, fy = np.linspace(0, 1, 5), np.linspace(0, 1, 5)
    lon = ((x + fx) / n * 360.0 - 180.0)[None, :].repeat(5, 0)
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (y + fy) / n))))[:, None].repeat(5, 1)
    e, nn = Transformer.from_crs(4326, 25832, always_xy=True).transform(lon, lat)
    k0, k1 = int(math.floor((e.min() - margin_m) / 1000)), int(math.floor((e.max() + margin_m) / 1000))
    m0, m1 = int(math.floor((nn.min() - margin_m) / 1000)), int(math.floor((nn.max() + margin_m) / 1000))
    return any((a, b) in have for a in range(k0, k1 + 1) for b in range(m0, m1 + 1))


FADE_PX = 120          # Länge des Ausgleichs außerhalb der Landesdaten in Zoom-14-Pixeln (rund 730 m)


def blend_bias(st: np.ndarray, fb: np.ndarray, fade_px: int = FADE_PX) -> np.ndarray:
    """Landesdaten `st` (NaN = keine) durch `fb` (Mapzen) ergänzen, ohne Stufe am Rand der Landesdaten.

    Mapzen weicht vom Landes-DGM1 um viele Meter ab (Messung Irrel: im Mittel 9,6 m). Ein hartes Umschalten setzt am Rand der
    Abdeckung eine Stufe, die die Schummerung als gerade Linie und die Höhenlinien als gedrängtes Band zeigen. Darum wird der
    Versatz (st - fb) am Rand nach außen fortgesetzt und über `fade_px` Pixel auf null geführt (cos², Steigung null am Rand
    und am Ende). Innerhalb der Landesdaten bleibt jede Höhe unverändert. Das Ergebnis hängt nur von Pixeln im Abstand
    `fade_px` ab; Kacheln mit mindestens so großem Rand schließen deshalb ohne Sprung aneinander an."""
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    fin = np.isfinite(st)
    if fin.all() or not fin.any():
        return np.where(fin, st, fb)
    w = fin.astype(np.float32)
    diff = np.where(fin, st - fb, 0.0).astype(np.float32)
    near = gaussian_filter(diff * w, 3) / np.maximum(gaussian_filter(w, 3), 1e-6)          # Versatz, leicht geglättet
    dist, idx = distance_transform_edt(~fin, return_indices=True)
    field = np.where(fin, near, near[idx[0], idx[1]])                                       # nach außen fortgesetzt
    field = gaussian_filter(field, 5)                                                       # keine Streifen quer zum Rand
    fade = np.where(dist < fade_px, np.cos(0.5 * math.pi * np.clip(dist / fade_px, 0, 1)) ** 2, 0.0)
    return np.where(fin, st, fb + field * fade).astype(np.float32)


def build_top(args: tuple) -> tuple[int, int, str]:
    """Zoom-14-Kachel schreiben. Rückgabe (x, y, "state"|"edge"|"base"|"none"|"keep"); "edge" = Kachel ohne eigene Landesdaten im Ausgleichsstreifen."""
    x, y, red_s, base_s, out_s, have, force, only_gaps = args
    red, base, out = Path(red_s), Path(base_s), Path(out_s)
    dest = out / str(MAXZ) / str(x) / f"{y}.png"
    if dest.exists() and not force:
        return x, y, "keep"
    m = FADE_PX
    inner = (slice(m, m + 256), slice(m, m + 256))
    st_h = sample_state(red, MAXZ, x, y, have, margin=m)        # mit Rand: der Ausgleich am Rand der Landesdaten braucht die Nachbarschaft
    st = None if st_h is None else st_h[inner]
    if only_gaps and st is not None and np.isfinite(st).all():
        return x, y, "keep"                                # reine Landesdaten: unverändert lassen
    fb_h = upsample_base(base, MAXZ, x, y, margin=m)
    fallback = None if fb_h is None else fb_h[inner]
    if st_h is None or not np.isfinite(st_h).any():
        if fallback is None:
            return x, y, "none"
        write_png(dest, fallback)
        return x, y, "base"
    if fb_h is not None:
        full = blend_bias(st_h, fb_h)[inner]
    else:
        full = st
    if np.isnan(full).all():
        return x, y, "none"
    write_png(dest, np.nan_to_num(full, nan=0.0))
    return x, y, "state" if st is not None and np.isfinite(st).any() else "edge"


def merge_children(out: Path, base: Path, z: int, x: int, y: int, touched: set[tuple[int, int]] | None = None) -> np.ndarray | None:
    """Kachel aus den vier Kindern (Zoom z+1) mitteln. Ab Zoom 12 darunter kommen Kinder ohne Landesdaten (nicht in
    `touched`) unverändert aus Mapzen; None, wenn ein Kind fehlt."""
    big = np.zeros((512, 512), np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            cx, cy = 2 * x + dx, 2 * y + dy
            use_base = z + 1 <= BASEZ and touched is not None and (cx, cy) not in touched
            c = read_png((base if use_base else out) / str(z + 1) / str(cx) / f"{cy}.png")
            if c is None and z + 1 <= BASEZ:
                c = read_png(base / str(z + 1) / str(cx) / f"{cy}.png")      # Kind (noch) nicht gebaut: Mapzen
            elif c is None:
                c = upsample_base(base, z + 1, cx, cy)                      # Zoom 13/14 außerhalb des Gebiets: hochgerechnet
            if c is None:
                return None
            big[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = c
    return big.reshape(256, 2, 256, 2).mean(axis=(1, 3))


def stage_tiles(items_have: set[tuple[int, int]], bbox: tuple[float, float, float, float], work: Path, base: Path, out: Path,
                force: bool, budget_s: float, region, only_gaps: bool = False) -> tuple[bool, dict]:
    t0 = time.monotonic()
    red = work / "red"
    lon0, lat0, lon1, lat1 = bbox
    x0, y1 = tile_xy(lon0, lat0, MAXZ)
    x1, y0 = tile_xy(lon1, lat1, MAXZ)
    cand = []
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            lo, la = pixel_lonlat(MAXZ, x, y, 1)
            if region is None or region.contains(float(la[0, 0]), float(lo[0, 0]), margin_km=6):
                cand.append((x, y))
    log.info("Stufe 2: %d Zoom-14-Kacheln im Gebiet", len(cand))
    jobs = [(x, y, str(red), str(base), str(out), items_have, force, only_gaps) for x, y in cand]
    stats = {"state": 0, "edge": 0, "base": 0, "none": 0, "keep": 0}
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 2) - 0)) as pool:
        for k, (x, y, kind) in enumerate(pool.map(build_top, jobs, chunksize=16), 1):
            stats[kind] += 1
            if k % 500 == 0:
                log.info("  %d/%d  %s", k, len(jobs), stats)
            if budget_s and time.monotonic() - t0 > budget_s:
                return False, stats
    # Zoom 13: für alle Eltern im Gebiet aus den Zoom-14-Kindern (außerhalb also Mapzen, hochgerechnet)
    z13 = {(x // 2, y // 2) for x, y in cand}
    for x, y in sorted(z13):
        dest = out / "13" / str(x) / f"{y}.png"
        if force or not dest.exists():
            m = merge_children(out, base, 13, x, y)
            if m is not None:
                write_png(dest, m)
    # Zoom 12 bis 6: nur dort mitteln, wo Landesdaten liegen; der Rest kommt unverändert aus Mapzen
    touched_by_z: dict[int, set[tuple[int, int]]] = {13: {(x // 2, y // 2) for x, y in cand if touches(MAXZ, x, y, items_have, FADE_PX * 6.2)}}
    lvl = touched_by_z[13]   # Zoom 13 mit Landesdaten
    for z in range(BASEZ, MINZ - 1, -1):
        lvl = {(x // 2, y // 2) for x, y in lvl}
        touched_by_z[z] = lvl
    written = 0
    for z in range(BASEZ, MINZ - 1, -1):
        for x, y in sorted(touched_by_z[z]):
            dest = out / str(z) / str(x) / f"{y}.png"
            if dest.exists() and not force:
                continue
            m = merge_children(out, base, z, x, y, touched_by_z.get(z + 1) if z < BASEZ else None)
            if m is not None:
                write_png(dest, m)
                written += 1
        log.info("  Zoom %d: %d Kacheln aus Landesdaten", z, len(touched_by_z[z]))
    # Rest unverändert aus Mapzen übernehmen
    copied = 0
    for z in range(MINZ, BASEZ + 1):
        zdir = base / str(z)
        if not zdir.exists():
            continue
        for p in zdir.rglob("*.png"):
            target = out / p.relative_to(base)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, target)
                copied += 1
    stats["merged"], stats["copied"] = written, copied
    return True, stats


# ------------------------------------------------------------------ Hauptprogramm
def attribution(years: list[int]) -> str:
    lo, hi = min(years), max(years)
    jahre = str(lo) if lo == hi else f"{lo}–{hi}"
    return (f"Höhen in Rheinland-Pfalz: © GeoBasis-DE / LVermGeoRP {jahre}, dl-de/by-2-0, www.lvermgeo.rlp.de [Daten bearbeitet]; "
            "außerhalb: EU-DEM (Copernicus, EU) und SRTM (NASA) über Mapzen Terrain Tiles")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("LON0", "LAT0", "LON1", "LAT1"), help="nur dieser Ausschnitt")
    ap.add_argument("--work", type=Path, default=ROOT / "_scratch" / "dgm1", help="Arbeitsordner (4-m-Raster, Dateiliste)")
    ap.add_argument("--base", type=Path, default=ROOT / "web" / "tiles" / "dem-base", help="Mapzen-Kacheln Zoom 6 bis 12")
    ap.add_argument("--out", type=Path, default=ROOT / "web" / "tiles" / "dem", help="Zielordner für die Kacheln")
    ap.add_argument("--region", type=Path, default=ROOT / "region.yaml")
    ap.add_argument("--check", action="store_true", help="nur zählen")
    ap.add_argument("--force", action="store_true", help="vorhandene Kacheln neu schreiben")
    ap.add_argument("--keep-raw", action="store_true", help="1-m-Rohkacheln zusätzlich in <work>/raw/ ablegen (rund 22 GB für RLP), damit build_klippen_dgm.py nicht ein zweites Mal lädt")
    ap.add_argument("--no-fetch", action="store_true", help="nichts laden: nur mit den vorhandenen 4-m-Rasterkacheln in work/red/ arbeiten")
    ap.add_argument("--only-gaps", action="store_true",
                    help="Zoom-14-Kacheln mit reinen Landesdaten unverändert lassen, nur Rand und Außenbereich neu schreiben (mit --force)")
    ap.add_argument("--budget-s", type=float, default=0, help="Zeitbudget je Stufe, 0 = unbegrenzt")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from app import region as regmod
    region = regmod.load(a.region)
    s, w, n, e = region.bbox
    bbox = tuple(a.bbox) if a.bbox else (w, s, e, n)
    a.work.mkdir(parents=True, exist_ok=True)
    listing = a.work / "dgm1_tif_07.meta4"
    if not listing.exists() or time.time() - listing.stat().st_mtime > 7 * 86400:
        import httpx
        r = httpx.get(LIST_URL, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        listing.write_bytes(r.content)
    items_all = parse_meta4(listing.read_text(encoding="utf-8"))
    if not items_all:
        log.error("Dateiliste leer oder Format geändert: %s", listing)
        return 1
    E0, N0, E1, N1 = utm_bbox(bbox)
    # Kachel-Index: 1 km² mit linker unterer Ecke (e, n) in km; 6 km Rand für Zoom-14-Nachbarn
    items = [i for i in items_all if E0 / 1000 - 6 <= i["e"] <= E1 / 1000 + 6 and N0 / 1000 - 6 <= i["n"] <= N1 / 1000 + 6]
    gb = sum(i["size"] for i in items) / 1e9
    print(f"{len(items)} DGM1-Kacheln im Ausschnitt ({len(items_all)} landesweit), {gb:.1f} GB Download")
    if a.check:
        top = (tile_xy(bbox[2], bbox[3], MAXZ)[0] - tile_xy(bbox[0], bbox[1], MAXZ)[0] + 1) * (tile_xy(bbox[0], bbox[1], MAXZ)[1] - tile_xy(bbox[2], bbox[3], MAXZ)[1] + 1)
        print(f"bis zu {top} Kacheln Zoom 14 im Rechteck")
        return 0
    if not (a.base / str(BASEZ)).exists():
        log.error("Mapzen-Kacheln fehlen: %s (zuerst python tools/build_dem.py --dest %s)", a.base, a.base)
        return 1
    if a.no_fetch:
        log.info("Stufe 1 übersprungen (--no-fetch)")
    else:
        ok, fail, more = stage_reduce(items, a.work, a.budget_s, a.keep_raw)
        log.info("Stufe 1: %d geladen, %d fehlgeschlagen", ok, fail)
        if fail:
            return 1
        if more:
            return 2
    red = a.work / "red"
    have = {(i["e"], i["n"]) for i in items if (red / f"{i['e']}_{i['n']}.npy").exists()}
    done, stats = stage_tiles(have, bbox, a.work, a.base, a.out, a.force, a.budget_s, region, a.only_gaps)
    log.info("Stufe 2: %s", stats)
    if not done:
        return 2
    years = [i["year"] for i in items if (i["e"], i["n"]) in have] or [0]
    meta = {"attribution": attribution(years), "source": "LVermGeoRP DGM1", "licence": "dl-de/by-2-0", "years": [min(years), max(years)],
            "built": time.strftime("%Y-%m-%d"), "max_zoom": MAXZ, "bbox": list(bbox)}
    old = a.out / "meta.json"
    if old.exists():                                       # Eintrag der Zoom-15/16-Kacheln (build_dem_hires.py) nicht verlieren
        try:
            hires = json.loads(old.read_text(encoding="utf-8")).get("hires")
        except (OSError, ValueError):
            hires = None
        if hires:
            meta["hires"] = hires
    old.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    size = sum(p.stat().st_size for p in a.out.rglob("*.png")) / 1e6
    (a.out / "README.txt").write_text(
        "Höhenkacheln (Terrarium-Kodierung), Zoom 6 bis 14.\n"
        "Rheinland-Pfalz: DGM1 des Landesamts für Vermessung und Geobasisinformation, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet].\n"
        "Außerhalb und in Lücken: Mapzen Terrain Tiles auf AWS Open Data (EU-DEM, SRTM), oberhalb Zoom 12 nur hochgerechnet.\n"
        f"Erzeugt mit tools/build_dem_rlp.py, {size:.0f} MB.\n", encoding="utf-8")
    print(f"fertig: {size:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
