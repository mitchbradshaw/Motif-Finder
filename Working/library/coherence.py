"""
coherence.py
==============
How much a family's members are copies of one shape: the **SVD entropy** of
its member matrix, used as a per-family shape-coherence score (w2-b).

In plain words: stack a family's members as the rows of a table, each one
resampled to the same length and scaled to the same size. If every row is a
copy of one shape, the table is really one row repeated, and one number
(the first singular value) carries all of it — the entropy is near 0. If the
family is a mixture of two shapes, two numbers share it — the entropy is
higher. The score ignores amplitude (every row is z-normalised), so it
complements the amplitude spread the supervisor already reads: a family can
be tight in shape and loose in size, or the reverse.

The definition (Colominas & Wu 2023, IEEE TSP 71:701-712, eq. 17)
-----------------------------------------------------------------
With sigma_1 >= sigma_2 >= ... the singular values of the P x L member matrix,

    p_i = sigma_i / sum_j sigma_j,      H = - sum_i p_i ln p_i,

i.e. the Shannon entropy of the *normalised singular values* — the primary-
sources check (`docs/research/analysis-blocks-primary-sources.md` section 2,
step 4) records eq. 17 that way, so the singular values are NOT squared here
(squaring would weight by explained variance instead, and make the score
blind to a minority shape). `svd_entropy_norm = H / ln min(P, L)` puts it on
[0, 1]: 0 for one shape, 1 for singular values all equal.

A consequence of not squaring, measured so a reader can calibrate: every
small singular value counts in proportion to itself, not to its square, so the
noise floor under a family weighs heavily. Forty copies of one drop (resampled
from 120-179 samples, 40 x 256) score 0 exactly without noise but about 0.30 at
1 % background noise, 0.62-0.73 at 5 % and 0.76-0.86 at 10 %; a 50/50 mixture of
a drop and a square pulse scores 0.43-0.46, 0.67-0.76 and 0.75-0.83 at the same
levels — so above a few per cent of noise the paper's score no longer separates
a pure family from a mixture. `squared=True` (sigma_i^2, the variance share) is
offered beside it for that comparison; it is not the default because it is not
eq. 17.

The two adaptations
-------------------
* **Alignment** (`align=True`, the default). The paper's cycles are aligned by
  a synchronisation of cyclic shifts; our events are not cycles and do not wrap,
  so each row is instead shifted to its best zero-padded shape-based-distance
  match against the family's medoid (`Working.distances.sbd_matrix`, the same
  alignment k-Shape uses). Without it, copies of one event cut a few seconds
  apart read as a mixture. The medoid is the member with the least summed SBD
  to the others, unless the caller names it (`medoid=`).
  The shifted rows are then **cut to the columns every row still covers** and
  re-z-normalised. That departs from k-Shape, which keeps the zero padding: in
  a z-normalised row the baseline is not 0, so the padding is a step whose
  length differs row to row, and it alone raised the score of 40 shifted exact
  copies of a bump from ~0 to 0.40 (normalised) in the synthetic check. When
  the shifts leave less than `MIN_OVERLAP` (half) of the length in common the
  padded rows are kept, and the rule text says so.
* **Sampling.** The SVD of P x 256 is cheap, but finding the medoid is P^2: at
  most `max_members` (2,000) rows are used, a seeded sample, and the result
  says so (`sampled`, `n_used`).

Rows holding a NaN or an inf have no shape and are left out, counted in
`n_dropped`. A family of fewer than two usable rows has no coherence to
measure: the values are None and `reason` says why.
"""

import numpy as np

from Working.distances import sbd_matrix
from Working.library.grouping.methods.ward import RESAMPLE_LENGTH, shape_vectors

MAX_MEMBERS = 2000
# aligned rows are cut to their common span when it keeps at least this share
MIN_OVERLAP = 0.5

RULE = ("SVD entropy (Colominas & Wu 2023, eq. 17): rows = members resampled to {L} samples and "
        "z-normalised{aligned}; p_i = sigma_i / sum(sigma) over the singular values (not squared); "
        "H = -sum p_i ln p_i; normalised H / ln min(P, L). Near 0 = copies of one shape; higher = "
        "a mixture of shapes. Amplitude does not enter.")


def _z_rows(Y):
    out = Y - Y.mean(axis=1, keepdims=True)
    sd = Y.std(axis=1)
    big = sd > 1e-8
    out[big] /= sd[big, None]
    return out


def _align_to(V, medoid, min_overlap=MIN_OVERLAP):
    """Every row of V shifted to its best SBD match against row `medoid`,
    then cut to the columns EVERY shifted row still covers and re-z-normalised.
    Returns `(rows, shifts, overlap)`, where `overlap` is the fraction of the
    length kept. When the shifts leave less than `min_overlap` in common, the
    rows are kept zero-padded at full length instead (and `overlap` is 1.0 with
    the padding in it — the caller says which)."""
    _, shifts = sbd_matrix(V[medoid:medoid + 1], V, z_normalise=False, return_shifts=True)
    shifts = shifts[0]
    L = V.shape[1]
    src = np.arange(L)[None, :] - shifts[:, None]
    valid = (src >= 0) & (src < L)
    moved = np.where(valid, np.take_along_axis(V, np.clip(src, 0, L - 1), axis=1), 0.0)
    lo = int(max(0, shifts.max()))
    hi = int(L + min(0, shifts.min()))
    if hi - lo >= min_overlap * L:
        return _z_rows(moved[:, lo:hi]), shifts, (hi - lo) / L
    return _z_rows(moved), shifts, None


def svd_entropy(member_matrix, align=True, *, medoid=None, resample_length=RESAMPLE_LENGTH,
                max_members=MAX_MEMBERS, seed=0, squared=False):
    """The SVD-entropy coherence of a family (module docstring).

    `member_matrix` is a 2-D array (one member per row) or a list of 1-D
    waveforms of any lengths; either way each row is resampled to
    `resample_length` and z-normalised (`ward.shape_vectors`). `medoid`, if
    given, is the row index (into `member_matrix`) to align against.
    `squared=True` is NOT the paper's score: it weights by sigma_i^2 (the
    share of variance), which a noise floor barely moves; it exists so the
    two can be compared on real families (module docstring), and the rule
    text says which was used.

    Returns a dict: `svd_entropy`, `svd_entropy_norm` (= H / ln min(P, L)),
    `n_members` (rows given), `n_used` (rows in the matrix), `n_dropped`
    (non-finite rows left out), `sampled`, `aligned`, `medoid_index` (into
    `member_matrix`), `top_share` (p_1, the first singular value's share),
    `rule`, and `reason` (None unless the values are None).
    """
    rows = list(member_matrix) if not isinstance(member_matrix, np.ndarray) else list(member_matrix)
    n_members = len(rows)
    L = int(resample_length)
    keep = [i for i, r in enumerate(rows)
            if np.asarray(r, dtype=float).size > 0 and np.isfinite(np.asarray(r, dtype=float)).all()]
    out = {"svd_entropy": None, "svd_entropy_norm": None, "n_members": n_members,
           "n_used": 0, "n_dropped": n_members - len(keep), "sampled": False,
           "aligned": False, "medoid_index": None, "top_share": None, "overlap": None,
           "rule": RULE.format(L=L, aligned=(", each shifted to its best zero-padded SBD match "
                                             "against the medoid and re-z-normalised" if align else ""))
                   + (" SQUARED VARIANT: p_i = sigma_i^2 / sum(sigma^2) — not eq. 17." if squared else ""),
           "squared": bool(squared),
           "reason": None}

    sampled = len(keep) > int(max_members)
    if sampled:
        rng = np.random.default_rng(seed)
        pick = sorted(rng.choice(len(keep), size=int(max_members), replace=False).tolist())
        if medoid is not None and medoid in keep and keep.index(medoid) not in pick:
            pick[0] = keep.index(medoid)
            pick.sort()
        keep = [keep[i] for i in pick]
    out["sampled"] = bool(sampled)
    out["n_used"] = len(keep)
    if len(keep) < 2:
        out["reason"] = (f"{len(keep)} usable member(s) of {n_members}: a coherence needs at least two"
                         + (f" ({out['n_dropped']} held NaN or inf)" if out["n_dropped"] else ""))
        return out

    V = shape_vectors([rows[i] for i in keep], L)
    if align:
        if medoid is not None and medoid in keep:
            m = keep.index(medoid)
        else:
            D = sbd_matrix(V, z_normalise=False, dtype=np.float32)
            m = int(np.argmin(D.sum(axis=1)))
        V, _, overlap = _align_to(V, m)
        out["aligned"] = True
        out["overlap"] = overlap
        out["rule"] += (f" Aligned rows cut to the {overlap:.0%} of the length every one covers."
                        if overlap is not None else
                        " The shifts left under half the length in common: rows kept zero-padded.")
        out["medoid_index"] = int(keep[m])

    sigma = np.linalg.svd(V, compute_uv=False)
    total = float(sigma.sum())
    if total <= 0.0:
        out["reason"] = "every usable member is flat: no shape to measure"
        return out
    weights = sigma ** 2 if squared else sigma
    p = weights / float(weights.sum())
    nz = p[p > 0]
    H = float(-(nz * np.log(nz)).sum())
    scale = np.log(min(V.shape))
    out.update(svd_entropy=H, svd_entropy_norm=float(H / scale) if scale > 0 else 0.0,
               top_share=float(p[0]))
    return out
