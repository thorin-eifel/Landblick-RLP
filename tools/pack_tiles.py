#!/usr/bin/env python3
"""Kachelordner (z/x/y.png oder z/x/y.pbf) zu einer PMTiles-Datei packen, auf Wunsch in Teile unter 2 GB zerlegen.

Zweck:      Relief (web/tiles/dem, Terrarium-PNG) und Felswände (web/tiles/klippen, Vektorkacheln) liegen nach dem Bau als
            zehntausende Einzeldateien. Für die Auslieferung mit der Desktop-App braucht es je Ebene eine Datei: sie lässt
            sich prüfen (SHA-256), in Teilen laden und von der Karte per Bereichsabruf lesen (Protokoll pmtiles://).
Aufruf:     python tools/pack_tiles.py --src web/tiles/dem --out dist/pakete/dem.pmtiles --split-mb 1500
            python tools/pack_tiles.py --src web/tiles/klippen --out dist/pakete/klippen.pmtiles
            python tools/pack_tiles.py --src web/tiles/dem --out dist/pakete/dem.pmtiles --max-zoom 12          Basis (Installer)
            python tools/pack_tiles.py --src web/tiles/dem --out dist/pakete/dem-hoch.pmtiles --min-zoom 13 --split-mb 1500   Nachladepaket
Parameter:  --src DIR         Kachelordner mit <z>/<x>/<y>.png oder .pbf (Endung bestimmt den Kacheltyp)
            --out FILE        Zieldatei (.pmtiles); Eltern­ordner wird angelegt
            --meta FILE       JSON (z. B. meta.json des Ordners), wandert in die Metadaten der Datei (Namensnennung!)
            --split-mb N      zusätzlich in Teile von höchstens N MB zerlegen (<out>.part01 …) und <out>.manifest.json schreiben
            --keep-whole      bei --split-mb die ganze Datei behalten (sonst wird sie nach dem Zerlegen entfernt)
            --min-zoom N, --max-zoom N   nur diese Zoomstufen packen (Standard alle); so entstehen Basis- und Nachlade-Paket
            --verify N        nach dem Packen N zufällige Kacheln zurücklesen und Byte für Byte vergleichen (Standard 200)
Ergebnis:   <out>; mit --split-mb: <out>.partNN und <out>.manifest.json {name, bytes, sha256, parts:[{file, bytes, sha256}]}
Nebenwirkung: schreibt nur nach --out; --src wird nur gelesen. Läuft in einem Durchgang, Speicher: eine Liste der Kachelpfade.
Exit:       0 fertig, 1 Fehler (Ordner leer, Verifikation fehlgeschlagen, unbekannte Endung)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import math
import random
import sys
from pathlib import Path

from pmtiles.reader import MmapSource, Reader, all_tiles  # noqa: F401  (all_tiles nur für Tests über Reader)
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

log = logging.getLogger("osint.pack_tiles")
CHUNK = 8 * 1024 * 1024
TYPES = {".png": TileType.PNG, ".pbf": TileType.MVT, ".mvt": TileType.MVT}


def tile_to_lonlat(z: int, x: int, y: int) -> tuple[float, float]:
    """Nordwestliche Ecke der Kachel (x, y) bei Zoom z in Grad (lon, lat), Web-Mercator."""
    n = 2.0 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def scan(src: Path, min_zoom: int = 0, max_zoom: int = 26) -> tuple[list[tuple[int, Path, tuple[int, int, int]]], str]:
    """Alle Kacheln unter src: Liste (Kachelnummer, Pfad, (z, x, y)) sortiert nach Kachelnummer, dazu die Endung.

    Dateien, deren Pfad nicht <z>/<x>/<y>.<ext> entspricht (README.txt, meta.json), werden übersprungen.
    Gemischte Endungen sind ein Fehler. Nur Zoomstufen min_zoom bis max_zoom (einschließlich) werden aufgenommen.
    """
    found: list[tuple[int, Path, tuple[int, int, int]]] = []
    exts: set[str] = set()
    for p in src.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in TYPES:
            continue
        try:
            z, x, y = int(p.parent.parent.name), int(p.parent.name), int(p.stem)
        except ValueError:
            continue
        if z < max(0, min_zoom) or z > min(26, max_zoom) or not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
            continue
        exts.add(p.suffix.lower())
        found.append((zxy_to_tileid(z, x, y), p, (z, x, y)))
    if not found:
        raise SystemExit(f"Keine Kacheln unter {src} im Zoombereich {min_zoom}–{max_zoom} (erwartet <z>/<x>/<y>.png oder .pbf)")
    if len(exts) > 1:
        raise SystemExit(f"Gemischte Kachelendungen unter {src}: {sorted(exts)}")
    found.sort(key=lambda t: t[0])
    return found, exts.pop()


def pack(src: Path, out: Path, meta: dict | None = None, min_zoom: int = 0, max_zoom: int = 26) -> dict:
    """Packt src nach out (PMTiles v3). Gibt Kennzahlen zurück: tiles, bytes, min_zoom, max_zoom, bbox."""
    tiles, ext = scan(src, min_zoom, max_zoom)
    ttype = TYPES[ext]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    zs = [t[2][0] for t in tiles]
    zmin, zmax = min(zs), max(zs)
    west = south = 1e9
    east = north = -1e9
    for _, _, (z, x, y) in tiles:
        if z != zmax:
            continue
        lon0, lat0 = tile_to_lonlat(z, x, y)
        lon1, lat1 = tile_to_lonlat(z, x + 1, y + 1)
        west, east = min(west, lon0), max(east, lon1)
        south, north = min(south, lat1), max(north, lat0)
    tile_comp = Compression.NONE
    with tmp.open("wb") as fh:
        writer = Writer(fh)
        first = True
        for i, (tid, path, _) in enumerate(tiles, 1):
            data = path.read_bytes()
            if first:
                tile_comp = Compression.GZIP if data[:2] == b"\x1f\x8b" else Compression.NONE
                first = False
            elif (data[:2] == b"\x1f\x8b") != (tile_comp == Compression.GZIP):
                raise SystemExit(f"Gemischte Kachelkompression bei {path}")
            writer.write_tile(tid, data)
            if i % 10000 == 0:
                log.info("%d/%d Kacheln", i, len(tiles))
        header = {
            "tile_type": ttype,
            "tile_compression": tile_comp,
            "min_zoom": zmin,
            "max_zoom": zmax,
            "min_lon_e7": int(west * 1e7),
            "min_lat_e7": int(south * 1e7),
            "max_lon_e7": int(east * 1e7),
            "max_lat_e7": int(north * 1e7),
            "center_zoom": zmin,
            "center_lon_e7": int((west + east) / 2 * 1e7),
            "center_lat_e7": int((south + north) / 2 * 1e7),
        }
        writer.finalize(header, dict(meta or {}))
    tmp.replace(out)
    return {"tiles": len(tiles), "bytes": out.stat().st_size, "min_zoom": zmin, "max_zoom": zmax,
            "bbox": [round(west, 5), round(south, 5), round(east, 5), round(north, 5)]}


def verify(src: Path, pm: Path, n: int, seed: int = 1, min_zoom: int = 0, max_zoom: int = 26) -> int:
    """Liest n zufällige Kacheln aus der PMTiles-Datei und vergleicht sie mit den Quelldateien. Gibt die Zahl der Abweichungen zurück."""
    tiles, _ = scan(src, min_zoom, max_zoom)
    rnd = random.Random(seed)
    sample = tiles if n >= len(tiles) else rnd.sample(tiles, n)
    bad = 0
    with pm.open("rb") as fh:
        reader = Reader(MmapSource(fh))
        for _, path, (z, x, y) in sample:
            got = reader.get(z, x, y)
            if got != path.read_bytes():
                bad += 1
                log.error("Abweichung bei %d/%d/%d", z, x, y)
    return bad


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def split(path: Path, part_bytes: int) -> dict:
    """Zerlegt path in <path>.part01 …, schreibt <path>.manifest.json und gibt das Manifest zurück."""
    parts = []
    total = hashlib.sha256()
    with path.open("rb") as fh:
        n = 0
        while True:
            n += 1
            name = f"{path.name}.part{n:02d}"
            h = hashlib.sha256()
            size = 0
            with (path.parent / name).open("wb") as pf:
                while size < part_bytes:
                    chunk = fh.read(min(CHUNK, part_bytes - size))
                    if not chunk:
                        break
                    pf.write(chunk)
                    h.update(chunk)
                    total.update(chunk)
                    size += len(chunk)
            if size == 0:
                (path.parent / name).unlink()
                break
            parts.append({"file": name, "bytes": size, "sha256": h.hexdigest()})
            if size < part_bytes:
                break
    manifest = {"name": path.name, "bytes": sum(p["bytes"] for p in parts), "sha256": total.hexdigest(), "parts": parts}
    (path.parent / (path.name + ".manifest.json")).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def join(manifest_path: Path, dest: Path) -> None:
    """Fügt die Teile laut Manifest zu dest zusammen und prüft Teil- und Gesamtsumme (Gegenstück zu split, auch für die App)."""
    man = json.loads(manifest_path.read_text(encoding="utf-8"))
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    total = hashlib.sha256()
    with tmp.open("wb") as out:
        for part in man["parts"]:
            h = hashlib.sha256()
            with (manifest_path.parent / part["file"]).open("rb") as fh:
                while chunk := fh.read(CHUNK):
                    h.update(chunk)
                    total.update(chunk)
                    out.write(chunk)
            if h.hexdigest() != part["sha256"]:
                tmp.unlink(missing_ok=True)
                raise ValueError(f"Prüfsumme falsch: {part['file']}")
    if total.hexdigest() != man["sha256"]:
        tmp.unlink(missing_ok=True)
        raise ValueError("Gesamtprüfsumme falsch")
    tmp.replace(dest)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--meta", type=Path)
    ap.add_argument("--split-mb", type=int, default=0)
    ap.add_argument("--keep-whole", action="store_true")
    ap.add_argument("--verify", type=int, default=200)
    ap.add_argument("--min-zoom", type=int, default=0)
    ap.add_argument("--max-zoom", type=int, default=26)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    meta = json.loads(a.meta.read_text(encoding="utf-8")) if a.meta else {}
    if not a.src.is_dir():
        log.error("Quellordner fehlt: %s", a.src)
        return 1
    info = pack(a.src, a.out, meta, a.min_zoom, a.max_zoom)
    log.info("Gepackt: %d Kacheln, Zoom %d–%d, %.1f MB", info["tiles"], info["min_zoom"], info["max_zoom"], info["bytes"] / 1e6)
    bad = verify(a.src, a.out, a.verify, 1, a.min_zoom, a.max_zoom) if a.verify else 0
    if bad:
        log.error("%d Kacheln weichen ab", bad)
        return 1
    log.info("Verifikation bestanden (%d Stichproben)", min(a.verify, info["tiles"]))
    if a.split_mb:
        man = split(a.out, a.split_mb * 1024 * 1024)
        log.info("In %d Teile zerlegt, Gesamtprüfsumme %s", len(man["parts"]), man["sha256"][:16])
        if not a.keep_whole:
            a.out.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
