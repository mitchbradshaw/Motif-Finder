"""
test_mpdist_distance.py
=======================
w3-d: MPdist (Gharghabi et al. 2018, matrix profile XII) as the Library's
fourth edge distance — "do these two members share their sub-shapes, at their
own speed?".

What it pins:

* **The question it answers.** A shape and the same shape with 30 % extra
  baseline on one side are near 0 under MPdist while the scale-invariant
  distance (put on the same unit footing) is far; two different shapes (a drop
  with slow recovery, a square dip) are far apart.
* **The question it does NOT answer.** A 0.8x time-compressed copy of a smooth
  drop reads as close as an uncompressed copy, while a compressed ringing
  shape reads far: a small MPdist is never a verdict on scale.
* **The footing.** The value is stumpy's MPdist divided by sqrt(2 x sub-length)
  — sqrt(1 - r) of the sub-piece pair it reads: 0 for an identical sub-shape,
  1 for an uncorrelated one, sqrt(2) the hard maximum. It agrees with
  `stumpy.mpdist` on finite, non-flat input.
* **Symmetry**, and **refusals in words**: a member mostly NaN, a flat member,
  a member too short to hold two sub-pieces of the minimum length.
* **Flat stretches and gaps are left out**, not read as identical.
* **The null beside the value** (`mpdist_null`): coloured-noise pairs (AR(1)
  phi 0.99, detrended random walk) sit near their own surrogates; a shared
  shape sits well below.
* **The fourth edge**: `resolve_run_matches` writes an MPdist edge per accepted
  pair in a temp database, refuses a member too short for it in words (no edge,
  no silent 0), and the scale read-out counts the pair it could not compare.
"""

import json
import math
import os
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import stumpy  # noqa: E402

from Working.distances import (  # noqa: E402
    DISTANCE_MPDIST, DISTANCE_REGISTRY, MPDIST_MIN_SUB_LENGTH, MPDIST_PERCENTAGE, MPDIST_RULE, MPDIST_SUB_FRAC,
    MPDIST_TOOLTIP,
    MPdistRefused, mpdist_detail, mpdist_distance, mpdist_null, resample_to_length,
    scale_invariant_distance,
)


# ── synthetic shapes and backgrounds ────────────────────────────────────────

def _drop(n, tau=0.25):
    """A fast fall at 20 % of the window and a slow exponential recovery."""
    t = np.linspace(0.0, 1.0, n)
    y = np.zeros(n)
    on = t >= 0.2
    y[on] = -np.exp(-(t[on] - 0.2) / tau)
    return y


def _square(n):
    t = np.linspace(0.0, 1.0, n)
    return -((t > 0.3) & (t < 0.7)).astype(float)


def _ring(n):
    """A fall that rings: a damped oscillation, whose period a time-squeeze changes."""
    t = np.linspace(0.0, 1.0, n)
    y = np.zeros(n)
    on = t >= 0.2
    y[on] = -np.exp(-(t[on] - 0.2) / 0.4) * np.cos(2 * np.pi * 4 * (t[on] - 0.2))
    return y


def _ar1(rng, n, phi=0.99):
    x = np.zeros(n)
    e = rng.standard_normal(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def _walk(rng, n):
    x = np.cumsum(rng.standard_normal(n))
    t = np.arange(n)
    return x - np.polyval(np.polyfit(t, x, 1), t)


def _noisy(y, rng, sd=0.05):
    return y + sd * rng.standard_normal(len(y))


def _unit(d, n):
    """A z-normalised Euclidean distance over n samples on the unit footing sqrt(1 - r)."""
    return d / math.sqrt(2 * n)


# ── 1. the question it answers ─────────────────────────────────────────────

def test_extra_baseline_is_near_zero_where_the_scale_invariant_distance_is_far():
    rng = np.random.default_rng(0)
    n = 300
    a = _noisy(_drop(n), rng)
    b = _noisy(np.concatenate([np.zeros(int(0.3 * n)), _drop(n)]), rng)
    mp = mpdist_distance(a, b)
    si = _unit(scale_invariant_distance(a, b), max(len(a), len(b)))
    assert mp < 0.3, mp
    assert si > 0.6, si
    assert si > 3 * mp, (mp, si)


def test_two_different_shapes_are_far_apart():
    rng = np.random.default_rng(1)
    n = 300
    a = _noisy(_drop(n), rng)
    same = mpdist_distance(a, _noisy(_drop(n), rng))
    other = mpdist_distance(a, _noisy(_square(n), rng))
    assert other > 0.3, other
    assert other > 2 * same, (same, other)


# ── 2. the question it does not answer ─────────────────────────────────────

def test_a_compressed_copy_is_not_a_scale_verdict():
    """A squeezed piece of a smooth drop still matches a piece of the original,
    so MPdist calls the 0.8x copy as close as an unsqueezed one; a ringing
    shape's squeeze changes its period and MPdist sees it. Either way MPdist
    says nothing about whether the shape survives rescaling — the tooltip
    must say so."""
    rng = np.random.default_rng(2)
    n = 300
    a = _noisy(_drop(n), rng)
    same = mpdist_distance(a, _noisy(_drop(n), rng))
    squeezed = mpdist_distance(a, _noisy(resample_to_length(_drop(n), int(0.8 * n)), rng))
    assert squeezed < 1.5 * same + 0.05, (same, squeezed)

    r = _noisy(_ring(n), rng)
    r_same = mpdist_distance(r, _noisy(_ring(n), rng))
    r_squeezed = mpdist_distance(r, _noisy(resample_to_length(_ring(n), int(0.8 * n)), rng))
    assert r_squeezed > 2 * r_same, (r_same, r_squeezed)

    tip = MPDIST_TOOLTIP.lower()
    assert "not" in tip and "scale" in tip and "sub-shape" in tip


# ── 3. the footing ─────────────────────────────────────────────────────────

def test_the_footing_is_stumpys_mpdist_over_root_two_sub_lengths():
    rng = np.random.default_rng(3)
    a = rng.standard_normal(200).cumsum()
    b = rng.standard_normal(150).cumsum()
    s = int(math.ceil(MPDIST_SUB_FRAC * 150))
    ours = mpdist_distance(a, b)
    theirs = stumpy.mpdist(a, b, s, percentage=MPDIST_PERCENTAGE) / math.sqrt(2 * s)
    assert ours == pytest.approx(theirs, rel=1e-6, abs=1e-9)
    d = mpdist_detail(a, b)
    assert d["sub_length"] == s
    assert d["value"] == pytest.approx(ours)
    assert d["raw"] == pytest.approx(ours * math.sqrt(2 * s))


def test_the_dense_engine_and_stumpys_join_agree():
    """Two engines, one number: the dense correlation matrix (no numba
    compile) and stumpy's AB-join, on plain pairs, a pair with a gap and a
    pair with flat stretches (where stumpy's flat partner is re-measured)."""
    rng = np.random.default_rng(12)
    a = _noisy(_drop(240), rng, 0.1)
    b = _noisy(_square(180), rng, 0.1)
    b_gap = b.copy()
    b_gap[100:110] = np.nan
    t = np.linspace(-3.0, 3.0, 120)
    flat_a = np.concatenate([np.zeros(150), np.exp(-t ** 2)])
    flat_b = np.concatenate([np.zeros(150), -np.exp(-t ** 2)])
    for x, y in ((a, b), (b, a), (a, b_gap), (flat_a, flat_b), (_walk(rng, 400), _ar1(rng, 333))):
        dense = mpdist_detail(x, y, engine="dense")
        joined = mpdist_detail(x, y, engine="stumpy")
        assert dense["engine"] == "dense" and joined["engine"] == "stumpy"
        assert dense["value"] == pytest.approx(joined["value"], rel=1e-6, abs=1e-6)
        assert dense["k"] == joined["k"] and dense["pool"] == joined["pool"]
    assert mpdist_detail(a, b)["engine"] == "dense", "members of minutes take the dense engine"


def test_the_footing_runs_from_zero_for_a_copy_to_root_two_for_its_mirror():
    ramp = np.arange(120, dtype=float)
    assert mpdist_distance(ramp, 3.0 * ramp + 5.0) == pytest.approx(0.0, abs=1e-6)
    assert mpdist_distance(ramp, -ramp) == pytest.approx(math.sqrt(2.0), abs=1e-6)


def test_it_is_symmetric():
    rng = np.random.default_rng(4)
    for n_a, n_b in ((300, 390), (120, 80), (500, 500)):
        a = _noisy(_drop(n_a), rng, 0.1)
        b = _noisy(_square(n_b), rng, 0.1)
        assert mpdist_distance(a, b) == pytest.approx(mpdist_distance(b, a), rel=1e-9, abs=1e-12)


def test_it_is_in_the_registry():
    assert DISTANCE_MPDIST == "mpdist"
    assert DISTANCE_REGISTRY[DISTANCE_MPDIST] is mpdist_distance


# ── 4. what it cannot compare ──────────────────────────────────────────────

def test_a_member_mostly_nan_is_refused_in_words():
    rng = np.random.default_rng(5)
    a = _noisy(_drop(200), rng)
    b = _noisy(_drop(200), rng)
    b[:120] = np.nan
    with pytest.raises(MPdistRefused) as err:
        mpdist_distance(a, b)
    assert "nan" in str(err.value).lower() or "gap" in str(err.value).lower()


def test_a_flat_member_is_refused_in_words():
    rng = np.random.default_rng(6)
    a = _noisy(_drop(200), rng)
    with pytest.raises(MPdistRefused) as err:
        mpdist_distance(a, np.full(200, 4.2))
    assert "flat" in str(err.value).lower()
    with pytest.raises(MPdistRefused):
        mpdist_distance(np.full(150, -1.0), a)


def test_a_member_too_short_is_refused_in_words():
    rng = np.random.default_rng(7)
    a = _noisy(_drop(200), rng)
    short = _noisy(_drop(2 * MPDIST_MIN_SUB_LENGTH - 2), rng)
    with pytest.raises(MPdistRefused) as err:
        mpdist_distance(a, short)
    assert "short" in str(err.value).lower()
    assert str(2 * MPDIST_MIN_SUB_LENGTH) in str(err.value)
    # just long enough is compared
    ok = _noisy(_drop(2 * MPDIST_MIN_SUB_LENGTH), rng)
    assert np.isfinite(mpdist_distance(a, ok))


def test_bad_parameters_are_refused():
    rng = np.random.default_rng(8)
    a, b = rng.standard_normal(100), rng.standard_normal(100)
    for frac in (0.0, 0.6, -0.1):
        with pytest.raises(ValueError):
            mpdist_distance(a, b, sub_frac=frac)
    for pct in (0.0, 1.5):
        with pytest.raises(ValueError):
            mpdist_distance(a, b, percentage=pct)


def test_flat_stretches_shared_by_both_members_are_not_read_as_identical():
    """stumpy scores two constant sub-pieces 0 apart. A hump and its mirror
    image on long noise-free flat baselines would then read as identical; the
    flat sub-pieces are left out instead (neither read nor a partner), and
    what is left — a rise against a fall-then-recovery — is no more alike than
    unrelated pieces (0.88 measured; 0.71 if a flat piece could still be a
    partner at stumpy's sqrt(s))."""
    t = np.linspace(-3.0, 3.0, 200)
    hump = np.exp(-t ** 2)
    a = np.concatenate([np.zeros(400), hump])
    b = np.concatenate([np.zeros(400), -hump])
    s = int(math.ceil(MPDIST_SUB_FRAC * 600))
    assert stumpy.mpdist(a, b, s) == pytest.approx(0.0, abs=1e-9), "stumpy alone reads them as identical"
    d = mpdist_detail(a, b)
    assert d["value"] > 0.8, d
    assert d["excluded_flat"] > 0


def test_a_short_gap_is_left_out_not_filled():
    rng = np.random.default_rng(9)
    a = _noisy(_drop(300), rng)
    b = _noisy(_drop(300), rng)
    whole = mpdist_distance(a, b)
    b_gap = b.copy()
    b_gap[250:262] = np.nan
    d = mpdist_detail(a, b_gap)
    assert np.isfinite(d["value"])
    assert d["excluded_gap"] > 0
    assert abs(d["value"] - whole) < 0.05, (whole, d["value"])


# ── 5. the null the read-out prints beside the value ───────────────────────

def test_the_null_is_context_only_never_a_verdict():
    """Fix round 1 (F3, decision 12): the trend-kept surrogate null is biased
    (coloured noise sits below its own null median in 65-70 % of pairs; a
    trough sits at its null), so it returns a median and a 5th percentile to
    print beside the value and NO verdict field."""
    rng = np.random.default_rng(10)
    n = 300
    for a, b in ((_ar1(rng, n), _ar1(rng, n)), (_walk(rng, n), _walk(rng, n)),
                 (_noisy(_drop(n), rng), _noisy(np.concatenate([np.zeros(90), _drop(n)]), rng))):
        out = mpdist_null(a, b, seed=0)
        assert out["draws"] == 5
        assert 0.2 < out["null_median"] < 1.2, out
        assert out["null_p05"] <= out["null_median"]
        assert "beyond_noise" not in out and "margin" not in out, sorted(out)
        note = out["note"].lower()
        assert "context" in note and "not a verdict" in note and "65" in note, note
    for text in (out["rule"], MPDIST_RULE):
        low = text.lower()
        assert "beyond_noise" not in low and "across a family" not in low, text
        assert "surrogate" in low and "not a scale" in low


def test_the_null_names_its_follow_up():
    assert "background_null" in (mpdist_null.__doc__ or "")


# ── 5b. fix round 1: the default order statistic and realistic noise ────────

def test_the_default_order_statistic_is_a_quarter_of_the_samples_about_half_the_pool():
    """F4 / F5: percentage defaults to 0.25 (an adaptation, decision 11), and
    k is a share of the SAMPLE count |A| + |B| (the paper's), which at the
    default sub-length is about half of the pool of closest-piece distances."""
    assert MPDIST_PERCENTAGE == 0.25
    rng = np.random.default_rng(13)
    for n_a, n_b in ((300, 300), (150, 190), (454, 400)):
        d = mpdist_detail(_noisy(_drop(n_a), rng), _noisy(_drop(n_b), rng))
        assert 0.40 <= d["pool_share"] <= 0.56, d["pool_share"]
        assert d["pool_share"] == pytest.approx(d["k"] / d["pool"])
    assert "5 % of the pool" not in MPDIST_RULE
    assert "|a| + |b|" in MPDIST_RULE.lower() and "half" in MPDIST_RULE.lower()


def _coloured(rng, kind, n, sd):
    x = _ar1(rng, n, 0.97) if kind == "ar1" else _walk(rng, n)
    return sd * (x - x.mean()) / x.std()


@pytest.mark.parametrize("kind", ["ar1", "walk"])
def test_at_realistic_coloured_noise_mpdist_barely_tells_a_drop_from_a_square(kind):
    """What MPdist really does on coloured backgrounds (wave 1's lesson):
    at noise sd 0.1 of the event's depth a square dip still sits above the
    same-shape pairs; at sd 0.2 the two overlap. The page must not say it
    tells shapes apart."""
    rng = np.random.default_rng(14 if kind == "ar1" else 15)
    n = 300

    def run(sd):
        same, square = [], []
        for _ in range(10):
            a = _drop(n) + _coloured(rng, kind, n, sd)
            same.append(mpdist_distance(a, _drop(n) + _coloured(rng, kind, n, sd)))
            square.append(mpdist_distance(a, _square(n) + _coloured(rng, kind, n, sd)))
        return np.median(square) / np.median(same), np.mean(np.array(square) <= np.percentile(same, 75))

    ratio_low, _ = run(0.1)
    ratio_high, confused_high = run(0.2)
    assert ratio_low > 1.2, ratio_low
    assert ratio_high < 1.35, ratio_high
    assert confused_high >= 0.1, confused_high
    tip = MPDIST_TOOLTIP.lower()
    assert "noise" in tip and "tell" in tip


@pytest.mark.parametrize("kind", ["ar1", "walk"])
def test_at_realistic_coloured_noise_extra_baseline_still_reads_as_the_same_shape(kind):
    rng = np.random.default_rng(16 if kind == "ar1" else 17)
    n = 300
    for sd in (0.1, 0.2):
        same, ext = [], []
        for _ in range(10):
            a = _drop(n) + _coloured(rng, kind, n, sd)
            same.append(mpdist_distance(a, _drop(n) + _coloured(rng, kind, n, sd)))
            b = np.concatenate([np.zeros(90), _drop(n)])
            ext.append(mpdist_distance(a, b + _coloured(rng, kind, len(b), sd)))
        ratio = np.median(ext) / np.median(same)
        assert 0.8 < ratio < 1.25, (sd, ratio)


def test_the_null_is_seeded():
    rng = np.random.default_rng(11)
    a, b = _ar1(rng, 200), _ar1(rng, 240)
    assert mpdist_null(a, b, seed=3) == mpdist_null(a, b, seed=3)


# ── 6. the fourth edge ─────────────────────────────────────────────────────

N = 3000
M = 60


def _trough(n):
    u = np.linspace(0.0, 1.0, n)
    fall = np.clip(u / 0.2, 0.0, 1.0)
    rise = np.clip((u - 0.2) / 0.8, 0.0, 1.0)
    return -(fall - rise ** 0.5) * (u < 0.2) - (1.0 - rise ** 0.5) * (u >= 0.2)


@pytest.fixture
def scratch():
    from Working.database import queries as q
    from Working.database import runs as R
    from Working.database.schema import init_db
    from Working.discovery import seeded_search

    with tempfile.TemporaryDirectory() as tmp:
        conn = init_db(":memory:")
        rng = np.random.default_rng(0)
        x = rng.standard_normal(N) * 0.02
        for at, n in ((500, 48), (1000, 60), (1600, 75), (2200, 12)):
            x[at:at + n] += _trough(n)
        path = os.path.join(tmp, "ch0.npy")
        np.save(path, x)
        rec = q.insert_recording(conn, "syn.mat", 0, 1.0, N, 0, path)
        entry = R.insert_motif_entry(conn, rec, 1000, 1060)
        steps = seeded_search.seed_steps(
            {"binding": {"source_kind": "library_exemplar", "entry_id": entry, "source_file": "syn.mat",
                         "channel": 0, "start_idx": 1000, "end_idx": 1060}},
            k=10, max_distance=4.0, scales=(0.8, 1.0, 1.25), overlap="lowest")
        cfg, _h = R.get_or_create_config(conn, {"recording_id": rec, "steps": steps, "span": None})
        run = R.insert_run(conn, cfg, rec, 0, N, status="completed")
        dets = {key: R.insert_detection(conn, run, s, e, score=sc)
                for key, s, e, sc in (("short", 500, 548, 1.1), ("long", 1600, 1675, 1.3),
                                      ("tiny", 2200, 2212, 2.0))}
        for d in dets.values():
            conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) "
                         "VALUES (?, 'interesting', '2026-10-14')", (d,))
        conn.commit()
        yield {"conn": conn, "entry": entry, "run": run, "det": dets}


def test_adding_matches_writes_a_fourth_edge_per_pair_and_refuses_one_it_cannot_compare(scratch):
    from Working.library import matching

    conn, entry, run, det = scratch["conn"], scratch["entry"], scratch["run"], scratch["det"]
    assert DISTANCE_MPDIST in matching.EDGE_DISTANCES
    out = matching.resolve_run_matches(conn, entry, [run], cut=4.0)
    rows = conn.execute("SELECT * FROM motif_edge WHERE distance_function = ?", (DISTANCE_MPDIST,)).fetchall()
    by_det = {r["detection_id"]: r for r in rows}
    assert set(by_det) == {det["short"], det["long"]}, "the 12-sample member is too short for MPdist"
    for r in rows:
        assert 0.0 <= r["distance_value"] < 0.5, r["distance_value"]
        recipe = json.loads(r["recipe_json"])
        assert recipe["distance_params"] == {"sub_frac": MPDIST_SUB_FRAC, "percentage": 0.25}

    assert out["edges_by_function"][DISTANCE_MPDIST] == 2
    refused = out["edges_refused"]
    assert len(refused) == 1
    assert refused[0]["detection_id"] == det["tiny"] and refused[0]["function"] == DISTANCE_MPDIST
    assert "short" in refused[0]["reason"].lower()
    # the other three distances still measured the tiny member
    tiny = conn.execute("SELECT distance_function FROM motif_edge WHERE detection_id = ?", (det["tiny"],)).fetchall()
    assert len(tiny) == 3

    again = matching.resolve_run_matches(conn, entry, [run], cut=4.0)
    assert again["edges_new"] == 0, "idempotent"
    assert len(again["edges_refused"]) == 1, "a refusal is reported every time, never turned into an edge"

    ro = matching.scale_readout(conn, entry, [run])
    assert DISTANCE_MPDIST in ro["distances"]
    cells = [r[DISTANCE_MPDIST] for r in ro["rows"]]
    assert sum(c["n"] for c in cells) == 2
    assert sum(c["missing"] for c in cells) == 1, "the pair MPdist could not compare is counted, not dropped"
    assert all(c["within"] is None for c in cells), "MPdist is not on the cut's footing"
    # F6: a missing edge says which kind it is — refused, or never computed
    assert sum(c["refused"] for c in cells) == 1
    assert sum(c["not_computed"] for c in cells) == 0
    assert out["refusal_summary"] and "1 of 3" in out["refusal_summary"]

    # pairs added before MPdist existed: their MPdist edges are simply not there yet
    conn.execute("DELETE FROM motif_edge WHERE distance_function = ?", (DISTANCE_MPDIST,))
    conn.commit()
    cells = [r[DISTANCE_MPDIST] for r in matching.scale_readout(conn, entry, [run])["rows"]]
    assert sum(c["not_computed"] for c in cells) == 2 and sum(c["refused"] for c in cells) == 1
    assert "add n matches" in cells[0]["missing_rule"].lower()


def test_an_exemplar_too_short_for_mpdist_is_said_once_not_per_pair(scratch):
    """F2: an exemplar under 16 samples refuses every pair; the result says so
    in one entry and one sentence."""
    from Working.database import runs as R
    from Working.library import matching

    conn, run, det = scratch["conn"], scratch["run"], scratch["det"]
    rec = conn.execute("SELECT recording_id FROM motif_entry WHERE id = ?", (scratch["entry"],)).fetchone()[0]
    tiny_entry = R.insert_motif_entry(conn, rec, 2200, 2212)
    out = matching.resolve_run_matches(conn, tiny_entry, [run], cut=4.0)
    assert out["edges_by_function"][DISTANCE_MPDIST] == 0
    assert len(out["edges_refused"]) == 1, out["edges_refused"]
    only = out["edges_refused"][0]
    assert only["detection_id"] is None and only["pairs"] >= 2
    assert "exemplar" in only["reason"].lower()
    assert "exemplar" in out["refusal_summary"].lower()
    assert out["edges_by_function"][matching.DISTANCE_SCALE_INVARIANT] >= 2, "the other distances still ran"


def test_symbolic_and_mpdist_are_off_the_cuts_footing():
    """F1: neither the symbolic distance (SAX MINDIST without the sqrt(n/w)
    factor) nor MPdist is on the seed cut's footing."""
    from Working.library import matching

    assert set(matching.OFF_CUT_FOOTING) == {DISTANCE_MPDIST, matching.DISTANCE_SYMBOLIC}
    assert all(isinstance(v, str) and v for v in matching.OFF_CUT_FOOTING.values())
