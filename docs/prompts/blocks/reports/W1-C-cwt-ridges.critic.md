# Critic report — W1-C: `detection.cwt_ridges` + `cwt_events`

Filed by the manager, 2026-10-13. Verdict: **merge after fixes** (two blockers).

## In plain words

Like a set of measuring cups: each bump is poured into every cup and the one it fills best gives its duration. On the
implementer's test day (white noise, smooth drift) it does exactly that. The trouble is the yardstick for "is this
real": noise is measured only in the smallest cup, at the 95th percentile. On slow wander (random-walk-like — how fungal
recordings tend to look) that gives tens to over a hundred false events a day; on coloured noise it misses large, obvious
slow events; and a train of spikes raises its own "noise" level and disappears. Turning `min_snr` up or `max_scale_s`
down fixes none of it.

## Findings

- **F1 blocker** — SNR noise from the 10 s row only; with A0's 1/a normalisation SNR is a pure amplitude cut. Random walk:
  125 / 46 / 21 / 6 false events a day at `min_snr` 3 / 5 / 8 / 12 (scale-free); AR(1) 0.3: recall 0.3 / 7 at the
  default; no `min_snr` gives zero false events with full recall on wander-dominated backgrounds. Fix: noise at the
  event's own scale (robust MAD of that scale's row).
- **F2 blocker** — the p95 noise is raised by the events themselves: 24 s drops every 120 / 300 / 600 s → 0 / 718,
  0 / 286, 17 / 142 found; a median-based noise recovers 285 / 286 and 142 / 142 with no white-noise false events.
- **F3** — the template's Event shape `polarity: auto` disagrees with the ridge on ~⅓ of events (the drift slope
  decides); set both to `drop`.
- **F4** — meta 3.4–3.6 MB per run (the full-precision scalogram).
- **F5** — runtime 20–23 s for 2.6 M samples standalone, not 12 s.
- **F6–F8 nits** — reflection about one edge sample; a 99.9 %-NaN span still reports an event; durations shrink in
  dense trains.

## Checked and sound

A3 chunk seams identical at defaults (max SNR difference 4e-15); A12 does not eat slow events (43-min events every hour:
21 / 22; flat-floored 30 min – 2 h drops found with right durations); A6 / A7 / A14 as documented; acceptance items
present and tested; test-first; 234 passed.
