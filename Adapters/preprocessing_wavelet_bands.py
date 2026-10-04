"""
preprocessing_wavelet_bands.py
================================
`preprocessing.wavelet_bands` — split the span into octave layers with a
**stationary (undecimated) wavelet transform** and pass ONE layer on down the
chain as an ordinary Signal (fixup-AC, Q-W3, RQ4).

In plain words: a bandpass cuts the signal at two frequencies you choose; this
splits it into a ladder of layers, each about half the speed of the one above,
and is better at keeping a sharp event sharp while doing it. Each layer is turned
back into a signal, so detrend, symbolic encoding and symbol search read a layer
exactly as they read a bandpassed signal.

* **Stationary, so sample-aligned.** `pywt.swt` downsamples nothing: every layer
  has one value per sample of the span, so a detection on a layer is at the right
  time on the raw trace. Each layer is the transform's projection onto one
  octave (`pywt.mra(..., transform="swt")`: the inverse transform of that level's
  coefficients alone), so the layers ADD UP to the input — nothing is lost and
  nothing is invented — and the projection is aligned whatever the wavelet's
  symmetry.
* **Layers.** `D1` is the fastest octave (fs/4 – fs/2, up to Nyquist), `Dj`
  covers fs/2^(j+1) – fs/2^j, and `A<levels>` (the *residual approximation*) is
  everything slower than the deepest detail. The edges are the nominal octave
  edges; a real wavelet filter's response overlaps its neighbours a little.
* **`level`** chooses the layer that goes on: 1 … `levels` a detail, **0 the
  residual**. **`levels`** is how deep to decompose; 0 (the default) chooses it
  from the span and `fs`: deep enough that the slowest detail reaches the slowest
  named band's lower edge (`FLOOR_HZ`, 0.001 Hz — Settings › Analysis defaults'
  seeded list), never shallower than `level`, never deeper than the span lets the
  filter fit (`pywt.dwt_max_level`). A detail level's content does not depend on
  how much deeper the decomposition goes, so a band run and a hand-built chain
  that both leave `levels` at auto read the same layer.
* **Padding.** `swt` needs a length divisible by 2^levels. The span is padded by
  mirror reflection (`np.pad(mode="symmetric")`), split across both ends, to the
  next such length, and every layer is trimmed back to the span. `swt` treats the
  padded signal as periodic, so the first and last few filter-lengths of the
  deepest layers carry an edge effect; `meta` says both.

**What `meta` carries** — the page draws every layer, not just the one that went
on: `layers` (each layer's name, level, Hz range, label, whether it is the chosen
one, its RMS, and a **min/max envelope** of span-relative sample indices —
rule 2, never a stride, ≤ 2 × `ENVELOPE_BUCKETS` points so it survives the
bridge's meta sidecar on a step-cache hit), `padding`, `levels`, `levels_auto`,
`level`, `layer`, `wavelet`, and the reconstruction error of the whole set.

Why not reuse `preprocessing.wavelet_transform`: that is a continuous Morse
scalogram (Signal → Encoding) for Dehshibi's detector, an image with no inverse
the chain can read on. `preprocessing.bandpass` is the other band source; this is
the wavelet one. Both are `Z`'s band scope's step builders
(`Working.run_groups._BAND_STEPS`).
"""

import math

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import Signal

#: The short list the block offers. Orthogonal discrete wavelets with an SWT;
#: db4 is the default (a compact, moderately smooth filter, 8 taps).
WAVELETS = ["db4", "db2", "db8", "sym4", "sym8", "coif2", "haar"]

#: The slowest named band's lower edge (Settings › Analysis defaults' seeded
#: list, Q43). Auto levels decompose until the slowest detail reaches it.
FLOOR_HZ = 0.001

#: Buckets per layer envelope: each contributes its min and max, so at most
#: 2 × this many points — under the 4096-value cap of the bridge's meta sidecar.
ENVELOPE_BUCKETS = 1200


def _wavelet(name):
    import pywt

    return pywt.Wavelet(name)


def max_levels(n, wavelet="db4"):
    """The deepest level the span lets the filter fit (`pywt.dwt_max_level`)."""
    import pywt

    return int(pywt.dwt_max_level(int(n), _wavelet(wavelet).dec_len))


def auto_levels(n, fs, wavelet="db4", level=0):
    """How deep to decompose when `levels` is 0: the first level whose slowest
    detail reaches `FLOOR_HZ`, at least `level`, at most what the span allows."""
    reach = max(1, int(math.ceil(math.log2(float(fs) / FLOOR_HZ))) - 1)
    return max(1, min(max(reach, int(level)), max_levels(n, wavelet)))


def layer_range_hz(fs, level, levels):
    """A layer's nominal frequency range in Hz: detail `level` (≥ 1) is one
    octave, fs/2^(level+1) – fs/2^level; level 0 is the residual approximation,
    0 – fs/2^(levels+1)."""
    fs = float(fs)
    if int(level) == 0:
        return (0.0, fs / 2 ** (int(levels) + 1))
    return (fs / 2 ** (int(level) + 1), fs / 2 ** int(level))


def _hz(v):
    return f"{v:.2g}"


def range_words(fs, level, levels):
    """'0.031–0.062 Hz' for a detail, 'below 0.00098 Hz' for the residual."""
    lo, hi = layer_range_hz(fs, level, levels)
    return f"below {_hz(hi)} Hz" if int(level) == 0 else f"{_hz(lo)}–{_hz(hi)} Hz"


def layer_name(level, levels):
    return f"A{int(levels)}" if int(level) == 0 else f"D{int(level)}"


def _padding(n, levels):
    block = 2 ** int(levels)
    total = (-int(n)) % block
    left = total // 2
    return {"n": int(n), "padded_to": int(n) + total, "left": int(left), "right": int(total - left),
            "mode": "symmetric"}


def swt_coeffs(x, wavelet, levels):
    """The stationary transform of `x`, padded to the length it needs.

    Returns ``(coeffs, pad)``: `coeffs` as `pywt.swt(..., norm=True,
    trim_approx=True)` gives them (``[cA_levels, cD_levels, …, cD_1]``, each the
    PADDED length), and `pad` = ``{n, padded_to, left, right, mode}``.
    `pywt.iswt(coeffs, wavelet, norm=True)[left:left + n]` is `x` again.
    """
    import pywt

    x = np.asarray(x, dtype=float)
    pad = _padding(len(x), levels)
    xp = np.pad(x, (pad["left"], pad["right"]), mode="symmetric") if pad["padded_to"] != pad["n"] else x
    coeffs = pywt.swt(xp, wavelet, level=int(levels), norm=True, trim_approx=True)
    return coeffs, pad


def decompose(x, wavelet, levels):
    """Every layer of `x`, each trimmed back to the span: ``{"layers": [{name,
    level, kind, x}, …], "pad": {…}}``, ordered D1 (fastest) … D<levels>, then
    the residual A<levels>. The layers add up to `x`."""
    import pywt

    coeffs, pad = swt_coeffs(x, wavelet, levels)
    lo, n = pad["left"], pad["n"]
    zero = np.zeros_like(coeffs[0])
    parts = []
    for j in range(len(coeffs)):              # coeffs[0] is cA_levels, coeffs[k] is cD_(levels-k+1)
        only = [zero] * len(coeffs)
        only[j] = coeffs[j]
        parts.append(pywt.iswt(only, wavelet, norm=True)[lo:lo + n])
    levels = int(levels)
    layers = [{"name": f"D{lv}", "level": lv, "kind": "detail", "x": parts[levels - lv + 1]}
              for lv in range(1, levels + 1)]
    layers.append({"name": f"A{levels}", "level": 0, "kind": "residual", "x": parts[0]})
    return {"layers": layers, "pad": pad}


def envelope(v, buckets=ENVELOPE_BUCKETS):
    """A min/max envelope of `v` over span-relative sample indices: every sample
    when it fits in 2 × `buckets` points, else each bucket's min and max in the
    order they occur (rule 2 — a stride would delete a narrow event)."""
    v = np.asarray(v, dtype=float)
    n = len(v)
    if n <= 2 * buckets:
        return {"i": list(range(n)), "v": [float(a) for a in v], "n_source": n, "n_points": n, "decimated": False}
    edges = np.linspace(0, n, buckets + 1).astype(np.int64)
    starts = edges[:-1]
    lo = np.minimum.reduceat(v, starts)
    hi = np.maximum.reduceat(v, starts)
    counts = np.diff(edges)
    idx = np.arange(n, dtype=np.int64)
    i_lo = np.minimum.reduceat(np.where(v == np.repeat(lo, counts), idx, n), starts)
    i_hi = np.minimum.reduceat(np.where(v == np.repeat(hi, counts), idx, n), starts)
    first, second = np.minimum(i_lo, i_hi), np.maximum(i_lo, i_hi)
    order = np.empty(2 * buckets, dtype=np.int64)
    order[0::2], order[1::2] = first, second
    order = np.unique(order)                  # a bucket whose min and max are one sample contributes it once
    return {"i": order.tolist(), "v": v[order].astype(float).tolist(), "n_source": n,
            "n_points": int(len(order)), "decimated": True}


def _run(x, t, fs, wavelet="db4", levels=0, level=4):
    x = np.asarray(x, dtype=float)
    n = len(x)
    if not np.all(np.isfinite(x)):
        raise ValueError(
            f"preprocessing.wavelet_bands: the span holds {int((~np.isfinite(x)).sum())} NaN or infinite "
            "sample(s); a wavelet transform spreads one missing sample across every layer. Choose a span "
            "without gaps, or fill them upstream.")
    level, levels = int(level), int(levels)
    ceiling = max_levels(n, wavelet)
    auto = levels == 0
    if auto:
        levels = auto_levels(n, fs, wavelet, level)
    if level > ceiling:
        raise ValueError(
            f"preprocessing.wavelet_bands: level {level} is deeper than a {n}-sample span allows with {wavelet} "
            f"(at most level {ceiling}: the filter must fit the span). Choose a level of {ceiling} or less, "
            "or a longer span.")
    if level > levels:
        raise ValueError(
            f"preprocessing.wavelet_bands: level {level} is deeper than the {levels} levels asked for. "
            "Set levels to 0 (auto) or at least the level.")
    if levels > ceiling:
        raise ValueError(
            f"preprocessing.wavelet_bands: {levels} levels is deeper than a {n}-sample span allows with "
            f"{wavelet} (at most {ceiling}).")
    dec = decompose(x, wavelet, levels)
    chosen = layer_name(level, levels)
    out = None
    layers_meta = []
    for L in dec["layers"]:
        lo, hi = layer_range_hz(fs, L["level"], levels)
        if L["name"] == chosen:
            out = L["x"]
        layers_meta.append({
            "name": L["name"], "level": L["level"], "kind": L["kind"], "low_hz": lo, "high_hz": hi,
            "label": f"{L['name']} · {range_words(fs, L['level'], levels)}", "chosen": L["name"] == chosen,
            "rms": float(np.sqrt(np.mean(L["x"] ** 2))) if n else 0.0, "envelope": envelope(L["x"]),
        })
    total = np.sum([L["x"] for L in dec["layers"]], axis=0)
    pad = dec["pad"]
    meta = {
        "wavelet": wavelet, "levels": levels, "levels_auto": auto, "level": level, "layer": chosen,
        "layer_label": f"{chosen} · {range_words(fs, level, levels)}",
        "layers": layers_meta, "padding": pad,
        "padding_note": (f"padded {pad['n']} → {pad['padded_to']} samples by mirror reflection "
                         f"({pad['left']} before, {pad['right']} after) for the stationary transform, "
                         "then every layer trimmed back to the span"
                         if pad["padded_to"] != pad["n"] else
                         f"{pad['n']} samples is a multiple of 2^{levels}: no padding, nothing to trim"),
        "boundary_note": "the transform treats the span as periodic: the deepest layers carry an edge effect "
                         "over their first and last few filter lengths",
        "reconstruction_error": float(np.max(np.abs(total - x))) if n else 0.0,
        "edges_note": "nominal octave edges; a wavelet filter's response overlaps its neighbours a little",
    }
    return AdapterResult(output_kind="signal", value=Signal(x=out, fs=fs), meta=meta)


def _plot(x, t, result, wavelet="db4", levels=0, level=4):
    import matplotlib.pyplot as plt

    layers = result.meta["layers"]
    fig, axes = plt.subplots(len(layers) + 1, 1, figsize=(14, 1.4 * (len(layers) + 1)), sharex=True)
    axes[0].plot(t, x, linewidth=0.5, color="#999999")
    axes[0].set_ylabel("input", rotation=0, ha="right")
    for ax, L in zip(axes[1:], layers):
        idx = np.asarray(L["envelope"]["i"], dtype=int)
        ax.plot(np.asarray(t)[idx], L["envelope"]["v"], linewidth=0.6,
                color="mediumseagreen" if L["chosen"] else "#4c72b0")
        ax.set_ylabel(L["label"], rotation=0, ha="right", fontsize=8)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"Wavelet bands ({result.meta['wavelet']}, {result.meta['levels']} levels) — "
                 f"{result.meta['layer_label']} goes on")
    fig.tight_layout()
    return fig


SPEC = register(AdapterSpec(
    name="preprocessing.wavelet_bands",
    display_name="Wavelet bands (stationary wavelet transform)",
    stage="preprocessing",
    category="preprocess",
    page_name="Wavelet bands",
    params=[
        ParamSpec("wavelet", str, "db4", "The wavelet: db4 is a compact, moderately smooth default; haar is the "
                  "sharpest, sym8/db8/coif2 the smoothest.", choices=list(WAVELETS)),
        ParamSpec("levels", int, 0, "How many octave layers to split the span into. 0 = chosen from the span and "
                  f"the sample rate: deep enough to reach {FLOOR_HZ:g} Hz, as deep as the span allows.",
                  min=0, max=20),
        ParamSpec("level", int, 4, "Which layer goes on down the chain: 1 = the fastest octave (fs/4 to fs/2), "
                  "each next level half as fast; 0 = the residual approximation (everything slower than the "
                  "deepest layer). Every layer is drawn on the block page with its Hz range.", min=0, max=20),
    ],
    run=_run,
    input_kind="signal",
    output_kind="signal",
    plot=_plot,
    description=(
        "Stationary (undecimated) wavelet transform: splits the span into octave layers, each about half the "
        "speed of the one above, all sample-aligned with the recording and adding up to it. One layer — the "
        "`level` you choose — goes on down the chain as an ordinary signal; the block page draws every layer "
        "with its frequency range in Hz."
    ),
))
