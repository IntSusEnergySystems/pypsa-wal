# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Invariants of the cabinet batches (September, 30 September and October 2026).

Each test here pins something that was got wrong once while a batch was being
built, and whose failure mode is a run that completes and is quietly wrong
rather than one that stops. See docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md
docs/logs/2026-09-30_cabinet_batch_20260930_2010_1h.md and
docs/logs/2026-10-04_cabinet_batch_20261002_2010_1h.md.
"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "config.walloon.yaml"
SCENARIOS = ROOT / "config" / "scenarios.walloon.yaml"
WAL = ROOT / "data" / "walloon"
CENTRAL_AGG = WAL / "agg_p_nom_minmax_demande_haute.csv"

# The batch in run.name: ICEDD's times_20261002_* exports, central first;
# scen_realiste stays on its 30 Sep export (not re-exported on 2 Oct).
BATCH = [
    "scen_central",
    "scen_noccsccgt",
    "scen_noccsccgt_route",
    "scen_retardnucleaire",
    "scen_biomethane_industrie",
    "scen_realiste",
]
# The .vd each batch scenario must read. A block left on an older export runs
# without complaint and is a different scenario.
BATCH_VD = {
    "scen_central": "scen_central_v01_261002_0210.vd",
    "scen_noccsccgt": "scen_sensibilite_central_noccsccgt_261002_0210.vd",
    "scen_noccsccgt_route": "scen_sensibilite_central_noccsccgt_261002_0210.vd",
    "scen_retardnucleaire": "scen_sensibilite_retardnucleaire_261002_0210.vd",
    "scen_biomethane_industrie": "scen_sensibilite_biomethane_industrie_v01_261002_0210.vd",
    "scen_realiste": "scen_sensibilite_realiste_260929_3009.vd",
}
# September-only scenarios: their blocks and generated files stay in the tree
# for reproducibility, so the file-level invariants below still apply to them.
SEPTEMBER = [
    "scen_taxshift",
    "scen_taxshift_plus",
    "scen_realiste_nets",
    "scen_realiste_nobnd30",
    *[f"scen_nuctip_{c}" for c in (9500, 7500, 6500, 6000, 5500, 4500)],
]
REALISTE = ["scen_realiste_nets", "scen_realiste_nobnd30", "scen_realiste"]
NUCTIP = [s for s in SEPTEMBER if s.startswith("scen_nuctip_")]

# TIMES `Transfo_Imp` is a binding bound, identical in all eight exports.
IMPORT_CAP = {2030: 2.94, 2040: 6.47, 2050: 10.0}


@pytest.fixture(scope="module")
def scenarios() -> dict:
    return yaml.safe_load(SCENARIOS.read_text()) or {}


@pytest.fixture(scope="module")
def run_names() -> list[str]:
    names = (yaml.safe_load(CONFIG.read_text()).get("run") or {}).get("name") or []
    return [names] if isinstance(names, str) else list(names)


def test_run_name_is_the_batch(run_names):
    """cluster/config.sh derives its scenario list from run.name.

    A name here that is not a scenario key fails at parse time; a scenario
    missing from here is silently not run, and the batch looks complete.
    """
    assert run_names == BATCH, (
        "run.name in config/config.walloon.yaml has drifted from the batch "
        "documented in docs/logs/2026-10-04_cabinet_batch_20261002_2010_1h.md §1"
    )


@pytest.mark.parametrize("scenario", BATCH)
def test_batch_reads_its_export(scenario, scenarios):
    times_file = scenarios[scenario]["sector"]["times_file"]
    assert Path(times_file).name == BATCH_VD[scenario], (
        f"{scenario} reads {times_file}, not {BATCH_VD[scenario]}"
    )


@pytest.mark.parametrize("scenario", BATCH)
def test_scenario_inputs_exist(scenario, scenarios):
    """Every file a scenario block names must resolve."""
    assert scenario in scenarios, f"{scenario} missing from {SCENARIOS.name}"
    block = scenarios[scenario]
    sector = block.get("sector", {})

    for label, path in [
        ("times_file", sector.get("times_file")),
        ("rooftop_floor", (sector.get("rooftop_floor") or {}).get("file")),
        ("industry_cc_floor", (sector.get("industry_cc_floor") or {}).get("file")),
        ("agg_p_nom_limits", ((block.get("solving") or {}).get("agg_p_nom_limits") or {}).get("file")),
        ("custom_cost_fn", (block.get("costs") or {}).get("custom_cost_fn")),
        ("walloon_potentials", (block.get("electricity") or {}).get("walloon_potentials")),
    ]:
        if path is None:
            continue
        assert (ROOT / path).exists(), f"{scenario}: {label} -> missing {path}"


@pytest.mark.parametrize("scenario", BATCH)
def test_self_sufficiency_is_the_times_bound(scenario, scenarios):
    """`Transfo_Imp` is identical in all eight exports, so this block is too.

    Repeated on purpose, not copied carelessly. If a future export moves the
    bound, this fails and the block has to be re-extracted with
    scripts/walloon_scripts/extract_times_softlink_values.py — not edited.
    """
    ss = scenarios[scenario].get("self_sufficiency") or {}
    assert ss.get("self_sufficiency_constraint") is True
    assert ss.get("nodes") == ["BEWAL"]
    assert {int(k): float(v) for k, v in ss["limit_twh"].items()} == IMPORT_CAP


@pytest.mark.parametrize("scenario", BATCH)
def test_softlink_files_are_scenario_specific(scenario, scenarios):
    """No scenario may point at another's TIMES-derived files.

    The failure this prevents: a sensitivity silently inheriting the central
    export's rooftop floor or capture floor, which makes it a hybrid of itself
    and the central case. 2040 rooftop capacity is 10.47 GW central vs 9.68 GW
    taxshift, so the error is large and invisible.
    """
    sector = scenarios[scenario]["sector"]
    for key in ("rooftop_floor", "industry_cc_floor"):
        path = (sector.get(key) or {}).get("file")
        if path is None:
            continue
        stem = Path(path).stem
        # Two groups share one .vd and therefore one pair of extracted files:
        # scen_central_2013 is scen_central on other weather, and all six
        # nuclear sweep points run on ICEDD's `nofixnuc` export.
        expected = scenario
        if scenario == "scen_central_2013":
            expected = "scen_central"
        elif scenario == "scen_noccsccgt_route":
            # the one-change twin runs on the noccsccgt export
            expected = "scen_noccsccgt"
        elif scenario.startswith("scen_nuctip_"):
            expected = "scen_nofixnuc"
        assert stem.endswith(expected), (
            f"{scenario}: {key} points at {path}, which belongs to another "
            "scenario. Regenerate with extract_times_softlink_values.py."
        )


@pytest.mark.parametrize("scenario", BATCH)
def test_softlink_files_come_from_the_scenario_export(scenario, scenarios):
    """The side files must have been extracted from the .vd the scenario reads.

    The 24 and 29 Sep central runs read `…260923_2_2309.vd` with floors still
    extracted from `…260911_1109.vd`: the right file names, the wrong export,
    and nothing failed. The extractor writes its source into line 1.
    """
    sector = scenarios[scenario]["sector"]
    vd = Path(sector["times_file"]).name
    for key in ("rooftop_floor", "industry_cc_floor"):
        path = ROOT / sector[key]["file"]
        first = path.read_text().splitlines()[0]
        assert first.startswith(f"# Extracted from {vd} "), (
            f"{scenario}: {path.name} says {first!r}, but the scenario reads {vd}. "
            "Re-run extract_times_softlink_values.py <vd> --scenario "
            f"{scenario} --write."
        )


@pytest.mark.parametrize("scenario", [s for s in BATCH + SEPTEMBER if (WAL / f"agg_p_nom_minmax_{s}.csv").exists()])
def test_flanders_is_never_touched(scenario):
    """The instruction is Wallonia only; BE parent rows move as arithmetic.

    Every BE row change in this batch is "BE = unchanged Flemish part + changed
    Walloon part". If a BEVLG row ever differs from the central file, a
    sensitivity has silently moved Flanders too.
    """
    central = [l for l in CENTRAL_AGG.read_text().splitlines() if l.startswith("BEVLG,")]
    variant = [
        l for l in (WAL / f"agg_p_nom_minmax_{scenario}.csv").read_text().splitlines()
        if l.startswith("BEVLG,")
    ]
    assert variant == central, f"{scenario} changes Flanders; the batch must not"


def _agg_cell(path: Path, location: str, carrier: str, year: str, bound: str) -> str:
    lines = path.read_text().splitlines()
    header = lines[0].split(",")
    years, bounds = lines[0].split(","), lines[1].split(",") if len(lines) > 1 else []
    # header row 1 is the year row; columns come in (min, max) pairs per year
    idx = None
    seen_min = False
    for i, y in enumerate(header[2:], start=2):
        if y == year:
            if not seen_min:
                seen_min = True
                if bound == "min":
                    idx = i
                    break
            else:
                if bound == "max":
                    idx = i
                    break
    assert idx is not None, f"no {year}/{bound} column in {path.name}"
    for line in lines:
        parts = line.split(",")
        if len(parts) > idx and parts[0] == location and parts[1] == carrier:
            return parts[idx]
    raise AssertionError(f"no {location},{carrier} row in {path.name}")


@pytest.mark.parametrize("scenario", [s for s in REALISTE if (WAL / f"agg_p_nom_minmax_{s}.csv").exists()])
@pytest.mark.parametrize("carrier,cap", [("solar-all", "3310"), ("onwind", "2366")])
def test_realiste_2030_corridor_is_not_empty(scenario, carrier, cap):
    """ICEDD's realistic 2030 caps are BELOW the old central floors.

    The realiste caps are 3310 / 2366 (ICEDD's 3474 / 2203 with their swapped
    PV/wind increments corrected — see the September batch doc §1.2). Dropping
    a row from the master table only stops it being *managed* — the seeded value
    stays in the cell — so the first generated realiste file carried
    min 6500 / max 3474: an empty corridor and an infeasible 2030, three files
    away from the error message. Since e27dccfd (16 Sep) the floor is set
    explicitly 5 % below the cap; what must hold is min < max.
    """
    path = WAL / f"agg_p_nom_minmax_{scenario}.csv"
    assert _agg_cell(path, "BEWAL", carrier, "2030", "max") == cap
    floor = _agg_cell(path, "BEWAL", carrier, "2030", "min")
    assert floor == "" or float(floor) < float(cap), (
        f"{scenario}: BEWAL {carrier} 2030 floor is {floor!r} against a cap of "
        f"{cap} — min >= max is an empty corridor. Re-run "
        "`build_common_parameters.py --write --all-scenarios`."
    )


@pytest.mark.parametrize("scenario", [s for s in REALISTE if (WAL / f"agg_p_nom_minmax_{s}.csv").exists()])
@pytest.mark.parametrize("carrier", ["solar-all", "onwind"])
def test_realiste_drops_the_belgian_2030_floor(scenario, carrier):
    """The national floor must go too, or the Walloon cap only moves the problem.

    `add_CCL_constraints` groups by (location, carrier) and BE is a parent row
    over BEVLG + BEWAL + BEBRU. With BEWAL capped at 3 310 MW of PV and the BE
    floor held at 16 500, the shortfall does not disappear — it is transferred
    to Flanders, which would have to reach ~13 000 MW against ~7 100 today. The
    scenario's premise is that the 2030 targets are NOT met, so the national
    floor cannot survive the regional cap.

    The 2025 base-year pin must SURVIVE: it is the calibration, not a target.
    """
    path = WAL / f"agg_p_nom_minmax_{scenario}.csv"
    assert _agg_cell(path, "BE", carrier, "2030", "min") == "", (
        f"{scenario}: the Belgian 2030 {carrier} floor is still set; it would "
        "push the whole Walloon shortfall onto Flanders"
    )
    assert _agg_cell(path, "BE", carrier, "2025", "min") != "", (
        "the 2025 base-year pin is a calibration and must not be dropped"
    )


@pytest.mark.parametrize("carrier,floor", [("solar-all", "16500"), ("onwind", "5000")])
def test_central_keeps_the_belgian_2030_floor(carrier, floor):
    """Dropping it is scoped to the realiste pair, not a change to the central case."""
    assert _agg_cell(CENTRAL_AGG, "BE", carrier, "2030", "min") == floor


@pytest.mark.parametrize("scenario", REALISTE)
def test_realiste_drops_the_2030_rooftop_pin(scenario, scenarios):
    """Neither PV convention describes the realiste 2030 fleet (§3.1)."""
    path = ROOT / scenarios[scenario]["sector"]["rooftop_floor"]["file"]
    if not path.exists():
        pytest.skip(f"{path.name} not generated yet")
    df = pd.read_csv(path, comment="#")
    assert 2030 not in set(df["year"]), (
        f"{path.name} has a 2030 row. Plant-only gives 0.347 and all-PV 0.903 "
        "that year — 56 pp apart; pinning either misdescribes the BEWAL solar "
        "fleet the constraint is applied to."
    )
    assert 2050 in set(df["year"]), "later horizons must keep the pin"


@pytest.mark.parametrize("scenario", [s for s in NUCTIP if (WAL / f"custom_costs_{s}.csv").exists()])
def test_nuctip_capex_matches_its_name(scenario):
    """The swept value must be the one the scenario is named after."""
    want = float(scenario.rsplit("_", 1)[1])
    costs = pd.read_csv(WAL / f"custom_costs_{scenario}.csv", comment="#")
    row = costs[(costs.technology == "nuclear") & (costs.parameter == "investment")]
    assert len(row) == 1, f"{scenario}: expected one nuclear/investment row"
    assert float(row["value"].iloc[0]) == want


@pytest.mark.parametrize("scenario", [s for s in NUCTIP if (WAL / f"agg_p_nom_minmax_{s}.csv").exists()])
def test_nuctip_capacity_is_actually_free(scenario):
    """A pinned capacity cannot reveal a tipping point.

    The floor must drop to the LTO while the ceiling stays at the central
    envelope — and the BE parent floor must drop with it, or the 2050 BE floor
    of 6000 MW re-imposes the Walloon build through the parent row and every
    sweep point returns the same capacity.
    """
    path = WAL / f"agg_p_nom_minmax_{scenario}.csv"
    assert _agg_cell(path, "BEWAL", "nuclear-all", "2050", "min") == "1000"
    assert _agg_cell(path, "BEWAL", "nuclear-all", "2050", "max") == "3000"
    assert _agg_cell(path, "BE", "nuclear-all", "2050", "min") == "4000"


@pytest.mark.parametrize("other", ["scen_realiste_nobnd30", "scen_realiste"])
def test_realiste_pair_is_pypsa_identical(scenarios, other):
    """ICEDD: the realiste scenarios differ only in their .vd.

    The single 30 Sep `scen_realiste` keeps the September PyPSA side too.
    """
    a, b = (dict(scenarios[s]) for s in ("scen_realiste_nets", other))
    # times_ev_fleet_skip_horizons follows the .vd too: it is set where an
    # export's car count cannot carry its own EV load (scen_realiste 2025).
    for block in (a, b):
        block["sector"] = {
            k: v
            for k, v in block["sector"].items()
            if k not in ("times_file", "times_ev_fleet_skip_horizons")
        }
    # the per-scenario file names embed the scenario name; compare their shape
    def _strip(d):
        return yaml.safe_dump(d).replace("scen_realiste_nets", "X").replace(other, "X")

    assert _strip(a) == _strip(b), (
        "the two realiste scenarios have diverged on the PyPSA side; ICEDD "
        "specified them as identical apart from the TIMES demands"
    )


def test_shared_resources_excludes_the_f_string_families():
    """Rules that bake the year into an input name need the exclusion.

    `resources(f"costs_{year}_processed.csv")` and
    `resources(f"wallon_demands_{baseyear}.csv")` carry no wildcard, so under
    `policy: base` they resolve to the SHARED path while their producer writes
    the per-run one — MissingInputException naming a file that exists on disk
    under a different prefix.
    """
    run = yaml.safe_load(CONFIG.read_text())["run"]
    shared = run.get("shared_resources") or {}
    assert shared.get("policy") == "base"
    for prefix in ("costs_", "wallon_demands_"):
        assert prefix in shared.get("exclude", []), (
            f"{prefix} must stay in run.shared_resources.exclude"
        )


def test_realiste_override_matches_the_september_one():
    """Same override rows as scen_realiste_nets, row for row."""
    a = pd.read_csv(ROOT / "config" / "scenarios" / "scen_realiste_nets.csv")
    b = pd.read_csv(ROOT / "config" / "scenarios" / "scen_realiste.csv")
    cols = ["pypsa_wal_target", "year", "value", "status"]
    assert a[cols].equals(b[cols])


def test_retardnucleaire_is_the_lto_only_pin():
    """New nuclear deferred beyond 2050: Wallonia holds the 1 GW Tihange 3 LTO.

    The definition of 3 Sep ("l'installation de nouvelles capacités nucléaires
    est désactivée, seule la prolongation du parc existant restant possible"),
    kept on 2026-09-30. NOTE: ICEDD's 30 Sep TIMES export does NOT follow it —
    it builds 0.5 GW large + 0.25 GW SMR in 2050 (1.795 GW with Tihange), and
    ICEDD's config/scen_RetardNucleaire.csv caps 2050 at 1 750 MW. The gap is
    recorded in the 30 Sep batch log §2.6 and raised with ICEDD. The BE parent
    row is the unchanged Flemish part plus the Walloon pin.
    """
    path = WAL / "agg_p_nom_minmax_scen_retardnucleaire.csv"
    for year in ("2045", "2050"):
        assert _agg_cell(path, "BEWAL", "nuclear-all", year, "min") == "1000"
        assert _agg_cell(path, "BEWAL", "nuclear-all", year, "max") == "1000"
        for bound in ("min", "max"):
            flemish = float(_agg_cell(CENTRAL_AGG, "BEVLG", "nuclear-all", year, bound))
            assert float(_agg_cell(path, "BE", "nuclear-all", year, bound)) == flemish + 1000


_KEYS = {
    "custom_costs": ["planning_horizon", "technology", "parameter"],
    "custom_potentials": ["bus", "technology", "parameter", "year"],
}


@pytest.mark.parametrize("kind", sorted(_KEYS))
@pytest.mark.parametrize(
    "scenario",
    sorted(p.stem for p in (ROOT / "config" / "scenarios").glob("*.csv")),
)
def test_scenario_copies_have_the_central_structure(scenario, kind):
    """A generated copy must carry every row of the central file.

    The patchers only rewrite values. Until 2026-09-30 a copy was seeded once
    and never rebuilt, so the September copies silently lacked the 29 Sep
    network-cost calibration rows (620 EUR/kW distribution, HVAC 450/408/372)
    and still had the 25-year electrolysis lifetime: those scenarios would
    have run on uncalibrated costs. `--write --all-scenarios` now re-seeds.
    """
    path = WAL / f"{kind}_{scenario}.csv"
    if not path.exists():
        pytest.skip(f"{path.name} not generated")
    keys = _KEYS[kind]
    central = pd.read_csv(WAL / f"{kind}.csv", comment=None)[keys].astype(str)
    copy = pd.read_csv(path, comment=None)[keys].astype(str)
    assert sorted(map(tuple, copy.values)) == sorted(map(tuple, central.values)), (
        f"{path.name} has drifted from {kind}.csv; re-run "
        "`build_common_parameters.py --write --all-scenarios`"
    )


# --------------------------------------------------------------------------- #
# The TIMES-priced CO2 disposal route (decided 2026-10-04; closed in the central
# from 2026-10-06, re-opened only in scen_noccsccgt_route)
# --------------------------------------------------------------------------- #
# Every row, the 5-year grid's 2035/2045 included: on 4 Oct scen_noccsccgt had the
# route closed in the four solved years but open in 2035/2045, because a 10-year
# `--write` left those rows as seeded from the central.
YEARS = (2025, 2030, 2035, 2040, 2045, 2050)
CLOSED = dict.fromkeys(YEARS, 0.0)
ROUTE_TIMES = {2025: 0.0, 2030: 0.0, 2035: 4000.0, 2040: 6000.0, 2045: 7000.0, 2050: 8000.0}
ROUTE_PRICE = {2030: 83.8, 2035: 83.8, 2040: 71.8, 2045: 67.8, 2050: 63.8}


def _route(path: Path) -> dict[str, dict[int, float]]:
    df = pd.read_csv(path)
    df = df[(df["bus"].fillna("BEWAL") == "BEWAL") & (df["technology"] == "co2 disposal service")]
    return {
        par: {int(y): float(v) for y, v in zip(g["year"], g["value"])}
        for par, g in df.groupby("parameter")
    }


def test_central_route_is_closed_in_every_horizon():
    """Closed 2025-2050 (decided 2026-10-06); the tariff rows stay, inert at volume 0."""
    r = _route(WAL / "custom_potentials.csv")
    assert r["e_nom_max"] == CLOSED
    for year, price in ROUTE_PRICE.items():
        assert r["vom_downstream"][year] + r["vom_onshore"][year] == pytest.approx(price), year


@pytest.mark.parametrize(
    "path",
    sorted(p.name for p in WAL.glob("custom_potentials_scen_*.csv")),
)
def test_route_closed_in_every_copy_but_the_twin(path):
    """A scenario copy re-seeded from the central must not keep an old route row."""
    r = _route(WAL / path)["e_nom_max"]
    want = ROUTE_TIMES if path == "custom_potentials_scen_noccsccgt_route.csv" else CLOSED
    assert r == want


def test_noccsccgt_closes_the_route_and_the_twin_opens_it():
    """noccsccgt_route - noccsccgt is the TIMES route alone, nothing else."""
    closed = _route(WAL / "custom_potentials_scen_noccsccgt.csv")
    assert closed["e_nom_max"] == CLOSED
    twin = _route(WAL / "custom_potentials_scen_noccsccgt_route.csv")
    assert twin["e_nom_max"] == ROUTE_TIMES
    assert {k: v for k, v in twin.items() if k != "e_nom_max"} == {
        k: v for k, v in _route(WAL / "custom_potentials.csv").items() if k != "e_nom_max"
    }
    a = pd.read_csv(WAL / "custom_potentials_scen_noccsccgt.csv")
    b = pd.read_csv(WAL / "custom_potentials_scen_noccsccgt_route.csv")
    route = a["technology"].eq("co2 disposal service") & a["parameter"].eq("e_nom_max")
    assert a[~route].equals(b[~route.values]), "the twin differs beyond the route"
    for kind in ("custom_costs", "agg_p_nom_minmax"):
        x = (WAL / f"{kind}_scen_noccsccgt.csv").read_text()
        y = (WAL / f"{kind}_scen_noccsccgt_route.csv").read_text()
        assert x == y, kind


@pytest.mark.parametrize("scenario", ["scen_retardnucleaire", "scen_realiste"])
def test_other_sensitivities_follow_the_central_route(scenario):
    assert _route(WAL / f"custom_potentials_{scenario}.csv") == _route(WAL / "custom_potentials.csv")


def test_bewal_2040_national_cap_is_the_times_tonnage():
    """BEWAL 2040 on TIMES-WAL's 6 826 kt (15 % of 45 600); everyone else 25 %."""
    budget = yaml.safe_load(CONFIG.read_text())["budget_national"]
    assert budget[2040]["BEWAL"] == 0.15
    assert {r: v for r, v in budget[2040].items() if r != "BEWAL"} == {
        r: 0.25 for r in budget[2040] if r != "BEWAL"
    }
    assert budget[2030]["BEWAL"] == 0.45 and budget[2050]["BEWAL"] == 0.05
