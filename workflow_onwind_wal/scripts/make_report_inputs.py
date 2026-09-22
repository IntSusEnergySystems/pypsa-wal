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


def tabular(rows, header, align, caption=None, label=None, note=None):
    out = []
    out.append(r"\begin{tabular}{" + align + "}")
    out.append(r"\toprule")
    out.append(" & ".join(header) + r" \\")
    out.append(r"\midrule")
    for r in rows:
        if r == MIDRULE:            # a bare separator, not a data row
            out.append(r"\midrule")
            continue
        out.append(" & ".join(r) + r" \\")
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out)


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
    exclusion_stats = {
        Path(p).stem.replace("exclusions_", ""): json.loads(Path(p).read_text())
        for p in snakemake.input.exclusion_stats
    }

    ref_t = cfg["reference_turbine"]
    ref_scenario = cfg["reference_scenario"]
    rs = headline["region_stats"]
    bench = headline["benchmarks"]

    # ------------------------------------------------------------------
    # macros.tex
    # ------------------------------------------------------------------
    m = []

    def macro(name, value):
        m.append(rf"\newcommand{{\{name}}}{{{value}}}")

    macro("refScenario", tex_escape(headline["reference_scenario"]))
    macro("refTurbine", tex_escape(headline["reference_turbine_label"]))
    macro("refDensity", num(headline["reference_density_mw_km2"], 2))
    macro("adminArea", num(rs["admin_area_km2"]))
    macro("modelArea", num(rs["model_area_km2"]))
    macro("modelCoverage", num(rs["model_coverage_pct"], 1))
    macro("areaOutsideModel", num(rs["walloon_area_outside_model_km2"]))

    for region in ("admin", "model"):
        h = headline[region]
        pre = region.capitalize()
        macro(f"{pre}Eligible", num(h["eligible_area_km2"]))
        macro(f"{pre}EligibleShare", num(h["eligible_share_pct"], 2))
        macro(f"{pre}Pnom", num(h["p_nom_max_mw"]))
        macro(f"{pre}PnomGW", num(h["p_nom_max_mw"] / 1000, 2))
        macro(f"{pre}Flh", num(h["flh_h"]))
        macro(f"{pre}Energy", num(h["energy_twh"], 2))
        macro(f"{pre}Turbines", num(h["n_turbines"]))

    b = headline["pypsa_eur_baseline"]
    macro("BaseAdminEligible", num(b["admin_eligible_area_km2"]))
    macro("BaseAdminPnom", num(b["admin_p_nom_max_mw"]))
    macro("BaseModelEligible", num(b["model_eligible_area_km2"]))
    macro("BaseModelPnom", num(b["model_p_nom_max_mw"]))
    macro("BaseModelPnomGW", num(b["model_p_nom_max_mw"] / 1000, 1))

    macro("ModelRangeLow", num(headline["model_range_mw"][0]))
    macro("ModelRangeHigh", num(headline["model_range_mw"][1]))
    macro("AdminRangeLow", num(headline["admin_range_mw"][0]))
    macro("AdminRangeHigh", num(headline["admin_range_mw"][1]))

    macro("CapToday", num(bench["model_p_nom_max_mw"]))
    macro("CapTodayGW", num(bench["model_p_nom_max_mw"] / 1000, 1))
    macro("Installed", num(bench["installed_2024_mw"]))
    macro("TargetGWh", num(bench["target_2030_gwh"]))
    macro("SpwNewGWh", num(bench["spw2022_new_gwh"]))
    macro("SpwStrictArea", num(bench["spw2022_strict_ha"] / 100, 0))
    macro("SpwEnlargedArea", num(bench["spw2022_enlarged_ha"] / 100, 0))

    ex = exclusion_stats.get(ref_t, {})
    macro("HabitatSetback", num(ex.get("habitat_setback_m"), 0))
    macro("HabitatRule", tex_escape(str(ex.get("habitat_setback_rule", ""))))
    macro("DwellingSetback", num(ex.get("dwelling_setback_m"), 0))
    macro("RoadSetback", num(ex.get("road_setback_m"), 0))
    macro("HvSetback", num(ex.get("hv_line_setback_m"), 0))
    macro("TipHeight", num(ex.get("tip_height_m"), 0))
    macro("RotorDiameter", num(ex.get("rotor_diameter_m"), 0))

    # End-to-end validation: reproducing PyPSA-Eur's own constraint set with
    # PyPSA-Eur's own turbine on the model's own region should reproduce the
    # full-load hours of the profile the model actually carries.
    val = summary[
        (summary["scenario"] == "S0_pypsa_eur")
        & (summary["region"] == "model")
        & (summary["turbine"] == "T136_V112")
        & (summary["density_case"] == "pypsa_eur")
    ]
    if not val.empty:
        v = val.iloc[0]
        macro("ValFlh", num(v["flh_h"]))
        macro("ValArea", num(v["eligible_area_km2"]))
        macro("ValPnom", num(v["p_nom_max_mw"]))
        macro("ValCf", num(100 * float(v["mean_capacity_factor"]), 1))
        ref = bench.get("model_profile_flh_2013")
        macro("ValRefFlh", num(ref))
        macro("ValDelta", num(100 * (float(v["flh_h"]) - ref) / ref, 1))

    ref_flh = summary[
        (summary["scenario"] == ref_scenario)
        & (summary["region"] == "admin")
        & (summary["turbine"] == "T136_V112")
        & (summary["density_case"] == cfg["reference_density"])
    ]
    if not ref_flh.empty:
        macro("VOneTwelveFlh", num(ref_flh.iloc[0]["flh_h"]))

    # Ratio of the model cap today to what this study finds.
    ratio = bench["model_p_nom_max_mw"] / max(headline["model"]["p_nom_max_mw"], 1)
    macro("CapOverstatement", num(ratio, 1))
    macro("ZoningOnly", num(headline["zoning_only_km2"]))
    macro("SetbackCut", num(headline["setback_cut_pct"], 0))
    macro("SetbackRemoved", num(headline["largest_step"]["removed_km2"]))
    # How much of the Walloon *resource* — not just the area — the model's
    # region boundary leaves out.
    lost = 100 * (
        1 - headline["model"]["eligible_area_km2"] / headline["admin"]["eligible_area_km2"]
    )
    macro("ResourceLostPct", num(lost, 1))
    macro("AfterSetbackRemoved", num(headline["remaining_steps_removed_km2"]))
    ed = list(headline["energy_density_gwh_km2"].values())
    macro("EnergyDensityLow", num(min(ed), 1))
    macro("EnergyDensityHigh", num(max(ed), 1))
    dv = headline["developable"]
    fr = headline["fragmentation"]
    macro("DevAllMW", num(dv["all_mw"]))
    macro("DevOneKm", num(dv["ge1_km2"]))
    macro("DevOneMW", num(dv["ge1_mw"]))
    macro("DevOnePct", num(fr["share_ge_1_turbine_pct"], 0))
    macro("DevFourKm", num(dv["ge4_km2"]))
    macro("DevFourMW", num(dv["ge4_mw"]))
    macro("DevFourPct", num(fr["share_ge_4_turbines_pct"], 1))
    macro("NPatches", num(fr["n_patches"]))
    macro("MedianPatch", num(100 * fr["median_patch_km2"], 0))  # hectares
    macro("LargestPatch", num(fr["largest_patch_km2"], 1))
    macro("Footprint", num(fr["footprint_km2"], 2))

    Path(snakemake.output.macros).write_text("\n".join(m) + "\n")

    # ------------------------------------------------------------------
    # Waterfall table
    # ------------------------------------------------------------------
    rows = []
    for region, label in [("admin", "Wallonia"), ("model", "BEWAL node")]:
        sub = waterfall[waterfall["region"] == region]
        for i, r in enumerate(sub.itertuples()):
            rows.append(
                [
                    tex_escape(label) if i == 0 else "",
                    tex_escape(r.scenario.replace("_", " ")),
                    tex_escape(r.title),
                    num(r.eligible_area_km2),
                    num(r.share_of_region_pct, 2),
                    num(r.removed_vs_previous_km2) if r.in_ladder else "n/a",
                ]
            )
        if region == "admin":
            rows.append(MIDRULE)
    Path(snakemake.output.waterfall_tex).write_text(
        tabular(
            rows,
            [
                "region",
                "scen.",
                "constraint set",
                r"area [\si{\square\kilo\metre}]",
                r"share [\%]",
                r"removed [\si{\square\kilo\metre}]",
            ],
            "llp{0.30\\linewidth}rrr",
        )
    )

    # ------------------------------------------------------------------
    # Sensitivity table
    # ------------------------------------------------------------------
    rows = []
    for region, label in [("admin", "Wallonia"), ("model", "BEWAL node")]:
        sub = sensitivity[sensitivity["region"] == region]
        first = True
        for r in sub.itertuples():
            rows.append(
                [
                    tex_escape(label) if first else "",
                    tex_escape(r.turbine_label),
                    tex_escape(r.density_case.replace("_", " ")),
                    num(r.capacity_density_mw_km2, 2),
                    num(r.eligible_area_km2),
                    num(r.p_nom_max_mw),
                    num(r.flh_h),
                    num(r.energy_twh, 2),
                ]
            )
            first = False
        if region == "admin":
            rows.append(MIDRULE)
    Path(snakemake.output.sensitivity_tex).write_text(
        tabular(
            rows,
            [
                "region",
                "turbine",
                "density case",
                r"[\si{\mega\watt\per\square\kilo\metre}]",
                r"area [\si{\square\kilo\metre}]",
                r"$p_{\mathrm{nom,max}}$ [\si{\mega\watt}]",
                r"FLH [\si{\hour}]",
                r"$E$ [\si{\tera\watt\hour}]",
            ],
            "lllrrrrr",
        )
    )

    # ------------------------------------------------------------------
    # Comparison table
    # ------------------------------------------------------------------
    rows = [
        [
            tex_escape(str(r.source)),
            tex_escape(str(r.basis)),
            tex_escape(str(r.region)),
            num(r.capacity_mw),
            num(r.energy_twh, 2),
        ]
        for r in comparison.itertuples()
    ]
    Path(snakemake.output.comparison_tex).write_text(
        tabular(
            rows,
            [
                "source",
                "basis",
                "region",
                r"$P$ [\si{\mega\watt}]",
                r"$E$ [\si{\tera\watt\hour}]",
            ],
            "p{0.27\\linewidth}p{0.24\\linewidth}p{0.16\\linewidth}rr",
        )
    )

    # ------------------------------------------------------------------
    # Full cross-product, for the annex
    # ------------------------------------------------------------------
    full = summary[summary["density_case"] == cfg["reference_density"]]
    rows = [
        [
            tex_escape(r.region),
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
                "region",
                "scenario",
                "turbine",
                r"area [\si{\square\kilo\metre}]",
                r"$P$ [\si{\mega\watt}]",
                r"FLH [\si{\hour}]",
                r"$E$ [\si{\tera\watt\hour}]",
            ],
            "lllrrrr",
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
