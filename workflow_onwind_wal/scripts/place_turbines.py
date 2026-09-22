# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Place individual machines on the eligible raster, instead of multiplying area
by a capacity density.

Multiplying eligible area by MW/km2 assumes that the land comes in blocks large
enough to lay out an array.  Walloon eligible land does not: it is thousands of
disconnected patches, most of them smaller than one turbine's share of an array.
The area-times-density figure therefore counts land no machine could occupy,
while screening patches by size throws away land that a machine *could* occupy,
because a real turbine does not have to sit inside one contiguous eligible
polygon.

The way out is the one VITO uses in the Dynamic Energy Atlas (Clymans et al.,
BREGILAB WP3, 2022): an allocation algorithm that walks the eligible cells and
accepts a machine wherever no previously accepted machine lies closer than a
minimum inter-turbine distance.  Patches smaller than an array still take one
turbine; a machine may stand at the edge of its patch with its rotor
overhanging ineligible land, which is what happens in reality and is legally
correct here, because the Walloon setbacks are measured from the mast.

Two models are run.

``free``
    The allocation as described above, with no further rule.  This is the upper
    bound on what the land can carry, and it is what BREGILAB reports.  It is
    *not* a plausible build-out: it produces a uniform carpet of machines across
    the whole Region, every one of them a lone turbine or a pair.

``farm``
    The same allocation, plus the two structural rules of the Walloon framework
    that the carpet violates:

      * **regroupement** --- the cadre de référence gives priority to grouping
        machines rather than dispersing them, and since 24 January 2024 a wind
        farm means at least four turbines.  A site that cannot take four
        machines is not a wind farm and is dropped.
      * **inter-distance** --- the same framework gives an indicative minimum
        distance of 4 to 6 km between wind farms, to protect the landscape and
        to avoid encircling villages.  Farm centres are therefore allocated
        first, under their own minimum distance, and machines only afterwards
        inside each farm.

    This is the model whose result the study reports.  It is still an upper
    bound --- it does not apply the azimuth-of-open-horizon test that the
    Region's own site-by-site study applies on top --- but it is the first one
    that produces something shaped like a set of wind farms.

Two cell orderings are run for the free model, row-major and pseudo-random, to
show how much the answer depends on the order in which the allocation walks the
land.
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import uniform_filter
from scipy.spatial import cKDTree

logger = logging.getLogger(__name__)

SEED = 20260922


def allocate(xs, ys, min_distance, order):
    """
    Greedy minimum-distance allocation.

    Cells are visited in `order`; a cell is accepted when no accepted cell lies
    within `min_distance`.  A uniform grid of cell size `min_distance` keeps the
    neighbour test to the nine surrounding buckets, so the whole pass is O(N).
    """
    buckets = {}
    keep = np.zeros(len(xs), dtype=bool)
    d2 = min_distance * min_distance
    for i in order:
        x, y = xs[i], ys[i]
        bx, by = int(x // min_distance), int(y // min_distance)
        clash = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py) in buckets.get((bx + dx, by + dy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < d2:
                        clash = True
                        break
                if clash:
                    break
            if clash:
                break
        if clash:
            continue
        buckets.setdefault((bx, by), []).append((x, y))
        keep[i] = True
    return keep


def allocate_farms(
    xs, ys, tree, land_score, min_turbine_distance, interfarm, radius, min_turbines
):
    """
    Two-level allocation: farm sites first, machines inside them afterwards.

    Candidate farm centres are the eligible cells, taken in decreasing order of
    how much eligible land lies within `radius` of them, so that the allocation
    settles on the parts of the Region that can actually hold a farm.  A
    candidate is committed only if it is at least `interfarm` from every
    committed centre *and* its own disc yields at least `min_turbines` machines;
    a candidate that fails the second test is skipped without blocking anything,
    so a poor site does not sterilise a good one next to it.
    """
    order = np.argsort(-land_score, kind="stable")
    centres = []
    centre_buckets = {}
    turbine_idx = []
    farm_id = []

    for i in order:
        if land_score[i] <= 0:
            break
        cx, cy = xs[i], ys[i]
        bx, by = int(cx // interfarm), int(cy // interfarm)
        clash = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py) in centre_buckets.get((bx + dx, by + dy), ()):
                    if (px - cx) ** 2 + (py - cy) ** 2 < interfarm * interfarm:
                        clash = True
                        break
                if clash:
                    break
            if clash:
                break
        if clash:
            continue

        members = np.asarray(tree.query_ball_point([cx, cy], radius), dtype=np.int64)
        if len(members) < min_turbines:
            continue
        # Fill the farm from its centre outwards: a real layout starts at the
        # best part of the site and works out.
        d = (xs[members] - cx) ** 2 + (ys[members] - cy) ** 2
        local = members[np.argsort(d, kind="stable")]
        keep = allocate(xs[local], ys[local], min_turbine_distance, np.arange(len(local)))
        if keep.sum() < min_turbines:
            continue
        centre_buckets.setdefault((bx, by), []).append((cx, cy))
        fid = len(centres)
        centres.append((cx, cy, int(keep.sum())))
        turbine_idx.extend(local[keep].tolist())
        farm_id.extend([fid] * int(keep.sum()))

    return np.asarray(turbine_idx, dtype=np.int64), np.asarray(farm_id), centres


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.config
    turbine_key = snakemake.wildcards.turbine
    turbine = cfg["turbines"][turbine_key]
    D = float(turbine["rotor_diameter"])
    p_nom = float(turbine["p_nom"])
    crs = cfg["atlite"]["crs"]
    pcfg = cfg["placement"]

    with rasterio.open(snakemake.input.raster) as src:
        mask = src.read(1).astype(bool)
        transform = src.transform
        res = abs(transform.a)

    rows, cols = np.nonzero(mask)
    # Cell centres in the equal-area working CRS.
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e
    area_km2 = len(rows) * res * res / 1e6
    logger.info("%d eligible cells, %.1f km2", len(rows), area_km2)

    sc = cfg["turbines"]["spacing_crosswind"]
    sd = cfg["turbines"]["spacing_downwind"]
    spacings = {
        "array": float(np.sqrt(sc * sd) * D),
        "bregilab": float(pcfg["bregilab_spacing_rotor_diameters"] * D),
    }

    rng = np.random.default_rng(SEED)
    orders = {"row_major": np.arange(len(rows)), "random": rng.permutation(len(rows))}

    # How much eligible land lies within the farm radius of each cell.  A box
    # filter of the mask is within a few per cent of a disc at this radius and
    # costs one pass instead of a convolution.
    radius = float(pcfg["farm"]["radius_m"])
    win = int(2 * radius / res) | 1
    land_score = uniform_filter(mask.astype(np.float32), size=win, mode="constant")[
        rows, cols
    ] * win * win
    tree = cKDTree(np.c_[xs, ys])

    records = []
    geoms = {}
    for sname, dist in spacings.items():
        for oname, order in orders.items():
            keep = allocate(xs, ys, dist, order)
            n = int(keep.sum())
            cap = n * p_nom
            records.append(
                {
                    "turbine": turbine_key,
                    "turbine_label": turbine["label"],
                    "model": "free",
                    "spacing_case": sname,
                    "min_distance_m": round(dist, 1),
                    "interfarm_distance_m": None,
                    "order": oname,
                    "eligible_area_km2": round(area_km2, 2),
                    "n_farms": None,
                    "turbines_per_farm": None,
                    "n_turbines": n,
                    "p_nom_max_mw": round(cap, 0),
                    "effective_density_mw_km2": round(cap / area_km2, 3),
                    "land_per_turbine_km2": round(area_km2 / max(n, 1), 4),
                }
            )
            logger.info(
                "free / %s / %s: d=%.0f m -> %d turbines, %.0f MW, %.2f MW/km2",
                sname,
                oname,
                dist,
                n,
                cap,
                cap / area_km2,
            )
            if oname == "row_major":
                geoms[f"free_{sname}"] = (xs[keep], ys[keep], np.full(n, -1))

    # ------------------------------------------------------------------
    # Farm model.  The inter-farm distance is swept across the 4-6 km band the
    # cadre de référence gives as indicative, because the answer is sensitive
    # to it and the framework does not fix a single value.
    # ------------------------------------------------------------------
    interfarm = [float(d) for d in pcfg["farm"]["interfarm_distance_m"]]
    cases = [(sn, d, f) for sn, d in spacings.items() for f in interfarm]
    for sname, dist, ifd in cases:
        idx, fid, centres = allocate_farms(
            xs,
            ys,
            tree,
            land_score,
            dist,
            ifd,
            radius,
            int(pcfg["farm"]["min_turbines"]),
        )
        n = len(idx)
        cap = n * p_nom
        records.append(
            {
                "turbine": turbine_key,
                "turbine_label": turbine["label"],
                "model": "farm",
                "spacing_case": sname,
                "min_distance_m": round(dist, 1),
                "interfarm_distance_m": ifd,
                "order": "land_score",
                "eligible_area_km2": round(area_km2, 2),
                "n_farms": len(centres),
                "turbines_per_farm": round(n / max(len(centres), 1), 1),
                "n_turbines": n,
                "p_nom_max_mw": round(cap, 0),
                "effective_density_mw_km2": round(cap / area_km2, 3),
                "land_per_turbine_km2": round(area_km2 / max(n, 1), 4),
            }
        )
        logger.info(
            "farm / %s / %.0f km: %d farms, %d turbines (%.1f per farm), %.0f MW",
            sname,
            ifd / 1000,
            len(centres),
            n,
            n / max(len(centres), 1),
            cap,
        )
        if ifd == interfarm[0]:
            geoms[f"farm_{sname}"] = (xs[idx], ys[idx], fid)

    df = pd.DataFrame(records)
    Path(snakemake.output.table).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(snakemake.output.table, index=False)

    out = Path(snakemake.output.points)
    if out.exists():
        out.unlink()
    for name, (gx, gy, fid) in geoms.items():
        gpd.GeoDataFrame(
            {"turbine": turbine_key, "farm": fid},
            geometry=gpd.points_from_xy(gx, gy),
            crs=crs,
            index=range(len(gx)),
        ).to_file(out, driver="GPKG", layer=name)
    logger.info("wrote %s", snakemake.output.table)
