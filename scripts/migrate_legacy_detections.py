"""
migrate_legacy_detections.py
============================
Fixup M — run the one-time migration of legacy span-relative `detections`
rows against a real database, in the order that makes it safe, and verify
the result against the SIGNAL rather than the schema.

    python scripts/migrate_legacy_detections.py --db DATA/db/annotations.sqlite --dry-run
    python scripts/migrate_legacy_detections.py --db DATA/db/annotations.sqlite --apply
    python scripts/migrate_legacy_detections.py --db DATA/db/annotations.sqlite --verify
    python scripts/migrate_legacy_detections.py --db DATA/db/annotations.sqlite --redetect

The migration itself lives in `Working.database.schema` and runs inside
`init_db()`; this script only sequences it:

1. **Back up first**, with the sqlite backup API, to `<db dir>/backups/<stamp>-fixup-m.sqlite`
   (the same place `webui --project` writes its own), and refuse to continue
   unless the copy opens and passes `PRAGMA integrity_check`.
2. **Dry run**: print exactly which runs and how many rows the migration
   would rewrite, and which runs it refuses and why.
3. **Migrate**, through `init_db()` — the application path — and print the
   audit_log row it wrote.
4. **Verify against the signal**: for every rewritten row, load the channel
   and ask whether the window now sits on an event rather than on baseline.
   A row whose indices moved but which now points at flat signal means the
   shift was wrong. `--verify` alone re-runs this step later, reconstructing
   the pre-migration coordinates from the audit_log row (before = after -
   span_start), so it needs nothing but the migrated database.

Nothing here reads the real database through a junction, and `--apply`
refuses to run without a verified backup. Steps 1–2 alone are `--dry-run`.

The signal check
----------------
Two questions per window, both answered before and after the shift:

* **Is this window event-like for its run?** The window's peak-to-peak range
  is ranked against the same statistic over every same-length window across
  the run's span (the population the detector chose from). A detector fires
  where that statistic is extreme, so a correctly placed window ranks high;
  a window dropped on baseline ranks wherever chance puts it. Reported as a
  percentile; `>= 0.90` is called "event".
* **Does the window contain its extremum?** The window is widened by
  `PAD_FACTOR` x its length (at least `PAD_MIN` samples) each side, a straight
  line is fitted to that context to take slow drift out, and the sample of
  largest |residual| is the extremum. The window passes if it lies inside
  (a window narrower than `NARROW` samples passes within ±`NARROW`, so a
  one-sample spike marker is judged fairly).

A window as long as its whole span (a segment-type output) has no population
to rank against and is reported as `n/a`.

Both are heuristics. The decisive check is `--redetect`: each migrated run's
own recipe is re-run on its own span, headlessly and without writing
anything (adapters only, no run row, no cache, no persist), and the
detector's fresh spans — shifted by span_start exactly as the executor writes
them today — are compared with the migrated rows. A run whose migrated rows
are the rows its detector produces today is verified by the detector itself.
A chain that needs side inputs (`catalogue.cnn_score`) cannot be re-run this
way and is reported as such.
"""

import argparse
import datetime as _dt
import json
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db, plan_legacy_detections  # noqa: E402

PAD_FACTOR = 4
PAD_MIN = 120
NARROW = 3
EVENT_PERCENTILE = 0.90


def _connect_ro(path):
    conn = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(path).replace("\\", "/"), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------------------------------------------ steps --

def backup(db_path):
    backups_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), "backups")
    os.makedirs(backups_dir, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(backups_dir, "%s-fixup-m.sqlite" % stamp)
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    if not os.path.isfile(dest) or os.path.getsize(dest) == 0:
        raise SystemExit("backup at %s was not written" % dest)
    chk = _connect_ro(dest)
    try:
        integrity = chk.execute("PRAGMA integrity_check").fetchone()[0]
        n_det = chk.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
        n_runs = chk.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    finally:
        chk.close()
    if integrity != "ok":
        raise SystemExit("backup at %s failed integrity_check: %s" % (dest, integrity))
    return {"path": dest, "bytes": os.path.getsize(dest), "integrity_check": integrity,
            "runs": n_runs, "detections": n_det}


def dry_run(db_path):
    conn = _connect_ro(db_path)
    try:
        plan = plan_legacy_detections(conn)
        n_span = conn.execute("SELECT COUNT(*) FROM runs WHERE span_start > 0").fetchone()[0]
        n_span_det = conn.execute(
            "SELECT COUNT(DISTINCT r.id) FROM runs r JOIN detections d ON d.run_id = r.id "
            "WHERE r.span_start > 0").fetchone()[0]
        before = {}
        for entry in plan["runs"]:
            for det_id in entry["ids"]:
                r = conn.execute("SELECT start_idx, end_idx FROM detections WHERE id = ?", (det_id,)).fetchone()
                before[det_id] = (int(r["start_idx"]), int(r["end_idx"]))
    finally:
        conn.close()
    return {"plan": plan, "spanned_runs": n_span, "spanned_runs_with_detections": n_span_det,
            "before": before}


def print_plan(d):
    plan = d["plan"]
    print("runs with span_start > 0: %d; of those with detections: %d; to migrate: %d; refused: %d; rows: %d"
          % (d["spanned_runs"], d["spanned_runs_with_detections"], len(plan["runs"]),
             len(plan["refused"]), plan["n_rows"]))
    print("| run | span | length | n | min start_idx | ids |")
    print("|---|---|---|---|---|---|")
    for e in plan["runs"]:
        lo = min(d["before"][i][0] for i in e["ids"])
        ids = e["ids"]
        ids_s = ("%d..%d" % (ids[0], ids[-1])) if len(ids) > 2 else ", ".join(str(i) for i in ids)
        print("| %d | [%s, %s) | %s | %d | %s | %s |" % (
            e["run_id"], format(e["span_start"], ","), format(e["span_end"], ","),
            format(e["span_length"], ","), e["n"], format(lo, ","), ids_s))
    for e in plan["refused"]:
        print("REFUSED run %d (%s): span [%d, %d) n=%d n_legacy=%d"
              % (e["run_id"], e["reason"], e["span_start"], e["span_end"], e["n"], e["n_legacy"]))


def apply(db_path):
    conn = init_db(db_path)
    try:
        row = conn.execute("SELECT * FROM audit_log WHERE kind = 'migration' ORDER BY id DESC LIMIT 1").fetchone()
        audit = dict(row) if row is not None else None
        again = plan_legacy_detections(conn)
    finally:
        conn.close()
    return {"audit": audit, "second_pass": again}


def migrated_rows_from_audit(db_path):
    """(run_id, det_id, span_start) for every row the latest migration audit
    row names — the record the migration left, read back."""
    conn = _connect_ro(db_path)
    try:
        row = conn.execute("SELECT * FROM audit_log WHERE kind = 'migration' ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            raise SystemExit("no migration audit row in %s" % db_path)
        detail = json.loads(row["detail_json"])
    finally:
        conn.close()
    out = []
    for e in detail["runs"]:
        out.extend((e["run_id"], i, e["span_start"]) for e2 in [e] for i in e2["ids"])
    return dict(row), out


# ----------------------------------------------------------------- verify --

def verify(db_path, rows_and_offsets):
    """For each (run_id, det_id, span_start): the row as it is now, the row as
    it was (after - span_start), and the two signal checks on each."""
    import numpy as np
    conn = _connect_ro(db_path)
    out = []
    cache = {}
    try:
        for run_id, det_id, offset in rows_and_offsets:
            d = conn.execute(
                "SELECT d.start_idx, d.end_idx, d.score, r.span_start, r.span_end, rec.fs, rec.npy_path, "
                "rec.source_file, rec.channel FROM detections d JOIN runs r ON r.id = d.run_id "
                "JOIN recordings rec ON rec.id = r.recording_id WHERE d.id = ?", (det_id,)).fetchone()
            fs = float(d["fs"])
            after = (int(d["start_idx"]), int(d["end_idx"]))
            before = (after[0] - int(offset), after[1] - int(offset))
            span = (int(d["span_start"]), int(d["span_end"]))
            if d["npy_path"] not in cache:
                cache[d["npy_path"]] = np.load(os.path.join(PROJECT_ROOT, d["npy_path"]), mmap_mode="r")
            x = cache[d["npy_path"]]
            out.append({
                "run": run_id, "id": det_id, "recording": "%s CH%d" % (d["source_file"], d["channel"]),
                "before": before, "after": after,
                "before_h": [before[0] / fs / 3600, before[1] / fs / 3600],
                "after_h": [after[0] / fs / 3600, after[1] / fs / 3600],
                "score": d["score"], "length": after[1] - after[0],
                "inside_span": span[0] <= after[0] and after[1] <= span[1],
                "before_check": _signal_check(x, before, span),
                "after_check": _signal_check(x, after, span),
            })
    finally:
        conn.close()
    return out


def _signal_check(x, window, span):
    import numpy as np
    s, e = int(window[0]), int(window[1])
    n = len(x)
    length = max(1, e - s)
    # --- 1. event-likeness: the window's range ranked against every same-length window in the span
    rank = None
    if length < (span[1] - span[0]) and 0 <= s and e <= n:
        seg = np.asarray(x[span[0]:span[1]], dtype=float)
        stride = max(1, length // 4)
        win_len = max(length, 3)
        starts = np.arange(0, len(seg) - win_len + 1, stride)
        if len(starts) >= 20:
            idx = starts[:, None] + np.arange(win_len)[None, :]
            tiles = seg[idx]
            pop = np.nanmax(tiles, axis=1) - np.nanmin(tiles, axis=1)
            pop = pop[np.isfinite(pop)]
            w = np.asarray(x[s:s + win_len], dtype=float)
            mine = float(np.nanmax(w) - np.nanmin(w)) if np.isfinite(w).any() else float("nan")
            if np.isfinite(mine) and len(pop):
                rank = float(np.mean(pop < mine))
    # --- 2. the detrended extremum of a context sits inside the window
    pad = max(PAD_MIN, PAD_FACTOR * length)
    lo, hi = max(0, s - pad), min(n, e + pad)
    ctx = np.asarray(x[lo:hi], dtype=float)
    finite = np.isfinite(ctx)
    extremum = None
    if finite.sum() >= 3:
        t = np.arange(len(ctx), dtype=float)
        a, b = np.polyfit(t[finite], ctx[finite], 1)
        resid = np.abs(ctx - (a * t + b))
        resid[~finite] = -1.0
        k = int(np.argmax(resid)) + lo
        tol = NARROW if length < NARROW else 0
        extremum = {"idx": k, "inside": bool((s - tol) <= k < (e + tol))}
    return {"rank": rank, "event": (rank is not None and rank >= EVENT_PERCENTILE),
            "extremum": extremum}


def print_verify(rows, sample_per_run=3):
    def fmt(c):
        r = "n/a" if c["rank"] is None else "%.2f" % c["rank"]
        ex = "n/a" if c["extremum"] is None else ("yes" if c["extremum"]["inside"] else "no")
        return r, ex
    print("| run | row id | length | before (h) | after (h) | before: rank / holds extremum | after: rank / holds extremum |")
    print("|---|---|---|---|---|---|---|")
    by_run = {}
    for r in rows:
        by_run.setdefault(r["run"], []).append(r)
    for run in sorted(by_run):
        lst = by_run[run]
        pick = lst if len(lst) <= sample_per_run else [lst[0], lst[len(lst) // 2], lst[-1]]
        for r in pick:
            br, be = fmt(r["before_check"])
            ar, ae = fmt(r["after_check"])
            print("| %d | %d | %d | %.4f–%.4f | %.4f–%.4f | %s / %s | %s / %s |" % (
                r["run"], r["id"], r["length"], r["before_h"][0], r["before_h"][1],
                r["after_h"][0], r["after_h"][1], br, be, ar, ae))
    ranked = [r for r in rows if r["after_check"]["rank"] is not None]
    print("all %d rows: after the shift %d of %d rankable windows are event-like (rank >= %.2f), before %d; "
          "the detrended extremum lies inside %d windows after, %d before; %d of %d lie inside their run's span after."
          % (len(rows),
             sum(1 for r in ranked if r["after_check"]["event"]), len(ranked), EVENT_PERCENTILE,
             sum(1 for r in ranked if r["before_check"]["event"]),
             sum(1 for r in rows if r["after_check"]["extremum"] and r["after_check"]["extremum"]["inside"]),
             sum(1 for r in rows if r["before_check"]["extremum"] and r["before_check"]["extremum"]["inside"]),
             sum(1 for r in rows if r["inside_span"]), len(rows)))
    print("per run (after): " + "; ".join(
        "run %d: %d/%d event-like, median rank %s" % (
            run, sum(1 for r in by_run[run] if r["after_check"]["event"]),
            sum(1 for r in by_run[run] if r["after_check"]["rank"] is not None),
            _median_rank(by_run[run]))
        for run in sorted(by_run)))


def _median_rank(lst):
    import numpy as np
    v = [r["after_check"]["rank"] for r in lst if r["after_check"]["rank"] is not None]
    return "n/a" if not v else "%.2f" % float(np.median(v))


# --------------------------------------------------------------- redetect --

def redetect(db_path, rows_and_offsets):
    """Re-run each migrated run's recipe on its span through the adapters
    alone and compare with the rows the database holds now."""
    import inspect
    import numpy as np
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    conn = _connect_ro(db_path)
    out = []
    try:
        for run_id in sorted({r for r, _, _ in rows_and_offsets}):
            r = conn.execute(
                "SELECT r.span_start, r.span_end, c.config_json, rec.fs, rec.npy_path FROM runs r "
                "JOIN configs c ON c.id = r.config_id JOIN recordings rec ON rec.id = r.recording_id "
                "WHERE r.id = ?", (run_id,)).fetchone()
            recipe = json.loads(r["config_json"])
            s0, s1, fs = int(r["span_start"]), int(r["span_end"]), float(r["fs"])
            algo = " -> ".join(s["algorithm"] for s in recipe["steps"])
            migrated = [(int(a), int(b)) for a, b in conn.execute(
                "SELECT start_idx, end_idx FROM detections WHERE run_id = ? ORDER BY start_idx, id", (run_id,))]
            row = {"run": run_id, "recipe": algo, "n_migrated": len(migrated)}
            try:
                x = np.asarray(np.load(os.path.join(PROJECT_ROOT, r["npy_path"]), mmap_mode="r")[s0:s1])
                t = np.arange(s0, s1) / fs
                current_value, fresh = None, None
                for step in recipe["steps"]:
                    spec = get_adapter("%s.%s" % (step["stage"], step["algorithm"]))
                    params = spec.validate_params(step.get("params"))
                    accepted = inspect.signature(spec.run).parameters
                    extra = {}
                    if spec.input_kind is not None and "value" in accepted:
                        extra["value"] = current_value
                    if spec.side_inputs and step.get("side_inputs"):
                        raise ValueError("chain binds side inputs; not re-runnable headlessly here")
                    result = spec.run(x, t, fs, **params, **extra)
                    if result.output_kind == "signal":
                        x = result.value.x
                    elif result.output_kind == "spanset" and spec.input_kind != "spanset":
                        fresh = [(int(a) + s0, int(b) + s0) for a, b in zip(result.value.starts, result.value.ends)]
                    if result.value is not None:
                        current_value = result.value
                fresh_set = set(fresh or [])
                row.update({"n_fresh": len(fresh or []),
                            "exact": sum(1 for m in migrated if m in fresh_set),
                            "near": sum(1 for m in migrated if any(
                                abs(m[0] - f[0]) <= 2 and abs(m[1] - f[1]) <= 2 for f in fresh_set))})
            except Exception as exc:  # a chain this cannot re-run is reported, not hidden
                row.update({"n_fresh": None, "exact": None, "near": None, "error": str(exc)[:200]})
            out.append(row)
    finally:
        conn.close()
    return out


def print_redetect(rows):
    print("| run | recipe | migrated rows | fresh rows | exact matches | within 2 samples |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        if r.get("error"):
            print("| %d | %s | %d | not re-runnable: %s | | |" % (r["run"], r["recipe"], r["n_migrated"], r["error"]))
        else:
            print("| %d | %s | %d | %d | %d | %d |" % (
                r["run"], r["recipe"], r["n_migrated"], r["n_fresh"], r["exact"], r["near"]))


# ------------------------------------------------------------------- main --

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join("DATA", "db", "annotations.sqlite"))
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="back up, check it, and print the plan")
    mode.add_argument("--apply", action="store_true", help="back up, check it, print the plan, migrate, verify")
    mode.add_argument("--verify", action="store_true", help="re-run the signal check on the rows the audit row names")
    mode.add_argument("--redetect", action="store_true",
                      help="re-run each migrated run's recipe on its span (no writes) and compare with the rows")
    ap.add_argument("--out", default=None, help="write everything measured as JSON here")
    args = ap.parse_args()
    db = args.db
    if os.path.islink(db) or os.path.islink(os.path.dirname(os.path.abspath(db))):
        raise SystemExit("refusing: %s is reached through a link" % db)
    if not os.path.isfile(db):
        raise SystemExit("no database at %s" % db)

    result = {"db": os.path.abspath(db), "at": _dt.datetime.now().isoformat(timespec="seconds")}
    if args.verify:
        audit, rows = migrated_rows_from_audit(db)
        result["audit"] = audit
        result["verify"] = verify(db, rows)
        print_verify(result["verify"])
    elif args.redetect:
        audit, rows = migrated_rows_from_audit(db)
        result["audit"] = audit
        result["redetect"] = redetect(db, rows)
        print_redetect(result["redetect"])
    else:
        print("== 1. backup")
        result["backup"] = backup(db)
        print(json.dumps(result["backup"], indent=1))
        print("== 2. dry run")
        d = dry_run(db)
        result["dry_run"] = {"plan": d["plan"], "spanned_runs": d["spanned_runs"],
                             "spanned_runs_with_detections": d["spanned_runs_with_detections"],
                             "before": d["before"]}
        print_plan(d)
        if args.apply and d["plan"]["n_rows"]:
            print("== 3. migrate (through init_db)")
            result["apply"] = apply(db)
            print("audit_log:", json.dumps(result["apply"]["audit"], indent=1, default=str))
            print("second pass plans %d rows" % result["apply"]["second_pass"]["n_rows"])
            print("== 4. verify against the signal")
            rows = [(e["run_id"], i, e["span_start"]) for e in d["plan"]["runs"] for i in e["ids"]]
            result["verify"] = verify(db, rows)
            print_verify(result["verify"])
            print("== 5. re-detect")
            result["redetect"] = redetect(db, rows)
            print_redetect(result["redetect"])
        elif args.apply:
            print("nothing to migrate")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, default=str)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
