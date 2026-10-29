#!/usr/bin/env bash
set -euo pipefail
cd /home/icdm/crosslingual-codewatermark/external_validity_20261028
exec 7>records/sphinx_v5.lock
flock -n 7 || exit 3
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
py=/home2/icdm/conda_envs/aaai27/bin/python
"$py" -u scripts/test_sphinx_addon.py --preflight
"$py" -u scripts/test_sphinx_addon.py --freeze
"$py" -u scripts/test_sphinx_addon.py
"$py" -u scripts/test_sphinx_addon.py --analyze
date -u +%FT%TZ > records/sphinx_v5_analysis_complete.txt
