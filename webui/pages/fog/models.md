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
- Results: the suggested threshold at a target precision other than 0.8 is drawn by no frame · the page moves
  the frame's four suggested values deterministically with the target (thr +0.55·Δ, precision +0.95·Δ,
  recall −1.3·Δ) · frame models-3, spec §7b.3
- Results: what arm B's calibration means (cluster labels mapped onto manual classes) is unstated · shown on
  the mapped classes · spec §7b.3, §7b.4
- Results: the RF baseline has no calibration, no epochs and no registration gate; the frames never show it ·
  those three cards say "unavailable for the RF baseline" with the reason (§3 "nothing claims more than it
  knows") · frame models-3
- Results: a running training job (j-0214) has no frame · the page shows an indeterminate bar, "results arrive
  through Jobs › Manifest inbox" and a link into Jobs · spec §7b.2, P24
- Compare: how a cluster arm's prediction is judged right or wrong (through the majority cluster → class mapping)
  is implied, never stated · the step-through says so behind an InfoTip · spec §7b.4
- Compare: the GASF / RP tiles in the frame are stylised · the page computes them from the window itself
  (GASF cos(φi+φj), RP 1−|xi−xj|); the real ones would come from 04 Image encode's cache · frame models-4
- Compare: clicking a filter (Seg or a 2×2 cell) opens that filter at the window the frame shows
  (only A 7, only B 1, both wrong 12) rather than at 1, so both frames are reachable by clicking · frames models-4, 4b
- Compare: a pair that is not paired (different test windows) has no frame · paired difference, agreement,
  per channel and the step-through all say "unavailable" with the reason · spec §7b.4, §3
