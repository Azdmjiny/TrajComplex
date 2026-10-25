"""Rebuild the 1-hour application case from saved results; never run Encoder/D.

Usage: python evaluation/code/report_changi_hourly.py --input /local/saved-package --output /new/report-dir
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

DATES = ('2026-09-08', '2026-09-11')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state(row):
    return 'ok' if row['full']['status'] == 'ok' else row['full']['reason']


def displayed_D(row):
    # Keep NA in the full 24-element series: Matplotlib breaks the line there.
    return row['full']['dimension'] if state(row) == 'ok' else float('nan')


def validate(source):
    rows = read(source / 'results/one-hour-summary.json')
    audit = read(source / 'results/background-counts.json')
    assert len(rows) == len(audit['windows']) == 48
    by_key = {x['key']: x for x in audit['windows']}
    assert len(by_key) == 48
    expected = {(d, h) for d in DATES for h in range(24)}
    assert {(r['date'], r['hour']) for r in rows} == expected
    for row in rows:
        assert row['width'] == 1 and row['n'] == by_key[row['key']]['accepted']
        a = by_key[row['key']]
        assert sum(a['stage_counts_exclusive'].values()) == a['basic_airborne_before_qc']
        assert state(row) in {'ok', 'insufficient_samples', 'poor_linear_fit'}
        cfg = row['full']['config']
        assert (cfg['min_samples'], cfg['min_r_squared'], cfg['min_fit_points'], cfg['min_pairs']) == (30, .94, 8, 10)
        assert cfg['correlation_bounds'] == [.02, .3] and cfg['min_radius_ratio'] == 2
        with gzip.open(source / 'results' / (row['key'] + '-all-attempts.json.gz'), 'rt', encoding='utf8') as f:
            attempts = json.load(f)
        assert attempts['full'] == row['full']
        values = [x['dimension'] for x in attempts['draws'] if x['status'] == 'ok']
        assert values == row['valid_draw_values'] and len(values) == row['successful']
        assert len(attempts['draws']) == row['attempted'] == (200 if row['n'] >= 30 else 0)
        assert all(x['dimension'] is None for x in [attempts['full'], *attempts['draws']] if x['status'] != 'ok')
        assert not row['show_range'] or (row['successful'] == 200 and row['distinct_subsets'] > 1)
    return rows, audit


def figures(rows, audit, target):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none'})
    directory = target / 'figures'
    directory.mkdir()
    groups = {d: sorted([x for x in rows if x['date'] == d], key=lambda x: x['hour']) for d in DATES}
    by_key = {x['key']: x for x in audit['windows']}
    colors = {'ok': '#23896c', 'insufficient_samples': '#b8bfc9', 'poor_linear_fit': '#dc8b35'}
    hours = np.arange(24)
    valid = [displayed_D(x) for x in rows if state(x) == 'ok']
    pad = max(.1, (max(valid)-min(valid))*.15)
    limits = (max(0, min(valid)-pad), max(valid)+pad)
    count_limit = max(x['basic_airborne_before_qc'] for x in audit['windows'])*1.3

    def save(fig, name):
        for ext in ('png', 'svg', 'pdf'):
            fig.savefig(directory / (name+'.'+ext), dpi=180)
        plt.close(fig)

    for day, group in groups.items():
        fig, ax = plt.subplots(3, 1, figsize=(15, 8.8), sharex=True, layout='constrained', gridspec_kw={'height_ratios': [3, 2.5, .9]})
        states = [state(x) for x in group]
        counts = Counter(states)
        fig.suptitle(f'Changi area | {day} | 1-hour windows, UTC+08\nD + aircraft count + estimability', fontsize=17)
        ax[0].plot(hours, [displayed_D(x) for x in group], 'o-', color='#236692', lw=2, ms=6)
        ax[0].set(ylabel='Accepted full-population D', ylim=limits)
        ax[0].text(.01, .97, f'{counts["ok"]}/24 estimable | NA: {counts["insufficient_samples"]} insufficient N, {counts["poor_linear_fit"]} poor fit', transform=ax[0].transAxes, va='top')
        for h, s in enumerate(states):
            if s != 'ok': ax[0].axvspan(h-.48, h+.48, color=colors[s], alpha=.14, lw=0)
        ax[1].bar(hours-.19, [by_key[x['key']]['basic_airborne_before_qc'] for x in group], width=.38, color='#ccd5e0', label='Basic airborne tracks before whole-track QC')
        ax[1].bar(hours+.19, [x['n'] for x in group], width=.38, color='#397aaa', label='Accepted tracks used by Encoder')
        ax[1].axhline(30, color='#943a3a', ls='--', lw=1.1, label='Current minimum N = 30')
        for h, x in enumerate(group): ax[1].text(h+.19, x['n']+1, str(x['n']), ha='center', fontsize=8)
        ax[1].set(ylabel='Distinct aircraft per hour', ylim=(0, count_limit))
        ax[1].legend(loc='upper left', fontsize=9, ncol=3)
        for h, s in enumerate(states): ax[2].bar(h, 1, width=.94, color=colors[s])
        ax[2].set(ylim=(0, 1), yticks=[], ylabel='Status', xlabel='Local hour (window start, UTC+08)', xlim=(-.6, 23.6))
        ax[2].set_xticks(hours, [f'{h:02}' for h in hours])
        ax[2].legend(handles=[Patch(color=colors[k], label=v) for k, v in [('ok','Estimable'), ('insufficient_samples','Insufficient accepted aircraft'), ('poor_linear_fit','Poor linear fit')]], loc='upper center', bbox_to_anchor=(.5,-.65), ncol=3, frameon=False)
        for a in ax[:2]: a.grid(axis='y', alpha=.2)
        save(fig, day+'-24h-D-count-status')

    # Supplement: original fixed-N draws, no new sampling or estimates.
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True, layout='constrained', gridspec_kw={'height_ratios':[2,2,1]})
    palette = ['#2676ae', '#cb4d35']
    for i, day in enumerate(DATES):
        g = groups[day]; a = axes[i]; color = palette[i]
        a.plot(hours, [displayed_D(x) for x in g], 's--', color='#555555', ms=3, lw=1)
        a.plot(hours, [x['conditional_median'] if x['successful']==200 else np.nan for x in g], '-', color=color)
        for x in g:
            if x['successful']:
                a.plot(x['hour'], x['conditional_median'], 'o', mec=color, mfc=color if x['successful']==200 else 'white', ms=6)
                if x['show_range']:
                    low, high = x['display_range']; med = x['conditional_median']
                    a.errorbar(x['hour'], med, yerr=[[med-low],[high-med]], fmt='none', color=color, capsize=3)
        a.set(ylabel='D', title=day+' | hollow median = conditional on successful fits')
        axes[2].plot(hours, [x['successful'] if x['attempted'] else np.nan for x in g], 'o-', color=color, label=day, ms=3)
    for a in axes:
        a.axvspan(12.5,17.5,color='#f2c36d',alpha=.16)
        a.set_xlim(-.6,23.6); a.set_xticks(hours); a.grid(axis='y',alpha=.2)
    axes[2].set(ylabel='Valid draws / 200', ylim=(-8,210), xlabel='Local hour (UTC+08)'); axes[2].legend(ncol=2)
    fig.suptitle('Supplement | fixed N=30, B=200 | existing 1-hour results\nYellow: Sep 11 hours with TS/VCTS reports; same clock hours on Sep 08',fontsize=14)
    fig.legend(handles=[Line2D([],[],color='#555555',marker='s',ls='--',label='All-aircraft D'), Line2D([],[],color=palette[0],marker='o',label='200/200 median; bars = central 95% subsampling range'),Line2D([],[],mec=palette[0],mfc='white',marker='o',ls='',label='Partial success: median only')],loc='outside lower center',ncol=1,fontsize=10)
    save(fig,'fixed-N-weather-1h')

    fig, axes = plt.subplots(1,2,figsize=(13,5),layout='constrained')
    for i, day in enumerate(DATES):
        for x in groups[day]:
            if state(x)=='ok': axes[0].scatter(x['n'],x['full']['dimension'],color=palette[i],s=30)
            if x['conditional_median'] is not None: axes[1].scatter(x['n'],x['conditional_median'],edgecolors=palette[i],facecolors=palette[i] if x['successful']==200 else 'none',s=40)
    for a in axes: a.set(xlabel='Accepted aircraft in full window',ylabel='D'); a.grid(alpha=.2)
    axes[0].set_title('All-aircraft estimates');axes[1].set_title('N=30 median; hollow = conditional on success')
    fig.suptitle('Descriptive sample-count comparison; no claim of independence from traffic volume')
    fig.legend(handles=[Line2D([],[],marker='o',ls='',color=c,label=d) for c,d in zip(palette,DATES)],loc='outside lower center',ncol=2)
    save(fig,'D-vs-N-1h')


def report(rows, audit, target):
    groups = {d: sorted([x for x in rows if x['date']==d], key=lambda x:x['hour']) for d in DATES}
    by_key = {x['key']:x for x in audit['windows']}
    lines = ['# Changi: a 24-hour real-traffic application case', '',
      'This case demonstrates hourly application and explicitly reports when D cannot be reliably estimated under the current rules. The complete 24-hour display combines accepted D, aircraft counts before and after whole-track QC, and estimability. It does not claim 24 valid D estimates or complete validation of operational complexity.', '',
      'Only 1-hour windows are presented. NA is retained, never filled with zero or interpolated, and lines do not bridge failed hours. This publication regenerates figures and text from saved results only; no training, inference, D estimation, new sampling or threshold change was performed.', '',
      '## Primary coverage', '', '| Local date | Estimable D | Insufficient accepted aircraft | Poor fit | Valid subsets / attempts | Hours with 200/200 |', '|---|---:|---:|---:|---:|---:|']
    for d,g in groups.items():
        c=Counter(state(x) for x in g)
        lines.append(f'| {d} | {c["ok"]}/24 | {c["insufficient_samples"]} | {c["poor_linear_fit"]} | {sum(x["successful"] for x in g)}/{sum(x["attempted"] for x in g)} | {sum(x["successful"]==200 for x in g)} |')
    lines += ['', '## Primary figures', '',
      'Counts before QC are distinct ICAO identifiers with basic finite airborne records, not a complete airport movement census. Counts after QC are the actual Encoder population. The study covers 100 km around Changi, including overflights and other airport traffic. Each status cell represents one hour; missing D means unavailable under these rules, not zero complexity.', '']
    for d in reversed(DATES): lines += [f'![{d}: D, aircraft count and estimability](figures/{d}-24h-D-count-status.png)', '']
    lines += ['## Frozen method', '',
      '- Strict 10-second barometric input, one full-window sequence per accepted aircraft, frozen epoch-90 9-feature Encoder, training normalization and sum pooling. Checkpoint SHA-256: `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`.',
      '- Minimum 30 aircraft, 8 fitting scales, 10 pairs, C(r) in [0.02, 0.3], radius ratio >=2, R²>=0.94. These are the saved case-study gates, not a retrospective relaxation of historical 0.98 maneuver results.',
      '- A shared 64-radius logarithmic grid (0.21153999267980197 to 377.183110301039), built from positive within-window distances across all 24 September 11 populations, including low-N hours, and saved before D. Both days and all subsets use it. Eligible regression scales can still vary by population.',
      '- Fixed N=30; exactly B=200 subsets without replacement within each draw for every eligible hour. Repeated subsets are permitted; failed draws are not replaced. There are 6,200 saved draws across 31 eligible hours.', '',
      '## Why some hours are unavailable', '',
      'The full-population results have 17 insufficient-N hours and 6 poor-fit hours. Every computed full-population and subset fit met the scale-count and radius-span gates; fit failures occur at the R² gate. This does not establish that the shared grid is optimal or that physical traffic lacks a geometric dimension. Changing plot ticks or distance units cannot remove curvature in the log-correlation curve.', '',
      'Whole-track QC rejects an entire aircraft-hour at its first failure. Source auditing found 849 first rejections for non-advancing position time across both days: all were repeated timestamps with unchanged coordinates, not backward timestamps. Of those, 565 also have excessive position age or gaps between distinct position observations; 284 have no such additional time flags. The latter are NOT accepted or recovered tracks: downstream checks have not been established under a different observation-stream treatment. This conservative policy can reduce availability. It remains unchanged in the reported results.', '',
      '| First screening outcome (aircraft-hours) | September 8 | September 11 |', '|---|---:|---:|']
    counts={d:Counter() for d in DATES}
    for x in audit['windows']: counts[x['date']].update(x['stage_counts_exclusive'])
    for key in sorted(set().union(*counts.values())): lines.append(f'| {key} | {counts[DATES[0]][key]} | {counts[DATES[1]][key]} |')
    lines += ['', '## Supplement: fixed N and weather comparison', '',
      'Fixed-N results retain time variation but often depend on which subsets pass. Partial-success medians are conditional and shown hollow without a range or continuous median curve. A central 95% subsampling range is shown only for 200/200 valid draws with more than one distinct subset; it is not a bootstrap confidence interval. At September 11 12:00, N=30 yields the same subset on all 200 draws, so this is not resampling robustness.', '',
      'September 11 is the thunderstorm day and September 8 the clearer-weather comparator. Independent WSSS TS/VCTS reports occur in September 11 clock bins 13–17; shading does not identify exact continuous storm boundaries. The comparison has mixed directions: at 14:00 the event-day fixed-N median is lower (both 200/200); at 15:00–17:00 it is higher, with some partial-success hours. At 13:00 the control full fit fails and only 10/200 subsets pass. No storm-caused increase, wind-shear detection, or universal positive association is established.', '',
      'Weather evidence: [WSSS archive provider](https://mesonet.agron.iastate.edu/request/download.phtml?network=SG__ASOS) and [Meteorological Service Singapore retrospective](https://www.weather.gov.sg/more-showers-expected-in-the-coming-fortnight/). The local evidence summary records the archived observations; absence of a weather code is not proof that no adverse weather occurred.', '',
      '![Fixed-N and weather supplement](figures/fixed-N-weather-1h.png)', '', '![D versus aircraft count](figures/D-vs-N-1h.png)', '',
      '## Every hour retained', '',
      '| Date | Hour | Before QC | Accepted | D | Status | Valid / attempted draws | Conditional median |', '|---|---:|---:|---:|---:|---|---:|---:|']
    def value(x): return 'NA' if x is None else f'{x:.3f}'
    for d,g in groups.items():
        for x in g: lines.append(f'| {d} | {x["hour"]:02} | {by_key[x["key"]]["basic_airborne_before_qc"]} | {x["n"]} | {value(x["full"]["dimension"])} | {state(x)} | {x["successful"]}/{x["attempted"]} | {value(x["conditional_median"])} |')
    lines += ['', '## Interpretation and publication limits', '',
      'Suitable claim: the case demonstrates an auditable hourly application to observed airport-area traffic and makes estimator availability explicit. It does not establish a complete reliable day/night D pattern, independence from traffic count, causal weather sensitivity, or general operational-complexity validity.', '',
      'Fixed N controls count, not route composition, trajectory duration or data availability. The dates differ in weekday. Subsets are dependent within-hour draws, not independent days; aircraft may recur across hours. September 11 input sequences reach 357 samples versus 298 in the prepared training data; no new length cutoff was applied.', '',
      'Reproduction: use `python evaluation/code/report_changi_hourly.py --input LOCAL_SAVED_PACKAGE --output NEW_DIRECTORY` from the repository root. The saved input package is retained locally and is not distributed on GitHub. The command verifies saved records and regenerates this report and four figure sets without Encoder/D calls. Source results remain immutable. The run package README documents the local input requirements.']
    (target/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True,help='Local saved-data package; derived records are not distributed on GitHub')
    p.add_argument('--output',type=Path,required=True,help='New directory; existing outputs are never overwritten')
    args=p.parse_args()
    if args.output.exists(): p.error('Output already exists; choose a new directory.')
    rows,audit=validate(args.input)
    protected={str(x.relative_to(args.input)):digest(x) for x in args.input.rglob('*') if x.is_file()}
    args.output.mkdir(parents=True)
    figures(rows,audit,args.output); report(rows,audit,args.output)
    assert all(digest(args.input/path)==h for path,h in protected.items())
    files={str(x.relative_to(args.output)):digest(x) for x in args.output.rglob('*') if x.is_file()}
    (args.output/'report-manifest.json').write_text(json.dumps(dict(new_D_calls=0,new_encoder_calls=0,new_draws=0,threshold_changes=0,windows=48,figure_sets=4,inputs_sha256=protected,outputs_sha256=files),indent=2)+'\n',encoding='utf8')
    print('Verified 48 hourly windows and 6200 saved draws; rebuilt report and four figure sets. No experiments run.')


if __name__=='__main__': main()
