"""
test_adapter_drop_detection.py
================================
`detection.drop_detection` — Encoding (five-stage) → SpanSet, the block form
of `detect5.detect_drops5`. Given the letters the encoder emitted and the
detrended signal, it reproduces the monolithic detector event for event.

Runnable standalone:  python tests/test_adapter_drop_detection.py
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
from Working.Detection.drop_motifs.detect5 import Detect5Params, detect_drops5  # noqa: E402
from Working.types import Encoding  # noqa: E402

discover_adapters()
NAME = "detection.drop_detection"
FS = 10.0
WINDOW_S, SEG_S = 12.0, 0.5


def sharkfin(seconds=30.0, period=10.0, fs=FS, seed=0):
    n = int(seconds * fs)
    t = np.arange(n) / fs
    phase = (t % period) / period
    x = np.where(phase < 0.85, phase / 0.85, 1.0 - (phase - 0.85) / 0.15) * 0.01
    x += 0.00002 * np.random.default_rng(seed).standard_normal(n)
    return x, t


def _chain(x, t):
    d = get_adapter("preprocessing.detrend")
    xd = d.run(x, t, FS, **d.validate_params({"mode": "rolling_mean_nearest", "window_s": WINDOW_S})).value.x
    e = get_adapter("detection.stage_encoding")
    enc = e.run(xd, t, FS, **e.validate_params({"segment_seconds": SEG_S})).value
    return xd, enc


def test_registered_as_the_encoding_to_spanset_detector():
    spec = get_adapter(NAME)
    assert spec.input_kind == "encoding" and spec.output_kind == "spanset"
    assert spec.category == "detect"
    assert {p.name for p in spec.params} >= {"slope_sigma", "min_rise_frac", "min_fall_dominance", "morphology"}


def test_reproduces_detect_drops5_event_for_event():
    x, t = sharkfin()
    xd, enc = _chain(x, t)
    spec = get_adapter(NAME)
    r = spec.run(xd, t, FS, value=enc, **spec.validate_params({}))
    ref = detect_drops5(x, FS, Detect5Params(detrend_window_s=WINDOW_S, segment_seconds=SEG_S))
    assert len(ref.events) >= 2, "the sharkfin train must yield events for this test to mean anything"
    got = [(s, e) for s, e in zip(r.value.starts, r.value.ends)]
    assert got == [(e.window_start_idx, e.window_end_idx) for e in ref.events]
    assert [ev["onset_idx"] for ev in r.meta["events"]] == [e.onset_idx for e in ref.events]
    assert [ev["trough_idx"] for ev in r.meta["events"]] == [e.trough_idx for e in ref.events]
    assert r.meta["morphology"] == ref.morphology
    assert r.meta["counts"]["drops_confirmed"] == ref.counts["drops_confirmed"]
    assert r.value.scores == tuple(e.drop_depth_mv for e in ref.events)


def test_labels_carry_onset_trough_and_morphology():
    x, t = sharkfin()
    xd, enc = _chain(x, t)
    spec = get_adapter(NAME)
    r = spec.run(xd, t, FS, value=enc, **spec.validate_params({}))
    for lab, ev in zip(r.value.labels, r.meta["events"]):
        assert lab == f"onset={ev['onset_idx']};trough={ev['trough_idx']};{ev['morphology']}"   # t starts at 0 here
    t2 = t + 500.0                       # the same span 500 s into the channel: labels are channel-absolute
    r2 = spec.run(xd, t2, FS, value=enc, **spec.validate_params({}))
    assert r2.value.labels[0].startswith(f"onset={r.meta['events'][0]['onset_idx'] + 5000};")


def test_refuses_a_plain_sax_encoding_with_a_pointer_to_the_right_block():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="Five-stage encoding"):
        spec.run(np.zeros(100), np.arange(100.0), FS, value=Encoding(values=np.array([0, 7, 2]), kind="symbolic"))


def test_refuses_a_missing_input():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="Encoding"):
        spec.run(np.zeros(100), np.arange(100.0), FS, **spec.validate_params({}))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
