# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Capture the dashboard into the social-media formats of the infographic plan
(§5, §12): the funnel and the "Et si… ?" sequence as GIF and MP4, in landscape
(1600 x 900) and portrait (1080 x 1350), and a portrait PNG/PDF carousel.

The page is served locally and driven through ``window.renderState()`` in its
fixed export layouts (``?export=landscape|portrait``), so every frame is the
dashboard itself.  Needs Playwright, gifski, gifsicle, ffmpeg and img2pdf,
which live in their own environment (``envs/infographic.yaml``); this script
is therefore run through ``conda run`` rather than as a Snakemake ``script:``.

    python scripts/infographic_export.py results/infographic results/infographic/exports
"""

import argparse
import asyncio
import functools
import glob
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import tempfile
import threading
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

SIZES = {"paysage": ("landscape", 1600, 900), "portrait": ("portrait", 1080, 1350)}

# (renderState argument, seconds on screen)
FUNNEL = (
    [({"view": "titre"}, 3.0)]
    + [({"etape": str(i)}, 2.2) for i in range(9)]
    + [({"etape": "bilan"}, 5.0)]
)
ETSI = [
    ({"view": "choix", "choix": "derogation"}, 3.0),
    ({"view": "choix", "choix": "isolees"}, 3.0),
    ({"view": "choix", "choix": "inter4"}, 3.0),
    ({"view": "choix", "choix": "inter6"}, 3.0),
    ({"view": "choix", "choix": "resineux"}, 3.0),
    ({"view": "choix", "choix": "foret"}, 3.0),
    ({"view": "enveloppe"}, 5.0),
]
CAROUSEL = [{"view": "titre"}] + [{"etape": str(i)} for i in range(9)] + [{"view": "etsi"}, {"etape": "bilan"}]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(root):
    handler = functools.partial(QuietHandler, directory=str(root))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def chromium_path():
    """A Chromium Playwright can drive: its own if installed, else any cached build."""
    if os.environ.get("CHROMIUM_PATH"):
        return os.environ["CHROMIUM_PATH"]
    builds = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome")))
    return builds[-1] if builds else None


async def capture(url, frames, size, out_dir):
    fmt, w, h = size
    out_dir.mkdir(parents=True, exist_ok=True)
    # A shorter sequence than last time must not leave old frames behind.
    for old in out_dir.glob("[0-9][0-9].*"):
        old.unlink()
    paths = []
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception:
            browser = await p.chromium.launch(executable_path=chromium_path())
        page = await browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{url}/index.html?export={fmt}")
        await page.wait_for_function("typeof window.renderState === 'function' && document.body.classList.contains('ready')",
                                     timeout=30000)
        for k, spec in enumerate(frames):
            await page.evaluate("s => window.renderState(s)", spec)
            path = out_dir / f"{k:02d}.png"
            await page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": w, "height": h})
            paths.append(path)
        await browser.close()
        if errors:
            raise RuntimeError(f"page errors while capturing: {errors}")
    return paths


def gif(frames, durations, out, width):
    """gifski at 4 frames per second, a frame repeated for its duration, then gifsicle."""
    tmp = Path(tempfile.mkdtemp())
    seq = []
    for f, d in zip(frames, durations):
        for _ in range(max(1, round(d * 4))):
            dst = tmp / f"{len(seq):04d}.png"
            os.symlink(Path(f).resolve(), dst)
            seq.append(dst)
    raw = tmp / "raw.gif"
    subprocess.run(["gifski", "--quiet", "--fps", "4", "--quality", "82", "--width", str(width), "-o", str(raw),
                    *map(str, seq)], check=True)
    subprocess.run(["gifsicle", "-O3", "--lossy=40", "--colors", "192", "-o", str(out), str(raw)], check=True)
    shutil.rmtree(tmp)


def mp4(frames, durations, out, fade=0.4, fps=30):
    """H.264 with 0.4 s cross-fades between frames."""
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for f, d in zip(frames, durations):
        args += ["-loop", "1", "-t", f"{d + fade:.2f}", "-framerate", str(fps), "-i", str(f)]
    # Every input lasts its duration plus the fade, so fade i starts at the sum
    # of the durations before it.
    chain, last, t = [], "[0:v]", 0.0
    for i in range(1, len(frames)):
        t += durations[i - 1]
        lab = f"[x{i}]"
        chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={fade}:offset={t:.2f}{lab}")
        last = lab
    chain.append(f"{last}format=yuv420p[v]")
    args += ["-filter_complex", ";".join(chain), "-map", "[v]", "-c:v", "libx264", "-preset", "slow",
             "-crf", "20", "-r", str(fps), "-movflags", "+faststart", str(out)]
    subprocess.run(args, check=True)


def alt_text(root):
    """One French paragraph describing the funnel, for every export."""
    states = json.loads((root / "data" / "states.json").read_text())
    t = json.loads((root / "textes.json").read_text())
    # d0-i1-x0-f0 is the reference: parks of four, then the §3.1 4° exception
    # on leftover land.  d0-i0 is the strict "four everywhere" sensitivity.
    steps = states["states"]["d0-i1-x0-f0"]["steps"]
    meta = states["meta"]

    def n(v):
        return f"{round(v):,}".replace(",", " ")

    parts = [f"Carte de la Wallonie ({n(meta['region_km2'])} km²) où les règles d'implantation des éoliennes "
             f"retirent du terrain étape par étape."]
    for e in t["etapes"]:
        if e["id"] in ("0", "7bis", "bilan"):
            continue
        # Stops 6 and 7 are the states' steps 7 and 8 (step 6 is the free
        # packing, which the dashboard does not show as a stop).
        s = steps[-1] if e["id"] == "8" else steps[int(e["id"]) + (e["id"] in "67")]
        if e["id"] in "12345":
            parts.append(f"{e['titre']} : il reste {n(s['area_km2'])} km², place pour {n(s['n'])} éoliennes.")
        elif e["id"] == "8":
            parts.append(f"{e['titre']} : une réserve ramène le résultat à environ {n(s['mw'])} MW, "
                         f"entre {n(s['mw_low'])} et {n(s['mw_high'])} MW.")
        else:
            parts.append(f"{e['titre']} : {n(s['n'])} éoliennes, {n(s['mw'])} MW.")
    last = steps[-1]
    parts.append((f"Bilan : environ {last['mw'] / 1000:.1f} GW possibles, environ "
                  f"{last['mw'] / meta['installed_mw']:.1f} fois le parc actuel de "
                  f"{meta['installed_mw'] / 1000:.1f} GW").replace(".", ",") + ".")
    return " ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site", type=Path)
    ap.add_argument("out", type=Path)
    a = ap.parse_args()
    for tool in ("gifski", "gifsicle", "ffmpeg", "img2pdf"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found: run this in the `infographic` environment")
    a.out.mkdir(parents=True, exist_ok=True)
    httpd, port = serve(a.site)
    url = f"http://127.0.0.1:{port}"
    frames_dir = a.out / "images"
    try:
        for name, size in SIZES.items():
            for seq_name, seq in (("entonnoir", FUNNEL), ("etsi", ETSI)):
                specs, durs = zip(*seq)
                frames = asyncio.run(capture(url, specs, size, frames_dir / f"{seq_name}_{name}"))
                gif(frames, durs, a.out / f"{seq_name}_{name}.gif", size[1])
                mp4(frames, durs, a.out / f"{seq_name}_{name}.mp4")
                print(f"{seq_name}_{name}: {len(frames)} frames")
        pages = asyncio.run(capture(url, CAROUSEL, SIZES["portrait"], frames_dir / "carrousel"))
        # JPEG pages keep the PDF a few MB; the PNGs stay for posting one by one.
        jpgs = []
        for pg in pages:
            j = pg.with_suffix(".jpg")
            Image.open(pg).convert("RGB").save(j, quality=90, optimize=True)
            jpgs.append(j)
        subprocess.run(["img2pdf", "-o", str(a.out / "carrousel.pdf"), *map(str, jpgs)], check=True)
    finally:
        httpd.shutdown()
    (a.out / "texte_alternatif.txt").write_text(alt_text(a.site) + "\n", encoding="utf-8")
    sizes = {p.name: round(p.stat().st_size / 1e6, 2) for p in sorted(a.out.glob("*.*"))}
    (a.out / "exports.json").write_text(json.dumps(sizes, indent=1))
    print(json.dumps(sizes, indent=1))


if __name__ == "__main__":
    main()
