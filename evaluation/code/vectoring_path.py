"""Continuous, constrained ground-track construction. No pointwise normals.

Reference: minimum-jerk quintic interpolant of verified observations and their
provenance-preserving grid interpolants. Interpolation is a conservative special
case of the approved NACp residual bound; no denoising parameter is fitted.
Search family: reference + a nonnegative degree-eight Bernstein displacement
in ONE chord-normal direction. Its first/last three controls are zero, so
position, velocity and acceleration join exactly. Three free controls minimize
integrated squared Cartesian jerk. This restricted family can fail even when
another flight path exists. Continuous bounds independently verify the result.
"""
from dataclasses import dataclass
import heapq
import math
import numpy as np
from scipy.interpolate import make_interp_spline
from scipy.optimize import minimize

POSITION_TOL=0.03
SPEED_TOL=0.01
ACCELERATION_TOL=0.001
HEADING_TOL=np.deg2rad(0.01)
PEAK=15000.0
DURATION=600.0
MAX_SPEED=500.0
MAX_LONGITUDINAL=2.0
MAX_LATERAL=9.80665*np.tan(np.deg2rad(35.0))
MIN_SPEED_RATIO=0.5
DIRECTION_ERROR=np.deg2rad(10.0)
# Computational work caps, not flight thresholds. Exhaustion always rejects.
MAX_VERIFY_NODES=100000
SOLVER_MAXITER=100  # SciPy SLSQP's documented default, recorded in diagnostics.
MODEL='minimum-jerk-interpolant/chord-normal-Bernstein-8-v1'
NUMERICS='direct-offset-derivatives/adaptive-continuous-peak-feedback-v3'


def policy():
    return dict(model=MODEL,numerics=NUMERICS,peak_cross_track_m=PEAK,duration_s=DURATION,sample_s=5,
                reference_fit='minimum-jerk quintic interpolant of real updates and provenance-preserving grid constraints',
                residual_bound='each original observation within its NACp engineering disk; no extra allowance',
                route_search='nonnegative degree-eight chord-normal displacement; three free controls; local SLSQP minimum of integrated squared jerk',
                joins='C2 with continuous reference; original altitude and outside samples retained',
                numerical_tolerances=dict(position_m=POSITION_TOL,speed_m_s=SPEED_TOL,
                                          acceleration_m_s2=ACCELERATION_TOL,heading_deg=float(np.rad2deg(HEADING_TOL))),
                maximum_solver_iterations=SOLVER_MAXITER,maximum_verification_nodes=MAX_VERIFY_NODES,
                peak_feedback='continuous off-grid witnesses are added to solver constraints; warm-start same controls; total SLSQP budget shared across solves',
                on_failure='reject; do not shrink the fixed target, extend time, fill data or relax limits',
                limitations='restricted search; conditional reference model; ground-motion proxies; no global optimum or aircraft-specific certification')


class PathRejected(ValueError):pass


def split(b,u=.5):
    work=np.array(b,float);left=[work[0]];right=[work[-1]]
    for _ in range(len(b)-1):
        work=(1-u)*work[:-1]+u*work[1:]
        left.append(work[0]);right.append(work[-1])
    return np.asarray(left),np.asarray(right[::-1])


def restrict(b,a,c):
    if a==0 and c==1:return np.asarray(b)
    left=split(b,c)[0] if c<1 else np.asarray(b)
    return split(left,a/c)[1] if a>0 else left


def elevate(b,n):
    b=np.asarray(b)
    while len(b)-1<n:
        k=len(b);u=np.arange(1,k)/k
        b=np.concatenate((b[:1],u[:,None]*b[:-1]+(1-u[:,None])*b[1:],b[-1:]))
    return b


def derivative(b,h):return (len(b)-1)*np.diff(b,axis=0)/h
def middle(b):return split(b)[0][-1]


def hull(b):return np.min(b,axis=0),np.max(b,axis=0)
def product(a,b):
    vals=np.array([a[0]*b[0],a[0]*b[1],a[1]*b[0],a[1]*b[1]])
    return vals.min(axis=0),vals.max(axis=0)
def dot_bounds(a,b):
    lo,hi=product(a,b);return float(lo.sum()),float(hi.sum())


def bernstein_product(a,b):
    """Exact coefficient product, retaining same-parameter dependence."""
    n=len(a)-1;m=len(b)-1
    return np.array([sum(math.comb(n,i)*math.comb(m,k-i)*a[i]*b[k-i]
                        for i in range(max(0,k-m),min(n,k)+1))/math.comb(n+m,k)
                     for k in range(n+m+1)])
def norm_lower(bounds):
    lo,hi=bounds
    return float(np.linalg.norm(np.where(lo>0,lo,np.where(hi<0,hi,0))))


def point_segment(points,a,b):
    points=np.atleast_2d(points);ab=b-a;den=np.sum(ab*ab,axis=1)
    if np.any(den<=0):raise PathRejected('reference_zero_chord')
    u=np.clip(np.sum((points[:,None,:]-a)*ab,axis=2)/den,0,1)
    nearest=a+u[:,:,None]*ab
    return np.linalg.norm(points[:,None,:]-nearest,axis=2),u,nearest


@dataclass
class Reference:
    xy: np.ndarray
    times: np.ndarray
    radii: np.ndarray
    mapping: object
    breaks: np.ndarray
    pieces: list
    axis: np.ndarray
    origin: np.ndarray
    metadata: dict

    def values(self,t,order=0):return self.mapping(t,nu=order)@self.xy


def make_reference(xy,times,radii,grid,original_xy):
    """Linear observation-to-spline map; no inferred observations or headings."""
    xy=np.asarray(xy,float);times=np.asarray(times,float);radii=np.asarray(radii,float)
    grid=np.asarray(grid,float);original_xy=np.asarray(original_xy,float)
    if times.ndim!=1 or grid.ndim!=1 or len(grid)!=123 or original_xy.shape!=(123,2) or len(times)<6 or xy.shape!=(len(times),2) or radii.shape!=(len(times),):
        raise PathRejected('invalid_continuous_reference_support')
    if not all(np.isfinite(x).all() for x in [xy,times,radii,grid,original_xy]) or np.any(np.diff(times)<=0) or np.any(radii<=0):
        raise PathRejected('invalid_continuous_reference_support')
    if np.any(np.diff(grid)!=5.):raise PathRejected('invalid_reference_sample_grid')
    if grid[0]<times[0] or grid[-1]>times[-1]:raise PathRejected('reference_extrapolation')
    # Work in relative seconds to avoid large Unix epochs in polynomial algebra.
    epoch=grid[1];times=times-epoch;grid=grid-epoch
    origin=xy[0].copy();xy=xy-origin
    # Knots contain real updates plus existing resampled grid points. The latter
    # retain their exact linear weights on real updates, not new observations.
    knots=np.unique(np.r_[times,grid]);weights=np.column_stack([np.interp(knots,times,col) for col in np.eye(len(times)).T])
    zero=np.zeros(len(times))
    mapping=make_interp_spline(knots,weights,k=5,bc_type=([(3,zero),(4,zero)],[(3,zero),(4,zero)]))
    if not np.isfinite(mapping.c).all():raise PathRejected('nonfinite_reference_solve')
    # Natural minimum-jerk boundary conditions: third/fourth derivatives vanish
    # at SUPPORT edges, not artificially at the maneuver endpoints.
    residual=np.linalg.norm(mapping(times)@xy-xy,axis=1)
    if np.any(residual>radii):raise PathRejected('reference_outside_nacp_disks')
    if np.max(np.linalg.norm(mapping(grid)@xy+origin-original_xy,axis=1))>POSITION_TOL:
        raise PathRejected('reference_grid_provenance_mismatch')
    start=grid[1];end=grid[-2]
    if abs(end-start-DURATION)>np.finfo(float).eps*DURATION*8:
        raise PathRejected('missing_maneuver_join_support')
    chord=(mapping(end)-mapping(start))@xy;length=np.linalg.norm(chord)
    if length<=POSITION_TOL:raise PathRejected('reference_ambiguous_chord')
    axis=chord/length;breaks=np.unique(np.r_[start,knots[(knots>start)&(knots<end)],end]);pieces=[]
    worst_angle=0.;curvature_bounds=[]
    for a,b in zip(breaks[:-1],breaks[1:]):
        h=b-a
        power=np.array([mapping(a,nu=j)*h**j/math.factorial(j) for j in range(6)])
        w=np.array([sum(math.comb(i,j)/math.comb(5,j)*power[j] for j in range(i+1)) for i in range(6)])
        controls=w@xy;vw=derivative(w,h);aw=derivative(vw,h)
        # Check the independent spline and Bernstein derivative evaluations.
        # These numerical budgets never relax a physical acceptance threshold.
        mid=(a+b)/2
        for order,tolerance in [(0,POSITION_TOL),(1,SPEED_TOL),(2,ACCELERATION_TOL)]:
            check=controls.copy()
            for _ in range(order):check=derivative(check,h)
            if np.linalg.norm(middle(check)-mapping(mid,nu=order)@xy)>tolerance:
                raise PathRejected('reference_representation_precision_unresolved')
        vel=vw@xy;acc=aw@xy
        ev=float(np.max(np.abs(vw)@radii));ea=float(np.max(np.abs(aw)@radii))
        forward=float(np.min(vel@axis));vmax=float(np.max(np.linalg.norm(vel,axis=1)))
        # Convex-hull envelopes enclose each spline interval, not only samples.
        if forward<=ev or ev/forward>np.sin(DIRECTION_ERROR):
            raise PathRejected('continuous_reference_direction_unreliable')
        worst_angle=max(worst_angle,float(np.arcsin(ev/forward)))
        amax=float(np.max(np.linalg.norm(acc,axis=1)))
        kmax=(vmax*amax+vmax*ea+amax*ev+ev*ea)/(forward-ev)**3
        if not np.isfinite(kmax):raise PathRejected('continuous_reference_curvature_unbounded')
        curvature_bounds.append([-kmax,kmax])
        pieces.append((float(a-start),float(b-start),controls))
    return Reference(xy,times,radii,mapping,breaks-start,pieces,axis,origin,
                     dict(method=MODEL,maximum_source_residual_m=float(residual.max()),
                          maximum_conditional_direction_error_deg=float(np.rad2deg(worst_angle)),
                          curvature_intervals=curvature_bounds,
                          uncertainty='linear spline weights and NACp disks; conditional model, no measurement/model-bias certification',
                          fit='minimum-jerk interpolant; no adjustable smoothing weight; source and baseline samples unchanged'))


def polyline(reference):
    """Hausdorff-bounded chord cover using Bezier convex hulls."""
    pending=list(reversed(reference.pieces));edges=[];count=0;error=POSITION_TOL/8
    while pending:
        a,b,c=pending.pop();count+=1
        if count>MAX_VERIFY_NODES:raise PathRejected('reference_cover_unresolved')
        dist,_,_=point_segment(c,c[:1],c[-1:])
        if float(dist.max())<=error:
            edges.append((a,b,c));continue
        l,r=split(c);m=(a+b)/2
        pending.extend([(m,b,r),(a,m,l)])
    return dict(a=np.array([c[0] for _,_,c in edges]),b=np.array([c[-1] for _,_,c in edges]),edges=edges,error=error)


def construct(reference,controls,side):
    normal=side*np.array([-reference.axis[1],reference.axis[0]])
    bump=np.r_[np.zeros(3),np.asarray(controls)*PEAK,np.zeros(3)][:,None]*normal
    return [(a,b,elevate(c,8)+restrict(bump,a/DURATION,b/DURATION)) for a,b,c in reference.pieces]


def motion_bounds(c,r,h):
    v=derivative(c,h);a=derivative(v,h);rv=derivative(r,h)
    vb=hull(v);ab=hull(a);speed_min=norm_lower(vb)
    speed_max=float(np.max(np.linalg.norm(v,axis=1)))
    refmax=float(np.max(np.linalg.norm(rv,axis=1)))
    longitudinal=dot_bounds(vb,ab)
    # cross(v,a) = dot(v, [a_y,-a_x]).
    rotate=(np.array([ab[0][1],-ab[1][0]]),np.array([ab[1][1],-ab[0][0]]))
    lateral=dot_bounds(vb,rotate)
    if speed_min<=0:return np.array([-1.,-1.,-1.,-1.])
    return np.array([MAX_SPEED-speed_max,speed_min-MIN_SPEED_RATIO*refmax,
                     MAX_LONGITUDINAL-max(abs(x) for x in longitudinal)/speed_min,
                     MAX_LATERAL-max(abs(x) for x in lateral)/speed_min])


def verify_motion(pieces,reference):
    pending=[(a,b,c,r[2]) for (a,b,c),r in zip(pieces,reference.pieces)];count=0
    margins=np.full(4,np.inf)
    while pending:
        a,b,c,r=pending.pop();count+=1
        if count>MAX_VERIFY_NODES:raise PathRejected('continuous_motion_verification_unresolved')
        bounds=motion_bounds(c,r,b-a)
        if np.all(bounds>=0):margins=np.minimum(margins,bounds);continue
        v=middle(derivative(c,b-a));acc=middle(derivative(derivative(c,b-a),b-a));rv=middle(derivative(r,b-a))
        speed=np.linalg.norm(v)
        if speed<=0 or speed<MIN_SPEED_RATIO*np.linalg.norm(rv):raise PathRejected('continuous_speed_collapse')
        if speed>MAX_SPEED:raise PathRejected('continuous_horizontal_speed_over_limit')
        if abs(v@acc)/speed>MAX_LONGITUDINAL:raise PathRejected('continuous_longitudinal_acceleration_over_limit')
        if abs(v[0]*acc[1]-v[1]*acc[0])/speed>MAX_LATERAL:raise PathRejected('continuous_lateral_acceleration_over_limit')
        m=(a+b)/2
        if m in (a,b):raise PathRejected('continuous_motion_precision_unresolved')
        cl,cr=split(c);rl,rr=split(r);pending.extend([(a,m,cl,rl),(m,b,cr,rr)])
    return dict(verified_intervals=count,conservative_margins=margins.tolist())


def peak_bounds(pieces,line,*,work=None):
    """Bound max distance to the continuous reference, not same-time offset."""
    heap=[];best=0.;best_time=0.;serial=0;visits=0
    if work is None:work={'used':0}
    def push(a,b,c):
        nonlocal best,best_time,serial
        q=middle(c);dist,_,_=point_segment(q,line['a'],line['b']);j=int(dist.argmin())
        lower=float(dist[0,j]-line['error'])
        if lower>best:best=lower;best_time=(a+b)/2
        upper=float(point_segment(c,line['a'][j:j+1],line['b'][j:j+1])[0].max()+line['error'])
        heapq.heappush(heap,(-upper,serial,a,b,c));serial+=1
    for a,b,c in pieces:push(a,b,c)
    while heap and -heap[0][0]-best>POSITION_TOL/2:
        if work['used']>=MAX_VERIFY_NODES:raise PathRejected('cross_track_peak_unresolved')
        _,_,a,b,c=heapq.heappop(heap);visits+=1;work['used']+=1
        m=(a+b)/2
        if m in (a,b):raise PathRejected('cross_track_precision_unresolved')
        l,r=split(c);push(a,m,l);push(m,b,r)
    return best,max(best,-heap[0][0]),best_time


def verify_projection(pieces,line,side):
    """Conservative uniqueness, side and forward-progress envelopes.

    Candidate nearest-reference intervals are enclosed by Lipschitz distance
    bounds. Positive second derivative of squared distance ensures a unique
    projection in their connected union; positive tangent dot velocity ensures
    forward projection progress. Ambiguous or unresolved geometry rejects.
    """
    pending=list(pieces);count=0
    while pending:
        a,b,c=pending.pop();count+=1
        if count>MAX_VERIFY_NODES:raise PathRejected('reference_projection_unresolved')
        q=middle(c);radius=float(np.max(np.linalg.norm(c-q,axis=1)))
        distances,_,_=point_segment(q,line['a'],line['b']);d=distances[0]
        possible=np.flatnonzero(d<=d.min()+2*radius+2*line['error'])
        connected=bool(len(possible) and np.all(np.diff(possible)==1))
        refs=[line['edges'][j] for j in possible]
        rpoints=np.concatenate([r for _,_,r in refs]);rvel=np.concatenate([derivative(r,y-x) for x,y,r in refs]);racc=np.concatenate([derivative(derivative(r,y-x),y-x) for x,y,r in refs])
        rb=hull(rpoints);qb=hull(c);vb=hull(rvel);ab=hull(racc);qvb=hull(derivative(c,b-a))
        rq=(rb[0]-qb[1],rb[1]-qb[0])
        convex=norm_lower(vb)**2+dot_bounds(rq,ab)[0]>0
        forward=dot_bounds(vb,qvb)[0]>0
        # r and r' share a parameter. Independent coordinate boxes lose that
        # dependence and spuriously reject small offsets along curved routes.
        signed=[]
        for x,y,r in refs:
            velocity=derivative(r,y-x);delta=q-r
            coeff=bernstein_product(velocity[:,0],delta[:,1])-bernstein_product(velocity[:,1],delta[:,0])
            dq=c-q
            variation=velocity[:,0,None]*dq[None,:,1]-velocity[:,1,None]*dq[None,:,0]
            signed.extend([float(coeff.min()+variation.min()),float(coeff.max()+variation.max())])
        side_ok=(min(signed)>=0 if side>0 else max(signed)<=0)
        near_route=float(point_segment(c,line['a'][d.argmin():d.argmin()+1],line['b'][d.argmin():d.argmin()+1])[0].max()+line['error'])<=POSITION_TOL
        # A clamped endpoint distance is not a lateral cross-track distance.
        first=line['edges'][0];last=line['edges'][-1]
        entry=first[2][0];exit=last[2][-1]
        entry_v=derivative(first[2],first[1]-first[0])[0]
        exit_v=derivative(last[2],last[1]-last[0])[-1]
        inside=(np.max((entry-c)@entry_v)<=0 and np.min((exit-c)@exit_v)>=0)
        if connected and convex and forward and (side_ok or near_route) and (inside or near_route):continue
        m=(a+b)/2
        if m in (a,b):raise PathRejected('reference_projection_precision_unresolved')
        l,r=split(c);pending.extend([(a,m,l),(m,b,r)])
    return count


def sample_pieces(pieces,t,order=0):
    out=[]
    for value in np.atleast_1d(t):
        j=min(np.searchsorted([b for _,b,_ in pieces],value,side='right'),len(pieces)-1)
        a,b,c=pieces[j]
        for _ in range(order):c=derivative(c,b-a)
        u=np.clip((value-a)/(b-a),0,1)
        out.append(split(c,u)[0][-1])
    return np.asarray(out)


def offset_basis(reference,t,side,order=0):
    """Differentiate the global offset polynomial BEFORE adding positions.

    Coordinates and arbitrarily short reference intervals never enter these
    differences. Columns correspond to the same three dimensionless controls
    as construct(); the route family, duration and target are unchanged.
    """
    if side not in (-1,1):raise ValueError('side must be -1 or +1')
    if order not in (0,1,2,3):raise ValueError('unsupported offset derivative')
    t=np.atleast_1d(np.asarray(t,float))
    if not np.isfinite(t).all() or np.any(t<0) or np.any(t>DURATION):
        raise ValueError('offset time outside maneuver')
    coefficients=np.zeros((9,3));coefficients[3:6]=np.eye(3)*PEAK
    for _ in range(order):coefficients=derivative(coefficients,DURATION)
    scalar=np.array([split(coefficients,value/DURATION)[0][-1] for value in t])
    normal=side*np.array([-reference.axis[1],reference.axis[0]])
    return scalar[:,None,:]*normal[None,:,None]


def sampled_motion_constraints(x,reference_velocity,reference_acceleration,velocity_basis,acceleration_basis):
    """Existing normalized motion constraints and their analytic Jacobian."""
    v=reference_velocity+velocity_basis@x
    a=reference_acceleration+acceleration_basis@x
    speed=np.linalg.norm(v,axis=1)
    if not np.isfinite(v).all() or not np.isfinite(a).all() or np.any(speed<=0):
        raise PathRejected('undefined_solver_motion')
    ds=np.einsum('nd,ndk->nk',v,velocity_basis)/speed[:,None]
    longitudinal=np.sum(v*a,axis=1)/speed
    lateral=(v[:,0]*a[:,1]-v[:,1]*a[:,0])/speed
    dl=(np.einsum('nd,ndk->nk',a,velocity_basis)+
        np.einsum('nd,ndk->nk',v,acceleration_basis))/speed[:,None]
    dl-=longitudinal[:,None]*ds/speed[:,None]
    dc=(velocity_basis[:,0,:]*a[:,1,None]-velocity_basis[:,1,:]*a[:,0,None]+
        v[:,0,None]*acceleration_basis[:,1,:]-v[:,1,None]*acceleration_basis[:,0,:])/speed[:,None]
    dc-=lateral[:,None]*ds/speed[:,None]
    original=np.linalg.norm(reference_velocity,axis=1)
    values=np.r_[(MAX_SPEED-speed)/MAX_SPEED,
                 (speed-MIN_SPEED_RATIO*original)/MAX_SPEED,
                 (MAX_LONGITUDINAL-np.abs(longitudinal))/MAX_LONGITUDINAL,
                 (MAX_LATERAL-np.abs(lateral))/MAX_LATERAL]
    jacobian=np.concatenate((-ds/MAX_SPEED,ds/MAX_SPEED,
        -np.sign(longitudinal)[:,None]*dl/MAX_LONGITUDINAL,
        -np.sign(lateral)[:,None]*dc/MAX_LATERAL))
    # At abs(0), zero is a deterministic subgradient; this is not a claim of
    # differentiability or feasibility. Independent continuous checks remain.
    return values,jacobian


def sampled_peak_constraint(x,positions,basis,line):
    """Current sampled spatial-distance target with an active-branch derivative.

    Recompute the nearest segment and maximizing sample at EVERY evaluation.
    Exact ties use the first active segment/sample deterministically. The
    max/min target remains nonsmooth at switches; local failure still rejects.
    This solver aid does not replace the continuous peak/projection verifier.
    """
    q=positions+basis@x
    distances,_,nearest=point_segment(q,line['a'],line['b'])
    segments=np.argmin(distances,axis=1)
    per_sample=distances[np.arange(len(q)),segments]
    i=int(np.argmax(per_sample));j=int(segments[i]);peak=float(per_sample[i])
    jacobian=np.zeros(3) if peak==0 else ((q[i]-nearest[i,j])/peak)@basis[i]/PEAK
    active=dict(sample_index=i,segment_index=j,
                maximizing_sample_ties=int(np.count_nonzero(per_sample==peak)),
                nearest_segment_ties=int(np.count_nonzero(distances[i]==peak)))
    return (peak-PEAK)/PEAK,jacobian,active


def generate(reference,side,diagnostics=None,*,sample_s=5):
    if side not in (-1,1):raise ValueError('side must be -1 or +1')
    if sample_s not in (5,10):raise ValueError('unsupported output cadence')
    detail={} if diagnostics is None else diagnostics
    history=[];feedback_times=[];peak_work={'used':0}
    detail.update(method=MODEL,numerics=NUMERICS,solver_calls=0,solver_iterations=0,
                  solver_budget_used=0,maximum_total_solver_iterations=SOLVER_MAXITER,
                  peak_refinement_history=history,peak_feedback_times_s=feedback_times,
                  peak_verification_work=peak_work,
                  peak_feedback_policy='same 5000 m target; add continuous witnesses; shared iteration/refinement ceilings')
    line=polyline(reference)
    sample_times=np.unique(np.r_[np.arange(0,DURATION+1,5.),reference.breaks])
    q0=reference.values(sample_times)
    basis=offset_basis(reference,sample_times,side)
    peak=float(point_segment(q0+basis@np.ones(3),line['a'],line['b'])[0].min(axis=1).max())
    if peak<=POSITION_TOL:raise PathRejected('initial_cross_track_unresolved')
    initial=np.full(3,PEAK/peak)
    # Exact polynomial quadrature: squared jerk has degree <=10 per interval.
    nodes,weights=np.polynomial.legendre.leggauss(6)
    quad_t=np.concatenate([(a+b)/2+nodes*(b-a)/2 for a,b,_ in reference.pieces])
    quad_w=np.concatenate([weights*(b-a)/2 for a,b,_ in reference.pieces])
    j0=reference.values(quad_t,3)
    jb=offset_basis(reference,quad_t,side,3)
    def jerk(x):return float(np.sum(quad_w[:,None]*(j0+jb@x)**2))
    scale=max(jerk(initial),np.finfo(float).tiny)
    def objective(x):return jerk(x)/scale
    def gradient(x):return 2*np.einsum('n,nd,ndk->k',quad_w,j0+jb@x,jb)/scale
    # SLSQP ftol has a normalized absolute meaning. Squaring a positional error
    # tolerance does not buy physical accuracy; it can prevent useful steps.
    # Independent continuous verifiers still enforce every approved budget.
    ftol=min(POSITION_TOL/PEAK,SPEED_TOL/MAX_SPEED,ACCELERATION_TOL/MAX_LONGITUDINAL,HEADING_TOL)
    used=0;iterations=0
    while True:
        remaining=SOLVER_MAXITER-used
        if remaining<=0:raise PathRejected('continuous_peak_solver_budget_exhausted')
        # Only constraint evaluation times grow. The objective, route family,
        # initial route on the first solve, and all physical limits stay fixed.
        q0=reference.values(sample_times)
        basis=offset_basis(reference,sample_times,side)
        velocity=reference.values(sample_times,1);acceleration=reference.values(sample_times,2)
        velocity_basis=offset_basis(reference,sample_times,side,1)
        acceleration_basis=offset_basis(reference,sample_times,side,2)
        def constraints(x):return sampled_motion_constraints(x,velocity,acceleration,velocity_basis,acceleration_basis)[0]
        def constraint_jacobian(x):return sampled_motion_constraints(x,velocity,acceleration,velocity_basis,acceleration_basis)[1]
        def peak_eq(x):return sampled_peak_constraint(x,q0,basis,line)[0]
        def peak_jacobian(x):return sampled_peak_constraint(x,q0,basis,line)[1]
        fit=minimize(objective,initial,jac=gradient,method='SLSQP',bounds=[(0,None)]*3,
                     constraints=[{'type':'eq','fun':peak_eq,'jac':peak_jacobian},
                                  {'type':'ineq','fun':constraints,'jac':constraint_jacobian}],
                     options={'ftol':ftol,'maxiter':remaining})
        # A zero-iteration return consumes one unit so feedback cannot create
        # an unbounded sequence of nominally zero-work solver restarts.
        charged=max(1,int(fit.nit));used+=charged;iterations+=int(fit.nit)
        detail.update(solver_calls=detail['solver_calls']+1,solver_iterations=iterations,
                      solver_last_iterations=int(fit.nit),solver_budget_used=used,
                      solver_success=bool(fit.success),solver_message=str(fit.message),solver_ftol=ftol)
        if not np.isfinite(fit.x).all() or np.any(fit.x<0):raise PathRejected('invalid_solver_controls')
        final_ineq=constraints(fit.x)
        detail.update(
                           solver_candidate_controls_m=(fit.x*PEAK).tolist(),
                           solver_peak_error_m=float(peak_eq(fit.x)*PEAK),
                           solver_minimum_sampled_constraint_margin=float(final_ineq.min()),
                           solver_failed_sampled_constraints=int(np.count_nonzero(final_ineq<0)),
                           solver_sampled_constraint_failures=dict(zip(
                               ['horizontal_speed','speed_retention','longitudinal_acceleration','lateral_acceleration'],
                               np.count_nonzero(final_ineq.reshape(4,-1)<0,axis=1).tolist())),
                           solver_peak_active_branch=sampled_peak_constraint(fit.x,q0,basis,line)[2])
        step=dict(solver_call=detail['solver_calls'],solver_iterations=int(fit.nit),
                  solver_budget_remaining=max(0,SOLVER_MAXITER-used),
                  constraint_time_count=len(sample_times),solver_success=bool(fit.success),
                  sampled_peak_error_m=detail['solver_peak_error_m'],
                  controls_m=detail['solver_candidate_controls_m'])
        history.append(step)
        if used>SOLVER_MAXITER:raise PathRejected('continuous_peak_solver_budget_exhausted')
        if not fit.success:raise PathRejected('no_validated_path_solver_failed')
        pieces=construct(reference,fit.x,side)
        bounds=peak_bounds(pieces,line,work=peak_work)
        step.update(continuous_peak_distance_bounds_m=list(bounds[:2]),peak_witness_t_s=float(bounds[2]),
                    cumulative_peak_refinements=peak_work['used'])
        detail.update(continuous_peak_distance_bounds_m=list(bounds[:2]),peak_witness_t_s=float(bounds[2]))
        if bounds[0]>=PEAK-POSITION_TOL and bounds[1]<=PEAK+POSITION_TOL:break
        if used>=SOLVER_MAXITER:raise PathRejected('continuous_peak_solver_budget_exhausted')
        # Recompute a continuous witness after EVERY solve; never assume the
        # previous maximum remains the maximum of the modified route.
        witness=float(bounds[2])
        if not np.isfinite(witness) or not 0<=witness<=DURATION:
            raise PathRejected('invalid_continuous_peak_witness')
        if np.any(sample_times==witness):
            raise PathRejected('continuous_cross_track_not_fixed_5km_feedback_stalled')
        feedback_times.append(witness)
        sample_times=np.unique(np.r_[sample_times,witness])
        initial=fit.x.copy()
    movement=verify_motion(pieces,reference)
    projection=verify_projection(pieces,line,side)
    for at in [0,DURATION]:
        for order,tolerance in [(0,POSITION_TOL),(1,SPEED_TOL),(2,ACCELERATION_TOL)]:
            if np.linalg.norm(sample_pieces(pieces,[at],order)-sample_pieces(reference.pieces,[at],order))>tolerance:
                raise PathRejected('maneuver_join_mismatch')
        v=sample_pieces(pieces,[at],1)[0];r=sample_pieces(reference.pieces,[at],1)[0]
        angle=abs(np.arctan2(v[0]*r[1]-v[1]*r[0],v@r))
        if angle>HEADING_TOL:raise PathRejected('maneuver_heading_join_mismatch')
    if diagnostics is not None:diagnostics.update(continuous_peak_distance_bounds_m=list(bounds[:2]),controls_m=(fit.x*PEAK).tolist(),integrated_squared_jerk=jerk(fit.x),continuous_motion=movement,projection_intervals=projection,reference=reference.metadata)
    return sample_pieces(pieces,np.arange(0,DURATION+1,sample_s))+reference.origin


def generate_segmented(reference,side,diagnostics=None,*,peak=None,ramp_s=150.,plateau_end_s=450.,blend_s=30.,sample_s=10.):
    """Piecewise-straight vectoring stimulus (schematic, not C2-certified).

    The offset is a trapezoid in the chord-normal direction: a straight
    diagonal out, a straight plateau at the target offset, and a straight
    diagonal back. A short moving-average blend rounds the three corners
    without smoothing the long legs. This is intentionally not the smooth
    minimum-jerk family; the point is to test whether a segmented,
    ATC-heading-like geometry is easier for the Encoder to see.

    The function fixes the spatial peak (default PEAK, 15 km) and the endpoint
    joins. It does not claim the smooth generator's 2 m/s^2 / 35-degree motion
    certificate; callers that need it must use generate().
    """
    if side not in (-1,1):raise ValueError('side must be -1 or +1')
    target=float(PEAK if peak is None else peak)
    if target<=POSITION_TOL:raise PathRejected('invalid_segmented_peak')
    sample=float(sample_s)
    if not (0<ramp_s<plateau_end_s<DURATION):raise PathRejected('invalid_segmented_breakpoints')
    dense=np.arange(0,DURATION+1e-9,1.0)
    refd=reference.values(dense)+reference.origin
    axis=refd[-1]-refd[0]
    length=float(np.linalg.norm(axis))
    if length<=POSITION_TOL:raise PathRejected('reference_ambiguous_chord')
    axis=axis/length
    normal=side*np.array([-axis[1],axis[0]])
    offset=np.zeros_like(dense)
    up=(dense>=0)&(dense<ramp_s);offset[up]=target*dense[up]/ramp_s
    flat=(dense>=ramp_s)&(dense<=plateau_end_s);offset[flat]=target
    down=(dense>plateau_end_s)&(dense<=DURATION);offset[down]=target*(DURATION-dense[down])/(DURATION-plateau_end_s)
    width=max(1,int(round(blend_s)))
    kernel=np.ones(width)/width
    offset=np.convolve(np.r_[np.zeros(width//2),offset,np.zeros(width-1-width//2)],kernel,'valid')
    offset[0]=0.;offset[-1]=0.
    line=polyline(reference)
    measured=0.
    for _ in range(3):
        qd=refd+offset[:,None]*normal
        measured=float(point_segment(qd-reference.origin,line['a'],line['b'])[0].min(axis=1).max())
        if measured<=POSITION_TOL:raise PathRejected('segmented_cross_track_unresolved')
        if abs(measured-target)<=0.01:break
        offset*=target/measured
        offset[0]=0.;offset[-1]=0.
    qd=refd+offset[:,None]*normal
    times=np.arange(0,DURATION+1e-9,sample)
    q=np.column_stack([np.interp(times,dense,qd[:,0]),np.interp(times,dense,qd[:,1])])
    q[0]=refd[0];q[-1]=refd[-1]
    if diagnostics is not None:
        v=np.diff(q,axis=0)/sample
        speed=np.linalg.norm(v,axis=1)
        acc=np.diff(v,axis=0)/sample
        mid=(v[1:]+v[:-1])/2;midnorm=np.linalg.norm(mid,axis=1)
        longitudinal=np.abs(np.sum(acc*mid,axis=1)/np.maximum(midnorm,1e-6))
        lateral=np.abs(acc[:,0]*mid[:,1]-acc[:,1]*mid[:,0])/np.maximum(midnorm,1e-6)
        heading=np.arctan2(v[:,1],v[:,0])
        turn=np.abs(np.arctan2(np.sin(np.diff(heading)),np.cos(np.diff(heading))))/sample
        diagnostics.update(method=MODEL+'-segmented',numerics='trapezoid-chord-normal-moving-average-v1',
                           peak_cross_track_m=target,peak_measured_m=measured,
                           ramp_s=float(ramp_s),plateau_end_s=float(plateau_end_s),blend_s=float(blend_s),
                           maximum_horizontal_speed_m_s=float(speed.max()),
                           minimum_horizontal_speed_m_s=float(speed.min()),
                           maximum_longitudinal_acceleration_m_s2=float(longitudinal.max()),
                           maximum_lateral_acceleration_m_s2=float(lateral.max()),
                           maximum_turn_rate_rad_s=float(turn.max()),
                           kinematic_certificate=False,
                           note='schematic segmented stimulus; the smooth-generator C2/motion certificate does not apply')
    return q
