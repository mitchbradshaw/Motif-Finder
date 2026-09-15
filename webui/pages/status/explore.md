# Status — explore unit

| page | status | what's left | last commit |
|---|---|---|---|
| explore.corpus | done | URL write-back of rec/ch/colour (deep links are read-only today) | corpus: recordings menu, legend, demo rail |
| explore.signal | done | `?motif=233` is an ordinal in the merged live+demo list, so it does not land on the frame's fixture motif; drawer scope defaults to whole channel (frame: visible span, fog) | signal: picker, legend, drawer, keyboard |
| explore.cross-channel | done | row reorder is pointer + Alt+↑/↓ (no drop animation); lag/r/bins are a seeded table, not computed (fog) | cross-channel: stack, lag-align, classification, hand-offs |
| explore.span-edit | done | grip drag snaps on release only; no entry into span edit from Explore itself (D2) | span-edit: banner, extent editor, snap, revisions |

Smoke: `smoke.py --url http://127.0.0.1:5173 --pages-only --only explore` → 51 page states, 0 failures. smoke.py's live
corpus / signal / held-out flows re-run against the dev server: all checks pass.
Screenshots of every state: `webui/screenshots/build/explore/` (build looks) and `webui/screenshots/pages/explore/` (smoke).
