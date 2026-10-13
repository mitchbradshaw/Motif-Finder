# Critic report — W1-E: `interrogation.trains`

Filed by the manager, 2026-10-13. Verdict: **merge after fixes**.

## In plain words

The block never claims convoys that are not there: on random event times — including slowly drifting rates — it reported
no trains in every run. The trouble is the other direction: the default rule (logISI) also misses convoys that are
plainly there when gaps inside a train are irregular, or when most events are not in a train. Adamatzky's rule and
MaxInterval do what they claim.

## Findings

- **F1 should-fix (borderline blocker)** — auto ceiling (`trains.py:173-179`): the intra-train peak is the largest peak
  below the median gap; when fewer than half the gaps are within trains the median lands in the inter-train hump and
  the block reports "one hump". Trains every 4th unit (intra share 0.34): auto logISI 0 trains; `max_core_gap_s = 100`
  and Adamatzky find all 15.
- **F2 should-fix** — Scott's bandwidth over-smooths. Exponential within-train gaps at ratio 100: recall 64 % (n = 300),
  10 % (n = 60); ratios 5–30: ~0–1 %. Silverman's robust bandwidth: 99 % / 84 % at ratio 100, 0 % false trains on Poisson,
  1.5 % on a 100× drift at n = 30; 0.6 × robust is too narrow (11–18 % false trains on drift). Even the true mixture's void
  is 0.51 at ratio 10, 0.72 at 30, 0.89 at 100 — logISI needs between-train gaps ~30–100× the within-train ones.
- **F3 nit** — "one hump" said when a second hump is below the 5 % prominence floor.
- **F4 nit** — quadratic loops (20 k events in 6.4 s under Adamatzky).
- **F5 nit** — LZ via the private `_lz76_complexity`; pyplot loads on first call (harmless, already loaded elsewhere).

## False-train rate measured (400 seeds per cell, n = 30–300)

Poisson 0 %; gamma(k = 2) 0 %; inhomogeneous Poisson with a linear 10× ramp, an exponential 100× ramp or a 5× sinusoid
0 %; two-state regimes 0–0.8 %. Rate drift does not fake a bimodal histogram at Scott's bandwidth.

## Checked and fine

Void formula and > 0.7 test, valley logic, core-and-extend, MaxInterval order and Adamatzky's ≤ θ match §8; adaptations
named; upstream columns survive; NaN onsets counted; edge cases honest; < 10 gaps refuses in words; test-first;
271 passed.
