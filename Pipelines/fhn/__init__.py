"""
Pipelines/fhn — FitzHugh-Nagumo modelling of recorded fungal cycle shapes (thesis ch. 10).

* `model`   — the vector field, its Jacobian, the period, the limit cycle sampled uniformly in
  phase, phase by projection onto the cycle, and the infinitesimal PRC by small perturbations
  (the "ground truth" of Wilshin, Kvalheim & Revzen 2024, Sect. 6.1), the adjoint PRC as an
  independent check, and the delay-coordinate PRC with its Jacobian correction (Sect. 6.2).
* `fit`     — least-squares fits of one recorded cycle shape: the FHN limit cycle (oscillatory
  regime), one FHN excursion from rest (excitable regime), and the jump + exponential recovery
  kernel of `detection.deconvolve` (OASIS) as the competitor.
* `data`    — read-only loading of the drop-motif sequences, their mean cycle, and the nulls.
* `figures` — the paper's figure styles (Fig. 1, Fig. 4, Fig. 3/5) for a fitted model.
* `run_ch10.py` — the chapter-10 demonstration; writes docs/thesis/data/ch10_fhn/.

Reference: S. Wilshin, M. D. Kvalheim, S. Revzen (2024) "Phase response curves and the role of
coordinates", Biological Cybernetics 118:311-330, doi:10.1007/s00422-024-00997-w. Written from
the paper; the authors' release code was read for conventions only and is not copied.

The analysis lives here rather than under Working/ only because Working/ was out of scope for
the job that wrote it; it imports nothing from Working/ or Adapters/.
"""
