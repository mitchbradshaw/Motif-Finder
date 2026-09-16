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
