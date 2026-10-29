#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 8>records/functional_controller.lock
flock -n 8 || exit 3
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
py=/home2/icdm/conda_envs/aaai27/bin/python
"$py" -u scripts/freeze_functional.py --version v4 --allow-partial
"$py" -u scripts/test_temporal.py --version v4 --ready-only
"$py" -u scripts/analyze_functional_temporal.py --version v4 --ready-only
date -u +%FT%TZ > records/functional_ready_analysis_complete.txt
