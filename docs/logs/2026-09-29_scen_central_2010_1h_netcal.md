# Solve log — scen_central, weather 2010, 1 h, network-cost calibration

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-29 12:27 (6 h smoke test) / 12:53 (1 h prepare) → 19:03 (2050 solved), 19:40 (post-processing) |
| Operator | Claude session on the home workstation (`pop-os`, on the university campus: no VPN), at the user's request |
| Run name (`run.name`) | `scen_central` only, via `RUN_NAME=scen_central`. The 6 h smoke test ran `scen_central_6h` locally |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + `config/scenarios.walloon.yaml`; `cluster/config_cluster.yaml` on NIC5 |
| Code version | pypsa-wal `bbc9450e` (`master`, nuclear seed threshold) **plus uncommitted working-tree edits**: the network-cost calibration of [`../network-costs-review-20260928.md`](../network-costs-review-20260928.md) (§9 below lists the files). TIMES_PyPSA `c6f93e2` |
| Outcome | Four horizons optimal. The nuclear-dust fix was applied between 2025 and 2030 (§12.7). Not published |

## 2. Goal of the run

Re-solve the central scenario with the network-cost calibration decided on 2026-09-29.
That calibration answers the stakeholder feedback on the September cabinet deck's
*Distribution* and *Transport* bars. It changes:

* the distribution unit cost (620 €/kW) and losses (5 %);
* industry at HV (70 %);
* rooftop-PV hosting (120 €/kWp);
* the gas-boiler grid charge (factor 0.12);
* the AC branch cost (450 / 408 / 372 €/MW/km);
* ALEGrO at its project cost;
* CO₂ trunk economies of scale;
* a 3.5 % discount rate for regulated network assets;
* the HVDC reversed-twin double-counting, now fixed.

**Baseline** is the 24 September central run
([`2026-09-24_scen_central_2010_1h.md`](2026-09-24_scen_central_2010_1h.md)): same TIMES
file `scen_central_v01_260923_2_2309.vd`, same weather and resolution.

**The difference is not purely the calibration.** The code also carries `bbc9450e`
(nuclear seed after the 10 MW threshold, committed the same morning) and the
working-tree edits the 24 September run had, now committed in `dd25f62b`.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_v01_260923_2_2309.vd`. Pulled from NIC5 into `../TIMES_PyPSA/data/` and symlinked; symlink mtime set to the file's (2026-09-23 17:54) |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, 8 760 h |
| Sector time resolution | `1h` (the smoke test: `6h`) |
| Planning horizons / foresight | 2025, 2030, 2040, 2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE, FR, GB, NL, DE, LU |
| Solver + options | Gurobi barrier, 16 threads, `BarHomogeneous 1` (cluster overlay) |
| Network calibration | see [`../network-costs-review-20260928.md`](../network-costs-review-20260928.md) §2–§6 |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Pre-processing | reused, not re-run | Per-run resources of the 24 Sep office run pulled from NIC5 into `resources/walloon/scen_central/`. The local 15 Sep trees were moved to `resources/_archive/`, `results/_archive/` and `benchmarks/_archive/` (`scen_central_20260915_vd260911`) |
| 6 h smoke test | local, 12 threads, 100 GB | `scen_central_6h` (TIMES 260911), 19 jobs, `tmp/run_netcal_6h_test.log` |
| Prepare (1 h) | local, `nic5.sh prepare` | 12 jobs: `process_cost_data` ×4, `add_electricity`, `prepare_network`, `time_aggregation`, `prepare_sector_network` ×4, `add_existing_baseyear` |
| LP solve 2025 | NIC5, partition `batch` | 16 CPUs, 80 GB, runtime 720 min; orchestrator pid 1041451; 7 jobs (4 solves + 3 `add_brownfield`). The node `nic5-w005` was fully allocated, but the work units show no measurable slowdown from it (§12.2) |
| LP solve 2030–2050 | NIC5, partition `hmem` (`nic5-w072`) | Switched after 2025 (user decision). `batch` had no node with 16 free cores. The first hmem orchestrator (pid 1566073) was stopped at 15:55 for the nuclear-dust fix (§12.7). Relaunched at 15:57, orchestrator pid 1617736, 6 jobs |
| Post-processing | local | `nic5.sh postprocess` with `AUTO_UPLOAD_S3=0` and `HTML_PUBLISH=0`, then `network_cost_report.py` and `bill_harmonisation.py` |
| Explorer / S3 | not published | not requested |

The 24 Sep results were archived on NIC5 before the solve
(`results/_archive/scen_central_20260924_vd260923/`) and locally.

## 5. Timings

| Step | Duration |
|---|---|
| 6 h smoke test (prepare + 4 solves) | 12:27 → 12:44, 17 min; barrier 181–228 s per horizon |
| Prepare 1 h, attempt 1 | 12:49 → 12:49. Stopped before submission: HVAC flat 450 instead of the DEA shape (§9) |
| Prepare 1 h, attempt 2 | 12:53:08 → 12:53:47 |
| Push | 12:53 → 12:55, failed (dangling symlink); 12:56 → 12:56:08 |
| Queue wait | < 1 min (2025 job on `nic5-w005` at 12:57) |
| Solve 2025 (`batch`, `nic5-w005`) | 12:57 → 15:36. Barrier 489 iterations, 9 048 s. Baseline: 300 iterations, 4 401 s (§12) |
| Switch to `hmem` | 15:36 → 15:43. The stopped orchestrator hung on its cancelled `add_brownfield` job and had to be killed. Then `--unlock` and a dry-run (6 jobs) |
| First 2030 attempt | 15:43 → 15:55, stopped for the fix of §12.7 |
| Solve 2030 (`hmem`, `nic5-w072`) | 15:57 → ~17:03. Barrier 205 iterations, 3 730 s (baseline 266 iterations, 5 056 s). Objective 3.81558274e11 (baseline 3.81781013e11) |
| Solve 2040 (`hmem`, `nic5-w072`) | ~17:08 → ~17:58. Barrier 188 iterations, 2 885 s, 2 600 work units (baseline 207 iterations, 3 307 s, 2 956 work units). Objective 2.64982447e11 |
| Solve 2050 (`hmem`, `nic5-w072`) | ~18:07 → ~18:58. Barrier 181 iterations, 2 919 s, 2 632 work units (baseline 230 iterations, 4 328 s, 3 262 work units). Objective 2.88929508e11 (baseline 2.90884512e11) |

## 6. Resource usage

Peak memory of the solve jobs, from the `Maximum memory usage` line of `logs/*_python.log`.
Every job had an 80 GB allocation.

| Horizon | This run | 24 Sep |
|---|---:|---:|
| 2025 | 30.9 GB | 29.5 GB |
| 2030 | 31.2 GB | 30.6 GB |
| 2040 | 31.1 GB | 30.7 GB |
| 2050 | 35.2 GB | 31.6 GB |

**TIMES heat pins.** No TIMES heat pin was relaxed in any horizon: 0.0000 TWh_th was
undelivered each time.

**Cluster time.** This run used about 5 h of 16-core solve time: 2025 on `batch`, the rest on
`hmem`. The three diagnostic 2025 solves of §12.5 used about 3 h 45 more; the control was
cancelled after ~15 min.

## 7. Results

**All four horizons are optimal.** The results were pulled at 19:05 (`results/walloon/scen_central/`,
targeted rsync). Post-processing ran locally with `AUTO_UPLOAD_S3=0 HTML_PUBLISH=0` (15 of 15
steps, no upload). Then `network_cost_report.py`, `bill_harmonisation.py` and `review_run.py`
ran; the comparison below is `tmp/ablation/compare_netcal.py`.

| Horizon | Objective | 24 Sep objective | Δ |
|---|---:|---:|---:|
| 2025 | 3.42830698e11 | 3.52212805e11 | −9.38 bn€ (−2.7 %) |
| 2030 | 3.81558274e11 | 3.81781013e11 | −0.22 bn€ |
| 2040 | 2.64982447e11 | 2.70555960e11 | −5.57 bn€ |
| 2050 | 2.88929508e11 | 2.90884512e11 | −1.96 bn€ |

**Only 2025 is a clean before/after.** From 2030 on, the comparison is dominated by nuclear,
not by the network calibration. With `bbc9450e`, the FR/GB `nuclear-2025` options survive
the 2025 → 2030 cleanup. France then rebuilds its fleet:

| Nuclear (GW_e) | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| FR, this run | 39.4 | 61.8 | 62.9 | 62.9 |
| FR, 24 Sep | 39.4 | 13.1 | 6.2 | 0 |
| GB, this run | 8.7 | 5.5 | 13.2 | 13.2 |
| GB, 24 Sep | 8.7 | 4.7 | 3.4 | 3.4 |
| BEWAL and BEVLG, 2050 | | | | 3.0 each (24 Sep: 1.03 and 1.0) |

The 15 September batch (`scen_central`, `scen_taxshift` and `scen_retardnucleaire`) has the
same FR/GB figures. It is the 24 Sep baseline that is atypical: the 10 MW cleanup deleted the
foreign nuclear options there.

| Walloon / Belgian indicator | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| BEWAL distribution link (GW) | 3.10 (3.69) | 4.13 (4.31) | 6.36 (7.72) | 7.99 (9.49) |
| BEWAL distribution inflow (TWh) | 15.4 (20.8) | 20.2 (26.2) | 33.0 (45.6) | 43.3 (52.5) |
| BEWAL rooftop PV (GW) | 1.77 (1.77) | 4.29 (4.29) | 10.47 (10.47) | 11.27 (18.87) |
| BEWAL utility PV (GW) | 0.91 (0.91) | 2.98 (4.98) | 6.38 (7.21) | 13.00 (10.60) |
| BEWAL batteries incl. home (GW) | 0.29 (0.29) | 0.49 (2.59) | 2.10 (3.11) | 6.39 (8.98) |
| BEWAL gas boilers (GW_th) | 9.46 (8.66) | 7.56 (7.15) | 2.93 (2.93) | 1.97 (1.97) |
| AC expansion touching BE (GW) | 0 (0) | 0 (0.03) | 1.77 (1.89) | 7.31 (6.22) |
| H₂ pipelines touching BE (GW) | 0.13 (0.14) | 7.8 (11.4) | 8.8 (11.8) | 13.3 (19.0) |
| CO₂ pipelines touching BE (kt/h) | 0 (0) | 4.05 (2.33) | 6.49 (4.48) | 8.41 (7.09) |
| Reversed-DC capital cost (M€/a) | 0 (0) | **0 (713)** | **0 (774)** | **0 (856)** |
| BE zonal price, time average (€/MWh) | 105.4 (109.9) | 124.6 (192.6) | 97.6 (104.1) | 111.0 (123.4) |
| EU ETS1 CO₂ dual (€/t) | 77.6 (83.6) | 93.9 (186.7) | 130.0 (162.0) | 659.1 (644.0) |

24 Sep values are in brackets.

**Network cost segments** (`csvs/network_cost_segments.csv`, M€₂₀₂₅/a):

| Segment | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| Distribution | 982.8 | 1 082.1 | 1 247.1 | 1 347.0 |
| Transport | 463.7 | 559.6 | 740.1 | 800.2 |

The per-layer detail and the TIMES comparison are in the network-cost doc §9.

## 8. Publication

Not published: neither S3 nor the Explorer nor pypsa.squoilin.eu.

## 9. Issues encountered and fixes

* **The local pre-processing did not match the scenario.**
  * *Symptom:* `scen_central` names `…260923_2_2309.vd`, which was absent here; the local
    resources dated from 12–15 Sep (TIMES 260911).
  * *Fix:* pulled the `.vd` and the 24 Sep per-run resources from NIC5.
* **The dry-run wanted 96 jobs after the pull**, where 12 were expected.
  * *Cause 1:* Snakemake counts the rule's *benchmark* file in the "oldest output" time
    (`jobs.py`, `output_mintime`). The local benchmarks of the 12–15 Sep builds were
    older than the shared inputs.
  * *Cause 2:* the new `.vd` symlink carried today's mtime.
  * *Fix:* moved `benchmarks/walloon/scen_central` to `benchmarks/_archive/`, and
    `touch -h` on the symlink. `--cleanup-metadata` alone did not help.
  * The dry-run then had the 12 expected jobs.
* **The HVAC trajectory was flat.** `test_cost_learning` requires managed investments to
  follow technology-data's learning shape. The first prepare had HVAC flat at 450; it was
  stopped before submission and redone with 450 / 408 / 372. The 6 h smoke test ran
  with the flat value and is only a code test.
* **The push failed on a dangling symlink.** `run6h.log` points into an old session's
  scratchpad, and rsync exits with code 23. Re-pushed with `--exclude run6h.log` added
  to `PUSH_EXCLUDES`; the link itself was not deleted.
* **The patcher rejected discount-rate overrides.** `build_common_parameters.py
  patch_costs` required a `custom_costs.csv` row for `cost:<tech>:discount rate`
  targets, which belong in `discount_rates.csv`. They are now skipped there.
* **Four pre-existing test failures**, `test_cabinet_batch::test_realiste_2030_corridor_is_not_empty`,
  fail on `bbc9450e` before any change of this run. They are unrelated and were left
  as found.

**Files changed:**
* modified:
  * `config/config.walloon.yaml`, `config/input_parameters_for_models.csv`;
  * `data/walloon/custom_costs.csv`, `discount_rates.csv`, `discount_rates_car11.csv`;
  * `rules/build_sector.smk`, `rules/solve_myopic.smk`;
  * `scripts/add_brownfield.py`, `add_electricity.py`, `build_common_parameters.py`,
    `prepare_sector_network.py`, `walloon_scripts/plot_cost_segments.py`;
  * `test/test_discount_rates.py`, `instructions.md`, and the network-cost doc;
  * `scripts/add_brownfield.py` again (nuclear dust, §12.7) and
    `test/test_nuclear_seed_threshold.py`, both pushed at 15:57 before the 2030–2050 solves;
* new:
  * `data/walloon/network_cost_calibration.csv`, `transmission_cost_overrides.csv`;
  * `scripts/walloon_scripts/network_calibration.py`, `network_cost_report.py`,
    `bill_harmonisation.py`, `build_co2_trunk_overrides.py`,
    `build_network_cost_calibration.py`;
  * `test/test_network_calibration.py`.

## 10. Follow-ups / pending

* Commit the working tree (not done: not requested). It now also contains the nuclear-dust
  fix in `add_brownfield.py` and its test.
* Foreign nuclear build rate (§11 R1). This is a scenario-design decision.
* A calibration-only counterfactual chain, to attribute the 2030–2050 network effects
  (§11 R4).
* The 2025 seed options of §12.8, if the 2025 solve time matters.
* The ClimAct extraction ran locally at ~19:50. It was staged in
  `results/walloon/scen_central/explorer/` and not uploaded. The redrawn chart is in
  `docs/figures/netcal_20260929/` (FR + EN). Its subtitle still reads "September 2026
  cabinet batch" (fixed text in the script). Nothing is published.
* Re-solve `scen_retardnucleaire` (and the rest of the batch) with the calibration before
  comparing scenarios; the calibration is in the base config.
* The data requests of the network-cost doc §11: ICEDD mark-ups and `G_YRFR`, the DSOs'
  split of E1.1, Elia's revenue breakdown.

## 11. Critical review

**`review_run.py`: 161 PASS · 30 INFO · 14 WARN · 1 FAIL (exit 1).** The 24 Sep run had 188 /
30 / 15 / 0.

| Level | Finding |
|---|---|
| 0 provenance | `run.json` is absent: a local pull, not an S3 upload. The code is `bbc9450e` plus the uncommitted working tree listed in §9 |
| 1 solver | All four horizons are optimal, with Crossover 0. The "large bounds / rhs" conditioning warnings are as on 24 Sep. The 2030 RHS range is [1e-4, 1e9] after the dust fix (§12.7) |
| 2 TIMES soft link | Every TIMES demand is matched to 0.00 %. The BEWAL electric load closes. No heat pin was relaxed |
| 3 accounting | Every BEWAL and Belgian carrier balance closes. **FAIL:** 2050 `tes_se` Sankey node, 1.162 TWh in against 1.104 out (−0.058 TWh, 5 %). This is a Sankey transformation node. The gap is the size of a water-pit standing loss that the node does not draw, but that was not checked further. `enc_pe` gaps of 5–10 TWh, as on 24 Sep (known hole) |
| 4 caps | The BEWAL import cap binds in 2030/40/50 (μ −6.4 / −6.7 / −7.3 €/MWh). The effective BEWAL CO₂ price is 260 / 148 / 677 €/t in 2030 / 40 / 50 |
| 5 plausibility | Capacity factors and heat-pump COPs are in range. The build-rate warnings are as on 24 Sep: onwind and solar 2025→30, rooftop 2025→40 |
| 5.5 zero-cost capacity | The 7 992 MW of "electricity distribution grid" at zero capital cost are the `-reversed` twins. They equal the forward total 3 100 + 1 028 + 2 237 + 1 627, so this is not a degenerate result |

**R1 — The before/after is dominated by nuclear from 2030 on (§7).**
* 61.8 GW of French nuclear in 2030 means about 49 GW of new build in five years (61.8 − 13.1 GW still standing). No
  build-rate limit applies to foreign nuclear, so this is a model artefact.
* The same numbers are in the September batch, so the cabinet deck carries it too. It is
  not part of the network work.
* **Proposed next step:** cap FR/GB/NL/LU nuclear new build per horizon (e.g. the EPR2
  programme), or drop the foreign `extendable_nuclear_links` before 2040.

**R2 — Network-specific effects can only be attributed in 2025 and in network-local
quantities.**
* **2025:** in the clean horizon, the system cost falls by 10.4 bn€/a (−1.8 %). This is
  mostly the 3.5 % annuity on every existing network asset of the six countries.
* **Distribution:** the BEWAL distribution link shrinks by 0.59 GW and its inflow by
  5.4 TWh, which is the HV industry split (E6).
* **Gas boilers:** BEWAL gas boilers rise by 0.8 GW_th, the lower avoidable grid charge
  (GD2).
* **Reversed DC legs:** they now cost nothing in every horizon (TV4).

**R3 — Rooftop PV, batteries and H₂ pipelines fall; CO₂ pipelines grow.**
* 2050 rooftop PV is 11.3 GW against 18.9, and 2030 batteries 0.5 GW against 2.6.
  * These are consistent with the PV hosting charge and the cheaper distribution grid:
    batteries earn less from peak shaving.
  * 2050 is confounded by R1, 2030 much less so: the only nuclear difference there is
    abroad.
* H₂ pipelines are 26–32 % smaller, and CO₂ pipelines 19–74 % larger (the TR12 economies of
  scale).
* **The 2030 price and CO₂ dual halve** (192.6 → 124.6 €/MWh, 186.7 → 93.9 €/t). This follows
  the French nuclear of R1, not the networks.

**R4 — A calibration-only counterfactual for 2030–2050 would need a second chain.** That is
today's code with `sector.network_calibration` and the five switches reverted, about 4 h on
NIC5. It was not run; see §10.

## 12. Investigation: why the 2025 solve took twice as long

Asked on 2026-09-29 at 15:25: *which recent change leads to numerical difficulties?*

### 12.1 Symptom

| | 24 Sep baseline | this run |
|---|---:|---:|
| Barrier iterations | 300 | 489 |
| Barrier time | 4 401 s | 9 048 s |
| Gurobi work units | 3 936 | 8 470 |
| Seconds per iteration | 14.7 | 18.5 |
| Seconds per work unit | 1.12 | 1.07 |
| Final primal residual (Gurobi log) | 8.9 | 27 |
| Objective | 3.52212805e11 | 3.42830698e11 |
| "Numerical trouble" / infeasible | no | no |

**Solver settings are identical in both runs.**
* Method 2, `BarConvTol 1e-5`, `BarHomogeneous 1`, `Crossover 0`, `AggFill 0`, `PreDual 0`,
  `Seed 123`, 16 threads, `GURO_PAR_BARDENSETHRESH 200`.
* `NumericFocus` is at its default (0) in both. It was not switched off by any change.

**The numerics Gurobi reports are the same too.**
* Matrix range [6e-4, 8e2], objective [9e-3, 1e9], RHS [1e-2, 1e9].
* Bounds [7e-2, 1e10] (baseline 2e10).
* The same "large rhs / large bounds" warnings.
* The factor is the same size (4.59e8 against 4.56e8 non-zeros).

**The two runs converge differently.** This run reached the final objective by iteration ~120,
faster than the baseline (which had a wobble near iteration 100). It then spent ~370
iterations on a slow primal-feasibility tail: 6.3e1 at iteration 300, 4.1e1 at 360,
2.7e1 at 489.

### 12.2 Wall time: all of it is solver work, none is contention

**The contention hypothesis, now withdrawn.** `nic5-w005` was fully allocated (64/64 cores,
load 59), and other users' jobs started on it at about 13:23 and 14:15. While the solve was
running I attributed ~1 870 s of the extra time to that contention. That was based on the
seconds per iteration rising from ~14 to ~23.

**The work units contradict it.** Gurobi counts them independently of machine load:
* this run: 8 470 work units against 3 936 (× 2.15), for × 2.06 in wall time;
* seconds per work unit: 1.07 against 1.12.

So the node's load did not measurably slow this solve.

**The per-iteration rise is the barrier's own tail.** Iterations get more expensive towards
convergence in every run:

| Run | s/iteration, 100–150 | s/iteration, 250–300 |
|---|---:|---:|
| baseline | 11.8 | 18.9 |
| this run | 15.8 | 19.9 |

This run simply spent more iterations there.

**The hmem move.** The chain still moved to `hmem` (`nic5-w072`) for 2030–2050 (§4), because
`batch` had no node with 16 free cores.

### 12.3 What changed in the LP

* **Code.** Between the baseline code (`32bab4e9` plus the edits committed as `dd25f62b`) and
  this run, only two changes reach the 2025 LP:
  * `bbc9450e` (nuclear seed threshold);
  * the network-cost calibration in the working tree.
  The other commits are documentation, infographics and scenario CSVs that this run does not
  read.
* **Size.** The 2025 LP grew by 105 125 rows and 52 563 columns. That is exactly
  6 × 8 760 × (2 rows, 1 column), plus 3 capacity columns and 5 rows. **All of it is the six
  `nuclear-2025` seeds that `bbc9450e` keeps:**

| Link | p_nom (MW_th) | extendable | must-run band | p_nom_opt |
|---|---:|---|---|---:|
| BEVLG nuclear-2025 | 0.061 | no | 0.783–0.883 | fixed |
| BEWAL nuclear-2025 | 0.031 | no | 0.783–0.883 | fixed |
| DE nuclear-2025 | 0.031 | no | 0.826–0.926 | fixed |
| GB nuclear-2025 | 0.031 | yes, p_nom_max ∞ | 0.584–0.684 | 4.9e-7 |
| LU nuclear-2025 | 0.031 | yes, p_nom_max ∞ | 0.900–1.000 | 2.1e-4 |
| NL nuclear-2025 | 0.031 | yes, p_nom_max ∞ | 0.801–0.901 | 2.0e-6 |

* **The calibration adds no rows or columns.** It changes coefficients only:
  * capital cost on 100 links (pipelines, DC, distribution grid, gas boilers), the 11 AC
    lines and 10 rooftop-PV generators;
  * the efficiency of the 16 distribution-grid links (0.97 → 0.95);
  * the loads: 8 new industry HV loads, and the AC-bus base loads, which scale with that
    efficiency (× 0.9794).

**The extendable seeds end at zero capacity.** GB, LU and NL all finish at p_nom_opt ≈ 0.
With a must-run band, each of them leaves 8 760 pairs of rows 0.8·p_nom ≤ p ≤ 0.9·p_nom that
meet at one degenerate point, (0, 0). This is the textbook shape that slows an interior-point
tail.

**The baseline already had one such option.** Its FR nuclear-2025 is extendable and also ends
at zero, in both runs.

### 12.4 Evidence against a single culprit

* **The seeds are not new to the model.** The 12–13 September batch ran with
  `threshold_capacity: 0` and had all six seeds; `c094ff46` (22 Sep) raised the threshold to
  10 MW, which removed them. That batch's 1 h 2025 solves took 183–372 iterations, apart from
  one run with 583, so the seeds did not by themselves slow those solves down. The 24 Sep
  baseline is the only recent run without them.
* **The iteration count is erratic under cost-only changes.** The six `scen_nuctip_*` runs
  of 13 Sep have the same LP structure (30 906 435 rows, 14 568 672 columns) and differ only in
  the nuclear capital cost. Their 2025 solves took 583 / 278 / 183 / 282 / 372 / 297
  iterations. `scen_nuctip_4500` had the same long primal tail as this run: 8.9 at iteration
  300, 0.7 at 583.
* **The 6 h smoke test shows nothing.** The same changes gave 128 iterations for 2025, against
  126 before the calibration (22 Sep).
* **The solution is clean.** Recomputed from the solved network, every nodal balance and
  every Link/Generator bound holds to ≤ 1.0e-3 MW (script `tmp/ablation/residuals.py`).
  * This run's residuals are ~3× the baseline's, and uniformly so over every carrier: 54
    against 18 MWh summed over the year. They are not concentrated on the seeds or on any
    calibrated component.
  * The residual of 27 in the Gurobi log therefore sits on the large-RHS aggregate rows
    (annual CO₂ and TIMES caps, RHS up to 1e9), where it is ≤ 3e-8 relative.

### 12.5 Ablation

Three 2025 solves ran on `batch` (`nic5-w027`) through `tmp/ablation/solve_variant.py`. That
driver runs `scripts/solve_network.py` unchanged, with the production rule's snakemake
object and the cluster overlay.

| Variant | Network | Rows | Fingerprint | Iterations | Work units | Time | Objective |
|---|---|---:|---|---:|---:|---:|---|
| production | this run | 27 507 523 | `0x325a1b4e` | 489 | 8 470 | 9 048 s | 3.42830698e11 |
| control | this run's 2025 input, unchanged | 27 507 523 | `0x325a1b4e` | first 25 identical | | | |
| noseed | minus the six sub-MW `nuclear-2025` seeds | 27 402 398 | `0x7bc1e79f` | 326 | 4 880 | 6 115 s | 3.42831080e11 |
| nocal | seeds kept; calibration reverted (24 Sep capital costs, efficiencies and loads) | 27 507 523 | `0x6394296e` | 365 | 4 764 | 5 175 s | 3.52212626e11 |
| 24 Sep baseline | no seeds, no calibration | 27 402 398 | | 300 | 3 936 | 4 401 s | 3.52212805e11 |

* **The driver builds the production LP.** The control has the same fingerprint as
  production.
* **The solve is deterministic.** The control's first 25 barrier iterations match
  production line for line, on the same CPU (EPYC 7542). It was therefore cancelled at 15:59
  instead of repeating the known 489 iterations.
* **`noseed` has the baseline's row count** (27 402 398), with this run's coefficients.

The variant networks come from `tmp/ablation/build_variants.py`. For `nocal` it restores:
* 100 link capital costs (pipelines, DC, distribution grid, gas boilers);
* 11 AC-line capital costs;
* 10 rooftop-PV capital costs;
* 16 distribution efficiencies (0.95 → 0.97);
* the 8 HV industry loads, folded back to LV;
* 7 AC-bus base-load series (× 0.97/0.95).

Everything else that differs from the 24 Sep solved network was checked, and none of it is an
input difference:
* the marginal-cost noise of `noisy_costs`;
* the AC-line x/r/b that the iterative solve rewrites;
* `p_nom_max` net of existing capacity;
* `p_max_pu` values below `clip_p_max_pu`.

**Checks on the variants.**
* `nocal` reproduces the baseline objective to 5e-7 relative. `noseed` reproduces this run's
  objective to 1e-6.
* The six seeds therefore do not change the solution. The two variant networks are the
  intended two-by-two.

**The 2025 barrier iterations, as a two-by-two** (in brackets: work units):

| | no seeds | six seeds (`bbc9450e`) |
|---|---:|---:|
| **24 Sep costs** | 300 (3 936), baseline | 365 (4 764), `nocal` |
| **calibrated costs** | 326 (4 880), `noseed` | **489 (8 470)**, this run |

**Reading.** Each change slows the solve on its own. Together they slow it by more than
the sum of the two:
* The seeds add 65 iterations with the 24 Sep costs, but 163 with the calibrated costs.
* The calibration adds 26 iterations without seeds, but 124 with them.
* Together: +189 iterations and × 2.15 in work units. Adding the two separate effects
  would predict +91 iterations and × 1.45.

**How much weight each cell can carry.**
* Each cell is a single deterministic draw, and §12.4 showed that cost-only changes can move
  the count by a factor of three.
* Both one-change effects, however, point the same way in both rows and both columns.
* The largest effect, the seeds under the calibrated costs, is also the one the degenerate
  structure of §12.3 predicts.

### 12.6 A related hazard from `bbc9450e` for 2030–2050

**The mechanism.** `add_brownfield` has two rules for the `XX nuclear-2025` links:
* it keeps them extendable in every later horizon, with `p_nom_min` = the previous
  `p_nom_opt` (lines 139–148);
* since `bbc9450e`, nuclear is exempt from the `threshold_capacity` cleanup.

Together, these carry the 2025 barrier's rounding dust into 2030 as lower bounds:

| Link (2030 input) | p_nom = p_nom_min (MW_th) | extendable |
|---|---:|---|
| FR nuclear-2025 | 4.07e-7 | yes |
| GB nuclear-2025 | 4.93e-7 | yes |
| NL nuclear-2025 | 1.97e-6 | yes |
| LU nuclear-2025 | 2.13e-4 | yes |
| BEWAL / BEVLG / DE nuclear-2025 | 0.031 / 0.061 / 0.031 | no (the intended seeds) |

**The effect on the 2030 LP.** Its RHS range now starts at **4e-7**, against 3e-5 in the
24 Sep 2030 LP. That is two more orders of spread (4e-7 … 1e9). This is precisely what
`threshold_capacity: 10` was restored to prevent on 22 Sep ("a 17-order spread of variable
bounds" in `scen_realiste_nobnd30` 2050).

**Why it matters less here.** It is four links, not the 1 278 near-zero components of that
failure. The extra rows keep the structure 2025 already has: extendable nuclear near zero
inside a must-run band.

### 12.7 Fix applied mid-run (user decision, 15:52)

**The code change.** In [`scripts/add_brownfield.py`](../../scripts/add_brownfield.py), a
carried `nuclear-2025` option whose previous `p_nom_opt` is below `NUCLEAR_DUST_MW = 1e-3`
MW_th restarts at `p_nom_min = p_nom = 0`.
* The link stays in the network, so it remains an investment option.
* The seeds (0.031 / 0.061 MW_th) are above the cut and keep their size.

**The test.** `test/test_nuclear_seed_threshold.py::test_brownfield_restarts_nuclear_dust_from_zero`
fails on the previous code and passes with the fix.

**The restart.** Only 2030 had to be redone; 2025 was kept.
1. At 15:55 I stopped the hmem orchestrator and cancelled its 2030 job, which had been
   iterating for ~7 min. The diagnostic solves were left running.
2. I set aside the 2030 input built with the dust as
   `tmp/ablation/y2030/base_s_adm___2030_brownfield_dust.nc`, and its aborted solver log as
   `tmp/ablation/y2030_solver_aborted_dust.log` (both on NIC5).
3. I pushed the file and relaunched on hmem at 15:57. The dry-run had 6 jobs.

**Result on the 2030 LP.** The rebuilt 2030 input has FR, GB, NL and LU `nuclear-2025`
at `p_nom = p_nom_min = 0`, still extendable. The 2030 LP statistics:

| 2030 LP | Rows | RHS range | Bounds range | Fingerprint |
|---|---:|---|---|---|
| 24 Sep baseline | 28 462 372 | [3e-05, 1e+09] | [1e-01, 3e+09] | `0x61b68efd` |
| with the dust (aborted) | 28 383 539 | **[4e-07, 1e+09]** | [1e-01, 1e+09] | `0x3762c085` |
| after the fix | 28 383 539 | [1e-04, 1e+09] | [1e-01, 1e+09] | `0xc27099e2` |

The fix changes coefficients only, not the LP size. The spread is now narrower than in the
24 Sep baseline.

### 12.8 Conclusion

**Answer to the question.** No change introduced numerical difficulty in the usual sense:
* no "Numerical trouble";
* identical coefficient ranges and solver settings;
* a solution that holds every balance and bound to 1e-3 MW.

**What slowed the 2025 solve** is two changes of 29 September, interacting:
* **`bbc9450e`:** three extendable nuclear options (GB, LU, NL) that end at zero inside a
  must-run band, plus three fixed 0.03–0.06 MW plants. The 12–13 September batch had the
  same six seeds and solved normally with its costs.
* **The network-cost calibration:** it adds no rows and changes costs only.

Neither change is wrong. Their combination doubled the barrier work of 2025. In 2030 the
fixed chain was faster than the baseline: 205 iterations against 266.

**`bbc9450e` also had a real defect, now fixed (§12.6–§12.7).** It carried the 2025 rounding
dust into 2030 as lower bounds.

**Options to recover the 2025 solve time.** None is applied; each changes the LP and needs
a re-run.

1. **Give the six seeds `p_nom = 0` instead of 0.01 MW_e, keeping the links.** They are
   investment options from 2040 on (`extendable_nuclear_links`), so they need to exist,
   but not with capacity. Zero-capacity fixed links are removed in presolve. This needs
   a change in `_keep_existing_capacity` and a check that `add_BEWAL_nuclear` still finds
   the links.
2. **Drop 2025 from `extendable_nuclear_links`.** No plant can be built by 2025, and
   FR/GB/NL/LU `nuclear-2025` end at zero in every run looked at. This removes the four
   degenerate extendable options from the 2025 LP. It is a scenario choice, not a fix.
3. **Solver:** `FeasibilityTol 1e-5`, the value PyPSA-Eur's `gurobi-fallback` uses. It
   shortens a primal tail, but it changes tolerances relative to every earlier run.

## 13. Addendum 2026-09-30: gas plants with capture, the NoCCSCCGT sensitivity, and a correction to R1

Written while preparing the next cabinet batch (see
[`2026-09-30_cabinet_batch_20260930_2010_1h.md`](2026-09-30_cabinet_batch_20260930_2010_1h.md)).
The numbers come from the three solved central trees. Scripts are in that log's §10.

### 13.1 Walloon CCGT with capture is small in this run

BEWAL, electrical capacity `p_nom_opt × efficiency` (MW_e) and output (TWh_e):

| run (TIMES file) | carrier | 2030 | 2040 | 2050 |
|---|---|---:|---:|---:|
| 13 Sep batch (`260911`) | CCGT | 1 740 / 6.67 | 2 831 / 11.56 | 2 323 / 1.89 |
| | CCGT CC | 0 | 707 / 4.37 | **2 172 / 9.17** |
| | urban central gas CHP CC | 0 | 0 | 409 / 1.58 |
| 24 Sep (`260923`) | CCGT | 1 740 / 6.12 | 3 134 / 12.11 | 2 626 / 2.06 |
| | CCGT CC | 0 | 141 / 0.84 | **3 416 / 8.95** |
| | urban central gas CHP CC | 0 | 0 | 482 / 1.34 |
| **29 Sep, this run** (`260923`) | CCGT | 1 740 / 6.37 | 3 042 / 11.75 | 2 534 / 2.20 |
| | CCGT CC | 0 | 551 / 3.26 | **551 / 1.33** |
| | urban central gas CHP CC | 0 | 0 | 449 / 1.26 |

CO₂ captured on Walloon gas plants: 1.44 / 3.71 Mt in 2040 / 2050 (13 Sep), 0.28 / 3.51
(24 Sep), **1.07 / 1.01** (this run).

**Why it collapsed in 2050.** The 2050 Walloon and Flemish nuclear are back at 3 GW each
(`bbc9450e`). The 24 Sep run had them at the 1.03 / 1.0 GW retrofit and filled the gap
with 3.4 GW of CCGT CC (§7, and R1 of the 24 Sep log). The CC fleet here is the 551 MW_e
built in 2040, carried to 2050 and run at ~28 % load. No CC plant is added in 2050.

> **Incomplete, corrected 1 Oct.** Nuclear explains the step from 24 to 29 Sep. It does not
> explain the step from **13 Sep**, which also had 3 GW of nuclear in 2050 and built
> 2.2 GW of CC. That step is the CO₂ storage correction (lever A). Disposal goes from 78 to
> 348 €/t, so CC's short-run cost doubles (85 → 176 €/MWh_e). With 13 Sep's CO₂ and disposal
> prices, the 2050 candidate in this run's network would recover about 215 % of its capex,
> against 92 % as solved. See the batch log
> [`2026-09-30_cabinet_batch_20260930_2010_1h.md`](2026-09-30_cabinet_batch_20260930_2010_1h.md)
> §11.7.

**The figures sent to the SPW are superseded.** J. Simon's reply of 29 Sep on the new CCGT
permit ("1,9 GW en 2030, 3,5 GW en 2040 et 4,5 GW en 2050 (dont 2,6 GW avec captage) … 7, 17
et 12 TWh") reproduces the **13 Sep batch**: 1 740 + 178 OCGT; 2 831 + 707; 2 323 + 2 172 +
409 CHP CC. The current central says, for 2050: 2.5 GW of unabated CCGT producing 2.2 TWh,
and 1.0 GW of gas plant with capture producing 2.6 TWh. The unabated fleet is a backup
fleet, not a baseload one. Worth a correction before it is quoted in a permit opinion.

### 13.2 Will the NoCCSCCGT sensitivity change anything?

**What TIMES removes** (`scen_sensibilite_central_noccsccgt_260929_2909.vd` against the
central `scen_central_v01_260929_3009.vd`):
* `ETSTP_Retrofit_CCGT_CCS_E12_N` and `…_E13_N`, the capture retrofit of the two recent
  CCGTs, 0.51 + 0.51 GW from 2040, ≈ 10 PJ of activity each;
* the new post-combustion plant `ETSTP_CCGT-CCS_PostC_GAS_N`.

The two recent units then run unabated, 0.87 GW each (`ETSTP_CCGT_exist_E12/E13_N`).
TIMES-WAL has no gas-CHP-with-capture process in the solution.

**What PyPSA would lose, on this run's numbers:**
* about 1.1 Mt/a of capture in 2040 and 1.0 Mt/a in 2050;
* 3.3 TWh_e (2040) and 2.6 TWh_e (2050) of firm low-carbon output.

That is a real but moderate change: about a quarter of what the 13 Sep or 24 Sep baselines
would have implied (3.5–3.7 Mt/a in 2050). In 2040 the output shifts to unabated CCGT at
the ~150 EUR/t Walloon CO₂ price. In 2050 it has to come from PV, storage and a higher
carbon price, not from imports: the one-way import cap already binds in 2030, 2040 and
2050 (§11 level 4), so moving the capture to Flanders and importing the power is closed.

**The honest answer is "less than in TIMES, and mostly in 2040".** Two things can move it
before tonight's numbers exist:
* the next central uses the 30 Sep TIMES file and the foreign-nuclear corridor of the batch
  log §3. Less French and British nuclear in 2040–2050 raises import prices, which makes
  domestic CC more attractive;
* the NoCCSCCGT export was built on the **pre-final** central. In 2025 it is identical to
  the RetardNucleaire and biomethane exports and differs from the final central in 405
  flows. So the difference between the two TIMES files is not purely the CCS switch (batch
  log §2.2).

**PyPSA formalisation.** Two `potential:BEWAL:<carrier>:p_nom_max = 0` rows per horizon,
for `CCGT CC` and `urban central gas CHP CC`, in `config/scenarios/scen_noccsccgt.csv`.
* Industrial capture is kept, as agreed on 29 Sep ("on maintient bien le CCS sur process").
  That covers process emissions CC, gas / solid biomass for industry CC, SMR CC and biomass
  CHP CC.
* Flanders, Brussels and the neighbours are unchanged, as in every other sensitivity.

### 13.3 Correction to R1: the foreign "rebuild" is forced, not chosen

R1 reads the 49 GW of French new build in 2030 as the optimiser's choice, with no
build-rate limit. **It is forced.**
* The central caps file, `data/walloon/agg_p_nom_minmax_demande_haute.csv`, carries
  `legacy-unreviewed` rows with the foreign nuclear figures in the **min** columns:
  * FR ≥ 61 761 MW in 2030 and ≥ 62 907 MW from 2040;
  * GB ≥ 5 510 MW in 2030 and ≥ 13 236 MW from 2040;
  * NL ≥ 486 → 243 → 0 MW.
* `add_CCL_constraints` only adds a floor for a group that has extendable links. The rows
  were therefore inert on 24 Sep, when the 10 MW cleanup had deleted the FR/GB
  `nuclear-2025` options. They bind as soon as `bbc9450e` keeps those options: this run's
  61.8 / 62.9 / 62.9 GW (FR) and 5.5 / 13.2 / 13.2 GW (GB) are exactly the floors.

**The floor was what kept France realistic.** The model's existing French fleet retires on
38–41-year lifetimes: 39.4 GW in 2025 (real fleet about 63 GW), 13.1 GW in 2030, 6.2 GW in
2040, 0 in 2050. A max-only cap would therefore collapse French nuclear in 2030. The fix is
a reviewed **min/max corridor** from national plans, not a ceiling. It is implemented for
the next batch (batch log §3). The 2025 base-year shortfall is left as found and is
recorded there.

### 13.4 Is the calibration replicable for the next runs? One hole, now closed

The calibration lives in three places. All three reach every scenario:
* the base config: `sector.network_calibration`, `transmission_efficiency`,
  `gas_distribution_grid_cost_factor`;
* the global tables: `discount_rates.csv` (3.5 % for network assets) and
  `transmission_cost_overrides.csv` (ALEGrO, CO₂ trunks);
* the code (the HVDC twin fix).

**The one exception was the scenario-specific cost files.**
* A scenario with an override (`config/scenarios/<name>.csv`) reads its own
  `custom_costs_<name>.csv`. Those copies were seeded once, on 12 Sep, and the patcher
  never adds rows. So `custom_costs_scen_retardnucleaire.csv`, the two realiste copies and
  the six `scen_nuctip_*` copies had **no** `electricity distribution grid` (620 €/kW) and
  **no** `HVAC overhead` (450 / 408 / 372) row. They would have run on technology-data's
  668 €/kW and the DEA line cost.
* They also still had the 25-year electrolysis lifetime (10 years since 24 Sep).
* `--check --all-scenarios` reported it; `--check` alone does not look at scenarios.

Fixed on 30 Sep: `--write --all-scenarios` now rebuilds each copy from the central file
before applying the overrides. `test_scenario_copies_have_the_central_structure` fails if
a copy ever drifts again. No solved run was affected: the calibration postdates every
scenario-specific run.

**Reporting:**
* `network_cost_report.py` and `bill_harmonisation.py` now run inside `nic5.sh
  postprocess` for every scenario of a batch; before, only by hand.
* The ClimAct *Distribution* / *Transport* segments in the Explorer are still the
  uncalibrated ones: `plot_cost_segments.py --network-costs calibrated` fixes the chart,
  not the Explorer CSVs.

**What the cabinet was told on 29 Sep, against what is implemented:**
* J. Simon's reply quoted "529 €/kW … revu à la hausse (autour de 650 €/kW). Ces montants
  combinent bien électricité et gaz". The implemented value is **620 €/kW**, up from 668
  (technology-data), and it is **electricity only**.
* Gas distribution is a separate fixed block (282 M€/a, CWaPE 2025) plus a boiler charge
  of ≈ 5 €/kW_th/a (factor 0.12). The old chart's *Distribution* bar did mix in a ClimAct
  gas slice; that is what Antoine Dubois spotted.
* The calibrated 2030 Walloon electricity-distribution requirement is 800 M€ (L1 + L2 + L3
  + meters + PV hosting), against CWaPE's 2029 authorised revenue of 981 M€, which also
  contains losses, PSO, the road-use fee and "other" (≈ 189 M€). Like for like, 800 vs
  ~792 M€.
* Worth sending that correction with the next results.

