"""
run_references.py
=================
Auto-detect on the reference stretches (2026-11-19 prototype); everything it finds, graded against what was
reviewed there, written to ``docs/autodetect/20261119/<reference>/``.

In plain words
--------------
For each reference: run auto-detect (`Working.autodetect.pipeline.auto_detect`), then lay the result over the
answer sheet — the accepted catalogue's events, the rejected verdicts and (on M2_aug) the judged 10-minute windows.
A reviewed event counts as **found** when a candidate covers at least half of the shorter of the two (the rule
detector agreement uses). The **hit rate** counts only candidates that land on reviewed material: of those, the
share on an accepted event. Unreviewed stretches are neither right nor wrong (Q15 (a)).

Read-only: the database is opened ``mode=ro``, the channel files are memory-mapped, and every write under DATA/ is
refused by a guard. Writes only ``docs/autodetect/20261119/``.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/run_references.py [--only KEY ...]
"""

from __future__ import annotations

import argparse
from functools import partial
import json
import os
import sys
import tempfile
import time

os.environ.setdefault("NUMBA_NUM_THREADS", "8")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as K  # noqa: E402

# the whole-drop rule as committed (the researcher, 2026-11-23), unless AUTODETECT_WHOLE_DROP_REV says otherwise
# ("working" = the working copy)
_REV = os.environ.get("AUTODETECT_WHOLE_DROP_REV", "HEAD")
WHOLE_DROP_PIN = None if _REV == "working" else K.pin_whole_drop(_REV)

from Working.autodetect.pipeline import auto_detect, auto_detect_both  # noqa: E402
from Working.discovery.candidate_events import AGREE_SHARE, _caught  # noqa: E402

THRESHOLDS = tuple(round(v, 2) for v in np.arange(0.30, 0.96, 0.05))
from Working.autodetect.seeds import MIN_FAMILY_LINE as SEED_MIN_FAMILY_LINE  # noqa: E402
LABELS = ("accepted", "rejected", "window_interesting", "window_not", "unjudged")


def _arr(df, col):
    return df[col].to_numpy(np.int64) if len(df) else np.zeros(0, np.int64)


def label_candidates(cands, known):
    """What each candidate lands on, the first that applies: an accepted event, a rejected one, an interesting
    window, a not-interesting window, nothing reviewed."""
    cs, ce = _arr(cands, "start"), _arr(cands, "end")
    acc, rej, win = known["accepted"], known["rejected"], known["windows"]
    on_acc = _caught(cs, ce, _arr(acc, "start"), _arr(acc, "end"), AGREE_SHARE)
    on_rej = _caught(cs, ce, _arr(rej, "start"), _arr(rej, "end"), AGREE_SHARE)
    wi = win[win["verdict"] == "interesting"] if len(win) else win
    wn = win[win["verdict"] == "not_interesting"] if len(win) else win
    on_wi = _caught(cs, ce, _arr(wi, "start"), _arr(wi, "end"), AGREE_SHARE)
    on_wn = _caught(cs, ce, _arr(wn, "start"), _arr(wn, "end"), AGREE_SHARE)
    out = np.full(len(cands), "unjudged", dtype=object)
    for mask, name in ((on_wn, "window_not"), (on_wi, "window_interesting"), (on_rej, "rejected"),
                       (on_acc, "accepted")):
        out[mask] = name
    return out


def evaluate(cands, known, proposals):
    acc, win = known["accepted"], known["windows"]
    conf = cands["confidence"].to_numpy(float) if len(cands) else np.zeros(0)
    rows = []
    wi = win[win["verdict"] == "interesting"] if len(win) else win
    wn = win[win["verdict"] == "not_interesting"] if len(win) else win
    for t in THRESHOLDS:
        c = cands[conf >= t]
        cs, ce = _arr(c, "start"), _arr(c, "end")
        found = _caught(_arr(acc, "start"), _arr(acc, "end"), cs, ce, AGREE_SHARE)
        lab = c["known"].value_counts().to_dict() if len(c) else {}
        judged = lab.get("accepted", 0) + lab.get("rejected", 0)
        row = {"threshold": t, "candidates": int(len(c)), "r4_scan_only": int((c["kind"] == "r4_scan").sum()),
               "accepted_found": int(found.sum()), "accepted_total": int(len(acc)),
               "recall": float(found.mean()) if len(acc) else None,
               "on_accepted": int(lab.get("accepted", 0)), "on_rejected": int(lab.get("rejected", 0)),
               "hit_rate": (lab.get("accepted", 0) / judged) if judged else None,
               "unjudged": int(lab.get("unjudged", 0))}
        # the same without R4's own window-scan candidates (detectors and seeds only)
        cp = c[c["kind"] != "r4_scan"]
        fp = _caught(_arr(acc, "start"), _arr(acc, "end"), _arr(cp, "start"), _arr(cp, "end"), AGREE_SHARE)
        lp = cp["known"].value_counts().to_dict() if len(cp) else {}
        jp = lp.get("accepted", 0) + lp.get("rejected", 0)
        row.update(proposals=int(len(cp)), proposals_found=int(fp.sum()),
                   proposals_recall=float(fp.mean()) if len(acc) else None,
                   proposals_hit_rate=(lp.get("accepted", 0) / jp) if jp else None)
        if len(win):
            row["windows_interesting_touched"] = float(_caught(_arr(wi, "start"), _arr(wi, "end"), cs, ce,
                                                               AGREE_SHARE).mean()) if len(wi) else None
            row["windows_not_touched"] = float(_caught(_arr(wn, "start"), _arr(wn, "end"), cs, ce,
                                                       AGREE_SHARE).mean()) if len(wn) else None
        rows.append(row)
    # who found what: accepted events each source's raw proposals reach (before any merge)
    by_source = {}
    labelled = proposals.assign(source=[f"{s} (inverted)" if r == "inverted" else s for s, r in
                                         zip(proposals["source"], proposals.get("run", pd.Series("normal", index=proposals.index)))])
    for src, g in labelled.groupby("source"):
        f = _caught(_arr(acc, "start"), _arr(acc, "end"), _arr(g, "start"), _arr(g, "end"), AGREE_SHARE)
        by_source[str(src)] = {"proposals": int(len(g)), "accepted_reached": int(f.sum())}
    by_variant = {}
    for var, g in proposals.groupby("variant"):
        if str(var).startswith("seed__"):
            continue
        f = _caught(_arr(acc, "start"), _arr(acc, "end"), _arr(g, "start"), _arr(g, "end"), AGREE_SHARE)
        by_variant[str(var)] = {"proposals": int(len(g)), "accepted_reached": int(f.sum())}
    sc = cands[cands["kind"] == "r4_scan"]
    by_source["r4_scan (own candidates)"] = {"proposals": int(len(sc)), "accepted_reached": int(
        _caught(_arr(acc, "start"), _arr(acc, "end"), _arr(sc, "start"), _arr(sc, "end"), AGREE_SHARE).sum())}
    by_polarity = {}
    if "polarity" in cands:
        for pol, name in (("drop", "drops"), ("spike", "rises")):
            g = cands[(cands["polarity"] == pol) & (conf >= 0.5)]
            lab = g["known"].value_counts().to_dict() if len(g) else {}
            judged = lab.get("accepted", 0) + lab.get("rejected", 0)
            f = _caught(_arr(acc, "start"), _arr(acc, "end"), _arr(g, "start"), _arr(g, "end"), AGREE_SHARE)
            by_polarity[name] = {"candidates_05": int(len(g)), "accepted_found_05": int(f.sum()),
                                 "on_accepted": int(lab.get("accepted", 0)), "on_rejected": int(lab.get("rejected", 0)),
                                 "unjudged": int(lab.get("unjudged", 0)),
                                 "hit_rate": (lab.get("accepted", 0) / judged) if judged else None,
                                 "from_inverted_run": int((g["run"] == "inverted").sum()) if "run" in g else 0,
                                 "found_by_both_runs": int((g["runs"] == "both").sum()) if "runs" in g else 0}
    return {"by_threshold": rows, "by_source": by_source, "by_variant": by_variant, "by_polarity": by_polarity,
            "labels": cands["known"].value_counts().to_dict() if len(cands) else {}}


def _fingerprint(path):
    """sha256 (first 12) and mtime of a rule file, as this process loaded it (read at import, beside the import)."""
    import hashlib
    full = os.path.join(K.ROOT, path)
    with open(full, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()[:12]
    return {"sha256_12": digest, "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(full)))}


# the shared rules auto-detect imports and other sessions edit: which version a run used
RULE_FILES = {p: _fingerprint(p) for p in ("Working/autodetect/anchor.py", "Working/autodetect/pipeline.py",
                                           "Working/autodetect/gates.py", "Working/autodetect/finder.py")}
RULE_FILES["Working/interrogation/whole_drop.py"] = (
    {"pinned_to_git": WHOLE_DROP_PIN} if WHOLE_DROP_PIN else {"working_copy": _fingerprint(K.WHOLE_DROP)})


def run_one(conn, ref, steps, fams, rule, *, every_family=False):
    rec, a, b = K.stretch(conn, ref)
    x = K.load_samples(rec, a, b)
    floor, floor_src = K.noise_floor_mv(conn, rec["source_file"])
    key = ref["key"] + ("__every_family" if every_family else "")
    print(f"\n=== {key}: rec {rec['id']} {rec['source_file']} CH{rec['channel']}  samples {a}-{b} "
          f"({len(x)} at {rec['fs']} Hz, {len(x) / rec['fs'] / 3600:.0f} h)  floor {floor} mV ({floor_src})",
          flush=True)
    scorer = K.make_r4_scorer(conn, rec["id"], a)
    t0 = time.perf_counter()
    if every_family:
        run = auto_detect
    else:
        # drops and sharp rises: the whole process again on the inverted signal, R4 included
        run = partial(auto_detect_both, score_spans_inverted=K.make_r4_scorer(conn, rec["id"], a, invert=True))
    res = run(x, rec["fs"], units=rec["units"], detectors=steps, seed_families=fams, score_spans=scorer,
                      floor_mv=floor, start_idx=a, rule=rule, seed_min_family_line=None if every_family else
                      SEED_MIN_FAMILY_LINE,
                      on_progress=lambda m: print(f"  [{time.perf_counter() - t0:7.1f} s] {m}", flush=True))
    wall = time.perf_counter() - t0
    known = K.reviewed(conn, ref, rec, a, b)
    cands = res.candidates
    cands["known"] = label_candidates(cands, known) if len(cands) else []
    ev = evaluate(cands, known, res.proposals)

    out = os.path.join(K.OUT, key)
    os.makedirs(out, exist_ok=True)
    cands.to_csv(os.path.join(out, "candidates.csv"), index=False)
    res.sequences.to_csv(os.path.join(out, "sequences.csv"), index=False)
    res.proposals.to_csv(os.path.join(out, "proposals.csv"), index=False)
    res.scan_hits.to_csv(os.path.join(out, "scan_hits.csv"), index=False)
    for k, df in known.items():
        df.to_csv(os.path.join(out, f"known_{k}.csv"), index=False)
    meta = {"reference": ref, "key": key, "every_family": bool(every_family), "rule_files": RULE_FILES,
            "seed_min_family_line": None if every_family else SEED_MIN_FAMILY_LINE,
            "recording": {k: rec[k] for k in ("id", "source_file", "channel", "fs", "units", "npy_path")},
            "stretch": {"start_idx": a, "end_idx": b, "n_samples": int(len(x))},
            "floor_mv": floor, "floor_source": floor_src, "wall_s": wall, "timings": res.timings,
            "scan_windows": res.scan_windows, "info": res.info, "evaluation": ev,
            "known_counts": {k: int(len(v)) for k, v in known.items()}}
    with open(os.path.join(out, "run.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    row = next(r for r in ev["by_threshold"] if r["threshold"] == 0.5)
    print(f"  done in {wall:.0f} s: {len(res.proposals)} proposals -> {len(cands)} candidates "
          f"({(cands['kind'] == 'r4_scan').sum()} R4-scan only), {len(res.sequences)} sequences; "
          f"at 0.5: {row['accepted_found']}/{row['accepted_total']} accepted found, hit rate {row['hit_rate']}",
          flush=True)
    if res.info.get("errors"):
        print("  ERRORS:", json.dumps(res.info["errors"], indent=1), flush=True)
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="reference keys to run (default all)")
    ap.add_argument("--every-family", action="store_true",
                    help="search every seed family, loose ones included (the first agreed rule; output key "
                         "<reference>__every_family)")
    args = ap.parse_args(argv)
    K.install_write_guard()
    K.redirect_adapter_outputs(tempfile.mkdtemp(prefix="autodetect_"))
    conn = K.connect()
    steps = K.detector_specs(conn)
    fams, bank = K.load_seed_bank()
    rule = K.matching_rule(conn)
    print(f"{len(fams)} seed families; detectors {[s['variant'] for s in steps]}; rule {rule}", flush=True)
    refs = [r for r in K.REFERENCES if not args.only or r["key"] in args.only]
    summary = []
    for ref in refs:
        meta = run_one(conn, ref, steps, fams, rule, every_family=args.every_family)
        summary.append({"key": meta["key"], "wall_s": meta["wall_s"]})
    print("\n" + json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
