"""
build_pool.py
=============
The 24 Nov drop pool: every drop the auto-detect found across the datasets (`run_pool.py`) that the researcher has
not judged and has not been shown, and that passes the 24 Nov review queue's rules for a clean, clear event.

In plain words
--------------
The researcher, 24 Nov: "use the same prioritisation/confidence scoring/thresholds to evaluate and filter the final
candidates. Use the candidates i marked not interesting or unsure to also update your filtering process. Ignore rises
for now ... Goal is minimum of 100,000 new, unseen and unjudged candidates (not including the 5000 already in the
review queue) ... up to 1M ... feed them into the plotting structures of the NeurIPS agent".

* **The same rules as queue 57** (`build_review_queue.py`, imported, not copied): confidence >= 0.6; a detector, a
  seed or a rule vouched for it; not the recovery of the event before it; box no longer than the channel allows; the
  box does not run into a bigger event the other way; a clean window (no gap, no dropout, no span judged an
  artifact, no unexplained jump); at least 15x the noise of its own window; overlapping boxes keep the better one;
  M4-like runs rank 0.1 higher.
* **Unjudged**: no judged event span on any copy of the channel matches it (the queue's test). **Unseen**: no item of
  ANY review queue (open, closed or archived; queue 57 included) matches it.
* **Updated from the researcher's verdicts.** Queue 57 (209 accepted, 7 unsure, 2 artifact by 24 Nov evening) is too
  small to fit a rule to, so each idea its doubtful drops suggested was tested against every earlier verdict on the
  same kind of drop (`calibration.csv`: the judged drops that pass every other rule):
  - rises are left out (4 of its 9 not accepted were rises; the researcher said ignore rises);
  - a SLOW DECLINE is left out: a drop whose fall never steps further in a second than the channel's own step noise
    (queue 57's #184, sharpness 0.54, was one; all 5 such judged drops were rejected or unsure);
  - tested and NOT made rules, because the verdicts do not back them: drops only the event-rule finder vouched for
    (80 % of 491 accepted, against 89 %; they stay, flagged `finder_only`), a dip small against the slow wander around
    it (`prominence`: the lowest band was accepted 88 %), the slow lead-in of a deeper drop (`shoulder`: 88 %).
  These numbers are from the first 38 channels (24 Nov evening, 2,535 judged drops). On all 144 (25 Nov, 4,794 judged
  drops on nine datasets): finder-only 77 % against 87 % among the drops passing the core's settings; 7 judged slow
  declines, 2 accepted (both on S_commune, at the extended tier's confidence and clarity) and none of the 5 at the
  core's; the rules stand (`docs/autodetect/20261124_pool/checks/core_verdicts.out.txt`).
* Every candidate that lands on a judged span keeps its label (`label`), so how often each band was accepted can be
  read off the researcher's own past verdicts (`calibration.csv`).

Stages
------
    flags   per recording, as `run_pool.py` finishes them: the rules, the labels, the whole-drop measures of the
            drops that pass them (`--follow` waits for more)
    choose  calibrate, choose, cap at 1,000,000, write the pool

Read-only on the database. Writes DATA/derived/autodetect/pool_20261124/{flags,seqs}/ and pool.parquet, and the small
tables to docs/autodetect/20261124_pool/.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/build_pool.py flags [--follow]
    ... build_pool.py choose
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as K  # noqa: E402

ROOT = K.ROOT
os.chdir(ROOT)
WHOLE_DROP_PIN = K.pin_whole_drop(os.environ.get("AUTODETECT_WHOLE_DROP_REV", "HEAD"))

import run_pool as P  # noqa: E402
import build_review_queue as B  # noqa: E402
from Working.discovery.candidate_events import _caught  # noqa: E402
from Working.units import read_as_mv  # noqa: E402

POOL = P.POOL
FLAGS = os.path.join(POOL, "flags")
SEQS = os.path.join(POOL, "seqs")
DOCS = os.path.join(ROOT, "docs", "autodetect", "20261124_pool")
REFS = os.path.join(POOL, "reference_spans.parquet")
#: the columns of the pool's committed copy (docs/.../pool_compact.parquet): enough to find, rank and redraw a drop.
#: Times are left out (start_s = start_idx / fs_run), and so are priority (confidence + 0.1 when m4_like) and
#: n_sources (count the `|`s); the full pool, at full precision, is DATA/derived/autodetect/pool_20261124/pool.parquet
COMPACT = ("rank", "tier", "dataset", "species", "source_file", "recording_id", "channel", "native_fs", "decimation",
           "fs_run", "candidate_id", "start_idx", "end_idx", "onset", "extremum", "event_end", "confidence", "p_r4",
           "m4_like", "clarity", "depth_mv", "sharpness", "sources", "finder_only", "prominence", "shoulder",
           "glitch", "wd_ok", "wd_top", "wd_bottom", "wd_recovery", "wd_depth_mv", "wd_fall_s", "wd_width_s",
           "wd_recovery_s", "wd_steep_s", "wd_n_events", "wd_long_tail", "sequence_id")
#: decimals kept in the committed copy: finer than any rule or figure reads
COMPACT_DECIMALS = {"confidence": 4, "p_r4": 4, "clarity": 1, "depth_mv": 3, "wd_depth_mv": 3, "sharpness": 2,
                    "prominence": 2, "wd_fall_s": 1, "wd_width_s": 1, "wd_recovery_s": 1, "wd_steep_s": 1}


def compact(pool):
    """The `COMPACT` columns, rounded to `COMPACT_DECIMALS`, at 32 bits (the longest channel is ~2M run samples), the
    whole-drop sample indices as integers (-1 where the rule could not measure), the text as categories."""
    out = pool[[k for k in COMPACT if k in pool]].copy()
    for k in ("wd_top", "wd_bottom", "wd_recovery", "wd_n_events"):
        if k in out:
            out[k] = np.nan_to_num(out[k].to_numpy(float), nan=-1).round().astype(np.int32)
    for k in out.columns:
        v = out[k]
        if v.dtype == object or str(v.dtype) == "string":
            out[k] = v.astype("category")
        elif v.dtype.kind == "i":
            out[k] = v.astype(np.int32)
        elif v.dtype.kind == "f":
            out[k] = v.round(COMPACT_DECIMALS.get(k, 6)).astype(np.float32)
    return out


#: The most kept ("go for gold, up to 1M surviving candidates").
CAP = 1_000_000
#: The least the researcher asked for.
GOAL = 100_000
ACCEPT = ("interesting", "seed")
REJECT = ("not_interesting", "artifact")
#: The event-rule finder's source name: a drop only it vouched for has R4's confidence alone.
FINDER = "event_rule"
#: The loosest settings a final choice may use; every drop passing them is measured by the whole-drop rule.
MEASURE_FROM = {"confidence": 0.5, "clarity": 10.0}
#: A drop whose steepest 1-s step is at most this many times the channel's step noise is a slow decline (`slow_only`).
MIN_SHARPNESS = 1.0


# ── what was judged or shown, on every copy of every channel ─────────────────

def reference_spans(conn):
    """Every judged event span (with its verdict), every span judged an artifact, and every item of every review
    queue, on the physical channel's canonical recording (`accepted_catalogue.canonical_span`). Cached."""
    if os.path.isfile(REFS):
        return pd.read_parquet(REFS)
    from Working.review import queues as Q
    mod = K._load_catalogue_module()
    rows, recs = mod.collect(conn)
    out = []
    for r in rows:
        if r.get("placement_ambiguous") or not r.get("valid_bounds"):
            continue
        base = {"canonical": int(r["canonical_recording_id"]), "start": int(r["canonical_start"]),
                "end": max(int(r["canonical_end"]), int(r["canonical_start"]) + 1), "verdict": r["verdict"],
                "ref": str(r["ref"]), "queue_id": -1}
        if r["kind"] == "event_span":
            out.append({**base, "what": "judged"})
        if r["verdict"] == "artifact":
            out.append({**base, "what": "artifact"})
    n_items = 0
    for q in conn.execute("SELECT id FROM review_queues ORDER BY id").fetchall():
        for it in Q.queue_items(conn, int(q[0])):
            if it.get("recording_id") is None:
                continue
            rec = recs[int(it["recording_id"])]
            for s0, e0 in (it.get("member_spans") or [(it["start_idx"], it["end_idx"])]):
                crid, cs, ce = mod.canonical_span(rec, int(s0), int(e0), recs)
                out.append({"canonical": int(crid), "start": int(cs), "end": max(int(ce), int(cs) + 1),
                            "verdict": "", "ref": f"queue {int(q[0])}", "queue_id": int(q[0]), "what": "queued"})
                n_items += 1
    df = pd.DataFrame(out)
    os.makedirs(POOL, exist_ok=True)
    df.to_parquet(REFS, index=False)
    return df


def canonical_of(conn, rec):
    """``(canonical recording id, its fs)`` for a searched recording."""
    mod = K._load_catalogue_module()
    recs = {int(r["id"]): dict(r) for r in conn.execute("SELECT * FROM recordings")}
    crid, _s, _e = mod.canonical_span(rec, 0, 1, recs)
    return int(crid), float(recs[int(crid)]["fs"])


# ── three measures the queue did not have, tested against the researcher's verdicts (`calibration`) ─────────────

#: The window a prominence is read in: Review's own context, the box +-120 s.
PROM_PAD_S = 120.0
#: A drop whose next, deeper drop starts this soon after its bottom...
SHOULDER_GAP_S = 30.0
#: ...and is at least this much deeper, is that drop's shoulder (its slow lead-in), not an event of its own.
SHOULDER_RATIO = 2.0


def prominence(c, x_mv, fs):
    """Each candidate's depth over the spread (5th to 95th percentile) of the 10 s running median outside its box, in
    its +-120 s window: how far the drop stands out from the slow wander around it. The queue's clarity reads the
    noise ABOUT that running median, so a dip the size of the slow waves around it can still be "clear"."""
    from scipy.ndimage import median_filter
    n = len(x_mv)
    ok = np.isfinite(x_mv)
    filled = x_mv if ok.all() else np.interp(np.arange(n), np.flatnonzero(ok), x_mv[ok])
    sm = median_filter(filled, size=max(3, int(round(B.CLARITY_SMOOTH_S * fs)) | 1), mode="nearest")
    sm[~ok] = np.nan
    pad = int(round(PROM_PAD_S * fs))
    depth = c["depth_mv"].to_numpy(float)
    out = np.full(len(c), np.nan)
    for i, (s, e) in enumerate(zip(c["start_idx"].to_numpy(np.int64), c["end_idx"].to_numpy(np.int64))):
        r = np.concatenate([sm[max(0, s - pad):s], sm[e:min(n, e + pad)]])
        r = r[np.isfinite(r)]
        if len(r) > 10:
            spread = float(np.percentile(r, 95) - np.percentile(r, 5))
            out[i] = np.inf if spread == 0 else depth[i] / spread
    return out


def is_shoulder(c, fs):
    """A drop whose bottom a much deeper drop follows within `SHOULDER_GAP_S` (the deeper one starting there): the slow
    lead-in of that drop, boxed on its own. Every candidate of the channel counts as the deeper one."""
    gap = int(round(SHOULDER_GAP_S * fs))
    d = c[c["polarity"].astype(str) == "drop"]
    on = d["onset"].to_numpy(float)
    order = np.argsort(on, kind="stable")
    on_s, depth_s = on[order], d["depth_mv"].to_numpy(float)[order]
    out = np.zeros(len(c), bool)
    idx = d.index.to_numpy()
    bottom = d["extremum"].to_numpy(float)
    depth = d["depth_mv"].to_numpy(float)
    for k in range(len(d)):
        if not np.isfinite(bottom[k]):
            continue
        lo = np.searchsorted(on_s, bottom[k] - gap, side="left")
        hi = np.searchsorted(on_s, bottom[k] + gap, side="right")
        if hi > lo and np.nanmax(depth_s[lo:hi]) >= SHOULDER_RATIO * depth[k]:
            out[c.index.get_loc(idx[k])] = True
    return out


# ── one recording ────────────────────────────────────────────────────────────

def flags_one(conn, rid, refs, rule, log):
    from Working.autodetect import sequences as SQ
    from Working.interrogation import whole_drop as WD
    t0 = time.perf_counter()
    run = json.load(open(os.path.join(P.RAW, str(rid), "run.json"), encoding="utf-8"))
    c = pd.read_parquet(os.path.join(P.RAW, str(rid), "candidates.parquet"))
    rec = K.recording(conn, rid)
    x, fs, dec = P.load_signal(rec)
    factor, _note = read_as_mv(rec["units"])
    x_mv = x * factor
    crid, cfs = canonical_of(conn, rec)
    f = fs / cfs                                   # canonical samples -> this run's samples
    mine = refs[refs["canonical"] == crid].copy()
    mine["start"] = np.round(mine["start"] * f).astype(np.int64)
    mine["end"] = np.maximum(np.round(mine["end"] * f).astype(np.int64), mine["start"] + 1)
    judged = mine[mine["what"] == "judged"]
    artifacts = mine[mine["what"] == "artifact"]
    queued = mine[mine["what"] == "queued"]
    if not len(c):
        out = pd.DataFrame()
    else:
        for col in ("onset", "extremum", "event_end", "start", "end"):
            c[col] = pd.to_numeric(c[col], errors="coerce")
        c["ref"] = rid
        cs, ce = c["start_idx"].to_numpy(np.int64), c["end_idx"].to_numpy(np.int64)
        region_len = int(round(B.REGION_S * fs))
        c["reviewed"] = B.same_event(cs, ce, judged, rule, region_len)
        c["seen"] = B.same_event(cs, ce, queued, rule, region_len)
        # the researcher's own label, where a judged span is this event (accepted wins, then rejected, then unsure)
        lab = np.full(len(c), "", dtype=object)
        for name, verdicts in (("unsure", ("unsure",)), ("rejected", REJECT), ("accepted", ACCEPT)):
            sub = judged[judged["verdict"].isin(verdicts)]
            if len(sub):
                lab[B.same_event(cs, ce, sub, rule, region_len)] = name
        c["label"] = lab
        flags, noise, clarity = B.context_flags(c, x_mv, fs, artifacts)
        for k, v in flags.items():
            c[f"ctx_{k}"] = v
        c["clarity"] = clarity
        c["unclear"] = ~(np.nan_to_num(clarity, nan=0.0) >= B.CLARITY_MIN)
        c["swings_back"] = B.swings_back(c, x_mv)
        acc = c[c["label"] == "accepted"]
        cap = min(B.MAX_BOX_S, float(acc["duration_s"].quantile(B.BOX_QUANTILE))) if len(acc) >= 10 else B.MAX_BOX_S
        c["box_cap_s"] = cap
        c["too_long"] = c["duration_s"] > cap
        src = c["sources"].fillna("").astype(str)
        c["no_source"] = (c["kind"] != "proposal") | (src == "")
        c["finder_only"] = src == FINDER
        c["is_return"] = B.is_return(c, fs)
        c["step_noise_mv"] = noise
        c["prominence"] = prominence(c, x_mv, fs)
        c["shoulder"] = is_shoulder(c.reset_index(drop=True), fs)
        out = c[c["polarity"].astype(str) == "drop"].copy()
        # drop sequences, found per polarity as the combined runs find them
        labels, seqs, _info = SQ.find_sequences(out[["start", "end", "confidence"]].reset_index(drop=True), fs)
        out["sequence_id"] = labels
        out["start_s"] = out["start_idx"] / fs
        if len(seqs):
            seqs = seqs.copy()
            seqs["polarity"] = "drop"
            seqs["start_s"] = seqs["start"] / fs
            seqs["end_s"] = seqs["end"] / fs
        table = B.sequence_table(out, seqs, f"rec{rid}") if len(seqs) else pd.DataFrame()
        if len(table):
            table["recording_id"] = rid
            os.makedirs(SEQS, exist_ok=True)
            table.to_parquet(os.path.join(SEQS, f"{rid}.parquet"), index=False)
        # the whole-drop measures the plots draw, for every drop a final choice could keep: the per-candidate rules
        # at their loosest settings under consideration (0.5 confidence - the pipeline's own line -, clarity 10, the
        # finder's lone drops in), so the choice can be made on the researcher's verdicts without measuring again
        # (the judged ones too, so the calibration can test the measures on the researcher's own verdicts)
        passes = rule_mask(out.assign(reviewed=False, seen=False), with_overlap=False,
                           min_confidence=MEASURE_FROM["confidence"], finder_only_out=False,
                           clarity_min=MEASURE_FROM["clarity"])
        cols = {k: np.full(len(out), np.nan) for k in ("wd_top", "wd_bottom", "wd_recovery", "wd_depth_mv",
                                                       "wd_fall_s", "wd_width_s", "wd_recovery_s", "wd_steep_s",
                                                       "wd_n_events")}
        long_tail = np.zeros(len(out), dtype=bool)
        wd_ok = np.zeros(len(out), dtype=bool)
        s_arr, e_arr = out["start_idx"].to_numpy(np.int64), out["end_idx"].to_numpy(np.int64)
        on_arr = out["onset"].to_numpy(float)
        for i in np.flatnonzero(passes.to_numpy(bool)):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                try:
                    r = WD.measure(x, int(s_arr[i]), int(e_arr[i]), fs, to_mv=factor,
                                   anchor=int(on_arr[i]) if on_arr[i] == on_arr[i] else None)
                except Exception:  # noqa: BLE001 - one unmeasurable drop is a NaN row, said in the counts
                    continue
            if not r.get("ok"):
                continue
            wd_ok[i] = True
            for k, src_k in (("wd_top", "top_idx"), ("wd_bottom", "bottom_idx"), ("wd_recovery", "recovery_idx"),
                             ("wd_depth_mv", "depth_mv"), ("wd_fall_s", "fall_s"), ("wd_width_s", "width_s"),
                             ("wd_recovery_s", "half_recovery_s"), ("wd_steep_s", "steep_s"),
                             ("wd_n_events", "n_events")):
                v = r.get(src_k)
                cols[k][i] = np.nan if v is None else float(v)
            long_tail[i] = bool(r.get("long_tail"))
        for k, v in cols.items():
            out[k] = v
        out["wd_long_tail"] = long_tail
        out["wd_ok"] = wd_ok
        # a glitch: down and back within two samples (top to half recovery)
        out["glitch"] = wd_ok & (out["wd_width_s"].to_numpy(float) * fs <= 2.0)
        out["dataset"] = run["target"]["dataset"]
        out["species"] = run["target"]["species"]
        out["source_file"] = rec["source_file"]
        out["channel"] = int(rec["channel"])
        out["native_fs"] = float(rec["fs"])
    os.makedirs(FLAGS, exist_ok=True)
    out.to_parquet(os.path.join(FLAGS, f"{rid}.parquet"), index=False)
    n_ok = int(rule_mask(out, with_overlap=False).sum()) if len(out) else 0
    n_wd = int(out["wd_ok"].sum()) if len(out) else 0
    log(f"flags rec {rid} ({run['target']['dataset']} CH{rec['channel']}): {len(out):,} drops, {n_ok:,} pass the "
        f"rules before overlap ({n_wd:,} measured at the loosest settings); judged here "
        f"{int((out['label'] != '').sum()) if len(out) else 0:,}; {time.perf_counter() - t0:.0f} s")


def slow_only(c):
    """A drop whose fall never steps further in a second than the channel's own step noise (`sharpness` <= 1): a
    slow decline. Of the judged drops on the first 38 channels, all 5 such were rejected or unsure (queue 57's #184
    among them); 80-91 % of every sharper band was accepted. On all 144 channels: 7 judged, the 5 at the core's
    confidence and clarity all rejected or unsure (one M4 stretch), the 2 accepted both on S_commune below them. It
    removes 37,640 drops, 97 % on Cordyceps and Enoki. A drop whose sharpness cannot be read passes (the pipeline's convention)."""
    s = pd.to_numeric(c["sharpness"], errors="coerce")
    return (s <= MIN_SHARPNESS).fillna(False)


def rule_mask(c, *, with_overlap=True, min_confidence=B.MIN_CONFIDENCE, finder_only_out=False,
              clarity_min=B.CLARITY_MIN, slow_out=True):
    """Every per-candidate rule (the queue's, plus what the researcher's verdicts added) - True = kept."""
    if not len(c):
        return pd.Series(dtype=bool)
    clear = pd.Series(np.nan_to_num(c["clarity"].to_numpy(float), nan=0.0) >= clarity_min, index=c.index)
    keep = (c["confidence"] >= min_confidence) & ~c["no_source"] & ~c["is_return"] & ~c["reviewed"] & ~c["seen"] \
        & ~c["too_long"] & ~c["swings_back"] & ~c["ctx_nan"] & ~c["ctx_flat"] & ~c["ctx_artifact"] \
        & ~c["ctx_jump"] & clear & (c["polarity"].astype(str) == "drop")
    if finder_only_out:
        keep &= ~c["finder_only"]
    if slow_out:
        keep &= ~slow_only(c)
    return keep


#: The reason a drop is left out, the first that applies (the queue's order, the new rules beside their kin).
REASONS = [
    ("below 0.6 confidence", lambda c: c["confidence"] < B.MIN_CONFIDENCE),
    ("no detector, seed or rule vouched for it (R4 alone)", lambda c: c["no_source"]),
    ("a slow decline: its fall never steps beyond the step noise (new 24 Nov, from the verdicts)", slow_only),
    ("the recovery or way back of the event just before it", lambda c: c["is_return"]),
    ("already judged (any copy)", lambda c: c["reviewed"]),
    ("already in a review queue (any queue, queue 57 included)", lambda c: c["seen"]),
    ("box longer than the channel's cap", lambda c: c["too_long"]),
    ("its box runs into a bigger event the other way", lambda c: c["swings_back"]),
    ("gap in the data in its window", lambda c: c["ctx_nan"]),
    ("dropout (flat line) in its window", lambda c: c["ctx_flat"]),
    ("a span judged an artifact in its window", lambda c: c["ctx_artifact"]),
    ("a jump far bigger than the event in its window", lambda c: c["ctx_jump"]),
    ("not clear against the noise around it", lambda c: c["unclear"]),
]


def cmd_flags(args):
    P.install_write_guard()
    conn = K.connect()
    from Working.discovery.matching import rule_from_settings
    rule = rule_from_settings(conn)
    refs = reference_spans(conn)
    logf = open(os.path.join(POOL, "flags.log"), "a", encoding="utf-8")

    def log(msg):
        line = f"{dt.datetime.now():%H:%M:%S} {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    log(f"flags: {len(refs):,} reference spans ({refs['what'].value_counts().to_dict()})")
    order = [int(r["id"]) for r, _t in P.targets(conn)]
    while True:
        pending = [rid for rid in order if P.done(rid) and not os.path.isfile(os.path.join(FLAGS, f"{rid}.parquet"))]
        if args.only:
            pending = [rid for rid in pending if rid in {int(i) for i in args.only}]
        for rid in pending:
            try:
                flags_one(conn, rid, refs, rule, log)
            except Exception as exc:  # noqa: BLE001 - loud, with the traceback; the next recording goes on
                import traceback
                log(f"flags rec {rid} FAILED: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
                os.makedirs(FLAGS, exist_ok=True)
                with open(os.path.join(FLAGS, f"{rid}.failed"), "w", encoding="utf-8") as fh:
                    fh.write(traceback.format_exc())
        remaining = [rid for rid in order if not os.path.isfile(os.path.join(FLAGS, f"{rid}.parquet"))
                     and not os.path.isfile(os.path.join(FLAGS, f"{rid}.failed"))]
        if not args.follow or not remaining:
            break
        time.sleep(30)
    log("flags: finished")


# ── the choice ───────────────────────────────────────────────────────────────

def load_flags():
    frames = []
    for name in sorted(os.listdir(FLAGS)):
        if name.endswith(".parquet"):
            df = pd.read_parquet(os.path.join(FLAGS, name))
            if len(df):
                frames.append(df)
    return pd.concat(frames, ignore_index=True)


def m4_reference_tables():
    """M4 CH1_A1's v4 sequences (both kinds, as queue 57 measured M4-likeness against them)."""
    ref = next(r for r in K.REFERENCES if r["key"] == "M4_CH1_A1")
    c = pd.read_csv(os.path.join(K.OUT, ref["key"], "candidates.csv"))
    s = pd.read_csv(os.path.join(K.OUT, ref["key"], "sequences.csv"))
    return B.sequence_table(c, s, "M4_CH1_A1")


def calibration(allc):
    """How often the researcher accepted the candidates that land on a judged span, by band - the drops that pass
    every other rule (what the pool would hold if they had not been judged)."""
    c = allc[allc["label"] != ""].copy()
    # judged events were mostly judged in a queue, so "already in a queue" is set aside here with "already judged";
    # the loosest settings a choice may use, so the table can say what loosening would let in
    other = rule_mask(c.assign(reviewed=False, seen=False), with_overlap=False,
                      min_confidence=MEASURE_FROM["confidence"], finder_only_out=False,
                      clarity_min=MEASURE_FROM["clarity"])
    c = c[other.to_numpy(bool)]
    c["finder alone"] = c["finder_only"].map({True: "only the finder vouched", False: "a detector or seed vouched"})
    c["strict"] = rule_mask(c.assign(reviewed=False, seen=False), with_overlap=False).map(
        {True: "passes the queue's settings", False: "only the looser settings"})
    rows = []

    def add(by, name, bins=None):
        key = pd.cut(c[by], bins) if bins is not None else c[by]
        for k, g in c.groupby(key, observed=True):
            n_acc, n_rej, n_uns = (g["label"] == "accepted").sum(), (g["label"] == "rejected").sum(), (g["label"] == "unsure").sum()
            rows.append({"by": name, "band": str(k), "judged": int(len(g)), "accepted": int(n_acc),
                         "rejected": int(n_rej), "unsure": int(n_uns),
                         "accepted_share": float(n_acc / len(g)) if len(g) else np.nan})

    add("confidence", "confidence", [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0001])
    add("clarity", "clarity", [10, 15, 20, 30, 50, 100, 300, 1e12])
    if "prominence" in c:
        add("prominence", "prominence", [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 1e12])
        c["glitch_s"] = c["glitch"].map({True: "down and back within 2 samples", False: "wider"})
        add("glitch_s", "glitch")
        c["shoulder_s"] = c["shoulder"].map({True: "a 2x deeper drop starts within 30 s of its bottom",
                                             False: "no such drop"})
        add("shoulder_s", "shoulder")
    # the doubtful drops of queue 57: two slow declines (sharpness 0.5 and 5.6), two sub-millivolt CH14 dips
    add("sharpness", "sharpness (steepest 1-s step / step noise)", [0, 1, 2, 3, 5, 10, 20, 50, 1e12])
    add("depth_mv", "depth (mV)", [0, 0.25, 0.5, 1, 2, 5, 10, 1e12])
    add("duration_s", "box (s)", [0, 10, 30, 60, 120, 300, 600, 1200])
    add("n_sources", "agreeing sources")
    add("finder alone", "who vouched")
    add("strict", "settings")
    add("dataset", "dataset")
    return pd.DataFrame(rows)


def cmd_choose(args):
    t0 = time.perf_counter()
    allc = load_flags()
    allc["ref"] = allc["recording_id"]
    os.makedirs(DOCS, exist_ok=True)
    # M4-likeness: each drop run against M4's runs, in units of M4's own spread (the queue's rule)
    tables = [m4_reference_tables()] + [pd.read_parquet(os.path.join(SEQS, n)) for n in sorted(os.listdir(SEQS))
                                       if n.endswith(".parquet")] if os.path.isdir(SEQS) else [m4_reference_tables()]
    seqs, threshold = B.m4_likeness(pd.concat(tables, ignore_index=True), "M4_CH1_A1")
    like = {(r.ref, int(r.sequence_id)): (bool(r.m4_like), float(r.m4_distance)) for r in seqs.itertuples(index=False)}
    keys = [f"rec{int(r)}" for r in allc["recording_id"]]
    allc["m4_like"] = [like.get((k, int(q)), (False, np.nan))[0] if q >= 0 else False
                       for k, q in zip(keys, allc["sequence_id"])]
    allc["m4_distance"] = [like.get((k, int(q)), (False, np.nan))[1] if q >= 0 else np.nan
                           for k, q in zip(keys, allc["sequence_id"])]
    allc["priority"] = allc["confidence"] + B.M4_BONUS * allc["m4_like"].astype(float)
    cal = calibration(allc)
    cal.to_csv(os.path.join(DOCS, "calibration.csv"), index=False)
    allc["left_out"] = ""
    for name, fn in REASONS:
        m = fn(allc).to_numpy(bool)
        allc.loc[(allc["left_out"] == "") & m, "left_out"] = name
    # two tiers: the core (the queue's settings, plus the verdicts' rule) and, behind it, the drops that miss the core
    # only on confidence (0.5-0.6, the pipeline's own line) or clarity (10-15) - "go for gold", flagged apart
    core = (allc["left_out"] == "").to_numpy()
    loose = rule_mask(allc, min_confidence=MEASURE_FROM["confidence"],
                      clarity_min=MEASURE_FROM["clarity"]).to_numpy(bool) & ~core
    pr = allc["priority"].to_numpy(float)
    cf = allc["confidence"].to_numpy(float)
    sh = np.nan_to_num(allc["sharpness"].to_numpy(float), nan=0.0)

    def ranked(idx):
        return idx[np.lexsort((-sh[idx], -cf[idx], -pr[idx]))]

    order = np.concatenate([ranked(np.flatnonzero(core)), ranked(np.flatnonzero(loose))])
    kept = B.overlap_keep(allc, order)
    lost = order[~kept[order]]
    allc.loc[lost[core[lost]], "left_out"] = "its box overlaps a better candidate's"
    chosen = order[kept[order]]
    if len(chosen) > CAP:
        allc.loc[chosen[CAP:], "left_out"] = f"beyond the first {CAP:,}"
        chosen = chosen[:CAP]
    allc["tier"] = ""
    allc.loc[chosen[core[chosen]], "tier"] = "core"
    allc.loc[chosen[~core[chosen]], "tier"] = "extended"
    allc.loc[chosen[~core[chosen]], "left_out"] = ""          # in the pool, in the extended tier
    pool = allc.loc[chosen].copy()
    pool["rank"] = np.arange(1, len(pool) + 1)
    pool.to_parquet(os.path.join(POOL, "pool.parquet"), index=False)
    # the pool itself in git as well (the data folder is gitignored): where each drop is and what it measured
    compact(pool).to_parquet(os.path.join(DOCS, "pool_compact.parquet"), index=False, compression="zstd")
    reasons = allc["left_out"].where(allc["left_out"] != "", "IN THE POOL (" + allc["tier"] + " tier)").value_counts() \
        .rename_axis("reason").reset_index(name="drops")
    reasons.to_csv(os.path.join(DOCS, "reasons.csv"), index=False)
    by = (allc.assign(core=allc["tier"] == "core", extended=allc["tier"] == "extended")
          .groupby(["dataset", "species", "source_file"], dropna=False)
          .agg(channels=("recording_id", "nunique"), drops_found=("candidate_id", "size"),
               drops_06=("confidence", lambda v: int((v >= 0.6).sum())), judged=("label", lambda v: int((v != "").sum())),
               core=("core", "sum"), extended=("extended", "sum"))
          .reset_index().sort_values("core", ascending=False))
    by.to_csv(os.path.join(DOCS, "by_dataset.csv"), index=False)
    ch = (allc.assign(core=allc["tier"] == "core", extended=allc["tier"] == "extended")
          .groupby(["dataset", "recording_id", "channel"]).agg(drops=("candidate_id", "size"), core=("core", "sum"),
                                                              extended=("extended", "sum"))
          .reset_index())
    ch.to_csv(os.path.join(DOCS, "by_channel.csv"), index=False)
    seqs.to_csv(os.path.join(DOCS, "sequences_m4_likeness.csv"), index=False)
    plan = {"built": dt.datetime.now().isoformat(timespec="seconds"), "drops_considered": int(len(allc)),
            "pool": int(len(pool)), "core": int((pool["tier"] == "core").sum()),
            "extended": int((pool["tier"] == "extended").sum()), "goal": GOAL, "cap": CAP, "m4_threshold": threshold,
            "whole_drop": WHOLE_DROP_PIN, "rules": [n for n, _ in REASONS] + ["its box overlaps a better candidate's"],
            "recordings": int(allc["recording_id"].nunique()), "seconds": time.perf_counter() - t0,
            "confidence_quantiles": {str(q): float(pool["confidence"].quantile(q)) for q in (0.1, 0.5, 0.9)} if len(pool) else {}}
    with open(os.path.join(DOCS, "plan.json"), "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1, default=str)
    print(json.dumps(plan, indent=1, default=str))
    print(reasons.to_string(index=False))
    print(by.to_string(index=False))
    print(cal.to_string(index=False))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("flags")
    f.add_argument("--follow", action="store_true", help="wait for run_pool.py to finish more recordings")
    f.add_argument("--only", nargs="*")
    sub.add_parser("choose")
    args = ap.parse_args(argv)
    {"flags": cmd_flags, "choose": cmd_choose}[args.cmd](args)


if __name__ == "__main__":
    main()
