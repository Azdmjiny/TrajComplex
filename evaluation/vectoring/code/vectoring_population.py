"""Prepare one fixed 10-second scene population before any dose calculation.

Basic-QC tracks are never removed by candidate-only gates. Failed fitting keeps
the original background; successful fitting fixes the paired baseline before
direction/route checks. A route failure never switches that baseline back.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
from dataclasses import dataclass
from collections import Counter
import hashlib
import numpy as np
import vectoring_path as path
from vectoring_reference import fit_track, maneuver_reference
from vectoring_inputs import llh_to_enu
from vectoring_uncertainty import quality_radii
from position_timeline import position_grid
from run_vectoring_eval import _check_deformed_kinematics, VectoringRejected

# 2026-10-25 active shape: piecewise-straight vectoring stimulus. Set False to
# restore the smooth minimum-jerk control.
SEGMENTED=True


def array_hash(a):
    a = np.ascontiguousarray(a, dtype='<f8')
    return hashlib.sha256(a.tobytes()).hexdigest()


@dataclass
class PreparedPopulation:
    baseline: dict
    injections: dict
    records: list

    def dose(self, assignments):
        """Pure replacement from a frozen baseline; never re-fit at each dose."""
        out = {k: v.copy() for k,v in self.baseline.items()}
        seen = set()
        for aircraft, side in assignments:
            if aircraft in seen:
                raise ValueError('duplicate injection assignment')
            if side not in (-1,1) or aircraft not in self.injections:
                raise ValueError('ineligible injection assignment')
            out[aircraft] = self.injections[aircraft][side].copy()
            seen.add(aircraft)
        return out


def prepare_population(tracks, sources, quality, *, progress=None):
    baseline = {}; injections = {}; records = []
    for aircraft in sorted(tracks):
        original = np.asarray(tracks[aircraft], float)
        if original.ndim != 2 or original.shape[1] != 3 or not np.isfinite(original).all():
            raise ValueError('prepare_population requires finite basic-QC tracks')
        p = original.copy()
        record = dict(icao24=aircraft, basic_pass=True, length_qualified=len(p)>=63,
                      full_quality_pass=False, fit_attempted=False, fit_success=False,
                      reference_pass=False, injectable=False, baseline_version='original',
                      rejection_reasons=[], original_sha256=array_hash(original),
                      grid_points=len(p), side_diagnostics={})
        raw = sources[aircraft]
        grid = position_grid(raw, sample_s=10)
        if len(grid) != len(p):
            raise ValueError('source/grid population mismatch')
        record['grid_sha256'] = array_hash(grid)
        fit = None
        if not record['length_qualified']:
            record['rejection_reasons'] = ['missing_maneuver_join_support']
        else:
            radii, errors = quality_radii(raw, range(len(raw)), quality.get(aircraft))
            record['full_quality_pass'] = not errors
            if errors:
                record['rejection_reasons'] = errors
            else:
                record['fit_attempted'] = True
                detail = {}; record['fit_diagnostics'] = detail
                try:
                    xy = llh_to_enu(raw[:,1],raw[:,2],raw[:,3])[:,:2]
                    fit = fit_track(xy, raw[:,4], radii, detail)
                    fitted_xy = fit.positions(grid)
                    if not np.isfinite(fitted_xy).all():
                        raise path.PathRejected('nonfinite_fitted_grid')
                    # A changed background must still satisfy the same basic
                    # horizontal-speed QC; no new flight limit is introduced.
                    fitted_speed = float(np.max(np.linalg.norm(np.diff(fitted_xy,axis=0),axis=1)/10))
                    detail['fitted_grid_maximum_horizontal_speed_m_s'] = fitted_speed
                    if fitted_speed > path.MAX_SPEED:
                        raise path.PathRejected('fitted_grid_horizontal_speed_over_500_m_s')
                    p[:,:2] = fitted_xy
                    record['fit_success'] = True
                    record['baseline_version'] = 'full_track_fit'
                except (path.PathRejected, np.linalg.LinAlgError, FloatingPointError) as exc:
                    record['rejection_reasons'] = [str(exc)]
                    fit = None
        # Freeze baseline BEFORE route feasibility. No candidate gate below
        # changes membership or replaces this version with the raw trajectory.
        p.setflags(write=False); baseline[aircraft] = p
        record['baseline_sha256'] = array_hash(p)
        if fit is not None:
            start = (len(p)-60)//2; end = start+61
            ref_detail = {}; record['reference_diagnostics'] = ref_detail
            try:
                reference = maneuver_reference(fit, grid, start, ref_detail)
                record['reference_pass'] = True
            except (path.PathRejected, np.linalg.LinAlgError, FloatingPointError) as exc:
                record['rejection_reasons'] = ref_detail.get('rejection_reasons',[str(exc)])
            else:
                accepted = {}
                for side in (-1,1):
                    side_detail = {}; record['side_diagnostics'][str(side)] = side_detail
                    try:
                        xy = (path.generate_segmented(reference, side, side_detail, sample_s=10)
                              if SEGMENTED else path.generate(reference, side, side_detail, sample_s=10))
                        if xy.shape != (61,2) or not np.isfinite(xy).all():
                            raise path.PathRejected('invalid_generated_grid')
                        q = p.copy(); q[start:end,:2] = xy
                        if not SEGMENTED:
                            _check_deformed_kinematics(p[start-1:end+1], q[start-1:end+1], sample_s=10)
                        if not (np.array_equal(q[:,2],p[:,2]) and np.array_equal(q[:start],p[:start]) and np.array_equal(q[end:],p[end:])):
                            raise RuntimeError('paired trajectory invariance failed')
                        q.setflags(write=False); accepted[side] = q
                        side_detail['accepted'] = True
                    except (path.PathRejected,VectoringRejected,np.linalg.LinAlgError,FloatingPointError) as exc:
                        side_detail.update(accepted=False,rejection_reason=str(exc))
                        record['rejection_reasons'].append(str(exc))
                if len(accepted)==2:
                    injections[aircraft] = accepted
                    record['injectable'] = True
        record['rejection_reasons'] = sorted(set(record['rejection_reasons']))
        record['background_only'] = not record['injectable']
        assert np.array_equal(p[:,2],original[:,2])
        records.append(record)
        if progress is not None: progress(record)
    assert set(baseline)==set(tracks)
    return PreparedPopulation(baseline,injections,records)


def summarize(records):
    return dict(basic_retained=len(records),
                length_qualified=sum(r['length_qualified'] for r in records),
                full_quality_candidates=sum(r['full_quality_pass'] for r in records),
                fit_attempted=sum(r['fit_attempted'] for r in records),
                fit_success=sum(r['fit_success'] for r in records),
                reference_pass=sum(r['reference_pass'] for r in records),
                injectable=sum(r['injectable'] for r in records),
                background_only=sum(r['background_only'] for r in records),
                raw_background=sum(r['baseline_version']=='original' for r in records),
                fitted_background=sum(r['fit_success'] and not r['injectable'] for r in records),
                rejection_counts=dict(Counter(reason for r in records for reason in set(r['rejection_reasons']))))
