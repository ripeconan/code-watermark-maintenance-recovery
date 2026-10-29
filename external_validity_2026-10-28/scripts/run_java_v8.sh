#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 8>records/java_v8.lock
flock -n 8 || exit 3
oldpid=$(cat records/rich_v7.pid)
while kill -0 "$oldpid" 2>/dev/null; do sleep 20; done
if [ ! -f records/rich_v7_analysis_complete.txt ]; then echo 'RICH_STAGE_NOT_SUMMARIZED'; exit 2; fi
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
py=/home2/icdm/conda_envs/aaai27/bin/python
"$py" -u scripts/prepare_java_runtime_v8.py
"$py" -u scripts/test_java_runtime_v8.py --preflight
"$py" -u scripts/test_java_runtime_v8.py --freeze
"$py" -u scripts/test_java_runtime_v8.py
"$py" -u scripts/test_java_runtime_v8.py --analyze
date -u +%FT%TZ > records/java_v8_analysis_complete.txt
