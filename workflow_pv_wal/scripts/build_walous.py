# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Reduce the WALOUS 2023 land-cover map (1 m, 11 classes, EPSG:3812) to the
share of each 20 m cell of the study grid covered by each group of classes.

The 1 m map of Wallonia is some 5e10 pixels.  It is read window by window in
its own grid; each window is folded into 20 m blocks and the class counts of
each block are turned into shares (per cent, uint8) of the configured groups.
These native 20 m shares are then warped onto the study grid (EPSG:3035)
with an area-weighted average.  Peak memory is one window (a few tens of MB)
plus the native share rasters.

Pixels outside every class (no data) do not count in the denominator.
"""

import json
import logging
import subprocess
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

logger = logging.getLogger(__name__)

BLOCK_M = 20
WIN_BLOCKS = 128      # 128 blocks of 20 m = 2 560 px, a multiple of the file's 128 px tiles
WORKERS = 4

_SRC = None


def _init(path, lut, f, ngroups):
    global _SRC, _LUT, _F, _NG
    _SRC = rasterio.open(path)
    _LUT, _F, _NG = lut, f, ngroups


def _window(args):
    """Group shares (per cent) of every 20 m block of one window."""
    bx, by, w, h = args
    a = _SRC.read(1, window=Window(bx * _F, by * _F, w * _F, h * _F)).view(np.uint8)
    seen = np.bincount(a.ravel(), minlength=256)
    g = _LUT[a].reshape(h, _F, w, _F)
    out = np.full((_NG, h, w), 255, dtype=np.uint8)
    valid = (g >= 0).sum(axis=(1, 3))
    ok = valid > 0
    for gi in range(_NG):
        n = (g == gi).sum(axis=(1, 3))
        out[gi][ok] = np.rint(100.0 * n[ok] / valid[ok]).astype(np.uint8)
    return bx, by, w, h, out, seen


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logfile = open(snakemake.log[0], "w")  # noqa: SIM115
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=logfile)

    groups = snakemake.params.groups
    gdal = snakemake.params.gdal
    grid = json.loads(Path(snakemake.input.grid).read_text())
    folder = Path(snakemake.input.folder).parent
    tifs = sorted(folder.rglob("*.tif"))
    if len(tifs) != 1:
        vrt = folder / "walous.vrt"
        subprocess.run([f"{gdal}/gdalbuildvrt", str(vrt)] + [str(t) for t in tifs], check=True,
                       stdout=logfile, stderr=subprocess.STDOUT)
        src_path = vrt
    else:
        src_path = tifs[0]
    logger.info("source %s", src_path)

    lut = np.zeros(256, dtype=np.int16) - 1
    names = list(groups)
    for gi, g in enumerate(names):
        for c in groups[g]:
            lut[c] = gi

    tmpdir = Path(snakemake.output.stats).parent / "walous_native"
    tmpdir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(src_path) as src:
        res = src.transform.a
        f = int(round(BLOCK_M / res))
        if abs(f * res - BLOCK_M) > 1e-6:
            raise ValueError(f"source resolution {res} m does not divide {BLOCK_M} m")
        W, H = src.width // f, src.height // f
        logger.info("source %d x %d at %.2f m -> %d x %d blocks of %d m", src.width,
                    src.height, res, W, H, BLOCK_M)
        tr = src.transform * rasterio.Affine.scale(f)
        prof = dict(driver="GTiff", width=W, height=H, count=len(names), dtype="uint8",
                    crs=src.crs, transform=tr, compress="deflate", tiled=True, nodata=255)
        native = tmpdir / "shares.tif"
    classes_seen = np.zeros(256, dtype=np.int64)
    tasks = [(bx, by, min(WIN_BLOCKS, W - bx), min(WIN_BLOCKS, H - by))
             for by in range(0, H, WIN_BLOCKS) for bx in range(0, W, WIN_BLOCKS)]
    logger.info("%d windows on %d workers", len(tasks), WORKERS)
    from multiprocessing import Pool
    with rasterio.open(native, "w", **prof) as dst, Pool(
            WORKERS, initializer=_init, initargs=(str(src_path), lut, f, len(names))) as pool:
        for n, (bx, by, w, h, out, seen) in enumerate(pool.imap_unordered(_window, tasks, chunksize=4)):
            dst.write(out, window=Window(bx, by, w, h))
            classes_seen += seen
            if n % 500 == 0:
                logger.info("window %d / %d", n, len(tasks))

    minx, miny, maxx, maxy = grid["bounds"]
    for gi, (g, path) in enumerate(zip(names, snakemake.output[: len(names)])):
        subprocess.run([f"{gdal}/gdalwarp", "-overwrite", "-b", str(gi + 1), "-t_srs",
                        f"EPSG:{grid['crs']}", "-te", str(minx), str(miny), str(maxx), str(maxy),
                        "-tr", str(grid["res"]), str(grid["res"]), "-r", "average",
                        "-srcnodata", "255", "-dstnodata", "255", "-ot", "Byte",
                        "-co", "COMPRESS=DEFLATE", "-co", "TILED=YES",
                        "--config", "GTIFF_SRS_SOURCE", "EPSG",
                        str(native), path], check=True, stdout=logfile, stderr=subprocess.STDOUT)
    seen = {int(c): int(n) for c, n in enumerate(classes_seen) if n}
    unmapped = {c: n for c, n in seen.items() if lut[c] < 0}
    stats = {"source": str(src_path), "classes_pixels": seen, "unmapped_classes": unmapped,
             "groups": groups}
    Path(snakemake.output.stats).write_text(json.dumps(stats, indent=2))
    logger.info("%s", stats)
