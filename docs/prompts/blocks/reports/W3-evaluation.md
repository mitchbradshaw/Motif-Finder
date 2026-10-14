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
| **Pan matrix profile** (`detection.pan_matrix_profile`) | At which window lengths anything repeats, as a picture with lengths up the side | `motif_lengths` **ships**: on two of three chains the windows repeat far more than noise with the same values and spectrum — but on every recording every length "repeats", so the answer does not pick a window; the picture does |
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
| Plain phase draws | 0.350–0.363 (5 draws, p's floor 1/6), all below the real 0.428 |

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

**Statistic (declared; its null corrected to AAFT before any data):** at the real run's strongest-gap length
(`suggested_window_s`), the span's median normalised nearest-neighbour distance (1 − the median of that image row)
against 20 AAFT draws, seeds 0–19 (plain phase beside, 5 draws). Beats when below every draw. A span where no length
stands out does not beat. The draws were scored on the same image row with the block's own three null copies off
(`null_draws` 0, "picture only"): the row is the span's own profile whatever that setting is, and the script checked
on every real run that the picture-only rows equal the full run's (they did, all four) before relying on it.

| Span | Lengths that clear (all judged ones?) | Strongest gap at | Real median distance | AAFT draws | p | Plain phase draws | Beats? |
|---|---|---|---|---|---|---|---|
| rec 2 · M2_aug CH1 · 296–304 h (sharkfins) | 30–1508 s (10 of 10) | 30 s (gap 40.9) | 0.265 | 0.142–0.151 | 1.0 | 0.081–0.082 | **no** |
| rec 6 · M2_aug CH5 · 400–408 h (chain) | 30–1508 s (10 of 10) | 976 s (gap 25.7) | **0.018** | 0.204–0.264 | 0.048 | 0.200–0.220 | **yes** |
| rec 3 · M2_aug CH2 · 512–520 h (chain) | 30–1508 s (10 of 10) | 976 s (gap 35.4) | **0.110** | 0.280–0.319 | 0.048 | 0.252–0.280 | **yes** |
| rec 385 · Mushroom_260720 CH14 · 4 h (the supervisor's check) | 30–976 s (9 of 9) | 30 s (gap 15.8) | **0.143** | 0.209–0.216 | 0.048 | 0.156–0.158 | yes |

**Verdict: ships** (2 of 3 chains). Moved into `CANONICAL` (`64b2995`), its description now saying what the band
did on these recordings. No stalls (`n_stalled` 0) and no long gaps on any span; the real run took 82 s (4 h) and
~180 s (8 h) at 3 threads on a loaded machine.

**Findings (beside the verdict):**
- **The band picks no window on real recordings.** Every judged length cleared on all four spans. What the template
  can say here is that the span repeats beyond noise with its own values and colour; *which* length is the event's is
  in the picture, as the W3-C critic found on planted data (the band covered every judged rung in 8 of 10 runs).
- **The strongest gap is not an event length, again.** It fell at 976 s on both chains (the longest rung judged at the
  full cut — leaning long, as measured) and at 30 s, the shortest rung, on rec 2 and rec 385.
- **The supervisor's check (rec 385):** does it point at ≈ 1 min? **No** — the strongest gap is at 30 s, with 46 s
  and 72 s close behind (gaps 14.8 and 13.5 against 15.8). At 30 s the recording beats all 20 AAFT draws. So short
  windows repeat beyond noise there, as the 1-minute spikes would, but the block cannot name 1 min over 30 s.
- **Why rec 2 fails, though its gap is the largest anywhere.** The two statistics ask different things. The block's
  gap compares the span's *closest few* matches with the copies' closest few: rec 2's drops match each other very
  closely at 30 s. The declared statistic reads the *typical* window: most 30 s windows of that span are the quiet
  stretches between 13 drops, whose fine jitter rarely repeats, while an AAFT copy spreads the drops' slow swing
  evenly over the whole span, so every 30 s piece of a copy is a smooth curve that finds a twin easily (0.265 against
  ~0.145). On a span whose power sits in a few events, the typical window is the quiet one; the declared statistic was
  fixed before the data and stands.

### The FLUSS window (report only)

The brief's item 3, as declared before any data (`W3-ledger.md` decision 26): never the strongest-gap length (W3-C's
re-critique: it is not an event length), but the **top of the cleared band**, read on a span long enough to judge a
chain's unit — `motif_lengths` on rec 6 400–424 h — then the experimental `fluss_regimes` on rec 6 370–470 h at that
length (its detrend kept at the template's 2 : 1) and at 300 s (the template exactly), side by side. The paper's
readout (`regime_locs`, the two lowest arc-curve minima) is compared with the chain's edges at 383 h and 445 h.

| Run | Result | Seconds |
|---|---|---|
| `motif_lengths`, rec 6 400–424 h | clears 30–2330 s (11 of 12; 3600 s just below its cut, gap 5.5 vs 6.0); strongest gap at 30 s | 516 |
| `fluss_regimes` at **2330 s** (detrend 4660 s) | changes at **424.9 h and 421.7 h** (arc-curve 0.29, 0.31) — mid-chain, **20–23 h** from either edge | 144 |
| `fluss_regimes` at 300 s (the template) | changes at 469.5 h and 469.1 h (arc-curve 0.53, 0.54) — at the span's end, about 30 min inside the scored part, 24 h past the chain's end | 129 |

`estimate_seconds` gave no number (the matrix-profile cost model is uncalibrated in a fresh sandbox, and the block
never guesses); the whole piece took under 15 minutes, far inside the hour's cap.

**Plainly:** handing FLUSS pan's longest repeating length does not make it find rec 6's chain. With a 39-minute window
it calls the middle of the chain the strongest change; with 5 minutes, the end of the span. FLUSS stays experimental
(its status moves only by the Q4 bar). The 300 s answer is an edge effect, and a repeatable one: the 2026-10-14
retest used the same readout on a different span, 372–456 h, and got 455.5 h and 372.5 h — each about half an hour
inside that span's ends, as 469.5 h is here. At 300 s FLUSS's strongest changes follow the span's ends, not the
chain's; at 2330 s they move inside the chain (≈ 422–425 h), which nothing else here marks as a boundary. One aside,
from one span only: the band's top, 2330 s (39 min), is the ladder's first rung above rec 6's median cycle (37 min,
cycle shapes) — worth checking on other chains before reading anything into it.

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

Each question opens with what is at stake in plain words, then the options, then a recommendation. Nothing here
blocks what has shipped; each was settled provisionally in `W3-ledger.md` ("Decisions taken on the researcher's
behalf") so the wave could finish.

1. **Which "how alike" score judges a group: σ² or eq. 17?** *Plainly:* both scores ask how much of a group's
   variation is one shared shape. Think of two bathroom scales: eq. 17 (the paper's SVD entropy) never reads below a
   certain weight even when the group is tidy, because noise props it up; σ² (the share of variation in the first
   shape) reads lower and moves more, but on its own lets an occasional pile of noise through. On W3-B's synthetic
   chains σ² caught three structured cases eq. 17 missed and never passed one eq. 17 failed; on the Library side, σ²
   against the quiet stretches let 1 pure-noise family in 52 through at the 0.9 margin. *Options:* (a) eq. 17 decides,
   σ² shown first (the Library now); (b) both must pass (cycle groups now — decision 18); (c) σ² decides, with its own
   margin measured on noise families first. *Recommendation:* keep (b) for cycle groups and (a) for families; measure a
   σ² margin before ever choosing (c).
2. **What is a sharkfin's "floor"?** *Plainly:* on rec 2 your labelled sharkfins drop 50–78 mV, recover half of that
   within ~40 s, and then sit a little below where they started (2–15 % of the drop's depth), drifting slowly lower
   until the next drop. Cycle shapes measures "floor" as time spent in the bottom quarter of each cycle's range, which
   is the bottom of the drop itself — so it reports rec 2's sharkfins as recovering almost at once (floor fraction
   0.02–0.03) and cannot see the plateau you describe. *Options:* (a) a plateau measure: the share of the cycle spent
   between, say, 2 % and 20 % of the depth below the pre-drop level, with its drift slope; (b) time until the trace is
   back within a few per cent of its starting level; (c) leave it to Deconvolution's residual. *Recommendation:* (a)
   with (b) beside it, as a small follow-up to cycle shapes — once you confirm the description above is what you mean.
3. **One shape per chain, or two?** *Plainly:* stacking whole cycles found one kind of cycle on each of the three long
   chains; wave 2's families, which looked at 10-minute windows, found a large and a small family on rec 6 (53, 13)
   and rec 542 (131, 11). The cycle view averages a whole cycle, and its split test gives up power when a minority is
   ≤ 20 % at 30 % noise, so a rare second kind is not ruled out. *Options:* (a) accept one shape per chain; (b) look at
   the cycle-stack picture on rec 6 and rec 542 first; (c) make the split test less strict (more false splits).
   *Recommendation:* (b) — it costs a look, and the picture is built for it.
4. **A family passes on either noise test.** *Plainly:* a family is called real if it is tighter than fake families
   made from either (i) the recording's own quiet stretches or (ii) scrambled copies that keep the slow trend. Each
   fake has a blind spot, on opposite sides (ii misses smooth shapes; i misses sharp families on recordings whose
   "quiet" stretches still hold uncatalogued events), so requiring both would fail real families for the tests' own
   faults. *Options:* (a) either (now); (b) both; (c) quiet stretches only. *Recommendation:* (a). Note what (b) would
   change: rec 542's 131-member family passes on the trend-kept test only.
5. **MPdist's share, 0.25 instead of the paper's 0.05.** *Plainly:* MPdist compares two shapes piece by piece and
   then reads one of the better piece-matches as the distance; the paper reads one near the very best 5 %, which is
   forgiving — two shapes sharing a single small piece look alike. 0.25 reads further down the list. *Options:*
   0.05 (the paper), 0.25 (now), a setting. *Recommendation:* keep 0.25 (it cut drop/square confusion from 20–63 % to
   3–33 % without hurting the shifted-start case).
6. **Multiscale entropy: 72 h windows and the AAFT null.** *Plainly:* the complexity curve needs long windows to
   reach long blur levels — 72 h reaches about 4 minutes, 24 h about 50 s; a recording shorter than the window is
   refused in words. And when you run the paired null for it, choose **AAFT** in Settings › Nulls: plain scrambling
   makes any lopsided signal look complex. *Options:* keep 72 h; default 24 h. *Recommendation:* keep 72 h (four times
   the power on weak structure), set `window_s` down for short recordings as the description says.
7. **Comparing organisms.** *Plainly:* the four Adamatzky species separate on their complexity curves, but most of
   that separation is in their noise colour already, and M2_aug was recorded on another setup (another logger, stored
   in V), so "M2_aug against the species" mixes the organism with the instrument. *Options:* compare within one setup
   only; record a known species on the M2 setup to anchor it. *Recommendation:* within one setup, and treat the M2-vs-
   species difference as uninterpretable until anchored.
8. **Cycle shapes' own gates.** *Plainly:* W3-B added two rules beyond the paper — a group split must show two humps
   along its own direction (the paper's test alone split pure noise every time), and a verdict must be beyond every
   draw *and* 3 spreads below the draws' typical value (the Library's 0.9 margin failed clean chains). *Options:*
   accept or veto each. *Recommendation:* accept both; they are what stopped the block inventing shapes in noise.
9. **The pan picture's band.** *(pending its evaluation.)*
