"""Build traceable manuscript assets from completed robustness analyses."""
import collections,hashlib,json,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'robustness_revision_20261029';GEN=ROOT/'paper/generated'
NAMES={'official':'Official','syntax':'Single','structured64':'Struct64','nearest64':'Nearest64','dictionary64':'Dict64','dictionary_pairs64':'DictPair64'}
REPOS={'Textualize/rich':'Rich','apache/commons-csv':'Commons CSV','checkstyle/checkstyle':'Checkstyle','javaparser/javaparser':'JavaParser','pallets/flask':'Flask','sphinx-doc/sphinx':'Sphinx'}
def write(n,s):(GEN/n).write_text(s,encoding='utf-8')
def cell(x):return f"{100*x['median']:.2f} [{100*x['q025']:.2f}, {100*x['q975']:.2f}]"
def table(spec,head,body):return '\\begin{tabular}{'+spec+'}\n\\toprule\n'+head+' \\\\\n\\midrule\n'+'\n'.join(' & '.join(map(str,r))+' \\\\' for r in body)+'\n\\bottomrule\n\\end{tabular}\n'
def main():
    p=json.loads((OUT/'p1_results.json').read_text());a=np.load(OUT/'p1_draws.npz');summaries=p['summaries'];checks=[]
    for ri,pool in enumerate(p['pools']):
        n=pool['calibration_size']
        for ki,(key,count) in enumerate(pool['keys'].items()):
            h=count['calibration_unknown']
            for m in (20,40,80):
                rank=math.ceil((m+1)*.95);minimum=m-rank+1
                expected=sum(math.comb(h,j)*math.comb(n-h,m-j)/math.comb(n,m) for j in range(minimum,min(h,m)+1) if 0<=m-j<=n-h)
                values=np.isposinf(a[f'p{ri}_b{m}_thresholds'][:,ki,0]);observed=float(values.mean())
                assert np.all(np.isposinf(a[f'p{ri}_b{m}_thresholds'][:,ki,:])==values[:,None])
                mc=float(math.sqrt(expected*(1-expected)/len(values)))
                checks.append(dict(repo=pool['repo'],key=int(key),budget=m,n=n,unknown=h,infinite_requires=minimum,exact_probability=expected,observed_probability=observed,mc_se_under_exact=mc,z=(observed-expected)/mc if mc else 0))
    assert max(abs(c['z']) for c in checks)<5
    rows=[]
    for budget in (20,40,80,'full'):
        r=next(r for r in summaries if r['scope']=='equal_project_mean' and r['method']=='structured64' and r['budget']==budget)
        if budget=='full':rows.append(['Full',f"{r['detection']['mean']*100:.2f}",f"{r['alarm_lower']['mean']*100:.2f}--{r['alarm_upper']['mean']*100:.2f}",'0.00'])
        else:rows.append([budget,cell(r['detection']),cell(r['alarm_lower']),f"{r['infinite_threshold']['mean']*100:.2f}"])
    write('budget_primary.tex',table('lrrr',r'$m$ & Detection & Observed alarms & Infinite thresholds',rows))
    rows=[]
    for method in NAMES:
        for budget in (20,40,80,'full'):
            r=next(r for r in summaries if r['scope']=='equal_project_mean' and r['method']==method and r['budget']==budget)
            if budget=='full':v=[f"{r[k]['mean']*100:.2f}" for k in ('detection','alarm_lower','alarm_upper')]
            else:v=[cell(r[k]) for k in ('detection','alarm_lower','alarm_upper')]
            rows.append([NAMES[method],budget,*v])
    write('budget_all_methods.tex',table('llrrr',r'Method & $m$ & Detection & Alarm lower & Alarm upper',rows))
    rows=[]
    for pool in p['pools']:
        for ki,(key,c) in enumerate(pool['keys'].items()):
            cc=next(c for c in checks if c['repo']==pool['repo'] and c['key']==int(key) and c['budget']==20)
            rows.append([REPOS[pool['repo']],f'$K_{ki+1}$',pool['calibration_size'],c['calibration_unknown'],f"{100*cc['exact_probability']:.2f}",f"{100*cc['observed_probability']:.2f}",c['later_unknown']])
    write('budget_missingness.tex',table('llrrrrr',r'Project & Key & Pool & Unknown & Exact $m=20$ & Observed & Later unknown',rows))
    rows=[]
    for pool in p['pools']:
        for budget in (20,40,80,'full'):
            r=next(r for r in summaries if r['scope']=='project_mean' and r['repo']==pool['repo'] and r['method']=='structured64' and r['budget']==budget)
            if budget=='full':v=[f"{r[k]['mean']*100:.2f}" for k in ('detection','alarm_lower','alarm_upper')]
            else:v=[cell(r[k]) for k in ('detection','alarm_lower','alarm_upper')]
            rows.append([REPOS[pool['repo']],budget,*v])
    write('budget_by_project.tex',table('llrrr',r'Project & $m$ & Detection & Alarm lower & Alarm upper',rows))
    # Same draw index across independently sampled project pools gives equal-project draws.
    mc=[]
    for budget in (20,40,80):
        arr=np.mean([a[f'p{ri}_b{budget}_metrics'].mean(axis=1) for ri in range(6)],axis=0)
        for mi,method in enumerate(NAMES):
            mc.append(dict(budget=budget,method=method,mean_mc_se={metric:float(arr[:,mi,k].std(ddof=1)/math.sqrt(len(arr))) for k,metric in enumerate(('detection','alarm_lower','alarm_upper','infinite_frequency'))}))
    q=json.loads((OUT/'p2_summary.json').read_text());plan=json.loads((OUT/'p2_plan.json').read_text())
    status=collections.Counter((r['canonical_merge'],r['line_status']) for r in plan if r['embedding_ok'])
    assert all(r.get('same_as_canonical') for r in plan if r['line_status']=='clean')
    write('replay_transitions.tex',table('llr','Character policy & Line policy & Attempts',[[a.replace('_',' '),b.replace('_',' '),n] for (a,b),n in sorted(status.items())]+[['Embedding abstention','Not reached',33]]))
    rows=[]
    for repo in list(REPOS)+[None]:
        r=next(r for r in q['summary'] if r['subgroup']=='all' and r['repo']==repo)
        rows.append([REPOS.get(repo,'Total'),r['n'],sum(p['repo']==repo and p['embedding_ok'] and p['canonical_merge']=='clean' for p in plan) if repo else sum(p['embedding_ok'] and p['canonical_merge']=='clean' for p in plan),r['line_status'].get('clean',0),f"{r['canonical_joint']['official']}/{r['line_joint']['official']}",f"{r['canonical_joint']['syntax']}/{r['line_joint']['syntax']}",f"{r['canonical_joint']['structured64']}/{r['line_joint']['structured64']}"])
    write('replay_primary.tex',table('lrrrrrr',r'Project & $n$ & Char clean & Line clean & Official & Single & Struct64',rows))
    rows=[]
    for group in ('all','original_pair','both_clean'):
        r=next(r for r in q['summary'] if r['repo'] is None and r['subgroup']==group)
        for m in NAMES:rows.append([group.replace('_',' '),r['n'],NAMES[m],r['canonical_joint'][m],r['line_joint'][m],r['paired_changes'][m]['gained'],r['paired_changes'][m]['lost']])
    write('replay_all_methods.tex',table('lrlrrrr','Subgroup & $n$ & Method & Character & Line & Gained & Lost',rows))
    plt.rcParams.update({'font.size':9,'font.family':'DejaVu Sans','pdf.fonttype':42})
    fig,axes=plt.subplots(1,2,figsize=(7,2.5),layout='constrained')
    for ax,metric,title in zip(axes,('detection','alarm_lower'),('Detection (%)','Observed negative alarms (%)')):
        for j,m in enumerate(('official','syntax','structured64')):
            rr=[next(r for r in summaries if r['scope']=='equal_project_mean' and r['method']==m and r['budget']==b)[metric] for b in (20,40,80,'full')]
            med=np.array([r['median']*100 for r in rr]);lo=med-np.array([r['q025']*100 for r in rr]);hi=np.array([r['q975']*100 for r in rr])-med
            ax.errorbar(np.arange(4)+(j-1)*.13,med,yerr=[lo,hi],fmt='o-',markersize=3,capsize=2,label=NAMES[m],linewidth=1)
        ax.set_xticks(range(4),['20','40','80','Full']);ax.set_xlabel('Earlier transitions per project');ax.set_ylabel(title);ax.grid(alpha=.2)
    axes[0].legend(fontsize=8,loc='lower right');fig.savefig(GEN/'budget_sensitivity.pdf');fig.savefig(GEN/'budget_sensitivity.png',dpi=200);plt.close(fig)
    audit=dict(p1_exact_infinity_checks=checks,p1_mean_mc_error=mc,p1_max_abs_z=max(abs(c['z']) for c in checks),p2_transition_counts=[dict(character=a,line=b,n=n) for (a,b),n in status.items()],p2_new_code_outputs=0,p2_new_test_jobs=0,full_pool='deterministic point; no sampling interval',generated_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in GEN.glob('budget*')})
    audit['negative_infinite_threshold_count']=sum(int(np.isneginf(a[k]).sum()) for k in a.files if k.endswith('_thresholds'))
    audit['nan_threshold_count']=sum(int(np.isnan(a[k]).sum()) for k in a.files if k.endswith('_thresholds'))
    audit['negative_infinity_and_nan_audit_passed']=audit['negative_infinite_threshold_count']==audit['nan_threshold_count']==0
    (OUT/'assets_audit.json').write_text(json.dumps(audit,indent=2))
    print('Assets generated; maximum infinity probability discrepancy (SE):',audit['p1_max_abs_z'])
if __name__=='__main__':main()
