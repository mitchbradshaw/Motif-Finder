# library-family-actions — pick a trace in the family overlay; click a cluster into the slideshow; the rose reference

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; then this file. Commit prefix `family:`; every
commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first for the bridge; client gated
by `tsc`, build, smoke states.

## Why (the researcher, 2026-10-15; older items confirmed 2026-10-18)

> Pick a trace in the family overlay and act on it. … Library: click a cluster → its members in place in the
> slideshow; the rose reference line = the median steepest slope over human-accepted Library motifs, printed on
> every rose.

## Decided with the researcher

- **Pick a trace:** clicking a trace in the family overlay highlights it, names its detection (recording, channel,
  time, verdict), and offers three actions beside it: **remove from the family** (the existing remove-member edit),
  **send to Review** (the picked-queue mechanism, one detection), **open in Explore** (the Signal page on that
  channel at that span, via the `ub-proto-a:source` handoff or the view state Explore reads). No "make exemplar":
  what a medoid is stays a separate decision.
- **Click a cluster (Q-L6/Q-E6):** in the atlas and on the family page, clicking a cluster/family card opens its
  members in place in the `H` slideshow (the kit `EventSlideshow`), not a navigation.
- **The rose reference:** every rose draws a reference line at the median steepest slope over the human-accepted
  Library motifs of the same unit (`verdict in (interesting, seed)`), labelled with its value and `n`; computed by
  the bridge once per request family and cached by the adjudication fingerprint.

## Facts

- The family overlay is on `webui/client/src/library/FamilyPage.tsx` (the overlay component it uses — find it;
  `kit` has `EventSlideshow`); remove-member is already there. The picked queue: `sendDetectionsToReview`
  (`api.ts`, fixup-AL). Explore's handoff: `state.tsx:74-78` (`ub-proto-a:source`, `SourceSpan` with
  `recording_id`, `start_idx`, `end_idx`). Roses: kit `Rose`, used in `SlopePage.tsx:460`, `SequencePage.tsx:69`,
  `SpansToSpans` (`registry.tsx:441`); the slope values come from `block.rose` / `p.rose`.

## The work

1. **Overlay pick:** hit-testing on the overlay's paths (nearest path within 6 px), a highlighted stroke, a small
   caption card with the three buttons; keyboard ↑/↓ to move the pick between members.
2. **Cluster click → slideshow in place:** on the atlas card and the family page's cluster strip, open the members
   as slideshow events (the family's members with their spans), with the same load function the block slideshow
   uses; Esc closes.
3. **Rose reference:** `GET /api/library/rose-reference?unit=motifs` → `{median_slope, n, computed_from}`; the
   kit `Rose` gains an optional `reference` prop (angle line + label); the three rose sites pass it.

## Files

Yours: `webui/client/src/library/FamilyPage.tsx`, `AtlasPage.tsx`, the overlay component, `webui/client/src/kit/`
(`Rose`, the slideshow's in-place host), `webui/server/library.py` (one route), `webui/client/src/api.ts`, the three
rose call sites (prop only), `tests/`.

## Method and gate

- Tests (venv): the reference route returns the median over accepted motifs and changes after a verdict; a unit
  with no accepted motifs returns `n: 0` and no line.
- `tsc -b`, `vite build`. Smoke in `webui/smoke_pages/zzzzzzzzzzz_family_actions.json`: a click on the overlay
  highlights a trace and shows the three buttons; a cluster click opens the slideshow in place; a rose shows the
  reference label.
- Run your files plus `tests/test_webui_library.py`, `tests/test_import_boundaries.py`.

## Report

`docs/prompts/changes/reports/family-actions-report.md`: **Assumed**; what each action does; tests; smoke states;
what is left.
