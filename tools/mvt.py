"""Kleiner MVT- und PMTiles-Schreiber (Linien, Punkte, getypte Attribute) für die Werkzeuge in tools/.

Zweck:   Mapbox Vector Tiles (Version 2) von Hand kodieren und als PMTiles-Archiv schreiben, ohne tippecanoe oder GDAL.
         tools/build_gebaeude_rlp.py hat einen eigenen Schreiber für Polygone; dieser hier ist für Linien und Punkte.
Test:    tests/test_mvt.py
"""
from __future__ import annotations

import gzip
import struct
from pathlib import Path

EXTENT = 4096


def varint(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def zig(v: int) -> int:
    return (v << 1) ^ (v >> 63)


def packed(values: list[int]) -> bytes:
    return b"".join(varint(v) for v in values)


def line_geometry(lines: list[list[tuple[int, int]]]) -> list[int]:
    """Linien (Listen von (x, y) in Kacheleinheiten) → MVT-Befehle MoveTo/LineTo mit Deltas. Linien mit weniger als zwei Punkten entfallen."""
    out: list[int] = []
    cx = cy = 0
    for pts in lines:
        if len(pts) < 2:
            continue
        out += [(1 << 3) | 1, zig(pts[0][0] - cx), zig(pts[0][1] - cy)]
        cx, cy = pts[0]
        out.append(((len(pts) - 1) << 3) | 2)
        for x, y in pts[1:]:
            out += [zig(x - cx), zig(y - cy)]
            cx, cy = x, y
    return out


def point_geometry(x: int, y: int) -> list[int]:
    return [(1 << 3) | 1, zig(x), zig(y)]


def _value(v) -> bytes:
    if isinstance(v, bool):
        return b"\x38" + (b"\x01" if v else b"\x00")
    if isinstance(v, int):
        return b"\x28" + varint(v) if v >= 0 else b"\x30" + varint(zig(v))
    if isinstance(v, float):
        return b"\x19" + struct.pack("<d", v)
    s = str(v).encode()
    return b"\x0a" + varint(len(s)) + s


class Layer:
    """Eine Ebene eines Kachelinhalts; Schlüssel und Werte werden gemeinsam geführt (wie in der MVT-Spezifikation)."""

    def __init__(self, name: str, extent: int = EXTENT):
        self.name, self.extent = name, extent
        self.keys: dict[str, int] = {}
        self.values: dict[tuple, int] = {}
        self.features: list[bytes] = []

    def add(self, geom_type: int, geom: list[int], props: dict | None = None) -> None:
        """geom_type: 1 Punkt, 2 Linie, 3 Fläche."""
        if not geom:
            return
        tags: list[int] = []
        for k, v in (props or {}).items():
            ki = self.keys.setdefault(k, len(self.keys))
            vi = self.values.setdefault((type(v).__name__, v), len(self.values))
            tags += [ki, vi]
        body = b""
        if tags:
            t = packed(tags)
            body += b"\x12" + varint(len(t)) + t
        g = packed(geom)
        body += b"\x18" + varint(geom_type) + b"\x22" + varint(len(g)) + g
        self.features.append(body)

    def to_bytes(self) -> bytes:
        n = self.name.encode()
        body = b"\x0a" + varint(len(n)) + n
        for f in self.features:
            body += b"\x12" + varint(len(f)) + f
        for k in self.keys:
            kb = k.encode()
            body += b"\x1a" + varint(len(kb)) + kb
        for (_, v) in self.values:
            vb = _value(v)
            body += b"\x22" + varint(len(vb)) + vb
        body += b"\x28" + varint(self.extent) + b"\x78\x02"
        return b"\x1a" + varint(len(body)) + body


def tile_bytes(layers: list[Layer]) -> bytes:
    return gzip.compress(b"".join(l.to_bytes() for l in layers if l.features), compresslevel=6, mtime=0)


def _fields(b: bytes):
    p = 0
    while p < len(b):
        key, p = _vi(b, p)
        f, w = key >> 3, key & 7
        if w == 0:
            v, p = _vi(b, p)
        elif w == 2:
            ln, p = _vi(b, p)
            v, p = b[p:p + ln], p + ln
        elif w == 1:
            v, p = b[p:p + 8], p + 8
        elif w == 5:
            v, p = b[p:p + 4], p + 4
        else:
            return
        yield f, w, v


def _vi(b: bytes, p: int) -> tuple[int, int]:
    r = s = 0
    while True:
        c = b[p]
        p += 1
        r |= (c & 0x7F) << s
        if not c & 0x80:
            return r, p
        s += 7


def read_layers(raw: bytes) -> dict[str, list[dict]]:
    """Gegenstück zum Schreiben, für Tests und Prüfungen: {Ebene: [{type, geom, props}]}."""
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    out: dict[str, list[dict]] = {}
    for f, w, v in _fields(raw):
        if f != 3:
            continue
        name, keys, vals, feats = "", [], [], []
        for lf, lw, lv in _fields(v):
            if lf == 1:
                name = lv.decode()
            elif lf == 2:
                feats.append(lv)
            elif lf == 3:
                keys.append(lv.decode())
            elif lf == 4:
                for vf, vw, vv in _fields(lv):
                    if vf == 1:
                        vals.append(vv.decode())
                    elif vf == 3:
                        vals.append(struct.unpack("<d", vv)[0])
                    elif vf == 5:
                        vals.append(vv)
                    elif vf == 6:
                        vals.append((vv >> 1) ^ -(vv & 1))
                    elif vf == 7:
                        vals.append(bool(vv))
        for ft in feats:
            typ, tags, geom = 0, [], []
            for ff, fw, fv in _fields(ft):
                if ff == 3:
                    typ = fv
                elif ff in (2, 4) and fw == 2:
                    p, tgt = 0, tags if ff == 2 else geom
                    while p < len(fv):
                        t, p = _vi(fv, p)
                        tgt.append(t)
            props = {keys[tags[i]]: vals[tags[i + 1]] for i in range(0, len(tags) - 1, 2)}
            out.setdefault(name, []).append({"type": typ, "geom": geom, "props": props})
    return out


def decode_line(geom: list[int]) -> list[list[tuple[int, int]]]:
    """MVT-Befehle einer Linie → Liste von Linien (x, y)."""
    lines, cur, x, y, i = [], [], 0, 0, 0
    while i < len(geom):
        cmd, cnt = geom[i] & 7, geom[i] >> 3
        i += 1
        for _ in range(cnt):
            x += (geom[i] >> 1) ^ -(geom[i] & 1)
            y += (geom[i + 1] >> 1) ^ -(geom[i + 1] & 1)
            i += 2
            if cmd == 1 and cur:
                lines.append(cur)
                cur = []
            cur.append((x, y))
    if cur:
        lines.append(cur)
    return lines


def zxy_bounds(tiles: dict, extent: int = EXTENT) -> tuple[float, float, float, float]:
    """Geografischer Umriss (lon0, lat0, lon1, lat1) der Kacheln für den PMTiles-Kopf."""
    import math

    def lonlat(z, x, y):
        n = 2.0 ** z
        return x / n * 360 - 180, math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))

    lon0 = lat0 = 1e9
    lon1 = lat1 = -1e9
    for (z, x, y) in tiles:
        w, n = lonlat(z, x, y)
        e, s = lonlat(z, x + 1, y + 1)
        lon0, lat0, lon1, lat1 = min(lon0, w), min(lat0, s), max(lon1, e), max(lat1, n)
    return lon0, lat0, lon1, lat1


def write_pmtiles(tiles: dict[tuple[int, int, int], bytes], out: Path, meta: dict) -> dict:
    """tiles: (z, x, y) → bereits gzip-komprimierte MVT-Bytes. meta: Felder für das JSON-Metadatenfeld (name, attribution, vector_layers ...)."""
    from pmtiles.tile import Compression, TileType, zxy_to_tileid
    from pmtiles.writer import Writer
    items = sorted(((zxy_to_tileid(z, x, y), (z, x, y)) for (z, x, y) in tiles), key=lambda t: t[0])
    if not items:
        raise SystemExit("keine Kacheln")
    lon0, lat0, lon1, lat1 = zxy_bounds(tiles)
    zs = [k[0] for _, k in items]
    header = {
        "version": 3, "tile_compression": Compression.GZIP, "tile_type": TileType.MVT, "min_zoom": min(zs), "max_zoom": max(zs),
        "min_lon_e7": int(lon0 * 1e7), "min_lat_e7": int(lat0 * 1e7), "max_lon_e7": int(lon1 * 1e7), "max_lat_e7": int(lat1 * 1e7),
        "center_zoom": min(zs), "center_lon_e7": int((lon0 + lon1) / 2 * 1e7), "center_lat_e7": int((lat0 + lat1) / 2 * 1e7),
    }
    meta = {"format": "pbf", "type": "overlay", "minzoom": min(zs), "maxzoom": max(zs), **meta}
    tmp = out.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        w = Writer(fh)
        for tid, key in items:
            w.write_tile(tid, tiles[key])
        w.finalize(header, meta)
    tmp.replace(out)
    return {"kacheln": len(items), "bytes": out.stat().st_size}
