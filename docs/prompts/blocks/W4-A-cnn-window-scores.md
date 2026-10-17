# W4-A — `catalogue.cnn_window_scores`: the trained CNNs' P(interesting) for every window at any scale, and the twelve CNN detection templates

Read [`00-common.md`](00-common.md) first. Commit prefix **`w4-a:`**. There is no plan section in `docs/research/` for
this one: the researcher asked for it on 2026-10-17, for the RQ4 detection sweep and Discovery › Map. Your core function
is a public API (RQ1's blind scoring, `Working/training/blind.py`, may call it later): name it, document it, keep it
stable.

## In plain words

The researcher has four CNNs that learned to tell "interesting" from "not interesting" ten-minute stretches of signal:
`fusion_cnn_3`, `GADF_cnn`, `GASF_cnn` and `recurrence_cnn` in `MODELS/`. Each was trained on 600-sample windows
(10 minutes at 1 Hz, from M2_aug) turned into a 224 × 224 picture: a Gramian image (GASF, GADF), a recurrence plot, or
the three fused as one RGB image. The researcher wants to slide each model along whole recordings at three window
lengths — 1 minute, 10 minutes and 1 hour — and mark the windows the model is confident about. Every window is
stretched or squeezed to 600 samples first, so its picture has the geometry the model was trained on. The model's
confidence becomes a score along the recording, and the existing Threshold block turns the confident windows into
detections. Four models × three scales = twelve detection templates.

## Why a new block rather than the existing chain

`cnn_detection` (`webui/server/templates.py`) chains `preprocessing.sliding_windows` → `catalogue.window_images` →
`catalogue.cnn_score` → `detection.threshold`. Read all four adapters. On real recordings it cannot do this job:

1. **It holds every image at once.** `window_images` returns an `(n, 224, 224, 3)` stack (150 KB a window) and refuses
   over `max_windows=2000`. Both Discovery runs of `cnn_detection` (2026-10-13) failed with *"4326 windows ×
   224×224×3 bytes = 651 MB exceeds max_windows=2000"* (2 channels × 721 h of M2_aug at 10-minute windows). One 721-h
   channel at 1-minute windows is 43,260 windows, about 6.5 GB, and the step cache would write the stack to disk too.
2. **It never resamples.** A window's n raw samples become an n × n matrix. A 1-hour window at 10 Hz (36,000 samples)
   is about 10 GB in float64, and a 1-minute window at 1 Hz (60 samples) is a 60 × 60 picture blown up to 224: not the
   geometry any of these models was trained on.
3. **Its default model cannot answer.** `MODELS/fusion_cnn.pth` has one output class, so `softmax(...)[:, 0]` is 1.0
   for every window and nothing says so. Class counts measured 2026-10-17 (`backbone.classifier.1.weight`):
   `fusion_cnn` 1; `fusion_cnn_2`, `fusion_cnn_3`, `GADF_cnn`, `GASF_cnn`, `recurrence_cnn` 2; `fusion_prediction_cnn`
   14 (a different, binned predictor).
4. **Flat or gapped windows score silently.** `Working/Catalogue/gramian/gramian_calc.py::_polar_encode` divides by
   `max − min`; a flat window, or one holding NaN, becomes an all-zero picture that still gets a score.

So: one block that encodes and scores one batch at a time and never holds more than `batch_size` images.

## The block

`catalogue.cnn_window_scores`, **WindowSet → Scores**. Stage `catalogue`, `category` as `catalogue.cnn_score`,
`page_name="CNN window scores"`.

**Core**, next to `Working/Catalogue/cnn/apply_cnn.py` (e.g. `Working/Catalogue/cnn/window_scores.py`): a plain
function such as `score_windows(x, starts_rel, length, *, image_type, model_path, resample_to=600, img_size=224,
batch_size=64, positive_class=0, on_progress=None, should_cancel=None) -> (probs, meta)`, where `probs[i]` is
P(positive class) for window i and NaN for a window left out. Reuse, do not copy:

- `apply_cnn._window_to_pil` (the exact pixels training used) and `apply_cnn.load_model`;
- `cnn_rangapur.get_transforms(img_size, is_train=False, is_rgb=(image_type == "fusion"))`, the training rule
  (`cnn_rangapur.py:135`). For these L → RGB images it should give the same tensor as `cnn_score`'s `is_rgb=True`:
  pin that in a test rather than assume it;
- `Working.distances.resample_to_length`.

Move the batched inference in `catalogue_cnn_score.score_stack` into the core, so both blocks run one implementation.

**Parameters** (bounds on every one):

- `image_type`: `fusion` · `GASF` · `GADF` · `recurrence` (the `window_images` choices).
- `model_path`: default `MODELS/fusion_cnn_3.pth` (the two-class fusion model `apply_cnn.py`'s own `DEFAULTS` names).
  The help text says to pick from Settings › Models & registration.
- `resample_to`: default **600** (the training windows). `0` = as is, which is the convention `blind.py` scored RQ1
  with. Otherwise at least 16 (the recurrence embedding, m = 3 and τ = 4, needs more than 8 points) and at most 2048.
- `img_size`: 224 (8–1024).
- `batch_size`: 64 (1–1024).
- `positive_class`: 0 = "interesting" (ImageFolder's alphabetical class order, as `cnn_score` and `blind.py` read it),
  checked against the checkpoint's class count at run time.

**Behaviour:**

- **Resampling rule**, stated in `meta["rules"]`: each window's L samples become `resample_to` points spanning the
  window. Downsampling is anti-aliased (block means when L is a whole multiple, else `scipy.signal.resample_poly`);
  upsampling is linear (`resample_to_length`). Name the choice and the reason in the docstring. When L equals
  `resample_to` it is the identity.
- **Refuse loudly** (ValueError naming the file and the count) for:
  - a checkpoint with other than two classes;
  - a `positive_class` out of range;
  - a checkpoint whose file name names a different image type from `image_type` (case-insensitive `fusion`, `gasf`,
    `gadf`, `recurrence`);
  - a missing file.
- **Leave out and count, never blank:** a window holding NaN and a flat window (max == min) score NaN and are counted by
  reason in `meta["skipped"]`.
- **Memory:** at most `batch_size` images alive at once.
- **Cancel and progress inside the step:** declare `on_progress` / `should_cancel` in `_run`, as
  `Adapters/detection_pan_matrix_profile.py` does. `Working/execution.py` forwards them, and `RecipeCancelled` is the
  one cancellation exception. Check between batches.
- **Threads:** no `torch.set_num_threads` (it is process-wide, and the bridge runs jobs on threads). Use CUDA if
  available, else the CPU (the researcher's machine has no GPU).
- **Loading must not download.** `EEG_CNN.__init__` builds `efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT)`,
  fetching ImageNet weights only for `load_model` to overwrite every one of them. Add a `pretrained` flag to `EEG_CNN`
  (default unchanged, so training is untouched) and build with `pretrained=False` when loading a state dict. Tests run
  with no network.

**Output Scores:** one value per sample of `x`. Each window's probability fills its samples (the later window wins where
windows overlap, as `cnn_score` does), and samples no window reaches are NaN. WindowSet starts are channel-absolute:
subtract the span offset, `round(t[0]·fs)`, as `window_images` does.

**meta:**

- `model_path`, `n_classes`, `positive_class`, `image_type`, `resample_to`, `resample_factor`;
- `window_length` (samples) and `window_s`;
- `n_windows`, `n_scored`, `skipped` (counts by reason);
- `window_scores` and `starts` (first 4096 of each), `p_range`, `p_quantiles` (5 / 50 / 95 %);
- `seconds_per_window` (measured);
- `training_scale`: one sentence saying the models were trained on 600-sample, 10-minute windows of M2_aug at 1 Hz,
  that any other window length is outside that scale, and that M2_aug scores are not out-of-sample (`blind.py`'s
  docstring says the same);
- `rules`.

**Cost:** declare `estimate` (`register_cost_model`, with the torch import and model load as the untimed warm-up) on the
per-window work. `estimate` sees the span and this block's parameters, not the windows, so state what you assume about
the window length. Report the projected wall time on this CPU for one 721-h, 1-Hz M2_aug channel at 60 s, 600 s and
3600 s windows.

Then **say what Discovery will do with that time.** Above `limit.Discovery` (20 min by default) a run is offered as a
SLURM script, and template results from the cluster cannot come back into Discovery today (`webui/server/jobs_routes.py`,
`SCRIPT_KINDS["detection_chain"]`). The researcher will probably raise the limit and run overnight locally, so say which
limit lets one full M2_aug channel run locally at each scale.

## Also fix (same failure, one rule)

- `catalogue.cnn_score` refuses a checkpoint with fewer than two classes (today it silently scores 1.0), through the
  core's check. No parameter changes, so no recipe hash moves.
- `cnn_detection` defaults to the one-class `fusion_cnn.pth`. Report that it should switch to `fusion_cnn_3.pth` or be
  retired in favour of the twelve; do not edit it (`webui/server/templates.py` is the manager's).

## The twelve templates

Define them in `tests/test_template_cnn_window_scores.py` as a module-level `TEMPLATES` list (the manager moves them
into `CANONICAL`). Each is `kind: "detection"`, `version: 1`, with three steps:

1. `preprocessing.sliding_windows`: `window_s` 60, 600 or 3600, with `gap_s` 0 so the windows tile the span. Its split
   columns are irrelevant to detection and ignored.
2. `catalogue.cnn_window_scores`: `image_type` and `model_path` per model (table below), `resample_to` 600.
3. `detection.threshold`: `threshold` 0.5, **a placeholder** the researcher will sweep. Adjacent windows above the cut
   merge into one span (`spans_from_mask`), scored by their highest window.

| model | `image_type` | `model_path` |
|---|---|---|
| `fusion3` | fusion | `MODELS/fusion_cnn_3.pth` |
| `gadf` | GADF | `MODELS/GADF_cnn.pth` |
| `gasf` | GASF | `MODELS/GASF_cnn.pth` |
| `recurrence` | recurrence | `MODELS/recurrence_cnn.pth` |

Names are `cnn_<model>_<scale>`, with scale `1min`, `10min` or `60min` (e.g. `cnn_gadf_10min`). Each description says,
in plain words:

- what the model was trained on;
- that 1 min and 60 min are outside the 10-minute training scale;
- that `threshold` is the knob to tune first;
- that a Discovery null of 20 surrogate draws re-runs the CNN 20 more times per channel.

The test runs all twelve through `Working.execution.execute_recipe` on a synthetic recording in a temporary database
(the `tests/test_template_dehshibi.py` pattern). It swaps `model_path` for small random-weight two-class checkpoints
written to a temp directory, because `MODELS/` is gitignored and absent from your worktree.

## The `windowset->scores` view row — handed to you

`tests/test_block_standard.py` fails any block whose conversion has no row, and no WindowSet → Scores block exists yet.
As W2-A did for `spanset->windowset` (the exception in `00-common.md`), make three edits:

1. Add the row to `webui/server/views.py::MODIFIERS`, e.g. "the windows on the trace, each shaded by its score, the
   curve below on the same x".
2. Map it in `webui/client/src/analyse/views/registry.tsx` to an **existing** component. The one `signal->scores` uses
   is the closest; add no new component.
3. Raise the count in `tests/test_block_standard.py`: rename `test_there_are_fourteen_modifiers…` to fifteen, with a
   comment.

Those three edits are all you touch under `webui/` and in that test file.

## Deliver

- The core module and `Adapters/catalogue_cnn_window_scores.py`.
- The `pretrained` flag in `Working/Catalogue/cnn/cnn_rangapur.py`, and its use in `apply_cnn.load_model`.
- The class check in `Adapters/catalogue_cnn_score.py`.
- Tests: `tests/test_cnn_window_scores.py` (core), `tests/test_adapter_cnn_window_scores.py` and
  `tests/test_template_cnn_window_scores.py`.
- The adapter counts in `tests/test_adapter_spec.py` and `tests/test_end_to_end.py` (the manager reconciles counts
  across branches).

## Acceptance

- [ ] **Same pixels as training.** For a 600-sample window at 1 Hz, the image equals `catalogue.window_images`' image
      for that window, and the score equals `catalogue.cnn_score`'s for the same checkpoint. `resample_to` 600 and 0
      agree when L = 600.
- [ ] **Resampling.** Windows of 60, 3,600 and 36,000 samples reach the encoder as 600 points. A known waveform (a slow
      drop and recovery) keeps its shape: correlation with its analytic 600-point version > 0.99.
- [ ] **Memory.** No more than `batch_size` images exist at once (instrument the model or the encoder to record batch
      shapes). A 20,000-window synthetic run completes without allocating an n-sized image array.
- [ ] **Refusals, each naming the reason:** a one-class checkpoint, a 14-class one, `positive_class` out of range, a
      file name naming another image type, and a missing file. `cnn_score` refuses a one-class checkpoint too.
- [ ] **Left out, counted.** Windows with NaN and flat windows score NaN and are counted by reason. An empty WindowSet
      gives all-NaN Scores and a `meta` that says why.
- [ ] **Geometry.** The Scores have one value per sample of `x`, NaN past the last whole window. A span that does not
      start at 0 maps its windows correctly, and Threshold's spans are unions of whole windows.
- [ ] **No network.** Loading a checkpoint works with torchvision's weight download made to raise.
- [ ] **Cancel and progress.** A cancel between batches raises the run's cancellation; progress fires once a batch.
- [ ] **Templates.** All twelve run end to end and each produces a SpanSet (empty is fine on random weights).
- [ ] **Shared tests.** `tests/test_block_standard.py`, `tests/test_adapter_spec.py`, `tests/test_import_boundaries.py`
      and `tests/test_templates.py` pass.

## For the report: what to check on real data

Ask the manager to:

1. Run one M2_aug channel at each of the three scales through each model and give the score distribution.
2. Score the windows the researcher labelled blind in RQ1 (`annotations.source = 'blind_test_review'`: 1,100 labels at
   1, 10 and 30 minutes) and give each model's balanced accuracy per scale, beside the majority baseline. That is the
   bar these templates must clear.

Name anything else you would want measured.
