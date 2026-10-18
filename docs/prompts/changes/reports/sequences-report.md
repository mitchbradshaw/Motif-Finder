# sequences — report

WORKTREE: `C:\Users\mmebr\Documents\CNN\.claude\worktrees\agent-a360deb213ff7c7e2`
BRANCH: `worktree-agent-a360deb213ff7c7e2` (base `9504e38`)

## 1. Assumed

- **Kept sequences are `origin = 'machine'`**, `source_kind = 'library_join'`. A join is a rule computed from members
  rather than a span a person drew, so it is a machine claim, like the detector CSV's sequences. The person's choice is
  recorded in the provenance note.
- **Provenance goes in `sequences.source_store`** as JSON (rule, gap, tolerance, min length, motif grouping, recording,
  date). The label key goes in `source_ref`, and `sequence_key = join:r<recording>:<member ids>` is the identity. No
  schema change was needed: `sequence_members` already holds ordered member refs.
- **Families: a keep that writes anything saves a new sequence grouping** (`method = basis = 'label-chain'`, through
  `writes.write_human` as `POST /groupings` does). It covers every kept sequence, with `family_label` = the label key.
  It is then the newest sequence grouping, so the existing atlas, `/sequence-families` and `/family/{id}?unit=sequences`
  reads show it unchanged. A keep that adds nothing saves no grouping. Each such keep leaves one more grouping in the
  picker: these are snapshots, not edits in place.
- **The label key is joined with `.`**, e.g. `F-01.F-02.F-01`. The family is named `F-01 → F-02 → F-01` on the page. I
  did not use `>` because a hash route percent-encodes it and the id would stop matching. I did not use `-` because the
  labels themselves contain one.
- **Only kept (`library_join`) sequences go into label-chain families.** Imported sequences (`sequence_csv`) stay in
  their own distance groupings. The new family page draws those families too, since it replaces the placeholder for
  every sequence family.
- **Member labels come from the newest motif grouping** (or one that is named), from `grouping_assignments` where
  `family_id IS NOT NULL`. This is the same read `_compositions` uses, so hand edits are not applied there either. Two
  members on the identical span count as one element (the lower id).
- **There are two gaps.** The rule and the family page use end→start seconds. `sequence_members.gap_before` keeps the
  schema's onset→onset meaning. `read_sequences` recomputes end→start from the stored spans, so the family route's gaps
  are the joiner's gaps.
- **Overlapping members join** (their gap is negative).
- **The adaptive rules ignore the gap and tolerance numbers.** The control hides those numbers for them.
- **Remove a sequence from its family** is an ordinary hand edit: `POST /hand-edits` with
  `contentHash = "seq:<sequence_key>"`, `kind = remove_member`, scoped to the sequence grouping. Restore is
  `DELETE /hand-edits/{id}`. Nothing is deleted.
- **Send to Review** sends the family's unjudged ELEMENTS (motif members) as the family's queue through
  `Working.review.family_queue`, the motif family page's door. This needed a fourth route,
  `POST /sequences/{id}/review`.
- **The atlas's "≥ N members" filter does not apply to a label-chain grouping.** Its families are usually one sequence
  each, so the default of 10 would have hidden every one.
- **With no `recording_id`, a preview joins the busiest channel.** `candidates_only` returns just the picker list,
  without joining.

## 2. In plain words

On the Library atlas, switching the unit to sequences now shows a **Build sequences** card. You pick a channel and a
gap rule, and Preview lists the runs of neighbouring Library motifs it would join. Each run is drawn as a strip of
coloured blocks (one colour per motif family) with the gaps between them to scale, and each label chain (for example
F-01 → F-02 → F-01) gets a count. Nothing is saved until **Keep these**. After that the atlas shows one family per label
chain, and each family has a real page: the strips, the typical shape at each position, gap and length histograms,
example traces, and a rail for verdicts, removing a sequence and sending it to Review.

## 3. Files

Created:
- `Working/library/sequences.py`: the joiner, label key, edit distance, keep, read-back and label-chain assignments
  (core, no UI imports).
- `webui/client/src/library/BuildSequences.tsx`: the atlas card.
- `webui/client/src/library/SequenceStrips.tsx`: strips, the colour key, and the example trace with bands (d3).
- `webui/client/src/library/SequenceFamilyPage.tsx`: the sequence family page, which replaces the placeholder.
- `webui/smoke_pages/zzzzzzzzzzz_sequences.json`: four smoke states.
- `tests/test_library_sequences.py` (conda) and `tests/test_webui_library_sequences.py` (venv).

Modified:
- `Working/library/importers/sequences.py`: the INSERT pair became the public `insert_sequence(conn, row, members)`.
  `_write_sequence` calls it, and behaviour is unchanged (its tests pass).
- `webui/server/library.py`: one import line, plus one block before the "WRITES AND JOBS" banner holding four routes and
  their helpers. No existing function was edited.
- `webui/client/src/library/AtlasPage.tsx`: imports the card, takes `setSeqGid` from the existing hook, renders the card
  in the sequences branch, and lifts the min-members filter for a label-chain grouping inside `SequenceAtlas`.
- `webui/client/src/library/FamilyPage.tsx`: one import, one render line (placeholder → `SequenceFamilyPage`), and the
  `SequenceFamilyPlaceholder` function removed. The motif-family code is untouched, so it should meet
  `library-family-actions` cleanly.
- `webui/client/src/library/index.tsx`: the `sequences` case, implemented as a `SequencesRedirect` that replaces the URL.
- `webui/client/src/api.ts`: **append-only**, one block at the end (types plus `previewLibrarySequences`,
  `keepLibrarySequences`, `getLibrarySequenceFamily`, `sendSequenceFamilyReview`). No existing function was touched.
- `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md`: one appended Log line (the researcher called this a possible RQ1
  precursor).

## 4. What was built

1. **The joiner's rule.** The members of one recording (one channel) that carry a family label in the motif grouping
   are ordered by start. Under the **fixed** rule, two neighbours join when the time from the end of the first to the
   start of the second is at most `gap_s + tol_frac × the shorter member's length`. The default is 0 s + 10 %, and
   overlapping members join. Under **adamatzky** or **logisi**, the members' onset times go to
   `trains.find_trains(rule, min_events=min_len)` and each train is a sequence. Runs shorter than `min_len` (default 2)
   are dropped, and there is no maximum. The result is deterministic, NaN-free and writes nothing. A detection with no
   family neither joins nor bridges two members.
2. **Routes** (`/api/library/...`):
   - `POST /sequences/preview {recording_id?, rule, gap_s, tol_frac, min_len?, grouping?, candidates_only?}` returns
     the strips with times relative to each sequence's start, the gaps, colours per label (the motif atlas's order), a
     count per label chain, `kept` flags, the picker `candidates`, and a `note` when the join made nothing. It writes
     nothing.
   - `POST /sequences/keep` re-runs the same join on the server, keeps the result, and saves the label-chain grouping.
     It returns `{kept, created, already, grouping, families}`.
   - `GET /sequences/{family}?grouping=` returns the family page's payload (below). An unknown family or grouping is a
     404 in words.
   - `POST /sequences/{family}/review?grouping=` builds a Review queue over the unjudged elements. It returns 409 when
     every element is already judged.
   - The held-out recording gets a 423 on preview and keep. A family read leaves held-out sequences out.
3. **The family page's figures, in order:**
   - strips, one per sequence, on one shared time axis, with each element coloured by its motif family;
   - the medoid per element position (least summed distance among up to 60 elements at that position, each resampled
     and centred);
   - histograms of the inter-element gaps (12 bins) and of sequence length (one bin per length);
   - the first three sequences as real decimated traces with element bands;
   - the rail: judged / of and the verdict split, the median gap, Send N unjudged elements to Review, remove / restore
     per sequence, and back to the atlas;
   - beside the title: the nearest other family in the grouping by edit distance over labels.

   **One example**, from the bridge test's synthetic library: family `F-01.F-02.F-01`, named `F-01 → F-02 → F-01`.
   It has one sequence on the first channel at 3.33 h, 180 s long, with elements 0–60 s (F-01), 60–120 s (F-02) and
   122–180 s (F-01). `gaps = [0.0, 2.0]`, `lengths = [3]`, there are three medoid traces (positions 0, 1, 2), one
   example trace with three bands, and `nearest = F-01 → F-02 (1 element different)`. I could not render it in a
   browser here (no database in the worktree); the smoke state below is where it gets drawn.
4. **`library/sequences`** now replaces itself with `library/atlas?unit=sequences` and keeps any other query
   parameters.
5. **Deviations from the prompt.**
   - There is a fourth route (`/review`), because the rail's *send to Review* needs one.
   - The atlas's min-members filter is lifted for label-chain groupings.
   - The family is identified by a `.`-joined key rather than `A-B-A` (see Assumed).

## 5. Tests

- **Red** (`6cc21bf`, tests only): both files failed at collection with
  `ImportError: cannot import name 'sequences' from 'Working.library'`, under conda and venv respectively.
- **Green:**
  - `tests/test_library_sequences.py`, **12 passed** (conda). It pins:
    - touching members join, a 5 s gap under 10 % joins, and a pair 20 % apart does not;
    - the gap and tolerance numbers are live;
    - `min_len` holds, and `min_len < 2` is refused;
    - only labelled members on that channel join;
    - an unknown rule or a negative / NaN number is refused;
    - adamatzky and logisi equal `find_trains`' trains on the same onsets (parametrised);
    - `label_key` is order-sensitive and `edit_distance` is correct;
    - the join is deterministic and NaN-free;
    - keeping twice writes once (row and member counts, with the same id returned);
    - kept rows read back with the joiner's gaps, labels and members;
    - label-chain assignments group by key, with one medoid per family, and `nearest_family`.
  - `tests/test_webui_library_sequences.py`, **7 passed** (`webui/.venv`). It pins:
    - preview writes nothing (row counts of `sequences`, `sequence_members`, `groupings`, `grouping_assignments` and
      `hand_edits` are unchanged) and lists the expected strips and counts;
    - no recording means the busiest channel, and `candidates_only` works;
    - keep writes, then `/sequence-families` (both named and default) lists the family; a second keep writes nothing;
    - the family route's gaps equal the preview's joiner gaps `[0, 2]`, along with the lengths, bins, medoids, examples
      and nearest family, and an unknown family is a 404;
    - remove is a hand edit, and restore brings the sequence back;
    - held-out gets a 423 on preview and keep;
    - a bad rule is a 400 that says why.
  - `tests/test_library_import_sequences.py` (the refactored insert) and `tests/test_import_boundaries.py`: 13 passed
    between them (conda; run together with my core file, 25 passed in total).
  - `tests/test_webui_library.py` (named by the prompt): **all passed** (`webui/.venv`, run together with my bridge file:
    66 passed, 3 xpassed, 0 failed).

## 6. Smoke states (`webui/smoke_pages/zzzzzzzzzzz_sequences.json`)

1. `sequences-the-atlas-offers-build-sequences` (library/atlas?unit=sequences). The Build sequences card shows with its
   channel select enabled (filled from the bridge's candidates), the rule control, the gap field, Preview and Keep.
2. `sequences-a-preview-draws-strips-and-writes-nothing`. It picks **adamatzky** (theta = the mean onset gap, so any
   busy channel makes runs) and runs Preview on the first channel the picker offers, which is the busiest. It expects
   the summary line, at least one strip element, the label-chain counts and the colour key.
3. `sequences-keep-then-the-family-page-draws`. **WRITES, sandbox only.** It does the same preview, then Keep these.
   The atlas shows label-chain family cards; *Open all …* (`open-family`) opens the family page, which should show the
   strips, the medoid cells, both histograms (as svg), the examples and the rail, and no placeholder or load-failed card.
4. `sequences-the-library-sequences-route-opens-the-atlas` (`library/sequences`). It should land on the atlas with the
   card, and the URL hash should carry `unit=sequences`.

**For the manager on real data:**
- Under the default fixed rule (0 s + 10 %), the seeded drop-motif members may not touch, so a fixed-rule preview can
  honestly say "none sits close enough". That is why the smoke uses adamatzky.
- Please also check by eye that the strip colours match the motif atlas's card colours.
- Please check that the first family page's medoid row is not blank (it is blank only if the unit is undeclared).

## 7. Gates I ran

- `node …/typescript/bin/tsc -b` (from the worktree's `webui/client`): clean, run twice (after the client compiled and
  before the report).
- `node …/vite/bin/vite.js build`: built (the usual Gallery dynamic-import warning only).
- pytest:
  - conda: `tests/test_library_sequences.py`, `tests/test_library_import_sequences.py`, `tests/test_import_boundaries.py`;
  - venv: `tests/test_webui_library_sequences.py`, `tests/test_webui_library.py`.
  - Not the full suite, no `-n`. No browser smoke (no DATA in the worktree).

## 8. Open questions and risks

- **Grouping pile-up.** Every keep that adds rows saves a new label-chain grouping. If that clutters the picker, a later
  change could rewrite the newest label-chain grouping in place instead.
- **Labels are a snapshot of the motif grouping.** A kept sequence's family key is fixed at keep time, from the motif
  grouping current then. If the motif grouping is regrouped later, the atlas card's `compositionLabel` (read live by
  `_compositions`) can disagree with the family id until the sequences are re-kept under the new labels. The provenance
  note names the motif grouping that was used.
- **Hand edits on motifs are not applied to member labels** (the same is true of `_compositions`).
- **Hand edits on sequences are counted in `handEditsKept`.** A `seq:`-keyed edit scoped to the sequence grouping is
  counted there and nowhere else, and the motif reads ignore it (it matches no member's content hash).
- **The medoid is drawn from the first 60 elements per position.** The page prints "of N" whenever that sample is
  smaller than the position's count.
- **What is left:**
  - the looser grouping experiment (near-matches folded into one family, e.g. by an edit-distance cut);
  - cross-channel sequences (propagation), which is a separate question;
  - the atlas's sequence rail still says "Seed search needs multi-seed".

## 9. Commits

```
6cc21bf sequences: red tests for the member joiner and the Build sequences routes
ebd3dac sequences: join adjacent Library members into sequences; preview, keep and family routes
738028f sequences: Build sequences card, preview strips, the sequence family page, library/sequences route
(+ this report)
```

Shared-file edits for the merge:
- `webui/client/src/api.ts`: one block appended at the end.
- `webui/server/library.py`: one import line plus a new block before the WRITES banner.
- `FamilyPage.tsx`: three small hunks (import, render line, placeholder removed).
- `AtlasPage.tsx`: import, the hook setter, the card in the sequences branch, and the filter in `SequenceAtlas`.
- No changes to `schema.py`, `smoke.py`, `serialize.py`, `views.py` or the kit.
