"""
background_null.py
===================
Windows of a recording's own background: stretches cut at random from where
nothing was detected, for a noise test whose noise is the recording itself
(w3-b). Generic on purpose — it knows nothing of cycles, families or events.
`Working.interrogation.cycle_shapes` uses it for its verdict null, and the
Library's quiet-stretch test for families (W3-G) is meant to reuse it.

Why a background null at all (wave 2's lesson, `Working/library/coherence.py::
SMOOTH_CAVEAT`): a surrogate built from the shapes themselves keeps whatever it
does not destroy — the trend-kept phase surrogate keeps a smooth curve that
fills the window, so a broad hump or a drop-floor-climb cycle reads "no more
coherent than its own noise". Windows of the recording where no event lies
have the recording's colour, drift and artefacts, and none of the shapes.

The contract
------------
`sample_background(trace, avoid, lengths, count, seed, *, fs=None)` ->
`BackgroundSample(starts, lengths, windows, report)`:

* `trace` — 1-D array, one recording (or span) in its own index frame;
* `avoid` — sample ranges `(start, end)`, half-open, in the trace's frame, that
  no window may touch (the events; clipped to the trace). Samples holding NaN
  are avoided too, so a background window carries no gap;
* `lengths` — the window lengths wanted, in samples: each window's length is
  drawn uniformly, with replacement, from this list (so passing the real
  windows' lengths gives the null their length distribution; a single value
  gives every window that length);
* `count` — how many windows; `seed` — the seed of the generator (seeded,
  never numpy's global state: the bridge runs jobs on threads);
* returns the window starts and lengths (int64 arrays, in the trace's frame),
  the windows themselves (copies, one 1-D array each), and `report`:
  `n_wanted`, `n_cut`, `n_fallback`, `fell_back`, `n_too_long`,
  `background_samples` (free samples: neither avoided nor NaN),
  `background_s` (when `fs` is given), `trace_samples`, `rule`.

**The fallback.** A window whose length fits in no free stretch is cut instead
at a uniformly random place in the whole trace (it may overlap events and
gaps), and counted in `n_fallback`; `fell_back` is True when any window was.
A window longer than the trace is not cut at all (`n_too_long`). Windows may
overlap one another: they are draws, not a partition.

Per-member windows for a set of members on many recordings (w3-g)
------------------------------------------------------------------
`MemberBackground(members, trace_of, *, avoid_of=None, prepare=None,
fs_of=None, seed=0)` is the same cutting for a Library family, whose members
sit on many recordings: `draw(rows, draws, salt)` cuts, for each asked row, a
window **from that member's own recording, at that member's own length**,
avoiding every span `avoid_of(recording)` names (by default the members' own
spans on it) and every NaN — the same free-stretch rule as above (one cache of
free stretches per recording, so a 2,000-member family reads each recording's
mask once). A member whose recording is not on disk (`trace_of` gives None) or
has no free stretch as long as the member borrows a window from another asked
member's recording that has room (counted: `n_borrowed`); the share of members
cut from their own recording (`own_share`) decides whether the draw is a
quiet-stretch null at all (`usable`: `own_share >= QUIET_MIN_SHARE`). A
recording has room for a member only when at least `QUIET_MIN_DISJOINT`
non-overlapping member-length windows fit in its free stretches, so the null
is never a handful of near-copies cut from one short gap. It never
falls back to a random cut through events: a window that cannot be cut quietly
anywhere is None and counted. `prepare(trace, start, end)` turns the cut into
what the member was handed as (the Library hands the engine a decimated
envelope; a chain hands it the raw slice). The report carries
`background_s` — the free seconds on the members' own recordings — and a
`reason` in words when the draw is not usable.

No plotting library — CLAUDE.md rule 1.
"""

from dataclasses import dataclass, field

import numpy as np

#: the share of a family's members that must get a quiet window from their own recording for the quiet-stretch null
#: to be the verdict (below it the caller falls back to its trend-kept null and says so). The W3-B critic's B3: on a
#: recording dense with events the free stretches are fragmented and member-length windows fit nowhere; a placeholder
#: at the critic's "fallback share > ~0.5".
QUIET_MIN_SHARE = 0.5
#: a member's recording "has room" only when at least this many non-overlapping member-length windows fit in its free
#: stretches. Without it a span whose only free stretch is one short tail (W2-E's dense noise events: 300-sample gaps
#: between 600-sample windows, one 1,020-sample tail) gave every quiet window from that one tail — near-copies of each
#: other, so the null crowded as tightly as a family. A placeholder.
QUIET_MIN_DISJOINT = 20

MEMBER_RULE = ("quiet-stretch windows: for each member, a window of its own length cut from its own recording at a "
               "seeded uniform place where the whole window lies in a free stretch (no span of the avoided set — "
               "{avoid} — and no NaN); a member whose recording is not on disk, or holds no free stretch that long, "
               "borrows a window cut the same way from another member's recording (counted); never a random cut "
               "through events. The null is used only when at least {share:.0%} of the members got a window from "
               "their own recording")

RULE = ("background windows: each length drawn with replacement from the wanted lengths; each start uniform over "
        "every place the whole window fits in a free stretch (no avoided sample, no NaN); a window that fits in no "
        "free stretch is cut at a uniform place in the whole trace instead (counted as a fallback); windows may "
        "overlap one another; seeded")


@dataclass
class BackgroundSample:
    starts: np.ndarray
    lengths: np.ndarray
    windows: list = field(default_factory=list)
    report: dict = field(default_factory=dict)


def free_runs(n, avoid, nan_mask=None):
    """`(run_starts, run_ends)` of the samples in `0..n-1` that no avoided range
    covers and that are not NaN, as half-open runs."""
    free = np.ones(int(n), dtype=bool)
    for a, b in avoid:
        a, b = max(0, int(a)), min(int(n), int(b))
        if b > a:
            free[a:b] = False
    if nan_mask is not None:
        free &= ~np.asarray(nan_mask, dtype=bool)
    edges = np.diff(np.concatenate([[0], free.astype(np.int8), [0]]))
    return np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)


def sample_background(trace, avoid, lengths, count, seed, *, fs=None):
    """Background windows of `trace` (module docstring: the contract)."""
    trace = np.asarray(trace, dtype=float).ravel()
    n = trace.size
    lengths = np.asarray(lengths, dtype=np.int64).ravel()
    count = int(count)
    if lengths.size == 0 and count > 0:
        raise ValueError("sample_background needs at least one wanted window length.")
    if np.any(lengths <= 0):
        raise ValueError("sample_background: every wanted window length must be a positive number of samples.")
    rng = np.random.default_rng(seed)
    rs, re = free_runs(n, avoid, np.isnan(trace))
    run_len = re - rs
    want = rng.choice(lengths, size=count, replace=True) if count > 0 else np.zeros(0, dtype=np.int64)
    starts, got, windows = [], [], []
    n_fallback = n_too_long = 0
    for L in want:
        L = int(L)
        if L > n:
            n_too_long += 1
            continue
        cs = np.cumsum(np.maximum(0, run_len - L + 1))
        total = int(cs[-1]) if cs.size else 0
        if total > 0:
            u = int(rng.integers(total))
            k = int(np.searchsorted(cs, u, side="right"))
            s = int(rs[k] + u - (int(cs[k - 1]) if k else 0))
        else:
            n_fallback += 1
            s = int(rng.integers(n - L + 1))
        starts.append(s)
        got.append(L)
        windows.append(trace[s:s + L].copy())
    free_samples = int(run_len.sum())
    report = {"n_wanted": count, "n_cut": len(starts), "n_fallback": n_fallback, "fell_back": bool(n_fallback),
              "n_too_long": n_too_long, "background_samples": free_samples,
              "background_s": (free_samples / float(fs)) if fs else None, "trace_samples": int(n), "rule": RULE}
    return BackgroundSample(starts=np.asarray(starts, dtype=np.int64), lengths=np.asarray(got, dtype=np.int64),
                            windows=windows, report=report)


# ── per-member windows on many recordings (w3-g) ────────────────────────────

@dataclass
class MemberDraws:
    """`windows[d][j]`: draw d's window for asked row j (None when none could be
    cut quietly anywhere); `source[j]`: "own", "borrowed" or None; `report`:
    the counts (`MemberBackground.draw`)."""
    windows: list
    source: list
    report: dict

    @property
    def usable(self):
        return bool(self.report.get("usable"))


class _Recording:
    """One recording's free stretches, cached: the trace (a memmap is fine), its
    free runs and, per window length, the cumulative count of placements."""

    def __init__(self, trace, avoid):
        self.trace = trace
        n = int(len(trace))
        arr = np.asarray(trace)
        nan = np.isnan(arr) if arr.dtype.kind == "f" else None
        self.rs, self.re = free_runs(n, avoid, nan)
        self.n = n
        self.free = int((self.re - self.rs).sum())
        self._cs = {}

    def placements(self, L):
        L = int(L)
        if L not in self._cs:
            self._cs[L] = np.cumsum(np.maximum(0, (self.re - self.rs) - L + 1))
        return self._cs[L]

    def room(self, L):
        """Placements of a window of L, or 0 when fewer than `QUIET_MIN_DISJOINT`
        non-overlapping windows of L fit in the free stretches."""
        if int(((self.re - self.rs) // max(1, int(L))).sum()) < QUIET_MIN_DISJOINT:
            return 0
        cs = self.placements(L)
        return int(cs[-1]) if cs.size else 0

    def start(self, L, rng):
        cs = self.placements(L)
        u = int(rng.integers(int(cs[-1])))
        k = int(np.searchsorted(cs, u, side="right"))
        return int(self.rs[k] + u - (int(cs[k - 1]) if k else 0))


def _raw_slice(trace, start, end):
    return np.asarray(trace[int(start):int(end)], dtype=float).copy()


class MemberBackground:
    """Background windows for the members of a set that lives on many
    recordings (module docstring, "Per-member windows").

    members : one entry per member: `(recording, start, end)` in that recording's
              sample frame (half-open), or None (no recording known)
    trace_of : `recording -> 1-D array` (a memmap is fine) or None when it is not
               on disk; called once per recording
    avoid_of : `recording -> iterable of (start, end)`: what no window may touch.
               Default: the members' own spans on that recording
    prepare : `(trace, start, end) -> waveform`, the form the members were handed
              in; default the raw slice
    fs_of : `recording -> sampling rate` (for `background_s`), optional
    seed : the base seed; `draw(..., salt)` seeds each call from (seed, salt)
    avoid_words : what `avoid_of` avoids, in words, for the rule
    """

    def __init__(self, members, trace_of, *, avoid_of=None, prepare=None, fs_of=None, seed=0, avoid_words=None):
        self.members = list(members)
        self._trace_of = trace_of
        self._avoid_of = avoid_of
        self._prepare = prepare or _raw_slice
        self._fs_of = fs_of
        self.seed = int(seed)
        self.avoid_words = avoid_words or ("every member's span" if avoid_of is None else "the given spans")
        self._recordings = {}
        self._rows = None            # a subset's map onto the parent's members

    def subset(self, rows):
        """A view onto `rows` of this set (row j of the view = member rows[j]),
        sharing the recordings' caches; the avoidance still covers every member."""
        view = MemberBackground.__new__(MemberBackground)
        view.__dict__.update(self.__dict__)
        base = self._rows if self._rows is not None else np.arange(len(self.members))
        view._rows = np.asarray(base, dtype=np.int64)[np.asarray(list(rows), dtype=np.int64)]
        return view

    def __len__(self):
        return len(self._rows) if self._rows is not None else len(self.members)

    def _member(self, j):
        return self.members[int(self._rows[j]) if self._rows is not None else int(j)]

    def rule(self):
        return MEMBER_RULE.format(avoid=self.avoid_words, share=QUIET_MIN_SHARE)

    def _recording(self, rec):
        if rec not in self._recordings:
            trace = self._trace_of(rec)
            if trace is None:
                self._recordings[rec] = None
            else:
                if self._avoid_of is not None:
                    avoid = list(self._avoid_of(rec))
                else:
                    avoid = [(int(m[1]), int(m[2])) for m in self.members if m is not None and m[0] == rec]
                self._recordings[rec] = _Recording(trace, avoid)
        return self._recordings[rec]

    def draw(self, rows, draws, salt=0):
        """`MemberDraws` for the asked `rows` (indices into this set), `draws`
        windows each (module docstring)."""
        rows = [int(r) for r in rows]
        draws = max(0, int(draws))
        rng = np.random.default_rng([self.seed, int(salt), 7919])
        windows = [[None] * len(rows) for _ in range(draws)]
        source = [None] * len(rows)
        n_unknown = n_not_on_disk = n_no_room = n_borrowed = n_lost = 0
        lengths, own_recs, need = [], [], []
        for j, r in enumerate(rows):
            m = self._member(r)
            if m is None:
                n_unknown += 1
                need.append((j, None))
                continue
            rec, a, b = m[0], int(m[1]), int(m[2])
            L = max(1, b - a)
            lengths.append(L)
            R = self._recording(rec)
            if R is None:
                n_not_on_disk += 1
                need.append((j, L))
                continue
            if rec not in own_recs:
                own_recs.append(rec)
            if L > R.n or R.room(L) <= 0:
                n_no_room += 1
                need.append((j, L))
                continue
            source[j] = "own"
            for d in range(draws):
                s = R.start(L, rng)
                windows[d][j] = self._prepare(R.trace, s, s + L)
        fallback_L = int(np.median(lengths)) if lengths else None
        for j, L in need:
            L = L if L is not None else fallback_L
            ok = [rec for rec in own_recs if L is not None and self._recordings[rec].room(L) > 0]
            if not ok:
                n_lost += 1
                continue
            source[j] = "borrowed"
            n_borrowed += 1
            for d in range(draws):
                R = self._recordings[ok[int(rng.integers(len(ok)))]]
                s = R.start(L, rng)
                windows[d][j] = self._prepare(R.trace, s, s + L)
        n = len(rows)
        n_own = sum(1 for s in source if s == "own")
        free_samples, free_s = 0, (0.0 if self._fs_of is not None else None)
        for rec in own_recs:
            R = self._recordings[rec]
            free_samples += R.free
            fs = self._fs_of(rec) if self._fs_of is not None else None
            free_s = (free_s + R.free / float(fs)) if (free_s is not None and fs) else None
        own_share = (n_own / n) if n else 0.0
        usable = bool(n) and own_share >= QUIET_MIN_SHARE
        reason = None
        if not usable:
            parts = []
            if n_no_room:
                parts.append(f"{n_no_room} of {n} members' recordings hold too little event-free signal: fewer than "
                             f"{QUIET_MIN_DISJOINT} non-overlapping member-length windows fit in their quiet stretches "
                             f"(the recording is mostly events, or its quiet stretches are fragmented)")
            if n_not_on_disk:
                parts.append(f"{n_not_on_disk} of {n} members' recordings are not on disk")
            if n_unknown:
                parts.append(f"{n_unknown} of {n} members have no recording")
            reason = (f"only {n_own} of {n} members ({own_share:.0%}) got a quiet window from their own recording, "
                      f"under the {QUIET_MIN_SHARE:.0%} needed: " + ("; ".join(parts) or "no members"))
        report = {"n_members": n, "n_own": n_own, "n_borrowed": n_borrowed, "n_not_on_disk": n_not_on_disk,
                  "n_no_room": n_no_room, "n_unknown": n_unknown, "n_lost": n_lost, "own_share": float(own_share),
                  "usable": usable, "draws": draws, "background_samples": int(free_samples),
                  "background_s": free_s, "n_recordings": len(own_recs), "reason": reason, "rule": self.rule()}
        return MemberDraws(windows=windows, source=source, report=report)
