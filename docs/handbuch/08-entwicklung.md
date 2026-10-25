# 8 Entwicklung

## 8.1 Aufbau des Repositorys

```
app/            Python-Kern: Sammler, Region, Speicher, Export, Live
app/collectors/ ein Modul je Quelle
web/            statisches Frontend (index.html, js/, css/, geo/, data/, tiles/)
tools/          Werkzeuge: Karten bauen, Gesundheit, Backup, Dauerlauf, Zyklus, lokaler Webserver
desktop/        Tauri-Hülle
docs/           Betrieb, Pläne, Entscheidungen (adr/), dieses Handbuch
tests/          pytest und tests/js (node --test)
sources.yaml    Quellenregister
region.yaml     Gebiet
install.*       Installer
```

## 8.2 Entwicklungsumgebung

```bash
python3 -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/js/*.test.mjs
```

Der Stand der Tests steht in der `README.md`: 553 Python-Tests und 110 JavaScript-Tests. Ein paar Tests (Felswände) brauchen `scikit-image` und werden in der CI übersprungen, weil `requirements-dev.txt` es nicht enthält. Deshalb stimmt die Zahl in der README nur, wenn sie in einer vollständigen Umgebung erzeugt wurde; `tools/update_readme.py --check` bringt es auf den Punkt.

## 8.3 Eine Quelle hinzufügen

1. Nutzungsbedingungen, Lizenz und Ratenlimit klären und aufschreiben. Im Zweifel bleibt die Quelle aus.
2. Eintrag in `sources.yaml` mit allen Pflichtfeldern, zunächst `aktiv: false`, `lizenz_geprueft: false`.
3. Modul in `app/collectors/<id>.py` nach dem Muster eines vorhandenen Sammlers, mit Kopfkommentar (Zweck, Quelle, Lizenz, Intervall, Beispielaufruf).
4. Echte Beispielantwort als Fixture unter `tests/fixtures/` ablegen; Test für den Normalisierer, für den Geofilter (Punkte knapp innerhalb und außerhalb) und für den Fehlerfall.
5. Live abrufen: `python -m app.collect --only <id> --log-level DEBUG`.
6. Erst wenn Antwort und Lizenz stimmen: `aktiv: true`.
7. `python tools/update_readme.py` und Handbuch neu bauen.

## 8.4 Regeln für Sammler

Kopfkommentar, ehrlicher User-Agent mit Kontakt, Zeitlimit und Wiederholung mit Wartezeit, Schutzschalter, Idempotenz, Protokoll von Erfolg, Fehler, neuen Datensätzen und Dauer, Filter am Rand, keine Zugangsdaten im Code. Ein Sammler, der abstürzt, darf die anderen nicht mitreißen; dafür gibt es die Chaos-Tests.

## 8.5 Qualitätssicherung

- Tests für Normalisierer und Geofilter, Fixtures mit echten Antworten, damit eine Schemaänderung beim Anbieter auffällt.
- Chaos-Tests: Quelle abschalten, Datenträger voll, Datenbank gesperrt, Umstellung auf Sommer- und Winterzeit (Python und JavaScript prüfen dieselben Fälle).
- Continuous Integration (`.github/workflows/ci.yml`): Tests, README-Prüfung, `pip-audit`, `npm audit`. Der Windows-Installer der Desktop-App wird in einem eigenen Workflow gebaut.
- Gemessen wird, bevor optimiert wird (`docs/perf.md`).
- Zeiten sind intern UTC und werden erst bei der Anzeige in Ortszeit gewandelt.

## 8.6 Phasen

| Phase | Inhalt | Stand |
|---|---|---|
| R0 | Repository und Baseline | fertig |
| R1 | Raumabstraktion (Region als Datei statt Kreis im Code) | fertig |
| R2 | Kartenbasis | fertig |
| R3 | Datenpipeline | fertig |
| R4 | Export und Auslieferung | fertig |
| R5 | Frontend | fertig |
| R6 | Betrieb und Härtung | Dauerlauf offen |
| R7 | Abnahme | offen |

Jede Phase endet mit einer Vorführung und einer Liste dessen, was nicht funktioniert hat (`docs/rlp/offen.md`). Plan: `docs/rlp/plan.md`. Entscheidungen: `docs/adr/`.

## 8.7 Mitarbeit

Fehler, Fragen und Rückmeldungen als Issue im Repository. Vorschläge als Pull Request gegen `main`, klein und mit Test. Fragen zu Datenschutz und Lizenz haben Vorrang vor Funktion: Wer unsicher ist, ob eine Quelle erlaubt ist, schreibt das hin, statt zu bauen. Kontakt: thorin.eifel@icloud.com.
