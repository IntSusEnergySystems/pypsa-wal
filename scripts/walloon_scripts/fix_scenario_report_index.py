#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Point a per-scenario pypsa2html index at that scenario's own landing page.

``config/pypsa2html.yaml`` carries one ``landing.scenario`` (``scen_central``).
That is correct for the COMBINED report at ``results/<prefix>/index.html``, which
holds every scenario's pages side by side. pypsa2html applies it verbatim to the
per-scenario reports too, so ``results/<prefix>/<scen>/html/pypsa/index.html``
redirects to ``BEWAL_overview_scen_central.html`` — a file that exists only in the
central tree. Every other scenario's report therefore opens on a 404 (observed
2026-09-13 on the September cabinet batch).

This rewrites the redirect to the landing page that is actually present next to
it, leaving the combined report and pypsa2html itself untouched. Idempotent: an
index already pointing at an existing sibling is left alone.

    python scripts/walloon_scripts/fix_scenario_report_index.py results/walloon/scen_x [...]
    python scripts/walloon_scripts/fix_scenario_report_index.py --all
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REDIRECT = re.compile(r"(?P<attr>url=|href=')(?P<page>[A-Za-z0-9_]+\.html)")
#: Preference order for the landing page of a single-scenario report.
PREFERRED_NODES = ("BEWAL", "ALL", "BE")


def landing_candidates(html_dir: Path, scenario: str) -> list[Path]:
    out = []
    for node in PREFERRED_NODES:
        p = html_dir / f"{node}_overview_{scenario}.html"
        if p.exists():
            out.append(p)
    out.extend(sorted(html_dir.glob(f"*_overview_{scenario}.html")))
    return out


def fix_one(run_dir: Path) -> str:
    scenario = run_dir.name
    index = run_dir / "html" / "pypsa" / "index.html"
    if not index.exists():
        return f"[skip] {scenario}: no html/pypsa/index.html"

    text = index.read_text()
    current = REDIRECT.search(text)
    if current and (index.parent / current.group("page")).exists():
        return f"[ok]   {scenario}: already points at {current.group('page')}"

    candidates = landing_candidates(index.parent, scenario)
    if not candidates:
        return f"[WARN] {scenario}: no *_overview_{scenario}.html to point at"

    target = candidates[0].name
    fixed = REDIRECT.sub(lambda m: m.group("attr") + target, text)
    index.write_text(fixed)
    was = current.group("page") if current else "?"
    return f"[fix]  {scenario}: {was} -> {target}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("runs", nargs="*", help="results/<prefix>/<scenario> directories")
    ap.add_argument(
        "--all",
        action="store_true",
        help="every results/*/*/html/pypsa/index.html under the repo",
    )
    args = ap.parse_args()

    runs = [Path(r) for r in args.runs]
    if args.all:
        runs += [p.parents[2] for p in Path("results").glob("*/*/html/pypsa/index.html")]
    if not runs:
        ap.error("give at least one run directory, or --all")

    bad = 0
    for run in dict.fromkeys(runs):
        line = fix_one(run)
        print(line)
        bad += line.startswith("[WARN]")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
