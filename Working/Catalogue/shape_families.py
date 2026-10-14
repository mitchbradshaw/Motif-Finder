"""
shape_families.py
===================
Families of event shapes inside an Analyse chain, computed by **the Library's own
grouping engine** (w2-e): the core under `catalogue.shape_families` (WindowSet ->
Grouping) and `interrogation.event_families` (SpanSet -> SpanSet + `family`). The
researcher's Q3 (`docs/research/analysis-blocks-from-literature.md` §8): one
implementation, two surfaces — a family found here and a family found in the Library
are the same computation on the same vectors.

In plain words: give it a stack of waveforms (one per event); it sorts them into
families of similar shape with Ward, k-Shape or HDBSCAN — whichever the Library's
registry offers for its `shape-distance` basis — leaves out what fits no family (and
says why), and for every family reports two things that say whether the family is
real: the method's own **noise flag** (did the family beat noise of its members' own
recordings — windows cut where no event lies, w3-g — or, where too little quiet signal
is left, trend-kept phase-randomised copies of its members?) and the family's **SVD
entropy** (how far its members are copies of one shape) beside what that noise scores.

**The public function for a null.** `shape_families(waveforms, ...)` takes the cut
waveform matrix (n x L, or a list of 1-D waveforms) and returns `ShapeFamilies`:
the family labels (1..K, -1 = none), each family's flags and SVD entropy with its
null, and `fraction_placed` / `fraction_confident`. It is the exact code path
`interrogation.event_families` runs (through `event_families(x, fs, spans, ...)`,
which cuts with W2-A's `event_windows` / `cut` and calls it), so a caller can feed it
surrogates of the same events and compare.

What is computed
----------------
1. **Screening.** A waveform with a +-inf has no shape (`infinite_values`); one with
   more missing samples than `max_nan_frac`, or none at all, is `missing_values`
   (the engine's reasons). A waveform with a few NaNs (at most `max_nan_frac`, the
   fraction W2-A's cutter already admits into a window) is filled by linear
   interpolation and counted (`n_gap_filled`) — **an adaptation**: the Library's
   methods screen out any NaN row, which would silently drop every event whose window
   holds one missing sample.
2. **Grouping.** `Working.library.grouping.engine.run_grouping(items, unit=
   "single_motifs", basis="shape-distance", method, params)` with one item per kept
   waveform (`member_ref` = its row, `values` = the waveform). The engine prepares
   the vectors itself (`ward.shape_vectors`: resampled to 256 samples, z-normalised),
   applies the Library's ten-member floor (`min_group`), and returns each family's
   medoid and flags (`Family.flags`: `noise_like` / `unstable` / `tested` / `why`)
   and the method's `fit_summary`. **Nothing is re-derived here**: the noise verdict
   is W2-B's, read off the flags. The item dicts are honest — a member reference and
   a waveform are all a `shape-distance` grouping reads.
3. **Numbering.** Families are renumbered 1..K by size, largest first (ties: the
   earliest member), so "family 1" means the same thing whatever method made it;
   the engine's own label (`F-03`) rides as `library_label`.
4. **Distance.** `distance[i]` is the engine's distance from a member to its
   family's medoid on the method's [0, 1] scale (normalised SBD for k-Shape and
   HDBSCAN, Ward's normalised scale-invariant distance for Ward); NaN off a family.
5. **Coherence.** Per family, W2-B's `Working.library.coherence.svd_entropy` on the
   members' (gap-filled) waveforms, aligned to the family's medoid, with its null
   (`null_median`, `null_p05`: the quiet-stretch one where usable, else trend-kept),
   the sigma^2 variant and `top_share`. The sigma^2 variant leads the summary line
   (the researcher, 2026-10-14); eq. 17 keeps the verdict.
7. **The noise (w3-g).** `shape_families(..., background=)` takes a
   `Working.background_null.MemberBackground` over the waveforms: the method's
   per-family test and the coherence judge against windows of the recording's own
   quiet stretches wherever at least half a family's members got one, and fall back
   to trend-kept noise, said per family (`null_kind`, `why`, a warning).
   `event_families` and `catalogue.shape_families` build it from the chain's own
   trace (`span_background`): windows of the event-window length, cut where no
   event span and no window of the set lies.
6. **Exemplar.** Each family's exemplar is its medoid — a member, never an average
   (`docs/BLOCK_INTEGRATION.md` §2) — at distance 0.

Caps. HDBSCAN and k-Shape fit at most their `sample` rows and assign the rest (W2-B's
rule, passed through). Ward builds a full square matrix: it is refused past
`WARD_MAX_ITEMS` (5,000, W2-B's sample default) in words that name the two methods
that sample.

Why not extend `catalogue.shape_cluster`. That block is RQ1's training-pool clusterer:
it reads Trace shape's vectors by path, clusters a stratified sample of TRAINING
windows only (validation, test and exam windows are -1 by design, assigned later by a
trained model), keeps the Ward tree on disk keyed by pool and sample so a later cut
re-uses it, carries the researcher's cluster-to-class mapping, and freezes once a run
on the pool has a test score. A chain's events have no split, no pool, no mapping and
no tree to keep; they need the registry's methods (k-Shape, HDBSCAN) with their noise
flags, and every event assigned. Folding this into `shape_cluster` would put a branch
on each of those paths; a sibling that calls the same engine keeps both honest.

Imports no adapter and no UI.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from Working.Catalogue import event_windows as EW
from Working.library.coherence import ALIGNED as COHERENCE_ALIGNED
from Working.library.coherence import NULL_DRAWS as COHERENCE_NULL_DRAWS
from Working.library.coherence import RULE as COHERENCE_RULE
from Working.library.coherence import QUIET_MAX_POOL, QUIET_SECONDS_PER_WINDOW, svd_entropy
from Working.library.grouping import engine
from Working.library.grouping import methods as registry
from Working.library.grouping.methods.kshape import QUIET_KIND, TREND_KIND
from Working.library.grouping.methods.ward import RESAMPLE_LENGTH, shape_vectors

BASIS = "shape-distance"
UNIT = "single_motifs"
DEFAULT_METHOD = "hdbscan"
#: params every method carries that mean one thing for all of them (the engine's rules): one control each
SHARED_PARAMS = ("min_group", "resample_length")
#: Ward's square matrix: past this many waveforms the block refuses (W2-B's sample default)
WARD_MAX_ITEMS = 5000

OMIT_NO_WINDOW = "no_window"          # the cutter left the event out (too near a span end, too many NaN)
OMIT_OUTSIDE_SPAN = "outside_span"    # a window that does not lie inside the chain's span
#: the suffix a noise-like family's group key carries, so Intervals' table says it on its face
NOISE_LIKE_SUFFIX = "~noise_like"
#: ... and an untested one (a method that draws no null, Ward) — never an unmarked key for a family nobody tested
UNTESTED_SUFFIX = "~untested"

#: methods whose noise null is not trusted as a confidence, with the measurement: their families are never called
#: confident (`confident` None, `fraction_confident` None, the reason in notes). EMPTY since w3-g. k-Shape was here
#: (the W2-E critic: its plain phase-randomised null left families unflagged on cut events of pure random-walk noise,
#: 132 + 108 members at n = 1,000). W3-G replaced that null with the trend-kept one and added the quiet-stretch one,
#: and re-ran the no-structure test at the defaults (k chosen, 10 starts) through `event_families`: cut events of
#: pure random walk and AR(1) phi 0.95 / 0.97 / 0.99, n = 200 and 1,000, both with events dense enough that the
#: trend-kept null judges (W2-E's `noise_events`) and spread so the quiet-stretch null judges — every family flagged
#: noise-like, no Intervals key unmarked (`tests/test_library_background_null.py`, `tests/test_adapter_event_families.py`).
UNTRUSTED_NULLS = {}
#: methods `event_families` does not offer, and why: its families become Intervals keys, where an unflagged
#: noise crowd reads as a real rhythm. EMPTY since w3-g (k-Shape's measurement above).
EVENT_FAMILIES_EXCLUDED = {}

#: the window length `event_families` defaults to — a PLACEHOLDER, measured (W2-E critic's 432-run sweep through
#: the real chain: two shapes x three backgrounds x two seeds x SNR 10 and 40): anchored on the span start, 600 s
#: kept both shapes in distinct unmarked families with their medians within 10 % in 18/18 cases at both SNRs
#: (300 s: 18/18 and 16/18; 1200 s: 8/18 and 16/18; the auto length: 5/18 and 4/18; onset or extremum anchors at
#: their best length 7-12/18). Check on real recordings.
DEFAULT_EVENT_LENGTH_S = 600.0
#: an auto-length coverage share past which a warning is raised (as `catalogue.event_windows`)
AUTO_WARN_FRAC = 0.25

#: coherence cost, measured 2026-10-14 on this machine: svd_entropy with 5 null draws ~ 1.5 ms per member
#: (aligned SBD to the medoid + six SVDs of P x 256), so a whole set costs ~ n x this
COHERENCE_SECONDS_PER_ITEM = 2.0e-3
#: families an estimate assumes for the coherence's quiet-stretch pools (w3-g; a placeholder: the families block's
#: real runs found 0-3 families on real spans, W2-evaluation.md)
COHERENCE_ESTIMATE_FAMILIES = 5

EXEMPLAR_RULE = ("each family's medoid — the member with the least summed distance to the other members "
                 "(HDBSCAN, Ward) or the member nearest its centroid (k-Shape), as the Library's engine names it: "
                 "a member, never an average")


@dataclass
class FamilyInfo:
    """One family: its number (1..K by size), the engine's label, its rows (into the
    waveforms given), its medoid row, the method's flags and its coherence."""
    family: int
    library_label: str
    size: int
    rows: np.ndarray
    medoid_row: int
    medoid_distance: float
    flags: dict
    coherence: dict
    #: False for a method in `UNTRUSTED_NULLS`: its "not noise-like" is not a confidence
    null_trusted: bool = True
    null_caveat: Optional[str] = None

    @property
    def confident(self):
        """True: tested against a trusted null and passed; False: flagged noise-like;
        None: not tested, or tested against a null that is not trusted."""
        if self.flags.get("noise_like"):
            return False
        if not self.flags.get("tested") or not self.null_trusted:
            return None
        return True


@dataclass
class ShapeFamilies:
    """The answer for n waveforms. `labels[i]` is 1..K or -1; `omit_reason[i]` is None
    for a placed row, else the reason; `distance[i]` is to the family's medoid (NaN off
    a family). `fraction_placed` = rows in a family / n; `fraction_confident` = rows in
    a family that was tested against its null and is not noise-like / n (None when the
    method draws no null, e.g. Ward)."""
    labels: np.ndarray
    omit_reason: list
    distance: np.ndarray
    families: list
    omitted: dict
    n: int
    n_placed: int
    n_confident: Optional[int]
    fraction_placed: Optional[float]
    fraction_confident: Optional[float]
    method: str
    params: dict
    fit_summary: dict = field(default_factory=dict)
    recipe_hash: str = ""
    notes: list = field(default_factory=list)
    n_gap_filled: int = 0

    @property
    def k(self):
        return len(self.families)


@dataclass
class EventFamilies:
    """`shape_families` on the windows W2-A's cutter cut around a SpanSet's events,
    mapped back to the events: `family[i]` per input event (-1 = none),
    `omit_reason[i]` (`no_window` for an event the cutter left out), `distance[i]`,
    `noise_like[i]` (the event's family is flagged noise-like). `fraction_placed` is
    over the EVENTS (a left-out event counts against it)."""
    windows: EW.EventWindows
    families: ShapeFamilies
    family: np.ndarray
    omit_reason: list
    distance: np.ndarray
    noise_like: np.ndarray
    omitted: dict
    n_events: int
    fraction_placed: Optional[float]
    fraction_confident: Optional[float]
    #: per event: its family was tested against a trusted null (False for Ward's, and off a family)
    tested: np.ndarray = None


# ── the method choice and its params, read from the registry ───────────────

def shape_methods():
    """The registered grouping methods that serve the `shape-distance` basis, in the
    registry's order — a future method appears here without an edit."""
    return tuple(m.name for m in registry.methods_for(BASIS))


def flat_name(method, param):
    return param if param in SHARED_PARAMS else f"{method}_{param}"


def flat_param_specs():
    """Every method's params flattened for a block's param form: `{flat, method,
    param, spec}`, the shared ones (`SHARED_PARAMS`) once, unprefixed (`method` None),
    the rest as `<method>_<param>`."""
    out, seen = [], set()
    for m in shape_methods():
        for p, spec in registry.get(m).params.items():
            flat = flat_name(m, p)
            if flat in seen:
                continue
            seen.add(flat)
            out.append({"flat": flat, "method": None if p in SHARED_PARAMS else m, "param": p, "spec": dict(spec)})
    return out


def method_params(method, flat):
    """The `method`'s own params out of a flat dict (only the keys present)."""
    out = {}
    for p in registry.get(method).params:
        key = flat_name(method, p)
        if key in flat:
            out[p] = flat[key]
    return out


def prepared_vectors(waveforms, resample_length=RESAMPLE_LENGTH):
    """The Library's preparation (`ward.shape_vectors`: resampled, z-normalised)."""
    return shape_vectors(list(waveforms), int(resample_length))


def group_key(family, noise_like=False, tested=True):
    """The `group` an event of `family` is written under: the number, `-1` for none,
    the number + `~noise_like` for a family the method flagged no better than noise,
    and the number + `~untested` for a family no null was drawn for (Ward) — so
    Intervals' per-group table says so on its face. An unmarked key is a family that
    was tested and passed."""
    family = int(family)
    if family < 0:
        return "-1"
    if noise_like:
        return f"{family}{NOISE_LIKE_SUFFIX}"
    if not tested:
        return f"{family}{UNTESTED_SUFFIX}"
    return str(family)


# ── the core ────────────────────────────────────────────────────────────────

def _screen(waves, max_nan_frac):
    clean, reasons, filled = {}, {}, 0
    for i, w in enumerate(waves):
        w = np.asarray(w, dtype=float).ravel()
        if w.size == 0:
            reasons[i] = engine.OMIT_MISSING_VALUES
            continue
        if np.isinf(w).any():
            reasons[i] = engine.OMIT_INFINITE_VALUES
            continue
        nan = np.isnan(w)
        if nan.any():
            if nan.all() or nan.mean() > float(max_nan_frac):
                reasons[i] = engine.OMIT_MISSING_VALUES
                continue
            idx = np.arange(w.size)
            w = w.copy()
            w[nan] = np.interp(idx[nan], idx[~nan], w[~nan])
            filled += 1
        clean[i] = w
    return clean, reasons, filled


def coherence_of(waveforms, rows, medoid_row, *, resample_length=RESAMPLE_LENGTH, seed=0,
                 null_draws=COHERENCE_NULL_DRAWS, background=None, n_set=None):
    """W2-B's `svd_entropy` on `waveforms[rows]`, aligned to `medoid_row`;
    with `background` (a `MemberBackground` over the same row numbers as
    `waveforms`) its quiet-stretch null is the verdict (w3-g)."""
    rows = [int(r) for r in rows]
    medoid = rows.index(int(medoid_row)) if int(medoid_row) in rows else None
    return svd_entropy([waveforms[r] for r in rows], medoid=medoid, resample_length=int(resample_length),
                       seed=int(seed), null_draws=int(null_draws),
                       background=None if background is None else background.subset(rows), n_set=n_set)


def _counts(reasons):
    out = {}
    for r in reasons:
        if r is not None:
            out[r] = out.get(r, 0) + 1
    return out


def shape_families(waveforms, *, method=DEFAULT_METHOD, params=None, max_nan_frac=EW.DEFAULT_MAX_NAN_FRAC, seed=0,
                   coherence_null_draws=COHERENCE_NULL_DRAWS, should_cancel=None, background=None,
                   background_note=None):
    """Families of the waveforms by the Library's engine (module docstring).

    waveforms : (n, L) array or a list of 1-D waveforms (any lengths)
    method : a registered `shape-distance` method (`shape_methods()`)
    params : that method's params (its own names; the engine fills the rest)
    max_nan_frac : a waveform with at most this fraction of NaN is gap-filled, above it is `missing_values`
    seed : the coherence null's seed (the method's own seed is in `params`)
    coherence_null_draws : surrogate draws for each family's SVD-entropy null (W2-B's default 5)
    background : a `Working.background_null.MemberBackground` over the same rows as `waveforms` (w3-g): the
        quiet-stretch null of the method's per-family test and of the coherence; None = the trend-kept nulls
    background_note : why there is no background, in words, for the notes (when `background` is None)
    """
    names = shape_methods()
    if method not in names:
        raise ValueError(f"method={method!r} is not a shape-distance grouping method; use one of {names}")
    params = dict(params or {})
    waves = list(waveforms)
    n = len(waves)
    clean, reasons, filled = _screen(waves, max_nan_frac)
    if method == "ward" and len(clean) > WARD_MAX_ITEMS:
        raise ValueError(f"ward builds a square distance matrix over every waveform; {len(clean)} is past its "
                         f"{WARD_MAX_ITEMS} cap. Use hdbscan or kshape, which fit a seeded sample and assign the rest.")
    labels = np.full(n, -1, dtype=np.int64)
    omit = [reasons.get(i) for i in range(n)]
    distance = np.full(n, np.nan)
    notes = []
    if filled:
        notes.append(f"{filled} waveform(s) held a few missing samples (at most {max_nan_frac:g} of the window) and "
                     f"were filled by linear interpolation before grouping")
    if not clean:
        notes.insert(0, "no waveforms to group: " + ("the input is empty" if n == 0 else
                                                     f"all {n} were screened out ({_counts(omit)})"))
        return ShapeFamilies(labels=labels, omit_reason=omit, distance=distance, families=[], omitted=_counts(omit),
                             n=n, n_placed=0, n_confident=0 if n else None, fraction_placed=0.0 if n else None,
                             fraction_confident=0.0 if n else None, method=method, params=params, notes=notes,
                             n_gap_filled=filled)

    items = [{"member_ref": i, "values": w} for i, w in clean.items()]
    res = engine.run_grouping(items, unit=UNIT, basis=BASIS, method=method, params=params,
                              should_cancel=should_cancel,
                              background=None if background is None else background.subset(list(clean)))
    if background is None:
        notes.append("no quiet-stretch null: " + (background_note or "no recording was given to cut quiet windows "
                                                                     "from") + "; every family is judged against "
                     "its trend-kept null, which a smooth window-filling shape can fail without being noise")
    for a in res.assignments:
        if a.family_id is None:
            omit[a.ref] = a.omit_reason
        elif a.distance is not None:
            distance[a.ref] = float(a.distance)

    resample_length = int(params.get("resample_length", RESAMPLE_LENGTH))
    ordered = sorted(res.families, key=lambda f: (-f.size, min(f.members)))
    families = []
    for rank, f in enumerate(ordered, start=1):
        rows = np.array(sorted(int(r) for r in f.members), dtype=np.int64)
        labels[rows] = rank
        coh = coherence_of(clean, rows, f.medoid, resample_length=resample_length, seed=seed,
                           null_draws=coherence_null_draws, background=background, n_set=len(clean))
        families.append(FamilyInfo(family=rank, library_label=f.label, size=int(f.size), rows=rows,
                                   medoid_row=int(f.medoid), medoid_distance=float(f.medoid_distance),
                                   flags=dict(f.flags), coherence=coh, null_trusted=method not in UNTRUSTED_NULLS,
                                   null_caveat=UNTRUSTED_NULLS.get(method)))

    n_placed = int((labels > 0).sum())
    tested = [f for f in families if f.flags.get("tested")]
    untested = len(families) > 0 and not tested
    untrusted = method in UNTRUSTED_NULLS
    n_conf = None if (untested or untrusted) else int(sum(f.size for f in families if f.confident))
    if untested:
        notes.append(f"{method} draws no noise null: its families are not tested against noise of the same colour "
                     f"(fraction_confident is None); read their SVD entropy against its null instead")
    if untrusted:
        notes.append(f"{UNTRUSTED_NULLS[method]}. Its families are not called confident (fraction_confident is None).")
    return ShapeFamilies(
        labels=labels, omit_reason=omit, distance=distance, families=families, omitted=_counts(omit), n=n,
        n_placed=n_placed, n_confident=n_conf, fraction_placed=n_placed / n,
        fraction_confident=None if n_conf is None else n_conf / n, method=method, params=params,
        fit_summary=dict(res.fit_summary), recipe_hash=res.recipe_hash, notes=notes, n_gap_filled=filled)


def event_families(x, fs, spans, *, anchor="start", length_s=DEFAULT_EVENT_LENGTH_S, pre_frac=EW.DEFAULT_PRE_FRAC,
                   max_nan_frac=EW.DEFAULT_MAX_NAN_FRAC, method=DEFAULT_METHOD, params=None, seed=0,
                   coherence_null_draws=COHERENCE_NULL_DRAWS, should_cancel=None):
    """Cut a window around each event of `spans` with W2-A's cutter (`event_windows`,
    `cut`; its anchor / length / pre_frac / max_nan_frac rules), group the windows with
    `shape_families`, and map the families back onto the events. An event the cutter
    left out is `no_window:<its reason>` (past_start, past_end, too_much_nan). Methods in
    `EVENT_FAMILIES_EXCLUDED` are refused with the reason."""
    if method in EVENT_FAMILIES_EXCLUDED:
        raise ValueError(f"method={method!r} is not offered for event families: {EVENT_FAMILIES_EXCLUDED[method]}. "
                         f"Use hdbscan (or ward, whose families are marked untested).")
    ew = EW.event_windows(x, fs, spans, anchor=anchor, length_s=length_s, pre_frac=pre_frac,
                          max_nan_frac=max_nan_frac)
    W = EW.cut(x, ew.starts, ew.length)
    avoid = (list(zip(np.asarray(spans.starts, dtype=np.int64).tolist(), np.asarray(spans.ends, dtype=np.int64).tolist()))
             + [(int(s), int(s) + int(ew.length)) for s in ew.starts])
    bg = span_background(x, fs, ew.starts, ew.length, avoid, seed=seed,
                         avoid_words="every event span and every cut window")
    fam = shape_families(W, method=method, params=params, max_nan_frac=max_nan_frac, seed=seed,
                         coherence_null_draws=coherence_null_draws, should_cancel=should_cancel, background=bg)
    n_ev = len(spans.starts)
    family = np.full(n_ev, -1, dtype=np.int64)
    reason = [OMIT_NO_WINDOW] * n_ev
    for why, rows in ew.omitted_rows.items():
        for r in rows:
            reason[int(r)] = f"{OMIT_NO_WINDOW}:{why}"
    dist = np.full(n_ev, np.nan)
    noise_like = np.zeros(n_ev, dtype=bool)
    tested = np.zeros(n_ev, dtype=bool)
    kept = np.asarray(ew.kept, dtype=np.int64)
    family[kept] = fam.labels
    dist[kept] = fam.distance
    flagged = {f.family for f in fam.families if f.flags.get("noise_like")}
    was_tested = {f.family for f in fam.families if f.flags.get("tested") and f.null_trusted}
    for w, ev in enumerate(kept):
        reason[ev] = fam.omit_reason[w]
        noise_like[ev] = int(fam.labels[w]) in flagged
        tested[ev] = int(fam.labels[w]) in was_tested
    n_conf = fam.n_confident
    return EventFamilies(
        windows=ew, families=fam, family=family, omit_reason=reason, distance=dist, noise_like=noise_like,
        omitted=_counts(reason), n_events=n_ev, tested=tested,
        fraction_placed=(fam.n_placed / n_ev) if n_ev else None,
        fraction_confident=None if (n_conf is None or not n_ev) else n_conf / n_ev)


def span_background(x, fs, starts, length, avoid, *, seed=0, avoid_words="every window"):
    """The quiet-stretch background of a chain's own trace (w3-g): one member per
    window (`starts`, `length`, in the frame of `x`), every window cut where none of
    `avoid` (half-open `(start, end)` in the frame of `x`) and no NaN lies
    (`Working.background_null.MemberBackground` on one recording, the span)."""
    from Working.background_null import MemberBackground
    x = np.asarray(x, dtype=float)
    avoid = [(int(a), int(b)) for a, b in avoid]
    return MemberBackground([("span", int(s), int(s) + int(length)) for s in starts], lambda _rec: x,
                            avoid_of=lambda _rec: avoid, fs_of=lambda _rec: float(fs) if fs else None,
                            seed=seed, avoid_words=avoid_words)


# ── what the blocks print ───────────────────────────────────────────────────

def estimate_seconds(n, method, params):
    """Seconds to group `n` waveforms: the method's own measured estimate (W2-B's
    coefficients, through the engine) plus the coherence (`COHERENCE_SECONDS_PER_ITEM`).
    Ward past `WARD_MAX_ITEMS` is refused by its run, which sees the real count; the
    blocks' estimates only assume one (the adapters' `ASSUMED_SECONDS_PER_ITEM`), so
    a refusal here would be a guess — and the bridge shows a raising estimate as
    "uncalibrated", not in words (W2-E re-critique)."""
    full = {**registry.defaults_for(method), **dict(params or {})}
    # w3-g: each family's coherence draws a quiet-stretch pool of min(n, QUIET_MAX_POOL) windows per null draw;
    # COHERENCE_ESTIMATE_FAMILIES families assumed (the estimate runs before any family exists)
    quiet = (COHERENCE_ESTIMATE_FAMILIES * min(int(n), QUIET_MAX_POOL) * COHERENCE_NULL_DRAWS
             * QUIET_SECONDS_PER_WINDOW)
    return float(engine.estimate_seconds(int(n), BASIS, method, full) + int(n) * COHERENCE_SECONDS_PER_ITEM + quiet)


def family_summary(fam: FamilyInfo):
    """One family as a page reads it: size, the method's flags, the coherence beside its null."""
    c = fam.coherence or {}
    norm, p05 = c.get("svd_entropy_norm"), c.get("null_p05")
    return {
        "family": int(fam.family), "library_label": fam.library_label, "size": int(fam.size),
        "medoid_row": int(fam.medoid_row), "medoid_distance": float(fam.medoid_distance),
        "noise_like": bool(fam.flags.get("noise_like", False)), "unstable": bool(fam.flags.get("unstable", False)),
        "tested": bool(fam.flags.get("tested", False)), "why": fam.flags.get("why"),
        "flags": engine.json_safe(fam.flags),
        # w3-g: which null judged the family, and how much quiet background it had
        "null_kind": fam.flags.get("null_kind"), "background_s": fam.flags.get("background_s"),
        "background": engine.json_safe(fam.flags.get("background")),
        # the researcher's headline (2026-10-14): sigma^2 first; eq. 17 keeps the verdict
        "svd_entropy_squared_first": True,
        "svd_entropy_squared_null_p05": c.get("null_squared_p05"),
        "svd_entropy_squared_beyond_noise": c.get("beyond_noise_squared"),
        "svd_entropy_null_kind": c.get("null_kind"), "svd_entropy_why": c.get("why"),
        "svd_entropy_background": engine.json_safe(c.get("background")),
        "svd_entropy_variants": engine.json_safe(c.get("variants") or []),
        "svd_entropy": c.get("svd_entropy"), "svd_entropy_norm": norm,
        "svd_entropy_null_median": c.get("null_median"), "svd_entropy_null_p05": p05,
        "svd_entropy_squared_norm": c.get("svd_entropy_squared_norm"),
        "svd_entropy_squared_null_median": c.get("null_squared_median"),
        "top_share": c.get("top_share"), "coherence_reason": c.get("reason"),
        # svd_entropy's own verdict (its margin x null_p05) and rule, read off, never re-derived (fix round 1, F3)
        "svd_entropy_beyond_noise": c.get("beyond_noise"), "svd_entropy_null_margin": c.get("null_margin"),
        "svd_entropy_rule": c.get("rule"),
        # True = tested against a trusted null and passed; False = noise-like; None = untested / null not trusted
        "confident": fam.confident,
        "null_caveat": fam.null_caveat,
    }


def rules(method, params):
    """The rule behind every number the family blocks report, as printed in meta."""
    flat = ", ".join(f"{k}={v}" for k, v in sorted(dict(params or {}).items()))
    return [
        {"name": "families", "rule": f"the Library's grouping engine (run_grouping, basis shape-distance, unit "
                                     f"single_motifs) with method {method} ({flat or 'its defaults'}); every "
                                     f"waveform resampled to 256 samples and z-normalised (ward.shape_vectors), so "
                                     f"amplitude does not enter; families renumbered 1..K by size, largest first; "
                                     f"the engine's ten-member floor (min_group) applies"},
        {"name": "omitted", "rule": "an event in no family is -1 with its reason: the method's own (not_in_a_dense_"
                                    "family, past_cut, group_too_small), missing_values / infinite_values (no shape: "
                                    "more NaN than max_nan_frac, or an inf; a few NaN are interpolated and counted), "
                                    "no_window:<the cutter's reason> (past_start, past_end, too_much_nan) or "
                                    "outside_span"},
        {"name": "family_distance", "rule": "the engine's distance from the member to its family's medoid on the "
                                            "method's 0-1 scale: normalised SBD (shape-based distance / 2) for kshape "
                                            "and hdbscan, Ward's normalised scale-invariant distance for ward"},
        {"name": "noise_like", "rule": "the method's own verdict, never re-derived here: hdbscan and kshape compare "
                                       "each family with the chain's own quiet stretches (windows of the members' "
                                       "length cut where no event and no window of the set lies, selection-matched: "
                                       "the members' median distance to their centre must beat 0.7 x the "
                                       "min(5 %, m/2n)-quantile of the quiet windows' distances) wherever at least "
                                       "half the members got such a window; otherwise with trend-kept phase-"
                                       "randomised surrogates of the members (a cubic trend kept, so a smooth "
                                       "window-filling hump or ramp can read noise-like), and each family's "
                                       "null_kind and why say which - the exact rule is fit_summary.null.rule; ward "
                                       "draws no null and reports its families untested"},
        {"name": "svd_entropy", "rule": "per family, W2-B's svd_entropy, its verdict (svd_entropy_beyond_noise) read "
                                        "off, not re-derived: "
                                        + COHERENCE_RULE.format(L=int(dict(params or {}).get("resample_length",
                                                                                              RESAMPLE_LENGTH)),
                                                                aligned=COHERENCE_ALIGNED)},
        {"name": "confident", "rule": "a family is confident only when its method tested it against noise and it "
                                      "passed: Ward draws no null (untested, key '<n>~untested')"
                                      + "".join(f"; {m}: {r}" for m, r in UNTRUSTED_NULLS.items())},
        {"name": "exemplar", "rule": EXEMPLAR_RULE},
    ]


def summary_line(fam: ShapeFamilies, unit_word="event"):
    """`K families (sizes ...) of N <unit>s by <method>; ... in no family; SVD entropy ...`."""
    n = fam.n
    if n == 0:
        return f"no {unit_word}s to group"
    k = fam.k
    if not k:
        why = ", ".join(f"{r} {c}" for r, c in fam.omitted.items())
        return f"no family among {n} {unit_word}(s) by {fam.method}: every one is in no family ({why})"
    sizes = ", ".join(str(f.size) for f in fam.families)
    left = n - fam.n_placed
    parts = [f"{k} famil{'y' if k == 1 else 'ies'} (sizes {sizes}) of {n} {unit_word}(s) by {fam.method}"]
    if left:
        parts.append(f"{left} in no family (" + ", ".join(f"{r} {c}" for r, c in fam.omitted.items()) + ")")
    noisy = [f.family for f in fam.families if f.flags.get("noise_like")]
    if noisy:
        parts.append(f"{len(noisy)} noise-like (no better than noise of the same colour: family "
                     + ", ".join(str(f) for f in noisy) + ")")
    elif fam.families and not any(f.flags.get("tested") for f in fam.families):
        parts.append("not tested against noise (untested)")
    if fam.method in UNTRUSTED_NULLS and fam.families:
        parts.append(f"{fam.method}'s noise null is not trusted: no family is called confident")
    tested = [f for f in fam.families if f.flags.get("tested")]
    fell = [f.family for f in tested if f.flags.get("null_kind") and f.flags.get("null_kind") != QUIET_KIND]
    if tested and any(f.flags.get("null_kind") == QUIET_KIND for f in tested):
        parts.append("judged against the recording's own quiet stretches"
                     + (f" (trend-kept fallback for family " + ", ".join(str(x) for x in fell) + ")" if fell else ""))
    elif tested:
        parts.append("judged against trend-kept noise (no quiet-stretch null)")
    # the researcher's headline (2026-10-14): sigma^2 first, eq. 17 beside it (eq. 17 keeps the verdict)
    sq, ents = [], []
    for f in fam.families:
        c = f.coherence or {}
        if c.get("svd_entropy_norm") is None:
            sq.append("n/a")
            ents.append("n/a")
            continue
        sq.append(f"{c['svd_entropy_squared_norm']:.2f}" + (f" (noise {c['null_squared_p05']:.2f})"
                                                             if c.get("null_squared_p05") is not None else ""))
        ents.append(f"{c['svd_entropy_norm']:.2f}" + (f" (noise {c['null_p05']:.2f})" if c.get("null_p05") is not None
                                                       else ""))
    parts.append("SVD entropy sigma^2 " + ", ".join(sq) + "; eq. 17 (the verdict) " + ", ".join(ents))
    return "; ".join(parts)


def warnings_for(fam: ShapeFamilies):
    out = []
    for f in fam.families:
        bg = f.flags.get("background") or {}
        if f.flags.get("tested") and f.flags.get("null_kind") == TREND_KIND and bg.get("reason"):
            out.append(f"family {f.family}: the quiet-stretch null could not be used ({bg['reason']}); it is judged "
                       f"against trend-kept noise instead, which a smooth window-filling shape can fail without being "
                       f"noise")
        if f.flags.get("noise_like"):
            why = str(f.flags.get("why") or "").replace("no better than noise of the same colour: ", "")
            out.append(f"family {f.family} ({f.size} members) is no better than noise of the same colour: {why}")
        s = family_summary(f)
        if s["svd_entropy_beyond_noise"] is False:
            out.append(f"family {f.family}: its SVD entropy {s['svd_entropy_norm']:.2f} is not below "
                       f"{s['svd_entropy_null_margin']} x what noise like its members scores "
                       f"({s['svd_entropy_null_p05']:.2f}): no more coherent than noise (a smooth shape that fills "
                       f"the window can read so without being noise)")
    return out


def auto_length_warnings(spans, ew, length_s):
    """W2-A's coverage checks. Whatever the length: more than `AUTO_WARN_FRAC` of the
    windows overlapping the next (at the 600 s default, events closer than the window
    share it — the W2-E re-critique). For a caller that asked for the auto length
    (`length_s` 0) also: the length clamped to the floor or the ceiling, and more than
    `AUTO_WARN_FRAC` ending before their event recovered. `(warnings, short phrases for
    the summary)`."""
    if not len(ew.starts):
        return [], []
    warn, short = [], []
    n = len(ew.starts)
    auto = float(length_s) == 0.0
    if auto and ew.length_s <= EW.AUTO_MIN_S:
        warn.append(f"the auto window length is at its {EW.AUTO_MIN_S:g} s floor (twice the median event duration "
                    f"was shorter): a window may hold only the onset. Set length_s (600 s is this block's default).")
        short.append(f"auto window at the {EW.AUTO_MIN_S:g} s floor")
    elif auto and ew.length_s >= EW.AUTO_MAX_S:
        warn.append(f"the auto window length is at its {EW.AUTO_MAX_S:g} s ceiling (most event durations are "
                    f"unmeasured or very long): a window may hold several events. Set length_s (600 s is this "
                    f"block's default).")
        short.append(f"auto window at the {EW.AUTO_MAX_S:g} s ceiling")
    n_ov = int(EW.overlaps_next(ew.starts, ew.length).sum())
    if n_ov > AUTO_WARN_FRAC * n:
        warn.append(f"{n_ov} of {n} windows overlap the next ({ew.length_s:g} s windows): neighbouring events share "
                    f"samples and can make one shape of two. Set length_s shorter.")
        short.append(f"{n_ov} of {n} windows overlap the next")
    n_rec = EW.recovery_outside(spans, ew) if auto else None
    if n_rec is not None and n_rec > AUTO_WARN_FRAC * n:
        warn.append(f"{n_rec} of {n} windows end before their event has recovered (its recovery point lies outside "
                    f"the {ew.length_s:g} s window). Raise length_s if the recovery belongs to the shape.")
        short.append(f"{n_rec} of {n} windows end before the recovery")
    return warn, short
