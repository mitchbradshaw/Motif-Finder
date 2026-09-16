# Frontend-design fog — Analyse › Training

Places where a frame assumes something the core, the canon or the spec cannot settle. Each bullet:
question · why it matters · source · what was built.

1. **The frames' class counts do not sum to the frames' own window count.** Frame 2 draws six classes of
   142 / 98 / 51 / 32 / 13 / 7 = 343, while every other frame (and the footer of frame 0) says 543 windows.
   · A partition that does not cover its set makes every per-class number and every image count wrong. ·
   frames 0, 2, 3, 4. **Built** with the frame's shape rescaled to sum to 543 (260 / 180 / 51 / 32 / 13 / 7),
   noted in the fixture header. Which number is authoritative is still open.

2. **Where does the blocked split go when the source is a WindowSet?** Frame 0b removes the sliding-windows
   stage (P15), and with it the stage that creates the split — but the model still needs a leakage-free
   split, and the source's windows may already overlap in time. · It decides whether a saved window set can
   be trained from at all. · frame 0b, backlog B7. **Built** as the amber B7 callout stating the question,
   with a candidate (a split filter over the source windows, blocked by recording and time, gap ≥ one
   window length, block-edge windows dropped). Not implemented anywhere.

3. **Is the gap `≥ window length` or `≥ window length − stride`?** P12 requires that no training window
   shares a sample with a validation window. With 10 min windows on a 5 min stride, a 10 min gap is exactly
   enough; the frames also show `gap 5 min` as the value before the edit, which leaks by half a window. ·
   The guard is the page's main safety claim. · frame 01, P12. **Built** as `gap ≥ window length`, with the
   frame's 5 min shown only as the "was" value of the pending edit.

4. **Cluster class colours are a categorical palette, not verdict hues.** §3 assigns meanings to blue /
   green / amber / red / purple, and a six-class partition needs six colours that mean nothing but "a
   different class". · A red class reads as "failed" and a green one as "human" to anyone who learnt §3. ·
   §3 vs frames 2 / 3. **Built** with a separate categorical ramp, never the status colours; the status
   colours stay for badges and bands on the same pages. Worth an explicit §3 sentence.

5. **`cached` and `on cluster` are one field in the frames and two facts.** Frame 0's 02 row reads
   `on cluster · cached`: where it ran, and whether the result is reusable. The kit `Badge` takes one
   status. · The ribbon badge is how a user sees what will re-run. · frame 0, §0 badge words.
   **Built** as `on cluster` on the row (the stronger fact); `cached` shows in the block page's compute card.

6. **What does "Export run" export?** Frame 0's footer offers it beside Send to Review with no destination,
   no format and no frame behind it. · It is the only footer action with no consequence drawn anywhere. ·
   frame 0. **Built** as a not-wired toast naming the call.

7. **The trial job's stage range is derived, but the frame's is fixed.** Frame 4 says `stages 04 → 05` while
   also letting every stage be ticked; ticking 02 would make the range `02 → 05` and the cost far larger
   than the "trial ≈ 2 h 40" in the toolbar. · The estimate and the script would disagree. · frame 4.
   **Built** with the range and the script's `--from-stage` derived from the ticks; the toolbar estimate
   stays the frame's fixed string, so the two can disagree by design until a cost model exists.

8. **"Both, paired" is offered in Analyse but runs in Models.** The third label source is selectable here
   and its own description says it runs elsewhere. · A control that cannot act where it sits is a dead
   click by the brief's standard. · frame 4, P11. **Built** as selectable, with a blue callout carrying the
   Models hand-off, so the click always ends somewhere.

9. **No frame shows a failed training run.** Every other chain page in this group has a failure state; 05
   has none, and a GPU job that dies is the likeliest outcome of the whole page. · Loud failure is a house
   rule. · frames 0–4. **Built** with the failure state on the chain page only (`?state=failed`), which is
   where the run lives; 05 itself never runs anything.

10. **Block indices differ between the live detection chain and this one.** `#/analyse/block/0` is the
    first detection stage; `#/analyse/training/block/1` is the first training stage. · Two routes that look
    alike count differently. · inventory, `analyse/index.tsx`. **Built** as 1-based here, matching the
    displayed stage number. Recorded so the dispatcher's asymmetry is not read as a bug.
