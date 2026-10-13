# 7 Sicherheit und Datenschutz

Datenschutz steht in diesem Projekt vor Korrektheit, Korrektheit vor Stabilität, Stabilität vor Optik. Ein Merkmal, das nur mit personenbezogenen Daten funktionieren würde, wird nicht gebaut.

## 7.1 Grundsatz: Ereignisse statt Personen

Gespeichert und angezeigt werden Orte, Zeiten, Themen und Zahlen. Nicht gespeichert werden Klarnamen aus sozialen Netzen, Nutzerprofile, Bilder von Personen, Kennzeichen, Adressen von Privatpersonen. Anfragen, die auf eine bestimmte Person, eine Adresse oder ein Konto zielen, gehören nicht in dieses Projekt.

Wo Quellen Freitext liefern (etwa Warnmeldungen), wird der Text vor dem Speichern bereinigt: HTML entfernt, Länge begrenzt. Das Themenradar zählt Themen, nicht Menschen. Von Mastodon werden nur Zählungen der letzten 24 Stunden je Regions-Hashtag und eine Rangliste begleitender Hashtags gespeichert; ein begleitendes Hashtag erscheint erst, wenn mindestens drei verschiedene Konten es genutzt haben. Texte, Konten, Bilder und Links werden nicht gelesen oder gespeichert, Beiträge mit Inhaltswarnung fallen ganz weg. Bluesky ist nicht eingebunden (die öffentliche Suche verlangt Anmeldung).

## 7.2 Besucher der Oberfläche

- Kein Tracking, keine Drittanbieter-Skripte, keine Cookies (der Code setzt keine).
- Keine externen Schriften, Bibliotheken oder Kacheln; alles kommt vom eigenen Server.
- Eine Content-Security-Policy erlaubt für Skripte, Stile, Bilder, Schriften und Verbindungen ausschließlich die eigene Herkunft. Einzige Ausnahme sind die fünf Hosts der Landesdienste (siehe 7.3), und die nur in der Richtlinie der Kartenseite.
- Links aus Fremdinhalten tragen `rel="noopener noreferrer"`. Fremdtexte werden escaped, nicht als HTML eingesetzt.
- Der mitgelieferte Webserver protokolliert ohne Client-IP (Standardmeldungen sind überschrieben). Bei einem fremden Hoster entstehen Zugriffsprotokolle dort, nach dessen Regeln.

## 7.3 Die Zustimmungsschranke

Die Ebenen aus den Landesdiensten (LGB und weitere Stellen) kommen nicht von Landblick, sondern vom jeweiligen Kartendienst. Ein Abruf verrät dem Dienst die IP-Adresse der Besucherin. Deshalb ruft die Seite diese Dienste erst nach ausdrücklicher Zustimmung ab, die Quelle steht dabei im Klartext. Die Content-Security-Policy erlaubt diese Hosts zwar, abgerufen wird aber erst, nachdem das Skript die Zustimmung festgestellt hat; ohne sie geht keine Anfrage hinaus. Die Zustimmung wird nicht gespeichert, sie gilt bis zum Neuladen der Seite. Die Desktop-App hat eine eigene Schranke (`web/js/desktop-gate.js`).

## 7.4 Sicherheit im Betrieb

- Keine Zugangsdaten im Code, im Repository oder in Logs. Schlüssel (Tankerkönig, NASA FIRMS, Zugangsdaten des Webspace) stehen in `.env`, die nicht eingecheckt wird und auf Unix-Systemen Rechte 600 bekommt.
- Eingaben werden validiert (Geometrien, Zeiträume, Filter); SQL läuft mit Parameterbindung; kein `eval` auf externe Daten.
- Rechte sind klein gehalten: Sammler lesen aus dem Netz und schreiben in die Datenbank, sonst nichts. Das Frontend liest nur.
- Der lokale Webserver bindet standardmäßig an `127.0.0.1`. Wer ihn im Netz erreichbar machen will, setzt `--bind` bewusst und stellt ihn hinter einen Proxy mit TLS.
- Abhängigkeiten sind gepinnt, die CI prüft sie auf bekannte Lücken.
- Kein Schlüssel und kein Passwort wird in Dialoge, Logs oder Berichte geschrieben; der Installer fragt nach der Kontaktadresse, nie nach Kennwörtern.

## 7.5 Künstliche Intelligenz

Landblick enthält in dieser Fassung keine Sprachmodelle. Damit entfällt die Angriffsfläche, die Fremdtexte für Modelle bedeuten (Prompt Injection). Sollte später ein lokales Modell hinzukommen (Zusammenfassung, Ortserkennung), gelten diese Regeln: Fremdtexte nur als Daten, kein Werkzeugzugriff, kein Netz, keine Schreibrechte; Ausgaben werden geprüft, bevor sie gespeichert werden; alles, was ein Modell erzeugt, ist als solches gekennzeichnet, mit Quelle und Sicherheitsgrad. Eine Warnung, die nur ein Modell behauptet, gibt es nicht.

## 7.6 Rechtliches

- **Kein amtliches Warnsystem.** Landblick ersetzt weder NINA noch KATWARN noch die Leitstelle. Im Notfall gilt 112 und die offizielle Warn-App. Der Hinweis steht in der Fußzeile und im Impressum.
- **Urheberrecht.** Medien: Titel, Datum, Link. Keine Volltexte, keine Bilder aus Nachrichtenquellen.
- **Lizenzen.** Namensnennung nach den Bedingungen der Quellen; Übersicht auf der Seite „Quellen“.
- **Plattformbedingungen.** Vor jeder Quelle aus einem sozialen Netz werden Nutzungsbedingungen gelesen und im Register festgehalten. Tragen sie nicht, fliegt die Quelle raus.
- **Datenschutzfolgeabschätzung.** Ein Entwurf liegt vor (`docs/dsfa-entwurf.md`). Er ist knapp, weil die Verarbeitung keine personenbezogenen Daten zum Ziel hat.
- **Endabnahme.** Eine rechtliche Prüfung vor einem öffentlichen Start ersetzt dieses Handbuch nicht. Sie ist offen (Kapitel 9).
