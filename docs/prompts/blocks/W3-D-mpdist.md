# W3-D — `mpdist`: a fourth Library distance, shared sub-shapes at native speed (Gharghabi et al. 2018, matrix profile XII)

Read [`00-common.md`](00-common.md) first, including **both** "Lessons" sections. Commit prefix **`w3-d:`**. Plan:
`docs/research/analysis-blocks-from-literature.md` §6 ("MPdist as a fourth Library distance … a small, direct addition
to RQ3's three distances") and §7.1 (wave 3, optional). Read `docs/rq_roundA/RQ3-identity-under-scale.md` — the question
this serves — and `Working/library/matching.py` (how an accepted match becomes members and one `motif_edge` per
distance function). **Round 2 of wave 3.** Optional in the plan; the researcher chose to build it (2026-10-14).

## In plain words

RQ3 asks whether a slow, stretched-out copy of a motif is "the same motif" as a fast one. The Library compares two
members either after stretching both to one length (the scale-invariant distance, which the Library groups by) or at
their own lengths (the native-length control). **MPdist** compares two members by the short pieces they share at their
own speed: it slides a short window along both, finds each piece's closest partner in the other, and reads off one of
the larger of those closest distances. Two members of different lengths — one with an extra tail of baseline, one cut
tighter — can still be close. So it answers *"do these share their sub-shapes?"*, which neither existing distance does.
It does **not** answer *"is one a time-stretched copy of the other"*: a piece of a 0.8× copy is itself squeezed. The
read-out must never imply otherwise.

## The change

1. **`Working/distances.py::mpdist_distance(x1, x2, …)`**: the MPdist sub-length as a fraction of the **shorter**
   member (`sub_frac`; propose the default and justify it — W2-D's snippets uses 0.35 of a piece, the paper's example
   70 of 200), stumpy's `percentage` (0.05, its default: which order statistic of the joined profile is read — say what
   it does). W2-D's numba kernel (`Working/Detection/matrix_profiling/snippets.py::mpdist_profiles`, with
   `sub_length`) computes the MPdist profile of pieces against a whole series, not the distance between two members;
   `stumpy.mpdist(T_A, T_B, m)` (installed) is the pairwise form. Use it, or derive the pair from the kernel if that is
   cleaner — say which and why (W2-D measured that stumpy's form holds a j × n matrix per piece: harmless for members of
   minutes, fatal for hours). Reuse `sub_length` so "the sub-length" means one thing in both blocks.
2. **One footing.** RQ3's read-out puts every distance on the native length's footing (`d·√(m/L)`). Put MPdist on a
   stated footing — e.g. ÷ √(2 × sub-length), so it lies in [0, 1] like a normalised distance — and pin it in a test.
3. **Register it.** `DISTANCE_MPDIST = "mpdist"` in `DISTANCE_REGISTRY`. `tests/test_distances.py` pins the registry to
   three names; this change deliberately makes it four — update that test and **say so in the commit message**
   (CLAUDE.md rule 2). Then follow the consequences: `matching.resolve_run_matches` writes one edge per distance
   function, so *Add N matches* now writes a fourth edge per pair. Check every reader of edges per distance
   (`webui/server/library.py`: `DISTANCE_LABELS` ≈ line 1397, the edges histogram ≈ line 692, the Family page's scale
   read-out) and whether each lists distances from the registry or by name.
4. **Members it cannot compare** — shorter than 2 × the sub-length, flat, mostly NaN — are refused in words or fall back
   to a stated rule; never a silent 0 or NaN that reads as "identical" or "missing".
5. **Cost.** Measure a family of 200 members against its medoid (the Family page) and the *Add N matches* case (each
   accepted pair once).

## Deliver

`Working/distances.py`, `tests/test_mpdist_distance.py`, `tests/test_distances.py` (the registry pin, deliberately), any
`Working/library/` change resolving edges needs, and **one line handed to you in `webui/server/library.py`**: the
`DISTANCE_LABELS` entry ("shared sub-shapes (MPdist)" or better). Anything else the pages need goes in your report for
W3-F — do not edit `webui/` otherwise.

## Acceptance

- [ ] A shape and the same shape with 30 % extra baseline on one side: MPdist near 0, scale-invariant distance clearly
      larger.
- [ ] Two different shapes (a drop with slow recovery, a square dip): MPdist large.
- [ ] A shape and its 0.8× time-compressed copy: report what MPdist says, and word the read-out's tooltip so it cannot be
      read as a scale verdict.
- [ ] Coloured-noise pairs (AR(1) φ 0.99, detrended random walk): where they sit on the footing — the null the read-out
      should print beside the value (wave 2: every distance needs its noise level beside it).
- [ ] MPdist(a, b) = MPdist(b, a); NaN, flat and too-short members refused in words.
- [ ] Registered; `resolve_run_matches` writes the fourth edge in a temp-database test; the existing edge tests updated
      deliberately and passing.
- [ ] Your report gives the manager the RQ3 file's new line in plain words.
