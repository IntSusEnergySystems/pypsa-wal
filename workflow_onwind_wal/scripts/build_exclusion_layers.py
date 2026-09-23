# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Translate the Walloon siting rules into geometry layers, for one turbine class.

Four groups of layers are produced, each written as a separate layer of one
GeoPackage so that any of them can be inspected in QGIS:

``pds_ineligible``
    The complement, inside Wallonia, of the plan-de-secteur zones in which a
    turbine may stand.  This is a *positive-list* construction, exactly as in
    the 2013 Walloon favourable-zone map and its 2022 update: agricultural land
    counts only within 1.5 km of the main communication infrastructure (PIC) or
    of a zone d'activité économique (CoDT R.II.36-2), coniferous forest only
    within 750 m of a PIC (R.II.37-2), and broad-leaved forest not at all.  The
    PIC is the network of CoDT R.II.21-1 -- motorways and 2x2 regional roads,
    railways, waterways -- not every road of the plan de secteur.  Two variants
    are written for the sensitivity analysis (the forest readings
    ``pds_ineligible_conifers`` and ``pds_ineligible_forest``, with and without
    the corridor, among them): ``pds_ineligible_nocorridor``
    (agricultural land admitted everywhere, the derogation route of D.IV.11) and
    ``pds_ineligible_psroads`` (every plan-de-secteur road taken as a PIC).

``habitat_setback`` / ``dwelling_setback`` / ``infrastructure_setback``
    Buffers whose width follows the Cadre de référence éolien.  The habitat-zone
    setback is configurable between the 2013 rule (4 x total height) and the
    2024 rule (500 m + half the total height), which is the one in force since
    25 April 2024; the other rule is written as ``habitat_setback_<rule>``.  The
    400 m dwelling setback is drawn around the ICAR address points outside the
    zones d'activité économique, whose addresses are businesses or the
    operators' housing the 2024 rule exempts.

``nature`` / ``landscape`` / ``risk``
    Protected-area, landscape and natural-hazard layers.

``aviation`` / ``heritage`` / ``radar``
    The aeronautical servitudes of the DGTA obstacle-evaluation map, the
    classified sites and their protection perimeters, and a reconstruction of
    the radar and radio-astronomy perimeters that have no published geometry.
    The slope criterion of the same group is a raster and is built separately
    by ``retrieve_slope_raster.py``.

Everything is computed in the equal-area CRS of the workflow (EPSG:3035).
Buffer widths that depend on the machine are evaluated from ``H`` (total tip
height = hub height + rotor radius) and ``D`` (rotor diameter).
"""

import json
import logging
from pathlib import Path

# rasterio before geopandas: in this environment the reverse import order makes
# the first deflate-compressed GeoTIFF write abort ("double free or corruption").
import rasterio
import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import shapes as rio_shapes
from rasterio.transform import from_origin
from scipy.ndimage import distance_transform_edt
from shapely.geometry import shape as shapely_shape
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

# Resolution of the raster on which the scattered-dwelling setback is computed.
# Buffering 1.5 M address points as vectors and unioning them is intractable;
# an exact Euclidean distance transform on a 50 m grid gives the same mask to
# within half a cell, well inside the 100 m resolution of the exclusion raster.
DWELLING_RASTER_RES = 50


def evaluate(expr, H, D):
    """Evaluate a setback expression in terms of H (tip height) and D (rotor)."""
    if expr is None:
        return 0.0
    if isinstance(expr, (int, float)):
        return float(expr)
    return float(eval(expr, {"__builtins__": {}}, {"H": H, "D": D}))  # noqa: S307


def read(path, crs, repair=True):
    """
    Read one downloaded layer and reproject it.

    Server-side generalisation occasionally produces self-intersecting rings, so
    every polygon layer is repaired on the way in; a single invalid ring is
    enough to make GEOS abort the union of a 44 000-polygon layer.
    """
    gdf = gpd.read_file(path, layer="data").to_crs(crs)
    if repair and not gdf.empty and gdf.geom_type.isin(["Polygon", "MultiPolygon"]).any():
        bad = ~gdf.geometry.is_valid
        if bad.any():
            logger.info("repairing %d invalid geometries in %s", int(bad.sum()), path)
            gdf.loc[bad, "geometry"] = gdf.loc[bad, "geometry"].make_valid()
        gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    return gdf


def _union(geoms):
    """Union that survives the odd unrepairable ring."""
    try:
        return unary_union(geoms)
    except Exception as exc:  # noqa: BLE001 - fall back to a cleaning pass
        logger.warning("union failed (%s); retrying after buffer(0)", exc)
        cleaned = gpd.GeoSeries(geoms).buffer(0)
        return unary_union(cleaned.values)


def dissolve(gdf):
    if gdf.empty:
        return None
    return _union(gdf.geometry.values)


def buffered(gdf, distance, crs):
    """Union of `gdf` buffered by `distance` metres (0 => plain union)."""
    if gdf.empty:
        return None
    geom = gdf.geometry
    if distance and distance > 0:
        geom = geom.buffer(distance)
    return _union(geom.values)


# The CORINE raster shipped in the PyPSA-Eur data bundle declares no usable
# CRS (its GeoTIFF header carries a LOCAL_CS placeholder), but its grid is
# ETRS89-LAEA.  PyPSA-Eur works around this by passing crs=3035 explicitly to
# ExclusionContainer.add_raster; we do the same.
CORINE_CRS = 3035


def conifer_mask(forest, corine_path, codes, crs):
    """
    Split plan-de-secteur forest zones into coniferous and other stands.

    The plan de secteur does not record the species composition, so the split
    comes from CORINE (grid codes 23 broad-leaved / 24 coniferous / 25 mixed).
    Mixed stands are counted as broad-leaved, which is the conservative choice.
    """
    with rasterio.open(corine_path) as src:
        bounds = forest.to_crs(CORINE_CRS).total_bounds
        window = rasterio.windows.from_bounds(*bounds, transform=src.transform)
        window = window.round_offsets().round_lengths()
        data = src.read(1, window=window)
        transform = src.window_transform(window)

    mask = np.isin(data, codes).astype(np.uint8)
    if not mask.any():
        logger.warning("no CORINE cell with codes %s over the forest zones", codes)
        return None
    polys = [
        shapely_shape(geom)
        for geom, val in rio_shapes(mask, mask=mask.astype(bool), transform=transform)
        if val == 1
    ]
    logger.info("%d coniferous CORINE patches", len(polys))
    conif = gpd.GeoDataFrame(geometry=polys, crs=CORINE_CRS).to_crs(crs)
    return _union(conif.geometry.values)


def clip(geom, boundary):
    if geom is None:
        return None
    g = geom.intersection(boundary)
    return g if not g.is_empty else None


def dwelling_setback_raster(points, distance, boundary, crs, path, res=DWELLING_RASTER_RES):
    """
    Burn a `distance`-metre setback around every address point into a GeoTIFF.

    Written as 1 = excluded / 0 = free, so it can be handed to
    ``ExclusionContainer.add_raster(codes=[1])``.
    """
    minx, miny, maxx, maxy = boundary.bounds
    pad = distance + 5 * res
    minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
    width = int(np.ceil((maxx - minx) / res))
    height = int(np.ceil((maxy - miny) / res))
    logger.info("dwelling raster %d x %d cells at %d m", width, height, res)

    xs = points.geometry.x.values
    ys = points.geometry.y.values
    cols = ((xs - minx) / res).astype(np.int64)
    rows = ((maxy - ys) / res).astype(np.int64)
    keep = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
    logger.info("%d of %d address points inside the raster", keep.sum(), len(points))

    occupied = np.zeros((height, width), dtype=bool)
    occupied[rows[keep], cols[keep]] = True

    # Distance, in cells, to the nearest address point.
    dist = distance_transform_edt(~occupied, sampling=res)
    mask = (dist <= distance).astype(np.uint8)

    transform = from_origin(minx, maxy, res, res)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint8",
        crs=f"EPSG:{crs}",
        transform=transform,
        compress="deflate",
        nodata=255,
    ) as dst:
        dst.write(mask, 1)

    share = float(mask.mean())
    logger.info("dwelling setback covers %.1f %% of the raster envelope", 100 * share)
    return share


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    crs = snakemake.params.crs
    pds_cfg = snakemake.params.plan_de_secteur
    sb_cfg = snakemake.params.setbacks
    forest_cfg = snakemake.params.forest_split
    turbine = snakemake.params.turbine

    D = float(turbine["rotor_diameter"])
    H = float(turbine["hub_height"]) + D / 2.0
    logger.info("turbine %s: D=%.0f m, tip height H=%.0f m", turbine["label"], D, H)

    src = dict(snakemake.input)
    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    boundary = regions.union_all()

    # ------------------------------------------------------------------
    # 1. Plan de secteur: build the eligible envelope, then invert it
    # ------------------------------------------------------------------
    zones = read(src["pds_zones"], crs)
    zones["DESCRIPTION"] = zones["DESCRIPTION"].astype(str).str.strip()

    # Every configured label must name a zone that exists: a spelling variant
    # ("Dépendances" for "Dépendance d'extraction") once dropped 148 km2 of
    # zoning without a word.
    known = set(zones["DESCRIPTION"])
    for key in ("eligible_unconditional", "economic_activity_zones",
                "eligible_conditional_agriculture", "eligible_conditional_forest",
                "habitat_zones"):
        unknown = sorted(set(pds_cfg[key]) - known)
        if unknown:
            raise ValueError(
                f"plan_de_secteur.{key}: no zone is labelled {unknown}; "
                f"the labels present are {sorted(known)}"
            )

    def pick(labels):
        return zones[zones["DESCRIPTION"].isin(labels)]

    # PIC = principales infrastructures de communication, CoDT art. R.II.21-1:
    # "les autoroutes et les routes de liaisons régionales à deux fois deux
    # bandes de circulation", the railway lines, the navigable waterways.
    roads_pds = read(src["pds_roads"], crs)
    rail = read(src["pds_rail"], crs)
    waterways = read(src["pds_waterways"], crs)
    dual = read(src["osm_dual_carriageways"], crs, repair=False)
    motorways_pds = roads_pds[roads_pds["DESCRIPTION"] == "Autoroute existante"]
    rail_ww = [g for g in (dissolve(rail), dissolve(waterways)) if g is not None]
    pic_codt = _union(list(motorways_pds.geometry.values) + list(dual.geometry.values) + rail_ww)
    pic_psroads = _union(list(roads_pds.geometry.values) + rail_ww)
    pic = pic_codt if pds_cfg["pic_roads"] == "codt" else pic_psroads
    logger.info(
        "PIC roads (%s): %.0f km of plan-de-secteur motorway, %.0f km of OSM "
        "dual carriageway (both carriageways counted); every plan-de-secteur "
        "road would be %.0f km",
        pds_cfg["pic_roads"],
        motorways_pds.length.sum() / 1e3,
        dual.length.sum() / 1e3,
        roads_pds.length.sum() / 1e3,
    )

    econ = pick(pds_cfg["eligible_unconditional"])
    econ_geom = dissolve(econ)
    zae_geom = dissolve(pick(pds_cfg["economic_activity_zones"]))
    agri_geom = dissolve(pick(pds_cfg["eligible_conditional_agriculture"]))
    forest = pick(pds_cfg["eligible_conditional_forest"])
    conif = None
    if not forest.empty:
        conif = conifer_mask(
            forest, forest_cfg["corine"], forest_cfg["coniferous_codes"], crs
        )
    forest_geom = dissolve(forest)
    reach = pds_cfg["agri_max_distance_to_pic"]

    def envelope(pic_net, corridor=True, forest="codt"):
        """
        The plan-de-secteur zones a mast may stand in, for one PIC network.

        ``forest`` is the reading of the forest zone: ``codt`` coniferous stands
        within the conifer distance of a PIC (D.II.37 §1, R.II.37-2);
        ``conifers`` every coniferous stand, which is the Cadre 2024 wording
        (§3.2 §1) without the CoDT's distance; ``all`` the whole forest zone.
        """
        agri = agri_geom
        if agri is not None and corridor:
            anchors = [pic_net.buffer(reach)] + ([zae_geom.buffer(reach)] if zae_geom else [])
            agri = agri.intersection(_union(anchors))
        forest_ok = None
        if forest_geom is not None and forest == "all":
            forest_ok = forest_geom
        elif forest_geom is not None and conif is not None:
            forest_ok = forest_geom.intersection(conif)
            if forest == "codt":
                forest_ok = forest_ok.intersection(
                    pic_net.buffer(pds_cfg["conifer_max_distance_to_pic"])
                )
        return _union([g for g in (econ_geom, agri, forest_ok) if g is not None])

    eligible = envelope(pic, corridor=pds_cfg.get("agri_corridor", True))
    pds_ineligible = boundary.difference(eligible)
    pds_variants = {
        "pds_ineligible_nocorridor": boundary.difference(envelope(pic, corridor=False)),
        "pds_ineligible_psroads": boundary.difference(envelope(pic_psroads)),
        "pds_ineligible_conifers": boundary.difference(envelope(pic, forest="conifers")),
        "pds_ineligible_conifers_nocorridor": boundary.difference(
            envelope(pic, corridor=False, forest="conifers")),
        "pds_ineligible_forest": boundary.difference(envelope(pic, forest="all")),
        "pds_ineligible_forest_nocorridor": boundary.difference(
            envelope(pic, corridor=False, forest="all")),
    }

    # ------------------------------------------------------------------
    # 2. Setbacks
    # ------------------------------------------------------------------
    rule = sb_cfg["habitat_zone"][sb_cfg["habitat_zone"]["default"]]
    habitat_distance = evaluate(rule, H, D)
    logger.info("habitat-zone setback (%s): %.0f m", sb_cfg["habitat_zone"]["default"], habitat_distance)
    habitat_zones = pick(pds_cfg["habitat_zones"])
    habitat_union = _union(habitat_zones.geometry.values)
    habitat_setback = habitat_union.buffer(habitat_distance)
    habitat_variants = {}
    for name, expr in sb_cfg["habitat_zone"].items():
        if name in ("default", sb_cfg["habitat_zone"]["default"]):
            continue
        d = evaluate(expr, H, D)
        habitat_variants[f"habitat_setback_{name}"] = habitat_union.buffer(d)
        logger.info("habitat-zone setback variant %s: %.0f m", name, d)

    # Settlements, for the open-horizon criterion of the 2013 cadre de
    # référence: "un azimut minimal sans éoliennes doit être préservé pour
    # chaque village; celui-ci sera d'au moins 130°, sur une distance de 4 km".
    # A "village" is taken to be a contiguous block of plan-de-secteur habitat
    # zoning above `min_area_ha`; below that the block is a hamlet or a ribbon
    # and is already protected by the dwelling setback.
    settle = (
        gpd.GeoDataFrame(geometry=[habitat_union], crs=crs)
        .explode(index_parts=False)
        .reset_index(drop=True)
    )
    min_area = float(snakemake.params.settlements["min_area_ha"]) * 1e4
    settle = settle[settle.area >= min_area].copy()
    settle["area_ha"] = settle.area / 1e4
    settle["geometry"] = settle.geometry.centroid
    logger.info("%d settlements above %.0f ha", len(settle), min_area / 1e4)
    settle.to_file(snakemake.output.settlements, driver="GPKG", layer="settlements")

    dwelling_distance = evaluate(sb_cfg["scattered_dwellings"], H, D)
    addr = read(src["address_points"], crs)
    n_addr = len(addr)
    exempt_key = sb_cfg.get("scattered_dwellings_exempt_zones")
    n_exempt = 0
    if exempt_key and zae_geom is not None:
        inside = gpd.sjoin(
            addr, gpd.GeoDataFrame(geometry=[zae_geom], crs=crs), predicate="within"
        ).index
        n_exempt = len(inside)
        addr = addr.drop(index=inside)
    logger.info(
        "%d address points, %d of them inside a zone d'activité économique and "
        "exempt; %.0f m setback around the other %d",
        n_addr, n_exempt, dwelling_distance, len(addr),
    )
    dwelling_share = dwelling_setback_raster(
        addr, dwelling_distance, boundary, crs, snakemake.output.dwelling_raster
    )

    road_distance = evaluate(sb_cfg["road"], H, D) * sb_cfg["road_multiplier"]
    rail_distance = evaluate(sb_cfg["railway"], H, D)
    hsl_distance = evaluate(sb_cfg["railway_high_speed"], H, D)
    hv_distance = evaluate(sb_cfg["hv_line"], H, D)
    hsl = read(src["osm_high_speed_rail"], crs, repair=False)
    infra_parts = [
        g
        for g in (
            buffered(roads_pds, road_distance, crs),
            buffered(rail, rail_distance, crs),
            buffered(hsl, hsl_distance, crs),
            buffered(read(src["pds_hv_lines"], crs), hv_distance, crs),
        )
        if g is not None
    ]
    infrastructure_setback = _union(infra_parts)
    logger.info(
        "infrastructure setbacks: road %.0f m, rail %.0f m (high-speed %.0f m on "
        "%.0f km of track), HV %.0f m",
        road_distance, rail_distance, hsl_distance, hsl.length.sum() / 1e3, hv_distance,
    )

    # ------------------------------------------------------------------
    # 3. Nature, landscape, risk
    # ------------------------------------------------------------------
    def union_of(keys):
        parts = []
        for k in keys:
            if k not in src:
                logger.warning("layer %s absent, skipped", k)
                continue
            g = dissolve(read(src[k], crs))
            if g is not None:
                parts.append(g)
        return _union(parts) if parts else None

    nature = union_of(
        [
            "natura2000",
            "reserves_forest",
            "reserves_domanial",
            "reserves_agreed",
            "wetlands",
            "caves",
        ]
    )
    landscape_pds = union_of(["pds_landscape"])
    landscape_adesa = union_of(["adesa_landscape"])
    landscape = _union([g for g in (landscape_pds, landscape_adesa) if g is not None])
    karst = read(src["karst"], crs)
    levels = snakemake.params.risk["karst_levels"]
    kept = karst[karst["NATURE"].isin(levels)]
    logger.info("karst: %d of %d polygons at levels %s", len(kept), len(karst), levels)
    risk = _union(
        [g for g in [dissolve(kept)] if g is not None]
        + [g for g in [union_of(["flood", "landslide", "steep_slopes", "water_capture"])] if g is not None]
    )

    # ------------------------------------------------------------------
    # 3b. Aeronautical servitudes, classified sites, radar perimeters
    # ------------------------------------------------------------------
    av_cfg = snakemake.params.aviation
    aoem = read(src["aviation_obstacles"], crs)
    keep = aoem[aoem["HAUTEURS"].isin(av_cfg["exclude_heights"])]
    logger.info(
        "aviation: %d of %d AOEM polygons in classes %s",
        len(keep),
        len(aoem),
        av_cfg["exclude_heights"],
    )
    aviation = dissolve(keep)

    heritage = union_of(
        [
            "heritage_sites",
            "heritage_ensembles",
            "heritage_protection",
            "heritage_unesco",
        ]
    )

    # Circles around the installations whose protection perimeter is real but
    # unpublished.  Coordinates are WGS84 in the config; the buffer is applied
    # in the equal-area working CRS.
    radar_cfg = snakemake.params.radar_installations or []
    if radar_cfg:
        pts = gpd.GeoSeries(
            gpd.points_from_xy(
                [float(r["lon"]) for r in radar_cfg],
                [float(r["lat"]) for r in radar_cfg],
            ),
            crs=4326,
        ).to_crs(crs)
        radar = _union([p.buffer(float(r["radius_m"])) for p, r in zip(pts, radar_cfg)])
        for r in radar_cfg:
            logger.info("radar surrogate: %s, %.0f m", r["name"], float(r["radius_m"]))
    else:
        radar = None

    # ------------------------------------------------------------------
    # 4. Write
    # ------------------------------------------------------------------
    # Two copies of every layer: one multi-layer GeoPackage for inspection in
    # QGIS, and one file per layer because atlite refuses to parallelise an
    # ExclusionContainer whose geometries were handed in as GeoDataFrames
    # rather than as paths.
    out = Path(snakemake.output.layers)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    per_layer = Path(snakemake.output.layer_dir)
    per_layer.mkdir(parents=True, exist_ok=True)

    areas = {}
    for name, geom in [
        ("eligible_pds", eligible),
        ("pds_ineligible", pds_ineligible),
        ("habitat_setback", habitat_setback),
        ("infrastructure_setback", infrastructure_setback),
        ("nature", nature),
        ("landscape", landscape),
        ("landscape_pds", landscape_pds),
        ("landscape_adesa", landscape_adesa),
        ("risk", risk),
        ("aviation", aviation),
        ("heritage", heritage),
        ("radar", radar),
        *pds_variants.items(),
        *habitat_variants.items(),
    ]:
        g = clip(geom, boundary)
        if g is None:
            logger.warning("layer %s is empty", name)
            areas[name] = 0.0
            continue
        gdf = gpd.GeoDataFrame({"name": [name]}, geometry=[g], crs=crs)
        gdf.to_file(out, driver="GPKG", layer=name)
        gdf.to_file(per_layer / f"{name}.gpkg", driver="GPKG")
        areas[name] = round(gdf.area.sum() / 1e6, 1)
        logger.info("%-26s %10.1f km2", name, areas[name])

    areas["dwelling_setback_raster_share"] = round(dwelling_share, 4)

    meta = {
        "turbine": turbine,
        "tip_height_m": H,
        "rotor_diameter_m": D,
        "habitat_setback_rule": sb_cfg["habitat_zone"]["default"],
        "habitat_setback_m": round(habitat_distance, 1),
        "dwelling_setback_m": round(dwelling_distance, 1),
        "address_points": n_addr,
        "address_points_exempt_in_zae": n_exempt,
        "road_setback_m": round(road_distance, 1),
        "railway_setback_m": round(rail_distance, 1),
        "railway_high_speed_setback_m": round(hsl_distance, 1),
        "high_speed_track_km": round(float(hsl.length.sum() / 1e3), 1),
        "hv_line_setback_m": round(hv_distance, 1),
        "pic_roads": pds_cfg["pic_roads"],
        "pic_motorway_km": round(float(motorways_pds.length.sum() / 1e3), 1),
        "pic_dual_carriageway_km": round(float(dual.length.sum() / 1e3), 1),
        "pds_road_km": round(float(roads_pds.length.sum() / 1e3), 1),
        "karst_polygons_kept": int(len(kept)),
        "karst_polygons_total": int(len(karst)),
        "region_area_km2": round(boundary.area / 1e6, 1),
        "layer_areas_km2": areas,
    }
    Path(snakemake.output.stats).write_text(json.dumps(meta, indent=2))
    pd.Series(areas).to_csv(snakemake.output.areas, header=["area_km2"])
