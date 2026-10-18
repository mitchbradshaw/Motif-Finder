# sequences — build sequences from adjacent Library members, and draw the sequence family page

**Read first:** `CLAUDE.md`; `docs/prompts/fixup/UX-1015-common.md` (isolated worktree, no `DATA/`, interpreters,
client toolchain through the junction, no smoke in a worktree, no new dependencies); then this file. You run alone:
open choices go under **Assumed**. Commit prefix `sequences:`; every commit ends with
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Test-first.

## Why (the researcher, 2026-10-18)

> Can the library combine adjacent motifs to recognise sequences (possible RQ1 precursor)? Library sequences pages
> are not implemented. … A sequence is an ordered run of motifs on one channel with gaps below a limit, like a
> spike train. … For now, with only ~20 sequences or so, each family is probably just a unique sequence.

## What the code has today (facts, 2026-10-18)

- `library/index.tsx:20-28` has no `sequences` case ("No Library page called…"); `library/atlas?unit=sequences`
  (`AtlasPage.tsx:290-360`) is a working family grid; the sequence FAMILY page is `SequenceFamilyPlaceholder`
  (`FamilyPage.tsx:146, 159-167`). `api.ts:917 getLibrarySequences` → `server/library.py:2428` exists and nothing
  calls it. Sequence rows arrive only through importers (`Working/library/importers/sequences.py:170`,
  `catalogue.py:474`, `annotations.py:217`); nothing joins detections or members into sequences.
- Joiners that exist: `Working/interrogation/trains.py:395 find_trains` (gap rules `maxinterval`, `adamatzky`,
  `logisi`, emits `train_id`), `cycle_shapes.py:853 sequences_of`, `drop_motifs/detect.py:455 merge_up_runs`.
- `Working/library/revisions.py` holds member span revisions; `library.py:2538` is the regroup job; family pages read
  `library.py:966/1038`.

## Decided with the researcher (grilling, 2026-10-18)

- **A sequence is one channel's ordered run of Library MEMBERS** (motifs that carry a family label), so a sequence
  reads as a chain of labels, A-B-A. Cross-channel propagation is a different question and not this prompt. Only
  members join; detections without a family do not.
- **Join rule:** a fixed maximum gap between the end of one member and the start of the next, **default 0 s with a
  tolerance of 10 % of the shorter member's length** (members rarely touch to the sample), both shown as numbers you
  can change; the two adaptive rules (`adamatzky`, `logisi`) offered as alternatives in the same control. Minimum
  two elements, no maximum.
- **Same sequence = same family labels in the same order**, whatever the gaps and durations. With ~20 sequences
  today each family is one unique sequence; a near-match (one element different or missing) is its own family,
  with the nearest other sequence family named on the page. Grouping sequences more loosely is a later experiment.
- **Where:** the Library atlas under `unit=sequences` gains **"Build sequences"** over one recording's members
  (recording picker, gap rule and numbers, Preview). The preview lists the sequences it would make, as strips, with
  counts; **nothing is stored until "Keep these"**. Kept sequences become `sequences` rows (the importers' table) with
  their member refs in order, and the atlas groups them into families by label-sequence.
- **The sequence family page** shows, in order: every member drawn as a **strip of its elements in order with the
  gaps to scale** (one strip per sequence, colour per element family, the same colours the motif atlas uses); the
  **medoid shape per element position**; the distributions of **inter-element gap** and of **sequence length**;
  example traces (the first three sequences as traces with element bands); and the usual family rail (verdicts,
  remove member, send to Review).
- Also: `library/sequences` must route somewhere — make it the atlas at `unit=sequences`.

## The work

1. **Core joiner** `Working/library/sequences.py` (new): `join_members(conn, recording_id, rule, gap_s, tol_frac,
   min_len=2) -> list[Sequence]` over that recording's members ordered by start; a `Sequence` is the ordered member
   refs, the element labels, the gaps; deterministic; NaN-free; pure Python/numpy. Reuse `trains.find_trains` for
   the two adaptive rules by handing it the members' onset times. `label_key(seq) -> str` is the family identity.
2. **Store on keep:** `keep_sequences(conn, seqs, provenance)` writes `sequences` rows the importers' way (read
   `importers/sequences.py:170` for the row shape and reuse its insert), each with the member refs in order and a
   provenance note (rule, numbers, date). Re-keeping the same sequence is a no-op (identity = recording + ordered
   member refs). Families: the atlas's grouping for `unit=sequences` groups by `label_key`; name each family by its
   label chain (A-B-A).
3. **Bridge:** `POST /api/library/sequences/preview {recording_id, rule, gap_s, tol_frac}` → the strips payload (no
   write); `POST /api/library/sequences/keep` → writes, returns the new rows; `GET /api/library/sequences/{id}` for
   the family page's data (members with their elements' spans and labels, the medoids per position, the gap and
   length distributions, the nearest other sequence family by edit distance over labels). Held-out recordings
   refused as elsewhere.
4. **Client:** the Build sequences card on the atlas (`AtlasPage.tsx` sequences branch); the preview strips
   (`library/SequenceStrips.tsx`, new; d3 as the atlas uses it); the family page (`FamilyPage.tsx` replaces the
   placeholder); the `library/sequences` route. Buttons blue / muted blue; never grey.

## Files

Yours: `Working/library/sequences.py` (new), `Working/library/importers/sequences.py` (only to expose its insert),
`webui/server/library.py` (the three routes), `webui/client/src/library/AtlasPage.tsx`, `FamilyPage.tsx`,
`index.tsx` (the route), new files under `webui/client/src/library/`, `webui/client/src/api.ts`, `tests/`. Do not
touch the trains adapter or `interrogation/`.

## Method and gate

- Core tests (conda): synthetic members on one channel; gap 0 with 10 % tolerance joins touching pairs and not a
  pair 20 % apart; `min_len` holds; the two adaptive rules agree with `find_trains` on the same onsets; `label_key`
  is order-sensitive; keeping twice writes once.
- Bridge tests (venv): preview writes nothing (row count unchanged); keep writes and the atlas lists the family;
  the family route's gap distribution matches the joiner's gaps; held-out refused.
- `tsc -b`, `vite build`. Smoke states in `webui/smoke_pages/zzzzzzzzzzz_sequences.json`: the atlas at
  `unit=sequences` shows Build sequences; a preview draws at least one strip on the seeded library; the family page
  draws strips and the two histograms; `library/sequences` opens the atlas.
- Run your files plus `tests/test_webui_library.py`, `tests/test_import_boundaries.py`.

## Stop and report if

the `sequences` table cannot hold ordered member refs without a schema change beyond an additive column; or the
atlas's family grouping for sequences is computed somewhere you cannot reach.

## Report

`docs/prompts/changes/reports/sequences-report.md`: **Assumed**; the joiner's rule in one paragraph; the routes; the
family page's figures with one rendered example; tests and interpreters; smoke states; what is left (the looser
grouping experiment, cross-channel sequences).
