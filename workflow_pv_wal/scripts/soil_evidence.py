# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Which share of the mapped-poor, unfarmed land of the agricultural zone could
realistically be *demonstrated* to have a poor agronomic quality in a permit.

The circular admits a derogation in the agricultural zone on « des terres où il
est démontré que la qualité agronomique du sol est médiocre » (14 March 2024,
p. 19).  The only regional map, « Sols de bonne qualité agronomique »
(AWAC / GxABT, Pirlot & Degré 2024), classes soils by *percentiles* of their
plant-available water (corrected for stones) and of their depth: its classes
1-2 are the bottom of a Walloon ranking, not a demonstration.  So the share is
built from three independent lines of evidence, cell by cell:

1. **Not farmland in the administration's own register.**  A cell inside the
   LPIS 2024 agricultural surfaces is aid-eligible farmland, whether or not it
   was declared this year: « une parcelle agricole en cours d'exploitation »,
   which the circular keeps for food.  Weight 0.
2. **Not a garden or a farmyard.**  A cell within ``curtilage_m`` of a building
   (a WALOUS 2023 cell at least ``curtilage_built_pct`` % built) is the curtilage
   of a house or a farm.  Weight 0.
3. **Revealed agronomic value.**  For every soil unit (CNSW principal soil type
   x AWAC class), the share of the land a farmer could farm in the agricultural
   zone (not built, not sealed, not wooded, not water) that farmers *do* farm
   (SIGEC 2024).  A soil that is farmed wherever it is available is not
   « impropre à la fonction agricole », whatever its water reserve: the cell's
   weight is one minus that share.

The share opened in the reference is the weighted area over the whole area of
the gisement (after exclusions and the park rule).  The workflow prices 0 and
100 % around it, and the curtilage distance.
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
from pv_lib import Stack, scenario_from_config  # noqa: E402

logger = logging.getLogger(__name__)


def read(path):
    with rasterio.open(path) as src:
        return src.read(1)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    cfg = snakemake.params.config
    ev = cfg["soil_evidence"]
    st = Stack(cfg, snakemake.input.grid, Path(snakemake.input.layers[0]).parent,
               {Path(p).stem: p for p in snakemake.input.rasters}, snakemake.input.region_mask)
    ref = scenario_from_config(cfg, evidence={"share": 0.0})
    keys = [g["key"] for g in ref["gisements"]]
    r = st.evaluate(ref, keep_rasters=True)["rasters"]
    gis, tech = r["gisement"], r["tech_land"]
    target = (gis == keys.index("agri_zone_poor") + 1) & tech
    ha = st.cell_ha
    total = float(target.sum()) * ha
    logger.info("mapped-poor, unfarmed agricultural-zone land after exclusions and the park rule: %.0f ha", total)

    soil = st.r["soil_quality"]
    code = read(snakemake.input.cnsw)
    farmed = st.r["sigec_class"] > 0
    lpis = st.has(["lpis_agri"])
    th = cfg["walous"]["thresholds_pct"]
    agri_zone = st.has(["pds_agri"])
    farmable = (agri_zone & (st.r["walous_built"] < th["built"]) & (st.r["walous_sealed"] < th["sealed"])
                & (st.r["walous_trees"] < th["trees"]) & (st.r["walous_water"] < th["water"]))

    # 3. revealed agronomic value per soil unit
    unit = code.astype(np.int64) * 10 + soil.astype(np.int64)
    df = pd.DataFrame({"unit": unit[farmable], "farmed": farmed[farmable]})
    by_unit = df.groupby("unit")["farmed"].agg(["size", "mean"]).rename(
        columns={"size": "cells", "mean": "farmed_share"})
    by_class = df.assign(awac=df["unit"] % 10).groupby("awac")["farmed"].mean()

    built = st.r["walous_built"]
    b = (built >= ev["curtilage_built_pct"]) & (built != 255)
    dist = ndimage.distance_transform_edt(~b, sampling=st.res)

    def share(curtilage_m):
        cand = target & ~lpis & (dist > curtilage_m)
        w = 1.0 - by_unit["farmed_share"].reindex(unit[cand]).fillna(0.0).to_numpy()
        return float(cand.sum()) * ha, float(w.sum()) * ha

    steps = {
        "mapped_poor_ha": total,
        "not_lpis_ha": float((target & ~lpis).sum()) * ha,
    }
    cand_ha, usable_ha = share(ev["curtilage_m"])
    steps["not_curtilage_ha"] = cand_ha
    steps["revealed_weighted_ha"] = usable_ha
    variants = {}
    for name, c in cfg["sensitivity"]["cases"].items():
        if "soil_evidence" in c:
            m = c["soil_evidence"].get("curtilage_m", ev["curtilage_m"])
            variants[name] = round(share(m)[1] / total, 4) if total else 0.0
    # Cross-check: excess of unfarmed land on poor soils over the others.
    unf_poor = 1.0 - float(by_class.reindex(ev["poor_classes"]).mean())
    unf_rest = 1.0 - float(by_class.reindex([3, 4, 5]).mean())
    out = {
        "share": round(usable_ha / total, 4) if total else 0.0,
        "steps_ha": {k: round(v, 1) for k, v in steps.items()},
        "variants": variants,
        "farmed_share_by_awac_class": {int(k): round(float(v), 4) for k, v in by_class.items()},
        "unfarmed_share_poor": round(unf_poor, 4),
        "unfarmed_share_other": round(unf_rest, 4),
        "excess_unfarmed_on_poor": round(unf_poor - unf_rest, 4),
        "poor_soils_region_ha": round(float(((soil >= 1) & (soil <= 2)).sum()) * ha, 0),
        "poor_soils_farmed_ha": round(float(((soil >= 1) & (soil <= 2) & farmed).sum()) * ha, 0),
        "poor_soils_by_cnsw_ha": {int(k): round(float(v) * ha, 0) for k, v in pd.Series(
            code[(soil >= 1) & (soil <= 2)]).value_counts().head(8).items()},
        "curtilage_m": ev["curtilage_m"],
    }
    Path(snakemake.output.json).write_text(json.dumps(out, indent=2))
    table = by_unit.reset_index()
    table["cnsw"] = table["unit"] // 10
    table["awac"] = table["unit"] % 10
    table["ha"] = table["cells"] * ha
    table[["cnsw", "awac", "ha", "farmed_share"]].round(4).to_csv(snakemake.output.table, index=False)
    logger.info("%s", json.dumps(out, indent=1))
