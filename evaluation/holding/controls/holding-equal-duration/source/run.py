"""Approved paired terminal-append experiment; preserve all earlier results."""
from pathlib import Path
import hashlib, json, os, sys, time, zipfile
ROOT = Path(__file__).resolve().parent
B = ROOT.parent
WS = B / 'evaluation-10s/workspace'
sys.dont_write_bytecode = True
sys.path[:0] = [str(B/'evaluation-python-deps'), str(WS), str(WS/'evaluation/code')]
os.environ['ATM_DATA_ZIP'] = str(B/'evaluation-10s/scene-inputs.zip')
os.environ['ATM_ENCODER_CHECKPOINT'] = str(B/'encoder-10s/encoder/encoder.pt')
import numpy as np
import scipy, torch
from scipy.spatial.distance import pdist
import run_holding_eval as h
from Encoder.trajectory_encoder.inference import FrozenEncoder
from complexity.calculator import ComplexityConfig, estimate_complexity
from truncation import curve_correlation

SCENES = ['2026-09-01T01Z','2026-09-04T08Z','2026-09-07T10Z','2026-09-10T06Z',
          '2026-09-12T15Z','2026-09-15T06Z','2026-09-18T00Z','2026-09-20T04Z',
          '2026-09-23T10Z','2026-09-25T23Z','2026-09-28T07Z','2026-09-30T15Z']
def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, obj): Path(p).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding='utf8')

def append_pair(p):
    """Existing racetrack geometry relocated to endpoint; matched straight arm."""
    tangent = p[-1,:2] - p[-2,:2]
    if not np.isfinite(tangent).all() or np.linalg.norm(tangent) == 0:
        raise ValueError('undefined_endpoint_heading')
    # Same local speed rule as the original Holding, evaluated at the endpoint.
    speed_samples = np.linalg.norm(np.diff(p[-4:,:2], axis=0), axis=1) / h.SAMPLE_S
    usable = speed_samples[speed_samples > 1]
    if not len(usable):
        raise ValueError('no_existing_rule_speed_support')
    speed = float(np.median(usable))
    if speed > 500:
        raise ValueError('endpoint_speed_over_existing_500_m_s')
    phi = float(np.arctan2(tangent[1], tangent[0]))
    omega, dt = h.TURN_RATE, h.SAMPLE_S
    nturn, nleg = int(round(np.pi/omega/dt)), int(round(h.LEG_S/dt))
    assert 2*(nturn+nleg)*dt == 240 and dt == 10
    cur = p[-1,:2].copy(); z = p[-1,2]
    loop = []
    for _ in range(2):
        origin = cur.copy()
        direction = np.array([np.cos(phi), np.sin(phi)])
        for k in range(1,nleg+1):
            loop.append(np.r_[origin+direction*speed*dt*k, z])
        origin = loop[-1][:2].copy()
        for k in range(1,nturn+1):
            theta = phi+omega*dt*k
            xy = origin + speed/omega*np.array([np.sin(theta)-np.sin(phi), -np.cos(theta)+np.cos(phi)])
            loop.append(np.r_[xy,z])
        cur = loop[-1][:2].copy(); phi += np.pi
    extra_h = np.asarray(loop)
    closure = float(np.linalg.norm(extra_h[-1]-p[-1]))
    if closure > 1e-6: raise ValueError('circuit_did_not_close_naturally')
    extra_h[-1] = p[-1]
    direction = tangent/np.linalg.norm(tangent)
    extra_s = np.column_stack((p[-1,:2]+np.arange(1,25)[:,None]*dt*speed*direction, np.full(24,z)))
    holding, straight = np.vstack((p,extra_h)), np.vstack((p,extra_s))
    assert holding.shape == straight.shape == (len(p)+24,3)
    for q in (holding,straight):
        np.testing.assert_array_equal(q[:len(p)],p)
        assert np.isfinite(q).all()
        np.testing.assert_array_equal(q[len(p):,2],np.full(24,z))
        assert np.max(np.linalg.norm(np.diff(q[len(p)-1:,:2],axis=0),axis=1)/dt) <= 500+1e-9
    np.testing.assert_allclose(extra_h[:nleg],extra_s[:nleg],rtol=0,atol=1e-8)
    return holding,straight,dict(speed_m_s=speed,heading_rad=float(np.arctan2(tangent[1],tangent[0])),
        speed_samples_m_s=speed_samples.tolist(),added_points=24,added_duration_s=240,
        continuous_path_length_m=240*speed,closure_error_m=closure,
        sampled_holding_path_length_m=float(np.linalg.norm(np.diff(holding[len(p)-1:,:2],axis=0),axis=1).sum()),
        sampled_straight_path_length_m=float(np.linalg.norm(np.diff(straight[len(p)-1:,:2],axis=0),axis=1).sum()))

def main():
    out = ROOT/'results'; out.mkdir(exist_ok=False)
    inputs = ROOT/'inputs'; inputs.mkdir(exist_ok=False)
    cfg = ComplexityConfig(normalize=False)
    previous = read(WS/'evaluation/results/run-manifest.json')
    old_results = read(WS/'evaluation/results/experiment-results.json')['qc500']['holding']['scenes']
    assert json.loads(json.dumps(cfg.__dict__)) == previous['config']
    assert sha(h.CHECKPOINT) == previous['checkpoint_sha256'] == 'bc1e0d74255cfee60a1c09c64dab8fac5a31f3175c4c234f8cf3983bc07af976'
    protected = {str(p):sha(p) for folder in [B/'evaluation-10s', B/'encoder-10s/encoder',
        B/'four-scene-vectoring-evaluation', B/'vectoring-existing-result-diagnosis']
        for p in folder.rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    write(ROOT/'before-hashes.json',protected)
    policy = dict(approval='User approved terminal append: original 12 Holding scenes, frozen 10s Encoder, +240s in each arm',
        scenes=SCENES,primary_qc='Existing QC500 only; no additional sensitivity experiment',
        checkpoint_sha256=sha(h.CHECKPOINT),D_config=cfg.__dict__,
        baseline='Same reader, barometric altitude, source QC and bounded time alignment as prior strict-10s Holding; all original sampled points retained',
        timing='Strict 10s; add exactly 24 samples beyond each trajectory endpoint; this is synthetic continuation, not recovered observations',
        heading='Direction of last observed input segment; reject exactly zero/undefined tangent; no imputation or default direction',
        speed='Original local median of segment speeds >1m/s, evaluated at endpoint (last three segments); reject absent support instead of old 220m/s fallback; reject >500m/s',
        holding='Existing left-turn closed racetrack: 60s straight +60s 180-degree turn +60s straight +60s 180-degree turn; turn rate 3deg/s',
        straight='240s constant-speed, constant-heading flight from same endpoint; same speed and constant local ENU z as Holding',
        matching='Same aircraft, anchor, starting direction, speed, added duration, point count, continuous path length and injection order in both arms',
        candidate_failure='Reject pair from injection only; retain original trajectory in shared background; save reason',
        ordering='Original Holding seeds 43 + one-based scene index*1009 + replicate 0..4; permute legacy reader IDs then filter QC and pair eligibility',
        dose='All integer doses from zero through all pair-eligible aircraft; five matched orders; no cutoff or outcome-based selection',
        radii='Same 64 geometric baseline-distance scales, fixed for both arms and all doses within each scene; original dynamic eligibility of fit scales unchanged',
        correlation='Original Spearman eligibility: at least 5 status-ok finite D doses; report individual-arm and same-dose joint-valid correlations',
        paired_effect='Holding D minus straight D at identical scene/order/dose only where both estimates valid; baseline-relative comparisons additionally require valid baseline',
        aggregation='Scene summaries and equal-scene descriptive medians; repeated orders and doses are not independent observations; no p-values',
        interpretation='Equal-duration/point-count control for terminal continuation; not a replay of midpoint Holding and not proof of physical traffic complexity. Geometry/location and final endpoint differ by design.',
        restrictions=dict(vectoring_runs=0,new_downloads=0,retraining=0,threshold_relaxation=0,original_point_edits=0,truncations=0))
    write(ROOT/'policy.json',policy)
    assignments=[]; audits=[]; started=time.monotonic()
    with zipfile.ZipFile(h.DATA_ZIP) as archive:
        for si,sid in enumerate(SCENES,1):
            member=f'OpenSky_Changi_2026-09/sampled_10s/{sid}.csv.gz'
            legacy=h.read_scene(archive,member,max_horizontal_speed=None)
            qc_audit=[]; tracks=h.read_scene(archive,member,max_horizontal_speed=500.,audit=qc_audit)
            ids=sorted(tracks); old=next(t for t in old_results if t['scene_id']==sid)
            assert len(ids)==old['n_aircraft']
            arrays={}; rows=[]; eligible=[]
            for i,a in enumerate(ids):
                p=tracks[a]; arrays[a+'_baseline']=p
                try:
                    hold,straight,diagnostics=append_pair(p)
                    arrays[a+'_holding']=hold; arrays[a+'_straight']=straight
                    eligible.append(i)
                    rows.append(dict(icao24=a,eligible=True,original_points=len(p),**diagnostics))
                except ValueError as exc:
                    rows.append(dict(icao24=a,eligible=False,reason=str(exc),original_points=len(p)))
            np.savez_compressed(inputs/(sid+'-trajectories.npz'),**arrays)
            legacy_ids=sorted(legacy); lookup={a:i for i,a in enumerate(ids)}
            repeats=[]
            for rep in range(5):
                seed=43+si*1009+rep
                order=[lookup[legacy_ids[int(j)]] for j in np.random.default_rng(seed).permutation(len(legacy_ids))
                    if legacy_ids[int(j)] in lookup and lookup[legacy_ids[int(j)]] in eligible]
                assert sorted(order)==eligible
                repeats.append(dict(replicate=rep,seed=seed,order=order,aircraft_order=[ids[j] for j in order]))
            assignments.append(dict(scene=sid,aircraft_ids=ids,eligible_indices=eligible,repeats=repeats))
            audits.append(dict(scene=sid,legacy_count=len(legacy),background=len(ids),eligible=len(eligible),
                rejected=len(ids)-len(eligible),candidates=rows,source_qc_audit=qc_audit))
    # Freeze data and assignments before any new inference or D calculation.
    write(ROOT/'assignments.json',assignments); write(ROOT/'geometry-audit.json',audits)
    torch.set_num_threads(2)
    enc=FrozenEncoder(h.CHECKPOINT,pooling='sum',device='cuda' if torch.cuda.is_available() else 'cpu')
    assert enc.preprocess['preprocessing']['stride_s']==10 and enc.preprocess['preprocessing']['include_endpoint'] is False
    assert enc.preprocess['preprocessor_id']==previous['encoder_preprocessor_id']
    assert str(enc.device)==previous['device']
    manifest=dict(state='running',policy_sha256=sha(ROOT/'policy.json'),assignments_sha256=sha(ROOT/'assignments.json'),
        checkpoint_sha256=sha(h.CHECKPOINT),preprocessor_id=enc.preprocess['preprocessor_id'],
        input_zip_sha256=sha(h.DATA_ZIP),device=str(enc.device),numpy=np.__version__,scipy=scipy.__version__,torch=torch.__version__,
        source_sha256={str(p):sha(p) for p in [Path(__file__),WS/'evaluation/code/run_holding_eval.py',
            WS/'evaluation/code/position_timeline.py',WS/'evaluation/code/trajectory_quality.py',WS/'evaluation/code/truncation.py',
            WS/'complexity/calculator.py',*sorted((WS/'Encoder/trajectory_encoder').glob('*.py'))]},
        input_sha256={p.name:sha(p) for p in inputs.glob('*.npz')},config=cfg.__dict__)
    write(out/'run-manifest.json',manifest)
    trials=[]; checks=[]; calls=0; D_calls=0
    for selection in assignments:
        sid=selection['scene']; ids=selection['aircraft_ids']
        base=[]; hold=[]; straight=[]
        with np.load(inputs/(sid+'-trajectories.npz')) as source:
            for i,a in enumerate(ids):
                z=enc.encode(source[a+'_baseline'])['embedding']; calls+=1
                base.append(z)
                for arm,target in [('holding',hold),('straight',straight)]:
                    if i in selection['eligible_indices']:
                        target.append(enc.encode(source[a+'_'+arm])['embedding']); calls+=1
                    else: target.append(z.copy())
        base=np.asarray(base,dtype=float); hold=np.asarray(hold,dtype=float); straight=np.asarray(straight,dtype=float)
        assert np.isfinite(base).all() and np.isfinite(hold).all() and np.isfinite(straight).all()
        positive=pdist(base); positive=positive[positive>0]
        if len(positive)==0 or positive.min()==positive.max(): raise RuntimeError('No baseline radius span; no automatic fallback')
        radii=np.geomspace(positive.min(),positive.max(),64)
        def estimate(points):
            nonlocal D_calls
            D_calls+=1
            return estimate_complexity(points,config=cfg,radii=radii,scene_id=sid).to_dict()
        baseline=estimate(base)
        old=next(t['dose_curve'][0] for t in old_results if t['scene_id']==sid)
        for key in ['status','reason','dimension','r_squared','n_samples','n_unique']:
            assert baseline[key]==old[key], (sid,key,baseline[key],old[key])
        checks.append(dict(scene=sid,baseline_identical_to_prior=True,status=baseline['status'],D=baseline['dimension']))
        np.savez_compressed(out/(sid+'-embeddings.npz'),baseline=base,holding=hold,straight=straight,radii=radii,aircraft_ids=np.asarray(ids))
        for repeat in selection['repeats']:
            curves={}
            for arm,extra in [('holding',hold),('straight',straight)]:
                current=base.copy(); curve=[dict(injected_aircraft=0,**baseline)]
                for dose,j in enumerate(repeat['order'],1):
                    current[j]=extra[j]
                    curve.append(dict(injected_aircraft=dose,**estimate(current)))
                curves[arm]=curve
            trials.append(dict(scene=sid,replicate=repeat['replicate'],n_aircraft=len(ids),n_eligible=len(selection['eligible_indices']),
                seed=repeat['seed'],aircraft_order=repeat['aircraft_order'],curves=curves,
                correlations={arm:curve_correlation(curve,'injected_aircraft') for arm,curve in curves.items()}))
        write(out/'experiment-results.json',trials)
        print(json.dumps(dict(scene=sid,N=len(ids),eligible=len(selection['eligible_indices']),baseline=baseline['dimension'],
            holding_rho=[t['correlations']['holding']['rho'] for t in trials if t['scene']==sid],
            straight_rho=[t['correlations']['straight']['rho'] for t in trials if t['scene']==sid],elapsed_s=round(time.monotonic()-started,1))),flush=True)
    assert all(sha(p)==digest for p,digest in protected.items())
    write(out/'baseline-verification.json',checks)
    manifest.update(state='complete',elapsed_s=time.monotonic()-started,encoding_calls=calls,D_calls=D_calls,
        n_background=sum(len(s['aircraft_ids']) for s in assignments),n_eligible=sum(len(s['eligible_indices']) for s in assignments),
        scenes=len(SCENES),matched_orders=len(trials),old_files_unchanged=True)
    write(out/'run-manifest.json',manifest)
    print('COMPLETE '+json.dumps({k:manifest[k] for k in ['elapsed_s','encoding_calls','D_calls','n_background','n_eligible']}),flush=True)

if __name__=='__main__': main()
