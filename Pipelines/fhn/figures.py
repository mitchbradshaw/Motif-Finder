"""
Figures in the manner of Wilshin, Kvalheim & Revzen (2024), doi:10.1007/s00422-024-00997-w:

* `fig_cycle_isochrons` — their Fig. 1: the limit cycle in the (gating, voltage) plane, short
  isochron ticks coloured by phase on a cyclic rainbow (hsv) map, and the voltage PRC in several
  coordinate systems against phase 0-2 pi, with the ill-conditioned phases barred in grey.
* `fig_prc` — their Fig. 4: ground truth (green), a rolling median of simulated noisy
  observations (black), "constant delay" (orange) and "corrected" (red), and a residual subplot.
* `fig_delay` — their Fig. 3/5 view: the RECORDING's own cycles in delay coordinates
  (V(t), V(t - delta)), coloured by cycle phase, with the fitted model's loop over them.
* `fig_fit` — the fits themselves and their nulls.

Every PRC figure is the PRC of a fitted MODEL: no perturbation experiment was made on any
recording, and the titles say so.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from Pipelines.fhn import model as M  # noqa: E402

GREEN, ORANGE, RED, BLUE, VIOLET, GREY, INK = "#008300", "#eb6834", "#e34948", "#2a78d6", "#6250d6", "#8a8984", "#0b0b0b"
MODEL_ONLY = "MODEL PRC of the fitted FHN - not a measured PRC (no perturbation experiments)"
PI_TICKS = ([0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi], ["0", "π/2", "π", "3π/2", "2π"])


def _save(fig, path_stem):
    fig.savefig(str(path_stem) + ".png", dpi=150)
    fig.savefig(str(path_stem) + ".pdf")
    plt.close(fig)
    return [str(path_stem) + ".png", str(path_stem) + ".pdf"]


def _phase_axis(ax):
    ax.set_xlim(0, 2 * np.pi)
    ax.set_xticks(*PI_TICKS)
    ax.set_xlabel("phase (rad)")
    ax.grid(alpha=0.25, lw=0.6)


def _bars(ax, ph, ok):
    for p in ph[~ok]:
        ax.axvspan(p - 0.02, p + 0.02, color="0.6", alpha=0.5, lw=0)


def _clip_to(ax, keep, others, pad=0.35):
    """y-limits fitted to the `keep` curves; any `others` leaving the panel are named on it."""
    k = np.concatenate([np.ravel(c) for c in keep])
    lo, hi = np.nanmin(k), np.nanmax(k)
    r = hi - lo
    lo, hi = lo - pad * r, hi + pad * r
    ax.set_ylim(lo, hi)
    o = np.concatenate([np.ravel(c) for c in others])
    if np.nanmin(o) < lo or np.nanmax(o) > hi:
        ax.text(0.01, 0.02, f"constant-delay curves leave the panel (range {np.nanmin(o):.3g} to {np.nanmax(o):.3g})",
                transform=ax.transAxes, fontsize=7.5, color=ORANGE)


def fig_cycle_isochrons(cycle, prcs, prcs_quarter, title, path_stem, n_ticks=60, note=MODEL_ONLY):
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw=dict(width_ratios=[1, 1.25]))
    v, w = cycle.states[:, 0], cycle.states[:, 1]
    ph, rv, rw = prcs["phases"], prcs["ground_truth"], prcs["w_prc"]
    sel = np.unique(np.linspace(0, len(ph) - 1, n_ticks).astype(int))
    scale = (np.ptp(v), np.ptp(w))
    ticks = M.isochron_ticks(cycle, ph[sel], rv[sel], rw[sel], length=0.09, scale=scale)
    cmap = plt.get_cmap("hsv")
    for seg, p in zip(ticks, ph[sel]):
        a0.plot(seg[:, 1], seg[:, 0], color=cmap(p / (2 * np.pi)), lw=1.6)
    a0.plot(w, v, color=INK, lw=3)
    a0.scatter(w, v, c=cycle.phases, cmap="hsv", s=2, zorder=3, vmin=0, vmax=2 * np.pi)
    a0.set_xlabel("w (gating variable, model units)")
    a0.set_ylabel("v (voltage, model units)")
    a0.set_title("limit cycle; ticks along the isochrons, coloured by phase", fontsize=10)
    sm = plt.cm.ScalarMappable(cmap="hsv", norm=plt.Normalize(0, 2 * np.pi))
    cb = fig.colorbar(sm, ax=a0, fraction=0.046, pad=0.02, ticks=PI_TICKS[0])
    cb.ax.set_yticklabels(PI_TICKS[1])
    cb.set_label("phase")

    ok = prcs["well_conditioned"]
    a1.plot(ph, rv, color=GREEN, lw=2, label="w held fixed (the FHN's own coordinates)")
    a1.plot(ph, np.where(ok, prcs["constant_delay"], np.nan), color=ORANGE, lw=2,
            label=f"v_d held fixed, delay {prcs['delta']:.3g} model units")
    okq = prcs_quarter["well_conditioned"]
    cdq = np.where(okq, prcs_quarter["constant_delay"], np.nan)
    a1.plot(prcs_quarter["phases"], cdq, color=VIOLET, lw=1.6, ls="--",
            label=f"v_d held fixed, delay {prcs_quarter['delta']:.3g} (quarter period)")
    a1.plot(ph, prcs["hidden_linear"], color=BLUE, lw=1.6, ls=":",
            label=f"h = w + {prcs['hidden_lambda']:.2f} v held fixed (linear change)")
    _bars(a1, ph, ok)
    cd = np.where(ok, prcs["constant_delay"], np.nan)
    _clip_to(a1, [rv, prcs["hidden_linear"]], [cd, cdq])
    _phase_axis(a1)
    a1.set_ylabel("v phase response (rad per model voltage unit)")
    a1.legend(fontsize=8, loc="best")
    a1.set_title("the same model's voltage PRC depends on what is held fixed", fontsize=10)
    fig.suptitle(f"{title}\n{MODEL_ONLY}", fontsize=10)
    fig.tight_layout()
    return _save(fig, path_stem)


def fig_prc(prcs, adjoint_v, noisy, title, path_stem, units_note="", note=MODEL_ONLY):
    ph, gt = prcs["phases"], prcs["ground_truth"]
    ok = prcs["well_conditioned"]
    fig, (a0, a1) = plt.subplots(2, 1, figsize=(9, 8), sharex=True, gridspec_kw=dict(height_ratios=[1.3, 1]))
    obs_ph, obs = noisy["phases"], noisy["values"]
    lo, hi = np.nanpercentile(obs, [1, 99])
    keep = (obs > lo - (hi - lo)) & (obs < hi + (hi - lo))
    a0.scatter(obs_ph[keep], obs[keep], s=4, color="#86b6ef", alpha=0.5, lw=0,
               label="simulated noisy model observations (phase change)")
    g, med = noisy["median_phase"], noisy["median"]
    a0.plot(g, med, color=INK, lw=1.2, label="median phase change")
    a0.plot(ph, gt, color=GREEN, lw=3, label="small perturbation, w held fixed (ground truth of the model)")
    a0.plot(ph, adjoint_v, color=BLUE, lw=1, ls="--", label="adjoint (independent check)")
    cd = np.where(ok, prcs["constant_delay"], np.nan)
    co = np.where(ok, prcs["corrected"], np.nan)
    a0.plot(ph, cd, color=ORANGE, lw=1.2, marker="+", ms=5, label="constant delay (v_d held fixed)")
    a0.plot(ph, co, color=RED, lw=1.2, marker=".", ms=4, label="corrected (Jacobian of (v, w) -> (v, v_d); assumes w fixed)")
    _bars(a0, ph, ok)
    _clip_to(a0, [gt, adjoint_v, co], [cd])
    a0.set_ylabel("infinitesimal phase response\n(rad per model voltage unit)")
    a0.legend(fontsize=7.5, loc="best")
    a0.grid(alpha=0.25, lw=0.6)
    gt_med = np.interp(g, ph, gt, period=2 * np.pi)
    a1.scatter(obs_ph[keep], obs[keep] - np.interp(obs_ph[keep], ph, gt, period=2 * np.pi), s=4, color="#86b6ef",
               alpha=0.5, lw=0)
    a1.plot(g, med - gt_med, color=INK, lw=1.2)
    a1.plot(ph, adjoint_v - gt, color=BLUE, lw=1, ls="--")
    a1.plot(ph, cd - gt, color=ORANGE, lw=1.2, marker="+", ms=5)
    a1.plot(ph, co - gt, color=RED, lw=1.2, marker=".", ms=4)
    a1.axhline(0, color=GREEN, lw=2)
    span = np.nanmax(np.abs(gt))
    a1.set_ylim(-0.6 * span, 0.6 * span)
    a1.set_ylabel("residual against the ground truth")
    _bars(a1, ph, ok)
    _phase_axis(a1)
    fig.suptitle(f"{title}\n{MODEL_ONLY}{units_note}", fontsize=9.5)
    fig.tight_layout()
    return _save(fig, path_stem)


def fig_delay(panels, title, path_stem):
    """panels: list of dicts with x, xd (data delay pairs, mV), phase (rad), mx, mxd (model loop),
    label."""
    fig, axes = plt.subplots(1, len(panels), figsize=(5.6 * len(panels), 5.2))
    axes = np.atleast_1d(axes)
    for ax, p in zip(axes, panels):
        ax.scatter(p["xd"], p["x"], c=p["phase"], cmap="hsv", vmin=0, vmax=2 * np.pi, s=3, alpha=0.6, lw=0)
        ax.plot(p["mxd"], p["mx"], color=INK, lw=2.2, label="fitted FHN, mapped to mV")
        ax.set_xlabel("V(t - delta), mV (detrended)")
        ax.set_ylabel("V(t), mV (detrended)")
        ax.set_title(p["label"], fontsize=9)
        ax.grid(alpha=0.25, lw=0.6)
        ax.legend(fontsize=8, loc="best")
    fig.suptitle(f"{title}\nrecorded cycles in delay coordinates, coloured by cycle phase (hsv)", fontsize=10)
    fig.tight_layout()
    return _save(fig, path_stem)


def fig_fit(tau_s, cycles, mean, fits, nulls, title, path_stem):
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw=dict(width_ratios=[1.6, 1]))
    for c in cycles:
        a0.plot(tau_s, c, color="0.82", lw=0.6)
    a0.plot(tau_s, mean, color=INK, lw=2.4, label=f"mean of {len(cycles)} recorded cycles")
    styles = dict(fhn_oscillator=(BLUE, "-"), fhn_excitable=(VIOLET, "-"), jump_exp_rise=(ORANGE, "--"),
                  sinusoid_1=(GREY, ":"))
    for name, (col, ls) in styles.items():
        if name in fits:
            f = fits[name]
            a0.plot(tau_s, f["fitted"], color=col, ls=ls, lw=1.8,
                    label=f"{name}: R² {f['r2']:.3f}, AIC {f['aic']:.0f}")
    a0.set_xlabel("time from 10 % of a cycle before the drop (s)")
    a0.set_ylabel("mV (each cycle chord-detrended)")
    a0.grid(alpha=0.25, lw=0.6)
    a0.legend(fontsize=8, loc="best")
    names = [n for n in styles if n in fits]
    for i, name in enumerate(names):
        for j, (kind, mk) in enumerate((("quiet", "o"), ("surrogate", "s"))):
            vals = nulls.get(kind, {}).get(name)
            if vals:
                a1.scatter(np.full(len(vals), i + (j - 0.5) * 0.25), vals, marker=mk, s=18, facecolor="none",
                           edgecolor=GREY, label=f"{kind} null" if i == 0 else None)
        a1.scatter([i], [fits[name]["r2"]], marker="D", s=40, color=styles[name][0], zorder=3,
                   label="recording" if i == 0 else None)
    a1.set_xticks(range(len(names)))
    a1.set_xticklabels(names, rotation=20, fontsize=8)
    a1.set_ylabel("R² of the fit")
    a1.set_ylim(min(-0.05, a1.get_ylim()[0]), 1.02)
    a1.grid(alpha=0.25, lw=0.6)
    a1.legend(fontsize=8, loc="lower left")
    a1.set_title("the same fits on what noise gives", fontsize=9)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    return _save(fig, path_stem)
