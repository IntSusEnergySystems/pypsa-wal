# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""
Snakemake wrapper: export Walloon TIMES demands via the ``times_pypsa`` package.

The extraction logic lives in the sibling ``TIMES_PyPSA`` repository
(``pip install -e ../TIMES_PyPSA``). This script only wires Snakemake I/O.
"""

import shutil
from pathlib import Path

from times_pypsa import default_mappings_dir, export_horizon

from scripts._helpers import configure_logging

if __name__ == "__main__" and "snakemake" not in globals():
    from scripts._helpers import mock_snakemake

    snakemake = mock_snakemake("build_wallon_demands", planning_horizons="2030")

planning_horizon = int(snakemake.wildcards.planning_horizons[-4:])
configure_logging(snakemake)

coupling_dir = snakemake.params.get("coupling_dir")
times_use_preexported = snakemake.params.get("times_use_preexported", False)

demands_src = heating_src = targets_src = None
fleet_src = fleet_shares_src = None
if coupling_dir:
    preexported_dir = Path(coupling_dir) / "pypsa_inputs"
    demands_src = preexported_dir / f"wallon_demands_{planning_horizon}.csv"
    heating_src = preexported_dir / f"heating_capacities_{planning_horizon}.csv"
    targets_src = preexported_dir / f"heating_targets_{planning_horizon}.csv"
    fleet_src = preexported_dir / f"road_transport_{planning_horizon}.csv"
    fleet_shares_src = preexported_dir / f"road_transport_{planning_horizon}_shares.csv"

if coupling_dir and (times_use_preexported or demands_src.exists()):
    if not demands_src.exists():
        raise FileNotFoundError(f"Pre-exported demands not found: {demands_src}")
    if not heating_src.exists():
        raise FileNotFoundError(
            f"Pre-exported heating capacities not found: {heating_src}"
        )
    if not targets_src.exists():
        raise FileNotFoundError(
            f"Pre-exported heating targets not found: {targets_src}. The bundle "
            "predates the option-C heating soft-link; re-export it with "
            "`times-pypsa export-coupling`."
        )
    for src, label in (
        (fleet_src, "road-vehicle fleet"),
        (fleet_shares_src, "road-vehicle fleet shares"),
    ):
        if not src.exists():
            raise FileNotFoundError(
                f"Pre-exported {label} not found: {src}. The bundle predates the "
                "EV fleet-share soft-link (E1-E3), which scales the BEV charger "
                "and EV battery on the TIMES vehicle count rather than the energy "
                "ratio; re-export it with `times-pypsa export-coupling`."
            )
    shutil.copy2(demands_src, snakemake.output.wallon_demands)
    shutil.copy2(heating_src, snakemake.output.heating_capacities)
    shutil.copy2(targets_src, snakemake.output.heating_targets)
    shutil.copy2(fleet_src, snakemake.output.road_transport)
    shutil.copy2(fleet_shares_src, snakemake.output.road_transport_shares)
else:
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
        heating_targets_path=snakemake.output.heating_targets,
        # Writes `road_transport_<h>.csv` and, alongside it,
        # `road_transport_<h>_shares.csv` -- both declared as rule outputs.
        road_transport_path=snakemake.output.road_transport,
    )
