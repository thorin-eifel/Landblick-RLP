"""Tests der Länder-Quellen: LHP (Pegel, Hochwasserwarnungen), MobiData BW (Baustellen, Verkehrsmeldungen)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app import geo, region
from app.collectors import load_collector_class
from app.collectors.base import Collector, SourceError
from conftest import FIX, fixture, make_client

ROOT = Path(__file__).resolve().parent.parent


def _make(registry, storage, settings, name, handler, keep_all=True, monkeypatch=None):
    if keep_all and monkeypatch is not None:
        monkeypatch.setattr(Collector, "keep", staticmethod(lambda g: True))
    client, router = make_client(handler)
    entry = registry.get(name)
    c = load_collector_class(entry.collector)(entry, storage, client, settings, backoff_base_s=0.0)
    return c, client, router


def _lhp(stations=None, alerts=None, alerts_status=200):
    def h(req: httpx.Request):
        if req.url.path.endswith("/stations"):
            return stations if stations is not None else fixture("lhp_stations_real_KLASSEN_SYNTHETISCH.json")
        return httpx.Response(alerts_status, json=alerts if alerts is not None else fixture("lhp_alerts_SYNTHETISCH.json"))
    return h


# ------------------------------------------------------------------ LHP
async def test_lhp_pegelklassen_und_warnungen(registry, storage, settings, monkeypatch):
    c, client, router = _make(registry, storage, settings, "lhp_hochwasser", _lhp(), monkeypatch=monkeypatch)
    res = await c.collect()
    await client.aclose()
    q = router.calls[0].url.params
    assert q["format"] == "geojson" and q["states"] == "NW,HE,BW,BY,SL"
    assert router.calls[0].headers["accept"] == "application/geo+json"     # mit application/json liefert der Server eine andere Struktur
    ev = {e.id: e for e in res.events}
    # Pegel: Klasse 0 ergibt kein Ereignis; 1 notice, 2 warning, 3 und 4 critical
    assert {k for k in ev if k.startswith("lhp:")} == {"lhp:BW_105", "lhp:NW_2710080", "lhp:NW_2721390000100", "lhp:HE_23940359"}
    assert ev["lhp:NW_2721390000100"].severity == "notice" and ev["lhp:BW_105"].severity == "warning"
    assert ev["lhp:NW_2710080"].severity == "critical" and ev["lhp:HE_23940359"].severity == "critical"
    p = ev["lhp:BW_105"]
    assert p.type == "flood" and p.region_tag == "DE-BW" and p.geometry["type"] == "Point"
    assert "Datenquelle: www.hochwasserzentralen.de" in p.summary and "Stand 12.10.2026" in p.summary
    assert p.valid_from.isoformat().startswith("2026-10-12T07:00")        # 09:00 Ortszeit (MESZ) = 07:00 UTC
    assert p.raw_ref.startswith("https://www.hvz.baden-wuerttemberg.de")
    # Warnungen: Entwarnung (Klasse 1) ohne Ereignis, Vorwarnung notice, Hochwasser warning, Fläche
    assert {k for k in ev if k.startswith("lhpwarn:")} == {"lhpwarn:BW_901", "lhpwarn:NW_903"}
    assert ev["lhpwarn:BW_901"].severity == "warning" and ev["lhpwarn:NW_903"].severity == "notice"
    assert ev["lhpwarn:BW_901"].geometry["type"] == "Polygon" and ev["lhpwarn:BW_901"].attrs["kind"] == "hochwasserwarnung"
    assert res.complete is True


async def test_lhp_unsichere_felder_werden_bereinigt(registry, storage, settings, monkeypatch):
    c, client, _ = _make(registry, storage, settings, "lhp_hochwasser", _lhp(), monkeypatch=monkeypatch)
    res = await c.collect()
    await client.aclose()
    w = next(e for e in res.events if e.id == "lhpwarn:NW_903")
    assert "<" not in w.title and "javascript" not in (w.raw_ref or "")      # HTML raus, nur https-Links
    assert w.raw_ref.startswith("https://")


async def test_lhp_warnungen_ausfall_laesst_pegel_stehen(registry, storage, settings, monkeypatch):
    c, client, _ = _make(registry, storage, settings, "lhp_hochwasser", _lhp(alerts_status=503), monkeypatch=monkeypatch)
    res = await c.collect()
    await client.aclose()
    assert any(e.id.startswith("lhp:") for e in res.events) and not any(e.id.startswith("lhpwarn:") for e in res.events)
    assert res.complete is False and "Warnungen" in res.note


async def test_lhp_schemaaenderung_ist_fehler(registry, storage, settings, monkeypatch):
    c, client, _ = _make(registry, storage, settings, "lhp_hochwasser", _lhp(stations={"foo": 1}), monkeypatch=monkeypatch)
    with pytest.raises(SourceError):
        await c.collect()
    await client.aclose()


# ------------------------------------------------------------------ BW Baustellen
def _bw_baustellen():
    return lambda req: fixture("mobidata_bw_roadworks_real_gekuerzt.json")


async def test_bw_baustellen_mapping_ohne_autobahn(registry, storage, settings, monkeypatch):
    c, client, router = _make(registry, storage, settings, "mobidata_bw_baustellen", _bw_baustellen(), monkeypatch=monkeypatch)
    res = await c.collect()
    await client.aclose()
    assert len(router.calls) == 1 and len(res.events) == 5          # sechs Einträge, einer mit Autobahnnummer fällt weg
    assert not any("A5" in e.title for e in res.events)
    closed = [e for e in res.events if e.attrs["kind"] == "sperrung"]
    works = [e for e in res.events if e.attrs["kind"] == "baustelle"]
    assert closed and works and all(e.severity == "warning" for e in closed) and all(e.severity == "notice" for e in works)
    assert {e.attrs.get("sperr") for e in closed} == {"voll", "richtung"}
    assert all(e.type == "traffic" and e.region_tag == "DE-BW" and e.geometry["type"] == "LineString" for e in res.events)
    assert all(e.valid_from is not None for e in res.events)


async def test_bw_baustellen_idempotent_und_schema(registry, storage, settings, monkeypatch):
    c, client, _ = _make(registry, storage, settings, "mobidata_bw_baustellen", _bw_baustellen(), monkeypatch=monkeypatch)
    a, b = await c.collect(), await c.collect()
    assert [e.id for e in a.events] == [e.id for e in b.events] and len({e.id for e in a.events}) == len(a.events)
    await client.aclose()
    c2, client2, _ = _make(registry, storage, settings, "mobidata_bw_baustellen", lambda r: {"nope": []}, monkeypatch=monkeypatch)
    with pytest.raises(SourceError):
        await c2.collect()
    await client2.aclose()


async def test_bw_baustellen_regionsfilter_am_rand(registry, storage, settings, monkeypatch):
    # echte Landesfläche (RLP plus 80 km): der Eintrag am Hochrhein (L154 Albbruck) liegt weit draußen, die Einträge bei Böblingen und
    # Sindelfingen liegen noch innerhalb der 80 km
    monkeypatch.setattr(geo._region, "REGION", region.load(ROOT / "region.yaml"))
    c, client, _ = _make(registry, storage, settings, "mobidata_bw_baustellen", _bw_baustellen(), keep_all=False)
    res = await c.collect()
    await client.aclose()
    assert len(res.events) == 4 and not any("L 154" in e.title or "L154" in e.title for e in res.events)


# ------------------------------------------------------------------ BW Verkehrsmeldungen
def _bw_meldungen():
    data = (FIX / "mobidata_bw_incidents_real_gekuerzt_teils_SYNTHETISCH.xml").read_bytes()
    return lambda req: httpx.Response(200, content=data, headers={"content-type": "application/xml"})


async def test_bw_meldungen_filtert_baustellen_und_autobahn(registry, storage, settings, monkeypatch):
    c, client, _ = _make(registry, storage, settings, "mobidata_bw_meldungen", _bw_meldungen(), monkeypatch=monkeypatch)
    res = await c.collect()
    await client.aclose()
    text = " ".join(e.title + " " + e.summary for e in res.events)
    assert "Baustelle" not in text and "Hohenheimer" not in text        # Baustellen kommen aus mobidata_bw_baustellen
    assert "A8 Stuttgart" not in text and "B37" in text                 # Autobahnmeldung fällt weg, Bundesstraße bleibt
    kinds = {e.attrs["kind"] for e in res.events}
    assert {"stau", "unfall", "warnung"} <= kinds or {"stau", "warnung"} <= kinds
    stau = next(e for e in res.events if e.attrs["kind"] == "stau")
    assert stau.type == "congestion" and stau.region_tag == "DE-BW" and stau.geometry["type"] in ("Point", "LineString")
    unfall = next(e for e in res.events if "Hauptstraße" in e.summary)
    assert unfall.severity == "warning" and "Landesmeldestelle" in unfall.summary
    assert len({e.id for e in res.events}) == len(res.events)


async def test_bw_meldungen_kaputtes_xml_ist_fehler(registry, storage, settings, monkeypatch):
    c, client, _ = _make(registry, storage, settings, "mobidata_bw_meldungen", lambda r: httpx.Response(200, content=b"<html>nope"), monkeypatch=monkeypatch)
    with pytest.raises(SourceError):
        await c.collect()
    await client.aclose()


def test_register_eintraege_vollstaendig(registry):
    for sid in ("lhp_hochwasser", "mobidata_bw_baustellen", "mobidata_bw_meldungen"):
        e = registry.get(sid)
        assert e.aktiv if hasattr(e, "aktiv") else True
        assert e.lizenz_geprueft is False and e.url.startswith("https://") and e.auth == "keine"
