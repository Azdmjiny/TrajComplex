"""Build a current summary from saved run statistics, without new inference."""
from pathlib import Path
import json,os
from collections import Counter
from evaluation_runtime import RUNS

def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def fmt(value):return 'Unavailable' if value is None else f'{value:+.3f}'

def count_candidate_reasons(screens):
    """Count each side-normalized rejection reason once per candidate."""
    return Counter(reason for row in screens
                   for reason in {r.split(':',1)[-1] for r in row['rejection_reasons']})

def build_report(runs,output):
    runs=Path(runs);output=Path(output)
    holding=read(runs/'holding-equal-duration/results/summary.json')
    cutoff=read(runs/'holding-equal-duration-old-cutoff/results/summary.json')
    fixed=read(runs/'vectoring-fixed-baseline-scales/results/summary.json')
    vectoring=read(runs/'four-scene-vectoring-evaluation/results/scene-summary.json')
    lines=['# Saved evaluation results','',
        'Generated from published statistics only. No trajectories, embeddings, D estimates or cutoffs were recomputed. Full results and rejected values are retained in the source packages.','',
        '## Holding: matched valid doses','',
        '| Scope | Holding median rho | Straight median rho | Matched orders |','|---|---:|---:|---:|']
    for name,v in [('Complete range',holding['common_correlations']),('Archived common cutoff',cutoff['common_valid']),
                   ('Common cutoff, valid baseline only',cutoff['baseline_valid_common'])]:
        h=v['holding'];s=v['straight'];n=h.get('valid',h.get('n'))
        lines.append(f"| {name} | {fmt(h['median'])} | {fmt(s['median'])} | {n} |")
    lines += ['',f"There are {holding['baseline_valid_scenes']} baseline-valid scenes. At the common archived cutoff, {cutoff['paired_difference']['positive_scene_medians']} of {cutoff['paired_difference']['scenes']} scene summaries have positive Holding-minus-Straight differences; their equal-scene median is {cutoff['paired_difference']['equal_scene_median']:+.5f}.",'',
        'Both arms append 240 seconds at the endpoint. The old midpoint-Holding cutoffs are shared unchanged; they are outcome-selected, not physical limits. Equal duration does not isolate pure length because straight continuation also changes geometry/location. Orders are dependent repeats.','',
        '## Vectoring','',
        'The frozen four-scene run contains 21 accepted candidates. The first three scenes fail the original D fit-quality gate; the fourth has mixed signs. The fixed-scale diagnostic below is separate from the primary results.','',
        '| Order | Original rho | Fixed-scale rho | Fixed-valid doses |','|---|---:|---:|---:|']
    for r in fixed['curves']:
        lines.append(f"| {r['order']} | {fmt(r['original_correlation']['rho'])} | {fmt(r['fixed_correlation']['rho'])} | {r['fixed_correlation']['valid']}/6 |")
    lines += ['', 'A sign change with all six doses retained demonstrates fitting-scale sensitivity. An unavailable dose or correlation is not evidence of a positive effect. The results do not establish stable strong positive Vectoring association or complete validation of operational complexity.','',
        '## Detailed source reports','']
    for folder in ['holding-equal-duration','holding-equal-duration-old-cutoff','four-scene-vectoring-evaluation','vectoring-fixed-baseline-scales']:
        target=runs/folder/'report.md'
        try:link=os.path.relpath(target,output).replace('\\','/')
        except ValueError:link=target.as_uri()
        lines.append(f'- [{folder}]({link})')
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    return dict(holding=holding,cutoff=cutoff,fixed=fixed,vectoring=vectoring)

if __name__=='__main__':
    from refresh_outputs import main
    main()
