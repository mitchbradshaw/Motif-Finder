"""
rq1b_candidate_events.py
========================
Round A_2, RQ1b / RQ4b: the RQ4b sweep's detections merged into candidate events, a stratified sample of the
unjudged ones put to Review, and the precision estimates from the answers. The rules are
`Working/discovery/candidate_events.py`'s; this is the handle on them.

    build     the candidate-event table of one recording: the database opened READ-ONLY, the table written to
              disk (--out, default <main checkout>/DATA/derived/candidate_events/<key>/)
    queue     the stratified sample of the events nobody has judged yet (your existing verdicts are training data
              and are never asked again). A DRY RUN by default: it prints the strata and writes nothing. --apply
              saves the sample beside the table and creates ONE blind Review queue over it, served shuffled;
              applying the same sample again returns the same queue
    estimate  the precision per agreement level, per detector family and per setting, from the answers so far
              (read-only; the estimate is written to the sample's folder as estimate.json)

The REAL database (the main checkout's DATA/db/annotations.sqlite) is named only with --real, and --real takes no
--db: a --db naming it by any other spelling is refused (the guard is scripts/backfill_seed_entry_ids.py's, imported,
not copied).

    python scripts/rq1b_candidate_events.py build --db <copy>.sqlite --out <dir>              # a sandbox copy
    python scripts/rq1b_candidate_events.py build --real                                      # M2_aug, the real one
    python scripts/rq1b_candidate_events.py queue --table <table dir> --real                  # dry run
    python scripts/rq1b_candidate_events.py queue --table <table dir> --real --apply          # the queue
    python scripts/rq1b_candidate_events.py estimate --sample <table dir>/sample_seed0_l100_f50 --real

M4_aug (the held-out exam) is refused by name, whatever Settings › Datasets' lock says.
"""

import argparse
import importlib.util
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.discovery import candidate_events as ce  # noqa: E402


def _guard():
    """`scripts/backfill_seed_entry_ids.py`'s real-database guard, loaded from its file (scripts/ is not a
    package): one guard for every script that can write the real database."""
    spec = importlib.util.spec_from_file_location("_rq1b_real_db_guard",
                                                  os.path.join(ROOT, "scripts", "backfill_seed_entry_ids.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GUARD = _guard()
DEFAULT_FILE = "M2_aug_concat_fs1.mat"
DEFAULT_OUT = os.path.join(GUARD.main_checkout(), "DATA", "derived", "candidate_events")


def _db_options(p, *, can_apply):
    p.add_argument("--db", help="the sqlite file (never the real one: that is --real)")
    p.add_argument("--real", action="store_true", help="the real database, deliberately (takes no --db)")
    if can_apply:
        p.add_argument("--apply", action="store_true", help="write (without it: a dry run that writes nothing)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")


def _database(ap, a, real):
    if a.db and a.real:
        ap.error("give --db or --real, not both: --real is the real database, --db any other file")
    db = real if a.real else a.db
    if not db:
        ap.error("name a database with --db, or pass --real for the real one")
    if not a.real and GUARD.is_the_real_database(db, real):
        ap.error(f"{db} is the real database ({real}); pass --real, and no --db, to use it deliberately")
    if not os.path.isfile(db):
        ap.error(f"no database at {db}")
    return db


def _read_only(db):
    conn = GUARD._read_only(db)
    conn.row_factory = sqlite3.Row
    return conn


def _print(report, as_json):
    if as_json:
        print(json.dumps(report, indent=1, default=str))
        return
    for k, v in report.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for kk, vv in v.items():
                print(f"  {kk}: {vv}")
        else:
            print(f"{k}: {v}")


def _levels(events):
    lv = events["n_agree"].map(lambda n: ce.level_of(int(n)))
    return {k: int(v) for k, v in lv.value_counts().sort_index().items()}


def _build(a, db):
    conn = _read_only(db)
    try:
        events, members, meta = ce.build_table(conn, a.file)
    finally:
        conn.close()
    meta["database"] = os.path.abspath(db)
    where = ce.save_table(a.out, events, members, meta)
    fam = members.groupby("family")["event_id"].nunique().sort_values(ascending=False)
    return {"table": where, "source_file": meta["source_file"], "n_detections": meta["n_detections"],
            "n_events": meta["n_events"], "excluded_variants": meta["excluded_variants"],
            "skipped_runs": len(meta["skipped"]), "labels": meta["labels"], "agreement_levels": _levels(events),
            "events_found_per_family": {k: int(v) for k, v in fam.items()}, "rule": meta["rule"]}


def _sample_name(a):
    return f"sample_seed{int(a.seed)}_l{int(a.per_level)}_f{int(a.per_family)}"


def _queue(a, db):
    events, members, meta = ce.load_table(a.table)
    if a.apply:
        conn, held = GUARD._open_for_apply(db)
    else:
        conn, held = _read_only(db), []
    try:
        events = ce.attach_labels(conn, events, members)       # the labels as they stand now: the frame is current
        sample = ce.draw_sample(events, seed=a.seed, per_level=a.per_level, per_family=a.per_family)
        strata = {h: {"frame": int(g["frame_size"].iloc[0]), "sampled": int(len(g)),
                      "weight": float(g["weight"].iloc[0])} for h, g in sample.groupby("stratum")}
        report = {"applied": bool(a.apply), "table": os.path.abspath(a.table), "n_sampled": int(len(sample)),
                  "labels_now": ce.label_counts(events), "strata": strata, "sample": None, "queue_id": None}
        if a.apply:
            name = a.name or (f"RQ1b candidate events · {meta['source_file']} · stratified sample · seed {a.seed}")
            smeta = {"name": _sample_name(a), "table_key": meta["key"], "source_file": meta["source_file"],
                     "seed": int(a.seed), "per_level": int(a.per_level), "per_family": int(a.per_family),
                     "levels": [list(x) for x in ce.AGREEMENT_LEVELS], "selective": list(ce.SELECTIVE_FAMILIES),
                     "strata": strata, "database": os.path.abspath(db), "created_at": ce._now()}
            labels = events[["event_id", "label", "label_kind", "label_refs", "inside_interesting"]]
            where = ce.save_sample(a.table, sample, labels, smeta)
            qid = ce.create_sample_queue(conn, sample, name=name, note=f"rq1b-sample:{meta['key']}:{smeta['name']}")
            smeta["queue_id"] = qid
            ce._atomic_json(os.path.join(where, "meta.json"), smeta)
            report.update(sample=where, queue_id=qid, queue_name=name)
        if held:
            report["migration_messages_held"] = len(held)
    finally:
        conn.close()
    return report


def _estimate(a, db):
    sample, labels, smeta = ce.load_sample(a.sample)
    table = os.path.dirname(os.path.abspath(a.sample))
    events, members, meta = ce.load_table(table)
    if meta["key"] != smeta["table_key"]:
        raise SystemExit(f"{a.sample} was drawn from table {smeta['table_key']}, not {meta['key']}")
    events = events.drop(columns=["label", "label_kind", "label_refs", "inside_interesting"]).merge(
        labels, on="event_id", how="left")
    conn = _read_only(db)
    try:
        ce.check_sample_against(conn, sample)
        verdicts = ce.read_sample_verdicts(conn, sample)
    finally:
        conn.close()
    est = ce.estimate(events, members, sample, verdicts, n_boot=a.n_boot, seed=0)
    est.update(sample=os.path.abspath(a.sample), queue_id=smeta.get("queue_id"), source_file=smeta["source_file"],
               rule=meta["rule"], created_at=ce._now())
    ce._atomic_json(os.path.join(a.sample, "estimate.json"), est)
    return est


def main(argv=None, real=None):
    """`real`: the real database's path (the main checkout's by default); a test hands in a stand-in."""
    real = real or GUARD.REAL_DB
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="the candidate-event table of one recording (read-only)")
    _db_options(b, can_apply=False)
    b.add_argument("--file", default=DEFAULT_FILE, help=f"the recording's source file (default {DEFAULT_FILE})")
    b.add_argument("--out", default=DEFAULT_OUT, help="the folder the table's own folder goes in")
    qp = sub.add_parser("queue", help="the stratified sample and its Review queue (dry run unless --apply)")
    _db_options(qp, can_apply=True)
    qp.add_argument("--table", required=True, help="a table folder `build` wrote")
    qp.add_argument("--seed", type=int, default=0)
    qp.add_argument("--per-level", type=int, default=ce.DEFAULT_PER_LEVEL)
    qp.add_argument("--per-family", type=int, default=ce.DEFAULT_PER_FAMILY)
    qp.add_argument("--name", help="the queue's name in Review")
    e = sub.add_parser("estimate", help="precision estimates from the sample's answers so far (read-only)")
    _db_options(e, can_apply=False)
    e.add_argument("--sample", required=True, help="a sample folder `queue --apply` wrote")
    e.add_argument("--n-boot", type=int, default=1000)
    a = ap.parse_args(argv)
    db = _database(ap, a, real)
    report = {"build": _build, "queue": _queue, "estimate": _estimate}[a.cmd](a, db)
    _print(report, a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
