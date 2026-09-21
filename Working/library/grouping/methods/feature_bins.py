"""
feature_bins.py
=================
Spec 8.2's second kind of basis: **"feature bins, no distance"**. Bins on ONE
feature — amplitude, timescale, frequency content or polarity — with the bin
method being one of exactly three: `quantiles`, `log-spaced`, `fixed edges`.

There is no tree and no distance here, which is the point: a researcher who
wants "the six frequency decades" is asking a question about a measurement,
not about similarity, and answering it with a clustering would hide the bin
edges the question was actually about. So `merge_heights` is empty, a member
carries no distance to a medoid, and the families are the bins themselves,
labelled by their edges.

A value outside every bin is omitted with reason `outside_bins` — spec 8.2's
first "what does not fit" case — never clipped into the nearest edge bin.
(The editor offers *unticking* "omit and flag motifs outside every bin",
which is that clipping; the engine's caller passes different bin edges for
that rather than this method quietly moving a member.)

The features themselves live in `Working/library/grouping/bases.py` and are
computed on demand, never stored (LIBRARY_STORAGE.md 3.4).
"""

from Working.library.grouping import bases
from Working.library.grouping.methods import FitResult, register


def _edge_label(lo, hi):
    """A bin's label is its own edges — the one honest name for a bin, and
    what the Atlas card needs to show instead of a meaningless `F-04`."""
    return f"{lo:g} – {hi:g}"


class FeatureBinsMethod:
    """Bins on one measured feature. No distance, no tree."""

    name = "feature_bins"
    label = "Feature bins"
    description = ("Bins on one measured feature — quantiles, log-spaced or "
                   "fixed edges. No distance is computed.")
    applies_to = ("amplitude", "timescale", "frequency-content", "polarity")

    params = {
        "feature": {
            "type": "str", "default": "amplitude", "label": "feature",
            "help": "which measured feature to bin; normally the basis itself.",
        },
        "bin_method": {
            "type": "choice", "default": bases.BIN_QUANTILES, "label": "bins",
            "help": f"one of {bases.BIN_METHODS} (spec 8.2 names exactly these).",
        },
        "count": {
            "type": "int", "default": 6, "label": "number of bins",
            "help": f"{bases.MIN_BINS} to {bases.MAX_BINS} bins; ignored for "
                    f"'fixed edges', where the edges given decide the count.",
        },
        "range": {
            "type": "range", "default": None, "label": "range",
            "help": "(lo, hi) for quantiles and log-spaced; for 'fixed edges' "
                    "it is the full increasing edge sequence instead.",
        },
    }

    def fit(self, values, *, params=None):
        """`values` is one feature value per item — the engine measures them,
        so this method never sees a waveform and never needs `fs`."""
        params = params or {}
        values = [float(v) for v in values]
        bin_method = params.get("bin_method", bases.BIN_QUANTILES)
        edges = bases.bin_edges(values, bin_method=bin_method,
                                count=params.get("count", 6),
                                range=params.get("range"))
        indices = bases.assign_bins(values, edges)
        labels = {k + 1: _edge_label(edges[k], edges[k + 1])
                  for k in range(len(edges) - 1)}
        return FitResult(
            method=self.name, n=len(values), family_labels=labels,
            payload={"edges": edges, "bins": indices, "values": values,
                     "bin_method": bin_method,
                     "feature": params.get("feature")},
        )

    def assign(self, fit, *, cut=None):
        """Family id = bin number, 1-based. `cut` is accepted and ignored:
        bin edges do the work a cut does for a distance basis, and refusing
        the argument would make the engine special-case this method."""
        fit.omit_reasons.clear()
        out = []
        for i, index in enumerate(fit.payload["bins"]):
            if index is None:
                fit.omit_reasons[i] = "outside_bins"
                out.append(None)
            else:
                out.append(index + 1)
        return out

    def merge_heights(self, fit):
        """No tree, so nothing to draw a cut on. The editor draws the
        feature's own distribution (`bases.distribution`) instead."""
        return []


register(FeatureBinsMethod())
