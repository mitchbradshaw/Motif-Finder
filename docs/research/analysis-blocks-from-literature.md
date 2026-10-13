# Analysis blocks from the literature — research and implementation plan

**Date:** 2026-10-13 · **Status:** research done; **plan confirmed 2026-10-13 (§8); wave 1 being built** from
`docs/prompts/blocks/`.
**Method:** `research` skill — primary sources only. The per-paper verification of formulas, defaults and the
installed implementations is in the companion file [`analysis-blocks-primary-sources.md`](analysis-blocks-primary-sources.md);
this file is the evaluation (does it suit mycelium recordings?) and the mapping onto the seven block types.

## In plain words

The Analyse page builds an analysis like a production line. Each station (a *block*) takes one kind of thing in and
hands one kind of thing on, and there are only seven kinds of thing: a **signal**, a **score** per sample, a set of
time **spans**, a set of **windows**, an **encoding** (an image or a string of letters), a **grouping**, and a
**model**. The Dehshibi spike detector became three stations in a row. This review looked for more published
algorithms that could become stations — spike, trough and sequence detectors, ways of clustering and categorising,
and one or two built on the matrix profile — and checked each against what our recordings are actually like: slow
(1 Hz), events lasting minutes to hours, strong drift, sharkfin and trough shapes, few events per day.

What came out:

- **Your three papers.** *Multiscale entropy* — **accept**, as a fingerprint for comparing recordings, species and
  conditions (it is not an event detector). *Iterative warping and clustering (WSF)* — **accept the second half**
  (line the events up, sort them into shape families, score how alike each family is) and **replace the first half**,
  which assumes a steady rhythm our recordings rarely have. *The √t-warped transform* — **reject**: its clock is tied
  to the moment the recording started, its comparison with the STFT was not like for like, and its machine-learning
  results are empty. One useful piece is salvaged (a spike-regularity number called LV).
- **Eleven further papers recommended.** The strongest three: **deconvolution**, borrowed from calcium imaging, which
  reads each drop as a jump followed by a slow recovery — the shape of a trough, and the reading of a sharkfin you
  settled in Q26d — and can pull apart events that start before the previous one has recovered; **wavelet ridge
  lines**, which find spikes and troughs at every duration at once and ignore slow drift without a detrend window;
  and **BEADS**, which separates drift from events, the problem behind the detrend-window and drifting-motif findings.
- **Matrix profile:** **FLUSS** (where does the recording change behaviour?) and **snippets** (what are the two to
  four typical behaviours, and where does each dominate?). Both ship in the installed `stumpy`, and both give the
  site a kind of answer it cannot give today. The pan matrix profile (every window length at once) is a useful third.
- **No new dependency, no eighth type, no new page.** Everything either comes with installed libraries (`stumpy`
  1.14.1, `scikit-learn` 1.7.2, `tslearn` 0.8.1 / `aeon` 1.4.0) or is a short numpy port. Most new blocks draw with
  views that already exist.
- **Three waves** (§7). Wave 1 is seven detection blocks that need no UI work. **Five decisions are yours (§8).**

---

## 1. How each paper was judged

Six questions, in order of weight:

1. **Does its core assumption hold for our recordings?** (§2 lists the facts it is checked against.) An algorithm
   built for a steady heartbeat, for 30 kHz neurons or for one-sided chromatogram peaks is not disqualified — the
   Dehshibi port shows translation works — but the assumption that breaks has to be named and handled.
2. **Does it add something the site lacks?** Checked against the 42 registered blocks (`Adapters.registry.list_adapters()`,
   2026-10-13) and the Library's grouping methods (`Working/library/grouping/methods/`: `ward`, `feature_bins`,
   `labels`).
3. **Does it fit the seven types** (`Working/types/`) without an eighth? (A method that fits none is out of scope —
   `docs/T09-detection-entropy-decision.md`.)
4. **What does it cost on this machine?** O(n) runs on a 721-hour channel in seconds; the matrix-profile family is
   O(n²) and a whole M2_aug channel is ~260 h locally, so those blocks are span-limited or go to SLURM.
5. **Which research question does it serve** (`docs/rq_roundA/`, `docs/rq_roundB/README.md`)?
6. **How good is the evidence in the paper itself?** Peer review, a reference implementation, results that can be
   checked.

## 2. The facts about our recordings that decide fit

| Fact | Value | Source |
|---|---|---|
| Sampling rate | 1 Hz typical (M2, Mushroom_260720, Adamatzky four species); 10 Hz (reishi_10hz, L_LM_Jul_26_J, provisional); 0.8 Hz (Dwij mfs2) | `recordings.fs`; `scripts/derive_adamatzky_four_species.py`, `scripts/derive_dwij_mfs2.py` |
| Length | 4 h (rec 385) to 721 h (M2_aug: 2,595,600 samples per channel, 16 channels) | `recordings` |
| Morphology vocabulary | sharkfin 17 / 37 catalogue rows; halfdome, crestedwave, furrycaterpillar, ridge, singletons | `DATA/catalogue/signal_catalog.xlsx` |
| Sharkfin | a drop, a floor (plateau) for ½–⅔ of the interval, then a slow climb; the climb is the **previous** event's recovery (decided, Q26d); 121 of 154 reach half recovery, median 199 s | `docs/prompts/fixup/future/N-event-extent.md`; `docs/rq_roundB/README.md` |
| Trough | a drop "mostly back by the quarter point" — a fast recovery | `docs/rq_roundB/README.md` |
| Event scales | 1–21 h spikes across species (Adamatzky 2022); in *S. commune* three families of ~24 s, ~8 min and ~43 min (the abstract rounds them to half a minute, 10 min and hours), **the two slower ones found by hand**; ~80 % of recordings irregular wideband activity, the fast spikes in occasional trains of ~6 (Adamatzky et al. 2023) | [S1], [S2] |
| Amplitudes | 0.03–2.1 mV across species [S1]; rec 385 has a ~7–14 mV regime and a ~0.4–0.6 mV regime | [S1]; the rec 385 motif-report analysis (2026-08; its code is not on `main`) |
| Rates | median inter-occurrence ~900–1,400 s in rec 385's families; tens to hundreds of events per channel-day | the same rec 385 analysis |
| Drift | strong; the detrend window has been shorter than the recovery on two families; on drifting channels the top matrix-profile motifs are ramps (a linear-residual guard rejected 13 of 15 M2_concat seeds) | `N-event-extent.md`; the 2026-08 motif-report analysis |
| Human labels | `interesting` annotations on M2_aug (recordings 1–16); Library 3,603 entries, 149 families at cut 0.60, almost no verified members | `docs/LIBRARY_STORAGE.md` §6.3; `docs/rq_roundB/README.md` |
| Detector baseline | Dehshibi template: faithful to the authors' code but unselective — hits 91 % of *interesting* vs 86 % of *not interesting* windows on M2_aug CH0 | Q34; `dehshibi_authors.py` notes |

The single most useful sentence from the fungal literature: the activity is *"highly variable compared to neural
activity"* [S3], and the in-field papers mostly detect spikes with a threshold on a moving-average baseline and group
them with a fixed gap [S1][S4] — with key parameters often unstated [S4]. **The well-specified algorithms come from
neuroscience, calcium imaging, chromatography and time-series data mining**, and two families of method — multiscale
entropy and the matrix profile — have, as far as this search found, **never been published on fungal recordings**.

---

## 3. Verdicts at a glance

`*` existing block · `†` new block · **W1/W2/W3** = wave (§7).

| # | Paper | Kind | Verdict | Chain (types) | Serves | Wave |
|---|---|---|---|---|---|---|
| A1 | Costa, Goldberger & Peng 2005 — multiscale entropy | categorise | **Accept, adapted** | Signal → Sliding windows* → WindowSet → **Multiscale entropy†** → WindowSet → Cluster* / Classifier* | round B *conditions and organisms*; tests the √t paper's complexity claim | W3 |
| A2 | Colominas & Wu 2023 — iterative warping & clustering (WSF) | cluster / sequence | **Accept the back half; replace the front** | SpanSet (a train) → **Cycle shapes†** → SpanSet (+ `group`) → Intervals*; and SVD-entropy coherence per Library family | round B *motif trains*; spiking families | W3 (coherence score: W2) |
| A3 | Knowles 2025 — √t-warped transform | encode | **Reject** (salvage LV, CV2) | — (LV and CV2 join Intervals*) | — | W1 (LV) |
| 1 | Friedrich, Zhou & Paninski 2017 — OASIS deconvolution | spike / trough detection | **Accept** (troughs first) | Signal → **BEADS†** or Detrend* → Signal → **Deconvolve†** → Scores → **Impulse events†** → SpanSet → Event shape* → Intervals* | RQ5, round B *sharkfin plateau*, *recovery*, Q26 | W1 |
| 2 | Du, Kibbe & Lin 2006 — CWT ridge lines | spike / trough detection | **Accept** | Signal → **CWT ridges†** → SpanSet (+ `best_scale_s`) → Event shape* → Intervals* | RQ3 (each event's own scale), RQ4, Adamatzky's three scales | W1 |
| 3 | Ning, Selesnick & Duval 2014 — BEADS | baseline / trough detection | **Accept** | Signal → **BEADS†** → Signal (drift removed) → any detector | every detector; motif drift; Q26 recovery vs drift | W1 |
| 4 | Quian Quiroga, Nadasdy & Ben-Shaul 2004 — Wave_clus | spike detection + sorting | **Accept the detector; adapt the sorter** | Signal → Detrend* → **Noise threshold†** → SpanSet; sorting = rows 7–8 | friction (no volts/mV cut to type); RQ5 | W1 (detector) |
| 5 | Pasquale, Martinoia & Chiappalone 2010 — logISI bursts (+ Cotterill et al. 2016 benchmark, Adamatzky 2022 words) | sequence detection | **Accept** | SpanSet → **Trains†** → SpanSet (+ `train_id`, …) → Intervals* | round B *motif trains*; Library "spike trains: defined, not populated" | W1 |
| 6 | Gharghabi et al. 2017 — FLUSS (matrix profile) | segmentation | **Accept** | Signal → Detrend*/BEADS† → Signal → **FLUSS†** → Scores (regime-change score) → Threshold* → SpanSet (boundaries) | round B *conditions*; long multi-day recordings | W1 |
| 7 | Paparrizos & Gravano 2015 — k-Shape | cluster | **Accept** | SpanSet → **Event windows†** → WindowSet → **Shape families†** (method `kshape`) → Grouping; and Library method `kshape` | spiking families; RQ1 new scope; RQ3 | W2 |
| 8 | Campello, Moulavi & Sander 2013 — HDBSCAN | cluster | **Accept** | as row 7 with method `hdbscan`; Library method `hdbscan` | RQ1 *cluster the unlabelled pool*; families with an honest "no family" | W2 |
| 9 | Dempster, Schmidt & Webb 2021 — MiniRocket | categorise | **Accept** | WindowSet → **MiniRocket†** → WindowSet → Manual labels* / Cluster* → Grouping → Classifier* → Model | RQ1; round B *CNN on Library motifs* (a cheap baseline first) | W2 |
| 10 | Imani et al. 2018 / 2020 — snippets (matrix profile) | categorise | **Accept** | Signal → Sliding windows* (gap 0) → WindowSet → **Snippets†** → Grouping | overview of a recording; picking spans to study | W2 |
| 11 | Madrid et al. 2019 — pan matrix profile | motif utility | **Accept as optional** | Signal → **Pan matrix profile†** → Encoding (lengths × time) → Wavelet summation* → Scores | picking the matrix-profile window (the 1- vs 3- vs 10-min finding) | W3 |
| — | Zhu et al. 2017 chains; Lu et al. 2022 DAMP; Gharghabi et al. 2018 MPdist; Mukhopadhyay & Ray 1998 NEO; Scholkmann et al. 2012 AMPD; Adams & MacKay 2007 BOCPD; Fukasawa et al. 2024 transfer entropy | — | **Considered, not planned** (§6) | — | — | — |

---

## 4. Your three papers

### A1. Multiscale entropy — Costa, Goldberger & Peng 2005, *Phys. Rev. E* 71:021906 — **accept, adapted**

**In plain words.** Entropy asks "how surprising is the next value?". Pure noise is maximally surprising and a metronome
not at all, yet neither is *complex*. MSE blurs the signal more and more (averaging 2, 3, … 20 points at a time) and
measures the surprise at every blur level. Noise loses its surprise as you blur it; a signal with structure at many
time-scales keeps it. The shape of the curve — not one number — is the fingerprint.

**The algorithm.** Coarse-grain by non-overlapping means at scale τ (eq. 16); compute sample entropy on each coarse
series with m = 2 and r = 0.15 × the SD of the *original* series, r held fixed across scales; read the curve. The
paper's own summary features are the slopes over scales 1–5 and 6–20 (its Fig. 8). It used ~2 × 10⁴ points so the
coarsest series kept 10³ (§VI).

**Fit to our recordings.**
- *For:* a scale-aware complexity measure is exactly what the site lacks — `preprocessing.window_matrix` already
  computes sample entropy (`Working/Detection/analysis/entropy_analysis.py:163`), but at one scale only. The fungal
  literature uses compression measures on a binarised spike string [S1][S5]; no published MSE on fungi was found.
- *Against:* MSE needs long series. At 1 Hz, τ = 20 with 750 points per coarse series is 15,000 samples ≈ 4 h, so it
  describes **recordings, conditions and species — not events**. Second, the paper itself warns (App. B) that
  outliers and nonstationarity inflate the SD, so r grows and entropy collapses; and that *removing* trends alters
  multi-scale structure too. On drifting fungal channels that is a real dilemma, and very likely why the √t preprint
  reports "mean MSE 0.0028".
- *Adaptation:* use **refined composite MSE** (Wu et al. 2014, *Phys. Lett. A* 378:1369 — fewer undefined values on
  short series); set scales **in seconds** (e.g. 1 s → 20 min at 1 Hz, geometric); take r from a **robust SD**
  (median absolute deviation) of the detrended window, with the plain SD as an option; and **grey every scale whose
  coarse series is too short**, saying so on the card (an absence is never hidden).

**Chain.** `Signal ─Detrend*→ Signal ─Sliding windows* (e.g. 6 h, gap 0)→ WindowSet ─Multiscale entropy†→ WindowSet
(+ rcmse_τ per scale, complexity index, small- and large-scale slopes) ─Cluster* / Classifier* / Compare`. One window
covering the whole span gives the recording's single curve.

**Serves:** round B *conditions and organisms* (Adamatzky four-species data are 1 Hz and already derived), and a
direct, falsifiable check of the √t paper's "very low complexity" claim. **Cost:** sample entropy is O(N²) per scale
naively — numba, or the standard sorted-template trick. **Effort:** M.

### A2. Iterative warping and clustering — Colominas & Wu 2023, *IEEE TSP* 71:701–712 — **accept the back half, replace the front**

**In plain words.** Picture a drummer whose tempo drifts. To compare one beat with another you first stretch every
beat to the same length, then stack them and sort them into piles of "the same beat". The paper does this for
heartbeats and voices: it finds the rhythm, stretches each cycle to unit length, keeps re-stretching until the stack
is as tidy as it gets (measured by **SVD entropy** — low when every row is a copy of a few patterns), lines the
cycles up, and clusters them. A jump from one pile to another is a change point.

**The algorithm (Alg. 1).** STFT → ridge → instantaneous frequency and amplitude of a dominant harmonic ℓ chosen
beforehand (ℓ = 2 for their ECG) → phase →
warp (non-uniform resampling so each cycle has unit length) and demodulate → repeat while SVD entropy falls → cut into
cycles (a P × L matrix) → align by cyclic shift (graph connection Laplacian synchronisation) → k-means, 50 replicates,
K by Calinski–Harabasz → each waveform as the cluster median or a trigonometric regression on it.

**Fit to our recordings.**
- *The front half does not fit.* It assumes one continuous oscillation with a slowly varying, dominant harmonic
  (assumptions T1–T4; the authors state the single-component limit in §VI). Our recordings are mostly irregular
  wideband activity with **occasional** trains (~20 % of *S. commune* recordings [S2]); an STFT ridge on them tracks
  drift and noise, not a rhythm.
- *The back half fits well, with one change.* For a train our detectors have already found, the phase can be taken
  from the **event times themselves** — each inter-event interval is one cycle (φ runs from k to k + 1 between events
  k and k + 1). That keeps the paper's warp → stack → SVD-entropy → align → cluster → change-point machinery and drops
  only the STFT ridge. Alignment should use zero-padded cross-correlation (as k-Shape does, row 7) rather than cyclic
  shifts, because a fungal cycle does not wrap around.
- *SVD entropy is useful on its own.* On a family's member matrix it is a **shape-coherence score**: low when members
  are scaled copies of one shape, high when the family is a mixture. That complements the supervisor's
  amplitude-stereotypy finding (some families have peak-to-peak SD ~0.15 mV, others 1.6–3.1 mV), because SVD entropy
  ignores amplitude and amplitude CV ignores shape.
- *One conflict with the site's standard:* the paper's family waveform is a **median**; the drawing standard draws a
  **member, never an average** (`docs/BLOCK_INTEGRATION.md` §2, `serialize.py::_exemplars`). The plan keeps the
  standard: the median, if computed at all, stays a number in `meta`, not a drawn waveform.

**Chain.** `SpanSet (a detector) ─Trains†→ SpanSet ─Cycle shapes†→ SpanSet (+ group = cycle-shape cluster,
cycle_change, the train's SVD entropy before and after re-alignment) ─Intervals*` (per cycle-shape group). And
`svd_entropy` as one more number per family on the Library's Family page (W2, small).

**Serves:** round B *motif trains — do slopes within a train change in order?*; spiking families. **Effort:** M–L;
**exploratory** — build after Trains shows how many regular trains exist. Reference code: MATLAB,
github.com/macolominas/WarpingWSF — it carries **no licence**, so the block is written from the paper, not ported.

### A3. √t-warped wave transform — Knowles 2025, bioRxiv 10.1101/2025.08.31.673362 — **reject**

**In plain words.** The transform measures time on a clock that runs fast at first and ever slower afterwards, always
counted from the moment the recording started. So the same spike is analysed with a short window if it happens in hour
1 and a ten-times-longer one if it happens in hour 100. For a recording of a living network that has been growing for
days before the electrodes went in — let alone our concatenated M2 sets, where "the start" is where one file was
joined to another — that start time means nothing.

**Why rejected** (all from the preprint itself):
1. **The warp is anchored to t = 0.** Eq. (1) windows √t − u₀; the paper's own matching rule σ_t = 2u₀τ makes the
   effective window grow with √(time since start). The result depends on where the span begins.
2. **The comparison with the STFT is not like for like.** Table 1: √t without detrending scores 0.0525 concentration,
   with detrending 0.7873, the STFT 0.0273 — and no detrended STFT is reported. Detrending, not the warp, does almost
   all the work; Fig. S1's STFT is a single spike at zero frequency, i.e. undetrended drift. On SNR the STFT "wins" by
   a factor of ~10⁵, which the paper sets aside.
3. **The machine-learning results are empty.** The published confusion matrix (Fig. 2A) holds one class
   (*S. commune*, 35); the feature-importance panel is blank; the calibration panel shows only the ideal diagonal.
4. **Numbers that cannot be right:** "fractal dimension −0.0000", a Lyapunov exponent from about ten spikes, mean MSE
   0.0028, and "species-specific sampling rates" (5 Hz for *Cordyceps*, 2 Hz for *Pleurotus*) applied to a dataset
   recorded at 1 Hz — the Zenodo record (5790768, the same data as our `DATA/raw` four-species set) says "one sample
   per second", and so does the preprint's own abstract — with a claimed 20–500 % gain over 1 Hz. It also lists
   *Pleurotus* and eleven *S. commune* files that the four-file Zenodo record does not contain.
5. **Its spike detector is the site's existing one:** moving-average baseline, absolute threshold 0.05–0.2 mV,
   refractory 120–300 s — i.e. `Detrend → Signal threshold`. Fig. 1B's spikes sit mostly on the electrode-settling
   transient of the first ~30,000 s.
6. Single author holding every CRediT role; not peer reviewed; v1 only, and no public review (0 on PREreview).

**Salvaged:** its list of spike-train statistics points at two sound, standard measures the Intervals block lacks —
**LV** (local variation; Shinomoto, Shima & Tanji 2003, *Neural Comput.* 15:2823) and the local **CV2** (Holt, Softky,
Koch & Douglas 1996, *J. Neurophysiol.* 75:1806) — added to `interrogation.intervals` per group (W1, small). Both are
close to 1 for random (Poisson) timing and 0 for clockwork, and unlike CV they are not fooled by a slowly changing
rate. (The preprint's own "CV²" is the squared CV, which adds nothing to the CV the block already reports;
*corrected 2026-10-13, before the build*.)

---

## 5. The new papers

Each section: what it is in plain words, the algorithm, why it fits or where it breaks, the chain, parameters in our
units, cost, how we would know it works, what it serves.

### 1. OASIS deconvolution — Friedrich, Zhou & Paninski 2017, *PLoS Comput. Biol.* 13(3):e1005423 — **accept (troughs first)**

**In plain words.** In calcium imaging every neuron firing makes the light jump up and then fade slowly. When firings
come close together the fades overlap and a simple threshold sees one blob. Deconvolution works backwards: "what list
of sudden jumps, each followed by the same slow fade, best explains this trace?". The answer is one number per sample —
how big a jump happened there — mostly zero.

**The algorithm.** y_t = b + c_t + noise, c_t = γ c_{t−1} + s_t with s_t ≥ 0 and sparse (AR(1); AR(2) gives a finite
rise). Solved by an active-set generalisation of pool-adjacent-violators in O(T), online; γ from the autocovariance or
given; a thresholded variant forces every non-zero jump to be at least s_min.

**Fit to our recordings — strong for troughs, partial for sharkfins.**
- A fungal **drop with an exponential-like recovery is exactly this kernel upside-down**: a sudden jump, then a fade.
  Flip the sign and a trough is a calcium transient.
- It **encodes the reading you chose in Q26d** — the slow climb belongs to the *previous* event — because the fade is
  part of the event that caused it, and the next jump is a new event even if the fade has not finished.
- It is built for the case a threshold gets wrong: events that start before the previous one has recovered. In
  Q26's measurement, 33 of 154 sharkfins had not reached half recovery when the next drop began — the overlap case.
- **Where it breaks:** a sharkfin's floor *plateaus* for half to two-thirds of the interval before climbing; an AR
  kernel recovers fastest first. So the honest plan is **troughs first**, then measure how badly the kernel fits
  sharkfins — the fit residual is itself a plateau measure (round B *the sharkfin plateau*).
- Drift must go first (BEADS or a long detrend): OASIS's baseline b is one constant per span.

**Chain (template `deconvolved_troughs`).**
`Signal ─BEADS† (or Detrend*, window ≫ the recovery)→ Signal ─Deconvolve†→ Scores (jump size per sample, mV)
─Impulse events†→ SpanSet ─Event shape*→ SpanSet ─Intervals*→ SpanSet`

| New block | Types | Parameters (our units) | Why a block of its own |
|---|---|---|---|
| `detection.deconvolve` | Signal → Scores | `polarity` drop/spike; `recovery_half_s` (0 = estimate γ from the data); `fall_s` (0 = AR(1), else AR(2)); `min_jump` (s_min, signal units) | the deconvolved jumps drawn under the trace (the existing `signal->scores` view) are the evidence |
| `detection.impulse_events` | Scores → SpanSet | `threshold` (jump size — **draggable** on the curve by the existing convention); `extent` = to the next jump / until x recovers by a fraction, capped | any impulse-like score (this, NEO, a derivative) needs one span per impulse with a sensible extent; `detection.threshold` would give 1-sample spans. Emits `meta["events"]` with `onset_idx`, so the slideshow counts falls per window |

**Cost:** O(n); a 2.6 M-sample channel in seconds. **How we'd know:** synthetic overlapping troughs with known onsets
(test-first); the port is written from the paper — the authors' code (github.com/j-friedrich/OASIS) is GPL-3.0, so
nothing is copied — and checked against a fixture made by running the authors' MATLAB with the local MATLAB R2025b, as
the Dehshibi blocks were; on M2_aug, beats the surrogate null and is more selective on *interesting* vs *not
interesting* windows than `drop_detection_v1` (§7.3). The paper itself says drifting baselines are not handled, which
is why BEADS or a long detrend comes first. **Serves:** RQ5, round B *sharkfin plateau* and *recovery*, Q26.
**Effort:** M.

### 2. CWT ridge-line peaks — Du, Kibbe & Lin 2006, *Bioinformatics* 22(17):2059–2065 — **accept**

**In plain words.** Slide a "Mexican hat" template along the trace, at many sizes from a few seconds to hours. A real
spike lights up the template at a whole run of neighbouring sizes; noise lights it up only at the smallest sizes.
Join the bright points across sizes into ridge lines and keep the long, strong ridges. The size at which a ridge is
brightest is the event's own duration.

**The algorithm.** Continuous wavelet transform with the Mexican hat over a range of scales; local maxima per scale
linked across scales into ridges; a peak needs a long enough ridge and an SNR above a cut, noise being a percentile of
the smallest-scale coefficients in a local window; **no smoothing or baseline correction beforehand** — the Mexican
hat has zero mean and zero first moment, so constant and linear drift cancel locally. The installed
`scipy.signal.find_peaks_cwt` is **not** a faithful implementation — its noise is the 10th percentile of *signed*
smallest-scale coefficients (the paper: 95th percentile of absolute values) and its SNR uses the smallest-scale
coefficient (the paper: the ridge maximum) — so the block writes the paper's ridge, SNR and width steps itself
(companion file §7).

**Fit to our recordings — strong.**
- **Multi-scale by construction.** Events from half a minute to hours [S1][S2] in one pass, each with its own scale —
  where the site today picks one window (1, 3 or 10 min) per run.
- **Drift-immune without a detrend window** — the window that has been wrong on two families (`N-event-extent.md`).
- **Troughs as well as spikes**: the hat is symmetric, so a trough is a negative ridge (`polarity`).
- **Where it breaks:** the hat is symmetric and a sharkfin is not, so the ridge's centre sits toward the slow side.
  Use it to *find* events and their scale; let Event shape* time the onset. Nested events (a fast spike on a slow one)
  give two ridges at two scales — informative, but needs a rule.

**Chain (template `cwt_events`).** `Signal ─CWT ridges†→ SpanSet (+ best_scale_s, ridge_scales, snr per event)
─Event shape*→ SpanSet ─Intervals*→ SpanSet`. **One block, not two:** an Encoding carries no axis and a block cannot
read the previous block's `meta` (`BLOCK_INTEGRATION.md` §6), so a separate ridge block could not know which width each
row is without a parameter repeated in two places. The scalogram and ridges travel in `meta` for an optional drawing
(W2/W3 UI). **Parameters:** `min_scale_s` (10), `max_scale_s` (7,200), `n_scales` (~40, geometric), `polarity`,
`min_snr`, `min_ridge_scales`. **Cost:** O(n log n × scales); the wavelet-transform block's 320,000-sample memory cap
carries over. **Serves:** RQ3 (each event's own scale, not a chosen window); RQ4; a direct test of the three-scale
claim [S2] — does `best_scale_s` cluster near 24 s, 8 min and 43 min? Two of those families were found by eye; this is
the automatic version. **Effort:** M.

### 3. BEADS — Ning, Selesnick & Duval 2014, *Chemometr. Intell. Lab. Syst.* 139:156–167 — **accept**

**In plain words.** Split the trace into three layers: a slow baseline, a sparse layer of events (mostly zero, with
mostly-zero slopes), and noise — and let each layer explain only what it is good at. A rolling mean cannot do this:
near a big drop it is dragged down by the drop itself and leaves a fake overshoot.

**The algorithm.** y = f + x + w; f low-pass; x sparse with sparse first and second differences; an **asymmetric**
penalty (ratio r) so events can be one-sided; a convex cost solved by majorisation–minimisation with banded systems,
O(N) per iteration. Parameters: the baseline cut-off fc (the one that matters most), filter order d, r, λ₀–λ₂.

**Fit to our recordings — strong, with one honest limit.** It attacks three standing findings: drifting channels whose
top motifs are ramps; detrend windows shorter than the recovery; and Q26's "separating recovery from slow baseline
drift is the first real task". With r set for drops it is also a **trough detector** (x is the trough layer). **The
limit:** no baseline method can split an event from drift that has the same time-scale — fungal events reach hours
[S1] — so `baseline_period_s` must sit above the events you care about, and the block should say so.

**Chain.** `Signal ─BEADS†→ Signal (y − f)` in front of any detector; optionally a second face
`detection.beads_events` (Signal → Scores, the sparse layer x) → Threshold* → SpanSet. **Parameters:**
`baseline_period_s` (→ fc), `polarity` (drop / spike / both → r), `sparsity` (λ₀; λ₁, λ₂ scaled from it).
**Cost:** O(N × iterations); whole channels. **Serves:** every detector; RQ2 and RQ3 matrix-profile motifs; Q26.
**Effort:** M — a port of Laurent Duval's BSD-3 MATLAB (the code pybaselines adapted). Two practicalities from the
implementations: the trace must be near zero at both ends (subtract a fitted parabola first, as pybaselines does), and
small changes of λ₁ are known to destabilise it, so λ₁ and λ₂ are derived from one `sparsity` setting rather than
exposed.

### 4. Wave_clus — Quian Quiroga, Nadasdy & Ben-Shaul 2004, *Neural Comput.* 16(8):1661–1687 — **accept the detector, adapt the sorter**

**In plain words.** To set a spike threshold you need the noise level, but spikes make the ordinary SD too big. The
median of the absolute signal hardly notices a few spikes, so σ_noise = median(|x|) / 0.6745 is the noise level as if
there were no spikes; cut at 4 × that.

**Fit.** The site's `detection.signal_threshold` cuts at an **absolute** level in the signal's stored units (−0.005 V
as shipped for M2), which must be re-typed per dataset and whose units needed their own fix (commit c92a151). A
**noise-relative** cut is unit-free and adapts per channel — amplitudes span 0.03–2.1 mV across species [S1]. It
assumes events are a small fraction of samples; where a channel is mostly events, it over-estimates the noise (the card
should print the σ it used). The sorting half (Haar coefficients of each spike, a normality test to keep the most
multimodal ones, superparamagnetic clustering) is adapted: superparamagnetic clustering is not installed and is a
heavy Monte-Carlo method, so the density-based **HDBSCAN** (row 8) takes its place, and the per-spike window (64 samples
at 24 kHz in the paper — 64 s at our 1 Hz) is taken from the events' own durations. Wave_clus's code is licensed for
non-commercial use only; only the published equations are reused.

**Chain.** Detector: `Signal ─Detrend* / BEADS†→ Signal ─Noise threshold†→ SpanSet` (`k_sigma` 4, `direction`;
the computed cut in mV printed). Sorter (W3, optional): `SpanSet ─Event windows†→ WindowSet ─Wavelet features†→
WindowSet ─Shape families† (hdbscan)→ Grouping`. **Recommendation:** a new block rather than a mode on
`signal_threshold`, so that block's draggable absolute cut and its recipe hashes stay as they are. **Effort:** S.

### 5. logISI bursts — Pasquale, Martinoia & Chiappalone 2010, *J. Comput. Neurosci.* 29:213–229; with Cotterill et al. 2016, *J. Neurophysiol.* 116:306–321, and Adamatzky 2022, *R. Soc. Open Sci.* 9:211926 — **accept**

**In plain words.** If spikes come in trains, the gaps between them are of two kinds — short gaps inside a train and
long gaps between trains — and a histogram of gaps (on a log scale) has two humps. logISI finds the valley between the
humps and uses it as the cut: gaps shorter than the valley join spikes into one train. If there is only one hump, it
says so — no trains — rather than inventing some.

**Why this paper.** Cotterill et al. benchmarked eight burst detectors. MaxInterval is their "recommendation for a
first choice" and logISI "a high-performing alternative" that tends to underestimate burst durations. But MaxInterval
needs five thresholds fixed in advance — in milliseconds, for neurons — and nobody knows the fungal values, whereas
logISI **sets its cut from the data**. So logISI is the default rule here; MaxInterval is a rule option once the trains
logISI finds supply fungal values. Adamatzky 2022 grouped fungal spikes into "words" with a fixed cut (θ = the
species' mean inter-spike interval, or 2×) — a third rule, so the paper can be reproduced and the cuts compared.

**Fit.** The neuronal constants (the 100 ms ceiling on a within-train gap) have to become fungal ones — a parameter in
seconds, or relative to the median gap. With tens to hundreds of events the histogram is coarse, so a kernel density
on log-gaps replaces fixed bins, and the card states how many gaps it had. The site already has Adamatzky's
neighbourhood-average detector as `detection.spike_v1`; its defaults (w = 20, δ = 0.01, d = 30) are the 2023
*S. commune* fast-spike values, while the 2022 paper used per-species settings (w = 50–200, δ = 0.003–0.1, d = 100–300).
The word grouping is what is new. One caution from the artefact literature: a no-fungus control channel showed a
~0.005 Hz cycle (one every ~200 s; Buffi et al. 2025), so a strikingly regular train at that spacing should be checked
against another channel before it is believed.

**Chain (template `spike_trains`).** `SpanSet (any detector) ─Event shape*→ SpanSet ─Trains†→ SpanSet (+ train_id,
train_size, position_in_train; meta: the gap histogram, the cut found, the valley's depth, the word-length
distribution, Lempel–Ziv complexity of the word sequence — `compute_lempel_ziv_complexity` exists in
`dehshibi_detection_analysis.py:1205`) ─Intervals*→ SpanSet` with LV and CV2 (A3's salvage; LvR is left out — its
refractory constant, 5 ms, was fitted to cortex). Trains does not overwrite
an upstream `group` column; an option writes `group = train_id` when you want intervals *within* trains. **Serves:**
round B *motif trains* ("what populates a train?"); the Library's spike-train scale, "defined, not populated"
(`LIBRARY_STORAGE.md` §4). **Effort:** M.

### 6. FLUSS — Gharghabi et al. 2017, *ICDM*, pp. 117–126 (matrix profile VIII) — **accept**

**In plain words.** For every short stretch of the recording, the matrix profile knows which other stretch looks most
like it. Draw an arc from each stretch to its look-alike. Within one "regime" of behaviour the arcs stay inside it; at
a change of behaviour few arcs cross. Count crossing arcs at every point, correct for the fact that the middle always
gets more arcs than the ends, and the dips are the change points.

**The algorithm.** The arc curve from the matrix-profile index; the idealised arc curve is a parabola; CAC =
min(AC / IAC, 1), edges set to 1; regimes are the lowest minima with an exclusion zone; **one parameter**, the
subsequence length. `stumpy.fluss` (and the streaming `floss`) are installed.

**Fit.** It finds changes in the **repertoire of shapes**, which `detection.rupture` (PELT, mean/variance) cannot.
Useful for multi-day recordings (colonisation, drying, a stimulus, Faraday cage vs outside) and to pick spans worth
studying. **Where it breaks:** z-normalised drift ramps match anywhere, so arcs cross everywhere and the curve goes
flat — it fails safe (no boundaries) rather than inventing them, but needs Detrend*/BEADS† first.

**Chain (template `fluss_regimes`).** `Signal ─BEADS†/Detrend*→ Signal ─FLUSS†→ Scores (regime-change score = 1 −
CAC; 0 = no change) ─Threshold*→ SpanSet (one span per boundary zone, sent to Review as "is this a real change?")`.
Emitting 1 − CAC lets the **existing** `detection.threshold` cut it, with the cut draggable on the curve — one new
block, not two. **Parameters:** `window_s` (≈ one event; 60 s matches the 1-minute finding), `exclusion_factor`
(5). Two places where `stumpy.fluss` differs from the paper, to be set deliberately: it blanks 5·L at each end where
the paper blanks L, and it fits a beta curve where the paper uses the parabola (pass the parabola as `custom_iac`); and
it must be given the profile **index**, not the distances (its own docstring examples get this wrong). **Cost:** the
matrix profile's O(n²) — hours-long spans locally, days via SLURM; declare the estimate with the matrix-profile cost
model. **Effort:** S.

### 7. k-Shape — Paparrizos & Gravano 2015, *SIGMOD*, pp. 1855–1870 — **accept**

**In plain words.** Two copies of the same spike shape cut out a few seconds apart look different point by point.
k-Shape compares shapes after sliding one along the other to the best match (shift-invariant) and after scaling both
to the same size (amplitude-invariant), and builds each family's centre the same way.

**The algorithm.** Shape-based distance SBD = 1 − max over shifts of the coefficient-normalised cross-correlation,
computed with FFTs, zero-padded (not cyclic) shifts; centroid by shape extraction (leading eigenvector of a Rayleigh
quotient); k-means-style iterations. aeon 1.4's `KShape` implements it and z-normalises its inputs (tslearn's
`KShape.fit` does not; aeon's older `TimeSeriesKShape` is deprecated).

**Fit.** Our event extents are known to be off — 46 % of seed-store left edges are set by a cap, not the morphology
(`N-event-extent.md`) — so point-by-point Euclidean on stored snippets compares misaligned events. Shift-invariance is
the right medicine, and the same alignment the WSF paper (A2) adds by synchronisation. It needs K: choose it by the
WSF paper's Calinski–Harabasz rule or the site's existing best-silhouette rule.

**Chain.** Two surfaces, one implementation:
- **Library** (where the 3,603 events and 149 families live): a grouping method `kshape` in
  `Working/library/grouping/methods/` for the `shape-distance` basis, following `LIBRARY_STORAGE.md` §6.2, plus
  SVD-entropy coherence per family (A2).
- **Analyse:** `SpanSet ─Event windows†→ WindowSet ─Shape families† (method kshape | hdbscan | ward, from the Library
  registry)→ Grouping`, and a second face `interrogation.event_families` (SpanSet → SpanSet + `group`) so that
  `─Intervals*` gives **per-family timing in one linear chain** — the supervisor's spiking families as a template.

`catalogue.event_windows` (SpanSet → WindowSet) is the bridge that makes every window block — Cluster*, Classifier*,
Window images*, MiniRocket† — usable on **detected events** instead of a fixed grid; it carries Event shape's feature
table onto the windows, so `Cluster*` on amplitude / width / recovery works the day it lands. Its windows are
channel-absolute (it adds `t[0]·fs`). **Effort:** M–L for the family blocks (+ one serializer change so a block can
name its own exemplars — still a member, never an average), S for the bridge (+ one row in `views.py` and
`registry.tsx` for `spanset->windowset`).

### 8. HDBSCAN — Campello, Moulavi & Sander 2013, *PAKDD*, LNCS 7819:160–172 — **accept**

**In plain words.** Instead of "split everything into K piles", HDBSCAN finds the places where points crowd together
and leaves the stragglers out, labelled "no family". No K to choose.

**Fit.** k-means and Ward force every window or event into some family; the round-B CNN discussion already concluded
that forcing noise into a motif class is the main failure (it needs an explicit background class). HDBSCAN's noise
label is the clustering version of that background class. It maps exactly onto the Library's rule "return None for a
row you will not place … do not invent a catch-all family", and its `min_cluster_size` is the Library's existing
ten-member floor. `sklearn.cluster.HDBSCAN` is installed (works on a precomputed distance matrix too); besides −1 for
noise it uses −2 and −3 for rows with infinite or missing values, which become omissions with their own reason.

**Chain.** As row 7 (`method = hdbscan`), on waveforms, on Event shape features, or on any feature table (MiniRocket,
MSE): `WindowSet ─Shape families† (hdbscan)→ Grouping` and Library method `hdbscan`. **Serves:** RQ1's new scope
(*cluster the unlabelled pool, validate blind* — K unknown). **Effort:** S once row 7 exists.

### 9. MiniRocket — Dempster, Schmidt & Webb 2021, *KDD*, pp. 248–257 — **accept**

**In plain words.** Run every window through ten thousand tiny fixed pattern-detectors and record, for each, how often
it fires. Those counts are a fingerprint a simple classifier can learn from in seconds — on a CPU, no images, no GPU.

**The algorithm.** Fixed kernels of length 9 with weights in {−1, 2}, many dilations, biases from quantiles of the
convolution output, proportion-of-positive-values pooling → ~10,000 features; a ridge classifier (logistic regression
for very large sets). `aeon`'s `MiniRocket` is installed.

**Fit.** It answers "is this label learnable from the raw shape?" with a near state-of-the-art, cheap baseline —
before the round-B CNN is built, and without the Gramian images' 5,000-sample cap. **Where it breaks:** the features
are not interpretable; it categorises, it does not explain.

**Chain (template `minirocket_manual_labels`).** `Signal ─Sliding windows* / Window matrix* (or SpanSet ─Event windows†)
→ WindowSet ─MiniRocket†→ WindowSet (+ features) ─Manual labels*→ Grouping ─Classifier* (windows side input)→ Model`.
For pools, MiniRocket reads the vectors Trace shape* already saved (`shape_file`), so it never has to read the store.
aeon's MiniRocket refuses windows shorter than 9 samples (never an issue at our window lengths). Optional: a
`model = ridge` choice on `catalogue.classifier`, the paper's recommendation, which aeon's `MiniRocketClassifier`
already pairs with the transform. **Serves:** RQ1 (a stronger
arm than Catch22 + forest); round B *a model that sifts a whole dataset*. **Effort:** S–M.

### 10. Snippets — Imani, Madrid, Ding, Crouter & Keogh 2018, *ICBK*, pp. 382–389 (matrix profile XIII); *DMKD* 34(6):1713–1743 (2020) — **accept**

**In plain words.** Summarise a long recording with its two to four most typical pieces, and say where each one
dominates — like a few thumbnail frames that best represent a film, plus a bar showing which frame each scene most
resembles.

**The algorithm.** Cut the series into non-overlapping pieces of length m; for each, the MPdist profile against the
whole series; greedily choose k pieces whose combined minimum profile is lowest; report each snippet's coverage
fraction and the regime of every piece. `stumpy.snippets` is installed and returns snippets, fractions and regimes.

**Fit.** A new kind of answer — a categorisation of the recording itself — and directly useful to the researcher's
first question on a new recording, *where should I look?*. MPdist compares pieces by their shared sub-shapes, which the
paper says makes it robust to "linear trends … wandering baseline" — **but only if it is switched on**: `stumpy.snippets`
defaults to `percentage = 1.0`, which quietly turns MPdist into plain Euclidean distance. The block sets it below 1
(the paper's example used sub-length 70 of 200, i.e. 0.35). Detrending first stays the default.

**Chain.** `Signal ─Detrend*→ Signal ─Sliding windows* (window = m, gap 0)→ WindowSet ─Snippets†→ Grouping` — the
existing Grouping view draws regimes over time and cluster sizes; the exemplar of each regime is the snippet itself (a
real member window, via the same serializer change as row 7). **Parameters:** `snippet_s`, `k`. **Cost:** O(n²);
hours-long spans locally. **Effort:** S–M.

### 11. Pan matrix profile — Madrid et al. 2019, *ICBK*, pp. 175–182 (matrix profile XX) — **accept as optional**

**In plain words.** Instead of choosing one window length and hoping, compute the matrix profile at every length and
show it as a heat-map: lengths up the side, time along the bottom, dark where something repeats.

**Fit and limits.** It removes a guess the project has made by trial (1 minute beats 3 and 10 for spikes in rec 385).
It does **not** answer RQ3 by itself: two occurrences must have the same length to match, so "the same shape at two
durations" is still the seed search's scale bank. **Chain.** `Signal ─Detrend*→ Signal ─Pan matrix profile†→ Encoding
(a time-aligned image: rows = window lengths, long first, one column per sample; values flipped so bright = repeated)`
— the existing Encoding view *is* the paper's motif heat-map, and Wavelet summation* can sum a band of lengths into a
Scores. A `recommend` hook proposes `window_min` for `detection.matrix_profile`. **Cost:** O(n² × lengths), anytime
(`stumpy.stimp` with a percentage). stumpy scales each length by 1/(2√m) — the paper gives no rule — and its `PAN_` is
**binarised** by default, so the block reads `pan(contrast=False, binary=False)` to keep distances. **Effort:** M.

---

## 6. Considered, not planned (one line each)

- **Time-series chains** (Zhu et al. 2017, *ICDM*): motifs that drift in a direction over time — a real question
  (do spike shapes evolve as the colony grows?) but niche until families are verified. `stumpy.allc` is installed;
  easy to add later.
- **DAMP** (Lu et al. 2022, *KDD*): exact *left* discords — "the most novel thing so far" — fast enough for whole
  721-hour channels. Worth it if whole-channel novelty becomes a question; it answers "first occurrence", not "how
  often". Not in stumpy, and its profile at pruned positions is filler rather than distances, so it could feed a top-k
  list but never Threshold*.
- **MPdist as a fourth Library distance** (Gharghabi et al. 2018, *ICDM*): compares members of different lengths by
  shared sub-shapes. A small, direct addition to RQ3's three distances (`Working/distances.py`); `stumpy.mpdist` is
  installed.
- **Nonlinear energy operator** (Mukhopadhyay & Ray 1998, *IEEE TBME* 45:180): the classic sharpness detector;
  cheap, but at 1 Hz on minute-long events its emphasis on the fastest change mostly amplifies noise. Would reuse
  Impulse events†.
- **AMPD** (Scholkmann et al. 2012, *Algorithms* 5:588): parameter-free peaks, but assumes quasi-periodic signals.
- **Bayesian online change points** (Adams & MacKay 2007): overlaps `detection.rupture` (PELT); FLUSS adds more.
- **Transfer entropy / multichannel causality** (Fukasawa et al. 2024, *Sci. Rep.* 14:15601) and **TICC**: need
  several channels at once — parked with round B's *multivariate analysis*.
- **Superparamagnetic clustering** (Wave_clus's sorter): replaced by HDBSCAN (row 8).

---

## 7. Implementation plan

### 7.1 Waves

| Wave | Blocks (types) | UI work | Effort (agent-days) |
|---|---|---|---|
| **W1 — detection, no UI work** | `preprocessing.beads` (S→S) · `detection.deconvolve` (S→Sc) · `detection.impulse_events` (Sc→Sp) · `detection.cwt_ridges` (S→Sp) · `detection.noise_threshold` (S→Sp) · `interrogation.trains` (Sp→Sp) · `detection.fluss` (S→Sc) · LV + CV2 in `interrogation.intervals` | none — every conversion has a view; glyphs only | ~5 |
| **W2 — families and categories** | `catalogue.event_windows` (Sp→W) · Library methods `kshape`, `hdbscan` (+ SVD-entropy coherence) · `catalogue.shape_families` (W→G) / `interrogation.event_families` (Sp→Sp) · `catalogue.minirocket` (W→W) · `catalogue.snippets` (W→G) | one view row for `spanset->windowset`; a serializer option for block-named exemplars | ~4 |
| **W3 — exploratory** | `catalogue.multiscale_entropy` (W→W) · `interrogation.cycle_shapes` (Sp→Sp) · `detection.pan_matrix_profile` (S→E) · optional Quiroga sorter, MPdist distance | an optional scalogram-with-ridges drawing | ~3 |

S = Signal, Sc = Scores, Sp = SpanSet, W = WindowSet, G = Grouping, E = Encoding. Effort per block: S ≈ half a day,
M ≈ a day, L ≈ two days of agent time, each including tests, glyph, smoke state and template. Stage and insert-modal
category per block are settled at build time against `Working/recipes.py::STAGES` and `Adapters/base.py::CATEGORIES`.

**Templates to ship (each a named chain in `webui/server/templates.py::CANONICAL`):** `deconvolved_troughs`,
`cwt_events`, `noise_threshold`, `spike_trains`, `fluss_regimes` (W1); `event_families`, `minirocket_manual_labels`,
`recording_snippets` (W2); `complexity_fingerprint` (W3).

### 7.2 Per block, the standing checklist (`docs/BLOCK_INTEGRATION.md` §5)

Test-first (the first commit touches only `tests/` and fails); core function under `Working/` with no UI import;
adapter in `Adapters/<stage>_<name>.py`; `estimate` for anything not O(n)-cheap (and a `COSTED` entry); glyph in
`glyphs.tsx`; a smoke state; template + end-to-end template test; the RQ file it serves updated before reporting. **No
package is installed**: everything above is in `stumpy`, `scikit-learn`, `tslearn`/`aeon`, `scipy`, `numpy`, or is a
port. Where the authors published code, the port is checked against it on a fixture, as the Dehshibi blocks were
against the authors' MATLAB (MATLAB R2025b is installed locally for the MATLAB references).

### 7.3 How a new detector earns a template

1. **Synthetic truth** — events with known onsets, overlaps, drift and noise; the unit tests.
2. **Port fidelity** — matches the reference implementation where one exists.
3. **Real data** — beats its own surrogate null (the existing 20-draw phase-randomised null), and on M2_aug's
   labelled windows is **more selective than `drop_detection_v1`** (a higher hit rate on *interesting* than on *not
   interesting* windows — the bar the Dehshibi template did not clear, 91 % vs 86 %).

A block that passes 1–2 but not 3 still ships as a block, its description saying "experimental: not selective on
M2_aug"; only a chain that passes 3 becomes a shipped template. (Question 4.)

### 7.4 Risks

- **Shared files** across parallel builders: `templates.py`, `glyphs.tsx`, `views.py`, `registry.tsx`,
  `tests/test_block_standard.py`, the smoke states. Build in separate worktrees and merge one at a time.
- **Recipe hashes:** adding a parameter to an existing block changes its recipe hash (defaults are filled before
  hashing). The plan adds parameters to no existing block except `interrogation.intervals` (new output columns, no
  new parameter) and, optionally, `catalogue.classifier`.
- **Drift is everyone's problem.** Matrix-profile blocks, MSE and OASIS all degrade on drift; BEADS lands first so
  the others are tested on cleaned signals as well as raw.
- **Artefacts that look like biology.** Both Buffi et al. 2025 papers saw spikes from people walking past, the
  incubator door and window shades on fungus **and** no-fungus channels, and a ~0.005 Hz cycle with no fungus at all.
  No single-channel block can tell those apart. Any new detector's events should be checked for coincidence across
  channels — RQ6's contamination machinery is where that lives today; a per-chain "control-channel veto" would need a
  cross-channel side input, which is round B's parked *multivariate analysis*.
- **Licences.** OASIS (GPL-3.0), Wave_clus (non-commercial) and WarpingWSF (no licence) are re-derived from the papers
  and never copied; BEADS is ported from Duval's BSD-3 MATLAB.
- **Timing.** CLAUDE.md puts the polish of the Pipeline UI first until 21 October. Wave 1 touches only `Adapters/`,
  `Working/`, `tests/`, templates and glyphs — not the pages being polished — but it is still agent time. (Question 1.)

---

## 8. Questions for you

> **Decided by the researcher, 2026-10-13:**
> - **Q1 — build wave 1 today**, the main session acting as manager: one prompt per block
>   (`docs/prompts/blocks/`), implementer sub-agents in parallel, critic sub-agents, then a final evaluation in the
>   main session.
> - **Q2 — (a)** FLUSS + snippets (snippets is wave 2).
> - **Q3 — (a)** both the Library and Analyse, one implementation (wave 2).
> - **Q4 — (a), amended:** a chain becomes a shipped template only if it **beats its random-data (surrogate) null** on
>   real recordings; it does **not** have to be choosier than `drop_detection_v1`, because different algorithms suit
>   different motif types. A block that misses the bar ships as a block marked experimental.
> - **Q5 — (a)** reject the √t transform; keep LV (and the local CV2, see §4 A3).

**Q1 — When to build.** *In plain words:* the 21 October deadline is about making the app smooth and reliable, and
new analysis blocks are new capability, not polish. They do not touch the pages being polished, but they compete for
the same time. **Options:** (a) build wave 1 now, alongside the polish, in separate worktrees; (b) build nothing
until after 21 October; (c) build only the two blocks that remove friction now — the noise-relative threshold (no
volts-or-millivolts cut to type per dataset) and BEADS (no detrend window to guess) — and the rest of wave 1 straight
after 21 October. **Recommendation: (c).**

**Q2 — Which matrix-profile methods.** *In plain words:* FLUSS draws lines where the recording changes behaviour;
snippets names the few typical behaviours and colours the recording by them; the pan matrix profile shows at which
window lengths anything repeats, so you stop guessing the window. **Options:** (a) FLUSS + snippets; (b) FLUSS + pan
matrix profile; (c) all three. **Recommendation: (a)** — two new kinds of answer; the pan matrix profile is a
convenience for a parameter you have already settled by trial for spikes.

**Q3 — Where clustering lives.** *In plain words:* there are two places a clustering method can go. The Library's
grouping editor is where your 3,603 events and 149 families live; Analyse is where a chain can cluster windows or
events and then hand the families to Intervals. **Options:** (a) both, implemented once in the Library's method
registry and exposed in Analyse through one block; (b) Analyse only; (c) Library only. **Recommendation: (a)** — one
implementation, and the families you curate in the Library are the same objects a chain can time.

**Q4 — The bar for a template.** *In plain words:* the Dehshibi detector was a faithful copy of the paper and still
fired almost as often on boring windows as on interesting ones. Before a new detector is offered as a ready-made
template, should it have to prove it is choosier than the drop detector? **Options:** (a) yes — §7.3: synthetic tests,
port fidelity, beats its null and is more selective than `drop_detection_v1` on M2_aug, otherwise block-only and
marked experimental; (b) ship every chain as a template and judge them in use; (c) stricter — also require your
verdicts in Review on a sample of its detections. **Recommendation: (a).**

**Q5 — The √t paper.** *In plain words:* the √t transform's clock starts when the recording starts, so the same spike
looks different at hour 1 and hour 100; its advantage over the standard method came from a detrending step the
standard method was not given; and its classifier results are blank. **Options:** (a) reject, keep only the LV / CV2
statistics; (b) build it anyway as an experimental encoding so it can be compared on our data. **Recommendation: (a).**

---

## Sources

Attached by the researcher:
- Costa, M., Goldberger, A. L. & Peng, C.-K. (2005). Multiscale entropy analysis of biological signals. *Phys. Rev. E*
  71, 021906. doi:10.1103/PhysRevE.71.021906
- Colominas, M. A. & Wu, H.-T. (2023). An iterative warping and clustering algorithm to estimate multiple wave-shape
  functions from a nonstationary oscillatory signal. *IEEE Trans. Signal Process.* 71, 701–712.
  doi:10.1109/TSP.2023.3252883 — code: https://github.com/macolominas/WarpingWSF
- Knowles, J. (2025). A √t-warped wave transform reveals multi-scale electrical rhythms in fungal networks. *bioRxiv*.
  doi:10.1101/2025.08.31.673362

Recommended:
- Friedrich, J., Zhou, P. & Paninski, L. (2017). Fast online deconvolution of calcium imaging data. *PLoS Comput.
  Biol.* 13(3), e1005423. doi:10.1371/journal.pcbi.1005423
- Du, P., Kibbe, W. A. & Lin, S. M. (2006). Improved peak detection in mass spectrum by incorporating continuous
  wavelet transform-based pattern matching. *Bioinformatics* 22(17), 2059–2065. doi:10.1093/bioinformatics/btl355
- Ning, X., Selesnick, I. W. & Duval, L. (2014). Chromatogram baseline estimation and denoising using sparsity
  (BEADS). *Chemometr. Intell. Lab. Syst.* 139, 156–167. doi:10.1016/j.chemolab.2014.09.014
- Quian Quiroga, R., Nadasdy, Z. & Ben-Shaul, Y. (2004). Unsupervised spike detection and sorting with wavelets and
  superparamagnetic clustering. *Neural Comput.* 16(8), 1661–1687. doi:10.1162/089976604774201631
- Pasquale, V., Martinoia, S. & Chiappalone, M. (2010). A self-adapting approach for the detection of bursts and
  network bursts in neuronal cultures. *J. Comput. Neurosci.* 29, 213–229.
- Cotterill, E., Charlesworth, P., Thomas, C. W., Paulsen, O. & Eglen, S. J. (2016). A comparison of computational
  methods for detecting bursts in neuronal spike trains and their application to human stem cell-derived neuronal
  networks. *J. Neurophysiol.* 116, 306–321. https://pmc.ncbi.nlm.nih.gov/articles/PMC4969396/
- Shinomoto, S., Shima, K. & Tanji, J. (2003). Differences in spiking patterns among cortical neurons. *Neural
  Comput.* 15, 2823–2842.
- Gharghabi, S., Ding, Y., Yeh, C.-C. M., Kamgar, K., Ulanova, L. & Keogh, E. (2017). Matrix profile VIII: domain
  agnostic online semantic segmentation at superhuman performance levels. *ICDM*, 117–126.
  https://www.cs.ucr.edu/~eamonn/Segmentation_ICDM.pdf
- Paparrizos, J. & Gravano, L. (2015). k-Shape: efficient and accurate clustering of time series. *SIGMOD*,
  1855–1870. doi:10.1145/2723372.2737793
- Campello, R. J. G. B., Moulavi, D. & Sander, J. (2013). Density-based clustering based on hierarchical density
  estimates. *PAKDD*, LNCS 7819, 160–172.
- Dempster, A., Schmidt, D. F. & Webb, G. I. (2021). MiniRocket: a very fast (almost) deterministic transform for
  time series classification. *KDD*, 248–257. doi:10.1145/3447548.3467231
- Imani, S., Madrid, F., Ding, W., Crouter, S. & Keogh, E. (2018). Matrix profile XIII: time series snippets.
  *ICBK*, 382–389; extended in *Data Min. Knowl. Discov.* 34(6), 1713–1743 (2020).
- Madrid, F., Imani, S., Mercer, R., Zimmerman, Z., Shakibay, N. & Keogh, E. (2019). Matrix profile XX: finding and
  visualizing time series motifs of all lengths using the matrix profile. *ICBK*, 175–182.
  https://www.cs.ucr.edu/~eamonn/PAN_SKIMP%20%28Matrix%20Profile%20XX%29.pdf
- Wu, S.-D., Wu, C.-W., Lin, S.-G., Lee, K.-Y. & Peng, C.-K. (2014). Analysis of complex time series using refined
  composite multiscale entropy. *Phys. Lett. A* 378(20), 1369–1374. doi:10.1016/j.physleta.2014.03.034

Considered:
- Zhu, Y., Imamura, M., Nikovski, D. & Keogh, E. (2017). Matrix profile VII: time series chains. *ICDM*.
  doi:10.1109/ICDM.2017.79
- Lu, Y., Wu, R., Mueen, A., Zuluaga, M. A. & Keogh, E. (2022). Matrix profile XXIV: scaling time series anomaly
  detection to trillions of datapoints and ultra-fast arriving data streams. *KDD*, 1173–1182.
  doi:10.1145/3534678.3539271
- Gharghabi, S., Imani, S., Bagnall, A., Darvishzadeh, A. & Keogh, E. (2018). Matrix profile XII: MPdist. *ICDM*,
  965–970. doi:10.1109/ICDM.2018.00119
- Mukhopadhyay, S. & Ray, G. C. (1998). A new interpretation of nonlinear energy operator and its efficacy in spike
  detection. *IEEE Trans. Biomed. Eng.* 45(2), 180–187. doi:10.1109/10.661266; and Choi, J. H., Jung, H. K. & Kim, T.
  (2006). A new action potential detector using the MTEO … *IEEE Trans. Biomed. Eng.* 53(4), 738–746.
- Scholkmann, F., Boss, J. & Wolf, M. (2012). An efficient algorithm for automatic peak detection in noisy periodic
  and quasi-periodic signals. *Algorithms* 5(4), 588–603.
- Adams, R. P. & MacKay, D. J. C. (2007). Bayesian online changepoint detection. arXiv:0710.3742.
- Fukasawa, Y., Akai, D., Takehi, T. & Osada, Y. (2024). Electrical integrity and week-long oscillation in fungal
  mycelia. *Sci. Rep.* 14, 15601. doi:10.1038/s41598-024-66223-6

Fungal context:
- [S1] Adamatzky, A. (2022). Language of fungi derived from their electrical spiking activity. *R. Soc. Open Sci.* 9,
  211926. doi:10.1098/rsos.211926 (arXiv:2112.09907)
- [S2] Adamatzky, A., Schunselaar, E., Wösten, H. A. B. & Ayres, P. (2023). Multiscalar electrical spiking in
  *Schizophyllum commune*. *Sci. Rep.* 13, 12808. doi:10.1038/s41598-023-40163-z
- [S3] Dehshibi, M. M. & Adamatzky, A. (2021). Electrical activity of fungi: spikes detection and complexity analysis.
  *Biosystems* 203, 104373. (arXiv:2008.10276)
- [S4] Adamatzky, A. (2026). Directional electrical spiking, bursting, and information propagation in oyster mycelium
  recorded with a star-shaped electrode array. arXiv:2601.08099 — threshold multiple, burst gap and propagation window
  are not stated in the text.
- [S5] Buffi, M. et al. (2025). Detection of electrical signals in fungal mycelia in response to external stimuli.
  *iScience* 28(10), 113484. doi:10.1016/j.isci.2025.113484; Buffi, M., Kelliher, J. M., Robinson, A. J. et al.,
  Junier, P. (2025). Electrical signaling in fungi: past and present challenges. *FEMS Microbiol. Rev.* 49, fuaf009.
  doi:10.1093/femsre/fuaf009
- Shinomoto, S. et al. (2009). Relating neuronal firing patterns to functional differentiation of cerebral cortex.
  *PLoS Comput. Biol.* 5(7), e1000433 (the LV / LvR formulas as verified).
