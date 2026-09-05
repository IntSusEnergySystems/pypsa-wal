# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/PyPSA/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""Reconcile IRENA recent additions with the negotiated base-year pins.

``add_existing_renewables`` distributes IRENASTAT's yearly capacity
differences onto the extendable candidates, and units that already exist in
the network get their share written as ``p_nom``/``p_nom_min``. That
assignment exists "for the year 2020"; with a 2025 base year the grouping
bins the 2021-2024 differences into grouping-year 2025, while the agg caps
file already pins the full 2025 fleet (min = max, ``incl. existing``). Both
cannot hold: in the 2026-09-05 1h run BEWAL entered the solve with 1 802 MW
of forced new utility solar on top of a 2 286 MW standing fleet, against a
2 668 MW pin — and the max branch can only clip its ceiling *up* to the
forced floor, never down, so the review failed four ``aggregate max
exceeded`` checks on an otherwise optimal run.

Wherever the caps file carries a collapsed (min = max) base-year pin for a
(node, carrier) group, this scales the rows binned into the base-year
grouping down to the pin headroom (``pin - standing``), or drops them when
the standing fleet already covers the pin. Groups without a pin are
untouched, so every other country keeps the upstream behaviour.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

#: df_agg Fueltype (IRENA technology) -> agg caps file carrier group
FUELTYPE_TO_GROUP = {
    "solar": "solar-all",
    "onwind": "onwind",
    "offwind": "offwind-all",
    "offwind-ac": "offwind-all",
    "offwind-dc": "offwind-all",
    "offwind-float": "offwind-all",
}


def baseyear_pins(agg_file: str, baseyear: int) -> dict[tuple[str, str], float]:
    """{(node, group): MW} for every collapsed base-year pin in the caps file."""
    header = pd.read_csv(agg_file, nrows=2, header=None)
    years = [str(y) for y in header.iloc[0, 2:].tolist()]
    kinds = [str(k) for k in header.iloc[1, 2:].tolist()]
    cols = {}
    for pos, (year, kind) in enumerate(zip(years, kinds)):
        if year == str(int(baseyear)) and kind in ("min", "max"):
            cols[kind] = pos + 2
    if "min" not in cols or "max" not in cols:
        return {}
    data = pd.read_csv(agg_file, skiprows=3, header=None, index_col=[0, 1])
    out = {}
    for (node, carrier), row in data.iterrows():
        lo, hi = row[cols["min"]], row[cols["max"]]
        if pd.isna(lo) or pd.isna(hi) or float(lo) != float(hi):
            continue
        out[(str(node), str(carrier))] = float(lo)
    return out


def reconcile_baseyear_forced_build(
    df_agg: pd.DataFrame,
    agg_file: str,
    baseyear: int,
    grouping_years: list[int],
) -> pd.DataFrame:
    """Scale base-year-grouped renewable rows down to the pin headroom.

    Modifies ``df_agg`` in place and returns it. ``grouping_years`` is the
    same binning ``add_power_capacities_installed_before_baseyear`` applies
    (``np.digitize(DateIn, grouping_years, right=True)``): rows landing in
    the base-year bin are the forced new build this reconciles.
    """
    pins = baseyear_pins(agg_file, baseyear)
    if not pins:
        return df_agg
    df_agg["DateIn"] = pd.to_numeric(df_agg["DateIn"])
    bins = np.take(
        list(grouping_years),
        np.digitize(df_agg["DateIn"], list(grouping_years), right=True),
    )
    df_agg["_grouping_year"] = bins
    try:
        for (bus, fuel), group in df_agg.groupby(["bus", "Fueltype"]):
            pin = pins.get((str(bus), FUELTYPE_TO_GROUP.get(str(fuel), "")))
            if pin is None:
                continue
            forced = group.index[group["_grouping_year"] == int(baseyear)]
            if forced.empty:
                continue
            # Same aliveness rule as the phased_out drop below: rows without
            # a DateOut (the IRENA rows just added) survive.
            alive = group["DateOut"].isna() | (
                group["DateOut"] >= int(baseyear)
            )
            standing = float(
                group.loc[(group["_grouping_year"] < int(baseyear)) & alive][
                    "Capacity"
                ].sum()
            )
            forced_sum = float(group.loc[forced, "Capacity"].sum())
            if forced_sum <= 0:
                continue
            headroom = pin - standing
            if headroom >= forced_sum:
                continue
            if headroom <= 0:
                logger.warning(
                    "Base-year reconciliation: standing %s %s (%.0f MW) already "
                    "covers the %.0f MW pin — dropping %.0f MW of forced "
                    "%s additions. Check the pin against the fleet source.",
                    bus,
                    fuel,
                    standing,
                    pin,
                    forced_sum,
                    baseyear,
                )
                df_agg.drop(forced, inplace=True)
            else:
                factor = headroom / forced_sum
                logger.info(
                    "Base-year reconciliation: scaling %s %s %s additions by "
                    "%.3f (%.0f MW of %.0f MW headroom under the pin).",
                    bus,
                    fuel,
                    baseyear,
                    factor,
                    headroom,
                    pin,
                )
                df_agg.loc[forced, "Capacity"] = (
                    df_agg.loc[forced, "Capacity"] * factor
                )
    finally:
        df_agg.drop(columns=["_grouping_year"], inplace=True, errors="ignore")
    return df_agg
