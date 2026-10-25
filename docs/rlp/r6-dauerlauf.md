# R6: 7-Tage-Dauerlauf, Ablauf und Protokoll

Stand: **offen**. Das Werkzeug ist gebaut und getestet, der Lauf selbst braucht sieben Tage Betrieb ohne Handeingriff und hat noch nicht stattgefunden.

## Vorbereitung (einmal)

1. Sammelstelle läuft stabil im Fünf-Minuten-Zyklus (launchd `de.thorin.landblick-cycle` oder systemd `landblick-cycle.timer`).
2. Ruhezustand des Rechners aus, Netzteil dran.
3. Probe-Job einrichten (mit dem Installer: `-Dauerlauf` bzw. `--dauerlauf`, siehe `docs/betrieb.md`, Abschnitt Installation auf einem Dauerläufer), von Hand: `*/10 * * * * cd <Projekt> && .venv/bin/python tools/dauerlauf.py sample`.
4. Backup-Job und Gesundheitsjob laufen (`de.thorin.landblick-backup`, `de.thorin.landblick-health` bzw. die systemd-Timer).
5. Start und Version hier eintragen (kein `note`, denn jeder Vermerk gilt im Bericht als Handeingriff):

| Start (UTC) | Version | Rechner | Zyklus |
|---|---|---|---|
| | | | |

## Während des Laufs

Nichts anfassen. Wer doch eingreift (Neustart, Schlüssel erneuert, Quelle abgeschaltet), vermerkt es sofort mit `tools/dauerlauf.py note "…"`. Ein Eingriff beendet den Lauf nicht, er wird im Bericht aufgeführt und der Mensch entscheidet, ob neu gestartet wird.

## Auswertung

`python tools/dauerlauf.py report --out docs/rlp/r6-bericht.md`

| Kriterium | Ergebnis |
|---|---|
| Mindestens 7 Tage Laufzeit | |
| Keine Pause über 30 Minuten zwischen Proben | |
| Keine Handeingriffe | |
| Backup täglich gelaufen, Rückspielprobe grün (`tools/backup.py --verify`) | |
| Stichprobe: kein personenbezogenes Datum in Datenbank und Logs | |

Was nicht funktioniert hat (Quellen mit langen Störungen, Pausen und ihre Ursache):

-
