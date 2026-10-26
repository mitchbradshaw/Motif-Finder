"""
Chapter 10 demonstration: fit FitzHugh-Nagumo to recorded drop-cycle shapes, judge the fits
against nulls, and draw the fitted models' PRCs in the manner of Wilshin, Kvalheim & Revzen (2024).

    python Pipelines/fhn/run_ch10.py [--out docs/thesis/data/ch10_fhn] [--null-draws 10]

Reads the database read-only (sqlite mode=ro) and the channel .npy files memory-mapped; writes only
under --out. The held-out recording (M4_aug_concat_fs1, recordings 49-64) is refused by `data`.
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

from Pipelines.fhn import data as D  # noqa: E402
from Pipelines.fhn import figures as G  # noqa: E402
from Pipelines.fhn import fit as F  # noqa: E402
from Pipelines.fhn import model as M  # noqa: E402

SEQUENCES = {
    3: "oyster_id28_ch5_1394131s - M2_aug CH6 (recording 6), 387-407 h: inside the W3 chain_cycles rec 6 chain "
       "(370-470 h); the clearest morph (28/28)",
    7: "oyster_id35_ch15_288397s - M2_aug CH16 (recording 16), 80 h: 18 drops at a 131 s beat (17/17 morph)",
    22: "reishi_id901_ch1_461s - Fig2A CH2 (recording 467), 10 Hz: 57 drops at a ~2 s beat, drifting",
}
PAPER_DELTA = 0.1
EPS = 1e-2
N_BASE = 150
NOISE_SD = 0.005
MODELS = ("fhn_oscillator", "fhn_excitable", "jump_exp", "jump_exp_rise", "sinusoid_1")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def fit_all(tau, y, restarts, seed=0, max_nfev=300):
    out = {}
    out["fhn_oscillator"] = F.fit_oscillator(tau, y, restarts=restarts, seed=seed, max_nfev=max_nfev)
    out["fhn_excitable"] = F.fit_excitable(tau, y, restarts=restarts, seed=seed, max_nfev=max_nfev)
    out["jump_exp"] = F.fit_jump_exp(tau, y, rise=False)
    out["jump_exp_rise"] = F.fit_jump_exp(tau, y, rise=True)
    out["sinusoid_1"] = F.fit_sinusoid(tau, y, 1)
    return out


def best_fhn_r2(fits):
    return max(fits["fhn_oscillator"]["r2"], fits["fhn_excitable"]["r2"])


def summary(f):
    return {k: f[k] for k in ("model", "n", "k", "rss", "rmse", "nrmse", "r2", "aic")} | {
        "params": {k: (float(v) if not isinstance(v, list) else v) for k, v in f["params"].items()}}


def prc_bundle(alpha, b, c, eps=EPS, n_base=N_BASE, seed=0):
    cyc = M.limit_cycle(M.fhn(a=alpha, b=b, c=c, z=0.0), n=2000)
    pr = M.delay_prcs(cyc, delta=PAPER_DELTA, eps=eps, n_base=n_base)
    prq = M.delay_prcs(cyc, delta=cyc.T / 4, eps=eps, n_base=n_base)
    Z = M.prc_adjoint(cyc)
    adj_v = np.interp(pr["phases"], cyc.phases, Z[:, 0], period=2 * np.pi)
    oph, ov = M.simulated_noisy_prc(cyc, n_obs=500, eps=0.05, noise_sd=NOISE_SD, seed=seed)
    g, med = M.rolling_median(oph, ov)
    noisy = dict(phases=oph, values=ov, median_phase=g, median=med)
    return cyc, pr, prq, adj_v, noisy


def prc_stats(pr, adj_v):
    ok = pr["well_conditioned"]
    gt = pr["ground_truth"]
    return dict(min=float(gt.min()), max=float(gt.max()), n_base=int(len(gt)), n_ill_conditioned=int((~ok).sum()),
                max_abs_adjoint_minus_gt=float(np.max(np.abs(adj_v - gt))),
                max_abs_constant_delay_minus_gt=float(np.nanmax(np.abs(pr["constant_delay"] - gt)[ok])),
                max_abs_corrected_minus_gt=float(np.nanmax(np.abs(pr["corrected"] - gt)[ok])),
                delta_model_units=pr["delta"], hidden_lambda=pr["hidden_lambda"])


def paper_reproduction(out_dir):
    log("paper FHN: period, PRCs, figures")
    cyc, pr, prq, adj_v, noisy = prc_bundle(M.PAPER["a"] + M.PAPER["b"] * M.PAPER["z"], M.PAPER["b"], M.PAPER["c"])
    a = np.deg2rad(-9.5)
    _, rot = M.prc_perturbation(cyc, [np.cos(a), np.sin(a)], eps=EPS, n_base=N_BASE)
    note = "the paper's model with its parameters (simulated; eq. 17 coordinates, not the figure code's rotated ones)"
    figs = G.fig_cycle_isochrons(cyc, pr, prq, "Reference: the paper's FHN (a=0.7, b=0.8, c=3, z=-0.4)",
                                 out_dir / "paper_fhn_fig1_style", note=note)
    figs += G.fig_prc(pr, adj_v, noisy, "Reference: the paper's FHN, voltage PRC (Fig. 4 style)",
                      out_dir / "paper_fhn_fig4_style", note=note)
    return dict(period=float(cyc.T), appendix_b_guess=3 * 3.743, prc=prc_stats(pr, adj_v),
                prc_on_paper_figure_axis=dict(min=float(rot.min()), max=float(rot.max()),
                                              note="perturbation along the release code's figure axis (rotated "
                                                   "-9.5 degrees about the fixed point); Fig. 4 reads ~-2.2..2.6"),
                figures=figs)


def piecewise_chord(x, onsets, x_start, k):
    a = np.asarray(onsets) - x_start
    lv = np.array([np.median(x[max(0, i - k):i + 1]) for i in a])
    t = np.arange(len(x))
    return x - np.interp(t, a, lv), a


def delay_panels(seqc, seq, osc, L_s, fs, cyc_fast):
    p = osc["params"]
    k_model_per_s = p["time_ratio"] * cyc_fast.T / L_s
    on = seq["onsets"]
    kk = max(2, int(round(0.05 * seqc["median_len_samples"])))
    xd, a = piecewise_chord(seqc["x"], on, seqc["x_start"], kk)
    i0, i1 = int(a[0]), int(a[-1])
    t = np.arange(i0, i1)
    k_idx = np.clip(np.searchsorted(a, t, side="right") - 1, 0, len(a) - 2)
    Lk = a[k_idx + 1] - a[k_idx]
    tau = ((t - a[k_idx]) / Lk + D.PRE_FRAC) % 1.0
    phase = np.mod(2 * np.pi * p["time_ratio"] * tau + p["phase_shift"], 2 * np.pi)
    th = np.linspace(0, 2 * np.pi, 600)
    panels = []
    for label, d_samp in (("paper's delay", max(1, int(round(PAPER_DELTA / k_model_per_s * fs)))),
                          ("quarter cycle", max(1, int(round(seqc["median_len_samples"] / 4))))):
        d_model = d_samp / fs * k_model_per_s
        sel = t - d_samp >= 0
        mv = F.oscillator_model(th / (2 * np.pi), cyc_fast, 1.0, 0.0)
        mvd = F.oscillator_model(th / (2 * np.pi), cyc_fast, 1.0, -2 * np.pi * d_model / cyc_fast.T)
        panels.append(dict(x=xd[t[sel]], xd=xd[t[sel] - d_samp], phase=phase[sel],
                           mx=p["offset"] + p["gain"] * mv, mxd=p["offset"] + p["gain"] * mvd,
                           label=f"{label}: delta = {d_samp / fs:.3g} s = {d_model:.3g} model units",
                           delta_s=d_samp / fs, delta_model=d_model))
    return panels


def run_sequence(sid, out_dir, n_null, restarts, null_nfev=300):
    seq = D.sequence(sid)
    rec = seq["recording"]
    fs = rec["fs"]
    seqc = D.sequence_cycles(seq)
    tau, y = seqc["tau"], seqc["mean"]
    L_s = seqc["median_len_samples"] / fs
    log(f"seq {sid} {seq['key']}: {len(seqc['cycles'])} cycles of median {L_s:.1f} s; fitting")
    fits = fit_all(tau, y, restarts=restarts)
    for n, f in fits.items():
        log(f"   {n:16s} R2 {f['r2']:.4f} AIC {f['aic']:.1f}")

    # nulls
    nulls = {k: {m: [] for m in MODELS + ("fhn_gain_over_sinusoid",)} for k in ("quiet", "surrogate")}
    qmeans, n_windows = D.quiet_null_means(seq, len(seqc["cycles"]), seqc["median_len_samples"], n_null, seed=sid)
    smeans = D.surrogate_null_means(seqc, seq, n_null, seed=sid)
    null_ptp = {"quiet": [], "surrogate": []}
    for kind, means in (("quiet", qmeans), ("surrogate", smeans)):
        if means is None:
            continue
        for i, m in enumerate(means):
            nf = fit_all(tau, m, restarts=2, seed=100 + i, max_nfev=null_nfev)
            for name in MODELS:
                nulls[kind][name].append(float(nf[name]["r2"]))
            nulls[kind]["fhn_gain_over_sinusoid"].append(float(best_fhn_r2(nf) - nf["sinusoid_1"]["r2"]))
            null_ptp[kind].append(float(np.ptp(m)))
        log(f"   {kind} null: {len(means)} draws, FHN-osc R2 max {max(nulls[kind]['fhn_oscillator']):.3f}")

    osc, exc = fits["fhn_oscillator"], fits["fhn_excitable"]
    regime = "excitable" if exc["aic"] < osc["aic"] else "oscillatory"
    best = min(fits.values(), key=lambda f: f["aic"])["model"]
    real_stat = {m: fits[m]["r2"] for m in MODELS}
    real_stat["fhn_gain_over_sinusoid"] = best_fhn_r2(fits) - fits["sinusoid_1"]["r2"]
    verdict = {}
    for name, real in real_stat.items():
        v = dict(real=float(real))
        for kind in ("quiet", "surrogate"):
            r = nulls[kind][name]
            if r:
                v[kind] = dict(draws=len(r), null_max=max(r), null_median=float(np.median(r)),
                               beats_every_draw=bool(real > max(r)))
        verdict[name] = v

    # PRC of the oscillatory fit
    p = osc["params"]
    cyc, pr, prq, adj_v, noisy = prc_bundle(p["alpha"], p["b"], p["c"], seed=sid)
    cyc_fast = F.fast_cycle(p["alpha"], p["b"], p["c"])
    gain = p["gain"]
    model_period_s = L_s / p["time_ratio"]
    stem = out_dir / f"seq{sid}"
    pref = "" if regime == "oscillatory" else " (AIC prefers the EXCITABLE regime, which has no PRC)"
    title = f"seq {sid} {seq['key']}: oscillatory FHN fit{pref}"
    units = (f"\n1 model voltage unit = {abs(gain):.3g} mV (gain {gain:+.3g}); 1 model time unit = "
             f"{model_period_s / cyc.T:.3g} s")
    figs = G.fig_fit(tau * L_s, seqc["cycles"], y, fits, nulls,
                     f"seq {sid} {seq['key']} ({seq['species']}): mean cycle and fits; regime by AIC: {regime}; "
                     f"best of all by AIC: {best}", f"{stem}_fit")
    figs += G.fig_cycle_isochrons(cyc, pr, prq, title, f"{stem}_fig1_style")
    figs += G.fig_prc(pr, adj_v, noisy, title, f"{stem}_fig4_style", units_note=units)
    panels = delay_panels(seqc, seq, osc, L_s, fs, cyc_fast)
    figs += G.fig_delay(panels, f"seq {sid} {seq['key']}: the recording's cycles; black = the oscillatory FHN fit",
                        f"{stem}_delay")
    ps = prc_stats(pr, adj_v)
    ps["rad_per_mV"] = dict(min=float(min(pr["ground_truth"].min() / gain, pr["ground_truth"].max() / gain)),
                            max=float(max(pr["ground_truth"].min() / gain, pr["ground_truth"].max() / gain)))
    ps["seconds_advance_per_mV_max"] = float(np.max(np.abs(pr["ground_truth"] / gain)) * model_period_s / (2 * np.pi))
    return dict(id=sid, key=seq["key"], description=SEQUENCES[sid], species=seq["species"], recording_id=rec["id"],
                source_file=rec["source_file"], stored_channel=rec["channel"], fs=fs, units=rec["units"],
                n_events=seq["n_events"], n_cycles=int(len(seqc["cycles"])), median_cycle_s=L_s,
                mean_cycle_ptp_mV=float(np.ptp(y)), fits={k: summary(v) for k, v in fits.items()},
                delta_aic_vs_best={k: float(v["aic"] - min(f["aic"] for f in fits.values())) for k, v in fits.items()},
                regime_by_aic=regime, best_model_by_aic=best,
                nulls=dict(r2=nulls, quiet_windows_available=int(n_windows),
                           mean_ptp_mV={k: (float(np.median(v)) if v else None) for k, v in null_ptp.items()},
                           verdict=verdict),
                oscillatory_fit_physical=dict(model_period_s=model_period_s,
                                              model_time_unit_s=model_period_s / cyc.T, mV_per_model_unit=gain,
                                              refined_model_period=float(cyc.T)),
                prc_of_oscillatory_fit=ps, delay_views=[{k: pp[k] for k in ("label", "delta_s", "delta_model")}
                                                        for pp in panels],
                figures=figs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO / "docs" / "thesis" / "data" / "ch10_fhn"))
    ap.add_argument("--null-draws", type=int, default=10)
    ap.add_argument("--restarts", type=int, default=8)
    ap.add_argument("--only", type=int, nargs="*", default=None)
    ap.add_argument("--null-nfev", type=int, default=300, help="least-squares budget per null fit")
    ap.add_argument("--merge", action="store_true",
                    help="keep the other sequences (and the paper block) of an existing results.json")
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    res = dict(reference="Wilshin, Kvalheim & Revzen (2024) Biol Cybern 118:311-330, doi:10.1007/s00422-024-00997-w",
               caveat="Every PRC here is the PRC of a fitted MODEL. No perturbation experiment was made on any "
                      "recording; the PRCs say how the fitted FHN would respond, not how the fungus does.",
               identifiability="a and z enter v(t) only through alpha = a + b z; a is reported with z = -0.4",
               settings=dict(eps=EPS, n_base=N_BASE, paper_delta=PAPER_DELTA, null_draws=args.null_draws,
                             restarts=args.restarts, n_points=D.N_POINTS, pre_frac=D.PRE_FRAC, gap_rule=D.GAP_RULE,
                             simulated_noise_sd_model_units=NOISE_SD))
    old = None
    if args.merge and (out_dir / "results.json").exists():
        old = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
    res["paper_fhn"] = old["paper_fhn"] if old else paper_reproduction(out_dir)
    todo = list(args.only or SEQUENCES)
    res["sequences"] = [s for s in (old or {}).get("sequences", []) if s["id"] not in todo]
    for s_old in res["sequences"]:
        s_old.setdefault("settings", old["settings"] | {"null_nfev": 300})
    for sid in todo:
        r = run_sequence(sid, out_dir, args.null_draws, args.restarts, args.null_nfev)
        r["settings"] = dict(null_draws=args.null_draws, restarts=args.restarts, null_nfev=args.null_nfev)
        res["sequences"].append(r)
        res["sequences"].sort(key=lambda s: s["id"])
        (out_dir / "results.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    res["elapsed_s"] = time.time() - t0
    (out_dir / "results.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    log(f"done in {res['elapsed_s']:.0f} s -> {out_dir / 'results.json'}")


if __name__ == "__main__":
    main()
