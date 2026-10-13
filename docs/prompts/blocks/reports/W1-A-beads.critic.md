# Critic report — W1-A: `preprocessing.beads`

Filed by the manager, 2026-10-13. Verdict: **merge after fixes** (one blocker).

## In plain words

On the test trace it was built against, the block strips the drift and keeps the events, better than a rolling mean,
and both the faithful port and the coarse-grid shortcut hold up. But the default strength of its "events must be rare"
setting was tuned on that one trace and is too weak: when the drift is large compared with the noise, or only two to
three times slower than the chosen period, BEADS files the whole drift under "events" and leaves it in the output —
reporting `converged=True` and no error. Clean recordings with big drift, which is ours, sit right in that zone.

## Findings

- **F1 blocker** — λ scale too weak (normalising by σ/√q). Sine drift + white noise at defaults, baseline error as % of
  drift: σ 0.05 / 3 h / A 5 → 97 % (event fraction 0.99); σ 0.05 / 4 h / A 20 → 84 %; σ 0.01 / 4 h / A 5 → 89 %;
  σ 0.002 / 6 h / A 5 → 22 %; σ 0.002 / 6 h / A 20 → 56 %; the acceptance regime (σ 0.05 / 6 h / A 5) → 0.9 %. AR(0.95)
  noise is worse (BEADS 1.42 vs rolling mean 0.78). `sparsity = 5` rescues the failing cases (4.2 / 1.0 / 1.2 / 11.7 %).
- **F2** — order 1 at defaults leaves 3.83, not the documented 0.37.
- **F3** — bridged NaN gaps degrade the nearby baseline 5–10× (0.48 vs 0.075), unreported.
- **F4 nit** — on event-dominated spans (sharkfin plateau) the baseline sits partway into the events (+0.44 vs the
  rolling mean's +0.86); shape is still far better (0.066 vs 0.208).
- **F5 nit** — short spans hit the iteration cap (honestly reported).

## Checked and fine

The coarse grid neither blurs nor steps (30 s – 1 h drops keep 96.5–100 % depth; it beats a full-resolution solve at
P = 600); "drops 4–8 % deeper" is a metric artefact (no baseline sag); the port matches beads.m line by line and the
dense reference is independent; polarity and ends correct; unit-free; linear cost (2.6 M samples 0.47 s); standards;
test-first. 217 passed. Do not wire BEADS into `signal_threshold` until F1 is fixed.
