# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""TIMES → PyPSA heating soft-link, option C: annual energy-mix constraints.

Three separable pieces, each behind its own config switch under
``sector.times_heat`` and each defaulting to *off* so an untouched config
reproduces the previous results exactly:

``energy_mix.enable``
    Constrain the annual heat delivered to the Walloon **decentral** heat buses
    per technology group to the TIMES value. This is the actual soft-link: TIMES
    decides *what* serves Walloon heat, PyPSA keeps deciding *when*, with how
    much iron, at what COP, and against which electricity price. The
    right-hand sides come from ``heating_targets_{year}.csv``
    (``times_pypsa.heat_softlink``).

``urban_rural_split``
    How the TIMES residential decentral heat *demand* is divided between
    ``rural`` and ``urban decentral``. TIMES-WAL has no urban/rural dimension —
    the labels are an archetype convention (2-façade houses and apartments →
    ``urban decentral``; 3- and 4-façade houses → ``rural``) — and its implied
    rural share **drifts from 59 % to 37 %** across the horizons, i.e. dwellings
    migrate between PyPSA buses over time and the base-year rural stock strands.
    See ``docs/heat_soft_linking.md``.

``base_year_capacities``
    Replace the BEWAL rows of ``existing_heating_distribution`` with the TIMES
    base-year stock. Both sides are already in **MW thermal output**, so this is
    a substitution, not a conversion (see :func:`times_heat_stock_capacities`).

Scope is the two decentral heat buses only. The urban-central bus is excluded by
design: DAC withdraws more heat than the district-heating load, CHP heat is
welded to CHP electricity, the pit store re-injects, and 73 % of the TIMES 2050
district-heat supply (geothermal + industrial waste heat) has no PyPSA component
to constrain. ``docs/times-heating-softlink-options.md`` §6 *Scope*.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

#: The PyPSA heat systems option C applies to, *after* ``cluster_heat_buses``
#: has stripped the ``residential ``/``services `` prefixes.
DECENTRAL_HEAT_SYSTEMS = ("rural", "urban decentral")

#: ``sector.times_heat`` defaults. Every one of them reproduces the behaviour
#: that predates this module, so adding the block to a config is a no-op until a
#: switch is flipped.
DEFAULT_OPTIONS: dict = {
    "node": "BEWAL",
    # times | times_base_year | pypsa
    "urban_rural_split": "times",
    "base_year_capacities": False,
    "energy_mix": {
        "enable": False,
        # share | absolute
        "mode": "share",
        "tolerance": 0.05,
        "slack_groups": [],
        # forbid | free — what a zero TIMES target means (see below)
        "zero_target": "forbid",
        # EUR per MWh_th of unmet TIMES mix. A finite penalty makes every
        # constraint *soft*, so a TIMES mix the Walloon system physically cannot
        # deliver relaxes at a price instead of making the LP infeasible.
        # Set to 0 (or null) for hard constraints.
        "penalty": 1000.0,
    },
}

_VALID_SPLITS = ("times", "times_base_year", "pypsa")
_VALID_MODES = ("share", "absolute")
_VALID_ZERO_TARGETS = ("forbid", "free")


def times_heat_options(config: dict) -> dict:
    """``sector.times_heat`` merged onto :data:`DEFAULT_OPTIONS`, validated."""
    raw = (config.get("sector") or {}).get("times_heat") or {}
    opts = {**DEFAULT_OPTIONS, **{k: v for k, v in raw.items() if k != "energy_mix"}}
    opts["energy_mix"] = {
        **DEFAULT_OPTIONS["energy_mix"],
        **(raw.get("energy_mix") or {}),
    }
    if opts["urban_rural_split"] not in _VALID_SPLITS:
        raise ValueError(
            f"sector.times_heat.urban_rural_split must be one of {_VALID_SPLITS}, "
            f"got {opts['urban_rural_split']!r}"
        )
    if opts["energy_mix"]["mode"] not in _VALID_MODES:
        raise ValueError(
            f"sector.times_heat.energy_mix.mode must be one of {_VALID_MODES}, "
            f"got {opts['energy_mix']['mode']!r}"
        )
    if opts["energy_mix"]["zero_target"] not in _VALID_ZERO_TARGETS:
        raise ValueError(
            f"sector.times_heat.energy_mix.zero_target must be one of "
            f"{_VALID_ZERO_TARGETS}, got {opts['energy_mix']['zero_target']!r}"
        )
    tol = float(opts["energy_mix"]["tolerance"])
    if not 0.0 <= tol < 1.0:
        raise ValueError(
            f"sector.times_heat.energy_mix.tolerance must be in [0, 1), got {tol}"
        )
    opts["energy_mix"]["tolerance"] = tol
    penalty = opts["energy_mix"].get("penalty")
    penalty = 0.0 if penalty in (None, False) else float(penalty)
    if penalty < 0:
        raise ValueError(
            f"sector.times_heat.energy_mix.penalty must be >= 0, got {penalty}"
        )
    opts["energy_mix"]["penalty"] = penalty
    return opts


# --------------------------------------------------------------------------- #
# Payload
# --------------------------------------------------------------------------- #


def load_heat_targets(path: str) -> pd.DataFrame:
    """Read ``heating_targets_{year}.csv`` written by ``times_pypsa``."""
    df = pd.read_csv(path)
    required = {"group", "scope", "constrained", "pypsa_component", "sense", "TWh"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing columns {sorted(missing)}")
    df["carriers"] = (
        df["pypsa_carriers"]
        .fillna("")
        .map(lambda s: [v.strip() for v in str(s).split(";") if v.strip()])
    )
    return df


def load_heat_capacities(path: str) -> pd.DataFrame:
    """Read ``heating_capacities_{year}.csv`` written by ``times_pypsa``."""
    df = pd.read_csv(path)
    required = {
        "sector",
        "times_heat_system",
        "pypsa_stock_technology",
        "MW_th",
        "transferable",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{path} is missing columns {sorted(missing)}. It was probably written "
            "by a times_pypsa older than the option-C heating soft-link; re-run "
            "build_wallon_demands."
        )
    return df


# --------------------------------------------------------------------------- #
# Demand: urban/rural split of the TIMES residential decentral heat
# --------------------------------------------------------------------------- #


def split_residential_heat_target(
    total_twh: float,
    mode: str,
    pypsa_weights: pd.Series,
    times_weights: pd.Series,
) -> pd.Series:
    """Divide the TIMES residential decentral heat between the two PyPSA buses.

    Parameters
    ----------
    total_twh
        TIMES residential decentral useful heat, both buses together. This is the
        quantity TIMES actually determines; the split is not.
    mode
        ``times`` keeps the per-horizon TIMES labels (previous behaviour),
        ``times_base_year`` freezes the TIMES archetype split at the first
        planning horizon, ``pypsa`` uses PyPSA's own population-based split.
    pypsa_weights
        Un-rescaled annual load energy of the two residential heat loads, i.e.
        PyPSA's native split — ``1 - urban_fraction`` against
        ``urban_fraction - district_fraction``, already carrying the hourly
        profile and the district-heating share of the horizon.
    times_weights
        TIMES heat per bus for the horizon whose labelling should govern the
        split: the current one for ``times``, the base year for
        ``times_base_year``.

    Returns
    -------
    pd.Series
        Per-bus targets in TWh, summing to ``total_twh``.
    """
    weights = pypsa_weights if mode == "pypsa" else times_weights
    weights = weights.astype(float)
    if weights.sum() <= 0:
        logger.warning(
            "Cannot split the residential decentral heat target: %s weights sum to "
            "zero. Falling back to an even split.",
            mode,
        )
        weights = pd.Series(1.0, index=weights.index)
    return total_twh * weights / weights.sum()


# --------------------------------------------------------------------------- #
# Base-year stock
# --------------------------------------------------------------------------- #


def times_heat_stock_capacities(
    capacities: pd.DataFrame,
    split_mode: str,
    pypsa_rural_fraction: float,
) -> pd.Series:
    """TIMES base-year heat stock as an ``existing_heating_distribution`` row.

    Returns a Series indexed by ``(heat name, technology)`` — the MultiIndex of
    ``existing_heating_distribution_*.csv`` — in **MW thermal output**, which is
    the unit that file already uses: ``add_existing_baseyear`` divides by the
    appliance efficiency itself for boilers and resistive heaters, and for heat
    pumps ``p_nom`` *is* thermal because ``p_min_pu`` is ``-COP/COP = -1``
    (verified on the solved networks). So no COP and no boiler efficiency enters
    here, which removes the single largest objection to reusing TIMES capacities.

    Placement rules, all of them arbitrary at some level and all documented in
    ``docs/heat_soft_linking.md``:

    * ``services`` capacity goes to ``services urban decentral`` only —
      ``write_wallon_heat_demands`` deletes the whole ``BEWAL services rural``
      sub-system, so a services-rural row would be silently dropped.
    * residential capacity follows ``split_mode``: the TIMES archetype labels
      (``times``/``times_base_year`` — identical in the base year) or PyPSA's own
      rural fraction (``pypsa``).
    * ``urban central`` rows (district-heating substations) and rows with no
      ``pypsa_stock_technology`` (solar thermal) are dropped, with a log line
      naming the MW_th left behind.
    """
    transferable = capacities[capacities["transferable"]].copy()
    dropped = capacities.loc[~capacities["transferable"], "MW_th"].sum()
    central = transferable["times_heat_system"] == "urban central"
    dropped += transferable.loc[central, "MW_th"].sum()
    transferable = transferable[~central]

    if dropped > 0:
        logger.info(
            "TIMES base-year heat stock: %.1f MW_th not transferable to "
            "existing_heating_distribution (solar thermal has no stock column; "
            "district-heating substations have no PyPSA component).",
            dropped,
        )

    rows: dict[tuple[str, str], float] = {}

    def _add(heat_name: str, tech: str, value: float) -> None:
        rows[(heat_name, tech)] = rows.get((heat_name, tech), 0.0) + float(value)

    services = transferable[transferable["sector"] == "services"]
    for tech, mw in services.groupby("pypsa_stock_technology")["MW_th"].sum().items():
        _add("services urban decentral", tech, mw)

    residential = transferable[transferable["sector"] != "services"]
    if split_mode == "pypsa":
        for tech, mw in (
            residential.groupby("pypsa_stock_technology")["MW_th"].sum().items()
        ):
            _add("residential rural", tech, mw * pypsa_rural_fraction)
            _add("residential urban decentral", tech, mw * (1 - pypsa_rural_fraction))
    else:
        for (system, tech), mw in (
            residential.groupby(["times_heat_system", "pypsa_stock_technology"])["MW_th"]
            .sum()
            .items()
        ):
            _add(f"residential {system}", tech, mw)

    stock = pd.Series(rows)
    # PyPSA can only site a ground-source heat pump on a rural bus
    # (`heat_pump_sources.urban decentral: [air]`), and
    # `build_existing_heating_distribution` already moves every ground heat pump
    # to rural and every air heat pump to urban decentral. Mirror that, or the
    # capacity is dropped by add_existing_baseyear without a word.
    stock = _fold_heat_pumps_onto_available_buses(stock)
    stock.index = pd.MultiIndex.from_tuples(
        stock.index, names=["heat name", "technology"]
    )
    return stock.sort_index()


def _fold_heat_pumps_onto_available_buses(stock: pd.Series) -> pd.Series:
    """Move heat-pump stock onto the (heat system, source) pairs PyPSA can site.

    ``heat_pump_sources`` lists ``[air, ground]`` for ``rural`` and ``[air]`` for
    ``urban decentral``, and ``build_existing_heating_distribution`` already puts
    every ground heat pump on rural and every air heat pump on urban decentral.
    A pair outside that grid is dropped by ``add_existing_baseyear`` in silence,
    so the same folding is applied here:

    * residential ground → ``residential rural``, residential air →
      ``residential urban decentral``;
    * services stock has only one bus to live on (``write_wallon_heat_demands``
      deletes ``BEWAL services rural``), and only ``air`` is siteable there, so a
      **services ground heat pump becomes a services air heat pump**. That
      re-labels the heat source — 7 MW_th in the reference 2025 stock, 0.03 % of
      the Walloon heat stock — rather than discarding the capacity.
    """
    out = dict(stock)

    ground_on_urban = out.pop(("residential urban decentral", "ground heat pump"), 0.0)
    if ground_on_urban:
        out[("residential rural", "ground heat pump")] = (
            out.get(("residential rural", "ground heat pump"), 0.0) + ground_on_urban
        )
    air_on_rural = out.pop(("residential rural", "air heat pump"), 0.0)
    if air_on_rural:
        out[("residential urban decentral", "air heat pump")] = (
            out.get(("residential urban decentral", "air heat pump"), 0.0) + air_on_rural
        )

    services_ground = out.pop(("services urban decentral", "ground heat pump"), 0.0)
    services_ground += out.pop(("services rural", "ground heat pump"), 0.0)
    if services_ground:
        logger.info(
            "%.1f MW_th of tertiary ground-source heat pump re-labelled as "
            "air-source: PyPSA has no services rural bus and no ground source on "
            "urban decentral.",
            services_ground,
        )
        out[("services urban decentral", "air heat pump")] = (
            out.get(("services urban decentral", "air heat pump"), 0.0) + services_ground
        )
    return pd.Series(out)


def apply_times_base_year_stock(
    existing: pd.DataFrame,
    stock: pd.Series,
    node: str,
) -> pd.DataFrame:
    """Overwrite one node's row of ``existing_heating_distribution`` with TIMES.

    Every ``(heat name, technology)`` column of the frame is written, so a
    technology TIMES does not have is set to zero rather than left at the
    population-scaled EU value: a partial overwrite would mix two inconsistent
    stock estimates on the same bus.

    The node's total is logged before and after — the number to check against
    the peak heat load when judging whether the substitution can bind.
    """
    if node not in existing.index:
        raise KeyError(
            f"{node} is not a node of existing_heating_distribution "
            f"(have {list(existing.index)})"
        )
    out = existing.copy()
    before = out.loc[node].sum()
    out.loc[node, :] = 0.0
    unknown = [key for key in stock.index if key not in out.columns]
    if unknown:
        raise KeyError(
            f"TIMES base-year stock has no matching existing_heating_distribution "
            f"column for {unknown}"
        )
    for key, value in stock.items():
        out.loc[node, key] = value
    logger.info(
        "TIMES base-year heat stock replaces the %s row of "
        "existing_heating_distribution: %.0f MW_th → %.0f MW_th.",
        node,
        before,
        out.loc[node].sum(),
    )
    return out


# --------------------------------------------------------------------------- #
# Energy-mix constraints
# --------------------------------------------------------------------------- #


def decentral_heat_buses(n, node: str) -> pd.Index:
    """The node's ``rural``/``urban decentral`` heat buses (post-clustering)."""
    names = [f"{node} {system} heat" for system in DECENTRAL_HEAT_SYSTEMS]
    return pd.Index([b for b in names if b in n.buses.index])


def _group_carriers(carriers: list[str]) -> list[str]:
    """``["gas boiler"]`` → ``["rural gas boiler", "urban decentral gas boiler"]``."""
    return [
        f"{system} {suffix}"
        for system in DECENTRAL_HEAT_SYSTEMS
        for suffix in carriers
    ]


def heat_injection_terms(
    n, buses: pd.Index, carriers: list[str], component: str
) -> tuple[pd.Index, pd.Series]:
    """Components injecting into ``buses``, and their MWh_th-per-unit coefficient.

    The two orientations in the network need opposite signs:

    * boilers and resistive heaters have ``bus1`` on the heat bus, so the heat
      injected is ``efficiency · p0`` — coefficient ``+efficiency``;
    * heat pumps are **reversed** (``bus0`` is the heat bus, ``p_max_pu = 0``,
      ``p_min_pu = -1``, ``efficiency = 1/COP``), so the heat injected is ``-p0``
      — coefficient ``-1``.

    Generators (solar thermal) inject ``p`` directly — coefficient ``+1``.
    """
    wanted = _group_carriers(carriers)
    if component == "Generator":
        gens = n.generators[
            n.generators.carrier.isin(wanted) & n.generators.bus.isin(buses)
        ]
        return gens.index, pd.Series(1.0, index=gens.index)

    links = n.links[n.links.carrier.isin(wanted)]
    into_bus1 = links[links.bus1.isin(buses)]
    into_bus0 = links[links.bus0.isin(buses)]
    overlap = into_bus0.index.intersection(into_bus1.index)
    if len(overlap):
        raise ValueError(
            f"Links {list(overlap)} touch a decentral heat bus on both ports; the "
            "heat-injection sign is ambiguous."
        )
    coeffs = pd.concat(
        [
            into_bus1["efficiency"].astype(float),
            pd.Series(-1.0, index=into_bus0.index),
        ]
    )
    time_dependent = [
        name for name in into_bus1.index if name in n.links_t.efficiency.columns
    ]
    if time_dependent:
        # A boiler with an hourly efficiency would make the annual coefficient
        # snapshot-dependent; none exists today, and silently using the static
        # value would be wrong if one appeared.
        raise NotImplementedError(
            "Time-dependent efficiency on a heat-injecting link is not supported "
            f"by the annual heat-mix constraint: {time_dependent[:5]}"
        )
    return coeffs.index, coeffs


def group_heat_supply(n, group_terms: dict[str, tuple[pd.Index, pd.Series]], snapshots):
    """Weighted annual heat injection (MWh_th) per group, as linopy expressions."""
    weights = n.snapshot_weightings.generators.loc[snapshots]
    out = {}
    for group, (index, coeffs) in group_terms.items():
        if not len(index):
            continue
        links = index[index.isin(n.links.index)]
        gens = index[index.isin(n.generators.index)]
        expr = None
        if len(links):
            term = (
                n.model["Link-p"].loc[snapshots, links] * coeffs.loc[links]
            ) * weights
            expr = term.sum()
        if len(gens):
            term = (
                n.model["Generator-p"].loc[snapshots, gens] * coeffs.loc[gens]
            ) * weights
            expr = term.sum() if expr is None else expr + term.sum()
        out[group] = expr
    return out


def add_times_heat_mix_constraints(n, snapshots, snakemake) -> None:
    """Impose the TIMES annual heat mix on the Walloon decentral heat buses.

    ``share`` mode (default) constrains each group against the *realised* heat
    supplied by all constrained groups::

        Σ_t w_t · heat_g,t   ⋛   (1 ∓ tol) · share_g · Σ_h Σ_t w_t · heat_h,t

    which is scale-free. That matters: the decentral heat load also carries the
    non-electric cooking fuel, the tertiary "other energy" fuel and the
    agriculture heat that ``write_wallon_heat_demands`` re-buses there — about
    4 % of the load that has no TIMES appliance behind it — and absolute targets
    would hand all of it to whichever technology is cheapest, wrecking the mix
    they are supposed to transfer. ``share`` mode also cannot over-determine the
    system: ``heat_g = share_g · Σ`` satisfies every constraint strictly.

    ``absolute`` mode uses the TIMES MWh directly and is the honest reading of
    "TIMES says gas delivers 14.7 TWh"; it is the stricter, more fragile option.

    Senses come from the payload (``>=`` on what TIMES keeps, ``<=`` on heat
    pumps, which PyPSA over-builds in every horizon), so the constraint reads as
    "the transition is at most this fast" rather than pinning an equality.
    """
    options = times_heat_options(snakemake.config)
    mix = options["energy_mix"]
    if not mix["enable"]:
        return

    targets_path = getattr(snakemake.input, "heating_targets", None)
    if not targets_path:
        raise ValueError(
            "sector.times_heat.energy_mix.enable is true but the solve rule has no "
            "`heating_targets` input. It is declared only when `sector.times_demand` "
            "is true (see input_times_heating_targets in rules/common.smk): a mix "
            "constraint without the TIMES demand transfer would constrain the mix of "
            "a load TIMES never saw."
        )
    if isinstance(targets_path, (list, tuple)):
        targets_path = targets_path[0]
    targets = load_heat_targets(targets_path)

    node = options["node"]
    buses = decentral_heat_buses(n, node)
    if buses.empty:
        logger.warning(
            "No %s decentral heat buses in the network; skipping the TIMES heat-mix "
            "constraints.",
            node,
        )
        return

    slack = set(mix["slack_groups"])
    constrained = targets[targets["constrained"].astype(bool)]

    group_terms: dict[str, tuple[pd.Index, pd.Series]] = {}
    for _, row in constrained.iterrows():
        index, coeffs = heat_injection_terms(
            n, buses, row["carriers"], row["pypsa_component"]
        )
        if not len(index):
            logger.warning(
                "TIMES heat group %r matches no %s on %s; its target of %.4f TWh "
                "cannot be imposed.",
                row["group"],
                row["pypsa_component"],
                list(buses),
                row["TWh"],
            )
            continue
        group_terms[row["group"]] = (index, coeffs)

    if not group_terms:
        logger.warning("No TIMES heat group matched a component; nothing imposed.")
        return

    supply = group_heat_supply(n, group_terms, snapshots)
    total = sum(supply.values())
    tol = mix["tolerance"]
    nyears = n.snapshot_weightings.objective.sum() / 8760.0

    # Soft constraints. A hard `>=` on the TIMES gas share is jointly infeasible
    # with PyPSA's Walloon CO2 cap and EU biomass limit in 2040 — both already
    # bind before any heat constraint is added — and an infeasible sector LP does
    # not merely fail: `solve_network.py` then calls
    # `n.model.compute_infeasibilities()`, a Gurobi IIS on 1.3 M rows that never
    # returns. One horizon can therefore hang a whole myopic chain indefinitely.
    # A per-group slack variable priced at `penalty` EUR/MWh_th removes that
    # failure mode entirely: the mix is met wherever it physically can be (the
    # penalty is ~10-25x the marginal cost of heat, so relaxing is never cheaper
    # than complying), and where it cannot, the slack *is* the answer — "TIMES
    # asks for X TWh_th more gas heat than Wallonia can emit for". See
    # `docs/heat_soft_linking.md`.
    penalty = mix["penalty"]
    groups_to_constrain = [
        row["group"]
        for _, row in constrained.iterrows()
        if row["group"] in supply and row["group"] not in slack
    ]
    slack_var = None
    if penalty > 0 and groups_to_constrain:
        slack_var = n.model.add_variables(
            lower=0.0,
            coords=[pd.Index(groups_to_constrain, name="times_heat_group")],
            name="TimesHeatMix-slack",
        )
        n.model.objective = n.model.objective + (penalty * slack_var).sum()

    def relaxed(group: str, sense: str):
        """The slack term to add to the LHS so `sense` can always be satisfied."""
        if slack_var is None:
            return None
        term = slack_var.sel(times_heat_group=group)
        return term if sense == ">=" else -term

    imposed = []
    for _, row in constrained.iterrows():
        group = row["group"]
        if group not in supply:
            continue
        if group in slack:
            logger.info("TIMES heat group %r left unconstrained (slack).", group)
            continue
        sense = row["sense"]
        target = float(row["share"]) if mix["mode"] == "share" else float(row["TWh"])

        if target <= 0:
            # TIMES has retired the technology. `>= 0` would be vacuous, and
            # leaving it free is where the mix constraint leaks worst: in 2050
            # TIMES has no oil boiler at all while PyPSA builds 0.73 TWh_th of
            # one. Using a technology TIMES has retired is a *slower* transition
            # than TIMES, which is exactly what the `>=` senses exist to bound,
            # so the default is to forbid it. Always feasible — no heat link is
            # must-run.
            if mix["zero_target"] == "free":
                logger.info(
                    "TIMES heat group %r has a zero target and zero_target='free': "
                    "left unconstrained.",
                    group,
                )
                continue
            lhs = supply[group]
            relax = relaxed(group, "<=")
            if relax is not None:
                lhs = lhs + relax
            n.model.add_constraints(lhs <= 0.0, name=f"times_heat_mix_{group}")
            imposed.append((group, "<=", 0.0))
            continue

        factor = (1 - tol) if sense == ">=" else (1 + tol)
        if mix["mode"] == "share":
            lhs = supply[group] - factor * target * total
            rhs = 0.0
        else:
            lhs = supply[group]
            rhs = factor * target * 1e6 * nyears
        relax = relaxed(group, sense)
        if relax is not None:
            lhs = lhs + relax
        if sense == ">=":
            n.model.add_constraints(lhs >= rhs, name=f"times_heat_mix_{group}")
        else:
            n.model.add_constraints(lhs <= rhs, name=f"times_heat_mix_{group}")
        imposed.append((group, sense, factor * target))

    logger.info(
        "TIMES heat-mix constraints (%s mode, tolerance %.0f %%, penalty %s) on %s: %s",
        mix["mode"],
        100 * tol,
        f"{penalty:.0f} EUR/MWh_th" if penalty > 0 else "none (hard constraints)",
        list(buses),
        ", ".join(f"{g} {s} {v:.4g}" for g, s, v in imposed),
    )
