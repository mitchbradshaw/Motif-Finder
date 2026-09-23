"""
spanset.py
===========
`SpanSet` — regions of interest over a signal, optionally labelled and
scored. This is what a "threshold a Scores to obtain a SpanSet" block
produces, and what an annotation or detection ultimately is.

Serialises to `.json` — see `docs/PIPELINE_PRD.md` "Type system": span sets
serialise to JSON. An attached per-span feature table (fixup-d) goes beside it
as `.parquet`, exactly as `WindowSet`'s does: the feature blocks
(`interrogation.event_shape`, `interrogation.intervals`) are `SpanSet ->
SpanSet` and carry their measures here, so no eighth interchange type exists
(`Working/types/__init__.py`).
"""

import json
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import pandas as pd

_FILENAME = "spanset.json"
_FEATURES_FILENAME = "features.parquet"


@dataclass(frozen=True, eq=False)
class SpanSet:
    """A set of `[start, end)` regions over a signal, optionally labelled
    and/or scored.

    Attributes
    ----------
    starts, ends : tuple[int, ...]
        Sample-index bounds of each span, same length. `ends[i] >
        starts[i]` for every `i`.
    labels : tuple[str | None, ...] | None
        One label per span, or None if spans carry no labels.
    scores : tuple[float | None, ...] | None
        One score per span, or None if spans carry no scores.
    features : pd.DataFrame | None
        One row of measures per span, in `starts` order, or None (every
        detector's output, and every SpanSet written before fixup-d).
        Mirrors `WindowSet.features`: same invariant, same parquet file, same
        `__eq__`. Index columns in it (`onset_idx`, `extremum_idx`, ...) are
        span-relative, like `starts`.
    """
    starts: Tuple[int, ...]
    ends: Tuple[int, ...]
    labels: Optional[Tuple[Optional[str], ...]] = None
    scores: Optional[Tuple[Optional[float], ...]] = None
    features: Optional[pd.DataFrame] = None

    def __post_init__(self):
        n = len(self.starts)
        if len(self.ends) != n:
            raise ValueError(
                f"starts and ends must have the same length, got {n} and {len(self.ends)}"
            )
        if self.labels is not None and len(self.labels) != n:
            raise ValueError(f"labels must have length {n}, got {len(self.labels)}")
        if self.scores is not None and len(self.scores) != n:
            raise ValueError(f"scores must have length {n}, got {len(self.scores)}")
        for start, end in zip(self.starts, self.ends):
            if end < start:
                raise ValueError(f"span end {end} precedes its start {start}")
        if self.features is not None and len(self.features) != n:
            raise ValueError(
                f"features has {len(self.features)} row(s) but there are {n} span(s) "
                "— SpanSet carries one feature row per span."
            )

    def __eq__(self, other):
        if not isinstance(other, SpanSet):
            return NotImplemented
        if (tuple(self.starts), tuple(self.ends)) != (tuple(other.starts), tuple(other.ends)):
            return False
        if self.labels != other.labels or self.scores != other.scores:
            return False
        if (self.features is None) != (other.features is None):
            return False
        if self.features is None:
            return True
        return self.features.reset_index(drop=True).equals(other.features.reset_index(drop=True))

    def to_path(self, dir_path):
        """Write this span set to `dir_path` (created if missing) and
        return the path to the written file."""
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, _FILENAME)
        payload = {
            "starts": list(self.starts),
            "ends": list(self.ends),
            "labels": list(self.labels) if self.labels is not None else None,
            "scores": list(self.scores) if self.scores is not None else None,
        }
        with open(path, "w") as f:
            json.dump(payload, f, sort_keys=True)
        features_path = os.path.join(dir_path, _FEATURES_FILENAME)
        if self.features is not None:
            self.features.to_parquet(features_path, index=False)
        elif os.path.exists(features_path):
            # a directory rewritten in place must not keep an earlier write's table
            os.remove(features_path)
        return path

    @classmethod
    def from_path(cls, dir_path):
        """Read a `SpanSet` back from `dir_path`."""
        path = os.path.join(dir_path, _FILENAME)
        with open(path) as f:
            payload = json.load(f)
        features_path = os.path.join(dir_path, _FEATURES_FILENAME)
        return cls(
            starts=tuple(payload["starts"]),
            ends=tuple(payload["ends"]),
            labels=tuple(payload["labels"]) if payload["labels"] is not None else None,
            scores=tuple(payload["scores"]) if payload["scores"] is not None else None,
            features=pd.read_parquet(features_path) if os.path.isfile(features_path) else None,
        )
