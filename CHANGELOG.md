# Änderungen

Format angelehnt an „Keep a Changelog“, Versionen nach SemVer. Alpha heißt: läuft, ist aber nicht abgenommen (rechtliche Prüfung, Dauerbetrieb, Lizenzvermerke der Landesdienste stehen aus).

## [Unreleased]

### Behoben (Vollbild)
- Das Vollbild zeigt jetzt die ganze Lageseite statt nur der Kartenfläche: Menü mit Suche und das Detailfeld bleiben sichtbar (vorher fehlten beide). Die Suchzeile muss dafür nicht mehr umziehen. Schmal gestapelt scrollt die Seite im Vollbild.

### Geändert (Anordnung)
- Zoom, Vollbild, Messen und Maßstab sitzen in einer Werkzeugleiste unten mittig nach Art des macOS-Docks (Glasleiste, Kacheln werden beim Darüberfahren nur heller, ohne Bewegung). Bis 640 px Breite steht sie über den beiden Legenden. Ist das Detailfeld offen, rückt die Zeichenerklärung über die Leiste. Auf der Karte um 1450 entfällt der Maßstab wie bisher.
- Das Messfeld sitzt oben rechts (folgt dem Detailfeld bei jeder Breite) statt unten über der Kartenmitte und dem Maßstab. Auf schmalen Schirmen ist es kompakter.
- Breite Schirme: Das Menü links lässt unten Platz für Höhenlegende bzw. Windrose und scrollt innen, statt sie zu überdecken.
- Schmale Schirme (bis 1000 px): Eine geöffnete Menügruppe nimmt die ganze Zeile, die übrigen bleiben in einer Reihe (vorher rutschte „Freizeit“ neben die offene Gruppe). Bis 640 px steht der Maßstab oben links statt zwischen den Legenden.

### Geändert (Burgen)
- Burg und Ruine teilen das Zeichen, unterscheiden sich jetzt aber deutlich in der Farbe: Burg und Schloss karminrot, Ruine moosgrün (vorher dunkelrot und grau).

### Neu (Messen)
- Messwerkzeug im Dock (Lineal): Punkte anklicken ergibt Strecke mit Abschnittslängen; den ersten Punkt erneut anklicken oder „Schließen“ ergibt Fläche (m², ha, km²) und Umfang, ab drei Punkten schon als Vorschau. Kreuzen sich die Kanten, steht eine Warnung dabei. Ohne Maus: „Punkt in Kartenmitte“, Rücktaste, Eingabe, Esc. Werte lassen sich kopieren. Kugelrechnung, Abweichung unter 0,5 %; keine Vermessung. Nichts wird gespeichert oder gesendet.

### Neu (Geographie → Energie)
- Eigene Gruppe **Energie** mit sechs Schaltern: Windräder (aus „Orte und Einrichtungen“ hierher verschoben), Solarparks, Kraftwerke, Umspannwerke, Transformatoren, Hochspannungsleitungen (`wturb`, `enSolar`, `enPlant`, `enSub`, `enTrafo`, `enLine`). Jeder Schalter hat ein eigenes Zeichen (Temaki, CC0; Solar eigene Zeichnung).
- Tankstellen mit Preisen (`tank`) und Ladesäulen (`charge`) gehören jetzt ebenfalls zu Energie; die Gruppe „Verkehr und Tanken“ heißt „Verkehr“. Schalternamen und Daten bleiben unverändert.
- Quellen: `sgdnord_energie` (Raumordnungskataster ROK25 Online der SGD Nord, dl-de/by-2.0, täglich): Windräder (am Netz, genehmigt, beantragt) mit Nennleistung, Nabenhöhe und Gesamthöhe, Solarparks mit Umriss und Leistung. Betreiber, Typ und Aktenlinks werden nicht übernommen. `osm_energie` (ODbL, wöchentlich): Kraftwerke, Solarparks, Umspannwerke, Transformatoren und Leitungen ab 110 kV. Amtliche Windräder und Solarparks ersetzen OSM-Einträge im Umkreis von 150 m bzw. 400 m.
- Neue Ausgabe `energie.json` und Zellenart `energie` (ab Zoom 9, Leitungen laufen über Zellgrenzen). Geplante Windräder erscheinen blasser; Popup nennt Stand, Maße und Quelle.
- Lücke: Der Süden (SGD Süd) bietet keinen vergleichbaren offenen Dienst; dort kommt alles aus OpenStreetMap. Die amtlichen Wasserkraftdaten sind nicht verwendbar.
- Geändert: Umspannwerke, Kraftwerke und Leitungen kommen jetzt aus `osm_energie` (nur Übertragungsnetz ab 110 kV), nicht mehr aus `osm_infra`. Die frühere Entscheidung, sie wegzulassen, ist damit aufgehoben.
- Der OSM-Sammler wurde aus der Entwicklungsumgebung nicht live getestet (Overpass dort nicht erreichbar); Parser und Zusammenführung sind mit Fixtures bzw. synthetischen Daten geprüft.

### Geändert (Menüzeichen)
- Jeder Schalter und jeder Reiter hat ein eigenes Zeichen; vorher teilten sich 58 Einträge das Wanderer-Zeichen und zehn Straßen- und Verkehrseinträge das Stau-Zeichen. Neue Zeichen aus Maki, Temaki und OSM Carto (alle CC0) in `web/icons/menu/`, dazu acht eigene für Straßenklassen und Grenzebenen. Der Test `icons-eindeutig` verhindert Doppelungen.

### Geändert (Natur und Freizeit)
- „Natur und Freizeit“ ist aufgeteilt. **Geographie → Natur** hat fünf Schalter statt einem: Berggipfel, Höhlen, Wasserfälle und Quellen, Aussichtspunkte, Felsen und Vulkane (`natPeak`, `natCave`, `natWater`, `natView`, `natRock`; ersetzen `nature`). Das neue Menü **Freizeit** führt Wanderrouten, Radrouten und Rast und Baden (Rastplätze, Schutzhütten, Badestellen). `web/index.html`, `web/js/lage/natur.js`, `zustand.js`, Handbuch Kapitel 3.3.

### Geändert (Menüs)
- Das Menü „Ebenen“ ist aufgeteilt in **Ereignisse** (was gerade passiert: Warnungen und Gefahren, Wetter und Luft, Wasserstände, Verkehr und Tanken) und **Geographie** (die Landkarte selbst: Gelände und Gebäude, Wald, Wiesen und Felder, Straßen und Bahn, Grenzen und Schutzgebiete, Orte und Einrichtungen, Natur und Freizeit, Kultur und Geschichte, dazu die Zusatzkarten LGB Daten und Landesdaten). Alle 70 Schalter sind erhalten und gleich benannt, bis auf „Pegel (Wasserstand der Flüsse)“ und „Berge und Täler (Schattierung und Farbe)“. Wehre und Schleusen wechseln zu „Orte und Einrichtungen“, Tankstellen bleiben beim Verkehr. `web/index.html`, Handbuch Kapitel 3.3.

### Geändert (Übersichtskreise)
- Klick auf einen Kreis oder ein Land in der Übersicht zoomt wie bisher auf die Fläche, setzt jetzt aber auch den Gebietsfilter auf diese Einheit, klappt das Detailfeld auf und zeigt den Reiter „Ereignisse“. Die Liste nennt so genau die Meldungen des gewählten Kreises; „Zurücksetzen“ hebt den Filter auf. Liegen Ereignisse im Ausschnitt nur in ausgeschalteten Ebenen, sagt die Liste das, statt „kein Ereignis“ zu melden. `gebietAusEinheit()` in `web/js/gebiet.js`, `zeigeEinheit()` in `lage/ereignisliste.js`, Test `tests/js/gebiet.test.mjs`.

### Behoben (Code-Review)
- Desktop-Server lieferte per `/data/../zugang.json` oder `/tiles/../osint.sqlite` Zugangsdaten und Datenbank aus (Pfadprüfung gegen den ganzen Datenordner). Erlaubt ist jetzt nur `data/` bzw. `tiles/`, Verzeichnisse werden nicht mehr aufgelistet, der Datenordner wird aufgelöst (Symlink, relativer Pfad). `app/desktop.py`, Tests `tests/test_desktop.py`.
- Sammel-Takt der Desktop-App endete dauerhaft nach einem Timeout oder einem Exportfehler. Jetzt wird der Fehler gemeldet und im nächsten Takt neu versucht; nach dem ersten Export bleibt die Karte offen.
- Tankerkönig: die Reihenfolge der Abfragepunkte läuft über einen Zeiger statt über die Uhr, damit bei 300-s-Takt (Desktop) keine Punkte ausfallen. Zeiger rückt auch nach Fehlschlag weiter.
- `fetch_text` lehnt Weiterleitungen (3xx) ab statt deren Rumpf als Antwort zu nehmen.
- Karte: Art `anbau` wird aus den Zellen in die Karte gesetzt; ein fehlgeschlagener Erstabruf ersetzt keine vorhandenen Daten mehr; die Statuszeile nennt, wenn der Ausschnitt mehr Zellen braucht als geladen werden; neueres Manifest während eines laufenden Abrufs führt zum Nachladen.
- Regeln: unlesbare Zeitangaben verbergen Ereignisse nicht und täuschen keine Aktualität vor (`windowFilter`, `deriveStatus`, `exportStale`); `cssColor` behält Alpha.

### Dokumentation
- Handbuch: neues Kapitel 11 „Darstellung und Skins“ (Aufbau des Kartenstils, Farbquellen, Zeichen, CSS und SVG, Befund für Themen).

### Geändert
- Zahlen in den Übersichtskreisen (Land und Kreis) sitzen in jeder Schrift optisch mittig: Kreis und Ziffern werden als Bild auf Canvas gezeichnet und nach der echten Tintenfläche der Ziffern zentriert, statt über die feste Zeilenhöhe von MapLibre. Gemessen in zehn Schriften und vier Zahlen: Abweichung höchstens 1 Pixel bei 2-facher Auflösung, mit zwei Ausreißern von 1,5 und 2 Pixel (Caveat „8“, Grenze Gotisch 100). `web/js/lage/plakette.js`, Test `tests/js/plakette.test.mjs`, neue Schrift `noto-sans.woff2` (OFL). Weitere Zahlen in Kreisen gibt es auf der Karte nicht.
- Detailfenster (Ereignisse, Gewässer, Luft und Strahlung) zeigt nur, was im sichtbaren Kartenausschnitt liegt, und folgt jeder Kartenbewegung (entprellt, 250 ms). `web/js/lage/ausschnitt.js` (rein), `ausschnitt-karte.js`, `detailNachBewegung()` in `laden.js`; Test `tests/js/ausschnitt.test.mjs`. Die Zahl neben „Lagekarte“ zählt weiter alle Ereignisse im Zeitfenster, die Tabelle nennt ihre Zahl „im Ausschnitt“.
- Warnungen (NINA, DWD) und Hochwasser sind jetzt standardmäßig an. Vorher zählte die Übersicht sie je Kreis mit, aber nach dem Zoom in einen Kreis fehlten die Einzelmeldungen auf der Karte, weil die Ebenen aus waren.
- Ebenenmenü aufgeräumt: lange Beschriftungen gekürzt (Einzelheiten als Tooltip), Zeilen brechen um statt abzuschneiden (kein seitliches Scrollen, keine leeren Zeilen), die sechs gleichen Gebirgs-Icons der Kartengrundlage entfallen, Trennlinien zwischen den Themen, kürzere Themen-Hinweise.

### Hinzugefügt
- Menü „Darstellung“ in drei Bereiche geteilt: Farb-Schema (Paletten), Symbole (Grundzeichnung, Alte Karte, Oxford) und Schrift (`web/js/lage/darstellung.js`; `state.schema`, `state.symbole`, `state.skin` = wirksamer Skin). Ein Symbolsatz bringt eigene Farben mit und sperrt das Schema. Neu: Knopf „Anpassen …“ öffnet ein Formular (`<dialog>`) für eigene Farben (Palette: zehn Felder je Ansicht; Zeichensatz: Papier, Tinte, Wasser, Wald) und Symbolschalter (Flächenmuster; Windrose und Fabelwesen); daraus entsteht der Skin „eigen“ (`web/js/lage/anpassen.js`, nur #rrggbb und Schalter, nichts gespeichert). Test: `tests/js/anpassen.test.mjs`.
- Schriftwahl unter „Darstellung“ (`web/js/lage/schrift.js`): acht mitgelieferte OFL-Schriften (Lora, Alegreya, Cinzel, IM Fell English, Almendra, Uncial Antiqua, Pirata One, Caveat als woff2 in `web/fonts/woff2`, über MapLibre `font-faces`) plus Schriften des Geräts (Liste per `queryLocalFonts()` nach Zustimmung oder getippter Name). Wirkt auf alle Beschriftungs-Layer, „Standard“ behält die Schrift der Darstellung. Nichts wird gespeichert. Test: `tests/js/schrift.test.mjs`.
- Darstellungen (Skins) in zwei Methoden, beide nebeneinander: Farbpaletten (`web/js/lage/skins.js`: Mountain View, Cupertino, Amsterdam, Olathe, Ostfildern, je hell und dunkel) und Zeichensätze (`zeichensaetze.js`, `zeichensatz.js`: tauschen Flächenmuster, Hügel-, Wellen- und Siedlungszeichen, Schrift und Zierde; Alte Karte und neu Oxford als Federzeichnung, nur hell). Auswahl unter „Darstellung“ (`state.skin`, `html[data-skin]`). Eigene Zeichnungen in der Anmutung der Gattung, keine Nachbauten von Produkten oder Werken. Tests: `tests/js/skins.test.mjs`, `tests/js/zeichensaetze.test.mjs`.

### Behoben
- Karte: Straßennamen fehlten fast überall außer an Haupt- und Landstraßen, ebenso kleine Straßen und Wege. Ursache: `region.pmtiles` endet bei Zoom 13 und führt dort Namen nur für größere Straßen. Straßenlinien und -namen werden ab Zoom 14 aus `core.pmtiles` und `ring.pmtiles` gezeichnet (`roadsFromDetail` in `stil.js`, Ebenen mit Endung `_c` und `_r`), die dieselbe Schicht vollständig tragen. Geprüft in Irrel, Wittlich (Kern) und Pirmasens (Ring). Tests: `tests/js/strassen-detail.test.mjs`.

### Geändert
- Karte: Gebäude stehen im Nahbereich deutlicher da: Deckkraft 40 % bis Zoom 14, linear bis 75 % bei Zoom 17 (vorher fest 40 %). Gebäude liegen über Schummerung und Hangneigung (Dächer sind flach, kein Schatten und keine Hangflecken auf Häusern), unter Höhenlinien und Wasser. Die Hangflächen blenden zwischen Zoom 16 und 17,5 aus, im Hausmaßstab sind sie zu grob.
- Karte: Klippen aus OpenStreetMap (dort, wo keine Wände aus dem Geländemodell vorliegen, z. B. Luxemburg) werden wie diese gezeichnet: Wandband rechts der Linie, Oberkante wie bei einer 10-m-Wand, feine Fallstriche (Bild `cliff-stroke`) ab Zoom 14; Breite, Strichlänge und -abstand wachsen mit dem Zoom wie bei den Kacheln.
- Karte: OSM-Klippen erscheinen nicht mehr zusätzlich dort, wo es Wandkacheln gibt (bisher lagen im Grenzstreifen zu Luxemburg beide Zeichnungen übereinander). Grundlage ist die tatsächliche Kachelabdeckung (`web/js/lage/klippen-umriss.js`, erzeugt mit `tools/build_klippen_umriss.py`), nicht mehr die Landesgrenze.

### Quellenübersicht: Zugangsdaten auch auf dem lokalen Webserver
- `deploy/serve-local.py` beantwortet wie die Desktop-App `api/zugang` (Status, Setzen, Löschen) und legt API-Schlüssel in `data/zugang.json` ab (Rechte 600). Nur auf Loopback, mit Host-, Herkunfts- und Kopfprüfung; auf anderen Adressen gibt es den Weg nicht. Die Logik teilen sich App und Webserver (`app/zugang.py`, `handle_post`).
- `app/config.py` liest `data/zugang.json` nach der `.env` in die Umgebung, damit Zeitplan-Läufe die dort eingegebenen Schlüssel nutzen (`OSINT_ZUGANG` ändert den Pfad). `.env` und Shell gehen vor.

### Darstellung: Alte Karte
- Neues Menü „Darstellung“ mit „Landblick“ und „Alte Karte“ (bisher „Karte im Stil des 15. Jahrhunderts“, ein Schalter unter Kartengrundlage). Weitere Darstellungen sind vorgesehen.
- Klippen und Felswände aus dem Geländemodell (Wandfläche, Schraffen, Oberkante, Geröllband) werden in der Alten Karte genauso gezeichnet wie in Landblick, in Tinte und Pergament statt Grau.
- Kirchen, Kapellen, Wegkreuze, Mühlen, Furten, Grenzsteine, Richtstätten und Brunnen sind in beiden Darstellungen wählbar; der Zusatz „(nur Karte um 1450)“ entfällt. In Landblick erscheinen sie mit denselben Zeichen wie in der Alten Karte.
- Am Rand: `med-cliff` (altes Schraffenbild) entfällt.

### Karte: Reihenfolge der Ebenen
- Die Hangneigung liegt jetzt unter der Vegetation (Landnutzung), die Klippen weiterhin über allem Gelände. Die Hangflächen sind etwas kräftiger (Deckkraft 0,16 / 0,20 / 0,24), damit sie durch Wald und Wiese lesbar bleiben.

## [1.0.0-alpha.2] - 2026-10-14

### Relief: Naht an der Abdeckungskante
- Zwischen Landes-DGM1 und Mapzen lag an der Kante der Abdeckung (Kilometerraster, Randkacheln bei Vianden und Echternach) ein Höhensprung von rund 10 bis 14 m, in Schummerung und Höhenlinien als gerade Naht sichtbar. `tools/build_dem_rlp.py` führt den Versatz jetzt über `blend_bias()` mit cos²-Übergang über rund 730 m nach außen aus. Das Relief ist neu gebaut und neu gepackt.

### Nachladepaket
- `PAKETE_MANIFEST` in `app/desktop.py` zeigt auf das Manifest am Release: `dem-hoch.pmtiles` (Zoom 13/14, 4,3 GB) in drei Teilen unter 1,6 GB mit Prüfsumme je Teil und gesamt. Die App lädt es im Hintergrund nach, mit Wiederaufnahme.

## [1.0.0-alpha.1] - 2026-10-13

Erste Version unter der Nummer 1. Vorher gab es keine gezählten Versionen; der Stand davor ist als Git-Tag `archiv/vor-1.0.0-alpha.1` (Commit c9e0875) und als Archiv auf dem Arbeitsrechner gesichert.

### Karte (Zusatz): Hangneigung und Kachelpakete
- Neue Ebene „Hangneigung“ aus dem 1-m-DGM1: Flächen ab 15, 25 und 35 Grad als Vektorkacheln Zoom 14 (`tools/build_hang_rlp.py`, Probe `tools/build_hang_probe.py`). Durchscheinend, Klippenfläche ebenfalls heller (20 %), Wandstriche und Oberkante deckend.
- `tools/pack_tiles.py` packt Kachelordner (Relief, Felswände, Hangneigung) zu PMTiles und zerlegt sie in Teile unter 2 GB mit Manifest und SHA-256. `app/tilepack.py` liest solche Pakete; der Desktop-Server liefert daraus die Ordner-URLs `tiles/dem/…`, `tiles/klippen/…` und `tiles/hang/…` aus (ein vorhandener Ordner hat Vorrang).

- Relief geteilt: `dem.pmtiles` (Zoom 6–12, rund 680 MB) kommt in den Installer, `dem-hoch` (Zoom 13/14, rund 4,3 GB in drei Teilen) lädt die App im Hintergrund nach. `app/pakete.py` holt die Teile mit Range-Wiederaufnahme in eine Datei, prüft Teil- und Gesamtsumme und benennt erst dann um; `/api/state` meldet den Stand unter `nachladen`. Adresse des Manifests: `PAKETE_MANIFEST` in `app/desktop.py` oder `OSINT_PAKETE_MANIFEST` (`aus` schaltet ab). Solange keine Adresse eingetragen ist, passiert nichts.

- Desktop-Installer liefert Relief (bis Zoom 12), Felswände, Hangneigung, Gebäude und den Suchindex als Tauri-Ressource `pakete/` mit (`desktop/stage-pakete.sh`, bricht über 1,9 GB ab). Der Dienst bekommt den Ordner per `--pack-dir` und liest ihn nur; aus ihm kommen `tiles/*.pmtiles` und `data/suche_geo.json`, sonst nichts. Die Basiskarte (rund 1,5 GB) bleibt Download beim ersten Start, weil sie mit dem Rest die 2-GB-Grenze des NSIS-Installers sprengt.

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
