# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Before/after report for the TIMES heating soft-link (option C).

Reads the two archives written by ``run_heat_softlink_comparison.sh`` and prints
Markdown tables ready to paste into ``docs/heat_soft_linking.md``:

* the decentral heat mix per horizon, against the TIMES target;
* installed decentral heat capacity;
* system objective and Walloon CO₂;
* the knock-on effects outside heating (electricity demand, gas and biomass use)
  — the part a mix constraint is *not* supposed to touch, and therefore the part
  worth checking.

Usage::

    python scripts/walloon_scripts/compare_heat_softlink.py [scenario]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.walloon_scripts.times_heat_softlink import (  # noqa: E402
    decentral_heat_buses,
    heat_injection_terms,
)

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "scen_demande_haute"
ARCHIVE = Path("results/_heat_softlink_comparison")
RESOURCES = Path("resources/times-pypsa") / SCENARIO
HORIZONS = [2025, 2030, 2040, 2050]
NODE = "BEWAL"
PHASES = ["before", "after"]


def load(phase: str, year: int) -> pypsa.Network:
    return pypsa.Network(ARCHIVE / phase / "networks" / f"base_s_adm___{year}.nc")


def targets(year: int) -> pd.DataFrame:
    return pd.read_csv(RESOURCES / f"heating_targets_{year}.csv")


def heat_mix(n: pypsa.Network, tgt: pd.DataFrame) -> pd.Series:
    """Annual heat delivered to the decentral buses per constraint group, TWh_th."""
    buses = decentral_heat_buses(n, NODE)
    w = n.snapshot_weightings.generators
    out = {}
    for _, row in tgt[tgt["constrained"]].iterrows():
        carriers = [c.strip() for c in str(row["pypsa_carriers"]).split(";") if c.strip()]
        index, coeffs = heat_injection_terms(n, buses, carriers, row["pypsa_component"])
        p = n.links_t.p0 if row["pypsa_component"] == "Link" else n.generators_t.p
        out[row["group"]] = float((p[index] * coeffs).mul(w, axis=0).to_numpy().sum()) / 1e6
    return pd.Series(out)


def unmet_mix(realised: pd.Series, tgt: pd.DataFrame, tolerance: float = 0.05) -> pd.Series:
    """TWh_th by which the realised mix misses its constraint bound.

    The penalty slack variable (`TimesHeatMix-slack`) is a bare linopy variable, so
    PyPSA cannot map it to a component and it is **not written to the netCDF** — the
    number has to be reconstructed. That is straightforward and in fact more robust
    than reading the solver's own value: in `share` mode the bound is
    ``(1 ∓ tol) · share_g · Σ_h supply_h`` on the *realised* total, so the shortfall
    is just the signed distance from it. A non-zero entry here is the honest
    statement "TIMES asks for this much more than Wallonia could deliver".
    """
    total = realised.sum()
    out = {}
    for group, value in realised.items():
        row = tgt.loc[group]
        share = float(row["share"])
        sense = str(row["sense"])
        if share <= 0:
            out[group] = max(0.0, value) if sense != ">=" else 0.0
            continue
        factor = (1 - tolerance) if sense == ">=" else (1 + tolerance)
        bound = factor * share * total
        out[group] = max(0.0, bound - value) if sense == ">=" else max(0.0, value - bound)
    return pd.Series(out)


def decentral_capacity(n: pypsa.Network) -> pd.Series:
    """Installed decentral heat capacity, MW thermal output."""
    buses = set(decentral_heat_buses(n, NODE))
    links = n.links[
        n.links.index.str.startswith(NODE)
        & (n.links.bus0.isin(buses) | n.links.bus1.isin(buses))
        & ~n.links.carrier.str.contains("water tanks|DAC", case=False, na=False)
    ]
    mw = [
        row.p_nom_opt if row.bus0 in buses else row.p_nom_opt * row.efficiency
        for _, row in links.iterrows()
    ]
    return links.assign(MW_th=mw).groupby("carrier")["MW_th"].sum()


def _link_port_flow(n: pypsa.Network, bus: str) -> float:
    """MWh withdrawn from ``bus`` by links, summed over every port.

    PyPSA defines ``p_i`` as the power *withdrawn from* ``bus_i``, so the sum over
    all ports touching a bus is the withdrawal regardless of link orientation.
    Looping over ports matters here: a heat pump is a reversed link whose
    electricity consumption appears on **bus1**, so a ``bus0``-only sum silently
    drops the entire heat-pump electricity demand — which is exactly the quantity
    this comparison is meant to show moving.
    """
    total = 0.0
    for port in range(0, 6):
        bus_col, p_col = f"bus{port}", f"p{port}"
        if bus_col not in n.links.columns or p_col not in n.links_t:
            continue
        sel = n.links.index[n.links[bus_col] == bus].intersection(
            n.links_t[p_col].columns
        )
        if not len(sel):
            continue
        total += float(
            n.links_t[p_col][sel]
            .mul(n.snapshot_weightings.generators, axis=0)
            .to_numpy()
            .sum()
        )
    return total


def walloon_co2(n: pypsa.Network) -> float:
    """Mt CO₂ emitted to the atmosphere by links located in the node.

    Sign: ``p_i`` is the withdrawal from ``bus_i``, so a link that *emits* into
    ``co2 atmosphere`` shows a negative flow on that port. Negated here so the
    reported figure is positive for emissions and negative for removals (DAC).
    """
    mwh = 0.0
    for port in range(1, 6):
        bus_col, p_col = f"bus{port}", f"p{port}"
        if bus_col not in n.links.columns or p_col not in n.links_t:
            continue
        sel = n.links.index[
            (n.links[bus_col] == "co2 atmosphere")
            & n.links.index.str.startswith(NODE)
        ].intersection(n.links_t[p_col].columns)
        if not len(sel):
            continue
        mwh += float(
            n.links_t[p_col][sel]
            .mul(n.snapshot_weightings.generators, axis=0)
            .to_numpy()
            .sum()
        )
    return -mwh / 1e6


#: Carrier suffix → the input the decentral heat technology draws.
HEAT_INPUT_CARRIERS = {
    "electricity": ["air heat pump", "ground heat pump", "resistive heater"],
    "gas": ["gas boiler"],
    "oil": ["oil boiler"],
    "solid biomass": ["biomass boiler"],
}


def heat_inputs(n: pypsa.Network) -> pd.Series:
    """Fuel and electricity drawn by the decentral heat technologies, TWh.

    Measured on the technologies themselves rather than at their supply bus. A
    bus-wide sum over every link port is the *nodal balance* and is therefore ~0 by
    construction — the first version of this table read 0.000 TWh for three
    horizons for exactly that reason. Heat pumps also draw on **bus1** (they are
    reversed links), so the port has to be found per link rather than assumed.
    """
    buses = set(decentral_heat_buses(n, NODE))
    w = n.snapshot_weightings.generators
    out = {}
    for label, suffixes in HEAT_INPUT_CARRIERS.items():
        wanted = [
            f"{system} {suffix}"
            for system in ("rural", "urban decentral")
            for suffix in suffixes
        ]
        # Restricting by carrier alone is NOT enough: `rural gas boiler` exists in
        # every country, so a carrier-only filter silently sums DE/FR/GB/NL/LU as
        # well (64 links instead of 8, and ~80x the gas). The node is identified by
        # requiring one port to be a BEWAL decentral heat bus.
        links = n.links[
            n.links.carrier.isin(wanted)
            & (n.links.bus0.isin(buses) | n.links.bus1.isin(buses))
        ]
        total = 0.0
        for name, row in links.iterrows():
            # the port that is NOT the heat bus is the input side
            for port in range(0, 6):
                bus_col, p_col = f"bus{port}", f"p{port}"
                if bus_col not in links.columns or p_col not in n.links_t:
                    continue
                if row[bus_col] in buses or not row[bus_col]:
                    continue
                if name not in n.links_t[p_col].columns:
                    continue
                flow = float((n.links_t[p_col][name] * w).sum())
                if flow > 0:  # positive = withdrawal from that bus
                    total += flow
        out[label] = total / 1e6
    return pd.Series(out)


def md(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    body = df.copy()
    for c in body.columns:
        if pd.api.types.is_numeric_dtype(body[c]):
            body[c] = body[c].map(lambda v: floatfmt.format(v))
    head = "| " + " | ".join([body.index.name or ""] + list(body.columns)) + " |"
    rule = "|" + "|".join(["---"] * (len(body.columns) + 1)) + "|"
    rows = [
        "| " + " | ".join([str(i)] + list(r)) + " |" for i, r in body.iterrows()
    ]
    return "\n".join([head, rule, *rows])


def main() -> None:
    missing = [
        p for p in PHASES if not (ARCHIVE / p / "networks").is_dir()
    ]
    if missing:
        raise SystemExit(
            f"Archive incomplete: {missing}. Run "
            "scripts/walloon_scripts/run_heat_softlink_comparison.sh first."
        )

    print(f"# Heating soft-link before/after — {SCENARIO}\n")

    print("## Decentral heat mix, share of supply\n")
    for year in HORIZONS:
        tgt = targets(year).set_index("group")
        rows = {}
        for phase in PHASES:
            s = heat_mix(load(phase, year), targets(year))
            rows[f"{phase} TWh"] = s
            rows[f"{phase} %"] = 100 * s / s.sum()
        tbl = pd.DataFrame(rows)
        tbl.insert(0, "TIMES %", 100 * tgt.loc[tbl.index, "share"])
        tbl.insert(0, "TIMES TWh", tgt.loc[tbl.index, "TWh"])
        tbl["unmet TWh"] = unmet_mix(rows["after TWh"], tgt)
        tbl.index.name = f"{year}"
        print(md(tbl, "{:.2f}"))
        unmet = tbl["unmet TWh"].sum()
        if unmet > 1e-3:
            print(
                f"\n> **{year}: {unmet:.3f} TWh_th of the TIMES mix could not be "
                "delivered** — the constraint relaxed at "
                "`energy_mix.penalty` rather than making the LP infeasible. "
                "See §3.3.1 and §8.7.\n"
            )
        print()

    print("## Installed decentral heat capacity, MW_th\n")
    for year in HORIZONS:
        rows = {p: decentral_capacity(load(p, year)) for p in PHASES}
        tbl = pd.DataFrame(rows).fillna(0.0)
        tbl["change %"] = 100 * (tbl["after"] / tbl["before"].where(tbl["before"] > 0) - 1)
        tbl.loc["TOTAL"] = tbl.sum()
        tbl.loc["TOTAL", "change %"] = 100 * (
            tbl.loc["TOTAL", "after"] / tbl.loc["TOTAL", "before"] - 1
        )
        tbl.index.name = f"{year}"
        print(md(tbl, "{:.1f}"))
        print()

    print("## System totals\n")
    rows = []
    for year in HORIZONS:
        nb, na = load("before", year), load("after", year)
        rows.append(
            {
                "horizon": year,
                "objective before (bn)": nb.objective / 1e9,
                "objective after (bn)": na.objective / 1e9,
                "delta (MEUR)": (na.objective - nb.objective) / 1e6,
                "delta %": 100 * (na.objective / nb.objective - 1),
                "BEWAL CO2 before (Mt)": walloon_co2(nb),
                "BEWAL CO2 after (Mt)": walloon_co2(na),
            }
        )
    tbl = pd.DataFrame(rows).set_index("horizon")
    tbl.index.name = "horizon"
    print(md(tbl, "{:.3f}"))
    print()

    print("## Fuel and electricity drawn by decentral heating, TWh\n")
    rows = []
    for year in HORIZONS:
        entry = {"horizon": year}
        for phase in PHASES:
            s = heat_inputs(load(phase, year))
            for label, value in s.items():
                entry[f"{label} {phase}"] = value
        rows.append(entry)
    tbl = pd.DataFrame(rows).set_index("horizon")
    tbl.index.name = "horizon"
    print(md(tbl, "{:.3f}"))


if __name__ == "__main__":
    main()
