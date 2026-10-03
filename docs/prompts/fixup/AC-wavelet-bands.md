# Fixup AC — a wavelet decomposition is a band source for RQ4

**Runs after `Z`** (it extends `Z`'s band scope). **Wave 5, beside `W`.** Written 2026-10-03 from
`QUESTIONS.md` Round 10 **Q-W3**, which is answered. It serves **RQ4**: *does band decomposition followed by
symbolic encoding surface regions raw-signal methods miss?* The researcher wants that question asked with
wavelet layers as well as with bandpass bands.

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python
`"/c/ProgramData/anaconda3/python.exe"`). Read these first:
- `CLAUDE.md`;
- `docs/BLOCK_INTEGRATION.md` (the whole thing; it is how a block is added and drawn);
- `docs/prompts/rq_roundA/RQ4-bands-and-symbols.md`;
- `Z-band-scope-and-compare-by-verdict.md` and its report `reports/Z-*.md`;
- `Adapters/preprocessing_bandpass.py`, the model for a Signal → Signal block;
- `Working/run_groups.py::materialize_target`.

Commit prefix `fixup-ac:`. Test-first: your first commit touches only `tests/` and must fail.
**`--sandbox` only.**

## In plain words (the researcher asked for this framing)

A bandpass filter cuts the signal at two frequencies you choose. A wavelet decomposition instead splits it
into a ladder of octave layers, each roughly half the speed of the one above. It is better at keeping a sharp
event sharp while doing so. Each layer can be turned back into an ordinary signal. That means everything
downstream (detrend, symbolic encoding, symbol search) can read a layer exactly as it reads a bandpassed
signal.

## Where it stands

- **What exists:**
  - `preprocessing.wavelet_transform` (Signal → Encoding, a Morse scalogram for Dehshibi);
  - `detection.wavelet_summation` (Encoding → Scores);
  - `detection.wavelet_scattering` (Signal → Encoding; its `kymatio` dependency is broken against the
    installed scipy).
- **What's missing:** no block turns a decomposition back into a band-limited **Signal**.
- `pywt` **1.8.0 is installed** in the conda base. It's already a dependency, so it's allowed; do not install
  anything.
- `Z` was told to make a band scope entry typed (`{kind: "bandpass", low_hz, high_hz}`) so that a
  `{kind: "wavelet", level}` entry can be added. **Read `Z`'s report to see what it actually built** before
  you design against it. If it did not type the entry, stop and say so rather than reshaping `Z`'s work.

## What to build

1. **`preprocessing.wavelet_bands`, Signal → Signal** (`Adapters/preprocessing_wavelet_bands.py`).
   - **The transform:** a **stationary (undecimated) wavelet transform**, `pywt.swt` / `iswt`, so every layer
     stays sample-aligned with the recording. A detection on a layer is then at the right time on the raw
     trace.
   - **Padding:** pad to the length `swt` needs and trim back, and say so in `meta`.
   - **Parameters:** `wavelet` (default `db4`; offer a short list), `levels` (default chosen from the span
     length and `fs`), and **`level` — which layer goes on down the chain** (the researcher's answer: the
     decomposition yields several signals, and the user chooses which one feeds the next block). The
     residual approximation is selectable as its own entry.
   - **What `meta` carries:** every layer's frequency range in Hz, computed from `fs` and the level, so a
     layer can be read as "about 0.03–0.06 Hz", not only as "level 4".
2. **Its view shows every layer, not just the chosen one.** The output type is Signal, so per
   `BLOCK_INTEGRATION.md` §2 it is a `signal → signal` view.
   - Draw each layer stacked on the source's time axis, with the chosen one highlighted and its Hz range
     printed.
   - `tests/test_block_standard.py` must stay green: no block may resolve to a generic view.
   - If the stacked-layers drawing needs a modifier the standard lacks, add it the way §2 says to add one.
     Do not hand-roll a view outside the registry.
3. **A wavelet kind in the band scope.** `materialize_target` prepends a `preprocessing.wavelet_bands` step
   for a `{kind: "wavelet", wavelet, level}` target, exactly as it prepends a bandpass for a bandpass target.
   - On *Apply template*, the band picker offers *wavelet levels* beside the named bandpass bands. Each
     chosen level becomes one Discovery run across the channels in scope, with its paired surrogate, exactly
     as `Z` does for a band.
   - The run's label carries the level and its Hz range.
4. **Compare's union** (from `Z`) takes wavelet-level runs as members of side B the same way it takes band
   runs. Check this works; do not re-build it.

## Leave alone

| Leave alone | Why |
|---|---|
| `preprocessing.bandpass` and the named band list | `Z`'s; tested |
| The Dehshibi blocks and `detection.wavelet_scattering` | not this question; kymatio is a dependency problem, not yours |
| Fan-out inside a chain | Q-B-CHAIN is out of scope (2026-10-03); a scope is not a fork |
| The cross-channel rule | `W`, beside you |

## Running in parallel (2026-10-03)

**Wave 5: you run beside `W`** (`W-cross-channel-onto-edges.md`), another agent in the same checkout. The README's
**"Running two prompts at once"** rules apply in full:
- **Your own build:** use your own port and a private client build served with `run_server.py --dist`. Use
  `npx vite build --outDir <yours>` while working, and `npm run build` only for the gate.
- **Tests:** `pytest -n 4`, never `-n auto`. Announce in your report when you took the machine for smoke.
- **Shared files** are append-only and committed immediately, with your own hunks only (`git add -p`).
- If you need a file `W` owns, stop and write to `requests/` rather than editing it.

| | files |
|---|---|
| **yours** | `Adapters/preprocessing_wavelet_bands.py` (new), the wavelet kind in `Working/run_groups.py` / `Working/recipes.py`, the band picker on *Apply template* |
| **`W`'s — do not edit** | `Working/cross_channel.py`, `Working/library/matching.py`, `webui/server/explore_routes.py`, `webui/client/src/explore/CrossChannelPage.tsx`, Library › Recurrence |
| **shared** | `webui/client/src/api.ts`, `webui/smoke.py`, Settings (`W` adds three cross-channel keys; if you need one, request it) |

**Talking to the researcher:** any question you put to them opens with a plain-language explanation, then the
options, then your recommendation (`CLAUDE.md`). **Before you report, update**
`docs/prompts/rq_roundA/RQ4-bands-and-symbols.md` per that folder's README.

## Acceptance (check these in a browser)

1. **Analyse › Chain, the layers view:**
   - ⤓ Import `symbol_search` → `+ insert` *Wavelet bands* above 01.
   - Run on an Explore span. The block page shows every layer stacked on one time axis, the chosen one
     highlighted, each with its Hz range.
   - Change `level` and re-run: the next block's input changes, and nothing upstream re-computes (step cache).
2. **Alignment:** a drop visible on the raw trace sits at the same time on the layers that carry it. Smoke
   measures this the way `G`'s `feature_in_band` does.
3. **Discovery, the band scope:**
   - *Apply template* with two wavelet levels and one bandpass band over 3 channels. The result is three runs,
     each with its surrogate and its label.
   - Compare raw vs the union of the three, then *Send only-B unjudged to Review*.

## The gate

1. `npx tsc -b` + `npm run build` (own `--outDir` and `--dist`).
2. `webui/smoke.py` on a fresh `--sandbox` bridge, finishing on the **full** walk.
3. `pytest -n 4` against the README baseline (compare failure sets).
4. In particular: `tests/test_block_standard.py`, `tests/test_import_boundaries.py`, and a new test that
   `iswt` of the full decomposition reconstructs the input.

Evidence into `webui/screenshots/fixup/AC/`.

## Report

Write `docs/prompts/fixup/reports/AC-wavelet-bands.md`. Open with a plain-language summary. Then cover:
- what a layer looks like on one real span;
- the Hz range per level at 1 Hz and at 10 Hz;
- the three-run Discovery result and its Compare union;
- items left;
- out-of-scope files touched;
- the gate.
