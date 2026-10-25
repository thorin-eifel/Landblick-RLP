#!/usr/bin/env python3
"""Gebäudeebene für die Karte: amtliche Hausumringe in Rheinland-Pfalz, OpenStreetMap-Gebäude außerhalb, als eine PMTiles-Datei.

Zweck:      Die Gebäude der Basiskarte stammen aus OpenStreetMap und sind lückenhaft (um Irrel fehlt gut jedes siebte,
            meist Nebengebäude). Das Land gibt die Hausumringe des Liegenschaftskatasters frei. Diese Datei ersetzt die
            OSM-Gebäude in Rheinland-Pfalz; außerhalb (Luxemburg, Saarland, Frankreich, Hessen ...) bleiben die OSM-Gebäude
            aus core.pmtiles und ring.pmtiles, damit dort keine Löcher entstehen.
Quelle:     Hausumringe RP, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet],
            https://geobasis-rlp.de/data/hu/current/zip/HAUSUMRINGE_RP.zip (Shapefile, EPSG:25832, rund 330 MB, ganz Rheinland-Pfalz).
            OSM-Gebäude: Protomaps-Build, © OpenStreetMap-Mitwirkende (ODbL).
Datenschutz: Übernommen werden die Umrisse und die Gebäudefunktion (GFK, Spalte der .dbf), gröber zusammengefasst zu acht Klassen
            (wohnen, wirtschaft, garage, ueberdachung, technik, oeffentlich, religion, sonst). Gemeindeschlüssel (AGS), Objektkennung (OI)
            und Kachelnummer der Quelle werden nicht gelesen, Adressen und Eigentümer enthält die Quelle nicht. Fehlt die .dbf, entsteht
            die Datei ohne Klassen (alles in der Standardfarbe).
Ablauf:     1. Hausumringe lesen, nach Web-Mercator umrechnen, je Kachel Zoom 15 (alle) und Zoom 14 (nur größere) als MVT-Merkmal ablegen
            2. OSM-Gebäude aus core (Zoom 14/15) und ring (Zoom 14) übernehmen, deren Schwerpunkt außerhalb der Landesgrenze liegt
            3. Kacheln zu <out> (PMTiles, Ebene `buildings`, Attribute kind=building wie im Stil der Basiskarte und klasse=<Klasse> bei Hausumringen) schreiben
Aufruf:     python tools/build_gebaeude_rlp.py --hu hu/gebaeude_hu.shp --core perf-rlp/tiles/core.pmtiles \\
                --ring perf-rlp/tiles/ring.pmtiles --grenze web/geo/rlp.geojson --out perf-rlp/tiles/gebaeude.pmtiles
            python tools/build_gebaeude_rlp.py ... --bbox 6.35 49.80 6.55 49.92        Ausschnitt (Probe, in Sekunden)
Parameter:  --min-z14 40   Mindestfläche (m², Umgrenzungsrechteck) der Hausumringe in den Zoom-14-Kacheln
Exit:       0 = fertig, 1 = Fehler
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import math
import struct
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterator

import numpy as np

log = logging.getLogger("landblick.gebaeude")

EXTENT = 4096
ZMAX, ZMIN = 15, 14
MERC = 20037508.342789244
KEEP_KINDS = {"building", "building_part"}
KLASSEN = ("wohnen", "wirtschaft", "garage", "ueberdachung", "technik", "oeffentlich", "religion", "sonst")
CODE_KLASSE = {   # Gebäudefunktion (ADV-Codeliste BuildingFunctionTypeAdV) → Klasse; Rest nach klasse_von_gfk()
    "31001_1000": "wohnen", "31001_2000": "wirtschaft", "31001_2461": "garage", "31001_2462": "garage", "31001_2463": "garage",
    "31001_2464": "garage", "31001_2465": "garage", "51009_1610": "ueberdachung", "51001_1001": "technik",
}
ATTRIBUTION = ("Gebäude in Rheinland-Pfalz: © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet]; "
               "sonst © OpenStreetMap-Mitwirkende (ODbL)")


def klasse_von_gfk(gfk: str | None) -> str:
    """Gebäudefunktionskennung (z. B. "31001_3041") → eine von KLASSEN. Unbekannt oder leer: "sonst"."""
    g = (gfk or "").strip()
    if g in CODE_KLASSE:
        return CODE_KLASSE[g]
    try:
        kopf, num = g.split("_")
        n = int(num)
    except ValueError:
        return "sonst"
    if kopf != "31001":
        return "sonst"
    if 1000 <= n < 2000:
        return "wohnen"
    if n in (2213, 2513, 2523, 2527, 2611):      # Schöpfwerk, Wasserbehälter, Umformer, Reaktorgebäude, Kläranlage
        return "technik"
    if 2000 <= n < 3000:
        return "wirtschaft"
    if 3040 <= n < 3050 or 3080 <= n < 3090:     # religiöse Zwecke, Friedhofsgebäude, Trauerhalle, Krematorium
        return "religion"
    if 3000 <= n < 4000:
        return "oeffentlich"
    return "sonst"


# ------------------------------------------------------------------ MVT schreiben
def varint(v: int) -> bytes:
    out = bytearray()
    while v > 0x7F:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v)
    return bytes(out)


def _zig(v: int) -> int:
    return (v << 1) ^ (v >> 63)


def packed(values: list[int]) -> bytes:
    return b"".join(varint(v) for v in values)


def ring_area2(xs: list[int], ys: list[int]) -> int:
    """Doppelte vorzeichenbehaftete Fläche (Schnürsenkel), positiv = Außenring im Kachelraum (y nach unten)."""
    n = len(xs)
    return sum(xs[i] * ys[(i + 1) % n] - xs[(i + 1) % n] * ys[i] for i in range(n))


def geometry_ints(rings: list[tuple[list[int], list[int], bool]]) -> list[int]:
    """MVT-Befehle für Ringe [(xs, ys, aussen)], Zeiger läuft über alle Ringe eines Merkmals.
    Außenringe bekommen positive, Löcher negative Fläche; entartete Ringe (< 3 Punkte, Fläche 0) fallen weg."""
    out: list[int] = []
    cx = cy = 0
    for xs, ys, outer in rings:
        px, py = [xs[0]], [ys[0]]
        for x, y in zip(xs[1:], ys[1:]):          # aufeinanderfolgende Dubletten entfernen
            if x != px[-1] or y != py[-1]:
                px.append(x)
                py.append(y)
        if len(px) > 1 and px[0] == px[-1] and py[0] == py[-1]:
            px.pop()
            py.pop()
        if len(px) < 3:
            continue
        a = ring_area2(px, py)
        if a == 0:
            continue
        if (a > 0) != outer:
            px.reverse()
            py.reverse()
        out.append(1 | (1 << 3))
        out += [_zig(px[0] - cx), _zig(py[0] - cy)]
        cx, cy = px[0], py[0]
        out.append(2 | ((len(px) - 1) << 3))
        for x, y in zip(px[1:], py[1:]):
            out += [_zig(x - cx), _zig(y - cy)]
            cx, cy = x, y
        out.append(7 | (1 << 3))
    return out


def feature_bytes(geom: list[int], klasse: str | None = None) -> bytes:
    """Ein Polygon-Merkmal mit kind=building (Schlüssel 0, Wert 0 der Ebene) und, wenn gegeben, klasse=<Klasse> (Schlüssel 1, Wert 1 + Index)."""
    tags = packed([0, 0] if klasse is None else [0, 0, 1, 1 + KLASSEN.index(klasse)])
    g = packed(geom)
    return b"\x12" + varint(len(tags)) + tags + b"\x18\x03" + b"\x22" + varint(len(g)) + g


def layer_bytes(features: list[bytes]) -> bytes:
    body = b"\x0a\x09buildings"
    for f in features:
        body += b"\x12" + varint(len(f)) + f
    body += b"\x1a\x04kind" + b"\x1a\x06klasse"                # Schlüssel 0 = kind, 1 = klasse
    for v in ("building",) + KLASSEN:                            # Werte: 0 = "building", 1.. = Klassen
        vb = v.encode()
        body += b"\x22" + varint(len(vb) + 2) + b"\x0a" + varint(len(vb)) + vb
    body += b"\x28" + varint(EXTENT) + b"\x78\x02"              # extent, version 2
    return b"\x1a" + varint(len(body)) + body


def tile_bytes(features: list[bytes]) -> bytes:
    return gzip.compress(layer_bytes(features), compresslevel=6, mtime=0)


# ------------------------------------------------------------------ MVT lesen (nur Ebene buildings)
def _varint(b: bytes, p: int) -> tuple[int, int]:
    r = s = 0
    while True:
        c = b[p]
        p += 1
        r |= (c & 0x7F) << s
        s += 7
        if not c & 0x80:
            return r, p


def _fields(b: bytes) -> Iterator[tuple[int, int, int | bytes]]:
    p = 0
    while p < len(b):
        k, p = _varint(b, p)
        f, w = k >> 3, k & 7
        if w == 0:
            v, p = _varint(b, p)
            yield f, w, v
        elif w == 2:
            n, p = _varint(b, p)
            yield f, w, b[p:p + n]
            p += n
        elif w == 1:
            yield f, w, b[p:p + 8]
            p += 8
        elif w == 5:
            yield f, w, b[p:p + 4]
            p += 4
        else:
            return


def read_buildings(raw: bytes) -> tuple[int, list[list[int]]]:
    """Polygone der Ebene `buildings` mit kind in KEEP_KINDS: (extent, [Befehlsliste, ...])."""
    extent, out = read_buildings_klasse(raw)
    return extent, [g for g, _ in out]


def read_buildings_klasse(raw: bytes) -> tuple[int, list[tuple[list[int], str | None]]]:
    """Wie read_buildings, dazu das Attribut `klasse` je Polygon (None, wenn es keines trägt): (extent, [(Befehlsliste, klasse), ...])."""
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    extent, out = 4096, []
    for f, w, v in _fields(raw):
        if f != 3 or w != 2:
            continue
        name, keys, vals, feats = "", [], [], []
        for lf, lw, lv in _fields(v):
            if lf == 1 and lw == 2:
                name = lv.decode()
            elif lf == 2 and lw == 2:
                feats.append(lv)
            elif lf == 3 and lw == 2:
                keys.append(lv.decode())
            elif lf == 4 and lw == 2:
                s = next((x for ff, ww, x in _fields(lv) if ff == 1 and ww == 2), b"")
                vals.append(s.decode())
            elif lf == 5 and lw == 0:
                extent = lv
        if name != "buildings":
            continue
        kind_i = keys.index("kind") if "kind" in keys else -1
        kl_i = keys.index("klasse") if "klasse" in keys else -1
        for ft in feats:
            typ, tags, geom = 0, [], []
            for ff, fw, fv in _fields(ft):
                if ff == 3 and fw == 0:
                    typ = fv
                elif ff == 2 and fw == 2:
                    p = 0
                    while p < len(fv):
                        t, p = _varint(fv, p)
                        tags.append(t)
                elif ff == 4 and fw == 2:
                    p = 0
                    while p < len(fv):
                        t, p = _varint(fv, p)
                        geom.append(t)
            if typ != 3:
                continue
            kind = next((vals[tags[i + 1]] for i in range(0, len(tags) - 1, 2) if tags[i] == kind_i and tags[i + 1] < len(vals)), None)
            klasse = next((vals[tags[i + 1]] for i in range(0, len(tags) - 1, 2) if tags[i] == kl_i and tags[i + 1] < len(vals)), None)
            if kind in KEEP_KINDS:
                out.append((geom, klasse))
    return extent, out


def first_ring_points(geom: list[int]) -> list[tuple[int, int]]:
    """Stützpunkte des ersten Rings einer Befehlsliste (für den Schwerpunkt)."""
    pts, x, y, i = [], 0, 0, 0
    while i < len(geom):
        cmd, cnt = geom[i] & 7, geom[i] >> 3
        i += 1
        if cmd == 7:
            break
        for _ in range(cnt):
            dx, dy = geom[i], geom[i + 1]
            i += 2
            x += (dx >> 1) ^ -(dx & 1)
            y += (dy >> 1) ^ -(dy & 1)
            pts.append((x, y))
    return pts


# ------------------------------------------------------------------ Kachelgeometrie
def tile_lonlat(z: int, x: int, y: int, px: float, py: float, extent: int = EXTENT) -> tuple[float, float]:
    n = 2.0 ** z
    fx, fy = (x + px / extent) / n, (y + py / extent) / n
    return fx * 360.0 - 180.0, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * fy))))


def tile_box(z: int, x: int, y: int):
    from shapely.geometry import box
    w, n = tile_lonlat(z, x, y, 0, 0)
    e, s = tile_lonlat(z, x, y, EXTENT, EXTENT)
    return box(w, s, e, n)


def load_grenze(path: Path):
    from shapely.geometry import shape
    from shapely.ops import unary_union
    gj = json.loads(Path(path).read_text(encoding="utf-8"))
    feats = gj["features"] if gj.get("type") == "FeatureCollection" else [gj]
    return unary_union([shape(f["geometry"]) for f in feats])


# ------------------------------------------------------------------ Hausumringe lesen
def read_shp(path: Path, bbox_utm: tuple[float, float, float, float] | None = None, batch: int = 40000):
    """Liest Polygone aus dem Shapefile. Liefert je Merkmal (teile, punkte, nr) als numpy-Felder, in Stapeln; `nr` ist die laufende
    Nummer des Datensatzes in der Datei (null-basiert, zählt auch übersprungene), damit die .dbf-Zeile danebenliegt."""
    skipped = 0
    nr = -1
    with open(path, "rb") as f:
        head = f.read(100)
        if struct.unpack(">i", head[:4])[0] != 9994:
            raise ValueError("keine Shapefile-Datei")
        buf: list[tuple[np.ndarray, np.ndarray, int]] = []
        while True:
            h = f.read(8)
            if len(h) < 8:
                break
            nr += 1
            ln = struct.unpack(">i", h[4:])[0] * 2
            rec = f.read(ln)
            if struct.unpack("<i", rec[:4])[0] != 5:
                skipped += 1
                continue
            bx0, by0, bx1, by1 = struct.unpack("<4d", rec[4:36])
            if bbox_utm and (bx1 < bbox_utm[0] or bx0 > bbox_utm[2] or by1 < bbox_utm[1] or by0 > bbox_utm[3]):
                continue
            nparts, npts = struct.unpack("<2i", rec[36:44])
            parts = np.frombuffer(rec, dtype="<i4", count=nparts, offset=44)
            pts = np.frombuffer(rec, dtype="<f8", count=npts * 2, offset=44 + 4 * nparts).reshape(npts, 2)
            buf.append((parts, pts, nr))
            if len(buf) >= batch:
                yield buf
                buf = []
        if buf:
            yield buf
    if skipped:
        log.warning("%d Merkmale ohne Polygon übersprungen", skipped)


def read_gfk(shp: Path) -> np.ndarray | None:
    """Spalte GFK der zugehörigen .dbf als Feld von Klassen-Nummern (Index in KLASSEN), eine je Datensatz in Reihenfolge der .shp.
    Alle anderen Spalten (AGS, OI, KACHEL ...) werden nicht angefasst. Ohne .dbf oder ohne Spalte GFK: None."""
    dbf = shp.with_suffix(".dbf")
    if not dbf.exists():
        log.warning("%s fehlt: Hausumringe ohne Gebäudefunktion", dbf.name)
        return None
    with open(dbf, "rb") as f:
        head = f.read(32)
        n, hlen, rlen = struct.unpack("<Ihh", head[4:12])
        off = 1                                                  # erstes Byte jedes Datensatzes: Löschmarke
        spalte = None
        while True:
            d = f.read(32)
            if len(d) < 32 or d[0] == 0x0D:
                break
            name, ln = d[:11].split(b"\0")[0].decode("ascii", "replace"), d[16]
            if name.upper() == "GFK":
                spalte = (off, ln)
            off += ln
    if spalte is None:
        log.warning("Spalte GFK fehlt in %s", dbf.name)
        return None
    a = np.memmap(dbf, dtype=np.uint8, mode="r", offset=hlen, shape=(n, rlen))
    roh = np.ascontiguousarray(a[:, spalte[0]:spalte[0] + spalte[1]]).view(f"S{spalte[1]}").ravel()
    codes, inv = np.unique(roh, return_inverse=True)
    num = np.array([KLASSEN.index(klasse_von_gfk(c.decode("ascii", "replace"))) for c in codes], dtype=np.uint8)
    log.info("GFK: %d Datensätze, %d Codes", n, len(codes))
    return num[inv.ravel()]


def to_tile_space(x: np.ndarray, y: np.ndarray, tr, z: int) -> tuple[np.ndarray, np.ndarray]:
    mx, my = tr.transform(x, y)
    n = 2.0 ** z
    return (mx + MERC) / (2 * MERC) * n, (MERC - my) / (2 * MERC) * n


def encode_rings(fx: np.ndarray, fy: np.ndarray, parts: np.ndarray, tx: int, ty: int, scale: float = 1.0) -> list[int]:
    """Ringe eines Merkmals in Kachelpixel (tx, ty) umrechnen und als MVT-Befehle kodieren.
    fx, fy: Kachelkoordinaten im Zoom des Merkmals; scale = 1 für dieselbe Stufe, 0,5 für eine Stufe gröber."""
    bounds = list(parts) + [len(fx)]
    rings = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        u, v = fx[a:b], fy[a:b]
        # Shapefile: Außenringe im Uhrzeigersinn (y nach oben) = positive Fläche im Kachelraum (y nach unten), Löcher umgekehrt
        outer = float(np.dot(u, np.roll(v, -1)) - np.dot(np.roll(u, -1), v)) > 0
        xs = np.rint((u * scale - tx) * EXTENT).astype(np.int64).tolist()
        ys = np.rint((v * scale - ty) * EXTENT).astype(np.int64).tolist()
        rings.append((xs, ys, outer))
    return geometry_ints(rings)


def add_hausumringe(shp: Path, tiles: dict, min_z14: float, bbox: tuple[float, float, float, float] | None) -> int:
    from pyproj import Transformer
    gfk = read_gfk(shp)
    tr = Transformer.from_crs(25832, 3857, always_xy=True)
    bbox_utm = None
    if bbox:
        t2 = Transformer.from_crs(4326, 25832, always_xy=True)
        x0, y0 = t2.transform(bbox[0], bbox[1])
        x1, y1 = t2.transform(bbox[2], bbox[3])
        bbox_utm = (x0, y0, x1, y1)
    n = 0
    t0 = time.time()
    for stapel in read_shp(shp, bbox_utm):
        sizes = [len(p) for _, p, _ in stapel]
        allp = np.concatenate([p for _, p, _ in stapel])
        fx, fy = to_tile_space(allp[:, 0], allp[:, 1], tr, ZMAX)
        off = 0
        for (parts, pts, nr), sz in zip(stapel, sizes):
            klasse = None if gfk is None or nr >= len(gfk) else KLASSEN[gfk[nr]]
            ux, uy = fx[off:off + sz], fy[off:off + sz]
            raw_x, raw_y = pts[:, 0], pts[:, 1]
            off += sz
            flaeche = (raw_x.max() - raw_x.min()) * (raw_y.max() - raw_y.min())
            tx0, tx1 = int(math.floor(ux.min())), int(math.floor(ux.max()))
            ty0, ty1 = int(math.floor(uy.min())), int(math.floor(uy.max()))
            for tx in range(tx0, tx1 + 1):
                for ty in range(ty0, ty1 + 1):
                    g = encode_rings(ux, uy, parts, tx, ty)
                    if g:
                        tiles[(ZMAX, tx, ty)].append(feature_bytes(g, klasse))
            if flaeche >= min_z14:
                for tx in range(tx0 >> 1, (tx1 >> 1) + 1):
                    for ty in range(ty0 >> 1, (ty1 >> 1) + 1):
                        g = encode_rings(ux, uy, parts, tx, ty, scale=0.5)
                        if g:
                            tiles[(ZMIN, tx, ty)].append(feature_bytes(g, klasse))
            n += 1
        log.info("%d Hausumringe, %.0f s", n, time.time() - t0)
    return n


# ------------------------------------------------------------------ OSM-Gebäude außerhalb
def add_osm(archiv: Path, zooms: set[int], grenze, tiles: dict, bbox=None) -> tuple[int, int]:
    """OSM-Gebäude aus einem PMTiles-Archiv übernehmen, deren Schwerpunkt NICHT in `grenze` liegt. Rückgabe (behalten, verworfen)."""
    from pmtiles.reader import MmapSource, all_tiles
    from shapely.geometry import Point, box
    from shapely.prepared import prep
    pg = prep(grenze)
    keep = drop = 0
    with open(archiv, "rb") as fh:
        for (z, x, y), data in all_tiles(MmapSource(fh)):
            if z not in zooms:
                continue
            kasten = tile_box(z, x, y)
            if bbox and not kasten.intersects(box(*bbox)):
                continue
            if pg.contains(kasten):
                drop += 1
                continue
            extent, geoms = read_buildings(data)
            if not geoms:
                continue
            ganz_aussen = not pg.intersects(kasten)
            for g in geoms:
                if not ganz_aussen:
                    pts = first_ring_points(g)
                    if not pts:
                        continue
                    mx = sum(p[0] for p in pts) / len(pts)
                    my = sum(p[1] for p in pts) / len(pts)
                    if pg.contains(Point(tile_lonlat(z, x, y, mx, my, extent))):
                        drop += 1
                        continue
                if extent != EXTENT:
                    continue            # Fremdmaß nicht umrechnen; die Protomaps-Builds nutzen 4096
                tiles[(z, x, y)].append(feature_bytes(g))
                keep += 1
    return keep, drop


# ------------------------------------------------------------------ Schreiben
def write_pmtiles(tiles: dict, out: Path, stand: str) -> dict:
    from pmtiles.tile import Compression, TileType, zxy_to_tileid
    from pmtiles.writer import Writer
    items = sorted(((zxy_to_tileid(z, x, y), (z, x, y)) for (z, x, y), f in tiles.items() if f), key=lambda t: t[0])
    if not items:
        raise SystemExit("keine Kacheln")
    lon0 = lat0 = 1e9
    lon1 = lat1 = -1e9
    for _, (z, x, y) in items:
        w, n = tile_lonlat(z, x, y, 0, 0)
        e, s = tile_lonlat(z, x, y, EXTENT, EXTENT)
        lon0, lat0, lon1, lat1 = min(lon0, w), min(lat0, s), max(lon1, e), max(lat1, n)
    header = {
        "version": 3, "tile_compression": Compression.GZIP, "tile_type": TileType.MVT, "min_zoom": ZMIN, "max_zoom": ZMAX,
        "min_lon_e7": int(lon0 * 1e7), "min_lat_e7": int(lat0 * 1e7), "max_lon_e7": int(lon1 * 1e7), "max_lat_e7": int(lat1 * 1e7),
        "center_zoom": ZMIN, "center_lon_e7": int((lon0 + lon1) / 2 * 1e7), "center_lat_e7": int((lat0 + lat1) / 2 * 1e7),
    }
    meta = {"name": "gebaeude", "format": "pbf", "type": "overlay", "minzoom": ZMIN, "maxzoom": ZMAX, "attribution": ATTRIBUTION,
            "description": f"Gebäudeumrisse, Stand Hausumringe {stand}", "vector_layers": [{"id": "buildings", "fields": {"kind": "String", "klasse": "String"}}]}
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        w = Writer(fh)
        for tid, key in items:
            w.write_tile(tid, tile_bytes(tiles[key]))
        w.finalize(header, meta)
    tmp.replace(out)
    return {"kacheln": len(items), "bytes": out.stat().st_size}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hu", type=Path, required=True, help="gebaeude_hu.shp aus HAUSUMRINGE_RP.zip")
    ap.add_argument("--core", type=Path, help="core.pmtiles (OSM-Gebäude Zoom 14/15 außerhalb der Landesgrenze)")
    ap.add_argument("--ring", type=Path, help="ring.pmtiles (OSM-Gebäude Zoom 14 außerhalb der Landesgrenze)")
    ap.add_argument("--grenze", type=Path, required=True, help="Landesgrenze als GeoJSON (web/geo/rlp.geojson)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("W", "S", "E", "N"), help="nur dieser Ausschnitt (Probe)")
    ap.add_argument("--min-z14", type=float, default=40.0, help="Mindestfläche in m² für Zoom 14")
    ap.add_argument("--stand", default="Juli 2026", help="Stand der Hausumringe für die Metadaten")
    args = ap.parse_args(argv)
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    grenze = load_grenze(args.grenze)
    tiles: dict[tuple[int, int, int], list[bytes]] = defaultdict(list)
    n = add_hausumringe(args.hu, tiles, args.min_z14, tuple(args.bbox) if args.bbox else None)
    log.info("Hausumringe: %d", n)
    if args.core:
        k, d = add_osm(args.core, {14, 15}, grenze, tiles, args.bbox)
        log.info("OSM aus core: %d Gebäude außerhalb übernommen, %d innerhalb verworfen (Kacheln ganz im Land zählen als eins)", k, d)
    if args.ring:
        k, d = add_osm(args.ring, {14}, grenze, tiles, args.bbox)
        log.info("OSM aus ring: %d Gebäude außerhalb übernommen, %d innerhalb verworfen (Kacheln ganz im Land zählen als eins)", k, d)
    res = write_pmtiles(tiles, args.out, args.stand)
    log.info("fertig: %d Kacheln, %.1f MB", res["kacheln"], res["bytes"] / 1e6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
