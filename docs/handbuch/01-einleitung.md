# 1 Einleitung: wozu es das gibt

Wer an einem Dienstagmorgen von Irrel nach Echternach fährt, schaut vorher auf drei Dinge: ob die Sauer nach den Regentagen noch im Bett liegt, ob vor Wasserbillig wieder Stau steht und ob irgendwo eine Warnung gilt, die man sonst erst im Radio hört. Drei Seiten, drei Apps, vier Quellen. Alle Daten sind öffentlich, aber sie liegen an verschiedenen Orten und sprechen verschiedene Sprachen.

**Landblick - RLP** legt sie auf eine Karte. Es ruft offene Datenquellen ab (Warnungen, Wetter, Pegel, Verkehr, Luft, Strahlung, Erdbeben, regionale Meldungen), schneidet sie auf Rheinland-Pfalz plus 80 Kilometer Umland zu und zeigt sie so, dass an jedem Wert dransteht, woher er kommt, wie alt er ist und unter welcher Lizenz er steht. Wenn eine Quelle ausfällt, sagt die Kachel das, statt eine leere Fläche zu zeigen.

Dieses Handbuch beschreibt Version **1.0.0-alpha.1**. Es richtet sich an drei Leserinnen und Leser: wer die Karte benutzt (Kapitel 3), wer sie betreibt (Kapitel 2 und 6) und wer sie später weiterentwickeln oder warten muss (Kapitel 5, 8 und 10). Kapitel 9 sagt ehrlich, was noch nicht geht.

## 1.1 Was es ist

- Ein **Lagebild aus offenen Daten**: Ereignisse (Warnung, Sperrung, Stau, Beben, Brandverdacht), Messwerte (Pegel, Wetter, Luftgüte, Strahlung) und Wegmarken (Haltestellen, Tankstellen, Einrichtungen) auf einer eigenen Karte.
- Ein **Werkzeug zum Selberbetreiben**: eine Sammelstelle (Python), die Quellen abruft und fertige JSON-Dateien schreibt, plus eine statische Webseite, die diese Dateien liest. Es braucht keinen Anwendungsserver, keine Cloud und keine Datenbank im Netz.
- Ein **Beispiel dafür, was mit freien Daten, lokaler Hardware und sauberem Engineering geht**, ohne dass jemand beobachtet wird.

## 1.2 Was es nicht ist

Es ist **kein amtliches Warnsystem** und ersetzt weder NINA noch KATWARN noch die Leitstelle. Im Notfall gilt die 112. Dieser Satz steht auf jeder Seite im Fuß, weil er der wichtigste ist.

Es ist auch **kein Überwachungswerkzeug**. Es gibt keine Personensuche, keine Profile, keine Adressrecherche. Das Wort „OSINT“ (Open Source Intelligence) stand im Arbeitstitel; gemeint war immer das Lagebild, nicht das Ausforschen. Anfragen, die auf eine bestimmte Person, Adresse oder einen Account zielen, gehören nicht in dieses Projekt.

## 1.3 Leitplanken

Diese Regeln sind nicht verhandelbar. Sie stehen so in der Projektanweisung und in den Tests, und jede Erweiterung wird daran gemessen.

1. **Ereignisse statt Personen.** Gespeichert und angezeigt werden Orte, Zeiten, Themen und Zahlen. Keine Klarnamen, keine Nutzerprofile, keine Bilder von Personen. Bei Fluginformationen wird nur eine Klasse (zivil, militärisch, Hubschrauber) gespeichert, nie Kennzeichen oder Kennung.
2. **Offene Daten, offene Lizenzen.** Jede Quelle hat einen Eintrag im Quellenregister mit Lizenz und Namensnennung. Ohne Eintrag läuft kein Sammler. Wo die Bedingungen unklar sind, bleibt die Quelle aus.
3. **Lokal zuerst.** Betrieb auf eigener Hardware oder bei einem EU-Hoster. Die Karte kommt aus eigenen Kacheln, nicht aus einem Kartendienst. Die Suche läuft im Browser.
4. **Herkunft immer sichtbar.** Jede Kachel und jede Meldung zeigt Quelle, Abrufzeit und Alter. Alte Daten werden als alt markiert, nicht versteckt.
5. **Ehrlich bei Unsicherheit.** Schätzungen sind als Schätzungen gekennzeichnet (etwa die Abflussbahnen bei Starkregen). Es gibt keine Warnung, die nur eine Rechnung behauptet.
6. **Ausfallsicher.** Fällt eine Quelle aus, bleibt der Rest stehen. Die Kachel sagt „Quelle nicht erreichbar seit …“.
7. **Kein Amtsersatz.** Siehe oben.

Dazu kommt eine Besucherregel: keine Cookies außer technisch nötigen, kein Tracking, keine Skripte, Schriften oder Kacheln von Dritten. Die einzige Ausnahme sind die Kartendienste der Landesämter, die erst nach ausdrücklicher Bestätigung im Menü geladen werden (Kapitel 3.7 und 7).

## 1.4 Das Gebiet

Das Gebiet steht fest in `region.yaml`: die Landesgrenze von Rheinland-Pfalz (BKG VG250) plus 80 Kilometer nach außen, als Polygon. Der Kasten reicht grob von 48,25 bis 51,66 Grad Nord und 5,0 bis 9,6 Grad Ost, etwa 330 mal 380 Kilometer. Darin liegen unter anderem das Saarland, Luxemburg, Lothringen bis Metz, Ostbelgien bis Lüttich, Aachen, Köln, Frankfurt, Mannheim und Karlsruhe. Die Startansicht bleibt Irrel; Entfernungen werden von dort angegeben.

Quellen kommen auf Deutsch, Französisch und Englisch, die Luxemburger zum Teil mehrsprachig. Nicht jede Quelle deckt das ganze Gebiet: Luxemburg, Rheinland-Pfalz und Ostbelgien liefern nur dort Daten, bundesweite Quellen (Deutscher Wetterdienst, NINA, Autobahn) überall in Deutschland. Die Quellenübersicht (Kapitel 4) nennt den Bezug je Quelle.

## 1.5 Wie es dazu kam

Das Projekt begann als Schaufenster der CTW Computer-Irrel GmbH für Datenpipelines, Betrieb und Oberfläche rund um Irrel, mit einem Kreis von 120 Kilometern. Seit dem 9. Oktober 2026 ist es ein privates Open-Source-Projekt von Thorsten Schleicher und wächst in den Phasen R0 bis R7 auf die Landesfläche (Architekturentscheidung 0001, `docs/adr/0001-region-rlp.md`). R0 bis R5 sind abgeschlossen, R6 (Betrieb und Härtung) läuft, R7 (Abnahme) steht aus. Der aktuelle Stand steht im README.

## 1.6 Was „alpha“ heißt

Die Version 1.0.0-alpha.1 läuft, ist aber nicht abgenommen. Offen sind die rechtliche Prüfung vor einem öffentlichen Start, der Dauerbetrieb über sieben Tage ohne Eingriff (R6), die Bestätigung einiger Lizenztexte an der Primärquelle und Erfahrungen auf Windows. Wer die Seite öffentlich ins Netz stellt, tut das auf eigene Verantwortung, und das Impressum und die Datenschutzerklärung müssen vorher zur eigenen Lage passen.

## 1.7 Lizenz und Kontakt

Der Code steht unter der **GNU General Public License Version 3** (Datei `LICENSE`). Die Daten gehören ihren Betreibern und stehen unter den Lizenzen, die das Quellenregister und die Seite „Quellen und Lizenzen“ nennen. Die Karte beruht auf OpenStreetMap-Daten (© OpenStreetMap-Mitwirkende, ODbL). Die Piktogramme der Oberfläche stammen von uxwing.com; ihre Lizenz erlaubt den Einsatz in einer Webseite, nicht die Weitergabe, deshalb liegen die Dateien nicht im Repository und nicht in diesem Release (Kapitel 6.9).

Kontakt: Thorsten Schleicher, thorin.eifel@icloud.com. Projektseite: https://github.com/thorin-eifel/maps
