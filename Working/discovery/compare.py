"""
compare.py
==========
Spec §7.7 ("Comparing two runs") and §7.8 ("Compare every stage") — the
headless half of the Compare view: what differs between two chains, where
the two runs fire, and how the two span sets overlap.

Three things are deliberately imported rather than written again:

- **The matching rule.** ``Working.discovery.matching.match_span_sets`` is
  §4.6 — reciprocal IoU *and* onset agreement scaled to the candidate. The
  older ``Working.compare.compare_run_sets`` cannot serve this view: it
  refuses a non-completed run, defaults to IoU 0.8 with no onset term, and
  takes run ids, which the human reference side does not have.
- **The recipe diff.** ``Working.compare.diff_recipes`` already answers
  "these two chains differ at step 2 in one parameter"; ``stage_diff`` only
  renders its result as JSON-safe dicts.
- **What a block is.** Roles come from the registry's *declared*
  ``category``/``input_kind``/``output_kind`` (``Adapters.base.AdapterSpec``),
  never from a glyph or a name match — a name match is how a mis-filed block
  ends up drawn in the wrong column with nobody noticing.

The five roles and their order are the client's ``ROLES`` constant
(``webui/client/src/fixtures/discovery.ts``); §7.7's prose lists them in a
different order and the frames draw a third, so the client's order is the one
that binds. ``'Score / estimate'`` carries spaces around its slash.

No UI import, no FastAPI, no browser type (rule 1): the bridge in
``webui/server/discovery.py`` is the only caller that knows a browser exists.
"""

from Working.compare import MISSING, diff_recipes
from Working.discovery.matching import match_span_sets

#: The client's five columns, in the client's order.
ROLES = ("Source", "Preprocess", "Score / estimate", "Encode", "Detect")

#: The sentinel `Working.compare.MISSING` rendered for the wire. The string is
#: what `_Missing.__repr__` already prints, so the two spellings cannot drift.
MISSING_TEXT = "<missing>"

#: `GlyphKind` in the client — the complete vocabulary. `glyph_for` may only
#: ever return one of these; a new picture is a client change first.
GLYPH_KINDS = ("human", "drop", "sax", "seed", "mp", "spike", "model",
               "threshold", "baseline", "noise", "source")

#: The generic glyph a role falls back to when a block has no specific one.
ROLE_GLYPH = {
    "Source": "source",
    "Preprocess": "baseline",
    "Score / estimate": "mp",
    "Encode": "sax",
    "Detect": "threshold",
}

#: Per-algorithm glyphs. Keyed by registry name so the mapping is checkable
#: against `discover_adapters()` rather than guessed from a display string.
#: 'noise' has no registered block of its own: the noise floor in this
#: codebase is dSAX's internal estimate, which draws as 'sax'.
ALGORITHM_GLYPH = {
    "human": "human",
    "preprocessing.detrend": "baseline",
    "preprocessing.bandpass": "baseline",
    "preprocessing.highpass": "baseline",
    "preprocessing.lowpass": "baseline",
    "preprocessing.surrogate": "noise",          # the control chain's null
    "preprocessing.wavelet_transform": "sax",
    "detection.matrix_profile": "mp",
    "detection.mp_motifs": "mp",
    "detection.sax_csax": "sax",
    "detection.sax_dsax": "sax",
    "detection.sax_psax": "sax",
    "detection.stage_encoding": "sax",
    "detection.symbol_search": "sax",
    "detection.freq_stft": "sax",
    "detection.wavelet_scattering": "sax",
    "detection.wavelet_summation": "mp",
    "detection.seed_matches": "seed",
    "detection.spike_v1": "spike",
    "detection.dehshibi_spikes": "spike",
    "detection.drop_detection": "drop",
    "detection.threshold": "threshold",
    "detection.summation_threshold": "threshold",
    "catalogue.classifier": "model",
    "catalogue.cnn_score": "model",
    "catalogue.cluster": "model",
    "catalogue.window_images": "sax",
    "catalogue.gramian_gasf": "sax",
    "catalogue.gramian_gadf": "sax",
    "catalogue.gramian_fusion": "sax",
    "catalogue.gramian_recurrence": "sax",
}

#: `Working.types.__all__` spelled as the interchange kinds are stored
#: (lower-case) so a signature reads 'Signal → SpanSet', not 'signal → spanset'.
_KIND_LABEL = {
    "encoding": "Encoding", "grouping": "Grouping", "model": "Model",
    "scores": "Scores", "signal": "Signal", "spanset": "SpanSet",
    "windowset": "WindowSet",
}


def qualified(step_or_name, stage=None):
    """The registry name for a step.

    The registry is keyed `"<stage>.<algorithm>"`; a recipe step carries the
    two apart (`{"stage": "detection", "algorithm": "threshold"}`). Passing the
    bare algorithm looks up nothing, and because `_spec_for` answers None for
    an unknown block — deliberately, so an old recipe still renders — the
    failure is silent: every role comes back None and Compare draws five absent
    cells over two chains that share nothing. Accepts a step dict, or a name
    with `stage` beside it, or an already-qualified name.
    """
    if isinstance(step_or_name, dict):
        name = step_or_name.get("algorithm") or ""
        stage = step_or_name.get("stage") or stage
    else:
        name = str(step_or_name or "")
    if "." in name or not stage:
        return name
    return f"{stage}.{name}"


def _spec_for(algorithm):
    """The registered `AdapterSpec`, or None for an algorithm this build does
    not have (an old recipe, or a block whose dependency failed to import).
    Compare must still render such a chain rather than raise."""
    from Adapters.registry import discover_adapters, get_adapter

    discover_adapters()
    try:
        return get_adapter(algorithm)
    except KeyError:
        return None


def role_of(spec):
    """Which of the five roles a registered block sits in — from its declared
    category and interchange types only.

    The order of the tests is the contract, and it is what makes the mapping
    single-valued: 'preprocess'/'control' first (a surrogate generator emits a
    Signal and would otherwise fall through to nothing), then 'scores' or a
    model, then the encodings, then span sets.

    Returns None for a block that fits none of the five (a clustering block
    emitting a Grouping, for instance) — the Compare columns simply have no
    place to draw it.
    """
    if spec is None:
        return None
    category = getattr(spec, "category", None)
    output_kind = getattr(spec, "output_kind", None)
    if category in ("preprocess", "control"):
        return "Preprocess"
    if output_kind == "scores" or category == "model":
        return "Score / estimate"
    if output_kind in ("encoding", "windowset"):
        return "Encode"
    if output_kind == "spanset":
        return "Detect"
    return None


def glyph_for(algorithm):
    """The client `GlyphKind` for one algorithm name.

    Explicitly mapped blocks get their own picture; anything else falls back
    to its role's generic glyph, and an algorithm with no role at all to
    'source' — the neutral one. Never a new kind: the client draws from a
    closed set and an unknown string would render as nothing at all.
    """
    glyph = ALGORITHM_GLYPH.get(algorithm)
    if glyph is not None:
        return glyph
    return ROLE_GLYPH.get(role_of(_spec_for(algorithm)), "source")


def _signature(spec):
    """'Signal → Scores' for one block, from its declared types. A block with
    side inputs says so ('Signal + exemplar → SpanSet'), because that is the
    difference between a seeded search and a bare detector."""
    if spec is None:
        return "? → ?"
    left = _KIND_LABEL.get(spec.input_kind, str(spec.input_kind))
    for side in getattr(spec, "side_inputs", None) or []:
        left += f" + {side.name}"
    right = _KIND_LABEL.get(spec.output_kind, str(spec.output_kind))
    return f"{left} → {right}"


def _format_value(name, value):
    """One parameter value as a human would say it.

    A `_s`/`_min`/`_h` suffix is a unit, and 600 seconds read as '600' is the
    kind of number a researcher has to convert in their head mid-comparison,
    so it is converted here instead.
    """
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (int, float)):
        seconds = None
        if name.endswith("_s"):
            seconds = float(value)
        elif name.endswith(("_min", "_minutes")):
            seconds = float(value) * 60.0
        elif name.endswith(("_h", "_hours")):
            seconds = float(value) * 3600.0
        if seconds is not None:
            if seconds >= 3600:
                return f"{_number(seconds / 3600)} h"
            if seconds >= 60:
                return f"{_number(seconds / 60)} min"
            return f"{_number(seconds)} s"
        return _number(value)
    return str(value)


def _number(value):
    """A float without its trailing zeros; an int unchanged."""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _label(name):
    """'window_s' -> 'window'. The unit is already in the value."""
    for suffix in ("_seconds", "_minutes", "_hours", "_min", "_s", "_h"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.replace("_", " ")


#: How many parameters a cell may name. Three fits the column; a chain row is
#: a reminder of what the step is, not its parameter sheet (the spec does not
#: fix a number, so this is the defensible default).
_MAX_PARAMS = 3


def _param_summary(step, spec):
    """A one-line parameter summary: 'window 5 min', 'cut 0.5'.

    The parameters a researcher set themselves come first — a value that
    differs from the adapter's default is the one carrying the decision. A
    step left entirely on its defaults still says something, so the adapter's
    leading ParamSpecs are used in that case.
    """
    params = dict(step.get("params") or {})
    specs = list(getattr(spec, "params", None) or [])
    defaults = {p.name: p.default for p in specs}
    order = [p.name for p in specs] + [n for n in params if n not in defaults]

    changed = [n for n in order if n in params and params[n] != defaults.get(n, object())]
    # A step on its defaults gets two parameters, not three: with nothing
    # chosen by a human there is no decision to show, and a longer line here
    # is the jargon dump the cell is meant to avoid.
    chosen = changed or [n for n in order if n in defaults][:2]
    parts = []
    for name in chosen[:_MAX_PARAMS]:
        value = params.get(name, defaults.get(name))
        parts.append(f"{_label(name)} {_format_value(name, value)}")
    return " · ".join(parts)


#: Above this many characters a cell name is abbreviated for the narrow
#: Compare column ('Symbolic encoding' -> 'Symbolic enc.').
_SHORT_AT = 18


def _short(name):
    """A narrow-column spelling, or None when the name already fits.

    A trailing parenthetical is the first thing to go — '(dSAX)', '(STUMPY)'
    and '(v1)' distinguish siblings in a list, not in a column that already
    names the algorithm underneath. Only if that is still too long is the
    last word abbreviated.
    """
    if len(name) <= _SHORT_AT:
        return None
    trimmed = name.split(" (")[0].rstrip()
    if len(trimmed) <= _SHORT_AT:
        return trimmed
    head, _, tail = trimmed.rpartition(" ")
    if not head or len(head) > _SHORT_AT:
        return trimmed[: _SHORT_AT - 1].rstrip() + "."
    return f"{head} {tail[:3]}."


def role_cells(recipe, *, source_label):
    """`{role: cell|None}` for all five roles — §7.7's "columns by role".

    A cell is
    ``{index, name, short, param, signature, glyph, algorithm, n_stages}``.
    Where a chain has two steps in one role the **last** wins (it is the one
    whose output leaves that role) and ``n_stages`` says how many there were,
    so the column can admit that it is showing one of two.

    The Source cell is always present — every chain has a source, and an empty
    first column would read as a missing stage rather than as the input.
    """
    cells = {role: None for role in ROLES}
    cells["Source"] = {
        "index": "●",
        "name": "Source",
        "short": None,
        "param": source_label,
        "signature": "— → Signal",
        "glyph": "source",
        "algorithm": "source",
        "n_stages": 1,
    }

    for position, step in enumerate(recipe.get("steps") or [], start=1):
        algorithm = qualified(step)
        spec = _spec_for(algorithm)
        role = role_of(spec)
        if role is None:
            # Either unregistered in this build or a block with no Compare
            # column (a Grouping, say). Drawing it in the wrong column would
            # be worse than leaving it out.
            continue
        name = getattr(spec, "page_name", None) or spec.display_name
        previous = cells[role]
        cells[role] = {
            "index": f"{position:02d}",
            "name": name,
            "short": _short(name),
            "param": _param_summary(step, spec),
            "signature": _signature(spec),
            "glyph": glyph_for(algorithm),
            "algorithm": algorithm,
            "n_stages": (previous["n_stages"] + 1) if previous else 1,
        }
    return cells


def compare_spans(a_spans, b_spans, *, rule=None):
    """Pair two span sets under §4.6, A as the candidate side.

    **Swapping the sides can change a borderline pair.** §4.6 scales the onset
    tolerance to the *candidate's* duration, so a long A against a short B is
    not the same question as the reverse. A is the candidate here; the caller
    decides which run that is and labels the columns accordingly.

    Returns ``{'pairs': [{a, b, iou}], 'only_a': [i], 'only_b': [j],
    'counts': {...}, 'rule': {...}}`` — indices into the input lists. The
    counts are symmetric (``a_total``/``b_total``/``both``/``only_a``/
    ``only_b``) so neither side is privileged in what the view totals.
    """
    matched = match_span_sets(list(a_spans), list(b_spans), rule=rule)
    pairs = [{"a": p["candidate"], "b": p["reference"], "iou": p["iou"],
              "onset_gap": p["onset_gap"]} for p in matched["pairs"]]
    only_a = list(matched["candidate_only"])
    only_b = list(matched["reference_only"])
    return {
        "pairs": pairs,
        "only_a": only_a,
        "only_b": only_b,
        "counts": {
            "a_total": len(pairs) + len(only_a),
            "b_total": len(pairs) + len(only_b),
            "both": len(pairs),
            "only_a": len(only_a),
            "only_b": len(only_b),
        },
        "rule": matched["rule"],
    }


def overlap_rows(per_channel, *, rule=None):
    """§7.7's set-overlap bars: one row per channel plus a pooled total.

    ``per_channel`` is ``[{'channel', 'a': [spans], 'b': [spans]}]``. The
    total is the sum of the per-channel counts, not a comparison of the
    concatenated span sets — spans from different channels are not comparable
    and pooling them first would invent matches across channels.
    """
    rows = []
    totals = {"onlyA": 0, "both": 0, "onlyB": 0}
    for entry in per_channel:
        counts = compare_spans(entry.get("a") or [], entry.get("b") or [],
                               rule=rule)["counts"]
        row = {
            "channel": entry.get("channel"),
            "onlyA": counts["only_a"],
            "both": counts["both"],
            "onlyB": counts["only_b"],
        }
        for key in totals:
            totals[key] += row[key]
        rows.append(row)
    rows.append({"channel": "all channels", **totals})
    return rows


def _wire(value):
    """`MISSING` as the string the client shows. Everything else untouched —
    a parameter's real None must stay None, which is the whole reason the
    sentinel exists."""
    return MISSING_TEXT if value is MISSING else value


def stage_diff(recipe_a, recipe_b):
    """`Working.compare.diff_recipes` rendered JSON-safe for the bridge.

    ``[{'index', 'a', 'b', 'changed': [{'name', 'a', 'b'}]}]``, one entry per
    differing chain position, with the `MISSING` sentinel turned into
    ``'<missing>'`` — a bridge route serialises this result directly.
    """
    rows = []
    for diff in diff_recipes(recipe_a, recipe_b):
        rows.append({
            "index": diff.index,
            "a": diff.a_step,
            "b": diff.b_step,
            "changed": [{"name": c.name, "a": _wire(c.a_value), "b": _wire(c.b_value)}
                        for c in diff.changed_params],
        })
    return rows
