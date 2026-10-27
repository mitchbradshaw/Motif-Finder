"""
Figures for round-B B3 (`run_b3.py figures`), drawn from b3_restitution.json and b3_track.json.

* `b3_restitution_rho`   — every sequence, chain and census channel's rho (recovery vs the gap
  before), beside the same rho against the gap AFTER (the censoring control), sized by pairs.
* `b3_restitution_scatter` — recovery against the gap before and after, in ranks, for the three
  chains and the longest oyster sequence.
* `b3_track_ratio`      — held-out-cycle error relative to the mean of the other cycles, per model
  and dataset, real cycles beside the quiet and phase-scrambled fake cycles.
* `b3_track_params`     — the fitted parameters block by block along each chain and sequence.
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from Pipelines.fhn.figures import BLUE, GREY, INK, ORANGE, RED, VIOLET, _save  # noqa: E402

MODEL_LABEL = {"kernel": "fall + recovery kernel (k=6)", "fhn_excitable": "FHN excitable (k=8)",
               "fhn_oscillator": "FHN oscillatory (k=7)", "izhikevich": "Izhikevich (k=9)"}
MODEL_COLOUR = {"kernel": INK, "fhn_excitable": BLUE, "fhn_oscillator": VIOLET, "izhikevich": ORANGE}
KIND_MARK = {"real": "o", "quiet": "s", "surrogate": "^"}


def _units(r):
    rows = []
    for s in r["sequences"]["rows"]:
        rows.append(("sequence · " + (s.get("species") or "?"), s))
    for s in r["chains"]["rows"]:
        rows.append(("chain", s))
    for corpus, v in r["census"].items():
        for s in v["channels"]:
            rows.append((f"census · {corpus}", s))
    return [(g, s) for g, s in rows if s.get("rho") is not None]


def fig_restitution_rho(r, out_dir):
    units = _units(r)
    groups = list(dict.fromkeys(g for g, _ in units))
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.5 + 0.55 * len(groups) + 2), sharey=True)
    for ax, which, title in ((axes[0], "before", "recovery vs the gap BEFORE (restitution)"),
                             (axes[1], "after", "recovery vs the gap AFTER (control)")):
        for gi, g in enumerate(groups):
            rows = [s for gg, s in units if gg == g]
            rho = [s["rho"] if which == "before" else (s["control_gap_after"] or {}).get("rho") for s in rows]
            p = [s["p_two"] if which == "before" else (s["control_gap_after"] or {}).get("p_two") for s in rows]
            n = np.array([s["n_pairs"] for s in rows], float)
            ok = np.array([v is not None for v in rho])
            rr = np.array([v if v is not None else np.nan for v in rho], float)
            pp = np.array([v if v is not None else np.nan for v in p], float)
            jit = np.random.default_rng(gi).uniform(-0.22, 0.22, len(rows))
            sig = ok & (pp < 0.05)
            ax.scatter(rr[ok & ~sig], gi + jit[ok & ~sig], s=8 + 2 * n[ok & ~sig], facecolors="none", edgecolors=GREY,
                       lw=0.8)
            ax.scatter(rr[sig], gi + jit[sig], s=8 + 2 * n[sig], color=RED, alpha=0.8)
            if ok.any():
                w = n[ok]
                ax.plot([np.sum(w * rr[ok]) / np.sum(w)] * 2, [gi - 0.35, gi + 0.35], color=INK, lw=2)
        ax.axvline(0, color=GREY, lw=0.8)
        ax.set_xlim(-1.05, 1.05)
        ax.set_xlabel("Spearman rho")
        ax.set_title(title, fontsize=10)
    axes[0].set_yticks(range(len(groups)))
    axes[0].set_yticklabels([f"{g} ({sum(1 for gg, _ in units if gg == g)})" for g in groups], fontsize=8)
    fig.suptitle("B3 restitution: each dot one train (size = pairs; red = permutation p < 0.05; bar = pair-weighted "
                 "mean)", fontsize=10)
    fig.tight_layout()
    return _save(fig, out_dir / "b3_restitution_rho")


def fig_restitution_scatter(r, out_dir):
    picks = [s for s in r["chains"]["rows"]] + [s for s in r["sequences"]["rows"] if s.get("id") in (1, 3)]
    fig, axes = plt.subplots(2, len(picks), figsize=(3.0 * len(picks), 6), squeeze=False)
    for j, s in enumerate(picks):
        g = np.array(s["pairs"]["gap_s"], float)
        rec = np.array(s["pairs"]["recovery_s"], float)
        ax = axes[0, j]
        ax.scatter(stats.rankdata(g), stats.rankdata(rec), s=10, color=BLUE)
        ax.set_title(f"{s.get('key')}\nrho {s['rho']:+.2f} (p {s['p_two']:.2g}); | depth {s['partial_depth']['rho']:+.2f}"
                     f"; | gap after {s.get('partial_gap_after', {}).get('rho', float('nan')):+.2f}", fontsize=7)
        ax.set_xlabel("rank of gap before")
        ax.set_ylabel("rank of recovery")
        # the control: the gap after (consecutive events; the last event has none)
        ga = np.array([v if v is not None else np.nan for v in s["pairs"].get("gap_after_s", [])], float) \
            if "gap_after_s" in s["pairs"] else None
        ax2 = axes[1, j]
        if ga is not None and np.isfinite(ga).sum() > 3:
            m = np.isfinite(ga)
            ax2.scatter(stats.rankdata(ga[m]), stats.rankdata(rec[m]), s=10, color=ORANGE)
        c = s.get("control_gap_after") or {}
        ax2.set_title(f"vs gap AFTER: rho {c.get('rho', float('nan')):+.2f} (p {c.get('p_two', float('nan')):.2g})",
                      fontsize=7)
        ax2.set_xlabel("rank of gap after")
        ax2.set_ylabel("rank of recovery")
    fig.suptitle("Recovery time (Event shape, extremum to half recovery) against the gap before and after", fontsize=10)
    fig.tight_layout()
    return _save(fig, out_dir / "b3_restitution_scatter")


def _track_table(t):
    tab = {}
    for res in t["results"]:
        tab.setdefault(res["dataset"], {}).setdefault(res["model"], []).append(res)
    return tab


def fig_track_ratio(t, out_dir):
    tab = _track_table(t)
    names = list(t["datasets"])
    fig, axes = plt.subplots(1, len(names), figsize=(2.6 * len(names), 4.2), sharey=True, squeeze=False)
    for j, name in enumerate(names):
        ax = axes[0, j]
        for mi, model in enumerate(MODEL_LABEL):
            for res in tab.get(name, {}).get(model, []):
                x = mi + {"real": -0.2, "quiet": 0.0, "surrogate": 0.2}[res["kind"]] + 0.05 * res["draw"]
                ax.scatter(x, res["summary"]["pooled_ratio"], marker=KIND_MARK[res["kind"]],
                           color=MODEL_COLOUR[model] if res["kind"] == "real" else "none",
                           edgecolors=MODEL_COLOUR[model], s=40)
        ax.axhline(1.0, color=GREY, lw=0.8)
        ax.set_xticks(range(len(MODEL_LABEL)))
        ax.set_xticklabels(["kernel", "FHN exc", "FHN osc", "Izh"], rotation=45, fontsize=8)
        d = t["datasets"][name]
        ax.set_title(f"{name}\n{d['n_cycles']} cycles, blocks of {d['block']}", fontsize=8)
    axes[0, 0].set_ylabel("held-out error / error of the mean of the other cycles\n(pooled; < 1 = model better)")
    axes[0, 0].set_yscale("log")
    fig.suptitle("Held-out-cycle prediction. Filled = real cycles; square = quiet fake cycles; triangle = "
                 "phase-scrambled fake cycles", fontsize=9)
    fig.tight_layout()
    return _save(fig, out_dir / "b3_track_ratio")


def fig_track_params(t, out_dir):
    tab = _track_table(t)
    panels = [("fhn_excitable", "alpha"), ("fhn_excitable", "span"), ("fhn_oscillator", "alpha"),
              ("fhn_oscillator", "time_ratio"), ("izhikevich", "a"), ("izhikevich", "b"), ("izhikevich", "c"),
              ("izhikevich", "d"), ("kernel", "decay_frac")]
    names = list(t["datasets"])
    fig, axes = plt.subplots(len(panels), len(names), figsize=(2.6 * len(names), 1.5 * len(panels)), squeeze=False)
    for j, name in enumerate(names):
        for i, (model, par) in enumerate(panels):
            ax = axes[i, j]
            for res in tab.get(name, {}).get(model, []):
                y = np.array([v if v is not None else np.nan for v in res["params"].get(par, [])], float)
                if not y.size:
                    continue
                style = dict(color=MODEL_COLOUR[model], lw=1.5) if res["kind"] == "real" else dict(color=GREY, lw=0.7)
                ax.plot(np.arange(y.size), y, marker=".", ms=3, **style)
                if res["kind"] == "real":
                    d = res["drift"].get(par) or {}
                    if d.get("rho") is not None:
                        ax.set_title(f"rho {d['rho']:+.2f} p {d['p_rho']:.2g}; vN p {d['p_sssd']:.2g}", fontsize=6)
            if j == 0:
                ax.set_ylabel(f"{model.replace('fhn_', 'FHN ')}\n{par}", fontsize=7)
            if i == len(panels) - 1:
                ax.set_xlabel(f"block ({name})", fontsize=7)
            ax.tick_params(labelsize=6)
    fig.suptitle("Fitted parameters block by block (colour = real cycles; grey = fake cycles). Title: drift test on "
                 "the real track against shuffled block order", fontsize=9)
    fig.tight_layout()
    return _save(fig, out_dir / "b3_track_params")


def all_figures(out_dir):
    figs = []
    rp = out_dir / "b3_restitution.json"
    if rp.exists():
        r = json.loads(rp.read_text(encoding="utf-8"))
        figs += fig_restitution_rho(r, out_dir)
        figs += fig_restitution_scatter(r, out_dir)
    tp = out_dir / "b3_track.json"
    if tp.exists():
        t = json.loads(tp.read_text(encoding="utf-8"))
        figs += fig_track_ratio(t, out_dir)
        figs += fig_track_params(t, out_dir)
    print("\n".join(figs))
    return figs
