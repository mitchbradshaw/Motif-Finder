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
import json

import numpy as np

from Working.database import queries as q
from Working.database import runs as R
from Working.cross_channel import ARTIFACT, classify_waveforms
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
                                   classification_bin):
    """Write the cross-channel classification onto an existing motif edge.

    `R.insert_motif_edge` is deliberately idempotent and therefore cannot
    update a duplicate key, so the classification action needs this single
    UPDATE path for edges the search/matching seam has already created.
    """
    conn.execute(
        """UPDATE motif_edge
           SET lag = ?, waveform_correlation = ?, classification_bin = ?
           WHERE id = ?""",
        (lag, waveform_correlation, classification_bin, edge_id),
    )
    conn.commit()


def classify_cross_channel_edges(conn, entry_id):
    """Classify and persist every cross-channel edge of one motif family.

    A pair is cross-channel when both member spans live in recordings with the
    same `source_file` but different `channel` — the same acquisition seen on
    two electrodes. For each such edge, the lag is the cross-correlation peak
    and the waveform identity is the correlation at that lag, computed by
    `Working.cross_channel.classify_waveforms`, then written back onto the
    edge.

    Returns
    -------
    list[dict]
        One dict per classified edge, in `list_motif_edges` order, with the
        persisted `edge_id`, `member_a_id`, `member_b_id`, `lag`,
        `waveform_correlation` and `classification_bin`.
    """
    results = []
    for edge in R.list_motif_edges(conn, entry_id):
        member_a = R.get_motif_member(conn, edge["member_a_id"])
        member_b = R.get_motif_member(conn, edge["member_b_id"])
        recording_a = q.get_recording_by_id(conn, member_a["recording_id"])
        recording_b = q.get_recording_by_id(conn, member_b["recording_id"])

        if (recording_a["source_file"] != recording_b["source_file"]
                or recording_a["channel"] == recording_b["channel"]):
            continue

        x_a = _load_span(recording_a, member_a["start_idx"], member_a["end_idx"])
        x_b = _load_span(recording_b, member_b["start_idx"], member_b["end_idx"])
        lag, waveform_correlation, classification_bin = classify_waveforms(x_a, x_b)

        _set_motif_edge_classification(
            conn, edge["id"], lag, waveform_correlation, classification_bin,
        )
        results.append({
            "edge_id": edge["id"],
            "member_a_id": edge["member_a_id"],
            "member_b_id": edge["member_b_id"],
            "lag": lag,
            "waveform_correlation": waveform_correlation,
            "classification_bin": classification_bin,
        })

    return results


def recurrence_count(conn, entry_id):
    """Recurrence count for a motif family, with artifact edges excluded.

    An edge classified as `artifact` is a shared-ground recording error, not a
    finding, so it contributes nothing to this count.
    """
    return sum(
        1 for edge in R.list_motif_edges(conn, entry_id)
        if edge["classification_bin"] != ARTIFACT
    )



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
