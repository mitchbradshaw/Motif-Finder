"""
wave1.export_bundle — steps 1-12 of the wave-1 export (read-only; see run_wave1.py for the list).

Every query here copies a pattern from an existing reader rather than inventing one:
  recordings / datasets / units      scripts/thesis/ledger_checks.py recordings()
  live template runs, rule 1         Working/discovery/candidate_events.py load_sweep_detections()
  drop_detection_v1 channel runs     scripts/thesis/b1_intervals.py channel_runs()
  blind queues' detection ids        scripts/thesis/catalogue_stats.py blind_events(), promote_blind_accepted.py
  own verdicts (carried_from NULL)   scripts/thesis/promote_blind_accepted.py accepted()
  exam verdicts via the queue        scripts/m4_exam_score.py exam_verdicts()
  RQ2 panel key / seeds              scripts/rq2_blind.py (key.json; discovery_runs.params_json seedId / entryId)
  the 10-minute hand labels          scripts/thesis/miss_rate.py (annotations.source = 'imported_10min')
  Library members + g-05 families    scripts/thesis/library_events.py load_members()
  B4 co-occurrences                  scripts/thesis/b4_cross_channel.py (cross_census / cross_cooccurrence)
  CNN window scores                  Working/execution.py _recipe_prefix_hash + step_artifacts (the step cache)
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import shutil
import time

import numpy as np
import pandas as pd

from wave1 import common as C


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 1. meta
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def step_meta(ctx):
    d = ctx.step_dir()
    conn = ctx.conn
    recs = pd.DataFrame(list(ctx.recordings.values()))
    n_refused = int(recs["source_file"].map(C.is_refused).sum()) if len(recs) else 0
    recs = recs[~recs["source_file"].map(C.is_refused)] if len(recs) else recs
    if C.has_table(conn, "datasets"):
        ds = pd.DataFrame([dict(r) for r in conn.execute("SELECT * FROM datasets")])
        if len(ds):
            ds = ds[~ds["source_file"].map(C.is_refused)]
            C.write_csv(os.path.join(d, "datasets.csv"), ds)
            keep = [c for c in ("source_file", "display_name", "species") if c in ds.columns]
            recs = recs.merge(ds[keep].rename(columns={"display_name": "dataset_display_name",
                                                       "species": "dataset_species"}),
                              on="source_file", how="left")
    short = {sf: s for s, sf in ctx.kept.items()}
    recs["kept_as"] = recs["source_file"].map(short)
    recs["hours"] = recs["n_samples"] / recs["fs"] / 3600.0
    C.write_csv(os.path.join(d, "recordings.csv"), recs)

    kept_rows = []
    for s, sf in ctx.kept.items():
        chans = ctx.channels_of(sf)
        kept_rows.append({"short": s, "source_file": sf, "n_channels": len(chans),
                          "recording_ids": ";".join(str(r["id"]) for r in chans),
                          "fs": chans[0]["fs"] if chans else None,
                          "hours": chans[0]["n_samples"] / chans[0]["fs"] / 3600.0 if chans else None,
                          "units": chans[0].get("units") if chans else None,
                          "active": chans[0].get("active") if chans else None})
    C.write_csv(os.path.join(d, "kept_recordings.csv"), pd.DataFrame(kept_rows))

    # queues with item counts
    qrows = []
    own = C.own_adjudication_clause(conn)
    for qid, (row, f) in C.queue_filters(ctx).items():
        ids = [int(x) for x in (f.get("detection_ids") or []) if str(x).lstrip("-").isdigit()]
        files, n_own, verdicts = set(), 0, {}
        for ch in C.chunks(ids):
            marks = ",".join("?" * len(ch))
            files |= {r[0] for r in conn.execute(
                f"SELECT DISTINCT rec.source_file FROM detections d JOIN runs r ON r.id = d.run_id JOIN recordings rec "
                f"ON rec.id = r.recording_id WHERE d.id IN ({marks})", ch)}
        refused = any(C.is_refused(f_) for f_ in files) or C.mentions_refused(row.get("name")) or \
            C.mentions_refused(row.get("note"))
        if ids and not refused:
            for ch in C.chunks(ids):
                marks = ",".join("?" * len(ch))
                for v, n in conn.execute(f"SELECT a.verdict, COUNT(DISTINCT a.detection_id) FROM adjudications a "
                                         f"WHERE a.detection_id IN ({marks}) AND {own} GROUP BY a.verdict", ch):
                    verdicts[v] = verdicts.get(v, 0) + int(n)
                    n_own += int(n)
        qrows.append({"id": qid, "name": "(withheld: a S. commune queue)" if refused else row.get("name"),
                      "source_kind": row.get("source_kind"),
                      "source_ref": row.get("source_ref"), "unit": row.get("unit"), "writes_to": row.get("writes_to"),
                      "blind": row.get("blind"), "cap": row.get("cap"), "created_at": row.get("created_at"),
                      "closed_at": row.get("closed_at"),
                      "n_items_listed": len(ids) if ids else None,
                      "items_resolved_live": not bool(ids),
                      "recordings": ";".join(sorted(files)) if not refused else "(S. commune: not read)",
                      "n_with_own_verdict": None if refused else n_own,
                      "own_verdicts": None if refused else json.dumps(verdicts, sort_keys=True),
                      "filter_keys": ";".join(sorted(f)), "note": "" if refused else (row.get("note") or "")[:200]})
    C.write_csv(os.path.join(d, "queues.csv"), pd.DataFrame(qrows))

    chosen = {sf: (C.newest_table(ctx, sf) or {}).get("key") for sf in {t["source_file"] for t in
                                                                       C.candidate_tables(ctx)}}
    tabs = pd.DataFrame([dict({k: v for k, v in t.items() if k != "recordings"},
                              read_by_this_export=(chosen.get(t["source_file"]) == t["key"]))
                         for t in C.candidate_tables(ctx) if not C.is_refused(t["source_file"])])
    if len(tabs):
        tabs["dir"] = tabs["dir"].map(lambda p: os.path.relpath(p, ctx.root).replace("\\", "/"))
    C.write_csv(os.path.join(d, "candidate_tables.csv"), tabs)
    if C.has_table(conn, "groupings"):
        g = pd.DataFrame([dict(r) for r in conn.execute("SELECT * FROM groupings ORDER BY id")])
        C.write_csv(os.path.join(d, "groupings.csv"), g)
    if C.has_table(conn, "templates"):
        cols = [c for c in ("id", "name", "kind", "builtin", "version", "description")
                if c in C.columns_of(conn, "templates")]
        t = pd.DataFrame([dict(r) for r in conn.execute(f"SELECT {', '.join(cols)} FROM templates ORDER BY id")],
                         columns=cols)
        C.write_csv(os.path.join(d, "templates.csv"), t)
    return {"recordings": int(len(recs)), "refused_rows_left_out": n_refused, "kept": len(ctx.kept),
            "queues": len(qrows), "candidate_tables": int(len(tabs))}


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 2. overviews
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def overview_of(ctx, rec, bin_n):
    x = C.channel_array(ctx, rec)
    n = len(x)
    n_bins = int(math.ceil(n / float(bin_n)))
    out = np.full(n_bins, np.nan, dtype=np.float64)
    step = bin_n * 20000
    for a in range(0, n, step):
        b = min(n, a + step)
        out[a // bin_n: a // bin_n + int(math.ceil((b - a) / float(bin_n)))] = C.block_mean(np.asarray(x[a:b]), bin_n)
    factor, _ = C.mv_factor(rec)
    return (out * factor).astype(np.float32)


def step_overviews(ctx):
    d = ctx.step_dir()
    bin_s = float(ctx.spec.get("overview_bin_s", 60))
    done, files = 0, 0
    for short, sf in ctx.kept.items():
        chans = ctx.channels_of(sf)
        if not chans:
            continue
        fs = float(chans[0]["fs"])
        bin_n = max(1, int(round(bin_s * fs)))
        arrs, metas = [], []
        for r in chans:
            ctx.tick()
            try:
                t = time.time()
                arrs.append(overview_of(ctx, r, bin_n))
                metas.append(C.rec_meta(r, n_channels=len(chans)))
                done += 1
                ctx.log(f"overview {short} CH{r['channel']} ({len(arrs)}/{len(chans)}) "
                        f"{time.time() - t:.1f}s")
            except (FileNotFoundError, OSError, ValueError) as e:
                ctx.warn(f"overview {short} CH{r['channel']}: {e}")
        if not arrs:
            continue
        L = max(len(a) for a in arrs)
        X = np.full((len(arrs), L), np.nan, dtype=np.float32)
        for i, a in enumerate(arrs):
            X[i, :len(a)] = a
        meta = {"what": f"overview: mean of each {bin_s:g} s ({bin_n} samples) of every channel, whole recording",
                "source_file": sf, "short": short, "recording_id": [m["recording_id"] for m in metas],
                "channel": [m["channel"] for m in metas], "channels": metas, "fs": fs, "t0_s": 0.0,
                "dt_s": bin_n / fs, "decimation": bin_n, "start_idx": 0,
                "units_original": sorted({str(m["units_original"]) for m in metas}), "converted_to": "mV",
                "rows": "x[i] is channel channels[i]; NaN where a bin has no finite sample or past a channel's end"}
        files += len(C.save_series(ctx, os.path.join(d, f"{short}__overview{int(bin_s)}s"), X, meta))
    return {"channels": done, "npz_files": files}


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 3. full channels
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def channels_from(ctx, sf, want):
    chans = ctx.channels_of(sf)
    have = [int(r["channel"]) for r in chans]
    if want in (None, "all"):
        return have
    if isinstance(want, (int, np.integer)):
        want = [int(want)]
    out = [int(c) for c in want if int(c) in have]
    missing = [c for c in want if int(c) not in have]
    if missing:
        ctx.warn(f"{sf}: channel(s) {missing} not registered; have {have}")
    return out


def step_full_channels(ctx):
    d = ctx.step_dir()
    n = 0
    for req in ctx.spec.get("full_channels") or []:
        sf = ctx.kept.get(req["recording"])
        if sf is None:
            ctx.warn(f"full channel request {req['recording']}: recording not present")
            continue
        chans = ctx.channels_of(sf)
        for ch in channels_from(ctx, sf, req.get("channel")):
            ctx.tick()
            rec = ctx.by_file[sf][ch]
            x, s, e = C.read_segment(ctx, rec, 0, int(rec["n_samples"]))
            meta = dict(C.rec_meta(rec, n_channels=len(chans)), what=f"whole channel, native rate ({req.get('why')})",
                        t0_s=0.0, start_idx=0, end_idx=int(e), decimation=1, dt_s=1.0 / float(rec["fs"]))
            C.save_series(ctx, os.path.join(d, f"{req['recording']}__CH{ch}__full"), x, meta)
            n += 1
            ctx.log(f"full channel {req['recording']} CH{ch}: {len(x):,} samples")
    return {"channels": n}


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 4. windows (explicit + rule-based), and the CNN window scores
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def _hours_or_seconds(w, key):
    if w.get(f"{key}_s") is not None:
        return float(w[f"{key}_s"])
    if w.get(f"{key}_h") is not None:
        return float(w[f"{key}_h"]) * 3600.0
    raise ValueError(f"window {w.get('name')} gives neither {key}_s nor {key}_h")


def resolve_label(ctx, sf, label, fallback):
    """(channel index, how): a channel label (CH4_A2) through the tool's own naming, else the fallback index."""
    chans = ctx.channels_of(sf)
    n = len(chans)
    for r in chans:
        if C.channel_label(sf, r["channel"], n) == label:
            return int(r["channel"]), f"label {label} -> recordings.channel {r['channel']} " \
                                      f"(Working.discovery.channels.channel_name)"
    names = C.m2_style_names()
    if names and label in names and names.index(label) in [int(r["channel"]) for r in chans]:
        return names.index(label), f"label {label} -> index {names.index(label)} (M2_STYLE_NAMES)"
    for r in chans:
        if label and str(r.get("notes") or "").strip() == label:
            return int(r["channel"]), f"label {label} -> recordings.notes of channel {r['channel']}"
    ctx.warn(f"{sf}: channel label {label!r} could not be resolved; falling back to index {fallback}")
    return int(fallback), f"label {label} unresolved: fallback index {fallback}"


def _window(ctx, *, name, rule, short, sf, channels, start, end, why, extra=None):
    chans = ctx.channels_of(sf)
    fs = float(chans[0]["fs"])
    n = int(min(ctx.by_file[sf][c]["n_samples"] for c in channels))
    s, e = max(0, int(start)), min(n, int(end))
    w = {"name": C.safe_name(name), "rule": rule, "recording": short, "source_file": sf,
         "channels": [int(c) for c in channels],
         "recording_ids": [int(ctx.by_file[sf][c]["id"]) for c in channels],
         "start_idx": s, "end_idx": e, "fs": fs, "start_s": s / fs, "end_s": e / fs,
         "start_h": s / fs / 3600.0, "end_h": e / fs / 3600.0, "why": why}
    w.update(extra or {})
    return w


def _hour_name(s, e, fs):
    return f"{s / fs / 3600.0:.6g}-{e / fs / 3600.0:.6g}h"


def resolve_windows(ctx):
    """Every window the spec asks for, resolved against this database (a list of dicts)."""
    out = []
    spec = ctx.spec
    for w in spec.get("windows") or []:
        sf = ctx.kept.get(w["recording"])
        if sf is None:
            ctx.warn(f"window {w.get('name')}: recording {w['recording']} not present")
            continue
        fs = float(ctx.channels_of(sf)[0]["fs"])
        ch = w.get("channel")
        how = None
        if isinstance(ch, str) and ch != "all":
            idx, how = resolve_label(ctx, sf, ch, w.get("fallback_channel", 0))
            chans = [idx]
        else:
            chans = channels_from(ctx, sf, ch)
        s, e = int(round(_hours_or_seconds(w, "start") * fs)), int(round(_hours_or_seconds(w, "end") * fs))
        extra = {"channel_resolution": how, "decimate_hz": w.get("decimate_hz")}
        out.append(_window(ctx, name=w["name"], rule="explicit", short=w["recording"], sf=sf, channels=chans,
                           start=s, end=e, why=w.get("why"), extra=extra))
        fb = w.get("fallback_channel")
        if w.get("also_export_fallback") and fb is not None and chans != [int(fb)] and \
                int(fb) in ctx.by_file[sf]:
            out.append(_window(ctx, name=w["name"] + f"__fallback_index{int(fb)}", rule="explicit_fallback_check",
                               short=w["recording"], sf=sf, channels=[int(fb)], start=s, end=e,
                               why=f"the same hours on index {fb} (the prompt's fallback), to check the label "
                                   "resolution against", extra={"decimate_hz": w.get("decimate_hz")}))
    for r in spec.get("rules") or []:
        try:
            fn = RULES[r["rule"]]
        except KeyError:
            ctx.warn(f"unknown rule {r.get('rule')!r}")
            continue
        try:
            out.extend(fn(ctx, r))
        except C.StepTimeout:
            raise
        except Exception:  # noqa: BLE001 - one rule failing must not lose the others
            ctx.warn(f"rule {r['rule']} failed: see the log")
            ctx.log_exception(f"rule {r['rule']}")
    return out


def _recording_list(ctx, which):
    if which == "kept":
        return list(ctx.kept)
    if which == "round_b":
        return [s for s in ctx.spec.get("round_b") or [] if s in ctx.kept]
    if isinstance(which, list):
        return [s for s in which if s in ctx.kept]
    return [which] if which in ctx.kept else []


def rule_gallery(ctx, r):
    out = []
    for short in _recording_list(ctx, r.get("recordings", "kept")):
        ctx.tick()
        sf = ctx.kept[short]
        chans = ctx.channels_of(sf)
        fs = float(chans[0]["fs"])
        L = int(round(float(r.get("hours", 24)) * 3600 * fs))
        by_id = {int(c["id"]): c for c in chans}
        on, _rows = C.accepted_events(ctx, by_id)
        key, start, count = C.best_window(on, L, {k: by_id[k]["n_samples"] for k in on})
        if key is None:
            rec = chans[0]
            n = int(rec["n_samples"])
            start = int(round(float(r.get("fallback_start_h", 100)) * 3600 * fs))
            if start + L > n:
                start = max(0, n - L)
            why = f"no accepted event on {short}: first channel, from hour {start / fs / 3600:.4g}"
            ch, count = int(rec["channel"]), 0
        else:
            ch = int(by_id[key]["channel"])
            why = f"{count} accepted events in these {r.get('hours', 24)} h (the most on any channel)"
        e = start + L
        out.append(_window(ctx, name=f"gallery__{short}__CH{ch}__{_hour_name(start, min(e, chans[0]['n_samples']), fs)}",
                           rule="gallery", short=short, sf=sf, channels=[ch], start=start, end=e, why=why,
                           extra={"score": count}))
    return out


def drop_v1_runs(ctx, recording_ids, template="drop_detection_v1"):
    """scripts/thesis/b1_intervals.py channel_runs(): one channel's complete `template` run (completed, not
    superseded, not a surrogate), the longest then latest per channel."""
    conn = ctx.conn
    rows = []
    sup = "AND r.superseded_at IS NULL" if "superseded_at" in C.columns_of(conn, "runs") else ""
    for ch in C.chunks(sorted({int(x) for x in recording_ids})):
        marks = ",".join("?" * len(ch))
        rows += [tuple(r) for r in conn.execute(
            f"SELECT DISTINCT r.id, r.recording_id, r.span_start, r.span_end FROM runs r "
            f"JOIN discovery_runs dr ON dr.run_group_id = r.run_group_id "
            f"WHERE dr.template_name = ? AND r.surrogate_of_run_id IS NULL AND r.status = 'completed' {sup} "
            f"AND r.recording_id IN ({marks})", [template] + ch)]
    df = pd.DataFrame(rows, columns=["run_id", "recording_id", "span_start", "span_end"])
    if not len(df):
        return df
    df["len"] = df["span_end"] - df["span_start"]
    return df.sort_values(["recording_id", "len", "run_id"]).drop_duplicates("recording_id", keep="last")


def rule_b1_trains(ctx, r):
    out = []
    for short in _recording_list(ctx, r.get("recordings", "round_b")):
        ctx.tick()
        sf = ctx.kept[short]
        chans = ctx.channels_of(sf)
        fs = float(chans[0]["fs"])
        L = int(round(float(r.get("hours", 4)) * 3600 * fs))
        by_id = {int(c["id"]): c for c in chans}
        runs = drop_v1_runs(ctx, by_id, r.get("template", "drop_detection_v1"))
        if not len(runs):
            ctx.warn(f"b1_trains: no complete {r.get('template')} run on {short}: no window")
            continue
        on = {}
        for run in runs.itertuples():
            det = C.detections_of_run(ctx, run.run_id, run.span_start)
            on[int(run.recording_id)] = det["start"].to_numpy(np.int64)
        key, start, count = C.best_window(on, L, {k: by_id[k]["n_samples"] for k in on})
        if key is None:
            ctx.warn(f"b1_trains: {short}'s runs hold no detection")
            continue
        ch = int(by_id[key]["channel"])
        run_id = int(runs[runs["recording_id"] == key]["run_id"].iloc[0])
        out.append(_window(ctx, name=f"b1_trains__{short}__CH{ch}__{_hour_name(start, start + L, fs)}",
                           rule="b1_trains", short=short, sf=sf, channels=[ch], start=start, end=start + L,
                           why=f"{count} {r.get('template')} onsets (run {run_id}) in these {r.get('hours')} h",
                           extra={"score": count, "run_id": run_id}))
    return out


def b4_cooccurrences(ctx, r, sf):
    """The B4 census's co-occurrences on `sf`: the census named in b4_pairs.csv (else the newest finished one of
    drop_detection_v1), rows not binned 'artifact', on the pairs b4_pairs.csv lists. DataFrame or None."""
    conn = ctx.conn
    if not (C.has_table(conn, "cross_census") and C.has_table(conn, "cross_cooccurrence")):
        return None, "no cross_census tables in this database"
    pairs_path = ctx.path(r.get("pairs_csv", "docs/thesis/data/ch10_b4/b4_pairs.csv"))
    pairs, census_id, how = None, None, None
    if os.path.isfile(pairs_path):
        p = pd.read_csv(pairs_path)
        p = p[p["source_file"] == sf]
        if len(p):
            pairs = {(int(a), int(b)) for a, b in zip(p["a"], p["b"])}
            for h in p["census_hash"].dropna().unique():
                row = conn.execute("SELECT id FROM cross_census WHERE hash = ?", (str(h),)).fetchone()
                if row:
                    census_id, how = int(row[0]), f"census {str(h)[:12]}... named in b4_pairs.csv"
    if census_id is None:
        row = conn.execute("SELECT id, hash FROM cross_census WHERE source_file = ? AND status = 'done' "
                           "AND detector = 'drop_detection_v1' ORDER BY id DESC LIMIT 1", (sf,)).fetchone()
        if row is None:
            return None, f"no finished census for {sf}"
        census_id, how = int(row[0]), f"newest finished drop_detection_v1 census ({str(row[1])[:12]}...)"
    rows = pd.DataFrame([dict(x) for x in conn.execute(
        "SELECT id, det_a_id, det_b_id, rec_a_id, rec_b_id, onset_a_s, onset_b_s, lag_s, r, bin, common_mode "
        "FROM cross_cooccurrence WHERE census_id = ?", (census_id,))])
    if not len(rows):
        return None, f"census {census_id} has no co-occurrence rows"
    rows["counted"] = rows["bin"] != "artifact"
    if pairs:
        on_pair = np.array([(int(a), int(b)) in pairs or (int(b), int(a)) in pairs
                            for a, b in zip(rows["rec_a_id"], rows["rec_b_id"])], dtype=bool)
        rows["counted"] = rows["counted"].to_numpy(dtype=bool) & on_pair
    rows["census_id"] = census_id
    return rows, how


def rule_b4_stack(ctx, r):
    short = r.get("recording", "M2_aug")
    sf = ctx.kept.get(short)
    if sf is None:
        return []
    chans = ctx.channels_of(sf)
    fs = float(chans[0]["fs"])
    L = int(round(float(r.get("hours", 6)) * 3600 * fs))
    n = int(min(c["n_samples"] for c in chans))
    rows, how = b4_cooccurrences(ctx, r, sf)
    if rows is None or not rows["counted"].any():
        start = min(int(round(float(r.get("fallback_start_h", 100)) * 3600 * fs)), max(0, n - L))
        ctx.warn(f"b4_stack: {how if rows is None else 'no counted co-occurrence'}; fallback hours "
                 f"{start / fs / 3600:.4g}+")
        count, why = 0, "fallback: no B4 census co-occurrences"
    else:
        on = np.round(rows.loc[rows["counted"], "onset_a_s"].to_numpy(float) * fs).astype(np.int64)
        _k, start, count = C.best_window({"all": on}, L, {"all": n})
        why = f"{count} non-artifact co-occurrences of the B4 pairs in these {r.get('hours')} h ({how})"
        ctx.cache["b4_rows"] = rows
    return [_window(ctx, name=f"b4_stack__{short}__all__{_hour_name(start, start + L, fs)}", rule="b4_stack",
                    short=short, sf=sf, channels=[int(c["channel"]) for c in chans], start=start, end=start + L,
                    why=why, extra={"score": count})]


def judged_starts(ctx, recording_ids):
    """Starts of human-judged items (any verdict): live annotations not on a judged window, and own adjudications
    on real runs' detections. {recording_id: sorted int64 array}."""
    conn = ctx.conn
    ids = sorted({int(x) for x in recording_ids})
    own = C.own_adjudication_clause(conn)
    win = ",".join("?" * len(C.WINDOW_SOURCES))
    out = {}
    for ch in C.chunks(ids):
        marks = ",".join("?" * len(ch))
        for rid, s in conn.execute(f"SELECT recording_id, start_idx FROM annotations WHERE recording_id IN ({marks}) "
                                   f"AND deleted_at IS NULL AND source NOT IN ({win})", ch + list(C.WINDOW_SOURCES)):
            out.setdefault(int(rid), []).append(int(s))
        for rid, s, e, s0 in conn.execute(
                f"SELECT r.recording_id, d.start_idx, d.end_idx, r.span_start FROM adjudications a JOIN detections d "
                f"ON d.id = a.detection_id JOIN runs r ON r.id = d.run_id WHERE r.recording_id IN ({marks}) AND {own} "
                f"AND r.surrogate_of_run_id IS NULL", ch):
            out.setdefault(int(rid), []).append(C.absolute_bounds(s, e, s0)[0])
    return {k: np.asarray(sorted(set(v)), dtype=np.int64) for k, v in out.items()}


def rule_agreement_excerpt(ctx, r):
    short = r.get("recording", "M2_aug")
    sf = ctx.kept.get(short)
    if sf is None:
        return []
    tab = C.newest_table(ctx, sf)
    if tab is None:
        ctx.warn(f"agreement_excerpt: no candidate-event table for {sf}")
        return []
    chans = ctx.channels_of(sf)
    fs = float(chans[0]["fs"])
    L = int(round(float(r.get("hours", 12)) * 3600 * fs))
    k = int(r.get("min_agree", 9))
    ev = C.read_events(tab, ["recording_id", "start", "end", "n_agree"], filters=[("n_agree", ">=", k)])
    judged = judged_starts(ctx, [c["id"] for c in chans])
    by_id = {int(c["id"]): c for c in chans}
    best, best_any = None, None
    for rid, g in ev.groupby("recording_id"):
        if int(rid) not in by_id:
            continue
        n = int(by_id[int(rid)]["n_samples"])
        on = np.sort(g["start"].to_numpy(np.int64))
        starts = np.clip(on, 0, max(0, n - L))
        cnt = np.searchsorted(on, starts + L, side="left") - np.searchsorted(on, starts, side="left")
        j = judged.get(int(rid), np.zeros(0, np.int64))
        jc = np.searchsorted(j, starts + L, side="left") - np.searchsorted(j, starts, side="left")
        for i in range(len(starts)):
            cand = (int(cnt[i]), int(jc[i]), int(rid), int(starts[i]))
            if best_any is None or cand[0] > best_any[0]:
                best_any = cand
            if jc[i] >= int(r.get("min_judged", 3)) and (best is None or cand[0] > best[0]):
                best = cand
    pick = best
    if pick is None:
        if best_any is None:
            ctx.warn(f"agreement_excerpt: no candidate event at >= {k} families on {short}")
            return []
        ctx.warn(f"agreement_excerpt: no 12-h window holds >= {r.get('min_judged', 3)} judged items; taking the one "
                 "with the most high-agreement events")
        pick = best_any
    cnt, jc, rid, start = pick
    ch = int(by_id[rid]["channel"])
    return [_window(ctx, name=f"agreement__{short}__CH{ch}__{_hour_name(start, start + L, fs)}",
                    rule="agreement_excerpt", short=short, sf=sf, channels=[ch], start=start, end=start + L,
                    why=f"{cnt} candidate events at >= {k} agreeing families and {jc} human-judged items "
                        f"(table {tab['key']})", extra={"score": cnt, "judged": jc, "table_key": tab["key"]})]


def rule_cnn_scores(ctx, r):
    short = r.get("recording", "M2_aug")
    sf = ctx.kept.get(short)
    if sf is None:
        return []
    chans = ctx.channels_of(sf)
    fs = float(chans[0]["fs"])
    L = int(round(float(r.get("hours", 48)) * 3600 * fs))
    by_id = {int(c["id"]): c for c in chans}
    on, _ = C.accepted_events(ctx, by_id)
    key, start, count = C.best_window(on, L, {k: by_id[k]["n_samples"] for k in on})
    if key is None:
        key, start, count = int(chans[0]["id"]), 0, 0
        ctx.warn("cnn_scores: no accepted event on M2_aug: first channel, hours 0-48")
    ch = int(by_id[key]["channel"])
    return [_window(ctx, name=f"cnn_scores__{short}__CH{ch}__{_hour_name(start, start + L, fs)}", rule="cnn_scores",
                    short=short, sf=sf, channels=[ch], start=start, end=start + L,
                    why=f"{count} accepted events in these {r.get('hours')} h", extra={"score": count})]


RULES = {"gallery": rule_gallery, "b1_trains": rule_b1_trains, "b4_stack": rule_b4_stack,
         "agreement_excerpt": rule_agreement_excerpt, "cnn_scores": rule_cnn_scores}


def cnn_window_scores(ctx, w, out_dir):
    """The CNN window scores (P(interesting) per window) of every live, real CNN template run on the window's
    channel, read from the step cache: the run's recipe (configs.config_json), the prefix hash of its
    cnn_window_scores step (Working.execution._recipe_prefix_hash, with the recording's units), the
    `step_artifacts` row of that hash, and its scores.npz. Writes one CSV of runs of equal score (window start, end,
    p) per run. Returns a summary dict."""
    from Working.execution import _recipe_prefix_hash
    from Working.types.scores import Scores
    conn = ctx.conn
    rid = w["recording_ids"][0]
    rec = ctx.rec(rid)
    runs = C.runs_on(ctx, [rid], kinds=("template",))
    runs = runs[runs["variant"].map(lambda v: C.family_of(v).startswith("cnn_"))]
    found, missing, rows = [], [], []
    for run in runs.itertuples():
        ctx.tick()
        cfg = conn.execute("SELECT c.config_json FROM runs r JOIN configs c ON c.id = r.config_id WHERE r.id = ?",
                           (int(run.run_id),)).fetchone()
        try:
            recipe = json.loads(cfg[0])
        except (TypeError, ValueError):
            missing.append((run.run_id, run.variant, "config not JSON"))
            continue
        if recipe.get("windows"):
            missing.append((run.run_id, run.variant, "a windowed (stitched) run: scores live on its window runs"))
            continue
        steps = recipe.get("steps") or []
        hit = None
        for k, st in enumerate(steps):
            if "cnn" not in str(st.get("algorithm", "")):
                continue
            try:
                h = _recipe_prefix_hash(recipe, k, rec.get("units"))
            except Exception as e:  # noqa: BLE001
                missing.append((run.run_id, run.variant, f"prefix hash failed: {e}"))
                break
            row = conn.execute("SELECT path FROM step_artifacts WHERE recipe_prefix_hash = ? AND step_index = ?",
                               (h, k)).fetchone()
            if row is None:
                continue
            p = row[0] if os.path.isabs(row[0]) else os.path.join(ctx.root, row[0])
            if os.path.isfile(os.path.join(p, "scores.npz")):
                hit = (k, h, p)
                break
        if hit is None:
            if not any(m[0] == run.run_id for m in missing):
                missing.append((run.run_id, run.variant, "no cached scores.npz for its CNN step"))
            continue
        sc = Scores.from_path(hit[2])
        s0 = int(run.span_start)
        a, b = max(0, w["start_idx"] - s0), max(0, min(len(sc.values), w["end_idx"] - s0))
        v = np.asarray(sc.values[a:b], dtype=float)
        if not v.size:
            missing.append((run.run_id, run.variant, "the cached scores do not reach this window"))
            continue
        same = np.r_[False, (v[1:] == v[:-1]) | (np.isnan(v[1:]) & np.isnan(v[:-1]))]
        starts = np.flatnonzero(~same)
        ends = np.r_[starts[1:], v.size]
        for st, en in zip(starts, ends):
            rows.append({"run_id": int(run.run_id), "variant": run.variant, "family": C.family_of(run.variant),
                         "start_idx": s0 + a + int(st), "end_idx": s0 + a + int(en),
                         "start_s": (s0 + a + int(st)) / float(rec["fs"]), "end_s": (s0 + a + int(en)) / float(rec["fs"]),
                         "p_interesting": None if np.isnan(v[st]) else float(v[st]),
                         "cache_dir": os.path.relpath(hit[2], ctx.root).replace("\\", "/")})
        found.append((run.run_id, run.variant))
    if rows:
        C.write_csv(os.path.join(out_dir, f"{w['name']}__cnn_window_scores.csv"), pd.DataFrame(rows))
    if missing:
        C.write_csv(os.path.join(out_dir, f"{w['name']}__cnn_window_scores_MISSING.csv"),
                    pd.DataFrame(missing, columns=["run_id", "variant", "why"]))
    if not found:
        ctx.warn(f"cnn scores: none found in the step cache for the {len(runs)} CNN run(s) on this channel; "
                 "exported nothing for this part (see *_MISSING.csv)")
    return {"cnn_runs": int(len(runs)), "cnn_runs_with_scores": len(found), "cnn_score_rows": len(rows)}


def step_windows(ctx):
    d = ctx.step_dir()
    wins = resolve_windows(ctx)
    C.write_json(os.path.join(d, "resolved_windows.json"), wins)
    C.write_csv(os.path.join(d, "resolved_windows.csv"),
                pd.DataFrame([{k: (";".join(map(str, v)) if isinstance(v, list) else v) for k, v in w.items()}
                              for w in wins]))
    n_files, extra = 0, {}
    for w in wins:
        ctx.tick()
        sf = w["source_file"]
        chans = ctx.channels_of(sf)
        decim = 1
        if w.get("decimate_hz"):
            decim = max(1, int(round(w["fs"] / float(w["decimate_hz"]))))
        xs, metas = [], []
        for ch in w["channels"]:
            rec = ctx.by_file[sf][ch]
            x, s, e = C.read_segment(ctx, rec, w["start_idx"], w["end_idx"], decim)
            xs.append(x)
            metas.append(C.rec_meta(rec, n_channels=len(chans)))
        L = max(len(x) for x in xs)
        X = xs[0] if len(xs) == 1 else np.vstack([np.pad(x, (0, L - len(x)), constant_values=np.nan) for x in xs])
        meta = {"what": f"window ({w['rule']}): {w.get('why')}", "window": w, "source_file": sf,
                "recording_id": metas[0]["recording_id"] if len(metas) == 1 else [m["recording_id"] for m in metas],
                "channel": metas[0]["channel"] if len(metas) == 1 else [m["channel"] for m in metas],
                "channels": metas, "fs": w["fs"], "t0_s": w["start_s"], "start_idx": w["start_idx"],
                "end_idx": w["end_idx"], "decimation": decim, "dt_s": decim / w["fs"],
                "units_original": metas[0]["units_original"] if len(metas) == 1 else
                [m["units_original"] for m in metas], "converted_to": "mV"}
        n_files += len(C.save_series(ctx, os.path.join(d, w["name"]), X, meta))
        ctx.log(f"window {w['name']}: {len(w['channels'])} channel(s) x {L:,} samples")
        if w["rule"] == "b4_stack" and "b4_rows" in ctx.cache:
            rows = ctx.cache["b4_rows"]
            inw = rows[(rows["onset_a_s"] * w["fs"] < w["end_idx"]) & (rows["onset_a_s"] * w["fs"] >= w["start_idx"])]
            C.write_csv(os.path.join(d, f"{w['name']}__b4_cooccurrences.csv"), inw)
        if w["rule"] == "cnn_scores":
            try:
                extra.update(cnn_window_scores(ctx, w, d))
            except C.StepTimeout:
                raise
            except Exception:  # noqa: BLE001
                ctx.warn("cnn window scores failed: see the log; exported nothing for this part")
                ctx.log_exception("cnn_window_scores")
    return dict({"windows": len(wins), "npz_files": n_files,
                 "by_rule": {k: sum(1 for w in wins if w["rule"] == k) for k in sorted({w["rule"] for w in wins})}},
                **extra)


def load_resolved_windows(ctx):
    p = os.path.join(ctx.data_dir, "windows", "resolved_windows.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    ctx.log("no resolved_windows.json (the windows step did not run): resolving the spec now")
    return resolve_windows(ctx)


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 5. detections, candidate events and verdicts in every window
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def run_maxlen(ctx, run_ids):
    cache = ctx.cache.setdefault("run_maxlen", {})
    todo = [int(r) for r in run_ids if int(r) not in cache]
    for ch in C.chunks(todo):
        marks = ",".join("?" * len(ch))
        for rid, m in ctx.conn.execute(f"SELECT run_id, MAX(end_idx - start_idx) FROM detections WHERE run_id IN "
                                       f"({marks}) GROUP BY run_id", ch):
            cache[int(rid)] = int(m or 0)
        for r in ch:
            cache.setdefault(int(r), 0)
    return cache


def annotation_queue_map(ctx):
    if "ann_queue" in ctx.cache:
        return ctx.cache["ann_queue"]
    out = {}
    if C.has_table(ctx.conn, "blind_test_labels"):
        for q, a in ctx.conn.execute("SELECT queue_id, annotation_id FROM blind_test_labels"):
            out.setdefault(int(a), []).append(int(q))
    out = {k: ";".join(map(str, sorted(set(v)))) for k, v in out.items()}
    ctx.cache["ann_queue"] = out
    return out


def verdicts_in(ctx, recording_ids, ws, we):
    """Every human verdict overlapping [ws, we) on these recordings: live annotations and adjudications on real
    runs' detections (own and carried, flagged), with the queues that hold them."""
    conn = ctx.conn
    rows = []
    dq = C.detection_queue_map(ctx)
    aq = annotation_queue_map(ctx)
    cf = "a.carried_from" if "carried_from" in C.columns_of(conn, "adjudications") else "NULL"
    for rid in recording_ids:
        for r in conn.execute("SELECT id, start_idx, end_idx, verdict, source, created_at, tag FROM annotations "
                              "WHERE recording_id = ? AND deleted_at IS NULL AND start_idx < ? AND end_idx > ?",
                              (int(rid), int(we), int(ws))):
            rows.append({"recording_id": int(rid), "store": "annotations", "row_id": int(r[0]), "detection_id": None,
                         "start_idx": int(r[1]), "end_idx": int(r[2]), "verdict": r[3], "source": r[4],
                         "created_at": r[5], "tag": r[6], "carried_from": None, "queue": aq.get(int(r[0]))})
        for r in conn.execute(f"SELECT a.id, a.detection_id, d.start_idx, d.end_idx, r.span_start, a.verdict, "
                              f"a.created_at, {cf} FROM adjudications a JOIN detections d ON d.id = a.detection_id "
                              f"JOIN runs r ON r.id = d.run_id WHERE r.recording_id = ? "
                              f"AND r.surrogate_of_run_id IS NULL", (int(rid),)):
            s, e = C.absolute_bounds(r[2], r[3], r[4])
            if s < we and e > ws:
                rows.append({"recording_id": int(rid), "store": "adjudications", "row_id": int(r[0]),
                             "detection_id": int(r[1]), "start_idx": s, "end_idx": e, "verdict": r[5],
                             "source": "review", "created_at": r[6], "tag": None,
                             "carried_from": None if r[7] is None else int(r[7]), "queue": dq.get(int(r[1]))})
    return pd.DataFrame(rows, columns=["recording_id", "store", "row_id", "detection_id", "start_idx", "end_idx",
                                       "verdict", "source", "created_at", "tag", "carried_from", "queue"])


def step_detections_in_windows(ctx):
    d = ctx.step_dir()
    wins = load_resolved_windows(ctx)
    summary = []
    for w in wins:
        ctx.tick()
        rids = w["recording_ids"]
        fs = float(w["fs"])
        ws, we = int(w["start_idx"]), int(w["end_idx"])
        ch_of = {int(r): int(ctx.rec(r)["channel"]) for r in rids}
        runs = C.runs_on(ctx, rids, kinds=("template", "seed"), include_surrogates=True)
        chosen = C.rule1_choice(runs[runs["kind"] == "template"])
        maxlen = run_maxlen(ctx, runs["run_id"].tolist())
        parts = []
        for run in runs.itertuples():
            det = C.detections_of_run(ctx, run.run_id, run.span_start, ws, we, maxlen.get(int(run.run_id), 0))
            if not len(det):
                continue
            det.insert(0, "run_id", int(run.run_id))
            det["recording_id"] = int(run.recording_id)
            det["channel"] = ch_of[int(run.recording_id)]
            det["run_kind"] = run.kind
            det["variant"] = run.variant
            det["family"] = "seed_search" if run.kind == "seed" else C.family_of(run.variant)
            sur = run.surrogate_of is not None and not pd.isna(run.surrogate_of)
            det["is_surrogate"] = bool(sur)
            det["surrogate_of"] = float(run.surrogate_of) if sur else np.nan
            det["rule1_chosen"] = int(run.run_id) in chosen
            parts.append(det)
        det = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
            columns=["run_id", "detection_id", "start", "end", "score", "recording_id", "channel", "run_kind",
                     "variant", "family", "is_surrogate", "surrogate_of", "rule1_chosen"])
        det = det.rename(columns={"start": "start_idx", "end": "end_idx"})
        det["start_s"] = det["start_idx"] / fs
        det["end_s"] = det["end_idx"] / fs
        # seconds only (sample = seconds x fs, exact at 1, 2 and 10 Hz): this is the biggest table of the bundle
        C.write_csv(os.path.join(d, f"{w['name']}__detections.csv"),
                    det[["recording_id", "channel", "run_id", "run_kind", "variant", "family", "is_surrogate",
                         "surrogate_of", "rule1_chosen", "detection_id", "start_s", "end_s", "score"]])
        # candidate events
        n_cand = 0
        tab = C.newest_table(ctx, w["source_file"])
        if tab is not None:
            cand = C.read_events(tab, ["event_id", "recording_id", "channel", "start", "end", "n_agree",
                                       "n_matched_families", "matched_families", "agree_families", "anchor_variant",
                                       "anchor_detection_id", "label", "label_kind", "label_basis",
                                       "inside_interesting"],
                                 filters=[("recording_id", "in", [int(r) for r in rids]), ("start", "<", we),
                                          ("end", ">", ws)])
            cand.insert(0, "table_key", tab["key"])
            cand.insert(0, "window", w["name"])
            cand["start_s"] = cand["start"] / fs
            cand["end_s"] = cand["end"] / fs
            C.write_csv(os.path.join(d, f"{w['name']}__candidates.csv"), cand)
            n_cand = len(cand)
        ver = verdicts_in(ctx, rids, ws, we)
        if len(ver):
            ver.insert(0, "window", w["name"])
            ver["channel"] = ver["recording_id"].map(ch_of)
            ver["start_s"] = ver["start_idx"] / fs
            ver["end_s"] = ver["end_idx"] / fs
        C.write_csv(os.path.join(d, f"{w['name']}__verdicts.csv"), ver)
        summary.append({"window": w["name"], "runs": int(len(runs)), "detections": int(len(det)),
                        "real": int((~det["is_surrogate"].astype(bool)).sum()) if len(det) else 0,
                        "candidates": n_cand, "verdicts": int(len(ver)),
                        "table_key": tab["key"] if tab is not None else None})
        ctx.log(f"{w['name']}: {len(det):,} detections from {len(runs)} runs, {n_cand} candidates, "
                f"{len(ver)} verdicts")
    C.write_csv(os.path.join(d, "summary.csv"), pd.DataFrame(summary))
    return {"windows": len(wins), "detections": int(sum(s["detections"] for s in summary)),
            "candidates": int(sum(s["candidates"] for s in summary)),
            "verdicts": int(sum(s["verdicts"] for s in summary))}


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 6. drop_detection_v1, every channel of the round-B recordings
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def step_drop_v1_all(ctx):
    d = ctx.step_dir()
    parts, runs_out = [], []
    for short in _recording_list(ctx, "round_b"):
        sf = ctx.kept[short]
        chans = ctx.channels_of(sf)
        by_id = {int(c["id"]): c for c in chans}
        runs = drop_v1_runs(ctx, by_id)
        for run in runs.itertuples():
            ctx.tick()
            rec = by_id[int(run.recording_id)]
            det = C.detections_of_run(ctx, run.run_id, run.span_start)
            fs = float(rec["fs"])
            det = det.rename(columns={"start": "start_idx", "end": "end_idx"})
            det.insert(0, "run_id", int(run.run_id))
            det.insert(0, "channel", int(rec["channel"]))
            det.insert(0, "recording_id", int(rec["id"]))
            det.insert(0, "source_file", sf)
            det.insert(0, "recording", short)
            det["fs"] = fs
            det["start_s"] = det["start_idx"] / fs
            det["end_s"] = det["end_idx"] / fs
            parts.append(det)
            runs_out.append({"recording": short, "source_file": sf, "recording_id": int(rec["id"]),
                             "channel": int(rec["channel"]), "run_id": int(run.run_id),
                             "span_start": int(run.span_start), "span_end": int(run.span_end),
                             "hours": (run.span_end - run.span_start) / fs / 3600.0, "n_detections": int(len(det))})
        missing = sorted(set(by_id) - set(runs["recording_id"].astype(int))) if len(runs) else sorted(by_id)
        if missing:
            ctx.warn(f"drop_v1_all: {short}: no complete drop_detection_v1 run on recording id(s) {missing}")
    det = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    C.write_csv(os.path.join(d, "drop_v1_detections.csv"), det)
    C.write_csv(os.path.join(d, "drop_v1_runs.csv"), pd.DataFrame(runs_out))
    return {"runs": len(runs_out), "detections": int(len(det))}


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 7. queues 25, 28, 35, 36
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def via_queue_targets(ctx, qid):
    """scripts/m4_exam_score.py exam_verdicts(): the detections a not-undone 'verdict' row of review_audit names
    for this queue."""
    out = set()
    if not C.has_table(ctx.conn, "review_audit"):
        return out
    for (payload,) in ctx.conn.execute("SELECT payload_json FROM review_audit WHERE queue_id = ? AND action = 'verdict' "
                                       "AND undone_at IS NULL", (int(qid),)):
        try:
            targets = json.loads(payload or "{}").get("targets") or []
        except (ValueError, AttributeError):
            continue
        for t in targets:
            if not isinstance(t, dict):
                continue
            for k in ("row_id", "target_id"):
                if t.get(k) is not None:
                    try:
                        out.add(int(t[k]))
                    except (TypeError, ValueError):
                        pass
    return out


def queue_detections(ctx, ids):
    rows = {}
    cols = C.columns_of(ctx.conn, "runs")
    sur = "r.surrogate_of_run_id" if "surrogate_of_run_id" in cols else "NULL"
    for ch in C.chunks(ids):
        marks = ",".join("?" * len(ch))
        for r in ctx.conn.execute(f"SELECT d.id, d.start_idx, d.end_idx, d.score, r.id, r.span_start, r.recording_id, "
                                  f"{sur}, r.run_group_id FROM detections d JOIN runs r ON r.id = d.run_id "
                                  f"WHERE d.id IN ({marks})", ch):
            s, e = C.absolute_bounds(r[1], r[2], r[5])
            rows[int(r[0])] = {"detection_id": int(r[0]), "start": s, "end": e, "score": r[3], "run_id": int(r[4]),
                               "recording_id": int(r[6]), "surrogate_run": r[7] is not None,
                               "run_group_id": r[8]}
    return rows


def queue_verdicts(ctx, ids):
    """{detection_id: {...}}: the verdict on each detection (adjudications holds at most one per detection). A row
    with `carried_from` set is a copy Review carried from another detection's verdict, not a look: it is reported
    as `verdict_carried`, never as the detection's own verdict (catalogue_stats.py, promote_blind_accepted.py)."""
    conn = ctx.conn
    acols = C.columns_of(conn, "adjudications")
    cf = "carried_from" if "carried_from" in acols else "NULL"
    cl = "class_label" if "class_label" in acols else "NULL"
    out = {}
    for ch in C.chunks(ids):
        marks = ",".join("?" * len(ch))
        for aid, did, v, c, at, lab in conn.execute(
                f"SELECT id, detection_id, verdict, {cf}, created_at, {cl} FROM adjudications WHERE detection_id IN "
                f"({marks}) ORDER BY id", ch):
            own = c is None
            out[int(did)] = {"verdict_own": v if own else None, "verdict_own_at": at if own else None,
                             "adjudication_id": int(aid), "class_label": lab,
                             "verdict_carried": None if own else v, "carried_from": None if own else int(c)}
    return out


def rq2_key(ctx, qid):
    """The RQ2 blind panel's key (DATA/derived/rq2_blind/<stamp>/key.json) for queue `qid`, or None."""
    for p in sorted(glob.glob(os.path.join(ctx.root, "DATA", "derived", "rq2_blind", "*", "key.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                k = json.load(fh)
        except (OSError, ValueError):
            continue
        if int(k.get("queue_id", -1)) == int(qid):
            return k, p
    return None, None


def seed_span(ctx, discovery_run_id):
    """A seed search's own seed: discovery_runs.params_json seedId ('<kind>:<recording>:<start>:<end>') or its
    entryId (motif_entry's span). Returns a dict."""
    row = ctx.conn.execute("SELECT id, label, kind, params_json FROM discovery_runs WHERE id = ?",
                           (int(discovery_run_id),)).fetchone()
    if row is None:
        return {"discovery_run": int(discovery_run_id), "why": "no such discovery run"}
    try:
        p = json.loads(row["params_json"] or "{}")
    except ValueError:
        p = {}
    out = {"discovery_run": int(row["id"]), "label": row["label"], "kind": row["kind"], "seedId": p.get("seedId"),
           "entryId": p.get("entryId"), "recording_id": None, "start_idx": None, "end_idx": None, "how": None}
    m = re.match(r"^[A-Za-z_]+:(\d+):(\d+):(\d+)$", str(p.get("seedId") or ""))
    if m:
        out.update(recording_id=int(m.group(1)), start_idx=int(m.group(2)), end_idx=int(m.group(3)), how="seedId")
    entry = p.get("entryId")
    if out["recording_id"] is None and not entry:
        m2 = re.match(r"^library:(\d+)$", str(p.get("seedId") or ""))
        entry = int(m2.group(1)) if m2 else None
    if out["recording_id"] is None and entry:
        e = ctx.conn.execute("SELECT recording_id, start_idx, end_idx FROM motif_entry WHERE id = ?",
                             (int(entry),)).fetchone()
        if e is not None:
            out.update(recording_id=int(e[0]), start_idx=int(e[1]), end_idx=int(e[2]), how=f"motif_entry {entry}")
    if out["recording_id"] is not None and out["recording_id"] in ctx.recordings:
        rec = ctx.recordings[out["recording_id"]]
        out.update(source_file=rec["source_file"], channel=int(rec["channel"]), fs=float(rec["fs"]))
    return out


def step_queues(ctx):
    d = ctx.step_dir()
    qf = C.queue_filters(ctx)
    all_rows, summary = [], {}
    for qid in ctx.spec.get("queues") or []:
        ctx.tick()
        if int(qid) not in qf:
            ctx.warn(f"queue {qid} is not in this database")
            continue
        row, f = qf[int(qid)]
        ids = [int(x) for x in (f.get("detection_ids") or [])]
        if not ids:
            ctx.warn(f"queue {qid} ({row.get('source_kind')}) lists no detection ids: its items are resolved live, "
                     "not exported here")
            continue
        dets = queue_detections(ctx, ids)
        ver = queue_verdicts(ctx, ids)
        via = via_queue_targets(ctx, qid)
        sample = None
        for sd in C.samples_with_queue(ctx).get(int(qid), []):
            s = pd.read_parquet(os.path.join(sd, "sample.parquet"))
            s["sample_dir"] = os.path.relpath(sd, ctx.root).replace("\\", "/")
            sample = s if sample is None else pd.concat([sample, s], ignore_index=True)
        smap = {int(r.detection_id): r for r in sample.itertuples()} if sample is not None else {}
        key, key_path = rq2_key(ctx, qid) if int(qid) == 35 or not smap else (None, None)
        kmap = {int(it["panel_detection_id"]): it for it in (key or {}).get("items", []) if "panel_detection_id" in it}
        rows, refused = [], 0
        for pos, did in enumerate(ids):
            dd = dets.get(did)
            if dd is None:
                rows.append({"queue": qid, "position": pos, "detection_id": did, "missing": True})
                continue
            rec = ctx.recordings.get(dd["recording_id"])
            if rec is None or C.is_refused(rec["source_file"]):
                refused += 1
                continue
            v = ver.get(did, {})
            r = {"queue": int(qid), "queue_name": row.get("name"), "position": pos, "detection_id": did,
                 "run_id": dd["run_id"], "recording_id": dd["recording_id"], "source_file": rec["source_file"],
                 "channel": int(rec["channel"]), "fs": float(rec["fs"]), "start": dd["start"], "end": dd["end"],
                 "start_s": dd["start"] / float(rec["fs"]), "end_s": dd["end"] / float(rec["fs"]),
                 "span_s": (dd["end"] - dd["start"]) / float(rec["fs"]), "score": dd["score"],
                 "verdict_own": v.get("verdict_own"), "verdict_own_at": v.get("verdict_own_at"),
                 "class_label": v.get("class_label"), "verdict_carried": v.get("verdict_carried"),
                 "carried_from": v.get("carried_from"),
                 "own_verdict_via_this_queue": did in via and v.get("verdict_own") is not None,
                 "missing": False}
            sm = smap.get(did)
            if sm is not None:
                r.update({"kind": "candidate_event_sample", "stratum": sm.stratum, "event_id": int(sm.event_id),
                          "frame_size": getattr(sm, "frame_size", None), "weight": getattr(sm, "weight", None),
                          "serve_rank": getattr(sm, "serve_rank", None), "sample_dir": sm.sample_dir})
            ki = kmap.get(did)
            if ki is not None:
                r.update({"kind": "rq2_panel", "stratum": ki.get("group"), "seed": ki.get("seed"),
                          "control_length": ki.get("control_length"), "item_length": ki.get("length"),
                          "source_json": json.dumps(ki.get("source"), sort_keys=True),
                          "earlier_json": json.dumps(ki.get("earlier"), sort_keys=True),
                          "serve_rank": ki.get("serve_rank")})
            rows.append(r)
        if refused:
            ctx.warn(f"queue {qid}: {refused} item(s) on a refused recording left out")
        if not smap and not kmap:
            ctx.warn(f"queue {qid}: no sample folder or RQ2 key names it: items have no stratum")
        all_rows += rows
        summary[str(qid)] = {"items": len(rows), "with_own_verdict": sum(1 for r in rows if r.get("verdict_own")),
                             "stratum_from": "sample" if smap else ("rq2 key" if kmap else None),
                             "key": os.path.relpath(key_path, ctx.root).replace("\\", "/") if key_path else None}
        items = [r for r in rows if not r.get("missing")]
        segs, idx, skipped = C.window_rows(ctx, [{"recording_id": r["recording_id"], "start": r["start"],
                                                  "end": r["end"], "queue": r["queue"],
                                                  "detection_id": r["detection_id"], "stratum": r.get("stratum"),
                                                  "verdict_own": r.get("verdict_own")} for r in items])
        C.save_stack(ctx, os.path.join(d, f"queue{qid}_windows"), segs, idx,
                     {"what": f"queue {qid}: every item's span +- one span length (at most 4,000 points; block-mean "
                              "decimated by an integer factor when longer)", "queue": int(qid)})
        summary[str(qid)]["windows"] = len(segs)
        if int(qid) == 35:
            runs = set(int(v) for v in (ctx.spec.get("rq2_seed_discovery_runs") or {}).values())
            for it in (key or {}).get("items", []):
                dr = (it.get("source") or {}).get("discovery_run")
                if dr is not None:
                    runs.add(int(dr))
            names = {int(v): k for k, v in (ctx.spec.get("rq2_seed_discovery_runs") or {}).items()}
            seeds = []
            for dr in sorted(runs):
                s = seed_span(ctx, dr)
                s["seed_key"] = names.get(dr)
                seeds.append(s)
            C.write_csv(os.path.join(d, "queue35_seeds.csv"), pd.DataFrame(seeds))
            ok = [s for s in seeds if s.get("recording_id") is not None and s["recording_id"] in ctx.recordings
                  and not C.is_refused(ctx.recordings[s["recording_id"]]["source_file"])]
            segs, idx, _ = C.window_rows(ctx, [{"recording_id": s["recording_id"], "start": s["start_idx"],
                                                "end": s["end_idx"], "seed_key": s.get("seed_key"),
                                                "discovery_run": s["discovery_run"]} for s in ok])
            C.save_stack(ctx, os.path.join(d, "queue35_seed_windows"), segs, idx,
                         {"what": "queue 35's seeds: each seed's own span +- one span length"})
            summary["35"]["seeds"] = len(seeds)
            summary["35"]["seeds_with_span"] = len(ok)
    C.write_csv(os.path.join(d, "queue_items.csv"), pd.DataFrame(all_rows))
    return summary


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 8. Library events (g-11) and rec 385's members (g-05)
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def step_library_events(ctx):
    d = ctx.step_dir()
    conn = ctx.conn
    ev_path = ctx.path(ctx.spec.get("library_events_csv"))
    out = {}
    if not os.path.isfile(ev_path):
        ctx.warn(f"no {ev_path}: g-11 events not exported")
    else:
        ev = pd.read_csv(ev_path)
        gid = 11
        gpath = ctx.path(ctx.spec.get("library_grouping_json"))
        if os.path.isfile(gpath):
            with open(gpath, encoding="utf-8") as fh:
                gid = int(json.load(fh).get("grouping_id") or 11)
            shutil.copy2(gpath, os.path.join(d, "events_grouping.json"))
        fam = pd.DataFrame([dict(r) for r in conn.execute(
            "SELECT member_ref, family_id, family_label, distance, is_medoid, omit_reason FROM grouping_assignments "
            "WHERE grouping_id = ? AND unit = 'single_motifs'", (gid,))])
        if len(fam):
            fam = fam.rename(columns={c: f"g{gid:02d}_{c}" for c in fam.columns if c != "member_ref"})
            ev = ev.merge(fam, left_on="representative_member", right_on="member_ref", how="left").drop(
                columns=["member_ref"])
        else:
            ctx.warn(f"grouping {gid} has no single_motifs assignments in this database")
        ev = ev[~ev["recording"].map(C.is_refused)]
        C.write_csv(os.path.join(d, "events_with_family.csv"), ev)
        items, bad = [], 0
        for r in ev.itertuples():
            rid = int(r.recording_id)
            rec = ctx.recordings.get(rid)
            if rec is None or rec["source_file"] != r.recording or int(rec["channel"]) != int(r.channel):
                hit = ctx.by_file.get(r.recording, {}).get(int(r.channel))
                if hit is None:
                    bad += 1
                    continue
                rid = int(hit["id"])
            items.append({"recording_id": rid, "start": int(r.start_idx), "end": int(r.end_idx),
                          "event_id": r.event_id,
                          "family": getattr(r, f"g{gid:02d}_family_label", None)})
        if bad:
            ctx.warn(f"{bad} g-11 event(s) name a recording not in this database")
        segs, idx, skipped = C.window_rows(ctx, items)
        C.save_stack(ctx, os.path.join(d, "library_event_windows"), segs, idx,
                     {"what": "every g-11 event: span +- one span length (at most 4,000 points)",
                      "grouping_id": gid})
        out.update(events=int(len(ev)), windows=len(segs), grouping_id=gid,
                   with_family=int(ev[f"g{gid:02d}_family_label"].notna().sum())
                   if f"g{gid:02d}_family_label" in ev else 0)
    cfg = ctx.spec.get("library_rec385") or {}
    rid, g5 = int(cfg.get("recording_id", 385)), int(cfg.get("grouping_id", 5))
    rows = [dict(r) for r in conn.execute(
        """SELECT m.id AS member_id, m.entry_id, m.recording_id, m.start_idx, m.end_idx,
                  rv.start_idx AS current_start_idx, rv.end_idx AS current_end_idx, rv.revision AS current_revision,
                  e.source_kind, e.source_store, e.label AS entry_label, e.scale AS entry_scale,
                  ga.family_id AS g05_family_id, ga.family_label AS g05_family_label, ga.distance AS g05_distance,
                  ga.is_medoid AS g05_is_medoid, ga.omit_reason AS g05_omit_reason
             FROM motif_member m JOIN motif_entry e ON e.id = m.entry_id
             LEFT JOIN motif_member_revision rv ON rv.id = m.current_revision_id
             LEFT JOIN grouping_assignments ga ON ga.member_ref = m.id AND ga.grouping_id = ?
                                              AND ga.unit = 'single_motifs'
            WHERE m.recording_id = ? ORDER BY m.start_idx, m.id""", (g5, rid))]
    df = pd.DataFrame(rows)
    if rid in ctx.recordings and len(df):
        fs = float(ctx.recordings[rid]["fs"])
        df["source_file"] = ctx.recordings[rid]["source_file"]
        df["start_s"], df["end_s"] = df["start_idx"] / fs, df["end_idx"] / fs
    C.write_csv(os.path.join(d, f"rec{rid}_members_g{g5:02d}.csv"), df)
    out.update(rec385_members=int(len(df)))
    return out


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 9. the imported 10-minute hand labels
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def step_hand_labels(ctx):
    d = ctx.step_dir()
    cfg = ctx.spec.get("hand_labels") or {}
    src = cfg.get("source", "imported_10min")
    rows = [dict(r) for r in ctx.conn.execute(
        "SELECT a.id AS annotation_id, a.recording_id, rec.source_file, rec.channel, rec.fs, a.start_idx, a.end_idx, "
        "a.verdict AS label, a.tag, a.note, a.created_at, a.deleted_at FROM annotations a JOIN recordings rec "
        "ON rec.id = a.recording_id WHERE a.source = ? ORDER BY a.recording_id, a.start_idx", (src,))]
    df = pd.DataFrame(rows)
    if not len(df):
        ctx.warn(f"no annotations with source {src!r}")
        C.write_csv(os.path.join(d, "hand_labels.csv"), df)
        return {"labels": 0}
    df = df[~df["source_file"].map(C.is_refused)]
    n_deleted = int(df["deleted_at"].notna().sum())
    df = df[df["deleted_at"].isna()].drop(columns=["deleted_at"])
    df["start_s"], df["end_s"] = df["start_idx"] / df["fs"], df["end_idx"] / df["fs"]
    C.write_csv(os.path.join(d, "hand_labels.csv"), df)
    rng = np.random.default_rng(int(cfg.get("seed", 0)))
    pick = []
    for cls in cfg.get("classes") or ["interesting", "not_interesting", "artifact"]:
        g = df[df["label"] == cls].sort_values("annotation_id")
        k = min(int(cfg.get("per_class", 10)), len(g))
        if k:
            pick.append(g.iloc[np.sort(rng.choice(len(g), size=k, replace=False))])
    pick = pd.concat(pick) if pick else df.iloc[0:0]
    items = [{"recording_id": int(r.recording_id), "start": int(r.start_idx), "end": int(r.end_idx),
              "annotation_id": int(r.annotation_id), "label": r.label} for r in pick.itertuples()]
    segs, idx, _ = C.window_rows(ctx, items, context=int(cfg.get("context_samples", 1800)))
    C.save_stack(ctx, os.path.join(d, "hand_label_windows"), segs, idx,
                 {"what": f"{cfg.get('per_class', 10)} random labels per class (seed {cfg.get('seed', 0)}): the "
                          f"labelled span +- {cfg.get('context_samples', 1800)} samples, native rate"})
    return {"labels": int(len(df)), "deleted_left_out": n_deleted,
            "by_label": {str(k): int(v) for k, v in df["label"].value_counts().items()}, "windows": len(segs)}


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 10. misses: human-accepted events no sweep family touches
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def step_misses(ctx):
    d = ctx.step_dir()
    conn = ctx.conn
    out_rows = []
    for short, sf in ctx.kept.items():
        chans = ctx.channels_of(sf)
        by_id = {int(c["id"]): c for c in chans}
        marks = ",".join("?" * len(by_id))
        ann = pd.DataFrame([dict(r) for r in conn.execute(
            f"SELECT id AS annotation_id, recording_id, start_idx, end_idx, verdict, source, created_at FROM annotations "
            f"WHERE recording_id IN ({marks}) AND deleted_at IS NULL AND verdict IN ('interesting', 'seed')",
            list(by_id))])
        if not len(ann):
            continue
        runs = C.runs_on(ctx, list(by_id), kinds=("template",))
        chosen = C.rule1_choice(runs)
        runs = runs[runs["run_id"].isin(chosen)]
        fams = {}
        for rid, g in ann.groupby("recording_id"):
            ctx.tick()
            ws, we = g["start_idx"].to_numpy(np.int64), g["end_idx"].to_numpy(np.int64)
            hit = {}
            for run in runs[runs["recording_id"] == rid].itertuples():
                det = C.detections_of_run(ctx, run.run_id, run.span_start)
                t = C.touched(ws, we, det["start"].to_numpy(np.int64), det["end"].to_numpy(np.int64))
                fam = C.family_of(run.variant)
                neg = run.variant.startswith("cnn_") and run.variant.endswith(C.NEGATIVE_CONTROL_SUFFIX)
                key = fam + (" (1-min CNN, negative control)" if neg else "")
                hit[key] = hit.get(key, np.zeros(len(g), bool)) | t
            for i, idx in enumerate(g.index):
                fams[idx] = sorted(k for k, v in hit.items() if v[i])
        ann["families_touching"] = [";".join(fams.get(i, [])) for i in ann.index]
        neg = " (1-min CNN, negative control)"
        ann["n_families_touching"] = [sum(1 for f in fams.get(i, []) if not f.endswith(neg)) for i in ann.index]
        ann["touched_no_cnn"] = [any(not f.startswith("cnn_") for f in fams.get(i, [])) for i in ann.index]
        ann["touched_incl_1min_cnn"] = [bool(fams.get(i)) for i in ann.index]
        ann["miss"] = ann["n_families_touching"] == 0
        ann["recording"] = short
        ann["source_file"] = sf
        ann["channel"] = ann["recording_id"].map(lambda r: int(by_id[int(r)]["channel"]))
        ann["fs"] = ann["recording_id"].map(lambda r: float(by_id[int(r)]["fs"]))
        ann["start_s"], ann["end_s"] = ann["start_idx"] / ann["fs"], ann["end_idx"] / ann["fs"]
        ann["n_sweep_runs_on_channel"] = ann["recording_id"].map(runs.groupby("recording_id").size()).fillna(0)
        out_rows.append(ann)
        ctx.log(f"misses {short}: {int(ann['miss'].sum())} of {len(ann)} accepted annotations touched by no family")
    df = pd.concat(out_rows, ignore_index=True) if out_rows else pd.DataFrame()
    C.write_csv(os.path.join(d, "misses.csv"), df)
    if not len(df):
        return {"accepted": 0, "misses": 0}
    cfg = ctx.spec.get("misses") or {}
    rng = np.random.default_rng(int(cfg.get("seed", 0)))
    miss = df[df["miss"] & (df["n_sweep_runs_on_channel"] > 0)].sort_values("annotation_id")
    ev = miss[~miss["source"].isin(C.WINDOW_SOURCES)]
    pool = ev if len(ev) >= int(cfg.get("n_windows", 12)) else miss
    k = min(int(cfg.get("n_windows", 12)), len(pool))
    pick = pool.iloc[np.sort(rng.choice(len(pool), size=k, replace=False))] if k else pool
    items = [{"recording_id": int(r.recording_id), "start": int(r.start_idx), "end": int(r.end_idx),
              "annotation_id": int(r.annotation_id), "source": r.source} for r in pick.itertuples()]
    segs, idx, _ = C.window_rows(ctx, items)
    C.save_stack(ctx, os.path.join(d, "miss_windows"), segs, idx,
                 {"what": f"{k} random misses (seed {cfg.get('seed', 0)}; event-level sources first): span +- one "
                          "span length (at most 4,000 points)"})
    return {"accepted": int(len(df)), "misses": int(df["miss"].sum()),
            "misses_on_swept_channels": int(len(miss)), "misses_no_cnn": int((~df["touched_no_cnn"]).sum()),
            "windows": len(segs)}


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 11. the final drop-motif store
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

def step_drop_motifs_store(ctx):
    d = ctx.step_dir()
    cfg = ctx.spec.get("drop_motifs") or {}
    cands = []
    for p in sorted(glob.glob(os.path.join(ctx.root, "Plots", "drop_motifs*", "motifs*", "motifs.csv"))):
        sd = os.path.dirname(p)
        n = None
        try:
            with open(os.path.join(sd, "manifest.json"), encoding="utf-8") as fh:
                n = json.load(fh).get("n_motifs")
        except (OSError, ValueError):
            pass
        cands.append({"dir": os.path.relpath(sd, ctx.root).replace("\\", "/"), "n_motifs": n,
                      "npz_mb": os.path.getsize(os.path.join(sd, "motifs.npz")) / 1e6
                      if os.path.isfile(os.path.join(sd, "motifs.npz")) else None})
    C.write_csv(os.path.join(d, "stores_found.csv"), pd.DataFrame(cands))
    want = os.path.join(ctx.root, cfg.get("store", "Plots/drop_motifs12a/motifs"))
    if not os.path.isfile(os.path.join(want, "motifs.csv")):
        if not cands:
            ctx.warn("no drop-motif store found under Plots/drop_motifs*/motifs*")
            return {"store": None}
        best = sorted(cands, key=lambda c: (c["n_motifs"] or 0))[-1]
        ctx.warn(f"{cfg.get('store')} not found; using {best['dir']} (the largest store found)")
        want = os.path.join(ctx.root, best["dir"])
    sd_out = os.path.join(d, "store")
    os.makedirs(sd_out, exist_ok=True)
    for f in ("motifs.csv", "manifest.json"):
        if os.path.isfile(os.path.join(want, f)):
            shutil.copy2(os.path.join(want, f), os.path.join(sd_out, f))
    ev = pd.read_csv(os.path.join(want, "motifs.csv"))
    out = {"store": os.path.relpath(want, ctx.root).replace("\\", "/"), "events": int(len(ev))}
    if "species" in ev.columns:
        out["by_species"] = {str(k): int(v) for k, v in ev["species"].value_counts().items()}
    # the figures' notes and the sequences
    figs = os.path.join(ctx.root, cfg.get("figures", "Plots/drop_motifs12b"))
    copied = []
    for p in sorted(set(glob.glob(os.path.join(ctx.root, "Plots", "drop_motifs*", "*.md")) +
                        glob.glob(os.path.join(ctx.root, "Plots", "drop_motifs*", "sequences*.csv")) +
                        glob.glob(os.path.join(ctx.root, "Plots", "drop_motifs*", "*", "FIGURES.md")) +
                        glob.glob(os.path.join(ctx.root, "Plots", "drop_motifs*", "*", "CLAIMS.md")))):
        if os.path.getsize(p) > 5e6:
            continue
        rel = os.path.relpath(p, os.path.join(ctx.root, "Plots"))
        dst = os.path.join(d, "notes", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(p, dst)
        copied.append(rel.replace("\\", "/"))
    out["notes_copied"] = len(copied)
    seq_path = os.path.join(figs, "sequences.csv")
    seq = pd.read_csv(seq_path) if os.path.isfile(seq_path) else None
    out["sequences"] = None if seq is None else int(len(seq))
    npz = os.path.join(want, "motifs.npz")
    if not os.path.isfile(npz):
        ctx.warn("the store has no motifs.npz: snippets not exported")
        return out
    mb = os.path.getsize(npz) / 1e6
    if mb <= float(cfg.get("max_npz_mb", 20)) and mb <= ctx.max_part_mb * 0.8:
        shutil.copy2(npz, os.path.join(sd_out, "motifs.npz"))
        out["snippets"] = f"all ({mb:.1f} MB)"
        return out
    # a stratified subset + every sequence member
    rng = np.random.default_rng(int(cfg.get("seed", 0)))
    keep = set()
    seq_members = set()
    if seq is not None and {"species", "catalogue_id", "channel", "start_event_id", "end_event_id"} <= set(seq) and \
            {"species", "catalogue_id", "channel", "event_id", "onset_idx"} <= set(ev):
        for s in seq.itertuples():
            g = ev[(ev["species"] == s.species) & (ev["catalogue_id"] == s.catalogue_id) &
                   (ev["channel"] == s.channel)].sort_values("onset_idx").reset_index(drop=True)
            ids = list(g["event_id"])
            if s.start_event_id in ids and s.end_event_id in ids:
                a, b = ids.index(s.start_event_id), ids.index(s.end_event_id)
                seq_members |= set(ids[min(a, b):max(a, b) + 1])
    keep |= seq_members
    n_seq = len(keep)
    strat = "species" if "species" in ev.columns else None
    target = int(cfg.get("subset_n", 1000))
    rest = ev[~ev["event_id"].isin(keep)]
    if strat:
        groups = list(rest.groupby(strat))
        per = {k: int(round(target * len(g) / max(1, len(rest)))) for k, g in groups}
        for k, g in groups:
            n = min(len(g), max(1, per[k]))
            keep |= set(g["event_id"].iloc[np.sort(rng.choice(len(g), size=n, replace=False))])
    else:
        keep |= set(rest["event_id"].iloc[np.sort(rng.choice(len(rest), size=min(target, len(rest)),
                                                              replace=False))])
    z = np.load(npz)
    sub = {k: z[k] for k in z.files if k.partition("__")[0] in keep}
    np.savez_compressed(os.path.join(sd_out, "motifs_subset.npz"), **sub)
    sub_ev = ev[ev["event_id"].isin(keep)].copy()
    sub_ev["in_sequence"] = sub_ev["event_id"].isin(seq_members)
    C.write_csv(os.path.join(sd_out, "motifs_subset_events.csv"), sub_ev)
    out["snippets"] = (f"subset: {len(keep)} events ({n_seq} sequence members + a {target}-event stratified draw by "
                       f"species, seed {cfg.get('seed', 0)}); the full npz is {mb:.1f} MB")
    return out


# ════════════════════════════════════════════════════════════════════════════════════════════════════════
# 12. existing plots
# ════════════════════════════════════════════════════════════════════════════════════════════════════════

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".webp", ".tif", ".tiff")


def downscale_png(src, dst, max_w):
    """Downscale a PNG to at most `max_w` pixels wide: PIL when importable, else matplotlib's image io (every k-th
    pixel). Returns how, or None when neither is available."""
    try:
        from PIL import Image
        with Image.open(src) as im:
            w, h = im.size
            if w <= max_w:
                shutil.copy2(src, dst)
                return "copied (narrow enough)"
            im = im.resize((max_w, max(1, int(round(h * max_w / float(w))))), Image.LANCZOS)
            im.save(dst, optimize=True)
            return f"PIL {w}px -> {max_w}px"
    except ImportError:
        pass
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.image as mpimg
        a = mpimg.imread(src)
        k = int(math.ceil(a.shape[1] / float(max_w)))
        if k <= 1:
            shutil.copy2(src, dst)
            return "copied (narrow enough)"
        mpimg.imsave(dst, a[::k, ::k])
        return f"matplotlib every {k}th pixel"
    except Exception:  # noqa: BLE001
        return None


def step_existing_plots(ctx):
    d = ctx.step_dir()
    cfg = ctx.spec.get("existing_plots") or {}
    over = float(cfg.get("downscale_over_mb", 2)) * 1e6
    max_w = int(cfg.get("max_width_px", 2000))
    budget = float(cfg.get("max_total_mb", 200)) * 1e6
    rows, total = [], 0
    for rel_dir in cfg.get("dirs") or []:
        base = os.path.join(ctx.root, rel_dir)
        if not os.path.isdir(base):
            rows.append({"path": rel_dir, "status": "folder not found"})
            continue
        for dp, _dn, fns in os.walk(base):
            for fn in sorted(fns):
                if not fn.lower().endswith(IMAGE_EXT) or C.mentions_refused(os.path.join(dp, fn)):
                    continue                    # S. commune is refused everywhere, its figures included
                ctx.tick()
                src = os.path.join(dp, fn)
                rel = os.path.relpath(src, ctx.root).replace("\\", "/")
                size = os.path.getsize(src)
                dst = os.path.join(d, os.path.relpath(src, os.path.join(ctx.root, "Plots")))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                status = "copied"
                if fn.lower().endswith(".png") and size > over:
                    how = downscale_png(src, dst, max_w)
                    if how is None:
                        status = "skipped: over 2 MB and neither PIL nor matplotlib could downscale it"
                    else:
                        status = f"downscaled ({how})"
                elif size > ctx.max_part_mb * 0.8e6:
                    status = "skipped: larger than a zip part"
                else:
                    shutil.copy2(src, dst)
                out_size = os.path.getsize(dst) if os.path.isfile(dst) else 0
                if status.startswith(("copied", "downscaled")) and total + out_size > budget:
                    os.remove(dst)
                    status, out_size = f"skipped: over the {budget / 1e6:.0f} MB budget for plots", 0
                total += out_size
                rows.append({"path": rel, "bytes": size, "exported_bytes": out_size, "status": status})
    C.write_csv(os.path.join(d, "plots_manifest.csv"), pd.DataFrame(rows))
    return {"files": sum(1 for r in rows if str(r.get("status", "")).startswith(("copied", "downscaled"))),
            "skipped": sum(1 for r in rows if str(r.get("status", "")).startswith("skipped")),
            "exported_mb": round(total / 1e6, 1)}
