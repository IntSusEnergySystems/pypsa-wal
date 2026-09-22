# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Test the constraint set against the turbines that are actually standing.

A land-eligibility study is a claim about where a machine may be built.  The
cheapest way to find out whether the claim is calibrated is to point it at the
machines that exist: if the constraint set says most of the standing fleet is
illegal, the constraint set is too strict, and the potential it produces is too
low.

Three things are measured:

  * which rung of the scenario ladder first excludes each standing turbine,
  * which individual constraint layers cover its position, and
  * for each layer, the **avoidance ratio**: the share of standing turbines
    inside the layer divided by the share of the Region the layer covers.  A
    ratio well below one says that developers and the permitting authority
    treat the constraint as real; a ratio at or above one says that they do
    not, whatever the layer is called.

None of it is a pass/fail test.  Walloon wind development began under the 2002 and
2013 frameworks and much of the fleet predates the rules applied here; the
landscape perimeters and several of the hazard layers are *partial* constraints
in permitting practice, which an area calculation must treat as binary.  The
numbers therefore bound how conservative the constraint set is, and say which
rule does the bounding.
"""

import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

logger = logging.getLogger(__name__)

RASTER_LAYERS = {"dwelling_setback": "dwelling_raster", "slope": "slope_raster"}


def raster_hits(path, points, codes=(1,)):
    with rasterio.open(path) as src:
        vals = np.array(
            [v[0] for v in src.sample([(p.x, p.y) for p in points.geometry])]
        )
    return np.isin(vals, codes)


def raster_land_share(path, shape, codes=(1,)):
    """Share of `shape` covered by the raster's coded cells."""
    with rasterio.open(path) as src:
        window = rasterio.windows.from_bounds(*shape.bounds, transform=src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(1, window=window)
        transform = src.window_transform(window)
    inside = geometry_mask(
        [shape], out_shape=data.shape, transform=transform, invert=True
    )
    if not inside.any():
        return 0.0
    return float(np.isin(data[inside], codes).mean())


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.config
    crs = cfg["atlite"]["crs"]
    scenarios = cfg["scenarios"]
    ladder = [s for s in scenarios if scenarios[s]["mode"] == "walloon"]

    fleet = gpd.read_file(snakemake.input.points, layer="data").to_crs(crs)
    n = len(fleet)
    logger.info("%d standing turbines", n)

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"].geometry.union_all()
    region_area = admin.area

    layer_dir = Path(snakemake.input.layer_dir)
    covered = {}
    land_share = {}
    for name in scenarios[cfg["reference_scenario"]]["layers"]:
        if name in RASTER_LAYERS:
            path = snakemake.input[RASTER_LAYERS[name]]
            covered[name] = raster_hits(path, fleet)
            land_share[name] = raster_land_share(path, admin)
        else:
            path = layer_dir / f"{name}.gpkg"
            if not path.exists():
                continue
            geom = gpd.read_file(path).to_crs(crs).union_all()
            covered[name] = fleet.within(geom).values
            land_share[name] = float(geom.intersection(admin).area / region_area)
        logger.info(
            "%-24s covers %5.1f %% of the Region and %4d of %d standing turbines "
            "(%.1f %%), avoidance ratio %.2f",
            name,
            100 * land_share[name],
            covered[name].sum(),
            n,
            100 * covered[name].mean(),
            covered[name].mean() / land_share[name] if land_share[name] else float("nan"),
        )

    out = {
        "n_turbines": n,
        "by_layer": {
            k: {
                "n": int(v.sum()),
                "pct": round(100 * float(v.mean()), 1),
                "land_pct": round(100 * land_share[k], 1),
                "avoidance_ratio": (
                    round(float(v.mean()) / land_share[k], 2) if land_share[k] else None
                ),
            }
            for k, v in covered.items()
        },
        "by_scenario": {},
    }
    for s in ladder:
        hit = np.zeros(n, dtype=bool)
        for name in scenarios[s]["layers"]:
            if name in covered:
                hit |= covered[name]
        out["by_scenario"][s] = {
            "excluded": int(hit.sum()),
            "surviving": int(n - hit.sum()),
            "surviving_pct": round(100 * float(1 - hit.mean()), 1),
        }
        logger.info("%s: %d of %d standing turbines survive", s, n - hit.sum(), n)

    # The layers that, on their own, account for most of the exclusions.
    ranked = sorted(out["by_layer"].items(), key=lambda kv: -kv[1]["n"])
    out["dominant_layers"] = [k for k, _ in ranked[:3]]

    # How the standing fleet is itself grouped.  Single-linkage clustering at
    # `farm_link_m` turns the turbine positions into wind farms, which is the
    # only way to compare the farm-allocation model with reality: it predicts a
    # number of farms and a number of machines in each, and Wallonia already has
    # both.
    link = float(snakemake.params.farm_link_m)
    xy = np.c_[fleet.geometry.x, fleet.geometry.y]
    tree = cKDTree(xy)
    pairs = tree.query_pairs(link, output_type="ndarray")
    if len(pairs):
        adj = coo_matrix(
            (np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)
        )
    else:
        adj = coo_matrix((n, n))
    n_farms, labels = connected_components(adj, directed=False)
    sizes = np.bincount(labels)
    out["farms"] = {
        "link_distance_m": link,
        "n_farms": int(n_farms),
        "turbines_per_farm": round(float(n / n_farms), 1),
        "n_farms_ge_4": int((sizes >= 4).sum()),
        "turbines_in_farms_ge_4": int(sizes[sizes >= 4].sum()),
        "largest_farm": int(sizes.max()),
    }
    logger.info("standing fleet groups into %s", json.dumps(out["farms"]))

    Path(snakemake.output.table).write_text(json.dumps(out, indent=2))
