"""
detection_dehshibi_spikes.py
==============================
The Dehshibi & Adamatzky (2021) spike detector as ONE block — deprecated in
favour of the `dehshibi_spikes` template (stage-3 decision 2), kept
registered so an old recipe still runs.

Since fixup-J it calls the same core as the template
(`Working.Detection.analysis.dehshibi_authors.detect_spikes`, the port of the
authors' MATLAB), so the two entry points cannot drift apart
(`tests/test_template_dehshibi.py`). Its spans are half-open, like every
other block's.

The parameters keep their old names and their old unit (samples):
`n_p` is the authors' `peakWidth`; `epsilon_factor` their `thr`.
`min_spike_duration` and `min_roi_wavelet` belonged to the printed
Algorithm 4 and have no counterpart in the authors' code — accepted, unused.
"""

from Adapters.base import AdapterSpec, AdapterResult, ParamSpec
from Adapters.registry import register
from Working.Detection.analysis.dehshibi_authors import detect_spikes
from Working.Detection.analysis.dehshibi_detection_analysis import plot_spike_detection
from Working.types import SpanSet
from Working.block_cost import estimate_seconds, register_cost_model

COST_MODEL = "detection.dehshibi_spikes"
# Morse CWT per window is FFT-bound, so seconds ~ n log n; a single calibrated
# constant with exponent 1.1 tracks it to within the noise on every span
# length that matters here.
register_cost_model(COST_MODEL, 1.1, lambda x, fs: detect_spikes(x, fs=fs))


def _estimate(x, t, fs, **params):
    """Seconds for this span from `Working.block_cost` — None until
    `Working.block_cost.calibrate()` has timed the detector on this machine
    (never a guessed number)."""
    return estimate_seconds(COST_MODEL, len(x))


def _run(x, t, fs, n_p=60, min_spike_duration=60, min_roi_wavelet=30, epsilon_factor=0.05):
    spikes, pseudo_spikes, info = detect_spikes(x, fs=fs, thr=epsilon_factor, peak_width_s=n_p / float(fs))
    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(
            starts=tuple(int(s) for s, _ in spikes),
            ends=tuple(int(e) + 1 for _, e in spikes),
        ),
        meta={"pseudo_spikes": [[int(s), int(e) + 1] for s, e in pseudo_spikes], "n_spikes": len(spikes),
              "n_pseudo_spikes": len(pseudo_spikes), "n_chunks": len(info["chunks"])},
    )


def _plot(x, t, result, n_p=60, min_spike_duration=60, min_roi_wavelet=30, epsilon_factor=0.05):
    # `plot_spike_detection` wants the legacy inclusive [(start, end), ...] shape
    spans = [(s, e - 1) for s, e in zip(result.value.starts, result.value.ends)]
    pseudo = [(s, e - 1) for s, e in result.meta["pseudo_spikes"]]
    return plot_spike_detection(x, spans, pseudo, fs=1.0)


SPEC = register(AdapterSpec(
    name="detection.dehshibi_spikes",
    display_name="Spike detection (Dehshibi & Adamatzky 2021)",
    stage="detection",
    category="control",            # deprecated: kept runnable for comparison, filed out of the detect tab
    page_name="Spike detection (Dehshibi, monolithic — deprecated)",
    params=[
        ParamSpec("n_p", int, 60, "Minimum extrema separation (samples)", min=1),
        ParamSpec("min_spike_duration", int, 60, "Not used since fixup-J (samples)", min=1),
        ParamSpec("min_roi_wavelet", int, 30, "Not used since fixup-J (samples)", min=1),
        ParamSpec("epsilon_factor", float, 0.05, "Candidate-region prominence threshold (fraction of range)", min=0.0, max=1.0),
    ],
    run=_run,
    estimate=_estimate,
    input_kind="signal",
    output_kind="spanset",
    plot=_plot,
    description=(
        "DEPRECATED (stage-3 decision 2): use the `dehshibi_spikes` TEMPLATE — "
        "Wavelet transform → Wavelet summation → Summation threshold — which "
        "reproduces this pipeline exactly (tests/test_template_dehshibi.py) with "
        "every intermediate visible. Kept registered so an old recipe still runs."
    ),
))
