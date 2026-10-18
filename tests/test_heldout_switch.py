"""
test_heldout_switch.py
======================
a2-p1 — the held-out lock honours Settings › Datasets.

The switch is ``settings(page='datasets', key='heldout.on')``, written by
`Working.registration.settings.put_settings` (the name typed exactly, an audit
row of kind ``lock``). Until a2-p1 nothing in the core read it: the runner,
the Discovery fan-out's pre-flight and the seed card all compared the file
name against the code constant ``Working.config.HELD_OUT_UNLOCK``, so turning
the lock off in the app changed nothing.

These tests pin, on a fresh ``init_db()`` database holding a recording named
``M4_aug_concat_fs1.mat`` (real samples on disk, so "allowed" means the work
really happens, not that it fails one step later for another reason):

* the one predicate, ``held_out_locked(conn)``: on by default, off when the
  setting is off or the code-level override is set, read from the settings
  table itself (not through ``held_out_state``, which joins ``datasets``);
* ``execute_recipe``, ``fanout.plan`` and ``seed_from_content`` refuse the
  recording while locked, allow it once the lock is off, and refuse it again
  once it is back on — in one process, with no restart and no re-import;
* every refusal says how to unlock, and the runner no longer tells anyone to
  edit ``Working/config.py``;
* no core module binds the unlock constant at import;
* exam (iii) keeps its own lock whatever the switch says.

Run from the project root:
    python -m pytest tests/test_heldout_switch.py -q
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import Working.config as config  # noqa: E402
from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import fanout  # noqa: E402
from Working.discovery import seeded_search as ss  # noqa: E402
from Working.execution import HeldOutRecordingLocked, execute_recipe  # noqa: E402
from Working.recipes import make_recipe  # noqa: E402
from Working.registration import settings as S  # noqa: E402

LOWPASS = [{"stage": "preprocessing", "algorithm": "lowpass", "params": {"cutoff_hz": 0.05}}]
N = 600
UNLOCK_WORDS = "Settings › Datasets"


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh database: one ordinary recording and the held-out one, each a
    real single-channel array on disk. The step cache is redirected into the
    test's own directory so nothing is written under the worktree's DATA/."""
    monkeypatch.setattr(config, "STEP_CACHE_ROOT", str(tmp_path / "step_cache"))
    db_path = str(tmp_path / "heldout_switch.sqlite")
    conn = init_db(db_path)
    try:
        for k, name in enumerate(("other.mat", HELD_OUT_RECORDING_FILE)):
            npy = tmp_path / f"rec{k}.npy"
            np.save(npy, np.random.default_rng(k).standard_normal(N))
            q.insert_recording(conn, name, 0, 1.0, N, 0, str(npy))
        conn.commit()
    finally:
        conn.close()
    return db_path


def _held_id(db_path):
    conn = init_db(db_path)
    try:
        return int(q.list_recordings(conn, HELD_OUT_RECORDING_FILE)[0]["id"])
    finally:
        conn.close()


def _other_id(db_path):
    conn = init_db(db_path)
    try:
        return int(q.list_recordings(conn, "other.mat")[0]["id"])
    finally:
        conn.close()


def _set_lock(db_path, on):
    """Turn the lock on or off the way the app does: through `put_settings`,
    with the name typed exactly to turn it off."""
    conn = init_db(db_path)
    try:
        if on:
            S.put_settings(conn, "datasets", {"heldout.on": True})
        else:
            name = S.held_out_state(conn)["name"]
            S.put_settings(conn, "datasets", {"heldout.on": False}, confirm_name=name)
    finally:
        conn.close()


def _locked(db_path):
    conn = init_db(db_path)
    try:
        return S.held_out_locked(conn)
    finally:
        conn.close()


# ── the one predicate ───────────────────────────────────────────────────────


def test_the_lock_is_on_by_default_and_follows_the_switch(db):
    assert _locked(db) is True, "a database that never wrote the setting keeps the recording locked"
    _set_lock(db, False)
    assert _locked(db) is False
    _set_lock(db, True)
    assert _locked(db) is True


def test_the_code_level_override_still_unlocks_for_scripts(db, monkeypatch):
    """`HELD_OUT_UNLOCK` stays as a script's override, read when the predicate
    runs (a monkeypatch after import must take effect)."""
    monkeypatch.setattr(config, "HELD_OUT_UNLOCK", True)
    assert _locked(db) is False
    monkeypatch.setattr(config, "HELD_OUT_UNLOCK", False)
    assert _locked(db) is True


def test_the_predicate_reads_the_settings_row_not_held_out_state(db, monkeypatch):
    """One indexed settings read: `held_out_state` joins `datasets` for a
    display name the predicate has no use for."""
    def _no(*_a, **_k):
        raise AssertionError("held_out_locked must not go through held_out_state")
    monkeypatch.setattr(S, "held_out_state", _no)
    monkeypatch.setattr(S, "_dataset_display_name", _no)
    conn = init_db(db)
    try:
        assert S.held_out_locked(conn) is True
        conn.execute("INSERT INTO settings (page, key, value_json, updated_at, actor) "
                     "VALUES ('datasets', 'heldout.on', 'false', '2026-10-17T05:02:50+00:00', 'test')")
        conn.commit()
        assert S.held_out_locked(conn) is False, "the stored value is read on every call, never cached"
    finally:
        conn.close()


def test_the_unlock_sentence_names_the_page_and_the_typed_name():
    hint = S.HELD_OUT_UNLOCK_HINT
    assert UNLOCK_WORDS in hint and "type" in hint and "name" in hint


# ── the runner ──────────────────────────────────────────────────────────────


def test_execute_recipe_follows_the_switch_without_a_restart(db):
    rid = _held_id(db)
    recipe = make_recipe(rid, span=(0, 200), steps=LOWPASS)

    with pytest.raises(HeldOutRecordingLocked):
        execute_recipe(recipe, db_path=db)

    _set_lock(db, False)
    out = execute_recipe(recipe, db_path=db)
    assert out["run_id"], "unlocked, the held-out recording runs like any other"

    _set_lock(db, True)
    with pytest.raises(HeldOutRecordingLocked):
        execute_recipe(make_recipe(rid, span=(0, 300), steps=LOWPASS), db_path=db)


def test_the_runner_still_leaves_other_recordings_alone(db):
    out = execute_recipe(make_recipe(_other_id(db), span=(0, 200), steps=LOWPASS), db_path=db)
    assert out["run_id"]


# ── the Discovery fan-out's pre-flight ──────────────────────────────────────


def test_fanout_plan_follows_the_switch(db):
    held, other = _held_id(db), _other_id(db)
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=[other, held], span=(0, 200))
        assert [t["recording_id"] for t in plan["targets"]] == [other]
        assert [r["recording_id"] for r in plan["refused"]] == [held]
    finally:
        conn.close()

    _set_lock(db, False)
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=[held], span=(0, 200))
        assert [t["recording_id"] for t in plan["targets"]] == [held]
        assert plan["refused"] == [] and plan["runnable"] is True
    finally:
        conn.close()

    _set_lock(db, True)
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=[held], span=(0, 200))
        assert plan["targets"] == [] and plan["runnable"] is False
        assert HELD_OUT_RECORDING_FILE in plan["reason"]
    finally:
        conn.close()


# ── the seed card ───────────────────────────────────────────────────────────


def test_a_seed_on_the_held_out_recording_follows_the_switch(db):
    conn = init_db(db)
    try:
        with pytest.raises(PermissionError):
            ss.seed_from_content(conn, HELD_OUT_RECORDING_FILE, 0, 100, 160)
    finally:
        conn.close()

    _set_lock(db, False)
    conn = init_db(db)
    try:
        seed = ss.seed_from_content(conn, HELD_OUT_RECORDING_FILE, 0, 100, 160)
        assert seed["recording_id"] == _held_id(db) and seed["samples"] == 60 and seed["hash"]
    finally:
        conn.close()

    _set_lock(db, True)
    conn = init_db(db)
    try:
        with pytest.raises(PermissionError):
            ss.seed_from_content(conn, HELD_OUT_RECORDING_FILE, 0, 100, 160)
    finally:
        conn.close()


# ── every refusal says how to unlock ────────────────────────────────────────


def test_every_core_refusal_says_how_to_unlock(db):
    """While locked, each refusal names the way out: Settings › Datasets, the
    recording's name typed. The runner used to say "Set HELD_OUT_UNLOCK=True in
    Working/config.py", which no researcher should do to a running app."""
    held = _held_id(db)
    with pytest.raises(HeldOutRecordingLocked) as runner:
        execute_recipe(make_recipe(held, span=(0, 200), steps=LOWPASS), db_path=db)
    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=LOWPASS, recording_ids=[held], span=(0, 200))
        with pytest.raises(PermissionError) as seed:
            ss.seed_from_content(conn, HELD_OUT_RECORDING_FILE, 0, 100, 160)
    finally:
        conn.close()
    for where, text in (("execute_recipe", str(runner.value)), ("fanout.plan", plan["refused"][0]["reason"]),
                        ("seed_from_content", str(seed.value))):
        assert HELD_OUT_RECORDING_FILE in text, where
        assert UNLOCK_WORDS in text, f"{where}'s refusal does not say how to unlock: {text!r}"
        assert "config.py" not in text, f"{where} still tells the reader to edit Working/config.py"


# ── no cache, no binding at import ──────────────────────────────────────────


def test_no_core_module_binds_the_unlock_constant_at_import():
    """A module that did `from Working.config import HELD_OUT_UNLOCK` froze the
    lock at import: no setting, and no later override, could ever reach it."""
    for mod in (fanout, ss):
        assert not hasattr(mod, "HELD_OUT_UNLOCK"), f"{mod.__name__} binds HELD_OUT_UNLOCK at import"


# ── exam (iii) keeps its own lock ───────────────────────────────────────────


def test_exam_iii_stays_locked_with_the_switch_off(db):
    """RQ1's exam (iii) slot is the researcher's act on the freeze day, by its
    own rule (`Working/training/windows.py`): the Settings switch is not it."""
    from Working.training.windows import HeldOutRefused, refuse_held_out
    _set_lock(db, False)
    assert _locked(db) is False
    with pytest.raises(HeldOutRefused):
        refuse_held_out(HELD_OUT_RECORDING_FILE)


def test_a_chain_job_marks_a_held_out_target_unlocked_exactly_when_the_lock_says_so(db, monkeypatch):
    """a2 integration (P1 x P2). A cluster chain job exported for the held-out
    recording carries `heldOutUnlocked`, so its scratch database reads unlocked
    there. Whether to mark it is P1's one predicate, not a second reader of the
    setting: the switch, and the HELD_OUT_UNLOCK override a script may set."""
    from Working.discovery import chain_job

    def unlocked(name):
        conn = init_db(db)
        try:
            return chain_job._held_out_unlocked(conn, name)
        finally:
            conn.close()

    assert unlocked(HELD_OUT_RECORDING_FILE) is False, "locked by default"
    _set_lock(db, False)
    assert unlocked(HELD_OUT_RECORDING_FILE) is True
    assert unlocked("other.mat") is False, "only the held-out recording is ever marked"
    _set_lock(db, True)
    assert unlocked(HELD_OUT_RECORDING_FILE) is False
    monkeypatch.setattr(config, "HELD_OUT_UNLOCK", True)
    assert unlocked(HELD_OUT_RECORDING_FILE) is True, "a script's override unlocks it for the export too"
