> Filed by the manager session, 2026-10-14 23:30 — the final message of implementer agent `a5a78efe8b36c0a92`,
> resumed for fix round 1 on branch `worktree-agent-a5a78efe8b36c0a92` (`e4ff42f` red, `48710ae`), verbatim.

# W3-D fix round 1 report

## In plain words

All eight of the critic's points are fixed, and every test listed below passes.

- The Family page will no longer print "within the cut" beside an MPdist edge. That was a yardstick from a different scale, like checking a temperature against a speed limit. The symbolic edges had the same problem and are fixed too.
- *Add N matches* now reports the pairs MPdist could not compare. It gives one sentence for the page, plus the details.
- The noise comparison is now context only, not a pass/fail. It was biased: pure noise looked "closer than noise" too often, and troughs looked like noise.
- MPdist now reads roughly the middle of its piece-by-piece distances rather than the best 10 %. The tests and the wording now say plainly that at realistic noise it cannot tell a drop from a square dip.

## What changed, per item

**F1: `within` on the face.**
- `_edge_payload` in `webui/server/library.py` now returns `threshold: None`, `within: None` and `footing` for any function in `matching.OFF_CUT_FOOTING`.
- **Symbolic edges change on purpose.** I checked, and the symbolic distance is SAX MINDIST without the √(n/w) length factor, so it was never on the seed cut's footing. It now joins `OFF_CUT_FOOTING` with its own footing sentence (`SYMBOLIC_FOOTING`). Two visible consequences: the Family page drops the cut and "within" for symbolic edges, and `scale_readout`'s symbolic cells now carry `within`/`threshold` None. The commit message says so.

**F2: refusals reach the response.**
- `post_run_matches` now returns `edgesRefused` (each `{detection_id, member_id, function, reason}`) and `refusalSummary` (one sentence, or None).
- The audit `detail` gets `edges_refused`, the count.
- An exemplar under 16 samples gives one entry, not one per pair: `detection_id` None, `member_id` the exemplar's, and `pairs` = n. Its sentence reads "MPdist compared none of the N pairs: the exemplar cannot be compared … The other distances were written."
- Ordinary refusals read "mpdist refused 1 of 4 pairs (too short); their other distances were written."

**F3: no verdict from the null.**
- `mpdist_null` now returns `{value, null_median, null_p05, draws, note, rule}`. `beyond_noise` and `MPDIST_NULL_MARGIN` are gone.
- `MPDIST_NULL_NOTE` says the numbers are context, not a verdict, and gives the bias: coloured noise sits below its own null median in 65–70 % of pairs, and troughs sit at their null (the cubic-trend blind spot).
- The docstring names the follow-up: an empirical same-recording null via `Working/background_null.py` (W3-G).
- No rule text says "across a family" any more.

**F4: `percentage` default is 0.25.**
- The docstring calls it an adaptation (decision 11) and quotes the critic's measurement: at noise sd 0.2 and 150–454 samples, drop and square dip are confused 3–33 % of the time at 0.25, against 20–63 % at 0.05. The extra-baseline case is unchanged.
- New tests pin what MPdist does on AR(1) φ 0.97 and detrended random-walk backgrounds, at noise sd 0.1 and 0.2 of the event's depth (300 samples, 10 pairs):
  - square / same-shape ratio is above 1.2 at sd 0.1 and below 1.35 at sd 0.2, and at least 10 % of square pairs fall inside the same-shape spread;
  - extra baseline / same-shape ratio stays between 0.8 and 1.25 at both noise levels.
- My own measurements:

| Background | Ratio at sd 0.1 | Ratio at sd 0.2 |
|---|---|---|
| AR(1) | 1.36 | 1.05 |
| Random walk | 1.43 | 1.23 |

- `MPDIST_TOOLTIP` and `MPDIST_RULE` now say MPdist does not reliably tell shapes apart at realistic noise.

**F5: the "5 %" wording.**
- `MPDIST_RULE` and docstring step 5 now say k is a share of |A| + |B|, not of the pool.
- `mpdist_detail` returns `pool_share` = k / pool. At the new default it is 0.45–0.50 of the pool, roughly the median closest-piece distance (it was 0.09–0.11 at 0.05). A test pins it between 0.40 and 0.56.

**F6: `missing`.** Counting refusals on the fly turned out to be cheap: it is a length, NaN and flat check per lacking member, via the new `mpdist_member_refusal`. So for MPdist, `scale_readout` now reports `missing`, `refused`, `not_computed` and `missing_rule` (`MPDIST_MISSING_RULE`: "…not_computed (added before MPdist existed — run Add N matches again…)").

**F7 / F8 nits.**
- The compile note now mentions the bridge's existing `stumpy.stump` warm-up in `webui/server/app.py`, and that the route runs in the threadpool. No new warm-up was added.
- The "names the three distances" comment is fixed.
- The importer change was the smaller option: `Pipelines/import_drop_motifs/importer.py` now takes `IMPORT_DISTANCES` (the registry minus mpdist) and refuses mpdist in words.

## Commits

- **Red, `e4ff42f`** (tests only):
  - conda: 9 failed, 30 passed (null verdict, follow-up named, default order statistic, two coloured-noise tests at ratio 1.08 plus the tooltip, recipe percentage, exemplar refused once, off-cut footing set, importer);
  - venv: 3 failed (`threshold 6.0 is not None`, `KeyError 'edgesRefused'` twice).
- **Green, `48710ae`.**
- **Existing tests I changed deliberately** (stated in the red commit's message):
  - the footing test now compares with stumpy at `MPDIST_PERCENTAGE`;
  - the white-noise extra-baseline bound went from 0.25 to 0.3, because at 0.25 the value reads a deeper order statistic (measured 0.24);
  - the recipe pin went from 0.05 to 0.25;
  - the old null test, which read `beyond_noise`, is replaced.

## Test counts

- **conda python, 321 passed:** `test_mpdist_distance` (now 24 tests), `test_import_drop_motifs`, `test_distances`, `test_library_seed_edges`, `test_library_edges`, `test_block_standard`, `test_adapter_spec`, `test_import_boundaries`, `test_templates`.
- **webui/.venv python, 14 passed:** `test_webui_mpdist_edges.py` (new, 3) and `test_webui_library_edges.py` (11). Command, run from the worktree root: `"/c/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" -m pytest tests/test_webui_mpdist_edges.py tests/test_webui_library_edges.py -q -p no:cacheprovider`. The warnings are the existing "event loop is closed" and job-persistence messages at teardown.

## Paste-ready for W3-F

1. **Family page, the null.** If you show `mpdist_null`, print it as "noise of this colour scores {null_median} (5th percentile {null_p05})" beside the value, with `note` (`MPDIST_NULL_NOTE`) as its tooltip. Show no verdict, colour or badge from it, and draw no family-level "beyond noise" either. The MPdist value's tooltip is `Working.distances.MPDIST_TOOLTIP`, verbatim.
2. **The `edgesRefused` toast.** After *Add N matches*, if `refusalSummary` is not null, show it as a neutral (not error) line on the result toast or card. Expandable detail: one row per `edgesRefused` entry, giving its member (`m-{member_id}`), detection and `reason`. An entry with `detection_id: null` is the exemplar refusing every pair; show it once, using its `pairs` count.
3. **`Edges.tsx`.** When `within === null`, print "—" for the cut and colour the row neutral. Do not use the purple "beyond the cut" colour: today `Edges.tsx:39` colours any falsy `within` purple. Show `footing` as the tooltip on the "—". This now applies to both `mpdist` and `symbolic_sax`.
4. **The scale read-out table.** Add an `mpdist` column (`n`, `median`, `min`, `max`; `within` is null). Where `refused > 0`, show "k could not be compared". Where `not_computed > 0`, show "k added before MPdist — run Add N matches again" (`missing_rule` as the tooltip). The `symbolic_sax` cells also now have `within: null`.

## What I could not do

Nothing is left undone. Two smaller things:
- The F4 measurements are synthetic. On real recordings, it is still worth checking MPdist values on a few trough families beside `mpdist_null`, and how many real members are refused.
- The `"1 of 4"` route test inserts its 12-sample match directly into the database. That shows the response wiring; it is not a real seed-search match.
