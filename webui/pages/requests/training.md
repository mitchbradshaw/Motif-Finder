# Kit / shared requests — Training builder

Written from `webui/client/src/training/`. Everything below is **worked around locally** in that
directory, so nothing here blocks the build; each entry says where the local stand-in lives.

## kit

1. **A dendrogram plot with a draggable cut line.** Frames 2 / 2b need a hierarchical tree over ~543
   leaves, coloured below the cut, with a horizontal cut handle that writes a pending k. Nothing in the kit
   draws a tree. *Workaround:* hand-rolled SVG in `ClusterPage.tsx` (`dendrogram`, `cut-handle`) over a
   fixture tree; it does not virtualise, so the leaves are binned.

2. **An image/matrix raster component.** 04 needs a square `n × n` field of values in [−1, 1] on a
   diverging ramp — a GASF/GADF/recurrence plot. `Heatmap` is close but is built for labelled rows and
   columns with a legend and cell padding, and at 22 × 22 in a 168 px box its labels and gaps dominate.
   *Workaround:* `Encoding.tsx` paints the raster directly (one `<rect>` per cell, no axes).

3. **`LineChart` wants a shaded x band.** The k-sweep (frame 2b) shades the current k across all three
   linkage curves. `Trace` has `bands`; `LineChart` does not. *Workaround:* an absolutely-positioned strip
   behind the chart in `ClusterPage.tsx` (`k-sweep`), which is why it does not move with a rescale.

4. **`Badge` takes one status where two are true.** A stage can be both `on cluster` (where it runs) and
   `cached` (whether it re-runs). See fog 5. *Workaround:* the ribbon and rows show the stronger word only.

5. **`Checklist` has no per-item action.** Frame 4's "Before this trains" hangs two fixes off two of the
   six checks (*Merge C5 + C6 in 03*, *Send 412 to Review*). *Workaround:* the actions sit in a row beneath
   the list (`before-trains`), so which check each belongs to is implied, not drawn.

6. **`CodeBlock`'s Save writes nothing and cannot be hidden per-button.** Passing `save={false}` removes it
   entirely, which is what 05 needs (the frame has *Download trial job* instead), but 02's SLURM modal
   wants Copy without Save. Currently Copy and Save are separate booleans — fine — but a `onCopy` hook
   would let the page own the toast. *Workaround:* 05 calls `navigator.clipboard` itself for *Copy script*.

## fixtures/canon.ts

7. **`TRAINING_CHAIN` / `TEMPLATES_BY_KIND` were proposed in the inventory and are not in canon.** Models ›
   Launch and Library › Templates list the same template (`cnn_windows_v3`) and the same six stages this
   unit draws. *Workaround:* `fixtures/training.ts` owns `CHAIN`, `CANON_TEMPLATES` and `IMPORT_TEMPLATES`
   locally; if Models has its own copy, the two can drift.

8. **Run `#140` is mapped to `spike_shape_v1` in canon but is named "F-03 slope interrogation".**
   Recommended: `#140` → `sharkfin_slope_v1`. *Workaround:* the History popover on the chain page lists
   `#140` with the run's own label and does not name a template.

## shell

9. **No route exists for a stage inserted into a chain** (the §6.4 type-contract modal). Every `+ insert`
   and the ribbon's `+` therefore end in a not-wired toast. This is a chain-builder surface, not a training
   one — noted so the owner knows two pages are waiting on it.
