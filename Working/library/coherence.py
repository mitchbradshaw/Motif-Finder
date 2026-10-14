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

i.e. the Shannon entropy of the *normalised singular values*. The paper's own
text (arXiv 2208.06500v2, section 4.3: "the Shannon entropy of the normalized
singular values", p_i = sigma_i / sum sigma) and the primary-sources check
agree, so the headline is NOT squared. `svd_entropy_norm = H / ln min(P, L)`
puts it on [0, 1]: 0 for one shape, 1 for singular values all equal.

A consequence of not squaring, measured so a reader can calibrate: every
small singular value counts in proportion to itself, not to its square, so the
noise floor under a family weighs heavily. Forty copies of one drop score 0
exactly without noise but about 0.30 at 1 % background noise, 0.62-0.73 at 5 %
and 0.76-0.86 at 10 %; a 50/50 mixture of a drop and a square pulse scores
0.43-0.46, 0.67-0.76 and 0.75-0.83 — so above a few per cent of noise the
paper's score no longer separates a pure family from a mixture, and the number
is not comparable between families of different noise levels. Two things
therefore travel beside it (w2-b fix round 1):

* **its own null** — the same score on `NULL_DRAWS` (5) phase-randomised
  surrogates of the members (each row's amplitude spectrum kept, its shape
  destroyed; `kshape.phase_randomised_rows`), aligned the same way:
  `null_median`, `null_p05`. Read the score against it: "noise like these
  members' scores X". A score at or above `null_p05` is no more coherent than
  noise of the same colour.
* **the sigma^2-weighted variant** — `svd_entropy_squared_norm` (p_i =
  sigma_i^2 / sum sigma^2, the share of variance), which a noise floor barely
  moves, with its own null median — and `top_share`, the sigma^2 share of the
  main component (the fraction of the members' variance one shape carries).
  `squared=True` makes the variant the headline; the default stays eq. 17
  until the researcher decides.

The two adaptations
-------------------
* **Alignment** (`align=True`, the default). The paper's cycles are aligned by
  a synchronisation of cyclic shifts; our events are not cycles and do not
  wrap, so each row is instead shifted to its best zero-padded shape-based-
  distance match against the family's medoid (`Working.distances.sbd_matrix`,
  the alignment k-Shape uses), then **padded with its own edge value**
  (replicate) where the shift vacated samples, and re-z-normalised. Without
  alignment copies of one event cut a few seconds apart read as a mixture.
  Zero padding (k-Shape's) is not used: in a z-normalised row the baseline is
  not 0, so the padding is a step whose length differs row to row (it alone
  raised 40 shifted exact copies from ~0 to 0.40). Cutting every row to the
  common span (round 1's rule) let one or two stragglers decide the window for
  the whole family: three noise members in 63 moved the score 0.36 -> 0.57.
  Members whose best shift exceeds a quarter of the length are counted in
  `n_misaligned`. The medoid is the member with the least summed SBD to the
  others, unless the caller names it (`medoid=`) — a caller in a request path
  should, because that search is P^2.
* **Sampling.** At most `max_members` (2,000) rows are used, a seeded sample,
  and the result says so (`sampled`, `n_used`).

Rows holding a NaN or an inf have no shape and are left out, counted in
`n_dropped`. A family of fewer than two usable rows has no coherence to
measure: the values are None and `reason` says why in words.
"""

import numpy as np

from Working.distances import sbd_matrix
from Working.library.grouping.methods.kshape import null_rng, phase_randomised_rows
from Working.library.grouping.methods.ward import RESAMPLE_LENGTH, shape_vectors

MAX_MEMBERS = 2000
NULL_DRAWS = 5                 # the manager's R = 5 surrogates of the members
MISALIGNED_FRACTION = 0.25     # a best shift beyond this share of the length is counted

RULE = ("SVD entropy (Colominas & Wu 2023, eq. 17): rows = members resampled to {L} samples and "
        "z-normalised{aligned}; p_i = sigma_i / sum(sigma) over the singular values (not squared); "
        "H = -sum p_i ln p_i; normalised H / ln min(P, L). Near 0 = copies of one shape; higher = "
        "a mixture of shapes. Amplitude does not enter. Not comparable between families of "
        "different noise levels: read it against null_median / null_p05, the same score on "
        "phase-randomised surrogates of these members.")
ALIGNED = (", each shifted to its best SBD match against the medoid, padded with its own edge "
           "value where the shift vacated samples, and re-z-normalised")
TOP_SHARE_IS = "sigma^2 share of the main component (the fraction of variance one shape carries)"


def _z_rows(Y):
    out = Y - Y.mean(axis=1, keepdims=True)
    sd = Y.std(axis=1)
    big = sd > 1e-8
    out[big] /= sd[big, None]
    return out


def _align_to(V, medoid):
    """Every row of V shifted to its best SBD match against row `medoid`, the
    vacated samples filled with the row's own edge value, re-z-normalised.
    Returns `(rows, shifts)`."""
    _, shifts = sbd_matrix(V[medoid:medoid + 1], V, z_normalise=False, return_shifts=True)
    shifts = shifts[0]
    L = V.shape[1]
    src = np.clip(np.arange(L)[None, :] - shifts[:, None], 0, L - 1)
    return _z_rows(np.take_along_axis(V, src, axis=1)), shifts


def _entropies(V):
    """(H, H_norm, H_squared_norm, sigma^2 share of the first component), or
    None for an all-flat matrix."""
    sigma = np.linalg.svd(V, compute_uv=False)
    if float(sigma.sum()) <= 0.0:
        return None
    scale = np.log(min(V.shape))

    def h(weights):
        p = weights / float(weights.sum())
        nz = p[p > 0]
        return float(-(nz * np.log(nz)).sum())

    H, Hs = h(sigma), h(sigma ** 2)
    norm = (lambda x: float(x / scale) if scale > 0 else 0.0)
    return H, norm(H), norm(Hs), Hs, float(sigma[0] ** 2 / float((sigma ** 2).sum()))


def svd_entropy(member_matrix, align=True, *, medoid=None, resample_length=RESAMPLE_LENGTH,
                max_members=MAX_MEMBERS, seed=0, squared=False, null_draws=NULL_DRAWS):
    """The SVD-entropy coherence of a family (module docstring).

    `member_matrix` is a 2-D array (one member per row) or a list of 1-D
    waveforms of any lengths; either way each row is resampled to
    `resample_length` and z-normalised (`ward.shape_vectors`). `medoid`, if
    given, is the row index (into `member_matrix`) to align against.
    `squared=True` makes the sigma^2-weighted variant the headline (NOT the
    paper's score; the rule text says so).

    Returns a dict: `svd_entropy`, `svd_entropy_norm` (= H / ln min(P, L)),
    `svd_entropy_squared_norm`, `null_median`, `null_p05`,
    `null_squared_median`, `null_draws`, `top_share` (sigma^2 share of the
    main component; `top_share_is` says so), `n_members`, `n_used`,
    `n_dropped`, `n_misaligned`, `sampled`, `aligned`, `padding`,
    `medoid_index` (into `member_matrix`), `squared`, `rule`, `reason` (words;
    None unless the values are None).
    """
    rows = list(member_matrix)
    n_members = len(rows)
    L = int(resample_length)
    keep = [i for i, r in enumerate(rows)
            if np.asarray(r, dtype=float).size > 0 and np.isfinite(np.asarray(r, dtype=float)).all()]
    out = {"svd_entropy": None, "svd_entropy_norm": None, "svd_entropy_squared_norm": None,
           "null_median": None, "null_p05": None, "null_squared_median": None,
           "null_draws": 0, "n_members": n_members, "n_used": 0,
           "n_dropped": n_members - len(keep), "n_misaligned": 0, "sampled": False,
           "aligned": False, "padding": None, "medoid_index": None,
           "top_share": None, "top_share_is": TOP_SHARE_IS,
           "rule": RULE.format(L=L, aligned=ALIGNED if align else "")
                   + (" SQUARED VARIANT as the headline: p_i = sigma_i^2 / sum(sigma^2) — not "
                      "eq. 17." if squared else ""),
           "squared": bool(squared), "reason": None}

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

    V0 = shape_vectors([rows[i] for i in keep], L)
    m = None
    V = V0
    if align:
        if medoid is not None and medoid in keep:
            m = keep.index(medoid)
        else:
            D = sbd_matrix(V0, z_normalise=False, dtype=np.float32)
            m = int(np.argmin(D.sum(axis=1)))
        V, shifts = _align_to(V0, m)
        out.update(aligned=True, padding="edge", medoid_index=int(keep[m]),
                   n_misaligned=int(np.sum(np.abs(shifts) > MISALIGNED_FRACTION * L)))

    scores = _entropies(V)
    if scores is None:
        out["reason"] = "every usable member is flat: no shape to measure"
        return out
    H, Hn, Hsn, Hs, top = scores
    out.update(svd_entropy=Hs if squared else H, svd_entropy_norm=Hsn if squared else Hn,
               svd_entropy_squared_norm=Hsn, top_share=top)

    # the same score on phase-randomised surrogates of these members
    rng = null_rng(seed, 17)
    null, null_sq = [], []
    for _ in range(max(0, int(null_draws))):
        S = _z_rows(phase_randomised_rows(V0, rng))
        if align:
            S, _ = _align_to(S, m)
        s = _entropies(S)
        if s is not None:
            null.append(s[2] if squared else s[1])
            null_sq.append(s[2])
    if null:
        out.update(null_draws=len(null), null_median=float(np.median(null)),
                   null_p05=float(np.percentile(null, 5)),
                   null_squared_median=float(np.median(null_sq)))
    return out
