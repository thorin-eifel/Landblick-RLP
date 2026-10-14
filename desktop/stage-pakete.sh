#!/usr/bin/env bash
# Zweck:    Legt die mitgelieferten Kachelpakete als Tauri-Ressource ab (desktop/src-tauri/pakete), bevor `npx tauri build` läuft.
# Aufruf:   desktop/stage-pakete.sh [--pakete DIR] [--dem DIR]     z. B. --pakete dist/pakete --dem dist/pakete2
# Inhalt:   tiles/{dem,klippen,hang,gebaeude}.pmtiles + data/suche_geo.json. NICHT dabei: dem-hoch (Zoom 13/14, wird nachgeladen).
# Option:   --mit-karte  nimmt auch region/core/ring.pmtiles aus web/tiles mit (nur sinnvoll für Formate ohne 2-GB-Grenze).
# Grenze:   NSIS-Installer höchstens 2 GB; das Skript bricht ab, wenn die Summe darüber liegt.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/desktop/src-tauri/pakete"
PAK="${ROOT}/dist/pakete"; DEM="${ROOT}/dist/pakete2"
KARTE=0
while [[ $# -gt 0 ]]; do case "$1" in --mit-karte) KARTE=1; shift ;; --pakete) PAK="$2"; shift 2 ;; --dem) DEM="$2"; shift 2 ;; *) echo "unbekannt: $1" >&2; exit 2 ;; esac; done
die() { echo "FEHLER: $*" >&2; exit 1; }
rm -rf "${OUT}"; mkdir -p "${OUT}/tiles" "${OUT}/data"
need() { [[ -f "$1" ]] || die "fehlt: $1"; }
need "${DEM}/dem.pmtiles";           cp "${DEM}/dem.pmtiles" "${OUT}/tiles/"
need "${PAK}/klippen.pmtiles";       cp "${PAK}/klippen.pmtiles" "${OUT}/tiles/"
need "${PAK}/hang.pmtiles";          cp "${PAK}/hang.pmtiles" "${OUT}/tiles/"
need "${ROOT}/web/tiles/gebaeude.pmtiles"; cp "${ROOT}/web/tiles/gebaeude.pmtiles" "${OUT}/tiles/"
need "${ROOT}/web/data/suche_geo.json";    cp "${ROOT}/web/data/suche_geo.json" "${OUT}/data/"
# Basiskarte (region/core/ring, rund 1,5 GB) sprengt zusammen mit dem Rest die 2 GB: Standard ist Download beim ersten Start
(( KARTE )) && for n in region core ring; do [[ -f "${ROOT}/web/tiles/${n}.pmtiles" ]] && cp "${ROOT}/web/tiles/${n}.pmtiles" "${OUT}/tiles/" || true; done
BYTES="$(du -sk "${OUT}" | cut -f1)"; BYTES=$((BYTES * 1024))
echo "Ressourcen: $((BYTES / 1000000)) MB in ${OUT}"
(( BYTES < 1900000000 )) || die "über 1,9 GB: der NSIS-Installer verträgt höchstens 2 GB (Region/Kern/Ring weglassen oder auslagern)"
