"""
labels.py
===========
Spec 8.2's third kind of basis: **labels** — one group per label. The bases
are `tag` (the morphology tags on an entry), `provenance` (recording, run or
spike train) and `custom` (a clustering exported from Analyse).

Nothing is computed. PIPELINE_PRD.md Part 2 is explicit about why this is a
first-class grouping and not a filter: provenance *"is already exact in the
seed data and requires no computation"*, and shape and provenance are *"two
independent axes, not conflated … the finding is only visible when both
exist and can be seen to disagree."* A label grouping is how the second axis
gets drawn.

A member with no label is **omitted with reason `no_label`**, not collected
into an "(unlabelled)" group. An absent tag is an absence of evidence; a
group named after it would be read as a family, and a family of things that
happen to be untagged is not a finding.
"""

from Working.library.grouping.methods import FitResult, register


class LabelsMethod:
    """One group per label, in sorted label order."""

    name = "labels"
    label = "One group per label"
    description = ("One group per label — tags, provenance (recording, run or "
                   "spike train), or a clustering exported from Analyse.")
    applies_to = ("tag", "provenance", "custom")

    params = {
        "provenance_by": {
            "type": "choice", "default": "recording", "label": "provenance by",
            "help": "recording | run | spike_train — which provenance field "
                    "is the label. Only read for the `provenance` basis.",
        },
        "tag_mode": {
            "type": "choice", "default": "first", "label": "tag",
            "help": "first | each — whether an entry with several tags takes "
                    "its first tag or joins every matching group. Only read "
                    "for the `tag` basis, and applied by the engine, which is "
                    "what owns the item dicts.",
        },
    }

    def fit(self, labels, *, params=None):
        """`labels` is one label per item — a string, or `None`/`''` for an
        item that carries none. The engine extracts them from the item dicts,
        so which field is the label is the engine's business, not this
        method's."""
        labels = [None if lab is None or lab == "" else str(lab)
                  for lab in labels]
        distinct = sorted({lab for lab in labels if lab is not None})
        ids = {lab: k + 1 for k, lab in enumerate(distinct)}
        return FitResult(
            method=self.name, n=len(labels),
            family_labels={fid: lab for lab, fid in ids.items()},
            payload={"labels": labels, "ids": ids},
        )

    def assign(self, fit, *, cut=None):
        """A family id per row; `None`, reason `no_label`, for an item with
        no label. `cut` is accepted and ignored — there is no tree to cut."""
        fit.omit_reasons.clear()
        ids = fit.payload["ids"]
        out = []
        for i, lab in enumerate(fit.payload["labels"]):
            if lab is None:
                fit.omit_reasons[i] = "no_label"
                out.append(None)
            else:
                out.append(ids[lab])
        return out

    def merge_heights(self, fit):
        """Labels build no tree."""
        return []


register(LabelsMethod())
