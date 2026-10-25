# 11 Darstellung und Skins: wie Landblick zeichnet

Grundlage für Themen und Skins (Landblick, Alte Karte, weitere folgen). Beschreibt, wo Farben, Formen, Schriften und Zeichen herkommen, in welcher Reihenfolge die Karte aufgebaut wird und an welchen Stellen die „Alte Karte“ heute eingreift. Stand: Version 1.0.0-beta.1 plus Änderungen auf `feat/kartenpakete`.

Vorweg: Es gibt keine Stildatei, weder `style.json` noch XML. Der MapLibre-Stil wird zur Laufzeit in JavaScript zusammengesetzt. XML im weiteren Sinn sind nur die SVG-Glyphen unter `web/icons/` (Abschnitt 11.6). Alles, was sonst „Darstellung“ ist, steht in JS-Konstanten und in drei CSS-Dateien.

---

## 11.1 Beispiele zuerst

**Wald dunkler machen (beide Ansichten getrennt).** `web/js/lage/stil.js`, Konstante `LAND`:

```js
export const LAND = {
  light: { forest: ['#5f9f5b', 0.55], ... },   // [Farbe, Deckkraft]
  dark:  { forest: ['#245234', 0.6],  ... },
};
```

Die Zeichenerklärung (`fillFlaechenLegenden` in `basiskarte.js`) liest dieselbe Konstante, die Legende folgt also von selbst. Die Signatur (Baumkronen) hat ihre eigene Tinte in `web/js/icons.js`, `LAND_INK`.

**Hauptstraßen umfärben.** `stil.js`: `ROAD_FILL`, `ROAD_FILL_MINOR`, `AUTOBAHN_FILL`. Breiten: `ROAD_W`, `LINK_W`. Die Kontur ist immer `#000000` (in `mainRoad()`).

**Bedienoberfläche umfärben.** Nur Tokens in `web/css/tokens.css`. Hell steht in `:root`, Dunkel überschreibt in `:root[data-ansicht="dunkel"]`. Beide Blöcke zusammen ändern, sonst kippt eine Ansicht.

**Zeichnung der Klippen ändern.** `stil.js`, `cliffLayers()`. Eine Funktion zeichnet beide Quellen (Wandkacheln aus dem Gelände und OSM-Linien), siehe 11.3.4.

**Ansicht prüfen, ohne zu raten.** Im Browser `#debug` an die Adresse, Seite neu laden. Dann liefert der Prüfzugang (`web/js/lage/debug.js`) die tatsächliche Layer-Reihenfolge und Paint-Werte:

```js
document.documentElement.dataset.debugIn = JSON.stringify({ order: '^bm-land-cliff', paint: [['bm-land-cliff', 'line-width']] });
document.dispatchEvent(new Event('osint-debug'));
JSON.parse(document.documentElement.dataset.debugOut);
```

---

## 11.2 Zwei Schalter, zwei Achsen

| Achse | Wert | Wo gespeichert | Wirkung |
|---|---|---|---|
| Ansicht | hell (Grundeinstellung) / dunkel | `html[data-ansicht="dunkel"]`, gesetzt von `util.js` (`initTheme`) | CSS-Tokens, Kartenfarben `light`/`dark`, Protomaps-Flavor `grayscale`/`dark` |
| Darstellung (Skin) | `landblick` / `alte-karte` | `state.layers.medieval` (bool) und `html[data-karte="mittelalter"]` | Alternative Karte um 1450, eigene Farben, Zeichen, Schrift, Bedienelemente |

Die beiden sind nicht unabhängig: Die Alte Karte kennt kein Dunkel. In `applyBasemap()` gilt `flavor = !med && dunkel ? 'dark' : 'grayscale'`. Der Skin hat Vorrang.

**Ablauf beim Umschalten.**

1. Die Ansicht: Knopf „Dunkel“ → `html.dataset.ansicht` → Ereignis `ansicht` → `recolor()` (`basiskarte.js`).
2. Der Skin: Radio `input[name="skin"]` (Menü „Darstellung“, `index.html`) → `state.layers.medieval` → `applyLayerFilters(); render(); syncGroups(); syncMedieval()` (`lage/ebenen.js`). `syncMedieval` schaltet die Landmarken-Ebenen mit um und ruft `recolor()`.
3. `recolor()`: registriert die Zeichen neu (`registerIcons`, bei Alter Karte zusätzlich `registerMedieval`), setzt Hintergrund und Ereignisfarben, ruft `applyBasemap()`.
4. `applyBasemap()` entfernt alle Layer mit Präfix `bm-` und baut sie neu, siehe 11.3.

Der Kartenstil wird also bei jedem Wechsel komplett neu aufgebaut. Daten-Quellen (`basemap`, `klippen`, `hang`, `dem`, `contours`, `anbau` …) bleiben stehen, nur die Layer darauf wechseln.

---

## 11.3 Der Kartenstil

### 11.3.1 Aufbau in `applyBasemap()` (`web/js/lage/basiskarte.js`)

```
protomaps layers('basemap', flavor, {lang:'de'})      69 Layer aus vendor/protomaps-basemaps
  → LABEL_SKIP-Filter                                  Länder, Regionen, POIs, Schilder des Stils raus
  → mainRoad()                                         Hauptstraßen: Farbe, Breite, schwarze Kontur
  → labelsAndBuildings(dark)                           Schrift, Gebäude, Ortsnamen, Gewässernamen
  → ortsnamenUebersicht()                              Zoom 5–9: RLP alle Orte, außerhalb nur Großstädte
  → Quelle wechseln: Gebäude aus basemap-geb / -core
splice hinter 'landuse_park':  hangLayers + landUseLayers
splice vor erster Beschriftung: cliffLayers
waterEdges()                                           Säume um Gewässer, Reihenfolge der Wasserlayer
push peakLayers()                                      Gipfel obenauf
[Alte Karte] medievalize(styled)                       Farben, Muster, Weglassen, Schrift ersetzen
[Ring]       Gebäude-Ebenen aus basemap-ring
[Flow]       flow.layers()                             Wasserbewegung über den Gewässerlinien
map.addLayer({...l, id:'bm-'+l.id}, before)            alles unter dem Anker 'before' (baseAnchor())
signLayers()                                           Straßenschilder (nur wenn state.signsOk)
moveLayer(...)                                         Routen, Infrastruktur, Landmarken, air-dim wieder nach oben
paintWater / paintStops / paintNature / applyBaseToggles / applyRelief / placeLgb
```

Alle Basis-Layer heißen `bm-<id>`. `applyBaseToggles()` schaltet sie über Namensmuster mit den Schaltern der Ebenenliste (`state.layers.*`) sichtbar oder unsichtbar. Wer einen Layer neu anlegt, muss sein Muster dort eintragen, sonst bleibt er immer an.

### 11.3.2 Reihenfolge von unten nach oben (gemessen am laufenden Stand)

| Gruppe | Layer (Auswahl) | Gebaut in |
|---|---|---|
| Grund | `bg`, `bm-background`, `bm-earth`, `bm-landuse_park` | Kern (`karte.js`), Protomaps |
| Hangneigung | `bm-land-hang-ab15/25/35` | `hangLayers` (stil.js) |
| Höhenfärbung | `relief-color` | `relief.js` (`buildRelief`) |
| Vegetation | `bm-land-forest`, `-meadow`, `-grass`, `-scrub`, `-heath`, `-farmland`, `-orchard`, `-vineyard`, `-allotment`, `-wetland`, `-rock`, `-sand`, `-cemetery`, je mit Zusatz `-pat` (Signatur) | `landUseLayers` |
| Schutz, Militär, Grenzen | `bm-land-protected-*`, `bm-land-military-*`, `bm-land-bound-*`, `bm-land-bound-region-rlp` (rote Landesgrenze mit Verlauf `glow0..4`) | `landUseLayers`, `rlpBorderLayers` |
| Steinbruch | `bm-land-quarry-dot/-label` | `landUseLayers` |
| weitere Landnutzung | `bm-landuse_*` (Krankenhaus, Industrie, Schule, Flughafen …) | Protomaps |
| Gewässer | `bm-water_*_casing`, `bm-water_edge`, `relief-hill` (Schummerung), `bm-water`, `bm-water_stream/river` | Protomaps, `waterEdges`, `paintWater` |
| Wasserbewegung | `bm-flow-*` | `fluss.js` |
| Tunnel, Gebäude | `bm-roads_tunnels_*`, `bm-buildings` | Protomaps, `buildingFill` |
| Höhenlinien | `relief-contour` | `relief.js` |
| Straßen | `bm-roads_minor…highway` mit Kontur, `bm-roads_rail`, Brücken | Protomaps, `mainRoad` |
| Klippen | `bm-land-cliff-band`, `-cliff`, `-cliff-teeth`, `-cliff-wand-dgm`, `-cliff-schraffur-dgm`, `-cliff-dgm` | `cliffLayers` |
| Beschriftung | `bm-address_label`, Gewässernamen, Straßennamen, Ortsnamen, Gipfel, Schilder | Protomaps, `peakLayers`, `signLayers` |
| Datenebenen | `air-dim`, `radar`, `blitz`, `radius-fill`, `ev-*` (Ereignisse), `dichte-*`, `air-*`, `st-*`, `env-*`, `wxst-label`, `tank-*` | `lage/*.js`, `orte.js` |
| Rand | `relief-contour-label`, `vig`, `vig-bild` (Vignette) | `relief.js`, `vignette.js` |

Regel dahinter: Gelände und Fläche unten, Linien (Wasser, Straßen) in der Mitte, Klippen über allem Gelände, Text oben, Fachdaten über der Basiskarte. Hangneigung liegt bewusst unter der Vegetation, Klippen über beiden.

### 11.3.3 Farbquellen: wo steht was

Alle Werte sind feste Hex-/rgba-Strings in JS. Es gibt keine gemeinsame Palette, die Skin-Wechsel zentral steuert. Jede Datei hat ihre eigene Tabelle mit den Schlüsseln `light` / `dark` (und teils `med`).

| Was | Konstante | Datei |
|---|---|---|
| Vegetation (Farbe, Deckkraft) | `LAND`, `GREEN` | `lage/stil.js` |
| Signatur-Tinte der Vegetation | `LAND_INK` | `icons.js` |
| Hauptstraßen, Schilder | `ROAD_FILL`, `ROAD_FILL_MINOR`, `AUTOBAHN_FILL`, `SIGNS` | `lage/stil.js`, `icons.js` |
| Schrift, Saum, Gewässerschrift | `INK`, `HALO`, `WATER_INK`, `HOUSENO` | `lage/stil.js` |
| Gewässer | `paintWater` (Fläche), `WATER_EDGE` (Saum) | `lage/basiskarte.js`, `stil.js` |
| Gebäude nach Funktion | `BUILDING`, `BUILDING_KLASSEN`, `buildingFill()` | `gebaeude-farben.js` (auch von der Legende und `tests/js` genutzt) |
| Klippen | `CLIFF`, `CLIFF_SCREE`, Wandfläche in `cliffLayers` | `lage/stil.js` |
| Hangneigung | `col` in `hangLayers` | `lage/stil.js` |
| Schutzgebiete, Militär, Grenzen | `PROTECTED`, `PARK_NAT`, `MILITARY`, `BOUND_COLOR`, `RLP_RED`, `RLP_GLOW` | `lage/stil.js` |
| Höhenstufen, Schummerung, Höhenlinien | `RAMP`, `STYLE` (+ `MED_RAMP`, `MED_STYLE`) | `relief.js` |
| Wasserbewegung | `COLORS` (light/dark/med) | `fluss.js` |
| Landmarken, Gipfel | `NATURE_COLOR`, `NATURE_CHIP` | `lage/natur.js`, `icons.js` |
| Temperaturskala, Militär-Marker | `TEMP_COLOURS`, `MIL_COLOUR` | `icons.js` |
| Meldungsstufen (kritisch … Info) | `palette()`, `sevColor()` | `lage/farben.js` (liest CSS-Tokens per `cssColor`) |
| Alte Karte, Karte | `MED`, `MED_COLORS`, `MED_LAND`, `MED_ICON_STYLE` | `lage/mittelalter.js` |
| Alte Karte, Zeichnungen | `MED` (zweiter Satz), `MED_INK/PAPER/STONE/ROOF/WATER` | `medieval.js`, `icons.js` |

Einzige Brücke zwischen CSS und Karte ist `palette()` in `lage/farben.js`: Es liest `--surface`, `--border-strong`, `--fg`, `--brand-red-600`, `--sys-yellow`, `--sys-blue`, `--accent`, `--bg-elevated` aus dem laufenden CSS. Meldungsfarben (Ereignisse) folgen damit den Tokens, Flächenfarben der Karte nicht.

### 11.3.4 Klippen als Beispiel für „eine Zeichnung, zwei Quellen“

`cliffLayers(k, dark, ticks, dgm)` in `stil.js`. `k` ist `light`, `dark` oder `med`.

* Wände aus dem Gelände (Quelle `klippen`, Vektorkacheln Zoom 13, Ebenen `wand`, `kante`, `schraffur`, Attribut `drop` = Wandhöhe in m): Fläche mit 20 % Deckkraft, Fallstriche, Oberkante in Breite nach Wandhöhe.
* OSM-Klippen (Quelle `basemap`, Ebene `earth`, `kind=cliff`): Wandband rechts der Linie, Oberkante wie eine 10-m-Wand, Fallstriche aus dem Bild `cliff-stroke`. Breite, Strichlänge und -abstand wachsen mit dem Zoom (Meter statt Pixel).
* Wo die Kacheln liegen, entfallen die OSM-Linien. Grundlage ist die Kachelabdeckung (`web/js/lage/klippen-umriss.js`, erzeugt von `tools/build_klippen_umriss.py`), nicht die Landesgrenze. Nach jedem Neubau der Kacheln neu erzeugen.

### 11.3.5 Die Alte Karte: wie der Skin heute eingreift

`medievalize(styled)` (`lage/mittelalter.js`) arbeitet als Nachbearbeitung auf der fertigen Layer-Liste:

1. verwirft per `MED_DROP` alles Moderne (Bahn, Grenzen, Signaturen, Hausnummern, Straßenkonturen, Flughäfen …),
2. ersetzt Farben (`MED.bg`, `MED.paper`, `MED.water`, `MED.road` …),
3. ersetzt Straßen durch gestrichelte oder dünne Wege,
4. legt Muster über Flächen (`patternLayer`) und Wasser (`waterPatternLayer`),
5. setzt Gebäude auf ein Füllmuster (`med-bldg`),
6. ersetzt die Schrift durch „Grenze Gotisch“ (`MED_FONT`), mit Retina-Zuschlag,
7. fügt Hügel-, Wellen- und Siedlungszeichen (`extraLayers`) und Tiere (`faunaLayers`, `fauna.js`) ein.

Der Basis-Flavor kommt von `medFlavor()` (Protomaps-Flavor `grayscale`, mit Pergamentfarben überschrieben).

Zusätzlich verzweigt Code an anderen Stellen auf `state.layers.medieval`: `relief.js` (eigene Rampe und Schummerung), `fluss.js` (eigene Farben), `licht.js` (Wasserglitzern), `lage/orte.js` (Infrastruktur, Wanderwege), `lage/natur.js` (Landmarken), `lage/wetterkarte.js` (Legenden), `icons.js` (Zeichensatz), `lage/ebenen.js`. Das sind rund 90 Fundstellen in 16 Dateien (Importe eingerechnet). Die Windrose (`windrose()` in `lage/mittelalter.js`) ist ein SVG, das per DOM-Code gebaut wird.

---

## 11.4 Zeichen und Bilder

Die Karte benutzt zwei Arten von Zeichen. Beide werden zur Laufzeit als Bild in MapLibre registriert (`map.addImage`), nichts davon liegt als fertiges Sprite vor.

| Gruppe | Bildnamen | Quelle | Datei |
|---|---|---|---|
| Meldungszeichen | `ico-<symbol>-<stufe>` (Verkehr als Plakette `chip`, sonst freies Zeichen `bare`), Haltestellen `stop-bahn`, `stop-tanken` | SVG-Glyph, getönt per Canvas | `icons.js` (`registerIcons`, `chip`, `bare`) |
| Flugzeuge, Hubschrauber | `plane-<stufe>`, `heli-<stufe>`, militärisch `mplane-*`, `mheli-*` | SVG-Glyph | `icons.js` (`plane`, `badge`) |
| Temperaturfelder | `wx-<k>` | 33 Farbfelder | `icons.js` (`TEMP_COLOURS`) |
| Landmarken | `nat-<Art>` | SVG-Glyph auf Artfarbe | `icons.js` (`NATURE_CHIP`) |
| Straßenschilder | `sign-autobahn/-bundes/-land` | Canvas, dehnbar | `icons.js` (`registerSigns`) |
| Vegetationssignaturen | `lp-<klasse>-<light|dark>` | Canvas, 24 × 24 | `icons.js` (`LAND_DRAW`, `registerLandPatterns`) |
| Klippenstrich | `cliff-stroke` (SDF, Farbe per `icon-color`) | Canvas | `icons.js` |
| Gipfeldreieck | `peak-tri` (SDF) | Canvas | `icons.js` |
| Zeichen der Alten Karte | `med-<Art>`, `med-bldg`, `med-peak`, Hügel, Wellen, Siedlungen, Tiere | eigene Canvas-Zeichnung | `icons.js` (`medDraw`, `registerMedieval`), `medieval.js` (`registerMedievalPatterns`, `registerFauna`) |
| Wasserbewegung | Wellen, Pfeile, Striche | Canvas-Einzelbilder | `fluss.js` |

SDF-Bilder (`sdf: true`) nehmen ihre Farbe aus dem Layer (`icon-color`). Für Skins ist das der bequeme Weg: eine Form, Farbe im Stil. Die übrigen Bilder tragen ihre Farbe fest und müssen für jede Darstellung neu gezeichnet werden (`recolor()` tut das schon für Hell/Dunkel und Alte Karte).

---

## 11.5 Schrift

* Karte: „Noto Sans Regular“ (Glyph-PBF unter `web/fonts/`, OFL). Der Stil hat eine einzige Schrift; `labelsAndBuildings()` ersetzt jede `text-font` darauf.
* Alte Karte: „Grenze Gotisch Regular“ (nur Glyph-PBF für die Karte, `grenze-gotisch.woff` für die Oberfläche, OFL).
* Oberfläche: Systemschriften, definiert in `tokens.css` (`--font-sans`, `--font-display`, `--font-mono`).
* Keine externen Schriften, keine CDNs (Content-Security-Policy `font-src 'self'`).

Ortsnamen: Größe nach Siedlungsrang (`population_rank` der Kacheln, 1 bis 9) von 8 bis 12 pt, unabhängig vom Zoom (`SIZE_MIN_PX`, `SIZE_MAX_PX`).

---

## 11.6 CSS und SVG der Oberfläche

### 11.6.1 Dateien

| Datei | Inhalt |
|---|---|
| `web/css/tokens.css` | nur Tokens: Marken-, System-, Status-Farben (OKLCH), semantische Rollen, Typografie, Radien, Abstände, Schatten, Bewegung, „Liquid Glass“-Materialien. Herkunft: Design System v5.1 (`ctw-design-system-v5.1.html` im Projekt). Hell in `:root`, Dunkel in `:root[data-ansicht="dunkel"]`. Kein `prefers-color-scheme`, die Ansicht wählt der Nutzer. |
| `web/css/app.css` | Oberfläche und Kartenhülle, ca. 725 Zeilen, gegliedert durch Kommentare (Kopf, Warnband, Karte, Seitenleiste, Tabellen, Plaketten, Legenden, Glas-Variante ab Zeile 351, Alte-Karte-Blöcke ab Zeile 585) |
| `web/css/icons.css` | Klassen `.ico-*`: SVG-Datei als Maske (`mask`), Farbe folgt `currentColor` |
| `web/vendor/maplibre-gl/maplibre-gl.css` | Karten-Steuerelemente (nicht ändern; überschrieben wird in `app.css`) |

Das Handbuch (`docs/handbuch/handbuch.css`) ist ein eigenes Blatt und gehört nicht zur App.

### 11.6.2 Bausteine

* Tokens: Farben folgen Rollen (`--bg`, `--surface`, `--fg`, `--fg-muted`, `--accent`, `--danger`, `--border`), nicht Farbnamen. Neue Oberflächenfarben gehören als Rolle in `tokens.css`, nicht als Hex in `app.css`.
* Materialien: `--glass-*`, `--material-*` für schwebende Flächen über der Karte (Ebenenmenü, Detailfeld, Legenden).
* Skin-Schalter im CSS: `html[data-karte="mittelalter"] …` in `app.css`. 32 Selektoren, 59 feste Hex-Werte (Pergament `#efe0b0`, Tinte `#3a2614`, Linien `#7a5530`). Sie überschreiben Zoomknöpfe, Maßstab, Popups, Legenden, Ebenenmenü, Detailfeld, Reiter.
* Hell/Dunkel im CSS: `html[data-ansicht="dunkel"]` überschreibt Token und einzelne Selektoren (Logo, Stufenfarben).

### 11.6.3 SVG

* `web/icons/*.svg`: Symbole der Oberfläche und Karte (uxwing, freie Nutzung ohne Namensnennung, aber nicht weiterverbreiten; Lizenz und Ausnahmen in `web/icons/README.txt`; `tanken.svg` ist eine eigene Zeichnung). Diese Dateien liegen nicht im Repository, sie holt `tools/fetch_icons.sh`.
* Dieselben Dateien dienen zweimal: in der Oberfläche als CSS-Maske (`icons.css`), in der Karte als Quelle für die Canvas-Bilder (`registerIcons`). Eine Änderung an einem SVG wirkt in beiden.
* Per DOM-Code gebaute SVG: nur die Windrose der Alten Karte (`lage/mittelalter.js`).
* Das Logo (`web/brand/`) kommt als PNG in hell und dunkel; die Umschaltung läuft über `.logo-hell` / `.logo-dunkel` in `app.css`.

### 11.6.4 Grenzen durch die Content-Security-Policy (`index.html`)

`default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'`. Daraus folgt für jedes Thema:

* kein Inline-Style im Markup (Farbfelder werden per CSSOM gesetzt, siehe `legendZeile()`),
* keine externen Schriften, Skripte oder Stylesheets,
* Bilder nur von `self`, `data:`, `blob:` und den freigegebenen LGB-Diensten,
* ein Skin darf keine Ressourcen von fremden Hosts laden.

---

## 11.7 Befund für den Skin-Support

Das ist die Ist-Beschreibung, daraus abgeleitet die Stellen, die ein Skin-System anfassen muss. Entschieden ist noch nichts.

1. **Skin ist ein Boolean.** `state.layers.medieval` ist die einzige Unterscheidung. Mit drei Darstellungen braucht es einen Namen (`state.skin`), aus dem `medieval` abgeleitet wird oder ganz entfällt.
2. **Farben liegen verteilt.** 13 Dateien mit eigenen `light`/`dark`-Tabellen (Abschnitt 11.3.3). Ein Skin müsste in jeder einen dritten Schlüssel bekommen. Besser wäre eine Palette je Skin, die diese Tabellen füllt.
3. **Der Skin greift als Nachbearbeitung ein** (`medievalize`), nicht als Palette. Das funktioniert für eine radikal andere Karte (Pergament, andere Zeichen), ist aber für „gleiche Karte, andere Farben“ (zum Beispiel Hochkontrast oder Nacht) zu schwer.
4. **Oberfläche und Karte schalten getrennt:** Karte über `data-karte`, Farbschema über `data-ansicht`. Ein neues Thema braucht beides, mindestens ein weiteres Attribut und CSS-Blöcke wie die der Alten Karte (die heute feste Hex-Werte tragen statt Tokens).
5. **Bilder tragen Farbe fest** (außer SDF). Jedes Thema, das Farben ändert, muss `registerIcons` und die Signaturen neu zeichnen. Der Weg steht in `recolor()`.
6. **Anker für Tests:** `tests/js/*.test.mjs` prüfen Layerlisten und Farbausdrücke (`cliffLayers`, `buildingFill`, `ortsnamen`). Ein Skin-System sollte diese Tests mit je einem Fall pro Darstellung erweitern.

Vorschlag in einem Satz: eine Skin-Beschreibung als Objekt (`id`, `name`, `flavor`, `palette`, `font`, `symbols`, `css`-Attribut, `postprocess`), das `applyBasemap`, `recolor` und die Legenden lesen, statt `if (med)` an so vielen Stellen. Landblick und Alte Karte wären dann die ersten zwei Einträge.

---

## 11.8 Rezepte

**Neuen Layer in die Basiskarte.** In der passenden Funktion in `stil.js` mit `id` ohne Präfix anlegen. Reihenfolge entscheidet der `splice` in `applyBasemap()`. Muster in `applyBaseToggles()` ergänzen. Für die Alte Karte entscheiden: weglassen (`MED_DROP`), umfärben (in `medievalize`) oder unverändert lassen.

**Neues Zeichen.** SVG nach `web/icons/` (und in `tools/fetch_icons.sh`/README eintragen), in `icons.js` registrieren, in `icons.css` die Klasse `.ico-<name>` ergänzen, wenn die Oberfläche es braucht.

**Farbe für Hell und Dunkel prüfen.** Immer beide Werte setzen. Prüfen im Browser mit `#debug` und der Karte in beiden Ansichten, danach `node --test tests/js/*.test.mjs` und `python -m pytest -q`.

**Zoom-Ausdrücke.** MapLibre erlaubt `['zoom']` nur als Eingabe des obersten `interpolate`/`step`. Skalieren geht über die Stützwerte (`scaled()`, `scaleSize()`, `widen()` in `stil.js` und `mittelalter.js`), nicht über Verschachteln.

## 11.9 Skins: Aufbau und neue Darstellung anlegen

`web/js/lage/skins.js` führt die Liste `SKINS`. Landblick (keine Nachbearbeitung) und Alte Karte (`medievalize`) bleiben, was sie waren. Jeder weitere Skin ist eine Palette mit den Schlüsseln `bg`, `earth`, `water`, `edge`, `waterInk`, `ink`, `halo`, `forest`, `green`, `scrub`, `farm`, `wet`, `rock`, `landOp`, `bld` und `roads` (je Klasse `[Füllung, Kontur]`), jeweils für `light` und `dark`.

`applyBasemap()` baut die Layer wie gewohnt und ruft danach `skinize(styled, palette, { patterns })`. Das Umfärben läuft über die Layer-IDs; Geometrie, Schalter und Datenebenen bleiben unberührt. Wasserfarbe für `paintWater` und Licht kommt aus derselben Palette. Der Zustand steht in `state.skin`, die Auswahl in `html[data-skin]`; `state.layers.medieval` ist daraus abgeleitet.

Neue Darstellung: Eintrag in `SKINS` mit `id`, `name`, `hinweis` und `tint`, Test in `tests/js/skins.test.mjs` läuft ohne weitere Anpassung. Namen sind Orte, keine Marken. Nicht von der Palette erfasst sind Höhenfärbung (Relief), Wetter- und Datenebenen, Schilder und Zeichen; sie folgen weiter hell/dunkel.

Palette-Zusatz für feine Linien: `inkRoads` (Faktor der Linienbreite, Konturen aus, Nebenwege gestrichelt) und `spacing` (Sperrung der Ortsnamen).

### Zwei Methoden

**Farbpalette (`tint`).** Tauscht nur Farben der fertigen Layerliste; Texturen, Symbole und Schrift bleiben die von Landblick. Dafür gibt es hell und dunkel. Beispiel: Mountain View.

**Zeichensatz (`art`).** Tauscht Texturen und Symbole: Flächenmuster (Baumkronen, Furchen, Schilf), Hügel-, Wellen- und Siedlungszeichen, Gebäudeschraffur, Zeichen der Infrastruktur, Schrift und Zierde (Titelschild, Windrose, Fabelwesen). Die Zeichnungen entstehen auf Canvas und lesen ihre Farben aus Objekten (`MED` in `medieval.js` und `mittelalter.js`, `PIG` in `pigmente.js`, `MED_COLORS`, `MED_LAND`, `MED_RAMP`, `MED_STYLE`, `CLIFF`). `applyArt()` in `lage/zeichensatz.js` schreibt die Werte des gewählten Satzes dorthin und zeichnet Muster und Symbole mit gleichen Bildnamen neu; danach läuft `recolor()`. Die Daten eines Satzes stehen in `lage/zeichensaetze.js` (`ARTS`); ein neuer Satz braucht dieselben Schlüssel wie `alte-karte` (der Test prüft das). Zeichensätze kennen nur hell. Neue Zeichenformen (andere Bäume, andere Häuser) brauchen eine Parameterisierung der Zeichenfunktionen in `medieval.js`; bisher ändern Sätze Farben, Schrift und Zierde, die Formen sind noch die der Alten Karte.

### 11.9.1 Drei Achsen und „Anpassen“

Das Menü „Darstellung“ hat drei Auswahlen: Farb-Schema (`state.schema`, Paletten aus `skins.js`), Symbole (`state.symbole`: Grundzeichnung, Alte Karte, Oxford) und Schrift (`schrift.js`). `effektiverSkin()` macht aus Schema und Symbolen den einen Skin `state.skin`, den der übrige Code kennt; ein Symbolsatz hat Vorrang, weil er seine Farben mitbringt (das Schema ist dann gesperrt).

„Anpassen …“ öffnet ein Formular (`darstellung.js`, reine Funktionen in `anpassen.js`). Es legt Farbüberschreibungen (nur `#rrggbb`) und Schalter auf den gewählten Ausgang und baut daraus den Skin `eigen`: bei Paletten eine Kopie je Ansicht (hell und dunkel getrennt, Konturen aus der Füllung abgeleitet), bei Zeichensätzen eine Kopie unter `ARTS.eigen`. Wer ein anderes Schema oder anderes Symbol wählt, beginnt neu. Es gibt keinen Speicher: nach dem Neuladen gilt wieder die Grundzeichnung.

