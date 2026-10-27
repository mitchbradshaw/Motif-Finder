"""
The restitution test: within a train of drops, does an event's recovery depend on the gap before it?

The cardiac name: an action potential that follows a short diastolic interval is shorter (the
"restitution curve", APD against the preceding interval, rises). Here the event is a drop, its
"duration" is the Event shape block's `recovery_time_s` (extremum -> half recovery,
`Working.interrogation.event_shape`), and the interval is the gap from the previous event's onset,
`Working.interrogation.intervals.inter_event_intervals` of the onsets — both imported, not
re-derived, so every number can be read off the site's own measures.

Per sequence:

* pairs (gap before event i, recovery of event i) for i >= 1, an event with no recovery (NaN: not
  reached before the next event) left out and counted; a gap longer than `max_gap` (a break in
  the train) makes no pair;
* rho = Spearman between the two; p from `n_perm` seeded permutations of the gaps within the
  sequence (recovery and its covariates stay paired): two-sided on |rho|, and both one-sided
  tails, each (1 + #{as extreme}) / (1 + n_perm);
* the confound — a deeper (or longer) drop may simply take longer to recover — as a partial
  Spearman controlling for depth (and for the event's index, the shared slow drift a shuffle of
  the gaps does not keep), with the same permutation null.

Across sequences (`combine`), three ways, with the reasons:

* **Stouffer (primary)**, signed: z_i = Phi^-1(1 - p_greater_i), weighted by sqrt(n_pairs_i).
  It keeps the direction (a mixture of strong positive and strong negative rho cancels, as it
  should for a claim of one restitution law) and the strength, and it lets a 60-pair sequence count
  for more than a 5-pair one.
* **Sign count**: how many rho < 0, against Binomial(n, 1/2), two-sided. Robust to any one
  sequence's p and to the permutation's discreteness, but blind to strength.
* **Fisher** on the two-sided p: "is there a relation anywhere", direction-blind; reported, not
  primary, because it is significant when half the sequences go one way and half the other.

Positive rho is restitution in the cardiac sense (a shorter gap, a shorter recovery).
"""

import math

import numpy as np
from scipy import stats

from Working.interrogation.intervals import inter_event_intervals

MIN_PAIRS = 5


def event_pairs(onsets, recovery, depth=None, width=None, max_gap=None, which="before"):
    """Pairs (gap before event i, recovery of event i), i >= 1, in the onsets' own unit.

    `which="after"` is the control: event i's recovery against the gap AFTER it (to the next onset),
    i <= n - 2. Restitution is a claim about the gap before; a recovery that tracks the gap after as
    closely points at the measurement instead — the recovery search stops at the next event, so a
    short gap after censors a long recovery, and gaps that drift slowly make before and after alike.

    `onsets` must be in time order (the gaps come from `inter_event_intervals`, which sorts)."""
    if which not in ("before", "after"):
        raise ValueError(f"event_pairs: which must be 'before' or 'after', got {which!r}")
    on = np.asarray(onsets, float)
    if np.any(np.diff(on) < 0):
        raise ValueError("event_pairs: onsets must be in time order")
    rec = np.asarray(recovery, float)
    gaps = inter_event_intervals(on)
    sel = slice(1, None) if which == "before" else slice(0, -1)
    idx = np.arange(on.size)[sel]
    r = rec[sel]
    keep = np.isfinite(r) & np.isfinite(gaps)
    if max_gap is not None:
        keep &= gaps <= max_gap
    out = dict(gap=gaps[keep], recovery=r[keep], event_index=idx[keep], which=which,
               n_events=int(on.size), n_no_recovery=int((~np.isfinite(rec)).sum()),
               n_long_gap=int(0 if max_gap is None else (gaps > max_gap).sum()))
    for name, v in (("depth", depth), ("width", width)):
        if v is not None:
            out[name] = np.asarray(v, float)[sel][keep]
    if which == "before":                       # each pair's gap after (NaN for the last event)
        after = np.append(gaps[1:], np.nan)
        if max_gap is not None:
            after = np.where(after <= max_gap, after, np.nan)
        out["gap_after"] = after[keep]
    return out


def _rank(x):
    return stats.rankdata(x)


def _resid(y, Z):
    A = np.column_stack([np.ones(len(y)), Z])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return y - A @ coef


def partial_spearman(x, y, Z):
    """Spearman of x and y with the ranks of the columns of Z regressed out of both ranks."""
    Zr = np.column_stack([_rank(z) for z in np.asarray(Z, float).T])
    rx, ry = _resid(_rank(x), Zr), _resid(_rank(y), Zr)
    d = np.sqrt(np.sum(rx * rx) * np.sum(ry * ry))
    return float(np.sum(rx * ry) / d) if d > 0 else float("nan")


def _perm_null(gap, rec, Z, n_perm, rng):
    """(observed, null) partial Spearman of gap and rec given Z (None = plain Spearman), the null over
    permutations of the gaps, vectorised: a permutation of the gaps permutes the gaps' ranks."""
    n = gap.size
    A = np.ones((n, 1)) if Z is None else np.column_stack([np.ones(n)] + [_rank(z) for z in np.asarray(Z, float).T])
    P = np.eye(n) - A @ np.linalg.pinv(A)
    rg = _rank(gap)
    ry = P @ _rank(rec)
    ny = np.sqrt(ry @ ry)

    def corr(RX):
        RX = RX @ P
        d = np.sqrt(np.sum(RX * RX, axis=-1)) * ny
        with np.errstate(invalid="ignore", divide="ignore"):
            return (RX @ ry) / d

    obs = float(corr(rg[None, :])[0])
    perms = np.argsort(rng.random((n_perm, n)), axis=1)
    return obs, corr(rg[perms])


def _perm(gap, rec, Z, n_perm, rng):
    obs, null = _perm_null(gap, rec, Z, n_perm, rng)
    null = null[np.isfinite(null)]
    m = null.size
    return dict(rho=obs, p_two=float((1 + np.sum(np.abs(null) >= abs(obs) - 1e-12)) / (1 + m)),
                p_greater=float((1 + np.sum(null >= obs - 1e-12)) / (1 + m)),
                p_less=float((1 + np.sum(null <= obs + 1e-12)) / (1 + m)), n_perm=int(m))


def restitution(pairs, n_perm=1000, seed=0, min_pairs=MIN_PAIRS):
    """Spearman rho of recovery against the preceding gap, with its within-sequence permutation null,
    and the partial rho controlling for depth (and for depth + event index) where depth is given."""
    gap, rec = pairs["gap"], pairs["recovery"]
    n = int(gap.size)
    base = dict(n_pairs=n, n_events=pairs.get("n_events"), n_no_recovery=pairs.get("n_no_recovery"),
                n_long_gap=pairs.get("n_long_gap"))
    if n < min_pairs or np.ptp(gap) == 0 or np.ptp(rec) == 0:
        return dict(base, rho=None, why=f"{n} usable pairs (needs {min_pairs}, with gaps and recoveries that vary)")
    rng = np.random.default_rng(seed)
    out = dict(base, **_perm(gap, rec, None, n_perm, rng))
    idx = pairs["event_index"].astype(float)
    for key, cov in (("depth", "depth"), ("width", "width")):
        if cov in pairs and np.ptp(pairs[cov]) > 0:
            Z = pairs[cov][:, None]
            out[f"partial_{key}"] = _perm(gap, rec, Z, n_perm, rng)
            Z2 = np.column_stack([pairs[cov], idx])
            out[f"partial_{key}_index"] = _perm(gap, rec, Z2, n_perm, rng)
    out["partial_index"] = _perm(gap, rec, idx[:, None], n_perm, rng)
    ga = pairs.get("gap_after")
    if ga is not None:
        m = np.isfinite(ga)
        if m.sum() >= min_pairs and np.ptp(ga[m]) > 0 and np.ptp(gap[m]) > 0 and np.ptp(rec[m]) > 0:
            out["partial_gap_after"] = _perm(gap[m], rec[m], ga[m][:, None], n_perm, rng)
    out["median_gap"] = float(np.median(gap))
    out["median_recovery"] = float(np.median(rec))
    return out


def combine(results, key=None):
    """Sign count (rho < 0 vs Binomial(n, 1/2)), signed Stouffer weighted by sqrt(n_pairs) (primary)
    and Fisher on the two-sided p, over the sequences with a rho. `key` picks a partial
    (e.g. 'partial_depth') instead of the raw rho."""
    rows = []
    for r in results:
        if r.get("rho") is None:
            continue
        s = r if key is None else r.get(key)
        if s is None or s.get("rho") is None or not np.isfinite(s["rho"]):
            continue
        rows.append((s["rho"], s["p_greater"], s["p_two"], r["n_pairs"]))
    n = len(rows)
    if n == 0:
        return dict(n_sequences=0)
    rho = np.array([r[0] for r in rows])
    pg = np.clip(np.array([r[1] for r in rows]), 1e-12, 1 - 1e-12)
    p2 = np.clip(np.array([r[2] for r in rows]), 1e-300, 1.0)
    w = np.sqrt(np.array([r[3] for r in rows], float))
    z = stats.norm.isf(pg)
    Z = float(np.sum(w * z) / np.sqrt(np.sum(w * w)))
    k_neg = int(np.sum(rho < 0))
    k_pos = int(np.sum(rho > 0))
    n_sign = k_neg + k_pos
    chi = float(-2 * np.sum(np.log(p2)))
    return dict(n_sequences=n, n_rho_negative=k_neg, n_rho_positive=k_pos,
                sign_p_two=float(stats.binomtest(k_neg, n_sign, 0.5).pvalue) if n_sign else float("nan"),
                stouffer_z=Z, stouffer_p_two=float(2 * stats.norm.sf(abs(Z))),
                fisher_chi2=chi, fisher_df=2 * n, fisher_p=float(stats.chi2.sf(chi, 2 * n)),
                median_rho=float(np.median(rho)), weighted_mean_rho=float(np.sum(w * w * rho) / np.sum(w * w)),
                n_p_two_below_0p05=int(np.sum(p2 < 0.05)))


def fmt_p(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "-"
    return f"{p:.2g}" if p >= 1e-3 else f"{p:.1e}"
