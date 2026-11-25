"""Score queue 47 (diversity proposals, background controls, repeat checks) and refresh the catalogue, read-only.

In plain words: queue 47 mixed three kinds of item, shuffled and with their sources hidden: 750 new detector
proposals from under-covered recordings, 54 random windows of matched duration on the same channels, and 46 items
the researcher had already judged in the cross-recording drop panel (queue 38), shown again unannounced. Now that
every item is answered, this script unblinds them from the private key, scores each group, compares each repeat
with its frozen first answer, and rebuilds the accepted-span inventory from the live database so the thesis counts
include the new acceptances.

No verdict, annotation or file under DATA/ is written. One read transaction gives one cutoff for everything.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/reviews_queue47_20261109.py
"""
from __future__ import annotations

import collections
import datetime as dt
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from Working.review import queues  # noqa: E402
from scripts.rq2_blind import wilson  # noqa: E402
from scripts.thesis.accepted_catalogue import build, connect, csv_write  # noqa: E402

QUEUE = 47
KEY = ROOT / "DATA/derived/library_diversity_review_20261108/key.json"
OUT = ROOT / "docs/thesis/data/queue47_20261109"
CAT = ROOT / "docs/thesis/data/accepted_catalogue_20261109"
PREVIOUS = ROOT / "docs/thesis/data/accepted_catalogue/summary.json"
ACCEPT = {"interesting", "seed"}


def tally(verdicts):
    counts = collections.Counter(verdicts)
    n = sum(counts.values())
    k = sum(counts[v] for v in ACCEPT)
    decided = k + counts["not_interesting"]
    lo, hi = wilson(k, n) if n else (None, None)
    return {"reviewed": n, "accepted": k, "rate": k / n if n else None, "wilson_lo": lo, "wilson_hi": hi,
            "interesting": counts["interesting"], "seed": counts["seed"],
            "not_interesting": counts["not_interesting"], "unsure": counts["unsure"],
            "artifact": counts["artifact"], "decided": decided,
            "rate_excluding_unsure_artifact": k / decided if decided else None}


def fisher(k1, n1, k2, n2):
    from scipy.stats import fisher_exact
    return float(fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])[1])


def kappa(pairs):
    """Cohen's kappa for two binary ratings (accepted or not); None when undefined."""
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe >= 1 else (po - pe) / (1 - pe)


def score(c, key):
    own, cur = {}, {}
    for r in c.execute("SELECT id, detection_id, verdict, carried_from FROM adjudications ORDER BY id"):
        cur[r["detection_id"]] = dict(r)
        if r["carried_from"] is None:
            own[r["detection_id"]] = dict(r)
    edited = {int(r[0]) for r in c.execute("SELECT detection_id FROM review_span_edits")}
    rows = []
    for item in key["presentations"]:
        ids = item["represented_detection_ids"]
        mine = [own[d] for d in ids if d in own]
        if len({r["verdict"] for r in mine}) > 1:
            raise ValueError(f"conflicting own answers within one presentation: {ids}")
        chosen = max(mine, key=lambda r: r["id"]) if mine else None
        rows.append({"group": item["group"], "dataset": item.get("dataset") or item.get("recording"),
                     "primary_group": (item.get("source") or {}).get("primary_group"),
                     "earlier": (item.get("earlier") or {}).get("verdict"),
                     "verdict": chosen["verdict"] if chosen else None,
                     "carried_only": bool([cur[d] for d in ids if d in cur]) and not mine,
                     "span_corrected": any(d in edited for d in ids)})
    return rows


def main():
    key = json.loads(KEY.read_text(encoding="utf-8"))
    if key["queue_id"] != QUEUE or len(key["presentations"]) != key["presentation_count"]:
        raise ValueError("the private key does not describe queue 47's 850 presentations")
    c = connect(ROOT / "DATA/db/annotations.sqlite")
    try:
        counts = queues.queue_counts(c, QUEUE)
        rows = score(c, key)
        observations, events, recs = build(c)
        cutoff = {t: c.execute(f"SELECT MAX(id) FROM {t}").fetchone()[0]
                  for t in ("adjudications", "annotations", "review_audit")}
    finally:
        c.close()
    OUT.mkdir(parents=True, exist_ok=True)
    CAT.mkdir(parents=True, exist_ok=True)

    answered = [r for r in rows if r["verdict"]]
    by = collections.defaultdict(list)
    for r in answered:
        by[(r["group"], r["dataset"])].append(r["verdict"])
        by[(r["group"], "All")].append(r["verdict"])
    acceptance = [{"group": g, "dataset": d, **tally(v)} for (g, d), v in sorted(by.items())]

    div = tally(by[("diversity_candidate", "All")])
    bg = tally(by[("background_control", "All")])
    reps = [r for r in rows if r["group"] == "rq2_repeat"]
    pairs = [(r["earlier"] in ACCEPT, r["verdict"] in ACCEPT) for r in reps if r["verdict"] and r["earlier"]]
    changes = collections.Counter((r["primary_group"], r["earlier"], r["verdict"]) for r in reps)
    repeat = {"items": len(reps), "answered": sum(bool(r["verdict"]) for r in reps),
              "same_accept_decision": sum(a == b for a, b in pairs),
              "accepted_then_not": sum(a and not b for a, b in pairs),
              "not_then_accepted": sum(b and not a for a, b in pairs),
              "identical_word": sum(r["earlier"] == r["verdict"] for r in reps if r["verdict"]),
              "kappa_accept": kappa(pairs),
              "by_primary_group": {g: {"items": sum(r["primary_group"] == g for r in reps),
                                       "first_accepted": sum(r["primary_group"] == g and r["earlier"] in ACCEPT
                                                             for r in reps),
                                       "now_accepted": sum(r["primary_group"] == g and r["verdict"] in ACCEPT
                                                           for r in reps)}
                                   for g in sorted({r["primary_group"] for r in reps})},
              "transitions": [{"primary_group": g, "first": a, "now": b, "n": n}
                              for (g, a, b), n in sorted(changes.items(), key=lambda kv: tuple(map(str, kv[0])))]}
    if repeat["same_accept_decision"]:
        lo, hi = wilson(repeat["same_accept_decision"], len(pairs))
        repeat.update(agreement=repeat["same_accept_decision"] / len(pairs), agreement_wilson=[lo, hi])

    thesis = [e for e in events if e["thesis_scope"]]
    previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    per_dataset = dict(collections.Counter(e["dataset"] for e in thesis))
    catalogue = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "cutoff": cutoff, "read_only": True,
                 "thesis_span_components": len(thesis), "previous_thesis_span_components":
                     previous["thesis_span_components"], "previous_cutoff": previous["cutoff"],
                 "per_dataset": per_dataset,
                 "previous_per_dataset": {k: v for k, v in previous["per_dataset"].items() if k in per_dataset},
                 "linked_to_queue_47": sum(QUEUE in e["queue_ids"] for e in thesis),
                 "by_boundary_status": dict(collections.Counter(e["boundary_status"] for e in thesis)),
                 "accepted_observations": sum(r["accepted"] for r in observations),
                 "accepted_observations_by_source": dict(collections.Counter(
                     r["source"] for r in observations if r["accepted"])),
                 "wider_project_components": len(events) - len(thesis)}
    summary = {"queue_id": QUEUE, "live_counts": counts, "presentations": len(rows), "answered": len(answered),
               "carried_only": sum(r["carried_only"] for r in rows),
               "span_corrected": dict(collections.Counter(r["group"] for r in rows if r["span_corrected"])),
               "diversity_candidates": div, "background_controls": bg,
               "candidates_vs_controls_fisher_p": fisher(div["accepted"], div["reviewed"],
                                                         bg["accepted"], bg["reviewed"]),
               "repeats": repeat, "catalogue": catalogue, "cutoff": cutoff}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    csv_write(OUT / "acceptance.csv", acceptance)
    (CAT / "summary.json").write_text(json.dumps(catalogue, indent=2), encoding="utf-8")
    csv_write(CAT / "accepted_spans.csv", thesis)
    print(json.dumps({k: v for k, v in summary.items() if k != "catalogue"}, indent=2))
    print(json.dumps(catalogue, indent=2))
    for a in acceptance:
        print(f"{a['group']:20s} {a['dataset']:10s} {a['accepted']:4d}/{a['reviewed']:<4d} "
              f"{100 * a['rate']:5.1f}% [{100 * a['wilson_lo']:.1f}-{100 * a['wilson_hi']:.1f}] "
              f"not {a['not_interesting']} unsure {a['unsure']} artefact {a['artifact']} seed {a['seed']}")


if __name__ == "__main__":
    main()
