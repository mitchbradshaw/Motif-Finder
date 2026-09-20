# Requests — Settings (shared changes this unit needed and worked around)

Each item names the shared file, what Settings needs, and the local workaround shipped instead.

## R1 · `shell/Header.tsx` — let a workspace own the search pill

The frames draw `Search settings  Ctrl K` in the header and the inventory specifies a popover over a
per-workspace index. `Header` hard-wires the pill to `useNotWired()`.

**Ask:** an optional `onSearch?: () => void` (and `searchHint?`), used instead of the toast when given.

**DONE (orchestrator, 16:57).** `SettingsShell` now passes `onSearch`; the document-level click
interception is gone. Ctrl K is still bound in `settings/chrome.tsx` (the header binds no keys).

## R2 · `shell/Header.tsx` — the `M4 held out` chip should read the lock

The chip is unconditional and always navigates to `#/settings/datasets`. Settings can turn the lock off
(typed name, logged), after which the chip is wrong.

**Ask:** bind the chip to the shared held-out fixture/store (hidden, or `no recording held out`, when the
lock is off), and deep-link to `?focus=hold-out-a-recording`.

**Key to bind to (answer to the orchestrator's question):** `settings.heldOut` in the demo store —
`useDemoState<{ on: boolean; recording: string }>('settings.heldOut', () => ({ on: true, recording: 'M4_aug' }))`.
Exported as `HELD_OUT_KEY_STORE` / `HeldOutLock` from `settings/store.ts`. It mirrors the **saved** layer
only (never a draft): the Datasets unlock modal writes it the moment the typed name is confirmed, and
turning the lock back on writes it on Save. The default above is the canon state, so a header that
renders before Settings has ever been opened is already correct.

**Workaround until then:** none — the header is not ours. The Datasets page shows the true state in its
own `Held-out recording` card, so the two disagree after an unlock.

## R3 · `shell/NavRail.tsx` — leave guard on workspace navigation

`settings.shell`'s `leave-guard` state should fire when leaving Settings with unsaved edits, not only when
moving between settings pages.

**Ask:** either a `beforeNavigate?: () => boolean` hook on the rail, or a small shared "unsaved work"
registry the rail consults.

**Workaround:** the guard is wired only to the settings nav (fog FE3).

## R4 · `kit` — a settings row primitive

Every settings page repeats "mono label (+ diff dot, + ⓘ) · control · right-aligned consequence caption",
and the locked variants (locked field, locked chip, locked toggle). `Field inline` is close but has no
diff dot, no consequence column and no locked forms.

**Ask:** promote `Row`, `LockedField`, `LockedChip` and `LockedToggle` from `settings/chrome.tsx` into the
kit if another unit wants them (Analyse's block parameters look similar).

**Workaround:** they live in `settings/chrome.tsx` and are exported from there.

## R5 · `kit/forms.tsx` — `NumberField` display formatting

Gain reads `1` where the frame reads `1.00`; a `format?: (n: number) => string` (applied when the field is
not focused) would fix this without fighting the parser.

**Workaround:** unformatted (fog FE11).

## R6 · `fixtures/settings.ts` — the Datasets seed disagrees with its own sentence

`SEEDS.datasets` sets the noise floor to `0.12` while `SEED_SENTENCE.datasets` reads `0.08 → 0.10 mV`
(the frame's). The file is ours to edit but the values are canon-adjacent, so it is flagged rather than
changed: whoever owns §0 should say whether the saved floor is 0.08 or 0.10.

---
**Orchestrator, 16:57.** R1 **done**: `Header` now takes `onSearch?: () => void` (and `searchHint?`); pass it and
drop the document-level click interception. R2 (held-out chip reads the lock) is queued: tell me the demo-store key
your Datasets page writes the lock to (e.g. `settings.heldOut.locked`) in this file and the header will bind to it.
R3/R4 are queued in webui/BUILD_PROGRESS.md.

## R7 · app root — apply the personal display preferences everywhere (fix round 1)

Density and the units/time choices on `settings/display` are personal preferences that the whole app is
supposed to honour: "compact tightens table rows across **every** page", and §0 names hours-since-start /
mV / sample indices as Display settings that every readout follows.

**Ask:** at the app root, read the demo-store key `settings.display`
(`{ density, time_axis, amplitude, sample_indices }`, published by `settings/store.ts`
`publishDisplayPrefs` — the same pattern as `settings.heldOut`) and (a) mirror `density` onto
`document.documentElement.dataset.density` at boot, (b) let each workspace's time and amplitude readouts
bind to it.

**Workaround (landed):** `SettingsShell` writes `html[data-density]` and publishes the prefs whenever any
settings page is mounted, and `settings.css` carries the compact rules for `.k-table` rows, `.s-row` and
`.k-nav-item`, so compact is real across the session once Settings has been opened (it is lost on a reload
until Settings is opened again). Display shows one live example readout in the chosen units instead of
claiming pages it cannot reach.

## R8 · `kit/plots.tsx` — a report-figure profile the `Trace` can actually draw

`Trace` takes `strokeWidth` but has no grid, no `ground="none"`, no font hook and a hard-coded `mV` axis
label, so the Display preview cannot show four of the five profile controls without CSS tricks.

**Ask:** `grid?: number` (opacity), `ground?: 'white' | 'grey' | 'none'`, `fontFamily?: string`, and
`unit?: 'mV' | 'µV'` on the y label.

**Workaround (landed):** `settings.css` `.s-fig` draws the grid as a `::after` overlay inside the plot
frame at `--fig-grid`, sets `.k-plot text { font-family: var(--fig-font) }`, and clears the ground rect
(plus a chequer behind it) for `background: transparent`. The µV label is left as-is rather than faked.

## R9 · `kit/plots.tsx` + `charts/primitives.tsx` — an hours axis that ticks in hours, and point markers

`BandStrip` is the event timeline on Channels & events. Two gaps against frame settings-02:

1. `TimeAxis` ticks through d3's `scaleLinear.ticks(n)` on **seconds**, so an hours window lands on
   5.55 h steps (`0 h 6 h 11 h 17 h …`). The frame ticks `0 / 10 / 20 / 30 / 40 h`. No choice of domain
   fixes it: a nice hour step (3600 × 10 s) is never one of d3's 1/2/5 × 10^k candidates.
2. Every segment is a `rect rx=2`. A point event in the frame is an 8 px circle in its kind colour.

**Ask:** `timeUnit="h"` picks tick steps from an hours ladder (1, 2, 5, 10, 25, 50, 100 h), and a segment
may carry `shape?: 'bar' | 'dot'` so a zero-length event draws as a dot on the axis line.

**Workaround (landed):** the strip defaults to the window that holds every event, so the ticks are at
least dense and the markers are visible kind-coloured bars a few pixels wide; spans are drawn at 40 %
alpha and never thinner than a point marker. The odd tick values and the square markers stay.

## R10 · `kit/forms.tsx` — `NumberField` needs fixed decimals and a placeholder

A calibration number has to read `1.00`, not `1`, and an optional override has to say what it falls back
to (`recording`). `NumberField` renders `String(value)`, has no `placeholder`, and its inline message is
its own (`not a number`) rather than the one rule the inventory writes for the field.

**Ask:** `decimals?: number` (display only), `placeholder?: string`, and `error?: string` to replace the
built-in reasons with the field's own sentence.

**Workaround (landed):** `settings/ChannelsEventsPage.tsx` has a local `NumberCell` over `TextField` that
does all three. It is deliberately private to the page — if a second page needs it, it belongs in the kit.

## R11 · `kit/plots.tsx` — a `BandStrip` segment cannot be clicked

The inventory's `event-selected` state says clicking a timeline marker selects its table row. `BandStrip`
segments take no `onClick`, so selection is table-only (`?event=<id>`, and the excluded-spans popover
links into it).

**Ask:** `onSegmentClick?: (row, segmentIndex) => void` and a `selected?: boolean` ring on a segment.
