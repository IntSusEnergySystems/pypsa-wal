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

---

## 12. Resolution of R1–R4 (2026-09-07, code only — no re-solve yet)

All four findings were traced to a cause and fixed in code. **None of the fixes
is in the published 20260906/20260907 results**: R1 and R2 change the LP inputs,
so the numbers below are what the *current* networks say, and the four horizons
have to be rebuilt and re-solved before anything is republished.

### R1 — `coal for industry` above TIMES — **transfer defect, fixed**

PyPSA-Eur has no coke bus: `prepare_sector_network.add_industry` restates coke
demand as the hard coal a coke oven would burn to make it,
`mwh_coal_per_mwh_coke = 1.366`, and charges the whole chain at coal's CO2
intensity. Correct for a region whose own ovens make its coke. Wallonia has no
coke oven in TIMES — `COACOK` is produced only by `IMPCOACOK` and consumed only
by `INDCOK00`, i.e. the region buys finished coke — so the factor invented
Walloon coal, and Walloon CO2 inside the country cap, that TIMES does not have.

The overshoot is that factor and nothing else:

| | coal | coke | PyPSA `coal + 1.366·coke` | TIMES `coal + coke` | dev | §11 reported |
|---|---:|---:|---:|---:|---:|---:|
| 2025 | 2.700 | 1.006 | 4.075 | 3.706 | +9.9 % | +9.8 % |
| 2030 | 1.876 | 1.162 | 3.463 | 3.038 | +14.0 % | +14.0 % |
| 2040 | 0.002 | 1.017 | 1.392 | 1.019 | +36.5 % | +36.7 % |
| 2050 | 0.707 | 1.162 | 2.294 | 1.868 | +22.8 % | +23.4 % |

Fix: `coke_to_coal_factors()` returns 1.0 for the TIMES-driven node and 1.366
everywhere else. Also `build_industrial_energy_demand_per_node.py` now writes
`%.6f` instead of `%.2f` — the unit is TWh/a, so two decimals quantised every
industrial demand to 10 GWh and rounded BEWAL's 2040 coal (0.0024 TWh) to zero.

### R2 — BEWAL electric load below TIMES — **two transfer defects, fixed**

Traced carrier by carrier against the run's own v2 demands. 2050, TWh:

| term | PyPSA | TIMES | gap |
|---|---:|---:|---:|
| `industry electricity` | 21.140 | 21.141 | −0.001 (the `%.2f` above) |
| EV (battery side) | 16.608 | 16.912 | −0.304 — charger loss, *check* artefact |
| `agriculture electricity` | 0.063 | 0.063 | 0 |
| `agriculture machinery electric` | 0.272 | — | +0.272, no TIMES row |
| `electricity` load | 18.635 | 19.146 | **−0.510** |

The −0.510 is two defects that the old check's two offsetting conventions
almost cancelled:

1. **Distribution losses deducted from a low-voltage TIMES demand.**
   `insert_electricity_distribution_grid` multiplies every `electricity` load by
   `efficiency_static` = 0.97 because PyPSA-Eur's source (ENTSO-E) measures
   demand above the distribution network. The Walloon load is not that number:
   TIMES routes residential, tertiary, agriculture and transport electricity
   through `EVTRANS_H-M` (η 0.973) and `EVTRANS_M-L` (η 0.968) and books the
   demand on `ELCLOW`, downstream of both — the same place as PyPSA's
   low-voltage bus. Deducting again cost 0.333 / 0.382 / 0.475 / **0.576** TWh.
   Every other BEWAL electricity carrier already escaped, so the exemption also
   removes an inconsistency.
2. **`total rail` instead of `electricity rail`** in the scaling target:
   `total rail` is electric *and* diesel rail, so the Walloon grid was asked to
   haul the diesel trains too (+0.053 → +0.066 TWh).

Fixes: `distribution_loss_targets()` drops the TIMES node;
`WALLOON_ELECTRICITY_CATEGORIES` uses `electricity rail`. Predicted level-2.3
deviation after a re-solve: **−0.005 / −0.015 / −0.004 / −0.002 %**.

The level-2.3 check itself was comparing the two sides at different points of
the grid and is rewritten: the EV term is grossed back up by the 0.9 charger
efficiency (matching check 2.2 and the extraction rule, which measures
`electricity road` at the charger *input*), and loads with no TIMES row are
excluded and reported by name instead of silently widening the tolerance. On the
current networks it reads −1.38 / −1.22 / −0.92 / −0.89 %, i.e. **2025 and 2030
never passed either** — they were flattered by the charger loss and the
agricultural machinery cancelling the 3 %.

### R3 — Sankey mapping holes — **two of four fixed upstream (pypsa2html)**

Not "known mapping gaps": two extraction bugs. See pypsa2html `docs/DESIGN_DECISIONS.md` D21.

- `pac_fe` −0.147 TWh, every horizon: the agricultural correction ran *after*
  the `pac_pe → pac_fe` closure had totalled the outflow. **Fixed.**
- `elc_se` +7.22 (2040) / +9.29 (2050): the heat pumps' `_2` row carried their
  **heat output** while the taxonomy books it as electricity, so the node was
  charged for the ambient intake — 9.1 TWh in 2040. Plus `rural air heat pump`
  had no mapping at all. **Fixed.**
- `vap_se` +0.437 (2030): rows that become identical only after
  `_aggregate_carriers` were never re-grouped, so a retired zero-flow vintage of
  `urban central resistive heater` took rank 1 and 0.388 TWh_th of district heat
  was booked as *losses*. **Fixed.**
- Remaining on BEWAL: `elc_se` 2025 −0.64 TWh and `vap_se` 2025 −0.08 TWh —
  pumped-hydro round-trip loss (no edge exists for a StorageUnit), the rank-1
  `H2 pipeline` row, and `urban central heat vent` (deleted as a self-loop
  because carrier and bus carrier both normalise to `heat`). Each is a taxonomy
  decision; none is a solve defect.

Whole run: 53 → 45 unbalanced node-years; ALL `elc_se` 2050 +642.9 TWh → balanced.

### R4 — heat fidelity — **reconciled; the "pass" was wrong**

The sum-vs-max discrepancy was two different runs. The 8.15 TWh total came from
the production networks; the −0.033 TWh "worst single gap" came from
`profile_fidelity_live.csv` **dated 2026-09-03**, i.e. the 6h test run. Re-run
on this run's networks, the worst single gap is **−2.008 TWh (2040 biomass
boiler, rural heat) — 88.1 % of its pinned target**, mirrored on the urban
decentral bus. 4.03 TWh_th of the TIMES 2040 decentral biomass-boiler heat was
delivered by heat pumps instead.

Why it was invisible: the absorber makes the signed gaps cancel per (year, bus)
to 4×10⁻⁷ TWh, so the total decentral heat closes exactly and every aggregate
check passes. Summing |gaps| over groups is therefore meaningless — an 8.15 TWh
total made of ±2.008 TWh substitutions reads the same as one made of rounding.

Why it happened: not a code bug. BEWAL's solid biomass was **exhausted** in
2040 — 6.00 TWh domestic + 2.25 TWh transported, both at `e_sum_max` — with
7.62 TWh going to the TIMES-pinned industrial demand. The pin needed ~5.25 TWh
more fuel than existed. In 2050 the EU `biomass limit` priced the marginal MWh
at **1202.5 EUR/MWh** against a 1000 EUR/MWh_th relaxation penalty, so buying
out the pin was simply cheaper — the premise in the penalty's own docstring
("~10–25× the marginal cost of heat, so relaxing is never cheaper than
complying") is false once a fuel is scarce.

Fixes, all reporting rather than physics — the conflict is real and belongs to
the modeller:

- `report_relaxed_profiles()` reads `TimesHeatProfile-unmet` off the solved
  model and logs the relaxed energy, share and penalty per group; called from
  `solve_network.py` after a certified solution.
- `review_run.py` gains **level 2.5**, which runs the fidelity measurement on
  the run's own networks and WARNs on any group under 98 % of its profile,
  instead of quoting a stale CSV.
- `check_heat_profile_fidelity.py` now prints the worst *group* and the
  per-(year, bus) residual next to the |sum|, so the two cannot be confused
  again.

**Open for the modeller:** the Walloon biomass envelope (`custom_potentials.csv`
`e_sum_max`) is smaller than what TIMES's own solution spends, once the pinned
industrial demand and the pinned decentral heat mix are both imposed. Either the
envelope or one of the two pins has to give.

### R5 — Gurobi conditioning warnings

Not touched; still tolerated per checklist level 1.

### Re-solve required

R1, R2 and the `%.6f` demand precision change the LP for **every** node, so all
four horizons need `prepare` + solve again before republication. R3 and R4 are
reporting-only and can be regenerated from the existing networks.

---

## 13. Biomass: the ICEDD potential, and where the "imports" were really coming from

### ICEDD's new Walloon potential, merged

`origin/master` `2f67b01e` raises the Walloon solid-biomass potential from
**6000 to 9222 GWh/an** in `config/input_parameters_for_models.csv`. Merged into
`development_plan` (`25680656`) and `build_common_parameters.py --write` pushed
it into `data/walloon/custom_potentials.csv` for all four horizons.

It corroborates well: TIMES's own Walloon woody supply (`BIOCPS` chips +
`BIOLOG` logs + `MBOWOO` + `MPPWOO`) peaks at **9.37 TWh** in 2030 and 2040 —
within 2 % of 9.222.

### What TIMES actually does with biomass trade

Measured on `scen_central_demande_haute_v2_260903_0309.vd`, PJ → TWh:

| | domestic woody | + renewable sludge | imports | exports | net |
|---|---:|---:|---:|---:|---:|
| 2025 | 7.758 | 10.284 | **0.000** | 3.334 | 6.950 |
| 2030 | 9.374 | 11.901 | **0.000** | 1.967 | 9.934 |
| 2040 | 9.373 | 12.604 | **0.000** | 0.000 | 12.604 |
| 2050 | 5.298 | 8.529 | **0.000** | 0.000 | 8.529 |

**TIMES Wallonia imports no solid biomass in any horizon.** `IMPBIOPEL` never
activates; the region is a net *exporter* of pellets in 2025 (3.33 TWh) and of
chips in 2030 (1.97 TWh). The only `IMP*` flows on bio commodities are
`BIODST` (biodiesel), `BIOETH` (ethanol) and `BIOEFF` (effluents, in Mt) —
liquids and biogas feedstock, not solid biomass.

### Defect 1 — every brownfield biomass boiler burned Brussels' biomass

`add_existing_baseyear.py` wired the brownfield boiler `bus0` to
`spatial.biomass.nodes[0]` — the first biomass bus of the whole model,
alphabetically **`BEBRU solid biomass`**. Measured on the 2030 network:

| boiler's own region | fuel from `BEBRU solid biomass` | from its own bus |
|---|---:|---:|
| BEWAL | **4.481** | 1.110 |
| FR | 12.454 | 71.272 |
| DE | 7.318 | 0.000 |
| BEVLG / GB / LU / NL | 0.329 | 0.070 |

**24.6 TWh of 97.1 TWh** of brownfield biomass-boiler fuel crossed regions in
2030, all of it onto a Brussels bus whose own resource is 0.6 TWh. BEWAL's
share, 4.48 TWh, is more than **twice** the 2.0 TWh Walloon import cap it was
bypassing — and the `solid biomass transported` generator on the receiving bus
carries no `e_sum_max` of its own (BEBRU drew 24.9 TWh through it in 2030,
39.5 TWh in 2025), so the fuel was in effect free and unlimited. No regional
biomass potential can bind while this holds.

Fixed: `biomass_fuel_buses()` returns the per-node bus from
`spatial.biomass.df`, the same wiring the brownfield biomass CHP already used,
and still the single `EU solid biomass` bus when `biomass_spatial` is off.

### Defect 2 — two caps on one flow, one of them applying to nothing

| row | value | component | managed? | applied? |
|---|---:|---|---|---|
| `solid biomass import` / `e_nom` | 4.0 / 4.0 / 4.5 / 6.0 TWh | Store | yes | **no** — `sector.solid_biomass_import.enable` is false (F8), so the Store is never built |
| `solid biomass transported` / `e_sum_max` | 2.0 / 2.0 / 2.25 / 3.0 TWh | Generator | **no** — unmanaged orphan | yes, and it binds in 2030 and 2040 |

Exactly half, on a different component, and the one that mattered was invisible
to `build_common_parameters`. Fixed by swapping their roles in the master CSV:
the Bioenergy-Europe row is now `status: none` with the reason (its value kept
as documentation, so re-enabling the feature restores it), and the Valbiom
`solid biomass transported` cap is now an active managed target. Plus a guard:
`BEWAL_potentials.py` **warns** when a potential row matches no component
instead of no-op'ing, which is what let this sit unnoticed.

### The value: recommendation

After the leak fix the Walloon envelope is **11.2 / 11.2 / 11.5 / 12.2 TWh**
(9.222 domestic + the Valbiom import cap) against TIMES's **10.3 / 11.9 / 12.6 /
8.5 TWh**, all domestic. Close through 2040, generous in 2050 — where the import
cap *rises* to 3.0 TWh while TIMES's own supply *falls* to 8.5.

The 2.0–3.0 TWh "import" is, in substance, standing in for a domestic resource:
TIMES's renewable sludges/residues (`BIOSLU`/`BIOSLUH`, ~2.5–2.8 TWh) count as
`solid biomass` in the industry extraction rule but are outside ICEDD's
pellets-and-chips potential. **The clean end state is to book that resource as a
Walloon potential and take the import cap to zero, matching TIMES exactly.**
That is an ICEDD data decision, so the cap is left at the conservative Valbiom
value for now — zeroing it today, before the sludges are added, would simply
starve 2030.

### Expected effect on the next solve

Biomass supply vs the previous run's demand, TWh:

| | supply before | supply after | demand at the old dispatch | verdict |
|---|---:|---:|---:|---|
| 2025 | 8.0 | 11.2 | 8.0 + 2.67 leaked | just fits |
| 2030 | 8.0 | 11.2 | 8.0 + 4.48 leaked | **~1.3 short** — the model must substitute; those boilers were burning biomass Wallonia does not have |
| 2040 | 8.25 | 11.5 | 8.25 (rationed) | **+3.2 TWh of headroom** — directly relieves the R4 biomass-boiler pin that went 88 % unmet |
| 2050 | 9.0 | 12.2 | 6.38 | ample |

So R4's 2040 finding should largely resolve itself, and 2030 becomes the tight
horizon instead — honestly this time.
