"""Installer (install.py), Laufwrapper (tools/lauf.py), portabler Zyklus (tools/zyklus.py): reine Teile ohne Zeitplaner."""
from __future__ import annotations

import asyncio
import plistlib
import signal
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import install  # noqa: E402
import lauf  # noqa: E402
import zyklus  # noqa: E402

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
JOBS = install.job_liste("127.0.0.1", 8080, live=True, dauerlauf=True)
PY = Path("C:/Users/Max Muster/Landblick/.venv/Scripts/pythonw.exe")
WROOT = Path("C:/Users/Max Muster/Landblick")


def test_job_liste_enthaelt_r6_jobs_und_respektiert_schalter():
    namen = {j.name for j in JOBS}
    assert {"zyklus", "spaet", "backup", "health", "web", "live", "dauerlauf"} == namen
    ohne = {j.name for j in install.job_liste("0.0.0.0", 9000, live=False, dauerlauf=False)}
    assert "live" not in ohne and "dauerlauf" not in ohne and "backup" in ohne
    web = next(j for j in install.job_liste("0.0.0.0", 9000, True, False) if j.name == "web")
    assert "9000" in web.args and "0.0.0.0" in web.args


@pytest.mark.parametrize("system", [False, True])
def test_windows_aufgaben_sind_wohlgeformt(system):
    for j in JOBS:
        xml = install.win_task_xml(j, WROOT, PY, "PC\\Max <M>", system, "2026-10-13T14:30:00")
        root = ET.fromstring(xml.split("?>", 1)[1])          # Deklaration abtrennen (UTF-16 steht erst beim Schreiben fest)
        exe = root.find("t:Actions/t:Exec", NS)
        assert exe.findtext("t:Command", namespaces=NS).endswith("pythonw.exe")
        args = exe.findtext("t:Arguments", namespaces=NS)
        assert "lauf.py" in args and "--log" in args
        assert exe.findtext("t:WorkingDirectory", namespaces=NS) == str(WROOT)
        assert root.find("t:Settings/t:MultipleInstancesPolicy", NS).text == "IgnoreNew"
        limit = root.findtext("t:Settings/t:ExecutionTimeLimit", namespaces=NS)
        assert (limit == "PT0S") == (j.art == "daemon")
        assert (root.find("t:Settings/t:RestartOnFailure", NS) is not None) == (j.art == "daemon")
        princ = root.find("t:Principals/t:Principal", NS)
        assert (princ.findtext("t:UserId", namespaces=NS) == "S-1-5-18") == system


def test_windows_aufgabe_pfade_mit_leerzeichen_werden_gequotet():
    j = next(j for j in JOBS if j.name == "zyklus")
    root = ET.fromstring(install.win_task_xml(j, WROOT, PY, "PC\\max", False, "2026-10-13T14:30:00").split("?>", 1)[1])
    args = root.findtext("t:Actions/t:Exec/t:Arguments", namespaces=NS)
    assert '"C:/Users/Max Muster/Landblick/tools/lauf.py"' in args.replace("\\", "/")


def test_windows_trigger_arten():
    def trig(name, system=False):
        j = next(j for j in JOBS if j.name == name)
        r = ET.fromstring(install.win_task_xml(j, WROOT, PY, "PC\\max", system, "2026-10-13T14:30:00").split("?>", 1)[1])
        return r.find("t:Triggers", NS)[0].tag.split("}")[1], r
    assert trig("zyklus")[0] == "TimeTrigger"
    assert trig("zyklus")[1].findtext("t:Triggers/t:TimeTrigger/t:Repetition/t:Interval", namespaces=NS) == "PT5M"
    assert trig("backup")[0] == "CalendarTrigger"
    assert "T03:15:00" in trig("backup")[1].findtext("t:Triggers/t:CalendarTrigger/t:StartBoundary", namespaces=NS)
    assert trig("web")[0] == "LogonTrigger" and trig("web", True)[0] == "BootTrigger"


def test_systemd_units():
    py = Path("/opt/lb/.venv/bin/python")
    z = install.systemd_dateien(next(j for j in JOBS if j.name == "zyklus"), Path("/opt/lb"), py, True, "lb")
    assert set(z) == {"landblick-zyklus.service", "landblick-zyklus.timer"}
    assert "Type=oneshot" in z["landblick-zyklus.service"] and "User=lb" in z["landblick-zyklus.service"]
    assert "OnUnitActiveSec=300s" in z["landblick-zyklus.timer"]
    b = install.systemd_dateien(next(j for j in JOBS if j.name == "backup"), Path("/opt/lb"), py, False, "lb")
    assert "OnCalendar=*-*-* 03:15:00" in b["landblick-backup.timer"] and "Persistent=true" in b["landblick-backup.timer"]
    assert "User=" not in b["landblick-backup.service"]
    w = install.systemd_dateien(next(j for j in JOBS if j.name == "web"), Path("/opt/lb"), py, False, "lb")
    assert list(w) == ["landblick-web.service"] and "Restart=always" in w["landblick-web.service"] and "default.target" in w["landblick-web.service"]


def test_launchd_plist():
    py = Path("/opt/lb/.venv/bin/python")
    d = plistlib.loads(install.launchd_plist(next(j for j in JOBS if j.name == "health"), Path("/opt/lb"), py))
    assert d["Label"] == "de.thorin.landblick-health" and d["StartInterval"] == 600
    assert d["ProgramArguments"][:2] == [str(py), "/opt/lb/tools/lauf.py"]
    b = plistlib.loads(install.launchd_plist(next(j for j in JOBS if j.name == "backup"), Path("/opt/lb"), py))
    assert b["StartCalendarInterval"] == {"Hour": 3, "Minute": 15}
    w = plistlib.loads(install.launchd_plist(next(j for j in JOBS if j.name == "web"), Path("/opt/lb"), py))
    assert w["KeepAlive"] is True


def test_env_setzen_und_lesen():
    t = "# Kommentar\nLANDBLICK_CONTACT=fremd@example.org   # alt\n# LANDBLICK_LIVE=1\nPUBLISH_ENABLED=0\n"
    t2 = install.env_setzen(t, "LANDBLICK_CONTACT", "ich@example.org")
    t2 = install.env_setzen(t2, "LANDBLICK_LIVE", "0")
    t2 = install.env_setzen(t2, "NEU", "x")
    assert install.env_lesen(t2, "LANDBLICK_CONTACT") == "ich@example.org"
    assert install.env_lesen(t2, "LANDBLICK_LIVE") == "0" and install.env_lesen(t2, "NEU") == "x"
    assert install.env_lesen(t2, "PUBLISH_ENABLED") == "0" and "# Kommentar" in t2
    assert t2.count("LANDBLICK_LIVE") == 1


def test_pmtiles_asset_namen_wie_im_sidecar_bau(monkeypatch):
    monkeypatch.setattr(install, "IS_WIN", True)
    assert install.pmtiles_asset() == "go-pmtiles_1.31.2_Windows_x86_64.zip"
    monkeypatch.setattr(install, "IS_WIN", False)
    monkeypatch.setattr(install, "IS_MAC", True)
    monkeypatch.setattr(install.platform, "machine", lambda: "arm64")
    assert install.pmtiles_asset() == "go-pmtiles-1.31.2_Darwin_arm64.zip"
    monkeypatch.setattr(install, "IS_MAC", False)
    monkeypatch.setattr(install.platform, "machine", lambda: "x86_64")
    assert install.pmtiles_asset() == "go-pmtiles_1.31.2_Linux_x86_64.tar.gz"


def test_kontakt_pflicht_ohne_tty(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "ROOT", tmp_path)
    (tmp_path / ".env.example").write_text("LANDBLICK_CONTACT=fremd@example.org\nPUBLISH_ENABLED=0\n")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(install.Fehler, match="kontakt"):
        install.schritt_env(None, True, False)
    install.schritt_env("ich@example.org", False, False)
    t = (tmp_path / ".env").read_text()
    assert install.env_lesen(t, "LANDBLICK_CONTACT") == "ich@example.org" and install.env_lesen(t, "LANDBLICK_LIVE") == "0"
    install.schritt_env(None, True, False)   # vorhandene .env behält den Kontakt
    assert install.env_lesen((tmp_path / ".env").read_text(), "LANDBLICK_CONTACT") == "ich@example.org"


# --- lauf.py ------------------------------------------------------------------------------------

def test_lauf_schreibt_log_mit_umlauten_und_code(tmp_path):
    log = tmp_path / "l" / "x.log"
    rc = lauf.run(["python", "-c", "import sys; print('Grüße'); sys.exit(3)"], log)
    text = log.read_text(encoding="utf-8")
    assert rc == 3 and "Grüße" in text and "[ende] Code 3" in text and "[start]" in text


def test_lauf_rotiert(tmp_path):
    log = tmp_path / "x.log"
    for _ in range(40):
        lauf.run(["python", "-c", "print('x' * 2000)"], log, max_mb=0.01, keep=2)
    assert len(list(tmp_path.glob("x.log*"))) <= 3


def test_lauf_zeitlimit_und_startfehler(tmp_path):
    rc = lauf.run(["python", "-c", "import time\nwhile True:\n    print('x', flush=True); time.sleep(0.05)"], tmp_path / "t.log", timeout=0.5)
    assert rc == 124
    assert lauf.run(["gibt-es-nicht-xyz"], tmp_path / "e.log") == 127


def test_lauf_cli_braucht_trenner():
    assert lauf.main(["--log", "x.log"]) == 2


# --- zyklus.py / Portabilität -----------------------------------------------------------------------

def test_sperre_atomar_und_verwaist(tmp_path):
    lock = tmp_path / "l.lock"
    assert zyklus.acquire(lock) is True
    assert zyklus.acquire(lock) is False
    assert zyklus.acquire(lock, now=time.time() + 31 * 60) is True   # verwaist nach 30 Minuten


def test_ro_uri_mit_leerzeichen_im_pfad(tmp_path):
    from app.db import Storage, ro_uri
    d = tmp_path / "mit Leerzeichen"
    d.mkdir()
    s = Storage(d / "t.sqlite")
    s.close()
    assert " " not in ro_uri(d / "t.sqlite")
    c = sqlite3.connect(ro_uri(d / "t.sqlite"), uri=True)
    assert c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
    st = Storage(d / "t.sqlite", readonly=True)
    assert st.ping()
    st.close()


def test_signal_fallback_wenn_loop_kein_add_signal_handler_kann():
    from app.collect import _on_signal

    class Loop:
        def add_signal_handler(self, *a):
            raise NotImplementedError

        def call_soon_threadsafe(self, fn):
            fn()

    stop = asyncio.Event()
    alt = signal.getsignal(signal.SIGTERM)
    try:
        _on_signal(Loop(), signal.SIGTERM, stop)
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        assert stop.is_set()
    finally:
        signal.signal(signal.SIGTERM, alt)


def test_backup_verify_after(settings, storage, tmp_path):
    import backup
    out = tmp_path / "bk"
    old = sys.argv
    sys.argv = ["backup", "--db", str(settings.db_path), "--dir", str(out), "--keep", "3", "--verify-after"]
    try:
        assert backup.main() == 0
    finally:
        sys.argv = old
    assert len(list(out.glob("landblick-*.sqlite.json"))) == 1


# --- Aufräumen der Rohdaten am Ende --------------------------------------------------------------------------------------
def _aufraeum_umgebung(tmp_path, monkeypatch, rcs, antwort):
    monkeypatch.setattr(install, "ROOT", tmp_path)
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "rohdaten_aufraeumen.py").write_text("")
    (tmp_path / "_scratch" / "dgm1").mkdir(parents=True)
    aufrufe = []

    def fake_run(cmd, dry=False, check=True, cwd=None, quiet=False):
        aufrufe.append(cmd)
        return rcs.pop(0)

    monkeypatch.setattr(install, "run", fake_run)
    monkeypatch.setattr(install, "frage", lambda text, ja: antwort if not ja else True)
    return aufrufe


def test_aufraeumen_ohne_arbeitsordner_tut_nichts(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "ROOT", tmp_path)
    monkeypatch.setattr(install, "run", lambda *a, **k: pytest.fail("darf nichts starten"))
    install.schritt_aufraeumen(Path("py"), "127.0.0.1", 8080, False, False)


def test_aufraeumen_loescht_nur_nach_bestandener_pruefung_und_ja(tmp_path, monkeypatch):
    aufrufe = _aufraeum_umgebung(tmp_path, monkeypatch, [0, 0], True)
    install.schritt_aufraeumen(Path("py"), "0.0.0.0", 9090, False, False)
    assert len(aufrufe) == 2 and "--ja" not in aufrufe[0] and aufrufe[1][-1] == "--ja"
    assert "http://127.0.0.1:9090/" in aufrufe[0]


def test_aufraeumen_antwort_nein_laesst_alles_liegen(tmp_path, monkeypatch):
    aufrufe = _aufraeum_umgebung(tmp_path, monkeypatch, [0], False)
    install.schritt_aufraeumen(Path("py"), "127.0.0.1", 8080, False, False)
    assert len(aufrufe) == 1 and "--ja" not in aufrufe[0]


@pytest.mark.parametrize("rc", [1, 2])
def test_aufraeumen_pruefung_gescheitert_fragt_nicht_und_loescht_nicht(tmp_path, monkeypatch, rc):
    aufrufe = _aufraeum_umgebung(tmp_path, monkeypatch, [rc], True)
    install.schritt_aufraeumen(Path("py"), "127.0.0.1", 8080, True, False)
    assert len(aufrufe) == 1 and "--ja" not in aufrufe[0]
