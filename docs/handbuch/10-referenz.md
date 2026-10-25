# 10 Referenz

## 10.1 Umgebungsvariablen

Sie stehen in `.env` im Projektordner (nicht im Repository, Vorlage `.env.example`). Eine bereits gesetzte Umgebungsvariable hat Vorrang vor `.env`. `LANDBLICK_NO_DOTENV=1` schaltet das Laden der Datei ab.

| Variable | Standard | Bedeutung |
|---|---|---|
| `LANDBLICK_CONTACT` | – | Kontaktadresse im User-Agent gegenüber den Quellen (Pflicht, der Installer setzt sie) |
| `LANDBLICK_DB_PATH` | `data/landblick.sqlite` | Datenbankdatei |
| `LANDBLICK_SOURCES` | `sources.yaml` | Quellenregister |
| `LANDBLICK_WEB_DIR` | `web` | Ordner des Frontends (Export nach `<web>/data`) |
| `LANDBLICK_REGION` | `region.yaml` | anderes Gebiet |
| `LANDBLICK_EXPORT_DIR` | `<web>/data` | Exportordner für die Gesundheitsprüfung |
| `LANDBLICK_HTTP_TIMEOUT` | 20 | Zeitlimit je Abruf in Sekunden |
| `LANDBLICK_HTTP_ATTEMPTS` | 3 | Versuche je Abruf |
| `LANDBLICK_BREAKER_THRESHOLD` | 5 | Fehlschläge bis Pause |
| `LANDBLICK_BREAKER_COOLDOWN` | 900 | Pause in Sekunden |
| `LANDBLICK_RETENTION_DAYS` | 30 | Aufbewahrung |
| `LANDBLICK_LIVE` | – | `1`: der Live-Dienst übernimmt schnelle Quellen, der Zyklus lässt sie aus |
| `TANKERKOENIG_API_KEY` | – | Schlüssel für Spritpreise Deutschland |
| `FIRMS_MAP_KEY` | – | Schlüssel für NASA FIRMS |
| `PUBLISH_ENABLED` | – | `1`: der Zyklus lädt Änderungen hoch (nur wenn Upload eingerichtet ist) |
| `IONOS_SFTP_HOST`, `_USER`, `_KEY`, `_PASSWORD`, `IONOS_REMOTE_DIR` | – | Zugang zum Webspace für den Upload |

## 10.2 Befehle

| Befehl | Wirkung |
|---|---|
| `python -m app.collect --once` | alle aktiven Quellen einmal abrufen |
| `python -m app.collect --due` | nur fällige Quellen |
| `python -m app.collect --only ID …` | nur die genannten Quellen |
| `python -m app.collect --healthcheck` | Zustand der Sammler ausgeben |
| `python -m app.export` | Export schreiben (`--out`, `--db`, `--no-cells`, `--no-legacy`) |
| `python -m app.region` | Gebiet anzeigen |
| `python -m app.live` | Live-Dienst |
| `python tools/zyklus.py` | ein Zyklus: Abruf, Export, optional Upload |
| `python tools/gesundheit.py` | Gesundheitsprüfung (`--json`) |
| `python tools/backup.py --out DIR --keep 14 --verify-after` | Sicherung |
| `python tools/dauerlauf.py sample / note / report` | 7-Tage-Lauf |
| `python deploy/serve-local.py --dir web --port 8080 --bind 127.0.0.1` | lokaler Webserver |
| `python install.py --status / --deinstall / --dry-run` | Installer verwalten |
| `python tools/update_readme.py [--check]` | Stand der README erzeugen oder prüfen |
| `python tools/handbuch.py` | dieses Handbuch bauen (`--check` prüft die Quellentabelle) |

## 10.3 Optionen des Installers

| Option (Bash / PowerShell) | Bedeutung |
|---|---|
| `--kontakt` / `-Kontakt` | Kontaktadresse (Pflicht, wird nicht erraten) |
| `--bind`, `--port` / `-Bind`, `-Port` | Adresse und Port des Webservers (127.0.0.1, 8080) |
| `--karte keine\|voll` / `-Karte` | Kartenarchive bauen (nach Rückfrage) |
| `--ohne-erstlauf` / `-OhneErstlauf` | keinen ersten Abruf |
| `--ohne-live` / `-OhneLive` | Live-Dienst weglassen |
| `--dauerlauf` / `-Dauerlauf` | Messpunkt-Job für den 7-Tage-Lauf |
| `--system` / `-System` | systemweit statt für den Benutzer (Administrator nötig) |
| `--ruhezustand-aus` / `-RuhezustandAus` | Windows: Ruhezustand abschalten |
| `--ohne-dienste` | nur einrichten, keine Jobs |
| `--ja` / `-Ja` | Rückfragen mit Ja beantworten |
| `--status`, `--deinstall` / `-Status`, `-Deinstall` | Jobs anzeigen, Jobs entfernen |
| `--dry-run` / `-DryRun` | nur anzeigen, nichts ändern |

## 10.4 Dateien und Ordner

| Pfad | Inhalt |
|---|---|
| `data/landblick.sqlite` | die Datenbank |
| `data/logs/` | Logs der Jobs (rotierend) |
| `data/backup/` | Sicherungen mit Beschreibungsdatei |
| `data/dauerlauf.jsonl` | Messpunkte des 7-Tage-Laufs |
| `web/data/` | Export (manifest, start, meta, Zellen) |
| `web/tiles/` | Kartenarchive (PMTiles) |
| `web/geo/` | Gebietsgrenzen, Kataloge der Landesdienste |
| `.env` | Einstellungen und Schlüssel |
| `.venv/` | Python-Umgebung des Installers |

## 10.5 Exit-Codes der Gesundheitsprüfung

0 in Ordnung, 1 Warnung, 2 kritisch, 3 Prüfung selbst fehlgeschlagen.

## 10.6 Glossar

**ARS** – amtlicher Regionalschlüssel. **Collector / Sammler** – Modul, das eine Quelle abruft. **Delta-Upload** – nur geänderte Dateien hochladen. **Export** – fertige JSON-Dateien für das Frontend. **Lagebild** – Überblick über die Lage einer Region. **PMTiles** – ein Kartenarchiv in einer Datei, das der Browser stückweise liest. **Quellenregister** – `sources.yaml`. **Region** – das Gebiet in `region.yaml`. **WAL** – Write-Ahead-Log, SQLite-Modus, in dem Lesen und Schreiben sich nicht blockieren. **WMS** – Dienst für Kartenbilder.

## 10.7 Versionen und Lizenz

Version 1.0.0-alpha.1. Lizenz GPL-3.0 (siehe `LICENSE`). Daten haben die Lizenzen ihrer Quellen (Kapitel 4). Autor und Betreiber: Thorsten Schleicher, Ferschweiler.
