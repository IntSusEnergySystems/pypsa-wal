#!/usr/bin/env bash
# Driver for the 2026-08-29 scen_demande_haute 1h/2013 local run.
set -o pipefail
source /home/sylvain/progs/miniconda/etc/profile.d/conda.sh
conda activate pypsa-eur
cd /home/sylvain/svn/pypsa-wal
export GRB_LICENSE_FILE=/home/sylvain/.gurobi/gurobi.lic
export TMPDIR=/home/sylvain/svn/pypsa-wal/tmp
# Headless: matplotlib otherwise auto-selects QtAgg (DISPLAY is set) and the Qt
# platform plugins fail to load, killing plot_base_network with SIGABRT.
export MPLBACKEND=Agg

echo "PHASE_START $(date -Is)"
snakemake --configfile config/config.walloon.yaml \
          --cores 20 --resources mem_mb=100000 \
          --rerun-triggers mtime \
          -call
rc=$?
echo "SNAKEMAKE_EXIT=$rc $(date -Is)"
echo "ALL_PHASES_DONE"
exit $rc
