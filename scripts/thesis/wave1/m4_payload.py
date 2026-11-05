"""
wave1.m4_payload — step 14, the scored held-out M4 exam.

M4_aug_concat_fs1 is exported on purpose: its exam (review queue 36, 290 items) was judged and scored on
2026-10-26 (``scripts/m4_exam_score.py``), so its data no longer need to stay unseen.

* the exam items: the sample whose meta names queue 36 (``DATA/derived/candidate_events/M4_aug_concat_fs1_*/
  sample_seed20261026_l40_f15``), with its strata and design weights;
* their verdicts: the researcher's own adjudication (``carried_from IS NULL``) given through queue 36 (a not-undone
  'verdict' row of ``review_audit`` names it) — ``m4_exam_score.exam_verdicts`` exactly — and, beside it, the newest
  own verdict whatever the route;
* R4 scores, recomputed exactly as ``m4_exam_score.minirocket_scorer`` computes them (results.json keeps no
  per-item score);
* the 48 h on the M4 channel holding the most exam items, raw at native rate, and R4 scores for every candidate
  event of the M4 table in that window;
* every exam item's context window (span +- one span length, at most 4,000 points).
"""
from __future__ import annotations

import os
import shutil

import numpy as np
import pandas as pd

from wave1 import common as C
from wave1 import export_bundle as X
from wave1 import pool as P


def exam_sample(ctx, qid):
    dirs = C.samples_with_queue(ctx).get(int(qid), [])
    if not dirs:
        fb = ctx.path((ctx.spec.get("m4_exam") or {}).get("sample_fallback") or "")
        if os.path.isfile(os.path.join(fb, "sample.parquet")):
            dirs = [fb]
    if not dirs:
        return None, None
    sd = dirs[-1]
    return pd.read_parquet(os.path.join(sd, "sample.parquet")), sd


def step_m4_exam(ctx):
    d = ctx.step_dir()
    cfg = ctx.spec.get("m4_exam") or {}
    qid = int(cfg.get("queue", 36))
    sf = ctx.kept.get("M4_aug")
    if sf is None:
        ctx.warn("M4_aug is not in this database")
        return {"items": 0}
    # the frozen manifest and the scored results, as they are on disk
    for key in ("manifest", "manifest_tracked"):
        p = ctx.path(cfg.get(key) or "")
        if cfg.get(key) and os.path.isfile(p):
            shutil.copy2(p, os.path.join(d, f"exam_{key}.json"))
    exam_dir = os.path.join(ctx.root, "DATA", "derived", "exam", "M4")
    if os.path.isdir(exam_dir):
        for fn in sorted(os.listdir(exam_dir)):
            p = os.path.join(exam_dir, fn)
            if os.path.isfile(p) and fn.lower().endswith((".json", ".md", ".csv")) and os.path.getsize(p) < 5e6:
                shutil.copy2(p, os.path.join(d, "exam_dir__" + fn))
    sample, sd = exam_sample(ctx, qid)
    if sample is None:
        ctx.warn(f"no sample names queue {qid}: the exam items cannot be listed")
        return {"items": 0}
    ids = [int(x) for x in sample["detection_id"]]
    via = X.via_queue_targets(ctx, qid)
    ver = X.queue_verdicts(ctx, ids)
    items = sample.copy()
    items["sample_dir"] = os.path.relpath(sd, ctx.root).replace("\\", "/")
    items["verdict_newest_own"] = [ver.get(i, {}).get("verdict_own") for i in ids]
    items["verdict_at"] = [ver.get(i, {}).get("verdict_own_at") for i in ids]
    items["verdict_carried"] = [ver.get(i, {}).get("verdict_carried") for i in ids]
    # m4_exam_score.exam_verdicts: own (carried_from NULL) AND written through the exam queue
    items["exam_verdict"] = [v["verdict_own"] if (i in via and v.get("verdict_own") is not None) else None
                             for i, v in ((i, ver.get(i, {})) for i in ids)]
    items["exam_y"] = items["exam_verdict"].map({"interesting": 1, "not_interesting": 0, "artifact": 0})
    fs_of = {int(r["id"]): float(r["fs"]) for r in ctx.channels_of(sf)}
    items["fs"] = items["recording_id"].map(fs_of)
    items["start_s"], items["end_s"] = items["start"] / items["fs"], items["end"] / items["fs"]
    # the table the exam sample was drawn from (the sample's parent folder), else the table every step reads
    tab = next((t for t in C.candidate_tables(ctx)
                if os.path.abspath(t["dir"]) == os.path.abspath(os.path.dirname(sd))), None) or C.newest_table(ctx, sf)
    if tab is not None:
        extra = C.read_events(tab, ["event_id", "n_agree", "matched_families", "agree_families", "anchor_variant"],
                              filters=[("event_id", "in", [int(x) for x in items["event_id"]])])
        items = items.merge(extra, on="event_id", how="left")
    sc = P.r4_scores(ctx, items[["recording_id", "start", "end"]])
    sc.index = items.index
    items = pd.concat([items, sc], axis=1)
    C.write_csv(os.path.join(d, "exam_items.csv"), items)
    ctx.log(f"exam: {len(items)} items, {int(items['exam_verdict'].notna().sum())} with an exam verdict")
    # the 48 h holding the most exam items
    L_h = float(cfg.get("hours", 48))
    by_id = {int(r["id"]): r for r in ctx.channels_of(sf)}
    on = {int(rid): g["start"].to_numpy(np.int64) for rid, g in items.groupby("recording_id")}
    fs = float(next(iter(by_id.values()))["fs"])
    L = int(round(L_h * 3600 * fs))
    key, start, count = C.best_window(on, L, {k: by_id[k]["n_samples"] for k in on})
    out = {"items": int(len(items)), "exam_verdicts": int(items["exam_verdict"].notna().sum()),
           "r4_source": str(sc["r4_source"].iloc[0]) if len(sc) else None}
    if key is not None:
        rec = by_id[key]
        ch = int(rec["channel"])
        w = X._window(ctx, name=f"m4_exam__CH{ch}__{X._hour_name(start, start + L, fs)}", rule="m4_exam",
                      short="M4_aug", sf=sf, channels=[ch], start=start, end=start + L,
                      why=f"{count} exam items in these {L_h:g} h (the most on any M4 channel)")
        x, s, e = C.read_segment(ctx, rec, w["start_idx"], w["end_idx"])
        meta = dict(C.rec_meta(rec, n_channels=len(by_id)), what=w["why"], window=w, t0_s=s / fs, start_idx=s,
                    end_idx=e, decimation=1, dt_s=1.0 / fs)
        C.save_series(ctx, os.path.join(d, w["name"]), x, meta)
        out.update(window=w["name"], window_items=count)
        if tab is not None:
            cand = C.read_events(tab, ["event_id", "recording_id", "channel", "start", "end", "n_agree",
                                       "matched_families", "agree_families", "anchor_variant", "anchor_detection_id",
                                       "label"],
                                 filters=[("recording_id", "==", int(key)), ("start", "<", int(e)), ("end", ">", int(s))])
            cand["start_s"], cand["end_s"] = cand["start"] / fs, cand["end"] / fs
            cand["is_exam_item"] = cand["event_id"].isin(set(int(x) for x in items["event_id"]))
            sc2 = P.r4_scores(ctx, cand[["recording_id", "start", "end"]])
            sc2.index = cand.index
            cand = pd.concat([cand, sc2], axis=1)
            C.write_csv(os.path.join(d, f"{w['name']}__candidates_r4.csv"), cand)
            out["window_candidates"] = int(len(cand))
        else:
            ctx.warn("no M4 candidate-event table on disk: the window's candidates are not scored")
    segs, idx, _ = C.window_rows(ctx, [{"recording_id": int(r.recording_id), "start": int(r.start), "end": int(r.end),
                                        "detection_id": int(r.detection_id), "event_id": int(r.event_id),
                                        "stratum": r.stratum, "exam_verdict": r.exam_verdict}
                                       for r in items.itertuples()])
    C.save_stack(ctx, os.path.join(d, "exam_item_windows"), segs, idx,
                 {"what": "every M4 exam item: span +- one span length (at most 4,000 points)", "queue": qid})
    out["item_windows"] = len(segs)
    return out
