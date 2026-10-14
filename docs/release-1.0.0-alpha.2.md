Zweite Alpha-Fassung von Landblick - RLP. Das Relief ist neu gebaut: Die gerade Naht in Schummerung und Höhenlinien an der Kante der Landes-DGM1-Abdeckung (bei Vianden und Echternach) ist weg. Dazu hängt jetzt das Nachladepaket mit dem hochauflösenden Relief am Release, und die Desktop-App kennt seine Adresse.

**Alpha heißt weiter:** läuft, ist aber nicht abgenommen. Offen sind der 7-Tage-Dauerlauf (R6), die Abnahme (R7), ein Test des Installers unter Windows, die Lizenzprüfung eines Teils der Quellen und die rechtliche Endabnahme. Einzelheiten in Kapitel 9 des Handbuchs.

## Was dranhängt

- `landblick-1.0.0-alpha.2-quelltext.zip` / `.tar.gz`: der vollständige Quelltext samt Installern.
- `install.ps1`, `install.sh`, `install.py`: die Installer einzeln zum Nachlesen und Prüfen.
- `landblick-1.0.0-alpha.2-handbuch.pdf` / `.html` / `.md`: das Handbuch.
- `dem-hoch.pmtiles.part01` bis `part03` und `dem-hoch.pmtiles.manifest.json`: das Relief Zoom 13/14 (4,3 GB). Die Desktop-App holt es selbst, mit Wiederaufnahme und Prüfsummen. Von Hand: `python -m app.pakete --manifest <Adresse des Manifests> --dest <Ordner>`.
- `SHA256SUMS`: Prüfsummen der Release-Dateien. Die Prüfsummen der Relief-Teile stehen im Manifest.

## Nicht enthalten

- `dem.pmtiles` (Zoom 6–12), Felswände, Hangneigung und Gebäude: die kommen mit dem Windows-Installer, der noch nicht gebaut und getestet ist.
- Die Basiskarte (rund 1,5 GB): Download beim ersten Start.
- Die uxwing-Symbole (Lizenz verbietet Weitergabe): `tools/fetch_icons.sh` holt sie.

Änderungen: `CHANGELOG.md`.
