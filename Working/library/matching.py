"""
library.py
===========
The matching half of the shape-first motif library (ticket 36): matching a
candidate span to an exemplar entry writes a `motif_member` (the candidate
span, in whatever recording/channel it came from) and a `motif_edge` (the
distance-carrying relationship between the exemplar's own member and the
candidate's member). Every field the edge needs to reproduce the match is
recorded on the row — distance function name, threshold, distance value,
recipe hash — so a motif family is an object, not a screenshot.

`match_span_to_entry` is the seam the search UI (and tickets 41/46) call;
`search_entry_across_durations` is the search-at-other-scales action on top of
it — sliding the exemplar's shape across a range of durations. The low-level
member/edge rows live in `Working.database.runs`.

**`search_entry_across_durations` cannot be pointed at a real channel**
(measured by fixup-v: see its docstring). The affordable route to the same
question is Discovery's seed search with a scale bank
(`detection.seed_matches`' `scales`), whose human-accepted matches
`resolve_run_matches` writes onto the Library — **an edge per distance
function** on each accepted pair, so the three numbers sit side by side on the
same pair — and `scale_readout` reads back per scale factor (Q3).

Nothing here imports a UI library — callable from a bare script exactly like
the rest of `Working/`.
"""

import datetime as _dt
from functools import partial
import json
import os

import numpy as np

from Working.database import queries as q
from Working.database import runs as R
from Working.recipes import recipe_hash
from Working.distances import (
    DISTANCE_NATIVE_LENGTH, DISTANCE_REGISTRY, DISTANCE_SCALE_INVARIANT, DISTANCE_SYMBOLIC,
)


def _load_span(recording, start_idx, end_idx):
    """The raw sample values of one span, read off disk from the recording's
    npy path. A small slice copied out of the mmap so the file handle doesn't
    stay open."""
    x_full = np.load(recording["npy_path"], mmap_mode="r")
    return np.array(x_full[start_idx:end_idx])


def match_span_to_entry(conn, entry_id, recording_id, start_idx, end_idx,
                        threshold, recipe_hash,
                        distance_function=DISTANCE_SCALE_INVARIANT,
                        candidate_member_id=None, gate_on_threshold=True,
                        **distance_params):
    """Match a candidate span to an exemplar entry and persist the match.

    Loads the exemplar's waveform and the candidate's waveform from disk,
    computes the named distance, and if it is within `threshold` writes:

      - a `motif_member` for the candidate span (and, on first match, for the
        exemplar's own span — an edge connects two members), and
      - a `motif_edge` carrying the distance function name, threshold,
        distance value and recipe hash.

    A member may reference any recording and any channel, including one the
    exemplar did not come from.

    Idempotent: re-running the same match with the same recipe_hash returns
    the existing edge rather than writing a duplicate.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open, initialised database connection.
    entry_id : int
        The `motif_entry` the candidate is being matched against.
    recording_id : int
        The recording the candidate span lives in.
    start_idx, end_idx : int
        The candidate span's sample range (channel-local).
    distance_function : str
        One of `Working.distances.DISTANCE_REGISTRY`. Defaults to the primary
        scale-invariant distance.
    threshold : float
        Maximum distance accepted as a match. Required — the value is stored
        on the edge.
    recipe_hash : str
        The recipe that produced this match. Required — stored on the edge so
        the match is reproducible.
    candidate_member_id : int, optional
        The candidate is an EXISTING member (fixup-v, spec §4.2: a match that
        re-finds an occurrence resolves onto it rather than making a second
        member). Its span is the member's revision 1 — what the matcher
        compares against — and `recording_id`/`start_idx`/`end_idx` are not
        read. No member is created for the candidate.
    gate_on_threshold : bool
        True (the default, and every caller before fixup-v): a distance past
        `threshold` writes nothing and returns None. False: the edge is written
        whatever its distance, because something else decided membership — a
        person's accepting verdict (Q39) — and the distance is the measurement
        being recorded, not the gate. `threshold` is still stored, so "within"
        stays a comparison any reader can make.
    **distance_params
        Forwarded to the named distance function (e.g. `word_length` for the
        symbolic distance). These are recipe parameters and must be captured
        in `recipe_hash` by the caller.

    Returns
    -------
    dict or None
        None when the distance exceeds `threshold` (nothing is persisted).
        Otherwise a dict with the persisted rows' ids and the recorded fields:

        {
            "entry_id": int,
            "exemplar_member_id": int,
            "candidate_member_id": int,
            "edge_id": int,
            "distance_value": float,
            "distance_function": str,
            "threshold": float,
            "recipe_hash": str,
        }
    """
    entry = R.get_motif_entry(conn, entry_id)
    if entry is None:
        raise ValueError(f"No motif_entry with id={entry_id}")

    if threshold is None:
        raise ValueError("threshold is required to persist an edge")
    if recipe_hash is None:
        raise ValueError("recipe_hash is required to persist an edge")

    if distance_function not in DISTANCE_REGISTRY:
        raise ValueError(
            f"Unknown distance_function {distance_function!r}; "
            f"must be one of {sorted(DISTANCE_REGISTRY)}"
        )

    exemplar_rec = q.get_recording_by_id(conn, entry["recording_id"])
    if candidate_member_id is not None:
        from Working.library.revisions import matching_revision

        member = R.get_motif_member(conn, candidate_member_id)
        if member is None:
            raise ValueError(f"No motif_member with id={candidate_member_id}")
        rev1 = matching_revision(conn, candidate_member_id)
        recording_id = member["recording_id"]
        start_idx, end_idx = ((rev1["start_idx"], rev1["end_idx"]) if rev1 is not None
                              else (member["start_idx"], member["end_idx"]))
    candidate_rec = q.get_recording_by_id(conn, recording_id)
    if candidate_rec is None:
        raise ValueError(f"No recording with id={recording_id}")
    if start_idx < 0 or end_idx > candidate_rec["n_samples"] or end_idx <= start_idx:
        raise ValueError(
            f"Candidate span [{start_idx}, {end_idx}) is outside recording "
            f"{recording_id} (n_samples={candidate_rec['n_samples']})."
        )

    x_exemplar = _load_span(exemplar_rec, entry["start_idx"], entry["end_idx"])
    x_candidate = _load_span(candidate_rec, start_idx, end_idx)

    func = DISTANCE_REGISTRY[distance_function]
    distance_value = func(x_exemplar, x_candidate, **distance_params)

    if gate_on_threshold and distance_value > threshold:
        return None

    exemplar_member_id = R.get_or_create_motif_member(
        conn, entry_id, entry["recording_id"], entry["start_idx"], entry["end_idx"],
    )
    if candidate_member_id is None:
        candidate_member_id = R.get_or_create_motif_member(
            conn, entry_id, recording_id, start_idx, end_idx,
        )

    edge_id = R.insert_motif_edge(
        conn, exemplar_member_id, candidate_member_id,
        distance_function=distance_function,
        threshold=threshold,
        distance_value=distance_value,
        recipe_hash=recipe_hash,
    )

    return {
        "entry_id": entry_id,
        "exemplar_member_id": exemplar_member_id,
        "candidate_member_id": candidate_member_id,
        "edge_id": edge_id,
        "distance_value": distance_value,
        "distance_function": distance_function,
        "threshold": threshold,
        "recipe_hash": recipe_hash,
    }


def search_entry_across_durations(conn, entry_id, recording_id, durations,
                                  threshold, recipe_hash,
                                  distance_function=DISTANCE_SCALE_INVARIANT,
                                  **distance_params):
    """Search for members of an exemplar across a range of durations.

    For every duration `d` in `durations` and every start index such that a
    window of length `d` fits in `recording_id`, compute the named distance
    between the window and the exemplar. Whenever it is within `threshold`,
    persist the match as a `motif_member` + `motif_edge` (via
    `match_span_to_entry`) and record the matched span in the returned
    summary.

    This is the "search at other scales" action (PIPELINE_PRD.md, Library):
    the same shape the exemplar defines at one duration is queried at
    durations it was never defined at, so scale-invariance is a testable
    query rather than an assumption. Passing `DISTANCE_NATIVE_LENGTH` as the
    distance runs the unnormalised control — a shape identical under
    resampling but longer/shorter is a large distance under it.

    The exemplar's own span is skipped when it falls inside the search range,
    so re-searching the recording the exemplar came from does not write a
    self-edge.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open, initialised database connection.
    entry_id : int
        The `motif_entry` being searched for.
    recording_id : int
        The recording the search runs over.
    durations : iterable of int
        The candidate durations (sample counts) to search at.
    threshold, recipe_hash, distance_function, **distance_params
        Forwarded to `match_span_to_entry`.

    Returns
    -------
    dict
        {
            "entry_id": int,
            "recording_id": int,
            "distance_function": str,
            "threshold": float,
            "recipe_hash": str,
            "durations": list[int],
            "by_duration": {int: [match_result, ...]},
            "matches": [match_result, ...],
            "matched_spans": [(start_idx, end_idx), ...],
            "recall": int,
        }
        Each match_result is what `match_span_to_entry` returns, augmented
        with `"span"` and `"duration"`.
    """
    entry = R.get_motif_entry(conn, entry_id)
    if entry is None:
        raise ValueError(f"No motif_entry with id={entry_id}")
    rec = q.get_recording_by_id(conn, recording_id)
    if rec is None:
        raise ValueError(f"No recording with id={recording_id}")

    durations = sorted({int(d) for d in durations})
    if not durations:
        raise ValueError("durations must be a non-empty iterable")

    exemplar_span = (entry["recording_id"], entry["start_idx"], entry["end_idx"])
    n_samples = rec["n_samples"]

    by_duration = {}
    matches = []
    matched_spans = []

    for d in durations:
        if d < 1 or d > n_samples:
            continue
        found = []
        for start in range(0, n_samples - d + 1):
            if (recording_id, start, start + d) == exemplar_span:
                continue
            end = start + d
            result = match_span_to_entry(
                conn, entry_id, recording_id, start, end,
                threshold=threshold, recipe_hash=recipe_hash,
                distance_function=distance_function,
                **distance_params,
            )
            if result is not None:
                result = dict(result)
                result["span"] = (start, end)
                result["duration"] = d
                found.append(result)
        by_duration[d] = found
        matches.extend(found)
        matched_spans.extend(r["span"] for r in found)

    return {
        "entry_id": entry_id,
        "recording_id": recording_id,
        "distance_function": distance_function,
        "threshold": threshold,
        "recipe_hash": recipe_hash,
        "durations": durations,
        "by_duration": by_duration,
        "matches": matches,
        "matched_spans": matched_spans,
        "recall": len(matches),
    }
def _set_motif_edge_classification(conn, edge_id, lag, waveform_correlation,
                                   classification_bin, classification_json=None,
                                   commit=True):
    """Write the cross-channel classification onto an existing motif edge.

    `R.insert_motif_edge` is deliberately idempotent and therefore cannot
    update a duplicate key, so the classification action needs this single
    UPDATE path for edges the search/matching seam has already created. The
    edge's distance, threshold and recipe are left as they were.
    """
    conn.execute(
        """UPDATE motif_edge
           SET lag = ?, waveform_correlation = ?, classification_bin = ?,
               classification_json = ?
           WHERE id = ?""",
        (lag, waveform_correlation, classification_bin, classification_json, edge_id),
    )
    if commit:
        conn.commit()


# ── fixup-W: classification on SIMULTANEOUS windows (Q40a/b/c, Q-W5) ─────────
#
# Before 2026-10-04 `classify_cross_channel_edges` cut each member's OWN span,
# wherever in the recording it sat, and cross-correlated the two snippets. Its
# "lag" was only how far one cut-out had to slide to align with the other:
# measured (fixup-W Part 1), it read a pulse injected 5 samples later on a
# sibling as lag 0 / artifact, and the same pulse an HOUR later as lag 0 /
# artifact too. The researcher's ruling (Q40a): lag is measured on the same
# absolute window on both channels, always.

#: The distance function an edge carries when the classifier had to write one
#: (two members co-occur on sibling channels and no edge joined them): the
#: correlation distance 1 - |r|, under the threshold 1 - (the r floor), so
#: "within" reads as "|r| cleared the floor".
CROSS_CHANNEL_DISTANCE = "cross_correlation"

#: What a pair is measured on, in words — carried on every classification.
SIMULTANEOUS_METHOD = ("the same absolute window on both channels (Q40a): the union of the two members' "
                       "spans, cut from each channel, cross-correlated; lag is the second member's channel "
                       "relative to the first's")

_CHUNK = 500


def _members_with_recordings(conn, member_ids):
    ids = sorted({int(m) for m in member_ids or []})
    out = []
    for i in range(0, len(ids), _CHUNK):
        part = ids[i:i + _CHUNK]
        marks = ",".join("?" * len(part))
        out.extend(dict(r) for r in conn.execute(
            f"""SELECT mm.id AS id, mm.entry_id AS entry_id, mm.recording_id AS recording_id,
                       mm.start_idx AS start_idx, mm.end_idx AS end_idx,
                       r.source_file AS source_file, r.channel AS channel, r.fs AS fs,
                       r.n_samples AS n_samples, r.npy_path AS npy_path
                  FROM motif_member mm JOIN recordings r ON r.id = mm.recording_id
                 WHERE mm.id IN ({marks})""", tuple(part)))
    return out


def _gap_s(a, b):
    """Seconds between two members' spans; negative when they overlap."""
    fs = float(a["fs"] or 1.0)
    return (max(a["start_idx"], b["start_idx"]) - min(a["end_idx"], b["end_idx"])) / fs


def _pair_edges(conn, a_id, b_id):
    return conn.execute(
        "SELECT * FROM motif_edge WHERE (member_a_id = ? AND member_b_id = ?) OR (member_a_id = ? AND member_b_id = ?) "
        "ORDER BY id", (a_id, b_id, b_id, a_id)).fetchall()


def _write_pair(conn, a_id, b_id, lag, r, b, info, rule):
    """The pair's classification onto every edge that joins the two members
    (a seed match carries one per distance function), with the lag's sign
    turned to each row's own a->b direction; one `cross_correlation` edge when
    none joins them. Returns the edge ids written."""
    info_json = json.dumps(info, sort_keys=True)
    distance = (1.0 - abs(r)) if r is not None else 1.0
    threshold = round(1.0 - rule.min_abs_r, 12)
    rows = _pair_edges(conn, a_id, b_id)
    if not rows:
        recipe = {"classifier": "cross_channel", "method": SIMULTANEOUS_METHOD, "rule": rule.as_dict()}
        eid = R.insert_motif_edge(
            conn, a_id, b_id, CROSS_CHANNEL_DISTANCE, threshold, distance, recipe_hash(recipe),
            lag=lag, waveform_correlation=r, classification_bin=b, commit=False)
        conn.execute("UPDATE motif_edge SET classification_json = ?, recipe_json = ?, created_at = ? WHERE id = ?",
                     (info_json, json.dumps(recipe, sort_keys=True), _now(), eid))
        return [int(eid)]
    out = []
    for row in rows:
        own = lag if (lag is None or int(row["member_a_id"]) == int(a_id)) else -lag
        _set_motif_edge_classification(conn, row["id"], own, r, b, info_json, commit=False)
        if row["distance_function"] == CROSS_CHANNEL_DISTANCE:
            # the classifier's own edge: its distance IS the correlation, its threshold the floor in force
            conn.execute("UPDATE motif_edge SET distance_value = ?, threshold = ? WHERE id = ?",
                         (distance, threshold, row["id"]))
        out.append(int(row["id"]))
    return out


def _write_pair_into(pair, conn, a_id, b_id, lag, r, b, info, rule):
    """`_write_pair`, with the edge ids it wrote kept on the classifier's `pair` row."""
    pair["edge_ids"] = _write_pair(conn, a_id, b_id, lag, r, b, info, rule)


def _window(load, rec, w0, w1):
    n = int(rec["n_samples"] or w1)
    return np.asarray(load(rec)[max(0, int(w0)):min(n, int(w1))], dtype=float)


def _measurable(x, y):
    n = min(len(x), len(y))
    ok = (n >= 4 and np.isfinite(x[:n]).all() and np.isfinite(y[:n]).all()
          and x[:n].std() > 0 and y[:n].std() > 0)
    return ok, n


def _edges_among(conn, ids):
    ids = sorted(ids)
    if not ids:
        return []
    out = []
    for i in range(0, len(ids), _CHUNK):
        part = ids[i:i + _CHUNK]
        marks = ",".join("?" * len(part))
        out.extend(conn.execute(f"SELECT * FROM motif_edge WHERE member_a_id IN ({marks})", tuple(part)).fetchall())
    keep = set(ids)
    return [e for e in out if int(e["member_b_id"]) in keep]


# ── fixup-AD: the chance test, the noise floor and the minimum length ────────

def _human_artifact_spans(conn, recording_ids):
    """`{recording_id: [(start, end), ...]}` — the spans a HUMAN marked
    artifact (`annotations`, never a machine row): the chance test's random
    windows never cut one."""
    ids = sorted({int(r) for r in recording_ids})
    out = {rid: [] for rid in ids}
    for i in range(0, len(ids), _CHUNK):
        part = ids[i:i + _CHUNK]
        marks = ",".join("?" * len(part))
        for r in conn.execute(f"SELECT recording_id, start_idx, end_idx FROM annotations WHERE verdict = 'artifact' "
                              f"AND deleted_at IS NULL AND recording_id IN ({marks})", tuple(part)):
            out[int(r[0])].append((int(r[1]), int(r[2])))
    return out


def _ptp_mv(x, units):
    """Peak-to-peak of `x` in mV by the recording's declared unit; None when the
    unit is undeclared (never assumed — fixup-B)."""
    from Working.units import to_mv_factor

    f = to_mv_factor(units)
    if f is None or len(x) == 0:
        return None
    return float(np.ptp(np.asarray(x, dtype=float))) * f


def _floor_check(x, y, units_x, units_y, floor):
    """Both swings against the dataset's noise floor (Round 11 Q40d-3: the twin
    must itself be an event, not merely correlate)."""
    px, py = _ptp_mv(x, units_x), _ptp_mv(y, units_y)
    out = {"member_ptp_mv": px, "sibling_ptp_mv": py, "floor_mv": float(floor["floor_mv"]),
           "from": floor["from"], "ok": False, "reason": None}
    if px is None or py is None:
        out["reason"] = "a unit is undeclared (Settings › Datasets), so neither swing can be put in mV"
    elif px < out["floor_mv"] or py < out["floor_mv"]:
        out["reason"] = (f"{'the member' if px < out['floor_mv'] else 'the sibling'}'s swing is under the noise "
                         f"floor ({out['floor_mv']:g} mV)")
    else:
        out["ok"] = True
    return out


def _amplitude_ratio(floor):
    px, py = floor.get("member_ptp_mv"), floor.get("sibling_ptp_mv")
    return (py / px) if (px and py is not None) else None


def _too_short(m, rule):
    return int(m["end_idx"]) - int(m["start_idx"]) < int(rule.min_samples)


def _clear_pair(conn, a_id, b_id, info):
    """A pair the rule does not classify any more (a member too short to tell):
    the classifier's own edge goes; any other edge (a seed match's) keeps its
    distance and loses only the classification the classifier wrote on it."""
    for row in _pair_edges(conn, a_id, b_id):
        if row["distance_function"] == CROSS_CHANNEL_DISTANCE:
            conn.execute("DELETE FROM motif_edge WHERE id = ?", (row["id"],))
        elif row["classification_bin"] is not None or row["lag"] is not None:
            _set_motif_edge_classification(conn, row["id"], None, None, None,
                                           json.dumps(info, sort_keys=True), commit=False)


def _judge(xc, x, y, sibling, w0, w1, fs, rule, seed, forbidden, units_x, units_y, floor):
    """One pair, in full: the waveform's lag and r, its chance test on the
    sibling, both swings against the floor, and the bin all three make."""
    lag, r = xc.cross_correlation_peak(x, y)
    null = xc.chance_null(x, sibling, w0, w1, fs, rule=rule, seed=seed, forbidden=forbidden)
    chance = xc.chance_summary(r, null)
    fl = _floor_check(x, y, units_x, units_y, floor)
    b = xc.bin_for(lag / fs, r, rule, beats_chance=chance["beats"], above_floor=fl["ok"])
    return int(lag), float(r), b, chance, fl


def classify_family_across_channels(conn, member_ids, rule=None, progress=None, cancel=None,
                                    exclude_source_files=()):
    """Classify one family's members against their sibling channels, on
    simultaneous windows, and persist the result.

    For each member, every other channel of the same recording (same
    `source_file`) is examined over the same absolute samples:

    - where the sibling holds another member of the family within the
      propagation ceiling of this one, the PAIR is classified on the union of
      the two spans, cut from both channels, and the bin, lag and r are written
      onto the pair's edge(s) (`_write_pair`) — an edge is written if none
      joined them;
    - where it holds none, the member's own span is classified against the
      sibling and the result kept in `motif_member_cooccurrence` — counted on
      the family as a *co-occurrence without a member* when it bins artifact or
      propagation, **never written as an edge** (Q40c).

    fixup-AD: every pair also carries its **chance test** (the same sibling at
    `rule.null_k` random other times, seeded from the member ids;
    `cross_channel.chance_null`) and the **noise floor** on both swings
    (`view_filter.dataset_floors`, in mV by `recordings.units`); a pair that
    fails either is independent. A member under `rule.min_samples` is **too
    short to tell**: never classified, its stale rows cleared, its id in
    `tooShort`. The bin `artifact` now means *suspected* — a human confirms it
    (`Working.review.artifact_queue`).

    An existing edge between two members on sibling channels that are further
    apart than the ceiling is `independent_recurrence` with no lag and no r:
    they are not simultaneous, so there is no lag to measure (Q40a).

    `rule` defaults to Settings' (`Working.cross_channel.rule_from_settings`);
    `progress(done, total, message)` is called once per channel holding
    members; `cancel()` returning true stops between channels. Files in
    `exclude_source_files` (the held-out recording) are never read.
    """
    from Working import cross_channel as xc
    from Working.library.view_filter import dataset_floors

    rule = rule or xc.rule_from_settings(conn)
    excluded = set(exclude_source_files or ())
    members, skipped = [], []
    for m in _members_with_recordings(conn, member_ids):
        if m["source_file"] in excluded:
            skipped.append({"member_id": m["id"], "reason": f"{m['source_file']} is held out and is never read"})
        else:
            members.append(m)
    short = {int(m["id"]) for m in members if _too_short(m, rule)}

    by_rec = {}
    for m in members:
        by_rec.setdefault(int(m["recording_id"]), []).append(m)
    sibs = {sf: [dict(r) for r in q.list_recordings(conn, sf)] for sf in {m["source_file"] for m in members}}
    channels = sorted(by_rec, key=lambda rid: (by_rec[rid][0]["source_file"], int(by_rec[rid][0]["channel"])))
    total = len(channels)
    floors = dataset_floors(conn)
    units = {int(r[0]): r[1] for r in conn.execute("SELECT id, units FROM recordings")}
    forbidden = _human_artifact_spans(conn, [int(s["id"]) for ss in sibs.values() for s in ss])

    arrays = {}

    def load(rec):
        rid = int(rec["recording_id"])
        if rid not in arrays:
            arrays[rid] = np.load(rec["npy_path"], mmap_mode="r")
        return arrays[rid]

    def sib_rec(s):
        return {"recording_id": s["id"], "npy_path": s["npy_path"], "n_samples": s["n_samples"]}

    now = _now()
    too_short_info = {"too_short": True, "rule": rule.as_dict(), "at": now,
                      "method": rule.describe_too_short()}
    pairs, without, done_pairs = [], [], set()
    for i, rid in enumerate(channels):
        if cancel is not None and cancel():
            break
        ms = by_rec[rid]
        here = ms[0]
        others = [s for s in sibs[here["source_file"]] if int(s["id"]) != rid and s["channel"] != here["channel"]]
        if progress is not None:
            from Working.discovery.channels import channel_name
            name = channel_name(here["source_file"], int(here["channel"]), len(sibs[here["source_file"]]))
            progress(i, total, f"{here['source_file']} · {name} · {len(ms)} member"
                               f"{'s' if len(ms) != 1 else ''} against {len(others)} sibling channel"
                               f"{'s' if len(others) != 1 else ''}")
        floor = floors.get(here["source_file"]) or {"floor_mv": 0.1, "from": "default 0.1 mV"}
        # fixup-dblock: this channel's writes, applied together once every pair on it is judged. A write
        # opens a transaction that holds SQLite's one write lock until COMMIT; writing as we went held it
        # across every chance test (`_judge`), and a request that wrote meanwhile — Send suspected
        # artifacts to Review — waited past its busy timeout and failed with `database is locked`.
        writes = []
        for m in ms:
            fs = float(m["fs"] or 1.0)
            if int(m["id"]) in short:
                # too short to tell: never binned — whatever an earlier rule stored goes
                writes.append(partial(conn.execute, "DELETE FROM motif_member_cooccurrence WHERE member_id = ?",
                                      (m["id"],)))
            for s in others:
                if not s["npy_path"] or not os.path.isfile(s["npy_path"]):
                    skipped.append({"member_id": m["id"], "recording_id": s["id"],
                                    "reason": "the sibling's samples are not on disk"})
                    continue
                if float(s["fs"] or 1.0) != fs:
                    skipped.append({"member_id": m["id"], "recording_id": s["id"],
                                    "reason": f"fs differs ({fs:g} vs {float(s['fs'] or 1.0):g} Hz): no common window"})
                    continue
                partners = [p for p in by_rec.get(int(s["id"]), []) if _gap_s(m, p) <= rule.propagation_max_lag_s]
                if partners:
                    # a member there now: whatever was counted without one is superseded
                    writes.append(partial(conn.execute,
                                          "DELETE FROM motif_member_cooccurrence WHERE member_id = ? AND recording_id = ?",
                                          (m["id"], s["id"])))
                    for p in partners:
                        key = frozenset((int(m["id"]), int(p["id"])))
                        if key in done_pairs:
                            continue
                        done_pairs.add(key)
                        a, b = (m, p) if int(m["id"]) < int(p["id"]) else (p, m)
                        if int(a["id"]) in short or int(b["id"]) in short:
                            writes.append(partial(_clear_pair, conn, int(a["id"]), int(b["id"]), too_short_info))
                            continue
                        w0, w1 = min(a["start_idx"], b["start_idx"]), max(a["end_idx"], b["end_idx"])
                        x, y = _window(load, a, w0, w1), _window(load, b, w0, w1)
                        ok, n = _measurable(x, y)
                        if not ok:
                            skipped.append({"member_a_id": a["id"], "member_b_id": b["id"],
                                            "reason": "flat or non-finite samples in the window: lag and r undefined"})
                            continue
                        lag, r, cls, chance, fl = _judge(
                            xc, x[:n], y[:n], load(b), int(w0), int(w0) + n, fs, rule,
                            [int(a["id"]), int(b["recording_id"])], forbidden.get(int(b["recording_id"]), ()),
                            units.get(int(a["recording_id"])), units.get(int(b["recording_id"])), floor)
                        info = {"method": SIMULTANEOUS_METHOD, "window": [int(w0), int(w1)], "fs": fs,
                                "recording_ids": [int(a["recording_id"]), int(b["recording_id"])],
                                "lag_s": lag / fs, "rule": rule.as_dict(), "simultaneous": True, "at": now,
                                "chance": chance, "floor": fl, "amplitude_ratio": _amplitude_ratio(fl)}
                        pair = {"member_a_id": int(a["id"]), "member_b_id": int(b["id"]), "lag": lag,
                                "lag_s": lag / fs, "waveform_correlation": r,
                                "classification_bin": cls, "window": (int(w0), int(w1)),
                                "edge_ids": None, "simultaneous": True, "chance": chance, "floor": fl,
                                "amplitude_ratio": _amplitude_ratio(fl)}
                        # `edge_ids` is filled when the channel's writes are applied
                        writes.append(partial(_write_pair_into, pair, conn, int(a["id"]), int(b["id"]),
                                              lag, r, cls, info, rule))
                        pairs.append(pair)
                    continue
                if int(m["id"]) in short:
                    continue
                x = _window(load, m, m["start_idx"], m["end_idx"])
                y = _window(load, sib_rec(s), m["start_idx"], m["end_idx"])
                ok, n = _measurable(x, y)
                if not ok:
                    continue
                lag, r, cls, chance, fl = _judge(
                    xc, x[:n], y[:n], load(sib_rec(s)), int(m["start_idx"]), int(m["start_idx"]) + n, fs, rule,
                    [int(m["id"]), int(s["id"])], forbidden.get(int(s["id"]), ()),
                    units.get(int(m["recording_id"])), units.get(int(s["id"])), floor)
                info = {"method": "the member's own span, cut from both channels (Q40a); no member on the sibling",
                        "window": [int(m["start_idx"]), int(m["end_idx"])], "fs": fs, "rule": rule.as_dict(),
                        "lag_s": lag / fs, "at": now, "chance": chance, "floor": fl,
                        "amplitude_ratio": _amplitude_ratio(fl)}
                writes.append(partial(
                    conn.execute,
                    """INSERT INTO motif_member_cooccurrence
                           (member_id, recording_id, lag, waveform_correlation, classification_bin,
                            classification_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(member_id, recording_id) DO UPDATE SET
                           lag = excluded.lag, waveform_correlation = excluded.waveform_correlation,
                           classification_bin = excluded.classification_bin,
                           classification_json = excluded.classification_json, created_at = excluded.created_at""",
                    (m["id"], s["id"], lag, r, cls, json.dumps(info, sort_keys=True), now)))
                if cls in (xc.ARTIFACT, xc.PROPAGATION):
                    without.append({"member_id": int(m["id"]), "recording_id": int(s["id"]), "lag": lag,
                                    "lag_s": lag / fs, "waveform_correlation": r, "classification_bin": cls,
                                    "chance": chance, "floor": fl, "amplitude_ratio": _amplitude_ratio(fl)})
        # one short transaction per channel, in the order the writes were made: every channel or none of it
        with conn:
            for write in writes:
                write()

    # an existing edge between members on sibling channels too far apart to be simultaneous
    by_id = {int(m["id"]): m for m in members}
    for e in _edges_among(conn, set(by_id)):
        key = frozenset((int(e["member_a_id"]), int(e["member_b_id"])))
        if key in done_pairs:
            continue
        a, b = by_id[int(e["member_a_id"])], by_id[int(e["member_b_id"])]
        if a["source_file"] != b["source_file"] or a["channel"] == b["channel"]:
            continue
        if int(a["id"]) in short or int(b["id"]) in short:
            done_pairs.add(key)
            _clear_pair(conn, int(a["id"]), int(b["id"]), too_short_info)
            continue
        if _gap_s(a, b) <= rule.propagation_max_lag_s:
            continue          # simultaneous but unmeasurable: said in `skipped` above
        done_pairs.add(key)
        info = {"method": ("not simultaneous: the two members are further apart than the propagation ceiling, so "
                           "no lag is measured (Q40a)"), "gap_s": _gap_s(a, b), "rule": rule.as_dict(),
                "simultaneous": False, "at": now}
        eids = _write_pair(conn, int(a["id"]), int(b["id"]), None, None, xc.INDEPENDENT_RECURRENCE, info, rule)
        pairs.append({"member_a_id": int(a["id"]), "member_b_id": int(b["id"]), "lag": None, "lag_s": None,
                      "waveform_correlation": None, "classification_bin": xc.INDEPENDENT_RECURRENCE,
                      "window": None, "edge_ids": eids, "simultaneous": False, "gap_s": _gap_s(a, b)})
    conn.commit()
    if progress is not None:
        progress(total, total, f"done · {len(pairs)} pair{'s' if len(pairs) != 1 else ''} classified across "
                               f"{total} channel{'s' if total != 1 else ''}"
                               + (f" · {len(short)} too short to tell" if short else ""))

    counts = {b: sum(1 for p in pairs if p["classification_bin"] == b) for b in xc.BINS}
    wm = {}
    for w in without:
        wm[w["classification_bin"]] = wm.get(w["classification_bin"], 0) + 1
    counts["withoutMember"] = wm
    counts["tooShort"] = len(short)
    return {"pairs": pairs, "withoutMember": without, "counts": counts, "channels": total,
            "members": len(members), "skipped": skipped, "tooShort": sorted(short),
            "rule": rule.as_dict(), "rules": rule.describe(), "tooShortRule": rule.describe_too_short()}


def classify_cross_channel_edges(conn, entry_id, rule=None):
    """Classify one motif entry's members across channels — the entry-scoped
    form of `classify_family_across_channels`, kept for
    ``python Working/cross_channel.py ENTRY_ID`` and the exporter's callers.

    Returns the classified pairs: `member_a_id`, `member_b_id`, `lag`
    (samples, b relative to a), `lag_s`, `waveform_correlation`,
    `classification_bin`, `edge_ids`.
    """
    ids = [int(r["id"]) for r in conn.execute("SELECT id FROM motif_member WHERE entry_id = ?", (int(entry_id),))]
    return classify_family_across_channels(conn, ids, rule=rule)["pairs"]


#: How the three recurrence counts are made, in the words the page prints.
RECURRENCE_RULES = {
    "all": "every member of the family, each counted once — nothing taken out",
    "excluding_artifacts": ("members a human marked artifact in Review are not counted, and neither is the other "
                            "member of a member–member artifact pair a human confirmed (Q40d-2). A machine flag "
                            "alone takes nothing out: flagged members stay counted, drawn red, until a human "
                            "decides"),
    "propagation_once": ("human-confirmed artifacts taken out as above, then members joined by propagation that "
                         "beat its chance test count once — one travelling event — on the member with the "
                         "earliest onset"),
}
RECURRENCE_MODES = tuple(RECURRENCE_RULES)

#: The flagged / confirmed / rejected / unsure / unjudged line, in words.
FLAG_LINE_RULE = ("machine-flagged: a member in a suspected-artifact pair, or with a suspected-artifact match on a "
                  "sibling channel holding no member (Q40d-1 b), under the chance test. confirmed: a human marked it "
                  "artifact in Review; rejected: a human gave it another verdict (interesting, not_interesting, "
                  "seed); unsure: a human answered unsure; unjudged: no human verdict yet")


def _beat_chance(raw_json):
    """A stored bin counts only if it was computed under the chance test and
    beat it — a bin W wrote before the test existed carries no `chance`."""
    if not raw_json:
        return False
    try:
        info = json.loads(raw_json)
    except (TypeError, ValueError):
        return False
    return bool((info.get("chance") or {}).get("beats"))


def family_recurrence(conn, member_ids):
    """Recurrence of one family with the cross-channel bins taken out — the ONE
    definition (PIPELINE_PRD.md: artifacts excluded from counts, propagation
    one event). Read from the bins on the members' edges and co-occurrence
    rows, so it is whatever the last classification wrote; `classified` says
    whether one ran.

    fixup-AD: the machine only FLAGS. *Excluding artifacts* takes out only
    members a human marked artifact (`Working.review.artifact_queue`), plus the
    other member of a member–member artifact pair a human confirmed (Q40d-2),
    unless a human said otherwise of that one. Propagation counted once merges
    only pairs that beat their chance test. A member under the rule's minimum
    length is *too short to tell*: never flagged, counted in `tooShort`.

    Returns `all`, `excluding_artifacts`, `propagation_once` (counts of
    members), `flagged`, `confirmed`, `rejected`, `unsure`, `unjudged`,
    `tooShort`, `members` (per member: `flagged`, `artifact` (taken out),
    `verdict`, `tooShort`, `counted` per mode), the pair counts per bin
    (`pairs`), the Q40c `withoutMember` counts and `rules`.
    """
    from Working import cross_channel as xc
    from Working.review.artifact_queue import CONFIRMING_VERDICTS, member_verdicts

    rule = xc.rule_from_settings(conn)
    members = {int(m["id"]): m for m in _members_with_recordings(conn, member_ids)}
    ids = set(members)
    short = {mid for mid, m in members.items() if _too_short(m, rule)}
    pairs, pair_beat = {}, {}
    for e in _edges_among(conn, ids):
        if e["classification_bin"]:
            k = frozenset((int(e["member_a_id"]), int(e["member_b_id"])))
            pairs[k] = e["classification_bin"]
            pair_beat[k] = pair_beat.get(k, False) or _beat_chance(e["classification_json"])
    co_rows = []
    sorted_ids = sorted(ids)
    for i in range(0, len(sorted_ids), _CHUNK):
        part = sorted_ids[i:i + _CHUNK]
        marks = ",".join("?" * len(part))
        co_rows.extend(conn.execute(
            f"SELECT member_id, classification_bin, classification_json FROM motif_member_cooccurrence "
            f"WHERE member_id IN ({marks})", tuple(part)).fetchall())

    # the machine's flags: only bins that beat chance, never on a member too short to tell
    art_pairs = [k for k, b in pairs.items() if b == xc.ARTIFACT and pair_beat.get(k) and not (k & short)]
    flagged = {mid for k in art_pairs for mid in k}
    flagged |= {int(r["member_id"]) for r in co_rows
                if r["classification_bin"] == xc.ARTIFACT and _beat_chance(r["classification_json"])
                and int(r["member_id"]) not in short}

    # the human's verdicts, and what they take out
    verdicts = member_verdicts(conn, sorted(ids))
    confirmed = {mid for mid in flagged if verdicts.get(mid) in CONFIRMING_VERDICTS}
    out_set = set(confirmed)
    for k in art_pairs:
        if k & confirmed:
            for mid in k:
                if verdicts.get(mid) is None or verdicts.get(mid) in CONFIRMING_VERDICTS:
                    out_set.add(mid)
    # a human verdict of artifact on a member no flag points at is still a human verdict: it goes
    out_set |= {mid for mid, v in verdicts.items() if v in CONFIRMING_VERDICTS}
    kept = [mid for mid in sorted(ids) if mid not in out_set]
    parent = {mid: mid for mid in kept}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for k, b in pairs.items():
        if b != xc.PROPAGATION or not pair_beat.get(k):
            continue
        a, c = tuple(k)
        if a in parent and c in parent:
            ra, rc = find(a), find(c)
            if ra != rc:
                parent[rc] = ra
    onset = {mid: (members[mid]["start_idx"] / float(members[mid]["fs"] or 1.0), mid) for mid in ids}
    first = {}
    for mid in kept:
        root = find(mid)
        if root not in first or onset[mid] < onset[first[root]]:
            first[root] = mid
    once = set(first.values())

    per = {mid: {"flagged": mid in flagged, "artifact": mid in out_set, "verdict": verdicts.get(mid),
                 "tooShort": mid in short,
                 "counted": {"all": True, "excluding_artifacts": mid not in out_set,
                             "propagation_once": mid in once}} for mid in ids}
    rejected = {mid for mid in flagged if verdicts.get(mid) not in (None, "unsure") and mid not in confirmed}
    unsure = {mid for mid in flagged if verdicts.get(mid) == "unsure"}
    by_bin = {b: sum(1 for v in pairs.values() if v == b) for b in xc.BINS}
    wm = {}
    for r in co_rows:
        if r["classification_bin"] in (xc.ARTIFACT, xc.PROPAGATION):
            wm[r["classification_bin"]] = wm.get(r["classification_bin"], 0) + 1
    return {"classified": bool(pairs) or bool(co_rows),
            "all": len(ids), "excluding_artifacts": len(kept), "propagation_once": len(once),
            "flagged": len(flagged), "confirmed": len(confirmed), "rejected": len(rejected),
            "unsure": len(unsure), "unjudged": len(flagged) - len(confirmed) - len(rejected) - len(unsure),
            "tooShort": len(short), "tooShortRule": rule.describe_too_short(), "flagRule": FLAG_LINE_RULE,
            "members": per, "pairs": by_bin, "withoutMember": wm, "rules": dict(RECURRENCE_RULES)}


def recurrence_count(conn, entry_id, mode="excluding_artifacts"):
    """Recurrence count for one motif entry's members under `mode` (one of
    `RECURRENCE_MODES`) — `family_recurrence`, the one definition.

    Before fixup-W this counted non-artifact EDGES; it now counts members, with
    the artifacts taken out (PIPELINE_PRD.md: a shared-ground error is excluded
    from counts) — since fixup-AD, only those a human confirmed.
    """
    if mode not in RECURRENCE_RULES:
        raise ValueError(f"mode must be one of {RECURRENCE_MODES}, got {mode!r}")
    ids = [int(r["id"]) for r in conn.execute("SELECT id FROM motif_member WHERE entry_id = ?", (int(entry_id),))]
    return family_recurrence(conn, ids)[mode]



# ── fixup-v: a seed-search match becomes a member, with its distances ──────

#: Q39 (2026-10-03): a seed-search match becomes a Library member only with one
#: of these verdicts. *Include unjudged* is a flag, off by default; every other
#: verdict is a rejection, and a rejected match keeps its distance on its own
#: `detections` row (`score`) and nothing else.
ACCEPTING_VERDICTS = ("interesting", "seed")

#: The three distances of PIPELINE_PRD.md "Distances", in the order the Family
#: page prints them: the primary, the symbolic arm, the native-length control.
EDGE_DISTANCES = (DISTANCE_SCALE_INVARIANT, DISTANCE_SYMBOLIC, DISTANCE_NATIVE_LENGTH)

#: The symbolic distance's fixed word length and alphabet. A span shorter than
#: the word gets a word as long as the span; whichever ran is on the edge.
SYMBOLIC_WORD_LENGTH = 16
SYMBOLIC_ALPHABET = 10

#: What every resolved edge's `threshold` is, in words, on its recipe.
THRESHOLD_IS = ("the seed run's cut: the z-normalised Euclidean distance (on the native length's footing) "
                "under which the search proposed this pair. Membership was decided by a person's accepting "
                "verdict (Q39), not by this edge's distance, so a value past the threshold is a measurement, "
                "not a contradiction.")


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _distance_params(function, n_a, n_b):
    if function == DISTANCE_SYMBOLIC:
        return {"word_length": int(max(1, min(SYMBOLIC_WORD_LENGTH, n_a, n_b))),
                "alphabet_size": SYMBOLIC_ALPHABET}
    return {}


def _seed_step(recipe):
    steps = (recipe or {}).get("steps") or []
    return next((st for st in steps if st.get("algorithm") == "seed_matches"), None)


def _run_bank(conn, run_id):
    """`(scales, m, config_hash)` of one seed run, read off its own recipe: the
    bank it searched (`(1.0,)` for a native search) and the exemplar's length."""
    from Adapters.detection_seed_matches import parse_scales

    row = conn.execute("SELECT c.config_json, c.config_hash FROM runs r JOIN configs c ON c.id = r.config_id "
                       "WHERE r.id = ?", (int(run_id),)).fetchone()
    if row is None:
        raise ValueError(f"No run with id={run_id}")
    step = _seed_step(json.loads(row["config_json"])) or {}
    params = step.get("params") or {}
    scales = parse_scales(params.get("scales") or "1")
    b = ((step.get("side_inputs") or {}).get("exemplar") or {})
    m = (int(b["end_idx"]) - int(b["start_idx"])) if {"start_idx", "end_idx"} <= set(b) else None
    return scales, m, row["config_hash"]


def scale_of(length, m, scales):
    """The bank factor a match of `length` samples was found at: the factor
    whose copy is exactly that long, else the nearest by ratio. A match is as
    long as the copy that found it (`detection.seed_matches`), so this is a
    reading of the row, not a guess; `(1.0,)` for a native search."""
    if not m or not scales or len(scales) == 1:
        return float(scales[0]) if scales else 1.0
    for s in scales:
        if int(round(m * s)) == int(length):
            return float(s)
    ratio = float(length) / float(m)
    return float(min(scales, key=lambda s: abs(s - ratio)))


def match_verdicts(conn, run_ids, entry=None):
    """Every match of these seed runs, with the human verdict on it.

    One row per detection of a REAL run (never a paired null's), carrying the
    verdict a person gave it: an `adjudications` row on the detection first,
    else a human `annotations` row the match re-finds under the §4.6 rule (§4.7:
    a rediscovery points at the prior verdict). `is_exemplar` marks the seed
    finding itself — the exemplar's own span — which is the shape searched
    for, not a match of it."""
    from Working.discovery.matching import match_span_sets, rule_from_settings, spans_match

    ids = [int(r) for r in run_ids or []]
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""SELECT d.id AS detection_id, d.run_id, d.start_idx, d.end_idx, d.score,
                   r.recording_id, rec.channel, a.verdict AS adjudication
              FROM detections d
              JOIN runs r ON r.id = d.run_id
              JOIN recordings rec ON rec.id = r.recording_id
              LEFT JOIN adjudications a ON a.detection_id = d.id
             WHERE d.run_id IN ({marks}) AND {q.not_surrogate('r')}
             ORDER BY d.run_id, d.start_idx""", tuple(ids)).fetchall()
    banks = {rid: _run_bank(conn, rid) for rid in {int(r["run_id"]) for r in rows}}
    rule = rule_from_settings(conn)

    out = [{
        "detection_id": int(r["detection_id"]), "run_id": int(r["run_id"]),
        "recording_id": int(r["recording_id"]), "channel": r["channel"],
        "start_idx": int(r["start_idx"]), "end_idx": int(r["end_idx"]),
        "score": None if r["score"] is None else float(r["score"]),
        "verdict": r["adjudication"], "verdict_source": "adjudication" if r["adjudication"] else None,
        "scale": scale_of(int(r["end_idx"]) - int(r["start_idx"]), banks[int(r["run_id"])][1],
                          banks[int(r["run_id"])][0]),
        "is_exemplar": bool(entry is not None and int(r["recording_id"]) == int(entry["recording_id"])
                            and spans_match((int(r["start_idx"]), int(r["end_idx"])),
                                            (int(entry["start_idx"]), int(entry["end_idx"])), rule=rule)),
    } for r in rows]

    by_rec = {}
    for i, row in enumerate(out):
        if row["verdict"] is None:
            by_rec.setdefault(row["recording_id"], []).append(i)
    for rid, idx in by_rec.items():
        humans = conn.execute(
            "SELECT start_idx, end_idx, verdict FROM annotations WHERE recording_id = ? AND verdict IS NOT NULL "
            "AND deleted_at IS NULL", (int(rid),)).fetchall()
        if not humans:
            continue
        pairing = match_span_sets([(out[i]["start_idx"], out[i]["end_idx"]) for i in idx],
                                  [(h["start_idx"], h["end_idx"]) for h in humans], rule=rule)
        for p in pairing["pairs"]:
            row = out[idx[p["candidate"]]]
            row["verdict"] = humans[p["reference"]]["verdict"]
            row["verdict_source"] = "annotation"
    return out


def _classify(verdict):
    if verdict is None:
        return "unjudged"
    return "accepted" if str(verdict).lower() in ACCEPTING_VERDICTS else "rejected"


def _member_for(conn, entry_id, row):
    """The member a match resolves onto, and whether it was made just now.

    §4.2 / `04-to-03.md` §3: a match that re-finds an existing occurrence — any
    entry's member on the same channel under the §4.6 rule — resolves onto it.
    Otherwise a new member of this entry, carrying its content hash, its
    channel and revision 1, a machine revision pointing at the detection."""
    from Working.library.dedupe import find_near_duplicates
    from Working.library.identity import hash_span
    from Working.library.revisions import add_revision

    flags = find_near_duplicates(conn, recording_id=row["recording_id"], channel=row["channel"],
                                 start_idx=row["start_idx"], end_idx=row["end_idx"])
    if flags:
        return int(flags[0]["member_id"]), False
    digest = hash_span(conn, row["recording_id"], row["channel"], row["start_idx"], row["end_idx"])
    member_id = R.get_or_create_motif_member(conn, entry_id, row["recording_id"], row["start_idx"],
                                             row["end_idx"], commit=False)
    conn.execute("UPDATE motif_member SET content_hash = ?, channel = ? WHERE id = ?",
                 (digest, row["channel"], member_id))
    add_revision(conn, member_id, origin="machine", start_idx=row["start_idx"], end_idx=row["end_idx"],
                 detection_id=row["detection_id"], content_hash=digest, commit=False)
    return member_id, True


def edge_recipe(*, run_config_hash, run_id, detection_id, scale, distance_function, distance_params,
                threshold):
    """The recipe one resolved edge was produced under — stored in full on the
    row (`recipe_json`) and hashed into its `recipe_hash`. The verdict is NOT in
    it: a person changing their mind is not a different measurement."""
    return {
        "kind": "seed-search match",
        "run_config_hash": run_config_hash, "run_id": int(run_id), "detection_id": int(detection_id),
        "scale": float(scale), "distance_function": distance_function,
        "distance_params": dict(distance_params), "threshold": float(threshold),
        "threshold_is": THRESHOLD_IS,
        "gate": f"a person's verdict in {list(ACCEPTING_VERDICTS)} (Q39)",
    }


def resolve_run_matches(conn, entry_id, run_ids, *, cut=None, include_unjudged=False,
                        distances=EDGE_DISTANCES):
    """*Add N matches to E-xxxx*: a seed run's accepted matches become members
    of the entry it searched for, each with an edge per distance function.

    For every match of the real runs `run_ids` (paired nulls are never read):

      - **accepted** (`interesting` / `seed`, Q39) → the member it resolves onto
        (`_member_for`: an existing occurrence, else a new member), and one
        `motif_edge` from the entry's exemplar member to it **per distance
        function**, written whatever the distance (the verdict is the gate),
        with `threshold` = the run's cut, the scale factor it was found at, the
        detection, and the recipe;
      - **unjudged** → the same, only when `include_unjudged` (off);
      - **rejected** → nothing. Its distance stays on its detection row.

    The seed finding itself (the exemplar's own span) is not a match and makes
    no edge. Idempotent: a second call writes nothing.

    `cut` is the seed run's cut; None (a run kept every match) takes the
    largest distance the run kept, and the edges' recipe says so.
    """
    entry = R.get_motif_entry(conn, entry_id)
    if entry is None:
        raise ValueError(f"No motif_entry with id={entry_id}")
    exemplar_member = R.get_or_create_motif_member(
        conn, entry_id, entry["recording_id"], entry["start_idx"], entry["end_idx"])
    rows = match_verdicts(conn, run_ids, entry)
    threshold = float(cut) if cut is not None else max(
        (r["score"] for r in rows if r["score"] is not None), default=0.0)
    banks = {}
    counts = {"accepted": 0, "unjudged": 0, "rejected": 0, "exemplar": 0}
    members_new = members_resolved = edges_new = edges_kept = 0
    by_function = {fn: 0 for fn in distances}
    pairs = []
    for row in rows:
        if row["is_exemplar"]:
            counts["exemplar"] += 1
            continue
        kind = _classify(row["verdict"])
        counts[kind] += 1
        if kind == "rejected" or (kind == "unjudged" and not include_unjudged):
            continue
        member_id, made = _member_for(conn, entry_id, row)
        if member_id == exemplar_member:
            continue
        members_new += int(made)
        members_resolved += int(not made)
        if row["run_id"] not in banks:
            banks[row["run_id"]] = _run_bank(conn, row["run_id"])
        run_hash = banks[row["run_id"]][2]
        member = R.get_motif_member(conn, member_id)
        n_b = int(member["end_idx"]) - int(member["start_idx"])
        n_a = int(entry["end_idx"]) - int(entry["start_idx"])
        for fn in distances:
            params = _distance_params(fn, n_a, n_b)
            recipe = edge_recipe(run_config_hash=run_hash, run_id=row["run_id"],
                                 detection_id=row["detection_id"], scale=row["scale"],
                                 distance_function=fn, distance_params=params, threshold=threshold)
            if cut is None:
                recipe["threshold_is"] = "no cut was chosen: the largest distance the run kept. " + THRESHOLD_IS
            rh = recipe_hash(recipe)
            existing = R.get_motif_edge(conn, exemplar_member, member_id, fn, threshold, rh)
            if existing is not None:
                edges_kept += 1
                continue
            res = match_span_to_entry(conn, entry_id, None, None, None, threshold=threshold, recipe_hash=rh,
                                      distance_function=fn, candidate_member_id=member_id,
                                      gate_on_threshold=False, **params)
            conn.execute("UPDATE motif_edge SET scale_factor = ?, detection_id = ?, recipe_json = ?, "
                         "created_at = ? WHERE id = ?",
                         (row["scale"], row["detection_id"], json.dumps(recipe, sort_keys=True), _now(),
                          res["edge_id"]))
            edges_new += 1
            by_function[fn] += 1
        pairs.append({"detection_id": row["detection_id"], "member_id": member_id, "new": made,
                      "scale": row["scale"], "verdict": row["verdict"]})
    conn.commit()
    return dict(counts, members_new=members_new, members_resolved=members_resolved,
                edges_new=edges_new, edges_kept=edges_kept, edges_by_function=by_function,
                threshold=threshold, include_unjudged=bool(include_unjudged), pairs=pairs,
                exemplar_member_id=exemplar_member)


def edges_for_entry(conn, entry_id):
    """Every edge touching a member of one entry, with both members' spans —
    including an edge to an occurrence that belongs to another entry (a match
    resolved onto an existing member), which `R.list_motif_edges` (both ends in
    the entry) leaves out."""
    return conn.execute(
        """SELECT e.*,
                  ma.entry_id AS a_entry_id, ma.recording_id AS a_recording_id,
                  ma.start_idx AS a_start_idx, ma.end_idx AS a_end_idx,
                  mb.entry_id AS b_entry_id, mb.recording_id AS b_recording_id,
                  mb.start_idx AS b_start_idx, mb.end_idx AS b_end_idx
             FROM motif_edge e
             JOIN motif_member ma ON ma.id = e.member_a_id
             JOIN motif_member mb ON mb.id = e.member_b_id
            WHERE ma.entry_id = ? OR mb.entry_id = ?
            ORDER BY e.id""", (int(entry_id), int(entry_id))).fetchall()


def _spread(values, threshold):
    vals = sorted(float(v) for v in values)
    if not vals:
        return {"n": 0, "median": None, "min": None, "max": None, "within": 0, "threshold": threshold}
    return {"n": len(vals), "median": float(np.median(vals)), "min": vals[0], "max": vals[-1],
            "within": sum(1 for v in vals if threshold is not None and v <= threshold),
            "threshold": threshold}


def scale_readout(conn, entry_id, run_ids):
    """The Q3 read-out for one exemplar over its seed runs, filled from rows.

    Per scale factor of the bank: matches **found** (the runs' detections at
    that length, the seed finding itself left out), **judged**, **accepted**,
    the **members** those accepted matches are, and — from the `motif_edge`
    rows those members carry — the same pairs' distance under each distance
    function (n, median, range, how many sit within the edge's threshold). The
    null per length goes beside each row: the paired null runs' spans at that
    length, per draw. This is PIPELINE_PRD.md's query — search at durations the
    exemplar was never defined at and compare the scale-invariant distance with
    the control — and no test is run on it: it is counts and distances.
    """
    entry = R.get_motif_entry(conn, entry_id)
    if entry is None:
        raise ValueError(f"No motif_entry with id={entry_id}")
    ids = [int(r) for r in run_ids or []]
    rows = [r for r in match_verdicts(conn, ids, entry) if not r["is_exemplar"]]
    banks = {rid: _run_bank(conn, rid) for rid in ids}
    scales = sorted({float(s) for b in banks.values() for s in b[0]}) or [1.0]

    edges = [dict(e) for e in edges_for_entry(conn, entry_id)]
    edges_by_det = {}
    for e in edges:
        if e["detection_id"] is not None:
            edges_by_det.setdefault(int(e["detection_id"]), []).append(e)

    marks = ",".join("?" * len(ids)) or "NULL"
    nulls = conn.execute(f"SELECT id, surrogate_of_run_id FROM runs WHERE surrogate_of_run_id IN ({marks})",
                         tuple(ids)).fetchall()
    draws_by_run = {}
    for n in nulls:
        draws_by_run[int(n["surrogate_of_run_id"])] = draws_by_run.get(int(n["surrogate_of_run_id"]), 0) + 1
    draws = max(draws_by_run.values(), default=0)
    null_counts = {s: 0 for s in scales}
    for n in nulls:
        bank, m, _h = banks[int(n["surrogate_of_run_id"])]
        for d in conn.execute("SELECT start_idx, end_idx FROM detections WHERE run_id = ?", (int(n["id"]),)):
            s = scale_of(int(d["end_idx"]) - int(d["start_idx"]), m, bank)
            null_counts[s] = null_counts.get(s, 0) + 1

    out_rows = []
    for s in scales:
        at = [r for r in rows if r["scale"] == s]
        accepted = [r for r in at if _classify(r["verdict"]) == "accepted"]
        es = [e for r in accepted for e in edges_by_det.get(r["detection_id"], [])]
        row = {"scale": s, "found": len(at), "judged": sum(1 for r in at if r["verdict"] is not None),
               "accepted": len(accepted), "members": len({e["member_b_id"] for e in es}),
               "nullCount": null_counts.get(s, 0),
               "nullPerDraw": (null_counts.get(s, 0) / draws) if draws else None}
        for fn in EDGE_DISTANCES:
            fe = [e for e in es if e["distance_function"] == fn]
            row[fn] = _spread([e["distance_value"] for e in fe], (fe[0]["threshold"] if fe else None))
        out_rows.append(row)
    return {"entryId": int(entry_id), "runIds": ids, "scales": scales, "rows": out_rows,
            "nullDraws": draws, "distances": list(EDGE_DISTANCES),
            "note": ("counts and distances only: per length, how many matches the search found, how many a person "
                     "judged and accepted, and the accepted pairs' distance under each function; the null per draw "
                     "is beside each row and nothing here is tested against it")}
