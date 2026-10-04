# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Slope and aspect on the study grid, from the 20 m mean of the LiDAR terrain
model.

Central differences over two cells, i.e. a 40 m baseline (Horn's 3 x 3
operator, as ``gdaldem`` uses): the slope a row of PV tables and its access
track sit on, not the micro-relief of a furrow or a ditch.  Cells whose 3 x 3
neighbourhood has no data (outside the LiDAR coverage) get no slope and are
treated as flat, which the exclusion step reports.

Outputs, both uint8 or uint16 on the study grid:

``slope_pct.tif``   slope in per cent, rounded, capped at 254 (255 = no data)
``aspect_deg.tif``  downslope azimuth in degrees clockwise from north
                    (0-359), 65535 where the slope is below 0.5 % (flat)
"""

import json
import logging
from pathlib import Path

import numpy as np
import rasterio

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    with rasterio.open(snakemake.input.dem) as src:
        z = src.read(1)
        profile = src.profile
        res = src.transform.a
    nodata = z == -9999
    z[nodata] = np.nan
    logger.info("DEM %s, %.1f %% no data", z.shape, 100 * nodata.mean())

    # Horn (1981): weighted central differences on the 3 x 3 window.
    p = np.pad(z, 1, mode="edge")
    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]
    d, f = p[1:-1, :-2], p[1:-1, 2:]
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * res)   # east positive
    del a, c, d, f, g, i
    p0 = p
    dzdy = ((p0[:-2, :-2] + 2 * b + p0[:-2, 2:]) - (p0[2:, :-2] + 2 * h + p0[2:, 2:])) / (8 * res)  # north positive
    del p, p0, b, h
    slope = 100.0 * np.hypot(dzdx, dzdy)
    # Downslope direction: the terrain falls towards -grad(z).
    aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360.0) % 360.0
    del dzdx, dzdy

    bad = ~np.isfinite(slope)
    s8 = np.where(bad, 255, np.clip(np.rint(slope), 0, 254)).astype(np.uint8)
    a16 = np.where(bad | (slope < 0.5), 65535, np.rint(aspect) % 360).astype(np.uint16)

    prof = dict(profile, dtype="uint8", nodata=255, compress="deflate", tiled=True, predictor=2)
    with rasterio.open(snakemake.output.slope, "w", **prof) as dst:
        dst.write(s8, 1)
    prof = dict(profile, dtype="uint16", nodata=65535, compress="deflate", tiled=True, predictor=2)
    with rasterio.open(snakemake.output.aspect, "w", **prof) as dst:
        dst.write(a16, 1)

    with rasterio.open(snakemake.input.region_mask) as src:
        region = src.read(1).astype(bool)
    sv = s8[region & (s8 != 255)]
    stats = {
        "region_cells_without_dem": int((region & (s8 == 255)).sum()),
        "slope_pct_quantiles": {q: int(np.percentile(sv, q)) for q in (50, 75, 90, 95, 99)},
        "share_ge": {t: round(float((sv >= t).mean()), 4) for t in (5, 7, 10, 15, 20, 25)},
    }
    Path(snakemake.output.stats).write_text(json.dumps(stats, indent=2))
    logger.info("%s", stats)
