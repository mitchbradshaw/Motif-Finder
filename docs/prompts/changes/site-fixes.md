# site-fixes — small, decided, do directly (one commit each, prefix `ux-1019:`)

Not a prompt for an agent unless the manager is busy: each item is under an hour, decided with the researcher on
2026-10-18, and gated by `tsc -b`, `vite build` and the affected smoke unit. Do them on main after the AR speed pass
is merged (two of them touch the Discovery pages AR reshaped).

1. **A page open across a rebuild must not die.** "⚠ models workspace failed to render — Failed to fetch dynamically
   imported module …/assets/models-XXXX.js" (the researcher, 2026-10-18: "cannot happen on demo day"). Workspaces are
   `lazyNamed(load, name)` in `webui/client/src/App.tsx:13-26` (and two pages in `analyse/index.tsx:18-19`); there
   is no retry; `React.lazy` caches the rejection, so the error card's "Try again" fails the same way
   (`shell/ErrorBoundary.tsx:21-24`). Fix: in `lazyNamed`, catch the import error; if its message matches
   `/dynamically imported module|Failed to fetch|Importing a module script failed/` and `sessionStorage` has no
   `ub:reloaded-for-chunk` flag, set the flag and `location.reload()`; clear the flag once any chunk loads; also
   listen for `vite:preloadError` and do the same. Test by hand: open the app, rebuild, click another workspace.
   Smoke: none possible; say so in the commit.
2. **Discovery: runs are not all shown by default.** Today every detection run is drawn in "Where each run fires"
   and counted everywhere on open; the researcher wants shown-off by default, each run's button turning it on.
   `discovery/session.ts` (`picks`, the `shown` filter in `RunsPage.tsx` `WhereFires`): a per-session "shown" set,
   empty on a new session, toggled from the run row (a small eye button; the colour swatch doubles as the state),
   with "show all / hide all" in the card head; the reference (human) row is always shown. Remember it with the
   other `useDemoState` keys. Smoke: the existing `discovery.runs--default` expects `fires-cell` — seed one shown
   run in that state's actions or update its expectation; say which.
3. **AM default alignment:** drop-detector templates default to `trough` at an anchor of ⅓; everything else keeps
   `centre` at 0.5 (`decided 2026-10-18`, BACKLOG §1; refined 2026-10-19: the choice is AUTOMATIC from the template
   kind, with an explicit "for drops" switch on the card that forces the drop setting either way). Where the default is chosen (the Models › Launch setup and
   the block's parameter defaults — `grep -rn "anchor" Working/ Adapters/ webui/server`), make the default depend
   on the template kind, show the chosen default on Launch's setup line (which also still omits the anchor —
   BACKLOG §5), and add a test that a drop template's launch body carries `trough, 0.333`.
4. **AO baseline window on the card:** the 600 s default stays; expose `window_s` on the decompose block's card
   with its default, as the other block parameters are shown (BACKLOG §1).
5. **Cubic detrend control (AQ):** Cross-channel's y control has a disabled "detrended (display only)" option
   (`explore/CrossChannelPage.tsx:216`) while the bridge serves `detrend=cubic`; make the Seg raw · linear · cubic
   and pass it to the read; the note at `:273` already words the linear case — extend it. Smoke: the AQ unit's
   states keep passing.
6. **Record the six closed decisions** in `docs/prompts/fixup/BACKLOG.md` §1 (all six resolved 2026-10-18 as the
   recommendations stood) and remove the rows.
