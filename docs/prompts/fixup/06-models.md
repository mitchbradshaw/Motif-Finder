# Fixup 06 — Models: Launch, Results, Compare, Registry

**Status: skeleton.** Symptoms only. The prompt body is written after `QUESTIONS.md` Q-M1…Q-M2.

**No wiring prompt was ever written for this workspace.** All four pages are fixture shells; this is not a
fixup so much as the wiring prompt that stage 3 did not get to. Sizing it is the first question.

## Symptoms

| # | Symptom | Evidence |
|---|---|---|
| M1 | **`api/models.ts` holds 6 fixture reads and every page wears the "demo data" chip.** Launch, Results, Compare and Registry all draw fixture shapes: paired label arms, nulls, calibration, paired metrics, disagreement windows, candidate checks, sign-off. | wiring `reports/05-review.md` §7 |
| M2 | **What exists server-side to wire against**: 18 models registered on this machine through Prompt 02's registry; `catalogue.cnn_score` as a block; `MODEL_ROOT` redirected in sandbox mode; `registered_artifacts(kind='model')`; the held-out lock (M4/D6) refused server-side without the typed name. What does **not** exist: any route that trains a model, any arm/nulls/calibration payload, any table for paired label arms. | wiring `reports/02-settings-import.md`; `reports/01-analyse-blocks.md` |
| M3 | **Launch from a window set cannot work**: `window_sets` holds zero rows (see `04-analyse-training.md` T4). | wiring `reports/03-library.md` §9 |
| M4 | **`fusion_prediction`** (a second CNN head, `FusionPredictionCNN`) is a `model_kind` parameter away from being runnable — 2 h, and wiring's recommendation was to finish it "when a registered checkpoint needs it". Models is that need. | wiring `reports/01-analyse-blocks.md` unfinished-algorithms table |
| M5 | **Registry sign-off and the held-out checks** are the one place a model can be promoted; the unlock is enforced server-side for Settings but nothing checks a *model* against the held-out recordings before registration. | wiring `reports/02-settings-import.md` |

## Goal · Work · Testing and critique · Report

*(written after the questions)*
