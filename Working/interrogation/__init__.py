"""
Working.interrogation
======================
Per-event measures of the events a detector found, and the cross-event views
over them (fixup-d). UI-free core: `event_shape` (the shape of each event),
`intervals` (the time between them, and when a run of them is a train), and
`sequences` (the same measures read off a stored sequence, with the rose).

Vocabulary, fixed on purpose (QUESTIONS.md Q12): a *motif train* is a sequence
of motifs of either polarity; drops and spikes are different events measured
the same way about opposite signs, so every measure here is polarity-neutral.

No plotting library - CLAUDE.md rule 1.
"""
