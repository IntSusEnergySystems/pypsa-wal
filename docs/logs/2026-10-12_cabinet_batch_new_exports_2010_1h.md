# Cabinet batch 2 — ICEDD's 9 Oct TIMES exports (1 h, weather 2010)

**Status (13 Oct 2026, 07:30): DONE. 8 of 8 runs solved (32 of 32 horizons optimal, NIC6 + NIC5), landed, post-processed and published on 13 Oct (§4, §7). Critical review §5.**

Operator: Claude desktop agent on the office computer, on S. Quoilin's instruction ("relaunch the previous batch with the
latest `.vd`; NIC6 as main resource, a few runs on NIC5; when all runs are done, the whole post-processing with upload;
solve the problems, report them and the decisions here").

**Predecessor:** [`2026-10-10_cabinet_batch_nuc3_nuc4_2010_1h.md`](2026-10-10_cabinet_batch_nuc3_nuc4_2010_1h.md) (the
"10 Oct batch"). Read its §9.1 (what NIC6 needed) and §11 (critical review) first: this batch changes the TIMES side only,
so every PyPSA-side finding of that review (capture cap, Tihange 1 restart, F1–F14) still applies.

---

## 1. Goal and what changed

In the 10 Oct batch the S2 trio and `scen_noco2cap` ran on their S1 counterparts' exports (placeholders) and the S1 trio on
the 2 Oct exports. ICEDD has since delivered six exports (S3 `test/scenarios/times_20261009_*`, uploaded 11 Oct 22:03–22:11).
This batch re-solves every scenario that has a newer export. **The PyPSA code and parameters are unchanged** (HEAD
`c31a96f1` only adds ICEDD's `config/central_4GW.csv`); only the `.vd` and the three files extracted from it differ.

| scenario | `.vd` in the 10 Oct batch | `.vd` now (`*_261009_0910.vd`) |
|---|---|---|
| `scen_central` | `scen_central_v01_261002_0210` | `scen_central_v1_3gw` |
| `scen_biomethane_industrie` | `…biomethane_industrie_v01_261002_0210` | `scen_central_v1_3gw_biomethane` |
| `scen_noccsccgt` | `…central_noccsccgt_261002_0210` | `scen_central_v1_3gw_no_ccs_ccgt` |
| `scen_nuc4gw` | S1 central (placeholder) | **`scen_central_v2_4gw`** (own export) |
| `scen_nuc4gw_biomethane_industrie` | S1 biomethane (placeholder) | **`scen_central_v2_4gw_biomethane`** |
| `scen_nuc4gw_noccsccgt` | S1 noccsccgt (placeholder) | **`scen_central_v2_4gw_no_ccs_ccgt`** |
| `scen_noco2cap` | S1 central (placeholder) | `scen_central_v1_3gw` (still no export of its own) |
| `scen_test_lowccs_ptx` | S1 central, by design | `scen_central_v1_3gw`, by design |
| `scen_realiste`, `scen_retardnucleaire` | 30 Sep / 2 Oct exports | **unchanged, not re-run** (decision D3) |

## 2. Decisions (taken without asking, as instructed)

* **D1. Wiring (§5b of the 10 Oct log).** The six `.vd` were fetched to `/sylvain/mount/pypsa-wal-data/times/`, symlinked into
  `data/walloon/` with the S3 mtime, and `extract_times_softlink_values.py --write` was run for each (new files
  `times_{pv_rooftop_share,industrial_capture}_scen_nuc4gw*.csv`; the three S1 files were overwritten, the old ones are in
  `…/batch_20261012_scripts/side_before/`). The blocks of the eleven scenarios that follow these exports (the eight of the batch
  plus the twins `scen_central_6h`, `scen_central_2013`, `scen_noccsccgt_route`, so that no block mixes an old export with the
  new side files) now name the new `.vd`. The `PLACEHOLDER` comments are gone, except for `scen_noco2cap`. `BATCH_VD`,
  `PLACEHOLDER_OF` and `test_s2_block_mirrors_s1` of `test/test_cabinet_batch.py`, the push filter of `cluster/config.sh`, and the two
  re-extracted rooftop figures of `test/test_rooftop_floor.py` were updated. `pytest test -q`: 732 passed, 1 skipped;
  `build_common_parameters.py --check --all-scenarios`: CHECK PASSED.
* **D2. What the new exports changed in the soft-link inputs** (`extract_times_softlink_values.py`):
  * `limit_twh` (Walloon electricity import, `Transfo_Imp`) is **2.94 / 6.47 / 10.0 TWh in all six exports**, as before: the blocks keep it.
  * The industrial capture floor (kt/a, 2035 / 40 / 45 / 50) is 2 521 / 4 147 / 5 147 / 4 814 (S1 central; 2 Oct: 4 145 in 2040),
    4 285 / 5 239 / 4 586 for the S2 central, 5 160 / 5 363 for S1 noccsccgt, 5 134 / 4 877 for S2 noccsccgt. **Every floor is under
    the 6 000 / 8 000 kt capture cap** (the solve aborts before Gurobi otherwise).
  * Rooftop PV floor, central: 11.097 GW (2040) and 11.979 GW (2050), against 11.033 and 12.136 in the 2 Oct export; S2 central 80–82 % of TIMES PV
    is rooftop in 2040–50. All far below the 46 GW potential. The "two share conventions disagree" warning of the extractor is the
    known one (it appeared on every export since 11 Sep).
  * The process-emissions load of the 2025 / 2030 / 2040 / 2050 horizons is the same to 0.1 % in all six exports (4 411.6 / 3 946.1 / 3 875–3 886 / 3 880–3 891 kt/a),
    so the load of `custom_potentials*.csv` needs no change.
  * The biogas bound of the ICEDD message (`BWBIOGAZ100`, `VAR_Act` 14.40 / 22.64 PJ in 2040 / 2050) is identical in the new central.
* **D3. `scen_realiste` and `scen_retardnucleaire` are not re-run.** They have no newer export and nothing else changed, so a re-solve would
  reproduce the 10 Oct trees (same inputs, same code). Their 10 Oct trees stay in `results/walloon/` and stay published
  (20261010). The eight others were re-prepared and re-solved. The comparison report therefore mixes two vintages for these two
  internal runs; the report must say so.
* **D4. The S2 nuclear pins are kept as generated (central + 962 MW), not replaced by ICEDD's new `config/central_4GW.csv`.**
  ICEDD's file pins BEWAL `nuclear-all` min = max at **2 070 / 2 750 / 4 000 MW** in 2040 / 2045 / 2050; ours are
  **1 962–1 992 / 2 712 / 3 962**. Evidence from the new S2 export (`VAR_Cap`, RW): the retrofit fleet is **2.007 GW** from 2040
  (Tihange 3 1.045 + Tihange 1 0.962), plus 0.5 + 0.25 GW new in 2045 (2.757 GW) and 1.0 + 1.0 GW in 2050 (**4.007 GW**). So ICEDD's
  2 745 and 4 000 are TIMES's figures rounded; **2 070 in 2040 looks like a transposed 2 007**. Taking it literally would force
  78 MW of new nuclear at 9 500 €/kW in 2040 that TIMES does not build. The generated pins keep "S2 − S1 = Tihange 1 alone" (the S1 pins are 1 030 / 1 750 /
  3 000, TIMES's S1 are 1.045 / 1.816 / 3.045), and the 2050 difference to TIMES is 45 MW. **To confirm with ICEDD**; if they want 4 000 MW
  in 2050 exactly, it is `make_nuc4gw_scenarios.py` (10 Oct log §6).
* **D5. Placement.** Cabinet scenarios, **all six on NIC6** (32 Gurobi threads, so that every S1/S2 pair has the same solver path,
  which the 10 Oct review F8 had to prove); `scen_noco2cap` and `scen_test_lowccs_ptx` (internal) on **NIC5** as the comparison
  sample. `scen_realiste` / `scen_retardnucleaire` are not re-run (D3).
* **D6. NIC6 memory.** `cluster/config_cluster_nic6.yaml`: `mem_mb: 60000 → 75000`, `cpus: 32 → 40` (1 900 MB per core gives
  76 000 MB; `sbatch --test-only` accepts it), Gurobi `threads` stays 32. The 10 Oct solves reached 99 % of 60 GB (§11 F9 of the 10 Oct log).
  The solve script does not read `snakemake.threads` (checked), so the extra 8 cores only buy the memory.

## 3. Pre-flight (12 Oct, office computer)

| check | result |
|---|---|
| branch / tree | `development_plan` at `c31a96f1` (= origin); local edits: the scenario blocks, tests, `cluster/*`, `config/pypsa2html.yaml`, `run_from_office_computer.md` (head record `/sylvain/mount/pypsa-wal-data/batch_20261012_scripts/batch_20261012_head_at_launch.txt`) |
| code versions | TIMES_PyPSA `c6f93e2` (main = origin), pypsa2html `c306378` (12 Oct: frees evicted networks, summaries, `compare`) |
| host | `/` 15 GB free (68 %), `/home` 29 GB, `/sylvain/mount` 151 GB free (47 %); `check_host_health.sh` flags "no VPN" only (on campus, `ssh nic5` and `ssh nic6` answer) |
| `pytest test -q` | 732 passed, 1 skipped (after D1) |
| archive | the eight trees moved to `results/_archive_batch_20261010` (local, on the big disk) and `pypsa-wal-archive/batch_20261010` (NIC5, NIC6) |
| `prepare` dry run | **240 jobs**, only `build_wallon_demands` and its dependants, `prepare_sector_network`, `add_existing_baseyear`: no `retrieve_*`, cutout or profile rule |
| NIC6 queue | saturated by other users: 22 of 2 304 cores idle; `sbatch --test-only` quotes 32 and 40 cores starting between 01:41 and 02:26 on 13 Oct |

(Run record follows.)

## 4. Run record

### 4.1 Launch (12 Oct, office computer)

| step | when | result |
|---|---|---|
| `prepare`, eight scenarios | 22:27–22:40 | **240 jobs, 13 min, exit 0, cgroup peak 3.9 GB** (8 GB cap). `Process-emissions load at BEWAL: 4411.62 kt/a` in all eight 2025 logs; each `build_wallon_demands` log names its own `*_261009_0910.vd` |
| push | 22:41–22:42 | NIC5 and NIC6 in parallel, 1 min; the six `.vd` present with the same sizes on both |
| cluster dry run | 22:43 | NIC6 (six scenarios): 24 solves + 18 `add_brownfield`; NIC5 (two): 8 + 6; nothing else planned |
| `solve` | 22:43 | NIC6: orchestrator pid 1258505, **40 cores / 75 000 MB** per solve, 6 h limit; NIC5: pid 125556, 16 cores / 80 GB, 12 h |

NIC6 was almost full (other users, multi-day jobs): the first solve started at once (node `nic6-w012`), the others queued.
Watchers: `batch_20261012_scripts/watch_state.sh` (job changes), `probe_both_b2.sh` (health probe).

### 4.2 Outcome of the solves (read from `sacct`, the orchestrator logs and the solver logs, 13 Oct)

**NIC6 (six cabinet runs): 24 of 24 horizons optimal, 42 of 42 jobs COMPLETED, no failed, cancelled or OOM-killed job**
(`cluster/logs/orchestrate_nic6_final_20261012.log`, `sacct_nic6_20261012.md`). All six solves started within 50 minutes of the
submission although the cluster was almost full. The `add_brownfield` jobs (9 cores, 30 min limit) did not delay any chain.

| scenario | cluster | 2025 / 2030 / 2040 / 2050, min | chain, min | peak `MaxRSS`, GiB (request 73.2) |
|---|---|---|---:|---:|
| `scen_central` | NIC6 | 84 / 36 / 28 / 35 | 183 | 54.6 |
| `scen_nuc4gw` | NIC6 | 80 / 33 / 31 / 29 | 173 | 53.9 |
| `scen_biomethane_industrie` | NIC6 | 163 / 50 / 40 / 33 | 286 | 56.5 |
| `scen_nuc4gw_biomethane_industrie` | NIC6 | 118 / 35 / 28 / 38 | 219 | 58.0 |
| `scen_noccsccgt` | NIC6 | 79 / 31 / 44 / 38 | 192 | 58.2 |
| `scen_nuc4gw_noccsccgt` | NIC6 | 82 / 28 / 29 / 29 | 168 | **59.0** |

* **The memory change of D6 was needed.** Seven of the 24 NIC6 solves peaked at 56.5–59.0 GiB. The old request was 58.6 GiB: with it
  `scen_nuc4gw_noccsccgt` 2050 (59.0) and `scen_noccsccgt` 2040 (58.2, at 99.3 %) would have been killed or have run on luck. At 75 000 MB the
  worst solve uses 81 %. Keep `mem_mb: 75000` / `cpus: 40` for NIC6 (`run_from_office_computer.md` §3b updated).
* **Barrier:** `Crossover 0`, no "Numerical trouble" or "Infeasible" line in any solver log.
* **Code paths of runbook §5.7 (probe `runbook-checks`, all started horizons):** process-emissions load 3 946 / 3 875 / 3 880 kt/a,
  `Capped BEWAL CO2 capture at 2000 / 6000 / 8000 kt/a`, the industry floor and the rooftop pin of **each scenario's own export**
  (central: `≥ 4147.2` / `4813.5` kt/a, `≥ 11097` / `11979` MW), and the Tihange 1 offer in the three S2 trees.

### 4.3 NIC5 against NIC6 (the comparison asked for)

`scen_test_lowccs_ptx` and `scen_noco2cap` ran on NIC5 (16 Gurobi threads, 80 GB); `scen_test_lowccs_ptx` is the central LP until 2040 and
`scen_noco2cap` until 2025, so they can be set against the NIC6 central.

| | NIC5 `scen_test_lowccs_ptx` | NIC6 `scen_central` |
|---|---|---|
| 2025 objective (`Optimal objective`) | 3.35336274e11 | 3.35336219e11 (**1.6e-7** apart) |
| 2030 objective | 3.72882880e11 | 3.72882661e11 (**5.9e-7** apart) |
| Barrier time 2025 / 2030 / 2040 / 2050 | 10 765 / 3 552 / 3 172 / 2 775 s | 4 855 / 1 948 / 1 503 / 1 887 s |
| ratio | 2.2× / 1.8× / 2.1× / 1.5× | |
| peak memory | 32 GiB of 78 (41 %) | 54.6 GiB of 73.2 (75 %) |

NIC6 with 32 threads is about **2× faster** on the same LP; the objectives of the identical LPs agree to 1e-6, as on 10 Oct (F8 of its log). The
two NIC5 chains took 6.9 h (queue wait included) against 3–5 h for the NIC6 chains.

### 4.4 Landing and publication (13 Oct)

* **Landing** (`land_all_b2.sh`, one scenario at a time, each step capped): `pull`, 4/4 optimal, `postprocess` (11 steps, 7 min, peak 4.7 GB),
  `ptx_report` (3.2 GB), `review_run` (5.2 GB), `check_heat_profile_fidelity` (3.0 GB). The network-cost files were present (3 of 3) in every
  tree, because `postprocess` now produces them itself (T1 below).
* **`review_run.py`:** `scen_central` PASS 170 / WARN 15 / **FAIL 9, the nine known foreign-nuclear rows of F11** (NL, GB, FR, DE), same as 10 Oct.
  The heat load closes to 2e-6 TWh.
* **Phase A** (ClimAct extraction, cost-segment plot, S3 upload), 04:02–04:36 for the six: each Explorer set **53 files, none empty**
  (`times-pypsa__<s>-2010-1h__20261012`; no `-times-placeholder` any more except `scen_noco2cap`).
* **Phase B** (pypsa2html at cache 4, Sankeys, indicators, hub, rsync, S3 re-sync), 04:40–05:05 for the six: **91 pages in 2 min each, 0 failed**,
  HTTP 200 on hub, report and Sankey for all six. `scen_test_lowccs_ptx` A+B 05:47–05:52, same result.
* Stamp pinned to **20261012** (batch launch day). The 10 Oct pages (`…_20261010`) stay online for comparison.

### 4.5 What went wrong, and what was done

* **T1. `postprocess` and the network-cost files (F10 of the 10 Oct review).** Fixed in `cluster/nic5.sh` / `cluster/config.sh`: the two scripts now run
  through a new `LOCAL_PYTHON` (plain Python in the `pypsa-eur` env), never `LOCAL_RUN`, and `postprocess` **dies** when one of the three CSVs is missing.
  Verified: 3 of 3 in the seven landed trees without any manual step.
* **T2. The desktop app crashed twice during this run** (`coredumpctl`: SIGILL in `claude-desktop`, 13 Oct 05:47 and an earlier one on 12 Oct 17:03),
  both while heavy local steps ran (the ClimAct extraction of `scen_test_lowccs_ptx`, 7.6 GB, with an ad-hoc analysis script of mine reading the CSVs
  at the same moment). The detached drivers survived (`setsid`), so nothing of the run was lost; the session restarted and the state was re-read from the
  cluster and the logs. From then on only one capped step ran at a time and nothing ad-hoc ran beside a driver.
* **T3. A foreground wait of mine was killed by the app crash** (exit 137); the background watchers died with the session (expected, §5 of the office guide).
  They were not re-armed: the landing driver (`land_all_b2.sh`) polls the cluster itself.
* **T4. `check_host_health.sh` says "no VPN active — NIC5 unreachable"** although both clusters answer (on campus). Cosmetic; not changed.

## 5. Results and critical review (13 Oct; scripted checks, no re-solve)

**Scope.** `review_run.py`, `check_heat_profile_fidelity.py`, `ptx_report.csv` and the solver logs of the eight new trees, set against the 10 Oct trees
(`results/_archive_batch_20261010`). Read §11 of the 10 Oct log for the PyPSA-side findings (F1–F14): they are unchanged because the PyPSA code is.
**Not done:** no re-solve, no resolution sensitivity, no TIMES-side check beyond the extraction figures of §2 D2, no read of the 20 Explorer sets in the dropdown.

### 5.1 Provenance and scripted checks

* **Code:** pypsa-wal `c31a96f1` + the uncommitted edits of §3 (nothing of the model physics); TIMES_PyPSA `c6f93e2`; pypsa2html `c306378`. Pinned env as on 10 Oct.
* **Each tree reads its own export:** the `build_wallon_demands` log of every scenario names its `*_261009_0910.vd`; the S2 trio no longer carries a placeholder banner.
  `scen_noco2cap` still reads the S1 central's export (banner and `-times-placeholder` Explorer label kept).
* **`review_run.py`:** every tree gives the same nine known FAILs (foreign nuclear aggregate rows, F11 of 10 Oct) and no new one; the `tes_se` standing-loss false positive of F10 is the same as before where it appears.
  Heat load closes to 2–3e-6 TWh in all eight.
* **Tihange 1:** BEWAL nuclear link capacity S2 − S1 = **2 950 MW_th = 962 MW_e** in 2040 and 2050 in all three S2 trees (6 110 vs 3 160 and 12 153 vs 9 202 MW_th).

### 5.2 Headline numbers


**2040** (BEWAL; capacities MW; duals EUR/t; price EUR/MWh) — new batch (12 Oct)

| scenario | cluster | capture Mt (cap) | CCGT CC Mt | capture-cap dual | national-cap dual | price mean | CCGT | CCGT CC | battery disch. | ground PV | objective bn |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `central` | NIC6 | 6.00 (6) | 0.51 | -118 | -141 | 94.8 | 3,450 | 478 | 2,917 | 6,392 | 263.74 |
| `nuc4gw` | NIC6 | 6.00 (6) | 0.00 | -20 | -32 | 90.3 | 3,433 | 0 | 2,277 | 7,056 | 263.37 |
| `biomethane_industrie` | NIC6 | 6.00 (6) | 0.51 | -118 | -141 | 94.8 | 3,453 | 478 | 2,915 | 6,337 | 263.75 |
| `nuc4gw_biomethane_industrie` | NIC6 | 6.00 (6) | 0.00 | -20 | -32 | 90.3 | 3,430 | 0 | 2,283 | 7,147 | 263.37 |
| `noccsccgt` | NIC6 | 6.00 (6) | 0.00 | -120 | -145 | 95.0 | 4,081 | 0 | 2,942 | 6,693 | 263.78 |
| `nuc4gw_noccsccgt` | NIC6 | 6.00 (6) | 0.00 | -20 | -32 | 90.3 | 3,569 | 0 | 2,256 | 6,852 | 263.41 |
| `noco2cap` | NIC5 | 5.56 (6) | 0.00 | -0 | -0 | 90.1 | 7,319 | 0 | 418 | 1,456 | 266.22 |
| `test_lowccs_ptx` | NIC5 | 5.49 (6) | 0.00 | -0 | -230 | 98.4 | 3,774 | 0 | 3,503 | 6,392 | 264.30 |

**2050** (BEWAL; capacities MW; duals EUR/t; price EUR/MWh) — new batch (12 Oct)

| scenario | cluster | capture Mt (cap) | CCGT CC Mt | capture-cap dual | national-cap dual | price mean | CCGT | CCGT CC | battery disch. | ground PV | objective bn |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `central` | NIC6 | 7.03 (8) | 0.41 | -0 | -0 | 107.0 | 2,558 | 890 | 5,611 | 13,000 | 284.72 |
| `nuc4gw` | NIC6 | 6.64 (8) | 0.20 | -0 | -0 | 105.5 | 2,542 | 446 | 3,566 | 7,479 | 284.92 |
| `biomethane_industrie` | NIC6 | 7.18 (8) | 0.26 | -0 | -0 | 106.8 | 2,561 | 572 | 5,448 | 13,000 | 284.61 |
| `nuc4gw_biomethane_industrie` | NIC6 | 6.93 (8) | 0.20 | -0 | -0 | 105.5 | 2,539 | 450 | 3,299 | 6,751 | 284.88 |
| `noccsccgt` | NIC6 | 6.13 (8) | 0.00 | -0 | -0 | 107.4 | 3,189 | 0 | 6,291 | 13,000 | 283.81 |
| `nuc4gw_noccsccgt` | NIC6 | 6.09 (8) | 0.00 | -0 | -0 | 105.7 | 2,977 | 0 | 4,341 | 9,473 | 285.14 |
| `noco2cap` | NIC5 | 6.63 (8) | 0.00 | -0 | -0 | 106.4 | 6,428 | 0 | 5,307 | 12,365 | 283.48 |
| `test_lowccs_ptx` | NIC5 | 6.92 (8) | 0.26 | -0 | -0 | 107.2 | 2,883 | 565 | 5,694 | 13,000 | 284.24 |

### 5.3 What changed against the 10 Oct batch

**Change against the 10 Oct batch** (new − old; same scenario names; S2/noco2cap were placeholders then)

| scenario | year | Δ objective bn | Δ price | Δ CCGT CC MW | Δ CCGT MW | Δ ground PV MW | Δ battery MW | capture Mt new (old) |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `central` | 2030 | +0.01 | +0.0 | +0 | +22 | +0 | +0 | 1.30 (2) (1.28 (2)) |
| `central` | 2040 | -0.00 | +0.0 | -0 | +9 | -102 | -17 | 6.00 (6) (6.00 (6)) |
| `central` | 2050 | -0.04 | +0.0 | +5 | +9 | +0 | -42 | 7.03 (8) (6.98 (8)) |
| `nuc4gw` | 2030 | +0.02 | +0.0 | +0 | +54 | +0 | +0 | 1.33 (2) (1.28 (2)) |
| `nuc4gw` | 2040 | -0.02 | +0.1 | +0 | +65 | +669 | +8 | 6.00 (6) (6.00 (6)) |
| `nuc4gw` | 2050 | -0.17 | +0.0 | -65 | +65 | +671 | +35 | 6.64 (8) (6.66 (8)) |
| `biomethane_industrie` | 2030 | +0.00 | +0.0 | -0 | +21 | +0 | +0 | 1.30 (2) (1.28 (2)) |
| `biomethane_industrie` | 2040 | +0.00 | +0.0 | -1 | +16 | -57 | -22 | 6.00 (6) (6.00 (6)) |
| `biomethane_industrie` | 2050 | -0.09 | -0.0 | -50 | +16 | +0 | -4 | 7.18 (8) (7.14 (8)) |
| `nuc4gw_biomethane_industrie` | 2030 | +0.02 | +0.0 | +0 | +54 | +0 | +0 | 1.33 (2) (1.28 (2)) |
| `nuc4gw_biomethane_industrie` | 2040 | -0.02 | +0.1 | -0 | +62 | +862 | +13 | 6.00 (6) (6.00 (6)) |
| `nuc4gw_biomethane_industrie` | 2050 | -0.14 | +0.0 | -62 | +62 | +769 | +134 | 6.93 (8) (6.95 (8)) |
| `noccsccgt` | 2030 | +0.00 | +0.0 | +0 | +23 | +0 | +0 | 1.30 (2) (1.28 (2)) |
| `noccsccgt` | 2040 | -0.00 | +0.0 | +0 | +7 | -54 | +3 | 6.00 (6) (6.00 (6)) |
| `noccsccgt` | 2050 | -0.00 | -0.0 | +0 | +7 | -0 | +6 | 6.13 (8) (6.13 (8)) |
| `nuc4gw_noccsccgt` | 2030 | +0.02 | +0.0 | +0 | +48 | +0 | +0 | 1.33 (2) (1.28 (2)) |
| `nuc4gw_noccsccgt` | 2040 | -0.01 | +0.1 | +0 | +170 | +105 | -55 | 6.00 (6) (6.00 (6)) |
| `nuc4gw_noccsccgt` | 2050 | +1.02 | +0.1 | +0 | +4 | +2,648 | +179 | 6.09 (8) (6.13 (8)) |
| `noco2cap` | 2030 | +0.00 | +0.0 | +0 | +0 | +0 | +0 | 0.00 (2) (0.00 (2)) |
| `noco2cap` | 2040 | -0.00 | -0.0 | +0 | -3 | -54 | +0 | 5.56 (6) (5.56 (6)) |
| `noco2cap` | 2050 | -0.03 | -0.0 | -0 | -3 | +166 | -9 | 6.63 (8) (6.60 (8)) |
| `test_lowccs_ptx` | 2030 | +0.01 | +0.0 | +0 | +22 | -0 | -0 | 1.30 (2) (1.28 (2)) |
| `test_lowccs_ptx` | 2040 | -0.00 | +0.0 | +0 | -7 | -102 | -16 | 5.49 (6) (5.49 (6)) |
| `test_lowccs_ptx` | 2050 | -0.04 | +0.0 | +12 | -7 | +0 | -36 | 6.92 (8) (6.87 (8)) |

### 5.4 Reading

* **The new exports barely move the PyPSA results.** For the S1 trio and the PtX test the objective changes by ≤ 0.09 bn in every horizon, capacities by tens of MW (2040: CCGT −7 to +16 MW, ground PV −102 to −54 MW, batteries −22 to +3 MW),
  and the 2040 capture-cap and national-cap duals are identical (−118 / −141 €/t). That is the expected result: the new S1 exports differ from the 2 Oct ones by a few percent on the extracted soft-link inputs (D2).
  It also confirms that the 10 Oct results of these scenarios were not a solver artefact. The same numbers on NIC6 (32 threads) as on NIC5 (16) in 10 Oct are a second confirmation (§4.3).
* **The S2 trio now has its own TIMES side, and its 2040 picture is unchanged:** CCGT CC 0 Mt in all three, capture 6.00 Mt at the cap, capture-cap dual −20 €/t (−17 before), price 90.3 €/MWh. The F1/F2/F4/F5 findings of 10 Oct hold; the cabinet's
  "CCS on CCGT active by default from 2040" is still not met in S2 and it is still a marginal route in S1 (0.51 Mt). Do not quote 2040 CCGT CC tonnages.
* **One outlier: `scen_nuc4gw_noccsccgt` 2050.** Objective **+1.02 bn**, ground PV **+2 648 MW** (6 852 → 9 473), batteries +179 MW against the 10 Oct run; the other two S2 runs move by −0.14 to −0.17 bn and +0.7–0.8 GW PV.
  The S2 export of this scenario has a different industrial floor (5 134 / 4 877 kt in 2040 / 2050 against S1's placeholder 5 160 / 5 363 before), a different rooftop floor and its own 2040 path, so a different myopic
  trajectory is the likely cause (F13: objectives of different myopic paths are not comparable at the ±1 bn level). **Not investigated further**; read the 2050 PV and battery of this run with that caveat, and do not quote
  "S2 − S1" for the no-CCS pair in 2050 until the cause is traced (§6 item 3).
* **`scen_noco2cap`** keeps the 10 Oct picture (CCGT 7.3 GW and PV 1.5 GW in 2040), now on the new central export.
* **2050 ground PV of the S1 trio is 13 000 MW**, the potential cap, as before (not an optimum).
* **Cost/price caveats unchanged:** PyPSA wholesale price about 2× TIMES's in three of four horizons (F14); `scen_realiste` is the 30 Sep base; the 2025 horizon is not a calibration.

## 6. Follow-up actions

1. **ICEDD:** confirm D4 (the 2 070 MW of `config/central_4GW.csv` in 2040 vs TIMES's 2 007; 4 000 vs our 3 962 in 2050), and the 2030 `CO2STG01` bound of 2 Mt (open since 10 Oct, §8 Q1a). Ask for dedicated exports for `scen_noco2cap`, `scen_realiste`, `scen_retardnucleaire` if they are to be re-run on the new base.
2. **Cabinet / Sylvain:** the CCS-on-CCGT lever (10 Oct F1) is still open; S2 has none in 2040.
3. **Trace the `nuc4gw_noccsccgt` 2050 shift** (+1.02 bn, +2.6 GW PV): re-solve its 2050 on the 10 Oct 2040 network, or compare the 2040 networks of the two batches.
4. `scen_realiste` and `scen_retardnucleaire` stay at their 10 Oct trees (D3); their pages are `…_20261010`, and the comparison report below includes them next to the new runs: say so when pointing anyone at it.
5. **Commit.** All edits of this batch are uncommitted (scenario blocks, tests, `cluster/*`, new side-file CSVs, the six `.vd` symlinks are git-ignored). Sylvain to review and commit; the `config/pypsa2html.yaml` and `run_from_office_computer.md` edits that were already in the tree at the start are theirs and untouched except for the NIC6 note.
6. The orchestrator logs are saved as `cluster/logs/orchestrate_nic{5,6}_final_20261012.log`; `pull` overwrites the plain `orchestrate.log`.

## 7. Published pages (internal, policy of 5 Oct; S3 `test/`, nothing sent to `prod/`)

All **HTTP 200** on hub, pypsa2html report and Sankey page; raw trees 332 files, 1.33–1.35 GB each on `s3://intervectoriel/test/pypsa_raw_results/20261012_walloon_<s>/`;
Explorer sets 53 files, 0 empty, in `test/scenarios/times-pypsa__<label>__20261012/` (Explorer dropdown **not verified** in a browser).

| scenario | pypsa.squoilin.eu | Explorer label |
|---|---|---|
| `scen_central` | https://pypsa.squoilin.eu/scen_central_20261012/ | `scen_central-2010-1h` |
| `scen_nuc4gw` | https://pypsa.squoilin.eu/scen_nuc4gw_20261012/ | `scen_nuc4gw-2010-1h` |
| `scen_biomethane_industrie` | https://pypsa.squoilin.eu/scen_biomethane_industrie_20261012/ | `scen_biomethane_industrie-2010-1h` |
| `scen_nuc4gw_biomethane_industrie` | https://pypsa.squoilin.eu/scen_nuc4gw_biomethane_industrie_20261012/ | `scen_nuc4gw_biomethane_industrie-2010-1h` |
| `scen_noccsccgt` | https://pypsa.squoilin.eu/scen_noccsccgt_20261012/ | `scen_noccsccgt-2010-1h` |
| `scen_nuc4gw_noccsccgt` | https://pypsa.squoilin.eu/scen_nuc4gw_noccsccgt_20261012/ | `scen_nuc4gw_noccsccgt-2010-1h` |
| `scen_noco2cap` (internal; banner: S1 export) | https://pypsa.squoilin.eu/scen_noco2cap_20261012/ | `scen_noco2cap-2010-1h-times-placeholder` |
| `scen_test_lowccs_ptx` (TEST) | https://pypsa.squoilin.eu/scen_test_lowccs_ptx_20261012/ | `scen_test_lowccs_ptx-2010-1h` |
| **comparison report**, 10 runs, reference `scen_central` (8 new + the two 10 Oct trees `scen_retardnucleaire`, `scen_realiste`), 23 pages, built from the summaries in 109 s / 0.2 GB | https://pypsa.squoilin.eu/compare_20261012/ | – |

The old comparison output was moved to `results/_archive_batch_20261010/compare_20261010` (still online as `compare_20261010`).
