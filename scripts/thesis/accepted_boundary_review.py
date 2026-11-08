"""Make a self-contained boundary editor and validate its explicit human choices."""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import sys
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def signature(events):
    return hashlib.sha256(json.dumps(events, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


def validate_decisions(doc, manifest):
    if doc.get("format") != "mycowave-boundary-review-v1" or doc.get("manifest_hash") != signature(manifest):
        raise ValueError("Review file does not match its saved catalogue snapshot")
    index = {e["event_id"]: e for e in manifest}
    good = []
    seen = set()
    for choice in doc["decisions"]:
        if not choice.get("complete"):
            continue
        eid = choice["event_id"]
        if eid in seen or eid not in index:
            raise ValueError("Unknown or duplicated reviewed event")
        seen.add(eid)
        event = index[eid]
        if int(choice["recording_id"]) != event["recording_id"]:
            raise ValueError("Recording differs from the reviewed waveform")
        segments = choice["segments"]
        if not segments:
            raise ValueError("No events in a completed boundary check")
        for s in segments:
            a, b = s["start_idx"], s["end_idx"]
            if type(a) is not int or type(b) is not int or not (event["context_start"] <= a < b <= event["context_end"]) or b-a < 2:
                raise ValueError("Reviewed interval is outside its waveform or empty")
        good.append((event, choice))
    return good


def apply_decisions(c, path, out):
    """Only explicit saved human choices write annotations; one audit per choice."""
    from Working.database import queries as Q
    from Working.library.importers.sequences import insert_sequence
    from Working.registration.settings import append_audit
    doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    key = doc.get("manifest_hash", "")
    if not isinstance(key, str) or len(key) != 20 or any(ch not in "0123456789abcdef" for ch in key):
        raise ValueError("Invalid review manifest identifier")
    manifest = json.loads((out / f"review_manifest_{key}.json").read_text())
    choices = validate_decisions(doc, manifest)
    existing = set()
    for r in c.execute("SELECT note FROM annotations WHERE source='catalogue_boundary_review' AND deleted_at IS NULL"):
        existing.add(json.loads(r[0])["decision_key"])
    results = []
    for event, choice in choices:
        dkey = hashlib.sha256(json.dumps(choice, sort_keys=True).encode()).hexdigest()
        if dkey in existing:
            results.append({"event_id": event["event_id"], "status": "already_present"})
            continue
        children = []
        for i, s in enumerate(choice["segments"]):
            note = {"decision_key": dkey, "boundary_status": "human_checked", "manifest_hash": key,
                    "original_event_id": event["event_id"], "supersedes_source_refs": event["source_refs"],
                    "segment_index": i, "reviewed_at": choice["reviewed_at"],
                    "acceptance_level": "explicit boundary review"}
            aid = Q.insert_annotation(c, event["recording_id"], s["start_idx"], s["end_idx"],
                    "interesting", "catalogue_boundary_review", note=json.dumps(note), event_count=1, commit=False)
            children.append(aid)
        sequence_id = None
        if len(children) > 1:
            # Explicitly checked children are individual annotations. Their
            # ordered container is a separate, machine-assembled sequence;
            # shared context/recoveries must not merge the children again.
            ordered = sorted(zip(choice["segments"], children), key=lambda item: (item[0]["start_idx"], item[0]["end_idx"]))
            rec = c.execute("SELECT channel,fs FROM recordings WHERE id=?", (event["recording_id"],)).fetchone()
            members = [{"member_id": None, "start_idx": s["start_idx"], "end_idx": s["end_idx"],
                        "gap_before": None if i == 0 else (s["start_idx"]-ordered[i-1][0]["start_idx"])/rec["fs"]}
                       for i, (s, aid) in enumerate(ordered)]
            sequence_id = insert_sequence(c, {
                "sequence_key": "checked-sequence-"+dkey[:20], "origin": "machine",
                "recording_id": event["recording_id"], "channel": rec["channel"],
                "start_idx": min(s["start_idx"] for s, _ in ordered),
                "end_idx": max(s["end_idx"] for s, _ in ordered), "n_events": len(children),
                "needs_extraction": False, "source_kind": "catalogue_checked_segments", "source_store": str(path),
                "source_ref": json.dumps({"decision_key": dkey, "parent_observation": event["event_id"],
                                          "child_annotation_ids": [aid for _, aid in ordered]}),
                "content_hash": dkey, "created_at": choice["reviewed_at"]}, members)
        audit = append_audit(c, "accepted-boundary-review", f"{event['event_id']}: {len(children)} checked events",
                "Library", actor="researcher boundary editor", route="scripts.thesis.accepted_boundary_review.apply_decisions",
                detail={"decision": choice, "annotation_ids": children, "sequence_id": sequence_id,
                        "original_source_refs": event["source_refs"]}, commit=False)
        results.append({"event_id": event["event_id"], "status": "created", "annotation_ids": children,
                        "sequence_id": sequence_id, "audit_id": audit})
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "docs/thesis/data/accepted_catalogue")
    ap.add_argument("--queue-id", type=int, help="Focus on accepted spans linked to this review source")
    ap.add_argument("--html-name", default="boundary_review.html")
    ap.add_argument("--hierarchy", type=pathlib.Path, help="Unchecked individual-event suggestions with separate sequence parents")
    args = ap.parse_args()
    if pathlib.Path(args.html_name).name != args.html_name or not args.html_name.endswith(".html"):
        raise ValueError("html-name must be one HTML filename")
    review_dir = args.project_root / "DATA/derived/accepted_catalogue_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads((args.out / "catalogue.json").read_text())
    hierarchy = json.loads(args.hierarchy.read_text()) if args.hierarchy else {}
    parent_suggestions = {p["event_id"]: p for p in hierarchy.get("parents", [])}
    child_suggestions = {p["event_id"]: p for p in hierarchy.get("individual_events", [])}
    observation_sources = {r["ref"]: r["source"] for r in data["observations"]}
    pub = json.loads((args.out / "published.json").read_text()) if (args.out / "published.json").exists() else {}
    mids = {e["event_id"]: e["member_id"] for e in pub.get("links", [])}
    recs = {int(k): v for k, v in data["recordings"].items()}
    events, manifest, cache = [], [], {}
    review_items = [{**e, "item_kind": "event_span"} for e in data["events"]]
    for r in data["observations"]:
        if not r["accepted"] or not r["valid_bounds"] or r["kind"] == "event_span" or r["source"] == "researcher_train_region":
            continue
        rid = r["canonical_recording_id"]
        rec = recs[rid]
        review_items.append({"event_id": "region-"+r["ref"].replace(":", "-"),
            "dataset": r["dataset"], "thesis_scope": r["thesis_scope"], "recording_id": rid,
            "channel": rec["channel"], "fs": rec["fs"], "start_idx": r["canonical_start"],
            "end_idx": r["canonical_end"], "span_s": (r["canonical_end"]-r["canonical_start"])/rec["fs"],
            "source_refs": [r["ref"]], "source_count": 1, "acceptance_level": r["kind"],
            "train_id": None, "item_kind": r["kind"]})
    for e in review_items:
        if not e["thesis_scope"] or (args.queue_id and args.queue_id not in e.get("queue_ids", [])):
            continue
        rec = recs[e["recording_id"]]
        path = args.project_root / rec["npy_path"]
        if str(path) not in cache:
            cache[str(path)] = np.load(path, mmap_mode="r")
        arr = cache[str(path)]
        fs = float(rec["fs"])
        factor = {"V": 1000, "mV": 1, "uV": .001}.get(rec["units"])
        if factor is None:
            raise ValueError(f"Unknown signal unit for {e['event_id']}")
        pad = max(round(300 * fs), min(round(3600 * fs), 2 * (e["end_idx"] - e["start_idx"])))
        a, b = max(0, e["start_idx"] - pad), min(len(arr), e["end_idx"] + pad)
        x = np.asarray(arr[a:b], dtype=float) * factor
        if not np.isfinite(x).all():
            raise ValueError(f"Non-finite waveform needs separate inspection: {e['event_id']}")
        flags = []
        if e.get("other_event_sized_negative_refs"):
            flags.append(f"Other event-sized negative judgements retained: {len(e['other_event_sized_negative_refs'])}")
        if e["item_kind"] != "event_span":
            flags.append("Accepted window/region: draw the individual events before adding them to the event catalogue")
        core = x[e["start_idx"]-a:e["end_idx"]-a]
        smooth = gaussian_filter1d(core, max(.5, fs)) if len(core) > 3 else core
        noise = float(np.median(np.abs(np.diff(core)))) * 1.4826 if len(core) > 1 else 0.
        threshold = max(.1, 6*noise, .25 * float(np.ptp(smooth)))
        down, dp = find_peaks(-smooth, prominence=threshold, distance=max(1, round(fs*3)))
        up, up_p = find_peaks(smooth, prominence=threshold, distance=max(1, round(fs*3)))
        peaks = down if max(dp["prominences"], default=0) >= max(up_p["prominences"], default=0) else up
        if len(peaks) > 1:
            flags.append(f"Possible multiple events: {len(peaks)} prominent extrema")
        if len(core) > 4 and np.ptp(core) > 0:
            lo, hi = np.quantile(core, [.05, .95])
            if core[0] < lo or core[0] > hi or core[-1] < lo or core[-1] > hi:
                flags.append("An edge is near an extreme: check onset and recovery in context")
        if e.get("train_id"):
            flags.append("Train extraction: machine-proposed extent")
        if e["span_s"] > 3600:
            flags.append("Long accepted region: check for several separate events")
        n = min(900, len(x))
        step = max(1, int(np.ceil(len(x)/n)))
        starts = np.arange(0, len(x), step)
        lo = np.minimum.reduceat(x, starts)
        hi = np.maximum.reduceat(x, starts)
        ev = {**e, "flags": flags, "trace": {"start": a, "end": b, "step": step,
                "lo": [float(f"{v:.7g}") for v in lo], "hi": [float(f"{v:.7g}") for v in hi]},
              "explore_url": f"http://127.0.0.1:8765/#/explore/span-edit/m-{mids[e['event_id']]}" if e["event_id"] in mids else "http://127.0.0.1:8765/#/explore"}
        proposed = parent_suggestions.get(e["event_id"])
        protected = any(observation_sources.get(ref) in {"review-span-edit", "catalogue_boundary_review"} for ref in e["source_refs"])
        if proposed and not protected:
            ev["suggested_segments"] = [{"start_idx": max(a, child_suggestions[c]["start_idx"]),
                                         "end_idx": min(b, child_suggestions[c]["end_idx"])}
                                        for c in proposed["individual_event_ids"]]
            ev["suggested_segments"] = [s for s in ev["suggested_segments"] if s["end_idx"]-s["start_idx"]>=2]
            if len(ev["suggested_segments"]) > 1:
                flags.append(f"Unchecked sequence proposal: {len(ev['suggested_segments'])} separate events; preserve their separate selections")
        elif protected:
            ev["suggested_segments"] = [{"start_idx": e["representative_start"], "end_idx": e["representative_end"]}]
            ev["starting_extent_source"] = "saved_human_extent"
        events.append(ev)
        manifest.append({"event_id": e["event_id"], "recording_id": e["recording_id"],
                         "source_refs": e["source_refs"], "context_start": a, "context_end": b})
    key = signature(manifest)
    (args.out / f"review_manifest_{key}.json").write_text(json.dumps(manifest), encoding="utf-8")
    payload = json.dumps({"manifest_hash": key, "events": events}, ensure_ascii=True).replace("</", "<\\/")
    template = (pathlib.Path(__file__).with_name("boundary_review.html")).read_text(encoding="utf-8")
    (review_dir / args.html_name).write_text(template.replace("__PAYLOAD__", payload), encoding="utf-8")
    summary = {"items": len(events), "event_spans": sum(e["item_kind"] == "event_span" for e in events),
               "windows_and_regions_to_extract": sum(e["item_kind"] != "event_span" for e in events),
               "flagged_event_spans": sum(e["item_kind"] == "event_span" and bool(e["flags"]) for e in events),
               "event_spans_with_multiple_extrema": sum(e["item_kind"] == "event_span" and any(f.startswith("Possible multiple") for f in e["flags"]) for e in events),
               "flagged": sum(bool(e["flags"]) for e in events),
               "multiple_extrema": sum(any(f.startswith("Possible multiple") for f in e["flags"]) for e in events),
               "manifest_hash": key, "queue_id": args.queue_id, "html": str((review_dir / args.html_name).resolve())}
    summary_name = "boundary_audit_summary.json" if args.html_name == "boundary_review.html" else pathlib.Path(args.html_name).stem+"_summary.json"
    (args.out / summary_name).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
