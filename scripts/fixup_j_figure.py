"""
fixup_j_figure.py
=================
The before/after evidence for fixup-J, against events whose number is KNOWN.

1. `known-events-synthetic.png` — a 12,000 s synthetic recording with 20
   injected events (`fixup_j_synthetic.py`): the detector as it was, and the
   port of the authors' code, each with its scalogram, Ω, funnel and spans,
   and the count of events found.
2. `known-events-real.png` — a stretch of M2_aug CH0 where a human labelled
   consecutive 10-minute windows `interesting` / `not_interesting`, same two
   columns.
3. `known-events.json` — the tallies, including every human-labelled window
   on the channel.

Read-only and in memory: the channel is opened with `mmap_mode="r"`, the
database with `mode=ro`; nothing is run through the bridge, the executor or
the step cache, and nothing is written outside `--out`.

    python scripts/fixup_j_figure.py --out webui/screenshots/fixup/J
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Working.Detection.analysis import dehshibi_authors as A                      # noqa: E402
from Working.Detection.analysis import dehshibi_detection_analysis as OLD         # noqa: E402
from scripts.fixup_j_synthetic import synthetic_recording                         # noqa: E402

WINDOW = 3000
CHANNEL = "DATA/derived/channels/M2_aug_concat_fs1/CH0.npy"
DB = "DATA/db/annotations.sqlite"


# ── the two detectors, each returning what the figure draws ─────────────────

def run_old(x):
    """The detector as it stood before fixup-J, called as the template called
    it: histogram slicing on the span, then per chunk."""
    spikes, pseudo, info = OLD.detect_spikes(x, fs=1.0)
    g = np.full((64, len(x)), np.nan)
    om = np.full(len(x), np.nan)
    for c0, c1 in info["chunks"]:
        if c1 - c0 + 1 < 120:
            continue
        phi, _ = OLD.compute_morse_wavelet_transform(x[c0:c1 + 1])
        gg, s = OLD.normalise_wavelet_coefficients(phi)
        g[:, c0:c1 + 1] = gg[::-1]
        om[c0:c1 + 1] = s
    R = [(int(min(a, b)), int(max(a, b))) for r in info["R"] for a, b, _ in r]
    return {"image": g, "omega": om, "B": info["B"], "C": info["C"], "D": info["D"], "R": R,
            "spikes": spikes, "analysed": float(np.isfinite(om).mean())}


def run_new(x):
    spikes, pseudo, info = A.detect_spikes(x, fs=1.0, window_s=float(WINDOW))
    img, _, _ = A.transform(x, fs=1.0, window_s=float(WINDOW))
    return {"image": img, "omega": info["omega"], "B": info["B"], "C": info["C"], "D": info["D"],
            "R": info["R_kept"], "spikes": spikes, "analysed": float(np.isfinite(info["omega"]).mean())}


# ── scoring against known events ────────────────────────────────────────────

def score(spans, events):
    """An event is FOUND when one span covers at least half of it and is no
    longer than three times the event (a span that swallows the whole window
    finds nothing). A span that covers no event at all is a false span."""
    found = []
    for a, b in events:
        ok = False
        for s, e in spans:
            s, e = min(s, e), max(s, e)
            cover = max(0, min(b, e + 1) - max(a, s))
            if cover >= 0.5 * (b - a) and (e + 1 - s) <= 3 * (b - a):
                ok = True
                break
        found.append(ok)
    false = [sp for sp in spans if not any(min(sp) < b and max(sp) + 1 > a for a, b in events)]
    return found, false


# ── drawing ─────────────────────────────────────────────────────────────────

def bands(ax, regions, y0, y1, color, alpha=0.55):
    for a, b in regions:
        a, b = min(a, b), max(a, b)
        ax.axvspan(a, b + 1, ymin=y0, ymax=y1, color=color, alpha=alpha, lw=0)


def column(axes, x, r, title, events=None, labelled=None):
    n = len(x)
    a_img, a_om, a_fun, a_sig = axes
    a_img.imshow(np.ma.masked_invalid(r["image"]), aspect="auto", origin="lower", extent=[0, n, 0, r["image"].shape[0]],
                 cmap="viridis", interpolation="nearest")
    a_img.set_facecolor("#bbbbbb")
    a_img.set_ylabel("frequency row\n(low → high)")
    a_img.set_title(title, fontsize=9.5, loc="left")
    a_om.plot(np.arange(n), r["omega"], color="k", lw=0.7)
    a_om.set_ylabel("Ω(τ)")
    for k in range(WINDOW, n, WINDOW):
        for ax in (a_om, a_sig):
            ax.axvline(k, color="0.6", lw=0.6, ls=":")
    rows = [("candidates B", r["B"], "#7b6fd0"), ("spike cand. C", r["C"], "#2f9e44"),
            ("pseudo D", r["D"], "#868e96"), ("envelope R", r["R"], "#f08c00"), ("SPIKES", r["spikes"], "#e03131")]
    for i, (name, regs, col) in enumerate(rows):
        y1 = 1.0 - i / len(rows)
        bands(a_fun, regs, y1 - 0.9 / len(rows), y1, col, alpha=0.8)
        a_fun.text(-0.005, y1 - 0.5 / len(rows), f"{name}  {len(regs)}", transform=a_fun.transAxes,
                   ha="right", va="center", fontsize=8, color=col)
    a_fun.set_yticks([]); a_fun.set_xlim(0, n)
    a_sig.plot(np.arange(n), x * 1e3, color="k", lw=0.7)
    a_sig.set_ylabel("mV")
    a_sig.set_xlabel("seconds from the start of the span")
    bands(a_sig, r["spikes"], 0.0, 0.12, "#e03131", alpha=0.9)
    if events is not None:
        found, _ = score(r["spikes"], events)
        for (a, b), ok in zip(events, found):
            a_sig.axvspan(a, b, ymin=0.88, ymax=1.0, color="#2f9e44" if ok else "#e03131", alpha=0.85, lw=0)
            a_sig.axvspan(a, b, ymin=0.12, ymax=0.88, color="#2f9e44" if ok else "#e03131", alpha=0.08, lw=0)
    if labelled is not None:
        for a, b, verdict in labelled:
            a_sig.axvspan(a, b, ymin=0.88, ymax=1.0, lw=0, alpha=0.85,
                          color={"interesting": "#1c7ed6", "not_interesting": "#ced4da"}.get(verdict, "#f08c00"))
    for ax in axes:
        ax.set_xlim(0, n)


def figure(path, x, events, labelled, suptitle, captions):
    old, new = run_old(x), run_new(x)
    fig, axes = plt.subplots(4, 2, figsize=(19, 11), sharex=True,
                             gridspec_kw={"height_ratios": [1.3, 1.0, 0.9, 1.6]})
    column(axes[:, 0], x, old, captions[0](old), events, labelled)
    column(axes[:, 1], x, new, captions[1](new), events, labelled)
    fig.suptitle(suptitle, fontsize=12, x=0.01, ha="left")
    fig.tight_layout(rect=[0.03, 0, 1, 0.96])
    fig.savefig(path, dpi=75)
    plt.close(fig)
    return old, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("webui", "screenshots", "fixup", "J"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tally = {}

    # 1 ── synthetic, 20 known events ───────────────────────────────────────
    x, ev = synthetic_recording(n=12000, n_events=20, seed=11)
    events = [(e["start"], e["end"]) for e in ev]

    def cap(name):
        def f(r):
            found, false = score(r["spikes"], events)
            return (f"{name}\n{sum(found)} of {len(events)} known events found · {len(r['spikes'])} spans, "
                    f"{len(false)} on no event · {100 * r['analysed']:.0f}% of the span analysed")
        return f
    old, new = figure(os.path.join(a.out, "known-events-synthetic.png"), x, events, None,
                      "Synthetic recording, 12,000 s at 1 Hz, 20 injected events (0.6–5 mV, 150–420 s; top strip: green = found, red = missed). "
                      "Bottom strip: the detector's spans.",
                      (cap("BEFORE (repo at the grilling round)"), cap("AFTER (port of the authors' code, 3000 s windows)")))
    for name, r in (("before", old), ("after", new)):
        found, false = score(r["spikes"], events)
        tally[f"synthetic_{name}"] = {"events": len(events), "found": int(sum(found)), "spans": len(r["spikes"]),
                                      "spans_on_no_event": len(false), "fraction_analysed": r["analysed"],
                                      "missed_amp_mv": [ev[i]["amp_mv"] for i, ok in enumerate(found) if not ok]}

    # the three reference recordings too: these are the ones MATLAB was run on
    for seed_kw in (dict(n=3000, n_events=6, seed=0), dict(n=3000, n_events=4, seed=7), dict(n=4200, n_events=8, seed=3)):
        xs, es = synthetic_recording(**seed_kw)
        evs = [(e["start"], e["end"]) for e in es]
        sp, _, _ = A.detect_spikes(xs, fs=1.0, window_s=float(len(xs)))
        f, fl = score(sp, evs)
        tally.setdefault("reference_cases_after", []).append({"n": seed_kw["n"], "events": len(evs), "found": int(sum(f)), "spans": len(sp)})

    # 2 ── real, human-labelled 10-minute windows ───────────────────────────
    if os.path.exists(CHANNEL) and os.path.exists(DB):
        ch = np.load(CHANNEL, mmap_mode="r")
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        lab = conn.execute("SELECT start_idx, end_idx, verdict FROM annotations WHERE recording_id = 1 AND deleted_at IS NULL "
                           "AND source = 'imported_10min' ORDER BY start_idx").fetchall()
        conn.close()
        # the 4-window stretch holding the most labelled windows with both verdicts present
        best, best_k = None, -1
        for k in range(0, len(ch) // WINDOW - 4):
            s0, s1 = k * WINDOW, (k + 4) * WINDOW
            inside = [l for l in lab if l[0] >= s0 and l[1] <= s1]
            ni = sum(1 for l in inside if l[2] == "interesting")
            if ni >= 4 and len(inside) - ni >= 4 and len(inside) > best_k:
                best, best_k = k, len(inside)
        if best is not None:
            s0 = best * WINDOW
            xr = np.asarray(ch[s0:s0 + 4 * WINDOW], dtype=float)
            labelled = [(l[0] - s0, l[1] - s0, l[2]) for l in lab if l[0] >= s0 and l[1] <= s0 + 4 * WINDOW]

            def cap_r(name):
                def f(r):
                    hit = lambda v: sum(1 for a_, b_, vv in labelled if vv == v and any(min(sp) < b_ and max(sp) + 1 > a_ for sp in r["spikes"]))
                    tot = lambda v: sum(1 for _, _, vv in labelled if vv == v)
                    return (f"{name}\na span in {hit('interesting')} of {tot('interesting')} 'interesting' windows and "
                            f"{hit('not_interesting')} of {tot('not_interesting')} 'not interesting' · {len(r['spikes'])} spans · "
                            f"{100 * r['analysed']:.0f}% analysed")
                return f
            figure(os.path.join(a.out, "known-events-real.png"), xr, None, labelled,
                   f"M2_aug_concat_fs1 CH0, {s0 / 3600:.1f}–{(s0 + 4 * WINDOW) / 3600:.1f} h. Top strip: the researcher's 10-minute labels "
                   "(blue = interesting, grey = not interesting). Bottom strip: the detector's spans.",
                   (cap_r("BEFORE (repo at the grilling round)"), cap_r("AFTER (port of the authors' code, 3000 s windows)")))
            tally["real_span"] = {"start_h": s0 / 3600, "hours": 4 * WINDOW / 3600, "labelled_windows": len(labelled)}

        # every labelled window on the channel, each run in the 3000 s grid window(s) it falls in
        grid = sorted({l[0] // WINDOW for l in lab} | {(l[1] - 1) // WINDOW for l in lab})
        spans_new, spans_old = {}, {}
        for k in grid:
            seg = np.asarray(ch[k * WINDOW:(k + 1) * WINDOW], dtype=float)
            if len(seg) < WINDOW:
                continue
            sp, _, _ = A.detect_spikes(seg, fs=1.0, window_s=float(WINDOW))
            spans_new[k] = [(s + k * WINDOW, e + k * WINDOW) for s, e in sp]
            so, _, _ = OLD.detect_spikes(seg, fs=1.0)
            spans_old[k] = [(min(s, e) + k * WINDOW, max(s, e) + k * WINDOW) for s, e in so]
        for name, spans in (("after", spans_new), ("before", spans_old)):
            allsp = [sp for k in spans for sp in spans[k]]
            starts = np.array(sorted(s for s, _ in allsp)) if allsp else np.array([])
            out = {}
            for verdict in ("interesting", "not_interesting", "artifact"):
                wins = [l for l in lab if l[2] == verdict]
                hit = sum(1 for a_, b_, _ in wins if any(s < b_ and e + 1 > a_ for s, e in allsp
                                                         if s < b_ + 1 and e + 1 > a_ - 1))
                out[verdict] = {"windows": len(wins), "with_a_span": hit}
            out["spans"] = len(allsp)
            out["fraction_of_time_inside_a_span"] = (sum(e + 1 - s for s, e in allsp) / float(len(spans) * WINDOW)) if spans else 0.0
            out["grid_windows_run"] = len(spans)
            tally[f"real_labelled_{name}"] = out

    with open(os.path.join(a.out, "known-events.json"), "w", encoding="utf-8") as f:
        json.dump(tally, f, indent=1)
    print(json.dumps(tally, indent=1))


if __name__ == "__main__":
    main()
