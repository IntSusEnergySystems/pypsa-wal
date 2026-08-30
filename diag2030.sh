#!/usr/bin/env bash
set -o pipefail
source /home/sylvain/progs/miniconda/etc/profile.d/conda.sh
conda activate pypsa-eur
cd /home/sylvain/svn/pypsa-wal
export GRB_LICENSE_FILE=/home/sylvain/.gurobi/gurobi.lic
export TMPDIR=/home/sylvain/svn/pypsa-wal/tmp MPLBACKEND=Agg
echo "DIAG_START $(date -Is)"
snakemake --configfile config/config.walloon.yaml /tmp/claude-1000/-home-sylvain-svn-pypsa-wal/c5d75d0f-e2f1-46ff-8953-63f67c332b3d/scratchpad/nogrowth.yaml \
          --cores 14 --resources mem_mb=100000 --rerun-triggers mtime \
          -- results/walloon/scen_demande_haute/networks/base_s_adm___2030.nc
echo "DIAG_EXIT=$? $(date -Is)"
echo "DIAG_DONE"
