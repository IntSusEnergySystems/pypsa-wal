# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Machine and park allocation on an eligible raster, shared by
``place_turbines.py``, ``sensitivity.py``, ``bregilab_emulation.py`` and
``validate_fleet.py``.

``allocate_free``
    Greedy minimum-distance allocation over the eligible cells: a cell takes a
    machine when no machine already placed is closer than ``spacing``.  This is
    the land-and-wake bound, and it is the quantity the VITO Dynamic Energy
    Atlas (BREGILAB) reports.

``grow_parks``
    Parks grown machine by machine from seed cells ranked by how much eligible
    land surrounds them, under explicit rules only:

    * wake spacing: no two machines closer than ``spacing``, whatever park they
      belong to;
    * park: a machine within ``link`` of a park machine belongs to that park
      (the single-linkage distance used to group the standing fleet), and a
      park is kept only if it reaches ``n_min`` machines;
    * open horizon (optional): every village keeps a turbine-free arc of at
      least ``min_free_deg`` within ``radius``, each machine occupying the arc
      its rotor subtends;
    * inter-distance (optional): no machine closer than ``interdistance`` to a
      machine of another park -- the distance between the nearest masts of two
      parks, which is how the Region measures it -- unless both machines stand
      along a motorway.

    Nothing else constrains the layout.  There is no farm radius and no
    centre-to-centre separation, so no land is lost in the gaps between discs.
    Growth is nearest-first from the seed, so parks come out compact.

``place_parks``
    The park rule of the Cadre 2024 (§3.1): parks of at least ``n_min`` first,
    then, under its exception for machines above 3.2 MW, smaller groups on the
    land no park can use.

``check_layout``
    Verifies a layout against the rules it claims to satisfy, independently of
    the code that produced it.
"""

import heapq

import numpy as np
from scipy.spatial import cKDTree


class Buckets:
    """Uniform grid of points for fixed-radius neighbour queries."""

    def __init__(self, size):
        self.size = float(size)
        self.b = {}

    def add(self, x, y, payload=None):
        self.b.setdefault((int(x // self.size), int(y // self.size)), []).append((x, y, payload))

    def near(self, x, y, r):
        """Payloads within r of (x, y); r must not exceed the bucket size."""
        bx, by = int(x // self.size), int(y // self.size)
        r2 = r * r
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for px, py, pl in self.b.get((bx + dx, by + dy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < r2:
                        yield pl

    def any_near(self, x, y, r):
        return next(self.near(x, y, r), False) is not False


def allocate_free(xs, ys, spacing, order=None, preplaced=None):
    """Boolean mask of the cells that take a machine; `preplaced` block but are not counted."""
    b = Buckets(spacing)
    for x, y in preplaced if preplaced is not None else ():
        b.add(x, y, -1)
    keep = np.zeros(len(xs), dtype=bool)
    for i in order if order is not None else range(len(xs)):
        x, y = xs[i], ys[i]
        if b.any_near(x, y, spacing):
            continue
        b.add(x, y, i)
        keep[i] = True
    return keep


class Horizon:
    """
    The open-horizon rule: "un angle horizontal de 130° sans éoliennes est
    préservé sur une distance de 4 kilomètres" for every village.
    """

    def __init__(self, centres, rotor_diameter, radius, min_free_deg):
        self.xy = np.asarray(centres, dtype=float).reshape(-1, 2)
        self.tree = cKDTree(self.xy) if len(self.xy) else None
        self.r = rotor_diameter / 2.0
        self.radius = float(radius)
        self.min_free = np.deg2rad(min_free_deg)
        self.arcs = [[] for _ in range(len(self.xy))]

    def arc(self, v, x, y):
        cx, cy = self.xy[v]
        d = max(np.hypot(x - cx, y - cy), self.r)
        b = np.arctan2(y - cy, x - cx) % (2 * np.pi)
        h = np.arcsin(min(self.r / d, 1.0))
        s, e = b - h, b + h
        if s < 0:
            return [(s + 2 * np.pi, 2 * np.pi), (0.0, e)]
        if e > 2 * np.pi:
            return [(s, 2 * np.pi), (0.0, e - 2 * np.pi)]
        return [(s, e)]

    @staticmethod
    def largest_gap(arcs):
        """Largest turbine-free arc, in radians, given occupied arcs."""
        if not arcs:
            return 2 * np.pi
        a = sorted(arcs)
        ms, me = a[0]
        merged = []
        for s, e in a[1:]:
            if s <= me:
                me = max(me, e)
            else:
                merged.append((ms, me))
                ms, me = s, e
        merged.append((ms, me))
        gaps = [merged[0][0] + 2 * np.pi - merged[-1][1]]
        gaps += [merged[i + 1][0] - merged[i][1] for i in range(len(merged) - 1)]
        return max(gaps)

    def ok(self, x, y, tentative):
        """Would a machine at (x, y) keep every village at or above the threshold?"""
        if self.tree is None:
            return True, {}
        new = {}
        for v in self.tree.query_ball_point([x, y], self.radius):
            a = self.arc(v, x, y)
            if self.largest_gap(self.arcs[v] + tentative.get(v, []) + a) < self.min_free:
                return False, None
            new[v] = a
        return True, new

    def commit(self, arcs):
        for v, a in arcs.items():
            self.arcs[v].extend(a)


def seed_scores(mask, rows, cols, res, seed_radius):
    """Eligible cells within a square window of +/- seed_radius around each cell."""
    from scipy.ndimage import uniform_filter

    win = int(2 * seed_radius / res) | 1
    return uniform_filter(mask.astype(np.float32), size=win, mode="constant")[rows, cols] * win * win


def grow_parks(xs, ys, score, spacing, link=1500.0, n_min=4, horizon=None,
               interdistance=0.0, along_motorway=None, tree=None, preplaced=None,
               excluded=None):
    """
    Returns (turbine cell indices, park id of each, number of placements the
    open-horizon rule refused).

    ``preplaced`` -- (x, y, along_motorway) arrays of machines already standing
    (a first pass): they block wake spacing and inter-distance but are not
    returned.  With the same ``horizon`` object, their arcs are already
    committed.
    """
    n = len(xs)
    tree = tree if tree is not None else cKDTree(np.c_[xs, ys])
    amw = along_motorway if along_motorway is not None else np.zeros(n, dtype=bool)
    placed = Buckets(spacing)
    others = Buckets(max(interdistance, spacing))
    if preplaced is not None:
        for x, y, mw in zip(*preplaced):
            placed.add(x, y, -1)
            others.add(x, y, bool(mw))
    considered = np.zeros(n, dtype=bool)
    blocked = np.zeros(n, dtype=bool) if excluded is None else np.asarray(excluded, dtype=bool)
    turbines, parks = [], []
    refused = 0
    pid = 0

    def too_close_to_other_park(x, y, mw):
        if interdistance <= 0:
            return False
        return any(not (mw and f) for f in others.near(x, y, interdistance))

    for s in np.argsort(-score, kind="stable"):
        if considered[s] or blocked[s] or score[s] <= 0:
            continue
        x0, y0 = xs[s], ys[s]
        if placed.any_near(x0, y0, spacing) or too_close_to_other_park(x0, y0, amw[s]):
            considered[s] = True
            continue
        members, own = [], Buckets(spacing)
        arcs = {}
        heap = [(0.0, s)]
        seen = {s}
        while heap:
            _, c = heapq.heappop(heap)
            if blocked[c]:
                continue
            x, y = xs[c], ys[c]
            if placed.any_near(x, y, spacing) or own.any_near(x, y, spacing):
                continue
            if too_close_to_other_park(x, y, amw[c]):
                continue
            if horizon is not None:
                ok, new = horizon.ok(x, y, arcs)
                if not ok:
                    refused += 1
                    continue
                for v, a in new.items():
                    arcs.setdefault(v, []).extend(a)
            members.append(c)
            own.add(x, y, c)
            for m in tree.query_ball_point([x, y], link):
                if m not in seen:
                    seen.add(m)
                    heapq.heappush(heap, ((xs[m] - x0) ** 2 + (ys[m] - y0) ** 2, m))
        if len(members) >= n_min:
            for c in members:
                placed.add(xs[c], ys[c], c)
                others.add(xs[c], ys[c], bool(amw[c]))
            turbines.extend(members)
            parks.extend([pid] * len(members))
            if horizon is not None:
                horizon.commit(arcs)
            considered[list(seen)] = True
            pid += 1
        else:
            considered[s] = True
    return np.asarray(turbines, dtype=np.int64), np.asarray(parks, dtype=np.int64), refused


def place_parks(xs, ys, score, spacing, link=1500.0, n_min=4, small_groups="after", horizon=None,
                interdistance=0.0, along_motorway=None, tree=None):
    """
    The park rule of the Cadre 2024, §3.1: a park is at least ``n_min``
    machines, and the minimum may be reduced for machines above 3.2 MW "pour
    autant qu'il [...] ne réduise pas le potentiel éolien de la zone" (4°).

    ``small_groups="after"`` reads that condition literally: parks of at least
    ``n_min`` are grown first, then groups below ``n_min`` -- down to a single
    machine -- only on the land no park could use, under the same spacing,
    horizon (the same ``horizon`` object, so the first pass's arcs stand) and
    inter-distance.  ``"none"`` is the minimum without its exceptions.

    Returns (turbine cell indices, park id of each, placements the open-horizon
    rule refused), like ``grow_parks``.
    """
    tree = tree if tree is not None else cKDTree(np.c_[xs, ys])
    kw = dict(link=link, horizon=horizon, interdistance=interdistance,
              along_motorway=along_motorway, tree=tree)
    idx, pid, refused = grow_parks(xs, ys, score, spacing, n_min=n_min, **kw)
    if small_groups == "none":
        return idx, pid, refused
    if small_groups != "after":
        raise ValueError(f"small_groups must be 'after' or 'none', not {small_groups!r}")
    # Cells within `link` of a park already kept belong to that park.  The
    # second pass must not open a new group on them: that would split one
    # park into two and would use land the first pass could have used.
    excluded = np.zeros(len(xs), dtype=bool)
    if len(idx):
        for nbrs in tree.query_ball_point(np.c_[xs[idx], ys[idx]], link):
            excluded[nbrs] = True
    amw = along_motorway if along_motorway is not None else np.zeros(len(xs), dtype=bool)
    i2, p2, r2 = grow_parks(xs, ys, score, spacing, n_min=1, excluded=excluded,
                            preplaced=(xs[idx], ys[idx], amw[idx]), **kw)
    offset = int(pid.max()) + 1 if len(pid) else 0
    return np.r_[idx, i2].astype(np.int64), np.r_[pid, p2 + offset].astype(np.int64), refused + r2


def min_group(n_min, small_groups):
    """The smallest group a layout under this park rule may contain."""
    return 1 if small_groups == "after" else n_min


def largest_free_arc_deg(vx, vy, tx, ty, rotor_radius, radius):
    """Independent implementation of the open-horizon measure, for checking."""
    d = np.hypot(tx - vx, ty - vy)
    near = d <= radius
    if not near.any():
        return 360.0
    d = np.maximum(d[near], rotor_radius)
    b = np.arctan2(ty[near] - vy, tx[near] - vx) % (2 * np.pi)
    h = np.arcsin(np.clip(rotor_radius / d, 0, 1))
    iv = []
    for bb, hh in zip(b, h):
        s, e = bb - hh, bb + hh
        if s < 0:
            iv += [(s + 2 * np.pi, 2 * np.pi), (0.0, e)]
        elif e > 2 * np.pi:
            iv += [(s, 2 * np.pi), (0.0, e - 2 * np.pi)]
        else:
            iv.append((s, e))
    iv.sort()
    merged = [list(iv[0])]
    for s, e in iv[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    gaps = [merged[0][0] + 2 * np.pi - merged[-1][1]]
    gaps += [merged[i + 1][0] - merged[i][1] for i in range(len(merged) - 1)]
    return float(np.rad2deg(max(gaps)))


def check_layout(tx, ty, park, spacing, n_min=1, villages=None, rotor_diameter=None,
                 radius=4000.0, min_free_deg=130.0, interdistance=0.0, along_motorway=None):
    """Measure a layout against its rules.  Returns a dict; `ok` is the verdict."""
    out = {"n": int(len(tx))}
    if len(tx) == 0:
        out["ok"] = True
        return out
    t = cKDTree(np.c_[tx, ty])
    nn = t.query(np.c_[tx, ty], k=2)[0][:, 1] if len(tx) > 1 else np.array([np.inf])
    out["min_spacing_m"] = round(float(nn.min()), 1)
    ok = bool(nn.min() >= spacing - 1e-6)
    sizes = np.bincount(park)
    out["min_park_size"] = int(sizes[sizes > 0].min())
    ok &= out["min_park_size"] >= n_min
    if interdistance > 0:
        viol = 0
        for i, j in t.query_pairs(interdistance - 1e-6):
            if park[i] != park[j] and not (
                along_motorway is not None and along_motorway[i] and along_motorway[j]
            ):
                viol += 1
        out["interdistance_violations"] = viol
        ok &= viol == 0
    if villages is not None and len(villages):
        vt = cKDTree(villages)
        near = set(j for lst in vt.query_ball_point(np.c_[tx, ty], radius) for j in lst)
        gaps = [largest_free_arc_deg(villages[v, 0], villages[v, 1], tx, ty,
                                     rotor_diameter / 2.0, radius) for v in near]
        out["worst_free_arc_deg"] = round(min(gaps), 1) if gaps else 360.0
        out["villages_below_threshold"] = int(sum(g < min_free_deg - 1e-6 for g in gaps))
        ok &= out["villages_below_threshold"] == 0
    out["ok"] = bool(ok)
    return out


def motorway_distance(shape, transform, lines, res):
    """Distance, in metres, from every raster cell to the nearest motorway."""
    from rasterio.features import rasterize
    from scipy.ndimage import distance_transform_edt

    geoms = [(g, 1) for g in lines if g is not None and not g.is_empty]
    if not geoms:
        return np.full(shape, np.inf)
    burnt = rasterize(geoms, out_shape=shape, transform=transform, fill=0, all_touched=True)
    return distance_transform_edt(~burnt.astype(bool), sampling=res)
