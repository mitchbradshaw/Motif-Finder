"""
catalogue_stats.py — the catalogue statistics for the thesis (chapter 9), read-only.

What it measures, per recording and pooled:

* the judged events of the two BLIND stratified queues (25: M2_aug; 28: CO_fs2, LM_fs2, M2_concat, L_LM fs2),
  own looks only (an adjudication whose ``carried_from`` is set is a copy of another verdict and is left out);
  classes: accepted = interesting or seed; rejected = not_interesting; artifact and unsure kept apart;
* the Library's accepted members (``annotations`` rows with ``source = 'library_review'`` and verdict
  interesting or seed), merged into distinct events (members on one channel overlapping >= 50 % of the shorter
  span are one event, as ``scripts/library_fragment_audit.py`` does);
* the seed-search censuses (every match judged: dip id010 = run group 9, long dip id020 = run group 12), for the
  intervals between accepted events on one channel, which is only meaningful where every event was judged.

Each event is measured with the tool's own Interrogation formulas:
``Working.interrogation.event_shape.measure_events`` (the core of ``interrogation.event_shape``) with
``polarity = "auto"`` (the window's fastest edge decides: a drop when the steepest fall is at least as steep as the
steepest rise) and ``to_mv`` from ``Working.units.read_as_mv(recordings.units)`` (V x1000, mV x1); and
``Working.interrogation.intervals`` (the core of ``interrogation.intervals``) for onsets on one channel.
The swing is ``span_ptp_mv``, the peak-to-peak of the samples inside the judged span, in mV. Duration is the judged
span's length (end - start) / fs; event_shape's onset-to-recovery ``duration_s`` is written beside it.
A second polarity reading, the Library's ``bases.polarity`` (excursion above vs below the span median), is written
beside the tool's rule, so the drop share can be seen to depend (or not) on the rule.

Never reads M4_aug_concat_fs1 (recordings 49-64), never opens Review queue 35, writes nothing to the database
(mode=ro) and nothing outside docs/thesis/data/ch9_catalogue/.

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/catalogue_stats.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch9_catalogue")
HELD_OUT_FILE = "M4_aug_concat_fs1.mat"
BLIND_QUEUES = (25, 28)
CENSUS_GROUPS = {9: "dip id010 (105 s seed, 3 channels)", 12: "long dip id020 (816 s seed, 16 channels)"}
SHORT = {"M2_aug_concat_fs1.mat": "M2_aug", "M2_concat_fs1.mat": "M2_concat", "CO_fs2.mat": "CO_fs2",
         "LM_fs2.mat": "LM_fs2", "L_LM_Jul_26_J_raw_fs2.mat": "L_LM_fs2", "L_LM_Jul_26_J_raw.mat": "L_LM_10Hz",
         "Fig2A_dt0p1.csv": "Fig2A", "Mushroom_260720_0509_4hrs_CH14_fs1.mat": "Mushroom_260720"}


def ro():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def klass(v):
    return {"interesting": "accepted", "seed": "accepted", "not_interesting": "rejected"}.get(v, v)


def blind_events(c):
    rows = []
    for qid in BLIND_QUEUES:
        f = json.loads(c.execute("SELECT filters_json FROM review_queues WHERE id = ?", (qid,)).fetchone()[0])
        ids = [int(x) for x in f["detection_ids"]]
        for k in range(0, len(ids), 500):
            chunk = ids[k:k + 500]
            ph = ",".join("?" * len(chunk))
            for r in c.execute(
                    f"SELECT d.id det, d.start_idx s, d.end_idx e, r.recording_id rid, "
                    f"(SELECT dr.template_name FROM discovery_runs dr WHERE dr.run_group_id = r.run_group_id "
                    f"ORDER BY dr.id LIMIT 1) run_name, "
                    f"a.verdict v, a.carried_from cf FROM detections d JOIN runs r ON r.id = d.run_id "
                    f"LEFT JOIN adjudications a ON a.detection_id = d.id WHERE d.id IN ({ph})", chunk):
                rows.append({"set": f"queue{qid}", "queue": qid, "det": r["det"], "recording_id": r["rid"],
                             "start": r["s"], "end": r["e"], "run_name": r["run_name"],
                             "verdict": r["v"] if r["cf"] is None else None,
                             "carried_only": r["v"] is not None and r["cf"] is not None})
    df = pd.DataFrame(rows)
    return df


def library_events(c):
    rows = [dict(r) for r in c.execute(
        "SELECT a.id ann, a.recording_id, a.start_idx start, a.end_idx \"end\", a.verdict FROM annotations a "
        "JOIN recordings r ON r.id = a.recording_id WHERE a.source = 'library_review' AND a.deleted_at IS NULL "
        "AND a.verdict IN ('interesting', 'seed') AND r.source_file != ?", (HELD_OUT_FILE,))]
    df = pd.DataFrame(rows)
    df["set"] = "library_accepted"
    df["queue"] = None
    df["det"] = None
    df["run_name"] = None
    # distinct events: union-find over >= 50 % overlap of the shorter span, per recording (one channel = one id)
    ev = np.arange(len(df))
    def find(i):
        while ev[i] != i:
            ev[i] = ev[ev[i]]
            i = ev[i]
        return i
    for rid, g in df.groupby("recording_id"):
        idx = g.sort_values("start").index.to_list()
        for a_i, a in enumerate(idx):
            for b in idx[a_i + 1:]:
                if df.at[b, "start"] >= df.at[a, "end"]:
                    break
                ov = min(df.at[a, "end"], df.at[b, "end"]) - max(df.at[a, "start"], df.at[b, "start"])
                short = min(df.at[a, "end"] - df.at[a, "start"], df.at[b, "end"] - df.at[b, "start"])
                if short > 0 and ov >= 0.5 * short:
                    ra, rb = find(a), find(b)
                    if ra != rb:
                        ev[rb] = ra
    df["distinct_event"] = [find(i) for i in range(len(df))]
    return df


def census_events(c):
    rows = []
    for g, label in CENSUS_GROUPS.items():
        for r in c.execute("SELECT d.id det, d.start_idx s, d.end_idx e, r.recording_id rid, a.verdict v, "
                           "a.carried_from cf FROM runs r JOIN detections d ON d.run_id = r.id "
                           "LEFT JOIN adjudications a ON a.detection_id = d.id "
                           "WHERE r.run_group_id = ? AND r.surrogate_of_run_id IS NULL", (g,)):
            rows.append({"set": f"census_rg{g}", "queue": None, "det": r["det"], "recording_id": r["rid"],
                         "start": r["s"], "end": r["e"], "run_name": label,
                         "verdict": r["v"] if r["cf"] is None else None})
    return pd.DataFrame(rows)


def measure(c, df):
    from Working.interrogation import event_shape as ES
    from Working.library.grouping.bases import polarity as median_polarity
    from Working.units import read_as_mv
    recs = {int(r["id"]): dict(r) for r in c.execute(
        "SELECT id, source_file, channel, fs, units, npy_path FROM recordings WHERE source_file != ?", (HELD_OUT_FILE,))}
    out = []
    for (_set, rid), g in df.groupby(["set", "recording_id"]):
        rec = recs.get(int(rid))
        if rec is None:      # a held-out recording, or a row whose recording is gone: never read
            continue
        to_mv, note = read_as_mv(rec["units"])
        x = np.load(rec["npy_path"], mmap_mode="r")
        g = g.copy()
        feats, _ = ES.measure_events(x, g["start"].to_numpy(), g["end"].to_numpy(), float(rec["fs"]),
                                     polarity="auto", to_mv=to_mv)
        feats.index = g.index
        g["source_file"] = rec["source_file"]
        g["recording"] = SHORT.get(rec["source_file"], rec["source_file"])
        g["channel"] = int(rec["channel"])
        g["fs"] = float(rec["fs"])
        g["units"] = rec["units"]
        g["to_mv"] = to_mv
        g["units_note"] = note
        g["span_s"] = (g["end"] - g["start"]) / float(rec["fs"])
        g["swing_mv"] = feats["span_ptp_mv"].astype(float)
        g["event_amplitude_mv"] = feats["event_amplitude_mv"].astype(float)
        g["event_duration_s"] = feats["duration_s"].astype(float)
        # event_shape records DROP = -1 and SPIKE = +1 (Working/interrogation/event_shape.py); until 2026-11-03 this
        # read the sign the other way round, so drop_share.png's grey bars showed the rise share
        g["polarity_auto"] = np.where(feats["polarity"].astype(int) < 0, "drop", "rise")
        g["polarity_median"] = [median_polarity(np.asarray(x[int(s):int(e)], dtype=float))
                                if int(e) - int(s) >= 3 else np.nan for s, e in zip(g["start"], g["end"])]
        out.append(g)
    return pd.concat(out, ignore_index=True) if out else df.iloc[0:0]


def q(a, p):
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.quantile(a, p)) if a.size else None


def summary(g):
    acc = g["class"] == "accepted"
    d = {"n": int(len(g)), "n_accepted": int(acc.sum()), "n_rejected": int((g["class"] == "rejected").sum()),
         "n_artifact": int((g["class"] == "artifact").sum()), "n_unsure": int((g["class"] == "unsure").sum())}
    for name, m in (("accepted", acc), ("rejected", g["class"] == "rejected")):
        h = g[m]
        if not len(h):
            continue
        d[name] = {
            "swing_mv": {"min": q(h.swing_mv, 0), "p05": q(h.swing_mv, .05), "median": q(h.swing_mv, .5),
                         "p95": q(h.swing_mv, .95), "max": q(h.swing_mv, 1)},
            "share_swing_over_95mv": float((h.swing_mv > 95).mean()),
            "share_swing_under_1mv": float((h.swing_mv < 1).mean()),
            "span_s": {"min": q(h.span_s, 0), "p05": q(h.span_s, .05), "median": q(h.span_s, .5),
                       "p95": q(h.span_s, .95), "max": q(h.span_s, 1)},
            "event_duration_s_median": q(h.event_duration_s, .5),
            "share_drop_auto": float((h.polarity_auto == "drop").mean()),
            "share_down_median_rule": float((h.polarity_median < 0).mean()),
        }
    return d


def intervals(df):
    from Working.interrogation import intervals as IV
    rows = []
    for (st, rid), g in df[df["class"] == "accepted"].groupby(["set", "recording_id"]):
        on = np.sort(g["start"].to_numpy(dtype=float)) / float(g["fs"].iloc[0])
        gaps = IV.inter_event_intervals(on)
        s = IV.interval_statistics(gaps, n_events=int(len(on)))
        rows.append({"set": st, "recording_id": int(rid), "recording": g["recording"].iloc[0],
                     "channel": int(g["channel"].iloc[0]), "n_events": int(len(on)),
                     "median_interval_s": s.get("median_s"), "cv": s.get("cv"), "lv": s.get("lv"),
                     "min_s": s.get("min_s"), "max_s": s.get("max_s")})
    return pd.DataFrame(rows)


def plots(df, iv):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sets = [("blind queues 25 + 28", df["set"].isin(["queue25", "queue28"])),
            ("Library accepted members", df["set"] == "library_accepted")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, (title, m) in zip(axes, sets):
        bins = np.logspace(-3, 3, 49)
        for cl, col in (("accepted", "C0"), ("rejected", "C1")):
            v = df.loc[m & (df["class"] == cl), "swing_mv"].dropna()
            v = v[v > 0]
            if len(v):
                ax.hist(v, bins=bins, histtype="step", color=col, label=f"{cl} (n={len(v)})")
        ax.set_xscale("log"); ax.set_xlabel("swing (peak-to-peak in the span), mV"); ax.set_ylabel("events")
        ax.set_title(title); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "swing_hist.png"), dpi=120); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, (title, m) in zip(axes, sets):
        bins = np.logspace(0, 5, 51)
        for cl, col in (("accepted", "C0"), ("rejected", "C1")):
            v = df.loc[m & (df["class"] == cl), "span_s"].dropna()
            if len(v):
                ax.hist(v, bins=bins, histtype="step", color=col, label=f"{cl} (n={len(v)})")
        ax.set_xscale("log"); ax.set_xlabel("judged span length, s"); ax.set_ylabel("events")
        ax.set_title(title); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "duration_hist.png"), dpi=120); plt.close(fig)

    b = df[df["set"].isin(["queue25", "queue28"]) & (df["class"] == "accepted")]
    med = b.groupby("recording")["polarity_median"].apply(lambda s: (s < 0).mean()).sort_index()
    auto = b.groupby("recording")["polarity_auto"].apply(lambda s: (s == "drop").mean()).reindex(med.index)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    xs = np.arange(len(med))
    ax.bar(xs - 0.2, med.values * 100, width=0.4, color="C0", label="excursion below the median (Library rule)")
    ax.bar(xs + 0.2, auto.values * 100, width=0.4, color="C7", label="fastest edge is a fall (event_shape auto)")
    for i, k in enumerate(med.index):
        ax.text(i - 0.2, med[k] * 100 + 1, f"{med[k]*100:.0f}%", ha="center", fontsize=8)
        ax.text(i, -9, f"n={int((b.recording == k).sum())}", ha="center", fontsize=8)
    ax.set_xticks(xs); ax.set_xticklabels(med.index)
    ax.set_ylim(-12, 110); ax.set_ylabel("accepted events read as falls, %"); ax.legend(fontsize=7, loc="upper right")
    ax.set_title("share of accepted blind-queue events that are falls, by rule")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "drop_share.png"), dpi=120); plt.close(fig)

    if len(iv):
        fig, ax = plt.subplots(figsize=(6, 3.2))
        for st, col in (("census_rg9", "C2"), ("census_rg12", "C3"), ("library_accepted", "C0")):
            m = df[(df["set"] == st) & (df["class"] == "accepted")]
            gaps = []
            for _rid, g in m.groupby("recording_id"):
                on = np.sort(g["start"].to_numpy(float)) / g["fs"].iloc[0]
                gaps.extend(np.diff(on).tolist())
            gaps = np.asarray(gaps)
            gaps = gaps[gaps > 0]
            if gaps.size:
                ax.hist(gaps / 3600.0, bins=np.logspace(-3, 3, 49), histtype="step", color=col,
                        label=f"{st} ({gaps.size} intervals)")
        ax.set_xscale("log"); ax.set_xlabel("interval between accepted events on one channel, h")
        ax.set_ylabel("intervals"); ax.legend(fontsize=8)
        fig.tight_layout(); fig.savefig(os.path.join(OUT, "intervals_hist.png"), dpi=120); plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    c = ro()
    b = blind_events(c)
    lib = library_events(c)
    cen = census_events(c)
    allev = pd.concat([b, lib, cen], ignore_index=True, sort=False)
    m = measure(c, allev)
    m["class"] = [klass(v) if isinstance(v, str) else "unjudged" for v in m["verdict"]]
    # queue 28's seven same-run overlapping pairs and any exact duplicate span: count each judged span once
    key = ["set", "recording_id", "start", "end"]
    n_before = len(m)
    m = m.drop_duplicates(key)
    m.to_csv(os.path.join(OUT, "events.csv"), index=False)

    res = {"rules": __doc__.split("Never reads")[0].strip(), "n_exact_duplicate_spans_dropped": int(n_before - len(m)),
           "units": m.groupby("recording")[["units", "to_mv"]].first().reset_index().to_dict("records"),
           "sets": {}}
    for st, g in m.groupby("set"):
        entry = {"pooled": summary(g), "per_recording": {r: summary(h) for r, h in g.groupby("recording")}}
        if st == "library_accepted":
            entry["n_distinct_events"] = int(g["distinct_event"].nunique())
            # distinct events: the longest member speaks for each
            gd = g.sort_values("span_s", ascending=False).drop_duplicates("distinct_event")
            entry["distinct_pooled"] = summary(gd)
        if st.startswith("queue"):
            entry["carried_only_left_out"] = int(b[(b["set"] == st)]["carried_only"].sum())
            entry["unjudged"] = int((g["class"] == "unjudged").sum())
        res["sets"][st] = entry
    blind = m[m["set"].isin(["queue25", "queue28"])]
    res["blind_pooled_25_28"] = {"pooled": summary(blind),
                                 "per_recording": {r: summary(h) for r, h in blind.groupby("recording")}}
    iv = intervals(m)
    iv.to_csv(os.path.join(OUT, "intervals_by_channel.csv"), index=False)
    res["intervals"] = {}
    for st, g in iv.groupby("set"):
        allgaps = []
        for (_s, rid), h in m[(m["set"] == st) & (m["class"] == "accepted")].groupby(["set", "recording_id"]):
            on = np.sort(h["start"].to_numpy(float)) / h["fs"].iloc[0]
            allgaps.extend(np.diff(on).tolist())
        a = np.asarray(allgaps)
        res["intervals"][st] = {"n_channels": int(len(g)), "n_intervals": int(a.size),
                                "median_s": q(a, .5), "p05_s": q(a, .05), "p95_s": q(a, .95),
                                "median_of_channel_cv": q(g["cv"].dropna(), .5)}
    with open(os.path.join(OUT, "catalogue_stats.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    plots(m, iv)
    print(json.dumps({k: v for k, v in res.items() if k not in ("rules",)}, indent=1, default=str)[:12000])


if __name__ == "__main__":
    main()
