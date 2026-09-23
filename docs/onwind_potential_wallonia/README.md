# The technical potential for onshore wind in Wallonia

**[onwind_potential_wallonia.pdf](onwind_potential_wallonia.pdf)** — land-eligibility
and siting analysis of Walloon onshore wind against the Region's own regulatory
instruments, and what it implies for `potential:BEWAL:onwind:p_nom_max`.

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

Reference turbine NREL 2020ATB 4 MW (tip 185 m), 5 D between any two machines.

| | Wallonia (administrative) |
|---|---:|
| eligible land, all implemented constraints | 420 km² (2.5 %) |
| free allocation — *land-and-wake bound*, the quantity BREGILAB reports | 11 460 MW |
| + parks of at least 4 machines | 8 648 MW |
| + open horizon, 130° within 4 km of each village — **gross reference** | **6 480 MW** |
| **central estimate** (+ residual allowance for birds and partial constraints) | **4 957 MW** |
| credible range | 3 629 – 6 480 MW |
| *if the recommended 4 / 6 km inter-distance were applied as a rule* | 5 436 / 4 336 MW gross |
| PyPSA-Eur default land analysis (area × 3 MW/km²) | 19 079 MW |
| BREGILAB / VITO Dynamic Energy Atlas, gross | 11 400 MW |
| BREGILAB's own rules applied to open data | 25 087 MW |
| cap in the model today | 6 500 MW |
| standing fleet, end 2024 | 1 528 MW |

## What the answer depends on

The Cadre de référence is a circular *à valeur indicative* and the plan de
secteur admits derogations for wind farms (CoDT D.IV.11), so the rules that shape
the answer are mostly policy. Each is priced on the gross reference (§7):

| one change from the reference | gross MW | Δ |
|---|---:|---:|
| no agricultural corridor (derogation route) | 9 076 | +40 % |
| no open-horizon rule | 8 648 | +34 % |
| no minimum park size (2024 exception above 3.2 MW) | 8 116 | +25 % |
| inter-distance 4 km between parks, motorways exempt | 5 436 | −16 % |
| inter-distance 6 km between parks, motorways exempt | 4 336 | −33 % |
| 2013 habitat setback (4 × tip height) | 4 660 | −28 % |
| corridor relaxed and no park minimum, horizon kept | 10 664 | +65 % |
| 6 km inter-distance and 2013 setback | 3 152 | −51 % |

## The rules, as the texts state them

| rule | reference | basis |
|---|---|---|
| distance between machines | 5 D (750 m) | nearest-neighbour distance of a 5D×7D array; BREGILAB's rule; the fleet sits at 4.3 D |
| park | ≥ 4 machines, 1.5 km linkage, no radius or centre separation | Cadre 2024 §3.1; the fleet's own farm definition |
| open horizon | 130° free within 4 km of each village | Cadre 2024 §3.4 §3; 6 of 880 affected villages breach it today |
| inter-distance | **sensitivity only** | Cadre 2024 §3.4 §3: 4 km (short views) to 6 km (long views) "recommandée et peut être réduite", not along motorways, measured between nearest masts; 53 % of standing farms are closer than 4 km to another |
| agricultural corridor | 1.5 km from a PIC or a zone d'activité économique | CoDT R.II.36-2; a PIC is a motorway, a 2×2 regional road, a railway or a waterway (R.II.21-1) — not every plan-de-secteur road |
| setbacks | 500 m + H/2 from habitat zones; 400 m from dwellings outside the economic zones | Cadre 2024 §3.2 §2 |

## Calibration

Everything is tested against the **652 turbines standing in Wallonia**
(OpenStreetMap).

- **Constraint set.** Every layer is avoided by the fleet. Conditional on the
  other layers, the plan-de-secteur landscape perimeters (0.04), the
  aeronautical rings (0.12), the slope criterion (0.15) and the ADESA inventory
  (0.25) are strongly avoided; the infrastructure distances least (0.61).
- **Zoning.** 79 % of the fleet stands where the zoning admits a turbine with
  the CoDT's PIC network: about one machine in five was permitted by derogation
  or before the present code.
- **Farm geometry.** Measured between nearest masts, 53 % of the 134 farms have
  a neighbour closer than 4 km (39 % of those not along a motorway); only 34 %
  of the machines stand within 1 km of a motorway.
- **Layouts.** Every placed layout is checked against its own rules by an
  independent implementation; the run fails if one is broken.

## Files

| | |
|---|---|
| `onwind_potential_wallonia.tex` | the report; every number comes from `generated/macros.tex` |
| `generated/` | LaTeX macros and table fragments, written by the workflow |
| `figures/` | copies of `workflow_onwind_wal/results/figures/`, for standalone compilation |

Do not edit `generated/` or `figures/` by hand — re-run the workflow.

## What is an allowance rather than geometry

Two families remain unrepresentable and carry a documented, bracketed
allowance: the DEMNA priority-bird zones (10 %, 0–20 %) and the method's
*partial* constraints (15 %, 0–30 %). The skeyes and Defence red zones are not
published and are not represented at all; they are the most likely reason
BREGILAB's published figure is less than half of what its own rules give on open
data. See §8 and §11.
