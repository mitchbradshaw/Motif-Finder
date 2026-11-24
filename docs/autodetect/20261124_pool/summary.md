# The 24 Nov drop pool: the numbers

Written by `scripts/autodetect/pool_summary.py` from the saved results; `summary.json` holds the same.

## The search

* 144 channels in 17 datasets, 54,551 hours of recording (summed over channels).
* 830,648 drops found (371,348 at confidence >= 0.6); 26,235 sharp rises met on the way, not used.
* 17.2 worker hours on 3 workers; 6.3 h of wall clock (2026-11-24 18:04 to 2026-11-25 00:20).
* Slowest channels: MJu26a CH2 (rec 694) 40 min for 636 h; MJu26a CH8 (rec 700) 30 min for 636 h; MJu26a CH7 (rec 699) 29 min for 636 h; MJu26a CH4 (rec 696) 29 min for 636 h; Cordyceps CH3 (rec 618) 29 min for 528 h.

## The pool

**231,522 drops: 131,669 core, 99,853 extended.**

| dataset | species | channels | hours (all channels) | drops found | core | extended | core per 100 h | share of core |
|---|---|---|---|---|---|---|---|---|
| M1 | unknown | 13 | 3,925 | 176,961 | 35,212 | 28,358 | 897.2 | 26.7% |
| MJu26a | lion's mane | 16 | 10,175 | 215,797 | 21,956 | 27,636 | 215.8 | 16.7% |
| M2_aug | oyster | 16 | 11,536 | 47,173 | 20,678 | 2,111 | 179.2 | 15.7% |
| L_R_Aug_26_PD | unknown | 13 | 1,391 | 119,060 | 18,303 | 20,202 | 1,316.0 | 13.9% |
| Cordyceps | Cordyceps | 7 | 3,695 | 138,560 | 11,115 | 12,024 | 300.8 | 8.4% |
| Enoki | enoki | 7 | 2,097 | 75,919 | 5,022 | 6,435 | 239.5 | 3.8% |
| CO | chocolate oyster | 4 | 1,920 | 7,791 | 4,230 | 626 | 220.3 | 3.2% |
| LM | lion's mane | 4 | 1,920 | 6,639 | 4,114 | 271 | 214.3 | 3.1% |
| M2_concat | oyster | 16 | 4,520 | 9,747 | 3,896 | 570 | 86.2 | 3.0% |
| M4 | oyster | 16 | 8,080 | 17,944 | 2,272 | 585 | 28.1 | 1.7% |
| SH | Asian shiitake | 4 | 1,920 | 6,849 | 2,058 | 454 | 107.2 | 1.6% |
| F2B | unknown | 5 | 720 | 2,968 | 1,580 | 238 | 219.4 | 1.2% |
| SO | snow oyster | 4 | 1,920 | 2,545 | 1,053 | 226 | 54.8 | 0.8% |
| S_commune | split gill | 7 | 513 | 2,604 | 150 | 109 | 29.3 | 0.1% |
| Dwij_D | unknown | 4 | 117 | 30 | 14 | 3 | 11.9 | 0.0% |
| Dwij_C | unknown | 4 | 33 | 40 | 9 | 4 | 27.1 | 0.0% |
| Dwij_B | unknown | 4 | 70 | 21 | 7 | 1 | 10.0 | 0.0% |

## What the verdicts say to expect

* Judged drops that pass the core's settings (a ceiling: the queues showed the clearest first): 86% accepted (n 4,556); looser settings only: 50% (n 238).
* Weighted to the pool's own confidences: core 75%, extended 64%.
* The verdicts come from CO (270), LM (334), M2_aug (2,319), M2_concat (264), M4 (216), MJu26a (1,204), SH (86), SO (93), S_commune (8); the pool's drops are the ones no queue picked.

| band | judged | accepted | core | extended |
|---|---|---|---|---|
| (0.5, 0.6] | 180 | 55% | 0 | 36,368 |
| (0.6, 0.7] | 208 | 63% | 18,439 | 14,917 |
| (0.7, 0.8] | 247 | 66% | 23,053 | 17,408 |
| (0.8, 0.9] | 372 | 70% | 28,534 | 16,579 |
| (0.9, 0.95] | 342 | 79% | 19,881 | 8,211 |
| (0.95, 0.99] | 768 | 81% | 26,066 | 5,834 |
| (0.99, 1.0] | 2,677 | 93% | 15,696 | 536 |

### Re-weighted to the pool's own measures

A model of 4,794 past verdicts (accepted against rejected or unsure; shallow gradient-boosted trees) from log clarity, confidence, p_r4, log depth, log sharpness, sources, finder only, fast rises; cross-validated AUC 0.79, Brier 0.108. Averaged over the pool: **core 70%, extended 49%** (the judged drops themselves: 84%). 35% of the core (46,558 drops) is predicted at 0.8 or more. Each drop's prediction is `DATA/derived/autodetect/pool_20261124/p_accept.parquet`: a device for re-weighting and for checking a plot on a cleaner subset, not a verdict. It assumes a drop is judged by how it looks, whatever dataset it is on; six datasets have no verdicts at all.

| dataset | core expected |
|---|---|
| LM | 83% |
| F2B | 82% |
| CO | 82% |
| M2_aug | 82% |
| SO | 79% |
| M4 | 78% |
| L_R_Aug_26_PD | 74% |
| Dwij_B | 74% |
| SH | 74% |
| M2_concat | 71% |
| Dwij_D | 71% |
| M1 | 70% |
| Dwij_C | 62% |
| MJu26a | 58% |
| Enoki | 53% |
| Cordyceps | 52% |
| S_commune | 46% |

Cross-validated calibration (each tenth of the judged drops by predicted acceptance):

| judged | predicted | accepted |
|---|---|---|
| 480 | 46% | 46% |
| 479 | 71% | 69% |
| 479 | 79% | 80% |
| 480 | 84% | 84% |
| 479 | 88% | 89% |
| 479 | 90% | 90% |
| 480 | 93% | 92% |
| 479 | 95% | 95% |
| 479 | 97% | 97% |
| 480 | 99% | 100% |

Cross-validated, by fast_rises band:

| band | judged | predicted | accepted |
|---|---|---|---|
| (-0.5, 0.5] | 2,122 | 87% | 88% |
| (0.5, 1.5] | 926 | 91% | 92% |
| (1.5, 2.5] | 367 | 83% | 83% |
| (2.5, 3.5] | 151 | 75% | 71% |
| (3.5, 5.5] | 151 | 66% | 66% |
| (5.5, 9.5] | 164 | 61% | 59% |
| (9.5, 1000000.0] | 146 | 61% | 61% |

Cross-validated, by clarity band:

| band | judged | predicted | accepted |
|---|---|---|---|
| (10.0, 15.0] | 88 | 37% | 38% |
| (15.0, 20.0] | 79 | 56% | 54% |
| (20.0, 30.0] | 163 | 63% | 61% |
| (30.0, 50.0] | 273 | 77% | 75% |
| (50.0, 100.0] | 423 | 82% | 85% |
| (100.0, 300.0] | 751 | 85% | 84% |
| (300.0, 1000000000000.0] | 1,746 | 90% | 90% |

Cross-validated, by depth_mv band:

| band | judged | predicted | accepted |
|---|---|---|---|
| (0.0, 0.25] | 77 | 41% | 40% |
| (0.25, 0.5] | 169 | 65% | 63% |
| (0.5, 1.0] | 418 | 79% | 81% |
| (1.0, 2.0] | 613 | 84% | 84% |
| (2.0, 5.0] | 993 | 84% | 85% |
| (5.0, 10.0] | 1,001 | 90% | 89% |
| (10.0, 1000000000000.0] | 1,523 | 86% | 86% |

Cross-validated, by confidence band:

| band | judged | predicted | accepted |
|---|---|---|---|
| (0.5, 0.6] | 180 | 56% | 55% |
| (0.6, 0.7] | 208 | 62% | 63% |
| (0.7, 0.8] | 247 | 66% | 66% |
| (0.8, 0.9] | 372 | 71% | 70% |
| (0.9, 0.95] | 342 | 79% | 79% |
| (0.95, 0.99] | 768 | 82% | 81% |
| (0.99, 1.0] | 2,677 | 93% | 93% |

## Concentration

* M1 and MJu26a hold 43% of the core; the ten biggest channels hold 29%.
* 142 channels have core drops; the median channel has 546.

| dataset | recording_id | channel | core |
|---|---|---|---|
| M1 | 557 | 12 | 5,171 |
| MJu26a | 694 | 2 | 4,712 |
| M1 | 550 | 5 | 4,453 |
| M1 | 545 | 0 | 4,294 |
| M1 | 549 | 4 | 4,010 |
| Cordyceps | 620 | 5 | 3,475 |
| L_R_Aug_26_PD | 684 | 5 | 3,243 |
| M2_aug | 16 | 15 | 3,151 |
| L_R_Aug_26_PD | 683 | 4 | 3,137 |
| MJu26a | 696 | 4 | 2,861 |

## Flagged in the pool

| tier | finder_only | m4_like | wd_long_tail | several_events_in_span | whole_drop_measured | confidence_median |
|---|---|---|---|---|---|---|
| core | 30.2% | 10.8% | 3.2% | 5.6% | 100.0% | 0.888 |
| extended | 33.3% | 4.8% | 2.1% | 5.1% | 100.0% | 0.692 |

## The drops' shapes by dataset (core, medians)

| dataset | drops | depth_mv | fall_s | width_s | recovery_s | confidence |
|---|---|---|---|---|---|---|
| M1 | 35,212 | 1.17 | 6.5 | 13.6 | 8.0 | 0.900 |
| MJu26a | 21,956 | 0.33 | 10.5 | 18.4 | 8.1 | 0.848 |
| M2_aug | 20,677 | 1.58 | 18.0 | 43.8 | 24.8 | 0.940 |
| L_R_Aug_26_PD | 18,303 | 0.91 | 5.5 | 12.6 | 7.5 | 0.900 |
| Cordyceps | 11,102 | 0.30 | 10.0 | 17.9 | 7.3 | 0.768 |
| Enoki | 5,021 | 0.46 | 9.0 | 17.2 | 7.1 | 0.776 |
| CO | 4,230 | 1.60 | 6.5 | 24.1 | 16.2 | 0.957 |
| LM | 4,114 | 2.63 | 9.0 | 44.4 | 30.7 | 0.978 |
| M2_concat | 3,895 | 3.49 | 43.0 | 97.8 | 38.1 | 0.936 |
| M4 | 2,272 | 1.23 | 44.0 | 112.9 | 52.7 | 0.898 |
| SH | 2,058 | 1.75 | 52.2 | 109.3 | 57.2 | 0.884 |
| F2B | 1,580 | 1.86 | 10.5 | 21.3 | 10.9 | 0.976 |
| SO | 1,053 | 1.65 | 19.0 | 43.0 | 25.9 | 0.936 |
| S_commune | 148 | 0.16 | 8.0 | 13.5 | 5.5 | 0.764 |
| Dwij_D | 14 | 0.78 | 5.0 | 5.6 | 1.0 | 0.847 |
| Dwij_C | 9 | 0.96 | 3.8 | 9.8 | 5.7 | 0.851 |
| Dwij_B | 7 | 1.31 | 7.5 | 7.5 | 0.7 | 0.926 |
