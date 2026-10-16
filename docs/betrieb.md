# Landblick - RLP

> **Hinweis:** Diese Betriebsanleitung beschreibt den Stand vor dem Umbau auf Rheinland-Pfalz plus 80 km. Die Fläche kommt jetzt aus `region.yaml` (`app/region.py`); Angaben zu "120 km", Kartengrößen und Kacheln werden in R2 bis R5 angepasst. Der aktuelle Stand steht in der `README.md`. Launchd-Labels und Bundle-Kennung heißen noch `de.ctw.osint`: Umbenennen würde das Datenverzeichnis der Desktop-App verschieben und ist deshalb nicht erfolgt.

Die aktuelle Lage rund um unsere Heimat. Privates Open-Source-Projekt (bis Oktober 2026 ein Schaufenster der CTW Computer-Irrel GmbH).

Regionales Lagebild aus offenen Daten für die Südeifel und ihre Nachbarregionen (zurzeit 120 km um Irrel; Ziel ist Rheinland-Pfalz plus 80 km, siehe `docs/rlp/plan.md`): Warnungen, Verkehr, Pegel, Wetter. Kein Tracking, keine US-Cloud, kein Überwachungswerkzeug: gespeichert werden Orte, Zeiten und Zahlen, keine Personen.

Stand: **Phase 1 (MVP)**. Kein amtliches Warnsystem, kein Ersatz für NINA oder die Leitstelle.

## Wie es läuft (statisch, für IONOS-Webspace)

Der Webspace führt nur HTML, CSS und JavaScript aus, kein Python. Deshalb zwei Teile:

```
Sammelstelle (ein Rechner des Betreibers, Python, Cron alle 5 Min.)          IONOS-Webspace (statisch)
  Quellen → Collector → Geo-Filter → SQLite → Export → JSON-Dateien ──SFTP──▶ web/data/*.json
                                                                            web/ (HTML, CSS, JS, MapLibre)
                                                                                  ▲
                                                                     Browser holt Dateien, rechnet
                                                                     Zeitfenster und Alter selbst
```

Die Sammelstelle braucht Python 3.11+, Internet und `lftp`. Sie kann jeder Rechner sein, der dauerhaft läuft: ein Server, ein Mini-PC, ein Raspberry Pi. Fällt sie aus, bleibt die Seite stehen und sagt es: Das Frontend rechnet Alter und Zustand gegen die Uhr des Besuchers und zeigt „Datenstand veraltet“, sobald der Export älter als 20 Minuten ist.

## Schnellstart

```bash
# Sammelstelle einrichten
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q && node --test tests/js/rules.test.mjs     # 60 + 4 Tests
cp .env.example .env && chmod 600 .env                         # OSINT_CONTACT eintragen

# Lokal ansehen, ohne Upload
python -m app.collect --once          # alle Quellen einmal
python -m app.export                  # schreibt web/data/*.json, manifest.json, start.json und z/<x>_<y>/ (Zellen, siehe docs/rlp/r4-export.md)
deploy/publish.sh --delta            # lädt nur geänderte Dateien hoch, Manifest zuletzt
python -m http.server 8000 -d web     # → http://localhost:8000

# Seite auf den Webspace (einmalig und bei Änderungen an HTML/JS/CSS)
deploy/publish.sh --site --dry-run
deploy/publish.sh --site

# Dauerbetrieb: Cron alle 5 Minuten (Vorlage: deploy/crontab.example)
deploy/run-cycle.sh                   # abrufen (nur Fälliges) → exportieren → hochladen
```

## Einrichtung IONOS

1. **SFTP-Zugang** im IONOS-Kundencenter anlegen (Hosting → SFTP & SSH). Host, Benutzer und Passwort bzw. SSH-Schlüssel in `.env` eintragen: `IONOS_SFTP_HOST`, `IONOS_SFTP_USER`, `IONOS_SFTP_KEY` (oder `IONOS_SFTP_PASSWORD`), `IONOS_REMOTE_DIR`, `PUBLISH_ENABLED=1`.
2. **Host-Schlüssel** einmalig ins `known_hosts`, den Fingerabdruck vorher gegen die Angabe im Kundencenter prüfen: `ssh-keyscan -t ed25519 "$IONOS_SFTP_HOST" >> ~/.ssh/known_hosts`. Das Skript prüft den Schlüssel strikt.
3. **HTTPS** für die Domain im Kundencenter aktivieren (SSL-Zertifikat). Die `.htaccess` leitet auf HTTPS um.
4. **Erster Upload:** `deploy/publish.sh --site`, danach `deploy/run-cycle.sh`.
5. **Prüfen:** `curl -sI https://<domain>/` muss die Header `Content-Security-Policy`, `X-Content-Type-Options` und `Strict-Transport-Security` zeigen. Fehlen sie, wertet der Webspace die `.htaccess` nicht aus. Die CSP steht dann trotzdem als Meta-Tag in jeder Seite; `frame-ancestors` geht nur per Header.
6. **Auftragsverarbeitung:** IONOS verarbeitet die Zugriffsprotokolle. Ohne Vertrag zur Auftragsverarbeitung mit IONOS nicht öffentlich schalten (siehe `docs/dsfa-entwurf.md`).

## Aufbau

| Datei / Ordner | Inhalt |
|---|---|
| `sources.yaml` | Quellenregister. Ohne Eintrag läuft kein Collector. Speist die Seite „Quellen und Lizenzen“. |
| `app/collectors/` | `nina`, `dwd_warnungen`, `brightsky`, `pegelonline`, `autobahn`, Basisklasse `base.py` (Retry, Backoff, Circuit Breaker) |
| `app/collect.py` | Runner: `--once`, `--due` (nur Fälliges, für Cron), `--only`, `--healthcheck` |
| `app/export.py`, `app/payloads.py` | Datenbank → `meta, events, gewaesser, wetter, status, sources` als JSON |
| `web/` | Die Seite: `index.html`, `status.html`, `quellen.html`, `js/`, `css/`, `geo/`, `vendor/maplibre-gl/`, `.htaccess` |
| `web/js/rules.js` | Zeitfenster und Quellenzustand, rechnen im Browser gegen die aktuelle Uhr |
| `deploy/` | `run-cycle.sh`, `publish.sh`, `crontab.example` |
| `tools/` | `backup.py`, `build_orientation.py` (Kreisgrenzen für die Karte) |
| `tests/` | Python-Tests, `tests/js/` (Node), `fixtures/` mit echten Antworten |

Die Sammelstelle liest aus dem Netz und schreibt in ihre Datenbank und den Exportordner, sonst nichts. Der Webspace enthält nur die Seite und die fertigen JSON-Dateien: keine Datenbank, keine Zugangsdaten, kein Code, der etwas ausführt.

## Das Quellenregister (`sources.yaml`)

Pflichtfelder je Quelle: `id, name, betreiber, url, lizenz, namensnennung, intervall, ratenlimit, auth, geo_bezug, datenschutz_risiko, aktiv, zuletzt_geprüft, collector`. Dazu `params`, `lizenz_geprueft` und optional `erstlauf` (`spaeter` für große, langsame Abfragen: die Desktop-App holt sie erst nach dem ersten Export im Hintergrund; derzeit die fünf OSM-Quellen). Steht dort `false`, wurde der Endpunkt live getestet, der Lizenztext aber noch nicht an der Primärquelle bestätigt. Die Seite „Quellen und Lizenzen“ zeigt das offen an. **Vor dem öffentlichen Start muss jede Zeile auf `true`.**

Neue Quelle: erst Nutzungsbedingungen, Lizenz und Ratenlimit klären, dann Registereintrag, dann Collector (Vorlage: `pegelonline.py`), Fixture mit echter Antwort, Test.

## Ereignisse und Messwerte

Ereignisse (Warnung, Verkehr, Verkehrslage, Flug) tragen `source_id, type, title, summary, severity, confidence, geometry, region_tag, valid_from, valid_to, fetched_at, raw_ref, ai_generated, model` und optional `attrs` (Art, Verzögerung, Tempo, Kurs; nie Kennungen). Messreihen (Pegel, Wetter) liegen in eigenen Tabellen. Schweregrade: `info, notice, warning, critical`; `critical` (rot) gibt es nur bei CAP `Severe`/`Extreme`.

Snapshot-Semantik: Ein Collector liefert die vollständige aktive Menge seiner Quelle, was fehlt, wird inaktiv. Nur bei **vollständigem** Abruf. Ein halber Abruf (eine Region oder Autobahn nicht erreichbar) schreibt, räumt aber nichts ab.

Zeitfenster („Jetzt“, 24 Std., 7 Tage): Der Export liefert die Obermenge für 7 Tage, der Browser filtert. Die Regel steht zweimal (`app/db.py`, `web/js/rules.js`), beide sind getestet.

## Betrieb

### Runbook: „Collector kaputt“

1. `https://<domain>/status.html` öffnen: Zustand, letzter Erfolg, Fehler in Folge, Fehlertext, letzte Läufe. Steht dort „Export erzeugt vor … Std.“ in Orange, liegt das Problem bei der Sammelstelle oder beim Upload, nicht bei einer Quelle.
2. Auf der Sammelstelle: `python tools/gesundheit.py` zeigt, welche Quelle in welcher Region betroffen ist. Dann `tail -n 100 /var/log/osint-cycle.log` (systemd: `journalctl -u osint-cycle -n 100`). Details einer Quelle: `.venv/bin/python -m app.collect --once --only <id> --log-level DEBUG`.
3. Häufige Ursachen:
   - **HTTP 4xx**: Endpunkt oder Parameter geändert. Doku des Betreibers lesen, Fixture neu aufnehmen, Collector anpassen.
   - **„Schlüssel … fehlt“ / „ohne 'features'“**: Schema geändert. Der Collector rät nicht, er meldet. Fixture ersetzen, Test rot sehen, dann fixen.
   - **Timeout, 5xx, 429**: Quelle down oder drosselt. Retry mit Backoff läuft, nach 5 Fehlläufen pausiert der Collector 15 Minuten (Circuit Breaker). Abwarten oder Intervall erhöhen.
   - **Upload schlägt fehl**: `deploy/publish.sh --data` von Hand laufen lassen. Meist Zugang, Host-Schlüssel oder Netz. Der nächste Cron-Lauf versucht es erneut.
4. Quelle vorübergehend abschalten: `aktiv: false` in `sources.yaml`.

Bei Ausfall bleibt die Seite stehen: „Quelle nicht erreichbar seit …“, die letzten guten Daten sind sichtbar und als veraltet markiert (Chaos-Test in `tests/test_payloads_export.py`).

### Gesundheitsprüfung

`python tools/gesundheit.py` fasst den Zustand in einer Zeile pro Region zusammen und endet mit einem Nagios-Exit-Code: 0 ok, 1 Warnung, 2 kritisch, 3 Prüfung selbst kaputt. Die Zustände je Quelle kommen aus derselben Regel wie die Statusseite (`app/payloads.py`, gespiegelt in `web/js/rules.js`). Region ist der `region_tag` der aktiven Ereignisse einer Quelle; Quellen ohne aktive Ereignisse stehen unter „ohne“. Kritisch ist es, wenn die Datenbank oder der Export fehlt, der Export älter als 60 Minuten ist oder mindestens die Hälfte der Quellen ausgefallen ist. `--json` liefert dasselbe maschinenlesbar, die Schwellen stehen im Kopf des Skripts. Das Skript schreibt nichts.

### Zeitplan

Drei Wege, derselbe Inhalt: Cron (`deploy/crontab.example`), launchd auf dem Mac (`deploy/de.ctw.osint-*.plist`), systemd auf Linux (`deploy/systemd/`). Kein Docker.

systemd, einmalig als root, Pfad `/opt/osint` und Benutzer `osint` in den Units anpassen:

```
cp deploy/systemd/osint-*.{service,timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now osint-cycle.timer osint-backup.timer osint-health.timer
systemctl list-timers 'osint-*'
journalctl -u osint-cycle -n 50
```

Der Zyklus läuft alle fünf Minuten, die Sicherung um 03:15 (mit Rückspielprobe), die Gesundheitsprüfung alle zehn Minuten. Die Units laufen ohne Rechte außer Schreiben in `data/` und `web/data`. Schlägt `osint-health` mit „kritisch“ an, steht die Unit in `systemctl --failed`; eine Benachrichtigung hängt man bei Bedarf per `OnFailure=` an.

### Backup

`tools/backup.py` sichert die Datenbank der Sammelstelle (Online-Backup, Integritätsprüfung, 14 Stück, täglich 03:15). Zu jeder Sicherung liegt eine `.sqlite.json` mit SHA-256, Größe und Zeilenzahl je Tabelle.

Wiederherstellungstest: `python tools/backup.py --verify` spielt die neueste Sicherung in einen Wegwerf-Ordner zurück, prüft Prüfsumme, `PRAGMA integrity_check`, die Zeilenzahlen gegen die Prüfsummendatei und ob die Anwendungsschicht die Kopie lesen kann. Der Test läuft nach jeder Sicherung mit und kippt bei jeder Abweichung. Das ersetzt nicht die Probe von Hand vor dem Livegang: einmal wirklich zurückspielen, `python -m app.export` laufen lassen, Seite ansehen.

Wiederherstellen im Ernstfall: Zyklus pausieren (Timer stoppen oder `launchctl bootout`), neueste Sicherung als `data/osint.sqlite` zurückkopieren (alte `-wal`/`-shm`-Dateien daneben löschen), `python tools/backup.py --verify` zur Kontrolle, Zyklus wieder starten. Der Webspace braucht kein Backup außer dem Projektordner selbst: alles dort lässt sich mit `publish.sh --site` neu aufspielen.

### Chaos-Tests

Was automatisch geprüft wird (`tests/test_betrieb.py`, `tests/test_payloads_export.py`, `tests/test_ausfall_alle_quellen.py`): eine Quelle fällt aus, die Hälfte fällt aus, alle fallen aus, das Netz antwortet mit 503, Zeitüberschreitung, HTML statt Daten oder leerem JSON; der Export bleibt lesbar, die Statusseite zeigt „down“, nichts Altes wird gelöscht. Platte voll beim Export: Temp-Dateien werden weggeräumt, Manifest und alte Dateien bleiben unverändert, der nächste Lauf heilt. Zeitumstellung (29.03. und 25.10.2026, jeweils 01:00 UTC): Zeitfenster und Alter rechnen in UTC, Python und JavaScript haben dieselben Tests.

Von Hand, vor jeder Vorführung: eine wichtige Quelle in `sources.yaml` auf `aktiv: false`, Zyklus laufen lassen, Karte ansehen. Erwartet wird die Kachel „Quelle nicht erreichbar seit …“, der Rest bleibt stehen.

### Updates

Alle Abhängigkeiten sind gepinnt (`requirements.txt`, `requirements-dev.txt`, ein Test prüft das). CI führt `pip-audit` für beide Dateien und `npm audit --audit-level=high` für `desktop/` aus. Rhythmus: einmal im Monat `pip-audit` lokal, Treffer sofort, sonst gesammelt. Ablauf pro Paket: Pin in der Datei ändern, `pytest` und `node --test tests/js/*.test.mjs` laufen lassen, Branch, Pull Request. Nie mehrere Hauptversionen auf einmal. MapLibre liegt unter `web/vendor/` (Version 6.11.2, BSD-3-Clause, Dateiendung auf `.js` geändert, siehe `README.txt` dort); Updates dort von Hand und mit Blick auf die Layer-Ausdrücke (zoom-Interpolation, siehe `web/js/lage/abfluss.js`). Seite geändert: `deploy/publish.sh --site`.

### Dauerlauf (R6)

Gemessen wird nicht geschätzt: `tools/dauerlauf.py sample` hängt alle zehn Minuten eine Probe (Gesundheitszustand, Problemquellen, Exportalter) an `data/dauerlauf.jsonl` (launchd: `de.ctw.osint-dauerlauf.plist`). Jeder Eingriff von Hand wird mit `tools/dauerlauf.py note "…"` vermerkt, auch ein Neustart. Nach sieben Tagen erzeugt `tools/dauerlauf.py report --out docs/rlp/r6-bericht.md` den Bericht: Laufzeit, Anteile OK/Warnung/kritisch, Pausen, längste Störung je Quelle, Vermerke. Bestanden heißt: mindestens sieben Tage, keine Pause über 30 Minuten, kein Vermerk. Die Vorlage und die Reihenfolge stehen in `docs/rlp/r6-dauerlauf.md`. Schläft der Mac, entsteht eine Pause; für den Dauerlauf Ruhezustand abschalten (`caffeinate -s` oder Energiesparen-Einstellung).

## Datenschutz und Sicherheit in Kürze

- Keine personenbezogenen Daten. Externe Texte werden beim Sammeln bereinigt (`app/sanitize.py`), das Frontend setzt sie nur per `textContent`. Ein Test prüft, dass keine Kontaktadresse oder Zugangsdaten in den Exportdateien landen.
- CSP ohne `unsafe-inline`, keine Drittanbieter-Anfragen (per Browsertest geprüft), keine Cookies, keine Speicherung der Ansicht, kein `eval`.
- Zugriffsprotokolle führt der Hoster (IONOS), nicht die Anwendung. Speicherdauer und IP-Kürzung dort prüfen.
- Sammelstelle: keine Zugangsdaten im Code, `.env` mit Rechten 600 und in `.gitignore`. Für den Upload ein eigener SFTP-Zugang, der nur auf den Zielordner beschränkt ist.
- Entwürfe: `docs/dsfa-entwurf.md`; „Datenschutz“ und „Impressum“ sind Platzhalter bis zur rechtlichen Endabnahme.

## Was in Phase 1 nicht funktioniert oder offen ist

1. **Lizenzen nicht bestätigt.** Alle zwölf Quellen laufen, kein Lizenztext ist an der Primärquelle geprüft (`lizenz_geprueft: false`). NINA und Autobahn-API nennen in ihrer OpenAPI-Beschreibung keine Datenlizenz. Am heikelsten ist `hochwasser_rlp`: Die JSON-Schnittstelle der Seite hochwasser.rlp.de ist nicht als offene API dokumentiert und trägt keine Lizenzangabe. Vor jeder öffentlichen Nutzung beim Landesamt für Umwelt RLP anfragen; solange bleibt es ein interner Demo-Betrieb.
2. **DWD-Warnungen nur gegen Doku gebaut.** Am Testtag lag bundesweit keine Warnung vor, die Fixture `dwd_wfs_SYNTHETISCH_landkreise.json` ist nachgebaut. Beim ersten echten Warnfall Feldnamen prüfen und durch eine echte Aufnahme ersetzen. Verifiziert: Endpunkt, Layer, BBox-Achsenreihenfolge (lon,lat; lat,lon liefert leere Antworten).
3. **Kein Live-Test auf IONOS.** Upload, Skripte und Seite laufen gegen einen lokalen SFTP-Server und einen lokalen Webserver. Ob `.htaccess` (Header, MIME-Typen, Umleitung) auf dem Tarif greift, zeigt erst der erste Upload (`curl -sI`, siehe oben).
4. **Kein Server-Push.** Die Seite holt die Dateien alle 60 Sekunden. Die Aktualität ist damit höchstens so gut wie der Cron-Takt (5 Minuten) plus Abrufintervall der Quelle.
5. **Keine Basiskarte.** Radius, Kreisgrenzen (DWD), Orte, Ereignisse. Luxemburg und Belgien haben keine Grenzen. Eigene Tiles folgen in Phase 2 und brauchen auf statischem Webspace Platz (PMTiles-Datei, wenige zehn MB, Range-Requests). Ob IONOS die unterstützt, ist vorher zu klären.
6. **Pegel aus zwei Quellen.** PEGELONLINE (WSV: Mosel, Saar) und die Hochwasservorhersagezentrale RLP (Prüm, Kyll, Sauer, Our, Nebengewässer; WSA-Stellen werden dort verworfen, damit nichts doppelt steht). Eigene Hochwasserstufen gibt es nicht; angezeigt wird der Zustand laut Legende der jeweiligen Quelle. Die Luxemburger Pegel kommen nur soweit, wie die RLP-Seite sie führt.
7. **Baustellen-Zeiträume** stehen nur als Fließtext in der Autobahn-API. Der erste Termin wird per Muster gelesen, sonst bleibt der Beginn leer und der Eintrag „(geplant)“.
8. **Öffentliche Bright-Sky-Instanz** im Dauerbetrieb ist unhöflich. Eigene Instanz in Phase 2 (braucht dann etwas mehr als den Cron-Rechner).
9. **Sammelstelle ist ein Einzelpunkt.** Fällt sie aus, wird die Seite ehrlich veraltet, aber nicht aktueller. Wer das nicht will, braucht einen zweiten Rechner oder Überwachung auf `--healthcheck`.
10. **7-Tage-Dauerlauf** (Definition of Done) steht aus.
11. **Rate Limiting** für eine öffentliche Demo entfällt bei statischen Dateien weitgehend, Missbrauch fängt der Hoster ab. Trotzdem im Vertrag nachsehen.
12. **Offene Punkte aus Abschnitt 12** der Projektanweisung (Name/Domain, Hosting, GPU, Quellenpflege, Luxemburg) sind weiter offen. Hosting ist mit IONOS entschieden; „GPU“ entfällt, solange die lokalen Modelle (Phase 3) nicht kommen.

## Installation auf einem Dauerläufer (Windows, Linux, macOS)

Ein Skript richtet die Sammelstelle auf einem Rechner ein, der durchläuft: `install.ps1` (Windows), `install.sh` (Linux, macOS), beide rufen `install.py` auf. Voraussetzung ist Python 3.11 oder neuer (getestet: 3.11; unter Windows 3.12 empfohlen, bei 3.13 und neuer vorher prüfen, ob alle gepinnten Pakete Räder haben) und der Ordner dieses Repositorys.

```
# Windows (PowerShell, normale Rechte genügen)
powershell -ExecutionPolicy Bypass -File install.ps1 -Kontakt name@example.org -Dauerlauf -RuhezustandAus
# Linux / macOS
./install.sh --kontakt name@example.org --dauerlauf
# Zustand, Entfernen
powershell -File install.ps1 -Status          ./install.sh --status
powershell -File install.ps1 -Deinstall       ./install.sh --deinstall
```

Was passiert, der Reihe nach: `.venv` anlegen und `requirements.txt` installieren; `.env` aus der Vorlage schreiben (Kontakt-Mail für den User-Agent ist Pflicht, die Adresse aus der Vorlage wird nie übernommen); optional die Basiskarte holen (`--karte voll`, rund 1,5 GB von build.protomaps.com, die pmtiles-CLI wird nach Rückfrage geladen, der Lauf ist wiederaufnehmbar); erste Datensammlung und Export (`tools/zyklus.py --erst`: jede Quelle einmal, die langsamen kommen mit dem Zeitplan); Jobs anlegen; prüfen, ob der Webserver antwortet. Quellen mit Zugangsdaten (z. B. Tankerkönig, NASA FIRMS) bleiben ohne Schlüssel in `.env` im Zustand „ausgefallen“; das ist gewollt und steht in der Gesundheitsprüfung.

| Job | Takt | Aufgabe |
|---|---|---|
| zyklus | alle 5 Minuten | fällige Quellen abrufen, exportieren (`tools/zyklus.py`) |
| spaet | alle 30 Minuten | langsame Quellen (große Abfragen), bis 3 Stunden Laufzeit |
| backup | täglich 03:15 | Datenbank sichern, Rückspieltest (`tools/backup.py --keep 14 --verify-after`) |
| health | alle 10 Minuten | Gesundheitsprüfung (`tools/gesundheit.py`) |
| web | dauerhaft | lokaler Webserver auf `--bind`:`--port` (Standard 127.0.0.1:8080) |
| live | dauerhaft | Luftverkehr in kurzem Takt (mit `--ohne-live` aus) |
| dauerlauf | alle 10 Minuten | Probe für das R6-Protokoll (nur mit `--dauerlauf`) |

Jeder Job läuft über `tools/lauf.py`: keine Shell-Umleitung, keine Konsolenfenster unter Windows, Ausgabe nach `data/logs/<job>.log` (rotierend, 5 Dateien zu 2 MB), Umlaute stimmen. Zeitplaner: Windows-Aufgabenplanung (Ordner „Landblick“, versteckte Aufgaben, bei Absturz Neustart nach einer Minute, nie zwei Instanzen), systemd (`landblick-*.timer` und `.service`, Benutzerdienste mit `loginctl enable-linger`, mit `--system` unter `/etc/systemd/system`), launchd (`de.ctw.landblick-*`).

**Läuft es ohne Anmeldung?** Standard sind Aufgaben des angemeldeten Benutzers: Windows führt sie nur aus, solange er angemeldet ist (Sperrbildschirm genügt). Für einen echten Dauerläufer ohne Anmeldung: `-System` in einem Administrator-Fenster, die Aufgaben laufen dann als SYSTEM; unter Linux `sudo ./install.sh --system`. Unter macOS laufen LaunchAgents nur bei angemeldetem Benutzer. **Ruhezustand** stoppt jeden Zyklus: `-RuhezustandAus` stellt unter Windows den Standby im Netzbetrieb ab, anderswo nennt der Installer den Befehl.

**Netz:** Der Webserver hat keine Anmeldung. Mit `--bind 0.0.0.0` ist die Seite im lokalen Netz sichtbar, nie ohne Firewall oder Reverse-Proxy ins Internet stellen. Datenschutz und Quellenregister sind unverändert: ausgehend gehen nur die Abrufe laut `sources.yaml` und, wenn gewählt, der Kartenabruf.

### Windows-Test: Checkliste

Der Windows-Teil ist unter Linux nur durch Tests der erzeugten Aufgabendateien abgedeckt (wohlgeformtes XML, Trigger, Pfade mit Leerzeichen), nicht auf echtem Windows gelaufen. Beim ersten Test prüfen und Abweichungen notieren:

1. Installer endet mit „Fertig. Oberfläche: http://127.0.0.1:8080/“, die Seite zeigt Daten (bei `-Karte keine` nur die Weltkarte als Hintergrund).
2. Aufgabenplanung → Ordner „Landblick“ zeigt sieben Aufgaben (ohne `-Dauerlauf` sechs); „Letztes Ergebnis“ 0x0 bei zyklus, spaet, backup; health darf 0x1 (Warnung) zeigen.
3. `data\logs\zyklus.log` bekommt alle fünf Minuten einen Block „[start] … [ende] Code 0“.
4. Beim Start einer Aufgabe blitzt kein Konsolenfenster auf (`pythonw.exe` plus `CREATE_NO_WINDOW`).
5. `python tools\gesundheit.py` und `python tools\backup.py --verify` laufen durch (SQLite-Pfade mit Laufwerksbuchstaben und Leerzeichen sind abgedeckt, auf echtem Windows aber ungeprüft).
6. Nach Neustart ohne Anmeldung (nur mit `-System`) laufen `web` und `live` wieder an.
7. Windows Defender oder Firewall melden etwas: Python im Ordner `.venv` freigeben, Fund notieren (bei PyInstaller-Programmen bekannt, hier nicht zu erwarten).

Bekannte Grenzen: `lauf.py --timeout` greift nur, solange der Befehl Ausgabe schreibt; die harte Grenze setzt der Zeitplaner (ExecutionTimeLimit bzw. TimeoutStartSec). Der Upload (`PUBLISH_ENABLED=1`) braucht bash und lftp und ist unter Windows nicht vorgesehen. Kartenbau und Landesdaten-Werkzeuge außer `build_region_tiles.py` (Höhenmodell, Gebäude, Abfluss) gehören nicht zum Installer; ihre Ergebnisse (`web/tiles/*.pmtiles`) kopiert man vom Bau-Rechner in `web/tiles/`.

## Sammelstelle auf dem Mac (launchd)

Stand: läuft auf dem Mac des Betreibers, Python 3.11 in `.venv`, Zyklus alle 5 Minuten.

```
launchctl print gui/$(id -u)/de.ctw.osint-cycle | grep -E 'state|last exit'
tail -f ~/Library/Logs/osint-cycle.log
launchctl bootout gui/$(id -u)/de.ctw.osint-cycle      # anhalten
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/de.ctw.osint-cycle.plist   # starten
```

Lokale Ansicht: http://127.0.0.1:8080 (Job `de.ctw.osint-web`, nur localhost).
Fallstricke: Schläft der Mac, steht der Zyklus; die Seite zeigt dann nach 20 Minuten
"Datenstand veraltet". Upload bleibt aus, bis `PUBLISH_ENABLED=1` und die IONOS-Werte in `.env` stehen
(lftp fehlt noch: `brew install lftp`). `OSINT_CONTACT` in `.env` ist noch der Platzhalter.

## Luftverkehr (adsb.lol) und warum keine Schiffe

**Flugzeuge:** Quelle adsb.lol (ODbL 1.0 laut Betreiber, Ratenlimit unveröffentlicht, ein Abruf alle 15 Sekunden in der Live-Schleife, siehe „Live, Stau, Icons“). Die Abfrage sitzt auf der Landesmitte: umschließender Kreis der Region (`query_lat`, `query_lon`, `query_radius_km`, derzeit rund 113 NM, Obergrenze der API 250 NM), danach der Feinfilter auf die Region am Rand. OpenSky ist bewusst draußen: dort braucht jede kommerzielle Stelle, auch bei interner Nutzung, eine Lizenz, und CTW ist eine GmbH. Gespeichert wird nur Position, Höhe, Geschwindigkeit, Kurs und grobe Klasse. Hex-Code, Rufzeichen, Kennzeichen und Typ werden nie geschrieben. Die Ereignis-ID ist ein Hash mit täglich wechselndem Salz (Tabelle `kv_cache`, nicht im Export): innerhalb eines Tages überschreibt der Upsert die Position, es entsteht keine Spur, über Tage lässt sich nichts verknüpfen. Transpondercodes 7500/7600/7700 erscheinen als Hinweis mit Konfidenz 0,4, nicht als Warnung. Die Ebene ist auf der Karte standardmäßig aus. Fixture: `tests/fixtures/adsblol_point_ANONYMISIERT_SYNTHETISCH.json` (echte Struktur, Kennungen ersetzt, Positionen teils erfunden).

**Schiffe: nicht gebaut.** Für Mosel, Saar und Sauer gibt es keine offen lizenzierten Positionsdaten. Inland-AIS der WSV ist nicht öffentlich. aisstream.io nennt keine Nutzungsbedingungen, keinen Umfang für Binnengewässer und keine Zusage zu gewerblicher Nutzung (die Anfragen dazu im Issue-Tracker sind unbeantwortet); außerdem identifiziert die MMSI Schiffe, bei Sportbooten also Halter. Möglich wären: Anfrage an das WSV Trier, ein eigener AIS-Empfänger an der Mosel (dann eigene Daten, keine Lizenzfrage), oder nur Schleusen- und Pegeldaten, die schon da sind.

## Baustellen und Sperrungen RLP (Mobilitätsatlas)

Quelle: WFS `https://maps.mobilitaetsatlas.de/geoserver/ows` (Layer `mwvlw:baustelle`, `mwvlw:verlauf`), derselbe Bestand, den die Karte auf mobilitaetsatlas.de zeigt. Er umfasst Bundes-, Landes-, Kreis- und Gemeindestraßen der Verkehrsbehörden in Rheinland-Pfalz sowie Meldungen aus Luxemburg (`region_tag` LU). Aktualisierung im Dienst alle 10 Minuten, Verzug bis 20 Minuten. Abfrage mit Bounding Box, Feinfilter auf 80 km am Rand.

Entscheidungen: (1) Meldungen der Autobahn GmbH aus diesem Dienst werden verworfen, der Autobahn-Collector liefert sie. (2) Der Verlauf (Linie) ersetzt den Punkt, wo er vorhanden ist. (3) Das Feld `ansprechpartner` (Behörden-Postfächer) wird nie gelesen, im Freitext werden E-Mail-Adressen und Telefonnummern entfernt. (4) Typen: G Vollsperrung und F Fahrtrichtung gesperrt = Warnung, C halbseitig und N Lkw-Sperre = Hinweis, B Einschränkung = Info; `_GEPLANT` bekommt den Zusatz „(geplant)“ im Titel. Umleitungen (`mwvlw:umleitung`) sind noch nicht eingebaut.

Offen: Der Dienst nennt keine Lizenz (Capabilities ohne Fees/AccessConstraints, die Erläuterung ebenfalls). Anfrage an das Mobilitätsatlas-Team, Referat 8702 im Ministerium: mobilitaetsatlas@rlp.de. Der Betreiber weist selbst darauf hin, dass nicht alle Kommunen liefern.

Die Presseseite des LBM (lbm.rlp.de/service/presse-aktuelles) ist keine Datenquelle für die Karte: kein Feed, keine Koordinaten, nur Pressetext. Sie taugt später für das Modul „Meldungen“ (nur Titel, Datum, Dienststelle und Link), das ohne Kartenpunkt auskommt. Phase 2.

## Basiskarte (eigene PMTiles)

Die Karte nutzt keine Kacheln von Dritten. `web/tiles/region.pmtiles` ist ein Ausschnitt des Protomaps-Basiskartenbaus (OSM-Daten, ODbL): Bounding Box 4.63/48.61/8.28/51.08 (120-km-Radius plus Rand), Zoom 0 bis 13 (ca. 285 MB), Luxemburg inklusive. Tiefer als Zoom 13 bricht der Abruf für die ganze Region am Protomaps-Server immer wieder ab, und Hausnummern stehen erst in Zoom 15 in den Kacheln. Darum gibt es `web/tiles/core.pmtiles` (ca. 120 MB): derselbe Build, Kern 5.90/49.49/7.02/50.21 um Irrel (rund 80 x 80 km) mit Zoom 0 bis 15. Nur die Ebenen `buildings` und `address_label` lesen daraus; fehlt die Datei, bleibt die Karte ohne Gebäudedetail. Außerhalb des Kerns gäbe es demnach kaum Gebäude; deshalb gibt es `web/tiles/ring.pmtiles` (ca. 140 MB): derselbe Kartenbau, nur Zoom 14, nur im 120-km-Kreis außerhalb des Kerns (GeoJSON mit Loch, damit nichts doppelt liegt). Das Frontend zeichnet die Gebäudeebenen aus Kern und Ring; fehlt der Ring, fehlen die Umrisse außerhalb des Kerns. Hausnummern gibt es nur im Kern, im Ring nie. Der Ring kam aus einem neueren Protomaps-Build als Region und Kern (die alten Builds liegen nicht mehr am Server); beim nächsten Gesamtbau mit `tools/build_tiles.sh` sind alle drei wieder aus einem Guss. Gebaut mit `tools/build_tiles.sh [JJJJMMTT]` (lädt nur den Ausschnitt per Teilabruf, nicht den Planet; braucht die `pmtiles`-CLI in `tools/bin/`). Das Frontend liest die Datei im Browser per HTTP Range (pmtiles.js, MapLibre); Stil aus `@protomaps/basemaps` mit Option `lang: 'de'` (nur damit liefert die Bibliothek Beschriftungen), ohne Symbol-Layer (POIs, Einbahnpfeile; sie bräuchten Sprite-Bilder). Schrift: nur „Noto Sans Regular“ aus `web/fonts/` (Bereiche 0–511 und Satzzeichen). Hell = Grau, Dunkel = Dunkel.

Ehrlich bei Ausfall: Fehlt die Datei oder kann der Server keine Teilabrufe, bleibt die Karte ohne Basis benutzbar und der Kartenhinweis sagt „Basiskarte nicht verfügbar“.

**Vor dem Produktivbetrieb auf IONOS prüfen:** `python tools/check_range.py https://<domain>/tiles/region.pmtiles` muss „Teilabrufe funktionieren“ melden (Status 206, keine Kompression). `deploy/publish.sh --site` lädt die Dateien mit hoch (beim ersten Mal rund 410 MB, ein Schritt für sich; die Datei ändert sich nur bei neuem Kartenbau). Die `.htaccess` nimmt `.pmtiles` bewusst aus der Kompression aus. Antwortet der Webspace mit 200 statt 206: Kachelverzeichnis (`z/x/y.pbf`) statt einer Datei bauen, das läuft auf jedem Webspace.

Die lokale Ansicht auf dem Mac nutzt `deploy/serve-local.py` (versteht Range), nicht `python -m http.server`.

Offen: Beschriftungen (Straßen, Orte) brauchen Schriftdateien (Glyphen) auf dem Server; Zoom über 13 wird nur hochskaliert; Kartenstand ist der Build vom 29.09.2026, Aktualisierung von Hand.

### Gebäude aus den Hausumringen

Die OSM-Gebäude sind lückenhaft: Um Irrel fehlte beim Abgleich mit dem Liegenschaftskataster gut jedes siebte Gebäude (217 von 1545, meist Garagen und Schuppen, aber auch Wohnhäuser bis 150 m²). Darum gibt es `web/tiles/gebaeude.pmtiles`: in Rheinland-Pfalz die amtlichen Hausumringe (© GeoBasis-DE / LVermGeoRP, dl-de/by-2-0, Daten bearbeitet), außerhalb des Landes (Luxemburg, Saarland, Frankreich, Hessen ...) die OSM-Gebäude aus Kern und Ring, deren Schwerpunkt nicht im Land liegt. Eine Quelle, kein Doppelzeichnen. Zoom 15 trägt alle Umrisse, Zoom 14 nur die ab 40 m² (Umgrenzungsrechteck); darüber zeichnet MapLibre die Zoom-15-Kacheln hochgezoomt. Zoom-14-Kacheln gelten ab Kartenzoom 14, Zoom 15 ab 15 (MapLibre 5 erlaubt bei Vektorquellen nur das Kachelmaß 512; ein früheres `tileSize: 256` am Kern führte dazu, dass der Kern gar nicht lud und um Irrel nur die groben Gebäude aus Zoom 13 standen). Hausnummern bleiben im Kern (`core.pmtiles`).

Bauen (einmal je Datenstand der Hausumringe, rund 5 Minuten, 2 GB Arbeitsspeicher):

```
curl -fLO https://geobasis-rlp.de/data/hu/current/zip/HAUSUMRINGE_RP.zip     # 334 MB, ganz Rheinland-Pfalz
unzip -o HAUSUMRINGE_RP.zip 'gebaeude_hu.*'                                  # .shp und .dbf (aus der .dbf wird nur die Spalte GFK gelesen)
python tools/build_gebaeude_rlp.py --hu gebaeude_hu.shp --core web/tiles/core.pmtiles --ring web/tiles/ring.pmtiles \
    --grenze web/geo/rlp.geojson --out web/tiles/gebaeude.pmtiles
```

Gebäudefunktion: Aus der `.dbf` liest das Werkzeug nur die Spalte `GFK` (ADV-Codeliste, z. B. `31001_3041` Kirche) und ordnet sie in `klasse_von_gfk()` acht Klassen zu (wohnen, wirtschaft, garage, ueberdachung, technik, oeffentlich, religion, sonst). Das Attribut `klasse` steht im MVT neben `kind`; die Farben stehen in `web/js/gebaeude-farben.js` (ein Test hält beide Listen gleich), die Zeichenerklärung zeigt sie. Gebäude aus OSM außerhalb des Landes haben keine Klasse und bleiben weinrot. Der Code `31001_2000` heißt „Gebäude für Wirtschaft oder Gewerbe“, ist aber nach der Größe (Median 56 m²) überwiegend Schuppen und Scheune; die Karte nennt es deshalb so in der Erklärung. Datenschutz: Gemeindeschlüssel, Objektkennung und Kachelnummer der Quelle bleiben unberührt, Adressen und Eigentümer enthält die Quelle nicht. Fehlt die `.dbf`, entsteht die Datei ohne Klassen; fehlt die Datei, zeichnet die Karte wie vorher die OSM-Gebäude aus Kern und Ring. Vermerk steht unter der Karte, auf der Quellenseite und in den Fußzeilen; das Jahr (`GEB_JAHR` in `web/js/lage/zustand.js`) ist das Jahr des Datenbezugs und bei jedem neuen Bezug anzupassen.

### Rechtsklick-Auskunft

Rechtsklick auf die Karte (auf Touchgeräten: Finger lang halten) öffnet ein kleines Fenster mit Höhe (Geländemodell der Karte), Koordinaten (Dezimalgrad, Grad/Minuten/Sekunden, UTM 32 ETRS89), Ort, Gemeinde mit Verbandsgemeinde und Kreis. Code: `web/js/lage/kontext.js` (Fenster) und `web/js/ortsinfo.js` (Punkt in Fläche, UTM; getestet in `tests/js/ortsinfo.test.mjs`). Die Namen kommen aus `web/geo/verwaltung.json`, die der Browser beim ersten Rechtsklick holt (3,3 MB, gz rund 1,2 MB), und aus `web/geo/kreise.geojson` (Kreise außerhalb von Rheinland-Pfalz). Es gibt keine Anfrage an Dritte.

Bauen (bei neuem Datenstand der Verwaltungseinheiten oder des Wohnplatzverzeichnisses, rund 5 Sekunden):

```
curl -fLO https://geobasis-rlp.de/data/inspire-annexi/current/xml/dlkm_au.zip                # 34 MB, Verwaltungseinheiten (GML)
curl -fLO https://geobasis-rlp.de/data/wohnplatz/current/zip/WOHNPLATZVERZEICHNIS_RP.zip     # 0,4 MB, Ortsteile und Wohnplätze
unzip -o dlkm_au.zip; unzip -o WOHNPLATZVERZEICHNIS_RP.zip
python tools/build_verwaltung.py --au dlkm_au.gml --wohnplatz WOHNPLATZ_RP_wohnplcsv.CSV --out web/geo/verwaltung.json --stand "Dezember 2025"
```

Inhalt: 2324 Gemeinden als Flächen (vereinfacht auf rund 5 m, ganzzahlige Deltas), 135 Verbandsgemeinden, 38 Kreise und Städte, 10306 Ortsteile und Wohnplätze (je Gemeinde einsortiert). „Ort“ ist der nächste Ortsteil innerhalb der Gemeinde, Wohnplätze (Höfe, Mühlen) zählen nicht. Das Wohnplatzverzeichnis enthält auch Einwohnerzahlen je Ortsteil; sie werden nicht übernommen. Grenzen: direkt an einer Gemeindegrenze kann der Nachbar treffen (Vereinfachung); außerhalb von Rheinland-Pfalz (Saarland, Luxemburg ...) gibt es keine Gemeinde, nur den Kreis aus `kreise.geojson`. **Gemarkung fehlt**: Der offene Kleindatensatz enthält sie nicht, sie steckt nur in den Flurstückdaten (INSPIRE `dlkm_cp` 1,3 GB, `lb.zip` 1,9 GB).

## Live, Stau, Icons

**Flüge live.** Ein Webspace ohne Server kann nicht schieben, und der Browser darf keine Drittserver anfragen (CSP, Datenschutz). „Live“ heißt deshalb: Die Live-Schleife (`python -m app.live`, launchd-Job `deploy/de.ctw.osint-live.plist`) holt adsb.lol alle 15 Sekunden (Untergrenze 10 s), schreibt nur `data/aircraft.json` und `data/status.json` und lädt sie hoch, wenn `PUBLISH_ENABLED=1` (höchstens alle `OSINT_LIVE_PUBLISH_S`, Standard 30 s; läuft ein Upload noch, wird übersprungen). Der Browser holt `aircraft.json` alle 15 s, solange die Ebene an und der Tab sichtbar ist, und lässt die Flugzeuge dazwischen auf Kurs und Tempo weiterrücken (`advance()` in `rules.js`, rein optisch, nichts wird gemerkt; bei „weniger Bewegung“ im System aus). Der Fünf-Minuten-Zyklus überspringt Quellen mit `params.live` (`--skip-live`; `OSINT_LIVE=0` in `.env` legt sie zurück in den Zyklus). Steht die Schleife, laufen die Punkte nach 90 s ab und die Quelle zeigt „veraltet“. Ratenlimit von adsb.lol ist unveröffentlicht: vor öffentlichem Start nachfragen.

```
python -m app.live --once             # ein Durchlauf zum Testen
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/de.ctw.osint-live.plist
tail -f ~/Library/Logs/osint-live.log
```

**Stau und zähfließender Verkehr.** Kommt aus derselben Autobahn-API (`warning` mit `abnormalTrafficType`): `QUEUING_TRAFFIC` = Stau, `SLOW_TRAFFIC` = zähfließend, `STATIONARY_TRAFFIC` = Stillstand, dazu Verzögerung (Minuten) und Durchschnittstempo. Eigener Ereignistyp `congestion`, gezeichnet als Linie von Anfang bis Ende der Meldung (gerade Verbindung, nur Näherung des Straßenverlaufs). Stau ab 30 Minuten Verzögerung und Stillstand sind `warning`, gewöhnlicher Stau `notice`, zähfließend `info`. Sie erscheinen nicht im Warnband, das bleibt für NINA/DWD/Pegel. Eine eigene Stufe „Stop-and-go“ kennt die API nicht. Der Autobahn-Lauf kommt jetzt alle 3 Minuten (vorher 10). Grenzen: nur Autobahnen (A1, A48, A60, A64), keine Bundes- und Landesstraßen, kein Luxemburg. Die Kennungen tragen den Vermerk INRIX; das gehört in die Lizenzanfrage an die Autobahn GmbH. Fixture: `tests/fixtures/autobahn_A64_warning_STAU_SYNTHETISCH.json` (echte Struktur, Orte verlegt).

**Icons.** Einzige Quelle: uxwing.com. Die Lizenz erlaubt Nutzung in Websites, auch gewerblich, ohne Namensnennung, mit Änderung; verboten sind Weiterverkauf, Weiterverbreitung und Unterlizenzierung. Darum liegen die SVGs nicht im Repository (`.gitignore`), `tools/fetch_icons.sh` holt sie (Rollenname → uxwing-Name steht im Skript). Die fertige Webseite liefert sie aus, das ist Nutzung in einer Website. Nicht in ein öffentliches Repository oder Paket legen. Im HTML als CSS-Maske (`css/icons.css`, Farbe folgt dem Text), auf der Karte als Bitmap (`js/icons.js`: Plakette in Stufenfarbe, Flugzeug mit Umriss). Fehlen die Dateien, fällt die Karte auf Kreise zurück, der Text trägt die Bedeutung.

## Höhenrelief

Schummerung, Höhenfärbung, Höhenlinien (mit Beschriftung der Hauptlinien) und Höhenanzeige unter dem Zeiger.
Datenbasis: Terrarium-Kacheln bis Zoom 14. In Rheinland-Pfalz stammen sie aus dem DGM1 des Landes (LVermGeoRP, 1 m Gitter, dl-de/by-2-0), außerhalb aus den Mapzen Terrain Tiles (AWS Open Data; EU-DEM und SRTM, rund 30 m). Messung bei Irrel: Mapzen weicht vom Landesmodell im Mittel um 9,6 m ab, an Einzelstellen bis 36 m.
Zwei Schritte, beide einmalig und wiederaufnehmbar:

    .venv/bin/python tools/build_dem.py                          # Mapzen Zoom 6 bis 12, ca. 200 MB nach web/tiles/dem-base/ (Rückfall und Außenbereich)
    .venv/bin/python tools/build_dem_rlp.py --check              # zählt: rund 21 000 Landeskacheln, 32 GB Download
    .venv/bin/python tools/build_dem_rlp.py                      # lädt, mittelt auf 4 m (Arbeitsordner _scratch/dgm1, ca. 3 GB), schreibt web/tiles/dem/ Zoom 6 bis 14 (ca. 1,5 GB)
    .venv/bin/python tools/build_dem_rlp.py --budget-s 900       # in Portionen, Exit 2 = Befehl wiederholen
    .venv/bin/python tools/build_dem_rlp.py --keep-raw           # wie oben, legt die 1-m-Rohkacheln zusätzlich in <work>/raw/ ab (rund 22 GB); die Felswände laden dann nicht ein zweites Mal

Die Landesdaten kommen von `geobasis-rlp.de/data/dgm1/` (Dateiliste `meta4/dgm1_tif_07.meta4`, Prüfsummen werden verglichen). Das Werkzeug legt `tiles/dem/meta.json` mit dem Namensnennungstext an (Jahre der Befliegung); die Karte zeigt ihn unten rechts. Außerhalb von RLP sind die Kacheln ab Zoom 13 nur aus Mapzen hochgerechnet (kein Gewinn an Genauigkeit, aber lückenlos). An der Kante der Landesabdeckung weicht Mapzen im Mittel um etwa 10 m vom DGM1 ab. Damit daraus keine sichtbare Stufe (gerade Naht in Schummerung und Höhenlinien) wird, setzt `blend_bias()` den Versatz zwischen beiden Quellen über `FADE_PX` (120 px, rund 730 m bei Zoom 14) nach außen fort und blendet ihn mit cos² aus; Kacheln werden mit gleichem Rand gerechnet, damit Nachbarn ohne Sprung anschließen. Nach einer Änderung daran muss `web/tiles/dem` neu gebaut und das Relief neu gepackt werden (`python tools/build_dem_rlp.py --no-fetch --force --only-gaps`, dann `tools/pack_tiles.py`). Für Luxemburg, Saarland, NRW, Hessen, Baden-Württemberg gibt es eigene offene Geländemodelle, die sich im selben Schema einbauen ließen (noch nicht geprüft, Lizenzen offen).
Die Kacheln liegen nicht im Repository (`.gitignore`) und müssen mit auf den Webspace (`web/tiles/dem/`, inkl. `README.txt` als Prüfdatei und `meta.json`). `dem-base/` und `_scratch/` bleiben lokal.
Höhenlinien rechnet `web/vendor/maplibre-contour` (BSD-3) im Browser in einem Worker (ab Zoom 7, bis 2,5 m Abstand bei Zoom 16); Ziffern kommen aus `web/fonts/` (Noto Sans, OFL).
Fehlt `tiles/dem/README.txt`, bleibt die Karte ohne Relief und läuft normal. Code: `web/js/relief.js`.
Im Menü Geographie (Gelände und Gebäude) gibt es zwei Schalter: „Berge und Täler (Schattierung und Farbe)“ (`relief`) und „Höhenlinien“ (`contours`, mit Beschriftung). Beide laufen über dieselben Höhenkacheln und sind einzeln schaltbar; die Lichtquelle am Zeiger hängt an der Schummerung, die Höhe unter dem Zeiger und die Legende an einem von beiden.
Namensnennung steht auf `quellen.html`. Höhenwerte sind Raster (in RLP ca. 6 m, sonst ca. 30 m), keine Vermessung.

Zoom 15 und 16 aus dem 1-m-Raster (optional, setzt den Rohordner der Felswände voraus):

    .venv-dem/bin/python tools/build_dem_hires.py --raw dgm1-work/raw --out web/tiles/dem --bbox 7.62 50.08 7.92 50.24 --cover

Je Zielkachel wird bilinear im 1-m-Gitter abgetastet (Zoom 15 ca. 3,1 m, Zoom 16 ca. 1,5 m je Pixel), die Höhe auf 1/16 m gerundet (spart rund die Hälfte der PNG-Größe, Schummerung zeigt keine Stufen). Pixel ohne Landesdaten kommen aus der Elternkachel; `--cover` schreibt außerhalb des Landes Kacheln aus der Elternkachel, damit relief.js dort nicht ins Leere fragt. Messung Loreley (Steilgelände): Zoom 15 rund 50 KB/km², Zoom 16 rund 160 KB/km²; `--measure` rechnet vorab. Danach `hires: {"maxzoom": 16}` in `tiles/dem/meta.json` eintragen, erst dann nutzt relief.js die Kacheln (sonst bleibt es bei Zoom 14 mit Überzoom). Höhenanzeige unter dem Zeiger bleibt bei Zoom 14.

### Felswände aus dem DGM1

In RLP stammen Felswände nicht aus OSM, sondern aus dem 1-m-DGM1: `tools/build_klippen_dgm.py` findet die Steilzone (Hysterese 55/47 Grad auf dem um 1,5 m geglätteten Gelände), macht daraus Flächen und leitet je Wand drei Ebenen ab: `wand` (Polygon mit Löchern), `kante` (Oberkante, Wand rechts der Laufrichtung) und `schraffur` (kurze Striche in Fallrichtung, von oben nach unten). `drop` ist die Wandhöhe in m (mindestens 5 m). Ausgabe sind Vektorkacheln Zoom 13 in `tiles/klippen/` (mit `meta.json`, Namensnennung „Daten bearbeitet").

Der Lauf braucht die 1-m-Rohkacheln. Standardmäßig lädt er nur Kilometerkacheln mit Steilhängen im 4-m-Raster samt Nachbarn, mit `--all-tiles` das ganze Land. Rohkacheln liegen komprimiert in `<work>/raw/` (rund 22 GB für RLP), ein Abbruch setzt beim nächsten Aufruf fort. Lief vorher `build_dem_rlp.py --keep-raw` mit demselben Arbeitsordner, sind sie schon da und es wird nichts mehr geladen (Kacheln, die ohne `--keep-raw` entstanden, holt der Lauf nach).

    .venv-dem/bin/python tools/build_klippen_dgm.py --work ~/Claude/OSINT/dgm1-work --out web/tiles/klippen --all-tiles   # RLP: ca. 21 000 Wände, 0,9 Mio. Striche, 24 MB; Download 33 GB, Gesamtlauf rund 3 Stunden
    .venv-dem/bin/python tools/build_klippen_dgm.py --work ... --out ... --bbox 7.70 50.10 7.76 50.14                     # Ausschnitt (Loreley), 20 Sekunden

**Rohdaten aufräumen (zuletzt).** Relief und Felswände hinterlassen im Arbeitsordner (`_scratch/dgm1`) Rohdaten: `raw/` (1-m-Kacheln, rund 22 GB für RLP) und `red/`. Wer lokal installiert, braucht sie danach nicht mehr. `tools/rohdaten_aufraeumen.py` löscht den Ordner erst, wenn alles fertig ist: Relief und Felswände mit Metadaten und Kacheln vorhanden, Basiskarte da, die App antwortet mit 200 und der Export ist lesbar. Ohne `--ja` ist es ein Probelauf, der nur zeigt, was frei würde. Liegt im Arbeitsordner eine Datei `BEHALTEN.txt`, löscht es nichts, bis sie von Hand entfernt wird. Fremde Dateien im Ordner und unsichere Pfade (Home, Projektordner) lehnt es ab. Der Installer (`install.py`) ruft am Ende, wenn der Webserver antwortet und `_scratch/dgm1` existiert, denselben Probelauf auf. Besteht er, fragt der Installer im Terminal, ob gelöscht werden soll; ohne Terminal oder bei Nein bleibt alles liegen. `--ja` löscht nie Rohdaten, dafür gibt es `--rohdaten-loeschen`.

    .venv/bin/python tools/rohdaten_aufraeumen.py          # Probelauf
    .venv/bin/python tools/rohdaten_aufraeumen.py --ja     # prüfen und löschen

Fehlt `tiles/klippen/meta.json`, zeigt die Karte wie bisher die OSM-Klippen. Mit Kacheln werden OSM-Klippen innerhalb von RLP ausgeblendet, außerhalb bleiben sie. Schmale Schluchten (Teufelsschlucht, Felsspalten) fallen durch die Glättung aus der Hysterese heraus. Deshalb sucht `_slots` zusätzlich Spalten: mindestens `--slot-depth` m (Standard 5) tiefer als die Umgebung, Flanken steiler als 40 Grad, Mindestfläche 40 m². Flachere Gräben und Hohlwege bleiben draußen; `--slot-depth 0` schaltet die Suche ab. Das Ergebnis steht in `meta.json` (`slot_depth_m`). Nach einer Änderung der Schwelle muss das ganze Land neu gebaut werden, in ein neues Verzeichnis, dann tauschen. Die Flächen sind abgeleitet, keine Vermessung; künstliche Böschungen (Steinbrüche, Einschnitte) erscheinen ebenfalls, wenn sie höher als 5 m und steiler als 55 Grad sind.

## Weitere Quellen (Umwelt)

| Quelle | Collector | Inhalt | Takt |
|---|---|---|---|
| Hochwasservorhersagezentrale RLP | `hochwasser_rlp` | Pegel (89 Messstellen im Radius), Klassen laut Quellenlegende, Ereignis ab HW-Stufe 2 | 15 min |
| BfS ODL | `bfs_odl` | Ortsdosisleistung (Sonden im Radius), Ereignis erst ab eigener Orientierungsschwelle 0,3 / 1,0 µSv/h | 30 min |
| UBA Luftdaten | `uba_luft` | Luftqualitätsindex und PM10, PM2.5, NO2, O3 (RLP/Saarland), Ereignis ab Index 3 | 30 min |
| EMSC | `emsc` | Erdbeben der letzten 7 Tage, ab M 3,0 Hinweis, ab M 4,0 Warnung; Sprengungen werden verworfen | 15 min |
| DWD Radar | `dwd_radar` | Regenradar als Bild, wird auf dem Mac geholt und mit hochgeladen (`radar.png`) | 5 min |
| MeteoLux (Findel) | `meteolux` | Minutenwerte der Station Findel (CC0): Temperatur, Feuchte, Druck, Wind; Wetter-Reiter, Tabelle „Weitere Messungen“ | 10 min |
| MET Norway | `metno` | zweites Vorhersagemodell (CC BY 4.0), 48 h, im Wetter-Diagramm gestrichelt neben DWD | 60 min |
| Sensor.Community | `sensor_community` | Temperatur und Feuchte von Bürgersensoren, nur als 0,1°-Raster-Median aus mindestens 3 Außensensoren, keine Sensor-IDs gespeichert | 10 min |

Lücken, die man wissen muss: Luxemburg und Frankreich (Cattenom) liefern weder BfS noch UBA; „keine Farbe“ im Radar heißt kein Regen ODER außerhalb der Radarreichweite. Die Sonde Biringen (UBA) liefert keine Daten. Pillow (Radarbild) steht in `requirements.txt`; nach dem Update `pip install -r requirements.txt`.
Tests: `tests/test_collectors_umwelt.py`, `tests/test_wetter_quellen.py` (echte gekürzte Antworten, Abwandlungen sind im Test mit SYNTHETISCH markiert).

## Meldungen, Luxemburg, Indizes, Spritpreise, Themenradar

| Quelle | Collector | Inhalt | Takt |
|---|---|---|---|
| Presseportal (Polizei) | `presseportal` | Überschrift, Ort (aus der Datumszeile), Zeit, Link der Dienststellen Trier und Wittlich; Text wird verworfen, Fahndungen und Vermisste nie übernommen | 10 min |
| Trierischer Volksfreund | `rss_volksfreund` | Schlagzeilen der Rubriken Region und Blaulicht, nur mit Ortsname im Radius; Titel und Link | 15 min |
| Pegel Luxemburg (AGE) | `lu_pegel` | 40 Stationen (Sauer, Our, Alzette, Mosel), CC0, im Gewässer-Reiter; keine Warnstufen der Quelle | 15 min |
| CITA Luxemburg | `cita_lu` | Verkehrsmeldungen DATEX II (Unfälle, Baustellen, Hindernisse), CC0 | 5 min |
| DWD Waldbrand/Grasland | `dwd_waldbrand` | Stationsindex Stufe 1 bis 5 (10 nächste Stationen), Ereignis ab Stufe 3, Umwelt-Reiter | 3 h |
| DWD Pollen/UV | `dwd_gesundheit` | Pollenflug Teilregionen 101/102, UV-Index Station Hahn, Umwelt-Reiter | 60 min |
| Tankerkönig | `tankerkoenig` | Spritpreise deutsche Seite (CC BY 4.0), **inaktiv, bis `TANKERKOENIG_API_KEY` in `.env` steht**, dann `aktiv: true` im Register | 15 min |
| Mastodon | `mastodon_themen` | Themenradar: Beiträge je Regions-Hashtag und begleitende Themen, nur Zählungen, Schwelle 3 verschiedene Konten | 60 min |

Ortszuordnung ohne externen Geocoder: `app/geoparse.py` nutzt das Ortsverzeichnis `app/data/orte.json` (OSM, ODbL, gebaut mit `tools/build_gazetteer.py`). Meldungen ohne erkennbaren Ort im Radius werden verworfen, nicht auf einen Kreismittelpunkt geraten. Neue Ausgabedateien: `indizes.json`, `kraftstoff.json`, `themen.json`.

Bewusst nicht eingebunden: Wort.lu (behält sich Text- und Data-Mining ausdrücklich vor), Bluesky (öffentliche Suche verlangt Anmeldung), Telegram (Projektanweisung), Luxemburger Luftqualität und Spritpreise je Tankstelle (kein offener Datensatz gefunden), Copernicus EMS (nur bei konkretem Einsatz). Lizenz von Presseportal, Volksfreund, DWD Pollen/UV und Mastodon ist im Register mit `lizenz_geprueft: false` vermerkt und vor dem öffentlichen Start zu klären.
Tests: `tests/test_quellen_batch2.py`.

## Ostbelgien, Wallonie, Grand Est

| Quelle | Collector | Inhalt | Takt |
|---|---|---|---|
| Hub'eau Hydrométrie | `hubeau_pegel` | Wasserstände Nordlothringen (Mosel, Nied, Orne, Seille), mm zu cm, im Gewässer-Reiter; keine Warnstufen der Quelle; Lizenz nicht gegengelesen | 15 min |
| BRF Ostbelgien | `rss_brf` | Rubrik Regional, nur mit Ort im Radius (Schlagzeile oder Schlagwort); Titel und Link | 15 min |
| MeteoAlarm | `meteoalarm` | Wetterwarnungen BE, FR, LU als Fläche je NUTS-Gebiet (`app/data/nuts_meteoalarm.json`, gebaut mit `tools/build_nuts.py`); nur Stufe, Art, Gebiet, Zeit, Link; Auflagen der Quelle nicht gelesen | 10 min |

Der Radius von 120 km reicht nach Süden bis Metz und Thionville, nach Westen bis Bastogne, Namur bleibt draußen, nach Norden bis Eupen und Aachen, nach Osten bis Koblenz und Bad Kreuznach. Noch nicht eingebunden: SPW Wallonie Hydrometrie, IRCELINE, ATMO Grand Est, IRSN Téléray, Vigicrues (Endpunkte und Lizenzen nicht geprüft). Tests: `tests/test_quellen_batch3.py`.

## Kultur und Geschichte

Der Landmarken-Collector `osm_natur` (Overpass, wöchentlich) liefert neben der Natur jetzt Burgen und Schlösser (`historic=castle|fort|manor`), Ruinen, archäologische Stätten, Klöster sowie historische Gebäude, Stadttore und Türme. Nur benannte Objekte; Gedenkorte (`memorial`, Stolpersteine) fehlen absichtlich, weil sie oft Personen nennen. Auf der Karte gibt es eine eigene Ebene „Kultur und Geschichte" (Zeichen aus Maki, CC0, geholt mit `tools/fetch_icons.sh`). Nach dem Update einmal `tools/fetch_icons.sh` und `python -m app.collect --once --only osm_natur` ausführen.

## Große Bildschirme

Ab 1800 px Breite skaliert die Oberfläche über die Schriftgröße der Wurzel (`app.css`, Abschnitt „Große Bildschirme“): Inhalt in einem Rahmen (`--frame`), Kartenhöhe aus `--map-h`. Geprüft bei 1440 und 3440 px Breite.

## Karte: Aufbau, Straßen, Radar-Sweep

**Layout.** Ab 1001 px Breite füllt die Karte den ganzen Rahmen. Zeitraum, Darstellung, Ereignisse und Geographie (links, einklappbar) und die Liste (rechts) schweben darüber; darunter stehen die Teile untereinander. Kartensteuerung und Höhenlegende weichen den schwebenden Karten aus (`app.css`, letzter Abschnitt).

**Grenzen.** Alle Verwaltungsgrenzen der Kacheln (Staat, Land, Kreis, Gemeinde; `BOUNDS` in `stil.js`) sehen gleich aus: Punktlinie in einer Farbe je Ansicht, Schalter wie bisher je Ebene. Die Landesgrenze von Rheinland-Pfalz ist die einzige Ausnahme: rote Linie, 2 px, darunter fünf graue Linien (je 1 px, Abstand 1,5 bis 5,5 px nach außen, Deckkraft fallend) als Verlauf. Die Kacheln tragen keine Eigenschaft, die RLP von anderen Ländern trennt; die Linie kommt deshalb aus `web/geo/rlp.geojson` (BKG VG250, `VG250_LAN`, auf 20 m vereinfacht), gebaut mit `python tools/build_landesgrenze.py --zip <vg250…zip>`. Die Datei ist eine eigene Quelle (`rlp-grenze`) und läuft mit dem Schalter „Landesgrenzen". Abweichung zur OSM-Linie der Kacheln: Zehnermeter, bei Zoom 13 und höher sieht man daneben stellenweise einzelne Punkte der Kachellinie. Fehlt die Datei, bleibt die Karte ohne rote Linie, die gepunktete Landesgrenze aus den Kacheln bleibt. Das Vorzeichen des Verlaufs (negativer `line-offset` = außen) ist an der Karte geprüft; wer die Datei anders orientiert, dreht den Verlauf nach innen.

**Vignette.** Die schwarze Vignette der Lagekarte folgt der Landesgrenze von Rheinland-Pfalz, nicht einem Kreis: klar bis 80 km außerhalb der Grenze, danach über 30 km stufenlos (Smoothstep) auf Schwarz. Gebaut wird sie aus `web/geo/rlp.geojson` mit `python tools/build_vignette.py` (Abstand zur Grenze in UTM 32N, ein Graustufen-PNG mit Alpha, `web/geo/vignette.png` plus `vignette.json`, zusammen etwa 16 KB). Die Seite legt das PNG als Bildquelle über die Karte und liest daraus auch die Ausblendung für Wind und Regenwellen (`lage/vignette.js`). Fehlt eine der beiden Dateien, nimmt die Karte den alten Kreis um `meta.radius_km`. Anderes Land oder anderer Abstand: `build_landesgrenze.py --land …`, dann `build_vignette.py --abstand-km … --fade-km …`. Nicht angefasst ist der Radar-Sweep; er zeichnet weiter um den Mittelpunkt.

**LGB Daten (Kartendienste des Landesamts für Geologie und Bergbau).** Eigene Gruppe im Ebenenmenü, 16 ausgewählte Ebenen in den Themen Bergbau, Boden, Erdbeben, Geologie, Geothermie, Hydrogeologie, Ingenieurgeologie, je Dienst die Ebenen als Schalter, dazu Deckkraft und „Alle LGB-Ebenen aus“. Aufbau: `web/geo/lgb.json` (Katalog, 13 Dienste, 16 Ebenen) wird mit `python tools/build_lgb_katalog.py` aus den GetCapabilities unter `mapserver.lgb-rlp.de/cgi-bin/mc_*` gebaut (ein Abruf je Dienst, eine Sekunde Pause; `--from-dir` liest gespeicherte XML, `--save-dir` legt sie ab). Technische Hilfsebenen der Dienste (Kachelquelle, Vektorabfrage, Download-Auswahl) stehen in `AUSGEBLENDET` und fehlen im Katalog. Die Seite fragt nie Capabilities ab, sie holt nur GetMap-Kacheln (EPSG:3857, 256 px) für eingeschaltete Ebenen; Code: `web/js/lage/lgb.js`, reine Funktionen in `web/js/lgb-katalog.js`.

Datenschutz: Das ist (zusammen mit „Landesdaten“, siehe unten) der einzige Fall, in dem der Browser etwas bei einem Dritten holt. Deshalb ist alles aus, bis die Besucherin den Hinweis im Menü bestätigt („Verstanden, Karte laden“); die Bestätigung gilt nur bis zum Neuladen und wird nicht gespeichert. Die Content-Security-Policy erlaubt `https://mapserver.lgb-rlp.de` nur in `web/index.html` und im globalen Header (`web/.htaccess`), die übrigen Seiten bleiben bei `'self'`. Datenschutzerklärung und Quellenregister (`lgb_wms`, `art: client`) nennen das. Quellenvermerk laut LGB („©LGB-RLP <Jahr>, dl-de/by-2-0, www.lgb-rlp.de [Daten bearbeitet]“) steht unter der Karte, solange eine Ebene an ist. Höchstens sechs Ebenen gleichzeitig. Fällt ein Dienst aus, steht „n nicht erreichbar“ im Menü, der Rest der Karte bleibt. Die Ebenen liegen über der Basiskarte und unter Straßen und Beschriftung; nach einem Themenwechsel werden sie wieder dorthin gesetzt (`placeLgb`).

Nicht enthalten: Objektabfrage (GetFeatureInfo), WFS, die Karte „Cross Compliance Erosion“ (sie steht auf der Onlinekarten-Seite, aber nicht in der OGC-Dienste-Liste), Legenden. Der Katalog ist ein Stand vom Tag des Abrufs; ändert das LGB sein Angebot, wird er neu gebaut.

**Landesdaten (offene Kartendienste weiterer Landesstellen).** Zweite Gruppe im Ebenenmenü, gleiche Bedienung wie „LGB Daten“ (ein Code in `lage/lgb.js`, zwei Menüs mit eigenem Hinweis, eigener Deckkraft, eigenem Vermerk und je höchstens sechs Ebenen). Gruppiert nach Landesstelle (Vermessung und Geobasisdaten, Umwelt, Wasserwirtschaft, Straßen, Ländlicher Raum). Die Auswahl (16 Ebenen) steht in `tools/katalog_auswahl.json` und gilt für beide Menüs; `--alle` baut den vollen Katalog. Verworfen wurde, was die App schon hat (Straßen, Gewässer, Grenzen, Gelände, Hochwasser-Pegel, Wetter, Warnungen), Mehrfach-Fassungen derselben Karte, Nischenthemen und Dienste ohne CORS oder mit unvollständiger Zertifikatskette. Die Geoportal-Suche (nur offene Daten) liefert die Kandidaten: `python tools/crawl_geoportal.py --out M.json`, dann `python tools/build_landesdaten_katalog.py --meta M.json` schreibt `web/geo/landesdaten.json`. Lizenz und Vermerk stehen je Dienst im Katalog. Zugelassen sind nur https-Server, die im Katalog unter `hosts` stehen; jeder davon steht auch in der Content-Security-Policy (`web/index.html` und `web/.htaccess`). Neuer Server im Katalog heißt: CSP an beiden Stellen nachziehen (der Test prüft das).

Was fehlt und warum, steht im Katalog unter `ausgelassen`: Kommunen (bewusst nicht), Dienste nur mit WMS 1.1.1 oder ohne EPSG:3857, Server ohne CORS (Umgebungslärm, Naturschutzkarten), und Server, deren Zertifikatskette ich nicht prüfen konnte (Statistisches Landesamt mit 64 Diensten, SGD Nord ROK, LANIS). Letzteres ist kein Urteil über die Server, sondern eine Grenze der Prüfumgebung; Wiederholung von einem Rechner mit normalem Zertifikatsspeicher.

**Straßen.** Autobahnen, Bundes-/Landstraßen und Anschlüsse (auch Brücken, Tunnel) sind gelborange (`#f6a81c`) mit 1 px schwarzer Kontur. Die Umstellung passiert beim Aufbau des Basiskartenstils (`mainRoad` in `web/js/lage/stil.js`); Grenzlinien des Stils (`boundaries*`) werden nicht gezeichnet.

**Radius und Sweep.** Der 120-km-Kreis ist grün (Fläche 1 % Deckkraft, Rand 2 px voll). Ist die Luftverkehr-Ebene an und mindestens ein Flugzeug aktiv, läuft ein Radarstrahl (6 s je Umlauf, Zeichnung auf einer eigenen Canvas, `web/js/sweep.js`); überstreicht er ein Flugzeug, sendet es einen Ping. Ohne aktive Flugzeuge, bei ausgeblendeter Ebene, verstecktem Tab oder „weniger Bewegung“ im System steht alles still.

**Schweife.** Jedes Flugzeug zieht 200 px Schweif entlang der beobachteten Bahn, nach hinten schwächer. Die Bahn besteht nur aus Positionen, die der Browser in dieser Sitzung gesehen hat (Arbeitsspeicher, höchstens 30 Minuten); sie wird nie gespeichert oder hochgeladen. Neu geladene Seite = Schweife beginnen von vorn.

**Flugzeugklassen.** Der Collector speichert `klass`: `civil`, `mil` (Militär-Kennzeichen der adsb.lol-Datenbank, `dbFlags` Bit 0), `heli` (Kategorie A7) oder `milheli`. Kennzeichen, Hex-Code und Typ bleiben draußen, gespeichert wird nur die Klasse. Darstellung: zivil = dunkles Flugzeug, militärisch = violett im Ring, Hubschrauber = eigenes Symbol (uxwing „helicopter“, Seitenansicht, dreht sich nicht). Die Klasse ist so gut wie die Datenbank von adsb.lol: nicht gemeldete oder nicht erfasste Militärflugzeuge erscheinen als zivil.

### Hangneigung aus dem DGM1

`tools/build_hang_rlp.py` rechnet aus dem 1-m-DGM1 drei Neigungsklassen (ab 15, 25 und 35 Grad) als Vektorflächen und schreibt Kacheln Zoom 14 nach `web/tiles/hang/` (Ebenen `ab15`, `ab25`, `ab35`, dazu `meta.json` mit Namensnennung). Die Karte zeigt sie als Ebene „Hangneigung“ (unter Relief, standardmäßig aus), bewusst durchscheinend: die drei Flächen liegen ineinander und addieren sich nach innen auf rund 32 % Deckkraft, die Klippenfläche hat 20 %. Wandstriche und Oberkante der Klippen bleiben deckend, damit Schummerung, Höhenlinien und Neigung zusammen ein genaueres Bild ergeben. Ohne Kacheln gibt es die Ebene nicht.

Der Lauf teilt das Land in Blöcke von 4 km (+ 1 km Rand zum Glätten), rechnet sie parallel und ist wiederaufnehmbar (Marken unter `web/tiles/hang_parts/_done`). Masken reichen 1 m über den Blockrand, die Teilstücke einer Kachel werden vereinigt, deshalb gibt es keine Nähte. Messung RLP (Mac, 6 Arbeiter): 1 391 Blöcke, 33 Minuten, 8 845 Kacheln, 144 MB gzip (188 MB ungepackt), davon `ab15` 78 MB, `ab25` 49 MB, `ab35` 19 MB. Speicherbedarf rund 1 GB je Arbeiter.

    python tools/build_hang_rlp.py --raw ~/Claude/OSINT/dgm1-work/raw --out web/tiles/hang --workers 6
    python tools/build_hang_rlp.py ... --bbox 6.3 49.7 6.6 49.95       # Ausschnitt
    python tools/build_hang_probe.py --raw ... --center 6.45 49.85 --size-km 3 --out /tmp/hang   # nur messen

Parameter und ihre Wirkung: `--sigma` (Glättung des Geländes, Standard 1 m), `--simplify` (Umrisse, 1,5 m), `--min-area` (kleinste Fläche, 40 m²), `--classes` (Schwellen in Grad). Die Deckkraft steht in `web/js/lage/stil.js` (`hangLayers`, `cliffLayers`).

### Relief nachladen (dem-hoch)
Das Relief liegt in zwei Paketen: `dem.pmtiles` (Zoom 6–12) im Installer, `dem-hoch.pmtiles` (Zoom 13/14, rund 4,3 GB) wird beim ersten Start im Hintergrund geholt. Der Server liefert Kacheln aus `dem` und fällt für fehlende (hohe) Zoomstufen auf `dem-hoch` zurück; bis das Nachladepaket da ist, wird Zoom 12 überzoomt.
```
python -m app.pakete --manifest https://…/dem-hoch.pmtiles.manifest.json --dest ~/.local/share/osint/tiles
```
Abbruch ist unkritisch: `dem-hoch.pmtiles.part` wächst Teil für Teil, jeder Lauf prüft die fertigen Teile neu und setzt das angefangene per Range fort. Umbenannt wird erst nach bestandener Gesamtprüfsumme. Bedarf: Paketgröße plus 200 MB frei. Die Adresse steht in `PAKETE_MANIFEST` (`app/desktop.py`), Überschreiben mit `OSINT_PAKETE_MANIFEST`, Abschalten mit `aus`. Fehler: `/api/state` → `nachladen.error`, Log `osint.pakete`. Namensnennung: die Landesdaten (DGM1, © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0) stehen in den Metadaten der Pakete.

### Mitgelieferte Pakete im Installer
`desktop/stage-pakete.sh` kopiert `dem.pmtiles` (Zoom ≤ 12), `klippen`, `hang`, `gebaeude` und `suche_geo.json` nach `desktop/src-tauri/pakete/` (nicht im Git). `tauri.conf.json` nimmt den Ordner als Ressource auf, `main.rs` übergibt ihn dem Dienst als `--pack-dir`. Reihenfolge der Suche für `/tiles/`: Datenordner, Installer-Ressource, `web/tiles`. Erlaubt ist so nur Lesen; `/data/` kommt weiter nur aus dem Datenordner, außer `suche_geo.json`. Gesamtgröße ohne Basiskarte rund 1,1 GB. Ablauf: `desktop/build-sidecar.sh` → `desktop/stage-pakete.sh` → `cd desktop && npx tauri build`. Ungetestet auf Windows (Installer wurde noch nicht gebaut).

### Gebäude, Straßenschilder, Beschriftung, Verkehrsfarben

- **Gebäude** bordeaux (`#800020` hell, `#9c2a4b` dunkel), Deckkraft nach Zoom: 40 % bis Zoom 14, linear bis 75 % bei Zoom 17 (`BUILDING_OPACITY` in `web/js/lage/stil.js`). Standardmäßig an. Die Ebene beginnt bei Zoom 13 (nur große Gebäude, die Kacheln führen darunter nicht mehr). Alle Gebäude gibt es ab Kartenzoom 14: der Kern wird mit `tileSize: 256` eingebunden, dadurch gelten die Zoom-15-Kacheln eine Stufe früher. Weiter vorzuziehen (Zoom 13) würde viermal so viele Kacheln je Bild laden; dafür bräuchte es eigene Gebäudekacheln.
- **Autobahnen** blau mit schwarzer Kontur; auf der Strecke Schilder mit der OSM-Nummer (`ref`): A blau/weiß, B gelb, L und K weiß. Nur Nummern bis 8 Zeichen ohne Semikolon; Anschlussstellen tragen kein Schild.
- **Straßennamen** ab Zoom 14 (aus `core.pmtiles` und `ring.pmtiles`; die Region-Kacheln bis Zoom 13 tragen Namen nur an größeren Straßen), **Hausnummern** ab Zoom 16 (Kacheln bis Zoom 15, darüber wird vergrößert). Es sind Kartenbeschriftungen aus OSM, keine Adresssuche und kein Geocoding; die Daten liegen in den Kacheln, nicht in der Datenbank. Wo OSM keine Namen oder Nummern kennt (kleine Weiler), bleibt die Karte leer.
- **Verkehrsmeldungen** in vier Stufen (`trafficLevel` in `rules.js`): gelb Baustelle, orange Behinderung oder Stau, rot langer Stau (ab 30 Min.) oder eine Richtung gesperrt, schwarz Vollsperrung. Die Stufe folgt aus `type`, `severity` und `attrs.sperr` (`voll`/`richtung`, gesetzt von den Collectoren `lbm_baustellen` und `autobahn`); die Liste rechts zeigt weiter die Stufe der Quelle. Schwarze Linien bekommen einen weißen Saum.
- **Detailfeld** rechts lässt sich mit dem Knopf „Details ausblenden“ einklappen; Ebenen, Höhenlegende und Detailfeld haben dasselbe Material (Deckkraft, Unschärfe, Rand, Schatten).
- **Prüfzugang:** mit `#debug` in der Adresse reagiert die Seite auf das Ereignis `osint-debug` (Auftrag als JSON in `data-debug-in`, Zählwerte in `data-debug-out`). Nur zum Testen, nichts geht nach außen.

## Radius: 120 km, endgültig

Das Lagebild gilt der Region, nicht dem Ort. `RADIUS_KM` in `app/config.py` steht auf 120; die Bounding Box wird daraus berechnet (`config.BBOX`, nach außen auf 0,01° gerundet), es gibt keine zweite Stelle, an der sie stehen müsste. Außerhalb blendet die Karte über die letzten 30 km in 200 Ringen in die Hintergrundfarbe aus (Vignette, `VIG_*` in `web/js/lage/geometrie.js`); das Kartenfenster (`maxBounds`) endet kurz dahinter. Größer wird es nicht.

Nach einer Änderung des Radius neu bauen, in dieser Reihenfolge: `tools/build_tiles.sh`, `tools/build_dem.py`, `tools/build_gazetteer.py` (Ortsverzeichnis für das Geoparsing), `tools/build_nuts.py` (MeteoAlarm-Flächen), danach `tools/check_range.py <URL>` gegen den Server. NINA fragt 21 Kreise ab (RLP, Saarland, Euskirchen, Aachen), Tankerkönig fünf Umkreise zu je 25 km.

## Suche über alle Namen

Suchfeld oben links in der Karte (Taste `/` oder Strg+K). Alles läuft im Browser, keine Anfrage nach außen. Der Index wird erst beim ersten Fokus geladen.

- `web/data/suche_geo.json` (statisch, ca. 6,5 MB, rund 160 000 Einträge): Orte, Straßen, Bäche, Gipfel, Wälder, Schutzgebiete aus unseren Kartenkacheln. Bauen: `python tools/build_search_index.py --rescan` (liest `web/tiles/region.pmtiles` und `core.pmtiles`, Zwischenstand in `data/search_raw.json.gz`; ohne `--rescan` wird der Zwischenstand benutzt). Nach jedem Kachel-Neubau wiederholen.
- `web/data/suche.json` (dynamisch, ca. 1,3 MB): Schulen, Kirchen, Feuerwachen, Brücken, Landmarken, Haltestellen, Routen, Pegel. Entsteht bei `python -m app.export`.
- Format `{"v":1,"t":[Typen],"o":[Orte],"e":[[Name,Typ,Breite*1e4,Länge*1e4,Ort]]}`; `TYPES` in `app/search.py` nur anhängen, nie umsortieren.
- Datenschutz: keine Hausnummern, keine Adressen, keine Personennamen. Reine Zahlennamen werden verworfen. Lizenz: © OpenStreetMap-Mitwirkende (ODbL).
- Test: `python -m pytest tests/test_search.py && node --test tests/js/suche.test.mjs`

Die Karte im Stil des 15. Jahrhunderts hat keine Papiertextur mehr (Foto und Überlagerung entfernt); Farben, Schrift, Windrose und Zeichen bleiben.

## Vegetation und Wasserbewegung

**Vegetation:** `web/js/lage/stil.js` (`LAND`, `LAND_KINDS`) zeichnet 13 Klassen nach Naturfarben (Wald, Wiese, Rasen/Park, Busch, Heide, Acker, Obst, Wein, Kleingarten, Moor, Fels, Sand, Friedhof). Ab Zoom 12 liegen feine Signaturen darüber (`icons.js`, `registerLandPatterns`). Schutzgebiete haben eine gestrichelte grüne Kante. Die Kacheln tragen keinen Blatttyp, Laub-, Nadel- und Mischwald sind daher nicht trennbar (dafür wäre ein OSM-Collector für `leaf_type` nötig).

**Wasserbewegung** (Ebene „Wasserbewegung“, standardmäßig aus, `web/js/fluss.js`): Striche und Pfeile entlang der Gewässerlinien zeigen die Fließrichtung (Digitalisierungsrichtung der OSM-Linien, geprüft an Mosel, Saar, Our, Sûre, Kyll, Prüm, Nims, Alzette, Lieser, Ruwer). Tempo ist eine Klasse (Bach, Fluss, gestaut), kein gemessener Abfluss. `IMPOUNDED` (Mosel, Saar) bewegt sich kaum: staugeregelt. Seen, Teiche und Becken zeigen Wellenzeichen, die mit dem Modellwind (ICON-D2, Kartenmitte) ziehen; bei Flaute oder ohne Windmodell bleibt das Wasser glatt. Flächen ohne Gewässerart gelten als Stillgewässer. Bei `prefers-reduced-motion` stehen die Zeichen still. Tests: `node tests/js/fluss.test.mjs`. Prüfhilfe: `#debug` schreibt Seitenfehler nach `data-debug-err` am `<html>`.

## Licht am Zeiger

Ebene „Licht am Zeiger“ (aus, unter Kartengrundlage; braucht Höhenrelief). `web/js/licht.js` rechnet im Fragment-Shader (WebGL2): Höhenmosaik aus den sichtbaren Terrarium-Kacheln (höchstens 48, Zoom 6 bis 12), Hangneigung per Sobel, Punktlicht über dem Zeiger (Höhe einstellbar), Schatten durch Strahlverfolgung mit weichem Rand (48 Schritte). Ohne Maus gilt die Bildmitte bzw. der letzte Tippunkt. Gilt nur bei Nordausrichtung ohne Neigung. Prüfzugang: `licht:{on,lon,lat,hoehe}` im `#debug`-Auftrag.

## Desktop-App (Tauri, lokal, GPU)

Dieselbe Oberfläche als App für Windows 10+, Linux und macOS. Gezeichnet wird mit dem System-WebView (WebView2, WebKitGTK, WKWebView), WebGL läuft dort auf der GPU. Daten und Karte liegen lokal, es gibt keinen Server und keine US-Cloud.

```
Tauri-Hülle (Rust) ──startet──▶ osint-core (Python, Sidecar) ──▶ 127.0.0.1:<Port>
                                  ├─ liefert web/ (mit Teilabrufen für PMTiles)
                                  ├─ erster Start: Karte für das ganze Gebiet laden (tools/build_region_tiles.py, pmtiles-CLI)
                                  └─ Sammelzyklus alle 5 Min: app.collect → app.export → <Datenordner>/data
```

Es gibt keine Auswahl eines Mittelpunkts: Das Gebiet steht fest in `region.yaml` (Rheinland-Pfalz plus 80 km). Beim ersten Start zeigt `einrichtung.html` nur den Fortschritt, die App lädt die Karte für die ganze Fläche (rund 1,5 GB mit Höhenmodell, einmalig, wiederaufnehmbar: Stücke in `tiles-work/chunks`, jeder Lauf macht dort weiter) und beginnt zu sammeln. Der Sidecar braucht dafür `shapely` und `pmtiles` (Python) sowie die pmtiles-CLI; ob das gebündelte Programm sie enthält, ist nicht geprüft.

Zugangsdaten in der App: Quellen, die einen Schlüssel oder ein Login brauchen, tragen im Register ein Feld `zugang` (Name der Umgebungsvariable, Art: `schluessel`, `benutzername` oder `passwort`, Bezeichnung). Die Seite „Quellen und Lizenzen“ zeigt in der Desktop-App und auf dem lokalen Webserver (`deploy/serve-local.py`, nur auf Loopback) je Quelle Eingabefelder; auf dem statischen Webspace erscheinen sie nicht. Die Werte liegen in `zugang.json` im Datenordner (Rechte 600, Klartext, nicht im Schlüsselbund). Die Desktop-App reicht sie als Umgebungsvariable an die Sammler-Kindprozesse; beim lokalen Webserver liegt die Datei in `data/zugang.json` und `app/config.py` liest sie nach der `.env` (`.env` und Shell gehen vor). Langlaufende Prozesse (Livemodul) lesen sie erst nach einem Neustart. Angenommen werden nur Variablen, die im Register stehen. Die Oberfläche erfährt nie einen Wert, nur „gesetzt“. Neue Quelle mit Schlüssel: `zugang` im Register eintragen, der Collector liest die Variable wie bisher. Gilt ab dem nächsten Abruf der Quelle.

Ablauf in der App: Als Hintergrund der Einrichtungsseite dient die mitgelieferte Weltkarte `web/basis/welt.pmtiles` (Zoom 0 bis 5, rund 15 MB, Herkunft in `web/basis/README.txt`). Der Balken zeigt beim Kartenabruf die fertigen Stücke, beim Sammeln „n von m abgerufen, läuft noch: <Name>" (`.collect-progress.json` im Datenordner, nur Quellennamen). Der erste Lauf überspringt die Quellen mit `erstlauf: spaeter`; sobald der erste Export steht, zeigt die App „Bereit", die langsamen Quellen laufen im Hintergrund (`--due`) und erscheinen mit dem nächsten Export (alle 5 Minuten). Spätere Zyklen holen nur noch fällige Quellen (`--due`), nicht mehr jede Quelle bei jedem Zyklus.

```bash
# Dienst allein ausprobieren (ohne Hülle)
python -m app.desktop --data-dir /tmp/osint-demo --pmtiles tools/bin/pmtiles     # → "OSINT_READY port=N", dann http://127.0.0.1:N/

# App bauen (je Betriebssystem auf diesem System; CI: .github/workflows/desktop.yml)
desktop/build-sidecar.sh && cd desktop && npm install --include=dev && npx tauri build
```

### Windows-Installer

Der Installer (NSIS, eine `Landblick - RLP_<Version>_x64-setup.exe`, rund 50 MB) wird auf einem Windows-Runner gebaut, nicht lokal: GitHub → Actions → **windows-installer** → *Run workflow*; nach rund 8 Minuten steht er im Lauf unter *Artifacts* (`landblick-windows-installer`, Zip mit der Setup.exe). Ein Tag `windows-v*` startet den Lauf ebenfalls. Lokal auf Windows: `powershell -File desktop\build-sidecar.ps1`, danach `cd desktop; npm install --include=dev; npx tauri build --bundles nsis` (Python 3.11+, Node 22, Rust und die Visual-Studio-Build-Tools nötig).

- **Installation:** pro Benutzer (`currentUser`, ohne Administratorrechte), Deutsch, Eintrag im Startmenü und Deinstallation über „Apps“. Der Installer holt bei Bedarf WebView2 nach (Windows 11 hat es, Windows 10 braucht eine Internetverbindung dafür).
- **Erster Start:** Die App öffnet die Einrichtungsseite, lädt die Karte für das ganze Gebiet (rund 1,5 GB, einmalig, wiederaufnehmbar) und beginnt zu sammeln. Daten und Zugangsdaten liegen in `%APPDATA%\de.ctw.osint`; Deinstallieren lässt sie stehen (zum Zurücksetzen den Ordner löschen).
- **Nicht signiert:** Windows SmartScreen meldet „Der Computer wurde durch Windows geschützt“. *Weitere Informationen → Trotzdem ausführen*. Ein Code-Signing-Zertifikat ist offen.
- **Nicht getestet auf echter Hardware:** Der Bau läuft durch, der Rauchtest des Sidecars (`app.region` im gebündelten Programm) ist Teil des Baus; der Lauf der App unter Windows ist beim ersten Test auf dem PC zu prüfen (Windows-Firewall-Abfrage für den lokalen Dienst, Pfade, Antivirus-Fehlalarme bei PyInstaller-Programmen).


Grenzen der ersten Fassung: Suchindex, Gewässernetz, Höhenkacheln und Routen (`web/geo`, `web/tiles/dem`, `tools/build_*.py`) werden über die Werkzeuge in `tools/` für die Landesfläche gebaut, nicht von der App. Quellen für Luxemburg, Rheinland-Pfalz und Ostbelgien liefern nur dort Daten; bundesweite (DWD, NINA, Autobahn, Bright Sky) funktionieren überall in Deutschland. Das Bündeln mit PyInstaller und die Installer sind hier nicht gebaut worden (Sandbox ohne WebKit, nur Linux): erster Build auf Mac, Windows und Linux steht aus.

## Frontend: Zellenbetrieb (ab R5)

Die Seite lädt `data/manifest.json` und `data/start.json` und holt danach nur die Zellen im Bildausschnitt (`data/z/<x>_<y>/<art>.json`, Raster 0,5 Grad). Fehlt das Manifest, läuft sie wie bisher aus den Flachdateien. Code: `web/js/zellen.js` (rein, getestet), `web/js/lage/zellenlauf.js` (Anbindung an Karte und Zustand).

- **Stufen.** Unter Zoom 8 keine Zellen: die Karte zeigt je Rasterzelle eine Zahl (Dichte-Ebene aus `start.json`), das Warnband und die Tabelle stammen aus dem Warnband des Startpakets. Ab Zoom 8 Ereignisse, Pegel und Umweltstationen, ab 9 Kraftstoff, ab 10 Haltestellen, Landmarken und Routen, ab 11 Infrastruktur und Anbau (`KIND_MIN_ZOOM`). Unter Zoom 9 werden nur Meldungen ab Stufe „Hinweis“ gezeichnet, höchstens 1500 (`ebenenBudget`).
- **Rand und Obergrenze.** Ab Zoom 9 wird eine Zelle Rand mitgeladen, höchstens 60 Zellen gleichzeitig, die Bildmitte hat Vorrang. Zellen außerhalb werden verworfen.
- **Änderungen.** Das Manifest trägt je Datei eine Prüfsumme; eine Datei wird nur neu geholt, wenn sie sich geändert hat. Ein Fehler in einer Zelle lässt die übrigen stehen, die Statuszeile neben „Lagekarte“ nennt die Zahl der nicht erreichbaren Dateien (Einzelheiten als Tooltip), nach 30 Sekunden folgt ein neuer Versuch.
- **Alter.** Zellen tragen keine Abrufzeit. `fetched_at`, `source_status` und `age_s` setzt das Frontend beim Zusammenführen aus dem Quellenzustand des Startpakets (`anreichern`).
- **Gebiet.** Land und Landkreis stehen im Ereignisfilter („Filter“). Das Backend schreibt `ars` und `land` an Ereignisse und Messstellen (VG250, `app/export_cells.py`); außerhalb Deutschlands kommt `land` aus dem `region_tag` des Sammlers, ein deutsches Kürzel ohne Kreis bleibt „unbekannt“.
- **Prüfzugang.** `#debug` kennt den Befehl `zellen` (gehaltene Dateien, Fehler, Bytes, Ereignisse) und wartet auf laufende Abrufe.

