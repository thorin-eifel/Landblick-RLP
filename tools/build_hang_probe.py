#!/usr/bin/env python3
"""Hangneigungsklassen aus dem Landes-DGM1 (1 m) als Vektorflächen ableiten: Probe für einen Ausschnitt, mit Größenmessung.

Zweck:      Frage: Was kostet es, aus dem 1-m-Gelände statt Schummerungskacheln Vektorflächen zu machen? Hangneigung ist
            lichtunabhängig und bleibt bei jedem Zoom scharf. Dieses Werkzeug baut für einen Ausschnitt Flächen je Neigungsklasse
            (Standard ab 15, 25, 35 Grad, jeweils "ab", also ineinander liegend), schreibt Vektorkacheln und misst Stützpunkte,
            Dateigröße und Hochrechnung für ganz Rheinland-Pfalz. Es ist eine Messprobe, keine Produktionsstufe.
Quelle:     Rohkacheln aus tools/build_klippen_dgm.py (work/raw, uint16-npz). Landes-DGM1 RLP, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0
            (Daten bearbeitet).
Aufruf:     python tools/build_hang_probe.py --raw _scratch/dgm1/raw --center 6.45 49.85 --size-km 3 --out _scratch/probe/hang
            python tools/build_hang_probe.py ... --classes 12 20 30 --sigma 1.5 --simplify 1.5 --min-area 40 --zoom 14
Parameter:  --raw DIR       Rohkachel-Cache (<ostkm>_<nordkm>.npz)
            --center LON LAT, --size-km N   Ausschnitt (Quadrat, auf ganze Kilometerkacheln aufgerundet, +1 km Rand zum Glätten)
            --classes ...   Schwellen in Grad (aufsteigend)
            --sigma         Glättung des Geländes in m (Standard 1,0), unterdrückt Rauschen von Bäumen/Gebäuderändern nicht, nur Messrauschen
            --simplify      Vereinfachung der Umrisse in m (Standard 1,5)
            --min-area      kleinste Fläche in m² (Standard 40)
            --zoom          Kachelzoom der Ausgabe (Standard 14)
            --out DIR       Kachelordner <out>/<z>/<x>/<y>.pbf, dazu stats.json
Ergebnis:   Kennzahlen je Klasse auf stdout und in <out>/stats.json (Flächen, Stützpunkte, Bytes roh und gzip, Bytes je km², Hochrechnung RLP).
Nebenwirkung: schreibt nur nach --out; Rohkacheln werden nur gelesen.
Exit:       0 fertig, 1 Fehler (keine Rohkacheln im Ausschnitt)
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # Aufruf als Skript: Projektwurzel auffindbar machen
from tools import build_klippen_dgm as kd  # noqa: E402

log = logging.getLogger("landblick.hang_probe")
RLP_KM2 = 19858.0
EXTENT = 4096


def slope_deg(h: np.ndarray, sigma: float) -> np.ndarray:
    """Hangneigung in Grad aus einem 1-m-Raster (Lücken vorher gefüllt), nach Gauß-Glättung."""
    from scipy import ndimage as ndi
    f, bad = kd._filled(h)
    if sigma > 0:
        f = ndi.gaussian_filter(f, sigma)
    gy, gx = np.gradient(f, kd.RES)
    s = np.degrees(np.arctan(np.hypot(gx, gy)))
    s[bad] = 0.0
    return s


def class_mask(s: np.ndarray, thr: float, min_area: float) -> np.ndarray:
    """Maske s >= thr, Einzelpixel entfernt, kleine Flächen verworfen."""
    from scipy import ndimage as ndi
    m = s >= thr
    m = ndi.binary_opening(m, structure=np.ones((2, 2), bool))
    lab, n = ndi.label(m)
    if n:
        sizes = ndi.sum(m, lab, index=np.arange(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes * kd.RES * kd.RES >= min_area
        m = keep[lab]
    return m


def utm_to_merc_tiles(x: np.ndarray, y: np.ndarray, z: int) -> tuple[np.ndarray, np.ndarray]:
    from pyproj import Transformer
    lon, lat = Transformer.from_crs(kd.CRS_UTM, "EPSG:4326", always_xy=True).transform(x, y)
    return kd.merc(np.asarray(lon), np.asarray(lat), z)


def build(raw: Path, center: tuple[float, float], size_km: float, classes: list[float], sigma: float,
          simplify: float, min_area: float, zoom: int, out: Path) -> dict:
    from pyproj import Transformer
    from shapely.affinity import affine_transform
    from shapely.geometry import Polygon, box
    import mapbox_vector_tile as mvt

    cx, cy = Transformer.from_crs("EPSG:4326", kd.CRS_UTM, always_xy=True).transform(*center)
    half = size_km * 500.0
    e0, e1 = int(math.floor((cx - half) / 1000)), int(math.floor((cx + half) / 1000))
    n0, n1 = int(math.floor((cy - half) / 1000)), int(math.floor((cy + half) / 1000))
    present = sum(1 for a in range(e0 - 1, e1 + 2) for b in range(n0 - 1, n1 + 2) if kd.raw_path(raw, a, b))
    if not present:
        log.error("Keine Rohkacheln im Ausschnitt (%d..%d, %d..%d) unter %s", e0, e1, n0, n1, raw)
        raise SystemExit(1)
    h = kd.load_block(raw, e0 - 1, n0 - 1, e1 + 1, n1 + 1)
    rows = h.shape[0]
    s = slope_deg(h, sigma)
    inner = (slice(1000, rows - 1000), slice(1000, h.shape[1] - 1000))       # Rand nur zum Glätten
    ox, oy = (e0 - 1) * 1000.0, (n0 - 1) * 1000.0
    area_km2 = (e1 - e0 + 1) * (n1 - n0 + 1)
    buckets: dict[tuple[int, int], dict[str, list]] = defaultdict(lambda: defaultdict(list))
    stats: dict = {"km2": area_km2, "zoom": zoom, "sigma": sigma, "simplify_m": simplify, "min_area_m2": min_area, "klassen": {}}
    for thr in classes:
        m = class_mask(s, thr, min_area)
        m[: inner[0].start] = False
        m[inner[0].stop:] = False
        m[:, : inner[1].start] = False
        m[:, inner[1].stop:] = False
        rings = kd._rings(m, 0, 0, rows, simplify)
        name = f"ab{int(thr) if float(thr).is_integer() else thr}"
        verts = 0
        for ext, holes in rings:
            def pr(coords):
                c = np.asarray(coords, float)
                tx, ty = utm_to_merc_tiles(c[:, 0] + ox, c[:, 1] + oy, zoom)
                return np.stack([tx, ty], 1)
            g = Polygon(pr(ext.exterior.coords), [pr(hc) for hc in holes])
            if not g.is_valid:
                g = g.buffer(0)
            verts += len(ext.exterior.coords) + sum(len(hc) for hc in holes)
            x0, y0, x1, y1 = g.bounds
            for tx in range(int(math.floor(x0)), int(math.floor(x1)) + 1):
                for ty in range(int(math.floor(y0)), int(math.floor(y1)) + 1):
                    buckets[(tx, ty)][name].append(g)
        stats["klassen"][name] = {"schwelle_grad": thr, "anteil_prozent": round(100.0 * float(m[inner].mean()), 2),
                                  "flaechen": len(rings), "stuetzpunkte": verts}
    pad = 64 / EXTENT
    total_raw = total_gz = ntiles = 0
    per_class_bytes: dict[str, int] = defaultdict(int)
    for (tx, ty), layers in buckets.items():
        win = box(tx - pad, ty - pad, tx + 1 + pad, ty + 1 + pad)
        mat = [EXTENT, 0, 0, EXTENT, -tx * EXTENT, -ty * EXTENT]
        out_layers = []
        for name, geoms in layers.items():
            feats = []
            for g in geoms:
                c = g.intersection(win)
                for p in (list(c.geoms) if hasattr(c, "geoms") else [c]):
                    if p.is_empty or p.geom_type != "Polygon":
                        continue
                    feats.append({"geometry": affine_transform(p, mat), "properties": {}})
            if feats:
                out_layers.append({"name": name, "features": feats})
        if not out_layers:
            continue
        data = mvt.encode(out_layers, default_options={"extents": EXTENT, "y_coord_down": True})
        d = out / str(zoom) / str(tx)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{ty}.pbf").write_bytes(data)
        ntiles += 1
        total_raw += len(data)
        total_gz += len(gzip.compress(data, 6))
        for layer in out_layers:                     # Anteil je Klasse grob über Einzelkodierung
            per_class_bytes[layer["name"]] += len(gzip.compress(mvt.encode([layer], default_options={"extents": EXTENT, "y_coord_down": True}), 6))
    for name, b in per_class_bytes.items():
        stats["klassen"][name]["bytes_gzip"] = b
    stats.update(kacheln=ntiles, bytes_roh=total_raw, bytes_gzip=total_gz,
                 kb_je_km2_gzip=round(total_gz / 1024 / area_km2, 1),
                 hochrechnung_rlp_mb_gzip=round(total_gz / area_km2 * RLP_KM2 / 1e6, 1))
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--center", type=float, nargs=2, metavar=("LON", "LAT"), required=True)
    ap.add_argument("--size-km", type=float, default=3.0)
    ap.add_argument("--classes", type=float, nargs="+", default=[15.0, 25.0, 35.0])
    ap.add_argument("--sigma", type=float, default=1.0)
    ap.add_argument("--simplify", type=float, default=1.5)
    ap.add_argument("--min-area", type=float, default=40.0)
    ap.add_argument("--zoom", type=int, default=14)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not (0 < a.size_km <= 20) or a.classes != sorted(a.classes) or not (0 < a.zoom <= 17):
        log.error("Ungültige Parameter")
        return 1
    st = build(a.raw, tuple(a.center), a.size_km, a.classes, a.sigma, a.simplify, a.min_area, a.zoom, a.out)
    print(json.dumps(st, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
