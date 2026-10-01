# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The report's "capped" net emissions must be booked like the solver's cap.

pypsa2html's `features.capped_emissions` splits the carbon Sankey's net into the
part the national cap constrains and the rest. If its booking rules drift from
`national_co2_expression`, the "capped" bar stops being the cap's LHS and the
comparison with TIMES-WAL's regional total silently breaks.
"""

from pathlib import Path

import yaml

from scripts.solve_network import AVIATION_CARRIER, NATIONAL_CO2_SOURCE_PATTERNS

ROOT = Path(__file__).resolve().parents[1]


def test_split_mirrors_the_solver_rules():
    cfg = yaml.safe_load((ROOT / "config" / "pypsa2html.yaml").read_text())
    split = cfg["features"]["capped_emissions"]
    assert split["enable"] is True
    assert split["source_patterns"] == list(NATIONAL_CO2_SOURCE_PATTERNS)
    # Aviation is off the national cap unless co2_budget_national_include_aviation.
    walloon = yaml.safe_load((ROOT / "config" / "config.walloon.yaml").read_text())
    if not walloon.get("co2_budget_national_include_aviation", False):
        assert split["exclude_patterns"] == [AVIATION_CARRIER]
    else:
        assert split["exclude_patterns"] == []
    assert split["location_port"] == {"DAC": 3}
