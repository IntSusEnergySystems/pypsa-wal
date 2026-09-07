# Solve log — scen_demande_haute @ 2010, 1h (2030 barrier sub-optimal, chain stopped)

## 1. Identification

| Field | Value |
|---|---|
| Date of run | 2026-09-07 ~13:30 (launch) → 16:57 (2030 gave up) |
| Operator | sylvain |
| Run name / prefix | `scen_demande_haute` / `walloon` |
| Code version | `development_plan` `8fbc39f3` ("solving the remaining run issues") |
| Outcome | **1/4** — 2025 optimal, 2030 sub-optimal, 2040/2050 never started |

## 2. Goal of the run

First solve on `8fbc39f3`: the R1/R2/R4 fixes, the biomass fuel-bus fix and
ICEDD's 9222 GWh Walloon potential. Predicted in §13 of
[`2026-09-05_…_production.md`](2026-09-05_scen_demande_haute_2010_1h_production.md):
2040 and 2050 gain headroom, **2030 becomes the tight horizon**. That is exactly
what happened, and harder than predicted.

## 3. Main parameters

Unchanged from the 2026-09-05 production run except the code version:
`scen_central_demande_haute_v2_260903_0309.vd`, 2010 / 8760 h, 1h sector
resolution, myopic 2025-2030-2040-2050, Gurobi 13.0.2 barrier (Method 2,
BarConvTol 1e-5, BarHomogeneous 1, Crossover 0, Seed 123), 16 threads, NIC5.

## 4. Results

| Horizon | Status | Objective | Barrier |
|---|---|---|---|
| 2025 | optimal | 3.48378362e+11 | 211 it / 3279 s |
| 2030 | **sub-optimal** | 3.65011313e+11 | 402 it / 6237 s |
| 2040 | not run | — | — |
| 2050 | not run | — | — |

2025 solved **faster** than on the previous code (211 it vs the reference pace)
and its objective fell from 3.56589911e+11 — consistent with the R1 coal fix and
the biomass rewiring. No 2030 network was written; the `2040`/`2050` `.nc` still
on scratch are the 2026-09-06 files and must not be mistaken for this run.

## 5. Diagnosis — it is not numerics

Gurobi's `Model contains large rhs` / `large bounds` warnings prompted the
NumericFocus suggestion. Those two warnings were **also printed by the 6 September
run that solved optimally**: they come from the coefficient ranges, which did not
move. Comparing the two logs:

| | 6 Sep (optimal) | 7 Sep (sub-optimal) |
|---|---|---|
| rows / cols / nonzeros | 39421163 / 19115120 / 94905710 | identical |
| presolved | 7887015 / 14638834 / 53381963 | identical |
| Matrix range | `[6e-04, 8e+02]` | `[6e-04, 8e+02]` |
| Objective / Bounds / RHS range | 1e+09 / 6e+09 / 1e+09 | 1e+09 / 5e+09 / 1e+09 |
| Dense cols / Free vars | 530 / 148920 | 530 / 148920 |
| Factor NZ / Ops | 5.078e8 / 4.981e11 | 4.930e8 / **4.730e11** |

Same structure, same conditioning, marginally *cheaper* per iteration. What
differs is convergence: at iteration 241 the old run had primal residual **1.72**
and complementarity 1.24e-04; at iteration 402 the new one is still at **1.38e5**
and 4.04e+01. The barrier could not reach primal *feasibility*, not precision.
NumericFocus addresses unstable factorisation; the factorisation is fine.

**Cause: the 2030 solid-biomass budget lands almost exactly on the boundary.**
The pre-solve budget report said so before the solve:

> `biomass boiler profile needs ~5.049 TWh of solid biomass at BEWAL solid biomass,`
> `whose own supply caps at 11.222 TWh (imports excepted) …`

Supply 11.222 (9.222 ICEDD + 2.0 import). Demand: industry 6.205 TWh of demand
needing ~6.89 TWh of fuel (the `solid biomass for industry CC` link carries the
capture energy penalty) plus a 5.020–5.753 TWh boiler pin. The budget is binding
to within a fraction of a percent, so the optimal face is near-degenerate and the
interior the barrier needs has essentially collapsed.

The other two horizons confirm the mechanism by contrast: 2025 has clear slack
(demand 8.21 vs 11.222) and solved in 211 iterations; 2040 is clearly short
(12.60 vs 11.222) so the pin relaxes decisively — that is finding R4 — and it
solved in 259 on the previous code. Only 2030 sits on the knife edge.

## 6. Resolution — ICEDD's 2026-09-07 scenario, not a solver flag

ICEDD re-ran TIMES the same morning, freezing the Walloon solid-biomass resource
at its 2021 energy-balance level with no growth
(`scen_central_demande_haute_v01_260907_0709.vd`, S3 `times_20260907/`). Exported
through the soft link, the Walloon biomass demand PyPSA must serve drops:

| TWh | industry | boiler heat | ≈ total fuel | vs supply 11.222 |
|---|---:|---:|---:|---:|
| 2030 old | 6.205 | 4.094 | 10.91 | knife edge |
| **2030 new** | 4.522 | 3.881 | **8.98** | **+2.2 slack** |
| 2040 old | 7.625 | 4.332 | 12.60 | −1.4 |
| **2040 new** | 5.025 | 4.102 | **9.74** | **+1.5 slack** |

The boundary 2030 was sitting on is gone, and R4's 2040 biomass-boiler
relaxation should resolve with it. `sector.times_file` now points at the new
`.vd` for `scen_demande_haute`, `scen_test_2013_6h` and `scen_evflex`.

TIMES domestic supply under the new scenario is 8.016 / 8.016 / 8.720 / 5.780 TWh
(chips 3.124 + logs 2.365 + renewable sludges 2.527, flat; BIOSLUH 0.704 from
2040), with **zero solid-biomass imports in every horizon**.

### Correction to §13 of the previous log

That section reported TIMES domestic solid biomass as 10.284 / 11.901 / 12.604 /
8.529 TWh. Wrong: `MBOWOO` ("Wood : arbre") and `MPPWOO` ("Paper: Wood") are in
**Mt**, not PJ — raw wood into the wood and paper *material* industries — and
were summed as energy. Corrected figures for that `.vd` are **8.991 / 10.616 /
11.320 / 7.245**. The recommendation built on them (raise the Walloon potential
to 11749 GWh) is **withdrawn**: against the new scenario it would give PyPSA
~45 % more biomass than TIMES has. ICEDD's 9222 GWh stands unchanged.

## 7. Follow-ups

1. Re-run all four horizons on `v01_260907_0709` from a machine with NIC5 access.
   A fresh clone has no `.vd` (gitignored) — fetch it from S3 first, see
   [`instructions.md`](../../instructions.md) §Scenarios.
2. Clear or ignore the stale `results/walloon/scen_demande_haute/networks/`
   on scratch: 2025 is from this failed run, 2040/2050 from 2026-09-06. The
   `times_file` path changed, so Snakemake re-runs everything downstream — but do
   not read those files as if they were this run's.
3. Nothing in the config or the aggregate caps stops PyPSA burning Walloon solid
   biomass in `urban central solid biomass CHP`, `biomass to liquid` or
   `biomass-to-methanol`. It came out at ~1e-5 MW while biomass was scarce; with
   1.5–2.2 TWh of new headroom that is no longer guaranteed. TIMES uses only
   `ELCSLU00` (0.959 TWh flat) plus `ELCPEL00` (0.059 TWh in 2040, 2.433 in
   2050). **Modeller call: constrain it, or accept the divergence.**
4. Open question for ICEDD: TIMES mines 8.016 TWh against the 9222 GWh potential,
   and PyPSA additionally carries a 2.0 TWh import cap — ~3.2 TWh of headroom
   TIMES does not have. What perimeter does the 9222 cover?
5. Independent of the data: the heat profile pins are exact hourly equalities.
   `solve_network.py` already widens collapsed *capacity* corridors for exactly
   this reason (`widen_collapsed_corridors`). Giving the profile pins a ±2 % band
   would make the soft link robust to this class of squeeze instead of relying on
   the budget never binding. Not done — it changes results and no run has tested
   it.
