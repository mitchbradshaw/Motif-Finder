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

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.types.windowset import BOOKKEEPING_COLUMNS
from Working.types import Grouping

# Where `persist` writes a run's labels. Module-level so the bridge's sandbox
# runtime can redirect it (same pattern as the matrix-profile and window-matrix
# adapters' RESULTS_DIR); read by name at call time.
RESULTS_DIR = os.path.join("DATA", "derived", "groupings")


#: the label a window gets when it is not clustered: the "excluded" value `catalogue.manual_labels`
#: already gives and `catalogue.classifier` already skips (cluster labels themselves start at 1)
NO_LABEL = -1


def _cluster_window_set(window_set, linkage, k):
    """Run the two dendrogram stages and return `(ClusterResult, PreprocessResult, keep)` —
    the second so the meta can name the columns actually clustered on; `keep` marks the windows
    clustered. A window whose features are ALL NaN once the bookkeeping columns are dropped (a
    feature block left it out: a gap, a flat window) is never imputed and clustered as if it were
    an average window (w3-a fix round 1): it is left out, labelled `NO_LABEL`, and counted."""
    if window_set is None:
        raise ValueError(
            "catalogue.cluster requires a WindowSet input from a prior step "
            "(input_kind='windowset')."
        )
    if window_set.n_windows == 0:
        # w2-a: an empty set is the step before's finding (e.g. Event windows found no
        # events), not a missing feature matrix — say so, and send the reader there
        raise ValueError(
            "catalogue.cluster: no windows to cluster: the step before produced none — "
            "see its meta for why."
        )
    features = window_set.features
    if features is not None:
        # The train/validation/test assignment `preprocessing.sliding_windows`
        # rides on the window set (P12) is metadata, never a feature: a
        # clustering that saw it would recover the split as a cluster. The same
        # holds for the rest of the WindowSet contract's bookkeeping list
        # (`Working.types.windowset.BOOKKEEPING_COLUMNS`: time orders, geometry,
        # identifiers, the detector's own score).
        features = features.drop(columns=[c for c in BOOKKEEPING_COLUMNS if c in features.columns])
    if features is None or features.shape[0] == 0 or features.shape[1] == 0:
        raise ValueError(
            "catalogue.cluster requires a WindowSet with an attached feature "
            "matrix, one row per window; the bookkeeping columns "
            f"({', '.join(BOOKKEEPING_COLUMNS)}) are not features."
        )
    keep = ~features.isna().all(axis=1).to_numpy()
    if not keep.any():
        raise ValueError(
            f"catalogue.cluster: every one of the {len(features):,} windows has no features (all blank): the "
            "step before left them all out — see its meta for why.")
    features = features.loc[keep].reset_index(drop=True)
    if k > len(features):
        raise ValueError(
            f"k={k} exceeds the number of windows ({len(features)}"
            + (f", after {int((~keep).sum()):,} windows with no features were left out" if not keep.all() else "")
            + ") — cannot cut more clusters than there are leaves."
        )

    from Working.Catalogue.dendrogram.dendrogram_cluster import (
        cluster_window_matrix,
        preprocess_window_matrix,
    )

    preprocessed = preprocess_window_matrix(features)
    return cluster_window_matrix(preprocessed, method=linkage, n_clusters=k), preprocessed, keep


def _full_labels(cluster, keep):
    """One label per window of the set: the cluster's for the clustered ones, `NO_LABEL` for the rest."""
    import numpy as np
    labels = np.full(len(keep), NO_LABEL, dtype=np.int64)
    labels[keep] = np.asarray(cluster.labels, dtype=np.int64)
    return labels


def _opt_float(v):
    return None if v is None or not np.isfinite(v) else float(v)


def _run(x, t, fs, linkage="ward", k=3, value=None):
    from Working.Catalogue.dendrogram.dendrogram_cluster import correlation_filter_note
    cluster, preprocessed, keep = _cluster_window_set(value, linkage, k)
    n_total = int(len(keep))
    n_left = int((~keep).sum())
    reason = (f"{n_left:,} of {n_total:,} windows have no features (every feature blank: the step before left "
              f"them out) and were not clustered: label {NO_LABEL}") if n_left else None
    summary = f"{int(keep.sum()):,} of {n_total:,} windows clustered into {k}"
    if n_left:
        summary += f" · {n_left:,} of {n_total:,} with no features left out (label {NO_LABEL})"
    return AdapterResult(
        output_kind="grouping",
        value=Grouping(labels=_full_labels(cluster, keep)),
        meta={
            "linkage": linkage,
            "k": k,
            "cluster_counts": cluster.cluster_counts,
            "n_windows": n_total,
            "n_clustered": int(keep.sum()),
            "n_left_out": n_left,
            "left_out_reason": reason,
            "summary": summary,
            "n_features": cluster.n_features,
            # w2-a fix round 1: k clusters are always cut, so noise and structure read alike
            # without a quality figure. Outputs, not params: no recipe hash moves.
            "silhouette": _opt_float(cluster.silhouette),
            "cophenetic_r": _opt_float(cluster.cophenetic_r),
            "feature_names": [str(c) for c in preprocessed.feature_names],
            # w2-c: whether the feature clean-up's correlation filter ran (skipped above
            # 2,000 columns); read off the preprocessing result W2-A's tuple carries
            "correlation_filter": correlation_filter_note(preprocessed),
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

    cluster, _, keep = _cluster_window_set(value, params["linkage"], params["k"])
    sizes = ", ".join(
        str(cluster.cluster_counts[label])
        for label in sorted(cluster.cluster_counts)
    )
    rows = [
        ("Clusters requested", str(params["k"]), ""),
        ("Windows clustered", str(cluster.n_windows), ""),
        ("Cluster sizes", sizes, ""),
    ]
    if not keep.all():
        rows.append(("Left out", f"{int((~keep).sum()):,} windows with no features", "warn"))
    return rows


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
