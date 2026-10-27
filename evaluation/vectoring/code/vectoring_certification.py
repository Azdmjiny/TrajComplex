"""Stable continuous certificates and failure witnesses for the existing family.

No physical tolerances are introduced here. Polynomial derivatives are carried
through subdivision, never recovered from nearly identical position controls.
Numerical root witnesses guide rejection/optimization, never certify acceptance.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
import math
from functools import lru_cache
import numpy as np
from numpy.polynomial import polynomial as pol
from scipy.optimize import brentq


def fail(reason, witness=None):
    from vectoring_path import PathRejected
    exc=PathRejected(reason)
    exc.witness=witness
    raise exc


@lru_cache(None)
def product_weights(n,m):
    weights=np.zeros((n+m+1,n+1,m+1))
    for i in range(n+1):
        for j in range(m+1):weights[i+j,i,j]=math.comb(n,i)*math.comb(m,j)/math.comb(n+m,i+j)
    return weights


def dot_polynomial(a,b):
    return np.einsum('kij,nid,njd->nk',product_weights(a.shape[1]-1,b.shape[1]-1),a,b)


def convexity_envelope(refs,q,query_controls):
    """Keep r, r', r'' at the SAME reference parameter in each polynomial.

    Independent global boxes combine unrelated reference locations. The exact
    Bernstein product removes that loss without changing convexity > 0.
    """
    r=np.array([x[2] for x in refs]);v=np.array([x[3] for x in refs]);a=np.array([x[4] for x in refs])
    coeff=dot_polynomial(v,v)+dot_polynomial(r-q,a)
    variation=np.einsum('nid,jd->nij',a,query_controls-q)
    return float(np.min(coeff.min(axis=1)-variation.max(axis=(1,2))))


def motion_envelope(v,a,rv):
    import vectoring_path as p
    vb=p.hull(v);ab=p.hull(a);low=p.norm_lower(vb)
    if low<=0:return np.full(4,-1.)
    lon=p.dot_bounds(vb,ab)
    rotate=(np.array([ab[0][1],-ab[1][0]]),np.array([ab[1][1],-ab[0][0]]))
    lat=p.dot_bounds(vb,rotate)
    return np.array([p.MAX_SPEED-np.linalg.norm(v,axis=1).max(),
        low-p.MIN_SPEED_RATIO*np.linalg.norm(rv,axis=1).max(),
        p.MAX_LONGITUDINAL-max(abs(x) for x in lon)/low,
        p.MAX_LATERAL-max(abs(x) for x in lat)/low])


def motion(pieces,reference,kinematics=None):
    import vectoring_path as p
    pending=[]
    for i,((a,b,c),(_,_,r)) in enumerate(zip(pieces,reference.pieces)):
        v=p.derivative(c,b-a);acc=p.derivative(v,b-a);rv=p.derivative(r,b-a)
        if kinematics is not None:v,acc,rv=kinematics[i]
        pending.append((a,b,v,acc,rv))
    count=0;margins=np.full(4,np.inf)
    reasons=['continuous_horizontal_speed_over_limit','continuous_speed_collapse',
             'continuous_longitudinal_acceleration_over_limit','continuous_lateral_acceleration_over_limit']
    while pending:
        a,b,v,acc,rv=pending.pop();count+=1
        if count>p.MAX_VERIFY_NODES:fail('continuous_motion_work_budget_unresolved')
        bounds=motion_envelope(v,acc,rv)
        if np.all(bounds>=0):margins=np.minimum(margins,bounds);continue
        vv=p.middle(v);aa=p.middle(acc);rr=p.middle(rv);speed=np.linalg.norm(vv)
        if speed<=0:fail('continuous_speed_collapse',dict(kind='motion',time_s=(a+b)/2,quantity='zero_speed'))
        actual=np.array([p.MAX_SPEED-speed,speed-p.MIN_SPEED_RATIO*np.linalg.norm(rr),
            p.MAX_LONGITUDINAL-abs(vv@aa)/speed,p.MAX_LATERAL-abs(vv[0]*aa[1]-vv[1]*aa[0])/speed])
        for j,reason in enumerate(reasons):
            if actual[j]<0:fail(reason,dict(kind='motion',time_s=(a+b)/2,quantity=reason,margin=float(actual[j])))
        mid=(a+b)/2
        if mid in (a,b):fail('continuous_motion_numeric_resolution_unresolved',dict(kind='unresolved',time_s=mid))
        vl,vr=p.split(v);al,ar=p.split(acc);rl,rr=p.split(rv)
        pending.extend([(a,mid,vl,al,rl),(mid,b,vr,ar,rr)])
    return dict(verified_intervals=count,conservative_margins=margins.tolist(),derivatives='subdivided original derivative polynomials')


def edge(a,b,c,v,acc):
    import vectoring_path as p
    error=float(p.point_segment(c,c[:1],c[-1:])[0].max())
    return a,b,c,v,acc,error


def split_edge(e):
    import vectoring_path as p
    a,b,c,v,acc,_=e;m=(a+b)/2
    if m in (a,b):fail('reference_projection_numeric_resolution_unresolved')
    cl,cr=p.split(c);vl,vr=p.split(v);al,ar=p.split(acc)
    return edge(a,m,cl,vl,al),edge(m,b,cr,vr,ar)


def stationary_candidates(q,reference_pieces):
    """All piece endpoints and real stationary roots, centered before conversion."""
    import vectoring_path as p
    values=[]
    for lo,hi,c in reference_pieces:
        n=len(c)-1;delta=c-q
        power=np.array([math.comb(n,k)*sum((-1)**(k-i)*math.comb(k,i)*delta[i] for i in range(k+1)) for k in range(n+1)])
        v=pol.polyder(power)
        equation=pol.polyadd(pol.polymul(power[:,0],v[:,0]),pol.polymul(power[:,1],v[:,1]))
        roots=pol.polyroots(equation)
        us=[0.,1.]+[float(x.real) for x in roots if abs(x.imag)<=np.sqrt(np.finfo(float).eps) and 0<x.real<1]
        for u in us:
            d=pol.polyval(u,power);vv=pol.polyval(u,v)/(hi-lo);aa=pol.polyval(u,pol.polyder(v))/(hi-lo)**2
            values.append(dict(time_s=lo+u*(hi-lo),distance_m=float(np.linalg.norm(d)),
                convexity=float(vv@vv+d@aa),stationary=bool(0<u<1),position=(d+q)))
    return values


def branch_witness(query_piece,reference_pieces,center):
    """Detect distance-order reversal; never turn numerical roots into acceptance.

    The separator's negative squared-distance curvature supplies a solver aid
    for the *existing sufficient convex-projection certificate*. It is not
    asserted necessary for every conceivable valid route.
    """
    import vectoring_path as p
    a,b,c=query_piece
    def query(t):return p.split(c,np.clip((t-a)/(b-a),0,1))[0][-1]
    initial=stationary_candidates(query(center),reference_pieces)
    minima=sorted((v for v in initial if v['stationary'] and v['convexity']>0),key=lambda v:v['distance_m'])
    if len(minima)<2:return None
    one,two=minima[:2]
    if abs(one['distance_m']-two['distance_m'])>p.POSITION_TOL:return None
    boundary=(one['time_s']+two['time_s'])/2
    def evaluate(t):
        vals=stationary_candidates(query(t),reference_pieces)
        left=[v for v in vals if v['time_s']<boundary];right=[v for v in vals if v['time_s']>=boundary]
        if not left or not right:return None
        x=min(left,key=lambda v:v['distance_m']);y=min(right,key=lambda v:v['distance_m'])
        return x['distance_m']-y['distance_m'],x,y,vals
    x=evaluate(a);y=evaluate(b)
    if x is None or y is None or x[0]*y[0]>=0:return None
    at=float(brentq(lambda t:evaluate(t)[0],a,b,xtol=np.spacing(max(1.,abs(a),abs(b)))*4))
    _,left,right,vals=evaluate(at)
    if not (left['stationary'] and right['stationary'] and left['convexity']>0 and right['convexity']>0):return None
    separators=[v for v in vals if left['time_s']<v['time_s']<right['time_s'] and v['stationary'] and v['convexity']<0]
    if not separators:return None
    separator=min(separators,key=lambda v:v['convexity'])
    return dict(kind='projection_convexity',classification='nearest_branch_conflict',time_s=at,
        reference_time_s=float(separator['time_s']),convexity=float(separator['convexity']),
        nearest_reference_times_s=[float(left['time_s']),float(right['time_s'])],
        nearest_distance_m=[float(left['distance_m']),float(right['distance_m'])],
        reference_separation_m=float(np.linalg.norm(left['position']-right['position'])),
        bracket_s=[float(a),float(b)],distance_order_at_bracket_m=[float(x[0]),float(y[0])],
        evidence='stationary-root distance-order reversal; rejection/solver aid only')


def projection(pieces,line,side,velocities=None,diagnostics=None):
    import vectoring_path as p
    base=line.get('kinematic_edges')
    if base is None:
        base=[edge(a,b,c,p.derivative(c,b-a),p.derivative(p.derivative(c,b-a),b-a)) for a,b,c in line['edges']]
    originals=line.get('original_pieces',line['edges'])
    pending=[]
    for i,(a,b,c) in enumerate(pieces):
        v=p.derivative(c,b-a) if velocities is None else velocities[i]
        pending.append((a,b,c,v,None,i))
    count=0;ref_splits=0;diagnosed=set()
    first,last=base[0],base[-1]
    while pending:
        a,b,c,velocity,refs,i=pending.pop();count+=1
        if count+ref_splits>p.MAX_VERIFY_NODES:fail('reference_projection_work_budget_unresolved',dict(kind='unresolved',time_s=(a+b)/2))
        if refs is None:refs=base
        q=p.middle(c);radius=float(np.linalg.norm(c-q,axis=1).max())
        distances=p.point_segment(q,np.array([r[2][0] for r in refs]),np.array([r[2][-1] for r in refs]))[0][0]
        errors=np.array([r[5] for r in refs])
        indices=np.flatnonzero(distances-errors<=np.min(distances+errors)+2*radius)
        refs=[refs[j] for j in indices]
        connected=all(x[1]==y[0] for x,y in zip(refs[:-1],refs[1:]))
        rp=np.concatenate([r[2] for r in refs]);rv=np.concatenate([r[3] for r in refs]);ra=np.concatenate([r[4] for r in refs])
        rb=p.hull(rp);qb=p.hull(c);vb=p.hull(rv);ab=p.hull(ra);qvb=p.hull(velocity)
        convexity=p.norm_lower(vb)**2+p.dot_bounds((rb[0]-qb[1],rb[1]-qb[0]),ab)[0]
        if convexity<=0:convexity=convexity_envelope(refs,q,c)
        forward=p.dot_bounds(vb,qvb)[0]
        signed=[]
        for _,_,r,v,_,_ in refs:
            delta=q-r
            coeff=p.bernstein_product(v[:,0],delta[:,1])-p.bernstein_product(v[:,1],delta[:,0])
            dq=c-q;variation=v[:,0,None]*dq[None,:,1]-v[:,1,None]*dq[None,:,0]
            signed.extend([float(coeff.min()+variation.min()),float(coeff.max()+variation.max())])
        side_ok=(min(signed)>=0 if side>0 else max(signed)<=0)
        j=int(np.argmin(distances[indices]+errors[indices]));near=refs[j]
        near_route=float(p.point_segment(c,near[2][:1],near[2][-1:])[0].max()+near[5])<=p.POSITION_TOL
        inside=np.max((first[2][0]-c)@first[3][0])<=0 and np.min((last[2][-1]-c)@last[3][-1])>=0
        if connected and convexity>0 and forward>0 and (side_ok or near_route) and (inside or near_route):continue
        if radius<=line['error'] and (not connected or convexity<=0) and i not in diagnosed:
            diagnosed.add(i)
            witness=branch_witness(pieces[i],originals,(a+b)/2)
            if witness is not None:fail('reference_projection_branch_conflict',witness)
        # Tighten the reference cover too: query-only subdivision has an
        # irreducible reference error floor. Derivatives remain independent.
        max_error=max(r[5] for r in refs)
        if radius<=max_error and max_error>0:
            # Degree-bounded floating-point resolution guard. It can only
            # reject an unresolved certificate, never accept or relax it.
            resolution=max((len(r[2])-1)*np.spacing(max(1.,float(np.abs(r[2]).max()))) for r in refs)
            if max_error<=resolution:
                fail('reference_projection_numeric_resolution_unresolved',dict(kind='unresolved',time_s=(a+b)/2,
                    connected=connected,convexity_lower=float(convexity),forward_lower=float(forward),
                    reference_error_m=float(max_error),floating_point_resolution_m=float(resolution)))
            refined=[]
            for r in refs:
                if r[5]>=max_error:
                    refined.extend(split_edge(r));ref_splits+=1
                else:refined.append(r)
            pending.append((a,b,c,velocity,refined,i));continue
        mid=(a+b)/2
        if mid in (a,b):fail('reference_projection_numeric_resolution_unresolved',dict(kind='unresolved',time_s=mid,
            connected=connected,convexity_lower=float(convexity),forward_lower=float(forward)))
        cl,cr=p.split(c);vl,vr=p.split(velocity)
        pending.extend([(a,mid,cl,vl,refs,i),(mid,b,cr,vr,refs,i)])
    if diagnostics is not None:diagnostics.update(query_intervals=count,reference_subdivisions=ref_splits)
    return count


def convexity_constraints(x,witnesses,reference,side):
    """Linear solver aids for the existing sufficient projection certificate."""
    import vectoring_path as p
    values=[];jac=[]
    for w in witnesses:
        t=w['time_s'];s=w['reference_time_s']
        r=reference.values([s])[0];v=reference.values([s],1)[0];a=reference.values([s],2)[0]
        q=reference.values([t])[0];basis=p.offset_basis(reference,[t],side)[0]
        scale=float(v@v)
        if scale<=0:fail('reference_projection_stationary_reference')
        values.append((v@v+(r-q-basis@x)@a)/scale)
        jac.append(-a@basis/scale)
    return np.asarray(values),np.asarray(jac).reshape(-1,3)
