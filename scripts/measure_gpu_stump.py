"""
measure_gpu_stump.py
====================
Round A_2, P2: does `gpu_stump` (the a100) compute the same matrix profile as
`stump` (the CPU)? The answer decides whether `backend` may leave the step
cache's key. It is IN the key today (`detection.matrix_profile`'s params), so a
profile computed with `gpu_stump` is a separate cache entry from one computed
with `stump`; a template that asks for `auto` shares one entry whichever
backend ran (the backend used is recorded in the run's meta).

Run it on the cluster's GPU node (this PC has no CUDA GPU), e.g. through
`HPC/Detection/measure_gpu_stump.sh`:

    python scripts/measure_gpu_stump.py --sizes 50000,200000 --out logs/gpu_stump_check.json
    python scripts/measure_gpu_stump.py --gpu-only 2596000            # time one whole 721-h channel on the GPU

For each size it builds a coloured synthetic series (a random walk, an AR(1)
stretch at phi 0.97, a slow drift, planted motifs — not white noise), computes
both profiles at m = 60 and m = 600 (1 and 10 minutes at 1 Hz), and prints:

* the time each took;
* the largest absolute and relative difference between the two profiles, and
  the 99.9th percentile of the relative difference;
* the share of nearest-neighbour indices that agree;
* for the thresholds the `mp_threshold` variants use (6, 8, 10), how many
  samples change side of the cut, and how many spans the cut makes each way.

Within float noise (relative differences around 1e-12 to 1e-9, no sample
changing side at 6, 8 or 10) means `backend` could become execution-only:
excluded from the hash and recorded in meta. Anything visible on a cut means it
stays in the key. `--gpu-only N` skips the CPU and times the GPU on N samples:
whether one whole channel fits a 20-minute job (if not, export with the CPU and
let the chain job compute the profile in blocks).
"""

import argparse
import json
import os
import sys
import time

import numpy as np

THRESHOLDS = (6.0, 8.0, 10.0)
WINDOWS = (60, 600)


def series(n, seed=0):
    rng = np.random.default_rng(seed)
    walk = np.cumsum(rng.standard_normal(n)) * 0.01
    ar = np.empty(n)
    ar[0] = 0.0
    e = rng.standard_normal(n) * 0.01
    for i in range(1, n):
        ar[i] = 0.97 * ar[i - 1] + e[i]
    x = walk - np.linspace(walk[0], walk[-1], n) + ar + 0.05 * np.sin(np.linspace(0, 40 * np.pi, n))
    shape = -0.3 * np.exp(-np.linspace(0, 4, 300))
    for a in range(1000, n - 1000, max(5000, n // 50)):
        x[a:a + 300] += shape
    return x


def spans(mask):
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return int(np.sum(d == 1))


def gpu_profile(x, m):
    import numba.cuda
    import stumpy
    if not numba.cuda.is_available():
        raise SystemExit("no CUDA GPU here: run this on the a100 partition")
    ids = [d.id for d in numba.cuda.list_devices()]
    t0 = time.time()
    out = stumpy.gpu_stump(x, m=m, device_id=ids)
    return out, time.time() - t0


def cpu_profile(x, m):
    import stumpy
    t0 = time.time()
    out = stumpy.stump(x, m=m)
    return out, time.time() - t0


def compare(n, m, seed):
    x = series(n, seed)
    cpu, t_cpu = cpu_profile(x, m)
    gpu, t_gpu = gpu_profile(x, m)
    p_c, p_g = cpu[:, 0].astype(float), gpu[:, 0].astype(float)
    i_c, i_g = cpu[:, 1].astype(int), gpu[:, 1].astype(int)
    ok = np.isfinite(p_c) & np.isfinite(p_g)
    diff = np.abs(p_c[ok] - p_g[ok])
    rel = diff / np.maximum(np.abs(p_c[ok]), 1e-12)
    out = {"n": n, "m": m, "cpu_s": round(t_cpu, 2), "gpu_s": round(t_gpu, 2),
           "max_abs_diff": float(diff.max()) if diff.size else 0.0,
           "max_rel_diff": float(rel.max()) if rel.size else 0.0,
           "p999_rel_diff": float(np.quantile(rel, 0.999)) if rel.size else 0.0,
           "same_finite": bool(np.array_equal(np.isfinite(p_c), np.isfinite(p_g))),
           "index_agreement": float(np.mean(i_c == i_g)), "cuts": {}}
    # the profile as the cache holds it: float32 (the adapter casts), then the threshold block's `>` cut
    c32, g32 = p_c.astype(np.float32), p_g.astype(np.float32)
    for thr in THRESHOLDS:
        a, b = c32 > thr, g32 > thr
        out["cuts"][f"{thr:g}"] = {"samples_changing_side": int(np.sum(a != b)),
                                   "spans_cpu": spans(a), "spans_gpu": spans(b)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="stump vs gpu_stump on synthetic coloured series")
    ap.add_argument("--sizes", default="50000,200000", help="comma-separated series lengths")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--gpu-only", type=int, default=None, help="time gpu_stump alone on this many samples")
    ap.add_argument("--out", default=None, help="also write the JSON here")
    args = ap.parse_args(argv)
    import stumpy
    report = {"stumpy": getattr(stumpy, "__version__", "?"), "numpy": np.__version__,
              "node": os.environ.get("SLURMD_NODENAME"), "cpus": os.environ.get("SLURM_CPUS_PER_TASK"), "runs": []}
    if args.gpu_only:
        x = series(int(args.gpu_only), args.seed)
        for m in WINDOWS:
            gpu_profile(x[:20000], m)                      # compile first: the timing is the profile, not the JIT
            _, t = gpu_profile(x, m)
            report["runs"].append({"n": int(args.gpu_only), "m": m, "gpu_s": round(t, 1)})
            print(json.dumps(report["runs"][-1]), flush=True)
    else:
        cpu_profile(series(2000), 50)                      # compile both before timing
        gpu_profile(series(2000), 50)
        for n in (int(v) for v in args.sizes.split(",") if v.strip()):
            for m in WINDOWS:
                r = compare(n, m, args.seed)
                report["runs"].append(r)
                print(json.dumps(r), flush=True)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
