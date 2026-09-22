# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Only two PV technologies exist in the Walloon config: ground-mounted and roof.

Single-axis tracking (``solar-hsat``) was dropped on 2026-09-22. Wallonia's
ground-mounted potential is agrivoltaics plus industrial brownfield (13 GW,
``custom_potentials.csv``) and the Walloon sources that size and price it
describe fixed-tilt plant; ``solar-hsat`` was a second, unsourced ground-mounted
technology carrying its own 37.8 GW land-availability potential.

Keeping both also switched on ``add_solar_potential_constraints``, which trades
one against the other through the ratio of their ``capacity_per_sqkm`` — an
upstream land-use assumption nobody on this project reviewed, and one that
silently bounded the *sum* of the two at the ground-mounted potential.
``solve_network`` only builds that constraint when ``solar-hsat`` is in both
carrier lists, so dropping it from the lists is what removes it.

``config/config.default.yaml`` keeps its ``renewable['solar-hsat']`` block: the
lists below are what decide whether the technology exists, and leaving the
block in place keeps a re-enable to a one-line change.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "config" / "config.default.yaml"
WALLOON = ROOT / "config" / "config.walloon.yaml"

# Every list the Walloon overlay must override, because snakemake's config
# merge replaces lists wholesale but only *merges* dicts: a list left out of
# the overlay is inherited from config.default.yaml complete with solar-hsat.
CARRIER_LISTS = [
    ("electricity", "renewable_carriers"),
    ("electricity", "extendable_carriers", "Generator"),
    ("pypsa_eur", "Generator"),
]


def _dig(cfg: dict, path: tuple[str, ...]):
    for key in path:
        assert isinstance(cfg, dict) and key in cfg, (
            f"config/config.walloon.yaml does not set {'.'.join(path)}, so it "
            "inherits config.default.yaml's list — which contains solar-hsat"
        )
        cfg = cfg[key]
    return cfg


def test_walloon_config_overrides_every_carrier_list():
    walloon = yaml.safe_load(WALLOON.read_text())
    for path in CARRIER_LISTS:
        carriers = _dig(walloon, path)
        assert "solar-hsat" not in carriers, f"{'.'.join(path)} still has solar-hsat"
        assert "solar" in carriers, f"{'.'.join(path)} lost ground-mounted PV"


def test_the_override_is_load_bearing():
    """If upstream ever drops solar-hsat too, this file stops being needed.

    Until then, config.default.yaml is where it comes from, and a merge that
    only merges dicts is why every list has to be repeated in the overlay.
    """
    default = yaml.safe_load(DEFAULT.read_text())
    assert any(
        "solar-hsat" in _dig(default, path) for path in CARRIER_LISTS
    ), "upstream no longer ships solar-hsat; the Walloon overrides are now inert"


def test_solar_potential_constraint_is_switched_off_by_the_removal():
    """`add_solar_potential_constraints` needs hsat in BOTH lists to be built."""
    import inspect

    import scripts.solve_network as sn

    src = inspect.getsource(sn.extra_functionality)
    assert '{"solar-hsat", "solar"}.issubset(' in src, (
        "the guard on add_solar_potential_constraints changed; re-check that "
        "dropping solar-hsat still removes the land-use trade-off"
    )
