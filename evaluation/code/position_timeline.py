"""Horizontal position updates and snapshot altitude have separate clocks.

Retain the original snapshot-anchored five-second grid only where both
observation streams support it. Never extrapolate or repair invalid updates.
"""
import numpy as np


def position_grid(raw, sample_s=5, max_age_s=15, max_gap_s=20):
    raw=np.asarray(raw,dtype=float)
    if raw.ndim!=2 or raw.shape[1] not in (5,6) or len(raw)<2:
        raise ValueError('invalid_source_observations')
    if not np.isfinite(raw).all() or np.any(np.diff(raw[:,0])<=0):
        raise ValueError('invalid_source_times_or_positions')
    if np.any(np.diff(raw[:,4])<=0):
        raise ValueError('position_timestamp_not_advancing')
    age=raw[:,0]-raw[:,4]
    if np.any(age<0) or np.any(age>max_age_s):
        raise ValueError('stale_or_invalid_position_timestamp')
    if np.any(np.diff(raw[:,4])>max_gap_s):
        raise ValueError('position_update_gap_over_20_s')
    if np.any(np.diff(raw[:,0])>max_gap_s):
        raise ValueError('source_record_gap_over_20_s')
    if np.any(np.all(np.diff(raw[:,1:3],axis=0)==0,axis=1)):
        raise ValueError('repeated_raw_horizontal_position')
    stop=min(raw[-1,0],raw[-1,4])
    grid=np.arange(raw[0,0],stop+1e-6,sample_s)
    grid=grid[(grid>=raw[0,4])&(grid<=stop)]
    if len(grid)==0:raise ValueError('no_common_time_support')
    return grid


def resample_positions(raw,enu,grid):
    """Interpolate supported horizontal updates; keep vertical snapshot timing."""
    raw=np.asarray(raw,float);enu=np.asarray(enu,float);grid=np.asarray(grid,float)
    if np.any(grid<max(raw[0,0],raw[0,4])) or np.any(grid>min(raw[-1,0],raw[-1,4])):
        raise ValueError('position_extrapolation')
    return np.column_stack((np.interp(grid,raw[:,4],enu[:,0]),
                            np.interp(grid,raw[:,4],enu[:,1]),
                            np.interp(grid,raw[:,0],enu[:,2])))
