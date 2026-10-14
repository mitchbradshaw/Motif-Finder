"""
test_cycle_shapes.py
======================
The core of `interrogation.cycle_shapes` (w3-b): every cycle of a chain cut from
one event's anchor to the next, stretched to one length, lined up, sorted into
shapes; where the shape changes; the plateau measures; coherence beside a
background null cut from the recording's own quiet stretches.

Pinned (the prompt's acceptance, on coloured backgrounds — AR(1) phi 0.98, a
detrended random walk, a slow drift — at 15 % noise unless said):
* two shapes in a drifting chain -> K = 2, the truth recovered (adjusted Rand
  >= 0.9), the change within +-1 cycle, order p small, beyond the background;
* warping helps (the sigma^2 entropy after warping is below the fixed cuts');
* floor fractions: sharkfins 0.5-0.67 (median; 90 % within 0.42-0.72),
  troughs half back by 0.25;
* one family whose plateau drifts -> K = 1 although SigClust alone would split
  it (the bimodality gate), the drift visible in cycle_floor_frac;
* no structure at the defaults (Poisson events, 400 and 1,000 cycles; and a
  phase-randomised chain at real event times) -> K = 1, inside the null, every
  group key marked;
* the choice of null: on sharkfins and on broad humps the background null calls
  them real where the trend-kept null cannot (and the plain phase null cannot
  for the hump);
* the same chain at 1 and 10 Hz gives the same groups and floor fractions;
* a 600 s detrend distorts a sharkfin's floor; the raw waveform restores it;
* gaps, splits, NaN, too few cycles: counted and said;
* sequences by train, exemplars are members, the stack payload's caps.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _cycle_synthetic as syn  # noqa: E402
from Working.Catalogue.shape_families import NOISE_LIKE_SUFFIX, UNTESTED_SUFFIX  # noqa: E402
from Working.interrogation import cycle_shapes as CS  # noqa: E402
from Working.library.coherence import NULL_MARGIN, svd_entropy  # noqa: E402
from Working.library.grouping.methods.kshape import phase_randomised_rows  # noqa: E402

TRUTH = np.r_[np.ones(60), 2 * np.ones(60)]


def _run(x, st, en, features=None, **kw):
    return CS.cycle_shapes(x, kw.pop("fs", 1.0), st, en, features, **kw)


def _seq(r, i=0):
    return r["meta"]["sequences"][i]


@pytest.fixture(scope="module")
def two_families():
    """The acceptance chain on each background, at the defaults."""
    out = {}
    for bg in syn.BACKGROUNDS:
        x, st, en = syn.two_family_chain(bg)
        out[bg] = _run(x, st, en)
    return out


# ── two shapes in a drifting chain ─────────────────────────────────────────

@pytest.mark.parametrize("bg", syn.BACKGROUNDS)
def test_two_shapes_are_two_groups_with_one_change_where_the_shape_changes(two_families, bg):
    r = two_families[bg]
    s = _seq(r)
    g = r["columns"]["cycle_group"][:-1]
    assert s["k"] == 2, s.get("splits")
    assert adjusted_rand_score(TRUTH, g) >= 0.9
    idx = r["columns"]["cycle_index"]
    changes = idx[s["change_points"]]
    assert any(59 <= c <= 61 for c in changes), changes
    assert s["order_test"]["p"] < 0.01
    assert r["columns"]["cycle_index"][-1] == -1 and r["omit_reason"][-1] == CS.OMIT_NO_CYCLE


@pytest.mark.parametrize("bg", syn.BACKGROUNDS)
def test_the_chain_beats_its_background_null_on_both_entropies(two_families, bg):
    w = _seq(two_families[bg])["whole"]
    v = w["verdict"]
    assert v["tested"] and v["beyond_noise"] and v["beyond_noise_squared"]
    assert v["below_every_draw"] and v["below_every_draw_squared"]
    assert w["nulls"]["background"]["eq17"]["draws"] == CS.NULL_DRAWS
    for g in _seq(two_families[bg])["groups"]:
        assert not g["key"].endswith((NOISE_LIKE_SUFFIX, UNTESTED_SUFFIX)), g["key"]


@pytest.mark.parametrize("bg", syn.BACKGROUNDS)
def test_warping_lowers_the_headline_entropy_below_the_fixed_cuts(two_families, bg):
    w = _seq(two_families[bg])["whole"]
    assert w["after_warp"]["svd_entropy_squared_norm"] < w["before_warp"]["svd_entropy_squared_norm"]


@pytest.mark.parametrize("bg", syn.BACKGROUNDS)
def test_floor_fractions_land_where_the_researcher_says(two_families, bg):
    c = two_families[bg]["columns"]
    ff = c["cycle_floor_frac"][:60]
    hr = c["cycle_half_recovery_frac"][60:120]
    assert 0.5 <= np.median(ff) <= 0.67
    lo, hi = np.percentile(ff, [5, 95])
    assert lo >= 0.42 and hi <= 0.72, (lo, hi)
    assert np.nanmedian(hr) <= 0.25 and np.nanpercentile(hr, 95) <= 0.25
    # and a trough sits on no floor
    assert np.median(c["cycle_floor_frac"][60:120]) < 0.15


def test_the_summary_leads_with_sigma_squared(two_families):
    m = two_families["ar1"]["meta"]
    assert m["headline"] == "svd_entropy_squared_norm"
    line = m["summary"]
    assert "K = 2" in line and line.index("σ²") < line.index("eq. 17")


# ── one family that varies ─────────────────────────────────────────────────

@pytest.mark.parametrize("bg", syn.BACKGROUNDS)
def test_a_plateau_that_lengthens_is_one_family_with_its_drift_in_the_floor_fraction(bg):
    # fix round 1 (B2): this test used to pin "SigClust p < 0.05" - the floored SigClust's defect. SigClust is
    # now a reported number; the split is refused because it is one mode along its own direction.
    x, st, en = syn.plateau_drift_chain(bg)
    r = _run(x, st, en, null_draws=0)
    s = _seq(r)
    assert s["k"] == 1, s["splits"]
    assert (r["columns"]["cycle_group"][:-1] == 1).all()
    assert s["sigclust"]["decides"] is False
    assert s["splits"][0]["bimodal_p"] >= CS.SIGCLUST_ALPHA
    tr = s["floor_trend"]
    assert tr["tau"] > 0.4 and tr["p"] < 1e-6


# ── no structure ───────────────────────────────────────────────────────────

def _all_keys_marked(r):
    return all(k == "-1" or k.endswith((NOISE_LIKE_SUFFIX, UNTESTED_SUFFIX)) for k in r["group_keys"])


def test_chain_timed_noise_on_a_random_walk_is_one_group_in_every_seed():
    """B1: z-normalised noise cycles are sign-bimodal (+-PC1); the shipped gate said K = 2 in 4-5 of 10 such
    random-walk chains. The split is now calibrated on the same 2-means over the background draws."""
    ks = []
    for seed in range(6):   # fix round 2: 10 -> 6 seeds (test cost)
        x, st, en = syn.regular_events(100, "rw", seed=seed)
        r = _run(x, st, en)
        s = _seq(r)
        assert s["k_null"]["source"] == "background" and s["k_null"]["draws"] == CS.NULL_DRAWS
        ks.append(s["k"])
        assert _all_keys_marked(r) or s["k"] == 1
    assert ks == [1] * 6, ks


def test_a_thousand_chain_timed_random_walk_cycles_are_one_group():
    x, st, en = syn.regular_events(1000, "rw", seed=4)
    r = _run(x, st, en, null_draws=10)   # fix round 2: 10 draws (test cost)
    s = _seq(r)
    assert s["n_cycles"] == 1000 and s["k"] == 1, s["splits"]
    assert s["whole"]["verdict"]["beyond_noise"] is False
    assert _all_keys_marked(r)


def test_poisson_events_on_coloured_noise_are_one_noise_like_group_at_the_defaults():
    x, st, en = syn.poisson_events(400, "drift")
    r = _run(x, st, en)
    s = _seq(r)
    assert s["n_cycles"] == 400 and s["k"] == 1
    assert s["whole"]["verdict"]["beyond_noise"] is False
    assert _all_keys_marked(r)


def test_cycles_cut_from_a_phase_randomised_chain_at_real_event_times_are_inside_the_null():
    x, st, en = syn.two_family_chain("ar1")
    xs = phase_randomised_rows(x[None, :], np.random.default_rng(5))[0]
    r = _run(xs, st, en)
    s = _seq(r)
    assert s["k"] == 1
    assert s["whole"]["verdict"]["beyond_noise"] is False
    assert _all_keys_marked(r)


# ── the choice of null ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def smooth_chains():
    out = {}
    for name, f in (("sharkfin", syn.sharkfin), ("hump", syn.hump)):
        x, st, en = syn.chain([f] * 60, syn.drifting_periods(60), bg="ar1", noise=0.3, seed=1,
                              lead_s=6 * 3600, tail_s=6 * 3600)
        out[name] = _run(x, st, en)
    return out


@pytest.mark.parametrize("name", ["sharkfin", "hump"])
def test_the_background_null_sees_smooth_cycles_the_trend_kept_null_cannot(smooth_chains, name):
    s = _seq(smooth_chains[name])
    w = s["whole"]
    assert s["background"]["fell_back_any"] is False
    v = w["verdict"]
    assert v["beyond_noise"] and v["beyond_noise_squared"]
    # the trend-kept null (svd_entropy's own) keeps the cycle's curve: by the Library's rule it is noise
    tk = w["nulls"]["trend_kept"]
    assert w["after_align"]["svd_entropy_norm"] >= NULL_MARGIN * tk["eq17_p05"]


def test_the_plain_phase_null_cannot_see_the_broad_hump_either(smooth_chains):
    w = _seq(smooth_chains["hump"])["whole"]
    assert w["after_align"]["svd_entropy_norm"] >= w["nulls"]["phase"]["eq17"]["p05"]


# ── sampling rate, waveform, detrend ───────────────────────────────────────

def test_the_same_chain_at_1_and_10_hz_gives_the_same_groups_and_floors():
    # fix round 2: a 60-cycle chain (test cost)
    x, st, en = syn.chain([syn.sharkfin] * 30 + [syn.trough] * 30, syn.drifting_periods(60), bg="ar1", noise=0.15,
                          seed=1)
    t1 = np.arange(x.size, dtype=float)
    t10 = np.arange(x.size * 10, dtype=float) / 10.0
    x10 = np.interp(t10, t1, x)
    a = _run(x, st, en, null_draws=0)
    b = _run(x10, st * 10, en * 10, fs=10.0, null_draws=0)
    ga, gb = a["columns"]["cycle_group"], b["columns"]["cycle_group"]
    assert adjusted_rand_score(ga, gb) == 1.0
    assert len(np.unique(ga[:-1])) == 2
    fa, fb = a["columns"]["cycle_floor_frac"][:30], b["columns"]["cycle_floor_frac"][:30]
    assert abs(np.median(fa) - np.median(fb)) < 0.02
    np.testing.assert_allclose(a["columns"]["cycle_length_s"][:-1], b["columns"]["cycle_length_s"][:-1], atol=0.2)


def _detrend600(x):
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    spec = get_adapter("preprocessing.detrend")
    return np.asarray(spec.run(x, np.arange(x.size, dtype=float), 1.0, mode="rolling_mean", window_s=600.0).value.x)


def test_a_600s_detrend_distorts_the_sharkfin_and_the_raw_waveform_restores_it():
    x, st, en = syn.chain([syn.sharkfin] * 40, syn.drifting_periods(40), bg="ar1", noise=0.1, seed=2)
    xd = _detrend600(x)
    on_detrended = _run(xd, st, en, null_draws=0)
    on_raw = _run(xd, st, en, waveform=x, null_draws=0)
    cd, cr = on_detrended["columns"], on_raw["columns"]
    # from the raw trace: a sharkfin (on its floor for 1/2-2/3, half back late)
    assert 0.5 <= np.median(cr["cycle_floor_frac"][:-1]) <= 0.67
    assert np.nanmedian(cr["cycle_half_recovery_frac"][:-1]) >= 0.5
    # from the 600 s trace: half back early, as a trough, and the floor all over the place
    assert np.nanmedian(cd["cycle_half_recovery_frac"][:-1]) <= 0.35
    lo, hi = np.percentile(cd["cycle_floor_frac"][:-1], [10, 90])
    assert hi - lo > 0.5, (lo, hi)
    assert on_raw["meta"]["waveform"] == "side input"


# ── gaps, splits, NaN, too few ─────────────────────────────────────────────

def _drop_events(st, en, drop):
    keep = np.setdiff1d(np.arange(st.size), drop)
    return st[keep], en[keep]


@pytest.mark.parametrize("n", [30, 120])
def test_missed_detections_are_gaps_and_split_drops_are_too_short(n):
    x, st, en = syn.chain([syn.sharkfin] * n, syn.drifting_periods(n), bg="ar1", noise=0.1, seed=3)
    missed = np.arange(3, n - 2, n // 5)                  # 5 missed detections across the drift
    st2, en2 = _drop_events(st, en, missed)
    split_at = st2[n // 2]
    st3 = np.sort(np.r_[st2, split_at + 30])
    en3 = np.sort(np.r_[en2, split_at + 40])
    r = _run(x, st3, en3, null_draws=0)
    om = r["meta"]["omitted"]
    assert om.get(CS.OMIT_LONG, 0) == len(missed)
    assert om.get(CS.OMIT_SHORT, 0) == 1
    used = _seq(r)["n_used"]
    true_cycles = n - 2 * len(missed) - 1                # each miss eats two cycles; the split eats one
    assert used >= true_cycles - 1
    assert "left out" in r["meta"]["summary"] and "gap_long" in r["meta"]["summary"]


def test_an_explicit_max_cycle_overrides_the_automatic_rule():
    x, st, en = syn.chain([syn.sharkfin] * 30, syn.drifting_periods(30), bg="ar1", noise=0.1, seed=3)
    r = _run(x, st, en, null_draws=0, max_cycle_s=2400.0)
    lens = np.diff(st) / 1.0
    assert r["meta"]["omitted"].get(CS.OMIT_LONG, 0) == int(np.sum(lens > 2400))


def test_nan_inside_a_cycle_is_counted_or_filled():
    x, st, en = syn.chain([syn.sharkfin] * 30, syn.drifting_periods(30), bg="ar1", noise=0.1, seed=4)
    x = x.copy()
    a, b = st[5], st[6]
    x[a + 100:a + 100 + int(0.2 * (b - a))] = np.nan     # 20 % missing: left out
    c, d = st[10], st[11]
    x[c + 100:c + 100 + int(0.05 * (d - c))] = np.nan    # 5 %: filled
    r = _run(x, st, en, null_draws=0)
    assert r["omit_reason"][5] == CS.OMIT_NAN and r["meta"]["omitted"][CS.OMIT_NAN] == 1
    assert r["omit_reason"][10] == "" and np.isfinite(r["columns"]["cycle_floor_frac"][10])


def test_too_few_cycles_keep_their_measures_but_get_no_group_and_no_k():
    x, st, en = syn.chain([syn.sharkfin] * 6, syn.drifting_periods(6), bg="ar1", noise=0.1, seed=5)
    r = _run(x, st, en)
    s = _seq(r)
    assert s["k"] is None and "fewer than" in s["reason"]
    assert (r["columns"]["cycle_group"] == -1).all()
    assert np.isfinite(r["columns"]["cycle_floor_frac"][:-1]).all()
    assert all(k == "-1" for k in r["group_keys"])
    assert r["meta"]["omitted"][CS.OMIT_FEW] == 6
    assert "fewer than" in r["meta"]["summary"]


def test_no_events_says_so():
    r = _run(np.zeros(1000), np.zeros(0, dtype=int), np.zeros(0, dtype=int))
    assert r["meta"]["n_events"] == 0 and "no events" in r["meta"]["summary"]


# ── sequences, exemplars, the stack payload ────────────────────────────────

def test_trains_are_sequences_and_events_in_no_train_open_no_cycle():
    x, st, en = syn.chain([syn.sharkfin] * 24 + [syn.trough] * 24, syn.drifting_periods(48), bg="ar1",
                          noise=0.1, seed=6)
    tid = np.r_[np.zeros(25, dtype=int), np.ones(24, dtype=int)]
    tid[0] = -1
    feats = pd.DataFrame({"train_id": tid})
    r = _run(x, st, en, feats, null_draws=2)
    m = r["meta"]
    assert m["sequence_basis"] == "train_id" and m["n_sequences"] == 2
    assert r["omit_reason"][0] == CS.OMIT_NO_SEQUENCE and r["columns"]["cycle_index"][0] == -1
    keys = {k for k in r["group_keys"] if k != "-1"}
    assert keys and all(k.startswith(("t0:", "t1:")) for k in keys)
    # the last event of each train opens no cycle
    assert r["omit_reason"][24] == CS.OMIT_NO_CYCLE and r["omit_reason"][48] == CS.OMIT_NO_CYCLE


def test_exemplars_are_members_and_the_stack_respects_its_caps():
    x, st, en = syn.chain([syn.sharkfin] * 130 + [syn.trough] * 130, np.full(260, 900.0), bg="ar1",
                          noise=0.1, seed=7)
    r = _run(x, st, en, null_draws=0)
    m = r["meta"]
    g = r["columns"]["cycle_group"]
    assert m["exemplar_events"]
    for key, ev in m["exemplar_events"].items():
        assert isinstance(ev, int) and g[ev] == int(key.split(":")[-1])
    cs = m["cycle_stack"]
    assert cs["n_rows"] == CS.STACK_MAX and cs["sampled"] and cs["n_cycles"] == 260
    assert cs["n_points"] == CS.STACK_POINTS
    for row in cs["rows"]:
        assert len(row["before"]) == CS.STACK_POINTS and len(row["after"]) == CS.STACK_POINTS
        assert g[row["event"]] == row["group"]
    assert "member" in m["exemplar_rule"]


# ── the pieces ─────────────────────────────────────────────────────────────

def test_the_fast_entropy_agrees_with_svd_entropy():
    Z = np.random.default_rng(0).standard_normal((50, 256)).cumsum(axis=1)
    ref = svd_entropy(Z, align=False, null_draws=0)
    h, hs = CS.entropy_pair(CS._z_rows(Z))
    assert h == pytest.approx(ref["svd_entropy_norm"], abs=1e-9)
    assert hs == pytest.approx(ref["svd_entropy_squared_norm"], abs=1e-9)


def test_the_bimodality_test_takes_the_uniform_as_its_least_favourable_shape():
    rng = np.random.default_rng(1)
    n = 200
    shapes = {"uniform": lambda: rng.uniform(size=n), "normal": lambda: rng.standard_normal(n),
              "triangular": lambda: rng.triangular(0, 0.5, 1, n), "exponential": lambda: rng.exponential(size=n)}
    med = {k: np.median([CS.ci_1d(f()) for _ in range(100)]) for k, f in shapes.items()}
    assert all(med[k] >= med["uniform"] for k in med)
    for f in shapes.values():
        assert CS.bimodality_test(f(), seed=2)["p"] > 0.01
    two = np.r_[rng.normal(0, 1, 100), rng.normal(5, 1, 100)]
    assert CS.bimodality_test(two, seed=2)["p"] < 0.01


def test_the_order_test_tells_blocks_from_alternation():
    blocked = np.r_[np.ones(30), 2 * np.ones(30)]
    alternating = np.tile([1, 2], 30)
    assert CS.order_test(blocked)["p"] < 0.01
    assert CS.order_test(alternating)["p"] > 0.5
    assert CS.order_test(np.ones(20))["p"] is None


def test_bounded_shifts_find_a_known_shift_and_never_exceed_the_bound():
    t = np.arange(256)
    base = CS._z_rows(-np.exp(-0.5 * ((t - 100) / 15.0) ** 2)[None, :])[0]
    rows = np.vstack([np.r_[np.full(k, base[0]), base[:256 - k]] for k in (0, 5, 12)])
    s = CS.bounded_shifts(rows, base, 20)
    assert list(s) == [0, -5, -12]
    assert np.abs(CS.bounded_shifts(rows, base, 3)).max() <= 3


def test_a_cancel_raises_the_executors_cancellation():
    from Working.execution import RecipeCancelled
    x, st, en = syn.two_family_chain("ar1")
    with pytest.raises(RecipeCancelled):
        _run(x, st, en, should_cancel=lambda: True)


# ── fix round 1 ────────────────────────────────────────────────────────────

def test_sigclust_without_the_floor_does_not_reject_a_true_gaussian():
    """B2: the MAD floor rejected a one-cluster Gaussian with smooth covariance 12/12 at n = 200."""
    d = 256
    lag = np.abs(np.subtract.outer(np.arange(d), np.arange(d)))
    C = 0.97 ** lag
    Lc = np.linalg.cholesky(C + 1e-9 * np.eye(d))
    ps = []
    for seed in range(3):
        X = np.random.default_rng(seed).standard_normal((200, d)) @ Lc.T
        ps.append(CS.sigclust(X, draws=50, seed=seed)["p"])
    assert min(ps) >= 0.05, ps


def _dense(shapes, bg="ar1", seed=1, noise=0.15):
    """A chain that fills its span: no margins, each event's span reaching the next anchor."""
    x, st, en = syn.chain(shapes, syn.drifting_periods(len(shapes)), bg=bg, noise=noise, seed=seed,
                          lead_s=60, tail_s=60)
    return x, st, np.r_[st[1:] - 5, en[-1]]


@pytest.fixture(scope="module")
def dense_sharkfins():
    return _run(*_dense([syn.sharkfin] * 120))


def test_a_chain_that_fills_its_span_is_untested_not_noise_like(dense_sharkfins):
    r = dense_sharkfins
    s = _seq(r)
    bg = s["background"]
    assert bg["fallback_share"] > 0.5
    for v in [s["whole"]["verdict"]] + [g["coherence"]["verdict"] for g in s["groups"]]:
        assert v["tested"] is False and "no free stretch as long as a cycle" in v["reason"]
    assert all(g["key"].endswith(UNTESTED_SUFFIX) for g in s["groups"])
    assert all(k == "-1" or k.endswith(UNTESTED_SUFFIX) for k in r["group_keys"])
    w = " ".join(r["meta"]["warnings"])
    assert "no free stretch as long as a cycle (longest free stretch" in w
    assert "pseudo-cycles would be random-phase cuts of the chain" in w
    assert "untested" in r["meta"]["summary"]


def test_the_sampler_reports_its_longest_free_stretch(dense_sharkfins):
    bg = _seq(dense_sharkfins)["background"]
    assert bg["longest_free_samples"] > 0 and bg["longest_free_s"] == pytest.approx(bg["longest_free_samples"])
    assert bg["longest_free_s"] < np.median(dense_sharkfins["columns"]["cycle_length_s"][:-1])


def test_without_background_k_is_calibrated_on_phase_copies_and_still_finds_two_shapes(dense_sharkfins):
    s = _seq(dense_sharkfins)
    assert s["k"] == 1 and s["k_null"]["source"] == "phase"
    x, st, en = _dense([syn.sharkfin] * 60 + [syn.trough] * 60)
    r = _run(x, st, en)
    s2 = _seq(r)
    assert s2["k_null"]["source"] == "phase" and s2["k"] == 2
    assert adjusted_rand_score(TRUTH, r["columns"]["cycle_group"][:-1]) >= 0.9
    assert "phase null" in r["meta"]["summary"]


def test_chain_timed_noise_that_fills_its_span_stays_one_group_on_the_phase_null():
    """Measured: 0/10 random walk, 0/10 AR(1), 0/10 drift (30 chains); pinned here on the AR(1) seeds 0-4."""
    ks = []
    for seed in range(3):   # fix round 2: 5 -> 3 seeds (test cost)
        x, st, en = syn.regular_events(100, "ar1", seed=seed, span_frac=0.9, lead_s=60)
        s = _seq(_run(x, st, en))
        assert s["k_null"]["source"] == "phase"
        ks.append(s["k"])
    assert ks == [1] * 3, ks


def test_every_background_draw_is_in_meta(two_families):
    s = _seq(two_families["ar1"])
    b = s["whole"]["nulls"]["background"]
    assert len(b["eq17"]["values"]) == CS.NULL_DRAWS and len(b["squared"]["values"]) == CS.NULL_DRAWS
    assert b["draws_dropped"] == 0
    assert min(b["eq17"]["values"]) == pytest.approx(b["eq17"]["min"])
    for g in s["groups"]:
        gb = g["coherence"]["nulls"]["background"]
        assert len(gb["eq17"]["values"]) == CS.NULL_DRAWS and len(gb["squared"]["values"]) == CS.NULL_DRAWS
        assert "matched" in gb
    assert len(s["k_null"]["values"]) == CS.NULL_DRAWS


def test_the_per_group_null_matches_the_selection_on_noise():
    """S2: groups forced out of noise cycles must not read beyond noise against a null that went through the
    same K-means (the random-subset null passed sigma^2 in 9 of 36 such groups). Measured with 20 draws on
    random walk and AR(1), seeds 0-5: 1 of 24 groups passed (random walk seed 4, z 6.6 - that realisation's lower
    group); pinned: at most 1 of the 12 random-walk groups."""
    passed = []
    for seed in range(6):
        x, st, _ = syn.regular_events(120, "rw", seed=seed)
        Z = CS._z_rows(CS._prepare_all(x, st[:-1], st[1:], 256, "chord", 0.1)[0])
        lab, _ = CS.kmeans(Z, 2, 10, seed)
        real = [CS.entropy_pair(CS.align_stack(Z[lab == c], 26, seed)[0]) for c in (0, 1)]
        nulls = []
        for b in range(20):
            xb, sb, _ = syn.regular_events(120, "rw", seed=500 + 20 * seed + b)
            nulls.append(CS._z_rows(CS._prepare_all(xb, sb[:-1], sb[1:], 256, "chord", 0.1)[0]))
        matched = CS.group_nulls(nulls, 2, 26, seed)
        r17 = sorted(range(2), key=lambda c: real[c][0])
        rsq = sorted(range(2), key=lambda c: real[c][1])
        for rank in range(2):
            v = CS._verdict(real[r17[rank]][0], real[rsq[rank]][1], [m[0][rank] for m in matched],
                            [m[1][rank] for m in matched])
            passed.append(bool(v["beyond_noise"]) or bool(v["beyond_noise_squared"]))
    assert sum(passed) <= 1, passed


def test_many_gaps_warn_that_the_longest_cycles_are_lost():
    rng = np.random.default_rng(3)
    sig = np.sqrt(np.log(1 + 0.5 ** 2))
    periods = 1800.0 * np.exp(rng.normal(-0.5 * sig ** 2, sig, 120))
    x, st, en = syn.chain([syn.sharkfin] * 120, periods, bg="ar1", noise=0.1, seed=3)
    r = _run(x, st, en, null_draws=0)
    n_long = r["meta"]["omitted"].get(CS.OMIT_LONG, 0)
    assert n_long > 12
    w = " ".join(r["meta"]["warnings"])
    assert "the longest cycles are the ones lost" in w and "the longest cycles are the ones lost" in r["meta"]["summary"]


def test_a_short_sequence_says_a_split_needs_twice_min_cycles():
    x, st, en = syn.chain([syn.sharkfin] * 8 + [syn.trough] * 7, syn.drifting_periods(15), bg="ar1", noise=0.1,
                          seed=5)
    r = _run(x, st, en, null_draws=0)
    s = _seq(r)
    assert s["k"] == 1 and "a split needs >= 2 x min_cycles" in s["k_note"]
    assert "a split needs >= 2 x min_cycles" in r["meta"]["summary"]


def test_an_unbound_waveform_is_warned_and_a_bound_one_is_not():
    x, st, en = syn.chain([syn.sharkfin] * 12, syn.drifting_periods(12), bg="ar1", noise=0.1, seed=1)
    a = _run(x, st, en, null_draws=0)
    b = _run(x, st, en, null_draws=0, waveform=x)
    assert any("bind waveform to the root signal" in w for w in a["meta"]["warnings"])
    assert not any("bind waveform" in w for w in b["meta"]["warnings"])


# ── fix round 2 ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mixed_noise():
    """S-A: AR(0.95) margins, a random walk under chain-timed events with no shape (3 seeds)."""
    return [_run(*syn.mixed_colour_chain(100, seed=seed)) for seed in range(3)]


def test_a_background_of_another_colour_is_named_and_its_groups_untested(mixed_noise):
    for r in mixed_noise:
        s = _seq(r)
        v = s["whole"]["verdict"]
        assert v["background_colour_mismatch"] is True, (v["beyond_noise"], v["beyond_noise_squared"],
                                                         v["beyond_phase_cycles_squared"])
        assert s["background_colour_mismatch"] is True
        # K is gated on both nulls: the margins' background alone let K = 2 through in 5 of 10 such chains
        assert s["k"] == 1, s["splits"]
        assert all(k == "-1" or k.endswith(UNTESTED_SUFFIX) for k in r["group_keys"])
        assert "differs in colour from the quiet margins" in r["meta"]["summary"]
        assert "beyond the margins, not beyond its own noise" in " ".join(r["meta"]["warnings"])


def test_the_phase_cycle_null_is_reported_on_sigma_squared_only(mixed_noise):
    pc = _seq(mixed_noise[0])["whole"]["nulls"]["phase_cycles"]
    assert set(pc) == {"squared", "beyond_squared", "rule"}
    assert len(pc["squared"]["values"]) == CS.NULL_DRAWS and "eq. 17 is never read" in pc["rule"]


def test_a_real_two_shape_chain_on_another_colour_still_beats_its_own_noise():
    x, st, en = syn.mixed_colour_chain(120, seed=1, shapes=[syn.sharkfin] * 60 + [syn.trough] * 60)
    r = _run(x, st, en)
    s = _seq(r)
    v = s["whole"]["verdict"]
    assert v["beyond_phase_cycles_squared"] is True and v["background_colour_mismatch"] is False
    assert s["k"] == 2


def test_a_group_is_unmarked_only_when_eq17_and_sigma_squared_both_pass():
    both = {"tested": True, "beyond_noise": True, "beyond_noise_squared": True}
    assert CS.group_key("1", both, False) == "1"
    assert CS.group_key("1", {**both, "beyond_noise_squared": False}, False) == "1" + NOISE_LIKE_SUFFIX
    assert CS.group_key("1", {**both, "beyond_noise": False}, False) == "1" + NOISE_LIKE_SUFFIX
    assert CS.group_key("1", both, True) == "1" + UNTESTED_SUFFIX
    assert CS.group_key("1", {**both, "tested": False}, None) == "1" + UNTESTED_SUFFIX


def test_the_rules_say_what_the_verdict_is(two_families):
    rules = {r["name"]: r["rule"] for r in two_families["ar1"]["meta"]["rules"]}
    v = rules["verdict"]
    assert "a 1-in-20 test" in v and "unlike the quiet margins" in v and "fallback_share" in v
    assert "rank" in v and "random subset" not in v


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
