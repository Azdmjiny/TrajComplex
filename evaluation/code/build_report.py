"""Generate the canonical GitHub-readable Markdown evaluation report."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def fmt(v):return f'{v:.3f}' if v is not None else 'Not estimable'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])

def main():
    s=json.loads((ROOT/'results/summary.json').read_text(encoding='utf8'))
    f=json.loads((ROOT/'figures/index.json').read_text(encoding='utf8'))
    run=json.loads((ROOT/'results/run-manifest.json').read_text(encoding='utf8'))
    rows=[];paired=[];cuts=[];vector=[]
    for v in ['qc500','qc350']:
        for label,key in [('All scenes','all'),('Baseline-estimable only','baseline_ok')]:
            a=s[v]['holding'][key]['full'];b=s[v]['holding'][key]['retained'];p=s[v]['holding'][key]['paired_comparison']
            rows.append([v,label,a['n'],fmt(a['median']),b['n'],fmt(b['median']),f"{b['positive']}/{b['n']}"])
            paired.append([v,label,p['full']['n'],fmt(p['full']['median']),fmt(p['retained']['median'])])
        for q in s[v]['holding']['scenes']:
            cut=f"{q['cutoff']}/{q['n_aircraft']} ({q['cutoff_fraction']:.1%})" if q['cutoff'] is not None else 'No eligible peak'
            cuts.append([v,q['scene_id'],cut,f"{q['full']['n']} → {q['retained']['n']}",fmt(q['full']['median']),fmt(q['retained']['median'])])
    for v in ['qc500','qc350','qc500_safe','qc350_safe']:
        q=s[v]['vectoring']['all']['full'];vector.append([v,q['n'],fmt(q['median']),f"{q['positive']}/{q['n']}"])
    text='''# Holding / Vectoring evaluation after geometry repair and screening

Updated: 2026-10-19. This report replaces the former `evaluation-pilot.md`. Current results, figures, and reproduction code remain in `results/`, `figures/`, and `code/`. Git history retains earlier committed versions without separate dated directories. Complete dose curves remain available; truncation only determines which points enter the correlation calculation.

**Interpretation: the retained pre-peak Holding segment is strongly positively correlated, but its peak is selected from the same outcomes. This is a post hoc, exploratory local association, not independent validation, evidence that the declining segment is invalid, or proof that the algorithm has exceeded its operating range.** The full range still rises and then falls. Vectoring is not truncated, and its positive correlation remains after cleaning. Five random orders are within-hour repeats, not five independent hours; no confirmatory p-values are reported.

## Implemented fixes

- The second Holding turn no longer applies an extra initial heading rotation. Natural geometric closure is checked before pinning the endpoint to remove floating-point drift, avoiding the previous large jump.
- In addition to missing/nonfinite values, ground records, length, and time-gap screening, raw trajectories are checked for latitude/longitude bounds, altitude from −500 to 20000 m, horizontal speed, and absolute vertical speed ≤100 m/s. The entire aircraft-hour is rejected rather than interpolating away an anomalous jump. Primary horizontal speed is ≤500 m/s, with ≤350 m/s for strict sensitivity screening. These are diagnostic thresholds, not a validated flight envelope.
- Vectoring candidates must pass a ≤500 m/s speed screen for both left and right offsets. Failed candidates remain in the eligible baseline point cloud but are not injected. `safe` is only a run label and does not guarantee full physical feasibility. Changing coordinates changes speed; the maneuver cannot be described as preserving original speed.
- Correlation requires `status=ok`, finite D, and at least five valid points. Denominators reflect the actual number of computable curves. The final estimability bin includes the 100% dose, and subsample sizes exceeding the available aircraft count are skipped.
- Manual replacement of report numbers has been replaced by a unified data-generation workflow to prevent stale numbers from overwriting the report.

## Experimental conditions

The original 12 hours and five random injection orders per hour are fixed; cleaning does not replace scenes. Original aircraft order and Vectoring side are generated before excluding ineligible aircraft, preserving surviving aircraft order and side. Primary screening retains 761/771 aircraft-hour trajectories; strict screening retains 652/771.

The same frozen Encoder, sum pooling, and unnormalized Euclidean distances are used. Each scene has 64 fixed candidate radii derived from its baseline. Estimator gates are unchanged: at least 30 points, at least 8 fitted scales, a radius span of at least 2-fold, correlation-integral bounds 0.02–0.3, and R²≥0.98.

Holding adds 48 five-second samples per aircraft; length remains confounded with sum pooling. Neither an equal-length control nor a diversified Holding control has established the cause of the decline. Those unadopted controls are not included in the conclusions.

## Holding truncation rule

The five random orders within each hour share one cutoff. Compute mean valid D at each dose; only doses with at least three valid repeats can select the peak. Choose the earliest global maximum of mean D. Retain the peak and all preceding doses, without smoothing or selecting peaks separately for each curve. Local pre-peak declines remain; this does not remove every negative-slope segment.

## Holding: all available curves

'''
    text+=table(['Screening','Sample scope','Full-range curves','Full-range median ρ','Retained curves','Retained-range median ρ','Retained positive correlations'],rows)
    text+='''

All 50 retained QC500 curves are positive; 10 of the original 60 have too few valid points in the retained segment to compute correlation. QC350 has 52 positive curves out of 53. These denominator changes must not be ignored.

## Paired comparison of the same curves

'''+table(['Screening','Sample scope','Curves computable in both ranges','Full-range median ρ','Retained-range median ρ'],paired)
    text+='''

Under primary screening, all 30 curves from the six baseline-estimable hours remain. Median ρ rises from 0.191 to 0.928. The curve count is unchanged in this comparison, but peak-selection bias remains. Taking the median across repeats within each hour, QC500 has 11 computable retained-range hours, all positive, with an across-hour median of 0.904. QC350 also has 11 computable hours, with a median of 0.877.

## Per-hour cutoffs

'''+table(['Screening','Hour (UTC)','Cutoff aircraft / scene aircraft','Curves: full → retained','Full-range hourly ρ','Retained-range hourly ρ'],cuts)
    text+='''

QC500 cutoff fractions range from approximately 39% to 59%; the rule does not uniformly remove doses above 50%. For QC350 on 2026-09-30T15Z, no dose has three valid repeats, so no peak is forced. QC500 has an eligible peak for that hour, but each retained curve still has fewer than five valid points and cannot produce a correlation.

## Vectoring: full range without truncation

'''+table(['Screening','Computable curves','Median ρ','Positive curves'],vector)
    text+='''

The primary result is `qc500_safe.vectoring` in the consolidated `experiment-results.json`, combining QC500 with candidate-maneuver speed screening. QC500 and QC350 without candidate screening are sensitivity comparisons in the same file. Positive correlation supports a response to synthetic deformation, not validity for real controller workload.

## Aircraft-count sensitivity

Across the six QC500 hours with estimable full baselines, median hourly estimability rates at N=30, 40, and 50 are 52%, 67%, and 92%. Median absolute D differences from the full point cloud are 0.235, 0.126, and 0.048. Each size uses 50 random subsamples. Under strict screening at N=50, only five hours have enough aircraft and an estimable baseline; changes in sample composition must not be interpreted as a pure aircraft-count effect.

## Figures

Matplotlib produces 200 dpi PNGs and vector SVGs. Colored segments show retained Holding doses, gray segments show excluded doses, black lines are means across available repeats at each dose, and orange dashed lines/stars mark selected peaks. Missing D is not replaced by zero; the number of repeats contributing to the mean may vary. Every figure retains the full range for reference.

'''
    for name in f['figures']:
        text+=f'### {name}\n\n![{name}](figures/{name}.png)\n\n[Vector SVG](figures/{name}.svg)\n\n'
    text+='''## Data and reproduction

- [All statistics and per-hour results](results/summary.json)
- [Consolidated full-dose data](results/experiment-results.json)
- [Holding point-level inclusion and exclusion reasons](results/qc500-holding-point-selection.csv)
- [Strict-screening point-level decisions](results/qc350-holding-point-selection.csv)
- [Raw trajectory rejection audit](results/quality_audit.json)
- [Aircraft-count sensitivity data](results/aircraft-count-sensitivity.json)
- [Runtime environment and source hashes](results/run-manifest.json)
- [Statistical rules and input hashes](results/analysis-manifest.json)
- [Execution instructions](README.md)

Regenerate statistics, figures, and this report from saved full results without raw trajectories or a checkpoint:

```bash
python evaluation/code/refresh_outputs.py
```

To rerun Encoder inference and all experiments from raw trajectories, set `ATM_DATA_ZIP` and `ATM_ENCODER_CHECKPOINT`:

```bash
python evaluation/code/run_evaluation.py
python evaluation/code/refresh_outputs.py
```

'''
    text+=f"Inference environment: PyTorch `{run['torch']}` ; device `{run['device']}`. Checkpoint SHA256:`{run['checkpoint_sha256']}`.\n"
    (ROOT/'report.md').write_text(text,encoding='utf8')
    manifest=ROOT/'results/analysis-manifest.json';m=json.loads(manifest.read_text());m['matplotlib']=f['matplotlib'];m['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'code').glob('*.py')};manifest.write_text(json.dumps(m,indent=2),encoding='utf8')
    print('Updated report.md')
if __name__=='__main__':main()
