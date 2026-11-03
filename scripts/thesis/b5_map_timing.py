"""B5 for Chapter 10: what do the Discovery Maps show about when and where the detectors fire?

In plain words: the Map shades how often each detector fires on each channel, and its channel level shows that per
3-hour bin across a whole recording. If the detectors respond to the same changes in the signal, their rates rise and
fall together over hours and days: bursts of agreement and quiet stretches. If channels follow a shared driver, the
channels rise and fall together. Two nulls:
- shifting each series in time by a random amount, which keeps each detector's own rate pattern and breaks only the
  alignment;
- the paired phase-randomised surrogate run that the sweep made beside every real run, which keeps the signal's
  spectrum and scrambles its timing.

The real counts are binned exactly as the Map's channel level bins them (`Working.discovery.detection_map
.timeline_map`: detections by start sample in `bin_h`-hour bins from the recording's start). The script checks that
against the Map's own payload for one channel. The surrogate runs, which the Map does not draw, are binned the same
way from the database. Read-only throughout.

Per channel: co-modulation C, the mean pairwise Spearman correlation between the settings' binned counts, against
`draws` random circular shifts per setting (p = (1 + shifts with C >= observed) / (draws + 1)); the same for the
surrogate runs. Per recording: channel bands, the mean pairwise Spearman correlation between channels' summed
(z-scored) rates, against independent shifts per channel.

    python scripts/thesis/b5_map_timing.py      # writes docs/thesis/data/ch10_b5/
"""
import argparse
import json
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b5")
RECORDINGS = ["M2_aug_concat_fs1.mat", "M2_concat_fs1.mat", "CO_fs2.mat", "LM_fs2.mat", "L_LM_Jul_26_J_raw.mat"]


def bin_counts(starts, n_samples, fs, bin_h):
    """Detections per `bin_h`-hour bin by start sample, the Map's level-1 binning."""
    n_bins = max(1, int(np.ceil(n_samples / fs / 3600.0 / bin_h - 1e-9)))
    edges = [min(n_samples, int(round(i * bin_h * 3600.0 * fs))) for i in range(n_bins + 1)]
    edges[-1] = n_samples
    return np.histogram(np.asarray(starts, dtype=float), bins=np.asarray(edges, dtype=float))[0]


def _ranks(M):
    """Average ranks along each row: counts tie a lot (zeros above all), and Spearman needs ties shared."""
    from scipy.stats import rankdata
    return rankdata(M, axis=1).astype(float)


def comodulation(M):
    """Mean pairwise Spearman correlation between rows; rows with no variation are left out."""
    M = np.asarray(M, dtype=float)
    M = M[np.std(M, axis=1) > 0]
    if len(M) < 2:
        return float("nan")
    R = _ranks(M)
    R = (R - R.mean(axis=1, keepdims=True)) / R.std(axis=1, keepdims=True)
    C = (R @ R.T) / R.shape[1]
    iu = np.triu_indices(len(M), 1)
    return float(C[iu].mean())


def shift_null(M, draws=200, rng=None):
    """Co-modulation with every row rolled by its own random offset, `draws` times."""
    rng = rng or np.random.default_rng(0)
    M = np.asarray(M)
    n = M.shape[1]
    out = np.empty(draws)
    for d in range(draws):
        out[d] = comodulation(np.array([np.roll(row, int(rng.integers(1, n))) for row in M]))
    return out


def _zrows(M):
    M = np.asarray(M, dtype=float)
    M = M[np.std(M, axis=1) > 0]
    return (M - M.mean(axis=1, keepdims=True)) / M.std(axis=1, keepdims=True)


def _runs(conn, source_file):
    """The newest live real run per (channel, setting) that has a paired surrogate, with that surrogate's id."""
    rows = conn.execute(
        "SELECT r.id, r.recording_id, dr.template_name, "
        "(SELECT MIN(s.id) FROM runs s WHERE s.surrogate_of_run_id = r.id AND s.status = 'completed') AS sur "
        "FROM runs r JOIN recordings rec ON rec.id = r.recording_id "
        "JOIN discovery_runs dr ON dr.run_group_id = r.run_group_id AND dr.superseded_at IS NULL "
        "AND dr.kind = 'template' AND dr.template_name IS NOT NULL "
        "WHERE rec.source_file = ? AND r.status = 'completed' AND r.superseded_at IS NULL "
        "AND r.surrogate_of_run_id IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM stitched_windows sw WHERE sw.window_run_id = r.id) "
        "ORDER BY r.id", (source_file,)).fetchall()
    pick = {}
    for rid, rec, tpl, sur in rows:
        if sur is not None:
            pick[(rec, tpl)] = (rid, sur)                      # ordered by id: the newest wins
    return pick


def _starts(conn, run_id):
    return np.array([r[0] for r in conn.execute("SELECT start_idx FROM detections WHERE run_id = ?", (int(run_id),))])


def read_recording(conn, source_file, bin_h=3.0, draws=200, seed=20261103):
    chans = conn.execute("SELECT id, channel, fs, n_samples FROM recordings WHERE source_file = ? ORDER BY channel",
                         (source_file,)).fetchall()
    pick = _runs(conn, source_file)
    rng = np.random.default_rng(seed)
    per_channel, totals_real, totals_sur, real_by_channel = [], [], [], {}
    for rec_id, ch, fs, n in chans:
        tpls = sorted(t for (r, t) in pick if r == rec_id)
        if len(tpls) < 2:
            continue
        R = np.array([bin_counts(_starts(conn, pick[(rec_id, t)][0]), n, fs, bin_h) for t in tpls])
        S = np.array([bin_counts(_starts(conn, pick[(rec_id, t)][1]), n, fs, bin_h) for t in tpls])
        real_by_channel[rec_id] = dict(zip(tpls, R))
        cr, cs = comodulation(R), comodulation(S)
        nr, ns = shift_null(R, draws, rng), shift_null(S, draws, rng)
        per_channel.append({"recording_id": int(rec_id), "channel": int(ch), "settings": len(tpls), "bins": R.shape[1],
                            "real_C": cr, "real_shift_mean": float(np.nanmean(nr)),
                            "real_p": (1 + int(np.sum(nr >= cr))) / (draws + 1),
                            "sur_C": cs, "sur_shift_mean": float(np.nanmean(ns)),
                            "sur_p": (1 + int(np.sum(ns >= cs))) / (draws + 1),
                            "quiet_bins_real": float(np.mean(R.sum(axis=0) == 0)),
                            "quiet_bins_sur": float(np.mean(S.sum(axis=0) == 0))})
        totals_real.append(_zrows(R).mean(axis=0))
        totals_sur.append(_zrows(S).mean(axis=0))
    bands = {}
    for name, T in (("real", np.array(totals_real)), ("surrogate", np.array(totals_sur))):
        if len(T) >= 2:
            c = comodulation(T)
            nl = shift_null(T, draws, rng)
            bands[name] = {"C": c, "shift_mean": float(np.nanmean(nl)), "p": (1 + int(np.sum(nl >= c))) / (draws + 1)}
    return {"source_file": source_file, "channels": per_channel, "bands": bands,
            "timecourse_real": np.median(np.array(totals_real), axis=0).tolist() if totals_real else [],
            "timecourse_sur": np.median(np.array(totals_sur), axis=0).tolist() if totals_sur else [],
            "bin_h": bin_h, "draws": draws}, real_by_channel


def check_against_map(real_by_channel, map_payload):
    """The Map's own channel-level counts against this script's binning, per setting: (agree, compared)."""
    rid = int(map_payload["recordingId"])
    mine = real_by_channel.get(rid, {})
    agree = compared = 0
    for row in map_payload["rows"]:
        t = row.get("template")
        cell = map_payload["cells"].get(row["key"])
        if not t or t not in mine or not cell or cell.get("state") != "covered":
            continue
        compared += 1
        agree += int(list(map(int, cell["counts"])) == mine[t].astype(int).tolist())
    return agree, compared


def _figure(results, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(len(results), 1, figsize=(7.2, 1.45 * len(results) + 0.6), sharex=False)
    for ax, r in zip(np.atleast_1d(axes), results):
        t = np.arange(len(r["timecourse_real"])) * r["bin_h"]
        ax.plot(t, r["timecourse_real"], color="#2166ac", lw=1.0, label="real")
        ax.plot(t, r["timecourse_sur"], color="#bbbbbb", lw=1.0, label="paired surrogate")
        ax.set_ylabel("rate (z)", fontsize=7)
        ax.set_title(f"{r['source_file']}: median over channels of the settings' mean z-scored rate", fontsize=7)
        ax.tick_params(labelsize=7)
    np.atleast_1d(axes)[-1].set_xlabel("hours from the recording's start", fontsize=7)
    np.atleast_1d(axes)[0].legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=os.path.join(ROOT, "DATA", "db", "annotations.sqlite"))
    ap.add_argument("--map-check", help="a saved /api/discovery/map/channel payload to check the binning against")
    ap.add_argument("--draws", type=int, default=200)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    results, check = [], None
    try:
        for sf in RECORDINGS:
            res, real = read_recording(conn, sf, draws=a.draws)
            results.append(res)
            if a.map_check:
                with open(a.map_check, encoding="utf-8") as fh:
                    mp = json.load(fh)
                if mp.get("file") == sf:
                    check = dict(zip(("agree", "compared"), check_against_map(real, mp)), channel=mp["channel"], file=sf)
            ch = res["channels"]
            print(f"{sf}: {len(ch)} channels; co-modulation real median {np.median([c['real_C'] for c in ch]):.2f} "
                  f"(shift {np.median([c['real_shift_mean'] for c in ch]):.2f}; beyond shifts on "
                  f"{sum(c['real_p'] < 0.05 for c in ch)}); surrogate median {np.median([c['sur_C'] for c in ch]):.2f} "
                  f"(beyond shifts on {sum(c['sur_p'] < 0.05 for c in ch)}); bands {json.dumps(res['bands'])}")
    finally:
        conn.close()
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"recordings": results, "map_check": check}, fh, indent=1, default=float)
    _figure(results, os.path.join(a.out, "b5_timecourse.png"))
    if check:
        print(f"Map check, {check['file']} {check['channel']}: {check['agree']} of {check['compared']} settings' counts "
              f"identical to the page's")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    sys.exit(main())
