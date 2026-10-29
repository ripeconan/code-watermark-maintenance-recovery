#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 7>records/rich_v7.lock
flock -n 7 || exit 3
if [ ! -f records/functional_ready_analysis_complete.txt ]; then echo 'INITIAL_STAGE_NOT_SUMMARIZED'; exit 2; fi
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
py=/home2/icdm/conda_envs/aaai27/bin/python
"$py" -u scripts/test_rich_dependencies.py --preflight
"$py" -u scripts/test_rich_dependencies.py --freeze
"$py" -u scripts/test_rich_dependencies.py
"$py" -u scripts/test_rich_dependencies.py --analyze
date -u +%FT%TZ > records/rich_v7_analysis_complete.txt
