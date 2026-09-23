# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Test the constraint set and the siting rules against the turbines that are
actually standing.

A land-eligibility study is a claim about where a machine may be built.  The
cheapest way to find out whether the claim is calibrated is to point it at the
machines that exist.  Four things are measured.

Avoidance ratios.  For each exclusion layer, the share of the standing fleet
inside it divided by the share of the land it covers.  A ratio well below one
says developers and the permitting authority treat the layer as a constraint; a
ratio near one says they do not, whatever it is called.  The ratio is reported
twice: against the whole Region, and *conditionally* -- counting only the land
and the machines that pass every other layer of the set.  The conditional ratio
is the one that tests the layer: steep slopes, for instance, are mostly in
forest that the zoning already excludes, so the whole-Region ratio of a slope
layer mostly measures the forest.  The two size-dependent setbacks are left
out of the conditions, because most standing machines are smaller than the
reference class.

Farm geometry.  The fleet grouped into farms by single linkage, and the
distances between farms measured the way the Region measures its
inter-distance -- between the nearest masts of two farms -- with the share of
farms that stand along a motorway, where the inter-distance does not apply.

Dwellings.  Which addresses lie within 400 m of a standing machine, by zone.

Open horizon.  Whether the fleet respects the 130° rule of the Cadre, using the
placement model's own implementation.
"""

import json
import logging
import sys
from pathlib import Path

# rasterio before geopandas: see retrieve_slope_raster.py.
import rasterio
import geopandas as gpd
import numpy as np
from atlite.gis import ExclusionContainer, shape_availability
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parent))
from placement_lib import Horizon  # noqa: E402

logger = logging.getLogger(__name__)

RASTER_LAYERS = {"dwelling_setback": "dwelling_raster", "slope": "slope_raster"}
SIZE_DEPENDENT = {"habitat_setback", "dwelling_setback"}


def pct(a, qs=(5, 10, 25, 50, 75, 90)):
    return {f"p{q}": round(float(np.percentile(a, q)), 1) for q in qs}


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
    res = float(cfg["atlite"]["excluder_resolution"])
    scenarios = cfg["scenarios"]
    ladder = [s for s in scenarios if scenarios[s]["mode"] == "walloon"]
    ref_layers = list(scenarios[cfg["reference_scenario"]]["layers"])
    layer_dir = Path(snakemake.input.layer_dir)

    fleet = gpd.read_file(snakemake.input.points, layer="data").to_crs(crs)
    n = len(fleet)
    xy = np.c_[fleet.geometry.x, fleet.geometry.y]
    logger.info("%d standing turbines", n)
    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]

    # ------------------------------------------------------------------
    # 1. Avoidance ratios, on the exclusion raster itself
    # ------------------------------------------------------------------
    def burn(name):
        ex = ExclusionContainer(crs=crs, res=res)
        if name in RASTER_LAYERS:
            ex.add_raster(snakemake.input[RASTER_LAYERS[name]], codes=[1], crs=crs, nodata=255)
        else:
            ex.add_geometry(str(layer_dir / f"{name}.gpkg"))
        avail, t = shape_availability(admin.geometry, ex)
        return ~avail.astype(bool), t

    extra = ["pds_ineligible_psroads", "pds_ineligible_nocorridor", "landscape_pds",
             "landscape_adesa"]
    masks = {}
    transform = None
    for name in ref_layers + extra:
        masks[name], transform = burn(name)
    region = shape_availability(admin.geometry, ExclusionContainer(crs=crs, res=res))[0].astype(bool)
    r = ((xy[:, 1] - transform.f) / transform.e).astype(int)
    c = ((xy[:, 0] - transform.c) / transform.a).astype(int)
    hit = {k: v[r, c] for k, v in masks.items()}

    def union(names):
        m = np.zeros_like(region)
        for k in names:
            m |= masks[k]
        return m

    by_layer = {}
    for name in ref_layers + ["landscape_pds", "landscape_adesa"]:
        land = float((masks[name] & region).sum() / region.sum())
        share = float(hit[name].mean())
        others = [k for k in ref_layers if k != name and k not in SIZE_DEPENDENT
                  and not (name.startswith("landscape") and k == "landscape")]
        ok_land = region & ~union(others)
        ok_fleet = ~np.any([hit[k] for k in others], axis=0)
        c_land = float((masks[name] & ok_land).sum() / ok_land.sum())
        c_share = float(hit[name][ok_fleet].mean()) if ok_fleet.any() else float("nan")
        by_layer[name] = {
            "n": int(hit[name].sum()),
            "pct": round(100 * share, 1),
            "land_pct": round(100 * land, 1),
            "avoidance_ratio": round(share / land, 2) if land else None,
            "conditional_land_pct": round(100 * c_land, 1),
            "conditional_fleet_pct": round(100 * c_share, 1),
            "conditional_n": int(ok_fleet.sum()),
            "conditional_ratio": round(c_share / c_land, 2) if c_land else None,
        }
        logger.info("%-22s %s", name, by_layer[name])

    out = {"n_turbines": n, "by_layer": by_layer, "by_scenario": {}}
    for s in ladder:
        h = np.any([hit[k] for k in scenarios[s]["layers"]], axis=0)
        out["by_scenario"][s] = {"excluded": int(h.sum()), "surviving": int(n - h.sum()),
                                 "surviving_pct": round(100 * float(1 - h.mean()), 1)}
    out["zoning"] = {
        k: round(100 * float(1 - hit[k].mean()), 1)
        for k in ("pds_ineligible", "pds_ineligible_psroads", "pds_ineligible_nocorridor")
    }
    logger.info("share of the fleet admitted by the zoning: %s", out["zoning"])

    # ------------------------------------------------------------------
    # 2. Farm geometry
    # ------------------------------------------------------------------
    link = float(snakemake.params.farm_link_m)
    tree = cKDTree(xy)
    pairs = tree.query_pairs(link, output_type="ndarray")
    adj = (coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
           if len(pairs) else coo_matrix((n, n)))
    n_farms, labels = connected_components(adj, directed=False)
    sizes = np.bincount(labels)
    centres = np.array([xy[labels == i].mean(axis=0) for i in range(n_farms)])
    span = np.array([np.linalg.norm(xy[labels == i] - centres[i], axis=1).max()
                     if (labels == i).sum() > 1 else 0.0 for i in range(n_farms)])
    edge = np.array([cKDTree(xy[labels != i]).query(xy[labels == i])[0].min()
                     for i in range(n_farms)])
    roads = gpd.read_file(snakemake.input.dual_carriageways, layer="data").to_crs(crs)
    motorways = unary_union(roads[roads["highway"] == "motorway"].geometry.values)
    d_mw = np.array([motorways.distance(p) for p in fleet.geometry])
    exempt_m = float(cfg["placement"]["landscape"]["motorway_exemption_m"])
    mw_farm = np.array([(d_mw[labels == i] <= exempt_m).all() for i in range(n_farms)])
    mdist = tree.query(xy, k=2)[0][:, 1]
    out["farms"] = {
        "link_distance_m": link,
        "n_farms": int(n_farms),
        "turbines_per_farm": round(float(n / n_farms), 1),
        "n_farms_ge_4": int((sizes >= 4).sum()),
        "share_in_farms_ge_4_pct": round(100 * float(sizes[sizes >= 4].sum()) / n, 0),
        "largest_farm": int(sizes.max()),
        "machine_nn_m": pct(mdist),
        "farm_radius_m": pct(span[sizes >= 2]),
        "farm_edge_nn_m": pct(edge),
        "farms_edge_below_4km_pct": round(100 * float((edge < 4000).mean()), 0),
        "farms_edge_below_6km_pct": round(100 * float((edge < 6000).mean()), 0),
        "farms_along_motorway": int(mw_farm.sum()),
        "farms_not_along_motorway_edge_below_4km_pct": round(
            100 * float((edge[~mw_farm] < 4000).mean()), 0),
        "turbines_within_1km_of_motorway_pct": round(100 * float((d_mw <= 1000).mean()), 0),
        "turbines_within_1500m_of_motorway_pct": round(100 * float((d_mw <= 1500).mean()), 0),
    }
    logger.info("standing fleet groups into %s", json.dumps(out["farms"]))

    # ------------------------------------------------------------------
    # 3. Which addresses are within 400 m of a standing machine
    # ------------------------------------------------------------------
    addr = gpd.read_file(snakemake.input.address_points, layer="data").to_crs(crs)
    dd, ii = cKDTree(np.c_[addr.geometry.x, addr.geometry.y]).query(xy)
    near = addr.iloc[ii[dd <= 400]].copy()
    zones = gpd.read_file(snakemake.input.pds_zones, layer="data").to_crs(crs)
    bad = ~zones.geometry.is_valid
    zones.loc[bad, "geometry"] = zones.loc[bad, "geometry"].make_valid()
    j = gpd.sjoin(near, zones[["DESCRIPTION", "geometry"]], predicate="within", how="left")
    j = j[~j.index.duplicated()]
    zae = set(cfg["plan_de_secteur"]["economic_activity_zones"])
    out["addresses"] = {
        "turbines_within_400m_of_an_address": int((dd <= 400).sum()),
        "of_which_nearest_address_in_zae": int(j["DESCRIPTION"].isin(zae).sum()),
        "of_which_in_agricultural_zone": int((j["DESCRIPTION"] == "Agricole").sum()),
        "by_zone": j["DESCRIPTION"].fillna("none").value_counts().to_dict(),
    }
    logger.info("addresses within 400 m: %s", out["addresses"])

    # ------------------------------------------------------------------
    # 4. Open horizon
    # ------------------------------------------------------------------
    lcfg = cfg["placement"]["landscape"]
    settle = gpd.read_file(snakemake.input.settlements, layer="settlements").to_crs(crs)
    sxy = np.c_[settle.geometry.x, settle.geometry.y]
    horizon = Horizon(sxy, float(cfg["turbines"][snakemake.wildcards.turbine]["rotor_diameter"]),
                      float(lcfg["horizon_radius_m"]), float(lcfg["min_free_azimuth_deg"]))
    gaps = []
    for v in range(len(sxy)):
        arcs = [a for x, y in xy[np.hypot(*(xy - sxy[v]).T) <= horizon.radius]
                for a in horizon.arc(v, x, y)]
        gaps.append(np.rad2deg(horizon.largest_gap(arcs)))
    gaps = np.array(gaps)
    affected = gaps < 359.9
    thr = float(lcfg["min_free_azimuth_deg"])
    out["open_horizon"] = {
        "min_free_azimuth_deg": thr,
        "horizon_radius_m": float(lcfg["horizon_radius_m"]),
        "n_settlements": int(len(sxy)),
        "n_with_a_turbine_within_radius": int(affected.sum()),
        "share_affected_pct": round(100 * float(affected.mean()), 0),
        "largest_free_arc_deg": {f"p{q}": round(float(np.percentile(gaps[affected], q)), 0)
                                 for q in (1, 5, 10, 25, 50)},
        "n_failing": int((gaps[affected] < thr).sum()),
        "failing_pct_of_affected": round(100 * float((gaps[affected] < thr).mean()), 1),
    }
    logger.info("open horizon vs the standing fleet: %s", json.dumps(out["open_horizon"]))

    Path(snakemake.output.table).write_text(json.dumps(out, indent=2))
