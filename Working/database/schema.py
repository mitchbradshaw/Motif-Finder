"""
schema.py
=========
SQLite schema for the annotation/labelling database and the run-tracking
tables the pipeline (algorithm runs, detections, cached encodings) writes to.

`configs`, `runs`, `detections`, `encodings` and `motifs` are the original
run-tracking tables. `adjudications` (+ `adjudication_tags`) is where a human
verdict against a machine detection lives — the one place algorithmic output
is judged, kept physically separate from `annotations`. `motif_entry`,
`motif_member`, `motif_edge` and `motif_entry_tags` are the shape-first motif
library: an entry is an exemplar span, a member is any span matched to it in
any recording/channel, an edge is a distance-carrying relationship between
two members. `motif_member_revision` is that member's span re-described — a
human redrew its extent — so a revision is a span and never an edit to one.
`sequences` + `sequence_members` hold a run of events in order with gaps: a
different unit from a motif, kept in its own tables because a sequence's
identity is its ordered composition and because its `origin` column is what
decides whether the row is a detector's claim or a person's. `groupings` +
`grouping_assignments` are one saved question asked of the catalogue and its
per-member answer, with `family_id IS NULL` meaning omitted rather than
deleted; `hand_edits` are the researcher's overrides, keyed by content hash so
they survive a regroup. `window_sets` is a saved training-window set, its bulk
bounds on disk. `run_groups` holds N sibling runs fanned out from one recipe
(`runs.run_group_id`); `runs.surrogate_of_run_id` pairs a run with its
surrogate control. `step_artifacts` is the per-step recipe-prefix cache.
`templates` is a saved chain with recording and span stripped.

No ORM — plain `sqlite3`, callable from scripts and the UI alike.

Migrations
----------
`init_db()` is always additive and safe to call repeatedly: base tables use
`CREATE TABLE IF NOT EXISTS`, and anything added to an *existing* table
(new columns on `annotations`; `run_group_id`/`surrogate_of_run_id`/`name`
on `runs`) is applied by `_migrate_columns`, which checks `PRAGMA table_info`
first and only adds what's missing.

The one exception is `_migrate_annotations_verdict`, which SQLite forces to be
destructive: a CHECK constraint cannot be altered in place, so widening the
verdict vocabulary rebuilds the table. It backs the file up first, runs in one
transaction, verifies its row and tag-link counts before committing, and is a
no-op once the live constraint is current.
"""

import datetime
import os
import sqlite3

DB_PATH = os.path.join("DATA", "db", "annotations.sqlite")

# The controlled terms a human verdict may take, defined once. `queries.VERDICTS`
# re-exports this same object and the adjudication path reads it too: two
# literals that happen to agree today are how the annotation and adjudication
# vocabularies drift apart tomorrow. `seed` marks a span recognised by eye as
# exemplar-worthy, and is what the shape library promotes from.
VERDICTS = ("seed", "interesting", "not_interesting", "artifact", "unsure")

_VERDICT_SQL_LIST = ", ".join("'{}'".format(v) for v in VERDICTS)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recordings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file   TEXT    NOT NULL,
    channel       INTEGER NOT NULL,
    fs            REAL    NOT NULL,
    n_samples     INTEGER NOT NULL,
    global_offset INTEGER NOT NULL,
    npy_path      TEXT    NOT NULL,
    notes         TEXT,
    UNIQUE (source_file, channel)
);

CREATE TABLE IF NOT EXISTS reviewed_spans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    start_idx     INTEGER NOT NULL,
    end_idx       INTEGER NOT NULL,
    scale_viewed  TEXT,
    source        TEXT    NOT NULL,
    reviewed_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviewed_spans_recording ON reviewed_spans(recording_id);

CREATE TABLE IF NOT EXISTS annotations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    start_idx     INTEGER NOT NULL,
    end_idx       INTEGER NOT NULL,
    verdict       TEXT    NOT NULL CHECK (verdict IN (__VERDICTS__)),
    tag           TEXT,
    note          TEXT,
    scale_viewed  TEXT,
    source        TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_annotations_recording ON annotations(recording_id);
CREATE INDEX IF NOT EXISTS idx_annotations_verdict   ON annotations(verdict);

CREATE TABLE IF NOT EXISTS configs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    config_hash   TEXT    NOT NULL UNIQUE,
    config_json   TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id     INTEGER NOT NULL REFERENCES configs(id),
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    span_start    INTEGER NOT NULL,
    span_end      INTEGER NOT NULL,
    started_at    TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    artifact_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_recording ON runs(recording_id);

-- One row per saved artifact (plot, cached encoding, model, csv, ...)
-- produced by a run. `path` is relative to the repo root so it stays
-- portable across machines running the same recipe.
CREATE TABLE IF NOT EXISTS artifacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES runs(id),
    kind          TEXT    NOT NULL CHECK (kind IN
                      ('plot', 'encoding', 'model', 'csv', 'other')),
    path          TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);

CREATE TABLE IF NOT EXISTS detections (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES runs(id),
    start_idx     INTEGER NOT NULL,
    end_idx       INTEGER NOT NULL,
    score         REAL,
    meta_json     TEXT
);
CREATE INDEX IF NOT EXISTS idx_detections_run ON detections(run_id);

CREATE TABLE IF NOT EXISTS encodings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    span_start    INTEGER NOT NULL,
    span_end      INTEGER NOT NULL,
    encoding_type TEXT    NOT NULL,
    config_hash   TEXT    NOT NULL,
    path          TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_encodings_recording ON encodings(recording_id);

CREATE TABLE IF NOT EXISTS motifs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id  INTEGER NOT NULL REFERENCES detections(id),
    label         TEXT,
    tags          TEXT,
    rating        INTEGER,
    notes         TEXT,
    created_at    TEXT    NOT NULL
);

-- Many-to-many: a motif's element tags, via the same controlled vocabulary
-- as annotations (`tag_vocabulary`). Separate from `annotation_tags` because
-- a motif and an annotation are different entities with different ids, not
-- because the tagging concept differs. The legacy `motifs.tags` TEXT column
-- (free text, pre-dating the vocabulary) is left alone.
CREATE TABLE IF NOT EXISTS motif_tags (
    motif_id INTEGER NOT NULL REFERENCES motifs(id),
    tag_id   INTEGER NOT NULL REFERENCES tag_vocabulary(id),
    PRIMARY KEY (motif_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_motif_tags_tag ON motif_tags(tag_id);

-- Controlled vocabulary: element / quality / structure / provenance / status
-- terms, editable through the admin panel rather than hardcoded. Deactivating
-- a term (active=0) is a soft-delete — existing annotation_tags rows
-- referencing it are never removed.
CREATE TABLE IF NOT EXISTS tag_vocabulary (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category      TEXT    NOT NULL,
    value         TEXT    NOT NULL,
    description   TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    UNIQUE (category, value)
);
CREATE INDEX IF NOT EXISTS idx_tag_vocabulary_category ON tag_vocabulary(category);

-- Many-to-many: an annotation can carry several element tags (multi-select),
-- exactly one quality/structure/provenance tag in practice (the UI enforces
-- single-select for those categories; the schema doesn't need to, since
-- "at most one per category" is a UI/import-time rule, not a storage one).
CREATE TABLE IF NOT EXISTS annotation_tags (
    annotation_id INTEGER NOT NULL REFERENCES annotations(id),
    tag_id        INTEGER NOT NULL REFERENCES tag_vocabulary(id),
    PRIMARY KEY (annotation_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_annotation_tags_tag ON annotation_tags(tag_id);

-- Human verdict against a machine detection — the only place adjudication
-- of algorithmic output lives (standards rule 2.5: annotations stays
-- human-only, detections/adjudications stay machine-only). One row per
-- detection. `verdict` carries no CHECK: the vocabulary is due to gain
-- `seed`, SQLite can't alter a CHECK in place, and a four-verdict CHECK
-- written here would make that a second non-additive rebuild that rule 2.2
-- doesn't permit. The vocabulary is enforced in Python instead, against
-- the shared constant `queries.VERDICTS`.
CREATE TABLE IF NOT EXISTS adjudications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id  INTEGER NOT NULL REFERENCES detections(id),
    verdict       TEXT    NOT NULL,
    note          TEXT,
    created_at    TEXT    NOT NULL,
    UNIQUE (detection_id)
);

-- Many-to-many: an adjudication's tags, via the same controlled vocabulary
-- as annotations and motifs.
CREATE TABLE IF NOT EXISTS adjudication_tags (
    adjudication_id INTEGER NOT NULL REFERENCES adjudications(id),
    tag_id          INTEGER NOT NULL REFERENCES tag_vocabulary(id),
    PRIMARY KEY (adjudication_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_adjudication_tags_tag ON adjudication_tags(tag_id);

-- Shape-first motif library. An entry is an exemplar span identified by
-- recording and sample range, with one nullable provenance pointer back to
-- the detection it came from. One pointer only — a second nullable FK
-- alongside it would rebuild the origin-discriminator shape `v_spans` was
-- withdrawn for, one column lower.
CREATE TABLE IF NOT EXISTS motif_entry (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    start_idx     INTEGER NOT NULL,
    end_idx       INTEGER NOT NULL,
    detection_id  INTEGER REFERENCES detections(id),
    -- Legacy presentation/notes columns carried across from `motifs` so the
    -- migration loses nothing the old table stored. The shape-first identity
    -- stays (recording_id, start_idx, end_idx); none of these are keys.
    label         TEXT,
    rating        INTEGER,
    notes         TEXT,
    tags          TEXT,
    sax_string    TEXT,
    created_at    TEXT,
    UNIQUE (recording_id, start_idx, end_idx)
);
CREATE INDEX IF NOT EXISTS idx_motif_entry_recording ON motif_entry(recording_id);

-- A span matched to a motif_entry. May sit in any recording and any
-- channel — membership is not restricted to the entry's own recording.
CREATE TABLE IF NOT EXISTS motif_member (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      INTEGER NOT NULL REFERENCES motif_entry(id),
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    start_idx     INTEGER NOT NULL,
    end_idx       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_motif_member_entry ON motif_member(entry_id);
CREATE INDEX IF NOT EXISTS idx_motif_member_recording ON motif_member(recording_id);

-- A relationship between two members of a motif family — cross-channel
-- classification compares each pair of members on different channels of
-- one recording (PIPELINE_PRD.md, Analysis semantics). Carries the
-- distance that produced the match, plus, when the pair is cross-channel,
-- the lag/correlation/bin classification.
CREATE TABLE IF NOT EXISTS motif_edge (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    member_a_id          INTEGER NOT NULL REFERENCES motif_member(id),
    member_b_id          INTEGER NOT NULL REFERENCES motif_member(id),
    distance_function    TEXT    NOT NULL,
    threshold            REAL    NOT NULL,
    distance_value       REAL    NOT NULL,
    recipe_hash          TEXT    NOT NULL,
    lag                  INTEGER,
    waveform_correlation REAL,
    classification_bin   TEXT
);
CREATE INDEX IF NOT EXISTS idx_motif_edge_member_a ON motif_edge(member_a_id);
CREATE INDEX IF NOT EXISTS idx_motif_edge_member_b ON motif_edge(member_b_id);

-- Many-to-many: an entry's tags. Surrogate `id` with a UNIQUE pair, rather
-- than the composite primary key `motif_tags`/`annotation_tags` use,
-- because no tag may be part of any primary key here.
CREATE TABLE IF NOT EXISTS motif_entry_tags (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL REFERENCES motif_entry(id),
    tag_id   INTEGER NOT NULL REFERENCES tag_vocabulary(id),
    UNIQUE (entry_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_motif_entry_tags_tag ON motif_entry_tags(tag_id);

-- N sibling runs sharing one recipe, fanned out over a channel or band
-- list. Carries only an id and a created_at — fan-out and scope semantics
-- belong to the ticket that writes to this table.
CREATE TABLE IF NOT EXISTS run_groups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL
);

-- Per-step cache, keyed on the hash of the recipe prefix up to and
-- including that step.
CREATE TABLE IF NOT EXISTS step_artifacts (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_prefix_hash TEXT    NOT NULL,
    step_index         INTEGER NOT NULL,
    path               TEXT    NOT NULL,
    UNIQUE (recipe_prefix_hash, step_index)
);

-- Saved chains, with recording and span stripped.
CREATE TABLE IF NOT EXISTS templates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    steps_json TEXT NOT NULL
);
"""

_SCHEMA = _SCHEMA.replace("__VERDICTS__", _VERDICT_SQL_LIST)

# Columns added to the original `annotations` table by the tag-vocabulary
# feature. Applied via ALTER TABLE ADD COLUMN, guarded by a PRAGMA
# table_info check so re-running is a no-op — CREATE TABLE IF NOT EXISTS
# doesn't help for columns added to a table that already exists.
_ANNOTATIONS_NEW_COLUMNS = [
    ("event_count", "INTEGER"),
    ("parent_annotation_id", "INTEGER REFERENCES annotations(id)"),
    ("status", "TEXT"),
    ("relation_kind", "TEXT CHECK (relation_kind IN ('type_specimen', 'sub_window') "
                       "OR relation_kind IS NULL)"),
    # Part E7: soft delete — NULL means "not deleted". `delete_annotation`
    # sets this instead of removing the row, so an accidental delete has an
    # undo. `list_annotations` excludes non-NULL rows by default.
    ("deleted_at", "TEXT"),
]

# Columns added to `runs` by the run-tracking/provenance feature (part 2).
_RUNS_NEW_COLUMNS = [
    ("finished_at", "TEXT"),
    ("duration_s", "REAL"),
    ("error_text", "TEXT"),
    ("step_timings_json", "TEXT"),
    # T24: the index of the step a background run is currently executing, so a
    # poller can read progress off the run row. NULL before the first step and
    # on a reused run; left at the last started step when a run fails/cancels.
    ("current_step", "INTEGER"),
    # Fan-out (run_groups) and surrogate-control pairing, both nullable —
    # a run belongs to neither unless something opts it in.
    ("run_group_id", "INTEGER REFERENCES run_groups(id)"),
    ("surrogate_of_run_id", "INTEGER REFERENCES runs(id)"),
    # T67: a researcher-chosen label. A label, never an identifier — nothing
    # keys on it and no uniqueness constraint applies; the recipe hash remains
    # a run's content identity.
    ("name", "TEXT"),
    # Stage-3 prompt 04 (spec §7.4, "Discard run"): a discarded run is marked
    # superseded and writes NO adjudications — a whole-run discard writing
    # thousands of `not_interesting` human verdicts would poison the RQ5
    # divergence measurement. The run row, its config and its detections all
    # stay; only these two columns change, so the discard is reversible and
    # the run stays reproducible from its own recipe.
    ("superseded_at", "TEXT"),
    ("superseded_by_run_id", "INTEGER REFERENCES runs(id)"),
]

# `motifs` += the symbolic SAX string, when one exists for the motif's span.
_MOTIFS_NEW_COLUMNS = [
    ("sax_string", "TEXT"),
]

# The two scales a motif-library entry may take (ticket 52). Stored, never
# inferred from a span's duration: a long single event and a short spike
# train would be silently misclassified by any duration heuristic.
ENTRY_SCALE_EVENT = "event"
ENTRY_SCALE_TRAIN = "train"
ENTRY_SCALES = (ENTRY_SCALE_EVENT, ENTRY_SCALE_TRAIN)

# `motif_entry` += the legacy presentation columns carried across from
# `motifs` by the shape-first migration (ticket 16). They are nullable
# because an entry may be created by eye with no detection to inherit from,
# and because ALTER TABLE ADD COLUMN cannot add a NOT NULL column without a
# default to a table that already has rows.
_MOTIF_ENTRY_NEW_COLUMNS = [
    ("label", "TEXT"),
    ("rating", "INTEGER"),
    ("notes", "TEXT"),
    ("tags", "TEXT"),
    ("sax_string", "TEXT"),
    ("created_at", "TEXT"),
    # T52: distinguishes an event-scale entry (one spike) from a train-scale
    # entry (a whole spike train). Nullable because the column is additive and
    # an eye-created entry may carry no scale.
    ("scale", "TEXT"),
    # Stage-3 prompt 03 (docs/LIBRARY_STORAGE.md §3.2). `content_hash` is the
    # entry's real identity from §2.2 — same hash, same entry, never a second
    # one — while `UNIQUE (recording_id, start_idx, end_idx)` keeps meaning
    # what it always meant about the exemplar span. `fs` is carried so a time
    # axis can be drawn; it is deliberately NOT part of the hash (§2.3), so the
    # same drop at 1 Hz and at 10 Hz is one entry with fs on each exemplar.
    # `source_kind`/`source_store`/`source_ref` are what makes a re-import
    # idempotent and a snippets.npz key recoverable from the row alone.
    # All nullable: 118 entries already exist and ALTER TABLE ADD COLUMN
    # cannot add NOT NULL without a default to a populated table.
    ("content_hash", "TEXT"),
    ("channel", "INTEGER"),
    ("fs", "REAL"),
    ("source_kind", "TEXT"),
    ("source_store", "TEXT"),
    ("source_ref", "TEXT"),
]


# `motif_member` += the same identity half plus a pointer to its current
# revision (docs/LIBRARY_STORAGE.md §3.2, §2.5). A member is one OCCURRENCE of
# a shape; re-describing that occurrence writes a `motif_member_revision` row
# and moves `current_revision_id`, never a second member. `channel` is
# denormalised off `recordings` because every library reader filters on it and
# the join is otherwise paid per row. Nullable for the reason above.
_MOTIF_MEMBER_NEW_COLUMNS = [
    ("content_hash", "TEXT"),
    ("channel", "INTEGER"),
    ("current_revision_id", "INTEGER REFERENCES motif_member_revision(id)"),
]


# Stage-3 Prompt 02 (docs/DATA_REGISTRATION.md): registration provenance on
# `recordings`, all nullable / defaulted so the 70 existing rows are untouched.
# `parent_recording_id` + `parent_offset` + `decimation` record that a row is
# an EXCERPT of another registered channel (block-mean decimated subset; the
# Mushroom_260720 / L_LM_Jul_26_J case) — the row and its id are kept because
# runs and detections reference it. `active = 0` is the soft unregister.
_RECORDINGS_REGISTRATION_COLUMNS = [
    ("parent_recording_id", "INTEGER REFERENCES recordings(id)"),
    ("parent_offset", "INTEGER"),
    ("decimation", "INTEGER"),
    ("fs_source", "TEXT"),          # 'read' | 'inferred'
    ("registered_at", "TEXT"),
    ("registered_by", "TEXT"),
    ("warnings_json", "TEXT"),
    ("active", "INTEGER NOT NULL DEFAULT 1"),
]

# fixup-b: the unit the channel's samples are stored in ('V' | 'mV' | 'uV';
# NULL = undeclared) and where that unit came from. Nothing recorded it before,
# and the web UI printed stored volts as "mV" for two years. `Working.units`
# is the vocabulary and holds the per-file evidence the backfill below applies.
_RECORDINGS_UNITS_COLUMNS = [
    ("units", "TEXT"),
    ("units_note", "TEXT"),
]

# `encodings` += the same soft-unregister flag (an encoding is a registrable kind).
_ENCODINGS_REGISTRATION_COLUMNS = [
    ("active", "INTEGER NOT NULL DEFAULT 1"),
]

# The registry of artifacts that are not recordings or encodings (models,
# matrix profiles, window matrices, window sets, drop-motif stores, catalogue
# spreadsheets, HPC result bundles). One row per registered file or
# directory; the bulk data stays on disk at `path` (rule 4) and the sidecar
# `<path>.manifest.json` (`manifest_path`) carries the provenance. `active =
# 0` is the soft unregister. `settings` holds every project setting the
# Settings pages save (page, key, JSON value); `audit_log` is append-only:
# nothing in the codebase updates or deletes a row.
_REGISTRATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS registered_artifacts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kind           TEXT    NOT NULL,
    path           TEXT    NOT NULL,
    name           TEXT,
    manifest_path  TEXT,
    recording_id   INTEGER REFERENCES recordings(id),
    channel        INTEGER,
    span_start     INTEGER,
    span_end       INTEGER,
    fs             REAL,
    params_json    TEXT,
    producer       TEXT,
    sha1           TEXT,
    checks_json    TEXT,
    warnings_json  TEXT,
    created_at     TEXT    NOT NULL,
    actor          TEXT,
    active         INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_registered_artifacts_kind ON registered_artifacts(kind, active);
CREATE INDEX IF NOT EXISTS idx_registered_artifacts_path ON registered_artifacts(path);

CREATE TABLE IF NOT EXISTS settings (
    page        TEXT NOT NULL,
    key         TEXT NOT NULL,
    value_json  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    actor       TEXT,
    PRIMARY KEY (page, key)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    at           TEXT NOT NULL,
    kind         TEXT NOT NULL,
    what         TEXT NOT NULL,
    where_       TEXT NOT NULL,
    route        TEXT,
    actor        TEXT NOT NULL,
    detail_json  TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_log_kind ON audit_log(kind);
"""


def _migrate_columns(conn, table, new_columns):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, coltype in new_columns:
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")
    conn.commit()


def _migrate_annotations_columns(conn):
    _migrate_columns(conn, "annotations", _ANNOTATIONS_NEW_COLUMNS)


def _migrate_runs_columns(conn):
    _migrate_columns(conn, "runs", _RUNS_NEW_COLUMNS)


def _migrate_motifs_columns(conn):
    _migrate_columns(conn, "motifs", _MOTIFS_NEW_COLUMNS)


def _migrate_motif_entry_columns(conn):
    _migrate_columns(conn, "motif_entry", _MOTIF_ENTRY_NEW_COLUMNS)


# Stage-3 prompt 01 (docs/BLOCK_INTEGRATION.md "Templates"): a template is a
# named, versioned, typed chain. `kind` is detection|encoding|training|
# interrogation (derived from the terminal type when not given), `builtin`
# marks a row seeded from webui/server/templates.py (copied, never edited in
# place), `version` increments on every edit. All nullable/defaulted so the
# two-column rows the core's `save_template` wrote still read.
_TEMPLATES_NEW_COLUMNS = [
    ("kind", "TEXT"),
    ("version", "INTEGER NOT NULL DEFAULT 1"),
    ("builtin", "INTEGER NOT NULL DEFAULT 0"),
    ("description", "TEXT"),
    ("created_at", "TEXT"),
    ("updated_at", "TEXT"),
]


def _migrate_templates_columns(conn):
    _migrate_columns(conn, "templates", _TEMPLATES_NEW_COLUMNS)


# Stage-3 prompt 01 (docs/BLOCK_INTEGRATION.md "Long work"): the persisted job
# model behind webui/server/jobs.py. One row per job the bridge starts, of
# kind chain_run | sweep | import | regroup | training; `run_id` links a chain
# run to the `runs` row the core wrote. Additive: CREATE TABLE IF NOT EXISTS.
_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY,
    kind          TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    started_at    TEXT,
    finished_at   TEXT,
    cancelled     INTEGER NOT NULL DEFAULT 0,
    meta_json     TEXT,
    progress_json TEXT,
    error_json    TEXT,
    run_id        INTEGER REFERENCES runs(id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_kind_status ON jobs(kind, status);
"""


def _migrate_jobs_table(conn):
    conn.executescript(_JOBS_SCHEMA)
    conn.commit()


# Stage-3 prompt 04 (spec §7.1, P17): a Discovery session is a named scope —
# one recording, one or more channels, one section — holding a list of runs,
# each either a template applied across that scope or a seed search over it.
# `run_groups` deliberately carries only an id and a timestamp, so the plan
# itself (which channel was target 3, which seed, which cut) has to live
# somewhere: here, not in the job's in-memory result, which a server restart
# discards. `discovery_runs.run_key` is the stable key the page uses; the real
# runs are reached through `run_group_id`. Additive: CREATE TABLE IF NOT EXISTS.
_DISCOVERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS discovery_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    source_file   TEXT    NOT NULL,
    channels_json TEXT    NOT NULL,
    span_start    INTEGER,
    span_end      INTEGER,
    null_json     TEXT,
    state_json    TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL REFERENCES discovery_sessions(id),
    run_key       TEXT    NOT NULL,
    kind          TEXT    NOT NULL,
    label         TEXT    NOT NULL,
    colour        TEXT,
    template_id   INTEGER,
    template_name TEXT,
    run_group_id  INTEGER REFERENCES run_groups(id),
    job_id        INTEGER,
    params_json   TEXT,
    status        TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL,
    superseded_at TEXT,
    UNIQUE (session_id, run_key)
);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_session ON discovery_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_group ON discovery_runs(run_group_id);
"""


def _migrate_discovery_tables(conn):
    conn.executescript(_DISCOVERY_SCHEMA)
    conn.commit()


# Stage-3 prompt 05 (spec S10.1, P20/P21): the Review workspace's own tables.
# Additive: CREATE TABLE IF NOT EXISTS only.
#
# `review_queues` exists because a queue is a QUESTION PUT TO A PERSON, and a
# question has properties no source table can carry: who is being asked, with
# the machine score hidden or not (P20 blinding), capped at how many, writing
# into which table. Prompt 04 offered to keep the descriptor inside
# `discovery_sessions.state_json` (requests/04-to-05.md S1) and that is the
# right storage for a Discovery-shaped queue only; four of the five queue kinds
# in S10.1 have no discovery session to live in (a seeded search, an Explore
# span set, a training window set, Library's `extract events`). One table that
# every kind can name is what makes the Jobs page's queue group and the
# header's "N need you" a single read instead of five.
#
# A queue holds NO items. `source_kind` + `source_ref` say where the items come
# from and they are resolved live, so a verdict written here immediately
# changes the count Discovery shows (04-to-05 S1) and a discarded run
# (`runs.superseded_at`) stops arriving without anything to keep in step.
#
# `writes_to` is stored rather than derived because it is the rule-5 decision
# (CLAUDE.md rule 5) made ONCE, at queue creation, where a person can read it,
# instead of re-inferred at each verdict where a wrong inference would be a
# silent crossing. It is CHECKed to the two verdict tables.
_REVIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_queues (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    source_kind   TEXT    NOT NULL CHECK (source_kind IN (
                      'discovery-run', 'seed-search', 'explore-spans',
                      'training-windows', 'model-verification',
                      'extract-events')),
    -- What the source kind points at: a run_group_id, a session/search id, a
    -- window-set id, or empty for a whole-corpus sweep. TEXT because the five
    -- kinds key on different things and a typed column per kind would be five
    -- mostly-null columns.
    source_ref    TEXT,
    -- The unit a verdict lands on, and therefore which table it writes.
    unit          TEXT    NOT NULL CHECK (unit IN ('detection', 'human span', 'window', 'sequence')),
    writes_to     TEXT    NOT NULL CHECK (writes_to IN ('adjudications', 'annotations', 'window_verdicts')),
    blind         INTEGER NOT NULL DEFAULT 0,
    -- NULL = no cap. A cap is a promise about how long the queue is, so the
    -- pace and progress readouts mean something.
    cap           INTEGER,
    verdict_options TEXT,          -- JSON list; NULL = the full vocabulary
    filters_json  TEXT,            -- JSON dict passed through to the source resolver
    created_at    TEXT    NOT NULL,
    closed_at     TEXT,
    note          TEXT
);
CREATE INDEX IF NOT EXISTS idx_review_queues_open
    ON review_queues(closed_at);
CREATE INDEX IF NOT EXISTS idx_review_queues_source
    ON review_queues(source_kind, source_ref);

-- A verdict on a TRAINING or VERIFICATION WINDOW (fog A13). A window is not a
-- detection and not a span a person drew: it is one index into a window set,
-- and it has no row in `detections` to adjudicate and no extent a person
-- chose to annotate. Writing a window verdict into either of those tables
-- would be exactly the crossing rule 5 forbids -- an invented detection or an
-- invented human span -- so it gets its own table, keyed by the window set and
-- the index within it.
CREATE TABLE IF NOT EXISTS window_verdicts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    window_set_id  INTEGER NOT NULL REFERENCES window_sets(id),
    window_index   INTEGER NOT NULL,
    verdict        TEXT    NOT NULL,
    note           TEXT,
    queue_id       INTEGER REFERENCES review_queues(id),
    created_at     TEXT    NOT NULL,
    UNIQUE (window_set_id, window_index)
);
CREATE INDEX IF NOT EXISTS idx_window_verdicts_set
    ON window_verdicts(window_set_id);

-- One row per verdict written through Review, in order, so undo (Ctrl-Z) is a
-- replayable fact rather than client state, and so a batch action is ONE
-- audit row covering N writes (S10, P20) instead of N indistinguishable ones.
-- `payload_json` holds what is needed to reverse the write -- the prior
-- verdict if there was one -- because reversing to "unjudged" and reversing to
-- "it was `interesting` before" are different acts.
CREATE TABLE IF NOT EXISTS review_audit (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    queue_id     INTEGER REFERENCES review_queues(id),
    action       TEXT    NOT NULL,     -- verdict | batch | promote | cluster | extract | undo
    target_table TEXT,
    target_ids   TEXT,                 -- JSON list of row ids written
    payload_json TEXT,
    undone_at    TEXT,
    created_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_audit_queue
    ON review_audit(queue_id, id);
"""


def _migrate_review_tables(conn):
    conn.executescript(_REVIEW_SCHEMA)
    conn.commit()


def _migrate_motif_member_columns(conn):
    _migrate_columns(conn, "motif_member", _MOTIF_MEMBER_NEW_COLUMNS)


# Stage-3 prompt 03 (docs/LIBRARY_STORAGE.md §3.3): the Library's new units.
# Additive: CREATE TABLE IF NOT EXISTS only, nothing that already exists is
# touched. The two indexes on columns this prompt ADDS to `motif_entry` /
# `motif_member` live in `_LIBRARY_INDEX_SCHEMA` below, because an index
# cannot be created before the column it covers.
_LIBRARY_SCHEMA = """
-- One revision of a member's span: the same occurrence re-described, never a
-- second member (spec §4.2). Revision 1 is the span the matcher compares
-- against; the current revision is what the researcher sees. `origin` picks
-- which provenance pointer is set, and the two are separate columns rather
-- than one polymorphic id because a machine detection and a human annotation
-- must stay distinguishable at the storage level (CLAUDE.md rule 5): a human
-- extent edit writes a new `annotations` row and NEVER mutates the detection,
-- so the run still reproduces from its recipe.
CREATE TABLE IF NOT EXISTS motif_member_revision (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id      INTEGER NOT NULL REFERENCES motif_member(id),
    revision       INTEGER NOT NULL,
    origin         TEXT    NOT NULL CHECK (origin IN ('machine','human')),
    detection_id   INTEGER REFERENCES detections(id),
    annotation_id  INTEGER REFERENCES annotations(id),
    start_idx      INTEGER NOT NULL,
    end_idx        INTEGER NOT NULL,
    content_hash   TEXT,
    created_at     TEXT    NOT NULL,
    superseded_at  TEXT,
    UNIQUE (member_id, revision)
);
CREATE INDEX IF NOT EXISTS idx_motif_member_revision_member
    ON motif_member_revision(member_id);

-- A run of events in order, with gaps between them. A sequence is a different
-- UNIT from a single motif, not a longer one: its identity is its ordered
-- composition — which shapes, in what order, with what gaps — and that cannot
-- be a content hash of one waveform, which is all `motif_entry` can hold. The
-- second reason it is its own table is CLAUDE.md rule 5 (§3.5 of the
-- standard): a sequence read out of a detector's CSV is a machine claim and a
-- sequence read out of `annotations` is a person's, and `origin` is what picks
-- which write door the row goes through. Folding both into `motif_entry` would
-- have made them indistinguishable, which is how that rule gets broken quietly.
-- `needs_extraction = 1` is the honest state for a catalogued span whose
-- singular events have not been resolved: the claim is recorded (`n_events` as
-- the source stated it), the events are not invented, and no
-- `sequence_members` rows exist for it yet.
CREATE TABLE IF NOT EXISTS sequences (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_key     TEXT    NOT NULL,
    origin           TEXT    NOT NULL CHECK (origin IN ('machine','human')),
    recording_id     INTEGER REFERENCES recordings(id),
    channel          INTEGER,
    start_idx        INTEGER,
    end_idx          INTEGER,
    n_events         INTEGER,
    needs_extraction INTEGER NOT NULL DEFAULT 0,
    source_kind      TEXT,
    source_store     TEXT,
    source_ref       TEXT,
    annotation_id    INTEGER REFERENCES annotations(id),
    content_hash     TEXT,
    created_at       TEXT    NOT NULL,
    UNIQUE (sequence_key, origin)
);
CREATE INDEX IF NOT EXISTS idx_sequences_origin ON sequences(origin);
CREATE INDEX IF NOT EXISTS idx_sequences_needs_extraction
    ON sequences(needs_extraction);

-- One singular event's place in one sequence, in time order. `member_id` is
-- nullable because a sequence may be extracted later: the position, span and
-- gap can be known before the event has been promoted to a `motif_member`.
-- `gap_before` is seconds from the previous event's onset, and is part of what
-- makes two sequences of the same six shapes different sequences.
CREATE TABLE IF NOT EXISTS sequence_members (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id  INTEGER NOT NULL REFERENCES sequences(id),
    position     INTEGER NOT NULL,
    member_id    INTEGER REFERENCES motif_member(id),
    start_idx    INTEGER NOT NULL,
    end_idx      INTEGER NOT NULL,
    gap_before   REAL,
    UNIQUE (sequence_id, position)
);
CREATE INDEX IF NOT EXISTS idx_sequence_members_sequence
    ON sequence_members(sequence_id);

-- A saved grouping: one question asked of the catalogue, with its answer. The
-- question is `unit x basis x method(params)`; `params_json` is canonical JSON
-- carrying the method's parameters AND the cut, so the grouping can be re-run
-- and shown to have produced the same families. The counts are cached because
-- a Library list wants them per row and recomputing them means re-reading
-- every assignment.
CREATE TABLE IF NOT EXISTS groupings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    unit         TEXT    NOT NULL CHECK (unit IN ('single_motifs','sequences','spike_trains')),
    basis        TEXT    NOT NULL,
    method       TEXT    NOT NULL,
    params_json  TEXT    NOT NULL,
    cut          REAL,
    filters_json TEXT,
    n_families   INTEGER,
    n_assigned   INTEGER,
    n_omitted    INTEGER,
    recipe_hash  TEXT,
    created_at   TEXT    NOT NULL,
    actor        TEXT
);

-- One member's place in one grouping. `family_id IS NULL` means OMITTED and
-- `omit_reason` says why: an omitted member is flagged, never deleted (spec
-- §8.2), so "what fell outside the cut" stays answerable. `unit` says which
-- table `member_ref` points into (motif_member, or sequences), which is why
-- there is no foreign key on it. `content_hash` is copied onto the row so a
-- hand edit can key to the same shape across a regroup, a re-import or a
-- re-clustering, when every member id may have changed.
CREATE TABLE IF NOT EXISTS grouping_assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    grouping_id  INTEGER NOT NULL REFERENCES groupings(id),
    unit         TEXT    NOT NULL,
    member_ref   INTEGER NOT NULL,
    content_hash TEXT,
    family_id    INTEGER,
    family_label TEXT,
    distance     REAL,
    is_medoid    INTEGER NOT NULL DEFAULT 0,
    omit_reason  TEXT,
    UNIQUE (grouping_id, unit, member_ref)
);
CREATE INDEX IF NOT EXISTS idx_grouping_assignments_grouping
    ON grouping_assignments(grouping_id);
CREATE INDEX IF NOT EXISTS idx_grouping_assignments_content_hash
    ON grouping_assignments(content_hash);

-- A hand edit, sitting OUTSIDE every grouping and re-applied on top of each
-- one. It is keyed by `content_hash` and not by `motif_member.id` on purpose:
-- a member id is an accident of when a row was written, and a re-import or a
-- rebuilt grouping renumbers them, which would silently drop the researcher's
-- decisions. The hash is the shape itself, so an edit made in March survives a
-- re-clustering in June. `grouping_id IS NULL` means the edit applies to every
-- grouping; `active = 0` is the undo, so an edit is withdrawn rather than
-- erased and the history of the catalogue stays readable.
CREATE TABLE IF NOT EXISTS hand_edits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash  TEXT    NOT NULL,
    kind          TEXT    NOT NULL CHECK (kind IN ('add_member','remove_member','make_exemplar','tag','class')),
    family_label  TEXT,
    value         TEXT,
    grouping_id   INTEGER REFERENCES groupings(id),
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL,
    actor         TEXT
);
CREATE INDEX IF NOT EXISTS idx_hand_edits_content_hash ON hand_edits(content_hash);

-- A saved window set (spec P18 / §6.9 / §8.8): the training-window bookkeeping
-- for one recording. The window bounds themselves are bulk arrays and stay on
-- disk at `path` (CLAUDE.md rule 4); what is in the row is everything needed
-- to judge the set without opening it — the split rule and its assignment, the
-- spacing check, and the human-verdict coverage AS IT WAS AT SAVE TIME, which
-- is recorded rather than recomputed because a later annotation must not
-- silently rewrite the provenance of a model already trained on this set.
-- `(name, version)` is unique so editing a set makes a new version instead of
-- overwriting the one a model was trained from.
CREATE TABLE IF NOT EXISTS window_sets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    version        INTEGER NOT NULL DEFAULT 1,
    path           TEXT    NOT NULL,
    recording_id   INTEGER REFERENCES recordings(id),
    channel        INTEGER,
    fs             REAL,
    window_length  INTEGER,
    stride         INTEGER,
    gap            INTEGER,
    n_windows      INTEGER,
    split_json     TEXT,
    spacing_json   TEXT,
    coverage_json  TEXT,
    labels_source  TEXT,
    recipe_hash    TEXT,
    created_at     TEXT    NOT NULL,
    UNIQUE (name, version)
);
CREATE INDEX IF NOT EXISTS idx_window_sets_name ON window_sets(name);
"""


# The content-hash indexes over the two OLD tables. Separate from
# `_LIBRARY_SCHEMA` only because `_migrate_columns` has to add the columns
# first — "resolve this hash to its entry" is the Library's hottest lookup and
# a scan over 118 entries today is 10 000 tomorrow.
_LIBRARY_INDEX_SCHEMA = """
CREATE INDEX IF NOT EXISTS idx_motif_entry_content_hash ON motif_entry(content_hash);
CREATE INDEX IF NOT EXISTS idx_motif_member_content_hash ON motif_member(content_hash);
"""


def _migrate_library_tables(conn):
    conn.executescript(_LIBRARY_SCHEMA)
    conn.commit()


def _migrate_library_indexes(conn):
    conn.executescript(_LIBRARY_INDEX_SCHEMA)
    conn.commit()


def _migrate_recordings_registration_columns(conn):
    _migrate_columns(conn, "recordings", _RECORDINGS_REGISTRATION_COLUMNS)


def _migrate_recordings_units(conn):
    """Add the unit columns, then backfill the measured unit onto every row of
    a known source file that carries neither a unit nor a note. The guard is
    what keeps this idempotent AND what keeps a unit a person declared (or a
    registration supplied) from ever being overwritten by the table."""
    from Working.units import RECORDING_UNITS_EVIDENCE
    _migrate_columns(conn, "recordings", _RECORDINGS_UNITS_COLUMNS)
    for source_file, (units, note) in RECORDING_UNITS_EVIDENCE.items():
        conn.execute("UPDATE recordings SET units = ?, units_note = ? "
                     "WHERE source_file = ? AND units IS NULL AND units_note IS NULL",
                     (units, note, source_file))
    conn.commit()


def _migrate_encodings_registration_columns(conn):
    _migrate_columns(conn, "encodings", _ENCODINGS_REGISTRATION_COLUMNS)


def _create_registration_tables(conn):
    """`registered_artifacts`, `settings`, `audit_log` — CREATE IF NOT EXISTS only."""
    conn.executescript(_REGISTRATION_SCHEMA)
    conn.commit()


def _backfill_motif_entries(conn):
    """Copy legacy `motifs` rows into `motif_entry`, then their tag links.

    Idempotent: entries are only inserted for (recording, sample range)
    spans that aren't already present, and `motif_entry_tags` has a UNIQUE
    pair, so re-running this never doubles either the entries or their
    links. The legacy `motifs` table is left in place — this migration is
    additive, not a destructive rebuild (standards rule 2.2).

    A motif's detection pointer is retained as `motif_entry.detection_id`;
    the entry's own identity is the span it was found at.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO motif_entry
            (recording_id, start_idx, end_idx, detection_id,
             label, rating, notes, tags, sax_string, created_at)
        SELECT r.recording_id, d.start_idx, d.end_idx, d.id,
               m.label, m.rating, m.notes, m.tags, m.sax_string, m.created_at
        FROM motifs m
        JOIN detections d ON d.id = m.detection_id
        JOIN runs r ON r.id = d.run_id
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO motif_entry_tags (entry_id, tag_id)
        SELECT e.id, mt.tag_id
        FROM motif_tags mt
        JOIN motifs m ON m.id = mt.motif_id
        JOIN detections d ON d.id = m.detection_id
        JOIN runs r ON r.id = d.run_id
        JOIN motif_entry e
          ON e.recording_id = r.recording_id
         AND e.start_idx = d.start_idx
         AND e.end_idx = d.end_idx
        """
    )
    conn.commit()


# ── The verdict-constraint rebuild ────────────────────────────────────────────
# SQLite cannot ALTER a CHECK constraint in place, so widening the verdict
# vocabulary means the full rebuild: create a new table, copy every row across,
# drop the old one, rename. Against eleven thousand rows of manual labelling
# that cannot be regenerated from raw data plus code, the failure mode to design
# against is the quiet one — a column left out of the INSERT ... SELECT does not
# raise, it just arrives empty.
#
# So: the copy list is derived from `PRAGMA table_info` on the *live* table
# rather than from a list written here (a list here would go stale the next time
# someone adds a column); a column the new table cannot carry aborts the
# migration instead of being dropped; the whole thing runs inside one
# transaction with the row and link counts verified before COMMIT, so a mismatch
# rolls back rather than lands; and the file is backed up first regardless.

_ANNOTATIONS_REBUILD_SQL = """
CREATE TABLE annotations_rebuild (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    start_idx     INTEGER NOT NULL,
    end_idx       INTEGER NOT NULL,
    verdict       TEXT    NOT NULL CHECK (verdict IN (__VERDICTS__)),
    tag           TEXT,
    note          TEXT,
    scale_viewed  TEXT,
    source        TEXT    NOT NULL,
    created_at    TEXT    NOT NULL,
    event_count   INTEGER,
    -- Still spelled `annotations`, not `annotations_rebuild`: a forward
    -- reference while the old table stands, self-referencing after the rename.
    parent_annotation_id INTEGER REFERENCES annotations(id),
    status        TEXT,
    relation_kind TEXT CHECK (relation_kind IN ('type_specimen', 'sub_window')
                              OR relation_kind IS NULL),
    deleted_at    TEXT
)
"""
_ANNOTATIONS_REBUILD_SQL = _ANNOTATIONS_REBUILD_SQL.replace(
    "__VERDICTS__", _VERDICT_SQL_LIST)


def _annotations_verdict_is_current(conn):
    """True when the live CHECK constraint already names every term in VERDICTS."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'annotations'"
    ).fetchone()
    if row is None or row[0] is None:
        return True
    return all("'{}'".format(v) in row[0] for v in VERDICTS)


def _backup_database(conn, db_path):
    """Snapshot the database beside itself before anything destructive runs.

    Uses SQLite's own backup API rather than a file copy, so the snapshot is
    transactionally consistent even with the connection open.
    """
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = "{}.pre-seed-rebuild-{}.bak".format(db_path, stamp)
    dest = sqlite3.connect(backup_path)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    return backup_path


def _migrate_annotations_verdict(conn, db_path=None):
    """Rebuild `annotations` so its verdict CHECK accepts every term in VERDICTS.

    Idempotent: once the live constraint names all five terms this is one
    `sqlite_master` read and nothing more — no re-copy, no fresh backup on every
    startup.

    Returns
    -------
    str or None
        Path of the backup written before the rebuild, or None if no rebuild
        was needed (or the database is in-memory, where there is no file to
        back up).
    """
    if _annotations_verdict_is_current(conn):
        return None

    # Indexes and triggers are dropped along with the table and SQLite does not
    # warn you. Capture them now; recreate them after the rename. `sql IS NOT
    # NULL` skips the auto-indexes SQLite creates for UNIQUE/PK, which come back
    # with the new table on their own.
    dependents = [
        r[0] for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type IN ('index', 'trigger') "
            "AND tbl_name = 'annotations' AND sql IS NOT NULL")
    ]

    backup_path = None
    if db_path and db_path != ":memory:":
        backup_path = _backup_database(conn, db_path)

    live_cols = [r["name"] for r in conn.execute("PRAGMA table_info(annotations)")]

    # `PRAGMA foreign_keys` is a no-op inside a transaction, so it has to be set
    # before BEGIN — hence autocommit and explicit transaction control here.
    fk_was_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    prior_isolation = conn.isolation_level
    conn.commit()
    conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        n_rows = conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
        n_links = conn.execute("SELECT COUNT(*) FROM annotation_tags").fetchone()[0]

        conn.execute(_ANNOTATIONS_REBUILD_SQL)
        new_cols = {r["name"] for r in
                    conn.execute("PRAGMA table_info(annotations_rebuild)")}
        orphans = [c for c in live_cols if c not in new_cols]
        if orphans:
            raise RuntimeError(
                "annotations carries column(s) the rebuild would drop: {}. "
                "Add them to _ANNOTATIONS_REBUILD_SQL before migrating."
                .format(", ".join(orphans)))

        cols = ", ".join(live_cols)
        conn.execute("INSERT INTO annotations_rebuild ({0}) SELECT {0} FROM annotations"
                     .format(cols))
        copied = conn.execute("SELECT COUNT(*) FROM annotations_rebuild").fetchone()[0]
        if copied != n_rows:
            raise RuntimeError(
                "rebuild copied {} of {} annotations".format(copied, n_rows))

        conn.execute("DROP TABLE annotations")
        conn.execute("ALTER TABLE annotations_rebuild RENAME TO annotations")
        for sql in dependents:
            conn.execute(sql)

        # Verified inside the transaction, so a mismatch rolls back.
        final_rows = conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
        final_links = conn.execute("SELECT COUNT(*) FROM annotation_tags").fetchone()[0]
        if (final_rows, final_links) != (n_rows, n_links):
            raise RuntimeError(
                "rebuild ended with {} rows / {} tag links, expected {} / {}"
                .format(final_rows, final_links, n_rows, n_links))
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "rebuild left {} foreign-key violation(s)".format(len(violations)))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.isolation_level = prior_isolation
        if fk_was_on:
            conn.execute("PRAGMA foreign_keys = ON")

    print("[schema] annotations verdict constraint rebuilt: {} rows, {} tag links "
          "preserved; backup at {}".format(n_rows, n_links, backup_path))
    return backup_path


def get_connection(db_path=None):
    """Open a connection with row access by column name and FKs enforced.

    Parameters
    ----------
    db_path : str, optional
        Defaults to `DB_PATH` (DATA/db/annotations.sqlite). Pass ":memory:"
        or a temp path for tests.
    """
    db_path = DB_PATH if db_path is None else db_path
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Create every table (and index) if it doesn't already exist.

    Safe to call on every startup — CREATE TABLE/INDEX IF NOT EXISTS only.

    Returns
    -------
    sqlite3.Connection
    """
    db_path = DB_PATH if db_path is None else db_path
    conn = get_connection(db_path)
    conn.executescript(_SCHEMA)
    conn.commit()
    _migrate_annotations_columns(conn)
    _migrate_runs_columns(conn)
    _migrate_motifs_columns(conn)
    _migrate_motif_entry_columns(conn)
    # The library tables come before the `motif_member` columns because
    # `current_revision_id` references `motif_member_revision(id)`, and before
    # the index pass because an index needs its column to exist.
    _migrate_library_tables(conn)
    _migrate_motif_member_columns(conn)
    _migrate_library_indexes(conn)
    _migrate_templates_columns(conn)
    _migrate_jobs_table(conn)
    _migrate_discovery_tables(conn)
    # After the library tables: `window_verdicts` references `window_sets`.
    _migrate_review_tables(conn)
    _migrate_recordings_registration_columns(conn)
    _migrate_recordings_units(conn)
    _migrate_encodings_registration_columns(conn)
    _create_registration_tables(conn)
    # The backfill must run after `motif_entry` has every column it copies
    # into, and after `motifs.sax_string` exists on legacy databases.
    _backfill_motif_entries(conn)
    # Must run after the column migrations: the rebuild copies whatever columns
    # the live table has, so they need to be there first.
    _migrate_annotations_verdict(conn, db_path)
    return conn
