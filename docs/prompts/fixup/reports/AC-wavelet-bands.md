# Report — Fixup AC: a wavelet decomposition is a band source for RQ4

Run 2026-10-04 on `main`, in the main checkout, **beside `W`** (wave 5). Commit prefix `fixup-ac:`. The first commit,
`3d13730`, touches only `tests/` and failed: the adapter test module could not import (no
`Adapters/preprocessing_wavelet_bands.py`), and 18 more failed in the core and the serializer (no `wavelet` band kind,
no `resolve_band` / `wavelet_levels`, no `layers` on a signal payload). The five route tests were red under
`webui/.venv` for the same reasons. Every bridge ran in `--sandbox` on a private port (**8775**) and a private client
build (`run_server.py --dist <scratchpad>/dist`). Nothing wrote to the real `DATA/db/annotations.sqlite`. Shared files
(`api.ts`, `smoke.py`) were committed on their own, path-scoped, with only my hunks.

**In plain words, first.** A bandpass filter is like a sieve with two mesh sizes you choose: it keeps the rhythms
between them and throws the rest away. A wavelet decomposition is a stack of sieves, each catching rhythms about half
as fast as the one above. It splits a recording into a ladder of layers (fast wiggles, slower swells, slower still)
that add back up to the original exactly. Its advantage is that a sharp event stays sharp and **stays where it
happened**: we use the *stationary* version, which never thins the samples out, so a drop on the raw trace is at the
same second on every layer that carries it. Now any one layer can be fed into the symbolic chain exactly like a
bandpassed signal. In Discovery, a wavelet level is just another band: tick "level 4" beside "0.01–0.1 Hz" and each
becomes one run across the channels, with its own null and a label that says its frequency range.

On the sandbox, one bandpass band and two wavelet levels found 75, 46 and 35 regions on the 3-channel scope. Their
nulls expected 248, 125 and 123: **on these recordings and this chain, chance still out-finds every layer, wavelet
ones included.** The tool now asks RQ4 with wavelets as well as bandpasses; the answer so far is the same as `Z` found.

---

## 1. What was built

| # | The prompt asked | Now |
|---|---|---|
| 1 | `preprocessing.wavelet_bands`, Signal → Signal, stationary transform | `Adapters/preprocessing_wavelet_bands.py`. Each layer is `pywt.swt`'s projection onto one octave (`iswt` of that level's coefficients alone, the `pywt.mra(transform="swt")` construction), so the layers are sample-aligned and **add up to the input** (largest difference 6.1 × 10⁻¹⁶ on the example span). Padding: mirror reflection, split across both ends, to the next multiple of 2^levels, every layer trimmed back; `meta.padding` + `padding_note` say so (7,200 → 7,680 samples on the example span). `meta.boundary_note` says the transform treats the span as periodic, so the deepest layers carry an edge effect |
| 1 | Parameters | `wavelet` (default `db4`; db4 · db2 · db8 · sym4 · sym8 · coif2 · haar), `levels` (default **0 = auto**: the first depth whose slowest detail reaches 0.001 Hz, the lower edge of the slowest seeded band; never shallower than `level`; never deeper than the span lets the filter fit, `pywt.dwt_max_level`), **`level`**: which layer goes on (1 = fastest; **0 = the residual approximation**, its own entry). A level deeper than the span allows is refused by name |
| 1 | `meta` carries every layer's Hz range | `meta.layers`: name (`D1`…`Dn`, `An`), level, kind, `low_hz` / `high_hz`, label (`"D4 · 0.031–0.062 Hz"`), chosen, RMS, and a min/max **envelope** (span-relative sample indices, ≤ 2,400 points, rule 2: never a stride) |
| 2 | Its view shows every layer | Under the before/after overlay, **Every layer**: the input first (grey), then each layer fastest first, on the page's own time axis. Each row is its own rule-9 plot on a y measured from its own trace, with a scale bar (rule 4). The chosen row is highlighted and labelled *"goes on down the chain"*. One hover line runs through every row. A one-line note gives wavelet · depth (auto or not) · the chosen layer · padding · the sum check · resolution; the rest is behind the info icon. **No new modifier**: the conversion is `signal->signal`, so this is a *payload convention* (`payload.layers`), added to `BLOCK_INTEGRATION.md` §2's table, never selected by the block's name. `test_block_standard.py` stays green |
| 3 | A wavelet kind in the band scope | `recipes.BAND_KINDS = ("bandpass", "wavelet")`; a wavelet band is `{kind, wavelet, level}`. `run_groups._BAND_STEPS["wavelet"]` builds **the block as Analyse inserts it** (adapter defaults filled, `levels` 0, wavelet and level set), so `materialize_target` prepends it exactly as it prepends a bandpass, and a wavelet band run **hashes the same as the hand-built twin** (pinned in the core, and executed end to end). The surrogate goes ahead of it. `run_groups.resolve_band(band, fs, n)` gives a level its Hz range and a label carrying it (`"db4 level 4 · 0.031–0.062 Hz"`); `wavelet_levels(fs, n)` is what a scope can offer |
| 3 | The band picker on *Apply template* | Below the named bands: **Wavelet levels**, with a wavelet dropdown. Every level the auto depth reaches over the section in scope at the recording's rate, then the residual, each with its Hz range. All start unticked, so Z's "named bands start ticked" default is unchanged. `GET /api/discovery/bands` carries them (`?wavelet=`); `/plan` and `/templates/apply` resolve each band against the section and refuse a too-deep level (422, naming it) before any run is written |
| 4 | Compare's union takes wavelet-level runs | Checked, not rebuilt: a route test and the sandbox walk (§4) put two wavelet runs and a bandpass run in one set; the union, the per-band rows and the verdict split read them like any band |

## 2. What a layer looks like on one real span

The example span: M2_aug CH1_A1, 336–338 h, 7,200 samples at 1 Hz. `symbol_search` imported, *Wavelet bands*
inserted above 01, run (`webui/screenshots/fixup/AC/analyse-3-block-every-layer.png`):

- auto depth **9 levels** (D9 bottoms out at 0.00098 Hz); padded 7,200 → 7,680 and trimmed back;
- **D1–D3** are the fast wiggle plus a burst at each sharp fall;
- **D4 (0.031–0.062 Hz, the default that goes on)** holds the falls as isolated bursts. Its range on this span is
  −0.68 … +0.91 mV, against an input range of −461.7 … −434.0 mV, so it is the drops with the offset and the slow
  recovery taken out;
- **D5–D7** show each drop as one broad dip; **D8, D9** are the slow swells; the residual **A9** is the baseline;
- the drop at **336.815–336.866 h** (a 183 s fall) is drawn inside the fall on D1–D7: their deepest points sit
  between 655 s and 709 s past 336.5 h, later as the level rises, because a fast layer marks the steepest part of
  the fall and a slower one its body.

**Changing `level` 4 → 6 and re-running** (`analyse-4-level-6-rerun.png`): the recipe's step 01 records `level 6`;
the next block's input (Baseline removal) changes from −0.68 … 0.91 mV to −2.26 … 2.54 mV, and the highlighted row
moves to D6. Upstream of the block is only the source, which is not a step. The wavelet step itself takes 0.05–0.09 s
here, under the step cache's 1 s write threshold, so it is recomputed rather than read back. On a long span, where it
is cached, its layers come back through the bridge's meta sidecar: each envelope is under the sidecar's 4,096-value
cap, pinned by `test_the_layers_survive_the_meta_sidecar_of_a_step_cache_hit` (200,000 samples, 9 layers).

**Alignment, measured.** Smoke's new `layers_aligned` check reads the DOM the way `G`'s `feature_in_band` does. The
drop is the fall on the input row, from onset to trough. The layers that carry it are the detail layers fine enough
to resolve it (octave time scale ≤ the fall) in which it is prominent. Each must have its deepest vertex inside the
fall, give or take its own time scale. On the example span all seven carriers (D1–D7) pass. **With the layer rows
shifted by 240 samples in the DOM (this span's padding, i.e. the bug the check exists for), all seven fail**
(`layers-aligned-mutation.json`).

A first version of the check used the raw trace's single lowest point and failed on D9, whose trough sat 1,638 s
later. That is not misalignment: D9's octave is 8–17 minutes long, far too slow to place a 3-minute fall, and the fast
layers mark the *steepest* part of a fall, 44–64 s before its bottom. The check now uses the fall and only the layers
that can resolve it. The core test (`test_a_drop_on_the_raw_trace_sits_at_the_same_sample_on_the_layers_that_carry_it`)
pins the same thing to the sample on a synthetic dip.

## 3. The Hz range per level

Nominal octave edges: detail level *j* is fs/2^(j+1) – fs/2^j, and the residual is everything below the deepest
detail. A real wavelet filter's response overlaps its neighbours a little, and the page says so.

| layer | at 1 Hz (4 h span: 9 levels auto, the span allows 11) | at 10 Hz (4 h span: 13 levels auto, the span allows 14) |
|---|---|---|
| D1 | 0.25–0.5 Hz | 2.5–5 Hz |
| D2 | 0.12–0.25 | 1.2–2.5 |
| D3 | 0.062–0.12 | 0.62–1.2 |
| D4 | **0.031–0.062** (the default) | 0.31–0.62 |
| D5 | 0.016–0.031 | 0.16–0.31 |
| D6 | 0.0078–0.016 | 0.078–0.16 |
| D7 | 0.0039–0.0078 | 0.039–0.078 |
| D8 | 0.002–0.0039 | 0.02–0.039 |
| D9 | 0.00098–0.002 | 0.0098–0.02 |
| D10 – D13 | — | 0.0049–0.0098 · 0.0024–0.0049 · 0.0012–0.0024 · 0.00061–0.0012 |
| residual | below 0.00098 (A9) | below 0.00061 (A13) |

The default `level 4` is a different frequency at each rate (0.031–0.062 Hz at 1 Hz, 0.31–0.62 Hz at 10 Hz). The band
picker always prints the range for the recording in scope, and the block page prints it on every row. A template
saved with `level 4` from a 1 Hz recording and applied to a 10 Hz one would pick a layer ten times faster.

## 4. The three-run Discovery result and its Compare union

Sandbox, the scope `Z` used (M2_aug 452–456 h × CH2_A1 · CH6_B1 · CH7_B2), Settings › Nulls default (20 draws per
template run). Walked through the page (`webui/screenshots/fixup/AC/discovery-*.png`, `discovery-walk.json`):
*Apply template* · `symbol_search` · Bands: **0.01–0.1 Hz**, wavelet **level 4**, wavelet **level 6** → footer *"× 3
bands × 3 channels"* → *Add and run* → toast *"3 runs added · 3 bands × 1 template · 3 running locally"*, 33 s.

| run (label) | found | channels | null expects (20 draws per channel) |
|---|---|---|---|
| `symbol_search · 0.01–0.1 Hz` | 75 | 3 / 3 | 247.75 |
| `symbol_search · db4 level 4 · 0.031–0.062 Hz` | 46 | 3 / 3 | 125.25 |
| `symbol_search · db4 level 6 · 0.0078–0.016 Hz` | 35 | 3 / 3 | 123.35 |
| **union** (`set:symbol_search_bands`) | **123 regions** | | **496.35** |

Each wavelet run's first step is `preprocessing.wavelet_bands {wavelet db4, levels 0, level 4|6}`; each null is
`[surrogate, wavelet_bands, …]`. Compare A = `drop_detection_v1` (the raw-signal detector) vs B = the set: **only A 3
· both 0 · only B 123**. Per band, alone in the union: 44 · 27 · 20. *What differs* reads 3 of 5 roles (not
attributable), and the like-for-like note asks for `symbol_search` with no band. The sentence: *"Of the 123 regions
only a band found, a human has judged 0 and accepted 0. The bands' nulls expect 496.35 on this scope (20 draws per
channel per band)."* ***Send only-B unjudged to Review*** → *"123 unjudged of 123 regions in 'Compare · only B · A
drop_detection_v1 vs B symbol_search · 3 bands'"* → *Open Review* → `#/review/queue/3/1212`, *0 / 123*. I wrote no
verdicts. These are the researcher's to make, and the split above is what they will move.

The 0.01–0.1 Hz band found 75, the same as `Z`'s run on this scope, now that `sax_dsax` is seeded. Its null at 20
draws expects 247.75, against 249 at Z's single draw: the first 20-draw re-measure of one part of Z's 297. RQ4's file
records it.

## 5. Items left

| Item | Why it is not done here |
|---|---|
| **The null out-finds every layer** (§4) | A research finding, not a defect: `symbol_search` at untuned defaults fires more often on phase-randomised data than on the recordings, bandpass or wavelet. RQ4's file says so |
| A wavelet run routed to the cluster comes back with no null; the SLURM modal writes one script for N pending band runs | Pre-existing for every band kind (RQ4 *What is still needed*); the `/slurm` writer is not this prompt's |
| `level` means a different frequency at a different rate (§3) | Kept as a level, as Q-W3 decided ("the user picks which level goes on"); the Hz is printed everywhere it is chosen |
| The Compare set side's note *"the 3 band runs differ from each other only in the band"* | Still true with mixed kinds (the band step is the only difference), but the role cells are drawn from the first band's chain, so a set that mixes a bandpass and a wavelet level shows the bandpass's chain. Left as `Z` built it |
| Hz labels round to two significant figures (0.125 prints as 0.12) | They are nominal edges and say so; the exact `low_hz` / `high_hz` ride on the band and the layer |

## 6. Files touched outside the prompt's named list

| File | Why |
|---|---|
| `Working/recipes.py` | named ("the wavelet kind in … `Working/recipes.py`"): `BAND_KINDS`, `_normalize_wavelet_band`, and `WAVELET_BAND_WAVELETS`, the block's list restated so the recipe layer imports no adapter (a test holds the two equal) |
| `webui/server/serialize.py` | the one seam a payload goes through: `_signal_layers` ships the layers on absolute seconds in the display unit |
| `webui/server/discovery.py` | the band picker's route offers the levels; `/plan` and `/templates/apply` resolve a band against the section |
| `webui/client/src/analyse/views/SignalView.tsx`, `views/registry.tsx` | the layers view in the `signal->signal` composition (no new modifier, no view selected by name) |
| `webui/client/src/analyse/glyphs.tsx` | the block's glyph (checklist step 4) |
| `webui/client/src/api/discovery.ts`, `webui/client/src/api.ts` (shared) | `getBandsFor`; the payload and band types, appended by declaration merging. Two existing lines changed: `DiscBand.kind` widened to `'bandpass' \| 'wavelet'`, `getDiscoveryBands` takes an optional wavelet |
| `webui/smoke.py` (shared), `webui/smoke_pages/zz_analyse_run_ac.json` (new) | `layers_aligned`, three page states |
| `docs/BLOCK_INTEGRATION.md` | the payload convention's row in §2 |
| `tests/test_band_scope.py` (Z's) | **a deliberate behaviour change**: `test_an_unknown_band_kind_is_refused_by_name` used `wavelet` as its unknown kind; it now refuses `notch` and checks the message lists both kinds. Stated in `3d13730` |
| `tests/test_webui_serialize.py`, `tests/test_webui_discovery.py` | appended tests |
| `docs/rq_roundA/RQ4-bands-and-symbols.md` | the RQ rule |

Nothing of `W`'s was edited.

## 7. The gate

| Step | Result |
|---|---|
| `npx tsc -b`, `npm run build` in `webui/client` | **clean** on HEAD with `W`'s client work in it; every walk served a private build (`npx vite build --outDir <scratchpad>/dist`) |
| `pytest -n 4` under conda, **baseline** before my first edit | 2134 passed, 21 skipped, **27 failed, all in `tests/test_cross_channel_simultaneous.py`**: `W`'s red first commit (`3aebd08`), in flight beside me. My failure set outside `W`'s file was empty |
| `pytest -n 4` under conda, first gate run | 2210 passed, 22 skipped, **2 failed**: `test_adapter_spec.py::test_every_shipped_adapter_registers_without_modification` and `test_end_to_end.py::test_discover_adapters_registers_the_expected_count`, both pinning the shipped adapter count at 37. AC ships the 38th; the counts were updated in `4e6ec48` as a deliberate change |
| `pytest -n 4` under conda, **the gate** (HEAD, after `W` reported) | **2212 passed, 22 skipped, 0 failed** (5 m 34 s). Failure set empty |
| `webui/.venv`: `test_webui_discovery.py`, `test_webui_routes.py`, `test_webui_block_views.py`, `test_webui_serialize.py` | **107 passed, 1 failed**: the standing `test_the_scoreboard_cells_are_the_tables_own_numbers`. The five new wavelet route tests are green |
| `tests/test_block_standard.py`, `tests/test_import_boundaries.py` | **150 passed**. No block falls through to a generic view; the new block imports no UI library |
| New: `iswt` of the full decomposition reconstructs the input | `test_adapter_wavelet_bands.py::test_iswt_of_the_full_decomposition_reconstructs_the_input` (to 1e-8), plus the layers adding up to the input |
| `webui/smoke.py`, **full**, on a fresh `--sandbox` bridge (port 8775), **alone on the machine** (19:28–19:51, after `W`'s own walk ended) | **627 screenshots, 7 failures, 0 browser console/page errors, 0 unexpected server tracebacks.** The 7: the five standing (`discovery.runs--default` and the four Settings registration states) and the **two screenshot-path errors `V` also recorded**: two Review state names contain `+/-`, and the `/` becomes a directory in the screenshot path (`[Errno 2]`); both states rendered. Every AC state passed (`zz_analyse_run_ac`: the chain with the block inserted above 01; the block page with every layer stacked, rule 9 on 12 traces, `layers_aligned` on D1–D7; the band picker's wavelet levels). `Z`'s band walk passed with the wavelet section present (it still ticks exactly the 3 named bands) |

Logs: `webui/screenshots/fixup/AC/smoke-logs/` (`smoke-gate.txt`, `smoke-result-ac.json`, `pytest-baseline.txt`,
`pytest-gate.txt`); the AC page states in `states/`; the flow screenshots `analyse-*` and `discovery-*`.

**I took the machine** for the baseline `pytest -n 4` (at the start of the session), both gate
`pytest -n 4` runs and the full smoke walk. Each started only after a check that no other `pytest` or `smoke.py` was
running. I waited out `W`'s suite and its full walk.

## 8. In short

The wavelet decomposition is a band source for RQ4. One block splits a span into octave layers that stay in step with
the recording and add back up to it. Its page draws every layer with its frequency range, and a drop is measured at
the same time on the layers that carry it. In Discovery a wavelet level is ticked beside the named bands and becomes
one run with its own null, labelled with its range, and Compare's union takes it like any band. On the sandbox scope
two levels and one bandpass band found 123 regions the raw detector did not. Their nulls expected about four times as
many, so RQ4 can now be asked with wavelets, and on these defaults the answer is still "not above chance".
