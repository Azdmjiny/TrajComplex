"""Render archived corrected 10-second midpoint Holding results only.

No inference, D estimation, new cutoff selection or source-data modification.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

ROOT = EVALUATION_ROOT
COLORS = ['#1683b5', '#d58b29', '#239b80', '#c579a5', '#8675b5']
NAVY = '#203f53'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def label(s):
    return (datetime.strptime(s['scene_id'], '%Y-%m-%dT%HZ') + timedelta(hours=8)).strftime('%b %d, %H:00')


def render(out):
    source = study_path('strict-10s-reference/results')
    files = [source/x for x in ['experiment-results.json', 'summary.json', 'analysis-manifest.json', 'run-manifest.json']]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in files}
    raw, summary, analysis, manifest = [json.loads(p.read_text(encoding='utf8')) for p in files]
    runs = raw['qc500']['holding']['scenes']
    summary = summary['qc500']['holding']
    scenes = summary['scenes']
    selected = [s for s in scenes if s['cutoff'] is not None]
    baseline = [s for s in selected if s['baseline_ok']]
    lookup = {(r['scene'], r['replicate']): r for r in summary['curves']}
    assert len(scenes) == 12 and len(selected) == 7 and len(baseline) == 3
    assert summary['all']['retained']['positive'] == 32
    assert summary['all']['retained']['n'] == 33
    arrays = {}
    for s in scenes:
        rr = sorted([r for r in runs if r['scene_id'] == s['scene_id']], key=lambda r: r['replicate'])
        x = np.array([p['holding_aircraft'] for p in rr[0]['dose_curve']])
        y = np.array([[p['dimension'] if p['status'] == 'ok' else np.nan for p in r['dose_curve']] for r in rr], float)
        assert y.shape == (5, len(x))
        mean = np.array([np.mean(v[np.isfinite(v)]) if np.isfinite(v).any() else np.nan for v in y.T])
        saved = np.array([np.nan if v is None else v for v in s['peak']['mean_D']], float)
        assert np.allclose(mean, saved, equal_nan=True)
        for r in rr:
            for kind in ['full', 'retained']:
                if kind == 'retained' and s['cutoff'] is None:
                    continue
                valid = sum(p['status'] == 'ok' for p in r['dose_curve'] if kind == 'full' or p['holding_aircraft'] <= s['cutoff'])
                assert valid == lookup[s['scene_id'], r['replicate']][kind]['valid']
        arrays[s['scene_id']] = x, y, mean

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#b2bec7', 'axes.labelcolor': NAVY,
                         'xtick.color': '#526472', 'ytick.color': '#526472',
                         'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    handles = [Line2D([], [], marker='o', color=c, lw=.7, ms=4, label=f'Order {i+1}') for i, c in enumerate(COLORS)]
    handles += [Line2D([], [], color=NAVY, lw=2.5, label='Mean of available orders'),
                Line2D([], [], color='#78838c', marker='x', ls='', ms=4, label='Rejected D fit (bottom marks)')]

    def panel(ax, s, delta=False, full=False, tag=''):
        x, ys, mean = arrays[s['scene_id']]
        mask = np.ones(len(x), bool) if full else x <= s['cutoff']
        x, ys, mean = x[mask], ys[:, mask], mean[mask]
        offset = s['baseline_D'] if delta else 0
        ys, mean = ys-offset, mean-offset
        for k, (y, c) in enumerate(zip(ys, COLORS)):
            ax.plot(x, y, color=c, lw=.65, alpha=.4)
            ax.scatter(x, y, color=c, s=15, alpha=.8, linewidths=0, zorder=3)
            bad = ~np.isfinite(y)
            ax.plot(x[bad], np.full(bad.sum(), .018+k*.014), marker='x', ls='', color=c,
                    ms=2.4, mew=.6, transform=ax.get_xaxis_transform(), alpha=.6)
        ax.plot(x, mean, color=NAVY, lw=2.4, zorder=4)
        if delta:
            ax.axhline(0, color='#7f919d', ls='--', lw=.8)
        if full and s['cutoff'] is not None:
            ax.axvline(s['cutoff'], color='#748796', ls='--', lw=.8)
        key = 'full' if full else 'retained'
        rho = s[key]['median']
        rho_text = 'NA' if rho is None else f'{rho:.3f}'
        count = int(np.isfinite(ys).sum())
        end_text = f'full range 0–{s["n_aircraft"]}' if full else f'archived range 0–{s["cutoff"]}'
        ax.set_title(f'{tag}{label(s)} | N = {s["n_aircraft"]}\n{end_text}; median order ρ = {rho_text}', loc='left', fontsize=10.5, pad=12, color=NAVY)
        ax.text(.02, .97, f'Accepted fits: {count}/{ys.size}' + ('' if delta else f'  |  baseline {"accepted" if s["baseline_ok"] else "NA"}'),
                transform=ax.transAxes, va='top', fontsize=8.3, color='#526472')
        ax.set(xlabel='Injected Holding aircraft', ylabel='D − baseline D' if delta else 'Estimated D', xlim=(-.3, max(x)+.3))
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.grid(axis='y', alpha=.22, lw=.6)
        if not np.isfinite(ys).any():
            ax.text(.5, .5, 'D unavailable at every dose', transform=ax.transAxes, ha='center', fontsize=10, color='#61717d')
        return ys

    def save(fig, name):
        for ext in ['png', 'pdf', 'svg']:
            fig.savefig(out/f'{name}.{ext}', dpi=240, facecolor='white')
        plt.close(fig)

    def footer(fig, y, text):
        fig.text(.055, y, text, fontsize=9, color='#526472')

    # Main delta response: all and only scenes with an accepted baseline.
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.8), sharey=True)
    fig.subplots_adjust(left=.055, right=.985, top=.69, bottom=.27, wspace=.19)
    fig.suptitle('Holding: response within archived pre-peak ranges', x=.055, y=.965, ha='left', fontsize=21, fontweight='bold', color=NAVY)
    footer(fig, .91, 'Corrected 10-second midpoint injection • +240 seconds • all 3 scenes with an accepted baseline • times UTC+08')
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.05, .87), ncol=4, frameon=False, fontsize=9.5)
    values = [panel(ax, s, delta=True, tag=f'{chr(65+i)}  ') for i, (ax, s) in enumerate(zip(axes, baseline))]
    finite = np.concatenate([v[np.isfinite(v)] for v in values]); lo, hi = min(0, finite.min()), finite.max()
    for ax in axes:
        ax.set_ylim(lo-.15*(hi-lo), hi+.25*(hi-lo))
    footer(fig, .16, 'Hour-based source selection; injected trajectories retain their complete tails and may extend beyond the source hour.')
    footer(fig, .115, 'Cutoffs are inherited outcome-selected peaks (included), not validated operating limits. Full ranges and unavailable scenes appear in the companion report.')
    footer(fig, .07, 'No smoothing or new D fits. Missing values break lines. Means use available orders; R² ≥ 0.98 unchanged. Equal-duration control is reported separately.')
    footer(fig, .025, 'Baseline-valid subset: 14/15 positive order coefficients, median ρ = 0.800. Orders are dependent repeats; the response is not uniformly monotonic.')
    save(fig, 'holding-midpoint-prepeak-delta')

    fig, axes = plt.subplots(2, 4, figsize=(18.5, 11))
    fig.subplots_adjust(left=.055, right=.985, top=.79, bottom=.17, hspace=.52, wspace=.3)
    fig.suptitle('Holding: all archived pre-peak ranges', x=.055, y=.97, ha='left', fontsize=23, fontweight='bold', color=NAVY)
    footer(fig, .927, 'Corrected 10-second midpoint results • all 7 cutoff-available scenes • absolute D; no imputed baseline • times UTC+08')
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.05, .9), ncol=4, frameon=False, fontsize=10)
    for i, (ax, s) in enumerate(zip(axes.flat, selected)):
        yy = panel(ax, s, tag=f'{chr(65+i)}  ')
        good = yy[np.isfinite(yy)]; lo, hi = good.min(), good.max(); span=max(hi-lo, .05)
        ax.set_ylim(lo-.17*span, hi+.26*span)
    ax = axes.flat[-1]
    missing = []
    for i, s in enumerate(selected):
        for k, c in enumerate(COLORS):
            rho = lookup[s['scene_id'], k]['retained']['rho']
            if rho is None:
                missing.append(f'{chr(65+i)}{k+1}')
            else:
                ax.scatter(i+(k-2)*.09, rho, s=26, color=c, zorder=4)
        ax.hlines(s['retained']['median'], i-.28, i+.28, color=NAVY, lw=2)
    ax.axhline(0, ls='--', lw=.8, color='#7f919d')
    ax.set(ylim=(-1.12, 1.12), xlim=(-.6, 6.6), xticks=range(7), xticklabels=list('ABCDEFG'), ylabel='Spearman ρ', xlabel='Scene panels A–G')
    ax.set_title('H  Every retained-range coefficient\n32/33 positive; median ρ = 0.845', loc='left', fontsize=10.5, color=NAVY, pad=12)
    ax.text(.03, .06, '1 negative coefficient retained\n2/35 orders NA: '+', '.join(missing), transform=ax.transAxes, fontsize=8.5)
    ax.grid(axis='y', alpha=.22)
    footer(fig, .105, 'Hour-based source selection; complete injected tails retained. Historical cutoffs are outcome-selected; no claim of a validated operating limit.')
    footer(fig, .075, 'All 12 planned scenes and full ranges are retained in the report. Four displayed scenes have no accepted baseline; these panels show absolute D.')
    footer(fig, .045, 'Panel y-scales differ. Available-order means are descriptive; order correlations use each order’s valid doses. Missing values break lines; no smoothing.')
    footer(fig, .015, 'R² ≥ 0.98 unchanged. Five orders share the same aircraft and are not independent scenes. Equal-duration control remains separate evidence.')
    save(fig, 'holding-midpoint-prepeak-all-scenes')

    fig, axes = plt.subplots(4, 3, figsize=(16, 18), sharey=True)
    fig.subplots_adjust(left=.055, right=.985, top=.85, bottom=.09, hspace=.57, wspace=.23)
    fig.suptitle('Holding appendix: all 12 scenes and complete dose ranges', x=.055, y=.975, ha='left', fontsize=21, fontweight='bold', color=NAVY)
    footer(fig, .945, 'Corrected 10-second midpoint results • same common D scale • times UTC+08 • dashed lines mark archived cutoffs')
    fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(.05, .927), ncol=4, frameon=False)
    for i, (ax, s) in enumerate(zip(axes.flat, scenes)):
        panel(ax, s, full=True, tag=f'{i+1}  ')
    allfinite=np.concatenate([v[1][np.isfinite(v[1])] for v in arrays.values()]);lo,hi=allfinite.min(),allfinite.max()
    for ax in axes.flat:
        ax.set_ylim(lo-.15*(hi-lo), hi+.25*(hi-lo))
    footer(fig, .045, 'Full-range correlations: 25/35 positive; median ρ = 0.220. Rejected fits are bottom marks, not zero-valued dimensions.')
    footer(fig, .022, 'Source-hour aircraft selection only; complete synthetic tails are retained. No new estimation, sample selection, cutoff selection or threshold change.')
    save(fig, 'holding-midpoint-full-range-appendix')

    rows = []
    for s in scenes:
        fmt = lambda x: 'NA' if x is None else f'{x:.3f}'
        rows.append(f'| {s["scene_id"]} | {label(s)} | {s["n_aircraft"]} | {fmt(s["baseline_D"])} | {s["cutoff"] if s["cutoff"] is not None else "NA"} | {s["retained"]["n"]} | {fmt(s["retained"]["median"])} | {fmt(s["full"]["median"])} |')
    report = '''# Corrected 10-second midpoint Holding: archived pre-peak response

Rendered 2026-10-27 from existing QC500 results only. No Encoder calls, D fits, sampling, new cutoffs or threshold changes. The original experiment and terminal equal-duration results remain unchanged.

## Exact experimental scope

Aircraft were selected from a natural-hour source file. A corrected 240-second racetrack was inserted at each selected trajectory's midpoint; the original tail was retained. The injected trajectory was **not clipped back to the hour boundary**. These results describe hour-selected synthetic trajectories, not traffic confined to an unchanged natural hour after injection. The input interval is 10 seconds; the frozen epoch-90 Encoder has 9 input features and a 16-dimensional output embedding.

The archived peak is the earliest maximum of the scene's available-order mean D with at least three accepted orders. It is shared by five orders and included in the plotted range. It was selected from outcomes, not independently specified or validated as an operational limit. This renderer never searches for a new peak.

## Main response: accepted baselines only

![Midpoint pre-peak change relative to baseline](figures/holding-midpoint-prepeak-delta.png)

[Vector PDF](figures/holding-midpoint-prepeak-delta.pdf) · [SVG](figures/holding-midpoint-prepeak-delta.svg)

All three scenes with an accepted baseline are shown. Subtracting a scene's constant baseline changes the vertical origin, not its order correlations. Within these archived ranges, 14/15 order coefficients are positive (median 0.800); one negative remains. The same shared vertical scale is used in all three panels. The short September 26 range is not extended to make it resemble the other panels.

## Complete pre-peak inventory

![All seven available midpoint ranges and every coefficient](figures/holding-midpoint-prepeak-all-scenes.png)

[Vector PDF](figures/holding-midpoint-prepeak-all-scenes.pdf) · [SVG](figures/holding-midpoint-prepeak-all-scenes.svg)

All seven scenes with an archived cutoff are included. Four lack an accepted baseline, so this overview uses absolute D. Across 35 planned orders, 33 coefficients are estimable: 32 positive and one negative, with median 0.845. Two orders remain NA. All seven scene median coefficients are positive. This does not mean each curve is monotonic or that every extra aircraft increases D. Panel-specific vertical scales are labelled and should not be used to compare effect magnitudes visually.

Colored points are accepted order-dose estimates. Thin lines and the dark available-order mean are unsmoothed and break at missing estimates. Bottom crosses mark failed fits on a separate axes-coordinate strip, not D=0. The set of contributing orders can change with dose; the dark line is descriptive, not a fixed-cohort estimate or a confidence interval. Coefficients are calculated per order from archived accepted doses, not from the dark line. The original R² ≥ 0.98 gate remains unchanged.

## Full ranges and unavailable scenes

![All midpoint scenes with complete dose ranges](figures/holding-midpoint-full-range-appendix.png)

[Vector PDF](figures/holding-midpoint-full-range-appendix.pdf)

Across the full ranges, 25/35 computable order coefficients are positive and the median is 0.220. On the same 33 orders used for the retained-range comparison, the full-range median is also 0.220 (24 positive). The strong pre-peak association is range-dependent. Five of 12 planned scenes have no archived cutoff and are not silently removed from this inventory.

| Source hour (UTC) | Local time (UTC+08) | N | Baseline D | Saved cutoff | Estimable pre-peak orders | Median pre-peak rho | Median full rho |
|---|---|---:|---:|---:|---:|---:|---:|
''' + '\n'.join(rows) + '''

## Interpretation for the paper

Suggested wording: “For the corrected 10-second midpoint Holding stimulus, the archived pre-peak ranges showed predominantly positive dose–dimension associations (32 of 33 computable order coefficients positive; median Spearman rho 0.845). The three scenes with accepted baselines also showed predominantly positive associations (14/15; median 0.800). These exploratory results are conditional on outcome-selected ranges and estimation gates; they do not establish a globally monotonic response or an independently validated operating range.”

Holding adds both geometry and duration. The [terminal equal-duration control](holding-paper-appendix.md) remains relevant evidence: straight continuation also increases D in many cases. Its midpoint-derived cutoff comparison gave matched-order medians 0.661 for endpoint Holding and 0.598 for straight continuation. Because insertion position differs, that comparison does not quantify the exact length contribution to this midpoint experiment. Do not treat it as a matched midpoint control or claim the midpoint response is entirely caused by turning geometry.

The complete evidence supports sensitivity of this representation and dimension estimate to this synthetic intervention within the displayed ranges. It does not by itself establish operational workload validity, universal superiority, or that a downward response is caused by exceeding a physical controllability limit. Five orders reuse aircraft and are dependent; no confirmatory p-values or confidence intervals are claimed.

## Reproducibility

- [Renderer](code/plot_holding_midpoint_response.py): accepts a new output directory and refuses overwriting an existing render.
- [Saved experiment](runs/strict-10s-reference/results/experiment-results.json), [saved summary](runs/strict-10s-reference/results/summary.json), [archived cutoff rule](runs/strict-10s-reference/results/analysis-manifest.json).
- [Version comparison](holding-version-comparison.md): original 5-second pilot, corrected midpoint experiment and endpoint control are distinct.
- The local render manifest stores source hashes and zero counts for new inference/estimation/cutoff selection. Source hashes are checked again after rendering.
'''
    (out/'holding-midpoint-response.md').write_text(report, encoding='utf8')
    assert all(sha(ROOT/p)==h for p,h in hashes.items())
    (out/'render-manifest.json').write_text(json.dumps(dict(source_sha256=hashes, new_encoder_calls=0, new_D_calls=0,
        new_draws=0, changed_cutoffs=0, changed_thresholds=0, baseline_scenes=[s['scene_id'] for s in baseline],
        cutoff_scenes=[s['scene_id'] for s in selected], unavailable_orders=missing,
        figure_sha256={p.name: sha(p) for p in out.iterdir() if p.suffix in ['.pdf', '.svg', '.png']}), indent=2)+'\n', encoding='utf8')
    print('Rendered 3 baseline-valid scenes, 7 archived ranges, all 12 full-range scenes. Source hashes unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output directory; existing artifacts are protected.')
    args.output.mkdir(parents=True)
    render(args.output)
