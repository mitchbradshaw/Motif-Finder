# P1 — The held-out lock honours Settings › Datasets

Read [`00-common.md`](00-common.md) first. Commit prefix **`a2-p1:`**. **Urgent:** the researcher is using M4_aug for
demos from 2026-10-17.

## In plain words

The website keeps one recording, M4_aug, locked away as an untouched exam. Settings › Datasets has a switch to unlock
it. The researcher used it on 2026-10-17 at 15:02: typed the name, and the app wrote "Held-out lock turned off ·
M4_aug_concat_fs1 selectable in every workspace" to the audit log. Yet M4_aug stayed refused everywhere. The switch
is real; nothing obeys it.

Make every refusal of the held-out recording obey that one switch: off opens M4_aug everywhere, on closes it again, no
restart needed.

## What is true today (read 2026-10-17)

### The switch

- It is `settings(page='datasets', key='heldout.on')`, default **true**.
- It is written by `Working/registration/settings.py::put_settings`, which needs the name typed exactly
  (`confirm_name`) and writes an audit row of kind `lock`. `held_out_state(conn)` reads it.
- **In the real database it has been `false` since 2026-10-17T05:02:50Z** (audit id 519). So once this lands and the
  bridge restarts, M4_aug is open at once.
- The module's own docstring: *"The routes' refusal of the held-out FILE (423) is separate and does not read this
  setting."* The only reader is `webui/server/registration.py:206-209`, which keeps metadata read-only while the lock
  is on.

### Every refusal ignores it

They compare the file name, or read a code constant. About 130 references in 20 files; grep
`HELD_OUT_FILE|HELD_OUT_RECORDING_FILE|HELD_OUT_UNLOCK|held_out`.

- **Core:** `Working/config.py:462` `HELD_OUT_UNLOCK = False` is a constant. It is read by:
  - `Working/execution.py:349`, whose message says to edit `config.py`;
  - `Working/discovery/fanout.py:158`, which imports the constant at module load;
  - `Working/discovery/seeded_search.py:550`, which also imports it at module load.
- **Bridge:** `webui/server/runtime.py:52` defines `HELD_OUT_FILE`.
  - `corpus.py` 155, 174 and 322 compute the `held_out` flag every page reads.
  - `app.py`: 98 (`rec_or_423`), 154 (corpus coverage) and 372 (run history).
  - `discovery.py`: `_refuse_held_out` (100) and its callers, plus 204, 1231, 1254 and 1343.
  - `discovery_map.py`: `exclude_files=[HELD_OUT_FILE]` three times, and `_refuse_held_out` twice.
  - `explore_routes.py`: 42, 49 and 170.
  - `library.py`: `_is_held_out_path` (83), `_refuse_held_out` (237) and the index flags.
  - `review.py`: `_is_held_out` (85), `_held_out_ids` (514) and `_refuse_held_out` (525).
  - `jobs_routes.py` 392 and 428, `shape_routes.py`, `blind_routes.py` and `analyse_routes.py`.
- **Client:** the top bar's "M4 held out" chip, and the `heldOut` flags each page reads from the server.

## The change

1. **One predicate, in the core.** Add `Working/registration/settings.py::held_out_locked(conn) -> bool`. It is true
   unless `Working.config.HELD_OUT_UNLOCK` is true (kept as a code-level override for scripts) or `heldout.on` is false.
   - Read it at request or run time. Never cache it at import or at bridge start, and never bind the constant at module
     load, because a toggle must take effect without a restart.
   - One indexed settings read. Do not call `held_out_state` for it (that joins `datasets` for a display name).
2. **Every refusal and exclusion listed above consults it.**
   - A refusal (423, `HeldOutRecordingLocked`, `PermissionError`) happens only while locked.
   - A list exclusion (`exclude_files`, `_held_out_ids`, the index flags) applies only while locked.
   - Each module already has one helper (`_refuse_held_out`, `_is_held_out`): change the helper to take the
     connection, rather than editing call sites one by one.
3. **Messages:** while locked, every refusal says how to unlock: "turn the lock off in Settings › Datasets (type the
   recording's name)". Replace `execution.py`'s instruction to edit `config.py`.
4. **Keep, deliberately:**
   - **RQ1's exam (iii) slot** stays locked whatever the switch says. It is the researcher's act on the freeze day,
     by its own rule (`Working/training/windows.py:36`, `training_routes.py`, `cnn_routes.py`). Do not touch
     training.
   - **The Library importers** (`Working/library/importers/*`) and **registration's checks**
     (`Working/registration/kinds.py`) keep their rules. List any you think should follow the switch in your report.
5. **The top-bar chip** reads the server's state. Show "M4 unlocked" in amber, as a reminder, while the lock is off.

## Tests (test-first)

- **Core**, on a fresh `init_db()` database holding a recording named `M4_aug_concat_fs1.mat`:
  - locked by default: `execute_recipe` raises `HeldOutRecordingLocked`, `fanout.plan` refuses the recording, and
    `seed_from_content` refuses it;
  - after `put_settings(conn, 'datasets', {'heldout.on': False}, confirm_name=…)`, all three allow it;
  - switched back on, all three refuse again;
  - no restart or re-import in between.
- **Bridge** (`webui/.venv`):
  - while locked, every route that returns 423 today still does, and the existing held-out tests pass unchanged;
  - with the lock off: Explore lists M4, `GET /api/channels/{id}/spans` returns 200, Discovery lists the recording and
    can plan a run on it, the Map's dataset map includes it, and Library and Review list its rows;
  - switched back on, the same routes refuse again.

## Acceptance

- [ ] **Off opens everywhere.** Turning the lock off on Settings › Datasets makes M4_aug usable in Explore, Analyse,
      Discovery (apply, seed search, Map), Review and Library **without a bridge restart**. Turning it on refuses it
      again everywhere.
- [ ] **The default is unchanged.** With the setting never written, behaviour is exactly today's.
- [ ] **Exam (iii) is untouched.**
- [ ] **No cache.** No module caches the lock state or binds it at import.
- [ ] **Smoke states** in `webui/smoke_pages/a2_p1_held_out.json`: Settings › Datasets with the lock off shows the
      amber chip, and Explore lists M4.

**Report:** every site changed (file:line), every site deliberately left and why, and the clicks that re-lock M4.
