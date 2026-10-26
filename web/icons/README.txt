Symbole der Oberfläche und der Karte. Alle Dateien sind frei weitergebbar und liegen im Repository; die Installer bringen sie mit.

Maki (Mapbox, CC0 1.0, https://github.com/mapbox/maki, npm @mapbox/maki 8.2.0):
  flug (airport), stau (car), baustelle (construction), sperrung (barrier), warnung (caution), hubschrauber (heliport),
  feuer (fire-station), bahn (rail), quelle (water), gebirge (mountain), vulkan (volcano), burg (castle),
  denkmal (monument), kloster (religious-christian), gebaeude (landmark)
Temaki (OpenStreetMap-Editor iD, CC0 1.0, https://github.com/ideditor/temaki, npm @rapideditor/temaki 5.13.0):
  wind (windsock), relief (mountain_range), strahlung (radiation), ton (speaker), natur (pedestrian), feuchte (water)
OpenStreetMap Carto (CC0 1.0, https://github.com/gravitystorm/openstreetmap-carto/tree/master/symbols):
  hoehle (natural/cave), wasserfall (natural/waterfall), fernglas (tourism/viewpoint)
Eigene Zeichnungen des Projekts (15er-Raster wie Maki, GPL-3.0 wie der Code):
  tanken, wolken, regen, blitz, temperatur, druck, beben, hochwasser, pegel, luft

Keine Namensnennung nötig. Bis Oktober 2026 kamen die meisten Symbole von uxwing.com; deren Lizenz verbietet die Weitergabe,
deshalb fehlten sie in den Installern. Sie sind vollständig ersetzt.

Menüzeichen (web/icons/menu/, im Repository, weil frei weitergebbar):
Maki (Mapbox, CC0 1.0, https://github.com/mapbox/maki), Temaki (OpenStreetMap-Editor iD, CC0 1.0, https://github.com/ideditor/temaki)
und OpenStreetMap Carto (CC0 1.0, hoehle.svg). Eigene Zeichnungen des Projekts: autobahn, bundesstrasse, landstrasse, nebenstrasse,
grenze-staat, grenze-land, grenze-kreis, grenze-gemeinde, solar (Energie; kraftwerk, umspannwerk, transformator, leitung aus Temaki). Regel: jedes Zeichen steht im Menü und in den Reitern nur einmal,
tests/js/icons-eindeutig.test.mjs prüft das. Neue Schalter bekommen ein neues Zeichen, keine Wiederverwendung.
