"""Energie: SGD-Nord-Parser (Fixtures aus echten Antworten), OSM-Parser (SYNTHETISCH), Zusammenführung in den Nutzlasten, Zellenzuordnung."""
from __future__ import annotations

import pytest

from app import export_cells, payloads
from app.collectors import osm_energie, rlp_energie
from app.collectors.base import SourceError

from conftest import fixture


# ------------------------------------------------------------------ SGD Nord (amtlich)
def test_wind_keeps_only_existing_or_planned_inside_region():
    got = rlp_energie.parse_wind(fixture("sgdnord_wind_real_2026-10-16.json"))
    states = sorted({i["state"] for i in got})
    assert states == ["beantragt", "genehmigt", "netz"]            # aufgegeben und rueckgebaut fehlen
    assert len(got) == 6                                            # 3 Stände x 2; das Windrad im Westerwald liegt außerhalb der Region
    w = got[0]
    assert w["kind"] == "wind" and w["src"] == "rok" and w["id"].startswith("rok/wind/") and w["kw"] > 0 and w["hub"] > 0


def test_wind_drops_operator_type_and_files():
    blob = repr(rlp_energie.parse_wind(fixture("sgdnord_wind_real_2026-10-16.json")))
    for leak in ("typ", "Enercon", "Vestas", "Nordex", "open_docurl", "rok25online", "datum_antr", "windpark"):
        assert leak not in blob


def test_solar_has_ring_centroid_and_no_operator():
    got = rlp_energie.parse_solar(fixture("sgdnord_pv_real_2026-10-16.json"))
    assert got and all(i["state"] in ("netz", "genehmigt", "beantragt") for i in got)
    s = got[0]
    assert s["kind"] == "solar" and s["ring"][0] == s["ring"][-1] and len(s["ring"]) >= 4
    lons, lats = [p[0] for p in s["ring"]], [p[1] for p in s["ring"]]
    assert min(lats) <= s["lat"] <= max(lats) and min(lons) <= s["lon"] <= max(lons)
    assert "betreiber" not in repr(got).lower() and "GmbH" not in repr(got)


@pytest.mark.parametrize("fn", [rlp_energie.parse_wind, rlp_energie.parse_solar])
def test_sgdnord_rejects_unexpected_shape(fn):
    with pytest.raises(SourceError):
        fn({"unerwartet": True})


# ------------------------------------------------------------------ OpenStreetMap (synthetisch)
def _line(i, voltage, *pts):
    return {"type": "way", "id": i, "tags": {"power": "line", "voltage": voltage, "operator": "Netz GmbH", "ref": "1234"}, "geometry": [{"lat": la, "lon": lo} for lo, la in pts]}


def test_line_classes_and_region_SYNTHETISCH():
    data = {"elements": [
        _line(1, "380000;110000", (6.40, 49.80), (6.41, 49.80), (6.42, 49.80), (6.43, 49.8001)),
        _line(2, "110000", (6.40, 49.81), (6.41, 49.81)),
        _line(3, "20000", (6.40, 49.82), (6.41, 49.82)),                  # Mittelspannung
        _line(4, "380000", (13.4, 52.5), (13.5, 52.5)),                   # Berlin, außerhalb
    ]}
    got = {i["id"]: i for i in osm_energie.parse_elements(data, "line")}
    assert set(got) == {"way/1", "way/2"}
    assert got["way/1"]["kv"] == 380 and got["way/2"]["kv"] == 110
    assert len(got["way/1"]["lines"][0]) == 2                             # kollineare Zwischenpunkte entfallen
    assert "Netz GmbH" not in repr(got) and "1234" not in repr(got)


def test_points_keep_technical_names_only_SYNTHETISCH():
    def el(i, **tags):
        return {"type": "node", "id": i, "lat": 49.84, "lon": 6.45, "tags": tags}
    plants = osm_energie.parse_elements({"elements": [
        el(1, power="plant", **{"plant:source": "gas", "name": "Gaskraftwerk Beispiel", "plant:output:electricity": "120 MW", "operator": "X"}),
        el(2, power="plant", **{"plant:source": "solar", "name": "Solarpark Familie Muster"}),
        el(3, power="plant", **{"plant:source": "biomass", "name": "Biogas Hof Meier"}),
        el(4, power="plant", **{"plant:source": "wind"}),
        el(5, power="plant", **{"plant:source": "hydro", "name": "Haus am Bach"}),
    ]}, "plant")
    by = {i["id"]: i for i in plants}
    assert set(by) == {"node/1", "node/2", "node/3", "node/5"}            # Windpark fällt weg
    assert by["node/1"]["source"] == "gas" and by["node/1"]["kw"] == 120000 and by["node/1"]["name"] == "Gaskraftwerk Beispiel"
    assert by["node/2"]["kind"] == "solar" and "name" not in by["node/2"]
    assert "name" not in by["node/3"] and "name" not in by["node/5"]      # kein technischer Name
    assert "operator" not in repr(plants)
    subs = osm_energie.parse_elements({"elements": [el(7, power="substation", substation="transmission", voltage="380000;110000", name="Umspannwerk Beispiel"),
                                                    el(8, power="substation", voltage="110000", name="Privat Müller")]}, "substation")
    assert {i["id"]: i.get("name") for i in subs} == {"node/7": "Umspannwerk Beispiel", "node/8": None}
    assert {i["id"]: i["kv"] for i in subs} == {"node/7": 380, "node/8": 110}


def test_queries_survive_regex_braces():
    for kind in osm_energie.KINDS:
        q = osm_energie.build_query(kind, (49.0, 6.0, 50.0, 7.0))
        assert "(49.0,6.0,50.0,7.0)" in q and "{box}" not in q
    assert "[0-9]{3}" in osm_energie.build_query("line", (49.0, 6.0, 50.0, 7.0))


# ------------------------------------------------------------------ Zusammenführung und Zellen
def _put(storage, key, payload):
    storage.cache_put(key, "test", payload)


def test_official_wind_replaces_nearby_osm_and_extends(storage, registry):
    _put(storage, "infrastruktur", {"items": [
        {"id": "node/1", "kind": "wind", "name": "", "lat": 49.8400, "lon": 6.4500},      # selbes Windrad wie das amtliche (ca. 20 m)
        {"id": "node/2", "kind": "wind", "name": "", "lat": 49.9000, "lon": 6.5000},      # nur in OSM
        {"id": "node/3", "kind": "charging", "name": "", "lat": 49.84, "lon": 6.45}]})
    _put(storage, "energie_rok", {"wind": [{"id": "rok/wind/9", "kind": "wind", "src": "rok", "lat": 49.8401, "lon": 6.4502, "state": "genehmigt", "kw": 6000}], "solar": []})
    items = {i["id"]: i for i in payloads.infrastruktur_payload(storage, registry)["items"]}
    assert set(items) == {"node/2", "node/3", "rok/wind/9"}
    assert items["rok/wind/9"]["source_id"] == "sgdnord_energie" and items["rok/wind/9"]["kw"] == 6000


def test_official_wind_shows_without_osm_cache(storage, registry):
    _put(storage, "energie_rok", {"wind": [{"id": "rok/wind/9", "kind": "wind", "src": "rok", "lat": 49.84, "lon": 6.45, "state": "netz"}], "solar": []})
    assert [i["id"] for i in payloads.infrastruktur_payload(storage, registry)["items"]] == ["rok/wind/9"]


def test_energie_payload_prefers_official_solar(storage, registry):
    _put(storage, "energie_osm", {"items": [
        {"id": "way/5", "kind": "solar", "src": "osm", "lat": 49.8400, "lon": 6.4500},
        {"id": "way/6", "kind": "solar", "src": "osm", "lat": 49.9500, "lon": 6.6000},
        {"id": "way/7", "kind": "line", "kv": 380, "lines": [[[6.4, 49.8], [6.6, 49.8]]]}]})
    _put(storage, "energie_rok", {"wind": [], "solar": [{"id": "rok/solar/1", "kind": "solar", "src": "rok", "lat": 49.8402, "lon": 6.4503, "state": "netz", "ring": [[6.45, 49.84], [6.46, 49.84], [6.46, 49.85], [6.45, 49.84]]}]})
    p = payloads.energie_payload(storage, registry)
    assert [i["id"] for i in p["items"]] == ["way/7", "rok/solar/1", "way/6"]


def test_energie_cells_lines_span_cells_points_one(storage, registry):
    line = {"id": "way/7", "kind": "line", "kv": 380, "lines": [[[6.1, 49.8], [6.9, 49.8]]]}      # quert die 0,5-Grad-Grenze bei 6,5
    point = {"id": "node/1", "kind": "substation", "lat": 49.84, "lon": 6.45}
    cells = export_cells.split_payload("energie", {"items": [line, point], "source": None}, registry)
    with_line = [c for c, v in cells.items() if any(i["id"] == "way/7" for i in v["items"])]
    with_point = [c for c, v in cells.items() if any(i["id"] == "node/1" for i in v["items"])]
    assert len(with_line) >= 2 and len(with_point) == 1
