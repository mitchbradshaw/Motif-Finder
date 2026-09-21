"""
event_store.py
==============
`docs/LIBRARY_STORAGE.md` §5, row one: a registered `drop_motif_store`
(`events.csv` + `snippets.npz` + `manifest.json`) becoming `motif_entry` +
`motif_member` rows, each with revision 1 and origin `machine`.

What this importer is for, in one line: **the detector found shapes; the
Library is the catalogue of shapes.** Everything below follows from the gap
between those two sentences.

The shape of the work
---------------------
Per event: read its waveform out of the store's own `snippets.npz`, hash it
(§2.2), ask `dedupe.classify` what it already is (§2.4), and write accordingly.

    new    -> a `motif_entry`, its first `motif_member`, and revision 1
    exact  -> no second entry. A new member if the occurrence is new;
              otherwise nothing, because the occurrence is already described
    near   -> still its own entry, PLUS a flag. Never merged

The waveform that is hashed
---------------------------
**`detrended_mv`.** §2.3 says the importer picks one of the store's three
arrays and states which, and this is the statement. It is read through
`Working.Detection.drop_motifs.cluster.event_waveform`, whose default this is
and whose docstring gives the reason: the detrended trace is what detection ran
on and what "the same shape" was defined against, while the raw trace still
carries the channel's slow baseline. Hashing `raw_mv` would let the same drop
on a drifting baseline and on a flat one become two entries; `__t_s` is a time
axis and not a waveform at all.

Three refusals, all loud
------------------------
1. **The held-out file.** Any event binding to a recording whose `source_file`
   is `Working.config.HELD_OUT_RECORDING_FILE` aborts the whole import. Nothing
   is left behind — a partial import that quietly dropped the held-out rows
   would be indistinguishable from a complete one.
2. **A partial store.** `Plots/drop_motifs12a/*_PARTIAL` is readable by
   `read_event_store` and refused by `import_event_store`; see
   `PARTIAL_STORE_REFUSAL` for the reason, which is recorded here rather than
   left as an absence in a run log.
3. **A non-finite or empty waveform**, which `identity.content_hash` raises on.
   A corrupt snippet must not hash to something plausible.

Everything else that cannot be written is **counted with a reason**, never
dropped silently: an unknown `recording_id` is a warning plus a skip, and an
excluded corpus is a skip naming the corpus.

Measured features are NOT stored
--------------------------------
`drop_depth_mv`, `fall_duration_s`, the slopes and `purity` have no columns
here and gain none: §3.4 and spec §4.4 reject measured features on Library rows
outright, because a row's meaning would then depend on whichever interrogation
ran last. `Working/library/grouping/bases.py` computes them on demand.

Nothing here imports a UI library (CLAUDE.md rule 1), and no bulk array enters
the database (rule 4) — the snippets stay on disk and the row carries
`source_store` + `source_ref`, which is exactly the `.npz` key.
"""

import contextlib
import datetime
import json
import os
from collections import Counter
from dataclasses import dataclass, field

from Working.Detection.drop_motifs import store as event_store_io
from Working.Detection.drop_motifs.cluster import event_waveform
from Working.config import HELD_OUT_RECORDING_FILE
from Working.database import runs as R
from Working.database import vocabulary as V
from Working.library import dedupe, revisions
from Working.library.identity import content_hash

#: `motif_entry.source_kind` for every row this importer writes (§3.2).
SOURCE_KIND = "event_store"

#: Which of the store's three arrays is hashed. See the module docstring.
WAVEFORM_FIELD = "detrended_mv"

#: A single event is `scale = 'event'`; a whole spike train would be `'train'`
#: and a sequence is neither — it is its own table (§4).
SCALE = "event"

#: The 1 Hz control corpus, excluded by default and by name.
#:
#: `reishi_1hz` is the *same organism* as `reishi_10hz` recorded at a second
#: sampling rate: the two share `catalogue_id`, `channel` and `recording_id`
#: and differ only in `fs`. Importing both double-counts the organism, and
#: because §2.3 deliberately keeps `fs` out of the hash, the two rates of one
#: curve are one entry anyway — so the second copy adds members, not shapes.
#: The measured consequence, from the scout's verification: the sequence
#: recovery rule reproduces 118/118 real sequences with this corpus excluded
#: and only 52/118 with it included.
#:
#: A parameter and not a hard-coded filter, because "which corpora are
#: controls" is a fact about a particular run and not about the importer.
DEFAULT_EXCLUDED_CORPORA = ("reishi_1hz",)

#: Why `Plots/drop_motifs12a/*_PARTIAL` is not imported on this machine.
PARTIAL_STORE_REFUSAL = (
    "This store is marked partial: true. Region A of its recording was never "
    "detected, 844 of its 1,077 Lion's mane rows carry recording_id = -1, and "
    "its two floor policies (derived_3x_amplitude_MAD and global_0.1mV) are "
    "two views of ONE detection — importing both would put two motif_entry "
    "rows at the same (recording_id, start_idx, end_idx) and collide on that "
    "UNIQUE constraint. Read it with read_event_store() if you need to look "
    "at it; importing it would ship a knowingly incomplete species."
)

#: The tag categories the store's metadata columns land in (§3.4). Species,
#: corpus, morphology and framing are TAGS and not columns, because the
#: Library's label basis for grouping is defined over tags (spec §8.2) and a
#: column is not groupable that way.
TAG_COLUMNS = {
    "morphology": "element",
    "species": "species",
    "corpus": "corpus",
    "framing": "framing",
}

#: Spellings the sources carry that the vocabulary already holds under another
#: spelling. `Stegasauras` is the catalogue spreadsheet's typo; `stegasaurus`
#: is the `tag_vocabulary` row that exists. Normalising at the import seam
#: keeps one term from becoming two groupable families.
TAG_ALIASES = {"stegasauras": "stegasaurus"}

# The outcome vocabulary, one per event.
CREATED = "created"                  # a new entry (a `new` or a `near` verdict)
MEMBER_ADDED = "member_added"        # an `exact` duplicate in a new place
ALREADY_PRESENT = "already_present"  # this occurrence is already described
REVISION_ADDED = "revision_added"    # a known member that carried no revision
SKIPPED = "skipped"


class StoreRefused(ValueError):
    """A store this machine can read but will not import — see
    `PARTIAL_STORE_REFUSAL`. Its own class so a caller can tell a policy
    refusal from a corrupt store, and so the refusal reads as a decision
    rather than as a failure."""


@dataclass
class ImportReport:
    """What an import did, in the shape the Import page draws.

    Carried rather than printed, because the same object serves three readers:
    the dry run (which reports without writing), the bridge's job progress, and
    a test asserting that the second run wrote nothing.
    """

    source: str
    dry_run: bool = False
    n_rows: int = 0
    outcomes: Counter = field(default_factory=Counter)
    skipped: Counter = field(default_factory=Counter)
    warnings: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    samples: list = field(default_factory=list)
    tags_created: list = field(default_factory=list)
    tags_reused: list = field(default_factory=list)

    @property
    def n_created(self):
        return self.outcomes.get(CREATED, 0)

    @property
    def n_duplicate(self):
        """Events that resolved onto an existing shape — `exact` in §2.4 —
        whether they added a member or found their occurrence already there."""
        return self.outcomes.get(MEMBER_ADDED, 0)

    @property
    def n_near_flagged(self):
        return len(self.flags)

    @property
    def n_skipped(self):
        return self.outcomes.get(SKIPPED, 0)

    def as_dict(self):
        """A JSON-safe view for the bridge. `Counter` is a dict subclass but
        serialises as one only after this cast, and the page wants stable key
        order."""
        return {
            "source": self.source,
            "dry_run": self.dry_run,
            "n_rows": self.n_rows,
            "outcomes": dict(self.outcomes),
            "skipped": dict(self.skipped),
            "n_created": self.n_created,
            "n_duplicate": self.n_duplicate,
            "n_near_flagged": self.n_near_flagged,
            "n_skipped": self.n_skipped,
            "warnings": list(self.warnings),
            "flags": list(self.flags),
            "samples": list(self.samples),
            "tags_created": list(self.tags_created),
            "tags_reused": list(self.tags_reused),
        }


# ── reading a store ──────────────────────────────────────────────────────────

# The seed store names its files `events.csv` / `snippets.npz`, which is what
# `store.EVENTS_FILENAME` and `store.SNIPPETS_FILENAME` say and what
# `store.load_events` joins onto the directory. `Plots/drop_motifs10/motifs`
# and both drop_motifs12a stores name the same two files `motifs.csv` /
# `motifs.npz`. They are the same format under two names.
_FILENAME_ALIASES = [("events.csv", "snippets.npz"), ("motifs.csv", "motifs.npz")]


@contextlib.contextmanager
def _store_filenames(events_name, snippets_name):
    """Read a store whose files carry the older `motifs.*` names.

    Rebinding the two module constants for the duration of the read, rather
    than writing a second CSV parser here, is deliberate: `load_events` does
    the int-column coercion that keeps an index from arriving as a float, and a
    second parser would be a second place for that to be got wrong. The
    constants are restored in a `finally`, so a raising read leaves the module
    exactly as it found it.
    """
    old = (event_store_io.EVENTS_FILENAME, event_store_io.SNIPPETS_FILENAME)
    event_store_io.EVENTS_FILENAME = events_name
    event_store_io.SNIPPETS_FILENAME = snippets_name
    try:
        yield
    finally:
        (event_store_io.EVENTS_FILENAME,
         event_store_io.SNIPPETS_FILENAME) = old


def read_event_store(store_path):
    """`{"dir", "events", "snippets", "manifest"}` for one store on disk.

    Reads and refuses nothing — a store that `import_event_store` will not
    import can still be inspected, which is how a decision about it gets made.

    Raises `FileNotFoundError` naming both filename conventions if neither is
    present, because "no event table" and "the table is under its other name"
    are different problems with the same symptom.
    """
    for events_name, snippets_name in _FILENAME_ALIASES:
        if not os.path.exists(os.path.join(store_path, events_name)):
            continue
        with _store_filenames(events_name, snippets_name):
            return {
                "dir": store_path,
                "events": event_store_io.load_events(store_path),
                "snippets": event_store_io.load_snippets(store_path),
                "manifest": _read_manifest(store_path),
            }
    raise FileNotFoundError(
        f"No event table in {store_path!r}: neither events.csv nor motifs.csv "
        "is present. A run that found nothing still writes one, so this is an "
        "unregistered directory rather than an empty store."
    )


def _read_manifest(store_path):
    """The store's manifest, or `{}`.

    Missing is tolerated because the manifest carries provenance and counts
    rather than data; the refusal checks below read it defensively for the same
    reason. A store without one is poorer, not unreadable.
    """
    path = os.path.join(store_path, event_store_io.MANIFEST_FILENAME)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ── the import ───────────────────────────────────────────────────────────────

def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _repo_relative(path):
    """`source_store` as a repo-relative path (§3.2).

    An absolute path on this machine is provenance that stops being true the
    moment the database is copied — and the bridge copies it into
    `webui/runtime/<stamp>/` before every run.
    """
    path = os.path.abspath(path)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        "..", "..", ".."))
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except ValueError:  # a different drive on Windows
        return path.replace(os.sep, "/")


def _normalise_tag(value):
    """One vocabulary term out of one source cell.

    Lower-cased, spaces folded to underscores, and the known typos mapped
    through `TAG_ALIASES`. Returns None for a blank or a sentinel, so a `'...'`
    placeholder cell never becomes a groupable family of one.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"...", "nan", "None", "-1"}:
        return None
    term = text.lower().replace(" ", "_").replace("-", "_")
    return TAG_ALIASES.get(term, term)


def _recording_index(conn):
    """`{recordings.id: row}` for the whole table, read once.

    One query instead of one per event: the real stores are 3,511 rows and the
    lookup is otherwise the import's dominant cost. `recordings` is a few
    hundred rows, so holding it is cheap.
    """
    return {row["id"]: row
            for row in conn.execute("SELECT * FROM recordings").fetchall()}


def _check_held_out(events, recordings):
    """Abort before writing anything if any event binds to the held-out file.

    Checked up front over the whole table rather than per row, so the refusal
    cannot land halfway through an import and leave the library holding the
    first half of a store it was never allowed to hold.
    """
    for event in events:
        recording = recordings.get(int(event["recording_id"]))
        if recording is None:
            continue
        if recording["source_file"] == HELD_OUT_RECORDING_FILE:
            raise ValueError(
                f"Event {event['event_id']!r} binds to recording "
                f"{recording['id']} of {HELD_OUT_RECORDING_FILE!r}, which is "
                "held out on every route. Nothing was imported — a store that "
                "touches the held-out file is refused whole, because a partial "
                "import of it is indistinguishable from a complete one."
            )


def _apply_tags(conn, entry_id, event, report, dry_run):
    """Write the four metadata columns as tags, reusing vocabulary rows (§3.4).

    Reuse is the property worth stating: `sharkfin` and `trough` already exist
    as `element` terms, and creating a second row for either would split one
    morphology into two groupable families. `get_or_create_term` is the
    existing helper for exactly this — an importer that must not silently drop
    an unrecognised value.
    """
    for column, category in TAG_COLUMNS.items():
        value = _normalise_tag(event.get(column))
        if value is None:
            continue
        label = f"{category}={value}"
        existed = V.get_term(conn, category, value) is not None
        (report.tags_reused if existed else report.tags_created).append(label)
        if dry_run:
            continue
        V.get_or_create_term(conn, category, value)
        V.add_motif_entry_tag(conn, entry_id, category, value, commit=False)


def _pending_flags(pending_spans, *, recording_id, channel, start_idx, end_idx,
                   iou_threshold, fraction):
    """Near-duplicate flags against spans this DRY RUN has decided to create.

    `dedupe.find_near_duplicates` asks the database, and in a dry run the
    database is empty of everything the run would have written — so without
    this, a dry run of a store whose first event is the near-duplicate of its
    fourth would report no flags and the real import would then raise one. The
    page's preview has to say what the import will say.

    The record shape is `find_near_duplicates`' own, thresholds included, so a
    caller cannot tell a previewed flag from a real one by its shape.
    """
    flags = []
    candidate = {"recording_id": recording_id, "channel": channel,
                 "start_idx": start_idx, "end_idx": end_idx}
    for span in pending_spans:
        if not dedupe.is_near_duplicate(candidate, span,
                                        iou_threshold=iou_threshold,
                                        fraction=fraction):
            continue
        flags.append({
            "member_id": None,
            "entry_id": None,
            "content_hash": span["content_hash"],
            "start_idx": span["start_idx"],
            "end_idx": span["end_idx"],
            "iou": dedupe.span_iou(start_idx, end_idx,
                                   span["start_idx"], span["end_idx"]),
            "onset_delta": abs(int(start_idx) - int(span["start_idx"])),
            "onset_tolerance": fraction * max(0, int(end_idx) - int(start_idx)),
            "iou_threshold": iou_threshold,
            "onset_tolerance_fraction": fraction,
            "pending": True,
        })
    flags.sort(key=lambda f: -f["iou"])
    return flags


def _record_flag(conn, event, flag, dry_run):
    """Persist one near-duplicate flag as an `audit_log` row.

    The Library has no flag table and gains none here: a flag is a note that a
    person must look at two rows, not a relationship between them, and giving
    it a table would invite code that reads it as one. `audit_log` already
    carries dated, JSON-detailed records of exactly this kind, and the row
    keeps **both thresholds** (§4.6: the rule is recorded on the run), so a
    flag raised today stays readable after the defaults change.
    """
    if dry_run:
        return
    conn.execute(
        """INSERT INTO audit_log (at, kind, what, where_, route, actor, detail_json)
           VALUES (?, 'library_near_duplicate', ?, 'motif_member', NULL, 'importer', ?)""",
        (_now(), str(event["event_id"]), json.dumps(flag, sort_keys=True)),
    )


def import_event_store(conn, store_path, *, source_store=None,
                       exclude_corpora=DEFAULT_EXCLUDED_CORPORA,
                       dry_run=False, progress=None):
    """Import one detector event store into the Library. Returns an `ImportReport`.

    `source_store` overrides the repo-relative path written onto every row;
    it exists because a registered store may be known to the database under a
    path that is not where it currently sits on disk.

    `exclude_corpora` names control corpora to leave out — see
    `DEFAULT_EXCLUDED_CORPORA` for why `reishi_1hz` is the default and why it
    is a parameter.

    `dry_run=True` computes every verdict and reports every count **without
    executing a single INSERT**: the write sites are guarded individually and
    the row counts of every table this function can touch are compared before
    and after, so a dry run that wrote something raises rather than returning a
    report that lies. This is what the Import page's dry run calls.

    `progress` is called as `progress(done, total, message)` once per event, so
    the bridge can drive a job without this module knowing a bridge exists.

    **Idempotent** (PRD story 43): a second run finds every occurrence already
    described and writes nothing.

    Raises `StoreRefused` for a partial store, and `ValueError` if any event
    binds to the held-out recording file — both before anything is written.
    """
    run = read_event_store(store_path)
    manifest = run["manifest"]
    if manifest.get("partial"):
        raise StoreRefused(f"{store_path}: {PARTIAL_STORE_REFUSAL}")

    events, snippets = run["events"], run["snippets"]
    report = ImportReport(source=_repo_relative(store_path), dry_run=dry_run,
                          n_rows=len(events))
    store_ref = source_store or _repo_relative(store_path)
    excluded = {str(c).lower() for c in (exclude_corpora or ())}

    recordings = _recording_index(conn)
    _check_held_out(events, recordings)

    before = _table_counts(conn)
    # A dry run resolves an `exact` duplicate against what the run has already
    # decided as well as against the database, because nothing it decided has
    # been written. Without this, a store holding the same shape twice would
    # report two entries on a dry run and create one for real.
    pending_hashes = {}
    pending_spans = []

    created_at = _now()
    for index, event in enumerate(events, start=1):
        outcome, detail = _import_one(
            conn, event, snippets, recordings, report,
            store_ref=store_ref, excluded=excluded, dry_run=dry_run,
            pending_hashes=pending_hashes, pending_spans=pending_spans,
            created_at=created_at,
        )
        report.outcomes[outcome] += 1
        report.samples.append({
            "source_ref": str(event["event_id"]),
            "recording_id": int(event["recording_id"]),
            "start_idx": int(event["snippet_start_idx"]),
            "end_idx": int(event["snippet_end_idx"]),
            "outcome": outcome,
            "detail": detail,
        })
        if progress is not None:
            progress(index, len(events), f"{event['event_id']}: {outcome}")

    if dry_run:
        # Belt and braces: the guards above are per-write, this is the proof.
        conn.rollback()
        after = _table_counts(conn)
        if after != before:
            raise RuntimeError(
                "A dry run wrote to the database — this is a bug in "
                f"import_event_store, not in the caller. Before: {before}, "
                f"after: {after}."
            )
    else:
        conn.commit()
    return report


def _table_counts(conn):
    """Row counts of every table this importer can write. The dry-run proof."""
    tables = ("motif_entry", "motif_member", "motif_member_revision",
              "motif_entry_tags", "tag_vocabulary", "audit_log")
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in tables}


def _import_one(conn, event, snippets, recordings, report, *, store_ref,
                excluded, dry_run, pending_hashes, pending_spans, created_at):
    """One event. Returns `(outcome, detail)` and never raises for bad data —
    a row that cannot be written is counted with a reason instead, because an
    import of 3,511 events that dies on row 900 has told the researcher
    nothing about rows 901 to 3,511."""
    source_ref = str(event["event_id"])
    corpus = str(event.get("corpus") or "").lower()
    if corpus and corpus in excluded:
        report.skipped["excluded_corpus"] += 1
        return SKIPPED, f"corpus {corpus!r} is excluded"

    recording_id = int(event["recording_id"])
    recording = recordings.get(recording_id)
    if recording is None:
        report.skipped["unknown_recording"] += 1
        report.warnings.append(
            f"{source_ref}: recording_id {recording_id} binds to no row in "
            "`recordings`; the event was skipped and counted."
        )
        return SKIPPED, f"unknown recording_id {recording_id}"

    try:
        values = event_waveform(snippets, event, field=WAVEFORM_FIELD)
        digest = content_hash(values)
    except (KeyError, ValueError) as exc:
        report.skipped["unhashable_waveform"] += 1
        report.warnings.append(f"{source_ref}: {exc}")
        return SKIPPED, str(exc)

    start_idx = int(event["snippet_start_idx"])
    end_idx = int(event["snippet_end_idx"])
    channel = int(event["channel"])

    verdict = dedupe.classify(
        conn, content_hash=digest, recording_id=recording_id, channel=channel,
        start_idx=start_idx, end_idx=end_idx,
    )
    entry_id = verdict["entry_id"]
    flags = list(verdict["flags"])
    if entry_id is None:
        entry_id = pending_hashes.get(digest)
    if dry_run:
        flags.extend(_pending_flags(
            pending_spans, recording_id=recording_id, channel=channel,
            start_idx=start_idx, end_idx=end_idx,
            iou_threshold=verdict["rule"]["iou_threshold"],
            fraction=verdict["rule"]["onset_tolerance_fraction"],
        ))

    if entry_id is None:
        # `new` and `near` both land here: a near-duplicate keeps its own entry
        # and is never merged (§2.4). The flag is the whole difference, and it
        # is raised only on the run that creates the entry — a re-import sees
        # the same overlap and must not raise the flag a second time, or the
        # count of "things a person still has to look at" grows every time the
        # importer is run.
        for flag in flags:
            record = dict(flag, source_ref=source_ref,
                          recording_id=recording_id,
                          start_idx=start_idx, end_idx=end_idx)
            report.flags.append(record)
            _record_flag(conn, event, record, dry_run)
        return _create_entry(
            conn, event, report, digest=digest, recording_id=recording_id,
            channel=channel, start_idx=start_idx, end_idx=end_idx,
            store_ref=store_ref, source_ref=source_ref, dry_run=dry_run,
            pending_hashes=pending_hashes, pending_spans=pending_spans,
            created_at=created_at,
        )

    # `exact`: the same shape. Never a second entry.
    #
    # Its tags still go on, because the second occurrence's source row may
    # label the shape differently from the first — `trough` here, `Stegasauras`
    # there — and that disagreement is a finding, not noise: PRD Part 2 reports
    # families "which mix morphologies that the per-span labels call distinct".
    # Dropping the label because the shape arrived second would delete the
    # evidence of the disagreement, and `add_motif_entry_tag` is idempotent on
    # (entry, term), so a label that agrees costs nothing.
    _apply_tags(conn, entry_id, event, report, dry_run=dry_run)
    return _attach_member(
        conn, entry_id, report, digest=digest, recording_id=recording_id,
        channel=channel, start_idx=start_idx, end_idx=end_idx,
        dry_run=dry_run, created_at=created_at,
    )


def _create_entry(conn, event, report, *, digest, recording_id, channel,
                  start_idx, end_idx, store_ref, source_ref, dry_run,
                  pending_hashes, pending_spans, created_at):
    """A new shape: one entry, its first member, revision 1, and its tags."""
    if dry_run:
        pending_hashes[digest] = f"pending:{digest}"
        pending_spans.append({"recording_id": recording_id, "channel": channel,
                              "start_idx": start_idx, "end_idx": end_idx,
                              "content_hash": digest})
        _apply_tags(conn, None, event, report, dry_run=True)
        return CREATED, "would create a new entry"

    # `motif_entry` still carries `UNIQUE (recording_id, start_idx, end_idx)`
    # on the exemplar span (§3.1), and `insert_motif_entry` is idempotent on
    # it. A span already held by a DIFFERENT shape is therefore a real
    # conflict, not a duplicate: two detectors disagreeing about what is at one
    # place. It is counted and left alone rather than overwritten.
    entry_id = R.insert_motif_entry(
        conn, recording_id, start_idx, end_idx,
        label=str(event.get("span_key") or "") or None, commit=False)
    existing = conn.execute(
        "SELECT content_hash FROM motif_entry WHERE id = ?", (entry_id,)
    ).fetchone()
    if existing["content_hash"] and existing["content_hash"] != digest:
        report.skipped["span_holds_another_shape"] += 1
        report.warnings.append(
            f"{source_ref}: recording {recording_id} [{start_idx}, {end_idx}) "
            f"is already entry {entry_id} with a different content hash. Two "
            "shapes cannot share one exemplar span; the event was skipped."
        )
        return SKIPPED, "span already holds another shape"

    conn.execute(
        """UPDATE motif_entry
              SET content_hash = ?, channel = ?, fs = ?, scale = ?,
                  source_kind = ?, source_store = ?, source_ref = ?,
                  created_at = COALESCE(created_at, ?)
            WHERE id = ?""",
        (digest, channel, float(event.get("fs") or 0.0) or None, SCALE,
         SOURCE_KIND, store_ref, source_ref, created_at, entry_id),
    )
    pending_hashes[digest] = entry_id
    _apply_tags(conn, entry_id, event, report, dry_run=False)
    _attach_member(conn, entry_id, report, digest=digest,
                   recording_id=recording_id, channel=channel,
                   start_idx=start_idx, end_idx=end_idx, dry_run=False,
                   created_at=created_at)
    return CREATED, f"entry {entry_id}"


def _attach_member(conn, entry_id, report, *, digest, recording_id, channel,
                   start_idx, end_idx, dry_run, created_at):
    """The occurrence half of §2.1, and the whole of idempotence.

    Same hash, new occurrence -> a new member with revision 1. Same hash, same
    occurrence -> nothing at all, which is what makes a second run write
    nothing. The one middle case is a member that predates the revision table
    and carries no revision 1: it gets one, because rev 1 is what the matcher
    compares against and a member without it is invisible to a re-run.
    """
    if dry_run or not isinstance(entry_id, int):
        existing = conn.execute(
            """SELECT id FROM motif_member
                WHERE entry_id = ? AND recording_id = ?
                  AND start_idx = ? AND end_idx = ?""",
            (entry_id if isinstance(entry_id, int) else -1,
             recording_id, start_idx, end_idx),
        ).fetchone()
        if existing is not None:
            return ALREADY_PRESENT, f"member {existing['id']}"
        return MEMBER_ADDED, "would add a member"

    before = conn.execute(
        """SELECT id FROM motif_member
            WHERE entry_id = ? AND recording_id = ? AND start_idx = ? AND end_idx = ?""",
        (entry_id, recording_id, start_idx, end_idx),
    ).fetchone()
    member_id = R.get_or_create_motif_member(
        conn, entry_id, recording_id, start_idx, end_idx, commit=False)
    conn.execute(
        "UPDATE motif_member SET content_hash = ?, channel = ? WHERE id = ?",
        (digest, channel, member_id),
    )

    has_revision = conn.execute(
        "SELECT id FROM motif_member_revision WHERE member_id = ? AND revision = 1",
        (member_id,),
    ).fetchone()
    if has_revision is None:
        revisions.add_revision(
            conn, member_id, origin=revisions.MACHINE, start_idx=start_idx,
            end_idx=end_idx, content_hash=digest, created_at=created_at,
            commit=False,
        )
        # A member that already existed but had no revision 1 was described
        # before the revision list did; describing it now is a revision, not a
        # new occurrence.
        if before is not None:
            return REVISION_ADDED, f"member {member_id} gained revision 1"
    elif before is not None:
        return ALREADY_PRESENT, f"member {member_id}"

    return MEMBER_ADDED, f"member {member_id}"
