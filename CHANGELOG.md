# Änderungen

Format angelehnt an „Keep a Changelog“, Versionen nach SemVer. Alpha heißt: läuft, ist aber nicht abgenommen (rechtliche Prüfung, Dauerbetrieb, Lizenzvermerke der Landesdienste stehen aus).

## [1.0.0-alpha.1] - 2026-10-13

Erste Version unter der Nummer 1. Vorher gab es keine gezählten Versionen; der Stand davor ist als Git-Tag `archiv/vor-1.0.0-alpha.1` (Commit c9e0875) und als Archiv auf dem Arbeitsrechner gesichert.

### Installer (Zusatz seit dem ersten Stand dieser Version)
- Der Installer bietet am Ende an, die Rohdaten der Kartenwerkzeuge zu löschen (Probelauf von `tools/rohdaten_aufraeumen.py`, Rückfrage im Terminal, `--rohdaten-loeschen` ohne Rückfrage; `--ja` löscht nie).
- Flugabfrage (adsb.lol) sitzt auf der Landesmitte statt auf Irrel, Radius aus dem umschließenden Kreis der Region.
- `install.py` mit `install.ps1` (Windows) und `install.sh` (Linux, macOS): Umgebung, `.env`, erste Datensammlung, Export, Webserver, Jobs für Zyklus, Sicherung, Gesundheit, Livemodul und optional Dauerlauf-Proben (Windows-Aufgabenplanung, systemd, launchd), `--status`, `--deinstall`, `--dry-run`.
- `tools/release.sh` baut die Release-Dateien (Quelltext, Installer, Handbuch, Prüfsummen) und legt auf Wunsch das GitHub-Release an.
- `tools/zyklus.py` (portabler Zyklus), `tools/lauf.py` (rotierendes Log ohne Shell-Umleitung).
- Windows-Festigkeit: SQLite-URIs für schreibgeschützten Zugriff über `Path.as_uri()`, Signal-Fallback für den asyncio-Loop.

### R6 Betrieb und Härtung (Dauerlauf steht aus)
- `tools/gesundheit.py`: Zustand je Quelle und Region, Exportalter, Exit-Codes 0/1/2/3, `--json`.
- Zeitpläne: systemd-Units (`deploy/systemd/`), launchd-Jobs für Sicherung, Gesundheit und Dauerlauf.
- `tools/backup.py`: Prüfsummendatei je Sicherung, `--verify` als Wiederherstellungstest.
- Export räumt bei voller Platte halbe Temp-Dateien weg; alter Stand bleibt unverändert.
- Tests: Ausfall einzelner, halber und aller Quellen, Platte voll, Zeitumstellung (Python und JavaScript), Pinning aller Abhängigkeiten.
- CI: `pip-audit` auch für `requirements-dev.txt`, `npm audit` für `desktop/`. `PyYAML` in `requirements-dev.txt` gepinnt.
- `tools/dauerlauf.py` und `docs/rlp/r6-dauerlauf.md`: Messung und Protokoll für den 7-Tage-Lauf (der Lauf selbst steht aus).
- Umgebungsvariable für das Register heißt in `gesundheit.py` und `dauerlauf.py` jetzt wie im Rest (`OSINT_SOURCES`).

### Handbuch
- `docs/handbuch/` (zehn Kapitel), Bau mit `tools/handbuch.py` zu Markdown, HTML und PDF; die Quellentabelle entsteht aus `sources.yaml` und wird getestet.

### Enthalten
- **Raum:** ganz Rheinland-Pfalz, festes Gebiet, Landesgrenze als Rand; Quellen und Lizenzen im Register (`sources.yaml`), Seite „Quellen und Lizenzen“.
- **Sammler und Export:** Warnungen, Wetter, Pegel, Verkehr, Luft, Strahlung, Erdbeben, Meldungen, Länderquellen (LU, BE, FR); Zellenbetrieb im Frontend, Statusseite.
- **Karte:** eigene Vektorkacheln, Relief und Höhenlinien aus dem Landes-DGM1 (bis Zoom 16), Klippen und Schluchten, Gebäude aus den Hausumringen mit Funktionsklassen (GFK), Bewuchs, Wasserbewegung, Zeichenerklärung zu den Ebenen.
- **Bedienung:** Suche über alle Namen, Rechtsklick-Auskunft (Höhe, Koordinaten, Ort, Gemeinde, Kreis), Menüs „LGB Daten“ und „Landesdaten“ mit Hinweis vor jedem Fremdserver-Abruf.
- **Betrieb:** Desktop-App (Tauri) mit lokalem Sammler, Windows-Installer, Zugangsdaten je Quelle in der App (Datei mit Rechten 600, nicht im Schlüsselbund).

### Bekannte Lücken
- Gemarkung fehlt in der Rechtsklick-Auskunft (offene Daten dazu sind 1,3 GB groß).
- Teile der Legende (Pegel, Luftqualität, Strahlung, Erdbeben, Brandverdacht, Routen, Schutzgebiete, Grenzen, Infrastruktur-Symbole) sind noch ohne Eintrag.
- Lizenzangaben der Landesdienste sind noch nicht rechtlich geprüft.
