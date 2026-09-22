# Walloon onshore-wind land-eligibility workflow

A **stand-alone** Snakemake workflow that computes the technical potential for
onshore wind in Wallonia from the Walloon Region's own regulatory cartography,
using the same `atlite` land-eligibility machinery PyPSA-Eur uses for every
other node.

It exists because the Walloon onshore-wind cap in PyPSA-Wal
(`potential:BEWAL:onwind:p_nom_max`, 6 500 MW) is an expert judgement from the
PNEC wallon and EDORA, not a spatial calculation — and PyPSA-Eur's own default
land analysis was never run against Walloon law.

The report is [`docs/onwind_potential_wallonia/`](../docs/onwind_potential_wallonia/).

> **This workflow does not touch PyPSA-Wal.** It reads two model resources
> (`resources/regions_onshore_base_s_adm.geojson`, `resources/nuts3_shapes.geojson`)
> and the `atlite` cutout, and writes only inside this directory and into
> `docs/onwind_potential_wallonia/`. No model input is modified.

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
| retrieve 19 Walloon reference datasets | `retrieve_wallonia_layer` | `data/*.gpkg` + `.meta.json` provenance |
| build the administrative and model regions | `build_regions` | `resources/regions.gpkg` |
| translate the siting rules into geometry | `build_exclusion_layers` | `resources/exclusions_<turbine>/` |
| run the `atlite` eligibility analysis | `build_availability` | `resources/availability_*.nc` |
| area → capacity, capacity factor, FLH | `build_potential` | `results/potential/*.csv` |
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
- `scenarios:` — the constraint ladder, each step adding layers to the previous.
- `turbines:` — the three classes, matching the "150 m / 180 m / 210 m"
  scenarios of the 2022 SPW/Gembloux favourable-zone update.

Changing a rule is a config edit; Snakemake re-derives only what depends on it.

## Data

All source layers come from the ESRI-REST services of
<https://geoservices.wallonie.be> under CC-BY 4.0. Each download writes a
`.meta.json` recording the service, layer, feature count and retrieval date, and
the workflow warns if a feature count has moved more than 20 % from the value
recorded in `config.yaml` on 22 September 2026.

`data/`, `resources/` and `results/*/` are gitignored — they are reproducible.

## Known gaps

Aviation and defence radar exclusions, classified sites, priority
ornithological zones and the 7 % slope criterion of the 2013 Walloon map are
**not** implemented: the geometries are not public. They all reduce the
potential. See §7 of the report.
