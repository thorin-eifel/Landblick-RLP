"""Kacheln aus einer PMTiles-Datei lesen (nur Standardbibliothek), damit der lokale Server sie wie Einzeldateien ausliefern kann.

Zweck:      Relief (dem.pmtiles) und Felswände (klippen.pmtiles) kommen als je eine Paketdatei zur Desktop-App
            (tools/pack_tiles.py). Die Karte lädt sie aber über URLs der Form tiles/dem/{z}/{x}/{y}.png, weil die
            Höhenkachel-Bibliothek in einem Worker abruft, dem das Protokoll pmtiles:// fehlt. Dieses Modul liest die
            Kachel aus dem Paket; app/desktop.py liefert sie unter der alten URL aus. Der Karten-Code bleibt unverändert.
Format:     PMTiles v3, Verzeichnis- und Kachelkompression none oder gzip (so schreibt tools/pack_tiles.py).
Grenzen:    nur lesen, nur lokale Datei; ein Zugriff holt Verzeichnisse einmal und hält sie im Speicher
            (Größenordnung: einige MB für das Land). Threadsicher über eine Sperre je Datei.
Beispiel:   pk = PackArchive(Path("tiles/dem.pmtiles")); data, gz = pk.get(12, 2145, 1380)
"""
from __future__ import annotations

import gzip
import json
import struct
import threading
from dataclasses import dataclass
from pathlib import Path

COMP_NONE, COMP_GZIP = 1, 2
MAX_TILE_BYTES = 8 * 1024 * 1024   # Schutz gegen kaputte Verzeichnisse


class PackError(ValueError):
    """Datei ist keine lesbare PMTiles-v3-Datei."""


@dataclass(frozen=True)
class Header:
    root_off: int
    root_len: int
    meta_off: int
    meta_len: int
    leaf_off: int
    leaf_len: int
    data_off: int
    data_len: int
    internal_comp: int
    tile_comp: int
    tile_type: int
    min_zoom: int
    max_zoom: int


def tile_id(z: int, x: int, y: int) -> int:
    """Hilbert-Nummer der Kachel nach der PMTiles-Spezifikation; ValueError außerhalb des Bereichs."""
    if z < 0 or z > 26 or not (0 <= x < (1 << z)) or not (0 <= y < (1 << z)):
        raise ValueError("Kachel außerhalb des Bereichs")
    acc = sum(1 << (2 * t) for t in range(z))
    n = 1 << z
    d = 0
    s = n // 2
    while s > 0:
        rx = 1 if (x & s) > 0 else 0
        ry = 1 if (y & s) > 0 else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        s //= 2
    return acc + d


def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    val = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if b < 0x80:
            return val, pos
        shift += 7


def _decomp(data: bytes, comp: int) -> bytes:
    if comp == COMP_GZIP:
        return gzip.decompress(data)
    if comp in (COMP_NONE, 0):
        return data
    raise PackError(f"Kompression {comp} nicht unterstützt")


def _parse_dir(buf: bytes) -> list[tuple[int, int, int, int]]:
    """Verzeichnis als Liste (tile_id, offset, length, run_length), aufsteigend nach tile_id."""
    n, pos = _varint(buf, 0)
    ids: list[int] = []
    last = 0
    for _ in range(n):
        d, pos = _varint(buf, pos)
        last += d
        ids.append(last)
    runs = []
    for _ in range(n):
        r, pos = _varint(buf, pos)
        runs.append(r)
    lens = []
    for _ in range(n):
        ln, pos = _varint(buf, pos)
        lens.append(ln)
    offs: list[int] = []
    for i in range(n):
        o, pos = _varint(buf, pos)
        offs.append(offs[i - 1] + lens[i - 1] if (o == 0 and i > 0) else o - 1)
    return list(zip(ids, offs, lens, runs))


def _find(entries: list[tuple[int, int, int, int]], tid: int) -> tuple[int, int, int, int] | None:
    """Binärsuche nach dem Eintrag, der tid abdeckt (Einzelkachel oder Lauf), sonst None."""
    lo, hi = 0, len(entries) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if entries[mid][0] <= tid:
            lo = mid + 1
        else:
            hi = mid - 1
    if hi < 0:
        return None
    e = entries[hi]
    if e[3] == 0 or tid - e[0] < e[3]:
        return e
    return None


class PackArchive:
    """Lesezugriff auf eine PMTiles-Datei. get() liefert (Bytes, gzip?) einer Kachel oder None."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._dirs: dict[tuple[int, int], list[tuple[int, int, int, int]]] = {}
        with self.path.open("rb") as f:
            head = f.read(127)
        if len(head) < 127 or head[:7] != b"PMTiles" or head[7] != 3:
            raise PackError("keine PMTiles-v3-Datei")
        o = struct.unpack("<8Q", head[8:72])
        self.h = Header(o[0], o[1], o[2], o[3], o[4], o[5], o[6], o[7], head[97], head[98], head[99], head[100], head[101])
        self._fh = self.path.open("rb")
        self._meta: dict | None = None

    def close(self) -> None:
        self._fh.close()

    def _read(self, off: int, length: int) -> bytes:
        self._fh.seek(off)
        return self._fh.read(length)

    def _dir(self, off: int, length: int) -> list[tuple[int, int, int, int]]:
        key = (off, length)
        if key not in self._dirs:
            self._dirs[key] = _parse_dir(_decomp(self._read(off, length), self.h.internal_comp))
        return self._dirs[key]

    def metadata(self) -> dict:
        """Metadaten-JSON der Datei (Namensnennung usw.); leer, wenn unlesbar."""
        with self._lock:
            if self._meta is None:
                try:
                    self._meta = json.loads(_decomp(self._read(self.h.meta_off, self.h.meta_len), self.h.internal_comp) or b"{}")
                except (ValueError, OSError):
                    self._meta = {}
            return self._meta

    def get(self, z: int, x: int, y: int) -> tuple[bytes, bool] | None:
        """Kachel (z, x, y): (Bytes wie gespeichert, True wenn gzip-komprimiert) oder None, wenn nicht im Paket."""
        try:
            tid = tile_id(z, x, y)
        except ValueError:
            return None
        if z < self.h.min_zoom or z > self.h.max_zoom:
            return None
        with self._lock:
            off, length = self.h.root_off, self.h.root_len
            for _ in range(4):
                e = _find(self._dir(off, length), tid)
                if e is None:
                    return None
                if e[3] > 0:
                    if e[2] > MAX_TILE_BYTES:
                        raise PackError("Kachel größer als erlaubt")
                    return self._read(self.h.data_off + e[1], e[2]), self.h.tile_comp == COMP_GZIP
                off, length = self.h.leaf_off + e[1], e[2]
        return None
