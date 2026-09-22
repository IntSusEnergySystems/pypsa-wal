# The technical potential for onshore wind in Wallonia

**[onwind_potential_wallonia.pdf](onwind_potential_wallonia.pdf)** — land-eligibility
analysis of Walloon onshore wind against the Region's own regulatory
cartography, and what it implies for `potential:BEWAL:onwind:p_nom_max`.

Produced by [`workflow_onwind_wal/`](../../workflow_onwind_wal/):

```bash
cd workflow_onwind_wal && snakemake -c4 report
```

**No PyPSA-Wal input has been modified.** This is the evidence base for that
decision, not the decision.

## Headline

| | Wallonia (administrative) | BEWAL node |
|---|---:|---:|
| eligible land, all constraints | 870 km² (5.1 %) | 813 km² (5.4 %) |
| installable capacity, reference case | 4 417 MW | 4 127 MW |
| range across turbine classes and spacings | 2 489 – 7 560 MW | 2 327 – 7 059 MW |
| after the developability screen | 2 066 MW | — |
| PyPSA-Eur default land analysis | 19 079 MW | 18 270 MW |
| cap in the model today | — | 6 500 MW |

Two independent methods converge: the developability-screened figure
(2 066 MW) and the Region's own 2022 site-by-site simulation
(457 turbines ≈ 2 559 MW) agree within 20 %.

## Files

| | |
|---|---|
| `onwind_potential_wallonia.tex` | the report; every number comes from `generated/macros.tex` |
| `generated/` | LaTeX macros and table fragments, written by the workflow |
| `figures/` | copies of `workflow_onwind_wal/results/figures/`, for standalone compilation |

Do not edit `generated/` or `figures/` by hand — re-run the workflow.

## Validation

Reproducing PyPSA-Eur's own constraint set with PyPSA-Eur's own turbine on the
model's own region returns 2 442 full-load hours against the 2 425 h of the
profile PyPSA-Wal actually carries (+0.7 %). The plumbing is right; the
differences that follow come from the constraint set.

## What is missing

Aviation and defence radar exclusions, classified sites, priority ornithological
zones and the 7 % slope criterion are not implemented — the geometries are not
public. All four reduce the potential. §7 of the report lists them in order of
expected impact, with the action needed to close each.
