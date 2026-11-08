# Return audit and analysis — 8 November 2026

These files analyse the PC copies of the drop-transfer return and the partial 2 Hz detector sweep. They do not contain raw recordings or the blind review key.

- audit.json: 64 seed-channel and 1,014 detector-task records; specification matching, completion, file location, counts and existing PC import/cache state.
- seed_summary.json: the unchanged original-threshold comparison and separately recalibrated target comparison. MJu26a's surrogate summaries use only its 11 completed channels.
- rq4_summary.csv: all 129 setting/recording combinations, their channel coverage and real/phase counts on completed channels. Use whole=True rows for complete-coverage comparisons.
- verification.json: provenance, packaging and static checks.

## Drop transfer

The six fully returned targets have 393 matches at the frozen distance cut 2.2080859509008204. They have 200 phase-randomised draws per channel:

| Recording | Complete channels | Recording matches | Total surrogate matches over 200 draws | Mean per draw, summed channels |
|---|---:|---:|---:|---:|
| M2_concat | 16/16 | 76 | 1 | 0.005 |
| M4 | 16/16 | 66 | 1 | 0.005 |
| LM | 4/4 | 195 | 3 | 0.015 |
| CO | 4/4 | 15 | 0 | 0.000 |
| SH | 4/4 | 21 | 1 | 0.005 |
| SO | 4/4 | 20 | 0 | 0.000 |
| MJu26a, restricted partial comparison | 11/16 | 65 | 9 | 0.045 |

All 16 MJu26a real searches are finished, with 71 fixed-cut matches. Its five unfinished files are CH6–CH10 (zero-based export names); their null draws are 110, 120, 120, 120 and 110 of 200, leaving 420 draws. All results match their part-specification hashes. All searches preserve 377 seconds, including resampling to 754 points at 2 Hz. No fixed-cut channel reaches 200 passing returns.

The real search therefore supplies 464 raw fixed-cut matches across seven targets. Five match earlier adjudications. Review merges two further overlapping LM proposals, leaving 457 fresh match presentations. These are mixed with 459 matched-duration/channel random controls in blind queue 38, for 916 presentations. Forty-six repeat presentations are reserved for a second queue after the first is complete; creating both simultaneously would let automatic verdict carrying answer repeats before review.

The private key is in the ignored main-checkout DATA/derived/rq2_blind/20261108-drop-transfer/. No human acceptance result is reported until these judgements arrive. MJu26a's pending null draws do not change this fixed-cut real-match selection.

## 2 Hz sweep

| Recording | Complete tasks | Missing | Refused | Whole settings |
|---|---:|---:|---:|---:|
| MJu26a | 497/674 | 168 | 9 | 25/43 |
| SH | 116/170 | 44 | 10 | 26/43 |
| SO | 116/170 | 46 | 8 | 28/43 |
| Total | 729/1,014 | 258 | 27 | 79/129 |

The audit indexes logical tasks and matching specification hashes, avoiding duplicated nested return folders. Complete tasks comprise 280 already imported on the PC and 449 with complete returned artifacts ready for later import. Forty-eight newly whole settings account for 336 of those tasks; 113 further completed tasks belong to settings still missing other channels.

Failures comprise 13 shared job.json.tmp rename conflicts and 14 SQLite disk-I/O errors. Unique per-writer temporary files address the observed race. Fresh recovery output/scratch locations avoid reusing potentially damaged scratch databases. Disk-I/O errors alone do not prove quota exhaustion; earlier logs/notes document a quota problem and the restart includes verified space release.

Complete-coverage examples are reported in Chapter 10: drop v1 gives 463/33 real/phase detections on MJu26a, 21/0 on SH and 28/0 on SO. Default OASIS gives 127,429/2,007, 20,095/353 and 25,556/364. Default wavelet encoded gives 1,883/38,714, 21/7,241 and 12/7,286. These are one-draw detection-count comparisons, not candidate counts or human precision.

The existing five-recording Chapter 6 census, earlier B5 timing calculations and frozen Chapter 8 classifier examination are not recomputed by this audit. Full B11 agreement/candidate formation still needs the unfinished CNN and matrix-profile settings.

## Recovery

The upload archive is in the main checkout, DATA/derived/hpc/recovery_20261108_upload.tar.gz. The instructions are in docs/thesis/hpc/recovery_20261108/README.md in the thesis worktree and inside the archive. The plan covers five seed channels, 29 CPU detector tasks, 250 CNN tasks and six matrix profiles split across two A100 packs.

No jobs were submitted by the assistant. No training or new matrix-profile computation ran on the PC. Thesis changes are TeX only; the full thesis PDF was not rebuilt.
