"""
test_sax_determinism.py
=========================
fixup-dsax-seed: one recipe, one answer.

dSAX's `threshold_mode="learned"` (the adapter default) and every pSAX
encoding initialise Lloyd-Max with k-means++, whose two random draws came
from the GLOBAL `np.random` — never seeded by the adapters. So the same
recipe, under the same recipe hash, produced different symbol strings and
therefore different `symbol_search` spans from one run to the next (fixup-Z
report §6: 11, 11, 13, 11 detections from four forced runs), and the step
cache froze whichever draw happened first.

The contract pinned here:
  - the same input encoded twice gives the identical string, cutlines and
    spans, whatever the global `np.random` state is beforehand;
  - an encode neither consumes nor reseeds the global `np.random`;
  - the seed is a fixed internal constant, not a `ParamSpec`, so no saved
    chain's recipe hash changes.

fixup-csax-seed extends the same contract to cSAX, whose Mean-Shift
clustering picked each seed point with the global `np.random.rand()`: on
M2_aug_concat_fs1 CH1_A1 at adapter defaults, eight global seeds gave six
different cSAX strings.

Pure-numpy, no database/UI — runnable standalone:
    python tests/test_sax_determinism.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.Detection.sax.csax_python.csax import csax  # noqa: E402
from Working.Detection.sax.csax_python.meanshift.hg_meanshift_cluster import (  # noqa: E402
    hg_meanshift_cluster,
)
from Working.Detection.sax.dsax_python.dsax import dsax  # noqa: E402
from Working.Detection.sax.psax_python.kmeanspp import kmeanspp  # noqa: E402
from Working.Detection.sax.psax_python.psax import psax  # noqa: E402

discover_adapters()

# A noisy sawtooth "sharkfin" train. Chosen because, before the fix, eight
# different global seeds gave three different dSAX strings and two
# different `c+a+` span sets on it — the failure is visible, not
# hypothetical.
FS = 1.0
_n = 6000
T = np.arange(_n) / FS
_phase = (T % 300.0) / 300.0
X = (np.where(_phase < 0.85, _phase / 0.85, 1.0 - (_phase - 0.85) / 0.15)
     + np.random.default_rng(7).normal(0, 1.0, _n))
DIM_RATIO = 0.1              # 10 samples per symbol
GLOBAL_SEEDS = range(8)


def _states_equal(a, b):
    return (a[0] == b[0] and np.array_equal(a[1], b[1])
            and tuple(a[2:]) == tuple(b[2:]))


def _encode_dsax_spans(seed):
    """Disturb the global RNG, then run the adapter chain the
    `symbol_search` template runs: sax_dsax (default = learned) →
    symbol_search."""
    np.random.seed(seed)
    d = get_adapter("detection.sax_dsax")
    e = d.run(X, T, FS, **d.validate_params({"seconds_per_symbol": 10.0})).value
    s = get_adapter("detection.symbol_search")
    r = s.run(X, T, FS, value=e, **s.validate_params({"pattern": "c+a+"}))
    return tuple(e.values.tolist()), (tuple(r.value.starts), tuple(r.value.ends))


# -- the same input gives the same answer --------------------------------

def test_learned_dsax_gives_one_string_and_one_span_set_whatever_the_global_seed():
    runs = [_encode_dsax_spans(seed) for seed in GLOBAL_SEEDS]
    strings = {s for s, _ in runs}
    spans = {sp for _, sp in runs}
    assert len(strings) == 1, f"{len(strings)} different dSAX strings from one recipe"
    assert len(spans) == 1, f"{len(spans)} different span sets from one recipe"


def test_learned_dsax_cutlines_are_identical_across_calls():
    np.random.seed(1)
    a, da = dsax(X, len(X), DIM_RATIO, threshold_mode="learned", return_details=True)
    np.random.seed(999)
    b, db = dsax(X, len(X), DIM_RATIO, threshold_mode="learned", return_details=True)
    assert np.array_equal(a, b)
    assert np.array_equal(da["cutlines"], db["cutlines"])


def test_psax_gives_one_string_whatever_the_global_seed():
    strings = set()
    for seed in GLOBAL_SEEDS:
        np.random.seed(seed)
        strings.add(tuple(psax(X, len(X), DIM_RATIO, 8).tolist()))
    assert len(strings) == 1, f"{len(strings)} different pSAX strings from one input"


def test_psax_adapter_gives_one_string_whatever_the_global_seed():
    spec = get_adapter("detection.sax_psax")
    strings = set()
    for seed in GLOBAL_SEEDS:
        np.random.seed(seed)
        e = spec.run(X, T, FS, **spec.validate_params({"seconds_per_symbol": 10.0})).value
        strings.add(tuple(e.values.tolist()))
    assert len(strings) == 1


# -- the global RNG is neither consumed nor reseeded ---------------------

def test_encoders_leave_the_global_rng_untouched():
    for call in (
        lambda: kmeanspp(X, 3),
        lambda: dsax(X, len(X), DIM_RATIO, threshold_mode="learned"),
        lambda: psax(X, len(X), DIM_RATIO, 8),
    ):
        np.random.seed(424242)
        before = np.random.get_state()
        call()
        after = np.random.get_state()
        assert _states_equal(before, after), "an encode consumed or reseeded np.random"


# -- cSAX: Mean-Shift's seed point (fixup-csax-seed) ---------------------

# On the sharkfin above, before the fix, eight global seeds gave three
# different cSAX strings at the adapter default (20 samples per symbol at
# 1 Hz) and five at 10 samples per symbol, with 2 to 5 clusters.
CSAX_DIM_RATIOS = (0.05, 0.1)


def _csax_details_key(details):
    return (details["alphabet_size"], details["fallback_used"],
            tuple(details["cutlines"].tolist()),
            tuple(np.asarray(details["representatives"]).tolist()),
            tuple(details["paa"].tolist()))


def test_csax_gives_one_string_and_one_set_of_details_whatever_the_global_seed():
    for dim_ratio in CSAX_DIM_RATIOS:
        strings, details = set(), set()
        for seed in GLOBAL_SEEDS:
            np.random.seed(seed)
            out, d = csax(X, len(X), dim_ratio, return_details=True)
            strings.add(tuple(out.tolist()))
            details.add(_csax_details_key(d))
        assert len(strings) == 1, (
            f"{len(strings)} different cSAX strings from one input at dim_ratio={dim_ratio}")
        assert len(details) == 1, (
            f"{len(details)} different cSAX details from one input at dim_ratio={dim_ratio}")


def test_csax_adapter_gives_one_string_whatever_the_global_seed():
    spec = get_adapter("detection.sax_csax")
    strings, cutlines = set(), set()
    for seed in GLOBAL_SEEDS:
        np.random.seed(seed)
        r = spec.run(X, T, FS, **spec.validate_params({}))
        strings.add(tuple(r.value.values.tolist()))
        cutlines.add(tuple(r.meta["details"]["cutlines"].tolist()))
    assert len(strings) == 1, f"{len(strings)} different cSAX strings from one recipe"
    assert len(cutlines) == 1


def test_csax_and_meanshift_leave_the_global_rng_untouched():
    for call in (
        lambda: csax(X, len(X), 0.1),
        lambda: hg_meanshift_cluster(X[:600], "gaussian"),
    ):
        np.random.seed(424242)
        before = np.random.get_state()
        call()
        after = np.random.get_state()
        assert _states_equal(before, after), "a cSAX encode consumed or reseeded np.random"


def test_csax_and_meanshift_take_an_explicit_random_state_for_seed_sweeps():
    a = csax(X, len(X), 0.1, random_state=5)
    b = csax(X, len(X), 0.1, random_state=np.random.default_rng(5))
    assert np.array_equal(a, b)
    ca, la, _ = hg_meanshift_cluster(X[:600], "gaussian", random_state=5)
    cb, lb, _ = hg_meanshift_cluster(X[:600], "gaussian", random_state=np.random.default_rng(5))
    assert np.array_equal(ca, cb) and np.array_equal(la, lb)


# -- the seed is a hook for scripts, not a recipe parameter --------------

def test_kmeanspp_takes_an_explicit_random_state_for_seed_sweeps():
    _, a = kmeanspp(X, 3, random_state=5)
    _, b = kmeanspp(X, 3, random_state=5)
    _, c = kmeanspp(X, 3, random_state=np.random.default_rng(5))
    assert np.array_equal(a, b)
    assert np.array_equal(a, c)


def test_no_seed_param_on_the_sax_adapters_so_recipe_hashes_are_unchanged():
    for name in ("detection.sax_dsax", "detection.sax_psax", "detection.sax_csax"):
        names = {p.name for p in get_adapter(name).params}
        assert not names & {"seed", "random_state", "rng"}, (name, names)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
