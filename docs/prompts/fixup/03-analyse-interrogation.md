# Fixup 03 — Analyse › Interrogation: family block, Slope, Aggregate

**Status: skeleton.** Symptoms only. The prompt body is written after `QUESTIONS.md` Q-I1…Q-I3.

## Symptoms

| # | Symptom | Evidence |
|---|---|---|
| I1 | **Drop morphology is not encoded as analysable features.** The user wants width vs amplitude vs recovery time as first-class quantities — *"e.g. drop width vs recovery time"* — plotted against each other, with the relationship fitted and nulled. Today Interrogation's aggregate route computes depth / interval / slope distributions from the seed store; **recovery is measured on the stored snippet** (trough back to within 10 % of the drop of the onset level) and **the store does not carry it**, so it is recomputed per read and nothing downstream can filter or group on it. | user; wiring `reports/01-analyse-blocks.md` questions table |
| I2 | **Each motif should store its own width, amplitude, recovery.** Library §4.4 rejects measured features on Library rows outright and the four feature-bin bases are computed on demand. That decision and I1 are in direct tension: the user is asking for exactly the stored measurements the spec refuses. This is a spec decision, not a bug. | user; wiring `reports/03-library.md` §8.6 |
| I3 | **Inter-spike intervals.** `spike_analysis.compute_spike_statistics` is a stub whose body is a comment; wiring's recommendation was "ignore for v1 — the aggregate route covers the intent". The user has since named ISIs directly, which changes that call. | user; wiring `reports/01-analyse-blocks.md` unfinished-algorithms table |
| I4 | **The slope page's selectors are a preview, not the rule.** The rules card lists the store's rules verbatim and says so, but the selectors beside them do not drive anything. | wiring `reports/01-analyse-blocks.md` critics |
| I5 | **Interrogation is marked "seed"** — it reads the drop-motif seed store, not the Library's motif tables, so it cannot interrogate anything imported after the seed bundle. | wiring `reports/01-analyse-blocks.md` |

## Goal · Work · Testing and critique · Report

*(written after the questions)*
