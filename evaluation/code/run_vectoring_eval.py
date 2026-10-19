"""Synthetic vectoring geometry and candidate speed screening."""
import numpy as np

TURN_S=300; RETURN_S=300; SAMPLE=5; MAX_OFFSET=5000.; REPEATS=5; SEED=43019

def add_vectoring(p,side):
    # A 10-minute smooth lateral bump: 5 min to max offset, then 5 min back.
    half=int(TURN_S/SAMPLE); total=2*half
    if len(p)<total+1: raise ValueError('track shorter than vectoring maneuver duration')
    start=(len(p)-total)//2
    end=start+total+1
    q=p.copy(); seg=p[start:end]
    u=np.linspace(0.,1.,len(seg))
    offset=MAX_OFFSET*0.5*(1-np.cos(2*np.pi*u))*side
    tangent=np.gradient(seg[:,:2],axis=0)
    norm=np.linalg.norm(tangent,axis=1,keepdims=True)
    tangent=tangent/np.maximum(norm,1e-9)
    normal=np.column_stack((-tangent[:,1],tangent[:,0]))
    q[start:end,:2]=seg[:,:2]+offset[:,None]*normal
    return q,start,end

def vectoring_eligible(p, max_horizontal_speed=500.0):
    """Require both random sides to pass a fixed kinematic screen before injection.

    This is a speed screen, not a complete physical feasibility guarantee.
    Aircraft failing it remain in the baseline scene but receive no injection.
    """
    if len(p)<121:
        return False
    return all(np.linalg.norm(np.diff(add_vectoring(p,side)[0][:,:2],axis=0),axis=1).max()/SAMPLE <= max_horizontal_speed for side in (-1,1))
