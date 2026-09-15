# Models — fog of war

- Other label-arm kinds for *Add arm* (beyond manual and cluster labels) are not specified · the popover offers "labels from a window set" as not built · spec §7b.1, inventory F19
- How the local estimate scales with channels, seeds, epochs and the null is not specified · the page uses fixture maths (per arm 1.6 h per 3 channels, RF 0.1 h, 5 model nulls 2.3 h) and says ≈ · frame models-1, spec §7b.1
- How a split applies to a human-annotated window set without one (ws_humanlabel_frame0b, backlog B7) · the row is disabled with the reason · frame models-1b, spec §6.9
- ws_M3jul_8ch_300s split blocks and per-class counts appear in no frame · fixture scales the canon counts · frame models-1b
- The frame shows L_LM_Jul26_J CH1 as 92 h; canon says 22.4 h, and the row has no disabled reason · canon wins; reason "10 Hz (inferred) · the template's sliding windows expect 1 Hz" is invented · frame models-1, spec §0
- The Save-window-set name chip reads "ws_M2aug_3ch_600s v2" while the script flag reads "_v2" · kept both as the frame · frame models-1
- The frame's "gap" select offers no values; what gaps other than one window mean (2 windows, 0 s) is invented · 0 s fails the check (P12 leakage guard) · frame models-1
- Whether *Create SLURM script* also saves the window set to the Library immediately, or only when results are imported · the page writes it at script creation · spec §6.9, §7b.1
- The "open in Jobs" filter parameter for training jobs is owned by Jobs · the link uses #/jobs?kind=cluster · spec §7b, P24
