"""
test_webui_units.py
===================
fixup-b — the web bridge converts a channel to millivolts at ONE named seam,
and a raw array and a millivolt array are never in circulation under the same
name.

* `corpus.load_native(path)` is what the core is handed: the stored samples,
  byte for byte (volts for a volts file). It is never drawn.
* `corpus.display_channel(rec)` is what a page draws: millivolts when the
  recording declares its unit, and — when it does not — the stored numbers
  with `unit = None`, so the page says "unit undeclared" instead of "mV".
* `corpus.load_channel` is gone: the one name that did not say which of the
  two it returned is the name the 1000x error lived behind.

No FastAPI: these are the service modules, importable under conda.
"""

import gc
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from server import corpus  # noqa: E402
from server.serialize import to_payload  # noqa: E402
from Working.types import Signal  # noqa: E402

#: The first three samples of the span behind seed event id001_r1_1213252
#: (CH0.npy[1212809:]) and the store's own __raw_mv for the same samples.
VOLTS = np.array([-0.45839212, -0.45842311, -0.45842109, -0.44], dtype=np.float64)
STORE_MV = np.array([-458.39212, -458.42311, -458.42109, -440.0])


@pytest.fixture(autouse=True)
def _release_mmaps():
    yield
    corpus._yrange.cache_clear()
    corpus._mmap.cache_clear()
    gc.collect()


def _rec(tmp_path, units, values=VOLTS, name="CH0.npy"):
    p = str(tmp_path / name)
    np.save(p, np.asarray(values, dtype=np.float64))
    return {"id": 1, "npy_path": p, "fs": 1.0, "n_samples": len(values), "units": units}


def test_the_ambiguous_loader_is_gone():
    assert not hasattr(corpus, "load_channel"), \
        "`load_channel` returned stored volts to callers that printed them as mV; every caller must now choose"


def test_load_native_is_the_stored_samples_byte_for_byte(tmp_path):
    rec = _rec(tmp_path, "V")
    assert np.array_equal(np.asarray(corpus.load_native(rec["npy_path"])), VOLTS)


def test_a_volts_recording_is_drawn_in_millivolts(tmp_path):
    ch = corpus.display_channel(_rec(tmp_path, "V"))
    assert ch.unit == "mV"
    assert len(ch) == len(VOLTS)
    assert np.allclose(ch[0:4], STORE_MV, rtol=0, atol=1e-9), \
        "a depth the app prints must equal the depth the detector recorded"


def test_a_millivolts_recording_is_drawn_as_stored(tmp_path):
    ch = corpus.display_channel(_rec(tmp_path, "mV", values=STORE_MV))
    assert ch.unit == "mV"
    assert np.array_equal(ch[0:4], STORE_MV)


def test_an_undeclared_recording_is_never_labelled_millivolts(tmp_path):
    ch = corpus.display_channel(_rec(tmp_path, None))
    assert ch.unit is None, "an undeclared unit is said, never assumed"
    assert np.array_equal(ch[0:4], VOLTS), "and its numbers are not scaled by a guess"


def test_the_y_extent_is_in_the_display_unit(tmp_path):
    assert corpus.y_range(_rec(tmp_path, "V")) == pytest.approx([-458.42311, -440.0])
    corpus._yrange.cache_clear(); corpus._mmap.cache_clear(); gc.collect()
    assert corpus.y_range(_rec(tmp_path, None, name="u.npy")) == pytest.approx([-0.45842311, -0.44])


def test_the_explore_window_is_in_millivolts_and_says_so(tmp_path):
    rec = _rec(tmp_path, "V")
    w = corpus.window(None, rec, 0.0, 4.0, 400)
    assert w["unit"] == "mV"
    assert np.allclose(w["envelope"]["v"], STORE_MV)
    rec_u = _rec(tmp_path, None, name="u.npy")
    w_u = corpus.window(None, rec_u, 0.0, 4.0, 400)
    assert w_u["unit"] is None


def test_a_chain_signal_payload_is_drawn_in_the_recordings_unit():
    """Every Signal-producing block (detrend, band/high/low-pass, surrogate)
    preserves units, so a chain's Signal is in the recording's stored unit and
    is converted by the same factor for display — and only for display."""
    sig = Signal(x=VOLTS.copy(), fs=1.0)
    p = to_payload("signal", sig, {}, {"fs": 1.0, "span_start": 0, "px": 100, "units": "V"})
    assert p["unit"] == "mV"
    assert p["y_range"] == pytest.approx([-458.42311, -440.0])
    assert "mV" in p["summary"] and "-458.423" in p["summary"]
    assert np.array_equal(sig.x, VOLTS), "the core's value is not mutated by drawing it"
    pu = to_payload("signal", Signal(x=VOLTS.copy(), fs=1.0), {}, {"fs": 1.0, "span_start": 0, "px": 100, "units": None})
    assert pu["unit"] is None
    assert "mV" not in pu["summary"] and "undeclared" in pu["summary"]
