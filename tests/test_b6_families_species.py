"""B6 (Chapter 10): do the same shape families occur across recordings and species? Read from the Recurrence page's
own payload, against recording labels shuffled across members (each family's size and each recording's count kept)."""
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "thesis"))

import b6_families_species as B6  # noqa: E402


def _payload(families):
    """A Recurrence payload: {family: {recording: count}} drawn as the page's cells (one channel each)."""
    return {"recordings": [{"key": k, "file": f"{k}.mat"} for k in sorted({r for f in families.values() for r in f})],
            "families": [{"id": fid, "members": sum(c.values()),
                          "cells": {f"{rec}:CH1": {"count": n} for rec, n in c.items()}}
                         for fid, c in families.items()]}


def test_the_table_is_read_off_the_pages_cells():
    t = B6.family_table(_payload({"F-1": {"A": 3, "B": 1}, "F-2": {"B": 2}}))
    assert t["recordings"] == ["A", "B"] and t["families"] == ["F-1", "F-2"]
    assert t["counts"].tolist() == [[3, 1], [0, 2]]


def test_recording_specific_families_beat_the_shuffle():
    # every family lives on one recording: far fewer shared families than shuffled labels give
    fams = {f"F-{i}": {("A" if i % 2 else "B"): 20} for i in range(10)}
    out = B6.read_out(_payload(fams), species={"A": "oyster", "B": "lion's mane"}, draws=2000, seed=0)
    rec = out["by"]["recording"]
    assert rec["observed"]["shared_families"] == 0
    assert rec["null_mean"]["shared_families"] > 8
    assert rec["p_fewer_shared"] == pytest.approx(1 / 2001)
    assert rec["p_mi_higher"] == pytest.approx(1 / 2001)


def test_well_mixed_families_look_like_the_shuffle():
    rng = np.random.default_rng(1)
    fams = {f"F-{i}": {"A": int(rng.integers(5, 15)), "B": int(rng.integers(5, 15))} for i in range(12)}
    out = B6.read_out(_payload(fams), species={"A": "oyster", "B": "lion's mane"}, draws=2000, seed=0)
    assert out["by"]["species"]["observed"]["shared_families"] == 12
    assert out["by"]["species"]["p_mi_higher"] > 0.05


def test_an_unlabelled_recording_is_refused():
    with pytest.raises(ValueError, match="species"):
        B6.read_out(_payload({"F-1": {"A": 2, "C": 1}}), species={"A": "oyster"}, draws=10)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
