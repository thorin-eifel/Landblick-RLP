# 2 Schnellstart: drei Wege zum laufenden System

Alle drei Wege führen zum selben Ergebnis: eine Sammelstelle ruft die Quellen ab, schreibt JSON-Dateien, und ein Webserver zeigt die Seite. Sie unterscheiden sich darin, wie dauerhaft und wie bequem das geschieht.

| Weg | Wann | Aufwand |
|---|---|---|
| **A. Installer für einen Dauerläufer** | Ein Rechner soll 24 Stunden am Tag sammeln und die Seite im lokalen Netz anbieten (Windows, Linux, macOS). | Ein Befehl, Aufgaben im Zeitplaner |
| **B. Desktop-App** | Ein einzelner Arbeitsplatz, mit Fenster, ohne Server. Sammeln, solange die App läuft. | Windows-Installer; Karte lädt beim ersten Start |
| **C. Von Hand aus dem Quelltext** | Ausprobieren, entwickeln, testen. | Fünf Befehle |

Voraussetzung für A und C ist Python 3.11 oder neuer (getestet mit 3.11; unter Windows ist 3.12 die sichere Wahl) und der Quelltext dieses Releases.

## 2.1 Weg A: Installer für einen Dauerläufer

Quelltext entpacken (Release-Datei `landblick-1.0.0-alpha.1-quelltext.zip` oder `.tar.gz`), in den Ordner wechseln und den Installer starten.

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -Kontakt name@example.org -Dauerlauf -RuhezustandAus
```

**Linux und macOS:**

```bash
./install.sh --kontakt name@example.org --dauerlauf
```

Die Kontakt-Adresse ist Pflicht: Sie steht im User-Agent aller Abrufe, damit die Betreiber der Quellen uns erreichen können. Der Installer legt dann der Reihe nach an:

1. eine Python-Umgebung `.venv` mit den gepinnten Paketen aus `requirements.txt`,
2. die Konfiguration `.env` (Rechte nur für den Benutzer),
3. die erste Datensammlung und den ersten Export (jede Quelle einmal; das dauert je nach Netz einige Minuten),
4. Jobs im Zeitplaner (Windows-Aufgabenplanung, systemd oder launchd): Sammelzyklus, langsame Quellen, Sicherung, Gesundheitsprüfung, lokaler Webserver, Luftverkehr, auf Wunsch Dauerlauf-Proben,
5. einen Test, ob der Webserver antwortet.

Danach ist die Seite unter `http://127.0.0.1:8080/` erreichbar. Mit `--bind 0.0.0.0` erreicht man sie im lokalen Netz; der Server hat keine Anmeldung, also nie ohne Firewall ins Internet stellen.

Die **Basiskarte** (rund 1,5 GB von build.protomaps.com) lädt der Installer nur auf ausdrücklichen Wunsch: `--karte voll` (Windows: `-Karte voll`). Er fragt vorher, bevor er die pmtiles-Programmdatei herunterlädt. Ohne Karte bleibt der Hintergrund leer und der Kartenhinweis sagt „Basiskarte nicht verfügbar“; Warnband, Tabellen, Status und Quellenseite arbeiten trotzdem.

Nützliche Schalter, vollständig mit `python install.py --help`:

| Schalter | Wirkung |
|---|---|
| `--status` / `-Status` | Zustand der Jobs und Gesundheitsprüfung |
| `--deinstall` / `-Deinstall` | Jobs entfernen (Daten, `.env`, `.venv` bleiben) |
| `--dry-run` / `-DryRun` | nur anzeigen, was getan würde |
| `--system` / `-System` | Dienste für den ganzen Rechner, laufen ohne Anmeldung (Administrator bzw. `sudo`) |
| `--ruhezustand-aus` / `-RuhezustandAus` | Windows: Standby im Netzbetrieb abschalten |
| `--ohne-live` / `-OhneLive` | kein Luftverkehr-Livemodul |
| `--ohne-erstlauf` / `-OhneErstlauf` | keine erste Datensammlung jetzt |

Einzelheiten, Prüfliste für den ersten Windows-Test und Grenzen stehen in Kapitel 6.

## 2.2 Weg B: Desktop-App

Die Desktop-App (Tauri, mit dem System-WebView, WebGL auf der Grafikkarte) bringt alles in einem Fenster mit: einen lokalen Dienst auf `127.0.0.1`, den Sammelzyklus und die Oberfläche. Beim ersten Start zeigt eine Einrichtungsseite den Fortschritt, lädt die Karte für das ganze Gebiet (rund 1,5 GB, einmalig und wiederaufnehmbar) und beginnt zu sammeln.

Der Windows-Installer (`Landblick - RLP_<Version>_x64-setup.exe`) wird mit dem GitHub-Workflow **windows-installer** gebaut (Kapitel 6.10). Er installiert pro Benutzer, ohne Administratorrechte. Er ist nicht signiert: Windows SmartScreen meldet „Der Computer wurde durch Windows geschützt“; unter „Weitere Informationen“ lässt er sich trotzdem ausführen. Daten und Zugangsdaten liegen unter `%APPDATA%\de.thorin.landblick`.

In der Desktop-App erscheinen in der Quellenübersicht Eingabefelder für Zugangsdaten (Tankerkönig-Schlüssel, NASA-FIRMS-Schlüssel). Auf dem Dauerläufer (Weg A) trägt man sie in `.env` ein.

## 2.3 Weg C: von Hand aus dem Quelltext

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q && node --test tests/js/*.test.mjs     # Tests

cp .env.example .env && chmod 600 .env                     # LANDBLICK_CONTACT auf die eigene Adresse setzen
python -m app.collect --once                               # alle Quellen einmal abrufen
python -m app.export                                       # schreibt web/data/*.json
python deploy/serve-local.py --dir web --port 8080         # http://127.0.0.1:8080
```

Der kleine Server `deploy/serve-local.py` versteht HTTP-Teilabrufe (Range), die die Kartendatei braucht; `python -m http.server` kann das nicht.

## 2.4 Erste Sichtprüfung

Nach jedem Weg hilft diese Reihenfolge:

1. Die Seite öffnen. Oben links steht „Lagekarte“ mit einer Statuszeile; die Karte zeigt Rheinland-Pfalz.
2. Auf **Status** klicken. Jede Quelle hat eine Zeile mit Zustand, letztem Erfolg und Fehlertext. Ein paar Quellen stehen ohne Schlüssel auf „nicht erreichbar“ (Tankerkönig, NASA FIRMS); das ist erwartet.
3. Auf der Kommandozeile `python tools/gesundheit.py` laufen lassen. Es nennt Quellen, Regionen und das Alter des Exports.
4. Nach zehn Minuten `data/logs/zyklus.log` ansehen (Weg A): Alle fünf Minuten steht dort ein Block mit „[start]“ und „[ende] Code 0“.
