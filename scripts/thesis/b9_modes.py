"""
b9_modes.py - B9's declared test on the events b9_cwt_durations.py wrote: is log duration (best_scale_s) multimodal,
and are its modes the real recording's or the noise's?

Per recording and pooled, for the real spans and for their AAFT and phase-randomised copies:
  * Gaussian mixtures with 1, 2 and 3 components on log10(best_scale_s) (sklearn, 10 restarts, seed 0); the
    BIC-best K, and Delta-BIC = BIC(1) - BIC(best) (> 10 = strong evidence for more than one mode);
  * the scales sit on a 40-step log grid (10-7200 s), so each value is jittered uniformly within +/- half a grid
    step first (seed 0) - otherwise a mixture can "find" the grid's spikes;
  * the fitted components' means (in s) and weights; a component only counts as a mode if its weight is >= 10 %;
  * a two-sample Kolmogorov-Smirnov test, real against AAFT log durations;
  * nothing is fitted on fewer than 20 events.
Clean events (no edge_flag, no step_pair) are the primary set; all events are reported alongside.

Writes docs/thesis/data/ch10_b9/{modes.csv, counts.csv, durations_hist.png}.
"""
import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.mixture import GaussianMixture

warnings.filterwarnings("ignore")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b9")
STEP = np.log10(7200 / 10) / 39
MIN_N = 20


def fit(logd):
    rng = np.random.default_rng(0)
    z = (logd + rng.uniform(-STEP / 2, STEP / 2, len(logd))).reshape(-1, 1)
    out = {}
    for k in (1, 2, 3):
        g = GaussianMixture(k, n_init=10, random_state=0).fit(z)
        out[k] = (g.bic(z), g)
    best = min(out, key=lambda k: out[k][0])
    g = out[best][1]
    order = np.argsort(g.means_.ravel())
    comps = [(10 ** g.means_.ravel()[i], g.weights_[i]) for i in order]
    modes = [m for m, w in comps if w >= 0.10]
    return {"bic1": out[1][0], "bic2": out[2][0], "bic3": out[3][0], "best_k": best,
            "dbic_1_vs_best": out[1][0] - out[best][0],
            "components_s_w": "; ".join(f"{m:.0f} s ({w:.0%})" for m, w in comps),
            "modes_s": ", ".join(f"{m:.0f}" for m in modes), "n_modes": len(modes)}


def main():
    ev = pd.read_csv(os.path.join(D, "events.csv"))
    sp = pd.read_csv(os.path.join(D, "spans.csv"))
    ev["clean"] = ~(ev.edge_flag.astype(bool) | ev.step_pair.astype(bool))
    ev["logd"] = np.log10(ev.best_scale_s)
    rows = []
    groups = [(r, ev[ev.recording == r]) for r in sorted(ev.recording.unique())] + [("pooled", ev)]
    for rec, e in groups:
        for subset in ("clean", "all"):
            es = e[e.clean] if subset == "clean" else e
            real = es[es.kind == "real"].logd.values
            for kind in ("real", "aaft", "pr"):
                x = es[es.kind == kind].logd.values
                row = {"recording": rec, "events": subset, "kind": kind, "n": len(x),
                       "median_s": float(10 ** np.median(x)) if len(x) else np.nan}
                if len(x) >= MIN_N:
                    row.update(fit(x))
                if kind != "real" and len(x) >= MIN_N and len(real) >= MIN_N:
                    ks = stats.ks_2samp(real, x)
                    row["ks_vs_real_D"], row["ks_vs_real_p"] = ks.statistic, ks.pvalue
                rows.append(row)
    m = pd.DataFrame(rows)
    m.to_csv(os.path.join(D, "modes.csv"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(m[["recording", "events", "kind", "n", "median_s", "best_k", "dbic_1_vs_best", "components_s_w",
             "ks_vs_real_D", "ks_vs_real_p"]].to_string())
    ok = sp[~sp.skipped.astype(bool)]
    cnt = ok.groupby("recording").agg(spans=("n_real", "size"), real=("n_real", "sum"), clean_real=("clean_real", "sum"),
                                      aaft=("n_aaft0", "sum"), clean_aaft=("clean_aaft0", "sum"),
                                      pr=("n_pr0", "sum"), clean_pr=("clean_pr0", "sum"),
                                      spans_real_gt_aaft=("n_real", lambda s: int((s > ok.loc[s.index, "n_aaft0"]).sum())))
    cnt.loc["pooled"] = cnt.sum()
    cnt.to_csv(os.path.join(D, "counts.csv"))
    print(cnt)
    print("skipped spans:", int(sp.skipped.astype(bool).sum()))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    recs = sorted(ev.recording.unique())
    fig, axs = plt.subplots(1, len(recs) + 1, figsize=(3.2 * (len(recs) + 1), 3), sharey=False)
    bins = np.log10(10) + STEP * (np.arange(41) - 0.5)
    for ax, (rec, e) in zip(axs, [(r, ev[ev.recording == r]) for r in recs] + [("pooled", ev)]):
        e = e[e.clean]
        for kind, col in (("real", "#1f4e79"), ("aaft", "#c55a11"), ("pr", "#7f7f7f")):
            x = e[e.kind == kind].logd
            ax.hist(x, bins=bins, histtype="step", color=col, label=f"{kind} ({len(x)})", lw=1.4)
        ax.set_title(rec, fontsize=9)
        ax.set_xlabel("log10 best_scale_s")
        ax.legend(fontsize=7)
    axs[0].set_ylabel("clean events")
    fig.tight_layout()
    fig.savefig(os.path.join(D, "durations_hist.png"), dpi=150)


if __name__ == "__main__":
    main()
