"""Outcome-independent finite history frame and chronological sample."""
import collections, datetime, gzip, hashlib, json, os, re, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = [
    ('python', 'pallets/flask', 'src/flask/'),
    ('python', 'Textualize/rich', 'rich/'),
    ('python', 'sphinx-doc/sphinx', 'sphinx/'),
    ('java', 'apache/commons-csv', 'src/main/java/'),
    ('java', 'javaparser/javaparser', 'javaparser-core/src/main/java/'),
    ('java', 'checkstyle/checkstyle', 'src/main/java/'),
]

def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()

def git(path, *args, timeout=120):
    p = subprocess.run(['git', '-c', 'core.quotepath=false', '--git-dir', str(path), *args], capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(p.stderr.decode('utf8', 'replace')[-1500:])
    return p.stdout

def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, ensure_ascii=True, indent=2).encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)

def acquire(language, name, source_root):
    slug = name.replace('/', '__')
    manifest = ROOT/'records'/f'acquire_{slug}.json'
    if manifest.exists() and json.loads(manifest.read_text()).get('complete'):
        return json.loads(manifest.read_text())
    repo = ROOT/'data/repos'/slug
    repo.parent.mkdir(parents=True, exist_ok=True)
    if not (repo/'HEAD').exists():
        print('CLONE', name, flush=True)
        p = subprocess.run(['git', 'clone', '--bare', '--depth', '2400', '--single-branch', f'https://github.com/{name}.git', str(repo)], capture_output=True, timeout=1200, env={**os.environ, 'GIT_TERMINAL_PROMPT':'0'})
        if p.returncode:
            raise RuntimeError(p.stderr.decode('utf8', 'replace')[-2000:])
    pinfile = ROOT/'records'/f'pin_{slug}.json'
    if pinfile.exists():
        pin = json.loads(pinfile.read_text())['pin']
    else:
        pin = git(repo, 'rev-list', '-1', '--before=2026-10-27T23:59:59Z', 'HEAD').decode().strip()
        if not pin:
            raise ValueError('no commit before cutoff')
        dump(pinfile, dict(repo=name, pin=pin, cutoff='2026-10-27T23:59:59Z', retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    entries = git(repo, 'ls-tree', pin).decode().splitlines()
    licenses = []
    for entry in entries:
        meta, path = entry.split('\t', 1)
        if meta.split()[1] == 'blob' and path.lower().startswith(('license', 'copying')):
            raw = git(repo, 'show', f'{pin}:{path}')
            target = ROOT/'data/licenses'/f'{slug}__{path}'
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
            licenses.append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), local=str(target.relative_to(ROOT))))
    if not licenses:
        raise ValueError('root license requires manual inspection')
    # Build/test metadata is retained without executing upstream code.
    for path in ('pyproject.toml', 'pom.xml', 'tox.ini', 'requirements.txt', 'README.rst', 'README.md'):
        try:
            raw = git(repo, 'show', f'{pin}:{path}')
            target = ROOT/'data/metadata'/slug/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        except RuntimeError:
            pass
    lines = git(repo, 'log', '--no-merges', '--max-count=1200', '--format=%H %P %ct', pin).decode().splitlines()
    census, rows = [], []
    counts = collections.Counter()
    for index, line in enumerate(lines):
        parts = line.split(); sha = parts[0]
        if len(parts) != 3:
            counts['missing_single_parent'] += 1; census.append(dict(sha=sha, status='missing_single_parent')); continue
        _, parent, timestamp = parts
        try:
            changes = git(repo, 'diff-tree', '--no-commit-id', '--name-status', '-r', '--no-renames', parent, sha).decode().splitlines()
        except RuntimeError as e:
            counts['history_unavailable'] += 1; census.append(dict(sha=sha, status='history_unavailable', error=str(e))); continue
        extension = '.py' if language == 'python' else '.java'
        paths = [s.split('\t',1)[1] for s in changes if s.startswith('M\t') and s.split('\t',1)[1].startswith(source_root) and s.endswith(extension)]
        paths.sort(key=lambda p: digest('external-file-v1|'+sha+'|'+p))
        chosen = None; rejections = []
        for path in paths:
            try:
                b, a = [git(repo, 'show', f'{commit}:{path}') for commit in (parent, sha)]
                reason = 'empty' if not b or not a else 'oversize' if max(len(b), len(a)) > 80000 else 'nul' if b'\0' in b or b'\0' in a else 'same_contents' if b == a else None
                if reason:
                    raise ValueError(reason)
                before, after = b.decode('utf8'), a.decode('utf8')
                if any(re.search(r'@generated|automatically generated|generated by', x[:4096], re.I) for x in (before, after)):
                    raise ValueError('generated_notice')
            except (ValueError, UnicodeError, RuntimeError) as e:
                rejections.append(dict(path=path, reason=str(e)[:300])); continue
            chosen = dict(id=digest(name+'|'+sha+'|'+path)[:24], repo=name, language=language, sha=sha, parent_sha=parent, timestamp=int(timestamp), date=datetime.datetime.fromtimestamp(int(timestamp), datetime.timezone.utc).isoformat(), filename=path, before=before, after=after, before_sha256=hashlib.sha256(b).hexdigest(), after_sha256=hashlib.sha256(a).hexdigest())
            rows.append(chosen); break
        status = 'selected_pre_dedup' if chosen else 'no_eligible_production_change'
        counts[status] += 1
        census.append(dict(sha=sha, parent=parent, timestamp=int(timestamp), status=status, production_paths=len(paths), selected_path=chosen['filename'] if chosen else None, rejections=rejections))
        if index % 100 == 0:
            print('FRAME', name, index, len(rows), flush=True)
    rows.sort(key=lambda r:(r['timestamp'],r['sha']))
    frame, seen, duplicates = [], set(), []
    for row in rows:
        identity = (row['before_sha256'], row['after_sha256'])
        if identity in seen:
            duplicates.append(row['id']); continue
        seen.add(identity); frame.append(row)
    if len(frame) < 2:
        raise ValueError('fewer than two eligible commits')
    boundary = frame[(len(frame)-1)//2]['timestamp']
    selected, period_counts = [], {}
    for split, predicate in [('calibration', lambda r:r['timestamp'] <= boundary), ('test', lambda r:r['timestamp'] > boundary)]:
        candidates = [r for r in frame if predicate(r)]
        period_counts[split] = len(candidates)
        candidates.sort(key=lambda r:digest('external-sample-v1|'+split+'|'+r['id']))
        selected.extend({**r, 'split':split} for r in candidates[:120])
    cal = [r for r in selected if r['split']=='calibration']; test = [r for r in selected if r['split']=='test']
    assert not cal or not test or max(r['timestamp'] for r in cal) < min(r['timestamp'] for r in test)
    functional = sorted(test, key=lambda r:digest('external-functional-v1|'+r['id']))[:24]
    metadata = lambda rs:[{k:v for k,v in r.items() if k not in ('before','after')} for r in rs]
    dump(ROOT/'data/pairs'/f'{slug}.frame.json.gz', frame)
    dump(ROOT/'data/pairs'/f'{slug}.json.gz', selected)
    dump(ROOT/'records'/f'functional_{slug}.json', metadata(functional))
    dump(ROOT/'records'/f'selection_{slug}.json', metadata(selected))
    dump(ROOT/'records'/f'census_{slug}.json.gz', census)
    cal_hashes = {r[g] for r in cal for g in ('before_sha256','after_sha256')}
    test_hashes = {r[g] for r in test for g in ('before_sha256','after_sha256')}
    result = dict(complete=True, repo=name, language=language, source_root=source_root, pin=pin, licenses=licenses, commits_inspected=len(lines), census_counts=dict(counts), frame_size=len(frame), duplicate_pair_ids=duplicates, boundary=boundary, period_counts=period_counts, selected={s:sum(r['split']==s for r in selected) for s in ('calibration','test')}, unique_paths={s:len({r['filename'] for r in selected if r['split']==s}) for s in ('calibration','test')}, exact_snapshot_overlap=len(cal_hashes & test_hashes), functional_transitions=len(functional), functional_paths=len({r['filename'] for r in functional}), dates={s:[min((r['date'] for r in selected if r['split']==s),default=None), max((r['date'] for r in selected if r['split']==s),default=None)] for s in ('calibration','test')}, limited_feasibility=min(period_counts.values())<40)
    dump(manifest,result)
    print('ACQUIRED', json.dumps(result), flush=True)
    return result

def main():
    results = []
    for project in PROJECTS:
        try:
            results.append(acquire(*project))
        except Exception as e:
            record = dict(repo=project[1], complete=False, error=type(e).__name__+': '+str(e))
            dump(ROOT/'records'/f"acquire_error_{project[1].replace('/','__')}.json", record)
            results.append(record); print('ACQUIRE_ERROR',json.dumps(record),flush=True)
    dump(ROOT/'records/acquisition_summary.json', results)
    if not all(r.get('complete') for r in results):
        raise SystemExit(1)

if __name__=='__main__':
    main()
