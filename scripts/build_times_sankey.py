# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""
Snakemake wrapper: TIMES Sankey diagrams into ``html/times/``.

One interactive page per planning horizon and aggregation level. They live in
a subfolder so pypsa2html can keep ``html/pypsa/`` (and its ``index.html``)
untouched; ``html/index.html`` is a pypsa-wal hub that links both. The
rendering lives in the sibling ``TIMES_PyPSA`` repository
(``pip install -e ../TIMES_PyPSA``); this script only wires Snakemake I/O.

These pages describe the **TIMES input**, not the PyPSA solve — the same ``.vd``
`build_wallon_demands` extracts the demands from. Reading them next to the PyPSA
report is the point: the export colouring shows which TIMES flows crossed the
soft-link, so a demand that looks wrong downstream can be traced to the flow it
came from. See `docs/times-sankey.md`.
"""

import shutil
from pathlib import Path

from times_pypsa import default_mappings_dir, export_sankey_pages, sankey_page_names

from scripts._helpers import configure_logging

if __name__ == "__main__" and "snakemake" not in globals():
    from scripts._helpers import mock_snakemake

    snakemake = mock_snakemake("build_times_sankey")

configure_logging(snakemake)

out_dir = Path(snakemake.output.index).parent
years = [int(y) for y in snakemake.params.planning_horizons]
levels = list(snakemake.params.agg_levels)

# `years` is the parse-time horizon list the rule expanded its outputs from;
# `scenario_horizons` is what this run actually solves. They differ only if a
# scenario overlay overrode `scenario.planning_horizons`, which the rule cannot
# follow -- its output file names were fixed before the overlay was applied.
# Rendering the parse-time years anyway would put a diagram for the wrong
# horizon in the report, so stop instead.
scenario_years = [int(y) for y in snakemake.params.scenario_horizons]
if sorted(set(scenario_years)) != sorted(set(years)):
    raise ValueError(
        f"scenario.planning_horizons for run '{snakemake.wildcards.get('run', '')}' "
        f"is {sorted(set(scenario_years))} but the TIMES Sankey outputs were "
        f"declared for {sorted(set(years))}. The rule reads the horizons at parse "
        "time, before scenario overlays. Either keep planning_horizons out of the "
        "scenario overlay, or set sector.times_sankey.enable: false for this run."
    )

mappings_dir = snakemake.params.get("mappings_dir")
mappings_dir = Path(mappings_dir) if mappings_dir else default_mappings_dir()

export_sankey_pages(
    out_dir,
    vd_file=snakemake.input.times_file,
    mappings_dir=mappings_dir,
    years=years,
    agg_levels=levels,
    units=snakemake.params.units,
    flow_threshold=snakemake.params.threshold,
    scenario_label=snakemake.wildcards.get("run", ""),
)

# The rule declares its outputs from the same helper the library writes with, so
# a mismatch is a bug in one of the two -- fail with the missing names rather
# than with Snakemake's "missing output files" list, which does not say why.
expected = sankey_page_names(years, levels)
missing = [name for name in expected if not (out_dir / name).exists()]
if missing:
    raise RuntimeError(
        f"times_pypsa wrote {out_dir} but these declared pages are absent: {missing}"
    )

# DirectoryIndex serves index.html for a bare ``times/`` URL. Copy the real
# year table rather than a meta-refresh stub (some browsers never follow it).
index = out_dir / "times_sankey_index.html"
shutil.copyfile(index, out_dir / "index.html")
