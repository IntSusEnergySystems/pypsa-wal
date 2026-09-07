# Solve log — scen_demande_haute @ 2010, 1h (production, post-review fixes)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-05 21:53 (prepare) → 2026-09-06 15:51 (2050 solved) → 2026-09-06 ~23:30 (postprocess + S3 done) |
| Operator | opencode agent (supervised by sylvain, on explicit `status?` polling — no autonomous follow-up; see §9) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + overlay `config/scenarios.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | `development_plan` `0f9ce604` (working tree clean, up to date with `origin/development_plan`) |
| Outcome | **4/4 optimal** |

## 2. Goal of the run

First production 1h / 2010 solve of `scen_demande_haute` on the code that
includes all post-review fixes landed 2026-09-05 (commit-intent table in
§11). The overnight v2 solve
([`2026-09-04_scen_demande_haute_2010_1h_v2.md`](2026-09-04_scen_demande_haute_2010_1h_v2.md),
`c68d1474`) was invalidated the same day by five physics/config fix commits,
so its `results/` (pulled Sep 5 09:26) were **not** shipped — this run
rebuilt inputs and re-solved all four horizons from scratch.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v2_260903_0309.vd` (symlink → `/sylvain/git/TIMES_PyPSA/data/…`, present) |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` (6.2 GB, cached) |
| Snapshots | 2010-01-01 → 2011-01-01, 8760 hourly, weight 1.0 (verified on built networks) |
| Sector time resolution | `1h` (`clustering.temporal.resolution_sector`) |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `adm` (custom 3-node Belgium) |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi 13.0.2 barrier (Method 2, Crossover 0, BarConvTol 1e-5, BarHomogeneous 1, Seed 123), 16 threads |
| Key scenario overrides | per `scen_demande_haute` in `config/scenarios.walloon.yaml` (vd v2, rooftop split, agg caps, item 6a import cap, item 9) |
| Pre-flight | `build_common_parameters.py --check` PASSED |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local, 16 cores | `nic5.sh prepare`, 12/12 steps, ~40 min (21:53→~22:00 start… all targets rebuilt 21:53–21:54) |
| LP solve | NIC5 `hmem` | 16 cpus/task, `mem_mb` 100000, runtime 1440 min; 7 jobs (4 solves + 3 brownfields) |
| Post-processing (CSVs, plots) | local, 16 cores | `nic5.sh postprocess`, 10/10 steps |
| HTML report (pypsa2html) | local | built by postprocess (`html/pypsa/index.html`), published |
| Explorer CSV extraction (ClimAct) | n/a | explorer/ CSVs already staged from earlier extraction run; uploaded as-is (see §8) |

Cluster specifics: orchestrator pid 1829248 on the login node, alive for the
whole chain. `hmem` at submit: 2 mix + 1 idle node, 121 pending (all one
capped user, `AssocGrpJobsLimit` — not real contention). 2025 solve started
within ~2 min of submission (**no queue wait** — the 100 GB shared-node
sizing worked). Nodes: 2025+2030 on `nic5-w071`, 2040 on `nic5-w072`
(job 11121053).

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (prepare launch → S3 done) | ~49.5 h wall (Sep 5 21:53 → Sep 6 ~23:30), dominated by solves |
| Prepare (network build) | ~40 min local |
| Push to cluster | minutes |
| Queue wait (cluster) | ~0 (started in ~2 min) |
| Solve 2025 | job ~12.7 h (due to a delay in launching); barrier 290 it / 4815 s |
| Solve 2030 | job ~1.4 h (→ 12:25); barrier 241 it / 4957 s |
| Solve 2040 | job ~1.6 h (→ 14:06); barrier 259 it / 5176 s |
| Solve 2050 | job ~1.6 h (→ 15:51); barrier 251 it / 5467 s |
| Pull results | ~2 min transfer + diagnosis (see §9 rsync incident) |
| Post-processing + plots + pypsa2html + Sankeys + HTML publish | ~10 min local Snakemake (log stamp 23:22–23:26) + S3 upload |
| ClimAct extraction | n/a (this run) |

Runtime comparison (same scenario, 1h, Sep-4 v2 run §5: ≈4.5 h chain):
**2025 took 12.7 h here vs ~1 h/horizon there.** Barriers are comparable
(1.3–1.5 h each); the 2025 anomaly is ~11 h of non-barrier job time
(model build/export phase — unresolved, see §10). Horizons 2030–2050 match
the reference pace. The Friday fix commits (import cap, heat pinning,
nuclear inflexibility) grew the LP: 2025 now 30.9M rows / 14.6M cols
(vs smaller v2 shape — exact v2 row counts not recorded).

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size 2025 / 2030 / 2040 / 2050 (rows) | 30.9M / 39.4M / 42.7M / 43.5M (cols 14.6M / 19.1M / 21.1M / 21.7M; nnz 74.7M / 94.9M / 102.8M / 104.3M) |
| Peak RAM per solve (`*_memory.log` max) | 22.5 / 28.2 / 29.7 / 29.9 GB — all well under the 100 GB request |
| Peak RAM local phases | not separately metered; 16 GB office box stayed responsive |
| Disk footprint | `resources/walloon/scen_demande_haute` 936 MB; `results/walloon/scen_demande_haute` 1.7 GB |

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | optimal | 3.56589911e+11 |
| 2030 | optimal | 3.63803341e+11 |
| 2040 | optimal | 2.91412678e+11 |
| 2050 | optimal | 2.69026074e+11 |

All four objectives differ from the stale v2 values (3.55890314 / 3.63618342
/ 2.91120598 / 2.68575853 e+11) — expected: the fix commits changed the LP.
Local result folders:

- Networks: `results/walloon/scen_demande_haute/networks/` (md5-verified against scratch after pull, §9)
- CSVs / plots: `results/walloon/scen_demande_haute/{csvs,graphs}/` (`costs.csv`, `costs.svg`, `cumulative_costs.csv`)
- HTML report: `results/walloon/scen_demande_haute/html/index.html` → https://pypsa.squoilin.eu/scen_demande_haute_20260906/

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260906_walloon_scen_demande_haute/` |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__scen_demande_haute__20260906/` (`pypsa/` + `strategy/` + `times/` all uploaded OK) |
| Explorer display label | `demande-haute-2010-1h` (`EXPLORER_SCENARIOS` in `cluster/config.sh`) |
| TIMES vd staged | yes — `explorer/times/scen_central_demande_haute_v2_260903_0309.vd` uploaded |
| Verified in Explorer dropdown | **no** — test-env listing not checked; owner to confirm |
| **Addendum 2026-09-07 (pypsa2html trade fix).** The published Sankey showed 17.2 TWh of 2050 electricity imports against the 10 TWh item-6a cap — a report artefact, not a solve defect (pypsa2html `725333c` plugged the node residual instead of measuring cross-border branches; fixed upstream in `5793e1a`, verified by its `test_electricity_trade.py`). Pulled pypsa2html to `5793e1a`, rebuilt `html/pypsa` + hub via `--forcerun`, re-published to the same public folder, re-synced S3 (new date-stamped prefixes `20260907_walloon_scen_demande_haute` and `times-pypsa__demande-haute-2010-1h__20260907`). Rendered 2050 imports now read exactly 10.000 TWh (direct `import_export_series` check on the network agrees: import 10.000, export 2.382). Side effect of the fix, now visible: the electricity node is short ~9 TWh in 2050 (taxonomy hole, upstream question — see the fix commit message). | | |

## 9. Issues encountered and fixes

- **Stale Sep-5 results.** Local `results/` (09:26) predated five fix commits
  (11:54–21:13). Caught by comparing `git log` dates against file mtimes
  before launching. Fix: full rebuild + re-solve, not ship. Lesson recorded
  in `run_from_office_computer.md` §4 (verify `results/` not newer than HEAD).
- **No autonomous monitoring (opencode).** The agent runs only on user
  messages; "next probe in 30 min" promises made overnight did not execute
  (~13 h gap, caught by user). A cron prober + auto-land driver were built,
  tested, then **removed at the user's request** — protocol is now explicit
  `status?` polling. Documented in `run_from_office_computer.md` §5 and in
  `docs/run-review-checklist.md` ("Monitoring a run driven by an agent":
  opencode cannot follow up unattended; Cursor background agents on this
  machine could).
- **`nic5.sh pull` rsync "failed verification" on every large file.**
  Symptom: transfer ran at ~63 MB/s but all `.nc`/CSV updates were discarded
  (code 23); small files (solver logs) passed. `ssh cat` pipe of the same
  238 MB file was bit-perfect (md5 match), clearing network and disks.
  Cause: rsync delta-transfer verification failing over this path (VPN),
  not data corruption. Fix: manual
  `rsync -arhK --whole-file` of `results/`, then md5-verified all four
  `.nc` against scratch (exact match). Follow-up in §10: consider
  `--whole-file` in `nic5.sh pull`.
- **Memory-pressure notice on the office box** (`systemd-journald: Under
  memory pressure` in dmesg during pull week). No failure resulted, but heavy
  local phases (`review_run.py --full`, ClimAct extraction) should be watched
  with `free` on this 16 GB machine.

## 10. Follow-ups / pending

1. Explain the 2025 11 h non-barrier gap (job 11120848 wall 12.7 h vs
   barrier 1.34 h; horizons 2030–2050 show no such gap). Candidate: linopy
   model-build/export scaling with the new constraint set.
2. Consider `RSYNC_EXTRA=--whole-file` (or equivalent) in `nic5.sh pull` —
   delta rsync is currently unusable for multi-100 MB files on this route.
3. Confirm the scenario appears in the Explorer **test** dropdown.
4. Commit `run_from_office_computer.md` + checklist monitoring note
   (currently uncommitted: `?? run_from_office_computer.md`,
   `M docs/run-review-checklist.md`).
5. Levels 5–8 judgement items below are recorded, not closed — reviewer call.

## 11. Critical review

**Reviewed by / date:** opencode agent (scripted levels 0–4 only), 2026-09-06.
Human judgement levels (0b table filled; 5–8 verdicts provisional) pending —
**do not cite outside the team until a modeller signs off.**

**Headline counts:** `156 PASS · 26 INFO · 22 WARN · 0 FAIL` from
`review_run.py results/walloon/scen_demande_haute`
(with `PYTHONPATH=. conda run -n pypsa-eur`; bare `python` fails on
`country_converter` — run it in the env).

| Level | Verdict |
|---|---|
| 0 provenance | pass (config snapshots verified post-pull; weather block all-2010; 8760 snaps on built + solved nets; vd v2 symlink target exists) |
| 0b commit intent | table below — mechanisms present, behavioural pass/fail needs modeller observables |
| 1 solve | pass with caveats (4/4 optimal; conditioning warnings all horizons; Crossover 0 interior-point caveat; 2025 wall-time anomaly §10.1) |
| 2 TIMES soft link | pass with caveats (EV identity within tolerance per script; heat fidelity worst single gap −0.033 TWh biomass-boiler rural; coal overshoot open, R2; 2040/50 elec load −0.8/−0.9 % outside ±0.5 %, R3) |
| 3 accounting identities | pass (script closes AC/low-voltage/EV-battery; TIMES Sankey holes are the known pypsa2html mapping gaps, R4) |
| 4 constraint compliance | pass (no FAIL; agg-cap/potential checks green in script) |
| 5 realism | **provisional warn** (build rates R5; CFs/COPs all in range) |
| 6 prices / costs | not reviewed — modeller |
| 7 TIMES consistency | not reviewed — modeller |
| 8 robustness | not reviewed (single vintage: this run *is* the new reference) |

### Commit intent (level 0b)

Previous production log:
[`2026-09-04_scen_demande_haute_2010_1h_v2.md`](2026-09-04_scen_demande_haute_2010_1h_v2.md)
at SHA `c68d1474`. `git log c68d1474..0f9ce604`:

| Commit | Class | Claimed behaviour → observable in this tree |
|---|---|---|
| `0def1c0a` scale DateIn-into-baseyear rows to pin headroom | physics | IRENA forced build reconciled with agg pins → 2025 onwind 1,568 MW / rooftop 1,770 MW within pinned headroom (script PASS on potentials) |
| `99335b87` review §11: PV cost trajectory, F1/F2, F9 | docs/review | n/a (no network effect) |
| `ecbe3215` cost learning follows technology-data rate | config | Walloon overrides on tech-data trajectory → costs table regenerated (build `--check` PASSED pre-run) |
| `f948c56b` item 6a BEWAL import cap + 3 fixes | physics | BEWAL import cap present → check cap binds sensibly (modeller) |
| `a1638911` 6h verification of the four post-review changes | review tooling | n/a (verification run, not model change) |
| `0872452c` Sankey trade-plug fix in both run logs | docs | n/a |
| `0f9ce604` all issues fixes, 6h-tested | physics (bundle) | the bundle this run tests → 4/4 optimal at 1h |

### Findings

- **R1 — `coal for industry` above TIMES every horizon** (+9.8 % 2025,
  +14.0 % 2030, **+36.7 % 2040**, +23.4 % 2050). Known from the first
  reviewed run (+8/+12 %); materially worse in 2040. Action: modeller call —
  tolerance or transfer defect?
- **R2 — total BEWAL electric load −0.8 % (2040) / −0.9 % (2050) vs TIMES.**
  Outside the ±0.5 % level-2.3 tolerance while 2025/2030 pass. Action:
  trace which carrier is short before publishing.
- **R3 — TIMES Sankey mapping holes unchanged** (`pac_fe` −0.147 TWh all
  years, `vap_se`, `enc_pe` up to +8.25 TWh out with no in). Known
  pypsa2html mapping gaps, not solve defects — but the pages are now public
  (§7), so the holes are visible externally.
- **R4 — heat-fidelity total |gap| 8.15 TWh** over all (year, group, bus)
  with worst single gap −0.033 TWh (biomass boiler, rural). The sum vs max
  discrepancy was not reconciled tonight (absorber accounting suspected) —
  treat the "pass" as provisional; see
  `results/_heat_softlink_comparison/profile_fidelity_live.csv`.
- **R5 — Gurobi conditioning warnings on all four horizons**
  (`Warning: Model contains large bounds`, bounds to 5e10, RHS to 1e9).
  Tolerated per checklist level 1, recorded; re-solve with `NumericFocus 1`
  if any structural oddity appears.

### What passed cleanly

CFs in range (onwind 25–26 %, rooftop PV 11.1 %, ror 26.3 %, heat-pump COP
2.40 → 2.53); heat-pump capacity rises monotonically (no age-profile
retirement bug); EV identity within tolerance; bus balances close;
potentials/agg caps respected (no script FAIL); objectives move
consistently with the fix bundle vs v2.

### Numbers that must not be published as-is

- Zero-capital-cost `p_nom_opt` (distribution grid, gas/H2 pipelines, BEV
  charger 4 194 MW, water-pit charge/discharge, home/battery dischargers…):
  degenerate, swings between vintages — not capacities.
- Single-horizon PV sub-carrier splits (cost-ranking artefact); report total PV.
- Anything at 3 significant figures from the Crossover-0 interior point
  (level-1 caveat); 2040 biogas-block on/off economics (§6 lumpy-costs note).

### Review follow-ups

| # | Action | Owner |
|---|---|---|
| 1 | Close R1 (2025 wall-time gap) | ops |
| 2 | Rule on R2 (coal overshoot, esp. 2040 +37 %) | modeller |
| 3 | Trace R3 (2040/50 elec load −0.8/−0.9 %) | modeller |
| 4 | Reconcile R6 (heat-fidelity total vs max) | modeller |
| 5 | `--whole-file` for `nic5.sh pull` | code |
| 6 | Confirm Explorer test listing | ops |
