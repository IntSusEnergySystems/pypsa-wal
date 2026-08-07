# SPDX-FileCopyrightText: : 2023- The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT


def custom_extra_functionality(n, snapshots, snakemake):
    """
    Add custom extra functionality constraints.

    Walloon addition: the TIMES heating soft-link (option C). Inactive unless
    ``sector.times_heat.energy_mix.enable`` is true, so the default behaviour of
    this hook is still a no-op. See
    ``scripts/walloon_scripts/times_heat_softlink.py`` and
    ``docs/heat_soft_linking.md``.
    """
    from scripts.walloon_scripts.times_heat_softlink import (
        add_times_heat_mix_constraints,
    )

    add_times_heat_mix_constraints(n, snapshots, snakemake)
