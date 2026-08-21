# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Active TIMES-coupled scenarios must point at existing TIMES .vd inputs.

Prevents a mid-run MissingInputException when a new TIMES export is wired in
config but the .vd was never downloaded / symlinked into data/walloon/.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TIMES_CONFIG = ROOT / "config" / "config.walloon.yaml"
SCENARIOS_FILE = ROOT / "config" / "scenarios.walloon.yaml"


def _active_run_names() -> list[str]:
    cfg = yaml.safe_load(TIMES_CONFIG.read_text())
    names = cfg.get("run", {}).get("name") or []
    if isinstance(names, str):
        return [names]
    return list(names)


def _scenario_times_file(scenario: str) -> str | None:
    scenarios = yaml.safe_load(SCENARIOS_FILE.read_text()) or {}
    block = scenarios.get(scenario) or {}
    return (block.get("sector") or {}).get("times_file")


@pytest.mark.parametrize("scenario", _active_run_names())
def test_active_scenario_times_file_exists(scenario: str):
    """Every active run.name scenario has a resolvable sector.times_file."""
    times_file = _scenario_times_file(scenario)
    if not times_file:
        base = yaml.safe_load(TIMES_CONFIG.read_text())
        times_file = (base.get("sector") or {}).get("times_file")
    if not times_file:
        pytest.fail(
            f"{scenario}: no sector.times_file in scenarios.walloon.yaml "
            "or config.walloon.yaml."
        )

    path = ROOT / times_file
    if not path.exists():
        pytest.fail(
            f"{scenario}: times_file {times_file!r} is missing.\n"
            "Download the TIMES .vd into TIMES_PyPSA/data/ and symlink it:\n"
            f"  ln -sfn /path/to/TIMES_PyPSA/data/{Path(times_file).name} "
            f"{times_file}"
        )
    if not path.is_file():
        pytest.fail(f"{scenario}: times_file {times_file!r} exists but is not a file.")
    # Symlinks to gitignored VDs are fine; broken links are not.
    if path.is_symlink() and not path.resolve().exists():
        pytest.fail(
            f"{scenario}: times_file {times_file!r} is a broken symlink → "
            f"{path.resolve()}."
        )


def test_active_scenarios_are_defined_in_scenarios_file():
    """run.name entries must have an override block in scenarios.walloon.yaml."""
    scenarios = yaml.safe_load(SCENARIOS_FILE.read_text()) or {}
    missing = [s for s in _active_run_names() if s not in scenarios]
    if missing:
        pytest.fail(
            "config.walloon.yaml run.name lists scenario(s) with no block in "
            f"scenarios.walloon.yaml: {missing}"
        )
