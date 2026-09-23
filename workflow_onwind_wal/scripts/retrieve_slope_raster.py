# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Build the ``slope >= 7 %`` exclusion raster from the Walloon slope-class map.

The 2013 Walloon favourable-zone methodology excludes slopes above 7 % as
technically incompatible with the crane pad and the access track of a large
machine.  The Region publishes the underlying grid --- ``ERRUISOL_CLASSE_PENTE``,
slope in per cent derived from the 10 m ERRUISSOL digital terrain model --- but
only as a *visualisation* service: there is no feature query and no coverage
download.  What the service does expose is ``export``, which renders an exact
bounding box into an exact number of pixels with nearest-neighbour resampling
and a seven-colour palette, one colour per slope class.  Decoding those colours
recovers the class grid losslessly.

The classes are ``0-1``, ``1-3``, ``3-5``, ``5-7``, ``7-10``, ``10-15`` and
``> 15`` per cent, so the 7 % threshold of the Walloon rule falls exactly on a
class boundary and no interpolation is involved.  The per-class sample counts
are kept, so the 10 % and 15 % masks of the sensitivity analysis come out of
the same decode.

Sampling.  The source is 10 m; a turbine needs a platform of order one hectare.
The raster is therefore rendered at ``SAMPLE_RES`` (25 m) and a 100 m cell is
marked excluded when the **majority** of its 25 m samples are at or above 7 %,
i.e. when most of the hectare is too steep --- not when a single steep pixel
touches it.
"""

import json
import logging
from io import BytesIO
from pathlib import Path

# rasterio before geopandas: in this environment the reverse import order makes
# the first deflate-compressed GeoTIFF write abort ("double free or corruption").
import rasterio
import geopandas as gpd
import numpy as np
import requests
from PIL import Image
from rasterio.transform import from_origin

logger = logging.getLogger(__name__)

SERVICE = "SOL_SOUS_SOL/ERRUISOL_CLASSE_PENTE"
URL = f"https://geoservices.wallonie.be/arcgis/rest/services/{SERVICE}/MapServer/export"

# Rendered palette of the slope-class renderer, in class order.  Verified
# against the service on 22 September 2026: an export of any window of Wallonia
# contains these seven colours and nothing else besides the no-data white.
PALETTE = {
    (115, 193, 76): 0.5,    # 0-1 %
    (153, 213, 76): 2.0,    # 1-3 %
    (199, 232, 76): 4.0,    # 3-5 %
    (254, 254, 76): 6.0,    # 5-7 %
    (254, 195, 76): 8.5,    # 7-10 %
    (254, 135, 76): 12.5,   # 10-15 %
    (254, 76, 76): 20.0,    # > 15 %
}
NODATA_RGB = (253, 253, 253)

SAMPLE_RES = 25          # m, the resolution the service is rendered at
TILE_PX = 2000           # px per tile side (50 km at 25 m)
RETRIES = 4


def export_tile(session, minx, miny, maxx, maxy, width, height, crs):
    params = {
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "bboxSR": crs,
        "imageSR": crs,
        "size": f"{width},{height}",
        "format": "png32",
        "transparent": "false",
        "dpi": 96,
        "f": "image",
    }
    last = None
    for attempt in range(RETRIES):
        try:
            r = session.get(URL, params=params, timeout=300)
            r.raise_for_status()
            return np.asarray(Image.open(BytesIO(r.content)).convert("RGB"))
        except Exception as exc:  # noqa: BLE001 - retried
            last = exc
            logger.warning("tile attempt %d/%d failed (%s)", attempt + 1, RETRIES, exc)
    raise RuntimeError(f"export failed: {last}")


# Lower bound of each class, in palette order: a threshold is exact only if it
# is one of these.
CLASS_FLOOR = [0.0, 1.0, 3.0, 5.0, 7.0, 10.0, 15.0]


def classify(rgb):
    """RGB tile -> class index per sample (-1 where no class colour)."""
    cls = np.full(rgb.shape[:2], -1, dtype=np.int8)
    key = (rgb[..., 0].astype(np.int32) << 16) | (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2]
    for k, (r, g, b) in enumerate(PALETTE):
        cls[key == ((r << 16) | (g << 8) | b)] = k
    return cls


def write_mask(path, mask, transform, crs):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=mask.shape[0],
        width=mask.shape[1],
        count=1,
        dtype="uint8",
        crs=f"EPSG:{crs}",
        transform=transform,
        compress="deflate",
        nodata=255,
    ) as dst:
        dst.write(mask, 1)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    crs = int(snakemake.params.crs)
    out_res = int(snakemake.params.out_res)
    threshold = float(snakemake.params.threshold_pct)
    extra = [float(t) for t in snakemake.params.sensitivity_thresholds_pct]
    for t in [threshold] + extra:
        if t not in CLASS_FLOOR[1:]:
            raise ValueError(f"{t} % is not a class boundary of the published grid")

    factor = out_res // SAMPLE_RES
    if out_res % SAMPLE_RES:
        raise ValueError("out_res must be a multiple of the sampling resolution")

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]
    minx, miny, maxx, maxy = admin.total_bounds
    # Snap outward to the output grid so the result aligns with the other rasters.
    minx = np.floor(minx / out_res) * out_res
    miny = np.floor(miny / out_res) * out_res
    maxx = np.ceil(maxx / out_res) * out_res
    maxy = np.ceil(maxy / out_res) * out_res

    width = int((maxx - minx) / out_res)
    height = int((maxy - miny) / out_res)
    logger.info("output grid %d x %d at %d m", width, height, out_res)

    # Samples of each slope class per output cell.
    counts = np.zeros((len(PALETTE), height, width), dtype=np.int16)

    tile_m = TILE_PX * SAMPLE_RES
    session = requests.Session()
    n_tiles = 0
    for ty in range(int(np.ceil((maxy - miny) / tile_m))):
        for tx in range(int(np.ceil((maxx - minx) / tile_m))):
            x0 = minx + tx * tile_m
            y1 = maxy - ty * tile_m
            x1 = min(x0 + tile_m, maxx)
            y0 = max(y1 - tile_m, miny)
            w = int(round((x1 - x0) / SAMPLE_RES))
            h = int(round((y1 - y0) / SAMPLE_RES))
            if w <= 0 or h <= 0:
                continue
            rgb = export_tile(session, x0, y0, x1, y1, w, h, crs)
            cls = classify(rgb)
            # Aggregate the 25 m samples into the 100 m output cells.
            sh, sw = cls.shape[0] // factor, cls.shape[1] // factor
            cls = cls[: sh * factor, : sw * factor].reshape(sh, factor, sw, factor)
            r0 = int(round((maxy - y1) / out_res))
            c0 = int(round((x0 - minx) / out_res))
            for k in range(len(PALETTE)):
                counts[k, r0 : r0 + sh, c0 : c0 + sw] += (cls == k).sum(axis=(1, 3)).astype(np.int16)
            n_tiles += 1
            logger.info("tile %d: %d x %d px at (%.0f, %.0f)", n_tiles, w, h, x0, y1)

    cells = factor * factor
    valid_count = counts.sum(axis=0)
    covered = valid_count >= cells // 2
    transform = from_origin(minx, maxy, out_res, out_res)

    def steep_mask(t):
        steep = counts[CLASS_FLOOR.index(t):].sum(axis=0)
        return ((steep > valid_count / 2.0) & covered).astype(np.uint8)

    mask = steep_mask(threshold)
    logger.info(
        "%.1f %% of the covered grid is at or above %.0f %% slope",
        100 * mask.sum() / max(covered.sum(), 1),
        threshold,
    )
    write_mask(snakemake.output.raster, mask, transform, crs)
    shares = {}
    for t, path in zip(extra, snakemake.output.sensitivity):
        m = steep_mask(t)
        write_mask(path, m, transform, crs)
        shares[f"{t:g}"] = round(float(m.sum()) / max(int(covered.sum()), 1), 4)
        logger.info("%.1f %% of the covered grid is at or above %.0f %% slope",
                    100 * shares[f"{t:g}"], t)

    meta = {
        "service": SERVICE,
        "layer": 0,
        "title": "Classes de pentes ERRUISSOL (MNT 10 m)",
        "threshold_pct": threshold,
        "sample_res_m": SAMPLE_RES,
        "out_res_m": out_res,
        "rule": "cell excluded when the majority of its 25 m samples are >= 7 %",
        "covered_cells": int(covered.sum()),
        "excluded_cells": int(mask.sum()),
        "excluded_share_of_covered": round(float(mask.sum()) / max(int(covered.sum()), 1), 4),
        "sensitivity_shares_of_covered": shares,
        "tiles": n_tiles,
        "licence": "CC-BY 4.0, Géoportail de la Wallonie",
    }
    Path(snakemake.output.meta).write_text(json.dumps(meta, indent=2))
    logger.info("wrote %s", snakemake.output.raster)
