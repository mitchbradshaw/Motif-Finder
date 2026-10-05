"""The drawing standard: which picture a block gets, from its type signature alone
(fixup-h, `docs/BLOCK_INTEGRATION.md` §2, QUESTIONS.md Round 7).

    The OUTPUT type decides what kind of picture you get. The INPUT type decides
    what one "thing" is in that picture, and whether there is a before/after.

So there are seven **type views**, keyed on the output type, and thirteen
**modifiers**, keyed on the conversion ``input->output``. A block names neither:
both are read off its ``AdapterSpec`` here and ride on its catalog card, and the
client holds a component for every key (``analyse/views/registry.tsx``;
``tests/test_block_standard.py`` checks the two tables against each other).

A conversion nobody has written yet still resolves: it gets its output type's view
and no modifier. Registering a block whose conversion is new fails the standard's
test until a row is added here - one line, on purpose, because what the input
contributes to the picture is a decision and not a default.

Each value is the view's *minimum*, as decided with the researcher: the first
sentence is the settings page, the second the chain thumbnail.
"""
from __future__ import annotations

VIEWS: dict[str, str] = {
    "signal": "Before and after overlaid, the input grey beneath; both axes when the block changes the scale. "
              "Thumbnail: the overlaid plot.",
    "scores": "The score curve, the source signal above it on the same x, the value histogram, the threshold if one exists. "
              "Thumbnail: the scores plot alone.",
    "spanset": "The slideshow of spans, every span marked on the full trace, a duration distribution. "
               "Thumbnail: every span marked on the full trace.",
    "encoding": "Three sampled images and a scan through the rest, a colour bar carrying the real value range, no-data in grey. "
                "Thumbnail: three images side by side.",
    "windowset": "The windows on the time axis and the feature matrix as a heatmap. "
                 "Thumbnail: the heatmap on the source signal's time axis, grey where no window.",
    "grouping": "Clusters over time, cluster sizes, one exemplar drawn per cluster. "
                "Thumbnail: the distribution of clusters over time as a heatmap.",
    "model": "Accuracy per class as bars. Thumbnail: a card.",
}

MODIFIERS: dict[str, str] = {
    "signal->signal": "before/after overlay; dual axes when the scale changes",
    "signal->scores": "the source signal above the curve, same x",
    "encoding->scores": "the image above, the curve below, same x, the summed band marked on the image",
    "scores->spanset": "the cut drawn on the score curve, draggable",
    "encoding->spanset": "which cells/symbols fired, marked on the encoding itself",
    "signal->spanset": "spans on the trace - no intermediate exists to show",
    "spanset->spanset": "the features, not the spans: a histogram per measure, plus the rose",
    "signal->encoding": "three sampled images and which chunk of signal each came from",
    "windowset->encoding": "three sampled images and which window each is",
    "signal->windowset": "a feature matrix draws as a heatmap; a set with no features draws its windows by train / validation / test",
    # fixup-ag: Trace shape, the first WindowSet -> WindowSet block
    "windowset->windowset": "the windows before and after: what was kept, what was left out and why, and the measure each window now carries",
    "windowset->grouping": "clusters over time and one exemplar per cluster",
    "grouping->model": "accuracy per class",
}


def resolve_kinds(input_kind: str, output_kind: str) -> dict:
    """``{"view", "modifier"}`` for a conversion. The view always resolves for a
    known output type; the modifier is ``None`` for a conversion with no row."""
    for kind in (input_kind, output_kind):
        if kind not in VIEWS:
            raise ValueError(f"{kind!r} is not an interchange type; known: {sorted(VIEWS)}")
    key = f"{input_kind}->{output_kind}"
    return {"view": output_kind, "modifier": key if key in MODIFIERS else None}


def resolve(spec) -> dict:
    """The view and modifier of one registered block, read off its spec."""
    return resolve_kinds(spec.input_kind or "signal", spec.output_kind)
