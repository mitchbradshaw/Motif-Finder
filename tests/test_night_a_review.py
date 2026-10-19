"""
test_night_a_review.py
======================
night pass A (2026-10-19): what the night's drive of Review on the scale fixture found, pinned at the source
(the drive itself is `scripts/night/night_a.py`, against a sandbox bridge).

* **A finished queue says it is finished.** Every live queue whose items are all judged lands on
  `?state=exhausted`, which read "No more items in the demo fixture … the other 0 are not in the fixture" —
  fixture language on the most ordinary end of a real queue. A queue with no items at all said the same.
* **No fixture ids, no fixture words on the face.** "Pick another queue" navigated to the fixture queue `q-12`
  (a 404 on live data), and the arrow keys at either end of a queue toasted "this is the last item in the demo
  fixture" / "the first item in the queue fixture".
"""
import io
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(PROJECT_ROOT, "webui", "client", "src", "review")


def _src(name):
    return io.open(os.path.join(REVIEW, name), encoding="utf-8").read()


def _code(text):
    """The source with its comments taken out (block and line), so a comment's history is not a finding."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


def test_no_fixture_words_on_the_review_face():
    for name in ("common.tsx", "Inspector.tsx", "ClusterView.tsx", "Shell.tsx"):
        code = _code(_src(name))
        for phrase in ("demo fixture", "queue fixture", "not in the fixture"):
            assert phrase not in code, f"{name} still shows the researcher '{phrase}'"


def test_pick_another_queue_opens_a_queue_that_exists():
    code = _code(_src("common.tsx"))
    assert "q-12" not in code, "the queue-end view still navigates to the fixture queue q-12"


def test_a_finished_queue_says_done_and_an_empty_one_says_empty():
    code = _code(_src("common.tsx"))
    # the end view is reached through ?state=exhausted on live data: it must name both real ends
    assert "queue-done" in code, "the end view has no 'every item judged' state for a live queue"
    assert "queue-no-items" in code, "a queue with no items says nothing of the kind"
