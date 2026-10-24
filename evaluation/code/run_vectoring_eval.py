"""Synthetic vectoring geometry and reject-only candidate screening.

Legacy five-second compatibility helpers; the current population workflow explicitly
passes sample_s=10. Do not use SAMPLE as the current Encoder cadence.

The screens reject complete aircraft-hour candidates. They never infer a
missing direction or reduce the requested offset to make a candidate pass.
"""
import numpy as np
from vectoring_uncertainty import quality_radii
import vectoring_path as path
from position_timeline import position_grid

TURN_S=300; RETURN_S=300; SAMPLE=5; MAX_OFFSET=5000.; REPEATS=5; SEED=43019
MAX_HORIZONTAL_SPEED=500.0
MAX_POSITION_GAP_S=20.0
MAX_POSITION_AGE_S=15.0
# Engineering screening policy approved by the user on 2026-10-22.
MIN_SPEED_RATIO=0.5
MAX_EQUIVALENT_BANK_DEG=35.0
GRAVITY=9.80665
NUMERICAL_EPS_M=1e-6  # Numerical guard only; NOT a position-accuracy bound.


class VectoringRejected(ValueError):
    """Candidate is unsuitable for vectoring under the frozen screening rules."""

def add_vectoring(p,side, *, diagnostics=None, frame=None):
    """Use only the continuous reference checked against this source trajectory."""
    p=np.asarray(p,dtype=float)
    if p.ndim!=2 or p.shape[1]!=3 or not np.isfinite(p).all():
        raise VectoringRejected('invalid_trajectory')
    if side not in (-1,1): raise ValueError('side must be -1 or +1')
    if len(p)<123: raise VectoringRejected('missing_maneuver_join_support')
    start=(len(p)-120)//2;end=start+121
    seg=p[start:end]
    if np.any(np.linalg.norm(np.gradient(seg[:,:2],axis=0),axis=1)<=NUMERICAL_EPS_M):
        raise VectoringRejected('unreliable_direction_zero_tangent')
    if frame is None or not isinstance(frame.get('reference'),path.Reference):
        raise VectoringRejected('missing_approved_geometry_frame')
    if not np.array_equal(frame.get('source_trajectory'),p):
        raise VectoringRejected('geometry_frame_trajectory_mismatch')
    cached=frame.get('verified_paths',{}).get(side)
    if cached is not None:
        if diagnostics is not None:diagnostics.update(frame['path_diagnostics'][side])
        return cached.copy(),start,end
    before=p[start-1:end+1]
    detail={} if diagnostics is None else diagnostics
    detail['original']=kinematic_diagnostics(before,start-1)
    try:xy=path.generate(frame['reference'],side,detail)
    except path.PathRejected as exc:raise VectoringRejected(str(exc)) from exc
    except (np.linalg.LinAlgError,FloatingPointError) as exc:raise VectoringRejected('path_numerical_failure') from exc
    q=p.copy();q[start:end,:2]=xy
    detail['deformed']=kinematic_diagnostics(q[start-1:end+1],start-1)
    _check_deformed_kinematics(before,q[start-1:end+1])
    return q,start,end


def _check_deformed_kinematics(original, deformed, *, sample_s=None):
    dt=float(SAMPLE if sample_s is None else sample_s); v0=np.diff(original[:,:2],axis=0)/dt; v1=np.diff(deformed[:,:2],axis=0)/dt
    s0=np.linalg.norm(v0,axis=1); s1=np.linalg.norm(v1,axis=1)
    if np.any(s0<=NUMERICAL_EPS_M/dt):
        raise VectoringRejected('unreliable_direction_zero_segment')
    if np.any(s1/s0<MIN_SPEED_RATIO):
        raise VectoringRejected('deformed_speed_collapses_below_half_baseline')
    if np.any(s1>MAX_HORIZONTAL_SPEED):
        raise VectoringRejected('deformed_horizontal_speed_over_500_m_s')
    acceleration=np.diff(v1,axis=0)/dt
    mid=(v1[1:]+v1[:-1])/2;midnorm=np.linalg.norm(mid,axis=1)
    if np.any(midnorm<=NUMERICAL_EPS_M):raise VectoringRejected('undefined_acceleration_direction')
    longitudinal=np.abs(np.sum(acceleration*mid,axis=1)/midnorm)
    lateral=np.abs(acceleration[:,0]*mid[:,1]-acceleration[:,1]*mid[:,0])/midnorm
    if np.any(longitudinal>2.0):raise VectoringRejected('longitudinal_acceleration_over_2_m_s2')
    max_acceleration=GRAVITY*np.tan(np.deg2rad(MAX_EQUIVALENT_BANK_DEG))
    if np.any(lateral>max_acceleration):
        raise VectoringRejected('lateral_acceleration_over_35deg_bank_proxy')
    heading=np.arctan2(v1[:,1],v1[:,0])
    turn=np.abs(np.arctan2(np.sin(np.diff(heading)),np.cos(np.diff(heading))))
    mean_speed=0.5*(s1[:-1]+s1[1:])
    max_rate=max_acceleration/np.maximum(mean_speed,NUMERICAL_EPS_M/dt)
    if np.any(turn/dt>max_rate):
        raise VectoringRejected('deformed_turn_rate_over_35deg_bank_proxy')


def require_confirmed_vectoring_policy():
    """Approval recorded 2026-10-22; quality data remains mandatory per candidate."""
    return 'approved-2026-10-22'


def _extreme(values, sample_start, *, minimum=False):
    values=np.asarray(values)
    valid=np.flatnonzero(np.isfinite(values))
    if not len(valid): return None
    local=int(valid[np.argmin(values[valid]) if minimum else np.argmax(values[valid])])
    return dict(value=float(values[local]), sample_index=sample_start+local)


def kinematic_diagnostics(p, sample_start=0):
    """Ground-track diagnostics only; no new acceptance thresholds.

    Speed index denotes the segment start; acceleration/turn index denotes
    the shared sample of two segments. Undefined directions remain null.
    """
    velocity=np.diff(np.asarray(p)[:,:2],axis=0)/SAMPLE
    speed=np.linalg.norm(velocity,axis=1)
    acceleration=np.diff(velocity,axis=0)/SAMPLE
    midpoint=(velocity[1:]+velocity[:-1])/2
    midnorm=np.linalg.norm(midpoint,axis=1)
    good=midnorm>NUMERICAL_EPS_M/SAMPLE
    longitudinal=np.full(len(acceleration),np.nan)
    longitudinal[good]=np.sum(acceleration[good]*midpoint[good],axis=1)/midnorm[good]
    lateral=np.full(len(acceleration),np.nan)
    lateral[good]=np.abs(acceleration[good,0]*midpoint[good,1]-acceleration[good,1]*midpoint[good,0])/midnorm[good]
    heading=np.arctan2(velocity[:,1],velocity[:,0])
    turn=np.abs(np.arctan2(np.sin(np.diff(heading)),np.cos(np.diff(heading))))/SAMPLE
    turn[(speed[:-1]<=NUMERICAL_EPS_M/SAMPLE)|(speed[1:]<=NUMERICAL_EPS_M/SAMPLE)]=np.nan
    return dict(minimum_speed_m_s=_extreme(speed,sample_start,minimum=True),
                maximum_speed_m_s=_extreme(speed,sample_start),
                maximum_total_acceleration_m_s2=_extreme(np.linalg.norm(acceleration,axis=1),sample_start+1),
                maximum_abs_longitudinal_acceleration_m_s2=_extreme(np.abs(longitudinal),sample_start+1),
                maximum_lateral_acceleration_m_s2=_extreme(lateral,sample_start+1),
                maximum_turn_rate_rad_s=_extreme(turn,sample_start+1),
                undefined_acceleration_direction_samples=(np.flatnonzero(~good)+sample_start+1).tolist())


def _source_support(p, raw, diagnostics):
    """Check actual bracketing observations, including boundary interpolation.

    No heading filling or offset reduction. The approved age/gap ceilings apply. Brackets are found by interpolation support, not an
    arbitrary +/-5-second window that can omit a necessary source record.
    """
    if raw is None: return ['missing_source_observations']
    raw=np.asarray(raw,dtype=float)
    if raw.ndim!=2 or raw.shape[1]!=5 or len(raw)<2:
        return ['invalid_source_observations']
    if not np.isfinite(raw[:,:4]).all() or np.any(np.diff(raw[:,0])<=0):
        return ['invalid_source_times_or_positions']
    try:
        grid=position_grid(raw,SAMPLE,MAX_POSITION_AGE_S,MAX_POSITION_GAP_S)
    except ValueError as exc:
        return [str(exc)]
    if len(grid)!=len(p):
        return ['source_grid_length_mismatch']
    start=(len(p)-120)//2
    sample_indices=np.arange(max(0,start-1),min(len(p),start+122))
    times=grid[sample_indices]
    right=np.searchsorted(raw[:,4],times,side='left')
    left=np.searchsorted(raw[:,4],times,side='right')-1
    lo=int(left.min());hi=int(right.max())
    local=raw[lo:hi+1]
    age=local[:,0]-local[:,4]
    reasons=[]
    if np.any(~np.isfinite(age)) or np.any(age<0) or np.any(age>MAX_POSITION_AGE_S):
        reasons.append('stale_or_invalid_position_timestamp')
    if np.any(np.diff(local[:,4])<=0): reasons.append('position_timestamp_not_advancing')
    if np.any(np.diff(local[:,4])>MAX_POSITION_GAP_S): reasons.append('position_update_gap_over_20_s')
    if np.any(np.diff(local[:,0])>MAX_POSITION_GAP_S): reasons.append('source_record_gap_over_20_s')
    if np.any(np.all(np.diff(local[:,1:3],axis=0)==0,axis=1)):
        reasons.append('repeated_raw_horizontal_position')
    if diagnostics is not None:
        diagnostics['source_record_indices']=list(range(lo,hi+1))
        diagnostics['source_records']=[[float(v) if np.isfinite(v) else None for v in row] for row in local]
        diagnostics['sample_support']=[dict(sample_index=int(i),left_raw_index=int(l),right_raw_index=int(r))
                                       for i,l,r in zip(sample_indices,left,right)]
        diagnostics['horizontal_time_axis']='lastposupdate'
        diagnostics['sample_times']=times.tolist()
    return reasons


def vectoring_eligibility(p, source_observations=None, *, diagnostics=None, quality_matches=None, prepared=None):
    """Reject-only approved conditional screen with auditable raw interpolation support.

    This helper is for diagnostics under the approved conditional uncertainty model.
    Both sides retain 5 km peak offset. No missing metadata may bypass screening.
    Each side reports its first failing gate, not an exhaustive causal inventory.
    """
    if prepared is not None:prepared.clear()
    p=np.asarray(p,dtype=float)
    if p.ndim!=2 or p.shape[1]!=3 or not np.isfinite(p).all():
        return False,['invalid_trajectory']
    if len(p)<121: return False,['track_shorter_than_maneuver']
    support={}
    reasons=_source_support(p,source_observations,support)
    if diagnostics is not None:diagnostics.update(support)
    if reasons: return False,sorted(set(reasons))
    raw=np.asarray(source_observations,float);indices=support['source_record_indices']
    radii,reasons=quality_radii(raw,indices,quality_matches)
    if reasons:return False,reasons
    from run_holding_eval import llh_to_enu
    source=raw[indices];xy=llh_to_enu(source[:,1],source[:,2],source[:,3])[:,:2]
    start=(len(p)-120)//2
    # The reference includes one unchanged sample before and after the maneuver.
    # Its grid constraints retain their linear provenance on actual updates.
    grid=position_grid(raw,SAMPLE,MAX_POSITION_AGE_S,MAX_POSITION_GAP_S)
    if start<1 or start+121>=len(p):return False,['missing_maneuver_join_support']
    if diagnostics is not None:diagnostics['nacp_radius_m']=radii.tolist()
    try:reference=path.make_reference(xy,source[:,4],radii,grid[start-1:start+122],p[start-1:start+122,:2])
    except path.PathRejected as exc:return False,[str(exc)]
    frame={'reference':reference,'source_trajectory':p.copy(),'verified_paths':{},'path_diagnostics':{}}
    if diagnostics is not None:diagnostics['geometry_fit']=reference.metadata
    for side in (-1,1):
        detail={}
        try:
            q,_,_=add_vectoring(p,side,diagnostics=detail,frame=frame)
            q.setflags(write=False)
            frame['verified_paths'][side]=q
            frame['path_diagnostics'][side]=detail
        except VectoringRejected as exc:reasons.append(f'side_{side}:{exc}')
        if diagnostics is not None: diagnostics[f'side_{side}']=detail
    if not reasons and prepared is not None:prepared.update(frame)
    return not reasons,sorted(set(reasons))


def vectoring_eligible(p, max_horizontal_speed=500.0, source_observations=None):
    """Boolean wrapper retained for callers using the previous helper API."""
    global MAX_HORIZONTAL_SPEED
    old=MAX_HORIZONTAL_SPEED
    try:
        MAX_HORIZONTAL_SPEED=float(max_horizontal_speed)
        return vectoring_eligibility(p,source_observations)[0]
    finally:
        MAX_HORIZONTAL_SPEED=old
