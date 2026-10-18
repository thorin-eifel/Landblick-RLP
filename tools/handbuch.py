#!/usr/bin/env python3
"""Baut das Handbuch aus docs/handbuch/*.md.

Zweck:      Setzt die Kapitel zu einer Datei zusammen und erzeugt HTML und PDF. Die Quellentabelle in Kapitel 4 wird aus
            sources.yaml geschrieben (zwischen den Marken quellen:start / quellen:ende), damit sie nicht vom Register abweicht.
Parameter:  --out DIR     Ausgabeordner (Standard build/handbuch)
            --version V   Versionsangabe auf dem Deckblatt (Standard: aus pyproject.toml / CHANGELOG-frei: 1.0.0-alpha.2)
            --update      Quellentabelle in docs/handbuch/04-datenquellen.md neu schreiben
            --check       nur prüfen, ob die Tabelle zum Register passt (Exit 1 bei Abweichung)
            --nur-md      nur die zusammengesetzte Markdown-Datei, ohne pandoc
Beispiel:   python tools/handbuch.py --update && python tools/handbuch.py
Benötigt:   pandoc; für PDF zusätzlich wkhtmltopdf oder Chrome/Chromium/Edge (Ersatz). Fehlt beides, wird das PDF übersprungen und das gesagt.
Exit:       0 = gut, 1 = Tabelle weicht ab (--check) oder Bau fehlgeschlagen
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "docs" / "handbuch"
QUELLE = DIR / "04-datenquellen.md"
START, ENDE = "<!-- quellen:start -->", "<!-- quellen:ende -->"
log = logging.getLogger("handbuch")


def _zelle(text: object) -> str:
    return str(text).replace("|", "/").replace("\n", " ").strip()


def _intervall(s: int | None) -> str:
    if not s:
        return "—"
    return f"{s // 3600} h" if s % 3600 == 0 else f"{s // 60} min" if s % 60 == 0 else f"{s} s"


def quellen_tabelle(register: Path | None = None) -> str:
    """Markdown-Tabelle aller Quellen aus sources.yaml."""
    daten = yaml.safe_load((register or ROOT / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    kopf = ["| Kennung | Quelle | Betreiber | Lizenz | Intervall | Risiko | geprüft | aktiv |", "|---|---|---|---|---|---|---|---|"]
    zeilen = []
    for s in daten:
        art = " (Browser)" if s.get("art") == "client" else ""
        zeilen.append("| " + " | ".join([
            f"`{s['id']}`", _zelle(s.get("kurzname") or s["name"]) + art, _zelle(s.get("betreiber", "")), _zelle(s.get("lizenz", "")),
            "—" if s.get("art") == "client" else _intervall(s.get("intervall")), _zelle(s.get("datenschutz_risiko", "")),
            "ja" if s.get("lizenz_geprueft") else "nein", "ja" if s.get("aktiv", True) else "nein"]) + " |")
    return "\n".join(kopf + zeilen) + f"\n\n{len(daten)} Quellen im Register, davon {sum(1 for s in daten if s.get('aktiv', True))} aktiv ({sum(1 for s in daten if s.get('aktiv', True) and s.get('art') != 'client')} mit Sammler, {sum(1 for s in daten if s.get('aktiv', True) and s.get('art') == 'client')} nur im Browser).\n"


def ersetze(text: str, tabelle: str) -> str:
    if START not in text or ENDE not in text:
        raise SystemExit(f"Marken {START} / {ENDE} fehlen in {QUELLE}")
    vor, rest = text.split(START, 1)
    _, nach = rest.split(ENDE, 1)
    return f"{vor}{START}\n\n{tabelle}\n{ENDE}{nach}"


def kapitel() -> list[Path]:
    return sorted(p for p in DIR.glob("[0-9][0-9]-*.md"))


def zusammensetzen(version: str, tabelle: str) -> str:
    teile = [f"---\ntitle: Landblick - RLP, Handbuch\nsubtitle: Version {version}\nauthor: Thorsten Schleicher\nlang: de\n---\n"]
    for p in kapitel():
        inhalt = p.read_text(encoding="utf-8")
        teile.append((ersetze(inhalt, tabelle) if p == QUELLE else inhalt).strip() + "\n")
    return "\n\n".join(teile)


def pandoc(quelle: Path, ziel: Path, extra: list[str]) -> bool:
    cmd = ["pandoc", str(quelle), "-o", str(ziel), "--from", "markdown+pipe_tables-smart", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        log.error("pandoc: %s", r.stderr.strip())
    return r.returncode == 0


def chrome() -> str | None:
    """Chrome oder Chromium für den PDF-Druck (Pfad oder Befehl), sonst None."""
    kandidaten = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for k in kandidaten:
        if Path(k).exists():
            return k
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "chrome"):
        if (w := shutil.which(n)):
            return w
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "build" / "handbuch"))
    ap.add_argument("--version", default="1.0.0-alpha.2")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--nur-md", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level="INFO", format="%(message)s")

    tabelle = quellen_tabelle()
    aktuell = QUELLE.read_text(encoding="utf-8")
    neu = ersetze(aktuell, tabelle)
    if a.check:
        if neu != aktuell:
            log.error("Quellentabelle in %s weicht von sources.yaml ab: python tools/handbuch.py --update", QUELLE.name)
            return 1
        log.info("Quellentabelle stimmt.")
        return 0
    if a.update:
        QUELLE.write_text(neu, encoding="utf-8")
        log.info("Quellentabelle geschrieben (%d Zeichen).", len(tabelle))
        return 0

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    md = out / "landblick-handbuch.md"
    md.write_text(zusammensetzen(a.version, tabelle), encoding="utf-8")
    log.info("Markdown: %s", md)
    if a.nur_md:
        return 0
    if not shutil.which("pandoc"):
        log.warning("pandoc fehlt: HTML und PDF übersprungen.")
        return 0
    css = DIR / "handbuch.css"
    html = out / "landblick-handbuch.html"
    ok = pandoc(md, html, ["--standalone", "--toc", "--toc-depth=2", "--embed-resources", f"--css={css}", "--metadata", "pagetitle=Landblick - RLP, Handbuch"])
    log.info("HTML: %s", html) if ok else log.error("HTML fehlgeschlagen")
    pdf = out / "landblick-handbuch.pdf"
    if shutil.which("wkhtmltopdf"):
        ok2 = pandoc(md, pdf, ["--standalone", "--toc", "--toc-depth=2", "--pdf-engine=wkhtmltopdf", f"--css={css}",
                               "--pdf-engine-opt=--enable-local-file-access", "--pdf-engine-opt=--page-size", "--pdf-engine-opt=A4",
                               "--pdf-engine-opt=--zoom", "--pdf-engine-opt=1.3",
                               "-V", "margin-left=20mm", "-V", "margin-right=20mm", "-V", "margin-top=20mm", "-V", "margin-bottom=20mm",
                               "--metadata", "pagetitle=Landblick - RLP, Handbuch"])
    elif (browser := chrome()) and ok:
        # Ersatz, wenn wkhtmltopdf fehlt (Homebrew führt es nicht mehr): Chrome/Chromium druckt das fertige HTML.
        root = ["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []   # nur in Containern als root
        r = subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", *root, f"--print-to-pdf={pdf}", html.as_uri()],
                           capture_output=True, text=True, timeout=180)
        ok2 = r.returncode == 0 and pdf.exists()
        if not ok2:
            log.error("Chrome: %s", r.stderr.strip()[-300:])
    else:
        log.warning("Weder wkhtmltopdf noch Chrome/Chromium gefunden: PDF übersprungen.")
        ok2 = None
    if ok2 is not None:
        log.info("PDF: %s", pdf) if ok2 else log.error("PDF fehlgeschlagen")
        ok = ok and ok2
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
