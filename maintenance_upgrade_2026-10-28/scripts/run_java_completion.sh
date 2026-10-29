set -eu
cd /home/icdm/crosslingual-codewatermark/maintenance_upgrade_20261028
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/home2/icdm/crosslingual-codewatermark/revision_20261019/.venv/bin/python
"$PY" -u scripts/run_java_batches.py
"$PY" -u scripts/analyze_functional.py
