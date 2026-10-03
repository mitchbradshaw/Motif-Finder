# Fixup W — cross-channel classification reaches an edge, and recurrence is counted with it taken out

**Runs after `V`** (there must be edges to classify). **Q40 is answered (below) and Parts 1–2 are measured — wave 5, beside `AC`.** *(Original note:* opens with a grilling round — `QUESTIONS.md`
Round 9, Q40 — and unlike the other prompts in this set it must not start building until Q40 is
answered*)*, because the rule it would store is the finding an examiner will attack (PRD, "Testing
Decisions": *"This is the test to insist on"*). Parts 1 and 2 below are measurement and can be done while
waiting. It is what **Q6** needs.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read `CLAUDE.md`, `docs/RESEARCH_READINESS.md` §Q6,
`docs/PIPELINE_PRD.md` "Cross-channel classification", `prototyping/UI_FUNCTIONAL_SPEC.md` §5.4, §8.4 and
§8.5, and `Working/cross_channel.py` in full (it is 135 lines).

Commit prefix `fixup-w:`. Test-first; first commit touches only `tests/` and must fail.
**`--sandbox` only.**

## Decided — `QUESTIONS.md` Q40 and Round 10 Q-W5 (2026-10-03). Parts 1 and 2 are DONE; go straight to Part 3.

Parts 1–2 were measured on 2026-10-03 (`QUESTIONS.md` "Q40, measured"; scripts, `part2_pairs.csv` and the scatter in `webui/screenshots/fixup/W/`). Re-use them in your report; re-run only to confirm.

- **Q40a — lag is measured on the same absolute window on both channels, always.** A family member is compared with its sibling channels at the member's own time; two snippets far apart in time are never "lag".
- **Q40b + Q-W5 — three bins, in seconds, with an r floor:**
  - **artifact:** |lag| ≤ **1 s** and **|r| ≥ 0.5**, either sign of r (events at the same time on two electrodes are contamination — the researcher's rule; a sub-second propagation is out of reach at 1 Hz);
  - **propagation:** **1 s < |lag| ≤ 50 s** and |r| ≥ 0.5;
  - **independent:** everything else, including any pair under the r floor whatever its lag.
  The three numbers (1 s, 0.5, 50 s) are Settings keys, converted to samples with each recording's `fs`; the sign of r is stored on the edge, not binned; each bin prints its rule on the page. There is **no** common-mode bin.
- **Fix while there:** Explore's lag is in *strided* samples compared against sample thresholds — convert with the stride and `fs`.
- **Q40c:** a co-occurrence on a sibling channel with no family member there is **counted on the family as *co-occurrence without a member***, never written as an edge.

## Running in parallel (2026-10-03)

**Wave 5: you run beside `AC`** (`AC-wavelet-bands.md`), another agent in the same checkout. The README's **"Running two prompts at once"** rules apply in full: your own port and a private client build served with `run_server.py --dist`; `npx vite build --outDir <yours>` while working and `npm run build` only for the gate (the other agent's in-flight files may make it red — say so in the report); `pytest -n 4`, never `-n auto`, and announce in your report when you took the machine for smoke; shared files are **append-only and committed immediately with your own hunks only** (`git add -p`). If you need a file the other agent owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `Working/cross_channel.py`, `Working/library/matching.py`, `webui/server/explore_routes.py`, `webui/client/src/explore/CrossChannelPage.tsx`, Library › Recurrence |
| **`AC`'s — do not edit** | `Adapters/preprocessing_wavelet_bands.py` (new), the wavelet kind in `Working/run_groups.py` and the band picker on *Apply template* |
| **shared** | `webui/client/src/api.ts`, `webui/smoke.py`, Settings (you add the three cross-channel keys; `AC` adds none — if it needs one, it requests it) |

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the options, then your recommendation (`CLAUDE.md`). **Before you report, update** `docs/prompts/rq_roundA/RQ6-recurrence-across-channels.md` per that folder's README.

## Where it stands

- Explore › Cross-channel classifies **one window, live**, and stores nothing. Measured 2026-10-02 on
  `M2_aug_concat_fs1.mat`, CH4_A2 as reference, a 640 s window at 0.83 h: lag *"0.0 s"* on all five
  pairs, r *"0.82"*, *"0.80"*, *"-0.76"*, *"-0.71"*, *"-0.70"*, each binned *"propagation"*.
- *"Classify every F-03 member in Library — runs across all channels and stores bins on edges"* is
  `notWired(...)` (`webui/client/src/explore/CrossChannelPage.tsx:317`).
- `Working/library/matching.py::classify_cross_channel_edges` (:284) has no route; the only entry is
  `python Working/cross_channel.py ENTRY_ID`.
- Every family on Library › Recurrence reads `artifactChannels 0 · propChannels 0 · indChannels 0`.

## Part 1 — measure what the two classifiers actually compare (before any code)

They are not the same computation, and only one of them measures a lag between channels.

- **Explore's route** (`webui/server/explore_routes.py:119–165`) cuts the **same absolute window** from
  the reference channel and from each sibling and calls `classify_waveforms` on the pair. Its lag is a
  time offset between two electrodes.
- **The Library's function** (`matching.py:284`) takes each edge's two **member spans**, wherever in the
  recording each one is, and calls `classify_waveforms` on those. Two members hours apart are resampled
  to a common length and cross-correlated; the "lag" that comes back is how far one *snippet* must slide
  to align with the other. It is bounded by the snippet length and says nothing about when either event
  happened.

So as written, the Library action would label a pair "propagation" or "independent recurrence" from the
alignment of two cut-outs. **Establish this with a test on a synthetic pair** — the same shape placed at
a known 5-sample offset on two channels, and again an hour apart — and report what each path returns.
If the Library path cannot recover the injected offset, that is the first finding of your report and
the reason Part 3 exists.

## Part 2 — measure the rule on real windows

On the sandbox copy, read-only: for a few hundred `interesting` windows of `M2_aug_concat_fs1.mat`, run
Explore's computation across all 16 channels and tabulate lag against r. The researcher needs to see the
shape of that cloud to answer Q40 — in particular how many pairs sit at |lag| ≤ 1 with |r| between 0.5
and 0.99, which today's rule (`cross_channel.py:33–38`, `:105–108`) calls *propagation*, and how many are
**negative** r, which today's rule can never call an artifact because it tests the signed value against
0.99. Put the table and one scatter in the report. No conclusion about biology; counts only.

## Part 3 — build, once Q40 is answered

1. **Classify simultaneous windows.** For a family member on one channel, the comparison is the same
   absolute span on each sibling channel of that recording — Explore's computation — not another member's
   snippet. Where the sibling also holds a member of the family overlapping that span, the result is
   written onto **their** edge (`lag`, `waveform_correlation`, `classification_bin`, via
   `_set_motif_edge_classification`). Where it does not, decide with the researcher (Q40c) whether a
   cross-channel co-occurrence with no member is recorded at all, and where.
2. **The rule is Q40's**, in named constants in `Working/cross_channel.py`, each printed on the page
   behind an info icon beside the count it produced. The synthetic lagged-pair test the PRD insists on
   must pass for every bin, including the injected-lag case from Part 1.
3. **A route and a job.** `POST` to classify one family across its recordings' channels — a `GenericJob`
   with per-channel progress, like a Discovery sweep. Wire *Classify every … member in Library* to it,
   and add the same act to Library › Family.
4. **Recurrence counts with the bins taken out.** Library › Recurrence: artifact cells red and still
   visible (§8.4 — *flagged, not excluded*); the count toggle gains "excluding artifacts" and
   "propagation counted once", each stating its rule. `recurrence_count` (`matching.py:331`) is the
   core's version; one definition, read by the page.
5. **Surrogate counts beside them**, from the run that produced the members — after `T`, the true draw
   count for that run. No claim that a count exceeds its null unless the page shows both numbers.

## Leave alone

| Leave alone | Why |
|---|---|
| Edge creation, the three distances, the scale bank | `V` |
| Multivariate analysis of any kind | out of scope in the PRD and parked in spec §11; this is a pairwise label on an edge, nothing more |
| Which recordings a family spans | the Library's import stores differ by species (`reishi_10hz` 2,425 · `oyster` 749 · `sp385` 76 entry tags); cross-recording recurrence is the researcher's to interpret |

## Acceptance — the researcher's walk

1. Library › Family for a family with members on several channels of one recording → *Classify across
   channels* → a job with per-channel progress.
2. The family rail's *cross-channel* line reads real counts per bin; each member's edge list shows lag
   and r where a sibling member co-occurs.
3. Library › Recurrence → the family's row: artifact cells red; the count toggle changes the row's totals
   and names the rule.
4. Explore › Cross-channel on one of those windows shows the same lag, r and bin the edge stores.

## The gate

`npx tsc -b` + `npm run build`; `webui/smoke.py` on a fresh `--sandbox` bridge, alone, finishing on the
**full** walk; `pytest -n 4` against the baseline in `README.md` (re-measure; compare failure sets).

Evidence into `webui/screenshots/fixup/W/`, including the Part 2 scatter.

## Report

`docs/prompts/fixup/reports/W-cross-channel-onto-edges.md`: Part 1's synthetic result for both paths;
Part 2's lag-by-r table; Q40 as answered; counts per bin on three real families; items left;
out-of-scope files touched; the gate.
