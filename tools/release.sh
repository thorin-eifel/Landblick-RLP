#!/usr/bin/env bash
# =============================================================================
# Landblick - RLP — Release bauen und auf GitHub veröffentlichen
#
# Zweck:     Baut aus einem Git-Stand die Release-Dateien (Quelltext-Archive, Installer, Handbuch als PDF/HTML/Markdown,
#            Prüfsummen) nach build/release/ und legt auf Wunsch das GitHub-Release an.
# Aufruf:    tools/release.sh 1.0.0-alpha.1            nur bauen (aus HEAD)
#            tools/release.sh 1.0.0-alpha.1 --github   bauen, Tag v<Version> auf HEAD setzen und Release anlegen
#            REF=main tools/release.sh 1.0.0-alpha.1   anderen Git-Stand nehmen
# Braucht:   git, python3, pandoc, wkhtmltopdf (Handbuch); für --github die GitHub-CLI `gh`, angemeldet.
# Regeln:    Nur versionierte Dateien kommen ins Archiv; die uxwing-Symbole (nicht versioniert) sind damit nie dabei.
#            Notizen aus docs/release-<Version>.md; Versionen mit "-" gelten als Vorabversion.
# Exit:      0 = gut, 1 = Fehler
# =============================================================================
set -euo pipefail

VERSION="${1:?Version angeben, z. B. 1.0.0-alpha.1}"
MODE="${2:-}"
REF="${REF:-HEAD}"
ROOT="$(git rev-parse --show-toplevel)"
OUT="${ROOT}/build/release"
NOTES="${ROOT}/docs/release-${VERSION}.md"

log() { printf '%s\n' "$*" >&2; }
fail() { log "FEHLER: $*"; exit 1; }

[ -f "${NOTES}" ] || fail "Notizen fehlen: ${NOTES}"
grep -q "^## \[${VERSION}\]" "${ROOT}/CHANGELOG.md" || fail "CHANGELOG.md hat keinen Abschnitt für ${VERSION}"
if [ "${MODE}" = "--github" ]; then
  [ -z "$(git status --porcelain)" ] || fail "Arbeitsbaum nicht sauber (git status)"
  command -v gh >/dev/null || fail "gh (GitHub-CLI) fehlt"
fi

rm -rf "${OUT}" && mkdir -p "${OUT}"
cd "${ROOT}"
git archive --format=zip    --prefix="landblick-${VERSION}/" -o "${OUT}/landblick-${VERSION}-quelltext.zip"    "${REF}"
git archive --format=tar.gz --prefix="landblick-${VERSION}/" -o "${OUT}/landblick-${VERSION}-quelltext.tar.gz" "${REF}"
for f in install.ps1 install.sh install.py; do git show "${REF}:${f}" > "${OUT}/${f}"; done

python3 tools/handbuch.py --version "${VERSION}" --out "${OUT}/handbuch"
for ext in pdf html md; do
  [ -f "${OUT}/handbuch/landblick-handbuch.${ext}" ] || fail "Handbuch ${ext} fehlt (pandoc/wkhtmltopdf?)"
  mv "${OUT}/handbuch/landblick-handbuch.${ext}" "${OUT}/landblick-${VERSION}-handbuch.${ext}"
done
rmdir "${OUT}/handbuch"

( cd "${OUT}" && { command -v sha256sum >/dev/null && sha256sum * || shasum -a 256 *; } > SHA256SUMS )
log "Dateien in ${OUT}:"; ls -l "${OUT}" >&2

if [ "${MODE}" = "--github" ]; then
  PRE=()
  case "${VERSION}" in *-*) PRE=(--prerelease);; esac
  git rev-parse -q --verify "refs/tags/v${VERSION}" >/dev/null || git tag -a "v${VERSION}" -m "Landblick - RLP ${VERSION}" "${REF}"
  git push origin "v${VERSION}"
  gh release create "v${VERSION}" "${PRE[@]}" --title "Landblick - RLP ${VERSION}" --notes-file "${NOTES}" "${OUT}"/*
  log "Release v${VERSION} angelegt."
fi
