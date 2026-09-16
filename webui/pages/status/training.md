# Status — Analyse › Training (6 pages)

Builder: training. Code in `webui/client/src/training/`, reads in `src/api/training.ts`, fixtures in
`src/fixtures/training.ts`. Every page passes `demo` to `Header`; nothing calls the bridge.

Gate at the last commit: `npx tsc --noEmit -p tsconfig.app.json` clean for
`src/training/**`, `src/api/training.ts`, `src/fixtures/training.ts`;
`smoke.py --url http://127.0.0.1:5173 --pages-only --only training` → **54 screenshots, 0 failures**
(0 console errors, 0 server tracebacks).

| page | route | states (deep link) | status |
|---|---|---|---|
| analyse.training | `#/analyse/training` | `default` · `source-popover` (`?popover=source`) · `illustrative-human-windows` (`?source=human-windows`) · `history` (`?popover=history`) · `import` (`?popover=import`) · `send-review` (`?modal=send-review`) · `queued-to-review` · `save-template` (`?modal=save-template`) · `rename-invalid` · `running` (`?state=running`) · `failed` (`?state=failed`) · `stage-deleted` (row trash icon) | **done** |
| analyse.training.windows | `#/analyse/training/block/1` | `default` · `edited` (`?state=edited`) · `invalid-gap` (gap < window length) · `random-split` (`?split=random`) · `boundary` · `verdicts` · `save-window-set` (`?modal=save-window-set`) · `send-review` (`?modal=send-review`) · `running` (`?state=running`) | **done** |
| analyse.training.matrix | `#/analyse/training/block/2` | `default` · `edited` (`?state=edited`) · `group-open` (`?open=catch22`) · `label-derived-on` (tick CNN scores) · `readout` · `slurm` (`?modal=slurm`) · `upload` (`?modal=upload`) · `running` (`?state=running`) | **done** |
| analyse.training.cluster | `#/analyse/training/block/3` | `default` · `occupancy` · `choose-k` (`?view=choose-k`) · `criterion-locked` (`&locked=1`) · `merge-pending` (`?merge=C5,C6`) · `save-grouping` (`?modal=save-grouping`) · `send-review` (`?modal=send-review`) · `running` (`?state=running`) | **done** |
| analyse.training.encode | `#/analyse/training/block/4` | `default` · `window` (`?window=283`) · `window-by-pager` · `edited` (`?state=edited`, or tick Fusion) · `new-encoder-version` (`?encoder=new`) · `browse-gadf` (`?browse=gadf`) · `running` (`?state=running`) | **done** |
| analyse.training.model | `#/analyse/training/block/5` | `default` · `labels-manual` / `labels-both` (`?labels=manual\|both`) · `stage-04-off` (untick 04 → 05 disabled with a reason) · `trial-job-created` (Download trial job) · `focus-trial` (`?focus=trial`) · `send-review` (`?modal=send-review`) · `save-template` (`?modal=save-template`) · `held-out-locked` | **done** |

## Shared chrome (mirrors Interrogation's, cannot import it)

`src/training/chrome.tsx` — toolbar (name chip with validated rename · source chip + popover · null chip ·
estimate · History / Import / Save template · primary), `ChainCard` (kit `ChainRibbon`, 6 chips, `+`),
`UnappliedBar` (amber dot only while something is pending), `RunVeil`, `Loading` / `LoadFailed` (a failed
read is a red card, never a blank), `SaveTemplateModal`, `SendToReviewModal` (P13, cap 20,000),
`SaveWindowSetModal` (P18), `BlockFrame`, `Heat`.
`src/training/draft.ts` — `useDemoState('analyse.training.draft')`, one `{applied, pending}` set per block;
the draft survives navigation between the six pages, not a reload.

## Guards the pages actually enforce

- **P12** gap NumberField validated `≥ window length` (red + inline reason, Apply blocked); `random` split
  selectable but marked as leaking with a route back to blocked-by-time; label-derived feature groups
  (Random Forest, CNN scores) off by default and ticking one raises the red leakage callout.
- **P13** Send N unseen windows to Review, cap 20,000, from the chain footer, 01, choose-k and 05.
- **P15** with the WindowSet source the sliding-windows row is **absent** (not greyed) and the stages
  renumber; the open question rides in the amber B7 callout.
- **P18** Save window set on 01.
- **P11** Train in Models → `#/models/launch?template=cnn_windows_v3`.
- **D6** `M4_aug` never appears as a choice; the held-out line on 05 carries the lock and the reason.
- 05: unticking 04 Encode disables 05 with "04 Encode is unticked — 05 would have no images to train on".

## Cross-workspace writes (kit contract)

`review` `add-queue` (Send N unseen windows to Review — chain footer, 01, choose-k, 05) ·
`library` `save-window-set` (P18, 01) · `library` `save-template` + `analyse` `save-template` ·
`library` `save-grouping` (03) · `jobs` `add-job` (SLURM script in 02, trial job in 05) ·
`models` `add-training-job` (Train in Models, P11).

## Known gaps

- The dendrogram, the k-sweep chart's shaded "current k" band and the encoded-image raster are drawn
  locally (SVG in `ClusterPage.tsx` / `Encoding.tsx`); no kit component draws them — see
  `pages/requests/training.md`.
- 05's eight training Dropdowns and 01's chain row: see below. Fixed after the first pass — the ribbon on
  01 marked every stage stale (an `||`/ternary precedence slip), and the boundary close-up overflowed its
  card.
- 01's chain row draws the split bands without the frame's inline `train / val / train / test` labels and
  without the window tick strip beneath them (the block page has both).
- 02's chain-row badge shows `on cluster` where the frame shows `on cluster · cached` (the kit Badge takes
  one status).
- Per-class window counts are the frame's 142/98/51/32/13/7 scaled so the partition sums to the canon 543
  (fixture header note); the frames' own numbers sum to 343.
- The eight training-parameter Dropdowns on 05 are page-local state: they change the control and nothing
  downstream, because no frame shows what a different architecture would do to the cost.
