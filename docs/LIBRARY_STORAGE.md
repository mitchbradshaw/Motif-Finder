# LIBRARY_STORAGE.md — how the motif library stores what it knows

**Status: complete (stage-3 Prompt 03, 2026-09-22).** The table shapes, the identity rule and the route
list are **fixed** — Prompt 04 (Discovery) reads exemplars and templates from them and builds against them.
Every number in §5.2 and §6.3 was measured on this machine's catalogue, not estimated.

Audience: a researcher who, next year, wants to add a clustering method, import a new bundle of extracted
motifs, or understand why two spans that look identical are one library entry and not two.

Companion documents: `docs/BLOCK_INTEGRATION.md` (adding an analysis block, Prompt 01),
`docs/DATA_REGISTRATION.md` (registering a dataset, model or window set, Prompt 02). This one is the third:
adding things to the **Library**.

---

## 1. What the Library stores, in one paragraph

A **motif** is a shape. The Library is the catalogue of shapes the project has found, plus every place each
shape occurs. An **entry** (`motif_entry`) is one shape. A **member** (`motif_member`) is one occurrence of
that shape — a span in some recording, on some channel. A member carries a **revision list**: the same
occurrence re-described (a human redrew its extent), never a second member. An **edge** (`motif_edge`) is a
measured relationship between two members. A **sequence** is a run of events in order with gaps between
them — a different unit, stored in its own tables. A **grouping** is a question asked of the catalogue
("group single motifs by shape distance, Ward, cut 0.42"), saved with an id, with the answer recorded as an
assignment per member. **Hand edits** sit outside every grouping and are re-applied on top of each one.

Bulk arrays never enter the database (CLAUDE.md rule 4). A motif's waveform is read back either by slicing
its recording's channel `.npy` at the stored absolute indices, or from the event store's `snippets.npz` it
was imported from, whose path is on the row.

---

## 2. Identity and hashing

### 2.1 The rule

Identity has two halves.

| half | what it answers | how it is computed |
|---|---|---|
| **content hash** | *which entry* — is this the same shape? | `Working.library.identity.content_hash(values)` over the waveform alone |
| **occurrence key** | *which member* — is this the same place? | `occurrence_key(hash, recording_id, channel, start_idx, end_idx)` |

- Same hash → **the same `motif_entry`**. Never a second entry.
- Same hash, new occurrence → **a new `motif_member`** of that entry.
- Same hash, same occurrence → **the same member**, and a **new revision** if the description changed.

This is the PRD's "members are keyed on their content — recording, start and end sample" with the shape
hash added in front of it, so that the same shape found in two recordings lands in one entry rather than two.

### 2.2 The algorithm, exactly

```
content_hash(values) =
    x  = float64(values), flattened
         reject if empty; reject if any value is NaN or +/-inf   (loud, ValueError)
    r  = resample_to_length(x, HASH_LENGTH)      # Working.distances, linear interp over [0,1]
    z  = z_normalize(r)                          # Working.distances, std == 0 -> all zeros
    q  = round(z, HASH_DECIMALS) + 0.0           # +0.0 folds -0.0 to 0.0
    h  = blake2b(q.astype('<f8').tobytes(), digest_size=16).hexdigest()   # 32 hex chars
```

with the pinned constants

| constant | value | changing it means |
|---|---|---|
| `HASH_LENGTH` | **256** | re-hashing the whole library |
| `HASH_DECIMALS` | **6** | re-hashing the whole library |
| digest | **blake2b, 16 bytes → 32 hex chars** | re-hashing the whole library |

The resample-then-z-normalise pair is **the same pair `Working.distances.scale_invariant_distance` uses**,
and that is deliberate: the hash and the default distance agree on what "the same shape" means, so a pair at
distance 0 hashes the same.

### 2.3 What is in the hash, and what is not

**In:** the waveform's shape, and nothing else.

**Not in, on purpose:**

| not hashed | consequence | why |
|---|---|---|
| amplitude and baseline | the same shape at 1 mV and 17 mV is **one entry** | z-normalisation; depth is a measured feature, not identity |
| recording, channel, sample range | the same shape in two places is one entry with **two members** | that is what `occurrence_key` is for |
| every metadata column | an event re-imported with one column changed resolves onto **its existing entry** | re-import must be idempotent (PRD story 43) |
| detrending | a raw and a detrended copy of one event may hash differently | the importer picks one waveform per source and states which — see §5 |

### 2.3.1 What the hash does NOT do, and why that is not a bug

**The same curve sampled at two rates does not hash the same.** This was the first thing the identity tests
asserted, and it was wrong. Resampling is lossy: interpolating 100 points up to 256 does not land on the
same values as decimating 1000 points down to 256. Measured on a drop-shaped curve, the two normalised
vectors differ by up to **5.2e-4**, and **255 of the 256 samples** differ by more than the rounding quantum.

No choice of `HASH_DECIMALS` repairs this. A coarser quantum only moves the boundary the two values straddle,
and across 256 samples something always straddles it — at a 1e-2 quantum and 1.2e-4 of error, the chance all
256 agree is about 0.2%. **A hash cannot implement a tolerance.** The alternative, a locality-sensitive
("fuzzy") hash, buys tolerance at the price of false positives, and a library that silently merges two
motifs is worse than one that asks.

So three mechanisms answer three different questions, and the mistake to avoid is collapsing them:

| mechanism | question | used for |
|---|---|---|
| **content hash** | is this the same **waveform**? | making re-import idempotent; resolving an event onto its existing entry |
| **`scale_invariant_distance`** | is this the same **shape**? | shape families, and a motif recurring at another sampling rate |
| **IoU (§2.4)** | is this the same **span**? | duplicate detections of one event in one channel |

On the same drop measured two ways, the distance reads **0.0076** where a different shape reads **21.8** —
three orders of magnitude, so the separation is not marginal. Cross-rate recurrence is found by
`Working/library/matching.py::match_span_to_entry`, which writes a member and a distance-carrying edge. That
is the designed path and it predates this document.

### 2.4 Duplicates and near-duplicates

| case | test | what happens |
|---|---|---|
| **exact duplicate** | same `content_hash` | resolves onto the existing entry; a new member if the occurrence is new, a new revision if it is not. Never a second entry. |
| **near-duplicate** | same recording **and** channel, reciprocal **IoU ≥ 0.5**, and onset agreement within **`ONSET_TOLERANCE_FRACTION` × the candidate's own duration** | **flagged for review, never merged** |
| **different shape** | neither | a new entry |

The near-duplicate rule is spec §4.6, whose text is *"reciprocal overlap IoU ≥ 0.5 with onset agreement
scaled to the candidate's own duration"*. The spec gives **no coefficient** for the onset term;
**`ONSET_TOLERANCE_FRACTION = 0.25` is this document's default** and is stated here because it is a choice,
not a reading. Both numbers live in one place (`Working/library/dedupe.py`) and both are recorded on the
flag row, so a flag raised under one rule is not silently compared against another.

Note there are **two different 0.5s** in this project and they are not the same number: §4.6's IoU ≥ 0.5 is a
span-overlap match threshold (Settings › Analysis defaults); §9.10's "omit motifs whose nearest family is
past d > 0.50" is a shape-distance omit cut (Settings › Library groupings).

### 2.5 Revisions

Spec §4.2: *"A `motif_member` row is the identity of a motif. It carries a current span pointer and a
revision list. Revisions are spans, not edits to a span."*

- A revision points at **either** a `detections` row (machine) **or** an `annotations` row (human edit).
- **Rev 1 is what the matcher compares against; the current revision is what the researcher sees.**
- A human extent edit writes a **new annotation** with a provenance pointer, moves the member's current
  pointer, and **never mutates the detection** — the run still reproduces from its recipe.
- A re-run producing a span that matches **rev 1** resolves onto **this same member** (§4.2 rule 4), and
  writes its own detection row carrying a pointer to the prior adjudication (§4.7). It does not create a
  revision.
- Editing an extent **invalidates that member's `motif_edge` distances**. **Nothing marks them.** There is
  no staleness column on `motif_edge` and `add_revision` does not touch the edge table;
  `revisions.stale_edges(conn, member_id)` returns the invalidated edge ids and **the caller that edited
  the extent is on the hook for recomputing them**. This paragraph previously claimed the edges were
  "marked stale rather than silently kept", which was aspirational — a reader who believed it would have
  trusted a distance the edit had already invalidated.

---

## 3. The tables

Everything here is **additive** and applied through `init_db()`, which stays idempotent (CLAUDE.md rule 3).
Each migration is its own function in `Working/database/schema.py`.

### 3.1 Tables that already existed

| table | one row means |
|---|---|
| `motif_entry` | **one shape.** Identified by its content hash; `UNIQUE (recording_id, start_idx, end_idx)` still holds on the exemplar span it was created from. |
| `motif_member` | **one occurrence** of that shape, in any recording and any channel. |
| `motif_edge` | **one measured relationship** between two members: distance function, threshold, value, recipe hash, and for cross-channel pairs the lag / correlation / bin. |
| `motif_entry_tags` → `tag_vocabulary` | **one label on an entry.** Species, corpus and morphology are tags, not columns — see §3.4. |
| `templates` | a saved chain with recording and span stripped (spec §4.5). The Library's Templates section reads **this** table; there is no second store. |

### 3.2 Columns added to them

`motif_entry` gains, all nullable:

| column | meaning |
|---|---|
| `content_hash` | §2.2. The entry's identity. Indexed. |
| `channel` | which channel the exemplar span came from. |
| `fs` | the sampling rate the exemplar was measured at — **not** part of identity, but needed to render a time axis. |
| `scale` | `event` or `train` (already present, T52). A sequence is **not** a scale — see §4. |
| `source_kind` | `event_store` · `catalogue` · `annotation` · `review_seed` · `hand` |
| `source_store` | the registered store or file the row was imported from, as a repo-relative path |
| `source_ref` | the source's own id for this event (e.g. the event store's `event_id`), so the `snippets.npz` key is recoverable from the row |

`motif_member` gains `content_hash`, `channel`, and `current_revision_id`.

### 3.3 New tables

```sql
-- One revision of a member's span. Rev 1 is what the matcher compares against.
CREATE TABLE motif_member_revision (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id      INTEGER NOT NULL REFERENCES motif_member(id),
    revision       INTEGER NOT NULL,            -- 1, 2, 3 ... per member
    origin         TEXT    NOT NULL CHECK (origin IN ('machine','human')),
    detection_id   INTEGER REFERENCES detections(id),   -- set when origin = 'machine'
    annotation_id  INTEGER REFERENCES annotations(id),  -- set when origin = 'human'
    start_idx      INTEGER NOT NULL,
    end_idx        INTEGER NOT NULL,
    content_hash   TEXT,
    created_at     TEXT    NOT NULL,
    superseded_at  TEXT,                          -- NULL on the current revision
    UNIQUE (member_id, revision)
);

-- A run of events in order, with gaps. A different UNIT from a single motif,
-- stored separately rather than as a long motif_entry, because a sequence's
-- identity is its ordered composition and not one waveform.
CREATE TABLE sequences (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_key     TEXT    NOT NULL,            -- the source's own name, e.g. 'oyster_id10_ch3_1362824s'
    origin           TEXT    NOT NULL CHECK (origin IN ('machine','human')),
    recording_id     INTEGER REFERENCES recordings(id),
    channel          INTEGER,
    start_idx        INTEGER,
    end_idx          INTEGER,
    n_events         INTEGER,                     -- as CLAIMED by the source
    needs_extraction INTEGER NOT NULL DEFAULT 0,  -- 1 = its singular events are not resolved yet
    source_kind      TEXT,                        -- 'sequence_csv' | 'annotation' | 'catalogue'
    source_store     TEXT,
    source_ref       TEXT,
    annotation_id    INTEGER REFERENCES annotations(id),   -- set when origin = 'human'
    content_hash     TEXT,                        -- hash of the gap profile; NULL while needs_extraction
    created_at       TEXT    NOT NULL,
    UNIQUE (sequence_key, origin)
);

-- A singular event belonging to a sequence, in order. Absent for a sequence
-- that still needs extraction -- which is exactly what needs_extraction records.
CREATE TABLE sequence_members (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id  INTEGER NOT NULL REFERENCES sequences(id),
    position     INTEGER NOT NULL,                -- 0-based, in time order
    member_id    INTEGER REFERENCES motif_member(id),   -- the singular event, when extracted
    start_idx    INTEGER NOT NULL,
    end_idx      INTEGER NOT NULL,
    gap_before   REAL,                            -- seconds from the previous event's onset
    UNIQUE (sequence_id, position)
);

-- A saved grouping: one question asked of the catalogue.
CREATE TABLE groupings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    unit         TEXT    NOT NULL CHECK (unit IN ('single_motifs','sequences','spike_trains')),
    basis        TEXT    NOT NULL,                -- 'shape-distance' | 'sequence-similarity' | 'amplitude' | ... | 'tag' | 'provenance'
    method       TEXT    NOT NULL,                -- registered name in Working/library/grouping/methods/
    params_json  TEXT    NOT NULL,                -- canonical JSON: the method's parameters AND the cut
    cut          REAL,
    filters_json TEXT,
    n_families   INTEGER,
    n_assigned   INTEGER,
    n_omitted    INTEGER,
    recipe_hash  TEXT,
    created_at   TEXT    NOT NULL,
    actor        TEXT
);

-- One member's place in one grouping. family_id NULL means OMITTED, and the
-- reason says why -- omitted entries are flagged, never deleted (spec 8.2).
CREATE TABLE grouping_assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    grouping_id  INTEGER NOT NULL REFERENCES groupings(id),
    unit         TEXT    NOT NULL,                -- which table member_ref points into
    member_ref   INTEGER NOT NULL,                -- motif_member.id, or sequences.id when unit = 'sequences'
    content_hash TEXT,                            -- so a hand edit can key to it across regroups
    family_id    INTEGER,                         -- NULL = omitted
    family_label TEXT,
    distance     REAL,                            -- to the family medoid, when the basis is a distance
    is_medoid    INTEGER NOT NULL DEFAULT 0,
    omit_reason  TEXT,                            -- 'past_cut' | 'outside_bins' | 'group_too_small' | 'not_in_a_sequence'
    UNIQUE (grouping_id, unit, member_ref)
);

-- A hand edit, keyed by CONTENT HASH rather than by member id, so it survives
-- a regroup, a re-import and a re-clustering (fog A16).
CREATE TABLE hand_edits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash  TEXT    NOT NULL,
    kind          TEXT    NOT NULL CHECK (kind IN ('add_member','remove_member','make_exemplar','tag','class')),
    family_label  TEXT,
    value         TEXT,
    grouping_id   INTEGER REFERENCES groupings(id),   -- NULL = applies to every grouping
    active        INTEGER NOT NULL DEFAULT 1,         -- 0 = undone/restored
    created_at    TEXT    NOT NULL,
    actor         TEXT
);

-- A saved window set (spec P18 / 6.9 / 8.8). Bulk window bounds stay on disk.
CREATE TABLE window_sets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    version        INTEGER NOT NULL DEFAULT 1,
    path           TEXT    NOT NULL,             -- DATA/derived/window_sets/<name>/windows.npz
    recording_id   INTEGER REFERENCES recordings(id),
    channel        INTEGER,
    fs             REAL,
    window_length  INTEGER,
    stride         INTEGER,
    gap            INTEGER,
    n_windows      INTEGER,
    split_json     TEXT,                          -- the split assignment and the split rule
    spacing_json   TEXT,                          -- the spacing check result
    coverage_json  TEXT,                          -- human-verdict coverage per split/class AT SAVE TIME
    labels_source  TEXT,
    recipe_hash    TEXT,
    created_at     TEXT    NOT NULL,
    UNIQUE (name, version)
);
```

### 3.4 Where species, corpus and morphology go — and where measurements do not

They are **tags** (`tag_vocabulary` + `motif_entry_tags`), not columns. Two reasons:

1. The Library's **label basis** for grouping is defined over tags (spec §8.2), so a tag is directly
   groupable and a column is not.
2. Spec §4.4 rejects measured features on Library rows outright: *"Writing measured features onto Library
   rows was rejected outright: it would make a row's meaning depend on whichever interrogation happened to
   run last."*

So **amplitude, timescale, frequency content and polarity — the four feature-bin bases — are computed on
demand from the waveform, never stored on the row.** `Working/library/grouping/bases.py` computes them; the
Library's grouping editor draws their live distributions. A number you see in a feature histogram was
measured when the page asked for it.

**A tag belongs to the shape, not to the occurrence — a known limitation.** Tags attach to `motif_entry`,
and there is no `motif_member_tags` table. So when a second occurrence of one shape arrives carrying
different labels — another species, another corpus, another word for the morphology — the entry accumulates
**both**. That is deliberate rather than tidy:

- a shape found in an oyster and in a reishi is exactly the cross-recording recurrence the Library exists to
  show (PRD Part 2: eleven of twelve shape families draw members from more than one spike train);
- two source rows disagreeing about a morphology is a **finding**, not noise — Part 2 reports families
  "which mix morphologies that the per-span labels call distinct";
- keeping only the label that happened to be imported first would delete that evidence silently.

The cost is that you cannot ask "which species did *this occurrence* come from" through tags; you ask the
member's `recording_id` instead, which is exact. A future ticket wanting per-occurrence labels should add
`motif_member_tags` rather than reinterpreting the entry's.

**Amended 2026-09-23 (fixup-d; QUESTIONS.md Q-I1, Q-I4, Q14) — a versioned change, not a reversal.**
The researcher asked for exactly the stored measurements the paragraph above refuses: width, amplitude,
depth, recovery and slope per motif, to group, filter and sort the whole Library by. The fear above is
kept; the answer is to move the features OFF the rows, not onto them. **`motif_features`**
(`schema.py::_MOTIF_FEATURES_SCHEMA`, written only by `Working/library/features.py::backfill_library`):

- keyed by **content hash** (plus `fs`, because the hash is fs-blind and every duration is not), so a
  measurement is tied to the waveform it was taken on and cannot outlive it — the failure the
  paragraph above guards against;
- measured on the **same samples the hash was taken over** (the store's `detrended_mv` snippet, §5.1),
  from the **detector's own onset and trough** where a detector produced the event, so the stored depth
  is the detector's depth (410 / 410 seed events, to 1e-14 mV);
- carrying the **detector's own numbers** beside ours (`source = 'detector'`: `drop_depth_mv`,
  `fall_duration_s`, `peak_to_peak_mv`, `rise_height_mv`, slopes in mV/s), which §5.1's import dropped
  and Q-X2.5's floor filter needs;
- **recomputable, never authoritative**: re-running the backfill replaces a row, and nothing reads it as
  ground truth. `motif_entry` / `motif_member` gain no column;
- **per-event only**: a comparison across events (a rose, an interval statistic) is never stored — it
  is a view over these rows, computed where it is drawn.

`grouping/bases.py` still computes its four grouping features on demand; the two are not merged. One
caveat, recorded: the hash is z-normalised and so blind to amplitude, so two motifs of one shape at two
depths would share a feature row. None of the 3,603 live members share a hash today.

### 3.5 Which door each table writes through (rule 5)

`webui/server/writes.py` already routes `motif_*` to `write_human`. The new tables split by origin:

| table | door | why |
|---|---|---|
| `motif_entry`, `motif_member`, `motif_member_revision`, `motif_entry_tags`, `hand_edits` | **human** | the library is a curated catalogue; an entry is a claim a person owns |
| `groupings`, `grouping_assignments` | **human** | a grouping is a question a researcher asked, and its answer |
| `window_sets` | **machine** | a window set is produced by a chain, like the other registered artifacts |
| `sequences`, `sequence_members` | **by `origin`** — `human` rows through `write_human`, `machine` rows through `write_machine` | this is the whole reason sequences are not one table with the motifs |

The last row is the one that matters. A sequence read out of `Plots/drop_motifs11/sequences.csv` is a
**detector's** claim; a sequence read out of `annotations` is a **person's**. Storing both in `motif_entry`
would have made them indistinguishable, which is how rule 5 gets broken quietly. They are one table with an
`origin` column that picks the door, and a reader can always tell which is which.

---

## 4. Sequences, single motifs, and spike trains

Spec §8.2 names three grouping **units**. They are three different things in storage:

| unit | stored as | identity |
|---|---|---|
| **single motifs** | `motif_entry` + `motif_member`, `scale = 'event'` | the content hash of one waveform |
| **sequences** | `sequences` + `sequence_members` | the ordered composition: which events, in what order, with what gaps |
| **spike trains** | `motif_entry` with `scale = 'train'` | the content hash of the whole train's waveform |

**A sequence is not a long motif.** Two sequences of the same six shapes with different gaps are different
sequences; two sequences of different shapes with the same gaps are also different. That is why the identity
is compositional and lives in `sequence_members`, and why the sequence tables are separate from the entry
tables rather than a `scale` value.

**`needs_extraction`.** A sequence whose singular events have not been extracted is stored with
`needs_extraction = 1` and **no `sequence_members` rows**. It is listed on the Library, it is compared only
at sequence scale, and it is offered to Review as an **"extract events"** queue so a person can mark the
individual events later. This is the honest state for a human-catalogued span that says *"60 spikes (7 mV,
10 min/cycle at start, 3 min/cycle at end)"* — the claim is recorded, the events are not invented.

**Spike trains: defined, not populated.** A spike train is a `motif_entry` with `scale = 'train'`: one row
whose waveform is the whole train, so that an **edge can attach to it** — PRD Part 2 is explicit that this
is why the scale is a stored column rather than inferred from duration, because inference gives no row for
an edge to reference. `motif_edge` already carries distance function, threshold and recipe hash, so
train-to-train edges under a different distance coexist with event-to-event edges **without further schema
change**.

Nothing on this machine writes one yet. A future importer must provide, per train: its recording, channel
and absolute sample range; the waveform to hash (so the train gets a `content_hash` like any other entry);
`scale = 'train'`; and the member events it contains, as `motif_member` rows of the train's entry. Computing
train-to-train edges by spectral or symbolic distance is named Out of Scope in Part 2 and is later work.

Note a train and a sequence are **not** the same object here: a train is a shape at a coarser scale (one
entry, one waveform, one hash), a sequence is an ordered composition (its own table, identity in its
members and gaps). A spike train that you also want compared by composition gets both — an entry at train
scale, and a `sequences` row pointing at the same events.

---

## 5. Import kinds and provenance

| importer | source | writes |
|---|---|---|
| `importers/event_store.py` | a registered `drop_motif_store` (`events.csv` + `snippets.npz` + `manifest.json`) | `motif_entry` + `motif_member` + revision 1 + tags |
| `importers/sequences.py` | `Plots/drop_motifs11/sequences.csv` | `sequences` (`origin = 'machine'`) + `sequence_members` |
| `importers/catalogue.py` | `DATA/catalogue/signal_catalog.xlsx` via the registered `catalogue_spreadsheet` | `annotations` (human) + `annotation_tags` |
| `importers/annotations.py` | the `annotations` table already in the database | `sequences` (`origin = 'human'`) and single-event `motif_entry` rows |

### 5.1 The event store, column by column

| source column | target | note |
|---|---|---|
| `snippet_start_idx` / `snippet_end_idx` | `motif_entry.start_idx` / `end_idx` | **end is exclusive** (`len(array) == end - start`, measured across all four stores) |
| `recording_id` | `motif_entry.recording_id` | bound to `recordings.id`; an unknown id is a counted warning, never a crash |
| `channel`, `fs` | `motif_entry.channel`, `.fs` | explicit on the row; `fs` is not part of identity |
| `event_id` | `motif_entry.source_ref` | so the `snippets.npz` key is recoverable from the row |
| the store path | `motif_entry.source_store` | with `source_kind = 'event_store'` |
| `span_key` | `motif_entry.label` | |
| `morphology`, `species`, `corpus`, `framing` | **tags** (§3.4) | reusing vocabulary rows; `Stegasauras` normalises to `stegasaurus` |
| the `__detrended_mv` snippet | the **hashed waveform** | detrended rather than raw: detection ran on the detrended trace, and hashing `__raw_mv` would let the same drop on a drifting baseline and on a flat one become two entries. `Working/library/importers/event_store.py::WAVEFORM_FIELD` is the single place this is stated in code |
| `drop_depth_mv`, `fall_duration_s`, slopes, `purity` … | **nothing** on the Library rows | measured features are computed on demand (§3.4, spec §4.4); since fixup-d the detector's own numbers are carried in `motif_features` (§3.4 amendment) |
| `cluster_id` | **nothing** | it is `-1` on all 11,106 rows of all four stores |

### 5.2 What was imported on this machine, and what was not

Run through `scripts/populate_library.py`, which is the reproducible record of it.

| source | result |
|---|---|
| `DATA/library_seed/drop_motifs5/motifs` | **410** created, 17 near-duplicates flagged |
| `Plots/drop_motifs10/motifs` | **3,189** created, **61 exact duplicates** of seed events resolved onto their entries, 256 excluded (`reishi_1hz`), 5 span conflicts counted, 420 flagged |
| `Plots/drop_motifs11/sequences.csv` | **118 of 118** resolved, **1,646** member events in order |
| `DATA/catalogue/signal_catalog.xlsx` | 32 already imported, **5 unimportable**, each with a stated reason |
| the `annotations` table | **30** human sequences, **4** type-specimen entries, 11,234 triage rows correctly not imported, 1 refused as held out |

Totals: **3,603** entries / members / revisions, **13,349** tags, **148** sequences (118 machine, 30 human),
**1,646** sequence members. The 11,269 annotations are untouched.

Three deliberate exclusions, each a decision rather than an oversight:

- **`Plots/drop_motifs12a` is not imported.** Both its stores are marked `partial` (region A of the Lion's
  mane recording was never detected), 844 of 1,077 rows carry `recording_id = -1`, and its two floor
  policies are two views of one detection that would collide on `UNIQUE (recording_id, start_idx, end_idx)`.
  The importer can still read it; `--include-12a` runs it.
- **The `reishi_1hz` control corpus is excluded** from drop_motifs10. It is the same organism as
  `reishi_10hz` at a second sampling rate and shares `(catalogue_id, channel)` with it, so it double-counts:
  sequence recovery reproduces **118/118** with it excluded and **52/118** with it in. The exclusion is a
  parameter (`exclude_corpora`), not a literal.
- **The 11,234 `imported_10min` annotations are not library content.** They are a ten-minute sort grid —
  every one exactly 600 samples, `scale_viewed = '10min'` — and the longest run of adjacent interesting
  windows is 3, so the grid does not encode sequences. The split is by `source`, not by span length,
  because a future grid at another window size would break a length rule.

### 5.3 Idempotence

Every importer is safe to run twice (PRD story 43). A second run of the event store imports nothing: same
hash and same occurrence resolves to the same member, and the member already has revision 1. The catalogue
recognises its 32 existing rows. `--dry-run` computes the whole report and writes nothing — verified by
comparing row counts before and after, not by trusting the flag.

---

## 6. The grouping engine

A grouping is **`unit × basis × method(params) → one assignment per member`**.

`Working/library/grouping/engine.py::run_grouping(items, *, unit, basis, method, params)` takes **plain
dicts** and never touches a database. That is deliberate: the bridge loads rows and hands them over, which
is what lets the engine be tested without a database and re-used by a script (`scripts/populate_library.py`
does exactly this). An item carries `member_ref`, `content_hash`, and whatever the basis needs — `values`
for a distance basis, `gap_profile` for sequence similarity, `tags` or `recording_id` for a label basis.

`GroupingResult` carries one `Assignment` per input item **in input order, including the omitted ones** —
spec §8.2's rule that what does not fit is flagged and never dropped. Omission reasons are `past_cut`,
`outside_bins`, `group_too_small`, `no_label` and `not_in_a_sequence`.

### 6.1 The three basis kinds, and the three methods

| basis kind | bases | method | where groups come from |
|---|---|---|---|
| distance | `shape-distance`, `sequence-similarity` | `ward` | a cut on a linkage tree |
| feature bins, no distance | `amplitude`, `timescale`, `frequency-content`, `polarity` | `feature_bins` | bins on one feature — quantiles, log-spaced or fixed edges |
| labels | `tag`, `provenance` | `labels` | one group per label |

`bases.py` computes the four features **on demand** and `applicable_bases(unit)` returns, for each basis
that does not apply to a unit, **the reason** — spec §8.2 requires it be shown disabled with one, not
hidden.

### 6.2 Checklist: adding a clustering method

1. **Write the class** in `Working/library/grouping/methods/<name>.py`:
   ```python
   class MyMethod:
       name = "my_method"
       applies_to = ("shape-distance",)          # which bases it can serve
       params = {"cut": {"type": "float", "default": 0.6, "label": "Cut", "help": "..."}}
       def fit(self, data, *, params): ...       # -> an opaque fit object
       def assign(self, fit, *, cut): ...        # -> a family id per row, None = omitted
       def merge_heights(self, fit): ...         # -> floats for the editor's histogram, [] if not a tree
   ```
2. **Register it by name** in `methods/__init__.py` with `register(MyMethod())`, the way
   `Adapters/registry.py` registers a block. Duplicate registration is an error, not a silent overwrite.
3. **Declare `applies_to` honestly.** A method offered for a basis it cannot serve is worse than one that is
   absent, because the editor will offer it and the run will fail.
4. **Return `None` for a row you will not place.** The engine turns that into an omission with a reason; do
   not drop rows, and do not invent a catch-all family.
5. **Expose `merge_heights`** if the method has a tree — that is what the editor draws the cut on. Return
   `[]` if it does not, rather than a fabricated distribution.
6. **Add a test** in `tests/test_library_grouping_methods.py`: a synthetic set with a known number of
   obvious groups, the cut changing the count, and the omission reason you emit.
7. **Do not read the database.** If your method needs something the items do not carry, add it to what the
   caller loads, not to the method.
8. **Check the recipe hash changes** when your parameters change — it is what tells two saved groupings
   apart, and spec §8.2's whole point is that two threshold choices that look alike must not be confused.

### 6.3 Choosing a cut is a measurement, not a constant

The default cut on this machine is **0.60**, and it was measured. The frontend fixture carried 0.42; on the
real 3,603-entry catalogue that omits 29% of it, every one for `group_too_small`:

| cut | families | assigned | omitted |
|---|---|---|---|
| 0.30 | 116 | 1,660 | 54% |
| 0.42 | 151 | 2,545 | 29% |
| **0.60** | **149** | **3,239** | **10%** |
| 0.80 | 115 | 3,480 | 3% |
| 1.00 | 92 | 3,570 | 1% |

The family count is flat from 0.42 to 0.60 while the omitted fraction falls by two thirds — so the extra
omission at 0.42 buys no structure, it is the same families with a quarter of the catalogue shaken out
below the ten-member floor. Re-measure when the catalogue changes; the sweep is four lines of script.

---

## 7. What the UI reads

`webui/server/library.py`, 20 routes under `/api/library`. Every read takes an optional `?grouping=` and
defaults to the **newest grouping of the right unit**.

| method | path | returns |
|---|---|---|
| GET | `/counts` | `{motifs, spikeTrains, sequences, templates, windowSets}` |
| GET | `/groupings` | `Grouping[]` — ids are strings, `g-NN` |
| GET | `/recurrence` | `{recordings, families, coverage, sharedGround}` |
| GET | `/families`, `/sequence-families` | `MotifFamily[]`, `SequenceFamily[]`, with **real decimated mV traces** |
| GET | `/family/{id}` | `{kind:'motif',detail}` / `{kind:'sequence',family}` / `{kind:'missing',id}` |
| GET | `/omitted` | `{groupingId, singles, sequences}`, each carrying `omitReason` |
| GET | `/grouping-editor` | units with live counts, the nine bases with a `reason` where disabled, real distributions |
| GET | `/windowsets`, `/templates` | `WindowSetRow[]`, `Template[]` |
| GET | `/sequences?needs_extraction=1` | Review's "extract events" queue |
| POST | `/groupings/run`, `/groupings` | a **job**, then the saved grouping |
| POST | `/import/dry-run`, `/import` | `ImportBundle`, then a **job** |
| GET | `/import/bundles` | from the **registry**, not a disk scan |
| POST/DELETE | `/hand-edits`, `/hand-edits/{id}` | through `hand_edits.py`, via `write_human` |
| GET | `/export/family/{id}`, `/export/atlas` | `?format=json\|csv`, a real download |

**Three things the bridge cannot give the pages**, because no table holds them — it returns empty rather
than inventing: `Template.versions` / `scores` / `latest` (no version-history or scoring table exists
anywhere), `WindowSetRow.usedBy` (nothing records window-set consumption), and `SequenceFamily.hand` (hand
edits key on a content hash and a sequence has none). `snrDb` is **computed from the exemplar trace**, so
it is an estimate rather than a measurement, and is labelled as one.

**A gap worth naming:** spec §4.5's "a saved detection algorithm *is* the `templates` row, no second store"
is right, but the Library's Templates rail also wants version history, per-run scores and null-model
provenance, and **none of those has a table**. Either §4 should say they are aspirational, or a
`template_versions` / `template_scores` pair is missing from it.

---

## 8. Worked example

Importing a store, grouping it, hand-editing an exemplar, regrouping, and watching the edit survive.

```bash
# 1. Import. Refuses to run without a backup newer than the database.
python scripts/populate_library.py --dry-run     # reports everything, writes nothing
python scripts/populate_library.py --backup      # 3,603 entries, 148 sequences
```

```python
# 2. Group. The engine takes dicts; the caller loads them.
from Working.library.grouping import engine
result = engine.run_grouping(items, unit="single_motifs", basis="shape-distance",
                             method="ward", params={"cut": 0.60, "min_group": 10})
result.n_families, result.n_omitted          # 149, 364
result.omitted_by_reason                     # {'group_too_small': 364}
```

```python
# 3. Hand-edit an exemplar. Keyed by CONTENT HASH, not by member id.
from Working.library import hand_edits
hand_edits.record(conn, content_hash=h, kind="make_exemplar", family_label="F-07")
hand_edits.record(conn, content_hash=other, kind="remove_member", family_label="F-07")
```

```python
# 4. Regroup at a different cut — a different tree, different family ids.
regrouped = engine.run_grouping(items, unit="single_motifs", basis="shape-distance",
                                method="ward", params={"cut": 0.80, "min_group": 10})

# 5. The edits re-apply on top of it, because they were never keyed to the old grouping.
applied = hand_edits.apply_to_assignment(regrouped.assignments,
                                         hand_edits.active_edits(conn))
applied["counts"]     # {'applied': 2, 'orphaned': 0, 'removed_by_hand': 1}
applied["orphans"]    # edits whose family the new grouping lacks, kept as "<label> additions"
```

The removed member **stays out on every regroup until restored** (spec §8.3), and an edit naming a family
the new grouping no longer has comes back as an orphan to be kept as a hand group rather than being
silently dropped. That is the whole reason the key is a content hash: a member id survives a regroup, but a
*family* id does not, and an edit keyed to a family would be lost the moment the cut moved.

### 8.1 A hand edit names its family by the family's medoid, not by its label

Labels are sequential and **every grouping numbers its families from one**, so `F-06` names a different
set of shapes in every grouping. On this machine g-01 and g-02 share **60 labels and 59 of those pairs
have no shape in common at all**. Matching an edit to a family by label therefore does not merely fail on
a renamed family — in the common case it *succeeds against the wrong one*, silently, which is the failure
mode hand edits exist to avoid.

So an edit resolves its family by that family's **medoid content hash**
(`grouping_assignments.content_hash` where `is_medoid = 1`), and falls back to the label only when the
edit and the assignments belong to the same grouping. Two consequences worth stating:

- an edit whose family key is no shape's medoid in the new grouping comes back as an **orphan**, visible,
  to be kept as a hand group;
- a family the re-clustering **renamed** is still matched, because the medoid is the same shape — which
  label matching never managed.

---

## 9. Decisions this document took, that the spec and the PRD did not

| # | question | default taken |
|---|---|---|
| L1 | what bytes the content hash covers (spec OPEN 1) | the waveform alone, resampled and z-normalised — §2.2 |
| L2 | resample length (spec OPEN 2) | **256** |
| L2b | whether the hash recognises one shape across sampling rates | **no — it cannot**, and the distance does it instead. §2.3.1 |
| L3 | onset-agreement coefficient in §4.6 (spec OPEN 4) | **0.25 × the candidate's duration** |
| L4 | where a sequence lives (spec OPEN 9) | its own tables, with an `origin` column — §3.3, §4 |
| L5 | the grouping / hand-edit / omission schema (spec OPEN 6) | `groupings` + `grouping_assignments` + `hand_edits` — §3.3 |
| L6 | the window-set schema (spec OPEN 7) | `window_sets` — §3.3 |
| L7 | the revision schema (spec OPEN 8) | `motif_member_revision` + `motif_member.current_revision_id` — §3.3 |
| L8 | where species / corpus / morphology live | tags, not columns — §3.4 |
| L8b (fixup-d) | where per-event measurements live | `motif_features`, keyed by content hash, beside the rows — §3.4 amendment |
| L9 | where amplitude / timescale / frequency / polarity live | computed on demand, never stored — §3.4 |
