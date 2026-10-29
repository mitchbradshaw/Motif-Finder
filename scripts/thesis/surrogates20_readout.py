"""The 20-draw read-out for Chapter 6 (RQ4b read-out, step 3): each chosen detector variant's real count on each
M2_aug channel against that channel's own 20 phase-randomised draws.

In plain words: a detector that finds something real in the signal should fire more on the recording than on copies
of it whose frequency content is kept and whose timing is scrambled. One scrambled copy per channel (the 26 Oct
analysis) is a single coin toss; 20 copies give each channel a ranking: did the real count beat all 20?

It reads the cluster's returned task records (`*_out/return/task*/result.json`) and writes nothing to the database.

- Per channel: p_high = (1 + #draws >= real) / 21 (real more than its null; floor 1/21) and p_low = (1 + #draws <=
  real) / 21 (real fewer), the ratio real / mean(draws), and z = (real - mean) / sd.
- Per variant: how many of its channels beat every draw (`beats_all`) and fall below every draw (`below_all`),
  each against chance by the binomial tail with p = 1/21 per channel (channels are not fully independent: the B4
  census found a shared driver across packs, so read the tail as approximate), Benjamini-Hochberg across variants
  on the pre-specified direction (real above its null); and the pooled count (all channels) against the 20 pooled
  draws (the i-th draw summed across channels).

    python scripts/thesis/surrogates20_readout.py        # writes docs/thesis/data/ch06_20draw/
"""
import argparse
import csv
import glob
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ROOT = os.path.join(ROOT, "docs", "thesis", "hpc", "surrogates20_M2_aug")
DEFAULT_ONE_DRAW = os.path.join(ROOT, "docs", "thesis", "data", "detectors_vs_surrogates", "by_variant_recording.csv")
DEFAULT_OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch06_20draw")
_JOB = re.compile(r"^(?P<variant>.+?)_\d+ch_\d+-\d+_[0-9a-f]+_out$")


def channel_stats(real, draws):
    """One channel: its real count ranked against its own draws."""
    d = np.asarray(draws, dtype=float)
    k = d.size
    mean = float(d.mean())
    sd = float(d.std(ddof=1)) if k > 1 else float("nan")
    if mean > 0:
        ratio = real / mean
    else:
        ratio = float("inf") if real > 0 else float("nan")
    return {"real": int(real), "draws": k, "draws_mean": mean, "draws_sd": sd, "draws_min": float(d.min()),
            "draws_max": float(d.max()),
            "p_high": (1 + int(np.sum(d >= real))) / (k + 1), "p_low": (1 + int(np.sum(d <= real))) / (k + 1),
            "beats_all": bool(np.all(d < real)), "below_all": bool(np.all(d > real)),
            "ratio": ratio, "z": (real - mean) / sd if sd and sd > 0 else float("nan")}


def _binom_tail(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p)."""
    from scipy.stats import binom
    return float(binom.sf(k - 1, n, p)) if k > 0 else 1.0


def _tasks(root):
    for path in sorted(glob.glob(os.path.join(root, "*_out", "return", "task*", "result.json"))):
        job = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
        m = _JOB.match(job)
        if not m:
            raise ValueError(f"{path}: the job folder {job!r} does not name a variant")
        with open(path, encoding="utf-8") as fh:
            r = json.load(fh)
        if not r.get("complete") or r.get("error"):
            raise ValueError(f"{path}: the task is incomplete ({r.get('error')}); bring every task home first")
        yield m.group("variant"), r


def read_out(root=DEFAULT_ROOT):
    """`{"variants": {variant: summary}, "channels": [rows]}` from the returned task records."""
    from Working.discovery.seeded_search import corrected_levels

    rows, by_variant = [], {}
    for variant, r in _tasks(root):
        draws = [int(x) for x in r["draws"]["detections"]]
        row = {"variant": variant, "task": int(r["task"]), "channel": r["channelName"],
               **channel_stats(int(r["run"]["detections"]), draws)}
        rows.append(row)
        by_variant.setdefault(variant, []).append((row, draws))
    variants = {}
    for variant, items in sorted(by_variant.items()):
        k = {len(dr) for _, dr in items}
        if len(k) != 1:
            raise ValueError(f"{variant}: tasks drew different numbers of draws {sorted(k)}")
        k = k.pop()
        n = len(items)
        chance = 1.0 / (k + 1)
        hi = sum(row["beats_all"] for row, _ in items)
        lo = sum(row["below_all"] for row, _ in items)
        pooled_real = sum(row["real"] for row, _ in items)
        pooled_draws = np.sum(np.array([dr for _, dr in items], dtype=float), axis=0)
        pooled = channel_stats(pooled_real, pooled_draws)
        variants[variant] = {"channels": n, "draws": k, "chance_per_channel": chance,
                             "beats_all": hi, "below_all": lo, "expected_by_chance": n * chance,
                             "p_channels_high": _binom_tail(hi, n, chance), "p_channels_low": _binom_tail(lo, n, chance),
                             "median_ratio": float(np.median([row["ratio"] for row, _ in items])),
                             "pooled": pooled}
    names = list(variants)
    levels = corrected_levels([variants[v]["p_channels_high"] for v in names], correction="BH")
    for v, lvl in zip(names, levels):
        variants[v]["bh_high_pass"] = lvl is not None
    return {"variants": variants, "channels": rows}


def _one_draw(path, recording="M2_aug"):
    out = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["recording"] == recording:
                    out[r["template"]] = {"real": float(r["real"]), "surrogate": float(r["surrogate"]),
                                          "ratio": float(r["ratio"])}
    return out


def _figure(res, one, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(res["variants"])
    finite = [r["ratio"] for r in res["channels"] if np.isfinite(r["ratio"]) and r["ratio"] > 0]
    lo_edge, hi_edge = min(finite) / 3, max(finite) * 3      # where a channel off the log scale is drawn
    fig, ax = plt.subplots(figsize=(7.2, 0.62 * len(names) + 1.4))
    for i, v in enumerate(names):
        for r in [r for r in res["channels"] if r["variant"] == v]:
            x, marker = r["ratio"], "o"
            if np.isnan(x):
                continue                                      # nothing on the real signal or its draws
            if not np.isfinite(x):
                x, marker = hi_edge, ">"                      # the 20 draws found none
            elif x <= 0:
                x, marker = lo_edge, "<"                      # the real signal found none
            colour = "#1b7837" if r["beats_all"] else ("#b2182b" if r["below_all"] else "#777777")
            ax.plot(x, i + np.random.default_rng(r["task"]).uniform(-0.18, 0.18), marker, ms=4, color=colour,
                    alpha=0.8)
        if v in one and one[v]["ratio"] > 0:
            ax.plot(one[v]["ratio"], i, marker="|", ms=16, mew=2, color="black")
    ax.axvline(1.0, color="black", lw=0.8, ls="--")
    ax.set_xscale("log")
    ax.set_xlim(lo_edge / 1.5, hi_edge * 1.5)
    ax.set_yticks(range(len(names)), names, fontsize=8)
    ax.set_xlabel("real count / mean of its 20 draws (per channel; log scale)")
    ax.set_title("M2_aug, 16 channels per variant. Green: real beat all 20 draws; red: below all 20.\n"
                 "Bar: the 1-draw ratio. ▶ at the right edge: the draws found none.", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write(res, one, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    cols = ["variant", "task", "channel", "real", "draws_mean", "draws_sd", "draws_min", "draws_max", "ratio", "z",
            "p_high", "p_low", "beats_all", "below_all"]
    with open(os.path.join(out_dir, "per_channel.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(res["channels"])
    vcols = ["variant", "channels", "beats_all", "below_all", "expected_by_chance", "p_channels_high",
             "p_channels_low", "bh_high_pass", "median_ratio", "pooled_real", "pooled_draws_mean", "pooled_ratio",
             "pooled_p_high", "pooled_p_low", "one_draw_real", "one_draw_surrogate", "one_draw_ratio"]
    with open(os.path.join(out_dir, "per_variant.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=vcols)
        w.writeheader()
        for v, s in res["variants"].items():
            o = one.get(v, {})
            w.writerow({"variant": v, "channels": s["channels"], "beats_all": s["beats_all"],
                        "below_all": s["below_all"], "expected_by_chance": round(s["expected_by_chance"], 3),
                        "p_channels_high": s["p_channels_high"], "p_channels_low": s["p_channels_low"],
                        "bh_high_pass": s["bh_high_pass"], "median_ratio": s["median_ratio"],
                        "pooled_real": s["pooled"]["real"], "pooled_draws_mean": s["pooled"]["draws_mean"],
                        "pooled_ratio": s["pooled"]["ratio"], "pooled_p_high": s["pooled"]["p_high"],
                        "pooled_p_low": s["pooled"]["p_low"], "one_draw_real": o.get("real"),
                        "one_draw_surrogate": o.get("surrogate"), "one_draw_ratio": o.get("ratio")})
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"variants": res["variants"], "one_draw_M2_aug": one,
                   "note": "p = (1 + draws on the far side) / 21; the binomial tails treat channels as independent, "
                           "which the B4 census's shared driver says they are not quite"}, fh, indent=1, default=float)
    _figure(res, one, os.path.join(out_dir, "ratio_strip.png"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--one-draw", default=DEFAULT_ONE_DRAW)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    res = read_out(a.root)
    one = _one_draw(a.one_draw)
    write(res, one, a.out)
    print(f"{'variant':40s} {'beat all':>8s} {'below all':>9s} {'p(chance)':>10s} {'BH':>3s} {'pooled ratio':>12s} "
          f"{'1-draw':>7s}")
    for v, s in res["variants"].items():
        o = one.get(v, {}).get("ratio")
        print(f"{v:40s} {s['beats_all']:5d}/{s['channels']:<2d} {s['below_all']:6d}/{s['channels']:<2d} "
              f"{s['p_channels_high']:10.2e} {'yes' if s['bh_high_pass'] else 'no':>3s} {s['pooled']['ratio']:12.3f} "
              f"{o if o is None else round(o, 3)!s:>7s}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    sys.exit(main())
