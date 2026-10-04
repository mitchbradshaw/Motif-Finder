"""
test_library_seed_edges.py
==========================
fixup-v: the Library gets its edges — a seed-search match becomes a member
with its distance written down, and the seed search can be run at other
scales.

What it pins (headless; the routes are `test_webui_library_edges.py`):

* **The scale bank.** `detection.seed_matches` takes a `scales` parameter: the
  exemplar resampled to each length, `stumpy.match` at each, every distance
  put on the native length's footing (``d * sqrt(m / L)``) so one cut means one
  thing across lengths, and matches that overlap across lengths reduced by the
  page's overlap policy. A one-length bank is today's search, byte for byte, so
  no stored seed recipe re-hashes.
* **The lengths come from one Settings key** (`analysis-defaults` ·
  `seed.scale_bank`), and the page's null is drawn per length.
* **Q39.** A match becomes a Library member only with an accepting verdict
  (`interesting` / `seed`); *include unjudged* is a flag that is off; a
  rejected match keeps its distance on the detection row and nothing else.
* **An edge per distance function.** Each accepted pair carries up to three
  `motif_edge` rows — scale-invariant, symbolic, native-length — each with
  the scale factor, the detection it came from and the recipe that produced it.
* **§4.2.** A match that re-finds an existing member resolves onto it rather
  than making a second one; the seed finding itself is not an edge.
* **The Q3 read-out.** Per scale factor: found · judged · accepted, the same
  pairs' distance under the scale-invariant function and the native-length
  control, and the null per length beside each row.
"""

import json
import os
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import stumpy  # noqa: E402

from Adapters.detection_seed_matches import SPEC, match_exemplar, match_exemplar_bank, parse_scales, reduce_overlaps  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import seeded_search  # noqa: E402
from Working.distances import (  # noqa: E402
    DISTANCE_NATIVE_LENGTH, DISTANCE_SCALE_INVARIANT, DISTANCE_SYMBOLIC, resample_to_length,
)
from Working.library import matching  # noqa: E402
from Working.registration.settings import put_settings  # noqa: E402
from Working.types import Signal  # noqa: E402

M = 60
N = 4000
#: where the shape is planted, and at what length
PLANTS = ((500, 48), (1500, 60), (2600, 75))
BANK = (0.8, 1.0, 1.25)


def _shape(n):
    """A trough with a fast fall and a slow rise — asymmetric, so a copy
    stretched in time is NOT the same samples at native length."""
    u = np.linspace(0.0, 1.0, n)
    fall = np.clip(u / 0.2, 0.0, 1.0)
    rise = np.clip((u - 0.2) / 0.8, 0.0, 1.0)
    return -(fall - rise ** 0.5) * (u < 0.2) - (1.0 - rise ** 0.5) * (u >= 0.2)


def _signal(seed=0):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(N) * 0.02
    for at, n in PLANTS:
        x[at:at + n] += _shape(n)
    return x


# ── 1. the bank ─────────────────────────────────────────────────────────────

def test_parse_scales_reads_a_bank_and_refuses_nonsense():
    assert parse_scales("0.8, 1, 1.25") == (0.8, 1.0, 1.25)
    assert parse_scales("1") == (1.0,)
    assert parse_scales("1.25,0.8,1,1") == (0.8, 1.0, 1.25)
    with pytest.raises(ValueError):
        parse_scales("0.8,-1")
    with pytest.raises(ValueError):
        parse_scales("")


def test_the_bank_finds_the_shape_at_each_length_and_says_which():
    x = _signal()
    q_ = _shape(M)
    rows = match_exemplar_bank(x, q_, BANK, k=10)
    by_site = {}
    for r in rows:
        for at, n in PLANTS:
            if abs(r["index"] - at) <= 3:
                by_site.setdefault(at, []).append(r)
    for at, n in PLANTS:
        best = min(by_site[at], key=lambda r: r["distance"])
        assert best["length"] == n, f"the plant at {at} is {n} samples long"
        assert best["scale"] == pytest.approx(n / M, abs=0.01)


def test_a_bank_distance_is_put_on_the_native_lengths_footing():
    x = _signal()
    q_ = _shape(M)
    rows = match_exemplar_bank(x, q_, BANK, k=10, overlap="all")
    long = [r for r in rows if r["length"] == 75]
    assert long
    raw = stumpy.match(resample_to_length(q_, 75), x, max_matches=10)
    raw_by_index = {int(i): float(d) for d, i in raw}
    for r in long:
        assert r["distance"] == pytest.approx(raw_by_index[r["index"]] * np.sqrt(M / 75), rel=1e-9)


def test_a_one_length_bank_is_todays_search():
    x = _signal()
    q_ = _shape(M)
    today = SPEC.run(x, np.arange(N, dtype=float), 1.0, k=10, max_distance=0.0, exemplar=Signal(x=q_, fs=1.0))
    banked = SPEC.run(x, np.arange(N, dtype=float), 1.0, k=10, max_distance=0.0, exemplar=Signal(x=q_, fs=1.0),
                      scales="1")
    assert banked.value == today.value
    raw = match_exemplar(x, q_, k=10)
    assert tuple(int(r[1]) for r in raw) == today.value.starts


def test_overlapping_matches_across_lengths_are_reduced_by_the_policy():
    rows = [
        {"index": 100, "length": 60, "scale": 1.0, "distance": 2.0},
        {"index": 95, "length": 75, "scale": 1.25, "distance": 1.0},
        {"index": 110, "length": 48, "scale": 0.8, "distance": 3.0},
        {"index": 400, "length": 60, "scale": 1.0, "distance": 4.0},
        # same length and overlapping: stumpy's own exclusion zone decides those, not this policy
        {"index": 420, "length": 60, "scale": 1.0, "distance": 4.5},
    ]
    lowest = reduce_overlaps(rows, "lowest")
    assert sorted((r["index"], r["length"]) for r in lowest) == [(95, 75), (400, 60), (420, 60)]
    first = reduce_overlaps(rows, "first")
    assert sorted((r["index"], r["length"]) for r in first) == [(95, 75), (400, 60), (420, 60)]
    first_late = reduce_overlaps([dict(rows[0]), dict(rows[1], index=105)], "first")
    assert [(r["index"], r["length"]) for r in first_late] == [(100, 60)]
    assert len(reduce_overlaps(rows, "all")) == len(rows)
    with pytest.raises(ValueError):
        reduce_overlaps(rows, "most")


def test_the_block_takes_a_bank_and_records_the_scale_on_each_match():
    names = {p.name for p in SPEC.params}
    assert {"scales", "overlap"} <= names
    x = _signal()
    out = SPEC.run(x, np.arange(N, dtype=float), 1.0, k=10, max_distance=0.0,
                   exemplar=Signal(x=_shape(M), fs=1.0), scales="0.8,1,1.25", overlap="lowest")
    lengths = {e - s for s, e in zip(out.value.starts, out.value.ends)}
    assert {48, 60, 75} <= lengths, "a match is as long as the copy that found it"
    assert all("@" in lab for lab in out.value.labels), "each label says its scale"
    assert set(out.meta["scales"]) == set(BANK)
    assert sum(out.meta["per_scale"].values()) == len(out.value.starts)


# ── 2. one Settings key, a null per length ─────────────────────────────────

def test_the_lengths_come_from_one_settings_key():
    conn = init_db(":memory:")
    assert seeded_search.scale_bank_from_settings(conn) == BANK
    put_settings(conn, seeded_search.SCALE_BANK_PAGE, {seeded_search.SCALE_BANK_KEY: [0.5, 1, 2]})
    assert seeded_search.scale_bank_from_settings(conn) == (0.5, 1.0, 2.0)


def test_candidates_carry_their_scale():
    found = seeded_search.candidates(_signal(), _shape(M), k=10, scales=BANK)
    assert found and all({"scale", "length"} <= set(c) for c in found)
    assert {c["length"] for c in found} >= {48, 60, 75}
    native = seeded_search.candidates(_signal(), _shape(M), k=10)
    assert all(c.get("scale", 1.0) == 1.0 for c in native)


def test_the_null_is_drawn_per_length():
    out = seeded_search.null_distances(_signal(), _shape(M), draws=3, k=5, scales=BANK)
    assert set(out["by_scale"]) == set(BANK)
    for s in BANK:
        assert out["by_scale"][s]["draws"] == 3
    pooled = sum(len(v["distances"]) for v in out["by_scale"].values())
    assert pooled == len(out["distances"])


def test_a_seed_step_carries_the_bank_only_when_it_is_on():
    seed = {"binding": {"source_kind": "library_exemplar", "entry_id": 0, "source_file": "a.mat",
                        "channel": 0, "start_idx": 0, "end_idx": M}}
    plain = seeded_search.seed_steps(seed, k=10)
    assert "scales" not in plain[0]["params"], "a native search keeps its recipe hash"
    bank = seeded_search.seed_steps(seed, k=10, scales=BANK, overlap="lowest")
    assert bank[0]["params"]["scales"] == "0.8,1,1.25"
    assert bank[0]["params"]["overlap"] == "lowest"


# ── 3. resolving a run's matches onto the Library ──────────────────────────

class Lib:
    """A scratch library: two channels of one recording, one exemplar entry,
    a seed run over channel 0 with five matches, its paired null, and a
    second entry whose member sits where one match lands."""

    def __init__(self, tmp):
        self.conn = conn = init_db(":memory:")
        x0 = _signal(0)
        x1 = _signal(1)
        self.rec = []
        for ch, x in enumerate((x0, x1)):
            path = os.path.join(tmp, f"ch{ch}.npy")
            np.save(path, x)
            self.rec.append(q.insert_recording(conn, "syn.mat", ch, 1.0, N, 0, path))
        # the exemplar: the native planting on channel 0
        self.entry = R.insert_motif_entry(conn, self.rec[0], 1500, 1560)
        self.exemplar_member = R.get_or_create_motif_member(conn, self.entry, self.rec[0], 1500, 1560)
        # another entry, whose member is the 0.8x planting on channel 1
        self.other_entry = R.insert_motif_entry(conn, self.rec[1], 500, 548)
        self.other_member = R.get_or_create_motif_member(conn, self.other_entry, self.rec[1], 500, 548)
        steps = seeded_search.seed_steps(
            {"binding": {"source_kind": "library_exemplar", "entry_id": self.entry, "source_file": "syn.mat",
                         "channel": 0, "start_idx": 1500, "end_idx": 1560}},
            k=10, max_distance=4.0, scales=BANK, overlap="lowest")
        recipe = {"recording_id": self.rec[0], "steps": steps, "span": None}
        cfg, self.config_hash = R.get_or_create_config(conn, recipe)
        self.run = R.insert_run(conn, cfg, self.rec[0], 0, N, status="completed")
        self.run1 = R.insert_run(conn, cfg, self.rec[1], 0, N, status="completed")
        d = {}
        d["self"] = R.insert_detection(conn, self.run, 1500, 1560, score=0.0)       # the seed finding itself
        d["short"] = R.insert_detection(conn, self.run, 500, 548, score=1.1)        # 0.8x · interesting
        d["long"] = R.insert_detection(conn, self.run, 2600, 2675, score=1.3)       # 1.25x · seed
        d["rejected"] = R.insert_detection(conn, self.run, 3200, 3260, score=3.5)   # 1x · not interesting
        d["unjudged"] = R.insert_detection(conn, self.run, 3600, 3660, score=3.8)   # 1x · unjudged
        d["refind"] = R.insert_detection(conn, self.run1, 501, 549, score=1.0)      # 0.8x on ch1 · interesting
        self.det = d
        for key, verdict in (("short", "interesting"), ("long", "seed"), ("rejected", "not_interesting"),
                             ("refind", "interesting"), ("self", "seed")):
            conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, ?, '2026-10-04')",
                         (d[key], verdict))
        # the paired null: two draws for the channel-0 run
        self.nulls = []
        for i in range(2):
            n_id = R.insert_run(conn, cfg, self.rec[0], 0, N, status="completed")
            conn.execute("UPDATE runs SET surrogate_of_run_id = ? WHERE id = ?", (self.run, n_id))
            self.nulls.append(n_id)
        R.insert_detection(conn, self.nulls[0], 100, 175, score=3.9)    # 1.25x
        R.insert_detection(conn, self.nulls[0], 900, 948, score=3.7)    # 0.8x
        R.insert_detection(conn, self.nulls[1], 1900, 1975, score=3.95)  # 1.25x
        conn.commit()

    def resolve(self, **kw):
        return matching.resolve_run_matches(self.conn, self.entry, [self.run, self.run1], cut=4.0, **kw)

    def members(self):
        return self.conn.execute("SELECT * FROM motif_member ORDER BY id").fetchall()

    def edges(self):
        return self.conn.execute("SELECT * FROM motif_edge ORDER BY id").fetchall()


@pytest.fixture
def lib():
    with tempfile.TemporaryDirectory() as tmp:
        yield Lib(tmp)


def test_only_an_accepting_verdict_makes_a_member(lib):
    before = len(lib.members())
    out = lib.resolve()
    assert out["accepted"] == 3          # short, long, refind (the self-match is the exemplar)
    assert out["unjudged"] == 1
    assert out["rejected"] == 1
    # short and long are new members; refind resolves onto the other entry's member
    assert len(lib.members()) == before + 2
    spans = {(m["recording_id"], m["start_idx"], m["end_idx"]) for m in lib.members()}
    assert (lib.rec[0], 3200, 3260) not in spans, "a rejected match is not a member"
    assert (lib.rec[0], 3600, 3660) not in spans, "an unjudged match is not a member by default"


def test_include_unjudged_is_a_flag_and_rejected_never_joins(lib):
    lib.resolve(include_unjudged=True)
    spans = {(m["recording_id"], m["start_idx"], m["end_idx"]) for m in lib.members()}
    assert (lib.rec[0], 3600, 3660) in spans
    assert (lib.rec[0], 3200, 3260) not in spans


def test_a_rejected_match_keeps_its_distance_on_the_detection_row(lib):
    lib.resolve()
    row = lib.conn.execute("SELECT score FROM detections WHERE id = ?", (lib.det["rejected"],)).fetchone()
    assert row["score"] == pytest.approx(3.5)
    assert not lib.conn.execute("SELECT 1 FROM motif_edge WHERE detection_id = ?", (lib.det["rejected"],)).fetchall()


def test_each_accepted_pair_carries_an_edge_per_distance_function(lib):
    lib.resolve()
    edges = lib.edges()
    by_det = {}
    for e in edges:
        by_det.setdefault(e["detection_id"], set()).add(e["distance_function"])
    expected = {DISTANCE_SCALE_INVARIANT, DISTANCE_SYMBOLIC, DISTANCE_NATIVE_LENGTH}
    for key in ("short", "long", "refind"):
        assert by_det[lib.det[key]] == expected, key
    assert len(edges) == 9
    for e in edges:
        assert e["member_a_id"] == lib.exemplar_member
        assert e["threshold"] == pytest.approx(4.0), "the cut the search applied"
        recipe = json.loads(e["recipe_json"])
        assert recipe["scale"] == e["scale_factor"]
        assert recipe["distance_function"] == e["distance_function"]
        assert recipe["run_config_hash"] == lib.config_hash
        assert e["recipe_hash"]


def test_the_scale_factor_is_on_every_edge(lib):
    lib.resolve()
    scale = {e["detection_id"]: e["scale_factor"] for e in lib.edges()}
    assert scale[lib.det["short"]] == pytest.approx(0.8)
    assert scale[lib.det["long"]] == pytest.approx(1.25)


def test_the_control_is_larger_than_the_scale_invariant_distance_off_scale(lib):
    lib.resolve()
    vals = {(e["detection_id"], e["distance_function"]): e["distance_value"] for e in lib.edges()}
    long_ = lib.det["long"]
    assert vals[(long_, DISTANCE_NATIVE_LENGTH)] > 2 * vals[(long_, DISTANCE_SCALE_INVARIANT)]


def test_resolving_twice_writes_nothing_new(lib):
    lib.resolve()
    n_m, n_e = len(lib.members()), len(lib.edges())
    again = lib.resolve()
    assert (len(lib.members()), len(lib.edges())) == (n_m, n_e)
    assert again["members_new"] == 0 and again["edges_new"] == 0


def test_a_match_that_refinds_a_member_resolves_onto_it(lib):
    lib.resolve()
    rows = lib.conn.execute("SELECT * FROM motif_member WHERE recording_id = ? AND start_idx BETWEEN 495 AND 505",
                            (lib.rec[1],)).fetchall()
    assert [r["id"] for r in rows] == [lib.other_member], "no second member for the same occurrence"
    e = lib.conn.execute("SELECT * FROM motif_edge WHERE detection_id = ?", (lib.det["refind"],)).fetchall()
    assert {r["member_b_id"] for r in e} == {lib.other_member}


def test_the_seed_finding_itself_is_not_an_edge(lib):
    lib.resolve()
    assert not lib.conn.execute("SELECT 1 FROM motif_edge WHERE member_a_id = member_b_id").fetchall()
    assert not lib.conn.execute("SELECT 1 FROM motif_edge WHERE detection_id = ?", (lib.det["self"],)).fetchall()


def test_a_null_draws_spans_never_become_members(lib):
    lib.resolve(include_unjudged=True)
    spans = {(m["start_idx"], m["end_idx"]) for m in lib.members()}
    assert (100, 175) not in spans and (1900, 1975) not in spans


def test_a_new_member_carries_its_hash_channel_and_a_machine_revision(lib):
    lib.resolve()
    m = lib.conn.execute("SELECT * FROM motif_member WHERE recording_id = ? AND start_idx = 2600",
                         (lib.rec[0],)).fetchone()
    assert m["entry_id"] == lib.entry
    assert m["content_hash"] and m["channel"] == 0
    rev = lib.conn.execute("SELECT * FROM motif_member_revision WHERE member_id = ?", (m["id"],)).fetchall()
    assert len(rev) == 1 and rev[0]["origin"] == "machine" and rev[0]["detection_id"] == lib.det["long"]
    assert m["current_revision_id"] == rev[0]["id"]


def test_edges_for_entry_lists_every_edge_with_both_members(lib):
    lib.resolve()
    rows = matching.edges_for_entry(lib.conn, lib.entry)
    assert len(rows) == 9
    assert {r["member_b_id"] for r in rows} >= {lib.other_member}
    assert all({"distance_function", "distance_value", "threshold", "scale_factor", "recipe_json",
                "b_recording_id", "b_start_idx", "b_end_idx"} <= set(r.keys()) for r in rows)


# ── 4. the Q3 read-out ──────────────────────────────────────────────────────

def test_the_scale_readout_is_filled_from_the_rows(lib):
    lib.resolve()
    out = matching.scale_readout(lib.conn, lib.entry, [lib.run, lib.run1])
    rows = {r["scale"]: r for r in out["rows"]}
    assert set(rows) == set(BANK)
    assert rows[0.8]["found"] == 2 and rows[0.8]["accepted"] == 2
    assert rows[1.25]["found"] == 1 and rows[1.25]["accepted"] == 1
    # the seed finding itself is the exemplar, not a match: it is in no count
    assert rows[1.0]["found"] == 2 and rows[1.0]["judged"] == 1 and rows[1.0]["accepted"] == 0
    assert rows[1.25]["members"] == 1
    long_si = rows[1.25][DISTANCE_SCALE_INVARIANT]
    long_nl = rows[1.25][DISTANCE_NATIVE_LENGTH]
    assert long_si["n"] == long_nl["n"] == 1
    assert long_nl["median"] > long_si["median"]
    assert "within" in long_si
    # the null per length: run 0 drew 2 surrogates; 2 spans at 1.25x and 1 at 0.8x over those 2 draws
    assert out["nullDraws"] == 2
    assert rows[1.25]["nullPerDraw"] == pytest.approx(1.0)
    assert rows[0.8]["nullPerDraw"] == pytest.approx(0.5)
    assert rows[1.0]["nullPerDraw"] == pytest.approx(0.0)
    assert "significan" not in json.dumps(out).lower(), "no test of significance is implied"
