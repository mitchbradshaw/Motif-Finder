"""Read the wave-1 thesis bundle (scripts/thesis/wave1): series, stacks of windows and tables.

    import bundle_io as B
    b = B.Bundle("/path/to/unzipped/bundle")          # the folder holding REPORT.md and data/
    x, meta = b.series("m4_exam/m4_exam__CH2__155.363-203.363h")   # mV, meta has t0_s, dt_s, fs ...
    t = b.time_h(meta, len(x))                          # hours from the recording's first sample
    st = b.stack("library_events/library_event_windows") # index DataFrame + window(i) -> (t_s, mV)
    df = b.csv("pool/pool_counts")

The bundle is read-only input; nothing here writes into it.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd


class Stack:
    def __init__(self, path_stem: str):
        z = np.load(path_stem + ".npz")
        self.values, self.offsets = z["values"], z["offsets"]
        self.index = pd.read_csv(path_stem + "_index.csv")
        meta = path_stem + ".json"
        self.meta = json.load(open(meta)) if os.path.exists(meta) else {}

    def __len__(self):
        return len(self.index)

    def window(self, i: int):
        """(t in seconds from the recording's first sample, mV) for row i of the index."""
        r = self.index.iloc[i]
        o0, o1 = int(self.offsets[int(r["row"])]), int(self.offsets[int(r["row"]) + 1])
        y = self.values[o0:o1].astype(float)
        t = float(r["t0_s"]) + np.arange(len(y)) * float(r["dt_s"])
        return t, y


class Bundle:
    def __init__(self, root: str):
        self.root = root
        self.data = os.path.join(root, "data")

    def path(self, rel: str) -> str:
        return os.path.join(self.data, rel)

    def series(self, rel_stem: str):
        """A single series (or channels x time) and its sidecar. Chunked series are joined."""
        p = self.path(rel_stem)
        if os.path.exists(p + ".npz"):
            meta = json.load(open(p + ".json"))
            return np.load(p + ".npz")[meta.get("npz_key", "x")].astype(float), meta
        parts = sorted(f for f in os.listdir(os.path.dirname(p)) if f.startswith(os.path.basename(p) + "__chunk")
                       and f.endswith(".npz"))
        if not parts:
            raise FileNotFoundError(p)
        xs, metas = [], []
        for f in parts:
            stem = os.path.join(os.path.dirname(p), f[:-4])
            m = json.load(open(stem + ".json"))
            xs.append(np.load(stem + ".npz")[m.get("npz_key", "x")].astype(float))
            metas.append(m)
        return np.concatenate(xs, axis=-1), metas[0]

    @staticmethod
    def time_h(meta: dict, n: int):
        return (float(meta["t0_s"]) + np.arange(n) * float(meta.get("dt_s", 1.0 / float(meta["fs"])))) / 3600.0

    def stack(self, rel_stem: str) -> Stack:
        return Stack(self.path(rel_stem))

    def csv(self, rel_stem: str) -> pd.DataFrame:
        p = self.path(rel_stem if rel_stem.endswith(".csv") else rel_stem + ".csv")
        return pd.read_csv(p, low_memory=False)

    def ls(self, rel_dir: str):
        return sorted(os.listdir(self.path(rel_dir)))
