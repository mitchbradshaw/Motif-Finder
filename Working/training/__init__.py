"""
Working.training
================
The paired training job of RQ1 (fixup-ab): one window set pooled across the
channels of a recording, two label arms (manual · cluster) trained identically,
a blocked split by time with a gap, the label-shuffle null, and three exams
reported separately. UI-free: no browser library and no FastAPI is imported
anywhere under this package (CLAUDE.md rule 1).

    windows.py    the pooled set, the blocked split and the guards
    paired.py     the recipe, the Before-launch checks, the cut proposal, the job, the estimate
    metrics.py    macro F1, block bootstrap, McNemar, agreement, calibration
    store.py      window_sets + members rows, runs/configs/artifacts rows, the frozen cut
    reference.py  the existing MODELS/ scored as a reference line ("trained differently")
    __main__.py   the command line: save-set · propose · run · show
"""
