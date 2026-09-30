#!/usr/bin/env python3
# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
#
# SPDX-License-Identifier: MIT
"""Write ``data/walloon/network_cost_calibration.csv`` from the regulatory decisions.

The table holds the exogenous network-cost layers of the calibration
(docs/network-costs-review-20260928.md §2–§6): the existing grid (L1), the
non-capacity OPEX (L3) and the regulated add-ons (L4) of electricity and gas
distribution, the Elia and Fluxys revenues behind the tariff view of
transmission, and the physical denominators. ``network_cost_report.py`` reads it.

The per-DSO budgets below are transcribed from the CWaPE decisions, *Budget
2025* and *Budget 2029* columns. They are kept here, not typed into the CSV, so
that the aggregation can be re-checked:

* electricity: CD-25d03-CWaPE-1056 (ORES, Tableau 4), CD-25b20-CWaPE-1043 (RESA),
  CD-25a30-CWaPE-1038 (REW), -1037 (AIESH), -1036 (AIEG), Tableau 8;
* gas: CD-24c28-CWaPE-0890 (ORES gaz, Tableau 1), CD-24c28-CWaPE-0891 (RESA gaz).

M€, nominal. 2025 nominal is EUR2025, the model's price base; 2029 is deflated
by 1.024**4 where a real value is needed.

Usage::

    python scripts/walloon_scripts/build_network_cost_calibration.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

OUT = Path("data/walloon/network_cost_calibration.csv")

# opex (controllable excl. PSO), osp_ctrl, amort, transit, losses, fereso, voirie,
# isoc, other_tax, onssapl, pension, osp_nc, smart, margin_rab, margin_pv, margin_osp, total
ELEC_COLS = ["opex", "osp_ctrl", "amort", "transit", "losses", "fereso", "voirie", "isoc",
             "other_tax", "onssapl", "pension", "osp_nc", "smart", "margin_rab", "margin_pv",
             "margin_osp", "total"]
ELEC = {
    2025: {
        "ORES":  [201.653348, 29.977478, 149.837422, 0.028239, 67.814049, 0.0, 32.334287, 30.226455, 0.368465, 0.0, 1.770108, -1.283537, 16.169396, 88.994794, 21.444234, 0.137443, 639.472181],
        "RESA":  [74.626848, 12.840919, 38.786411, 0.603278, 15.087373, 11.678492, 9.712898, 8.887478, 0.0, 3.730785, 0.213460, 0.646622, 5.072115, 29.607082, 4.538241, 0.073899, 216.105902],
        "REW":   [3.112544, 0.907323, 3.542753, -0.002886, 0.625743, 0.0, 0.414821, 0.832052, 0.045867, 0.0, 0.0, 0.022885, 0.424619, 2.224028, 0.360125, 0.0, 12.509875],
        "AIESH": [4.291351, 0.999640, 3.028871, 0.033621, 1.779686, 0.058518, 0.637773, 0.848245, 0.000045, 0.677850, 0.0, 0.042065, 0.374943, 2.095570, 0.378706, 0.0, 15.246885],
        "AIEG":  [3.687637, 0.641245, 2.002062, 0.225412, 1.657856, 0.0, 0.675727, 0.715083, 0.0, 0.360709, 0.0, -0.025207, 0.878862, 2.046314, 0.135263, 0.002205, 13.003168],
    },
    2029: {
        "ORES":  [208.757663, 32.194835, 160.972996, 0.030328, 58.716231, 0.0, 34.725971, 33.398212, 0.368465, 0.0, 0.281021, -2.006574, 43.745330, 116.842779, 11.281239, 0.001621, 699.310117],
        "RESA":  [81.784807, 13.790728, 41.655342, 0.647901, 17.912912, 4.733390, 11.831499, 8.800677, 0.0, 4.900041, 0.0, 0.777129, 11.642226, 37.804740, 2.466463, 0.020796, 238.768650],
        "REW":   [3.519233, 0.974435, 3.804801, -0.003099, 0.576853, 0.0, 0.445504, 0.821837, 0.049260, 0.0, 0.0, 0.022173, 0.483158, 2.296018, 0.189097, 0.0, 13.179271],
        "AIESH": [4.592328, 1.073585, 3.252909, 0.039090, 1.822279, 0.059919, 0.637773, 0.812265, 0.000045, 0.674014, 0.0, 0.057612, 0.387482, 2.479537, 0.186797, 0.0, 16.075634],
        "AIEG":  [4.310017, 0.688676, 2.150149, 0.242085, 1.528326, 0.0, 0.725709, 0.781323, 0.0, 0.535739, 0.0, -0.070842, 0.728743, 2.244279, 0.070113, 0.001993, 13.936309],
    },
}
# opex, osp_ctrl, amort, voirie, isoc, margin_rab, margin_pv, margin_osp, osp_nc, total
GAS_COLS = ["opex", "osp_ctrl", "amort", "voirie", "isoc", "margin_rab", "margin_pv", "margin_osp", "osp_nc", "total"]
GAS = {
    2025: {
        "ORES": [52.935892, 8.618698, 66.693252, 18.251629, 10.422697, 44.999591, 5.609031, 7.590367, 2.801928, 218.549789],
        "RESA": [35.993825, 3.971369, 25.465691, 7.557730, 8.583957, 23.801484, 7.478041, 0.074287, -0.367654, 116.484269],
    },
}

SRC_E = "CWaPE revenus autorises electricite 2025-2029 (decisions 1036/1037/1038/1043/1056)"
SRC_G = "CWaPE revenus autorises gaz 2025-2029 (CD-24c28-CWaPE-0890/0891)"


def _elec_families(year: int) -> dict[str, float]:
    df = pd.DataFrame(ELEC[year], index=ELEC_COLS).T
    t = df.sum()
    assert abs(df[ELEC_COLS[:-1]].sum(axis=1) - df.total).max() < 1e-3, "per-DSO sum check"
    return {
        "capital": t.amort + t.margin_rab + t.margin_pv + t.isoc,
        "opex": t.opex,
        "losses": t.losses,
        "pso": t.osp_ctrl + t.osp_nc + t.margin_osp,
        "road_fee": t.voirie,
        "smart_meters": t.smart,
        "other": t.transit + t.fereso + t.other_tax + t.onssapl + t.pension,
        "total": t.total,
    }


def _gas_families(year: int) -> dict[str, float]:
    df = pd.DataFrame(GAS[year], index=GAS_COLS).T
    t = df.sum()
    return {
        "capital": t.amort + t.margin_rab + t.margin_pv + t.isoc,
        "opex": t.opex,
        "road_fee": t.voirie,
        "pso": t.osp_ctrl + t.osp_nc + t.margin_osp,
        "other": t.total - (t.amort + t.margin_rab + t.margin_pv + t.isoc + t.opex + t.voirie
                            + t.osp_ctrl + t.osp_nc + t.margin_osp),
        "total": t.total,
    }


def main() -> None:
    rows = []

    def add(network, layer, item, year, value, unit, source, note=""):
        rows.append(dict(network=network, layer=layer, item=item, year=year,
                         value=round(float(value), 4), unit=unit, source=source, note=note))

    for y in (2025, 2029):
        f = _elec_families(y)
        for k, layer in [("capital", "L1"), ("opex", "L3"), ("losses", "L4"), ("pso", "L4"),
                         ("road_fee", "L4"), ("smart_meters", "L4"), ("other", "L4"),
                         ("total", "total")]:
            add("electricity_distribution", layer, k, y, f[k], "MEUR nominal", SRC_E)
    # split of the 2025 OPEX: asset maintenance = FOM 1.5-2 % x replacement value
    # (1.5-2.5 x net book value 3.77 bn EUR) = 85-190; the rest is per connection.
    add("electricity_distribution", "L3", "opex_asset_share", 2025, 0.48, "-",
        "midpoint of 85-190 MEUR asset maintenance over 287 MEUR OPEX",
        "per-connection part (0.52) indexed on the EAN count")
    add("electricity_distribution", "denominator", "ean", 2024, 1.95e6, "connections",
        "CWaPE CD-25k27-CWaPE-0967 §2.3.4")
    add("electricity_distribution", "denominator", "ean_growth", 2024, 0.010, "1/yr",
        "CWaPE CD-25k27-CWaPE-0967 §2.3.4 (2007-2024 average)")
    add("electricity_distribution", "denominator", "energy_withdrawn", 2024, 12.678, "TWh",
        "CWaPE CD-25k27-CWaPE-0967 §2.3.4, excluding compensated volumes")
    add("electricity_distribution", "benchmark", "capex_2020_2024", 2022, 302.3, "MEUR/yr gross",
        "CWaPE CD-25k27-CWaPE-0967 Tableau 14")
    add("electricity_distribution", "benchmark", "capex_2026_2030", 2028, 661.8, "MEUR/yr gross",
        "CWaPE CD-25k27-CWaPE-0967 Tableau 14")
    add("electricity_distribution", "benchmark", "capex_transition_2026_2030", 2028, 774.1,
        "MEUR over 5 yr", "CWaPE CD-25k27-CWaPE-0967 Tableau 15, E1.1+E1.3+E1.4+GW subsidy")

    g = _gas_families(2025)
    for k, layer in [("capital", "L1"), ("opex", "L3"), ("road_fee", "L4"), ("pso", "L4"),
                     ("other", "L4"), ("total", "total")]:
        add("gas_distribution", layer, k, 2025, g[k], "MEUR nominal", SRC_G)
    add("gas_distribution", "denominator", "meters", 2025, 801102, "meters",
        "CWaPE CD-26g30-CWaPE-0981 Tableau 2")
    add("gas_distribution", "denominator", "energy_distributed", 2025, 17.426, "TWh",
        "CWaPE CD-26g30-CWaPE-0981 Tableau 2")
    add("gas_distribution", "denominator", "mains_km", 2025, 14497, "km",
        "CWaPE CD-26g30-CWaPE-0981 Tableau 2")
    add("gas_distribution", "L4", "decommissioning_per_connection", 2025, 1340, "EUR/connection",
        "Verbraucherzentrale NRW survey of 115 DSOs: 930 (seal) - 1 750 (remove), midpoint",
        "secondary source; not yet applied (no TIMES disconnection series)")

    for y, v in [(2024, 970.712516), (2025, 1552.071768), (2026, 1706.443973), (2027, 1875.950488)]:
        add("electricity_transmission", "tariff", "elia_allowed_revenue", y, v, "MEUR nominal",
            "CREG (B)658E/85 Tableau 1bis (Belgium, all Elia voltages)")
    add("electricity_transmission", "benchmark", "walloon_local_transmission_plan", 2028, 691,
        "MEUR over 2026-2030", "CWaPE CD-26g30-CWaPE-1283 (48 % historical realisation)")
    add("electricity_transmission", "benchmark", "elia_capex_2024_2027", 2025, 6400,
        "MEUR over 2024-2027", "CREG (B)658E/85 §27")
    add("gas_transmission", "tariff", "fluxys_allowed_revenue", 2025, 317.0, "MEUR nominal",
        "Fluxys Belgium tariff consultation (Oct 2022), pre-decision indicative 2025 value",
        "approved values confidential (CREG (B)656G/50); research summary, not re-checked")

    out = pd.DataFrame(rows)
    header = (
        "# Exogenous network-cost layers and denominators for the calibration.\n"
        "# Generated by scripts/walloon_scripts/build_network_cost_calibration.py -- do not hand-edit.\n"
        "# Read by scripts/walloon_scripts/network_cost_report.py. docs/network-costs-review-20260928.md §2–§6.\n"
    )
    with OUT.open("w") as fh:
        fh.write(header)
        out.to_csv(fh, index=False, lineterminator="\n")
    e25 = _elec_families(2025)
    print(f"wrote {OUT} ({len(out)} rows); electricity 2025 total {e25['total']:.1f}, "
          f"core {e25['capital'] + e25['opex']:.1f}; gas 2025 core {g['capital'] + g['opex']:.1f}")


if __name__ == "__main__":
    main()
