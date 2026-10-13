#!/usr/bin/env python3
"""Installer: Landblick - RLP auf einem Rechner einrichten, der durchläuft (Windows, Linux, macOS).

Zweck:      Richtet die Sammelstelle am Ort dieses Ordners ein: Python-Umgebung (.venv), .env, erste Datensammlung aus den
            Quellen (sources.yaml), Export, lokaler Webserver und Zeitplan für den Dauerbetrieb inklusive der R6-Jobs
            (Sicherung mit Rückspieltest, Gesundheitsprüfung, auf Wunsch Dauerlauf-Proben). Alles läuft lokal; nach außen
            gehen nur die Abrufe laut Quellenregister und, wenn gewünscht, der Kartenabruf bei Protomaps.
Aufruf:     Windows:      powershell -ExecutionPolicy Bypass -File install.ps1 -Kontakt name@example.org
            Linux/macOS:  ./install.sh --kontakt name@example.org
            oder direkt:  python install.py --kontakt name@example.org
Parameter:  --kontakt MAIL      Absender im User-Agent der Abrufe (Pflicht beim ersten Lauf; Quellen sollen uns erreichen können)
            --bind ADR          Adresse des Webservers (Standard 127.0.0.1; 0.0.0.0 macht ihn im Netz erreichbar, dann Firewall bedenken)
            --port N            Port des Webservers (Standard 8080)
            --karte keine|voll  voll: Basiskarte für die ganze Fläche holen (rund 1,5 GB, einmalig, wiederaufnehmbar). Standard keine
            --ohne-erstlauf     keine erste Datensammlung jetzt (kommt mit dem ersten Zeitplanlauf)
            --ohne-live         keine Livemodul-Schleife (Luftverkehr); die Quellen laufen dann im normalen Zyklus
            --dauerlauf         alle 10 Minuten eine Probe für das R6-Dauerlauf-Protokoll (tools/dauerlauf.py)
            --system            Dienste für den ganzen Rechner statt für den angemeldeten Benutzer (läuft ohne Anmeldung;
                                Windows: als Administrator starten, Linux: mit sudo)
            --ruhezustand-aus   Windows: Energiesparen (Standby) im Netzbetrieb abschalten. Sonst steht der Zyklus, wenn der Rechner schläft
            --ohne-dienste      nur einrichten, nichts im Zeitplaner anlegen
            --ja                Rückfragen (Download) mit Ja beantworten (löscht nie Rohdaten, dafür gibt es --rohdaten-loeschen)
            --rohdaten-loeschen Am Ende die Rohdaten der Kartenwerkzeuge (_scratch/dgm1) ohne Rückfrage löschen, aber nur, wenn
                                tools/rohdaten_aufraeumen.py alle Prüfungen besteht. Ohne die Option fragt der Installer im Terminal nach
            --status            Zustand der Jobs und Gesundheitsprüfung anzeigen
            --deinstall         Jobs entfernen (Daten, .env und .venv bleiben)
            --dry-run           nur anzeigen, was getan würde
Dateien:    data/osint.sqlite (Datenbank), data/backup/, data/logs/*.log (rotierend), web/data/ (Export), web/tiles/ (Karte), .env
Beispiel:   python install.py --kontakt kontakt@example.org --dauerlauf --ruhezustand-aus
Exit:       0 = fertig, 1 = Fehler (die Meldung nennt den Schritt)
"""
from __future__ import annotations

import argparse
import getpass
import os
import platform
import plistlib
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
MIN_PY = (3, 11)
PMTILES_VERSION = "1.31.2"
TASK_FOLDER = "Landblick"
LABEL = "de.ctw.landblick"


class Fehler(RuntimeError):
    """Schritt fehlgeschlagen; die Meldung geht an den Benutzer."""


# --- Jobs ---------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Job:
    name: str
    args: tuple[str, ...]            # Befehl nach "python" (Skript oder -m Modul)
    art: str                         # periodic | daily | daemon
    alle_s: int = 0                  # periodic: Abstand in Sekunden
    um: str = "03:15"                # daily: Uhrzeit HH:MM (Ortszeit)
    limit_min: int = 0               # 0 = ohne Zeitlimit
    text: str = ""
    extra: dict = field(default_factory=dict, hash=False, compare=False)


def job_liste(bind: str, port: int, live: bool, dauerlauf: bool) -> list[Job]:
    jobs = [
        Job("zyklus", ("tools/zyklus.py",), "periodic", 300, limit_min=45, text="Sammelzyklus: fällige Quellen abrufen, exportieren"),
        Job("spaet", ("tools/zyklus.py", "--spaet"), "periodic", 1800, limit_min=180, text="Langsame Quellen (große Abfragen)"),
        Job("backup", ("tools/backup.py", "--keep", "14", "--verify-after"), "daily", um="03:15", limit_min=60,
            text="Datenbank sichern und Wiederherstellung prüfen"),
        Job("health", ("tools/gesundheit.py",), "periodic", 600, limit_min=5, text="Gesundheitsprüfung (Quellen, Regionen, Export)"),
        Job("web", ("deploy/serve-local.py", "--dir", "web", "--port", str(port), "--bind", bind), "daemon", text="Lokaler Webserver"),
    ]
    if live:
        jobs.append(Job("live", ("-m", "app.live"), "daemon", text="Livemodul (Luftverkehr in kurzem Takt)"))
    if dauerlauf:
        jobs.append(Job("dauerlauf", ("tools/dauerlauf.py", "sample"), "periodic", 600, limit_min=5, text="Probe für das Dauerlauf-Protokoll (R6)"))
    return jobs


def venv_python(root: Path = ROOT, windowed: bool = False) -> Path:
    if IS_WIN:
        return root / ".venv" / "Scripts" / ("pythonw.exe" if windowed else "python.exe")
    return root / ".venv" / "bin" / "python"


def job_befehl(job: Job, root: Path, py: Path) -> list[str]:
    """Befehl für den Zeitplaner: lauf.py schreibt die Ausgabe in data/logs/<name>.log und rotiert sie."""
    return [str(py), str(root / "tools" / "lauf.py"), "--log", str(root / "data" / "logs" / f"{job.name}.log"),
            *(["--timeout", str(job.limit_min * 60)] if job.limit_min else []), "--",
            "python", *[str(root / a) if a.endswith(".py") else a for a in job.args]]


def iso_dauer(minuten: int) -> str:
    return "PT0S" if minuten <= 0 else f"PT{minuten}M"


# --- Windows: Aufgabenplanung -------------------------------------------------------------------------------------------

def win_task_xml(job: Job, root: Path, py: Path, benutzer: str, system: bool, start: str) -> str:
    """Aufgabendefinition (XML für schtasks /Create /XML). start: ISO-Zeit ohne Zone, z. B. 2026-10-13T14:30:00."""
    befehl = job_befehl(job, root, py)
    arg = " ".join(f'"{a}"' if " " in a or not a else a for a in befehl[1:])
    if job.art == "periodic":
        trig = (f"<TimeTrigger><Repetition><Interval>PT{job.alle_s // 60}M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>"
                f"<StartBoundary>{start}</StartBoundary><Enabled>true</Enabled></TimeTrigger>")
    elif job.art == "daily":
        trig = (f"<CalendarTrigger><StartBoundary>{start[:10]}T{job.um}:00</StartBoundary><Enabled>true</Enabled>"
                "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger>")
    else:
        trig = "<BootTrigger><Enabled>true</Enabled></BootTrigger>" if system else (
            f"<LogonTrigger><Enabled>true</Enabled><UserId>{escape(benutzer)}</UserId></LogonTrigger>")
    if system:
        princ = "<Principal id=\"Author\"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal>"
    else:
        princ = (f"<Principal id=\"Author\"><UserId>{escape(benutzer)}</UserId><LogonType>InteractiveToken</LogonType>"
                 "<RunLevel>LeastPrivilege</RunLevel></Principal>")
    neustart = "<RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>" if job.art == "daemon" else ""
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
        f"<RegistrationInfo><Description>{escape('Landblick - RLP: ' + job.text)}</Description></RegistrationInfo>"
        f"<Triggers>{trig}</Triggers><Principals>{princ}</Principals>"
        "<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>"
        "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"
        "<AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable>"
        "<RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable><AllowStartOnDemand>true</AllowStartOnDemand>"
        f"<Enabled>true</Enabled><Hidden>true</Hidden><ExecutionTimeLimit>{iso_dauer(0 if job.art == 'daemon' else job.limit_min + 5)}</ExecutionTimeLimit>"
        f"<Priority>7</Priority>{neustart}</Settings>"
        f'<Actions Context="Author"><Exec><Command>{escape(befehl[0])}</Command><Arguments>{escape(arg)}</Arguments>'
        f"<WorkingDirectory>{escape(str(root))}</WorkingDirectory></Exec></Actions></Task>"
    )


# --- Linux: systemd -----------------------------------------------------------------------------------------------------

def systemd_dateien(job: Job, root: Path, py: Path, system: bool, benutzer: str) -> dict[str, str]:
    name = f"landblick-{job.name}"
    befehl = " ".join(f'"{a}"' if " " in a else a for a in job_befehl(job, root, py))
    ziel = "multi-user.target" if system else "default.target"
    svc = ["[Unit]", f"Description=Landblick RLP: {job.text}", "After=network-online.target", "Wants=network-online.target", "",
           "[Service]", f"WorkingDirectory={root}", f"ExecStart={befehl}", "Nice=10"]
    if system:
        svc.append(f"User={benutzer}")
    if job.art == "daemon":
        svc += ["Restart=always", "RestartSec=10", "", "[Install]", f"WantedBy={ziel}"]
        return {f"{name}.service": "\n".join(svc) + "\n"}
    svc.insert(svc.index("[Service]") + 1, "Type=oneshot")
    svc.append(f"TimeoutStartSec={(job.limit_min + 5) * 60}")
    timer = ["[Unit]", f"Description=Landblick RLP: {job.text} (Zeitplan)", "", "[Timer]"]
    if job.art == "periodic":
        timer += ["OnBootSec=2min", f"OnUnitActiveSec={job.alle_s}s", "AccuracySec=15s"]
    else:
        timer += [f"OnCalendar=*-*-* {job.um}:00", "RandomizedDelaySec=5min", "Persistent=true"]
    timer += ["", "[Install]", "WantedBy=timers.target"]
    return {f"{name}.service": "\n".join(svc) + "\n", f"{name}.timer": "\n".join(timer) + "\n"}


# --- macOS: launchd -----------------------------------------------------------------------------------------------------

def launchd_plist(job: Job, root: Path, py: Path) -> bytes:
    d: dict = {"Label": f"{LABEL}-{job.name}", "ProgramArguments": job_befehl(job, root, py), "WorkingDirectory": str(root),
               "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"}}
    if job.art == "periodic":
        d["StartInterval"] = job.alle_s
    elif job.art == "daily":
        h, m = job.um.split(":")
        d["StartCalendarInterval"] = {"Hour": int(h), "Minute": int(m)}
    else:
        d.update(KeepAlive=True, RunAtLoad=True)
    return plistlib.dumps(d)


# --- Ausführung ---------------------------------------------------------------------------------------------------------

def ausgabe(text: str) -> None:
    print(text, flush=True)


def run(cmd: list[str], dry: bool = False, check: bool = True, cwd: Path | None = None, quiet: bool = False) -> int:
    ausgabe("  $ " + " ".join(cmd))
    if dry:
        return 0
    res = subprocess.run(cmd, cwd=cwd, stdout=subprocess.DEVNULL if quiet else None, stderr=subprocess.STDOUT if quiet else None)
    if check and res.returncode != 0:
        raise Fehler(f"Befehl fehlgeschlagen (Code {res.returncode}): {' '.join(cmd)}")
    return res.returncode


def frage(text: str, ja: bool) -> bool:
    if ja:
        return True
    if not sys.stdin.isatty():
        return False
    return input(f"{text} [j/N] ").strip().lower() in ("j", "ja", "y", "yes")


def pruefe_python() -> None:
    if sys.version_info < MIN_PY:
        raise Fehler(f"Python {MIN_PY[0]}.{MIN_PY[1]} oder neuer nötig, gefunden {platform.python_version()}")


def schritt_venv(dry: bool) -> Path:
    py = venv_python()
    if not py.exists():
        ausgabe("Python-Umgebung anlegen (.venv)")
        try:
            run([sys.executable, "-m", "venv", str(ROOT / ".venv")], dry)
        except Fehler as exc:
            raise Fehler(f"{exc}\n(Debian/Ubuntu: sudo apt install python3-venv)") from exc
    ausgabe("Abhängigkeiten installieren (requirements.txt, gepinnt)")
    run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(ROOT / "requirements.txt")], dry)
    return py


def env_setzen(text: str, schluessel: str, wert: str) -> str:
    """Setzt SCHLUESSEL=wert in einem .env-Text (ersetzt auch eine auskommentierte Zeile), lässt alles andere stehen."""
    zeilen, gesetzt = text.splitlines(), False
    for i, z in enumerate(zeilen):
        k = z.lstrip("# ").split("=", 1)[0].strip()
        if k == schluessel and "=" in z:
            zeilen[i], gesetzt = f"{schluessel}={wert}", True
            break
    if not gesetzt:
        zeilen.append(f"{schluessel}={wert}")
    return "\n".join(zeilen) + "\n"


def env_lesen(text: str, schluessel: str) -> str:
    for z in text.splitlines():
        if not z.lstrip().startswith("#") and z.partition("=")[0].strip() == schluessel:
            return z.partition("=")[2].split("#")[0].strip()
    return ""


def schritt_env(kontakt: str | None, live: bool, dry: bool) -> None:
    env = ROOT / ".env"
    text = env.read_text(encoding="utf-8") if env.exists() else (ROOT / ".env.example").read_text(encoding="utf-8")
    if kontakt:
        text = env_setzen(text, "OSINT_CONTACT", kontakt)
    elif not env.exists():   # die Vorlage trägt eine fremde Adresse: nie übernehmen
        if not sys.stdin.isatty():
            raise Fehler("--kontakt MAIL fehlt (steht im User-Agent der Abrufe, Quellen sollen uns erreichen können)")
        text = env_setzen(text, "OSINT_CONTACT", input("Kontakt-Mail für den User-Agent: ").strip())
    text = env_setzen(text, "OSINT_LIVE", "1" if live else "0")
    text = env_setzen(text, "PUBLISH_ENABLED", env_lesen(text, "PUBLISH_ENABLED") or "0")
    ausgabe(f"Konfiguration schreiben: {env.name}")
    if dry:
        return
    env.write_text(text, encoding="utf-8")
    if IS_WIN:
        subprocess.run(["icacls", str(env), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F", "SYSTEM:F"], capture_output=True)
    else:
        env.chmod(stat.S_IRUSR | stat.S_IWUSR)
    for d in ("data/logs", "data/backup", "web/data", "web/tiles"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)


def pmtiles_asset() -> str:
    m = platform.machine().lower()
    arm = m in ("arm64", "aarch64")
    v = PMTILES_VERSION
    if IS_WIN:
        return f"go-pmtiles_{v}_Windows_x86_64.zip"
    if IS_MAC:
        return f"go-pmtiles-{v}_Darwin_{'arm64' if arm else 'x86_64'}.zip"
    return f"go-pmtiles_{v}_Linux_{'arm64' if arm else 'x86_64'}.tar.gz"


def schritt_karte(py: Path, ja: bool, dry: bool) -> None:
    exe = ROOT / "tools" / "bin" / ("pmtiles.exe" if IS_WIN else "pmtiles")
    asset = pmtiles_asset()
    url = f"https://github.com/protomaps/go-pmtiles/releases/download/v{PMTILES_VERSION}/{asset}"
    ausgabe("Basiskarte: Abruf bei build.protomaps.com (OSM, ODbL), rund 1,5 GB, einmalig und wiederaufnehmbar.")
    if not exe.exists():
        ausgabe(f"Dafür wird die pmtiles-CLI geladen: {url}")
        if not frage("Herunterladen?", ja):
            raise Fehler("Download der pmtiles-CLI nicht bestätigt (--ja oder Datei nach tools/bin/ legen)")
        if not dry:
            exe.parent.mkdir(parents=True, exist_ok=True)
            pkg = exe.parent / asset
            urllib.request.urlretrieve(url, pkg)  # noqa: S310 (feste https-URL der Veröffentlichung)
            shutil.unpack_archive(str(pkg), str(exe.parent / "_pm"))
            gefunden = next((exe.parent / "_pm").rglob(exe.name))
            shutil.move(str(gefunden), str(exe))
            shutil.rmtree(exe.parent / "_pm", ignore_errors=True)
            pkg.unlink(missing_ok=True)
            exe.chmod(0o755)
    elif not frage("Karte jetzt laden (dauert, läuft in Stücken weiter, wenn unterbrochen)?", ja):
        return
    tvenv = ROOT / ".venv-tools"
    tpy = tvenv / ("Scripts/python.exe" if IS_WIN else "bin/python")
    if not tpy.exists():
        ausgabe("Eigene Umgebung für den Kartenbau (.venv-tools, requirements-tools.txt)")
        run([sys.executable, "-m", "venv", str(tvenv)], dry)
        run([str(tpy), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", str(ROOT / "requirements-tools.txt")], dry)
    args = [str(tpy), str(ROOT / "tools" / "build_region_tiles.py"), "--pmtiles", str(exe), "--work", str(ROOT / "tiles-work"),
            "--out", str(ROOT / "web" / "tiles"), "--region", str(ROOT / "region.yaml"), "--budget-s", "600"]
    for versuch in range(1, 61):
        ausgabe(f"Kartenabruf, Lauf {versuch}")
        rc = run(args, dry, check=False)
        if rc == 0:
            return
        if rc != 2:
            raise Fehler(f"Kartenabruf fehlgeschlagen (Code {rc}); erneut starten macht dort weiter")
        if dry:
            return
    raise Fehler("Karte nach 60 Läufen nicht vollständig; erneut starten macht dort weiter")


def schritt_aufraeumen(py: Path, bind: str, port: int, loeschen: bool, dry: bool) -> None:
    """Rohdaten der Kartenwerkzeuge anbieten zu löschen, erst nach bestandener Prüfung und nur mit Zustimmung.

    Ohne Arbeitsordner passiert nichts. Der Probelauf von tools/rohdaten_aufraeumen.py prüft Relief, Felswände,
    Basiskarte und die laufende App; erst wenn er mit 0 endet, kommt die Rückfrage. Ohne Terminal und ohne
    --rohdaten-loeschen bleibt alles liegen und der Installer nennt den Befehl.
    """
    work = ROOT / "_scratch" / "dgm1"
    tool = ROOT / "tools" / "rohdaten_aufraeumen.py"
    if not work.exists() or not tool.exists():
        return
    host = "127.0.0.1" if bind in ("0.0.0.0", "::") else bind
    args = [str(py), str(tool), "--work", str(work), "--web", str(ROOT / "web"), "--url", f"http://{host}:{port}/"]
    ausgabe("Rohdaten der Kartenwerkzeuge gefunden. Prüfe, ob sie gelöscht werden können (Relief, Felswände, Basiskarte, App).")
    if dry:
        run(args, dry)
        return
    rc = run(args, check=False, cwd=ROOT)
    if rc != 0:
        ausgabe("Rohdaten bleiben liegen (Grund oben). Später: python tools/rohdaten_aufraeumen.py --ja")
        return
    if frage("Rohdaten jetzt löschen? Sie werden für den Betrieb nicht gebraucht, nur zum Neubau der Karten.", loeschen):
        run(args + ["--ja"], check=False, cwd=ROOT)
    else:
        ausgabe("Rohdaten bleiben liegen. Löschen später: python tools/rohdaten_aufraeumen.py --ja")


def schritt_erstlauf(py: Path, dry: bool) -> None:
    ausgabe("Erste Datensammlung und Export (jede Quelle einmal, die langsamen kommen mit dem Zeitplan)")
    run([str(py), str(ROOT / "tools" / "zyklus.py"), "--erst"], dry, check=False, cwd=ROOT)


# --- Zeitplaner ---------------------------------------------------------------------------------------------------------

def schtasks_name(job: Job) -> str:
    return f"{TASK_FOLDER}\\{job.name}"


def dienste_windows(jobs: list[Job], system: bool, dry: bool) -> None:
    py = venv_python(ROOT, windowed=True)
    benutzer = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}".lstrip("\\")
    start = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = ROOT / "data" / "tasks"
    tmp.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        xml = tmp / f"{j.name}.xml"
        xml.write_text(win_task_xml(j, ROOT, py, benutzer, system, start), encoding="utf-16")
        run(["schtasks", "/Create", "/TN", schtasks_name(j), "/XML", str(xml), "/F"], dry, quiet=True)
        if j.art == "daemon":
            run(["schtasks", "/Run", "/TN", schtasks_name(j)], dry, check=False, quiet=True)


def dienste_systemd(jobs: list[Job], system: bool, dry: bool) -> None:
    py = venv_python()
    benutzer = os.environ.get("SUDO_USER") or getpass.getuser()
    zielordner = Path("/etc/systemd/system") if system else Path.home() / ".config" / "systemd" / "user"
    ctl = ["systemctl"] + ([] if system else ["--user"])
    ausgabe(f"systemd-Units nach {zielordner}")
    if not dry:
        zielordner.mkdir(parents=True, exist_ok=True)
    aktivieren = []
    for j in jobs:
        for fname, text in systemd_dateien(j, ROOT, py, system, benutzer).items():
            if not dry:
                (zielordner / fname).write_text(text, encoding="utf-8")
        aktivieren.append(f"landblick-{j.name}.service" if j.art == "daemon" else f"landblick-{j.name}.timer")
    run(ctl + ["daemon-reload"], dry)
    for einheit in aktivieren:
        run(ctl + ["enable", "--now", einheit], dry)
    if not system:
        run(["loginctl", "enable-linger", getpass.getuser()], dry, check=False)
        ausgabe("Hinweis: ohne 'enable-linger' (braucht ggf. sudo) stoppen die Benutzerdienste beim Abmelden.")


def dienste_launchd(jobs: list[Job], dry: bool) -> None:
    py = venv_python()
    ordner = Path.home() / "Library" / "LaunchAgents"
    domain = f"gui/{os.getuid()}"
    if not dry:
        ordner.mkdir(parents=True, exist_ok=True)
    for j in jobs:
        datei = ordner / f"{LABEL}-{j.name}.plist"
        if not dry:
            datei.write_bytes(launchd_plist(j, ROOT, py))
        run(["launchctl", "bootout", f"{domain}/{LABEL}-{j.name}"], dry, check=False, quiet=True)
        run(["launchctl", "bootstrap", domain, str(datei)], dry)
    ausgabe("Hinweis macOS: LaunchAgents laufen nur bei angemeldetem Benutzer; Ruhezustand: 'sudo pmset -a sleep 0'.")


def dienste_installieren(jobs: list[Job], system: bool, dry: bool) -> None:
    if IS_WIN:
        dienste_windows(jobs, system, dry)
    elif IS_MAC:
        dienste_launchd(jobs, dry)
    else:
        dienste_systemd(jobs, system, dry)


def dienste_entfernen(system: bool, dry: bool) -> None:
    jobs = job_liste("127.0.0.1", 8080, True, True)
    if IS_WIN:
        for j in jobs:
            run(["schtasks", "/End", "/TN", schtasks_name(j)], dry, check=False, quiet=True)
            run(["schtasks", "/Delete", "/TN", schtasks_name(j), "/F"], dry, check=False, quiet=True)
    elif IS_MAC:
        for j in jobs:
            run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}-{j.name}"], dry, check=False, quiet=True)
            (Path.home() / "Library" / "LaunchAgents" / f"{LABEL}-{j.name}.plist").unlink(missing_ok=True)
    else:
        ordner = Path("/etc/systemd/system") if system else Path.home() / ".config" / "systemd" / "user"
        ctl = ["systemctl"] + ([] if system else ["--user"])
        for j in jobs:
            for suffix in ("timer", "service"):
                f = ordner / f"landblick-{j.name}.{suffix}"
                if f.exists():
                    run(ctl + ["disable", "--now", f.name], dry, check=False, quiet=True)
                    if not dry:
                        f.unlink()
        run(ctl + ["daemon-reload"], dry, check=False)


def ruhezustand_aus(dry: bool) -> None:
    if IS_WIN:
        ausgabe("Energiesparen im Netzbetrieb abschalten (Standby und Ruhezustand)")
        run(["powercfg", "/change", "standby-timeout-ac", "0"], dry, check=False)
        run(["powercfg", "/change", "hibernate-timeout-ac", "0"], dry, check=False)
    else:
        ausgabe("Ruhezustand: unter Linux 'systemctl mask sleep.target suspend.target', unter macOS 'sudo pmset -a sleep 0' (nicht automatisch)")


def status(py: Path) -> int:
    if IS_WIN:
        run(["schtasks", "/Query", "/TN", f"{TASK_FOLDER}\\", "/FO", "TABLE"], check=False)
    elif IS_MAC:
        run(["bash", "-c", f"launchctl list | grep {LABEL} || true"], check=False)
    else:
        run(["bash", "-c", "systemctl list-timers 'landblick-*' --no-pager; systemctl --user list-timers 'landblick-*' --no-pager 2>/dev/null; true"], check=False)
    return run([str(py), str(ROOT / "tools" / "gesundheit.py")], check=False, cwd=ROOT)


def pruefe_web(bind: str, port: int, warte_s: int = 30) -> bool:
    host = "127.0.0.1" if bind in ("0.0.0.0", "::") else bind
    ende = time.time() + warte_s
    while time.time() < ende:
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/index.html", timeout=3) as r:  # noqa: S310
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(2)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kontakt")
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--karte", choices=["keine", "voll"], default="keine")
    ap.add_argument("--ohne-erstlauf", action="store_true")
    ap.add_argument("--ohne-live", action="store_true")
    ap.add_argument("--dauerlauf", action="store_true")
    ap.add_argument("--system", action="store_true")
    ap.add_argument("--ruhezustand-aus", action="store_true")
    ap.add_argument("--ohne-dienste", action="store_true")
    ap.add_argument("--ja", action="store_true")
    ap.add_argument("--rohdaten-loeschen", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--deinstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        pruefe_python()
        if a.deinstall:
            dienste_entfernen(a.system, a.dry_run)
            ausgabe("Jobs entfernt. Daten (data/, web/data, web/tiles), .env und .venv bleiben.")
            return 0
        if a.status:
            return status(venv_python() if venv_python().exists() else Path(sys.executable))
        if a.bind not in ("127.0.0.1", "localhost", "::1"):
            ausgabe(f"Achtung: der Webserver lauscht auf {a.bind} und ist im Netz erreichbar. Er hat keine Anmeldung; Firewall prüfen.")
        py = schritt_venv(a.dry_run)
        schritt_env(a.kontakt, not a.ohne_live, a.dry_run)
        if a.karte == "voll":
            schritt_karte(py, a.ja, a.dry_run)
        if not a.ohne_erstlauf:
            schritt_erstlauf(py, a.dry_run)
        if a.ruhezustand_aus:
            ruhezustand_aus(a.dry_run)
        if not a.ohne_dienste:
            dienste_installieren(job_liste(a.bind, a.port, not a.ohne_live, a.dauerlauf), a.system, a.dry_run)
            if not a.dry_run and pruefe_web(a.bind, a.port):
                ausgabe(f"Fertig. Oberfläche: http://{'127.0.0.1' if a.bind == '0.0.0.0' else a.bind}:{a.port}/")
            elif not a.dry_run:
                ausgabe("Webserver antwortet noch nicht; python install.py --status zeigt den Zustand, data/logs/web.log den Grund.")
        else:
            ausgabe("Fertig (ohne Dienste). Start von Hand: python deploy/serve-local.py --dir web")
        if not a.ohne_dienste and not a.dry_run and pruefe_web(a.bind, a.port, warte_s=5):
            schritt_aufraeumen(py, a.bind, a.port, a.rohdaten_loeschen, a.dry_run)
        ausgabe("Gesundheit prüfen: python tools/gesundheit.py · Betrieb: docs/betrieb.md, Abschnitt Installation auf einem Dauerläufer")
        return 0
    except Fehler as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
