"""
b3_long_rec6_abs_time.py - the check on research prompt 01's one positive result: does rec 6's spontaneous
phase-timing correlation survive when its cycles are cut in ABSOLUTE time?

empirical_prc.estimate resamples every cycle to a fixed number of points, so a longer cycle is a stretched view of
the same waveform and looks different at any given phase (the trap run_long.timewarp_cycles was built for). Here:
  * the phase estimate is re-run exactly as run_long.run_prc ran it (shuffle null only), to show it reproduces;
  * each kept cycle is cut instead as a fixed window of plain seconds around its own onset, -0.1 to +0.5 of the
    median cycle (the gap rule keeps cycles of 0.6-1.6 medians, so every window ends before the next drop), minus
    the pre-onset level, in 12 bins of 0.05 medians; the same estimator, the same timing residuals dT;
  * the phase estimate on 10 draws of the time-warp null, for comparison.
The fake-train nulls (quiet, phase-scrambled, AAFT) are not rerun in absolute time.

Read-only: run_long.datasets reads the channel memory-mapped and runs the chain rule's detection in memory.
Writes docs/thesis/data/ch10_fhn_long/rec6_abs_time.json.
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from Pipelines.fhn import empirical_prc as E  # noqa: E402
from Pipelines.fhn import run_long as RL  # noqa: E402

NAME = "rec6_370_470h"
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_fhn_long", "rec6_abs_time.json")
PRE, POST, N_POINTS, N_BINS = 0.1, 0.5, 120, 12


def absolute_cycles(x, onsets, kept, med):
    """Fixed windows of plain samples around each kept cycle's onset, minus its pre-onset level."""
    k5 = max(2, int(round(0.05 * med)))
    rows = []
    for k in kept:
        a = onsets[k]
        pos = a - PRE * med + (PRE + POST) * med * np.arange(N_POINTS) / N_POINTS
        y = np.interp(pos, np.arange(len(x)), x)
        rows.append(y - np.median(x[max(0, a - k5):a + 1]))
    return np.asarray(rows)


def main():
    ds, _ = RL.datasets(only=[NAME])
    d = ds[NAME]
    c, fs = d["c100"], d["fs"]
    on = np.asarray(d["onsets"], int) - c["x_start"]
    kept, L = np.asarray(c["kept"]), c["lengths"]
    med = float(np.median(L))

    phase = E.estimate(c["cycles"], L, kept=kept, n_shuffle=500, n_boot=200, seed=11, fs=fs)
    A = absolute_cycles(c["x"], on, kept, med)
    absolute = E.estimate(A, L, kept=kept, n_shuffle=500, n_boot=200, seed=11, fs=fs, n_bins=N_BINS)
    rng = np.random.default_rng(4000)
    tw = [E.estimate(RL.timewarp_cycles(d, rng), L, kept=kept, n_shuffle=50, n_boot=10, seed=1, fs=fs)["cv_r2"]
          for _ in range(10)]

    edges_s = [(-PRE + 0.05 * b) * med / fs for b in range(N_BINS + 1)]
    out = dict(train=NAME, median_cycle_s=med / fs, n_used=absolute["n_used"],
               phase=dict(cv_r2=phase["cv_r2"], shuffle_q95=phase["nulls"]["shuffle"]["cv_r2_q95"],
                          Z_rad_per_mV=phase["Z_rad_per_mV"], band_lo=phase["band_lo"], band_hi=phase["band_hi"]),
               absolute=dict(cv_r2=absolute["cv_r2"], shuffle_q95=absolute["nulls"]["shuffle"]["cv_r2_q95"],
                             bin_edges_s_from_onset=edges_s, Z_rad_per_mV=absolute["Z_rad_per_mV"],
                             band_lo=absolute["band_lo"], band_hi=absolute["band_hi"]),
               timewarp_phase_cv_r2=dict(median=float(np.median(tw)), max=float(np.max(tw)), draws=len(tw)))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"phase cv R2 {out['phase']['cv_r2']:.3f} (shuffle q95 {out['phase']['shuffle_q95']:.3f}); "
          f"absolute {out['absolute']['cv_r2']:.3f} (shuffle q95 {out['absolute']['shuffle_q95']:.3f}); "
          f"time-warp phase median {out['timewarp_phase_cv_r2']['median']:.3f}")
    for b in range(N_BINS):
        print(f"  {edges_s[b]:6.0f}..{edges_s[b + 1]:5.0f} s: Z {absolute['Z_rad_per_mV'][b]:6.2f}  "
              f"band {absolute['band_lo'][b]:6.2f}..{absolute['band_hi'][b]:5.2f}")


if __name__ == "__main__":
    main()
