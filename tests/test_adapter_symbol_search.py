"""
test_adapter_symbol_search.py
===============================
`detection.symbol_search` — symbolic Encoding → SpanSet by regular expression
(stage-3 D2).

Runnable standalone:  python tests/test_adapter_symbol_search.py
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
from Working.types import Encoding  # noqa: E402

discover_adapters()
NAME = "detection.symbol_search"


def enc(symbols):
    return Encoding(values=np.asarray(symbols), kind="symbolic")


def test_registered_as_an_encoding_to_spanset_detector():
    spec = get_adapter(NAME)
    assert spec.input_kind == "encoding" and spec.output_kind == "spanset"
    assert spec.category == "detect"


def test_matches_map_to_segments_with_the_shared_samples_per_symbol_rule():
    #        a b c c a a b c a   (0 down · 1 same · 2 up)
    syms = [0, 1, 2, 2, 0, 0, 1, 2, 0]
    x = np.zeros(9 * 10 + 3)          # 93 samples → 93 // 9 = 10 per symbol
    spec = get_adapter(NAME)
    r = spec.run(x, None, 1.0, value=enc(syms), **spec.validate_params({"pattern": "c+a+"}))
    assert list(zip(r.value.starts, r.value.ends)) == [(20, 60), (70, 90)]
    assert r.value.labels == ("ccaa", "ca")
    assert r.value.scores == (4.0, 2.0)
    assert r.meta["samples_per_symbol"] == 10


def test_custom_alphabet_spells_the_five_stage_letters():
    syms = [2, 3, 4, 0, 1, 2]        # S U u d D S
    spec = get_adapter(NAME)
    r = spec.run(np.zeros(60), None, 1.0, value=enc(syms), **spec.validate_params({"pattern": "[Uu]+[Dd]*d[Dd]*", "alphabet": "dDSUu"}))
    assert r.value.labels == ("UudD",)
    assert r.meta["string"] == "SUudDS"


def test_end_to_end_from_dsax_on_a_sharkfin_train():
    fs, n = 10.0, 300
    t = np.arange(n) / fs
    phase = (t % 10.0) / 10.0
    x = np.where(phase < 0.85, phase / 0.85, 1.0 - (phase - 0.85) / 0.15) * 0.01
    d = get_adapter("detection.sax_dsax")
    e = d.run(x, t, fs, **d.validate_params({"seconds_per_symbol": 0.5, "alphabet_size": 3, "threshold_mode": "quantile"})).value
    spec = get_adapter(NAME)
    r = spec.run(x, t, fs, value=e, **spec.validate_params({"pattern": "c+a+"}))
    assert 2 <= r.value.starts.__len__() <= 4, (r.meta["string"], r.value.labels)


def test_bad_regex_and_wrong_encoding_kind_fail_loudly():
    spec = get_adapter(NAME)
    with pytest.raises(ValueError, match="regular expression"):
        spec.run(np.zeros(10), None, 1.0, value=enc([0, 1]), **spec.validate_params({"pattern": "("}))
    with pytest.raises(ValueError, match="symbolic"):
        spec.run(np.zeros(10), None, 1.0, value=Encoding(values=np.zeros((2, 2)), kind="image"), **spec.validate_params({}))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
