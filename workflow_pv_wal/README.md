# Walloon ground-mounted PV land-eligibility workflow

A **stand-alone** Snakemake workflow that computes the technical potential for
ground-mounted photovoltaics in **the administrative Walloon Region** from the
Region's own regulatory cartography, the PV counterpart of
[`workflow_onwind_wal/`](../workflow_onwind_wal/). It covers brownfields,
landfills, spoil tips, extraction zones, motorway and railway verges,
economic-activity zones, floating PV on industrial basins and quarry lakes,
and **agrivoltaics** on the declared agricultural parcels.

It exists because the Walloon ground-mounted PV cap in PyPSA-Wal
(`potential:BEWAL:solar:p_nom_max`, 13 000 MW, `data/walloon/custom_potentials.csv`)
is an expert sum of published estimates (brownfields + agrivoltaics), not a
spatial calculation, and PyPSA-Eur's own land analysis gives 37 GW for the node
without knowing any Walloon rule.

The report is [`docs/pv_potential_wallonia/`](../docs/pv_potential_wallonia/).

> **This workflow does not touch PyPSA-Wal.** It reads two model resources
> (`resources/regions_onshore_base_s_adm.geojson`, `resources/nuts3_shapes.geojson`)
> and the 2010 `atlite` cutout, and writes only inside this directory, into
> `docs/pv_potential_wallonia/`, and onto the data disk.

## Running (office machine: 16 cores, 15 GB RAM)

```bash
cd workflow_pv_wal
PY=/home/anaconda/envs/pypsa-eur/bin
$PY/snakemake download -c3 --resources net=1 mem_mb=6000 --keep-going   # ~1.5 h, ~45 GB transferred
$PY/snakemake all -c3 --resources mem_mb=9000 --rerun-triggers mtime     # ~30 min
$PY/snakemake report --rerun-triggers mtime                              # the PDF (tectonic)
$PY/snakemake infographic --rerun-triggers mtime                         # the dashboard
cd results/infographic && python -m http.server 8000                    # http://localhost:8000
$PY/snakemake infographic_publish --rerun-triggers mtime                 # pypsa.squoilin.eu
```

Memory is the constraint, not CPU: every rule declares `mem_mb`, and
`--resources mem_mb=9000` keeps two 7 GB rules from running together. The
heavy trees are symlinks to `/sylvain/mount/pypsa-wal-data/workflow_pv_wal/`
(`data/`, `resources/`, `logs/`, `results/infographic/`), per
[`run_from_office_computer.md`](../run_from_office_computer.md) §1.
`net=1` serialises the big downloads (the LiDAR terrain model is 42 GB).

## What it does

| stage | rule | output |
|---|---|---|
| Walloon open-data layers (ESRI-REST, CC-BY) | `retrieve_wallonia_layer` | `data/*.gpkg` + `.meta.json` |
| bulk files: SIGEC 2024 parcels, WALOUS 2023 land cover (1 m), soil quality | `retrieve_bulk` | `data/<key>/` |
| LiDAR terrain model 2021-22 (1 m), per province, averaged to 20 m | `download_dem_province`, `retrieve_dem_province`, `merge_dem` | `resources/dem_20m.tif` |
| OSM ground-mounted PV parks and substations | `retrieve_osm` | `data/osm_pv.gpkg` |
| 20 m study grid (EPSG:3035) | `build_regions`, `build_grid` | `resources/grid.json`, `region_mask.tif` |
| every exclusion layer and gisement mask, burnt on its own | `burn_layer` | `resources/layers/*.tif` |
| slope and aspect; SIGEC crop classes; WALOUS shares; soils | `build_terrain`, `build_sigec`, `build_walous`, `build_soils` | `resources/rasters/` |
| reference potential + 30 sensitivity cases | `potential` | `results/tables/potential_reference.csv`, `sensitivity_cases.csv`, `headline.json` |
| test against the parks actually built | `validate_fleet` | `results/tables/fleet_*.csv/json` |
| full-load hours per system, 2010 weather | `energy` | `results/tables/energy.csv` |
| maps, charts, LaTeX macros, PDF | `plot_maps`, `plot_summary`, `make_report_inputs`, `build_report` | `results/figures/`, `../docs/pv_potential_wallonia/` |
| dashboard | `infographic_data`, `infographic_page`, `infographic_publish` | `results/infographic/` |

## The method in one paragraph

Every layer is burnt on its own onto one 20 m grid and packed one bit per
layer (`scripts/pv_lib.py`). Exclusions come in seven families applied in a
fixed order (nature, forest, woodland cover, landscape, hazards, terrain,
built), then water. The surviving land is classified into **gisements** — what
the land is (brownfield, landfill, extraction zone, verge, activity zone,
grassland parcel, arable parcel, water body…) — in a priority order that
encodes the circular: farmed land is farmland whatever its zoning. A **park
rule** (60 m minimum width, 1 ha minimum area) turns land into sites. Capacity
is area × a density per system (ground, agrivoltaic on grassland / crops /
canopy, floating). A **policy layer** then decides which gisements are open and
to what share; the park rule is re-applied to the opened land only, so a strip
of verge counts only if it is wide enough on its own.

## Reviewing the constraint set

Everything that decides the answer is in [`config.yaml`](config.yaml), each
entry labelled `law`, `circular`, `technical`, `judgement` or `policy`:

- `sources:` / `bulk:` — the datasets, with service, layer, feature count.
- `layers:` — the exclusions, with the text each implements.
- `gisements:` / `pds_codes:` / `masks:` / `sigec_classes:` — what the land is.
- `terrain:`, `walous:`, `park:` — the technical criteria.
- `densities_mwc_ha:`, `floating:` — land to capacity, with brackets.
- `policy:`, `agrivoltaics:`, `soil_filter:` — what is open.
- `sensitivity:` — every choice priced one at a time.
- `infographic:` — the dashboard, including the choice tuples that must
  reproduce the report's cases (the build fails otherwise).

Every plan-de-secteur label and attribute value is checked against the data:
a value that matches nothing stops the burn.

## Data gaps

- The plan-de-secteur *périmètres de point de vue remarquable* (PDS/16) are
  published empty; ADESA carries view *lines* only. Not represented.
- The SGIB (sites of biological interest) are not published as a layer.
- The BDES (soil-pollution parcels) is under a restricted licence and is not
  used; brownfields come from the SAR inventories.
- There is no official register of ground-mounted PV parks: OSM stands in, for
  calibration only.

`data/`, `resources/`, `logs/`, `results/figures/`, `results/infographic/` are
gitignored; `results/tables/` is versioned.
