# Status — Analyse › Training (6 pages)

Builder: training. Code in `webui/client/src/training/`, reads in `src/api/training.ts`, fixtures in
`src/fixtures/training.ts`. Every page passes `demo` to `Header`; nothing calls the bridge.

Gate at the last commit: `npx tsc --noEmit -p tsconfig.app.json` clean for
`src/training/**`, `src/api/training.ts`, `src/fixtures/training.ts`;
`smoke.py --url http://127.0.0.1:5173 --pages-only --only training` → **58 screenshots, 0 failures**
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

## Fixed after the first visual pass

- 01's ribbon marked every stage stale: the status read `(pending || staleFrom) ? 1 : staleFrom`, so a
  stale 04 dragged 01–03 down with it. Now `pending ? 1 : staleFrom`.
- 01's "At a boundary" close-up overflowed its card — the last window bars ran under the caption.
- The chain and 04 toolbars wrapped onto a second row at 1440; both estimates were shortened to the
  frame's wording.

## Known gaps

- The dendrogram, the k-sweep chart's shaded "current k" band and the encoded-image raster are drawn
  locally (SVG in `ClusterPage.tsx` / `Encoding.tsx`); no kit component draws them — see
  `pages/requests/training.md`.
- 01's chain row (on the chain page) still draws plain split bands; the labels, the drop marks and the
  window tick strip are on the block page's own strip.
- 02's chain-row badge shows `on cluster` where the frame shows `on cluster · cached` (the kit Badge takes
  one status).
- Per-class window counts are the frame's 142/98/51/32/13/7 scaled so the partition sums to the canon 543
  (fixture header note); the frames' own numbers sum to 343.
- 05's eight training-parameter Dropdowns are still page-local state (they do not survive leaving the
  page), but architecture and epochs now re-cost the 05 stage row and the estimate.

## Fix round 1 (all six pages)

Every P0/P1 from `critique/training/r1-*.json` is addressed. What changed, by page:

**analyse.training** — run steps map to numbered stages, so the `failed` badge lands on 04 Encode rather
than 03 Cluster; `chainStatuses` resolves `staleFrom` to a block id, so under the WindowSet source 03
Encode is badged `stale` as its own caption says; frame 0b now has its own header, a toolbar without
History/Import, the human-source hand-off copy with no Trial-job button and the amber `illustrative ·
out of scope` footer chip; bypass changes the row (badge `paused`, its own summary); an invalid junction
carries row-level fix actions and disables both hand-off buttons; the Model row's caption comes from the
block, so 0b stops citing "03 cluster" and "split from 01"; rename can be cancelled (Escape or Cancel);
Send to Review holds the field's own reason so the 20,000 cap holds; `?deleted=windows` deep-links the
stage-deleted state.

**01 windows** — the split strip is drawn here: labels in the bands, a red drop mark at every break, a
window tick row underneath; the geometry comes from `splitLayout(ratio, blocks)`, so the split ratio and
the block count move the bands, the counts and the verdict bars; the gap field's raw entry reaches the
checks card, the boundary verdict, the estimate and both primaries; the boundary check fails on a random
split; the bar names and counts the fields that changed; toolbar and bar offer one primary; `?state=edited`
moves the *applied* gap back to 5 so the deep link produces the pending change; the boundary close-up has
a pale amber gap band and its caption below the plot.

**02 matrix** — clip sets the heat ramp's domain and the legend's σ, per-window z-scoring centres the
columns; the bar lists what changed and distinguishes a column drop from a rescale; a column click
resolves through the shared window→hour→class helper.

**03 cluster** — the class subtrees close under the cut, so the line at 10.1 slices six subtrees apart;
the lock disables the Parameters criterion with a reason and offers an Unlock in the same callout the
toast points at; the chosen card carries a `chosen` / `locked` badge; Save grouping records the selected
scope.

**04 encode** — image size and PAA move the disk and time estimates; the window chip reads class, split
and hour from the shared helper, so `Open in Encode` from 02 lands on the same window it named; browse
class cards sample windows that really are in that class.

**05 model** — the 05 row is re-costed and re-captioned from the architecture and epochs selected and the
04 row from 04's encode settings; the estimate is the sum of the ticked stages; with nothing ticked,
Copy script, Download trial job and both Train in Models buttons are disabled with a reason.

Two function findings did not reproduce and were left alone after checking in the browser: the matrix
column click does select a window (a click inside the row-label gutter does not, which is what the
critic's 20 % offset hits), and the choose-k criterion cards do mark their selection (`aria-checked`,
not `aria-pressed`) — a visible badge was added anyway. The bar primary after a completed run was
already disabled with "no unapplied changes".

New states in `smoke_pages/training.json`: `rename-cancelled`, `criterion-locked-in-params`,
`stage-deleted-by-click`, `stage-deleted`. `stage-04-off` moved to the end of the model states because
it leaves the shared draft with nothing ticked.
