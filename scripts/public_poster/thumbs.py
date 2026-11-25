"""Public poster: candidate drop trains for the thumbnail panel, and the panel itself.

Candidates:
* the hand-labelled and Review-accepted sequences (all on M2_aug, oyster), from the database's human sequences;
* machine-found trains on the other recordings with a known species (CO, LM, SH, SO, M4, MJu26a): runs of 10 or more
  of the poster's drops (pool p >= 0.8 plus reviewed library drops) that come at a steady pace (low spread of the
  gaps), are alike in depth, and stand well clear of the trace's noise.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/thumbs.py candidates
    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/thumbs.py panel
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style as S  # noqa: E402
import seqdata as Q  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

SPECIES = {"M2_aug": "oyster", "M4": "oyster", "CO": "chocolate oyster", "SO": "snow oyster", "SH": "Asian shiitake",
           "LM": "lion's mane", "MJu26a": "lion's mane"}
SP_DIR = os.path.join(S.OUT, "thumb_candidates")


def human_sequences():
    D = Q.dp()
    c = sqlite3.connect(f"file:{D.DB}?mode=ro", uri=True)
    d = pd.read_sql("""SELECT s.id, s.recording_id rid, r.source_file, r.channel, r.fs, s.start_idx, s.end_idx,
                       a.verdict, substr(a.note, 1, 80) note FROM sequences s JOIN recordings r ON r.id = s.recording_id
                       LEFT JOIN annotations a ON a.id = s.annotation_id WHERE s.origin = 'human'""", c)
    d = d[d["verdict"] == "interesting"].copy()
    d["dataset"] = "M2_aug"
    d["kind"] = "human"
    return d


def machine_trains(k=10, per_rec=3):
    ev = pd.read_parquet(os.path.join(S.DATA, "drops.parquet"))
    ev = ev[ev["dataset"] != "M2_aug"].copy()
    ev["t_s"] = ev["top_idx"] / ev["fs"]
    rows = []
    for rid, g in ev.groupby("recording_id"):
        g = g.sort_values("t_s").reset_index(drop=True)
        if len(g) < k:
            continue
        t = g["t_s"].to_numpy()
        dep = g["depth_mv"].to_numpy()
        cand = []
        for i in range(len(g) - k + 1):
            tt = t[i:i + k]
            gaps = np.diff(tt)
            dur = tt[-1] - tt[0]
            if not (0.4 * 3600 <= dur <= 14 * 3600) or gaps.min() <= 0:
                continue
            cv_gap = gaps.std() / gaps.mean()
            dd = dep[i:i + k]
            cv_dep = dd.std() / dd.mean()
            score = cv_gap + 0.7 * cv_dep - 0.15 * np.log10(np.median(dd))
            cand.append((score, i, dur, cv_gap, cv_dep, np.median(dd)))
        cand.sort()
        used = []
        for sc, i, dur, cvg, cvd, md in cand:
            a, b = t[i], t[i + k - 1]
            if any(not (b < u0 or a > u1) for u0, u1 in used):
                continue
            used.append((a, b))
            r = g.iloc[i]
            fs = float(r["fs"])
            rows.append({"id": f"m{rid}_{i}", "rid": int(rid), "dataset": r["dataset"], "channel": int(r["channel"]),
                         "fs": fs, "start_idx": int(a * fs - 0.15 * dur * fs), "end_idx": int(b * fs + 0.15 * dur * fs),
                         "score": sc, "cv_gap": cvg, "cv_depth": cvd, "depth_mv": md, "hours": dur / 3600,
                         "kind": "machine"})
            if len(used) >= per_rec:
                break
    return pd.DataFrame(rows)


def noise_ratio(y, depth):
    n = np.nanmedian(np.abs(np.diff(y))) * 1.4826 + 1e-9
    return depth / n


def candidates():
    os.makedirs(SP_DIR, exist_ok=True)
    h = human_sequences()
    m = machine_trains()
    m = m.sort_values("score").groupby("dataset").head(6)
    allc = pd.concat([h, m], ignore_index=True)
    allc.to_csv(os.path.join(SP_DIR, "candidates.csv"), index=False)
    S.apply(base=10)
    n = len(allc)
    cols = 5
    rows_ = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows_, cols, figsize=(cols * 4.2, rows_ * 2.1))
    for ax, r in zip(axes.ravel(), allc.itertuples()):
        step = max(1, int((r.end_idx - r.start_idx) / 4000))
        idx, y = Q.trace(int(r.rid), r.start_idx, r.end_idx, step=step)
        ax.plot((idx - idx[0]) / r.fs / 3600, y, color=S.SPECIES_COLOUR[SPECIES[r.dataset]], lw=0.8)
        ax.set_title(f"{r.id} {r.dataset} ch{r.channel} {(r.end_idx - r.start_idx) / r.fs / 3600:.1f} h "
                     f"{'' if r.kind == 'human' else f'cv {r.cv_gap:.2f}/{r.cv_depth:.2f}'}", fontsize=8)
        ax.set_yticks([])
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(SP_DIR, "contact_sheet.png"), dpi=70)
    print(allc[["id", "dataset", "channel", "kind"]].to_string())




#: The ten thumbnails: (candidate id, title). Chosen by eye from the contact sheet (25 Nov) for clear trains, low noise
#: and variety: every species, and the kinds of train the NeurIPS session listed (regular, winding down, speeding up,
#: bursty, riding a slow wave, very large drops).
PANEL = [
    ("137", "Fading burst"),
    ("130", "Bursts and pauses"),
    ("136", "Ripples on a slow wave"),
    ("m54_144", "Regular spike train"),
    ("m644_123", "Spikes on a rising baseline"),
    ("m637_155", "Growing amplitude"),
    ("m638_252", "Large square drops"),
    ("m697_258", "Sawtooth with drift"),
    ("m710_51", "Accelerating sequence"),
    ("m714_174", "Ripples on a rising trend"),
]


def nice_bar(span):
    for v in (1, 2, 5, 10, 20, 50, 100, 200):
        if v >= span * 0.22:
            return v
    return 500


def duration_text(h):
    return f"{h * 60:.0f} min" if h < 1.5 else f"{h:.0f} h" if h >= 10 else f"{h:.1f} h"


def panel(w_mm=392, h_mm=86):
    S.apply(base=14)
    c = pd.read_csv(os.path.join(SP_DIR, "candidates.csv"))
    c["id"] = c["id"].astype(str)
    fig = S.figure(w_mm, h_mm)
    cols, rows = 5, 2
    W_, H_ = 1 / cols, 1 / rows
    meta = []
    for k, (cid, title) in enumerate(PANEL):
        r = c[c["id"] == cid].iloc[0]
        i, j = k % cols, k // cols
        ax = fig.add_axes([i * W_ + 0.025, 1 - (j + 1) * H_ + 0.05, W_ - 0.04, H_ - 0.2])
        n = int(r.end_idx - r.start_idx)
        idx, y = Q.trace(int(r.rid), r.start_idx, r.end_idx)
        per = max(1, n // 1500)
        if per > 1:
            m = len(y) // per * per
            Y = y[:m].reshape(-1, per)
            xs = np.repeat(idx[:m].reshape(-1, per)[:, 0], 2)
            ys = np.column_stack([np.nanmax(Y, 1), np.nanmin(Y, 1)]).ravel()
        else:
            xs, ys = idx, y
        sp = SPECIES[r.dataset]
        col = S.SPECIES_COLOUR[sp]
        ax.plot((xs - xs[0]) / r.fs / 3600, ys, color=col, lw=1.5, solid_joinstyle="round")
        for s_ in ("left", "bottom", "top", "right"):
            ax.spines[s_].set_visible(False)
        ax.set_xticks([])
        ax.set_yticks([])
        lo, hi = np.nanmin(ys), np.nanmax(ys)
        bar = nice_bar(hi - lo)
        x0 = -0.03 * (n / r.fs / 3600)
        ax.plot([x0, x0], [lo, lo + bar], color=S.INK_2, lw=2.5, solid_capstyle="butt", clip_on=False)
        ax.text(x0 - 0.015 * (n / r.fs / 3600), lo + bar / 2, f"{bar:g}\nmV", ha="right", va="center", fontsize=10.5,
                color=S.INK_2, linespacing=0.95)
        hours = n / r.fs / 3600
        ax.set_title(title, loc="left", fontsize=15.5, fontweight="bold", color=S.INK, pad=16)
        ax.text(0, 1.015, f"{S.SPECIES_LABEL[sp]}  ·  {duration_text(hours)}", transform=ax.transAxes,
                fontsize=12.5, color=col, fontweight="bold", va="bottom")
        meta.append({"id": cid, "title": title, "dataset": r.dataset, "channel_0based": int(r.channel),
                     "recording_id": int(r.rid), "start_idx": int(r.start_idx), "end_idx": int(r.end_idx),
                     "hours": hours, "species": sp, "bar_mv": bar})
    pd.DataFrame(meta).to_csv(os.path.join(S.DATA, "thumbnails.csv"), index=False)
    S.save(fig, "train_thumbnails")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "candidates"
    globals()[stage]()
