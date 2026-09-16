# Status — Analyse › Training (6 pages)

Builder: training. Code in `webui/client/src/training/`, reads in `src/api/training.ts`, fixtures in
`src/fixtures/training.ts`. Every page passes `demo` to `Header`; nothing calls the bridge.

| page | route | states (deep link) | status |
|---|---|---|---|
| analyse.training | `#/analyse/training` | `default` · `illustrative-human-windows` (`?source=human-windows`) · `source-popover` (`?popover=source`) · `history` (`?popover=history`) · `import` (`?popover=import`) · `send-review` (`?modal=send-review`) · `save-template` (`?modal=save-template`) · `running` (`?state=running`) · `failed` (`?state=failed`) · `stage-deleted` (row trash icon) | **done** |
| analyse.training.windows | `#/analyse/training/block/1` | `default` · `edited` (`?state=edited`) · `random-split` (`?split=random`) · `invalid-gap` (gap < window length) · `save-window-set` (`?modal=save-window-set`) · `send-review` (`?modal=send-review`) · `running` (`?state=running`) | **done** |
| analyse.training.matrix | `#/analyse/training/block/2` | `default` · `edited` (`?state=edited`) · `group-open` (`?open=catch22`) · `slurm` (`?modal=slurm`) · `upload` (`?modal=upload`) · `label-derived-on` (tick CNN scores) · `running` (`?state=running`) | **done** |
| analyse.training.cluster | `#/analyse/training/block/3` | `default` · `choose-k` (`?view=choose-k`) · `merge-pending` (`?merge=C5,C6`) · `save-grouping` (`?modal=save-grouping`) · `send-review` (`?modal=send-review`) · `criterion-locked` · `running` (`?state=running`) | **done** |
| analyse.training.encode | `#/analyse/training/block/4` | `default` · `window` (`?window=283`) · `edited` (tick Fusion) · `new-encoder-version` (`?encoder=new`) · `running` (`?state=running`) | **done** |
| analyse.training.model | `#/analyse/training/block/5` | `default` · `labels-manual` / `labels-both` (`?labels=manual|both`) · `focus-trial` (`?focus=trial`) · `send-review` (`?modal=send-review`) | **done** |

## Shared chrome (mirrors Interrogation's, cannot import it)

`src/training/chrome.tsx` — toolbar (name chip with validated rename · source chip + popover · null chip ·
estimate · History / Import / Save template · primary), `ChainCard` (kit `ChainRibbon`, 6 chips, `+`),
`UnappliedBar`, `RunVeil`, `Loading` / `LoadFailed` (a failed read is a red card, never a blank),
`SaveTemplateModal`, `SendToReviewModal` (P13, cap 20,000), `SaveWindowSetModal` (P18), `Heat`/`blanks`.
`src/training/draft.ts` — `useDemoState('analyse.training.draft')`, one `{applied, pending}` set per block.

## Cross-workspace writes (kit contract)

`review` `add-queue` (Send N unseen windows to Review — chain footer, 01, choose-k, 05) ·
`library` `save-window-set` (P18, 01) · `library` `save-template` + `analyse` `save-template` ·
`library` `save-grouping` (03) · `jobs` `add-job` (SLURM script in 02, trial job in 05) ·
`models` `add-training-job` (Train in Models, P11 → `#/models/launch?template=cnn_windows_v3`).

## Known gaps

- The dendrogram, the k-sweep line chart's shaded "current k" band and the encoded-image raster are drawn
  locally (SVG in `ClusterPage.tsx` / `Encoding.tsx`); no kit component draws them (see `pages/requests/training.md`).
- Per-class window counts are the frame's 142/98/51/32/13/7 scaled so the partition sums to the canon 543
  (fixture header note); the frames' own numbers sum to 343.
