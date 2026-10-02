"""
test_drop_motifs_extent.py
===========================
`Working/Detection/drop_motifs/extent.py` (fixup-h): what can be said about an
event's stored extent from the row alone, and the frame a sequence of events is
drawn in.

* `detect5.window_bounds` brackets an event by its morphology, but a scale-free
  `window_cap_mult x fall` cap is applied first and clamps every branch. The row
  does not record which rule set an edge, so a capped edge and a measured edge
  look identical on screen and one of them is a backstop (QUESTIONS.md Q18).
  `capped_edges` recovers it from the indices: an edge sitting exactly at the cap.
* `sequence_frame` is `drawing_rules.sequence_frames` as numbers rather than as a
  matplotlib figure: back to the PREVIOUS event's trough, capped at 14 falls,
  clipped to the stored snippet (Q19).
* 30 of the 1058 `drop_motifs9` rows carry an array shorter than their indices
  claim (`DETECTION_AND_FIGURES.md` 6.7); sliced by the indices they draw as a
  one-sample fall. `snippet_mismatch` detects it.

Runnable standalone:  python tests/test_drop_motifs_extent.py
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SEED_DIR = os.path.join(PROJECT_ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")


def _ev(onset, trough, start, end, fs=1.0, seg_s=0.0, **more):
    return {"onset_idx": onset, "trough_idx": trough, "snippet_start_idx": start, "snippet_end_idx": end,
            "fs": fs, "segment_seconds": seg_s, "fall_duration_s": (trough - onset) / fs, **more}


def test_an_edge_sitting_exactly_at_the_cap_is_capped():
    from Working.Detection.drop_motifs.extent import capped_edges
    # a 10-sample fall: the cap is 60 samples either side
    assert capped_edges(_ev(100, 110, 40, 150)) == (True, False)
    assert capped_edges(_ev(100, 110, 70, 170)) == (False, True)
    assert capped_edges(_ev(100, 110, 40, 170)) == (True, True)
    assert capped_edges(_ev(100, 110, 71, 169)) == (False, False)


def test_the_cap_is_measured_in_the_falls_the_detector_used():
    """`fall = max(trough - onset, segment_samples)`: a fall shorter than one encoding segment is capped at six
    segments, not six of its own lengths."""
    from Working.Detection.drop_motifs.extent import capped_edges
    e = _ev(1000, 1004, 1000 - 6 * 20, 1300, seg_s=20.0)
    assert capped_edges(e) == (True, False)
    assert capped_edges(_ev(1000, 1004, 1000 - 6 * 4, 1300, seg_s=20.0)) == (False, False)
    assert capped_edges(_ev(100, 110, 70, 150), cap_mult=3.0) == (True, False)


def test_an_edge_clamped_by_the_recording_start_is_not_called_capped():
    """`max(0, onset - cap)`: a window that stops at sample 0 stopped at the recording, which is a different fact."""
    from Working.Detection.drop_motifs.extent import capped_edges
    assert capped_edges(_ev(30, 40, 0, 80)) == (False, False)


def test_capped_counts_on_the_seed_store():
    """The count the page prints behind its info icon, on the 410 seed events."""
    from Working.Detection.drop_motifs import store as S
    from Working.Detection.drop_motifs.extent import capped_counts
    c = capped_counts(S.load_events(SEED_DIR))
    assert c["n"] == 410 and c["cap_mult"] == 6.0
    assert (c["left"], c["right"], c["both"]) == (185, 119, 90)


def test_a_sequence_frame_reaches_back_to_the_previous_trough():
    from Working.Detection.drop_motifs.extent import MAX_PRE_FALLS, POST_TROUGH_FALLS, PRE_ONSET_FALLS, sequence_frames
    members = [
        _ev(1000, 1010, 0, 5000),          # first of the run: no predecessor, 1.2 falls
        _ev(1060, 1070, 0, 5000),          # 50 samples after the previous trough
        _ev(3000, 3010, 0, 5000),          # a long silence: capped at 14 falls
    ]
    f = sequence_frames(members)
    assert f[0]["pre_s"] == pytest.approx(PRE_ONSET_FALLS * 10) and f[0]["first"] is True and f[0]["capped"] is False
    assert f[1]["pre_s"] == pytest.approx(50.0) and f[1]["reach_falls"] == pytest.approx(5.0)
    assert f[2]["pre_s"] == pytest.approx(MAX_PRE_FALLS * 10) and f[2]["capped"] is True
    assert all(x["post_s"] == pytest.approx(POST_TROUGH_FALLS * 10) for x in f)


def test_a_sequence_frame_never_reaches_past_the_stored_snippet():
    """Nothing is drawn that the store did not keep: the frame is clipped to the snippet and says it was."""
    from Working.Detection.drop_motifs.extent import sequence_frames
    f = sequence_frames([_ev(1000, 1010, 995, 1015)])[0]
    assert f["pre_s"] == pytest.approx(5.0) and f["post_s"] == pytest.approx(5.0) and f["clipped"] is True


def test_sequence_frames_are_per_recording_and_in_time_order():
    """The previous event is the previous one on the SAME channel, whatever order the rows arrive in."""
    from Working.Detection.drop_motifs.extent import sequence_frames
    a1 = _ev(1000, 1010, 0, 5000, recording_id=1, event_id="a1")
    a2 = _ev(1060, 1070, 0, 5000, recording_id=1, event_id="a2")
    b1 = _ev(1030, 1040, 0, 5000, recording_id=2, event_id="b1")
    f = sequence_frames([a2, b1, a1])
    assert [x["first"] for x in f] == [False, True, True]
    assert f[0]["pre_s"] == pytest.approx(50.0)


def test_a_snippet_shorter_than_its_indices_claim_is_detected():
    from Working.Detection.drop_motifs.extent import snippet_mismatch
    row = _ev(3520, 3530, 3508, 3625)
    assert snippet_mismatch(row, 16) == {"stored": 16, "claimed": 117}
    assert snippet_mismatch(row, 117) is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
