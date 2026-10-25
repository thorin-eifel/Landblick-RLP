# Datenschutzfolgeabschätzung — Entwurf (Phase 1)

Status: Entwurf, dünn wie angekündigt. Rechtliche Endabnahme vor öffentlichem Start durch Berater oder Datenschutzbeauftragte.

## Verarbeitung
Abruf offener Daten (Warnungen, Verkehr, Pegel, Wetter), Speicherung als Ereignisse und Messwerte, Anzeige in einer Web-App.

## Personenbezug
| Quelle | Personenbezug möglich? | Maßnahme |
|---|---|---|
| NINA (BBK) | Freitext behördlicher Warnungen; enthält gelegentlich Behörden-Kontaktdaten, keine Privatpersonen | Text auf 700 Zeichen gekürzt, HTML entfernt |
| DWD WFS, Bright Sky | nein | — |
| PEGELONLINE | nein | — |
| Autobahn-API | Verkehrsmeldungen ohne Personen; keine Kamerabilder eingebunden | Kameras bewusst ausgeschlossen |

Social-Media-Quellen, Telegram, Kamerabilder, Fotos: **nicht Teil von Phase 1**.

## Auslieferung
Keine Cookies, keine Drittanbieter, keine externen Schriften/Kacheln. Die Anwendung läuft auf dem Rechner der Nutzerin; die Oberfläche kommt von einem lokalen Dienst auf 127.0.0.1. Es gibt keinen Hoster, keine Zugriffsprotokolle und keine Besucherdaten.

## Abruf der Quellen
Der Rechner ruft die Quellen laut Register ab und schreibt die Ergebnisse (Ereignisse, Messwerte, Quellenstatus) in seine eigene Datenbank und den Exportordner. Nichts verlässt den Rechner. Kontaktadresse im User-Agent gegenüber den Quellen ist eine Funktionsadresse, keine Personenadresse.

## Risiken und Restrisiko
Gering. Offen: Prüfung der Freitexte aus NINA im Echtbetrieb (Stichprobe), Lizenz- und Nutzungsbedingungen je Quelle.
