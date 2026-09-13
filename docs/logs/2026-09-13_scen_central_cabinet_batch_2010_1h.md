# Solve log — `scen_central`, September 2026 cabinet batch (2010, 1 h)

## 1. Identification

| | |
|---|---|
| Scenario | `scen_central` (reference case of the 14-scenario cabinet batch) |
| Date | 2026-09-12 22:30 → 2026-09-13 05:17 CEST |
| Config | `config/config.walloon.yaml` (+ `cluster/config_cluster.yaml` on the cluster) |
| TIMES export | `data/walloon/scen_central_v01_260911_1109.vd` |
| Weather year | 2010 (`europe-2010-sarah3-era5`) |
| Resolution | `clustering.temporal.resolution_sector: 1h` |
| Horizons | 2025 / 2030 / 2040 / 2050, myopic |
| Repo branch | `development_plan` |
| Run recipe | `docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md` |

## 2. Goal of the run

Reference case for the Wednesday cabinet presentation, and the baseline every
other scenario in the batch is read against. It is also the run that proves the
three things new in this batch: `run.shared_resources.policy: base`, the
regenerated cost table carrying ICEDD's inflated fuel prices, and the
per-scenario TIMES softlink extraction (§3 of the recipe).

## 3. Main parameters

As `config/config.walloon.yaml` at `6b62d043` plus the three fixes of §9 below.
Central scenario takes no `config/scenarios/*.csv` override file: it uses
`custom_costs.csv`, `custom_potentials.csv` and
`agg_p_nom_minmax_demande_haute.csv` directly. `co2_budget` 2030 = 0.45,
`budget_national` 2030 = 0.45 for all eight regions (the realiste pair is what
relaxes those; see its own log).

## 4. Execution — where and how

Preprocessing local (16 cores), solve on NIC5 `batch` partition, 16 cpus / 80 GB
per solve job, Gurobi 13.0.2 via the `nic5-login1` token server.
Thirteen 2010 scenarios ran as one Snakemake orchestrator with
`MAX_SLURM_JOBS=16`; all thirteen were submitted and RUNNING within four minutes
of launch, with no queueing (the `batch`-over-`hmem` choice of `cluster/config.sh`
is vindicated — see §6).

`scen_central_2013` ran concurrently from a **separate cluster directory**
(`/scratch/.../pypsa-wal-2013`, cloned BeeGFS-side so it cost no WAN transfer),
because two Snakemake orchestrators cannot share one working directory's lock.

## 5. Timings

| horizon | barrier iterations | solve time | objective |
|---|---:|---:|---:|
| 2025 | 312 | 5 038 s (1 h24) | 3.667019e+11 |
| 2030 | 292 | 6 194 s (1 h43) | 3.758719e+11 |
| 2040 | 243 | 5 138 s (1 h26) | 2.799588e+11 |
| 2050 | 251 | 5 501 s (1 h32) | 2.639852e+11 |
| **total** | | **≈ 6 h04** | |

Wall-clock for the whole 13-scenario batch was ~7 h with everything in parallel,
against ~85 h in series.

Transfer legs (workstation uplink is the slow one, measured on the night):

| leg | rate | volume | time |
|---|---|---:|---:|
| push | 17.7 Mbit/s | 1.2 GB on the wire (6.8 GB scope) | 11 min |
| pull | 85 Mbit/s | ~13 GB, spread over four incremental pulls | ~30 min total |

## 6. Resource usage

Peak RSS 22.4 / 28.3 / 29.8 / 29.9 GB at 2025 / 2030 / 2040 / 2050 — identical to
the 2026-09-07 production run, against the 80 GB requested. `hmem` was not needed
and would have serialised the batch onto three nodes.

## 7. Results

Headline BEWAL trajectory (from `review_run.py --full`):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| onshore wind (MW) | 1 568 | 3 977 | **6 500** | **6 500** |
| solar rooftop (MW) | 1 770 | 3 345 | 7 910 | 9 012 |
| solar tracking (MW) | 13 | 894 | 3 164 | 3 753 |
| solar ground (MW) | 898 | 897 | 382 | **0** |
| nuclear (MW_e) | — | — | 1 030 | 3 000 |
| heat-pump COP (effective) | 2.49 | 2.43 | 2.44 | 2.49 |
| effective BEWAL CO₂ price (EUR/t) | 456 | 186 | 141 | **478** |
| one-way import (TWh) | — | 2.94 | 6.47 | 10.00 |

## 8. Publication (Wallonie Explorer / S3)

**Not published.** Post-processing was run with `SKIP_S3_UPLOAD=1 HTML_PUBLISH=0`
deliberately: review follow-up R1 below is unresolved, and publication is an
outward-facing step that should be a human decision. Local `csvs/`, `graphs/` and
`html/pypsa/` are complete. To publish: `RUN_NAME=scen_central ./cluster/nic5.sh publish`.

## 9. Issues encountered and fixes

| # | Issue | Fix |
|---|---|---|
| 1 | `cluster_network` and `simplify_network` died with `TypeError: Object of type function is not JSON serializable`. `clustering_for_n_clusters` did `aggregation_strategies.get("buses", dict())` — which **aliases** `config["clustering"]["aggregation_strategies"]` because `buses: {}` has existed in `config.default.yaml` since the Pydantic merge (`8b064878`) — then `setdefault` wrote two lambdas into the live config, which `n.meta = dict(snakemake.config, …)` cannot serialise on export. Latent since January; exposed by `policy: base` because it changed which rules run unscoped | Copy instead of alias, in both scripts |
| 2 | `prepare_sector_network` refused every scenario at 2025: `TIMES 2025 BEV fleet share 0.0028 is below the road-electricity energy share 0.0036`. The guard compares a **car-only** count share against an **all-road** energy share; its message accounts for the denominator carrying freight but not for the numerator carrying non-car electricity. Wallonia has ~199 kveh of two/three-wheelers, 48 % electric already in 2025, doing **2.9× the electric km of cars** in this export | Guard now gated on its own premise (`CAR_DOMINATED_ROAD_ELECTRICITY = 0.80`): hard error where cars carry ≥80 % of electric road km (2030/2040/2050, at 96–97 %), loud warning below (2025, at 25.5 %). See `docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md` §14.3 |
| 3 | Every per-scenario `html/pypsa/index.html` redirected to `BEWAL_overview_scen_central.html`, which exists only in the central tree — 12 of 13 reports opened on a 404. `config/pypsa2html.yaml` carries one `landing.scenario`, correct for the combined report, applied verbatim by pypsa2html to per-scenario ones | `scripts/walloon_scripts/fix_scenario_report_index.py` repoints each index at the landing page beside it. Idempotent; leaves pypsa2html and the combined report untouched |
| 4 | `cluster/probe.sh` reported `0/4` and `STOPPED-PARTIAL` for scenarios with demonstrably solved networks, and a blank Slurm column throughout (Snakemake names jobs with UUIDs, so no job maps to a scenario) | Not fixed — monitoring used a direct file-count matrix instead. **Worth fixing before the next batch**; as it stands the probe would not have detected a real stall |

## 10. Follow-ups / pending

* Publish to S3/Explorer once R1 is settled (§8).
* Fix `cluster/probe.sh` (issue 4) — it is the batch's designated stall detector
  and it does not work on a Snakemake-submitted batch.
* Logs for the realiste pair, the nuclear sweep and `scen_central_2013` follow.

---

## 11. Critical review

Against `docs/run-review-checklist.md`. Mechanical pass:
`python scripts/walloon_scripts/review_run.py results/walloon/scen_central --full`
→ **PASS 191 · INFO 31 · WARN 14 · FAIL 0** (exit 0).
Full output: `review_central_full.txt` (session scratch).

### Commit intent (level 0b)

The three commits this batch rests on do what they say: `de96e610` (framework +
shared resources), `d9752839`/`6b62d043` (2030 RES floors retired, Belgian floors
dropped for the realiste pair only). `test_central_keeps_the_belgian_2030_floor`
pins that the drop did not leak into the central case, and §4.1 of the review
confirms it at runtime: central still carries `BE/onwind` and `BE/solar-all`.
`build_common_parameters.py --check --all-scenarios` printed `CHECK PASSED` before
launch, so every generated input matches the master table it claims to come from.

### What passed cleanly

* **Soft-link fidelity (level 2) is exact.** Every transferred carrier matches
  TIMES to ±0.00 % at every horizon — industry electricity, gas, naphtha, solid
  biomass, kerosene, coal, and the total BEWAL electric load (2025: 19.783 vs
  19.783 TWh; 2030: 26.728 vs 26.728). EV grid draw equals the TIMES
  `electricity road` figure exactly (2025: 0.103 vs 0.103; 2030: 4.050 vs 4.050),
  which is the identity `docs/ev-charging-softlink.md` §3.1 exists to protect.
* **Accounting (level 3) closes everywhere**, including the slow per-bus sweep:
  largest signed residual 2.16e-07 TWh; Belgium AC+LV closes to 0.00 % on 201.6 TWh
  gross.
* **Constraints (level 4) respected**: all 22 aggregate-capacity corridors hold;
  the self-sufficiency cap binds at exactly 2.94 / 6.47 / 10.00 TWh, the TIMES
  `Transfo_Imp` values, with a shadow price that decays sensibly
  (−18.51 → −9.04 → −3.09 EUR/MWh); heat-pump capacity is non-decreasing.
* **Capacity factors** all inside their expected bands at all four horizons
  (onwind 25.7–26.2 %, rooftop PV 11.1 %, ror 26.3 %).

### Findings

**F1 — the Walloon onshore-wind potential binds from 2040, and it sets the answer.**

```
2040 BEWAL onwind: 6 500 MW vs p_nom_max 6 500
2050 BEWAL onwind: 6 500 MW vs p_nom_max 6 500
```

The optimiser takes every MW of wind the potential allows from 2040 on. The
central case's Walloon wind fleet is therefore **not an economic result after
2030 — it is the assumption `custom_potentials.csv` imposes.** Any sentence in
the presentation of the form "the model finds X GW of wind is optimal" is wrong
for 2040 and 2050; the honest statement is that wind is potential-limited and the
shadow value of additional Walloon wind potential is positive. This is the single
most important thing to get right in the cabinet narrative, and it also means a
sensitivity on the 6 500 MW potential would be more informative than any of the
cost sensitivities in this batch.

**F2 — 2030 wind implies a build rate ~3× anything Wallonia has achieved.**

```
[ WARN ] onwind 2025→2030: +482 MW/yr (1 568 → 3 977 MW)
[ WARN ] solar rooftop 2030→2040: +456 MW/yr (3 345 → 7 910 MW)
```

Against ~100–190 MW/yr observed for wind in 2023–24 and ~100 MWc of PV in 2025
(`docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md` §11.1). Note the 2030 floor was
deliberately set non-binding at 2 248 MW and the model cleared it by 77 %: the
3 977 MW is the optimiser's own choice, not a constraint. This strengthens rather
than weakens the realiste sensitivity's premise — the gap between central and
realiste is a statement about **deployment rates**, not costs.

**F3 — at 2050 biomass is extraordinarily scarce, and two TIMES heat pins go undelivered.**

```
2050 biomass limit <= 3.309e+08   mu = −1 222.99      (BINDING)
[ WARN ] 2050 biomass boiler on rural heat:            0.0000 of 0.8068 TWh_th (100 % undelivered)
[ WARN ] 2050 biomass boiler on urban decentral heat:  0.0000 of 0.7921 TWh_th (100 % undelivered)
```

A shadow price of ~1 223 EUR/MWh on the biomass budget is two orders of magnitude
above the 2040 value (−24.61) and coincides with the 2050 CO₂ price jumping back
to 478 EUR/t. The optimiser refuses to put any biomass in decentral boilers and
leaves 1.599 TWh_th of TIMES-pinned heat undelivered, substituting elsewhere.
This is the mechanism behind **open item 1** (sludge folded into the BEWAL
`solid biomass` pool): one bus cannot separate sludge from wood, so the whole pool
is priced by its scarcest use. Two consequences: 2050 decentral heat does **not**
reproduce the TIMES heating mix, and any 2050 biomass-related marginal cost in
this run should be treated as a corner solution rather than a price signal.

**F4 — the nuclear sweep reprices existing capacity, so its objectives are not comparable.**

The 2025 objective already moves monotonically with the swept CAPEX
(4500: 3.5704e11 · 5500: 3.6073e11 · 6000: 3.6218e11 · 7500: 3.6514e11) even
though 2025 nuclear capacity is pinned. `cost:nuclear:investment` therefore also
reprices the annuitised existing Tihange LTO fleet, not only new build. The
**capacity** reading of the sweep (does 2 GW appear at 2050?) is unaffected and
remains valid; **total-system-cost comparisons across sweep points are not**, and
must not be presented as "nuclear at 6 000 EUR/kW costs the system X less".

**F5 — provenance gap: no per-horizon config snapshot for 2050.**
Minor but it is a level-0 item; the other three horizons have theirs and are
identical apart from `planning_horizons`.

**F6 — solver conditioning and interior solutions.**
Gurobi reports `large bounds, large rhs` at every horizon (bounds range up to
7e+10) and crossover is disabled, so the reported solution is interior.
Individual small values carry solver-tolerance noise — **do not read three
significant figures off single components.** Aggregates are sound (level 3 closes
to 1e-07).

**F7 — Sankey node `enc_pe` does not balance at any horizon** (+8.3 / +10.9 /
+10.6 / +4.1 TWh, `in 0.000`), and `elc_se` is off by −0.589 TWh at 2025. Almost
certainly a reporting-side artefact of the primary-energy source node rather than
a model error — level 3 closes on the networks themselves — but it will appear in
the published Sankeys and should be explained or suppressed before they go out.

### Numbers that must not be published as-is

1. **2040/2050 Walloon wind capacity as an optimisation result** — it is the
   potential ceiling (F1).
2. **2025 EV flexibility** (charger `p_nom`, battery `e_nom`) — rests on a
   TIMES 2025 BEV car fleet of 4 757 vehicles that fell 52× between the 7 and
   11 September exports and matches no external figure; open item 7. The 2025 EV
   *load* is exact and may be used.
3. **2050 decentral heat mix and biomass marginal costs** — corner solution (F3).
4. **Cross-sweep total system costs** for the nuclear points (F4).
5. **Zero-capital-cost capacities** flagged by the review (distribution grid
   10 295 MW at 2050, etc.) — accounting artefacts, not results.

### Review follow-ups

* **R1** — put open item 7 (2025 BEV fleet, 52× discrepancy) to ICEDD; it gates
  publication of anything touching 2025 EV flexibility.
* **R2** — ask ICEDD whether the 2050 biomass boiler heat (1.599 TWh_th) should
  be enforced or dropped from the pin, given the pool is shared with industry
  (open item 1).
* **R3** — run a sensitivity on the 6 500 MW Walloon wind potential. On this
  evidence it determines the 2040–2050 result more than any cost assumption in
  the batch.
* **R4** — decide whether to present the nuclear sweep on capacity only, or to
  re-run it with existing-capacity cost held fixed (F4).
* **R5** — fix `cluster/probe.sh` (§9 issue 4) and the missing 2050 config
  snapshot (F5).
