# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Test the constraint set against the ground-mounted PV parks actually built in
Wallonia (OpenStreetMap), as the wind study tested its layers against the
standing fleet.

For every exclusion layer, terrain rule and land-cover rule:

``share_fleet``   share of the parks' cells inside the layer
``share_region``  share of the Region's cells inside it
``avoidance``     their ratio: < 1 the parks avoid the layer, > 1 they seek it

A park standing inside an exclusion is not an error of the method by itself:
some parks were permitted by derogation, before the circular, or on a
brownfield that the plan de secteur still shows as forest.  The avoidance
ratios say which rules the permitting practice has actually applied.

The script also reports the gisement each park stands on (reference
gisement raster, before exclusions), and the capacity density of the parks
whose capacity is tagged in OSM or known from the press.
"""

import json
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).parent))
from pv_lib import FAMILIES, Stack, scenario_from_config  # noqa: E402

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    cfg = snakemake.params.config
    st = Stack(cfg, snakemake.input.grid, Path(snakemake.input.layers[0]).parent,
               {Path(p).stem: p for p in snakemake.input.rasters}, snakemake.input.region_mask)
    ref = scenario_from_config(cfg)

    parks = gpd.read_file(snakemake.input.parks, layer="data").to_crs(st.grid["crs"])
    parks = parks.reset_index(drop=True)
    parks["pid"] = np.arange(1, len(parks) + 1)
    pid = rasterize(zip(parks.geometry, parks["pid"]), out_shape=st.region.shape,
                    transform=st.transform, dtype="int32")
    fleet = (pid > 0) & st.region
    nf, nr = int(fleet.sum()), int(st.region.sum())
    logger.info("%d parks, %d cells (%.0f ha)", len(parks), nf, nf * st.cell_ha)

    rows = []

    def add(name, kind, family, mask):
        m = mask & st.region
        sf = float((m & fleet).sum()) / max(nf, 1)
        sr = float(m.sum()) / nr
        # parks with at least half of their cells inside
        inside = np.bincount(pid[m & fleet], minlength=len(parks) + 1)[1:]
        tot = np.bincount(pid[fleet], minlength=len(parks) + 1)[1:]
        n_parks = int(((tot > 0) & (inside >= 0.5 * tot)).sum())
        rows.append({"rule": name, "kind": kind, "family": family,
                     "share_fleet": round(sf, 4), "share_region": round(sr, 4),
                     "avoidance": round(sf / sr, 3) if sr > 0 else None,
                     "parks_mostly_inside": n_parks})

    for n, spec in cfg["layers"].items():
        add(n, "layer", spec["family"], st.has([n]))
    for fam in FAMILIES:
        add(f"family:{fam}", "family", fam, st.family_mask(fam, ref))
    s = st.r["slope_pct"]
    for t in (5, 7, 10, 15, 20):
        add(f"slope>={t}%", "terrain", "terrain", (s >= t) & (s != 255))
    add("water", "cover", "water", st.water(ref))
    for n in cfg["masks"]:
        add(f"mask:{n}", "mask", "gisement", st.has([n]))
    for k in range(1, 6):
        add(f"sigec_class={k}", "mask", "gisement", st.r["sigec_class"] == k)
    for q in range(1, 6):
        add(f"soil_quality={q}", "soil", "soil", st.r["soil_quality"] == q)
    table = pd.DataFrame(rows)
    table.to_csv(snakemake.output.table, index=False)

    # Gisement of each park (majority of its cells), before any exclusion.
    gis = st.gisement_raster(ref)
    keys = [g["key"] for g in ref["gisements"]]
    comp = []
    for _, p in parks.iterrows():
        cells = gis[pid == p["pid"]]
        if len(cells) == 0:
            comp.append(None)
            continue
        v, c = np.unique(cells, return_counts=True)
        comp.append(keys[int(v[np.argmax(c)]) - 1] if v[np.argmax(c)] > 0 else "outside")
    parks["gisement"] = comp
    land = st.evaluate(ref, keep_rasters=True)["rasters"]["land_ok"]
    elig = np.bincount(pid[fleet & land], minlength=len(parks) + 1)[1:]
    tot = np.bincount(pid[fleet], minlength=len(parks) + 1)[1:]
    parks["share_eligible"] = np.where(tot > 0, elig / np.maximum(tot, 1), np.nan).round(3)
    # WALOUS 2023 is drawn from 2023 imagery, on which the parks built before
    # are panels: it classes them as sealed or built.  The same test without
    # the land-cover part of the "built" family says whether the *rules* admit
    # the parks' land.
    nobuilt = dict(ref, walous_thresholds_pct=dict(ref["walous_thresholds_pct"], built=101, sealed=101))
    land2 = st.evaluate(nobuilt, keep_rasters=True)["rasters"]["land_ok"]
    elig2 = np.bincount(pid[fleet & land2], minlength=len(parks) + 1)[1:]
    parks["share_eligible_rules"] = np.where(tot > 0, elig2 / np.maximum(tot, 1), np.nan).round(3)
    parks["mwc_per_ha"] = (parks["mw_tag"] / parks["area_ha"]).round(3)
    keep = ["name", "kind", "area_ha", "mw_tag", "mwc_per_ha", "gisement", "share_eligible",
            "share_eligible_rules"]
    parks[keep].sort_values("area_ha", ascending=False).to_csv(snakemake.output.parks, index=False)

    tagged = parks[parks["mw_tag"].notna() & (parks["area_ha"] >= 1)]
    summary = {
        "parks": int(len(parks)),
        "area_ha": round(float(parks["area_ha"].sum()), 1),
        "cells": nf,
        "gisement_of_parks_ha": parks.groupby("gisement")["area_ha"].sum().round(1).to_dict(),
        "gisement_of_parks_n": parks["gisement"].value_counts().to_dict(),
        "share_of_fleet_area_eligible": round(float((fleet & land).sum()) / max(nf, 1), 3),
        "share_of_fleet_area_eligible_without_landcover_built": round(
            float((fleet & land2).sum()) / max(nf, 1), 3),
        "tagged_parks_ge_1ha": int(len(tagged)),
        "density_mwc_ha_median": round(float(tagged["mwc_per_ha"].median()), 3) if len(tagged) else None,
        "density_mwc_ha_area_weighted": (round(float(tagged["mw_tag"].sum() / tagged["area_ha"].sum()), 3)
                                         if len(tagged) else None),
        "families": {r["family"]: r for r in rows if r["kind"] == "family"},
    }
    Path(snakemake.output.summary).write_text(json.dumps(summary, indent=2, default=str))
    logger.info("%s", json.dumps(summary, indent=1, default=str))
