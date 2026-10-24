"""Plot saved summary comparisons; no peak search or experiment execution."""
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def make_figures(data,output):
    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    scopes=[data['holding']['common_correlations'],data['cutoff']['common_valid']]
    for offset,arm,color in [(-.18,'holding','#2166ac'),(.18,'straight','#d66016')]:
        axes[0].bar(np.arange(2)+offset,[s[arm]['median'] for s in scopes],width=.35,label=arm.title(),color=color)
    axes[0].set(xticks=[0,1],xticklabels=['Full range','Shared old cutoff'],ylabel='Median Spearman rho',title='Holding equal-duration control',ylim=(-1,1))
    axes[0].legend();axes[0].axhline(0,color='gray',lw=.8)
    rows=data['fixed']['curves'];x=np.array([r['order'] for r in rows])
    axes[1].plot(x,[r['original_correlation']['rho'] for r in rows],'o--',color='gray',label='Original')
    axes[1].plot(x,[r['fixed_correlation']['rho'] if r['fixed_correlation']['rho'] is not None else np.nan for r in rows],'o-',color='#2166ac',label='Fixed baseline scales')
    missing=[str(r['order']) for r in rows if r['fixed_correlation']['rho'] is None]
    if missing: axes[1].text(.98,.03,'Fixed unavailable: order '+', '.join(missing),transform=axes[1].transAxes,ha='right',fontsize=9)
    axes[1].set(xticks=x,xlabel='Within-scene order',ylabel='Spearman rho',title='Vectoring: '+data['fixed']['scene'],ylim=(-1,1))
    axes[1].legend();axes[1].axhline(0,color='gray',lw=.8)
    for ax in axes:ax.grid(axis='y',alpha=.2)
    fig.suptitle('Saved results; dependent repeats and different estimability counts',fontsize=13)
    for ext in ['png','svg']:fig.savefig(output/f'summary.{ext}',dpi=180)
    plt.close(fig)

if __name__=='__main__':
    from refresh_outputs import main
    main()
