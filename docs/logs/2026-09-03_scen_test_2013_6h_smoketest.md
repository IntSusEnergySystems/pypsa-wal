# Solve log — scen_test_2013_6h (local workflow smoke test)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-03 19:27 → 20:10 CEST (42m47s) |
| Operator | GitHub Copilot agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_test_2013_6h` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + scenario overlay `scen_test_2013_6h` in `config/scenarios.walloon.yaml` |
| Code version | pypsa-wal `development_plan` @ `3160022d`, plus 2 uncommitted config-only edits (added the `scen_test_2013_6h` overlay and pointed `run.name` at it — see §9). TIMES_PyPSA @ `3627a53`. pypsa2html @ `9454be9`. |
| Outcome | **success** — 4/4 optimal, full workflow incl. pypsa2html completed. One process defect found: the HTML report was published to the public site despite an attempt to suppress it (§9). |

## 2. Goal of the run

Smoke-test the **full local pypsa-wal workflow** (data build, 4-horizon myopic
solve, postprocessing, pypsa2html) at a weather year and resolution the team
had not run together before in the currently-active scenario: 2013 weather
instead of the production 2010, and 6h sector resolution instead of the
production 1h. Not a decision-grade run — everything else (TIMES `.vd`,
nuclear caps, EV settings, cost overrides) is an exact copy of the production
`scen_demande_haute` overlay, so any divergence from that scenario's results is
attributable only to the weather-year/resolution swap. Run under a dedicated
scenario name specifically so it could not overwrite `scen_demande_haute`'s
live `resources/`/`results/` tree (see §9).

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v1_260828_2808.vd` (same as `scen_demande_haute`) |
| Weather year / cutout | 2013, `europe-2013-sarah3-era5` (already cached locally, no download) |
| Snapshots | 2013-01-01 → 2014-01-01 |
| Sector time resolution | `6h` |
| Planning horizons / foresight | 2025 – 2030 – 2040 – 2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi, `BarHomogeneous 1`, 12 threads (confirmed from solver logs), Crossover 0 |
| Key scenario overrides | Same as `scen_demande_haute`: `industry_cc_floor.enable: true`, `rooftop_share.enable: false`, `electricity.retrofit_nuclear_once: false`, `self_sufficiency_constraint: false`, `agg_p_nom_minmax_demande_haute.csv`. Added for this test only: `html_publish.enable: false` (did not take effect, §9). |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local | `--cores 16`, first build for this scenario name (nothing cached) |
| LP solve | local | 12 Gurobi threads, `mem_mb=100000` cap, actual peak 8–9.5 GB |
| Post-processing (CSVs, plots) | local | |
| HTML report (pypsa2html + TIMES Sankey) | local | built and (unintentionally) published, see §9 |
| Explorer CSV extraction / S3 upload | **skipped** | explicitly out of scope for this test |

No cluster involved.

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → `RUN_FINISHED_MARKER`) | 42m47s (19:27:43 → 20:10:30) |
| Build phase for 2025 (data retrieval through first solve) | ≈21m (dominates; nothing was cached for this new scenario) |
| Solve 2025 | Gurobi barrier 192.8s; chain reached this horizon at 19:48:52 |
| Solve 2030 | Gurobi barrier 335.3s; chain reached this horizon at 19:55:40 (+6m48s incl. brownfield/prepare) |
| Solve 2040 | Gurobi barrier 227.0s; chain reached this horizon at 20:00:46 (+5m06s) |
| Solve 2050 | Gurobi barrier 367.2s; chain reached this horizon at 20:08:12 (+7m26s) |
| pypsa2html + TIMES Sankey + hub + publish | ≈2m18s (20:08:12 → 20:10:30) |

This is the first run of this scenario/weather-year/resolution combination, so
there is no prior-vintage timing to compare against. For reference, the
production `scen_demande_haute` at 1h/2010 needs ≈4.5h per solve on NIC5 `hmem`
([`2026-08-14_scen_demande_haute_2010_1h.md`](2026-08-14_scen_demande_haute_2010_1h.md));
6h is roughly two orders of magnitude cheaper, consistent with earlier 6h
benchmarks in [`instructions.md`](../instructions.md).

## 6. Resource usage

| Metric | Value |
|---|---|
| Peak RAM per solve | 2025: 8.0 GB · 2030: 8.8 GB · 2040: 9.5 GB · 2050: 9.5 GB (well under the 100 GB cap) |
| Disk footprint | `results/walloon/scen_test_2013_6h/`: 660 MB · `resources/walloon/scen_test_2013_6h/`: 916 MB |

## 7. Results

| Horizon | Status | Objective (EUR/a) |
|---|---|---|
| 2025 | optimal | 3.31219086e+11 |
| 2030 | optimal | 3.45102067e+11 |
| 2040 | optimal | 2.75749355e+11 |
| 2050 | optimal | 2.52257935e+11 |

Local result folders:

- Networks: `results/walloon/scen_test_2013_6h/networks/`
- CSVs / plots: `results/walloon/scen_test_2013_6h/{csvs,graphs,graphics,maps}/`
- HTML report: `results/walloon/scen_test_2013_6h/html/index.html`

## 8. Publication (Wallonie Explorer / S3)

Deliberately **not done** — this was a local smoke test, and the user
explicitly asked to skip the AWS/S3 upload. No `run.json`, no Explorer
extraction, nothing on S3.

| Item | Value |
|---|---|
| Raw results on S3 | not uploaded (by design) |
| Scenario folder on S3 | not uploaded (by design) |
| Explorer CSVs | not extracted |
| TIMES vd staged | no |
| Verified in Explorer dropdown | n/a |
| **HTML report published to `pypsa.squoilin.eu`** | **yes — unintentionally.** `https://pypsa.squoilin.eu/intervec/scen_test_2013_6h_20260903/`. See §9. |

## 9. Issues encountered and fixes

- **`html_publish.enable: false` scenario override did not suppress
  publishing.** `rules/publish_html.smk`'s `_publish_html_cfg()` /
  `_publish_html_enabled()` / `html_publish_targets()` read the static,
  parse-time top-level `config` dict directly (`config.get("html_publish")`),
  not the per-scenario dynamically-merged config used elsewhere via
  `config_provider`/`dynamic_getter`. Setting `html_publish.enable: false`
  inside the `scen_test_2013_6h:` block of `config/scenarios.walloon.yaml` has
  no effect on whether `rule all` includes the publish target, because that
  gating is evaluated once, before any scenario/wildcard resolution, and it
  only ever sees the base `config.walloon.yaml` value (`enable: true`).
  **Consequence: this test run's HTML report was published to the public
  production URL** (`.../intervec/` has directory listing on, so it is
  discoverable). Not reverted at the time of writing — flagged to the user,
  pending a decision on takedown (§10).
- **Did not reuse the `scen_demande_haute` scenario name.** `resources/` and
  `results/` are namespaced per run name with no weather-year/resolution
  component (`RDIR = walloon/<scenario>/`), and `run.shared_resources.policy`
  is `false` (default, not overridden here) — nothing is shared between
  scenario names. Reusing the production name would have overwritten its live
  2010/1h tree the moment Snakemake decided the DAG needed updating, which the
  instructions' own weather-year-change warning says is not reliably detected.
  Added a full copy of `scen_demande_haute`'s overlay under a new key instead
  (`config/scenarios.walloon.yaml`), with only the weather/resolution keys and
  `html_publish.enable` changed, and pointed `run.name` at it (production entry
  commented out for an easy revert — not yet reverted, see §10).
  Consequence: the new scenario tree started empty, so rules that do not
  depend on weather year or resolution (`build_wallon_demands`,
  `process_cost_data`, `build_shapes`, `build_powerplants`, biomass/industrial
  potentials, busmaps, …) recomputed even though their output is identical to
  what is already cached for `scen_demande_haute`. This is expected given the
  policy default and was judged cheaper/safer than the alternative.
- **Unrelated to this run:** discovered that `wc` is aliased on this machine
  (`~/.bash_aliases:16`) to a command that launches a webcam/microphone
  recording via `cvlc`. Flagged to the user separately; avoided `wc` for the
  rest of the session (`grep -c ''` / `awk 'END{print NR}'` instead). No
  recording appears to have actually been captured (file timestamps
  unchanged, no process left running).
- No solver, infeasibility, or workflow-mechanical issues: 235/235 Snakemake
  steps completed, 4/4 horizons optimal, 0 infeasible.

## 10. Follow-ups / pending

| # | Item |
|---|---|
| 1 | Decide whether to take down `https://pypsa.squoilin.eu/intervec/scen_test_2013_6h_20260903/` (needs the `negawatt` SSH key this agent does not control from here without confirmation) or leave it. |
| 2 | Fix `rules/publish_html.smk` so a per-scenario `html_publish.enable` override actually works (or document that only the top-level key is honoured) — otherwise every future one-off scenario will publish by default. |
| 3 | Revert `run.name` in `config/config.walloon.yaml` back to `scen_demande_haute` (currently pointed at `scen_test_2013_6h`). |
| 4 | Decide whether to keep, archive, or delete the `scen_test_2013_6h` overlay and its `resources/`/`results/` tree. |
| 5 | If a real weather-year or 6h-vs-1h sensitivity comparison is wanted, diff this run's `csvs/` against a same-vintage `scen_demande_haute` run — not done here (no 2013-weather production run exists to diff against). |

See §11 for the critical review.

## 11. Critical review

**Reviewed by / date:** GitHub Copilot agent (supervised by sylvain), 2026-09-03.

**Headline counts:** `177 PASS · 26 INFO · 23 WARN · 0 FAIL` from
`python -m scripts.walloon_scripts.review_run results/walloon/scen_test_2013_6h --full`
(note: must be invoked as `python -m scripts.walloon_scripts.review_run`, not
`python scripts/walloon_scripts/review_run.py`, or its `scripts.*` absolute
import fails). Plus `check_heat_profile_fidelity.py scen_test_2013_6h live`:
total `|annual gap|` over every (year, group, bus) = **0.14253 TWh** (exit 0,
no group missing).

| Level | Verdict |
|---|---|
| 0 provenance | pass |
| 0b commit intent | pass with caveats |
| 1 solve | pass |
| 2 TIMES soft link | pass with caveats |
| 3 accounting identities | pass |
| 4 constraint compliance | pass |
| 5 realism | pass with caveats |
| 6 prices / costs | pass with caveats (partial — see below) |
| 7 TIMES consistency | pass |
| 8 robustness | n/a — this run *is* the level-8 data point, not yet compared |

### Commit intent (level 0b)

Previous production log: [`2026-09-02_scen_demande_haute_2010_1h.md`](2026-09-02_scen_demande_haute_2010_1h.md)
(latest by timestamp — started 19:28, "in progress; 2030-50 relaunch
2026-09-03") at pypsa-wal SHA `87552368`. `git log --oneline 87552368..HEAD`:

| Commit | Class | Claimed behaviour | Observed in this tree | Verdict |
|---|---|---|---|---|
| `4459a96c` add missing year_currency values, add central gas/biomass CHP, SMR, H2(l) storage tank to `input_parameters_for_models.csv` | data | new cost-table rows | `process_cost_data` for all 4 horizons completed without error; did not diff individual cost rows | n/a (data-only, not independently checked) |
| `788cc75a` set PV/onwind lifetime to 25 years | data | shorter asset life → different annuity | not independently checked | n/a (data-only) |
| `28870714` Development plan: NTC floors/import limits, industrial capture and rooftop share pins, demande_haute scenario updates | physics/config | NTC floors bind; `industry_cc_floor` active; `rooftop_share` stays off | NTC section (4.3) fully pass with plausible usable/nominal/rent figures; `rooftop_share.enable: false` confirmed in the overlay copied here; did not specifically verify the industrial-capture floor bound anything | pass (NTC, rooftop-off); not verified (industry_cc_floor) |
| `93bdf848` Merge origin/master: latest `input_parameters_for_models.csv` values | data | merge only | n/a | n/a |
| `3160022d` (HEAD) multiple corrections to the implementation of the last changes | unknown (vague message) | not stated | cannot audit without a before/after pair; this run only has the "after" state | **unresolved** — flag for the modeller if this commit matters for physics |

Two of five commits are data-table-only and not independently checked here
(would need a cost-table diff, out of scope for a workflow smoke test); the
`28870714` mechanisms that are checkable elsewhere in this review (NTC,
rooftop share) pass; the tip commit's message is too vague to derive an
observable from and was not audited.

### Findings

**R1 — `coal for industry` soft-link divergence grows to +36.7% at 2040.**
Observed: +10.07% (2025), +14.05% (2030), +36.69% (2040), +22.81% (2050) vs
TIMES. This is a **pre-existing, already-documented** divergence (the
checklist itself records +8%/+12% at 2025/2030 in the first reviewed
production run) — this test does not introduce it, and the magnitude here is
larger but the carrier is the same known suspect. Not re-diagnosed in this
review; upstream cause is unchanged.

**R2 — Total BEWAL electric load slightly outside the ±0.5% soft-link
tolerance at the later horizons.** 2040: −0.81%, 2050: −0.99% (2025/2030 are
within ±0.05%). Small in absolute terms but worth tracking if it grows further
in future re-runs of this data vintage.

**R3 — Sankey transformation-node WARNs are the checklist's known mapping
holes, not new ones.** `enc_pe` (in=0, out 7–12.75 TWh across horizons),
`pac_fe` (constant −0.147 TWh gap in 2025/2030/2040), `vap_se` (small,
sign-flipping gap) all match the pattern the checklist already names as
"known mapping holes, not this bug" (solid-biomass `prod` on a regional node,
DAC, district heat). The nodes that would actually indicate a real hole — BEV,
stationary battery, TES — all closed to <0.001 TWh at every horizon.

**R4 — Build rates for onwind and solar-hsat exceed historical Walloon norms,
the same way the checklist expects them to be checked.** onwind 2025→2030
+431 MW/yr (vs "well below 300 MW/yr" historical); solar-hsat +478 MW/yr
(2025→2030) and +450 MW/yr (2040→2050) (vs "well below 400 MW/yr" the script
uses; checklist's own text says historical PV is ~200–300 MWp/yr, so this is
flagged under either threshold). **Not diagnosed against the production
2010 run in this review** — no same-vintage comparison was performed, so it is
not yet known whether this is a weather-year artefact or a `demande_haute`
characteristic that the production run shares.

**R5 — Process/tooling defect, most operationally important finding of this
run.** The `html_publish.enable: false` per-scenario override silently had no
effect, and this test run's HTML report was published to the public
production site (§9, §10 item 2). This is a workflow defect surfaced by the
test, not a Walloon-physics finding, and should be fixed in
`rules/publish_html.smk` before the next one-off scenario run.

### What passed cleanly

- Solve convergence: 4/4 optimal, 0 infeasible, standard Crossover-0/large-bounds
  warnings only (already normalized by the checklist as tolerated-not-benign).
- Every accounting identity `review_run.py` checks: all BEWAL bus balances and
  the Belgium-wide AC+LV balance residual to 0.00% at every horizon; `biogas`/
  `solid biomass` `e_sum_max` respected; EV-battery bus closes.
- EV grid draw = TIMES `electricity road` to within 0.00%–0.00% at all four
  horizons (exact match).
- Nuclear MW_e trajectory matches the documented alignment exactly: 2 030 MW_e
  Belgium-wide in 2040 (1 030 BEWAL + 1 000 BEVLG), 6 000 MW_e in 2050 (3 000 +
  3 000) — see [`nuclear-alignment-20260816.md`](nuclear-alignment-20260816.md).
- NTC borders: Nemo Link (BE-GB) and ALEGrO (BE-DE) both cap at exactly
  1 000 MW as documented; all other borders' usable capacity is plausible.
- Heat-profile fidelity under option B′: 0.14253 TWh total gap across all 4
  horizons and all groups — smaller than the checklist's own documented
  ~0.46 TWh (2040) reference case; worst single mismatch is the 2050
  heat-pump/biomass-boiler pair (0.033 TWh, biomass boiler fully retired but
  still owed a residual 0.033 TWh by the pinned profile).
- Capacity factors and heat-pump COP all inside the checklist's expected
  ranges: onwind 25.3–27.7% (18–32% expected), solar 10.8% (8–15%),
  solar-hsat 12.4% (9–17%), run-of-river 33.2% (15–45%), heat-pump effective
  COP 2.48–2.59 (2.5–3.5 expected, 2030 marginally below floor).

### Numbers that must not be published as-is

- **2050 zero-capital-cost "capacities"** (electricity distribution grid
  10 178 MW, gas pipeline 7 500 MW, H2 pipeline 4 645 MW, water-pits
  charger/discharger 4 510 MW each, BEV charger 4 194 MW, and others down to
  agriculture machinery oil 72 MW) — degenerate variables, not a result; do
  not plot as capacities (checklist 5.4/5.5).
- **Any number from this run compared directly against `scen_demande_haute`**
  without first stating it is a different weather year (2013 vs 2010) *and* a
  coarser resolution (6h vs 1h) — both are known movers of storage, peaking
  plant and curtailment (checklist level 8), and this run was not built to
  isolate one from the other.
- The CO₂ effective BEWAL price series (425 / 88 / 108 / 426 EUR/t at
  2025/2030/2040/2050) — non-monotonic for the same reasons the checklist
  documents for the production run (2025 caps price a decarbonised
  counterfactual, not "today"; the biogas block flips on/off near its CO₂
  break-even) — not a new trend to report on its own.

### Review follow-ups

| # | Action | Owner |
|---|---|---|
| 1 | Fix `rules/publish_html.smk` to honour a per-scenario `html_publish.enable` override (currently reads only the static top-level config) | code |
| 2 | Decide whether to take down the accidentally-published test page at `pypsa.squoilin.eu/intervec/scen_test_2013_6h_20260903/` | ops |
| 3 | Revert `run.name` to `scen_demande_haute` and decide the fate of the `scen_test_2013_6h` scenario/tree | ops |
| 4 | If the weather-year/resolution sensitivity itself is of interest, run the same diff this log flags as not-yet-done against a same-vintage `scen_demande_haute` result | modeller |
| 5 | Independently verify the `28870714` industrial-capture floor and the two data-only cost commits this review marked `n/a` | modeller |
