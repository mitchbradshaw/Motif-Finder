# The drop pool through the 23 Nov drop plots (24–25 Nov 2026)

**Open [`index.html`](index.html)**: every figure with its caption, in order.

These are the NeurIPS session's 23 Nov drop plots (`scripts/library_analysis/drop_plots_20261123.py`, imported
unchanged), drawn over the **131,651 core drops** of the 24 Nov auto-detect pool: drops on 17 datasets that nobody has
judged or been shown in a queue. As in the 23 Nov plots, every drop is treated alike.

* How each figure is built and how to read it: that session's
  [`../20261123_plots/README.md`](../20261123_plots/README.md).
* What the pool is, its rules and its numbers: [`docs/autodetect/20261124_pool/README.md`](../../autodetect/20261124_pool/README.md).
* The same figures over the cleaner part of the core only, the drops the verdict model puts at 0.8 or more:
  [`../20261124_pool_plots_p80/`](../20261124_pool_plots_p80/index.html).

## Read these before the figures

1. **About 7 in 10 of these drops are likely real.** A model of 4,794 past verdicts puts the core at about 70%, and
   lower on some datasets: about half on Cordyceps and enoki, 58% on MJu26a. A pattern that holds only here and not in
   the cleaner `_p80` set may be noise.
2. **The Cordyceps, enoki and split gill rows are mostly not drops.** Most of their "drops" are down-swings of a steady
   oscillation (a 10–20 s period, rising as fast as it falls, `sheets/Cordyceps.png`), or a train of fast down-and-up
   spikes. That is why their typical shape (`species_typical_shape.png`) rises into the top and rebounds after the
   bottom. Read those rows as a portrait of the oscillation. In the pool, `fast_rises` (`pool_rhythm.py`) measures how
   often the trace climbs back as fast as the drop fell, and their median core drop has 7–9 such climbs within
   ±150 s, against 0–1 on most other datasets.
3. **Steepness partly measures the sampling rate.** In the steepness grids and fingerprints, M1, L_R_Aug_26_PD and F2B
   form their own group of cliff-like falls (median 5.2, against 2.3 for every other recording). These are the three
   recordings stored at 10 Hz. Re-measured on the same traces thinned to 2 Hz, their median is 3.2. So about
   two-thirds of the gap is the rate, and what is left may be real (`docs/autodetect/20261124_pool/checks/steepness_rate.out.txt`).
4. **M1 has a second kind of drop: long, deep slides.** 5% of M1's core drops fall for over 10 minutes and are about
   33 mV deep (median), against 1.2 mV for M1 as a whole. They are stretches of M1's slow drift, read as one drop
   (`sheets/M1.png` shows a few). They make M1's separate patch far up and right in `species_fingerprints.png`.
5. **Six datasets have never been judged at all:** M1, L_R_Aug_26_PD, Cordyceps, Enoki, F2B and the Dwij loggers.
   Their species is unknown except for Cordyceps and enoki, so each is its own row ("(species ?)"); none is pooled with
   another.
6. **Crowding.** The figures were laid out for the 7 datasets of 23 Nov; here there are 17. Labels overlap in the
   boxplots. The width–amplitude figure is drawn in two parts (`species_width_amplitude.png` and `_2.png`), because
   it has room for six species.
7. **Two figures use a random sample.** The shape map uses 30,000 drops and the t-SNE shape space 20,000: both compare
   every drop with every other. Their captions say so.

## What the plots show

See "What the plots show" in the pool's README (`docs/autodetect/20261124_pool/README.md`).

## Drawn by

`scripts/autodetect/pool_plots.py`. It adds names and colours for the datasets the 23 Nov plots never used, makes the
captions say "pool drop" where they said "reviewed drop", draws the six-species figure in parts and samples the two
quadratic figures. The event table (`events.csv`) and every drop's waveform (`event_shapes.npz`) are kept beside the
pool, in `DATA/derived/autodetect/pool_20261124/`.

    PYTHONIOENCODING=utf-8 MPLBACKEND=Agg "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_plots.py
    POOL_MIN_P_ACCEPT=0.8 ... scripts/autodetect/pool_plots.py      # the _p80 set
