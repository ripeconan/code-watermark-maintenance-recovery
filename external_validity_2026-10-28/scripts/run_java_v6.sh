#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 6>records/java_v6.lock
flock -n 6 || exit 3
oldpid=$(cat records/functional_ready.pid)
while kill -0 "$oldpid" 2>/dev/null; do sleep 20; done
if [ ! -f records/functional_ready_analysis_complete.txt ]; then echo 'INITIAL_STAGE_NOT_SUMMARIZED'; exit 2; fi
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
py=/home2/icdm/conda_envs/aaai27/bin/python
"$py" -u scripts/test_java_provider_fix.py --preflight
"$py" -u scripts/test_java_provider_fix.py --freeze
"$py" -u scripts/test_java_provider_fix.py
"$py" -u scripts/test_java_provider_fix.py --analyze
date -u +%FT%TZ > records/java_v6_analysis_complete.txt
