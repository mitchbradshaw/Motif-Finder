"""
test_adapter_summation_threshold.py
=====================================
`detection.summation_threshold` — Scores → SpanSet: Algorithms 1–4 of
Dehshibi & Adamatzky (2021) over the summed wavelet coefficient Ω(τ) and
the signal itself (Algorithm 2's excursion test and the Sect. 3.3 envelope
need the raw signal, which every block receives as `x`).

Not `detection.threshold`: that block cuts a Scores at an absolute value,
this one finds prominence-gated extrema PAIRS of Ω per chunk and then
confirms them against the signal envelope — different semantics, so a
different block (the standard says when to reuse and when not).

Runnable standalone:  python tests/test_adapter_summation_threshold.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Detection.analysis.dehshibi_detection_analysis import detect_spikes  # noqa: E402
from Working.types import Scores  # noqa: E402

discover_adapters()
NAME = "detection.summation_threshold"
FS = 10.0
SMALL = {"n_p": 10, "min_spike_duration": 10, "min_roi_wavelet": 5}


def synthetic(seconds=30.0, seed=0, fs=FS):
    """Two broad depolarisations each with a sharp core — the shape Algorithm 4
    confirms (an envelope region nested inside a wavelet region). Noise-free
    on purpose: a grid search over shapes found the monolithic detector
    confirms exactly this and nothing simpler (wiring report 01)."""
    n = int(fs * seconds)
    t = np.arange(n) / fs
    x = np.zeros(n)
    for centre in (0.3 * seconds, 0.7 * seconds):
        x += np.exp(-0.5 * ((t - centre) / (0.2 * seconds)) ** 2) + 0.3 * np.exp(-0.5 * ((t - centre) / (0.005 * seconds)) ** 2)
    return x, t


def _omega(x):
    tr = get_adapter("preprocessing.wavelet_transform")
    enc = tr.run(x, None, FS, **tr.validate_params({"min_chunk_samples": 2 * SMALL["n_p"]})).value
    sm = get_adapter("detection.wavelet_summation")
    return sm.run(x, None, FS, value=enc, **sm.validate_params({})).value


def test_registered_with_the_standard_types_and_the_papers_params():
    spec = get_adapter(NAME)
    assert spec.input_kind == "scores" and spec.output_kind == "spanset"
    assert spec.category == "detect"
    names = {p.name for p in spec.params}
    assert {"epsilon_factor", "n_p", "min_spike_duration", "min_roi_wavelet"} <= names
    d = spec.validate_params({})
    assert d["n_p"] == 60 and d["min_spike_duration"] == 60 and d["min_roi_wavelet"] == 30 and d["epsilon_factor"] == 0.05


def test_reproduces_the_monolithic_detector_exactly():
    x, t = synthetic()
    spikes, pseudo, _ = detect_spikes(x, fs=FS, **SMALL)
    spec = get_adapter(NAME)
    r = spec.run(x, t, FS, value=_omega(x), **spec.validate_params(SMALL))
    assert r.output_kind == "spanset"
    assert list(zip(r.value.starts, r.value.ends)) == [(s, e) for s, e in spikes]
    assert r.meta["pseudo_spikes"] == [list(p) for p in pseudo] or r.meta["pseudo_spikes"] == list(pseudo)
    assert len(spikes) >= 1, "the synthetic signal must produce at least one spike for this test to mean anything"


def test_spans_are_labelled_spike_and_scored_by_depth():
    x, t = synthetic()
    spec = get_adapter(NAME)
    r = spec.run(x, t, FS, value=_omega(x), **spec.validate_params(SMALL))
    assert r.value.labels is not None and set(r.value.labels) == {"spike"}
    assert r.value.scores is not None and all(s is None or s >= 0 for s in r.value.scores)


def test_refuses_a_missing_scores_input():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="Scores"):
        spec.run(np.zeros(50), np.arange(50.0), 1.0, **spec.validate_params({}))


def test_all_nan_scores_yield_no_spans_not_an_error():
    spec = get_adapter(NAME)
    x = np.zeros(50)
    r = spec.run(x, np.arange(50.0), 1.0, value=Scores(values=np.full(50, np.nan), fs=1.0), **spec.validate_params({}))
    assert r.value.starts == ()


# ---------------------------------------- the end convention (fixup-a item 3) --
# `SpanSet` documents its regions as `[start, end)` and `detection.threshold`
# emits exactly that. This block emitted `end` INCLUSIVE, so the same event's
# duration differed by one sample depending on which block found it.

def test_span_ends_are_half_open_like_every_other_block():
    x, t = synthetic()
    spikes, _, _ = detect_spikes(x, fs=FS, **SMALL)
    assert spikes, "the fixture must confirm a spike for this test to mean anything"
    spec = get_adapter(NAME)
    r = spec.run(x, t, FS, value=_omega(x), **spec.validate_params(SMALL))
    assert list(r.value.starts) == [s for s, _ in spikes]
    assert list(r.value.ends) == [e + 1 for _, e in spikes], (
        "the core's Algorithm 4 returns inclusive pairs; the adapter must hand SpanSet the "
        "half-open form, since that is what SpanSet documents and what every consumer assumes")


def test_the_two_detection_blocks_agree_on_the_same_events_bounds():
    """A Scores marking exactly the samples the monolith called a spike must be
    read back by `detection.threshold` as the very same span the Dehshibi block
    reports. Two blocks, one event, one pair of numbers."""
    x, t = synthetic()
    spikes, _, _ = detect_spikes(x, fs=FS, **SMALL)
    assert spikes
    s_incl, e_incl = spikes[0]
    mask = np.zeros(len(x)); mask[s_incl:e_incl + 1] = 1.0
    th = get_adapter("detection.threshold")
    rt = th.run(x, t, FS, value=Scores(values=mask, fs=FS), **th.validate_params({"threshold": 0.5}))
    spec = get_adapter(NAME)
    rs = spec.run(x, t, FS, value=_omega(x), **spec.validate_params(SMALL))
    assert (rs.value.starts[0], rs.value.ends[0]) == (rt.value.starts[0], rt.value.ends[0]), (
        f"summation_threshold says {(rs.value.starts[0], rs.value.ends[0])}, "
        f"threshold says {(rt.value.starts[0], rt.value.ends[0])} for the same samples")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
