"""Reduced-cost response of electrolysis and Fischer-Tropsch to a CO2 sequestration levy.

Per MW of p_nom (bus0 units), free-dispatch gross margin:
  electrolysis : eff*lam_H2 + eff2*lam_heat - lam_el - mc
  SMR CC       : eff*lam_H2 + eff2*lam_atm + eff3*lam_stored - lam_gas - mc
  FT           : eff*lam_oil + eff2*lam_stored + eff3*lam_heat - lam_H2 - mc
Recovery = sum_t w_t * max(0, margin_t) / capital_cost.
"""
import warnings

import numpy as np
import pypsa

warnings.filterwarnings("ignore")

NODES = ["BEWAL", "FR", "GB", "DE"]


def load(year):
    return pypsa.Network(
        f"results/walloon/scen_central/networks/base_s_adm___{year}.nc"
    )


def price(n, bus):
    if bus not in n.buses_t.marginal_price.columns:
        return None
    return n.buses_t.marginal_price[bus]


def recovery(margin_t, w, capital_cost):
    gross = (np.maximum(margin_t, 0.0) * w).sum()
    return gross / capital_cost, gross


def run(year):
    n = load(year)
    w = n.snapshot_weightings.objective
    suffix = f"-{year}"
    out = {}

    lam_atm = price(n, "co2 atmosphere")
    lam_oil = price(n, "EU oil")

    # --- technology parameters (identical across nodes for a given vintage) ---
    ely = n.links[(n.links.carrier == "H2 Electrolysis") & n.links.index.str.endswith(suffix)]
    smrcc = n.links[(n.links.carrier == "SMR CC") & n.links.index.str.endswith(suffix)]
    smr = n.links[(n.links.carrier == "SMR") & n.links.index.str.endswith(suffix)]
    ft = n.links[(n.links.carrier == "Fischer-Tropsch") & n.links.index.str.endswith(suffix)]

    p = {}
    for name, df in [("ely", ely), ("smrcc", smrcc), ("smr", smr), ("ft", ft)]:
        r = df.iloc[0]
        p[name] = dict(
            eff=r.efficiency,
            eff2=r.efficiency2,
            eff3=r.efficiency3,
            cc=r.capital_cost,
            mc=r.marginal_cost,
        )
    out["params"] = p

    # --- pass-through of a levy into lam_H2, per marginal technology ---
    # SMR CC buries eff3 tCO2 per MW_gas and makes eff MWh_H2 -> eff3/eff t/MWh_H2
    passthru_smrcc = p["smrcc"]["eff3"] / p["smrcc"]["eff"]
    out["passthru_smrcc"] = passthru_smrcc
    out["passthru_smr"] = 0.0  # unabated SMR sequesters nothing

    rows = {}
    for node in NODES:
        lam_h2 = price(n, f"{node} H2")
        lam_el = price(n, node)
        lam_gas = price(n, f"{node} gas")
        lam_st = price(n, f"{node} co2 stored")
        heat_bus = f"{node} urban central heat"
        lam_heat = price(n, heat_bus)
        if lam_heat is None:
            lam_heat = lam_h2 * 0.0
        rows[node] = dict(
            lam_h2=lam_h2, lam_el=lam_el, lam_gas=lam_gas,
            lam_st=lam_st, lam_heat=lam_heat,
        )

    def ely_recovery(node, dh2):
        r = rows[node]
        m = (p["ely"]["eff"] * (r["lam_h2"] + dh2)
             + p["ely"]["eff2"] * r["lam_heat"]
             - r["lam_el"] - p["ely"]["mc"])
        return recovery(m, w, p["ely"]["cc"])[0]

    def ft_recovery(node, dh2, dlevy):
        r = rows[node]
        m = (p["ft"]["eff"] * lam_oil
             + p["ft"]["eff2"] * (r["lam_st"] - dlevy)
             + p["ft"]["eff3"] * r["lam_heat"]
             - (r["lam_h2"] + dh2) - p["ft"]["mc"])
        return recovery(m, w, p["ft"]["cc"])[0]

    def smrcc_recovery(node, dh2, dlevy):
        r = rows[node]
        m = (p["smrcc"]["eff"] * (r["lam_h2"] + dh2)
             + p["smrcc"]["eff2"] * lam_atm
             + p["smrcc"]["eff3"] * (r["lam_st"] - dlevy)
             - r["lam_gas"] - p["smrcc"]["mc"])
        return recovery(m, w, p["smrcc"]["cc"])[0]

    out["rows"] = rows
    out["fns"] = (ely_recovery, ft_recovery, smrcc_recovery)
    out["n"] = n
    return out


def sweep(year, marginal_h2_tech):
    r = run(year)
    ely_rec, ft_rec, smrcc_rec = r["fns"]
    pt = r["passthru_smrcc"] if marginal_h2_tech == "SMR CC" else 0.0

    print(f"\n{'='*78}\n{year}  —  marginal H2 supplier: {marginal_h2_tech}"
          f"  (lam_H2 pass-through {pt:.4f} EUR/MWh_H2 per EUR/t)\n{'='*78}")
    print(f"{'levy':>6} {'dlam_H2':>8} | "
          + " ".join(f"{'ely '+nd:>10}" for nd in NODES) + " | "
          + " ".join(f"{'FT '+nd:>9}" for nd in NODES))
    for levy in [0, 10, 20, 30, 52, 70, 100, 150, 200]:
        dh2 = pt * levy
        e = [ely_rec(nd, dh2) * 100 for nd in NODES]
        f = [ft_rec(nd, dh2, levy) * 100 for nd in NODES]
        print(f"{30+levy:>6} {dh2:>8.2f} | "
              + " ".join(f"{v:>9.1f}%" for v in e) + " | "
              + " ".join(f"{v:>8.1f}%" for v in f))

    # crossover: levy at which each node's electrolyser reaches 100 %
    print("\n  levy at which the electrolyser reaches 100 % capex recovery"
          " (regime A, SMR CC marginal):")
    cross = {}
    for nd in NODES:
        lo, hi = 0.0, 3000.0
        if ely_rec(nd, pt * hi) < 1.0:
            print(f"    {nd:<6} never within +3000 EUR/t")
            cross[nd] = None
            continue
        for _ in range(80):
            mid = (lo + hi) / 2
            if ely_rec(nd, pt * mid) < 1.0:
                lo = mid
            else:
                hi = mid
        cross[nd] = 30 + hi
        print(f"    {nd:<6} co2_sequestration_cost = {30+hi:8.1f} EUR/t"
              f"   (lam_H2 {r['rows'][nd]['lam_h2'].mul(r['n'].snapshot_weightings.objective).sum()/r['n'].snapshot_weightings.objective.sum() + pt*hi:.2f} EUR/MWh)")
    return r, cross, pt


def regime_b(year=2050, cap_node="FR"):
    """Above the crossover, electrolysis sets lam_H2: the pass-through stops."""
    r = run(year)
    ely_rec, ft_rec, smrcc_rec = r["fns"]
    pt = r["passthru_smrcc"]
    lo, hi = 0.0, 3000.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if ely_rec(cap_node, pt * mid) < 1.0:
            lo = mid
        else:
            hi = mid
    cross, dh2_cap = 30 + hi, pt * hi
    print(f"\n{'='*78}\n{year} regime B — lam_H2 capped by {cap_node} electrolysis from "
          f"{cross:.1f} EUR/t (dlam_H2 frozen at +{dh2_cap:.2f} EUR/MWh_H2)\n{'='*78}")
    print(f"{'levy':>6} {'dlam_H2':>8} | " + " ".join(f"{'FT '+nd:>9}" for nd in NODES)
          + "  | regime")
    for levy in [30, 49.2, 52, 70, 100, 150, 200, 300, 400]:
        if 30 + levy <= cross:
            dh2, reg = pt * levy, "A (SMR CC)"
        else:
            dh2, reg = dh2_cap, "B (electrolysis)"
        f = [ft_rec(nd, dh2, levy) * 100 for nd in NODES]
        print(f"{30+levy:>6.0f} {dh2:>8.2f} | "
              + " ".join(f"{v:>8.1f}%" for v in f) + f"  | {reg}")

    p = r["params"]
    dA = (-p["ft"]["eff2"] - pt) / p["ft"]["eff"]
    dB = (-p["ft"]["eff2"]) / p["ft"]["eff"]
    print(f"\n  FT margin slope, EUR/MWh_oil per EUR/t of levy:"
          f"   regime A {dA:+.4f}   regime B {dB:+.4f}")
    print(f"  FT needs 1/{p['ft']['eff']:.3f} = {1/p['ft']['eff']:.3f} MWh_H2 per MWh_oil;"
          f" SMR CC buries {pt:.4f} tCO2/MWh_H2 = {pt/p['ft']['eff']:.4f} t/MWh_oil,"
          f" FT recycles {-p['ft']['eff2']/p['ft']['eff']:.4f} t/MWh_oil")
    return cross, dh2_cap


if __name__ == "__main__":
    for year, tech in [(2040, "SMR"), (2050, "SMR CC")]:
        sweep(year, tech)
    regime_b()
