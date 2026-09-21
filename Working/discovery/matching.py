"""
matching.py
===========
Spec §4.6 — the one rule that decides whether a machine detection and a
human span are the same event.

    Reciprocal overlap **IoU ≥ 0.5** with onset agreement scaled to the
    candidate's own duration — not an absolute tolerance, since durations
    here run from seconds to hours. The rule is recorded on the run, because
    the precision figure is a function of it and an unstated matching rule
    makes the metric unfalsifiable.

Two halves, and the second is the one an implementation loses by accident:

1. **Reciprocal overlap.** ``Working.database.similarity.interval_iou`` — the
   single interval-overlap definition in the codebase, imported rather than
   rewritten.
2. **Onset agreement.** ``|start_candidate − start_reference| ≤ onset ×
   duration(candidate)``. The *candidate* owns the scale: a four-hour drop
   may start twenty minutes out and still be the same event; a forty-second
   spike may not start ten seconds out.

The candidate is always the first argument — the machine's span, the thing
being scored. Passing the human span first silently changes the tolerance.

The defaults live in **one** place, Settings › Analysis defaults (§9.5, page
``analysis-defaults``, keys ``iou`` and ``onset``); ``rule_from_settings``
reads them so no caller hard-codes 0.5. Changing them is a versioned act
(§4.6), which is why every result carries the rule it was computed under.

Headless: pure functions over ``(start, end)`` sample pairs, in whatever
index space the caller uses — both sides must be in the same one (for
``detections`` that is channel-absolute since 2026-09-21).
"""

from Working.database.similarity import interval_iou

#: The one supported criterion, recorded alongside every figure computed
#: under it. ``Working.compare.OVERLAP_CRITERION`` ('interval_iou') is the
#: older, overlap-only criterion and stays available there.
MATCHING_RULE = "reciprocal_iou_onset"

#: Spec §4.6's defaults, used when Settings has saved nothing.
DEFAULT_IOU = 0.5
DEFAULT_ONSET_FRACTION = 0.25

SETTINGS_PAGE = "analysis-defaults"
IOU_KEY = "iou"
ONSET_KEY = "onset"


def _check(name, value, lo, hi):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"the matching rule's {name!r} must be a number, got {value!r}") from None
    if not (lo <= v <= hi):
        raise ValueError(f"the matching rule's {name!r} must be between {lo} and {hi}, got {v}")
    return v


def normalise_rule(rule=None):
    """A complete rule dict from a partial one (or None).

    Accepts ``{'iou': ..., 'onset': ...}`` with either key missing, and
    refuses a value outside its range loudly — a precision figure computed
    under an impossible rule is worse than no figure.
    """
    rule = dict(rule or {})
    iou = _check(IOU_KEY, rule.get(IOU_KEY, DEFAULT_IOU), 0.0, 1.0)
    onset = _check(ONSET_KEY, rule.get(ONSET_KEY, DEFAULT_ONSET_FRACTION), 0.0, 10.0)
    criterion = rule.get("criterion", MATCHING_RULE)
    if criterion != MATCHING_RULE:
        raise ValueError(f"criterion must be {MATCHING_RULE!r}, got {criterion!r}")
    return {"criterion": MATCHING_RULE, IOU_KEY: iou, ONSET_KEY: onset}


def rule_from_settings(conn):
    """The project's matching rule: Settings › Analysis defaults, else §4.6's
    defaults. The single place the default is read from."""
    from Working.registration.settings import get_settings

    saved = get_settings(conn, SETTINGS_PAGE)
    return normalise_rule({k: saved[k] for k in (IOU_KEY, ONSET_KEY) if k in saved})


def match_quality(candidate, reference, *, iou_threshold=None, onset_fraction=None, rule=None):
    """Both halves of §4.6 for one pair, with the numbers behind the verdict.

    Parameters
    ----------
    candidate : (int, int)
        The machine's span — **and the one whose duration sets the onset
        tolerance**.
    reference : (int, int)
        The human's span.
    iou_threshold, onset_fraction : float, optional
        Override one half; anything unset comes from `rule`, then §4.6.
    rule : dict, optional
        A rule dict as `normalise_rule` returns.

    Returns
    -------
    dict
        ``{iou, onset_gap, onset_tolerance, ok, reason, rule}``. ``reason`` is
        empty when the pair matches and names the failing half otherwise.
    """
    base = normalise_rule(rule)
    if iou_threshold is not None:
        base[IOU_KEY] = _check(IOU_KEY, iou_threshold, 0.0, 1.0)
    if onset_fraction is not None:
        base[ONSET_KEY] = _check(ONSET_KEY, onset_fraction, 0.0, 10.0)

    c_start, c_end = int(candidate[0]), int(candidate[1])
    r_start, r_end = int(reference[0]), int(reference[1])
    duration = max(0, c_end - c_start)
    iou = interval_iou(c_start, c_end, r_start, r_end)
    gap = abs(c_start - r_start)
    tolerance = base[ONSET_KEY] * duration

    reason = ""
    if iou < base[IOU_KEY]:
        reason = (f"reciprocal overlap IoU {iou:.3f} < {base[IOU_KEY]:.2f}")
    elif gap > tolerance:
        reason = (f"onset gap {gap} samples > the {tolerance:.1f}-sample tolerance "
                  f"({base[ONSET_KEY]:g} × the candidate's {duration} samples)")
    return {"iou": float(iou), "onset_gap": int(gap), "onset_tolerance": float(tolerance),
            "ok": not reason, "reason": reason, "rule": base}


def spans_match(candidate, reference, *, iou_threshold=None, onset_fraction=None, rule=None):
    """`match_quality(...)['ok']` — the rule as a predicate."""
    return match_quality(candidate, reference, iou_threshold=iou_threshold,
                         onset_fraction=onset_fraction, rule=rule)["ok"]


def match_span_sets(candidates, references, *, iou_threshold=None, onset_fraction=None, rule=None):
    """Pair two span sets one-to-one under §4.6.

    Every qualifying pair is ranked by IoU and taken greedily, best first, so
    a reference is claimed by the candidate that fits it best rather than by
    whichever happened to be listed first. Ties break on the candidate index
    then the reference index, which makes the result a function of the inputs
    alone — two runs of the same data give byte-identical pairings.

    "Reducing duplicate detections of the same motif is the priority it
    serves" (§4.6): a second candidate over the same reference stays in
    ``candidate_only``, where the scoreboard counts it as a false positive.

    Returns
    -------
    dict
        ``{pairs: [{candidate, reference, iou, onset_gap}], candidate_only:
        [i], reference_only: [j], rule: {...}}`` — indices into the input
        lists, both remainder lists ascending.
    """
    base = normalise_rule(rule)
    if iou_threshold is not None:
        base[IOU_KEY] = _check(IOU_KEY, iou_threshold, 0.0, 1.0)
    if onset_fraction is not None:
        base[ONSET_KEY] = _check(ONSET_KEY, onset_fraction, 0.0, 10.0)

    scored = []
    for i, c in enumerate(candidates):
        for j, r in enumerate(references):
            q = match_quality(c, r, rule=base)
            if q["ok"]:
                scored.append((-q["iou"], i, j, q))
    scored.sort(key=lambda s: (s[0], s[1], s[2]))

    taken_c, taken_r, pairs = set(), set(), []
    for _, i, j, q in scored:
        if i in taken_c or j in taken_r:
            continue
        taken_c.add(i)
        taken_r.add(j)
        pairs.append({"candidate": i, "reference": j, "iou": q["iou"], "onset_gap": q["onset_gap"]})
    pairs.sort(key=lambda p: p["candidate"])
    return {
        "pairs": pairs,
        "candidate_only": [i for i in range(len(candidates)) if i not in taken_c],
        "reference_only": [j for j in range(len(references)) if j not in taken_r],
        "rule": base,
    }
