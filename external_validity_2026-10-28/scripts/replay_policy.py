"""Frozen paired replay sensitivity on the 432 existing functional attempts."""
import argparse,collections,concurrent.futures,datetime,gzip,hashlib,json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'robustness_revision_20261029'
METHODS=('official','syntax','structured64','nearest64','dictionary64','dictionary_pairs64')
STAGES={'pallets/flask':'v4_ready','apache/commons-csv':'v4_ready','Textualize/rich':'rich_v7','sphinx-doc/sphinx':'sphinx_v5','checkstyle/checkstyle':'java_v8','javaparser/javaparser':'java_v8'}
ARGV=['git','-c','merge.conflictStyle=merge','merge-file','-p','--','marked.txt','base.txt','revised.txt']
def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(p.read_bytes())
def rows(p):return [json.loads(s) for s in p.read_text().splitlines() if s]
def write(name,x):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False))
def git_env():return {**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','LC_ALL':'C','LANG':'C'}
def provenance():
    names=['scripts/replay_policy.py','scripts/fine_replay.py','scripts/evaluate_upgrade.py','scripts/replay_pilot.py','scripts/structured_candidates.py','scripts/test_temporal.py','scripts/run_project_tests.py','scripts/test_java_runtime_v8.py','scripts/test_rich_dependencies.py','scripts/test_sphinx_addon.py','records/development_dictionary.json','records/scoring_freeze.json','records/functional_recipe_freeze.json','records/java_v8_freeze.json','records/rich_v7_freeze.json','records/sphinx_recipe_freeze.json','results/temporal_scores.jsonl','results/temporal_summary.json','results/functional_decisions_final.jsonl','results/functional_summary_final.json']
    names += ['results/functional_'+stage+'.jsonl' for stage in sorted(set(STAGES.values()))]
    paths=[ROOT/n for n in names]
    paths+=list((ROOT/'records').glob('environments_*/*.freeze.txt'))
    paths+=list((ROOT/'records').glob('environments_*/*.json'))
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}
def originals():
    jobs=[r for stage in sorted(set(STAGES.values())) for r in rows(ROOT/'results'/('functional_'+stage+'.jsonl')) if STAGES.get(r['repo'])==stage]
    bylink={}
    for j in jobs:
        for l in j['links']:bylink[l['id'],l['key'],l['group']]=j
    return jobs,bylink
def make_plan():
    from fine_replay import merge
    assert json.loads((OUT/'p0_gate.json').read_text())['proceed_p2']
    freeze=OUT/'p2_policy_freeze.json';assert not freeze.exists(),'frozen policy already exists'
    policy=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),label='post-outcome locally frozen robustness study',git_version=subprocess.check_output(['git','--version'],text=True).strip(),argv=ARGV,environment={'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','LC_ALL':'C','LANG':'C'},files=provenance(),workers=2,score_timeout=240,test_timeout=600,manual_resolution=False,score_based_test_selection=False,denominator=432,subgroup_rule='embedding ok and positive_before score reached, both canonical and line policies clean; no parse/score/test outcome filter',reuse_rule='same bytes, revision, path, key and frozen detector/test recipe; retain failed cached outcomes')
    write(freeze.name,policy)
    old={(r['id'],r['key']):r for r in rows(ROOT/'results/temporal_scores.jsonl')}
    functional=rows(ROOT/'results/functional_decisions_final.jsonl');jobs,bylink=originals()
    plan=[];saved=completed=abstain=0
    for f in functional:
        r=old[f['id'],f['key']];codes=json.loads(gzip.decompress((ROOT/r['codes_file']).read_bytes()))
        assert all(digest(v.encode())==r['code_sha256'][g] for g,v in codes.items())
        assert all(g in codes for g in ('negative_before','positive_before','negative_after'))
        canonical,detail=merge(codes['negative_before'],codes['positive_before'],codes['negative_after'])
        reached=r.get('stage_status',{}).get('replay')=='completed'
        if reached:
            completed+=1;assert r['merge_status']==('clean' if canonical is not None else 'conflict')
            assert r['replay_detail']==json.loads(json.dumps(detail))
        if 'positive_after' in codes:
            saved+=1;assert canonical==codes['positive_after']
        assert reached or (r['id']=='af895169cc63a302842cad44' and r['key']==49979687)
        emb=r.get('embedding',{}).get('status')=='ok'
        if not emb:
            abstain+=1;assert r['embedding']['status']=='abstain:not_converged' and codes['positive_before']==codes['negative_before']
        p=dict(id=r['id'],key=r['key'],repo=r['repo'],filename=r['filename'],commit=r['sha'],language=r['language'],embedding_ok=emb,canonical_merge=r.get('merge_status','not_reached'),canonical_functional=f,canonical_record_sha256=digest(json.dumps(r,sort_keys=True).encode()),input_hashes=r['code_sha256'],canonical_stage=STAGES[r['repo']])
        p['prerequisites_passed']=all(bylink.get((r['id'],r['key'],g),{}).get('pass_tests',False) for g in ('negative_before','negative_after','positive_before'))
        if not emb or not reached:
            p.update(line_status='embedding_abstention' if not emb else 'prerequisite_error',score_action='not_reached',test_action='not_reached',both_clean=False);plan.append(p);continue
        with tempfile.TemporaryDirectory(prefix='line-replay-',dir=ROOT/'work') as td:
            d=Path(td)
            for name,g in [('marked.txt','positive_before'),('base.txt','negative_before'),('revised.txt','negative_after')]: (d/name).write_bytes(codes[g].encode())
            result=subprocess.run(ARGV,cwd=d,env=git_env(),capture_output=True,timeout=60)
        if result.returncode<0 or result.returncode>127:raise RuntimeError(result.stderr.decode(errors='replace'))
        p.update(line_returncode=result.returncode,line_status='clean' if result.returncode==0 else 'conflict',both_clean=result.returncode==0 and r['merge_status']=='clean')
        if result.returncode:
            p.update(score_action='not_reached',test_action='not_reached');plan.append(p);continue
        code=result.stdout.decode('utf-8');h=digest(result.stdout);p['child_sha256']=h
        dest=OUT/'p2_codes'/f"{r['id']}_{r['key']}.txt.gz";dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(result.stdout,mtime=0));p['child_path']=str(dest.relative_to(ROOT))
        p['same_as_canonical']=h==r['code_sha256'].get('positive_after')
        p['score_action']='reuse' if p['same_as_canonical'] else 'execute'
        cached=bylink.get((r['id'],r['key'],'positive_after'))
        if cached and cached['code_sha256']==h and cached['commit']==r['sha'] and cached['filename']==r['filename']:
            p.update(test_action='reuse',cached_test_job_id=cached['job_id'],cached_test_sha256=digest(json.dumps(cached,sort_keys=True).encode()),cached_test_passed=bool(cached['pass_tests']),cached_test_status=cached['status'])
        else:p['test_action']='execute'
        plan.append(p)
    assert len(plan)==432 and saved==338 and completed==431 and abstain==33
    write('p2_plan.json',plan)
    write('p2_plan_audit.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),attempts=len(plan),canonical_children_matched=saved,canonical_replay_statuses_matched=completed,embedding_abstentions=abstain,pre_replay_error=1,original_pair_subgroup=sum(p['canonical_functional']['original_pair_passed'] for p in plan),both_clean_subgroup=sum(p['both_clean'] for p in plan),line_status=dict(collections.Counter(p['line_status'] for p in plan)),score_actions=dict(collections.Counter(p['score_action'] for p in plan)),test_actions=dict(collections.Counter(p['test_action'] for p in plan)),plan_sha256=sha(OUT/'p2_plan.json')))
    print((OUT/'p2_plan_audit.json').read_text(),flush=True)

def worker(kind,plan):
    code=gzip.decompress((ROOT/plan['child_path']).read_bytes()).decode();assert digest(code.encode())==plan['child_sha256']
    if kind=='score':
        from evaluate_upgrade import init,score
        init();dictionary=json.loads((ROOT/'records/development_dictionary.json').read_text())
        key=hashlib.sha256(('confirmation20261028|'+str(plan['key'])).encode()).digest()
        return dict(status='completed',score=score(code,plan['language'],key,dictionary.get(plan['language'],[])))
    import test_temporal as base
    stage=plan['canonical_stage'];base.VERSION='v4' if stage=='v4_ready' else stage;base.PHASE='replay_policy'
    if stage=='java_v8':
        from test_java_runtime_v8 import corrected_prepare
        base.prepare=corrected_prepare
    elif stage=='rich_v7':
        from test_rich_dependencies import prepare
        base.prepare=prepare
    elif stage=='sphinx_v5':
        from test_sphinx_addon import overlay_sandbox
        base.sandbox=overlay_sandbox
    # All original environment records already exist. No preparation/network fallback.
    identity=plan['repo'].replace('/','__')+'__'+plan['commit']
    folder='environments_rich_v7' if stage=='rich_v7' else 'environments_v4'
    assert (ROOT/'records'/folder/(identity+'.json')).exists(),'missing frozen environment'
    job=dict(job_id='rp_'+digest(json.dumps([plan['id'],plan['key'],plan['child_sha256']]).encode())[:24],repo=plan['repo'],language=plan['language'],commit=plan['commit'],filename=plan['filename'],code=code,code_sha256=plan['child_sha256'],original=False,links=[dict(id=plan['id'],key=plan['key'],group='positive_after')])
    return base.execute(job)

def isolated(kind,p):
    started=time.time();dest=OUT/'p2_worker_results'/f"{kind}_{p['id']}_{p['key']}.json";dest.parent.mkdir(exist_ok=True)
    try:
        result=subprocess.run([sys.executable,__file__,'--worker',kind,'--save',str(dest)],input=json.dumps(p),capture_output=True,text=True,timeout=240 if kind=='score' else 660)
        if result.returncode:raise RuntimeError(f'exit {result.returncode}: '+result.stderr[-2500:])
        r=json.loads(dest.read_text())
    except Exception as e:r=dict(status='process_error',pass_tests=False,error=type(e).__name__+': '+str(e))
    return dict(id=p['id'],key=p['key'],repo=p['repo'],kind=kind,seconds=time.time()-started,result=r)

def run():
    freeze=json.loads((OUT/'p2_policy_freeze.json').read_text());assert freeze['files']==provenance(),'source/recipe drift'
    assert freeze['git_version']==subprocess.check_output(['git','--version'],text=True).strip()
    audit=json.loads((OUT/'p2_plan_audit.json').read_text());assert audit['plan_sha256']==sha(OUT/'p2_plan.json')
    plan=json.loads((OUT/'p2_plan.json').read_text());dest=OUT/'p2_new_results.jsonl'
    done={(r['id'],r['key'],r['kind']) for r in rows(dest)} if dest.exists() else set()
    pending=[(kind,p) for p in plan for kind in ('score','test') if p[kind+'_action']=='execute' and (p['id'],p['key'],kind) not in done]
    with dest.open('a') as f,concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(isolated,kind,p) for kind,p in pending]
        for future in concurrent.futures.as_completed(futures):
            r=future.result();f.write(json.dumps(r)+'\n');f.flush();print('REPLAY_RESULT',r['repo'],r['kind'],r['result']['status'],round(r['seconds'],1),flush=True)
    write('p2_run_complete.json',dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),new_tasks=len(pending),all_records=len(rows(dest))))
    print('P2_EXECUTION_COMPLETE',flush=True)

def analyze():
    from analyze_upgrade import value
    assert (OUT/'p2_run_complete.json').exists()
    plan=json.loads((OUT/'p2_plan.json').read_text());new={(r['id'],r['key'],r['kind']):r['result'] for r in rows(OUT/'p2_new_results.jsonl')}
    expected={(p['id'],p['key'],kind) for p in plan for kind in ('score','test') if p[kind+'_action']=='execute'};assert new.keys()==expected
    old={(r['id'],r['key']):r for r in rows(ROOT/'results/temporal_scores.jsonl')}
    th={(r['repo'],r['key'],r['method']):float(r['threshold']) for r in json.loads((ROOT/'results/temporal_summary.json').read_text())['thresholds'] if r['mode']=='earlier_paired' and r['alpha']==.05 and r['method'] in METHODS}
    details=[]
    for p in plan:
        r=old[p['id'],p['key']];score={};test=False;teststatus=p['line_status'];scorestatus=p['line_status']
        if p['score_action']=='reuse':score=r.get('group_scores',{}).get('positive_after',{});scorestatus=r.get('stage_status',{}).get('positive_after','missing')
        elif p['score_action']=='execute':s=new[p['id'],p['key'],'score'];score=s.get('score',{});scorestatus=s['status']
        if p['test_action']=='reuse':test=p['cached_test_passed'];teststatus=p['cached_test_status']
        elif p['test_action']=='execute':t=new[p['id'],p['key'],'test'];test=t.get('pass_tests',False);teststatus=t['status']
        detection={m:p['embedding_ok'] and value({'group_scores':{'positive_after':score}},'positive_after',m)>th[p['repo'],p['key'],m] for m in METHODS}
        allfour=bool(p['prerequisites_passed'] and test)
        details.append(dict(id=p['id'],key=p['key'],repo=p['repo'],original_pair_passed=p['canonical_functional']['original_pair_passed'],both_clean=p['both_clean'],line_status=p['line_status'],score_status=scorestatus,test_status=teststatus,canonical_all_four=p['canonical_functional']['all_four_passed'],line_all_four=allfour,canonical_joint=p['canonical_functional']['joint_detection_and_tests'],line_joint={m:allfour and detection[m] for m in METHODS},line_detection=detection,same_as_canonical=p.get('same_as_canonical',False)))
    write('p2_decisions.json',details)
    sums=[]
    for subgroup in ('all','original_pair','both_clean'):
        for repo in [None]+sorted(STAGES):
            rr=[r for r in details if (repo is None or r['repo']==repo) and {'all':True,'original_pair':r['original_pair_passed'],'both_clean':r['both_clean']}[subgroup]]
            sums.append(dict(subgroup=subgroup,repo=repo,n=len(rr),line_status=dict(collections.Counter(r['line_status'] for r in rr)),test_status=dict(collections.Counter(r['test_status'] for r in rr)),canonical_all_four=sum(r['canonical_all_four'] for r in rr),line_all_four=sum(r['line_all_four'] for r in rr),canonical_joint={m:sum(r['canonical_joint'][m] for r in rr) for m in METHODS},line_joint={m:sum(r['line_joint'][m] for r in rr) for m in METHODS},paired_changes={m:dict(gained=sum(r['line_joint'][m] and not r['canonical_joint'][m] for r in rr),lost=sum(r['canonical_joint'][m] and not r['line_joint'][m] for r in rr)) for m in METHODS}))
    write('p2_summary.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),plan_audit=json.loads((OUT/'p2_plan_audit.json').read_text()),summary=sums,new_job_status=dict(collections.Counter((r['kind']+':'+r['result']['status']) for r in rows(OUT/'p2_new_results.jsonl'))),interpretation='Paired retrospective replay-policy sensitivity; documented joint success yield over all 432 attempts; original-pair and both-clean subsets descriptive, nonrandom; no repair or native Git bug claim. All-four counts include the canonical original archived attempts, while the line policy preserves embedding abstentions as not reached; use embedding-gated joint success for policy comparison.'))
    print(json.dumps([r for r in sums if r['repo'] is None],indent=2),flush=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',action='store_true');ap.add_argument('--run',action='store_true');ap.add_argument('--analyze',action='store_true');ap.add_argument('--worker',choices=['score','test']);ap.add_argument('--save');a=ap.parse_args()
    if a.worker:
        result=worker(a.worker,json.load(sys.stdin));Path(a.save).write_text(json.dumps(result));return
    if a.plan:make_plan()
    if a.run:run()
    if a.analyze:analyze()
if __name__=='__main__':main()
