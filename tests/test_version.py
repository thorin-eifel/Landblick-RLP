"""Eine Versionsnummer für alles: Python-Paket, Desktop-App (npm, Cargo, Tauri) müssen übereinstimmen."""
from __future__ import annotations

import json
import re
from pathlib import Path

import app

ROOT = Path(__file__).resolve().parent.parent


def test_versionen_stimmen_ueberein():
    v = app.__version__
    assert re.fullmatch(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?", v)
    assert json.loads((ROOT / "desktop/package.json").read_text())["version"] == v
    assert json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text())["version"] == v
    cargo = (ROOT / "desktop/src-tauri/Cargo.toml").read_text()
    assert re.search(r'^version = "%s"$' % re.escape(v), cargo, re.M)


def test_changelog_nennt_die_version():
    assert f"## [{app.__version__}]" in (ROOT / "CHANGELOG.md").read_text()
