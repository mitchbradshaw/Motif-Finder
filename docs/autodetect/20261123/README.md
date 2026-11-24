# Auto-detect v2 — refined (23 Nov 2026)

**Open `index.html`** in a browser, or serve the folder above with the `autodetect-pages` entry in
`.claude/launch.json` (port 8791) and go to `/20261123/index.html`. The first version's pages are in `../20261119/`
for comparison.

## What changed, and why (from your review of v1)

| Your screenshot | What was wrong | What v2 does |
|---|---|---|
| 1–2: small drops missed | Nothing proposed small drops (0.4–1.7 mV) next to big ones; every proposal nearby belonged to the big neighbour | **BEADS → noise threshold** (your 8 Nov chain, run 8718, which found the CH14 train): BEADS with a 60 s baseline, then a cut at **10 × the rolling one-hour noise** instead of a fixed mV level. Plus **drop v1 and drop v5 over 6-hour sliding windows** (the tool's own window code, 17 Oct), so a quiet stretch is not held to a loud week's bar |
| 3: a slice of a bigger drop | BEADS-invert always draws a 400 s box, and the merge chose it to stand for the event | **Every box is redrawn around its event** with the Library's **whole drop** (`Working/interrogation/whole_drop.py`, the rule you approved on 23 Nov). The box runs from the top of the drop to half recovery, or to the bottom if it never recovers, plus a tenth either side. M4's 218.5 h drop is now one box, 218:31–219:00 (146 mV) |
| 4, 6: overlapping and nested boxes | Each source draws its own box | Candidates whose falls overlap are **one event**, drawn by the deepest box. A step part-way down a fall folds into that fall. So does the rise back after a drop, which the either-side cut read as a spike. CH15 239.5–240.4 h now has 6 boxes that don't overlap (there were 11); CH14 433.8 h has one 20 s box (there were two) |
| 5: flat drift | R4's 30-minute window also reads a quarter of its length either side, so a drop just past the window's edge raised its score | **Flat-drift gate:** a candidate must keep at least 15 % of its range after the best smooth (cubic) curve is removed. This is judged over its original and redrawn boxes together, which keeps 100 % of accepted events on the references. **R4's scan boxes** are redrawn around the event inside them, and dropped if they hold none |

Two smaller changes came out of the runs:
- **R4 now scores each event with half its box's length of context either side.** It was trained on reviewed spans that include context, not on tight boxes. On the reviewed candidates, accepted events at p ≥ 0.5 went from 84 % to 96 % on M2_aug.
- **A detector box vouches only for the events it mainly points at.** These are the events at least half as deep as the deepest one it covers. Without this, a long drop v1 window lent its confidence to every small fall inside it.

## Results (confidence ≥ 0.5 unless noted)

| Reference | Run time | Candidates | Found | Hit rate | At ≥ 0.9: candidates · found · hit rate |
|---|---:|---:|---:|---:|---|
| M2_aug CH7_B2, 528 h | 146 s | 3,761 (7.1/h) | 209 of 212 (v1: 208) | 93 % (v1: 90 %) | 2,610 (4.9/h) · 197 · 96 % |
| MJu26a CH14, 264 h | 94 s | 3,099 (11.7/h) | 511 of 528 (v1: 517) | 98 % (v1: 98 %) | 1,631 (6.2/h) · 505 · 98 % |
| MJu26a CH15, 264 h | 84 s | 625 (2.4/h) | 177 of 186 (v1: 172) | 94 % (v1: 93 %) | 499 (1.9/h) · 172 · 94 % |
| M4 CH1_A1, 505 h | 97 s | 982 (1.9/h) | 46 of 47 (v1: 44) | 84 % (v1: 83 %) | 342 (0.7/h) · 43 · 88 % |

- **Speed:** each channel still takes under 2.5 minutes. The BEADS σ chain adds 25–80 s.
- **R4's own scan candidates** are now 42–602 per channel, down from 198–1,923.

**Your circled drops on M2_aug, 175 h:**
- Own candidates: 175:24 (0.96), 175:38 (0.98), 175:50 (0.87) and 175:52 (0.90).
- 175:22 is covered only by the box of the big drop just before it.
- 175:03, a 0.4 mV dip, is still missed.

## Still open, for the next round

1. **Slow rises boxed as "spikes".** The whole-drop rule measures rises as events too, so a slow drift upward can be boxed as a spike. Examples:
   - M4 216:44–218:45: a 2-hour R4-scan box over the recovery rise before the 218.5 h drop.
   - CH15 306:44–307:12: the rising drift of your fifth screenshot, now a 2 mV "spike".
   - M2_aug 175:40–175:54: a 0.7 mV rise.

   There are 181–1,499 spike-type candidates per channel. Possible fixes: require a spike's rise to be sharp, keep drops only for now, or leave them for review.
2. **CH14 lost 6 events** against v1 (511, was 517).
3. **The flat gate cannot catch a slow rise that ends in a real drop,** because the drop makes the stretch "not flat".

## Files

- Engine: `Working/autodetect/`.
  - `anchor.py`: the boxes, using whole_drop.
  - `gates.py`: the flat gate.
  - `chains.py`: now with `run_chain_windowed`.
  - `candidates.py`: `reanchor`, and agreement by main events.
  - `pipeline.py`: the v2 stages.
  - `sequences.py`: now takes `rule="gap"`.
- Tests: `tests/test_autodetect.py`, 48 tests.
- Scripts: `scripts/autodetect/common.py` holds the v2 detector line-up (`detector_specs`, `BEADS_SIGMA`, `WINDOWED`).
- Each reference's folder: the candidates CSV and the rest, as in v1. Candidates now carry `polarity`, `depth_mv`, `recovered`, their original boxes (`orig_start`, `orig_end`) and the flat-test score (`unexplained`).

**Review queues** are being built by the "NeurIPS demo prep" session:
- **Single candidates** will go to Review as machine detections through the existing detection-queue path.
- **Sequences** go through `Working.review.sequence_queue.send_to_sequence_review`.
- Auto-detect will use those entry points once that session hands them over; nothing here writes queues or detections.
