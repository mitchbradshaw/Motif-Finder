# Fixup AK — the Spike detection block: say what it does, detect spikes rather than the gaps between them

**Written 2026-10-13 from the researcher's question ("spike detection block — what does it do? how come it isn't
great at pulling spikes out, what param do I tune"). Not run yet.**

You are in `C:\Users\mmebr\Documents\CNN` (Windows; Bash = Git Bash; python `"/c/ProgramData/anaconda3/python.exe"`).
Read `CLAUDE.md`, `docs/BLOCK_INTEGRATION.md`, `Adapters/detection_spike_v1.py`, `Working/Detection/analysis/spike_analysis.py`,
`Adapters/base.py` (`AdapterSpec`, `ParamSpec`), `Working/units.py` (`to_mv_factor`), `Adapters/detection_dehshibi_spikes.py`
(the other spike detector — do not merge them; this one is Adamatzky 2023, that one is Dehshibi), and
`webui/client/src/analyse/views/SpanSetView.tsx` (what the block's page draws).

Commit prefix `fixup-ak:`. Test-first; the first commit touches only `tests/` and must fail. **`--sandbox` only.**

## In plain words

The block takes each sample and compares it with the average of its neighbours; a sample that stands out from that
local average by more than a threshold is called a spike, and spikes closer together than a refractory gap are
thinned to one. That is a fine idea. Three things make it look useless on this data:

1. **It draws the wrong thing.** The block returns the stretches *between* spikes as its spans (the adapter header
   calls this a "policy"), so what the page shows as detections are the quiet gaps, not the spikes.
2. **It can only see one direction.** The test is `|x| − |mean| > δ`. On a channel whose baseline sits at, say,
   −1.5 V, a *downward* dip makes `|x|` bigger and passes; an *upward* spike makes it smaller and never passes — and
   on a positive baseline it is the other way round. Which direction it can see depends on the sign of the DC offset,
   not on the biology. Drops are the main event in this project.
3. **The threshold is in whatever unit the channel is stored in.** M2 is stored in volts, so the default δ = 0.01 is
   10 mV against events of 1–30 mV: it fires only on the biggest. A researcher thinking in mV cannot tune it.

Also: the neighbourhood average is a per-sample Python loop; over a 2.6 M-sample channel that is minutes for nothing.

## Decided (from the researcher's 2026-10-13 list; confirm nothing else)

- The block stays Adamatzky's test, named as such. Its *page* must explain it in the plain words above, and name the
  one knob to turn first (δ, in mV), then w (how local the baseline is), then d (how close two spikes may sit).

## Work

1. **Spans are spikes.** Emit one span per detected index: `[i − half, i + half]` with a `span_s` parameter
   (default the refractory gap `d`), clipped to the span. Keep `spike_indices` and `n_spikes` in `meta`. Grep the
   builtin templates and saved recipes for `spike_v1` and say in the report which ones change meaning.
2. **Polarity.** Replace `|x| − |a| > δ` with a signed deviation `x − a` and a `polarity` param: `both` (default:
   `|x − a| > δ`), `up`, `down`. The docstring's formula is then true again on any baseline.
3. **δ in millivolts.** Declare the param in mV and convert with the recording's declared unit from `ctx` (how
   `preprocessing_trace_shape` reads the dataset's floor); a recording with no declared unit refuses in words.
4. **Vectorise** the neighbourhood mean (cumulative sum or `np.convolve`); a test pins it equal to the loop.
5. **The page.** A plain-words InfoTip and a "what to tune" line; the SpanSet view marks each spike at its index.

## Acceptance

- [ ] A synthetic trace with a +2 V baseline and one 5 mV dip is detected under `both` and `down`, not under `up`; the
      same dip on a −2 V baseline gives the same answer.
- [ ] Spans sit on the spikes (each contains its index), not between them.
- [ ] δ = 5 (mV) on a volts-stored recording behaves as 0.005 in the stored unit; a recording with no unit refuses.
- [ ] The vectorised mean equals the loop's to 1e-9 on random input; 2.6 M samples run in under a second.
- [ ] `pytest`, `tsc -b`, `npm run build` and smoke pass; the block's page shows the explanation.

## Report

`docs/prompts/fixup/reports/AK-spike-detection-block.md`: what changed meaning, how many spikes the defaults now find
on M2 CH4 over one hour versus before, and the plain-language page text as shipped.
