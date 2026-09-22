# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Assemble every (scenario, turbine, region, density) result into the four tables
the report is built from, and dump the headline numbers as JSON so that the
LaTeX text never has to restate a figure by hand.

``potential_summary``   the full cross-product, one row per case
``exclusion_waterfall`` how much land each successive constraint removes
``sensitivity``         reference scenario across turbine classes and densities
``comparison``          this study against the numbers currently in circulation
"""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_stats(paths):
    return [json.loads(Path(p).read_text()) for p in paths]


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.config
    scenarios = cfg["scenarios"]
    turbines = {k: v for k, v in cfg["turbines"].items() if isinstance(v, dict)}
    ref_scenario = cfg["reference_scenario"]
    ref_turbine = cfg["reference_turbine"]
    ref_density = cfg["reference_density"]
    bench = cfg["benchmarks"]

    summary = pd.concat(
        [pd.read_csv(p) for p in snakemake.input.potentials], ignore_index=True
    )
    summary["scenario_title"] = summary["scenario"].map(
        {k: v["title"] for k, v in scenarios.items()}
    )
    summary["turbine_label"] = summary["turbine"].map(
        {k: v["label"] for k, v in turbines.items()}
    )
    order = {s: i for i, s in enumerate(scenarios)}
    summary = summary.sort_values(
        ["region", "turbine", "density_case", "scenario"],
        key=lambda c: c.map(order) if c.name == "scenario" else c,
    )
    summary.to_csv(snakemake.output.summary, index=False)

    # ------------------------------------------------------------------
    # Waterfall: eligible area after each successive constraint group.
    # Reported on the reference turbine, both regions.
    # ------------------------------------------------------------------
    region_stats = json.loads(Path(snakemake.input.region_stats).read_text())
    frag = json.loads(Path(snakemake.input.fragmentation).read_text())
    avail = pd.DataFrame(load_stats(snakemake.input.availability_stats))
    avail = avail[avail["turbine"] == ref_turbine]

    # S0 is PyPSA-Eur's own constraint set, not the first rung of the Walloon
    # ladder: it is a different specification, not a subset of S1, so its area
    # is NOT comparable step-wise with the rest.  It is carried in the table as
    # a reference line with no "removed" figure.
    ladder = [s for s in scenarios if scenarios[s]["mode"] == "walloon"]

    rows = []
    for region in sorted(avail["region"].unique()):
        sub = avail[avail["region"] == region].set_index("scenario")
        total = region_stats[
            "admin_area_km2" if region == "admin" else "model_area_km2"
        ]
        for name in scenarios:
            if name not in sub.index:
                continue
            area = float(sub.loc[name, "eligible_area_km2"])
            if name in ladder:
                i = ladder.index(name)
                previous = (
                    total
                    if i == 0
                    else float(sub.loc[ladder[i - 1], "eligible_area_km2"])
                )
                removed = round(previous - area, 1)
            else:
                removed = None
            rows.append(
                {
                    "region": region,
                    "scenario": name,
                    "title": scenarios[name]["title"],
                    "in_ladder": name in ladder,
                    "eligible_area_km2": round(area, 1),
                    "share_of_region_pct": round(100 * area / total, 2),
                    "removed_vs_previous_km2": removed,
                }
            )
    waterfall = pd.DataFrame(rows)
    waterfall.to_csv(snakemake.output.waterfall, index=False)

    # ------------------------------------------------------------------
    # Sensitivity on the reference scenario
    # ------------------------------------------------------------------
    sens = summary[summary["scenario"] == ref_scenario].copy()
    sens = sens[
        [
            "region",
            "turbine",
            "turbine_label",
            "density_case",
            "capacity_density_mw_km2",
            "eligible_area_km2",
            "p_nom_max_mw",
            "flh_h",
            "energy_twh",
            "n_turbines",
        ]
    ]
    sens.to_csv(snakemake.output.sensitivity, index=False)

    # ------------------------------------------------------------------
    # Headline numbers and the comparison table
    # ------------------------------------------------------------------
    def pick(scenario, region, turbine=ref_turbine, density=ref_density):
        sel = summary[
            (summary["scenario"] == scenario)
            & (summary["region"] == region)
            & (summary["turbine"] == turbine)
            & (summary["density_case"] == density)
        ]
        if sel.empty:
            raise RuntimeError(f"missing case {scenario}/{region}/{turbine}/{density}")
        return sel.iloc[0]

    ref_admin = pick(ref_scenario, "admin")
    ref_model = pick(ref_scenario, "model")
    base_admin = pick("S0_pypsa_eur", "admin")
    base_model = pick("S0_pypsa_eur", "model")

    headline = {
        "reference_scenario": ref_scenario,
        "reference_turbine": ref_turbine,
        "reference_turbine_label": turbines[ref_turbine]["label"],
        "reference_density_case": ref_density,
        "reference_density_mw_km2": float(ref_admin["capacity_density_mw_km2"]),
        "admin": {
            "region_area_km2": region_stats["admin_area_km2"],
            "eligible_area_km2": float(ref_admin["eligible_area_km2"]),
            "eligible_share_pct": round(
                100 * ref_admin["eligible_area_km2"] / region_stats["admin_area_km2"], 2
            ),
            "p_nom_max_mw": float(ref_admin["p_nom_max_mw"]),
            "flh_h": float(ref_admin["flh_h"]),
            "energy_twh": float(ref_admin["energy_twh"]),
            "n_turbines": int(ref_admin["n_turbines"]),
        },
        "model": {
            "region_area_km2": region_stats["model_area_km2"],
            "eligible_area_km2": float(ref_model["eligible_area_km2"]),
            "eligible_share_pct": round(
                100 * ref_model["eligible_area_km2"] / region_stats["model_area_km2"], 2
            ),
            "p_nom_max_mw": float(ref_model["p_nom_max_mw"]),
            "flh_h": float(ref_model["flh_h"]),
            "energy_twh": float(ref_model["energy_twh"]),
            "n_turbines": int(ref_model["n_turbines"]),
        },
        "pypsa_eur_baseline": {
            "admin_eligible_area_km2": float(base_admin["eligible_area_km2"]),
            "admin_p_nom_max_mw": float(base_admin["p_nom_max_mw"]),
            "model_eligible_area_km2": float(base_model["eligible_area_km2"]),
            "model_p_nom_max_mw": float(base_model["p_nom_max_mw"]),
        },
        "region_stats": region_stats,
        "benchmarks": bench,
    }

    # Range across turbine classes and density cases, reference scenario.
    span = summary[
        (summary["scenario"] == ref_scenario) & (summary["region"] == "model")
    ]
    headline["model_range_mw"] = [
        float(span["p_nom_max_mw"].min()),
        float(span["p_nom_max_mw"].max()),
    ]
    span_admin = summary[
        (summary["scenario"] == ref_scenario) & (summary["region"] == "admin")
    ]
    headline["admin_range_mw"] = [
        float(span_admin["p_nom_max_mw"].min()),
        float(span_admin["p_nom_max_mw"].max()),
    ]

    # The first rung of the ladder is measured against the whole region, so its
    # "removed" figure is not the cost of a rule but the cost of zoning as a
    # whole.  The rule costs proper are rungs 2..N, each measured against the
    # land its predecessor left.
    lad = waterfall[(waterfall["region"] == "admin") & waterfall["in_ladder"]]
    zoning_only = lad.iloc[0]
    steps = lad.iloc[1:]
    biggest = steps.loc[steps["removed_vs_previous_km2"].idxmax()]
    headline["zoning_only_km2"] = float(zoning_only["eligible_area_km2"])
    headline["largest_step"] = {
        "scenario": biggest["scenario"],
        "title": biggest["title"],
        "removed_km2": float(biggest["removed_vs_previous_km2"]),
        "share_of_predecessor_pct": round(
            100
            * float(biggest["removed_vs_previous_km2"])
            / (
                float(biggest["removed_vs_previous_km2"])
                + float(biggest["eligible_area_km2"])
            ),
            1,
        ),
    }
    headline["setback_cut_pct"] = headline["largest_step"]["share_of_predecessor_pct"]
    # Everything after the largest step, together.
    after = steps[steps.index > biggest.name]
    headline["remaining_steps_removed_km2"] = round(
        float(after["removed_vs_previous_km2"].sum()), 1
    )

    # Energy density per km2 of eligible land, reference scenario, admin region.
    dens = summary[
        (summary["scenario"] == ref_scenario)
        & (summary["region"] == "admin")
        & (summary["density_case"] == ref_density)
    ]
    headline["energy_density_gwh_km2"] = {
        r["turbine"]: round(1000 * r["energy_twh"] / r["eligible_area_km2"], 1)
        for _, r in dens.iterrows()
    }

    # ------------------------------------------------------------------
    # Developability: the eligible land is fragmented, and an area-based
    # capacity assumes an array that a 3-hectare patch cannot hold.  Report the
    # capacity on the raw area and on the two filtered areas as a bracket.
    # ------------------------------------------------------------------
    density = headline["reference_density_mw_km2"]
    headline["fragmentation"] = frag
    headline["developable"] = {
        "all_km2": frag["area_km2"],
        "all_mw": round(frag["area_km2"] * density),
        "ge1_km2": frag["area_in_patches_ge_1_turbine_km2"],
        "ge1_mw": round(frag["area_in_patches_ge_1_turbine_km2"] * density),
        "ge4_km2": frag["area_in_patches_ge_4_turbines_km2"],
        "ge4_mw": round(frag["area_in_patches_ge_4_turbines_km2"] * density),
    }

    Path(snakemake.output.headline).write_text(json.dumps(headline, indent=2))

    comparison = pd.DataFrame(
        [
            {
                "source": "PyPSA-Wal today (input_parameters_for_models.csv)",
                "basis": "PNEC wallon / EDORA, expert judgement",
                "region": "BEWAL (model)",
                "capacity_mw": bench["model_p_nom_max_mw"],
                "energy_twh": round(
                    bench["model_p_nom_max_mw"] * ref_model["flh_h"] / 1e6, 2
                ),
            },
            {
                "source": "PyPSA-Eur land eligibility (CORINE + Natura 2000)",
                "basis": "this study, scenario S0",
                "region": "BEWAL (model)",
                "capacity_mw": round(float(base_model["p_nom_max_mw"])),
                "energy_twh": round(float(base_model["energy_twh"]), 2),
            },
            {
                "source": "Walloon legal constraint set",
                "basis": f"this study, scenario {ref_scenario}",
                "region": "BEWAL (model)",
                "capacity_mw": round(float(ref_model["p_nom_max_mw"])),
                "energy_twh": round(float(ref_model["energy_twh"]), 2),
            },
            {
                "source": "Walloon legal constraint set",
                "basis": f"this study, scenario {ref_scenario}",
                "region": "Wallonia (administrative)",
                "capacity_mw": round(float(ref_admin["p_nom_max_mw"])),
                "energy_twh": round(float(ref_admin["energy_twh"]), 2),
            },
            {
                "source": "Walloon legal constraint set, patches >= 1 turbine array",
                "basis": f"this study, {ref_scenario}, developability filter",
                "region": "Wallonia (administrative)",
                "capacity_mw": headline["developable"]["ge1_mw"],
                "energy_twh": round(
                    headline["developable"]["ge1_mw"] * ref_admin["flh_h"] / 1e6, 2
                ),
            },
            {
                "source": "Walloon legal constraint set, patches >= 4 turbine arrays",
                "basis": f"this study, {ref_scenario}, strict developability filter",
                "region": "Wallonia (administrative)",
                "capacity_mw": headline["developable"]["ge4_mw"],
                "energy_twh": round(
                    headline["developable"]["ge4_mw"] * ref_admin["flh_h"] / 1e6, 2
                ),
            },
            {
                "source": "SPW/Gembloux favourable-zone update 2022, '180 m' case",
                "basis": "site-by-site simulation, additional potential only",
                "region": "Wallonia (administrative)",
                "capacity_mw": None,
                "energy_twh": round(bench["spw2022_new_gwh"] / 1000, 2),
            },
            {
                "source": "Installed fleet, end 2024",
                "basis": "EDORA / Renouvelle",
                "region": "Wallonia (administrative)",
                "capacity_mw": bench["installed_2024_mw"],
                "energy_twh": None,
            },
            {
                "source": "PNEC / PACE 2030 onshore-wind target",
                "basis": "Walloon Government",
                "region": "Wallonia (administrative)",
                "capacity_mw": None,
                "energy_twh": round(bench["target_2030_gwh"] / 1000, 2),
            },
        ]
    )
    comparison.to_csv(snakemake.output.comparison, index=False)

    logger.info("headline\n%s", json.dumps(headline, indent=2))
