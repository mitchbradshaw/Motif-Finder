# Models — shared-code requests

- **smoke.py (`webui/smoke.py`) · allow one declared console error per page state.** A read that *rejects*
  (the honest shape for a bridge 500) makes the shared `api/seam.ts` `useSourced` log
  `console.error('read failed', …)`. The page renders a loud red error card, which is what the brief asks
  for, but `routes()` fails any state whose console produced an error, so a "failed read" state cannot be
  listed in `smoke_pages/*.json`. Request: an entry key like `"allow_console_error": ["read failed"]`
  (or reuse `allow_error_card`) so the deliberate failure state can be smoked.
  *Workaround:* `models/results/j-0209` is reachable and screenshotted
  (`webui/screenshots/build/models/results-failed.png`) but left out of the manifest.
