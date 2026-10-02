"""Q26 probe: WHY the 170 non-recovering seed events do not recover.

For every seed event: does it recover (50 % of depth, within 10 event widths, inside the stored
snippet)? For the ones that do not -- which bound stopped the search (the snippet's end, or the
10-width cap), how far back up did the trace actually climb before that bound, and how long until
the next event's onset?

Read-only. Reads DATA/library_seed/drop_motifs5 only.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.Detection.drop_motifs import store as S  # noqa: E402
from Working.library import features as F  # noqa: E402

SEED = os.path.join(ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
RECOVERY_FRAC = 0.5
RECOVERY_MAX_MULT = 10.0


def main():
    events = S.load_events(SEED)
    snips = S.load_snippets(SEED)
    by_span = {}
    for e in events:
        by_span.setdefault(e["span_key"], []).append(e)

    rows = []
    for key, evs in sorted(by_span.items()):
        evs = sorted(evs, key=lambda e: float(e["onset_h"]))
        onsets = np.array([float(e["onset_h"]) for e in evs]) * 3600.0
        for i, e in enumerate(evs):
            snip = snips[e["event_id"]]
            v = np.asarray(snip["detrended_mv"], dtype=float).ravel()
            fs = float(e["fs"])
            m = F.measure_snippet(v, fs, F.detector_anchor(e))
            on = m.get("onset_idx")
            ex = m.get("extremum_idx")
            rec = m.get("recovery_time_s")
            if on is None or ex is None:
                continue
            on, ex = int(on), int(ex)
            width = max(ex - on, 1)
            depth = float(v[on] - v[ex])
            if depth <= 0:
                continue
            cap = ex + RECOVERY_MAX_MULT * width + 1
            end = len(v)
            limit = int(min(cap, end))
            tail = v[ex:limit]
            # how far back up, as a fraction of depth, before the bound
            best = float(np.max(tail) - v[ex]) / depth if len(tail) else 0.0
            # and how far up if the search could run to the end of the stored snippet
            tail_all = v[ex:]
            best_all = float(np.max(tail_all) - v[ex]) / depth if len(tail_all) else 0.0
            rows.append({
                "span": key, "event_id": e["event_id"],
                "recovered": rec is not None,
                "fall_s": round(width / fs, 2),
                "post_context_s": round((end - ex) / fs, 1),
                "post_context_widths": round((end - ex) / width, 2),
                "bound": "snippet_end" if end <= cap else "ten_widths",
                "best_frac": round(best, 3),
                "best_frac_whole_snippet": round(best_all, 3),
                "interval_after_s": None if i == len(evs) - 1 else round(float(onsets[i + 1] - onsets[i]), 1),
            })

    nr = [r for r in rows if not r["recovered"]]
    rc = [r for r in rows if r["recovered"]]
    q = lambda xs, p: None if not xs else round(float(np.percentile(xs, p)), 3)  # noqa: E731

    by_fam = {}
    for r in rows:
        f = by_fam.setdefault(r["span"], {"n": 0, "not_recovered": 0, "bound_snippet": 0, "best": []})
        f["n"] += 1
        if not r["recovered"]:
            f["not_recovered"] += 1
            f["best"].append(r["best_frac"])
            if r["bound"] == "snippet_end":
                f["bound_snippet"] += 1
    for f in by_fam.values():
        f["best_frac_median"] = None if not f["best"] else round(float(np.median(f["best"])), 3)
        del f["best"]

    summary = {
        "n_events": len(rows),
        "n_recovered": len(rc),
        "n_not_recovered": len(nr),
        "not_recovered": {
            "bound_was_snippet_end": sum(1 for r in nr if r["bound"] == "snippet_end"),
            "bound_was_ten_widths": sum(1 for r in nr if r["bound"] == "ten_widths"),
            "post_context_widths": {
                "median": q([r["post_context_widths"] for r in nr], 50),
                "p10": q([r["post_context_widths"] for r in nr], 10),
                "p90": q([r["post_context_widths"] for r in nr], 90),
            },
            "best_frac_within_bound": {
                "median": q([r["best_frac"] for r in nr], 50),
                "p10": q([r["best_frac"] for r in nr], 10),
                "p90": q([r["best_frac"] for r in nr], 90),
                "max": q([r["best_frac"] for r in nr], 100),
            },
            "best_frac_whole_snippet": {
                "median": q([r["best_frac_whole_snippet"] for r in nr], 50),
                "p90": q([r["best_frac_whole_snippet"] for r in nr], 90),
                "max": q([r["best_frac_whole_snippet"] for r in nr], 100),
            },
            "would_recover_at_frac": {
                str(f): sum(1 for r in nr if r["best_frac"] >= f)
                for f in (0.1, 0.2, 0.25, 0.3, 0.4)
            },
            "would_recover_at_frac_if_snippet_ran_on": {
                str(f): sum(1 for r in nr if r["best_frac_whole_snippet"] >= f)
                for f in (0.1, 0.2, 0.25, 0.3, 0.5)
            },
            "has_interval_after": sum(1 for r in nr if r["interval_after_s"] is not None),
            "interval_after_s": {
                "median": q([r["interval_after_s"] for r in nr if r["interval_after_s"] is not None], 50),
                "p10": q([r["interval_after_s"] for r in nr if r["interval_after_s"] is not None], 10),
                "p90": q([r["interval_after_s"] for r in nr if r["interval_after_s"] is not None], 90),
            },
            "interval_over_fall": {
                "median": q([r["interval_after_s"] / r["fall_s"] for r in nr
                             if r["interval_after_s"] is not None and r["fall_s"] > 0], 50),
            },
        },
        "recovered": {
            "post_context_widths_median": q([r["post_context_widths"] for r in rc], 50),
        },
        "by_family": by_fam,
    }
    out = os.path.join(ROOT, "webui", "screenshots", "fixup", "Q26", "recovery-probe.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
