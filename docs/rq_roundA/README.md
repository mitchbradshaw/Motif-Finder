# rq_roundA — the six research questions, one living file each

Created 2026-10-03, at the researcher's request during the Round 9/10 grilling. The fixup prompts (`docs/prompts/fixup/`)
build the app; **these files track whether each of the six PRD research questions can be answered yet, and how.** After
the fixup stage the researcher works through each question, probably with its own prompts and agents; these files are
where that work starts.

| File | The question |
|---|---|
| `RQ1-cluster-vs-manual-labels.md` | Do cluster-derived labels produce a classifier that generalises better than manually-derived labels? |
| `RQ2-exemplar-seeded-search.md` | Does a human-adjudicated exemplar used as a matrix-profile seed recover instances a human also accepts? |
| `RQ3-identity-under-scale.md` | Is motif identity preserved under scale normalisation? |
| `RQ4-bands-and-symbols.md` | Does band decomposition followed by symbolic encoding surface regions raw-signal methods miss? |
| `RQ5-human-vs-machine-divergence.md` | Where do human and analytical judgement diverge, and is the divergence structured? |
| `RQ6-recurrence-across-channels.md` | Once contamination and propagation are separated out, does recurrence persist across channels and recordings? |

**The plan (the researcher, 2026-10-03):** about **18 research questions over about three rounds** (A, B, C).
Each question is answered with the website *as it currently stands*, and each round develops what the site can do for
the next. Round A is these six PRD questions; round B's notes are in `docs/rq_roundB/`.

Each file has the same sections: **In plain words**, **What is known**, **Decisions already made**, **What is still
needed**, **How it gets answered**, **Open decisions**, and **Log**.

## The rule for agents: keep these files current

**Any fixup or research prompt whose work changes what a question can do must update that question's file before it
reports.** Concretely:

1. Move the step you built from *What is still needed* to *What is known*, with the date and your report's path.
2. Copy any decision the researcher made that bears on the question into *Decisions already made*, citing the
   `QUESTIONS.md` row.
3. Add one line to *Log*: `YYYY-MM-DD · prompt-id · what changed`.
4. Do not delete history. If a finding is withdrawn, strike it through and say why, the way `QUESTIONS.md` does
   with Q26.

Sources these files summarise (do not duplicate them; link them): `docs/RESEARCH_READINESS.md` (what was measured on
2026-10-02), `docs/RESEARCH_RUNBOOK.md` (the clicks), `docs/prompts/fixup/QUESTIONS.md` (the decisions),
`docs/PIPELINE_PRD.md` "How the research questions map onto the build".

**Plain language first.** Every question put to the researcher opens with a simple explanation, then the options,
then a recommendation (`CLAUDE.md`, "Talking to the researcher").
