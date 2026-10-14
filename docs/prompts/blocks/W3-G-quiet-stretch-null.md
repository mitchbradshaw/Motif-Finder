# W3-G — A fairer noise test for families: the recording's own quiet stretches as the null, and a trend-kept null for k-Shape

Read [`00-common.md`](00-common.md) first, including **both** "Lessons" sections. Commit prefix **`w3-g:`**. **Round 2 of
wave 3**, after W3-B has merged: you reuse its quiet-stretch sampler (`Working/background_null.py`, below). The
researcher chose this follow-up on 2026-10-14: `docs/prompts/blocks/reports/W2-evaluation.md`, "What the researcher
should decide", question 5, option (a). **This prompt hands you** the Library-side functions of
`webui/server/library.py` named in "Deliver" (the exception in `00-common.md`'s "Do NOT touch").

Read before you design:
- `W2-evaluation.md`, its Library section and its `event_families` section;
- the W2-B reports, critics and fix reports (`reports/W2-B-library-methods*.md`), which hold how today's noise tests
  were chosen and measured;
- the W2-E reports (`reports/W2-E-families*.md`);
- `Working/library/coherence.py` (`SMOOTH_CAVEAT`);
- `Working/library/grouping/methods/hdbscan.py` (the per-family test, `_null`) and `kshape.py` (its plain phase null,
  `trend_kept_surrogates`);
- `Working/Catalogue/shape_families.py` (`UNTRUSTED_NULLS`, `EVENT_FAMILIES_EXCLUDED`, the `~noise_like` keys);
- W3-B's report, for the sampler's contract.

## In plain words

To ask "is this family more alike than chance?", the Library makes fake families and checks whether the real one is
tighter. Today a fake member is the real member scrambled, keeping its slow curve so the fake has the same "colour" of
noise. That works for spiky shapes and fails for smooth ones. For a broad hump or a slow ramp that fills its window,
the slow curve *is* the shape, so the fakes look like the real thing and a perfectly good family reads "noise-like".
On rec 542's drop chain, wave 2's largest family failed for exactly this reason.

The fairer test cuts the fakes from the recording itself, from stretches where nothing was detected: "would windows
of this recording's own quiet background crowd together this tightly?". A second, smaller fix gives k-Shape the same
kind of test HDBSCAN has. Its present one missed crowds of random-walk "events", so the families block in Analyse does
not offer k-Shape at all.

## What to build

1. **Quiet-stretch windows for Library members.** For each family's members, cut background windows:
   - from **each member's own recording**, at **its own length**, at seeded random positions;
   - overlapping no Library member on that recording. State whether detections count as "events" too, and why.
   - Use W3-B's sampler (`Working/background_null.py`) for the cutting. Do not write a second one; if its contract does
     not fit, extend it there, compatibly, and say how.
   - The engine stays free of UI and file paths: the caller passes a loader, the way the bridge's `_grouping_items`
     hands waveforms in today. Report per family how many seconds of background were available.
   - **Fall back to the trend-kept null, and say so per family**, when a recording is mostly events, or a member's
     recording is not on disk (count those, as `notOnDisk` does).
2. **The verdicts use it.** HDBSCAN's per-family test, k-Shape's (item 3) and the coherence null (`svd_entropy`'s
   `null_median` / `null_p05` / `beyond_noise`) take the quiet-stretch null as **the verdict**. The trend-kept result
   stays beside it, with `SMOOTH_CAVEAT`. Each verdict's text names its null and how much background it had (`null_kind`,
   `why`), because the pages already show that text.
   - Keep the 0.9 margin unless you measure a reason to move it.
   - Do not change which coherence variant heads the page: σ² against eq. 17 is the researcher's open question 4.
3. **k-Shape gets a trend-kept null and the quiet-stretch null**, replacing its plain phase null. The plain one turns a
   coloured window's trend into a wiggle, so its fake crowds are too loose.
   - Re-run the W2-E critic's no-structure test **at the defaults**: cut events of pure random walk and AR(1) φ
     0.95–0.99, at n = 200 and 1,000, through `interrogation.event_families`. Assert that no Intervals key reaches
     Intervals unmarked.
   - If it passes, remove k-Shape from `EVENT_FAMILIES_EXCLUDED` and `UNTRUSTED_NULLS`, so Analyse offers it again. If
     it fails, keep it excluded and write the measured reason into `UNTRUSTED_NULLS`.
4. **The Analyse blocks** (`catalogue.shape_families`, `interrogation.event_families`) draw their quiet-stretch windows
   from the chain's own trace: the span's stretches that hold no event, via the same sampler. Their `~noise_like` keys
   then follow the new verdict.
   - Add no new parameter unless you must: one changes every saved recipe's hash (plan §7.4). If you add a choice of
     null, default it to the new one and say why.
5. **Behaviour you change on purpose** — say each in a commit message:
   - groupings saved before this keep the fit summary stored with them;
   - new runs, and the Family page's live coherence, use the new null, so some existing families' badges will change;
   - tests that pinned the old verdicts are updated deliberately, not loosened.
6. **Cost.** Background reads are memory-mapped slices, but the Family page computes coherence inside a GET.
   - Measure a family-detail request: a 2,000-member family, cold and cached.
   - Measure a regroup of the real Library's size (3,616 items, per method).
   - Fold the extra into each method's existing estimate (W2-B decision 13: estimated before the job starts).

## Deliver

`Working/library/coherence.py`, `Working/library/grouping/methods/hdbscan.py`, `Working/library/grouping/methods/kshape.py`,
`Working/background_null.py` (compatible extensions only), `Working/Catalogue/shape_families.py`,
`Adapters/catalogue_shape_families.py`, `Adapters/interrogation_event_families.py`, and in `webui/server/library.py`
**only** `_grouping_items`, `_family_coherence` and the loader you pass the engine. Tests:
`tests/test_library_background_null.py`, plus the existing method, coherence and families tests, updated
deliberately. No client file: the pages show the verdict text the core returns. If a page needs more than that, put it
in your report for a follow-up.

## Acceptance

- [ ] Smooth shapes: a family of broad humps, and one of slow ramps, on a background that holds no such shapes →
      beats the quiet-stretch null, where the trend-kept null calls it noise-like. Show both numbers.
- [ ] No structure, at the defaults, on 200 and 1,000 items: "families" whose members are themselves windows cut from
      quiet stretches never beat the quiet-stretch null. Through `interrogation.event_families`, no Intervals key is
      unmarked.
- [ ] k-Shape: random-walk crowds of cut events are flagged; the `EVENT_FAMILIES_EXCLUDED` decision follows the
      measurement, either way.
- [ ] A recording that is mostly events, and a member not on disk: the fallback is said per family, never silently.
- [ ] Every verdict's text names its null and its background seconds.
- [ ] The families tests, `tests/test_block_standard.py` and `tests/test_adapter_spec.py` pass. Run the Library's
      webui tests with the venv interpreter (`00-common.md`) and say so.

**How the manager will judge it** (no template, so no ship verdict; a report):
- Re-run `W2-evaluation.md`'s Library table with the new null: families beyond noise per method (Ward, HDBSCAN eom /
  leaf, k-Shape k = 20).
- Re-run the per-family verdicts of `event_families` on rec 6's and rec 542's chains, where wave 2 found a
  smooth-shape blind spot.
- `event_families`' template status is **not** re-judged: the researcher chose not to re-test it.
