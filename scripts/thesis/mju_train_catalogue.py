"""Machine boundary proposals for the two researcher-accepted MJu26a trains.

No DB writes. The researcher's 8-Nov request accepts the spikes in BOTH trains;
that is a train-level acceptance, not a fresh blind verdict on each extraction.
Boundaries remain proposals and their method/thresholds are saved explicitly.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks, peak_widths

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.thesis.accepted_catalogue import canonical_span, connect, csv_write


def propose(values, fs, *, prominence_mv, min_separation_s=15.0):
    """Local extrema/95%-prominence widths. Suggestions, not event ontology.

    Smoothing is 0.5 s (one sigma). Two adjacent extrema remain separate even
    when recovery tails overlap. Their display snippets may share context.
    """
    x = np.asarray(values, dtype=float)
    if not np.isfinite(x).all():
        raise ValueError("A gap in a train needs inspection before segmentation")
    smooth = gaussian_filter1d(x, max(.5, .5 * fs))
    peaks, props = find_peaks(-smooth, prominence=prominence_mv,
                              distance=max(1, round(fs * min_separation_s)))
    if not len(peaks):
        return []
    widths, heights, left, right = peak_widths(-smooth, peaks, rel_height=.95,
        prominence_data=(props["prominences"], props["left_bases"], props["right_bases"]))
    out = []
    for i, p in enumerate(peaks):
        s, e = max(0, int(np.floor(left[i]))), min(len(x), int(np.ceil(right[i])) + 1)
        out.append({"peak_idx": int(p), "start_idx": s, "end_idx": e,
                    "prominence_mv": float(props["prominences"][i]),
                    "width_95_s": float(widths[i] / fs),
                    "boundary_status": "machine_proposed",
                    "acceptance_basis": "researcher accepted spikes in this train, 2026-11-08",
                    "individually_blind_reviewed": False})
    return out


def render(train, x, fs, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rr = train["events"]
    n_panels = 8 if train["id"] == "mju_ch15_long" else 4
    fig, axs = plt.subplots(n_panels, 1, figsize=(14, n_panels * 2.05), layout="constrained")
    edges = np.linspace(0, len(x), n_panels + 1).astype(int)
    for ax, a, b in zip(axs, edges[:-1], edges[1:]):
        stride = max(1, (b - a) // 6000)
        n = (b - a) // stride
        v = np.asarray(x[a:a + n * stride]).reshape(n, stride)
        tt = (a + np.arange(n) * stride) / fs / 3600 + train["start_s"] / 3600
        ax.fill_between(tt, v.min(1), v.max(1), color="#29465e", lw=.3)
        for i, r in enumerate(rr, 1):
            p = r["local_peak_idx"]
            if a <= p < b:
                ax.plot((p / fs + train["start_s"]) / 3600, x[p], "o", ms=2.5, color="#b24b38")
                ax.annotate(str(i), ((p / fs + train["start_s"]) / 3600, x[p]),
                            xytext=(0, -10), textcoords="offset points", ha="center", fontsize=6)
        ax.set(xlabel="Hours from start of source recording", ylabel="mV")
        ax.grid(alpha=.12)
    fig.suptitle(f"{train['label']} — {len(rr)} machine-separated spikes; boundaries require checking", fontsize=13)
    fig.savefig(out / (train["id"] + ".png"), dpi=160)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "docs/thesis/data/accepted_catalogue")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    c = connect(args.project_root / "DATA/db/annotations.sqlite")
    recs = {r["id"]: dict(r) for r in c.execute("SELECT * FROM recordings")}
    c.close()
    trains = []
    for tid, rid, a, b, prom, label in [
        ("mju_ch15_long", 543, 206 * 3600, 283 * 3600, 2.0, "MJu26a CH15, 206–283 h"),
        ("mju_ch14_excerpt", 385, 0, 14400, 1.0, "MJu26a CH14, four-hour excerpt"),
    ]:
        rec = recs[rid]
        arr = np.load(args.project_root / rec["npy_path"], mmap_mode="r")
        fs = float(rec["fs"])
        start, end = round(a * fs), min(len(arr), round(b * fs))
        x = np.asarray(arr[start:end], dtype=float) * {"V": 1000, "mV": 1, "uV": .001}[rec["units"]]
        proposals = propose(x, fs, prominence_mv=prom)
        events = []
        for i, r in enumerate(proposals, 1):
            crid, cs, ce = canonical_span(rec, start + r["start_idx"], start + r["end_idx"], recs)
            _, cp, _ = canonical_span(rec, start + r["peak_idx"], start + r["peak_idx"] + 1, recs)
            events.append({**r, "local_peak_idx": r["peak_idx"], "event_id": f"{tid}-{i:03d}",
                           "source_recording_id": rid, "source_start_idx": start + r["start_idx"],
                           "source_end_idx": start + r["end_idx"],
                           "recording_id": crid, "start_idx": cs, "end_idx": ce, "peak_idx": cp,
                           "channel": recs[crid]["channel"], "fs": recs[crid]["fs"]})
        train = {"id": tid, "label": label, "source_recording_id": rid, "start_s": a, "end_s": b,
                 "prominence_mv": prom, "method": "negative peaks, 0.5-s Gaussian smoothing, 15-s separation, 95%-prominence widths",
                 "acceptance_level": "researcher train-level inclusion; not individual blind judgements",
                 "events": events}
        trains.append(train)
        render(train, x, fs, args.out)
    (args.out / "mju_trains.json").write_text(json.dumps(trains, indent=2), encoding="utf-8")
    csv_write(args.out / "mju_train_spikes.csv", [dict(train=t["id"], **r) for t in trains for r in t["events"]])
    print(json.dumps([{k: t[k] for k in ["id", "label", "prominence_mv"]} | {"events": len(t["events"])} for t in trains], indent=2))


if __name__ == "__main__":
    main()
