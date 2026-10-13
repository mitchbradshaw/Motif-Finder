# Fixup AP — the grey-text sweep: one caption per card, the rest behind ⓘ

**Written 2026-10-13 from a non-technical user's feedback via the researcher ("too many small greyed instructional
text website wide that makes it difficult to determine what the eyes should be focused on … shown text should be
limited to bare minimum required to understand a page, rest should be hidden behind information icons/accordion
dropdowns"). Not run yet. Page by page, one commit per page, never one sweep commit.**

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `webui/client/src/kit/README.md` (**P9: explanations live behind `InfoTip`, not in paragraphs on the
page** — this ticket restores a rule the kit already states), `webui/client/src/kit/surfaces.tsx` (`InfoTip`),
`webui/client/src/kit/display.tsx` (`Callout`, `EmptyState`, `DisabledReason`), `webui/client/src/shell/PathStrip.tsx`
and `webui/smoke.py` (which captions it asserts on — those must stay or the assertion must move with them).

Commit prefix `fixup-ap:`. **`--sandbox` only.** Smoke on your own port with a private dist.

## In plain words

Every page carries small grey sentences that explain what a card is, why a number is what it is, and what to do
next. One at a time they are helpful; all at once nothing stands out and a new user cannot tell where to look. The
fix is not to delete the words — they are the researcher's record of what each thing means — but to show one line and
put the rest one click away behind the ⓘ that most cards already have.

## The measure (2026-10-13)

`className` containing `muted`, `lib-cap`, `hint` or `caption` across `webui/client/src`: analyse 111 · discovery 148 ·
explore 35 · jobs 17 · library 175 · review 64 · settings 56 · models 48 · training 31 · interrogation 17 — about 700,
against 145 `<InfoTip>` and 102 `<Callout>`. The sweep halves the first number per page without lowering the second.

## The rule (apply it, do not reinterpret it per page)

1. **One caption line per card**, under the title, saying what the card *is*. Everything that says *why* or *how it
   is computed* goes into the card's `InfoTip` (the `SectionCard info=` prop exists for this).
2. **"What to do next" is not a caption.** It becomes the button's label, or the `disabledReason` printed under a
   disabled button (as Jobs' import button now does), or the empty state's `action`.
3. **Numbers keep their one-word unit and nothing else** on the page; the rule that produced them is in the tooltip.
4. A caption that smoke asserts on moves into the tooltip with its `data-testid`, and the smoke locator follows it.
5. Nothing is deleted. Text that fits none of the above goes into the page's header comment with a note why it left
   the page, so the record survives.

## Order (the researcher's path first)

Explore › Signal → Explore › Corpus → Analyse › Chain → Analyse › Block → Review → Discovery › Runs → Discovery › Seed →
Library › Atlas → Library › Family → Library › Grouping → Jobs → Settings › Datasets → the rest of Settings → Models.
Stop after each page: screenshot before and after into `webui/screenshots/ap/`, run smoke, commit.

## Acceptance (per page, then overall)

- [ ] The page's grey-text count is at most half of the measure above; the InfoTip count did not fall.
- [ ] Every card has at most one caption line; every disabled next-step button prints its reason.
- [ ] Smoke passes after each page; no assertion was deleted, only moved.
- [ ] The before/after pair for each page is in the report.

## Report

`docs/prompts/fixup/reports/AP-grey-text-sweep.md`: the per-page counts before and after, the pairs, and any caption
you could not place under the rule (list them; do not force them).
