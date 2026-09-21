"""
catalogue_cluster.py
=====================
Adapter for the dendrogram clustering stage in
`Working.Catalogue.dendrogram.dendrogram_cluster` — the missing typed link
from a `WindowSet` (a per-window feature matrix) to a `Grouping` (one
integer cluster label per window).

`dendrogram_cluster` exposes two stages — `preprocess_window_matrix` and
`cluster_window_matrix` — and a long tail of visualisation helpers. This
adapter exposes exactly the two calls the typed chain needs, and surfaces
only `linkage` and `k` as parameters because the thesis plan records both
as unresolved research decisions: they must stay tunable from the block
inspector rather than be baked into the adapter.

The underlying module imports matplotlib at module scope for its plotting
half, so it is imported lazily inside `_cluster_window_set` rather than at
adapter-import time — registering this adapter must not drag a plotting
backend into every `discover_adapters()` call.
"""

import os

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types import Grouping

# Where `persist` writes a run's labels. Module-level so the bridge's sandbox
# runtime can redirect it (same pattern as the matrix-profile and window-matrix
# adapters' RESULTS_DIR); read by name at call time.
RESULTS_DIR = os.path.join("DATA", "derived", "groupings")


def _cluster_window_set(window_set, linkage, k):
    """Run the two dendrogram stages and return the `ClusterResult`."""
    if window_set is None:
        raise ValueError(
            "catalogue.cluster requires a WindowSet input from a prior step "
            "(input_kind='windowset')."
        )
    features = window_set.features
    if features is None or features.shape[0] == 0 or features.shape[1] == 0:
        raise ValueError(
            "catalogue.cluster requires a WindowSet with an attached feature "
            "matrix, one row per window."
        )
    if k > len(features):
        raise ValueError(
            f"k={k} exceeds the number of windows ({len(features)}) — cannot "
            "cut more clusters than there are leaves."
        )

    from Working.Catalogue.dendrogram.dendrogram_cluster import (
        cluster_window_matrix,
        preprocess_window_matrix,
    )

    preprocessed = preprocess_window_matrix(features)
    return cluster_window_matrix(preprocessed, method=linkage, n_clusters=k)


def _run(x, t, fs, linkage="ward", k=3, value=None):
    cluster = _cluster_window_set(value, linkage, k)
    return AdapterResult(
        output_kind="grouping",
        value=Grouping(labels=cluster.labels),
        meta={
            "linkage": linkage,
            "k": k,
            "cluster_counts": cluster.cluster_counts,
            "n_windows": cluster.n_windows,
            "n_features": cluster.n_features,
        },
    )


def _derive(x, t, fs, params, value=None):
    """Pre-run readout: cluster sizes for the current linkage and k.

    `derive` is normally called with `(x, t, fs, params)`. Because this
    block's primary input is a typed `WindowSet` rather than the root
    signal, the window set can be supplied as the optional `value` keyword
    (the same way `_run` receives it from `execute_recipe`). Without it
    there is no matrix to cluster, so the readout says so instead of
    inventing a number.
    """
    if value is None:
        return [("Cluster sizes", "run the window-matrix step first", "warn")]

    cluster = _cluster_window_set(value, params["linkage"], params["k"])
    sizes = ", ".join(
        str(cluster.cluster_counts[label])
        for label in sorted(cluster.cluster_counts)
    )
    return [
        ("Clusters requested", str(params["k"]), ""),
        ("Windows clustered", str(cluster.n_windows), ""),
        ("Cluster sizes", sizes, ""),
    ]


def _estimate(x, t, fs, **params):
    """Always None ("not calibrated"): a linkage tree costs O(w^2 log w) in the
    number of WINDOWS, which is a property of the WindowSet flowing in, not of
    the root span or of `linkage`/`k` - the only things an estimator is handed.
    Declaring the callable still matters: `route_recipe` reports 'unknown' for
    a None-answering estimator instead of costing the step at zero."""
    return None


def _persist(conn, run_id, config_hash, recording, span_start, span_end, params, result):
    """Write the labels as a CSV (window index, cluster label) under
    `RESULTS_DIR` and register it as an `artifacts(kind='csv')` row, so a
    headless run leaves a browsable grouping behind (rule 4: the array lives
    on disk, the database holds the path)."""
    import numpy as np

    labels = np.asarray(result.value.labels).astype(int).ravel()
    stem = os.path.splitext(str(recording["source_file"]))[0]
    name = f"{stem}_ch{recording['channel']}_{span_start}-{span_end}_{config_hash}_{params['linkage']}_k{params['k']}.csv"
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("window_index,label\n")
        for i, lab in enumerate(labels):
            f.write(f"{i},{int(lab)}\n")
    return ("csv", path)


SPEC = register(AdapterSpec(
    name="catalogue.cluster",
    display_name="Dendrogram clustering (WindowSet -> Grouping)",
    stage="catalogue",
    category="cluster",
    page_name="Hierarchical cluster",
    params=[
        ParamSpec(
            "linkage", str, "ward",
            "Hierarchical linkage method. Ward is the recommended default for "
            "electrophysiological windows; average/complete/single remain "
            "available because the linkage choice is an open research decision.",
            choices=["ward", "average", "complete", "single"],
        ),
        ParamSpec(
            "k", int, 3,
            "Number of flat clusters to cut the dendrogram into.",
            min=2,
        ),
    ],
    run=_run,
    input_kind="windowset",
    output_kind="grouping",
    estimate=_estimate,
    derive=_derive,
    persist=_persist,
    description=(
        "Hierarchical clustering of a window set's attached feature matrix, "
        "returning one integer cluster label per window as a Grouping. "
        "Linkage and cluster count are exposed as parameters — the selection "
        "criterion is an open research decision and must stay tunable."
    ),
))
