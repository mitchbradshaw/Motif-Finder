# tq-scope — Discovery's session/scope writes and the deep-link state as one model

Package id for commits: `tq-scope`. Read `docs/prompts/quality/00-common.md` first.

This area was fixed twice in the night wave: a recording switch overwrote the opened session's scope (night-disc
item 3), and the scoreboard showed "Send 0 unjudged" beside a run with detections on screen (site-runs item 4).
Both fixes must survive. Be conservative.

## The findings

1. **Three copies of the session write, with special-case branches at each call site.** Files:
   `webui/client/src/api/discovery.ts:~134-161`, `discovery/session.ts:~167-168`, `discovery/chrome.tsx:~252-255`.
   - `putScope`, `putScopeLink` and `putRecording` are all
     `putDiscoverySession(body).then(p => { RECORDINGS = …; SCOPE = …; return p })`. They differ only in which
     optional fields they send, and `putDiscoverySession` already takes them all as optional.
   - The split grew a `bare` branch in `setScope`:
     `const bare = patch.recording !== undefined && patch.recording !== scope.recording && patch.channels === undefined && patch.section === undefined`.
   - `ScopeCard.changeRecording` grew three `r.heldOut ?` branches.
   - **Remedy:** one `writeSession(body: Partial<{recording; channels; section}>)` that updates the module cache.
     `setScope(patch)` sends exactly the fields in `patch`, so a recording-only patch sends the recording alone. The
     `bare` branch, `putRecording` and `putScopeLink` are deleted. `putScopeLink`'s `section: null` becomes "omit
     section"; check the bridge treats an absent field as "leave it". The held-out view-only path stays a single
     early return in `setScope`.
2. **The deep-link "move the session" state is scattered.** File: `discovery/session.ts:~95-147, ~249-253`.
   - It is spread across:
     - `awaitRunsOf` (`useState<unknown>` compared by object identity);
     - `runsNow` and `recNow` refs that dodge stale closures;
     - `linkError`, `linkRefused`, `linkTarget`;
     - `linkKey` plus an effect with an exhaustive-deps disable;
     - `switching`, `linkWriting` and an extended `firstLoad`;
     - a three-way scope ternary.
   - `linkWriting` re-tests `'same' in link` though `linkTarget` non-null already implies it.
   - **Remedy:** a `useScopeLink(...)` hook (in `scopeLink.ts` or a sibling) with one reducer:
     `{kind:'idle'} | {kind:'writing', target} | {kind:'refused', why} | {kind:'switching', fromRuns}`. It returns
     `{ phase, viewScope(scope0), clear }`. `useDiscovery` keeps only `firstLoad ||= phase.kind === 'writing' || phase.kind === 'switching'`.
     `took()` passes the current runs as an argument, so the refs go.
3. **"Is this answer for the current request?" is written twice** as a workaround for `useAbortableSourced`
   (`api/seam.ts:~42-55`) keeping the previous request's data while a new read is out:
   - `discovery/scoreRead.ts` tags each answer with a key (`scoreKey`, `scoresFor`) and filters it;
   - `RunsPage.tsx:~514` does it by hand: `count.data && count.data.run_key === run.key ? count.data : null`.

   **Remedy:** fix it once in the seam, opt-in. Either a `useSourcedFor(key, fn)` that answers `data: null` while the
   held answer belongs to another key, or `useAbortableSourced` storing the deps signature with the data and
   exposing `current`. Then delete `scoreRead.ts`, the `{ key, rows }` wrapping in `session.ts:~241-247` and the
   `run_key` check. Leave every other `useSourced` caller's behaviour untouched.
4. **`RunRow`'s `hasActions`** (`discovery/chrome.tsx:~575`) repeats, by hand, the four render conditions below it.
   Add an action and forget `hasActions`, and the button silently disappears. **Remedy:** build the actions list
   once, then `actions.length > 0 && <div className="dsc-run-actions">{actions}</div>`.

## Behaviour that must not change

- **A change of recording sends the recording alone** and never overwrites the opened session's scope (night-disc
  item 3), including after a bare `?recording=` link (9189220).
- **A held-out recording is view-only:** nothing is written, with the same toast.
- **A deep link** that moves the session writes once, shows "refused" with the reason when the bridge refuses, and
  never flashes the old scope.
- **The scoreboard** never shows another run set's answer: "not in yet" until its own read answers (site-runs item 4).
- **The run row** shows exactly the same actions in the same situations.

## Files

`webui/client/src/api/discovery.ts`, `discovery/session.ts`, `discovery/scopeLink.ts`, `discovery/chrome.tsx` (the
ScopeCard recording change and `RunRow` only), `discovery/RunsPage.tsx` (`RunActs` and the scoreboard read only),
`discovery/scoreRead.ts` (delete), `api/seam.ts` (an opt-in addition only).

Tests: `tests/test_site_runs_scope_link.py`, `tests/test_night_disc.py`, `tests/test_webui_site_runs.py`,
`tests/test_night_a_review.py`, `tests/test_webui_night_disc.py` if present, and
`grep -rln "session.ts\|scopeLink\|putScope\|putRecording\|scoreRead\|scoresFor\|seam.ts\|hasActions" tests/`.
Record the failure set first.

Smoke units for the manager: `zzzzzzzzzzz_a1_night_disc`, `zzzzzzzzzzz_w2_site_runs_link`, `zzzzzzzzzzz_a1_site_runs`,
`zzzzzzzzzzz_a1_polish_discovery`. The `discovery` unit needs the full walk.
