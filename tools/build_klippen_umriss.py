#!/usr/bin/env python3
"""Abdeckung der Klippenkacheln als JS-Modul (web/js/lage/klippen-umriss.js).

Zweck:    Wo die Wände aus dem Geländemodell (tools/build_klippen_dgm.py) vorliegen, zeichnet die Karte nur sie. OpenStreetMap-Klippen
          dürfen dort nicht zusätzlich erscheinen (sonst liegen zwei Zeichnungen übereinander). Der Stilausdruck ["within", Umriss] braucht
          die Geometrie synchron beim Stilaufbau, deshalb ein kleines Modul. Der Umriss ist die Vereinigung aller Kacheln, die Wände
          enthalten (Zoom 13), also die tatsächliche Abdeckung und nicht die Landesgrenze.
Aufruf:   python tools/build_klippen_umriss.py --tiles web/tiles/klippen              (liest <tiles>/13/<x>/<y>.pbf)
          python tools/build_klippen_umriss.py --list kacheln.txt                       (Zeilen "x y", auch mit ";" getrennt)
Nach jedem neuen Lauf von build_klippen_dgm.py erneut ausführen.
Exit:     0 = geschrieben, 1 = keine Kacheln
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

from shapely.geometry import box, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
Z = 13


def lon(x: float) -> float:
    return x / 2**Z * 360.0 - 180.0


def lat(y: float) -> float:
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / 2**Z))))


def read_tiles(tiles: Path | None, listing: Path | None) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    if listing:
        for x, y in re.findall(r"(\d+)\s+(\d+)", listing.read_text(encoding="utf-8")):
            out.add((int(x), int(y)))
    if tiles:
        for f in (tiles / str(Z)).glob("*/*.pbf"):
            out.add((int(f.parent.name), int(f.stem)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tiles", type=Path)
    ap.add_argument("--list", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "web/js/lage/klippen-umriss.js")
    args = ap.parse_args()
    tiles = read_tiles(args.tiles, args.list)
    if not tiles:
        print("keine Kacheln gefunden", file=sys.stderr)
        return 1
    shape_ = unary_union([box(lon(x), lat(y + 1), lon(x + 1), lat(y)) for x, y in tiles])
    geo = mapping(shape_)
    if geo["type"] == "Polygon":
        geo = {"type": "MultiPolygon", "coordinates": [geo["coordinates"]]}
    geo = json.loads(json.dumps(geo), parse_float=lambda s: round(float(s), 4))
    args.out.write_text(
        "// Erzeugt von tools/build_klippen_umriss.py aus den Klippenkacheln. Nicht von Hand ändern.\n"
        f"// Abdeckung der Wände aus dem Geländemodell (Zoom 13, {len(tiles)} Kacheln) für den Stilausdruck \"within\".\n"
        f"export const KLIPPEN_UMRISS = {json.dumps(geo, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    print(f"{len(tiles)} Kacheln -> {args.out} ({sum(len(r) for p in geo['coordinates'] for r in p)} Punkte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
