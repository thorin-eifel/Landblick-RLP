#!/usr/bin/env bash
# Dauerlauf (R6) in einer Cloud-Sitzung ohne systemd.
#
# Zweck:      Startet die Jobs, die install.py --dauerlauf auf einem Dauerläufer anlegt, als Schleifen im Hintergrund:
#             zyklus alle 300 s, spaet alle 1800 s, health und dauerlauf-Probe alle 600 s, backup täglich 03:15 UTC.
#             Jeder Job läuft in einer eigenen Schleife, damit ein langer Sammelzyklus keine Probe verschiebt.
# Parameter:  start | stop | status | sichern
#             LANDBLICK_ROOT   Projektordner (Standard /home/user/landblick-rlp)
# Beispiel:   setsid nohup dauerlauf-cloud/run.sh start >/dev/null 2>&1 &
#             dauerlauf-cloud/run.sh status
#             dauerlauf-cloud/run.sh sichern     # Protokoll in diesen Branch kopieren, committen, pushen
# Seiteneffekte: schreibt data/ und web/data/ im Projektordner, PID-Dateien unter data/run/, Logs unter data/logs/.
#             "sichern" committet und pusht im Branch dieses Skripts (rlp/r6-dauerlauf-cloud).
set -euo pipefail

ROOT="${LANDBLICK_ROOT:-/home/user/landblick-rlp}"
PY="${ROOT}/.venv/bin/python"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="${ROOT}/data/run"
LOGS="${ROOT}/data/logs"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "${LOGS}/steuerung.log"; }

# Ein Job: Befehl im Takt, mit Zeitgrenze, Ausgabe ins eigene Log. Fehler beenden die Schleife nicht.
schleife() {
  local name="$1" takt="$2" grenze="$3"; shift 3
  while true; do
    local t0; t0=$(date +%s)
    ( cd "${ROOT}" && timeout "${grenze}" "${PY}" "$@" ) >> "${LOGS}/${name}.log" 2>&1 || log "${name}: Exit $?"
    local rest=$(( takt - ($(date +%s) - t0) ))
    (( rest > 0 )) && sleep "${rest}"
  done
}

# Sicherung täglich um 03:15 UTC.
taeglich() {
  while true; do
    local jetzt ziel; jetzt=$(date -u +%s); ziel=$(date -u -d "today 03:15" +%s)
    (( ziel <= jetzt )) && ziel=$(date -u -d "tomorrow 03:15" +%s)
    sleep $(( ziel - jetzt ))
    ( cd "${ROOT}" && timeout 3600 "${PY}" tools/backup.py --keep 14 --verify-after ) >> "${LOGS}/backup.log" 2>&1 || log "backup: Exit $?"
  done
}

starte() {
  mkdir -p "${RUN}" "${LOGS}"
  if laeuft; then echo "läuft schon"; return 0; fi
  log "Start"
  ( cd "${ROOT}" && timeout 2700 "${PY}" tools/zyklus.py --erst ) >> "${LOGS}/zyklus.log" 2>&1 || log "Erstlauf: Exit $?"
  schleife dauerlauf 600 300 tools/dauerlauf.py sample & echo $! > "${RUN}/dauerlauf.pid"
  schleife health    600 300 tools/gesundheit.py      & echo $! > "${RUN}/health.pid"
  schleife zyklus    300 2700 tools/zyklus.py         & echo $! > "${RUN}/zyklus.pid"
  schleife spaet    1800 10800 tools/zyklus.py --spaet & echo $! > "${RUN}/spaet.pid"
  taeglich & echo $! > "${RUN}/backup.pid"
  echo $$ > "${RUN}/steuerung.pid"
  wait
}

laeuft() {
  local f; for f in "${RUN}"/*.pid; do [[ -e "${f}" ]] && kill -0 "$(cat "${f}")" 2>/dev/null && return 0; done; return 1
}

stoppe() {
  local f; for f in "${RUN}"/*.pid; do [[ -e "${f}" ]] || continue; pkill -P "$(cat "${f}")" 2>/dev/null || true; kill "$(cat "${f}")" 2>/dev/null || true; rm -f "${f}"; done
  log "Stopp"
}

status() {
  local f; for f in "${RUN}"/*.pid; do [[ -e "${f}" ]] || continue
    if kill -0 "$(cat "${f}")" 2>/dev/null; then echo "$(basename "${f}" .pid): läuft"; else echo "$(basename "${f}" .pid): tot"; fi
  done
  [[ -s "${ROOT}/data/dauerlauf.jsonl" ]] && echo "Proben: $(wc -l < "${ROOT}/data/dauerlauf.jsonl"), letzte: $(tail -1 "${ROOT}/data/dauerlauf.jsonl" | cut -c1-60)"
}

# Protokoll in den Log-Branch übernehmen. Das jsonl wird angehängt, nicht ersetzt: nach einem Containerwechsel
# beginnt data/dauerlauf.jsonl leer, die Proben davor liegen nur noch hier.
sichern() {
  local ziel="${HERE}/dauerlauf.jsonl" quelle="${ROOT}/data/dauerlauf.jsonl"
  [[ -s "${quelle}" ]] || { echo "noch keine Proben"; return 0; }
  touch "${ziel}"
  sort -u "${ziel}" "${quelle}" > "${ziel}.neu" && mv "${ziel}.neu" "${ziel}"
  ( cd "${ROOT}" && "${PY}" tools/dauerlauf.py report --file "${ziel}" --out "${HERE}/bericht.md" ) >/dev/null
  cd "${HERE}"
  git add dauerlauf.jsonl bericht.md run.sh
  git diff --cached --quiet && { echo "nichts Neues"; return 0; }
  git commit -q -m "dauerlauf: $(wc -l < dauerlauf.jsonl) Proben, Stand $(date -u +%Y-%m-%dT%H:%MZ)"
  git push -q -u origin rlp/r6-dauerlauf-cloud
}

case "${1:-}" in
  start) starte ;;
  stop) stoppe ;;
  status) status ;;
  sichern) sichern ;;
  *) echo "Aufruf: $0 start|stop|status|sichern" >&2; exit 2 ;;
esac
