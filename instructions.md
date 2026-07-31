# PyPSA-Wal — running instructions

Sector-coupled energy system optimisation for Belgium with emphasis on the
Wallonia region (`BEWAL`), built on [PyPSA-Eur](https://github.com/PyPSA/pypsa-eur).

**Repository:** [https://github.com/IntSusEnergySystems/pypsa-wal](https://github.com/IntSusEnergySystems/pypsa-wal)

These instructions describe how to install the environment, run the Snakemake
workflow **locally**, and offload the LP solve to the **NIC5 / CÉCI** cluster
using the helper scripts in [`cluster/`](cluster/). The main [`README.md`](README.md)
is unchanged; this file is the operational guide. Shared TIMES/PyPSA cost and
potential assumptions are documented in [`common_parameters.md`](common_parameters.md).

The workflow follows the same strategy as
[pypsa-eur_negawatt](https://github.com/PyPSA/pypsa-eur_negawatt): data
retrieval and network preparation run where you have internet; only the
memory-intensive Gurobi solve is optionally delegated to the cluster.

---

## Model overview

| Item | Value |
|------|-------|
| Config file | [`config/config.walloon.yaml`](config/config.walloon.yaml) |
| Run name (`RDIR`) | `walloon-model` |
| Foresight | Myopic (2025 → 2030 → 2040 → 2050) |
| Countries | BE, FR, GB, NL, DE, LU |
| Spatial clustering | Custom 3-node Belgium (`adm` + `custom_busmap_BE`) |
| Temporal resolution | Sector snapshots (`resolution_sector: 6h` in default Walloon config) |
| Solver | Gurobi (`gurobi-default`) |

Walloon-specific settings (nuclear expansion, custom potentials/costs, NTC
constraints, cross-border flows) are documented in [`doc/walloon.rst`](doc/walloon.rst).

### The TIMES-coupled multi-scenario config

[`config/config.times-pypsa.yaml`](config/config.times-pypsa.yaml) is the
TIMES↔PyPSA coupled study. It differs from `config.walloon.yaml` in three ways
that change every output path:

| Item | Value |
|------|-------|
| `run.prefix` | `times-pypsa` |
| `run.name` | a **list** of scenarios (`scen_base`, `scen_corrige`, …) |
| `run.scenarios.enable` | `true`, overrides from [`config/scenarios.walloon.yaml`](config/scenarios.walloon.yaml) |

With `run.scenarios.enable: true`, `get_rdir()` returns `times-pypsa/{run}/`
instead of a fixed directory, so **`RDIR` contains a `{run}` wildcard** and
results land in one tree per scenario:

```
resources/times-pypsa/scen_base/    results/times-pypsa/scen_base/
resources/times-pypsa/scen_corrige/ results/times-pypsa/scen_corrige/
```

Each scenario names its own TIMES `.vd` file (`sector.times_file`). Those files
are gitignored — symlink them next to the others before running:

```bash
ln -sfn /path/to/TIMES_PyPSA/data/scen_base_251129_0112.vd    data/walloon/
ln -sfn /path/to/TIMES_PyPSA/data/scen_corrige_251129_0112.vd data/walloon/
```

> **Writing rules for a scenario run.** Because `RDIR` holds a wildcard, every
> `expand()` over `RESULTS` or `resources()` needs `allow_missing=True`, or
> Snakemake aborts at parse time with
> `WildcardError: No values given for wildcard 'run'`. Any file name that
> embeds the run name (the SEPIA `{study}` label) must use the `{run}` wildcard
> — see `STUDY` / `study_dir()` in [`rules/postprocess.smk`](rules/postprocess.smk).

### Output paths

Intermediate files live under `resources/walloon-model/`. Final solved networks
and plots are under `results/walloon-model/`. Network files follow the usual
PyPSA-Eur wildcard pattern with empty `opts` and `sector_opts`:

```
results/walloon-model/networks/base_s_adm___2025.nc
results/walloon-model/networks/base_s_adm___2030.nc
…
```

(Three underscores between `adm` and the year — both `opts` and `sector_opts` wildcards are empty strings.)

---

## Shared TIMES/PyPSA parameters

Assumptions that both TIMES-WAL and PyPSA-WAL must share (technology costs and
lifetimes, fuel prices, Walloon RES potentials, CO₂ trajectory, NTCs, …) live in
[`config/input_parameters_for_models.csv`](config/input_parameters_for_models.csv).
Monetary values are on an **EUR2025** base. Full design, audit, and modeller
decisions: [`common_parameters.md`](common_parameters.md).

**Editing the CSV alone does not change a PyPSA run.** Push the values into the
input files the workflow already reads:

```bash
python scripts/build_common_parameters.py --write --dry-run   # preview
python scripts/build_common_parameters.py --write
```

`--write` **patches values in place** for most destinations. The structure,
sources and comments of those files are hand-maintained and survive, so
`git diff` after a `--write` shows exactly what the shared table changed.
The exception is `discount_rates.csv`, which is **generated wholesale** from
`hurdle:*` rows plus `config/hurdle_rate_mapping.csv` (still committed).

| Family | Master-CSV target | File patched / generated |
|--------|-------------------|--------------------------|
| Costs / lifetimes / fuel prices | `cost:<tech>:<param>` | `data/walloon/custom_costs.csv` |
| Per-technology hurdle rates | `hurdle:<sector>` (+ mapping) | `data/walloon/discount_rates.csv` (**generated**) |
| Social discount rate (SDR) | `config:costs.social_discountrate` | `config.walloon.yaml` / `config.times-pypsa.yaml` (synced) |
| Financial-rate fill (unmapped fallback) | — | **PyPSA default** in `config.default.yaml` (`0.07`); not overridden in walloon configs |
| Walloon RES / biomass potentials | `potential:<bus>:<tech>:<attr>` | `data/walloon/custom_potentials.csv` |
| Cross-border NTCs | `ntc:<A>-<B>` | `data/walloon/ntc_<year>.csv` |
| CO₂ trajectory | `config:budget_national` | `config/config.walloon.yaml` |

There is no overlay config file and no load-order requirement — the ordinary run
command already picks the shared values up:

```bash
snakemake --configfile config/config.walloon.yaml --cores 16 -call
```

**Failsafe.** A patch may only rewrite the `value` cell of a row that already
exists. If a row would have to be added or removed, or a `planning_horizon: all`
row would have to hold a value that varies by horizon, or the units disagree on
scale (`/kW` vs `/MW`), `--write` aborts and tells you which file needs a manual
edit. Nothing is written for a file that fails.

`--check` re-runs the whole patch as a dry run and fails if any file has drifted
out of sync — wire it into CI or run it before a solve:

```bash
python scripts/build_common_parameters.py --check
python scripts/build_common_parameters.py --report   # + summary of the master CSV
```

`--check` also reports **technology-data drift**: rows tagged
`data_origin_choice: PyPSA` that carry no override row take their value straight
from the pinned archive, so if the archive disagrees with the negotiated figure
TIMES and PyPSA silently diverge.

### Sensitivity runs

Do **not** copy `custom_costs.csv` to vary one number. Override the cost table
from the scenario file instead — see `scen_nuc11500` / `scen_nuc13500` in
[`config/scenarios.walloon.yaml`](config/scenarios.walloon.yaml):

```yaml
scen_nuc13500:
  costs:
    overwrites:
      investment:
        nuclear: 13500000   # EUR/MW_e (= 13500 EUR/kW_e)
```

`costs.overwrites` is applied by `scripts/process_cost_data.py` on top of the
custom-costs file and *before* the annuity, so `capital_cost` follows. Values are
in **EUR/MW** (the table is already converted from `/kW` at that point) and must
be written as plain numbers: PyYAML follows YAML 1.1, where `13.5e6` parses as a
string, not a float.

Soft-linked **demands** (TIMES → PyPSA) are a separate path — see
[`times_data_extraction.md`](times_data_extraction.md), not the common-parameters CSV.

---

## Prerequisites

- Linux (local or cluster login node)
- [Conda](https://docs.conda.io/) or [Mamba/Micromamba](https://mamba.readthedocs.io/)
- A valid [Gurobi licence](https://www.gurobi.com) (academic licence is sufficient for local runs)
- ~30 GB disk space (data bundle, weather cutout, intermediate files, results)
- For cluster runs: CÉCI SSH access to NIC5 (typically via the `sqvpn` VPN) and scratch space on `$GLOBALSCRATCH`

Observed local footprint for the default Walloon configuration (PR #3, Sep 2025):

| Metric | Value |
|--------|-------|
| Wall-clock time (full workflow) | ~19 min |
| Peak RAM | ~8.2 GB |

Observed for `config.times-pypsa.yaml` (2 scenarios × 4 horizons, 6h, 12 threads,
24-core / 124 GB workstation, 26 Jul 2026):

| Metric | Value |
|--------|-------|
| Wall-clock, build phase (both scenarios, cutout cached) | ~50 min |
| Wall-clock, myopic solve + summaries + plots | ~35 min |
| Peak RAM per solve | ~7.5 GB (well under the 100 GB cap) |
| `results/times-pypsa/<scenario>/` on disk | ~680 MB each |

---

## Environment setup

Use the **same conda environment name and specification** as pypsa-eur and
pypsa-eur_negawatt: `pypsa-eur`, defined in [`envs/environment.yaml`](envs/environment.yaml).

```bash
cd /path/to/pypsa-wal
conda env create -f envs/environment.yaml    # first time only
conda activate pypsa-eur
```

If the environment already exists (e.g. from pypsa-eur_negawatt), update it:

```bash
conda env update -n pypsa-eur -f envs/environment.yaml --prune
conda activate pypsa-eur
```

Sanity check:

```bash
python -c "import pypsa, snakemake, gurobipy; print('OK')"
```

### Gurobi licence (local)

The workflow is configured to use Gurobi. Obtain a free academic licence at
<https://www.gurobi.com/academia/academic-program-and-licenses/>.

Place the licence file at `~/gurobi.lic` or set:

```bash
export GRB_LICENSE_FILE=/path/to/gurobi.lic
```

On NIC5, Gurobi uses a **floating token-server licence**; `./cluster/nic5.sh setup`
copies the module licence to `~/gurobi.lic` automatically (see cluster section below).

---

## Running locally

Activate the environment, then invoke Snakemake with the Walloon config overlay:

```bash
conda activate pypsa-eur
cd /path/to/pypsa-wal

# Dry run — list jobs without executing
snakemake --configfile config/config.walloon.yaml --cores 16 -n

# Full workflow (retrieve data, build networks, solve, post-process, report)
snakemake --configfile config/config.walloon.yaml --cores 16 -call
```

The `-call` flag runs all rules needed for the default `all` target, including
data retrieval from Zenodo/HTTP, network building, four myopic solves, summary
CSVs, and plots.

### Local resource settings — 12 threads, 100 GB, 6h

The pypsa-eur defaults (`solving.mem_mb: 128000`, `gurobi-default.threads: 32`)
are sized for a cluster node and **must not be used on a workstation**: 32 Gurobi
threads on a 24-core box thrashes, and a 128 GB request on a 124 GB machine
invites the OOM killer. Local runs use:

| Setting | Value | Where |
|---------|-------|-------|
| Gurobi threads (= Snakemake `threads` of the solve rule) | **12** | `solving.solver_options.gurobi-default.threads` |
| `solving.cpus` | **12** | keep in sync with the above |
| Memory per solve | **100 GB** (`mem_mb: 100000`) | `solving.mem_mb` |
| Sector time aggregation | **6h (suggested for testing)** | `clustering.temporal.resolution_sector` |

These are set in [`config/config.times-pypsa.yaml`](config/config.times-pypsa.yaml)
(and match the 6h default of `config.walloon.yaml`). Pass matching limits on the
command line so Snakemake never schedules two solves at once:

```bash
snakemake --configfile config/config.times-pypsa.yaml --cores 12 --resources mem_mb=100000 -call
```

A finer resolution (3h) doubles the LP and and might require running on NIC5 `hmem`, not locally (see the cluster section).

### Solve chain only

If intermediate files already exist under `resources/walloon-model/`:

```bash
snakemake --configfile config/config.walloon.yaml --cores 16 -call solve_sector_networks
```

### Cluster-equivalent solver settings (local)

`config.walloon.yaml` still inherits the thread count and memory of
`config.default.yaml` (32 threads / 128 GB) — see the section above for the local
values to use instead. To match the NIC5 allocation locally:

```bash
snakemake --configfile config/config.walloon.yaml \
  --configfile cluster/config_cluster.yaml \
  --cores 30 -call solve_sector_networks
```

(`cluster/config_cluster.yaml` only overrides `solving.mem_mb`, `solving.cpus`,
and Gurobi `threads`; it does not change model physics.)

### Reducing runtime for testing

The default Walloon config already uses a **6h** sector time aggregation
(`clustering.temporal.resolution_sector: 6h`). For even faster checks during development:

1. Reduce planning horizons in `config/config.walloon.yaml`, e.g. keep only `2050`.
2. Or run a subset of targets explicitly:

   ```bash
   snakemake --configfile config/config.walloon.yaml --cores 4 -call \
     results/walloon-model/networks/base_s_adm___2050.nc
   ```

3. Disable optional retrieval steps in a local override (`config/config.yaml`) if
   data are already cached — see [`config/config.default.yaml`](config/config.default.yaml)
   under `enable:`.

Re-enabling horizons or resolution changes re-triggers upstream build rules.

### Logs

| Location | Contents |
|----------|----------|
| `logs/walloon-model/` | Per-rule Snakemake logs |
| `results/walloon-model/logs/*_solver.log` | Gurobi solver output per horizon |
| `results/walloon-model/logs/*_python.log` | Python-side solve logs |
| `.snakemake/log/` | Master Snakemake run log |

After a successful local solve, publish results to the Wallonie Explorer with
`./cluster/nic5.sh upload` (raw results) followed by the ClimAct CSV extraction
described in [Publishing to Wallonie Explorer (S3)](#publishing-to-wallonie-explorer-s3).

---

## Running the optimisation on NIC5 / CÉCI

The LP solve is the most memory- and CPU-intensive step. The scripts in
[`cluster/`](cluster/) run **only the myopic solve chain** on NIC5 **`hmem`**
(~1 TB RAM per node), while data retrieval, network preparation, and
post-processing stay on your machine.

### Rationale

- NIC5 **compute nodes have no internet**, so data download and cutout build
  cannot run there. Un-solved networks are **prepared locally**, transferred,
  solved on the cluster, and pulled back.
- Gurobi on NIC5 uses a **token-server licence** (`nic5-login1`); the conda
  `gurobipy` checks out a token automatically after `setup`.
- Snakemake runs on the **login node** (internet for storage providers) and
  submits each rule to Slurm. Compute nodes run only `add_brownfield` and
  `solve_sector_network_myopic`.

Unlike pypsa-eur_negawatt, pypsa-wal has a **single scenario** and a fixed
temporal resolution in config — cluster commands do not take `<scenario>` or
`<resolution>` arguments.

### One-time setup

1. Edit [`cluster/config.sh`](cluster/config.sh): set `REMOTE` (SSH alias),
   `REMOTE_DIR` (scratch path, e.g. `$GLOBALSCRATCH/pypsa-wal`), and review
   Slurm partition/memory defaults.
2. Ensure VPN/SSH access to NIC5 works: `ssh nic5 hostname`.
3. Install the environment on the cluster:

   ```bash
   ./cluster/nic5.sh setup
   ```

   This runs [`cluster/cluster_setup.sh`](cluster/cluster_setup.sh) remotely:
   Miniforge, `pypsa-eur` conda env, Gurobi licence copy, import checks.

### Full cluster workflow

```bash
conda activate pypsa-eur          # local machine
./cluster/nic5.sh run             # prepare → push → solve → wait → pull → postprocess
```

Or step by step:

| Command | What it does |
|---------|--------------|
| `./cluster/nic5.sh prepare` | **Local**: build un-solved networks for all four horizons (`add_existing_baseyear` brownfield for 2025, `prepare_sector_network` bases for 2030–2050) |
| `./cluster/nic5.sh push` | `rsync` code + `resources/` + `data/` (minus multi-GB cutout) + `.snakemake/metadata` to scratch |
| `./cluster/nic5.sh solve` | Launch Slurm orchestrator for the four `solve_sector_network_myopic` jobs |
| `./cluster/nic5.sh stop` | Cancel your Slurm jobs and Snakemake orchestrators |
| `./cluster/nic5.sh status` | `squeue`, orchestrator log tail |
| `./cluster/nic5.sh wait` | Block until the orchestrator finishes |
| `./cluster/nic5.sh pull` | `rsync` solved `results/` and cluster logs back |
| `./cluster/nic5.sh postprocess` | **Local**: `--touch` solve outputs, rebuild summary CSVs and `costs.svg`, upload to S3 (test) |
| `./cluster/nic5.sh upload` | Publish `results/` to Intervectoriel S3 (`test/` by default) |
| `./cluster/nic5.sh shell` | Interactive shell in the cluster checkout |

**Progress during `prepare`:** output is streamed to the terminal and logged in
`cluster/logs/prepare.log`. Snakemake also writes to `.snakemake/log/` and
`logs/walloon-model/`. The first local run downloads the data bundle and weather
cutout (~several GB) and can take hours; subsequent runs are incremental.

### Post-processing after pull

`./cluster/nic5.sh run` calls `postprocess` automatically after `pull`. To run it
manually:

```bash
./cluster/nic5.sh postprocess
```

The script:

1. Aligns local brownfield mtimes with pulled solves when those files exist locally.
2. Runs Snakemake **`--touch`** on the four solved `results/walloon-model/networks/*.nc`
   files only (does not re-run Gurobi).
3. Runs summary targets: `results/walloon-model/csvs/costs.csv`,
   `results/walloon-model/graphs/costs.svg`, `results/walloon-model/csvs/cumulative_costs.csv`.
4. Uploads to S3: the full `results/walloon-model/` tree to `pypsa_raw_results/`, and
   `results/walloon-model/explorer/` CSVs to `scenarios/` when that folder is populated
   (see [Publishing to Wallonie Explorer (S3)](#publishing-to-wallonie-explorer-s3)).

To skip the S3 step: `SKIP_S3_UPLOAD=1 ./cluster/nic5.sh postprocess`

> **Warning — `--touch`**: updates modification times only; it does **not**
> verify file contents. Use only after a successful cluster solve and `pull`.
> Never add `--forcerun` on solve rules.

### Verifying a successful run

After `./cluster/nic5.sh run` (or individual steps):

| Check | What to look for |
|-------|------------------|
| Cluster solve | `cluster/logs/orchestrate.log` ends with `5 of 5 steps (100%) done` or `Complete log` |
| Solved networks | `results/walloon-model/networks/base_s_adm___*.nc` (four files) |
| Gurobi optimality | `grep 'Optimal objective' results/walloon-model/logs/base_s_adm___*_solver.log` |
| Postprocess | `cluster/logs/postprocess.log` completes without errors |
| Local prepare | `cluster/logs/prepare.log` |

Quick commands:

```bash
grep -E 'steps \(100%\) done|Complete log' cluster/logs/orchestrate.log
ls -lh results/walloon-model/networks/base_s_adm___*.nc
grep 'Optimal objective' results/walloon-model/logs/base_s_adm___*_solver.log
ls -lt results/walloon-model/graphs/costs.svg
```

To cancel a run in progress: `./cluster/nic5.sh stop`

### Slurm resource settings

CECI expects allocations to match actual usage — see the
[CECI job efficiency guide](https://support.ceci-hpc.be/doc/SubmittingJobs/JobEfficiency/).

| What | Value | Where |
|------|-------|-------|
| Slurm `--cpus-per-task` (solve) | **16** | `solving.cpus` in [`cluster/config_cluster.yaml`](cluster/config_cluster.yaml) |
| Gurobi threads | **16** | `solving.solver_options.gurobi-default.threads` (same file) |
| Slurm memory (solve) | **~1 TB** (`1000000` MB) | `solving.mem_mb` in `cluster/config_cluster.yaml` |
| Partition | **`hmem`** | `SOLVE_PARTITION` in [`cluster/config.sh`](cluster/config.sh) |
| Light rules (`add_brownfield`) | 1 CPU, 16 GB | `--default-resources` in `nic5.sh solve` |

Fine temporal resolution (e.g. `resolution_sector: 6h`) makes sector-coupled
PyPSA models memory-hungry during Gurobi model generation — **`hmem` is required**
for production solves on NIC5. Do not use the `batch` partition for these jobs unless
you also coarsen the time resolution substantially.

To change solve CPUs or memory, edit `cluster/config_cluster.yaml` (`solving.cpus`,
`solving.mem_mb`) and keep Gurobi `threads` in sync with `cpus`. Do not exceed the
hmem node memory limit (~1 000 000 MB on NIC5).

---

## Publishing to Wallonie Explorer (S3)

Solved PyPSA results are published to the **Intervectoriel** S3 bucket so the
[Wallonie Explorer](https://explorer.test.wallonie.climact.com/) Streamlit app
can display them. This is **separate from SEPIA** (the in-repo HTML/visualisation
tool under `SEPIA/`); Explorer uses its own CSV format produced by the ClimAct
extraction tool.

Operational reference (credentials, contacts, console login): `project-intervectoriel.md`
in the `llm` notes repository.

### End-to-end workflow

```
1. Run PyPSA-Wal (local Snakemake or cluster nic5.sh run)
      ↓  results/walloon-model/networks/*.nc + csvs/ + graphs/
2. Upload raw results → s3://intervectoriel/test/pypsa_raw_results/YYYYMMDD_walloon-model/
      ↓  ./cluster/nic5.sh upload   (automatic after postprocess)
3. Extract Explorer CSVs (ClimAct tool, datapypsa env)
      ↓  49 pypsa/*.csv + strategy/*.csv
4. Copy CSVs to results/walloon-model/explorer/ and stage TIMES .vd in explorer/times/
      ↓  ./cluster/nic5.sh upload   (syncs explorer/ → scenarios/ on S3)
5. Open Explorer test site, pick scenario, click "Clear cache" if needed
```

Steps 2 and 4 can be combined: run step 3 first, copy CSVs into
`results/walloon-model/explorer/`, then run `./cluster/nic5.sh upload` once.

### S3 layout and naming

Bucket: `intervectoriel` (region `eu-central-1`). The Explorer test site reads
from the `test/` prefix.

```
s3://intervectoriel/test/
├── pypsa_raw_results/                         ← full Snakemake results/ tree
│   └── YYYYMMDD_<run_name>/                   e.g. 20260717_walloon-model/
│       ├── csvs/ graphs/ networks/ logs/ maps/ configs/
│       └── run.json
├── scenarios/                                 ← Explorer scenario picker
│   └── <type>__<scenario>__YYYYMMDD/          e.g. pypsa__walloon-model__20260717
│       ├── pypsa/                             ← 49 Streamlit CSVs
│       ├── strategy/                          ← strategy_metrics*.csv
│       └── times/                             ← TIMES .vd file(s) — see times_data_extraction.md
├── archive_pypsa/
└── fallback_pypsa/
```

**Naming rules** (must match exactly — Explorer ignores folders with the wrong shape):

| S3 destination | Pattern | Walloon example |
|----------------|---------|-----------------|
| Raw results | `YYYYMMDD_<run_name>` | `20260717_walloon-model` |
| Scenario folder | `<type>__<scenario>__YYYYMMDD` | `pypsa__walloon-model__20260717` |
| Explorer display label | `{scenario} ({type}) - DD/MM/YYYY` | `walloon-model (pypsa) - 17/07/2026` |

The `<type>` prefix comes from the extraction config `run_nickname`
(`20260717_pypsa` → type `pypsa`). Other projects use `times-pypsa`, `sensibilité`, etc.

### Prerequisites

- AWS CLI with profile `intervectoriel` (see `project-intervectoriel.md`):

  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  export AWS_PROFILE=intervectoriel
  aws sts get-caller-identity --region eu-central-1
  ```

- Solved results under `results/walloon-model/` (four `.nc` networks, solver logs with
  `Optimal objective`).

### Step 1 — Upload raw results

Runs automatically at the end of `./cluster/nic5.sh postprocess` and `./cluster/nic5.sh run`.
Disable with `SKIP_S3_UPLOAD=1` or `AUTO_UPLOAD_S3=0` in [`cluster/config.sh`](cluster/config.sh).

```bash
./cluster/nic5.sh upload              # manual
./cluster/nic5.sh upload --dry-run    # preview
./cluster/upload_s3.sh                # standalone (same behaviour)
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `S3_ENV` | `test` | `test` or `prod` prefix |
| `RESULTS_DIR` | `results/<RUN_NAME>` | Results tree to upload — override for a `prefix/{run}` layout |
| `UPLOAD_ID` | `YYYYMMDD_<RUN_NAME>` | Folder under `pypsa_raw_results/` |
| `SCENARIO_ID` | `pypsa__<RUN_NAME>__YYYYMMDD` | Folder under `scenarios/` |
| `UPLOAD_SKIP_NETWORKS` | `0` | Set `1` to omit large `.nc` files |
| `SKIP_S3_UPLOAD` | `0` | Set `1` to skip upload in `postprocess` |
| `AUTO_UPLOAD_S3` | `1` | Set `0` to never auto-upload from `postprocess` |

Implementation note: upload uses [`cluster/upload_s3.sh`](cluster/upload_s3.sh) (bash,
not Snakemake) — same pattern as `nic5.sh push`/`pull`, keeps AWS credentials and
network access on the local machine.

#### Uploading a multi-scenario run

`RUN_NAME` names the S3 folders and must not contain a slash, so point
`RESULTS_DIR` at the scenario tree and set the two IDs explicitly — once per
scenario (`--dry-run` first; ~680 MB and ~1060 files per scenario):

```bash
export PATH="$HOME/.local/bin:$PATH"
DATE=$(date +%Y%m%d)
for s in scen_base scen_corrige; do
  RUN_NAME="times-pypsa_$s" \
  RESULTS_DIR="$PWD/results/times-pypsa/$s" \
  CONFIGFILE=config/config.times-pypsa.yaml \
  UPLOAD_ID="${DATE}_times-pypsa_$s" \
  SCENARIO_ID="times-pypsa__${s}__${DATE}" \
  ./cluster/upload_s3.sh
done
```

This publishes the raw tree only. The Explorer scenario folders stay empty until
the ClimAct CSVs are extracted per scenario (Step 2), which the upload script
warns about.

### Step 2 — Extract Explorer CSVs (ClimAct tool)

Snakemake postprocess produces summary CSVs (`costs.csv`, `energy.csv`, …) under
`results/walloon-model/csvs/`. The **Streamlit Explorer expects a different set**
of 49 CSV files (`balancing_capacities.csv`, `load_temporal_2025.csv`, …) generated
by the ClimAct extraction repo, which on this workstation lives at:

```
/home/sylvain/svn/climact-pypsa-eur_results_extraction-88d352b59aa4
```

It is **not** a git checkout (an unpacked archive), so local edits there are not
tracked — note them somewhere when you make them.

#### One-time setup

The `datapypsa` env is already installed on this machine. To recreate it:

```bash
# Separate conda env — pypsa 0.35.x required (pypsa-eur uses pypsa 1.x and will fail)
conda create -n datapypsa -c conda-forge -y python=3.11 pypsa=0.35.2 pandas \
  matplotlib plotly pyyaml openpyxl cloudpathlib boto3 s3fs dask joblib
```

`scripts/graph_extraction_main.py` defaults to `config_extraction_OET.yaml`;
it reads the `EXTRACTION_CONFIG` environment variable to pick another file, so a
Walloon run needs no source edit — see the run command below. (That one-line
`os.environ.get` was added locally on 2026-07-26; the OET default is unchanged.)

#### Per-run extraction

Set `UPLOAD_DATE=$(date +%Y%m%d)` and `UPLOAD_ID="${UPLOAD_DATE}_walloon-model"`.

1. **Symlink** local results into the extraction repo (folder name = `UPLOAD_ID`):

   ```bash
   EXTRA=/path/to/climact-pypsa-eur_results_extraction-88d352b59aa4
   mkdir -p "$EXTRA/results"
   ln -sfn /path/to/pypsa-wal/results/walloon-model \
     "$EXTRA/results/${UPLOAD_ID}"
   ```

2. **Edit** `config_extraction_walloon.yaml` in the extraction repo:

   ```yaml
   scenario_extraction:
     run:
       "20260717_walloon-model":          # must match UPLOAD_ID / symlink name
         scenario_nickname: "walloon-model"
         run_nickname: "20260717_pypsa"   # YYYYMMDD_<type> → scenario folder prefix
         config_file: "config.base_s_adm___2050.yaml"
   ```

   Set `download_networks: False` when using the local symlink (or `True` to read
   networks from `s3://intervectoriel/test/pypsa_raw_results/` instead).

3. **Run** extraction (`EXTRACTION_CONFIG` selects the Walloon config):

   ```bash
   cd "$EXTRA"
   PYTHONPATH=. EXTRACTION_CONFIG=config_extraction_walloon.yaml MPLBACKEND=Agg \
     conda run --no-capture-output -n datapypsa python -m scripts.graph_extraction_main
   ```

   Every entry under `run:` is extracted in one pass, so a multi-scenario run
   needs no repetition — list both scenarios and launch once.

   Output:

   ```
   analysis/graph_extraction_st/v6/pypsa__walloon-model__20260717/   ← 49 pypsa CSVs
   analysis/strategy/v6/pypsa__walloon-model__20260717/               ← strategy CSVs
   ```

4. **Stage** for upload via pypsa-wal:

   ```bash
   LABEL=pypsa__walloon-model__20260717   # from run_nickname + scenario_nickname + date
   mkdir -p /path/to/pypsa-wal/results/walloon-model/explorer/pypsa
   mkdir -p /path/to/pypsa-wal/results/walloon-model/explorer/strategy
   cp "$EXTRA/analysis/graph_extraction_st/v6/${LABEL}/"*.csv \
      /path/to/pypsa-wal/results/walloon-model/explorer/pypsa/
   cp "$EXTRA/analysis/strategy/v6/${LABEL}/"*.csv \
      /path/to/pypsa-wal/results/walloon-model/explorer/strategy/
   ```

   Alternatively, upload directly with `aws s3 sync` (see below).

### Steps 2+3 scripted — `nic5.sh extract` / `publish`

The four manual steps above (symlink, `run:` block, extract, stage) are automated
by [`cluster/extract_explorer.sh`](cluster/extract_explorer.sh), and the whole
publish chain is one command:

```bash
./cluster/nic5.sh extract --dry-run   # show symlinks, run: block, staging — writes nothing
./cluster/nic5.sh extract             # extract + stage into results/<run>/explorer/
./cluster/nic5.sh publish             # extract + upload (all scenarios)
```

| Command | Does |
|---------|------|
| `nic5.sh extract` | symlinks each results tree into the extractor, regenerates the `run:` block, runs the ClimAct tool once for all scenarios, stages `explorer/{pypsa,strategy,times}/` (including each scenario's own `sector.times_file` `.vd`) |
| `nic5.sh upload` | publishes; loops over scenarios when `EXPLORER_SCENARIOS` is set |
| `nic5.sh publish` | `extract` + `upload` |

`extract` also accepts `--skip-extract`, which re-stages from an existing
extraction (useful after changing only a display label or a `.vd`).

Extraction is **deliberately not part of `upload_s3.sh`**: upload stays cheap and
idempotent, whereas extraction is a multi-minute job in another conda env, and a
crash mid-way must not publish a half-written `pypsa/` folder.

#### Configuration

All of it is driven by [`cluster/config.sh`](cluster/config.sh) — no paths are
baked into the scripts:

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXTRACTOR_DIR` | `$HOME/svn/climact-pypsa-eur_results_extraction-88d352b59aa4` | Extraction tool checkout |
| `EXTRACTOR_ENV` | `datapypsa` | Its conda env (pypsa 0.35.x) |
| `EXTRACTOR_TAG` | `v6` | `tag` in the extraction config = output subfolder |
| `EXTRACTOR_BASE_CONFIG` | `config_extraction_walloon.yaml` | Template, **never modified** |
| `EXTRACTOR_GEN_CONFIG` | `config_extraction_pypsa-wal.generated.yaml` | Generated copy, selected via `EXTRACTION_CONFIG` |
| `EXTRACTOR_CONFIG_FILE` | `config.base_s_adm___2050.yaml` | Per-horizon snapshot read from `results/<run>/configs/` |
| `EXPLORER_TYPE` | `pypsa` | `<type>` in `<type>__<scenario>__YYYYMMDD` |
| `RUN_PREFIX` | *(empty)* | `run.prefix`; empty = single-run layout |
| `EXPLORER_SCENARIOS` | *(empty)* | `"<scenario>[:<label>] …"`; empty = one run named `RUN_NAME` |
| `UPLOAD_DATE` | today | Shared by extract and upload so one `publish` stamps one date |

The template config is treated as read-only: the script copies it and rewrites
only the `run:` block, so a hand-maintained file in a directory this repo does
not own is never clobbered. Selecting the copy relies on
`graph_extraction_main.py` honouring `EXTRACTION_CONFIG`; `extract` checks for
that and tells you the one-line patch if it is missing.

For `config.times-pypsa.yaml`, uncomment the prepared block in `config.sh`, or
export for a one-off:

```bash
CONFIGFILE=config/config.times-pypsa.yaml RUN_PREFIX=times-pypsa \
EXPLORER_TYPE=times-pypsa EXPLORER_SCENARIOS="scen_base scen_corrige" \
  ./cluster/nic5.sh publish
```

**Display labels are editorial.** `EXPLORER_SCENARIOS` accepts
`<scenario>:<label>`; the label is what the dropdown shows and is never derived
from the scenario name — existing entries use French names, e.g.
`"scen_base:demande-haute scen_corrige:demande-réduite"`.

Expected per scenario: **49** files in `pypsa/`, **3** in `strategy/`
(`strategy_metrics{,_mapping,_t}.csv`), **1** `.vd` in `times/`. Some older
scenarios also carry a `strategy/report/` subfolder of French-named CSVs; that
comes from a separate ClimAct reporting step and is not produced here.

### Step 3 — Upload Explorer CSVs to S3

**Option A** — via pypsa-wal upload script (after staging into `explorer/`):

```bash
cd /path/to/pypsa-wal
SCENARIO_ID=pypsa__walloon-model__20260717 ./cluster/nic5.sh upload
```

**Option B** — direct `aws s3 sync` from extraction output:

```bash
SCENARIO=pypsa__walloon-model__20260717
LABEL="$SCENARIO"
EXTRA=/path/to/climact-pypsa-eur_results_extraction-88d352b59aa4

aws s3 sync "$EXTRA/analysis/graph_extraction_st/v6/${LABEL}/" \
  "s3://intervectoriel/test/scenarios/${SCENARIO}/pypsa/" \
  --profile intervectoriel --region eu-central-1

aws s3 sync "$EXTRA/analysis/strategy/v6/${LABEL}/" \
  "s3://intervectoriel/test/scenarios/${SCENARIO}/strategy/" \
  --profile intervectoriel --region eu-central-1
```

**Option C** — enable built-in upload in the extraction tool (`upload_results: True`
in `config_extraction_walloon.yaml`); it writes directly to the scenario prefix
using the same folder label.

### Step 3b — Publish TIMES data (`.vd`)

If the run used TIMES demand coupling (`sector.times_demand: true`), upload the
source `.vd` file so Explorer can show TIMES charts. See
[`times_data_extraction.md`](times_data_extraction.md) for the full procedure.

Quick version:

```bash
VD=data/walloon/scen_base_coherence_3110.vd   # must match sector.times_file in config
mkdir -p results/walloon-model/explorer/times
cp -L "$VD" "results/walloon-model/explorer/times/$(basename "$VD")"
SCENARIO_ID=pypsa__walloon-model__20260717 ./cluster/nic5.sh upload
```

### Step 4 — Verify in Explorer

```bash
export AWS_PROFILE=intervectoriel
aws s3 ls s3://intervectoriel/test/pypsa_raw_results/20260717_walloon-model/
aws s3 ls s3://intervectoriel/test/scenarios/pypsa__walloon-model__20260717/pypsa/ | wc -l
# expect 49
```

Open [https://explorer.test.wallonie.climact.com/](https://explorer.test.wallonie.climact.com/),
select **`walloon-model (pypsa) - 17/07/2026`**, and click **Clear cache** if the
new scenario does not appear immediately.

### Troubleshooting Explorer

| Symptom | Likely cause / fix |
|---------|-------------------|
| Scenario missing from dropdown | The dropdown is built from `test/scenarios/`, **never** from `pypsa_raw_results/` — a complete raw upload alone shows nothing. Check `aws s3 ls s3://intervectoriel/test/scenarios/<id>/pypsa/`: if it is empty, the ClimAct extraction (Step 2) has not been run for that scenario. |
| Scenario folder exists but is empty | `upload_s3.sh` only syncs `explorer/{pypsa,strategy,times}/` when those folders contain files, and warns loudly when they do not — re-read the upload output. |
| Scenario missing from dropdown (naming) | Folder name must be **three parts** separated by `__`: `<type>__<scenario>__YYYYMMDD`. A two-part name like `walloon-model__20260717` is ignored. |
| Wrong display label | Check `run_nickname` in `config_extraction_walloon.yaml` — the part after `YYYYMMDD_` becomes the `(type)` label (e.g. `20260717_pypsa` → `(pypsa)`). |
| Upload OK but Explorer empty | Click **Clear cache** on the test site; confirm 49 files under `.../scenarios/<id>/pypsa/`. |
| Extraction fails with pypsa import error | Use the `datapypsa` env (pypsa 0.35.x), not `pypsa-eur` (pypsa 1.x). |
| Only raw results on S3 | Run ClimAct extraction, copy CSVs to `results/walloon-model/explorer/`, then `./cluster/nic5.sh upload`. |
| TIMES tab empty | Upload the `.vd` to `explorer/times/` — see [`times_data_extraction.md`](times_data_extraction.md) |

### Production promotion

| Item | Value |
|------|-------|
| Prod Explorer URL | [https://explorer.wallonie.climact.com/](https://explorer.wallonie.climact.com/) |
| Prod S3 prefix | `prod/` |
| Write access to `prod/` | <!-- TODO: confirm with Laurent (lco@climact.com) before first prod upload --> |

```bash
# After validation on test — only when prod write is confirmed:
S3_ENV=prod ./cluster/nic5.sh upload
# Re-run extraction upload with s3_scenario_folder_path: s3://intervectoriel/prod/scenarios/
```

---

## Repository layout (workflow-relevant)

```
.
├── Snakefile                      # Master Snakemake workflow
├── config/
│   ├── config.default.yaml        # PyPSA-Eur defaults
│   ├── config.walloon.yaml        # Walloon study configuration
│   ├── input_parameters_for_models.csv  # Shared TIMES/PyPSA assumptions (EUR2025)
│   └── common_parameters_meta.yaml # EUR_REF + technology-data pin
├── common_parameters.md            # How the shared CSV is audited and wired into pypsa-wal
├── cluster/
│   ├── nic5.sh                    # Local ↔ cluster orchestration (+ extract/publish)
│   ├── upload_s3.sh               # Publish results/ to Intervectoriel S3
│   ├── extract_explorer.sh        # Drive the ClimAct extraction, stage explorer/
│   ├── cluster_setup.sh           # One-time remote env install
│   ├── config.sh                  # SSH paths, Slurm defaults, extractor + scenario config
│   └── config_cluster.yaml        # Solver/memory overrides on NIC5
├── envs/environment.yaml          # Conda env `pypsa-eur`
├── rules/                         # Snakemake rule definitions
├── scripts/                       # Python scripts (incl. walloon_scripts/)
├── data/                          # Static inputs + walloon/ overrides
├── cutouts/                       # Atlite weather cutouts (downloaded)
├── resources/walloon-model/       # Intermediate build artefacts
└── results/walloon-model/         # Solved networks, CSVs, plots
    └── explorer/                  # Staged ClimAct CSVs + TIMES .vd for S3 (pypsa/, strategy/, times/)
```

---

## Hardware requirements (local)

| Resource | Recommendation |
|----------|----------------|
| RAM | ≥ 16 GB (peak ~8 GB observed for default config) |
| CPU | 16 cores for comfortable build parallelism; 30 threads for Gurobi if using cluster overlay locally |
| Disk | ~30 GB |
| Solve time | Minutes to hours per horizon depending on `resolution_sector` |

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|-------------------|
| `Directory cannot be locked` | Another Snakemake instance is running, or a stale lock in `.snakemake/locks/` after a crash — stop the other run or remove the lock if no process is active |
| Gurobi `No Gurobi license` | Set `GRB_LICENSE_FILE` or install `~/gurobi.lic` |
| Gurobi `Model too large for size-limited license` | The academic licence was not found and gurobipy fell back to its built-in demo licence. `GRB_LICENSE_FILE` is exported from `~/.bashrc`, which **non-interactive shells do not read** — export it explicitly when launching from a script, `cron`, `nohup`, or an agent: `export GRB_LICENSE_FILE=$HOME/.gurobi/gurobi.lic` |
| `WildcardError: No values given for wildcard 'run'` | A rule `expand()`s over `RESULTS`/`resources()` without `allow_missing=True` while `run.scenarios.enable: true` — see [The TIMES-coupled multi-scenario config](#the-times-coupled-multi-scenario-config) |
| Plot rules die with `SIGABRT` and `Could not find the Qt platform plugin` | matplotlib picked an interactive backend in a session with no usable display. Run with `MPLBACKEND=Agg` (add `QT_QPA_PLATFORM=offscreen` if Qt is still probed) |
| Cluster job pending on `hmem` | Partition busy (3 nodes, ~1 TB each) — check `squeue -p hmem`; wait for a slot or `./cluster/nic5.sh status` |
| Gurobi / solve OOM on cluster | Raise `solving.mem_mb` in `cluster/config_cluster.yaml` (max ~1 000 000 MB on hmem); ensure `SOLVE_PARTITION=hmem` in `cluster/config.sh` |
| Snakemake rebuilds everything after `pull` | Re-run `./cluster/nic5.sh postprocess` (touch + summaries); do not delete `.snakemake/metadata` locally |
| Missing `config/scenarios.yaml` | Not required unless you set `run.scenarios.enable: true` in config |
| S3 upload fails after postprocess | Check `cluster/logs/upload_s3.log`; verify `aws sts get-caller-identity --profile intervectoriel`; use `SKIP_S3_UPLOAD=1` to postprocess without upload |
| Explorer scenario not in dropdown | See **Troubleshooting Explorer** under Publishing to Wallonie Explorer (S3) |
| First run hangs on Zenodo cutout download | Symlink `cutouts/europe-2013-sarah3-era5.nc` from `~/.cache/snakemake-pypsa-eur/...` if you already retrieved it for pypsa-eur; or wait for the download to finish |
| `retrieve_osm_boundaries` Overpass 406 errors | Pre-populate `data/osm-boundaries/json/{BA,MD,UA,XK}_adm1.json` from another PyPSA-Eur checkout, or retry later |

---

## Licence

Code inherits the [PyPSA-Eur MIT licence](LICENSES/MIT.txt). Data files retain
their original licences as documented in [`doc/licenses.rst`](doc/licenses.rst).
