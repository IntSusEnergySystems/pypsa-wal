# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Place individual machines and parks on the eligible raster, instead of
multiplying area by a capacity density.

Multiplying eligible area by MW/km2 assumes that the land comes in blocks large
enough to lay out an array.  Walloon eligible land does not: it is thousands of
disconnected patches, most of them smaller than one turbine's share of an array.
The area-times-density figure therefore counts land no machine could occupy,
while screening patches by size throws away land that a machine *could* occupy,
because a real turbine does not have to sit inside one contiguous eligible
polygon: the Walloon setbacks are measured from the mast.

Models, each adding one rule to the one before (see ``placement_lib.py``):

``free``
    Minimum inter-turbine distance only: the land-and-wake bound, and the
    quantity the VITO Dynamic Energy Atlas (BREGILAB) reports.
``parks``
    The park rule of the Cadre 2024 (§3.1, ``place_parks``): parks of at least
    ``min_turbines`` at the fleet's single-linkage distance, then -- under the
    exception for machines above 3.2 MW -- smaller groups on the land no park
    can use; 5 D between any two machines.
``parks+horizon``
    The reference: the same, plus the open-horizon rule of the Cadre de
    référence -- 130° of every village's horizon, within 4 km, free of
    turbines.
``parks+horizon+Nkm``
    The reference plus the inter-distance the Cadre recommends between parks,
    4 km in short-view and 6 km in long-view landscapes, measured between the
    nearest masts and waived along motorways.  A sensitivity, not the reference.
``parks4+horizon``
    The reference with parks of at least ``min_turbines`` and no exception.

Every parks layout is checked against its own rules by an independent
implementation (``check_layout``) and the run fails if one is violated.
"""

import logging
import sys
from pathlib import Path

# rasterio before geopandas: see retrieve_slope_raster.py.
import rasterio
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))
from placement_lib import (  # noqa: E402
    Horizon,
    allocate_free,
    check_layout,
    min_group,
    place_parks,
    motorway_distance,
    seed_scores,
)

logger = logging.getLogger(__name__)

SEED = 20260922


def eligible_cells(path):
    with rasterio.open(path) as src:
        mask = src.read(1).astype(bool)
        transform = src.transform
    rows, cols = np.nonzero(mask)
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e
    return mask, transform, rows, cols, xs, ys


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
    res = float(cfg["atlite"]["excluder_resolution"])
    pcfg = cfg["placement"]
    park_cfg = pcfg["park"]
    lcfg = pcfg["landscape"]

    mask, transform, rows, cols, xs, ys = eligible_cells(snakemake.input.raster)
    area_km2 = len(rows) * res * res / 1e6
    logger.info("%d eligible cells, %.1f km2", len(rows), area_km2)

    settlements = gpd.read_file(snakemake.input.settlements, layer="settlements")
    villages = np.c_[settlements.geometry.x, settlements.geometry.y]
    roads = gpd.read_file(snakemake.input.dual_carriageways, layer="data").to_crs(crs)
    dmw = motorway_distance(
        mask.shape, transform, roads[roads["highway"] == "motorway"].geometry, res
    )
    along_mw = dmw[rows, cols] <= float(lcfg["motorway_exemption_m"])
    logger.info("%.1f %% of the eligible cells are along a motorway", 100 * along_mw.mean())

    spacings = {k: float(v) * D for k, v in pcfg["spacings_rotor_diameters"].items()}
    ref_case = pcfg["reference_case"]
    link = float(park_cfg["link_m"])
    n_min = int(park_cfg["min_turbines"])
    small = park_cfg.get("small_groups", "after")
    score = seed_scores(mask, rows, cols, res, float(park_cfg["seed_radius_m"]))
    tree = cKDTree(np.c_[xs, ys])
    rng = np.random.default_rng(SEED)
    orders = {"row_major": np.arange(len(rows)), "random": rng.permutation(len(rows))}

    records, geoms = [], {}

    def linkage_sizes(gx, gy):
        """Group sizes at the fleet's single-linkage distance, as the fleet is grouped."""
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        pr = cKDTree(np.c_[gx, gy]).query_pairs(link, output_type="ndarray")
        m = len(gx)
        adj = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(m, m))
        return np.bincount(connected_components(adj, directed=False)[1])

    def record(model, case, dist, n, variant="", park=None, interdistance=None,
               refused=None, check=None, xy=None):
        sizes = np.bincount(park) if park is not None and len(park) else None
        sizes = sizes[sizes > 0] if sizes is not None else None
        groups = linkage_sizes(*xy) if xy is not None and n > 1 else None
        rec = {
            "turbine": turbine_key,
            "turbine_label": turbine["label"],
            "model": model,
            "spacing_case": case,
            "min_distance_m": round(dist, 1),
            "min_distance_rotor_diameters": round(dist / D, 2),
            "variant": variant,
            "interdistance_m": interdistance,
            "eligible_area_km2": round(area_km2, 2),
            "n_parks": int(len(sizes)) if sizes is not None else None,
            "turbines_per_park": round(float(sizes.mean()), 1) if sizes is not None else None,
            "median_park_size": float(np.median(sizes)) if sizes is not None else None,
            "largest_park": int(sizes.max()) if sizes is not None else None,
            "n_turbines": int(n),
            "p_nom_max_mw": round(n * p_nom, 0),
            "effective_density_mw_km2": round(n * p_nom / area_km2, 3),
            "refused_by_horizon": refused,
            "share_in_groups_below_min_pct": None if groups is None
            else round(100 * float(groups[groups < n_min].sum()) / n, 1),
            "share_single_pct": None if groups is None else round(100 * float((groups == 1).sum()) / n, 1),
            "check_ok": None if check is None else check["ok"],
            "check_min_spacing_m": None if check is None else check.get("min_spacing_m"),
            "check_worst_free_arc_deg": None if check is None else check.get("worst_free_arc_deg"),
        }
        records.append(rec)
        logger.info("%-22s %-10s d=%4.0f m %-10s -> %5d machines %7.0f MW%s", model, case,
                    dist, variant, n, n * p_nom,
                    "" if sizes is None else f", {len(sizes)} parks")
        return rec

    def parks(case, dist, horizon=True, interdistance=0.0, small_groups=small):
        hz = (Horizon(villages, D, lcfg["horizon_radius_m"], lcfg["min_free_azimuth_deg"])
              if horizon else None)
        idx, pid, refused = place_parks(xs, ys, score, dist, link=link, n_min=n_min,
                                        small_groups=small_groups, horizon=hz,
                                        interdistance=interdistance,
                                        along_motorway=along_mw, tree=tree)
        chk = check_layout(xs[idx], ys[idx], pid, dist, n_min=min_group(n_min, small_groups),
                           villages=villages if horizon else None, rotor_diameter=D,
                           radius=lcfg["horizon_radius_m"],
                           min_free_deg=lcfg["min_free_azimuth_deg"],
                           interdistance=interdistance, along_motorway=along_mw[idx])
        if not chk["ok"]:
            raise RuntimeError(f"layout breaks its own rules: {chk}")
        return idx, pid, refused, chk

    for case, dist in spacings.items():
        for oname, order in orders.items():
            keep = allocate_free(xs, ys, dist, order)
            record("free", case, dist, keep.sum(), variant=oname)
            if oname == "row_major":
                geoms[f"free_{case}"] = (xs[keep], ys[keep], np.full(int(keep.sum()), -1))
        runs = [("parks+horizon", dict(horizon=True))]
        if case == ref_case:
            runs = [("parks", dict(horizon=False)), ("parks+horizon", dict(horizon=True))]
            runs += [(f"parks+horizon+{int(d) // 1000}km", dict(horizon=True, interdistance=float(d)))
                     for d in lcfg["interdistance_m"]]
            if small != "none":
                runs += [("parks4+horizon", dict(horizon=True, small_groups="none"))]
        for model, kw in runs:
            idx, pid, refused, chk = parks(case, dist, **kw)
            record(model, case, dist, len(idx), park=pid,
                   interdistance=kw.get("interdistance", 0.0) or None,
                   refused=refused if kw.get("horizon") else None, check=chk,
                   xy=(xs[idx], ys[idx]))
            geoms[f"{model.replace('+', '_')}_{case}"] = (xs[idx], ys[idx], pid)

    df = pd.DataFrame(records)
    Path(snakemake.output.table).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(snakemake.output.table, index=False)

    out = Path(snakemake.output.points)
    if out.exists():
        out.unlink()
    for name, (gx, gy, fid) in geoms.items():
        gpd.GeoDataFrame(
            {"turbine": turbine_key, "park": fid},
            geometry=gpd.points_from_xy(gx, gy),
            crs=crs,
            index=range(len(gx)),
        ).to_file(out, driver="GPKG", layer=name)
    logger.info("wrote %s", snakemake.output.table)
