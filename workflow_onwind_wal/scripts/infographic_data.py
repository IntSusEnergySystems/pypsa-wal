# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Everything the infographic draws, exported from the same burns and the same
placement code as the report, so the two cannot disagree.

Outputs, in ``results/infographic/data/``:

``attribution_<land>.png``
    One byte per 100 m cell of the reference grid: the number of the first
    family of ``config.infographic.families`` that excludes the cell, 0 if the
    cell survives, 6 outside the Region.  Values are stored multiplied by 40 so
    that a browser that nudges a grey level still decodes the right family.
    One map per land variant: the derogation (no agricultural corridor) or
    not, times the three readings of the forest zone (the CoDT's coniferous
    stands near a PIC, every coniferous stand, the whole forest zone).
``states.json``
    Area, number of machines and MW at every step of the funnel, for each of
    the 2 x 2 x 3 x 3 = 36 combinations of the "Et si… ?" choices.
``points.json``
    The machines of every placement state, as grid cells.
``landmarks.json``
    Region outline, motorways, towns, villages, the standing fleet and the
    magnifier window, already in grid coordinates.

Steps 0 to 5 carry the land-and-wake bound (``allocate_free``: the most
machines 5 D apart the land left can hold), so every step has a number.  Steps
6 to 8 are the placement models of ``place_turbines.py``; step 9 applies the
residual allowance.

The build fails if the reference, any one-at-a-time case or the two combined
cases differ from ``headline.json`` and ``sensitivity_cases.json``.
"""

import base64
import itertools
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# rasterio before geopandas: see retrieve_slope_raster.py.
import rasterio
import geopandas as gpd
import numpy as np
from atlite.gis import ExclusionContainer, shape_availability
from PIL import Image
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import linemerge

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

RASTERS = {"dwelling_setback": "dwelling_raster", "slope": "slope_raster"}
OUTSIDE = 6
SCALE = 40

FORESTS = ("codt", "conifers", "all")
LANDS = {  # key -> (derogation, forest reading)
    "ref": (False, "codt"),
    "derog": (True, "codt"),
    "conif": (False, "conifers"),
    "derog_conif": (True, "conifers"),
    "forest": (False, "all"),
    "derog_forest": (True, "all"),
}
# The forest readings are variants of the zoning layers, named by a suffix.
FOREST_SUFFIX = {"codt": "", "conifers": "_conifers", "all": "_forest"}
FOREST_CASE = {"conifers": "forest_conifers", "all": "forest_all"}


def forest_layer(name, forest):
    """pds_ineligible[_nocorridor] under a forest reading."""
    if not name.startswith("pds_ineligible") or forest == "codt":
        return name
    return name.replace("pds_ineligible", "pds_ineligible" + FOREST_SUFFIX[forest], 1)
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]


def family_layers(fam, derog, forest):
    layers = fam["layers"]
    if derog and "derogation" in fam:
        layers = fam["derogation"]
    return [forest_layer(l, forest) for l in layers]


def land_layers(cfg, derog, forest):
    """The reference layer set with the swaps of the matching sensitivity cases."""
    layers = list(cfg["scenarios"][cfg["reference_scenario"]]["layers"])
    if derog:
        for old, new in cfg["sensitivity"]["cases"]["no_corridor"]["land"].items():
            layers = [new if l == old else l for l in layers]
    return [forest_layer(l, forest) for l in layers]


def pack(*arrays):
    """Interleave uint16 arrays and base64 them (little-endian)."""
    a = np.stack([np.asarray(x, dtype="<u2") for x in arrays], axis=1).ravel()
    return base64.b64encode(a.tobytes()).decode("ascii")


def svg_path(geom, to_grid, ndigits=1):
    """SVG path data of a (multi)line or (multi)polygon, in grid coordinates."""
    parts = []

    def ring(coords, close):
        pts = [to_grid(x, y) for x, y in coords]
        s = "M" + "L".join(f"{c:.{ndigits}f},{r:.{ndigits}f}" for c, r in pts)
        parts.append(s + ("Z" if close else ""))

    def walk(g):
        if isinstance(g, Polygon):
            ring(g.exterior.coords, True)
            for i in g.interiors:
                ring(i.coords, True)
        elif isinstance(g, LineString):
            ring(g.coords, False)
        elif hasattr(g, "geoms"):
            for sub in g.geoms:
                walk(sub)

    walk(geom)
    return "".join(parts)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.config
    icfg = cfg["infographic"]
    crs = cfg["atlite"]["crs"]
    res = float(cfg["atlite"]["excluder_resolution"])
    tkey = cfg["reference_turbine"]
    turbine = cfg["turbines"][tkey]
    D, p_nom = float(turbine["rotor_diameter"]), float(turbine["p_nom"])
    pcfg, lcfg = cfg["placement"], cfg["placement"]["landscape"]
    spacing = float(pcfg["spacings_rotor_diameters"][pcfg["reference_case"]]) * D
    link = float(pcfg["park"]["link_m"])
    ref_layers = list(cfg["scenarios"][cfg["reference_scenario"]]["layers"])
    families = icfg["families"]
    out = Path(snakemake.output.states).parent
    out.mkdir(parents=True, exist_ok=True)

    headline = json.loads(Path(snakemake.input.headline).read_text())
    sens = json.loads(Path(snakemake.input.sensitivity).read_text())

    # The families must partition the reference constraint set.
    used = set(itertools.chain.from_iterable(f["layers"] for f in families))
    if used - {"pds_ineligible_nocorridor"} != set(ref_layers):
        raise ValueError(
            f"infographic families {sorted(used)} do not cover the reference "
            f"layers {sorted(ref_layers)}"
        )

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]

    # ------------------------------------------------------------------
    # One burn per layer, as in sensitivity.py
    # ------------------------------------------------------------------
    needed = set()
    for d, h in LANDS.values():
        needed |= set(land_layers(cfg, d, h))
        for f in families:
            needed |= set(family_layers(f, d, h))
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
    rows_n, cols_n = region.shape
    cell_km2 = res * res / 1e6

    with rasterio.open(snakemake.input.raster) as src:
        ref_raster = src.read(1).astype(bool)
        if src.transform != transform or src.shape != region.shape:
            raise RuntimeError("the reference raster is not on the burn grid")

    # ------------------------------------------------------------------
    # Attribution maps
    #
    # What is excluded is decided by the layer set of the matching sensitivity
    # case, so each map reproduces the report's raster; the families only say
    # *why*.  (The corridor-free zoning layer is burnt from its own polygon and
    # reaches a few edge cells the reference zoning does not: those stay free.)
    # ------------------------------------------------------------------
    attribution = {}
    for land, (derog, forest) in LANDS.items():
        total = np.zeros_like(region)
        for name in land_layers(cfg, derog, forest):
            total |= masks[name]
        fam = np.zeros(region.shape, dtype=np.uint8)
        for k in range(len(families), 0, -1):
            m = np.zeros_like(region)
            for name in family_layers(families[k - 1], derog, forest):
                m |= masks[name]
            fam[m] = k
        fam[~total] = 0
        if np.any(total & region & (fam == 0)):
            raise RuntimeError(f"{land}: excluded cells that no family claims")
        fam[~region] = OUTSIDE
        attribution[land] = fam
        Image.fromarray(fam * SCALE, mode="L").save(out / f"attribution_{land}.png", optimize=True)
        logger.info("attribution %-12s %s", land,
                    {k: round(float((fam == k).sum()) * cell_km2, 1) for k in range(len(families) + 1)})
    differ = int(np.sum((attribution["ref"] == 0) != ref_raster))
    if differ:
        raise RuntimeError(f"the families do not reproduce the reference raster ({differ} cells)")

    # ------------------------------------------------------------------
    # Land-and-wake bound at steps 0-5, and the placement states
    # ------------------------------------------------------------------
    def cells(mask):
        r, c = np.nonzero(mask)
        return r, c, transform.c + (c + 0.5) * transform.a, transform.f + (r + 0.5) * transform.e

    villages_gdf = gpd.read_file(snakemake.input.settlements, layer="settlements")
    villages = np.c_[villages_gdf.geometry.x, villages_gdf.geometry.y]
    roads = gpd.read_file(snakemake.input.dual_carriageways, layer="data").to_crs(crs)
    motorways_osm = roads[roads["highway"] == "motorway"].geometry
    dmw = motorway_distance(region.shape, transform, motorways_osm, res)

    free_cache = {}

    def free(mask):
        key = mask.tobytes().__hash__()
        if key not in free_cache:
            r, c, xs, ys = cells(mask)
            keep = allocate_free(xs, ys, spacing)
            free_cache[key] = (int(keep.sum()), r[keep], c[keep])
        return free_cache[key]

    points, land_steps = {}, {}
    for land, fam in attribution.items():
        steps = []
        for s in range(len(families) + 1):
            mask = region & ((fam == 0) | (fam > s))
            n, r, c = free(mask)
            steps.append({"area_km2": round(float(mask.sum()) * cell_km2, 1), "n": n,
                          "mw": round(n * p_nom)})
            logger.info("%-12s step %d: %.1f km2, room for %d machines", land, s,
                        steps[-1]["area_km2"], n)
        points[f"free_{land}"] = pack(r, c, np.zeros_like(r))
        land_steps[land] = steps

    def place(land, n_min, horizon, interdistance):
        mask = attribution[land] == 0
        r, c, xs, ys = cells(mask)
        amw = dmw[r, c] <= float(lcfg["motorway_exemption_m"])
        hz = (Horizon(villages, D, lcfg["horizon_radius_m"], lcfg["min_free_azimuth_deg"])
              if horizon else None)
        score = seed_scores(mask, r, c, res, float(pcfg["park"]["seed_radius_m"]))
        idx, pid, _ = grow_parks(xs, ys, score, spacing, link=link, n_min=n_min, horizon=hz,
                                 interdistance=float(interdistance), along_motorway=amw,
                                 tree=cKDTree(np.c_[xs, ys]))
        chk = check_layout(xs[idx], ys[idx], pid, spacing, n_min=n_min,
                           villages=villages if horizon else None, rotor_diameter=D,
                           radius=lcfg["horizon_radius_m"],
                           min_free_deg=lcfg["min_free_azimuth_deg"],
                           interdistance=float(interdistance), along_motorway=amw[idx])
        if not chk["ok"]:
            raise RuntimeError(f"layout breaks its own rules: {chk}")
        return r[idx], c[idx], pid

    placed = {}
    for land in LANDS:
        for n_min in (int(pcfg["park"]["min_turbines"]), 1):
            for rule, (hz, inter) in {"parks": (False, 0), "horizon": (True, 0),
                                      "inter4": (True, 4000), "inter6": (True, 6000)}.items():
                key = f"{rule}_{land}_m{n_min}"
                r, c, pid = place(land, n_min, hz, inter)
                points[key] = pack(r, c, pid)
                placed[key] = int(len(r))
                logger.info("%-26s %5d machines, %d parks", key, len(r),
                            int(pid.max() + 1) if len(pid) else 0)

    # ------------------------------------------------------------------
    # The 24 states
    # ------------------------------------------------------------------
    resid = headline["residual"]
    survival = {k: float(resid[k]["survival"]) for k in ("central", "low", "high")}
    n_min_ref = int(pcfg["park"]["min_turbines"])
    states = {}
    for derog, isolated, inter, forest in itertools.product((0, 1), (0, 1), (0, 4, 6), range(3)):
        land = next(k for k, v in LANDS.items() if v == (bool(derog), FORESTS[forest]))
        m = 1 if isolated else n_min_ref
        ls = land_steps[land]
        area = ls[-1]["area_km2"]
        steps = [dict(s, pts=None) for s in ls]
        steps.append(dict(ls[-1], pts=f"free_{land}"))
        for rule in ["parks", "horizon"] + ([f"inter{inter}"] if inter else []):
            key = f"{rule}_{land}_m{m}"
            steps.append({"area_km2": area, "n": placed[key], "mw": round(placed[key] * p_nom),
                          "pts": key})
        last = steps[-1]
        steps.append({
            "area_km2": None,
            "n": round(last["n"] * survival["central"]),
            "mw": round(last["mw"] * survival["central"]),
            "mw_low": round(last["mw"] * survival["high"]),
            "mw_high": round(last["mw"] * survival["low"]),
            "pts": last["pts"],
        })
        states[f"d{derog}-i{isolated}-x{inter}-f{forest}"] = {
            "land": land, "steps": steps,
        }

    # ------------------------------------------------------------------
    # Checks against the report
    # ------------------------------------------------------------------
    def st(key, i):
        return states[key]["steps"][i]

    ref = "d0-i0-x0-f0"
    fails = []

    def expect(what, got, want):
        if got != want:
            fails.append(f"{what}: {got} != {want}")

    s5, s7, s8, s9 = len(families), len(families) + 2, len(families) + 3, -1
    expect("reference area", st(ref, s5)["area_km2"], sens["reference"]["eligible_area_km2"])
    expect("reference free MW", st(ref, s5)["mw"], sens["reference"]["free_mw"])
    expect("reference parks MW", st(ref, s7)["mw"], sens["no_horizon"]["p_nom_max_mw"])
    expect("reference MW", st(ref, s8)["mw"], sens["reference"]["p_nom_max_mw"])
    expect("headline MW", st(ref, s8)["mw"], round(headline["placement"]["p_nom_max_mw"]))
    expect("central MW", st(ref, s9)["mw"], headline["credible_central_mw"])
    expect("range", [st(ref, s9)["mw_low"], st(ref, s9)["mw_high"]], headline["credible_range_mw"])
    for key, case, i in [
        ("d0-i0-x4-f0", "interdistance_4km", s8 + 1),
        ("d0-i0-x6-f0", "interdistance_6km", s8 + 1),
        ("d0-i1-x0-f0", "parks_min1", s8),
        ("d1-i0-x0-f0", "no_corridor", s8),
        ("d0-i0-x0-f1", "forest_conifers", s8),
        ("d0-i0-x0-f2", "forest_all", s8),
        ("d1-i1-x0-f0", "all_policy_relaxed", s8),
    ]:
        expect(f"{case} MW", st(key, i)["mw"], sens[case]["p_nom_max_mw"])
        expect(f"{case} area", st(key, s5)["area_km2"], sens[case]["eligible_area_km2"])
        expect(f"{case} free MW", st(key, s5)["mw"], sens[case]["free_mw"])
    if fails:
        raise RuntimeError("infographic differs from the report:\n  " + "\n  ".join(fails))
    logger.info("every state matches headline.json and sensitivity_cases.json")

    # ------------------------------------------------------------------
    # Landmarks
    # ------------------------------------------------------------------
    def to_grid(x, y):
        return (x - transform.c) / res, (transform.f - y) / res

    def grid_xy(geoms):
        return [[round(v, 1) for v in to_grid(g.x, g.y)] for g in geoms]

    outline = admin.geometry.union_all().simplify(120)
    pds_roads = gpd.read_file(snakemake.input.pds_roads).to_crs(crs)
    mw = pds_roads[pds_roads["DESCRIPTION"] == "Autoroute existante"].geometry.union_all()
    mw = linemerge(mw) if isinstance(mw, MultiLineString) else mw
    mw = mw.intersection(admin.geometry.union_all().buffer(2000)).simplify(80)
    fleet = gpd.read_file(snakemake.input.fleet).to_crs(crs)
    fleet = fleet[fleet.within(admin.geometry.union_all())]
    towns = gpd.GeoSeries(gpd.points_from_xy([c["lon"] for c in icfg["cities"]],
                                             [c["lat"] for c in icfg["cities"]]), crs=4326).to_crs(crs)

    # The magnifier: the window where every family and the surviving land are
    # all well represented, crossed by a motorway, with villages to draw the
    # open-horizon rule around.
    half = int(round(icfg["loupe"]["size_km"] * 1000 / res / 2))
    fam = attribution["ref"]
    onehot = np.stack([(fam == k) for k in range(len(families) + 1)]).astype(np.float32)
    integ = np.pad(onehot.cumsum(1).cumsum(2), ((0, 0), (1, 0), (1, 0)))
    mwgrid = (dmw < 300).astype(np.float32)
    mwint = np.pad(mwgrid.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    vg = np.array([to_grid(x, y) for x, y in villages])
    cands = []
    for r0 in range(half, rows_n - half, 10):
        for c0 in range(half, cols_n - half, 10):
            a, b, cc, dd = r0 - half, r0 + half, c0 - half, c0 + half
            cnt = integ[:, b, dd] - integ[:, a, dd] - integ[:, b, cc] + integ[:, a, cc]
            tot = cnt.sum()
            if tot < 0.98 * (2 * half) ** 2:
                continue
            share = cnt / tot
            mwc = mwint[b, dd] - mwint[a, dd] - mwint[b, cc] + mwint[a, cc]
            nv = int(((vg[:, 0] > cc) & (vg[:, 0] < dd) & (vg[:, 1] > a) & (vg[:, 1] < b)).sum())
            score = float(min(share[0] / 0.06, 1.5) * np.prod(np.minimum(share[1:] / 0.03, 1.0))
                          * (mwc > 0) * min(nv / 4, 1.0))
            cands.append((score, r0, c0, [round(float(v), 3) for v in share], nv))
    cands.sort(reverse=True)
    picked = []
    for cnd in cands:
        if all(abs(cnd[1] - p[1]) > 2 * half or abs(cnd[2] - p[2]) > 2 * half for p in picked):
            picked.append(cnd)
        if len(picked) == 3:
            break
    (out / "loupe_candidates.json").write_text(json.dumps([
        {"score": round(s, 3), "centre_3035": [transform.c + (c + 0.5) * res, transform.f - (r + 0.5) * res],
         "centre_grid": [c, r], "shares": sh, "villages": nv} for s, r, c, sh, nv in picked], indent=2))
    if icfg["loupe"]["centre"]:
        cx, cy = icfg["loupe"]["centre"]
        lc, lr = (int(round(v)) for v in to_grid(cx, cy))
    else:
        lr, lc = picked[0][1], picked[0][2]
    loupe = {"col0": lc - half, "row0": lr - half, "size": 2 * half}
    logger.info("loupe window %s (candidates: %s)", loupe, [(p[1], p[2]) for p in picked])

    landmarks = {
        "outline": svg_path(outline, to_grid),
        "motorways": svg_path(mw, to_grid),
        "towns": [{"name": c["name"], "xy": xy, "side": c.get("side", "right")}
                  for c, xy in zip(icfg["cities"], grid_xy(towns))],
        "fleet": grid_xy(fleet.geometry),
        "villages": [[round(c, 1), round(r, 1)] for c, r in vg],
        "loupe": loupe,
    }

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    stamp = datetime.fromtimestamp(Path(snakemake.input.sensitivity).stat().st_mtime)
    meta = {
        "grid": {"rows": rows_n, "cols": cols_n, "res_m": res, "crs": f"EPSG:{crs}",
                 "x0": transform.c, "y0": transform.f, "scale": SCALE, "outside": OUTSIDE},
        "families": [f["key"] for f in families],
        "turbine": {"label": turbine["label"], "p_nom_mw": p_nom, "rotor_m": D,
                    "tip_m": float(turbine["hub_height"]) + D / 2, "spacing_m": spacing},
        "rules": {
            "habitat_m": round(json.loads(Path(snakemake.input.exclusion_stats).read_text())["habitat_setback_m"]),
            "dwelling_m": round(float(cfg["setbacks"]["scattered_dwellings"])),
            "corridor_m": round(float(cfg["plan_de_secteur"]["agri_max_distance_to_pic"])),
            "conifer_m": round(float(cfg["plan_de_secteur"]["conifer_max_distance_to_pic"])),
            "park_link_m": link, "park_min": n_min_ref,
            "horizon_deg": lcfg["min_free_azimuth_deg"], "horizon_m": lcfg["horizon_radius_m"],
            "motorway_exemption_m": lcfg["motorway_exemption_m"],
        },
        "region_km2": round(float(region.sum()) * cell_km2, 1),
        "installed_mw": cfg["benchmarks"]["installed_2024_mw"],
        "fleet_n": int(len(fleet)),
        "model_cap_mw": cfg["benchmarks"]["model_p_nom_max_mw"],
        "survival": survival,
        "residual": resid["components"],
        "calc_date": f"{stamp.day} {MONTHS[stamp.month - 1]} {stamp.year}",
        "judgement": {k: {kk: v[kk] for kk in ("label", "p_nom_max_mw", "delta_pct")}
                      for k, v in sens.items() if v["group"] in ("judgement", "misreading")},
        "by_turbine": headline["placement"]["by_turbine"],
        "by_spacing": headline["placement"]["by_spacing"],
    }
    Path(snakemake.output.states).write_text(json.dumps({"meta": meta, "states": states},
                                                        ensure_ascii=False, indent=1))
    Path(snakemake.output.points).write_text(json.dumps(points))
    Path(snakemake.output.landmarks).write_text(json.dumps(landmarks, ensure_ascii=False))
    logger.info("wrote %s", out)
