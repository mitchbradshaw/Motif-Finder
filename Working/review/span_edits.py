"""Explicit current-extent links for Review detections, separate from machine output."""


def detection_edits(conn, detection_ids=None):
    # Read-only historical research snapshots predate this additive table.
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_span_edits'").fetchone():
        return {}
    wanted = None if detection_ids is None else set(detection_ids)
    # This small link table only contains events actually redrawn by a person.
    return {int(r["detection_id"]): dict(r) for r in conn.execute(
        "SELECT x.detection_id,a.id annotation_id,a.recording_id,a.start_idx,a.end_idx,a.verdict "
        "FROM review_span_edits x JOIN annotations a ON a.id=x.annotation_id "
        "WHERE a.deleted_at IS NULL")
        if wanted is None or int(r["detection_id"]) in wanted}


def link_detection(conn, detection_id, annotation_id, now):
    old = conn.execute("SELECT annotation_id FROM review_span_edits WHERE detection_id=?",
                       (int(detection_id),)).fetchone()
    if old and int(old[0]) != int(annotation_id):
        conn.execute("UPDATE annotations SET deleted_at=? WHERE id=? AND source='review-span-edit'",
                     (now, int(old[0])))
    conn.execute("INSERT INTO review_span_edits(detection_id,annotation_id) VALUES (?,?) "
                 "ON CONFLICT(detection_id) DO UPDATE SET annotation_id=excluded.annotation_id",
                 (int(detection_id), int(annotation_id)))
