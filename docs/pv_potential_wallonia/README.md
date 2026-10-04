# The potential for ground-mounted photovoltaics in Wallonia

**[pv_potential_wallonia.pdf](pv_potential_wallonia.pdf)** — land-eligibility
analysis of ground-mounted PV (brownfields, landfills, extraction zones,
verges, activity zones, floating PV, agrivoltaics) against the Walloon rules,
and what it implies for `potential:BEWAL:solar:p_nom_max`.

Produced by [`workflow_pv_wal/`](../../workflow_pv_wal/) (see its README):

```bash
cd workflow_pv_wal && snakemake all report infographic -c3 --resources mem_mb=9000 --rerun-triggers mtime
```

Dashboard (French): `workflow_pv_wal/results/infographic/`, plan in
[`infographic_plan.md`](infographic_plan.md).

**No PyPSA-Wal input has been modified.** This is the evidence base for that
decision, not the decision.

## Headline (administrative Region, 20 m grid, 2010 weather)

| | GWc |
|---|---:|
| technical potential: every hectare that survives the exclusions and the park rule (6 275 km², 37 % of the Region) | 356 |
| … of which declared farmland (533 000 ha, 72 % of the SAU) | 261 |
| circular of 14 March 2024 strictly as it stands (no derogation, no agrivoltaics) | 2.6 |
| **reference**: + the demonstrable share of the poor-soil derogation (5.1 %) + agrivoltaics on grassland at 0.6 % of the SAU | **6.25** |
| reference with agrivoltaics at 1 % / 2 % of the SAU | 8.3 / 13.5 |
| every eligible grassland parcel / every eligible parcel | 126 / 252 |
| cap in the model today | 13 |
| PyPSA-Eur default land analysis | 37 |

The 0.6 % is the Livre blanc's figure for the PV still to be built **to
2030**; the model's horizon is 2050, so the reference reads it as a policy on
the table, not a ceiling. **The model's 13 GW equals the reference with
agrivoltaics on 2 % of the agricultural area**: a policy assumption, not a
land limit.

### The poor soils

The circular admits a derogation on soils « dont la qualité agronomique est
médiocre » (démontrée). The only regional map (AWAC/GxABT 2024) ranks soils by
percentiles of water reserve and depth: its "faible" classes (110 000 ha) are
mostly stony loams, 78 % of them farmed — farmers crop them at 89–91 % where
they can, more than the average soil. Of the 4 697 ha of such land unfarmed in
the agricultural zone, 2 753 ha are outside the LPIS register, 2 245 ha away
from buildings, and weighting by the revealed agricultural use of each soil
unit leaves 241 ha: **5.1 %**, the central scenario (bracket 0–100 %, i.e.
−0.16 / +2.6 GWc). Cross-check: poor soils are left unfarmed at 9.95 %, the
others at 9.58 %.

## What the answer depends on (one change at a time, against 6.25 GWc)

| change | Δ GWc |
|---|---:|
| no agrivoltaics / quota 1 % / 2 % | −3.6 / +2.1 / +7.2 |
| all free land of the activity zones / none | +3.4 / −1.3 |
| brownfields kept for reindustrialisation | −0.9 |
| floating PV on every water body | +0.6 |
| poor soils: none / all | −0.16 / +2.6 |
| park rule: 5 ha minimum / 100 m width / 40 m width | −1.2 / −1.2 / +1.0 |
| densities low / high | −1.8 / +1.7 |
| extreme flood zones excluded | −0.6 |

## Calibration

Against the 88 ground-mounted parks mapped in OSM (241 ha): they avoid
nature (avoidance 0.03), the forest zone (0.10) and the landscape perimeters
(0.05); 72 % of their land passes every rule (33 % with the WALOUS land-cover
test, which sees parks built before 2023 as sealed surface). Median tagged
density 0.97 MWc/ha, the reference 1.0.

## Files

| | |
|---|---|
| `pv_potential_wallonia.tex` | the report; every number comes from `generated/macros.tex` |
| `generated/` | LaTeX macros and table fragments, written by the workflow |
| `figures/` | copies of `workflow_pv_wal/results/figures/` |
| `infographic_plan.md` | the dashboard plan (French) |
| `PROGRESS.md` | working notes of the study (design decisions, state) |

Do not edit `generated/` or `figures/` by hand — re-run the workflow.
