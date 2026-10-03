"""
windows.py
==========
The windows a paired training job is trained and examined on: ONE set pooled
across the channels of one recording (fixup-ab, `QUESTIONS.md` Q42 / Q-W2).

What a pooled set is
--------------------
For every channel, the windows of the labels' own grid (600 samples on a
200-sample stride, `AA`) are labelled by `catalogue.manual_labels`' rule
(containment, Q41) and thinned to a non-overlapping set, labelled windows
first (Q-W1 revised). The set keeps the LABELLED windows: both arms are trained
on "the windows labelled in every arm" (spec §7b.1), and a cluster arm labels
every window it clusters, so the intersection is the human-labelled windows.
That also bounds the clustering: Ward over every window of sixteen 30-day
channels would need a pairwise matrix of tens of gigabytes.

The split
---------
Blocked by time WITHIN each training channel (spec §7b.1 step 4): the channel
is cut into `n_blocks` equal blocks, the last `test_frac` of them are the test
block (exam (i), "a later time block"), the `validation_frac` before them the
validation block (calibration), the rest train. Whole blocks only, never a
random sample of windows — neighbouring windows of a slow signal are
near-copies, and a random split would put near-copies of test windows into
training. Between two roles there is a GAP of at least `gap_windows` window
lengths: the first windows of a later role that sit closer than that to the
last window of the role before are dropped and counted (`role = "gap"`).

Channels named as `exam_channels` are never trained on: every labelled window
on them is exam (ii), "channels never trained on — the same mushroom".

The guards (each raises; none is a warning)
-------------------------------------------
* the held-out recording (`Working.config.HELD_OUT_RECORDING_FILE`) is refused
  EVEN WHEN `HELD_OUT_UNLOCK` is set: exam (iii) is a locked slot, and its
  unlock is the researcher's act on the freeze day, never this module's;
* a split that is not blocked by time, or a gap below one window;
* features derived from a model trained on the human labels (the window
  matrix's `cnn` and `rf` stages): a feature that already encodes the labels
  makes any arm look good;
* `M2_aug_concat_fs1` and `_fs2` — one recording at two sample rates — on
  opposite sides of a split (`check_leakage`).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from Working.recipes import recipe_hash

DEFAULT_LENGTH = 600
DEFAULT_GRID = 200
DEFAULT_STAGES = ("catch22", "fast_entropy")
DEFAULT_SPLIT = {"rule": "blocked_by_time", "n_blocks": 10, "test_frac": 0.2,
                 "validation_frac": 0.1, "gap_windows": 1}

ROLES = ("train", "validation", "test", "exam")
# the window-matrix stages computed by a model already trained on the human
# labels: as features they would leak the labels into both arms
LABEL_DERIVED_STAGES = ("cnn", "rf")

TABLE_COLUMNS = ("recording_id", "channel", "start", "label", "seed", "role", "block")


class HeldOutRefused(PermissionError):
    """The held-out recording was asked for. Nothing in `Working/training/`
    reads it; exam (iii) is a slot that stays locked."""


class LeakageRefused(ValueError):
    """Two files of one recording would sit on opposite sides of a split."""


# ── guards ──────────────────────────────────────────────────────────────────

def refuse_held_out(source_file):
    from Working import config
    if str(source_file) == config.HELD_OUT_RECORDING_FILE:
        raise HeldOutRefused(
            f"{source_file} is the held-out recording (exam iii). The paired training job never reads it, "
            "unlocked or not: its one run is the researcher's act after the freeze, from Settings › Datasets.")


_RATE_SUFFIX = re.compile(r"_fs\d+(?=\.mat$|$)", re.IGNORECASE)


def recording_identity(source_file):
    """The underlying recording a file holds: `M2_aug_concat_fs1.mat` and
    `M2_aug_concat_fs2.mat` are one recording at two sample rates (PRD,
    "Evaluation protection")."""
    return _RATE_SUFFIX.sub("", os.path.basename(str(source_file)))


def check_leakage(train_files, test_files):
    """Refuse two DIFFERENT files of one recording on opposite sides of a split."""
    for a in train_files:
        for b in test_files:
            if a != b and recording_identity(a) == recording_identity(b):
                raise LeakageRefused(
                    f"{a} (train) and {b} (test) are the same recording at two sample rates; "
                    "they must never be split across training and test.")


def check_split(split):
    split = dict(split or {})
    rule = split.get("rule", "blocked_by_time")
    if rule != "blocked_by_time":
        raise ValueError(
            f"split rule {rule!r} is refused: a random split puts near-copies of test windows into training "
            "(neighbouring windows of a slow signal). The split is blocked by time within each channel.")
    if int(split.get("gap_windows", 1)) < 1:
        raise ValueError("the gap between train and test must be at least one window")
    return split


def check_stages(stages):
    bad = [s for s in stages if s in LABEL_DERIVED_STAGES]
    if bad:
        raise ValueError(
            f"feature stage(s) {', '.join(bad)} are label-derived — computed by a model trained on the human "
            "labels — and would leak the labels into both arms. Label-derived features stay off.")
    if not stages:
        raise ValueError("no feature stages: a window set needs at least one measure per window")
    return tuple(stages)


# ── geometry ────────────────────────────────────────────────────────────────

def grid_starts(n_samples, length=DEFAULT_LENGTH, grid=DEFAULT_GRID):
    """Every window start on the labels' grid that admits a whole window."""
    n_samples, length, grid = int(n_samples), int(length), int(grid)
    if n_samples < length:
        return np.zeros(0, dtype=np.int64)
    return np.arange(0, n_samples - length + 1, grid, dtype=np.int64)


@dataclass
class SplitResult:
    roles: np.ndarray          # 'train' | 'validation' | 'test' | 'gap' per window
    block: np.ndarray          # block index per window
    blocks: list = field(default_factory=list)


def blocked_split(starts, length, n_samples, n_blocks=10, test_frac=0.2, validation_frac=0.0, gap_windows=1):
    """One role per window, blocked by time, with the gap enforced (module docstring)."""
    if int(gap_windows) < 1:
        raise ValueError("the gap between train and test must be at least one window (gap_windows >= 1)")
    starts = np.asarray(starts, dtype=np.int64)
    n_blocks = max(1, int(n_blocks))
    n_test = int(round(n_blocks * float(test_frac)))
    if float(test_frac) > 0 and n_test == 0:
        n_test = 1
    n_val = int(round(n_blocks * float(validation_frac)))
    if n_test + n_val >= n_blocks:
        raise ValueError(f"{n_test} test + {n_val} validation block(s) of {n_blocks} leave nothing to train on")
    edges = np.linspace(0, int(n_samples), n_blocks + 1)
    block = np.clip(np.searchsorted(edges, starts, side="right") - 1, 0, n_blocks - 1).astype(np.int64)
    block_role = ["train"] * n_blocks
    for b in range(n_blocks - n_test - n_val, n_blocks - n_test):
        block_role[b] = "validation"
    for b in range(n_blocks - n_test, n_blocks):
        block_role[b] = "test"
    roles = np.array([block_role[b] for b in block], dtype=object)

    gap = int(gap_windows) * int(length)
    last_start, last_role = None, None
    for i in np.argsort(starts, kind="stable"):
        r = roles[i]
        if last_role is not None and r != last_role and int(starts[i]) - (last_start + int(length)) < gap:
            roles[i] = "gap"
            continue
        last_start, last_role = int(starts[i]), r
    blocks = [{"index": b, "start": int(edges[b]), "end": int(edges[b + 1]), "role": block_role[b],
               "n_windows": int(((block == b) & (roles != "gap")).sum()),
               "n_gap": int(((block == b) & (roles == "gap")).sum())} for b in range(n_blocks)]
    return SplitResult(roles=roles.astype(str), block=block, blocks=blocks)


# ── the pooled set ──────────────────────────────────────────────────────────

@dataclass
class PooledSet:
    """`table`: one row per window (`TABLE_COLUMNS`), row order = window id.
    `features`: one row per window, the window-matrix measures. `meta`: the
    geometry, split, stages and per-channel counts the set was built with."""
    table: pd.DataFrame
    features: pd.DataFrame
    meta: dict

    @property
    def key(self):
        """The set's content identity: its windows, labels and roles and how it was made.
        Feature values follow deterministically from the windows and stages."""
        t = self.table
        return recipe_hash({
            "how": {k: self.meta.get(k) for k in ("source_file", "channels", "exam_channels", "length",
                                                    "grid", "split", "stages", "non_overlap_rule")},
            "windows": [t[c].astype(str).tolist() for c in TABLE_COLUMNS],
            "columns": list(self.features.columns),
        })[:16]

    def role_mask(self, *roles):
        return self.table["role"].isin(roles).to_numpy()

    def save(self, d):
        os.makedirs(d, exist_ok=True)
        t = self.table
        np.savez_compressed(
            os.path.join(d, "pooled_windows.npz"),
            **{c: (t[c].to_numpy().astype(str) if c == "role" else t[c].to_numpy().astype(np.int64))
               for c in TABLE_COLUMNS})
        self.features.reset_index(drop=True).to_parquet(os.path.join(d, "features.parquet"))
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"kind": "pooled_window_set", "key": self.key, **self.meta}, f, indent=2, default=str)
        return d

    @classmethod
    def load(cls, d):
        with np.load(os.path.join(d, "pooled_windows.npz"), allow_pickle=False) as z:
            table = pd.DataFrame({c: (z[c].astype(str) if c == "role" else z[c].astype(np.int64))
                                  for c in TABLE_COLUMNS})
        table["seed"] = table["seed"].astype(bool)
        features = pd.read_parquet(os.path.join(d, "features.parquet"))
        with open(os.path.join(d, "manifest.json"), encoding="utf-8") as f:
            meta = json.load(f)
        saved_key = meta.pop("key", None)
        meta.pop("kind", None)
        out = cls(table=table, features=features, meta=meta)
        if saved_key is not None and saved_key != out.key:
            raise ValueError(f"the pooled window set at {d} does not match its own key ({saved_key} on disk, "
                             f"{out.key} recomputed): its files were changed after it was saved")
        return out


def _recording(conn, source_file, channel):
    row = conn.execute("SELECT * FROM recordings WHERE source_file = ? AND channel = ?",
                       (str(source_file), int(channel))).fetchone()
    if row is None:
        raise ValueError(f"no recording {source_file} channel {channel} in this database")
    return {k: row[k] for k in row.keys()}


def build_pooled_set(conn, source_file, channels, exam_channels=(), *, length=DEFAULT_LENGTH, grid=DEFAULT_GRID,
                     split=None, stages=DEFAULT_STAGES, progress=None, cancel=None):
    """Label, thin, split and measure the windows of `channels` (trained on, split by
    time) and `exam_channels` (never trained on) of one recording."""
    from Adapters.catalogue_manual_labels import NON_OVERLAP_RULE, human_spans, label_windows
    from Working.Preprocessing.window_matrix.build import features_at

    refuse_held_out(source_file)
    split = check_split({**DEFAULT_SPLIT, **(split or {})})
    stages = check_stages(tuple(stages))
    channels = [int(c) for c in channels]
    exam_channels = [int(c) for c in exam_channels]
    if not channels:
        raise ValueError("a paired training set needs at least one training channel")
    overlap = sorted(set(channels) & set(exam_channels))
    if overlap:
        raise ValueError(f"channel(s) {overlap} are both trained on and an exam; an exam channel is never trained on")
    check_leakage([source_file], [source_file])

    rows, feats, per_channel = [], [], []
    columns = None
    plan = [(c, "train") for c in channels] + [(c, "exam") for c in exam_channels]
    for i, (ch, kind) in enumerate(plan):
        if cancel is not None and cancel():
            raise InterruptedError("cancelled while building the window set")
        rec = _recording(conn, source_file, ch)
        n = int(rec["n_samples"])
        starts = grid_starts(n, length, grid)
        spans = human_spans(conn, rec["id"])
        lab = label_windows(starts, length, spans, non_overlapping=True)
        keep = np.isin(lab.fate, ["interesting", "not_interesting"])
        s, y = starts[keep], lab.labels[keep]
        # `seed` is a subset of interesting (Q41): flagged, never its own class
        seed_flag = np.zeros(len(s), dtype=bool)
        for a, b, verdict, _src in spans:
            if verdict == "seed":
                seed_flag |= (s <= a) & (s + int(length) >= b) & (y == 1)
        if kind == "train":
            sp = blocked_split(s, length, n, split["n_blocks"], split["test_frac"],
                               split.get("validation_frac", 0.0), split["gap_windows"])
            roles, block, blocks = sp.roles, sp.block, sp.blocks
        else:
            roles = np.full(len(s), "exam", dtype=object).astype(str)
            block, blocks = np.full(len(s), -1, dtype=np.int64), []
        kept = roles != "gap"
        counts = {f: int(lab.counts[f]) for f in ("interesting", "not_interesting", "unlabelled", "conflicting",
                                                  "artifact", "dropped_for_overlap")}
        by_role = {r: {"interesting": int(((roles == r) & (y == 1)).sum()),
                       "not_interesting": int(((roles == r) & (y == 0)).sum())}
                   for r in (("train", "validation", "test") if kind == "train" else ("exam",))}
        per_channel.append({
            "channel": ch, "recording_id": int(rec["id"]), "kind": kind, "n_samples": n,
            "hours": round(n / float(rec["fs"]) / 3600.0, 2), "fs": float(rec["fs"]),
            "grid_windows": int(len(starts)), **counts, "dropped_for_gap": int((roles == "gap").sum()),
            "n_windows": int(kept.sum()), "by_role": by_role, "blocks": blocks,
        })
        s, y, roles, block, seed_flag = s[kept], y[kept], roles[kept], block[kept], seed_flag[kept]

        if progress is not None:
            progress(i, len(plan), f"measuring {len(s):,} windows of channel {ch}")
        x = np.load(rec["npy_path"], mmap_mode="r")
        values, computed, columns = features_at(
            x, s, length, stages, should_cancel=cancel,
            on_progress=(None if progress is None else
                         (lambda d, t, st, _i=i, _ch=ch: progress(_i, len(plan), f"channel {_ch} · {st} {d:,}/{t:,}"))))
        feats.append(values.astype(np.float64))
        rows.append(pd.DataFrame({"recording_id": int(rec["id"]), "channel": ch, "start": s.astype(np.int64),
                                  "label": y.astype(np.int64), "seed": seed_flag, "role": roles.astype(str),
                                  "block": block.astype(np.int64)}))

    table = pd.concat(rows, ignore_index=True)[list(TABLE_COLUMNS)]
    features = pd.DataFrame(np.vstack(feats) if feats else np.zeros((0, 0)), columns=columns)
    meta = {
        "source_file": str(source_file), "channels": channels, "exam_channels": exam_channels,
        "length": int(length), "grid": int(grid), "fs": per_channel[0]["fs"], "split": split,
        "stages": list(stages), "non_overlap_rule": NON_OVERLAP_RULE,
        "pool": "labelled windows only (both arms train on the windows labelled in every arm)",
        "per_channel": per_channel,
    }
    if progress is not None:
        progress(len(plan), len(plan), f"{len(table):,} windows measured")
    return PooledSet(table=table, features=features, meta=meta)


def role_counts(pooled):
    """`{role: {interesting, not_interesting, n}}` over the whole set."""
    t = pooled.table
    out = {}
    for r in ROLES:
        m = t["role"] == r
        out[r] = {"interesting": int((m & (t["label"] == 1)).sum()),
                  "not_interesting": int((m & (t["label"] == 0)).sum()), "n": int(m.sum())}
    return out
