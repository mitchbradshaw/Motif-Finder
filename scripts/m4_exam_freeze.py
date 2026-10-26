"""
m4_exam_freeze.py
=================
The held-out M4 exam (2026-10-26), step 1: write the FROZEN exam manifest before any sample is drawn.

In plain words: before the exam paper is printed, we write down — and fingerprint — exactly which models will sit it,
which detector settings made the candidate events, how the questions will be picked, and how the answers will be
marked. The fingerprint (sha256) of that page goes into the RQ logs and the audit log, so nobody (us included) can
quietly change the rules after seeing the answers.

    python scripts/m4_exam_freeze.py            # writes DATA/derived/exam/M4/{manifest.json, detectors.json}
                                                # and copies both to docs/rq_roundA_2/exam/

The database is opened READ-ONLY. Refuses to overwrite an existing manifest: a frozen manifest is never rewritten.
Headless; no UI library.
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.discovery import candidate_events as ce  # noqa: E402
from Working.discovery.matching import rule_from_settings  # noqa: E402

REAL_DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "DATA", "derived", "exam", "M4")
DOCS = os.path.join(ROOT, "docs", "rq_roundA_2", "exam")

SEED = 20261026
PER_LEVEL = 40
PER_FAMILY = 15
N_BOOT = 2000

MODELS = {
    "minirocket_R4": {
        "dir": "DATA/derived/models/rq1b_minirocket/20261020-2343",
        "files": ["model.joblib", "manifest.json", "predictions.parquet"],
        "script": "scripts/rq1b_minirocket.py",
        "write_up": "docs/rq_roundA_2/findings/rq1b-minirocket-2026-10-20.md",
        "scores_on_exam": "the candidate-event sample (this exam): decision() > 0 is 'interesting'",
    },
    "random_forest_run79": {
        "dir": "DATA/derived/training/paired_68f57f69_run79",
        "files": ["paired_68f57f69_armA.joblib", "paired_68f57f69_armB.joblib", "results.json"],
        "scores_on_exam": "exam (iii) windows only; NOT scored on this event sample (see exam_iii)",
    },
    "cluster_label_forest_run1613": {
        "dir": "DATA/derived/training/shape_forest_9eccf73f_run1613",
        "files": ["forest_b2.joblib", "results.json", "predictions.parquet", "blind_sample.json",
                  "blind_reference.json"],
        "scores_on_exam": "exam (iii) windows only; NOT scored on this event sample (see exam_iii)",
    },
    "reference_cnns": {
        "dir": "MODELS",
        "files": ["GASF_cnn.pth", "GASF_cnn.pth.manifest.json", "GADF_cnn.pth", "GADF_cnn.pth.manifest.json",
                  "recurrence_cnn.pth", "recurrence_cnn.pth.manifest.json", "fusion_cnn_3.pth",
                  "fusion_cnn_3.pth.manifest.json", "GASF_checkpoint.pth", "GADF_checkpoint.pth",
                  "recurrence_checkpoint.pth", "fusion_prediction_checkpoint.pth", "fusion_prediction_cnn.pth",
                  "fusion_cnn.pth", "fusion_cnn_2.pth"],
        "write_up": "docs/prompts/blocks/reports/W4-A-evaluation.md",
        "scores_on_exam": "exam (iii) windows only; NOT scored on this event sample (see exam_iii)",
    },
}


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _git_head():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance only
        return None


def models_block():
    out = {}
    for name, m in MODELS.items():
        files = {}
        for f in m["files"]:
            p = os.path.join(ROOT, m["dir"], f)
            if os.path.isfile(p):
                files[f] = {"sha256": sha256_file(p), "bytes": os.path.getsize(p)}
            else:
                files[f] = {"sha256": None, "missing": True}
        out[name] = {k: v for k, v in m.items() if k != "files"} | {"files": files}
    return out


def detectors_block(conn):
    """Every real 2026-10-19 sweep run on M4: run, channel, template variant, config hash; plus a digest per variant."""
    rows = conn.execute(
        "SELECT r.id, r.recording_id, rec.channel, r.run_group_id, c.config_hash, r.span_start, r.span_end, r.status, "
        "r.started_at FROM runs r JOIN configs c ON c.id = r.config_id JOIN recordings rec ON rec.id = r.recording_id "
        "WHERE rec.source_file = ? AND r.started_at LIKE '2026-10-19%' AND r.surrogate_of_run_id IS NULL "
        "ORDER BY r.id", (HELD_OUT_RECORDING_FILE,)).fetchall()
    names = {int(g): n for g, n in conn.execute(
        "SELECT run_group_id, template_name FROM discovery_runs WHERE session_id = 7 AND kind = 'template'")}
    runs = [{"run_id": int(r[0]), "recording_id": int(r[1]), "channel": int(r[2]), "variant": names.get(int(r[3])),
             "config_hash": r[4], "span": [int(r[5]), int(r[6])], "status": r[7], "started_at": r[8]} for r in rows]
    by_variant = {}
    for r in runs:
        by_variant.setdefault(r["variant"], []).append(r["config_hash"])
    digests = {v: {"n_runs": len(h), "sha256_of_sorted_config_hashes":
                   hashlib.sha256("\n".join(sorted(h)).encode()).hexdigest()} for v, h in sorted(by_variant.items())}
    n_null = conn.execute(
        "SELECT COUNT(*) FROM runs r JOIN recordings rec ON rec.id = r.recording_id WHERE rec.source_file = ? "
        "AND r.started_at LIKE '2026-10-19%' AND r.surrogate_of_run_id IS NOT NULL",
        (HELD_OUT_RECORDING_FILE,)).fetchone()[0]
    return {"discovery_session": {"id": 7, "name": "M4_aug_concat_fs1_rq4"}, "n_real_runs": len(runs),
            "n_surrogate_runs": int(n_null), "variants": digests, "runs": runs}


def data_block(conn):
    out = []
    for rid, ch, n, fs, p in conn.execute("SELECT id, channel, n_samples, fs, npy_path FROM recordings "
                                          "WHERE source_file = ? ORDER BY channel", (HELD_OUT_RECORDING_FILE,)):
        path = p if os.path.isabs(p) else os.path.join(ROOT, p)
        out.append({"recording_id": int(rid), "channel": int(ch), "n_samples": int(n), "fs": float(fs),
                    "npy_path": p, "sha256": sha256_file(path) if os.path.isfile(path) else None})
    return out


def exposure_block():
    return {
        "summary": ("M4 was declared held out in the thesis plan (Aug 2026) but was touched twice before this exam; "
                    "the thesis discloses both."),
        "runs": {"total": 1275,
                 "2026-08-04": {"n": 11, "what": "pipeline smoke on channel 0, samples 747652-764509 (bandpass, "
                                "dehshibi_spikes x2, lowpass x5, two gramian catalogue runs; 5 failed)"},
                 "2026-10-19": {"n": 1264, "real": 632, "surrogates": 632,
                                "what": "RQ4b detector sweep batch 2 (43 template settings x 16 channels, each with "
                                        "a phase-randomised null), imported into Discovery session 7 via "
                                        "scripts/rq4_overnight.py adopt"}},
        "annotations": [{"id": 11298, "recording_id": 49, "channel": 0, "start": 748871, "end": 763617,
                         "verdict": "interesting", "source": "manual_ui", "created_at": "2026-08-04"}],
        "adjudications_on_M4_detections": 0,
        "motif_entry_or_member_rows": 0,
        "models_trained_on_M4": "none (Working/training refuses it; exam (iii) is a 'locked' slot in "
                                "Working/training/paired.py EXAM_III)",
        "lock_history": [{"audit_log_id": 519, "at": "2026-10-17T05:02:50Z", "what": "Held-out lock turned off"},
                         {"audit_log_id": 536, "at": "2026-10-25T22:34:13Z", "what": "Held-out lock turned on"}],
        "detector_outputs_seen": ("the 2026-10-19 sweep's detections were written to the DB and counted by the RQ4b "
                                  "write-up's batch tables; no human verdict was given on any of them"),
    }


def design_block():
    return {
        "frame": ("the M4 candidate-event table built by Working/discovery/candidate_events.py build_table (rules 1-5, "
                  "the matching rule from Settings > Analysis defaults as recorded under 'matching_rule'), from the "
                  "2026-10-19 sweep runs listed in detectors.json; NEGATIVE_CONTROLS excluded as for every table"),
        "eligible": "events with no existing label (rule 6): the frame is every unjudged event, conflicts included",
        "strata": {"selective_families_first": list(ce.SELECTIVE_FAMILIES),
                   "agreement_levels": [list(x) for x in ce.AGREEMENT_LEVELS],
                   "rule": "first selective family among an event's own detectors, else its agreement level"},
        "per_level": PER_LEVEL, "per_family": PER_FAMILY, "seed": SEED,
        "as_in": "review queue 28 (per_level 40, per_family 15)",
        "expected_n": "<= 5*40 + 6*15 = 290 (fewer when a stratum's frame is smaller than its quota)",
        "weights": "N_h / n_h (rule 6), recomputed over answered items per stratum (rule 7)",
        "serving": "one blind Review queue over each sampled event's anchor detection, served in the seeded random "
                   "order (serve_rank); the queue shows no detector name, agreement count, distance or model score",
        "code": "scripts/rq1b_candidate_events.py build/queue with --exam-manifest/--exam-sha256 (the exam path)",
    }


def metrics_block():
    return {
        "verdict_source": ("adjudications on the sample's anchor detections whose row is the researcher's own "
                           "(carried_from IS NULL) AND whose detection appears as a target of a not-undone 'verdict' "
                           "row of review_audit for the exam queue. Carried copies and verdicts from any other queue "
                           "are not counted; such items count as unanswered and are reported."),
        "y": {"interesting": 1, "not_interesting": 0, "artifact": 0, "unsure": "excluded (counted)"},
        "estimated_share_real": "candidate_events.estimate group 'all': weighted precision with the 95 % "
                                "within-stratum bootstrap interval",
        "agreement_ladder": "candidate_events.estimate groups 'agree:1-2' ... 'agree:9+'",
        "per_detector_precision": "candidate_events.estimate groups 'family:*' and 'variant:*'",
        "estimate_n_boot": N_BOOT, "estimate_seed": 0,
        "minirocket": {
            "model": "minirocket_R4 model.joblib (sha256 above), loaded with scripts/rq1b_minirocket.load_model",
            "input": "each sampled event's anchor span (sample start/end), read with rq1b_minirocket.extract "
                     "(pad 0.25, length the model's own), side features as at training",
            "score": "rq1b_minirocket.decision (ridge decision); positive = decision > 0",
            "primary": ["AUC (roc_auc_score on decision)", "balanced accuracy at decision > 0"],
            "population": "answered sample items with y in {0,1} that extract() could read; unweighted (each judged "
                          "event counts once), as RQ1b's queue_samples robustness row",
            "secondary": "the same two metrics design-weighted by N_h / n_h (weighted AUC and weighted recalls)",
            "ci": f"95 % percentile bootstrap, resampling answered items within strata, {N_BOOT} draws, seed 0",
            "comparator": "the event's agreement count n_agree as a score (AUC), as RQ1b's agreement_context",
            "when": "computed only AFTER judging, by scripts/m4_exam_score.py; no model score is computed or looked "
                    "at on the sample before then",
        },
        "outputs": ["DATA/derived/exam/M4/results.json", "docs/rq_roundA_2/findings/m4-exam-<date>.md"],
    }


def exam_iii_block():
    return {"prepared": False,
            "why": ("the blind random-window mechanism (Working/training/blind.py, table blind_test_labels, RQ1 queue "
                    "3) refuses M4 by design and lives in Working/training, another agent's area; opening it is more "
                    "than a small change. The forests and CNNs above are frozen by hash here so a later exam (iii) "
                    "can name them."),
            "planned": "about 200 ten-minute windows (+30-minute ones if needed) on M4, blind, via blind_test_labels"}


def judging_protocol_block():
    return {
        "review_hides_held_out_when_locked": True,
        "evidence": "webui/server/review.py _held_out_ids / _refuse_held_out: while heldout.on is true, held-out "
                    "recordings' items are excluded from every queue and verdicts on them are refused (no exam "
                    "exemption exists)",
        "protocol": [
            "Settings > Datasets: turn the held-out lock OFF (type M4_aug_concat_fs1); audited ('lock')",
            "Review: open ONLY the exam queue; judge every item; open no other page or queue that shows M4",
            "Settings > Datasets: turn the lock back ON straight after; audited ('lock')",
            "run scripts/m4_exam_score.py --real (reads the DB read-only)",
        ],
    }


def build(conn):
    return {
        "exam": "held_out", "name": "M4 held-out exam (one shot)", "source_file": HELD_OUT_RECORDING_FILE,
        "recording_ids": list(range(49, 65)), "frozen": True, "frozen_at": _now(), "git_head": _git_head(),
        "decided": "researcher, 2026-10-26: lock back on, freeze in writing, one blind stratified exam",
        "matching_rule": rule_from_settings(conn),
        "data": data_block(conn),
        "models": models_block(),
        "detectors": {"file": "detectors.json", "sha256": None},
        "sampling_design": design_block(),
        "metrics": metrics_block(),
        "exam_iii": exam_iii_block(),
        "judging": judging_protocol_block(),
        "exposure": exposure_block(),
        "rules": ["the sample is drawn once (save_sample refuses a different redraw)",
                  "verdicts are human-only; no script writes one",
                  "a change to this manifest after the sample is drawn voids the exam (its sha256 is in the audit "
                  "log and the RQ logs)"],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=REAL_DB)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--docs", default=DOCS)
    a = ap.parse_args(argv)
    man_path = os.path.join(a.out, "manifest.json")
    if os.path.exists(man_path):
        raise SystemExit(f"{man_path} exists: a frozen manifest is never rewritten")
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        det = detectors_block(conn)
        man = build(conn)
    finally:
        conn.close()
    os.makedirs(a.out, exist_ok=True)
    det_path = os.path.join(a.out, "detectors.json")
    with open(det_path, "w", encoding="utf-8") as fh:
        json.dump(det, fh, indent=1)
    man["detectors"]["sha256"] = sha256_file(det_path)
    man["detectors"]["n_real_runs"] = det["n_real_runs"]
    man["detectors"]["variants"] = det["variants"]
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    os.makedirs(a.docs, exist_ok=True)
    shutil.copyfile(man_path, os.path.join(a.docs, "M4-exam-manifest.json"))
    shutil.copyfile(det_path, os.path.join(a.docs, "M4-exam-detectors.json"))
    print(json.dumps({"manifest": man_path, "sha256": sha256_file(man_path), "detectors_sha256":
                      man["detectors"]["sha256"], "n_real_runs": det["n_real_runs"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
