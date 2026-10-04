# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Annual yield (full-load hours) of each PV system, on the model's weather year.

atlite converts the SARAH-3 / ERA5 cutout of PyPSA-Eur (2010) into a capacity
factor per weather cell for a given panel orientation, exactly as the model's
own ``solar`` profile is built.  The yield of a system is the mean over the
weather cells, weighted by the technically eligible land of the reference in
each cell (the 20 m raster is summed over 1 km blocks and each block is given
to the weather cell that contains it).

Systems (``config.energy.systems``):

``ground``               fixed, south, at the latitude-optimal tilt, as the
                         model's ``solar``
``agrivoltaic_grazing``  fixed, south, 25° (elevated, wide rows over pasture)
``agrivoltaic_canopy``   fixed, south, 20° (canopy over fruit)
``agrivoltaic_crops``    vertical bifacial, rows north-south: the east face at
                         its rating plus the west face times the bifaciality
``floating``             fixed, south, 12° (float structures)

The model's weather profile carries no cooling or albedo gain, and neither do
these; a floating plant's cooling gain (a few per cent) is left out.
"""

import json
import logging
from pathlib import Path

import atlite
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

logger = logging.getLogger(__name__)

BLOCK = 50   # 50 x 20 m = 1 km


def yield_per_cell(cutout, spec):
    kind = spec.get("kind", "fixed")
    if kind == "vertical_bifacial":
        east = cutout.pv(panel=spec["panel"], orientation={"slope": 90.0, "azimuth": 90.0},
                         capacity_factor=True)
        west = cutout.pv(panel=spec["panel"], orientation={"slope": 90.0, "azimuth": 270.0},
                         capacity_factor=True)
        return east + spec["bifaciality"] * west
    if spec.get("tilt") == "latitude_optimal":
        orient = "latitude_optimal"
    else:
        orient = {"slope": float(spec["tilt"]), "azimuth": float(spec.get("azimuth", 180.0))}
    return cutout.pv(panel=spec["panel"], orientation=orient, capacity_factor=True)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    cfg = snakemake.params.energy
    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(4326)
    minx, miny, maxx, maxy = regions[regions["name"] == "admin"].total_bounds
    pad = 0.5
    cutout = atlite.Cutout(snakemake.input.cutout).sel(
        x=slice(minx - pad, maxx + pad), y=slice(miny - pad, maxy + pad))
    logger.info("cutout trimmed to %s", dict(cutout.data.sizes))

    # Weights: eligible land (technical, reference) per weather cell.
    with rasterio.open(Path(snakemake.input.tech_land) / "tech_land.tif") as src:
        a = src.read(1).astype(np.float32)
        tr = src.transform
        crs = src.crs
    h, w = (a.shape[0] // BLOCK) * BLOCK, (a.shape[1] // BLOCK) * BLOCK
    blocks = a[:h, :w].reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK).sum(axis=(1, 3))
    rr, cc = np.nonzero(blocks)
    xs = tr.c + (cc + 0.5) * BLOCK * tr.a
    ys = tr.f + (rr + 0.5) * BLOCK * tr.e
    lon, lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(xs, ys)
    cx, cy = cutout.data.x.values, cutout.data.y.values
    ix = np.abs(lon[:, None] - cx[None, :]).argmin(axis=1)
    iy = np.abs(lat[:, None] - cy[None, :]).argmin(axis=1)
    weights = np.zeros((len(cy), len(cx)))
    np.add.at(weights, (iy, ix), blocks[rr, cc])
    weights /= weights.sum()
    logger.info("eligible land spread over %d weather cells", int((weights > 0).sum()))

    rows = []
    for name, spec in cfg["systems"].items():
        cf = yield_per_cell(cutout, spec)
        cf = cf.transpose("y", "x").values
        flh = float((cf * weights).sum() * 8760)
        spread = cf[weights > 0] * 8760
        rows.append({"system": name, "flh_h": round(flh, 0),
                     "flh_min_h": round(float(spread.min()), 0),
                     "flh_max_h": round(float(spread.max()), 0),
                     "description": spec["label"]})
        logger.info("%-22s %5.0f h (%.0f-%.0f)", name, flh, spread.min(), spread.max())
    pd.DataFrame(rows).to_csv(snakemake.output.table, index=False)
    Path(snakemake.output.json).write_text(json.dumps({r["system"]: r for r in rows}, indent=2))
