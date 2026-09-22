# Solve log — `scen_central_6h` (PV floor + levers A & B)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-22 12:26 → 13:25 (three launches, see §5) |
| Operator | Sylvain Quoilin (via Claude Code) |
| Run name (`run.name`) | `scen_central_6h` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + `config/config.test6h_central.yaml` |
| Code version | `7c304a90` + the working-tree edits listed in §9 |
| Outcome | success — 4/4 optimal, `review_run.py` 161 PASS · 31 INFO · 16 WARN · 0 FAIL |

## 2. Goal of the run

Validate, at 6 h and on the central case, the four changes described in
[`../co2-sequestration.md`](../co2-sequestration.md) §10.4:

1. the TIMES rooftop **share** pin replaced by an absolute rooftop **floor**
   (`sector.rooftop_share` → `sector.rooftop_floor`, `rooftop_gw` column);
2. `solar-hsat` removed — only ground-mounted `solar` and `solar rooftop` remain;
3. **lever A** — the CO2StoP sequestration ceiling applied to the standing
   fleet instead of to each myopic vintage;
4. **lever B** — `existing_capacities.threshold_capacity` 0 → 10.

**Deviation from the §11 test ladder, stated up front.** §11 prescribes one
change per step so a failure at step *k* is attributable to change *k*. This run
applies all four at once, at the operator's instruction. The mitigation is that
(1) and (2) are one change seen from two sides — both dismantle the PV bundle of
§7.2 — and that all four require a full myopic chain re-run from 2025 regardless,
so the ladder would have cost four chains. **If this run fails, the attribution
work of §11 steps 1 and 2 still has to be done before anything is concluded.**

This run is deliberately **not** `scen_central`: 6 h and 1 h write the same file
paths, so it was given its own run name to avoid overwriting the 1 h cabinet
batch in `results/walloon/scen_central`. It is therefore **not** comparable to
that batch — §11 step 0 is explicit that a 6 h result may never be compared
against 1 h results. The comparator for the next 6 h run is this one.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_v01_260911_1109.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` (shared with the cabinet batch) |
| Snapshots | 2010-01-01 → 2011-01-01 |
| Sector time resolution | `6h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier, 12 threads, `BarHomogeneous: 1` |
| Key scenario overrides | `rooftop_floor` on (`times_pv_rooftop_share_scen_central.csv`, `rooftop_gw`); `industry_cc_floor` on; `retrofit_nuclear_once: false`; agg caps `agg_p_nom_minmax_demande_haute.csv`; self-sufficiency absolute 2.94/6.47/10.0 TWh |
| Renewable carriers | `solar, onwind, offwind-ac, offwind-dc, offwind-float, hydro` — **no `solar-hsat`** |
| `threshold_capacity` | **10** (was 0) |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local | `--cores 12 --resources mem_mb=100000`, `SNAKEMAKE_STORAGE_CACHED_HTTP_SKIP_REMOTE_CHECKS=1` |
| LP solve | local | 12 Gurobi threads, 100 GB cap |
| Post-processing (CSVs, plots) | local | |
| HTML report (pypsa2html) | local | |
| Publication | **skipped on purpose** — `html_publish.enable: false` in `config/config.test6h_central.yaml`; no S3 upload |

## 5. Timings

Three launches, because of one environment fault and one defect found by
measuring the first result.

| # | window | what | outcome |
|---|---|---|---|
| 1 | 12:26 → 12:38 | full chain, 220 jobs | **failed** at the 2025 solve on the Gurobi licence (§9). 127/220 steps of preprocessing completed and were reused. |
| 2 | 12:44 → 13:04 | 93 jobs, `GRB_LICENSE_FILE` exported | 4/4 optimal, full post-processing + pypsa2html |
| 3 | 13:11 → 13:25 | 72 jobs, `--forcerun add_brownfield` | 4/4 optimal after the residual-crumb fix (§9 R2). Objectives unchanged to 4e-9. |

| Step | Duration |
|---|---|
| Total (first launch → verified results) | 59 min, of which ~12 lost to the licence fault |
| Prepare (network build, launch 1) | ~12 min — weather-derived resources shared with the cabinet batch, so only the 5 renewable profiles were rebuilt |
| Solve 2025 | barrier 205.4 s, 126 iterations |
| Solve 2030 | barrier 150.1 s, 103 iterations |
| Solve 2040 | barrier 198.6 s, 120 iterations |
| Solve 2050 | barrier 193.5 s, 122 iterations |
| Post-processing + plots + pypsa2html | ~9 min |

**6 h vs 1 h.** No 1 h comparison is made anywhere in this log. §11 of
`../co2-sequestration.md` is explicit that a 6 h result may not be compared
against the 1 h batch, and this run additionally changes four things at once, so
neither resolution nor lever can be separated. The comparator for the next 6 h
run is this one. The single exception is a **method** validation in §11 below,
which reproduces the doc's §5.1 figures on the 1 h networks to prove the price
metric is computed the doc's way — it compares methods, not results.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size 2025 | 4 568 006 rows / 2 136 761 cols / 11 111 540 nonzeros |
| LP size 2030 | 4 751 972 / 2 240 428 / 11 472 163 |
| LP size 2040 | 4 513 927 / 2 142 610 / 10 810 759 |
| LP size 2050 | 4 506 627 / 2 148 449 / 10 838 499 |
| Peak RAM per solve | 7.4 / 8.3 / 7.6 / 7.7 GB (2025/30/40/50) — far inside the 100 GB cap |
| Bound spread (finite upper bounds) | 5.03e6 / 5.39e6 / 8.94e7 / 3.65e7 — **passes the §11 `< ~1e9` gate in all four horizons** (was 1e17 before lever B; was 1.36e12 at 2040/2050 before the R2 fix) |

## 7. Results

| Horizon | Status | Objective (EUR/a) |
|---|---|---|
| 2025 | optimal | 3.65661260e+11 |
| 2030 | optimal | 3.65442145e+11 |
| 2040 | optimal | 2.68518887e+11 |
| 2050 | optimal | 2.82697300e+11 |

**No baseline to compare against.** §11 step 1's gate is "objective within 0.5 %
of #0", where #0 is a 6 h run with none of these changes. That run was never
made — the operator asked for the four changes together — so **the objective gate
of the test ladder could not be applied**. It is not reported as passed.

### 7.1 BEWAL PV fleet (MW, all vintages)

| | rooftop | floor | binding? | ground-mounted |
|---|---:|---:|---|---:|
| 2025 | 1 770 | — (no 2025 row) | — | 911 |
| 2030 | 4 290 | 4 290 | **yes, exactly** | 4 976 |
| 2040 | 10 470 | 10 470 | **yes, exactly** | 6 647 |
| 2050 | 22 329 | 11 269 | no — 11.1 GW above it | 6 579 |

`solar-hsat`: 0 MW in every horizon, as intended. Capacity factors all inside
`review_run.py`'s expected bands (rooftop 11.0 / 11.0 / 11.0 / 10.8 %).

### 7.2 CO₂ sequestration fleet (Mt/a) — lever A

| node | 2030 | 2040 | 2050 | own ceiling |
|---|---:|---:|---:|---:|
| DE | 50.905 | 79.147 | 79.147 | 79.147 |
| GB | 0.0 | 100.000 | 100.000 | 100.0 |
| NL | 9.095 | 9.095 | 9.095 | 9.095 |
| **total 2050** | | | **188.24** | |

Every node sits at or below its own reservoir. The 2050 total of 188.24 Mt/a is
the figure §9.4 projected arithmetically ("cuts storage from 382 to 188 Mt/a")
before the fix existed.

### 7.3 Walloon CO₂ and disposal price

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| gross capture onto `BEWAL co2 stored` (kt/a) | 1 735 | 8 727 | 8 376 | 10 700 |
| `BEWAL co2 stored` price (EUR/t) | 398.6 | 330.9 | **88.8** | **319.1** |
| effective stacked BEWAL CO₂ price (EUR/t) | 461 | 417 | 174 | 691 |

**Which layer sets the price, per horizon** (`review_run.py` §4.4 duals):
2025 and 2030 are set by the *pooled* `co2_sequestration_limit` deployment ramp
(0 and 60 Mt, μ = 463.6 and 293.4 — binding), not by lever A. 2040 and 2050 have
μ = 0 on the pooled cap, so their price is the per-node geological rent, which is
where lever A acts. **Only the 2040 and 2050 figures bear on the lever-C
decision.**

## 8. Publication (Wallonie Explorer / S3)

n/a — validation run, not published. `html_publish.enable: false`; no S3 upload,
by instruction.

## 9. Issues encountered and fixes

Working-tree edits under test (none of them committed at launch):

| File | Change |
|---|---|
| `scripts/walloon_scripts/named_pins.py` | `add_rooftop_share_constraint` → `add_rooftop_floor_constraint`; `SOLAR_ALL_CARRIERS` removed |
| `scripts/walloon_scripts/sequestration_bounds.py` | **new** — `apply_sequestration_fleet_cap` |
| `scripts/add_brownfield.py` | calls it, before `update_BEWAL_potentials` |
| `scripts/solve_network.py` | reads `sector.rooftop_floor`; raises on the old `sector.rooftop_share` key |
| `config/config.walloon.yaml` | `rooftop_floor`; `renewable_carriers` / `extendable_carriers.Generator` / `pypsa_eur.Generator` without `solar-hsat`; `threshold_capacity: 10` |
| `config/scenarios.walloon.yaml` | every `rooftop_share:` block renamed; new `scen_central_6h` |
| `config/config.test6h_central.yaml` | **new** — run name + publication off |
| `test/` | `test_rooftop_floor.py` (replaces `test_rooftop_share.py`), `test_sequestration_fleet_cap.py`, `test_no_solar_hsat.py` |
| `rules/pypsa2html.smk` | landing page set to the scenario being built (issue 2 below) |
| `instructions.md` | the Gurobi licence trap (issue 1 below) |

Three issues hit during the run:

1. **Gurobi licence path → the 2025 solve died as "Model too large".** The
   academic licence is at `~/.gurobi/gurobi.lic`, which is *not* one of the
   three places Gurobi searches (`GRB_LICENSE_FILE`, cwd, `$HOME/gurobi.lic`), so
   `gurobipy` fell back to the size-limited licence bundled with the pip wheel.
   The LP built normally and was then rejected, so the message names the model
   and reads like a modelling failure. Cost launch 1 (~12 min). Fixed by
   exporting `GRB_LICENSE_FILE`; written up in `instructions.md` under "Gurobi
   licence (local)".

2. **The pypsa2html report's front door 404'd.** `config/pypsa2html.yaml` sets
   `landing.scenario: scen_central`, and the per-scenario rule overrode `root`
   and `output.dir` but not `landing` — so `html/pypsa/index.html` redirected to
   `BEWAL_overview_scen_central.html` while the 83 pages on disk were
   `..._scen_central_6h.html`. Every page was present; only the entry point was
   wrong. This hits **any** single-scenario run whose name is not the configured
   landing scenario, so it is fixed in `rules/pypsa2html.smk` rather than worked
   around. It has to be set after the scenario is appended to `cfg.scenarios`,
   because `load_config` validates `landing.scenario` against the configured
   list.

3. **The residual crumb** — see §11 R2. Found by measuring the first complete
   result, not by the solve, which reported 4/4 optimal with it in place.

Pre-existing, unrelated, **not fixed here**: four failures in
`test/test_cabinet_batch.py::test_realiste_2030_corridor_is_not_empty`. Commit
`e27dccfd` reinstated the réaliste 2030 BEWAL floors at 3145 / 2248 while the
test still asserts those cells must be blank. Either the test or the data is
wrong; deciding which is a separate call.

## 10. Follow-ups / pending

1. **`growth_multiplier` sensitivity is now the priority** (finding R1). It binds
   at exactly 100 % in 2030 and 2050 and is the one number in the caps block that
   is not a measurement.
2. **Do not apply lever C** on the strength of this run without repeating the
   measurement at 1 h — but the direction is already clear (§11 R3).
3. Port to the réaliste scenarios only after a 1 h `scen_central` run passes,
   per §11 of `../co2-sequestration.md`.
4. The four pre-existing `test_cabinet_batch.py` failures need a decision: test
   or data (§9).
5. This run is **not** published and must not be cited outside the team until a
   1 h production run exists.

## 11. Critical review

**Reviewed by / date:** Claude Code, 2026-09-22, against
[`../run-review-checklist.md`](../run-review-checklist.md).

**Headline counts:** `161 PASS · 31 INFO · 16 WARN · 0 FAIL`
(`review_run.py results/walloon/scen_central_6h`, run with
`PYTHONPATH=<repo>`).

| Level | Verdict |
|---|---|
| 0 provenance | pass with caveats — working tree, nothing committed at launch (§9) |
| 0b commit intent | n/a — this run *is* the change under test; §9 is the intent table |
| 1 solve | pass — 4/4 optimal; but §11's objective gate could not be applied (§7) |
| 2 TIMES soft link | pass — rooftop floor and industry-CC floor both applied at their TIMES values, horizon by horizon |
| 3 accounting identities | pass with caveats — 6 pre-existing WARNs (`enc_pe` +6 to +11 TWh in every horizon, `elc_se`/`vap_se` at 2025) |
| 4 constraint compliance | pass — import cap binds exactly at all three horizons; every NTC inside its cap; sequestration fleet ≤ ceiling everywhere |
| 5 realism | pass with caveats — all capacity factors in band; 5 build-rate WARNs (R1) |
| 6 prices / costs | judgement — see R3 |
| 7 TIMES consistency | pass for what was tested (PV capacity, industrial capture) |
| 8 robustness | pass with caveats — Gurobi conditioning WARNs in all four horizons (R4) |

### Findings

**R1 — the CCL build rate binds at exactly 100.0 % in 2030 and 2050.**

| | new BEWAL solar-all | allowance | use |
|---|---:|---:|---:|
| 2030 | 6 585.0 MW | 6 585.0 | **100.0 %** |
| 2040 | 9 152.9 MW | 13 170.0 | 69.5 % |
| 2050 | 13 170.0 MW | 13 170.0 | **100.0 %** |

In two of three horizons the Walloon PV answer is therefore set by
`solving.agg_p_nom_limits.growth_multiplier: 2.0` — which
`config/config.walloon.yaml` itself describes as "the one number here that is not
a measurement, so sensitivity-test it". Before this change PV had slack against
the same limit (§7.2 of the CO₂ doc recorded 5 549 MW of it at 2040). Removing
the rooftop-share bundle moved the binding constraint **off a TIMES composition
assumption and onto an unmeasured judgement parameter**. That is an improvement
in kind — the new binding constraint is at least about Walloon deployment
capability rather than about TIMES' internal PV mix — but it is not a free one,
and it means the sensitivity run that lever E was going to get is now owed to
`growth_multiplier` instead. `review_run.py` flags the consequences directly:
rooftop +618 MW/yr over 2030→2040 and **+1 186 MW/yr over 2040→2050**, against a
400 MW/yr realism threshold and a best-ever Walloon year of 658.5 MW for *all*
PV combined.

**R2 — the lever-A implementation initially re-created the pathology lever B
removes. Fixed mid-run.** `NL co2 sequestered-2040` came out of the first
complete solve with `e_nom_max = 7.336978e-04 t`: NL's 9.0946 Mt/a ceiling minus
an inherited vintage that already filled it, leaving a floating-point crumb. A
tiny *finite upper bound* on a variable is exactly what
`existing_capacities.threshold_capacity` exists to prevent, and it carried the
2040/2050 bound spread to **1.36e12** against §11's `< ~1e9` gate. Residuals
below one millionth of a reservoir are now snapped to zero
(`RESIDUAL_EPS_REL`), with two regression tests. Re-solving changed the 2040
objective not at all and the 2050 objective by 4e-9 — it was pure numerical
hygiene, as a 7e-04 tonne bound should be. **Worth recording because it was
found by measuring the result, not by the solve: all four horizons reported
`optimal` with the crumb in place.**

**R3 — lever C is no longer warranted, and would now push the price the wrong
way.** Measured with the doc's own metric (magnitude of the time-weighted
`BEWAL co2 stored` marginal price — method validated below):

| | 2040 | 2050 |
|---|---:|---:|
| this run | **88.8** | **319.1** |
| what lever C would set (§10) | 75 | 67 |
| reference transport-and-storage chain (§5.1) | 82 | 74 |

Lever A raises the endogenous disposal price past both the proposed tariff and
the reference chain. Applying C on top would *lower* it. §5.2's warning that
"doing both double-counts" holds, in the opposite direction from the one
expected. **Caveat: 6 h, four changes at once — this establishes the level in
this run, not the attribution, and must be repeated at 1 h before C is formally
dropped.**

*Method validation.* The doc's §5.1 table (2030 86.5, 2040 57.7, 2050 78.1) was
reproduced exactly on the 1 h `scen_central` networks with the same code that
produced the figures above (−86.51, −57.65, −78.15 → magnitudes 86.5, 57.7,
78.1). This compares *methods*, not results, and is the only place this log
touches the 1 h tree.

**R4 — Gurobi conditioning warnings persist in all four horizons.** Lever B and
the R2 fix both improved the bound spread by orders of magnitude (1e17 → ≤ 9e7)
and the warnings did not go away. So the residual conditioning has another
source, and `BarHomogeneous: 1` is still doing work. Not a blocker at 6 h; watch
it at 1 h, where the doc records `scen_realiste_nobnd30` 2050 needing
`NumericFocus: 3, ScaleFlag: 2`.

**R5 — the 2050 biomass corner is where the doc says it is.** The EU-wide
`biomass limit` binds at 2050 with μ = −854.8 EUR/MWh (and at −34.0 in 2040,
−75.5 in 2030). This is the standing trap §11 warns about; it is unchanged by
this package and must be checked before any 2050 claim.

### What passed cleanly

- **Lever A**: every node at or under its own reservoir in every horizon; the
  2050 total of 188.24 Mt/a matches §9.4's arithmetic projection of 188.
- **Lever B**: carried-forward non-extendable vintages with 0 < capacity < 10
  are **0 at 2030, 2040 and 2050** (3 remain at 2025, from the separate
  `add_existing_baseyear` path). The doc's "~1 278 near-zero components by 2040"
  is gone. The count of *optimised* values under 10 MW is still ~460/horizon and
  always will be — `threshold_capacity` governs only what gets frozen forward.
- **The base year is undisturbed by `threshold_capacity: 10`**: the PV split took
  983.1 + 786.9 = 1 770.0 MW with no "standing fleet short" warning.
- **The rooftop floor is applied at exactly the TIMES value** and skipped, with a
  warning, in the horizon that has no TIMES row (2025).
- Import cap binds exactly (2.94 / 6.47 / 10.00 TWh); every NTC inside its cap;
  all capacity factors in band.

### Numbers that must not be published as-is

| Number | Reason |
|---|---|
| Every objective and capacity in this log | 6 h, and four simultaneous changes. Not a production result. |
| 2030 and 2050 BEWAL PV | Set by `growth_multiplier`, not by economics or TIMES (R1). |
| 2025 / 2030 disposal price (398.6 / 330.9) | Set by the pooled deployment ramp, not by geology — they say nothing about lever A. |
| 2050 anything | EU biomass limit binding at −854.8 EUR/MWh (R5). |
| `capital_cost = 0` capacities | `review_run.py` flags 13 carriers at 2050; pre-existing category, not a result. |

### Review follow-ups

| # | Action | Owner |
|---|---|---|
| 1 | Sensitivity on `growth_multiplier` (R1) — it now sets Walloon PV in 2 of 3 horizons | modeller |
| 2 | Repeat the disposal-price measurement at 1 h before formally dropping lever C (R3) | modeller |
| 3 | Decide the four `test_cabinet_batch.py` réaliste-corridor failures: test or data (§9) | code |
| 4 | Watch Gurobi conditioning at 1 h; escalate solver options if needed (R4) | ops |
| 5 | Port to réaliste only after a 1 h `scen_central` run passes | ops |
