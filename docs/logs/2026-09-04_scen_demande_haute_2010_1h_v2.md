# Solve log — scen_demande_haute @ 2010, 1h (TIMES vd v2, rooftop split)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-04 19:04 → 2026-09-05 02:00 (4/4 optimal) |
| Operator | Muse agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + overlay `config/scenarios.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | `development_plan` `c68d1474` (vd v2 swap, regenerated transfers, rooftop split, share on, item 9 on) |
| Outcome | **4/4 optimal** |

## 2. Goal of the run

Full 1h / 2010 four-horizon solve of `scen_demande_haute` on the new TIMES vd
(`scen_central_demande_haute_v2_260903_0309.vd`, received 2026-09-04 via S3),
with the rooftop fix: 2025 fleet split 1.77 GW rooftop / 0.9 GW ground,
TIMES share imposed from 2030 on (70.8 % 2030, 80.1 % 2050 on the new vd),
item 9 on (B3/B4). Follows the killed rooftop attempt on vd v1
([`2026-09-04_scen_demande_haute_2010_1h_rooftop_killed.md`](2026-09-04_scen_demande_haute_2010_1h_rooftop_killed.md)).

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v2_260903_0309.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, 8760 hourly, weight 1.0 |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier (`Method 2`), 16 threads / 100 GB, `BarConvTol 1e-5`, `Crossover 0`, `BarHomogeneous: 1`; NIC5 `hmem` (fall back to `batch` per job if Priority-blocked) |
| Key scenario overrides | rooftop split 1770/898 + share on (2030+); industry CC floor on (STORAGEMININD v2: 4365/5077/5140/4842 kt); 6a off; NTC floor 9600 from 2035; Belgian CO₂ store 0; aviation off |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local | 30 steps, full rebuild from the new vd; split applied (983.1 + 786.9 = 1 770 MW rooftop) |
| LP solve | NIC5 **`hmem`** (16 cpus/task, 100 GB) | orchestrator pid 3646416, zero queue wait; 2025 job 11116832, 2030 11117043, 2040 11117446, 2050 11117809 |
| Post-processing (CSVs, plots) | local | `nic5.sh postprocess` 08:05–08:2x, 11/11 steps |
| HTML report (pypsa2html) | local | via postprocess → `https://pypsa.squoilin.eu/scen_demande_haute_20260905/` (200) |
| Explorer CSV extraction (ClimAct) | local | `nic5.sh extract` 08:26 (49 pypsa + 3 strategy + vd); stale v1 `.vd` removed from `explorer/times/` before upload |

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → results verified) | 2026-09-04 19:04 → 2026-09-05 02:00 solve-complete (~7 h); postprocessing the same morning |
| Prepare (network build) | 30 steps from the new vd (demands, heat targets, 2025 brownfield) |
| Push to cluster | ~1 min |
| Queue wait (cluster) | none (hmem had room) |
| Solve 2025 | **1 h 14** wall, Optimal **3.55890314e11** |
| Solve 2030 | **2 h 14** wall, Optimal **3.63618342e11** |
| Solve 2040 | **1 h 41** wall, Optimal **2.91120598e11** |
| Solve 2050 | **1 h 31** wall, Optimal **2.68575853e11** |
| Pull results | rsync `--whole-file` (delta path corrupts, as on 3 Sept), md5-verified |
| Post-processing + plots | `nic5.sh postprocess` (touch, CSVs, plots, sankey, pypsa2html, S3) |
| pypsa2html report | in postprocess |
| ClimAct extraction | 49 pypsa + 3 strategy + `.vd`, 08:26 |

vd v1 → v2 deltas (same extractor): rooftop share 71.36/85.81 → **70.83/80.10 %**
(2030/2050; v2 has no 2025 row); industry CC 4365/5077/**5140/4842** kt
(2045/2050 +20/+16 kt); nuclear trajectory unchanged (2045 0.5+0.25,
2050 1+1 GW; v2 adds 1 MW GEN3 in 2040 — noise).

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (rows / cols / nonzeros) | |
| Peak RAM per solve | 2025 **30.6 GB** · 2030 **35.3 GB** · 2040 **37.0 GB** · 2050 **36.5 GB** (sacct MaxRSS; all well under the 100 GB request) |
| Peak RAM local phases | |
| Disk footprint | |

## 7. Results

| Horizon | Status | Objective (EUR/a or model units) |
|---|---|---|
| 2025 | **Optimal** (~1h14 wall) | **3.55890314e11** |
| 2030 | **Optimal** (~2h14 wall) | **3.63618342e11** |
| 2040 | **Optimal** (~1h41 wall) | **2.91120598e11** |
| 2050 | **Optimal** (~1h31 wall) | **2.68575853e11** |

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260905_walloon_scen_demande_haute/` (full tree, 4 networks, fresh explorer) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260905/` (49 pypsa + 3 strategy + v2 `.vd`; stale v1 `.vd` deleted) |
| Explorer display label | `demande-haute-2010-1h` |
| Explorer CSVs | extracted 08:26 from this run's networks |
| TIMES vd staged | `scen_central_demande_haute_v2_260903_0309.vd` |
| Verified in Explorer dropdown | not yet (test env; verify before promoting) |

## 9. Issues encountered and fixes

- **Post-run finding (review): 2025 overshot the tightened pins.**
  `review_run.py` failed 4 aggregate checks, all 2025: BEWAL solar-all
  4 088 vs pin 2 668, BEWAL onwind 2 349 vs 1 560, BE/solar-all 11 207 vs
  9 751, BE/onwind 4 135 vs 3 337. Root cause, found by reproducing
  `add_CCL_constraints` standalone (the CCL itself is sound — it writes a
  382 MW ceiling and the toy LP lands exactly on the pin): the 2025
  *extendable candidates* entered the solve with `p_nom_min` from the
  IRENASTAT current-year share (BEWAL solar 1 802 MW = the 2021–2024 diffs
  binned into grouping-year 2025; onwind 655 MW; same pattern in every
  country), and the max branch can only clip its ceiling *up* to a forced
  floor. The assignment exists "for the year 2020"; with a 2025 base year
  it double-counts against pins that already encode the full fleet.
  **Fix (post-run, in tree):** `electricity.baseyear_reconcile_forced_build`
  scales `DateIn`-into-base-year rows down to the pin headroom
  (`scripts/walloon_scripts/baseyear_forced_build.py`, guarded by
  `test_baseyear_forced_build.py` — 5 cases). Rebuilt brownfield:
  solar-2025 floor 381.9 MW (= 2 668 − 2 286), onwind-2025 floor 0.
  Remaining data conflict (not code): BEWAL onwind standing (1 694 MW
  IRENASTAT) exceeds the 1 560 MW Energy-Balance pin by ~134 MW — flagged
  by the CCL warning and the guard; needs the fleet-source decision, the LP
  stays feasible via the clip. The BE-group FAILs are the same forced-floor
  mechanism on BEVLG/BEBRU candidates (documented §4.1 myopic-reset class).
  **Not re-run**: the fix is prepare-level only (no LP shape change beyond
  the intended pins); next production run carries it.

## 10. Follow-ups / pending

- Re-run with the base-year reconciliation fix before any cross-vintage or
  2025-capacity claim (this run's 2025 new-build is overstated by the forced
  IRENA share: +1 420 MW utility solar, +655 MW onwind at BEWAL).
- BEWAL onwind 2025 pin (1 560 MW) vs standing fleet (1 694 MW IRENASTAT):
  reconcile the sources (Energy Balance preliminary vs IRENASTAT).
- §11 critical review **done 2026-09-05** — see below. Verdict: **not
  publishable as a Walloon PV or self-sufficiency result**; nine findings,
  four of them new (European VRE decay after 2030, Explorer import/export
  orientation, CO₂ trajectory inconsistency, solid-biomass double count).

## 11. Critical review

Done 2026-09-05 against [`../run-review-checklist.md`](../run-review-checklist.md),
on the S3 tree pulled to `results/_aws_review/20260905_walloon_scen_demande_haute/`
(`aws s3 sync`, 1.8 GB, 4 networks + CSVs + explorer). Mechanical half:
`review_run.py --full` → **PASS 148 · INFO 26 · WARN 17 · FAIL 4**.

**Verdict: not publishable as a Walloon PV or self-sufficiency result.** The
energy accounting is clean and the TIMES pins that were the point of this run
(rooftop share, industry CC, nuclear, NTC floors) all landed. What fails is the
*level* of Walloon PV, the European backdrop that prices it, and three data
inconsistencies that were not previously logged (CO₂ trajectory, solid-biomass
double count, Explorer import/export orientation). Findings new to this review:
**F2** (European VRE decay after 2030), **F4** (Explorer import/export
orientation), **F5** (CO₂ trajectory), **F8** (solid biomass), **F11** (process
emissions), **F12** (per-node CO₂ caps) and **F13** (2025 carbon capture).

**Status after the 2026-09-05 walkthrough.** F1 and F2 are **understood and
accepted for now**: the mechanisms are sound, PV is simply uneconomic at this
carbon price with this much cheap import available, and the fix belongs to the
*next* run (import cap on, CO₂ trajectory reconciled) rather than to this one.
F9 turned out not to be a defect and is closed. The reporting half of F1 is
fixed: pypsa2html `83a59b0` now splits the PV capacity charts three ways and
stops counting solar-thermal collectors as PV. The remaining blockers to
publication are unchanged — F3/F4 (self-sufficiency and its inverted Explorer
table), F5 (CO₂ trajectory), F7 (2025 pins) and F8 (solid biomass).

### 11.1 Provenance (level 0) — **pass**

| Item | Value |
|---|---|
| `git_commit` | `c68d1474` (`development_plan`), ancestor of HEAD |
| Effective config | `configs/config.base_s_adm___<year>.yaml`, all four identical apart from `planning_horizons` |
| Weather / cutout | 2010 / `europe-2010-sarah3-era5` — agree |
| `resolution_sector` | `1h` |
| `sector.times_file` | `scen_central_demande_haute_v2_260903_0309.vd` — the intended v2 |
| `agg_p_nom_limits.file` | `agg_p_nom_minmax_demande_haute.csv` |

Features this run **predates**: `electricity.baseyear_reconcile_forced_build`
(commit `0def1c0a`) is absent from all four effective configs — the §9 fix is
not in this run, which is what F7 is.

Solve (level 1): 4/4 `Optimal`, barrier with `Crossover 0` (interior point —
do not read three significant figures off any single capacity), `large bounds`
/ `large rhs` warnings in every horizon. Peak RAM 30.6–37.0 GB.

### 11.2 Commit intent (level 0b) — commits `87552368..c68d1474`

| Commit | Claim | Observable in this tree | |
|---|---|---|---|
| `4459a96c` | add `year_currency`, central gas CHP / solid-biomass CHP / SMR / H2 (l) tank | carriers exist; `urban central gas CHP` 899 MW_e and `gas CHP CC` 1 868 MW_e built in 2050, `SMR`/`SMR CC` present at ~0 | pass |
| `788cc75a` | PV and onwind lifetime 25 y | `lifetime = 25.0` on every 2050 solar/onwind generator | pass — **and it is the mechanism behind F1/F2** |
| `28870714` | NTC floors, import-limit constraint, industry-CC and rooftop-share pins | Boucle-du-Hainaut floor: BEWAL–BEVLG usable 9 600 MW in 2040 **and** 2050; rooftop share on; CC floor on; import limit coded, flag off | pass |
| `3160022d` (B1) | CCL group key carrier-aware, `n.buses.country` no longer mutated | solved `buses.country` = `['', BE, DE, FR, GB, LU, NL]` — no `BEWAL`/`BEVLG` codes | pass |
| `3160022d` (B2) | `BE,offwind-all` 2025 **and** 2030 pinned at 2 262 | solved BE offshore 2 273 MW in both (inside the 0.5 % corridor) | pass |
| `3160022d` (item 16) | water-pit `e_nom_max` = 4 weeks of that node's DH demand | BEWAL 2030 cap 193.9 GWh_th vs 4 weeks = 98.6 → **2× (one cap per vintage)**; 2050 550.7 vs 310.7 → 1.8×. Not binding (`e_nom_opt` 22.8 / 88.4) | pass with the known **B9** per-vintage caveat |
| `b4ba7733` | 2025 Walloon PV/onwind installed capacities 2 668 / 1 560 | present in the caps file; **violated in the solve** (F7) | fail — data right, solve wrong |
| `dbdd8cb0` | base-year fleet split 1.77 GW rooftop / 0.9 GW ground | rooftop vintages 983.06 + 786.94 = **1 770.0 MW exactly**; standing ground only 516.1 MW, the rest forced (F7) | pass on the split |
| `dbdd8cb0` | item 9 (industry CC floor) back on | `process emissions CC` 592 MW, `solid biomass for industry CC` 739 MW, `gas for industry CC` 512 MW in 2050 — floor reachable, LP feasible | pass |
| `c68d1474` | vd v2 swap; rooftop share 70.83 / 80.10 % | solve lands on 0.70830 (2030), 0.77570 (2040), 0.80096 (2050) — the file to 4 decimals | pass |
| `93bdf848` `14c3e9ff` `32ab38d6` `38c12845` `a1b1d556` | merges / docs | — | n/a |

### 11.3 Verdicts by level

| Level | Verdict |
|---|---|
| 0 provenance | pass |
| 0b commit intent | pass, one fail (`b4ba7733`, = F7) |
| 1 solve | pass with caveats (interior solution, conditioning warnings) |
| 2 soft link | **not verifiable** — `resources/<prefix>/<scenario>/wallon_demands_<year>.csv` is not in the published tree, so §2.2/2.3 (EV grid draw, per-carrier demand identities) could not be run. Heat-pump capacity is non-decreasing (1 283 → 1 580 → 5 557 → 7 950 MW_th) |
| 3 accounting | **pass** — every BEWAL bus balances to <1e-3 TWh; Belgium AC+LV closes to 0.00 %; BEV node closes in all four horizons (natural + smart charging both drawn — the 2026-08-18 hole is gone) |
| 4.1 aggregate limits | **fail** (4 rows, 2025 only — F7) |
| 4.2 Walloon potentials | pass on onwind/solar/rooftop; **fail on solid biomass** (F8) |
| 4.3 interconnection | pass |
| 4.4 CO₂ | **fail** — F5 (trajectory inconsistency, national caps inert after 2025), F6 (2025 counterfactual), F12 (per-node caps are a population split), F13 (2025 CCU) |
| 7 process emissions (item 12 / B4) | **pass** on the transfer, pass-with-caveats on its surroundings — F11 |
| 5 realism | **fail** — F1 (Walloon PV), F2 (European VRE decay); both accepted as understood on 2026-09-05 and deferred to the next run |
| 6 prices / costs | pass with caveats — F9 (resolved: grid-connection adder; cost table still unpublished), F10 |
| 7 TIMES consistency | **fail** — PV level 2.4× below TIMES (F1) |
| 8 robustness | not run (no comparable 1h vintage of the same code) |

---

### F1 — Walloon PV peaks in 2040 and then falls; the item-8 pin fixes the ratio and loses the level

**Observed.** BEWAL PV, `p_nom_opt` totals over all vintages (MW):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `solar` (ground, fixed) | 2 318 | 2 317 | 1 802 | **0** |
| `solar-hsat` | 0 | 0 | 0 | 1 305 |
| `solar rooftop` | 1 770 | 5 627 | 6 233 | 5 250 |
| **total** | **4 088** | **7 945** | **8 035** | **6 554** |
| rooftop share | 0.433 | 0.7083 | 0.7757 | 0.8010 |
| TIMES vd total (rooftop + utility) | — | 6 898 | **15 419** | **17 375** |

**What it should be.** The vd this run was built from says 11.96 GW rooftop +
3.46 GW utility in 2040 and 13.92 + 3.46 GW in 2050. PyPSA delivers 52 % of the
2040 level and **38 % of the 2050 level**, and moves in the wrong direction over
the last step (−1 481 MW, −18 %).

**Why.** Three things compose, and the arithmetic closes exactly:

1. **Retirement.** Lifetime is 25 y (`788cc75a`, and it is the agreed value in
   `input_parameters_for_models.csv`). Between 2040 and 2050 the 2025 ground
   vintage (1 802 MW) and the 2020 rooftop vintage (983 MW) both die — 2 785 MW
   gone.
2. **The model rebuilds only 1 305 MW, and *zero* rooftop.** The 2050 extendable
   rooftop generator has `p_nom_max` = 40 750 MW of headroom and
   `p_nom_opt` = **0.0**.
3. **The item-8 constraint is a floor on rooftop, so it acts as a ceiling on
   everything else.** `add_rooftop_share_constraint` writes
   `rooftop ≥ share × solar-all`, so each MW of ground PV must be bought with
   4.03 MW of rooftop at 97 329 EUR/MW/a (vs 80 933 for hsat, at a *lower*
   capacity factor: 11.1 % vs 12.9 %). The blended cost of marginal PV lands at
   ~94 EUR/MWh against a BEWAL mean price of 101.5 EUR/MWh, i.e. at break-even
   once the capture-price discount is taken. So the model builds exactly the
   ground quota that the *legacy* rooftop fleet licenses and stops:

   > 5 249.7 / 0.80096 − 5 249.7 = **1 304.6 MW** — the observed `solar-hsat` is
   > 1 304.5 MW. That identity is the proof that the share constraint, not
   > economics or potential, sets 2050 Walloon PV.

**Also.** From 2030 on the model builds **no fixed-tilt ground PV anywhere** —
`solar` → ~0 at BEWAL, BEVLG, BEBRU, DE, FR. `solar-hsat` strictly dominates it
(+2 % capex, +16 % capacity factor). Any chart that plots `solar` alone reads as
"Wallonia loses its PV"; report **total PV** and state the split.

**And.** `solar-hsat` has **no `p_nom_max` row in `custom_potentials.csv`**. Its
2050 Walloon bound is the raw atlite potential, **38 736 MW**, not the documented
13 000 MW ground-PV potential that `solar` carries. The 13 GW Walloon
ground-mounted limit is therefore not enforced on the only ground carrier the
model actually builds. It does not bind today (1.3 GW) — it would in any
scenario where PV is attractive.

**Do.** Pin the TIMES rooftop and utility **capacities** (add `BEWAL, solar-all`
and a rooftop level row to `agg_p_nom_minmax_demande_haute.csv` for 2035–2050),
not the ratio. Add a `BEWAL, solar-hsat` `p_nom_max` row, or fold hsat into the
`solar` 13 GW ceiling. Until then the Walloon PV trajectory must not be published.

**Cost trajectory: PV gets *more* expensive, not less.** Checked 2026-09-05 on
the run's own cost table (`costs_<year>_processed.csv`; the solved
`capital_cost` values match it to the euro). There is **no learning curve**:

| EUR/MW/a, as delivered to the generator | 2025 | 2030 | 2040 | 2050 | 2025→2050 |
|---|---:|---:|---:|---:|---:|
| `solar` (ground) | 77 320 | 78 779 | 79 037 | 79 060 | **+2.3 %** |
| `solar-hsat` (tracking) | 79 188 | 80 625 | 80 724 | 80 933 | **+2.2 %** |
| `solar rooftop` | 94 115 | 95 649 | 96 862 | 97 329 | **+3.4 %** |
| `onwind` | 166 573 | 166 312 | 165 864 | 165 743 | −0.5 % |

Two causes compose:

- **`custom_costs.csv` sets one `all`-horizon investment** — solar-utility
  525.825 EUR/kW, solar-rooftop 920.194, onwind 1 450 — so CAPEX is flat from
  2025 to 2050. Only `solar-utility single-axis tracking` has per-year values,
  and only −1.9 % over 25 years. For reference, technology-data v0.14 has
  utility PV falling roughly −28 % over the same window.
- **The FOM *percentage* still rises** (solar-utility 2.198 → 2.529 %/a,
  rooftop 1.257 → 1.606, hsat 2.037 → 2.553), because technology-data
  calibrates FOM% against its own *declining* CAPEX so that absolute O&M stays
  flat. Applied to a flat Walloon CAPEX it makes the annuity grow. `onwind`
  escapes because its FOM% was overridden and falls (1.235 → 1.178 %/a).

At the modelled Walloon capacity factors that is **81 / 72 / 100 EUR/MWh** for
ground / tracking / rooftop in 2050, against a BEWAL mean price of
101.5 EUR/MWh. PV is at the money and getting worse, which is exactly why the
model retires it rather than rebuilding.

> **Decision (2026-09-05).** Nothing here is *wrong* — the constraint is sound,
> the retirements follow an agreed 25-year lifetime, and the flat CAPEX is a
> deliberate Walloon override. PV is simply too expensive to enter at this
> carbon price with this much cheap import available. **Left as is for now.**
> The test is whether PV comes back when the system is squeezed: re-check F1
> after a run with the BEWAL import cap on (F3) and/or a tighter CO₂
> trajectory (F5). If PV still does not enter, the flat CAPEX is the next
> thing to revisit — not the rooftop-share constraint.
>
> Reporting is fixed in the meantime: pypsa2html `83a59b0` splits the capacity
> charts into ground / rooftop / tracking (and stops counting solar-thermal
> collectors as PV — that was +446 MW_th on 4 088 MW in 2025), while the
> capacity-factor charts keep one capacity-weighted `solar` bar. See
> pypsa2html `docs/DESIGN_DECISIONS.md` D19.

### F2 — the European VRE fleet decays after 2030, and it is what prices every Walloon investment

`agg_p_nom_minmax_demande_haute.csv` carries `min` pins for **2030 only**. There
is no solar or onwind row for 2035, 2040, 2045 or 2050 for any country. Under
myopic foresight with 25-year lifetimes the consequence is total capacity (GW):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| DE solar-all | 90.3 | **215.0** | 178.5 | **138.4** |
| DE onwind | 63.9 | **115.0** | 92.0 | **63.2** |
| FR onwind | 23.2 | 31.0 | 21.4 | **8.4** |
| GB solar-all | 18.0 | 47.0 | 37.4 | 29.0 |
| NL solar-all | 24.2 | 30.0 | 28.5 | 20.7 |
| NL onwind | 7.0 | 11.5 | 9.7 | 5.3 |

Germany ends 2050 with **less onshore wind than in 2025** and 36 % less solar
than in 2030; France loses 73 % of its onshore wind. Offshore is the exception
(it has 2040/2050 floors in the file) and grows throughout.

The 2030 step is the mirror image: it is met at **exactly** the build-rate
ceiling — DE offshore adds 22 892 MW against `2.0 × 2 289 × 5 = 22 890 MW`,
DE solar 24.9 GW/yr against a 15.1 GW record, DE onwind 10.2 GW/yr against a
4.9 GW record. So 2030 is a forced build at twice any observed rate, and
2040/2050 are unconstrained decay. Neither is a scenario.

This is not cosmetic: it is the European price signal behind every Walloon
number. It is also the same mechanism as F1 — Wallonia is not a special case.

**Do.** Add 2040/2050 floors for the neighbours from their own NECP/scenario
paths, in the same file that already carries the 2030 pins.

> **Decision (2026-09-05).** Same call as F1: the mechanism is understood and
> nothing is malfunctioning — the 2030 pins are floors, there are no floors
> after them, and 25-year lifetimes do the rest. **Left as is for now**, and
> re-checked on the next run once imports are capped (F3) and the CO₂
> trajectory is reconciled (F5): both tighten the system that is currently
> letting the European fleet decay. Until then, **do not publish neighbour
> capacities for 2040 or 2050**, and read the 2040/2050 Walloon price signal
> as conditional on a European system that is not a scenario.

### F3 — the 10 TWh import cap is off, and the run breaches it by 2×

`self_sufficiency.self_sufficiency_constraint: false` in all four effective
configs. Item 6a is documented as withdrawn "pending a decision on the number"
(B6), so this is deliberate — but the numbers it was meant to hold are now
measurable on a solved 1 h network, and they are far outside the proposed values.

BEWAL cross-border electricity, computed over the four AC corridors and both
legs of the ALEGrO DC pair (TWh/a):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `Import_p` analogue (hourly positive part of net inflow) | 0.84 | 2.79 | **14.10** | **21.18** |
| proposed cap (`limit_twh`) | — | 2.94 | 6.47 | 10.0 |
| **net annual balance** | −3.83 | −1.52 | **+12.46** | **+20.41** |

2050 net imports by corridor: DE **+12.31**, BEVLG **+9.53**, BEBRU +2.66,
LU +1.54, FR +1.51, i.e. Wallonia covers ~29 % of a ~70 TWh electricity demand
from outside. In 2025 it is still a net exporter (−3.8 TWh) while importing
7.9 TWh from Germany over ALEGrO at a ~90 % load factor.

So the constraint would bind hard from 2040. The 2.94 / 6.47 / 10.0 values were
sized on 6 h *net* tables; on a 1 h run the quantity they cap is 2.2× the 2040
value and 2.1× the 2050 value. **Re-derive the numbers before turning item 6a
on, and expect it to change the solution materially** — this is not a
tightening that will pass through unnoticed.

### F4 — the published Explorer `imports_exports.csv` reads backwards

`explorer/pypsa/imports_exports.csv` is the file that feeds the Wallonie
Explorer. Verified against the solved 2025 network on five corridors:

| file row | file value | what the network says |
|---|---:|---|
| `exports · Wallonia · Brussels` | 0.193 | Brussels→Wallonia inflow, 0.193 |
| `exports · Wallonia · France` | 0.085 | France→Wallonia inflow, 0.085 |
| `exports · Wallonia · Germany` | 8.109 | Germany→Wallonia inflow, 7.895 at the Walloon end (8.109 at the German end, before line losses) |
| `imports · Wallonia · Brussels` | 2.957 | Wallonia→Brussels outflow, 2.961 |
| `imports · Wallonia · France` | 6.647 | Wallonia→France outflow, 6.890 |

The two blocks use **opposite orientations** (`exports`: row = destination,
column = origin; `imports`: row = origin, column = destination), so reading the
row labelled `Wallonia` under `exports` gives Wallonia's *imports*. A reader who
takes the row label at face value sees Wallonia exporting ~17.6 TWh in 2050 when
the model has it importing 20.4 TWh net — the sign of the headline
self-sufficiency message is inverted.

Source: `graph_extraction_transform.py` (ClimAct extraction repo), around the
`imports`/`exports` `groupby` pair — `exports` groups `["node","node_1",…]`,
`imports` groups `["node_1","node",…]` and then renames the levels back, so the
`nodes` column means a different thing in each block. **Resolve with ClimAct
before promoting this scenario out of the test environment.**

### F5 — the global and national CO₂ trajectories disagree, and the national caps are inert after 2025

`config/input_parameters_for_models.csv` (`config:budget_national`,
*"Trajectoire globale … hors aviation internationale & UTCATF"*, `year_rule=interp`)
gives the authoritative anchors **2030 = 64.8 %, 2040 = 45.0 %, 2050 = 5.0 %**
of 1990.

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `budget_national` (per-country caps) | 0.648 | 0.648 | 0.450 | 0.050 |
| `co2_budget` (system `CO2Limit`) | 0.648 | **0.450** | **0.250** | 0.050 |

`budget_national` matches the agreed anchors. `co2_budget` does **not** — it
applies the 2040 anchor in 2030 and a value in 2040 (0.250) that is not an
anchor at all. Because the global cap is the tighter of the two, it is the one
that binds, and the agreed Walloon trajectory is never enforced:

| | sum of national caps | global `CO2Limit` | BEWAL realised | BEWAL cap | BEWAL dual |
|---|---:|---:|---:|---:|---:|
| 2025 | 1 437.5 Mt | 1 471.4 Mt | 21.60 | 21.60 | **−364.3 EUR/t** |
| 2030 | 1 437.5 Mt | **1 021.8 Mt** | 17.09 | 21.60 | ~0 |
| 2040 | 998.3 Mt | **567.7 Mt** | 10.56 | 15.00 | ~0 |
| 2050 | 110.9 Mt | 113.5 Mt | 0.56 | 1.67 | ~0 |

Every national cap is slack in 2030, 2040 and 2050 (duals ≈ 1e-8). The
checklist's "the per-country caps sum to exactly the global cap" holds in 2025
and 2050 only; in 2040 the national caps sum to **176 %** of the global cap.

Consequence for reporting: the Walloon emission path in this run is a
by-product of a European cap that is roughly a decade ahead of the agreed
trajectory, not a result of the Walloon target. Either sync `co2_budget` to the
same anchors, or state plainly that the binding constraint is European.

### F6 — 2025 is a 433 EUR/t counterfactual, not a base year

Every Belgian, French and Dutch national cap binds *exactly* in 2025:
BEVLG −367.2, BEWAL −364.3, FR −263.8, NL −252.5, BEBRU −215.6 EUR/t, on top of
the global −68.5. The effective Walloon carbon price is
**433 → 108 → 130 → 426 EUR/t** across the four horizons — the base year is more
carbon-constrained than 2030 *and* 2040.

The BEWAL AC price follows: mean **161.1** EUR/MWh in 2025 with **2 752 hours
above 200 EUR/MWh** (the Belgian day-ahead average in 2024 was in the 60–80 EUR/MWh range), then 94.3 / 103.3 /
101.5. No hour below 0 and none above 406 in any horizon — neither
surplus-driven collapse nor scarcity pricing exists in this model.

Do not present the 2025 column as "today", in any figure or table.

### F7 — the four aggregate-pin FAILs (already in §9), confirmed

| 2025 | total | pin (+0.5 % corridor) | extendable tranche |
|---|---:|---:|---:|
| BEWAL solar-all | 4 088 | 2 668 (2 681) | 1 802 |
| BEWAL onwind | 2 349 | 1 560 (1 568) | 655 |
| BE solar-all | 11 207 | 9 751 (9 800) | 5 754 |
| BE onwind | 4 135 | 3 337 (3 354) | 1 738 |

Root cause and fix are in §9; `baseyear_reconcile_forced_build` is not in this
run. Note the coupling to F1: the 1 802 MW of forced 2025 ground PV — about
1 420 MW of which should not exist — is precisely the vintage that retires in
2050 and produces the PV cliff.

### F8 — Walloon solid biomass exceeds the documented potential, twice over

The BEWAL `solid biomass` generator carries `e_sum_max` = **8.00 / 8.00 / 8.25 /
9.00 TWh** — the 6.0 TWh Valbiom domestic potential **plus** the
`solid biomass transported` pellet allowance (2.0 / 2.0 / 2.25 / 3.0), on the
same generator. On top of that, `solid biomass import` links deliver
**1.74 / 0.90 / 4.50 / 6.00 TWh** into BEWAL — exactly the separate
`solid biomass import e_nom` (4 000 / 4 000 / 4 500 / 6 000 GWh).

Total Walloon solid biomass consumed: **7.74 / 10.07 / 12.75 / 6.47 TWh**
against 6.0 domestic + 2.25 documented pellet imports = 8.25 TWh in 2040. The
double-specification flagged in checklist §4.2 is live, and **both** caps are
being used at once. The first three figures are exactly the `enc_pe` Sankey WARN
(`in 0, out 7.738 / 10.074 / 12.750 / 5.830 TWh`) — a source node, so one-sided
by construction, but the magnitude is the finding.

It matters: the 2050 `biomass limit` dual is **−1 041.6 EUR/MWh**. Biomass is
the scarcest commodity in the 2050 system, so a 4.5 TWh over-allocation is worth
billions and it carries the BECCS credit that puts BEWAL 2050 under its cap
(`solid biomass for industry CC` −2.24 Mt, `biogas to gas` −1.37 Mt against
4.2 Mt gross fossil).

Related: the Walloon biogas block is all-or-nothing as the checklist warns —
0 TWh in 2025/2030/2040, then **6.90 TWh in 2050, exactly on the ICEDD cap**.
Read the 2050 Walloon CO₂ balance knowing it flips on this single block.

### F9 — capital costs: **resolved 2026-09-05, not a defect**

The 13–31 % gap between the solved `capital_cost` and
`investment × (annuity + FOM)` is the **`electricity grid connection`** adder:
187 012 EUR/MW, 40 y, 7.5 %, FOM 2 % → **18 589 EUR/MW/a**, added in
`add_electricity.py` to every carrier built from an atlite profile. It is
exactly +18 589 on `solar`, `solar-hsat` and `onwind` at every node, and
**+0 on `solar rooftop`**, which is created in `prepare_sector_network.py`
(line 1755) straight from `costs.at["solar-rooftop", "capital_cost"]` — rooftop
PV sits behind the distribution grid and pays no transmission connection. The
run's own cost table reproduces all four numbers to the euro.

Two things to keep from it:

- **It is a real 31 % penalty on ground PV and 0 % on rooftop** (12 % on
  onshore wind). That is a defensible modelling choice, but it is not in
  `common_parameters.md` and it materially changes the ground-vs-rooftop
  ranking behind F1. Write it down.
- The residual finding is the *trajectory*, not the level — flat CAPEX plus a
  rising FOM percentage, see F1.

**Still do.** Ship `costs_<year>_processed.csv` with every run. This took a
detour through a sibling scenario's resources tree to close, and the published
artefacts should be self-sufficient.

### F10 — numbers that must not be published as-is

- **`csvs/prices.csv` and `metrics.csv::electricity_price_mean` are unweighted
  means across all eight nodes, not Walloon prices.** BEWAL AC is
  161.1 / 94.3 / 103.3 / 101.5 EUR/MWh against the files' 133.1 / 89.0 / 97.8 /
  97.1. BEWAL `land transport oil` is a flat **194.0** EUR/MWh in 2050 against
  the file's 24.25. Recompute per node before quoting any price.
- **`lignite` at −38.7 EUR/MWh in 2050** — a dual on a carrier with no flow.
- **Zero-capital-cost capacities** (2050): `electricity distribution grid`
  9 946 MW, `BEV charger` 4 194, `urban central water pits charger/discharger`
  3 435 each, `home battery discharger` 1 252, `H2 pipeline` 3 094. Degenerate
  variables, not capacity results.
- **Nuclear is absent from BEWAL's rows of `nodal_capacities.csv` /
  `nodal_costs.csv`** (`bus0` = EU uranium). Recompute on `bus1`: BEWAL
  1 992 MW_e / 15.40 TWh (2025), 1 030 / 7.88 (2030), 1 030 / 7.83 (2040),
  3 000 MW_e / 22.76 TWh (2050).
- **`costs.csv` total ≠ objective** by the usual convention (569.5 vs
  355.9 bn EUR/a in 2025): the CSV annuitises non-extendable capital.
- **Walloon H2**: 3.8–5.0 GW of `H2 pipeline`, `H2 Electrolysis` ≈ 0, net H2
  through the Walloon bus 0.35–0.71 TWh. Wallonia is a transit corridor, not a
  hydrogen producer — do not describe it as one.
- **`solar` vs `solar-hsat`** are near-identical technologies; the split between
  them is a cost-ranking artefact and will move between vintages.

### F11 — the TIMES process-emissions transfer (item 12 / B4) lands correctly, but it is bolted onto a differently-parameterised Belgium

**The transfer itself is right.** `BEWAL_potentials.apply_process_emission_load`
overwrites the `BEWAL process emissions` Load with the annual TIMES volume from
`custom_potentials.csv`, and the solved networks carry it to the kilotonne:

| BEWAL `process emissions` Load, kt/a | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `custom_potentials.csv` (TIMES `VAR_Comnet INDCO2P` + `VAR_FOut INDCO2c`) | 4 411.62 | 3 946.10 | 5 433.90 | 5 108.04 |
| in the solved network | **4 411.6** | **3 946.1** | **5 433.9** | **5 108.0** |

B4 (gross = emitted + captured) is doing what it was meant to: in 2040 the load
is 5 433.9 kt = 357.0 emitted + 5 076.9 captured, and the item-9 floor
(5 076.88 kt) is **reachable and exactly binding** — realised industry capture is
5 076.9 kt. On the net inventory (357 kt) it would have been infeasible, which is
what the 3 September withdrawal was about. That is fixed.

Three things around it are not clean:

1. **The bus carries more than the TIMES figure.** `naphtha for industry` routes
   its steam-cracker share onto the same bus (port 2), adding **+60.8 / +55.5 /
   +94.1 / +82.2 kt/a**. Total through the Walloon process-emissions bus is
   4 472 / 4 002 / 5 528 / 5 190 kt, i.e. 1.4–1.7 % above the pin. Small, but it
   is a **double-count risk**: if TIMES's `INDCO2` already includes steam-cracker
   process CO₂, it is now counted twice. Check the vd and, if so, net the naphtha
   term out of the pin.
2. **Only Wallonia is TIMES-sourced.** BEVLG and BEBRU keep the PyPSA-Eur
   default, which is the Belgian national figure × population share, and it
   follows PyPSA-Eur's own industry transformation rather than TIMES:

   | process-emissions Load, kt/a | 2025 | 2030 | 2040 | 2050 |
   |---|---:|---:|---:|---:|
   | BEWAL (TIMES) | 4 412 | 3 946 | **5 434** | **5 108** |
   | BEVLG (PyPSA-Eur) | 4 630 | 4 310 | 3 320 | 2 300 |
   | BEBRU (PyPSA-Eur) | 40 | 40 | 40 | 40 |

   Wallonia's process emissions **rise 16 %** to 2040 while Flanders' **fall
   50 %**, and from 2040 on Wallonia has more industrial process CO₂ than
   Flanders. That may well be right — Wallonia holds most of Belgium's cement
   and lime capacity — but it is an artefact of two unrelated parameterisations
   meeting in one network, not a modelled result. Say so, or transfer Flanders
   from TIMES too.
3. **Capture is modelled as energy-free.** `process emissions CC` has `bus0` =
   process emissions, `bus1` = atmosphere, `bus2` = `co2 stored` and **no bus3 or
   bus4** — the PyPSA-Eur comment is *"assume enough local waste heat for CC"*.
   So the only cost is 493 467 EUR/(t/h)/a of capex at a 90 % capture rate =
   **62.6 EUR/t at full load**. Real cement/lime capture needs ~2–3 GJ_th/t plus
   electricity. The abatement cost is understated, which is what makes F13 happen.

**Where the CO₂ goes.** Wallonia has `co2 storage e_nom_max = 0` (documented), so
every captured tonne leaves by pipeline: **2 367 / 3 602 / 5 077 / 9 222 kt/a**.
In 2050 that is a **9.2 Mt/a Walloon CO₂ export**, on 1 192 MW (t/h) of CO₂
pipeline. Europe-wide in 2050 the model captures 378.5 Mt and sequesters
373.2 Mt/a — against a 1 000 Mt `co2_sequestration_potential` that does **not**
bind, so this is economics at a 426 EUR/t carbon price, not a cap. Both numbers
are infrastructure claims that need a sentence of defence wherever they appear.

### F12 — the per-node CO₂ caps are the Belgian 1990 inventory split by *population*, sector by sector

`add_co2limit_country` builds the RHS from
`resources/<run>/co2_totals_adm_<year>.csv`. That file is produced by
`build_energy_totals.py`:

```python
co2 = co2.loc[pop_layout.ct].fillna(0.0)
co2.index = pop_layout.index
co2 = co2.multiply(pop_layout.fraction, axis=0)   # <- population share, every sector
```

`pop_layout_base_s_adm.csv` gives BEWAL **0.321914**, BEVLG 0.577164,
BEBRU 0.100922, and those fractions reproduce every row of the file exactly. The
file is identical across the four horizons, so it is a fixed 1990 reference —
that part is right.

Derivation, verified end to end (Mt CO₂, 1990):

| sector (1990) | BEWAL | BEVLG | BEBRU | BE |
|---|---:|---:|---:|---:|
| electricity | 7.577 | 13.584 | 2.375 | 23.537 |
| road non-elec | 6.335 | 11.358 | 1.986 | 19.680 |
| residential non-elec | 6.598 | 11.829 | 2.068 | 20.496 |
| industrial processes | 5.860 | 10.507 | 1.837 | 18.204 |
| industrial non-elec | 4.362 | 7.821 | 1.368 | 13.551 |
| services non-elec | 1.382 | 2.477 | 0.433 | 4.292 |
| agriculture | 1.035 | 1.855 | 0.324 | 3.215 |
| domestic navigation | 0.116 | 0.209 | 0.037 | 0.362 |
| rail non-elec | 0.072 | 0.128 | 0.022 | 0.222 |
| **baseline (aviation excluded)** | **33.337** | **59.770** | **10.451** | **103.557** |

× `budget_national` → 21.602 / 21.602 / 15.001 / 1.667 Mt for BEWAL, which is
exactly what the solved `GlobalConstraint` rows carry. Excluded from the RHS:
`international navigation`, `LULUCF`, `waste management`, `other`, `indirect`,
plus aviation (item 13). Item 13 is verifiably symmetric — the BEWAL 2050 cap
moved 1.717 → **1.667 Mt** when aviation left both sides.

**What is wrong with it.**

- **A population key is not an emissions key.** The same 0.321914 is applied to
  electricity, steel, cement, agriculture and shipping alike. The giveaway is
  `international navigation`: Wallonia is assigned **4.285 Mt** of 1990 maritime
  bunker emissions despite having no seaport. That row happens to be excluded
  from the cap, but it shows the split is mechanical, not an inventory.
- **The mismatch is largest in the sector the model now treats most carefully.**
  Wallonia is given 32.2 % of Belgium's 1990 industrial process emissions
  (5.860 Mt), while the network's own 2025 Walloon process-emissions load — the
  TIMES number from F11 — is 4 412 kt, i.e. **75 % of its 1990 baseline**. The
  population-scaled Flemish load is 4 630 kt against a 10 507 kt baseline, i.e.
  **44 %**. So the one node parameterised from a real regional inventory starts
  far closer to its (population-derived) 1990 baseline than its neighbours do,
  and its cap is correspondingly harder. **The left-hand side is regional data
  and the right-hand side is a population share** — they are not the same object.
- **By 2050 the cap is smaller than the process-emissions load alone.** BEWAL
  cap 1.667 Mt vs a gross process-emissions load of 5.108 Mt — **3.1×**. The cap
  is only met because 4.87 Mt of that is captured (item 9) and exported, and
  because biogenic capture returns −2.24 Mt (`solid biomass for industry CC`) and
  −1.37 Mt (`biogas to gas`). Strip the biogenic credits and Wallonia is over its
  2050 cap. Every 2050 Walloon CO₂ statement rests on those two blocks.
- **It does not bind anyway.** As F5 shows, only the 2025 national caps are
  active; 2030/2040/2050 have duals ≈ 0. So this RHS is currently shaping the
  results in the base year only — but it is the number the study will be read as
  "the Walloon CO₂ target", so it has to be defensible.

**Do.** Replace the population split for Belgium with the regional 1990
inventories (AwAC for Wallonia, VMM for Flanders, Bruxelles Environnement) —
at minimum for `electricity`, `industrial processes` and `industrial non-elec`,
where the regional structure is nothing like the population structure. Failing
that, state in every deliverable that the per-node caps are a population
disaggregation of the Belgian national 1990 total.

### F13 — 2025 builds 4 Mt/a of industrial carbon capture and a cross-border CO₂ pipeline; sequestration *is* capped, capture is not

Sequestration is capped and the cap holds. `sector.co2_sequestration_potential`
is **0** for 2025, all eight `co2 sequestered` links have `p_nom_opt = 0` and
zero flow, and `co2_sequestration_limit` binds with a dual of **435.3 EUR/t** —
the model would sequester if it were allowed to.

What is not capped is the **capture equipment and the utilisation route**. In
2025 the model builds `process emissions CC` at **BEWAL 327 MW and BEVLG 205 MW
(t/h) — and nowhere else in Europe** — captures 3 984 kt/a, and pipes it out:

| 2025, Europe-wide `co2 stored` | kt/a |
|---|---:|
| in — `process emissions CC` (BEWAL 2 367 + BEVLG 1 616) | **+3 984** |
| out — `Sabatier` (2 129 MW, in DE) → synthetic methane | −2 746 |
| out — `methanolisation` (648 MW, in LU) → methanol | −1 238 |
| out — `co2 sequestered` | **0** |

So it is **CCU, not CCS**: 2.4 Mt/a of Walloon industrial CO₂ becomes German
synthetic methane feedstock in the base year, carried on a CO₂ pipeline network
that the model also builds "by 2025" (BEWAL→DE 337, BEWAL→LU 141,
BEVLG→BEWAL 185 t/h). None of this exists.

**Why the model does it.** Two things multiply:

- Capture is energy-free (F11.3), so it costs **62.6 EUR/t** at full load —
  capex only.
- The 2025 Walloon effective carbon price is **432.8 EUR/t** (68.5 global +
  364.3 national, F6).

A 7× margin. It is not a numerical accident and it will not go away by tightening
tolerances — at that carbon price the model *should* capture everything it can.
And it is Belgium-only because the 2025 national caps bind only in BE/FR/NL/LU;
DE and GB have slack, so no capture is worth building there.

The 2035+ item-9 floor is not involved: `times_industrial_capture.csv` has no row
before 2035, so 2025 and 2030 capture is entirely economic.

**Do.** This is the clearest single symptom of F6 — the 2025 horizon is a
deeply-decarbonised counterfactual, not a base year. Either calibrate 2025
(exogenous 2025 capacities, no free investment) or state everywhere that the
2025 column is "the cheapest 2025 system that meets a −35.2 % cap", and add
2025/2030 `p_nom_max = 0` on `process emissions CC`, `Sabatier` and
`methanolisation` if the base year is meant to look like reality.

### 11.4 What passed and is worth stating

- Energy accounting is clean: every BEWAL bus carrier balances to <1e-3 TWh,
  Belgium AC+LV closes to 0.00 % on 200.9–402.9 TWh of gross supply, cyclic
  stores return to their start, and the **BEV node now closes in all four
  horizons** (smart 0.008/0.302/2.032/2.740 + natural 0.878/4.454/10.284/13.868
  TWh in, EV demand out, gap 0.000) — the 2026-08-18 natural-charging hole is
  fixed.
- Nuclear follows the agreed trajectory exactly: BE 2 030 MW_e in 2040
  (BEWAL 1 030 + BEVLG 1 000), 6 000 MW_e in 2050 (3 000 + 3 000), CF 86–88 %,
  `p_min_pu` 0.783 / `p_max_pu` 0.883 — inflexible-nuclear on with the 0.1 margin.
- Boucle-du-Hainaut NTC floor delivers 9 600 MW usable on BEWAL–BEVLG in 2040
  and 2050. All interconnection checks pass; ALEGrO 1 000 MW in 2025/2030 (1 833
  in 2040, 3 161 in 2050 — an assumption that belongs in writing).
- Rooftop share and industry-CC floor both bind cleanly and the LP stays
  feasible — items 8 and 9 are mechanically correct. Their *calibration* is F1.
- Capacity factors are all inside the plausibility windows (BEWAL onwind
  24.4–26.2 %, PV 11.1 %, hsat 12.9 %, ror 26.3 %, heat-pump COP 2.32–2.52).
- DAC off; Walloon CO₂ storage 0 with capture exported by pipeline
  (478 → 1 192 MW); no DH-to-DAC pathology.
- Walloon onwind respects 6 500 MW, `solar` 13 000 MW, rooftop 46 000 MW.
- Curtailment rises sensibly with penetration (BEWAL onwind 0.3 → 3.4 → 4.3 →
  7.2 %).

### 11.5 Follow-ups

1. **F1** — pin TIMES PV *capacity* for 2035–2050 in
   `agg_p_nom_minmax_demande_haute.csv`; add a `BEWAL, solar-hsat` `p_nom_max`
   (or fold hsat into the 13 GW `solar` ceiling). Regression test: total BEWAL
   PV non-decreasing across horizons.
2. **F2** — add 2040/2050 solar and onwind floors for DE/FR/GB/NL/BE.
3. **F3** — re-derive `limit_twh` from this run's 1 h numbers before enabling
   item 6a; expect a materially different solution.
4. **F4** — resolve the `imports_exports.csv` orientation with ClimAct; block
   promotion out of the test environment until then.
5. **F5** — sync `co2_budget` to the `input_parameters_for_models.csv` anchors,
   or document that the binding cap is European. Add a test that the per-country
   caps sum to the global cap in every horizon.
6. **F7** — re-run with `0def1c0a` before any 2025 or cross-vintage claim
   (already in §10).
7. **F8** — decide which solid-biomass cap is intended and remove the double
   count; add a test that BEWAL solid-biomass consumption ≤ domestic + one
   import allowance.
8. **F9** — publish `costs_<year>_processed.csv` with every run (the
   reconciliation itself is closed). Document the `electricity grid connection`
   adder in `common_parameters.md`, and decide whether PV CAPEX should keep a
   flat `all`-horizon value while its FOM percentage rises (F1).
9. **F11** — check whether the TIMES `INDCO2` pin already includes steam-cracker
   process CO₂; if so, net the `naphtha for industry` term (55–94 kt/a) out of
   `custom_potentials.csv`. Decide whether BEVLG/BEBRU should also come from
   TIMES, and add an energy input to `process emissions CC`.
10. **F12** — replace the population split of the Belgian 1990 baseline with the
    regional inventories (AwAC / VMM / Bruxelles Environnement), at least for
    `electricity`, `industrial processes` and `industrial non-elec`. Add a test
    that the three Belgian baselines sum to the national one and that no node is
    assigned `international navigation` it cannot have.
11. **F13** — decide whether the 2025 horizon is a calibration or an
    optimisation. If a calibration, set `p_nom_max = 0` in 2025/2030 on
    `process emissions CC`, `Sabatier`, `methanolisation` and the CO₂ pipeline.
12. **Level 2 gap** — publish `wallon_demands_<year>.csv` and
   `heating_targets_<year>.csv` in the S3 tree so the soft-link identities can
   be checked on a published run instead of only locally.
