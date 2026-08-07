# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Three-way report for the TIMES heating soft-link.

Reads the archives written by ``run_heat_softlink_comparison.sh`` and prints
Markdown tables ready to paste into the decision documents:

===========  ================================================================
``before``   legacy transfer — annual heat demand only, PyPSA re-optimises the
             appliance fleet from scratch
``after``    **option C** — annual energy-mix constraints
             (``docs/heat_soft_linking.md``)
``option_b`` **option B'** — reconstructed hourly profiles, pinned dispatch
             (``docs/heat_softlink_option_b.md``)
===========  ================================================================

Tables:

* decentral heat mix per horizon against the TIMES target, with the mix error
  each mechanism leaves behind;
* the **hourly** mix deviation and the decentral / district-heating storage
  cycling — the flexibility question, measured rather than argued;
* installed decentral heat capacity;
* system objective and Walloon CO₂;
* fuel and electricity drawn by decentral heating — the knock-on effects a mix
  transfer is *not* supposed to touch, and therefore the part worth checking.

Usage::

    python scripts/walloon_scripts/compare_heat_softlink.py [scenario] [phase...]

Any phase whose archive is missing is skipped with a note, so the script is
useful before the third chain has finished.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.walloon_scripts.times_heat_softlink import (  # noqa: E402
    decentral_heat_buses,
    heat_injection_terms,
)

ARGV = sys.argv[1:]
SCENARIO = ARGV[0] if ARGV else "scen_demande_haute"
ARCHIVE = Path("results/_heat_softlink_comparison")
RESOURCES = Path("resources/times-pypsa") / SCENARIO
HORIZONS = [2025, 2030, 2040, 2050]
NODE = "BEWAL"

ALL_PHASES = ["before", "after", "option_b"]
LABEL = {"before": "legacy", "after": "option C", "option_b": "option B'"}
PHASES = ARGV[1:] or ALL_PHASES

_CACHE: dict[tuple[str, int], pypsa.Network] = {}


def load(phase: str, year: int) -> pypsa.Network:
    key = (phase, year)
    if key not in _CACHE:
        _CACHE[key] = pypsa.Network(
            ARCHIVE / phase / "networks" / f"base_s_adm___{year}.nc"
        )
    return _CACHE[key]


def targets(year: int) -> pd.DataFrame:
    return pd.read_csv(RESOURCES / f"heating_targets_{year}.csv")


def group_dispatch(n: pypsa.Network, tgt: pd.DataFrame) -> pd.DataFrame:
    """Heat delivered per constraint group and snapshot, MW_th."""
    buses = decentral_heat_buses(n, NODE)
    out = {}
    for _, row in tgt[tgt["constrained"]].iterrows():
        carriers = [c.strip() for c in str(row["pypsa_carriers"]).split(";") if c.strip()]
        index, coeffs = heat_injection_terms(n, buses, carriers, row["pypsa_component"])
        p = n.links_t.p0 if row["pypsa_component"] == "Link" else n.generators_t.p
        out[row["group"]] = (p[index] * coeffs).sum(axis=1)
    return pd.DataFrame(out)


def heat_mix(n: pypsa.Network, tgt: pd.DataFrame) -> pd.Series:
    """Annual heat delivered to the decentral buses per group, TWh_th."""
    w = n.snapshot_weightings.generators
    return group_dispatch(n, tgt).mul(w, axis=0).sum() / 1e6


def mix_error(realised: pd.Series, tgt: pd.DataFrame) -> pd.Series:
    """Percentage points by which each group's realised share misses TIMES.

    This is the number that makes the two mechanisms directly comparable and
    that no per-mechanism diagnostic can give: option C reports its slack against
    its own *tolerance bound*, option B' against its *profile*, and the two
    bounds are not the same thing. The realised share against the TIMES share is.
    """
    shares = 100 * realised / realised.sum()
    return shares - 100 * tgt.loc[shares.index, "share"]


def hourly_mix_deviation(n: pypsa.Network, tgt: pd.DataFrame) -> float:
    """Energy-weighted mean |hourly share − annual share|, aggregated, in %.

    0 % means the technology mix is already constant through the year, i.e. the
    hourly substitution freedom option B' removes is worth nothing. The larger
    it is, the more option B' gives up — and the more of what PyPSA is doing is
    the single-bus perfect-substitutability artefact discussed in
    ``docs/heat_softlink_option_b.md`` §2.2.
    """
    supply = group_dispatch(n, tgt)
    w = n.snapshot_weightings.generators
    total = supply.sum(axis=1)
    annual = supply.mul(w, axis=0).sum()
    annual_share = annual / annual.sum()
    hourly = supply.div(total.where(total > 0), axis=0).fillna(0.0)
    deviation = hourly.sub(annual_share, axis=1).abs()
    weighted = (deviation.mul(total * w, axis=0)).sum() / float((total * w).sum())
    return float(weighted.sum() / 2 * 100)


def storage_cycling(n: pypsa.Network, buses: set[str], pattern: str) -> float:
    """TWh_th cycled through the thermal stores on ``buses`` (charge = discharge)."""
    w = n.snapshot_weightings.generators
    links = n.links[
        n.links.carrier.str.contains(pattern, na=False)
        & (n.links.bus0.isin(buses) | n.links.bus1.isin(buses))
        & n.links.index.str.startswith(NODE)
    ]
    total = 0.0
    for name, row in links.iterrows():
        column = "p0" if row.bus0 in buses else "p1"
        if name in getattr(n.links_t, column).columns:
            total += abs(float((getattr(n.links_t, column)[name] * w).sum()))
    return total / 2 / 1e6


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
            body[c] = body[c].map(
                lambda v: "—" if pd.isna(v) else floatfmt.format(v)
            )
    head = "| " + " | ".join([body.index.name or ""] + list(body.columns)) + " |"
    rule = "|" + "|".join(["---"] * (len(body.columns) + 1)) + "|"
    rows = ["| " + " | ".join([str(i)] + list(r)) + " |" for i, r in body.iterrows()]
    return "\n".join([head, rule, *rows])


def available_phases() -> list[str]:
    present, missing = [], []
    for phase in PHASES:
        (present if (ARCHIVE / phase / "networks").is_dir() else missing).append(phase)
    if missing:
        print(
            f"> Archives missing for {missing} — those columns are omitted. Run "
            "`bash scripts/walloon_scripts/run_heat_softlink_comparison.sh "
            f"{SCENARIO} {' '.join(missing)}` to produce them.\n"
        )
    if not present:
        raise SystemExit("No archive found at all.")
    return present


def main() -> None:
    print(f"# Heating soft-link comparison — {SCENARIO}\n")
    phases = available_phases()

    print("## Decentral heat mix, share of supply\n")
    for year in HORIZONS:
        tgt = targets(year).set_index("group")
        rows = {}
        for phase in phases:
            s = heat_mix(load(phase, year), targets(year))
            rows[f"{LABEL[phase]} TWh"] = s
            rows[f"{LABEL[phase]} %"] = 100 * s / s.sum()
            rows[f"{LABEL[phase]} err pp"] = mix_error(s, tgt)
        tbl = pd.DataFrame(rows)
        tbl.insert(0, "TIMES %", 100 * tgt.loc[tbl.index, "share"])
        tbl.insert(0, "TIMES TWh", tgt.loc[tbl.index, "TWh"])
        tbl.index.name = f"{year}"
        print(md(tbl, "{:.2f}"))
        for phase in phases:
            err = tbl[f"{LABEL[phase]} err pp"].abs()
            print(
                f"\n> {LABEL[phase]}: mean |share error| "
                f"{err.mean():.2f} pp, worst {err.max():.2f} pp "
                f"({err.idxmax()})."
            )
        print()

    print("## Hourly flexibility actually used\n")
    rows = []
    for year in HORIZONS:
        entry = {"horizon": year}
        for phase in phases:
            n = load(phase, year)
            tgt = targets(year)
            decentral = set(decentral_heat_buses(n, NODE))
            central = {f"{NODE} urban central heat"}
            entry[f"{LABEL[phase]} mix dev %"] = hourly_mix_deviation(n, tgt)
            entry[f"{LABEL[phase]} dec. store TWh"] = storage_cycling(
                n, decentral, "water tanks"
            )
            entry[f"{LABEL[phase]} DH store TWh"] = storage_cycling(
                n, central, "water tanks|water pits"
            )
        rows.append(entry)
    tbl = pd.DataFrame(rows).set_index("horizon")
    tbl.index.name = "horizon"
    print(md(tbl, "{:.4f}"))
    print(
        "\n> `mix dev` is the energy-weighted mean |hourly share − annual share|, "
        "aggregated: 0 % means the mix is already constant, so option B' removes "
        "nothing. `dec. store` is the decentral water-tank cycling option B' "
        "leaves to the absorber; `DH store` is the district-heating pit store, "
        "which neither option touches.\n"
    )

    print("## Installed decentral heat capacity, MW_th\n")
    for year in HORIZONS:
        tbl = pd.DataFrame(
            {LABEL[p]: decentral_capacity(load(p, year)) for p in phases}
        ).fillna(0.0)
        tbl.loc["TOTAL"] = tbl.sum()
        tbl.index.name = f"{year}"
        print(md(tbl, "{:.1f}"))
        print()

    print("## System totals\n")
    rows = []
    for year in HORIZONS:
        entry = {"horizon": year}
        base = load(phases[0], year).objective
        for phase in phases:
            n = load(phase, year)
            entry[f"{LABEL[phase]} obj (bn)"] = n.objective / 1e9
            entry[f"{LABEL[phase]} d (MEUR)"] = (n.objective - base) / 1e6
            entry[f"{LABEL[phase]} CO2 (Mt)"] = walloon_co2(n)
        rows.append(entry)
    tbl = pd.DataFrame(rows).set_index("horizon")
    tbl.index.name = "horizon"
    print(md(tbl, "{:.3f}"))
    print(f"\n> `d (MEUR)` is against **{LABEL[phases[0]]}**.\n")

    print("## Fuel and electricity drawn by decentral heating, TWh\n")
    rows = []
    for year in HORIZONS:
        entry = {"horizon": year}
        for phase in phases:
            for label, value in heat_inputs(load(phase, year)).items():
                entry[f"{label} {LABEL[phase]}"] = value
        rows.append(entry)
    tbl = pd.DataFrame(rows).set_index("horizon")
    tbl.index.name = "horizon"
    print(md(tbl, "{:.3f}"))


if __name__ == "__main__":
    main()
