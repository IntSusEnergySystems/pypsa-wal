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
| free allocation (no grouping rule) — *upper bound* | 13 084 MW |
| farm allocation, 4 / 5 / 6 km between farms | 6 936 / 5 348 / 4 440 MW |
| **central estimate** (5 km + residual allowance) | **4 091 MW** |
| credible range | 2 486 – 6 936 MW |
| PyPSA-Eur default land analysis (area × 3 MW/km²) | 19 079 MW |
| BREGILAB / VITO Dynamic Energy Atlas, gross | 11 400 MW |
| cap in the model today | 6 500 MW |
| standing fleet, end 2024 | 1 528 MW |

## What changed, and why it matters

An earlier version of this study concluded **2–4.5 GW**. That reading does not
survive: it rested on screening the eligible raster by patch size, a cut-off
with no legal or engineering basis. Capacity now comes from **placing machines
and wind farms** on the raster under the framework's own rules — the method
BREGILAB uses, plus the Walloon grouping and inter-distance criteria it lacks.
The 6 500 MW cap sits *inside* the credible range rather than far above it.
§6.6 of the report retracts the earlier figure in full.

## Calibration

The constraint set is tested against the **652 turbines standing in Wallonia**
(OpenStreetMap). No layer has an avoidance ratio above 0.77 — every constraint
is one Walloon wind development demonstrably avoids. Two candidate constraints
failed the test and were dropped. The farm model predicts 5.6 machines per farm
against the 4.9 of the real fleet, and 240 farms against 134.

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
