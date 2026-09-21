"""
identity.py
===========
The two halves of a motif's identity, exactly as `docs/LIBRARY_STORAGE.md` §2
pins them down:

  content hash    *which entry* — is this the same shape?
  occurrence key  *which member* — is this the same place?

The content hash is taken over the waveform alone, resampled to a fixed length
and z-normalised — **the same resample-then-z-normalise pair
`Working.distances.scale_invariant_distance` uses**. That is deliberate rather
than incidental: the hash and the default distance must agree on what "the same
shape" means, so a pair at distance 0 hashes the same. Both steps are imported
from `Working.distances` rather than re-derived here, because a second copy of
`z_normalize` is a second definition of identity.

What is deliberately *not* hashed (§2.3): sampling rate — a drop at 1 Hz and
the same drop at 10 Hz are **one entry**; amplitude and baseline — depth is a
measured feature, not identity; and every metadata column, so that an event
re-imported with one column changed resolves onto its existing entry rather
than forking the catalogue (PRD story 43). Where the span *is* lives in the
occurrence key instead.

The three constants below are pinned. Changing any of them re-hashes the whole
library, which is why they are module constants and not parameters a caller may
vary silently.

Nothing here imports a UI library (CLAUDE.md rule 1).
"""

import hashlib

import numpy as np

from Working.distances import resample_to_length, z_normalize

# §2.2. Changing either means re-hashing the whole library.
HASH_LENGTH = 256
HASH_DECIMALS = 6

# blake2b truncated to 16 bytes -> 32 hex characters. Short enough to read off
# a row, wide enough that a collision is not a thing that happens to a
# catalogue of this size.
HASH_DIGEST_SIZE = 16


def content_hash(values, *, length=HASH_LENGTH, decimals=HASH_DECIMALS):
    """The shape-first identity of one span's waveform (§2.2).

    `values` is resampled to `length` points, z-normalised, rounded to
    `decimals` and digested. The rounding is what stops two reads of the same
    snippet that differ far below the stated precision from becoming two
    motifs; `+ 0.0` folds `-0.0` onto `0.0` so a sign bit on a zero cannot
    split an entry in two.

    Empty input and any non-finite sample are refused loudly with a
    `ValueError` naming which of the two it was. A silent digest over NaN bytes
    would let a corrupt import look like a brand-new motif, which is the
    failure this guard exists for.

    Returns 32 lowercase hex characters.
    """
    x = np.asarray(values, dtype=float).ravel()
    if x.size == 0:
        raise ValueError(
            "content_hash: the span is empty — a motif with no samples has no "
            "shape to be the identity of."
        )
    if not np.all(np.isfinite(x)):
        n_bad = int(np.count_nonzero(~np.isfinite(x)))
        raise ValueError(
            f"content_hash: the span carries {n_bad} non-finite sample(s) "
            "(NaN or +/-inf). A corrupt snippet must not hash to something "
            "plausible — fix the source rather than hashing around it."
        )

    r = resample_to_length(x, int(length))
    # `z_normalize` means to return zeros for a flat span, but it decides that
    # on `std() == 0`, and the float variance of a constant span that is not
    # zero (4.2 repeated 256 times) comes out at ~1e-15 rather than exactly 0.
    # Dividing by that turns rounding dust into a full-amplitude waveform, so
    # two flat spans at different levels would hash differently. Peak-to-peak
    # is exact where the variance is not: a constant array has ptp 0 on the
    # nose. §2.2's "std == 0 -> all zeros" is the intent; this is how it holds.
    z = np.zeros_like(r) if np.ptp(r) == 0 else z_normalize(r)
    q = np.round(z, int(decimals)) + 0.0
    return hashlib.blake2b(
        q.astype("<f8").tobytes(), digest_size=HASH_DIGEST_SIZE
    ).hexdigest()


def occurrence_key(content_hash, *, recording_id, channel, start_idx, end_idx):
    """The other half of identity: *which place* this shape was found in.

    Same hash means the same `motif_entry`; same hash **and** the same
    occurrence key means the same `motif_member`, and a description change on
    it is a revision rather than a second row (§2.1).

    The hash is embedded as the key's prefix on purpose — a key carries its own
    entry with it, so a member key read off a row says which shape it belongs
    to without a join.
    """
    return "{}:{}:{}:{}:{}".format(
        content_hash, int(recording_id), int(channel), int(start_idx), int(end_idx)
    )


def _channel_recording(conn, recording_id, channel):
    """The `recordings` row holding `channel` of the acquisition that
    `recording_id` belongs to.

    A recording row in this schema is one *(source_file, channel)* pair, so the
    channel is already implied by the id. A caller carrying both — every
    Library row does, because `motif_member` gained its own `channel` column
    (§3.2) — may name a sibling channel of the same source file, and that must
    resolve rather than silently hash the wrong trace.
    """
    row = conn.execute(
        "SELECT * FROM recordings WHERE id = ?", (int(recording_id),)
    ).fetchone()
    if row is None:
        raise ValueError(f"No recording with id={recording_id}")
    if channel is None or int(row["channel"]) == int(channel):
        return row

    sibling = conn.execute(
        "SELECT * FROM recordings WHERE source_file = ? AND channel = ?",
        (row["source_file"], int(channel)),
    ).fetchone()
    if sibling is None:
        raise ValueError(
            f"Recording {recording_id} is channel {row['channel']} of "
            f"{row['source_file']!r}, and no row registers its channel "
            f"{channel}. The span cannot be hashed against a channel that was "
            "never registered."
        )
    return sibling


def hash_span(conn, recording_id, channel, start_idx, end_idx):
    """`content_hash` of a span read off disk, by database coordinates.

    The samples come from the channel's `.npy`, mmapped and the slice copied
    out, the same way `Working.library.matching._load_span` reads one — the
    bulk array stays on disk and only the span travels (CLAUDE.md rule 4).

    Raises `ValueError` when the channel is unregistered, when its `.npy` is
    missing, or when the span falls outside it. A missing channel file is the
    common case on a fresh clone, and it must say so rather than surface as an
    opaque numpy error three frames up.
    """
    recording = _channel_recording(conn, recording_id, channel)

    start_idx, end_idx = int(start_idx), int(end_idx)
    if end_idx <= start_idx or start_idx < 0:
        raise ValueError(
            f"Span [{start_idx}, {end_idx}) is not a span — end must exceed "
            "start and start must not be negative."
        )

    path = recording["npy_path"]
    try:
        x_full = np.load(path, mmap_mode="r")
    except OSError as exc:
        raise ValueError(
            f"Channel {recording['channel']} of {recording['source_file']!r} "
            f"is registered at {path!r}, but that file cannot be read: {exc}"
        ) from exc

    if end_idx > len(x_full):
        raise ValueError(
            f"Span [{start_idx}, {end_idx}) runs past channel "
            f"{recording['channel']} of {recording['source_file']!r}, which "
            f"holds {len(x_full)} samples."
        )

    return content_hash(np.array(x_full[start_idx:end_idx]))
