"""
extent.py
==========
What can be said about a stored event's extent from its row alone, and the frame a
sequence of events is drawn in (fixup-h). Reads rows; changes nothing. The stored
extent is the Library's identity - the content hash covers the whole snippet - so
nothing here redefines it (`docs/prompts/fixup/future/N-event-extent.md`).

Capped edges
------------
`detect5.window_bounds` brackets an event by its morphology (sharkfin: its own
preceding rise -> the next rise; trough: previous recovery -> its own recovery
end). But a scale-free cap of `window_cap_mult` falls is applied first and clamps
every branch, and the row does not record which rule set an edge. `capped_edges`
recovers it from the indices: an edge that sits EXACTLY at `onset - cap` (or
`trough + cap`) was set by the backstop, or tied with it. An edge the recording's
own start stopped is a different fact and is not called capped.

The fall the cap is measured in is the detector's: `max(trough - onset, one
encoding segment)`, so a fall shorter than a segment is capped at six segments.

The sequence frame
------------------
`Pipelines/drop_motifs/drawing_rules.py::sequence_frames` as numbers rather than
as a matplotlib figure, so a page can draw it: each event framed back to the
PREVIOUS event's trough (the slow rise is part of a sharkfin; 1.2 falls before
the onset shows the last tenth of it), capped at `MAX_PRE_FALLS`, with
`POST_TROUGH_FALLS` after the trough, clipped to what the stored snippet holds.
The first event of a run has no predecessor and falls back to `PRE_ONSET_FALLS`.

Snippet mismatch
----------------
`DETECTION_AND_FIGURES.md` 6.7: some stores carry a snippet array shorter than
`snippet_end_idx - snippet_start_idx` claims. Sliced by the indices, such a row
draws as a one-sample fall. `snippet_mismatch` says so.
"""

import json
import os

# The same constants `drawing_rules.py` draws the thesis figures with. Restated,
# not imported: that module pulls in matplotlib and its figure style.
PRE_ONSET_FALLS = 1.2
POST_TROUGH_FALLS = 1.8
MAX_PRE_FALLS = 14.0

# `Detect5Params.window_cap_mult`'s default, and the value every stored event
# was detected under.
DEFAULT_CAP_MULT = 6.0


def _fall_samples(event):
    """`window_bounds`' own `fall`: never shorter than one encoding segment."""
    fs = float(event["fs"])
    segment = int(round(float(event.get("segment_seconds") or 0.0) * fs))
    return max(int(event["trough_idx"]) - int(event["onset_idx"]), segment, 1)


def capped_edges(event, cap_mult=DEFAULT_CAP_MULT):
    """`(left, right)` - whether each stored edge sits exactly at the fall-multiple cap."""
    cap = int(round(float(cap_mult) * _fall_samples(event)))
    start, end = int(event["snippet_start_idx"]), int(event["snippet_end_idx"])
    left_at = int(event["onset_idx"]) - cap
    left = left_at > 0 and start == left_at          # at <= 0 the recording's start set it
    right = end == int(event["trough_idx"]) + cap
    return bool(left), bool(right)


def capped_counts(events, cap_mult=DEFAULT_CAP_MULT):
    """How many of `events` have each edge at the cap."""
    flags = [capped_edges(e, cap_mult) for e in events]
    return {"n": len(flags), "cap_mult": float(cap_mult),
            "left": sum(1 for a, _ in flags if a), "right": sum(1 for _, b in flags if b),
            "both": sum(1 for a, b in flags if a and b)}


def sequence_frames(members, post=POST_TROUGH_FALLS, max_pre_falls=MAX_PRE_FALLS):
    """One frame per member, in the order given.

    Each is `{pre_s, post_s, reach_falls, first, capped, clipped}`: seconds drawn
    before the onset and after the trough, how many falls back the frame reaches,
    whether the member had no predecessor, whether the `max_pre_falls` cap set the
    left edge, and whether the stored snippet was shorter than the frame asked for.

    "Previous" is the previous event on the same recording in time order, whatever
    order the rows arrive in.
    """
    order = sorted(range(len(members)), key=lambda i: (members[i].get("recording_id", 0), int(members[i]["onset_idx"])))
    out = [None] * len(members)
    previous = {}
    for i in order:
        row = members[i]
        fs = float(row["fs"])
        fall = _fall_s(row)
        onset, trough = int(row["onset_idx"]), int(row["trough_idx"])
        key = row.get("recording_id", 0)
        first = key not in previous
        want_pre = PRE_ONSET_FALLS * fall if first else max(0.0, (onset - previous[key]) / fs)
        capped = want_pre > max_pre_falls * fall
        pre = min(want_pre, max_pre_falls * fall)
        post_s = float(post) * fall
        have_pre = max(0.0, (onset - int(row["snippet_start_idx"])) / fs)
        have_post = max(0.0, (int(row["snippet_end_idx"]) - trough) / fs)
        clipped = pre > have_pre + 1e-9 or post_s > have_post + 1e-9
        pre, post_s = min(pre, have_pre), min(post_s, have_post)
        out[i] = {"pre_s": float(pre), "post_s": float(post_s), "reach_falls": float(pre / fall),
                  "first": bool(first), "capped": bool(capped), "clipped": bool(clipped)}
        previous[key] = trough
    return out


def _fall_s(row):
    """The event's fall in seconds, never zero - one sample if the store says 0 (`drawing_rules.fall_duration_s`)."""
    fs = float(row["fs"])
    duration = abs(float(row.get("fall_duration_s") or 0.0))
    return duration if duration > 0 else 1.0 / fs


def snippet_mismatch(row, n_stored):
    """`{stored, claimed}` when the stored array is not the length its indices claim, else None."""
    claimed = int(row["snippet_end_idx"]) - int(row["snippet_start_idx"])
    if int(n_stored) == claimed:
        return None
    return {"stored": int(n_stored), "claimed": claimed}


def main(out_dir):
    """The capped-edge counts on the seed store, per family, as json + markdown (`scripts/fixup_h_evidence.py capped`)."""
    from Working.Detection.drop_motifs import store as S
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    seed = os.path.join(repo, "DATA", "library_seed", "drop_motifs5", "motifs")
    events = S.load_events(seed)
    snips = S.load_snippets(seed)
    families = {}
    for e in events:
        families.setdefault(e.get("span_key") or f"r{e['recording_id']}", []).append(e)
    rows = []
    for key, members in sorted(families.items()):
        c = capped_counts(members)
        rows.append({"family": key, "morphology": members[0].get("morphology"), **c,
                     "impure": sum(1 for m in members if int(m.get("purity", 1)) != 1),
                     "mismatch": sum(1 for m in members if m["event_id"] in snips
                                     and snippet_mismatch(m, len(snips[m["event_id"]]["detrended_mv"])))})
    total = capped_counts(events)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "capped-edges.json"), "w", encoding="utf-8") as f:
        json.dump({"total": total, "families": rows}, f, indent=2)
    lines = ["| family | morphology | n | left capped | right capped | both | impure windows | snippet mismatch |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['family']} | {r['morphology']} | {r['n']} | {r['left']} | {r['right']} | {r['both']} | {r['impure']} | {r['mismatch']} |")
    lines.append(f"| **all** | | **{total['n']}** | **{total['left']}** ({100 * total['left'] / total['n']:.0f} %) | "
                 f"**{total['right']}** ({100 * total['right'] / total['n']:.0f} %) | **{total['both']}** | "
                 f"{sum(r['impure'] for r in rows)} | {sum(r['mismatch'] for r in rows)} |")
    with open(os.path.join(out_dir, "capped-edges.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
