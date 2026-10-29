"""Generate final-only manuscript tables from audited server summaries."""
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'paper/generated'
s=json.loads((ROOT/'results/confirmation_summary.json').read_text());assert s['missing_functional']==0
lookup={(r['language'],r['method'],r['group'],r['edit']):r for r in s['summary'] if r['regime']=='envelope' and r['alpha']==.05}
langs=('python','java','cpp');names={'python':'Python','java':'Java','cpp':'C++'};methods=('official','delta_dictionary','nearest_budget','l1_4','syntax')
labels=('Official','Dictionary','Equal budget','Radius 4','Syntax')
def write(name,lines): (out/(name+'.tex')).write_text('\n'.join(lines)+'\n',encoding='utf8')
def pct(n,d):return f'{100*n/d:.1f}'
lines=[r'\begin{tabular}{@{}llrrrrr@{}}',r'\toprule','Language & Edit & '+' & '.join(labels)+r' \\',r'\midrule']
for lang in langs:
    for edit,label in [('original','Original'),('helper','Helper'),('formatter_helper','Format + helper'),('helper_loop','Loop helper')]:
        cells=[]
        for method in methods:
            p=lookup[lang,method,'positive',edit];n=lookup[lang,method,'negative',edit]
            cells.append(pct(p['joint_count'],p['n'])+' / '+pct(n['detected'],n['n']))
        lines.append(names[lang]+' & '+label+' & '+' & '.join(cells)+r' \\')
    if lang!='cpp':lines.append(r'\addlinespace')
lines += [r'\bottomrule',r'\end{tabular}'];write('confirmation_joint',lines)
lines=[r'\begin{tabular}{@{}lrrrr@{}}',r'\toprule',r'Language & Official & Syntax & Gain [95\% CI] & Holm $p$ \\',r'\midrule']
for lang in langs:
    r=next(r for r in s['contrasts'] if r['language']==lang and r['edit']=='helper' and r['target']=='syntax' and r['baseline']=='official');v=r['delta_joint']
    a=lookup[lang,'official','positive','helper'];b=lookup[lang,'syntax','positive','helper']
    lines.append(f"{names[lang]} & {a['joint_count']}/{a['n']} & {b['joint_count']}/{b['n']} & {100*v['mean']:.1f} [{100*v['lo']:.1f},{100*v['hi']:.1f}] & {r['holm_p']:.5f}"+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('confirmation_primary',lines)
meta=json.loads((ROOT/'results/study_metadata.json').read_text());lines=[r'\begin{tabular}{@{}lrrrrr@{}}',r'\toprule',r'Language & Calibration & Test & Source pass & Marked pass & Marked compile \\',r'\midrule']
for lang in langs:
    r=meta['languages'][lang];lines.append(f"{names[lang]} & {r['valid']} & {r['test']} & {r['source_test_pass']}/{r['test']} & {r['marked_test_pass']}/{r['test_key_records']} & {r['marked_compile_pass']}/{r['test_key_records']}"+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('confirmation_flow',lines)
lines=[r'\begin{tabular}{@{}lrrrrr@{}}',r'\toprule','Language & '+' & '.join(labels)+r' \\',r'\midrule']
for lang in langs:
    cells=[]
    for method in methods:
        r=next(r for r in s['envelope_risk'] if r['language']==lang and r['method']==method and r['alpha']==.05);v=r['interval']
        cells.append(f"{100*v['mean']:.1f} [{100*v['lo']:.1f},{100*v['hi']:.1f}]")
    lines.append(names[lang]+' & '+' & '.join(cells)+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('confirmation_risk',lines)
t=json.loads((ROOT/'results/recovery_timing.json').read_text());lines=[r'\begin{tabular}{@{}lrrrrr@{}}',r'\toprule','Language & '+' & '.join(labels)+r' \\',r'\midrule']
for lang in langs:
    cells=[]
    for method in methods:
        rr=[r for r in t['rows'] if r['language']==lang and r['method']==method];cells.append(f"{1000*statistics.median(r['median_seconds'] for r in rr):.2f}")
    lines.append(names[lang]+' & '+' & '.join(cells)+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('confirmation_timing',lines)
stress=json.loads((ROOT/'results/structural_stress_summary.json').read_text());sl={(r['language'],r['method'],r['group'],r['edit']):r for r in stress['summary']}
lines=[r'\begin{tabular}{@{}llrrr@{}}',r'\toprule',r'Language & Edit & Official & Dictionary & Syntax \\',r'\midrule']
for lang in langs:
    for edit,label in [('nested_helper','Nested helper'),('two_helpers','Two helpers')]:
        cells=[]
        for method in ('official','delta_dictionary','syntax'):
            p=sl[lang,method,'positive',edit];n=sl[lang,method,'negative',edit];cells.append(f"{p['joint_count']}, {p['detected']}, {n['detected']}")
        lines.append(names[lang]+' & '+label+' & '+' & '.join(cells)+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('stress_boundary',lines)
# Complete compact operating-point tables for the supplement.
lines=[r'\begin{tabular}{@{}llrrrrr@{}}',r'\toprule','Language & Edit & '+' & '.join(labels)+r' \\',r'\midrule']
for lang in langs:
    for edit in ('original','formatter','helper','formatter_helper','helper_loop'):
        cells=[]
        for method in methods:
            p=lookup[lang,method,'positive',edit];n=lookup[lang,method,'negative',edit];cells.append(f"{p['detected']}/{p['joint_count']}/{n['detected']}")
        lines.append(names[lang]+' & '+edit.replace('_',r'\_')+' & '+' & '.join(cells)+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('confirmation_complete',lines)
lines=[r'\begin{tabular}{@{}llrrrrrr@{}}',r'\toprule',r'Language & Edit & Radius 1 & Radius 2 & Radius 3 & Radius 4 & Syntax & Oracle \\',r'\midrule']
for lang in langs:
    for edit,label in [('helper','Helper'),('helper_loop','Loop helper')]:
        cells=[]
        for method in ('l1_1','l1_2','l1_3','l1_4','syntax','oracle'):
            p=lookup[lang,method,'positive',edit];n=lookup[lang,method,'negative',edit];cells.append(f"{p['detected']}/{p['joint_count']}/{n['detected']}")
        lines.append(names[lang]+' & '+label+' & '+' & '.join(cells)+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('confirmation_radii_oracle',lines)
print('FINAL_TABLES_WRITTEN',s['raw_records'],t['parity_cases'])
diag=json.loads((ROOT/'results/review_diagnostics.json').read_text())
lines=[r'\begin{tabular}{@{}llrrrr@{}}',r'\toprule',r'Language & Edit & Official & Dictionary & Radius 4 & Syntax \\',r'\midrule']
for lang in langs:
    for edit,label in [('helper','Helper'),('helper_loop','Loop helper')]:
        cells=[]
        for method in ('official','delta_dictionary','l1_4','syntax'):
            r=next(r for r in diag['roc'] if r['language']==lang and r['edit']==edit and r['method']==method and r['endpoint']=='joint')
            cells.append(f"{100*r['tpr']:.1f} [{100*r['tpr_lo']:.1f},{100*r['tpr_hi']:.1f}]")
        lines.append(names[lang]+' & '+label+' & '+' & '.join(cells)+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('diagnostic_roc',lines)
lines=[r'\begin{tabular}{@{}llrrrr@{}}',r'\toprule',r'Language & Key & Official & Dictionary & Radius 4 & Syntax \\',r'\midrule']
for lang in langs:
    for i,key in enumerate((15485863,32452843,49979687),1):
        cells=[]
        for method in ('official','delta_dictionary','l1_4','syntax'):
            p=next(r for r in diag['per_key'] if r['language']==lang and r['key']==key and r['edit']=='helper_loop' and r['method']==method and r['group']=='positive')
            n=next(r for r in diag['per_key'] if r['language']==lang and r['key']==key and r['edit']=='helper_loop' and r['method']==method and r['group']=='negative')
            cells.append(f"{p['detected']}/{p['joint']}/{n['detected']}")
        lines.append(names[lang]+f' & $K_{i}$ & '+' & '.join(cells)+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('confirmation_per_key',lines)
lines=[r'\begin{tabular}{@{}llrr@{}}',r'\toprule',r'Language & Probe & Syntax alarms & Problem-cluster interval (\%) \\',r'\midrule']
for lang in langs:
    for edit,label in [('nested_helper','Nested helper'),('two_helpers','Two helpers')]:
        r=sl[lang,'syntax','negative',edit];v=r['detection'];lines.append(f"{names[lang]} & {label} & {r['detected']}/{r['n']} & [{100*v['lo']:.1f},{100*v['hi']:.1f}]"+r' \\')
lines += [r'\bottomrule',r'\end{tabular}'];write('stress_risk_intervals',lines)
