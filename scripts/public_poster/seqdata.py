"""Public poster: the drop trains (sequences) - their drops, their traces, and the CH14 thin/wide split.

Drops come from the NeurIPS session's 23 Nov sequence table (`docs/library_analysis/20261123_plots/
sequence_events.csv`: every drop of at least 15x the local noise, found by the whole-drop rule), read-only. The CH14
split follows that session's 24 Nov method exactly (its own helpers are imported): a drop is big or small against its
local level (the geometric mean of the 21 drops round it, because the train deepens two-fold over 90 h), and the
big ones are thin or wide against their local width, each cut where a two-group mixture's posterior crosses.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/seqdata.py
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

LIB = os.path.join(S.ROOT, "docs", "library_analysis", "20261123_plots")
CH14 = 254
SHUFFLES = 4000
BLOCK = 10


def dp_module():
    sys.path.insert(0, os.path.join(S.ROOT, "scripts", "library_analysis"))
    import drop_plots_20261123 as dp
    return dp


_DP = None
_RECS = None


def dp():
    global _DP, _RECS
    if _DP is None:
        _DP = dp_module()
        _RECS = _DP.recordings(sqlite3.connect(f"file:{_DP.DB}?mode=ro", uri=True))
    return _DP


def recs():
    dp()
    return _RECS


def tables():
    se = pd.read_csv(os.path.join(LIB, "sequence_events.csv"))
    sq = pd.read_csv(os.path.join(LIB, "sequences.csv")).set_index("sequence_id")
    return se, sq


def drops(sid):
    se, sq = tables()
    d = se[se["sequence_id"] == sid].sort_values("t_s").reset_index(drop=True)
    return d, sq.loc[sid]


def trace(rid, a, b, step=1):
    """mV samples [a, b) of recording `rid` (every `step`-th block mean), and their sample indices."""
    D = dp()
    x = D.channel(recs(), rid)
    a, b = max(0, int(a)), min(len(x), int(b))
    seg = np.asarray(x[a:b], dtype=float) * D.to_mv(recs()[rid]["units"])
    idx = np.arange(a, b)
    if step > 1:
        n = len(seg) // step * step
        seg = np.nanmean(seg[:n].reshape(-1, step), axis=1)
        idx = idx[:n].reshape(-1, step)[:, 0]
    return idx, seg


def ch14_kinds():
    """The CH14 train's two kinds of big drop, as the NeurIPS session found them (README of 23-24 Nov): its
    mixture model on depth and width (`kinds_of`) gives four kinds; the two big ones are thin (C) and wide (D).
    Switching is tested on the big drops in train order, against shuffles that move each drop only within its block
    of 10 (so the slow deepening cannot fake it), and against a full shuffle."""
    D = dp()
    d, m = drops(CH14)
    d = D.events_only(d).reset_index(drop=True)
    lab, k, _ = D.kinds_of(d)
    assert k == 4, f"expected four kinds on CH14, got {k}"
    d["kind"] = lab
    big = d[np.isin(lab, [2, 3])].reset_index(drop=True)
    L = (big["kind"] == 3).to_numpy().astype(int)            # 1 = wide
    big["wide"] = L
    rng = np.random.default_rng(20261125)
    keys = (np.arange(len(L)) // BLOCK).astype(float)

    def stats(p):
        prev, nxt = p[:-1], p[1:]
        return np.array([np.mean(nxt[prev == 1] == 0), np.mean(nxt[prev == 0] == 1), np.mean(prev != nxt),
                         np.mean(nxt[prev == 1] == 1), np.mean(nxt[prev == 0] == 0)])
    obs = stats(L)
    null = np.array([stats(L[np.argsort(keys + rng.random(len(L)), kind="stable")]) for _ in range(SHUFFLES)])
    full = np.array([stats(rng.permutation(L)) for _ in range(SHUFFLES)])
    out = {
        "drops_all": int(len(d)), "big": int(len(big)), "thin": int((L == 0).sum()), "wide": int((L == 1).sum()),
        "p_thin_after_wide": float(obs[0]), "p_thin_after_wide_block_null": float(null[:, 0].mean()),
        "p_thin_after_wide_full_null": float(full[:, 0].mean()),
        "p_value_thin_after_wide": float((np.sum(null[:, 0] >= obs[0]) + 1) / (SHUFFLES + 1)),
        "p_wide_after_thin": float(obs[1]), "p_wide_after_thin_block_null": float(null[:, 1].mean()),
        "switch": float(obs[2]), "switch_block_null": float(null[:, 2].mean()),
        "p_value_switch": float((np.sum(null[:, 2] >= obs[2]) + 1) / (SHUFFLES + 1)),
        "wide_wide_ratio": float(obs[3] / null[:, 3].mean()), "thin_thin_ratio": float(obs[4] / null[:, 4].mean()),
        "thin_depth_mv": float(big.loc[L == 0, "depth_mv"].median()),
        "wide_depth_mv": float(big.loc[L == 1, "depth_mv"].median()),
        "thin_width_s": float(big.loc[L == 0, "width_s"].median()),
        "wide_width_s": float(big.loc[L == 1, "width_s"].median()),
        "hours": float(m["duration_h"]), "recording_id": int(m["recording_id"]), "start_idx": int(m["start_idx"]),
        "fs": float(m["fs"]),
    }
    d.to_csv(os.path.join(S.DATA, "ch14_all_drops.csv"), index=False)
    big.to_csv(os.path.join(S.DATA, "ch14_big_drops.csv"), index=False)
    with open(os.path.join(S.DATA, "ch14_kinds.json"), "w") as f:
        json.dump(out, f, indent=1)
    return big, out


if __name__ == "__main__":
    os.makedirs(S.DATA, exist_ok=True)
    big, out = ch14_kinds()
    print(json.dumps(out, indent=1))
