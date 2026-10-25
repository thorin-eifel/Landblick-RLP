#!/usr/bin/env bash
# =============================================================================
# Landblick - RLP — Release bauen und auf GitHub veröffentlichen
#
# Zweck:     Baut aus einem Git-Stand die Release-Dateien (Quelltext-Archive, Installer, Handbuch als PDF/HTML/Markdown,
#            Prüfsummen) nach build/release/ und legt auf Wunsch das GitHub-Release an.
# Aufruf:    tools/release.sh 1.0.0-alpha.2            nur bauen (aus HEAD)
#            tools/release.sh 1.0.0-alpha.2 --github   bauen, Tag v<Version> auf HEAD setzen und Release anlegen
#            REF=main tools/release.sh 1.0.0-alpha.2   anderen Git-Stand nehmen
# Braucht:   git, python3 mit PyYAML, pandoc, wkhtmltopdf oder Chrome/Chromium/Edge (Handbuch-PDF); für --github die GitHub-CLI `gh`, angemeldet.
# Regeln:    Nur versionierte Dateien kommen ins Archiv; die uxwing-Symbole (nicht versioniert) sind damit nie dabei.
#            Notizen aus docs/release-<Version>.md; Versionen mit "-" gelten als Vorabversion.
# Exit:      0 = gut, 1 = Fehler
# =============================================================================
set -euo pipefail

VERSION="${1:?Version angeben, z. B. 1.0.0-alpha.2}"
MODE="${2:-}"
REF="${REF:-HEAD}"
ROOT="$(git rev-parse --show-toplevel)"
OUT="${ROOT}/build/release"
NOTES="${ROOT}/docs/release-${VERSION}.md"
# Python mit PyYAML: $PYTHON, sonst die Umgebung des Installers (.venv), sonst python3.
if [ -n "${PYTHON:-}" ]; then PY="${PYTHON}"
elif [ -x "${ROOT}/.venv/bin/python" ]; then PY="${ROOT}/.venv/bin/python"
else PY="python3"; fi

log() { printf '%s\n' "$*" >&2; }
fail() { log "FEHLER: $*"; exit 1; }

[ -f "${NOTES}" ] || fail "Notizen fehlen: ${NOTES}"
grep -q "^## \[${VERSION}\]" "${ROOT}/CHANGELOG.md" || fail "CHANGELOG.md hat keinen Abschnitt für ${VERSION}"
if [ "${MODE}" = "--github" ]; then
  # Unversionierte Dateien (data/, build/, Symbole) stören nicht: ins Archiv kommt nur, was in ${REF} versioniert ist.
  [ -z "$(git status --porcelain --untracked-files=no)" ] || { git status --short --untracked-files=no >&2; fail "versionierte Dateien geändert (git status); erst committen oder git stash"; }
  [ "$(git rev-parse "${REF}")" = "$(git rev-parse origin/main)" ] || log "Hinweis: ${REF} ist nicht origin/main"
  command -v gh >/dev/null || fail "gh (GitHub-CLI) fehlt"
fi

"${PY}" -c "import yaml" 2>/dev/null || fail "PyYAML fehlt für ${PY}: ${PY} -m pip install pyyaml, oder PYTHON=<Interpreter mit PyYAML> setzen"
command -v pandoc >/dev/null || fail "pandoc fehlt (brew install pandoc)"
if ! command -v wkhtmltopdf >/dev/null && ! "${PY}" -c "import sys; sys.path.insert(0,'tools'); import handbuch; sys.exit(0 if handbuch.chrome() else 1)"; then
  fail "kein PDF-Weg: wkhtmltopdf oder Chrome/Chromium/Edge installieren"
fi

rm -rf "${OUT}" && mkdir -p "${OUT}"
cd "${ROOT}"
git archive --format=zip    --prefix="landblick-${VERSION}/" -o "${OUT}/landblick-${VERSION}-quelltext.zip"    "${REF}"
git archive --format=tar.gz --prefix="landblick-${VERSION}/" -o "${OUT}/landblick-${VERSION}-quelltext.tar.gz" "${REF}"
for f in install.ps1 install.sh install.py; do git show "${REF}:${f}" > "${OUT}/${f}"; done

"${PY}" tools/handbuch.py --version "${VERSION}" --out "${OUT}/handbuch"
for ext in pdf html md; do
  [ -f "${OUT}/handbuch/landblick-handbuch.${ext}" ] || fail "Handbuch ${ext} fehlt (pandoc/wkhtmltopdf?)"
  mv "${OUT}/handbuch/landblick-handbuch.${ext}" "${OUT}/landblick-${VERSION}-handbuch.${ext}"
done
rmdir "${OUT}/handbuch"

# Erst neben den Ordner schreiben, dann hinein: sonst zählt sha256sum die halb geschriebene Datei mit (Prüfsumme einer leeren Datei).
( cd "${OUT}" && rm -f SHA256SUMS && { command -v sha256sum >/dev/null && sha256sum * || shasum -a 256 *; } > ../SHA256SUMS.neu && mv ../SHA256SUMS.neu SHA256SUMS )
log "Dateien in ${OUT}:"; ls -l "${OUT}" >&2

if [ "${MODE}" = "--github" ]; then
  PRE=()
  case "${VERSION}" in *-*) PRE=(--prerelease);; esac
  git rev-parse -q --verify "refs/tags/v${VERSION}" >/dev/null || git tag -a "v${VERSION}" -m "Landblick - RLP ${VERSION}" "${REF}"
  git push origin "v${VERSION}"
  gh release create "v${VERSION}" "${PRE[@]}" --title "Landblick - RLP ${VERSION}" --notes-file "${NOTES}" "${OUT}"/*
  log "Release v${VERSION} angelegt."
fi
