# Handbuch Landblick - RLP

Das Handbuch zu Version 1.0.0-beta.1, in Kapiteln als Markdown. Gebaut wird es mit `python tools/handbuch.py` (HTML und PDF unter `build/handbuch/`). Die fertigen Dateien hängen am GitHub-Release.

| Kapitel | Inhalt |
|---|---|
| [1 Einleitung](01-einleitung.md) | Wozu es das gibt, was es ist und nicht ist, Leitplanken |
| [2 Schnellstart](02-schnellstart.md) | Installation auf Windows, Linux und macOS |
| [3 Bedienung](03-bedienung.md) | Karte, Ebenen, Suche, Status lesen |
| [4 Datenquellen](04-datenquellen.md) | Quellenregister, Lizenzen, vollständige Liste |
| [5 Architektur](05-architektur.md) | Aufbau und technische Basis |
| [6 Betrieb](06-betrieb.md) | Jobs, Gesundheit, Backup, Dauerlauf, Fehlersuche |
| [7 Sicherheit und Datenschutz](07-sicherheit-datenschutz.md) | Grundsätze, Zustimmungsschranke, Recht |
| [8 Entwicklung](08-entwicklung.md) | Tests, neue Quelle, Phasen, Mitarbeit |
| [9 Grenzen](09-grenzen.md) | Was nicht fertig ist |
| [10 Referenz](10-referenz.md) | Variablen, Befehle, Dateien, Glossar |
| [11 Darstellung und Skins](11-darstellung.md) | Kartenstil, Farbquellen, Zeichen, CSS und SVG, Grundlage für Themen |

Die Quellentabelle in Kapitel 4 entsteht aus `sources.yaml` (`python tools/handbuch.py --update`); ein Test prüft, dass sie aktuell ist.
