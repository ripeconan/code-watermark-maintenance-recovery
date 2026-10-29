#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 9>records/java_v8_continuation.lock
flock -n 9 || exit 3
oldpid=$(cat records/java_v8.pid)
while kill -0 "$oldpid" 2>/dev/null; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
py=/home2/icdm/conda_envs/aaai27/bin/python
"$py" -u scripts/continue_java_v8.py
"$py" -u scripts/test_java_runtime_v8.py --analyze
date -u +%FT%TZ > records/java_v8_analysis_complete.txt
