"""Which levers actually move Walloon CO2 capture — the analysis behind §10.3 of
`docs/co2-sequestration.md`.

Three experiments, all read off the solved networks; no re-solve required.

  A. Sequestration-levy pass-through.  The BEWAL cap binds exactly, so a levy on
     `co2_sequestration_cost` cannot reduce capture — it raises the shadow carbon
     price instead.  The pass-through ratio is tonnes-captured / tonnes-avoided on
     the marginal route.  Prints it per route, plus the cost of a levy at zero
     quantity response.

  B. Free-dispatch capex recovery sweeps in the levy and in the gas price.  The
     BEWAL national CO2 shadow charge does NOT price through the `co2 atmosphere`
     bus, so it is added explicitly; the validation block confirms this returns
     exactly 100.0 % on every built extendable vintage, which is the LP-optimum
     signature.  Omitting it makes unabated gas look ~29 % more profitable.

  C. Cross-scenario decomposition of capture into power / industry / process over
     every solved network on disk — the only general-equilibrium evidence
     available without new solves.

Usage:
    python scripts/walloon_scripts/ccs_lever_sensitivity.py [scenario]
"""

import glob
import re
import sys
import warnings

import numpy as np
import pandas as pd
import pypsa

warnings.filterwarnings("ignore")
pd.set_option("display.width", 250)

NODE = "BEWAL"
SCEN = sys.argv[1] if len(sys.argv) > 1 else "scen_central"
YEARS = (2040, 2050)

POWER_CC = ["CCGT CC", "urban central gas CHP CC", "urban decentral gas CHP CC",
            "waste CHP CC"]
INDUSTRY_CC = ["gas for industry CC", "solid biomass for industry CC",
               "process emissions CC", "SMR CC"]
SWEEP = POWER_CC[:2] + ["CCGT", "urban central gas CHP"] + INDUSTRY_CC[:3]


def load(scen, year):
    return pypsa.Network(f"results/walloon/{scen}/networks/base_s_adm___{year}.nc")


def national_mu(n, node=NODE):
    """BEWAL national cap dual — stacks on top of the global one (§7.1)."""
    return -sum(n.global_constraints.loc[i, "mu"] for i in n.global_constraints.index
                if node in i and "co2" in i.lower())


def ports(link):
    """(efficiency, bus) for every output port of a Link."""
    out = [(link.efficiency, link.bus1), (link.efficiency2, link.bus2),
           (link.efficiency3, link.bus3)]
    if getattr(link, "bus4", ""):
        out.append((link.efficiency4, link.bus4))
    return [(e, b) for e, b in out if isinstance(b, str) and b]


def co2_ports(link):
    """(t to atmosphere, t to storage) per unit of bus0 input."""
    atm = sto = 0.0
    for eff, bus in ports(link):
        if bus == "co2 atmosphere":
            atm += eff
        elif "co2 stored" in bus:
            sto += eff
    return atm, sto


def extendable(n, carrier, year, node=NODE):
    idx = [i for i in n.links.index
           if n.links.at[i, "carrier"] == carrier and i.startswith(node)
           and i.endswith(f"-{year}") and n.links.at[i, "p_nom_extendable"]]
    return n.links.loc[idx[0]] if idx else None


def recovery(n, carrier, year, dlevy=0.0, dgas=0.0, node=NODE):
    """Free-dispatch capex recovery of the extendable vintage, national charge in."""
    link = extendable(n, carrier, year, node)
    if link is None or link.bus0 not in n.buses_t.marginal_price:
        return np.nan
    dnat = national_mu(n, node)
    w = n.snapshot_weightings.objective
    P = n.buses_t.marginal_price
    margin = -(P[link.bus0] + (dgas if "gas" in link.bus0 else 0.0)) - link.marginal_cost
    for eff, bus in ports(link):
        if bus not in P:
            continue
        lam = P[bus].copy()
        if "co2 stored" in bus:
            lam = lam - dlevy              # disposal costs more
        if bus == "co2 atmosphere":
            lam = lam - dnat               # national charge, invisible in the bus price
        if "gas" in bus:
            lam = lam + dgas
        margin = margin + eff * lam
    return (np.maximum(margin, 0.0) * w).sum() / link.capital_cost


def capture_by_carrier(n, node=NODE):
    """kt/a onto `<node> co2 stored`, per carrier."""
    w = n.snapshot_weightings.generators
    out = {}
    for i in n.links.index:
        if not i.startswith(node):
            continue
        link = n.links.loc[i]
        for eff, bus in ports(link):
            if "co2 stored" in bus and eff > 0:
                out[link.carrier] = out.get(link.carrier, 0.0) + \
                    (n.links_t.p0[i] * w).sum() * eff / 1e3
    return pd.Series(out, dtype=float)


# ---------------------------------------------------------------- A + B
for year in YEARS:
    n = load(SCEN, year)
    w = n.snapshot_weightings.generators
    P = n.buses_t.marginal_price
    tw = lambda b: (P[b] * w).sum() / w.sum()  # noqa: E731
    p_co2 = -n.global_constraints.at["CO2Limit", "mu"] + national_mu(n)
    p_seq = -tw(f"{NODE} co2 stored")
    capt = capture_by_carrier(n)

    print(f"\n{'#' * 104}\n{SCEN} {year}   stacked P_CO2 {p_co2:.2f}   "
          f"P_seq {p_seq:.2f}   lambda_gas {tw(f'{NODE} gas'):.2f}\n{'#' * 104}")

    print("\nVALIDATION — recovery of every built extendable vintage (must be ~100.0%):")
    for c in SWEEP:
        r = recovery(n, c, year)
        if r == r:
            print(f"   {c:<32}{r * 100:7.1f}%")

    print("\nA. Sequestration-levy pass-through into the shadow carbon price")
    for cc, plain in [("CCGT CC", "CCGT"),
                      ("urban central gas CHP CC", "urban central gas CHP"),
                      ("gas for industry CC", "gas for industry"),
                      ("solid biomass for industry CC", None),
                      ("process emissions CC", None)]:
        a = extendable(n, cc, year)
        if a is None:
            continue
        atm_a, sto_a = co2_ports(a)
        if plain:
            # per unit of bus1 output, so the two routes deliver the same service
            b = extendable(n, plain, year)
            if b is None:
                continue
            atm_b, _ = co2_ports(b)
            avoided = atm_b / b.efficiency - atm_a / a.efficiency
            captured = sto_a / a.efficiency
        else:
            # capture-or-emit: bus0 is already in tonnes, normalise by it, not by
            # `efficiency` (which is the atmosphere slip on bus1 for process capture)
            avoided = captured = sto_a
        if avoided <= 0:
            continue
        print(f"   {cc:<32}captured {captured:6.4f} / avoided {avoided:6.4f}"
              f"  ->  d(P_CO2)/d(levy) = {captured / avoided:5.3f}")
    total = capt.sum()
    print(f"   BEWAL capture {total / 1e3:,.2f} Mt/a  ->  a levy costs, at zero "
          "quantity response:")
    for d in (20, 52, 100, 150):
        print(f"      +{d:3d} EUR/t  =  {total * d / 1e3:,.0f} MEUR/a, "
              "no change in Walloon emissions (the cap binds)")

    print("\nB. Free-dispatch capex recovery, % — levy sweep then gas-price sweep")
    for kw, grid in [("dlevy", [0, 5, 10, 20, 50, 100, 200, 300]),
                     ("dgas", [0, 5, 10, 20, 50, 100])]:
        tab = {d: {c: recovery(n, c, year, **{kw: float(d)}) * 100 for c in SWEEP}
               for d in grid}
        frame = pd.DataFrame(tab).dropna(how="all")
        frame.columns.name = f"+{kw}"
        print(frame.to_string(float_format=lambda v: f"{v:7.1f}"))


# ---------------------------------------------------------------- C
print(f"\n{'#' * 104}\nC. Capture by origin across every solved network on disk\n{'#' * 104}")
rows = []
for path in sorted(glob.glob("results/walloon/*/networks/base_s_adm___*.nc")):
    year = int(re.search(r"___(\d{4})", path).group(1))
    if year not in YEARS:
        continue
    n = pypsa.Network(path)
    capt = capture_by_carrier(n)
    nuc = [i for i in n.links.index
           if n.links.at[i, "carrier"] == "nuclear" and i.startswith(NODE)]
    rows.append(dict(
        scen=path.split("/")[2], year=year,
        nuclear_MWe=(n.links.loc[nuc, "p_nom_opt"] * n.links.loc[nuc, "efficiency"]).sum(),
        total=capt.sum(),
        power=capt.reindex(POWER_CC).fillna(0.0).sum(),
        industry=capt.reindex(INDUSTRY_CC).fillna(0.0).sum(),
        process=capt.get("process emissions CC", 0.0)))
df = pd.DataFrame(rows)
df["power_pct"] = df.power / df.total * 100
for year in YEARS:
    sub = df[df.year == year].sort_values("total")
    print(f"\n{year} — kt/a\n" + "-" * 104)
    print(sub[["scen", "nuclear_MWe", "total", "power", "industry", "process",
               "power_pct"]].to_string(index=False, float_format=lambda v: f"{v:,.0f}"))
    print(f"   process emissions CC spread: {sub.process.min():,.0f} – "
          f"{sub.process.max():,.0f} kt "
          f"(+-{(sub.process.max() - sub.process.min()) / 2 / sub.process.mean() * 100:.1f}%)"
          f"   |   power capture: {sub.power_pct.min():.1f}–{sub.power_pct.max():.1f}% of total")
