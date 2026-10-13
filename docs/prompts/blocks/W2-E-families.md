# W2-E — `catalogue.shape_families` and `interrogation.event_families`: the Library's clustering, inside a chain

Read [`00-common.md`](00-common.md) first. Commit prefix **`w2-e:`**. **Round 2 of wave 2:** you start from a `main`
that already holds W2-A (`catalogue.event_windows`) and W2-B (the `kshape` / `hdbscan` Library methods, `sbd`,
`svd_entropy`). Read their reports in `docs/prompts/blocks/reports/W2-A-*.md` and `W2-B-*.md` first and **import**
their functions — do not write a second SBD, a second window cutter or a second clustering call. Plan:
`docs/research/analysis-blocks-from-literature.md` §5 rows 7–8 ("Chain") and §8 Q3 (one implementation, both
surfaces).

## In plain words

The Library can now sort events into families with Ward, k-Shape or HDBSCAN. These two blocks let a chain in Analyse
do the same thing on the events **it** just detected, with the very same code. The second one is the important one:
it writes each event's family onto the event, so the Intervals block after it can time each family separately — "do
family A events come every 40 minutes and family B every 3 hours?" in one straight chain. That is the supervisor's
spiking-families question as a ready-made template.

## The blocks

1. **`catalogue.shape_families`**, WindowSet → Grouping (`page_name="Shape families"`). Shape vectors: from
   `shape_file` when Trace shape ran, else sliced from `x` (channel-absolute starts) and resampled + z-normalised with
   `ward.shape_vectors` — the Library's own preparation, so a family here and a family in the Library mean the same
   thing. Clustering: `Working.library.grouping.engine.run_grouping` (or the method objects directly if the engine
   insists on item dicts you cannot honestly build — say which and why), `basis="shape-distance"`.
   Params: `method` (choices = the registered methods whose `applies_to` includes `shape-distance`, read from the
   registry at import, so a future method appears without an edit), and that method's own params flattened with a
   prefix or passed as `method_params` JSON — pick the one the Analyse param form can render (read
   `webui/client/src/analyse/` param rendering: it renders `ParamSpec`s, so flattened `ParamSpec`s are probably right;
   name the choice). Labels: family 1…K; an omitted window is −1 with its reason counted in `meta["omitted"]`.
   **Why not extend `catalogue.shape_cluster`:** read its docstring — it is a pool / training-split / kept-tree block
   for RQ1; write the one-paragraph reason in your module docstring.
2. **`interrogation.event_families`**, SpanSet → SpanSet (a feature block, `page_name="Event families"`): cut each
   event's waveform with W2-A's core function (anchor/length params as `catalogue.event_windows`), cluster as above,
   and add `family` (−1 = none), `family_omit_reason`, `family_distance` (normalised SBD or the method's own distance to
   its family's medoid/centroid). `write_group` (**default true here** — timing per family is this block's reason to
   exist) sets `group = family`, prefixing an upstream group the way `interrogation.trains` does (`"<upstream>/<family>"`,
   upstream kept in `group_upstream`) — import or share that helper, do not re-write it. Events the cutter left out
   (too near a span end) are `family = −1`, reason `no_window`.

Both: `meta` carries `method`, its params, `k`, family sizes, omissions by reason, **`svd_entropy` per family**
(W2-B's `svd_entropy`, aligned), `exemplar_windows` / `exemplar_events` = each family's **medoid member** (a member,
never an average — `BLOCK_INTEGRATION.md` §2) with the rule, timing, `rules`. Cost: HDBSCAN/k-Shape on a square SBD
matrix — declare `estimate` (reuse W2-B's measured timings) and refuse past W2-B's `sample` cap in words or assign the
rest as W2-B does.

## The template `event_families`

In `tests/test_template_event_families.py`: the `noise_threshold` template's steps (read `webui/server/templates.py`;
do not edit) → `interrogation.event_shape` → `interrogation.event_families` (`method="hdbscan"`, defaults) →
`interrogation.intervals`. On a synthetic recording with two event shapes at two different rhythms (e.g. sharkfins
every 40 min, square dips every 3 h) on an AR(1) background, the Intervals output must show the two rhythms per family.

## Deliver

`Working/Catalogue/shape_families.py` (or the core split the two blocks need), `Adapters/catalogue_shape_families.py`,
`Adapters/interrogation_event_families.py`, `tests/test_shape_families.py`, `tests/test_adapter_shape_families.py`,
`tests/test_adapter_event_families.py`, the template test.

## Acceptance

- [ ] On the same items, `catalogue.shape_families` with `method=ward` reproduces `run_grouping`'s Ward assignment
      exactly (one implementation, two surfaces — the researcher's Q3).
- [ ] The two-shapes-two-rhythms template recovers both families (adjusted Rand ≥ 0.9 against truth) and Intervals
      reports each family's own median gap within 10 %.
- [ ] **No-structure check:** events whose waveforms are phase-randomised copies of AR(1) noise → HDBSCAN puts most in
      no family, and nothing downstream claims family-level rhythms that are not there.
- [ ] An upstream `group` survives as `group_upstream`; `write_group=false` leaves `group` untouched.
- [ ] Exemplars are members; `svd_entropy` is reported per family.
- [ ] Both blocks pass `tests/test_block_standard.py` and `tests/test_adapter_spec.py`.
