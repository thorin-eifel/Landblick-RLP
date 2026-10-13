#!/usr/bin/env python3
"""Abflussbahnen und Geländesenken aus dem Höhenmodell: Vektorkacheln für die Ebene "Starkregen und Abfluss".

Zweck:      Zeigt, wohin Wasser vom Hang läuft, wenn es stark regnet: Linien nach Größe des Einzugsgebiets (oberhalb der Zelle liegende
            Fläche) und Senken mit Fassungsvolumen. Es ist eine Rechnung aus dem Gelände, kein amtliches Gefahrenkartenwerk: Durchlässe,
            Brücken, Gräben, Kanalisation, Boden und Bewuchs kennt sie nicht.
Quelle:     Terrarium-Höhenkacheln Zoom 14 der Karte (tools/build_dem_rlp.py; in Rheinland-Pfalz aus dem DGM1, © GeoBasis-DE / LVermGeoRP,
            dl-de/by-2-0, Daten bearbeitet). Rechengitter = Zoom-14-Pixel, rund 6 m.
Verfahren:  1. Kacheln zu einem Raster zusammensetzen (fehlende Kacheln = keine Daten)
            2. tools/abfluss_kern.c: Senken füllen (Priority-Flood), Abflussrichtung D8, Fläche stromab summieren
            3. Zellen oberhalb einer Schwelle je Zoomstufe zu Linien verketten (Kettenenden an Zusammenflüssen), an Zoom-14-Kachelgrenzen
               geteilt, vereinfacht; Senken ab einer Mindestmenge als Punkte mit Volumen. Nur Zellen innerhalb der Landesgrenze.
Ausgabe:    PMTiles mit den Ebenen `abfluss` (Linien: k = Größenklasse 0..6, ha = Einzugsgebiet in Hektar) und `senken` (Punkte: v = Volumen m³,
            d = größte Tiefe in cm, ha = Fläche in Zehntel Hektar)
Aufruf:     python tools/build_abfluss.py --dem-dir perf-rlp/tiles/dem --bbox 6.15 49.55 6.85 50.15 --grenze web/geo/rlp.geojson \\
                --out perf-rlp/tiles/abfluss.pmtiles --work /tmp/abfluss-work
Parameter:  --zoom-min 9 --zoom-max 14   Zoomstufen der Kacheln; Schwellen siehe SCHWELLE_HA
            --bbox W S E N               Rechengebiet. Am Rand fehlt der Zufluss von außen: dort sind Einzugsgebiete zu klein
Speicher:   rund 30 Byte je Zelle (87 Millionen Zellen ≈ 2,6 GB)
Exit:       0 = fertig, 1 = Fehler
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

log = logging.getLogger("osint.abfluss")
HERE = Path(__file__).resolve().parent
ZGRID = 14
EXTENT = 4096
EARTH = 40075016.686
DX = np.array([1, 1, 0, -1, -1, -1, 0, 1])
DY = np.array([0, 1, 1, 1, 0, -1, -1, -1])
# Einzugsgebiet (ha), ab dem eine Zelle auf dieser Zoomstufe als Abflussbahn gilt
SCHWELLE_HA = {9: 2500, 10: 500, 11: 100, 12: 25, 13: 5, 14: 1}
KLASSE_FAKTOR = 5          # Klasse k: Einzugsgebiet ab 1 ha * 5^k
# Senken: Mindestvolumen (m³) und Mindesttiefe (m) je Zoomstufe
SENKE_MIN_M3 = {11: 20000, 12: 5000, 13: 1000, 14: 200}
SENKE_MIN_TIEFE = 0.3


def _mvt():
    spec = importlib.util.spec_from_file_location("mvt", HERE / "mvt.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("mvt", m)
    spec.loader.exec_module(m)
    return m


def tile_of(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def mosaik(dem_dir: Path, x0: int, x1: int, y0: int, y1: int, z: int = ZGRID) -> tuple[np.ndarray, int]:
    """Terrarium-Kacheln x0..x1, y0..y1 → Float32-Raster in Metern; NaN, wo die Kachel fehlt. Rückgabe (Raster, Zahl fehlender Kacheln)."""
    from PIL import Image
    W, H = (x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256
    dem = np.full((H, W), np.nan, dtype=np.float32)
    fehlt = 0
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            p = dem_dir / str(z) / str(x) / f"{y}.png"
            if not p.exists():
                fehlt += 1
                continue
            rgb = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
            dem[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768
    return dem, fehlt


def zeilenflaeche(y0: int, hoehe: int, z: int = ZGRID) -> np.ndarray:
    """Fläche einer Zelle (m²) je Zeile: Web-Mercator-Pixel schrumpft mit cos(Breite)."""
    y = y0 * 256 + np.arange(hoehe) + 0.5
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * y / (256 * 2 ** z)))))
    px = EARTH / (256 * 2 ** z) * np.cos(np.radians(lat))
    return (px * px).astype(np.float32)


def kern_bauen(ziel: Path) -> Path:
    exe = ziel / "abfluss_kern"
    src = HERE / "abfluss_kern.c"
    if not exe.exists() or exe.stat().st_mtime < src.stat().st_mtime:
        ziel.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cc", "-O3", "-Wall", "-o", str(exe), str(src), "-lm"], check=True)
    return exe


def rechnen(dem: np.ndarray, y0: int, work: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Kern aufrufen; Rückgabe (dir uint8, acc m², depth m), alle in der Rastergröße von dem."""
    work.mkdir(parents=True, exist_ok=True)
    H, W = dem.shape
    dem.tofile(work / "dem.f32")
    zeilenflaeche(y0, H).tofile(work / "zeile.f32")
    exe = kern_bauen(work)
    t0 = time.time()
    r = subprocess.run([str(exe), str(work / "dem.f32"), str(work / "zeile.f32"), str(W), str(H), str(work / "aus")], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"Rechenkern: {r.stderr.strip()}")
    log.info("Rechenkern: %s (%.0f s)", r.stderr.strip(), time.time() - t0)
    shape = (H, W)
    return (np.fromfile(work / "aus.dir", np.uint8).reshape(shape), np.fromfile(work / "aus.acc", np.float32).reshape(shape),
            np.fromfile(work / "aus.depth", np.float32).reshape(shape))


def landmaske(grenze: Path, x0: int, y0: int, W: int, H: int, z: int = ZGRID) -> np.ndarray:
    """True innerhalb der Landesgrenze (GeoJSON), im Pixelraster des Mosaiks."""
    from skimage.draw import polygon
    from shapely.geometry import shape
    gj = json.loads(grenze.read_text())
    geoms = [shape(f["geometry"]) for f in gj["features"]] if gj.get("type") == "FeatureCollection" else [shape(gj)]
    mask = np.zeros((H, W), dtype=bool)
    n = 256 * 2 ** z
    for g in geoms:
        for poly in (g.geoms if hasattr(g, "geoms") else [g]):
            lon, lat = np.array(poly.exterior.xy)
            gx = (lon + 180) / 360 * n - x0 * 256
            gy = (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n - y0 * 256
            rr, cc = polygon(gy, gx, shape=(H, W))
            mask[rr, cc] = True
    return mask


def ketten(acc: np.ndarray, d: np.ndarray, mask: np.ndarray, schwelle_m2: float):
    """Zellen mit acc >= Schwelle zu Ketten verbinden. Ein Kettenende ist ein Zusammenfluss (zwei und mehr Zuflüsse aus der Menge) oder das
    Ende der Menge. Liefert (idx, stuecke): idx sind die flachen Zellindizes der Menge, ein Stück ist (Positionen in idx, acc der Kette, Position der Eigner-Zelle)."""
    H, W = acc.shape
    sel = (acc >= schwelle_m2) & mask & (d != 255)
    idx = np.flatnonzero(sel)
    if idx.size == 0:
        return idx, []
    dd = d.ravel()[idx]
    ziel = idx + DY[dd] * W + DX[dd]
    pos = np.searchsorted(idx, ziel)
    pos[pos >= idx.size] = 0
    gueltig = idx[pos] == ziel
    nxt = np.where(gueltig, pos, -1)
    indeg = np.bincount(nxt[gueltig], minlength=idx.size)
    heads = np.flatnonzero(indeg != 1)
    nl, il = nxt.tolist(), indeg.tolist()
    tx = ((idx % W) >> 8).tolist()
    ty = ((idx // W) >> 8).tolist()
    stuecke = []
    for h in heads.tolist():
        kette = [h]
        p = h
        while True:
            q = nl[p]
            if q < 0:
                break
            kette.append(q)
            if il[q] != 1:
                break
            p = q
        wert = float(acc.ravel()[idx[kette[-1]]])
        # an Zoom-14-Kachelgrenzen teilen; das Verbindungssegment liegt in beiden Stücken, jedes Stück gehört der Kachel seiner Eigner-Zelle
        start = own = 0
        for i in range(1, len(kette)):
            if (tx[kette[i]], ty[kette[i]]) != (tx[kette[own]], ty[kette[own]]):
                stuecke.append((kette[start:i + 1], wert, kette[own]))
                start, own = i - 1, i
        stuecke.append((kette[start:], wert, kette[own]))
    return idx, stuecke


def klasse(m2: float) -> int:
    return max(0, int(math.log(max(m2 / 10000.0, 1.0)) / math.log(KLASSE_FAKTOR)))


def punkte_lonlat(gx: np.ndarray, gy: np.ndarray, z: int) -> tuple[np.ndarray, np.ndarray]:
    n = 256 * 2 ** z
    return gx / n * 360 - 180, np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * gy / n))))


def abfluss_kacheln(mvt, acc, d, mask, x0, y0, zooms) -> dict:
    from shapely.geometry import LineString
    H, W = acc.shape
    tiles: dict[tuple[int, int, int], object] = {}
    for z in zooms:
        t0 = time.time()
        idx, stuecke = ketten(acc, d, mask, SCHWELLE_HA[z] * 10000.0)
        s = 2 ** (ZGRID - z)
        tol = 2.0 ** (12 - z)           # 0,5 Bildschirmpixel in Zoom-14-Pixeln
        n = 0
        for pos, wert, eigner in stuecke:
            c = idx[np.array(pos)]
            gx = (c % W) + 0.5 + x0 * 256
            gy = (c // W) + 0.5 + y0 * 256
            pts = list(zip(gx.tolist(), gy.tolist()))
            if len(pts) > 2 and tol > 0.3:
                pts = list(LineString(pts).simplify(tol, preserve_topology=False).coords)
            if len(pts) < 2:
                continue
            ce = int(idx[eigner])
            tx, ty = int(((ce % W) + 0.5 + x0 * 256) // (256 * s)), int(((ce // W) + 0.5 + y0 * 256) // (256 * s))
            lok = [(int(round((px / (256 * s) - tx) * EXTENT)), int(round((py / (256 * s) - ty) * EXTENT))) for px, py in pts]
            lay = tiles.setdefault((z, tx, ty), mvt.Layer("abfluss"))
            lay.add(2, mvt.line_geometry([lok]), {"k": klasse(wert), "ha": int(round(wert / 10000.0))})
            n += 1
        log.info("Zoom %d: %d Zellen, %d Linienstücke (%.0f s)", z, idx.size, n, time.time() - t0)
    return tiles


def senken_kacheln(mvt, depth, mask, rowa, x0, y0, tiles, zooms) -> int:
    from scipy import ndimage
    H, W = depth.shape
    roh = depth >= SENKE_MIN_TIEFE
    roh &= mask
    lab, n = ndimage.label(roh, structure=np.ones((3, 3)))
    if n == 0:
        return 0
    idx = np.arange(1, n + 1)
    w = np.broadcast_to(rowa[:, None], depth.shape)
    vol = ndimage.sum(depth * w, lab, idx)
    flaeche = ndimage.sum(w, lab, idx)
    tief = ndimage.maximum(depth, lab, idx)
    pos = ndimage.maximum_position(depth, lab, idx)
    gesamt = 0
    for z in zooms:
        if z not in SENKE_MIN_M3:
            continue
        s = 2 ** (ZGRID - z)
        for k in np.flatnonzero(vol >= SENKE_MIN_M3[z]):
            py, px = pos[k]
            gx, gy = px + 0.5 + x0 * 256, py + 0.5 + y0 * 256
            tx, ty = int(gx // (256 * s)), int(gy // (256 * s))
            lx, ly = int(round((gx / (256 * s) - tx) * EXTENT)), int(round((gy / (256 * s) - ty) * EXTENT))
            lay = tiles.setdefault((z, tx, ty, "s"), mvt.Layer("senken"))
            lay.add(1, mvt.point_geometry(lx, ly), {"v": int(round(vol[k])), "d": int(round(tief[k] * 100)), "ha": int(round(flaeche[k] / 1000.0))})
            gesamt += 1
    log.info("Senken: %d Gebiete über %.1f m, %d Punkte in den Kacheln", n, SENKE_MIN_TIEFE, gesamt)
    return gesamt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dem-dir", type=Path, required=True)
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("W", "S", "E", "N"), required=True)
    ap.add_argument("--grenze", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--zoom-min", type=int, default=9)
    ap.add_argument("--zoom-max", type=int, default=14)
    ap.add_argument("--stand", default="")
    args = ap.parse_args(argv)
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    mvt = _mvt()
    x0, y1 = tile_of(args.bbox[0], args.bbox[1], ZGRID)
    x1, y0 = tile_of(args.bbox[2], args.bbox[3], ZGRID)
    log.info("Kacheln x %d..%d, y %d..%d (%d)", x0, x1, y0, y1, (x1 - x0 + 1) * (y1 - y0 + 1))
    dem, fehlt = mosaik(args.dem_dir, x0, x1, y0, y1)
    if fehlt:
        log.warning("%d Kacheln fehlen (keine Daten dort)", fehlt)
    log.info("Raster %d x %d = %.1f Mio. Zellen", dem.shape[1], dem.shape[0], dem.size / 1e6)
    d, acc, depth = rechnen(dem, y0, args.work)
    del dem
    mask = landmaske(args.grenze, x0, y0, d.shape[1], d.shape[0])
    zooms = list(range(args.zoom_min, args.zoom_max + 1))
    tiles = abfluss_kacheln(mvt, acc, d, mask, x0, y0, zooms)
    senken_kacheln(mvt, depth, mask, zeilenflaeche(y0, d.shape[0]), x0, y0, tiles, zooms)
    fertig: dict[tuple[int, int, int], bytes] = {}
    for key in {k[:3] for k in tiles}:
        lays = [tiles[k] for k in (key, key + ("s",)) if k in tiles]
        fertig[key] = mvt.tile_bytes(lays)
    attr = "Gelände: © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet]; Abfluss: Geländeschätzung, kein amtliches Gefahrenkartenwerk"
    res = mvt.write_pmtiles(fertig, args.out, {"name": "abfluss", "attribution": attr, "description": f"Abflussbahnen und Senken aus dem Gelände{', ' + args.stand if args.stand else ''}",
                                               "vector_layers": [{"id": "abfluss", "fields": {"k": "Number", "ha": "Number"}}, {"id": "senken", "fields": {"v": "Number", "d": "Number", "ha": "Number"}}]})
    log.info("fertig: %d Kacheln, %.1f MB", res["kacheln"], res["bytes"] / 1e6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
