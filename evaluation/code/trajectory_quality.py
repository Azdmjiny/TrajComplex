"""Conservative diagnostic QC, not a certified aircraft flight envelope.

Reject a complete aircraft-hour instead of repairing jumps by interpolation.
Thresholds are fixed before examining dose-response results. A 350 m/s
sensitivity run accompanies the primary 500 m/s horizontal threshold.
"""
import numpy as np

def quality_reasons(observations, enu, max_horizontal_speed=500.0, *, position_times=None):
    if max_horizontal_speed is None:
        return []  # Explicit legacy reproduction only.
    a=np.asarray(observations); p=np.asarray(enu); reasons=[]
    if not np.isfinite(a).all() or not np.isfinite(p).all():
        return ['nonfinite']
    if np.any(np.abs(a[:,1])>90) or np.any(np.abs(a[:,2])>180):
        reasons.append('coordinate_range')
    if np.any((a[:,3]<-500)|(a[:,3]>20000)):
        reasons.append('altitude_range')
    dt=np.diff(a[:,0])
    if np.any(dt<=0):
        return reasons+['nonincreasing_time']
    horizontal_dt=dt if position_times is None else np.diff(np.asarray(position_times,float))
    if not np.isfinite(horizontal_dt).all() or np.any(horizontal_dt<=0):
        return reasons+['invalid_position_update_time']
    if np.any(np.linalg.norm(np.diff(p[:,:2],axis=0),axis=1)/horizontal_dt>max_horizontal_speed):
        reasons.append('horizontal_speed')
    if np.any(np.abs(np.diff(p[:,2]))/dt>100):
        reasons.append('vertical_speed')
    return reasons
