# scen_central — new central: ground PV capped at 6.5 GW + updated costs (NIC6, 1 h, weather 2010)

**Status (17 Oct 2026): solved 4/4 optimal, landed, pypsa2html published. Comparison with the flat-cost run written (§7). §11 NOT written. Committed.**
Operator: Claude desktop agent, office computer, on S. Quoilin's instruction. Sister run: [`2026-10-17_scen_central_flat_res_costs_2010_1h.md`](2026-10-17_scen_central_flat_res_costs_2010_1h.md). Predecessor (old costs, same 6.5 GW cap): [`2026-10-16_scen_central_pv65_2010_1h.md`](2026-10-16_scen_central_pv65_2010_1h.md).

## 1. Identification
Scenario `scen_central`, results `results/walloon/scen_central`. Code: HEAD `fba412b7` (merge of origin/development_plan `442f437b` + the 6.5 GW commit `9e6988ed`). TIMES export `scen_central_v1_3gw_261009_0910.vd`. The 13 Oct central (13 GW, old costs) is archived in `results/_archive_20261017/scen_central_13gw_pre_costs_update` (NIC6: `pypsa-wal-archive/20261017/`).

## 2. Goal
Re-run the central after two changes: (a) BEWAL ground PV `p_nom_max` 13 000 -> 6 500 MW in every scenario (master CSV, commit `9e6988ed`; sensitivity run of 16 Oct), (b) the colleague's updated costs / learning curves merged from origin (`442f437b`).

## 3. Parameters
Nothing else changed in the scenario block (the cap comes from the master CSV, the costs from the merged `custom_costs*.csv`). 2025 is unchanged against the 16 Oct run to 1e-7, 2030+ differ by the costs (§7).

## 4. Execution
Local prepare (112 steps, 8 GB cap) of this run and the flat-cost run together, push, one orchestrator `REMOTE=nic6 RUN_NAME="scen_central scen_central_flat_res_costs"` (40 cores / 75 000 MB, Gurobi 32 threads, 6 h), launched 10:35.
**2040 stalled (see §9.1)** and was solved on a second orchestrator; the final tree is assembled from three solves:

| horizon | solver settings | Slurm job | elapsed |
|---|---|---|---|
| 2025 | plain (`config_cluster_nic6.yaml`) | 48937 | 1:35:56 |
| 2030 | plain | 49016 | 34 min |
| 2040 | **NumericFocus 3 + ScaleFlag 2** (`config_cluster_nic6_numericfocus.yaml`) | 49111 | 3:49:32 |
| 2050 | plain, run in a **clone directory** (`pypsa-wal-plain`) from the NumericFocus 2040 network | 49313 | 34 min |

Failed / cancelled attempts: 2040 plain 49080 (41 min) and its identical repeat in the clone 49224 (44 min), both "Sub-optimal"; 2050 NumericFocus 49276 cancelled at 59 min (iteration 39) once the plain 2050 had solved. Peak `MaxRSS` 55-61 GB of 73 GiB.
Landing and publication under `cluster/capped.sh`, one step at a time, as for the flat run (`land_0617.sh`, `publish_0617.sh`).

## 7. Results
`Optimal objective`: 2025 3.35336258e11 · 2030 3.74449838e11 · 2040 2.64447336e11 · 2050 **2.88549610e11**.

| objective, 1e11 EUR | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| 16 Oct, 6.5 GW, old costs (`scen_central_pv65`) | 3.35336298 | 3.72882640 | 2.63609697 | 2.84817750 |
| **new central** (6.5 GW, new costs) | 3.35336258 | 3.74449838 | 2.64447336 | 2.88549610 |
| flat renewable costs (sister run) | 3.35401688 | 3.76754206 | 2.68693309 | 3.04947826 |

* Cost update (central against the 16 Oct run): 2025 unchanged (-4e-8 relative), 2030 +1.57e9 EUR (+0.42 %), 2040 +0.84e9 (+0.32 %), 2050 +3.73e9 (+1.31 %).
* Flat renewable costs against the new central: 2025 +6.5e7 (+0.02 %, an artefact: base-network onshore-wind VOM follows `costs.year`, see the flat log §3), 2030 +2.30e9 (+0.61 %), 2040 +4.25e9 (+1.6 %), 2050 **+1.64e10 (+5.7 %)**.

BEWAL, GW installed / TWh:

| | 2030 | 2040 | 2050 |
|---|---|---|---|
| ground PV, central | 0.91 / 0.87 | 5.89 / 5.71 | 6.50 / 6.31 (cap) |
| ground PV, flat | 0.91 / 0.87 | 6.39 / 6.20 | 6.50 / 6.31 (cap) |
| rooftop PV, central | 4.71 / 4.53 | 11.10 / 10.77 | 13.05 / 12.66 |
| rooftop PV, flat | 4.71 / 4.52 | 11.10 / 10.77 | 11.98 / 11.62 (TIMES floor) |
| onshore wind, both | 3.97 / 8.75 | 6.50 / 14.96 | 6.50 / 14.97 (potential cap) |

Whole model (six countries), GW in 2050, central vs flat: onshore 216 vs 255, solar 609 vs 592, offshore AC 68 vs 54, offshore DC 238 vs 229. The cap on Walloon ground PV (6.5 GW) binds only in 2050 in both runs; in 2040 the central, with learning, builds 0.5 GW less ground PV than the flat run and the same rooftop.
`review_run.py`: 170 PASS / 30 INFO / 14 WARN / **10 FAIL** = the nine known foreign-nuclear rows (F11) + **the provenance check that the 2040 config snapshot differs from 2025's beyond the horizon: it does, by the NumericFocus overlay (deliberate, §9.1)**. Heat-profile fidelity residual 2.7e-6 TWh.

## 8. Publication
https://pypsa.squoilin.eu/scen_central_20261017/ (hub, pypsa2html report, Sankey: HTTP 200). The 13 Oct page `scen_central_20261013` (13 GW, old costs) stays online for comparison. S3 / Explorer: not uploaded (not asked).

## 9. Issues and fixes
1. **2040 stalled twice on plain settings.** Barrier "Sub-optimal termination" at iteration 400, exactly the same iteration trace in the original and in the clone (the plain solve is deterministic here): `scripts/solve_network.py` refuses to export a network without a certified optimum, so the chain stopped. The plain run's final objective (2.64447634e11) is 1.1e-6 above the certified one (2.64447336e11): the point was good, the status was not. Remedy used: `NumericFocus 3` + `ScaleFlag 2` (the 13 Sep batch's second-line remedy; the overlay file was never committed, recreated as `cluster/config_cluster_nic6_numericfocus.yaml`), which converged after 3:49 (iteration ~210). The 2050 horizon solved on plain settings (180 iterations, 31 min) in a clone directory from the certified 2040 network, so the slow settings were not needed again. Whether the stall is related to the old `threshold_capacity: 0` finding (13 Sep log §14.1; upstream set it to 10 in `c094ff46`) was not tested.
2. The upstream merge made the hub target depend on the pypsa2html report; postprocess and publish were adapted (flat log §9.1-9.2).
3. Orchestration bookkeeping: `cluster/.last_jobs_nic6` was overwritten by each relaunch (original orchestrator pid 3469678, clone 3518464 / 3534252). Two orchestrators cannot share a directory: the clone was made with `rsync -a` (anchored excludes `/results /tmp /.cache /cluster/logs /.snakemake/{locks,incomplete,slurm_logs}`) plus the 2025/2030 results.

## 10. Follow-ups
* Consider whether a certified-optimal-or-1e-6 rule is acceptable for the stall (the guard in `solve_network.py` is deliberate; the 2040 point was 1.1e-6 from the optimum), or whether to set `NumericFocus` only on the horizons that need it.
* The other scenarios tied to the central (biomethane_industrie, noccsccgt, nuc4gw family, ...) now carry the 6.5 GW cap in their configuration but were not re-run.
* Two trees differ in solver settings by horizon (2040): same objective to 1e-6, but the provenance check says so.
* `/` was at 82 % (other projects' `/tmp`); not ours.

## 11. Critical review
Not done.
