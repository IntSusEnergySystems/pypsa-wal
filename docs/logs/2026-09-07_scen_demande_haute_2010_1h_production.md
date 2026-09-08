# Solve log — scen_demande_haute @ 2010, 1h (production, ICEDD 2026-09-07 export)

Second launch of 2026-09-07. The morning attempt on `8fbc39f3` stalled at 2030
(see [`2026-09-07_scen_demande_haute_2010_1h_stalled.md`](2026-09-07_scen_demande_haute_2010_1h_stalled.md)):
barrier sub-optimal after 402 iterations against the old
`scen_central_demande_haute_v2_260903_0309.vd`. Root cause per `d950d061` was not
numerics but a degenerate 2030 solid-biomass budget on the boundary. This run
solves the same code against ICEDD's new export, which freezes the Walloon
resource at its 2021 energy-balance level. All four horizons optimal.

## 1. Identification

| Field | Value |
|---|---|
| Date of run | 2026-09-07 19:14 (launch) → 2026-09-08 ~01:45 (solve done); recovery + review until ~04:30 |
| Operator | sylvain, assisted by opencode/Muse Spark |
| Run name / prefix | `scen_demande_haute` / `walloon` |
| Config files | `config/config.walloon.yaml` + `cluster/config_cluster.yaml` (16 CPUs, 100 GB, `BarHomogeneous: 1`) |
| Code version | `development_plan` `d950d061` ("Point the Walloon scenarios at ICEDD's 2026-09-07 TIMES export"); working tree clean at launch |
| Sibling checkouts | TIMES_PyPSA `3627a53` (edd); pypsa2html rebuilt from current checkout (trade fix `5793e1a` included, see 09-05 log addendum) |
| Outcome | **success 4/4**, after a pull/recovery incident documented in §9 (no solve re-run needed) |

## 2. Goal of the run

Production solve of `scen_demande_haute` (2010 weather year, 1h) on the
post-R1/R2/R4 code (`8fbc39f3`) with the `.vd` the stall diagnosis called for
(`d950d061`). Questions answered: does 2030 converge on the new export, is
R4's 2040 biomass-boiler relaxation gone, and do the R1/R2 transfer fixes
verify at ±0.00%.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v01_260907_0709.vd` (fetched from `s3://intervectoriel/test/scenarios/times_20260907/`, symlinked into `data/walloon/`) |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` (cached) |
| Snapshots | 2010-01-01 → 2011-01-01, 8760 h |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier, Method 2, BarConvTol 1e-5, BarHomogeneous 1, Crossover 0, Seed 123, 16 threads |
| Key scenario overrides | Tihange retrofit repeatable (`retrofit_nuclear_once: false`); agg caps `agg_p_nom_minmax_demande_haute.csv`; rooftop share on; industry CC floor on; self-sufficiency caps 2.94/6.47/10.0 TWh (2030/2040/2050); option B′ heat pinning, absorber = heat pump, penalty 1000 EUR/MWh_th |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Prepare (network build) | local, 16 cores | rebuilt demands + base networks against the new `.vd` (~20 min) |
| LP solve | NIC5 `hmem`, 16 CPUs/task, 100 GB | no queue wait either attempt (100 GB shares a mixed node instead of blocking a full one) |
| Post-processing (CSVs, plots) | local | re-ran after recovery (§9) |
| HTML report (pypsa2html) | local | 94 pages, re-published after recovery |
| Explorer CSV extraction (ClimAct) | local, env `datapypsa` | reads networks from S3 raw (`download_networks: True`); re-ran after recovery |

Solve jobs: 2025 `11126424`, 2030 brownfield `11126806` + solve `11126807`, 2040→2050 `11126807`→`11127558`, all on `nic5-w071`.
Pre-flight: `build_common_parameters --check` PASSED, full pytest 369 passed / 1 skipped (before first launch);
`pytest -k times_scenario_inputs` 2 passed after the `.vd` swap.

## 5. Timings

| Step | Duration |
|---|---|
| Total launch → solve done | ~6.5 h (19:14 → ~01:45) |
| Prepare (network build) | ~20 min (incremental: demands + 4 base networks) |
| Push to cluster | ~2 min |
| Queue wait | ~0 (both attempts) |
| Solve 2025 | 211→**247 it / 3892 s** barrier (~1h05 job); objective 3.48432903e11 |
| Solve 2030 | **314 it / 7809 s** barrier (~2h10; ~3h job with model gen); objective 3.64865569e11 |
| Solve 2040 | **244 it / 4733 s** barrier (~1h20 job); objective 2.88615231e11 |
| Solve 2050 | **199 it / 3971 s** barrier (~1h05 job); objective 2.67249208e11 |
| Pull results | minutes (but failed verification — see §9) |
| Post-processing + plots | ~5 min (re-ran 03:2x after recovery) |
| pypsa2html report | ~1 min (94 pages) |
| ClimAct extraction | ~25 min |

Runtime comparison (same 1h resolution, same scenario): the morning attempt's
2030 never converged (402 it / 6237 s → sub-optimal); on the new `.vd` 2030
converges in 314 it / 7809 s with residual 4.75 vs 1.38e5 at the old stall
point. 2025/2040/2050 barrier times are in line with the 09-06 run. No
constraint set changed between the two 09-07 attempts — only the `.vd`.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (2030) | 39,421,163 rows / 19,115,120 cols / 94,905,710 nonzeros; presolved 7,887,015 × 14,638,834 |
| Peak RAM per solve | 22.4 / 28.2 / 29.8 / 29.9 GB (2025 → 2050, `logs/*_memory.log`) — well inside the 100 GB request |
| Disk footprint | remote `results/walloon/scen_demande_haute/` 1.34 GB; local tree 2.29 GB (with derivatives + explorer) |

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | optimal | 3.48432903e11 |
| 2030 | optimal | 3.64865569e11 |
| 2040 | optimal | 2.88615231e11 |
| 2050 | optimal | 2.67249208e11 |

Local result folders: `results/walloon/scen_demande_haute/{networks,csvs,graphs,html,explorer,logs,configs,heating_profiles}/`.
Effective configs verified identical across horizons apart from
`planning_horizons`; all four name the new `.vd`.

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260908_walloon_scen_demande_haute/` (re-uploaded with true networks after recovery) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260908/` |
| Explorer CSVs | 49 in `pypsa/`, 3 in `strategy/` (re-extracted from corrected raw) |
| TIMES vd staged | yes — only `scen_central_demande_haute_v01_260907_0709.vd` (stale `v2_260903` removed locally and from S3) |
| HTML report | https://pypsa.squoilin.eu/scen_demande_haute_20260908/ (rebuilt 03:47 with pypsa2html `2c40825`, 95 pages, same folder overwritten) |
| Verified in Explorer dropdown | no — not checked from here |

## 9. Issues encountered and fixes

- **Pull failed end-to-end verification; stale tree published (critical, recovered).**
  Symptom: after a green solve, local networks/configs did not match the
  cluster (md5 mismatch, old `.vd` string in local configs, different
  objective 3.638e11 vs 3.6487e11 for 2030). Cause: every large solve output
  failed rsync verification (`failed verification -- update discarded`, exit
  code 23) — first pull at 01:46 raced the freshly finished 2050 outputs on
  BeeGFS, and the re-pull hours later still failed the same way, so it is not
  (only) a race: rsync's **delta-transfer** path mis-verifies on this
  link/filesystem while `scp` and single-file rsync verify cleanly. The
  `|| msg "(no results dir yet)"` fallback in `cmd_pull` then let the driver
  continue onto postprocess, which built CSVs/graphs/HTML from the stale Sep-6
  files, uploaded them to S3 raw, and the extractor (which reads S3 raw)
  propagated the staleness into the Explorer CSVs. Fix: re-transferred the 16
  failing files (4 networks + 4 configs + 4 python logs + 4 benchmarks) with
  `rsync --whole-file`, md5-verified all four networks against the cluster,
  re-ran standard pull (clean), touched the networks (the true files carry
  older remote mtimes than the stale derivatives, so Snakemake said "nothing
  to be done"), re-ran postprocess (CSVs/graphs/HTML rebuilt 03:23–03:26),
  re-uploaded raw, re-extracted, re-uploaded scenarios, removed the stale
  `.vd` from the scenario folder, re-published HTML. Lesson: a pull whose
  rsync exits non-zero must abort the driver, and the four networks should be
  md5-checked against the cluster before postprocess (see §11 follow-ups).
- **First review (163→140 PASS) was run against the stale files and is void.**
  The `review_run_20260908.log` findings (coal +9.8%, EV −1%, 2040 biomass
  relaxation) describe the Sep-6 model, not this run. Re-ran everything on
  the true tree (`review_run_20260908_true.log`); only the second review
  counts. Nothing derived before ~03:00 Sep 8 (CSVs, HTML `…_20260907`,
  first Explorer upload) may be cited.
- **Extractor preconditions evaporated.** `EXTRACTOR_BASE_CONFIG` defaults to
  `config_extraction_walloon.yaml`, which does not exist in the extractor
  checkout (prior runs overrode it with `config_extraction_OET.yaml`); the
  `EXTRACTION_CONFIG` patch to `graph_extraction_main.py` was gone
  (re-applied exactly as `extract_explorer.sh`'s guard prescribes, plus
  `import os`); the extractor needs `AWS_PROFILE=intervectoriel` in the
  environment (it reads networks from S3 raw and uploads strategy CSVs to
  S3) but `extract_explorer.sh` does not export it. All three are follow-ups
  in §11 — the next extraction hits the same walls otherwise.

## 10. Follow-ups / pending

Covered by the review follow-ups table at the end of §11 — 13 rows, of which
follow-ups 4 and 6 are **closed** by the second review pass and 9–13 are new.
F1–F3 are ops/tooling, F4–F7 modelling/reporting; the second pass adds
corrections C1–C4 and findings N1–N8. Plus: verify this run in the Explorer
dropdown.

## 11. Critical review

**First pass:** opencode/Muse Spark, 2026-09-08 ~03:00–04:30 CEST, on the
recovered true tree.
**Second pass (this text):** Claude Opus 5, 2026-09-08, independently, from the
published S3 raw tree
(`s3://intervectoriel/test/pypsa_raw_results/20260908_walloon_scen_demande_haute/`,
networks md5-distinct, objectives read back from the `.nc` and equal to §7) with
`resources/walloon/scen_demande_haute/wallon_demands_*.csv` **regenerated from
the run's own `.vd`** before any soft-link check. Four statements of the first
pass are corrected below (C1–C4) and eight findings are added (N1–N8). The
first pass's F1–F7 stand except where a C-item says otherwise.

**Headline counts:** `review_run.py results/… --full` → **191 PASS · 30 INFO ·
15 WARN · 0 FAIL** (the first pass's 163 PASS is the same run without
`--full`; the 28 extra passes are the per-bus balance sweep). Heat fidelity:
total |gap| 0.172 TWh over all (year, group, bus); worst single group 2050
biomass boiler rural, 0.0458 TWh pinned and 0 delivered — see N1 for *why*.

| Level | Verdict |
|---|---|
| 0 provenance | pass — `run.json` commit `d950d061` is an ancestor of HEAD; effective config byte-identical to `config/config.walloon.yaml`; four horizon configs differ only in `planning_horizons` |
| 0b commit intent | pass with caveats — every commit does what it claimed, but the `.vd` swap left two TIMES-derived side files behind (N6) |
| 1 solve | pass with caveats (Crossover 0 interior; large-bounds warnings in all four horizons) |
| 2 TIMES soft link | pass with caveats — every carrier ±0.00 %, but the 2050 heat pin was bought out because the absorber penalty is now below the biomass shadow price (N1) |
| 3 accounting identities | pass — every BEWAL bus and the Belgian AC+LV total close to 0.00 %; Sankey holes are mapping holes (F3) |
| 4 constraint compliance | pass with caveats — all 22 agg rows and every potential respected; the NTC is a ceiling the model does not reach on three BE borders (C4) |
| 5 realism | pass with caveats — build rates (F4); zero electrolysis (N4); DH share rises to ~16 % |
| 6 prices / costs | pass with caveats — F5 as corrected in C1; biogas lumpiness (N3); no negative prices anywhere (N8) |
| 7 TIMES consistency | pass with caveats — the capped quantity is not the quantity TIMES caps (C2); stale side files (N6) |
| 8 robustness | caveats — single weather year, interior solutions, **and** real run-to-run instability in storage and gas-CC (N7) |

### Commit intent (level 0b)

Previous production log: `docs/logs/2026-09-05_scen_demande_haute_2010_1h_production.md`
at SHA `0f9ce604`. `git log 0f9ce604..d950d061`:

| Commit | Class | Intended behaviour | Observable in this tree | Verdict |
|---|---|---|---|---|
| `7099524b` | docs only (two .md files) | none | n/a | n/a |
| `72c9bef2` power-plant CC option, shipped OFF | physics/config | no result change; `power_plant_cc_from_year: null` | effective config carries `power_plant_cc_from_year: None`; CC available all horizons, and none is built before 2040 anyway (`CCGT CC` 0 / 0 / 327 / 882 MW_e) | pass |
| `2f67b01e` ICEDD solid-biomass potential (master CSV) | config/data | synced potentials | `--check` PASSED; BEWAL `solid biomass` `e_sum_max` is 9 222 GWh/an in every horizon, as `custom_potentials.csv` says | pass |
| `25680656` merge | meta | — | n/a | n/a |
| `8fbc39f3` R1 coke→coal factor | physics | coal load == TIMES | coal for industry 3.706 / 3.141 / 1.019 / 1.819 TWh, all ±0.00 % vs the **regenerated** TIMES rows | pass |
| `8fbc39f3` R2 EV/rail | physics | EV grid draw within 0.02 % | 0.895 / 4.842 / 12.586 / 16.918 TWh, all −0.00 % | pass |
| `8fbc39f3` R4 relaxation reporting | review tooling | `report_relaxed_profiles` lines + review 2.5 | present in all four python logs; review 2.5 WARN matches | pass |
| `d950d061` new `.vd` | config | 2030 converges; 2040 relaxation gone | 2030 optimal in 314 it; 2040 pins fully delivered; `times_file` string correct in all four effective configs — **but** two CSVs derived from the *previous* `.vd` were not re-extracted (N6) | pass with caveat |

TIMES_PyPSA at `3627a53` (= that checkout's HEAD, clean); pypsa2html at
`2c40825` (= HEAD, includes the trade fix `5793e1a`).

**Publication integrity.** `csvs/nodal_capacities.csv` on S3 reproduces the
solved networks exactly (BEWAL onwind 1 568 / 3 977 / 6 500 / 6 500 MW), so the
stale-derivative incident of §9 did not survive into the published tree.

---

### Corrections to the first pass

**C1 — F5 has the 2050 CO₂ duals inverted.** The first pass wrote "in 2050 the
global dual is 0.0, so the full 407 is the national cap". It is the other way
round: `mu(CO2Limit)` = **−407.09** EUR/t and
`mu(co2_limit_per_countryBEWAL)` = **−2.4e−08**, i.e. zero.

| EUR/t | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| global `CO2Limit` | −68.7 | −100.3 | −113.3 | **−407.1** |
| BEWAL national cap | −364.5 | −96.1 | −27.6 | **−0.0** |
| effective BEWAL price | 433 | 196 | 141 | 407 |

In 2050 **not one** of the eight national caps binds (all |mu| < 1e−7); the
whole Walloon carbon price comes from the EU-wide budget. This also **closes
follow-up 4**: the global `CO2Limit` binds in every horizon, so kerosene is
priced throughout — it is, in 2050, the only thing priced at all.

**C2 — the import cap does not measure "one-way inflow".** `import_limit_BEWAL`
caps `Σ_t max(0, net cross-border balance)` — `add_selfsufficiency_constraints`
builds one `net_total` over AC and DC and bounds `Import_p ≥ net_total`. That
nets an export on one border against an import on another *within the same
hour*. Recomputed from the solved networks (physical arriving power, losses
booked as PyPSA books them):

| BEWAL, TWh/a | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| gross inflow, all borders | 11.58 | 13.66 | 19.92 | 24.50 |
| gross outflow, all borders | 11.38 | 12.60 | 16.63 | 16.90 |
| **capped quantity** `Σ max(0, net)` | 2.31 | **2.94** | **6.47** | **10.00** |
| annual net balance | +0.20 | +1.06 | +3.28 | +7.60 |

The cap binds to three decimals in all three capped horizons (duals −9.02 /
−13.63 / −2.97 EUR/MWh). But "Wallonia imports 10 TWh in 2050" is false under
either natural reading: gross inflow is 24.50 TWh, net balance is 7.60 TWh.
Three consequences:

1. Every chart and sentence must name the quantity. `review_run.py`'s 4.3b line
   and the `add_selfsufficiency_constraints` docstring both say "one-way
   inflow" and both are wrong — fix them (follow-up 9).
2. **The measure is resolution-dependent.** At 8 760 h the positive part of a
   net balance is much larger than at TIMES's handful of time slices, so
   transferring the TIMES number verbatim makes the PyPSA cap *tighter* than
   the TIMES one. That is the conservative direction, but it is not equivalence.
3. **Flanders and Brussels are "abroad".** 8.98 TWh of the 24.50 TWh gross 2050
   inflow is intra-Belgian. Net, BEWAL takes +2.97 TWh from Flanders and
   *sends* 1.50 TWh to Brussels.

**C3 — the biomass `e_sum_max` figures quoted under "what passed cleanly" are
not this run's.** The first pass wrote "fully used 2030 (4.824/4.824) and 2040
(8.250/8.250), slack in 2050 (6.377/9.000)". `review_run.py` on the published
tree reports:

| BEWAL `solid biomass`, TWh | used | `e_sum_max` |
|---|---:|---:|
| 2030 | 3.538 | 4.824 |
| 2040 | 10.550 | 11.472 |
| 2050 | 4.772 | 12.222 |

No horizon is "fully used", and the 2040 pair 8.250 = 6.000 + 2.250 is the
potential **before** `2f67b01e` — that bullet describes the 09-06 run. Everything
is inside the documented envelope, which is what the check was for; the
conclusion survives, the numbers do not. (Why 2050 is slack is N1, and it is not
a Walloon statement.)

**C4 — "usable == cap on every BE border" is false in five border-years.**

| border-year | NTC | usable | share |
|---|---:|---:|---:|
| 2040 BE–DE | 2 000 | 1 479 | 74 % |
| 2040 BE–GB | 2 400 | 1 000 | 42 % |
| 2050 BE–DE | 3 200 | 1 510 | 47 % |
| 2050 BE–FR | 7 300 | 4 809 | 66 % |
| 2050 BE–GB | 3 800 | 1 548 | 41 % |

This is **not** a `set_NTCs` convention error — the AC gross-up by `1/s_max_pu`
is correct (2025 BE–FR: `s_nom` 5 071 × 0.7 = 3 550 = NTC), and
`transmission_limit: vopt` makes the NTC a ceiling (`s_nom_max` / `p_nom_max`)
rather than a target. The under-build is endogenous. It still matters: the grid
this run delivers is not the grid the NTC table describes, and BE–GB sits at
41–42 % of its NTC while being at its limit 48–52 % of hours (185–253 MEUR/yr
of congestion rent). Nemo is 1 000 MW in 2025/2030 and 1 548 MW in 2050;
ALEGrO is 1 000 → 1 479 → 1 510 MW. Say which when quoting either.

---

### New findings

**N1 — 2050 European biomass is a corner solution at 1 087 EUR/MWh, and it is
what bought out the TIMES heat mix. (Headline.)**

The EU `biomass limit` binds in every horizon, at −47.4 / −38.5 / −30.5 /
**−1 086.8** EUR/MWh. The 2050 value is not solver noise: every solid-biomass
bus in the model prices at 1 104–1 133 EUR/MWh, and the mechanism is exact.

In 2050 the whole 330.92 TWh potential goes to one place — the exogenous
industrial solid-biomass demand of 303.19 TWh — split 277.36 TWh through
`solid biomass for industry CC` (η 0.90) and 53.56 TWh through the plain link
(η 1.00). Nothing is left for CHP, boilers, biomass-to-liquid or
biomass-to-methanol; in 2040 those still took 62 TWh. One extra MWh of biomass
therefore lets 9 MWh of industrial demand move from the η 1.0 link to the η 0.9
CC link, each capturing ~0.35 tCO₂ at 407 EUR/t ≈ 1.3 kEUR — which is the dual.

Four consequences, all reporting-relevant:

- **The option-B′ absorber penalty no longer holds the heat mix.** At 1 000
  EUR/MWh_th it is *below* the fuel's shadow price, so the solver pays the
  penalty and drops the pin. That is exactly the 2050 rural / urban-decentral
  biomass-boiler relaxation (0.0458 + 0.0402 TWh_th, 86 MEUR) that F6 recorded
  as "expected, tiny". It is expected only because the penalty is too low, and
  the same mechanism will silently drop any future 2050 pin on a scarce fuel.
- **~27.7 TWh of the European potential (8 %) is burned as the CC parasitic
  loss** — the 10 % efficiency penalty on 277 TWh — for the negative-emission
  credit.
- **BEWAL's 4.77 TWh of 2050 biomass is not a Walloon result.** 61.9 TWh of
  *regional* `e_sum_max` sits unused (FR 43.0, DE 11.4, BEWAL 4.45 + 3.00
  transported) because the EU aggregate binds first; the split across regions
  is degenerate. Do not present it as a Walloon supply or Walloon restraint.
- **The whole 2050 biomass story rests on `sector.solid_biomass_import: false`**
  (the F8b decision). With no import channel and an inelastic industrial demand,
  the price of the marginal MWh has no anchor.

Actions: raise `sector.times_heat.profile.penalty` above the fuel's shadow price
(or index it), and put the import channel question back on the agenda.

**N2 — Wallonia exports every tonne it captures: 2.2 / 6.1 / 8.8 / 9.6 Mt CO₂ a
year.**

| Mt/a captured at BEWAL | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `process emissions CC` | 2.162 | 3.602 | 5.052 | 4.856 |
| `solid biomass for industry CC` | — | 1.658 | 1.853 | 1.419 |
| `gas for industry CC` | — | 0.876 | 1.260 | 0.820 |
| `CCGT CC` | — | — | 0.638 | 1.123 |
| `urban central gas CHP CC` | — | — | — | 1.370 |
| **total** | **2.162** | **6.136** | **8.802** | **9.588** |
| **net `CO2 pipeline` export from BEWAL** | **2.162** | **6.136** | **8.802** | **9.588** |

`co2 sequestered` is 0 at BEWAL, BEVLG and BEBRU in every horizon (item 2), so
the two rows are equal by construction: **100 % of Walloon capture leaves the
region by pipeline**, to DE (14.5 Mt/a on the 2030 vintage), FR and LU. For
scale, 2030's 6.14 Mt is 41 % of the entire BEWAL national CO₂ cap (15.00 Mt)
and 2040's 8.80 Mt is 106 % of it (8.33 Mt). The pipeline is built with no
route, permit or acceptance constraint. This is the largest physical assumption
under the Walloon path and belongs on the slide, not in a footnote.

Item 9 is satisfied with room to spare: process + biomass + gas CC gives 8.17 Mt
in 2040 against a 5.08 Mt floor and 7.09 Mt in 2050 against 4.83 Mt.

**N3 — biogas runs in one horizon out of four (this answers follow-up 6).**
BEWAL biogas dispatch is **0.000 / 0.000 / 0.000 / 6.900 TWh** against caps of
8.3 / 8.3 / 4.0 / 6.9 TWh. It is a pure CO₂-price switch: at 78.8 EUR/MWh the
block is out of the money against fossil methane until the effective price
passes roughly 250 EUR/t, and 2050's 407 EUR/t turns it fully on. So 2040's
objective is low partly because a 4 TWh block worth ~315 MEUR/yr stayed off —
**do not read the 2040 cost dip as a trend.** Meeting item 4 asked for 4.0 TWh
in 2040; the model builds the cap and uses none of it, which is worth telling
ICEDD when the citation (17d) is finally supplied.

**N4 — zero electrolysis in Wallonia, in every horizon.** `H2 Electrolysis`
`p_nom_opt` = 0 MW in 2025, 2030, 2040 and 2050. The BEWAL H2 bus is fed only by
`H2 pipeline` (12.76 / 10.32 / 1.43 / 1.56 TWh in) and drained by pipeline plus
a small fuel cell (0.77 / 0.61 / 0 / 0 TWh). The 2 128 MW of 2050 `H2 pipeline`
has `capital_cost = 0`. Wallonia is a transit corridor, not a hydrogen producer;
neither the pipeline capacity nor the throughput may be plotted as a Walloon
hydrogen result.

**N5 — European onshore wind halves after 2030 and fixed-tilt PV disappears
(F2, now quantified).**

| GW onwind | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| DE | 63.9 | 115.0 | 92.0 | 63.2 |
| FR | 23.2 | 31.0 | 21.4 | **8.4** |
| NL | 7.0 | 16.2 | 24.2 | 19.8 |
| GB | 16.3 | 29.0 | 31.1 | 46.6 |

France ends with 36 % of its present fleet. In parallel, `solar` (fixed-tilt
ground) is **exactly 0.00 GW in every country in 2050** while `solar-hsat` and
`solar rooftop` grow. Both patterns are consistent with the 25-year lifetimes
B7 finally pushed into the model (`onwind` 30 → 25 y, PV 40 → 25 y): the
standing fleet retires inside the horizon and myopic foresight re-picks the
cheapest sub-carrier with no memory of what was there. This is the European
price signal that sets every Walloon investment decision, so it is not a
neighbour-country footnote. Until it is resolved: report **total wind** and
**total PV**, never the sub-carriers, and do not publish a neighbour-country
wind trajectory. DE 2030 onwind is still exactly 115.00 GW — the collapsed
corridor of 17b, unchanged.

**N6 — the `.vd` swap left two TIMES-derived side files behind.** Both
`data/walloon/times_pv_rooftop_share.csv` and
`data/walloon/times_industrial_capture.csv` state in their own header that they
were extracted from `scen_central_demande_haute_v2_260903_0309.vd`; this run
uses `…v01_260907_0709.vd`. Re-extracted from the export actually used:

| | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|
| rooftop share, shipped | 0.7083 | 0.7372 | 0.7757 | 0.7889 | 0.8010 |
| rooftop share, new `.vd` | 0.7022 | 0.7275 | 0.7663 | 0.7829 | 0.7880 |
| `STORAGEMININD` kt, shipped | — | 4 364.6 | 5 076.9 | 5 140.3 | 4 842.5 |
| `STORAGEMININD` kt, new `.vd` | — | 4 268.8 | 5 065.2 | 5 128.5 | 4 842.5 |

Effect on this run is small — rooftop PV is over-allocated by 0.04 / 0.13 /
0.20 GW and the 2040 capture floor is 11.7 kt (0.23 %) high on a floor that is
slack anyway. The defect is that **nothing declares the dependency**: neither
file is an output of a rule that reads `sector.times_file`, and no test compares
them against the active export. Same failure class as B7 and F7's undeclared
`add_existing_baseyear` inputs.

**N7 — storage and gas-CC are not stable across run vintages (level 8).**
BEWAL, GW, three vintages of the same scenario (`c68d1474` 09-05 / `0f9ce604`
09-06 / `d950d061` 09-08):

| carrier | 2040 | 2050 |
|---|---|---|
| battery | 3.21 → 3.62 → **5.83** | 3.77 → 7.19 → **13.99** |
| CCGT | 4.21 → 2.89 → 5.63 | 3.32 → 2.00 → 4.74 |
| `CCGT CC` (fuel input) | 0 → 3.14 → 0.57 | 0.13 → 3.14 → 1.53 |
| solar rooftop | 6.23 → 8.96 → 10.79 | 5.25 → 10.01 → 12.13 |

`onwind` (6.5 GW, cap-bound), `ror` and `OCGT` are stable to the digit. The
2050 battery fleet has nearly quadrupled over three runs; `CCGT CC` has swung
by a factor of six in both directions. Part of the drift is real input change
(new `.vd`, the 6.0 → 9.222 TWh biomass potential), which is exactly why these
are not point results: **report a range**. System-level aggregates are steady —
`total costs` moved −1.4 / −1.1 / −0.6 / −0.3 % from 09-06, and the 2050 CO₂
dual −440 → −407 EUR/t.

**N8 — no negative price in any horizon, and 2025 is a 165 EUR/MWh
counterfactual.** BEWAL `AC` marginal price, EUR/MWh:

| | mean | p05 | p50 | p95 | min | max | h ≤ 0 | h > 200 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025 | 165.7 | 95.2 | 169.5 | 224.2 | 1.6 | 284.6 | 0 | 2 437 |
| 2030 | 110.9 | 5.6 | 133.8 | 180.1 | 0.0 | 1 345.8 | 0 | 191 |
| 2040 | 105.0 | 1.7 | 117.9 | 204.2 | 0.0 | 328.5 | 0 | 486 |
| 2050 | 95.2 | 1.7 | 86.4 | 223.8 | 0.0 | 319.0 | 0 | 1 198 |

Not one hour below zero, in any horizon, with 15.1 GW of Walloon PV and 6.5 GW
of wind by 2050; curtailment stays at 0.1 / 1.9 / 3.1 / 3.5 % on onshore wind.
That is a consequence of `load_shedding: false`, no negative bidding and a
well-connected 8-node system — state it before putting this distribution next
to an observed day-ahead one. Note also that `metrics.csv`
`electricity_price_mean` (133.3 / 95.3 / 94.1 / 90.0) is the **unweighted mean
over all eight nodes**, not BEWAL.

### First-pass findings, retained

**F1 — pull verification failure; stale tree briefly published (ops).** §9.
Confirmed harmless to the published numbers: the S3 CSVs reproduce the S3
networks. The tooling defect stands.

**F2 — extractor preconditions are tribal knowledge (ops).** §9. The working
invocation is
`AWS_PROFILE=intervectoriel EXTRACTOR_BASE_CONFIG=config_extraction_OET.yaml ./cluster/nic5.sh extract`.

**F3 — Sankey mapping holes, not solve defects (reporting).** Re-confirmed:
`enc_pe` is one-sided in all four horizons (out 7.53 / 9.43 / 9.99 / 4.35 TWh,
in 0), and 2025 `elc_se` −0.618, `vap_se` −0.090 TWh. The buses balance to
0.00 % everywhere (level 3); the report graph does not. Do not cite `enc_pe`
throughput.

**F4 — build rates above historical (judgement call).** BEWAL onwind 2025→2030
+482 MW/yr (1 568 → 3 977) against ~100–150 MW/yr historical; rooftop PV
+567 MW/yr to 2030 and +618 MW/yr to 2040 against ~200–300 MWp/yr.
`limit_max_growth` is off. Any build-rate chart needs the caption.

**F5 — CO₂ prices, as corrected by C1.** 433 / 196 / 141 / 407 EUR/t effective;
2025 sits on a base year that is already a decarbonised counterfactual
(sequestration cap 0 binding at 435.6 EUR/t, EU `biomass limit` ≤ 0 binding),
so 2025 duals are not observed prices. The non-monotonic shape is real:
the price falls to 141 EUR/t in 2040 and triples by 2050.

**F6 — 2050 biomass micro-pins relaxed.** Kept, but the explanation is N1, not
"the fuel simply is not there": Wallonia had 4.45 TWh of its own unused
`e_sum_max`. The fuel was not *affordable* — the EU aggregate binds and the
penalty is below the resulting price.

**F7 — local/cluster pypsa skew (process).** Solved networks are pypsa 1.2.1;
pin the cluster env to `pixi.lock`.

### What passed cleanly, verified independently

- **Provenance.** Commit is an ancestor of HEAD; effective config identical to
  the repo config; four horizon configs differ only in `planning_horizons`;
  2010 snapshots against the 2010 cutout; `resolution_sector: 1h`; correct `.vd`
  string in all four.
- **Soft link, ±0.00 % on every carrier and horizon**, against demand files
  regenerated from this run's `.vd` — EV (R2), coal (R1), industry electricity,
  gas, naphtha, solid biomass, kerosene, and the BEWAL electric total
  (20.328 / 27.274 / 46.595 / 58.283 TWh). The only load outside the TIMES rows
  is `agriculture machinery electric`, a constant 0.272 TWh.
- **Balances.** Every BEWAL bus carrier and the Belgian AC+LV total close to
  0.00 %; the BEV node closes with smart **and** natural charging; EV battery
  cyclic.
- **Caps and potentials.** All 22 agg rows inside their corridor; BEWAL onwind
  ≤ 6 500 MW (binds 2040 and 2050), rooftop ≤ 46 000 MW, ground PV ≤ 13 000 MW.
- **Item-by-item, on this run:** no gas storage in Wallonia (item 1, `e_nom_opt`
  = 0 in every horizon); Belgian `co2 sequestered` = 0 (item 2); Boucle du
  Hainaut delivers 9 600 MW usable BEWAL–BEVLG from 2040 (item 3); BE offshore
  pinned at 2 273 MW in 2025 and 2030 (item 11); rooftop share 70.83 / 77.57 /
  80.10 % hit exactly (item 8, against the shipped file — see N6); industry-CC
  floor met with headroom (item 9); process-emissions load gross at
  4 411.6 / 3 946.1 / 5 433.9 / 5 108.0 kt (item 12); aviation out of the
  national caps (item 13); nuclear 2 030 MW_e Belgium-wide in 2030 and 2040,
  3 000 + 3 000 MW_e in 2050 (items 10 and the TIMES trajectory); no
  power-plant CC before 2040 (item 18); water pits 8.2 / 22.7 / 36.9 /
  74.8 GWh_th, under the fleet ceiling (item 16).
- **Capacity factors** all inside their windows (onwind 25.4–26.3 %, PV
  10.8–11.1 %, hsat 12.8–12.9 %, ror 26.3 %); heat-pump COP 2.42–2.52 with heat
  delivered rising 1.49 → 3.35 → 14.71 → 19.46 TWh_th.
- **District heating goes to buildings, not to DAC.** BEWAL DH load 0.25 / 1.29
  / 1.54 / 3.92 TWh_th, `sector.dac: false`, no DAC link anywhere. The failure
  mode of the 2026-08-18 run is gone.

### Numbers that must not be published as-is

- **Any "Walloon imports" figure without naming the metric** (C2). The cap is on
  `Σ max(0, hourly net)`; gross inflow and annual net are 2.5× and 0.8× it.
- **Any 2050 biomass number, Walloon or European** (N1). The EU cap binds at a
  price with no anchor and the regional split is degenerate.
- **BEWAL battery and `CCGT CC` capacity as point values** (N7). Ranges only.
- **Neighbour-country wind and PV sub-carrier trajectories** (N5). Totals only.
- **Walloon hydrogen** (N4). No electrolysis exists; the pipeline is transit and
  is zero-capital-cost.
- **Zero-capital-cost capacities** — 2050 distribution grid 9 944 MW, gas
  pipeline 7 500 MW, BEV charger 4 194 MW, water-pit charger/discharger
  2 857 MW, H2 pipeline 2 128 MW, battery/home-battery dischargers. Degenerate
  variables, not results.
- **Any capacity at three significant figures.** Crossover 0 interior solutions;
  a 1 % delta between runs is not signal.
- **2025 capacities or prices as "today"** — 2025 is an optimisation under 2025
  caps at a 433 EUR/t effective carbon price, with a mean Walloon electricity
  price of 165.7 EUR/MWh.
- **`costs.csv` / `nodal_costs.csv` totals without the convention** —
  non-extendable capital included, existing nuclear annuitised at new-build
  cost; `total costs` 5.62e11 against a 3.48e11 Gurobi objective in 2025.
- **Walloon nuclear from BEWAL nodal rows** — every nuclear link is booked to
  `EU` by `bus0` (168–259 GW of fuel input in the `EU` row, zero in BEWAL).
  Recompute grouped on `bus1`.
- **The `enc_pe` Sankey throughput** and any 2050 electricity-node residual (F3).
- **Build-rate charts without the historical-pace caption** (F4).
- **The interconnection capacity implied by `ntc_*.csv`** — three BE borders are
  built to 41–74 % of it in 2040/2050 (C4).

### Review follow-ups

| # | Action | Owner | State |
|---|---|---|---|
| 1 | `cmd_pull` must abort (not warn-continue) on rsync exit ≠ 0; md5-check the four networks against the cluster before postprocess | ops/code | open |
| 2 | Retry the standard pull without `--whole-file` next run; consider making `--whole-file` the default for `*.nc` | ops | open |
| 3 | Fix extractor preconditions: ship the walloon template or correct `EXTRACTOR_BASE_CONFIG`; export `AWS_PROFILE` in `extract_explorer.sh`; record the `EXTRACTION_CONFIG` patch | ops/code | open |
| 4 | Confirm the global `CO2Limit` binds every horizon | modeller | **closed** — it does, at −68.7 / −100.3 / −113.3 / −407.1 EUR/t (C1) |
| 5 | Decide on `limit_max_growth` given F4 build rates | modeller | open |
| 6 | Check the 8.3 TWh biogas block before reading the 2040 cost dip | reviewer | **closed** — biogas is 0/0/0/6.9 TWh; the 2040 dip is partly the block staying off (N3) |
| 7 | Verify this run in the Explorer dropdown | operator | open |
| 8 | Regression tests for F1 (pull-verify) and F3 (Sankey `enc_pe` / `elc_se` closure) | code | open |
| 9 | Rename the capped quantity everywhere — `review_run.py` 4.3b, the `add_selfsufficiency_constraints` docstring, pypsa2html trade panels (C2) | code | new |
| 10 | Raise `sector.times_heat.profile.penalty` above the 2050 fuel shadow price, or index it; a pin that is silently bought out is the failure this project keeps finding (N1) | modeller/code | new |
| 11 | Declare `sector.times_file` as an input of whatever reads `times_pv_rooftop_share.csv` / `times_industrial_capture.csv`, or add a test that fails when the header `.vd` differs from the active one (N6) | code | new |
| 12 | Put the ~9 Mt/a Walloon CO₂ export on the meeting agenda — it has no route, permit or acceptance constraint and is the largest physical assumption in the path (N2) | modeller | new |
| 13 | Decide whether the 25-year `onwind` / PV lifetimes are intended, given the DE/FR wind collapse and the disappearance of fixed-tilt PV they produce (N5, F2) | modeller | new |
