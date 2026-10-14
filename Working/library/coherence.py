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

* **its own null** — the same score on `NULL_DRAWS` (5) trend-kept
  phase-randomised surrogates of the members (a cubic trend kept per row, the
  rest phase-randomised so its colour is kept and its shape destroyed;
  `kshape.trend_kept_surrogates`, the surrogate HDBSCAN's test uses), aligned
  the same way. Round 1's plain phase surrogates scored 100 pure AR(1) phi 0.99
  windows 0.813 against a null p05 of 0.821 — "more coherent than noise" by a
  hair — because they turn a coloured window's trend into a wiggle (a line kept
  still left it at 0.801 / 0.817; the cubic gives 0.801 / 0.794):
  `null_median`, `null_p05`. Read the score against it: "noise like these
  members' scores X". A score at or above `null_p05` is no more coherent than
  noise of the same colour.
* **the quiet-stretch null** (w3-g; the verdict wherever it is usable) — given
  a `background` (the caller's loader of each member's own recording), the
  same score on quiet windows: per draw a pool of windows of the members' own
  lengths cut from their own recordings where no event lies, the m nearest the
  family's medoid by SBD taken (a family of m found among `n_set` went through
  that selection; the pool is capped at `QUIET_MAX_POOL` and m scaled with it),
  aligned to the medoid as the members were. Unlike the trend-kept surrogate it
  does not keep a smooth window-filling shape's curve, so a broad hump or a
  slow ramp can beat it. Used when at least half the members got a window from
  their own recording; `null_kind`, `nulls`, `background` and `why` say which
  null judged and with how much background. Measured (w3-g, 52 pure-noise
  HDBSCAN families, AR(1) phi 0.95-0.99 and random walk, 200 and 1,000 cut
  windows): eq. 17 at 0.98 x the quiet null's p05 and above (none beyond noise
  at the 0.9 margin); the sigma^2 variant at 0.89 x and above (one of 52 beyond
  noise) — so sigma^2 carries no verdict-shaped field at all (fix round 1,
  F4): `variants[0]` gives its `squared_vs_null_ratio` and `beyond_noise` None.
  **Either null** (fix round 1, the manager's decision 15): `beyond_noise` is
  True when eq. 17 is below 0.9 x the 5th percentile of the quiet-stretch null
  OR of the trend-kept null (`passed_by` lists which). The two have opposite
  blind spots: the trend-kept null cannot see smooth window-filling shapes, and
  the quiet null fails sharp families whose own shape sits uncatalogued in the
  quiet stretches (machine detections are not avoided: they cover most of a
  recording). The pool is n_set up to `QUIET_MAX_POOL` (4,000) so the null
  scores as many rows as the family; above it the family is scored on random
  subsets of the null's row count (`background.family_scored_on` says so).
* **the sigma^2-weighted variant** — `svd_entropy_squared_norm` (p_i =
  sigma_i^2 / sum sigma^2, the share of variance), which a noise floor barely
  moves, with its own null median — and `top_share`, the sigma^2 share of the
  main component (the fraction of the members' variance one shape carries).

  `squared=True` makes the variant the score's headline. The researcher decided
  (2026-10-14) that sigma^2 leads wherever a coherence is shown, eq. 17 beside
  it, the verdict staying on eq. 17: `variants` lists them in that order.

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
  Members whose best shift exceeds `MISALIGNED_FRACTION` (0.4) of the length —
  more than a clean family with edges 20 % off ever needs — are counted in
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
from Working.library.grouping.methods.kshape import (EITHER_KIND, QUIET_KIND, TREND_KIND, batched_shape_vectors,
                                                     null_rng, trend_kept_surrogates)
from Working.library.grouping.methods.ward import RESAMPLE_LENGTH, shape_vectors

MAX_MEMBERS = 2000
NULL_DRAWS = 5                 # the manager's R = 5 surrogates of the members
# A best shift beyond this share of the length is counted in `n_misaligned`.
# Set from clean families (fix round 2): 1,800 members of drop / sharkfin /
# square families, each event edge off by up to 20 % of its window, needed at
# most 0.30 of the length (p99 0.20-0.30); two members each 20 % off can sit
# 0.4 apart, so 0.4 is the most a clean family can need. Round 1's 0.25 counted
# 33 of 100 clean drops.
MISALIGNED_FRACTION = 0.4
# `beyond_noise` = score < NULL_MARGIN x null_p05 — the same placeholder margin HDBSCAN's per-family test uses.
# Without it pure coloured noise read as "more coherent than noise" by a hair (W2-B verification on main,
# 2026-10-14: 100 AR(1) phi 0.99 windows 0.805 vs p05 0.806; a random walk 0.807 vs 0.810).
NULL_MARGIN = 0.9
# The trend-kept surrogate keeps a cubic per row, so a shape that IS a smooth curve across the window (a broad
# hump, a slow ramp) keeps that curve in its own fake noise (the same verification: a ramp's null 0.585 against the
# family's 0.571 at 30 % noise). Said in the rule and in `beyond_noise_note`.
SMOOTH_CAVEAT = ("smooth shapes that fill the window (broad humps, slow ramps) keep their curve in their own "
                 "trend-kept noise and can read as no more coherent than noise: such a reading is not evidence "
                 "that the family is noise")

RULE = ("SVD entropy (Colominas & Wu 2023, eq. 17): rows = members resampled to {L} samples and "
        "z-normalised{aligned}; p_i = sigma_i / sum(sigma) over the singular values (not squared); "
        "H = -sum p_i ln p_i; normalised H / ln min(P, L). Near 0 = copies of one shape; higher = "
        "a mixture of shapes. Amplitude does not enter. Not comparable between families of "
        "different noise levels: read it against null_median / null_p05, the same score on "
        "noise — null_kind says which: the quiet-stretch null (windows of the members' own lengths cut "
        "from their own recordings where no event lies, the m nearest the medoid of a pool of the set's "
        "size taken, aligned the same way; used wherever at least half the members got such a window) "
        "or else trend-kept phase-randomised surrogates of these members; beyond_noise = score < "
        + f"{NULL_MARGIN} x null_p05 (a placeholder margin). Caveat of the trend-kept null: {SMOOTH_CAVEAT}.")
ALIGNED = (", each shifted to its best SBD match against the medoid, padded with its own edge "
           "value where the shift vacated samples, and re-z-normalised")
#: w3-g, the quiet-stretch null: the set a family was found in, when the caller does not say (ten times the family),
#: and the quiet windows cut per draw at most (the pool; above it the nearest-m selection is scaled down with it, so
#: the same share of the pool is taken). 2,000 keeps a Family-page GET at a few seconds cold whatever the family's
#: size (measured 2026-10-14, loaded machine: ~0.3 ms a window cut, resampled and measured; 5 draws).
QUIET_POOL_FACTOR = 10
#: fix round 1 (F1): the pool is n_set up to this, so the null scores as many rows as the family (like for like);
#: the cost is linear and small. Above it the family is scored on `QUIET_SUBSETS` random subsets of the null's
#: row count (the median), `take` floored at `QUIET_MIN_TAKE` (an SVD entropy of two rows means little)
QUIET_MAX_POOL = 4000
QUIET_MIN_TAKE = 10
QUIET_SUBSETS = 5
#: quiet draws for the coherence (F6: the pool is the cost; the trend-kept null keeps `NULL_DRAWS`)
QUIET_NULL_DRAWS = 3
#: seconds per quiet window (cut, resampled to 256, z-normalised, one SBD), measured as above
QUIET_SECONDS_PER_WINDOW = 3.0e-4
TOP_SHARE_IS ="sigma^2 share of the main component (the fraction of variance one shape carries)"


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
                max_members=MAX_MEMBERS, seed=0, squared=False, null_draws=NULL_DRAWS, background=None,
                n_set=None):
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

    w3-g: `background`, optional, a `Working.background_null.MemberBackground`
    over the rows of `member_matrix` (same order), and `n_set`, the size of the
    set the family was found in (default ten times the family): the
    quiet-stretch null (module docstring) becomes the verdict wherever it is
    usable (a family passes on either null; `passed_by` says which), the
    trend-kept one beside it under `nulls`. Also returned: `null_kind`,
    `null_squared_p05`, `passed_by`, `background`
    (the sampler's report, or None), `why` (the verdict in words, naming its
    null and its background seconds) and `variants` (sigma^2 first, then
    eq. 17: the researcher's headline order, 2026-10-14).
    """
    rows = list(member_matrix)
    n_members = len(rows)
    L = int(resample_length)
    keep = [i for i, r in enumerate(rows)
            if np.asarray(r, dtype=float).size > 0 and np.isfinite(np.asarray(r, dtype=float)).all()]
    out = {"svd_entropy": None, "svd_entropy_norm": None, "svd_entropy_squared_norm": None,
           "null_median": None, "null_p05": None, "null_squared_median": None,
           "null_draws": 0, "null_kind": "trend-kept phase-randomised", "n_members": n_members, "n_used": 0,
           "n_dropped": n_members - len(keep), "n_misaligned": 0, "sampled": False,
           "aligned": False, "padding": None, "medoid_index": None,
           "top_share": None, "top_share_is": TOP_SHARE_IS,
           "beyond_noise": None, "null_margin": NULL_MARGIN,
           "null_squared_p05": None, "passed_by": [], "background": None, "why": None,
           "nulls": {"quiet_stretch": None, "trend_kept": None}, "variants": [],
           "headline_variant": "squared", "verdict_variant": "eq17",
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

    # the same score on trend-kept phase-randomised surrogates of these members
    rng = null_rng(seed, 17)
    null, null_sq = [], []
    for _ in range(max(0, int(null_draws))):
        S = _z_rows(trend_kept_surrogates(V0, rng))
        if align:
            S, _ = _align_to(S, m)
        s = _entropies(S)
        if s is not None:
            null.append(s[2] if squared else s[1])
            null_sq.append(s[2])
    trend = _null_summary(null, null_sq, TREND_KIND, out["svd_entropy_norm"], out["svd_entropy_squared_norm"])
    if trend is not None:
        trend["caveat"] = SMOOTH_CAVEAT
    out["nulls"]["trend_kept"] = trend

    quiet = None
    if background is not None and int(null_draws) > 0:
        centre = V0[m] if m is not None else V0[0]
        quiet, report = _quiet_null(V, background, keep, centre, L, align, squared, n_set=n_set, seed=seed)
        out["background"] = report
        out["nulls"]["quiet_stretch"] = quiet

    # decision 15: beyond noise when EITHER null calls it so (the quiet one only where usable)
    passed = [k for k, v in ((QUIET_KIND, quiet), (TREND_KIND, trend)) if v is not None and v["beyond_noise"]]
    shown = (quiet if (quiet is not None and (QUIET_KIND in passed or TREND_KIND not in passed)) else trend)
    if shown is not None:
        out.update(null_kind=EITHER_KIND if quiet is not None else TREND_KIND, null_draws=shown["draws"],
                   null_median=shown["null_median"], null_p05=shown["null_p05"],
                   null_squared_median=shown["null_squared_median"], null_squared_p05=shown["null_squared_p05"],
                   beyond_noise=bool(passed), passed_by=passed)
    out["why"] = _why(out, quiet, trend)
    out["variants"] = _variants(out)
    return out


def _null_summary(null, null_sq, kind, head, sq):
    """The null's numbers, its eq. 17 (headline) verdict, and the sigma^2 score against its own null as a number
    (`squared_vs_null_ratio`) — not a verdict (fix round 1, F4)."""
    if not null:
        return None
    p05 = float(np.percentile(null, 5))
    sq_p05 = float(np.percentile(null_sq, 5))
    return {"kind": kind, "draws": len(null), "null_median": float(np.median(null)), "null_p05": p05,
            "null_squared_median": float(np.median(null_sq)), "null_squared_p05": sq_p05,
            "values": [float(v) for v in null], "squared_values": [float(v) for v in null_sq],
            "beyond_noise": bool(head < NULL_MARGIN * p05),
            "squared_vs_null_ratio": (float(sq / sq_p05) if sq_p05 > 0 else None)}


def _quiet_null(V, background, keep, centre, L, align, squared, *, n_set=None, seed=0):
    """The quiet-stretch null of the coherence (module docstring): per draw
    (`QUIET_NULL_DRAWS`), a pool of quiet windows of the members' own lengths
    from their own recordings (the members cycled to the pool's size), the
    `take` nearest the family's medoid by SBD — the selection a family of m
    found among `n_set` went through — aligned to the medoid as the members
    were, and the same score on them. Like for like (fix round 1, F1): the pool
    is `n_set` up to `QUIET_MAX_POOL`, so `take` = m and the null scores as many
    rows as the family; above the cap `take` = m x pool / n_set (floored at
    `QUIET_MIN_TAKE`), and the family is scored on random subsets of `take` of
    its (aligned) rows, the median of `QUIET_SUBSETS`, for this comparison only.
    `(summary or None, report)`."""
    m = len(keep)
    n_set = max(int(n_set) if n_set else QUIET_POOL_FACTOR * m, m)
    pool = min(n_set, QUIET_MAX_POOL)
    take = m if pool == n_set else max(min(QUIET_MIN_TAKE, m), int(round(m * pool / float(n_set))))
    take = min(take, m, pool)
    rows = [keep[i % m] for i in range(pool)]
    dr = background.draw(rows, QUIET_NULL_DRAWS, salt=17)
    report = dict(dr.report)
    report.update(pool=pool, n_set=n_set, nearest=take, family_rows_scored=take)
    if not dr.usable:
        return None, report
    head = out_head = None
    if take < m:
        rng = np.random.default_rng([int(seed), 23])
        sc, sq_sc = [], []
        for _ in range(QUIET_SUBSETS):
            e = _entropies(V[np.sort(rng.choice(m, size=take, replace=False))])
            if e is not None:
                sc.append(e[2] if squared else e[1])
                sq_sc.append(e[2])
        if sc:
            head, out_head = float(np.median(sc)), float(np.median(sq_sc))
        report["family_scored_on"] = (f"the median of {QUIET_SUBSETS} random subsets of {take} of its {m} rows "
                                      f"(the null's row count: the pool is capped at {QUIET_MAX_POOL})")
    else:
        e = _entropies(V)
        head, out_head = (e[2] if squared else e[1]), e[2]
    null, null_sq = [], []
    c = np.asarray(centre, dtype=float)[None, :]
    for d in range(QUIET_NULL_DRAWS):
        waves = [w for w in dr.windows[d] if w is not None and np.isfinite(np.asarray(w, dtype=float)).all()]
        if len(waves) < 2:
            continue
        B = batched_shape_vectors(waves, L)
        dist = sbd_matrix(B, c, z_normalise=False, dtype=np.float32)[:, 0]
        S = B[np.argsort(dist, kind="stable")[:take]]
        if align:
            S, _ = _align_to(np.vstack([c, S]), 0)
            S = S[1:]
        s = _entropies(S)
        if s is not None:
            null.append(s[2] if squared else s[1])
            null_sq.append(s[2])
    summary = _null_summary(null, null_sq, QUIET_KIND, head, out_head) if head is not None else None
    if summary is None:
        report.update(usable=False, reason="no draw gave two quiet windows to score")
    else:
        summary.update(family_score=head, family_squared_score=out_head, family_rows_scored=take)
    return summary, report


def _why(out, quiet, trend):
    """The verdict in words: which null(s) passed, both numbers, how much background."""
    if out["svd_entropy_norm"] is None:
        return out.get("reason")
    if quiet is None and trend is None:
        return "no null drawn: the coherence is not tested against noise"
    verdict = "more coherent than noise" if out["beyond_noise"] else "no more coherent than noise"
    rep = out.get("background")
    if quiet is not None:
        s = rep.get("background_s")
        amount = f"{s:,.0f} s" if s is not None else f"{rep.get('background_samples', 0):,} samples"
        extra = ""
        if rep.get("n_borrowed"):
            extra += f"; {rep['n_borrowed']} borrowed windows"
        if rep.get("detection_overlap_share") is not None:
            extra += (f"; {rep['detection_overlap_share']:.0%} of the quiet windows overlap a machine detection "
                      f"(not avoided)")
        passed = out.get("passed_by") or []
        return (f"the eq. 17 score is {verdict} — passed by {' and '.join(passed) if passed else 'neither null'} "
                f"(either suffices; {NULL_MARGIN} x a null's 5th percentile); the quiet-stretch null: "
                f"{quiet['family_score']:.3f} against a 5th percentile of {quiet['null_p05']:.3f} ({amount} of "
                f"event-free background on {rep.get('n_recordings', 0)} recording(s); the {rep['nearest']} of "
                f"{rep['pool']} quiet windows nearest the medoid, {quiet['draws']} draws"
                + (f"; the family {rep['family_scored_on']}" if rep.get("family_scored_on") else "") + extra
                + "). Trend-kept null: "
                + (f"{out['svd_entropy_norm']:.3f} against {trend['null_p05']:.3f}" if trend is not None
                   else "not drawn") + ".")
    head = (f"the eq. 17 score {out['svd_entropy_norm']:.3f} is {verdict} ({NULL_MARGIN} x the null's 5th "
            f"percentile {trend['null_p05']:.3f})")
    fallback = (("quiet-stretch null not used: " + str(rep.get("reason")))
                if rep is not None else "quiet-stretch null not available (no recording was given)")
    return f"{head}, against the trend-kept null ({fallback}). Caveat: {SMOOTH_CAVEAT}"


SQUARED_NOTE = ("sigma^2 is reported, not judged: against these nulls it needs a margin of about 0.7 to be safe on "
                "pure noise (W3-G critic), so its ratio to the null's 5th percentile is a number to read; eq. 17 "
                "carries the verdict (the researcher's rule)")


def _variants(out):
    """The two scores as the pages lead with them: sigma^2 first (the researcher's headline, 2026-10-14), eq. 17
    beside it, which carries the verdict. sigma^2 has NO verdict-shaped field (fix round 1, F4)."""
    if out["svd_entropy_squared_norm"] is None:
        return []
    eq17 = not out["squared"]
    sq_p05 = out["null_squared_p05"]
    return [
        {"name": "squared", "label": "sigma^2-weighted (share of variance)", "score": out["svd_entropy_squared_norm"],
         "null_median": out["null_squared_median"], "null_p05": sq_p05, "beyond_noise": None,
         "squared_vs_null_ratio": (out["svd_entropy_squared_norm"] / sq_p05) if sq_p05 else None,
         "note": SQUARED_NOTE, "is_verdict": False},
        {"name": "eq17", "label": "eq. 17 (Colominas & Wu 2023)",
         "score": out["svd_entropy_norm"] if eq17 else None,
         "null_median": out["null_median"] if eq17 else None, "null_p05": out["null_p05"] if eq17 else None,
         "beyond_noise": out["beyond_noise"] if eq17 else None, "is_verdict": True},
    ]
