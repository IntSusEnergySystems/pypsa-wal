# SPDX-License-Identifier: MIT
# Shared configuration for the NIC5 (CECI) cluster workflow.
# Sourced by cluster/nic5.sh. Edit these to match your account/cluster.
#
# Adapted by analogy from pypsa-eur_negawatt/cluster/config.sh (same NIC5/CECI
# target, same shared `pypsa-eur` conda environment). UNTESTED for pypsa-wal --
# see instructions.md ("Running the optimisation on a cluster") before first use.

# --- SSH / paths -------------------------------------------------------------
# SSH host alias (must be defined in ~/.ssh/config, reachable via the CECI VPN).
REMOTE="${REMOTE:-nic5}"
# Working directory on the cluster (use GLOBALSCRATCH, NOT $HOME).
# Use the cluster login name here — not the local workstation user (`whoami`).
REMOTE_DIR="${REMOTE_DIR:-/scratch/ulg/thermlab/squoilin/pypsa-wal}"

# Cluster workflow is headless. Override ~/.ssh/config ForwardX11=yes to avoid
# "No xauth data" warnings without loading modules or setting up xauth.
SSH_OPTS="${SSH_OPTS:--o ForwardX11=no}"

# --- conda environment on the cluster ----------------------------------------
# Same environment name/spec as pypsa-eur_negawatt (envs/environment.yaml here
# is a looser, subset specification -- see instructions.md "Environment setup").
CONDA_ROOT="${CONDA_ROOT:-\$HOME/miniforge3}"
ENV_NAME="${ENV_NAME:-pypsa-eur}"

# Gurobi licence file (token server). Set by `nic5.sh setup`; the module's
# licence is copied to ~/gurobi.lic so no `module load` is needed in jobs.
GUROBI_LIC="${GUROBI_LIC:-\$HOME/gurobi.lic}"
# Path to the cluster Gurobi module licence (source for the copy above).
# Verify this path is still correct on the cluster before running `setup`.
GUROBI_MODULE_LIC="${GUROBI_MODULE_LIC:-/opt/cecisw/arch/easybuild/2023b/software/Gurobi/13.0.0-GCCcore-13.2.0/gurobi.lic}"

# --- Slurm resources ----------------------------------------------------------
# Sector-coupled PyPSA solves at fine temporal resolution (e.g. 6h) need large
# RAM for Gurobi model generation. Use the `hmem` partition on NIC5 (~1 TB per
# node). Memory for solve jobs is set in cluster/config_cluster.yaml
# (`solving.mem_mb`); keep it aligned with the hmem node limit (~1 000 000 MB).
# Light rules (add_brownfield) share the same partition but use DEFAULT_MEM_MB.
# CECI job-efficiency guidance: https://support.ceci-hpc.be/doc/SubmittingJobs/JobEfficiency/
SOLVE_PARTITION="${SOLVE_PARTITION:-hmem}"
SOLVE_RUNTIME="${SOLVE_RUNTIME:-360}"     # minutes (fine resolution needs longer solves)
DEFAULT_PARTITION="${DEFAULT_PARTITION:-hmem}"
DEFAULT_MEM_MB="${DEFAULT_MEM_MB:-16000}"      # light rules (add_brownfield)
DEFAULT_RUNTIME="${DEFAULT_RUNTIME:-120}"
DEFAULT_CPUS="${DEFAULT_CPUS:-1}"              # light rules only; never set globally for solve
MAX_SLURM_JOBS="${MAX_SLURM_JOBS:-2}"

# --- run / scenario ------------------------------------------------------------
# pypsa-wal has a single scenario (config/config.walloon.yaml, run name
# "walloon-model") and does not encode temporal resolution as a `sector_opts`
# wildcard, so -- unlike pypsa-eur_negawatt -- there is no <scenario>/<resolution>
# argument anywhere in this tooling.
CONFIGFILE="${CONFIGFILE:-config/config.walloon.yaml}"
RUN_NAME="${RUN_NAME:-walloon-model}"
HORIZONS="${HORIZONS:-2025 2030 2040 2050}"
CLUSTERS="${CLUSTERS:-adm}"
OPTS="${OPTS:-}"
SECTOR_OPTS="${SECTOR_OPTS:-}"

# --- multi-scenario runs (run.prefix + run.scenarios) --------------------------
# Set these for a config whose RDIR is "<prefix>/{run}" -- e.g.
# config/config.times-pypsa.yaml -- so results live in results/<prefix>/<scenario>/
# instead of results/<RUN_NAME>/. Leave RUN_PREFIX and EXPLORER_SCENARIOS empty
# for a single-run config; the tooling then falls back to RUN_NAME everywhere.
RUN_PREFIX="${RUN_PREFIX:-}"                   # run.prefix, e.g. times-pypsa
# Scenario -> Explorer display label, space-separated "<scenario>:<label>" pairs.
# The label is what the Explorer dropdown shows and is an editorial choice (the
# existing scenarios use French names), so set it deliberately -- it is NOT
# derived from the scenario name. Omit ":<label>" to reuse the scenario name.
EXPLORER_SCENARIOS="${EXPLORER_SCENARIOS:-}"
#
# For config/config.times-pypsa.yaml, uncomment the four lines below (or export
# the same variables ahead of the command for a one-off run):
# CONFIGFILE="${CONFIGFILE:-config/config.times-pypsa.yaml}"
# RUN_PREFIX="${RUN_PREFIX:-times-pypsa}"
# EXPLORER_TYPE="${EXPLORER_TYPE:-times-pypsa}"
# EXPLORER_SCENARIOS="${EXPLORER_SCENARIOS:-scen_base scen_corrige}"
# ...with French display labels instead of the scenario names:
# EXPLORER_SCENARIOS="${EXPLORER_SCENARIOS:-scen_base:demande-haute scen_corrige:demande-réduite}"

# --- local conda invocation ----------------------------------------------------
# How to run the local environment (used by `nic5.sh prepare` / `postprocess`).
# --no-capture-output: stream Snakemake progress to the terminal (conda run buffers by default).
LOCAL_RUN="${LOCAL_RUN:-conda run --no-capture-output -n pypsa-eur}"
LOCAL_CORES="${LOCAL_CORES:-16}"

# --- Intervectoriel S3 (Wallonie Explorer) -----------------------------------
# Used by cluster/upload_s3.sh (called automatically after postprocess).
# Credentials: AWS profile [intervectoriel] in ~/.aws/credentials (see instructions.md).
AWS_PROFILE="${AWS_PROFILE:-intervectoriel}"
AWS_REGION="${AWS_REGION:-eu-central-1}"
S3_BUCKET="${S3_BUCKET:-intervectoriel}"
S3_ENV="${S3_ENV:-test}"                       # test → explorer.test… ; prod → explorer…
AUTO_UPLOAD_S3="${AUTO_UPLOAD_S3:-1}"           # 1 = upload after nic5.sh postprocess/run
SKIP_S3_UPLOAD="${SKIP_S3_UPLOAD:-0}"          # 1 = skip upload even when AUTO_UPLOAD_S3=1
UPLOAD_SKIP_NETWORKS="${UPLOAD_SKIP_NETWORKS:-0}"  # 1 = omit large .nc files
# Optional overrides (defaults: YYYYMMDD_<RUN_NAME> and <RUN_NAME>__YYYYMMDD):
# UPLOAD_ID=20260717_walloon-model
# SCENARIO_ID=pypsa__walloon-model__20260717
# EXPLORER_SRC=results/walloon-model/explorer/pypsa
# Shared by upload_s3.sh and extract_explorer.sh so a single `publish` stamps one
# date on the raw folder, the scenario folder and the extractor run_nickname.
UPLOAD_DATE="${UPLOAD_DATE:-$(date +%Y%m%d)}"

# --- Wallonie Explorer CSV extraction (ClimAct tool) --------------------------
# Used by cluster/extract_explorer.sh (`nic5.sh extract`). The tool lives OUTSIDE
# this repo, is an unpacked archive rather than a git checkout, and needs its own
# conda env (pypsa 0.35.x; the pypsa-eur env has pypsa 1.x and will fail).
EXTRACTOR_DIR="${EXTRACTOR_DIR:-$HOME/svn/climact-pypsa-eur_results_extraction-88d352b59aa4}"
EXTRACTOR_ENV="${EXTRACTOR_ENV:-datapypsa}"
EXTRACTOR_TAG="${EXTRACTOR_TAG:-v6}"           # `tag` in the extraction config
# Hand-maintained config read as the template. extract_explorer.sh never edits it:
# it writes EXTRACTOR_GEN_CONFIG with a regenerated `run:` block and selects that
# file through the EXTRACTION_CONFIG environment variable.
EXTRACTOR_BASE_CONFIG="${EXTRACTOR_BASE_CONFIG:-config_extraction_walloon.yaml}"
EXTRACTOR_GEN_CONFIG="${EXTRACTOR_GEN_CONFIG:-config_extraction_pypsa-wal.generated.yaml}"
# Per-horizon config snapshot the extractor reads out of results/<run>/configs/.
EXTRACTOR_CONFIG_FILE="${EXTRACTOR_CONFIG_FILE:-config.base_s_adm___2050.yaml}"
# `<type>` in the scenario folder name <type>__<scenario>__YYYYMMDD.
EXPLORER_TYPE="${EXPLORER_TYPE:-pypsa}"

# --- derived helpers (sourced by nic5.sh, upload_s3.sh, extract_explorer.sh) ---
# Emits one tab-separated record per Explorer scenario:
#   <scenario> <label> <results_dir> <upload_id> <scenario_id>
# A single-run config (EXPLORER_SCENARIOS empty) emits one record for RUN_NAME.
explorer_targets() {
    local spec scen label
    if [ -z "${EXPLORER_SCENARIOS:-}" ]; then
        printf '%s\t%s\t%s\t%s\t%s\n' \
            "$RUN_NAME" "$RUN_NAME" "results/${RUN_NAME}" \
            "${UPLOAD_DATE}_${RUN_NAME}" \
            "${EXPLORER_TYPE}__${RUN_NAME}__${UPLOAD_DATE}"
        return
    fi
    for spec in $EXPLORER_SCENARIOS; do
        scen="${spec%%:*}"
        label="${spec#*:}"
        printf '%s\t%s\t%s\t%s\t%s\n' \
            "$scen" "$label" \
            "results/${RUN_PREFIX:+${RUN_PREFIX}/}${scen}" \
            "${UPLOAD_DATE}_${RUN_PREFIX:+${RUN_PREFIX}_}${scen}" \
            "${EXPLORER_TYPE}__${label}__${UPLOAD_DATE}"
    done
}
