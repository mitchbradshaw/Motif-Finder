"""
make_viewer.py
==============
The interactive pages for the auto-detect prototype: one self-contained HTML viewer per reference (zoom, pan, scan
across, step through candidates, hover for how each confidence was built) and an index linking them.

Reads what `run_references.py` wrote under ``docs/autodetect/20261119/<reference>/`` plus the channel's samples
(memory-mapped, read-only), and writes ``<reference>/viewer.html`` and ``index.html`` beside them. The samples are
embedded as 16-bit integers (a quantum far below each channel's noise), so a page opens offline with nothing else.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/make_viewer.py
"""

from __future__ import annotations

import base64
import html
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as K  # noqa: E402

from Working.autodetect.sequences import find_sequences  # noqa: E402
from Working.units import read_as_mv  # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer_template.html")
KNOWN_NAMES = ["accepted", "rejected", "window_interesting", "window_not", "unjudged"]
SOURCES = ["drop_detection_v1", "drop_detection_v5", "wavelet_encoded", "BEADs_invert_detect_v1", "seed", "beads_sigma",
           "event_rule"]
LABEL = {"drop_detection_v1": "drop v1", "drop_detection_v5": "drop v5", "wavelet_encoded": "wavelet",
         "BEADs_invert_detect_v1": "BEADS", "seed": "seed", "r4_scan": "R4 scan", "beads_sigma": "BEADS σ",
         "event_rule": "event rule"}


def _f(v, nd=4):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def quantise(x_mv):
    finite = np.isfinite(x_mv)
    lo, hi = (float(np.min(x_mv[finite])), float(np.max(x_mv[finite]))) if finite.any() else (0.0, 1.0)
    scale = max(hi - lo, 1e-9) / 65000.0
    offset = (hi + lo) / 2.0
    q = np.full(len(x_mv), -32768, dtype=np.int16)
    q[finite] = np.clip(np.round((x_mv[finite] - offset) / scale), -32500, 32500).astype(np.int16)
    return {"b64": base64.b64encode(q.tobytes()).decode("ascii"), "scale": scale, "offset": offset,
            "quantum_mv": scale}


def columnar_candidates(c):
    def fams(v):
        if not isinstance(v, str):
            return ""
        f = sorted({p.split("__", 1)[1] for p in v.split("|") if p.startswith("seed__")},
                   key=lambda s: int(s.split("-")[1]) if s.split("-")[-1].isdigit() else 0)
        return ", ".join(f[:6]) + (f" +{len(f) - 6}" if len(f) > 6 else "")

    def mask(v):
        m = 0
        for s in (v.split("|") if isinstance(v, str) and v else []):
            if s in SOURCES:
                m |= 1 << SOURCES.index(s)
        return m

    return {
        "id": c["candidate_id"].astype(int).tolist(),
        "s": c["start"].astype(int).tolist(), "e": c["end"].astype(int).tolist(),
        "c": [round(float(v), 4) for v in c["confidence"]],
        "p": [_f(v) for v in c["p_r4"]],
        "k": [1 if k == "r4_scan" else 0 for k in c["kind"]],
        "src": [mask(v) for v in c["sources"]],
        "seq": c["sequence_id"].astype(int).tolist(),
        "kn": [KNOWN_NAMES.index(k) if k in KNOWN_NAMES else 4 for k in c["known"]],
        "lifts": c["lifts"].astype(str).tolist(),
        "sp": [_f(v) for v in c["scan_p"]],
        "fam": [fams(v) for v in c["member_variants"]],
        "dep": [_f(v, 3) for v in c["depth_mv"]] if "depth_mv" in c else [None] * len(c),
        "pol": [1 if p == "spike" else 0 for p in c["polarity"]] if "polarity" in c else [0] * len(c),
        "rec": [bool(v) if v == v else False for v in c["recovered"]] if "recovered" in c else [False] * len(c),
        "unx": [_f(v, 3) for v in c["unexplained"]] if "unexplained" in c else [None] * len(c),
        "ex": [int(v) if v == v else None for v in c["extremum"]] if "extremum" in c else [None] * len(c),
        "inv": [1 if r == "inverted" else 0 for r in c["run"]] if "run" in c else [0] * len(c),
        "both": [1 if r == "both" else 0 for r in c["runs"]] if "runs" in c else [0] * len(c),
        "shp": [_f(v, 1) for v in c["sharpness"]] if "sharpness" in c else [None] * len(c),
        "os": c["orig_start"].astype(int).tolist() if "orig_start" in c else c["start"].astype(int).tolist(),
        "oe": c["orig_end"].astype(int).tolist() if "orig_end" in c else c["end"].astype(int).tolist(),
        "anchor": [LABEL.get(str(a).split("__")[0], str(a).split("__")[0]) + (f" ({str(a).split('__', 1)[1]})"
                                                                              if "__" in str(a) else "")
                   for a in c["anchor_variant"]],
    }


def seqs_payload(s):
    return {"s": s["start"].astype(int).tolist() if len(s) else [], "e": s["end"].astype(int).tolist() if len(s) else [],
            "id": s["sequence_id"].astype(int).tolist() if len(s) else [],
            "n": s["n_members"].astype(int).tolist() if len(s) else [],
            "mc": [round(float(v), 3) for v in s["mean_confidence"]] if len(s) else [],
            "gap": [_f(v, 1) for v in s["median_gap_s"]] if len(s) else [],
            "rule": s["rule"].astype(str).tolist() if len(s) else [],
            "pol": [1 if p == "spike" else 0 for p in s["polarity"]] if len(s) and "polarity" in s else [0] * len(s)}


def sequences_without_scan(c, fs):
    """The same sequence rule over the detector and seed candidates only, for the page's scan toggle (per polarity,
    as the run finds them)."""
    seq2 = np.full(len(c), -1, dtype=int)
    pols = ("drop", "spike") if "polarity" in c else (None,)
    parts, info, nxt = [], {"n_sequences": 0, "n_in": 0, "rule": []}, 0
    for pol in pols:
        prop = c[(c["kind"] != "r4_scan") & ((c["polarity"] == pol) if pol else True)]
        if not len(prop):
            continue
        lab, s2, si = find_sequences(prop.reset_index(drop=True), fs)
        seq2[prop.index.to_numpy()] = np.where(lab >= 0, lab + nxt, -1)
        if len(s2):
            s2 = s2.copy()
            s2["sequence_id"] = s2["sequence_id"] + nxt
            s2["polarity"] = pol or "drop"
            parts.append(s2)
            nxt = int(s2["sequence_id"].max()) + 1
        info["n_sequences"] += int(len(s2))
        info["n_in"] += int(si.get("n_in", 0))
        info["rule"].append(f"{'rises' if pol == 'spike' else 'drops'}: {si.get('rule')}")
        if si.get("cut_s"):
            info.setdefault("cuts", []).append(f"{'rises' if pol == 'spike' else 'drops'} {si['cut_s'] / 60:.1f} min")
    info["rule"] = " / ".join(info["rule"])
    s_all = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["sequence_id", "start", "end", "n_members", "mean_confidence", "median_gap_s", "rule", "polarity"])
    return seq2, s_all, info


def spans(df, extra=None):
    out = {"s": df["start"].astype(int).tolist() if len(df) else [], "e": df["end"].astype(int).tolist() if len(df) else []}
    if extra:
        out.update(extra)
    return out


def run_notes(meta, cands):
    info = meta["info"]
    si = info.get("sequence_info", {})
    s2 = info.get("sequence_info_without_scan", {})
    notes = [
        f"Recording {meta['recording']['id']} ({meta['recording']['source_file']}, channel index "
        f"{meta['recording']['channel']}), samples {meta['stretch']['start_idx']:,}–{meta['stretch']['end_idx']:,}.",
        f"Noise floor for seed matches: {meta['floor_mv']} mV ({meta['floor_source']}).",
        "Detector proposals: " + ", ".join(f"{LABEL.get(k, k)} {v}" for k, v in info.get("detector_counts", {}).items())
        + f"; seed matches {sum(r['kept'] for r in info.get('seed_report', []))} from "
          f"{sum(1 for r in info.get('seed_report', []) if r['kept'])} families.",
        f"R4 window scan: {meta['scan_windows']:,} windows; {info.get('scan_windows_above_min_p', 0):,} scored ≥ 0.5; "
        f"{info.get('counts', {}).get('r4_scan_only', 0)} became candidates of their own (the rest overlapped a "
        f"proposal or a better window). Median window score "
        f"{info.get('scan_p_quantiles', {}).get('0.5', float('nan')):.2f}.",
        f"Sequences (drops and rises found apart): {si.get('n_sequences', 0)} by {si.get('rule') or 'no rule'}"
        + "".join(f"; {'rises' if k == 'spike' else 'drops'} cut {v['cut_s'] / 60:.1f} min"
                  for k, v in (si.get("by_polarity") or {}).items() if v.get("cut_s"))
        + f"; {si.get('n_in', 0)} candidates ≥ 0.5 took part.",
        f"Without R4's scan (what the band shows when the scan is unticked): {s2.get('n_sequences', 0)} sequences by "
        f"{s2.get('rule') or 'no rule'}" + (f" ({', '.join(s2['cuts'])})" if s2.get("cuts") else "")
        + f"; {s2.get('n_in', 0)} candidates ≥ 0.5 took part.",
    ]
    cb = info.get("combined") or {}
    if cb:
        inv = info.get("inverted") or {}
        notes.append(f"Drops and rises: the run on the signal kept {cb.get('normal', 0)} candidates (its drops, and its "
                     f"rises when sharp); the same process on the inverted signal"
                     f"{' (R4 included)' if info.get('r4_inverted') else ''} kept {cb.get('inverted', 0)} sharp rises. "
                     f"{cb.get('rises_found_by_both', 0)} rises were found by both runs and kept once "
                     f"({cb.get('same_event_removed', 0)} duplicates removed); {cb.get('folded_across_runs', 0)} "
                     f"candidates were part of a much deeper event from the other run (the rise back after a drop, the "
                     f"fall back after a spike) and folded into it. A rise is kept only when its steepest 1-second "
                     f"step is at least {info.get('rise_sharpness', 10):g} times the channel's 1-second step noise.")
        ig = inv.get("gates") or {}
        if ig:
            notes.append(f"Inverted run's gates: {ig.get('flat', 0)} flat drift, {ig.get('below_floor', 0)} below the "
                         f"floor, {ig.get('other_polarity', 0)} were the recording's drops (the first run's job), "
                         f"{ig.get('not_sharp', 0)} rises not sharp.")
    bx, gt, so = info.get("boxes") or {}, info.get("gates") or {}, info.get("scan_own") or {}
    if bx:
        notes.append(f"Boxes (the Library's whole drop): {bx.get('candidates', 0)} merged proposals pointed at "
                     f"{bx.get('events', 0)} events; {bx.get('not_events', 0)} of those were no event by the run's own "
                     f"rules (under the noise floor, or a rise not sharp) and were set aside before events were joined; "
                     f"{bx.get('same_event', 0)} were the same event as another and were folded; "
                     f"{bx.get('no_event', 0)} proposals pointed at no event and were dropped.")
    if gt:
        notes.append(f"Gates: {gt.get('flat', 0)} removed as flat drift "
                     f"({', '.join(f'{k} {v}' for k, v in (gt.get('flat_by_kind') or {}).items())}); "
                     f"{gt.get('below_floor', 0)} below the noise floor"
                     + (f"; {gt.get('not_sharp', 0)} rises not sharp" if "not_sharp" in gt else "")
                     + (f"; {gt.get('not_distinct', 0)} drops not told from noise" if "not_distinct" in gt else "")
                     + ".")
    dr = info.get("drop_rule") or {}
    if dr:
        notes.append(f"Your event rule: a drop counts when it is sharp (steepest 1-second step at least "
                     f"{dr.get('sharp', 10):g} times the step noise) or falls steadily - at least "
                     f"{dr.get('min_steady_samples', 5)} samples each lower than the last - to a bottom at least "
                     f"{dr.get('min_significance', 6):g} times the fine noise below the average of the points "
                     f"{dr.get('side_s', 10):g} s either side. A rise counts when it is sharp. The same rule, as a "
                     f"finder ('event rule'), proposed every place that meets it; it never raises a confidence.")
    if so:
        notes.append(f"R4 scan windows over no candidate: {so.get('hits', 0)}; {so.get('no_event', 0)} held no event; "
                     f"{so.get('below_min_p_after_redraw', 0)} fell under 0.5 once redrawn around their event.")
    if info.get("errors"):
        notes.append("<b>Errors:</b> " + html.escape("; ".join(f"{k}: {v.splitlines()[-1]}" for k, v in info["errors"].items())))
    return notes


def build(ref, conn):
    out = os.path.join(K.OUT, ref["key"])
    with open(os.path.join(out, "run.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    c = pd.read_csv(os.path.join(out, "candidates.csv"))
    s = pd.read_csv(os.path.join(out, "sequences.csv"))
    acc = pd.read_csv(os.path.join(out, "known_accepted.csv"))
    rej = pd.read_csv(os.path.join(out, "known_rejected.csv"))
    win = pd.read_csv(os.path.join(out, "known_windows.csv"))
    rec = K.recording(conn, meta["recording"]["id"])
    a, b = meta["stretch"]["start_idx"], meta["stretch"]["end_idx"]
    factor, _ = read_as_mv(rec["units"])
    x_mv = K.load_samples(rec, a, b) * factor
    sig = quantise(x_mv)
    counts = {k: int(sum(1 for v in c["sources"] if isinstance(v, str) and k in v.split("|"))) for k in SOURCES}
    counts["r4_scan"] = int((c["kind"] == "r4_scan").sum())
    counts["none"] = int(sum(1 for v, k in zip(c["sources"], c["kind"]) if k != "r4_scan" and not (isinstance(v, str) and v)))
    counts["drop"] = int((c["polarity"] == "drop").sum()) if "polarity" in c else int(len(c))
    counts["spike"] = int((c["polarity"] == "spike").sum()) if "polarity" in c else 0
    seq2, s2, info2 = sequences_without_scan(c, float(rec["fs"]))
    meta["info"]["sequence_info_without_scan"] = info2
    data = {
        "title": "Auto-detect · " + ref["title"], "why": "Reference: " + ref["why"] + ".",
        "fs": float(rec["fs"]), "n": int(b - a), "start_idx": int(a), "hours": (b - a) / rec["fs"] / 3600.0,
        "recording_id": int(rec["id"]), "signal": sig, "source_names": SOURCES, "source_counts": counts,
        "has_scan": bool(counts["r4_scan"]), "known_names": KNOWN_NAMES,
        "cands": {**columnar_candidates(c), "seq2": seq2.tolist()},
        "seqs": seqs_payload(s), "seqs2": seqs_payload(s2),
        "accepted": spans(acc, {"tr": acc["train_id"].fillna("").astype(str).tolist() if len(acc) else []}),
        "rejected": spans(rej),
        "windows": spans(win, {"v": [1 if v == "interesting" else 0 for v in win["verdict"]] if len(win) else []}),
        "eval": meta["evaluation"], "timings": meta["timings"], "wall_s": meta["wall_s"],
        "seed_report": meta["info"].get("seed_report", []),
        "rise_sharpness": meta["info"].get("rise_sharpness"), "by_polarity": meta["evaluation"].get("by_polarity", {}),
        "r4_inverted": bool(meta["info"].get("r4_inverted")),
        "whole_drop": (meta.get("rule_files") or {}).get("Working/interrogation/whole_drop.py"),
    }
    data["run_notes"] = run_notes(meta, c)
    page = open(TEMPLATE, encoding="utf-8").read()
    page = page.replace("__TITLE__", html.escape(data["title"]))
    page = page.replace("__DATA__", json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/"))
    path = os.path.join(out, "viewer.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    r5 = next((r for r in meta["evaluation"]["by_threshold"] if abs(r["threshold"] - 0.5) < 1e-9), {})
    print(f"{ref['key']}: {path} ({os.path.getsize(path) / 1e6:.1f} MB; quantum {sig['quantum_mv']:.2e} mV)")
    return {"key": ref["key"], "title": ref["title"], "why": ref["why"], "wall_s": meta["wall_s"],
            "candidates": int(len(c)), "scan_only": counts["r4_scan"], "sequences": int(len(s)),
            "accepted": int(len(acc)), "rejected": int(len(rej)), "windows": int(len(win)),
            "found05": r5.get("accepted_found"), "hit05": r5.get("hit_rate"), "cands05": r5.get("candidates"),
            "pfound05": r5.get("proposals_found"), "phit05": r5.get("proposals_hit_rate"),
            "pcands05": r5.get("proposals"), "hours": data["hours"], "comparison": "__" in ref["key"],
            "by_polarity": meta["evaluation"].get("by_polarity", {})}


INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auto-detect references (v4)</title><style>
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1c2026;--muted:#5d6570;--line:#e2e4e7;--accent:#4f46e5}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#111316;--panel:#191c20;--ink:#e6e8eb;--muted:#9aa3ae;--line:#2a2f35;--accent:#8f8aff}}
:root[data-theme="dark"]{--bg:#111316;--panel:#191c20;--ink:#e6e8eb;--muted:#9aa3ae;--line:#2a2f35;--accent:#8f8aff}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:21px;margin:0 0 4px}a{color:var(--accent)}
.sub{color:var(--muted);margin:0 0 14px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}.card h2{font-size:15px;margin:0 0 4px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:13px;margin-top:8px}.kv div:nth-child(odd){color:var(--muted)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-top:14px;font-size:13.5px}
</style></head><body><main><h1>Auto-detect v4 — your event rule (23 Nov 2026)</h1>
<p class="sub">One button's worth of work on four channels with known regions of interest. Open a reference to zoom,
pan, scan across and step through what it found. The method and its caveats are in <code>README.md</code> beside
this page. v4 applies your rule for telling an event from noise (a drop: sharp, or at least 5 samples falling
steadily to a bottom well below its surroundings; a rise: sharp), uses the same rule to find the small events no
detector proposed (the trains), folds each event's return into it, stops boxes at their neighbours, and runs on the
committed whole-drop rule. Earlier pages, for comparison: <a href="../20261123_v3/index.html">v3</a> ·
<a href="../20261123/index.html">v2</a> · <a href="../20261119/index.html">v1</a>.</p><div class="cards">__CARDS__</div>
<div class="panel"><b>How a candidate's confidence is built.</b> R4 (the classifier trained on your verdicts) scores
every candidate's own span. Each other source that agrees closes part of the remaining gap to certainty:
confidence = 1 − (1 − R4) × Π (1 − ½ × precision of each agreeing source). Precisions: drop v1 0.955, drop v5 0.812,
wavelet 0.862, BEADS 0.675 (thesis, M2_aug), seed matches 0.9, BEADS &sigma; 0.75 (provisional), the event rule 0 (it
proposes, never vouches). A candidate R4's window scan found alone keeps R4's
score. <b>Found</b> means a candidate covers at least half of the shorter of it and your accepted span;
<b>hit rate</b> counts only candidates that land on reviewed material.</div></main></body></html>"""


def main():
    conn = K.connect()
    cards = []
    for ref in K.REFERENCES:
        if not os.path.isfile(os.path.join(K.OUT, ref["key"], "run.json")):
            print(f"{ref['key']}: not run yet")
            continue
        r = build(ref, conn)
        pct = (lambda v: "–" if v is None else f"{100 * v:.0f} %")
        cards.append(
            f"<div class='card'{' style=\"opacity:.8\"' if r['comparison'] else ''}><h2><a href='{r['key']}/viewer.html'>"
            f"{html.escape(r['title'])}</a></h2>"
            f"<div style='color:var(--muted);font-size:13px'>{html.escape(r['why'])}</div><div class='kv'>"
            f"<div>run time</div><div>{r['wall_s'] / 60:.1f} min for {r['hours']:.0f} h</div>"
            f"<div>candidates</div><div>{r['candidates']} ({r['scan_only']} found by R4's scan alone); "
            f"{r['cands05']} at ≥ 0.5</div>"
            f"<div>sequences</div><div>{r['sequences']}</div>"
            + (f"<div>at ≥ 0.5, by type</div><div>{r['by_polarity'].get('drops', {}).get('candidates_05', 0)} drops · "
               f"{r['by_polarity'].get('rises', {}).get('candidates_05', 0)} rises "
               f"({r['by_polarity'].get('rises', {}).get('from_inverted_run', 0)} from the inverted run)</div>"
               if r.get("by_polarity") else "") +
            f"<div>your reviews here</div><div>{r['accepted']} accepted, {r['rejected']} rejected"
            + (f", {r['windows']} 10-min windows" if r['windows'] else "") + "</div>"
            f"<div>at ≥ 0.5, all</div><div>found {r['found05']} of {r['accepted']} accepted; hit rate {pct(r['hit05'])}</div>"
            f"<div>at ≥ 0.5, without R4's scan</div><div>{r['pcands05']} candidates; found {r['pfound05']} of "
            f"{r['accepted']}; hit rate {pct(r['phit05'])}</div>"
            f"</div></div>")
    with open(os.path.join(K.OUT, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(INDEX.replace("__CARDS__", "".join(cards)))
    print(os.path.join(K.OUT, "index.html"))


if __name__ == "__main__":
    main()
