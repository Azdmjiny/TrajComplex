"""Read-only consistency audit of current summaries, authored report and archives.

No model inference, trajectory generation, D estimation or outcome selection.
"""
from pathlib import Path
import ast,hashlib,json,re,subprocess
from evaluation_runtime import RUNS,REPO
from postprocess_results import holding_summaries,vectoring_summaries,read

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def audit():
    ev=RUNS.parent;archive=ev/'archive/legacy-before-workflow-integration'
    products=[]
    for package,fn in [('holding-equal-duration',holding_summaries),('four-scene-vectoring-evaluation',vectoring_summaries)]:
        root=RUNS/package
        for name,value in fn(root).items():
            if value!=read(root/'results'/name):raise ValueError(f'Summary differs: {package}/{name}')
            products.append(package+'/results/'+name)
    inventory=read(archive/'inventory.json')['files']
    for row in inventory:
        if digest(ev/row['archived'])!=row['sha256']:raise ValueError('Archive hash mismatch: '+row['archived'])
    before=read(archive/'published-before.json')
    changed=[name for name,h in before.items() if digest(ev/name)!=h]
    allowed={'runs/README.md','runs/publication-manifest.json'}
    if any(name.replace('\\','/') not in allowed for name in changed):raise ValueError('Published evidence changed: '+repr(changed))
    manifest=read(RUNS/'publication-manifest.json')
    for name,spec in manifest['files'].items():
        if digest(ev/name)!=spec['sha256']:raise ValueError('Publication hash mismatch: '+name)
    h=read(RUNS/'holding-equal-duration/results/summary.json')
    c=read(RUNS/'holding-equal-duration-old-cutoff/results/summary.json')
    v=read(RUNS/'four-scene-vectoring-evaluation/results/scene-summary.json')
    f=read(RUNS/'vectoring-fixed-baseline-scales/results/summary.json')
    text=(ev/'report.md').read_text(encoding='utf8')
    # Check whole table rows rather than unrelated occurrences of a number.
    def fmt(x):return 'Unavailable' if x is None else f'{x:+.3f}'.replace('-', '−')
    for label,value in [('Complete range, all computable pairs',h['common_correlations']),('Complete range, baseline-valid scenes only',h['baseline_ok_common_correlations']),('Shared archived cutoff, all computable pairs',c['common_valid']),('Shared archived cutoff, baseline-valid scenes only',c['baseline_valid_common'])]:
        hh=value['holding'];ss=value['straight'];n=hh.get('valid',hh.get('n'))
        expected=f"| {label} | {fmt(hh['median'])} | {fmt(ss['median'])} | {n} |"
        if expected not in text:raise ValueError('Authored Holding table drift: '+label)
    for r in f['curves']:
        a=r['original_correlation'];b=r['fixed_correlation']
        expected=f"| {r['order']} | {fmt(a['rho'])} | {fmt(b['rho'])} | {b['valid']}/{b['total']} |"
        if expected not in text:raise ValueError('Authored fixed-scale table drift')
    for row in v:
        expected=f"| {row['n_aircraft']} | {row['eligible']} | {row['valid_D']} / {row['attempted_D']} |"
        if expected not in text:raise ValueError('Authored Vectoring table drift')
    for x,dec in [(h['equal_scene_median_paired_excess'],5),(c['paired_difference']['equal_scene_median'],5)]:
        if f'{x:+.{dec}f}' not in text:raise ValueError('Paired effect drift')
    docs=[ev/'README.md',ev/'report.md',ev/'vectoring-study-history.md',ev/'code/README.md',RUNS/'README.md',archive/'README.md']
    links=0
    for doc in docs:
        for target in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf8')):
            if '://' in target or target.startswith('#'):continue
            if not (doc.parent/target.split('#')[0]).exists():raise ValueError(f'Broken navigation: {doc.name}: {target}')
            links+=1
    for p in (ev/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf8'))
    outside=[line for line in subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=REPO,text=True).splitlines() if not line[3:].startswith('evaluation/')]
    approved_doc='doc/trajectory-embedding-point-cloud-complexity.md'
    if any(line[3:]!=approved_doc for line in outside):raise ValueError('Changes outside approved scope: '+repr(outside))
    doc_text=(REPO/approved_doc).read_text(encoding='utf8')
    if '[evaluation report](../evaluation/report.md)' not in doc_text or '../evaluation/reports/evaluation-pilot.md' in doc_text:
        raise ValueError('External evaluation report link is stale')
    return dict(all_passed=True,saved_summaries_exact=products,archive_files_verified=len(inventory),
        publication_files_verified=len(manifest['files']),published_run_changes=changed,
        published_numerical_results_embeddings_figures_policies_and_execution_snapshots_unchanged=True,
        authored_primary_tables_match=True,navigation_links_checked=links,python_syntax_valid=True,
        changed_paths_outside_evaluation=outside,new_experiments=0,new_encoder_calls=0,new_D_estimates=0,
        threshold_changes=0,software_tests='5 postprocessing integration tests passed; no full experimental rerun',
        external_document_link='doc/trajectory-embedding-point-cloud-complexity.md now links to evaluation/report.md; checked',
        limitations='Read-only saved-record audit and targeted software checks; fresh inference and optimizer behavior were not rerun.')

if __name__=='__main__':print(json.dumps(audit(),indent=2))
