"""Abdeckung der Klippenkacheln: Kachelmenge -> Umriss, Punkt-in-Fläche."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("bku", ROOT / "tools/build_klippen_umriss.py")
bku = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bku)


def test_liste_ergibt_umriss(tmp_path):
    lst = tmp_path / "k.txt"
    lst.write_text("4240 2784;4241 2784;4241 2785")
    out = tmp_path / "u.js"
    import sys
    old = sys.argv
    sys.argv = ["x", "--list", str(lst), "--out", str(out)]
    try:
        assert bku.main() == 0
    finally:
        sys.argv = old
    geo = json.loads(re.search(r"= (\{.*\});", out.read_text()).group(1))
    g = shape(geo)
    assert g.contains(Point((bku.lon(4240) + bku.lon(4241)) / 2, (bku.lat(2784) + bku.lat(2785)) / 2))   # Mitte der Kachel 4240/2784
    assert not g.contains(Point(6.13, 49.61))   # Luxemburg-Stadt, keine Kachel


def test_eingecheckter_umriss_deckt_grenzstreifen():
    src = (ROOT / "web/js/lage/klippen-umriss.js").read_text()
    g = shape(json.loads(re.search(r"= (\{.*\});", src).group(1)))
    assert g.contains(Point(6.34, 49.82))       # Berdorf: hier gibt es Wandkacheln, OSM-Klippen dürfen nicht doppelt erscheinen
    assert g.contains(Point(6.64, 49.75))       # Trier
    assert not g.contains(Point(5.98, 49.50))   # Esch-sur-Alzette, weit außerhalb
