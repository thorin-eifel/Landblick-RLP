# Freizeit in Rheinland-Pfalz: Quellen und Verzeichnisse

Stand der Recherche: 2026-10-16. Zweck: klären, woher das Menü *Freizeit* seine Daten bekommen kann (Übernachten, Camping, Aktivitäten, Routen, Rast und Baden), unter welcher Lizenz und mit welchem Zugang. Es ist noch nichts eingebaut. Zeilen, die ich nicht selbst gelesen habe, sind als **ungeprüft** markiert.

Maßstab sind die Projektregeln: offene Lizenz, Quelle sichtbar, keine Personen statt Ereignisse, ohne Quelle läuft kein Collector (`sources.yaml`).

## Kurzfassung

1. **Vollständig und offen gibt es für ganz RLP nur OpenStreetMap** (ODbL). Hotels, Pensionen, Hostels, Ferienunterkünfte, Campingplätze, Wohnmobilstellplätze, Hütten, Museen, Zoos, Freizeitparks, Schwimmbäder und Routen liegen dort mit festen Tags vor. Die Pipeline nutzt die Overpass API schon für `osm_natur`, `osm_infra` und `osm_routen`; ein vierter Sammler `osm_freizeit` passt in dieselbe Bauart.
2. **Die amtliche Tourismusdatenbank ist nicht offen im Sinn von „herunterladen“.** Die Rheinland-Pfalz Tourismus GmbH (RPT) führt Unterkünfte, POIs, Touren und Veranstaltungen im *DataHub RLP*. Zugang gibt es nach Antrag; Partner außerhalb von RLP bekommen in der Regel nur Daten mit CC-Lizenz. Das ist ein Weg für später, mit Antrag und Wartezeit.
3. **Luxemburg ist gut bedient:** Luxembourg for Tourism liefert eine nationale POI-Datenbank mit Unterkünften als GeoPackage unter CC BY 4.0, monatlich aktualisiert.
4. **Routen:** Fern- und Regionalrouten kommen schon aus OSM. Der Tourenplaner der RPT (Outdooractive) bietet GPS-Download je Tour, aber weder Schnittstelle noch Datenlizenz; als Quelle ungeeignet.
5. **Datenschutz ist bei Unterkünften der heikle Punkt** (Abschnitt „Entscheidung nötig“).

## Quellen nach Bereich

### Übernachten (Hotels, Pensionen, Ferienunterkünfte, Hütten)

| Quelle | Inhalt | Zugang | Lizenz | Bewertung |
|---|---|---|---|---|
| **OpenStreetMap** | `tourism=hotel`, `guest_house`, `hostel`, `motel`, `apartment`, `chalet`, `alpine_hut`, `wilderness_hut` | Overpass API, wöchentlich, wie die bestehenden OSM-Sammler | ODbL 1.0, Namensnennung „© OpenStreetMap-Mitwirkende“ | **Empfohlen.** Unvollständig (Mitwirkende pflegen es), Qualität schwankt je Ort. |
| **DataHub RLP** (RPT, Software dataCycle, Quelle Deskline®) | Unterkünfte mit Unterkunftsart, verknüpft mit „Reisen für Alle“ | Zugang nur nach Antrag über `data.rlp-tourismus.de`; JSON-Schnittstelle, Doku unter `data.rlp-tourismus.de/docs/api`; Nutzung kostenfrei | Für Partner außerhalb RLP in der Regel nur CC-Daten (CC0, CC BY, CC BY-SA) | **Später, mit Antrag.** Besser gepflegt als OSM, aber nur der Teil mit offener Lizenz. Offener Punkt: wie groß dieser Teil ist. |
| **DZT Knowledge Graph** (`open-data-germany.org`) | Die Daten der RPT werden per Push an die Deutsche Zentrale für Tourismus gegeben, wenn offene CC-Lizenz und Qualitätskriterien erfüllt sind | Abruf über Antrag auf `open-data-germany.org` | CC0, CC BY, CC BY-SA | **Alternative zum DataHub**, bundesweit einheitlich. Zugang und Schnittstelle nicht selbst geprüft. |
| **Luxembourg for Tourism** (data.public.lu) | Nationale POI-Datenbank: Kultur, Natur, Freizeit, Unterkünfte, Restaurants | Direkter Download `lft-poi.gpkg` (17,4 MB), ohne Antrag | **CC BY 4.0** | **Empfohlen für Luxemburg**, Struktur der Datei ist nicht dokumentiert (erst ansehen, dann bauen). |
| Buchungsportale (Booking, Airbnb, Camping- und Stellplatzportale) | – | – | keine offene Lizenz | **Nicht verwenden.** Kein Scraping. |

### Camping und Stellplätze

| Quelle | Inhalt | Lizenz | Bewertung |
|---|---|---|---|
| **OpenStreetMap** | `tourism=camp_site` (Zeltplatz), `tourism=caravan_site` (Wohnmobilstellplatz, Caravanplatz) | ODbL | **Empfohlen.** Einzige offene Gesamtquelle. |
| DataHub RLP / DZT | Campingplätze sind Unterkunftsarten in Deskline® | CC, nach Antrag | Siehe oben. |
| Luxembourg for Tourism | Im POI-Bestand enthalten; zusätzlich gibt es in data.public.lu ein Programm „Destination Camper Park(ing)“ (Wohnmobilstellplätze, Leitfaden als PDF) | CC BY 4.0 für die POI-Datei | Dataset „Destination Camper Park(ing)“ nur dem Titel nach gesehen, **ungeprüft**. |
| Stellplatz- und Campingportale | – | keine offene Lizenz | **Nicht verwenden.** |

Ein amtliches, offen lizenziertes Verzeichnis der Campingplätze in RLP habe ich nicht gefunden.

### Aktivitäten und Sehenswertes

| Quelle | Inhalt | Lizenz | Bewertung |
|---|---|---|---|
| **OpenStreetMap** | `tourism=attraction`, `museum`, `gallery`, `zoo`, `theme_park`, `aquarium`, `viewpoint`; dazu `leisure=swimming_pool`, `water_park`, `miniature_golf`, `sports_centre`; `sport=climbing` und weitere | ODbL | **Empfohlen**, nach Gruppen schaltbar. Aussichtspunkte sind bereits in `osm_natur`. |
| DataHub RLP | POIs aus Deskline®, Standorte der Touristischen Unterrichtungstafeln, Erlebnisführer-Texte (Maqnify), Veranstaltungen, Gastronomie | CC, nach Antrag | Später. |
| Luxembourg for Tourism | siehe oben | CC BY 4.0 | Empfohlen für Luxemburg. |
| Statistik „Gäste und Übernachtungen im Tourismus“ (open.rlp.de, Statistisches Landesamt) | Monatliche Zahlen, **keine Standorte** | Lizenz **ungeprüft** | Nur Titel gesehen. Als Hintergrundzahl denkbar, nicht für die Karte. |

### Routen (Wandern, Radfahren)

| Quelle | Inhalt | Zugang | Lizenz | Bewertung |
|---|---|---|---|---|
| **OpenStreetMap** (`route=hiking`, `foot`, `bicycle`, `mtb`) | Fern-, National- und Regionalrouten, schon im Betrieb (`osm_routen`) | Overpass | ODbL | **Bleibt.** Mögliche Ausbau-Schritte: Rundwege, Mountainbike, Reitrouten, Premiumwege (nach Bedarf, Datenmenge messen). |
| **Waymarked Trails** | Darstellung von OSM-Routen als Kartenebene | – | Software GPL v3; für Kacheln und Daten fand ich keine Angabe | **Nicht als Quelle**, wir lesen die OSM-Relationen selbst. Höchstens als Link („Route ansehen“). |
| **Tourenplaner RLP** (RPT mit Outdooractive) | Prädikatswege (Eifelsteig, Moselsteig, Rheinsteig), Kurz- und Rundtouren | GPS-Download und PDF je Tour für Endnutzer | **keine Angabe zu API oder Lizenz** | **Nicht verwenden.** Wenn überhaupt: Link auf die Tour. Für Daten wäre ein Antrag bei der RPT nötig (DataHub liefert Touren aus Outdooractive.business). |
| **DataHub RLP** | Touren aus Outdooractive.business, filterbar nach Kategorie | Antrag | CC, soweit lizenziert | Später. Umfang des CC-Teils offen. |
| **LBM Radverkehrsnetz** | ca. 16.000 km Netz, rund 8.500 km beschildert (HBR) | Seite nennt weder Download noch WMS/WFS noch Lizenz | **ungeklärt** | **Rückfrage beim LBM nötig**, ob es offene Geodaten gibt. Ohne Antwort nicht einbauen. |
| **Premiumwanderwege Saarland** (GDI-SL, Tourismuszentrale des Saarlandes) | Wanderwege im Saarland (Ausdehnung 6,38–7,40 O, 49,12–49,65 N) | Metadatensatz bei GDI-DE; Dienst-URL nicht belegt | **CC BY 4.0**, Vermerk „© GDI-SL (Jahr)“ | Randgebiet, liegt in den 80 km hinter der Landesgrenze. Nicht RLP. Dienst erst suchen. |
| **LANIS** (Naturschutzverwaltung RLP) und Geodatendienste des Landesamts für Umwelt | Schutzgebiete, Naturparks, Erholung? | WMS/WFS | **ungeprüft** | Nur gefunden, nicht gelesen. Schutzgebiete sind schon im Menü Geographie. |

### Rast und Baden

Bleibt bei OSM (`osm_infra`: Rastplätze, Schutzhütten, Badestellen). Offen lizenzierte Alternativen habe ich nicht gefunden. Badegewässer-Qualität (Landesamt für Umwelt, EU-Badegewässer) wäre ein eigenes Ereignismodul und gehört eher ins Menü Ereignisse; **ungeprüft**.

## Entscheidung nötig: Datenschutz bei Unterkünften

Pensionen, Ferienwohnungen und kleine Campingplätze werden oft von Privatpersonen betrieben. Name und Standort einer „Ferienwohnung Müller“ sind dann personenbezogen, auch wenn sie aus offenen Daten stammen. Das ist ein Grenzfall nach Abschnitt 11 der Projektanweisung. Vorschlag, in dieser Reihenfolge:

1. **Aufnehmen nur mit Betriebsnamen**, der erkennbar ein Betrieb ist (Hotel, Gasthof, Campingplatz mit eigener Marke oder Betreiber-Tag), keine Hausnummer, keine Kontaktangaben, keine Fotos.
2. Kleine Privatvermieter (Ferienwohnung, Gästezimmer) **nur gezählt je Gemeinde oder Raster**, nicht als Punkt.
3. Wohnadresse bleibt in jedem Fall außen vor.

Die Entscheidung liegt bei dir. Ohne sie baue ich keinen Unterkunfts-Sammler.

## Vorschlag zum Vorgehen

1. `osm_freizeit` als vierten OSM-Sammler (Overpass, wöchentlich, Fair-Use wie die anderen), erst Camping und Aktivitäten, Unterkünfte nach Datenschutz-Entscheidung. Vorher die Datenmenge für RLP plus 80 km messen und die Zahl der Abfragen festlegen.
2. Luxemburg: `lft-poi.gpkg` ansehen (Felder, Anzahl, Aktualität), dann Collector auf CC BY 4.0.
3. Antrag auf DataHub-Zugang bei der RPT (`data.rlp-tourismus.de`) stellen und beantworten lassen, welcher Teil der Unterkünfte und Touren offen lizenziert ist.
4. Rückfrage beim LBM zum Radverkehrsnetz.
5. Je Quelle Eintrag in `sources.yaml` mit Lizenz, Namensnennung und Datenschutzbewertung, bevor der Collector läuft.

## Belege

Gelesen am 2026-10-16:

- RPT, Open Data im Tourismus RLP: https://rlp.tourismusnetzwerk.info/inhalte/digitales/open-data/
- RPT, DataHub Rheinland-Pfalz: https://rlp.tourismusnetzwerk.info/inhalte/digitales/datahub/
- Luxembourg for Tourism, nationale POI-Datenbank: https://data.public.lu/en/datasets/base-de-donnees-nationale-des-attractions-touristiques-national-database-of-tourism-attractions
- GDI-SL, Premiumwanderwege (Metadaten): https://gdk.gdi-de.org/geonetwork/srv/api/records/6ce85b9f-fc88-eff9-fbc3-7c71593af7be
- Tourenplaner Rheinland-Pfalz: https://www.rlp-tourismus.com/de/service/tourenplaner-rheinland-pfalz
- LBM, Radverkehrsnetz: https://lbm.rlp.de/themen/radverkehr/daten-und-statistik
- OSM-Wiki, Key:tourism: https://wiki.openstreetmap.org/wiki/Key:tourism
- OSM-Wiki, Waymarked Trails: https://wiki.openstreetmap.org/wiki/Waymarked_Trails

Nur in Suchtreffern gesehen, nicht gelesen (ungeprüft): Open-Data-Factsheet Pfalz (pfalz.de, PDF ließ sich nicht abrufen), open.rlp.de (Tourismusstatistik), LANIS (geodaten.naturschutz.rlp.de), Geodatendienste des Landesamts für Umwelt, „Destination Camper Park(ing)“ auf data.public.lu.
