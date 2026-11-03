"""
Figures for research prompt 01 (`run_long.py figures`): per train, PNG + PDF of

* `fit_<train>`        - the mean cycle, every model's fit, and the fits' R2 and the cycle height on the nulls;
* `track_<train>`      - held-out ratios, recording against the nulls, and the cold-start parameter series;
* `prc_models_<train>` - every oscillating fit's PRC in the style of Wilshin, Kvalheim & Revzen (2024) Fig. 1;
* `prc_spont_<train>`  - the spontaneous phase-timing estimate beside the model PRCs (own axes: other units);
* `returnmap_<train>`  - T_{i+1} against T_i, raw and drift-removed, with the shuffle null.

Every model PRC is the PRC of a fitted MODEL; the spontaneous estimate is a correlation. The titles say so.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from Pipelines.fhn.figures import BLUE, GREEN, GREY, INK, ORANGE, RED, VIOLET, _phase_axis, _save  # noqa: E402

COL = dict(kernel=ORANGE, jump_exp="#d9a05b", sinusoid_1=GREY, fhn_oscillator=BLUE, fhn_excitable=VIOLET,
           izhikevich=RED, van_der_pol=GREEN, morris_lecar="#0f9c9c")
NULL_MK = dict(quiet="o", surrogate="s", aaft="^")
MODEL_NOTE = "MODEL PRC of the fitted model, in rad per mV of kick - not a measured PRC (no fungus was stimulated)"
SPONT_NOTE = ("spontaneous phase-timing estimate: a CORRELATION between the signal's own deviations and the next "
              "drop's timing, not a PRC")


def _load(out_dir, stem):
    rows, extra = [], {}
    for p in sorted(Path(out_dir).glob(f"{stem}*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        rows += j.get("results", j.get("models", []))
        for k in ("trains", "spontaneous", "return_map"):
            if k in j:
                extra.setdefault(k, {}).update(j[k])
    return rows, extra


def fig_fit(train, meta, rows, path_stem):
    real = {r["model"]: r for r in rows if r["kind"] == "real" and r.get("r2") is not None}
    fig, (a0, a1, a2) = plt.subplots(1, 3, figsize=(16, 5), gridspec_kw=dict(width_ratios=[1.6, 1.3, 0.6]))
    t = np.asarray(meta["tau_s"])
    for c in meta["cycles_sample"]:
        a0.plot(t, c, color="0.85", lw=0.6)
    a0.plot(t, meta["mean"], color=INK, lw=2.4, label=f"mean of {meta['n_cycles']} cycles")
    for m, r in sorted(real.items(), key=lambda kv: -kv[1]["r2"]):
        if "fitted" in r:
            a0.plot(t, r["fitted"], color=COL.get(m, GREY), lw=1.4, label=f"{m}: R² {r['r2']:.3f}, AIC {r['aic']:.0f}")
    a0.set_xlabel("time from 10 % of a cycle before the drop (s)")
    a0.set_ylabel("mV (chord-detrended)")
    a0.legend(fontsize=7)
    a0.grid(alpha=0.25)
    names = [m for m in COL if m in real]
    for i, m in enumerate(names):
        for j, kind in enumerate(NULL_MK):
            v = [r["r2"] for r in rows if r["train"] == train and r["model"] == m and r["kind"] == kind
                 and r.get("r2") is not None]
            a1.scatter(np.full(len(v), i + (j - 1) * 0.22), v, marker=NULL_MK[kind], s=16, facecolor="none",
                       edgecolor=GREY, label=f"{kind} null" if i == 0 else None)
        a1.scatter([i], [real[m]["r2"]], marker="D", s=40, color=COL[m], zorder=3, label="recording" if i == 0 else None)
    a1.set_xticks(range(len(names)))
    a1.set_xticklabels(names, rotation=30, fontsize=7, ha="right")
    a1.set_ylabel("R²")
    a1.set_ylim(min(-0.05, a1.get_ylim()[0]), 1.02)
    a1.legend(fontsize=7, loc="lower left")
    a1.grid(alpha=0.25)
    a1.set_title("the same fits on fake trains", fontsize=9)
    for j, kind in enumerate(NULL_MK):
        h = (meta["null_height_mV"] or {}).get(kind)
        if h:
            a2.scatter(np.full(len(h), j), h, marker=NULL_MK[kind], facecolor="none", edgecolor=GREY)
    a2.axhline(meta["real_height_mV"], color=INK, lw=2, label="recording")
    a2.set_xticks(range(3))
    a2.set_xticklabels(list(NULL_MK), fontsize=8)
    a2.set_yscale("log")
    a2.set_ylabel("mean-cycle height (mV)")
    a2.legend(fontsize=7)
    a2.set_title("height statistic", fontsize=9)
    fig.suptitle(f"{train}: mean cycle and model fits ({meta['median_cycle_s']:.3g} s median cycle)", fontsize=10)
    fig.tight_layout()
    return _save(fig, path_stem)


def fig_track(train, rows, path_stem):
    mine = [r for r in rows if r["train"] == train]
    models = [m for m in COL if any(r["model"] == m for r in mine)]
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(14, 5))
    for i, m in enumerate(models):
        for j, kind in enumerate(NULL_MK):
            v = [r["pooled_ratio"] for r in mine if r["model"] == m and r["kind"] == kind and r["pooled_ratio"]]
            a0.scatter(np.full(len(v), i + (j - 1) * 0.22), v, marker=NULL_MK[kind], s=18, facecolor="none",
                       edgecolor=GREY, label=f"{kind} null" if i == 0 else None)
        rr = [r for r in mine if r["model"] == m and r["kind"] == "real"]
        if rr and rr[0]["pooled_ratio"]:
            a0.scatter([i], [rr[0]["pooled_ratio"]], marker="D", s=44, color=COL[m], zorder=3,
                       label="recording" if i == 0 else None)
    a0.axhline(1, color=INK, lw=1)
    a0.set_xticks(range(len(models)))
    a0.set_xticklabels(models, rotation=30, fontsize=8, ha="right")
    a0.set_yscale("log")
    a0.set_ylabel("held-out error / neighbours'-mean error (pooled)")
    a0.set_title("below 1 = the model predicts a held-out cycle better than its neighbours' mean", fontsize=9)
    a0.legend(fontsize=7)
    a0.grid(alpha=0.25)
    keys = dict(kernel="decay_frac", fhn_oscillator="alpha", fhn_excitable="alpha", van_der_pol="mu",
                morris_lecar="I", izhikevich="d")
    for m, k in keys.items():
        rr = [r for r in mine if r["model"] == m and r["kind"] == "real"]
        if not rr or k not in rr[0]["params"]:
            continue
        v = np.asarray(rr[0]["params"][k], float)
        if np.isfinite(v).sum() < 3 or np.nanstd(v) == 0:
            continue
        z = (v - np.nanmean(v)) / np.nanstd(v)
        dt = rr[0]["drift"].get(k, {})
        lab = f"{m} {k}: rho {dt.get('rho') or 0:+.2f} (p {dt.get('p_rho') or 1:.2g}), vN p {dt.get('p_sssd') or 1:.2g}"
        a1.plot(np.arange(len(z)), z, marker=".", color=COL[m], lw=1, label=lab)
    a1.set_xlabel("block (cold-start fits)")
    a1.set_ylabel("parameter, z-scored over the train")
    a1.legend(fontsize=7)
    a1.grid(alpha=0.25)
    a1.set_title("drift of the identifiable parameters (shuffle null, 1000 draws)", fontsize=9)
    fig.suptitle(f"{train}: per-cycle held-out tracking", fontsize=10)
    fig.tight_layout()
    return _save(fig, path_stem)


def fig_prc_models(train, prcs, path_stem):
    prcs = [p for p in prcs if p["train"] == train and not p.get("error")]
    if not prcs:
        return []
    fig, axes = plt.subplots(len(prcs), 2, figsize=(12, 3.6 * len(prcs)), squeeze=False,
                             gridspec_kw=dict(width_ratios=[1, 1.4]))
    cmap = plt.get_cmap("hsv")
    for (a0, a1), p in zip(axes, prcs):
        S = np.asarray(p["states"], float)
        ph_s = 2 * np.pi * np.arange(len(S)) / len(S)
        a0.plot(S[:, 1], S[:, 0], color=INK, lw=2.4)
        a0.scatter(S[:, 1], S[:, 0], c=ph_s, cmap="hsv", s=3, vmin=0, vmax=2 * np.pi, zorder=3)
        ph = np.asarray(p["phases"], float)
        g = abs(p["gain_mV_per_unit"])
        rv = np.asarray(p["w_fixed"], float)
        if "w_prc" in p:
            rw = np.asarray(p["w_prc"], float)
            P = np.stack([np.interp(ph, ph_s, S[:, j], period=2 * np.pi) for j in range(2)], axis=1)
            sc = np.array([np.ptp(S[:, 0]), np.ptp(S[:, 1])])
            tv = np.stack([-rw, rv], axis=1) / sc
            tv /= np.linalg.norm(tv, axis=1, keepdims=True)
            tv *= 0.08 * sc
            for k in range(0, len(ph), max(1, len(ph) // 50)):
                a0.plot([P[k, 1] - tv[k, 1], P[k, 1] + tv[k, 1]], [P[k, 0] - tv[k, 0], P[k, 0] + tv[k, 0]],
                        color=cmap(ph[k] / (2 * np.pi)), lw=1.4)
        a0.set_xlabel("hidden variable (model units)")
        a0.set_ylabel("voltage (model units)")
        a0.set_title(f"{p['model']}: limit cycle, isochron ticks by phase", fontsize=9)
        a1.plot(ph, rv / g, color=GREEN, lw=2, label="hidden variable held fixed")
        if "adjoint" in p:
            a1.plot(ph, np.asarray(p["adjoint"], float) / g, color=INK, lw=0.8, ls="--", label="adjoint (check)")
            a1.plot(ph, np.asarray(p["delay_fixed"], float) / g, color=ORANGE, lw=1.5,
                    label="delayed voltage held fixed (0.1 model units)")
            a1.plot(ph, np.asarray(p["quarter_delay_fixed"], float) / g, color=VIOLET, lw=1.3, ls="--",
                    label=f"delayed voltage held fixed (quarter period, {p['quarter_delta']:.3g})")
            a1.plot(ph, np.asarray(p["hidden_linear"], float) / g, color=BLUE, lw=1.3, ls=":",
                    label=f"h = w + {p['hidden_lambda']:.2g} v held fixed")
            core = np.concatenate([rv, np.asarray(p["hidden_linear"], float)]) / g
            lo, hi = np.nanmin(core), np.nanmax(core)
            a1.set_ylim(lo - 0.4 * (hi - lo), hi + 0.4 * (hi - lo))
        a1.axhline(0, color="0.5", lw=0.6)
        _phase_axis(a1)
        a1.set_ylabel("phase response (rad / mV)")
        t = p["type"]
        a1.set_title(f"Type {t['type']} (minority sign {t['minority_fraction']:.2f} of the area); "
                     f"{p['gain_mV_per_unit']:+.3g} mV per model unit", fontsize=9)
        a1.legend(fontsize=7, loc="best")
    fig.suptitle(f"{train}: model PRCs\n{MODEL_NOTE}", fontsize=10)
    fig.tight_layout()
    return _save(fig, path_stem)


def fig_prc_spont(train, sp, prcs, path_stem):
    if not sp or sp.get("skipped"):
        return []
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw=dict(width_ratios=[1.4, 1]))
    ph = np.asarray(sp["phases"])
    Z = np.asarray(sp["Z_rad_per_mV"])
    a0.fill_between(ph, sp["band_lo"], sp["band_hi"], color="#86b6ef", alpha=0.4, label="bootstrap 95 %")
    a0.plot(ph, Z, color=INK, lw=2, marker="o", ms=3, label="estimate Z(phase)")
    for kind, ls in (("shuffle", "-"), ("quiet", ":"), ("surrogate", "--"), ("aaft", "-."), ("timewarp", (0, (1, 3)))):
        if kind in sp["nulls"]:
            q = np.asarray(sp["nulls"][kind]["absZ_q95"])
            a0.plot(ph, q, color=GREY, ls=ls, lw=1, label=f"{kind} null |Z| 95 %")
            a0.plot(ph, -q, color=GREY, ls=ls, lw=1)
    # a bin is reported only when the train's cross-validated R2 also clears every null (else: 20 bins, chance hits)
    clr = np.asarray(sp["bins_clear"], bool) & bool(sp["train_clears"])
    a0.scatter(ph[clr], Z[clr], s=60, facecolor="none", edgecolor=RED, lw=1.5, zorder=4,
               label="clears every null (bin and train)")
    a0.axvline(0.1 * 2 * np.pi, color=RED, lw=0.8, ls=":")
    a0.text(0.1 * 2 * np.pi, a0.get_ylim()[1], " drop", color=RED, fontsize=8, va="top")
    a0.axhline(0, color="0.5", lw=0.6)
    _phase_axis(a0)
    a0.set_xlabel("cycle phase (0 = 10 % of a cycle before the drop)")
    a0.set_ylabel("rad advance per mV of spontaneous deviation")
    nulls = ", ".join(f"{k} q95 {v['cv_r2_q95']:.3f}" for k, v in sp["nulls"].items())
    a0.set_title(f"cv R² {sp['cv_r2']:.3f} ({nulls}); train clears: {sp['train_clears']}", fontsize=8)
    a0.legend(fontsize=7)
    for p in prcs:
        if p["train"] == train and not p.get("error"):
            a1.plot(p["phases"], np.asarray(p["w_fixed"], float) / abs(p["gain_mV_per_unit"]),
                    color=COL.get(p["model"], GREY), lw=1.6, label=f"{p['model']} (Type {p['type']['type']})")
    a1.axhline(0, color="0.5", lw=0.6)
    _phase_axis(a1)
    a1.set_xlabel("model phase (0 = the model's voltage maximum; Izhikevich: its reset)")
    a1.set_ylabel("rad per mV of kick (model)")
    a1.legend(fontsize=7)
    a1.set_title("the fitted models' PRCs, for comparison (other units, other phase origin)", fontsize=8)
    fig.suptitle(f"{train}: {SPONT_NOTE}", fontsize=10)
    fig.tight_layout()
    return _save(fig, path_stem)


def fig_returnmap(train, rm, path_stem):
    if not rm or "raw" not in rm:
        return []
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(11, 5))
    T, Tn = np.asarray(rm["T"]), np.asarray(rm["T_next"])
    a0.scatter(T, Tn, s=12, color=BLUE)
    lim = [min(T.min(), Tn.min()), max(T.max(), Tn.max())]
    a0.plot(lim, lim, color="0.6", lw=0.8)
    a0.set_xlabel("T_i (s)")
    a0.set_ylabel("T_{i+1} (s)")
    r = rm["raw"]
    a0.set_title(f"raw: Spearman {r['rho']:+.2f}, p {r['p_two']:.2g} (shuffle 95 %: {r['null_q025']:+.2f} to "
                 f"{r['null_q975']:+.2f})", fontsize=8)
    a0.grid(alpha=0.25)
    bars = [("raw", r, BLUE)] + ([("drift removed", rm["detrended"], VIOLET)] if "rho" in rm["detrended"] else [])
    a1.bar([b[0] for b in bars], [b[1]["rho"] for b in bars], color=[b[2] for b in bars])
    for i, (_, x, _) in enumerate(bars):
        a1.plot([i - 0.3, i + 0.3], [x["null_q025"]] * 2, color=INK)
        a1.plot([i - 0.3, i + 0.3], [x["null_q975"]] * 2, color=INK)
        a1.text(i, x["rho"], f" p {x['p_two']:.2g}", ha="center", va="bottom", fontsize=8)
    a1.axhline(0, color="0.5", lw=0.6)
    a1.set_ylabel("Spearman rho of T_{i+1} on T_i")
    a1.set_title("black: the shuffle null's 95 % range", fontsize=8)
    fig.suptitle(f"{train}: return map over {rm['n_pairs']} consecutive cycle pairs", fontsize=10)
    fig.tight_layout()
    return _save(fig, path_stem)


def all_figures(out_dir):
    out_dir = Path(out_dir)
    fits, fx = _load(out_dir, "fits")
    track, _ = _load(out_dir, "track")
    prcs, px = _load(out_dir, "prc")
    made = []
    for train, meta in fx.get("trains", {}).items():
        made += fig_fit(train, meta, [r for r in fits if r["train"] == train], out_dir / f"fit_{train}")
        if any(r["train"] == train for r in track):
            made += fig_track(train, track, out_dir / f"track_{train}")
        made += fig_prc_models(train, prcs, out_dir / f"prc_models_{train}")
        made += fig_prc_spont(train, px.get("spontaneous", {}).get(train), prcs, out_dir / f"prc_spont_{train}")
        made += fig_returnmap(train, px.get("return_map", {}).get(train), out_dir / f"returnmap_{train}")
    return made
