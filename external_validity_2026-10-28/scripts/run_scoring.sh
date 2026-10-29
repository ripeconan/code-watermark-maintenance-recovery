#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 9>records/scoring.lock
flock -n 9 || exit 3
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export PYTHONPATH=/home2/icdm/crosslingual-codewatermark/publication_revision_20261028/tools/parser_stable
py=/home2/icdm/crosslingual-codewatermark/revision_20261019/.venv/bin/python
while [ ! -f records/acquisition_summary.json ]; do
  pid=$(cat records/acquisition.pid)
  if ! kill -0 "$pid" 2>/dev/null; then echo 'ACQUISITION_STOPPED_WITHOUT_SUMMARY'; exit 1; fi
  sleep 20
done
"$py" scripts/freeze_scoring.py
"$py" -u scripts/evaluate_temporal.py
"$py" -u scripts/analyze_temporal.py
date -u +%FT%TZ > records/scoring_complete.txt
