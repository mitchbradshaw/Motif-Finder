"""
morph.py
========
Round-B B2: does a drop sequence MORPH - does the shape change gradually from
one event to the next - more than the same events would in a random order?

In plain words: think of a flip-book. Each page differs a little from the one
before, but the first and last pages can look nothing alike. So walk along a
sequence and, for each consecutive step, ask whether that step's shape change
is smaller than the change from the first event to the last. The **morph
fraction** is the share of steps for which it is. A steady morph scores 1; a
sequence of unrelated shapes scores whatever chance gives.

What decides whether a fraction is high is the **null**: the same events in a
shuffled order (seeded permutations; every order exactly once when there are
no more orders than draws). The per-sequence `p` is one-sided - how often a
shuffled order scores at least as high as the real one - because the question
is whether the real order morphs MORE than chance. `morph_summary` counts the
sequences that beat their null at p < `ALPHA`, against the number expected by
chance (the sum over the tested sequences of how often a shuffled order would
itself have reached p < `ALPHA`; at most `ALPHA` x the tested count, less
when a short sequence's null is coarse).

Rules a reader should know:

* **The distance is the Library groupings' own** - Ward's scale-invariant
  shape distance (`Working.library.grouping.methods.ward`: resample to 256
  points, z-normalise, Euclidean, divided by 2 sqrt(256) so it reads 0..1),
  the one every saved shape-distance grouping was cut on. Imported, not
  re-written.
* **Too short to test is not "failed".** Fewer than `MIN_ELEMENTS` (3) has no
  step that is not the end-to-end distance itself. A sequence and its reverse
  always score alike, so 4 elements (24 orders, every value at least twice)
  can never reach p < 0.05. Such a sequence is reported with `tested` False and
  its reason; it does not enter the beat or expected counts.
* **The readout is coarse** (found building it, 2026-10-28). A shuffled order
  also scores 1 whenever its two ends happen to be far apart in shape, so even
  a perfect, straight-line morph has a p floor of about 0.2 at 5 elements, 0.1
  at 9 and 0.05 at 20 (`tests/test_sequence_morph.py` pins it). "Not testable"
  is therefore common on short sequences, and is decided per sequence from its
  own null (`p_floor`), never from its length alone.
* **The step-size companion** (researcher, 2026-10-28) asks a related, weaker
  question that short sequences can answer: are neighbouring events more alike
  than random pairs of the same events? A steady morph passes it, but so does
  persistence (runs of near-identical events, AAABBB), and it does not tell the
  two apart. Sequences built from label chains can pass it by construction.
  Its p and the fraction's p come from the same orders, so they are not
  independent evidence. The **mean step** is the mean shape
  distance between consecutive elements. It is read against the same shuffled
  orders, with a one-sided `p` (how often a shuffled order takes steps at
  least as small) and a `ratio` (mean step / shuffled mean; below 1 means
  smoother than shuffled). A sequence and its reverse take the same steps, so
  its floor is 2/k! with exact enumeration: five elements can be judged, four
  cannot. Each row's `steps` holds it, with its own `tested`.
* **A flat element** (constant waveform) z-normalises to zeros and would read
  as a shape; the sequence is not scored and its note says which element.
* An empty waveform is a caller's bug and raises.

Headless: `sequence_morph(conn, ...)` reads stored sequences off the database
(the thesis calls it directly); the web bridge hands it the same decimated
waveform its groupings were fitted on. No UI library (CLAUDE.md rule 1).
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from scipy.spatial.distance import squareform

from Working.library.grouping.methods.ward import RESAMPLE_LENGTH, condensed_distances, shape_vectors

#: The significance level of the summary's count.
ALPHA = 0.05
#: Seeded shuffles per sequence (or every order, when there are fewer).
MORPH_DRAWS = 1000
MORPH_SEED = 2026
#: Fewer elements have no step that is not the end-to-end distance itself.
MIN_ELEMENTS = 3

DISTANCE_WORDS = (f"the Library groupings' shape distance (Ward's): each element resampled to {RESAMPLE_LENGTH} "
                  f"points, z-normalised, Euclidean, divided by 2 sqrt({RESAMPLE_LENGTH}) so it reads 0 to 1")
RULE_WORDS = ("morph fraction = the share of consecutive steps whose shape distance is smaller than the distance "
              "from the first element to the last; 1 = a steady morph. Null: the same elements in shuffled order "
              "(seeded; every order once when there are fewer orders than draws), one-sided p = how often a shuffled "
              "order scores at least as high. The readout is coarse: a shuffled order also scores 1 whenever its "
              "ends happen to lie far apart, so even a perfect morph's p cannot go below about 0.1 at 9 elements "
              "and about 0.05 at 20; a sequence whose null cannot reach p < 0.05 is reported as not testable.")
STEP_RULE_WORDS = ("mean step = the mean shape distance between consecutive elements; ratio = mean step / the "
                   "shuffled orders' mean (below 1 = neighbouring events more alike than random pairs: persistence or "
                   "gradual change - it does not tell the two apart). Null: the same "
                   "shuffled orders as the fraction; one-sided p = how often a shuffled order takes steps at least as "
                   "small. A sequence and its reverse take the same steps, so the floor is 2/k! when every order is "
                   "enumerated: five elements can be judged, four cannot.")


def shape_distances(waveforms) -> np.ndarray:
    """The square matrix of the groupings' shape distance between waveforms."""
    ws = [np.asarray(w, dtype=float).ravel() for w in waveforms]
    for i, w in enumerate(ws):
        if w.size == 0:
            raise ValueError(f"morph: element {i + 1} has an empty waveform; nothing to compare.")
        if not np.all(np.isfinite(w)):
            raise ValueError(f"morph: element {i + 1} holds NaN or inf; refusing to measure it.")
    if len(ws) < 2:
        return np.zeros((len(ws), len(ws)))
    return squareform(condensed_distances(shape_vectors(ws)))


def _fractions(d, orders) -> np.ndarray:
    """Morph fraction of every row of `orders` (`(m, k)` index arrays)."""
    o = np.asarray(orders, dtype=int)
    steps = d[o[:, :-1], o[:, 1:]]
    ends = d[o[:, 0], o[:, -1]]
    return (steps < ends[:, None]).mean(axis=1)


def morph_fraction(d, order=None) -> float:
    """The share of consecutive steps (in `order`, default as given) whose
    distance in the square matrix `d` is smaller than first-to-last."""
    d = np.asarray(d, dtype=float)
    k = d.shape[0]
    o = np.arange(k) if order is None else np.asarray(order, dtype=int)
    return float(_fractions(d, o[None, :])[0])


def _mean_steps(d, orders) -> np.ndarray:
    """Mean consecutive-step distance of every row of `orders` (`(m, k)` index arrays)."""
    o = np.asarray(orders, dtype=int)
    return d[o[:, :-1], o[:, 1:]].mean(axis=1)


def mean_step(d, order=None) -> float:
    """The mean distance in the square matrix `d` between consecutive elements
    (in `order`, default as given)."""
    d = np.asarray(d, dtype=float)
    o = np.arange(d.shape[0]) if order is None else np.asarray(order, dtype=int)
    return float(_mean_steps(d, o[None, :])[0])


def _p_ge(null, v, exact):
    """One-sided p of value(s) `v` against `null`: share at least as high
    (exact enumeration: the identity is among them), +1 corrected otherwise."""
    srt = np.sort(null)
    ge = null.size - np.searchsorted(srt, np.asarray(v) - 1e-12, side="left")
    return ge / null.size if exact else (1 + ge) / (null.size + 1)


def _p_le(null, v, exact):
    """One-sided p of value(s) `v` against `null`: share at most as low (smaller
    steps), exact or +1 corrected as `_p_ge`."""
    srt = np.sort(null)
    le = np.searchsorted(srt, np.asarray(v) + 1e-12, side="right")
    return le / null.size if exact else (1 + le) / (null.size + 1)


def _step_readout(d, orders, exact, alpha) -> dict:
    """The step-size companion of one scored sequence, on the fraction's own orders."""
    k = d.shape[0]
    null = _mean_steps(d, orders)
    step = mean_step(d)
    p = float(_p_le(null, step, exact))
    p_floor = float(_p_le(null, null.min(), exact))
    tested = p_floor < alpha
    null_mean = float(null.mean())
    lo, hi = np.percentile(null, [2.5, 97.5])
    note = None
    if not tested:
        note = (f"{k} elements: the smallest p its {null.size} {'orders' if exact else 'shuffles'} allow is "
                f"{p_floor:.3g} (a sequence and its reverse take the same steps), so it cannot beat its null at "
                f"p < {alpha:g}")
    return {"mean_step": step, "null_mean": null_mean, "ratio": step / null_mean if null_mean > 0 else None,
            "lo": float(lo), "hi": float(hi), "p": p, "p_floor": p_floor,
            "chance_rate": float(np.mean(_p_le(null, null, exact) < alpha)) if tested else 0.0,
            "tested": bool(tested), "note": note}


def morph_readout(waveforms, n_draws=MORPH_DRAWS, seed=MORPH_SEED, alpha=ALPHA) -> dict:
    """One sequence's morph fraction against its shuffled-order null.

    Returns `{n_elements, n_steps, fraction, null_mean, lo, hi, p, p_floor,
    chance_rate, n_draws, exact, tested, note}`: `lo`..`hi` is the null's
    2.5-97.5 % band, `p_floor` the smallest p this sequence's null allows,
    `chance_rate` the probability under the null of p < `alpha` (what the
    summary's expected count adds up). Not scored (`fraction` None) below
    `MIN_ELEMENTS` or with a flat element; `tested` False whenever it could not
    beat its null at `alpha`, with `note` saying why. `steps` is the step-size
    companion on the same orders (`{mean_step, null_mean, ratio, lo, hi, p,
    p_floor, chance_rate, tested, note}`), None when the sequence is not scored."""
    ws = [np.asarray(w, dtype=float).ravel() for w in waveforms]
    k = len(ws)
    base = {"n_elements": k, "n_steps": max(0, k - 1), "fraction": None, "null_mean": None, "lo": None, "hi": None,
            "p": None, "p_floor": None, "chance_rate": 0.0, "n_draws": 0, "exact": False, "tested": False,
            "note": None, "alpha": alpha, "steps": None}
    d = shape_distances(ws)                         # raises on an empty / non-finite element
    if k < MIN_ELEMENTS:
        base["note"] = (f"{k} element{'s' if k != 1 else ''}: the only step is the end-to-end distance itself, "
                        f"so there is nothing to compare (needs {MIN_ELEMENTS})")
        return base
    flat = [i + 1 for i, w in enumerate(ws) if np.ptp(w) == 0]
    if flat:
        base["note"] = (f"element{'s' if len(flat) > 1 else ''} {', '.join(map(str, flat))} "
                        f"{'are' if len(flat) > 1 else 'is'} flat (a constant waveform has no shape); not scored")
        return base

    fraction = morph_fraction(d)
    exact = math.factorial(k) <= int(n_draws)
    if exact:
        orders = np.array(list(itertools.permutations(range(k))), dtype=int)
    else:
        rng = np.random.default_rng(int(seed))
        orders = rng.permuted(np.broadcast_to(np.arange(k), (int(n_draws), k)), axis=1)
    null = _fractions(d, orders)
    p = float(_p_ge(null, fraction, exact))
    p_floor = float(_p_ge(null, null.max(), exact))
    chance = float(np.mean(_p_ge(null, null, exact) < alpha))
    lo, hi = np.percentile(null, [2.5, 97.5])
    tested = p_floor < alpha
    note = None
    if not tested:
        note = (f"{k} elements: the smallest p its {null.size} {'orders' if exact else 'shuffles'} allow is "
                f"{p_floor:.3g} (a shuffled order scores as high whenever its ends lie far apart in shape), so it "
                f"cannot beat its null at p < {alpha:g}")
    base.update({"fraction": fraction, "null_mean": float(null.mean()), "lo": float(lo), "hi": float(hi), "p": p,
                 "p_floor": p_floor, "chance_rate": chance if tested else 0.0, "n_draws": int(null.size),
                 "exact": bool(exact), "tested": bool(tested), "note": note,
                 "steps": _step_readout(d, orders, exact, alpha)})
    return base


def morph_summary(rows, alpha=ALPHA) -> dict:
    """`{n_sequences, n_scored, n_tested, n_beat, expected, alpha, words}` over
    per-sequence readouts: how many beat their null at p < alpha, against the
    number expected by chance (the sum of the tested sequences' chance rates)."""
    rows = list(rows)
    scored = [r for r in rows if r.get("fraction") is not None]
    tested = [r for r in scored if r.get("tested")]
    beat = [r for r in tested if r["p"] is not None and r["p"] < alpha]
    expected = float(sum(r.get("chance_rate") or 0.0 for r in tested))
    words = (f"{len(beat)} of {len(tested)} testable sequences morph more than their shuffled order at p < {alpha:g}; "
             f"about {expected:.1f} expected by chance")
    if len(rows) > len(tested):
        words += (f" ({len(rows) - len(tested)} of {len(rows)} not testable: too short, or an element flat or "
                  f"without a waveform)")
    st_tested = [r for r in scored if (r.get("steps") or {}).get("tested")]
    st_beat = [r for r in st_tested if r["steps"]["p"] is not None and r["steps"]["p"] < alpha]
    st_expected = float(sum(r["steps"].get("chance_rate") or 0.0 for r in st_tested))
    st_words = (f"step size: {len(st_beat)} of {len(st_tested)} testable sequences take smaller steps than their "
                f"shuffled order at p < {alpha:g}; about {st_expected:.1f} expected by chance")
    if len(rows) > len(st_tested):
        st_words += (f" ({len(rows) - len(st_tested)} of {len(rows)} not testable: under five elements, a null that "
                     f"cannot reach p < {alpha:g}, or not scored)")
    return {"n_sequences": len(rows), "n_scored": len(scored), "n_tested": len(tested), "n_beat": len(beat),
            "expected": expected, "alpha": alpha, "words": words,
            "steps": {"n_tested": len(st_tested), "n_beat": len(st_beat), "expected": st_expected, "words": st_words}}


# ── headless: stored sequences ──────────────────────────────────────────────

def stored_waveform(conn):
    """A `waveform_of(recording_id, start_idx, end_idx)` reading the STORED
    samples off each recording's npy; None for a recording not on disk, a
    soft-unregistered one (`recordings.active = 0`, offered nowhere in the
    Library), or the held-out one while its lock is on. (The bridge hands the decimated envelope
    its groupings were fitted on instead; for a span of at most 128 samples
    the two are the same samples.)"""
    from Working.hpc.job_export import REPO_ROOT
    from Working.registration.settings import HELD_OUT_FILE, held_out_locked
    import os

    locked = held_out_locked(conn)
    rows = {int(r[0]): (r[1], r[2]) for r in conn.execute(
        "SELECT id, source_file, npy_path FROM recordings WHERE COALESCE(active, 1) != 0")}
    cache = {}

    def waveform_of(recording_id, start_idx, end_idx):
        src, path = rows.get(int(recording_id), (None, None))
        if src == HELD_OUT_FILE and locked:
            return None
        # npy_path is stored relative to the repo root; read it as chain_job._resolve_npy does
        path = next((c for c in (path, os.path.join(REPO_ROOT, path or "")) if path and os.path.isfile(c)), None)
        if path is None:
            return None
        if path not in cache:
            cache[path] = np.load(path, mmap_mode="r")
        return np.array(cache[path][int(start_idx):int(end_idx)], dtype=float)
    return waveform_of


def sequence_morph(conn, sequence_ids=None, *, waveform_of=None, n_draws=MORPH_DRAWS, seed=MORPH_SEED,
                   alpha=ALPHA, grouping_id=None) -> dict:
    """`{rows, summary, distance, rule}` for stored sequences (every one when
    `sequence_ids` is None). Each row is `morph_readout`'s plus `sequence_id`,
    `recording_id` and `labels`; an element with no waveform (None from
    `waveform_of`) leaves its sequence unscored, said in its note. Each
    sequence's shuffles are seeded `seed + sequence_id`, so a row does not
    change when another sequence is added."""
    from Working.library import sequences as seq_mod

    if sequence_ids is None:
        sequence_ids = [int(r[0]) for r in conn.execute("SELECT id FROM sequences ORDER BY id")]
    load = waveform_of or stored_waveform(conn)
    rows = []
    for s in seq_mod.read_sequences(conn, sequence_ids, grouping_id=grouping_id):
        head = {"sequence_id": s.sequence_id, "recording_id": s.recording_id, "labels": list(s.labels)}
        ws = [load(s.recording_id, e.start_idx, e.end_idx) for e in s.elements]
        missing = [i + 1 for i, w in enumerate(ws) if w is None or len(w) == 0]
        if missing:
            r = {**morph_readout([], n_draws=0, alpha=alpha), "n_elements": len(ws), "n_steps": max(0, len(ws) - 1),
                 "note": f"no waveform for element{'s' if len(missing) > 1 else ''} "
                         f"{', '.join(map(str, missing[:5]))}{'…' if len(missing) > 5 else ''} "
                         f"(its recording is unregistered, held out, or not on disk); not scored"}
        else:
            r = morph_readout(ws, n_draws=n_draws, seed=int(seed) + int(s.sequence_id or 0), alpha=alpha)
        rows.append({**head, **r})
    return {"rows": rows, "summary": morph_summary(rows, alpha), "distance": DISTANCE_WORDS, "rule": RULE_WORDS,
            "step_rule": STEP_RULE_WORDS}
