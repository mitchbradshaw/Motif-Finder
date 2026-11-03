"""
b12_shapes_intervals.py - round-B question B12, read-only: do spike and drop SHAPES and INTERVALS differ between
recordings and species?

Protocol (declared before results; docs/rq_roundA_2/findings/b12-shapes-intervals-2026-11-03.md):

Shape - unit: one accepted event of the researcher's BLIND stratified queues 25 (M2_aug) and 28 (CO_fs2, LM_fs2,
M2_concat, L_LM fs2): own looks only (an adjudication with ``carried_from`` set is a copy and is left out), verdict
interesting or seed, each judged span once - the same 716 events as ledger E1-E4 (scripts/thesis/catalogue_stats.py,
whose readers are imported here, not copied). Each event is measured with the tool's own Interrogation code,
``Working.interrogation.event_shape.measure_events`` (polarity "auto", ``to_mv`` from ``Working.units.read_as_mv`` of
the recording's declared unit), on the stored samples of the judged span.

  features: amplitude |mV|, swing (peak-to-peak in the span) mV, judged span length s, event duration
  (onset -> half-recovery) s, onset->extremum s, 10-90 % rise time s, half-recovery time s, FWHM s, steepest slope
  |mV/s|, peakedness, asymmetry (onset->extremum share of onset->recovery), width fraction (FWHM / duration),
  normalised steepest slope (|slope| x duration / amplitude), drop share (polarity), and one multivariate
  duration-normalised waveform (the span resampled to 64 points, median removed, divided by its peak-to-peak).

  statistic: Kruskal-Wallis H across groups (rank-based, so mV scale and outliers do not drive it), epsilon^2 as
  the effect size; multivariate: a PERMANOVA-style pseudo-F (Euclidean) on the normalised waveforms.
  null: group labels shuffled across events, each group keeping its count (N_PERM draws, seeded); p = (k+1)/(N+1).
  duration control, three ways: (a) labels shuffled only WITHIN duration bands (quintiles of the judged span
  length), so a group difference that is only a duration difference is in the null too; (b) each log feature's
  residual after a cubic in log(span length), pooled, then the plain shuffle; (c) the duration-normalised features
  (asymmetry, width fraction, normalised slope, the normalised waveform), which carry no seconds.
  levels: recording (5 groups); species (oyster M2_aug, chocolate oyster CO, lion's mane = M2_concat + LM +
  L_LM); oyster + chocolate oyster pooled vs lion's mane (sensitivity); and lion's mane's three recordings alone
  (how big a recording difference is WITHIN one species, the yardstick a species difference has to beat).
  correction: Benjamini-Hochberg over the features of one level and one null
  (``Working.discovery.seeded_search.corrected_levels``).

Intervals - unit: one channel's complete ``drop_detection_v1`` run (the RQ4 sweep: whole channel, not superseded,
not a surrogate); onsets = detection start / fs. Per channel: LV and CV2 against the rate-matched Poisson and the
shuffled-interval nulls (``Working.interrogation.intervals.interval_nulls``, 1,000 draws, the B1 code). Across
channels: Kruskal-Wallis on per-channel LV (and CV2) by dataset and by species, null = dataset labels shuffled
across channels, each dataset keeping its channel count. Intervals between sampled accepted events are NOT used:
a stratified sample's gaps are the sampler's, not the organism's.

Never reads M4_aug_concat_fs1 or Schizophyllum commune (refused below), writes nothing to the database (mode=ro)
and nothing outside docs/thesis/data/ch10_b12/.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b12_shapes_intervals.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b12")
REFUSED = ("M4_aug_concat_fs1.mat", "Schizophyllum commune.txt")
N_PERM = 5000
SEED = 1203
SPECIES = {"M2_aug": "oyster", "CO_fs2": "chocolate oyster", "M2_concat": "lion's mane", "LM_fs2": "lion's mane",
           "L_LM_fs2": "lion's mane", "L_LM_10Hz": "lion's mane"}
SHORT = {"M2_aug_concat_fs1.mat": "M2_aug", "M2_concat_fs1.mat": "M2_concat", "CO_fs2.mat": "CO_fs2",
         "LM_fs2.mat": "LM_fs2", "L_LM_Jul_26_J_raw_fs2.mat": "L_LM_fs2", "L_LM_Jul_26_J_raw.mat": "L_LM_10Hz"}
WAVE_N = 64
SCALAR = ["amplitude_mv", "swing_mv", "span_s", "duration_s", "onset_to_extremum_s", "rise_time_s",
          "recovery_time_s", "fwhm_s", "max_slope_abs_mv_s", "peakedness", "asymmetry", "width_frac",
          "norm_slope", "is_drop"]
NORMALISED = {"asymmetry", "width_frac", "norm_slope", "peakedness", "is_drop"}


# ------------------------------------------------------------------------------------------------ statistics --
def _ranks(v):
    from scipy.stats import rankdata
    return rankdata(v)


def kw_perm(values, labels, n_perm=N_PERM, seed=SEED, strata=None):
    """Kruskal-Wallis H of `values` by `labels`, its epsilon^2, and a permutation p (labels shuffled, each group
    keeping its count; within `strata` when given). NaN values are dropped first (counted)."""
    v = np.asarray(values, dtype=float)
    lab = np.asarray(labels)
    ok = np.isfinite(v)
    v, lab = v[ok], lab[ok]
    st = None if strata is None else np.asarray(strata)[ok]
    groups, g = np.unique(lab, return_inverse=True)
    n, k = len(v), len(groups)
    if k < 2 or n < k + 2:
        return {"n": int(n), "k": int(k), "H": None, "eps2": None, "p": None}
    r = _ranks(v)
    cnt = np.bincount(g, minlength=k).astype(float)

    def H(gi):
        s = np.bincount(gi, weights=r, minlength=k)
        return 12.0 / (n * (n + 1)) * np.sum(s ** 2 / cnt) - 3 * (n + 1)

    h0 = H(g)
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(n_perm):
        if st is None:
            gp = rng.permutation(g)
        else:
            gp = g.copy()
            for s in np.unique(st):
                idx = np.flatnonzero(st == s)
                gp[idx] = rng.permutation(g[idx])
        ge += H(gp) >= h0 - 1e-12
    return {"n": int(n), "k": int(k), "H": float(h0), "eps2": float(h0 / (n - 1)), "p": (ge + 1) / (n_perm + 1),
            "n_dropped": int((~ok).sum())}


def permanova(X, labels, n_perm=N_PERM, seed=SEED, strata=None):
    """Pseudo-F = (between SS / (k-1)) / (within SS / (n-k)), Euclidean, on rows of X; permutation p as above."""
    X = np.asarray(X, dtype=float)
    lab = np.asarray(labels)
    ok = np.isfinite(X).all(axis=1)
    X, lab = X[ok], lab[ok]
    st = None if strata is None else np.asarray(strata)[ok]
    groups, g = np.unique(lab, return_inverse=True)
    n, k = len(X), len(groups)
    tot = float(((X - X.mean(0)) ** 2).sum())
    cnt = np.bincount(g, minlength=k).astype(float)

    def F(gi):
        sums = np.zeros((k, X.shape[1]))
        np.add.at(sums, gi, X)
        between = float((sums ** 2 / cnt[:, None]).sum() - n * (X.mean(0) ** 2).sum())
        within = tot - between
        return (between / (k - 1)) / (within / (n - k)), between / tot

    f0, r2 = F(g)
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(n_perm):
        if st is None:
            gp = rng.permutation(g)
        else:
            gp = g.copy()
            for s in np.unique(st):
                idx = np.flatnonzero(st == s)
                gp[idx] = rng.permutation(g[idx])
        ge += F(gp)[0] >= f0 - 1e-12
    return {"n": int(n), "k": int(k), "pseudo_F": float(f0), "R2": float(r2), "p": (ge + 1) / (n_perm + 1)}


def bh(ps):
    """(BH q-value, passes at alpha 0.05) per test. The pass/fail is the project helper's
    (``corrected_levels``, BH step-up); the q-value is the usual adjusted p, written beside it."""
    from Working.discovery.seeded_search import corrected_levels
    ps = [1.0 if p is None else float(p) for p in ps]
    lv = corrected_levels(ps, alpha=0.05, correction="BH")
    m = len(ps)
    order = np.argsort(ps)
    q = np.empty(m)
    run = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        run = min(run, ps[i] * m / rank)
        q[i] = run
    return [(float(qq), lvl is not None) for qq, lvl in zip(q, lv)]


# ------------------------------------------------------------------------------------------------ shape data --
def accepted_events(c):
    from catalogue_stats import blind_events, klass
    b = blind_events(c)
    b["class"] = [klass(v) if isinstance(v, str) else "unjudged" for v in b["verdict"]]
    b = b[b["class"] == "accepted"].drop_duplicates(["set", "recording_id", "start", "end"])
    return b


def measure(c, ev):
    from Working.interrogation import event_shape as ES
    from Working.units import read_as_mv
    recs = {int(r[0]): dict(zip(("id", "source_file", "channel", "fs", "units", "npy_path"), r)) for r in c.execute(
        "SELECT id, source_file, channel, fs, units, npy_path FROM recordings")}
    rows, waves = [], []
    for rid, g in ev.groupby("recording_id"):
        rec = recs[int(rid)]
        if rec["source_file"] in REFUSED:
            raise SystemExit(f"refused recording {rec['source_file']} reached the shape reader")
        to_mv, _note = read_as_mv(rec["units"])
        fs = float(rec["fs"])
        x = np.load(rec["npy_path"], mmap_mode="r")
        s_, e_ = g["start"].to_numpy(int), g["end"].to_numpy(int)
        f, _ = ES.measure_events(x, s_, e_, fs, polarity="auto", to_mv=to_mv)
        for i, (s, e) in enumerate(zip(s_, e_)):
            fr = f.iloc[i]
            amp = abs(float(fr["event_amplitude_mv"]))
            dur = float(fr["duration_s"])
            o2x = (float(fr["extremum_idx"]) - float(fr["onset_idx"])) / fs
            x2r = (float(fr["recovery_idx"]) - float(fr["extremum_idx"])) / fs
            slope = abs(float(fr["max_slope_mv_s"]))
            seg = np.asarray(x[s:e], dtype=float) * to_mv
            if seg.size >= 4 and np.isfinite(seg).all() and np.ptp(seg) > 0:
                w = np.interp(np.linspace(0, seg.size - 1, WAVE_N), np.arange(seg.size), seg)
                w = (w - np.median(w)) / np.ptp(w)
            else:
                w = np.full(WAVE_N, np.nan)
            waves.append(w)
            rows.append({
                "det": int(g["det"].iloc[i]), "queue": int(g["queue"].iloc[i]), "recording_id": int(rid),
                "recording": SHORT[rec["source_file"]], "channel": int(rec["channel"]), "fs": fs,
                "units": rec["units"], "to_mv": to_mv, "detector": g["run_name"].iloc[i],
                "start": int(s), "end": int(e), "span_s": (e - s) / fs,
                "amplitude_mv": amp, "swing_mv": float(fr["span_ptp_mv"]), "duration_s": dur,
                "onset_to_extremum_s": o2x, "rise_time_s": float(fr["rise_time_s"]),
                "recovery_time_s": float(fr["recovery_time_s"]), "fwhm_s": float(fr["fwhm_s"]),
                "max_slope_abs_mv_s": slope, "peakedness": float(fr["peakedness"]),
                "asymmetry": o2x / (o2x + x2r) if np.isfinite(x2r) and (o2x + x2r) > 0 else np.nan,
                "width_frac": float(fr["fwhm_s"]) / dur if dur and np.isfinite(dur) and dur > 0 else np.nan,
                "norm_slope": slope * dur / amp if amp > 0 and np.isfinite(dur) else np.nan,
                "is_drop": 1.0 if int(fr["polarity"]) == ES.DROP else 0.0,
            })
    df = pd.DataFrame(rows)
    df["species"] = df["recording"].map(SPECIES)
    return df, np.vstack(waves)


def residual_on_duration(v, span_s):
    """log(v) minus a pooled cubic in log(span length); NaN where v <= 0 or not finite."""
    v = np.asarray(v, dtype=float)
    lx = np.log(np.asarray(span_s, dtype=float))
    ok = np.isfinite(v) & (v > 0) & np.isfinite(lx)
    out = np.full(v.shape, np.nan)
    if ok.sum() > 10:
        coef = np.polyfit(lx[ok], np.log(v[ok]), 3)
        out[ok] = np.log(v[ok]) - np.polyval(coef, lx[ok])
    return out


def shape_tests(df, W):
    df = df.copy()
    df["band"] = pd.qcut(df["span_s"], 5, labels=False, duplicates="drop")
    levels = {
        "recording": (df["recording"], np.ones(len(df), bool)),
        "species (3)": (df["species"], np.ones(len(df), bool)),
        "oyster+CO vs lion's mane": (np.where(df["species"] == "lion's mane", "lion's mane", "oyster family"),
                                     np.ones(len(df), bool)),
        "lion's mane recordings only": (df["recording"], (df["species"] == "lion's mane").to_numpy()),
    }
    rows = []
    for lvl, (lab, m) in levels.items():
        lab = np.asarray(lab)[m]
        sub = df[m]
        for null in ("shuffle", "within duration bands", "duration residual"):
            block = []
            for f in SCALAR:
                v = sub[f].to_numpy(float)
                if null == "duration residual":
                    if f in NORMALISED or f == "span_s":
                        continue
                    v = residual_on_duration(v, sub["span_s"].to_numpy(float))
                if null == "within duration bands" and f == "span_s":
                    continue
                r = kw_perm(v, lab, strata=sub["band"].to_numpy() if null == "within duration bands" else None)
                block.append({"level": lvl, "null": null, "feature": f, **r})
            # the normalised waveform
            Wm = W[m]
            r = permanova(Wm, lab, n_perm=2000,
                          strata=sub["band"].to_numpy() if null == "within duration bands" else None)
            block.append({"level": lvl, "null": null, "feature": "normalised waveform (64 pt)",
                          "H": None, "eps2": None, "n": r["n"], "k": r["k"], "p": r["p"],
                          "pseudo_F": r["pseudo_F"], "R2": r["R2"]})
            q = bh([b["p"] for b in block])
            for b, (qq, ok) in zip(block, q):
                b["q_bh"], b["bh_pass_05"] = qq, ok
            rows.extend(block)
    return pd.DataFrame(rows)


def per_group_summary(df, by):
    out = []
    for k, g in df.groupby(by):
        d = {by: k, "n": len(g), "drop_share": float(g["is_drop"].mean())}
        for f in SCALAR:
            if f == "is_drop":
                continue
            v = g[f].to_numpy(float)
            v = v[np.isfinite(v)]
            d[f"{f}_median"] = float(np.median(v)) if v.size else None
            d[f"{f}_n"] = int(v.size)
        d["detectors"] = "; ".join(f"{a} ({b})" for a, b in g["detector"].value_counts().items())
        out.append(d)
    return pd.DataFrame(out)


# ------------------------------------------------------------------------------------------------ intervals --
def interval_channels(c):
    from Working.interrogation.intervals import interval_nulls
    q = ("SELECT DISTINCT r.id, r.recording_id, rec.source_file, rec.channel, rec.fs, r.span_start, r.span_end, "
         "rec.n_samples FROM runs r JOIN recordings rec ON rec.id = r.recording_id "
         "JOIN discovery_runs dr ON dr.run_group_id = r.run_group_id "
         "WHERE dr.template_name = 'drop_detection_v1' AND r.surrogate_of_run_id IS NULL AND r.status = 'completed' "
         "AND r.superseded_at IS NULL")
    runs = pd.DataFrame([tuple(r) for r in c.execute(q).fetchall()], columns=["run", "recording_id", "source_file", "channel", "fs",
                                                          "span_start", "span_end", "n_samples"])
    runs = runs[~runs["source_file"].isin(REFUSED) & runs["source_file"].isin(SHORT)]
    runs["len"] = runs["span_end"] - runs["span_start"]
    # one complete run per channel: the longest span, latest run on a tie
    runs = runs.sort_values(["recording_id", "len", "run"]).drop_duplicates("recording_id", keep="last")
    rows = []
    for _, r in runs.iterrows():
        on = np.array([s for (s,) in c.execute("SELECT start_idx FROM detections WHERE run_id = ?", (int(r.run),))],
                      dtype=float) / float(r.fs)
        nl = interval_nulls(on, resolution_s=1.0 / float(r.fs))
        po, sh = nl.get("poisson") or {}, nl.get("shuffle") or {}
        rows.append({"run": int(r.run), "recording_id": int(r.recording_id), "dataset": SHORT[r.source_file],
                     "species": SPECIES[SHORT[r.source_file]], "channel": int(r.channel), "fs": float(r.fs),
                     "complete": bool(r.span_start == 0 and r.span_end >= r.n_samples - 1),
                     "hours": float(r.len / r.fs / 3600.0), "n_events": nl["n_events"],
                     "lv": (po.get("lv") or {}).get("observed"), "cv2": (po.get("cv2") or {}).get("observed"),
                     "lv_poisson_lo": (po.get("lv") or {}).get("lo"), "lv_poisson_hi": (po.get("lv") or {}).get("hi"),
                     "lv_p_poisson": (po.get("lv") or {}).get("p"),
                     "lv_p_shuffled": (sh.get("lv") or {}).get("p"),
                     "lv_shuffled_mean": (sh.get("lv") or {}).get("null_mean"),
                     "cv2_p_poisson": (po.get("cv2") or {}).get("p"),
                     "caveat": nl.get("caveat") or nl.get("note")})
    return pd.DataFrame(rows), nl


def interval_tests(iv):
    rows = []
    for lvl, lab, m in (("dataset", iv["dataset"], np.ones(len(iv), bool)),
                        ("species (3)", iv["species"], np.ones(len(iv), bool)),
                        ("oyster+CO vs lion's mane", np.where(iv["species"] == "lion's mane", "lion's mane",
                                                                "oyster family"), np.ones(len(iv), bool)),
                        ("lion's mane datasets only", iv["dataset"], (iv["species"] == "lion's mane").to_numpy())):
        block = []
        for f in ("lv", "cv2", "n_events"):
            r = kw_perm(iv[f].to_numpy(float)[m], np.asarray(lab)[m], n_perm=10000)
            block.append({"level": lvl, "feature": f, **r})
        q = bh([b["p"] for b in block[:2]]) + [(None, None)]
        for b, (qq, ok) in zip(block, q):
            b["q_bh_lv_cv2"], b["bh_pass_05"] = qq, ok
        rows.extend(block)
    return pd.DataFrame(rows)


def main():
    import sqlite3
    os.makedirs(OUT, exist_ok=True)
    db = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    ev = accepted_events(c)
    df, W = measure(c, ev)
    df.to_csv(os.path.join(OUT, "events_shape.csv"), index=False)
    np.save(os.path.join(OUT, "waveforms_64.npy"), W)
    per_group_summary(df, "recording").to_csv(os.path.join(OUT, "shape_by_recording.csv"), index=False)
    per_group_summary(df, "species").to_csv(os.path.join(OUT, "shape_by_species.csv"), index=False)
    st = shape_tests(df, W)
    st.to_csv(os.path.join(OUT, "shape_tests.csv"), index=False)
    iv, _ = interval_channels(c)
    iv.to_csv(os.path.join(OUT, "intervals_by_channel.csv"), index=False)
    it = interval_tests(iv)
    it.to_csv(os.path.join(OUT, "interval_tests.csv"), index=False)
    # mean normalised waveform per recording, for the report's figure
    mw = {r: np.nanmean(W[(df["recording"] == r).to_numpy()], axis=0).tolist() for r in df["recording"].unique()}
    with open(os.path.join(OUT, "mean_waveform_by_recording.json"), "w", encoding="utf-8") as fh:
        json.dump(mw, fh)
    plots(df, W, iv)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    print(df.groupby("recording").size())
    print(per_group_summary(df, "recording").T)
    print(st.to_string())
    print(iv.drop(columns=["caveat"]).to_string())
    print(it.to_string())


def plots(df, W, iv):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    order = ["M2_aug", "CO_fs2", "M2_concat", "LM_fs2", "L_LM_fs2"]
    order = [o for o in order if o in set(df["recording"])]
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.4))
    for ax, f, lab, log in zip(axes.ravel(),
                               ("amplitude_mv", "span_s", "max_slope_abs_mv_s", "asymmetry", "width_frac", "norm_slope"),
                               ("amplitude, mV", "judged span, s", "steepest slope, |mV/s|",
                                "asymmetry (onset->extremum share)", "FWHM / duration", "|slope| x duration / amplitude"),
                               (True, True, True, False, False, True)):
        data = [df.loc[df.recording == o, f].dropna().to_numpy() for o in order]
        data = [d[d > 0] if log else d for d in data]
        ax.boxplot(data, showfliers=False)
        for i, d in enumerate(data):
            ax.scatter(np.random.default_rng(i).normal(i + 1, 0.07, d.size), d, s=3, alpha=0.3, color="C0")
        ax.set_xticks(range(1, len(order) + 1))
        ax.set_xticklabels([f"{o}\n(n={len(d)})" for o, d in zip(order, data)], fontsize=7)
        if log:
            ax.set_yscale("log")
        ax.set_ylabel(lab, fontsize=8)
    fig.suptitle("B12: accepted events (blind queues 25 + 28) by recording")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "b12_shape_by_recording.png"), dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    x = np.linspace(0, 1, W.shape[1])
    for i, o in enumerate(order):
        m = (df["recording"] == o).to_numpy()
        ax.plot(x, np.nanmean(W[m], axis=0), label=f"{o} (n={m.sum()})", color=f"C{i}")
    ax.set_xlabel("position in the judged span (0-1)")
    ax.set_ylabel("(x - median) / peak-to-peak")
    ax.legend(fontsize=7)
    ax.set_title("mean duration-normalised waveform per recording")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "b12_mean_waveform.png"), dpi=120)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    dorder = [o for o in order if o in set(iv["dataset"])]
    for ax, f in zip(axes, ("lv", "cv2")):
        for i, o in enumerate(dorder):
            v = iv.loc[iv.dataset == o, f].dropna().to_numpy()
            ax.scatter(np.full(v.size, i) + np.random.default_rng(i).normal(0, 0.06, v.size), v, s=14, color=f"C{i}")
        ax.axhline(1.0, color="grey", lw=0.8, ls="--")
        ax.set_xticks(range(len(dorder)))
        ax.set_xticklabels(dorder, fontsize=8)
        ax.set_ylabel(f"{f.upper()} per channel (drop_detection_v1)")
    fig.suptitle("B12: interval irregularity per channel; dashed = Poisson expectation")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "b12_intervals_lv_cv2.png"), dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
