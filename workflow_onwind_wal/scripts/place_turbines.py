# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Place individual machines on the eligible raster, instead of multiplying area
by a capacity density.

Multiplying eligible area by MW/km2 assumes that the land comes in blocks large
enough to lay out an array.  Walloon eligible land does not: it is thousands of
disconnected patches, most of them smaller than one turbine's share of an array.
The area-times-density figure therefore counts land no machine could occupy,
while screening patches by size throws away land that a machine *could* occupy,
because a real turbine does not have to sit inside one contiguous eligible
polygon.

The way out is the one VITO uses in the Dynamic Energy Atlas (Clymans et al.,
BREGILAB WP3, 2022): an allocation algorithm that walks the eligible cells and
accepts a machine wherever no previously accepted machine lies closer than a
minimum inter-turbine distance.  Patches smaller than an array still take one
turbine; a machine may stand at the edge of its patch with its rotor
overhanging ineligible land, which is what happens in reality and is legally
correct here, because the Walloon setbacks are measured from the mast.

Four models are run, each adding one rule to the one before.

``free``
    Minimum inter-turbine distance only.  This is the land-and-wake bound and
    it is what BREGILAB reports.  It is not a plausible build-out: it produces
    a carpet of lone machines across the whole Region.

``grouped``
    The same allocation, minus every machine that does not end up in a group of
    at least ``min_turbines`` within one farm diameter of each other.  This is
    the project-viability bound: a lone turbine on a leftover sliver is not a
    wind farm and nobody builds one.  No landscape rule is applied.

``farm``
    A two-level allocation: farm sites first, under their own minimum
    separation, machines only afterwards inside each site.  The radius and the
    reference separation are calibrated on the standing Walloon fleet, so the
    model forbids no configuration the Region has actually permitted.  Swept
    across the separations of interest, including the 4-6 km of the 2013
    cadre de référence.

``farm+horizon``
    The farm model plus the landscape criterion the 2013 framework actually
    states: at least ``min_free_azimuth_deg`` of each village's horizon, within
    ``horizon_radius_m``, free of turbines.  A candidate farm is refused if
    admitting it would close a village's open horizon below that angle.

The 4-6 km inter-farm distance is *not* the reference.  The framework calls it
indicative, subordinates it to the impact assessment, exempts turbines sited
along motorways -- which is where the Walloon zoning rule concentrates the
eligible land -- and the 2024 framework that replaced the 2013 one does not
carry it at all.  It is reported as a labelled legacy sensitivity.
"""

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import uniform_filter
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

logger = logging.getLogger(__name__)

SEED = 20260922


def allocate(xs, ys, min_distance, order):
    """
    Greedy minimum-distance allocation.

    Cells are visited in `order`; a cell is accepted when no accepted cell lies
    within `min_distance`.  A uniform grid of cell size `min_distance` keeps the
    neighbour test to the nine surrounding buckets, so the whole pass is O(N).
    """
    buckets = {}
    keep = np.zeros(len(xs), dtype=bool)
    d2 = min_distance * min_distance
    for i in order:
        x, y = xs[i], ys[i]
        bx, by = int(x // min_distance), int(y // min_distance)
        clash = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py) in buckets.get((bx + dx, by + dy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < d2:
                        clash = True
                        break
                if clash:
                    break
            if clash:
                break
        if clash:
            continue
        buckets.setdefault((bx, by), []).append((x, y))
        keep[i] = True
    return keep


def group(xs, ys, link, min_members):
    """Single-linkage grouping; returns the mask of points in a large enough group."""
    n = len(xs)
    if n == 0:
        return np.zeros(0, dtype=bool), np.zeros(0, dtype=np.int64)
    tree = cKDTree(np.c_[xs, ys])
    pairs = tree.query_pairs(link, output_type="ndarray")
    adj = (
        coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
        if len(pairs)
        else coo_matrix((n, n))
    )
    _, labels = connected_components(adj, directed=False)
    sizes = np.bincount(labels)
    return sizes[labels] >= min_members, labels


class OpenHorizon:
    """
    The open-horizon criterion of the 2013 cadre de référence.

    For every village, the largest arc of its horizon free of turbines --
    counting only machines within `radius` -- must stay at or above
    `min_free_deg`.  Each machine occupies the arc its rotor subtends from the
    village centre, so a machine at 1 km with a 150 m rotor closes 8.6 degrees
    and the same machine at 4 km closes 2.1.

    The test is applied forward: a candidate farm is asked whether admitting it
    would take any village below the threshold, and refused if it would.  That
    is cheaper than placing everything and repairing afterwards, and it matches
    how the criterion is actually used -- a project is assessed against what is
    already standing.
    """

    def __init__(self, centres, rotor_diameter, radius, min_free_deg):
        self.xy = centres
        self.tree = cKDTree(centres) if len(centres) else None
        self.r = rotor_diameter / 2.0
        self.radius = radius
        self.min_free = np.deg2rad(min_free_deg)
        # Occupied arcs per village, as a list of (start, end) in radians.
        self.arcs = [[] for _ in range(len(centres))]

    @staticmethod
    def _largest_gap(arcs):
        """Largest turbine-free arc, in radians, given occupied arcs."""
        if not arcs:
            return 2 * np.pi
        a = sorted(arcs)
        merged = [list(a[0])]
        for s, e in a[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        # The circle wraps: the gap between the last end and the first start
        # crosses 2*pi.
        gaps = [merged[0][0] + 2 * np.pi - merged[-1][1]]
        gaps += [merged[i + 1][0] - merged[i][1] for i in range(len(merged) - 1)]
        return max(gaps)

    def _arcs_for(self, village, tx, ty):
        cx, cy = self.xy[village]
        dx, dy = tx - cx, ty - cy
        dist = np.hypot(dx, dy)
        near = dist <= self.radius
        if not near.any():
            return []
        dist = np.maximum(dist[near], self.r)
        bearing = np.arctan2(dy[near], dx[near]) % (2 * np.pi)
        half = np.arcsin(np.clip(self.r / dist, 0, 1))
        out = []
        for b, h in zip(bearing, half):
            s, e = b - h, b + h
            if s < 0:                     # split an arc that crosses 0
                out.append((s + 2 * np.pi, 2 * np.pi))
                out.append((0.0, e))
            elif e > 2 * np.pi:
                out.append((s, 2 * np.pi))
                out.append((0.0, e - 2 * np.pi))
            else:
                out.append((s, e))
        return out

    def accepts(self, tx, ty):
        """Would these machines keep every village above the threshold?"""
        if self.tree is None or len(tx) == 0:
            return True, {}
        villages = set()
        for x, y in zip(tx, ty):
            villages.update(self.tree.query_ball_point([x, y], self.radius))
        proposed = {}
        for v in villages:
            new = self._arcs_for(v, tx, ty)
            if not new:
                continue
            combined = self.arcs[v] + new
            if self._largest_gap(combined) < self.min_free:
                return False, {}
            proposed[v] = combined
        return True, proposed

    def commit(self, proposed):
        for v, arcs in proposed.items():
            self.arcs[v] = arcs


def allocate_farms(
    xs,
    ys,
    tree,
    land_score,
    min_turbine_distance,
    interfarm,
    radius,
    min_turbines,
    horizon=None,
):
    """
    Two-level allocation: farm sites first, machines inside them afterwards.

    Candidate farm centres are the eligible cells, taken in decreasing order of
    how much eligible land lies within `radius` of them, so that the allocation
    settles on the parts of the Region that can actually hold a farm.  A
    candidate is committed only if it is at least `interfarm` from every
    committed centre, its own disc yields at least `min_turbines` machines, and
    -- when `horizon` is given -- admitting it leaves every village its open
    horizon.  A candidate that fails any of those is skipped without blocking
    anything, so a poor site does not sterilise a good one next to it.
    """
    order = np.argsort(-land_score, kind="stable")
    centres = []
    centre_buckets = {}
    turbine_idx = []
    farm_id = []
    refused_horizon = 0

    for i in order:
        if land_score[i] <= 0:
            break
        cx, cy = xs[i], ys[i]
        bx, by = int(cx // interfarm), int(cy // interfarm)
        clash = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py) in centre_buckets.get((bx + dx, by + dy), ()):
                    if (px - cx) ** 2 + (py - cy) ** 2 < interfarm * interfarm:
                        clash = True
                        break
                if clash:
                    break
            if clash:
                break
        if clash:
            continue

        members = np.asarray(tree.query_ball_point([cx, cy], radius), dtype=np.int64)
        if len(members) < min_turbines:
            continue
        # Fill the farm from its centre outwards: a real layout starts at the
        # best part of the site and works out.
        d = (xs[members] - cx) ** 2 + (ys[members] - cy) ** 2
        local = members[np.argsort(d, kind="stable")]
        keep = allocate(xs[local], ys[local], min_turbine_distance, np.arange(len(local)))
        if keep.sum() < min_turbines:
            continue
        tx, ty = xs[local[keep]], ys[local[keep]]
        if horizon is not None:
            ok, proposed = horizon.accepts(tx, ty)
            if not ok:
                refused_horizon += 1
                continue
            horizon.commit(proposed)
        centre_buckets.setdefault((bx, by), []).append((cx, cy))
        fid = len(centres)
        centres.append((cx, cy, int(keep.sum())))
        turbine_idx.extend(local[keep].tolist())
        farm_id.extend([fid] * int(keep.sum()))

    return (
        np.asarray(turbine_idx, dtype=np.int64),
        np.asarray(farm_id),
        centres,
        refused_horizon,
    )


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.config
    turbine_key = snakemake.wildcards.turbine
    turbine = cfg["turbines"][turbine_key]
    D = float(turbine["rotor_diameter"])
    p_nom = float(turbine["p_nom"])
    crs = cfg["atlite"]["crs"]
    pcfg = cfg["placement"]
    fcfg = pcfg["farm"]
    lcfg = pcfg["landscape"]

    with rasterio.open(snakemake.input.raster) as src:
        mask = src.read(1).astype(bool)
        transform = src.transform
        res = abs(transform.a)

    rows, cols = np.nonzero(mask)
    # Cell centres in the equal-area working CRS.
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e
    area_km2 = len(rows) * res * res / 1e6
    logger.info("%d eligible cells, %.1f km2", len(rows), area_km2)

    settlements = gpd.read_file(snakemake.input.settlements, layer="settlements")
    settle_xy = np.c_[settlements.geometry.x, settlements.geometry.y]
    logger.info("%d settlements for the open-horizon test", len(settle_xy))

    spacings = {k: float(v) * D for k, v in pcfg["spacings_rotor_diameters"].items()}
    radius = float(fcfg["radius_m"])
    link = 2.0 * radius
    min_turbines = int(fcfg["min_turbines"])

    rng = np.random.default_rng(SEED)
    orders = {"row_major": np.arange(len(rows)), "random": rng.permutation(len(rows))}

    # How much eligible land lies within the farm radius of each cell.  A box
    # filter of the mask is within a few per cent of a disc at this radius and
    # costs one pass instead of a convolution.
    win = int(2 * radius / res) | 1
    land_score = uniform_filter(mask.astype(np.float32), size=win, mode="constant")[
        rows, cols
    ] * win * win
    tree = cKDTree(np.c_[xs, ys])

    records = []
    geoms = {}

    def record(model, sname, dist, variant, n, n_farms=None, per_farm=None, extra=None):
        cap = n * p_nom
        rec = {
            "turbine": turbine_key,
            "turbine_label": turbine["label"],
            "model": model,
            "spacing_case": sname,
            "min_distance_m": round(dist, 1),
            "min_distance_rotor_diameters": round(dist / D, 2),
            "variant": variant,
            "interfarm_distance_m": extra,
            "eligible_area_km2": round(area_km2, 2),
            "n_farms": n_farms,
            "turbines_per_farm": per_farm,
            "n_turbines": int(n),
            "p_nom_max_mw": round(cap, 0),
            "effective_density_mw_km2": round(cap / area_km2, 3),
            "land_per_turbine_km2": round(area_km2 / max(n, 1), 4),
        }
        records.append(rec)
        logger.info(
            "%-12s %-10s d=%.0f m (%.1f D) %-14s -> %5d machines, %6.0f MW",
            model,
            sname,
            dist,
            dist / D,
            variant,
            n,
            cap,
        )
        return rec

    # ------------------------------------------------------------------
    # 1. free, and 2. grouped
    # ------------------------------------------------------------------
    for sname, dist in spacings.items():
        for oname, order in orders.items():
            keep = allocate(xs, ys, dist, order)
            record("free", sname, dist, oname, int(keep.sum()))
            if oname != "row_major":
                continue
            gx, gy = xs[keep], ys[keep]
            big, labels = group(gx, gy, link, min_turbines)
            sizes = np.bincount(labels)
            n_farms = int((sizes >= min_turbines).sum())
            record(
                "grouped",
                sname,
                dist,
                "row_major",
                int(big.sum()),
                n_farms=n_farms,
                per_farm=round(float(big.sum()) / max(n_farms, 1), 1),
            )
            geoms[f"free_{sname}"] = (gx, gy, np.full(len(gx), -1))
            geoms[f"grouped_{sname}"] = (gx[big], gy[big], labels[big])

    # ------------------------------------------------------------------
    # 3. farm, and 4. farm + open horizon
    # ------------------------------------------------------------------
    interfarm = [float(d) for d in fcfg["interfarm_distance_m"]]
    ref_ifd = float(fcfg["reference_interfarm_distance_m"])
    for sname, dist in spacings.items():
        for ifd in interfarm:
            for with_h in (False, True):
                horizon = (
                    OpenHorizon(
                        settle_xy,
                        D,
                        float(lcfg["horizon_radius_m"]),
                        float(lcfg["min_free_azimuth_deg"]),
                    )
                    if with_h
                    else None
                )
                idx, fid, centres, refused = allocate_farms(
                    xs, ys, tree, land_score, dist, ifd, radius, min_turbines, horizon
                )
                n = len(idx)
                rec = record(
                    "farm+horizon" if with_h else "farm",
                    sname,
                    dist,
                    f"{ifd / 1000:.1f} km apart",
                    n,
                    n_farms=len(centres),
                    per_farm=round(n / max(len(centres), 1), 1),
                    extra=ifd,
                )
                rec["farms_refused_by_horizon"] = refused if with_h else None
                if ifd == ref_ifd:
                    tag = "farm_horizon" if with_h else "farm"
                    geoms[f"{tag}_{sname}"] = (xs[idx], ys[idx], fid)

    df = pd.DataFrame(records)
    Path(snakemake.output.table).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(snakemake.output.table, index=False)

    out = Path(snakemake.output.points)
    if out.exists():
        out.unlink()
    for name, (gx, gy, fid) in geoms.items():
        gpd.GeoDataFrame(
            {"turbine": turbine_key, "farm": fid},
            geometry=gpd.points_from_xy(gx, gy),
            crs=crs,
            index=range(len(gx)),
        ).to_file(out, driver="GPKG", layer=name)
    logger.info("wrote %s", snakemake.output.table)
