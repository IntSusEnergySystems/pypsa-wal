# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""TIMES → PyPSA heating soft-link, option B': reconstructed hourly profiles.

Option C (:mod:`times_heat_softlink`) bounds the *annual* heat per technology
group and leaves PyPSA free to choose the hours. Option B' pins the hourly
dispatch instead: the TIMES technology shares are combined with PyPSA's own heat
load profile to reconstruct one heat profile per group and bus, and the group's
components are constrained to deliver it.

Why the shape has to come from PyPSA: TIMES-WAL resolves *only electricity*
sub-annually — every heat commodity is ``ANNUAL`` and the timeslice→calendar
mapping is not even in the ``.vd`` (``docs/times-heating-softlink-options.md``
§1.3). So there is no TIMES profile to import; there is a TIMES *composition*,
and PyPSA has the shape.

The reconstruction, per bus ``b`` and snapshot ``t``::

    solar thermal (the one group with a dispatch ceiling):
        rhs_solar,b(t) = s_solar * E_b * a_b(t) / sum_t w_t a_b(t)

    every other group, on the residual:
        rhs_g,b(t)     = s_g / (1 - s_solar) * (L_b(t) - rhs_solar,b(t))

with ``L_b`` the hourly heat load of the bus, ``E_b = sum_t w_t L_b(t)`` its
annual heat, ``a_b`` the solar-thermal collector availability and ``s_g`` the
TIMES share from ``heating_targets_{year}.csv``. Two identities hold exactly and
are asserted rather than assumed:

* ``sum_g rhs_g,b(t) == L_b(t)`` for every bus and snapshot — so the heat-bus
  balance closes by construction and nothing has to absorb a mismatch;
* ``sum_t w_t rhs_g,b(t) == s_g * E_b`` — so the annual mix is TIMES's exactly,
  not TIMES's within a tolerance.

One group (``profile.absorber``, the heat pump by default) is deliberately left
unpinned: the bus balance then determines it, which removes a linearly redundant
equality from the LP, keeps the heat vent / DAC / water tanks free, and gives the
relaxation somewhere physical to go.

Feasibility on the heat bus is structural — ``rhs`` is itself a feasible point,
because every pinned technology is extendable with no dispatch ceiling except
solar thermal, which is pinned to a multiple of its own availability. What can
still bind is *upstream*: the Walloon CO2 cap and the EU solid-biomass limit both
already bind in 2040 before any heat constraint exists. That is what the single
scalar relaxation per group (``profile.penalty``) and the pre-solve budget report
are for.

Full design record, including every arbitrage: ``docs/heat_softlink_option_b.md``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from scripts.walloon_scripts.times_heat_softlink import (
    DECENTRAL_HEAT_SYSTEMS,
    decentral_heat_buses,
    heat_injection_terms,
    load_heat_targets,
    times_heat_options,
)

logger = logging.getLogger(__name__)

#: Group whose profile follows its own availability rather than the heat load.
#: It is the only decentral group with an upper bound on dispatch, so a
#: load-shaped target for it would peak in January and be trivially infeasible.
SOLAR_GROUP = "solar thermal"

#: Relative tolerance for the two closure identities. They are exact in exact
#: arithmetic; this only absorbs float64 rounding over ~10^4 snapshots.
_CLOSURE_RTOL = 1e-9


# --------------------------------------------------------------------------- #
# Reconstruction
# --------------------------------------------------------------------------- #


def decentral_heat_load(n, buses: pd.Index, snapshots) -> pd.DataFrame:
    """Hourly heat load of each decentral bus, in MW.

    Sums every ``Load`` sitting on the bus. ``BEWAL agriculture heat`` is
    re-bussed onto the tertiary decentral bus by ``write_wallon_heat_demands``
    and carries a **static** ``p_set``, so it is absent from ``loads_t.p_set``;
    reading only the time-varying frame would silently drop 0.147 TWh from the
    denominator and break the hourly closure.
    """
    out = pd.DataFrame(0.0, index=pd.Index(snapshots, name="snapshot"), columns=buses)
    for name, bus in n.loads["bus"].items():
        if bus not in buses:
            continue
        if name in n.loads_t.p_set.columns:
            out[bus] += n.loads_t.p_set[name].reindex(snapshots).astype(float)
        else:
            out[bus] += float(n.loads.at[name, "p_set"])
    return out


def solar_availability(n, bus: str, snapshots) -> pd.Series:
    """The bus's solar-thermal collector profile (``p_max_pu``), normalised later.

    Every vintage on a bus shares one profile (verified on the solved networks:
    max pairwise difference 0.0), so a disagreement means the network is not what
    this code assumes and is refused rather than averaged away.
    """
    gens = n.generators.index[
        n.generators.carrier.isin(_solar_carriers()) & n.generators.bus.eq(bus)
    ]
    profiles = [
        n.generators_t.p_max_pu[g].reindex(snapshots).astype(float)
        for g in gens
        if g in n.generators_t.p_max_pu.columns
    ]
    static = [
        float(n.generators.at[g, "p_max_pu"])
        for g in gens
        if g not in n.generators_t.p_max_pu.columns
    ]
    if not profiles and not static:
        raise ValueError(
            f"No solar-thermal generator on {bus!r}: the {SOLAR_GROUP!r} profile "
            "cannot be reconstructed. Either the carrier naming changed or "
            "`sector.solar_thermal` is off — in the latter case give the group a "
            "zero TIMES share or list it in `profile.free_groups`."
        )
    if not profiles:
        return pd.Series(static[0], index=pd.Index(snapshots, name="snapshot"))
    reference = profiles[0]
    for other in profiles[1:]:
        if not np.allclose(reference.values, other.values, rtol=1e-9, atol=1e-12):
            raise ValueError(
                f"Solar-thermal vintages on {bus!r} carry different p_max_pu "
                "profiles; the reconstructed profile would be ambiguous."
            )
    return reference


def _solar_carriers() -> list[str]:
    return [f"{system} {SOLAR_GROUP}" for system in DECENTRAL_HEAT_SYSTEMS]


def reconstruct_profiles(
    load: pd.DataFrame,
    shares: pd.Series,
    availability: pd.DataFrame,
    weightings: pd.Series,
) -> dict[str, pd.DataFrame]:
    """The TIMES mix as one hourly heat profile per group, in MW.

    Parameters
    ----------
    load
        Hourly heat load per decentral bus (snapshots x buses), MW.
    shares
        TIMES share per constraint group. Must sum to 1 — it does by
        construction, because ``times_pypsa.heat_softlink`` normalises the
        constrained groups against their own sum and asserts that every TIMES
        child category is claimed exactly once.
    availability
        Solar-thermal ``p_max_pu`` per bus, same index as ``load``.
    weightings
        Snapshot weightings, in hours.

    Returns
    -------
    dict
        ``{group: DataFrame(snapshots x buses)}``. The two closure identities of
        the module docstring are asserted before returning.
    """
    if abs(float(shares.sum()) - 1.0) > 1e-6:
        raise ValueError(
            f"TIMES heat shares sum to {shares.sum():.6f}, not 1. The target file "
            "was written by an incompatible times_pypsa, or a group was dropped."
        )

    s_solar = float(shares.get(SOLAR_GROUP, 0.0))
    annual = load.mul(weightings, axis=0).sum()  # MWh per bus

    profiles: dict[str, pd.DataFrame] = {}

    solar = pd.DataFrame(0.0, index=load.index, columns=load.columns)
    if s_solar > 0:
        for bus in load.columns:
            avail = availability[bus]
            denominator = float((avail * weightings).sum())
            if denominator <= 0:
                raise ValueError(
                    f"The solar-thermal availability on {bus!r} is zero at every "
                    "snapshot, so its TIMES share cannot be delivered. If this is "
                    "a snapshot subsample, check the stride is coprime with the "
                    "snapshots per day (docs/heat_soft_linking.md §8.5)."
                )
            solar[bus] = s_solar * annual[bus] * avail / denominator
        profiles[SOLAR_GROUP] = solar

    residual = load - solar
    if float(residual.min().min()) < 0:
        worst = residual.min().idxmin()
        raise ValueError(
            f"The reconstructed solar-thermal profile exceeds the heat load on "
            f"{worst!r} at some snapshot (min residual "
            f"{residual.min().min():.2f} MW). The TIMES solar share is too large "
            "for this collector profile; see docs/heat_softlink_option_b.md A3."
        )

    rest = shares.drop(index=SOLAR_GROUP, errors="ignore")
    if rest.sum() <= 0:
        raise ValueError("Every TIMES heat share outside solar thermal is zero.")
    for group, share in rest.items():
        profiles[group] = residual * (float(share) / float(rest.sum()))

    _assert_closure(profiles, load, shares, weightings)
    return profiles


def _assert_closure(
    profiles: dict[str, pd.DataFrame],
    load: pd.DataFrame,
    shares: pd.Series,
    weightings: pd.Series,
) -> None:
    """The two identities the whole formulation rests on."""
    total = sum(profiles.values())
    scale = float(load.abs().to_numpy().max()) or 1.0
    hourly_gap = float((total - load).abs().to_numpy().max())
    if hourly_gap > _CLOSURE_RTOL * scale:
        raise AssertionError(
            f"Reconstructed profiles do not close on the heat load: worst hourly "
            f"gap {hourly_gap:.6g} MW. The bus balance would have to absorb it."
        )
    annual = load.mul(weightings, axis=0).sum().sum()
    for group, frame in profiles.items():
        got = float(frame.mul(weightings, axis=0).sum().sum())
        want = float(shares[group]) * annual
        if abs(got - want) > _CLOSURE_RTOL * max(annual, 1.0):
            raise AssertionError(
                f"Reconstructed profile of {group!r} carries {got / 1e6:.6f} TWh, "
                f"TIMES share implies {want / 1e6:.6f} TWh."
            )


# --------------------------------------------------------------------------- #
# Constraints
# --------------------------------------------------------------------------- #


def _component_dim(variable) -> str:
    """The non-snapshot dimension of a PyPSA linopy variable (``Link``/…)."""
    dims = [d for d in variable.dims if d != "snapshot"]
    if len(dims) != 1:
        raise ValueError(f"Unexpected variable dimensions {variable.dims}")
    return dims[0]


def _snapshot_da(values: pd.Series, snapshots) -> xr.DataArray:
    """A snapshot-indexed coefficient linopy will broadcast unambiguously.

    Multiplying a linopy variable by a bare pandas Series relies on the index
    name surviving; building the DataArray explicitly does not.
    """
    return xr.DataArray(
        values.reindex(snapshots).to_numpy(dtype=float),
        coords={"snapshot": list(snapshots)},
        dims=["snapshot"],
    )


def group_heat_expression(n, index: pd.Index, coeffs: pd.Series, snapshots):
    """Heat injected per snapshot (MW) by a set of components, as an expression.

    ``coeffs`` carries the sign convention of :func:`heat_injection_terms`:
    ``+efficiency`` for a boiler or resistive heater whose ``bus1`` is the heat
    bus, ``-1`` for a reversed heat-pump link whose ``bus0`` is, ``+1`` for a
    solar-thermal ``Generator``. Summing over the component dimension gives one
    term per snapshot; every vintage of every carrier in the group is included,
    so no arbitrary vintage allocation is needed.
    """
    expr = None
    for component, variable_name in (("Link", "Link-p"), ("Generator", "Generator-p")):
        members = index[index.isin(getattr(n, f"{component.lower()}s").index)]
        if not len(members):
            continue
        variable = n.model[variable_name]
        dim = _component_dim(variable)
        coefficient = xr.DataArray(
            coeffs.loc[members].to_numpy(dtype=float),
            coords={dim: list(members)},
            dims=[dim],
        )
        term = (variable.loc[snapshots, members] * coefficient).sum(dim)
        expr = term if expr is None else expr + term
    return expr


def add_times_heat_profile_constraints(n, snapshots, snakemake) -> None:
    """Pin the Walloon decentral heat dispatch to the reconstructed TIMES mix.

    For every group except the absorber, and every decentral heat bus::

        sum_c kappa_c * x_c(t)  +  (rhs_g,b(t) / E_g) * u_g  ==  rhs_g,b(t)
        objective += penalty * sum_g u_g

    ``u_g`` is one scalar per group: the annual heat, in MWh_th, the group could
    not deliver. Spreading it over the year in proportion to the profile is
    deliberate — a per-snapshot slack would let the model relax precisely in the
    expensive hours, i.e. re-create the hourly substitution freedom option B'
    exists to remove. A group whose TIMES share is zero gets ``rhs == 0`` and no
    relaxation variable, which is the ``zero_target: forbid`` behaviour of option
    C for free.
    """
    options = times_heat_options(snakemake.config)
    settings = options["profile"]
    if not settings["enable"]:
        return

    targets_path = getattr(snakemake.input, "heating_targets", None)
    if not targets_path:
        raise ValueError(
            "sector.times_heat.profile.enable is true but the solve rule has no "
            "`heating_targets` input. It is declared only when "
            "`sector.times_demand` is true (see input_times_heating_targets in "
            "rules/common.smk): pinning the mix of a load TIMES never saw would "
            "be meaningless."
        )
    if isinstance(targets_path, (list, tuple)):
        targets_path = targets_path[0]
    targets = load_heat_targets(targets_path)

    node = options["node"]
    buses = decentral_heat_buses(n, node)
    if buses.empty:
        logger.warning(
            "No %s decentral heat buses in the network; skipping the TIMES heat "
            "profile constraints.",
            node,
        )
        return

    constrained = targets[targets["constrained"].astype(bool)].set_index("group")
    shares = constrained["share"].astype(float)

    weightings = n.snapshot_weightings.generators.loc[snapshots]
    load = decentral_heat_load(n, buses, snapshots)
    availability = pd.DataFrame(
        {bus: solar_availability(n, bus, snapshots) for bus in buses}
        if SOLAR_GROUP in shares.index and shares[SOLAR_GROUP] > 0
        else {bus: pd.Series(0.0, index=load.index) for bus in buses}
    )
    profiles = reconstruct_profiles(load, shares, availability, weightings)

    # Keyed on (group, bus): the constraint is written per bus, so that the model
    # cannot sort heat pumps onto the rural bus (the only one with a ground-source
    # option) and gas onto urban decentral — a spatial result that would be driven
    # entirely by the TIMES urban/rural labelling artefact.
    terms = {
        (group, bus): heat_injection_terms(
            n,
            pd.Index([bus]),
            constrained.at[group, "carriers"],
            constrained.at[group, "pypsa_component"],
        )
        for group in profiles
        for bus in buses
    }

    absorber = settings["absorber"]
    free = set(settings["free_groups"])
    if absorber not in profiles:
        raise ValueError(
            f"sector.times_heat.profile.absorber is {absorber!r}, which is not a "
            f"constrained TIMES heat group (have {sorted(profiles)}). The absorber "
            "takes the bus residual, so it must be a real group."
        )
    for (group, bus), (index, _coeffs) in terms.items():
        if len(index):
            continue
        if group == absorber:
            raise ValueError(
                f"The absorber group {absorber!r} has no component on {bus!r}; it "
                "cannot take the bus residual."
            )
        if group in free:
            continue
        raise ValueError(
            f"TIMES heat group {group!r} has no {constrained.at[group, 'pypsa_component']} "
            f"on {bus!r}, so its reconstructed profile "
            f"({float((profiles[group][bus] * weightings).sum()) / 1e6:.4f} TWh) "
            "cannot be delivered. Add it to `profile.free_groups` if that is "
            "intended, or check the carrier naming."
        )

    pinned = [g for g in profiles if g != absorber and g not in free]
    energies = {
        g: float(profiles[g].mul(weightings, axis=0).sum().sum()) for g in profiles
    }

    penalty = settings["penalty"]
    relaxable = [g for g in pinned if energies[g] > 0]
    unmet = None
    if penalty > 0 and relaxable:
        # `upper` as an explicit DataArray: a bare pandas Series arrives with a
        # `dim_0` dimension name, which linopy refuses.
        unmet = n.model.add_variables(
            lower=0.0,
            upper=xr.DataArray(
                [energies[g] for g in relaxable],
                coords={"times_heat_group": list(relaxable)},
                dims=["times_heat_group"],
            ),
            name="TimesHeatProfile-unmet",
        )
        n.model.objective = n.model.objective + (penalty * unmet).sum()

    for group in pinned:
        for bus in buses:
            index, coeffs = terms[(group, bus)]
            if not len(index):
                continue  # free group with no component; already vetted above
            rhs = profiles[group][bus]
            lhs = group_heat_expression(n, index, coeffs, snapshots)
            if unmet is not None and group in relaxable:
                lhs = lhs + unmet.sel(times_heat_group=group) * _snapshot_da(
                    rhs / energies[group], snapshots
                )
            n.model.add_constraints(
                lhs == _snapshot_da(rhs, snapshots),
                name=f"times_heat_profile_{group}_{bus}",
            )

    _log_summary(profiles, energies, shares, absorber, free, pinned, penalty, buses)
    budget_report(n, profiles, terms, energies, weightings, node)
    if settings["export"]:
        export_profiles(profiles, weightings, snakemake)


def _log_summary(
    profiles, energies, shares, absorber, free, pinned, penalty, buses
) -> None:
    total = sum(energies.values())
    logger.info(
        "TIMES heat profiles: %d of %d groups pinned on %s (absorber %r, "
        "penalty %s%s): %s",
        len(pinned),
        len(profiles),
        list(buses),
        absorber,
        f"{penalty:.0f} EUR/MWh_th" if penalty > 0 else "none (hard constraints)",
        f", free {sorted(free)}" if free else "",
        ", ".join(
            f"{g} {energies[g] / 1e6:.4f} TWh ({energies[g] / total:.2%}"
            f"{'' if abs(energies[g] / total - shares[g]) < 1e-9 else ' !'}"
            f"{', absorber' if g == absorber else ''}"
            f"{', free' if g in free else ''})"
            for g in profiles
        ),
    )
    peaks = {g: float(f.sum(axis=1).max()) for g, f in profiles.items()}
    logger.info(
        "Reconstructed profile peaks (MW_th, the capacity each fleet must reach): %s",
        ", ".join(f"{g} {v:.0f}" for g, v in peaks.items()),
    )


# --------------------------------------------------------------------------- #
# Pre-solve diagnostics
# --------------------------------------------------------------------------- #


def budget_report(n, profiles, terms, energies, weightings, node: str) -> None:
    """Fuel and CO2 the pinned profiles imply, against the limits in the network.

    This is the only guard that fires *before* the solver. An infeasible sector
    LP does not merely fail: ``solve_network.py`` reacts to
    ``infeasible_or_unbounded`` by calling ``compute_infeasibilities()``, a Gurobi
    IIS over ~1.3 M rows that ran for 13 h without finishing on the 2040 network
    and blocked the whole myopic chain (``docs/heat_soft_linking.md`` §8.7).

    Never raises: a diagnostic that can break a solve is worse than no
    diagnostic.
    """
    try:
        fuels: dict[str, list[float]] = {}
        for (group, _bus), (index, coeffs) in terms.items():
            links = index[index.isin(n.links.index)]
            for name in links:
                source = n.links.at[name, "bus0"]
                if source in n.buses.index and n.buses.at[source, "carrier"] in (
                    "rural heat",
                    "urban decentral heat",
                ):
                    source = n.links.at[name, "bus1"]  # reversed heat-pump link
                carrier = n.buses.at[source, "carrier"] if source in n.buses.index else "?"
                efficiency = abs(float(coeffs.loc[name])) or 1.0
                fuels.setdefault(f"{group}|{carrier}", []).append(efficiency)

        lines = []
        co2 = 0.0
        for key, efficiencies in sorted(fuels.items()):
            group, carrier = key.split("|", 1)
            heat = energies[group]
            lo, hi = heat / max(efficiencies), heat / min(efficiencies)
            factor = (
                float(n.carriers.at[carrier, "co2_emissions"])
                if carrier in n.carriers.index
                else 0.0
            )
            co2 += factor * hi
            lines.append(
                f"{group}: {heat / 1e6:.3f} TWh_th -> {lo / 1e6:.3f}-{hi / 1e6:.3f} "
                f"TWh of {carrier}"
                + (f", {factor * hi / 1e6:.3f} Mt CO2" if factor else "")
            )
        logger.info("TIMES heat profile budget: %s", "; ".join(lines))

        cap_name = f"co2_limit_per_country{node}"
        if cap_name in n.global_constraints.index:
            cap = float(n.global_constraints.at[cap_name, "constant"])
            logger.info(
                "  decentral heating CO2 (upper estimate) %.3f Mt against the %s "
                "cap of %.3f Mt = %.1f %% of the whole node's budget.",
                co2 / 1e6,
                node,
                cap / 1e6,
                100 * co2 / cap if cap else float("nan"),
            )
            if cap and co2 > 0.8 * cap:
                logger.warning(
                    "The TIMES heating mix alone would use %.0f %% of the %s CO2 "
                    "budget. Expect the profile constraints to relax "
                    "(TimesHeatProfile-unmet) or, with penalty 0, an infeasible LP.",
                    100 * co2 / cap,
                    node,
                )

        _biomass_report(n, energies, weightings, node)
    except Exception:  # pragma: no cover - diagnostics must never break a solve
        logger.warning("TIMES heat profile budget report failed", exc_info=True)


def _biomass_report(n, energies, weightings, node: str) -> None:
    """Solid biomass the biomass-boiler profile needs, against the node's supply."""
    group = "biomass boiler"
    if group not in energies or energies[group] <= 0:
        return
    bus = f"{node} solid biomass"
    if bus not in n.buses.index:
        return
    gens = n.generators[n.generators.bus.eq(bus)]
    hours = float(weightings.sum())
    supply = 0.0
    for name, gen in gens.iterrows():
        cap = float(gen.get("e_sum_max", np.inf))
        if not np.isfinite(cap):
            cap = float(gen.get("p_nom_max", gen.get("p_nom", 0.0)))
            cap = cap * hours if np.isfinite(cap) else np.inf
        supply += cap
    demand = energies[group] / 0.855  # decentral biomass boilers run 0.84-0.87
    other = sum(
        float((n.links_t.p0[name] * weightings).sum())
        for name in n.links.index[n.links.bus0.eq(bus)]
        if name in n.links_t.p0.columns and "biomass boiler" not in n.links.at[name, "carrier"]
    )
    logger.info(
        "  biomass boiler profile needs ~%.3f TWh of solid biomass at %s, whose "
        "own supply caps at %.3f TWh (imports excepted); other users of that bus "
        "took %.3f TWh in the previous solve.",
        demand / 1e6,
        bus,
        supply / 1e6,
        other / 1e6,
    )
    if np.isfinite(supply) and demand + other > supply:
        logger.warning(
            "The biomass-boiler profile plus the existing users of %s exceed its "
            "own supply by %.3f TWh; the balance must be imported, and the EU "
            "solid-biomass limit binds in 2040 and 2050.",
            bus,
            (demand + other - supply) / 1e6,
        )


def export_profiles(profiles, weightings, snakemake) -> None:
    """Write the reconstructed profiles for inspection. Never raises."""
    try:
        frame = pd.concat(
            {group: value for group, value in profiles.items()},
            axis=1,
            names=["group", "bus"],
        )
        path = _export_path(snakemake)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path)
        logger.info("Reconstructed TIMES heat profiles written to %s", path)
    except Exception:  # pragma: no cover - an export must never break a solve
        logger.warning("Could not export the reconstructed heat profiles", exc_info=True)


def _export_path(snakemake) -> Path:
    """Prefer the declared output; fall back to the log directory.

    The solve rule runs under ``shadow``, so an undeclared file written into the
    working directory would be discarded. ``rules/solve_myopic.smk`` therefore
    declares ``heating_profiles`` whenever the option is on; the fallbacks exist
    for ``mock_snakemake`` and for the tests.
    """
    declared = getattr(snakemake.output, "heating_profiles", None)
    if declared:
        return Path(str(declared[0] if isinstance(declared, (list, tuple)) else declared))
    year = getattr(getattr(snakemake, "wildcards", None), "planning_horizons", "")
    name = f"heating_profiles_{year}.csv" if year else "heating_profiles.csv"
    logs = getattr(snakemake, "log", None)
    if logs:
        first = logs[0] if isinstance(logs, (list, tuple)) else logs
        return Path(str(first)).with_name(name)
    network = getattr(snakemake.output, "network", None)
    if network:
        return Path(str(network)).with_name(name)
    return Path(name)
