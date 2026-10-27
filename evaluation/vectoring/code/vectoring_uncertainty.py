"""Approved, conditional NACp-radius geometry screen; no missing-data filling.

Local quadratic model on five actual observations. Bounds are deterministic
triangle-inequality bounds conditional on that model and the NACp disks, not
simultaneous 95% confidence intervals or aircraft certification.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import numpy as np

NACP_RADIUS={1:18520.,2:7408.,3:3704.,4:1852.,5:926.,6:555.6,
             7:185.2,8:92.6,9:30.,10:10.,11:3.}
STATUS_DISTANCE_S=10.
MAX_DIRECTION_ERROR_DEG=10.

def quality_radii(raw, indices, matches):
    if matches is None:return None,['missing_quality_matches']
    errors=[];radii=[]
    for i in indices:
        r=matches.get(int(i))
        if r is None:
            errors.append('missing_quality_match');continue
        expected=np.array([float(r[k]) for k in ['time','lat','lon','geoaltitude','lastposupdate']])
        identity=raw[i] if raw.shape[1]==5 else raw[i,[0,1,2,5,4]]
        if not np.array_equal(expected,identity):errors.append('quality_source_mismatch')
        if not r['exact_position_rows'] or not r['positive_nic_exact_match']:
            errors.append('position_quality_unknown')
        if not r['brackets_agree_positive']:
            errors.append('status_missing_unknown_or_conflicting');continue
        if r['previous_age_s'] is None or r['next_delay_s'] is None or not (0<=r['previous_age_s']<=STATUS_DISTANCE_S and 0<=r['next_delay_s']<=STATUS_DISTANCE_S):
            errors.append('status_bracket_over_10_s');continue
        nacp=r['previous_quality'][0][1]
        if nacp not in NACP_RADIUS:errors.append('unsupported_nacp');continue
        radii.append(NACP_RADIUS[nacp])
    return (np.asarray(radii) if not errors else None),sorted(set(errors))

def local_frame(xy,times,radii,query_times):
    """Return unit tangents and enclosing curvature intervals on original data.

    No smoothing of source positions. A quadratic is used only as a local
    derivative model; inconsistent residuals or uncertain directions reject.
    Windows shift at boundaries within the already checked source support.
    """
    xy=np.asarray(xy,float);times=np.asarray(times,float);radii=np.asarray(radii,float)
    if len(times)<5 or np.any(np.diff(times)<=0):raise ValueError('invalid_geometry_support')
    normals=[];intervals=[];details=[]
    for qt in query_times:
        if qt<times[0] or qt>times[-1]:raise ValueError('geometry_extrapolation')
        center=int(np.argmin(np.abs(times-qt)));lo=min(max(0,center-2),len(times)-5)
        ix=np.arange(lo,lo+5);tt=times[ix]-qt
        scale=max(abs(tt));u=tt/scale
        design=np.column_stack((np.ones(5),u,u*u))
        if np.linalg.matrix_rank(design)<3:raise ValueError('singular_geometry_fit')
        weights=np.linalg.pinv(design);x=xy[ix]-xy[ix[2]]
        beta=weights@x;hat=design@weights
        residual=np.linalg.norm(x-design@beta,axis=1)
        # Necessary consistency condition for any exact quadratic within disks.
        residual_bound=np.abs(np.eye(5)-hat)@radii[ix]
        if np.any(residual>residual_bound+1e-6):raise ValueError('quadratic_model_inconsistent_with_error_disks')
        velocity=beta[1]/scale;acceleration=2*beta[2]/scale**2
        ev=float(np.abs(weights[1]/scale)@radii[ix])
        ea=float(np.abs(2*weights[2]/scale**2)@radii[ix])
        speed=float(np.linalg.norm(velocity));acc=float(np.linalg.norm(acceleration))
        if speed<=ev or ev/speed>np.sin(np.deg2rad(MAX_DIRECTION_ERROR_DEG)):
            raise ValueError('direction_uncertainty_over_10_deg')
        cross=float(velocity[0]*acceleration[1]-velocity[1]*acceleration[0])
        ec=speed*ea+acc*ev+ev*ea
        denom=((speed-ev)**3,(speed+ev)**3)
        bounds=[num/d for num in (cross-ec,cross+ec) for d in denom]
        intervals.append([min(bounds),max(bounds)])
        normals.append([-velocity[1]/speed,velocity[0]/speed])
        details.append(dict(source_local_indices=ix.tolist(),velocity_error_m_s=ev,
                            acceleration_error_m_s2=ea,model_residual_max_m=float(residual.max())))
    return dict(normals=np.asarray(normals),curvature_intervals=np.asarray(intervals),details=details)
