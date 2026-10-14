# Analysis-block algorithms checked against their primary sources — research

**Method.** Primary sources only: the papers themselves (author PDFs, arXiv/bioRxiv, PMC full text), the dataset record,
and the **installed** library source on this machine, read file by file. Nothing below is filled from memory without the
word **unverified** next to it. Checked 2026-10-13 by a verification sub-agent; reproduced here by the main session, which
corrected four points (marked **[main session]**). Companion to
[`analysis-blocks-from-literature.md`](analysis-blocks-from-literature.md), which holds the evaluation and the plan.

**Where the libraries actually live.** The conda python (`C:/ProgramData/anaconda3/python.exe`) imports stumpy,
scikit-learn, aeon and tslearn from the **user site-packages** `C:/Users/mmebr/AppData/Roaming/Python/Python313/site-packages/`
(abbreviated `USP/`), not from `C:/ProgramData/anaconda3/Lib/site-packages/` (`CSP/`). `CSP/` holds scikit-learn **1.6.1**;
`USP/` holds the **1.7.2** that is actually imported. scipy 1.17.1 is imported from `CSP/`. stumpy 1.14.1 is identical in
both. Every file:line below is in the copy that is imported.

**[main session] corrections to the sub-agent's report.**
1. Costa 2005's data-length guidance **is** in the paper (read from the PDF the researcher attached): §III "Unless
   otherwise specified, the values of the parameters used to calculate S_E are N = 2×10⁴, m = 2, and r = 0.15", and §VI
   "Typically, we use time series with 2×10⁴ data points for analyses extending up to scale 20, in which case the
   shortest coarse-grained time series has 1×10³ data points".
2. Adamatzky, Schunselaar, Wösten & Ayres 2023 is DOI **10.1038/s41598-023-40163-z**, *Sci. Rep.* 13, article 12808
   (publisher listing via DOAJ), not 10.1038/s41598-023-39526-8.
3. Knowles' eqs. (1)–(2) were read from the attached PDF: W(k, τ; u₀) = ∫₀^∞ V(t) ψ((√t − u₀)/τ) e^{−ik√t} dt, and with
   u = √t, W = ∫₀^∞ 2u V(u²) ψ((u − u₀)/τ) e^{−iku} du; the STFT baseline is matched by t₀ = u₀², σ_t = 2u₀τ (§3.2).
4. Cotterill et al. 2016, checked in the Europe PMC full text: MaxInterval "is our recommendation for a first choice";
   "a high-performing alternative is the logISI method"; logISI "had a tendency to underestimate burst durations in some
   cases"; rank surprise "tended to both overestimate bursting activity in nonbursting trains".

---

## Summary in plain language

Think of this note as a fact-check of a recipe book before cooking. The plan described, partly from memory, how fifteen
families of algorithms work (finding spikes, measuring how irregular a spike train is, clustering shapes, cutting a long
recording into regimes). This note goes back to the original papers and to the code installed on this computer and
checks each line.

**Most of the plan is right in spirit; a handful of specific numbers and details were wrong**, and some of those would
bite if blocks were built straight from it:

- **The fungal dataset is 1 Hz for all four species.** The Zenodo record says "one sample per second". The √t-warp
  preprint says "5 Hz" for *Cordyceps* in its text while its own abstract says fs≈1 Hz. Nobody has publicly reviewed it
  (0 PREreviews) and only v1 exists.
- **Adamatzky's spike-detector settings differ by species, and "w=20, δ=0.01, d=30" belongs to a different paper** (the
  2023 *Schizophyllum* study) — which is what `detection.spike_v1`'s defaults are.
- **Wave_clus filtered 300–6000 Hz, not 300–3000 Hz**, and its licence ("free for non-commercial use") is not open source.
- **stumpy's Pan Matrix Profile is scaled by d/(2·√m), not d/√(2m)**, and `stimp.PAN_` is *binarised at 0.2 by default*:
  it is a picture, not distances.
- **FLUSS edges:** the paper blanks the first and last **L** points; stumpy blanks **5·L** at each end and fits a beta
  curve instead of the paper's parabola.
- **stumpy's `snippets` default (`percentage=1.0`) silently turns the paper's MPdist into plain Euclidean distance**,
  losing the robustness to drift that the paper relies on.
- **scipy's `find_peaks_cwt` is not the published Du et al. algorithm**: noise is the 10th percentile of *signed*
  smallest-scale coefficients (paper: 95th percentile of *absolute* values), and the SNR uses the smallest-scale
  coefficient (paper: the ridge maximum).
- **The burst benchmark recommends MaxInterval first**, with logISI as the high-performing alternative.
- **The MTEO paper is IEEE TBME 53(4):738–746, not 53(12).** OASIS code is **GPL-3.0**.
- **tslearn `KShape.fit` does not z-normalise but `predict` does**; aeon 1.4 deprecates `TimeSeriesKShape` in favour of
  its own `KShape`.
- **Colominas & Wu's abstract says "vector spectral clustering" but the method is k-means** (50 replicates,
  Calinski–Harabasz). Their code has **no licence file**.

**Could not verify** (marked inline): the exact RCMSE equation (publisher blocked; secondary restatement only), the NEO
threshold multiplier, the Pasquale void formula/binning (Springer blocked; Cotterill's restatement used), the official
DAMP text (local PDF would not render; an unofficial port of the authors' MATLAB was read), the BEADS cost function in
the paper itself (HAL blocked; the authors' BSD MATLAB via pybaselines was read).

---

## 1. Multiscale entropy (MSE) and refined composite MSE (RCMSE)

**Citations.** Costa M, Goldberger AL, Peng C-K (2005) Multiscale entropy analysis of biological signals. *Phys Rev E*
71:021906. DOI 10.1103/PhysRevE.71.021906 (verified). Wu S-D, Wu C-W, Lin S-G, Lee K-Y, Peng C-K (2014) Analysis of
complex time series using refined composite multiscale entropy. *Phys Lett A* 378(20):1369–1374. DOI
10.1016/j.physleta.2014.03.034 (from NTU/NTOU repository records; full text not reached).

**Verified algorithm (MSE)**, from the paper and the authors' PhysioNet tutorial and `mse.c`
(https://physionet.org/files/mse/1.0/tutorial/tutorial.pdf, https://physionet.org/files/mse/1.0/mse.c):
1. Coarse-grain: y_j^(τ) = (1/τ) Σ_{i=(j−1)τ+1}^{jτ} x_i, 1 ≤ j ≤ N/τ (non-overlapping means; paper eq. 16).
2. SampEn of each y^(τ), plotted against τ.
3. Tolerance: in `mse.c`, `sd` is computed **once on the raw series** and `r_new = r*sd` is passed unchanged to every
   scale. So r is a fraction of the SD of the **original** series and fixed across scales (paper §III says the same).

**Defaults.** m = 2, r = 0.15; max scale 20; N = 2×10⁴ in the paper (§III, §VI — **[main session]**); the tutorial's
default uses the first 40,000 points and its noise figure used N = 30,000. r is "typically chosen to be between 10% and
20%" of the SD.

**Stated failure modes.** Outliers inflate the SD and therefore r; a few huge outliers drove SampEn to ≈0 at all scales
in the tutorial's example (§4). The paper adds (App. B): nonstationarity matters, and "attempts to remove nonlocal
nonstationarities, e.g., trends, will most likely modify the structure of the time series over multiple time scales".

**RCMSE.** At scale τ, build all τ coarse-grained series (offsets k = 1..τ). Count template matches n^m_{k,τ} and
n^{m+1}_{k,τ}, pool them, and take RCMSE = −ln(Σ_k n^{m+1}_{k,τ} / Σ_k n^m_{k,τ}). This pooling is per the secondary
restatement in Azami et al. 2017, *Med Biol Eng Comput*, DOI 10.1007/s11517-017-1647-5 (PMC5644759), which says RCMSE has
"τ times more number of instances … more reliable results, especially for short signals" but was "still undefined at
some scale factors" at N = 100 and 300. **The exact Wu 2014 equation is unverified.**

**Implementation here.** None installed (antropy and neurokit2 absent). `Working/Detection/analysis/entropy_analysis.py`
has a single-scale `_sample_entropy`. The PhysioNet C code's licence is unverified.

**Discrepancies with the plan.** None remaining after correction 1.

---

## 2. Iterative warping and clustering of wave-shape functions

**Citation.** Colominas MA, Wu H-T (2023) An iterative warping and clustering algorithm to estimate multiple wave-shape
functions from a nonstationary oscillatory signal. *IEEE Trans Signal Process* 71:701–712. DOI 10.1109/TSP.2023.3252883.
Read in full from the PDF the researcher attached; preprint arXiv:2208.06500 v2 consistent.

**Verified algorithm.**
1. STFT with a real even window whose spectrum is supported in [−H, H], H < inf φ₁′/2. Extract the ridge of the dominant
   harmonic ℓ (ℓ = 1 usually; ℓ = 2 for ECG and accelerometry) to get the IF.
2. Amplitude B̃ ≈ 2|V(t, φ̃′(t))|/|ĥ(0)|; phase = ∫φ̃′.
3. Resample at uniform phase and divide by amplitude (warp + demodulate). Repeat until the **SVD entropy stagnates** ("We
   thus suggest stopping the iteration process when the SVD entropy is stagnated"). Their examples needed 1–8 iterations.
4. Cycles of period 1 form a P×L matrix. SVD entropy is the Shannon entropy of the normalised singular values (eq. 17).
5. Synchronise cyclic shifts with a graph connection Laplacian (2P×2P SO(2) blocks; top two eigenvectors; rotation per
   block fitted by SVD).
6. k-means with **50 replicates**; K chosen by **Calinski–Harabasz**.
7. Wave-shape functions are cluster medians or trigonometric regression on them. Change points are where consecutive
   cycles switch cluster.

**Stated assumptions and limits.** Amplitude and frequency must vary slowly. Wave-shape changes are modelled only as
discontinuities in non-dominant harmonics. ℓ must be chosen beforehand. One oscillatory component is assumed (§VI). The
stopping rule is heuristic. The ECG case needed a hand-tuned ×1.991 rescale of warped time.

**Implementation here.** None. https://github.com/macolominas/WarpingWSF is MATLAB with **no LICENSE file**, so all
rights are reserved by default: implement from the paper, do not port the code.

**Discrepancies with the plan.** The abstract says "vector spectral clustering"; the method section (cited by the plan)
says k-means. The plan should mention the choice of ℓ. Isolated 1 Hz fungal spikes violating the slowly-varying
oscillation assumption is an inference, not a paper claim.

*Added 2026-10-15 by the wave-3 manager, from the W3-B critic (`docs/prompts/blocks/reports/W3-B-cycle-shapes.critic.md`
B2):* `interrogation.cycle_shapes` adapts the paper's K choice with **SigClust** (Liu, Hayes, Nobel & Marron 2008,
*JASA* 103:1281–1293), which this file does not cover. SigClust's background-noise floor σ_N² = (MAD/0.6745)² assumes
**sparse HDLSS data, most coordinates pure noise**. On z-normalised smooth cycles every coordinate carries the curve,
so flooring the eigenvalues up to σ_N² inflated the null's variance 1.4–2.1× and rejected a true one-cluster AR-Toeplitz
Gaussian 12/12 at n ≥ 200 (0/12 without the floor). The block now reports SigClust unfloored and gates K on 2-means
calibrated against its background-null draws instead.

---

## 3. √t-warped wave transform (Knowles 2025) and the dataset

**Citation.** Knowles J (2025) A √t-warped wave transform reveals multi-scale electrical rhythms in fungal networks.
bioRxiv, posted 4 Sep 2025, DOI 10.1101/2025.08.31.673362, CC-BY 4.0. Independent researcher.

**Versions and review.** Only **v1** is listed; a v2 request returned 403, so a later version cannot be ruled out.
PREreview (https://prereview.org/preprints/doi-10.1101-2025.08.31.673362) shows **0 reviews**.

**What it says.** Eqs. (1)–(2): see correction 3. Windowed Fourier transform in u = √t with a Gaussian window by default
(Morlet, DOG and Bump also compared) and optional detrending in u. τ scales {5.5, 24.5, 104} s. Spike detection: a
moving-average baseline of 300–900 s, an absolute threshold of 0.05–0.2 mV, a refractory period of 120–300 s. Validation
LOFO/LOCO with ≥200 permutations and 1000-rep bootstrap. N = 4/4/4/11 files. A repository is mentioned with **no URL and
no licence**.

**Dataset.** Adamatzky A, "Recordings of electrical activity of four species of fungi", Zenodo DOI
10.5281/zenodo.5790768, CC-BY 4.0 (https://zenodo.org/records/5790768): "We recorded electrical activity one sample per
second". The logger averaged up to ~600 readings/s into each sample; range 78 mV; *S. commune* ~1.5 days, the others ~5
days. The companion arXiv 2112.09907 also says one sample per second.

**Discrepancies with the plan.** None; the plan's reading is confirmed. Extra: the preprint contradicts itself (abstract
fs≈1 Hz; §3.4a/§4.2 *Cordyceps* "→ 5 Hz", *Pleurotus* 2 Hz), its Nyquist margins are numerically off (≈250×, not
"3–20×"), and it lists *Pleurotus djamor* and 11 *S. commune* files that are not in the four-file Zenodo record
(provenance unverified).

*Tested 2026-10-15 by the wave-3 manager (`docs/prompts/blocks/reports/W3-evaluation.md`, "The √t check"):* on our copy
of the same *S. commune* data (seven channels, one 72 h window each), multiscale entropy with r from the SD and **no
detrend** gives mean entropies of **0.014–0.49** per channel (mean 0.14) over scales 1–174 s — low, a partial collapse,
but not the preprint's "mean MSE 0.0028"; with a 2 h detrend and r from the MAD, 0.58–1.18. Drift-inflated r (the
plan's suspicion, §4 A1) explains a low value, not that number. One channel's collapse (CH6, 0.014) comes from a single
−71 mV spike inflating the SD, not from drift.

---

## 4. Wave_clus

**Citation.** Quian Quiroga R, Nadasdy Z, Ben-Shaul Y (2004) Unsupervised spike detection and sorting with wavelets and
superparamagnetic clustering. *Neural Comput* 16(8):1661–1687. DOI 10.1162/089976604774201631 (CaltechAUTHORS
kb2ve-awb39; PDF read in full).

**Verified algorithm.**
1. Band-pass **300–6000 Hz**, four-pole Butterworth (§3.1).
2. Thr = 4σ_n with σ_n = median{|x|/0.6745} (eq. 3.1). Rationale: the median is barely moved by spikes "under the
   reasonable assumption that spikes amount to a small fraction of all samples".
3. Keep 64 samples per spike (~2.5 ms at 24 kHz). Align maxima at sample 20 after cubic-spline upsampling to 256 samples.
4. Four-level Haar decomposition gives 64 coefficients (§2.1, §3.2).
5. Score each coefficient with the Lilliefors-modified KS statistic max|F−G|, using **only values within ±3 SD**. Keep
   the **10** most non-normal.
6. SPC: q = 20, K = 11, N = 500 Monte Carlo iterations, θ = 0.5; J_ij = (1/K) exp(−‖x_i−x_j‖²/2a²) (eq. 2.3).
7. Sweep T from **0 to 0.2 in steps of 0.01**; take the highest T at which a new cluster of **more than 60 points**
   appears (60 s recordings, so ≥1 Hz units; "should be decreased" for low rates) (§3.3).

**Stated failure modes.** A lower threshold (3.5σ) trades misses for false positives. Low noise causes double
detections of multiphasic spikes. KS also selects skewed or heavy-tailed unimodal coefficients (3 of 10 in their
example). Spikes overlapping by less than ~0.5 ms are not clustered. The method "should not be taken as a black box".

**Implementation here.** None. https://github.com/csn-le/wave_clus is MATLAB, "free … for any non-commercial
applications", with SPC as a separate `cluster.exe`. Steps 2 and 5 can be rebuilt with `scipy.stats.kstest` and pywt
1.8.0 `wavedec(..., 'haar', level=4)`.

**Discrepancies with the plan.** The band is 300–6000 Hz. At 1 Hz a 64-sample window is 64 s: derive the window from
spike duration, not from the constant.

---

## 5. OASIS

**Citation.** Friedrich J, Zhou P, Paninski L (2017) Fast online deconvolution of calcium imaging data. *PLoS Comput
Biol* 13(3):e1005423. DOI 10.1371/journal.pcbi.1005423. arXiv:1609.00639 v3. Equations are images; verified from the
prose.

**Verified algorithm.**
1. Model: calcium is AR(p), p = 1 or 2, driven by non-negative spikes s_t; observed = calcium + b + i.i.d. Gaussian noise
   σ². The AR(2) simulations used γ1 = 1.7, γ2 = −0.712.
2. Either an ℓ1-penalised non-negative LASSO (λ), or the noise-constrained form ‖c−y‖² = σ²T with λ raised until the
   constraint is tight.
3. Solver: an active-set generalisation of PAVA that "inherits its linear-time computational complexity".
4. γ starts as a crude autocovariance estimate and is refined by minimising RSS. σ comes from the PSD. b starts at a low
   percentile ("the 15% percentile") or is optimised jointly.
5. Thresholded variant: a **minimum spike size s_min** replaces ℓ1 (non-convex); s_min is raised until RSS reaches σ²T;
   s_min = 0.5 was best in their test.
6. Online processing at ~1 µs/frame with possible O(1) memory.

**Stated failure modes.** Linear-Gaussian model. Parameters assumed fixed: **drifting baselines "could be generalized"
but are not handled**. AR(1) assumes an instant rise. Fast AR(2) is greedy. Spike timing reliable to ~1 bin.

**Implementation here.** Not installed. https://github.com/j-friedrich/OASIS is Python/Cython (and MATLAB), **GPL-3.0**
(`pip install oasis-deconv`). Reimplement from the paper; do not vendor. A reference fixture can be generated by running
the authors' MATLAB code with the local MATLAB R2025b (licence of github.com/zhoupc/OASIS_MATLAB unverified).

**Discrepancies with the plan.** None in substance; detrend upstream.

---

## 6. BEADS

**Citation.** Ning X, Selesnick IW, Duval L (2014) Chromatogram baseline estimation and denoising using sparsity
(BEADS). *Chemom Intell Lab Syst* 139:156–167. DOI 10.1016/j.chemolab.2014.09.014. The HAL preprint hal-01330608 is
**blocked**, so the paper text was not read.

**Verified from implementations.** pybaselines' port is BSD-3, adapted from Duval's MATLAB ("Copyright (c) 2018, Laurent
Duval", BSD-3; https://raw.githubusercontent.com/derb12/pybaselines/main/pybaselines/misc.py). Its cost is
`0.5*h.dot(h) + lam_0*theta + lam_1*... + lam_2*...`, h being the high-pass-filtered residual (banded `B A⁻¹`), theta an
asymmetric Huber-like penalty with ratio `asymmetry`, the λ1/λ2 terms penalising first and second differences; the MM
steps cite "Table 3 of the beads paper". In symbols: F(x) = ½‖H(y−x)‖² + λ0 Σθ_ε(x_n; r) + λ1 Σφ([D1x]_n) +
λ2 Σφ([D2x]_n) — consistent with the code; **the paper's own equation is unverified**.

pybaselines signature: `Baseline.beads(data, freq_cutoff=0.005, lam_0=1.0, lam_1=1.0, lam_2=1.0, asymmetry=6.0,
filter_type=1, cost_function=2, max_iter=50, tol=0.01, eps_0=1e-06, eps_1=1e-06, fit_parabola=True,
smooth_half_window=None)`.
- The λ defaults suit ~1000 points; tune `freq_cutoff` first.
- **The endpoints must be near 0**, hence `fit_parabola`.
- pybeads (MIT, https://github.com/skotaro/pybeads) reports instability for tiny λ1 changes and recommends derivative
  smoothing (`conv` = 3 or 5) and sigmoid end-padding.

**Implementation here.** pybaselines is not installed. Duval's MATLAB is BSD-3 and portable.

**Discrepancies with the plan.** The endpoint requirement and the λ1 instability were missing. Drops (troughs) need the
asymmetry flipped.

---

## 7. CWT ridge-line peak detection vs scipy `find_peaks_cwt`

**Citation.** Du P, Kibbe WA, Lin SM (2006) Improved peak detection in mass spectrum by incorporating continuous wavelet
transform-based pattern matching. *Bioinformatics* 22(17):2059–2065. DOI 10.1093/bioinformatics/btl355 (verified).

**Paper algorithm.**
1. Mexican-hat CWT (support [−5, 5]); the illustration used 33 scales from 1 to 64 in steps of 2.
2. Local maxima per scale in a window proportional to the support; link from the largest scale down to the nearest
   maximum; a gap counter drops ridges with too many gaps.
3. A peak needs (a) the ridge maximum's scale within a range, (b) SNR above a threshold, (c) ridge length above a
   threshold.
4. SNR: signal = **max CWT coefficient on the ridge** within the scale range; noise = **95th percentile of |coefficients|
   at scale 1** in a local window, with a floor.
5. No baseline removal or smoothing, *assuming a slowly, monotonically varying baseline over the peak support*.
6. Width from the scale of the ridge maximum; location from the ridge or a centroid.

The numeric thresholds are **not stated** in the article; "SNR = 3" is unverified.

**Installed.** `scipy.signal.find_peaks_cwt(vector, widths, wavelet=None, max_distances=None, gap_thresh=None,
min_length=None, min_snr=1, noise_perc=10, window_size=None)` at `CSP/scipy/signal/_peak_finding.py:1201`.
- Public `signal.cwt`/`ricker` are removed; `wavelets.py` is a deprecation shim with empty `__all__`.
- It uses private `_cwt`/`_ricker`, the wavelet truncated to `min(10*width, len(data))` (`_wavelets.py:26`).
- Defaults: `gap_thresh=ceil(widths[0])` (:1296), `max_distances=widths/4` (:1298), `min_length=ceil(n_widths/4)`
  (:1174), `window_size=ceil(N/20)` (:1176).

**Differences from the paper.**
- Noise is the **10th percentile of signed** row-0 coefficients (:1182, :1188). On smooth data this is ~0 or negative,
  and taking `abs()` of the ratio then breaks the SNR.
- The SNR numerator is the coefficient at the ridge's **smallest** scale (:1193); the public docstring wrongly says
  "maximum CWT coefficient on the largest ridge line".
- No scale-range test and no width output; location is the column at the smallest scale (:1307).

**Discrepancies with the plan.** The plan describes the paper correctly. Do not assume scipy implements it: write the
paper's ridge, SNR and width steps.

---

## 8. Burst detection

**8a.** Pasquale V, Martinoia S, Chiappalone M (2010) A self-adapting approach for the detection of bursts and network
bursts in neuronal cultures. *J Comput Neurosci* 29(1–2):213–229. DOI 10.1007/s10827-009-0175-1 (PubMed 19669401). Full
text blocked; the algorithm below is **as restated by Cotterill et al. 2016**:
- A log-ISI histogram with a custom peak finder. The largest peak at ISI ≤ **100 ms** is the intraburst peak; if there
  is none, there are no bursts.
- At the minima after that peak, the first minimum with void parameter **exceeding 0.7** sets maxISI.
- A burst is ≥ **3** spikes with ISIs < maxISI.
- If there is no cutoff, or maxISI > 100 ms, find cores with 100 ms and extend them by spikes within maxISI of the edges.
- **Unverified:** the void formula (believed 1 − g(min)/√(g(p1)g(p2))), bins per decade, smoothing.

**8b.** Cotterill E, Charlesworth P, Thomas CW, Paulsen O, Eglen SJ (2016) A comparison of computational methods for
detecting bursts in neuronal spike trains and their application to human stem cell-derived neuronal networks. *J
Neurophysiol* 116:306–321. DOI 10.1152/jn.00093.2016 (PMC4969396; quotes checked in the Europe PMC full text — correction 4).
- MaxInterval "is our recommendation for a first choice"; "a high-performing alternative is the logISI method"; logISI
  "had a tendency to underestimate burst durations in some cases", and logISI and HSMM put more noise spikes into bursts.
- Rank surprise "tended to both overestimate bursting activity in nonbursting trains".
- Poisson surprise merged 10–20 s bursting episodes into single bursts.
- MaxInterval settings used: begin ISI 0.17 s, end ISI 0.3 s, minimum IBI 0.2 s, minimum duration 0.01 s, minimum 3
  spikes — neuronal units, to be rescaled for 1 Hz fungal data.

**8c.** Adamatzky A (2022) Language of fungi derived from their electrical spiking activity. *R Soc Open Sci* 9:211926.
Journal page 403; arXiv 2112.09907 read via ar5iv (published values could differ — unverified).
- Detection: |x_i| − |mean of its w-neighbourhood| > δ, then "removing false spikes located at a distance d from a given
  spike".
- Settings by species: *C. militaris* and *F. velutipes* w = 200, δ = 0.1, d = 300; *S. commune* w = 100, δ = 0.005,
  d = 100; *O. nidiformis* w = 50, δ = 0.003, d = 100. "Over 80% of spikes" were detected.
- Words: consecutive spikes belong to one word if their gap is "not more than θ", with θ = a or 2a and a = the species'
  mean interspike interval.
- No drift or artefact handling.

**Discrepancies with the plan.** w = 20 / δ = 0.01 / d = 30 are the 2023 *S. commune* fast-spike values (§15a), not the
2022 ones. The void threshold is "exceeds 0.7". MaxInterval is the benchmark's first choice; logISI is close behind with a
duration-underestimate caveat.

---

## 9. Local variation (LV / LvR)

**Citations.** Shinomoto S, Shima K, Tanji J (2003) Differences in spiking patterns among cortical neurons. *Neural
Comput* 15:2823–2842, DOI 10.1162/089976603322518759 (record verified; full text not read). Shinomoto S et al. (2009)
Relating neuronal firing patterns to functional differentiation of cerebral cortex. *PLoS Comput Biol* 5(7):e1000433,
DOI 10.1371/journal.pcbi.1000433 (PDF read).

**Verified (2009 eqs. 2–3).**
- Lv = 3/(n−1) Σ_{i=1}^{n−1} ((I_i − I_{i+1})/(I_i + I_{i+1}))², n = number of ISIs. 0 for a regular train, 1 for Poisson.
- LvR = 3/(n−1) Σ (1 − 4I_iI_{i+1}/(I_i+I_{i+1})²)(1 + 4R/(I_i+I_{i+1})); R = **5 ms** was optimal for cortex.
- Their data rules: ≥ 2000 ISIs, ≥ 5 spikes/s, fragments of 100 ISIs.

**Implementation here.** None (elephant not installed); trivial in numpy.

**Discrepancies with the plan.** LV formula exact. R must be refitted or set to 0 for fungi; fungal trains have far fewer
ISIs.

---

## 10. k-Shape

**Citation.** Paparrizos J, Gravano L (2015) k-Shape: efficient and accurate clustering of time series. *SIGMOD '15*. DOI
10.1145/2723372.2737793 (PDF read; page range unverified).

**Verified algorithm.**
1. SBD = 1 − max_w CC_w/√(R0(x,x)R0(y,y)) (eq. 9), range [0, 2]. Shifts are **zero-padded** (eq. 5); inputs z-normalised.
2. FFT padded to the next power of two ≥ 2m−1 (Alg. 1).
3. Shape extraction: align to the previous centroid, S = X′ᵀX′, Q = I − O/m, M = QᵀSQ; the centroid is the leading
   eigenvector (eq. 15, Alg. 2).
4. Random initial assignment; stop at no membership change or 100 iterations (Alg. 3).
5. Cost per iteration O(max{nkm log m, nm², km³}); k given; equal-length series.

**Installed.**
- tslearn 0.8.1 `KShape(n_clusters=3, max_iter=100, tol=1e-6, n_init=1, verbose=False, random_state=None, init='random')`
  (`USP/tslearn/clustering/kshape.py:96`); equal-sized series (:79); **`fit` does not z-normalise** (:200–256) but
  **`predict` does** (:298).
- aeon 1.4.0 `KShape(n_clusters=8, init="random", n_init=1, max_iter=100, tol=1e-6, z_normalise=True, n_jobs=1,
  random_state=None, verbose=False)` (`USP/aeon/clustering/_k_shape.py:90`); z-normalises in fit and predict (:125,
  :142); a port of kshape-python (MIT).
- aeon `TimeSeriesKShape` is **deprecated in 1.4.0 and removed in 1.5.0** (:266–272).

**Discrepancies with the plan.** None in the method. Use aeon `KShape`, or z-normalise before tslearn's `fit`.

---

## 11. HDBSCAN

**Citation.** Campello RJGB, Moulavi D, Sander J (2013) Density-based clustering based on hierarchical density
estimates. PAKDD 2013, LNCS 7819:160–172. DOI 10.1007/978-3-642-37456-2_14 (as cited in the sklearn docstring).

**Installed.** `sklearn.cluster.HDBSCAN(min_cluster_size=5, min_samples=None, cluster_selection_epsilon=0.0,
max_cluster_size=None, metric="euclidean", metric_params=None, alpha=1.0, algorithm="auto", leaf_size=40, n_jobs=None,
cluster_selection_method="eom", allow_single_cluster=False, store_centers=None, copy=False)` at
`USP/sklearn/cluster/_hdbscan/hdbscan.py:657` (1.7.2).
- `min_samples=None` defaults to `min_cluster_size` (:442, :778).
- Labels: noise −1, ±inf −2, NaN −3 (:539–541); `probabilities_` is 0 for those (:550).
- `metric="precomputed"` supported; no `outlier_scores_`.

**Discrepancies with the plan.** Confirmed; add the −2/−3 labels and the `min_samples` default.

---

## 12. MiniRocket

**Citation.** Dempster A, Schmidt DF, Webb GI (2021) MiniRocket: a very fast (almost) deterministic transform for time
series classification. KDD '21. DOI 10.1145/3447548.3467231 (per arXiv 2012.08791 v2). Verified **in code**.

**Verified (aeon 1.4.0, `USP/aeon/transformations/collection/convolution_based/_minirocket.py`).**
- 84 kernels from all C(9,3) index triples (:81), length 9; weights −1 with +2 at the three chosen positions (:268–269).
- Up to 32 dilations per kernel, exponentially spaced (:161–170); biases from golden-ratio quantiles (:185–188) of one
  **random training case's** convolution output (:419); PPV pooling only (:237).
- `MiniRocket(n_kernels=10_000, max_dilations_per_kernel=32, n_jobs=1, random_state=None)` (:83); `n_kernels` is really
  the feature count, rounded down to a multiple of 84.
- **`n_timepoints < 9` raises ValueError** (:115–119); float32; equal length required.
- `MiniRocketClassifier(...)` chains MiniRocket, `StandardScaler(with_mean=False)` and
  `RidgeClassifierCV(alphas=np.logspace(-3,3,10))` (`.../classification/convolution_based/_minirocket.py:139–143`).

**Discrepancies with the plan.** None checked; "logistic regression for large data" unverified.

---

## 13. Matrix-profile family (stumpy 1.14.1)

stumpy's default exclusion zone is m/4 (`USP/stumpy/config.py:19`) — the chains paper's; FLUSS and PMP use m/2.

### 13a. FLUSS / FLOSS

**Citation.** Gharghabi S, Ding Y, Yeh C-CM, Kamgar K, Ulanova L, Keogh E (2017) Matrix Profile VIII. ICDM 2017,
pp. 117–126; DOI 10.1109/ICDM.2017.21 (as cited in stumpy). PDF read; the DMKD 2019 extension not read.

**Verified.**
1. AC_i = number of NN arcs crossing i (Def. 5, Table I).
2. IAC = inverted parabola of height n/2, 2i(n−i)/n, "a special case of beta(2,2)" (fig. 4).
3. CAC = min(AC/IAC, 1) (eq. 1).
4. Table I line 17: "Set the **L** length in the beginning and end of CAC to 1".
5. Regime extraction (Table II): argmin, then exclude **5·L** either side. FLUSS "is not able to segment single gesture
   patterns".
6. L ≈ one period; results robust over a 4× range of L; ¼–½ of a period better post hoc.
7. FLOSS uses past-pointing arcs and a fitted-beta IAC_1D. A high CAC minimum means only "no evidence" of a change.

**Installed.** `stumpy.fluss(I, L, n_regimes, excl_factor=5, custom_iac=None)` → `(cac, regime_locs)`
(`USP/stumpy/floss.py:232`); n_regimes = changes + 1. `_iac` fits a beta (1000×1000 samples, seed 0) (:50–116). **Edges:
`CAC[:L*excl_factor]=1`, `CAC[-L*excl_factor:]=1`** (:178–179). `floss(...)` at :425. Docstring bug: the examples pass
`mp[:,0]`/`mp.P_` (distances) (:291, :297); it must be `mp[:,1]`/`mp.I_`.

### 13b. Pan Matrix Profile / SKIMP

**Citation.** Madrid F, Imani S, Mercer R, Zimmerman Z, Shakibay N, Keogh E (2019) Matrix Profile XX. ICBK 2019, pp.
175–182 (PDF read; DOI unverified). The PMP stacks matrix profiles for lengths L..U in steps of S; SKIMP visits lengths in
breadth-first order, ~99 % accurate at < 1 % of the work; motif heat-map. **No per-length normalisation in the paper.**

**Installed.** `stumpy.stimp(T, min_m=3, max_m=None, step=1, percentage=0.01, pre_scrump=True, normalize=True, p=2.0,
T_subseq_isconstant_func=None)` (`USP/stumpy/stimp.py:414/508`). Normalisation `1/(2*sqrt(m))`, clipped at 1 (:39).
`pan(threshold=0.2, normalize=True, contrast=True, binary=True, clip=True)` (:277); **`PAN_` returns those defaults, so
it is binarised** (:355). `percentage=0.01` → approximate scrump rows.

*Wave 3 (2026-10-15, W3-C critic F5 and the manager's evaluation):* scrump's approximate rows draw their diagonal
order from **numpy's global RNG** (`np.random.permutation`, `scrump.py:119, :1000, :1010` in the installed 1.14.1), so
an approximate profile is not reproducible beside any other thread that uses `np.random`, and a save/restore lock
around it is not process-wide (20/20 runs differed beside a second `np.random` user). `detection.pan_matrix_profile`
therefore computes exact profiles only (`stumpy.stump` per length; scrump saved only ~20 % there). And a *reading* the
paper does not make but a pan block invites: the length whose row stands out most is **not** an event's own length —
on real chains and the spiking recording every judged length repeated beyond amplitude-adjusted noise, and the
strongest fell on the longest or the shortest judged rung (`docs/prompts/blocks/reports/W3-evaluation.md`).

### 13c. Snippets

**Citation.** Imani S, Madrid F, Ding W, Crouter S, Keogh E (2018) Matrix Profile XIII: time series snippets. ICBK 2018
(10-page expanded version read; DMKD 2020 version not read).

**Verified.** Non-overlapping length-m subsequences (zero-padded); an MPdist profile of each against T — MPdist
(sub-length S) is robust to "spikes, warping, linear trends, dropouts, wandering baseline"; greedily add the profile that
minimises the area under min(profile, Q); a snippet's fraction = points where it is the overall minimum / (n−m+1);
change_k = Area_{k−1}/Area_k − 1, and **k is the peak of change_k** (§III.B: a small change_k means "adding the kth did
not add much explanatory power; thus, we should use a value of k corresponding to a peak"; Fig. 13 marks change_1
"undefined", so the paper has no k = 1 outcome); O(n²(n−m)/m); their example m = 200 with MPdist sub-length 70.
*(Corrected 2026-10-14 by the wave-2 manager from the W2-D critic's reading of the authors' 10-page PDF; this entry
first said only "k at the knee". `catalogue.snippets` uses its own largest-drop rule with a k = 1 outcome — named in
its docstring as an adaptation.)*

**Installed.** `stumpy.snippets(T, m, k, percentage=1.0, s=None, mpdist_percentage=0.05, mpdist_k=None, normalize=True,
p=2.0, mpdist_T_subseq_isconstant=None)` → `(snippets, indices, profiles, fractions, areas, regimes)`
(`USP/stumpy/snippets.py:153`, :332–339). m ≤ len(T)//2. Padding is **NaN** (:109). `s=min(ceil(percentage*m), m)`
(:101): **with the default, s = m and MPdist degenerates to z-normalised ED** — set `percentage` < 1.

*Added 2026-10-15 by the wave-3 manager, from the W3-D critic (`docs/prompts/blocks/reports/W3-D-mpdist.critic.md` F5):*
**MPdist** (Gharghabi et al. 2018, matrix profile XII; `stumpy.mpdist`) is the k-th smallest value of the joined
profile P_ABBA with **k = ⌈percentage × (|A| + |B|)⌉ — a share of the two series' sample counts, not of the pool**.
At a sub-length of half the shorter member, the default 5 % reads about the 9–11 % order statistic of the pool.
`Working/distances.py::mpdist_distance` (the Library's fourth distance) uses 25 % — about the pool's median — as a
named adaptation for members cut tight; its value equals `stumpy.mpdist` / √(2 × sub-length) to 7e-15 when no piece
is left out.

### 13d. Chains

**Citation.** Zhu Y, Imamura M, Nikovski D, Keogh E (2017) Matrix Profile VII: time series chains. ICDM 2017 (DOI
10.1109/ICDM.2017.79 not printed in the PDF — unverified). Left/right NNs with exclusion m/4; chain condition
RNN(C_i) = C_{i+1} and LNN(C_{i+1}) = C_i (Def. 12); ATSC and ALLC both O(n). **Installed:** `stumpy.atsc(IL, IR, j)`,
`stumpy.allc(IL, IR)` → `(S, C)` (`USP/stumpy/chains.py:10, :75`); IL/IR from `stump(...).left_I_` / `.right_I_`.

### 13e. DAMP

**Citation.** Lu Y, Wu R, Mueen A, Zuluaga MA, Keogh E (2022) Matrix Profile XXIV. KDD '22, pp. 1173–1182, DOI
10.1145/3534678.3539271; journal version DMKD 2023. **The paper text was not read** (the local 49-page PDF would not
render).
- Project page: 8 M points (17.36 h) in 22.3 s, "2,802 times faster than real-time"; DAMP "simply flags the first
  occurrence" of a repeated anomaly.
- Unofficial port of the authors' MATLAB (https://raw.githubusercontent.com/sihohan/DAMP/main/damp.py): the backward
  window starts at `2**nextpow2(8*m)` and doubles, stopping when the MASS minimum is below best-so-far; lookahead
  `2**nextpow2(16*m)` prunes future subsequences below best-so-far; **pruned positions get `left_mp[i] = left_mp[i-1] -
  1e-05`** — filler, not distances.
- stumpy has **no DAMP**; `stumpy.stumpi(T, m, egress=False)` exposes an exact but slow `left_P_`.

---

## 14. Teager / nonlinear energy operator

**Citations.** Mukhopadhyay S, Ray GC (1998) A new interpretation of nonlinear energy operator and its efficacy in spike
detection. *IEEE Trans Biomed Eng* 45(2):180–187. DOI 10.1109/10.661266. Choi JH, Jung HK, Kim T (2006) A new action
potential detector using the MTEO and its effects on spike sorting systems at low signal-to-noise ratios. *IEEE Trans
Biomed Eng* **53(4):738–746**. DOI 10.1109/TBME.2006.870239.

**Formulas.** ψ[x(n)] = x(n)² − x(n−1)x(n+1); threshold C·mean(ψ) (per a secondary source, arXiv:1812.04786). MTEO:
ψ_k = x(n)² − x(n−k)x(n+k), smoothed and noise-normalised per k, then the maximum over k. **Primary equations and C
unverified.**

---

## 15. Fungal context

**15a.** Adamatzky A, Schunselaar E, Wösten HAB, Ayres P (2023) Multiscalar electrical spiking in *Schizophyllum
commune*. *Sci Rep* 13:12808. DOI 10.1038/s41598-023-40163-z (**[main session]** correction 2). Read via bioRxiv
10.1101/2023.04.20.537646 v1.
- 1 Hz (logger averages ~600 readings/s), 16 electrode pairs, ~6 days, iridium-coated needles ~10 mm apart, ADC-24
  with a 78 mV range.
- **Very slow and slow spikes were detected by hand.** Fast spikes used the neighbourhood rule with **w = 20, δ = 0.01,
  d = 30** ("over 90%" by manual check) — `detection.spike_v1`'s defaults.
- Very slow: ~2573 s (~43 min), 0.16 mV, interval 2656 s. Slow: ~457 s (~8 min), 0.4 mV, interval 1819 s, rise ~89 s.
  Very fast: ~24 s, 0.36 mV, intervals 65 s–114 min, trains of ~6 spikes. (The abstract rounds these to hours, ~10 min
  and ~half a minute.)
- ~80 % of recordings show irregular wideband activity. Drift and artefacts are not analysed.

**15b.** Buffi M et al. (2025) Detection of electrical signals in fungal mycelia in response to external stimuli.
*iScience* 28(10):113484. DOI 10.1016/j.isci.2025.113484 (PMC12483595 read).
- PCB gold electrodes and a **Faraday cage**, whose absence "has been a common criticism and indicated as an experimental
  flaw of previous studies".
- Avoids agar, which "can be prone to the development of abiotic electrochemical gradients that can be mistakenly
  interpreted as true electrical signals".
- Without a cage, "people walking near the incubator or even the automatic closing of window shades affected voltage
  measurements".
- **DMSO alone reproduced the calcimycin "response"** (solvent–gold electrode interaction). One water control dropped
  for 5–6 h ("likely an artifact").
- STFT/PSD analysis; caution against reading extracellular spikes as action potentials.

**15c.** Buffi M, Kelliher JM, Robinson AJ, Gonzalez D, Cailleau G, Macalindong JA, Frau E, Schintke S, Chain PSG,
Stanley CE, Künzler M, Bindschedler S, Junier P (2025) Electrical signaling in fungi: past and present challenges. *FEMS
Microbiol Rev* 49:fuaf009. DOI 10.1093/femsre/fuaf009 (PMC11995700 read).
- Replicated the needle / fruiting-body method with an **uncolonised-substrate control**; spikes "ranging from above 50
  to up to −300 mV".
- The control and a detached fruiting body showed a ~0.005 Hz cyclic signal.
- **Opening the incubator door, people walking nearby and automatic window shades produced spikes in both fungus and
  control.**
- Proximity electrodes record field potentials that "can arise passively from either biological … and nonbiological
  sources (e.g. movement of ions on a matrix)"; reading them as action potentials is "misleading".
- Recommends Faraday cages, designed controls, attention to electrode and reference positioning, intracellular validation.

**What a detector should guard against (stated by these authors):** room and mechanical disturbances that appear
simultaneously on no-fungus channels; substrate (agar) electrochemistry; solvent–electrode effects after treatment
additions; a ~0.005 Hz cycle present without fungus; unshielded spikes of tens to hundreds of mV. Electrode
polarisation, humidity and temperature drift are **not** treated quantitatively in either paper.

---

## Sources not reachable

The PRE 2005 publisher page (the attached PDF was used instead), Wu 2014, the BEADS HAL preprint, Pasquale 2010, the RSOS
2022 journal page, the DAMP long-version PDF (could not render), the MiniRocket PDF text, the HDBSCAN chapter, the
Shinomoto 2003 full text, and the Mukhopadhyay & Ray and Choi full texts. Substitutes are noted inline.
