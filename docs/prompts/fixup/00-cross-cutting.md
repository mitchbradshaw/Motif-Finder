# Fixup 00 — cross-cutting: the shell, shared chart primitives, naming, workflow

**Status: skeleton.** Symptoms only. The prompt body is written after `QUESTIONS.md` Q-X1…Q-X6.

## Symptoms

| # | Symptom | Evidence |
|---|---|---|
| X1 | **22 fixture reads remain** outside Review, in three workspaces with no wiring prompt (Models 6, Jobs 6, Training 1) plus remainders in `analyse.ts` (6), `explore.ts` (2), `library.ts` (1). Every one of those pages still wears the "demo data" chip. | wiring `reports/05-review.md` §7 |
| X2 | **Hard-coded y domains are a systemic class, not a page bug.** Review pins every trace to `[-0.44, 0.44]` mV and every thumbnail to `[-0.45, 0.45]`; Discovery shipped a 0–8 distance axis over data running to 17 (fixed by its critic); Library's shared domain is a deliberate percentile rule that the user reads as "every plot has the same axis". One rule is needed for the whole app: when a domain is shared, when it is the data's, and how a clipped trace is marked. | `webui/client/src/review/parts.tsx:12`, `review/Shell.tsx:18`; wiring `reports/04-discovery.md` §"Three defects"; `library/chrome.tsx:301` |
| X3 | **The supervisor's actual workflow has no path through the app**: *find a spike train → analyse its spikes* (ISIs, per-spike width/amplitude/recovery). Today spike trains are a defined-but-unpopulated Library scale, `spike_analysis.compute_spike_statistics` is a stub, and no page moves from "here is a train" to "here are its spikes". | user; wiring `reports/03-library.md` §8.7; `reports/01-analyse-blocks.md` unfinished-algorithms table |
| X4 | **Datasets are named by their source file and nothing else** — `M2_aug fs1`, `M4_aug_concat_fs1.mat`, `L_LM_Jul_26_J`. A reader cannot tell species, organism, duration, channel count, or what distinguishes `M2_aug` from `M2_concat`, without opening Settings › Datasets. The name appears in every workspace header, every queue title and every card. | user; `memory/m2-datasets-and-seeds.md` |
| X5 | **"Code your own algorithm."** The user wants to add an analysis block without an agent round-trip. Nothing in the app accepts user code; `Adapters/` is a Python registry with a written contract (`docs/BLOCK_INTEGRATION.md`) and a per-adapter test module enforced by `tests/test_block_standard.py`. Whether this is a Settings surface, a scaffolding generator, or refused outright is undecided, and it has the largest security and gate surface of anything in this stage. | user |
| X6 | `Header` does not derive `demo` from the page's sourced reads; each page passes the prop. Harmless, but a page that goes live and forgets the prop lies to the reader. | wiring `reports/01-analyse-blocks.md` Left |

## Goal

*(written after the questions)*

## Work (test-first per seam)

*(written after the questions)*

## Testing and critique · Report

*(written after the questions)*
