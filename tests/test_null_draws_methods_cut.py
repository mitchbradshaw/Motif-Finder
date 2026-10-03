"""
test_null_draws_methods_cut.py
===============================
fixup-T, Parts B, C and D — `QUESTIONS.md` Q35, Q36, Q-Null-1 and Q37.

**B (Q35).** A template run was scored against ONE surrogate realisation per
channel while the session chip said "200×". A paired run now draws N — N a
Settings › Nulls key per run kind, 20 for detection chains and 200 for seed
searches — and every figure that names a draw count names the count drawn.
The draws cost N× the sweep, so the plan's estimate includes them and routes
past the ceiling like any other estimate; an unchanged recipe reuses its draws.

**C (Q36, Q-Null-1).** The core says which null methods exist (the block's
own), so Settings cannot offer a third. Block shuffle keeps any motif shorter
than a block intact, so its block must be longer than the motif under test:
the default is twice the longest motif, and a block under two samples — which
is what the old 1.0 s default was at 1 Hz, a sample shuffle — is refused.

**D (Q37).** α and the multiple-comparison correction reach the recommended
cut, per channel, and the sentence beside the cut is generated from the values
used.

Runnable standalone:  python tests/test_null_draws_methods_cut.py
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working import run_groups  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import fanout, scoreboard  # noqa: E402
from Working.discovery import seeded_search as ss  # noqa: E402
from Working.recipes import make_recipe  # noqa: E402
from Working.registration.settings import put_settings  # noqa: E402

discover_adapters()

SPIKE = [{"stage": "detection", "algorithm": "spike_v1", "params": {}}]


@pytest.fixture()
def db():
    tmpdir = tempfile.mkdtemp(prefix="fixup_t_")
    db_path = os.path.join(tmpdir, "t.sqlite")
    conn = init_db(db_path)
    ids = []
    for ch in range(2):
        npy = os.path.join(tmpdir, f"CH{ch}.npy")
        np.save(npy, np.random.default_rng(ch).standard_normal(400))
        ids.append(q.insert_recording(conn, "fake.mat", ch, 1.0, 400, 0, npy))
    yield {"path": db_path, "conn": conn, "ids": ids}
    conn.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _surrogate_seeds(conn, run_ids):
    out = []
    for rid in run_ids:
        recipe = R.load_recipe(conn, R.get_run(conn, rid)["config_id"])
        assert recipe["steps"][0]["algorithm"] == "surrogate"
        out.append(recipe["steps"][0]["params"]["seed"])
    return out


# ── B: N draws, the count stated, the cost counted ──────────────────────────

def test_a_paired_run_draws_n_surrogates_at_n_seeds(db):
    recipe = make_recipe(db["ids"][0], SPIKE, span=(0, 400))
    out = run_groups.run_paired_recipe(recipe, db_path=db["path"], surrogate=True, surrogate_draws=3)
    ids = out["surrogate_run_ids"]
    assert len(set(ids)) == 3
    assert out["surrogate_run_id"] == ids[0]            # the old single-draw key still answers
    assert _surrogate_seeds(db["conn"], ids) == [0, 1, 2]
    for rid in ids:
        assert R.get_run(db["conn"], rid)["surrogate_of_run_id"] == out["run_id"]


def test_one_draw_is_still_what_a_caller_gets_without_asking(db):
    recipe = make_recipe(db["ids"][0], SPIKE, span=(0, 400))
    out = run_groups.run_paired_recipe(recipe, db_path=db["path"], surrogate=True)
    assert len(out["surrogate_run_ids"]) == 1


def test_draws_are_reused_while_the_recipe_is_unchanged(db):
    recipe = make_recipe(db["ids"][0], SPIKE, span=(0, 400))
    first = run_groups.run_paired_recipe(recipe, db_path=db["path"], surrogate=True, surrogate_draws=3)
    again = run_groups.run_paired_recipe(recipe, db_path=db["path"], surrogate=True, surrogate_draws=5)
    assert again["surrogate_run_ids"][:3] == first["surrogate_run_ids"]
    assert len(set(again["surrogate_run_ids"])) == 5
    n = db["conn"].execute("SELECT COUNT(*) FROM runs WHERE surrogate_of_run_id = ?",
                           (first["run_id"],)).fetchone()[0]
    assert n == 5, "raising the count must add draws, not redraw the ones already made"


def test_the_scoreboard_row_states_the_count_the_run_drew(db):
    recipe = make_recipe(db["ids"][0], SPIKE, span=(0, 400))
    out = run_groups.run_paired_recipe(recipe, db_path=db["path"], surrogate=True, surrogate_draws=4)
    row = scoreboard.channel_score(db["conn"], out["run_id"])
    assert row["null_draws"] == 4
    counts = [len(R.list_detections(db["conn"], rid)) for rid in out["surrogate_run_ids"]]
    assert row["null_expects"] == pytest.approx(sum(counts) / 4.0, abs=0.01)


def test_the_run_total_states_draws_per_channel_not_their_sum(db):
    """Two channels at 3 draws each used to read "/ 6" — a number no channel
    drew, and not the denominator of anything on the row."""
    plan = fanout.plan(db["conn"], steps=SPIKE, recording_ids=db["ids"], span=(0, 400),
                       measured_per_channel_s=0.1)
    out = fanout.start(plan, db_path=db["path"], surrogate=True, surrogate_draws=3)
    assert [len(r["surrogate_run_ids"]) for r in out["runs"]] == [3, 3]
    scored = scoreboard.score_runs(db["conn"], out["run_ids"])
    assert scored["total"]["null_draws"] == 3
    assert scored["total"]["null_draw_runs"] == 6


def test_settings_holds_the_draw_count_per_run_kind(db):
    conn = db["conn"]
    assert ss.null_from_settings(conn, kind="detection")["draws"] == 20
    assert ss.null_from_settings(conn, kind="seed-search")["draws"] == 200
    put_settings(conn, "nulls", {"null.detection.draws": 50})
    assert ss.null_from_settings(conn, kind="detection")["draws"] == 50
    assert ss.null_from_settings(conn, kind="seed-search")["draws"] == 200


def test_phase_randomisation_is_the_default_null_for_a_detection_chain(db):
    assert ss.null_from_settings(db["conn"], kind="detection")["method"] == "phase_randomize"


def test_the_plan_counts_the_null_draws_and_routes_on_the_total(db):
    kw = dict(steps=SPIKE, recording_ids=db["ids"], span=(0, 400), measured_per_channel_s=10.0, ceiling_s=400)
    bare = fanout.plan(db["conn"], **kw)
    assert bare["estimate_s"] == pytest.approx(20.0) and bare["route"] == "local"
    with_null = fanout.plan(db["conn"], null_draws=20, **kw)
    # 2 channels x 10 s x (1 real + 20 draws)
    assert with_null["estimate_s"] == pytest.approx(420.0)
    assert with_null["null_draws"] == 20
    assert with_null["route"] == "cluster"


# ── C: the methods on offer are the block's own ─────────────────────────────

def test_every_method_on_offer_is_one_the_block_runs():
    offered = ss.offered_methods()
    assert [m["id"] for m in offered] == ["phase_randomize", "block_shuffle"]
    choices = next(p for p in get_adapter("preprocessing.surrogate").params if p.name == "method").choices
    assert [m["id"] for m in offered] == list(choices)
    for m in offered:
        assert ss.resolve_null(m["id"])["supported"], m
        assert ss.resolve_null(m["label"])["supported"], m
    assert offered[0]["default"] is True
    assert "timing and order" in offered[1]["note"] and "shape" in offered[1]["note"]


def test_circular_shift_is_still_refused_out_loud():
    assert ss.resolve_null("circular shift")["supported"] is False


def test_the_block_refuses_a_block_under_two_samples():
    spec = get_adapter("preprocessing.surrogate")
    x = np.random.default_rng(0).standard_normal(500)
    t = np.arange(500.0)
    with pytest.raises(ValueError, match="2 samples"):
        spec.run(x, t, 1.0, method="block_shuffle", seed=0, block_s=1.0)   # one sample at 1 Hz
    with pytest.raises(ValueError, match="longest motif"):
        spec.run(x, t, 1.0, method="block_shuffle", seed=0)                # no length given at all
    y = spec.run(x, t, 1.0, method="block_shuffle", seed=0, block_s=50.0).value.x
    assert sorted(y) == sorted(x) and not np.array_equal(y, x)
    # phase randomisation never reads the block length
    spec.run(x, t, 1.0, method="phase_randomize", seed=0)


def test_a_seed_searchs_block_is_twice_the_seed():
    assert ss.default_block_s(60, 1.0) == 120.0
    assert ss.default_block_s(60, 10.0) == 12.0
    x = np.random.default_rng(1).standard_normal(2000)
    out = ss.null_distances(x, x[300:360], draws=2, seed=0, method="block_shuffle")
    assert out["block_s"] == 120.0
    assert ss.null_distances(x, x[300:360], draws=1, seed=0)["block_s"] is None


def test_a_paired_block_shuffle_takes_its_block_from_the_runs_longest_detection(db):
    recipe = make_recipe(db["ids"][0], SPIKE, span=(0, 400))
    out = run_groups.run_paired_recipe(recipe, db_path=db["path"], surrogate=True, surrogate_draws=2,
                                       surrogate_params={"method": "block_shuffle", "seed": 0})
    dets = R.list_detections(db["conn"], out["run_id"])
    assert dets, "the fixture run must detect something for there to be a motif under test"
    longest = max(d["end_idx"] - d["start_idx"] for d in dets)
    for rid in out["surrogate_run_ids"]:
        step = R.load_recipe(db["conn"], R.get_run(db["conn"], rid)["config_id"])["steps"][0]
        assert step["params"]["block_s"] == pytest.approx(max(2.0, 2.0 * longest / 1.0))


# ── D: alpha and the correction reach the cut ───────────────────────────────

def _null(values, draws):
    return {"distances": list(values), "draws": draws}


def test_the_cut_rule_is_read_from_settings(db):
    conn = db["conn"]
    assert ss.cut_rule_from_settings(conn) == {"alpha": 0.01, "correction": "none"}
    put_settings(conn, "nulls", {"alpha": 0.05, "correction": "Benjamini–Hochberg"})
    assert ss.cut_rule_from_settings(conn) == {"alpha": 0.05, "correction": "bh"}
    put_settings(conn, "nulls", {"correction": "Holm"})
    assert ss.cut_rule_from_settings(conn)["correction"] == "holm"


def test_an_unknown_correction_is_refused():
    with pytest.raises(ValueError, match="correction"):
        ss.normalise_correction("Bonferroni-ish")


def test_the_sentence_is_generated_from_the_values_used():
    assert ss.cut_rule()["text"] == "marker: α = 0.01 per null draw · correction: none"
    holm = ss.cut_rule(0.05, "holm", n_channels=3)
    assert holm["correction"] == "holm" and holm["n_channels"] == 3
    assert "α = 0.05" in holm["text"] and "Holm" in holm["text"] and "3 channels" in holm["text"]
    assert "Benjamini–Hochberg" in ss.cut_rule(0.05, "bh", n_channels=2)["text"]


def test_one_channel_uncorrected_is_the_marker_it_always_was():
    null = _null(range(1, 101), 100)
    matches = [3.5, 5.5, 9.0]
    out = ss.recommended_cut_corrected([{"distances": matches, "null": null}], alpha=0.05, correction="none")
    assert out["cut"] == ss.recommended_cut(matches, null, alpha=0.05) == 5.5


def test_holm_and_bh_decide_differently_from_no_correction():
    """Two channels whose closest match has a null rate of 0.03 per draw
    (3 of 100 null distances at or below it), alpha = 0.05.

    none  each channel is tested at 0.05                    -> both pass, cut 5.5
    Holm  the smaller p is tested at 0.05 / 2 = 0.025       -> fails, and so does the rest: no cut
    BH    p(2) = 0.03 <= 0.05 x 2/2                          -> both pass at 0.05, cut 5.5
    """
    chans = [{"distances": [3.5, 5.5], "null": _null(range(1, 101), 100)} for _ in range(2)]
    none = ss.recommended_cut_corrected(chans, alpha=0.05, correction="none")
    holm = ss.recommended_cut_corrected(chans, alpha=0.05, correction="holm")
    bh = ss.recommended_cut_corrected(chans, alpha=0.05, correction="bh")
    assert none["cut"] == 5.5 and none["channels_passing"] == 2
    assert holm["cut"] is None and holm["channels_passing"] == 0
    assert bh["cut"] == 5.5 and bh["channels_passing"] == 2
    assert [c["p"] for c in none["per_channel"]] == [0.03, 0.03]
    assert holm["rule"]["text"] == ss.cut_rule(0.05, "holm", n_channels=2)["text"]


def test_holm_tests_the_strongest_channel_at_the_strictest_level():
    """Channel A's closest match beats every null distance (p = 0); channel B's
    has p = 0.03. Holm: A at 0.05/2 passes, then B at 0.05/1 passes — each
    channel's cut is computed at the level it was tested at, and the marker is
    the stricter of the two so that every match under it passes in its channel."""
    a = {"distances": [0.5, 2.5, 5.5], "null": _null(range(1, 101), 100)}
    b = {"distances": [3.5, 5.5], "null": _null(range(1, 101), 100)}
    out = ss.recommended_cut_corrected([a, b], alpha=0.05, correction="holm")
    assert [c["level"] for c in out["per_channel"]] == [0.025, 0.05]
    assert [c["cut"] for c in out["per_channel"]] == [2.5, 5.5]
    assert out["cut"] == 2.5 and out["channels_passing"] == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
