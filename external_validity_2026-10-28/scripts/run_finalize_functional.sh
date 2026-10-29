#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 5>records/functional_finalize.lock
flock -n 5 || exit 3
oldpid=$(cat records/java_v8_continuation.pid)
while kill -0 "$oldpid" 2>/dev/null; do sleep 10; done
test -f records/java_v8_analysis_complete.txt
py=/home2/icdm/conda_envs/aaai27/bin/python
"$py" -u scripts/summarize_functional_final.py
"$py" -u scripts/verify_functional_final.py
date -u +%FT%TZ > records/functional_final_verified.txt
