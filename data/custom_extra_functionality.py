# SPDX-FileCopyrightText: : 2023- The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT


def custom_extra_functionality(n, snapshots, snakemake):
    """
    Add custom extra functionality constraints.

    Walloon addition: the TIMES heating soft-link. Two alternative mechanisms,
    both inactive by default, so the default behaviour of this hook is still a
    no-op:

    ``sector.times_heat.energy_mix.enable`` — **option C**, an annual
        energy-mix constraint per technology group. TIMES fixes *what* serves
        Walloon heat; PyPSA keeps deciding *when*.
        ``scripts/walloon_scripts/times_heat_softlink.py``,
        ``docs/heat_soft_linking.md``.

    ``sector.times_heat.profile.enable`` — **option B'**, the TIMES shares
        combined with PyPSA's heat-load shape into one hourly profile per group,
        with the dispatch pinned to it. TIMES fixes both *what* and (through
        PyPSA's own profile) *when*.
        ``scripts/walloon_scripts/times_heat_profiles.py``,
        ``docs/heat_softlink_option_b.md``.

    Enabling both raises — they impose the same information through
    incompatible constraints. The check lives in ``times_heat_options`` so it
    also fires in the build rules, not only here.
    """
    from scripts.walloon_scripts.times_heat_profiles import (
        add_times_heat_profile_constraints,
    )
    from scripts.walloon_scripts.times_heat_softlink import (
        add_times_heat_mix_constraints,
    )

    add_times_heat_mix_constraints(n, snapshots, snakemake)
    add_times_heat_profile_constraints(n, snapshots, snakemake)
