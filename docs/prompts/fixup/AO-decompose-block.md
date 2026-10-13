# Fixup AO — a Decompose block: baseline, noise and signal as layers, one of them going on

**Written 2026-10-13 from the researcher's list ("analysis blocks for separating a signal into baseline, noise, freq
components, then selecting which signal to continue with for the rest of analysis"). Not run yet.**

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `docs/BLOCK_INTEGRATION.md`, **`Adapters/preprocessing_wavelet_bands.py` from top to bottom — it is
the pattern**, `Adapters/preprocessing_detrend.py`, `Adapters/preprocessing_lowpass.py`, `Adapters/preprocessing_highpass.py`,
`Adapters/base.py`, `webui/client/src/analyse/views/SignalView.tsx` (`LayerRow`, `chosen`, how the wavelet layers are
drawn), `webui/client/src/analyse/ParamsPanel.tsx` and `webui/server/views.py`.

Commit prefix `fixup-ao:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only.**

## In plain words

A recording is three things added together: a slow wander (the baseline), fast fuzz (the noise), and whatever is
left — the events. Today the researcher removes the wander with one block and the fuzz with another and never sees
the pieces side by side. The ask is one block that splits the trace into those layers, draws all of them, and lets
the researcher say which one the rest of the chain should work on. The wavelet-bands block already does exactly this
for frequency layers: it computes every layer, draws every layer, and passes one on through a `level` parameter.
Build the same shape, not a new one.

## The constraint that shapes it

A block has **one** output kind (`AdapterSpec.output_kind`); a chain is a line, not a fork. So "select which signal
to continue with" is a **parameter on the block** (`pass_on`), and the page's job is to make setting it a click on
the layer. The frequency case is already covered by `preprocessing.wavelet_bands` (its `level` *is* the frequency
selector); do not duplicate it — link to it from the page.

## Work

1. `Adapters/preprocessing_decompose.py` — `preprocessing.decompose`, input `signal`, output `signal`:
   - `baseline`: a running median over `baseline_window_s` (default from Settings › Analysis defaults' detrend
     window if one exists; else 600 s), the same estimator `preprocessing_detrend` uses if it has one — reuse, do not
     write a second.
   - `noise`: the part above `noise_cut_hz` (default a quarter of Nyquist), the same filter `preprocessing_highpass`
     uses — reuse.
   - `signal` = x − baseline − noise. The three **add up to the input** exactly; a test pins it.
   - `pass_on ∈ {signal, baseline, noise}`, default `signal`. `meta.layers` in the wavelet block's exact shape
     (`name`, `label`, `kind`, `chosen`, an envelope per layer), so `SignalView` draws it with no new drawing code.
2. The page: the three rows, the chosen one highlighted (as the wavelet page), **click a row → `pass_on` changes**
   (ParamsPanel gets the value; a re-run of the suffix follows as any param change does).
3. A builtin template `baseline_noise_signal` is *not* needed; a line in the block picker's description is.
4. Settings › Blocks lists it with its plain-words line.

## Acceptance

- [ ] baseline + noise + signal == input to 1e-9 on random input and on an hour of M2 CH4.
- [ ] `pass_on=baseline` hands the baseline on; a detrend after it sees a flat line (test).
- [ ] The page draws three layers; the chosen one is highlighted; clicking another sets `pass_on` and re-runs the suffix.
- [ ] `pytest`, `tsc -b`, `npm run build`, smoke (walk: insert the block → click the noise layer → the next block's
      input is the noise) pass.

## Report

`docs/prompts/fixup/reports/AO-decompose-block.md`.
