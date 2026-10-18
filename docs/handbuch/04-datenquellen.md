# 4 Datenquellen

Landblick erfindet keine Daten. Alles, was auf der Karte steht, stammt aus einer Quelle, die im Quellenregister `sources.yaml` eingetragen ist. Ohne Eintrag läuft kein Sammler. Das ist keine Formalie, sondern die Stelle, an der Lizenz, Datenschutzrisiko und Abrufgrenzen festgehalten werden, bevor ein einziger Abruf stattfindet.

## 4.1 Das Quellenregister

Je Quelle stehen dort:

| Feld | Bedeutung |
|---|---|
| `id`, `name`, `kurzname` | Kennung (Dateiname des Sammlers, Schlüssel in der Datenbank), Langname, Kurzform für Kacheln |
| `betreiber`, `url` | wer die Daten liefert und von wo sie kommen |
| `lizenz`, `lizenz_geprueft`, `lizenz_hinweis` | Lizenzname; `true` nur, wenn der Lizenztext an der Primärquelle gelesen wurde |
| `namensnennung` | der Wortlaut, der im Oberfläche sichtbar ist (Seite „Quellen“, Fußzeile der Kachel) |
| `intervall`, `ratenlimit` | Abrufabstand in Sekunden und die Grenze, die der Betreiber nennt |
| `auth` | `keine` oder der Name der Variable in `.env`, die den Schlüssel trägt |
| `geo_bezug` | wie die Region geschnitten wird |
| `datenschutz_risiko` | `niedrig`, `mittel`, `hoch` |
| `aktiv`, `zuletzt_geprüft` | Schalter und Datum der letzten Prüfung |
| `collector`, `params` | Modulname in `app/collectors/` und Parameter |
| `art` | `collector` (Standard) oder `client`: Quelle, die der Browser selbst abruft |
| `erstlauf`, `nutzung`, `zugang` | Hinweise für den ersten Lauf, den Zweck der Daten und Voraussetzungen wie Schlüssel |

Quellen mit `art: client` (derzeit die WMS-Dienste des Landesamts für Vermessung und Geobasisinformation und weitere Landesdienste) werden nicht von der Sammelstelle abgerufen, sondern erst nach ausdrücklicher Zustimmung der Besucherin oder des Besuchers direkt aus dem Browser. Wie das abläuft, steht in Kapitel 7.

## 4.2 Lizenzen

Die Lizenzen sind gemischt, und das ist gewollt, weil nur offene Daten hinein dürfen: Datenlizenz Deutschland (dl-de/by-2.0, dl-de/zero-2.0), GeoNutzV des Deutschen Wetterdienstes, CC BY 4.0, ODbL für OpenStreetMap-Daten, Etalab-Lizenz bei französischen Quellen, Open-Data-Bedingungen in Luxemburg, Belgien und der Wallonie. Wo eine Quelle Namensnennung verlangt, zeigt Landblick sie an.

Wichtig ist die Spalte `lizenz_geprueft`. Sie steht bei einem Teil der Quellen noch auf `false`: Der Endpunkt wurde live getestet, der Lizenztext aber noch nicht an der Primärquelle bestätigt. Vor einem öffentlichen Start muss jede Zeile auf `true`. Bis dahin ist Landblick ein privates Werkzeug, kein Angebot an Dritte. Der Stand wird in Kapitel 9 genannt.

## 4.3 Gruppen

Die Quellen lassen sich grob in diese Gruppen ordnen:

- **Warnungen und Lage:** NINA des Bundesamts für Bevölkerungsschutz, DWD-Unwetterwarnungen, MeteoAlarm für Nachbarländer, Waldbrandgefahr, Presseportal (Polizei, Feuerwehr: nur Titel, Ort, Zeit, Link).
- **Wetter:** Bright Sky (DWD-Daten), MET Norway, Stationsdaten des DWD und des belgischen KMI, Radar des DWD, Windfeld aus dem Modell des DWD, Blitze von EUMETSAT.
- **Gewässer:** PEGELONLINE, Hochwasserportal Rheinland-Pfalz, Länderübergreifendes Hochwasserportal, Luxemburg (Wasserverwaltung), Hub'Eau (Frankreich), Wallonie.
- **Luft und Strahlung:** Umweltbundesamt, Sensor.Community (nur aggregiert), IRCELINE (Belgien), BfS-Ortsdosisleistung.
- **Verkehr:** Autobahn-API, Landesbetrieb Mobilität Rheinland-Pfalz (Baustellen), Mobilitätsatlas BW für den Grenzraum, CITA Luxemburg, Bison Futé (Frankreich), GTFS-Fahrpläne und Echtzeitdaten, Luftverkehr über adsb.lol.
- **Preise:** Tankerkönig (Deutschland), STATEC (Luxemburg), OpenStreetMap für Stationen in Luxemburg.
- **Erde und Umwelt:** EMSC (Erdbeben), NASA FIRMS (Brandpixel, braucht Schlüssel), Infrastruktur, Natur, Routen und Anbau aus OpenStreetMap.
- **Medien und Themen:** RSS von BRF und Volksfreund (Titel, Datum, Link; keine Volltexte), Mastodon (nur aggregierte Themenzählung).
- **Karten im Browser (Client):** Dienste des Landesamts für Vermessung und der Landesstellen.

Die vollständige, aus `sources.yaml` erzeugte Liste folgt unten. Sie wird beim Bau des Handbuchs neu geschrieben und kann deshalb nicht vom Register abweichen.

## 4.4 Was bewusst fehlt

- **X/Twitter und Meta-Plattformen:** keine freie Schnittstelle, kein Scraping.
- **Telegram:** Rechtslage und Kontext heikel, deshalb nicht eingebunden.
- **Kamerabilder:** nur mit ausdrücklicher Freigabe und ohne erkennbare Personen, bisher keine.
- **Volltexte von Zeitungen und Bilder aus Nachrichtenquellen:** Urheberrecht.
- **Medienfeeds ohne geprüfte Lizenz und robots.txt:** bleiben aus (siehe Kapitel 9).

## 4.5 Vollständige Liste

Kennung in der ersten Spalte, die Intervalle sind Soll-Abstände. „Risiko“ ist das Datenschutzrisiko aus dem Register, „geprüft“ der Stand der Lizenzprüfung.

<!-- quellen:start -->

| Kennung | Quelle | Betreiber | Lizenz | Intervall | Risiko | geprüft | aktiv |
|---|---|---|---|---|---|---|---|
| `nina` | NINA / BBK | Bundesamt für Bevölkerungsschutz und Katastrophenhilfe (BBK) | Nutzungsbedingungen NINA/BBK | 5 min | niedrig | nein | ja |
| `dwd_warnungen` | DWD | Deutscher Wetterdienst (DWD) | GeoNutzV (DWD Open Data) | 5 min | niedrig | nein | ja |
| `brightsky` | DWD via Bright Sky | Bright Sky (Jakob de Maeyer) auf Basis von DWD Open Data | DWD GeoNutzV; Bright Sky Software MIT | 15 min | niedrig | nein | ja |
| `pegelonline` | WSV Pegelonline | Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV) | Datenlizenz Deutschland – Namensnennung 2.0 (zu bestätigen) | 10 min | niedrig | nein | ja |
| `autobahn` | Autobahn GmbH | Die Autobahn GmbH des Bundes | Nutzungsbedingungen Autobahn GmbH (zu bestätigen) | 5 min | niedrig | nein | ja |
| `adsblol` | adsb.lol | adsb.lol (Community-Netzwerk) | ODbL 1.0 (laut Betreiber-Dokumentation) | 15 s | mittel | nein | ja |
| `lbm_baustellen` | Mobilitätsatlas RLP | Ministerium für Wirtschaft, Verkehr, Landwirtschaft und Weinbau Rheinland-Pfalz (Mobilitätsatlas), Daten der Verkehrsbehörden RLP und der Straßenbauverwaltung Luxemburg | nicht angegeben (zu klären) | 10 min | niedrig | nein | ja |
| `hochwasser_rlp` | Hochwasser RLP | Landesamt für Umwelt Rheinland-Pfalz (Hochwasservorhersagezentrale); Messwerte der Pegelbetreiber (SGD Nord, Kommunen, AGE Luxemburg, SPW Belgien) | nicht angegeben (zu klären) | 15 min | niedrig | nein | ja |
| `bfs_odl` | BfS ODL | Bundesamt für Strahlenschutz (BfS) | Datenlizenz Deutschland – Namensnennung – Version 2.0 (nach Kenntnisstand) | 30 min | niedrig | nein | ja |
| `uba_luft` | UBA Luftdaten | Umweltbundesamt (UBA), Daten der Landesmessnetze Rheinland-Pfalz und Saarland | Datenlizenz Deutschland – Namensnennung – Version 2.0 (nach Kenntnisstand) | 30 min | niedrig | nein | ja |
| `emsc` | EMSC | Euro-Mediterranean Seismological Centre (EMSC), Meldungen nationaler Erdbebendienste | CC BY 4.0 (laut Dienstseite) | 15 min | niedrig | ja | ja |
| `dwd_radar` | DWD Radar | Deutscher Wetterdienst (DWD) | GeoNutzV (Geodatennutzungsverordnung), Quellenvermerk Deutscher Wetterdienst | 5 min | niedrig | nein | ja |
| `dwd_icon_d2_wind` | DWD Wind | Deutscher Wetterdienst (DWD) | GeoNutzV (Geodatennutzungsverordnung), Quellenvermerk Deutscher Wetterdienst | 1 h | niedrig | nein | ja |
| `eumetsat_li` | EUMETSAT Blitze | EUMETSAT | EUMETSAT-Datenpolitik, Quellenvermerk EUMETSAT (Bedingungen für MTG-LI über EUMETView nicht abschließend geprüft) | 5 min | niedrig | nein | ja |
| `nasa_firms` | NASA FIRMS | NASA LANCE / FIRMS (VIIRS auf Suomi NPP, NOAA-20, NOAA-21) | NASA Earthdata-Datennutzungsrichtlinie (frei, auch kommerziell), Quellenangabe NASA FIRMS | 30 min | niedrig | nein | ja |
| `gtfs_static` | GTFS Fahrplan | Ministère de la Mobilité et des Travaux publics (Luxemburg, über data.public.lu); DELFI e. V. (über gtfs.de) | CC BY 4.0 (Luxemburg laut Datensatz, Deutschland laut gtfs.de "Creative Commons 4.0") | 168 h | niedrig | nein | ja |
| `gtfs_rt_de` | ÖPNV Echtzeit | DELFI e. V. / gtfs.de (Daten der Verkehrsverbünde und der DB) | CC BY-SA 4.0 (Namensnennung, Weitergabe unter gleichen Bedingungen), ohne Gewähr | 10 min | niedrig | nein | ja |
| `osm_natur` | Landmarken | OpenStreetMap-Mitwirkende; Abfrage über die Overpass API (overpass-api.de) | ODbL 1.0 (© OpenStreetMap-Mitwirkende) | 168 h | niedrig | nein | ja |
| `osm_infra` | Infrastruktur | OpenStreetMap-Mitwirkende; Abfrage über die Overpass API (overpass-api.de) | ODbL 1.0 (© OpenStreetMap-Mitwirkende) | 168 h | niedrig | nein | ja |
| `sgdnord_energie` | Wind und Solar (SGD Nord) | Struktur- und Genehmigungsdirektion Nord, Obere Landesplanungsbehörde (Raumordnungskataster ROK25 Online); Bereitstellung über das Geoportal Rheinland-Pfalz | Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2.0) | 24 h | niedrig | ja | ja |
| `osm_energie` | Energie | OpenStreetMap-Mitwirkende; Abfrage über die Overpass API (overpass-api.de) | ODbL 1.0 (© OpenStreetMap-Mitwirkende) | 168 h | niedrig | nein | ja |
| `osm_anbau` | Anbauflächen | OpenStreetMap-Mitwirkende; Abfrage über die Overpass API (overpass-api.de) | ODbL 1.0 (© OpenStreetMap-Mitwirkende) | 168 h | niedrig | nein | ja |
| `osm_routen` | Routen | OpenStreetMap-Mitwirkende; Abfrage über die Overpass API (overpass-api.de) | ODbL 1.0 (© OpenStreetMap-Mitwirkende) | 168 h | niedrig | nein | ja |
| `meteolux` | MeteoLux Findel | Administration de la navigation aérienne (ANA) / MeteoLux | CC0 1.0 | 10 min | niedrig | ja | ja |
| `metno` | MET Norway | Norwegian Meteorological Institute (MET Norway) | CC BY 4.0 | 1 h | niedrig | ja | ja |
| `sensor_community` | Sensor.Community | Sensor.Community (Verein und Mitwirkende) | Datenbank ODbL 1.0, Inhalte DbCL 1.0 (laut Betreiberangabe, zu bestätigen) | 10 min | mittel | nein | ja |
| `presseportal` | Presseportal Polizei | news aktuell GmbH (Presseportal); Inhalte der Polizeidienststellen | keine offene Lizenz; nur Überschrift, Ort, Zeit und Link | 10 min | mittel | nein | nein |
| `volksfreund` | Volksfreund | Trierischer Volksfreund (Medienhaus) | keine offene Lizenz; nur Überschrift, Zeit und Link, kein Text, kein Bild | 15 min | niedrig | nein | ja |
| `lu_pegel` | Pegel Luxemburg | Administration de la gestion de l'eau (AGE), Luxembourg | CC0 1.0 | 15 min | niedrig | ja | ja |
| `cita_lu` | CITA Luxemburg | Centre d'information et de transport routier (CITA), Administration des ponts et chaussées | CC0 1.0 | 5 min | niedrig | ja | ja |
| `dwd_waldbrand` | DWD Waldbrandindex | Deutscher Wetterdienst (DWD) | CC BY 4.0 | 3 h | niedrig | ja | ja |
| `dwd_gesundheit` | DWD Pollen/UV | Deutscher Wetterdienst (DWD) | GeoNutzV (Namensnennung DWD), Bedingungen laut Open-Data-Hinweisen des DWD | 1 h | niedrig | nein | ja |
| `tankerkoenig` | Tankerkönig | Tankerkönig; Daten der Markttransparenzstelle für Kraftstoffe (Bundeskartellamt) | CC BY 4.0 | 2 min | niedrig | nein | ja |
| `mastodon_themen` | Themenradar Mastodon | Mastodon gGmbH (Instanz mastodon.social); Beiträge gehören ihren Verfassern | keine; es werden keine Beiträge gespeichert, nur Zählungen je Hashtag | 1 h | mittel | nein | nein |
| `hubeau_pegel` | Hub'eau Pegel | Office français de la biodiversité (OFB) und Schapi, Dienst Hub'eau (eaufrance.fr) | Licence Ouverte 2.0 (Etalab), nach Kenntnis | 15 min | niedrig | nein | ja |
| `wallonie_pegel` | SPW Pegel | Service public de Wallonie (SPW), Mobilité et Infrastructures, Direction des Voies hydrauliques, Hydrométrie | keine ausdrückliche Lizenzangabe am Dienst gefunden | 15 min | niedrig | nein | ja |
| `brf` | BRF | BRF, Belgischer Rundfunk der Deutschsprachigen Gemeinschaft, Eupen | keine offene Lizenz; nur Überschrift, Zeit und Link, kein Text, kein Bild | 15 min | niedrig | nein | ja |
| `meteoalarm` | MeteoAlarm | EUMETNET (MeteoAlarm); Herausgeber KMI/IRM Belgien, Météo-France, MeteoLux | laut Anbieter gleichwertig CC BY 4.0 mit zusätzlichen Auflagen für die Weiterverbreitung | 10 min | niedrig | nein | ja |
| `bison_fute` | Bison Futé | DGITM und Directions interdépartementales des routes (DIR), über tipi.bison-fute.gouv.fr | Licence Ouverte 2.0 (Etalab) | 10 min | niedrig | ja | ja |
| `statec_sprit` | Höchstpreise Luxemburg | STATEC Luxembourg (Preise setzt das Wirtschaftsministerium fest), Abruf über lustat.statec.lu (SDMX-REST) | CC0 1.0 | 1 h | niedrig | ja | ja |
| `osm_tankstellen_lu` | Tankstellen Luxemburg | OpenStreetMap-Mitwirkende; Abfrage über die Overpass API (overpass-api.de) | ODbL 1.0 (© OpenStreetMap-Mitwirkende) | 168 h | niedrig | nein | ja |
| `dwd_stationen` | DWD-Stationen | Deutscher Wetterdienst (Messdaten), Bright Sky (Jakob de Maeyer) als Aufbereitung | DWD GeoNutzV; Bright Sky Software MIT | 30 min | niedrig | nein | ja |
| `irceline` | IRCEL-CELINE | IRCEL - CELINE (Belgian Interregional Environment Agency), Messnetze Flandern, Wallonien, Brüssel | CC BY 4.0 (nach Kenntnisstand) | 30 min | niedrig | nein | ja |
| `kmi_stationen` | KMI-Stationen | Königliches Meteorologisches Institut von Belgien (KMI/IRM) | CC BY 4.0 (nach Kenntnisstand) | 30 min | niedrig | nein | ja |
| `lhp_hochwasser` | LHP Hochwasser | Länderübergreifendes Hochwasserportal der Hochwasserzentralen der Länder (Geschäftsstelle LfU Bayern, LUBW) | Creative Commons Namensnennung 4.0 (CC BY 4.0) | 10 min | niedrig | nein | ja |
| `mobidata_bw_baustellen` | Baustellen BW | Land Baden-Württemberg (Baustellen- und Ereignismanagementsystem BEMaS), bereitgestellt über MobiData BW (NVBW) | Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2.0) | 10 min | niedrig | nein | ja |
| `mobidata_bw_meldungen` | Verkehrsmeldungen BW | Landesmeldestelle Baden-Württemberg (Ministerium des Inneren, für Digitalisierung und Kommunen), bereitgestellt über MobiData BW (NVBW) | Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2.0) | 5 min | niedrig | nein | ja |
| `lgb_wms` | LGB Daten (Browser) | Landesamt für Geologie und Bergbau Rheinland-Pfalz (LGB) | Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0) | — | mittel | nein | ja |
| `landesdaten_wms` | Landesdaten (Browser) | Landesstellen Rheinland-Pfalz (Landesamt für Vermessung und Geobasisinformationen, Landesamt für Umwelt, Ministerium, LBM, DLR u. a.) | je Dienst, überwiegend Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0); daneben dl-de/zero-2-0, CC BY 3.0/4.0, ODbL 1.0 | — | mittel | nein | ja |

49 Quellen im Register, davon 47 aktiv (45 mit Sammler, 2 nur im Browser).

<!-- quellen:ende -->
