# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Invariants of the September 2026 cabinet batch.

Each test here pins something that was got wrong once while the batch was being
built, and whose failure mode is a run that completes and is quietly wrong
rather than one that stops. See docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md.
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

BATCH = [
    "scen_central",
    "scen_taxshift",
    "scen_taxshift_plus",
    "scen_biomethane_industrie",
    "scen_realiste_nets",
    "scen_realiste_nobnd30",
    "scen_retardnucleaire",
    *[f"scen_nuctip_{c}" for c in (9500, 7500, 6500, 6000, 5500, 4500)],
]
REALISTE = ["scen_realiste_nets", "scen_realiste_nobnd30"]
NUCTIP = [s for s in BATCH if s.startswith("scen_nuctip_")]

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
        "documented in docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md §1"
    )


@pytest.mark.parametrize("scenario", BATCH)
def test_scenario_inputs_exist(scenario, scenarios):
    """Every file a scenario block names must resolve."""
    assert scenario in scenarios, f"{scenario} missing from {SCENARIOS.name}"
    block = scenarios[scenario]
    sector = block.get("sector", {})

    for label, path in [
        ("times_file", sector.get("times_file")),
        ("rooftop_share", (sector.get("rooftop_share") or {}).get("file")),
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
    export's rooftop share or capture floor, which makes it a hybrid of itself
    and the central case. 2030 rooftop share is 0.651 central vs 0.347
    realiste, so the error is large and invisible.
    """
    sector = scenarios[scenario]["sector"]
    for key in ("rooftop_share", "industry_cc_floor"):
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
        elif scenario.startswith("scen_nuctip_"):
            expected = "scen_nofixnuc"
        assert stem.endswith(expected), (
            f"{scenario}: {key} points at {path}, which belongs to another "
            "scenario. Regenerate with extract_times_softlink_values.py."
        )


@pytest.mark.parametrize("scenario", [s for s in BATCH if (WAL / f"agg_p_nom_minmax_{s}.csv").exists()])
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
    """ICEDD's realistic 2030 caps are BELOW the central floors.

    The central scenario keeps a 2030 floor of 6500 MW solar-all / 3000 MW
    onwind (c337f36a). The realiste caps are 3310 / 2366 (ICEDD's 3474 / 2203
    with their swapped PV/wind increments corrected — see the batch doc §1.2).
    Dropping a row
    from the master table only stops it being *managed* — the seeded value
    stays in the cell — so the first generated realiste file carried
    min 6500 / max 3474: an empty corridor and an infeasible 2030, three files
    away from the error message. The floor must be BLANK here.
    """
    path = WAL / f"agg_p_nom_minmax_{scenario}.csv"
    assert _agg_cell(path, "BEWAL", carrier, "2030", "max") == cap
    floor = _agg_cell(path, "BEWAL", carrier, "2030", "min")
    assert floor == "", (
        f"{scenario}: BEWAL {carrier} 2030 floor is {floor!r} against a cap of "
        f"{cap} — min > max is an empty corridor. Re-run "
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
    path = ROOT / scenarios[scenario]["sector"]["rooftop_share"]["file"]
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


def test_realiste_pair_is_pypsa_identical(scenarios):
    """ICEDD: the two realiste scenarios differ only in their .vd."""
    a, b = (dict(scenarios[s]) for s in REALISTE)
    for block in (a, b):
        block["sector"] = {
            k: v for k, v in block["sector"].items() if k != "times_file"
        }
    # the per-scenario file names embed the scenario name; compare their shape
    def _strip(d):
        return yaml.safe_dump(d).replace("scen_realiste_nets", "X").replace(
            "scen_realiste_nobnd30", "X"
        )

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
