# Critic report — W1-B: `detection.deconvolve` + `detection.impulse_events`

Filed by the manager, 2026-10-13. Verdict: **merge after fixes** (one blocker in the defaults, not the solver).

## In plain words

The maths engine is sound: given the right "how fast does a trough recover" number it finds every sudden drop, separates
overlapping pairs and ignores pure noise. The default asks the block to guess that number itself, and the guess only
works on clean, undrifted data with ~2-minute recoveries — behind the template's own detrend, or with recoveries of 5
minutes or more, it guesses 40–60 s and one trough turns into dozens of events. Sharkfins fragment heavily even with the
right setting, and the description does not say so.

## Findings

- **F1 blocker** — the recovery estimate collapses on a non-constant baseline. Template defaults on 30 drifting troughs:
  true half 60 s → 58 s, 31 events; 120 s → 117 s, 30; **300 s → 48 s, 740 events; 600 s → 51 s, 1072** (30 each with
  the true half given). Slow troughs (1200 s): 495 events for 6; dense (every 300 s): ~6000 for 142. The test covered
  only 120 s without drift.
- **F2** — a quiet channel (white noise, a ramp) raises "cannot estimate the recovery" instead of reporting 0 events.
- **F3** — sharkfins: 14–42 events per fin with the half given, 100–180 estimated; every fall found; residual SD
  1.9–2.6; not warned.
- **F4** — σ from first differences underestimates coloured noise (AR(1) φ = 0.95 → ~0.22 of the true SD; 16.5
  events/h on event-free AR noise with the half given).
- **F5** — the running baseline never converges in 10 passes (results still right); only deep in `meta`.
- **F6 nit** — the thresholded and AR(2) forms are greedy (suboptimal in 55 % of tiny brute-force problems, median RSS
  gap 5 %).
- **F7 nit** — a drop on the first sample after a NaN gap is absorbed into `initial_levels`.
- **F8 nit** — consecutive spans overlap by `pre_s`; `threshold` has no `min`.
- **F9 nit** — no cost declared (2.6 M samples: 3.8–14.7 s).

## Checked and fine

Unpenalised AR(1) equals NNLS to 2.2e-12 on 50 more problems (γ up to 0.9998, n to 800); AR(2) closed forms and
noise-free recovery exact; ×1000 invariant; the running floor does not absorb real slow events (6/6 at half 1200 s);
onset convention correct; test-first honoured; 267 passed.
