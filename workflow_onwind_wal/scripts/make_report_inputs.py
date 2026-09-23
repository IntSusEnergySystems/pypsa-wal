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
    return s.replace(">=", r"$\geq$")


def signed(x, digits=0):
    """A signed number, with a typographic minus."""
    if x > 0:
        return "+" + num(x, digits)
    return r"$-$" + num(-x, digits) if x < 0 else num(0, digits)


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
    macro("PlaceLink", num(pl["link_m"] / 1000, 1))
    macro("PlaceMinTurbines", num(pl["min_turbines"]))
    macro("PlaceAzimuth", num(pl["min_free_azimuth_deg"]))
    macro("PlaceHorizonRadius", num(pl["horizon_radius_m"] / 1000, 0))
    macro("MotorwayExempt", num(pl["motorway_exemption_m"] / 1000, 0))
    macro("PlaceParks", num(pl["n_parks"]))
    macro("PlacePerPark", num(pl["turbines_per_park"], 1))
    macro("PlaceMedianPark", num(pl["median_park_size"], 0))
    macro("PlaceLargestPark", num(pl["largest_park"]))
    macro("PlaceRotorD", num(pl["min_distance_rotor_diameters"], 1))
    macro("PlaceRefused", num(pl["refused_by_horizon"]))
    macro("PlaceCheckSpacing", num(pl["check_min_spacing_m"]))
    macro("PlaceCheckArc", num(pl["check_worst_free_arc_deg"], 1))
    macro("NoHorizonPnom", num(pl["no_horizon_p_nom_max_mw"]))
    macro("NoHorizonParks", num(pl["no_horizon_n_parks"]))
    macro("NoHorizonTurbines", num(pl["no_horizon_n_turbines"]))
    macro("HorizonCostPct", num(pl["horizon_cost_pct"], 0))
    macro("ParksCostPct", num(pl["parks_cost_pct"], 0))
    macro("ParksOnePnom", num(pl["parks1_p_nom_max_mw"]))
    macro("ParksOneParks", num(pl["parks1_n_parks"]))
    macro("FreePnom", num(pl["free_p_nom_max_mw"]))
    macro("FreePnomGW", num(pl["free_p_nom_max_mw"] / 1000, 1))
    macro("FreeTurbines", num(pl["free_n_turbines"]))
    macro("FreeDensity", num(pl["free_density_mw_km2"], 1))
    macro("FreeOrderSpread", num(pl["free_order_sensitivity_pct"], 0))
    macro("ShareOfFree", num(pl["share_of_free_pct"], 0))
    macro("FreeOverRef", num(pl["free_p_nom_max_mw"] / pl["p_nom_max_mw"], 2))
    ID = {"4000": "Four", "6000": "Six"}
    for d, v in pl["by_interdistance"].items():
        tag = ID.get(d, d)
        macro(f"Id{tag}MW", num(v["p_nom_max_mw"]))
        macro(f"Id{tag}Parks", num(v["n_parks"]))
        macro(f"Id{tag}Turbines", num(v["n_turbines"]))
    SPC = {"observed": "Obs", "crosswind": "Cross", "isotropic": "Iso"}
    for k, v in pl["by_spacing"].items():
        tag = SPC.get(k, k)
        macro(f"Sp{tag}D", num(v["rotor_diameters"], 1))
        macro(f"Sp{tag}Free", num(v["free_mw"]))
        macro(f"Sp{tag}MW", num(v["p_nom_max_mw"]))
    macro("InterdistLow", num(headline["interdistance_policy_mw"][0]))
    macro("InterdistHigh", num(headline["interdistance_policy_mw"][1]))
    macro("PlaceSpacing", num(pl["min_distance_m"]))
    macro("PlaceTurbines", num(pl["n_turbines"]))
    macro("PlacePnom", num(pl["p_nom_max_mw"]))
    macro("PlacePnomGW", num(pl["p_nom_max_mw"] / 1000, 1))
    macro("PlaceDensity", num(pl["effective_density_mw_km2"], 2))
    macro("PlaceEnergy", num(pl["energy_twh"], 2))
    macro("PlaceVsDensity", num(abs(pl["vs_area_density_pct"]), 0))
    macro("PlaceRangeLow", num(headline["placement_range_mw"][0]))
    macro("PlaceRangeHigh", num(headline["placement_range_mw"][1]))
    TN = {"T136_V112": "VOneTwelve", "T185_NREL4": "NRELFour", "T208_NREL55": "NRELFive"}
    for t, v in pl["by_turbine"].items():
        macro(f"Place{TN.get(t, t)}", num(v["p_nom_max_mw"]))
        macro(f"Free{TN.get(t, t)}", num(v["free_mw"]))

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
    LAY = {"nature": "Nature", "slope": "Slope", "aviation": "Aviation",
           "habitat_setback": "Habitat", "dwelling_setback": "Dwelling", "risk": "Risk",
           "infrastructure_setback": "Infra", "pds_ineligible": "Zoning",
           "landscape": "Landscape", "landscape_pds": "LandscapePds",
           "landscape_adesa": "LandscapeAdesa", "heritage": "Heritage", "radar": "Radar"}
    for key, name in LAY.items():
        v = fleet["by_layer"].get(key)
        if v:
            macro(f"Fleet{name}Ratio", num(v["avoidance_ratio"], 2))
            macro(f"Fleet{name}Pct", num(v["pct"], 1))
            macro(f"Fleet{name}Cond", num(v["conditional_ratio"], 2))
            macro(f"Fleet{name}CondPct", num(v["conditional_fleet_pct"], 1))
            macro(f"Fleet{name}CondLand", num(v["conditional_land_pct"], 1))
    ref_keys = cfg["scenarios"][ref_scenario]["layers"]
    ratios = [fleet["by_layer"][k]["avoidance_ratio"] for k in ref_keys
              if fleet["by_layer"][k]["avoidance_ratio"] is not None]
    cond = [fleet["by_layer"][k]["conditional_ratio"] for k in ref_keys
            if fleet["by_layer"][k]["conditional_ratio"] is not None
            and k not in ("habitat_setback", "dwelling_setback")]
    macro("FleetMaxRatio", num(max(ratios), 2))
    macro("FleetMaxCond", num(max(cond), 2))
    DIGITS = {"1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five",
              "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine", "0": "Zero"}
    for sname, v in fleet["by_scenario"].items():
        tag = "".join(DIGITS.get(c, c) for c in sname.split("_")[0])
        macro(f"Fleet{tag}Pct", num(v["surviving_pct"], 0))
    macro("FleetRefPct", num(fleet["by_scenario"][ref_scenario]["surviving_pct"], 0))
    macro("FleetRefN", num(fleet["by_scenario"][ref_scenario]["surviving"]))
    z = fleet["zoning"]
    macro("FleetZoningCodt", num(z["pds_ineligible"], 0))
    macro("FleetZoningPsroads", num(z["pds_ineligible_psroads"], 0))
    macro("FleetZoningNocorridor", num(z["pds_ineligible_nocorridor"], 0))
    fm = fleet["farms"]
    macro("FleetFarms", num(fm["n_farms"]))
    macro("FleetPerFarm", num(fm["turbines_per_farm"], 1))
    macro("FleetFarmsFour", num(fm["n_farms_ge_4"]))
    macro("FleetLargestFarm", num(fm["largest_farm"]))
    macro("FleetFarmLink", num(fm["link_distance_m"] / 1000, 1))
    macro("FleetInBigFarms", num(fm["share_in_farms_ge_4_pct"], 0))
    P = {"p5": "PFive", "p10": "PTen", "p25": "PTwentyFive",
         "p50": "PFifty", "p75": "PSeventyFive", "p90": "PNinety"}
    for key, tag in [("machine_nn_m", "MachineNN"), ("farm_radius_m", "FarmRad"),
                     ("farm_edge_nn_m", "FarmEdge")]:
        for q, qt in P.items():
            macro(f"Fleet{tag}{qt}", num(fm[key][q]))
    macro("FleetEdgeBelowFour", num(fm["farms_edge_below_4km_pct"], 0))
    macro("FleetEdgeBelowSix", num(fm["farms_edge_below_6km_pct"], 0))
    macro("FleetMwFarms", num(fm["farms_along_motorway"]))
    macro("FleetNonMwEdgeBelowFour", num(fm["farms_not_along_motorway_edge_below_4km_pct"], 0))
    macro("FleetNearMotorway", num(fm["turbines_within_1km_of_motorway_pct"], 0))
    macro("FleetNearMotorwayWide", num(fm["turbines_within_1500m_of_motorway_pct"], 0))
    addr = fleet["addresses"]
    macro("FleetAddrN", num(addr["turbines_within_400m_of_an_address"]))
    macro("FleetAddrZae", num(addr["of_which_nearest_address_in_zae"]))
    macro("FleetAddrAgri", num(addr["of_which_in_agricultural_zone"]))
    oh = fleet.get("open_horizon")
    if oh:
        macro("HorizonSettlements", num(oh["n_settlements"]))
        macro("HorizonAffected", num(oh["n_with_a_turbine_within_radius"]))
        macro("HorizonAffectedPct", num(oh["share_affected_pct"], 0))
        macro("HorizonFailing", num(oh["n_failing"]))
        macro("HorizonFailingPct", num(oh["failing_pct_of_affected"], 1))
        macro("HorizonArcPOne", num(oh["largest_free_arc_deg"]["p1"]))
        macro("HorizonArcPFive", num(oh["largest_free_arc_deg"]["p5"]))
        macro("HorizonArcPFifty", num(oh["largest_free_arc_deg"]["p50"]))

    # Sensitivity cases.
    SENS = {"interdistance_4km": "IdFour", "interdistance_6km": "IdSix",
            "no_horizon": "NoHorizon", "parks_min1": "ParksOne",
            "no_corridor": "NoCorridor", "habitat_cdr2013": "HabitatOld",
            "no_adesa": "NoAdesa", "no_landscape": "NoLandscape",
            "slope_ge10": "SlopeTen", "slope_ge15": "SlopeFifteen",
            "no_aviation": "NoAviation", "pic_plan_de_secteur": "PicPds",
            "all_policy_relaxed": "Relaxed", "all_policy_tightened": "Tightened",
            "reference": "Reference"}
    for case, v in headline["sensitivity"].items():
        tag = SENS.get(case)
        if tag is None:
            continue
        macro(f"Sens{tag}MW", num(v["p_nom_max_mw"]))
        macro(f"Sens{tag}Pct", signed(v["delta_pct"], 0) if case != "reference" else "0")
        macro(f"Sens{tag}Area", num(v["eligible_area_km2"]))
        macro(f"Sens{tag}Free", num(v["free_mw"]))

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
    macro("BregPerf", num(cfg["bregilab"]["performance_ratio"], 2))
    emu = breg["emulation"]
    macro("BregEmuArea", num(emu["eligible_km2"]))
    macro("BregEmuMW", num(emu["with_fleet_mw"]))
    macro("BregEmuGW", num(emu["with_fleet_mw"] / 1000, 1))
    macro("BregEmuGrossMW", num(emu["gross_free_mw"]))
    macro("BregReportedShare", num(100 * emu["reported_share_of_emulation"], 0))
    macro("BregBridgeEndMW", num(breg["bridge"][-1]["p_nom_max_mw"]))
    macro("BregBridgeEndArea", num(breg["bridge"][-1]["eligible_km2"]))
    macro("BregVsFree", num(breg["vs_free"], 2))
    macro("BregVsReference", num(breg["vs_reference"], 1))
    macro("BregVsCentral", num(breg["vs_central"], 1))

    ex = exclusion_stats.get(ref_t, {})
    macro("HabitatSetback", num(ex.get("habitat_setback_m"), 0))
    macro("HabitatRule", tex_escape(str(ex.get("habitat_setback_rule", ""))))
    macro("DwellingSetback", num(ex.get("dwelling_setback_m"), 0))
    macro("RoadSetback", num(ex.get("road_setback_m"), 0))
    macro("RailSetback", num(ex.get("railway_setback_m"), 0))
    macro("HslSetback", num(ex.get("railway_high_speed_setback_m"), 0))
    macro("HslKm", num(ex.get("high_speed_track_km"), 0))
    macro("HvSetback", num(ex.get("hv_line_setback_m"), 0))
    macro("AddrPoints", num(ex.get("address_points")))
    macro("AddrExempt", num(ex.get("address_points_exempt_in_zae")))
    macro("PicMotorwayKm", num(ex.get("pic_motorway_km")))
    macro("PicDualKm", num(ex.get("pic_dual_carriageway_km")))
    macro("PdsRoadKm", num(ex.get("pds_road_km")))
    macro("KarstKept", num(ex.get("karst_polygons_kept")))
    macro("KarstTotal", num(ex.get("karst_polygons_total")))
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

    macro("CapRatio", num(bench["model_p_nom_max_mw"] / max(pl["p_nom_max_mw"], 1), 2))
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
    MODEL_LABEL = {
        "free": "free",
        "parks": "parks",
        "parks+horizon": "parks + horizon",
        "parks1+horizon": r"parks $\geq 1$ + horizon",
    }
    rows = []
    last = None
    for r in placement.itertuples():
        if last is not None and r.turbine != last:
            rows.append(MIDRULE)
        label = MODEL_LABEL.get(r.model, tex_escape(r.model.replace("+", " + ")))
        variant = tex_escape(str(r.variant).replace("_", " ")) if r.model == "free" else ""
        rows.append(
            [
                tex_escape(r.turbine_label) if r.turbine != last else "",
                label,
                tex_escape(r.spacing_case),
                num(r.min_distance_rotor_diameters, 1),
                variant,
                num(r.n_parks) if r.model != "free" else "--",
                num(r.n_turbines),
                num(r.p_nom_max_mw),
            ]
        )
        last = r.turbine
    Path(snakemake.output.placement_tex).write_text(
        tabular(
            rows,
            ["turbine", "model", "spacing", r"$d/D$", "order", "parks", "machines",
             r"$P$ [\si{\mega\watt}]"],
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
    LAYER_LABELS["landscape_pds"] = r"\quad of which plan-de-secteur PIP"
    LAYER_LABELS["landscape_adesa"] = r"\quad of which ADESA inventory"
    order = [k for k in cfg["scenarios"][ref_scenario]["layers"]]
    order.insert(order.index("landscape") + 1, "landscape_pds")
    order.insert(order.index("landscape_pds") + 1, "landscape_adesa")
    rows = []
    for k in order:
        v = fleet["by_layer"][k]
        size_dep = k in ("habitat_setback", "dwelling_setback")
        rows.append(
            [
                LAYER_LABELS.get(k, tex_escape(k)),
                num(v["land_pct"], 1),
                num(v["pct"], 1),
                num(v["avoidance_ratio"], 2),
                "--" if size_dep else num(v["conditional_land_pct"], 1),
                "--" if size_dep else num(v["conditional_fleet_pct"], 1),
                "--" if size_dep else num(v["conditional_ratio"], 2),
            ]
        )
    Path(snakemake.output.fleet_tex).write_text(
        tabular(
            rows,
            [
                "constraint layer",
                r"Region [\%]",
                r"fleet [\%]",
                "ratio",
                r"land$^*$ [\%]",
                r"fleet$^*$ [\%]",
                r"ratio$^*$",
            ],
            r"p{0.34\linewidth}rrrrrr",
        )
    )

    # ------------------------------------------------------------------
    # BREGILAB bridge table
    # ------------------------------------------------------------------
    rows = [[r"\multicolumn{3}{l}{\emph{V112, 3.3 MW, 560 m apart, free allocation}}"]]
    for i, st in enumerate(breg["bridge"]):
        rows.append([tex_escape(st["step"]), num(st["eligible_km2"]), num(st["p_nom_max_mw"])])
    rows.append(MIDRULE)
    rows.append([r"\multicolumn{3}{l}{\emph{reference machine, this study's rules}}"])
    rows.append([f"{tex_escape(headline['reference_turbine_label'])}, "
                 f"{pl['min_distance_rotor_diameters']:.0f} D, free allocation",
                 num(ad["eligible_area_km2"]), num(breg["ours_free_mw"])])
    rows.append([f"+ parks of {pl['min_turbines']} or more",
                 "", num(breg["ours_parks_mw"])])
    rows.append([f"+ open horizon, {pl['min_free_azimuth_deg']:.0f}° within "
                 f"{pl['horizon_radius_m'] / 1000:.0f} km \\textbf{{(gross reference)}}",
                 "", num(breg["ours_reference_mw"])])
    rows.append([r"$\times$ residual allowance (central estimate)", "",
                 num(resid["central"]["p_nom_max_mw"])])
    rows.append(MIDRULE)
    rows.append(["BREGILAB, as published (Table 22)", "", num(breg["total_mw"])])
    Path(snakemake.output.bregilab_tex).write_text(
        tabular(
            rows,
            ["step", r"area [\si{\square\kilo\metre}]", r"$P$ [\si{\mega\watt}]"],
            r"p{0.66\linewidth}rr",
        )
    )

    # ------------------------------------------------------------------
    # Sensitivity cases table
    # ------------------------------------------------------------------
    GROUP = {"reference": "", "policy": "policy", "judgement": "judgement",
             "misreading": "misreading", "combined": "combined"}
    rows, last = [], None
    for case, v in headline["sensitivity"].items():
        if last is not None and v["group"] != last:
            rows.append(MIDRULE)
        rows.append(
            [
                tex_escape(v["label"]),
                GROUP.get(v["group"], v["group"]),
                num(v["eligible_area_km2"]),
                num(v["p_nom_max_mw"]),
                "--" if case == "reference" else signed(v["delta_pct"], 0) + r"\,\%",
            ]
        )
        last = v["group"]
    Path(snakemake.output.sensitivity_cases_tex).write_text(
        tabular(
            rows,
            ["change from the reference", "kind", r"area [\si{\square\kilo\metre}]",
             r"$P$ [\si{\mega\watt}]", r"$\Delta$"],
            r"p{0.50\linewidth}lrrr",
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
