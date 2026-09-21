# LIBRARY_STORAGE.md — how the motif library stores what it knows

**Status: skeleton (stage-3 Prompt 03, 2026-09-21).** The table shapes, the identity rule and the route
list below are **fixed** — Prompt 04 (Discovery) reads exemplars and templates from them and may build
against them now. The sections marked *(to be completed)* are prose and worked examples, not contract.

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
- Editing an extent **invalidates that member's `motif_edge` distances**. The edges are marked stale rather
  than silently kept.

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

**Spike trains: defined, not populated.** *(to be completed)*

---

## 5. Import kinds and provenance

*(to be completed — the column-by-column mapping for each importer, and which stores were imported on this
machine and why.)*

| importer | source | writes |
|---|---|---|
| `importers/event_store.py` | a registered `drop_motif_store` (`events.csv` + `snippets.npz` + `manifest.json`) | `motif_entry` + `motif_member` (+ rev 1) |
| `importers/catalogue.py` | `DATA/catalogue/signal_catalog.xlsx` via the registered `catalogue_spreadsheet` | `annotations` (human) and `sequences` with `origin = 'human'` |
| `importers/annotations.py` | the `annotations` table | `sequences` (human) and single-event entries |
| `importers/sequences.py` | `Plots/drop_motifs11/sequences.csv` | `sequences` with `origin = 'machine'` + `sequence_members` |

---

## 6. The grouping engine

*(to be completed — the interface, the bases, and the worked checklist for adding a clustering method.)*

A grouping is `unit × basis × method(params) → an assignment per member`. A method is a class in
`Working/library/grouping/methods/`, registered by name.

---

## 7. What the UI reads

*(to be completed — the route table and payload shapes.)*

---

## 8. Worked example

*(to be completed — importing an event store, running a grouping, hand-editing an exemplar, regrouping, and
seeing the edit survive.)*

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
| L9 | where amplitude / timescale / frequency / polarity live | computed on demand, never stored — §3.4 |
