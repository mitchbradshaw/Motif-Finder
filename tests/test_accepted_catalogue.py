"""Catalogue invariants: physical copies and regions must not inflate counts."""
from scripts.thesis.accepted_catalogue import canonical_span, overlap_components
import json
import sqlite3
import numpy as np


def obs(rid, a, b, name):
    return {"canonical_recording_id": rid, "canonical_start": a, "canonical_end": b, "ref": name}


def test_overlap_union_keeps_all_provenance_but_not_abutting_or_other_channels():
    rows = [obs(1, 0, 10, "a"), obs(1, 8, 20, "b"), obs(1, 19, 25, "c"),
            obs(1, 25, 30, "touch"), obs(2, 0, 30, "different_channel")]
    got = overlap_components(rows)
    assert [[r["ref"] for r in g] for g in got] == [["a", "b", "c"], ["touch"], ["different_channel"]]


def test_old_mju_excerpt_and_five_channel_copy_map_to_one_physical_span():
    def rec(rid, file, ch, fs, parent=None, offset=None, dec=None):
        return dict(id=rid, source_file=file, channel=ch, fs=fs,
                    parent_recording_id=parent, parent_offset=offset, decimation=dec)
    recs = {1: rec(1, "MJu26a_fs10.mat", 13, 10),
            2: rec(2, "L_LM_Jul_26_J_raw.mat", 2, 10),
            3: rec(3, "L_LM_Jul_26_J_raw_fs2.mat", 2, 2),
            4: rec(4, "Mushroom_260720_0509_4hrs_CH14_fs1.mat", 0, 1, 2, 1000, 10)}
    assert canonical_span(recs[2], 1100, 1200, recs) == (1, 1100, 1200)
    assert canonical_span(recs[3], 220, 240, recs) == (1, 1100, 1200)
    assert canonical_span(recs[4], 10, 20, recs) == (1, 1100, 1200)


def test_publish_preserves_original_looks_and_is_idempotent(tmp_path, monkeypatch):
    from Working.database.schema import init_db
    from Working.database import queries as q, runs as r
    from Working.library.verdicts import member_verdicts
    from scripts.thesis.accepted_catalogue import build
    from scripts.thesis.publish_accepted_catalogue import add_trains, publish
    from scripts.thesis.accepted_boundary_review import signature, apply_decisions
    monkeypatch.chdir(tmp_path)
    c = init_db(":memory:")
    c.row_factory = sqlite3.Row
    np.save(tmp_path / "x.npy", np.sin(np.arange(1000) / 10))
    rid = q.insert_recording(c, "MJu26a_fs10.mat", 14, 10., 1000, 0, "x.npy")
    cfg, _ = r.get_or_create_config(c, {"steps": []})
    run = r.insert_run(c, cfg, rid, 0, 1000, status="completed")
    det = r.insert_detection(c, run, 80, 360)
    c.execute("insert into adjudications(detection_id,verdict,created_at) values (?,'interesting','2026-01-01')", (det,))
    c.commit()
    before = [tuple(v) for v in c.execute("select * from adjudications")]
    # A previously imported occurrence can have a stored-snippet hash different
    # from the native recording's hash. Reuse it without rewriting its source.
    entry = r.insert_motif_entry(c, rid, 90, 230)
    c.execute("update motif_entry set source_kind='event_store',source_store='original store',content_hash='old-snippet-hash' where id=?", (entry,))
    member = r.get_or_create_motif_member(c, entry, rid, 90, 230)
    c.commit()
    evs = [dict(event_id=f"p{i}", recording_id=rid, source_recording_id=rid,
                 start_idx=a, end_idx=b, peak_idx=p, source_start_idx=a,
                 source_end_idx=b, prominence_mv=10.)
           for i, (a, b, p) in enumerate([(90, 230, 120), (200, 350, 240)])]
    trains = [dict(id="fixture_train", source_recording_id=rid, start_s=0, end_s=50,
                  label="fixture", method="fixture proposals", prominence_mv=1, events=evs)]
    made = add_trains(c, trains)
    rows, events, recs = build(c)
    assert len(events) == 2, "a broad accepted look must not glue separate train peaks together"
    assert all(e["source_count"] == 2 for e in events)
    assert all(e["acceptance_level"] == "train_level" for e in events)
    pub = publish(c, events, rows, recs)
    c.commit()
    counts = [c.execute(f"select count(*) from {t}").fetchone()[0] for t in ["annotations", "motif_member", "groupings"]]
    add_trains(c, trains)
    rows, events, recs = build(c)
    again = publish(c, events, rows, recs)
    c.commit()
    assert again["grouping_id"] == pub["grouping_id"]
    assert counts == [c.execute(f"select count(*) from {t}").fetchone()[0] for t in ["annotations", "motif_member", "groupings"]]
    assert [tuple(v) for v in c.execute("select * from adjudications")] == before
    mm = [dict(v) for v in c.execute("select id member_id,recording_id,start_idx,end_idx from motif_member")]
    assert all(v["side"] == "yes" for v in member_verdicts(c, mm).values())
    held = c.execute("select source_kind,source_store,content_hash from motif_entry where id=?", (entry,)).fetchone()
    assert tuple(held) == ("event_store", "original store", "old-snippet-hash")
    # Explicit boundary edits split one broad member without allowing its old
    # context/provenance to merge the checked children back together.
    original = events[0]
    manifest = [{"event_id": original["event_id"], "recording_id": rid,
                 "source_refs": original["source_refs"], "context_start": 0, "context_end": 1000}]
    key = signature(manifest)
    (tmp_path / f"review_manifest_{key}.json").write_text(json.dumps(manifest))
    doc = {"format": "mycowave-boundary-review-v1", "manifest_hash": key, "decisions": [
        {"event_id": original["event_id"], "recording_id": rid, "complete": True,
         "segments": [{"start_idx": 80, "end_idx": 160}, {"start_idx": 140, "end_idx": 210}],
         "reviewed_at": "2026-11-08T00:00:00Z"}]}
    path = tmp_path / "choices.json"
    path.write_text(json.dumps(doc))
    apply_decisions(c, path, tmp_path)
    c.commit()
    _, corrected, _ = build(c)
    checked = [e for e in corrected if e["boundary_status"] == "human_checked"]
    assert len(checked) == 2
    assert {(e["start_idx"], e["end_idx"]) for e in checked} == {(80, 160), (140, 210)}
    assert all(e["count_as_verified_single_event"] for e in checked)
    seq = c.execute("SELECT * FROM sequences WHERE source_kind='catalogue_checked_segments'").fetchone()
    assert seq is not None and seq["n_events"] == 2
    assert len(c.execute("SELECT * FROM sequence_members WHERE sequence_id=?", (seq["id"],)).fetchall()) == 2
    assert c.execute("SELECT gap_before FROM sequence_members WHERE sequence_id=? AND position=1", (seq["id"],)).fetchone()[0] == 6.0
    corrected_rows, corrected_events, corrected_recs = build(c)
    publish(c, corrected_events, corrected_rows, corrected_recs)
    assert c.execute("SELECT COUNT(*) FROM sequence_members WHERE sequence_id=? AND member_id IS NOT NULL", (seq["id"],)).fetchone()[0] == 2
    previous_annotations = c.execute("select count(*) from annotations").fetchone()[0]
    apply_decisions(c, path, tmp_path)
    assert previous_annotations == c.execute("select count(*) from annotations").fetchone()[0]
    assert c.execute("SELECT COUNT(*) FROM sequences WHERE source_kind='catalogue_checked_segments'").fetchone()[0] == 1
    c.close()


def test_boundary_review_refuses_wrong_channel_or_outside_context():
    import pytest
    from scripts.thesis.accepted_boundary_review import signature, validate_decisions
    manifest = [{"event_id": "one", "recording_id": 1, "context_start": 0, "context_end": 100, "source_refs": ["annotation:1"]}]
    choice = {"event_id": "one", "recording_id": 1, "complete": True,
              "segments": [{"start_idx": 10, "end_idx": 20}], "reviewed_at": "2026-11-08T00:00:00Z"}
    doc = {"format": "mycowave-boundary-review-v1", "manifest_hash": signature(manifest), "decisions": [choice]}
    assert len(validate_decisions(doc, manifest)) == 1
    choice["recording_id"] = 2
    with pytest.raises(ValueError, match="Recording"):
        validate_decisions(doc, manifest)
    choice["recording_id"] = 1
    choice["segments"][0]["end_idx"] = 101
    with pytest.raises(ValueError, match="outside"):
        validate_decisions(doc, manifest)


def test_library_queue_provenance_uses_annotation_row_not_member_target():
    from Working.database.schema import init_db
    from Working.database import queries as q
    from scripts.thesis.accepted_catalogue import collect
    c = init_db(":memory:")
    c.row_factory = sqlite3.Row
    rid = q.insert_recording(c, "LM_fs2.mat", 0, 2., 2000, 0, "not-read.npy")
    aid = q.insert_annotation(c, rid, 10, 30, "interesting", "library_review")
    qid = c.execute("INSERT INTO review_queues(name,source_kind,unit,writes_to,created_at) "
                    "VALUES ('family','library-family','member','annotations','2026-11-08')").lastrowid
    payload = json.dumps({"targets": [{"target_id": 999, "row_id": aid}]})
    c.execute("INSERT INTO review_audit(queue_id,action,target_table,target_ids,payload_json,created_at) "
              "VALUES (?,'verdict','annotations','[999]',?,'2026-11-08')", (qid, payload))
    rows, _ = collect(c)
    assert next(r for r in rows if r["ref"] == f"annotation:{aid}")["queue_ids"] == [qid]
    c.close()


def test_legacy_relative_observation_uses_the_shared_absolute_coordinate_rule():
    from Working.database.schema import init_db
    from Working.database import queries as q, runs as r
    from scripts.thesis.accepted_catalogue import build
    c = init_db(":memory:")
    c.row_factory = sqlite3.Row
    rid = q.insert_recording(c, "LM_fs2.mat", 0, 2., 2000, 0, "not-read.npy")
    cfg, _ = r.get_or_create_config(c, {"steps": []})
    run = r.insert_run(c, cfg, rid, 500, 1000, started_at="2026-09-01", status="completed")
    det = r.insert_detection(c, run, 10, 30)
    c.execute("insert into adjudications(detection_id,verdict,created_at) values (?,'interesting','2026-01-01')", (det,))
    _, events, _ = build(c)
    assert len(events) == 1
    assert (events[0]["start_idx"], events[0]["end_idx"]) == (510, 530)
    c.close()
