set -eu
cd /home/icdm/crosslingual-codewatermark/maintenance_upgrade_20261028
PY=/home2/icdm/crosslingual-codewatermark/revision_20261019/.venv/bin/python
"$PY" -u scripts/prefetch_maven.py
"$PY" - <<'PY'
import json,pathlib
root=pathlib.Path.cwd()
for p in (root/'tools/warmups_v2').glob('*.json'):
 if json.loads(p.read_text()).get('returncode')!=0:p.rename(root/'records'/('initial_warmup_'+p.name))
PY
"$PY" -u scripts/test_project_local.py --language java --run-id javatransport --limit 4
