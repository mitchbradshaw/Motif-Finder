"""
Research prompt 01 (B3's follow-up): neuron models on the longest drop trains, with phase-response curves.

    python Pipelines/fhn/run_long.py regress     # seq 3, 7, 22 mean-cycle fits + the B3 tracking, as before
    python Pipelines/fhn/run_long.py trains      # every train's events and extent (the chain rule), bursts
    python Pipelines/fhn/run_long.py fits        # A: mean-cycle fits of every model, with the three nulls
    python Pipelines/fhn/run_long.py track       # B: per-cycle held-out tracking + cold-start drift tests
    python Pipelines/fhn/run_long.py prc         # C: model PRCs and the spontaneous phase-timing estimate
    python Pipelines/fhn/run_long.py figures

Everything is kept comparable with `run_ch10.py` and `run_b3.py`: the same cycle cutting (data.cut_cycle, drop at
tau = 0.1, chord detrend, gap rule 0.6-1.6 x median), N_POINTS 200 for mean cycles and 100 for tracking, the same
quiet and phase-scrambled nulls, the same fitters at the same settings; AAFT is added as its own null column.

Reads the database read-only (sqlite mode=ro) and channel .npy files memory-mapped; writes only under --out
(default docs/thesis/data/ch10_fhn_long). M4_aug_concat_fs1 is refused by `data.recording`; Schizophyllum
commune, L_R and F2B are never touched (no train here is on them, and `_guard` refuses them by name).
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

OUT = REPO / "docs" / "thesis" / "data" / "ch10_fhn_long"
FORBIDDEN = ("Schizophyllum", "M4_aug_concat_fs1", "L_R", "F2B")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _guard(rec):
    if any(f in rec["source_file"] for f in FORBIDDEN):
        raise PermissionError(f"{rec['source_file']} is not to be read")
    return rec


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
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def _write(out_dir, name, obj):
    p = Path(out_dir) / name
    p.write_text(json.dumps(_js(obj), indent=1), encoding="utf-8")
    return p


# ============================================================================ pure helpers

def train_extent(onsets, seed, max_gap):
    """The chain rule's train around a seed span: onsets split wherever a gap exceeds max_gap; the train
    with the most onsets inside the seed span is taken. `n_trains_overlapping_seed` > 1 means the seed
    straddles a break - the extent would then be a judgement, and the caller must say so."""
    on = np.sort(np.asarray(onsets, float))
    cuts = np.nonzero(np.diff(on) > max_gap)[0]
    starts = np.r_[0, cuts + 1]
    stops = np.r_[cuts, on.size - 1]
    inside = [(int(np.sum((on[a:b + 1] >= seed[0]) & (on[a:b + 1] <= seed[1]))), a, b) for a, b in zip(starts, stops)]
    hit = [t for t in inside if t[0] > 0]
    if not hit:
        return dict(n_events=0, n_trains_overlapping_seed=0, start=None, stop=None)
    n_in, a, b = max(hit)
    return dict(n_events=int(b - a + 1), start=float(on[a]), stop=float(on[b]), first_index=int(a),
                last_index=int(b), n_trains_overlapping_seed=len(hit), n_in_seed=n_in)


def aaft_cycles(x, onsets, x_start, rng, n_points=D.N_POINTS):
    """An AAFT copy of the stretch (the value distribution kept, the timing scrambled), cut at the real
    onsets by the same pipeline as the recording."""
    from Adapters.preprocessing_surrogate import aaft_surrogate
    xs = aaft_surrogate(np.asarray(x, float), rng)
    C, _, _ = D.cycles(xs, onsets, n_points, x_offset=x_start)
    return C


def aaft_null_means(seqc, onsets, n_draws, seed=0, n_points=D.N_POINTS):
    rng = np.random.default_rng(seed + 3000)
    return np.array([aaft_cycles(seqc["x"], onsets, seqc["x_start"], rng, n_points).mean(axis=0)
                     for _ in range(n_draws)])


# ============================================================================ regression check

def run_regress(out_dir, workers):
    """seq 3, 7, 22 mean-cycle fits (run_ch10.fit_all, 8 restarts) and the B3 held-out tracking of the six
    datasets (run_b3's warm-started fitters, real cycles only) - the numbers the prompt quotes."""
    from Pipelines.fhn import run_b3 as RB
    from Pipelines.fhn import run_ch10 as RC
    t0 = time.time()
    res = dict(mean_cycle={}, expected=dict(
        fhn_oscillator={3: 0.873, 7: 0.971, 22: 0.997}, fhn_excitable={3: 0.931, 7: 0.981, 22: 0.996},
        track_rec6=dict(kernel=1.08, fhn_excitable=1.34, fhn_oscillator=1.29, izhikevich=1.46)))
    old = json.loads((REPO / "docs/thesis/data/ch10_fhn/results.json").read_text(encoding="utf-8"))
    old_r2 = {s["id"]: {k: v["r2"] for k, v in s["fits"].items()} for s in old["sequences"]}
    for sid in (3, 7, 22):
        seq = D.sequence(sid)
        sc = D.sequence_cycles(seq)
        fits = RC.fit_all(sc["tau"], sc["mean"], restarts=8)
        res["mean_cycle"][sid] = dict(n_cycles=int(len(sc["cycles"])),
                                      r2={k: f["r2"] for k, f in fits.items()}, r2_before=old_r2.get(sid))
        log(f"regress seq {sid}: " + ", ".join(f"{k} {f['r2']:.4f}" for k, f in fits.items()))
        _write(out_dir, "regression.json", res)
    tr = RB.run_track(Path(out_dir), workers, 0, 0, 1000)
    old_t = json.loads((REPO / "docs/thesis/data/ch10_fhn/b3_track.json").read_text(encoding="utf-8"))
    before = {(r["dataset"], r["model"]): r["summary"]["pooled_ratio"] for r in old_t["results"] if r["kind"] == "real"}
    res["track"] = [dict(dataset=r["dataset"], model=r["model"], pooled_ratio=r["summary"]["pooled_ratio"],
                         median_ratio=r["summary"]["median_ratio"], before=before.get((r["dataset"], r["model"])),
                         elapsed_s=r["elapsed_s"]) for r in tr["results"]]
    res["track_datasets"] = tr["datasets"]
    res["elapsed_s"] = time.time() - t0
    _write(out_dir, "regression.json", res)
    log(f"regression done in {res['elapsed_s']:.0f} s")
    return res


# ============================================================================ the trains

SEQS = (20, 1, 21, 22, 2, 3, 6, 7)
CHAIN_NAMES = ("rec6_370_470h", "rec3_490_540h", "rec542_370_490h")
WIDEN_H = 48.0
MAX_WIDEN = 4
CANDIDATES = {
    "seq122": dict(recording_id=1, span_s=(1749416.0, 1758658.0), pad_h=0.5,
                   why="origin 'annotation' (a span marked by hand; needs_extraction = 1): no stored events, so the "
                       "chain rule is run on the span (+-0.5 h for the detrend) and its events are the train"),
    "mju26a_692": dict(recording_id=692, span_s=(314.0 * 3600, 322.0 * 3600), pad_h=WIDEN_H,
                       why="B10's ~20 min oscillation at 314-322 h, extended by the chain rule (span +-48 h)"),
}
RULE = ("Chain rule (the chain_cycles template's first steps, b3_data.CHAIN_STEPS): rolling-mean detrend 600 s, "
        "noise_threshold 4 sigma below (sigma over the whole run span), minimum 30 s, merge 60 s, Event shape onsets; "
        "a train ends where a gap exceeds 3 h. A W3 chain 'continues past its span' only when its own-span train "
        "comes within 3 h of a span edge; it is then re-run on a span widened by 48 h each side (up to 4 times) "
        "until the train ends at least 3 h inside both edges, and the train holding the original train's events is "
        "taken. A new train (seq 122, MJu26a) is the chain rule's train around its seed span; fewer than 20 "
        "events = no train under the rule (not fitted).")


def _register(name, rec_id, span_h, label):
    from Pipelines.fhn import b3_data as B
    B.CHAINS[name] = dict(recording_id=rec_id, span_h=(max(0.0, span_h[0]), span_h[1]), w3_events=None, label=label)


def chain_train(name):
    """(events dict, rule record) for a W3 chain, extended by the rule where it continues past its span."""
    from Pipelines.fhn import b3_data as B
    ch = B.CHAINS[name]
    gap = B.CHAIN_STEPS["train_gap_s"]
    ev = B.chain_events(name)
    on = ev["onset_s"]
    s0, s1 = ch["span_h"][0] * 3600, ch["span_h"][1] * 3600
    ext = train_extent(on, (s0, s1), gap)
    rec = dict(name=name, span_h=list(ch["span_h"]), own_span_events=int(ev["n_events"]), own_train=ext,
               touches_edge=bool(ext["start"] - s0 < gap or s1 - ext["stop"] < gap))
    if not rec["touches_edge"]:
        rec["decision"] = "kept as W3/B3 cut it (all the span's events): the train ends > 3 h inside both edges"
        return ev, rec, name
    seed = (ext["start"], ext["stop"])
    n_samples_h = D.recording(ch["recording_id"])["n_samples"] / D.recording(ch["recording_id"])["fs"] / 3600
    span = list(ch["span_h"])
    for k in range(1, MAX_WIDEN + 1):
        span = [max(0.0, span[0] - WIDEN_H), min(n_samples_h, span[1] + WIDEN_H)]
        nm = f"{name}_ext"
        _register(nm, ch["recording_id"], span, ch["label"] + f" - extended by the chain rule ({span[0]:.0f}-{span[1]:.0f} h run)")
        evw = B.chain_events(nm)
        e2 = train_extent(evw["onset_s"], seed, gap)
        inside = (e2["start"] - span[0] * 3600 >= gap or span[0] == 0.0) and \
                 (span[1] * 3600 - e2["stop"] >= gap or span[1] == n_samples_h)
        prev = rec.get("widenings", [])[-1]["train"] if rec.get("widenings") else None
        rec.setdefault("widenings", []).append(dict(run_span_h=list(span), events=int(evw["n_events"]), train=e2))
        stable = prev is not None and abs(prev["start"] - e2["start"]) <= gap and abs(prev["stop"] - e2["stop"]) <= gap
        if inside and stable:
            break
    else:
        # sigma is computed over the whole run span, so a wider run moves the cut: when successive widenings
        # disagree on where the train ends, the extent is set by the chosen span, not by the rule
        rec["decision"] = ("kept as W3/B3 cut it: the extended train's extent changes with the run span "
                           "(successive widenings disagree), so the rule does not decide it")
        rec["extension_unstable"] = True
        return ev, rec, name
    a, b = e2["first_index"], e2["last_index"]
    for key in ("onset_idx", "extremum_idx", "onset_s", "recovery_time_s", "depth_mv", "width_s", "duration_s"):
        evw[key] = evw[key][a:b + 1]
    evw["n_events"] = int(b - a + 1)
    rec["decision"] = (f"extended: the train runs {e2['start'] / 3600:.2f}-{e2['stop'] / 3600:.2f} h "
                       f"({e2['n_events']} events) on a {span[0]:.0f}-{span[1]:.0f} h run")
    rec["n_trains_overlapping_seed"] = e2["n_trains_overlapping_seed"]
    return evw, rec, f"{name}_ext"


def candidate_train(key):
    from Pipelines.fhn import b3_data as B
    c = CANDIDATES[key]
    gap = B.CHAIN_STEPS["train_gap_s"]
    rec = _guard(D.recording(c["recording_id"]))
    span_h = (c["span_s"][0] / 3600 - c["pad_h"], c["span_s"][1] / 3600 + c["pad_h"])
    _register(key, c["recording_id"], span_h, f"{key}: {rec['source_file']} ch{rec['channel']}")
    ev = B.chain_events(key, wide_h=0.0)
    ext = train_extent(ev["onset_s"], c["span_s"], gap)
    return dict(key=key, why=c["why"], run_span_h=list(span_h), events_in_run=int(ev["n_events"]), train=ext,
                fitted=bool(ext["n_events"] >= 20),
                decision=("a train" if ext["n_events"] >= 20 else
                          f"NOT a train under the rule: {ext['n_events']} event(s) in its extent"))


def _cycles_of(rec, on, n_points):
    L = float(np.median(np.diff(on)))
    s0 = max(0, int(on[0] - 2 * L))
    x = D.load_mv(rec, s0, int(on[-1] + 2 * L))
    C, lens, keep = D.cycles(x, on, n_points, x_offset=s0)
    return dict(x=x, x_start=s0, cycles=C, lengths=lens, kept=keep, mean=C.mean(axis=0),
                tau=np.arange(n_points) / n_points, median_len_samples=float(np.median(lens)))


def datasets(only=None):
    """{name: train dict} for every train the rule admits; plus the rule records."""
    from Pipelines.fhn import b3_data as B
    from Pipelines.fhn import hindmarsh_rose as HR
    out, records = {}, dict(rule=RULE, chains=[], candidates=[], sequences=[])
    for sid in SEQS:
        name = f"seq{sid}"
        if only and name not in only:
            continue
        seq = D.sequence(sid)
        _guard(seq["recording"])
        out[name] = dict(kind="seq", block=3, label=seq["key"], species=seq["species"], rec=seq["recording"],
                         onsets=seq["onsets"], seqlike=seq)
        records["sequences"].append(dict(name=name, key=seq["key"], events=int(seq["n_events"])))
    for nm in CHAIN_NAMES:
        if only and not any(o.startswith(nm) for o in only):
            continue
        ev, rr, name = chain_train(nm)
        rec = _guard(D.recording(ev["recording_id"]))
        seqlike = dict(recording=rec, store_onsets=ev["wide_onsets"], store_cover=ev["wide_cover"])
        out[name] = dict(kind="chain", block=5, label=ev["label"], species=None, rec=rec, onsets=ev["onset_idx"],
                         seqlike=seqlike)
        records["chains"].append(rr)
    if not only:
        for key in CANDIDATES:
            records["candidates"].append(candidate_train(key))
    for name, d in out.items():
        # the same stretch and cutting as data.sequence_cycles (onsets -/+ 2 median gaps) for every train
        d["c200"] = _cycles_of(d["rec"], d["onsets"], 200)
        d["c100"] = _cycles_of(d["rec"], d["onsets"], 100)
        d["bursts"] = HR.burst_structure(d["onsets"])
        d["fs"] = d["rec"]["fs"]
    return out, records


def run_trains(out_dir):
    ds, records = datasets()
    rows = []
    for name, d in ds.items():
        on = d["onsets"]
        rows.append(dict(name=name, kind=d["kind"], label=d["label"], recording_id=d["rec"]["id"],
                         source_file=d["rec"]["source_file"], stored_channel=d["rec"]["channel"], fs=d["fs"],
                         units=d["rec"]["units"], n_events=int(len(on)), start_h=float(on[0] / d["fs"] / 3600),
                         stop_h=float(on[-1] / d["fs"] / 3600), n_cycles_200=int(len(d["c200"]["cycles"])),
                         n_cycles_100=int(len(d["c100"]["cycles"])),
                         median_cycle_s=float(d["c100"]["median_len_samples"] / d["fs"]), bursts=d["bursts"]))
        log(f"{name}: {len(on)} events, {rows[-1]['n_cycles_100']} cycles, {rows[-1]['median_cycle_s']:.1f} s; "
            f"bursts: {d['bursts']['why']}")
    records["trains"] = rows
    records["hindmarsh_rose"] = dict(fitted_on=[r["name"] for r in rows if r["bursts"]["bursting"]],
                                     rule="hindmarsh_rose.burst_structure (split at 3 x median gap; >= 3 groups of "
                                          ">= 3 drops; long gaps >= 5 % of gaps)")
    _write(out_dir, "trains.json", records)
    return records


# ============================================================================ A. mean-cycle fits

MEAN_MODELS = ("kernel", "jump_exp", "sinusoid_1", "fhn_oscillator", "fhn_excitable", "izhikevich", "van_der_pol",
               "morris_lecar")
FAST = ("kernel", "jump_exp", "sinusoid_1")
SLOW_NULL_DRAWS = 3


def mean_fit(model, tau, y, null):
    from Pipelines.fhn import fit as F
    from Pipelines.fhn import izhikevich as IZ
    from Pipelines.fhn import morris_lecar as ML
    from Pipelines.fhn import van_der_pol as V
    if model == "kernel":
        return F.fit_jump_exp(tau, y, rise=True)
    if model == "jump_exp":
        return F.fit_jump_exp(tau, y, rise=False)
    if model == "sinusoid_1":
        return F.fit_sinusoid(tau, y, 1)
    if model == "fhn_oscillator":
        return F.fit_oscillator(tau, y, restarts=2 if null else 8, max_nfev=60 if null else 300)
    if model == "fhn_excitable":
        return F.fit_excitable(tau, y, restarts=2 if null else 8, max_nfev=60 if null else 300)
    if model == "izhikevich":
        return IZ.fit_izhikevich(tau, y, restarts=3 if null else 5, max_nfev=100 if null else 200)
    if model == "van_der_pol":
        return V.fit_vdp(tau, y, restarts=2 if null else 4, max_nfev=80 if null else 200)
    if model == "morris_lecar":
        return ML.fit_ml(tau, y, restarts=1 if null else 3, max_nfev=60 if null else 150)
    raise KeyError(model)


def _summ(f, keep_fit):
    out = {k: f.get(k) for k in ("model", "n", "k", "rss", "r2", "aic", "on_bound", "class")}
    out["params"] = {k: v for k, v in f["params"].items() if not isinstance(v, list)}
    if "by_class" in f:
        out["by_class"] = {c: dict(r2=v["r2"], aic=v["aic"]) for c, v in f["by_class"].items()}
    if keep_fit:
        out["fitted"] = f["fitted"]
    return out


def _fit_task(args):
    train, kind, draw, model, tau, y = args
    t0 = time.time()
    try:
        f = _summ(mean_fit(model, tau, y, null=kind != "real"), keep_fit=kind == "real")
    except Exception as e:
        f = dict(model=model, error=f"{type(e).__name__}: {e}", r2=None, aic=None)
    f["fit_model"] = f.pop("model")                  # the fitter's own name (kernel = jump_exp_rise)
    return dict(train=train, kind=kind, draw=draw, model=model, elapsed_s=time.time() - t0, **f)


def _pool_map(fn, tasks, workers, label):
    out = []
    if workers > 1:
        with mp.get_context("spawn").Pool(workers) as pool:
            for r in pool.imap_unordered(fn, tasks):
                out.append(r)
                log(f"  {label} {r.get('train')} {r.get('kind')}{r.get('draw', '')} {r.get('model')}: "
                    f"{r.get('r2', r.get('pooled_ratio'))} ({r.get('elapsed_s', 0):.0f} s)")
    else:
        for t in tasks:
            r = fn(t)
            out.append(r)
            log(f"  {label} {r.get('train')} {r.get('kind')}{r.get('draw', '')} {r.get('model')}: "
                f"{r.get('r2', r.get('pooled_ratio'))} ({r.get('elapsed_s', 0):.0f} s)")
    return out


def null_means(d, n_draws, seed):
    c = d["c200"]
    n = len(c["cycles"])
    q, nw = D.quiet_null_means(d["seqlike"], n, c["median_len_samples"], n_draws, seed=seed)
    s = D.surrogate_null_means(c, dict(onsets=d["onsets"]), n_draws, seed=seed)
    a = aaft_null_means(c, d["onsets"], n_draws, seed=seed)
    return dict(quiet=q, surrogate=s, aaft=a), nw


def run_fits(out_dir, workers, only=None, models=MEAN_MODELS):
    t0 = time.time()
    ds, records = datasets(only)
    tasks, meta = [], {}
    for k, (name, d) in enumerate(ds.items()):
        c = d["c200"]
        n = len(c["cycles"])
        n_draws = 10 if n < 60 else 5
        nm, nw = null_means(d, n_draws, seed=100 + k)
        meta[name] = dict(n_cycles=n, null_draws=n_draws, quiet_windows=int(nw), real_height_mV=float(np.ptp(c["mean"])),
                          null_height_mV={kk: (None if v is None else np.ptp(v, axis=1).tolist()) for kk, v in nm.items()},
                          median_cycle_s=c["median_len_samples"] / d["fs"], mean=c["mean"],
                          tau_s=(c["tau"] * c["median_len_samples"] / d["fs"]),
                          cycles_sample=c["cycles"][:: max(1, n // 40)])
        for model in models:
            tasks.append((name, "real", 0, model, c["tau"], c["mean"]))
            for kind, means in nm.items():
                if means is None:
                    continue
                for i, m in enumerate(means):
                    if model not in FAST and i >= SLOW_NULL_DRAWS:
                        continue
                    tasks.append((name, kind, i, model, c["tau"], m))
    slow_first = {"fhn_oscillator": 0, "morris_lecar": 1, "fhn_excitable": 2, "izhikevich": 3, "van_der_pol": 4}
    tasks.sort(key=lambda t: (t[1] != "real", slow_first.get(t[3], 9)))
    log(f"fits: {len(tasks)} tasks over {len(ds)} trains")
    res = _pool_map(_fit_task, tasks, workers, "fit")
    out = dict(settings=dict(n_points=200, slow_null_draws=SLOW_NULL_DRAWS, fast_models=FAST,
                             real=dict(fhn_restarts=8, fhn_nfev=300, izh=(5, 200), vdp=(4, 200), ml=(3, 150)),
                             null=dict(fhn_restarts=2, fhn_nfev=60, izh=(3, 100), vdp=(2, 80), ml=(1, 60))),
               trains=meta, results=res, elapsed_s=time.time() - t0, cpu_s=float(sum(r["elapsed_s"] for r in res)))
    fn = "fits.json" if not only else f"fits_{'_'.join(only)}.json"
    _write(out_dir, fn, out)
    log(f"fits done in {out['elapsed_s']:.0f} s wall, {out['cpu_s']:.0f} s CPU")
    return out


def load_fits(out_dir):
    """Every fits*.json merged: {train: {model: real fit}} and the full rows."""
    rows, trains = [], {}
    for p in sorted(Path(out_dir).glob("fits*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        rows += j["results"]
        trains.update(j["trains"])
    real = {}
    for r in rows:
        if r["kind"] == "real":
            real.setdefault(r["train"], {})[r["model"]] = r
    return real, rows, trains


# ============================================================================ B. tracking (cold starts)

TRACK_MODELS = ("kernel", "sinusoid_1", "fhn_excitable", "fhn_oscillator", "izhikevich", "van_der_pol", "morris_lecar")
TRACK_SLOW = ("fhn_excitable", "fhn_oscillator", "izhikevich", "van_der_pol", "morris_lecar")
DRIFT = {"kernel": ("decay_frac", "rise_frac", "amplitude"), "sinusoid_1": (),
         "fhn_excitable": ("alpha", "span", "gain"), "fhn_oscillator": ("alpha", "time_ratio", "gain"),
         "izhikevich": ("a", "d", "I", "gain"), "van_der_pol": ("mu", "time_ratio", "gain"),
         "morris_lecar": ("I", "phi", "gain")}


def track_fitter(model, init):
    """Cold-start block fitters: every block starts from the same point (the train's own mean-cycle fit), so
    no block's estimate leans on its predecessor's (B3's warm starts made the drift tests invalid)."""
    from Pipelines.fhn import fit as F
    from Pipelines.fhn import izhikevich as IZ
    from Pipelines.fhn import morris_lecar as ML
    from Pipelines.fhn import van_der_pol as V

    def wrap(f):
        return f["fitted"], dict(f["params"], r2=f["r2"])

    if model == "kernel":
        return lambda tau, y: wrap(F.fit_jump_exp(tau, y, rise=True))
    if model == "sinusoid_1":
        return lambda tau, y: wrap(F.fit_sinusoid(tau, y, 1))
    if model == "fhn_excitable":
        return lambda tau, y: wrap(F.fit_excitable(tau, y, restarts=1, max_nfev=100))
    if model == "fhn_oscillator":
        p = init["fhn_oscillator"]["params"]
        st = [p["u"], p["b"], p["c"], p["time_ratio"], np.nan]
        return lambda tau, y: wrap(F.fit_oscillator(tau, y, restarts=1, max_nfev=80, init=st))
    if model == "izhikevich":
        p = init["izhikevich"]["params"]
        st = (p["a"], p["b"], p["c"], p["d"], p["I"])
        return lambda tau, y: wrap(IZ.fit_izhikevich(tau, y, restarts=2, max_nfev=150, init=st))
    if model == "van_der_pol":
        st = (init["van_der_pol"]["params"]["mu"],)
        return lambda tau, y: wrap(V.fit_vdp(tau, y, restarts=1, max_nfev=80, init=st))
    if model == "morris_lecar":
        f0 = init["morris_lecar"]
        cls = f0["class"]
        st = {cls: (f0["params"]["I"], f0["params"]["phi"])}
        return lambda tau, y: wrap(ML.fit_ml(tau, y, restarts=1, max_nfev=80, classes=(cls,), init=st))
    raise KeyError(model)


def _track_task(args):
    from Pipelines.fhn import track as T
    train, kind, draw, model, tau, C, block, init = args
    t0 = time.time()
    h = T.heldout(tau, C, track_fitter(model, init), block=block)
    drift = {k: T.drift_test(h["params"][k], n_perm=1000, seed=draw) for k in DRIFT[model] if k in h["params"]}
    out = dict(train=train, kind=kind, draw=draw, model=model, block=block, summary=h["summary"],
               pooled_ratio=h["summary"]["pooled_ratio"], params=h["params"], drift=drift, failures=h["failures"],
               ratios=[(r["err_model"] / r["err_base"]) if r["err_base"] and np.isfinite(r["err_model"]) else None
                       for r in h["cycles"]], elapsed_s=time.time() - t0)
    return out


def _quiet_cycles(d, n, seed, n_points=100):
    from Pipelines.fhn import run_b3 as RB
    old = RB.N_POINTS
    RB.N_POINTS = n_points
    try:
        return RB._quiet_cycles(d["seqlike"], d["c100"]["median_len_samples"], n, seed)
    finally:
        RB.N_POINTS = old


def fake_cycles_100(d, n_draws, seed0=0):
    """{kind: [cycle arrays]} at N = 100: quiet windows, phase-scrambled and AAFT copies cut at the real onsets."""
    c = d["c100"]
    n = len(c["cycles"])
    out = {"quiet": [], "surrogate": [], "aaft": []}
    for k in range(n_draws):
        qc, _ = _quiet_cycles(d, n, seed=1000 + seed0 + k)
        out["quiet"].append(qc)
        xs = D.phase_randomise(c["x"], np.random.default_rng(2000 + seed0 + k))
        out["surrogate"].append(D.cycles(xs, d["onsets"], 100, x_offset=c["x_start"])[0])
        out["aaft"].append(aaft_cycles(c["x"], d["onsets"], c["x_start"], np.random.default_rng(3000 + seed0 + k), 100))
    return out


def run_track(out_dir, workers, only=None, n_draws=2, models=TRACK_MODELS):
    t0 = time.time()
    real_fits, _, _ = load_fits(out_dir)
    ds, _ = datasets(only)
    tasks, meta = [], {}
    tau = np.arange(100) / 100
    for name, d in ds.items():
        init = real_fits.get(name, {})
        C = d["c100"]["cycles"]
        fakes = fake_cycles_100(d, n_draws)
        meta[name] = dict(n_cycles=int(len(C)), block=d["block"], median_cycle_s=d["c100"]["median_len_samples"] / d["fs"])
        sets = [("real", 0, C)] + [(k, i, v) for k, vs in fakes.items() for i, v in enumerate(vs) if v is not None]
        for kind, draw, CC in sets:
            for model in models:
                if model in TRACK_SLOW and kind != "real" and draw > 0:
                    continue
                if model in ("fhn_oscillator", "izhikevich", "van_der_pol", "morris_lecar") and \
                        (model not in init or init[model].get("error")):
                    continue
                tasks.append((name, kind, draw, model, tau, CC, d["block"], init))
    tasks.sort(key=lambda t: (t[3] not in TRACK_SLOW, t[1] != "real", -len(t[5])))
    log(f"track: {len(tasks)} tasks over {len(ds)} trains")
    res = _pool_map(_track_task, tasks, workers, "track")
    out = dict(settings=dict(n_points=100, null_draws=n_draws, slow_models_on_draw0_only=TRACK_SLOW,
                             starts="cold: every block from the train's own mean-cycle fit (A)",
                             fit=dict(fhn_osc=(1, 80), fhn_exc=(1, 100), izh=(2, 150), vdp=(1, 80), ml=(1, 80))),
               trains=meta, results=res, elapsed_s=time.time() - t0, cpu_s=float(sum(r["elapsed_s"] for r in res)))
    fn = "track.json" if not only else f"track_{'_'.join(only)}.json"
    _write(out_dir, fn, out)
    log(f"track done in {out['elapsed_s']:.0f} s wall, {out['cpu_s']:.0f} s CPU")
    return out


# ============================================================================ C. PRCs

PRC_MODELS = ("fhn_oscillator", "van_der_pol", "morris_lecar", "izhikevich")
PAPER_DELTA = 0.1


def _prc_task(args):
    from Pipelines.fhn import model as M
    from Pipelines.fhn import morris_lecar as ML
    from Pipelines.fhn import oscfit as O
    from Pipelines.fhn import van_der_pol as V
    train, model, fitres, n_base = args
    t0 = time.time()
    p = fitres["params"]
    gain = p["gain"]
    try:
        if model == "izhikevich":
            r = O.izhikevich_prc(p["a"], p["b"], p["c"], p["d"], p["I"], n_base=n_base)
            out = dict(phases=r["phases"], w_fixed=r["ground_truth"], agreement=None,
                       note="hybrid model (reset): u held fixed only; no adjoint, no delay coordinates; phase 0 = reset")
            cyc_states = np.stack([r["orbit"]["v"], r["orbit"]["u"]], axis=1)
        else:
            osc = (M.fhn(a=p["alpha"], b=p["b"], c=p["c"], z=0.0) if model == "fhn_oscillator" else
                   V.vdp(p["mu"]) if model == "van_der_pol" else
                   ML.morris_lecar(p["I"], p["phi"], fitres["class"]))
            cyc, pr, prq, adj, agree = O.prc_bundle(osc, delta=PAPER_DELTA, n_base=n_base,
                                                    eps=1e-2 if model == "fhn_oscillator" else None)
            out = dict(phases=pr["phases"], w_fixed=pr["ground_truth"], adjoint=adj,
                       delay_fixed=np.where(pr["well_conditioned"], pr["constant_delay"], np.nan),
                       quarter_delay_fixed=np.where(prq["well_conditioned"], prq["constant_delay"], np.nan),
                       quarter_delta=prq["delta"], hidden_linear=pr["hidden_linear"], hidden_lambda=pr["hidden_lambda"],
                       w_prc=pr["w_prc"], agreement=agree)
            cyc_states = cyc.states
        T_model = p["model_period"]
        cycle_s = fitres.get("cycle_s")
        out.update(train=train, model=model, gain_mV_per_unit=gain, states=cyc_states[:: max(1, len(cyc_states) // 400)],
                   type=O.prc_type(out["w_fixed"]),
                   type_delay=(O.prc_type(out["delay_fixed"]) if "delay_fixed" in out and
                               np.isfinite(out["delay_fixed"]).sum() > 10 else None),
                   rad_per_mV=dict(min=float(np.nanmin(out["w_fixed"]) / abs(gain)),
                                   max=float(np.nanmax(out["w_fixed"]) / abs(gain))),
                   sign_note="per mV of a kick in the recorded direction: divided by gain (negative gain flips v)",
                   model_period=T_model, cycle_s=cycle_s, elapsed_s=time.time() - t0)
        return out
    except Exception as e:
        return dict(train=train, model=model, error=f"{type(e).__name__}: {e}", elapsed_s=time.time() - t0)


def run_prc(out_dir, workers, only=None, n_base=100, n_null=20, n_shuffle=500):
    from Pipelines.fhn import empirical_prc as E
    t0 = time.time()
    real_fits, _, trains_meta = load_fits(out_dir)
    tasks = []
    for train, fits in real_fits.items():
        if only and train not in only:
            continue
        for m in PRC_MODELS:
            if m in fits and not fits[m].get("error"):
                f = dict(fits[m], cycle_s=trains_meta[train]["median_cycle_s"])
                tasks.append((train, m, f, n_base))
    log(f"prc: {len(tasks)} model PRCs")
    models = _pool_map(_prc_task, tasks, workers, "prc")
    ds, _ = datasets(only)
    spont, rmap = {}, {}
    for name, d in ds.items():
        c = d["c100"]
        rmap[name] = E.return_map(c["lengths"] / d["fs"], kept=c["kept"], n_shuffle=n_shuffle, seed=7)
        if len(c["cycles"]) >= E.MIN_CYCLES:
            fakes = fake_cycles_100(d, n_null, seed0=500)
            spont[name] = E.estimate(c["cycles"], c["lengths"], kept=c["kept"], fake_cycles=fakes, n_shuffle=n_shuffle,
                                     n_boot=500, seed=11, fs=d["fs"])
            log(f"  spontaneous {name}: cv R2 {spont[name]['cv_r2']:.3f}, clears {spont[name]['train_clears']}, "
                f"{spont[name]['n_bins_clear']} bins clear")
        else:
            spont[name] = dict(skipped=f"{len(c['cycles'])} cycles (needs {E.MIN_CYCLES})")
    out = dict(settings=dict(n_base=n_base, paper_delta=PAPER_DELTA, spont_fake_draws=n_null, n_shuffle=n_shuffle,
                             bins=E.N_BINS, half=E.HALF),
               models=models, spontaneous=spont, return_map=rmap, elapsed_s=time.time() - t0)
    fn = "prc.json" if not only else f"prc_{'_'.join(only)}.json"
    _write(out_dir, fn, out)
    log(f"prc done in {out['elapsed_s']:.0f} s")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("what", choices=("regress", "trains", "fits", "track", "prc", "figures"))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--models", nargs="*", default=None)
    args = ap.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    w = min(2, args.workers)
    if args.what == "regress":
        run_regress(out_dir, w)
    elif args.what == "trains":
        run_trains(out_dir)
    elif args.what == "fits":
        run_fits(out_dir, w, args.only, tuple(args.models or MEAN_MODELS))
    elif args.what == "track":
        run_track(out_dir, w, args.only, models=tuple(args.models or TRACK_MODELS))
    elif args.what == "prc":
        run_prc(out_dir, w, args.only)
    else:
        from Pipelines.fhn import long_figures as G
        G.all_figures(out_dir)


if __name__ == "__main__":
    main()
