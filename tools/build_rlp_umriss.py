#!/usr/bin/env python3
"""Grober Umriss von Rheinland-Pfalz als JS-Modul (web/js/lage/rlp-umriss.js).

Zweck:    Die Übersichtskarte filtert Ortsnamen mit dem Stilausdruck ["within", Umriss]: in Rheinland-Pfalz alle Orte, außerhalb nur
          Großstädte. Der Ausdruck braucht die Geometrie synchron beim Stilaufbau, deshalb ein kleines Modul statt Fetch.
Quelle:   web/geo/rlp.geojson (BKG VG250, dl-de/by-2.0, siehe tools/build_landesgrenze.py), hier auf --tol Grad vereinfacht (Standard 0,003, rund 300 m;
          für Beschriftungen reicht das), nur Außenringe.
Aufruf:   python tools/build_rlp_umriss.py            (schreibt web/js/lage/rlp-umriss.js)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from shapely.geometry import MultiPolygon, shape

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=str(ROOT / "web/geo/rlp.geojson"))
    ap.add_argument("--out", default=str(ROOT / "web/js/lage/rlp-umriss.js"))
    ap.add_argument("--tol", type=float, default=0.003)
    a = ap.parse_args()
    doc = json.loads(Path(a.src).read_text(encoding="utf-8"))
    g = shape(doc["features"][0]["geometry"] if "features" in doc else doc.get("geometry", doc))
    polys = list(g.geoms) if isinstance(g, MultiPolygon) else [g]
    rings = []
    for p in polys:
        s = p.simplify(a.tol, preserve_topology=True)
        for q in (s.geoms if isinstance(s, MultiPolygon) else [s]):
            rings.append([[[round(x, 4), round(y, 4)] for x, y in q.exterior.coords]])
    geom = {"type": "MultiPolygon", "coordinates": rings}
    n = sum(len(r[0]) for r in rings)
    Path(a.out).write_text(
        "// Erzeugt von tools/build_rlp_umriss.py aus web/geo/rlp.geojson (BKG VG250, dl-de/by-2.0). Nicht von Hand ändern.\n"
        f"// Grober Umriss von Rheinland-Pfalz für den Stilausdruck \"within\" ({n} Punkte).\n"
        f"export const RLP_UMRISS = {json.dumps(geom, separators=(',', ':'))};\n", encoding="utf-8")
    print(f"{a.out}: {len(polys)} Fläche(n), {n} Punkte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
