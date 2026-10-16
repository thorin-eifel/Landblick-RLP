# 3 Bedienung

Die Seite ist ein Werkzeug, kein Schaufenster: ruhig, schnell, ohne Animationen um ihrer selbst willen. Sie hat drei Teile, erreichbar über die Kopfzeile: **Lage** (die Karte), **Status** (der Zustand aller Quellen) und **Quellen und Lizenzen**. Rechts oben schaltet der Knopf „Dunkel“ zwischen hellem und dunklem Aussehen um. Auf sehr großen Bildschirmen (ab 1800 Pixel Breite) wächst die Oberfläche mit.

## 3.1 Die Lagekarte im Überblick

Oben steht die Überschrift „Lagekarte“ mit zwei Zählern: die Zahl der angezeigten Meldungen und eine Statuszeile zum Nachladen der Daten. Darunter:

- **Warnband** ganz oben unter der Kopfzeile: die höchste Stufe der gerade geltenden Warnungen (NINA, Deutscher Wetterdienst, Hochwasser). Rot heißt rot. Das Band meldet sich als Statusbereich auch Bildschirmlesern.
- **Suchfeld** in der Karte (Kapitel 3.4).
- **Menüs links**, einklappbar: *Zeitraum*, *Darstellung*, *Ereignisse*, *Geographie* mit den Zusatzkarten *LGB Daten* und *Landesdaten*, *Freizeit* (Kapitel 3.2, 3.3, 3.7).
- **Zeichenerklärung** unten: Sie zeigt für jede eingeschaltete Ebene, was Farben und Zeichen bedeuten.
- **Seitenleiste** rechts mit Reitern *Ereignisse*, *Gewässer*, *Umwelt*, *Wetter* und *Grenzpendler* (Kapitel 3.5). Unter 1000 Pixel Breite stehen die Teile untereinander.

Die Karte lässt sich mit Maus, Touch und Tastatur bedienen. Zoomen geht mit dem Mausrad, mit Doppelklick, mit Zwei-Finger-Geste und mit den Tasten der Kartensteuerung. Dieselben Daten stehen rechts als Tabelle; die Karte ist also nie der einzige Zugang.

## 3.2 Zeitraum

Das Menü *Zeitraum* wählt, welche Ereignisse gelten:

| Auswahl | Gezeigt wird |
|---|---|
| **Jetzt** | was in diesem Moment gilt (Warnung läuft, Sperrung besteht) |
| **24 Std.** | was jetzt gilt oder in den nächsten 24 Stunden beginnt |
| **7 Tage** | dasselbe für die nächste Woche |

Die Auswahl rechnet der Browser selbst, gegen die Uhr des Besuchers. Der Export liefert immer die Obermenge für sieben Tage. Das hat einen Nebeneffekt, der gewollt ist: Wird die Sammelstelle abgeschaltet, ruft die Seite nicht fälschlich „aktuell“.

## 3.3 Ereignisse, Geographie und Freizeit

Die Schalter der Karte stehen in drei Menüs. *Ereignisse* zeigt, was gerade passiert und sich ändert. *Geographie* ist die Landkarte selbst, die sich nicht von Minute zu Minute ändert. *Freizeit* sammelt, was man unterwegs braucht. Beide sind nach Themen gegliedert; jede Gruppe lässt sich als Ganzes oder einzeln ein- und ausschalten.

**Menü Ereignisse**

| Gruppe | Inhalt |
|---|---|
| **Warnungen und Gefahren** | Warnungen (NINA, DWD), Hochwasser, Blitze, Brandverdacht (Satellit), Erdbeben, erhöhte Strahlung |
| **Wetter und Luft** | Regenradar mit Tropfen-Animation, Wind in 10 m Höhe, Wind im Gelände (Schätzung für Täler), Wetterstationen (DWD, KMI), Luftqualität |
| **Wasserstände** | Pegel der Flüsse, Wasserbewegung |
| **Verkehr und Tanken** | Straßenverkehr und Baustellen, ÖPNV-Verspätungen, Luftverkehr, Tankstellen mit Preisen |

**Menü Geographie**

| Gruppe | Inhalt |
|---|---|
| **Gelände und Gebäude** | Berge und Täler (Schattierung und Farbe), Höhenlinien, Licht am Zeiger, Klippen, Hangneigung, Gebäude |
| **Wald, Wiesen und Felder** | Wald, Wiesen, Busch und Heide, Äcker, Obst und Wein, Feuchtgebiete, Fels und Strand |
| **Straßen und Bahn** | das Straßennetz der Karte nach Art, Bahnstrecken, Haltestellen, Straßenschilder, Brücken und Tunnel |
| **Grenzen und Schutzgebiete** | Staats-, Landes-, Kreis- und Gemeindegrenzen, Naturschutzgebiete, Nationalparks, Militärgelände |
| **Orte und Einrichtungen** | Notfallpunkte, Schulen und Rathäuser, Ladesäulen, Windräder, Wehre und Schleusen |
| **Natur** | Berggipfel (mit Höhe), Höhlen, Wasserfälle und Quellen, Aussichtspunkte, Felsen und Vulkane |
| **Kultur und Geschichte** | Burgen, Ausgrabungen, Klöster, historische Gebäude, Kirchen, Friedhöfe |

Darunter stehen in *Geographie* die Zusatzkarten der Landesstellen (*LGB Daten*, *Landesdaten*, Kapitel 3.7).

**Menü Freizeit**

| Gruppe | Inhalt |
|---|---|
| **Wandern und Radfahren** | Wanderrouten und Radrouten (Fern- und Regionalrouten) |
| **Rast und Baden** | Rastplätze, Schutzhütten, Badestellen |

Übernachten (Hotels, Pensionen, Campingplätze) und Aktivitäten sind geplant; die Quellen dafür stehen in `docs/rlp/freizeit-quellen.md`.

Einige Ebenen verdienen ein Wort.

**Meldungen und ihre Stufen.** Die Farbe einer Meldung stammt von der meldenden Stelle (NINA, DWD, Hochwasserzentrale), nicht von uns. „Rot“ (critical) vergibt das Programm nur bei den Stufen *Severe* und *Extreme* des Warnstandards CAP. Verkehrsmeldungen haben eigene vier Stufen: Gelb Baustelle, Orange Behinderung oder Stau, Rot langer Stau (ab 30 Minuten Verzögerung) oder eine Fahrtrichtung gesperrt, Schwarz Vollsperrung.

**Wetter.** Das Regenradar des DWD ist ein Bild, die Tropfen sind eine Animation: Dichte, Größe und Helligkeit folgen dem Radarwert. Der Wind stammt aus dem Modell ICON-D2 und läuft im Zeitraffer. „Wind im Gelände“ ist eine Schätzung, die den Modellwind in Tälern und auf Kämmen verändert; sie ist als Schätzung gekennzeichnet.

**Blitze** kommen vom Satelliten (EUMETSAT, Meteosat Third Generation). Das Alter zeigt eine Farbskala bis 45 Minuten.

**Luftverkehr** zeigt zivile Flugzeuge, militärische (violett, im Ring) und Hubschrauber, aus dem Community-Netzwerk adsb.lol. Gespeichert wird nur die Klasse, nie Kennzeichen oder Kennung. Die Schweife ziehen sich aus Positionen, die der Browser in dieser Sitzung gesehen hat; sie werden nie gespeichert. Läuft ein Flugzeug, kreist ein Radarstrahl (nicht bei „weniger Bewegung“ im System).

**Wasserbewegung.** Wandernde Striche und Pfeile zeigen die Fließrichtung entlang der Gewässerlinien. Das Tempo ist eine Klasse (Bach, Fluss, gestaut), kein gemessener Abfluss. Mosel und Saar sind staugeregelt und bewegen sich kaum. Auf Seen und Teichen ziehen Wellenzeichen mit dem Wind.

**Gebäude.** Standardmäßig an, ab Kartenstufe 13 große, ab 14 alle. In Rheinland-Pfalz stammen die Umrisse aus den amtlichen Hausumringen, außerhalb aus OpenStreetMap. Die Ebene *Gebäude nach Funktion* färbt die Umrisse nach acht Klassen (wohnen, Wirtschaft, Garage, Überdachung, Technik, öffentlich, Religion, sonstige); die Zeichenerklärung nennt sie. Hausnummern erscheinen ab Stufe 16, aber nur dort, wo OpenStreetMap sie kennt, und es ist keine Adresssuche.

**Lichtquelle am Zeiger.** Eine Spielerei mit ernstem Kern: Ein Punktlicht über dem Mauszeiger beleuchtet das Relief, Schatten fallen hinter die Kämme. Gerechnet wird auf der Grafikkarte (WebGL2). Sie gilt nur bei Nordausrichtung ohne Neigung.

**Darstellung.** Im Menü „Darstellung“ wählt man zwischen „Landblick“ (Standard) und „Alte Karte“, einer zweiten Darstellung mit Pergamentfarben, gebrochener Schrift, Windrose und eigenen Zeichen. Weitere Darstellungen sollen folgen. Alle Ebenen bleiben in beiden wählbar, auch Kirchen, Kapellen, Wegkreuze, Mühlen, Furten, Grenzsteine, Richtstätten und Brunnen (Kultur und Geschichte). Klippen und Felswände sind in beiden gleich gezeichnet: Wandfläche, Schraffen und Oberkante; in der Alten Karte in Tinte und Pergament.

## 3.4 Suche und Rechtsklick

**Suche.** Das Feld links oben in der Karte (Tastaturkürzel `/` oder `Strg+K`) sucht Orte, Straßen, Bäche, Gipfel, Wälder, Schutzgebiete, Schulen, Kirchen, Feuerwachen, Brücken, Haltestellen, Routen und Pegel. Die Suche läuft vollständig im Browser; der Index wird beim ersten Klick ins Feld geladen, und es geht keine Anfrage nach außen. Der Index enthält keine Hausnummern, keine Adressen und keine Personennamen. Die Pfeiltasten wählen, `Enter` springt hin.

**Rechtsklick.** Ein Rechtsklick auf die Karte (auf Touchgeräten: Finger lang halten) öffnet ein kleines Fenster mit der Höhe über Normalhöhennull (aus dem Geländemodell der Karte), den Koordinaten in drei Schreibweisen (Dezimalgrad, Grad-Minuten-Sekunden, UTM 32 ETRS89), dem nächsten Ortsteil, der Gemeinde mit Verbandsgemeinde und dem Kreis. Die Namen kommen aus einer Datei, die der Browser beim ersten Rechtsklick holt (rund 1,2 MB komprimiert); es gibt keine Anfrage an Dritte. Außerhalb von Rheinland-Pfalz kennt die Auskunft nur den Kreis. Die Gemarkung fehlt noch.

## 3.5 Seitenleiste: Ereignisse, Gewässer, Umwelt, Wetter, Grenzpendler

- **Ereignisse**: die Meldungen als Liste, nach Schwere sortiert. Ein Klick auf eine Zeile zentriert die Karte. Der Filter wählt *Land* und *Landkreis*; er wirkt auf Liste und Karte. Meldungen von außerhalb Deutschlands tragen das Land aus der Quelle (LU, BE, FR); ein deutsches Kürzel ohne Kreis erscheint als „unbekannt“ und fällt bei gesetztem Filter heraus.
- **Gewässer**: Pegel mit Verlauf, Warnstufen und Trend (Mosel, Saar, Sauer, Prüm, Kyll, Lahn, Nahe, Rhein und mehr). Pegel erscheinen erst ab Kartenstufe 8.
- **Umwelt**: Luftqualität (Feinstaub, Stickstoffdioxid, Ozon), Ortsdosisleistung (Strahlung), Pollen und UV, Waldbrandindex. Auch ab Stufe 8.
- **Wetter**: Messwerte der DWD- und KMI-Stationen, Vorhersage.
- **Grenzpendler**: Spritpreise beiderseits der Grenze (Deutschland: Tankerkönig; Luxemburg: gesetzliche Höchstpreise des Wirtschaftsministeriums) und die Lage auf den Zufahrten.

Unter Kartenstufe 8 lädt die Seite keine Einzelmeldungen, sondern zeigt Zahlen je Land beziehungsweise Kreis (Dichte-Ebene). Das Warnband und die Tabelle zeigen auch dort alle Warnungen. Ab Stufe 9 sind es Einzelmeldungen mit einer Obergrenze (1500 Meldungen ab Stufe „Hinweis“), ab Stufe 10 kommen Haltestellen, Landmarken und Routen, ab Stufe 11 Infrastruktur und Anbauflächen.

## 3.6 Herkunft, Alter und Ausfälle lesen

Jede Meldung, jeder Pegel und jede Station zeigt im Popup:

- die **Quelle** (der Name des Betreibers),
- den **Abrufzeitpunkt** und das **Alter**,
- die **Lizenz** beziehungsweise den Quellenverweis.

Der Zustand einer Quelle ist einer von sechs:

| Zustand | Bedeutung |
|---|---|
| ok | zuletzt erfolgreich, Daten frisch |
| gestört (degraded) | der letzte Lauf schlug fehl, die Daten sind noch jung |
| veraltet (stale) | letzter Erfolg älter als das Dreifache des Abrufintervalls |
| nicht erreichbar (down) | nie erfolgreich oder drei Fehlläufe in Folge: „nicht erreichbar seit …“ |
| offen (pending) | noch nie versucht |
| aus (disabled) | im Register abgeschaltet |

Ist der **Export selbst** älter als 20 Minuten, zeigt die Seite „Datenstand veraltet“. Das passiert, wenn die Sammelstelle steht oder der Upload klemmt, und es fällt dem Besucher auf, weil die Seite gegen seine Uhr rechnet. Laufen die Datendateien gar nicht mehr, steht oben „Die Datendateien konnten nicht geladen werden. Angezeigt wird, was zuletzt geladen wurde.“

Die **Statusseite** listet jede Quelle mit Zustand, letztem Erfolg, Fehlern in Folge, Fehlertext und den letzten Läufen. Nach fünf Fehlläufen in Folge pausiert ein Sammler für 15 Minuten (Circuit Breaker), damit er die Quelle nicht belastet. Die Seite **Quellen und Lizenzen** nennt je Quelle Betreiber, Lizenz, Intervall und Datenschutzrisiko. Wo die Lizenz noch nicht an der Primärquelle bestätigt ist, steht das offen dort.

## 3.7 Kartendienste der Landesämter (LGB Daten, Landesdaten)

Zwei Menüs binden amtliche Kartendienste des Landes ein, zum Beispiel geologische Karten und Hochwassergefahrenkarten. Es sind die einzigen Stellen, an denen der Browser etwas bei einem Dritten holt: direkt beim Landesserver, nicht über uns. Deshalb ist alles aus, bis man den Hinweis im Menü bestätigt („Verstanden, Karte laden“). Die Bestätigung gilt nur bis zum Neuladen der Seite und wird nicht gespeichert. Es sind höchstens sechs Ebenen je Menü gleichzeitig; Deckkraft und „Alle Ebenen aus“ stehen im Menü. Fällt ein Dienst aus, steht „n nicht erreichbar“, der Rest der Karte bleibt. Der vorgeschriebene Quellenvermerk steht unter der Karte, solange eine Ebene an ist.

## 3.8 Tastatur, Bildschirmleser, Bewegung

- **Tastatur**: alle Menüs, die Suche (`/`, `Strg+K`), die Ebenenschalter und die Seitenleiste sind mit Tab, Pfeil- und Entertasten erreichbar; ein Link „Zum Inhalt springen“ steht am Anfang jeder Seite. Die Zahlen der Dichte-Ebene (unter Stufe 8) lassen sich nur mit der Maus anklicken; Ersatz sind die Zoomtasten, der Landkreisfilter und die Tabelle.
- **Bildschirmleser**: Die Karte trägt eine Beschreibung und verweist auf die Tabelle; Warnband und Hinweise sind Statusbereiche.
- **Bewegung**: Ist im Betriebssystem „weniger Bewegung“ eingestellt, stehen Wasserbewegung, Tropfen und Radarstrahl still.
- **Kontrast**: helle und dunkle Darstellung mit eigenen Farbwerten.

Die Barrierefreiheit ist geprüft, aber nicht von Dritten abgenommen. Fehlt etwas, bitte melden.

## 3.9 Prüfzugang für Entwickler

Die Adresse `…/#debug` schaltet einen Prüfzugang frei, den die Tests und die Messungen benutzen (zum Beispiel der Befehl `zellen`, der die geladenen Dateien und Fehler auflistet). Er verändert keine Daten und ist nicht für den Alltag gedacht.

**Detailfenster und Kartenausschnitt.** Ereignisse, Gewässer sowie Luft und Strahlung im Detailfenster zeigen nur Einträge im sichtbaren Kartenbereich. Wer verschiebt oder zoomt, sieht die Liste nachziehen. Für alle Meldungen: herauszoomen. Wetter und Tankstellen sind nicht an den Ausschnitt gebunden.
