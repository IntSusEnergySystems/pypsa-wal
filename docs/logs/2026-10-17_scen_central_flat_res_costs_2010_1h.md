# scen_central_flat_res_costs — renewable costs (biogas included) flat at their 2025 value (NIC6, 1 h, weather 2010)

**Status (17 Oct 2026): solved 4/4 optimal, landed, pypsa2html published. Comparison with the new central pending (central 2040/2050 still solving, see its log). §11 NOT written. Committed.**
Operator: Claude desktop agent, office computer, on S. Quoilin's instruction. Sister run: [`2026-10-17_scen_central_new_costs_pv65_2010_1h.md`](2026-10-17_scen_central_new_costs_pv65_2010_1h.md).

## 1. Identification
Scenario `scen_central_flat_res_costs`, results `results/walloon/scen_central_flat_res_costs`. HEAD `fba412b7` (+ comment-only edits, committed after). Merged with origin/development_plan `442f437b` (updated learning-curve costs) the same morning. TIMES export `scen_central_v1_3gw_261009_0910.vd`, as the central.

## 2. Goal
What if renewable technologies stopped getting cheaper after 2025? One change against the new central (`scen_central`, ground PV 6.5 GW, updated costs): **investment, FOM, VOM, fuel and lifetime of the renewable technologies are held at their 2025 value in every horizon.**

## 3. Parameters
* New file `data/walloon/custom_costs_scen_central_flat_res_costs.csv`, **generated** by `scripts/walloon_scripts/build_flat_res_costs.py` from `custom_costs.csv` and the technology-data 2025 table (`data/costs/archive/v0.14.0/costs_2025.csv`); scenario key `costs.custom_cost_fn`. `test/test_flat_res_costs.py` (10 tests; fails on a stale file).
* Technologies: onwind, offwind (+ AC/DC/float stations and connections), solar, solar-rooftop (+ commercial, residential), solar-utility (+ single-axis tracking), hydro, ror, geothermal, central geothermal heat source, central/decentral solar thermal, biogas, biogas CC, biogas upgrading, biogas manure, biogas plus hydrogen. **Not frozen:** solid-biomass plants, heat pumps, storage, electrolysis, grids (conversion/storage technologies). The list is `FLAT_TECHNOLOGIES` in the script.
* Lifetime is frozen too: technology-data lengthens some lifetimes with the year (central geothermal 25 -> 30 years), which would otherwise lower the annuity (first version of the test caught it).
* Test through `prepare_costs`: for 2030/2040/2050 only the listed technologies differ from the central table, and each equals its 2025 value; the 2025 tables are byte-identical (`costs_2025_processed.csv`, same md5).
* **Known quirk, not caused by this scenario:** the generators of the base electricity network (`base_s_adm_elec.nc`) take their marginal cost from the table of `costs.year` (**2050**), not from the horizon. So the central carries the learned 2050 onshore-wind VOM (1.623 EUR/MWh) in every horizon, while this scenario carries the frozen 1.9035. Result: the 2025 LPs differ (8 onwind generators, `marginal_cost` only) and the 2025 objective is **+6.5e7 EUR (+0.02 %)** above the central although the 2025 cost tables are identical.

## 4. Execution
Local prepare of both runs (`batch_20261016_scripts/prepare_0617.sh`, 8 GB cap, 112 steps, 10:13, peak 6.1 GB). Push, then one orchestrator for both scenarios: `REMOTE=nic6 RUN_NAME="scen_central scen_central_flat_res_costs" ./cluster/nic5.sh solve` (40 cores / 75 000 MB, Gurobi 32 threads, 6 h limit), launched 10:35. Old `scen_central` tree archived first (`results/_archive_20261017/scen_central_13gw_pre_costs_update`, NIC6 `pypsa-wal-archive/20261017/`).
Chain `chain_0617b.sh`: wait for 4/4 optimal, `land_0617.sh` (pull, postprocess, ptx_report, review_run, heat fidelity), `publish_0617.sh B` (pypsa2html report, hub, Sankeys, rsync). All local steps under `cluster/capped.sh`, one at a time (shared flock), per `run_from_office_computer.md` §7.

## 5. Timings (sacct)
2025 1:16:55, 2030 35 min, 2040 27 min, 2050 27 min (flat solved at about the same speed as the central). Chain solved 10:35 -> 13:27.

## 6. Resources
Solve `MaxRSS`: 54-61 GB of 73 GiB requested (2030 the largest, 60.8 GB). Local: prepare 6.1 GB, postprocess 3-5 GB, review 5.7 GB, ptx 3.9 GB, html 3.4 GB peak (91 pages, 2 min). `/` was at 82 % (other projects' `/tmp` data) during the run; nothing of this run writes there (TMPDIR on the mount).

## 7. Results
`Optimal objective`: 2025 3.35401688e11 · 2030 3.76754206e11 · 2040 2.68693309e11 · 2050 **3.04947826e11**.
BEWAL (GW installed / TWh), from the solved networks:

| | 2030 | 2040 | 2050 |
|---|---|---|---|
| ground PV | 0.91 / 0.87 | 6.39 / 6.20 | **6.50** / 6.31 (cap) |
| rooftop PV | 4.71 / 4.52 | 11.10 / 10.77 | 11.98 / 11.62 (= TIMES floor) |
| onshore wind | 3.97 / 8.75 | **6.50** / 14.97 | **6.50** / 14.97 (potential cap) |
| offshore | 0 | 0 | 0 |

Whole model (6 countries), GW: onwind 200 / 183 / 255, solar 355 / 336 / 592, offwind 111 / 167 / 283 (2030 / 40 / 50).
Comparison with the central: see the central's log (pending).
`review_run.py`: 170 PASS / 30 INFO / 14 WARN / 9 FAIL = the nine known foreign-nuclear rows (F11). Heat-profile fidelity residual 2.05e-6 TWh.

## 8. Publication
https://pypsa.squoilin.eu/scen_central_flat_res_costs_20261017/ (hub, pypsa2html, Sankey: HTTP 200). S3 / Explorer: not uploaded (not asked).

## 9. Issues and fixes
1. **Postprocess pulled the pypsa2html report in.** Since the merge of origin/development_plan the hub target (`html/index.html`, requested because `TIMES_SANKEY=1`) depends on `generate_html_report`, so `nic5.sh postprocess` started an HTML build under the plain 10 GB cap and the Snakemake run died before `network_cost_report.py` (0 of 3 network-cost CSVs). Fix: `land_0617.sh` sets `TIMES_SANKEY=0`; the publish phase builds hub, Sankeys and report under their own caps. The aborted attempt was killed by PID and the tree re-landed.
2. **`summary.json`.** The merged `rules/pypsa2html.smk` declares `html/pypsa/summary.json` as an output; the installed pypsa2html (`26305ed`) writes it to `html/pypsa/summaries/<scenario>/`. The hub dry run then planned a second report build and the safety check aborted the publish. Fix in `publish_0617.sh` (step 1b): copy the summary up one level and `snakemake --touch` the report rule (runs nothing). Not fixed in the repo: the rule and the library disagree on the path (to settle with the pypsa2html author).
3. The central's 2040 solve failed (sub-optimal barrier), see its log. Not this scenario.

## 10. Follow-ups
* Compare with the new central once its 2040/2050 are in (capacities, costs by technology, prices).
* Solid-biomass conversion plants are not frozen; extend `FLAT_TECHNOLOGIES` if they should be.
* Settle the `summary.json` location (item 9.2) and the `costs.year = 2050` marginal-cost quirk (item 3 above) with the model owners.

## 11. Critical review
Not done.
