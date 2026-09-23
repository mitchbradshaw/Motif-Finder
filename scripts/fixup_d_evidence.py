"""
fixup_d_evidence.py
====================
Prompt D's evidence: `interrogation.event_shape`'s measures of the 410 seed
events (`DATA/library_seed/drop_motifs5/motifs`) against the detector's own
columns in `events.csv` for the same events — depth against `drop_depth_mv`,
width against `fall_duration_s`, steepest slope against `max_slope_raw * 1000`,
and the anatomy (onset, extremum) against `onset_idx` / `trough_idx`.

Each event is measured on the store's own `detrended_mv` snippet — the trace
the detector measured on, and the one the Library's content hash is taken
over — so a disagreement is a disagreement of RULE, not of input. Run twice:
with the block's defaults, and with `walk_onset_back=False`, the flag the seed
store was made under (`Detect5Params`: "False reproduces drop_motifs5-9").

Read-only. Writes `webui/screenshots/fixup/D/seed-comparison.json`.

    python scripts/fixup_d_evidence.py
"""

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.Detection.drop_motifs import store as S  # noqa: E402
from Working.interrogation import event_shape as ES  # noqa: E402

SEED = os.path.join(ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
OUT = os.path.join(ROOT, "webui", "screenshots", "fixup", "D", "seed-comparison.json")


def measure(events, snippets, walk, anchored=False, polarity="drop"):
    rows = []
    for e in events:
        v = np.asarray(snippets[e["event_id"]]["detrended_mv"], dtype=float)
        s0 = int(e["snippet_start_idx"])
        anchors = [(int(e["onset_idx"]) - s0, int(e["trough_idx"]) - s0)] if anchored else None
        f, _ = ES.measure_events(v, [0], [len(v)], float(e["fs"]), to_mv=1.0, walk_onset_back=walk,
                                 anchors=anchors, polarity=polarity)
        r = f.iloc[0]
        rows.append({
            "event_id": e["event_id"], "span_key": e["span_key"], "fs": float(e["fs"]),
            "det_onset": int(e["onset_idx"]) - s0, "det_trough": int(e["trough_idx"]) - s0,
            "onset": r["onset_idx"], "extremum": r["extremum_idx"], "polarity": int(r["polarity"]),
            "det_depth": float(e["drop_depth_mv"]), "depth": float(r["event_amplitude_mv"]),
            "det_width": float(e["fall_duration_s"]), "width": float(r["event_width_s"]),
            "det_slope": float(e["max_slope_raw"]) * 1000.0, "slope": float(r["max_slope_mv_s"]),
            "fwhm": float(r["fwhm_s"]), "recovery": float(r["recovery_time_s"]),
            # the detector's depth re-read off the same snippet at its own anchors
            "det_depth_on_snippet": float(v[int(e["onset_idx"]) - s0] - v[int(e["trough_idx"]) - s0]),
        })
    return rows


def summarise(rows):
    def agree(a, b, tol):
        a, b = np.asarray(a, float), np.asarray(b, float)
        ok = np.isfinite(a) & np.isfinite(b)
        d = np.abs(a[ok] - b[ok])
        return {"n": int(ok.sum()), "exact_within_tol": int((d <= tol).sum()), "tol": tol,
                "median_abs_diff": float(np.median(d)) if d.size else None,
                "p90_abs_diff": float(np.percentile(d, 90)) if d.size else None,
                "max_abs_diff": float(d.max()) if d.size else None}
    R = {k: [r[k] for r in rows] for k in rows[0]}
    same_onset = [r["onset"] == r["det_onset"] for r in rows]
    same_ext = [r["extremum"] == r["det_trough"] for r in rows]
    ext_one_before = [r["extremum"] == r["det_trough"] - 1 for r in rows]
    return {
        "n_events": len(rows),
        "polarity_drop": int(sum(r["polarity"] == -1 for r in rows)),
        "onset_same_sample": int(sum(same_onset)),
        "onset_earlier": int(sum(r["onset"] < r["det_onset"] for r in rows)),
        "onset_later": int(sum(r["onset"] > r["det_onset"] for r in rows)),
        "extremum_same_sample": int(sum(same_ext)),
        "extremum_one_sample_before_knee": int(sum(ext_one_before)),
        "extremum_other": int(len(rows) - sum(same_ext) - sum(ext_one_before)),
        "both_anchors_same": int(sum(a and b for a, b in zip(same_onset, same_ext))),
        "depth_vs_drop_depth_mv": agree(R["depth"], R["det_depth"], 1e-6),
        "depth_vs_detector_anchors_on_snippet": agree(R["det_depth_on_snippet"], R["det_depth"], 1e-6),
        "width_vs_fall_duration_s": agree(R["width"], R["det_width"], 1e-9),
        "slope_vs_max_slope_raw_x1000": agree(R["slope"], R["det_slope"], 1e-6),
        "depth_ratio_median": float(np.median(np.asarray(R["depth"]) / np.asarray(R["det_depth"]))),
        "n_fwhm": int(np.isfinite(R["fwhm"]).sum()), "n_recovery": int(np.isfinite(R["recovery"]).sum()),
        "fwhm_s_median": float(np.nanmedian(R["fwhm"])), "recovery_s_median": float(np.nanmedian(R["recovery"])),
    }


def main():
    events = S.load_events(SEED)
    snippets = S.load_snippets(SEED)
    out = {}
    auto = measure(events, snippets, True, polarity="auto")
    out["auto_polarity_called_spike"] = [r["event_id"] for r in auto if r["polarity"] == 1]
    print("auto polarity: spikes among the 410 seed drops =", len(out["auto_polarity_called_spike"]))
    for label, walk, anchored in (("own_anatomy_walk_onset_back_true", True, False),
                                  ("own_anatomy_seed_flags_walk_onset_back_false", False, False),
                                  ("detector_anchors", True, True)):
        rows = measure(events, snippets, walk, anchored)
        out[label] = {"summary": summarise(rows),
                      "largest_depth_disagreements": sorted(rows, key=lambda r: -abs(r["depth"] - r["det_depth"]))[:8],
                      "rows": rows}
        print(label, json.dumps(out[label]["summary"], indent=1))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
