# TIMES data for Wallonie Explorer

How to publish the TIMES scenario file (`.vd`) alongside PyPSA results so the
[Wallonie Explorer](https://explorer.test.wallonie.climact.com/) can display
TIMES-side charts for a coupled run.

This complements the PyPSA CSV extraction documented in
[`instructions.md`](instructions.md) § Publishing to Wallonie Explorer (S3).

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
| **PyPSA-Wal** `build_wallon_demands.py` | In-workflow `.vd` parser (duplicate of TIMES_PyPSA logic) | Not uploaded |

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
