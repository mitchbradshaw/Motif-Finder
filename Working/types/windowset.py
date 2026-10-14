"""
windowset.py
=============
`WindowSet` — fixed-length segments over a signal, optionally carrying an
attached per-window feature matrix (e.g. Catch22, entropy). One row per
window, and deliberately **no timepoint alignment** — unlike `Scores`, a
window count has no obligation to match the source signal's length, so
`WindowSet` carries no assertion against a `Signal`.

Serialises to a compressed `.npz` for the window geometry and, when
present, a `.parquet` for the attached feature table — see
`docs/PIPELINE_PRD.md` "Type system": arrays serialise to compressed numpy
archives, feature tables to parquet.
"""

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

_GEOMETRY_FILENAME = "windowset.npz"
_FEATURES_FILENAME = "features.parquet"

#: Columns of a WindowSet's feature table that say where a window sits or who decided it
#: was there - never what the signal in it looks like. Every consumer that treats the
#: table as features (`catalogue.cluster`, `catalogue.classifier`) drops them first; a
#: clustering or a model that saw one would recover time, the split or the detector's
#: own decision instead of the signal's shape:
#:   split            - train / validation / test role (`preprocessing.sliding_windows`, P12)
#:   event_index      - the event's row in the SpanSet: a time order (`catalogue.event_windows`)
#:   anchor_offset    - window geometry, the same for every window
#:   overlaps_next    - window geometry
#:   train_id, word_id - time-ordered identifiers (`interrogation.trains`)
#:   span_score       - the detector's own score for the span (e.g. noise_threshold's
#:                      excursion in units of the local noise): its decision, not the shape
#:   family, family_omit_reason, family_distance, family_noise_like
#:                    - a clustering's own answer about the event (`interrogation.event_families`):
#:                      a label, its reason, the distance to its medoid and the noise flag - a
#:                      second clustering or a classifier that saw one would learn the first's answer
#:   group_upstream   - the group a feature block replaced (`interrogation.trains`,
#:                      `interrogation.event_families`): a label
#:   cycle_index      - the cycle's position in its sequence (`interrogation.cycle_shapes`): a time order
#:   cycle_group      - the cycle-shape group that block decided: its answer, not the shape
#:   cycle_change, cycle_omit_reason, cycle_corr, cycle_shift_s
#:                    - the same block's decisions about the cycle: whether its group changed, why it
#:                      was left out, its correlation with its group's medoid (as family_distance), and
#:                      how far it was shifted to line up (geometry, as anchor_offset)
#: Measurements (intervals, Event-shape measures, cycle_length_s / cycle_amplitude /
#: cycle_floor_frac / cycle_half_recovery_frac) are NOT here: they stay features, and
#: `catalogue.cluster`'s meta names the columns it actually used (`feature_names`).
#:   mse_n_scales, mse_n_collapsed
#:                    - how many scales a multiscale-entropy curve has defined, and how many its
#:                      collapse guard flagged (`catalogue.multiscale_entropy`): the estimate's
#:                      quality, not the signal's shape
#:   mse_r            - the tolerance in the signal's STORED units: a clustering that saw it separated
#:                      a V-stored from an mV-stored copy of one process (w3-a critic, silhouette
#:                      0.177 against 0.079 without it), and loud from quiet, which MSE ignores
#:   mse_drift_share, mse_inflation
#:                    - how much of the window is a ramp, and how much slow content inflated r
#:                      (the collapse guard's measure): drift, not complexity
BOOKKEEPING_COLUMNS = ("split", "event_index", "anchor_offset", "overlaps_next", "train_id", "word_id",
                       "span_score", "family", "family_omit_reason", "family_distance", "family_noise_like",
                       "group_upstream", "mse_n_scales", "mse_n_collapsed", "mse_r", "mse_drift_share",
                       "mse_inflation", "cycle_index", "cycle_group", "cycle_change", "cycle_omit_reason",
                       "cycle_corr", "cycle_shift_s")


def span_relative_starts(ws, n_samples, t, fs, block="this block"):
    """Each window's start as an index into the span's `x` (`WindowSet.starts` are channel-absolute;
    the span's offset is `round(t[0] * fs)`), refusing in words any window that runs outside the span.

    Promoted from `Working/Catalogue/minirocket.py::_slice_x` (w3-a) so the window slicers share one
    bounds rule; `block` names the caller in the refusal."""
    L = int(ws.length)
    span_start = int(round(float(t[0]) * float(fs))) if t is not None and len(t) else 0
    rel = np.asarray(ws.starts, dtype=np.int64) - span_start
    bad = np.flatnonzero((rel < 0) | (rel + L > int(n_samples)))
    if len(bad):
        i = int(bad[0])
        raise ValueError(
            f"{len(bad):,} of {len(rel):,} windows lie outside this span (window {i} covers channel samples "
            f"{int(ws.starts[i]):,}-{int(ws.starts[i]) + L:,}; the span is {span_start:,}-"
            f"{span_start + int(n_samples):,}, so it runs past the span): run {block} on the span its windows "
            f"were made on")
    return rel


@dataclass(frozen=True, eq=False)
class WindowSet:
    """Fixed-length windows over a signal, with an optional attached
    per-window feature table.

    Attributes
    ----------
    starts : np.ndarray
        Sample index of each window's start, one per window — **channel-
        absolute** (the index into the whole recorded channel, not into the
        span the chain ran over). Every producer adds the span's offset
        (`preprocessing.window_matrix`, `preprocessing.sliding_windows`
        recover it from `t[0] * fs`); every consumer that slices the span's
        `x` subtracts it (`catalogue.window_images`, `catalogue.cnn_score`);
        the bridge draws `starts / fs` directly. SpanSet is the other
        convention (span-relative) — do not mix them.
    length : int
        Window length in samples, fixed across the set.
    fs : float
        Sample rate in Hz.
    features : pd.DataFrame | None
        One row per window, in `starts` order, or None if no feature
        matrix is attached.
    """
    starts: np.ndarray
    length: int
    fs: float
    features: Optional[pd.DataFrame] = None

    def __post_init__(self):
        if self.features is not None and len(self.features) != len(self.starts):
            raise ValueError(
                f"features has {len(self.features)} row(s) but there are "
                f"{len(self.starts)} window(s) — WindowSet carries one feature "
                "row per window."
            )

    @property
    def n_windows(self):
        return len(self.starts)

    def __eq__(self, other):
        if not isinstance(other, WindowSet):
            return NotImplemented
        if self.length != other.length or self.fs != other.fs:
            return False
        if not np.array_equal(self.starts, other.starts):
            return False
        if (self.features is None) != (other.features is None):
            return False
        if self.features is None:
            return True
        a = self.features.reset_index(drop=True)
        b = other.features.reset_index(drop=True)
        return a.equals(b)

    def to_path(self, dir_path):
        """Write this window set to `dir_path` (created if missing) and
        return the path to the geometry archive."""
        os.makedirs(dir_path, exist_ok=True)
        geometry_path = os.path.join(dir_path, _GEOMETRY_FILENAME)
        np.savez_compressed(
            geometry_path,
            starts=np.asarray(self.starts, dtype=np.int64),
            length=np.int64(self.length),
            fs=np.float64(self.fs),
        )
        if self.features is not None:
            features_path = os.path.join(dir_path, _FEATURES_FILENAME)
            self.features.to_parquet(features_path, index=False)
        return geometry_path

    @classmethod
    def from_path(cls, dir_path):
        """Read a `WindowSet` back from `dir_path`."""
        geometry_path = os.path.join(dir_path, _GEOMETRY_FILENAME)
        with np.load(geometry_path, allow_pickle=False) as data:
            starts = data["starts"]
            length = int(data["length"])
            fs = float(data["fs"])

        features_path = os.path.join(dir_path, _FEATURES_FILENAME)
        features = pd.read_parquet(features_path) if os.path.isfile(features_path) else None

        return cls(starts=starts, length=length, fs=fs, features=features)
