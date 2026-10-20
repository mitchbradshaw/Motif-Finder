"""
test_site_runs_scope_link.py
============================
site-runs (2026-10-20), items 5 and 6: a deep-linked Discovery scope, and the session the page shows after a write.

Item 5. *Explore > Cross-channel > Apply a template across these N channels* opened
`discovery/runs?modal=add-template&channels=667,668,669,666`: channel IDS and no recording, so the session (still on
M2_aug) asked M2_aug for channels named `667...` and three cards printed "no channel(s) ['667', ...] on
M2_aug_concat_fs1". The link now carries `recording=<key>` and the channel NAMES, and the page resolves it with one
pure helper (`discovery/scopeLink.ts`, run here under Node; skips without `node`) before writing it to the session
through `putScope` -- the same write the Scope card makes. A name the recording does not have is refused in words
and nothing is sent.

Item 6. `setScope` merged its patch into the client's copy and never took the bridge's answer, so after a change of
recording the toolbar kept the OLD session's name. The scope is now built from `putScope`'s response by
`scopeFromSession`, the same builder the first read uses.
"""
import io
import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
LINK_TS = os.path.join(SRC, "discovery", "scopeLink.ts")

RECS = [
    {"key": "M2_aug_concat_fs1", "label": "M2 aug", "channels": ["CH1_A1", "CH2_A1", "CH3_A2", "CH4_A2"], "hours": 721.0,
     "heldOut": False},
    {"key": "CO_fs2", "label": "CO", "channels": ["CH1", "CH2", "CH3", "CH4"], "hours": 480.0, "heldOut": False},
    {"key": "M4_aug_concat_fs1", "label": "M4", "channels": ["CH1_A1"], "hours": 500.0, "heldOut": True},
]
CURRENT = {"recording": "M2_aug_concat_fs1", "channels": ["CH1_A1", "CH2_A1", "CH3_A2"], "section": [600.0, 700.0]}


def _node(expr_lines):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(LINK_TS), "webui/client/src/discovery/scopeLink.ts does not exist"
    url = "file:///" + LINK_TS.replace("\\", "/").lstrip("/")
    script = f"import * as L from {json.dumps(url)};\n" + "\n".join(expr_lines)
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _resolve(recording_q, channels_q, current=CURRENT, recs=RECS):
    return _node([f"process.stdout.write(JSON.stringify(L.resolveScopeLink({json.dumps(recording_q)}, "
                  f"{json.dumps(channels_q)}, {json.dumps(current)}, {json.dumps(recs)}) ?? null));"])


def _src(*parts):
    return io.open(os.path.join(SRC, *parts), encoding="utf-8").read()


# ── item 5: the link and its resolution ─────────────────────────────────────

def test_no_link_is_nothing_to_resolve():
    assert _resolve("", "") is None


def test_a_link_with_a_recording_and_channel_names_becomes_that_scope():
    out = _resolve("CO_fs2", "CH2,CH4")
    assert out["scope"]["recording"] == "CO_fs2"
    assert out["scope"]["channels"] == ["CH2", "CH4"]
    # the section is clamped to the new recording: [600, 700] h does not exist on a 480 h one
    s0, s1 = out["scope"]["section"]
    assert 0 <= s0 < s1 <= 480.0


def test_a_section_inside_the_new_recording_is_kept():
    out = _resolve("CO_fs2", "CH1", current={**CURRENT, "section": [10.0, 34.0]})
    assert out["scope"]["section"] == [10.0, 34.0]


def test_channel_names_alone_stay_on_the_sessions_recording_and_section():
    out = _resolve("", "CH4_A2,CH1_A1")
    assert out["scope"] == {"recording": "M2_aug_concat_fs1", "channels": ["CH4_A2", "CH1_A1"], "section": [600.0, 700.0]}


def test_channel_ids_are_refused_in_words_not_sent():
    out = _resolve("", "667,668,669,666")
    assert "scope" not in out
    assert "667" in out["refused"] and "M2 aug" in out["refused"]


def test_a_name_that_is_not_a_channel_of_the_recording_is_refused():
    out = _resolve("CO_fs2", "CH1,CH1_A1")
    assert "CH1_A1" in out["refused"] and "CO" in out["refused"]


def test_an_unknown_recording_is_refused():
    out = _resolve("nope", "CH1")
    assert "nope" in out["refused"]


def test_the_held_out_recording_is_left_to_the_scope_cards_refusal():
    # the Scope card refuses a held-out recording from the client's copy; the link must never write it
    assert _resolve("M4_aug_concat_fs1", "CH1_A1") is None


def test_a_recording_only_link_is_a_view_not_a_write():
    # discovery.json's held-out-refused state opens ?recording=M4...; with the lock off a write would move the
    # whole walk's session onto M4 (Assumed in the report): only a link that names channels is written
    assert _resolve("CO_fs2", "") is None


def test_the_cross_channel_link_carries_the_recording_and_the_names():
    src = _src("explore", "CrossChannelPage.tsx")
    line = next(ln for ln in src.splitlines() if 'testid="act-template"' in ln)
    assert "recording=" in line
    assert "selected.join(',')" not in line, "the link still sends channel ids"
    assert ".name" in line


def test_the_session_writes_a_deep_link_through_putScope_and_clears_it():
    src = _src("discovery", "session.ts")
    assert "resolveScopeLink(" in src
    assert "setRecordingQ(null)" in src and "setChannelsQ(null)" in src
    assert "linkRefused" in src


def test_the_runs_page_holds_the_modal_until_the_link_is_written():
    src = _src("discovery", "RunsPage.tsx")
    assert "dx.linkPending" in src and "dx.linkRefused" in src
    assert 'data-testid="scope-link-refused"' in src or 'testid="scope-link-refused"' in src


# ── item 6: the session the page shows is the bridge's ──────────────────────

def test_the_scope_is_built_from_the_bridges_session():
    payload = {"name": "CO", "recording": "CO_fs2", "channels": ["CH1"], "section": [0, 24],
               "null": {"method": "phase_randomize", "n": 200, "requested": None, "reason": None, "explicit": False},
               "nulls": {"template": {"method": "phase_randomize", "n": 20}}}
    out = _node([f"process.stdout.write(JSON.stringify(L.scopeFromSession({json.dumps(payload)})));"])
    assert out["name"] == "CO" and out["recording"] == "CO_fs2" and out["channels"] == ["CH1"]
    assert out["section"] == [0, 24] and out["saved"] is True
    assert out["nullN"] == 200 and out["nullTemplateN"] == 20 and out["nullExplicit"] is False


def test_setScope_takes_putScopes_answer():
    src = _src("discovery", "session.ts")
    m = re.search(r"putScope\(\{[^}]*\}\)\s*\.then\(([^)]*)\)", src)
    assert m and m.group(1).strip() not in ("", "()"), "setScope ignores the bridge's answer"
    assert "scopeFromSession(" in src


def test_the_scope_summary_chip_has_no_chevron():
    src = _src("discovery", "chrome.tsx")
    start = src.index("export function ScopeSummaryChip")
    body = src[start:src.index("export function", start + 10)]
    assert "chevron" not in body


# ── items 3 and 4: the scoreboard's read and its scroll ─────────────────────

SCORE_TS = os.path.join(SRC, "discovery", "scoreRead.ts")


def _score_node(lines):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(SCORE_TS), "webui/client/src/discovery/scoreRead.ts does not exist"
    url = "file:///" + SCORE_TS.replace("\\", "/").lstrip("/")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e",
                        f"import * as S from {json.dumps(url)};\n" + "\n".join(lines)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_an_answer_read_for_other_runs_is_not_the_scores():
    """Item 4's cause: the first scoreboard read goes out before the runs are in, with no run keys, and answers []
    at once; `useSourced` keeps that [] on screen while the real read (461 s cold on the real session) is out, and
    the page printed "no finished run on this scope yet" and "Send 0 unjudged". An answer counts only for the keys
    it was read for; anything else is "not in yet" (null)."""
    out = _score_node([
        "const k = S.scoreKey(['a','b'], ['CH1'], [0, 24]);",
        "const k0 = S.scoreKey([], ['CH1'], [0, 24]);",
        "process.stdout.write(JSON.stringify([",
        "  S.scoresFor({ key: k0, rows: [] }, k),",
        "  S.scoresFor({ key: k, rows: [{ run: 'a' }] }, k),",
        "  S.scoresFor(null, k),",
        "  S.scoresFor({ key: k0, rows: [] }, k0),",
        "]));",
    ])
    assert out == [None, [{"run": "a"}], None, []]


def test_the_scoreboard_says_it_is_working_while_the_scores_are_out():
    src = _src("discovery", "RunsPage.tsx")
    assert "working out the scores" in src
    start = src.index("function Scoreboard")
    body = src[start:src.index("function otherLine")]
    # the empty line is chosen on `dx.scores === null` before anything else, not only when no other row is drawn
    assert "scores-working" in body


def test_the_send_button_counts_from_its_own_read():
    src = _src("discovery", "RunsPage.tsx")
    start = src.index("function RunActs")
    body = src[start:]
    assert "getRunUnjudged(" in body
    assert "counting the unjudged detections" in body
    assert "total.found - total.judged" not in body
    assert "getRunUnjudged" in _src("api", "discovery.ts")


def test_the_scoreboard_scrolls_past_ten_runs_with_a_sticky_header():
    src = _src("discovery", "RunsPage.tsx")
    assert "SCORE_ROWS_VISIBLE = 10" in src
    assert 'data-testid="scoreboard-scroll"' in src
    css = _src("discovery", "discovery.css")
    assert re.search(r"\.dsc-score-scroll\s+thead\s+th\s*\{[^}]*position:\s*sticky", css)
    assert re.search(r"\.dsc-score-scroll\s*\{[^}]*overflow-y:\s*auto", css)


# ── item 1: a run row's lines ───────────────────────────────────────────────

def test_a_run_row_puts_its_actions_on_their_own_line():
    """The researcher's screenshot: in the 296 px column the name was cut to `dip_se...`, and *Report* and *Run on
    the missing 14* overlapped the text and each other. The small actions now sit on a line of their own under the
    row (grid row 2, every column), the A/B box and the x stay at the right of the name."""
    src = _src("discovery", "chrome.tsx")
    start = src.index("function RunRow")
    body = src[start:src.index("/* ------------------------------------------------------------------ coverage strip")]
    assert 'className="dsc-run-actions"' in body
    acts = body[body.index('className="dsc-run-actions"'):]
    for tid in ("run-missing-", "report-", "retry-", "chain-import-", "open-in-jobs-"):
        assert tid in acts, f"{tid} is not on the actions line"
    # the pick box and the x come BEFORE the actions in the row, so the grid puts them beside the name
    assert body.index("dsc-run-remove") < body.index('className="dsc-run-actions"')
    assert "title={run.label}" in body


def test_a_run_name_wraps_to_two_lines_then_ellipsis():
    css = _src("discovery", "discovery.css")
    assert re.search(r"\.dsc-run-text\s*>\s*b\s*\{[^}]*-webkit-line-clamp:\s*2", css)
    assert re.search(r"\.dsc-run\s*\{[^}]*display:\s*grid", css)
    assert re.search(r"\.dsc-run-actions\s*\{[^}]*grid-column:\s*1\s*/\s*-1", css)


# ── item 2: "Runs drawn: N of M" ────────────────────────────────────────────

PICK_TS = os.path.join(SRC, "discovery", "firesPicker.ts")


def _pick(runs, query):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(PICK_TS), "webui/client/src/discovery/firesPicker.ts does not exist"
    url = "file:///" + PICK_TS.replace("\\", "/").lstrip("/")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e",
                        f"import * as P from {json.dumps(url)};\n"
                        f"process.stdout.write(JSON.stringify(P.pickerGroups({json.dumps(runs)}, {json.dumps(query)})));"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


RUNS = [
    {"key": "human", "label": "human annotations", "kind": "reference"},
    {"key": "drop_v1", "label": "drop_detection_v1", "kind": "template", "template": "drop_detection"},
    {"key": "dip", "label": "dip_search_allch", "kind": "seed"},
    {"key": "b1", "label": "wavelet · 0.1 Hz", "kind": "template", "template": "wavelet", "bandSet": "s1"},
    {"key": "b2", "label": "wavelet · 0.5 Hz", "kind": "template", "template": "wavelet", "bandSet": "s1"},
    {"key": "thr", "label": "signal_threshold", "kind": "template", "template": "signal_threshold"},
]


def test_the_picker_groups_runs_by_kind_with_band_sets_folded():
    groups = _pick(RUNS, "")
    by = {g["key"]: g for g in groups}
    assert [r["key"] for r in by["templates"]["runs"]] == ["drop_v1", "thr"]
    assert [r["key"] for r in by["seeds"]["runs"]] == ["dip"]
    band = [g for g in groups if g["folded"]]
    assert len(band) == 1 and [r["key"] for r in band[0]["runs"]] == ["b1", "b2"]
    assert "human" not in [r["key"] for g in groups for r in g["runs"]]       # the human row is always drawn


def test_the_picker_search_matches_names_case_blind_and_drops_empty_groups():
    groups = _pick(RUNS, "DROP")
    assert [(g["key"], [r["key"] for r in g["runs"]]) for g in groups] == [("templates", ["drop_v1"])]


def test_the_wall_of_eye_links_is_one_button():
    src = _src("discovery", "RunsPage.tsx")
    start = src.index("function WhereFires")
    body = src[start:src.index("function FiresCells")]
    assert "hidden.map(" not in body, "the wall of hidden runs is still drawn under the rows"
    assert 'testid="fires-picker"' in body and "Runs drawn: " in body
    for tid in ("fires-show-all", "fires-hide-all", "fires-picker-search", "fires-hidden"):
        assert tid in body
    assert "fires-eye-${run.key}" in body           # a drawn row keeps its eye


def test_the_default_state_opens_the_picker_before_show_all():
    rows = json.load(io.open(os.path.join(PROJECT_ROOT, "webui", "smoke_pages", "discovery.json"), encoding="utf-8"))
    default = next(r for r in rows if r["page"] == "discovery.runs" and r["state"] == "default")
    clicks = [a["click"] for a in default["actions"] if "click" in a]
    assert clicks[0] == '[data-testid="fires-picker"]'
    assert any("fires-show-all" in c for c in clicks[1:])
