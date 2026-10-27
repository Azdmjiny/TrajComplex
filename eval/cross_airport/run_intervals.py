"""Airport-balanced intervals, temporal/LOAO validation, and one histogram."""
import argparse,json,os
from pathlib import Path
import numpy as np
import pandas as pd


def weighted_q(groups,probs):
    if not groups or any(len(x)==0 for x in groups):
        return np.full(len(probs),np.nan)
    x=np.concatenate(groups)
    w=np.concatenate([np.full(len(g),1/(len(groups)*len(g))) for g in groups])
    order=np.argsort(x,kind='stable');x=x[order]
    c=np.cumsum(w[order]);c/=c[-1]
    return x[np.minimum(np.searchsorted(c,np.asarray(probs)-1e-14),len(x)-1)]


def evaluate(values,bounds,probs):
    lo,hi=bounds;own=weighted_q([values],probs);n=len(values)
    width=own[1]-own[0]
    return dict(finite_hours=n,inside_hours=int(((values>=lo)&(values<=hi)).sum()),
                coverage_pct=100*np.mean((values>=lo)&(values<=hi)) if n else np.nan,
                below_pct=100*np.mean(values<lo) if n else np.nan,
                above_pct=100*np.mean(values>hi) if n else np.nan,
                width_ratio=(hi-lo)/width if width>0 else np.nan,
                local_lower=own[0],local_upper=own[1])


def estimate(cal,ev,airports,levels):
    rows=[];ends=[]
    for held in [None,*airports]:
        train=airports if held is None else [a for a in airports if a!=held]
        kind='temporal' if held is None else 'loao'
        for level in levels:
            p=(1-level/100)/2;probs=[p,1-p]
            bounds=weighted_q([cal[a] for a in train],probs)
            ends.append(dict(validation=kind,heldout_airport=held or '',interval_pct=level,
                             shared_lower=bounds[0],shared_upper=bounds[1],shared_width=bounds[1]-bounds[0],
                             calibration_airports=';'.join(train)))
            for a in (airports if held is None else [held]):
                rows.append(dict(validation=kind,airport=a,interval_pct=level,
                                 shared_lower=bounds[0],shared_upper=bounds[1],
                                 **evaluate(ev[a],bounds,probs)))
    return pd.DataFrame(rows),pd.DataFrame(ends)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path(__file__).with_name('config.json'))
    p.add_argument('--input',type=Path,required=True,help='CSV: airport,hour_local,dimension')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bootstrap-repeats',type=int)
    args=p.parse_args();cfg=json.loads(args.config.read_text(encoding='utf-8-sig'))
    if args.output.exists(): raise FileExistsError('Choose a new output directory')
    df=pd.read_csv(args.input,dtype={'airport':str})
    if not {'airport','hour_local','dimension'}<=set(df): raise ValueError('Missing input columns')
    if df.duplicated(['airport','hour_local']).any(): raise ValueError('Duplicate airport/hour')
    # Use the date at each airport, not a conversion of all hours to UTC dates.
    timestamps=[pd.Timestamp(x) for x in df.hour_local]
    if any(t.tzinfo is None for t in timestamps): raise ValueError('hour_local requires a UTC offset')
    df['day']=[t.date().isoformat() for t in timestamps]
    values=pd.to_numeric(df.dimension,errors='raise')
    if np.isinf(values).any(): raise ValueError('Infinite D')
    df['D']=values
    airports=list(cfg['airports']);levels=cfg['interval_levels'];cut=cfg['calibration_end_local']
    if set(df.airport)!=set(airports) or len(airports)<2: raise ValueError('Input/config airport mismatch')
    if any(not 0<x<100 for x in levels): raise ValueError('Invalid central interval level')
    # Shared local-date draws preserve cross-airport dependence within a day.
    dates=sorted(df.day.unique());caldays=[d for d in dates if d<cut];evdays=[d for d in dates if d>=cut]
    if not caldays or not evdays: raise ValueError('Both time splits need observations')
    daily={a:{d:df.loc[(df.airport==a)&(df.day==d)&df.D.notna(),'D'].to_numpy() for d in dates} for a in airports}
    def collect(days): return {a:np.concatenate([daily[a][d] for d in days]) for a in airports}
    cal,ev=collect(caldays),collect(evdays)
    if any(len(cal[a])==0 or len(ev[a])==0 for a in airports): raise ValueError('Empty calibration/evaluation airport')
    metrics,endpoints=estimate(cal,ev,airports,levels)
    repeats=cfg['bootstrap_repeats'] if args.bootstrap_repeats is None else args.bootstrap_repeats
    if repeats<0: raise ValueError('Negative bootstrap repeats')
    rng=np.random.default_rng(cfg['seed']);boot=[]
    for i in range(repeats):
        bc=collect(rng.choice(caldays,len(caldays)));be=collect(rng.choice(evdays,len(evdays)))
        b,_=estimate(bc,be,airports,levels);b['replicate']=i;boot.append(b)
    if boot:
        bf=pd.concat(boot,ignore_index=True)
        for i,row in metrics.iterrows():
            part=bf[(bf.validation==row.validation)&(bf.airport==row.airport)&(bf.interval_pct==row.interval_pct)]
            for field in ['coverage_pct','width_ratio']:
                v=part[field].to_numpy();v=v[np.isfinite(v)]
                ci=np.quantile(v,[.025,.975]) if len(v) else [np.nan,np.nan]
                metrics.loc[i,field+'_ci_low']=ci[0];metrics.loc[i,field+'_ci_high']=ci[1]
                metrics.loc[i,field+'_bootstrap_successes']=len(v)
    args.output.mkdir(parents=True)
    metrics.to_csv(args.output/'validation_metrics.csv',index=False)
    endpoints.to_csv(args.output/'shared_intervals.csv',index=False)
    support=[]
    for a in airports:
        part=df[df.airport==a]
        support.append(dict(airport=a,input_hours=len(part),finite_hours=int(part.D.notna().sum()),
                            calibration_finite_hours=len(cal[a]),evaluation_finite_hours=len(ev[a])))
    pd.DataFrame(support).to_csv(args.output/'input_support.csv',index=False)
    cfg['bootstrap_repeats']=repeats
    (args.output/'analysis_config.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
    os.environ.setdefault('MPLCONFIGDIR',str(args.output.resolve()/'.mplcache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    xlim=cfg['histogram_xlim'];bw=cfg['histogram_bin_width']
    allv=df.D.dropna().to_numpy();lo=min(xlim[0],np.floor(allv.min()/bw)*bw);hi=max(xlim[1],(np.floor(allv.max()/bw)+1)*bw)
    bins=np.arange(lo,hi+bw/2,bw)
    fig,axes=plt.subplots(int(np.ceil(len(airports)/2)),2,figsize=(13,4.3*int(np.ceil(len(airports)/2))),sharex=True,sharey=True,squeeze=False)
    colors={50:'#297D9C',75:'#60853B',90:'#D28B35'};shown=[n for n in [90,50] if n in levels]
    for ax,a in zip(axes.flat,airports):
        v=df.loc[(df.airport==a)&df.D.notna(),'D'].to_numpy()
        for level in shown:
            r=endpoints[(endpoints.validation=='temporal')&(endpoints.interval_pct==level)].iloc[0]
            ax.axvspan(r.shared_lower,r.shared_upper,color=colors[level],alpha=.16)
        ax.hist(v,bins=bins,color='#6487A0',edgecolor='white',linewidth=.5)
        text=[]
        for level in sorted(shown):
            q=(1-level/100)/2;bounds=weighted_q([v],[q,1-q])
            for x in bounds: ax.axvline(x,color='#354654',ls=':' if level==50 else '--',lw=1.3)
            text.append(f'{level}% [{bounds[0]:.3f}, {bounds[1]:.3f}]')
        text.append(f'Finite hours: {len(v)} / {sum(df.airport==a)}')
        ax.text(.02,.96,'\n'.join(text),transform=ax.transAxes,ha='left',va='top',fontsize=9,bbox=dict(facecolor='white',alpha=.85,edgecolor='none'))
        name=cfg['airports'][a].get('name',a);ax.set_title(f'{name} ({a})',loc='left')
        ax.set_xlim(*xlim);ax.set_xlabel('Original D');ax.set_ylabel(f'Hours per {bw:g}-D bin');ax.grid(axis='y',alpha=.15)
    for ax in list(axes.flat)[len(airports):]: ax.set_visible(False)
    fig.suptitle('D distributions and shared candidate intervals')
    fig.legend(handles=[Patch(color=colors[n],alpha=.3,label=f'Shared central {n}%') for n in shown],loc='lower center',ncol=2)
    fig.tight_layout(rect=[0,.06,1,.95]);fig.savefig(args.output/'histogram.png',dpi=200);plt.close(fig)
    print(metrics[['validation','airport','interval_pct','coverage_pct','width_ratio']].to_string(index=False))

if __name__=='__main__': main()
