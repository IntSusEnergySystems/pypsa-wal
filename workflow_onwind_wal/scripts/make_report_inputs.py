# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Generate the LaTeX fragments the report ``\\input``s.

Nothing in the report is typed by hand: every number is a macro defined here
from the workflow's own output, so the text cannot drift away from the tables,
and re-running the workflow with a different assumption updates the prose.
"""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

REGION = "admin"


def tex_escape(s):
    for a, b in [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]:
        s = s.replace(a, b)
    return s


def num(x, digits=0):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "--"
    return f"{x:,.{digits}f}".replace(",", r"\,")


MIDRULE = object()


def tabular(rows, header, align):
    out = [r"\begin{tabular}{" + align + "}", r"\toprule", " & ".join(header) + r" \\",
           r"\midrule"]
    for r in rows:
        if r is MIDRULE:            # a bare separator, not a data row
            out.append(r"\midrule")
            continue
        out.append(" & ".join(r) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)


# Human-readable names for the constraint families added in the last rung.
FAMILY_LABELS = {
    "aviation": "aeronautical servitudes (DGTA obstacle map)",
    "slope": r"slope $\geq 7\,\%$ (ERRUISSOL, 10 m DTM)",
    "heritage": "classified sites, protection zones, UNESCO buffers",
    "radar": "weather radar, radio astronomy, Bertem SSR",
}
FAMILY_MACRO = {"aviation": "Aviation", "slope": "Slope", "heritage": "Heritage",
                "radar": "Radar"}


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.config
    out_dir = Path(snakemake.output.macros).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    headline = json.loads(Path(snakemake.input.headline).read_text())
    summary = pd.read_csv(snakemake.input.summary)
    waterfall = pd.read_csv(snakemake.input.waterfall)
    sensitivity = pd.read_csv(snakemake.input.sensitivity)
    comparison = pd.read_csv(snakemake.input.comparison)
    placement = pd.read_csv(snakemake.input.placement)
    exclusion_stats = {
        Path(p).stem.replace("exclusions_", ""): json.loads(Path(p).read_text())
        for p in snakemake.input.exclusion_stats
    }

    ref_t = cfg["reference_turbine"]
    ref_scenario = cfg["reference_scenario"]
    rs = headline["region_stats"]
    bench = headline["benchmarks"]
    ad = headline["area_density"]
    pl = headline["placement"]
    resid = headline["residual"]
    breg = headline["bregilab"]
    serv = headline["servitude_costs"]
    fleet = headline["fleet_validation"]
    fr = headline["fragmentation"]

    # ------------------------------------------------------------------
    # macros.tex
    # ------------------------------------------------------------------
    m = []

    def macro(name, value):
        m.append(rf"\newcommand{{\{name}}}{{{value}}}")

    macro("refScenario", tex_escape(headline["reference_scenario"]))
    macro("refScenarioTitle", tex_escape(headline["reference_scenario_title"]))
    macro("refTurbine", tex_escape(headline["reference_turbine_label"]))
    macro("refDensity", num(headline["reference_density_mw_km2"], 2))

    # Region definitions.  Only the administrative Region is analysed; the model
    # node figures survive so the scope remark can quote them.
    macro("adminArea", num(rs["admin_area_km2"]))
    macro("modelArea", num(rs["model_area_km2"]))
    macro("modelCoverage", num(rs["model_coverage_pct"], 1))
    macro("areaOutsideModel", num(rs["walloon_area_outside_model_km2"]))
    macro("areaOutsideWallonia", num(rs["model_area_outside_wallonia_km2"]))

    # Area x density, the conventional figure.
    macro("AdminEligible", num(ad["eligible_area_km2"]))
    macro("AdminEligibleShare", num(ad["eligible_share_pct"], 2))
    macro("AdminPnom", num(ad["p_nom_max_mw"]))
    macro("AdminPnomGW", num(ad["p_nom_max_mw"] / 1000, 2))
    macro("AdminFlh", num(ad["flh_h"]))
    macro("AdminEnergy", num(ad["energy_twh"], 2))
    macro("AdminTurbines", num(ad["n_turbines"]))

    # Placement, the headline figure.
    macro("PlaceModel", tex_escape(pl["model"]))
    macro("PlaceInterfarm", num(pl["interfarm_distance_m"] / 1000, 0))
    macro("PlaceFarms", num(pl["n_farms"]))
    macro("PlacePerFarm", num(pl["turbines_per_farm"], 1))
    macro("FreePnom", num(pl["free_p_nom_max_mw"]))
    macro("FreePnomGW", num(pl["free_p_nom_max_mw"] / 1000, 1))
    macro("FreeTurbines", num(pl["free_n_turbines"]))
    macro("FreeDensity", num(pl["free_density_mw_km2"], 1))
    macro("FreeOrderSpread", num(pl["free_order_sensitivity_pct"], 0))
    macro("FarmShareOfFree", num(pl["farm_share_of_free_pct"], 0))
    for d, v in pl["by_interfarm"].items():
        tag = {"4000": "Four", "5000": "Five", "6000": "Six"}.get(d, d)
        macro(f"Ifd{tag}MW", num(v["p_nom_max_mw"]))
        macro(f"Ifd{tag}Farms", num(v["n_farms"]))
        macro(f"Ifd{tag}Turbines", num(v["n_turbines"]))
    ifd_mw = [v["p_nom_max_mw"] for v in pl["by_interfarm"].values()]
    macro("IfdLow", num(min(ifd_mw)))
    macro("IfdHigh", num(max(ifd_mw)))
    macro("PlaceSpacing", num(pl["min_distance_m"]))
    macro("PlaceTurbines", num(pl["n_turbines"]))
    macro("PlacePnom", num(pl["p_nom_max_mw"]))
    macro("PlacePnomGW", num(pl["p_nom_max_mw"] / 1000, 2))
    macro("PlaceDensity", num(pl["effective_density_mw_km2"], 2))
    macro("PlaceLand", num(100 * pl["land_per_turbine_km2"], 0))   # hectares
    macro("PlaceEnergy", num(pl["energy_twh"], 2))
    macro("PlaceVsDensity", num(abs(pl["vs_area_density_pct"]), 0))
    macro("PlaceRangeLow", num(headline["placement_range_mw"][0]))
    macro("PlaceRangeHigh", num(headline["placement_range_mw"][1]))

    # Residual allowance.
    macro("ResSurvival", num(100 * resid["central"]["survival"], 0))
    macro("ResCentral", num(resid["central"]["p_nom_max_mw"]))
    macro("ResCentralGW", num(resid["central"]["p_nom_max_mw"] / 1000, 1))
    macro("ResCentralEnergy", num(resid["central"]["energy_twh"], 2))
    macro("ResLow", num(resid["p_nom_max_range_mw"][0]))
    macro("ResHigh", num(resid["p_nom_max_range_mw"][1]))
    macro("ResOrnithology", num(100 * resid["components"]["ornithology"]["central"], 0))
    macro(
        "ResPartial", num(100 * resid["components"]["partial_constraints"]["central"], 0)
    )
    macro("CredibleLow", num(headline["credible_range_mw"][0]))
    macro("CredibleHigh", num(headline["credible_range_mw"][1]))
    macro("CredibleLowGW", num(headline["credible_range_mw"][0] / 1000, 1))
    macro("CredibleHighGW", num(headline["credible_range_mw"][1] / 1000, 1))
    macro("CredibleCentral", num(headline["credible_central_mw"]))
    dc = headline["density_check"]
    macro("DeDensity", num(dc["germany_kw_km2"]))
    macro("DeTurbines", num(dc["germany_turbines_per_1000km2"], 1))
    macro("WalDensityToday", num(dc["wallonia_today_kw_km2"]))
    macro("WalDensityCentral", num(dc["wallonia_central_kw_km2"]))
    macro("WalDensityHigh", num(dc["wallonia_high_kw_km2"]))
    macro("CentralVsDe", num(dc["central_vs_germany"], 2))
    macro("HighVsDe", num(dc["high_vs_germany"], 2))
    macro("TodayVsDe", num(dc["today_vs_germany"], 2))
    macro("CredibleCentralGW", num(headline["credible_central_mw"] / 1000, 1))

    # Calibration against the standing fleet.
    macro("FleetN", num(fleet["n_turbines"]))
    for name, key in [
        ("Nature", "nature"),
        ("Slope", "slope"),
        ("Aviation", "aviation"),
        ("Habitat", "habitat_setback"),
        ("Dwelling", "dwelling_setback"),
        ("Risk", "risk"),
        ("Infra", "infrastructure_setback"),
    ]:
        v = fleet["by_layer"].get(key)
        if v:
            macro(f"Fleet{name}Ratio", num(v["avoidance_ratio"], 2))
            macro(f"Fleet{name}Pct", num(v["pct"], 1))
    ratios = [
        v["avoidance_ratio"]
        for v in fleet["by_layer"].values()
        if v["avoidance_ratio"] is not None
    ]
    macro("FleetMaxRatio", num(max(ratios), 2))
    # LaTeX macro names cannot contain digits, so S1..S6 become words.
    DIGITS = {"1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
              "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine", "0": "Zero"}
    for sname, v in fleet["by_scenario"].items():
        tag = "".join(DIGITS.get(c, c) for c in sname.split("_")[0])
        macro(f"Fleet{tag}Pct", num(v["surviving_pct"], 0))
    macro("FleetRefPct", num(fleet["by_scenario"][ref_scenario]["surviving_pct"], 0))
    macro("FleetRefN", num(fleet["by_scenario"][ref_scenario]["surviving"]))
    fm = fleet.get("farms")
    if fm:
        macro("FleetFarms", num(fm["n_farms"]))
        macro("FleetPerFarm", num(fm["turbines_per_farm"], 1))
        macro("FleetFarmsFour", num(fm["n_farms_ge_4"]))
        macro("FleetLargestFarm", num(fm["largest_farm"]))
        macro("FleetFarmLink", num(fm["link_distance_m"] / 1000, 1))

    # Cost of the late-added constraint families.
    macro("ServBase", num(serv["base_area_km2"]))
    macro("ServCombined", num(serv["combined_area_km2"]))
    macro("ServCombinedRemoved", num(serv["combined_removed_km2"]))
    macro("ServCombinedPct", num(serv["combined_removed_pct"], 0))
    for key, suffix in FAMILY_MACRO.items():
        f = serv["families"].get(key)
        if f:
            macro(f"Serv{suffix}Removed", num(f["removed_km2"]))
            macro(f"Serv{suffix}Pct", num(f["removed_pct"], 1))

    b = headline["pypsa_eur_baseline"]
    macro("BaseEligible", num(b["eligible_area_km2"]))
    macro("BasePnom", num(b["p_nom_max_mw"]))
    macro("BasePnomGW", num(b["p_nom_max_mw"] / 1000, 1))

    macro("CapToday", num(bench["model_p_nom_max_mw"]))
    macro("CapTodayGW", num(bench["model_p_nom_max_mw"] / 1000, 1))
    macro("Installed", num(bench["installed_2024_mw"]))
    macro("TargetGWh", num(bench["target_2030_gwh"]))
    macro("TargetTWh", num(bench["target_2030_gwh"] / 1000, 1))
    macro("SpwNewGWh", num(bench["spw2022_new_gwh"]))
    macro("SpwNewTWh", num(bench["spw2022_new_gwh"] / 1000, 2))
    macro("SpwStrictArea", num(bench["spw2022_strict_ha"] / 100, 0))
    macro("SpwEnlargedArea", num(bench["spw2022_enlarged_ha"] / 100, 0))

    # BREGILAB reconciliation.
    macro("BregTotal", num(breg["total_mw"]))
    macro("BregTotalGW", num(breg["total_mw"] / 1000, 1))
    macro("BregCurrent", num(breg["current_mw"]))
    macro("BregAdditional", num(breg["additional_mw"]))
    macro("BregEnergy", num(breg["energy_twh"], 1))
    macro("BregFlh", num(breg["flh_h"]))
    macro("BregFlhGross", num(breg["flh_gross_h"]))
    macro("BregDensity", num(breg["implied_density_mw_km2"], 2))
    macro("BregArea", num(breg["implied_area_km2"]))
    macro("BregOursVOneTwelve", num(breg["ours_v112_array_mw"]))
    macro("BregOursVOneTwelveSpacing", num(breg["ours_v112_bregilab_spacing_mw"]))
    macro("BregOursArea", num(breg["our_v112_eligible_area_km2"]))
    macro("BregStepTurbine", num(breg["step_turbine_class"], 2))
    macro("BregStepSpacing", num(breg["step_spacing"], 2))
    macro("BregStepConstraints", num(breg["step_constraint_set"], 2))
    macro("BregRatio", num(breg["total_ratio"], 2))
    macro("BregVsCentral", num(breg["vs_central"], 1))
    macro("BregVsFarm", num(breg["vs_farm"], 1))
    macro("BregPerf", num(cfg["bregilab"]["performance_ratio"], 2))

    ex = exclusion_stats.get(ref_t, {})
    macro("HabitatSetback", num(ex.get("habitat_setback_m"), 0))
    macro("HabitatRule", tex_escape(str(ex.get("habitat_setback_rule", ""))))
    macro("DwellingSetback", num(ex.get("dwelling_setback_m"), 0))
    macro("RoadSetback", num(ex.get("road_setback_m"), 0))
    macro("HvSetback", num(ex.get("hv_line_setback_m"), 0))
    macro("TipHeight", num(ex.get("tip_height_m"), 0))
    macro("RotorDiameter", num(ex.get("rotor_diameter_m"), 0))
    exv = exclusion_stats.get("T136_V112", {})
    macro("HabitatSetbackVOneTwelve", num(exv.get("habitat_setback_m"), 0))

    # End-to-end validation: reproducing PyPSA-Eur's own constraint set with
    # PyPSA-Eur's own turbine should reproduce the full-load hours of the
    # profile PyPSA-Wal actually carries.
    val = summary[
        (summary["scenario"] == "S0_pypsa_eur")
        & (summary["region"] == REGION)
        & (summary["turbine"] == "T136_V112")
        & (summary["density_case"] == "pypsa_eur")
    ]
    if not val.empty:
        v = val.iloc[0]
        macro("ValFlh", num(v["flh_h"]))
        macro("ValArea", num(v["eligible_area_km2"]))
        macro("ValCf", num(100 * float(v["mean_capacity_factor"]), 1))
        ref = bench.get("model_profile_flh_2013")
        macro("ValRefFlh", num(ref))
        macro("ValDelta", num(100 * (float(v["flh_h"]) - ref) / ref, 1))

    ref_flh = summary[
        (summary["scenario"] == ref_scenario)
        & (summary["region"] == REGION)
        & (summary["turbine"] == "T136_V112")
        & (summary["density_case"] == cfg["reference_density"])
    ]
    if not ref_flh.empty:
        macro("VOneTwelveFlh", num(ref_flh.iloc[0]["flh_h"]))

    macro("CapRatio", num(bench["model_p_nom_max_mw"] / max(pl["p_nom_max_mw"], 1), 1))
    macro(
        "CapRatioCentral",
        num(bench["model_p_nom_max_mw"] / max(resid["central"]["p_nom_max_mw"], 1), 1),
    )
    macro("ZoningOnly", num(headline["zoning_only_km2"]))
    macro("SetbackCut", num(headline["setback_cut_pct"], 0))
    macro("SetbackRemoved", num(headline["largest_step"]["removed_km2"]))
    macro("AfterSetbackRemoved", num(headline["remaining_steps_removed_km2"]))
    macro("SFiveEligible", num(headline["before_servitudes"]["eligible_area_km2"]))
    macro("SFivePnom", num(headline["before_servitudes"]["p_nom_max_mw"]))

    ed = list(headline["energy_density_gwh_km2"].values())
    macro("EnergyDensityLow", num(min(ed), 1))
    macro("EnergyDensityHigh", num(max(ed), 1))

    macro("NPatches", num(fr["n_patches"]))
    macro("MedianPatch", num(100 * fr["median_patch_km2"], 0))  # hectares
    macro("LargestPatch", num(fr["largest_patch_km2"], 1))
    macro("Footprint", num(fr["footprint_km2"], 2))
    macro("DevOnePct", num(fr["share_ge_1_turbine_pct"], 0))
    macro("DevFourPct", num(fr["share_ge_4_turbines_pct"], 1))
    macro("DevOneKm", num(fr["area_in_patches_ge_1_turbine_km2"]))
    macro("DevFourKm", num(fr["area_in_patches_ge_4_turbines_km2"]))
    dens = headline["reference_density_mw_km2"]
    macro("DevOneMW", num(fr["area_in_patches_ge_1_turbine_km2"] * dens))
    macro("DevFourMW", num(fr["area_in_patches_ge_4_turbines_km2"] * dens))

    Path(snakemake.output.macros).write_text("\n".join(m) + "\n")

    # ------------------------------------------------------------------
    # Waterfall table
    # ------------------------------------------------------------------
    rows = [
        [
            tex_escape(r.scenario.replace("_", " ")),
            tex_escape(r.title),
            num(r.eligible_area_km2),
            num(r.share_of_region_pct, 2),
            num(r.removed_vs_previous_km2) if r.in_ladder else "n/a",
        ]
        for r in waterfall.itertuples()
    ]
    Path(snakemake.output.waterfall_tex).write_text(
        tabular(
            rows,
            [
                "scen.",
                "constraint set",
                r"area [\si{\square\kilo\metre}]",
                r"share [\%]",
                r"removed [\si{\square\kilo\metre}]",
            ],
            "lp{0.36\\linewidth}rrr",
        )
    )

    # ------------------------------------------------------------------
    # Sensitivity table
    # ------------------------------------------------------------------
    rows = []
    last = None
    for r in sensitivity.itertuples():
        if last is not None and r.turbine != last:
            rows.append(MIDRULE)
        rows.append(
            [
                tex_escape(r.turbine_label) if r.turbine != last else "",
                tex_escape(r.density_case.replace("_", " ")),
                num(r.capacity_density_mw_km2, 2),
                num(r.eligible_area_km2),
                num(r.p_nom_max_mw),
                num(r.flh_h),
                num(r.energy_twh, 1),
            ]
        )
        last = r.turbine
    Path(snakemake.output.sensitivity_tex).write_text(
        tabular(
            rows,
            [
                "turbine",
                "density",
                r"[\si{\mega\watt\per\square\kilo\metre}]",
                r"area [\si{\square\kilo\metre}]",
                r"$P$ [\si{\mega\watt}]",
                r"FLH [\si{\hour}]",
                r"$E$ [\si{\tera\watt\hour}]",
            ],
            "llrrrrr",
        )
    )

    # ------------------------------------------------------------------
    # Placement table
    # ------------------------------------------------------------------
    rows = []
    last = None
    for r in placement.itertuples():
        if last is not None and r.turbine != last:
            rows.append(MIDRULE)
        detail = (
            f"{r.interfarm_distance_m / 1000:.0f} km apart"
            if r.model == "farm"
            else tex_escape(r.order.replace("_", " ")) + " order"
        )
        rows.append(
            [
                tex_escape(r.turbine_label) if r.turbine != last else "",
                tex_escape(r.model),
                tex_escape(r.spacing_case),
                num(r.min_distance_m),
                detail,
                num(r.n_farms) if r.model == "farm" else "--",
                num(r.n_turbines),
                num(r.p_nom_max_mw),
            ]
        )
        last = r.turbine
    Path(snakemake.output.placement_tex).write_text(
        tabular(
            rows,
            [
                "turbine",
                "model",
                "spacing",
                r"$d$ [\si{\metre}]",
                "variant",
                "farms",
                "machines",
                r"$P$ [\si{\mega\watt}]",
            ],
            "lllrlrrr",
        )
    )

    # ------------------------------------------------------------------
    # Cost of the constraint families added last
    # ------------------------------------------------------------------
    rows = []
    for key, f in serv["families"].items():
        rows.append(
            [
                FAMILY_LABELS.get(key, tex_escape(key)),
                num(f["removed_km2"]),
                num(f["removed_pct"], 1),
                num(f["area_after_km2"]),
            ]
        )
    rows.append(MIDRULE)
    rows.append(
        [
            "all four together",
            num(serv["combined_removed_km2"]),
            num(serv["combined_removed_pct"], 1),
            num(serv["combined_area_km2"]),
        ]
    )
    Path(snakemake.output.servitudes_tex).write_text(
        tabular(
            rows,
            [
                "constraint family",
                r"removes [\si{\square\kilo\metre}]",
                r"[\%]",
                r"leaves [\si{\square\kilo\metre}]",
            ],
            "p{0.42\\linewidth}rrr",
        )
    )

    # ------------------------------------------------------------------
    # Fleet-calibration table
    # ------------------------------------------------------------------
    LAYER_LABELS = {
        "pds_ineligible": "plan de secteur, ineligible zoning",
        "habitat_setback": "setback from habitat zones",
        "dwelling_setback": "setback from scattered dwellings",
        "infrastructure_setback": "road, rail and HV-line setbacks",
        "nature": "Natura 2000, reserves, wetlands, caves",
        "landscape": "landscape perimeters (PIP / ADESA)",
        "risk": "flood, karst, landslide, water capture",
        "aviation": "aeronautical servitudes",
        "slope": r"slope $\geq 7\,\%$",
        "heritage": "classified sites and protection zones",
        "radar": "radar and radio astronomy",
    }
    rows = [
        [
            LAYER_LABELS.get(k, tex_escape(k)),
            num(v["land_pct"], 1),
            num(v["pct"], 1),
            num(v["avoidance_ratio"], 2),
        ]
        for k, v in sorted(
            fleet["by_layer"].items(), key=lambda kv: kv[1]["avoidance_ratio"] or 0
        )
    ]
    Path(snakemake.output.fleet_tex).write_text(
        tabular(
            rows,
            [
                "constraint layer",
                r"of the Region [\%]",
                r"of the fleet [\%]",
                "ratio",
            ],
            "p{0.40\linewidth}rrr",
        )
    )

    # ------------------------------------------------------------------
    # BREGILAB reconciliation table
    # ------------------------------------------------------------------
    rows = [
        [
            "this study, free allocation",
            f"{headline['reference_turbine_label']}, "
            f"{pl['min_distance_m']:.0f} m between machines",
            num(breg["ours_reference_mw"]),
            "",
        ],
        [
            r"$\times$ turbine class",
            "V112 instead: smaller setbacks, more eligible land",
            num(breg["ours_v112_array_mw"]),
            num(breg["step_turbine_class"], 2),
        ],
        [
            r"$\times$ spacing convention",
            r"5 D isotropic instead of $\sqrt{5\times7}\,D$",
            num(breg["ours_v112_bregilab_spacing_mw"]),
            num(breg["step_spacing"], 2),
        ],
        [
            r"$\times$ constraint set",
            "the residual: everything else",
            num(breg["total_mw"]),
            num(breg["step_constraint_set"], 2),
        ],
        MIDRULE,
        [
            "BREGILAB, Wallonia onshore, gross",
            tex_escape(cfg["bregilab"]["reference"]),
            num(breg["total_mw"]),
            num(breg["total_ratio"], 2),
        ],
        [
            "this study, farm allocation",
            "the same land under the framework's grouping rules",
            num(breg["ours_farm_mw"]),
            num(breg["ours_farm_mw"] / breg["total_mw"], 2),
        ],
    ]
    Path(snakemake.output.bregilab_tex).write_text(
        tabular(
            rows,
            ["step", "what changes", r"$P$ [\si{\mega\watt}]", "factor"],
            "p{0.24\\linewidth}p{0.40\\linewidth}rr",
        )
    )

    # ------------------------------------------------------------------
    # Comparison table
    # ------------------------------------------------------------------
    rows = [
        [
            tex_escape(str(r.source)),
            tex_escape(str(r.basis)),
            num(r.capacity_mw),
            num(r.energy_twh, 2),
        ]
        for r in comparison.itertuples()
    ]
    Path(snakemake.output.comparison_tex).write_text(
        tabular(
            rows,
            ["source", "basis", r"$P$ [\si{\mega\watt}]", r"$E$ [\si{\tera\watt\hour}]"],
            "p{0.32\\linewidth}p{0.34\\linewidth}rr",
        )
    )

    # ------------------------------------------------------------------
    # Full cross-product, for the annex
    # ------------------------------------------------------------------
    full = summary[summary["density_case"] == cfg["reference_density"]]
    rows = [
        [
            tex_escape(r.scenario.replace("_", " ")),
            tex_escape(r.turbine_label),
            num(r.eligible_area_km2),
            num(r.p_nom_max_mw),
            num(r.flh_h),
            num(r.energy_twh, 2),
        ]
        for r in full.itertuples()
    ]
    Path(snakemake.output.full_tex).write_text(
        tabular(
            rows,
            [
                "scenario",
                "turbine",
                r"area [\si{\square\kilo\metre}]",
                r"$P$ [\si{\mega\watt}]",
                r"FLH [\si{\hour}]",
                r"$E$ [\si{\tera\watt\hour}]",
            ],
            "llrrrr",
        )
    )

    # ------------------------------------------------------------------
    # Source-dataset provenance table
    # ------------------------------------------------------------------
    rows = []
    for meta_path in sorted(snakemake.input.source_meta):
        meta = json.loads(Path(meta_path).read_text())
        rows.append(
            [
                tex_escape(str(meta.get("title", ""))),
                tex_escape(f"{meta['service']}/{meta['layer']}"),
                num(meta.get("features_written")),
                tex_escape(str(meta.get("retrieved", ""))[:10]),
            ]
        )
    Path(snakemake.output.sources_tex).write_text(
        tabular(
            rows,
            ["dataset", "service / layer", "features", "retrieved"],
            "p{0.36\\linewidth}p{0.30\\linewidth}rl",
        )
    )

    logger.info("report inputs written to %s", out_dir)
