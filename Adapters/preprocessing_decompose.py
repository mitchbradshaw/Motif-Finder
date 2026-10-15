"""
preprocessing_decompose.py
============================
`preprocessing.decompose` -- split the span into **baseline, noise and signal**,
draw all three, and pass ONE of them on down the chain (fixup-AO, the
researcher's 2026-10-13 list: "separate a signal into baseline, noise, ... then
select which signal to continue with").

In plain words: a recording is a slow wander, plus fast fuzz, plus whatever is
left -- the events. This block takes the three apart (they add back up to the
input exactly), shows them stacked on the block page, and sends the one you
choose (`pass_on`, or a click on its row) to the next block as an ordinary
signal.

A chain is a line, not a fork, so "which layer goes on" is a parameter, exactly
as the wavelet-bands block's `level` is. The core is
`Working.Preprocessing.decompose.decompose`, which reuses the core's running
median and the Detrend / Highpass blocks' own filters -- no new filter.

**What `meta` carries** -- the wavelet block's shape, so `SignalView` draws the
layers with its existing rows: `layers` (each layer's name, label, kind, whether
it is the chosen one, its RMS, and a min/max envelope over span-relative sample
indices, <= 2 x `ENVELOPE_BUCKETS` points), `layer`, `layer_label`,
`reconstruction_error`; plus `layer_param` ("pass_on") and each layer's
`param_value`, the value a click on that row writes into `layer_param`; and
`split`, this block's own description (estimator, window, cut, whether the cut
was automatic, the edge notes). The bridge ships `split` in place of the wavelet
block's `decomposition`.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.preprocessing_wavelet_bands import envelope
from Adapters.registry import register
from Working.Preprocessing.decompose import BASELINE_METHODS, decompose
from Working.types import Signal

#: the layers in drawing order: fastest first, as the wavelet block draws D1 first
ORDER = ("noise", "signal", "baseline")
PASS_ON = ("signal", "baseline", "noise")


def _hz(v):
    return f"{v:.2g}"


def _labels(split, fs):
    cut = split["noise_cut_hz"]
    win = split["baseline_window_s"]
    est = "running median" if split["baseline_method"] == "rolling_median" else "rolling mean"
    return {
        "noise": (f"noise · the fast fuzz above {_hz(cut)} Hz", cut, float(fs) / 2.0),
        "signal": (f"signal · what is left: the events, below {_hz(cut)} Hz and off the baseline", None, cut),
        "baseline": (f"baseline · the slow wander, a {est} over {win:g} s", None, None),
    }


def _run(x, t, fs, pass_on="signal", baseline_window_s=600.0, noise_cut_hz=0.0,
         baseline_method="rolling_median", order=4):
    x = np.asarray(x, dtype=float)
    try:
        parts = decompose(x, fs, baseline_window_s=baseline_window_s, noise_cut_hz=noise_cut_hz,
                          baseline_method=baseline_method, order=order)
    except ValueError as e:
        raise ValueError(f"preprocessing.{e}") from None
    n = len(x)
    split = {
        "method": "baseline_noise_signal", "pass_on": pass_on, "baseline_method": baseline_method,
        "baseline_window_s": float(baseline_window_s), "baseline_window_samples": parts["baseline_window_samples"],
        "noise_cut_hz": parts["noise_cut_hz"], "noise_cut_auto": parts["noise_cut_auto"], "order": int(order),
        "edge_note": ("the running window shrinks to what fits at the span's ends (edges held at the nearest "
                      "sample), and the zero-phase filter carries a short transient there: read the first and "
                      "last half-window with care"),
        "nonlinear_note": ("the baseline is a running median, not a filter: it has no exact frequency edge, and a "
                           "step in the level goes to the baseline once it lasts longer than half the window"
                           if baseline_method == "rolling_median" else
                           "the baseline is the Detrend block's centred rolling mean"),
    }
    labels = _labels(split, fs)
    layers = []
    for name in ORDER:
        v = parts[name]
        label, lo, hi = labels[name]
        layers.append({
            "name": name, "level": None, "kind": name, "label": label, "low_hz": lo, "high_hz": hi,
            "chosen": name == pass_on, "param_value": name,
            "rms": float(np.sqrt(np.mean(v ** 2))) if n else 0.0, "envelope": envelope(v),
        })
    total = parts["baseline"] + parts["noise"] + parts["signal"]
    err = float(np.max(np.abs(total - x))) if n else 0.0
    split["reconstruction_error"] = err
    meta = {
        "split": split, "layers": layers, "layer_param": "pass_on",
        "layer": pass_on, "layer_label": labels[pass_on][0], "reconstruction_error": err,
    }
    return AdapterResult(output_kind="signal", value=Signal(x=parts[pass_on], fs=fs), meta=meta)


def _plot(x, t, result, **params):
    import matplotlib.pyplot as plt

    layers = result.meta["layers"]
    fig, axes = plt.subplots(len(layers) + 1, 1, figsize=(14, 1.6 * (len(layers) + 1)), sharex=True)
    axes[0].plot(t, x, linewidth=0.5, color="#999999")
    axes[0].set_ylabel("input", rotation=0, ha="right")
    for ax, L in zip(axes[1:], layers):
        idx = np.asarray(L["envelope"]["i"], dtype=int)
        ax.plot(np.asarray(t)[idx], L["envelope"]["v"], linewidth=0.6,
                color="mediumseagreen" if L["chosen"] else "#4c72b0")
        ax.set_ylabel(L["name"], rotation=0, ha="right", fontsize=8)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(f"Decompose -- {result.meta['layer']} goes on")
    fig.tight_layout()
    return fig


SPEC = register(AdapterSpec(
    name="preprocessing.decompose",
    display_name="Decompose: baseline, noise and signal",
    stage="preprocessing",
    category="preprocess",
    page_name="Decompose",
    params=[
        ParamSpec("pass_on", str, "signal", "Which layer goes on down the chain: signal (the events, with the slow "
                  "wander and the fast fuzz taken off), baseline (the slow wander) or noise (the fast fuzz). "
                  "Click a layer on the block page to choose it.", choices=list(PASS_ON)),
        ParamSpec("baseline_window_s", float, 600.0, "The baseline's running window in seconds: anything slower "
                  "than about this goes to the baseline. Tune this first. 600 s is the Detrend block's default "
                  "(no Settings default exists for it).", min=1.0),
        ParamSpec("noise_cut_hz", float, 0.0, "Above this frequency (Hz) is noise. 0 = a quarter of the Nyquist "
                  "frequency (fs / 8: 0.125 Hz at 1 Hz sampling). Must be below fs / 2.", min=0.0),
        ParamSpec("baseline_method", str, "rolling_median", "How the baseline is estimated: rolling_median "
                  "(a drop or a spike does not pull it) or rolling_mean (the Detrend block's own estimator).",
                  choices=list(BASELINE_METHODS)),
        ParamSpec("order", int, 4, "The noise highpass's Butterworth order (the Highpass block's filter).",
                  min=1, max=10),
    ],
    run=_run,
    input_kind="signal",
    output_kind="signal",
    plot=_plot,
    description=(
        "Splits the trace into three layers that add up to it: the slow wander (baseline, a running median), "
        "the fast fuzz (noise, a highpass above the cut) and what is left (signal, where the events are). The "
        "block page draws all three; `pass_on` -- or a click on a layer -- chooses the one that goes on down the "
        "chain. Tune baseline_window_s first. For frequency layers (octaves) use Wavelet bands instead."
    ),
))
