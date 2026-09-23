# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Assemble every (scenario, turbine, density) result into the tables the report is
built from, and dump the headline numbers as JSON so that the LaTeX text never
has to restate a figure by hand.

``potential_summary``   the full cross-product, one row per case
``exclusion_waterfall`` how much land each successive constraint removes
``sensitivity``         reference scenario across turbine classes and densities
``comparison``          this study against the numbers currently in circulation
``bregilab``            the reconciliation with the VITO Dynamic Energy Atlas

The headline capacity is the **placement** figure --- machines allocated on the
eligible raster under a minimum inter-turbine distance --- not area times
density.  Area times density is retained as a cross-check and to make the
comparison with studies that report on that convention possible.

Everything is computed for the administrative Walloon Region.  The model's
``BEWAL`` node is a different polygon and is deliberately out of scope; see the
report.
"""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

REGION = "admin"


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
    ref_place = cfg["placement"]["reference_case"]
    bench = cfg["benchmarks"]
    breg = cfg["bregilab"]

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
        ["turbine", "density_case", "scenario"],
        key=lambda c: c.map(order) if c.name == "scenario" else c,
    )
    summary.to_csv(snakemake.output.summary, index=False)

    placement = pd.concat(
        [pd.read_csv(p) for p in snakemake.input.placement], ignore_index=True
    )
    placement.to_csv(snakemake.output.placement, index=False)

    # ------------------------------------------------------------------
    # Waterfall: eligible area after each successive constraint group.
    # ------------------------------------------------------------------
    region_stats = json.loads(Path(snakemake.input.region_stats).read_text())
    frag = json.loads(Path(snakemake.input.fragmentation).read_text())
    servitudes = json.loads(Path(snakemake.input.servitudes).read_text())
    fleet = json.loads(Path(snakemake.input.fleet).read_text())
    avail = pd.DataFrame(load_stats(snakemake.input.availability_stats))
    avail = avail[avail["turbine"] == ref_turbine]

    # S0 is PyPSA-Eur's own constraint set, not the first rung of the Walloon
    # ladder: it is a different specification, not a subset of S1, so its area
    # is NOT comparable step-wise with the rest.  It is carried in the table as
    # a reference line with no "removed" figure.
    ladder = [s for s in scenarios if scenarios[s]["mode"] == "walloon"]

    rows = []
    sub = avail[avail["region"] == REGION].set_index("scenario")
    total = region_stats["admin_area_km2"]
    for name in scenarios:
        if name not in sub.index:
            continue
        area = float(sub.loc[name, "eligible_area_km2"])
        if name in ladder:
            i = ladder.index(name)
            previous = (
                total if i == 0 else float(sub.loc[ladder[i - 1], "eligible_area_km2"])
            )
            removed = round(previous - area, 1)
        else:
            removed = None
        rows.append(
            {
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
    # Headline numbers
    # ------------------------------------------------------------------
    def pick(scenario, turbine=ref_turbine, density=ref_density):
        sel = summary[
            (summary["scenario"] == scenario)
            & (summary["region"] == REGION)
            & (summary["turbine"] == turbine)
            & (summary["density_case"] == density)
        ]
        if sel.empty:
            raise RuntimeError(f"missing case {scenario}/{turbine}/{density}")
        return sel.iloc[0]

    ref_model = cfg["placement"]["reference_model"]

    def place(turbine, case=ref_place, model=None, variant="row_major"):
        model = ref_model if model is None else model
        sel = placement[
            (placement["turbine"] == turbine)
            & (placement["spacing_case"] == case)
            & (placement["model"] == model)
        ]
        if model == "free":
            sel = sel[sel["variant"] == variant]
        if sel.empty:
            raise RuntimeError(f"missing placement {turbine}/{case}/{model}")
        return sel.iloc[0]

    ref = pick(ref_scenario)
    s5 = pick("S5_risk")
    base = pick("S0_pypsa_eur")
    ref_flh = float(ref["flh_h"])

    headline = {
        "reference_scenario": ref_scenario,
        "reference_scenario_title": scenarios[ref_scenario]["title"],
        "reference_turbine": ref_turbine,
        "reference_turbine_label": turbines[ref_turbine]["label"],
        "reference_density_case": ref_density,
        "reference_density_mw_km2": float(ref["capacity_density_mw_km2"]),
        "region_area_km2": region_stats["admin_area_km2"],
        "area_density": {
            "eligible_area_km2": float(ref["eligible_area_km2"]),
            "eligible_share_pct": round(
                100 * ref["eligible_area_km2"] / region_stats["admin_area_km2"], 2
            ),
            "p_nom_max_mw": float(ref["p_nom_max_mw"]),
            "flh_h": ref_flh,
            "energy_twh": float(ref["energy_twh"]),
            "n_turbines": int(ref["n_turbines"]),
        },
        "before_servitudes": {
            "scenario": "S5_risk",
            "eligible_area_km2": float(s5["eligible_area_km2"]),
            "p_nom_max_mw": float(s5["p_nom_max_mw"]),
        },
        "pypsa_eur_baseline": {
            "eligible_area_km2": float(base["eligible_area_km2"]),
            "p_nom_max_mw": float(base["p_nom_max_mw"]),
            "energy_twh": float(base["energy_twh"]),
        },
        "region_stats": region_stats,
        "benchmarks": bench,
        "servitude_costs": servitudes,
        "fleet_validation": fleet,
        "fragmentation": frag,
    }

    # ------------------------------------------------------------------
    # Placement: the headline capacity
    # ------------------------------------------------------------------
    p = place(ref_turbine)
    no_h = place(ref_turbine, model="parks")
    free = place(ref_turbine, model="free")
    free_rand = place(ref_turbine, model="free", variant="random")
    small = cfg["placement"]["park"].get("small_groups", "after")
    parks4 = place(ref_turbine, model="parks4+horizon") if small != "none" else p
    lcfg = cfg["placement"]["landscape"]
    spacings = cfg["placement"]["spacings_rotor_diameters"]
    headline["placement"] = {
        "model": ref_model,
        "case": ref_place,
        "min_distance_m": float(p["min_distance_m"]),
        "min_distance_rotor_diameters": float(p["min_distance_rotor_diameters"]),
        "link_m": float(cfg["placement"]["park"]["link_m"]),
        "min_turbines": int(cfg["placement"]["park"]["min_turbines"]),
        "small_groups": small,
        "share_in_groups_below_min_pct": float(p["share_in_groups_below_min_pct"]),
        "share_single_pct": float(p["share_single_pct"]),
        "min_free_azimuth_deg": float(lcfg["min_free_azimuth_deg"]),
        "horizon_radius_m": float(lcfg["horizon_radius_m"]),
        "motorway_exemption_m": float(lcfg["motorway_exemption_m"]),
        "n_parks": int(p["n_parks"]),
        "turbines_per_park": float(p["turbines_per_park"]),
        "median_park_size": float(p["median_park_size"]),
        "largest_park": int(p["largest_park"]),
        "n_turbines": int(p["n_turbines"]),
        "p_nom_max_mw": float(p["p_nom_max_mw"]),
        "effective_density_mw_km2": float(p["effective_density_mw_km2"]),
        "energy_twh": round(float(p["p_nom_max_mw"]) * ref_flh / 1e6, 3),
        "refused_by_horizon": int(p["refused_by_horizon"]),
        "check_min_spacing_m": float(p["check_min_spacing_m"]),
        "check_worst_free_arc_deg": float(p["check_worst_free_arc_deg"]),
        "horizon_cost_pct": round(
            100 * (1 - float(p["p_nom_max_mw"]) / float(no_h["p_nom_max_mw"])), 0
        ),
        "no_horizon_p_nom_max_mw": float(no_h["p_nom_max_mw"]),
        "no_horizon_n_parks": int(no_h["n_parks"]),
        "no_horizon_n_turbines": int(no_h["n_turbines"]),
        "parks_cost_pct": round(
            100 * (1 - float(no_h["p_nom_max_mw"]) / float(free["p_nom_max_mw"])), 0
        ),
        "parks4_p_nom_max_mw": float(parks4["p_nom_max_mw"]),
        "parks4_n_parks": int(parks4["n_parks"]),
        "parks4_n_turbines": int(parks4["n_turbines"]),
        "small_groups_gain_pct": round(
            100 * (float(p["p_nom_max_mw"]) / float(parks4["p_nom_max_mw"]) - 1), 0
        ),
        "free_p_nom_max_mw": float(free["p_nom_max_mw"]),
        "free_n_turbines": int(free["n_turbines"]),
        "free_density_mw_km2": float(free["effective_density_mw_km2"]),
        "free_order_sensitivity_pct": round(
            100
            * abs(float(free_rand["p_nom_max_mw"]) - float(free["p_nom_max_mw"]))
            / float(free["p_nom_max_mw"]),
            1,
        ),
        "share_of_free_pct": round(
            100 * float(p["p_nom_max_mw"]) / float(free["p_nom_max_mw"]), 0
        ),
        "vs_area_density_pct": round(
            100 * float(p["p_nom_max_mw"]) / float(ref["p_nom_max_mw"]) - 100, 1
        ),
        "by_interdistance": {
            str(int(d)): {
                "n_parks": int(place(ref_turbine, model=f"parks+horizon+{int(d) // 1000}km")["n_parks"]),
                "n_turbines": int(place(ref_turbine, model=f"parks+horizon+{int(d) // 1000}km")["n_turbines"]),
                "p_nom_max_mw": float(place(ref_turbine, model=f"parks+horizon+{int(d) // 1000}km")["p_nom_max_mw"]),
            }
            for d in lcfg["interdistance_m"]
        },
        "by_spacing": {
            k: {
                "rotor_diameters": float(spacings[k]),
                "free_mw": float(place(ref_turbine, case=k, model="free")["p_nom_max_mw"]),
                "p_nom_max_mw": float(place(ref_turbine, case=k)["p_nom_max_mw"]),
            }
            for k in spacings
        },
        "by_turbine": {
            t: {
                "p_nom_max_mw": float(place(t)["p_nom_max_mw"]),
                "n_turbines": int(place(t)["n_turbines"]),
                "effective_density_mw_km2": float(place(t)["effective_density_mw_km2"]),
                "eligible_area_km2": float(place(t)["eligible_area_km2"]),
                "free_mw": float(place(t, model="free")["p_nom_max_mw"]),
            }
            for t in turbines
        },
    }
    headline["placement_range_mw"] = [
        min(v["p_nom_max_mw"] for v in headline["placement"]["by_turbine"].values()),
        max(v["p_nom_max_mw"] for v in headline["placement"]["by_turbine"].values()),
    ]

    # ------------------------------------------------------------------
    # Residual allowance for the families that still have no geometry
    # ------------------------------------------------------------------
    res_cfg = cfg["residual_allowance"]
    residual = {"components": res_cfg}
    for case in ("central", "low", "high"):
        survival = 1.0
        for comp in res_cfg.values():
            survival *= 1.0 - float(comp[case])
        residual[case] = {
            "survival": round(survival, 4),
            "p_nom_max_mw": round(float(p["p_nom_max_mw"]) * survival),
            "energy_twh": round(
                float(p["p_nom_max_mw"]) * survival * ref_flh / 1e6, 2
            ),
        }
    # The "low" allowance removes the least and therefore gives the highest
    # capacity; name the bracket by capacity, not by allowance, to avoid the
    # reader having to invert it.
    residual["p_nom_max_range_mw"] = [
        residual["high"]["p_nom_max_mw"],
        residual["low"]["p_nom_max_mw"],
    ]
    headline["residual"] = residual

    # Credible range.  The reference case is the park model with the
    # open-horizon rule; the range is the residual-allowance bracket applied to
    # it.  The inter-distance the Cadre recommends is a *policy* choice rather
    # than an uncertainty about the land, so it is reported separately rather
    # than compounded into the headline range.
    headline["credible_range_mw"] = list(residual["p_nom_max_range_mw"])
    headline["credible_central_mw"] = residual["central"]["p_nom_max_mw"]
    by_id = headline["placement"]["by_interdistance"]
    legacy = [v["p_nom_max_mw"] for v in by_id.values()]
    headline["interdistance_policy_mw"] = [
        round(min(legacy) * residual["central"]["survival"]),
        round(max(legacy) * residual["central"]["survival"]),
    ]

    # External plausibility anchor: how the resulting deployment density
    # compares with the onshore fleet Germany has actually built.
    region_km2 = region_stats["admin_area_km2"]
    de_density = 1000.0 * bench["germany_onshore_gw"] / bench["germany_area_km2"]
    headline["density_check"] = {
        "germany_kw_km2": round(1000 * de_density, 0),
        "germany_turbines_per_1000km2": round(
            1000.0 * bench["germany_onshore_turbines"] / bench["germany_area_km2"], 1
        ),
        "wallonia_today_kw_km2": round(
            1000 * bench["installed_2024_mw"] / region_km2, 0
        ),
        "wallonia_central_kw_km2": round(
            1000 * residual["central"]["p_nom_max_mw"] / region_km2, 0
        ),
        "wallonia_high_kw_km2": round(
            1000 * headline["credible_range_mw"][1] / region_km2, 0
        ),
        "central_vs_germany": round(
            residual["central"]["p_nom_max_mw"] / region_km2 / de_density, 2
        ),
        "high_vs_germany": round(
            headline["credible_range_mw"][1] / region_km2 / de_density, 2
        ),
        "today_vs_germany": round(
            bench["installed_2024_mw"] / region_km2 / de_density, 2
        ),
    }

    # ------------------------------------------------------------------
    # Waterfall-derived narrative numbers
    # ------------------------------------------------------------------
    lad = waterfall[waterfall["in_ladder"]]
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
    after = steps[steps.index > biggest.name]
    headline["remaining_steps_removed_km2"] = round(
        float(after["removed_vs_previous_km2"].sum()), 1
    )

    dens = summary[
        (summary["scenario"] == ref_scenario)
        & (summary["region"] == REGION)
        & (summary["density_case"] == ref_density)
    ]
    headline["energy_density_gwh_km2"] = {
        r["turbine"]: round(1000 * r["energy_twh"] / r["eligible_area_km2"], 1)
        for _, r in dens.iterrows()
    }

    # ------------------------------------------------------------------
    # Sensitivity: every choice priced one at a time
    # ------------------------------------------------------------------
    headline["sensitivity"] = json.loads(Path(snakemake.input.sensitivity).read_text())

    # ------------------------------------------------------------------
    # BREGILAB: their number reproduced from their own rules on this study's
    # data, then bridged to this study's answer one change at a time.
    # ------------------------------------------------------------------
    emu = json.loads(Path(snakemake.input.bregilab).read_text())
    breg_total = float(breg["wallonia_total_gw"]) * 1000.0
    headline["bregilab"] = {
        "reference": breg["reference"],
        "total_mw": breg_total,
        "current_mw": float(breg["wallonia_current_gw"]) * 1000.0,
        "additional_mw": float(breg["wallonia_additional_gw"]) * 1000.0,
        "energy_twh": round(
            (breg["wallonia_current_gwh"] + breg["wallonia_additional_gwh"]) / 1000.0, 2
        ),
        "flh_h": round(float(breg["wallonia_potential_availability_factor"]) * 8760, 0),
        "flh_gross_h": round(
            float(breg["wallonia_potential_availability_factor"]) * 8760
            / float(breg["performance_ratio"]),
            0,
        ),
        "emulation": emu["emulation"],
        "bridge": emu["bridge"],
        "ours_free_mw": float(free["p_nom_max_mw"]),
        "ours_parks_mw": float(no_h["p_nom_max_mw"]),
        "ours_reference_mw": float(p["p_nom_max_mw"]),
        "vs_free": round(breg_total / float(free["p_nom_max_mw"]), 2),
        "vs_reference": round(breg_total / float(p["p_nom_max_mw"]), 2),
        "vs_central": round(breg_total / max(residual["central"]["p_nom_max_mw"], 1), 2),
    }

    Path(snakemake.output.headline).write_text(json.dumps(headline, indent=2))

    # ------------------------------------------------------------------
    # Comparison table
    # ------------------------------------------------------------------
    def twh(mw, flh=ref_flh):
        return None if mw is None else round(mw * flh / 1e6, 2)

    comparison = pd.DataFrame(
        [
            {
                "source": "PyPSA-Wal today (input_parameters_for_models.csv)",
                "basis": "PNEC wallon / EDORA, expert judgement",
                "capacity_mw": bench["model_p_nom_max_mw"],
                "energy_twh": twh(bench["model_p_nom_max_mw"]),
            },
            {
                "source": "PyPSA-Eur default land eligibility",
                "basis": "this study, scenario S0, area x 3 MW/km2",
                "capacity_mw": round(float(base["p_nom_max_mw"])),
                "energy_twh": round(float(base["energy_twh"]), 2),
            },
            {
                "source": "BREGILAB / VITO Dynamic Energy Atlas",
                "basis": "Clymans et al. 2022, V112 at 5 D, free allocation, gross",
                "capacity_mw": round(breg_total),
                "energy_twh": headline["bregilab"]["energy_twh"],
            },
            {
                "source": "BREGILAB's rules on this study's data",
                "basis": "this study, emulation of the WTN scenario, V112 at 5 D",
                "capacity_mw": round(emu["emulation"]["with_fleet_mw"]),
                "energy_twh": None,
            },
            {
                "source": "Walloon constraint set, area x density",
                "basis": f"this study, {ref_scenario}, "
                f"{headline['reference_density_mw_km2']:.2f} MW/km2",
                "capacity_mw": round(float(ref["p_nom_max_mw"])),
                "energy_twh": round(float(ref["energy_twh"]), 2),
            },
            {
                "source": "Walloon constraint set, free allocation",
                "basis": f"this study, {ref_scenario}, "
                f"{headline['placement']['min_distance_m']:.0f} m between machines, "
                "no grouping rule",
                "capacity_mw": round(float(free["p_nom_max_mw"])),
                "energy_twh": round(float(free["p_nom_max_mw"]) * ref_flh / 1e6, 2),
            },
            {
                "source": "Walloon constraint set, parks of 4 or more",
                "basis": f"this study, {ref_scenario}, no landscape rule",
                "capacity_mw": round(float(no_h["p_nom_max_mw"])),
                "energy_twh": round(float(no_h["p_nom_max_mw"]) * ref_flh / 1e6, 2),
            },
            {
                "source": "Walloon constraint set, parks and open horizon",
                "basis": f"this study, {ref_scenario}, gross reference",
                "capacity_mw": round(float(p["p_nom_max_mw"])),
                "energy_twh": headline["placement"]["energy_twh"],
            },
            {
                "source": "Walloon constraint set, machines placed, residual allowance",
                "basis": "this study, central allowance for the families with no "
                "geometry",
                "capacity_mw": residual["central"]["p_nom_max_mw"],
                "energy_twh": residual["central"]["energy_twh"],
            },
            {
                "source": "SPW/Gembloux favourable-zone update 2022, '180 m' case",
                "basis": "site-by-site simulation, additional potential only",
                "capacity_mw": None,
                "energy_twh": round(bench["spw2022_new_gwh"] / 1000, 2),
            },
            {
                "source": "Installed fleet, end 2024",
                "basis": "EDORA / Renouvelle",
                "capacity_mw": bench["installed_2024_mw"],
                "energy_twh": None,
            },
            {
                "source": "PNEC / PACE 2030 onshore-wind target",
                "basis": "Walloon Government",
                "capacity_mw": None,
                "energy_twh": round(bench["target_2030_gwh"] / 1000, 2),
            },
        ]
    )
    comparison.to_csv(snakemake.output.comparison, index=False)

    logger.info("headline\n%s", json.dumps(headline, indent=2))
