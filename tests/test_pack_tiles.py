"""tools/pack_tiles.py: Kachelordner zu PMTiles, Zerlegen und Zusammenfügen mit Prüfsummen."""
import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import pack_tiles  # noqa: E402
from pmtiles.reader import MmapSource, Reader  # noqa: E402


def make_dir(root: Path, ext: str = "png", gz: bool = False) -> dict:
    tiles = {}
    for z, x, y in [(6, 33, 21), (7, 66, 42), (7, 67, 42), (8, 133, 85)]:
        d = root / str(z) / str(x)
        d.mkdir(parents=True, exist_ok=True)
        data = f"kachel-{z}-{x}-{y}".encode() * 20
        if gz:
            data = gzip.compress(data)
        (d / f"{y}.{ext}").write_bytes(data)
        tiles[(z, x, y)] = data
    (root / "README.txt").write_text("Pruefdatei")
    (root / "meta.json").write_text("{}")
    return tiles


def test_pack_roundtrip_png(tmp_path):
    tiles = make_dir(tmp_path / "dem")
    out = tmp_path / "o" / "dem.pmtiles"
    info = pack_tiles.pack(tmp_path / "dem", out, {"attribution": "© Test"})
    assert info["tiles"] == 4 and info["min_zoom"] == 6 and info["max_zoom"] == 8
    with out.open("rb") as fh:
        r = Reader(MmapSource(fh))
        for (z, x, y), data in tiles.items():
            assert r.get(z, x, y) == data
        assert r.header()["tile_type"].name == "PNG"
        assert r.metadata()["attribution"] == "© Test"
    assert pack_tiles.verify(tmp_path / "dem", out, 100) == 0


def test_pack_mvt_gzip_wird_erkannt(tmp_path):
    make_dir(tmp_path / "k", "pbf", gz=True)
    out = tmp_path / "k.pmtiles"
    pack_tiles.pack(tmp_path / "k", out)
    with out.open("rb") as fh:
        h = Reader(MmapSource(fh)).header()
    assert h["tile_type"].name == "MVT" and h["tile_compression"].name == "GZIP"


def test_leerer_ordner_und_gemischte_endungen_scheitern(tmp_path):
    (tmp_path / "leer").mkdir()
    with pytest.raises(SystemExit):
        pack_tiles.scan(tmp_path / "leer")
    make_dir(tmp_path / "m")
    (tmp_path / "m" / "9" / "1").mkdir(parents=True)
    (tmp_path / "m" / "9" / "1" / "1.pbf").write_bytes(b"x")
    with pytest.raises(SystemExit):
        pack_tiles.scan(tmp_path / "m")


def test_split_und_join(tmp_path):
    f = tmp_path / "x.pmtiles"
    f.write_bytes(bytes(range(256)) * 400)   # 102 400 Byte
    man = pack_tiles.split(f, 40_000)
    assert [p["bytes"] for p in man["parts"]] == [40_000, 40_000, 22_400]
    assert (tmp_path / "x.pmtiles.manifest.json").exists()
    dest = tmp_path / "zusammen.pmtiles"
    pack_tiles.join(tmp_path / "x.pmtiles.manifest.json", dest)
    assert dest.read_bytes() == f.read_bytes()


def test_join_erkennt_beschaedigten_teil(tmp_path):
    f = tmp_path / "x.pmtiles"
    f.write_bytes(b"a" * 10_000)
    pack_tiles.split(f, 4_000)
    p = tmp_path / "x.pmtiles.part02"
    p.write_bytes(b"b" + p.read_bytes()[1:])
    with pytest.raises(ValueError, match="Prüfsumme"):
        pack_tiles.join(tmp_path / "x.pmtiles.manifest.json", tmp_path / "ziel")
    assert not (tmp_path / "ziel").exists()


def test_cli_ende_zu_ende(tmp_path):
    make_dir(tmp_path / "dem")
    rc = pack_tiles.main(["--src", str(tmp_path / "dem"), "--out", str(tmp_path / "p" / "dem.pmtiles"),
                          "--meta", str(tmp_path / "dem" / "meta.json"), "--split-mb", "1"])
    assert rc == 0
    man = json.loads((tmp_path / "p" / "dem.pmtiles.manifest.json").read_text())
    assert len(man["parts"]) == 1 and not (tmp_path / "p" / "dem.pmtiles").exists()


def test_zoom_range_splits_into_base_and_more(tmp_path):
    from pmtiles.reader import MmapSource, Reader
    src = tmp_path / "s"
    for z, x, y in [(6, 33, 21), (12, 2145, 1380), (13, 4290, 2760), (14, 8580, 5520)]:
        p = src / str(z) / str(x) / f"{y}.png"; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"\x89PNG" + bytes([z]) * 8)
    base = pack_tiles.pack(src, tmp_path / "base.pmtiles", {}, 0, 12)
    more = pack_tiles.pack(src, tmp_path / "more.pmtiles", {}, 13, 26)
    assert (base["min_zoom"], base["max_zoom"], base["tiles"]) == (6, 12, 2)
    assert (more["min_zoom"], more["max_zoom"], more["tiles"]) == (13, 14, 2)
    assert pack_tiles.verify(src, tmp_path / "more.pmtiles", 10, 1, 13, 26) == 0
    with (tmp_path / "base.pmtiles").open("rb") as fh:
        assert Reader(MmapSource(fh)).get(13, 4290, 2760) is None
