# polish-pass — the site reads clean: less grey, fewer warnings, one palette, nothing a layperson must decode

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md`; `docs/prompts/fixup/AP-grey-text-sweep.md`
(the caption rule this pass extends); then this file. Commit prefix `polish:`; one commit per page. Runs AFTER the
speed pass (AR) and after the prompts that reshape pages (`seed-search`, `interval-event-pages`,
`discovery-coverage-and-gauge`), so it polishes the final shapes.

## Why (the researcher, 2026-10-18)

> Need a pass to ensure the website is polished, clean and readable. … Less yellow warning symbols where possible,
> and even less grey information text — include it in accordion dropdowns or info tags; really only the bare
> necessary information by default. Anything that a layperson would not understand on first read can be considered
> compressible. This is also true for analysis blocks: when adding a new block, the information should not be a wall
> of text on the right-hand side of the add-block pop-up, but a dropdown or a pop-up "about" card of its own.

## The standard (decided 2026-10-18)

1. **Grey text:** one caption per card (AP's rule), everything else behind ⓘ (InfoTip) or an accordion labelled
   "about …" / "how this is measured". The test: cover the grey with your hand — does the card still make sense to
   someone who has never seen the app? If yes, the grey was compressible.
2. **Warnings:** a yellow ⚠ only when the researcher must act or the number is unreliable. A note about a default,
   a scale, a demo source, or "not measured yet" is a muted ⓘ or a chip, not a warning.
3. **Palette:** primary blue, secondary muted blue (`--blue-muted`), green for "next" / go, red for destructive;
   never a grey button for an available action; disabled buttons say why on hover.
4. **Type and spacing:** the kit's sizes only (no inline font sizes under 10.5 px; no ad-hoc paddings where a kit
   layout exists); numbers right-aligned with their units in tables; one mono style for identifiers.
5. **States:** every list has an empty state with the one action that fills it; every failure is a red card with
   the server's sentence; no `demo data` chip on a live page (Jobs, Models, Training: label from
   `corpus.dataset_name`, or the chip goes).
6. **Add-block pop-up:** the block list on the left, and on the right ONLY the block's name, its one-line purpose,
   its inputs → outputs, and its parameters; the long explanation (what the method is, the paper, the caveats) is an
   "About this block" expander or a card that opens on ⓘ, closed by default.
7. **No layout jumps:** a card that loads shows a skeleton of its final height (AR's pattern), never a placeholder
   of another size.

## Order (the researcher's worst-first, then the rest)

Discovery › Runs → Library › Family → Analyse › block pages (and the add-block pop-up) → Discovery › Seed → Review
› Inspector → Explore › Signal and Cross-channel → Library › Atlas and Grouping → Settings pages → Models,
Training, Jobs → Corpus (home) → Reports. One commit per page named `polish: <page> — <what changed in one line>`.

## Method

- Before each page: list in your report every grey line, every ⚠, every grey button and every inline style you
  found, and what you did with each (kept / moved behind ⓘ / into an accordion / deleted / recoloured). That table
  is the evidence; the page is done when the table is empty of "kept because".
- Do not change any number, label, route or behaviour; this pass moves and restyles. If a page's wording is wrong,
  note it, do not fix it here.
- Smoke: the existing states must keep passing (selectors stay; add `data-testid` rather than renaming). Add one
  state per page to `webui/smoke_pages/zzzzzzzzzzz_polish.json` that counts `.muted` text nodes in the page's
  main card and asserts the count is at or below the number you report.
- `tsc -b`, `vite build` after every page.

## Files

Client only: `webui/client/src/**` for the pages in the order above, `kit/` for a missing primitive (an `About`
expander), the pages' CSS. No server change; no test under `tests/` except smoke states.

## Stop and report if

a page cannot meet rule 1 without changing its behaviour (then describe the change for its own prompt).

## Report

`docs/prompts/changes/reports/polish-report.md`: per page the table above and a one-line summary; the kit
primitives added; the smoke states; what is left.
