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
# Sector-coupled PyPSA solves at fine temporal resolution (e.g. 1h) need large
# RAM for Gurobi model generation. Use the `hmem` partition on NIC5 (~1 TB per
# node). Memory for solve jobs is set in cluster/config_cluster.yaml
# (`solving.mem_mb`); keep it aligned with the hmem node limit (~1 000 000 MB).
# Light rules (add_brownfield) share the same partition but use DEFAULT_MEM_MB.
# CECI job-efficiency guidance: https://support.ceci-hpc.be/doc/SubmittingJobs/JobEfficiency/
# The 2026-09-02 item-2 6h solves used `batch` (100 GB, 480 min); restore hmem
# for 1h production runs.
SOLVE_PARTITION="${SOLVE_PARTITION:-hmem}"
# 1440 min for the 1h-resolution solve (360/480 was sized for 6h).
SOLVE_RUNTIME="${SOLVE_RUNTIME:-1440}"     # minutes
DEFAULT_PARTITION="${DEFAULT_PARTITION:-hmem}"
DEFAULT_MEM_MB="${DEFAULT_MEM_MB:-16000}"      # light rules (add_brownfield)
DEFAULT_RUNTIME="${DEFAULT_RUNTIME:-120}"
DEFAULT_CPUS="${DEFAULT_CPUS:-1}"              # light rules only; never set globally for solve
MAX_SLURM_JOBS="${MAX_SLURM_JOBS:-2}"

# --- run / scenario ------------------------------------------------------------
# config/config.walloon.yaml is the only study config: it always runs in
# scenario mode (run.prefix + run.scenarios), so RDIR is "walloon/{run}/" whether
# run.name lists one scenario or several. Scenario overrides come from
# config/scenarios.walloon.yaml. There is still no <scenario>/<resolution> CLI
# argument anywhere in this tooling (unlike pypsa-eur_negawatt) — switch runs by
# exporting the variables below, e.g.
#   RUN_NAME=scen_base ./cluster/nic5.sh <command>
CONFIGFILE="${CONFIGFILE:-config/config.walloon.yaml}"
RUN_NAME="${RUN_NAME:-scen_demande_haute}"
HORIZONS="${HORIZONS:-2025 2030 2040 2050}"
CLUSTERS="${CLUSTERS:-adm}"
OPTS="${OPTS:-}"
SECTOR_OPTS="${SECTOR_OPTS:-}"

# --- multi-scenario runs (run.prefix + run.scenarios) --------------------------
# RUN_PREFIX must match run.prefix in CONFIGFILE, so results live in
# results/<prefix>/<scenario>/. The three defaults use `${VAR-default}` (NOT
# `${VAR:-default}`) so an exported EMPTY value clears them; clearing RUN_PREFIX
# falls back to results/<RUN_NAME>/, i.e. a config with no run.prefix.
#
# EDIT (2026-08-14): active run = scen_demande_haute @ 2010, 1h.
RUN_PREFIX="${RUN_PREFIX-walloon}"           # = run.prefix; empty = no prefix
# Scenario -> Explorer display label, space-separated "<scenario>:<label>" pairs.
# The label is what the Explorer dropdown shows and is an editorial choice (the
# existing scenarios use French names), so set it deliberately -- it is NOT
# derived from the scenario name. Omit ":<label>" to reuse the scenario name.
EXPLORER_SCENARIOS="${EXPLORER_SCENARIOS-scen_demande_haute:demande-haute-2010-1h}"
# `<type>` in the scenario folder name <type>__<scenario>__YYYYMMDD (used by
# upload_s3.sh and extract_explorer.sh). An explicitly cleared value means
# `pypsa` (the single-run Walloon type).
EXPLORER_TYPE="${EXPLORER_TYPE-times-pypsa}"
: "${EXPLORER_TYPE:=pypsa}"
#
# One-off examples (export ahead of the command):
#   Both TIMES scenarios with French display labels:
#     EXPLORER_SCENARIOS="scen_base:demande-haute scen_corrige:demande-réduite" ./cluster/nic5.sh publish
#   Higher solve runtime for a heavier LP:
#     SOLVE_RUNTIME=2880 ./cluster/nic5.sh solve

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
# HTML report → https://pypsa.squoilin.eu/intervec/<scenario>_<YYYYMMDD>/
# (rules/publish_html.smk, passwordless SSH as negawatt with rsa_nopasswd).
HTML_PUBLISH="${HTML_PUBLISH:-1}"               # 0 = do not ask postprocess for the publish sentinel
PYPSA2HTML="${PYPSA2HTML:-1}"                   # 0 = do not ask postprocess for html/pypsa/index.html
UPLOAD_SKIP_NETWORKS="${UPLOAD_SKIP_NETWORKS:-0}"  # 1 = omit large .nc files
# Optional overrides (defaults: YYYYMMDD_<RUN_NAME> and <RUN_NAME>__YYYYMMDD):
# UPLOAD_ID=20260717_scen_demande_haute
# SCENARIO_ID=times-pypsa__scen_demande_haute__20260717
# EXPLORER_SRC=results/walloon/scen_demande_haute/explorer/pypsa
# Shared by upload_s3.sh and extract_explorer.sh so a single `publish` stamps one
# date on the raw folder, the scenario folder and the extractor run_nickname.
UPLOAD_DATE="${UPLOAD_DATE:-$(date +%Y%m%d)}"
# Same stamp as S3 unless already set. Empty still means "today" inside the rule.
HTML_PUBLISH_DATE="${HTML_PUBLISH_DATE:-$UPLOAD_DATE}"

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
# `<type>` in the scenario folder name <type>__<scenario>__YYYYMMDD:
# defined once with the active-run defaults in the multi-scenario section above.

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
