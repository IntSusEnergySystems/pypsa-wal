#!/usr/bin/env bash
set -o pipefail
source /home/sylvain/progs/miniconda/etc/profile.d/conda.sh
conda activate pypsa-eur
cd /home/sylvain/svn/pypsa-wal
export GRB_LICENSE_FILE=/home/sylvain/.gurobi/gurobi.lic
export TMPDIR=/home/sylvain/svn/pypsa-wal/tmp
export MPLBACKEND=Agg
echo "TEST_START $(date -Is)"
snakemake --configfile config/config.walloon.yaml --cores 14 --resources mem_mb=100000 \
          --rerun-triggers mtime -- results/walloon/scen_demande_haute/networks/base_s_adm___2025.nc
echo "TEST_EXIT=$? $(date -Is)"
echo "TEST_DONE"
