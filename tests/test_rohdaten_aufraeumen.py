"""Tests für tools/rohdaten_aufraeumen.py: löscht den Arbeitsordner nur, wenn alles fertig ist, die App läuft und kein Schutzvermerk liegt."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("rohdaten_aufraeumen", ROOT / "tools" / "rohdaten_aufraeumen.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


@pytest.fixture
def welt(tmp_path, monkeypatch):
    """Fertiger Zustand: Arbeitsordner mit Rohdaten, Webordner mit Relief, Felswänden, Basiskarte und Export; App antwortet."""
    work, web = tmp_path / "dgm1", tmp_path / "web"
    (work / "raw").mkdir(parents=True)
    (work / "red").mkdir()
    (work / "raw" / "1_2.npz").write_bytes(b"x" * 1000)
    (work / "red" / "1_2.npy").write_bytes(b"y" * 100)
    (work / "dgm1_tif_07.meta4").write_text("<metalink/>")
    dem = web / "tiles" / "dem"
    (dem / "14" / "1").mkdir(parents=True)
    (dem / "14" / "1" / "2.png").write_bytes(b"p")
    (dem / "README.txt").write_text("x")
    (dem / "meta.json").write_text(json.dumps({"max_zoom": 14}))
    kl = web / "tiles" / "klippen"
    (kl / "13" / "1").mkdir(parents=True)
    (kl / "13" / "1" / "2.pbf").write_bytes(b"v")
    (kl / "meta.json").write_text("{}")
    (web / "tiles" / "region.pmtiles").write_bytes(b"pm")
    (web / "data").mkdir()
    (web / "data" / "manifest.json").write_text("{}")
    monkeypatch.setattr(R, "pruefe_pfad", lambda w: None)    # tmp_path liegt flach genug, hier geht es nicht um den Pfadschutz

    class Antwort:
        status_code = 200

    monkeypatch.setattr("httpx.get", lambda *a, **k: Antwort())
    return work, web


def lauf(work, web, *extra):
    return R.main(["--work", str(work), "--web", str(web), *extra])


def test_probelauf_loescht_nichts(welt):
    work, web = welt
    assert lauf(work, web) == 0 and (work / "raw" / "1_2.npz").exists()


def test_ja_loescht_alles_wenn_fertig(welt):
    work, web = welt
    assert lauf(work, web, "--ja") == 0 and not work.exists()


def test_schutzvermerk_haelt_die_daten(welt):
    work, web = welt
    (work / "BEHALTEN.txt").write_text("x")
    assert lauf(work, web, "--ja") == 2 and (work / "raw" / "1_2.npz").exists()


@pytest.mark.parametrize("fehlt", ["tiles/dem/meta.json", "tiles/dem/14/1/2.png", "tiles/klippen/meta.json", "tiles/klippen/13/1/2.pbf",
                                   "tiles/region.pmtiles", "data/manifest.json"])
def test_fehlt_etwas_bleibt_alles_liegen(welt, fehlt):
    work, web = welt
    (web / fehlt).unlink()
    assert lauf(work, web, "--ja") == 1 and (work / "raw" / "1_2.npz").exists()


def test_app_down_oder_fehler_bleibt_liegen(welt, monkeypatch):
    work, web = welt

    class Fehler:
        status_code = 503

    monkeypatch.setattr("httpx.get", lambda *a, **k: Fehler())
    assert lauf(work, web, "--ja") == 1 and work.exists()

    import httpx

    def kaputt(*a, **k):
        raise httpx.ConnectError("aus")

    monkeypatch.setattr("httpx.get", kaputt)
    assert lauf(work, web, "--ja") == 1 and work.exists()


def test_fremde_inhalte_werden_abgelehnt(welt):
    work, web = welt
    (work / "meine_doktorarbeit.docx").write_text("wichtig")
    assert lauf(work, web, "--ja") == 2 and (work / "meine_doktorarbeit.docx").exists()


def test_unsichere_pfade_abgelehnt(tmp_path):
    assert R.pruefe_pfad(Path("/")) and R.pruefe_pfad(Path.home()) and R.pruefe_pfad(R.ROOT)
    assert R.pruefe_pfad(R.ROOT.parent)    # enthält das Projekt
    assert R.pruefe_pfad(tmp_path / "a" / "b") is None


def test_fehlender_arbeitsordner_ist_nichts_zu_tun(tmp_path):
    assert R.main(["--work", str(tmp_path / "gibt-es-nicht"), "--web", str(tmp_path)]) == 0
