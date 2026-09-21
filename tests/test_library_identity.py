"""
test_library_identity.py
========================
Contract tests for `Working.library.identity` — the shape-first content hash
that gives a motif its identity (stage-3 Prompt 03, `docs/LIBRARY_STORAGE.md`).

The hash is what makes "the same motif" a decidable question. It is taken on
the *shape* alone: the span's samples resampled to a fixed length and
z-normalised, exactly as `Working.distances.scale_invariant_distance`
compares two spans. So:

  - the same curve at twice the amplitude, or shifted by an offset, hashes the
    same (z-normalisation);
  - a different curve hashes differently;
  - metadata is NOT in the hash, so re-importing an event with one column
    changed resolves onto the same entry rather than creating a second one.

Where the span *is* — recording, channel, sample range — is deliberately not
in the content hash; it is the second half of the identity, carried by
`occurrence_key`. Same hash means the same `motif_entry`; same hash AND the
same occurrence means the same `motif_member`.

What the hash does NOT do is recognise one shape across two sampling rates.
That was the first thing this file asserted and it was wrong — see
`test_the_same_curve_at_two_sampling_rates_does_NOT_hash_the_same` for the
measurement and the reason. Three mechanisms answer three questions, and
collapsing them is the mistake to avoid:

    hash     is this the same waveform?   -> re-import is idempotent
    distance is this the same shape?      -> a motif recurring at another rate
    IoU      is this the same span?       -> a duplicate detection of one event
"""

import numpy as np
import pytest

from Working.distances import scale_invariant_distance
from Working.library.identity import (
    HASH_DECIMALS,
    HASH_LENGTH,
    content_hash,
    occurrence_key,
)


def _drop(n, depth=1.0, offset=0.0):
    """A rise-then-fall drop motif sampled at `n` points — the shape the
    library is full of, in the amplitude the caller asks for."""
    t = np.linspace(0.0, 1.0, n)
    shape = np.sin(np.pi * t) ** 3 - 0.35 * t
    return offset + depth * shape


def test_hash_is_deterministic():
    x = _drop(128)
    assert content_hash(x) == content_hash(x)
    assert content_hash(x) == content_hash(list(x))


def test_hash_is_a_short_hex_digest():
    h = content_hash(_drop(128))
    assert isinstance(h, str)
    assert len(h) == 32
    int(h, 16)          # hex, and nothing else


def test_the_same_curve_at_two_sampling_rates_does_NOT_hash_the_same():
    """The 1 Hz / 10 Hz case, and the one place the hash deliberately stops
    short.

    Resampling is lossy: interpolating 100 points up to 256 does not land on
    the same values as decimating 1000 points down to 256. Measured on this
    curve the two normalised vectors differ by up to 5.2e-4, and 255 of the
    256 samples differ by more than the rounding quantum. No choice of
    HASH_DECIMALS fixes that — a coarser quantum only moves the boundary that
    the two values straddle, and over 256 samples something always straddles
    it. A hash cannot implement a tolerance; that is what a distance is for.

    So the hash answers "is this the same waveform" (which is what makes
    re-import idempotent), and `scale_invariant_distance` answers "is this the
    same shape" (which is what finds a motif recurring at another sampling
    rate). `test_the_distance_is_what_recognises_a_shape_across_rates` below
    pins the other half. Do not "fix" this by fuzzing the hash: a
    locality-sensitive hash has false positives, and a library that silently
    merges two motifs is worse than one that asks."""
    assert content_hash(_drop(100)) != content_hash(_drop(1000))


def test_the_distance_is_what_recognises_a_shape_across_rates():
    """The other half of the rule above: what the hash will not do, the
    scale-invariant distance does — and by three orders of magnitude, so the
    separation is not marginal."""
    same_shape = scale_invariant_distance(_drop(100), _drop(1000))
    other_shape = scale_invariant_distance(
        _drop(100), np.sin(6 * np.pi * np.linspace(0.0, 1.0, 256)))
    assert same_shape < 0.05
    assert other_shape > 100 * same_shape


def test_same_shape_at_a_different_amplitude_hashes_the_same():
    """z-normalisation: depth is a measured feature, not part of identity."""
    assert content_hash(_drop(256, depth=1.0)) == content_hash(_drop(256, depth=17.0))


def test_same_shape_at_a_different_baseline_hashes_the_same():
    assert content_hash(_drop(256, offset=0.0)) == content_hash(_drop(256, offset=-340.0))


def test_a_different_shape_hashes_differently():
    t = np.linspace(0.0, 1.0, 256)
    assert content_hash(_drop(256)) != content_hash(np.sin(6 * np.pi * t))


def test_a_constant_span_hashes_without_dividing_by_zero():
    """std == 0 returns the all-zero vector (Working.distances.z_normalize),
    so a flat span has a hash rather than an exception — and every flat span
    has the same one."""
    assert content_hash(np.zeros(64)) == content_hash(np.full(64, 4.2))


def test_an_empty_span_is_refused():
    with pytest.raises(ValueError):
        content_hash(np.array([]))


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_a_non_finite_sample_is_refused_loudly(bad):
    """A NaN in a snippet must not hash to something plausible — a silent
    digest over NaN bytes would let a corrupt import look like a new motif."""
    x = _drop(64)
    x[7] = bad
    with pytest.raises(ValueError):
        content_hash(x)


def test_rounding_absorbs_float_noise_below_the_stated_precision():
    """Two reads of the same snippet that differ far below HASH_DECIMALS must
    not be two motifs."""
    x = _drop(256)
    jitter = x + 10.0 ** (-(HASH_DECIMALS + 4))
    assert content_hash(x) == content_hash(jitter)


def test_the_hash_length_is_the_stated_constant():
    """A resample length change is a re-hash of the whole library, so the
    number is a pinned constant, not an argument someone may vary silently."""
    assert HASH_LENGTH == 256
    assert content_hash(_drop(40)) == content_hash(_drop(40), length=HASH_LENGTH)


def test_occurrence_key_carries_where_the_span_is():
    """The other half of identity: same shape, two places, two members."""
    h = content_hash(_drop(128))
    a = occurrence_key(h, recording_id=10, channel=3, start_idx=100, end_idx=228)
    b = occurrence_key(h, recording_id=10, channel=4, start_idx=100, end_idx=228)
    c = occurrence_key(h, recording_id=10, channel=3, start_idx=100, end_idx=228)
    assert a == c
    assert a != b
    assert h in a


def test_occurrence_key_distinguishes_spans_in_one_channel():
    h = content_hash(_drop(128))
    a = occurrence_key(h, recording_id=1, channel=0, start_idx=100, end_idx=228)
    b = occurrence_key(h, recording_id=1, channel=0, start_idx=101, end_idx=229)
    assert a != b
