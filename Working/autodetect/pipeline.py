"""
pipeline.py
===========
`auto_detect`: one channel through every source, merged, redrawn around its events, gated, scored, blended and
sequenced, with every stage timed.

The caller supplies what needs files or the database, so this module needs neither:

* ``detectors`` — a list of ``{"variant", "steps", "window_s", "fit"}`` (a template's parsed ``steps_json``; with
  ``window_s`` the chain runs over sliding windows, `chains.run_chain_windowed`). The variant's part before ``__`` is
  its source, so a detector's whole-stretch and windowed runs are one vote. A plain ``{name: steps}`` dict is read as
  whole-stretch runs.
* ``seed_families`` — `seeds.SeedFamily` objects;
* ``score_spans(starts, ends) -> p`` — R4's probability for spans of this channel (relative sample indices);
* ``floor_mv`` — the dataset's noise floor.

Stages (v2, 2026-11-23; v3 the same evening):

1. **Proposals**: every detector (whole stretch and sliding windows), the seed search (tight families only) and, with
   ``use_finder``, the researcher's own event rule as a finder (`finder.find`: every sharp fall, and every steady,
   significant one).
2. **Merge** (`candidates.merge`): the same-event rule, near-duplicates, loose boxes.
3. **Boxes** (`candidates.reanchor`): every candidate redrawn around every event it points at — the Library's whole
   drop, top to half recovery (or to the bottom when it does not recover) — and boxes holding one event made one
   (Q1 (b)). A candidate that points at no event is dropped.
4. **R4's scan**: windows of 2/6/10/30 min, the summit of overlapping hits at p >= 0.5; a hit over a candidate adds
   only its score (``scan_p``); one over nothing is redrawn around the event inside it, or dropped if it holds none
   (Q4 (b)).
5. **Gates** (`gates`): not flat drift (judged over the candidate's original and redrawn boxes together, Q2 (a)),
   not shallower than the noise floor, a rise sharp (``min_sharpness``) and a drop told from noise (``drop_rule``:
   sharp, or steady and significant, `gates.distinct`). The same event rule is applied before boxes are joined, so
   what it rejects never absorbs a real event. Then every box's margins are cut back from its neighbours
   (`anchor.clip_margins`).
6. **R4 on every box** (with half the box's length of context either side), the blend (`blend`), and a scan
   candidate kept only at R4 >= 0.5 on its redrawn box.
7. **Sequences** (`sequences.find_sequences`).

A stage that fails is recorded in ``info["errors"]`` and the others still run; the result says so rather than
going quiet.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from Working.autodetect import anchor as AN
from Working.autodetect import blend, candidates as C, finder, gates, scan, seeds, sequences
from Working.autodetect.chains import run_chain, run_chain_windowed
from Working.discovery.candidate_events import AGREE_SHARE, _caught, family_of
from Working.units import read_as_mv


@dataclass
class AutoDetectResult:
    """What one channel produced."""
    candidates: pd.DataFrame
    sequences: pd.DataFrame
    proposals: pd.DataFrame
    scan_windows: int
    scan_hits: pd.DataFrame
    timings: dict
    info: dict = field(default_factory=dict)


def _stage(timings, errors, name, fn):
    t0 = time.perf_counter()
    try:
        return fn()
    except Exception:  # noqa: BLE001 — recorded loudly in the result, never swallowed into a blank
        errors[name] = traceback.format_exc()
        return None
    finally:
        timings[name] = time.perf_counter() - t0


def detector_specs(detectors):
    """The ``detectors`` argument as a list of specs (a ``{name: steps}`` dict is whole-stretch runs)."""
    if isinstance(detectors, dict):
        return [{"variant": k, "steps": v, "window_s": None, "fit": False} for k, v in detectors.items()]
    return [{"variant": d["variant"], "steps": d["steps"], "window_s": d.get("window_s"), "fit": bool(d.get("fit"))}
            for d in detectors]


def sharp_enough(polarity, sharp, min_sharpness):
    """Which events pass the sharpness rule: ``min_sharpness`` None (every one), a number, or ``{polarity: number}``
    (a polarity it does not name passes). An event whose sharpness cannot be read passes."""
    sharp = np.asarray(sharp, dtype=float)
    if min_sharpness is None:
        return np.ones(len(sharp), dtype=bool)
    if isinstance(min_sharpness, dict):
        need = [min_sharpness.get(str(q)) for q in polarity]
        return np.array([n is None or not (s < float(n)) for s, n in zip(sharp, need)], dtype=bool)
    return ~(sharp < float(min_sharpness))


def auto_detect(x, fs, *, units, detectors, seed_families, score_spans, floor_mv, start_idx=0,
                scan_durations_s=scan.DURATIONS_S, scan_min_p=scan.MIN_P, precision=None, rule=None,
                seed_min_family_line=seeds.MIN_FAMILY_LINE, min_unexplained=gates.MIN_UNEXPLAINED,
                invert=False, keep_polarity=None, min_sharpness=None, drop_rule=None, use_finder=False,
                on_progress=None):
    """Run auto-detect over ``x`` (one channel, stored unit ``units``, sampled at ``fs``).

    ``invert`` runs the whole process on ``-x`` (the researcher's trial, 2026-11-23: rises found the way drops are);
    its drops are the recording's rises and come back labelled ``spike``. ``keep_polarity`` keeps only candidates of
    that polarity in the frame the process ran in (``"drop"``: each run keeps the falls it was built to find).
    ``min_sharpness`` (a number, or ``{polarity: number}`` in the run's own frame) drops candidates whose steepest
    1-second step is under that many times the channel's step noise (`gates.sharpness`; "sharp rises only").
    ``drop_rule`` names the polarity, in the run's own frame, that holds the recording's drops: those must be told
    from noise (`gates.distinct`: sharp, or at least 5 samples falling steadily to a significant bottom - the
    researcher's rule, 2026-11-23). ``use_finder`` adds that rule's own finder as a proposal source (`finder.find`;
    steady falls only when the run's falls are the recording's drops)."""
    timings, errors, info = {}, {}, {}
    say = on_progress or (lambda msg: None)
    x = np.asarray(x, dtype=float)
    if invert:
        x = -x
    factor, unit_note = read_as_mv(units)
    x_mv = x * factor
    n = len(x)
    info.update(n_samples=int(n), fs=float(fs), start_idx=int(start_idx), units=units, unit_note=unit_note,
                floor_mv=float(floor_mv))
    noise = gates.step_noise(x_mv, fs)
    info["step_noise_mv"] = float(noise)

    # 1. proposals
    parts = []
    for spec in detector_specs(detectors):
        name = spec["variant"]
        say(f"detector {name}" + (f" in {spec['window_s'] / 3600:g} h windows" if spec["window_s"] else ""))
        if spec["window_s"]:
            fn = (lambda spec=spec: run_chain_windowed(spec["steps"], x, fs, window_s=spec["window_s"],
                                                       fit=spec["fit"], start_idx=start_idx, units=units))
        else:
            fn = (lambda spec=spec: run_chain(spec["steps"], x, fs, start_idx=start_idx, units=units))
        out = _stage(timings, errors, f"detector:{name}", fn)
        if out is not None and len(out["starts"]):
            parts.append(pd.DataFrame({"start": out["starts"], "end": out["ends"], "variant": name,
                                       "source": family_of(name), "score": out["scores"]}))
        info.setdefault("detector_counts", {})[name] = 0 if out is None else int(len(out["starts"]))
    say(f"seed search ({len(seed_families)} families)")
    got = _stage(timings, errors, "seeds", lambda: seeds.search(x_mv, fs, seed_families, floor_mv=floor_mv,
                                                                min_family_line=seed_min_family_line))
    if got is not None:
        seed_matches, seed_report = got
        info["seed_report"] = seed_report
        if len(seed_matches):
            parts.append(seed_matches.assign(score=seed_matches["corr"]))
    if use_finder:
        say("the event rule as a finder")
        found = _stage(timings, errors, "event_rule", lambda: finder.find(x_mv, fs, floor_mv=floor_mv, noise=noise,
                                                                          steady=(drop_rule == "drop")))
        info.setdefault("detector_counts", {})[finder.SOURCE] = 0 if found is None else int(len(found))
        if found is not None and len(found):
            parts.append(found)
    proposals = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["start", "end", "variant", "source", "score"])
    proposals = proposals[(proposals["end"] > proposals["start"])].reset_index(drop=True)

    # 2. merge, 3. boxes
    say(f"merge ({len(proposals)} proposals)")
    cands = _stage(timings, errors, "merge", lambda: C.merge(proposals, rule=rule))
    if cands is None:
        cands = C.merge(None)
    say(f"boxes ({len(cands)} candidates)")

    def event_rule(frame, end_col):
        """(deep, rise_ok, drop_ok, sharpness) of each event: the floor, "sharp rises only", and a drop told from
        noise (the researcher's rule, 2026-11-23)."""
        pol = frame["polarity"].astype(str).to_numpy()
        on = frame["onset"].to_numpy(np.int64)
        ex = frame["extremum"].to_numpy(np.int64)
        en = pd.to_numeric(frame[end_col], errors="coerce").fillna(frame["extremum"]).to_numpy(np.int64)
        sharp = np.array([gates.sharpness(x_mv, o, e, fs, noise) for o, e in zip(on, ex)], dtype=float)
        deep = frame["depth_mv"].astype(float).to_numpy() >= float(floor_mv)
        rise_ok = sharp_enough(pol, sharp, min_sharpness)
        drop_ok = np.ones(len(frame), dtype=bool)
        if drop_rule is not None:
            sel = pol == str(drop_rule)
            if sel.any():
                drop_ok[sel] = gates.distinct(x_mv, fs, on[sel], ex[sel], en[sel], sharp[sel],
                                              falling=(str(drop_rule) == "drop"))
        return deep, rise_ok, drop_ok, sharp

    def is_event(an):
        # what this run's own rules reject is no event, and must not absorb a real one before it goes (M4 CH1
        # 64:00 h, 2026-11-23): shallower than the noise floor, a rise not sharp, a drop not told from noise
        deep, rise_ok, drop_ok, _sharp = event_rule(an, "end")
        return deep & rise_ok & drop_ok

    got = _stage(timings, errors, "boxes", lambda: C.reanchor(cands, proposals, x_mv, fs, is_event=is_event))
    if got is not None:
        cands, info["boxes"] = got

    # 4. R4's scan
    say("R4 window scan")
    ws, we, wd = scan.windows(n, fs, scan_durations_s)
    wp = _stage(timings, errors, "r4_scan", lambda: np.asarray(score_spans(ws, we), dtype=float))
    if wp is not None:
        keep = scan.peaks(ws, we, wp, min_p=scan_min_p)
        hits = pd.DataFrame({"start": ws[keep], "end": we[keep], "p": wp[keep], "duration_s": wd[keep]})
        info["scan_windows_above_min_p"] = int(np.sum(np.isfinite(wp) & (wp >= scan_min_p)))
        info["scan_p_quantiles"] = {q: float(np.nanquantile(wp, q)) for q in (0.5, 0.9, 0.99)} if len(wp) else {}
    else:
        hits = pd.DataFrame(columns=["start", "end", "p", "duration_s"])
    cands, own = C.attach_scan(cands, hits)
    scan_rows = pd.DataFrame()
    if own is not None and len(own):
        an = AN.anchor_all(x_mv, own["start"].to_numpy(np.int64), own["end"].to_numpy(np.int64), fs)
        ok = an["ok"].to_numpy(dtype=bool)
        into = AN.same_event(an, own["p"].to_numpy(dtype=float))
        roots = [i for i in sorted(set(into.tolist())) if ok[i]]
        scan_rows = pd.DataFrame({
            "start": an.loc[roots, "box_start"].astype(np.int64).to_numpy(),
            "end": an.loc[roots, "box_end"].astype(np.int64).to_numpy(),
            "anchor_variant": blend.R4_SCAN, "member_variants": blend.R4_SCAN, "n_members": 1, "sources": "",
            "n_sources": 0, "orig_start": own["start"].to_numpy(np.int64)[roots],
            "orig_end": own["end"].to_numpy(np.int64)[roots], "anchored": True,
            "polarity": an.loc[roots, "polarity"].to_numpy(), "onset": an.loc[roots, "onset"].to_numpy(),
            "extremum": an.loc[roots, "extremum"].to_numpy(), "event_end": an.loc[roots, "end"].to_numpy(),
            "recovered": an.loc[roots, "recovered"].to_numpy(), "depth_mv": an.loc[roots, "depth_mv"].to_numpy(),
            "scan_p": own["p"].to_numpy(dtype=float)[roots]})
        # a window over no candidate can still redraw onto a candidate's event (its box runs past the window):
        # that is the candidate again, and R4 never reinforces itself
        dup = _caught(scan_rows["start"].to_numpy(np.int64), scan_rows["end"].to_numpy(np.int64),
                      cands["start"].to_numpy(np.int64), cands["end"].to_numpy(np.int64), AGREE_SHARE) \
            if len(cands) and len(scan_rows) else np.zeros(len(scan_rows), dtype=bool)
        scan_rows = scan_rows[~dup].reset_index(drop=True)
        info["scan_own"] = {"hits": int(len(own)), "no_event": int((~ok).sum()), "redrawn": int(len(roots)),
                            "onto_a_candidate": int(dup.sum())}

    # 5. gates
    say("gates")
    allc = pd.concat([cands.assign(kind=C.KIND_PROPOSAL), scan_rows.assign(kind=C.KIND_SCAN)], ignore_index=True) \
        if len(scan_rows) else cands.assign(kind=C.KIND_PROPOSAL)

    def _gate():
        lo = np.minimum(allc["orig_start"].to_numpy(np.int64), allc["start"].to_numpy(np.int64))
        hi = np.maximum(allc["orig_end"].to_numpy(np.int64), allc["end"].to_numpy(np.int64))
        passes, fr = gates.flat_mask(x_mv, lo, hi, fs, min_unexplained=min_unexplained)
        deep, sharp_ok, drop_ok, sharp = event_rule(allc, "event_end")
        if keep_polarity is None:
            pol = np.ones(len(allc), dtype=bool)
        else:
            pol = allc["polarity"].astype(str).to_numpy() == str(keep_polarity)
        return passes, fr, deep, sharp, pol, sharp_ok, drop_ok

    got = _stage(timings, errors, "gates", _gate) if len(allc) else None
    if got is not None:
        passes, fr, deep, sharp, pol, sharp_ok, drop_ok = got
        allc["unexplained"] = fr
        allc["sharpness"] = sharp
        keep = passes & deep & pol & sharp_ok & drop_ok
        info["gates"] = {"flat": int((~passes).sum()), "below_floor": int((passes & ~deep).sum()),
                         "other_polarity": int((passes & deep & ~pol).sum()),
                         "not_sharp": int((passes & deep & pol & ~sharp_ok).sum()),
                         "not_distinct": int((passes & deep & pol & sharp_ok & ~drop_ok).sum()),
                         "flat_by_kind": allc.loc[~passes, "kind"].value_counts().to_dict()}
        allc = allc[keep].reset_index(drop=True)
    if len(allc):
        # no box's margins reach into a neighbouring event (M2_aug CH7_B2 282:58 h, 2026-11-23)
        bs, be = AN.clip_margins(allc["start"], allc["end"], allc["onset"],
                                 pd.to_numeric(allc["event_end"], errors="coerce").fillna(allc["extremum"]))
        allc["start"], allc["end"] = bs, be

    # 6. R4 on every box, the blend
    say(f"R4 on {len(allc)} candidates")
    def _r4():
        # R4 sees each event with half its box's length of context either side (on top of its own quarter): the
        # framing of the reviewed spans it was trained on, not a tight event box (2026-11-23: on the reviewed
        # candidates, accepted events at p >= 0.5 went from 84 % to 96 % on M2_aug and 98 % to 100 % on CH14)
        s = allc["start"].to_numpy(np.int64)
        e = allc["end"].to_numpy(np.int64)
        half = (e - s) // 2
        return np.asarray(score_spans(np.maximum(0, s - half), np.minimum(n, e + half)), dtype=float)

    p = _stage(timings, errors, "r4_candidates", lambda: _r4() if len(allc) else np.zeros(0))
    p = p if p is not None else np.full(len(allc), np.nan)
    allc = C.score(allc, p, precision=precision)
    is_scan = (allc["kind"] == C.KIND_SCAN).to_numpy()
    if is_scan.any():
        allc.loc[is_scan, "confidence"] = allc.loc[is_scan, "p_r4"].fillna(0.0)
        allc.loc[is_scan, "floor"] = 0.0
        low = is_scan & ~(allc["p_r4"].fillna(0.0).to_numpy() >= float(scan_min_p))
        info.setdefault("scan_own", {})["below_min_p_after_redraw"] = int(low.sum())
        allc = allc[~low].reset_index(drop=True)
    cands = allc.sort_values(["start", "end"]).reset_index(drop=True)
    cands.insert(0, "candidate_id", np.arange(len(cands), dtype=np.int64))
    cands["start_idx"] = cands["start"].astype(np.int64) + int(start_idx)
    cands["end_idx"] = cands["end"].astype(np.int64) + int(start_idx)
    cands["start_s"] = cands["start_idx"] / float(fs)
    cands["end_s"] = cands["end_idx"] / float(fs)
    cands["duration_s"] = (cands["end"] - cands["start"]) / float(fs)

    # 7. sequences
    say("sequences")
    got = _stage(timings, errors, "sequences", lambda: sequences.find_sequences(cands, fs))
    if got is not None:
        labels, seqs, seq_info = got
        cands["sequence_id"] = labels
        seqs = seqs.copy()
        if len(seqs):
            seqs["start_idx"] = seqs["start"].astype(np.int64) + int(start_idx)
            seqs["end_idx"] = seqs["end"].astype(np.int64) + int(start_idx)
            seqs["start_s"] = seqs["start_idx"] / float(fs)
            seqs["end_s"] = seqs["end_idx"] / float(fs)
        info["sequence_info"] = seq_info
    else:
        cands["sequence_id"] = -1
        seqs = pd.DataFrame(columns=list(sequences.SEQUENCE_COLUMNS))

    if invert and len(cands):                # the run's drops are the recording's rises (and the other way round)
        cands["polarity"] = cands["polarity"].map({"drop": "spike", "spike": "drop"}).fillna(cands["polarity"])
    cands["run"] = "inverted" if invert else "normal"
    info["invert"] = bool(invert)
    info["errors"] = errors
    info["counts"] = {"proposals": int(len(proposals)), "candidates": int(len(cands)),
                      "r4_scan_only": int((cands["kind"] == C.KIND_SCAN).sum()), "sequences": int(len(seqs))}
    return AutoDetectResult(candidates=cands, sequences=seqs, proposals=proposals, scan_windows=int(len(ws)),
                            scan_hits=hits, timings=timings, info=info)


def _anchored_of(cands):
    """The candidates as `anchor` rows (every candidate is an anchored event), for the cross-run event rules."""
    return pd.DataFrame({"ok": True, "why": None, "polarity": cands["polarity"].astype(str).to_numpy(),
                         "onset": cands["onset"].to_numpy(np.int64), "extremum": cands["extremum"].to_numpy(np.int64),
                         "end": cands["event_end"].to_numpy(np.int64), "recovered": cands["recovered"].to_numpy(),
                         "depth_mv": cands["depth_mv"].to_numpy(dtype=float),
                         "box_start": cands["start"].to_numpy(np.int64), "box_end": cands["end"].to_numpy(np.int64)})


def combine_runs(normal, inverted):
    """One candidate set from the run on ``x`` and the run on ``-x``, by the rules each run applies to itself:
    candidates whose rises overlap are one event, kept from the run that scored it higher (``runs`` says "both"); then
    a candidate that is the other run's event's return (the rise back after a drop, the fall back after a spike) or
    part of a much deeper event folds into it (`anchor.same_event`, `anchor.fold`). Returns ``(candidates, report)``;
    the caller cuts margins back from neighbours (`anchor.clip_margins`)."""
    both = pd.concat([normal, inverted], ignore_index=True)
    report = {"normal": int(len(normal)), "inverted": int(len(inverted)), "rises_found_by_both": 0,
              "same_event_removed": 0, "folded_across_runs": 0}
    if not len(both):
        return both.assign(runs=pd.Series(dtype=object)), report
    both["runs"] = both["run"].astype(str)
    an = _anchored_of(both)
    conf = both["confidence"].to_numpy(dtype=float)
    into = AN.same_event(an, conf)
    runs = both["run"].astype(str).to_numpy(dtype=object)
    groups = {}
    for k, root in enumerate(into):
        groups.setdefault(int(root), []).append(k)
    for members in groups.values():
        best = max(members, key=lambda k: (conf[k], -k))
        into[np.asarray(members)] = best
        if len(members) > 1:
            report["same_event_removed"] += len(members) - 1
            if len({runs[k] for k in members}) > 1:
                both.loc[best, "runs"] = "both"
                report["rises_found_by_both"] += 1
    before = int(np.sum(into == np.arange(len(into))))
    into = AN.fold(an, into)
    keep = into == np.arange(len(into))
    report["folded_across_runs"] = before - int(keep.sum())
    out = both[keep].sort_values(["start", "end"]).reset_index(drop=True)
    return out, report


def auto_detect_both(x, fs, *, score_spans, score_spans_inverted=None, rise_sharpness=None, on_progress=None, **kw):
    """Drops AND rises (the researcher, 2026-11-23: "sharp rises only ... trial running the same (entire) process on
    the inverted version of the signal").

    Two runs of `auto_detect`: on ``x`` (its drops, and its rises when sharp) and on ``-x`` (its drops are the
    recording's rises; kept when sharp, `gates.MIN_RISE_SHARPNESS` unless ``rise_sharpness``).
    ``score_spans_inverted`` scores spans of ``-x``, so R4 too sees the inverted signal; without it R4 reads the
    signal as it is in both runs. The two sets are combined by `combine_runs`; sequences are found per polarity.
    Returns one `AutoDetectResult`; every candidate says which run it came from (``run``, and ``runs`` = "both" for
    a rise both runs found)."""
    sharp = gates.MIN_RISE_SHARPNESS if rise_sharpness is None else float(rise_sharpness)
    say = on_progress or (lambda msg: None)
    kw.setdefault("use_finder", True)
    rn = auto_detect(x, fs, score_spans=score_spans, min_sharpness={"spike": sharp}, drop_rule="drop",
                     on_progress=lambda m: say(f"normal: {m}"), **kw)
    ri = auto_detect(x, fs, score_spans=score_spans_inverted or score_spans, invert=True, keep_polarity="drop",
                     min_sharpness={"drop": sharp}, drop_rule="spike", on_progress=lambda m: say(f"inverted: {m}"),
                     **kw)
    info = dict(rn.info)
    info["inverted"] = ri.info
    info["rise_sharpness"] = sharp
    info["drop_rule"] = {"min_steady_samples": gates.MIN_STEADY_SAMPLES, "min_significance": gates.MIN_SIGNIFICANCE,
                         "side_s": gates.SIDE_S, "fine_s": gates.FINE_S, "sharp": sharp}
    info["r4_inverted"] = score_spans_inverted is not None
    both, info["combined"] = combine_runs(rn.candidates, ri.candidates)
    if len(both):
        # no box's margins reach into a neighbouring event of the other run either
        offset = int(kw.get("start_idx", 0))
        both["start"], both["end"] = AN.clip_margins(
            both["start"], both["end"], both["onset"],
            pd.to_numeric(both["event_end"], errors="coerce").fillna(both["extremum"]))
        both["start_idx"] = both["start"].astype(np.int64) + offset
        both["end_idx"] = both["end"].astype(np.int64) + offset
        both["start_s"] = both["start_idx"] / float(fs)
        both["end_s"] = both["end_idx"] / float(fs)
        both["duration_s"] = (both["end"] - both["start"]) / float(fs)
        both = both.sort_values(["start", "end"]).reset_index(drop=True)
    both["candidate_id"] = np.arange(len(both), dtype=np.int64)
    # sequences, per polarity
    both["sequence_id"] = -1
    seq_parts, next_id, seq_info = [], 0, {}
    for pol in ("drop", "spike"):
        sub = both[both["polarity"] == pol]
        if not len(sub):
            continue
        labels, seqs, si = sequences.find_sequences(sub.reset_index(drop=True), fs)
        both.loc[sub.index, "sequence_id"] = np.where(labels >= 0, labels + next_id, -1)
        if len(seqs):
            seqs = seqs.copy()
            seqs["sequence_id"] = seqs["sequence_id"] + next_id
            seqs["polarity"] = pol
            seq_parts.append(seqs)
            next_id = int(seqs["sequence_id"].max()) + 1
        seq_info[pol] = si
    seqs = pd.concat(seq_parts, ignore_index=True) if seq_parts else pd.DataFrame(
        columns=list(sequences.SEQUENCE_COLUMNS) + ["polarity"])
    start_idx = int(kw.get("start_idx", 0))
    if len(seqs):
        seqs["start_idx"] = seqs["start"].astype(np.int64) + start_idx
        seqs["end_idx"] = seqs["end"].astype(np.int64) + start_idx
        seqs["start_s"] = seqs["start_idx"] / float(fs)
        seqs["end_s"] = seqs["end_idx"] / float(fs)
    info["sequence_info"] = {"rule": " / ".join(f"{k}: {v.get('rule')}" for k, v in seq_info.items()),
                             "n_sequences": int(len(seqs)),
                             "n_in": int(sum(v.get("n_in", 0) for v in seq_info.values())), "by_polarity": seq_info}
    info["counts"] = {"proposals": int(len(rn.proposals) + len(ri.proposals)), "candidates": int(len(both)),
                      "r4_scan_only": int((both["kind"] == C.KIND_SCAN).sum()), "sequences": int(len(seqs)),
                      "drops": int((both["polarity"] == "drop").sum()),
                      "rises": int((both["polarity"] == "spike").sum())}
    info["errors"] = {**rn.info.get("errors", {}), **{f"inverted:{k}": v for k, v in ri.info.get("errors", {}).items()}}
    timings = {**{f"normal:{k}": v for k, v in rn.timings.items()},
               **{f"inverted:{k}": v for k, v in ri.timings.items()}}
    proposals = pd.concat([rn.proposals.assign(run="normal"), ri.proposals.assign(run="inverted")], ignore_index=True)
    hits = pd.concat([rn.scan_hits.assign(run="normal"), ri.scan_hits.assign(run="inverted")], ignore_index=True)
    return AutoDetectResult(candidates=both, sequences=seqs, proposals=proposals,
                            scan_windows=int(rn.scan_windows + ri.scan_windows), scan_hits=hits, timings=timings,
                            info=info)
