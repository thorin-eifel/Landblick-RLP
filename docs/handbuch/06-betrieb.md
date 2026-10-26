# 6 Betrieb

Dieses Kapitel beschreibt, wie Landblick dauerhaft läuft. Die ausführliche Betriebsanleitung mit allen Einzelheiten zu Karten, Quellen und Desktop-App steht in `docs/betrieb.md`; hier steht, was man für den Alltag braucht.

## 6.1 Die Jobs

Ein laufendes Landblick besteht aus mehreren kleinen Aufgaben, jede für sich ausfallbar:

| Job | Takt | Aufgabe |
|---|---|---|
| zyklus | alle 5 Minuten | fällige Quellen abrufen, danach Export schreiben |
| spaet | alle 30 Minuten | langsame Quellen (große Abrufe, OpenStreetMap) |
| backup | täglich 03:15 | Datenbank online sichern, Prüfsumme prüfen, 14 Stände behalten |
| health | alle 10 Minuten | Gesundheitsprüfung, Exit-Code für Monitoring |
| web | dauernd | lokaler Webserver für `web/` |
| live | dauernd | Dienst für schnelle Quellen (Flugverkehr) |
| dauerlauf | alle 10 Minuten (optional) | Messpunkt für den 7-Tage-Lauf |

Der Zyklus sperrt sich selbst: Läuft der vorige noch, überspringt der neue. Eine verwaiste Sperre gilt nach 30 Minuten als tot. Jeder Job schreibt in eine eigene, rotierende Logdatei unter `data/logs/`. Die Desktop-App schreibt entsprechend nach `<Datenordner>/logs/dienst.log` (unter Windows `%APPDATA%\de.thorin.landblick\logs\`), weil sie dort ohne Konsole läuft.

## 6.2 Aufgaben starten: Windows, Linux, macOS

Der Installer (Kapitel 2) legt die Jobs je nach System an:

- **Windows:** Aufgabenplanung, Ordner „Landblick“, versteckt, ohne Konsolenfenster. Dauerprozesse starten bei der Anmeldung (bei `-System` beim Systemstart) und werden bei Absturz neu gestartet.
- **Linux:** systemd-Einheiten (Benutzerebene mit `loginctl enable-linger`, oder systemweit mit `--system`).
- **macOS:** launchd-Plisten `de.thorin.landblick-<job>` im Benutzerverzeichnis.

## 6.3 Gesundheitsprüfung

`python tools/gesundheit.py` fragt den Zustand ab und beendet sich nach Nagios-Art:

| Exit-Code | Bedeutung |
|---|---|
| 0 | in Ordnung |
| 1 | Warnung: Quelle veraltet oder ausgefallen, Export älter als 20 Minuten |
| 2 | kritisch: Datenbank oder Export fehlt, Export älter als 60 Minuten, mindestens die Hälfte der Quellen ausgefallen |
| 3 | die Prüfung selbst ist fehlgeschlagen |

Die Prüfung öffnet die Datenbank nur lesend. Sie zeigt den Zustand je Quelle und je Region (aus dem Regionskennzeichen der aktiven Ereignisse). Mit `--json` entsteht eine maschinenlesbare Fassung. Die Zustände sind dieselben wie auf der Statusseite: `ok`, `pending`, `degraded`, `stale`, `down`, `disabled`.

## 6.4 Zustände einer Quelle

- **down:** noch nie erfolgreich oder mindestens drei Fehlschläge in Folge.
- **stale:** letzter Erfolg älter als das Dreifache des Intervalls.
- **degraded:** läuft, aber mit Teilfehlern.
- **ok:** alles in Ordnung.
- **pending:** noch kein erster Abruf.
- **disabled:** im Register abgeschaltet.

Nach fünf Fehlschlägen in Folge pausiert der Sammler für 15 Minuten (Schutzschalter), damit eine tote Quelle nicht im Takt belästigt wird.

## 6.5 Backup

`python tools/backup.py --out data/backup --keep 14 --verify-after` sichert die Datenbank im laufenden Betrieb (SQLite-Onlinekopie), schreibt neben die Datei eine Beschreibung mit SHA-256, Größe und Tabellenzahlen und prüft sie. `--verify` prüft nur die letzte Sicherung. Ein Backup, das nie zurückgespielt wurde, ist kein Backup: Wiederherstellen heißt, die Datei an die Stelle von `data/landblick.sqlite` zu kopieren, während alle Jobs gestoppt sind.

## 6.6 Der Dauerlauf (R6)

Phase R6 verlangt sieben Tage Betrieb ohne Handeingriff. `tools/dauerlauf.py` hält dafür alle zehn Minuten einen Messpunkt fest (Quellenzustand, Exportalter, Größe der Datenbank) in `data/dauerlauf.jsonl`. Handeingriffe werden mit `note` vermerkt. Der Bericht (`report --out docs/rlp/r6-bericht.md`) prüft drei Kriterien: mindestens sieben Tage, keine Lücke über 30 Minuten, kein vermerkter Eingriff. Erst danach gibt der Betreiber R6 frei. Der Lauf ist, Stand dieses Handbuchs, noch nicht abgeschlossen.

## 6.7 Updates

Abhängigkeiten sind gepinnt (`requirements.txt`, `requirements-dev.txt`, `package-lock.json`). Die CI führt `pip-audit` und `npm audit --audit-level=high` aus. Aktualisieren heißt: neue Fassung entpacken oder `git pull`, `install.py` erneut aufrufen (er ist wiederholbar und lässt `.env` und Daten unberührt), `tools/gesundheit.py` prüfen.

## 6.8 Fehlersuche: „Sammler kaputt“

1. `python tools/gesundheit.py` – welche Quelle, welcher Zustand?
2. Log der Quelle: `data/logs/zyklus.log`, nach der Kennung suchen.
3. Einzeln abrufen: `python -m app.collect --only <id> --log-level DEBUG`.
4. Antwort des Anbieters prüfen (Adresse im Register, Schemaänderung?). Die Testdaten unter `tests/fixtures/` zeigen, wie die Antwort einmal aussah.
5. Bleibt die Quelle tot: `aktiv: false` im Register, Hinweis ins `lizenz_hinweis`, weiterarbeiten. Der Rest läuft ohnehin.

## 6.9 Symbole und Lizenz der Bilddateien

Die Karte nutzt Symbole aus dem Ordner `web/icons/`. Sie stammen aus Maki, Temaki und OpenStreetMap Carto (alle gemeinfrei, CC0); Wetter- und Messzeichen sind eigene Zeichnungen. Alle liegen im Repository und in den Installern, ein eigener Schritt ist nicht nötig. Herkunft je Datei: `web/icons/README.txt`.

## 6.10 Windows: Ablauf und Prüfliste

Der Installer wurde unter Linux durchgespielt. Unter Windows ist er noch ungetestet; das ist die ehrliche Lage. Der Ablauf:

1. PowerShell öffnen (normale Rechte genügen), in den entpackten Ordner wechseln.
2. `.\install.ps1 -Kontakt "name@example.org"`. Findet das Skript kein Python 3.11, nennt es den Weg; mit `-PythonInstallieren` installiert es per winget.
3. Der Erstlauf holt alle Quellen und schreibt den Export (dauert mehrere Minuten).
4. `.\install.ps1 -Status` zeigt die Jobs in der Aufgabenplanung.
5. Browser: `http://127.0.0.1:8080`.

Die Prüfliste für den Test steht in `docs/betrieb.md` unter „Windows-Test: Checkliste“. Rückmeldungen dazu sind der wichtigste Beitrag zur nächsten Fassung.
