# W2-B — Library clustering methods `kshape` and `hdbscan`, and an SVD-entropy coherence score per family

Read [`00-common.md`](00-common.md) first. Commit prefix **`w2-b:`**. Plan: `docs/research/analysis-blocks-from-literature.md`
§5 rows 7 (k-Shape) and 8 (HDBSCAN), §4 A2 (SVD entropy as a coherence score); facts:
`docs/research/analysis-blocks-primary-sources.md` §10, §11 and §2 (step 4, eq. 17). The researcher chose **one
implementation, used by both the Library and Analyse** (§8 Q3): you build the implementation, in the Library's method
registry; W2-E exposes it in Analyse in round 2, so keep your methods free of any Analyse assumption.

## In plain words

The Library groups its 3,603 events into families with Ward linkage on z-normalised shapes. Two weaknesses: two
copies of the same shape cut a few seconds apart look different point by point (our stored event edges are often
off — 46 % of left edges are set by a cap), and Ward forces every event into some family. **k-Shape** compares shapes
after sliding one along the other to the best match, so misaligned copies match. **HDBSCAN** finds the places where
shapes crowd together and leaves the stragglers out as "no family" — no number of families to choose. The **SVD
entropy** of a family is one number saying how much its members are copies of one shape (low) versus a mixture
(high); it ignores amplitude, so it complements the amplitude spread the supervisor already reads.

## What to build

Read `docs/LIBRARY_STORAGE.md` §6 (the grouping engine and **§6.2, the checklist for adding a method — follow it to
the letter**), `Working/library/grouping/methods/__init__.py` (the protocol) and `ward.py` (the model to copy the
shape of: `shape_vectors`, the [0, 1] distance scale, `medoid`, the omission reasons).

1. **The shape-based distance** — `sbd(a, b)` and `sbd_matrix(X)` (batched FFTs, zero-padded to the next power of two
   ≥ 2m − 1, **not cyclic**) in `Working/distances.py` beside the other distances, plus the best shift. SBD lies in
   [0, 2]; the methods report it divided by 2 so it sits on the editor's [0, 1] cut scale as Ward's does (say so).
   Grep first: `Working/cross_channel.py::cross_correlate` exists — reuse its FFT core if it fits, else say why not.
2. **`kshape`** (`methods/kshape.py`, `applies_to=("shape-distance",)`): aeon 1.4's `KShape` (it z-normalises in
   fit and predict; **not** tslearn's, whose `fit` does not; not the deprecated `TimeSeriesKShape`) on the same
   resampled, z-normalised vectors Ward uses (`ward.shape_vectors`, 256 samples). Params: `k` (0 = auto: the best
   silhouette under SBD over k = 2…12 — the site's rule for Ward's proposal; or Calinski–Harabasz, the WSF paper's —
   pick one, name it, and record every k's score in the fit), `n_init` (default 10), `seed`, `omit_d` (a member
   further than this from its centroid, in normalised SBD, is omitted `past_cut`; default 0.5, Ward's spec 9.10 value).
   `merge_heights` → `[]` (no tree; say so). `medoid` → the member nearest its centroid by SBD.
3. **`hdbscan`** (`methods/hdbscan.py`, `applies_to=("shape-distance",)`): `sklearn.cluster.HDBSCAN` on a
   **precomputed normalised-SBD matrix** (default; a `distance` param also offers `euclidean` on the shape vectors =
   Ward's scale-invariant distance). Params: `min_cluster_size` (default 10 — the Library's existing ten-member floor),
   `min_samples` (0 = None = sklearn's default, which equals `min_cluster_size`), `cluster_selection_method`
   (`eom` | `leaf`), `cut` → `cluster_selection_epsilon`. Noise (−1) is **omitted with a new reason**
   `not_in_a_dense_family`; −2/−3 (infinite / missing values) are omitted with their own reasons. Add the new reasons to
   the engine's list in `Working/library/grouping/engine.py` beside the five existing ones, with a one-line meaning
   each. `merge_heights`: `[]` unless you can give the condensed tree's λ values faithfully — say which.
4. **Scale.** A square SBD matrix of n items costs n² memory: fit on at most `sample` items (default 5,000, seeded,
   recorded), assign the rest — k-Shape: `predict`; HDBSCAN: the cluster of the nearest fitted *member* within that
   cluster's largest core distance, else `not_in_a_dense_family` — and say in the fit which rows were fitted and which
   assigned. Time a 3,603-item fit (the Library's size) and a 20,000-item run (RQ1's pool) and report both.
5. **SVD entropy** — `Working/library/coherence.py::svd_entropy(member_matrix, align=True)`: rows = members
   (resampled, z-normalised); if `align`, shift each row to its best SBD match against the medoid first (zero-padded);
   p_i = σ_i / Σσ_j, H = −Σ p_i ln p_i; return `{svd_entropy, svd_entropy_norm (= H / ln min(P, L)), n_members,
   aligned, rule}`. Check eq. 17's normalisation in the primary-sources file and follow it; if it squares the singular
   values, so do you, and say so. Sample at most 2,000 members (seeded) and say so when it does.
6. **Expose coherence on the Family page's data** — the one webui file you may touch: in `webui/server/library.py`,
   `_family_detail` gains a `coherence` field from `svd_entropy` (computed on demand, cached the way the module caches
   other per-family numbers; an exception is a red error card, never a silent blank — `CLAUDE.md`). Test it the way the
   existing `tests/test_webui_library*.py` tests read a family. The client side is W2-F's.

## Deliver

`Working/distances.py` (sbd), `Working/library/grouping/methods/kshape.py`, `.../hdbscan.py`, registration in
`methods/__init__.py` per §6.2, `engine.py` (the new omission reasons only), `Working/library/coherence.py`,
`webui/server/library.py` (`_family_detail` only). Tests: `tests/test_library_grouping_methods.py` (extend — §6.2 item
6), `tests/test_sbd.py`, `tests/test_library_coherence.py`, and the family-detail test.

## Acceptance

- [ ] SBD: a shape against its own shifted copy (zero-padded shift, not wrapped) scores ≈ 0 with the right shift; against
      its negative ≈ 1 on the normalised scale; matches a direct O(m²) loop to 1e-10 on random pairs.
- [ ] Three synthetic families (a drop with slow recovery, a sharkfin, a square pulse), each member **randomly shifted
      by up to 20 % of its length** and scaled, on AR(1) noise: `kshape` recovers them (adjusted Rand ≥ 0.9) where
      `ward` on the same vectors does measurably worse — show both numbers in a test or the report.
- [ ] The same three families plus 30 % pure-noise members: `hdbscan` recovers the three and omits the noise as
      `not_in_a_dense_family` (most of it); on **pure noise only** it returns no family, or says the families it found
      are unstable — never three confident families.
- [ ] `svd_entropy`: k scaled copies of one shape → near 0; a 50/50 mix of two shapes → clearly higher; alignment
      lowers it for shifted copies.
- [ ] Both methods go through `run_grouping` end to end, with omission reasons, and the recipe hash changes when a
      parameter does (§6.2 item 8).
- [ ] `ward`'s behaviour and its tests are unchanged.
