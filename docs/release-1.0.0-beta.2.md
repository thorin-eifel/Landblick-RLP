Zweite Beta von Landblick - RLP. Sie behebt, was an der ersten am meisten gestört hat: In den Installern fehlten fast alle Symbole. Dazu kommt das macOS-DMG, ebenfalls mit Karte.

**Beta heißt:** Alles ist beisammen und läuft, abgenommen ist es nicht. Offen sind der 7-Tage-Dauerlauf (R6), die Abnahme (R7), die Lizenzprüfung eines Teils der Quellen und die rechtliche Endabnahme. Einzelheiten in Kapitel 9 des Handbuchs.

## Was dranhängt

- `Landblick - RLP_1.0.0-beta.2_x64-setup.exe`: Windows-Installer (NSIS) mit den Kacheln für Rheinland-Pfalz plus 80 km (rund 1,8 GB). Nicht signiert: SmartScreen warnt beim ersten Start („Weitere Informationen“ → „Trotzdem ausführen“).
- `Landblick - RLP_1.0.0-beta.2_aarch64.dmg`: macOS-App für Apple Silicon (M1 bis M4), ebenfalls mit Kacheln (rund 1,8 GB). Nicht signiert, deshalb meldet macOS beim ersten Start „„Landblick - RLP“ ist beschädigt“. Die Datei ist in Ordnung: App in den Programme-Ordner ziehen, dann einmal im Terminal `xattr -dr com.apple.quarantine "/Applications/Landblick - RLP.app"`. Danach startet sie normal.
- `landblick-1.0.0-beta.2-quelltext.zip` / `.tar.gz`: der vollständige Quelltext samt Installern.
- `install.ps1`, `install.sh`, `install.py`: die Installer für einen Dauerläufer, einzeln zum Nachlesen und Prüfen.
- `landblick-1.0.0-beta.2-handbuch.pdf` / `.html` / `.md`: das Handbuch.
- `SHA256SUMS`: Prüfsummen der Release-Dateien.

Das hochauflösende Relief (Zoom 13/14, 4,3 GB) lädt die App weiterhin selbst vom Release `v1.0.0-alpha.2`.

## Neu seit beta.1

- **Symbole:** Die meisten Symbole kamen bisher von uxwing. Deren Lizenz verbietet die Weitergabe, deshalb fehlten sie in jedem Installer. Jetzt kommen alle aus Maki, Temaki und OpenStreetMap Carto (gemeinfrei) oder sind eigene Zeichnungen für Wetter und Messwerte. Sie liegen im Repository, ein Test prüft, dass keines fehlt.
- **macOS:** Das DMG bringt die Karte mit, wie der Windows-Installer; beim ersten Start entfällt der Download.
- **Alte Karte:** Das Titelschild heißt „Rheinland-Pfalz“ statt „Die Südeifel“, und die Jahreszahl folgt dem Kalender.

Vollständig im `CHANGELOG.md`.
