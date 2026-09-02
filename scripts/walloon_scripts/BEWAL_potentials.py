# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
# SPDX-FileCopyrightText: Open Energy Transition gGmbH
#
# SPDX-License-Identifier: MIT

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Typical duration of Belgian TSO-connected BESS (Vilvoorde, Navagne, Storm, …).
UTILITY_BATTERY_HOURS = 4.0


def _utility_battery_chargers(n, bus):
    """Charger links of the utility battery at `bus` (not home batteries)."""
    if n.links.empty:
        return n.links.iloc[0:0]
    mask = (
        n.links.carrier.str.contains("battery charger", na=False)
        & ~n.links.carrier.str.contains("home", na=False)
        & (n.links.bus0 == bus)
    )
    return n.links.loc[mask]


def _utility_battery_dischargers(n, bus):
    if n.links.empty:
        return n.links.iloc[0:0]
    mask = (
        n.links.carrier.str.contains("battery discharger", na=False)
        & ~n.links.carrier.str.contains("home", na=False)
        & (n.links.bus1 == bus)
    )
    return n.links.loc[mask]


def _utility_battery_stores(n, bus):
    if n.stores.empty:
        return n.stores.iloc[0:0]
    prefix = f"{bus} battery"
    mask = (
        (n.stores.carrier == "battery")
        & n.stores.index.str.startswith(prefix)
        & ~n.stores.index.str.contains("home", na=False)
    )
    return n.stores.loc[mask]


def _current_horizon_index(index, bus, kind, planning_horizons):
    """Names of the current-horizon asset: `{bus} {kind}` or `{bus} {kind}-{year}`."""
    year = str(int(planning_horizons))
    exact = f"{bus} {kind}"
    vintage = f"{bus} {kind}-{year}"
    return index[(index == exact) | (index == vintage)]


def _link_fleet(n, bus, carrier):
    """Every vintage of `carrier` links whose electricity bus is `bus`."""
    if n.links.empty:
        return n.links.iloc[0:0]
    mask = (n.links.carrier == carrier) & (
        n.links.index.str.startswith(f"{bus} {carrier}-")
        | (n.links.index == f"{bus} {carrier}")
    )
    return n.links.loc[mask]


def apply_link_p_nom_min(n, bus, carrier, p_min, planning_horizons, electrical=True):
    """Force a *fleet* floor on the `carrier` links at `bus`.

    Earlier vintages already contribute to the floor, so only the
    current-horizon extendable link has to cover the residual. Writing the full
    floor onto every new vintage instead makes the fleet grow by `p_min` at
    each myopic horizon.

    `p_min` is MW_el when `electrical` (the link `p_nom` is on the fuel bus, so
    it is divided by the efficiency on the way in), otherwise MW of `p_nom`.
    """
    p_min = float(p_min)
    fleet = _link_fleet(n, bus, carrier)
    current = _current_horizon_index(fleet.index, bus, carrier, planning_horizons)

    if current.empty:
        logger.warning(
            "No %s link at bus %s for horizon %s; cannot apply p_nom_min=%.0f.",
            carrier,
            bus,
            planning_horizons,
            p_min,
        )
        return

    older = fleet.drop(index=current)
    if electrical:
        existing = float((older.p_nom * older.efficiency).sum())
    else:
        existing = float(older.p_nom.sum())
    residual = max(p_min - existing, 0.0)

    if electrical:
        efficiency = float(n.links.loc[current, "efficiency"].iloc[0])
        n.links.loc[current, "p_nom_min"] = residual / efficiency
    else:
        n.links.loc[current, "p_nom_min"] = residual

    logger.info(
        "%s floor at %s: %.0f MW%s total (existing %.0f, current-horizon "
        "residual %.0f).",
        carrier,
        bus,
        p_min,
        "_el" if electrical else "",
        existing,
        residual,
    )


def apply_battery_p_nom_min(n, bus, p_min_mw, planning_horizons):
    """Force a fleet floor on the utility battery at `bus`.

    Existing vintages (other years) already contribute to the floor, so the
    current-horizon extendable charger/discharger/store only has to cover the
    residual. Energy floor is 4 h × residual power (Belgian utility BESS).
    """
    p_min_mw = float(p_min_mw)
    chargers = _utility_battery_chargers(n, bus)
    dischargers = _utility_battery_dischargers(n, bus)
    stores = _utility_battery_stores(n, bus)

    cur_ch = _current_horizon_index(
        chargers.index, bus, "battery charger", planning_horizons
    )
    cur_dis = _current_horizon_index(
        dischargers.index, bus, "battery discharger", planning_horizons
    )
    cur_st = _current_horizon_index(
        stores.index, bus, "battery", planning_horizons
    )

    if cur_ch.empty and cur_dis.empty and cur_st.empty:
        logger.warning(
            "No utility battery at bus %s for horizon %s; "
            "cannot apply p_nom_min=%.0f MW.",
            bus,
            planning_horizons,
            p_min_mw,
        )
        return

    existing_p = float(chargers.drop(index=cur_ch, errors="ignore").p_nom.sum())
    residual_p = max(p_min_mw - existing_p, 0.0)
    if not cur_ch.empty:
        n.links.loc[cur_ch, "p_nom_min"] = residual_p
    if not cur_dis.empty:
        n.links.loc[cur_dis, "p_nom_min"] = residual_p

    existing_e = float(stores.drop(index=cur_st, errors="ignore").e_nom.sum())
    residual_e = max(p_min_mw * UTILITY_BATTERY_HOURS - existing_e, 0.0)
    if not cur_st.empty:
        n.stores.loc[cur_st, "e_nom_min"] = residual_e

    logger.info(
        "Battery floor at %s: %.0f MW total (existing %.0f MW, "
        "current-horizon p_nom_min %.0f MW, e_nom_min %.0f MWh).",
        bus,
        p_min_mw,
        existing_p,
        residual_p,
        residual_e,
    )


def apply_gas_store_cap(n, bus, attr, value):
    """Write `attr` on the gas Store at `bus`.

    `prepare_sector_network.add_carrier_buses` creates one extendable gas Store
    per gas bus with `e_nom_max = inf`, and `add_gas_network` then writes
    `e_nom_min` from the SciGRID_gas inventory. Neither is a site-specific
    ceiling: a region with no underground store at all still gets an unbounded
    one, and the optimiser will happily build a seasonal inventory there. A
    region without the geology therefore needs the ceiling written here.

    The store has `lifetime = inf`, so `add_brownfield` drops it from the
    previous network and `prepare_sector_network` rebuilds it unconstrained at
    every horizon — the cap has to be re-applied each time, which is what the
    per-year rows in `custom_potentials.csv` do.
    """
    name = f"{bus} gas Store"
    if name not in n.stores.index:
        logger.warning(
            "No gas Store at bus %s; cannot apply %s=%s.", bus, attr, value
        )
        return

    n.stores.loc[name, attr] = value

    if attr == "e_nom_max":
        # an inherited floor above the new ceiling would be infeasible
        for floor in ["e_nom_min", "e_nom"]:
            if n.stores.at[name, floor] > value:
                n.stores.loc[name, floor] = value

    logger.info("Gas store at %s: %s = %s MWh_LHV.", bus, attr, value)


def apply_co2_store_cap(n, bus, attr, value):
    """Write `attr` on the `co2 sequestered` Store(s) at `bus`.

    `prepare_sector_network` builds one extendable Store per CO₂ node from
    the clustered CO2StoP CSV, then ``reindex(...).fillna(0.0)``. Belgian
    nodes have no offshore site that clears `min_size`, so they land at 0
    unless a documented value is written here. That silent zero is
    improvement-plan item 2; this function is the documented override.

    Value is in tonnes of CO₂ (the Store's native unit). `e_nom_max` is the
    annualised injection ceiling after `years_of_storage`, not the geological
    stock.

    Myopic brownfield vintages the name (``BEWAL co2 sequestered-2025``), so
    matching is by carrier and bus, not by the un-suffixed index. The ceiling
    is a fleet cap: inherited vintages keep their ``e_nom``, and the residual
    is written on the current extendable vintage.
    """
    bus_name = f"{bus} co2 sequestered"
    sel = n.stores.index[
        n.stores.carrier.astype(str).eq("co2 sequestered")
        & n.stores.bus.astype(str).eq(bus_name)
    ]
    if sel.empty:
        logger.warning(
            "No co2 sequestered Store at bus %s; cannot apply %s=%s.",
            bus,
            attr,
            value,
        )
        return

    if attr != "e_nom_max":
        n.stores.loc[sel, attr] = value
        logger.info("CO2 sequestered store at %s: %s = %s t.", bus, attr, value)
        return

    cap = float(value)
    # A documented zero is a fleet ban, including inherited brownfield vintages
    # (TIMES 7.1 Mt/a must not survive as e_nom on a 2025 store).
    if cap <= 0.0:
        n.stores.loc[sel, "e_nom_max"] = 0.0
        for floor in ["e_nom_min", "e_nom"]:
            n.stores.loc[sel, floor] = n.stores.loc[sel, floor].clip(upper=0.0)
        logger.info(
            "CO2 sequestered store at %s: e_nom_max = 0 t (documented zero).",
            bus,
        )
        return

    extendable = sel[n.stores.loc[sel, "e_nom_extendable"].fillna(False).astype(bool)]
    inherited = sel.difference(extendable)
    existing = (
        float(n.stores.loc[inherited, "e_nom"].sum()) if len(inherited) else 0.0
    )
    residual = max(cap - existing, 0.0)
    targets = extendable if len(extendable) else sel
    n.stores.loc[targets, "e_nom_max"] = residual
    for floor in ["e_nom_min", "e_nom"]:
        too_high = n.stores.loc[targets, floor] > residual
        if too_high.any():
            n.stores.loc[too_high.index[too_high], floor] = residual

    logger.info(
        "CO2 sequestered store at %s: e_nom_max = %s t "
        "(fleet cap %s t, inherited %s t).",
        bus,
        residual,
        cap,
        existing,
    )


def apply_process_emission_load(n, bus, kt_per_year):
    """Set the process-emissions Load at `bus` to an annual TIMES volume.

    Item 12: the Load is gross process CO₂ (t/h, negative p_set injects onto
    the process-emissions bus). ``kt_per_year`` is fossil ``INDCO2`` only
    (Annick / ``VAR_Comnet``); biogenic ``INDCO2b`` stays off this bus.
    Capture is a different object (item 9).
    """
    name = f"{bus} process emissions"
    if name not in n.loads.index:
        logger.warning(
            "No process-emissions Load at %s; cannot apply %s kt/a.",
            bus,
            kt_per_year,
        )
        return
    weights = n.snapshot_weightings
    if "objective" in weights.columns:
        nhours = float(weights["objective"].sum())
    else:
        nhours = float(weights.iloc[:, 0].sum())
    if nhours <= 0:
        logger.warning("snapshot weightings sum to 0; cannot apply process emissions.")
        return
    t_year = float(kt_per_year) * 1e3
    p_set = -t_year / nhours
    n.loads.loc[name, "p_set"] = p_set
    if name in n.loads_t.p_set.columns:
        n.loads_t.p_set[name] = p_set
    logger.info(
        "Process-emissions load at %s: %.2f kt/a (p_set = %.4f t/h).",
        bus,
        kt_per_year,
        p_set,
    )


def update_BEWAL_potentials(n, planning_horizons, walloon_potentials=None):
    if walloon_potentials == None:
        return

    potentials = pd.read_csv(
        walloon_potentials, dtype={"year": int, "value": str}
    ).query("year == @planning_horizons")

    if "technology" not in potentials.columns:
        potentials = potentials.rename(
            columns={potentials.columns[0]: "technology"}
        )

    for _, row in potentials.iterrows():
        attr = row["parameter"]
        carrier = row["technology"]
        unit = str(row.get("unit", ""))
        raw_value = row.get("value")
        bus_value = row.get("bus")
        bus = (
            "BEWAL" if pd.isna(bus_value) else str(bus_value)
        )  # default bus is "BEWAL" if not specified

        if isinstance(raw_value, str):
            if raw_value.strip().lower() == "inf":
                potential = np.inf
            elif raw_value in ["TRUE", "true", "True"]:
                potential = True
            elif raw_value in ["FALSE", "false", "False"]:
                potential = False
            else:
                potential = float(raw_value)
        else:
            potential = float(raw_value)

        if np.isfinite(potential) and ("GW" in unit or "GWh" in unit):
            potential = potential * 1000  # convert to MW or MWh

        logger_msg_success = (
            f"Overwriting exogenously given potentials for {carrier} on bus {bus}."
        )
        logger_msg_failure = (
            f"{carrier} is currently not a supported or valid technology."
        )
        if carrier == "offwind":
            carriers_to_update = ["offwind-ac", "offwind-dc", "offwind-float"]
        elif carrier in n.generators.carrier.unique() and carrier not in [
            "solid biomass",
            "biogas",
        ]:
            carriers_to_update = [carrier]
        else:
            carriers_to_update = []

        if carriers_to_update:
            region_carrier_idx = []
            for tech in carriers_to_update:
                bus_mask = n.generators.bus == bus
                carrier_mask = n.generators.carrier == tech
                idx = n.generators[bus_mask & carrier_mask].index

                gen_name = f"{bus} 0 {tech}-{planning_horizons}"
                if gen_name in n.generators.index:
                    idx = pd.Index([gen_name])

                if not idx.empty:
                    region_carrier_idx.extend(idx.tolist())

            if len(region_carrier_idx) == 0:
                continue
            if region_carrier_idx:
                allowed = {"p_nom", "p_nom_max", "p_nom_min"}
                assert attr in allowed, f"Unsupported attr: {attr!r}; expected one of {', '.join(sorted(allowed))}"
                logger.info(logger_msg_success)
                n.generators.loc[region_carrier_idx, attr] = potential
            continue

        if carrier in ["solid biomass", "biogas"]:
            logger.info(logger_msg_success)
            if carrier == "biogas":
                unsustainable_idx = f"BEWAL {carrier} unsustainable"
            else:
                unsustainable_idx = f"BEWAL unsustainable {carrier}"

            allowed = "p_nom"
            assert attr == allowed, f"Unsupported attr: {attr!r}; expected {allowed!r}"
            pypsa_eur_potential = n.generators.loc[f"BEWAL {carrier}", attr]
            if pypsa_eur_potential <= potential and carrier == "solid biomass":
                if "unsustainable biomass limit" in n.global_constraints.index:
                    n.generators.loc[unsustainable_idx, [attr, "e_sum_max"]] = (
                        potential - pypsa_eur_potential
                    )
                    limit = n.global_constraints.loc[
                        "unsustainable biomass limit", "constant"
                    ]
                    n.global_constraints.loc[
                        "unsustainable biomass limit", "constant"
                    ] = limit - pypsa_eur_potential + potential
            elif carrier == "solid biomass":
                if "unsustainable biomass limit" in n.global_constraints.index:
                    limit = n.global_constraints.loc[
                        "unsustainable biomass limit", "constant"
                    ]
                    n.global_constraints.loc[
                        "unsustainable biomass limit", "constant"
                    ] = limit - n.generators.loc[unsustainable_idx, attr]
                if unsustainable_idx in n.generators.index:
                    n.generators.loc[unsustainable_idx, [attr, "e_sum_max"]] = 0
            n.generators.loc[f"BEWAL {carrier}", [attr, "e_sum_max"]] = potential
            # what about ["BEWAL solid biomass transported", "BEWAL unsustainable solid biomass transported"] ?
            # what about ["BEWAL solid biomass transported", "BEWAL unsustainable solid biomass transported"] ?
        elif carrier == "solid biomass import":
            # remove all solid biomass imports except the one for BEWAL
            # and set the import potential to the one given for BEWAL
            logger.info(logger_msg_success)
            biomass_imports = n.stores.query("carrier == @carrier")

            allowed = "e_nom"
            assert attr == allowed, f"Unsupported attr: {attr!r}; expected {allowed!r}"
            n.stores.loc[
                biomass_imports.index,
                ["e_nom_min", attr, "e_nom_max", "e_initial"],
            ] = potential

            biomass_imports = biomass_imports.bus.values
            biomass_imports = n.links.query("bus0 in @biomass_imports").index
            drop_non_BEWAL_imports = [
                link for link in biomass_imports if "BEWAL" not in link
            ]
            n.remove("Link", drop_non_BEWAL_imports)
        elif carrier == "solid biomass transported":
            allowed = "e_sum_max"
            assert attr == allowed, f"Unsupported attr: {attr!r}; expected {allowed!r}"
            logger.info(logger_msg_success)

            sustainable_idx = "BEWAL solid biomass transported"
            unsustainable_idx = "BEWAL unsustainable solid biomass transported"

            if sustainable_idx not in n.generators.index:
                logger.warning(
                    "No BEWAL solid biomass transported generators found; "
                    "skipping transported biomass potential overwrite.",
                )
                continue

            # Cap the annual imported biomass energy (pellets) to the provided potential.
            # Enforce the limit on the sustainable generator and disable
            # the unsustainable copy so that the total transported energy cannot exceed
            # the given GWh/an value.
            n.generators.loc[sustainable_idx, attr] = potential
            if unsustainable_idx in n.generators.index:
                n.generators.loc[unsustainable_idx, ["p_nom", attr]] = 0
        if carrier == "battery":
            allowed = {"p_nom_min"}
            assert attr in allowed, (
                f"Unsupported attr: {attr!r}; expected one of {', '.join(sorted(allowed))}"
            )
            logger.info(logger_msg_success)
            apply_battery_p_nom_min(n, bus, potential, planning_horizons)
            continue
        if carrier == "gas storage":
            allowed = {"e_nom", "e_nom_min", "e_nom_max"}
            assert attr in allowed, (
                f"Unsupported attr: {attr!r}; expected one of {', '.join(sorted(allowed))}"
            )
            logger.info(logger_msg_success)
            apply_gas_store_cap(n, bus, attr, potential)
            continue
        if carrier in ("co2 storage", "co2 sequestered"):
            allowed = {"e_nom", "e_nom_min", "e_nom_max"}
            assert attr in allowed, (
                f"Unsupported attr: {attr!r}; expected one of {', '.join(sorted(allowed))}"
            )
            logger.info(logger_msg_success)
            if "Mt" in unit:
                potential = potential * 1e6  # t
            apply_co2_store_cap(n, bus, attr, potential)
            continue
        if carrier == "process emissions":
            allowed = {"p_set"}
            assert attr in allowed, (
                f"Unsupported attr: {attr!r}; expected one of {', '.join(sorted(allowed))}"
            )
            logger.info(logger_msg_success)
            kt = potential
            unit_l = unit.lower()
            if "mt" in unit_l:
                kt = potential * 1e3
            apply_process_emission_load(n, bus, kt)
            continue
        if carrier in ["CCGT", "CCGT CC"]:
            allowed = {"p_nom", "p_nom_extendable", "p_nom_min", "p_nom_max"}
            assert attr in allowed, f"Unsupported attr: {attr!r}; expected one of {', '.join(sorted(allowed))}"

            if attr == "p_nom_min":
                # fleet floor, not a per-vintage floor
                apply_link_p_nom_min(
                    n,
                    bus,
                    carrier,
                    potential,
                    planning_horizons,
                    electrical="el" in unit,
                )
                continue

            link_name = f"{bus} {carrier}-{planning_horizons}"
            if "el" in unit:
                potential = potential / n.links.loc[link_name, "efficiency"]
            n.links.loc[link_name, attr] = potential
        else:
            logger.warning(logger_msg_failure)
