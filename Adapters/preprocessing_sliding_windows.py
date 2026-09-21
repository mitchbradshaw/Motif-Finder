"""
preprocessing_sliding_windows.py
==================================
Signal → WindowSet: fixed-length windows with a **train-safe split** (spec
§6.7 "01 Sliding windows", §6.9, P12).

No features are computed here — that is `preprocessing.window_matrix`'s job
and a later feature block's. What this block owns is the geometry and the
leakage guards the core must enforce, not a page:

* `gap_s >= window_s` — the gap between consecutive windows must be at least
  one window length so no two windows share samples across a split boundary
  (P12). A smaller gap is refused with the reason; `gap_s = 0` means
  "exactly one window length" (windows tile the span).
* `split_rule = blocked_by_time` — the span is cut into `n_blocks`
  contiguous blocks and whole blocks are assigned to train / validation /
  test by `holdout_frac` (the last block(s) hold out); `random` is allowed
  only when `allow_random_split` is set, because a random split leaks
  autocorrelated neighbours (backlog B7).

`starts` are **channel-absolute** (the WindowSet convention, see
`Working/types/windowset.py`): the span's offset is recovered from `t[0] * fs`
exactly as `preprocessing.window_matrix` does, so the two producers agree and
the bridge can draw the windows on the channel's time axis.

The split rides on the WindowSet as a `split` column of its feature table
(`0 = train, 1 = validation, 2 = test`) so it survives the step cache and
"Save window set" (P18); `catalogue.cluster` and `catalogue.classifier`
drop that column before treating the table as features.
"""

import numpy as np
import pandas as pd

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import WindowSet

SPLIT_COLUMN = "split"
SPLIT_NAMES = ("train", "validation", "test")


def plan_windows(n_samples, fs, window_s, gap_s=0.0):
    """Window starts for a span, honouring `gap >= window` (P12)."""
    length = int(round(window_s * fs))
    if length < 2:
        raise ValueError(f"window_s={window_s} at fs={fs} is {length} sample(s); a window needs at least 2.")
    gap = int(round(gap_s * fs)) if gap_s and gap_s > 0 else length
    if gap < length:
        raise ValueError(
            f"gap_s={gap_s} s is shorter than the window ({window_s} s): consecutive windows would share "
            f"samples and a split could leak (P12). Use gap_s >= window_s, or 0 for exactly one window length.")
    starts = np.arange(0, n_samples - length + 1, gap, dtype=np.int64)
    if len(starts) == 0:
        raise ValueError(
            f"no window fits: the span has {n_samples} samples and one window is {length} ({window_s} s at {fs} Hz); "
            f"shorten window_s or widen the span.")
    return starts, length, gap


def assign_split(starts, n_samples, rule="blocked_by_time", n_blocks=5, holdout_frac=0.2,
                 validation_frac=0.0, seed=0):
    """One split label per window (0 train, 1 validation, 2 test)."""
    n = len(starts)
    labels = np.zeros(n, dtype=np.int64)
    if n == 0:
        return labels, []
    if rule == "blocked_by_time":
        n_blocks = max(1, int(n_blocks))
        edges = np.linspace(0, n_samples, n_blocks + 1)
        block = np.clip(np.searchsorted(edges, starts, side="right") - 1, 0, n_blocks - 1)
        n_test = int(round(n_blocks * holdout_frac))
        n_val = int(round(n_blocks * validation_frac))
        # the LAST blocks are held out, whole blocks only: a window is never split across roles
        test_blocks = set(range(n_blocks - n_test, n_blocks)) if n_test else set()
        val_blocks = set(range(n_blocks - n_test - n_val, n_blocks - n_test)) if n_val else set()
        for i, b in enumerate(block):
            labels[i] = 2 if b in test_blocks else 1 if b in val_blocks else 0
        blocks = [{"index": int(b), "start": int(edges[b]), "end": int(edges[b + 1]),
                   "role": SPLIT_NAMES[2] if b in test_blocks else SPLIT_NAMES[1] if b in val_blocks else SPLIT_NAMES[0],
                   "n_windows": int((block == b).sum())} for b in range(n_blocks)]
        return labels, blocks
    if rule == "random":
        rng = np.random.default_rng(int(seed))
        u = rng.random(n)
        labels[u < holdout_frac] = 2
        labels[(u >= holdout_frac) & (u < holdout_frac + validation_frac)] = 1
        return labels, []
    raise ValueError(f"unknown split_rule {rule!r}; use blocked_by_time or random")


def spacing_check(starts, length):
    """Min gap between consecutive windows and whether it is >= one window (P12)."""
    if len(starts) < 2:
        return {"min_gap": None, "train_safe": True}
    gaps = np.diff(np.asarray(starts))
    return {"min_gap": int(gaps.min()), "train_safe": bool(gaps.min() >= length)}


def _run(x, t, fs, window_s=600.0, gap_s=0.0, split_rule="blocked_by_time", n_blocks=5,
         holdout_frac=0.2, validation_frac=0.0, allow_random_split=False, seed=0):
    if split_rule == "random" and not allow_random_split:
        raise ValueError(
            "split_rule='random' leaks autocorrelated neighbours between train and test (B7/P12); "
            "use blocked_by_time, or set allow_random_split=True to accept that explicitly.")
    x = np.asarray(x)
    starts, length, gap = plan_windows(len(x), fs, window_s, gap_s)
    labels, blocks = assign_split(starts, len(x), split_rule, n_blocks, holdout_frac, validation_frac, seed)
    check = spacing_check(starts, length)
    span_start = int(round(float(t[0]) * fs)) if t is not None and len(t) else 0
    ws = WindowSet(starts=starts + span_start, length=length, fs=float(fs),
                   features=pd.DataFrame({SPLIT_COLUMN: labels}))
    counts = {name: int((labels == i).sum()) for i, name in enumerate(SPLIT_NAMES)}
    return AdapterResult(
        output_kind="windowset", value=ws,
        meta={"length": length, "gap": gap, "n_windows": int(len(starts)), "split_rule": split_rule, "span_start": span_start,
              "blocks": blocks, "split_counts": counts, "spacing": check, "seed": int(seed)},
    )


def _derive(x, t, fs, params):
    try:
        starts, length, gap = plan_windows(len(x), fs, params["window_s"], params["gap_s"])
    except ValueError as e:
        return [("Windows", str(e), "error")]
    labels, _ = assign_split(starts, len(x), params["split_rule"], params["n_blocks"], params["holdout_frac"],
                             params["validation_frac"], params["seed"])
    counts = {name: int((labels == i).sum()) for i, name in enumerate(SPLIT_NAMES)}
    rows = [("Windows", f"{len(starts)} × {length} samples · stride {gap}", "warn" if len(starts) < 10 else ""),
            ("Gap ≥ window", "yes" if gap >= length else "NO", "" if gap >= length else "error"),
            ("Split", " / ".join(f"{k} {v}" for k, v in counts.items()), "")]
    if params["split_rule"] == "random":
        rows.append(("Random split", "leaks neighbours (B7) — blocked_by_time is the safe rule", "warn"))
    return rows


SPEC = register(AdapterSpec(
    name="preprocessing.sliding_windows",
    display_name="Sliding windows with a blocked split (Signal -> WindowSet)",
    stage="preprocessing",
    category="cluster",
    page_name="Sliding windows",
    params=[
        ParamSpec("window_s", float, 600.0, "Window length (seconds)", min=0.01),
        ParamSpec("gap_s", float, 0.0, "Gap between window starts (seconds); must be >= window_s; 0 = one window length", min=0.0),
        ParamSpec("split_rule", str, "blocked_by_time", "How windows are assigned to train / validation / test", choices=["blocked_by_time", "random"]),
        ParamSpec("n_blocks", int, 5, "Contiguous time blocks the span is cut into (blocked_by_time)", min=1, max=1000),
        ParamSpec("holdout_frac", float, 0.2, "Fraction of blocks (or windows) held out as test", min=0.0, max=0.9),
        ParamSpec("validation_frac", float, 0.0, "Fraction held out as validation", min=0.0, max=0.9),
        ParamSpec("allow_random_split", bool, False, "Accept the leakage a random split carries (B7)"),
        ParamSpec("seed", int, 0, "Random-split seed", min=0),
    ],
    run=_run,
    derive=_derive,
    input_kind="signal",
    output_kind="windowset",
    description=(
        "Fixed-length windows over the span with a train-safe split: gap >= window "
        "(no shared samples) and whole time blocks per role. The split rides on the "
        "WindowSet's `split` column."
    ),
))
