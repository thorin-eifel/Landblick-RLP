Erste Beta von Landblick - RLP, und die erste mit einem fertigen Windows-Installer. Landblick ist jetzt eine reine Desktop-App: Der Weg über einen Webspace ist entfallen, die Karte läuft lokal mit eigenem Sammeldienst. Durchgehend heißt alles Landblick, auch Umgebungsvariablen, Datenbank und Kennungen.

**Beta heißt:** Alles ist beisammen und läuft, abgenommen ist es nicht. Offen sind der 7-Tage-Dauerlauf (R6), die Abnahme (R7), die Lizenzprüfung eines Teils der Quellen und die rechtliche Endabnahme. Den Windows-Installer hat bisher nur der Bau auf GitHub gesehen, kein echter Windows-Rechner. Einzelheiten in Kapitel 9 des Handbuchs.

## Was dranhängt

- `Landblick - RLP_1.0.0-beta.1_x64-setup.exe`: der Windows-Installer (NSIS) für die Desktop-App, mit den Kacheln für ganz Rheinland-Pfalz plus 80 km (rund 1,8 GB). Er ist nicht signiert: SmartScreen warnt beim ersten Start („Weitere Informationen“ → „Trotzdem ausführen“). Das hochauflösende Relief (Zoom 13/14, 4,3 GB) lädt die App danach selbst vom Release `v1.0.0-alpha.2`.
- `landblick-1.0.0-beta.1-quelltext.zip` / `.tar.gz`: der vollständige Quelltext samt Installern.
- `install.ps1`, `install.sh`, `install.py`: die Installer für einen Dauerläufer, einzeln zum Nachlesen und Prüfen.
- `landblick-1.0.0-beta.1-handbuch.pdf` / `.html` / `.md`: das Handbuch.
- `SHA256SUMS`: Prüfsummen der Release-Dateien.

## Desktop-App oder Dauerläufer

Die Desktop-App sammelt, solange sie geöffnet ist. Für einen Rechner, der rund um die Uhr läuft, mit Sicherung, Gesundheitsprüfung und Dauerlauf-Protokoll, ist `install.ps1` gedacht (Quelltext entpacken, Python 3.12, Administrator-Fenster):

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -Kontakt name@example.org -Dauerlauf -System -RuhezustandAus
```

## Neu seit alpha.2

- Reine Desktop-App: Upload, Webspace-Skripte, Plisten und systemd-Units aus `deploy/` sind entfernt; den Zeitplan legt `install.py` an.
- Windows-Installer mit mitgelieferten Kacheln; die Aufbauseite führt durch den ersten Start, bis der erste Export steht. Der Dienst schreibt ein Protokoll in den Datenordner.
- Ein Name: `LANDBLICK_*` statt `OSINT_*`, `data/landblick.sqlite`, Kennung `de.thorin.landblick`. Bestehende Installationen ziehen einmal um (Schritte in Pull Request #61).
- Behoben: Nach `cp .env.example .env` fielen alle Quellen aus, weil ein Kommentar mit Umlaut im User-Agent landete.
- Behoben: Der Desktop-Server lieferte über `..` im Pfad Zugangsdaten und Datenbank aus.
- Energie (Windräder, Solarparks, Kraftwerke, Umspannwerke, Leitungen), Messwerkzeug, Werkzeugleiste als Dock, Vollbild mit Menü und Detailfeld, Darstellungen und Schriften, eigene Menüzeichen.
- Abhängigkeiten: `pillow` 13.0.0, `certifi` 2026.10.19 (pip-audit ohne Befund).

Vollständig im `CHANGELOG.md`.
