# Q40d: are the same-instant cross-channel matches artifacts? (read-only, 2026-10-04)

**In plain words.** Imagine checking whether two microphones heard the same bird by asking: "does a one-second clip from mic A look like the clip from mic B at the same moment?" The catch is that these clips are very short (on Fig2A, about 1.6 s, or 16 points) and mostly slow drift. Almost any two clips like that look alike. As a control, I compared each member with its neighbouring electrode at a **random other moment**, at least 60 s away. That passes W's artifact rule just as often as the real same-moment clip does: 90% against 91% on Fig2A, 67% against 65% on M2_aug. So the matches do not show that the same event reached two electrodes, and they do not show that it didn't. **The rule as built cannot tell an artifact from a coincidence.** Tightening it doesn't fix that: requiring |r| ≥ 0.9, amplitude within 2x and both sides above 0.1 mV still passes about as often at random times on Fig2A (12.1% real vs 11.6% random). On M2_aug the strict rule shows a small excess (18.7% vs 13.0%). The flagged members are not bunched in time, and none sits near a human-marked artifact.

## What was measured
For each of the 135 members (F-130/F-119/F-39, grouping 5) × every other channel, I took the member's own span from both channels and ran it through `Working.cross_channel.classify_waveforms`. That gives 771 pairs. The recomputed values match the stored `motif_member_cooccurrence` rows (535 rows, max r difference 2e-11, 0 lag mismatches). Units are `V` for both files, so values ×1000 = mV. The files are 114 members on Fig2A_dt0p1 (10 Hz) and 21 on M2_aug_concat_fs1 (1 Hz).

- **W's stored verdict flags 133/135 members** (the earlier 114 counted co-occurrence rows only; artifact edges add 19). Recomputed on each member's own span, all 135 are flagged. The 2 that W left unflagged were measured on union windows against a sibling *member*.
- **The random-time control predicts 134.8 flagged members** under W's rule; 135 are flagged. Under the strict rule it predicts 57.3; 49 are flagged.

| same-instant pairs, by \|r\| | n | median amp ratio (IQR) | ratio within 0.5–2x | sibling ≥ 0.1 mV | both ≥ 0.1 mV | r < 0 | lag = 0 |
|---|---|---|---|---|---|---|---|
| 0.5–0.7 | 112 | 0.67 (0.27–1.23) | 44% | 66% | 58% | 42% | 35% |
| 0.7–0.9 | 241 | 0.66 (0.32–1.54) | 42% | 79% | 66% | 53% | 63% |
| 0.9–1.0 | 267 | 1.05 (0.52–1.78) | 53% | 91% | 79% | 28% | 90% |

- **Sign of r:** 40.3% of the 620 same-instant pairs have negative r, so the waveform is upside down on the other electrode.
- **Amplitude ratio:** on M2_aug the median ratio is 0.20–0.74, so the sibling's swing is usually much smaller.
- **Member swing:** the median member swing is only 0.205 mV, and 24% of members are themselves below the 0.1 mV floor.

## Is it bunched in time? (measured)
Fig2A, using the 34 strict-flagged of 114 members:
- 82% have another strict-flagged member within 30 s. Shuffling the flags among the same members gives 82% too (p = 0.56). At 60 s the figures are 94% vs 96%.
- The median gap is 16.4 s between strict-flagged members and 10.2 s between the rest. Members are dense overall: 42.5% of gaps are ≤ 5 s.
- **There is no extra bunching.**

On M2_aug, 5 strict members sit on CH7 within about 1.5 days (0.40 vs 0.27 shuffled, p = 0.28).

## Human artifact regions (measured)
- **Fig2A:** `parent_recording_id`, `parent_offset` and `decimation` are NULL on all 5 rows, and there are 0 annotations. No parent is registered. I tested the one unregistered 5-channel candidate, `DATA/raw/F2B.mat` (5,184,001 × 5, which would be 6 days if 10 Hz), by sliding correlation. Fig2A is not a verbatim excerpt of it: there is no consistent location across channels and r ≤ 0.62 (`find_parent*.txt`). Whether the parent is some other file is not known.
- **M2_aug:** it has 128 human `artifact` windows (10 min each, covering 1.4% of the time on some channel). 0 of the 21 members fall inside one or within 2 h of one; 1.1 would be expected at random within 30 min.

## Inferred, not measured
The high match rate comes from short windows plus a lag search of ±1 s (±10 samples on spans of about 16 samples) plus shared slow drift. It is not evidence of shared events. A useful artifact rule would need a null like this one: per pair, "does this match beat the same sibling at random times?"

## Files (`webui/screenshots/fixup/Q40d/`)
- `examples_gallery_mV.png`: true scale, shared mV axis, each trace minus its median.
- `examples_gallery_zscore.png`: shape view, z-scored by the member span.
- `scatter_r_vs_amplitude_ratio.png`
- `timeline.png`
- `overview_Fig2A_by_family.png`
- `overview_M2_aug.png`
- Scripts: `measure.py`, `analyse.py`, `find_parent.py`, `find_parent2.py`
- Data: `pairs.csv`, `members.csv`, `stats.json`
