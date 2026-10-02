"""Does a sharkfin recover if you look past the stored snippet?

The researcher's hypothesis (2026-10-02): a "sharkfin" is not rise-then-fall. It is a TROUGH whose
slow rise back up is its RECOVERY, and the detector has attributed that rise to the NEXT fall as its
precursor (`up_region_start_idx`).

`scripts/q26_recovery_probe.py` measured recovery inside the STORED SNIPPET and found a median 0.7 %
of depth. But the stored post-context is a median 118 s while the rise does not begin until a median
149 s after the trough (`scripts/q26_rise_provenance.py`) -- so that probe's window ENDS BEFORE the
rise starts and cannot see it. This one measures on the real channel, from the trough forward to the
next event's onset, which is the whole inter-event interval.

Reported per event: the recovered fraction of depth at quarter / half / three-quarters of the way to
the next onset, where it first reaches 50 %, and whether the climb is monotone or flat-then-rise.
Measured on the RAW channel in mV (fixup-b: `recordings.units`), because detrending with a window
shorter than the rise would subtract the very thing being looked for -- `detrend_window_s` is
reported beside it.

READ-ONLY. Opens the database `mode=ro` and the channel arrays `mmap_mode='r'`. Writes only to
`webui/screenshots/fixup/Q26/`.
"""
import json
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.Detection.drop_motifs import store as S  # noqa: E402

SEED = os.path.join(ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "webui", "screenshots", "fixup", "Q26")
UNIT_FACTOR = {"V": 1000.0, "mV": 1.0}


def load_channels(recording_ids):
    con = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = {}
    for rid in sorted(recording_ids):
        r = con.execute("SELECT npy_path, units, fs FROM recordings WHERE id=?", (int(rid),)).fetchone()
        if r is None:
            continue
        path = os.path.join(ROOT, r["npy_path"].replace("/", os.sep))
        if not os.path.exists(path):
            continue
        out[int(rid)] = (np.load(path, mmap_mode="r"),
                         UNIT_FACTOR.get(r["units"], 1.0), float(r["fs"]))
    con.close()
    return out


def main():
    events = S.load_events(SEED)
    chans = load_channels({int(e["recording_id"]) for e in events})
    by_span = {}
    for e in events:
        by_span.setdefault(e["span_key"], []).append(e)

    rows = []
    for key, evs in sorted(by_span.items()):
        evs = sorted(evs, key=lambda e: float(e["onset_h"]))
        for i, e in enumerate(evs):
            rid = int(e["recording_id"])
            if rid not in chans:
                continue
            arr, factor, fs = chans[rid]
            on, tr = int(e["onset_idx"]), int(e["trough_idx"])
            # the search runs to the NEXT event's onset, or the next rise's start, or 20 falls
            nxt = int(evs[i + 1]["onset_idx"]) if i + 1 < len(evs) else len(arr)
            width = max(tr - on, 1)
            end = int(min(nxt, tr + 20 * width + 1, len(arr)))
            if end - tr < 3:
                continue
            v_on = float(arr[on]) * factor
            v_tr = float(arr[tr]) * factor
            depth = v_on - v_tr
            if depth <= 0:
                continue
            tail = np.asarray(arr[tr:end], dtype=float) * factor
            frac = (tail - v_tr) / depth                       # 0 at the trough, 1 at the onset level
            n = len(frac)
            at = lambda f: float(frac[min(n - 1, int(f * (n - 1)))])      # noqa: E731
            reach = np.flatnonzero(frac >= 0.5)
            half_at = None if reach.size == 0 else float(reach[0]) / fs
            # flat-then-rise vs steady climb: how much of the climb happens in the last third
            thirds = [float(np.max(frac[a:b])) for a, b in
                      ((0, max(1, n // 3)), (max(1, n // 3), max(2, 2 * n // 3)), (max(2, 2 * n // 3), n))]
            rows.append({
                "span": key, "event_id": e["event_id"], "morphology": e.get("morphology"),
                "fall_s": round(width / fs, 1), "depth_mv": round(depth, 3),
                "detrend_window_s": e.get("detrend_window_s"),
                "stored_post_context_s": e.get("post_context_s"),
                "searched_s": round((end - tr) / fs, 1),
                "bound": ("next_onset" if end == nxt else
                          "twenty_widths" if end == tr + 20 * width + 1 else "recording_end"),
                "frac_at_25pct": round(at(0.25), 3),
                "frac_at_50pct": round(at(0.50), 3),
                "frac_at_75pct": round(at(0.75), 3),
                "frac_max": round(float(np.max(frac)), 3),
                "half_recovery_s": None if half_at is None else round(half_at, 1),
                "half_recovery_over_fall": None if half_at is None else round(half_at / (width / fs), 2),
                "max_by_third": [round(t, 3) for t in thirds],
            })

    def stats(xs):
        xs = [x for x in xs if x is not None]
        if not xs:
            return None
        a = np.array(xs, dtype=float)
        return {"n": len(a), "median": round(float(np.median(a)), 3),
                "p10": round(float(np.percentile(a, 10)), 3),
                "p90": round(float(np.percentile(a, 90)), 3)}

    summary = {}
    for morph in ("sharkfin", "trough"):
        sub = [r for r in rows if r["morphology"] == morph]
        summary[morph] = {
            "n": len(sub),
            "reaches_half_recovery": sum(1 for r in sub if r["half_recovery_s"] is not None),
            "frac_max": stats([r["frac_max"] for r in sub]),
            "frac_at_25pct": stats([r["frac_at_25pct"] for r in sub]),
            "frac_at_50pct": stats([r["frac_at_50pct"] for r in sub]),
            "frac_at_75pct": stats([r["frac_at_75pct"] for r in sub]),
            "half_recovery_s": stats([r["half_recovery_s"] for r in sub]),
            "half_recovery_over_fall": stats([r["half_recovery_over_fall"] for r in sub]),
            "searched_s": stats([r["searched_s"] for r in sub]),
            "stored_post_context_s": stats([float(r["stored_post_context_s"] or 0) for r in sub]),
            "detrend_window_s": sorted({r["detrend_window_s"] for r in sub}),
            "bounds": {b: sum(1 for r in sub if r["bound"] == b) for b in sorted({r["bound"] for r in sub})},
            "reaches_frac": {str(f): sum(1 for r in sub if r["frac_max"] >= f)
                             for f in (0.25, 0.5, 0.75, 0.9)},
        }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "sharkfin-recovery-on-channel.json"), "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
