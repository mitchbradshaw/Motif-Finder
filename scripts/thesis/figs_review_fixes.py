"""Figures made after the 9 November figure review (read-only on the database and DATA/).

    python scripts/thesis/figs_review_fixes.py transfer      # ch7_transfer_examples
    python scripts/thesis/figs_review_fixes.py durations     # ch10_b9_durations
    python scripts/thesis/figs_review_fixes.py restitution   # ch10_b3_restitution
    python scripts/thesis/figs_review_fixes.py timeline      # ch10_b5_timeline
    python scripts/thesis/figs_review_fixes.py crops         # *_crop.png beside the originals
    python scripts/thesis/figs_review_fixes.py encodings     # ch2_encodings
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

DB_URI = "file:C:/Users/mmebr/Documents/CNN/DATA/db/annotations.sqlite?mode=ro"
UNIT = {"V": 1000.0, "mV": 1.0, "uV": 0.001}


def _db():
    return sqlite3.connect(DB_URI, uri=True)


def _recording(conn, rid):
    src, ch, f, units, npy = conn.execute(
        "SELECT source_file, channel, fs, units, npy_path FROM recordings WHERE id=?", (rid,)).fetchone()
    return dict(source=src, channel=int(ch), fs=float(f), units=units, npy=npy)


# ---------------------------------------------------------------- task 1: what accepted transfer matches look like
TRANSFER_ORDER = ["M2_concat", "M4", "LM", "CO", "SH", "SO", "MJu26a"]
SEED = dict(recording_id=2, start=1553283, end=1553660)      # library:2:1553283:1553660, Library entry 185


def _scalebar(ax, x0, y0, mv, label):
    ax.plot([x0, x0], [y0, y0 + mv], color=fs.INK, lw=1.4, solid_capstyle="butt", clip_on=False)
    ax.text(x0, y0 + mv / 2, " " + label, ha="left", va="center", fontsize=7, color=fs.INK)


def _nice(v):
    for s in (0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100):
        if s >= v:
            return s
    return 100


def transfer():
    key = json.loads((ROOT / "DATA/derived/rq2_blind/20261108-drop-transfer/key.json").read_text())
    pres = {p["panel_detection_id"]: p for p in key["presentations"]}
    rows = list(csv.DictReader(open(ROOT / "docs/thesis/data/reviews_completed_20261108/rq2_presentations.csv")))
    accepted = {}
    for r in rows:
        p = pres.get(int(r["panel_detection_id"]))
        if p and r["group"] == "transfer_match" and r["verdict"] in ("interesting", "seed") \
                and r["carried_only"] == "False":
            accepted.setdefault(p["recording"], []).append({**p, "verdict": r["verdict"]})
    conn = _db()
    picks = []
    seed_meta = _recording(conn, SEED["recording_id"])
    picks.append(dict(recording="M2_aug", label="M2_aug (seed)", channel=f"CH{seed_meta['channel'] + 1}",
                      start=SEED["start"], end=SEED["end"], meta=seed_meta, distance=None, verdict="seed",
                      n=None))
    for rec in TRANSFER_ORDER:
        L = sorted(accepted[rec], key=lambda p: p["source"]["distance"])
        p = L[(len(L) - 1) // 2]          # the median; for an even count, the lower of the two middle matches
        meta = _recording(conn, p["recording_id"])
        picks.append(dict(recording=rec, label=rec, channel=f"CH{meta['channel'] + 1}", start=p["start"], end=p["end"],
                          meta=_recording(conn, p["recording_id"]), distance=p["source"]["distance"],
                          verdict=p["verdict"], n=len(L), median=float(np.median([q["source"]["distance"] for q in L]))))
    conn.close()

    fig = plt.figure(figsize=(fs.TEXT_WIDTH_IN, 8.4), layout="constrained")
    grid = fig.add_gridspec(5, 2, height_ratios=[1, 1, 1, 1, 1.35])
    axes = [fig.add_subplot(grid[i // 2, i % 2]) for i in range(8)]
    over = fig.add_subplot(grid[4, :])
    pad_s = 300.0
    letters = "abcdefghi"
    print("panel recording channel start_h distance verdict n_accepted median_distance")
    for i, (ax, p) in enumerate(zip(axes, picks)):
        m = p["meta"]
        f = m["fs"]
        x = np.load(ROOT / m["npy"], mmap_mode="r")
        a, b = max(0, int(p["start"] - pad_s * f)), min(len(x), int(p["end"] + pad_s * f))
        v = np.asarray(x[a:b], dtype=float) * UNIT[m["units"]]
        t = (np.arange(a, b) - p["start"]) / f
        col = fs.colour(p["recording"])
        span = (p["end"] - p["start"]) / f
        ax.axvspan(0, span, color=col, alpha=0.12, lw=0)
        inside = (t >= 0) & (t <= span)
        ax.plot(t, v, color=fs.MUTED, lw=0.7)
        ax.plot(t[inside], v[inside], color=col, lw=1.1)
        lo, hi = np.nanmin(v), np.nanmax(v)
        rng = hi - lo
        ax.set_ylim(lo - 0.12 * rng, hi + 0.12 * rng)
        w = t[-1] - t[0]
        ax.set_xlim(t[0], t[-1] + 0.2 * w)
        bar = _nice(rng * 0.35)
        lab = (f"{bar:g} mV")
        _scalebar(ax, t[-1] + 0.03 * w, lo, bar, lab)
        ax.set_yticks([])
        ax.set_xticks([-200, 0, 200, 400, 600])
        ax.spines["left"].set_visible(False)
        ax.grid(False)
        hours = p["start"] / f / 3600
        strain = fs.RECORDINGS[p["recording"]][0]
        head = f"({letters[i]}) {p['label']} · {strain} · {p['channel']} · {hours:.2f} h"
        ax.set_title(head, fontsize=8, color=col, loc="left")
        if p["distance"] is not None:
            ax.text(0.01, 0.03, f"distance {p['distance']:.2f}", transform=ax.transAxes, fontsize=7,
                    color=fs.INK_2, va="bottom")
        if i >= 6:
            ax.set_xlabel("Seconds from match start")
        ax.tick_params(labelsize=7)
        print(f"({letters[i]}) {p['recording']} {p['channel']} (stored channel {m['channel']}) "
              f"start_idx={p['start']} start_h={hours:.4f} fs={f:g} "
              f"distance={p['distance']} verdict={p['verdict']} n={p['n']} median={p.get('median')}")
        z = v[inside]
        z = (z - z.mean()) / z.std()
        tz = np.linspace(0, span, len(z))
        over.plot(tz, z, color=col, lw=2.0 if p["distance"] is None else 1.0,
                  zorder=5 if p["distance"] is None else 3,
                  label=p["label"])
    over.set_xlim(0, 377)
    over.set_xlabel("Seconds from match start")
    over.set_ylabel("z-normalised")
    over.set_title("(i) The seed and the seven matches above, each z-normalised over its 377 s", fontsize=8,
                   loc="left")
    over.legend(ncol=4, fontsize=7, loc="upper right", handlelength=1.5)
    fs.save(fig, "ch7_transfer_examples")


# ---------------------------------------------------------------- task 3: B9 wavelet durations against both nulls
def durations():
    import pandas as pd
    d = ROOT / "docs/thesis/data/ch10_b9"
    ev = pd.read_csv(d / "events.csv")
    ev = ev[~(ev.edge_flag.astype(bool) | ev.step_pair.astype(bool))]      # the clean events b9_modes.py fits
    ev["rec"] = ev.recording.map(fs.name)
    recs = [r for r in ["M2_aug", "M2_concat", "LM", "CO", "MJu26a", "SH", "SO", "M4"] if r in set(ev.rec)]
    fig, axs = fs.figure("full", 4.3, 2, 3, layout="constrained", sharex=True)
    edges = np.logspace(1, np.log10(7200), 31)
    print("recording real aaft phase (clean events)")
    for ax, rec in zip(axs.flat, recs + ["pooled"]):
        e = ev if rec == "pooled" else ev[ev.rec == rec]
        col = fs.INK if rec == "pooled" else fs.colour(rec)
        n = {}
        for kind, c, ls, lab in (("real", col, "-", "recording"), ("aaft", fs.INK_2, "--", "AAFT copy"),
                                 ("pr", fs.NEUTRAL, ":", "phase-randomised copy")):
            x = e[e.kind == kind].best_scale_s.values
            n[kind] = len(x)
            ax.hist(x, bins=edges, histtype="step", color=c, ls=ls, lw=1.5 if kind == "real" else 1.2,
                    label=f"{lab} ({len(x)})")
        print(rec, n["real"], n["aaft"], n["pr"])
        ax.set_xscale("log")
        ax.set_title("All recordings pooled" if rec == "pooled" else
                     f"{rec} ({fs.RECORDINGS[rec][0]})", fontsize=8.5,
                     color=col)
        ax.legend(fontsize=6.5, loc="upper right", handlelength=1.8)
        ax.set_ylim(0, ax.get_ylim()[1] * 1.45)
    for ax in axs[1]:
        ax.set_xlabel("Event duration (s)")
    for ax in axs[:, 0]:
        ax.set_ylabel("Clean events")
    fs.save(fig, "ch10_b9_durations")


# ---------------------------------------------------------------- task 4: B3 restitution rho per train
def restitution():
    from matplotlib.lines import Line2D
    r = json.loads((ROOT / "docs/thesis/data/ch10_fhn/b3_restitution.json").read_text())
    groups = [("Oyster sequences, M2_aug", [s for s in r["sequences"]["rows"] if s["species"] == "oyster"]),
              ("Reishi sequences, F2A", [s for s in r["sequences"]["rows"] if s["species"] == "reishi"]),
              ("Long chains, M2_aug + MJu26a", r["chains"]["rows"])]
    for corpus in ("M2_aug", "M2_concat", "LM_fs2", "CO_fs2"):
        groups.append((f"All channels, {fs.name(corpus)}", r["census"][corpus]["channels"]))
    groups = [(g, [s for s in rows if s.get("rho") is not None]) for g, rows in groups]
    fig, axes = fs.figure("full", 4.4, 1, 2, sharey=True, layout="constrained")
    means = {}
    for ax, which, title in ((axes[0], "before", "(a) Recovery vs gap before the drop"),
                             (axes[1], "after", "(b) Control: recovery vs gap after")):
        allw, allr = [], []
        for gi, (g, rows) in enumerate(groups):
            rho = np.array([(s["rho"] if which == "before" else (s.get("control_gap_after") or {}).get("rho"))
                            for s in rows], dtype=float)
            p = np.array([(s["p_two"] if which == "before" else (s.get("control_gap_after") or {}).get("p_two"))
                          for s in rows], dtype=float)
            n = np.array([s["n_pairs"] for s in rows], float)
            cols = [fs.colour(s.get("source_file", "")) if fs.name(s.get("source_file", "")) in fs.RECORDINGS
                    else fs.NEUTRAL for s in rows]
            ok = np.isfinite(rho)
            jit = np.random.default_rng(gi).uniform(-0.25, 0.25, len(rows))
            for k in np.flatnonzero(ok):
                sig = p[k] < 0.05
                ax.scatter(rho[k], gi + jit[k], s=6 + 1.2 * n[k], facecolors=cols[k] if sig else "none",
                           edgecolors=cols[k], lw=0.8, alpha=0.85 if sig else 0.9, zorder=3)
            if ok.any():
                m = np.sum(n[ok] * rho[ok]) / np.sum(n[ok])
                ax.plot([m, m], [gi - 0.38, gi + 0.38], color=fs.INK, lw=2, zorder=4)
                means[(which, g)] = (m, int(ok.sum()), int(n[ok].sum()))
                allw += list(n[ok]); allr += list(rho[ok])
        means[(which, "all")] = (float(np.sum(np.array(allw) * np.array(allr)) / np.sum(allw)), len(allw), int(sum(allw)))
        ax.axvline(0, color=fs.MUTED, lw=0.8)
        ax.set_xlim(-1.05, 1.05)
        ax.set_xlabel("Spearman rho")
        ax.set_xticks([-1, -0.5, 0, 0.5, 1], ["−1", "−0.5", "0", "0.5", "1"])
        ax.set_title(title, fontsize=8.5, loc="left")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(range(len(groups)))
    axes[0].set_yticklabels([f"{g} ({len(rows)})" for g, rows in groups], fontsize=7.5)
    axes[0].invert_yaxis()
    handles = [Line2D([], [], marker="o", ls="", mfc=fs.INK_2, mec=fs.INK_2, label="permutation p < 0.05"),
               Line2D([], [], marker="o", ls="", mfc="none", mec=fs.INK_2, label="p ≥ 0.05"),
               Line2D([], [], color=fs.INK, lw=2, label="pair-weighted mean"),
               Line2D([], [], marker="o", ls="", mfc="none", mec=fs.MUTED, ms=3, label="dot area = pairs")]
    fig.legend(handles=handles, loc="outside lower center", ncol=4, fontsize=7.5)
    fs.save(fig, "ch10_b3_restitution")
    print("which group mean_rho trains pairs")
    for (which, g), (m, k, n) in means.items():
        print(f"{which:6s} {m:+.3f} {k:3d} {n:5d}  {g}")


# ---------------------------------------------------------------- task 5: B5 family timeline on M2_aug CH6
FAMILIES = [("BEADs_", "BEADs baseline/peak"), ("OASIS_", "OASIS deconvolution"),
            ("deconvolved_troughs", "Deconvolved troughs"), ("Wavelet_detection_prototype", "Wavelet prototype"),
            ("wavelet_encoded", "Wavelet-encoded"), ("noise_threshold", "Noise threshold"),
            ("signal_threshold", "Signal threshold"), ("drop_detection_v1", "Drop detector v1"),
            ("drop_detection_v5", "Drop detector v5"), ("cnn_gasf", "CNN, GASF"), ("cnn_gadf", "CNN, GADF"),
            ("cnn_recurrence", "CNN, recurrence plot"), ("cnn_fusion3", "CNN, RGB fusion")]


def timeline():
    import b5_map_timing as b5
    rid = 6                                         # M2_aug CH6 in the Map (stored channel 5)
    conn = _db()
    _, ch, f, n, units = conn.execute("SELECT id, channel, fs, n_samples, units FROM recordings WHERE id=?",
                                      (rid,)).fetchone()
    pick = {t: v for (r, t), v in b5._runs(conn, "M2_aug_concat_fs1.mat").items() if r == rid}
    rows, labels, totals = [], [], []
    for prefix, lab in FAMILIES:
        tpls = sorted(t for t in pick if t.startswith(prefix))
        C = np.array([b5.bin_counts(b5._starts(conn, pick[t][0]), n, f, 3.0) for t in tpls], float)
        C = C[C.max(axis=1) > 0]
        # each setting scaled to its own busiest bin, so one prolific setting cannot drown its siblings
        fam = (C / C.max(axis=1, keepdims=True)).mean(axis=0)
        rows.append(fam / fam.max())
        labels.append(f"{lab} ({len(C)})")
        totals.append(int(C.sum()))
    conn.close()
    M = np.array(rows)
    x = np.load(ROOT / "DATA/derived/channels/M2_aug_concat_fs1/CH5.npy", mmap_mode="r")
    nh = int(n // (3600 * f))
    hourly = np.nanmean(np.asarray(x[:int(nh * 3600 * f)], float).reshape(nh, -1), axis=1) * UNIT[units]
    days_bins = M.shape[1] * 3 / 24
    fig, (a0, a1) = plt.subplots(2, 1, figsize=(fs.TEXT_WIDTH_IN, 4.6), sharex=True, layout="constrained",
                                 gridspec_kw={"height_ratios": [1, 2.6]})
    a0.plot(np.arange(nh) / 24, hourly, color=fs.colour("M2_aug"), lw=1.1)
    a0.set_ylabel("Hourly mean (mV)")
    a0.set_title("(a) M2_aug CH6, hourly mean of the signal", fontsize=8.5, loc="left")
    im = a1.imshow(M, aspect="auto", cmap="Blues", vmin=0, vmax=1, interpolation="nearest",
                   extent=(0, days_bins, len(M) - 0.5, -0.5))
    a1.set_yticks(range(len(M)), labels, fontsize=7.5)
    a1.grid(False)
    a1.set_xlabel("Days from recording start")
    a1.set_title("(b) Detections per 3-hour bin, each detector family scaled to its own busiest bin",
                 fontsize=8.5, loc="left")
    a1.set_xlim(0, days_bins)
    cb = fig.colorbar(im, ax=a1, location="bottom", fraction=0.04, shrink=0.35, aspect=25, pad=0.02)
    cb.set_label("Share of the family's peak rate", fontsize=7.5)
    cb.ax.tick_params(labelsize=7)
    fs.save(fig, "ch10_b5_timeline")
    iu = np.triu_indices(len(M), 1)
    from scipy.stats import spearmanr
    rho = spearmanr(M.T).correlation
    print("families:", len(M), "bins:", M.shape[1], "mean pairwise Spearman between family rows:",
          round(float(np.nanmean(rho[iu])), 3))
    for l, t in zip(labels, totals):
        print(f"  {l}: {t} detections")


# ---------------------------------------------------------------- task 6: crops of legacy PNGs (originals untouched)
def _white(a):
    return (a[..., :3] > 244).all(axis=-1)


def _bbox(a, pad=8):
    ink = ~_white(a)
    ys, xs = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    return a[max(0, ys[0] - pad):ys[-1] + pad + 1, max(0, xs[0] - pad):xs[-1] + pad + 1]


def _squeeze(a, gap=40):
    """Collapse every run of blank columns longer than `gap` pixels to `gap`."""
    blank = _white(a).all(axis=0)
    keep, run = [], 0
    for j, b in enumerate(blank):
        run = run + 1 if b else 0
        if run <= gap:
            keep.append(j)
    return a[:, keep]


def _stack(parts, vgap=18, horizontal=False):
    parts = [p for p in parts if p.size]
    if horizontal:
        H = max(p.shape[0] for p in parts)
        out = np.full((H, sum(p.shape[1] for p in parts) + vgap * (len(parts) - 1), 3), 255, np.uint8)
        x = 0
        for p in parts:
            out[(H - p.shape[0]) // 2:(H - p.shape[0]) // 2 + p.shape[0], x:x + p.shape[1]] = p
            x += p.shape[1] + vgap
        return out
    W = max(p.shape[1] for p in parts)
    out = np.full((sum(p.shape[0] for p in parts) + vgap * (len(parts) - 1), W, 3), 255, np.uint8)
    y = 0
    for p in parts:
        x0 = (W - p.shape[1]) // 2
        out[y:y + p.shape[0], x0:x0 + p.shape[1]] = p
        y += p.shape[0] + vgap
    return out


def crops():
    from PIL import Image
    fig = ROOT / "docs/thesis/figures"

    def load(rel):
        return np.asarray(Image.open(fig / rel).convert("RGB"))

    def box(a, k, x0, y0, x1, y1):         # coordinates read off a preview drawn k times smaller
        return a[int(y0 * k):int(y1 * k), int(x0 * k):int(x1 * k)]

    def save(a, rel):
        out = fig / rel.replace(".png", "_crop.png")
        Image.fromarray(a).save(out)
        print(out.relative_to(ROOT), a.shape[1], "x", a.shape[0])

    a = load("roundb/b10_motif_lengths_m2aug.png")
    save(a[:745], "roundb/b10_motif_lengths_m2aug.png")

    a, k = load("drop_motifs/S2_2_scale_collapse.png"), 2470 / 1689
    rows = [_stack([_bbox(box(a, k, 110, y0, 548, y1)), _bbox(box(a, k, 770, y0, 1245, y1))], 60, True)
            for y0, y1 in ((60, 560), (735, 1235), (1405, 1905))]
    save(_stack(rows, 30), "drop_motifs/S2_2_scale_collapse.png")

    a, k = load("drop_motifs/S2_1_fall_angle.png"), 2443 / 2000
    save(_stack([_bbox(box(a, k, 190, 120, 1995, 665)), _bbox(box(a, k, 190, 725, 1995, 770)),
                 _bbox(box(a, k, 190, 810, 1995, 1415))], 30),
         "drop_motifs/S2_1_fall_angle.png")

    a, k = load("drop_motifs/S3_1_sequence_morph_oyster_id28_ch5_1394131s.png"), 3431 / 1565
    parts = [_bbox(box(a, k, 25, 42, 1305, 212)),
             _bbox(box(a, k, 300, 262, 1300, 284)), _squeeze(_bbox(box(a, k, 130, 284, 1365, 725))),
             _bbox(box(a, k, 130, 735, 1300, 770)),
             _bbox(box(a, k, 300, 797, 1300, 819)), _squeeze(_bbox(box(a, k, 130, 819, 1300, 1312))),
             _bbox(box(a, k, 130, 1314, 1300, 1348)),
             _bbox(box(a, k, 30, 1378, 1305, 1605)),
             _bbox(box(a, k, 140, 1640, 1310, 1935))]
    save(_stack(parts, 24), "drop_motifs/S3_1_sequence_morph_oyster_id28_ch5_1394131s.png")


# ---------------------------------------------------------------- task 9: the four image encodings of one real window
def encodings():
    import bundle_io as B
    sys.path.insert(0, str(ROOT))
    from Working.Catalogue.gramian.gramian_calc import compute_GASF, compute_GADF, compute_recurrence, compute_fusion
    st = B.Bundle(str(ROOT / "DATA/derived/thesis_bundle/wave1")).stack("hand_labels/hand_label_windows")
    rows = [i for i in range(len(st)) if st.index.iloc[i]["label"] == "interesting"]
    best = None
    for i in rows:                       # the accepted window whose labelled 10 min holds the largest excursion
        t, y = st.window(i)
        r = st.index.iloc[i]
        core = y[(t >= r["start"]) & (t < r["end"])]
        if best is None or np.ptp(core) > best[0]:
            best = (float(np.ptp(core)), i)
    i = best[1]
    r = st.index.iloc[i]
    t, y = st.window(i)
    inside = (t >= r["start"]) & (t < r["end"])
    w = y[inside]
    ch = int(r["channel"]) + 1
    print(f"window: annotation {int(r['annotation_id'])}, M2_aug ({r['source_file']}) CH{ch} (stored channel "
          f"{int(r['channel'])}, recording_id {int(r['recording_id'])}), samples {int(r['start'])}-{int(r['end'])} "
          f"at 1 Hz = {r['start'] / 3600:.3f}-{r['end'] / 3600:.3f} h, label {r['label']}, "
          f"range {np.ptp(w):.2f} mV, {len(w)} samples")
    fig = plt.figure(figsize=(fs.TEXT_WIDTH_IN, 3.6), layout="constrained")
    g = fig.add_gridspec(2, 4, height_ratios=[0.8, 1])
    ax = fig.add_subplot(g[0, :])
    col = fs.colour("M2_aug")
    ax.plot(t / 3600, y, color=fs.MUTED, lw=0.7)
    ax.plot(t[inside] / 3600, w, color=col, lw=1.1)
    ax.axvspan(r["start"] / 3600, r["end"] / 3600, color=col, alpha=0.10, lw=0)
    ax.set_xlabel("Recording time (h)")
    ax.set_ylabel("mV")
    ax.ticklabel_format(axis="x", useOffset=False)
    ax.set_title(f"(a) M2_aug CH{ch}, {r['start'] / 3600:.2f}–{r['end'] / 3600:.2f} h, labelled interesting (shaded), "
                 "with 30 min either side", fontsize=8, loc="left")
    imgs = [("(b) GASF", compute_GASF(w)), ("(c) GADF", compute_GADF(w)),
            ("(d) Recurrence plot", compute_recurrence(w)), ("(e) RGB fusion", compute_fusion(w))]
    for k, (name, img) in enumerate(imgs):
        bx = fig.add_subplot(g[1, k])
        bx.imshow(img, cmap=None if img.ndim == 3 else "gray", origin="upper", interpolation="nearest")
        bx.set_xticks([0, len(w) - 1], ["0", f"{len(w) / 60:.0f} min"], fontsize=7)
        bx.set_yticks([])
        bx.grid(False)
        bx.set_title(name, fontsize=8)
        for sp in bx.spines.values():
            sp.set_visible(False)
    fs.save(fig, "ch2_encodings")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    fs.apply()
    {"transfer": transfer, "durations": durations, "restitution": restitution, "timeline": timeline, "crops": crops, "encodings": encodings}[sys.argv[1]]()
