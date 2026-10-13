#!/usr/bin/env bash
# =============================================================================
# Landblick - RLP — Installer für Linux und macOS (Start von install.py mit passendem Python)
#
# Zweck:     Sucht ein Python ab 3.11 und ruft install.py auf. Alle Parameter gehen unverändert durch.
# Aufruf:    ./install.sh --kontakt name@example.org [--karte voll] [--dauerlauf] [--system] [--status] [--deinstall]
# Hinweis:   Der Installer lädt nichts ohne Rückfrage nach (Karte: --karte voll, mit Bestätigung oder --ja).
# Exit:      wie install.py
# =============================================================================
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
for c in python3.13 python3.12 python3.11 python3 python; do
  if command -v "${c}" >/dev/null 2>&1 && "${c}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    exec "${c}" install.py "$@"
  fi
done
echo "FEHLER: Python 3.11 oder neuer nicht gefunden (Debian/Ubuntu: sudo apt install python3 python3-venv; macOS: brew install python@3.12)" >&2
exit 1
