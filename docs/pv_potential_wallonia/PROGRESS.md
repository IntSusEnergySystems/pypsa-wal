# Ground-mounted PV potential in Wallonia — working notes

Working file for the study started 2026-09-29, the PV counterpart of
`docs/onwind_potential_wallonia/` and `workflow_onwind_wal/`. It records the
design decisions and the state of the work so that an interruption (the office
machine rebooted once on 2026-09-29, during the first research phase) loses
nothing. It is replaced by a README once the study is finished.

## Layout

| path | what | disk |
|---|---|---|
| `workflow_pv_wal/` | Snakemake workflow (code, config, small tables) | `/` (code only) |
| `workflow_pv_wal/data -> /sylvain/mount/pypsa-wal-data/workflow_pv_wal/data` | downloads | sdb1 |
| `workflow_pv_wal/resources -> …/workflow_pv_wal/resources` | rasters, burns | sdb1 |
| `workflow_pv_wal/logs -> …/workflow_pv_wal/logs` | logs | sdb1 |
| `workflow_pv_wal/results/infographic -> …/workflow_pv_wal/infographic` | dashboard build | sdb1 |
| `/sylvain/mount/pypsa-wal-data/workflow_pv_wal/refs/` | source documents (circulaires, livre blanc) and research notes | sdb1 |
| `docs/pv_potential_wallonia/` | report, generated macros, figures | `/` |

## Resource rules (office machine: 16 cores, 15 GB RAM, `/` 12 GB free)

- Raster processing layer by layer, one bit per constraint in a `uint32`
  code raster; never hold more than a few full-grid arrays at once.
- Snakemake with `-c2` locally and `resources: mem_mb` on every heavy rule, with
  `--resources mem_mb=8000`.
- Downloads sequential (`workers: 1`).
- Anything heavier (10 m grid, DEM derivatives over the whole Region if they do
  not fit) goes to NIC5 `batch` via `sbatch` (compute nodes have no internet:
  push the downloaded data first).

## Design decisions (with where they come from)

1. **Scope**: administrative Walloon Region, as for wind (onwind README §Scope).
2. **Regulatory anchor**: the *Circulaire relative aux permis d'urbanisme pour
   le photovoltaïque* (14 March 2024, MB 16 April 2024; first version 2022) —
   the PV counterpart of the Cadre de référence éolien. Its plan-de-secteur
   compatibility table is the positive list (same construction as wind).
   Agricultural zone: "non" (derogation D.IV.11 / D.IV.13 possible) — the
   agrivoltaic question is therefore a *derogation / policy* question, carried
   as scenarios, as the wind agricultural corridor was.
3. **Gisements** (land categories) rather than one funnel: degraded land
   (friches/SAR, CET, extraction zones not yet exploited, motorway/rail edges,
   industrial basins), economic-activity zones, water bodies (floating), and
   agricultural land (agrivoltaics). Each has its own density.
4. **Capacity** = eligible area × density, after a minimum-park-size and
   compactness filter (the PV analogue of the wind placement step).
5. Hard-to-settle choices become "Et si… ?" scenarios in the dashboard, as for
   wind.

## What the regulation research established (refs/research_pv_regulation.md)

- No numeric framework: the 2024 circular is indicative and has **no setback,
  size, height, slope or farm-share figure**. Every number the study uses is
  therefore either a *hard legal exclusion* (refuse list, zone naturelle/parc),
  a *modelling assumption* (stated, bracketed, priced in the sensitivity), or a
  *policy choice* (dashboard "Et si… ?").
- Refuse (circular p. 9): Natura 2000, RN domaniales/agréées, RF, ZHIB, CSIS.
  Avoid: SGIB, périmètres de liaison écologique, PIP, point de vue remarquable,
  ICHE, sites classés, water bodies except industrial basins, karst/flood
  hazard, trackers, visible overburden mounds.
- Zoning (CoDT v48.1 + circular): conform/tolerated — ZAE mixte/industrielle
  (not compromising the zone), ZSPEC (incl. C.E.T.D.), zones d'enjeu; time-
  limited — zone d'extraction / dépendances d'extraction not yet exploited,
  C.E.T. not yet exploited; derogation (D.IV.11 + D.IV.13, restrictive) —
  agricultural zone (only pilots / poor soils / already artificialised), forest,
  espaces verts (closed CETs); excluded — naturelle, parc.
- Brownfields (SAR, 2 058 sites, 3 224 ha): PV only *temporarily*, pending
  reindustrialisation (2024 circular). BDES land: no étude d'orientation.
- Agrivoltaics: no decree; farmland "en cours d'exploitation" excluded except
  research pilots; DPR 2024-2029 excludes PV on agricultural parcels from
  acceleration zones. Livre blanc: yield ≥ 80 %, GCR ≤ 40 % (pilots),
  Wierde 10 MWc/14 ha (0.71 MWc/ha, GCR 35 %), quota ≤ 20 % (or 30 %) of
  rooftop PV, ~0.6 % SAU needed for the 2030 target, GLAES areas
  56 787 / 145 855 / 245 233 ha, permanent grassland must not be destroyed.
- Targets: PACE 2030 5 100 GWh PV (~6 GWc), no rooftop/ground split.
  Installed ≈ 2.4 GWc end 2025, ground-mounted a small share (largest parks:
  INEOS Jemeppe 30 ha, Alconval Braine-l'Alleud ~12 MWc/19 ha, Wierde,
  Tertre 6.4 MWc/9 ha, Soignies floating 6.1 MWc).
- Other estimates: APERe 2020 brownfields ≥ 2.5 GWc; SPW 2020 "6 000 GWh
  plausible" (study not online); model today 13 GW (custom_potentials.csv).

## Method (decided 2026-09-29)

- **Grid**: 20 m, EPSG:3035, admin Region; each constraint layer burnt on its
  own (buffered feature by feature, never unioned) into a bit of a `uint32`
  code raster. 20 m because PV parcels are narrow and small (median SIGEC
  parcel ~1–2 ha); 127 M cells, ~0.5 GB for the code raster.
- **Two axes**, not one funnel:
  1. *exclusions* (families, as for wind): nature (refuse list + zone
     naturelle/parc), forest & green zones, landscape & heritage, hazards &
     technical (flood, karst, landslide, catchment IIa, slope/aspect,
     buildings, roads/rail), already built;
  2. *gisements* (what the remaining land is, in priority order): water
     bodies, CET, SAR/brownfields, extraction zones, infrastructure edges,
     ZAE, ZSPEC/enjeu, agricultural parcels by crop class (SIGEC), other.
- **Park filter** (PV analogue of the wind placement): morphological opening
  (minimum width) + minimum contiguous area; densities per gisement × system.
- **Policy layer** on top of the technical potential: the share of each
  gisement a government would open (brownfields reserved for reindustrialisation,
  ZAE share, agrivoltaic quota as % SAU or % of rooftop, floating coverage).
- **Calibration**: OSM ground-mounted PV polygons in Wallonia → avoidance
  ratios per layer, observed MWc/ha where capacity is tagged.
- **Energy**: atlite PV on the 2010 SARAH-3/ERA5 cutout (the model's weather
  year), fixed south 30–35°, and E-W / vertical bifacial for agrivoltaics.

## State (2026-09-29, 19:00) — second version, published

- [x] user review 1 applied:
  - poor soils: the AWAC map examined (percentile ranking of water reserve and
    depth; 110 000 ha, 78 % farmed); realistic share of the derogation built
    from LPIS, curtilage (40 m) and revealed agricultural use per soil unit
    (`scripts/soil_evidence.py`): 5.1 %, central; 0 / 100 % priced
  - agrivoltaics: reference = 0.6 % of the SAU on grassland (Livre blanc, a
    2030 figure; the model runs to 2050)
  - dashboard: differentials (+/- GWc against the choice's reference option)
    instead of totals; "Règle actuelle" label for brownfields with a note;
    cache-busting build stamp
- [x] reference 6.25 GWc (circular strictly 2.6); report, README updated
- [x] dashboard published: https://pypsa.squoilin.eu/pv_sol_wallonie/
- [ ] commit — not done
- [ ] known quirk: `build_cnsw` failed twice under Snakemake with
      "OSError: Bad address: /bin/sh" (spawn), run by hand and `--touch`ed

Run commands (from `workflow_pv_wal/`):

```bash
snakemake download -c3 --resources net=1 mem_mb=6000 --keep-going --rerun-triggers mtime
snakemake potential validate_fleet energy -c2 --resources mem_mb=8000 --rerun-triggers mtime
```

Known data gaps: PdS "points de vue remarquable" perimeters published empty;
SGIB not published; BDES under restricted licence (not used); no Walloon
register of ground PV parks (OSM: 88 parks >= 0.2 ha, 241 ha, 12 tagged).
