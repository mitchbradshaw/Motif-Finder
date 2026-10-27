"""
Read-only event inputs for round-B B3: the drop sequences, the three long `chain_cycles` chains and
the `drop_detection_v1` census, each event measured by the site's own Event shape block.

* **Sequences**: the `sequences` table's 117 machine runs (`source_kind = 'sequence_csv'`, the
  retired Mushroom_260720 run left out). Events and their anchors (onset, trough) are the drop-motif
  store's rows, read by `data.sequence`; Event shape is given those anchors, as the Library's stored
  features are (`event_shape.measure_events(anchors=...)`), on the raw trace in mV.
* **Chains** (W3, `docs/prompts/blocks/reports/W3-evaluation.md`): the `chain_cycles` template's own
  steps on the chain's span — rolling-mean detrend 600 s, `detection.noise_threshold` (4 sigma_n below,
  min 30 s, merge 60 s), Event shape (drops, anatomy search, no anchors) — and the train cut where a
  gap exceeds 3 h (Trains' MaxInterval end gap).
* **Census**: the latest `drop_detection_v1` run with the template's exact parameters per channel of
  M2_aug, M2_concat, CO_fs2 and LM_fs2. A census detection's stored start is a padded window, not the
  onset; the onset is found inside it by Event shape's anatomy search on the detector's own detrended
  trace (rolling_mean_nearest 4916.67 s), as a downstream Event shape step would.

The database is opened `mode=ro`; channel arrays are memory-mapped by `data.load_mv`. The held-out
M4_aug_concat_fs1 recordings (49-64) are refused by `data.recording`.
"""

import functools
import json
import sqlite3

import numpy as np

from Pipelines.fhn import data as D
from Working.interrogation import event_shape as ES
from Working.Preprocessing.detrend import make_detrend_filter
from Working.units import read_as_mv

D._store_rows = functools.lru_cache(maxsize=1)(D._store_rows)     # read the 2 MB store once per process

CHAINS = {
    "rec6_370_470h": dict(recording_id=6, span_h=(370.0, 470.0), w3_events=115,
                          label="rec 6, M2_aug CH6 (stored ch 5), 370-470 h (scalloped; holds seq 3)"),
    "rec3_490_540h": dict(recording_id=3, span_h=(490.0, 540.0), w3_events=116,
                          label="rec 3, M2_aug CH3 (stored ch 2), 490-540 h (sharp drops)"),
    "rec542_370_490h": dict(recording_id=542, span_h=(370.0, 490.0), w3_events=163,
                            label="rec 542, L_LM_Jul_26_J region B (stored ch 2), 10 Hz, 370-490 h"),
}
CHAIN_STEPS = dict(detrend_s=600.0, k_sigma=4.0, min_duration_s=30.0, merge_gap_s=60.0, train_gap_s=10800.0)
CENSUS_CORPORA = {"M2_aug": "M2_aug_concat_fs1.mat", "M2_concat": "M2_concat_fs1.mat", "CO_fs2": "CO_fs2.mat",
                  "LM_fs2": "LM_fs2.mat"}
CENSUS_STEPS = [{"algorithm": "detrend", "params": {"mode": "rolling_mean_nearest", "window_s": 4916.67}},
                {"algorithm": "stage_encoding", "params": {"same_fraction": 0.6, "segment_seconds": 98.33,
                                                           "slope_sigma": 8.0}},
                {"algorithm": "drop_detection", "params": {}}]


def _ro():
    return D._ro()


def machine_sequence_ids():
    with _ro() as c:
        rows = c.execute("select id, recording_id from sequences where source_kind = 'sequence_csv' "
                         "order by id").fetchall()
    return [int(i) for i, r in rows if int(r) != 385 and int(r) not in D.HELD_OUT_RECORDINGS]


def _measure(x_mv, onsets, troughs, fs, anchors=True):
    """Event shape over windows [onset, trough] with the store's anchors (x in mV, to_mv = 1)."""
    on = np.asarray(onsets, int)
    tr = np.asarray(troughs, int)
    feats, _ = ES.measure_events(x_mv, on, tr + 1, fs, polarity="drop", to_mv=1.0,
                                 anchors=list(zip(on, tr)) if anchors else None)
    return feats


def sequence_events(seq_id):
    """One sequence's events measured by Event shape: onsets (s), recovery_time_s, depth (mV), width (s)."""
    seq = D.sequence(seq_id)
    rec = seq["recording"]
    fs = rec["fs"]
    on, tr = seq["onsets"], seq["troughs"]
    width = int(np.max(tr - on)) + 1
    s0 = max(0, int(on[0]) - 10)
    s1 = int(tr[-1] + ES.RECOVERY_MAX_MULT * width + 10)
    x = D.load_mv(rec, s0, s1)
    f = _measure(x, on - s0, tr - s0, fs)
    return dict(kind="sequence", id=seq["id"], key=seq["key"], species=seq["species"], recording_id=rec["id"],
                source_file=rec["source_file"], fs=fs, units=rec["units"], n_events=int(len(on)),
                onset_s=on / fs, recovery_time_s=f["recovery_time_s"].to_numpy(float),
                depth_mv=f["event_amplitude_mv"].to_numpy(float), width_s=f["event_width_s"].to_numpy(float),
                duration_s=f["duration_s"].to_numpy(float), median_gap_s=seq["median_gap_s"],
                member_check=_member_check(seq_id, f["recovery_time_s"].to_numpy(float)))


def _member_check(seq_id, rec_s):
    """The site's stored recovery_time_s for the sequence's members (motif_features), beside ours."""
    with _ro() as c:
        rows = c.execute("""select sm.position, mf.value from sequence_members sm
                            join motif_member mm on mm.id = sm.member_id
                            join motif_features mf on mf.content_hash = mm.content_hash
                            where sm.sequence_id = ? and mf.feature = 'recovery_time_s' order by sm.position""",
                         (int(seq_id),)).fetchall()
    if not rows:
        return dict(n_stored=0)
    stored = np.full(len(rec_s), np.nan)
    for pos, v in rows:
        if 0 <= int(pos) < len(stored) and v is not None:
            stored[int(pos)] = float(v)
    both = np.isfinite(stored) & np.isfinite(rec_s)
    return dict(n_stored=int(np.isfinite(stored).sum()), n_both=int(both.sum()),
                n_equal_1pct=int(np.sum(np.abs(stored[both] - rec_s[both]) <= 0.01 * np.abs(stored[both]) + 1e-9)),
                median_abs_diff_s=float(np.median(np.abs(stored[both] - rec_s[both]))) if both.any() else None)


def _noise_threshold_spans(xd, fs, k, min_dur, merge):
    from Adapters.detection_noise_threshold import _run           # the block itself, not a copy
    res = _run(xd, None, fs, k_sigma=k, direction="below", min_duration_s=min_dur, merge_gap_s=merge)
    return np.asarray(res.value.starts, int), np.asarray(res.value.ends, int)


def chain_events(name, wide_h=48.0):
    """The chain's events by the chain_cycles template's own steps, on its span; plus the onsets of the
    same detector over a span widened by `wide_h` either side (the quiet-window null's exclusion list)."""
    ch = CHAINS[name]
    rec = D.recording(ch["recording_id"])
    fs = rec["fs"]
    factor, _ = read_as_mv(rec["units"])
    s0, s1 = int(ch["span_h"][0] * 3600 * fs), int(ch["span_h"][1] * 3600 * fs)
    x = D.load_mv(rec, s0, s1) / factor                      # the recording's own unit, as the block sees it
    det = make_detrend_filter(fs, "rolling_mean", CHAIN_STEPS["detrend_s"])
    xd = det(x)
    st, en = _noise_threshold_spans(xd, fs, CHAIN_STEPS["k_sigma"], CHAIN_STEPS["min_duration_s"],
                                    CHAIN_STEPS["merge_gap_s"])
    feats, _ = ES.measure_events(xd, st, en, fs, polarity="drop", to_mv=factor)
    ok = np.isfinite(feats["onset_idx"].to_numpy(float))
    on = feats["onset_idx"].to_numpy(float)[ok]
    ex = feats["extremum_idx"].to_numpy(float)[ok]
    order = np.argsort(on)
    out = dict(kind="chain", id=name, key=name, label=ch["label"], recording_id=rec["id"],
               source_file=rec["source_file"], fs=fs, units=rec["units"], n_detections=int(len(st)),
               w3_detections=ch["w3_events"], n_events=int(ok.sum()), span_samples=(s0, s1),
               onset_idx=(on[order] + s0).astype(int), extremum_idx=(ex[order] + s0).astype(int),
               onset_s=(on[order] + s0) / fs,
               recovery_time_s=feats["recovery_time_s"].to_numpy(float)[ok][order],
               depth_mv=feats["event_amplitude_mv"].to_numpy(float)[ok][order],
               width_s=feats["event_width_s"].to_numpy(float)[ok][order],
               duration_s=feats["duration_s"].to_numpy(float)[ok][order],
               max_gap_s=CHAIN_STEPS["train_gap_s"])
    # wide pass for the quiet null (exclusion only)
    w0 = max(0, int((ch["span_h"][0] - wide_h) * 3600 * fs))
    w1 = min(rec["n_samples"], int((ch["span_h"][1] + wide_h) * 3600 * fs))
    xw = det(D.load_mv(rec, w0, w1) / factor)
    sw, ew = _noise_threshold_spans(xw, fs, CHAIN_STEPS["k_sigma"], CHAIN_STEPS["min_duration_s"],
                                    CHAIN_STEPS["merge_gap_s"])
    out["wide_onsets"] = np.sort(sw + w0)
    out["wide_cover"] = (w0, w1)
    return out


def census_runs():
    """{corpus: [(run_id, recording_id, stored channel)]}: the latest exact-template run per channel."""
    out = {}
    with _ro() as c:
        rows = c.execute("""select r.id, r.recording_id, rc.source_file, rc.channel, cf.config_json from runs r
                            join configs cf on cf.id = r.config_id join recordings rc on rc.id = r.recording_id
                            where r.surrogate_of_run_id is null and r.status = 'completed'
                            and r.superseded_at is null order by r.id""").fetchall()
    want = [(s["algorithm"], s["params"]) for s in CENSUS_STEPS]
    for rid, rec_id, src, ch, cj in rows:
        if int(rec_id) in D.HELD_OUT_RECORDINGS:
            continue
        corpus = next((k for k, v in CENSUS_CORPORA.items() if v == src), None)
        if corpus is None:
            continue
        cfg = json.loads(cj)
        if cfg.get("span") and cfg["span"][0] != 0:
            continue
        steps = [(s["algorithm"], s["params"]) for s in cfg.get("steps", [])]
        if steps == want:
            out.setdefault(corpus, {})[int(rec_id)] = (int(rid), int(rec_id), int(ch))
    return {k: [v[r] for r in sorted(v)] for k, v in out.items()}


def census_events(run_id, rec_id):
    rec = D.recording(rec_id)
    fs = rec["fs"]
    with _ro() as c:
        dets = c.execute("select start_idx, end_idx from detections where run_id = ? order by start_idx",
                         (int(run_id),)).fetchall()
    base = dict(kind="census", id=f"run{run_id}", key=f"{rec['source_file']} ch{rec['channel']}", run_id=int(run_id),
                recording_id=rec["id"], source_file=rec["source_file"], fs=fs, units=rec["units"],
                n_detections=len(dets))
    if len(dets) < 3:
        return dict(base, n_events=0, onset_s=np.array([]), recovery_time_s=np.array([]), depth_mv=np.array([]),
                    width_s=np.array([]))
    x = D.load_mv(rec, 0, rec["n_samples"])
    xd = make_detrend_filter(fs, "rolling_mean_nearest", 4916.67)(x)
    st = np.array([d[0] for d in dets], int)
    en = np.array([d[1] for d in dets], int)
    feats, _ = ES.measure_events(xd, st, en, fs, polarity="drop", to_mv=1.0)
    ok = np.isfinite(feats["onset_idx"].to_numpy(float))
    on = feats["onset_idx"].to_numpy(float)[ok]
    order = np.argsort(on)
    pad = (on - st[ok]) / fs
    return dict(base, n_events=int(ok.sum()), onset_s=on[order] / fs,
                recovery_time_s=feats["recovery_time_s"].to_numpy(float)[ok][order],
                depth_mv=feats["event_amplitude_mv"].to_numpy(float)[ok][order],
                width_s=feats["event_width_s"].to_numpy(float)[ok][order],
                median_onset_after_window_start_s=float(np.median(pad)) if pad.size else None)
