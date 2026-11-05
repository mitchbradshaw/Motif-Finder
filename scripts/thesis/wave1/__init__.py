"""
wave1 — the thesis's first data export from the PC (2026-11-05): real signal excerpts and tables for the figures,
in one read-only run. Entry point: ``run_wave1.py``; the request list: ``bundle_spec.json``.

Modules:
    common         paths, the read-only database, recordings, channel reads in mV, the array/stack/CSV writers
    export_bundle  steps 1-12 (meta, overviews, full channels, windows, detections, queues, library, labels, ...)
    pool           step 13 (candidate-event pool: collapse, stratified sample, shape features, R4 scores) and the
                   frozen R4 MiniRocket scorer shared with step 14
    m4_payload     step 14 (the scored M4 exam: items, verdicts, R4 scores, a 48-h window)
    zipper         REPORT.md and the <= 24 MB zip parts

Dev tooling: nothing under Working/, Adapters/ or Pipelines/ imports it.
"""
