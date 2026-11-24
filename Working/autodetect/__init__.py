"""
autodetect
==========
Auto-detect (prototype, 2026-11-19): one channel in; candidate events out, each with a confidence, plus the
sequences those candidates form.

In plain words
--------------
Three kinds of witness look at the channel.

* The **seed searches** ask "does anything here look like a shape you have already accepted?" — one search per
  shape family of the accepted catalogue, each at the family's typical durations.
* Four **precise detectors** (drop v1, drop v5, wavelet-encoded, BEADS-inverted) ask "is there a sharp fall here?".
* **R4**, the classifier trained on the researcher's verdicts, judges every stretch the others point at, and also
  scans the channel window by window (2, 6, 10 and 30 minutes) for anything they all missed.

Witnesses that point at the same stretch become one candidate. Its confidence starts at R4's score and rises with
each other witness that agrees — more for a more reliable witness (`blend`). Candidates that are more likely than
not, and that come in runs, form sequences (`sequences`).

No surrogates and no nulls: the aim is a fast, accurate first pass for review, not a significance test.

The modules
-----------
``chains``      a detection template's steps run on samples in memory (no database, no step cache)
``seeds``       a seed bank (one medoid per shape family) searched over a channel
``scan``        R4's sliding windows and the local-peak rule that keeps the best of overlapping hits
``blend``       the confidence formula and the source precisions it reads
``candidates``  proposals merged into candidates (the existing same-event rule), agreement, confidence
``sequences``   the logISI train finder over the confident candidates, with a fixed-gap fallback
``pipeline``    `auto_detect`, which runs the lot on one channel and times every stage

Headless: numpy, pandas and the core only (CLAUDE.md rule 1). Nothing here reads or writes the database or any
file: the caller hands in the samples, the detector templates, the seed bank and an R4 scorer.

Entry point: ``Working.autodetect.pipeline.auto_detect``.
"""
