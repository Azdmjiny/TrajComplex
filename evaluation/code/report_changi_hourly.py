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


def report(rows, audit, target, preprocessing='original'):
    from hourly_report_text import write_report
    write_report(rows, audit, target, preprocessing)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True,help='Local saved-data package; derived records are not distributed on GitHub')
    p.add_argument('--output',type=Path,required=True,help='New directory; existing outputs are never overwritten')
    p.add_argument('--preprocessing', choices=['original','position-dedup'], default='original', help='Saved input policy; use position-dedup for the current main result')
    args=p.parse_args()
    if args.output.exists(): p.error('Output already exists; choose a new directory.')
    rows,audit=validate(args.input)
    expected_tracks = 1697 if args.preprocessing=='position-dedup' else 1434
    if sum(r['n'] for r in rows) != expected_tracks:
        p.error('Saved population does not match the named frozen preprocessing policy.')
    protected={str(x.relative_to(args.input)):digest(x) for x in args.input.rglob('*') if x.is_file()}
    args.output.mkdir(parents=True)
    figures(rows,audit,args.output); report(rows,audit,args.output,args.preprocessing)
    assert all(digest(args.input/path)==h for path,h in protected.items())
    files={str(x.relative_to(args.output)):digest(x) for x in args.output.rglob('*') if x.is_file()}
    (args.output/'report-manifest.json').write_text(json.dumps(dict(new_D_calls=0,new_encoder_calls=0,new_draws=0,threshold_changes=0,windows=48,figure_sets=4,inputs_sha256=protected,outputs_sha256=files),indent=2)+'\n',encoding='utf8')
    print(f'Verified 48 hourly windows and {sum(r["attempted"] for r in rows)} saved draws; rebuilt report and four figure sets. No experiments run.')


if __name__=='__main__': main()
