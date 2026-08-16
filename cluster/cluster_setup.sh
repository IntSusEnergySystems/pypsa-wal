#!/bin/bash
# SPDX-License-Identifier: MIT
###############################################################################
# cluster_setup.sh  -  One-time environment setup on NIC5 (run ON the cluster).
#
# Invoked by `cluster/nic5.sh setup`. Installs Miniforge in $HOME, creates the
# `pypsa-eur` conda environment from envs/environment.yaml (the SAME environment
# name/spec used locally and by pypsa-eur_negawatt), and wires up the Gurobi
# token-server licence so the conda gurobipy can check out a token from any
# compute node.
#
# Adapted from pypsa-eur_negawatt/cluster/cluster_setup.sh. UNTESTED for
# pypsa-wal -- verify GUROBI_MODULE_LIC below still matches the cluster before
# running this.
###############################################################################
set -euo pipefail

ENV_NAME="pypsa-eur"
MINIFORGE="$HOME/miniforge3"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
GUROBI_MODULE_LIC="/opt/cecisw/arch/easybuild/2023b/software/Gurobi/13.0.0-GCCcore-13.2.0/gurobi.lic"

echo "=== [1/4] Miniforge ==="
if [ ! -x "$MINIFORGE/bin/conda" ]; then
    tmp="$(mktemp -d)"
    curl -fsSL -o "$tmp/mf.sh" \
        "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh"
    bash "$tmp/mf.sh" -b -p "$MINIFORGE"
    rm -rf "$tmp"
else
    echo "Miniforge already present."
fi
source "$MINIFORGE/etc/profile.d/conda.sh"

echo "=== [2/4] conda environment '$ENV_NAME' ==="
# EDIT (2026-08-14): strip the local `-e ../TIMES_PyPSA` pip section before
# creating/updating the remote env — the sibling checkout does not exist on
# the cluster, and the solve chain does not import times_pypsa.
# The awk state machine deletes the marker comment and the pip block iff it
# contains exactly the expected `-e ../TIMES_PyPSA` line; any other pip
# content (a sed range would silently eat the rest of the file) aborts setup.
ENV_YAML_LOCAL="$REPO/envs/environment.yaml"
ENV_YAML_REMOTE="$(mktemp /tmp/environment.cluster.XXXXXX.yaml)"
if ! awk '
    /^[[:space:]]*#.*TIMES.*PyPSA.*soft-linking/ { next }
    inpip && /^[[:space:]]*-[[:space:]]*-e[[:space:]]+\.\.\/TIMES_PyPSA[[:space:]]*$/ { inpip = 0; sawit = 1; justclosed = 1; next }
    inpip && /^[[:space:]]*[^[:space:]]/ { bad = 1; inpip = 0 }
    justclosed && /^[[:space:]]+-[[:space:]]/ { bad = 1 }   # orphaned pip entry after the -e line
    justclosed && /^[[:space:]]*[^[:space:]#]/ { justclosed = 0 }
    /^[[:space:]]*-[[:space:]]*pip:[[:space:]]*$/ { if (inpip || sawit) bad = 1; inpip = 1; next }
    { print }
    END { exit bad ? 3 : 0 }
' "$ENV_YAML_LOCAL" > "$ENV_YAML_REMOTE"; then
    echo "ERROR: unexpected pip section in envs/environment.yaml (not the plain" >&2
    echo "       TIMES soft-link block) — update the stripping logic in this script." >&2
    rm -f "$ENV_YAML_REMOTE"
    exit 1
fi
if conda env list | grep -qE "^\s*${ENV_NAME}\s"; then
    echo "Env exists; updating from environment.yaml..."
    conda env update -n "$ENV_NAME" -f "$ENV_YAML_REMOTE" --prune
else
    conda env create -n "$ENV_NAME" -f "$ENV_YAML_REMOTE"
fi

echo "=== [3/4] Gurobi licence (token server) ==="
if [ -r "$GUROBI_MODULE_LIC" ]; then
    cp -f "$GUROBI_MODULE_LIC" "$HOME/gurobi.lic"
    echo "Copied $GUROBI_MODULE_LIC -> $HOME/gurobi.lic"
else
    echo "WARNING: module licence not readable at $GUROBI_MODULE_LIC"
    echo "         load the Gurobi module and copy its gurobi.lic to ~/gurobi.lic manually."
fi

echo "=== [4/4] sanity checks ==="
export GRB_LICENSE_FILE="$HOME/gurobi.lic"
unset PYTHONPATH || true
conda activate "$ENV_NAME"
python - <<'PY'
import importlib.metadata as m
for p in ("pypsa", "linopy", "snakemake", "gurobipy"):
    try:
        print(f"  {p:10s} {m.version(p)}")
    except Exception as e:
        print(f"  {p:10s} MISSING ({e})")
try:
    import gurobipy as gp
    env = gp.Env()           # checks out a token from the cluster's licence server
    env.dispose()
    print("  gurobi licence : OK (token checkout succeeded)")
except Exception as e:
    print(f"  gurobi licence : FAILED -> {e}")
PY
echo "=== setup done ==="
