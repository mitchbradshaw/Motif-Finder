"""
test_library_background_null.py
=================================
W3-G: a fairer noise test for families — the recording's own quiet stretches as
the null (`Working.background_null.MemberBackground`), used by HDBSCAN's and
k-Shape's per-family tests and by the SVD-entropy coherence, with the trend-kept
null beside it (and as the fallback); k-Shape's plain phase null replaced by the
trend-kept one.

Pinned:
* the sampler: each member's window comes from its own recording at its own
  length, never touches an avoided span or a NaN, is seeded; a member whose
  recording is not on disk, or holds no free stretch that long, borrows and is
  counted; under half "own" the draw is not usable and says why in words;
* smooth shapes (broad humps, slow ramps) on a background that holds none:
  confident against the quiet-stretch null where the trend-kept null calls them
  noise-like — both numbers asserted (HDBSCAN, k-Shape, the coherence);
* no structure, at the defaults, 200 and 1,000 windows cut from quiet stretches
  of pure coloured noise: no family beats the quiet-stretch null, and through
  `interrogation.event_families` no Intervals key is unmarked;
* a recording that is mostly events and a member not on disk: the fallback to
  the trend-kept null is said per family, never silently;
* every verdict's text names its null and its background seconds;
* sigma^2 leads the coherence payload and the summary line; eq. 17 keeps the
  verdict; the background never enters the recipe hash.

Runnable standalone:  python -m pytest tests/test_library_background_null.py
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import pytest
from scipy.signal import lfilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.background_null import QUIET_MIN_SHARE, MemberBackground  # noqa: E402
from Working.Catalogue import shape_families as SF  # noqa: E402
from Working.library.coherence import svd_entropy  # noqa: E402
from Working.library.grouping.engine import run_grouping  # noqa: E402
from Working.library.grouping.methods import kshape as K  # noqa: E402
from Working.types import SpanSet  # noqa: E402

L = 600                      # the families block's default window, 1 Hz


# ── synthetic recordings ─────────────────────────────────────────────────────

def _noise(kind, n, rng):
    e = rng.standard_normal(n)
    if kind == "random_walk":
        b = np.cumsum(e)
        t = np.arange(n)
        b = b - np.polyval(np.polyfit(t, b, 1), t)
    else:
        b = lfilter([1.0], [1.0, -{"ar1_095": 0.95, "ar1_099": 0.99}[kind]], e)
    return b / b.std()


def quiet_recording(kind, n_events, seed=0, frac=0.4, shapes=0, amp=3.0, length=L):
    """`(x, starts)`: pure coloured noise with `n_events` non-overlapping windows of
    `length` covering `frac` of it (so quiet stretches remain between them). The
    first `2 * shapes` windows get a smooth window-filling shape added: a broad hump
    (even ones) or a slow ramp (odd ones), `amp` x the background's spread."""
    rng = np.random.default_rng(seed)
    n = int(n_events * length / frac)
    gaps = rng.dirichlet(np.ones(n_events + 1)) * (n - n_events * length)
    starts = (np.cumsum(gaps[:-1]) + np.arange(n_events) * length).astype(np.int64)
    x = _noise(kind, n, rng)
    t = np.arange(length) / length
    for i, s in enumerate(starts[:2 * shapes]):
        x[s:s + length] += amp * (np.sin(np.pi * t) if i % 2 == 0 else 2.0 * (t - 0.5))
    return x, starts


def _background(x, starts, length=L):
    return MemberBackground([("x", int(s), int(s) + length) for s in starts], lambda _r: x, fs_of=lambda _r: 1.0)


def _group(x, starts, method, params=None, background=True):
    W = [x[s:s + L].copy() for s in starts]
    bg = _background(x, starts) if background else None
    res = run_grouping([{"member_ref": i, "values": w} for i, w in enumerate(W)], unit="single_motifs",
                       basis="shape-distance", method=method, params=params or {}, background=bg)
    return res, W, bg


def _spans(starts, width=140):
    s = [int(v) for v in starts]
    return SpanSet(starts=tuple(s), ends=tuple(v + width for v in s), features=pd.DataFrame({"polarity": [-1] * len(s)}))


# ── the sampler ──────────────────────────────────────────────────────────────

def test_member_windows_come_from_their_own_recording_at_their_own_length_and_avoid_events():
    rng = np.random.default_rng(0)
    a = rng.normal(size=12000)
    b = rng.normal(size=12000) + 100.0                # a recording of another level
    a[2000:2100] = np.nan                             # a gap no window may hold
    members = [("a", 100, 400), ("a", 3000, 3050), ("b", 500, 900)]
    mb = MemberBackground(members, {"a": a, "b": b}.get, fs_of=lambda r: 2.0)
    dr = mb.draw([0, 1, 2], draws=40, salt=3)
    assert dr.source == ["own", "own", "own"] and dr.usable
    for d in range(40):
        w0, w1, w2 = dr.windows[d]
        assert len(w0) == 300 and len(w1) == 50 and len(w2) == 400
        assert np.isfinite(w0).all() and np.isfinite(w1).all()
        assert np.mean(w2) > 50 and np.mean(w0) < 50, "each from its own recording"
    # no window overlaps a member or the gap: find each window's start in its recording
    for d in range(40):
        for j, (rec, s0, e0) in enumerate(members):
            trace = {"a": a, "b": b}[rec]
            w = dr.windows[d][j]
            starts = [s for s in range(len(trace) - len(w) + 1) if trace[s] == w[0] and np.array_equal(trace[s:s + len(w)], w)]
            assert starts, "cut from its own trace"
            s = starts[0]
            for (r2, a2, b2) in members:
                if r2 == rec:
                    assert s + len(w) <= a2 or s >= b2, "never touches a member's span"
    rep = dr.report
    assert rep["n_own"] == 3 and rep["n_borrowed"] == 0 and rep["n_not_on_disk"] == 0
    assert rep["background_s"] == pytest.approx((12000 - 300 - 50 - 100) / 2.0 + (12000 - 400) / 2.0)
    again = mb.draw([0, 1, 2], draws=40, salt=3)
    assert all(np.array_equal(u, v) for du, dv in zip(dr.windows, again.windows) for u, v in zip(du, dv)), "seeded"


def test_off_disk_and_no_room_members_borrow_are_counted_and_the_share_decides():
    rng = np.random.default_rng(1)
    big = rng.normal(size=20000)
    dense = rng.normal(size=3000)
    # `dense` is mostly events: members every 300 samples, 250 long — no free stretch of 250
    members = [("big", 1000, 1500)] + [("dense", s, s + 250) for s in range(0, 2900, 300)] + [("gone", 0, 400)]
    mb = MemberBackground(members, {"big": big, "dense": dense}.get, fs_of=lambda r: 1.0)
    dr = mb.draw(range(len(members)), draws=5)
    rep = dr.report
    assert rep["n_own"] == 1 and rep["n_no_room"] == 10 and rep["n_not_on_disk"] == 1
    assert rep["n_borrowed"] == 11, "borrowed from the recording with room"
    assert not dr.usable and rep["own_share"] < QUIET_MIN_SHARE
    assert "mostly events" in rep["reason"] and "not on disk" in rep["reason"]
    assert all(w is not None and len(w) == 250 for w in dr.windows[0][1:11])
    # a set that is mostly on a quiet recording is usable
    ok = mb.draw([0, 0, 0, 1], draws=2)
    assert ok.usable and ok.report["own_share"] == 0.75


def test_a_recording_whose_only_quiet_stretch_is_one_short_gap_has_no_room():
    """One free tail fits a window a few hundred ways, but every one is a near-copy of
    the next: fewer than QUIET_MIN_DISJOINT non-overlapping windows is no room."""
    from Working.background_null import QUIET_MIN_DISJOINT
    x = np.random.default_rng(4).normal(size=10000)
    members = [("x", s, s + 600) for s in range(0, 9000, 900)]       # a 1,000-sample tail is the widest gap
    dr = MemberBackground(members, lambda _r: x).draw(range(len(members)), draws=3)
    assert dr.report["n_no_room"] == len(members) and not dr.usable
    assert f"fewer than {QUIET_MIN_DISJOINT} non-overlapping" in dr.report["reason"]


def test_sample_background_keeps_its_contract():
    """W3-B's sampler is untouched: its signature and its report's keys."""
    from Working.background_null import sample_background
    x = np.random.default_rng(2).normal(size=1000)
    b = sample_background(x, [(100, 200)], [50], 10, 0, fs=1.0)
    assert {"n_wanted", "n_cut", "n_fallback", "fell_back", "n_too_long", "background_samples", "background_s",
            "trace_samples", "rule"} <= set(b.report)


# ── smooth shapes: the trend-kept null's blind spot ──────────────────────────

@pytest.mark.parametrize("method,params", [("hdbscan", {}), ("kshape", {"k": 2, "n_init": 3})])
def test_humps_and_ramps_beat_the_quiet_null_where_the_trend_kept_null_calls_them_noise(method, params):
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    res, W, _ = _group(x, starts[:200], method, params)        # the 100 humps and the 100 ramps
    big = [f for f in res.families if f.size >= 50]
    assert len(big) >= 2, [(f.size, f.flags["noise_like"]) for f in res.families]
    for f in big:
        fl = f.flags
        q, t = fl["nulls"]["quiet_stretch"], fl["nulls"]["trend_kept"]
        assert fl["null_kind"] == K.EITHER_KIND and K.QUIET_KIND in fl["passed_by"]
        assert q["ratio"] < K.QUIET_MARGIN and not q["noise_like"], (f.size, q, t)
        assert t["noise_like"], ("the trend-kept null's blind spot is real here", t)
        assert not fl["noise_like"], "the verdict is the quiet-stretch one"


def test_hump_coherence_beats_the_quiet_null_where_the_trend_kept_null_does_not():
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    hump_rows = list(range(0, 200, 2))
    mb = _background(x, starts)
    W = [x[s:s + L] for s in starts]
    c = svd_entropy([W[r] for r in hump_rows], medoid=0, background=mb.subset(hump_rows), n_set=len(W))
    q, t = c["nulls"]["quiet_stretch"], c["nulls"]["trend_kept"]
    assert c["null_kind"] == K.EITHER_KIND and c["beyond_noise"] is True, (c["svd_entropy_norm"], q["null_p05"])
    assert c["passed_by"] == [K.QUIET_KIND]
    assert q["beyond_noise"] and not t["beyond_noise"], (c["svd_entropy_norm"], q["null_p05"], t["null_p05"])
    assert c["null_p05"] == q["null_p05"] and c["null_median"] == q["null_median"], "the verdict's null on top"
    json.dumps(c)


# ── no structure, at the defaults ────────────────────────────────────────────

@pytest.mark.parametrize("kind", ["random_walk", "ar1_099"])
@pytest.mark.parametrize("n", [200, 1000])
def test_windows_cut_from_quiet_noise_never_beat_the_quiet_null_hdbscan(kind, n):
    x, starts = quiet_recording(kind, n, seed=5)
    res, W, bg = _group(x, starts, "hdbscan")
    report = [(f.size, f.flags["null_kind"], (f.flags["nulls"]["quiet_stretch"] or {}).get("ratio"))
              for f in res.families]
    assert all(f.flags["null_kind"] == K.EITHER_KIND for f in res.families), report
    assert all(f.flags["passed_by"] == [] for f in res.families), report
    assert all(f.flags["noise_like"] for f in res.families), report
    for f in res.families:
        rows = sorted(f.members)
        c = svd_entropy([W[r] for r in rows], medoid=rows.index(f.medoid), background=bg.subset(rows), n_set=len(W))
        assert c["beyond_noise"] is False, (f.size, c["svd_entropy_norm"], c["null_p05"])


@pytest.mark.parametrize("kind", ["random_walk", "ar1_099"])
def test_windows_cut_from_quiet_noise_never_beat_the_quiet_null_kshape_defaults(kind):
    x, starts = quiet_recording(kind, 200, seed=6)
    res, _, _ = _group(x, starts, "kshape")
    report = [(f.size, f.flags["null_kind"], f.flags["noise_like"]) for f in res.families]
    assert res.families and all(f.flags["noise_like"] for f in res.families), report


@pytest.mark.parametrize("method", ["hdbscan", "kshape"])
@pytest.mark.parametrize("kind,n", [("random_walk", 200), ("ar1_099", 200), ("ar1_095", 200), ("random_walk", 1000)])
def test_event_families_on_quiet_noise_leaves_no_unmarked_intervals_key(method, kind, n):
    x, starts = quiet_recording(kind, n, seed=7)
    spans = _spans(starts + int(0.2 * L))       # the default anchor (start, pre_frac 0.2) puts the window on the slot
    if method in SF.EVENT_FAMILIES_EXCLUDED:
        pytest.skip(f"{method} is not offered for event families: {SF.EVENT_FAMILIES_EXCLUDED[method]}")
    ev = SF.event_families(x, 1.0, spans, method=method)
    keys = sorted({SF.group_key(f, nl, tt) for f, nl, tt in zip(ev.family, ev.noise_like, ev.tested)})
    unmarked = [k for k in keys if k != "-1" and "~" not in k]
    assert unmarked == [], (keys, [(f.size, f.flags.get("null_kind"), f.flags.get("why")) for f in ev.families.families])
    used = {f.flags.get("null_kind") for f in ev.families.families}
    assert used <= {K.EITHER_KIND}, "the span has quiet stretches: both nulls judge (either passes)"


def test_kshape_is_offered_to_event_families_again_and_untrusted_no_more():
    """The decision follows the measurement (prompt item 3): k-Shape's no-structure
    runs pass through event_families at the defaults (the test above), so it is
    neither excluded nor untrusted."""
    assert "kshape" not in SF.EVENT_FAMILIES_EXCLUDED
    assert "kshape" not in SF.UNTRUSTED_NULLS


# ── the fallback, per family, never silent ───────────────────────────────────

def test_a_recording_mostly_events_falls_back_per_family_and_says_so():
    # windows packed with 100-sample gaps: no free stretch as long as a window
    rng = np.random.default_rng(3)
    starts = np.arange(80) * (L + 100) + 50
    x = _noise("random_walk", int(starts[-1] + L + 50), rng)
    res, _, _ = _group(x, starts, "hdbscan")
    for f in res.families:
        fl = f.flags
        assert fl["null_kind"] == K.TREND_KIND and fl["nulls"]["quiet_stretch"] is None
        assert fl["background"]["usable"] is False and "mostly events" in fl["background"]["reason"]
        assert "quiet-stretch null not used" in fl["why"]
    fam = SF.shape_families([x[s:s + L] for s in starts], method="hdbscan",
                            background=_background(x, starts))
    for f in fam.families:
        assert any(w.startswith(f"family {f.family}: the quiet-stretch null could not be used")
                   for w in SF.warnings_for(fam)), SF.warnings_for(fam)


def test_members_not_on_disk_are_counted_and_the_family_falls_back():
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    W = [x[s:s + L].copy() for s in starts[:200]]
    # most members' recordings are gone (a quarter of the humps, none of the ramps, are on disk)
    members = [("x" if i % 8 == 0 else "gone", int(s), int(s) + L) for i, s in enumerate(starts[:200])]
    bg = MemberBackground(members, {"x": x}.get, fs_of=lambda _r: 1.0)
    res = run_grouping([{"member_ref": i, "values": w} for i, w in enumerate(W)], unit="single_motifs",
                       basis="shape-distance", method="hdbscan", background=bg)
    assert res.families
    for f in res.families:
        rep = f.flags["background"]
        assert rep["n_not_on_disk"] > 0 and rep["usable"] is False and "not on disk" in rep["reason"]
        assert f.flags["null_kind"] == K.TREND_KIND


# ── every verdict names its null and its background ──────────────────────────

def test_every_verdict_text_names_its_null_and_its_background_seconds():
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    for method, params in (("hdbscan", {}), ("kshape", {"k": 3, "n_init": 2})):
        res, W, bg = _group(x, starts, method, params)
        assert res.families
        for f in res.families:
            why = f.flags["why"]
            assert "quiet-stretch null" in why and "s of event-free background" in why, why
            assert "trend-kept" in why, "the trend-kept result stays beside it"
            assert f.flags["background_s"] > 0
        json.dumps(res.fit_summary)
        assert res.fit_summary["null"]["kind"] == K.EITHER_KIND
    rows = sorted(res.families[0].members)
    c = svd_entropy([W[r] for r in rows], medoid=0, background=bg.subset(rows), n_set=len(W))
    assert "quiet-stretch null" in c["why"] and "s of event-free background" in c["why"]
    # with no recording, the trend-kept verdict says so
    plain, _, _ = _group(x, starts, "hdbscan", background=False)
    for f in plain.families:
        assert f.flags["null_kind"] == K.TREND_KIND and "no recording was given" in f.flags["why"]
    c0 = svd_entropy([W[r] for r in rows], medoid=0)
    assert c0["null_kind"] == K.TREND_KIND and "no recording was given" in c0["why"]


def test_the_background_is_not_a_setting_it_never_moves_the_recipe_hash():
    x, starts = quiet_recording("random_walk", 120, seed=1)
    with_bg, _, _ = _group(x, starts, "hdbscan")
    without, _, _ = _group(x, starts, "hdbscan", background=False)
    assert with_bg.recipe_hash == without.recipe_hash


# ── k-Shape's trend-kept null ────────────────────────────────────────────────

def test_kshape_without_a_recording_uses_the_trend_kept_null():
    from _shape_families import pure_noise
    res = run_grouping([{"member_ref": i, "values": w} for i, w in enumerate(pure_noise(300, 0, "random_walk"))],
                       unit="single_motifs", basis="shape-distance", method="kshape", params={"k": 3})
    assert res.fit_summary["null"]["kind"] == K.TREND_KIND
    assert all(f.flags["noise_like"] for f in res.families)
    assert all(f.flags["nulls"]["trend_kept"]["kind"] == K.TREND_KIND for f in res.families)


# ── sigma^2 leads; eq. 17 keeps the verdict ──────────────────────────────────

def test_sigma_squared_leads_the_coherence_payload_and_eq17_keeps_the_verdict():
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    rows = list(range(0, 200, 2))
    W = [x[s:s + L] for s in starts]
    c = svd_entropy([W[r] for r in rows], medoid=0, background=_background(x, starts).subset(rows), n_set=300)
    assert [v["name"] for v in c["variants"]] == ["squared", "eq17"]
    assert c["variants"][0]["score"] == c["svd_entropy_squared_norm"] and not c["variants"][0]["is_verdict"]
    assert c["variants"][1]["is_verdict"] and c["variants"][1]["beyond_noise"] == c["beyond_noise"]
    assert c["headline_variant"] == "squared" and c["verdict_variant"] == "eq17"
    # fix round 1, F4: no verdict-shaped field on sigma^2 — the number only
    assert "beyond_noise_squared" not in c and c["variants"][0]["beyond_noise"] is None
    assert c["variants"][0]["squared_vs_null_ratio"] == pytest.approx(
        c["svd_entropy_squared_norm"] / c["nulls"]["quiet_stretch"]["null_squared_p05"])
    assert "not judged" in c["variants"][0]["note"]


def test_the_summary_line_puts_sigma_squared_first_and_names_the_null():
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    fam = SF.shape_families([x[s:s + L] for s in starts], method="hdbscan", background=_background(x, starts))
    line = SF.summary_line(fam)
    assert line.index("sigma^2") < line.index("eq. 17"), line
    assert "quiet stretches" in line, line
    s = SF.family_summary(fam.families[0])
    assert s["null_kind"] == K.EITHER_KIND and s["background_s"] > 0
    assert "svd_entropy_squared_beyond_noise" not in s
    assert s["svd_entropy_variants"][0]["name"] == "squared"


# ── the chain blocks draw from the chain's own trace ─────────────────────────

def test_the_two_family_blocks_judge_against_the_chains_quiet_stretches():
    from Adapters.registry import discover_adapters, get_adapter
    from Working.types import WindowSet
    discover_adapters()
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    sf = get_adapter("catalogue.shape_families")
    ws = WindowSet(starts=starts, length=L, fs=1.0, features=pd.DataFrame({"split": [0] * len(starts)}))
    res = sf.run(x, np.arange(len(x), dtype=float), 1.0, **sf.validate_params({}), value=ws)
    fams = res.meta["families"]
    assert fams and all(f["null_kind"] == K.EITHER_KIND for f in fams), [f["null_kind"] for f in fams]
    assert sum(1 for f in fams if not f["noise_like"]) >= 2, [(f["size"], f["noise_like"]) for f in fams]
    json.dumps(res.meta)
    ef = get_adapter("interrogation.event_families")
    res2 = ef.run(x, np.arange(len(x), dtype=float), 1.0, **ef.validate_params({}), value=_spans(starts + int(0.2 * L)))
    assert all(f["null_kind"] == K.EITHER_KIND for f in res2.meta["families"])
    assert "quiet stretches" in res2.meta["summary"]


# ── cost: the quiet windows are priced ───────────────────────────────────────

def test_the_estimates_price_the_quiet_windows():
    from Working.library.grouping import methods as registry
    for name in ("hdbscan", "kshape"):
        m = registry.get(name)
        base = dict(registry.defaults_for(name))
        assert m.estimate(3616, base) > m.estimate(3616, {**base, "null_draws": 0}), name



# ── fix round 1 (W3-G critic) ────────────────────────────────────────────────

def contaminate(x, starts, n, rng, *, amp, shape="drop"):
    """Add `n` UNCATALOGUED events (a drop, or a broad hump) in the quiet stretches,
    never on a member's window: what a real recording holds besides its Library members."""
    from _shape_families import drop
    t = np.arange(L) / L
    w = amp * (drop((t - 0.3) / 0.4) if shape == "drop" else np.sin(np.pi * t))
    taken = np.zeros(len(x), bool)
    for s in starts:
        taken[s:s + L] = True
    placed, tries = 0, 0
    while placed < n and tries < 100000:
        tries += 1
        s = int(rng.integers(0, len(x) - L))
        if not taken[s:s + L].any():
            x[s:s + L] += w
            taken[s:s + L] = True
            placed += 1
    return placed


def test_the_quiet_margin_is_0_6():
    """Decision 16: 0.6, a placeholder — the critic's worst case, 10-member densest noise
    families, reached 0.714 clean and 0.643 with uncatalogued events."""
    assert K.QUIET_MARGIN == 0.6


def test_either_null_passes_a_family_sharp_via_trend_kept_smooth_via_quiet():
    """Decision 15. The quiet stretches hold 448 uncatalogued drops: the drop family fails
    the quiet null (its own shape is in the 'quiet' windows) but passes the trend-kept one;
    the hump family fails the trend-kept null (smooth) but passes the quiet one. Both are
    confident, and each says which null passed with both ratios."""
    rng = np.random.default_rng(1)
    x, starts = quiet_recording("random_walk", 300, seed=0, frac=0.3)
    from _shape_families import drop
    t = np.arange(L) / L
    for i, s in enumerate(starts[:200]):
        x[s:s + L] += 1.5 * (drop((t - 0.3) / 0.4) if i % 2 == 0 else np.sin(np.pi * t))
    assert contaminate(x, starts, 500, rng, amp=1.5) > 400
    res, _, _ = _group(x, starts[:200], "hdbscan")
    by_kind = {}
    for f in res.families:
        rows = np.array(f.members)
        kind = "drop" if (rows % 2 == 0).all() else "hump" if (rows % 2 == 1).all() else "mixed"
        by_kind[kind] = f
    assert {"drop", "hump"} <= set(by_kind), [(f.size, f.flags["passed_by"]) for f in res.families]
    d, h = by_kind["drop"].flags, by_kind["hump"].flags
    assert d["nulls"]["quiet_stretch"]["noise_like"] and not d["nulls"]["trend_kept"]["noise_like"], d["why"]
    assert not d["noise_like"] and d["passed_by"] == [K.TREND_KIND]
    assert h["nulls"]["trend_kept"]["noise_like"] and not h["nulls"]["quiet_stretch"]["noise_like"], h["why"]
    assert not h["noise_like"] and h["passed_by"] == [K.QUIET_KIND]
    for fl in (d, h):
        assert f"{fl['nulls']['quiet_stretch']['ratio']:.2f}" in fl["why"]
        assert f"{fl['nulls']['trend_kept']['ratio']:.2f}" in fl["why"]
    # the coherence follows the same either rule
    W = [x[s:s + L] for s in starts[:200]]
    bg = _background(x, starts[:200])
    rows = sorted(by_kind["drop"].members)
    c = svd_entropy([W[r] for r in rows], medoid=rows.index(by_kind["drop"].medoid), background=bg.subset(rows),
                    n_set=200)
    q, tk = c["nulls"]["quiet_stretch"], c["nulls"]["trend_kept"]
    assert c["beyond_noise"] == (q["beyond_noise"] or tk["beyond_noise"])
    assert c["passed_by"] == [k for k, v in ((K.QUIET_KIND, q), (K.TREND_KIND, tk)) if v["beyond_noise"]]


@pytest.mark.parametrize("kind", ["random_walk", "ar1_099"])
def test_pure_noise_with_other_shape_contamination_is_not_confident(kind):
    """F3: uncatalogued drops in the quiet stretches loosen the quiet null for pure-noise
    members (the critic: 1.16 -> 0.84). Under the either rule no noise family passes."""
    rng = np.random.default_rng(2)
    x, starts = quiet_recording(kind, 300, seed=0)
    contaminate(x, starts, 150, rng, amp=3.0)
    res, W, bg = _group(x, starts, "hdbscan")
    report = [(f.size, f.flags["passed_by"], f.flags["nulls"]["quiet_stretch"]["ratio"]) for f in res.families]
    assert all(f.flags["noise_like"] for f in res.families), report
    for f in res.families:
        rows = sorted(f.members)
        c = svd_entropy([W[r] for r in rows], medoid=rows.index(f.medoid), background=bg.subset(rows), n_set=len(W))
        assert c["beyond_noise"] is False, (f.size, c["why"])


@pytest.mark.parametrize("kind", ["random_walk", "ar1_099"])
def test_small_densest_noise_families_fail_both_nulls(kind):
    """F5's worst case: among n = 3,600 quiet noise windows, the densest centres' 10 and 20
    nearest windows (the tightest crowds any method could select). Neither null may pass them."""
    from Working.distances import sbd_matrix
    n, m_sizes = 3600, (10, 20)
    x, starts = quiet_recording(kind, n, seed=11, length=200, frac=0.4)
    W = [x[s:s + 200] for s in starts]
    V = K.batched_shape_vectors(W, 128)
    D = sbd_matrix(V, z_normalise=False, dtype=np.float32) / K.SBD_SCALE
    bg = MemberBackground([("x", int(s), int(s) + 200) for s in starts], lambda _r: x)
    for m in m_sizes:
        knn = np.sort(D, axis=1)[:, :m]
        for c in np.argsort(knn.mean(axis=1))[:3]:              # the three densest centres
            rows = np.argsort(D[c])[:m]
            d_F = float(np.median(D[c, rows]))
            d_bg, q, rep = K.quiet_distances(bg, rows.tolist(), V[c], 128,
                                             lambda A, B: sbd_matrix(A, B, z_normalise=False) / K.SBD_SCALE,
                                             n_set=n, salt=int(c))
            _thr, ratio, q_noise, _ = K.quiet_verdict(d_F, d_bg, q, K.QUIET_MARGIN)
            S = K._z_rows(K.trend_kept_surrogates(V[np.repeat(rows, 3)], K.null_rng(0, int(c))))
            p05 = float(np.percentile(sbd_matrix(S, V[c][None], z_normalise=False)[:, 0] / K.SBD_SCALE, 5))
            t_pass = d_F < 0.9 * p05
            assert q_noise and not t_pass, (kind, m, int(c), round(ratio, 3), round(d_F / p05, 3))


def test_quiet_windows_report_their_share_overlapping_machine_detections():
    """F3: detections are not avoided (they cover most of a recording), but the share of
    quiet windows that overlap one is reported."""
    rng = np.random.default_rng(5)
    x = rng.normal(size=60000)
    members = [("x", s, s + 300) for s in range(0, 60000, 6000)]
    dets = [(s, s + 1000) for s in range(3000, 60000, 6000)]          # one detection in every gap
    with_marks = MemberBackground(members, lambda _r: x, mark_of=lambda _r: dets)
    rep = with_marks.draw(range(len(members)), draws=20).report
    assert 0.0 < rep["detection_overlap_share"] < 1.0
    assert "detections" in rep["rule"] and "not avoided" in rep["rule"]
    assert MemberBackground(members, lambda _r: x).draw([0], 2).report["detection_overlap_share"] is None


def test_coherence_null_scores_as_many_rows_as_the_family():
    """F1: pool = n_set up to 4,000, so the null's family has the real family's row count;
    above it the family is scored on random subsets of the null's row count, said in the rule."""
    from Working.library.coherence import QUIET_MAX_POOL
    assert QUIET_MAX_POOL == 4000
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    rows = list(range(0, 200, 2))
    W = [x[s:s + L] for s in starts]
    bg = _background(x, starts).subset(rows)
    c = svd_entropy([W[r] for r in rows], medoid=0, background=bg, n_set=3600)
    rep = c["background"]
    assert rep["pool"] == 3600 and rep["nearest"] == len(rows) and rep["family_rows_scored"] == len(rows)
    big = svd_entropy([W[r] for r in rows], medoid=0, background=bg, n_set=36000)
    rb = big["background"]
    assert rb["pool"] == 4000 and rb["nearest"] == 11 and rb["family_rows_scored"] == 11
    assert "random subsets" in big["rule"] or "random subsets" in big["why"]
    small = svd_entropy([W[r] for r in rows[:30]], medoid=0, background=_background(x, starts).subset(rows[:30]),
                        n_set=36000)
    assert small["background"]["nearest"] == 10, "take is floored at 10"


def test_coherence_quiet_null_draws_three_times():
    """F6: three draws of the quiet pool (the cost is the pool, linear in n_set)."""
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    rows = list(range(0, 200, 2))
    W = [x[s:s + L] for s in starts]
    c = svd_entropy([W[r] for r in rows], medoid=0, background=_background(x, starts).subset(rows), n_set=300)
    assert c["nulls"]["quiet_stretch"]["draws"] == 3 and c["nulls"]["trend_kept"]["draws"] == 5


def test_why_names_borrowed_windows():
    """F8: a usable null that borrowed windows says how many."""
    x, starts = quiet_recording("random_walk", 300, seed=0, shapes=100)
    W = [x[s:s + L].copy() for s in starts[:200]]
    members = [("x" if i % 5 else "gone", int(s), int(s) + L) for i, s in enumerate(starts[:200])]
    bg = MemberBackground(members, {"x": x}.get, fs_of=lambda _r: 1.0)
    res = run_grouping([{"member_ref": i, "values": w} for i, w in enumerate(W)], unit="single_motifs",
                       basis="shape-distance", method="hdbscan", background=bg)
    assert res.families
    for f in res.families:
        n_b = f.flags["background"]["n_borrowed"]
        assert n_b > 0 and f"{n_b} borrowed" in f.flags["why"], f.flags["why"]
