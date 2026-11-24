# Auto-detect v3 — drops and sharp rises (23 Nov 2026)

**Open `index.html`** in a browser, or serve the folder above with the `autodetect-pages` entry in
`.claude/launch.json` (port 8791) and go to `/20261123_v3/index.html`. The earlier pages are kept for comparison:
`../20261123/` (v2) and `../20261119/` (v1).

**New on every page:** type an hour in **go to** (`220:08` or `220.13`) and press Enter to see the 20 minutes
around it, or open a page at a time with `viewer.html#t=220:08`.

## What changed, and why (from your review of v2)

| What you asked or saw | What was wrong | What v3 does |
|---|---|---|
| Spikes (rises) "missed" on M4 at 109–131 h, 220:08 and 220:27 | v2 had found them (confidence 0.94–0.99), but you could not see them. Their boxes were a few seconds wide, drawn only as ticks in the thin strip above the trace. And the page hid every candidate no detector vouched for (319 on M4), which was a bug | Every candidate now has a **marker at any zoom**: ▼ below a drop's bottom, ▲ above a rise's peak. Candidates no detector vouched for are shown, with their own toggle, "R4 alone, inside another box". Rises are pink and have their own toggle. There is also a **go to** box |
| "Sharp rises only" | v2 boxed slow upward drifts as "spikes" | A rise is kept only when its **steepest 1-second step is at least 10 times the channel's 1-second step noise**. On M4, your circled spikes scored 20–44; the median rise candidate scored 4 |
| "Run the same (entire) process on the inverted signal" | — | The **whole process runs a second time on the inverted signal**: detectors, seeds, R4's scan and R4's scores, boxes and gates. Its drops are this signal's rises. The two runs are joined with the rules each run already applies to itself. A rise both runs found is kept once, from the run that scored it higher. The rise back after a drop folds into that drop, and the fall back after a spike folds into that spike |
| Narrow candidate at M4 281.5 h; "check candidates against the rule" | The whole-drop rule split your 50 mV decline into four at small pauses. It also stopped looking for the half recovery after ten fall times, so a sharp event with a slow recovery got no width at all | Raised with the session that owns the whole-drop rule (the NeurIPS demo session), which changed the rule. v3 uses the version pinned in each `run.json` (see "The whole-drop rule v3 uses" below) |

### The whole-drop rule v3 uses

Version `27506977efc8`, 17:20 on 23 Nov. It is **not committed until you OK it**. Each `run.json` records the hash
it ran on. What changed since the version you approved:

- **One sharp fall still has a width.** The half recovery is searched up to the next event's top, or 2 h. Before,
  the search stopped at ten fall times, so one sample of fall time could decide whether a shark fin had a width at
  all. That cut short 2–6 % of v2's boxes.
- **A decline is one drop through small pauses.** A pause must be a real stall, where the trace stops descending.
  A brief hesitation, or wiggles back to an earlier low, no longer ends a drop.
- **Separate drops stay separate.** A fall about five times steeper than the slow stretch before it starts a new
  drop, if it falls at least 15 % of the drop so far. A clear climb back also ends a drop.
- **The noise is read from a fixed hour round each box,** not from the box itself. One fall now gives one answer
  whatever box it is measured in.
- **A box holds an event whose steepest moment lies inside it,** even when its tail runs far past.
- **A sharp fall keeps its own settle.** A moment of flat right after the fall no longer ends the drop: a stall
  that ends in a slow creep is a pause only if it lasts at least 30 s. This came out of auto-detect's checks.

The rule's owner checked it on your accepted library (the 16:33 version):
- spans with no event: 55 → 47;
- widths measured: 2,115 → 2,260;
- depth within 5 % of before on 83 % of spans.

The 17:20 version changed 16 more spans' event count, 15 of them a sharp drop rejoined with its own settle. No
span lost or gained an event.

Still open with you: where a drop's tail ends when nothing stops it cleanly (a step on a pre-existing drift, or a
two-hour tail).

## Results (confidence ≥ 0.5 unless noted)

| Reference | Run time | Candidates: ▼ drops / ▲ rises | Found | Hit rate | At ≥ 0.9: candidates · found · hit rate |
|---|---:|---|---:|---:|---|
| M2_aug CH7_B2, 528 h | 4.9 min (v2: 2.4) | 3,564 (6.8/h): 3,271 / 293 | 206 of 212 (v2: 209) | 93 % (v2: 93 %) | 2,545 (4.8/h) · 199 · 95 % |
| MJu26a CH14, 264 h | 3.7 min (v2: 1.6) | 2,823 (10.7/h): 1,848 / 975 | 518 of 528 (v2: 511) | 98 % (v2: 98 %) | 1,687 (6.4/h) · 514 · 99 % |
| MJu26a CH15, 264 h | 2.8 min (v2: 1.4) | 530 (2.0/h): 505 / 25 | 176 of 186 (v2: 177) | 94 % (v2: 94 %) | 443 (1.7/h) · 172 · 94 % |
| M4 CH1_A1, 505 h | 3.5 min (v2: 1.6) | 678 (1.3/h): 542 / 136 | **47 of 47** (v2: 46) | 88 % (v2: 84 %) | 274 (0.5/h) · 43 · 88 % |

The run takes twice as long as v2 because the whole process runs twice. It is still under 5 minutes a channel.

**Your screenshots:**
- **The seven M4 spikes** (109:36, 114:10, 119:03, 123:20, 130:09, 220:08 and 220:27):
  - Each is now a rise that both runs found.
  - Confidence 0.97–1.00 (v2: 0.94–0.99): detectors and seeds now agree on them, not R4 alone.
  - Sharpness 12–44.
- **M4 281:30** is one drop, 281:14–282:51, 49.4 mV. v2 had a 16.5 mV slice, 281:29–281:37.
- **The slow rises are gone:** CH15 306:44–307:12 and M2_aug 175:40–175:54.

**What changed against your reviews** (accepted events v2 found at ≥ 0.5 and v3 does not, or the reverse):
- **M2_aug lost 3: 22:19, 248:02 and 525:10.** v2 found each only through a slow rise, with sharpness 2.5–5.3 and
  rising over 1 to 25 minutes. "Sharp rises only" removes these. You accepted those spans, so some slow rises are
  events to you (see "Still open").
- **CH15 lost 2.**
  - **217:44:** the new rule reads it as one 22.4 mV drop starting at 217:38.5. That box covers 44 % of your span,
    just under the "found" bar of half.
  - **266:34:** v2 credited it to a 2-hour slow-rise box. The two real drops either side are unchanged.
- **Gained:** CH14 7, CH15 1, M4 1. M4 now finds all 47.

**Rises** at ≥ 0.5: 293, 975, 25 and 136. Most land on material you haven't reviewed. Where they do land on
reviewed spans, 218 of 227 are accepted.

**Checked against the whole-drop rule:** each candidate's own box was measured again with the rule.

| | M2_aug | CH14 | CH15 | M4 |
|---|---:|---:|---:|---:|
| Same top and bottom, within 2 s (before) | 94 % (73 %) | 94 % (64 %) | 87 % (54 %) | 86 % (42 %) |
| No event found (before) | 3 (134) | 3 (266) | 0 (9) | 28 (237) |

The fall runs past its own box for 1–4 % of candidates (before: 8–11 %).

**A bug the checks found, fixed:** a slow climb that the sharp-rises rule removes could take the next real drop with
it.
- This happened at M4 64:00: your accepted 4.3 mV drop went missing in a first v3 run.
- The climb back after the 63:37 drop came out 0.11 mV deeper than the drop. So it was not folded in as that drop's
  rise back, and it stood as a "rise" of its own.
- The next drop then folded into it as "the fall back after a spike".
- The gate removed the climb, and the drop went with it.

What a run's own rules reject (a rise that isn't sharp, anything under the noise floor) is now set aside before
events are joined. The 64:00 drop is back, confidence 1.00.

## Still open

1. **Slow rises you accepted.** Three accepted M2_aug spans (22:19, 248:02, 525:10) hold only slow rises. Keep
   "sharp rises only", or let some slow rises through?
2. **The sharpness bar (10) is calibrated on M4 only.** Your circled spikes scored 20–44. It has not been checked
   by eye on the other channels.
3. **A rise's box ends halfway back down,** by the whole-drop rule. A long decay runs on past it: at M4 109:36 the
   box ends at 109:37.6, and the decay lasts to about 109:45.
4. **R4 judges the inverted run's rises as if they were drops.** It learned from your verdicts, mostly on drops. On
   its own training channels it scores almost anything high. "R4 alone, inside another box" means an event inside a
   detector's box that the box does not mainly point at, with no detector agreeing.
   - These are 316 candidates at ≥ 0.5 on M2_aug, 228 on CH14, 16 on CH15 and 51 on M4.
   - Where they land on reviewed spans, 42 of 44 are accepted.
   - They now have their own toggle.
5. **The whole-drop rule is uncommitted until you OK it.** Where a tail ends is still open with you. If it
   changes, these runs need re-doing; each `run.json` names the version it used.
6. **Sequences.** Drops and rises now form sequences separately. The 1-hour gap rule is used everywhere, because
   logISI found no valley on any channel.

## Files

- Engine: `Working/autodetect/`.
  - `pipeline.py`:
    - `auto_detect(..., invert=, keep_polarity=, min_sharpness=)` runs one pass.
    - `auto_detect_both` runs both passes.
    - `combine_runs` joins them.
    - `sharp_enough` applies the sharpness rule.
  - `candidates.reanchor(..., is_event=)` sets aside what the run's own rules reject before it joins events.
  - `gates.py`: `step_noise`, `sharpness` and `MIN_RISE_SHARPNESS`.
- Tests: `tests/test_autodetect.py`, 52 tests (56 with the import-boundary test).
- Scripts: `scripts/autodetect/`.
  - `common.make_r4_scorer(..., invert=True)` scores the inverted signal.
  - `run_references.py` records the rule files' fingerprints in each `run.json`.
- Each reference's folder holds the candidates CSV and the rest, as in v2. Candidates now also carry:
  - `run`: the signal, or the inverted signal;
  - `runs`: "both" for a rise both runs found;
  - `sharpness`.

  Sequences carry `polarity`.
