"""
blend.py
========
The confidence formula: R4's score, reinforced by every other source that agrees.

In plain words
--------------
Think of witnesses. R4 always gives its view of a candidate (how likely the researcher is to accept it). Every
other source that points at the same stretch closes part of the remaining gap to certainty, more for a source that
has been right more often. A source's measured precision is halved before it is used (``DAMPING``) because R4
learned from these same detectors' proposals, so their agreement with it is not fully independent evidence.

    confidence = 1 - (1 - p_R4) x  product over agreeing sources s of (1 - DAMPING x precision_s)

Agreement can only raise confidence. A candidate R4 found on its own (the window scan, no other source) keeps
p_R4. Worked example: R4 0.10, drop v1 (0.955) agrees -> 0.10 + 0.90 x 0.4775 = 0.53; a seed (0.9) agrees as well
-> 0.53 + 0.47 x 0.45 = 0.74.

The precisions are the thesis's M2_aug estimates (Table 6.x, ``tab:precision``: drop v1 95.5 %, drop v5 81.2 %,
wavelet-encoded 86.2 %, BEADS inverted 67.5 %), used as one global value per detector. Seed matches count as 0.9:
the one seed whose matches were judged blind scored 99.6 % (455 of 457), and the new medoid seeds are untested, so
the value is conservative. Agreed with the researcher 2026-11-19 (grilling round 2, Q10 (a)); the weights are to be
fitted later from verdicts on auto-detect's own output.
"""

from __future__ import annotations

import numpy as np

#: Source -> the precision the formula reads. Keys are source names as `candidates` writes them.
PRECISION = {
    "drop_detection_v1": 0.955,
    "drop_detection_v5": 0.812,
    "wavelet_encoded": 0.862,
    "BEADs_invert_detect_v1": 0.675,
    "seed": 0.9,
    # BEADS 60 s -> 10 sigma rolling threshold (added 2026-11-23, Q3): never graded blind, so a provisional value
    # between BEADS-invert and drop v5 (Q5 (a)), to be refitted from verdicts on auto-detect's own candidates.
    "beads_sigma": 0.75,
    # the researcher's own event rule as a finder (`finder.py`, 2026-11-23): it proposes boxes and never vouches, so a
    # candidate it alone found keeps R4's score
    "event_rule": 0.0,
}

#: Each source's precision is multiplied by this before it closes the gap (R4 learned from these detectors).
DAMPING = 0.5

#: The source name of R4's own window scan; it never reinforces (R4 already scores every candidate's own span).
R4_SCAN = "r4_scan"


def lift(source, precision=None, damping=DAMPING):
    """The share of the remaining gap one agreeing ``source`` closes: ``damping x precision``."""
    table = PRECISION if precision is None else precision
    if source not in table:
        raise KeyError(f"no precision for source {source!r}; known: {sorted(table)}")
    p = float(table[source])
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"precision of {source!r} must lie in [0, 1], got {p}")
    return float(damping) * p


def confidence(p_r4, sources, precision=None, damping=DAMPING):
    """The blended confidence of one candidate.

    ``p_r4`` is R4's probability for the candidate's own span (NaN when R4 could not read it, which counts as 0:
    the other sources still speak). ``sources`` is the set of sources that agree with it; ``r4_scan`` is ignored.
    """
    p = 0.0 if p_r4 is None or not np.isfinite(p_r4) else float(np.clip(p_r4, 0.0, 1.0))
    gap = 1.0 - p
    for s in sorted(set(sources) - {R4_SCAN}):
        gap *= 1.0 - lift(s, precision, damping)
    return 1.0 - gap


def contributions(p_r4, sources, precision=None, damping=DAMPING):
    """How the confidence was built, in the order the formula applies it: ``[(step, confidence after it)]``,
    R4 first, then each agreeing source alphabetically. The last value equals `confidence`."""
    p = 0.0 if p_r4 is None or not np.isfinite(p_r4) else float(np.clip(p_r4, 0.0, 1.0))
    out = [("r4", p)]
    gap = 1.0 - p
    for s in sorted(set(sources) - {R4_SCAN}):
        gap *= 1.0 - lift(s, precision, damping)
        out.append((s, 1.0 - gap))
    return out


def floor_of(sources, precision=None, damping=DAMPING):
    """The least confidence a candidate with these agreeing sources can have (R4 at 0)."""
    return confidence(0.0, sources, precision, damping)
