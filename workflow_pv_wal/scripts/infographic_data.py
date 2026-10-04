# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Everything the dashboard draws, from the same evaluation core as the report
(scripts/pv_lib.py), so the two cannot disagree.

Outputs, in ``results/infographic/data/``:

``map.png``        the Region at 100 m (the 20 m grid in 5 x 5 blocks).  Red
                   channel: the class of the pixel -- 1..5 the display family
                   of rules that removes it, 6 too small or too narrow for a
                   park, 10 + g the gisement g of the land that survives, 0
                   outside.  Green channel: the share of the pixel that
                   survives (0-250), so the page can draw a 2 ha brownfield
                   visibly.  Values are multiples of 8 in the red channel so a
                   browser that nudges a level still decodes the right class.
``loupe.png``      the same encoding at the full 20 m, on a 12 x 12 km window
``states.json``    the funnel (land left after each display family), the
                   technical area of each gisement, and, for every combination
                   of opened land the "Et si… ?" choices can produce, the
                   openable area of each gisement once the park rule is
                   re-applied to the opened land only.  The page turns areas
                   into MWc itself (shares, quota, densities: the arithmetic of
                   ``pv_lib.policy_total``); the build checks that its result
                   matches the report's reference and sensitivity cases.
``landmarks.json`` Region outline, motorways, towns, OSM parks, loupe window,
                   in display-grid coordinates.
"""

import itertools
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from plot_maps import DISPLAY_FAMILIES, GROUPS  # noqa: E402
from pv_lib import FAMILIES, Stack, apply_case, open_shares, policy_total, scenario_from_config  # noqa: E402

logger = logging.getLogger(__name__)

F = 5          # 20 m cells per 100 m display pixel
SCALE = 8
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]


def display_family(fam_first):
    """Pipeline family code (1..len+1 incl. water) -> display family (1..5)."""
    to = np.zeros(len(FAMILIES) + 3, dtype=np.uint8)
    for di, (_, _, members) in enumerate(DISPLAY_FAMILIES):
        for m in members:
            to[(FAMILIES.index(m) + 1) if m != "water" else len(FAMILIES) + 1] = di + 1
    return to[np.minimum(fam_first, len(FAMILIES) + 1)]


def classes(region, fam_first, gis, survive):
    c = display_family(fam_first).astype(np.uint8)
    c[region & ~survive & (c == 0)] = 6
    c[survive] = 10 + gis[survive]
    c[~region] = 0
    return c


def blocks(cls, survive, f):
    """Most frequent class per block, surviving land winning from a fifth."""
    h, w = (cls.shape[0] // f) * f, (cls.shape[1] // f) * f
    b = cls[:h, :w].reshape(h // f, f, w // f, f).transpose(0, 2, 1, 3).reshape(h // f, w // f, f * f)
    s = survive[:h, :w].reshape(h // f, f, w // f, f).sum(axis=(1, 3))
    vals = np.unique(b)
    counts = np.stack([(b == v).sum(axis=2) for v in vals])
    out = vals[counts.argmax(axis=0)].astype(np.uint8)
    land = vals >= 10
    if land.any():
        lc = counts[land]
        best = vals[land][lc.argmax(axis=0)]
        win = s >= 0.2 * f * f
        out[win] = best[win]
    share = np.rint(250.0 * s / (f * f)).astype(np.uint8)
    return out, share


def png(path, cls, share):
    rgb = np.zeros(cls.shape + (3,), dtype=np.uint8)
    rgb[..., 0] = cls * SCALE
    rgb[..., 1] = share
    Image.fromarray(rgb, "RGB").save(path, optimize=True)


def svg_path(geom, to_px, nd=1):
    parts = []
    geoms = getattr(geom, "geoms", [geom])
    for g in geoms:
        if g.geom_type in ("Polygon",):
            rings = [g.exterior] + list(g.interiors)
            for r in rings:
                pts = [to_px(x, y) for x, y in r.coords]
                parts.append("M" + "L".join(f"{x:.{nd}f} {y:.{nd}f}" for x, y in pts) + "Z")
        elif g.geom_type in ("LineString",):
            pts = [to_px(x, y) for x, y in g.coords]
            parts.append("M" + "L".join(f"{x:.{nd}f} {y:.{nd}f}" for x, y in pts))
        elif hasattr(g, "geoms"):
            parts.append(svg_path(g, to_px, nd))
    return "".join(parts)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    cfg = snakemake.params.config
    icfg = cfg["infographic"]
    out = Path(snakemake.output.states).parent
    out.mkdir(parents=True, exist_ok=True)
    st = Stack(cfg, snakemake.input.grid, Path(snakemake.input.layers[0]).parent,
               {Path(p).stem: p for p in snakemake.input.rasters}, snakemake.input.region_mask)
    evidence = json.loads(Path(snakemake.input.evidence).read_text())
    ref = scenario_from_config(cfg, evidence)
    keys = [g["key"] for g in ref["gisements"]]
    systems = {g["key"]: g["system"] for g in ref["gisements"]}

    r = st.evaluate(ref, keep_rasters=True)
    rr = r.pop("rasters")
    region = st.region
    survive = (rr["tech_land"] | rr["float_ok"]).astype(bool)
    cls = classes(region, rr["family_first"], rr["gisement"], survive)

    # ---- funnel, by display family ----------------------------------------------
    disp = display_family(rr["family_first"])
    disp[~region] = 0
    funnel = [{"step": 0, "left_ha": round(r["region_ha"], 0)}]
    removed = 0.0
    for di in range(1, len(DISPLAY_FAMILIES) + 1):
        removed += float((disp == di).sum()) * st.cell_ha
        funnel.append({"step": di, "left_ha": round(r["region_ha"] - removed, 0)})
    funnel.append({"step": len(DISPLAY_FAMILIES) + 1,
                   "left_ha": round(float(survive.sum()) * st.cell_ha, 0)})

    # ---- the map -----------------------------------------------------------------
    img, share = blocks(cls, survive, F)
    png(out / "map.png", img, share)
    rows_disp, cols_disp = img.shape
    tr = st.transform

    def to_px(x, y):
        return ((x - tr.c) / (tr.a * F), (y - tr.f) / (tr.e * F))

    # ---- the loupe -----------------------------------------------------------------
    size = int(icfg["loupe"]["size_km"] * 1000 / st.res)
    if icfg["loupe"].get("centre"):
        cx, cy = icfg["loupe"]["centre"]
        c0 = int((cx - tr.c) / tr.a) - size // 2
        r0 = int((cy - tr.f) / tr.e) - size // 2
    else:
        # the window with the most gisement groups present, then the most land
        best = None
        step = size // 2
        g_of = np.zeros(len(keys) + 1, dtype=np.int16)
        for gi, (_, _, members) in enumerate(GROUPS):
            for m in members:
                g_of[keys.index(m) + 1] = gi + 1
        grp = np.where(survive, g_of[rr["gisement"]], 0)
        for r0_ in range(0, region.shape[0] - size, step):
            for c0_ in range(0, region.shape[1] - size, step):
                win = grp[r0_:r0_ + size, c0_:c0_ + size]
                if region[r0_:r0_ + size, c0_:c0_ + size].mean() < 0.98:
                    continue
                cnt = np.bincount(win.ravel(), minlength=len(GROUPS) + 1)[1:]
                score = (int((cnt > 0.002 * size * size).sum()), int(cnt[:2].sum()))
                if best is None or score > best[0]:
                    best = (score, r0_, c0_)
        _, r0, c0 = best
    lw = cls[r0:r0 + size, c0:c0 + size]
    png(out / "loupe.png", lw, (survive[r0:r0 + size, c0:c0 + size] * 250).astype(np.uint8))
    loupe = {"row0": r0 / F, "col0": c0 / F, "size": size / F, "cells": size,
             "centre_3035": [tr.c + (c0 + size / 2) * tr.a, tr.f + (r0 + size / 2) * tr.e]}

    # ---- the combinations of opened land -----------------------------------------------
    # Opening depends only on: which farmland classes are admitted, whether
    # brownfields, activity zones and the poor-soil land of the agricultural
    # zone are open.  Shares and quotas are arithmetic on top.
    ch = icfg["choices"]
    combos = {}
    for agri, sar, zae, azu in itertools.product(ch["agri_sets"], [0, 1], [0, 1], [0, 1]):
        scn = apply_case(ref, {})
        scn["agrivoltaics"]["open"] = bool(ch["agri_sets"][agri])
        scn["agrivoltaics"]["classes_admitted"] = ch["agri_sets"][agri] or []
        scn["policy"]["sar"] = 1.0 if sar else 0.0
        scn["policy"]["zae"] = scn["policy"]["zspec"] = 1.0 if zae else 0.0
        scn["policy"]["agri_zone_poor"] = 1.0 if azu else 0.0
        scn["policy"]["water_other"] = 1.0   # always computed; the page applies its share
        res = st.evaluate(scn)
        key = f"a{agri}-s{sar}-z{zae}-u{azu}"
        combos[key] = {k: v["openable_ha"] for k, v in res["gisements"].items()}
        logger.info("%s: %.0f ha openable", key, sum(combos[key].values()))

    # ---- checks against the report ---------------------------------------------------
    def page_total(scn_choice):
        """What the page computes, in Python."""
        agri, sar, zae_share, poor, water, quota = scn_choice
        poor = float(evidence["share"]) if poor == "ref" else float(poor)
        key = f"a{agri}-s{sar}-z{1 if zae_share > 0 else 0}-u{1 if poor > 0 else 0}"
        rows = {k: {"system": systems[k], "eligible_ha": 0.0,
                    "after_park_rule_ha": r["gisements"][k]["after_park_rule_ha"],
                    "openable_ha": combos[key][k]} for k in keys}
        scn = apply_case(ref, {})
        scn["agrivoltaics"]["open"] = bool(ch["agri_sets"][agri])
        scn["agrivoltaics"]["classes_admitted"] = ch["agri_sets"][agri] or []
        scn["agrivoltaics"]["cap_share_sau"] = quota
        scn["policy"].update({"sar": float(sar), "zae": zae_share, "zspec": zae_share,
                              "agri_zone_poor": poor, "water_other": float(water)})
        return policy_total(rows, scn)["policy_mwc"]

    head = json.loads(Path(snakemake.input.headline).read_text())
    sens = json.loads(Path(snakemake.input.detail).read_text())
    checks = {
        "reference": (("prairies", 1, ref["policy"]["zae"], "ref", 0,
                       cfg["agrivoltaics"]["cap_share_sau"]), head["reference"]["policy_mwc"]),
    }
    for case, choice in icfg["checks"].items():
        checks[case] = (tuple(choice), sens[case]["total"]["policy_mwc"])
    bad = {}
    for name, (choice, expected) in checks.items():
        got = page_total(choice)
        logger.info("check %-20s page %.0f report %.0f", name, got, expected)
        if abs(got - expected) > 1:
            bad[name] = (got, expected)
    if bad:
        raise RuntimeError(f"dashboard arithmetic differs from the report: {bad}")

    # ---- landmarks -------------------------------------------------------------------
    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(st.grid["crs"])
    admin = regions[regions["name"] == "admin"].geometry.iloc[0].simplify(150)
    roads = gpd.read_file(snakemake.input.pds_roads, layer="data").to_crs(st.grid["crs"])
    mw = roads[roads["DESCRIPTION"] == "Autoroute existante"].geometry.union_all().simplify(100)
    towns = gpd.GeoDataFrame(icfg["cities"], geometry=gpd.points_from_xy(
        [c["lon"] for c in icfg["cities"]], [c["lat"] for c in icfg["cities"]]), crs=4326
    ).to_crs(st.grid["crs"])
    parks = gpd.read_file(snakemake.input.parks, layer="data").to_crs(st.grid["crs"])
    pp = parks.representative_point()
    landmarks = {
        "outline": svg_path(admin, to_px),
        "motorways": svg_path(mw, to_px),
        "towns": [{"name": c["name"], "xy": [round(v, 1) for v in to_px(p.x, p.y)],
                   **({"side": c["side"]} if c.get("side") else {})}
                  for c, p in zip(icfg["cities"], towns.geometry)],
        "parks": [[round(v, 1) for v in to_px(p.x, p.y)] + [round(float(a), 1)]
                  for p, a in zip(pp, parks["area_ha"])],
        "loupe": loupe,
    }
    Path(snakemake.output.landmarks).write_text(json.dumps(landmarks))

    # ---- states --------------------------------------------------------------------------
    now = datetime.now()
    meta = {
        "calc_date": f"{now.day} {MONTHS[now.month - 1]} {now.year}",
        "grid": {"cols": cols_disp, "rows": rows_disp, "res_m": st.res * F, "scale": SCALE},
        "loupe_grid": {"cols": size, "rows": size, "res_m": st.res, "scale": SCALE},
        "region_ha": round(r["region_ha"], 0),
        "families": [{"key": f"f{i + 1}", "colour": c} for i, (c, _, _) in enumerate(DISPLAY_FAMILIES)],
        "gisements": [{"key": k, "system": systems[k],
                       "group": next(gi for gi, (_, _, m) in enumerate(GROUPS) if k in m)}
                      for k in keys],
        "groups": [{"colour": c} for c, _, _ in GROUPS],
        "densities_mwc_ha": ref["densities_mwc_ha"],
        "floating_coverage": ref["floating_coverage"],
        "policy_reference": ref["policy"],
        "agri": {"sau_ha": cfg["agrivoltaics"]["sau_ha"], "sets": ch["agri_sets"],
                 "quotas": ch["quotas"]},
        "soil_evidence": evidence,
        "park": ref["park"],
        "technical_ha": {k: v["after_park_rule_ha"] for k, v in r["gisements"].items()},
        "eligible_ha": {k: v["eligible_ha"] for k, v in r["gisements"].items()},
        "funnel": funnel,
        "benchmarks": cfg["benchmarks"],
        "energy": json.loads(Path(snakemake.input.energy).read_text()),
        "sensitivity": [
            {"case": row["case"], "group": row["group"], "label": row["label"],
             "policy_mwc": float(row["policy_mwc"]), "delta_pct": float(row["delta_pct"])}
            for _, row in pd.read_csv(snakemake.input.sensitivity).iterrows()
            if row["group"] in ("judgement", "technical")],
        "reference_mwc": head["reference"]["policy_mwc"],
        "technical_mwc": head["reference"]["technical_mwc"],
    }
    Path(snakemake.output.states).write_text(json.dumps({"meta": meta, "combos": combos}))
    logger.info("dashboard data written to %s", out)
