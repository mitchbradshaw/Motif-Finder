"""tq-rules (2026-10-25), the bridge half: the queue listing asks `_queue_payload` for what it wants.

`_queue_payload(filters=...)` is a mode: "full" (the queue's own read carries its whole filter), "summary" (the
listing: a Discovery picked queue's `detection_ids` list becomes `detection_ids_count`) and "none" (an item's queue
header leaves `filters` out). The listing route no longer strips the list by hand.

FastAPI lives only in `webui/.venv`; under the conda pytest this file skips.
"""
import inspect
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")

from server import review as R  # noqa: E402

COUNTS = {"total": 3, "judged": 1, "remaining": 2}


def _q(filters):
    return {"id": 9, "name": "q", "source_kind": "detections", "filters": filters, "filters_json": "{}"}


@pytest.fixture(autouse=True)
def _no_pace(monkeypatch):
    monkeypatch.setattr(R.queues_mod, "queue_pace_s", lambda conn, qid: None)


def test_full_keeps_the_filter_and_drops_filters_json():
    out = R._queue_payload(None, _q({"detection_ids": [1, 2, 3], "run_id": 4}), counts=COUNTS, filters="full")
    assert out["filters"] == {"detection_ids": [1, 2, 3], "run_id": 4}
    assert "filters_json" not in out and out["total"] == 3


def test_summary_counts_the_detection_list_instead_of_carrying_it():
    out = R._queue_payload(None, _q({"detection_ids": [1, 2, 3], "run_id": 4}), counts=COUNTS, filters="summary")
    assert out["filters"] == {"run_id": 4, "detection_ids_count": 3}
    plain = R._queue_payload(None, _q({"run_id": 4}), counts=COUNTS, filters="summary")
    assert plain["filters"] == {"run_id": 4}


def test_none_leaves_the_filter_out():
    out = R._queue_payload(None, _q({"detection_ids": [1]}), counts=COUNTS, filters="none")
    assert "filters" not in out and "filters_json" not in out


def test_the_listing_route_asks_for_the_summary_and_strips_nothing_itself():
    src = inspect.getsource(R.get_queues)
    assert 'filters="summary"' in src
    assert "detection_ids" not in src
