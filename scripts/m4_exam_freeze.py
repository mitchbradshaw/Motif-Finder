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

**An unseen recording (2026-10-26).** The same exam for a recording that is NOT held out (the first is Adamatzky's
*Schizophyllum commune*): no lock, the same discipline. Run AFTER its sweep is imported and its candidate-event table
built (`scripts/rq1b_candidate_events.py build --real --file <source>`), BEFORE any sample is drawn:

    python scripts/m4_exam_freeze.py --recording "Schizophyllum commune.txt" --session <its Discovery session id> \
        --table DATA/derived/candidate_events/<table key> --slug scommune
        # writes DATA/derived/exam/scommune/{manifest.json, detectors.json, audit_body.json} and copies the first two
        # to docs/rq_roundA_2/exam/scommune-exam-*.json; --post-audit http://127.0.0.1:8765 also logs the freeze

Its manifest says ``exam: "unseen"`` and freezes, beside what M4's says: the frame (the candidate table's key, run ids
and file hashes: the draw and the marking refuse any other table), the reference CNNs inline in amendment 1's shape
(so no amendment is needed), and the known risks (units and amplitude range). Its freeze is audited as
``candidate_events.EXAM_UNSEEN_FROZEN`` (`audit_body.json`, POSTed to the bridge's ``/api/audit``).

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
import urllib.request

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


# ── an unseen recording (2026-10-26) ────────────────────────────────────────

UNSEEN_SEED = 20261027
UNSEEN_MODELS = ("minirocket_R4", "reference_cnns")
#: the reference CNNs scored on the event sample, as M4's amendment 1 scores them
CNN_CHECKPOINTS = {"GASF": ("MODELS/GASF_cnn.pth", "GASF"), "GADF": ("MODELS/GADF_cnn.pth", "GADF"),
                   "recurrence": ("MODELS/recurrence_cnn.pth", "recurrence"),
                   "fusion": ("MODELS/fusion_cnn_3.pth", "fusion")}
CNN_CODE = ["scripts/rq1b_cnn_vs_minirocket.py", "scripts/rq1b_minirocket.py", "Working/Catalogue/cnn/window_scores.py",
            "Working/Catalogue/cnn/apply_cnn.py", "Working/Catalogue/cnn/cnn_rangapur.py", "Working/units.py",
            "Working/Catalogue/minirocket.py", "Working/distances.py"]
#: whole-signal scale of the R4 training recordings, measured 2026-10-26 (first active channel, first 2 M samples, in
#: mV): the signal's std, and the robust sample-to-sample noise rq1b_minirocket's side feature uses
TRAINING_SCALE_MV = {"M2_aug_concat_fs1 (V, 1 Hz)": {"std": 166.8, "noise": 0.0268},
                     "M2_concat_fs1 (V, 1 Hz)": {"std": 128.6, "noise": 0.0260},
                     "LM_fs2 (V, 2 Hz)": {"std": 81.0, "noise": 0.0420},
                     "CO_fs2 (V, 2 Hz)": {"std": 78.3, "noise": 0.0259},
                     "L_LM_Jul_26_J_raw_fs2 (mV, 2 Hz)": {"std": 51.6, "noise": 0.0084}}


def _rel(path):
    a = os.path.abspath(path)
    try:
        r = os.path.relpath(a, ROOT)
    except ValueError:
        return a
    return a if r.startswith("..") else r.replace(os.sep, "/")


def data_block_of(conn, source_file):
    out = []
    for rid, ch, n, fs, units, p in conn.execute("SELECT id, channel, n_samples, fs, units, npy_path FROM recordings "
                                                 "WHERE source_file = ? AND active = 1 ORDER BY channel",
                                                 (source_file,)):
        path = p if os.path.isabs(p) else os.path.join(ROOT, p)
        out.append({"recording_id": int(rid), "channel": int(ch), "n_samples": int(n), "fs": float(fs),
                    "units": units, "npy_path": p, "sha256": sha256_file(path) if os.path.isfile(path) else None})
    return out


def session_detectors_block(conn, source_file, session_id):
    """Every real template run of Discovery session `session_id` on `source_file`: run, channel, variant, config
    hash; plus a digest per variant (as `detectors_block` for M4, keyed by the session instead of a date)."""
    groups = {int(g): n for g, n in conn.execute(
        "SELECT run_group_id, template_name FROM discovery_runs WHERE session_id = ? AND kind = 'template' "
        "AND run_group_id IS NOT NULL AND removed_at IS NULL", (int(session_id),))}
    marks = ",".join("?" * len(groups)) or "NULL"
    base = ("FROM runs r JOIN configs c ON c.id = r.config_id JOIN recordings rec ON rec.id = r.recording_id "
            f"WHERE rec.source_file = ? AND r.run_group_id IN ({marks}) ")
    rows = conn.execute("SELECT r.id, r.recording_id, rec.channel, r.run_group_id, c.config_hash, r.span_start, "
                        "r.span_end, r.status, r.started_at " + base + "AND r.surrogate_of_run_id IS NULL "
                        "ORDER BY r.id", (source_file, *groups)).fetchall()
    runs = [{"run_id": int(r[0]), "recording_id": int(r[1]), "channel": int(r[2]), "variant": groups.get(int(r[3])),
             "config_hash": r[4], "span": [int(r[5]), int(r[6])], "status": r[7], "started_at": r[8]} for r in rows]
    by_variant = {}
    for r in runs:
        by_variant.setdefault(r["variant"], []).append(r["config_hash"])
    digests = {v: {"n_runs": len(h), "sha256_of_sorted_config_hashes":
                   hashlib.sha256("\n".join(sorted(h)).encode()).hexdigest()} for v, h in sorted(by_variant.items())}
    (n_null,) = conn.execute("SELECT COUNT(*) " + base + "AND r.surrogate_of_run_id IS NOT NULL",
                             (source_file, *groups)).fetchone()
    name = conn.execute("SELECT name FROM discovery_sessions WHERE id = ?", (int(session_id),)).fetchone()
    return {"discovery_session": {"id": int(session_id), "name": name[0] if name else None},
            "n_real_runs": len(runs), "n_surrogate_runs": int(n_null), "variants": digests, "runs": runs}


def frame_block(table_dir, source_file, session_runs):
    """The frozen frame: the candidate-event table the sample is drawn from. Refuses a table of another recording,
    or one holding a run that is not one of the session's (SystemExit, naming the runs)."""
    with open(os.path.join(table_dir, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    if meta.get("source_file") != source_file:
        raise SystemExit(f"{table_dir} is a table of {meta.get('source_file')!r}, not {source_file!r}")
    ids = sorted(int(r["run_id"]) for r in meta.get("runs") or [])
    foreign = sorted(set(ids) - {int(r["run_id"]) for r in session_runs})
    if foreign:
        raise SystemExit(f"{table_dir} holds runs that are not the session's sweep runs: {foreign[:20]}; build the "
                         "table from the imported sweep only (or name the session it came from)")
    return {"table_key": meta["key"], "table_dir": _rel(table_dir), "n_events": int(meta["n_events"]),
            "n_detections": int(meta["n_detections"]), "n_runs": len(ids),
            "runs_sha256": hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest(),
            "families": meta.get("families"), "labels": meta.get("labels"), "rule": meta.get("rule"),
            "excluded_variants": meta.get("excluded_variants"),
            "files": {f: sha256_file(os.path.join(table_dir, f))
                      for f in ("meta.json", "events.parquet", "members.parquet")
                      if os.path.isfile(os.path.join(table_dir, f))}}


def cnn_block():
    """The reference CNNs, in M4 amendment 1's shape (what `m4_exam_score.verify_cnn_files`/`score_cnns` read)."""
    ck = {}
    for name, (path, image_type) in CNN_CHECKPOINTS.items():
        p = os.path.join(ROOT, path)
        ck[name] = {"path": path, "image_type": image_type,
                    "sha256": sha256_file(p) if os.path.isfile(p) else None,
                    "bytes": os.path.getsize(p) if os.path.isfile(p) else None}
    return {
        "as_in": "M4 exam amendment 1 (DATA/derived/exam/M4/amendment-1.json), here part of the frozen manifest",
        "models": {"reference_cnns": ck},
        "input_length": 600,
        "input": ("each answered sample item's anchor span with rq1b_minirocket.PAD (0.25) x its length of context on "
                  "each side, clipped at the recording's ends; in mV (Working.units.read_as_mv); gaps of at most 5 % "
                  "filled linearly, more and the item is not scored; resampled to 600 points by "
                  "window_scores.resample_window; a flat cut is not scored (scripts/rq1b_cnn_vs_minirocket.py "
                  "cuts600)"),
        "score": ("window_scores.window_image (224 px), cnn_rangapur.get_transforms(224, is_train=False, "
                  "is_rgb=(image_type == 'fusion')), window_scores.predict: softmax column 0 = P(interesting); CPU"),
        "population": "the answered items (y in {0,1}) that MiniRocket's extract read AND cuts600 could cut; "
                      "unweighted",
        "metrics": {"cut": 0.5, "primary": ["AUC of P(interesting)", "balanced accuracy at P(interesting) > 0.5"],
                    "secondary": "the same two, design-weighted by N_h / n_h",
                    "ci": f"95 % percentile bootstrap within strata, {N_BOOT} draws, seed 0 "
                          "(m4_exam_score.score_metrics)",
                    "paired": "AUC(CNN) minus AUC(MiniRocket R4) on the same items, within-stratum bootstrap "
                              "(m4_exam_score.paired_auc_difference)"},
        "code": {rel: sha256_file(os.path.join(ROOT, rel)) for rel in CNN_CODE
                 if os.path.isfile(os.path.join(ROOT, rel))},
        "code_rule": "a changed checkpoint sha256 refuses the scoring; a changed code sha256 is reported as a warning",
        "flags": "the CNNs' training data is not recorded (most likely the imported 10-minute M2_aug labels)",
    }


def _channel_scale(conn, source_file):
    import numpy as np
    out = {}
    for ch, units, p in conn.execute("SELECT channel, units, npy_path FROM recordings WHERE source_file = ? AND "
                                     "active = 1 ORDER BY channel", (source_file,)):
        path = p if os.path.isabs(p) else os.path.join(ROOT, p)
        if not os.path.isfile(path):
            continue
        x = np.asarray(np.load(path, mmap_mode="r"), float)
        x = x[np.isfinite(x)] * (1000.0 if units in (None, "", "V") else 1.0)
        if x.size < 2:
            continue
        d = np.diff(x)
        out[f"CH{int(ch)}"] = {"std_mv": round(float(x.std()), 4),
                               "p1_p99_mv": [round(float(v), 4) for v in np.percentile(x, [1, 99])],
                               "noise_mv": round(float(np.median(np.abs(d)) * 1.4826 / np.sqrt(2.0)), 5)}
    return out


def known_risks_block(conn, source_file):
    units = sorted({str(u) for (u,) in conn.execute("SELECT DISTINCT units FROM recordings WHERE source_file = ? "
                                                    "AND active = 1", (source_file,))})
    fs = sorted({float(f) for (f,) in conn.execute("SELECT DISTINCT fs FROM recordings WHERE source_file = ? AND "
                                                   "active = 1", (source_file,))})
    return {
        "units_and_amplitude": {
            "what": ("R4 was trained on recordings stored in V and mV at 1 and 2 Hz (all read as mV by "
                     "Working.units.read_as_mv). This recording is " + "/".join(units) + " at "
                     + "/".join(f"{f:g}" for f in fs) + " Hz from another lab, and its amplitudes are far smaller "
                     "(Adamatzky reports spikes of tenths of a mV to a few mV). R4's side features (log10 duration, "
                     "peak-to-peak mV, noise mV, SNR) may lie outside their training range; its shape features are "
                     "z-normalised, so they are not. Recorded as a known risk; NOTHING is adjusted (no rescaling, no "
                     "recalibration, no threshold change)."),
            "this_recording_mv": _channel_scale(conn, source_file),
            "training_recordings_mv": TRAINING_SCALE_MV,
            "reported_at_scoring": "the answered items' side-feature quantiles (5/50/95 %) beside the metrics",
        },
        "detectors_with_fixed_mv_thresholds": (
            "signal_threshold's mV copies (-2/-5/-10 mV), BEADs' delta_mv 5/25 and any other absolute-mV setting may "
            "find few or no events on a recording of this amplitude: those families' strata may be empty or small "
            "(an empty stratum is reported, never filled from another)"),
        "another_lab": ("electrodes, sampling and preparation differ (Adamatzky's differential needle electrodes); a "
                        "drop in R4's AUC measures transfer to another lab and species, not only to another "
                        "recording"),
    }


def unseen_exposure_block(conn, ids, session_id):
    marks = ",".join("?" * len(ids)) or "NULL"
    reg = conn.execute(f"SELECT MIN(registered_at), MIN(registered_by) FROM recordings WHERE id IN ({marks})",
                       ids).fetchone()
    runs = conn.execute(f"SELECT substr(started_at, 1, 10), COUNT(*) FROM runs WHERE recording_id IN ({marks}) "
                        "GROUP BY 1 ORDER BY 1", ids).fetchall()
    (n_ann,) = conn.execute(f"SELECT COUNT(*) FROM annotations WHERE recording_id IN ({marks})", ids).fetchone()
    (n_adj,) = conn.execute(f"SELECT COUNT(*) FROM adjudications a JOIN detections d ON d.id = a.detection_id "
                            f"JOIN runs r ON r.id = d.run_id WHERE r.recording_id IN ({marks})", ids).fetchone()
    return {"registered": {"at": reg[0], "by": reg[1]}, "runs_by_day": {str(d): int(n) for d, n in runs},
            "annotations": int(n_ann), "adjudications_on_its_detections": int(n_adj),
            "in_training_of_frozen_models": "no (R4's six UQ groups; the CNNs predate its registration)",
            "sweep_session": int(session_id)}


def build_unseen(conn, source_file, *, session_id, table_dir, slug, seed):
    """The unseen-recording exam manifest (the detectors file's sha256 is filled by `main_unseen`)."""
    if source_file == HELD_OUT_RECORDING_FILE:
        raise SystemExit(f"{source_file} is held out: its exam is this script's default (M4) path, not --recording")
    ids = [int(r[0]) for r in conn.execute("SELECT id FROM recordings WHERE source_file = ? AND active = 1 "
                                           "ORDER BY channel", (source_file,))]
    if not ids:
        raise SystemExit(f"no active recordings for {source_file!r}")
    det = session_detectors_block(conn, source_file, session_id)
    if not det["n_real_runs"]:
        raise SystemExit(f"Discovery session {session_id} has no real template runs on {source_file!r}: import the "
                         "sweep (scripts/rq4_overnight.py adopt) and build the candidate table first")
    frame = frame_block(table_dir, source_file, det["runs"])
    design = design_block() | {
        "frame": ("the candidate-event table frozen under 'frame' (Working/discovery/candidate_events.py build_table, "
                  "rules 1-5, the matching rule recorded under 'matching_rule'), built from the sweep runs listed in "
                  "detectors.json; NEGATIVE_CONTROLS excluded as for every table"),
        "seed": int(seed),
        "code": ("scripts/rq1b_candidate_events.py queue --exam-manifest/--exam-sha256: refuses another table, seed or "
                 "quota than this manifest's"),
    }
    models = {k: v for k, v in models_block().items() if k in UNSEEN_MODELS}
    models["reference_cnns"]["scores_on_exam"] = "the candidate-event sample, as M4's amendment 1 (see 'cnns')"
    metrics = metrics_block() | {"outputs": [f"DATA/derived/exam/{slug}/results.json",
                                             f"docs/rq_roundA_2/findings/{slug}-exam-<date>.md"],
                                 "cnns": "the 'cnns' block (amendment 1's design, part of this manifest)"}
    return {
        "exam": ce.EXAM_UNSEEN, "name": f"{os.path.splitext(source_file)[0]} unseen-recording exam (one shot)",
        "slug": f"{slug}-exam", "source_file": source_file, "recording_ids": ids, "held_out": False,
        "frozen": True, "frozen_at": _now(), "git_head": _git_head(),
        "decided": ("researcher, 2026-10-26: a second unseen-recording test on Adamatzky's public recording; sweep, "
                    "import, freeze, one blind stratified sample, judge, score the frozen models once"),
        "matching_rule": rule_from_settings(conn),
        "data": data_block_of(conn, source_file),
        "models": models,
        "cnns": cnn_block(),
        "detectors": {"file": "detectors.json", "sha256": None},
        "frame": frame,
        "sampling_design": design,
        "metrics": metrics,
        "known_risks": known_risks_block(conn, source_file),
        "judging": {"lock": None,
                    "why": (f"{source_file} is not held out: Review shows it everywhere, so the discipline is the "
                            "researcher's"),
                    "protocol": ["Review: open ONLY the exam queue and judge every item; do not open Discovery's "
                                 "Map, Library or any other queue showing this recording until judging is done",
                                 f"then scripts/m4_exam_score.py --real --manifest DATA/derived/exam/{slug}/"
                                 "manifest.json --sha256 <sha256> --sample <sample dir> --queue <queue id> "
                                 "(the database read-only)"]},
        "exposure": unseen_exposure_block(conn, ids, session_id),
        "rules": ["the sample is drawn once (save_sample refuses a different redraw); the draw refuses another table, "
                  "seed or quota than this manifest's",
                  "verdicts are human-only; no script writes one",
                  "a change to this manifest after the sample is drawn voids the exam (its sha256 is in the audit log "
                  "and the RQ logs)",
                  "no model score is computed on the sample before judging; the marking refuses a verdict older than "
                  "the freeze"],
    }


def audit_body(man, man_rel, sha, det_sha, slug):
    """What to POST to the bridge's /api/audit: the freeze, in the sentence the exam's door reads."""
    return {"kind": ce.EXAM_AUDIT_KIND, "what": f"{ce.EXAM_UNSEEN_FROZEN} · {man['source_file']} · sha256 {sha}",
            "where": "Datasets", "route": f"exam/{slug}",
            "detail": {"source_file": man["source_file"], "manifest": man_rel, "sha256": sha,
                       "detectors_sha256": det_sha, "table_key": man["frame"]["table_key"]}}


def post_audit(url, body):
    req = urllib.request.Request(url.rstrip("/") + "/api/audit", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main_unseen(a):
    if a.recording == HELD_OUT_RECORDING_FILE:
        raise SystemExit(f"{a.recording} is held out: its exam is this script's default (M4) path, not --recording")
    if a.session is None or not a.table:
        raise SystemExit("--recording needs --session (the sweep's Discovery session id) and --table (the frame)")
    slug = a.slug or "".join(ch if ch.isalnum() else "_" for ch in os.path.splitext(a.recording)[0]).strip("_")
    out = a.out or os.path.join(ROOT, "DATA", "derived", "exam", slug)
    man_path = os.path.join(out, "manifest.json")
    if os.path.exists(man_path):
        raise SystemExit(f"{man_path} exists: a frozen manifest is never rewritten")
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        man = build_unseen(conn, a.recording, session_id=a.session, table_dir=os.path.abspath(a.table), slug=slug,
                           seed=a.seed)
        det = session_detectors_block(conn, a.recording, a.session)
    finally:
        conn.close()
    os.makedirs(out, exist_ok=True)
    det_path = os.path.join(out, "detectors.json")
    with open(det_path, "w", encoding="utf-8") as fh:
        json.dump(det, fh, indent=1)
    man["detectors"].update(sha256=sha256_file(det_path), n_real_runs=det["n_real_runs"],
                            n_surrogate_runs=det["n_surrogate_runs"], variants=det["variants"],
                            discovery_session=det["discovery_session"])
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    sha = sha256_file(man_path)
    os.makedirs(a.docs, exist_ok=True)
    shutil.copyfile(man_path, os.path.join(a.docs, f"{man['slug']}-manifest.json"))
    shutil.copyfile(det_path, os.path.join(a.docs, f"{man['slug']}-detectors.json"))
    body = audit_body(man, _rel(man_path), sha, man["detectors"]["sha256"], slug)
    body_path = os.path.join(out, "audit_body.json")
    with open(body_path, "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=1)
    report = {"manifest": man_path, "sha256": sha, "detectors_sha256": man["detectors"]["sha256"],
              "n_real_runs": det["n_real_runs"], "frame": man["frame"]["table_key"], "audit_body": body_path}
    if a.post_audit:
        report["audit"] = post_audit(a.post_audit, body)
    else:
        report["next"] = f"POST {body_path} to <bridge>/api/audit BEFORE drawing the sample"
    print(json.dumps(report, indent=1))
    return 0


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
    ap.add_argument("--out", default=None, help="default DATA/derived/exam/M4 (exam/<slug> with --recording)")
    ap.add_argument("--docs", default=DOCS)
    ap.add_argument("--recording", help="an UNSEEN recording's source file (not held out): its exam manifest")
    ap.add_argument("--session", type=int, help="with --recording: the Discovery session its sweep was imported into")
    ap.add_argument("--table", help="with --recording: the candidate-event table folder (the frame)")
    ap.add_argument("--slug", help="with --recording: the exam's short name (folder and file names)")
    ap.add_argument("--seed", type=int, default=UNSEEN_SEED, help=f"with --recording (default {UNSEEN_SEED})")
    ap.add_argument("--post-audit", metavar="BRIDGE_URL",
                    help="with --recording: POST the freeze to <bridge>/api/audit (else write audit_body.json only)")
    a = ap.parse_args(argv)
    if a.recording:
        return main_unseen(a)
    a.out = a.out or OUT
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
