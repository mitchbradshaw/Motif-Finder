# Fixup 01 — Explore: Corpus, Signal, Cross-channel, Span edit

**Status: skeleton.** Symptoms only. The prompt body is written after `QUESTIONS.md` Q-E1…Q-E4.

## Symptoms

| # | Symptom | Evidence |
|---|---|---|
| E1 | **Morphology tag selection should be a dropdown.** The tag control on Explore is not a select; the morphology vocabulary lives in `tag_vocabulary` and in `MORPHOLOGY_TAGS`, and the page does not offer it as a closed list. | user; `webui/client/src/api/review.ts:195`, `settings/VocabularyPage.tsx` |
| E2 | **Sending a span to Review carries no information about it.** *Take span for Review* writes the span, but the researcher cannot say what they think it is (morphology, class, note, why it is interesting) at the moment of sending — so Review receives an unlabelled span and the context that made it worth sending is lost. | user |
| E3 | **The Corpus page still fetches the unfiltered coverage map.** `coverage?run=&method=` is served and the rail's run list is live, but Corpus ignores both; a note beside the filters admits it. | wiring `reports/01-analyse-blocks.md` Left |
| E4 | **Cross-channel has no window control.** The window is "the channel's first human span ± pad, else its first ten minutes", chosen server-side, and the whole-channel option is disabled with a reason. | wiring `reports/01-analyse-blocks.md` questions table |
| E5 | **`coverage.rows[].both` is a sum**, not a count of channels where both are true. The page's colour-by means the sum, so the number is right for the colour and wrong as a label. | wiring `reports/01-analyse-blocks.md` critics, Left |
| E6 | **Clicking a cluster on a plot does not open its waveforms.** The user wants a plot to be an index into the data, not a picture of it — on Explore's maps as well as in the Library. | user (see also `08-library.md` L7) |
| E7 | `api/explore.ts` still holds 2 fixture reads. | wiring `reports/05-review.md` §7 |
| E8 | The first two axis ticks collide on the Signal page (critic P2-2, left unfixed). | wiring `reports/01-analyse-blocks.md` critics |

## Goal · Work · Testing and critique · Report

*(written after the questions)*
