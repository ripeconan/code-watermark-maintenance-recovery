"""Publication figures from server-derived held-out detection summaries."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'results/confirmation_summary.json'
d=json.loads(path.read_text());assert d['missing_functional']==0
lookup={(r['language'],r['method'],r['group'],r['edit']):r for r in d['summary'] if r['regime']=='envelope' and r['alpha']==.05}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42,'ps.fonttype':42})
colors={'official':'#717680','delta_dictionary':'#2464af','nearest_budget':'#a65a32','l1_4':'#7867a7','syntax':'#167f83'}
labels={'official':'Official score','delta_dictionary':'Learned edit dictionary','nearest_budget':'Equal-budget search','l1_4':'Radius-4 search','syntax':'Syntax-derived search'}
fig,axes=plt.subplots(3,3,figsize=(7.3,6.6),sharey=True)
for col,lang in enumerate(('python','java','cpp')):
    for row,edit in enumerate(('helper','formatter_helper','helper_loop')):
        ax=axes[row,col]
        for method in colors:
            r=lookup[lang,method,'positive',edit];v=r['detection'];x=r['candidates_mean'];y=100*v['mean']
            ax.errorbar(x,y,yerr=[[y-100*v['lo']],[100*v['hi']-y]],fmt='o',ms=5,color=colors[method],capsize=2,label=labels[method])
            neg=lookup[lang,method,'negative',edit]
            offset={'official':(3,4),'delta_dictionary':(4,-11),'nearest_budget':(3,3),'l1_4':(-42,-11),'syntax':(4,4)}[method]
            if row==2 and method=='official':offset=(0,-12)
            if row==2 and method=='delta_dictionary':offset=(4,4)
            ax.annotate(f"{100*neg['detected']/neg['n']:.1f}%",(x,y),xytext=offset,textcoords='offset points',fontsize=7,color=colors[method])
        ax.set_xscale('log');ax.set_xlim(.7,500);ax.set_ylim(-3,108);ax.set_xticks([1,10,100]);ax.set_xticklabels(['1','10','100'])
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2)
        if row==0:ax.set_title({'python':'Python','java':'Java','cpp':'C++'}[lang],weight='bold')
        if row==2:ax.set_xlabel('Mean context candidates')
        if col==0:ax.set_ylabel(('Known helper','Formatting + helper','Unseen loop helper')[row]+'\nDetection (%)')
handles,legend=axes[0,0].get_legend_handles_labels();fig.legend(handles,legend,loc='lower center',ncol=2,bbox_to_anchor=(.5,-.01),frameon=False)
fig.subplots_adjust(left=.1,right=.98,top=.94,bottom=.14,hspace=.22,wspace=.15)
dest=ROOT/'paper/generated';fig.savefig(dest/'recovery_budget.pdf',bbox_inches='tight');fig.savefig(dest/'recovery_budget.png',dpi=220,bbox_inches='tight')
plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(7.3,2.5),sharey=True)
for ax,lang in zip(axes,('python','java','cpp')):
    for method in colors:
        points=[]
        for alpha in (.01,.05,.10):
            rr={r['group']:r for r in d['summary'] if r['regime']=='envelope' and r['alpha']==alpha and r['language']==lang and r['method']==method and r['edit']=='helper_loop'}
            points.append((100*rr['negative']['detected']/rr['negative']['n'],100*rr['positive']['joint_count']/rr['positive']['n']))
        ax.plot(*zip(*points),'-o',ms=3,lw=1,color=colors[method],label=labels[method]);ax.scatter(*points[1],s=40,facecolors='none',edgecolors=colors[method])
    ax.set_title({'python':'Python','java':'Java','cpp':'C++'}[lang]);ax.set_xlabel('Observed negative alarms (%)');ax.set_ylim(-3,103);ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
axes[0].set_ylabel('Correct and detected (%)');fig.tight_layout();fig.savefig(dest/'risk_operating_points.pdf',bbox_inches='tight');fig.savefig(dest/'risk_operating_points.png',dpi=220,bbox_inches='tight');plt.close(fig)
print('PLOT_WRITTEN',path.name,'functional_missing',d['missing_functional'])
