# Fog — Settings (frontend design)

Frontend-design fog only: places where the frames, the spec (§9, §12 P23) and the inventory did not
settle a question the shell had to answer, plus what this build decided. Analysis/data fog is already
recorded as F1–F26 in `webui/pages/inventory/settings.md`; these are additional and numbered from FE1.

- **FE1. Draft vs immediate on the held-out lock.** §9 says project settings write on save; D6 says
  unlocking is logged. Built as the inventory recommends: the typed-name modal *is* the commit
  (immediate, writes an audit entry), turning the lock **on** goes through the save bar. A Discard can
  therefore never silently undo a logged act. Unconfirmed with the researcher.
- **FE2. Where the draft lives.** One in-memory store (`settings.store`) holds `saved`/`draft` for all
  sixteen pages, so drafts survive navigation between settings pages and the nav-rail dots can be
  computed per page (B29). Consequence: leaving Settings entirely and coming back still shows the
  draft. The frames do not say whether a draft should survive leaving the workspace.
- **FE3. The leave guard only guards the settings nav.** Clicking another settings page with unsaved
  edits opens the guard modal. The workspace nav rail and the browser back button do **not** — the kit's
  `NavRail` is shared chrome this unit does not own, and `beforeunload` cannot be made to look like the
  frame's modal. Requested in `webui/pages/requests/settings.md`.
- **FE4. The header search pill.** The frames draw `Search settings  Ctrl K` in the shared header, but
  `shell/Header.tsx` hard-wires that pill to a not-wired toast. The shell intercepts the click in a
  capture-phase listener (and binds Ctrl K) to open the settings search modal instead. That is a
  workaround for a shared file this unit does not own; the clean fix is a `Header` `onSearch` prop.
- **FE5. Search ranking and `?focus=`.** The index is one field per card (18 entries, fixture). A hit
  navigates to `#/settings/<slug>?focus=<slugified field>` and pulses the element with that id. Only the
  fields named in the index carry an id, so a hit for an un-idded field would navigate but not pulse.
  No spec for ranking (inventory F2).
- **FE6. Save is instant, not `saving` → `saved`.** The inventory describes a ~600 ms spinner. The store
  writes synchronously and raises the "Saved · <consequence>" toast; a fake delay would be theatre in a
  page that writes nothing. The disabled-while-saving state therefore does not exist.
- **FE7. The consequence sentence for a multi-field draft.** P23 wants one consequence. With several
  fields edited the bar shows the consequence of the **last field touched** (or the seeded sentence
  under `?state=unsaved`), not a joined list. The frames only ever draw one sentence, so the rule is
  invented.
- **FE8. `?state=unsaved` seeds, and its sentence can disagree with its own values.** The fixture seeds
  Datasets' noise floor to `0.12` while the frame's sentence reads `0.08 → 0.10 mV`. The seed is
  fixture-owned, so the page shows both as given rather than rewriting either. A reviewer reading the
  Datasets save bar will see a sentence that does not match the field.
- **FE9. Shared values across two pages.** `seq_gap` / `seq_events` are edited on Review queues **and**
  Library groupings. Writing one writes the other's draft too (`SHARED` in `settings/store.ts`), so both
  pages show a save bar. Each page then saves its own copy — saving one does not clear the other's bar.
  The spec says only "shared with Library sequences".
- **FE10. The event timeline domain.** Drawn 0 → the recording's real duration (721 h for M2_aug fs1),
  not the frame's 0–45 h (inventory conflict). Point events are a solid tick, excluded spans are the
  kind colour at 27 % alpha, so the `40.1 h → end` exclusion does not paint over everything. At 721 h the
  four canon events cluster in the first 6 % of the strip — legible, but not what the frame shows.
- **FE11. Gain and other numbers render unformatted.** `NumberField` shows `1`, the frame shows `1.00`.
  A display-only formatter would fight the field's own parsing; left as-is.
- **FE12. Reset on a personal page.** Applies immediately (no save bar exists there) and raises the
  "Reset N values" toast. On a project page it stages the defaults as unsaved edits. The frames draw the
  link, never the outcome.
- **FE13. Class `implies` when informative is turned off.** Turning informative off sets `implies` to
  `artifact` (the spec's example) rather than leaving it empty, so the Select always has a value.
  Invented default.
- **FE14. The key-conflict resolution.** Frame 16 shows only the `no conflicts` chip. The conflict state
  is built as: capture → if the key is owned, show a red row with *Keep the old binding* / *Move ⟨key⟩
  here*, and moving it sets the loser's key to `—`. A binding left at `—` is unreachable and nothing
  offers to restore it.
- **FE15. Audit entries written this session.** Saves and the unlock write `recordDemoWrite('settings',
  'audit', …)`; the Audit log page prepends them to the fixture entries with a locally formatted
  timestamp. They are in-memory, so the log is append-only *within a session* and resets on reload —
  the opposite of "kept for the life of the project".
- **FE16. Import footer size.** Computed as `channels × samples × 8 B` (→ 138 MB), not the frame's
  8.2 GB (inventory F3). The imported row is in-memory and vanishes on reload (F4).
- **FE17. Profile cells are read-only.** §9.6 and the inventory describe inline editing of partition,
  nodes, gres, cpus, memory, time and array per profile; this build renders them as text and makes only
  the editor below (environment, working directory, return paths, email) editable. Selecting a profile
  re-binds the editor and the script preview, so nothing is a dead click, but the per-cell edits are a
  gap.
- **FE18. Not simulated, toast-only.** `open folder`, `pull`, `import` (manifest inbox), `export all`,
  `Export CSV`, `Export preferences`, `Copy diagnostics`' file, tag `merge`, tag/class `rename` and
  `Add a rule for a block parameter` raise a not-wired toast naming the call. Each would need a core
  write that does not exist.
- **FE19. Theme and density do nothing visible.** Display writes `theme` and `density` to the personal
  store and raises "Applied to this browser", but the site has one light theme and one density. The
  controls are honest about what they store and dishonest about what they change; the caption says so.
- **FE20. Personal settings are not persisted.** The inventory says personal pages persist to
  `localStorage`. This build keeps them in the same in-memory store as project settings, so a reload
  resets them — consistent with every other page in the empty frontend ("writes survive navigation but
  not a reload"), and inconsistent with the inventory.
