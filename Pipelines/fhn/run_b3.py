"""
Round-B B3 ("Modelling common motifs", thesis Chapter 10): the restitution test (B) and per-cycle model
tracking (A).

    python Pipelines/fhn/run_b3.py restitution [--n-perm 1000]
    python Pipelines/fhn/run_b3.py track [--workers 2] [--quiet-draws 2] [--surrogate-draws 2]
    python Pipelines/fhn/run_b3.py figures

Reads the database read-only (sqlite mode=ro) and channel .npy files memory-mapped; writes only under
--out (default docs/thesis/data/ch10_fhn): b3_restitution.json, b3_track.json and b3_*.png/pdf.
M4_aug_concat_fs1 (recordings 49-64) is refused by `data.recording`.
"""

import argparse
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

from Pipelines.fhn import data as D  # noqa: E402
from Pipelines.fhn import fit as F  # noqa: E402
from Pipelines.fhn import izhikevich as IZ  # noqa: E402
from Pipelines.fhn import restitution as R  # noqa: E402
from Pipelines.fhn import track as T  # noqa: E402

OUT = REPO / "docs" / "thesis" / "data" / "ch10_fhn"
N_POINTS = 100
TRACK_SEQUENCES = (3, 7, 22)
BLOCK = {"seq": 3, "chain": 5}
MODELS = ("kernel", "fhn_excitable", "fhn_oscillator", "izhikevich")
DRIFT_PARAMS = {"kernel": ("decay_frac", "rise_frac", "amplitude"),
                "fhn_excitable": ("alpha", "span", "gain", "b", "c"),
                "fhn_oscillator": ("alpha", "time_ratio", "gain", "b", "c"),
                "izhikevich": ("a", "b", "c", "d", "I", "time_ratio", "gain")}
FIT_SETTINGS = dict(osc_restarts_first=2, osc_restarts_warm=1, osc_nfev=80, exc_restarts=1, exc_nfev=100,
                    izh_restarts=3, izh_nfev=150)
SLOW = ("fhn_oscillator", "fhn_excitable")       # run on draw 0 of each null only (compute budget)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _js(o):
    if isinstance(o, dict):
        return {str(k): _js(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_js(v) for v in o]
    if isinstance(o, np.ndarray):
        return _js(o.tolist())
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


# ============================================================================ B. restitution

def _rest_one(ev, n_perm, seed, max_gap=None):
    pairs = R.event_pairs(ev["onset_s"], ev["recovery_time_s"], depth=ev["depth_mv"], width=ev["width_s"],
                          max_gap=max_gap)
    res = R.restitution(pairs, n_perm=n_perm, seed=seed)
    after = R.event_pairs(ev["onset_s"], ev["recovery_time_s"], depth=ev["depth_mv"], width=ev["width_s"],
                          max_gap=max_gap, which="after")
    ctl = R.restitution(after, n_perm=n_perm, seed=seed + 1)
    res["control_gap_after"] = {k: ctl.get(k) for k in ("rho", "p_two", "p_greater", "p_less", "n_perm", "why")}
    head = {k: ev.get(k) for k in ("kind", "id", "key", "species", "label", "recording_id", "source_file", "fs",
                                   "units", "n_events", "n_detections", "w3_detections", "median_gap_s",
                                   "member_check", "run_id", "median_onset_after_window_start_s")
            if ev.get(k) is not None}
    return dict(head, **res, pairs=dict(gap_s=pairs["gap"], recovery_s=pairs["recovery"], depth_mv=pairs["depth"],
                                        width_s=pairs["width"], event_index=pairs["event_index"],
                                        gap_after_s=pairs["gap_after"]))


def _combos(rows):
    out = {key or "raw": R.combine(rows, key=key) for key in
           (None, "partial_depth", "partial_width", "partial_index", "partial_depth_index", "partial_gap_after")}
    out["control_gap_after"] = R.combine([dict(r, **r["control_gap_after"]) for r in rows
                                          if r.get("rho") is not None and r["control_gap_after"].get("rho") is not None])
    return out


def run_restitution(out_dir, n_perm):
    from Pipelines.fhn import b3_data as B
    t0 = time.time()
    res = dict(settings=dict(n_perm=n_perm, min_pairs=R.MIN_PAIRS, recovery="event_shape recovery_time_s "
               "(extremum -> half recovery; searched to the next event, at most 10 event widths)",
               gap="intervals.inter_event_intervals of the onsets (onset to onset)",
               chain_steps=B.CHAIN_STEPS, census_steps=B.CENSUS_STEPS))
    seqs = []
    for sid in B.machine_sequence_ids():
        ev = B.sequence_events(sid)
        seqs.append(_rest_one(ev, n_perm, seed=sid))
    log(f"sequences: {len(seqs)}")
    chains = []
    for k, name in enumerate(B.CHAINS):
        ev = B.chain_events(name)
        chains.append(_rest_one(ev, n_perm, seed=10000 + k, max_gap=ev["max_gap_s"]))
        log(f"chain {name}: {ev['n_events']} events (W3: {ev['w3_detections']}), rho {chains[-1].get('rho')}")
    census = {}
    for corpus, runs in B.census_runs().items():
        rows = []
        for run_id, rec_id, ch in runs:
            ev = B.census_events(run_id, rec_id)
            rows.append(_rest_one(ev, n_perm, seed=run_id))
        census[corpus] = dict(channels=rows, combined=_combos(rows),
                              n_events=int(sum(r.get("n_events") or 0 for r in rows)))
        log(f"census {corpus}: {len(rows)} channels, {census[corpus]['n_events']} events")
    by_species = {}
    for sp in sorted({s.get("species") for s in seqs}):
        by_species[sp] = _combos([s for s in seqs if s.get("species") == sp])
    res["sequences"] = dict(rows=seqs, combined=_combos(seqs), by_species=by_species)
    res["chains"] = dict(rows=chains, combined=_combos(chains))
    res["census"] = census
    res["elapsed_s"] = time.time() - t0
    (out_dir / "b3_restitution.json").write_text(json.dumps(_js(res), indent=1), encoding="utf-8")
    log(f"restitution done in {res['elapsed_s']:.0f} s")
    return res


# ============================================================================ A. tracking

def _fitters():
    """Curve fitters with a warm start carried from block to block (a train's shape moves little)."""
    st = {}

    def kernel(tau, y):
        f = F.fit_jump_exp(tau, y, rise=True)
        return f["fitted"], dict(f["params"], r2=f["r2"])

    def exc(tau, y):
        f = F.fit_excitable(tau, y, restarts=FIT_SETTINGS["exc_restarts"], max_nfev=FIT_SETTINGS["exc_nfev"])
        return f["fitted"], dict(f["params"], r2=f["r2"])

    def osc(tau, y):
        init = st.get("osc")
        f = F.fit_oscillator(tau, y, max_nfev=FIT_SETTINGS["osc_nfev"], init=init,
                             restarts=FIT_SETTINGS["osc_restarts_first" if init is None else "osc_restarts_warm"])
        p = f["params"]
        st["osc"] = [p["u"], p["b"], p["c"], p["time_ratio"], np.nan]
        return f["fitted"], dict(p, r2=f["r2"])

    def izh(tau, y):
        f = IZ.fit_izhikevich(tau, y, restarts=FIT_SETTINGS["izh_restarts"], max_nfev=FIT_SETTINGS["izh_nfev"],
                              init=st.get("izh"))
        p = f["params"]
        st["izh"] = (p["a"], p["b"], p["c"], p["d"], p["I"])
        return f["fitted"], dict(p, r2=f["r2"], n_on_bound=len(f["on_bound"]),
                                 **{f"on_bound_{k}": float(k in f["on_bound"]) for k in IZ.KEYS})

    return {"kernel": kernel, "fhn_excitable": exc, "fhn_oscillator": osc, "izhikevich": izh}


def _task(args):
    name, kind, draw, model, tau, cycles, block, n_perm = args
    t0 = time.time()
    fitter = _fitters()[model]
    h = T.heldout(tau, cycles, fitter, block=block)
    drift = {k: T.drift_test(h["params"][k], n_perm=n_perm, seed=draw) for k in DRIFT_PARAMS[model]
             if k in h["params"]}
    keep_curves = kind == "real"
    out = dict(dataset=name, kind=kind, draw=draw, model=model, block=block, summary=h["summary"],
               ratios=[(r["err_model"] / r["err_base"]) if r["err_base"] and np.isfinite(r["err_model"]) else None
                       for r in h["cycles"]],
               params=h["params"], drift=drift, failures=h["failures"], elapsed_s=time.time() - t0,
               block_r2=h["params"].get("r2"))
    if keep_curves:
        out["curves"] = [None if c is None else c for c in h["curves"]]
        out["block_means"] = h["block_means"]
    return out


def _quiet_cycles(seqlike, L, n, seed):
    W = D.quiet_windows(seqlike, L)
    if len(W) < 8:
        return None, len(W)
    rng = np.random.default_rng(seed)
    pick = rng.choice(W, size=n, replace=len(W) < n)
    rec = seqlike["recording"]
    pad = int(np.ceil(0.2 * L)) + 4
    cs = []
    for s in pick:
        a = int(s + D.PRE_FRAC * L)
        x = D.load_mv(rec, a - pad, a + int(L) + pad)
        c = D.cut_cycle(x, pad, pad + int(L), N_POINTS)
        if c is not None:
            cs.append(c)
    return np.array(cs), len(W)


def _datasets():
    """{name: dict(kind seq|chain, cycles, x, x_start, onsets, seqlike, L)}"""
    from Pipelines.fhn import b3_data as B
    out = {}
    for sid in TRACK_SEQUENCES:
        seq = D.sequence(sid)
        sc = D.sequence_cycles(seq, n_points=N_POINTS)
        out[f"seq{sid}"] = dict(kind="seq", label=seq["key"], cycles=sc["cycles"], x=sc["x"], x_start=sc["x_start"],
                                onsets=seq["onsets"], seqlike=seq, L=sc["median_len_samples"],
                                fs=seq["recording"]["fs"], kept=sc["kept"])
    for name in B.CHAINS:
        ev = B.chain_events(name)
        rec = D.recording(ev["recording_id"])
        on = ev["onset_idx"]
        L = float(np.median(np.diff(on)))
        s0 = max(0, int(on[0] - 2 * L))
        x = D.load_mv(rec, s0, int(on[-1] + 2 * L))
        C, lens, keep = D.cycles(x, on, N_POINTS, x_offset=s0)
        seqlike = dict(recording=rec, store_onsets=ev["wide_onsets"], store_cover=ev["wide_cover"])
        out[name] = dict(kind="chain", label=ev["label"], cycles=C, x=x, x_start=s0, onsets=on, seqlike=seqlike,
                         L=float(np.median(lens)), fs=rec["fs"], kept=keep)
    return out


def run_track(out_dir, workers, q_draws, s_draws, n_perm, only=None):
    t0 = time.time()
    tau = np.arange(N_POINTS) / N_POINTS
    ds = _datasets()
    if only:
        ds = {k: v for k, v in ds.items() if k in only}
    tasks, meta = [], {}
    for name, d in ds.items():
        block = BLOCK[d["kind"]]
        n = len(d["cycles"])
        meta[name] = dict(kind=d["kind"], label=d["label"], n_cycles=n, block=block, median_cycle_s=d["L"] / d["fs"],
                          n_blocks=len(T.blocks(n, block)), real_ptp_mV=float(np.median(np.ptp(d["cycles"], axis=1))))
        sets = [("real", 0, d["cycles"])]
        for k in range(q_draws):
            qc, nw = _quiet_cycles(d["seqlike"], d["L"], n, seed=1000 + k)
            meta[name][f"quiet_windows_available"] = nw
            if qc is not None:
                sets.append(("quiet", k, qc))
        for k in range(s_draws):
            xs = D.phase_randomise(d["x"], np.random.default_rng(2000 + k))
            sc, _, _ = D.cycles(xs, d["onsets"], N_POINTS, x_offset=d["x_start"])
            sets.append(("surrogate", k, sc))
        for kind, draw, C in sets:
            meta[name].setdefault("fake_ptp_mV", {})[f"{kind}{draw}"] = float(np.median(np.ptp(C, axis=1)))
            for model in MODELS:
                if model in SLOW and kind != "real" and draw > 0:
                    continue                  # the slow fits: one draw of each null only (compute budget)
                tasks.append((name, kind, draw, model, tau, C, block, n_perm))
    log(f"track: {len(tasks)} tasks over {len(ds)} datasets, {workers} workers")
    tasks.sort(key=lambda t: (t[3] not in SLOW, -len(t[5])))     # the slow ones first
    results = []
    if workers > 1:
        with mp.get_context("spawn").Pool(workers) as pool:
            for r in pool.imap_unordered(_task, tasks):
                results.append(r)
                log(f"  {r['dataset']} {r['kind']}{r['draw']} {r['model']}: pooled ratio "
                    f"{r['summary']['pooled_ratio']:.3f} ({r['elapsed_s']:.0f} s)")
    else:
        for t in tasks:
            r = _task(t)
            results.append(r)
            log(f"  {r['dataset']} {r['kind']}{r['draw']} {r['model']}: pooled ratio "
                f"{r['summary']['pooled_ratio']:.3f} ({r['elapsed_s']:.0f} s)")
    res = dict(settings=dict(n_points=N_POINTS, block=BLOCK, fit=FIT_SETTINGS, quiet_draws=q_draws,
                             surrogate_draws=s_draws, drift_n_perm=n_perm, workers=workers,
                             note="the FHN fits are run on draw 0 of each null only; the kernel and Izhikevich on every draw"),
               datasets=meta, results=results, elapsed_s=time.time() - t0,
               cpu_s=float(sum(r["elapsed_s"] for r in results)))
    path = out_dir / ("b3_track.json" if not only else f"b3_track_{'_'.join(only)}.json")
    path.write_text(json.dumps(_js(res), indent=1), encoding="utf-8")
    log(f"track done in {res['elapsed_s']:.0f} s wall, {res['cpu_s']:.0f} s fit CPU -> {path}")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("what", choices=("restitution", "track", "figures"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--n-perm", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--quiet-draws", type=int, default=2)
    ap.add_argument("--surrogate-draws", type=int, default=2)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.what == "restitution":
        run_restitution(out_dir, args.n_perm)
    elif args.what == "track":
        run_track(out_dir, min(2, args.workers), args.quiet_draws, args.surrogate_draws, args.n_perm, args.only)
    else:
        from Pipelines.fhn import b3_figures as G
        G.all_figures(out_dir)


if __name__ == "__main__":
    main()
