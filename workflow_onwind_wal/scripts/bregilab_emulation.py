# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Reproduce BREGILAB's Walloon onshore-wind potential from its own rules, on
this study's data, and bridge from it to this study's answer one change at a
time.

BREGILAB (Clymans et al. 2022, WP3, §5.2.2) delineates "available space" from
the negative and positive boundary conditions of its Tables 20-21 (WTN
scenario), then fills it with Vestas V112 (3.3 MW, hub 94 m) at a minimum
spacing of 5 D = 560 m; its own Figure 21 shows machines allocated on isolated
100 m pixels, i.e. a free allocation.  The emulation applies those rules --
2013 habitat setback of 4 x the 150 m tip height, 400 m from dwellings, the
negative advice limits around roads, railways, waterways and HV lines, 2 km
around nuclear sites, 560 m around the standing fleet, Natura 2000 and reserves,
forest and green zoning, heritage, high-risk karst, and the 1.5 km corridor
along the "road, rail and waterway network" -- with the AOEM no-go rings
standing in for the aviation red zones.  What cannot be emulated from open data
(skeyes and Defence red zones, SEVESO, gas pipelines, cadastral residential
parcels) is listed in the output.

The bridge then adds this study's rules in turn, all on BREGILAB's machine, and
finally switches to the reference machine and to the park and landscape rules.
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
from rasterio.features import geometry_mask
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).parent))
from placement_lib import allocate_free  # noqa: E402

logger = logging.getLogger(__name__)


def evaluate(expr, H, D):
    if isinstance(expr, (int, float)):
        return float(expr)
    return float(eval(expr, {"__builtins__": {}}, {"H": H, "D": D}))  # noqa: S307


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
    b = cfg["bregilab"]
    em = b["emulation"]
    D, P = float(b["rotor_diameter_m"]), float(b["p_nom_mw"])
    H = float(b["hub_height_m"]) + D / 2
    spacing = float(b["min_spacing_m"])
    layer_dir = Path(snakemake.input.layer_dir)

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]
    with rasterio.open(snakemake.input.raster) as src:
        transform, shape = src.transform, src.shape
    region = ~geometry_mask(admin.geometry, shape, transform)

    def burn(geoms):
        geoms = [g for g in geoms if g is not None and not g.is_empty]
        return region & ~geometry_mask(geoms, shape, transform) if geoms else np.zeros(shape, bool)

    def layer(name):
        ex = ExclusionContainer(crs=crs, res=res)
        if name.endswith(".tif"):
            ex.add_raster(name, codes=[1], crs=crs, nodata=255)
        else:
            ex.add_geometry(str(layer_dir / f"{name}.gpkg"))
        avail, t = shape_availability(admin.geometry, ex)
        assert avail.shape == shape and t == transform
        return region & ~avail.astype(bool)

    def read(key):
        g = gpd.read_file(snakemake.input[key], layer="data").to_crs(crs)
        bad = ~g.geometry.is_valid
        if bad.any():
            g.loc[bad, "geometry"] = g.loc[bad, "geometry"].make_valid()
        return g

    zones = read("pds_zones")
    habitat = unary_union(
        zones[zones["DESCRIPTION"].isin(cfg["plan_de_secteur"]["habitat_zones"])].geometry.values
    )
    roads, rail, ww, hv = read("pds_roads"), read("pds_rail"), read("pds_waterways"), read("pds_hv_lines")
    hsl = read("osm_high_speed_rail")
    karst = read("karst")
    fleet = gpd.read_file(snakemake.input.fleet, layer="data").to_crs(crs)
    nuc = gpd.GeoSeries(
        gpd.points_from_xy([s["lon"] for s in em["nuclear_sites"]],
                           [s["lat"] for s in em["nuclear_sites"]]), crs=4326
    ).to_crs(crs)

    L = {
        "zoning, corridor along every road": layer("pds_ineligible_psroads"),
        "zoning, CoDT corridor": layer("pds_ineligible"),
        "habitat 4H": burn([habitat.buffer(evaluate(em["habitat_zone"], H, D))]),
        "habitat 2024": burn([habitat.buffer(evaluate(cfg["setbacks"]["habitat_zone"]["cdr2024"], H, D))]),
        "dwellings": layer(snakemake.input.dwelling_raster),
        "roads": burn(list(roads.buffer(evaluate(em["road"], H, D)).values)),
        "rail": burn(list(rail.buffer(evaluate(em["railway"], H, D)).values)
                     + list(hsl.buffer(evaluate(em["railway_high_speed"], H, D)).values)),
        "waterways": burn(list(ww.buffer(evaluate(em["waterway"], H, D)).values)),
        "hv": burn(list(hv.buffer(evaluate(em["hv_line"], H, D)).values)),
        "nature": layer("nature"),
        "heritage": layer("heritage"),
        "karst": burn(list(karst[karst["NATURE"].isin(cfg["risk"]["karst_levels"])].geometry.values)),
        "aviation": layer("aviation"),
        "nuclear": burn([p.buffer(float(em["nuclear_radius_m"])) for p in nuc]),
        "fleet": burn(list(fleet.buffer(evaluate(em["existing_turbines"], H, D)).values)),
        "landscape": layer("landscape"),
        "risk": layer("risk"),
        "slope": layer(snakemake.input.slope_raster),
        "radar": layer("radar"),
    }
    logger.info("burnt: %s", {k: round(float(v.sum()) * res * res / 1e6) for k, v in L.items()})

    def eligible(names):
        ex = np.zeros(shape, bool)
        for n in names:
            ex |= L[n]
        return region & ~ex

    def free_mw(mask, preplaced=None):
        rows, cols = np.nonzero(mask)
        xs = transform.c + (cols + 0.5) * transform.a
        ys = transform.f + (rows + 0.5) * transform.e
        return P * float(allocate_free(xs, ys, spacing, preplaced=preplaced).sum())

    wtn = ["zoning, corridor along every road", "habitat 4H", "dwellings", "roads", "rail",
           "waterways", "hv", "nature", "heritage", "karst", "aviation", "nuclear"]
    fleet_xy = list(zip(fleet.geometry.x, fleet.geometry.y))
    installed = float(cfg["benchmarks"]["installed_2024_mw"])
    E = eligible(wtn)
    em_out = {
        "eligible_km2": round(float(E.sum()) * res * res / 1e6, 1),
        "gross_free_mw": round(free_mw(E)),
        "with_fleet_mw": round(installed + free_mw(eligible(wtn + ["fleet"]), preplaced=fleet_xy)),
        "not_emulated": ["skeyes and Defence red zones (the AOEM no-go rings stand in)",
                         "SEVESO sites (250 m)", "gas pipelines (25 m)",
                         "cadastral residential parcels (the ICAR address points stand in)",
                         "undeveloped parcels in economic-activity zones"],
        "reported_mw": float(b["wallonia_total_gw"]) * 1000.0,
    }
    em_out["reported_share_of_emulation"] = round(em_out["reported_mw"] / em_out["with_fleet_mw"], 3)
    logger.info("emulation: %s", em_out)

    steps = [
        ("BREGILAB's rules (WTN), this study's data", list(wtn)),
        ("+ landscape perimeters (plan de secteur and ADESA)", ["landscape"]),
        ("+ flood, landslide and water-capture zones", ["risk"]),
        ("+ slope >= 7 %", ["slope"]),
        ("+ radar and radio-astronomy perimeters", ["radar"]),
        ("+ corridor restricted to the CoDT's PIC network", "codt"),
        ("+ 2024 habitat setback (500 m + H/2) instead of 4H", "hab2024"),
    ]
    names, bridge = [], []
    for label, change in steps:
        if change == "codt":
            names = ["zoning, CoDT corridor" if n.startswith("zoning") else n for n in names]
        elif change == "hab2024":
            names = ["habitat 2024" if n == "habitat 4H" else n for n in names]
        else:
            names += change
        m = eligible(names)
        bridge.append({"step": label,
                       "eligible_km2": round(float(m.sum()) * res * res / 1e6, 1),
                       "p_nom_max_mw": round(free_mw(m))})
        logger.info("%-58s %s", label, bridge[-1])

    pd.DataFrame(bridge).to_csv(snakemake.output.table, index=False)
    Path(snakemake.output.json).write_text(
        json.dumps({"emulation": em_out, "bridge": bridge,
                    "turbine": {"rotor_diameter_m": D, "tip_height_m": H, "p_nom_mw": P,
                                "spacing_m": spacing}}, indent=2)
    )
