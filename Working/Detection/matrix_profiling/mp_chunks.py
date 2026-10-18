"""
mp_chunks.py
============
A self-join matrix profile computed in blocks, so a profile longer than a job's
wall clock can be computed in pieces, each checkpointed (round A_2, P2: "chunk
the profile: AB-joins over blocks as separate checkpointed tasks, merged by the
elementwise minimum, with indices kept").

The decomposition, over the ``l = n - m + 1`` subsequences cut into blocks of
``L`` (the last one shorter):

* **adjacent blocks p, p+1 — a self-join over their union.** It covers every
  pair inside block p, inside block p+1, and between the two, with stumpy's own
  exclusion zone (``|i - j| <= ceil(m / 4)`` is a trivial match and skipped).
  An AB-join here would be wrong: next to the block boundary it would compare a
  subsequence with its own trivial neighbours.
* **blocks two or more apart — an AB-join each way** (`stump(T_A, m, T_B,
  ignore_trivial=False)`; rows of A against B, then rows of B against A). Every
  such pair is at least ``L + 1`` apart, beyond the exclusion zone, because
  ``L > ceil(m / 4)`` is enforced.
* **the merge** keeps, per subsequence, the smallest distance any unit found
  and the index it was found at (the first unit wins a tie).

Every pair ``|i - j| > ceil(m / 4)`` is covered, so the merged profile is the
one-shot ``stumpy.stump(x, m)`` profile: the distances agree to float rounding
(each unit starts its diagonals' running sums at its own first row), and the
indices wherever the nearest neighbour is not a tie. Left/right indices (chains)
are not kept: the step cache stores the profile (a `Scores`), and an AB-join has
no left/right side.

**Cost.** The one-shot evaluates each pair once (the self-join updates both
ends); an AB-join updates only its rows, so a far pair is evaluated twice, and
the union self-joins evaluate each block's inner pairs twice. Total about
``2 x`` the one-shot's work, in units of at most a ``2L``-sample self-join —
the price of using only stumpy's public API (`stump`, `gpu_stump`), which
holds across stumpy versions; splitting the self-join by diagonals would cost
``1 x`` but needs stumpy's private `_stump`, whose signature has changed
between releases, on a cluster whose stumpy version this machine cannot see.

**Checkpoint.** With ``state_dir``, the merged profile and the set of finished
units are written (atomically) after every unit; a call over the same input
continues from them. ``should_stop()`` is asked before each unit.

No UI imports.
"""

import json
import os

import numpy as np

#: what a resumable state is keyed on: a different input never continues another's merge
_STATE = "state.json"
_ARRAYS = "profile.npz"


def _excl_zone(m):
    from stumpy import config
    return int(np.ceil(m / config.STUMPY_EXCL_ZONE_DENOM))


def plan_units(n, m, block):
    """``(bounds, units)``: the blocks as subsequence ranges and the units in the
    order they run — ``("self", p, q)`` a self-join over blocks p..q, ``("ab", p,
    q)`` the rows of block p against block q."""
    l = int(n) - int(m) + 1
    if l < 1:
        raise ValueError(f"a {m}-sample window does not fit a {n}-sample span")
    block = max(int(block), _excl_zone(m) + 1, 1)
    bounds = [(a, min(a + block, l)) for a in range(0, l, block)]
    b = len(bounds)
    if b <= 2:
        return bounds, [("self", 0, b - 1)]
    units = [("self", p, p + 1) for p in range(b - 1)]
    for p in range(b):
        for q in range(p + 2, b):
            units.append(("ab", p, q))
            units.append(("ab", q, p))
    return bounds, units


def _join(backend, t_a, m, t_b=None):
    """One stumpy call — the backend the step names (`auto` tries the GPU)."""
    import stumpy

    def gpu():
        import numba.cuda
        if not numba.cuda.is_available():
            raise RuntimeError("no GPU")
        ids = [d.id for d in numba.cuda.list_devices()]
        if t_b is None:
            return stumpy.gpu_stump(t_a, m, device_id=ids)
        return stumpy.gpu_stump(t_a, m, t_b, ignore_trivial=False, device_id=ids)

    def cpu():
        if t_b is None:
            return stumpy.stump(t_a, m)
        return stumpy.stump(t_a, m, t_b, ignore_trivial=False)

    if backend == "gpu_stump":
        return gpu()
    if backend == "auto":
        try:
            return gpu()
        except Exception:
            return cpu()
    if backend == "stump":
        return cpu()
    raise ValueError(f"a chunked profile is an exact join: backend {backend!r} is not one (stump, gpu_stump, auto)")


def _unit(x, m, bounds, unit, backend):
    """``(row0, P, I)`` for one unit: the rows it covers, their distances, and the
    absolute index of each one's nearest neighbour (-1 when none)."""
    kind, p, q = unit
    if kind == "self":
        a, b = bounds[p][0], bounds[q][1]
        out = _join(backend, x[a:b + m - 1], m)
        dist = np.asarray(out[:, 0], dtype=np.float64)
        idx = np.asarray(out[:, 1], dtype=np.int64)
        idx = np.where(idx >= 0, idx + a, -1)
        return a, dist, idx
    (a0, a1), (b0, b1) = bounds[p], bounds[q]
    out = _join(backend, x[a0:a1 + m - 1], m, x[b0:b1 + m - 1])
    dist = np.asarray(out[:, 0], dtype=np.float64)
    idx = np.asarray(out[:, 1], dtype=np.int64)
    idx = np.where(idx >= 0, idx + b0, -1)
    return a0, dist, idx


def _load(state_dir, key):
    if not state_dir:
        return None
    meta_p, arr_p = os.path.join(state_dir, _STATE), os.path.join(state_dir, _ARRAYS)
    if not (os.path.isfile(meta_p) and os.path.isfile(arr_p)):
        return None
    with open(meta_p, encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("key") != key:
        return None                      # another input's merge: start afresh
    with np.load(arr_p) as z:
        return {"P": z["P"].copy(), "I": z["I"].copy(), "done": set(int(u) for u in meta.get("done") or [])}


def _save(state_dir, key, p, i, done, n_units):
    os.makedirs(state_dir, exist_ok=True)
    arr_p, meta_p = os.path.join(state_dir, _ARRAYS), os.path.join(state_dir, _STATE)
    tmp = arr_p + ".tmp.npz"
    np.savez(tmp, P=p, I=i)
    os.replace(tmp, arr_p)
    tmp = meta_p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"key": key, "done": sorted(done), "units": int(n_units)}, f)
    os.replace(tmp, meta_p)


def progress(state_dir):
    """Units finished in a checkpoint (0 when there is none) — a job's progress mark."""
    meta_p = os.path.join(state_dir, _STATE) if state_dir else None
    if not meta_p or not os.path.isfile(meta_p):
        return 0
    try:
        with open(meta_p, encoding="utf-8") as f:
            return len(json.load(f).get("done") or [])
    except (OSError, ValueError):
        return 0


def chunked_profile(x, m, *, block, backend="stump", state_dir=None, should_stop=None):
    """The self-join profile of ``x`` at window ``m``, in blocks of ``block``
    subsequences (see the module docstring for why it equals the one-shot).

    Returns ``{P, I, complete, units, done, resumed, block}``: ``P`` float64 and
    ``I`` int64 over the ``n - m + 1`` subsequences (meaningful only when
    ``complete``), ``units`` the units in all, ``done`` how many are finished,
    ``resumed`` how many came from the checkpoint."""
    x = np.ascontiguousarray(np.asarray(x, dtype=np.float64))
    m = int(m)
    bounds, units = plan_units(len(x), m, block)
    l = len(x) - m + 1
    key = f"n{len(x)}_m{m}_block{bounds[0][1] - bounds[0][0]}_units{len(units)}_{backend}"
    saved = _load(state_dir, key)
    if saved is not None:
        p, i, done = saved["P"], saved["I"], saved["done"]
    else:
        p, i, done = np.full(l, np.inf), np.full(l, -1, dtype=np.int64), set()
    resumed = len(done)
    for u, unit in enumerate(units):
        if u in done:
            continue
        if should_stop is not None and should_stop():
            return {"P": p, "I": i, "complete": False, "units": len(units), "done": len(done), "resumed": resumed,
                    "block": bounds[0][1] - bounds[0][0]}
        row0, dist, idx = _unit(x, m, bounds, unit, backend)
        rows = slice(row0, row0 + len(dist))
        better = dist < p[rows]
        p[rows] = np.where(better, dist, p[rows])
        i[rows] = np.where(better, idx, i[rows])
        done.add(u)
        if state_dir:
            _save(state_dir, key, p, i, done, len(units))
    return {"P": p, "I": i, "complete": True, "units": len(units), "done": len(done), "resumed": resumed,
            "block": bounds[0][1] - bounds[0][0]}
