Erste Alpha-Fassung von Landblick - RLP: ein Lagebild aus offenen Daten für Rheinland-Pfalz plus 80 km (Warnungen, Wetter, Pegel, Verkehr, Luft, Strahlung), mit Quelle, Alter und Lizenz an jedem Datum. Keine Personen, kein Tracking, keine US-Cloud. Kein amtliches Warnsystem: im Notfall 112 und die offiziellen Warn-Apps.

**Alpha heißt:** läuft, ist aber nicht abgenommen. Offen sind der 7-Tage-Dauerlauf (R6), die Abnahme (R7), ein Test des Installers unter Windows, die Lizenzprüfung eines Teils der Quellen und die rechtliche Endabnahme. Einzelheiten in Kapitel 9 des Handbuchs.

## Was dranhängt

- `landblick-1.0.0-alpha.1-quelltext.zip` / `.tar.gz`: der vollständige Quelltext samt Installern (`install.ps1`, `install.sh`, `install.py` liegen im Wurzelordner). Entpacken, im Ordner installieren.
- `install.ps1`, `install.sh`, `install.py`: die Installer einzeln zum Nachlesen und Prüfen. Sie brauchen den Rest des Quelltexts und laufen nicht allein.
- `landblick-1.0.0-alpha.1-handbuch.pdf` / `.html` / `.md`: das Handbuch (Intention, Bedienung, Quellen, Architektur, Betrieb, Sicherheit, Grenzen, Referenz).
- `SHA256SUMS`: Prüfsummen.

## Installation in zwei Zeilen

```powershell
# Windows (PowerShell, normale Rechte)
.\install.ps1 -Kontakt "name@example.org"
```
```bash
# Linux, macOS
./install.sh --kontakt name@example.org
```

Danach läuft die Sammelstelle als geplante Aufgabe, die Seite ist unter `http://127.0.0.1:8080` erreichbar.

## Nicht enthalten

- Die Kartenarchive (mehrere Gigabyte); der Installer baut sie auf Wunsch (`--karte voll`).
- Die uxwing-Symbole (Lizenz verbietet Weitergabe); `tools/fetch_icons.sh` holt sie.
- Die Windows-Desktop-App (Tauri); sie wird im Workflow `windows-installer` gebaut.

Änderungen: `CHANGELOG.md`.
