# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""
Snakemake wrapper: export Walloon TIMES demands via the ``times_pypsa`` package.

The extraction logic lives in the sibling ``TIMES_PyPSA`` repository
(``pip install -e ../TIMES_PyPSA``). This script only wires Snakemake I/O.
"""

from pathlib import Path

from times_pypsa import default_mappings_dir, export_horizon

from scripts._helpers import configure_logging

if __name__ == "__main__" and "snakemake" not in globals():
    from scripts._helpers import mock_snakemake

    snakemake = mock_snakemake("build_wallon_demands", planning_horizons="2030")

planning_horizon = int(snakemake.wildcards.planning_horizons[-4:])
configure_logging(snakemake)

mappings_dir = snakemake.params.get("mappings_dir")
if mappings_dir:
    mappings_dir = Path(mappings_dir)
else:
    mappings_dir = default_mappings_dir()

export_horizon(
    vd_file=snakemake.input.times_file,
    mappings_dir=mappings_dir,
    horizon=planning_horizon,
    wallon_demands_path=snakemake.output.wallon_demands,
    heating_capacities_path=snakemake.output.heating_capacities,
)
