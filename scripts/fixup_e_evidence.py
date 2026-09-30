"""
fixup_e_evidence.py
====================
What the Interrogation Aggregate page used to INVENT against what the core MEASURES, for the same
events (fixup-e, `docs/prompts/fixup/E-aggregate-stops-fabricating.md`, "Evidence").

Before fixup-e, `AggregatePage.tsx::featureOf` returned, for the live spike-shape upstream,

    half_width_s = fall_duration_s x 0.84
    rise_s       = fall_duration_s x 0.31
    isi_s        = fall_duration_s x 4.2

and `api/interrogation.ts::memberFrom` computed recovery in the browser: from the trough, on the
400-point DECIMATED snippet, the first sample back within 10 % of the drop depth of the onset level,
reporting an event that never got there as 0 s.

This script reproduces each of those four numbers for every event of the seed store and puts the
core's measurement beside it: `interrogation.event_shape` on the store's own full-resolution snippet
from the detector's anchors (`Working.library.features.measure_snippet`, fixup-d) — FWHM, rise time
(null for a drop), recovery (half the amplitude, bounded; null when not reached) — and the real
onset-to-onset interval within the span.

Writes `webui/screenshots/fixup/E/fabricated-vs-measured.json` and `.md`. Read-only.

    python scripts/fixup_e_evidence.py
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
OUT = os.path.join(ROOT, "webui", "screenshots", "fixup", "E")
SNIPPET_POINTS = 400        # interrogation_routes._decimate


def browser_recovery(e, snip):
    """The page's old recovery, exactly as `memberFrom` computed it on the decimated snippet."""
    t = np.asarray(snip["t_s"], dtype=float)
    v = np.asarray(snip["detrended_mv"], dtype=float)
    if len(t) > SNIPPET_POINTS:
        idx = np.linspace(0, len(t) - 1, SNIPPET_POINTS).round().astype(int)
        t, v = t[idx], v[idx]
    n = len(t)
    sn = int(e["snippet_end_idx"]) - int(e["snippet_start_idx"])
    k = lambda i: min(n - 1, int(round((i / max(1, sn)) * (n - 1))))          # noqa: E731
    ko, kt = k(int(e["onset_idx"]) - int(e["snippet_start_idx"])), k(int(e["trough_idx"]) - int(e["snippet_start_idx"]))
    level = v[ko] - 0.1 * float(e["drop_depth_mv"])
    kr = kt
    while kr < n and v[kr] < level:
        kr += 1
    return float(t[kr] - t[kt]) if kr < n else 0.0


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
            values = np.asarray(snip["detrended_mv"], dtype=float)
            m = F.measure_snippet(values, float(e["fs"]), F.detector_anchor(e))
            dur = float(e["fall_duration_s"])
            rows.append({
                "span": key, "event_id": e["event_id"], "fall_duration_s": dur,
                "fabricated": {"half_width_s": round(dur * 0.84, 2), "rise_s": round(dur * 0.31, 2), "isi_s": round(dur * 4.2, 2),
                               "recovery_s_browser": round(browser_recovery(e, snip), 2)},
                "measured": {"fwhm_s": m["fwhm_s"], "rise_time_s": m["rise_time_s"],
                             "interval_before_s": None if i == 0 else float(onsets[i] - onsets[i - 1]),
                             "recovery_time_s": m["recovery_time_s"]},
            })

    def err(fab, meas):
        if meas is None:
            return None
        return fab - meas

    summary = {"n_events": len(rows)}
    for fab_key, meas_key in (("half_width_s", "fwhm_s"), ("rise_s", "rise_time_s"), ("isi_s", "interval_before_s"), ("recovery_s_browser", "recovery_time_s")):
        pairs = [(r["fabricated"][fab_key], r["measured"][meas_key]) for r in rows]
        measured = [(f, m) for f, m in pairs if m is not None]
        unmeasured = len(pairs) - len(measured)
        d = np.array([f - m for f, m in measured]) if measured else np.array([])
        ratio = np.array([f / m for f, m in measured if m > 0]) if measured else np.array([])
        fab_when_unmeasured = [f for f, m in pairs if m is None]
        summary[fab_key] = {
            "against": meas_key, "n_measured": len(measured), "n_not_measured": unmeasured,
            "fabricated_value_when_not_measured": {"median": float(np.median(fab_when_unmeasured)) if fab_when_unmeasured else None,
                                                   "min": float(np.min(fab_when_unmeasured)) if fab_when_unmeasured else None,
                                                   "max": float(np.max(fab_when_unmeasured)) if fab_when_unmeasured else None},
            "error_s": None if not measured else {"median": float(np.median(d)), "median_abs": float(np.median(np.abs(d))),
                                                  "p90_abs": float(np.percentile(np.abs(d), 90)), "max_abs": float(np.max(np.abs(d)))},
            "ratio_fabricated_over_measured": None if ratio.size == 0 else {"median": float(np.median(ratio)), "p10": float(np.percentile(ratio, 10)), "p90": float(np.percentile(ratio, 90))},
        }
    # the browser recovery's special defect: 0 s where the core says "not recovered", and where it is a number, how wrong
    br = [(r["fabricated"]["recovery_s_browser"], r["measured"]["recovery_time_s"]) for r in rows]
    summary["recovery_s_browser"]["zero_where_core_says_not_recovered"] = sum(1 for f, m in br if m is None and f == 0.0)
    summary["recovery_s_browser"]["nonzero_where_core_says_not_recovered"] = sum(1 for f, m in br if m is None and f != 0.0)
    summary["recovery_s_browser"]["zero_where_core_measured_a_recovery"] = sum(1 for f, m in br if m is not None and f == 0.0)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "fabricated-vs-measured.json"), "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "rows": rows}, fh, indent=1)

    # the markdown table: id001 (the default family) event by event, then the 410-event summary
    lines = ["| event | fall s | half_width = 0.84×fall | FWHM (core) | rise = 0.31×fall | rise (core) | isi = 4.2×fall | interval before (core) | recovery (browser, 90 %) | recovery (core, 50 %) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda v: "**not measured**" if v is None else f"{v:.1f}"          # noqa: E731
    for r in [x for x in rows if x["span"] == "id001"]:
        f, m = r["fabricated"], r["measured"]
        lines.append(f"| {r['event_id']} | {r['fall_duration_s']:.0f} | {f['half_width_s']:.1f} | {fmt(m['fwhm_s'])} | {f['rise_s']:.1f} | {fmt(m['rise_time_s'])} | "
                     f"{f['isi_s']:.0f} | {fmt(m['interval_before_s'])} | {f['recovery_s_browser']:.1f} | {fmt(m['recovery_time_s'])} |")
    lines += ["", "Summary over all 410 seed events:", "",
              "| page used to draw | against the core's | measured on | not measured (the page drew a number anyway) | median error, s | p90 abs error, s | fabricated / measured, median [p10–p90] |",
              "|---|---|---|---|---|---|---|"]
    for k in ("half_width_s", "rise_s", "isi_s", "recovery_s_browser"):
        sm = summary[k]
        e_ = sm["error_s"]; rt = sm["ratio_fabricated_over_measured"]
        lines.append(f"| `{k}` | `{sm['against']}` | {sm['n_measured']} | {sm['n_not_measured']} | "
                     f"{'—' if not e_ else f'{e_['median']:+.1f}'} | {'—' if not e_ else f'{e_['p90_abs']:.1f}'} | "
                     f"{'—' if not rt else f'{rt['median']:.2f} [{rt['p10']:.2f}–{rt['p90']:.2f}]'} |")
    rb = summary["recovery_s_browser"]
    lines += ["", f"Browser recovery: {rb['zero_where_core_says_not_recovered']} events read **0 s** where the core says *not recovered*; "
                  f"{rb['nonzero_where_core_says_not_recovered']} read a positive number where the core says not recovered (the 90 % level was re-crossed by noise or the next event inside the decimated snippet, past the core's bound); "
                  f"{rb['zero_where_core_measured_a_recovery']} read 0 s where the core measured a recovery."]
    with open(os.path.join(OUT, "fabricated-vs-measured.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
