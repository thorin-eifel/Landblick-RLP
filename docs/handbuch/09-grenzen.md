# 9 Grenzen und offene Punkte

Eine Alpha-Fassung ist ehrlich, wenn sie sagt, was nicht geht. Dieses Kapitel sammelt es an einer Stelle. Die laufend gepflegte Fassung steht in `docs/rlp/offen.md`.

## 9.1 Was in 1.0.0-beta.1 nicht fertig ist

- **Dauerlauf (R6).** Sieben Tage Betrieb ohne Handeingriff sind noch nicht gelaufen. Bis dahin ist die Stabilität im Langbetrieb behauptet, nicht belegt.
- **Abnahme (R7).** Die Phase hat noch nicht begonnen. Sie beginnt erst nach Freigabe von R6 durch den Betreiber.
- **Windows.** Der Installer ist unter Linux durchgespielt und durch Tests abgedeckt, aber auf einem Windows-System noch nicht gelaufen. Wer ihn dort ausprobiert, findet die Prüfliste in `docs/betrieb.md`.
- **Lizenzprüfung.** Bei einem Teil der Quellen steht `lizenz_geprueft: false`. Der Endpunkt funktioniert, der Lizenztext ist aber noch nicht an der Primärquelle bestätigt. Gilt auch für die Landesdienste im Kartenmodul.
- **Rechtliche Endabnahme.** Impressum, Datenschutzerklärung (Angaben zu Hosting-Protokollen und Auftragsverarbeitung) und Datenschutzfolgeabschätzung brauchen vor einem öffentlichen Start eine Prüfung durch Fachleute. Dieses Handbuch ersetzt sie nicht.
- **Kein öffentlicher Betrieb.** Es gibt keine öffentliche Instanz und keine zugesagte Verfügbarkeit.

## 9.2 Bekannte Einschränkungen

- **Kartenarchive nicht im Paket.** Basiskarte, Gebäude und Relief sind mehrere Gigabyte groß und werden nicht mitgeliefert. Ohne sie zeigt die Seite Daten, aber keine Karte. Bau: Kapitel 2 und `docs/betrieb.md`. Der Installer baut auf Wunsch nur den Kartenteil (`--karte voll`) und fragt vorher.
- **Symbole.** Die uxwing-Symbole dürfen nicht weiterverbreitet werden und sind nicht im Paket; `tools/fetch_icons.sh` holt sie.
- **Keine Bildschirmfotos.** Dieses Handbuch beschreibt die Oberfläche in Worten. Ein Lauf in der Bauumgebung hat weder Kartenarchive noch Echtdaten.
- **Betriebsanleitung teilweise veraltet.** In `docs/betrieb.md` stehen noch Abschnitte aus der Zeit des 120-Kilometer-Kreises. Maßgeblich ist die Region in `region.yaml` (Rheinland-Pfalz plus 80 km).
- **Radar-Sweep** zeichnet um den Mittelpunkt Irrel, nicht entlang der Landesgrenze.
- **Länderzuordnung** außerhalb Deutschlands hängt am Kennzeichen des Sammlers; saubere Landesgrenzen (Natural Earth) fehlen noch.
- **Overpass-Sammler** (Infrastruktur, Natur, Routen, Anbau, Energie) sind nicht live gemessen; die Obergrenzen der Mengen sind geschätzt.
- **Tankerkönig und NASA FIRMS** brauchen eigene Schlüssel und sind nur dann aktiv, wenn sie in `.env` stehen.
- **Medienfeeds.** Nur ausgewählte Feeds sind eingebunden; weitere warten auf Prüfung von Lizenz und robots.txt.
- **Abrufzeit je Meldung.** Der Zeitpunkt „Abruf“ im Zellenbetrieb ist der letzte Erfolg der Quelle, nicht der der einzelnen Meldung.
- **Tastaturbedienung** der Dichte-Ebene: die Zahlen lassen sich nur mit der Maus anklicken; Ersatz sind Zoomtasten, Landkreisfilter und Tabelle.
- **Energie.** Windräder und Solarparks kommen aus dem Geodatendienst der SGD Nord (nur Nordteil von Rheinland-Pfalz, ohne Betreiberangaben), Kraftwerke, Umspannwerke, Transformatoren und Leitungen ab 110 kV aus OpenStreetMap. Der OSM-Teil ist noch nicht live gelaufen. Im Süden fehlt ein vergleichbarer amtlicher Dienst.
- **Ein unstabiler Test** (`test_hochwasser_rlp_config_cached_and_second_run_no_duplicates`) lief früher selten rot und wird beobachtet.

## 9.3 Was nicht geplant ist

Personensuche, Profile, Kennzeichen- oder Gesichtserkennung, Telegram-Auswertung, Scraping von Plattformen ohne offene Schnittstelle, Warnungen auf Grundlage eines Modells allein. Das sind keine Lücken, sondern die Linie des Projekts.

## 9.4 Wie man helfen kann

Der größte Hebel für die nächste Fassung: ein Test auf Windows, ein Test auf einem zweiten Linux, ein Blick auf die Lizenztexte der Quellen, Rückmeldungen zu Quellen, die in der Region fehlen. Alles als Issue mit Angabe von System, Version und Auszug aus `data/logs/`.
