#!/usr/bin/env python3
"""Apply modeller decisions (2026-07-26) to input_parameters_for_models.csv.

Adds pypsa_wal_target / year_rule / status, decision notes, missing Walloon
lifetime / potential rows, and SMR / H2-import / discount / placeholder notes.

See common_parameters.md §8.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "config" / "input_parameters_for_models.csv"

# Display label → cost-file technology key (same as refresh script).
TECH_KEY = {
    "solar utility": "solar-utility",
    "solar rooftop": "solar-rooftop",
    "Nuclear (advanced)": "nuclear",
    "Eletricity distribution grid": "electricity distribution grid",
    "Battery storage (utility)": "battery storage",
    "e-methane": "methanation",
    "Uranium cost": "nuclear",
}

SKIP_COST_TECHS = {
    "OCGT hydrogen",
    "CCGT hydrogen",
    "Nuclear (SMR)",
    "carbon sequestration",
}

PARAM_COST = {
    "investment": "investment",
    "FOM": "FOM",
    "VOM": "VOM",
    "lifetime": "lifetime",
    "efficiency": "efficiency",
    "price": "fuel",
}

SMR_WARNING = (
    "WARNING (2026-07-26): Nuclear (SMR) = small modular reactor. "
    "In pypsa-eur / technology-data the cost-file key 'SMR' is steam methane reforming "
    "(gas→H2), NOT a nuclear SMR. Never write Nuclear (SMR) costs onto technology=SMR. "
    "pypsa-wal has no separate nuclear-SMR carrier today — status=none until one exists. "
    "Remove any custom_costs rows that set SMR investment/lifetime from this nuclear figure."
)

NOTE_PLACEHOLDER = (
    "Placeholder left empty on purpose (2026-07-26). To be further refined — "
    "technology not wired or costs not agreed yet."
)

NOTE_DISCOUNT = (
    "Fallback financial discount rate is the PyPSA default "
    "(config.default.yaml costs.fill_values 'discount rate'=0.07). "
    "Do not override it in config.walloon.yaml / config.times-pypsa.yaml. "
    "TIMES sector hurdles live in hurdle:<sector> rows → "
    "data/walloon/discount_rates.csv; SDR in config:costs.social_discountrate. "
    "status=none — not patched into walloon configs."
)

NOTE_H2_ROW = (
    "No hydrogen imports from the rest of the world (2026-07-26 decision). "
    "H2 exchange among simulated countries remains allowed. "
    "Do not enable sector.imports for extra-EU H2; status=none."
)

NOTE_WASTE_GEO = (
    "Present in the shared CSV but not applied in pypsa-wal (2026-07-26): "
    "BEWAL_potentials.py has no branch; industrial waste heat is endogenous and "
    "enhanced geothermal is an EU-wide node. status=none."
)

NOTE_CO2 = (
    "Authoritative CO₂ trajectory (2026-07-26): use these anchors. "
    "If the run has extra planning horizons (e.g. 2025, 2035, 2045), interpolate "
    "emission_ratio between the nearest anchors (year_rule=interp). "
    "Values are % of 1990; config expects a fraction (divide by 100)."
)


def blank_row(template: pd.Series) -> dict:
    return {c: pd.NA for c in template.index}


def append_lifetime_rows(df: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    """Append lifetime rows for 2030/2040/2050 if tech/parameter not already present."""
    out = df.copy()
    for spec in rows:
        tech = spec["technology_name_pypsa"]
        exists = (
            (out["technology_name_pypsa"] == tech) & (out["parameter"] == "lifetime")
        ).any()
        if exists:
            continue
        for year in (2030, 2040, 2050):
            r = blank_row(out.iloc[0])
            r.update(spec)
            r["parameter"] = "lifetime"
            r["year"] = year
            r["units"] = "years"
            r["pypsa_wal_target"] = f"cost:{TECH_KEY.get(tech, tech)}:lifetime"
            r["year_rule"] = "hold"
            r["status"] = spec.get("status", "active")
            out = pd.concat([out, pd.DataFrame([r])], ignore_index=True)
    return out


def cost_key(name: object) -> str | None:
    if pd.isna(name):
        return None
    s = str(name).strip()
    if s in SKIP_COST_TECHS:
        return None
    return TECH_KEY.get(s, s)


def main() -> None:
    df = pd.read_csv(CSV_PATH)

    for col in ("pypsa_wal_target", "year_rule", "status"):
        if col not in df.columns:
            df[col] = pd.NA

    # --- 1. CO2 trajectory ---
    co2 = (df["type"] == "CO2_constraint") & (df["parameter"] == "emission_ratio")
    df.loc[co2, "pypsa_wal_target"] = "config:budget_national"
    df.loc[co2, "year_rule"] = "interp"
    df.loc[co2, "status"] = "active"
    for idx in df.index[co2]:
        note = df.at[idx, "note_complementaire"]
        note_s = "" if pd.isna(note) else str(note).rstrip()
        if "year_rule=interp" not in note_s:
            df.at[idx, "note_complementaire"] = (
                f"{note_s + ' | ' if note_s else ''}{NOTE_CO2}"
            )

    # --- 2. Nuclear (SMR) ---
    smr = df["technology_name_pypsa"] == "Nuclear (SMR)"
    df.loc[smr, "pypsa_wal_target"] = "none:nuclear_smr_not_in_pypsa_wal"
    df.loc[smr, "year_rule"] = "hold"
    df.loc[smr, "status"] = "none"
    for idx in df.index[smr]:
        note = df.at[idx, "note_complementaire"]
        note_s = "" if pd.isna(note) else str(note).rstrip()
        if "steam methane reforming" not in note_s:
            df.at[idx, "note_complementaire"] = (
                f"{note_s + ' | ' if note_s else ''}{SMR_WARNING}"
            )

    # SMR CC is steam-methane with capture — keep as normal cost tech, add clarifying note
    smr_cc = df["technology_name_pypsa"] == "SMR CC"
    for idx in df.index[smr_cc]:
        note = df.at[idx, "note_complementaire"]
        note_s = "" if pd.isna(note) else str(note).rstrip()
        clar = (
            "SMR CC = steam methane reforming with carbon capture (NOT nuclear SMR)."
        )
        if "steam methane reforming" not in note_s:
            df.at[idx, "note_complementaire"] = (
                f"{note_s + ' | ' if note_s else ''}{clar}"
            )

    # --- 3. Potentials: CSV authoritative ---
    pot = df["type"] == "local_RES_potential"
    # waste heat / deep geothermal → none
    for label, reason in [
        ("waste heat", "none:waste_heat_endogenous"),
        ("deep geothermal energy potential", "none:deep_geothermal_eu_node"),
    ]:
        m = pot & (df["technology_name_pypsa"] == label)
        df.loc[m, "pypsa_wal_target"] = reason
        df.loc[m, "year_rule"] = "hold"
        df.loc[m, "status"] = "none"
        for idx in df.index[m]:
            note = df.at[idx, "note_complementaire"]
            note_s = "" if pd.isna(note) else str(note).rstrip()
            if "not applied in pypsa-wal" not in note_s:
                df.at[idx, "note_complementaire"] = (
                    f"{note_s + ' | ' if note_s else ''}{NOTE_WASTE_GEO}"
                )

    # Wallonia RES caps with values
    pot_targets = {
        "Max solar PV (Wallonia) - Agri": "potential:BEWAL:solar:p_nom_max",
        "Max onwind capacity allowed (Wallonia)": "potential:BEWAL:onwind:p_nom_max",
        "Max solar PV capacity allowed (Wallonia)": "potential:BEWAL:solar rooftop:p_nom_max",
        "Solid biomass (pellets, chips) potential (Wallonia)": "potential:BEWAL:solid biomass:p_nom",
        "Local biogas potential (Wallonia)": "potential:BEWAL:biogas:p_nom",
        "Import solid biomass (pellets) potential (oustide europe)": "potential:BEWAL:solid biomass import:e_nom",
    }
    for label, tgt in pot_targets.items():
        m = pot & (df["technology_name_pypsa"] == label)
        df.loc[m, "pypsa_wal_target"] = tgt
        df.loc[m, "year_rule"] = "hold"
        df.loc[m, "status"] = "active"
        for idx in df.index[m]:
            note = df.at[idx, "note_complementaire"]
            note_s = "" if pd.isna(note) else str(note).rstrip()
            add = (
                "CSV authoritative for potentials (2026-07-26); "
                "supersedes custom_potentials_corrige.csv when artefacts are regenerated."
            )
            if "CSV authoritative for potentials" not in note_s:
                df.at[idx, "note_complementaire"] = (
                    f"{note_s + ' | ' if note_s else ''}{add}"
                )

    # Empty BE/EU aggregate potential rows
    empty_pot = pot & df["value"].isna()
    df.loc[empty_pot & df["status"].isna(), "pypsa_wal_target"] = "none:empty_potential"
    df.loc[empty_pot & df["status"].isna(), "year_rule"] = "hold"
    df.loc[empty_pot & df["status"].isna(), "status"] = "none"

    # --- 4. Discount rate (PyPSA fill fallback; not a walloon override) ---
    disc = df["technology_name_pypsa"] == "Discount rate"
    df.loc[disc, "pypsa_wal_target"] = "config:costs.fill_values.discount rate"
    df.loc[disc, "year_rule"] = "hold"
    df.loc[disc, "status"] = "none"
    df.loc[disc, "value"] = 0.07
    for idx in df.index[disc]:
        df.at[idx, "note_complementaire"] = NOTE_DISCOUNT

    # --- 5. Lifetimes: mark existing; note Walloon diffs superseded ---
    walloon_lifetime_diffs = {
        # csv_tech: (walloon_value, csv keeps its own value)
        "OCGT": 30,
        "CCGT": 30,
        "onwind": 25,
        "solar rooftop": 25,
        "solar utility": 25,
        "Nuclear (advanced)": 60,
        "Battery storage (utility)": 10,
        "electrolysis": 40,
        "SMR CC": 20,
        "direct air capture": 30,
    }
    lt = df["parameter"] == "lifetime"
    for tech, wval in walloon_lifetime_diffs.items():
        m = lt & (df["technology_name_pypsa"] == tech)
        for idx in df.index[m]:
            note = df.at[idx, "note_complementaire"]
            note_s = "" if pd.isna(note) else str(note).rstrip()
            add = (
                f"CSV authoritative for lifetimes (2026-07-26). "
                f"Previous Walloon custom_costs override was {wval} years and is superseded."
            )
            if "CSV authoritative for lifetimes" not in note_s:
                df.at[idx, "note_complementaire"] = (
                    f"{note_s + ' | ' if note_s else ''}{add}"
                )

    # --- 6. H2 import from outside Europe ---
    h2 = df["technology_name_pypsa"].astype(str).str.contains(
        "hydrogen import price from outside Europe", case=False, na=False
    )
    df.loc[h2, "pypsa_wal_target"] = "none:no_row_h2_imports"
    df.loc[h2, "year_rule"] = "hold"
    df.loc[h2, "status"] = "none"
    for idx in df.index[h2]:
        df.at[idx, "note_complementaire"] = NOTE_H2_ROW

    # --- 7. Empty placeholders (H2 turbines, capture, sequestration monetary) ---
    placeholders = df["value"].isna() & df["units"].astype(str).str.contains(
        "EUR", na=False
    )
    # also empty sequestration potential
    placeholders = placeholders | (
        (df["technology_name_pypsa"] == "carbon sequestration") & df["value"].isna()
    )
    for idx in df.index[placeholders]:
        tech = df.at[idx, "technology_name_pypsa"]
        if tech == "Nuclear (SMR)":
            continue  # already handled
        df.at[idx, "year_rule"] = "hold"
        df.at[idx, "status"] = "pending"
        if pd.isna(df.at[idx, "pypsa_wal_target"]):
            df.at[idx, "pypsa_wal_target"] = "none:placeholder_to_refine"
        note = df.at[idx, "note_complementaire"]
        note_s = "" if pd.isna(note) else str(note).rstrip()
        if "further refined" not in note_s:
            df.at[idx, "note_complementaire"] = (
                f"{note_s + ' | ' if note_s else ''}{NOTE_PLACEHOLDER}"
            )

    # --- Cost / lifetime / efficiency / FOM / VOM / fuel rows with values ---
    for idx, row in df.iterrows():
        if pd.notna(row["status"]):
            continue
        param = row["parameter"]
        if pd.isna(param) or str(param) not in PARAM_COST:
            continue
        if pd.isna(row["value"]):
            continue
        key = cost_key(row["technology_name_pypsa"])
        if key is None:
            df.at[idx, "pypsa_wal_target"] = "none:skipped_tech"
            df.at[idx, "year_rule"] = "hold"
            df.at[idx, "status"] = "none"
            continue
        p = PARAM_COST[str(param)]
        # Uranium uses fuel parameter on nuclear
        df.at[idx, "pypsa_wal_target"] = f"cost:{key}:{p}"
        df.at[idx, "year_rule"] = "hold"
        df.at[idx, "status"] = "active"

    # Fuel price rows (coal/gas/oil) — TIMES origin, map to cost fuel
    fuel_map = {
        "coal price": "coal",
        "natural gas price": "gas",
        "Oil price": "oil",
    }
    for label, key in fuel_map.items():
        m = df["technology_name_pypsa"] == label
        df.loc[m, "pypsa_wal_target"] = f"cost:{key}:fuel"
        df.loc[m, "year_rule"] = "hold"
        df.loc[m, "status"] = "active"

    # NTC rows — use FR name / times name if pypsa name empty
    ntc = df["technology_type"].astype(str).str.contains(
        "interconnection", case=False, na=False
    )
    for idx in df.index[ntc]:
        fr = str(df.at[idx, "technology_name_fr"]) if pd.notna(df.at[idx, "technology_name_fr"]) else ""
        # Expect names like "NTC BE-FR" in fr or pypsa
        py = df.at[idx, "technology_name_pypsa"]
        label = str(py) if pd.notna(py) else fr
        # Extract pair if present
        import re

        m = re.search(r"([A-Z]{2,3})[–\-]([A-Z]{2,3}|offshore)", label, re.I)
        if not m:
            m = re.search(r"([A-Z]{2,3})[–\-]([A-Z]{2,3}|offshore)", fr, re.I)
        if m:
            a, b = m.group(1).upper(), m.group(2).upper()
            if b == "OFFSHORE":
                df.at[idx, "pypsa_wal_target"] = "none:no_be_offshore_hub"
                df.at[idx, "status"] = "none"
            else:
                df.at[idx, "pypsa_wal_target"] = f"ntc:{a}-{b}"
                df.at[idx, "status"] = "active"
        else:
            df.at[idx, "pypsa_wal_target"] = "none:ntc_unparsed"
            df.at[idx, "status"] = "pending"
        df.at[idx, "year_rule"] = "hold"

    # demand_driver → none
    dd = df["type"] == "demand_driver"
    df.loc[dd, "pypsa_wal_target"] = "none:times_activity_driver"
    df.loc[dd, "year_rule"] = "hold"
    df.loc[dd, "status"] = "none"

    # Remaining empty status → pending
    still = df["status"].isna()
    df.loc[still, "status"] = "pending"
    df.loc[still & df["year_rule"].isna(), "year_rule"] = "hold"
    df.loc[still & df["pypsa_wal_target"].isna(), "pypsa_wal_target"] = (
        "none:unclassified"
    )

    # --- Add missing Walloon lifetime overrides into CSV ---
    missing_lifetimes = [
        {
            "type": "technology",
            "technology_type": "Electricity production",
            "technology_name_fr": "Rétrrofit nucléaire",
            "technology_name_pypsa": "nuclear retrofit",
            "value": 10.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from data/walloon/custom_costs_*.csv so the "
                "Walloon lifetime override is not lost. CSV is authoritative going forward."
            ),
            "status": "active",
        },
        {
            "type": "technology",
            "technology_type": "Electricity production",
            "technology_name_fr": "Solaire (clé PyPSA 'solar')",
            "technology_name_pypsa": "solar",
            "value": 25.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from Walloon custom_costs (technology=solar lifetime=25). "
                "Distinct from solar utility / solar rooftop rows."
            ),
            "status": "active",
        },
        {
            "type": "technology",
            "technology_type": "Electricity production",
            "technology_name_fr": "PV toiture commercial",
            "technology_name_pypsa": "solar-rooftop commercial",
            "value": 25.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from Walloon custom_costs lifetime override."
            ),
            "status": "active",
        },
        {
            "type": "technology",
            "technology_type": "Electricity production",
            "technology_name_fr": "PV toiture résidentiel",
            "technology_name_pypsa": "solar-rooftop residential",
            "value": 25.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from Walloon custom_costs lifetime override."
            ),
            "status": "active",
        },
        {
            "type": "technology",
            "technology_type": "Electricity production",
            "technology_name_fr": "PV utility single-axis tracking",
            "technology_name_pypsa": "solar-utility single-axis tracking",
            "value": 25.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from Walloon custom_costs lifetime override."
            ),
            "status": "active",
        },
        {
            "type": "technology",
            "technology_type": "Biomethane production",
            "technology_name_fr": "Biogaz",
            "technology_name_pypsa": "biogas",
            "value": 25.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from Walloon custom_costs lifetime override."
            ),
            "status": "active",
        },
        {
            "type": "technology",
            "technology_type": "Biomethane production",
            "technology_name_fr": "Upgrading biogaz",
            "technology_name_pypsa": "biogas upgrading",
            "value": 30.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from Walloon custom_costs lifetime override."
            ),
            "status": "active",
        },
        {
            "type": "technology",
            "technology_type": "Synthetic fuel production",
            "technology_name_fr": "Méthanation (e-methane)",
            "technology_name_pypsa": "e-methane",
            "value": 25.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from Walloon custom_costs (technology=methanation lifetime=25)."
            ),
            "status": "active",
        },
        {
            "type": "technology",
            "technology_type": "Carbon Capture",
            "technology_name_fr": "Réservoir de stockage CO₂",
            "technology_name_pypsa": "CO2 storage tank",
            "value": 40.0,
            "source": "Walloon custom_costs (was missing from shared CSV)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": (
                "Added 2026-07-26 from Walloon custom_costs lifetime override."
            ),
            "status": "active",
        },
        # Nuclear (SMR) lifetime for documentation only — must NOT map to cost key SMR
        {
            "type": "technology",
            "technology_type": "Electricity production",
            "technology_name_fr": "Nucléaire (SMR)",
            "technology_name_pypsa": "Nuclear (SMR)",
            "value": 60.0,
            "source": "Walloon custom_costs (erroneously applied to steam-methane SMR)",
            "data_origin_choice": "Revue de littérature",
            "note_complementaire": SMR_WARNING
            + " Lifetime kept for documentation only; status=none.",
            "status": "none",
            # override target in append
        },
    ]

    # Special-case Nuclear (SMR) lifetime append
    smr_lt_spec = missing_lifetimes.pop()
    df = append_lifetime_rows(df, missing_lifetimes)
    # Nuclear SMR lifetime with none target
    if not (
        (df["technology_name_pypsa"] == "Nuclear (SMR)") & (df["parameter"] == "lifetime")
    ).any():
        for year in (2030, 2040, 2050):
            r = blank_row(df.iloc[0])
            r.update(smr_lt_spec)
            r["parameter"] = "lifetime"
            r["year"] = year
            r["units"] = "years"
            r["pypsa_wal_target"] = "none:nuclear_smr_not_in_pypsa_wal"
            r["year_rule"] = "hold"
            r["status"] = "none"
            df = pd.concat([df, pd.DataFrame([r])], ignore_index=True)

    # Add Walloon-only potentials missing from CSV
    extra_pots = [
        {
            "type": "local_RES_potential",
            "technology_type": "Electricity production",
            "technology_name_fr": "Minimum CCGT installé (Wallonie)",
            "technology_name_pypsa": "CCGT p_nom_min (Wallonia)",
            "parameter": "p_nom_min",
            "year": year,
            "value": 1740.0,
            "units": "MW",
            "source": "Walloon custom_potentials (was missing from shared CSV)",
            "note_complementaire": (
                "Added 2026-07-26 from custom_potentials_corrige.csv "
                "(BEWAL,CCGT,p_nom_min=1740). Validate with modellers; CSV authoritative going forward."
            ),
            "data_origin_choice": "Revue de littérature",
            "pypsa_wal_target": "potential:BEWAL:CCGT:p_nom_min",
            "year_rule": "hold",
            "status": "active",
        }
        for year in (2030, 2040, 2050)
    ]
    # nuclear p_nom_max near-zero in BEBRU etc. — document once as Wallonia/BE note
    for year in (2030, 2040, 2050):
        extra_pots.append(
            {
                "type": "local_RES_potential",
                "technology_type": "Electricity production",
                "technology_name_fr": "Capacité nucléaire max (nœuds BE, hors Wallonie étendue)",
                "technology_name_pypsa": "nuclear p_nom_max (BE nodes)",
                "parameter": "p_nom_max",
                "year": year,
                "value": 0.011,
                "units": "MW",
                "source": "Walloon custom_potentials (was missing from shared CSV)",
                "note_complementaire": (
                    "Added 2026-07-26 from custom_potentials_corrige.csv "
                    "(e.g. BEBRU nuclear p_nom_max≈0.011). Effectively blocks new nuclear on those "
                    "buses. Confirm intended geography before treating as final."
                ),
                "data_origin_choice": "Revue de littérature",
                "pypsa_wal_target": "potential:BE*:nuclear:p_nom_max",
                "year_rule": "hold",
                "status": "pending",
            }
        )

    for r in extra_pots:
        df = pd.concat([df, pd.DataFrame([r])], ignore_index=True)

    # Column order: keep originals then new
    base_cols = [
        "type",
        "technology_type",
        "technology_name_fr",
        "technology_name_pypsa",
        "technology_name_times",
        "parameter",
        "year",
        "year_currency",
        "value",
        "units",
        "source",
        "description_complementaire",
        "note_complementaire",
        "data_origin_choice",
        "pypsa_wal_value",
        "pypsa_wal_location",
        "pypsa_wal_target",
        "year_rule",
        "status",
    ]
    for c in base_cols:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[base_cols]

    df.to_csv(CSV_PATH, index=False)
    print(f"wrote {CSV_PATH} ({len(df)} rows)")
    print(df["status"].value_counts(dropna=False).to_string())
    print("year_rule:", df["year_rule"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
