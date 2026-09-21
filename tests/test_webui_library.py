"""
test_webui_library.py
=====================
Route-level guarantees of the Library bridge (`webui/server/library.py`,
stage-3 Prompt 03). What a page cannot be trusted to catch:

* every read returns its declared contract shape, with the keys
  `webui/client/src/fixtures/library.ts` promises — a missing key renders as
  `undefined`, which draws as an empty cell rather than as an error;
* an unknown family is `{kind:'missing'}` and an unknown grouping is an empty
  payload — a 200 the page can draw, never a 500 and never a blank;
* the held-out recording is refused, in both runtime modes;
* a dry run writes **nothing** — the row counts of every table it could touch
  are identical before and after;
* a write routed through the wrong rule-5 door is a `PermissionError`, not a
  quiet crossing of the machine/human line;
* an export is a real download: the right content type and a
  `Content-Disposition: attachment`.

FastAPI lives only in `webui/.venv` (system-site-packages over conda), so
under the conda `pytest` this file skips with a message; run it with

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_library.py

to see it execute. Nothing here touches `DATA/`: the database is built by
`init_db()` in a tmp dir and seeded with synthetic rows, and the channel
`.npy` files are written by the fixture, so the traces the routes return are
genuinely read off disk rather than mocked.
"""

import json
import os
import sys
import time

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.library import router as library_router  # noqa: E402
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

FS = 1.0
N_SAMPLES = 36000          # 10 hours at 1 Hz
CHANNELS = ("CH1_A1", "CH2_A1")


# ── the seeded database ─────────────────────────────────────────────────────

def _write_channel(dir_path, name, n=N_SAMPLES):
    """A real .npy the bridge memmaps, so a returned trace is real decimated mV."""
    t = np.arange(n, dtype=float)
    x = 0.2 * np.sin(t / 97.0) + 0.02 * np.cos(t / 7.0)
    path = os.path.join(dir_path, f"{name}.npy")
    np.save(path, x.astype(np.float32))
    return path


def _seed(tmp_path):
    """A small but complete library: two channels of one recording, a held-out
    recording, four members in two families, one omitted, a sequence, a window
    set, a template, a hand edit and a registered bundle."""
    npy_dir = tmp_path / "npy"
    npy_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))

    rec_ids = []
    for ch in range(len(CHANNELS)):
        path = _write_channel(str(npy_dir), f"norm_{ch}")
        cur = conn.execute(
            "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
            "VALUES ('M2_aug_concat_fs1.mat', ?, ?, ?, 0, ?)", (ch, FS, N_SAMPLES, path))
        rec_ids.append(cur.lastrowid)
    held = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES (?, 0, ?, ?, 0, 'held.npy')", (HELD_OUT_FILE, FS, N_SAMPLES)).lastrowid

    # four members, two families, plus one that did not fit
    spans = [(rec_ids[0], 100, 160), (rec_ids[0], 900, 962),
             (rec_ids[1], 2000, 2058), (rec_ids[1], 5000, 5061), (rec_ids[0], 9000, 9040)]
    member_ids = []
    for i, (rid, a, b) in enumerate(spans):
        entry = conn.execute(
            "INSERT INTO motif_entry (recording_id, start_idx, end_idx, scale, content_hash, tags, created_at) "
            "VALUES (?, ?, ?, 'event', ?, ?, '2026-09-14T09:00:00')",
            (rid, a, b, f"hash{i}", json.dumps(["sharkfin" if i < 2 else "burst"]))).lastrowid
        mid = conn.execute(
            "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx, content_hash) "
            "VALUES (?, ?, ?, ?, ?)", (entry, rid, a, b, f"hash{i}")).lastrowid
        member_ids.append(mid)
        conn.execute(
            "INSERT INTO motif_member_revision (member_id, revision, origin, start_idx, end_idx, "
            "content_hash, created_at) VALUES (?, 1, 'machine', ?, ?, ?, '2026-09-14T09:00:00')",
            (mid, a, b, f"hash{i}"))
    # The tags the importers actually write: `motif_entry_tags` against
    # `tag_vocabulary`, not the legacy `motif_entry.tags` JSON column. Entry 3
    # is left out of the normalised tables on purpose so the legacy column is
    # still exercised as the fallback it is.
    vocab = {}
    for value in ("sharkfin", "trough"):
        vocab[value] = conn.execute(
            "INSERT INTO tag_vocabulary (category, value, active) VALUES ('element', ?, 1)",
            (value,)).lastrowid
    corpus_tag = conn.execute(
        "INSERT INTO tag_vocabulary (category, value, active) VALUES ('corpus', 'oyster', 1)").lastrowid
    entry_of = {i: conn.execute(
        "SELECT entry_id FROM motif_member WHERE id = ?", (mid,)).fetchone()[0]
        for i, mid in enumerate(member_ids)}
    for i, tag_ids in ((0, (vocab["sharkfin"], corpus_tag)), (1, (vocab["sharkfin"],)),
                       (2, (vocab["trough"],)), (3, (vocab["trough"], vocab["sharkfin"]))):
        for tag_id in tag_ids:
            conn.execute("INSERT INTO motif_entry_tags (entry_id, tag_id) VALUES (?, ?)",
                         (entry_of[i], tag_id))

    # a spike-train entry, so /counts can tell the two scales apart
    conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, scale, created_at) "
                 "VALUES (?, 20000, 20600, 'train', '2026-09-14T09:00:00')", (rec_ids[0],))

    gid = conn.execute(
        "INSERT INTO groupings (name, unit, basis, method, params_json, cut, n_families, n_assigned, "
        "n_omitted, recipe_hash, created_at, actor) VALUES ('motifs · shape', 'single_motifs', "
        "'shape-distance', 'ward', '{\"min_group\": 2}', 0.42, 2, 4, 1, 'abc123', "
        "'2026-09-14T11:02:00', 'this installation')").lastrowid
    for i, mid in enumerate(member_ids[:4]):
        conn.execute(
            "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
            "family_label, distance, is_medoid) VALUES (?, 'single_motifs', ?, ?, ?, ?, ?, ?)",
            (gid, mid, f"hash{i}", 1 if i < 2 else 2, "F-01" if i < 2 else "F-02",
             0.1 * (i + 1), 1 if i in (0, 2) else 0))
    conn.execute(
        "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
        "family_label, distance, omit_reason) VALUES (?, 'single_motifs', ?, 'hash4', NULL, 'F-01', "
        "0.9, 'past the cut')", (gid, member_ids[4]))
    # an assignment naming a member row that is not there. The real catalogue
    # had four of these and the bridge dropped them in silence, so the grouping
    # card and the atlas disagreed by four with nothing to reconcile them.
    conn.execute(
        "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
        "family_label, distance) VALUES (?, 'single_motifs', ?, 'hash-gone', 1, 'F-01', 0.3)",
        (gid, max(member_ids) + 500))

    # two reviewed spans that OVERLAP: 0…18000 and 9000…27000 is 27,000 samples
    # of 36,000 seen, not 36,000. Summing them reads as a fully reviewed channel.
    conn.execute("INSERT INTO reviewed_spans (recording_id, start_idx, end_idx, source, reviewed_at) "
                 "VALUES (?, 0, 18000, 'Explore', '2026-09-14T10:00:00')", (rec_ids[0],))
    conn.execute("INSERT INTO reviewed_spans (recording_id, start_idx, end_idx, source, reviewed_at) "
                 "VALUES (?, 9000, 27000, 'Review', '2026-09-15T10:00:00')", (rec_ids[0],))

    seq = conn.execute(
        "INSERT INTO sequences (sequence_key, origin, recording_id, channel, start_idx, end_idx, "
        "n_events, needs_extraction, source_kind, created_at) VALUES ('sq-a', 'machine', ?, 0, 100, "
        "1000, 2, 0, 'sequence_csv', '2026-09-14T09:00:00')", (rec_ids[0],)).lastrowid
    conn.execute("INSERT INTO sequence_members (sequence_id, position, member_id, start_idx, end_idx, "
                 "gap_before) VALUES (?, 0, ?, 100, 160, NULL)", (seq, member_ids[0]))
    conn.execute("INSERT INTO sequence_members (sequence_id, position, member_id, start_idx, end_idx, "
                 "gap_before) VALUES (?, 1, ?, 900, 962, 740.0)", (seq, member_ids[1]))
    # one the importer could not resolve: the claim is recorded, the events are not invented
    conn.execute("INSERT INTO sequences (sequence_key, origin, recording_id, n_events, "
                 "needs_extraction, source_kind, created_at) VALUES ('sq-b', 'human', ?, 3, 1, "
                 "'excel_catalog', '2026-09-14T09:00:00')", (rec_ids[0],))

    # three more sequences and a sequence grouping over them, so "order kept"
    # has something to measure: two of the three run F-01 then F-02, the third
    # runs them the other way round. One member sequence was drawn by a person
    # (`origin='human'`), which is not the same thing as a person having
    # judged it.
    seq_ids = {}
    for key, origin, events in (("sq-c", "machine", ((member_ids[0], 100, 160, None),
                                                     (member_ids[2], 2000, 2058, 1840.0))),
                                ("sq-d", "machine", ((member_ids[2], 2000, 2058, None),
                                                     (member_ids[1], 900, 962, 60.0))),
                                ("sq-e", "human", ((member_ids[0], 100, 160, None),
                                                   (member_ids[3], 5000, 5061, 4840.0)))):
        sid = conn.execute(
            "INSERT INTO sequences (sequence_key, origin, recording_id, channel, start_idx, end_idx, "
            "n_events, needs_extraction, source_kind, created_at) VALUES (?, ?, ?, 0, 100, 5100, ?, 0, "
            "'sequence_csv', '2026-09-14T09:00:00')", (key, origin, rec_ids[0], len(events))).lastrowid
        seq_ids[key] = sid
        for position, (mid, a, b, gap) in enumerate(events):
            conn.execute("INSERT INTO sequence_members (sequence_id, position, member_id, start_idx, "
                         "end_idx, gap_before) VALUES (?, ?, ?, ?, ?, ?)", (sid, position, mid, a, b, gap))

    seq_gid = conn.execute(
        "INSERT INTO groupings (name, unit, basis, method, params_json, cut, n_families, n_assigned, "
        "n_omitted, recipe_hash, created_at, actor) VALUES ('sequences · order', 'sequences', "
        "'sequence-similarity', 'ward', '{\"min_group\": 2}', 0.5, 1, 3, 1, 'seq123', "
        "'2026-09-14T11:30:00', 'this installation')").lastrowid
    for key, distance, medoid in (("sq-c", 0.05, 1), ("sq-e", 0.2, 0), ("sq-d", 0.3, 0)):
        conn.execute(
            "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
            "family_label, distance, is_medoid) VALUES (?, 'sequences', ?, ?, 1, 'F-01', ?, ?)",
            (seq_gid, seq_ids[key], f"seqhash-{key}", distance, medoid))
    conn.execute(
        "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
        "family_label, distance, omit_reason) VALUES (?, 'sequences', ?, 'seqhash-a', NULL, 'F-01', "
        "0.8, 'past_cut')", (seq_gid, seq))

    conn.execute(
        "INSERT INTO window_sets (name, version, path, recording_id, channel, fs, window_length, "
        "stride, gap, n_windows, split_json, spacing_json, coverage_json, labels_source, "
        "recipe_hash, created_at) VALUES ('ws_test_600s', 1, 'ws.npz', ?, 0, ?, 600, 300, 900, "
        "120, '{\"train\": 80, \"validation\": 20, \"test\": 20}', '{\"blocked\": true}', "
        "'{\"labelled_windows\": 30}', 'Review verdicts', 'rh1', '2026-09-14T09:00:00')",
        (rec_ids[0], FS))

    conn.execute("INSERT INTO templates (name, steps_json, kind, version, builtin, description, "
                 "created_at, updated_at) VALUES ('drop_v1', ?, 'detection', 1, 1, 'the drop "
                 "detector', '2026-09-14T09:00:00', '2026-09-14T09:00:00')",
                 (json.dumps([{"stage": "preprocessing", "algorithm": "detrend", "params": {"window_s": 4916.67}},
                              {"stage": "detection", "algorithm": "drop_detection", "params": {}}]),))

    conn.execute("INSERT INTO hand_edits (content_hash, kind, family_label, value, grouping_id, "
                 "active, created_at, actor) VALUES ('hash1', 'tag', 'F-01', 'clean', ?, 1, "
                 "'2026-09-14T12:00:00', 'this installation')", (gid,))
    conn.execute("INSERT INTO registered_artifacts (kind, path, name, created_at, active) VALUES "
                 "('drop_motif_store', 'DATA/library_seed/drop_motifs5', 'drop_motifs5', "
                 "'2026-09-14T09:00:00', 1)")
    conn.execute("INSERT INTO registered_artifacts (kind, path, name, created_at, active) VALUES "
                 "('drop_motif_store', 'DATA/library_seed/M4_aug_holdout', 'M4_aug_holdout', "
                 "'2026-09-14T09:00:00', 1)")
    conn.commit()
    conn.close()
    return db, held, gid, member_ids


def _fake_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    return dist


def _bridge(tmp_path, mode):
    db, held, gid, member_ids = _seed(tmp_path)
    rt = Runtime(mode=mode, stamp=f"20260922-{mode}", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(_fake_dist(tmp_path)))
    rt.setup()
    app = create_app(rt)
    # app.py is owned by the orchestrator; the router is included here so the
    # tests exercise exactly the lines app.py will gain. It MUST sit before the
    # `/api/{rest:path}` guard — Starlette matches in registration order, so a
    # router added after it is unreachable and every call returns the JSON 404,
    # which reads like a typo rather than the wiring bug it is. `create_app`
    # has already registered that guard, so the fixture moves the new routes
    # ahead of it to reproduce the order app.py will have.
    guard = next(i for i, r in enumerate(app.router.routes)
                 if str(getattr(r, "path", "")) == "/api/{rest:path}")
    before = len(app.router.routes)
    app.include_router(library_router)
    # This FastAPI version appends a single lazy `_IncludedRouter` entry rather
    # than the twenty routes themselves, so the move is by position, not path.
    moved = app.router.routes[before:]
    del app.router.routes[before:]
    app.router.routes[guard:guard] = moved
    return rt, app, held, gid, member_ids


@pytest.fixture
def bridge(tmp_path):
    rt, app, held, gid, member_ids = _bridge(tmp_path, "sandbox")
    try:
        with TestClient(app) as client:
            yield client, {"held": held, "gid": gid, "members": member_ids, "rt": rt}
    finally:
        rt.restore()


@pytest.fixture(params=["sandbox", "project"])
def both_modes(request, tmp_path):
    rt, app, held, gid, member_ids = _bridge(tmp_path, request.param)
    try:
        with TestClient(app) as client:
            yield client, request.param
    finally:
        rt.restore()


def _ok(response):
    assert response.status_code == 200, response.text[:400]
    return response.json()


# ── reads: the contract shapes ──────────────────────────────────────────────

def test_counts_separates_the_two_entry_scales(bridge):
    client, _ = bridge
    body = _ok(client.get("/api/library/counts"))
    assert set(body) == {"motifs", "windowSets", "templates", "spikeTrains", "sequences"}
    assert body["motifs"] == 5          # five event-scale entries
    assert body["spikeTrains"] == 1     # the train-scale one is not a motif
    assert body["sequences"] == 5
    assert body["windowSets"] == 1
    assert body["templates"] >= 1


def test_groupings_emit_g_NN_ids_the_client_can_parse(bridge):
    client, ctx = bridge
    rows = _ok(client.get("/api/library/groupings"))
    assert rows, "the seeded grouping must be listed"
    row = rows[0]
    for key in ("id", "unit", "basis", "basisLabel", "params", "chip", "computed",
                "motifs", "families", "omitted", "handEditsKept"):
        assert key in row, key
    # the client's nextGroupingId does Number(id.slice(2)) — `g-NN` or NaN
    assert row["id"] == f"g-{ctx['gid']:02d}"
    assert row["id"].startswith("g-") and row["id"][2:].isdigit()
    assert row["unit"] == "motifs"                  # not the DB's 'single_motifs'
    assert isinstance(row["chip"], list) and len(row["chip"]) == 2
    assert row["computed"] == "14 Sep 2026"
    assert row["motifs"] == 5 and row["families"] == 2 and row["omitted"] == 1


def test_recurrence_carries_recordings_families_coverage_and_shared_ground(bridge):
    client, _ = bridge
    body = _ok(client.get("/api/library/recurrence"))
    assert set(body) >= {"recordings", "families", "coverage", "sharedGround"}
    keys = {r["key"] for r in body["recordings"]}
    assert "M2_aug_fs1" in keys, "source_file -> RecGroup.key drops _concat and the extension"
    held = next(r for r in body["recordings"] if r.get("heldOut"))
    assert held["channels"] == [], "the held-out recording offers no channels to draw"
    normal = next(r for r in body["recordings"] if r["key"] == "M2_aug_fs1")
    for key in ("key", "label", "hours", "reviewedPct", "channels", "hiddenChannels"):
        assert key in normal, key
    assert normal["label"] == "M2_aug fs1"
    assert all(":" in k for k in body["coverage"]), "coverage is keyed `${recKey}:${channel}`"


def test_a_cell_never_looked_at_differs_from_one_looked_at_and_empty(bridge):
    """Spec 8.4: absent and never-looked must not render alike."""
    client, _ = bridge
    families = _ok(client.get("/api/library/families"))
    cells = {}
    for fam in families:
        cells.update(fam["cells"])
    reviewed = [c for c in cells.values() if not c.get("noCoverage")]
    unreviewed = [c for c in cells.values() if c.get("noCoverage")]
    assert reviewed, "the reviewed channel must produce cells without noCoverage"
    assert unreviewed, "the unreviewed channel must be flagged noCoverage, not left blank"
    for cell in cells.values():
        assert set(cell) <= {"perHour", "count", "artifact", "noCoverage"}


def test_families_return_real_decimated_traces_and_a_colour_on_every_row(bridge):
    client, _ = bridge
    families = _ok(client.get("/api/library/families"))
    assert len(families) == 2
    for i, fam in enumerate(families):
        for key in ("id", "name", "colour", "shape", "members", "inScope", "recordings", "hand",
                    "artifact", "durationS", "durationSd", "depthMv", "depthLabel", "judgedPct",
                    "judged", "exemplar", "medoid", "exemplarMedoidD", "meanMemberD", "snrDb",
                    "artifactChannels", "propChannels", "indChannels", "edges", "cells",
                    "exemplarTrace", "medoidTrace", "ampBins"):
            assert key in fam, f"{fam.get('id')} missing {key}"
        # FAMILY_COLOURS only covers F-01…F-11; a live id outside it would be undefined
        assert isinstance(fam["colour"], str) and fam["colour"].startswith("#")
        assert len(fam["ampBins"]) == 12
        assert fam["exemplarTrace"], "the trace must be real mV read off the channel, not empty"
        assert all(isinstance(v, (int, float)) for v in fam["exemplarTrace"])
        assert len(fam["exemplarTrace"]) <= 2 * 60 + 2
        # the shape is a real `element` tag value or nothing — the vocabulary
        # is open (trough, sharkfin, stegasaurus, …) and "drop" is no longer a
        # default stood in for a morphology nobody measured
        assert fam["shape"] is None or isinstance(fam["shape"], str) and fam["shape"]
    assert {f["id"] for f in families} == {"F-01", "F-02"}
    assert families[0]["shape"] == "sharkfin", "the shape is read off the entry's tags"


def test_family_detail_carries_real_revisions_and_the_hand_edit_record(bridge):
    client, _ = bridge
    body = _ok(client.get("/api/library/family/F-01"))
    assert body["kind"] == "motif"
    detail = body["detail"]
    for key in ("family", "cut", "members", "removed", "channels", "depthLabel", "handAdded"):
        assert key in detail, key
    assert detail["cut"] == 0.42
    member = detail["members"][0]
    for key in ("id", "d", "recording", "channel", "onsetH", "durationS", "amplitudeMv",
                "verdict", "foundBy", "revisions", "tags", "seed"):
        assert key in member, key
    assert member["recording"] == "M2_aug fs1", "Member.recording carries the LABEL"
    assert member["recordingKey"] == "M2_aug_fs1", "and recordingKey carries the key"
    assert member["revisions"], "revisions come from motif_member_revision, not invented"
    assert member["revisions"][0]["rev"] == 1
    assert member["verdict"] == "unjudged"
    assert any(m.get("handRecord") for m in detail["members"]), "the seeded hand edit must surface"


def test_an_unknown_family_is_missing_not_a_500(bridge):
    client, _ = bridge
    body = _ok(client.get("/api/library/family/F-99"))
    assert body == {"kind": "missing", "id": "F-99"}


def test_an_unknown_grouping_is_handled_rather_than_crashing(bridge):
    client, _ = bridge
    assert _ok(client.get("/api/library/families?grouping=g-99")) == []
    assert _ok(client.get("/api/library/family/F-01?grouping=g-99")) == {"kind": "missing", "id": "F-01"}
    omitted = _ok(client.get("/api/library/omitted?grouping=not-a-grouping"))
    assert omitted["singles"] == [] and omitted["sequences"] == []


def test_omitted_carries_the_reason_it_did_not_fit(bridge):
    client, ctx = bridge
    body = _ok(client.get(f"/api/library/omitted?grouping=g-{ctx['gid']:02d}"))
    assert set(body) >= {"groupingId", "singles", "sequences"}
    assert len(body["singles"]) == 1
    entry = body["singles"][0]
    for key in ("id", "kind", "nearest", "d", "recording", "channel", "onsetH", "shape", "amp", "seed"):
        assert key in entry, key
    assert entry["omitReason"] == "past the cut", "the reason is the point of the list"


def test_grouping_editor_lists_nine_bases_with_a_reason_on_each_that_cannot_apply(bridge):
    client, _ = bridge
    body = _ok(client.get("/api/library/grouping-editor"))
    assert set(body) >= {"units", "bases", "distributions", "clusterings"}
    assert len(body["bases"]) == 9
    for option in body["bases"]:
        assert set(option) >= {"kind", "group", "title", "caption", "units"}
        assert option["group"] in ("distance", "feature bins · no distance", "labels")
    seq_sim = next(b for b in body["bases"] if b["kind"] == "sequence-similarity")
    assert seq_sim.get("reason"), "spec 8.2: a basis that does not apply is disabled WITH its reason"
    assert set(body["distributions"]) == {"frequency-content", "amplitude", "timescale",
                                          "shape-distance", "sequence-similarity"}
    units = {u["unit"]: u["count"] for u in body["units"]}
    assert units == {"motifs": 5, "sequences": 5, "spike-trains": 1}, "live counts, not fixtures"
    amp = body["distributions"]["amplitude"]
    assert amp and all(set(b) == {"lo", "hi", "n"} for b in amp), "distributions are real FeatureBins"


def test_window_sets_and_templates_return_their_rows(bridge):
    client, _ = bridge
    sets = _ok(client.get("/api/library/windowsets"))
    assert len(sets) == 1
    row = sets[0]
    for key in ("id", "version", "saved", "source", "recording", "recordingKeys", "channels",
                "spacing", "windowS", "gapS", "windows", "split", "splitLabel", "labelledPct",
                "labelledWindows", "check", "checkReason", "splitPlan", "classCounts"):
        assert key in row, key
    assert row["splitLabel"] == "blocked" and row["check"] == "train-safe"

    templates = _ok(client.get("/api/library/templates"))
    assert templates
    t = next(t for t in templates if t["name"] == "drop_v1")
    for key in ("name", "version", "kind", "signature", "badges", "stages", "recipe",
                "nullModel", "containsModel", "runs", "runCount", "versions", "scores"):
        assert key in t, key
    glyphs = [s["glyph"] for s in t["stages"]]
    assert glyphs == ["baseline", "drop_detection"], "stages map to the BlockGlyph vocabulary"


def test_sequences_needing_extraction_are_the_review_queue(bridge):
    client, _ = bridge
    every = _ok(client.get("/api/library/sequences"))
    pending = _ok(client.get("/api/library/sequences?needs_extraction=1"))
    assert len(every) == 5 and len(pending) == 1
    assert pending[0]["needsExtraction"] is True
    assert pending[0]["nEvents"] == 3, "the claim is recorded even though the events are not"


def test_import_bundles_come_from_the_registry(bridge):
    client, _ = bridge
    bundles = _ok(client.get("/api/library/import/bundles"))
    paths = {b["path"] for b in bundles}
    assert "DATA/library_seed/drop_motifs5" in paths
    held = next(b for b in bundles if "M4_aug" in b["path"])
    assert held["heldOut"] is True


# ── the held-out refusal ────────────────────────────────────────────────────

def test_the_held_out_file_is_refused_in_both_modes(both_modes):
    client, _mode = both_modes
    r = client.post("/api/library/import", json={"path": "DATA/library_seed/M4_aug_holdout"})
    assert r.status_code == 423, r.text[:300]
    assert HELD_OUT_FILE.split("_concat")[0] in r.text or HELD_OUT_FILE in r.text

    dry = client.post("/api/library/import/dry-run", json={"path": "DATA/library_seed/M4_aug_holdout"})
    body = _ok(dry)
    assert body["heldOut"] is True
    assert body["blockedReason"], "a held-out bundle says why, rather than failing silently"


def test_no_family_payload_ever_carries_the_held_out_recording(bridge):
    client, _ = bridge
    body = _ok(client.get("/api/library/recurrence"))
    for fam in body["families"]:
        assert not any(k.startswith("M4_aug") for k in fam["cells"])


# ── writes ──────────────────────────────────────────────────────────────────

def _row_counts(db_path):
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    finally:
        conn.close()


def test_a_dry_run_writes_nothing(bridge):
    client, ctx = bridge
    db_path = ctx["rt"].db_path
    before = _row_counts(db_path)
    r = client.post("/api/library/import/dry-run",
                    json={"path": "DATA/library_seed/does_not_exist_anywhere"})
    body = _ok(r)
    assert body["blockedReason"], "a missing bundle is a named refusal, not an exception"
    after = _row_counts(db_path)
    assert before == after, "a dry run that wrote something is a dry run that lied"


def test_dry_run_payload_is_an_import_bundle(bridge):
    client, _ = bridge
    body = _ok(client.post("/api/library/import/dry-run", json={"path": "DATA/library_seed/nope"}))
    for key in ("path", "provenanceFound", "counts", "checks", "creates", "sample"):
        assert key in body, key
    assert set(body["counts"]) == {"motifs", "spikeTrains", "recordings", "channels"}


@pytest.mark.xfail(reason=(
    "webui/server/writes.py does not yet know the Library tables. Until the "
    "orchestrator extends HUMAN_TABLES with 'groupings', 'grouping_assignments' and "
    "'hand_edits' (and MACHINE_TABLES with 'window_sets'), every Library write is a "
    "loud PermissionError naming rule 5 — which is the seam working, not a bug here."),
    strict=False)
def test_a_hand_edit_goes_in_and_out_through_the_human_door(bridge):
    client, ctx = bridge
    r = client.post("/api/library/hand-edits", json={
        "contentHash": "hash2", "kind": "make_exemplar", "familyLabel": "F-02",
        "grouping": f"g-{ctx['gid']:02d}"})
    body = _ok(r)
    edit_id = body["id"]
    assert body["content_hash"] == "hash2" and body["active"] == 1

    gone = _ok(client.delete(f"/api/library/hand-edits/{edit_id}"))
    assert gone["active"] == 0, "undo flips active; it does not delete the record of the decision"
    assert client.delete("/api/library/hand-edits/99999").status_code == 404


def test_a_hand_edit_without_a_content_hash_is_refused(bridge):
    client, _ = bridge
    r = client.post("/api/library/hand-edits", json={"contentHash": "", "kind": "tag"})
    assert r.status_code == 400
    assert "content" in r.text.lower()


def test_rule_5_refuses_a_library_write_routed_through_the_machine_door():
    """The seam itself: `groupings`, `grouping_assignments` and `hand_edits` are
    human tables. Routing one through `write_machine` must raise, loudly, rather
    than quietly crossing the line rule 5 exists to hold."""
    import sqlite3

    from server import writes

    conn = sqlite3.connect(":memory:")
    for table in ("groupings", "grouping_assignments", "hand_edits", "motif_entry"):
        with pytest.raises(PermissionError) as excinfo:
            writes.write_machine(conn, table, {"name": "x"})
        assert "rule 5" in str(excinfo.value)
    # and the machine-side table refuses the human door
    with pytest.raises(PermissionError):
        writes.write_human(conn, "window_sets", {"name": "x"})


@pytest.mark.xfail(reason=(
    "webui/server/writes.py does not yet know the Library tables. Until the "
    "orchestrator extends HUMAN_TABLES with 'groupings', 'grouping_assignments' and "
    "'hand_edits' (and MACHINE_TABLES with 'window_sets'), every Library write is a "
    "loud PermissionError naming rule 5 — which is the seam working, not a bug here."),
    strict=False)
def test_saving_a_grouping_writes_the_row_and_its_assignments(bridge):
    client, ctx = bridge
    before = _ok(client.get("/api/library/groupings"))
    r = client.post("/api/library/groupings", json={
        "unit": "motifs", "basis": "amplitude", "method": "feature_bins",
        "params": {"count": 4}, "cut": 0.5, "name": "by amplitude",
        "assignments": [
            {"ref": ctx["members"][0], "contentHash": "hash0", "familyId": 1,
             "familyLabel": "F-01", "distance": 0.1, "isMedoid": True},
            {"ref": ctx["members"][1], "contentHash": "hash1", "familyId": None,
             "familyLabel": None, "distance": 0.8, "omitReason": "past the cut"},
        ]})
    saved = _ok(r)
    assert saved["id"].startswith("g-")
    assert saved["families"] == 1 and saved["omitted"] == 1
    after = _ok(client.get("/api/library/groupings"))
    assert len(after) == len(before) + 1


def test_running_a_grouping_returns_a_regroup_job(bridge):
    client, _ = bridge
    body = _ok(client.post("/api/library/groupings/run",
                           json={"unit": "motifs", "basis": "amplitude", "method": "feature_bins",
                                 "params": {"count": 3}}))
    assert body["kind"] == "regroup" and isinstance(body["job_id"], int)
    # the job is a real jobs-table job the existing routes can answer for
    snap = _ok(client.get(f"/api/jobs/{body['job_id']}"))
    assert snap["kind"] == "regroup"


def test_a_regroup_job_actually_SUCCEEDS(bridge):
    """The test above asserts the job starts, and a job that starts and then
    dies of a KeyError satisfies it. That is exactly what happened: the route
    built items as `{"ref", "waveform"}` where the engine reads `member_ref`
    and `values`, so every regroup job this bridge ever started ended `failed`,
    and the only thing that noticed was a red card in the browser.

    Asserting the terminal state is what closes that gap.
    """
    client, _ = bridge
    body = _ok(client.post("/api/library/groupings/run",
                           json={"unit": "motifs", "basis": "shape-distance",
                                 # `min_group` 2, because the seeded library has five
                                 # members and ward's default floor is ten — every family
                                 # would be correctly omitted as too small, and "0 groups"
                                 # would look like the failure this test is here to catch.
                                 "method": "ward",
                                 "params": {"cut": 0.6, "min_group": 2}}))
    job_id = body["job_id"]
    for _ in range(600):                       # the fit is seconds at test size
        snap = _ok(client.get(f"/api/jobs/{job_id}"))
        if snap["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert snap["status"] == "completed", snap.get("error") or snap
    # and it produced a real answer, not an empty one that merely did not throw
    preview = snap["result"]["preview"]
    assert preview["groups"] >= 1
    assert preview["members"] >= 1
    assert snap["result"]["assignments"]


def test_the_cut_sliders_merge_heights_are_not_always_empty(bridge):
    """`_merge_heights` wrapped the same wrong item shape in a bare
    `except Exception: return []`, so `/grouping-editor` returned an empty
    histogram for every distance basis and had done since it was written —
    silently, because an empty distribution and a broken one look identical.
    A bin count is the cheapest assertion that tells them apart.
    """
    client, _ = bridge
    editor = _ok(client.get("/api/library/grouping-editor?unit=motifs"))
    heights = editor["distributions"].get("shape-distance")
    assert heights, "the cut slider has no distribution to draw"
    assert sum(b["n"] for b in heights) > 0


def test_an_unknown_grouping_unit_is_a_400_not_a_silent_default(bridge):
    client, _ = bridge
    r = client.post("/api/library/groupings/run", json={"unit": "bananas"})
    assert r.status_code == 400


# ── export ──────────────────────────────────────────────────────────────────

def test_family_export_is_a_real_download_in_both_formats(bridge):
    client, _ = bridge
    r = client.get("/api/library/export/family/F-01?format=json")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert 'attachment; filename="family-F-01.json"' in r.headers["content-disposition"]

    r = client.get("/api/library/export/family/F-01?format=csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="family-F-01.csv"' in r.headers["content-disposition"]
    assert "recording" in r.text.splitlines()[0]


def test_atlas_export_and_an_unknown_family_export(bridge):
    client, _ = bridge
    r = client.get("/api/library/export/atlas?format=csv")
    assert r.status_code == 200
    assert 'attachment; filename="atlas.csv"' in r.headers["content-disposition"]
    assert client.get("/api/library/export/family/F-99").status_code == 404


@pytest.mark.xfail(reason=(
    "the orchestrator owns webui/server/writes.py; this test states the extension it "
    "needs and turns XPASS the moment it lands"), strict=False)
def test_writes_py_must_learn_the_library_tables():
    """The exact extension `webui/server/writes.py` needs, per §3.5 of the
    standard. This is the orchestrator's edit, not this ticket's — the test
    states the requirement so it cannot be lost between the two.

    `sequences` / `sequence_members` are on NEITHER list on purpose: they pick
    their door by their `origin` column, so a blanket entry on either list
    would be exactly the quiet crossing rule 5 exists to prevent.
    """
    from server import writes

    for table in ("groupings", "grouping_assignments", "hand_edits"):
        assert writes.is_human_table(table), (
            f"{table} is human (§3.5): a grouping and a hand edit are a person's "
            f"decision about the library, not a detector's output")
    assert writes.is_machine_table("window_sets"), (
        "window_sets is machine (§3.5): a window set is produced by a recipe")
    for table in ("sequences", "sequence_members"):
        assert not writes.is_human_table(table) and not writes.is_machine_table(table), (
            f"{table} must be on NEITHER list: its door is chosen per row by `origin`, "
            f"so a blanket listing would let a detector's claim in through the human door")


# ── what the critics found on the live library ──────────────────────────────

def test_a_channel_nobody_reviewed_gets_a_cell_of_its_own(bridge):
    """A missing cell used to mean "reviewed, no members" on the client, so
    every channel nobody has opened read as an examined-and-empty negative
    result. Absence now carries no meaning: every channel of every
    non-held-out recording is stated, with its own count and its own coverage."""
    client, _ = bridge
    body = _ok(client.get("/api/library/recurrence"))
    drawable = {f"{r['key']}:{ch}" for r in body["recordings"] if not r.get("heldOut")
                for ch in r["channels"]}
    assert drawable, "the fixture must offer channels to draw"
    for fam in body["families"]:
        assert drawable <= set(fam["cells"]), f"{fam['id']} leaves a channel to be guessed at"
    # a cell that holds members is never flagged as though it held none
    with_members = [c for fam in body["families"] for c in fam["cells"].values() if c["count"]]
    assert with_members, "the fixture's families have members"
    for cell in with_members:
        assert cell["count"] > 0, "noCoverage is about the coverage, never about the count"
    # and a channel nobody has reviewed is flagged on every family, not left absent
    unreviewed = drawable - set(body["coverage"])
    assert unreviewed, "the fixture leaves one channel unreviewed"
    for fam in body["families"]:
        for ck in unreviewed:
            assert fam["cells"][ck].get("noCoverage") is True, f"{fam['id']} {ck}"


def test_overlapping_reviewed_spans_are_merged_not_summed(bridge):
    """0…18000 and 9000…27000 is 27,000 samples of 36,000 seen. Summing the
    rows reported 36,000 — a channel a person half-reviewed read as complete."""
    client, _ = bridge
    body = _ok(client.get("/api/library/recurrence"))
    assert len(body["coverage"]) == 1, "one channel of the fixture was reviewed"
    seen = next(iter(body["coverage"].values()))
    assert abs(seen - 27000 / 36000) < 1e-3, f"union, not sum: {seen}"
    row = next(r for r in body["recordings"] if r["key"] == "M2_aug_fs1")
    assert row["reviewedPct"] == 37.5, "one channel at 75%, one at 0%"


def test_the_family_shape_is_the_entrys_own_element_tag(bridge):
    """All 149 live families reported shape "drop" because the code read the
    legacy `motif_entry.tags` column, which is empty on every row."""
    client, _ = bridge
    families = {f["id"]: f for f in _ok(client.get("/api/library/families"))}
    assert families["F-01"]["shape"] == "sharkfin"
    assert families["F-01"]["shapeLabel"] == "sharkfin"
    # F-02's members carry trough twice and sharkfin once: the majority is the
    # shape and the disagreement is reported rather than hidden (§3.4)
    assert families["F-02"]["shape"] == "trough"
    assert families["F-02"]["shapeLabel"] == "mixed · trough 2 · sharkfin 1"
    assert families["F-02"]["shapeMix"] == {"trough": 2, "sharkfin": 1}


def test_an_assignment_naming_a_member_that_is_gone_is_counted_not_dropped(bridge):
    client, ctx = bridge
    row = next(r for r in _ok(client.get("/api/library/groupings"))
               if r["id"] == f"g-{ctx['gid']:02d}")
    assert row["unresolved"] == 1, "the dangling assignment is stated, not silently discarded"
    assert _ok(client.get("/api/library/recurrence"))["unresolved"] == 1


def test_a_sequence_family_is_reachable_by_unit_and_never_substituted(bridge):
    """`F-01` names a motif family and a sequence family. Matching motifs
    first opened the wrong one under the id the caller asked for."""
    client, _ = bridge
    seq = _ok(client.get("/api/library/family/F-01?unit=sequences"))
    assert seq["kind"] == "sequence", seq
    assert seq["family"]["sequences"] == 3
    motif = _ok(client.get("/api/library/family/F-01?unit=motifs"))
    assert motif["kind"] == "motif"
    assert motif["detail"]["family"]["members"] == 2
    # with no unit the motif family answers, and it says the label also names a
    # sequence family rather than letting the caller assume it does not
    both = _ok(client.get("/api/library/family/F-01"))
    assert both["kind"] == "motif" and both["otherUnit"] == "sequences"
    # a unit that names nothing is a missing family, not another family's data
    assert _ok(client.get("/api/library/family/F-02?unit=sequences")) == {
        "kind": "missing", "id": "F-02", "unit": "sequences"}
    assert client.get("/api/library/family/F-01?unit=bogus").status_code == 400


def test_order_kept_counts_sequences_that_preserve_the_exemplars_order(bridge):
    """"order kept 14 of 10" was the exemplar's event count over the member
    count — two different quantities, the first bigger than the second."""
    client, _ = bridge
    fam = _ok(client.get("/api/library/family/F-01?unit=sequences"))["family"]
    assert fam["exemplarEvents"] == 2, "the exemplar's composition is its own number"
    assert fam["orderKept"] == 2 and fam["orderKeptOf"] == 3
    assert fam["orderKept"] <= fam["orderKeptOf"], "a ratio its own denominator can hold"


def test_judged_on_a_sequence_family_counts_verdicts_not_who_drew_it(bridge):
    """One member sequence has `origin='human'`, which says a person drew it,
    not that a person judged it. Numerator and denominator are both motifs."""
    client, _ = bridge
    fam = _ok(client.get("/api/library/family/F-01?unit=sequences"))["family"]
    assert fam["judgedMotifs"] == 0, "nobody has passed a verdict on these motifs"
    assert fam["judgedOf"] == 6, "six member motifs across the three sequences"
    assert fam["judgedPct"] == 0.0


def test_omitted_answers_for_both_units_and_names_the_catalogue_count(bridge):
    """The route resolved one grouping for both halves, so `sequences` was
    empty on every default call, and the page's "motifs in no sequence" was a
    grouping count wearing a catalogue label."""
    client, _ = bridge
    body = _ok(client.get("/api/library/omitted"))
    assert len(body["singles"]) == 1, "the motif grouping's omission"
    assert len(body["sequences"]) == 1, "and the sequence grouping's, in one read"
    assert body["groupingId"] and body["sequenceGroupingId"]
    assert body["groupingId"] != body["sequenceGroupingId"]
    assert body["singles"][0]["omitReason"] == "past the cut"
    assert body["sequences"][0]["omitReason"] == "past_cut"
    # a catalogue fact, named as one: four of the five members are in a sequence
    assert body["motifsInNoSequence"] == 1
    # an omitted motif's shape is its own tag, or nothing — never "drop" by default
    assert body["singles"][0]["shape"] in (None, "burst")


def test_an_invented_grouping_is_denied_rather_than_echoed_back(bridge):
    client, _ = bridge
    body = _ok(client.get("/api/library/omitted?grouping=g-77"))
    assert body["groupingId"] is None, "the route must not invent a grouping it does not have"
    assert body["singles"] == [] and body["sequences"] == []


def test_the_dry_run_counts_rows_that_are_already_held(tmp_path):
    """`counts.motifs` read `n_created + n_duplicate`, which counts neither the
    `already_present` outcome nor the rows themselves, so a bundle already held
    end to end reported 0 motifs and "0 of N already present" on the same card
    whose outcome line read `already_present × N`."""
    from server import corpus as corpus_mod
    from server import library as lib

    class _Report:
        source = "bundle"

        @staticmethod
        def as_dict():
            return {"n_rows": 10, "n_created": 1, "n_duplicate": 2,
                    "outcomes": {"created": 1, "member_added": 2, "already_present": 6, "skipped": 1},
                    "samples": [{"source_ref": "id001", "recording_id": 1, "start_idx": 100,
                                 "end_idx": 160, "outcome": "already_present", "detail": "member 1"}],
                    "warnings": [], "flags": []}

    db = str(tmp_path / "bundle.sqlite")
    init_db(db).close()
    conn = corpus_mod.connect(db)
    try:
        bundle = lib._import_bundle_payload(conn, "some/bundle", _Report(), "drop_motif_store")
    finally:
        conn.close()
    assert bundle["counts"]["motifs"] == 9, "ten rows less the one nothing will touch"
    assert "8 of 10 rows already describe a shape" in bundle["checks"][0]["detail"]
    assert bundle["creates"] == ["already_present × 6", "created × 1", "member_added × 2",
                                 "skipped × 1"]
    row = bundle["sample"][0]
    assert row["id"] == "id001", "the preview reads `source_ref`, the key the report carries"
    assert row["outcome"] == "already_present", "and says what would happen to it"
    # a field this read does not carry is absent, never a zero standing in for one
    assert row["amp"] is None and row["shape"] is None and row["seed"] is None
