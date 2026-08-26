# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Why is this solve at its limits? One solved network in, one markdown table out.

``review_run.py`` answers "is the result plausible". This answers the follow-up
question "which constraint is holding it there", by reading the duals the solver
already wrote into the network:

* every global constraint with a non-zero dual, largest first;
* the per-country CO2 constraint decomposed by carrier, so an implausible CO2
  price can be traced to the sector that has nowhere to go;
* cross-border and internal transmission loading, in *usable* terms
  (``s_nom_opt * s_max_pu`` for AC lines), with the congestion rent;
* the levelised cost gap between competing generation technologies, and the CO2
  price at which the ranking flips;
* the CO2 sequestration headroom actually reachable from each node.

Usage
-----
    python scripts/walloon_scripts/diagnose_binding_constraints.py NETWORK.nc \
        [--country BEWAL] [--output report.md]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

MWH_PER_TWH = 1e6
T_PER_MT = 1e6
EUR_PER_MEUR = 1e6

# duals below this are numerical noise, not a binding constraint
DUAL_EPS = 1e-4
# a corridor counts as congested when the flow is within this fraction of the cap.
# 1e-3 is too tight: the LP leaves AC flows at ~99.6 % of the bound, so a tighter
# tolerance reports zero congested hours on lines that are saturated all year.
CONGESTION_TOL = 1e-2


def _fmt(x: float, digits: int = 1) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "-"
    return f"{x:,.{digits}f}"


def _table(df: pd.DataFrame, floatfmt: str = ".2f") -> str:
    if df.empty:
        return "_(nothing to report)_\n"
    return df.to_markdown(floatfmt=floatfmt) + "\n"


def _section(title: str) -> str:
    return f"\n## {title}\n\n"


# --------------------------------------------------------------------------- #
# 1. global constraints with a non-zero dual
# --------------------------------------------------------------------------- #
def global_constraint_duals(n: pypsa.Network) -> pd.DataFrame:
    """Every ``GlobalConstraint`` the solver priced, largest |mu| first."""
    gc = n.global_constraints
    if gc.empty or "mu" not in gc:
        return pd.DataFrame()
    out = gc.loc[gc.mu.abs() > DUAL_EPS, ["type", "carrier_attribute", "sense", "constant", "mu"]]
    out = out.reindex(out.mu.abs().sort_values(ascending=False).index)
    out = out.rename(
        columns={
            "constant": "rhs",
            "mu": "dual [EUR/unit]",
            "carrier_attribute": "attribute",
        }
    )
    return out


def custom_constraint_duals(n: pypsa.Network) -> pd.DataFrame:
    """Duals of the extra constraints added in ``solve_network.py``.

    These live in the linopy model (``n.model``), which only survives the solve
    when the network was written with ``export_to_netcdf(..., model=True)``.
    Absent that, we report what the statistics can still show.
    """
    if not hasattr(n, "model") or n.model is None:
        return pd.DataFrame()
    rows = []
    for name, con in n.model.constraints.items():
        dual = getattr(con, "dual", None)
        if dual is None:
            continue
        arr = np.asarray(dual)
        if arr.size == 0 or not np.isfinite(arr).any():
            continue
        peak = np.nanmax(np.abs(arr))
        if peak <= DUAL_EPS:
            continue
        rows.append(
            {
                "constraint": name,
                "size": int(arr.size),
                "max |dual|": float(peak),
                "mean |dual|": float(np.nanmean(np.abs(arr))),
            }
        )
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values("max |dual|", ascending=False)
        .set_index("constraint")
    )


# --------------------------------------------------------------------------- #
# 2. per-country CO2 constraint, decomposed
# --------------------------------------------------------------------------- #
CO2_PATTERNS = [
    "process emissions",
    "HVC to air",
    "electrobiofuels",
    "unsustainable bioliquids",
    "biomass-to-methanol",
    "biomass to liquid",
]
CO2_EXCLUDE = ["EU oil refining", "EU methanol import", "EU oil import"]


def _atmosphere_intensity(n: pypsa.Network) -> pd.Series:
    """Signed tCO2 per MWh of link input that reaches ``co2 atmosphere``."""
    contrib = pd.Series(0.0, index=n.links.index)
    for i in range(2, 6):
        bus_col, eff_col = f"bus{i}", f"efficiency{i}"
        if bus_col not in n.links:
            continue
        hit = n.links[bus_col] == "co2 atmosphere"
        if hit.any():
            contrib[hit] += n.links.loc[hit, eff_col].fillna(0.0)
    return contrib


def _co2_country(n: pypsa.Network) -> pd.Series:
    """Country each link's emissions are booked to.

    Reproduces the attribution of ``add_co2limit_country`` in
    ``scripts/solve_network.py``: ``bus1`` by default, ``bus3`` for DAC, and
    ``bus0`` for the pattern carriers whose location sits on the input side.
    """
    location = n.buses.location
    country = n.links.bus1.map(location)

    dac = n.links[n.links.carrier == "DAC"]
    if not dac.empty and "bus3" in n.links:
        country[dac.index] = dac.bus3.map(location)

    for pattern in CO2_PATTERNS:
        hit = n.links[n.links.carrier.astype(str).str.contains(pattern, na=False)]
        if hit.empty:
            continue
        country[hit.index] = hit.bus0.map(location)

    blank = country.isna() | (country == "")
    country[blank] = country[blank].index
    return country[country != "EU"]


def co2_lhs_by_link(n: pypsa.Network) -> pd.DataFrame:
    """Per-link contribution to the per-country CO2 constraint, in t.

    Sums every port whose bus carries the ``co2`` carrier — i.e. ``co2
    atmosphere`` — weighted by that port's efficiency, exactly as the
    constraint does.
    """
    if n.links.empty:
        return pd.DataFrame()

    country = _co2_country(n)
    weights = n.snapshot_weightings.generators
    bus_carrier = n.buses.carrier
    total = pd.Series(0.0, index=n.links.index)

    ports = [c[3:] for c in n.links.columns if c.startswith("bus")]
    for port in ports:
        if port == "0":
            efficiency = pd.Series(1.0, index=n.links.index)
        elif port == "1":
            efficiency = n.links.efficiency
        else:
            efficiency = n.links[f"efficiency{port}"].fillna(0.0)

        mask = n.links[f"bus{port}"].map(bus_carrier).eq("co2")
        idx = n.links[mask].index.difference(pd.Index(CO2_EXCLUDE))
        idx = idx.intersection(country.index).intersection(n.links_t.p0.columns)
        if idx.empty:
            continue
        # every port of a link carries the same p0 up to its own efficiency
        flow = n.links_t.p0[idx].mul(weights, axis=0).sum()
        total[idx] += flow * efficiency[idx]

    active = total[total.abs() > 1.0]
    return pd.DataFrame(
        {
            "country": country.reindex(active.index),
            "carrier": n.links.carrier.reindex(active.index),
            "tCO2": active,
        }
    )


def co2_decomposition(n: pypsa.Network, country: str) -> tuple[pd.DataFrame, dict]:
    """Split one country's CO2 constraint LHS by carrier, in Mt."""
    lhs = co2_lhs_by_link(n)
    if lhs.empty:
        return pd.DataFrame(), {}

    sel = lhs[lhs.country == country]
    if sel.empty:
        return pd.DataFrame(), {}

    out = (sel.groupby("carrier").tCO2.sum() / T_PER_MT).sort_values()
    out = out[out.abs() > 1e-4]

    df = out.to_frame("MtCO2")
    df["cumulative [Mt]"] = out.iloc[::-1].cumsum().iloc[::-1]

    summary = {
        "net": float(out.sum()),
        "positive": float(out[out > 0].sum()),
        "negative": float(out[out < 0].sum()),
    }
    return df, summary


def co2_price(n: pypsa.Network, country: str | None = None) -> dict:
    """The CO2 duals in EUR/t, global and per country."""
    out = {}
    gc = n.global_constraints
    if not gc.empty and "mu" in gc:
        for name, mu in gc.mu.items():
            if "co2" in str(name).lower() or "CO2" in str(name):
                out[name] = float(mu)
    # per-country constraints are stored as extra shadow prices on the network
    for attr in ("co2_price_per_country", "co2_shadow_price"):
        if hasattr(n, attr):
            out.update(getattr(n, attr))
    return out


# --------------------------------------------------------------------------- #
# 3. transmission: usable capacity, congestion hours, rent
# --------------------------------------------------------------------------- #
def transmission_report(n: pypsa.Network) -> pd.DataFrame:
    """Loading and congestion rent per AC line and DC link."""
    rows = []
    weights = n.snapshot_weightings.objective
    prices = n.buses_t.marginal_price if not n.buses_t.marginal_price.empty else None

    def _rent(bus0: str, bus1: str, flow: pd.Series) -> float:
        if prices is None or bus0 not in prices or bus1 not in prices:
            return np.nan
        delta = (prices[bus1] - prices[bus0]).abs()
        return float((delta * flow.abs() * weights).sum() / EUR_PER_MEUR)

    if not n.lines.empty:
        # s_max_pu can be a time series, so the cap is one too
        s_max_pu = n.get_switchable_as_dense("Line", "s_max_pu")
        flows = n.lines_t.p0
        for line in n.lines.index:
            cap_t = s_max_pu[line] * n.lines.at[line, "s_nom_opt"]
            flow = flows[line] if line in flows else pd.Series(0.0, index=n.snapshots)
            loading = (flow.abs() / cap_t.replace(0, np.nan)).fillna(0.0)
            rows.append(
                {
                    "component": "Line",
                    "name": line,
                    "bus0": n.lines.at[line, "bus0"],
                    "bus1": n.lines.at[line, "bus1"],
                    "s_nom [MW]": float(n.lines.at[line, "s_nom"]),
                    "opt [MW]": float(n.lines.at[line, "s_nom_opt"]),
                    "usable [MW]": float(cap_t.mean()),
                    "extendable": bool(n.lines.at[line, "s_nom_extendable"]),
                    "p95 load [%]": 100 * float(loading.quantile(0.95)),
                    "congested [h]": float(
                        weights[loading >= 1 - CONGESTION_TOL].sum()
                    ),
                    "rent [MEUR]": _rent(
                        n.lines.at[line, "bus0"], n.lines.at[line, "bus1"], flow
                    ),
                }
            )

    dc = n.links[n.links.carrier == "DC"] if not n.links.empty else n.links.iloc[0:0]
    for link in dc.index:
        cap = float(dc.at[link, "p_nom_opt"])
        flow = n.links_t.p0[link] if link in n.links_t.p0 else pd.Series(0.0, index=n.snapshots)
        loading = flow.abs() / cap if cap > 0 else pd.Series(0.0, index=n.snapshots)
        rows.append(
            {
                "component": "Link",
                "name": link,
                "bus0": dc.at[link, "bus0"],
                "bus1": dc.at[link, "bus1"],
                "s_nom [MW]": float(dc.at[link, "p_nom"]),
                "opt [MW]": cap,
                "usable [MW]": cap,
                "extendable": bool(dc.at[link, "p_nom_extendable"]),
                "p95 load [%]": 100 * float(loading.quantile(0.95)),
                "congested [h]": float(weights[loading >= 1 - CONGESTION_TOL].sum()),
                "rent [MEUR]": _rent(dc.at[link, "bus0"], dc.at[link, "bus1"], flow),
            }
        )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("name")
    df["congested [%]"] = 100 * df["congested [h]"] / float(weights.sum())
    return df.sort_values("rent [MEUR]", ascending=False)


# --------------------------------------------------------------------------- #
# 4. technology competition: annualised cost and the CO2 break-even
# --------------------------------------------------------------------------- #
def technology_costs(
    n: pypsa.Network, carriers: tuple[str, ...] = ("CCGT", "CCGT CC", "OCGT")
) -> pd.DataFrame:
    """Per-MW_el capital cost, emission factor and dispatch of gas conversion."""
    rows = []
    for carrier in carriers:
        sel = n.links[n.links.carrier == carrier]
        if sel.empty:
            continue
        eta = sel.efficiency.replace(0, np.nan)
        weights = n.snapshot_weightings.generators
        gen = (
            n.links_t.p1[sel.index].mul(weights, axis=0).sum().sum() * -1 / MWH_PER_TWH
            if not n.links_t.p1.empty
            else np.nan
        )
        rows.append(
            {
                "carrier": carrier,
                "eta": float(eta.mean()),
                "capex [EUR/MW_el/a]": float((sel.capital_cost / eta).mean()),
                "vom [EUR/MWh_el]": float((sel.marginal_cost / eta).mean()),
                "tCO2/MWh_el": float((_atmosphere_intensity(n)[sel.index] / eta).mean()),
                "p_nom_opt [MW_el]": float((sel.p_nom_opt * sel.efficiency).sum()),
                "generation [TWh_el]": float(gen),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("carrier")


def co2_breakeven(costs: pd.DataFrame, dirty: str, clean: str) -> float | None:
    """CO2 price at which `clean` becomes cheaper than `dirty`, per MWh_el.

    Compares only the capital and emission terms, at full utilisation, so it is
    an order of magnitude rather than a dispatch result.
    """
    if dirty not in costs.index or clean not in costs.index:
        return None
    d, c = costs.loc[dirty], costs.loc[clean]
    dco2 = d["tCO2/MWh_el"] - c["tCO2/MWh_el"]
    if abs(dco2) < 1e-9:
        return None
    # annualised capex spread over 4000 full-load hours
    hours = 4000.0
    dcost = (c["capex [EUR/MW_el/a]"] - d["capex [EUR/MW_el/a]"]) / hours + (
        c["vom [EUR/MWh_el]"] - d["vom [EUR/MWh_el]"]
    )
    return float(dcost / dco2)


# --------------------------------------------------------------------------- #
# 5. CO2 sequestration headroom
# --------------------------------------------------------------------------- #
def sequestration_headroom(n: pypsa.Network) -> pd.DataFrame:
    """Every ``co2 sequestered`` store: cap, use, and whether it is full."""
    sel = n.stores[n.stores.carrier.astype(str).str.contains("co2 sequestered")]
    if sel.empty:
        return pd.DataFrame()
    used = (
        n.stores_t.e[sel.index].max() if not n.stores_t.e.empty else pd.Series(dtype=float)
    )
    df = pd.DataFrame(
        {
            "bus": sel.bus,
            "e_nom_max [Mt]": sel.e_nom_max / T_PER_MT,
            "e_nom_opt [Mt]": sel.e_nom_opt / T_PER_MT,
            "peak fill [Mt]": used.reindex(sel.index) / T_PER_MT,
        }
    )
    df["headroom [Mt]"] = df["e_nom_max [Mt]"] - df["peak fill [Mt]"]
    return df.sort_values("e_nom_max [Mt]", ascending=False)


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def build_report(n: pypsa.Network, country: str, path: Path) -> str:
    lines = [f"# Binding-constraint diagnosis: `{path.name}`\n"]
    lines.append(
        f"Snapshots: {len(n.snapshots)}, "
        f"weighted hours: {_fmt(float(n.snapshot_weightings.objective.sum()))}, "
        f"objective: {_fmt(n.objective / EUR_PER_MEUR)} MEUR\n"
    )

    lines.append(_section("1. Global constraints with a non-zero dual"))
    lines.append(_table(global_constraint_duals(n)))

    custom = custom_constraint_duals(n)
    if not custom.empty:
        lines.append(_section("1b. Custom constraint duals (from the linopy model)"))
        lines.append(_table(custom))
    else:
        lines.append(
            "\n_The linopy model was not stored with the network, so the duals of "
            "the custom constraints (`agg_p_nom_*`, `co2_limit_per_country*`) are "
            "not available here; only the CO2 global constraints above are._\n"
        )

    prices = co2_price(n, country)
    if prices:
        lines.append(_section("2. CO2 shadow prices [EUR/t]"))
        lines.append(_table(pd.Series(prices, name="EUR/t").to_frame()))

    df, summary = co2_decomposition(n, country)
    lines.append(_section(f"3. {country} CO2 balance by carrier [Mt]"))
    if summary:
        lines.append(
            f"Net **{_fmt(summary['net'], 3)} Mt** "
            f"= {_fmt(summary['positive'], 3)} emitted "
            f"{_fmt(summary['negative'], 3)} captured.\n\n"
        )
    lines.append(_table(df, floatfmt=".3f"))

    lines.append(_section("4. Transmission: usable capacity, congestion, rent"))
    tr = transmission_report(n)
    lines.append(_table(tr))
    if not tr.empty:
        frozen = tr[~tr.extendable]
        lines.append(
            f"\n{len(frozen)} of {len(tr)} corridors are non-extendable; "
            f"total congestion rent {_fmt(tr['rent [MEUR]'].sum())} MEUR.\n"
        )

    lines.append(_section("5. Gas conversion technologies"))
    costs = technology_costs(n)
    lines.append(_table(costs))
    be = co2_breakeven(costs, "CCGT", "CCGT CC")
    if be is not None:
        lines.append(
            f"\nCCGT CC undercuts unabated CCGT above roughly "
            f"**{_fmt(be)} EUR/tCO2** (capex at 4 000 full-load hours).\n"
        )

    lines.append(_section("6. CO2 sequestration headroom"))
    lines.append(_table(sequestration_headroom(n), floatfmt=".3f"))

    return "".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network", type=Path)
    parser.add_argument("--country", default="BEWAL")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    n = pypsa.Network(str(args.network))
    report = build_report(n, args.country, args.network)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
        print(f"written {args.output}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
