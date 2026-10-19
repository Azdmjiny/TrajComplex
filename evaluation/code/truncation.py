"""Outcome-selected peak truncation: descriptive/exploratory, never confirmatory."""
import numpy as np
from scipy.stats import spearmanr

def finite_ok(p):
    return p['status']=='ok' and p['dimension'] is not None and np.isfinite(p['dimension'])

def choose_cutoff(trials, minimum_repeats=3):
    """Earliest global maximum of available-replicate mean D; no smoothing.

    A shared cutoff for every random order of the same scene. Only doses with
    at least minimum_repeats valid estimates may select the peak. This explicitly
    uses outcomes and cannot establish a validated operating range.
    """
    curves=[t['dose_curve'] for t in trials]
    if len({len(c) for c in curves})!=1:raise ValueError('Unmatched dose grids')
    means=[];counts=[]
    for k in range(len(curves[0])):
        ps=[c[k] for c in curves]
        if any(p['holding_aircraft']!=k for p in ps):raise ValueError('Unexpected dose index')
        vs=[p['dimension'] for p in ps if finite_ok(p)]
        means.append(float(np.mean(vs)) if vs else None);counts.append(len(vs))
    eligible=[k for k,n in enumerate(counts) if n>=minimum_repeats]
    cutoff=max(eligible,key=lambda k:means[k]) if eligible else None
    return dict(cutoff=cutoff,mean_D=means,n_valid_repeats=counts,minimum_repeats=minimum_repeats)

def curve_correlation(curve,key,cutoff=None):
    selected=[p for p in curve if cutoff is None or p[key]<=cutoff]
    good=[p for p in selected if finite_ok(p)]
    value=None;reason=None
    if len(good)<5:reason='fewer_than_5_valid_doses'
    elif len({p['dimension'] for p in good})<2:reason='constant_D'
    else:
        value=float(spearmanr([p[key] for p in good],[p['dimension'] for p in good]).statistic)
        if not np.isfinite(value):value=None;reason='nonfinite_correlation'
    return dict(rho=value,reason=reason,total=len(selected),valid=len(good))
