# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
The picture on each card of the infographic: a real Walloon orthophoto (SPW,
summer 2023: the 2025 summer campaign only covers the south-east of the
Region) with the rule drawn over it from the workflow's own layers and
placement results, or a ground photograph dropped into ``infographic/photos/``.

For every vignette the script scores candidate windows on the 100 m grid --
where the rule is most visible -- and draws the best one, unless
``config.infographic.vignettes.<name>.centre`` fixes it.  The three best
candidates of each are written to ``vignette_candidates.json`` and drawn side
by side in ``vignette_candidates.jpg``, so that the final choice is made by
eye.  No place name is written on a vignette.

The orthophotos are fetched once through the service's ``export`` operation
and cached in ``resources/infographic_ortho/``.  Their use is governed by the
SPW's conditions for its viewing services, not by CC BY: see the catalogue
record of ``IMAGERIE/ORTHO_2023_ETE``.
"""

import hashlib
import json
import logging
import sys
from io import BytesIO
from pathlib import Path

# rasterio before geopandas: see retrieve_slope_raster.py.
import rasterio
import rasterio.transform
import rasterio.warp
import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import requests  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, Wedge  # noqa: E402
from PIL import Image, ImageEnhance, ImageOps  # noqa: E402
from rasterio.features import rasterize, shapes  # noqa: E402
from scipy.ndimage import uniform_filter  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from shapely.geometry import MultiPolygon, Point, box, shape  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from placement_lib import largest_free_arc_deg  # noqa: E402

logger = logging.getLogger(__name__)

ORTHO = "https://geoservices.wallonie.be/arcgis/rest/services/IMAGERIE/ORTHO_2023_ETE/MapServer/export"
W_PX, H_PX = 1200, 900
GREEN = "#2B8A3E"
FAMILY = [None, "#C4AC8E", "#E9E196", "#A780AD", "#3A70AD", "#513249"]
INK = "#1D2428"
FONT_DIR = Path("/usr/share/fonts/opentype/inter")


def font(weight="SemiBold", size=34):
    path = FONT_DIR / f"Inter-{weight}.otf"
    if path.exists():
        return font_manager.FontProperties(fname=str(path), size=size)
    return font_manager.FontProperties(weight="bold", size=size)


def decode_points(b64):
    import base64

    a = np.frombuffer(base64.b64decode(b64), dtype="<u2").reshape(-1, 3)
    return a[:, 0].astype(int), a[:, 1].astype(int), a[:, 2].astype(int)


class Grid:
    def __init__(self, meta):
        g = meta["grid"]
        self.x0, self.y0, self.res = g["x0"], g["y0"], g["res_m"]
        self.rows, self.cols = g["rows"], g["cols"]
        self.transform = rasterio.transform.from_origin(self.x0, self.y0, self.res, self.res)

    def xy(self, r, c):
        return self.x0 + (np.asarray(c) + 0.5) * self.res, self.y0 - (np.asarray(r) + 0.5) * self.res

    def rc(self, x, y):
        return int((self.y0 - y) // self.res), int((x - self.x0) // self.res)

    def burn(self, geoms):
        geoms = [g for g in geoms if g is not None and not g.is_empty]
        if not geoms:
            return np.zeros((self.rows, self.cols), dtype=bool)
        return rasterize(geoms, out_shape=(self.rows, self.cols), transform=self.transform,
                         all_touched=True).astype(bool)


def window_sum(a, h, w):
    """Mean of `a` over every h x w window, centred on each cell."""
    return uniform_filter(a.astype(np.float32), size=(h, w), mode="constant")


def best_windows(score, h, w, n=3):
    """The n best window centres, not overlapping."""
    s = score.copy()
    out = []
    for _ in range(n):
        i = int(np.nanargmax(s))
        if not np.isfinite(s.flat[i]) or s.flat[i] <= 0:
            break
        r, c = divmod(i, s.shape[1])
        out.append((r, c, float(s[r, c])))
        s[max(0, r - h):r + h, max(0, c - w):c + w] = -np.inf
    return out


def ortho(bbox, cache):
    key = hashlib.sha1(json.dumps([ORTHO] + [round(v) for v in bbox]).encode()).hexdigest()[:16]
    path = cache / f"{key}.jpg"
    if not path.exists():
        params = {
            "bbox": ",".join(str(round(v)) for v in bbox),
            "bboxSR": 3035, "imageSR": 3035,
            "size": f"{W_PX},{H_PX}", "format": "jpg", "transparent": "false", "f": "image",
        }
        for attempt in range(3):
            r = requests.get(ORTHO, params=params, timeout=120)
            if r.ok and r.headers.get("content-type", "").startswith("image") and len(r.content) > 60000:
                break
            logger.warning("ortho export failed (%s), retrying", r.status_code)
        r.raise_for_status()
        path.write_bytes(r.content)
    img = Image.open(path).convert("RGB")
    # The series treatment: slightly desaturated, slightly lifted.
    img = ImageEnhance.Color(img).enhance(0.72)
    img = ImageEnhance.Brightness(img).enhance(1.04)
    return img


class Canvas:
    """A 1200 x 900 figure in map coordinates."""

    def __init__(self, img, bbox):
        self.bbox = bbox
        self.fig = plt.figure(figsize=(W_PX / 100, H_PX / 100), dpi=100)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        x0, y0, x1, y1 = bbox
        self.ax.imshow(img, extent=(x0, x1, y0, y1), interpolation="lanczos")
        self.ax.set_xlim(x0, x1)
        self.ax.set_ylim(y0, y1)
        self.ax.set_axis_off()
        self.m_per_px = (x1 - x0) / W_PX
        self.boxes = []

    def free(self, x, y, text, size):
        """Is there room for a label here (approximate box, map units)?"""
        w = 0.62 * size * len(text) * self.m_per_px + 30 * self.m_per_px
        h = 1.9 * size * self.m_per_px
        b = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        x0, y0, x1, y1 = self.bbox
        if b[0] < x0 or b[2] > x1 or b[1] < y0 or b[3] > y1:
            return None
        if any(not (b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3]) for o in self.boxes):
            return None
        return b

    def place(self, candidates, text, size=34):
        """Label at the first candidate point with room; returns it or None."""
        for p in candidates:
            b = self.free(p.x, p.y, text, size)
            if b is not None:
                self.boxes.append(b)
                self.label(p.x, p.y, text, size=size)
                return p
        return None

    def poly(self, geom, **kw):
        if geom is None or geom.is_empty:
            return
        gpd.GeoSeries([geom]).plot(ax=self.ax, **kw)

    def label(self, x, y, text, size=36, ha="center", va="center", **kw):
        self.ax.text(x, y, text, fontproperties=font("SemiBold", size), ha=ha, va=va, color=INK,
                     zorder=20, bbox=dict(boxstyle="round,pad=0.32,rounding_size=0.5", fc="white",
                                          ec="none", alpha=0.93), **kw)

    def arrow(self, p0, p1, both=True):
        style = "<|-|>" if both else "-|>"
        for lw, col in ((7, "white"), (3, INK)):
            self.ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=26 if lw == 3 else 34,
                                              lw=lw, color=col, zorder=18, shrinkA=0, shrinkB=0))

    def turbines(self, xs, ys, r_px=13):
        r = r_px * self.m_per_px
        for x, y in zip(xs, ys):
            self.ax.add_patch(Circle((x, y), r * 1.35, fc="white", ec="none", zorder=15))
            self.ax.add_patch(Circle((x, y), r, fc=INK, ec="none", zorder=16))

    def crosses(self, xs, ys, r_px=15):
        r = r_px * self.m_per_px
        for x, y in zip(xs, ys):
            for lw, col in ((9, "white"), (4.5, INK)):
                self.ax.plot([x - r, x + r], [y - r, y + r], color=col, lw=lw, zorder=17, solid_capstyle="round")
                self.ax.plot([x - r, x + r], [y + r, y - r], color=col, lw=lw, zorder=17, solid_capstyle="round")

    def save(self, dst):
        buf = BytesIO()
        self.fig.savefig(buf, format="png", dpi=100)
        plt.close(self.fig)
        buf.seek(0)
        Image.open(buf).convert("RGB").save(dst, format="JPEG", quality=86, optimize=True, progressive=True)


def mask_polys(mask, grid, bbox):
    """Vectorise a 100 m mask inside a bbox."""
    r0, c0 = grid.rc(bbox[0], bbox[3])
    r1, c1 = grid.rc(bbox[2], bbox[1])
    r0, c0 = max(r0, 0), max(c0, 0)
    sub = mask[r0:r1 + 1, c0:c1 + 1].astype(np.uint8)
    t = rasterio.transform.from_origin(grid.x0 + c0 * grid.res, grid.y0 - r0 * grid.res, grid.res, grid.res)
    geoms = [shape(g) for g, v in shapes(sub, mask=sub.astype(bool), transform=t) if v == 1]
    return unary_union(geoms).intersection(box(*bbox)) if geoms else None


def hull_polys(xs, ys, pid, pad):
    out = []
    for p in np.unique(pid):
        m = pid == p
        pts = [Point(x, y) for x, y in zip(xs[m], ys[m])]
        out.append(unary_union(pts).convex_hull.buffer(pad))
    return out


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )
    cfg = snakemake.params.config
    vcfg = (cfg["infographic"].get("vignettes") or {})
    crs = cfg["atlite"]["crs"]
    out_dir = Path(snakemake.output.done).parent
    Path(snakemake.output.candidates).parent.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = Path(snakemake.params.cache)
    cache.mkdir(parents=True, exist_ok=True)

    states = json.loads(Path(snakemake.input.states).read_text())
    meta = states["meta"]
    grid = Grid(meta)
    R = meta["rules"]
    pts_raw = json.loads(Path(snakemake.input.points).read_text())
    fam = np.array(Image.open(snakemake.input.attribution)) // meta["grid"]["scale"]
    region = fam < 6

    def load(path, **kw):
        return gpd.read_file(path, **kw).to_crs(crs)

    zones = load(snakemake.input.pds_zones)
    zones["DESCRIPTION"] = zones["DESCRIPTION"].astype(str).str.strip()
    pcfg = cfg["plan_de_secteur"]
    habitat = zones[zones["DESCRIPTION"].isin(pcfg["habitat_zones"])]
    forest = zones[zones["DESCRIPTION"] == "Forestière"]
    agri = zones[zones["DESCRIPTION"].isin(pcfg["eligible_conditional_agriculture"])]
    zae = zones[zones["DESCRIPTION"].isin(pcfg["economic_activity_zones"])]
    roads = load(snakemake.input.pds_roads)
    motorways = roads[roads["DESCRIPTION"] == "Autoroute existante"]
    rail = load(snakemake.input.pds_rail)
    hv = load(snakemake.input.pds_hv_lines)
    natura = load(snakemake.input.natura2000)
    fleet = load(snakemake.input.fleet)
    f1_layer = gpd.read_file(Path(snakemake.input.layer_dir) / "pds_ineligible_nocorridor.gpkg").to_crs(crs)
    f1_layer = f1_layer.explode(index_parts=False)
    villages = gpd.read_file(snakemake.input.settlements, layer="settlements")
    vxy = np.c_[villages.geometry.x, villages.geometry.y]
    with rasterio.open(snakemake.input.slope) as src:
        slope = np.zeros((grid.rows, grid.cols), dtype=np.uint8)
        rasterio.warp.reproject(rasterio.band(src, 1), slope, dst_transform=grid.transform,
                                dst_crs=f"EPSG:{crs}", src_nodata=255, dst_nodata=0,
                                resampling=rasterio.warp.Resampling.max)
    slope = slope == 1
    logger.info("layers loaded")

    g_hab = grid.burn(habitat.geometry)
    g_for = grid.burn(forest.geometry)
    g_mw = grid.burn(motorways.geometry)
    g_rail = grid.burn(rail.geometry)
    g_hv = grid.burn(hv.geometry)
    g_nat = grid.burn(natura.geometry)

    def rc_bbox(r, c, w_m, h_m):
        x, y = grid.xy(r, c)
        return (float(x - w_m / 2), float(y - h_m / 2), float(x + w_m / 2), float(y + h_m / 2))

    def pts(key):
        r, c, p = decode_points(pts_raw[key])
        x, y = grid.xy(r, c)
        return x, y, p

    # ------------------------------------------------------------------
    # Candidate windows, one scoring rule per vignette
    # ------------------------------------------------------------------
    specs = {}

    def cells(w_m, h_m):
        return max(3, int(h_m / grid.res)), max(3, int(w_m / grid.res))

    # 1. Villes, forêts, parcs: a village edge against forest.
    h, w = cells(3000, 2250 * 1.0)
    f1 = window_sum(fam == 1, *cells(3000, 2250))
    s = (1 - np.abs(f1 - 0.5) / 0.5) * np.minimum(window_sum(g_hab, h, w) / 0.12, 1) \
        * np.minimum(window_sum(g_for, h, w) / 0.25, 1) * (window_sum(region, h, w) > 0.99)
    specs["etape1"] = (s, 3000, 2250)

    # 2. Près des grands axes: a motorway in open farmland, no railway, the
    # window centred on the motorway so that the band shows on both sides.
    h, w = cells(8000, 6000)
    s = np.minimum(window_sum(fam == 2, h, w) / 0.4, 1) * g_mw \
        * (window_sum(g_rail, h, w) == 0) * np.clip(1 - 4 * window_sum(g_hab, h, w), 0, 1) \
        * (window_sum(region, h, w) > 0.99)
    specs["etape2"] = (s, 8000, 6000)

    # 3. Loin des habitations: a village, isolated farms, and land left.
    h, w = cells(3000, 2250)
    hab = window_sum(g_hab, h, w)
    s = (hab > 0.06) * (hab < 0.22) * np.minimum(window_sum(fam == 3, h, w) / 0.4, 1) \
        * np.minimum(window_sum((fam == 0) | (fam > 3), h, w) / 0.08, 1) \
        * (window_sum(np.isin(fam, (0, 3, 4, 5)), h, w) > 0.55) * (window_sum(region, h, w) > 0.99)
    specs["etape3"] = (s, 3000, 2250)

    # 5. Relief et sécurité: a valley side with a railway and a power line.
    h, w = cells(3000, 2250)
    sl = window_sum(slope, h, w)
    s = (window_sum(g_rail, h, w) > 0.01) * (window_sum(g_hv, h, w) > 0.01) * (sl > 0.12) * (sl < 0.5) \
        * np.minimum(window_sum(fam == 5, h, w) / 0.25, 1) * (window_sum(region, h, w) > 0.99)
    specs["etape5"] = (s, 3000, 2250)

    # 6 and 7. Machines 750 m apart, then parks: where the free allocation is
    # dense and the park rule visibly drops isolated machines.
    fx, fy, _ = pts("free_ref")
    kx, ky, kp = pts("parks_ref_m4")
    free_g = np.zeros((grid.rows, grid.cols), dtype=np.float32)
    r_, c_ = decode_points(pts_raw["free_ref"])[:2]
    free_g[r_, c_] = 1
    park_g = np.zeros_like(free_g)
    r_, c_ = decode_points(pts_raw["parks_ref_m4"])[:2]
    park_g[r_, c_] = 1
    h, w = cells(4000, 3000)
    n_free = window_sum(free_g, h, w) * h * w
    h2, w2 = cells(8000, 6000)
    n_park = window_sum(park_g, h2, w2) * h2 * w2
    n_free2 = window_sum(free_g, h2, w2) * h2 * w2
    s = np.minimum(n_free / 10, 1.5) * np.minimum(n_park / 8, 1) * np.minimum((n_free2 - n_park) / 4, 1) \
        * (window_sum(region, h2, w2) > 0.99)
    specs["etape6"] = (s, 4000, 3000)
    # A park of 4 to 7 machines, compact, with isolated machines of the free
    # allocation dropped within 3 km of it and no other park crowding the frame.
    tf = cKDTree(np.c_[fx, fy])
    tkp = cKDTree(np.c_[kx, ky])
    park_cands = []
    for p in np.unique(kp):
        m = kp == p
        if not 4 <= m.sum() <= 7:
            continue
        cx_, cy_ = kx[m].mean(), ky[m].mean()
        if np.hypot(kx[m] - cx_, ky[m] - cy_).max() > 1600:
            continue
        near_free = tf.query_ball_point([cx_, cy_], 3000)
        d_park, _ = tkp.query(np.c_[fx[near_free], fy[near_free]])
        n_drop = int((d_park > 1500).sum())
        others = [j for j in tkp.query_ball_point([cx_, cy_], 3500) if kp[j] != p]
        if n_drop >= 1:
            park_cands.append((n_drop - 0.3 * len(others) + 0.5 * m.sum(), int(p), cx_, cy_))
    park_cands.sort(reverse=True)

    # 8. Un horizon libre: a village the rule actually protects.
    hx, hy, hp = pts("horizon_ref_m4")
    radius = R["horizon_m"]
    rot = meta["turbine"]["rotor_m"] / 2
    tk, th = cKDTree(np.c_[kx, ky]), cKDTree(np.c_[hx, hy])
    vcand = []
    for i, (vx, vy) in enumerate(vxy):
        near7 = tk.query_ball_point([vx, vy], radius)
        near8 = th.query_ball_point([vx, vy], radius)
        if len(near8) < 6 or len(near7) <= len(near8):
            continue
        a7 = largest_free_arc_deg(vx, vy, kx[near7], ky[near7], rot, radius)
        a8 = largest_free_arc_deg(vx, vy, hx[near8], hy[near8], rot, radius)
        if a7 < R["horizon_deg"] <= a8 < 200:
            vcand.append((len(near8) + (len(near7) - len(near8)) * 0.5, i, a7, a8))
    vcand.sort(reverse=True)

    # 8 bis. Two parks 4 km apart (nearest masts), neither along a motorway.
    ix, iy, ip = pts("inter4_ref_m4")
    pairs = []
    tree = cKDTree(np.c_[ix, iy])
    for a, b in tree.query_pairs(4600):
        if ip[a] == ip[b]:
            continue
        d = float(np.hypot(ix[a] - ix[b], iy[a] - iy[b]))
        pairs.append((d, ip[a], ip[b], a, b))
    best_pair = {}
    for d, pa, pb, a, b in pairs:
        k = (min(pa, pb), max(pa, pb))
        if k not in best_pair or d < best_pair[k][0]:
            best_pair[k] = (d, a, b)
    sizes = np.bincount(ip)
    pcand = sorted(((abs(d - 4200) - 3 * min(sizes[k[0]], sizes[k[1]]), k, a, b, d)
                    for k, (d, a, b) in best_pair.items() if 4000 <= d <= 4600
                    and min(sizes[k[0]], sizes[k[1]]) >= 4), key=lambda t: t[0])

    # 0 (fallback when there is no ground photo): the densest standing park.
    fl = np.zeros_like(free_g)
    for g in fleet.geometry:
        r, c = grid.rc(g.x, g.y)
        if 0 <= r < grid.rows and 0 <= c < grid.cols:
            fl[r, c] = 1
    h, w = cells(4000, 3000)
    s = window_sum(fl, h, w) * (window_sum(fam == 1, h, w) < 0.35) * (window_sum(region, h, w) > 0.99)
    specs["etape0"] = (s, 4000, 3000)

    # 4 (fallback): a Natura 2000 valley.
    h, w = cells(4000, 3000)
    nat = window_sum(g_nat, h, w)
    s = (1 - np.abs(nat - 0.45) / 0.45) * np.minimum(window_sum(g_for, h, w) / 0.3, 1) \
        * np.minimum(window_sum(slope, h, w) / 0.2, 1) * (window_sum(region, h, w) > 0.99)
    specs["etape4"] = (s, 4000, 3000)

    candidates = {}
    for name, (score, w_m, h_m) in specs.items():
        hh, ww = cells(w_m, h_m)
        candidates[name] = [
            {"centre_3035": [float(v) for v in grid.xy(r, c)], "score": round(sc, 3), "size_m": [w_m, h_m]}
            for r, c, sc in best_windows(score, 2 * hh, 2 * ww)
        ]
    candidates["etape7"] = [{"centre_3035": [float(cx_), float(cy_)], "score": round(sc, 2), "size_m": [7000, 5250],
                             "park": p} for sc, p, cx_, cy_ in park_cands[:3]]
    candidates["etape8"] = [{"centre_3035": [float(vxy[i, 0]), float(vxy[i, 1])], "score": round(sc, 1),
                             "size_m": [11200, 8400], "village": int(i), "arc7": a7, "arc8": a8}
                            for sc, i, a7, a8 in vcand[:3]]
    candidates["etape8bis"] = [{"centre_3035": [float((ix[a] + ix[b]) / 2), float((iy[a] + iy[b]) / 2)],
                                "score": round(-sc, 1), "size_m": [12000, 9000], "masts": [int(a), int(b)],
                                "distance_m": round(d)} for sc, k, a, b, d in pcand[:3]]
    Path(snakemake.output.candidates).write_text(json.dumps(candidates, indent=1))
    logger.info("candidates: %s", {k: len(v) for k, v in candidates.items()})

    def chosen(name, default_pick=0):
        c = vcfg.get(name) or {"candidate": default_pick}
        pick = int(c.get("candidate", 0))
        cands = candidates[name]
        if c.get("centre"):
            base = dict(cands[0]) if cands else {"size_m": specs[name][1:]}
            base["centre_3035"] = list(c["centre"])
            return base
        if not cands:
            return None
        return cands[min(pick, len(cands) - 1)]

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def bbox_of(c):
        (x, y), (w_m, h_m) = c["centre_3035"], c["size_m"]
        return (x - w_m / 2, y - h_m / 2, x + w_m / 2, y + h_m / 2)

    def clipped(gdf, bbox):
        sub = gdf.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
        if not len(sub):
            return None
        b = box(*bbox)
        return unary_union([g.intersection(b) for g in sub.geometry.make_valid() if g is not None])

    def draw_etape1(cv, c):
        bb = cv.bbox
        inner = box(bb[0] + 250, bb[1] + 200, bb[2] - 250, bb[3] - 200)
        f1 = clipped(f1_layer, bb)
        cv.poly(f1, fc=FAMILY[1], alpha=0.55, ec="none", zorder=5)
        if f1 is not None:
            gpd.GeoSeries([f1.boundary]).plot(ax=cv.ax, color="white", lw=2.6, zorder=6)

        def biggest(g):
            if g is None or g.is_empty:
                return None
            g = g.intersection(inner)
            parts = [q for q in (list(g.geoms) if hasattr(g, "geoms") else [g]) if q.area > 0]
            return max(parts, key=lambda q: q.area) if parts else None

        for gdf, text, inside in ((habitat, "habitat", True), (forest, "forêt", True), (agri, "zone agricole", False)):
            g = clipped(gdf, bb)
            if g is None or f1 is None:
                continue
            g = g.intersection(f1) if inside else g.difference(f1)
            q = biggest(g)
            if q is not None and q.area > 60000:
                p = q.representative_point()
                cv.label(p.x, p.y, text, size=34)

    def draw_etape2(cv, c):
        bb = cv.bbox
        mw = clipped(motorways, (bb[0] - 3000, bb[1] - 3000, bb[2] + 3000, bb[3] + 3000))
        band = mw.buffer(R["corridor_m"])
        outside = box(*bb).difference(band)
        cv.poly(outside, fc="#1D2428", alpha=0.42, ec="none", zorder=5)
        cv.poly(outside, fc=FAMILY[2], alpha=0.28, ec="none", zorder=6)
        edge = band.boundary.intersection(box(*bb))
        gpd.GeoSeries([edge]).plot(ax=cv.ax, color="white", lw=4, linestyle=(0, (4, 3)), zorder=8)
        mwin = mw.intersection(box(*bb))
        gpd.GeoSeries([mwin]).plot(ax=cv.ax, color=INK, lw=7, zorder=9)
        gpd.GeoSeries([mwin]).plot(ax=cv.ax, color="white", lw=3.5, zorder=10)
        # 1.5 km arrow, perpendicular from the motorway near the window centre
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        from shapely.ops import nearest_points
        p_mw = nearest_points(mw, Point(cx, cy))[0]
        q = nearest_points(edge, p_mw)[0]
        v = np.array([q.x - p_mw.x, q.y - p_mw.y])
        v = v / np.linalg.norm(v) * R["corridor_m"]
        p1 = (p_mw.x + v[0], p_mw.y + v[1])
        cv.arrow((p_mw.x, p_mw.y), p1)
        cv.label((p_mw.x + p1[0]) / 2, (p_mw.y + p1[1]) / 2, "1,5 km", size=38)
        far = mwin.interpolate(0.18, normalized=True)
        cv.label(far.x, far.y, "autoroute", size=30)

    def draw_etape3(cv, c):
        bb = cv.bbox
        big = (bb[0] - 800, bb[1] - 800, bb[2] + 800, bb[3] + 800)
        hab_g = clipped(habitat, big)
        ring = hab_g.buffer(R["habitat_m"]).difference(hab_g) if hab_g is not None else None
        addr = gpd.read_file(snakemake.input.address_points, bbox=tuple(gpd.GeoSeries(
            [box(*big)], crs=crs).to_crs(31370).total_bounds)).to_crs(crs)
        z = clipped(zae, big)
        if z is not None and not z.is_empty:
            addr = addr[~addr.within(z)]
        if hab_g is not None:
            addr = addr[~addr.within(hab_g.buffer(R["habitat_m"]))]
        dw = unary_union(list(addr.geometry.buffer(R["dwelling_m"]))) if len(addr) else None
        cv.poly(ring, fc=FAMILY[3], alpha=0.5, ec="none", zorder=5)
        cv.poly(dw, fc=FAMILY[3], alpha=0.36, ec="none", zorder=5)
        if dw is not None:
            gpd.GeoSeries([dw.boundary]).plot(ax=cv.ax, color="white", lw=2.2, zorder=7)
        if ring is not None:
            gpd.GeoSeries([hab_g.buffer(R["habitat_m"]).boundary]).plot(ax=cv.ax, color="white", lw=3.2, zorder=7)
            cv.poly(hab_g, fc="none", ec="white", lw=2, linestyle=(0, (3, 2)), zorder=7)
        left = mask_polys(((fam == 0) | (fam > 3)) & region, grid, bb)
        cv.poly(left, fc=GREEN, alpha=0.55, ec="#123F1C", lw=1.6, zorder=6)
        # distance labels: from the village edge straight out to its 592 m line
        if hab_g is not None and not hab_g.is_empty:
            from shapely.ops import nearest_points
            parts = list(hab_g.geoms) if isinstance(hab_g, MultiPolygon) else [hab_g]
            cen = Point((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
            vil = min((p for p in parts if p.intersects(box(*bb))), key=lambda p: p.distance(cen), default=None)
            if vil is not None:
                ringb = vil.buffer(R["habitat_m"]).exterior
                b = nearest_points(ringb, cen)[0]
                a = nearest_points(vil, b)[0]
                cv.arrow((a.x, a.y), (b.x, b.y))
                cv.label((a.x + b.x) / 2, (a.y + b.y) / 2, f"{R['habitat_m']} m", size=34)
        if len(addr):
            inside = addr[addr.within(box(bb[0] + 500, bb[1] + 400, bb[2] - 500, bb[3] - 400))]
            if len(inside):
                p = inside.geometry.iloc[len(inside) // 2]
                cv.arrow((p.x, p.y), (p.x + R["dwelling_m"], p.y))
                cv.label(p.x + R["dwelling_m"] / 2, p.y + 110, f"{R['dwelling_m']} m", size=30)

    def draw_etape5(cv, c):
        bb = cv.bbox
        sp = mask_polys(slope, grid, bb)
        if sp is not None:
            cv.poly(sp, fc="none", ec=FAMILY[5], hatch="///", lw=0, alpha=0.9, zorder=5)
            cv.poly(sp, fc=FAMILY[5], alpha=0.18, ec="none", zorder=5)
        D = meta["turbine"]["rotor_m"]
        big = (bb[0] - 500, bb[1] - 500, bb[2] + 500, bb[3] + 500)
        bands = []
        for gdf, d in ((rail, 50.0), (hv, 1.5 * D), (roads, 1.5 * D / 2)):
            g = clipped(gdf, big)
            if g is not None and not g.is_empty:
                bands.append(g.buffer(d))
        band = unary_union(bands) if bands else None
        cv.poly(band, fc=FAMILY[5], alpha=0.5, ec="white", lw=2, zorder=6)
        for gdf, text in ((hv, "ligne à haute tension"), (rail, "voie ferrée")):
            g = clipped(gdf, (bb[0] + 400, bb[1] + 300, bb[2] - 400, bb[3] - 300))
            if g is None or g.is_empty or not hasattr(g, "interpolate"):
                continue
            cv.place([g.interpolate(f, normalized=True) for f in (0.5, 0.3, 0.7, 0.15, 0.85)], text, size=30)
        if sp is not None and not sp.is_empty:
            parts = sorted(list(sp.geoms) if isinstance(sp, MultiPolygon) else [sp], key=lambda q: -q.area)
            cv.place([q.representative_point() for q in parts[:8]], "pente ≥ 7 %", size=32)

    def draw_etape6(cv, c):
        bb = cv.bbox
        cv.poly(mask_polys((fam == 0) & region, grid, bb), fc=GREEN, alpha=0.5, ec="#123F1C", lw=1.4, zorder=5)
        m = (fx > bb[0]) & (fx < bb[2]) & (fy > bb[1]) & (fy < bb[3])
        for x, y in zip(fx[m], fy[m]):
            for lw, col in ((5, "white"), (2.2, INK)):
                cv.ax.add_patch(Circle((x, y), meta["turbine"]["spacing_m"] / 2, fc="none", ec=col, lw=lw,
                                       linestyle=(0, (4, 3)) if col == INK else "-", zorder=12))
        cv.turbines(fx[m], fy[m])
        if m.sum() >= 2:
            t = cKDTree(np.c_[fx[m], fy[m]])
            d, j = t.query(np.c_[fx[m], fy[m]], k=2)
            cen = np.array([(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2])
            i = int(np.argmin(np.hypot(fx[m] - cen[0], fy[m] - cen[1]) + 5 * np.abs(d[:, 1] - 750)))
            a = (fx[m][i], fy[m][i])
            b = (fx[m][j[i, 1]], fy[m][j[i, 1]])
            cv.arrow(a, b)
            cv.label((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 140, "750 m", size=36)

    def draw_etape7(cv, c):
        bb = cv.bbox
        m = (kx > bb[0] - 2000) & (kx < bb[2] + 2000) & (ky > bb[1] - 2000) & (ky < bb[3] + 2000)
        for hpoly in hull_polys(kx[m], ky[m], kp[m], 330):
            cv.poly(hpoly, fc="white", alpha=0.22, ec="none", zorder=6)
            gpd.GeoSeries([hpoly.boundary]).plot(ax=cv.ax, color="white", lw=6, zorder=7)
            gpd.GeoSeries([hpoly.boundary]).plot(ax=cv.ax, color=INK, lw=2.6, zorder=8)
        cv.turbines(kx[m], ky[m], r_px=9)
        t = cKDTree(np.c_[kx, ky])
        d, _ = t.query(np.c_[fx, fy])
        drop = (d > 1500) & (fx > bb[0]) & (fx < bb[2]) & (fy > bb[1]) & (fy < bb[3])
        cv.crosses(fx[drop], fy[drop])
        p = c.get("park")
        if p is not None:
            n = int((kp == p).sum())
            cv.label(kx[kp == p].mean(), ky[kp == p].min() - 650, f"un parc de {n}", size=32)
        if drop.any():
            cen = np.array([(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2])
            idx = np.nonzero(drop)[0]
            i = idx[np.argmin(np.hypot(fx[idx] - cen[0], fy[idx] - cen[1]))]
            cv.label(fx[i], fy[i] + 480, "isolée : retirée", size=30)

    def draw_etape8(cv, c):
        bb = cv.bbox
        v = c.get("village")
        vx, vy = vxy[v]
        near7 = tk.query_ball_point([vx, vy], radius)
        near8 = th.query_ball_point([vx, vy], radius)
        # free sector
        pts8 = np.array(near8)
        dx, dy = hx[pts8] - vx, hy[pts8] - vy
        ang = np.degrees(np.arctan2(dy, dx)) % 360
        half = np.degrees(np.arcsin(np.clip(rot / np.maximum(np.hypot(dx, dy), rot), 0, 1)))
        iv = sorted([((a - h) % 360, (a + h) % 360) for a, h in zip(ang, half)])
        # largest gap by sampling
        occ = np.zeros(3600, dtype=bool)
        for s0, s1 in iv:
            i0, i1 = int(s0 * 10), int(s1 * 10)
            if i0 <= i1:
                occ[i0:i1 + 1] = True
            else:
                occ[i0:] = True
                occ[:i1 + 1] = True
        free = ~occ
        best, start, cur, cs = 0, 0, 0, 0
        for k in range(7200):
            if free[k % 3600]:
                if cur == 0:
                    cs = k
                cur += 1
                if cur > best:
                    best, start = cur, cs
            else:
                cur = 0
        best = min(best, 3600)
        a0, a1 = start / 10, (start + best) / 10
        cv.ax.add_patch(Wedge((vx, vy), radius, a0, a1, fc="white", alpha=0.36, ec="none", zorder=6))
        cv.ax.add_patch(Wedge((vx, vy), radius, a0, a1, fc="none", ec="white", lw=5, zorder=7))
        cv.ax.add_patch(Wedge((vx, vy), radius, a0, a1, fc="none", ec=INK, lw=2.2, zorder=8))
        for lw, col in ((5, "white"), (2.2, INK)):
            cv.ax.add_patch(Circle((vx, vy), radius, fc="none", ec=col, lw=lw,
                                   linestyle=(0, (5, 4)) if col == INK else "-", zorder=7))
        removed = [i for i in near7 if th.query([kx[i], ky[i]])[0] > 1]
        cv.crosses(kx[removed], ky[removed], r_px=12)
        cv.turbines(hx[near8], hy[near8], r_px=10)
        cv.ax.add_patch(Circle((vx, vy), 28 * cv.m_per_px, fc="white", ec=INK, lw=3, zorder=19))
        mid = np.radians((a0 + a1) / 2)
        cv.label(vx + 0.58 * radius * np.cos(mid), vy + 0.58 * radius * np.sin(mid),
                 "≥ 130° sans éolienne", size=34)
        # the 4 km radius, drawn on the occupied side
        opp = mid + np.pi
        ex, ey = vx + radius * np.cos(opp), vy + radius * np.sin(opp)
        cv.arrow((vx, vy), (ex, ey), both=False)
        cv.label(vx + 0.55 * radius * np.cos(opp), vy + 0.55 * radius * np.sin(opp), "4 km", size=32)

    def draw_etape8bis(cv, c):
        bb = cv.bbox
        a, b = c["masts"]
        m = (ix > bb[0] - 3000) & (ix < bb[2] + 3000) & (iy > bb[1] - 3000) & (iy < bb[3] + 3000)
        for hpoly in hull_polys(ix[m], iy[m], ip[m], 330):
            gpd.GeoSeries([hpoly.boundary]).plot(ax=cv.ax, color="white", lw=6, zorder=7)
            gpd.GeoSeries([hpoly.boundary]).plot(ax=cv.ax, color=INK, lw=2.6, zorder=8)
        cv.turbines(ix[m], iy[m], r_px=9)
        cv.arrow((ix[a], iy[a]), (ix[b], iy[b]))
        cv.label((ix[a] + ix[b]) / 2, (iy[a] + iy[b]) / 2, f"{c['distance_m'] / 1000:.1f} km".replace(".", ","), size=38)

    def draw_etape4(cv, c):
        bb = cv.bbox
        n = clipped(natura, bb)
        cv.poly(n, fc=FAMILY[4], alpha=0.25, ec="none", zorder=5)
        if n is not None:
            gpd.GeoSeries([n.boundary]).plot(ax=cv.ax, color="white", lw=4, linestyle=(0, (4, 3)), zorder=7)
            parts = list(n.geoms) if isinstance(n, MultiPolygon) else [n]
            p = max(parts, key=lambda q: q.area).representative_point()
            cv.label(p.x, p.y, "Natura 2000", size=34)

    def draw_etape0(cv, c):
        pass

    drawers = {"etape0": draw_etape0, "etape1": draw_etape1, "etape2": draw_etape2, "etape3": draw_etape3,
               "etape4": draw_etape4, "etape5": draw_etape5, "etape6": draw_etape6, "etape7": draw_etape7,
               "etape8": draw_etape8, "etape8bis": draw_etape8bis}

    # ------------------------------------------------------------------
    # Contact sheet of every candidate, then the chosen vignettes
    # ------------------------------------------------------------------
    sheet_rows = []
    for name, cands in candidates.items():
        tiles = []
        for c in cands:
            cv = Canvas(ortho(bbox_of(c), cache), bbox_of(c))
            drawers[name](cv, c)
            buf = BytesIO()
            cv.save(buf)
            buf.seek(0)
            tiles.append(Image.open(buf).resize((400, 300)))
        if tiles:
            row = Image.new("RGB", (1220, 320), "white")
            for k, t in enumerate(tiles):
                row.paste(t, (10 + 403 * k, 10))
            sheet_rows.append(row)
        logger.info("candidates drawn for %s", name)
    sheet = Image.new("RGB", (1220, 320 * len(sheet_rows)), "white")
    for k, r in enumerate(sheet_rows):
        sheet.paste(r, (0, 320 * k))
    sheet.save(snakemake.output.sheet, quality=80)

    photos = Path(snakemake.params.photos)
    for name in snakemake.params.names:
        dst = out_dir / f"{name}.jpg"
        src = next((p for p in sorted(photos.glob(f"{name}.*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")), None)
        if src is not None:
            im = ImageOps.fit(Image.open(src).convert("RGB"), (W_PX, H_PX), method=Image.LANCZOS)
            im = ImageEnhance.Color(im).enhance(0.85)
            im.save(dst, quality=86, optimize=True, progressive=True)
            logger.info("%s: ground photograph %s", name, src.name)
            continue
        if name == "bilan":
            name_src = "etape0"
        else:
            name_src = name
        if name_src not in drawers:
            if dst.exists():
                dst.unlink()
            logger.info("%s: no picture (pictogram shown)", name)
            continue
        c = chosen(name_src, default_pick=1 if name == "bilan" else 0)
        if c is None:
            logger.warning("%s: no candidate window", name)
            continue
        cv = Canvas(ortho(bbox_of(c), cache), bbox_of(c))
        drawers[name_src](cv, c)
        cv.save(dst)
        logger.info("%s: orthophoto at %s", name, [round(v) for v in c["centre_3035"]])
    Path(snakemake.output.done).write_text(json.dumps({"written": sorted(p.name for p in out_dir.glob("*.jpg"))}))
