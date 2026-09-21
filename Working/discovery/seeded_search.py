"""
seeded_search.py
================
Spec §7.6 — a seed search is a run (P17): take a shape by content, find where
else it occurs, see how many of those chance alone would give, and choose
where to cut.

What comes from where, and why it matters
------------------------------------------
**The matches are the block's own.** `Adapters.detection_seed_matches.
match_exemplar` is imported, not reimplemented, so the candidates the page
lists before the run and the `detections` the run writes are one function with
one trivial-match guard. A second implementation here would drift.

**There is no matrix profile in a seeded search.** `detection.seed_matches`
calls `stumpy.match` directly — an FFT search of one query against every
position. A matrix profile answers a different question (every subsequence's
nearest neighbour) and the block cannot consume one. Matrix-profile reuse
belongs to the `mp_threshold` / `mp_motifs` template path, and
`find_reusable_profile` below serves *that*; `USES_MATRIX_PROFILE` records the
fact so a caller cannot quietly claim work that never happened.

**The distance profile is computed here.** The block returns only the k kept
matches and their distances; §7.6's profile track ("clean signal, the distance
profile with the threshold line") needs a value at every position, which is
`stumpy.mass` — the same quantity, over a view at a time.

**The null is N draws, because the block has one.** `preprocessing.surrogate`
takes a `method` and a `seed` and produces **one** realisation; it has no
`draws`. A null *distribution* is therefore N realisations at N seeds, and the
same seed must reproduce it (D6: the surrogate block stays the mechanism and
Settings › Nulls holds the per-kind defaults).

**A null the block cannot compute is refused, not substituted.** Settings ›
Nulls names *circular shift of the channel* for seed search;
`preprocessing.surrogate` implements `phase_randomize` and `block_shuffle`
only. Falling back silently would put "circular shift 200×" on the page over a
different computation, and a × null whose null is unstated cannot be falsified.
`resolve_null` says so in words the page can print. (A circular shift would in
any case be a degenerate null here: shifting a channel leaves the multiset of
its z-normalised subsequences unchanged except at the wrap, so the distance
distribution would be the original's by construction.)

No UI imports.
"""

import hashlib
import json
import os

import numpy as np

from Adapters.detection_seed_matches import match_exemplar
from Working.config import HELD_OUT_RECORDING_FILE, HELD_OUT_UNLOCK
from Working.database import queries as _q
from Working.recipes import make_recipe

#: A seeded search consumes no matrix profile — see the module docstring.
USES_MATRIX_PROFILE = False
WHY_NO_PROFILE = (
    "detection.seed_matches calls stumpy.match directly: one query against every position, "
    "FFT-based. A matrix profile answers a different question and the block cannot consume one; "
    "reuse belongs to the mp_threshold / mp_motifs templates."
)

#: The methods `preprocessing.surrogate` actually implements.
BLOCK_METHODS = ("phase_randomize", "block_shuffle")
DEFAULT_NULL_METHOD = "phase_randomize"
DEFAULT_DRAWS = 200
NULL_PAGE = "nulls"
NULL_KIND = "seed-search"

_ALIASES = {
    "phase_randomize": "phase_randomize",
    "phase randomize": "phase_randomize",
    "phase randomise": "phase_randomize",
    "phase randomisation": "phase_randomize",
    "phase randomization": "phase_randomize",
    "block_shuffle": "block_shuffle",
    "block shuffle": "block_shuffle",
    "block shuffling": "block_shuffle",
}


# ── the null ────────────────────────────────────────────────────────────────

def resolve_null(method=None, draws=None, seed=0):
    """Turn a Settings › Nulls value into something the block can run — or say
    plainly that it cannot.

    Returns ``{method, requested, supported, reason, draws, seed}``. ``method``
    is None when unsupported; ``reason`` is then a sentence naming the block
    and what it does implement, for the page to print instead of a number.
    """
    requested = method
    draws = int(draws) if draws is not None else DEFAULT_DRAWS
    if method is None:
        return {"method": DEFAULT_NULL_METHOD, "requested": None, "supported": True,
                "reason": None, "draws": draws, "seed": int(seed)}
    key = str(method).strip().lower()
    resolved = _ALIASES.get(key)
    if resolved is None:
        return {
            "method": None, "requested": requested, "supported": False, "draws": draws,
            "seed": int(seed),
            "reason": (f"Settings › Nulls asks for {requested!r}, which preprocessing.surrogate does not "
                       f"implement — it offers {BLOCK_METHODS[0]} and {BLOCK_METHODS[1]}. No null is drawn, "
                       f"rather than a different one drawn under that name."),
        }
    return {"method": resolved, "requested": requested, "supported": True, "reason": None,
            "draws": draws, "seed": int(seed)}


def null_from_settings(conn, kind=NULL_KIND):
    """The project's null for a kind, from Settings › Nulls (`null.<kind>.method`
    / `.draws`), resolved against what the block implements."""
    from Working.registration.settings import get_settings

    saved = get_settings(conn, NULL_PAGE)
    return resolve_null(saved.get(f"null.{kind}.method"), saved.get(f"null.{kind}.draws"))


def _spec(name):
    """The registered block. `discover_adapters()` first: the registry is
    populated by import, and a caller that imported only this module would
    otherwise see an empty one."""
    from Adapters.registry import discover_adapters, get_adapter

    discover_adapters()
    return get_adapter(name)


def _surrogate(x, method, seed, fs, block_s):
    """One realisation, through the block — never a local reimplementation."""
    spec = _spec("preprocessing.surrogate")
    t = np.arange(len(x), dtype=float) / float(fs)
    result = spec.run(np.asarray(x, dtype=float), t, float(fs),
                      method=method, seed=int(seed), block_s=float(block_s))
    return np.asarray(result.value.x, dtype=float)


def null_distances(x, exemplar, *, draws=DEFAULT_DRAWS, seed=0, method=None, k=10,
                   max_distance=None, fs=1.0, block_s=1.0, on_progress=None, should_cancel=None):
    """The distances the seed gets against ``draws`` surrogate signals.

    One draw is one `preprocessing.surrogate` realisation at seed ``seed + i``
    put through the same `match_exemplar` the real search uses, so the two
    distributions are comparable by construction. Reproducible from ``seed``.

    Returns ``{distances, per_draw, draws, method, seed}``; ``distances`` is the
    pooled list (divide a count by ``draws`` for "what the null gives").
    """
    resolved = resolve_null(method, draws, seed)
    if not resolved["supported"]:
        raise ValueError(resolved["reason"])
    x = np.asarray(x, dtype=float).ravel()
    q = np.asarray(exemplar, dtype=float).ravel()
    per_draw, pooled = [], []
    for i in range(resolved["draws"]):
        if should_cancel is not None and should_cancel():
            break
        s = _surrogate(x, resolved["method"], resolved["seed"] + i, fs, block_s)
        rows = match_exemplar(s, q, k=k, max_distance=max_distance)
        ds = [float(r[0]) for r in rows]
        per_draw.append(ds)
        pooled.extend(ds)
        if on_progress is not None:
            on_progress(i + 1, resolved["draws"])
    return {"distances": pooled, "per_draw": per_draw, "draws": len(per_draw),
            "method": resolved["method"], "seed": resolved["seed"]}


# ── the matches and the profile ─────────────────────────────────────────────

def candidates(x, exemplar, *, k=10, max_distance=None):
    """The block's own matches: ``[{index, distance}]``, closest first.

    ``max_distance`` is passed straight through; the page fetches once with a
    generous cut and re-thresholds that list, so dragging the line costs
    nothing (`cut_counts`).
    """
    rows = match_exemplar(np.asarray(x, dtype=float).ravel(),
                          np.asarray(exemplar, dtype=float).ravel(),
                          k=int(k), max_distance=max_distance)
    out = [{"index": int(r[1]), "distance": float(r[0])} for r in rows]
    out.sort(key=lambda c: (c["distance"], c["index"]))
    return out


def distance_profile(x, exemplar, *, view=None):
    """§7.6's profile track: the z-normalised distance from the seed to **every**
    position (`stumpy.mass`).

    Without ``view`` this is the whole array. With ``view=(a, b)`` it is the
    same quantity over that window — a slice of the same profile, not a
    separately-normalised one — returned with the signal beside it:
    ``{t0, signal, distance, m}``.
    """
    import stumpy

    x = np.asarray(x, dtype=float).ravel()
    q = np.asarray(exemplar, dtype=float).ravel()
    m = len(q)
    if view is None:
        return np.asarray(stumpy.mass(q, x), dtype=float)
    a, b = int(view[0]), int(view[1])
    a = max(0, a)
    b = min(len(x), b)
    if b - a < m:
        return {"t0": a, "signal": x[a:b].tolist(), "distance": [], "m": m}
    d = np.asarray(stumpy.mass(q, x[a:b]), dtype=float)
    return {"t0": a, "signal": x[a:b].tolist(), "distance": d.tolist(), "m": m}


def cut_counts(distances, null, cut):
    """Re-threshold what is already in hand: how many matches the cut keeps and
    how many the null gives at the same cut (per draw, not pooled).

    ``null`` is `null_distances`'s result, or any ``{distances, draws}``.
    """
    cut = float(cut)
    kept = sum(1 for d in distances if float(d) <= cut)
    draws = int((null or {}).get("draws") or 0)
    null_hits = sum(1 for d in (null or {}).get("distances", []) if float(d) <= cut)
    null_gives = (null_hits / draws) if draws else None
    x_null = (kept / null_gives) if null_gives else None
    return {"kept": kept, "null_gives": null_gives, "x_null": x_null}


def recommended_cut(distances, null, *, alpha=0.01):
    """§7.6's "match threshold with a recommended marker".

    The marker is the largest observed match distance at which the null is
    still expected to give at most ``alpha`` matches per draw — i.e. below the
    ``alpha × draws``-th smallest null distance. None when even the closest
    match is no better than chance, which is the honest answer and reads as
    such on the page.
    """
    nulls = sorted(float(d) for d in (null or {}).get("distances", []))
    draws = int((null or {}).get("draws") or 0)
    if not nulls or not draws:
        return None
    idx = int(np.floor(alpha * draws))
    ceiling = nulls[idx] if idx < len(nulls) else nulls[-1] + 1e-9
    below = [float(d) for d in distances if float(d) < ceiling]
    return max(below) if below else None


# ── the seed ────────────────────────────────────────────────────────────────

def seed_from_content(conn, source_file, channel, start_idx, end_idx, *, role=None, title=None,
                      entry_id=0):
    """§7.6's seed card: the shape identified by **content** — recording,
    channel, sample range and a hash of the samples themselves — so an exported
    recipe resolves on another machine's database (the `library_exemplar`
    binding is content-addressed for exactly this reason)."""
    if source_file == HELD_OUT_RECORDING_FILE and not HELD_OUT_UNLOCK:
        raise PermissionError(
            f"{HELD_OUT_RECORDING_FILE} is held out (spec §0 D6): it cannot be a seed, "
            f"a search target or a compare side")
    rec = _q.get_recording(conn, source_file, int(channel))
    if rec is None:
        raise ValueError(f"no recording for {source_file!r} channel {channel}")
    start_idx, end_idx = int(start_idx), int(end_idx)
    n = int(rec["n_samples"])
    if start_idx < 0 or end_idx > n or end_idx <= start_idx:
        raise ValueError(f"the seed span [{start_idx}, {end_idx}) is outside {source_file} "
                         f"channel {channel}, which has {n} samples")
    x = np.load(rec["npy_path"], mmap_mode="r")[start_idx:end_idx]
    digest = hashlib.sha1(np.ascontiguousarray(x, dtype=np.float64).tobytes()).hexdigest()[:16]
    fs = float(rec["fs"])
    return {
        "recording_id": int(rec["id"]),
        "source_file": source_file,
        "channel": int(channel),
        "start_idx": start_idx,
        "end_idx": end_idx,
        "samples": end_idx - start_idx,
        "length_s": (end_idx - start_idx) / fs,
        "start_h": start_idx / fs / 3600.0,
        "fs": fs,
        "hash": digest,
        "role": role,
        "title": title,
        "entry_id": int(entry_id),
        # `entry_id` is the motif-library row this shape came from when there is
        # one, and 0 when the seed was taken straight off a channel (an Explore
        # selection, a family medoid, the seed bundle). The binding resolves by
        # CONTENT either way — `Working.side_inputs._resolve_library_exemplar`
        # never reads entry_id — so an exported recipe still resolves on a
        # machine whose motif_entry table is empty, which this one's is.
        "binding": {"source_kind": "library_exemplar", "entry_id": int(entry_id),
                    "source_file": source_file, "channel": int(channel),
                    "start_idx": start_idx, "end_idx": end_idx},
    }


def exemplar_signal(conn, seed):
    """The seed's samples, resolved through the **same** seam
    `execute_recipe` uses (`Working.side_inputs.resolve_side_inputs`), so the
    shape on the page and the query in the run are the same array."""
    from Working.side_inputs import resolve_side_inputs

    spec = _spec("detection.seed_matches")
    resolved = resolve_side_inputs(conn, spec, {"exemplar": seed["binding"]},
                                   root_signal=None, step_results={})
    return resolved["exemplar"]


def recommended_params(seed):
    """§7.6's parameter card. The window is **locked** to the exemplar's native
    length; the exclusion zone is m/2, the trivial-match guard.

    `exclusion_note` states the one place the block and the spec differ:
    `detection.seed_matches` exposes no exclusion parameter and does not pass
    `query_idx`, so the search actually runs under `stumpy.match`'s own default
    (m/4). Said here rather than drawn as a locked "m/2" over a search that
    used something else.
    """
    m = int(seed["samples"])
    fs = float(seed["fs"]) or 1.0
    return {
        "algorithm": "mass",
        "windowSamples": m,
        "windowS": m / fs,
        "windowLocked": True,
        "scaleBank": "none",
        "exclusionSamples": m // 2,
        "exclusionS": (m // 2) / fs,
        "overlap": "lowest",
        "exclusion_note": (
            "§7.6 specifies m/2. detection.seed_matches exposes no exclusion parameter and does not "
            "pass query_idx, so the search runs under stumpy.match's own default of m/4."),
    }


def seed_steps(seed, *, k=10, max_distance=None):
    """The one chain step a seeded search is."""
    return [{
        "stage": "detection",
        "algorithm": "seed_matches",
        "params": {"k": int(k), "max_distance": float(max_distance or 0.0)},
        "side_inputs": {"exemplar": dict(seed["binding"])},
    }]


def seed_recipe(seed, recording_ids, span=None, *, k=10, max_distance=None):
    """The fan-out recipe: one `detection.seed_matches` step over N channels."""
    ids = [int(r) for r in recording_ids]
    if not ids:
        raise ValueError("a seeded search needs at least one channel in scope")
    return make_recipe(ids[0], seed_steps(seed, k=k, max_distance=max_distance),
                       span=(list(span) if span else None),
                       fan_out={"kind": "channels", "targets": ids})


# ── matrix-profile reuse (for the template path, not for this one) ──────────

def find_reusable_profile(conn, recording_id, m, *, span=None, require_fresh=False):
    """A matrix profile already on disk that covers this exact question.

    Matched by **content**: same recording, same window `m`, and a span that
    contains the one being asked for. `matrix_profile_store.find_mp` keys on
    (recording, window_min) alone and ignores the span, so a whole-channel
    query would happily receive a four-hour profile; the span rule is applied
    here. A stale profile (its source `.npy` changed since) is returned with
    `stale: True` rather than dropped — the caller decides — and never
    silently.

    Returns ``{path, m, span, fs, stale, source, reason}`` or None.
    """
    m = int(m)
    want = (int(span[0]), int(span[1])) if span else None

    rows = conn.execute(
        "SELECT id, path, name, span_start, span_end, fs, params_json FROM registered_artifacts "
        "WHERE kind = 'matrix_profile' AND active = 1 AND recording_id = ? ORDER BY id",
        (int(recording_id),)).fetchall()
    for r in rows:
        try:
            params = json.loads(r["params_json"] or "{}")
        except ValueError:
            params = {}
        if int(params.get("m") or 0) != m:
            continue
        a = int(r["span_start"] or 0)
        b = int(r["span_end"] or 0)
        if want and not (a <= want[0] and b >= want[1]):
            continue
        if not os.path.isfile(r["path"]):
            continue
        return {"path": r["path"], "name": r["name"], "m": m, "span": [a, b],
                "fs": (float(r["fs"]) if r["fs"] is not None else None), "stale": False,
                "source": "registry", "registered_id": int(r["id"]),
                "reason": f"reusing the registered matrix profile {r['name']} (m = {m} samples)"}

    hit = _from_run_store(conn, recording_id, m, want, require_fresh)
    return hit


def _from_run_store(conn, recording_id, m, want, require_fresh):
    """The second place a profile can live: a completed `detection.matrix_profile`
    run with an artifacts row (`Working.database.matrix_profile_store`). Its
    lookup ignores the span, so the run row's own span is checked here."""
    from Working.database.matrix_profile_store import find_mp

    rec = _q.get_recording_by_id(conn, recording_id)
    if rec is None:
        return None
    fs = float(rec["fs"]) or 1.0
    window_min = m / fs / 60.0
    try:
        row = find_mp(conn, int(recording_id), window_min)
    except Exception:
        return None
    if row is None:
        return None
    if require_fresh and row.get("stale"):
        return None
    path = row.get("artifact_path") or row.get("path")
    if not path or not os.path.isfile(path):
        return None
    a, b = int(row.get("span_start") or 0), int(row.get("span_end") or rec["n_samples"])
    if want and not (a <= want[0] and b >= want[1]):
        return None
    return {"path": path, "name": os.path.basename(path), "m": m, "span": [a, b], "fs": fs,
            "stale": bool(row.get("stale")), "source": "run_store",
            "registered_id": None, "run_id": row.get("run_id"),
            "reason": ("reusing the matrix profile from run "
                       f"{row.get('run_id')} (m = {m} samples)"
                       + (" — STALE: its source channel changed since it was computed"
                          if row.get("stale") else ""))}
