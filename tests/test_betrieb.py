"""R6 Betrieb: Gesundheitsprüfung, Wiederherstellungstest, Chaos (Quellen aus, Platte voll), Pinning der Abhängigkeiten."""
from __future__ import annotations

import errno
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import backup  # noqa: E402
import gesundheit  # noqa: E402

from app import export  # noqa: E402
from app.models import utcnow  # noqa: E402
from test_sanitize_registry_db import ev  # noqa: E402


def _ok(storage, sid, ago_s=10):
    storage.record_run(sid, utcnow() - timedelta(seconds=ago_s), 50, True)


def _fail(storage, sid, n=1):
    for _ in range(n):
        storage.record_run(sid, utcnow(), 50, False, error="HTTP 503")


def _collectors(registry):
    return [e.id for e in registry.entries if e.art == "collector" and e.aktiv]


def _export_meta(tmp_path, age_min):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / "meta.json").write_text(json.dumps({"generated_at": (utcnow() - timedelta(minutes=age_min)).isoformat().replace("+00:00", "Z")}))
    return d


# --- Gesundheitsprüfung ------------------------------------------------------------------

def test_gesundheit_ok_bei_frischem_stand(storage, registry, tmp_path):
    for sid in _collectors(registry):
        _ok(storage, sid)
    r = gesundheit.evaluate(storage, registry, _export_meta(tmp_path, 3))
    assert r["overall"] == "OK" and r["exit"] == 0 and r["counts"]["down"] == 0


def test_gesundheit_eine_quelle_down_ist_warnung_und_nennt_region(storage, registry, tmp_path):
    ids = _collectors(registry)
    for sid in ids:
        _ok(storage, sid)
    storage.replace_snapshot("autobahn", [ev("a")])
    _fail(storage, "autobahn", 3)
    r = gesundheit.evaluate(storage, registry, _export_meta(tmp_path, 3))
    assert r["exit"] == 1
    reg = r["regions"]["DE-RLP"]
    assert reg["worst"] == "down" and reg["problem"] == ["autobahn"]
    assert any("ausgefallen" in g for g in r["reasons"])


def test_gesundheit_kritisch_wenn_haelfte_ausfaellt(storage, registry, tmp_path):
    ids = _collectors(registry)
    for sid in ids[: len(ids) // 2 + 1]:
        _fail(storage, sid, 3)
    r = gesundheit.evaluate(storage, registry, _export_meta(tmp_path, 3))
    assert r["exit"] == 2


@pytest.mark.parametrize("alter,erwartet", [(5, 0), (19.9, 0), (20, 1), (59, 1), (60, 2), (600, 2)])
def test_gesundheit_exportalter_schwellen(storage, registry, tmp_path, alter, erwartet):
    for sid in _collectors(registry):
        _ok(storage, sid)
    assert gesundheit.evaluate(storage, registry, _export_meta(tmp_path, alter))["exit"] == erwartet


def test_gesundheit_export_fehlt_ist_kritisch(storage, registry, tmp_path):
    for sid in _collectors(registry):
        _ok(storage, sid)
    assert gesundheit.evaluate(storage, registry, tmp_path / "gibtsnicht")["exit"] == 2


def test_gesundheit_veraltet_nach_dreifachem_intervall(storage, registry, tmp_path):
    e = next(x for x in registry.entries if x.art == "collector" and x.aktiv)
    for sid in _collectors(registry):
        _ok(storage, sid)
    spaeter = utcnow() + timedelta(seconds=3 * e.intervall + 60)
    r = gesundheit.evaluate(storage, registry, _export_meta(tmp_path, 1 + (3 * e.intervall + 60) / 60), now=spaeter)
    assert next(q for q in r["sources"] if q["id"] == e.id)["status"] == "stale"


def test_gesundheit_cli_exitcodes(settings, storage, registry, tmp_path, capsys):
    _ok(storage, _collectors(registry)[0])
    args = ["--db", str(settings.db_path), "--export", str(tmp_path / "leer"), "--json"]
    assert gesundheit.main(args) == 2   # Export fehlt
    assert json.loads(capsys.readouterr().out)["overall"] == "KRITISCH"
    assert gesundheit.main(["--db", str(tmp_path / "nix.sqlite")]) == 2


def test_gesundheit_schreibt_nichts(settings, storage, registry, tmp_path):
    before = settings.db_path.read_bytes()
    gesundheit.main(["--db", str(settings.db_path), "--export", str(tmp_path)])
    assert not Path(str(settings.db_path) + "-journal").exists()
    assert settings.db_path.stat().st_size == len(before)


# --- Sicherung und Wiederherstellung -----------------------------------------------------

def test_restore_test_besteht_und_erkennt_manipulation(settings, storage, tmp_path):
    storage.replace_snapshot("autobahn", [ev("a"), ev("b")])
    _ok(storage, "autobahn")
    out = tmp_path / "bk"
    f = backup.backup_once(settings.db_path, out, keep=3)
    assert backup.sidecar(f).exists()
    res = backup.verify_latest(out)
    assert res["tables"]["events"] == 2 and res["active_probe"] == 2
    with f.open("r+b") as fh:                      # ein Byte kippen
        fh.seek(-10, 2)
        b = fh.read(1)
        fh.seek(-10, 2)
        fh.write(bytes([b[0] ^ 0xFF]))
    with pytest.raises(RuntimeError, match="Prüfsumme"):
        backup.verify_latest(out)


def test_restore_test_ohne_pruefsumme_oder_sicherung(settings, storage, tmp_path):
    with pytest.raises(FileNotFoundError):
        backup.verify_latest(tmp_path / "leer")
    f = backup.backup_once(settings.db_path, tmp_path / "bk", keep=3)
    backup.sidecar(f).unlink()
    with pytest.raises(RuntimeError, match="Prüfsummendatei"):
        backup.verify_latest(tmp_path / "bk")


def test_restore_erkennt_abweichende_zeilenzahl(settings, storage, tmp_path):
    storage.replace_snapshot("autobahn", [ev("a")])
    f = backup.backup_once(settings.db_path, tmp_path / "bk", keep=3)
    side = backup.sidecar(f)
    meta = json.loads(side.read_text())
    meta["tables"]["events"] = 99
    side.write_text(json.dumps(meta))
    with pytest.raises(RuntimeError, match="Zeilenzahlen.*events"):
        backup.verify_latest(tmp_path / "bk")


def test_rotation_raeumt_pruefsummen_mit_auf(settings, storage, tmp_path):
    out = tmp_path / "bk"
    for i in range(3):
        f = backup.backup_once(settings.db_path, out, keep=2)
        neu = out / f"landblick-2026010{i}T000000Z.sqlite"
        f.rename(neu)
        backup.sidecar(f).rename(backup.sidecar(neu))
    backup.backup_once(settings.db_path, out, keep=2)
    assert len(list(out.glob("landblick-*.sqlite"))) == 2 and len(list(out.glob("landblick-*.sqlite.json"))) == 2


# --- Chaos: Platte voll beim Export -------------------------------------------------------

def test_export_bei_voller_platte_laesst_alten_stand_stehen(storage, registry, tmp_path, monkeypatch):
    out = tmp_path / "data"
    export.run_export(storage, registry, out)
    vorher = {p.name: p.read_bytes() for p in out.glob("*.json")}
    assert "meta.json" in vorher and "manifest.json" in vorher
    storage.replace_snapshot("autobahn", [ev("neu")])   # neuer Stand, der geschrieben werden soll
    orig = Path.write_bytes
    zaehler = {"n": 0}

    def voll(self, data):
        zaehler["n"] += 1
        if zaehler["n"] > 3:
            raise OSError(errno.ENOSPC, "No space left on device")
        return orig(self, data)
    monkeypatch.setattr(Path, "write_bytes", voll)
    with pytest.raises(OSError):
        export.run_export(storage, registry, out)
    monkeypatch.undo()
    assert not list(out.rglob(".*.tmp")), "halbe Temp-Dateien dürfen nicht liegen bleiben"
    for name in ("manifest.json", "start.json"):
        json.loads((out / name).read_text())            # alte Dateien bleiben lesbar
    assert json.loads((out / "manifest.json").read_text()) == json.loads(vorher["manifest.json"]), "Manifest wird zuletzt geschrieben, also unverändert"
    export.run_export(storage, registry, out)           # und der nächste Lauf heilt
    assert not list(out.rglob(".*.tmp"))


# --- Chaos: alle Quellen aus ----------------------------------------------------------------

def test_alle_quellen_down_export_und_status_bleiben_lesbar(storage, registry, tmp_path):
    for sid in _collectors(registry):
        _fail(storage, sid, 3)
    out = tmp_path / "data"
    export.run_export(storage, registry, out)
    st = json.loads((out / "status.json").read_text())
    stati = {s["status"] for s in (st["sources"] if isinstance(st, dict) and "sources" in st else st)}
    assert "down" in stati
    r = gesundheit.evaluate(storage, registry, out)
    assert r["exit"] == 2 and r["counts"]["down"] == len(_collectors(registry))


# --- Zeitumstellung ---------------------------------------------------------------------------

@pytest.mark.parametrize("jetzt", ["2026-03-29T00:30:00Z", "2026-03-29T01:30:00Z", "2026-10-25T00:30:00Z", "2026-10-25T01:30:00Z"])
def test_zeitfenster_ueber_die_umstellung_hinweg(storage, monkeypatch, jetzt):
    """Die Umstellung liegt um 01:00 UTC. Fenster werden in UTC gerechnet, also bleiben 24 Stunden 24 Stunden."""
    from app import db
    from app.models import Event
    t0 = datetime.fromisoformat(jetzt.replace("Z", "+00:00"))
    monkeypatch.setattr(db, "utcnow", lambda: t0)

    def e(i, h):
        return Event(id=f"autobahn:{i}", source_id="autobahn", type="traffic", title=i, severity="info",
                     geometry={"type": "Point", "coordinates": [6.46, 49.86]}, fetched_at=t0, valid_from=t0 + timedelta(hours=h))
    storage.replace_snapshot("autobahn", [e("innen", 23.98), e("aussen", 24.02), e("jetzt", -1)])
    ids = lambda h: sorted(x["id"].split(":")[1] for x in storage.active_events(within_hours=h))  # noqa: E731
    assert ids(0) == ["jetzt"]
    assert ids(24) == ["innen", "jetzt"]
    assert ids(168) == ["aussen", "innen", "jetzt"]


def test_zeitstempel_im_export_tragen_utc():
    from app.models import iso
    assert iso(datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc)).endswith("Z")
    assert iso(utcnow()).endswith("Z")


# --- Pinning ------------------------------------------------------------------------------------

@pytest.mark.parametrize("datei", ["requirements.txt", "requirements-dev.txt"])
def test_alle_abhaengigkeiten_sind_gepinnt(datei):
    for z in (ROOT / datei).read_text().splitlines():
        z = z.split("#")[0].strip()
        if not z or z.startswith("-r "):
            continue
        assert re.fullmatch(r"[A-Za-z0-9_.\-]+(\[[a-z,]+\])?==[0-9][^\s;]*", z), f"{datei}: nicht gepinnt: {z}"


# --- Dauerlauf-Werkzeug -------------------------------------------------------------------------

import dauerlauf  # noqa: E402


def _row(t0, minuten, overall="OK", problem=None):
    return {"t": dauerlauf.stamp(t0 + timedelta(minutes=minuten)), "overall": overall, "exit": 0, "reasons": [],
            "counts": {}, "problem": problem or {}, "export_age_min": 2}


def test_dauerlauf_sieben_tage_ohne_luecke_besteht():
    t0 = datetime(2026, 10, 14, tzinfo=timezone.utc)
    rows = [_row(t0, m) for m in range(0, 7 * 24 * 60 + 1, 10)]
    a = dauerlauf.analyse(rows)
    assert a["kriterien"] == {"laufzeit": True, "ohne_luecke": True, "ohne_handeingriff": True}
    assert "erfüllt" in dauerlauf.render(a, 30)


def test_dauerlauf_luecke_notiz_und_stoerung():
    t0 = datetime(2026, 10, 14, tzinfo=timezone.utc)
    rows = [_row(t0, 0), _row(t0, 10, "WARNUNG", {"nina": "down"}), _row(t0, 20, "WARNUNG", {"nina": "down"}), _row(t0, 30),
            _row(t0, 200), {"t": dauerlauf.stamp(t0 + timedelta(minutes=201)), "note": "Mac neu gestartet"}]
    a = dauerlauf.analyse(rows, luecke_min=30)
    assert a["luecken"] == [{"von": rows[3]["t"], "bis": rows[4]["t"], "minuten": 170}]
    assert a["laengste_stoerung"]["nina"]["minuten"] == 10
    assert a["kriterien"] == {"laufzeit": False, "ohne_luecke": False, "ohne_handeingriff": False}
    assert "Mac neu gestartet" in dauerlauf.render(a, 30)


def test_dauerlauf_cli_sample_note_report(settings, storage, registry, tmp_path):
    for sid in _collectors(registry):
        _ok(storage, sid)
    f = tmp_path / "d.jsonl"
    base = ["--file", str(f), "--db", str(settings.db_path), "--export", str(_export_meta(tmp_path, 1))]
    assert dauerlauf.main(["sample", *base]) == 0
    assert dauerlauf.main(["note", "Test", *base]) == 0
    f.write_text(f.read_text() + '{"t": "2026-')                      # halbe Zeile nach Stromausfall
    out = tmp_path / "b.md"
    assert dauerlauf.main(["report", *base, "--out", str(out)]) == 0
    assert "Handeingriffe" in out.read_text() and "Test" in out.read_text()
