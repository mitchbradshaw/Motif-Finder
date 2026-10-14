# Wave 3 — evaluation against each template's null on real recordings

Run by the manager, 2026-10-14/15, in **sandbox copies** of the database (`webui/server/runtime.py`, mode `sandbox`,
runtime roots in the session scratchpad — nothing written to the real `DATA/`). Scripts: `eval3/` in the session
scratchpad (`w3common.py`, `eval_mse.py`, `eval_cycles.py`, `cycles_floor.py`, `eval_pan.py`, `eval_mpdist.py`,
`eval_library3.py`, `eval_families3.py`); raw results `w3_*.json` beside them (not committed). Every statistic below
was fixed in `W3-ledger.md` ("The evaluation's statistics, declared before any data are seen", `64db0da`) before any
real recording went through a wave-3 block; the two corrections to it (the AAFT null for the complexity and
motif-length templates) were also made before any data, for measured flaws in the null, not for a result.

**The bar (researcher, Q4):** a chain ships as a template only if it beats its random-data null on real recordings —
its statistic beats every one of 20 null draws (p = 1/21 ≈ 0.048) — on at least 2 of 3 recordings.

## In plain words

Wave 3 built five things and checked them the way waves 1 and 2 were checked: run each template on real recordings,
run it again on 20 versions of the same recording with the pattern destroyed, and ship it only if the real recording
stands out every time. Think of a sniffer dog that must find the hidden treat more often than the empty boxes — on at
least two of three searches.

| What was built | In one line | Template verdict |
|---|---|---|
| **Multiscale entropy** (`catalogue.multiscale_entropy`) | How surprising a recording is at each level of blur, from 1 s to minutes — a "complexity curve" per recording | `complexity_fingerprint` **ships**: all three recordings differ from noise that keeps their values and their frequency content |
| **Cycle shapes** (`interrogation.cycle_shapes`) | Every drop-to-drop cycle of a chain stretched to one length, stacked, lined up and sorted into shapes | `chain_cycles` **ships**: on all three long chains the cycles are far more alike than pseudo-cycles cut from the recording's own quiet stretches |
| **Pan matrix profile** (`detection.pan_matrix_profile`) | At which window lengths anything repeats, as a picture with lengths up the side | `motif_lengths`: *(pending — see its section)* |
| **MPdist** (a fourth Library distance) | Do two members share their short sub-shapes, each at its own speed? | no template; on five real families it singles out one held together only by stretching |
| **A fairer noise test for families** | Fake families cut from the recording's own quiet stretches, beside the old scrambled ones; a family passes on either | no template; two smooth HDBSCAN families are no longer called noise; Analyse offers k-Shape again |
| **The UI** | *(pending)* | — |

## `complexity_fingerprint` — 2 h detrend → 72 h windows → a multiscale-entropy curve per window

**Statistic (declared):** the window-median curve's Euclidean distance (in nats, over the scales defined in all 21
runs) from the mean of 20 null draws, against each draw's distance from the mean of the other 19. **Null (declared,
corrected before any data):** 20 **AAFT** surrogates — the recording's own values rank-mapped onto a phase-randomised
Gaussian version, so the copies keep the value distribution and about the spectrum (Theiler 1992). The W3-A critic
showed why plain phase randomisation is not a fair null here: sample entropy with a MAD-based tolerance reads the
value distribution, so a featureless but lopsided process "beat" plain phase copies 20/20. The app's plain phase
draws are reported beside, for comparison. **Spans:** rec 1 and rec 3 from 440 h for one template window (440–512 h;
the brief's 24 h spans are shorter than the template's window — the rule was fixed before any data), rec 600 whole.

| Recording | Scales compared | Distance, real | AAFT draws (max; mean) | p | Plain phase draws (max) | Beats? |
|---|---|---|---|---|---|---|
| rec 1 · M2_aug CH0 · 440–512 h | 9 (1–174 s) | **0.84** | 0.18; 0.09 | 0.048 | 0.14 | **yes** |
| rec 3 · M2_aug CH2 · 440–512 h | 9 | **1.86** | 0.35; 0.12 | 0.048 | 0.09 | **yes** |
| rec 600 · *S. commune* CH0 · whole 73 h | 9 | **1.05** | 0.83; 0.38 | 0.048 | 0.18 | **yes** |
| rec 385 · Mushroom_260720 CH14 · 4 h | — | refused in words: "no window fits: the span has 14401 samples and one window is 259200 … shorten window_s or widen the span" | — | — | — | — |

**Verdict: ships** (3 of 3). Moved into `CANONICAL` (`46480ce`); its description now points the user at the AAFT
null (Settings › Nulls offers `aaft`, added by W3-A's fix round).

**Which way the curves differ.** M2_aug sits *below* its surrogates at every scale, more with scale (rec 3: −0.11
nats at 1 s, −0.93 at 174 s) — more regular than noise with the same values and spectrum, the more so the longer the
blur. *S. commune* sits *above* at 1–7 s (+0.49 to +0.61) and below past ~48 s.

**Warnings read:** each run warned that 3 of 12 scales are blank (a 72 h window reaches about 4.3 min); no collapse
flag, nothing left out. **rec 385 with one 4 h window** (information, the brief's "too few scales" check): 5 scales
defined (1–13 s), and it beats all 20 AAFT draws (distance 1.79 vs max 0.41).

### Species and conditions

Fingerprints of three channels per dataset — *S. commune* (recs 600–602), *C. militaris*, *F. velutipes* and
*O. nidiformis* (channels 0–2 each, **registered in the sandbox copy only**, through the same functions Settings ›
Datasets calls), and M2_aug (recs 1–3) — in 72 h windows (3 / 21 / 12 / 36 / 30 windows). **Statistic (declared):**
the silhouette of the dataset labels on the per-scale entropies (9 scales, z-scored). **Null:** the same windows' AAFT
copies, 20 draws (p's floor 1/21), plain phase beside.

| | Silhouette |
|---|---|
| Real fingerprints | **0.428** |
| 20 AAFT draws | 0.22–0.37 (mean 0.29) → real beats every draw, **p = 0.048** |
| Plain phase draws | 0.35–0.36 (5 draws) |

Median curves (entropy at 1 s … 174 s): *S. commune* 0.93 → 1.38 → 0.79; *C. militaris* 1.20 → 1.78 → 0.68;
*F. velutipes* 1.23 → 1.68 → 0.55; *O. nidiformis* 1.06 → 1.36 → **0.07** (the steepest fall); M2_aug **0.03 → 0.73,
rising**.

Plainly: the datasets do separate on their complexity curves, and better than noise with their own values and
spectrum — but most of the separation is already in that noise (0.29 of the 0.43). And M2_aug comes from another
setup (another logger, stored in V, far smoother at 1 s), so "M2_aug against the species" mixes organism with
instrument; the four Adamatzky species share one logger and are the cleaner comparison.

### The √t check

*S. commune* CH0–CH6 through the template **without the detrend and with `r_scale="sd"`** (the preprint's setting),
against the template's own settings:

| Channel | Mean entropy, raw + SD r | Guard fired | Template (2 h detrend, MAD r) |
|---|---|---|---|
| CH0 (rec 600) | 0.197 | every defined scale | 1.020 |
| CH1 | 0.053 | every defined scale | 0.978 |
| CH2 | 0.052 | every defined scale | 0.583 |
| CH3 | 0.021 | every defined scale | 0.912 |
| CH4 | 0.161 | every defined scale | 1.175 |
| CH5 | 0.494 | every defined scale | 0.698 |
| CH6 | **0.014** | **no** | 0.852 |

**Answers (declared):** *does the collapse reproduce* (mean < 0.01)? **No** — entropy falls to 0.014–0.49 (mean 0.14),
a partial collapse, an order of magnitude above the preprint's 0.0028. *Does the number reproduce* (0.001–0.008)?
**No.** *Does the guard fire?* **On 6 of 7 channels, on every defined scale; not on CH6, the most collapsed** — CH6
holds a −71 mV spike (range −71.2…1.8 mV) that inflates the SD before and after the detrend alike, so the drift guard
(inflation) stays near 1. Outlier-driven inflation is a second route to collapse; only `r_scale="sd"` is exposed to
it (the template's MAD r is immune). Follow-up: flag SD ÷ (1.4826 × MAD) when `r_scale="sd"`.

## `chain_cycles` — noise threshold → Event shape → Trains (chain scale) → Cycle shapes → Intervals

**Statistic (declared):** the aligned stack's SVD entropy, **σ² and eq. 17**, each below every one of the block's 20
**background-null** draws (pseudo-cycles cut at random places from the recording's own event-free stretches, through
the identical pipeline); a span whose background fell back, or whose quiet margins differ in colour from its own noise,
has no verdict; a span's verdict is its largest sequence's.

| Chain | Detector events | Cycles used | σ² real (draws' min) | eq. 17 real (draws' min) | Fallback · colour check | Verdict |
|---|---|---|---|---|---|---|
| rec 3 · 490–540 h | 116 | 77 of 115 | **0.169** (0.445) | **0.652** (0.839) | 0 · fine | **beats** |
| rec 6 · 370–470 h | 115 | 104 of 113 | **0.097** (0.298) | **0.457** (0.648) | 0 · fine | **beats** |
| rec 542 · 370–490 h (10 Hz) | 163 | 120 of 155 | **0.460** (0.795) | **0.918** (0.944) | 0 · fine | **beats** |
| rec 2 · 294–304 h | 13 | 9 of 12 | — | — | — | no verdict: 9 cycles < 10 |

**Verdict: ships** (3 of 3 long chains). Moved into `CANONICAL` (`6f07cff`). The app's phase-randomised copies of the
same spans gave the further floor: 0 events on 19 of 20 draws (one draw found 1).

**Findings (beside the verdict):**
- **One cycle shape per chain.** K = 1 on all three (SigClust p 0.10 / 0.10 / 0.90, reported only; the mode test p
  0.23 / 0.79 / 0.70), so no change point and no order test. Wave 2's `event_families` found two families on rec 6
  (53, 13) and on rec 542 (131, 11) from 600 s windows. The whole-cycle view sees one shape; the block's K gate gives
  up power for a 80/20 or 90/10 mixture at 30 % noise, so a minority shape is not ruled out — the cycle stack picture
  (W3-F) is where to look.
- **Gaps.** rec 3 left 24 of 115 cycles (21 %) out as `gap_long`, and the block warned that the longest cycles are the
  ones lost; rec 542 12 %.
- **The floor fraction, rec 2 against rec 3.** Per cycle, median [p25–p75]:

  | Chain | Floor fraction | Half recovery at | Median cycle |
  |---|---|---|---|
  | rec 3 (sharp drops) | 0.109 [0.06–0.17] | 0.25 of the cycle | 22 min |
  | rec 6 (scalloped) | 0.205 [0.14–0.26] | 0.16 | 37 min |
  | rec 542 | 0.016 | 0.023 | 24 min |
  | **rec 2, the labelled sharkfins (298.2–299.2 h)** | **0.02–0.03** | **0.04–0.06** | 10–19 min |

  rec 3 behaves as the researcher describes a trough ("mostly back by the quarter point"). rec 2's sharkfins do **not**
  read as sharkfins. The raw trace shows why: each is a 50–78 mV drop that recovers half its depth within ~40 s and then
  sits 2–15 % of the depth below its starting level, drifting slightly lower, until the next drop (cycle 3, mean level
  per tenth of the cycle: −0.60, −0.22, −0.17, −0.14, −0.13, −0.12, −0.11, −0.11, −0.12, −0.12 of the depth). That
  shallow, drifting level is the researcher's "floor"; the block's floor band — the lowest quarter of the cycle's range
  — sits down at the drop's minimum and cannot see it.

## `motif_lengths` — 2 h detrend → pan matrix profile (30 s – 1 h, 12 lengths)

*(pending: W3-C's fix round; the declared statistic and the AAFT correction are in the ledger.)*

## MPdist (W3-D) on real Library members

No accepted RQ3 pair exists yet (`motif_edge` is empty), so, as the brief says, five families' members against their
medoids: the five largest families of the stored Ward g-05 whose medoid MPdist can compare. All three distances on
one footing (√(1 − r): 0 = identical, 1 = uncorrelated); nulls: MPdist between AR(1) φ 0.99 and random-walk pairs at
the same lengths.

| Family (members; medoid / median member length) | MPdist median | Scale-invariant | Native length | Noise pairs | Members below noise's p10 |
|---|---|---|---|---|---|
| F-30 (79; 364 / 552 samples) | 0.064 | 0.064 | 0.63 | 0.50–0.53 | 100 % |
| **F-130 (55; 1,014 / 31)** | **0.68** | **0.13** | 0.70 | 0.51 | 27 % (10 refused: too short) |
| F-141 (51; 2,154 / 32) | 0.22 | 0.15 | 0.27 | 0.44–0.49 | 100 % (4 refused) |
| F-01 (49; 1,312 / 1,317) | 0.19 | 0.14 | 0.58 | 0.54–0.65 | 91 % (1 refused) |
| F-88 (43; 24 / 34) | 0.22 | 0.20 | 0.77 | 0.51–0.53 | 90 % |

What it adds to RQ3, plainly: where members and medoid share a duration, MPdist agrees with the scale-invariant
distance and both sit far below noise, while the native-length control reads large — MPdist does not hold a shifted
start or extra baseline against a pair. Where the members are ~30× shorter than the medoid (F-130), MPdist reads at
noise level while the scale-invariant distance calls them close: **that family holds together only after
stretching**, which is exactly RQ3's question, now visible per family. MPdist refuses members under 16 samples (15 of
271 pairs here; 21 % of the Library), in words.

## The fairer noise test (W3-G)

**The Library table again**, on exactly the items and loader the Library's grouping job uses, with each family judged
by either null (the recording's own quiet stretches, selection-matched, margin 0.6; or the trend-kept surrogates,
margin 0.9) and its coherence from the Family page's own function:

| Method | Families | Placed | Noise-like now (trend-kept alone; wave 2) | Passed by both / quiet only / trend only / none | Coherence beyond noise |
|---|---|---|---|---|---|
| Ward (cut 0.6) | 151 | 3,296 | not tested | — | 116 of 151 |
| HDBSCAN | 19 | 687 | **1** (3; 3) | 14 / 2 / 2 / 1 | 19 of 19 |
| HDBSCAN leaf | 23 | 582 | **0** (2; 2) | 17 / 2 / 4 / 0 | 23 of 23 |
| k-Shape, k = 20 | 20 | **2,701** (1,996 in wave 2) | **11** (17; 8 under its old plain-phase null) | 3 / 6 / 0 / 11 | 19 of 20 |

Which families change verdict, and why:
- **HDBSCAN:** two families the trend-kept null called noise-like are rescued by the quiet stretches (eom: 3 → 1;
  leaf: 2 → 0) — the smooth-shape blind spot, removed.
- **k-Shape:** its automatic cut is now the quiet windows' 5th percentile, so it places more events (2,701 vs 1,996),
  and 11 of its 20 families read noise-like (8 under the old plain-phase null, 17 if the trend-kept null judged alone).
- **Coherence:** no family moved — every family beyond noise by the quiet null was already beyond by the trend-kept
  one.
- **Analyse offers k-Shape again** in `interrogation.event_families` (no unmarked Intervals key in the critic's 37
  no-structure runs).

**`event_families` on the chains where wave 2 met the blind spot** (template status not re-judged): rec 6's two
families (53, 13) pass both nulls (quiet-stretch ratios 0.03× and 0.01×), as before. rec 542's two families (131, 11)
stay confident, but **by the trend-kept null only** — the chain's own quiet stretches crowd nearly as tightly
(0.79×, 1.20×) — and the 131-member family's coherence is still not beyond noise (eq. 17 0.82 vs 0.81). So the quiet
null does **not** rescue rec 542's large family: its smoothness was not the trend-kept null's blind spot alone. rec
543 (dense) gives no family at all.

## The gate

*(pending)*

## What the researcher should decide

*(pending — drafted after the last evaluations.)*
