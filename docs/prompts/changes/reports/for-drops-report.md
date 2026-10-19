WORKTREE: C:\Users\mmebr\Documents\CNN\.claude\worktrees\for-drops
BRANCH: changes/for-drops

# for-drops (`ux-1019`, site-fixes item 3 follow-up): report

Base: `b7bb474` (changes/integration, which already holds site-fixes).

## 1. In plain words

Before windows are compared by shape, each one is moved so that the same moment sits at the same place. Think of
lining up photos of people jumping so that everyone's feet leave the ground in the same frame. For drops, that moment
is the bottom of the drop, placed a third of the way in, so the recovery after it fits inside the window. For
everything else, it is the largest swing, placed in the middle.

- **What you now have:** the Trace shape block has a **for drops** switch.
  - On: every window is lined up on the bottom of its drop, a third in (trough, 0.333).
  - Off: every window is centred on its largest swing (centre, 0.5).
  - If you set align or anchor yourself on the card, your value wins, and the page says so.
- **Analyse and Launch always agree.** The switch is part of the chain, and one piece of code in the core decides
  the alignment. The Analyse run, the trained model's recipe and Models › Launch all go through that code, so the
  tree and the model can never be cut at different places.
- **Launch:** under the setup line, a chip reads "for drops · on" or "for drops · off", followed by where the setting
  came from. For example: "for drops: on — set on the card", or "for drops: on — set on the card · align peak set on
  the card · the card's setting wins over the switch".
- **Not automatic, and why.** The switch is **off by default**: the app cannot tell on its own that a chain is for
  drops. Think of a pile of photos with no captions: nothing on them says which ones are of jumps.
  - A pool chain starts from saved window sets. Those sets are either evenly spaced grid windows or windows you
    labelled by hand.
  - None is made from a drop detector's detections, and no detector can sit before a Window pool.
  - Saved templates hold only a name and their steps.
  - So the only clue would be the template's name, and you asked us not to guess from names.
- **What would make "automatic" possible:** a window set built from a drop detector's detections, which would record
  "made from drop_detection" on its row. The pool would then carry that clue, and the switch's default could read
  it: `resolve_alignment` is the one place to add it. Until then, turn the switch on for drop work. It is the first
  parameter on the Trace shape card.
- **Options:**
  - (a) Keep it as built: off by default, and you turn it on.
  - (b) Add "window set from detections" in the Library, so the default can follow the source. This is a separate,
    larger piece of work.
- **Recommendation:** (a) for demo day; (b) only if you plan to build pools from detected drops.

## 2. Assumed

- **The switch lives on Trace shape, not on Window pool.**
  - The alignment is applied by Trace shape, and both Analyse (the block run) and Launch (`chain_settings` reads the
    template's Trace shape step) already read its parameters.
  - Launch re-opens a pool by overriding Window pool's `pool` parameter. A switch on the pool block would sit next to
    parameters that are ignored once a saved pool is re-opened.
- **"Set explicitly" means "different from the block's default".** Analyse fills in every parameter
  (`validateParams({})` writes `align: centre, anchor_frac: 0.5`), so a value equal to the default cannot be told
  from "not chosen". The rule, in `resolve_alignment`:
  - an `align` other than `centre` wins;
  - an `anchor_frac` other than 0.5 wins (it is ignored on grid);
  - otherwise the switch decides.
  - The cost: you cannot have "switch on, but centre at 0.5". That is simply "switch off".
  - The gain: templates saved before today (all carrying centre / 0.5) obey the switch the moment it is turned on.
- **Default OFF, so nothing already built changes.** With the switch off, the alignment, the shape key, the tree key
  and the B.2 recipe are bit-for-bit what they were. The recipe's `shape` does not carry `for_drops`: it carries the
  resolved `align` and `anchor_frac`, which is what decides the windows.
- **Cache and model identity:**
  - The shape key already holds `align`, and `anchor_frac` whenever it is off 0.5. A switched chain therefore gets a
    different key, and a matrix cut the other way is never served from the cache.
  - The step cache also sees `for_drops`, because it is a parameter. Pool chains bypass the step cache anyway: Window
    pool reads the store.
  - The B.2 recipe (the model's identity) carries the resolved values. A test pins that the on and off recipes
    differ.
- **The Analyse card caption** (`captions.ts`) names the switch, and any card value that differs from its default,
  using the adapter card's defaults. It decides nothing. The block page's run view shows the core's own
  `alignment_from` string.
- **"From the drop template" wording.** It never appears, because nothing is inferred. The source is either "set on
  the card" or "off (the default)".

## 3. Files

- `Working/training/shape.py`: `resolve_alignment(params)`, the single resolver. The DROP_ comment is updated.
- `Adapters/preprocessing_trace_shape.py`:
  - a new `for_drops` ParamSpec (bool, default False, listed first);
  - `_run` cuts at the resolved alignment, and its meta carries `for_drops` and `alignment_from`;
  - the anchor description points at the switch.
- `Working/training/shape_forest.py`: `_recipe_shape` (the model's identity) and `launch_shape` (Launch) call the
  resolver. `launch_shape` adds `for_drops` and `alignment_from`.
- `webui/server/serialize.py` (shared): `for_drops` and `alignment_from` added to the shape payload's key tuple.
- `webui/client/src/api/shape.ts` (shared, append-only): optional `for_drops` and `alignment_from` on `ShapeInfo` and
  `B2Setup.shape`.
- `webui/client/src/models/B2Launch.tsx`: the `b2-for-drops` chip line, and the tip reworded.
- `webui/client/src/analyse/views/ShapeViews.tsx`: the `shape-for-drops` line in the run view.
- `webui/client/src/analyse/captions.ts`: a `preprocessing.trace_shape` caption.
- `docs/manual/generated/blocks/preprocessing/trace_shape.tex`: regenerated. `version.tex` is unchanged.
- `webui/smoke_pages/zzzzzzzzzzz_ux1019_for_drops.json`: new (see §6).
- `docs/rq_roundA/RQ1-cluster-vs-manual-labels.md`: Known, Decisions and Log.
- Tests: `tests/test_shape_for_drops.py` (new), plus one test appended to `tests/test_webui_shape_b2.py`.

## 4. Tests

- **Red, commit `29f682b`:**
  - conda `tests/test_shape_for_drops.py`: 6 failed (unknown param `for_drops`).
  - venv `tests/test_webui_shape_b2.py -k drop_chain`: 1 failed.
- **What the new tests pin:**
  - The switch exists: a bool, off by default.
  - A non-drop chain resolves to `centre, 0.5`.
  - The switch on resolves to `trough, 0.333`.
  - An explicit align, anchor or grid wins either way, and the wording says so.
  - The recipe and `launch_shape` agree, and the on and off recipes differ.
  - The block's `_run` hands `trace_shapes` exactly what the resolver says.
  - venv, end to end: a drop template's **launch body carries `trough, 0.333`** and a non-drop template carries
    `centre, 0.5`. An Analyse run of the same chain with the switch on reports the same align and anchor as Launch.
- **Green, conda:**

  | Test file | Result |
  |---|---|
  | `test_shape_for_drops` | 6 passed |
  | `test_shape_forest` | 8 passed |
  | `test_training_shape_align` | 20 passed |
  | `test_training_shape` | 16 passed |
  | `test_block_standard` | 222 passed |
  | `test_manual_tables` | 28 passed |
  | `test_import_boundaries` | 4 passed |

- **Green, venv:** `test_webui_shape_b2` 7 passed.

## 5. Gates

- `tsc -b`: clean.
- `vite build`: built. Its only warning is the existing `kit/Gallery.tsx` INEFFECTIVE_DYNAMIC_IMPORT.
- `scripts/manual_tables.py --check`: was stale on `trace_shape.tex`, then regenerated.
- No browser smoke (no database in the worktree).

## 6. Smoke state (not walked)

- `zzzzzzzzzzz_ux1019_for_drops.json` › `ux1019-launch-names-the-for-drops-switch` (`models/results`).
  - It clicks `b2-launch-cnn-*`, the same way in as `zzzzzzzz_ai`'s state, and expects
    `b2-for-drops[data-for-drops="off"]`, `b2-shape-line[data-align="centre"]` and `b2-anchor-rule`.
  - Walk it after `zzzzzzz_ah_*` and `zzzzzzzz_ai_*`.

## 7. Risks

- **Turning the switch on re-cuts every window.** That means a new shape key, and the tree must be rebuilt (Ward on
  the sample: minutes). A model trained with the switch off is still listed. Its recipe says centre, so it is not
  mistaken for a drop model.
- **An old template with a non-default align** (for example `peak`) ignores the switch, as designed. Launch's line
  says so.
- **`captions.ts` is a second, display-only reading** of "differs from the default". If the rule in
  `resolve_alignment` changes, update the caption too. The run view and Launch show the core's own words.

## 8. Commits

    29f682b ux-1019: test - a "for drops" switch on Trace shape, one resolver for Analyse and Launch (red)
    52bee1f ux-1019: a "for drops" switch on Trace shape, resolved once in the core for Analyse and Launch (AM)
    643270d ux-1019: smoke state for Launch's for-drops line; RQ1 records the switch
    (+ this report's commit)
