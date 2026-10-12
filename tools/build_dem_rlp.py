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


def pixel_lonlat(z: int, x: int, y: int, size: int = 256) -> tuple[np.ndarray, np.ndarray]:
    """Pixelmitten einer Kachel als (lon, lat), je (size, size)."""
    n = 2**z
    f = (np.arange(size) + 0.5) / size
    lon = (x + f) / n * 360.0 - 180.0
    ys = math.pi * (1 - 2 * (y + f) / n)
    lat = np.degrees(np.arctan(np.sinh(ys)))
    return np.broadcast_to(lon[None, :], (size, size)), np.broadcast_to(lat[:, None], (size, size))


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
def reduce_tif(path: Path) -> np.ndarray:
    """GeoTIFF (1000 x 1000, Float32) → uint16 (250 x 250), 0 = keine Daten."""
    import tifffile
    a = tifffile.imread(path).astype(np.float32)
    if a.shape != (1000, 1000):
        raise ValueError(f"unerwartete Größe {a.shape}")
    a[(a <= -9000) | ~np.isfinite(a)] = np.nan
    blocks = a.reshape(CELL, STEP, CELL, STEP)
    ok = np.isfinite(blocks).sum(axis=(1, 3))
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)       # Blöcke ganz ohne Daten ergeben NaN, gewollt
        mean = np.where(ok >= (STEP * STEP) // 2 + 1, np.nanmean(blocks, axis=(1, 3)), np.nan)
    q = np.rint((mean + OFFSET) * SCALE)
    q[~np.isfinite(q) | (q < 1)] = 0
    return np.clip(q, 0, 65535).astype(np.uint16)


def fetch_one(client, item: dict, red_dir: Path) -> str:
    dest = red_dir / f"{item['e']}_{item['n']}.npy"
    if dest.exists():
        return "skip"
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
                arr = reduce_tif(tmp)
            finally:
                tmp.unlink(missing_ok=True)
            np.save(str(dest) + ".tmp.npy", arr)
            os.replace(str(dest) + ".tmp.npy", dest)
            return "ok"
        except Exception as e:  # noqa: BLE001 - Netz, Datei, Format: alles wird gezählt und später wiederholt
            log.warning("%s: %s (Versuch %d)", item["name"], e, attempt + 1)
            time.sleep(2 * (attempt + 1))
    return "fail"


def stage_reduce(items: list[dict], work: Path, budget_s: float) -> tuple[int, int, bool]:
    import httpx
    red = work / "red"
    red.mkdir(parents=True, exist_ok=True)
    todo = [i for i in items if not (red / f"{i['e']}_{i['n']}.npy").exists()]
    log.info("Stufe 1: %d von %d Kacheln fehlen", len(todo), len(items))
    t0, ok, fail = time.monotonic(), 0, 0
    with httpx.Client(headers={"User-Agent": UA}, timeout=120, follow_redirects=False) as client, ThreadPoolExecutor(4) as pool:
        futs = []
        for it in todo:
            futs.append(pool.submit(lambda i=it: fetch_one(client, i, red) if not (budget_s and time.monotonic() - t0 > budget_s) else "later"))
        for k, f in enumerate(futs, 1):
            res = f.result()
            ok += res == "ok"
            fail += res == "fail"
            if k % 200 == 0:
                log.info("  %d/%d (%.0f MB/min geladen)", k, len(todo), ok * 1.5 / max((time.monotonic() - t0) / 60, 1e-9))
    later = sum(1 for i in todo if not (red / f"{i['e']}_{i['n']}.npy").exists())
    return ok, fail, later > 0 and fail == 0 and bool(budget_s)


# ------------------------------------------------------------------ Stufe 2: Kacheln
def sample_state(red: Path, z: int, x: int, y: int, have: set[tuple[int, int]]) -> np.ndarray | None:
    """Zoom-14-Kachel aus dem 4-m-Raster; NaN, wo keine Landesdaten. None, wenn die Kachel gar nichts trifft."""
    from pyproj import Transformer
    lon, lat = pixel_lonlat(z, x, y)
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


def upsample_base(base: Path, z: int, x: int, y: int) -> np.ndarray | None:
    """Kachel (z>12) aus der Mapzen-Kachel Zoom 12 hochgerechnet (bilinear); None, wenn die Basis fehlt."""
    from scipy.ndimage import zoom
    d = z - BASEZ
    s = 2**d
    parent = read_png(base / str(BASEZ) / str(x // s) / f"{y // s}.png")
    if parent is None:
        return None
    size = 256 // s
    cx, cy = (x % s) * size, (y % s) * size
    # eine Zeile/Spalte Rand mitnehmen, damit die Ränder zwischen Nachbarkacheln gleich werden
    pad = np.pad(parent, 1, mode="edge")
    crop = pad[cy:cy + size + 2, cx:cx + size + 2]
    up = zoom(crop, 256 / size, order=1, mode="nearest")
    off = int(round(256 / size))
    return up[off:off + 256, off:off + 256].astype(np.float32)


def touches(z: int, x: int, y: int, have: set[tuple[int, int]]) -> bool:
    """Trifft die Kachel (grob, 5 x 5 Stützpunkte plus Rand) mindestens eine 1-km-Kachel mit Landesdaten?"""
    from pyproj import Transformer
    n = 2**z
    fx, fy = np.linspace(0, 1, 5), np.linspace(0, 1, 5)
    lon = ((x + fx) / n * 360.0 - 180.0)[None, :].repeat(5, 0)
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (y + fy) / n))))[:, None].repeat(5, 1)
    e, nn = Transformer.from_crs(4326, 25832, always_xy=True).transform(lon, lat)
    k0, k1 = int(math.floor((e.min() - STEP) / 1000)), int(math.floor((e.max() + STEP) / 1000))
    m0, m1 = int(math.floor((nn.min() - STEP) / 1000)), int(math.floor((nn.max() + STEP) / 1000))
    return any((a, b) in have for a in range(k0, k1 + 1) for b in range(m0, m1 + 1))


def build_top(args: tuple) -> tuple[int, int, str]:
    """Zoom-14-Kachel schreiben. Rückgabe (x, y, "state"|"base"|"none")."""
    x, y, red_s, base_s, out_s, have, force = args
    red, base, out = Path(red_s), Path(base_s), Path(out_s)
    dest = out / str(MAXZ) / str(x) / f"{y}.png"
    if dest.exists() and not force:
        return x, y, "keep"
    st = sample_state(red, MAXZ, x, y, have)
    fallback = upsample_base(base, MAXZ, x, y)
    if st is None and fallback is None:
        return x, y, "none"
    if st is None:
        write_png(dest, fallback)
        return x, y, "base"
    if fallback is not None:
        st = np.where(np.isfinite(st), st, fallback)
    if np.isnan(st).all():
        return x, y, "none"
    write_png(dest, np.nan_to_num(st, nan=0.0))
    return x, y, "state"


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
                force: bool, budget_s: float, region) -> tuple[bool, dict]:
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
    jobs = [(x, y, str(red), str(base), str(out), items_have, force) for x, y in cand]
    stats = {"state": 0, "base": 0, "none": 0, "keep": 0}
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
    touched_by_z: dict[int, set[tuple[int, int]]] = {13: {(x // 2, y // 2) for x, y in cand if touches(MAXZ, x, y, items_have)}}
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
    ok, fail, more = stage_reduce(items, a.work, a.budget_s)
    log.info("Stufe 1: %d geladen, %d fehlgeschlagen", ok, fail)
    if fail:
        return 1
    if more:
        return 2
    red = a.work / "red"
    have = {(i["e"], i["n"]) for i in items if (red / f"{i['e']}_{i['n']}.npy").exists()}
    done, stats = stage_tiles(have, bbox, a.work, a.base, a.out, a.force, a.budget_s, region)
    log.info("Stufe 2: %s", stats)
    if not done:
        return 2
    years = [i["year"] for i in items if (i["e"], i["n"]) in have] or [0]
    meta = {"attribution": attribution(years), "source": "LVermGeoRP DGM1", "licence": "dl-de/by-2-0", "years": [min(years), max(years)],
            "built": time.strftime("%Y-%m-%d"), "max_zoom": MAXZ, "bbox": list(bbox)}
    (a.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
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
