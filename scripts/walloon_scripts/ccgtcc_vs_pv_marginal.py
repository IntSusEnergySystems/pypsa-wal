"""Why CCGT-CC and not more PV+battery at BEWAL: marginal economics from the duals."""
import warnings

import numpy as np
import pandas as pd
import pypsa

warnings.filterwarnings("ignore")
NODE = "BEWAL"


def gen_recovery(n, name, lam):
    """Free-dispatch capex recovery of one extendable generator."""
    g = n.generators.loc[name]
    w = n.snapshot_weightings.generators
    pu = n.generators_t.p_max_pu[name] if name in n.generators_t.p_max_pu else pd.Series(1.0, lam.index)
    margin = pu * (lam - g.marginal_cost)
    gross = (np.maximum(margin, 0.0) * w).sum()
    return gross, g.capital_cost, gross / g.capital_cost


def link_recovery(n, name, prices):
    """Free-dispatch capex recovery of one extendable link, per MW of bus0."""
    l = n.links.loc[name]
    w = n.snapshot_weightings.generators
    m = -prices[l.bus0] - l.marginal_cost
    for port, eff in [("bus1", l.efficiency), ("bus2", l.efficiency2), ("bus3", l.efficiency3)]:
        b = getattr(l, port)
        if isinstance(b, str) and b and b in prices:
            m = m + eff * prices[b]
    gross = (np.maximum(m, 0.0) * w).sum()
    return gross, l.capital_cost, gross / l.capital_cost


def run(year):
    n = pypsa.Network(f"results/walloon/scen_central/networks/base_s_adm___{year}.nc")
    w = n.snapshot_weightings.generators
    prices = n.buses_t.marginal_price
    lam = prices[NODE]
    suffix = f"-{year}"
    print(f"\n{'='*86}\n{NODE} {year}   mean lambda_el {(lam*w).sum()/w.sum():.2f} EUR/MWh"
          f"   CO2 price {-n.global_constraints.at['CO2Limit','mu']:.1f} EUR/t\n{'='*86}")

    # ---- solar / wind, per MW_e
    print("Generators (per MW_e, free dispatch):")
    print(f"  {'carrier':<22}{'p_nom_opt':>10}{'p_nom_max':>11}{'FLH':>7}"
          f"{'gross EUR/MW/a':>16}{'capex':>10}{'recovery':>10}")
    sol = {}
    for c in ["solar rooftop", "solar-hsat", "solar", "onwind"]:
        idx = [i for i in n.generators.index
               if n.generators.at[i, "carrier"] == c and i.startswith(NODE)
               and i.endswith(suffix) and n.generators.at[i, "p_nom_extendable"]]
        if not idx:
            continue
        name = idx[0]
        gross, cc, rec = gen_recovery(n, name, lam)
        pu = n.generators_t.p_max_pu[name]
        flh = (pu * w).sum()
        tot = n.generators[(n.generators.carrier == c)
                           & n.generators.index.str.startswith(NODE)]
        sol[c] = dict(gross=gross, cc=cc, rec=rec, name=name)
        print(f"  {c:<22}{tot.p_nom_opt.sum():10.0f}{n.generators.at[name,'p_nom_max']:11.0f}"
              f"{flh:7.0f}{gross:16,.0f}{cc:10,.0f}{rec*100:9.1f}%")

    # ---- the rooftop-share pin bundle
    shares = {2040: 0.690491, 2050: 0.705985}
    s = shares[year]
    k = s / (1 - s)
    r, h = sol.get("solar rooftop"), sol.get("solar-hsat")
    if r and h:
        net_r = r["gross"] - r["cc"]
        net_h = h["gross"] - h["cc"]
        bundle = net_h + k * net_r
        print(f"\n  TIMES rooftop-share pin: rooftop >= {s:.6f} x solar-all"
              f"  =>  1 MW hsat drags {k:.3f} MW rooftop")
        print(f"    hsat    net margin {net_h:+12,.0f} EUR/MW/a")
        print(f"    rooftop net margin {net_r:+12,.0f} EUR/MW/a  x {k:.3f} = {k*net_r:+12,.0f}")
        print(f"    BUNDLE             {bundle:+12,.0f} EUR/MW_hsat/a"
              f"   -> {'PROFITABLE' if bundle > 0 else 'BLOCKED by the pin'}")

    # ---- CCGT CC vs CCGT, per MW_gas and per MW_e
    print("\nGas links (per MW_gas, free dispatch):")
    print(f"  {'carrier':<22}{'MW_e opt':>10}{'eta':>7}{'FLH_e':>7}"
          f"{'gross EUR/MW/a':>16}{'capex':>10}{'recovery':>10}")
    for c in ["CCGT CC", "CCGT"]:
        idx = [i for i in n.links.index
               if n.links.at[i, "carrier"] == c and i.startswith(NODE)
               and i.endswith(suffix) and n.links.at[i, "p_nom_extendable"]]
        if not idx:
            continue
        name = idx[0]
        l = n.links.loc[name]
        gross, cc, rec = link_recovery(n, name, prices)
        tot = n.links[(n.links.carrier == c) & n.links.index.str.startswith(NODE)]
        pe = -(n.links_t.p1[tot.index] * w.values[:, None]).sum().sum()
        mwe = (tot.p_nom_opt * tot.efficiency).sum()
        print(f"  {c:<22}{mwe:10.0f}{l.efficiency:7.3f}{pe/max(mwe,1e-9):7.0f}"
              f"{gross:16,.0f}{cc:10,.0f}{rec*100:9.1f}%")
        # carbon cost decomposition per MWh_e
        atm = l.efficiency2 * (prices["co2 atmosphere"] * w).sum() / w.sum()
        sto_bus = l.bus3 if l.bus3 else None
        sto = (l.efficiency3 * (prices[sto_bus] * w).sum() / w.sum()) if sto_bus else 0.0
        print(f"       carbon per MWh_e:  atmosphere {atm/l.efficiency:+8.2f}"
              f"   stored {sto/l.efficiency:+8.2f}   total {(atm+sto)/l.efficiency:+8.2f} EUR/MWh_e")
    return n, lam, prices, sol


if __name__ == "__main__":
    for y in (2040, 2050):
        run(y)
