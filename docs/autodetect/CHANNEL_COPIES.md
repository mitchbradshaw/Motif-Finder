# Teaching the app which recordings are copies — a note, not built yet (24 Nov 2026)

You asked for this note before going live: "make a note on how to approach the 'teach the app which recordings are
copies' functionality, but dont implement yet". Nothing below is implemented.

## In plain words

Think of one lecture recorded three times: on a good recorder, as a compressed copy of that recording, and as a
4-hour clip cut from it. You wrote your notes in the margin of the good recording. When the app shows you the
compressed copy, it has no idea your notes apply there too, so it asks you the same questions again.

The app stores each copy as its own recording, and every "has the researcher already judged this?" check looks only
at the recording in front of it. Teaching the app which recordings are copies means giving it a small lookup table:
these recordings are the same physical channel, and here is how a moment on one lines up with a moment on another.
Every place that asks "already judged?" would then look across all copies.

**Recommendation:** fill in the copy links the database already has room for, check each one against the
waveforms, and let you approve them. Move the converter that the thesis scripts already use into the app. Then make
Review's "already judged" check read across copies first. The Discovery scoreboard, the coverage map and the Library
follow after that. The work is about a day, plus agreeing the details with the NeurIPS session, which owns the
Library catalogue. Details follow.

## What goes wrong today

- **Review's check.** Review's "already judged" check (`Working/review/queues.py`, `_prior_verdicts`) reads the
  **annotations** on the candidate's own `recording_id` and nothing else. It never reads adjudications (verdicts
  given on detections in Review queues), and it never reads another copy.
- **MJu26a is the case that bites.** Your verdicts on MJu26a sit on the **10 Hz copy**: CH14 is recording 663 and
  CH15 is 664. Auto-detect, the 2 Hz sweeps and the thesis runs use the **2 Hz copy**: 705 and 706. Review therefore
  asks again about events you have already judged. The Auto-detect Send panel now warns about this.

**The copies in this database (checked 24 Nov):**

| Physical channel(s) | Copies | How they relate |
|---|---|---|
| MJu26a, 16 channels | `MJu26a.mat` (7.246 Hz, as recorded) | the original; its sampling is uneven |
| | `MJu26a_fs10.mat` (10 Hz, 22,892,769 samples) | resampled; **where the verdicts live** |
| | `MJu26a_fs2.mat` (2 Hz, 4,578,553) | block means of 5 fs10 samples; sample centres are +0.2 s later |
| | `L_LM_Jul_26_J_raw.mat` (10 Hz, 5 channels) | the fs10 samples ×1000 plus an offset; its channels 0–4 are physical 9, 12, 13, 14, 15 |
| | `L_LM_Jul_26_J_raw_fs2.mat` (2 Hz, 5 channels) | its 2 Hz block means |
| | `Mushroom_260720_0509_4hrs_CH14_fs1.mat` (recording 385, 1 Hz) | a 4-hour CH14 excerpt of recording 542 (L_LM CH14): decimation 10, offset 15,777,590 |
| SH, 4 channels | `SH.mat` (10 Hz, 17,280,001) and `SH_fs2.mat` (2 Hz, 3,456,000) | probably block means (17,280,000 / 5); not verified |
| SO, 4 channels | `SO.mat` and `SO_fs2.mat` | same pattern as SH; not verified |
| M2_aug, 16 channels | `M2_aug_concat_fs1.mat` (2,595,600) and `M2_aug_concat_fs2.mat` (5,104,799) | **unresolved**: 5,104,799 is not twice 2,595,600, so either the joins differ or it is not a straight copy. Check before linking |

**Not copies:**
- `M2_aug` and `M2_concat` are different data (different recordings, different concatenation); never link them.
- M4 has a single file.
- CO, LM, F2B, M1/M100/M101 and the Adamatzky and Dwij sets have no copies here.

**What the app holds already:**
- `recordings` has `parent_recording_id`, `parent_offset` and `decimation` columns.
  - Only one row fills them: 385 → 542, decimation 10, offset 15,777,590.
  - `fs_source` says only how a rate was found ('read' or 'inferred'), not what a recording was derived from.
- Everything else lives in `scripts/thesis/accepted_catalogue.py`, `canonical_span()`:
  - The MJu26a_fs2 → fs10 and L_LM → MJu26a_fs10 links are hard-coded by file name.
  - So is the L_LM channel list (`LLM_CHANNELS`).
  - It maps edges by the fs ratio.
  - It is a script, so the app cannot import it.
- `collect()` in the same script is the one place that already gathers **every** judgement onto one canonical
  channel. It reads:
  - adjudications (latest own look per detection; carried labels skipped; surrogates skipped; span edits applied);
  - annotations, sorted into `event_span`, `reviewed_region` and `labelled_window`.
  - The imported 10-minute and blind-test window labels are `labelled_window`. They are not event judgements and
    must never hold an event back.

## The options

1. **Fill in the columns the database already has.**
   - Set `parent_recording_id`, `decimation` and `parent_offset` on every copy row, all pointing at one canonical
     row per physical channel (MJu26a_fs10, SH.mat, SO.mat).
   - No schema change.
   - `canonical_span()` already follows these columns, so its hard-coded file names can go.
   - Limit: one integer decimation. That covers the 2 Hz block means (5) and the excerpt (10), but cannot describe
     the uneven 7.246 Hz original. Leave that one unlinked, as the catalogue already does.
2. **A new `recording_copies` table**: `copy_id`, `canonical_id`, time factor (a real number), offset, how it was
   verified, when, and by whom.
   - More expressive (a non-integer factor) and an additive schema change through `init_db()`.
   - It holds the same information as option 1 in a second place, so the two could drift apart.
3. **Keep it in code**: a Python table like the script's.
   - The quickest.
   - But Settings cannot show it, you cannot approve it, and it can go stale without a test noticing.

**Recommendation: option 1.**
- Register the links with a one-off script (`scripts/register_channel_copies.py`). For each link it measures the
  correlation between a copy and its canonical row over a few windows, as was done for L_LM (r = 1.00000 on 27 Oct).
- Show each link on Settings › Datasets for you to approve. Nothing counts as linked until you have.
- Move `canonical_span()` into the core (for example `Working/recordings/copies.py`), have the thesis script import
  it, and add a reverse map: canonical → this copy's samples.

## Where it plugs in, in order of payoff

1. **Review: rediscovery** (`queues._prior_verdicts`).
   - For a candidate on any copy, read the judged spans on every copy of its channel and map them into the
     candidate's samples before the usual matching rule.
   - Decide with you whether **adjudications** count as "already judged" too. Today they do not; the catalogue
     counts them.
   - **Cache.** The queue-structure cache (`_structure_fingerprint`) reads "the human spans on those recordings".
     That list must grow to the copies' annotation rows plus the link rows. Otherwise a new verdict on the 10 Hz copy
     would leave a 2 Hz queue's cached structure stale.
2. **Auto-detect.** Its Send-to-Review "held back" count follows from 1. The Send panel's "spans you judged on this
   recording" becomes "on this channel, any copy".
3. **Discovery scoreboard** (`Working/discovery/scoreboard.py`): "already judged", "reviewed" and precision per
   channel use the same reads. Its `inputs_fingerprint` must follow in the same way.
4. **Coverage map** (`Working/discovery/coverage_map.py`, the reviewed share).
5. **Library** (`Working/library/matching.py`: the artifact spans and per-recording verdicts) and the catalogue's
   canonical coordinates. This belongs to the NeurIPS session; agree the canonical choice there first.

**What it must never do:**
- copy a verdict into a new row on another copy (that would forge a human judgement, against CLAUDE.md rule 5, and
  count it twice);
- merge recordings;
- let a window label hold back an event.

## Tests to write first

- `canonical_span` round trips. A span on 705 maps to 663 and back within one 2 Hz sample. The excerpt maps
  385 → 542 → 663. L_LM channel 2 maps to physical 13.
- Review:
  - a detection on 705 matching an annotation on 663 is held back;
  - the same span on 706 (another channel) is not;
  - M2_aug and M2_concat stay unlinked;
  - a window label never holds back an event.
- Cache: a new annotation on 663 rebuilds the structure of a queue built on 705.
- Speed: `_prior_verdicts` on the scale fixture stays inside the AR speed-pass budget.

## Risks

- **The uneven original.** No constant factor maps `MJu26a.mat` (7.246 Hz). Keep it unlinked, or map it by
  timestamps.
- **The +0.2 s block-mean shift.** On the 2 Hz copies sample centres sit 0.2 s late. That is well inside the
  matching tolerance for events seconds long, but say so in the code.
- **A wrong link hides real events.** Hence the waveform check and your approval for each link.
- **The held-out lock.** A copy of a held-out recording must be held out too. M4 has no copies today; the
  registration should refuse to link around the lock.
- **Shared code.** Review's resolver is shared and the Library is the NeurIPS session's. It needs one owner for the
  change and the per-merge gate.

## How tonight's Auto-detect queue handles this without the feature

The review queue built on 24 Nov (queue 57, `docs/autodetect/20261124_queue/`) uses `collect()` and
`canonical_span()` from the thesis script, in a script only. It leaves out every candidate that matches an event you
judged on any copy, whether annotation or adjudication. It never leaves one out because of a window label or a
whole train accepted in one go (a judged span over an hour and more than 4× the candidate). Review's own check
still cannot see across copies, so this was done before the queue was written. That is also why Review held back
only 4 of its 5,291 events itself.
