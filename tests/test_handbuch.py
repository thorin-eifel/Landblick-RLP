"""Handbuch: Quellentabelle aktuell, Kapitel vollständig, Bau ohne pandoc möglich."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import handbuch  # noqa: E402


def test_quellentabelle_aktuell():
    assert handbuch.main(["--check"]) == 0


def test_tabelle_hat_zeile_je_quelle():
    import yaml
    n = len(yaml.safe_load((handbuch.ROOT / "sources.yaml").read_text(encoding="utf-8"))["sources"])
    zeilen = [z for z in handbuch.quellen_tabelle().splitlines() if z.startswith("| `")]
    assert len(zeilen) == n


def test_kapitel_lueckenlos():
    nummern = [p.name[:2] for p in handbuch.kapitel()]
    assert nummern == [f"{i:02d}" for i in range(1, len(nummern) + 1)]
    assert len(nummern) >= 10


def test_zusammenbau(tmp_path):
    assert handbuch.main(["--out", str(tmp_path), "--nur-md"]) == 0
    text = (tmp_path / "landblick-handbuch.md").read_text(encoding="utf-8")
    assert "Version 1.0.0-alpha.1" in text and "`nina`" in text
