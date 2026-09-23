# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Price every choice the answer depends on, one at a time.

Each case of ``config.sensitivity.cases`` is the reference -- scenario
``reference_scenario``, reference turbine, reference placement model -- with
exactly one change: an exclusion layer swapped for a variant or dropped, or a
placement rule changed.  The difference to the reference is therefore the price
of that one choice, which is what a reader who disagrees with it needs.

Each exclusion layer is burnt once, on its own, by ``atlite``; a case's
eligible land is the complement of the union of its layers.  Because atlite
itself combines layers by union, this reproduces its combined burn exactly, and
the script checks that it reproduces the reference raster cell for cell before
it prices anything.
"""

import json
import logging
import sys
from pathlib import Path

# rasterio before geopandas: see retrieve_slope_raster.py.
import rasterio
import geopandas as gpd
import numpy as np
import pandas as pd
from atlite.gis import ExclusionContainer, shape_availability
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))
from placement_lib import (  # noqa: E402
    Horizon,
    allocate_free,
    check_layout,
    grow_parks,
    motorway_distance,
    seed_scores,
)

logger = logging.getLogger(__name__)

RASTERS = {"dwelling_setback": "dwelling_raster", "slope": "slope_raster",
           "slope_ge10": "slope_ge10", "slope_ge15": "slope_ge15"}


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
    turbine = cfg["turbines"][cfg["reference_turbine"]]
    D, p_nom = float(turbine["rotor_diameter"]), float(turbine["p_nom"])
    pcfg, lcfg = cfg["placement"], cfg["placement"]["landscape"]
    spacing = float(pcfg["spacings_rotor_diameters"][pcfg["reference_case"]]) * D
    ref_layers = list(cfg["scenarios"][cfg["reference_scenario"]]["layers"])
    cases = cfg["sensitivity"]["cases"]

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]

    # ------------------------------------------------------------------
    # One burn per layer
    # ------------------------------------------------------------------
    needed = set(ref_layers)
    for c in cases.values():
        needed |= {v for v in (c.get("land") or {}).values() if v}
    masks, transform = {}, None
    for name in sorted(needed):
        ex = ExclusionContainer(crs=crs, res=res)
        if name in RASTERS:
            ex.add_raster(snakemake.input[RASTERS[name]], codes=[1], crs=crs, nodata=255)
        else:
            ex.add_geometry(str(Path(snakemake.input.layer_dir) / f"{name}.gpkg"))
        avail, transform = shape_availability(admin.geometry, ex)
        masks[name] = ~avail.astype(bool)
        logger.info("burnt %-28s", name)
    region = shape_availability(admin.geometry, ExclusionContainer(crs=crs, res=res))[0].astype(bool)

    def eligible(layers):
        ex = np.zeros_like(region)
        for n in layers:
            ex |= masks[n]
        return region & ~ex

    with rasterio.open(snakemake.input.raster) as src:
        ref_raster = src.read(1).astype(bool)
    ref_mask = eligible(ref_layers)
    differ = int(np.sum(ref_mask != ref_raster))
    logger.info("reference rebuilt from single-layer burns: %d cells differ", differ)
    if differ:
        raise RuntimeError(f"single-layer burns do not reproduce the reference raster ({differ} cells)")

    villages_gdf = gpd.read_file(snakemake.input.settlements, layer="settlements")
    villages = np.c_[villages_gdf.geometry.x, villages_gdf.geometry.y]
    roads = gpd.read_file(snakemake.input.dual_carriageways, layer="data").to_crs(crs)
    dmw = motorway_distance(region.shape, transform,
                            roads[roads["highway"] == "motorway"].geometry, res)

    base_rules = {
        "interdistance_m": 0.0,
        "horizon": True,
        "min_turbines": int(pcfg["park"]["min_turbines"]),
    }

    def run(layers, rules):
        mask = eligible(layers)
        rows, cols = np.nonzero(mask)
        xs = transform.c + (cols + 0.5) * transform.a
        ys = transform.f + (rows + 0.5) * transform.e
        amw = dmw[rows, cols] <= float(lcfg["motorway_exemption_m"])
        free = int(allocate_free(xs, ys, spacing).sum())
        hz = (Horizon(villages, D, lcfg["horizon_radius_m"], lcfg["min_free_azimuth_deg"])
              if rules["horizon"] else None)
        score = seed_scores(mask, rows, cols, res, float(pcfg["park"]["seed_radius_m"]))
        idx, pid, _ = grow_parks(xs, ys, score, spacing, link=float(pcfg["park"]["link_m"]),
                                 n_min=rules["min_turbines"], horizon=hz,
                                 interdistance=float(rules["interdistance_m"]),
                                 along_motorway=amw, tree=cKDTree(np.c_[xs, ys]))
        chk = check_layout(xs[idx], ys[idx], pid, spacing, n_min=rules["min_turbines"],
                           villages=villages if rules["horizon"] else None,
                           rotor_diameter=D, radius=lcfg["horizon_radius_m"],
                           min_free_deg=lcfg["min_free_azimuth_deg"],
                           interdistance=float(rules["interdistance_m"]), along_motorway=amw[idx])
        if not chk["ok"]:
            raise RuntimeError(f"layout breaks its own rules: {chk}")
        return {
            "eligible_area_km2": round(float(mask.sum()) * res * res / 1e6, 1),
            "free_mw": round(free * p_nom),
            "n_turbines": int(len(idx)),
            "n_parks": int(pid.max() + 1) if len(pid) else 0,
            "p_nom_max_mw": round(len(idx) * p_nom),
        }

    def apply(case_names):
        layers, rules = list(ref_layers), dict(base_rules)
        for cn in case_names:
            c = cases[cn]
            for old, new in (c.get("land") or {}).items():
                layers = [new if l == old else l for l in layers if not (l == old and new is None)]
            rules.update(c.get("placement") or {})
        return layers, rules

    ref = run(ref_layers, base_rules)
    logger.info("reference: %s", ref)
    placed = pd.read_csv(snakemake.input.placement)
    pref = placed[(placed["model"] == pcfg["reference_model"])
                  & (placed["spacing_case"] == pcfg["reference_case"])]["p_nom_max_mw"].iloc[0]
    if round(float(pref)) != ref["p_nom_max_mw"]:
        raise RuntimeError(f"reference not reproduced: {ref['p_nom_max_mw']} vs {pref}")

    rows_out = [{"case": "reference", "group": "reference",
                 "label": "reference (2024 framework as applied)", **ref,
                 "delta_mw": 0, "delta_pct": 0.0}]
    for name, c in cases.items():
        r = run(*apply([name]))
        rows_out.append({"case": name, "group": c["group"], "label": c["label"], **r,
                         "delta_mw": r["p_nom_max_mw"] - ref["p_nom_max_mw"],
                         "delta_pct": round(100 * (r["p_nom_max_mw"] / ref["p_nom_max_mw"] - 1), 1)})
        logger.info("%-22s %s", name, rows_out[-1])
    for name, c in cfg["sensitivity"].get("combined", {}).items():
        r = run(*apply(c["cases"]))
        rows_out.append({"case": name, "group": "combined", "label": c["label"], **r,
                         "delta_mw": r["p_nom_max_mw"] - ref["p_nom_max_mw"],
                         "delta_pct": round(100 * (r["p_nom_max_mw"] / ref["p_nom_max_mw"] - 1), 1)})
        logger.info("%-22s %s", name, rows_out[-1])

    pd.DataFrame(rows_out).to_csv(snakemake.output.table, index=False)
    Path(snakemake.output.json).write_text(json.dumps({r["case"]: r for r in rows_out}, indent=2))
    logger.info("wrote %s", snakemake.output.table)
