"""
test_webui_header_counts.py
===========================
The header's "N need you" is the one piece of chrome whose whole job is to
tell a researcher there is work waiting. It was a fixture constant (`3`) while
`GET /api/review/counts` — a route that exists, is tested, and said 160 — was
never called. A critic found that in round 1, it was **reported fixed**, and
round 2 found it again.

So this file exists to make the constant's return a test failure rather than a
third finding. It reads the client source; there is no Node test runner in this
repo (the client's gate is `tsc -b`, `npm run build` and `webui/smoke.py`), and
a source-level assertion is what can be run from the headless suite.

What it pins:
  * the header reads the live count through `useReviewNeedYou`;
  * no fixture constant is left lying next to it for someone to reach for;
  * the hook calls the route, and answers 0 on failure rather than throwing —
    ambient chrome on every page must not take Explore down with Review.

Runnable standalone:  python tests/test_webui_header_counts.py
"""

import io
import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")


def _read(*parts):
    path = os.path.join(CLIENT_SRC, *parts)
    if not os.path.isfile(path):
        pytest.skip(f"{path} is not in this checkout")
    return io.open(path, encoding="utf-8").read()


def _client_files():
    for root, _dirs, names in os.walk(CLIENT_SRC):
        for name in names:
            if name.endswith((".ts", ".tsx")):
                yield os.path.join(root, name)


def test_the_header_reads_the_live_review_count():
    src = _read("shell", "Header.tsx")
    assert "useReviewNeedYou" in src, (
        "the header must read /api/review/counts, not a constant")
    assert re.search(r"const\s+review\s*=\s*useReviewNeedYou\(\)", src), (
        "the count the chip adds up must be the one the hook returns")


def test_no_fixture_constant_is_left_beside_the_live_count():
    """A dead `DEMO_NEED_YOU = 3` is how this came back the first time."""
    offenders = []
    for path in _client_files():
        src = io.open(path, encoding="utf-8").read()
        # the word may appear in prose explaining the history; a declaration may not
        if re.search(r"\b(?:const|let|var|export const)\s+DEMO_NEED_YOU\b", src):
            offenders.append(os.path.relpath(path, PROJECT_ROOT))
    assert not offenders, f"the fixture count is still declared in: {offenders}"


def test_the_hook_calls_the_route_and_fails_to_zero_rather_than_throwing():
    src = _read("api", "needYou.ts")
    assert "/api/review/counts" in src
    assert "need_you" in src, "the route's own key, not a re-invented one"
    assert "setN(0)" in src, (
        "a Review outage must not take the header down on every other workspace")
    assert not re.search(r"=\s*useState\(\s*[1-9]", src), (
        "the hook must start at 0, never at a plausible-looking number")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
