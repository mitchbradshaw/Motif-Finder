"""Does a sharkfin's RISE begin at the previous event's TROUGH?

The researcher's hypothesis: a "sharkfin" is not rise-then-fall. It is a trough whose slow rise back
up is its RECOVERY, and the detector has attributed that rise to the NEXT fall as its precursor.

The detector records the rise it triggered on: `up_region_start_idx` / `up_region_end_idx`
(detect5.py:827, the rise segment the rise trigger fired from). So the hypothesis is directly
testable on the event store: per span, in time order, how far is each event's up-region start from
the PREVIOUS event's trough?

  gap ~ 0            -> the rise starts at the previous trough: it IS that trough's recovery
  gap >> 0           -> the trace sits on the floor first; the rise is a separate phase

Read-only: the tracked seed store only.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.Detection.drop_motifs import store as S  # noqa: E402

SEED = os.path.join(ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")


def main():
    events = S.load_events(SEED)
    by_span = {}
    for e in events:
        by_span.setdefault(e["span_key"], []).append(e)

    rows = []
    for key, evs in sorted(by_span.items()):
        evs = sorted(evs, key=lambda e: float(e["onset_h"]))
        for i, e in enumerate(evs):
            fs = float(e["fs"])
            try:
                up0 = int(e["up_region_start_idx"])
                up1 = int(e["up_region_end_idx"])
            except (KeyError, TypeError, ValueError):
                up0 = up1 = -1
            row = {
                "span": key, "event_id": e["event_id"], "morphology": e.get("morphology"),
                "trigger": e.get("trigger"), "fs": fs,
                "fall_s": round(float(e["fall_duration_s"]), 1),
                "depth_mv": round(float(e["drop_depth_mv"]), 2),
                "onset_idx": int(e["onset_idx"]), "trough_idx": int(e["trough_idx"]),
                "up_start_idx": up0, "up_end_idx": up1,
                "has_up": up0 >= 0,
                "rise_s": None if up0 < 0 else round((up1 - up0) / fs, 1),
            }
            if i > 0:
                p = evs[i - 1]
                prev_trough = int(p["trough_idx"])
                row["prev_event"] = p["event_id"]
                row["prev_fall_s"] = round(float(p["fall_duration_s"]), 1)
                row["prev_trough_to_onset_s"] = round((int(e["onset_idx"]) - prev_trough) / fs, 1)
                if up0 >= 0:
                    row["prev_trough_to_rise_start_s"] = round((up0 - prev_trough) / fs, 1)
                    gap = (up0 - prev_trough) / fs
                    span_s = (int(e["onset_idx"]) - prev_trough) / fs
                    row["gap_over_interval"] = None if span_s <= 0 else round(gap / span_s, 3)
                    row["gap_over_prev_fall"] = round(gap / max(float(p["fall_duration_s"]), 1e-9), 2)
            rows.append(row)

    def stats(xs):
        xs = [x for x in xs if x is not None]
        if not xs:
            return None
        a = np.array(xs, dtype=float)
        return {"n": len(a), "median": round(float(np.median(a)), 3),
                "p10": round(float(np.percentile(a, 10)), 3),
                "p90": round(float(np.percentile(a, 90)), 3),
                "min": round(float(a.min()), 3), "max": round(float(a.max()), 3)}

    out = {}
    for morph in ("sharkfin", "trough"):
        sub = [r for r in rows if r["morphology"] == morph]
        withprev = [r for r in sub if "prev_event" in r and r.get("has_up")]
        out[morph] = {
            "n": len(sub),
            "n_with_up_region": sum(1 for r in sub if r["has_up"]),
            "triggers": {t: sum(1 for r in sub if r["trigger"] == t) for t in sorted({r["trigger"] for r in sub})},
            "rise_s": stats([r["rise_s"] for r in sub]),
            "fall_s": stats([r["fall_s"] for r in sub]),
            "n_with_prev_and_up": len(withprev),
            "prev_trough_to_rise_start_s": stats([r.get("prev_trough_to_rise_start_s") for r in withprev]),
            "gap_over_interval": stats([r.get("gap_over_interval") for r in withprev]),
            "gap_over_prev_fall": stats([r.get("gap_over_prev_fall") for r in withprev]),
            "rise_starts_within_1pct_of_prev_trough": sum(
                1 for r in withprev if r.get("gap_over_interval") is not None and r["gap_over_interval"] <= 0.01),
            "rise_starts_within_10pct_of_prev_trough": sum(
                1 for r in withprev if r.get("gap_over_interval") is not None and r["gap_over_interval"] <= 0.10),
            "rise_starts_at_or_before_prev_trough": sum(
                1 for r in withprev if (r.get("prev_trough_to_rise_start_s") or 1) <= 0),
            "rise_covers_whole_interval_frac": stats([
                None if not r.get("prev_trough_to_onset_s") or r["prev_trough_to_onset_s"] <= 0
                else round((r["up_end_idx"] - r["up_start_idx"]) / r["fs"] / r["prev_trough_to_onset_s"], 3)
                for r in withprev]),
        }
    dest = os.path.join(ROOT, "webui", "screenshots", "fixup", "Q26", "rise-vs-prev-trough.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump({"summary": out, "rows": rows}, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
