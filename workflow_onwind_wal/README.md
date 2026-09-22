# Walloon onshore-wind land-eligibility workflow

A **stand-alone** Snakemake workflow that computes the technical potential for
onshore wind in **the administrative Walloon Region** from the Region's own
regulatory cartography, using the same `atlite` land-eligibility machinery
PyPSA-Eur uses for every other node — and then places individual machines and
wind farms on the surviving land rather than multiplying it by a capacity
density.

It exists because the Walloon onshore-wind cap in PyPSA-Wal
(`potential:BEWAL:onwind:p_nom_max`, 6 500 MW) is an expert judgement from the
PNEC wallon and EDORA, not a spatial calculation — and PyPSA-Eur's own default
land analysis was never run against Walloon law.

The report is [`docs/onwind_potential_wallonia/`](../docs/onwind_potential_wallonia/).

> **This workflow does not touch PyPSA-Wal.** It reads two model resources
> (`resources/regions_onshore_base_s_adm.geojson`, `resources/nuts3_shapes.geojson`)
> and the `atlite` cutout, and writes only inside this directory and into
> `docs/onwind_potential_wallonia/`. No model input is modified.

> **Scope is the administrative Region.** The model's `BEWAL` node is a
> different polygon (89.6 % of the Region; western Hainaut falls on the Flemish
> side of the Voronoi partition) and is deliberately not analysed here. The
> region shapes are still read so the report can state the difference.

## Running

```bash
conda activate pypsa-eur
cd workflow_onwind_wal

snakemake -c4 download                      # ~20 min, one-off (≈200 MB)
snakemake -c4 all                            # eligibility, potentials, figures
snakemake -c4 report                         # the PDF
```

After editing `config.yaml`, add `--rerun-triggers mtime` so a changed buffer
does not trigger a re-download of the 1.5 M address points:

```bash
snakemake -c4 all --rerun-triggers mtime
```

## What it does

| stage | rule | output |
|---|---|---|
| retrieve 24 Walloon reference datasets | `retrieve_wallonia_layer` | `data/*.gpkg` + `.meta.json` provenance |
| decode the Region's slope-class map into a ≥ 7 % mask | `retrieve_slope_raster` | `data/slope_ge7.tif` |
| fetch the standing Walloon fleet from OpenStreetMap | `retrieve_osm_turbines` | `data/osm_wind_turbines.gpkg` |
| build the region polygons | `build_regions` | `resources/regions.gpkg` |
| translate the siting rules into geometry | `build_exclusion_layers` | `resources/exclusions_<turbine>/` |
| run the `atlite` eligibility analysis | `build_availability` | `resources/availability_*.nc` |
| area → capacity, capacity factor, FLH | `build_potential` | `results/potential/*.csv` |
| rasterise the reference constraint set at 100 m | `build_eligible_raster` | `results/eligible_land_<turbine>.tif` |
| **place machines and farms on that raster**, under the wake, grouping and open-horizon rules | `place_turbines` | `results/tables/placement_*.csv`, `results/placement_*.gpkg` |
| test the constraint set against the standing fleet | `validate_fleet` | `results/tables/fleet_validation_*.json` |
| cost of each late-added constraint family | `servitude_costs` | `results/tables/servitude_costs_*.json` |
| tables, figures, LaTeX macros | `collect_results`, `plot_*`, `make_report_inputs` | `results/`, `../docs/.../generated/` |

## Reviewing the constraint set

Everything that decides the answer is in [`config.yaml`](config.yaml), not in
the Python:

- `sources:` — one block per dataset, naming the ESRI-REST service and layer.
- `plan_de_secteur:` — the positive list of admissible `AFFECT` classes, the
  1.5 km agricultural corridor along the PIC and the 750 m coniferous-forest
  corridor.
- `setbacks:` — distances, as formulas in `H` (tip height) and `D` (rotor
  diameter). `habitat_zone.default` switches between the 2013 and 2024
  *cadre de référence*.
- `aviation:` — which classes of the DGTA obstacle-evaluation map are treated as
  exclusions. The choice is calibrated against the standing fleet, and the
  measurement that settles it is in the comment above the block.
- `slope:` — the 7 % threshold of the 2013 Walloon methodology.
- `radar_installations:` — the three reconstructed protection circles, with the
  coordinate and the basis for each radius.
- `scenarios:` — the constraint ladder, each step adding layers to the previous.
- `placement:` — the three siting rules and their calibration: the minimum
  inter-turbine distance in rotor diameters, the farm radius and separation
  (both taken from the standing fleet), the minimum farm size, and the
  open-horizon criterion of the 2013 cadre de référence. The comment above each
  block carries the measurement or the legal text it comes from.
- `settlements:` — what counts as a "village" for the open-horizon test.
- `residual_allowance:` — the documented allowance for the two constraint
  families that have no public geometry, with its bracket.
- `turbines:` — the three classes, matching the "150 m / 180 m / 210 m"
  scenarios of the 2022 SPW/Gembloux favourable-zone update.
- `bregilab:` — the published VITO Dynamic Energy Atlas figures the study
  reconciles against.

Changing a rule is a config edit; Snakemake re-derives only what depends on it.

## Data

All source layers come from the ESRI-REST services of
<https://geoservices.wallonie.be> under CC-BY 4.0. Each download writes a
`.meta.json` recording the service, layer, feature count and retrieval date, and
the workflow warns if a feature count has moved more than 20 % from the value
recorded in `config.yaml` on 22 September 2026.

`data/`, `resources/` and `results/*/` are gitignored — they are reproducible.

## What is represented, and what is an allowance

Everything in the Walloon method is now either geometry or a documented
allowance; there are no unquantified gaps.

### Siting rules

| rule | value | basis |
|---|---|---|
| distance between machines | 5 D | nearest-neighbour distance of a 5D×7D array; BREGILAB's rule; the standing fleet sits at 4.3 D; physical floor ≈ 3 D |
| machines per farm | ≥ 4 | 86 % of the standing fleet is in groups that size |
| farm radius / separation | 1 300 m / 2 600 m | observed p75 farm radius, and twice it; inside the fleet's p10–p25 separation band |
| landscape | 130° of open horizon within 4 km of each village | 2013 cadre de référence, verbatim; only 6 of 880 affected villages breach it today |
| *2013 4–6 km inter-farm distance* | **not applied** | indicative, subordinate to the impact assessment, exempt along motorways, and absent from the 2024 framework — reported as a legacy sensitivity |

### Constraint families

| family | treatment |
|---|---|
| aeronautical servitudes | geometry — DGTA obstacle map, inner rings only (calibrated) |
| slope ≥ 7 % | geometry — ERRUISSOL 10 m grid, decoded from the Region's map service |
| classified sites, UNESCO buffers | geometry — `BC_PAT`, `PAT_MND_UNESCO` |
| weather radar, radio astronomy, Bertem SSR | reconstructed circles at published coordinates |
| priority ornithological zones (DEMNA) | allowance, 10 % (bracket 0–20 %) — layer not public |
| partial constraints at 25 % success | allowance, 15 % (bracket 0–30 %) |
| azimuth of open horizon per village | not represented — needs a site-level model |
| broad-leaved / coniferous split | CORINE 250 m; CARTOFOR unpublished, WALOUS not bulk-retrievable |

See §3.5, §6.4 and §8 of the report.
