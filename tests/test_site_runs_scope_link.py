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
    # another recording is another session (the bridge opens it): it keeps ITS section, which the bridge clamps to
    # the recording -- the old recording's [600, 700] h is not carried over (it would overwrite that session's own)
    assert out["scope"]["section"] is None


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


def test_the_session_writes_a_deep_link_through_writeSession_and_clears_it():
    # tq-scope (2026-10-25): the link's resolution, write, keys and error live in one hook, discovery/useScopeLink.ts
    hook = _src("discovery", "useScopeLink.ts")
    assert "resolveScopeLink(" in hook and "writeSession(" in hook
    assert "setRecordingQ(null)" in hook and "setChannelsQ(null)" in hook
    src = _src("discovery", "session.ts")
    assert "useScopeLink(" in src and "linkRefused" in src


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


def test_setScope_takes_writeSessions_answer():
    src = _src("discovery", "session.ts")
    m = re.search(r"writeSession\((\{[^}]*\})\)\s*\.then\(([^)]*)\)", src)
    assert m and m.group(2).strip() not in ("", "()"), "setScope ignores the bridge's answer"
    assert "scopeFromSession(" in src


def test_the_scope_summary_chip_has_no_chevron():
    src = _src("discovery", "chrome.tsx")
    start = src.index("export function ScopeSummaryChip")
    body = src[start:src.index("export function", start + 10)]
    assert "chevron" not in body


# ── items 3 and 4: the scoreboard's read and its scroll ─────────────────────

def test_an_answer_read_for_another_question_is_not_the_answer():
    """Item 4's cause: the first scoreboard read goes out before the runs are in, with no run keys, and answers []
    at once; `useSourced` keeps that [] on screen while the real read (461 s cold on the real session) is out, and
    the page printed "no finished run on this scope yet" and "Send 0 unjudged". An answer counts only for the key
    it was read for; anything else is "not in yet" (null).

    tq-scope (2026-10-25): the rule lives once, in the seam (`useSourcedFor`), and the scoreboard and the run's
    unjudged count both read through it; scoreRead.ts and RunActs' hand-written `run_key` check are gone."""
    seam = _src("api", "seam.ts")
    m = re.search(r"export function useSourcedFor<T>\(key: string,.*?\n\}", seam, re.S)
    assert m and "heldFor(" in m.group(0), "useSourcedFor does not answer through the pure keyedRead.heldFor"
    assert not os.path.exists(os.path.join(SRC, "discovery", "scoreRead.ts")), "scoreRead.ts is a second copy of the rule"
    sess = _src("discovery", "session.ts")
    assert re.search(r"useSourcedFor\(wantKey,.*?getScoreboard\(", sess, re.S), "the scoreboard is not a keyed read"
    acts = _src("discovery", "RunsPage.tsx")
    acts = acts[acts.index("function RunActs"):]
    assert "useSourcedFor(" in acts and "getRunUnjudged(" in acts
    assert "run_key === run.key" not in acts, "RunActs still filters the count by hand"


KEYED_TS = os.path.join(SRC, "api", "keyedRead.ts")


def _held(cases):
    """Run keyedRead.heldFor(held, key) under Node for each (held, key)."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(KEYED_TS), "webui/client/src/api/keyedRead.ts does not exist"
    url = "file:///" + KEYED_TS.replace("\\", "/").lstrip("/")
    lines = [f"import * as K from {json.dumps(url)};",
             f"const cases = {json.dumps(cases)};",
             "process.stdout.write(JSON.stringify(cases.map(([h, k]) => K.heldFor("
             "{ ...h, error: h.error ? new Error(h.error) : null }, k))));"]
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", "\n".join(lines)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _h(key, value, loading=False, error=None):
    return {"data": None if key is None else {"key": key, "value": value}, "loading": loading, "error": error}


def test_the_keyed_read_answers_only_its_own_key():
    """tq-scope (2026-10-25, critic): the rule useSourcedFor applies to the read it holds, run under Node. The
    read state is {data: {key, value} | null, loading, error}; the answer is {data, loading} for the wanted key."""
    out = _held([
        [_h(None, None, loading=True), "A"],          # mounted, nothing in yet
        [_h("A", "answerA"), "A"],                    # answered
        [_h("A", "answerA"), "B"],                    # key changed: first render, before B's effect has run
        [_h("A", "answerA", loading=True), "B"],      # B's read is out
        [_h("A", "answerA", loading=True), "A"],      # back to the held key while a read is out
        [_h("B", "answerB-late"), "A"],               # an answer for another key is never this key's
        [_h("A", []), "A"],                           # an empty answer for THIS key is an answer
        [_h("A", "answerA", error="boom"), "C"],      # C's read failed: not loading, nothing shown
    ])
    assert out == [
        {"data": None, "loading": True},
        {"data": "answerA", "loading": False},
        {"data": None, "loading": True},
        {"data": None, "loading": True},
        {"data": "answerA", "loading": True},
        {"data": None, "loading": True},
        {"data": [], "loading": False},
        {"data": None, "loading": False},
    ]


def test_settling_a_scope_write_never_touches_absent_link_keys():
    """tq-scope (2026-10-25, critic): every setQuery replaces the hash and fires 'hashchange', and the toast host
    drops toasts older than 1 s on each one, so clearing absent keys after every recording or channel edit wiped
    "opened the X session as it was left". The old clearLink touched a key only when it was there; so do these."""
    hook = _src("discovery", "useScopeLink.ts")
    clear = re.search(r"const clear = \(\) => \{([^}]*)\}", hook)
    assert clear, "no clear()"
    body = clear.group(1)
    assert "if (channelsQ) setChannelsQ(null)" in body, "clear() sets ?channels= even when absent"
    assert "if (recordingQ) setRecordingQ(null)" in body, "clear() sets ?recording= even when absent"
    assert hook.count("setChannelsQ(null)") == 1 and hook.count("setRecordingQ(null)") == 1, \
        "a link key is set outside clear()'s guard"
    settle = re.search(r"const settle = [^\n]*", hook).group(0)
    assert "channelsQ || recordingQ || error" in settle, "settle() runs with no link keys and no held error"


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
    the missing 14* overlapped the text and each other. night-disc (2026-10-20, the researcher's drawing) replaced the
    five lines with three columns: the small actions are a line of their own in the MIDDLE column, under the name and
    its facts; Report is an icon in the right column under the x and the A/B box (tests/test_night_disc.py)."""
    src = _src("discovery", "chrome.tsx")
    start = src.index("function RunRow")
    body = src[start:src.index("/* ------------------------------------------------------------------ coverage strip")]
    # tq-scope (2026-10-25): the actions are built once (`const actions = [...]`) and drawn as one line
    line = body[body.index('className="dsc-run-actions"'):body.index('className="dsc-run-right"')]
    assert "{actions}" in line
    acts = body[body.index("const actions = ["):body.index("].filter(Boolean)")]
    for tid in ("run-missing-", "retry-", "chain-import-", "open-in-jobs-"):
        assert tid in acts, f"{tid} is not on the actions line"
    # the x, the pick box and the Report icon come AFTER the actions, in the right column
    right = body[body.index('className="dsc-run-right"'):]
    for tid in ("remove-", "pick-", "report-"):
        assert tid in right, f"{tid} is not in the right column"
    assert "title={run.label}" in body


def test_a_run_name_wraps_to_two_lines_then_ellipsis():
    css = _src("discovery", "discovery.css")
    assert re.search(r"\.dsc-run-text\s*>\s*b\s*\{[^}]*-webkit-line-clamp:\s*2", css)
    assert re.search(r"\.dsc-run\s*\{[^}]*display:\s*grid", css)
    # night-disc: the actions are a wrapping line inside the middle column
    assert re.search(r"\.dsc-run-actions\s*\{[^}]*flex-wrap:\s*wrap", css)


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


# ── fix round (the critic, 2026-10-20) ──────────────────────────────────────

def test_f2_a_failed_link_write_is_said_in_words_and_does_not_hang_the_page():
    """A rejected link write only logged and toasted: the link target stayed set, so the page stayed on its loading
    layout under "moving the session to the linked scope..." for ever (reproduced with the PUT forced to 500). The
    failure is held, said through the scope-link-refused callout (whose button keeps the session's scope and clears
    the keys), and the page is no longer 'writing' while it is held.

    tq-scope (2026-10-25): one phase in discovery/useScopeLink.ts; a held error is 'refused', never 'writing'."""
    hook = _src("discovery", "useScopeLink.ts")
    assert "setError(" in hook and "the bridge did not take the link's scope" in hook
    m = re.search(r"const phase: LinkPhase = (.*?kind: 'idle' \})", hook, re.S)
    assert m, "the hook has no single phase"
    phase = m.group(1)
    assert phase.index("error ?") < phase.index("'writing'"), "a held write error must end the writing state"
    assert re.search(r"error \? \{ kind: 'refused'", phase), "the write error is shown through the refusal callout"
    assert re.search(r"const clear = \(\) => \{[^}]*setError\(null\)", hook)
    sess = _src("discovery", "session.ts")
    assert "phase.kind === 'refused'" in sess and "phase.kind === 'writing'" in sess


def test_the_session_has_no_hand_kept_link_or_switch_state():
    """tq-scope (2026-10-25): the link's state was spread over awaitRunsOf, two refs, three link values, a key and
    an effect in useDiscovery. A change of session is now a new key on the runs read (useSourcedFor), so the old
    session's runs are never on screen, and the link is one hook."""
    sess = _src("discovery", "session.ts")
    for gone in ("awaitRunsOf", "runsNow", "recNow", "useRef", "linkWriting", "linkTarget", "setLinkError", "resolveScopeLink("):
        assert gone not in sess, f"{gone} is still in session.ts"
    assert re.search(r"const base = useSourcedFor\(", sess), "the runs read is not keyed by the session"


def test_f3_the_review_flow_waits_for_the_count_before_reading_the_label():
    src = io.open(os.path.join(PROJECT_ROOT, "webui", "smoke.py"), encoding="utf-8").read()
    start = src.index('print("[discovery → review]")')
    body = src[start:start + 1500]
    wait = body.find('data-counting="1"')
    read = body.find("label = btn.first.inner_text()")
    assert 0 <= wait < read, "the flow reads the Send label before the count has landed"


def test_f4_the_smoke_states_measure_the_row_and_the_scroll():
    rows = json.load(io.open(os.path.join(PROJECT_ROOT, "webui", "smoke_pages", "zzzzzzzzzzz_a1_site_runs.json"),
                             encoding="utf-8"))
    by = {r["state"]: r for r in rows}
    row = by["site-runs-run-row-geometry-at-1024"]
    sels = [s for pair in row["no_overlap"] for s in pair]
    for part in (".dsc-run-text > b", ".dsc-run-meta", ".dsc-run-line", ".dsc-cov", "pick-{run:a}", "remove-{run:a}",
                 "report-{run:a}"):
        assert any(part in s for s in sels), f"{part} is not measured"
    assert any("eval" in a and "1024px" in a["eval"] for a in row["actions"])
    assert any("data-geometry=\"ok\"" in x for x in row["expect"])
    sc = by["site-runs-scoreboard-scrolls-under-a-sticky-header"]
    assert any("eval" in a for a in sc["actions"])
    assert any("data-check=\"ok\"" in x for x in sc["expect"])
