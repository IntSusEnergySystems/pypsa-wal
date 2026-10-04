# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
The evaluation core shared by every result of the workflow: the reference, the
sensitivity cases, the report tables and the dashboard states all go through
``Stack.evaluate``, so they cannot disagree.

``Stack`` loads the burnt layers once, packed one bit per layer into a
``uint64`` code raster (0.8 GB on the 20 m grid), with the continuous rasters
(slope, aspect, WALOUS shares, SIGEC class, soil quality) alongside.  A
scenario is a plain dict (see ``scenario_from_config``); ``evaluate`` returns,
for each gisement, the eligible area before and after the park rule, the
technical capacity (every eligible hectare) and the capacity the scenario's
policy opens.

Exclusion families apply to *land* systems.  A floating system is on water:
it keeps the protection families (nature, forest zone, landscape) and ignores
the land-cover, terrain, built and hazard families, which describe the ground.
"""

import json
import logging
from copy import deepcopy
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

logger = logging.getLogger(__name__)

# Funnel order: the order of the dashboard (display groups nature | forest+cover |
# landscape | hazard+terrain | built+water), so that each cell is counted in the
# step where the reader sees it go.
FAMILIES = ["nature", "forest", "cover", "landscape", "hazard", "terrain", "built"]
WATER_FAMILIES = ["nature", "forest", "landscape"]
RASTERS = ["slope_pct", "aspect_deg", "sigec_class", "soil_quality",
           "walous_built", "walous_sealed", "walous_water", "walous_trees"]


def read(path):
    with rasterio.open(path) as src:
        return src.read(1)


class Stack:
    """All layers of one grid, packed."""

    def __init__(self, cfg, grid_json, layer_dir, raster_paths, region_mask):
        self.cfg = cfg
        self.grid = json.loads(Path(grid_json).read_text())
        self.res = float(self.grid["res"])
        self.cell_ha = self.res ** 2 / 1e4
        self.region = read(region_mask).astype(bool)
        names = list(cfg["layers"]) + list(cfg["masks"])
        if len(names) > 64:
            raise ValueError(f"{len(names)} layers do not fit in 64 bits")
        self.bit = {n: np.uint64(1) << np.uint64(i) for i, n in enumerate(names)}
        self.code = np.zeros(self.region.shape, dtype=np.uint64)
        for n in names:
            m = read(Path(layer_dir) / f"{n}.tif").astype(bool)
            self.code[m] |= self.bit[n]
        logger.info("packed %d layers", len(names))
        self.r = {k: read(v) for k, v in raster_paths.items()}
        with rasterio.open(region_mask) as src:
            self.transform, self.crs = src.transform, src.crs

    # -- masks ---------------------------------------------------------------
    def has(self, names):
        """Cells in any of the named burnt layers."""
        bits = np.uint64(0)
        for n in names:
            bits |= self.bit[n]
        return (self.code & bits) != 0

    def family_mask(self, fam, scn):
        """Cells excluded by one family under scenario ``scn``."""
        if fam == "terrain":
            t = scn["terrain"]
            s, a = self.r["slope_pct"], self.r["aspect_deg"].astype(np.int32)
            lo, hi = t["north_sector_deg"]
            north = ((a >= lo) | (a <= hi)) if lo > hi else ((a >= lo) & (a <= hi))
            north &= a != 65535
            valid = s != 255
            return valid & ((s >= t["max_slope_pct"]) | (north & (s >= t["north_max_slope_pct"])))
        if fam == "cover":
            th = scn["walous_thresholds_pct"]
            return self.r["walous_trees"] >= th["trees"]
        if fam == "built":
            th = scn["walous_thresholds_pct"]
            m = (self.r["walous_built"] >= th["built"]) | (self.r["walous_sealed"] >= th["sealed"])
            layers = [n for n in scn["layers"] if self.cfg["layers"][n]["family"] == "built"]
            return m | self.has(layers) if layers else m
        layers = [n for n in scn["layers"] if self.cfg["layers"][n]["family"] == fam]
        return self.has(layers) if layers else np.zeros(self.region.shape, bool)

    def water(self, scn):
        """Open water for the ground systems to avoid (and floating to use)."""
        return self.has(["water_any"]) | (self.r["walous_water"] >= scn["walous_thresholds_pct"]["water"])

    def gisement_raster(self, scn):
        """uint8: index+1 of the first gisement whose test a Region cell passes."""
        env = {n: self.has([n]) for n in self.cfg["masks"]}
        env["sigec"] = self.r["sigec_class"]
        env["soil"] = self.r["soil_quality"]
        env["region"] = self.region
        out = np.zeros(self.region.shape, dtype=np.uint8)
        free = self.region.copy()
        for i, g in enumerate(scn["gisements"]):
            m = eval(g["test"], {"__builtins__": {}}, env) & free  # noqa: S307
            out[m] = i + 1
            free &= ~m
        return out

    def open_mask(self, gis, keys, share, scn):
        """Cells of the gisements a scenario opens, minus the soil filter."""
        idx = [i + 1 for i, k in enumerate(keys) if share.get(k, 0) > 0]
        m = np.isin(gis, idx)
        sf = scn.get("soil_filter") or {}
        if sf.get("max_class"):
            fidx = [i + 1 for i, k in enumerate(keys) if k in sf.get("gisements", [])]
            # only soils *mapped* as poor: class 0 (not mapped) is not
            # « démontré médiocre »
            soil = self.r["soil_quality"]
            m &= ~(np.isin(gis, fidx) & ((soil > sf["max_class"]) | (soil == 0)))
        return m

    # -- the park rule -------------------------------------------------------
    def park_filter(self, mask, scn):
        """Morphological opening to a minimum width, then a minimum area."""
        w = int(round(scn["park"]["min_width_m"] / self.res))
        if w > 1:
            st = np.ones((w, w), dtype=bool)
            mask = ndimage.binary_opening(mask, structure=st)
        min_cells = int(np.ceil(scn["park"]["min_area_ha"] / self.cell_ha))
        if min_cells > 1:
            lab, n = ndimage.label(mask)
            sizes = np.bincount(lab.ravel())
            keep = sizes >= min_cells
            keep[0] = False
            mask = keep[lab]
            del lab
        return mask

    # -- one scenario ---------------------------------------------------------
    def evaluate(self, scn, keep_rasters=False):
        gis = self.gisement_raster(scn)
        keys = [g["key"] for g in scn["gisements"]]
        systems = {g["key"]: g["system"] for g in scn["gisements"]}
        land_ex = np.zeros(self.region.shape, bool)
        fam_first = np.zeros(self.region.shape, np.uint8)   # funnel attribution
        funnel = []
        for k, fam in enumerate(FAMILIES):
            m = self.family_mask(fam, scn) & self.region
            fam_first[m & ~land_ex] = k + 1
            land_ex |= m
            funnel.append({"family": fam,
                           "left_ha": float((self.region & ~land_ex).sum()) * self.cell_ha})
        water = self.water(scn) & self.region
        fam_first[water & ~land_ex] = len(FAMILIES) + 1
        water_ex = np.zeros(self.region.shape, bool)
        for fam in WATER_FAMILIES:
            water_ex |= self.family_mask(fam, scn)

        is_float = np.isin(gis, [i + 1 for i, k in enumerate(keys) if systems[k] == "floating"])
        land_ok = self.region & ~land_ex & ~water & ~is_float
        float_ok = self.region & is_float & ~water_ex

        # Technical: the park rule on all eligible land.  Policy: the park rule
        # again, on the land the scenario opens only -- a strip of motorway
        # verge must be wide enough on its own, not thanks to the closed
        # farmland beside it (on the reference, filtering once and applying
        # the shares afterwards overstates the opened land by a third).
        funnel.append({"family": "water",
                       "left_ha": float((self.region & ~land_ex & ~water).sum()) * self.cell_ha})
        tech_land = self.park_filter(land_ok, scn)
        funnel.append({"family": "park_rule",
                       "left_ha": float(tech_land.sum()) * self.cell_ha,
                       "floating_ha": float(float_ok.sum()) * self.cell_ha})
        share = open_shares(scn, systems)
        pol_land = self.park_filter(land_ok & self.open_mask(gis, keys, share, scn), scn)
        rows = {}
        for i, k in enumerate(keys):
            sel = gis == i + 1
            if systems[k] == "floating":
                pre = post = opened = float((float_ok & sel).sum()) * self.cell_ha
            else:
                pre = float((land_ok & sel).sum()) * self.cell_ha
                post = float((tech_land & sel).sum()) * self.cell_ha
                opened = float((pol_land & sel).sum()) * self.cell_ha
            rows[k] = {"system": systems[k], "eligible_ha": round(pre, 1),
                       "after_park_rule_ha": round(post, 1),
                       "openable_ha": round(opened if share.get(k, 0) > 0 else 0.0, 1)}
        tot = policy_total(rows, scn)
        out = {"gisements": rows, "total": tot, "funnel": funnel,
               "region_ha": float(self.region.sum()) * self.cell_ha}
        if keep_rasters:
            out["rasters"] = {"gisement": gis, "family_first": fam_first,
                              "tech_land": tech_land, "policy_land": pol_land,
                              "float_ok": float_ok, "land_ok": land_ok}
        return out


def open_shares(scn, systems):
    """Share of each gisement a scenario opens (farmland: 0 or 1, quota apart)."""
    cap = scn["agrivoltaics"]
    share = dict(scn["policy"])
    for k, sysk in systems.items():
        if sysk.startswith("agrivoltaic"):
            share[k] = 1.0 if (cap.get("open") and k in cap["classes_admitted"]) else 0.0
    return share


def policy_total(rows, scn):
    """
    Capacity per gisement, from the areas alone (mirrored in the dashboard).

    technical  every hectare that survives the exclusions and the park rule
    policy     the openable area (the park rule re-applied to the opened land
               only) times the share the policy opens; farmland capped as a
               quota on the SAU, the admitted classes being interchangeable for
               it (the quota binds on hectares, not on places).
    """
    dens = scn["densities_mwc_ha"]
    cover = scn["floating_coverage"]
    cap = scn["agrivoltaics"]
    share = open_shares(scn, {k: r["system"] for k, r in rows.items()})
    agri = [k for k, r in rows.items() if r["system"].startswith("agrivoltaic")]
    for k, r in rows.items():
        r["mwc_per_ha"] = dens["floating"] * cover if r["system"] == "floating" else dens[r["system"]]
        r["technical_mwc"] = round(r["after_park_rule_ha"] * r["mwc_per_ha"], 1)
        r["open_ha"] = r["openable_ha"] * share.get(k, 0.0)
    cap_ha = (cap["cap_share_sau"] * cap["sau_ha"]
              if cap.get("open") and cap.get("cap_share_sau") is not None else None)
    open_agri = sum(rows[k]["open_ha"] for k in agri)
    f = cap_ha / open_agri if (cap_ha is not None and open_agri > cap_ha) else 1.0
    for k in agri:
        rows[k]["open_ha"] *= f
    for r in rows.values():
        r["open_ha"] = round(r["open_ha"], 1)
        r["policy_mwc"] = round(r["open_ha"] * r["mwc_per_ha"], 1)
    return {"technical_mwc": round(sum(r["technical_mwc"] for r in rows.values()), 0),
            "policy_mwc": round(sum(r["policy_mwc"] for r in rows.values()), 0),
            "eligible_ha": round(sum(r["eligible_ha"] for r in rows.values()), 0),
            "after_park_rule_ha": round(sum(r["after_park_rule_ha"] for r in rows.values()), 0),
            "open_ha": round(sum(r["open_ha"] for r in rows.values()), 0),
            "agri_open": bool(cap.get("open")),
            "agri_cap_ha": None if cap_ha is None else round(cap_ha, 0),
            "agri_cap_binding": bool(f < 1.0),
            "shares": share}


def scenario_from_config(cfg, evidence=None):
    """
    The reference scenario, as a plain dict every case is a copy of.

    A policy share given as the string ``soil_evidence`` is the share computed
    by scripts/soil_evidence.py (``evidence["share"]``).
    """
    ref_layers = [n for n, s in cfg["layers"].items() if s.get("reference", True)]
    return {
        "layers": ref_layers,
        "terrain": deepcopy(cfg["terrain"]),
        "walous_thresholds_pct": deepcopy(cfg["walous"]["thresholds_pct"]),
        "gisements": deepcopy(cfg["gisements"]),
        "park": deepcopy(cfg["park"]),
        "densities_mwc_ha": {k: v["ref"] for k, v in cfg["densities_mwc_ha"].items()},
        "floating_coverage": cfg["floating"]["coverage"]["ref"],
        "policy": {k: (float((evidence or {}).get("share", 0.0)) if v == "soil_evidence" else v)
                   for k, v in cfg["policy"]["reference"].items()},
        "agrivoltaics": deepcopy(cfg["agrivoltaics"]),
        "soil_filter": deepcopy(cfg.get("soil_filter") or {}),
    }


def apply_case(scn, case, evidence=None, name=None):
    """
    A sensitivity case: a dict of changes to the reference scenario.  A case
    that changes the soil evidence (``soil_evidence: {...}``) takes the share
    computed for it (``evidence["variants"][name]``).
    """
    s = deepcopy(scn)
    if "soil_evidence" in case and evidence is not None:
        s["policy"]["agri_zone_poor"] = float(evidence["variants"][name])
    for n in case.get("drop_layers", []):
        s["layers"] = [l for l in s["layers"] if l != n]
    for n in case.get("add_layers", []):
        if n not in s["layers"]:
            s["layers"].append(n)
    for key in ("terrain", "walous_thresholds_pct", "park", "densities_mwc_ha",
                "policy", "agrivoltaics", "soil_filter"):
        if key in case:
            s[key].update(case[key])
    if "floating_coverage" in case:
        s["floating_coverage"] = case["floating_coverage"]
    return s
