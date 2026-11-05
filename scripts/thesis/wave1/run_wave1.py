"""
run_wave1.py — the thesis's wave-1 data export, in one read-only command (2026-11-05).

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/wave1/run_wave1.py --out DATA/derived/thesis_bundle/wave1

Options: ``--db`` (default DATA/db/annotations.sqlite), ``--only step,step`` (default every step), ``--max-part-mb``
(default 24), ``--step-timeout-min`` (default 90), ``--zip-only`` (re-zip what is already exported), ``--no-zip``.

Each step runs on its own: a failure is logged with its traceback and the run goes on. The run ends by writing
REPORT.md (each step ok/failed, counts, sizes, timings) and zipping everything into parts of at most 24 MB
(``wave1_part01.zip`` = the report, the manifest and the log; ``wave1_part02.zip`` ... = the data), and prints the
part paths. Re-running is safe: a step clears only its own folder under ``<out>/data/<step>/`` first.

Read-only: the database is opened with a ``mode=ro`` URI and ``PRAGMA query_only``; channels are memory-mapped one
at a time. No network, no bridge. M4_aug (the held-out exam) is exported: its exam was scored on 2026-10-26.
*Schizophyllum commune* is refused everywhere: its blind exam is unjudged.

Steps, in order (cheap first; the two that load the R4 model last):
    meta                  every recording row, datasets, Review queues with item counts, candidate tables, groupings
    overviews             every channel of every kept recording, mean per 60 s, whole length
    full_channels         M2_concat CH0/2/13, rec 385 and Fig2A whole, native rate
    windows               bundle_spec.json's windows and rule windows (gallery, b1_trains, b4_stack, agreement,
                          cnn_scores + the CNN window scores from the step cache)
    detections_in_windows every live completed run's detections (real and surrogate, flagged), candidate events and
                          human verdicts overlapping each window
    drop_v1_all           drop_detection_v1 (default settings) on every channel of the round-B recordings
    queues                queues 25, 28, 35, 36: items, strata, verdicts, a window per item; queue 35's seeds
    library_events        the g-11 events with families and a window each; rec 385's members with g-05 families
    hand_labels           the imported 10-minute labels; 10 windows per class
    misses                human-accepted events no sweep family touches; 12 windows
    drop_motifs_store     the final drop-motif store (events, snippets or a subset, FIGURES/CLAIMS/sequences)
    existing_plots        Plots/Detection/mp, family_search, Classification/{cnn,gramian,dendrogram}
    pool                  candidate-event pool: counts, collapse, sample, shape features, R4 scores, thumbnails
    m4_exam               the 290 exam items, verdicts, R4 scores, the 48-h window and its candidates' R4 scores
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(HERE))          # scripts/thesis: the `wave1` package

from wave1 import common as C  # noqa: E402

STEP_ORDER = ["meta", "overviews", "full_channels", "windows", "detections_in_windows", "drop_v1_all", "queues",
              "library_events", "hand_labels", "misses", "drop_motifs_store", "existing_plots", "pool", "m4_exam"]


def step_functions():
    from wave1 import export_bundle as X, m4_payload as M, pool as P
    return {"meta": X.step_meta, "overviews": X.step_overviews, "full_channels": X.step_full_channels,
            "windows": X.step_windows, "detections_in_windows": X.step_detections_in_windows,
            "drop_v1_all": X.step_drop_v1_all, "queues": X.step_queues, "library_events": X.step_library_events,
            "hand_labels": X.step_hand_labels, "misses": X.step_misses, "drop_motifs_store": X.step_drop_motifs_store,
            "existing_plots": X.step_existing_plots, "pool": P.step_pool, "m4_exam": M.step_m4_exam}


def estimate_seconds(ctx, steps):
    """A rough runtime estimate from the data volumes (reading ~30 M samples/s; ~4 us per candidate in the
    collapse; ~6 ms per R4-scored and measured event; a minute to load R4)."""
    s = 0.0
    kept_samples = sum(r["n_samples"] for sf in ctx.kept.values() for r in ctx.channels_of(sf))
    if "overviews" in steps:
        s += kept_samples / 30e6 + 10
    if "full_channels" in steps:
        s += 30
    for name in ("windows", "detections_in_windows", "drop_v1_all", "queues", "misses"):
        if name in steps:
            s += 120
    for name in ("meta", "library_events", "hand_labels", "drop_motifs_store", "existing_plots"):
        if name in steps:
            s += 30
    if "pool" in steps or "m4_exam" in steps:
        s += 90
    if "pool" in steps:
        tabs = [C.newest_table(ctx, sf) for k, sf in ctx.kept.items() if sf != C.HELD_OUT_FILE]
        n = sum(int(t["n_events"] or 0) for t in tabs if t)
        s += n * 4e-6 + 2000 * 0.006 * sum(1 for t in tabs if t) + 20
    if "m4_exam" in steps:
        s += 290 * 0.006 + 5000 * 0.006
    return s


def run_step(ctx, name, fn):
    ctx.start_step(name)
    n_notes = len(ctx.notes)
    t = time.time()
    status, error, summary = "ok", None, None
    ctx.log(f"--- start {name}")
    try:
        ctx.step_dir(name, clear=True)          # this step's own folder only: a re-run replaces, never mixes
        summary = fn(ctx)
    except C.StepTimeout as e:
        status, error = "timeout", f"{e}\n" + ctx.log_exception(name)
    except Exception:  # noqa: BLE001 - every step on its own: logged, and the run goes on
        status, error = "failed", ctx.log_exception(name)
    secs = time.time() - t
    d = os.path.join(ctx.data_dir, name)
    files = sum(len(f) for _dp, _dn, f in os.walk(d)) if os.path.isdir(d) else 0
    st = {"step": name, "status": status, "seconds": round(secs, 1), "finished_at": C.now_iso(),
          "summary": summary, "error": error, "files": files, "bytes": C.file_bytes(d),
          "warnings": [n.split("] ", 1)[-1] for n in ctx.notes[n_notes:]]}
    C.write_json(os.path.join(ctx.data_dir, "_status", f"{name}.json"), st)
    ctx.log(f"--- {name}: {status.upper()} in {secs:.1f}s ({files} files, {st['bytes'] / 1e6:.1f} MB)")
    ctx.step = "-"
    ctx.deadline = None
    return st


def parse(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join("DATA", "derived", "thesis_bundle", "wave1"))
    ap.add_argument("--db", help="the sqlite database (default <root>/DATA/db/annotations.sqlite), opened read-only")
    ap.add_argument("--root", default=C.CODE_ROOT, help="the repo root holding DATA/, Plots/ and docs/ (default: "
                                                        "the checkout this script is in)")
    ap.add_argument("--spec", default=C.SPEC_PATH)
    ap.add_argument("--only", help="comma-separated steps (default: all): " + ",".join(STEP_ORDER))
    ap.add_argument("--max-part-mb", type=float, default=24.0)
    ap.add_argument("--step-timeout-min", type=float, default=90.0)
    ap.add_argument("--zip-only", action="store_true", help="run no step; re-zip what is already in --out")
    ap.add_argument("--no-zip", action="store_true")
    return ap.parse_args(argv)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    a = parse(argv)
    root = os.path.abspath(a.root)
    db = os.path.abspath(a.db) if a.db else os.path.join(root, "DATA", "db", "annotations.sqlite")
    out = os.path.abspath(a.out if os.path.isabs(a.out) else os.path.join(os.getcwd(), a.out))
    try:
        holds_db = os.path.commonpath([out, os.path.dirname(db)]) == out
    except ValueError:                                   # different drives on Windows
        holds_db = False
    if out == root or holds_db:
        raise SystemExit(f"--out {out} would hold the repo root or the database folder; choose a folder of its own")
    with open(a.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    only = [s.strip() for s in a.only.split(",")] if a.only else list(STEP_ORDER)
    bad = [s for s in only if s not in STEP_ORDER]
    if bad:
        raise SystemExit(f"unknown step(s) {bad}; the steps are {STEP_ORDER}")
    os.makedirs(out, exist_ok=True)
    ctx = C.Ctx(root=root, db_path=db, out=out, spec=spec, max_part_mb=a.max_part_mb,
                step_timeout_s=a.step_timeout_min * 60)
    t0 = time.time()
    try:
        ctx.log(f"wave-1 export: db {db} (read-only), out {out}")
        ctx.log(f"kept recordings: {ctx.kept}")
        steps = [] if a.zip_only else [s for s in STEP_ORDER if s in only]
        try:
            est = estimate_seconds(ctx, steps)
        except Exception:  # noqa: BLE001 - an estimate is never worth stopping for
            est = 0.0
        ctx.log(f"steps: {steps or '(none: zip only)'}; rough estimate {est / 60:.0f} min")
        fns = step_functions()
        results = [run_step(ctx, s, fns[s]) for s in steps]
        run_s = time.time() - t0
        parts = []
        if not a.no_zip:
            from wave1 import zipper
            ctx.step = "zip"
            parts = zipper.finish(ctx, order=STEP_ORDER, args=sys.argv[1:] if argv is None else list(argv),
                                  estimate=est, run_s=run_s)
        else:
            from wave1 import zipper
            with open(os.path.join(out, "REPORT.md"), "w", encoding="utf-8") as fh:
                fh.write(zipper.report_text(ctx, order=STEP_ORDER, args=list(argv or sys.argv[1:]), estimate=est,
                                            run_s=run_s))
        ok = [r["step"] for r in results if r["status"] == "ok"]
        notok = [f"{r['step']} ({r['status']})" for r in results if r["status"] != "ok"]
        ctx.step = "done"
        ctx.log(f"finished in {(time.time() - t0) / 60:.1f} min: {len(ok)} ok, {len(notok)} not ok"
                + (f": {', '.join(notok)}" if notok else ""))
        ctx.log(f"REPORT: {os.path.join(out, 'REPORT.md')}")
        for p in parts:
            ctx.log(f"PART: {p} ({os.path.getsize(p) / 1e6:.1f} MB)")
        if notok:
            ctx.log("some steps did not finish: REPORT.md (in part 01) says which and why; the rest is exported")
        return 0 if (parts or a.no_zip) else 1
    finally:
        ctx.close()


if __name__ == "__main__":
    sys.exit(main())
