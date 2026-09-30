#!/usr/bin/env python3
# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
#
# SPDX-License-Identifier: MIT
"""Write the CO₂-trunk rows of ``data/walloon/transmission_cost_overrides.csv``.

The DEA CO₂ pipeline cost that technology-data carries (2 672 EUR/(t/h)/km
onshore) is the cost of a 12-inch line in the 120-500 t/h range, and PyPSA
applies it linearly to any capacity. The trunks the model builds are several
times larger (1 000-5 600 t/h on the 24 September 2026 central run), where the
cost per unit of capacity is much lower: the JRC puts the EU network at
0.62-0.89 M€/km on average (Tumara et al. 2024, doi:10.2760/582433).

The linear formulation cannot represent that, so each corridor gets a fixed
multiplier on its capital cost, computed from the size the corridor reached in
a reference run (the largest total capacity over the horizons) with the
six-tenths rule (:func:`network_calibration.co2_scale_factor`). This is a
one-step linearisation, documented in docs/network-costs-review-20260928.md
§6.5. Re-run it against a new reference when the CO₂ network changes a lot.

Only rows with ``carrier == "CO2 pipeline"`` are rewritten; every other row of
the table (e.g. the ALEGrO project cost) is kept as is.

Usage::

    python scripts/walloon_scripts/build_co2_trunk_overrides.py \\
        results/_archive/scen_central_20260924_vd260923
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.walloon_scripts.network_calibration import co2_scale_factor  # noqa: E402

OVERRIDES = Path("data/walloon/transmission_cost_overrides.csv")
HORIZONS = (2025, 2030, 2040, 2050)


def corridor_sizes(run: Path) -> pd.Series:
    """Largest total CO₂ pipeline capacity (t/h) per unordered corridor."""
    sizes = {}
    for y in HORIZONS:
        fn = run / "networks" / f"base_s_adm___{y}.nc"
        if not fn.exists():
            continue
        n = pypsa.Network(fn)
        c = n.links[(n.links.carrier == "CO2 pipeline") & ~n.links.index.str.endswith("-reversed")]
        loc = n.buses.location
        pairs = [tuple(sorted((loc[a], loc[b]))) for a, b in zip(c.bus0, c.bus1)]
        s = c.p_nom_opt.groupby(pd.MultiIndex.from_tuples(pairs, names=["bus0", "bus1"])).sum()
        for k, v in s.items():
            sizes[k] = max(sizes.get(k, 0.0), float(v))
    if not sizes:
        raise SystemExit(f"no solved networks under {run}/networks")
    return pd.Series(sizes).rename_axis(["bus0", "bus1"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reference_run", type=Path, help="results tree of the reference run")
    ap.add_argument("--q-ref", type=float, default=300.0, help="DEA reference capacity, t/h")
    ap.add_argument("--exponent", type=float, default=0.6, help="cost ∝ capacity**exponent")
    args = ap.parse_args()
    logging.disable(logging.WARNING)

    sizes = corridor_sizes(args.reference_run)
    rows = []
    for (a, b), q in sizes.sort_index().items():
        f = co2_scale_factor(q, args.q_ref, args.exponent)
        if f >= 1.0:
            continue
        rows.append(
            dict(
                component="Link", carrier="CO2 pipeline", bus0=a, bus1=b,
                parameter="capital_cost_factor", value=round(f, 4), reference="",
                unit="-",
                source=(f"six-tenths rule on {q:.0f} t/h ({args.reference_run.name}); "
                        f"DEA reference {args.q_ref:.0f} t/h"),
            )
        )
    new = pd.DataFrame(rows)

    old = pd.read_csv(OVERRIDES, comment="#") if OVERRIDES.exists() else pd.DataFrame()
    header = [l for l in OVERRIDES.read_text().splitlines() if l.startswith("#")] if OVERRIDES.exists() else []
    keep = old[old.carrier != "CO2 pipeline"] if len(old) else old
    out = pd.concat([keep, new], ignore_index=True)
    with OVERRIDES.open("w") as fh:
        for line in header:
            fh.write(line + "\n")
        out.to_csv(fh, index=False, lineterminator="\n")
    print(f"{len(new)} CO2 trunk row(s) written to {OVERRIDES}")
    print(new[["bus0", "bus1", "value", "source"]].to_string(index=False))


if __name__ == "__main__":
    main()
