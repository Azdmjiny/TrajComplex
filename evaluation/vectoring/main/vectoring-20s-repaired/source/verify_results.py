"""Read-only consistency checks on the saved before/after result package."""
from pathlib import Path
import sys,json,hashlib,re
R=Path(__file__).resolve().parent;B=R.parent
OLD=B/'vectoring-time-window-sensitivity-2026-10-27/window-20s'
sys.path.insert(0,str(B/'evaluation-python-deps'))
import numpy as np
from scipy.stats import rankdata
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(R/'run-manifest.json');s=read(R/'evaluation-summary.json')
assert m['state']=='complete' and all(sha(Path(p))==h for p,h in m['protected_sources'].items())
count=0
for shape in ['segmented','smooth']:
    for version,base in [('before',OLD/shape),('after',R/shape)]:
        trials=read(base/'results/experiment-results.json')['scenes']
        assert len(trials)==20
        summary=s['comparisons'][shape][version]
        rho=[];valid=0;total=0
        for t in trials:
            dose=t['dose_curve'];total+=len(dose)
            assert [d['vectoring_aircraft'] for d in dose]==list(range(t['n_vectoring_eligible']+1))
            good=[d for d in dose if d['status']=='ok' and d['dimension'] is not None]
            valid+=len(good)
            c=next(v for v in summary['curves'] if (v['scene'],v['replicate'])==(t['scene_id'],t['replicate']))
            if len(good)>=5 and np.ptp([d['dimension'] for d in good])>0:
                # Independent rank-and-Pearson formulation of Spearman.
                value=float(np.corrcoef(rankdata([d['vectoring_aircraft'] for d in good]),rankdata([d['dimension'] for d in good]))[0,1])
                assert abs(value-c['rho'])<1e-12;rho.append(value)
            else:assert c['rho'] is None and c['reason']
            count+=1
        a=summary['all']
        assert a['valid_D']==valid and a['attempted_D']==total
        assert a['positive']==sum(v>0 for v in rho) and a['negative']==sum(v<0 for v in rho) and a['zero']==sum(v==0 for v in rho)
        assert abs(a['median']-float(np.median(rho)))<1e-12
report=(R/'report.md').read_text(encoding='utf8')
links=re.findall(r'\]\(([^)]+)\)',report)
assert all((R/link).exists() for link in links)
assert len(read(R/'screening-exclusions.json')['records'])==14
assert read(R/'failed-D-records.json')['count']==0
audit=dict(state='passed',order_correlations_independently_checked=count,full_dose_ranges_checked=count,
    old_dose_records_reproduced=s['old_dose_records_exactly_reproduced'],protected_files_unchanged=len(m['protected_sources']),
    report_links_checked=len(links),new_failed_D=0,negative_and_zero_coefficients_retained=True)
(R/'verification.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf8')
print(json.dumps(audit))
