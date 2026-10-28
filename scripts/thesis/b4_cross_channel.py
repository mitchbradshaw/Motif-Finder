"""
b4_cross_channel.py — round-B question B4 (Chapter 10): is there evidence of a propagation lag between channels that
is not artefact? Tables and figures from the STORED cross-channel census (`Working/cross_census.py`, written by
Explore › Cross-channel's *Run census*). Nothing is recomputed here: every number is the census's, and every table
row and figure carries the census hash it came from (D24).

Reads the latest finished census per source file (of `--detector`, default drop_detection_v1) from a database
opened read-only (`mode=ro`). The held-out recording is never read: a census row naming it is skipped by name.

Writes into `--out` (default docs/thesis/data/ch10_b4/):
  b4_summary.json            per census: hash, bins, overall excess and shared driver, the BH families, layout
  b4_pairs.csv               every within-pack pair: co-occurrences against rotation, the timetable against its pool
  b4_bins.csv                bin counts per recording
  b4_bins.png                bin counts per recording
  b4_lag_hist_<stem>.png     per recording, the busiest within-pack pairs: observed non-copy lags against the
                             timetable pool's lags (scaled to the same count), when the null draws are on disk
  b4_lag_vs_distance.png     lag against electrode distance, ONLY when every channel's position is known;
  b4_lag_vs_distance_NOTE.txt otherwise, which recordings lack positions and why nothing is drawn

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b4_cross_channel.py --db <a bridge backup>.sqlite
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import math
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b4")
HELD_OUT_FILE = "M4_aug_concat_fs1.mat"
BINS = ("artifact", "propagation", "independent_recurrence", "shared_driver", "pack_unknown")
MAX_PANELS = 12


def _ro(path):
    uri = "file:" + os.path.abspath(path).replace("\\", "/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _latest(conn, detector):
    """`(censuses, skipped)`: the newest finished census per source file, the held-out file skipped by name."""
    files = [r[0] for r in conn.execute("SELECT DISTINCT source_file FROM cross_census WHERE status = 'done' "
                                        "AND detector = ? ORDER BY source_file", (detector,))]
    out, skipped = [], []
    for sf in files:
        if sf == HELD_OUT_FILE:
            skipped.append(f"{sf}: the held-out recording is never read")
            continue
        row = conn.execute("SELECT * FROM cross_census WHERE source_file = ? AND detector = ? AND status = 'done' "
                           "ORDER BY id DESC LIMIT 1", (sf, detector)).fetchone()
        r = dict(row)
        for src, dst in (("summary_json", "summary"), ("layout_json", "layout"), ("consts_json", "consts"),
                         ("rule_json", "rule")):
            r[dst] = json.loads(r[src]) if r[src] else {}
        out.append(r)
    return out, skipped


def _short(h):
    return str(h)[:12]


def _stem(sf):
    return os.path.splitext(os.path.basename(sf))[0]


def _pairs_rows(c):
    rows = []
    for p in c["summary"].get("pairs", []):
        t = p.get("timetable") or {}
        rows.append({"census_hash": c["hash"], "source_file": c["source_file"], "a": p["a"], "b": p["b"],
                     "a_name": p["a_name"], "b_name": p["b_name"], "pack": p["pack"], "n": p["n"],
                     "null_mean": p["null_mean"], "null_p95": p["null_p95"], "p": p["p"], "q": p["q"],
                     "propagation": (p.get("bins") or {}).get("propagation"),
                     "timetable_n_noncopy": t.get("n_noncopy"), "timetable_count": t.get("count"),
                     "timetable_L_s": t.get("L_s"), "timetable_median_lag_s": t.get("median_lag_s"),
                     "timetable_mad_s": t.get("mad_s"), "timetable_p": t.get("p"), "timetable_q": t.get("q"),
                     "timetable_null_mean": t.get("null_mean"), "timetable_null_p95": t.get("null_p95"),
                     "timetable_testable": t.get("testable"), "timetable_reason": t.get("reason")})
    return rows


def _write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _fig_bins(censuses, path):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(max(6, 1.6 * len(censuses) + 3), 4))
    width = 0.8 / len(BINS)
    x = np.arange(len(censuses))
    for i, b in enumerate(BINS):
        ax.bar(x + i * width - 0.4 + width / 2, [c["summary"].get("bins", {}).get(b, 0) for c in censuses], width,
               label=b.replace("_", " "))
    ax.set_xticks(x)
    ax.set_xticklabels([_stem(c["source_file"]) for c in censuses], rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("co-occurrences")
    ax.set_title("B4 census: co-occurrences per bin")
    ax.legend(fontsize=7)
    fig.text(0.01, 0.01, "census " + " · ".join(f"{_stem(c['source_file'])} {_short(c['hash'])}" for c in censuses),
             fontsize=6)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _fig_lag_hist(conn, c, path):
    plt = _plt()
    s = c["summary"]
    pairs = sorted((p for p in s.get("pairs", []) if (p.get("timetable") or {}).get("n_noncopy", 0) >= 1),
                   key=lambda p: -p["timetable"]["n_noncopy"])[:MAX_PANELS]
    draws = None
    if c.get("null_path") and os.path.isfile(c["null_path"]):
        draws = np.load(c["null_path"])
    n = max(1, len(pairs))
    cols = min(4, n)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.4 * rows), squeeze=False)
    hi = float(c["rule"].get("propagation_max_lag_s", 50.0))
    edges = np.arange(-hi, hi + 1.0, 2.0)
    for ax in axes.ravel()[len(pairs):]:
        ax.axis("off")
    if not pairs:
        axes[0][0].axis("on")
        axes[0][0].text(0.5, 0.5, "no within-pack pair has a non-copy co-occurrence", ha="center", va="center",
                        fontsize=8, transform=axes[0][0].transAxes)
    for ax, p in zip(axes.ravel(), pairs):
        lags = [r[0] for r in conn.execute(
            "SELECT lag_s FROM cross_cooccurrence WHERE census_id = ? AND rec_a_id = ? AND rec_b_id = ? "
            "AND bin != 'artifact' AND lag_s IS NOT NULL", (c["id"], p["a"], p["b"]))]
        ax.hist(lags, bins=edges, color="#0A84FF", label=f"observed (n={len(lags)})")
        key = f"tt_{p['a']}_{p['b']}_pool"
        if draws is not None and key in draws.files and len(lags):
            pool = draws[key]
            h, _ = np.histogram(pool, bins=edges)
            ax.step(edges[:-1], h * (len(lags) / max(1, pool.size)), where="post", color="#FF9F0A",
                    label="random-time lags, scaled")
        t = p["timetable"]
        ax.set_title(f"{p['a_name']}→{p['b_name']} · L {t['L_s'] if t['L_s'] is None else round(t['L_s'], 1)} s "
                     f"· p {t['p'] if t['p'] is None else round(t['p'], 4)}", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.legend(fontsize=5)
    note = "" if draws is not None else " · null draws not on disk: observed lags only"
    fig.text(0.01, 0.005, f"{c['source_file']} · census {c['hash']}{note}", fontsize=6)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    if draws is not None:
        draws.close()


def _fig_lag_distance(conn, censuses, path):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6, 4))
    for c in censuses:
        ch = c["layout"]["channels"]
        xs, ys = [], []
        for r in conn.execute("SELECT rec_a_id, rec_b_id, lag_s FROM cross_cooccurrence WHERE census_id = ? "
                              "AND bin IN ('propagation', 'independent_recurrence') AND lag_s IS NOT NULL",
                              (c["id"],)):
            a, b = ch[str(r[0])], ch[str(r[1])]
            xs.append(math.hypot(a["x_mm"] - b["x_mm"], a["y_mm"] - b["y_mm"]))
            ys.append(r[2])
        ax.scatter(xs, ys, s=8, label=f"{_stem(c['source_file'])} ({_short(c['hash'])})")
    ax.axhline(0, color="grey", lw=0.5)
    ax.set_xlabel("electrode distance (mm)")
    ax.set_ylabel("lag (s)")
    ax.set_title("B4: within-pack lag against distance")
    ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=DB, help="database to read (opened mode=ro); use a bridge backup")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--detector", default="drop_detection_v1")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    conn = _ro(args.db)
    try:
        censuses, skipped = _latest(conn, args.detector)
        summary = {"generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
                   "db": os.path.abspath(args.db), "detector": args.detector, "skipped": skipped,
                   "censuses": [{"source_file": c["source_file"], "census_id": c["id"], "hash": c["hash"],
                                 "finished_at": c["finished_at"], "bins": c["summary"].get("bins"),
                                 "n_events": c["summary"].get("n_events"),
                                 "n_cooccurrences": c["summary"].get("n_cooccurrences"),
                                 "overall": c["summary"].get("overall"), "bh": c["summary"].get("bh"),
                                 "layout_known": c["summary"].get("layout_known"),
                                 "layout_note": c["summary"].get("layout_note"),
                                 "pairs_beating_rotation": sum(1 for p in c["summary"].get("pairs", [])
                                                               if p.get("q") is not None),
                                 "timetables_beating_null": sum(1 for p in c["summary"].get("pairs", [])
                                                                if (p.get("timetable") or {}).get("q") is not None),
                                 "shared_driver": c["summary"].get("shared_driver"),
                                 "breadth": [{k: b[k] for k in ("instant_id", "breadth", "packs", "common_mode", "p",
                                                                "q")} for b in c["summary"].get("breadth", [])]}
                                for c in censuses]}
        with open(os.path.join(args.out, "b4_summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        pair_rows = [r for c in censuses for r in _pairs_rows(c)]
        _write_csv(os.path.join(args.out, "b4_pairs.csv"), pair_rows,
                   list(pair_rows[0]) if pair_rows else ["census_hash", "source_file", "a", "b", "n"])
        bin_rows = [{"census_hash": c["hash"], "source_file": c["source_file"], "bin": b,
                     "count": c["summary"].get("bins", {}).get(b, 0)} for c in censuses for b in BINS]
        _write_csv(os.path.join(args.out, "b4_bins.csv"), bin_rows, ["census_hash", "source_file", "bin", "count"])
        if censuses:
            _fig_bins(censuses, os.path.join(args.out, "b4_bins.png"))
            for c in censuses:
                _fig_lag_hist(conn, c, os.path.join(args.out, f"b4_lag_hist_{_stem(c['source_file'])}.png"))
        placed = [c for c in censuses if c["layout"].get("positions_known")]
        unplaced = [c for c in censuses if not c["layout"].get("positions_known")]
        note_path = os.path.join(args.out, "b4_lag_vs_distance_NOTE.txt")
        fig_path = os.path.join(args.out, "b4_lag_vs_distance.png")
        if placed:
            _fig_lag_distance(conn, placed, fig_path)
        if unplaced or not censuses:
            with open(note_path, "w", encoding="utf-8") as f:
                f.write("Lag against distance is drawn only for recordings whose every electrode has a position "
                        "(Settings › Channels & events, x_mm and y_mm). No position is set for:\n")
                for c in unplaced:
                    f.write(f"  {c['source_file']} (census {c['hash']})\n")
                if not censuses:
                    f.write("  (no census found)\n")
    finally:
        conn.close()
    print(f"B4: {len(censuses)} census(es) -> {args.out}" + (f"; skipped: {'; '.join(skipped)}" if skipped else ""))
    for c in censuses:
        print(f"  {c['source_file']}  census {c['hash']}  bins {c['summary'].get('bins')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
