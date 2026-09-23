# The technical potential for onshore wind in Wallonia

**[onwind_potential_wallonia.pdf](onwind_potential_wallonia.pdf)** — land-eligibility
and siting analysis of Walloon onshore wind against the Region's own regulatory
cartography, and what it implies for `potential:BEWAL:onwind:p_nom_max`.

Produced by [`workflow_onwind_wal/`](../../workflow_onwind_wal/):

```bash
cd workflow_onwind_wal && snakemake -c4 report
```

**No PyPSA-Wal input has been modified.** This is the evidence base for that
decision, not the decision.

## Scope

The **administrative Walloon Region** (16 905 km²), not the model's `BEWAL`
node. The node covers 89.6 % of the Region — western Hainaut falls on the
Flemish side of the Voronoi partition — and is out of scope here; §1.4 of the
report states the difference and its consequences.

## Headline

| | Wallonia (administrative) |
|---|---:|
| eligible land, all implemented constraints | 561 km² (3.3 %) |
| free allocation at 5 D between machines — *land and wake bound* | 15 236 MW |
| + grouping into farms | 7 752 MW |
| + open horizon, 130° within 4 km of each village — *gross reference* | 5 712 MW |
| **central estimate** (+ residual allowance) | **4 370 MW** |
| credible range | 3 199 – 5 712 MW |
| *if the 2013 indicative 4–6 km inter-distance were applied as a rule* | 2 509 – 3 516 MW |
| PyPSA-Eur default land analysis (area × 3 MW/km²) | 19 079 MW |
| BREGILAB / VITO Dynamic Energy Atlas, gross | 11 400 MW |
| cap in the model today | 6 500 MW |
| standing fleet, end 2024 | 1 528 MW |

## Siting rules

Three siting rules decide the answer, and together they matter more than the
whole constraint ladder below the setbacks (§2.4):

| rule | value | basis |
|---|---|---|
| distance between machines | 5 D (750 m) | nearest-neighbour distance of a 5D×7D array; BREGILAB's rule; the fleet sits at 4.3 D |
| machines per farm | ≥ 4 | 86 % of the standing fleet is in groups that size |
| landscape | 130° of open horizon within 4 km of each village | the 2013 cadre de référence, verbatim |

The 4–6 km inter-farm distance is **not** applied: the 2013 text calls it *indicative*, subordinates it to the
impact assessment, exempts turbines sited along motorways — which is where the
zoning rule concentrates the eligible land — and the 2024 framework that
replaced it does not carry it at all. It is reported as a labelled legacy
sensitivity.

## Calibration

Everything is tested against the **652 turbines standing in Wallonia**
(OpenStreetMap).

- **Constraint set.** No layer has an avoidance ratio (share of the fleet ÷
  share of the Region) above 0.77 — every constraint is one Walloon wind
  development demonstrably avoids.
- **Siting geometry.** The machine spacing, farm radius and farm separation are
  taken from the fleet's own distributions, not from a rule: 427 m median
  between machines, 1 309 m p75 farm radius, 2 342 m p10 between farms.
- **Landscape rule.** Of 2 261 settlements, 880 have a turbine within 4 km and
  only **6 of them** fall below the 130° open-horizon threshold — the criterion
  is observed in practice, and the implementation reproduces that.
- The farm model then predicts 4.7 machines per farm against the fleet's 4.9,
  and 307 farms against 134.

## Files

| | |
|---|---|
| `onwind_potential_wallonia.tex` | the report; every number comes from `generated/macros.tex` |
| `generated/` | LaTeX macros and table fragments, written by the workflow |
| `figures/` | copies of `workflow_onwind_wal/results/figures/`, for standalone compilation |

Do not edit `generated/` or `figures/` by hand — re-run the workflow.

## What is an allowance rather than geometry

Aeronautical servitudes, the 7 % slope criterion, classified sites and the
radar perimeters are now implemented from data. Two families remain
unrepresentable and carry a documented, bracketed allowance: the DEMNA
priority-bird zones (10 %, 0–20 %) and the method's *partial* constraints
(15 %, 0–30 %). The azimuth-of-open-horizon test needs a site-level model and
is not represented at all. All of them reduce the potential. See §8.
