# 5 Architektur und technische Basis

## 5.1 Das Leitbild

```
Quellen
  → Sammler          (app/collectors, ein Modul je Quelle)
  → Geofilter        (app/region.py, region.yaml)
  → Speicher         (SQLite, WAL-Modus)
  → Export           (app/export.py → JSON in web/data, Zellen)
  → statisches Frontend (web/, MapLibre, PMTiles)
```

Ein Rechner ruft die Quellen ab, filtert auf die Region und schreibt fertige Dateien. Alles danach ist statisch: Der Webserver liefert HTML, CSS, JavaScript, JSON und Kartenarchive aus, mehr nicht. Es gibt keine Anwendung auf dem Server, die Anfragen der Besucher auswertet, und damit auch keine Datenbank, die ein Besucher erreichen könnte.

Diese Trennung ist die wichtigste Entscheidung des Projekts. Sie macht den Betrieb einfach (jeder Webspace reicht), das Frontend robust (es zeigt, was da ist, auch wenn die Sammelstelle steht) und den Datenschutz leicht (der Server sieht von Besuchern nur, was jeder Webserver sieht).

## 5.2 Die Bausteine

**Quellenregister (`sources.yaml`, `app/registry.py`).** Lädt und prüft die Einträge. Fehlt ein Pflichtfeld, gibt es doppelte Kennungen oder ein Sammler ohne Modulnamen, bricht der Start ab.

**Sammler (`app/collectors/`).** Jeder Sammler erbt von `base.Collector`, holt eine Quelle, bereinigt Texte (`app/sanitize.py`) und liefert Ereignisse oder Messwerte. Gemeinsam ist ihnen: ehrlicher User-Agent mit Kontakt, Zeitlimit, Wiederholung mit Wartezeit, Schutzschalter nach fünf Fehlschlägen in Folge (15 Minuten Pause), Idempotenz (dieselbe Meldung zweimal ergibt einen Datensatz), Filter am Rand statt erst in der Oberfläche.

**Region (`region.yaml`, `app/region.py`).** Das Gebiet ist ein Polygon: Rheinland-Pfalz plus 80 Kilometer jenseits der Landesgrenze, Bezugspunkt Irrel. Ein Punkt außerhalb wird nicht gespeichert. Ein Kreis um einen Mittelpunkt wäre auch möglich; `LANDBLICK_REGION=<Datei>` stellt ein anderes Gebiet ein, ohne Code zu ändern.

**Speicher (`app/db.py`).** SQLite mit Write-Ahead-Log. Ereignisse (`events`), Stationen, Messwerte (`measurements`), ein Zwischenspeicher, die Läufe je Sammler (`collector_runs`) und der Zustand je Quelle (`collector_state`: letzter Erfolg, Fehler in Folge) liegen in getrennten Tabellen. Inaktive Ereignisse, Messwerte und Laufprotokolle werden nach der Aufbewahrungsfrist gelöscht (30 Tage, `LANDBLICK_RETENTION_DAYS`). Für Leser öffnet `ro_uri` die Datei schreibgeschützt.

**Ereignisschema (`app/models.py`).** Einheitlich: Kennung, Quelle, Typ, Titel, Zusammenfassung, Schweregrad (`info`, `notice`, `warning`, `critical`), Geometrie, Region, Gültigkeit, Abrufzeit, Verweis auf das Original. Messreihen haben eigene Tabellen.

**Export (`app/export.py`, `app/export_cells.py`, `app/cells.py`).** Schreibt aus der Datenbank:
- `manifest.json`: Verzeichnis aller Dateien mit Prüfsumme,
- `start.json`: das Startpaket (Warnband, Quellenzustand, Zähleinheiten),
- Zellen: die Region ist in Kacheln zu 0,5 Grad geteilt, je Zelle eine Datei für Ereignisse und eine für Messwerte, damit der Browser nur lädt, was im Bild liegt,
- `meta.json` mit Erzeugungszeit (das Alter des Exports),
- Flachdateien als Rückfall für alte Stellen.
Geschrieben wird atomar (temporäre Datei, dann umbenennen); eine halb geschriebene Datei bleibt nie liegen.

**Zugang (`app/zugang.py`, `web/js/zugang.js`).** Regelt, was ohne Zustimmung geht und was nicht (Kapitel 7).

**Live (`app/live.py`).** Optionaler Dauerprozess für schnelle Quellen (Flugverkehr), die alle paar Sekunden aktualisiert werden. Er schreibt in dieselbe Datenbank, aber getrennt vom Takt der übrigen Sammler.

**Desktop-Hülle (`desktop/`, `app/desktop.py`).** Tauri-Anwendung, die den Python-Dienst und das Frontend in einem Fenster bündelt, mit GPU-Beschleunigung. Sie ist eine Ergänzung, kein Muss.

## 5.3 Das Frontend

Semantisches HTML, JavaScript als ES-Module ohne Bauschritt und ohne Framework, MapLibre GL für die Karte, PMTiles für die Kartenkacheln. Schriften, Skripte und Kacheln liegen lokal (`web/fonts`, `web/vendor`, `web/tiles`). Die Dateien in `web/js/lage/` trennen Karte, Ebenen, Laden, Popup, Zustand und Suche; `web/js/rules.js` ist die Regel, nach der Quellen als ok, veraltet oder ausgefallen gelten, und wird gegen die Python-Fassung getestet, damit Statusseite und Gesundheitsprüfung nicht auseinanderlaufen.

Die Karte liest ihre Kacheln per HTTP Range aus einem einzigen Archiv. Das ist der Grund, warum der mitgelieferte lokale Webserver (`deploy/serve-local.py`) Range-Anfragen beherrscht; ein Server, der sie nicht kann, zeigt eine leere Karte.

## 5.4 Die Kartenbasis

Die Karte nutzt keine Kacheln von Dritten. Die Basiskarte ist ein Ausschnitt der Protomaps-Basiskarte (OpenStreetMap-Daten, ODbL), dazu kommen Archive für Gebäudedetails, ein Höhenrelief, Felswände aus dem DGM1, ein Gewässernetz. Die Archive sind groß (der gesamte Satz liegt bei mehreren Gigabyte), werden nicht im Repository geführt und mit `tools/build_region_tiles.py` und den weiteren `tools/build_*.py` erzeugt. Fehlt eine Datei, bleibt die zugehörige Ebene aus; die Karte läuft trotzdem.

## 5.5 Technische Eckdaten

| Bereich | Wahl |
|---|---|
| Sprache Backend | Python 3.11 oder neuer |
| Netzwerk | `httpx` (asynchron), Zeitlimit, Wiederholung, Schutzschalter |
| Validierung | `pydantic` |
| Konfiguration | `.env`, Register in YAML, Gebiet in `region.yaml` |
| Speicher | SQLite (WAL); PostGIS erst, wenn Messwerte es verlangen |
| Frontend | Vanilla-ES-Module, MapLibre GL, PMTiles |
| Auslieferung | statische Dateien; beliebiger Webserver mit Range-Unterstützung |
| Betrieb | Aufgabenplanung (Windows), systemd (Linux), launchd (macOS) |
| Tests | pytest (Python), `node --test` (JavaScript) |
| Lizenz | GPL-3.0 |

## 5.6 Warum diese Wahl

SQLite statt PostGIS, weil die Mengen es hergeben (gemessen wird, nicht geraten) und eine einzelne Datei sich sichern und verschieben lässt. Kein Framework im Frontend, weil jedes Framework eine Lieferkette mitbringt, die jemand in zwei Jahren noch pflegen muss. Statisches Ausliefern, weil ein Server ohne Anwendung wenig angreifbar ist. Lokale Kacheln, weil jeder Kartenabruf bei einem Dritten verraten würde, wer wo hinschaut.
