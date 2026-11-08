#!/usr/bin/env python3
"""WSSS 2 trajectory loading and Holding/Vectoring injection primitives."""
from __future__ import annotations
import hashlib, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/WSSS 2'
HOURS = DATA / 'hours'
CHECKPOINT = ROOT / 'Encoder/encoder/4_encoder_60/WSSS_epoch_60.pt'
ARP_E, ARP_N = 0.0, 0.0  # Archive ENU is centered on the WSSS ARP.
DT = 10.0
REPEATS = 10
EVENT_CAP = 15
SEED = 20261107
HOLDING_DURATION_S = 360
HOLDING_LEG_S = 90
HOLDING_TURN_RATE = math.radians(2.0)
VECTOR_WINDOW = 61
VECTOR_PEAK_M = 15000.0
VECTOR_RAMP_S = 150.0
VECTOR_PLATEAU_END_S = 450.0
VECTOR_BLEND_S = 30.0
CHECKPOINT_SHA_EXPECTED = 'c0d98e6cde14baf99d28b7d336c282eb245f1ce485c248c32a58fd9ccf5358e5'
PREPROCESSOR_ID_EXPECTED = 'cee1251c8b373994d009bcda89ee14811623849e762f858b0abe0bb7fbd5b8a5'

def holding_candidate(track):
    idx = len(track) // 2
    if len(track) - idx - 1 < 36:
        return None, 'fewer_than_36_original_tail_points'
    # Latest experiment allows the midpoint Holding anchor at any ARP distance.
    distance = float(np.linalg.norm(track[idx, :2] - np.array([ARP_E, ARP_N])))
    tangent = track[min(idx + 1, len(track)-1), :2] - track[max(0, idx - 1), :2]
    if not np.isfinite(tangent).all() or np.linalg.norm(tangent) == 0:
        return None, 'undefined_midpoint_heading'
    v = np.linalg.norm(np.diff(track[max(0, idx-3):min(len(track), idx+4), :2], axis=0), axis=1) / DT
    v = v[v > 1.0]
    if not len(v):
        return None, 'no_midpoint_speed_support'
    speed = float(np.median(v))
    if speed > 500:
        return None, 'midpoint_speed_over_500m_s'
    heading = float(math.atan2(tangent[1], tangent[0]))
    block, closure = holding_racetrack(track[idx], heading, speed)
    return {'index': idx, 'speed': speed, 'heading': heading, 'block': block, 'closure': closure, 'anchor_distance_m': distance}, None

def holding_inject_trim(state, cand):
    p, tags = state
    before = len(p)
    idx = cand['index']
    while idx + 1 < len(tags) and tags[idx+1] == 'holding':
        idx += 1
    q = np.concatenate((p[:idx+1], cand['block'], p[idx+1:]), axis=0)
    kinds = tags[:idx+1] + ['holding'] * 36 + tags[idx+1:]
    removed = {'original': kinds[-36:].count('original'), 'holding': kinds[-36:].count('holding')}
    q, kinds = q[:-36], kinds[:-36]
    if len(q) != before or len(kinds) != before:
        raise AssertionError('holding_track_length_changed')
    return (q, kinds), removed

def holding_racetrack(anchor, heading, speed):
    """Return a closed 360 s, 36-point racetrack at constant local speed."""
    if not np.isfinite(speed) or speed <= 0:
        raise ValueError('invalid_speed')
    nturn = int(round((math.pi / HOLDING_TURN_RATE) / DT))
    nleg = int(round(HOLDING_LEG_S / DT))
    if 2 * (nturn + nleg) != HOLDING_DURATION_S / DT:
        raise AssertionError('holding_point_count_mismatch')
    phi = float(heading)
    z = float(anchor[2])
    cur = np.asarray(anchor[:2], dtype=float).copy()
    out = []
    for _ in range(2):
        origin = cur.copy()
        direction = np.array([math.cos(phi), math.sin(phi)])
        for k in range(1, nleg + 1):
            out.append(np.r_[origin + direction * speed * DT * k, z])
        origin = np.asarray(out[-1][:2]).copy()
        for k in range(1, nturn + 1):
            theta = phi + HOLDING_TURN_RATE * DT * k
            xy = origin + speed / HOLDING_TURN_RATE * np.array([math.sin(theta) - math.sin(phi), -math.cos(theta) + math.cos(phi)])
            out.append(np.r_[xy, z])
        cur = np.asarray(out[-1][:2]).copy()
        phi += math.pi
    block = np.asarray(out)
    closure = float(np.linalg.norm(block[-1] - anchor))
    if closure > 1e-6:
        raise ValueError(f'holding_not_closed:{closure}')
    block[-1] = anchor
    if len(block) != 36:
        raise AssertionError(f'expected 36 inserted samples over 360 seconds, got {len(block)}')
    return block, closure

def holding_sequence(candidates, rng):
    """Sample distinct eligible aircraft; one Holding per aircraft per repeat."""
    pool = sorted(set(candidates))
    return rng.choice(pool, size=min(EVENT_CAP, len(pool)), replace=False).tolist() if pool else []

def load_scene(path):
    with np.load(path, allow_pickle=False) as z:
        ids = z['flight_ids'].astype(str)
        offsets = z['offsets']
        xyz = np.asarray(z['enu_m'], dtype=np.float64)
        ts = np.asarray(z['time'], dtype=np.float64)
        if len(offsets) != len(ids)+1 or offsets[0] != 0 or offsets[-1] != len(xyz) or len(ts) != len(xyz):
            raise ValueError(f'{path.name}: invalid archive offsets/time')
        if not np.all(z['traffic_label'].astype(str) == 'arrival'):
            raise ValueError(f'{path.name}: non-arrival data')
        tracks = {}
        for i, (a, b) in enumerate(zip(offsets[:-1], offsets[1:])):
            a, b = int(a), int(b)
            # Match the WSSS epoch-60 baseline runner's trajectory input precision.
            p, t = np.asarray(xyz[a:b], dtype=np.float32).astype(np.float64), ts[a:b]
            if len(p) < 30 or not np.isfinite(p).all() or len(t) != len(p) or not np.isfinite(t).all() or np.any(np.diff(t) != DT):
                continue
            tracks[ids[i]] = p
        return tracks

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def vector_candidates(track):
    out = []
    for start in range(0, len(track) - VECTOR_WINDOW + 1, VECTOR_WINDOW):
        try:
            sides = {side: vector_segment(track, start, side)[0] for side in (-1, 1)}
            out.append({'start': start, 'sides': sides})
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            continue
    return out

def vector_segment(track, start, side):
    from scipy.interpolate import PchipInterpolator
    source = track[start:start+VECTOR_WINDOW].copy()
    if source.shape != (VECTOR_WINDOW, 3) or side not in (-1, 1):
        raise ValueError('invalid_window_or_side')
    chord = source[-1, :2] - source[0, :2]
    length = np.linalg.norm(chord)
    if length <= 1:
        raise ValueError('ambiguous_window_chord')
    normal = side * np.array([-chord[1], chord[0]]) / length
    t = np.arange(VECTOR_WINDOW) * DT
    dense = np.arange(601, dtype=float)
    center = np.column_stack([PchipInterpolator(t, source[:, j])(dense) for j in (0, 1)])
    off = np.zeros(601)
    up = dense < VECTOR_RAMP_S
    flat = (dense >= VECTOR_RAMP_S) & (dense <= VECTOR_PLATEAU_END_S)
    down = dense > VECTOR_PLATEAU_END_S
    off[up] = VECTOR_PEAK_M * dense[up] / VECTOR_RAMP_S
    off[flat] = VECTOR_PEAK_M
    off[down] = VECTOR_PEAK_M * (600 - dense[down]) / (600 - VECTOR_PLATEAU_END_S)
    k = int(VECTOR_BLEND_S)
    kernel = np.ones(k) / k
    off = np.convolve(np.r_[np.zeros(k//2), off, np.zeros(k-1-k//2)], kernel, 'valid')
    off[0] = off[-1] = 0.0
    line = source[:, :2]
    a = line[:-1]
    ab = np.diff(line, axis=0)
    denom = np.sum(ab * ab, axis=1)
    if (denom <= 1e-12).any():
        raise ValueError('zero_length_reference_segment')
    out = source.copy()
    measured = 0.0
    for _ in range(12):
        displaced = center + off[:, None] * normal
        out[:, :2] = np.column_stack([np.interp(t, dense, displaced[:, j]) for j in (0, 1)])
        out[0], out[-1] = source[0], source[-1]
        delta = out[:, None, :2] - a[None, :, :]
        u = np.clip(np.sum(delta * ab[None, :, :], axis=2) / denom[None, :], 0, 1)
        nearest = a[None, :, :] + u[:, :, None] * ab[None, :, :]
        measured = float(np.linalg.norm(out[:, None, :2] - nearest, axis=2).min(axis=1).max())
        if measured <= 1:
            raise ValueError('segment_cross_track_unresolved')
        if abs(measured - VECTOR_PEAK_M) <= .01:
            break
        off *= VECTOR_PEAK_M / measured
        off[0] = off[-1] = 0.0
    displaced = center + off[:, None] * normal
    out[:, :2] = np.column_stack([np.interp(t, dense, displaced[:, j]) for j in (0, 1)])
    out[0], out[-1] = source[0], source[-1]
    delta = out[:, None, :2] - a[None, :, :]
    u = np.clip(np.sum(delta * ab[None, :, :], axis=2) / denom[None, :], 0, 1)
    nearest = a[None, :, :] + u[:, :, None] * ab[None, :, :]
    measured = float(np.linalg.norm(out[:, None, :2] - nearest, axis=2).min(axis=1).max())
    if abs(measured - VECTOR_PEAK_M) > .1:
        raise ValueError(f'vector_peak_calibration_failed:{measured:.3f}')
    return out, {'peak_measured_m': measured}