"""Regenerate the frozen 15 km population with a piecewise-straight injection.

Same scenes, same approved candidates, same 600 s window and 15 km peak as the
smooth 15 km arm. Only the lateral offset shape changes: a straight diagonal
out, a straight 15 km plateau, and a straight diagonal back, with a 30 s blend
at the three corners. The smooth-generator motion certificate is deliberately
not applied here (the segmented stimulus is schematic); source quality and the
baseline arrays are unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import make_interp_spline

B = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SCREEN = B / "four-scene-vectoring-screen" / "screening"
SMOOTH = B / "vectoring-15km-star-2026-10-24" / "population-15km"
sys.path[:0] = [str(B / "evaluation-python-deps"),
                str(B / "evaluation-10s" / "workspace" / "evaluation" / "code"),
                str(B / "vectoring-direction-repair" / "code")]
import vectoring_path as path  # noqa: E402  (workspace generator)
import vectoring_reference as reference  # noqa: E402


def rebuild(reference_file):
    saved = np.load(reference_file)
    times = saved["times"]
    n = len(times)
    zero = np.zeros(n)
    fit = reference.WholeTrackFit(float(saved["epoch"]), times, saved["raw_xy"], saved["fitted_xy"],
                                  saved["origin"], saved["radii"], None, {})
    fit.mapping = make_interp_spline(times, np.eye(n), k=5,
                                     bc_type=([(3, zero), (4, zero)], [(3, zero), (4, zero)]))
    return fit, saved


def main():
    smooth_summary = json.loads((SMOOTH / "summary.json").read_text(encoding="utf8"))
    out = HERE / "population-15km-segmented"
    out.mkdir(parents=True, exist_ok=False)
    summary = {"peak_m": 15000.0, "shape": "trapezoid: 150 s out, 300 s plateau, 150 s back, 30 s corner blend",
               "scenes": [], "note": "schematic segmented stimulus; motion certificate not applied"}
    for scene in smooth_summary["scenes"]:
        sid = scene["scene"]
        records = json.loads((SMOOTH / f"{sid}-records.json").read_text(encoding="utf8"))
        smooth = np.load(SMOOTH / f"{sid}-population.npz")
        arrays = {}
        rows = []
        for record in records:
            icao = record["icao24"]
            baseline = smooth[icao + "_baseline"]
            arrays[icao + "_baseline"] = baseline
            if not record.get("new_injectable"):
                rows.append(dict(record, segmented_injectable=False))
                continue
            fit, saved = rebuild(SCREEN / "references" / f"{sid}-{icao}.npz")
            start = (len(baseline) - 60) // 2
            try:
                ref = reference.maneuver_reference(fit, saved["grid"], start)
                injected = {}
                for side, label in ((-1, "left"), (1, "right")):
                    xy = path.generate_segmented(ref, side, peak=15000.0, ramp_s=150.0,
                                                 plateau_end_s=450.0, blend_s=30.0, sample_s=10.0)
                    q = baseline.copy()
                    q[start:start + 61, :2] = xy
                    injected[label] = q
                arrays[icao + "_left"] = injected["left"]
                arrays[icao + "_right"] = injected["right"]
                rows.append(dict(record, segmented_injectable=True))
            except Exception as exc:
                rows.append(dict(record, segmented_injectable=False, segmented_reason=str(exc)))
        np.savez_compressed(out / f"{sid}-population.npz", **arrays)
        (out / f"{sid}-records.json").write_text(json.dumps(rows, indent=2), encoding="utf8")
        injectable = [r["icao24"] for r in rows if r.get("segmented_injectable")]
        summary["scenes"].append(dict(scene=sid, background=len(rows), injectable_before=len(scene["injectable"]),
                                      injectable_after=len(injectable), injectable=injectable))
        print(json.dumps(summary["scenes"][-1]), flush=True)
    summary["totals"] = dict(background=sum(s["background"] for s in summary["scenes"]),
                             injectable_before=sum(s["injectable_before"] for s in summary["scenes"]),
                             injectable_after=sum(s["injectable_after"] for s in summary["scenes"]))
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    print("SEGMENTED POPULATION COMPLETE " + json.dumps(summary["totals"]), flush=True)


if __name__ == "__main__":
    main()
