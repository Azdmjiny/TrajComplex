"""Whole-track NACp-constrained minimum-jerk fit, independent of Encoder/D.

Only genuine position-update times are knots. The natural quintic cardinal
basis spans the full approved spline space (third/fourth endpoint derivatives
zero). Fitted knot values are constrained to the existing observation disks.
The zero-jerk quadratic nullspace is resolved lexicographically, not with a
smoothing penalty. Uncertainty remains conditional on the natural spline model.
"""
from pathlib import Path as _LayoutPath
import sys as _layout_sys
_layout_sys.path.insert(0, str(_LayoutPath(__file__).resolve().parents[2] / "code"))
from evaluation_layout import EVALUATION_ROOT, study_path, configure_imports
configure_imports()
from dataclasses import dataclass
import math
import numpy as np
from scipy import sparse
from scipy.interpolate import make_interp_spline
import clarabel
import vectoring_path as path

FIT_MODEL = 'full-track-natural-quintic-nacp-constrained-minimum-jerk-v1'
DIRECTION_CERTIFICATE = 'raw-velocity-disk-local-cone-adaptive-v1'


def _solve(P, q, A, b, cones, diagnostics, name, *, allow_infeasible=False):
    settings = clarabel.DefaultSettings()
    settings.verbose = False
    settings.max_iter = 200
    settings.tol_gap_abs = settings.tol_gap_rel = settings.tol_feas = 1e-8
    solver = clarabel.DefaultSolver(sparse.triu(sparse.csc_matrix(P)).tocsc(),
                                   np.asarray(q), sparse.csc_matrix(A),
                                   np.asarray(b), cones, settings)
    result = solver.solve()
    diagnostics[name] = dict(status=str(result.status), iterations=result.iterations,
                            primal_residual=float(result.r_prim),
                            dual_residual=float(result.r_dual))
    if allow_infeasible and str(result.status) == 'PrimalInfeasible':
        return None
    if str(result.status) != 'Solved':
        raise path.PathRejected('reference_' + name + '_' + str(result.status))
    x = np.asarray(result.x, dtype=float)
    if not np.isfinite(x).all():
        raise path.PathRejected('reference_nonfinite_solution')
    return x


@dataclass
class WholeTrackFit:
    epoch: float
    times: np.ndarray
    raw_xy: np.ndarray
    fitted_xy: np.ndarray
    origin: np.ndarray
    radii: np.ndarray
    mapping: object
    metadata: dict

    def positions(self, absolute_times):
        t = np.asarray(absolute_times) - self.epoch
        if np.any(t < self.times[0]) or np.any(t > self.times[-1]):
            raise path.PathRejected('reference_extrapolation')
        return self.mapping(t) @ self.fitted_xy + self.origin


def fit_track(xy, times, radii, diagnostics=None):
    """Fit once before route eligibility; failure leaves the raw background."""
    d = {} if diagnostics is None else diagnostics
    xy, times, radii = map(lambda a: np.asarray(a, dtype=float), (xy, times, radii))
    n = len(times)
    if n < 6 or xy.shape != (n, 2) or radii.shape != (n,):
        raise path.PathRejected('invalid_full_track_fit_support')
    if not all(np.isfinite(a).all() for a in (xy, times, radii)) or np.any(np.diff(times) <= 0) or np.any(radii <= 0):
        raise path.PathRejected('invalid_full_track_fit_support')
    epoch = float(times[0]); t = times - epoch
    origin = xy[0].copy(); y = xy - origin
    zero = np.zeros(n)
    mapping = make_interp_spline(t, np.eye(n), k=5,
                                bc_type=([(3, zero), (4, zero)], [(3, zero), (4, zero)]))
    # Exact polynomial quadrature; no smoothing length or new physical limit.
    nodes, weights = np.polynomial.legendre.leggauss(6)
    qt = np.concatenate([(a+b)/2 + nodes*(b-a)/2 for a,b in zip(t[:-1], t[1:])])
    qw = np.concatenate([weights*(b-a)/2 for a,b in zip(t[:-1], t[1:])])
    J = mapping(qt, nu=3) * np.sqrt(qw[:, None])
    # Removing a quadratic trend improves arithmetic without changing jerk.
    u = (t - t[-1]/2) / t[-1]
    B = np.column_stack((np.ones(n), u, u*u))
    trend = B @ np.linalg.lstsq(B, y, rcond=None)[0]
    j0 = J @ (y - trend)
    M = J * radii[None, :]
    scale = max(float(np.sum(M*M)), float(np.sum(j0*j0)), np.finfo(float).tiny)
    Q = 2*(M.T @ M)/scale
    P = sparse.block_diag((sparse.csc_matrix(Q), Q), format='csc')
    q = np.r_[2*M.T@j0[:, 0]/scale, 2*M.T@j0[:, 1]/scale]
    # x stores per-observation displacements divided by the existing radii.
    A = sparse.lil_matrix((3*n, 2*n)); b = np.zeros(3*n)
    for i in range(n):
        b[3*i] = 1
        A[3*i+1, i] = -1
        A[3*i+2, n+i] = -1
    cones = [clarabel.SecondOrderConeT(3) for _ in range(n)]
    # Resolve the zero-jerk case FIRST. If a quadratic lies in all disks, its
    # weighted least-squares optimum is exactly the lexicographic solution.
    # Otherwise the positive-jerk optimum is unique (see specification): two
    # minimizers can differ only by a quadratic, while strict disk convexity
    # and stationarity on the quadratic nullspace rule out a nonzero difference.
    # A second boundary-only conic solve after a positive-jerk optimum is thus
    # redundant and numerically ill-conditioned. No thresholds are changed.
    Z = B/radii[:, None]
    residual = (trend-y)/radii[:, None]
    P2 = sparse.block_diag((sparse.csc_matrix(2*Z.T@Z), 2*Z.T@Z), format='csc')
    q2 = np.r_[2*Z.T@residual[:, 0], 2*Z.T@residual[:, 1]]
    A2 = np.zeros((3*n, 6)); b2 = np.zeros(3*n)
    for i in range(n):
        b2[3*i:3*i+3] = [1, residual[i, 0], residual[i, 1]]
        A2[3*i+1, :3] = -Z[i]
        A2[3*i+2, 3:] = -Z[i]
    x2 = _solve(P2, q2, A2, b2, cones, d, 'quadratic_tie_break',allow_infeasible=True)
    if x2 is not None:
        fitted = trend + np.column_stack((B@x2[:3], B@x2[3:]))
        d['minimum_jerk'] = dict(status='ExactZeroJerkQuadratic',iterations=0)
        d['unique_solution_basis'] = 'strictly convex normalized residual objective on quadratic nullspace'
    else:
        x = _solve(P, q, A, b, cones, d, 'minimum_jerk')
        fitted = y + radii[:, None]*np.column_stack((x[:n], x[n:]))
        d['unique_solution_basis'] = 'positive-jerk optimum unique under strictly convex observation disks'
    residual_m = np.linalg.norm(fitted-y, axis=1)
    d.update(method=FIT_MODEL, source_points=n, minimum_knot_gap_s=float(np.diff(t).min()),
             maximum_source_residual_m=float(residual_m.max()),
             maximum_residual_to_radius_ratio=float(np.max(residual_m/radii)),
             integrated_squared_jerk=float(np.sum((J@(fitted-trend))**2)),
             clarabel_version=clarabel.__version__, max_iter=200,
             tol_gap_abs=1e-8, tol_gap_rel=1e-8, tol_feas=1e-8,
             reference_epoch=epoch, interpolation_grid_used_as_knots=False)
    # Solver success is not an acceptance certificate. No positional allowance
    # is added to NACp disks, and no solution is clipped/projected into a disk.
    if not np.isfinite(fitted).all() or np.any(residual_m > radii):
        raise path.PathRejected('reference_outside_nacp_disks')
    if np.max(np.linalg.norm(mapping(t)@fitted - fitted, axis=1)) > path.POSITION_TOL:
        raise path.PathRejected('reference_knot_precision_unresolved')
    # Independent piece evaluation of position/velocity/acceleration over the
    # entire fitted trajectory; same existing numerical budgets.
    for a, b in zip(t[:-1], t[1:]):
        h = b-a
        w = _weights(mapping, a, h)
        c = w@fitted
        for order, tolerance in [(0,path.POSITION_TOL),(1,path.SPEED_TOL),(2,path.ACCELERATION_TOL)]:
            if np.linalg.norm(path.middle(c)-mapping((a+b)/2, nu=order)@fitted) > tolerance:
                raise path.PathRejected('reference_representation_precision_unresolved')
            c = path.derivative(c, h)
    d['conditional_model'] = 'NACp engineering disks and natural quintic spline; not simultaneous confidence or physical truth'
    return WholeTrackFit(epoch, t, y, fitted, origin, radii, mapping, dict(d))


def _weights(mapping, a, h):
    power = np.array([mapping(a, nu=j)*h**j/math.factorial(j) for j in range(6)])
    return np.array([sum(math.comb(i,j)/math.comb(5,j)*power[j] for j in range(i+1)) for i in range(6)])


class _ShiftedMapping:
    def __init__(self, mapping, start):
        self.mapping, self.start = mapping, start
    def __call__(self, t, nu=0):
        return self.mapping(np.asarray(t)+self.start, nu=nu)


def _direction_point(vw, fit):
    """Exact velocity-disk/cone test at one time, conditional on source disks."""
    raw = vw@fit.raw_xy; fitted = vw@fit.fitted_xy
    radius = float(np.abs(vw)@fit.radii)
    speed = float(np.linalg.norm(fitted)); raw_speed = float(np.linalg.norm(raw))
    dot = float(raw@fitted)
    cross = float(fitted[0]*raw[1]-fitted[1]*raw[0])
    margin = math.sin(path.DIRECTION_ERROR)*dot-math.cos(path.DIRECTION_ERROR)*abs(cross)-radius*speed
    angle = None
    if speed>0 and raw_speed>radius:
        angle = math.degrees(min(math.pi,math.atan2(abs(cross),dot)+math.asin(radius/raw_speed)))
    return dict(passed=bool(speed>0 and raw_speed>radius and margin>=0),
                cone_margin=float(margin),maximum_direction_error_deg=angle,
                velocity_disk_radius_m_s=radius,velocity_disk_includes_zero=bool(raw_speed<=radius),
                fitted_speed_m_s=speed)


def _direction_interval(vw, fit):
    """Continuous cone enclosure preserving raw/fitted velocity dependence."""
    raw = vw@fit.raw_xy; fitted = vw@fit.fitted_xy
    dot = path.bernstein_product(raw[:,0],fitted[:,0])+path.bernstein_product(raw[:,1],fitted[:,1])
    cross = path.bernstein_product(fitted[:,0],raw[:,1])-path.bernstein_product(fitted[:,1],raw[:,0])
    radius = float(np.max(np.abs(vw)@fit.radii))
    vmax = float(np.max(np.linalg.norm(fitted,axis=1)))
    margin = math.sin(path.DIRECTION_ERROR)*float(dot.min())-math.cos(path.DIRECTION_ERROR)*float(np.abs(cross).max())-radius*vmax
    passed = np.isfinite(margin) and margin>=0 and float(dot.min())>0 and path.norm_lower(path.hull(fitted))>0
    return bool(passed),float(margin)


def certify_local_direction(fit, intervals, start):
    """Bound all maneuver/join times; witness failure and unresolved differ.

    The source disks and 10-degree limit are unchanged. No radius is shrunk,
    no statistical independence is assumed, and no sampled-only pass is used.
    A single existing verification-node budget covers the entire support.
    """
    pending = list(intervals); nodes = 0; subdivisions = 0; leaves = 0
    minimum = None
    def result(status, **extra):
        return dict(method=DIRECTION_CERTIFICATE,status=status,nodes=nodes,
                    subdivisions=subdivisions,accepted_leaves=leaves,
                    minimum_accepted_cone_margin=minimum,
                    limit_deg=float(np.rad2deg(path.DIRECTION_ERROR)),**extra)
    while pending:
        if nodes>=path.MAX_VERIFY_NODES:
            return result('unresolved',cause='verification_budget_exhausted')
        a,b,vw = pending.pop(); nodes += 1
        passed,margin = _direction_interval(vw,fit)
        if not np.isfinite(margin):
            return result('unresolved',cause='nonfinite_bound')
        if passed:
            leaves += 1; minimum = margin if minimum is None else min(minimum,margin)
            continue
        # Check both endpoints as well as the midpoint, including joins.
        for t,w in [(a,vw[0]),((a+b)/2,path.middle(vw)),(b,vw[-1])]:
            witness = _direction_point(w,fit)
            if not np.isfinite(witness['cone_margin']):
                return result('unresolved',cause='nonfinite_point')
            if not witness['passed']:
                return result('point_witness_failure',witness=dict(time_s=float(t-start),**witness))
        mid = (a+b)/2
        if not a<mid<b:
            return result('unresolved',cause='floating_point_resolution')
        left,right = path.split(vw)
        pending.extend([(a,mid,left),(mid,b,right)]); subdivisions += 1
    return result('continuous_certificate_pass')


def maneuver_reference(fit, grid, start_index, diagnostics=None):
    """Certify the whole-fit derivatives used for one maneuver and both joins.

    Local direction uses the raw-centered velocity disk directly. The existing
    independent chord-progress and curvature enclosures are retained.
    All full-track observation columns participate, including outside points.
    """
    d = {} if diagnostics is None else diagnostics
    grid = np.asarray(grid, float)
    if len(grid) < 63 or np.any(np.diff(grid) != 10) or start_index < 1 or start_index+61 >= len(grid):
        raise path.PathRejected('missing_maneuver_join_support')
    start = float(grid[start_index]-fit.epoch)
    end = float(grid[start_index+60]-fit.epoch)
    support_start = float(grid[start_index-1]-fit.epoch)
    support_end = float(grid[start_index+61]-fit.epoch)
    if support_start < fit.times[0] or support_end > fit.times[-1] or end-start != path.DURATION:
        raise path.PathRejected('reference_extrapolation')
    mapping = fit.mapping
    chord = (mapping(end)-mapping(start))@fit.fitted_xy
    length = np.linalg.norm(chord)
    if length <= path.POSITION_TOL:
        raise path.PathRejected('reference_ambiguous_chord')
    axis = chord/length
    breaks = np.unique(np.r_[support_start, fit.times[(fit.times>support_start)&(fit.times<support_end)], start, end, support_end])
    pieces = []; angles = []; curvature = []; failures = set(); intervals = []
    chord_failed = []; chord_witnesses = []; curvature_unresolved = False
    for a,b in zip(breaks[:-1],breaks[1:]):
        h = b-a; w = _weights(mapping, a, h)
        vw = path.derivative(w,h); aw = path.derivative(vw,h)
        intervals.append((a,b,vw))
        c = w@fit.fitted_xy; vel = vw@fit.fitted_xy; acc = aw@fit.fitted_xy
        delta = fit.fitted_xy-fit.raw_xy
        ev = float(np.max(np.abs(vw)@fit.radii + np.linalg.norm(vw@delta,axis=1)))
        ea = float(np.max(np.abs(aw)@fit.radii + np.linalg.norm(aw@delta,axis=1)))
        forward = float(np.min(vel@axis))
        vmax = float(np.max(np.linalg.norm(vel,axis=1)))
        amax = float(np.max(np.linalg.norm(acc,axis=1)))
        ratio = ev/forward if forward>0 else None
        angle = float(np.rad2deg(np.arcsin(ratio))) if ratio is not None and 0<=ratio<1 else None
        angles.append(dict(start_s=float(a-start),end_s=float(b-start),forward_lower_m_s=forward,
                           derivative_error_m_s=ev,legacy_chord_angle_bound_deg=angle))
        # Preserve the original forward>ev requirement; do not silently remove
        # a route-family guard when tightening the independent local-angle test.
        if forward<=ev:
            chord_failed.append(dict(start_s=float(a-start),end_s=float(b-start),
                                     forward_lower_m_s=forward,derivative_error_m_s=ev))
            for t,v in [(a,vel[0]),((a+b)/2,path.middle(vel)),(b,vel[-1])]:
                projection = float(v@axis)
                if projection<=0:
                    chord_witnesses.append(dict(time_s=float(t-start),forward_m_s=projection))
        if forward>ev:
            k = (vmax*amax+vmax*ea+amax*ev+ev*ea)/(forward-ev)**3
            if not np.isfinite(k): curvature_unresolved = True
            else: curvature.append([-float(k),float(k)])
        if a>=start and b<=end: pieces.append((float(a-start),float(b-start),c))
    certificate = certify_local_direction(fit,intervals,start)
    if certificate['status']=='point_witness_failure':
        failures.add('continuous_reference_direction_unreliable')
    elif certificate['status']!='continuous_certificate_pass':
        failures.add('continuous_reference_direction_unresolved')
    if chord_failed:
        failures.add('reference_chord_progress_nonpositive' if chord_witnesses else 'reference_chord_progress_uncertified')
    if curvature_unresolved: failures.add('reference_curvature_bound_unresolved')
    d.update(direction_intervals=angles,curvature_intervals=curvature,
             direction_certificate=certificate,
             chord_progress=dict(status='rejected' if chord_failed else 'passed',
                                 criterion='unchanged fitted forward lower bound > recentered derivative-error upper bound',
                                 failed_intervals=chord_failed,nonpositive_witnesses=chord_witnesses),
             curvature_status='blocked_by_chord_progress' if chord_failed else ('unresolved' if curvature_unresolved else 'bounded'),
             uncertainty='exact raw-centered natural-spline velocity disks; continuous local cone; all observation disks; no statistical independence assumption',
             quality_scope='all real updates of fitted track',direction_scope='maneuver and joining neighbor support',
             sample_s=10, method=FIT_MODEL, source_points=len(fit.times))
    if failures:
        d['rejection_reasons'] = sorted(failures)
        raise path.PathRejected('continuous_reference_direction_unreliable' if 'continuous_reference_direction_unreliable' in failures else sorted(failures)[0])
    relative_breaks = np.array([pieces[0][0]]+[b for _,b,_ in pieces])
    return path.Reference(fit.fitted_xy,fit.times-start,fit.radii,_ShiftedMapping(mapping,start),
                          relative_breaks,pieces,axis,fit.origin,dict(d))
