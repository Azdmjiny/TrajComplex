"""Version-aware text for the two frozen hourly evidence packages."""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
from collections import Counter


def write_report(rows, audit, target, preprocessing):
    def state(x): return 'ok' if x['full']['status']=='ok' else x['full']['reason']
    def fmt(x): return 'NA' if x is None else f'{x:.3f}'
    days=sorted({r['date'] for r in rows})
    groups={d:sorted([r for r in rows if r['date']==d],key=lambda r:r['hour']) for d in days}
    bykey={x['key']:x for x in audit['windows']}
    totals=Counter(state(x) for x in rows)
    attempts=sum(x['attempted'] for x in rows)
    mode='Position-deduplicated main result' if preprocessing=='position-dedup' else 'Original frozen result (appendix comparator)'
    lines=['# Changi: a 24-hour real-traffic application case','',f'**{mode}.** Both dates, all 24 clock hours, and all three schemes are retained. This presentation reads saved results only; no Encoder call, D estimate, new sampling or threshold change is made.','',
        'The complete display combines accepted D, aircraft counts before/after QC, and estimability. It demonstrates hourly application and explicit limits; it does not claim 24 valid estimates. NA is never zero or interpolated, and lines do not bridge failed hours.','',
        '## Coverage','', '| Date (UTC+08) | Valid D | Insufficient N | Poor fit | Valid subsets / attempts | Hours with 200/200 |','|---|---:|---:|---:|---:|---:|']
    for day,g in groups.items():
        c=Counter(state(r) for r in g)
        lines.append(f'| {day} | {c["ok"]}/24 | {c["insufficient_samples"]} | {c["poor_linear_fit"]} | {sum(r["successful"] for r in g)}/{sum(r["attempted"] for r in g)} | {sum(r["successful"]==200 for r in g)} |')
    if preprocessing=='position-dedup':
        lines += ['', '## Why this is the main result', '',
          'Only repeated horizontal observations with exactly the same position-update timestamp and latitude/longitude are collapsed. All altitude snapshots, age checks and gap checks remain. Backward timestamps, conflicting equal-time coordinates and unsupported intervals still reject the track. There is no new gap filling, extrapolation or relaxed gate; the existing bounded 10-second resampling is unchanged.', '',
          'The saved validation recovered 263 aircraft-hours (136 on September 8, 127 on September 11). All 1,434 original accepted trajectory arrays and embeddings were verified bitwise unchanged. Of 849 former repeated-timestamp first rejections, 565 still fail the distinct-position gap rule and 21 fail the minimum grid length. Aircraft-hours are not unique aircraft over two days.', '',
          'The frozen grid is reused exactly. Larger aircraft pools change both the point cloud and eligible regression scales. Identical seed/draw numbers do not imply matched aircraft subsets between versions. The change is justified by observation handling, not by choosing a more positive result. Fixed-N stability does not uniformly improve.']
    else:
        lines += ['', '## Original observation handling', '',
          'The original whole-track policy rejects repeated position timestamps. Its source audit found 849 such first rejections, all unchanged coordinates rather than backward clocks; 565 also had age/gap flags. The remaining 284 were not accepted by this original run. This report preserves that policy as the historical comparator.']
    lines += ['', '## Main figures', '', 'The area is within 100 km of Changi and includes overflights and traffic from other airports. Before-QC counts are distinct ICAO identifiers with basic airborne fields, not a complete count of Changi arrivals/departures.', '']
    for day in reversed(days): lines += [f'![{day}: accepted D, aircraft and status](figures/{day}-24h-D-count-status.png)', '']
    lines += ['## Frozen method', '',
        '- Strict 10-second barometric input, one full-window sequence per aircraft, frozen epoch-90 9-feature Encoder, training normalization and sum pooling. Checkpoint SHA-256: `bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976`.',
        '- N>=30, >=8 fitting scales, >=10 pairs, C(r) in [0.02,0.3], radius ratio>=2, R²>=0.94. These saved gates differ from the historical Holding control, which used R²>=0.98.',
        '- Exactly the original 64-radius log grid, from 0.21153999267980197 to 377.183110301039. Originally constructed from within-window positive distances across the 24 September 11 populations, including low-N hours. It is not rebuilt after deduplication. Eligible regression scales can still differ across populations.',
        f'- N=30, B=200; uniform sampling without replacement within a draw. The saved package contains {attempts:,} draws across {sum(r["attempted"]>0 for r in rows)} eligible hours. Failed draws are never replaced.', '',
        '## Unavailable estimates and screening', '',
        f'There are {totals["insufficient_samples"]} insufficient-N and {totals["poor_linear_fit"]} poor-fit hours. NA means unavailable under these rules, not zero complexity. A poor linear fit does not establish that physical traffic has no geometric dimension.', '',
        '| First screening outcome (aircraft-hours) | September 8 | September 11 |','|---|---:|---:|']
    counts={d:Counter() for d in days}
    for r in audit['windows']: counts[r['date']].update(r['stage_counts_exclusive'])
    for key in sorted(set().union(*counts.values())):lines.append(f'| {key} | {counts[days[0]][key]} | {counts[days[1]][key]} |')
    lines += ['', '## Scheme 2: fixed-N supplement', '',
        'Partial-success medians are conditional on accepted subsets, shown hollow without a range or joined median curve. A central 95% subsampling range is shown only when all 200 draws pass and more than one distinct subset is present. It is not a bootstrap confidence interval. The same aircraft subset on every draw is not evidence of robustness to aircraft composition.','']
    for r in rows:
        if r['successful']==200 and r['distinct_subsets']==1: lines.append(f'- {r["date"]} {r["hour"]:02}:00: all 200 draws are the same subset (N={r["n"]}).')
    lines += ['', '![Fixed-N and weather supplement](figures/fixed-N-weather-1h.png)', '',
        '## Scheme 3: independently selected weather comparison', '',
        'September 11 is the thunderstorm day; September 8 is the clearer-weather comparator. WSSS TS/VCTS observations identify September 11 clock bins 13–17; shading is not an exact continuous storm boundary. Mixed signs are retained. No causal weather effect, wind-shear detection, or general positive association is established.', '',
        '| Hour | Event minus control full D | Event minus control subset median | Valid control / event draws |','|---|---:|---:|---|']
    for hour in range(13,18):
        a,b=[next(r for r in groups[d] if r['hour']==hour) for d in days]
        def diff(key):return None if a[key] is None or b[key] is None else b[key]-a[key]
        fd=None if state(a)!='ok' or state(b)!='ok' else b['full']['dimension']-a['full']['dimension']
        lines.append(f'| {hour}:00 | {fmt(fd)} | {fmt(diff("conditional_median"))} | {a["successful"]}/200 ; {b["successful"]}/200 |')
    lines += ['', 'Weather sources: [WSSS archive provider](https://mesonet.agron.iastate.edu/request/download.phtml?network=SG__ASOS) and [Meteorological Service Singapore retrospective](https://www.weather.gov.sg/more-showers-expected-in-the-coming-fortnight/). Absence of a code does not prove absence of adverse weather.', '',
        '![D versus accepted aircraft](figures/D-vs-N-1h.png)', '',
        '## All 48 hourly records', '', '| Date | Hour | Before QC | Accepted | D | Status | Valid / attempted draws | Conditional median |','|---|---:|---:|---:|---:|---|---:|---:|']
    for day,g in groups.items():
        for r in g: lines.append(f'| {day} | {r["hour"]:02} | {bykey[r["key"]]["basic_airborne_before_qc"]} | {r["n"]} | {fmt(r["full"]["dimension"])} | {state(r)} | {r["successful"]}/{r["attempted"]} | {fmt(r["conditional_median"])} |')
    lines += ['', '## What the paper can claim', '',
        'This is an auditable real-traffic application with explicit estimator availability. It does not prove a complete reliable day/night D curve, independence from traffic count, causal storm sensitivity or general operational-complexity validity. Fixed N controls count, not composition, duration or observation availability. The two days differ in weekday; subsets are dependent, and aircraft may recur across hours. September 11 sequences reach 357 samples versus 298 in the prepared training data; no new length gate was applied.', '',
        f'Rebuild with `python evaluation/hourly/code/report_changi_hourly.py --input LOCAL_SAVED_PACKAGE --preprocessing {preprocessing} --output NEW_DIRECTORY`. Full saved attempts, embeddings, draw assignments, QC evidence and manifests remain local. Only code, reviewed reports and figures are publication artifacts.']
    (target/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
