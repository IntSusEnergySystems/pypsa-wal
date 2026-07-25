# TIMES data in pypsa-wal

Two things: **how the TIMES soft-link demands enter the PyPSA network**
([below](#how-times-demands-enter-the-pypsa-network)), and how to publish the
TIMES scenario file (`.vd`) alongside PyPSA results so the
[Wallonie Explorer](https://explorer.test.wallonie.climact.com/) can display
TIMES-side charts for a coupled run.

This complements the PyPSA CSV extraction documented in
[`instructions.md`](instructions.md) § Publishing to Wallonie Explorer (S3).

For **validating soft-link extraction rules** (multi-level Sankey with
pypsa-wal export highlighting, energy-balance tests), use the sibling
`TIMES_PyPSA` package. Always use `--agg-level custom` when testing or
troubleshooting:

```bash
times-pypsa qa \
  --vd ../TIMES_PyPSA/data/scen_corrige_251129_0112.vd \
  --vdt ../TIMES_PyPSA/data/scen_corrige_251129_0112.vdt \
  --year 2050 \
  --agg-level custom \
  --out-dir /tmp/times_qa_2050/
```

See `TIMES_PyPSA/README.md` (extraction QA, rule schema, rule-change log) and
`TIMES_PyPSA/aggregation.md` (aggregation levels, Sankey colouring, open points).

---

## How TIMES demands enter the PyPSA network

`build_wallon_demands` writes `resources/<run>/wallon_demands_<year>.csv`, one row
per TIMES_PyPSA extraction category (58 as of 2026-07-25) with `TWh` and `PJ`.
Those rows reach the network by three different mechanisms, and knowing which one
applies matters: **two of them are silent name matches**, so a renamed category
stops being used without any error.

1. **Name match against `energy_totals`** —
   `build_population_weighted_energy_totals.py` replaces the Walloon row of every
   column whose name equals a category
   (`nodal_totals.columns.intersection(wallon_demands.index)`). 12 categories:
   `total road`, `electricity road`, `total rail`, `electricity rail`,
   `total {domestic,international} aviation`, `total domestic navigation`,
   `total international navigation`, `total agriculture{, electricity, heat,
   machinery}`.
2. **Name match against the industry frame** —
   `build_industrial_energy_demand_per_node.py`, same idiom. 10 categories:
   `electricity`, `coal`, `coke`, `methane`, `hydrogen`, `naphtha`,
   `solid biomass`, `low-temperature heat`, `ammonia`, `methanol`.
3. **Explicit reads in `prepare_sector_network.py`** — the categories whose names
   are *not* pypsa-eur keys:

   | Where | Categories |
   |---|---|
   | `add_industry`: factor that rescales the whole Walloon electricity load | `total electricity residential` + `total electricity services` + `total rail` + **`residential cooking electricity`** |
   | `add_land_transport`: Walloon engine shares | `total road`, `electricity road`, `hydrogen road` |
   | `write_wallon_heat_demands`: rescales the decentral heat loads | `BEWAL residential urban decentral heat`, `BEWAL residential rural heat`, `BEWAL services urban decentral heat`, plus **`services other fuel`** and the non-electric part of **`residential cooking`** |
   | `write_wallon_heat_demands`: rescales `BEWAL urban central heat` | `residential district heating` + `services district heating` |

30 of the 58 categories declare a `parent`, so they are **subsets** and must never
be added to their parent. The ones that are deliberately read by nothing:

- `services data centre electricity` — a child of `total electricity services`,
  informational only;
- the 23 residential/services boiler, heat-pump, geothermal, solar-thermal and
  electric-heater categories — children of the three `BEWAL … heat` parents;
- `total agriculture` — the parent of the three agriculture children that
  `add_agriculture` does read;
- `retro` — informational: retrofitting is a PyPSA decision variable
  (`sector.retrofitting.retro_endogen`), not a demand to impose.

`electricity road` / `electricity rail` are children too, but they are used as
*shares* of their parent (engine mix, rail electrification) rather than added to
it, which is legitimate. `residential cooking` is a parent whose electric child
feeds the electricity load and whose non-electric remainder feeds the heat load —
so the parent is used exactly once, as a difference (see below).

### Changes of 2026-07-25 — closing the last unserved soft-links

Three soft-linked categories were being exported by TIMES_PyPSA and read by
nothing, so their energy silently left the Walloon balance. All three are now
served, in `scripts/prepare_sector_network.py`:

| Category | Now added to | 2050 |
|---|---|---:|
| `residential cooking electricity` | the Walloon electricity-load factor in `add_industry` | +0.43 TWh |
| `residential cooking` minus its electric child | `BEWAL residential {urban decentral,rural} heat`, pro rata to their heat | +0.84 TWh |
| `services other fuel` | `BEWAL services urban decentral heat` | +0.24 TWh |

Why each was missing:

- **`residential cooking electricity`** left `total electricity residential` when
  TIMES_PyPSA relabelled the `RCOK*` stoves (`RCOKELC100` had been carrying
  `residential other`). The electricity-load sum had not followed, so the Walloon
  load was ~0.5 TWh short.
- **Cooking and tertiary "other energy" fuel have no bus in PyPSA-Eur.** Both
  residential and tertiary heat are built from *space* + *water* only
  (`build_hourly_heat_demand.py`: `uses = ["water", "space"]`). The obvious route
  — writing the `total services cooking` / `total residential cooking`
  `energy_totals` columns — is a **dead end**: those columns are produced by
  `build_energy_totals.py` and read by no script in `scripts/` or `rules/`, so
  substituting them would have made the TIMES coverage table read 100% while the
  energy stayed outside the model. The decentral heat load is the only
  non-electric residential/tertiary sink there is, so that is where they go.

Two caveats, deliberate and reversible (delete the `services_fuel` /
`residential_cooking_fuel` terms in `write_wallon_heat_demands` to revert):

- PyPSA-Eur discards this bucket for every other node, so the Walloon node is now
  more *complete* than its neighbours rather than consistent with them.
- On the heat bus a heat pump may serve the fuel at COP 3 — a reasonable
  electrification story for cooking and miscellaneous building energy, less so for
  the 0.005 PJ of commercial gasoline inside `services other fuel`. The stricter
  alternative is a dedicated inelastic Load on the gas/oil buses (as pypsa-eur
  does for `gas for industry` and `agriculture machinery oil`), which preserves
  the fuel and its CO₂ exactly but needs new components.

A new `times_demand_twh()` helper performs every explicit read and **warns
instead of raising** when a category is absent, so an older
`wallon_demands_*.csv` — or a scenario whose extraction rules dropped a category —
no longer breaks the build.

### Still not consumed: `heating_capacities_*.csv`

`build_wallon_demands` also writes `resources/<run>/heating_capacities_<year>.csv`
(the TIMES heating stock in MW per technology), but **no rule takes it as an
input** — `add_existing_baseyear` still uses pypsa-eur's own
`build_existing_heating_distribution` from
`data/existing_infrastructure/existing_heating_raw.csv`. So the Walloon heating
*demands* come from TIMES while the Walloon existing heating *capacities* do not.
That is the one remaining unconsumed soft-link output; wiring it means replacing
the existing-heating distribution for the Walloon node, which is a modelling
change rather than a plumbing one.

For the TIMES side of these categories — composition, why `ammonia`/`methanol`
stay zero, and the full rule-change log — see
`TIMES_PyPSA/aggregation.md` § *Audit 2026-07-25* and § *Which demand keys
pypsa-wal actually reads*.

---

## What Explorer expects

Each scenario folder under `s3://intervectoriel/test/scenarios/<label>/` can
contain up to three data subfolders:

```
scenarios/<type>__<scenario>__YYYYMMDD/
├── pypsa/       ← 49 Streamlit CSVs (ClimAct graph_extraction_main.py)
├── strategy/    ← strategy_metrics*.csv (same tool, PyPSA-derived)
└── times/       ← TIMES .vd file(s) used as PyPSA demand input
```

| Subfolder | Source | Required for TIMES tab |
|-----------|--------|------------------------|
| `pypsa/` | ClimAct extraction repo | PyPSA charts |
| `strategy/` | ClimAct extraction repo | Strategy indicators |
| `times/` | TIMES model export (`.vd`) | TIMES charts |

**Reference scenarios on S3** (test env, July 2026):

| Scenario | `times/` contents |
|----------|-------------------|
| `times-pypsa__demande-haute__20251204` | `scen_corrige_251129_0112.vd` (~76 MB) |
| `times-pypsa__demande-réduite__20251204` | `scen_base_251129_0112.vd` (~75 MB) |
| `pypsa__walloon-model__20260717` | `scen_base_coherence_3110.vd` (~81 MB) |

Some `times-pypsa` scenarios also have pre-computed summary CSVs under
`strategy/report/` (e.g. `demande_par_secteur.csv`, `capacite_installee.csv`).
Those are **not** produced by the PyPSA extraction scripts in the ClimAct repo;
they appear to be generated separately at ClimAct. The `.vd` upload alone is
sufficient for the Explorer TIMES views (confirmed pattern from existing
scenarios).

---

## Which `.vd` file to use

The file must match the one referenced in the PyPSA config used for the solve.

For the default Walloon run (`config/config.walloon.yaml`):

```yaml
sector:
  times_demand: true
  times_file: data/walloon/scen_base_coherence_3110.vd
```

The file lives in the repo at `data/walloon/scen_base_coherence_3110.vd`
(symlink to `/home/sylvain/svn/TIMES_PyPSA/data/scen_base_coherence_3110.vd`).

Check the config snapshot saved with your results:

```bash
grep times_file results/walloon-model/configs/config.walloon-model.yaml
# or per-horizon configs under results/walloon-model/configs/
```

Other scenario overlays (`config/scenarios.walloon.yaml`, `config.times-pypsa.yaml`)
point at different `.vd` files — always use the one that was actually solved.

---

## Workflow

### 1. Stage the `.vd` locally

Copy (do not symlink — S3 sync needs a real file) into the explorer staging tree:

```bash
VD=data/walloon/scen_base_coherence_3110.vd
mkdir -p results/walloon-model/explorer/times
cp -L "$VD" "results/walloon-model/explorer/times/$(basename "$VD")"
```

Use the **original filename** (e.g. `scen_base_coherence_3110.vd`), matching how
`times-pypsa` scenarios name their files on S3.

### 2. Upload to S3

**Option A** — via pypsa-wal upload script (recommended):

```bash
cd /path/to/pypsa-wal
SCENARIO_ID=pypsa__walloon-model__20260717 ./cluster/nic5.sh upload
```

The script ([`cluster/upload_s3.sh`](cluster/upload_s3.sh)) syncs:

- `results/walloon-model/explorer/pypsa/` → `.../scenarios/<SCENARIO_ID>/pypsa/`
- `results/walloon-model/explorer/strategy/` → `.../strategy/`
- `results/walloon-model/explorer/times/` → `.../times/`

**Option B** — direct AWS CLI:

```bash
export AWS_PROFILE=intervectoriel
SCENARIO=pypsa__walloon-model__20260717
VD=results/walloon-model/explorer/times/scen_base_coherence_3110.vd

aws s3 cp "$VD" \
  "s3://intervectoriel/test/scenarios/${SCENARIO}/times/$(basename "$VD")" \
  --region eu-central-1
```

### 3. Verify

```bash
export AWS_PROFILE=intervectoriel
aws s3 ls s3://intervectoriel/test/scenarios/pypsa__walloon-model__20260717/
aws s3 ls s3://intervectoriel/test/scenarios/pypsa__walloon-model__20260717/times/
```

Expected listing:

```
PRE pypsa/
PRE strategy/
PRE times/
```

Open [https://explorer.test.wallonie.climact.com/](https://explorer.test.wallonie.climact.com/),
select **walloon-model (pypsa) - 17/07/2026**, click **Clear cache**, and check
the TIMES section.

---

## Relationship to other tools

| Tool | Role | Explorer output |
|------|------|-----------------|
| **ClimAct extraction** (`climact-pypsa-eur_results_extraction-88d352b59aa4`) | Reads solved PyPSA `.nc` networks | `pypsa/`, `strategy/` |
| **TIMES `.vd` export** | VEDA/TIMES scenario output | `times/` (upload as-is) |
| **TIMES_PyPSA** (`/home/sylvain/svn/TIMES_PyPSA`) | Parses `.vd` → PyPSA demand CSVs during Snakemake build | Not uploaded to Explorer directly |
| **PyPSA-Wal** `build_wallon_demands.py` | Thin Snakemake wrapper around `times_pypsa` (or copies from `coupling_dir/pypsa_inputs/`) | Not uploaded |

The ClimAct extraction repo does **not** contain a script that converts `.vd` →
Explorer CSVs. TIMES data reaches Explorer as the **raw `.vd` file** in the
`times/` subfolder. PyPSA-side CSVs still require running
`graph_extraction_main.py` (see `instructions.md`).

---

## Full publish checklist (TIMES-coupled run)

1. Run PyPSA-Wal with `times_demand: true` and the desired `times_file`.
2. Upload raw results: `./cluster/nic5.sh upload` (or automatic after postprocess).
3. Run ClimAct PyPSA extraction → copy CSVs to `results/walloon-model/explorer/pypsa/`
   (and `strategy/` if generated).
4. Copy the `.vd` to `results/walloon-model/explorer/times/`.
5. Re-run `./cluster/nic5.sh upload` (or upload `times/` only with Option B above).
6. Verify on Explorer test site.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| TIMES tab empty / missing | Confirm `times/*.vd` exists on S3; click **Clear cache** |
| Wrong TIMES scenario shown | Upload the `.vd` that matches `sector.times_file` in the solved config |
| Scenario not in dropdown | Folder name must be 3-part: `pypsa__walloon-model__20260717` (see `instructions.md`) |
| Upload skipped | Ensure file is under `explorer/times/` with `.vd` extension; check `upload_s3.sh` logs |

---

## Production

After validation on test, upload to prod with:

```bash
S3_ENV=prod SCENARIO_ID=pypsa__walloon-model__20260717 ./cluster/nic5.sh upload
```

Prod write access must be confirmed with ClimAct before first use.
