#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 8>records/functional_controller.lock
flock -n 8 || exit 3
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
py=/home2/icdm/conda_envs/aaai27/bin/python
oldpid=$(cat records/functional_preflight_v2.pid)
while kill -0 "$oldpid" 2>/dev/null; do sleep 20; done
"$py" -u scripts/test_temporal.py --preflight --version v3
"$py" -u scripts/freeze_functional.py
"$py" -u scripts/test_temporal.py --version v3
"$py" -u scripts/analyze_functional_temporal.py --version v3
date -u +%FT%TZ > records/functional_analysis_complete.txt
