# Stub — S: how plots come out on generated reports

**From Round 7 Q1.** The researcher drew this boundary explicitly: `H` is the UI's analysis pages;
report output is a separate prompt.

## The one rule that matters

**It inherits `H`'s standard. It does not invent a second one.**

`H` writes the contract — seven type views, twelve input-driven modifiers, the drawing rules, the
text budget — into `docs/BLOCK_INTEGRATION.md`, enforced by a test and by a measured check in the
smoke gate. A report prompt renders **the same rules to a different medium**.

The failure mode is concrete and this repo has already paid for it once: four different y-padding
rules in four places, each defensible on its own, which prompt `C` had to go and unify into
`charts/domain.ts`. A second drawing standard living in a report generator is that, again.

## What is already known

- The core keeps **matplotlib** for figure export and nothing else browser-shaped (`CLAUDE.md`
  rule 1), so a report plate is drawn in Python, not in the client.
- `Pipelines/drop_motifs/drawing_rules.py` is the researcher's own 636-line figure standard for the
  thesis plates — nine rules, and `check_drop_shape` as an assertion that a drawing did not flatten
  what it drew. A report prompt should probably *use* it rather than mirror it.
- The exemplar plate the researcher supplied is `Plots/drop_motifs11/S2_1_fall_angle.png`. Its
  provenance footer — store, n, date, and the unit rule — is the convention worth keeping: **every
  exported figure states what it was computed from.**
- `H`'s decision that thumbnails are browser-drawn SVG and matplotlib is reserved for multi-panel
  export plates (Round 7 Q13) is the seam this prompt picks up.
