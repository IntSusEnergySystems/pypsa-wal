# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""
Snakemake wrapper: TIMES scenario indicators into ``html/indicators/``.

Four pages — final energy demand, greenhouse-gas emissions, heat production and
the power fleet — each a stacked bar per planning horizon next to the table it
was built from, plus the same tables as CSV. They live in their own subfolder so
pypsa2html keeps ``html/pypsa/`` and the Sankeys keep ``html/times/``;
``html/index.html`` is a pypsa-wal hub that links all three.

Like the Sankeys, these describe the **TIMES input**, not the PyPSA solve: they
are read from the same ``.vd`` ``build_wallon_demands`` extracts the demands
from, so a demand that looks odd downstream can be checked against the
trajectory it came from. The extraction lives in the sibling ``TIMES_PyPSA``
repository (``pip install -e ../TIMES_PyPSA``, see its ``INDICATORS.md``); this
script only wires Snakemake I/O.
"""

import shutil
from pathlib import Path

from times_pypsa import export_indicator_pages, indicator_page_names
from times_pypsa.indicators import default_rules_dir

from scripts._helpers import configure_logging

if __name__ == "__main__" and "snakemake" not in globals():
    from scripts._helpers import mock_snakemake

    snakemake = mock_snakemake("build_times_indicators")

configure_logging(snakemake)

out_dir = Path(snakemake.output.index).parent
years = [int(y) for y in snakemake.params.planning_horizons]

# `years` is the parse-time horizon list the rule expanded its outputs from;
# `scenario_horizons` is what this run actually solves. They differ only if a
# scenario overlay overrode `scenario.planning_horizons`, which the rule cannot
# follow -- its output file names were fixed before the overlay was applied.
# Charting the parse-time years anyway would put the wrong horizons in the
# report, so stop instead.
scenario_years = [int(y) for y in snakemake.params.scenario_horizons]
if sorted(set(scenario_years)) != sorted(set(years)):
    raise ValueError(
        f"scenario.planning_horizons for run '{snakemake.wildcards.get('run', '')}' "
        f"is {sorted(set(scenario_years))} but the TIMES indicator outputs were "
        f"declared for {sorted(set(years))}. The rule reads the horizons at parse "
        "time, before scenario overlays. Either keep planning_horizons out of the "
        "scenario overlay, or set sector.times_indicators.enable: false for this run."
    )

mappings_dir = snakemake.params.get("mappings_dir")
mappings_dir = Path(mappings_dir) if mappings_dir else default_rules_dir()

export_indicator_pages(
    out_dir,
    vd_file=snakemake.input.times_file,
    mappings_dir=mappings_dir,
    years=years,
    scenario_label=snakemake.wildcards.get("run", ""),
    write_csv=bool(snakemake.params.write_csv),
)

# The rule declares its outputs from the same helper the library writes with, so
# a mismatch is a bug in one of the two -- fail with the missing names rather
# than with Snakemake's "missing output files" list, which does not say why.
missing = [name for name in indicator_page_names() if not (out_dir / name).exists()]
if missing:
    raise RuntimeError(
        f"times_pypsa wrote {out_dir} but these declared pages are absent: {missing}"
    )

# DirectoryIndex serves index.html for a bare ``indicators/`` URL. Copy the real
# index rather than a meta-refresh stub (some browsers never follow it).
shutil.copyfile(out_dir / "times_indicators_index.html", out_dir / "index.html")
