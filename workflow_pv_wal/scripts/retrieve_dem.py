# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Bring the SPW LiDAR terrain model (MNT 2021-2022, 1 m) of one province onto
the study grid.

The Region publishes its LiDAR digital *terrain* model (ground, vegetation and
buildings removed) as one 1 m GeoTIFF per province, under CC-BY 4.0: 2.6 GB for
Brabant wallon, 8.9-11.5 GB for the others.  It is used here, rather than the
ERRUISSOL slope classes of the wind study (restricted licence, CPA type D1,
and classes only -- no aspect) or the Copernicus GLO-30 surface model (which
carries tree and building heights and would invent slopes along every hedge).

The zip stores the GeoTIFF uncompressed, so it is read in place through
``/vsizip/``.  The TIFF itself is LZW-compressed in full-width strips of 11
rows; a direct ``gdalwarp`` onto the rotated study grid decompresses each strip
many times over (about two hours per province).  The reduction is therefore
done in two steps:

1. stream the source 20 rows at a time -- every strip is decompressed once --
   and average each 20 x 20 m block in the source's own grid (EPSG:3812), a
   block needing half its samples;
2. warp that 20 m raster onto the study grid (EPSG:3035) with an area-weighted
   average.

Each study cell is thus the mean ground height of the ~400 LiDAR samples
around it, smoothed over about one more cell by the second step; slope and
aspect are derived downstream over a 40 m baseline, the scale of a row of PV
tables.  (Brabant wallon, the first province processed, went through a direct
``gdalwarp -r average``; the two routes differ by far less than the terrain
variation that decides a slope class.)
"""

import json
import logging
import subprocess
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

logger = logging.getLogger(__name__)

F = 20   # 1 m samples per 20 m block


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logfile = open(snakemake.log[0], "w")  # noqa: SIM115
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=logfile)

    gdal = snakemake.params.gdal
    grid = json.loads(Path(snakemake.input.grid).read_text())
    out = Path(snakemake.output[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    zpath = Path(snakemake.input.zip)
    names = subprocess.run(["unzip", "-Z1", str(zpath)], check=True, capture_output=True,
                           text=True).stdout.split()
    tifs = [n for n in names if n.lower().endswith(".tif")]
    if len(tifs) != 1:
        raise RuntimeError(f"expected one GeoTIFF in {zpath}, found {tifs}")
    src_path = f"/vsizip/{zpath}/{tifs[0]}"

    native = out.with_name(out.stem + "_native20.tif")
    with rasterio.Env(GDAL_CACHEMAX=256), rasterio.open(src_path) as src:
        res = src.transform.a
        if abs(res - 1.0) > 1e-6:
            raise ValueError(f"expected a 1 m source, got {res} m")
        W, H = src.width // F, src.height // F
        nod = src.nodata
        prof = dict(driver="GTiff", width=W, height=H, count=1, dtype="float32",
                    crs=src.crs, transform=src.transform * rasterio.Affine.scale(F),
                    nodata=-9999.0, compress="deflate", predictor=3, tiled=True)
        logger.info("source %d x %d, nodata %s -> %d x %d blocks", src.width, src.height, nod, W, H)
        with rasterio.open(native, "w", **prof) as dst:
            # Written 256 rows at a time: row-by-row writes into a tiled,
            # compressed GeoTIFF re-encode every tile 256 times (a 3 GB file).
            buf, r0 = [], 0
            for r in range(H):
                a = src.read(1, window=Window(0, r * F, W * F, F)).astype(np.float32)
                bad = ~np.isfinite(a) | (a < -1000)
                if nod is not None:
                    bad |= a == nod
                a[bad] = 0.0
                s = a.reshape(F, W, F).sum(axis=(0, 2))
                n = (~bad).reshape(F, W, F).sum(axis=(0, 2))
                buf.append(np.where(n >= F * F // 2, s / np.maximum(n, 1), -9999.0).astype(np.float32))
                if len(buf) == 256 or r == H - 1:
                    dst.write(np.stack(buf)[None], window=Window(0, r0, W, len(buf)))
                    r0 += len(buf)
                    buf = []
                if r % 500 == 0:
                    logger.info("row %d / %d", r, H)

    minx, miny, maxx, maxy = grid["bounds"]
    res = grid["res"]
    subprocess.run([f"{gdal}/gdalwarp", "-overwrite", "-t_srs", f"EPSG:{grid['crs']}",
                    "-te", str(minx), str(miny), str(maxx), str(maxy), "-tr", str(res), str(res),
                    "-r", "average", "-srcnodata", "-9999", "-dstnodata", "-9999", "-ot", "Float32",
                    "-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=3", "-co", "TILED=YES",
                    "--config", "GTIFF_SRS_SOURCE", "EPSG", str(native), str(out)],
                   check=True, stdout=logfile, stderr=subprocess.STDOUT)
    native.unlink()
    logger.info("wrote %s", out)
