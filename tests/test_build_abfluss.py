"""Tests für tools/build_abfluss.py: Rechenkern (C) auf einem synthetischen Gelände, Verkettung, Größenklassen, Kachelzuordnung."""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("build_abfluss", Path(__file__).resolve().parent.parent / "tools" / "build_abfluss.py")
ba = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ba)

braucht_cc = pytest.mark.skipif(shutil.which("cc") is None, reason="kein C-Compiler")


def v_tal(h=40, w=41):
    """Rinne in der Mitte (Spalte w//2), fällt nach unten (Zeile h-1 = Auslauf), Hänge zu beiden Seiten."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return (100.0 - 0.5 * y + 2.0 * np.abs(x - w // 2)).astype(np.float32)


def test_klasse_stufen():
    assert ba.klasse(10000) == 0          # 1 ha
    assert ba.klasse(49999) == 0
    assert ba.klasse(50000) == 1          # 5 ha
    assert ba.klasse(250000) == 2         # 25 ha
    assert ba.klasse(10) == 0             # unter 1 ha bleibt 0


def test_kachel_von_koordinate():
    x, y = ba.tile_of(6.4473, 49.8497, 14)
    x2, y2 = ba.tile_of(6.6473, 49.6497, 14)
    assert 0 < x < 2 ** 14 and 0 < y < 2 ** 14
    assert x2 > x and y2 > y                              # nach Osten wächst x, nach Süden y


@braucht_cc
def test_kern_sammelt_in_der_rinne(tmp_path):
    dem = v_tal()
    d, acc, tiefe = ba.rechnen(dem, 5500, tmp_path)
    mitte = dem.shape[1] // 2
    assert acc[-2, mitte] > acc[2, mitte] * 5            # Fläche wächst talwärts
    assert acc[-2, mitte] > acc[-2, 3] * 5               # Rinne trägt mehr als der Hang
    assert (tiefe >= 0).all() and tiefe.max() < 0.01     # keine Senke im glatten Tal


@braucht_cc
def test_kern_findet_senke(tmp_path):
    dem = v_tal()
    dem[20:23, 18:21] -= 6.0                              # Loch in der Rinne
    d, acc, tiefe = ba.rechnen(dem, 5500, tmp_path)
    assert 2.5 < tiefe[21, 19] < 6.5                      # Loch minus Gefälle bis zum Überlauf


@braucht_cc
def test_ketten_enden_am_zusammenfluss(tmp_path):
    dem = v_tal()
    d, acc, tiefe = ba.rechnen(dem, 5500, tmp_path)
    maske = np.ones(dem.shape, bool)
    idx, stuecke = ba.ketten(acc, d, maske, schwelle_m2=float(acc[-2, dem.shape[1] // 2]) * 0.05)
    assert idx.size > 0 and stuecke
    # jede Zelle der Menge liegt in mindestens einem Stück
    belegt = set()
    for pos, _, _ in stuecke:
        belegt.update(pos)
    assert belegt == set(range(idx.size))


def test_ketten_ohne_treffer():
    acc = np.zeros((4, 4), np.float32)
    d = np.zeros((4, 4), np.uint8)
    idx, stuecke = ba.ketten(acc, d, np.ones((4, 4), bool), 1.0)
    assert idx.size == 0 and stuecke == []


def test_glatt_haelt_enden_und_schneidet_ecken():
    roh = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (2.0, 1.0)]
    g = ba.glatt(roh)
    assert g[0] == roh[0] and g[-1] == roh[-1]
    assert len(g) > len(roh)
    assert (1.0, 0.0) not in g                           # die Ecke selbst ist weg
    assert ba.glatt(roh[:2]) == roh[:2]
