# Shared-code requests — Review builder

Worked around locally in webui/client/src/review/; nothing blocks.

- **kit/plots.tsx `Trace` — time tick format.** For spans ≤ 20 min `fmtAxis` prints 4 decimals ("192.3380 h"); frames review-1/2 print 3 ("192.338 h") and review-5 prints 2 for a 600 s window ("3.13 h"). Request a `tickFormat` / `tickDigits` prop. Workaround: `timeUnit="none"` plus a local HTML tick row (`review/parts.tsx` `TimeTicks`) that assumes Trace's padL 44 / padR 10.
- **kit/plots.tsx `Trace` — unit label collides with the bottom mV tick when `timeUnit="none"`** (both drawn at the same y). Workaround: `unitLabel={false}`, "mV" printed in the local tick row.
- **kit/plots.tsx `Trace` — band edges and label lane.** Frames draw 1 px blue edges on a detected band and keep the band label off the trace; `markers` draw dashed lines that cross long labels. Request `bands[].edges` and a label lane above the plot area. Workaround: band fill only.
- **kit/surfaces.tsx `Popover` — header actions slot** (frame 1b has a × in the popover header). Workaround: × passed inside `title`.
- **kit/forms.tsx `RangeSlider` — `disabledReason` prop** (Slider has one). Workaround: wrapped in `DisabledReason`.
- **fixtures/canon.ts — `VERDICTS.seed` colour** is blue; frame review-6 draws the seed verdict green (human origin, §3). Review uses green locally for seed selection and verdict dots.
- **fixtures/canon.ts — F-11 members** is `null`; frames print 17. Review uses 17 from its own fixture (fog).
- **fixtures/canon.ts — `REVIEW_QUEUES`** lacks the Explore spans queue (proposed q-16) and per-queue totals/judged counts; Review extends them in fixtures/review.ts.
- **shell/pages.ts** — review-7-batch-undone is listed under review.inspector but draws the cluster page; consider moving it to review.cluster (the smoke manifest lists it under both).
