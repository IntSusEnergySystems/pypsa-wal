# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
The reference potential and every sensitivity case, from one load of the
layer stack (scripts/pv_lib.py).

Outputs
    results/tables/potential_reference.csv   one row per gisement
    results/tables/funnel.csv                land left after each family
    results/tables/sensitivity_cases.csv     one row per case, with the delta
    results/tables/headline.json             the numbers the report quotes
    resources/reference/*.tif                gisement, first excluding family,
                                             eligible land (technical, policy)
"""

import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, str(Path(__file__).parent))
from pv_lib import FAMILIES, Stack, apply_case, scenario_from_config  # noqa: E402

logger = logging.getLogger(__name__)


def write_tif(path, arr, st, dtype="uint8", nodata=None):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=1, dtype=dtype, crs=st.crs, transform=st.transform,
                       compress="deflate", tiled=True, nodata=nodata) as dst:
        dst.write(arr.astype(dtype), 1)


def flat(res):
    t = res["total"]
    g = res["gisements"]
    row = {k: t[k] for k in ("technical_mwc", "policy_mwc", "eligible_ha",
                             "after_park_rule_ha", "open_ha")}
    for k, v in g.items():
        row[f"{k}_mwc"] = v["policy_mwc"]
    return row


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    cfg = snakemake.params.config
    t0 = time.time()
    st = Stack(cfg, snakemake.input.grid, Path(snakemake.input.layers[0]).parent,
               {Path(p).stem: p for p in snakemake.input.rasters},
               snakemake.input.region_mask)
    logger.info("stack loaded in %.0f s", time.time() - t0)

    evidence = json.loads(Path(snakemake.input.evidence).read_text())
    ref = scenario_from_config(cfg, evidence)
    t0 = time.time()
    r = st.evaluate(ref, keep_rasters=True)
    logger.info("reference evaluated in %.0f s: %s", time.time() - t0, r["total"])

    out = Path(snakemake.output.rasters_dir)
    out.mkdir(parents=True, exist_ok=True)
    rr = r.pop("rasters")
    write_tif(out / "gisement.tif", rr["gisement"], st)
    write_tif(out / "family_first.tif", rr["family_first"], st)
    write_tif(out / "tech_land.tif", rr["tech_land"], st)
    write_tif(out / "policy_land.tif", rr["policy_land"], st)
    write_tif(out / "float_ok.tif", rr["float_ok"], st)
    write_tif(out / "land_ok.tif", rr["land_ok"], st)
    del rr

    rows = [{"gisement": k, **v} for k, v in r["gisements"].items()]
    pd.DataFrame(rows).to_csv(snakemake.output.reference, index=False)
    pd.DataFrame([{"step": "region", "left_ha": r["region_ha"]}] +
                 [{"step": f["family"], "left_ha": round(f["left_ha"], 1)} for f in r["funnel"]]
                 ).to_csv(snakemake.output.funnel, index=False)

    cases = cfg["sensitivity"]["cases"]
    out_rows = [{"case": "reference", "group": "reference",
                 "label": "reference (circular of 14 March 2024 as it stands)", **flat(r),
                 "delta_mwc": 0.0, "delta_pct": 0.0}]
    detail = {"reference": r}
    for name, c in cases.items():
        t0 = time.time()
        rc = st.evaluate(apply_case(ref, c, evidence, name))
        detail[name] = rc
        row = {"case": name, "group": c["group"], "label": c["label"], **flat(rc)}
        row["delta_mwc"] = round(row["policy_mwc"] - out_rows[0]["policy_mwc"], 0)
        row["delta_pct"] = round(100 * (row["policy_mwc"] / out_rows[0]["policy_mwc"] - 1), 1)
        out_rows.append(row)
        logger.info("%-22s %8.0f MWc policy, %9.0f MWc technical (%.0f s)", name,
                    row["policy_mwc"], row["technical_mwc"], time.time() - t0)
    pd.DataFrame(out_rows).to_csv(snakemake.output.sensitivity, index=False)
    Path(snakemake.output.detail).write_text(json.dumps(detail, indent=1))

    headline = {
        "reference": r["total"],
        "region_ha": r["region_ha"],
        "gisements": r["gisements"],
        "funnel": r["funnel"],
        "families": FAMILIES,
    }
    Path(snakemake.output.headline).write_text(json.dumps(headline, indent=2))
