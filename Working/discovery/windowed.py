"""
windowed.py
===========
Round A_2, P3 — detection over sliding windows with overlap (the researcher, 2026-10-17: "drop detection should run
over sliding windows with overlap. Looking only at the whole-span scale risks missing events").

Most detectors set their bar from the span they are given: the drop detector's slope floor and depth gate, the noise
threshold's sigma_n, SAX's cutlines. On a 721-hour recording a loud week sets the bar for a quiet hour. A **window
scope** runs the chain over windows instead, each judged on its own scale, and **stitches** the windows' detections
into one result with nothing counted twice.

    scope = {"kind": "windows", "window_s": 3600.0, "overlap_frac": 0.5, "fit": False}

* **Windows** start every ``window_s x (1 - overlap)``; the last one is moved back to end at the section end, so
  every window has the same length (one scale, one version of the algorithm). Each window is one target per channel
  through the ordinary fan-out (`fanout.plan`'s ``windows`` targets, `run_groups.materialize_target`), so every
  window is a normal run over its own span: cached, and reused when the scope is applied again.
* **The bound.** A window is at least `CONTEXT_MULTIPLE` x the chain's longest *context* window (a block that reads a
  stretch of signal around each point: a rolling mean, a baseline, a subsequence, a filter's period — near a window's
  edge it sees half of it, so a quarter of each window at most is distorted), or one whole *piece* of a block that
  cuts its input into consecutive pieces and treats each on its own (the Dehshibi scalogram's 3000 s pieces, SAX
  segments, Sliding windows): an outer window's edge is then one more piece boundary. A shorter window is refused,
  naming the step. `INTERNAL_WINDOWS` says which parameter of which block is which; a block it does not list reads no
  fixed stretch around a point (`NO_INTERNAL_WINDOW`), and `tests/test_windowed_detection.py` holds every registered
  preprocessing and detection block to one of the two lists.
* **Fit**, the explicit opt-in: every internal window over the bound is scaled down to it (a 600 s rolling mean in
  10-minute windows becomes 150 s). That is a different chain — the scaled parameters are in the recipe, so the scale
  is its own row on the Map and its own algorithm version.
* **Stitching** (`stitch`): detections from different windows that are the same event under Compare's matching rule
  (`Working.discovery.matching`, reciprocal IoU and onset agreement) are one event; an event is kept when one of its
  detections has its onset in that detection's own window's **core** (the part of the timeline nearer the window's
  centre than any other window's: the overlap with each neighbour split at its middle, the first and last windows
  keeping their outer edges), and it is drawn as the detection the window edge did not cut and that sits most
  centrally in its window. Each kept span names the window that produced it. `RULES` is the rule in words.
* **One stitched run per channel** (`write_stitched`): a `runs` row over the section whose detections are the stitched
  set, its recipe the chain plus the scope and the stitch rule (so it is never mistaken for a run of the chain over
  the whole section — `execute_recipe` refuses it), its provenance in `stitched_windows`. A Discovery run is made of
  the stitched runs, so Runs, Compare, Review, the Scoreboard and the Map read the stitched set unchanged; the Map's
  row key takes the window scope (`detection_map.steps_key`).
* **The null:** each window draws its own (Settings › Nulls, down to 1); draw j of every window is stitched by the same
  rule into the stitched run's draw j, linked by `surrogate_of_run_id` like any draw.
* **What each window fitted** (sigma, cutlines, the drop detector's slope floor) is kept per window run in
  `window_fits`, from the blocks' own `meta`.

Why not `preprocessing.sliding_windows`: that block makes a WindowSet for training (a blocked train/test split, no
overlap by design); here each window is a whole run of a detection chain. Why not `compare.union_span_sets`: it
de-duplicates band runs that all cover the same stretch; windows cover different stretches, and a window's verdict
on its own core must be able to drop another window's detection there.

No UI imports.
"""

import copy
import datetime as _dt
import json
import math
import time

KIND = "windows"
DEFAULT_OVERLAP = 0.5
MIN_OVERLAP = 0.0
MAX_OVERLAP = 0.9
#: a context window's edges distort about half of it, so 4 x keeps that to a quarter of each window
CONTEXT_MULTIPLE = 4
STITCH_VERSION = 1
#: Seconds of bookkeeping per run on top of the chain itself — the run row, its config, its detections, a database
#: opened per run. Measured on this machine (2026-10-18, a2-p3): 0.33 s for a computed noise-threshold window of
#: 600-3,600 samples. A windowed application is thousands of runs, so this floor, not the blocks' own estimates
#: (most declare none), is what decides whether it can run here.
RUN_OVERHEAD_S = 0.33

TRADE_OFF = ("Each window sets its own thresholds: a quiet window finds weaker events than the whole-span run would, "
             "and a busy one finds fewer.")

_RULE_TEXT = [
    ("windows", "The section is cut into windows of the chosen length, a new one every length x (1 - overlap); the "
                "last window is moved back to end at the section end, so every window has the same length. Each "
                "window is an ordinary run of the chain over its own span."),
    ("core", "Each window owns its core: the part of the timeline nearer its centre than any other window's (the "
             "overlap with each neighbour is split at its middle); the first window's core starts at the section "
             "start and the last one's ends at the section end. An event counts when one of its detections has its "
             "onset in its own window's core: that window, which sees the stretch most centrally, decides whether "
             "it is there."),
    ("duplicates", "Detections from different windows are one event when they match under Compare's rule: "
                   "reciprocal overlap IoU at least {iou:g} and onsets within {onset:g} x the duration. An event is "
                   "kept once, drawn as the detection that no window edge cut and that sits most centrally in its "
                   "window."),
    ("provenance", "Every kept span records the window that produced it (its index, span and run), the window whose "
                   "core holds its onset, and every window that also found it."),
    ("refit", "Each window sets its own thresholds (noise level, cutlines, slope floor and depth gates are fitted to "
              "the window): a quiet window finds weaker events than the whole-span run would, and a busy one finds "
              "fewer. What each window fitted is kept with its run."),
    ("bound", "A window is at least 4 x the chain's longest context window (a rolling mean, a baseline, a "
              "subsequence, a filter's period: near an edge the block sees half of it) or one whole piece of a "
              "block that cuts its input into pieces. Fitting the chain to a shorter window scales those windows "
              "down: a different chain, its own row on the Map. Running it as it is in a shorter window is an "
              "explicit choice, and the run says so."),
    ("null", "Each window draws its own null (Settings › Nulls); draw j of every window is stitched by the same rule "
             "into the stitched run's draw j."),
]


def rules_for(rule=None):
    """`meta["rules"]` for a stitch under ``rule`` (the matching rule: Settings › Analysis defaults)."""
    from Working.discovery.matching import normalise_rule

    r = normalise_rule(rule)
    return [{"name": n, "rule": t.format(iou=r["iou"], onset=r["onset"])} for n, t in _RULE_TEXT]


RULES = rules_for()


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def fmt_duration(seconds):
    """A length the way the page says it: 40 s, 10 min, 2.5 min, 1 h, 5.5 h."""
    s = float(seconds)
    if s < 60:
        return f"{s:.4g} s"
    if s < 3600:
        return f"{round(s / 60.0, 1):g} min"
    return f"{round(s / 3600.0, 1):g} h"


# ── the scope ───────────────────────────────────────────────────────────────

def normalize_scope(scope):
    """``{"kind": "windows", "window_s", "overlap_frac", "fit"}``, checked: a positive length, an overlap in
    [0, 0.9] (0.5 when not given: recommended), ``fit`` the opt-in that scales the chain to the window.

    ``allow_short`` (present only when True, and never beside ``fit``) is the other opt-in: keep the chain as it is
    in a window shorter than its bound, the run carrying the bound's warning — what the edges distort is the
    researcher's to judge (round A_2, P3: the 10-minute decision, RQ4b)."""
    if not isinstance(scope, dict):
        raise ValueError(f"a window scope is a dict with window_s and overlap_frac, got {scope!r}")
    kind = scope.get("kind", KIND)
    if kind != KIND:
        raise ValueError(f"a window scope's kind is {KIND!r}, got {kind!r}")
    try:
        window_s = float(scope.get("window_s"))
    except (TypeError, ValueError):
        raise ValueError(f"a window scope needs a numeric window_s (seconds), got {scope.get('window_s')!r}") from None
    if not math.isfinite(window_s) or window_s <= 0:
        raise ValueError(f"a window's length must be positive, got {window_s:g} s")
    raw = scope.get("overlap_frac")
    try:
        overlap = DEFAULT_OVERLAP if raw is None else float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"overlap_frac must be a number between {MIN_OVERLAP} and {MAX_OVERLAP}, got {raw!r}") from None
    if not (MIN_OVERLAP <= overlap <= MAX_OVERLAP):
        raise ValueError(f"overlap_frac must lie between {MIN_OVERLAP:g} and {MAX_OVERLAP:g} (0.5 is recommended), "
                         f"got {overlap:g}")
    out = {"kind": KIND, "window_s": window_s, "overlap_frac": overlap, "fit": bool(scope.get("fit", False))}
    if scope.get("allow_short") and not out["fit"]:
        out["allow_short"] = True
    return out


def scope_label(scope):
    """``1 h windows · 50 %`` (``· fitted`` when the chain was fitted to it)."""
    s = normalize_scope(scope)
    out = f"{fmt_duration(s['window_s'])} windows · {round(s['overlap_frac'] * 100):g} %"
    return out + (" · fitted" if s["fit"] else " · as is, warned" if s.get("allow_short") else "")


# ── the windows ─────────────────────────────────────────────────────────────

def window_samples(window_s, fs):
    return max(1, int(round(float(window_s) * float(fs))))


def step_samples(n_window, overlap_frac):
    return max(1, int(round(int(n_window) * (1.0 - float(overlap_frac)))))


def window_spans(start, end, n_window, overlap_frac):
    """The windows of ``[start, end)``: ``n_window`` samples each, a new one every ``n_window x (1 - overlap)``, the
    last moved back to end at ``end``. Empty when the section is shorter than one window."""
    start, end, n_window = int(start), int(end), int(n_window)
    if n_window <= 0 or end - start < n_window:
        return []
    step = step_samples(n_window, overlap_frac)
    out, s = [], start
    while s + n_window < end:
        out.append((s, s + n_window))
        s += step
    out.append((end - n_window, end))
    return out


def window_cores(spans, start, end):
    """Each window's core: the overlap with each neighbour split at its middle; the first core starts at ``start``,
    the last ends at ``end``. The cores tile ``[start, end)`` once."""
    if not spans:
        return []
    bounds = [int(start)] + [(int(spans[k][0]) + int(spans[k - 1][1])) // 2 for k in range(1, len(spans))] + [int(end)]
    return [(bounds[k], bounds[k + 1]) for k in range(len(spans))]


# ── the bound: each block's internal windows ─────────────────────────────────

def _w(param, kind, unit="s", when=None, fittable=True):
    return {"param": param, "kind": kind, "unit": unit, "when": when, "fittable": fittable}


#: block -> the parameters that set a stretch of signal it works over. ``kind``: ``context`` (it reads that stretch
#: around each point; near a span's edge it sees half of it) or ``piece`` (it cuts its input into consecutive pieces
#: of that length and treats each on its own). ``unit``: how the value reads in seconds (``s``; ``min`` x 60;
#: ``samples`` / fs; ``spike_width``: a local average over 4w+1 samples; ``period``: 1 / a cutoff in Hz; ``pow2``:
#: 2^J samples; ``swt``: a stationary wavelet layer's filter support; ``fixed:<s>``: a length the block does not
#: expose). ``when``: the parameter only applies then.
INTERNAL_WINDOWS = {
    "preprocessing.detrend": [_w("window_s", "context", when=lambda p: p.get("mode") != "linear")],
    "preprocessing.beads": [_w("baseline_period_s", "context")],
    "preprocessing.decompose": [_w("baseline_window_s", "context")],
    "preprocessing.highpass": [_w("cutoff_hz", "context", "period", fittable=False)],
    "preprocessing.bandpass": [_w("low_hz", "context", "period", fittable=False)],
    "preprocessing.lowpass": [_w("cutoff_hz", "context", "period", fittable=False)],
    "preprocessing.wavelet_bands": [_w("level", "context", "swt", fittable=False)],
    "preprocessing.wavelet_transform": [_w("window_s", "piece")],
    "preprocessing.sliding_windows": [_w("window_s", "piece")],
    "preprocessing.window_matrix": [_w("window_min", "piece", "min")],
    "detection.summation_threshold": [_w("window_s", "piece", when=lambda p: not p.get("slice_by_state"))],
    "detection.dehshibi_spikes": [_w("(its 3000 s pieces)", "piece", "fixed:3000", fittable=False)],
    "detection.deconvolve": [_w("baseline_window_s", "context", when=lambda p: float(p.get("baseline_window_s") or 0) > 0)],
    "detection.noise_threshold": [_w("noise_window_s", "context", when=lambda p: p.get("noise_from") == "rolling")],
    "detection.cwt_ridges": [_w("max_scale_s", "context"), _w("noise_window_s", "context")],
    "detection.fluss": [_w("window_s", "context")],
    "detection.matrix_profile": [_w("window_min", "context", "min")],
    "detection.mp_motifs": [_w("window_min", "context", "min", when=lambda p: float(p.get("window_min") or 0) > 0)],
    "detection.pan_matrix_profile": [_w("max_window_s", "context")],
    "detection.freq_stft": [_w("window_size", "context", "samples")],
    "detection.wavelet_scattering": [_w("J", "context", "pow2", fittable=False)],
    "detection.stage_encoding": [_w("segment_seconds", "piece")],
    "detection.sax_dsax": [_w("seconds_per_symbol", "piece")],
    "detection.sax_csax": [_w("seconds_per_symbol", "piece")],
    "detection.sax_psax": [_w("seconds_per_symbol", "piece")],
    "detection.spike_v1": [_w("width", "context", "spike_width")],
    "detection.seed_matches": [_w("exemplar", "context", "exemplar", fittable=False)],
    "catalogue.multiscale_entropy": [_w("scale_max_s", "context")],
}

#: Blocks that read no fixed stretch of signal around a point: thresholds, gates and measures of the spans handed to
#: them (the drop detector's windows are multiples of each fall's own duration), whole-span fits (a rupture
#: segmentation), and the blocks that score the windows a WindowSet already holds.
NO_INTERNAL_WINDOW = frozenset({
    "preprocessing.invert", "preprocessing.surrogate", "preprocessing.trace_shape", "preprocessing.window_pool",
    "detection.threshold", "detection.signal_threshold", "detection.drop_detection", "detection.impulse_events",
    "detection.symbol_search", "detection.wavelet_summation", "detection.rupture",
})


def _adapter(name):
    from Adapters.registry import discover_adapters, get_adapter

    try:
        return get_adapter(name)
    except KeyError:
        discover_adapters()
        return get_adapter(name)


def _name(step):
    return f"{step['stage']}.{step['algorithm']}"


def _swt_support(params, fs):
    """Samples a stationary wavelet layer reads: the cascade of its filters, (L - 1)(2^level - 1) + 1; the residual
    (level 0) at the depth the block decomposes to when it reaches its 0.001 Hz floor."""
    lengths = {"haar": 2, "db2": 4, "db4": 8, "db8": 16, "sym4": 8, "sym8": 16, "coif2": 12}
    dec_len = lengths.get(str(params.get("wavelet") or "db4"), 8)
    level = int(params.get("level") or 0)
    if level <= 0:
        level = int(params.get("levels") or 0) or max(1, int(math.ceil(math.log2(float(fs) / 0.002))))
    return (dec_len - 1) * (2 ** level - 1) + 1


def _seconds(entry, params, fs, step):
    unit, v = entry["unit"], params.get(entry["param"])
    if unit == "s":
        return float(v)
    if unit == "min":
        return float(v) * 60.0
    if unit == "samples":
        return float(v) / float(fs)
    if unit == "spike_width":
        return (4.0 * float(v) + 1.0) / float(fs)
    if unit == "period":
        return 1.0 / float(v) if v else None
    if unit == "pow2":
        return (2.0 ** int(v)) / float(fs)
    if unit == "swt":
        return _swt_support(params, fs) / float(fs)
    if unit == "exemplar":
        b = ((step.get("side_inputs") or {}).get("exemplar") or {})
        if b.get("start_idx") is None or b.get("end_idx") is None:
            return None
        return (int(b["end_idx"]) - int(b["start_idx"])) / float(fs)
    if unit.startswith("fixed:"):
        return float(unit.split(":", 1)[1])
    raise ValueError(f"unknown internal-window unit {unit!r}")


def _to_param(entry, seconds, fs):
    """The parameter value (in its own unit) that makes the window ``seconds`` long, rounded so it never exceeds it."""
    unit = entry["unit"]
    if unit == "s":
        return float(seconds)
    if unit == "min":
        return float(seconds) / 60.0
    if unit == "samples":
        return int(math.floor(float(seconds) * float(fs)))
    if unit == "spike_width":
        return int(math.floor((float(seconds) * float(fs) - 1.0) / 4.0))
    raise ValueError(f"a {unit} window cannot be fitted")


def internal_windows(steps, fs):
    """Every internal window of the chain at ``fs``: ``[{step, name, label, param, seconds, kind, minimum_s,
    fittable}]``, in chain order. ``minimum_s`` is what it asks of an outer window."""
    out = []
    for i, st in enumerate(steps):
        name = _name(st)
        entries = INTERNAL_WINDOWS.get(name)
        if not entries:
            continue
        spec = _adapter(name)
        params = spec.validate_params(st.get("params"))
        for e in entries:
            if e["when"] is not None and not e["when"](params):
                continue
            sec = _seconds(e, params, fs, st)
            if sec is None or not math.isfinite(sec) or sec <= 0:
                continue
            mult = CONTEXT_MULTIPLE if e["kind"] == "context" else 1
            out.append({"step": i, "name": name, "label": spec.page_name or spec.display_name or name,
                        "param": e["param"], "unit": e["unit"], "seconds": float(sec), "kind": e["kind"],
                        "minimum_s": float(sec) * mult, "fittable": bool(e["fittable"])})
    return out


def minimum_window(steps, fs):
    """The internal window that sets the chain's minimum outer window (the first, on a tie), or None."""
    best = None
    for w in internal_windows(steps, fs):
        if best is None or w["minimum_s"] > best["minimum_s"] + 1e-9:
            best = w
    return best


def _describe(w):
    """``step 01 (Detrend, preprocessing.detrend: window_s 600 s (10 min) — a stretch it reads around ...)``."""
    p = w["param"]
    if p.startswith("("):
        val = p.strip("()")
    elif w["unit"] == "s":
        val = f"{p} {w['seconds']:g} s" + (f" ({fmt_duration(w['seconds'])})" if w["seconds"] >= 60 else "")
    else:
        val = f"{p}, {fmt_duration(w['seconds'])}"
    what = ("a stretch it reads around every point: near a window's edge it sees half of it, so a window needs 4 x"
            if w["kind"] == "context" else
            "the pieces it cuts its input into, each treated on its own: a window needs one whole piece")
    return f"step {w['step'] + 1:02d} ({w['label']}, {w['name']}: {val} — {what})"


def bound_refusal(steps, fs, window_s):
    """None when ``window_s`` is long enough for the chain, else the refusal in words, naming the step."""
    m = minimum_window(steps, fs)
    if m is None or float(window_s) >= m["minimum_s"] - 1e-9:
        return None
    return (f"a {fmt_duration(window_s)} window is shorter than this chain allows: {_describe(m)} sets the minimum "
            f"at {fmt_duration(m['minimum_s'])}. Choose {fmt_duration(m['minimum_s'])} or longer, or tick “fit the "
            f"chain's internal windows to this window length” — a different chain, scaled to the window, its own "
            f"row on the Map — or “run it as it is”, its edges distorted and the run saying so")


def fit_steps(steps, fs, window_s):
    """``(steps, changes)``: every internal window over the bound scaled down to it (a context window to a quarter
    of ``window_s``, a piece to ``window_s``); ``changes`` lists ``{step, name, param, from, to}``. Raises
    ValueError, naming the step, when a window cannot be fitted (a filter edge, a wavelet level, an exemplar) or the
    fitted value is under the block's own minimum."""
    out = copy.deepcopy(list(steps))
    changes = []
    for w in internal_windows(steps, fs):
        allowed = float(window_s) / (CONTEXT_MULTIPLE if w["kind"] == "context" else 1)
        if w["seconds"] <= allowed + 1e-9:
            continue
        where = f"step {w['step'] + 1:02d} ({w['label']}, {w['name']})"
        if not w["fittable"]:
            raise ValueError(f"{where}: its {w['param']} ({fmt_duration(w['seconds'])}) is part of what the chain "
                             f"looks for and is not fitted to a window; a {fmt_duration(window_s)} window cannot "
                             f"hold it — choose at least {fmt_duration(w['minimum_s'])}")
        entry = next(e for e in INTERNAL_WINDOWS[w["name"]] if e["param"] == w["param"])
        to = _to_param(entry, allowed, fs)
        spec = _adapter(w["name"])
        ps = next(p for p in spec.params if p.name == w["param"])
        if (ps.min is not None and to < ps.min) or (isinstance(to, int) and to < 1) or to <= 0:
            raise ValueError(f"{where}: fitted to a {fmt_duration(window_s)} window its {w['param']} would be {to:g}, "
                             f"under the block's minimum ({ps.min:g}); this window is too short for this chain even "
                             f"fitted" if ps.min is not None else
                             f"{where}: fitted to a {fmt_duration(window_s)} window its {w['param']} would be {to:g}; "
                             f"this window is too short for this chain even fitted")
        params = out[w["step"]].setdefault("params", {})
        before = spec.validate_params(steps[w["step"]].get("params"))[w["param"]]
        params[w["param"]] = to
        changes.append({"step": w["step"], "name": w["name"], "param": w["param"], "from": before, "to": to})
    if changes:
        left = bound_refusal(out, fs, window_s)
        if left:
            raise ValueError(left)
    return out, changes


# ── stitching ───────────────────────────────────────────────────────────────

def stitch(windows, rule=None):
    """One result from the windows' detections.

    ``windows``: ``[{index, span: (a, b), core: (lo, hi), spans: [(start, end, score), ...]}]`` in order, every
    index channel-absolute. Returns ``{spans: [{start, end, score, window, owner, members, cut}], found, kept,
    duplicates, outside, per_window: {index: {found, kept}}, rule}``: ``window`` is the window whose view is kept,
    ``owner`` the one whose core holds the onset, ``members`` every window that found the event; ``outside`` counts
    the detections dropped because no window that found the event had its onset in its own core."""
    from Working.discovery.matching import match_quality, normalise_rule

    rule = normalise_rule(rule)
    windows = list(windows)
    if not windows:
        return {"spans": [], "found": 0, "kept": 0, "duplicates": 0, "outside": 0, "per_window": {}, "rule": rule}
    sec_a = min(int(w["span"][0]) for w in windows)
    sec_b = max(int(w["span"][1]) for w in windows)
    items = []
    for w in windows:
        k = int(w["index"])
        a, b = int(w["span"][0]), int(w["span"][1])
        lo, hi = int(w["core"][0]), int(w["core"][1])
        for sp in w.get("spans") or ():
            s, e = int(sp[0]), int(sp[1])
            score = sp[2] if len(sp) > 2 else None
            inner_a = a > sec_a
            inner_b = b < sec_b
            cut = (inner_b and e >= b) or (inner_a and s <= a)
            centrality = min((s - a) if inner_a else math.inf, (b - e) if inner_b else math.inf)
            items.append({"start": s, "end": e, "score": score, "window": k, "in_core": lo <= s < hi, "cut": cut,
                          "centrality": centrality})
    order = sorted(range(len(items)), key=lambda i: (items[i]["start"], items[i]["end"], items[i]["window"]))
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for x, i in enumerate(order):
        si = items[i]
        for j in order[x + 1:]:
            sj = items[j]
            if sj["start"] >= si["end"]:
                break
            if sj["window"] == si["window"]:
                continue
            a_, b_ = (si["start"], si["end"]), (sj["start"], sj["end"])
            if match_quality(a_, b_, rule=rule)["ok"] or match_quality(b_, a_, rule=rule)["ok"]:
                parent[find(j)] = find(i)
    clusters = {}
    for i in order:
        clusters.setdefault(find(i), []).append(i)
    kept, outside = [], 0
    per_window = {int(w["index"]): {"found": len(w.get("spans") or ()), "kept": 0} for w in windows}
    for members in clusters.values():
        owners = [i for i in members if items[i]["in_core"]]
        if not owners:
            outside += len(members)
            continue
        rep = min(members, key=lambda i: (items[i]["cut"], -items[i]["centrality"], items[i]["window"],
                                          items[i]["start"]))
        owner = rep if items[rep]["in_core"] else min(owners, key=lambda i: items[i]["window"])
        it = items[rep]
        per_window[it["window"]]["kept"] += 1
        kept.append({"start": it["start"], "end": it["end"], "score": it["score"], "window": it["window"],
                     "owner": items[owner]["window"], "members": sorted({items[i]["window"] for i in members}),
                     "cut": bool(it["cut"])})
    kept.sort(key=lambda s: (s["start"], s["end"]))
    found = len(items)
    return {"spans": kept, "found": found, "kept": len(kept), "duplicates": found - len(kept) - outside,
            "outside": outside, "per_window": per_window, "rule": rule}


# ── what each window fitted ─────────────────────────────────────────────────

#: the values a block's `meta` carries that it fitted to its span (scalars and short lists only)
FITTED_KEYS = ("sigma", "sigma_min", "sigma_max", "centre", "cut_below", "cut_above", "sigma_ratio_diff",
               "sigma_slope", "fast_cut_raw", "slope_threshold", "same_fraction_observed", "morphology",
               "cutlines", "alphabet_size", "threshold")


def _fitted_of(meta):
    out = {}
    if not isinstance(meta, dict):
        return out
    flat = dict(meta)
    details = meta.get("details")
    if isinstance(details, dict):
        for k in ("cutlines", "alphabet_size"):
            if k in details and k not in flat:
                flat[k] = details[k]
    for k in FITTED_KEYS:
        v = flat.get(k)
        if isinstance(v, bool) or v is None:
            continue
        if isinstance(v, (int, float)):
            if math.isfinite(float(v)):
                out[k] = float(v) if isinstance(v, float) else int(v)
        elif isinstance(v, str):
            out[k] = v
        elif isinstance(v, (list, tuple)) and 0 < len(v) <= 32 and all(isinstance(x, (int, float)) for x in v):
            out[k] = [float(x) for x in v]
    return out


def capture_fits(store, steps):
    """An `on_step_result` callback that keeps what each step fitted, under the block's name, in ``store``."""
    names = [_name(s) for s in steps]

    def on_step_result(i, result):
        got = _fitted_of(getattr(result, "meta", None))
        if got:
            key = names[i] if names.count(names[i]) == 1 else f"{names[i]}#{i + 1}"
            store[key] = got
    return on_step_result


def save_fits(conn, run_id, fits, commit=True):
    if not fits:
        return
    conn.execute("INSERT OR REPLACE INTO window_fits (run_id, fitted_json) VALUES (?, ?)",
                 (int(run_id), json.dumps(fits, sort_keys=True)))
    if commit:
        conn.commit()


def load_fits(conn, run_id):
    row = conn.execute("SELECT fitted_json FROM window_fits WHERE run_id = ?", (int(run_id),)).fetchone()
    return json.loads(row[0]) if row is not None else None


# ── recipes ─────────────────────────────────────────────────────────────────

def with_span(recipe, span):
    """``recipe`` over another span: what `make_recipe` returns for the same chain and recording there (the chain is
    validated once per channel, not once per window)."""
    out = dict(recipe)
    out["span"] = [int(span[0]), int(span[1])]
    return out


def stitched_recipe(steps, recording_id, section, scope, rule, surrogate):
    """The stitched run's recipe: the chain, the section, and the window scope with its stitch rule — never run as
    one span (`execute_recipe` refuses a recipe with ``windows``)."""
    from Working.discovery.matching import normalise_rule

    s = normalize_scope(scope)
    return {"recording_id": int(recording_id), "span": [int(section[0]), int(section[1])], "steps": steps,
            "surrogate": bool(surrogate),
            "windows": dict(s, rule=normalise_rule(rule), stitch=STITCH_VERSION)}


def stitched_draw_params(surrogate_params, j):
    from Working import run_groups as RG

    p = dict(surrogate_params or RG.DEFAULT_SURROGATE_PARAMS)
    p.setdefault("method", RG.DEFAULT_SURROGATE_PARAMS["method"])
    p["seed"] = int(p.get("seed") or 0) + int(j)
    return p


# ── the plan (fanout.plan's windowed branch) ─────────────────────────────────

def _store_step(steps):
    from Working.execution import _first_store_reading_step

    i = _first_store_reading_step(steps)
    return None if i is None else (i, _name(steps[i]))


def _channels(targets):
    out = {}
    for i, t in enumerate(targets):
        out.setdefault(int(t["recording_id"]), []).append(i)
    return out


def _chunks(seq, n=800):
    seq = list(seq)
    for k in range(0, len(seq), n):
        yield seq[k:k + n]


def _completed(conn, recording_id, hashes, spans):
    """For each (config hash, span): the newest completed run of it on ``recording_id`` — `find_completed_run`'s
    rule, read in bulk — as ``(run_id, surrogate_of_run_id)`` or None."""
    ids = {}
    for chunk in _chunks(sorted(set(hashes))):
        for row in conn.execute("SELECT id, config_hash FROM configs WHERE config_hash IN (%s)"
                                % ",".join("?" * len(chunk)), chunk):
            ids[row[1]] = int(row[0])
    runs = {}
    for chunk in _chunks(sorted(set(ids.values()))):
        for row in conn.execute("SELECT id, config_id, span_start, span_end, surrogate_of_run_id FROM runs "
                                "WHERE recording_id = ? AND status = 'completed' AND config_id IN (%s) ORDER BY id"
                                % ",".join("?" * len(chunk)), [int(recording_id), *chunk]):
            runs[(int(row[1]), int(row[2]), int(row[3]))] = (int(row[0]), row[4])
    out = []
    for h, (a, b) in zip(hashes, spans):
        cid = ids.get(h)
        out.append(runs.get((cid, int(a), int(b))) if cid is not None else None)
    return out


def lookup_windows(conn, base, spans, recording_id, *, draws=0, surrogate_params=None):
    """What already exists for each window of one channel: ``[{real, draws: [id|None], complete, todo_draws,
    skipped}]`` — the real run and each draw `run_paired_recipe` would reuse, read in bulk with one connection."""
    from Working import run_groups as RG
    from Working.recipes import short_hash

    recipes = [with_span(base, sp) for sp in spans]
    real = _completed(conn, recording_id, [short_hash(r) for r in recipes], spans)
    out = [{"real": (r[0] if r else None), "draws": [], "complete": r is not None, "todo_draws": 0, "skipped": None}
           for r in real]
    draws = max(0, int(draws or 0))
    if not draws:
        return out
    params = dict(surrogate_params or RG.DEFAULT_SURROGATE_PARAMS)
    params.setdefault("method", RG.DEFAULT_SURROGATE_PARAMS["method"])
    params["seed"] = int(params.get("seed") or 0)
    fixed = params["method"] != "block_shuffle" or params.get("block_s")
    want, where = [], []
    for k, (rec, st) in enumerate(zip(recipes, out)):
        if fixed:
            base_k, skipped = params, None
        elif st["real"] is None:
            st["todo_draws"] = draws
            continue
        else:
            base_k, skipped = RG.surrogate_draw_params(conn, st["real"], params)
        if base_k is None:
            st["skipped"] = skipped
            continue
        for j in range(draws):
            want.append(short_hash(RG.surrogate_recipe(rec, dict(base_k, seed=base_k["seed"] + j))))
            where.append((k, j))
    got = _completed(conn, recording_id, want, [spans[k] for k, _ in where])
    for st in out:
        if st["skipped"] is None and st["real"] is not None:
            st["draws"] = [None] * draws
    for (k, j), hit in zip(where, got):
        st = out[k]
        if not st["draws"]:
            st["draws"] = [None] * draws
        ok = hit is not None and st["real"] is not None and hit[1] is not None and int(hit[1]) == int(st["real"])
        st["draws"][j] = hit[0] if ok else None
    for st in out:
        if st["skipped"] is not None:
            continue
        if st["real"] is None:
            st["todo_draws"] = draws
            st["complete"] = False
            continue
        missing = sum(1 for d in st["draws"] if d is None)
        st["todo_draws"] = missing
        st["complete"] = missing == 0
        st["draws"] = [d for d in st["draws"] if d is not None] if missing == 0 else st["draws"]
    return out


def plan_windows(conn, *, steps, targets, refused, span, ceiling, measured_per_window_s=None, null_draws=0,
                 surrogate=None, surrogate_params=None, scope, stitch_rule=None):
    """`fanout.plan` for a window scope. ``targets`` are the plan's channel targets, the held-out and too-short ones
    already refused. Returns the plan in `fanout.plan`'s shape — ``targets`` one per window per channel, the recipe's
    fan-out of kind ``windows`` and its ``windows`` scope — plus ``windows``: the scope, the count per channel, the
    runs still to make (windows x (1 + draws), less what exists), the estimate per run and the run overhead floor,
    the chain's minimum window and the step that sets it, what fitting changed, and the stitch rule."""
    from Working.discovery import fanout, routing
    from Working.discovery.matching import normalise_rule, rule_from_settings
    from Working.recipes import make_recipe

    scope = normalize_scope(scope)
    rule = normalise_rule(stitch_rule) if stitch_rule is not None else rule_from_settings(conn)
    null_draws = max(0, int(null_draws or 0))
    surrogate = (null_draws > 0) if surrogate is None else bool(surrogate)
    draws = null_draws if surrogate else 0
    refused = list(refused)
    info = {"scope": scope, "label": scope_label(scope), "recommendedOverlap": DEFAULT_OVERLAP, "tradeOff": TRADE_OFF,
            "rule": rule, "rules": rules_for(rule), "minimum": None, "fitted": [], "refused": None, "warning": None,
            "per_channel": 0,
            "per_channel_by": {}, "targets": 0, "runs": 0, "done": 0, "per_window_s": None, "overhead_s": 0.0,
            "run_overhead_s": RUN_OVERHEAD_S, "window_samples": None, "step_samples": None}
    plan = {"targets": [], "refused": refused, "runnable": False, "reason": None,
            "span": (list(span) if span else None), "n_channels": 0, "recipe": None, "estimate_s": None,
            "estimate_real_s": None, "null_draws": null_draws, "per_channel_s": None, "uncosted": [],
            "route": "unknown", "ceiling_s": ceiling, "measured": measured_per_window_s is not None, "costs": [],
            "capped": [], "memory_capped": [], "surrogate": surrogate, "windows": info}

    def refuse(reason):
        info["refused"] = reason
        plan["reason"] = reason
        return plan

    if not targets:
        return refuse("; ".join(r["reason"] for r in refused) or "the scope has no runnable channel")
    store = _store_step(steps)
    if store is not None:
        return refuse(f"step {store[0] + 1:02d} ({store[1]}) reads the database while it runs, so its windows could "
                      f"not be reused; run this chain over the whole section")
    fs = float(targets[0]["fs"])
    if any(float(t["fs"]) != fs for t in targets):
        return refuse("the channels in scope have different rates; a window scope is one length in samples per rate")
    if scope["fit"]:
        try:
            steps, info["fitted"] = fit_steps(steps, fs, scope["window_s"])
        except ValueError as e:
            info["minimum"] = minimum_window(steps, fs)
            return refuse(str(e))
    info["minimum"] = minimum_window(steps, fs)
    why = bound_refusal(steps, fs, scope["window_s"])
    if why and scope.get("allow_short"):
        # the explicit opt-in: the chain kept as it is, the bound said on the plan and on the run
        info["warning"] = (f"run as it is in windows shorter than this chain allows: {_describe(info['minimum'])} "
                           f"asks for {fmt_duration(info['minimum']['minimum_s'])}, so near every window's edge "
                           f"that step works on part of what it needs and its output there is distorted")
    elif why:
        return refuse(why)
    n_w = window_samples(scope["window_s"], fs)
    info["window_samples"], info["step_samples"] = n_w, step_samples(n_w, scope["overlap_frac"])
    out, fan = [], []
    for t in targets:
        a, b = int(t["span"][0]), int(t["span"][1])
        spans = window_spans(a, b, n_w, scope["overlap_frac"])
        if not spans:
            refused.append({"recording_id": t["recording_id"], "reason": (
                f"{t['channel_name']}: its section ({fmt_duration((b - a) / fs)}) is shorter than one window "
                f"({fmt_duration(scope['window_s'])})")})
            continue
        info["per_channel_by"][int(t["recording_id"])] = len(spans)
        for k, ((wa, wb), (lo, hi)) in enumerate(zip(spans, window_cores(spans, a, b))):
            out.append({"recording_id": t["recording_id"], "channel": t["channel"], "channel_name": t["channel_name"],
                        "source_file": t["source_file"], "fs": t["fs"], "n_samples": t["n_samples"],
                        "span": [wa, wb], "samples": wb - wa, "section": [a, b],
                        "window": {"index": k, "of": len(spans), "core": [lo, hi]}})
            fan.append({"recording_id": int(t["recording_id"]), "span": [wa, wb]})
    if not out:
        return refuse("; ".join(r["reason"] for r in refused))
    recipe = make_recipe(out[0]["recording_id"], steps, span=(list(span) if span else None),
                         fan_out={"kind": KIND, "targets": fan})
    recipe["windows"] = dict(scope)
    chans = _channels(out)
    info["per_channel"] = len(next(iter(chans.values())))
    info["targets"] = len(out)
    costs, runs_real, runs_draws, done = [], 0, 0, 0
    total_s, real_total_s, per_window, uncosted = 0.0, 0.0, None, set()
    for rid, idxs in chans.items():
        base = fanout.target_recipe(recipe, idxs[0], surrogate)
        status = lookup_windows(conn, base, [out[i]["span"] for i in idxs], rid, draws=draws,
                                surrogate_params=surrogate_params)
        todo_real = sum(1 for st in status if st["real"] is None)
        todo_draws = sum(st["todo_draws"] for st in status)
        done += len(idxs) - todo_real
        rep = next((i for i, st in zip(idxs, status) if not st["complete"]), idxs[0])
        c = routing.target_cost(conn, fanout.target_recipe(recipe, rep, surrogate), samples=n_w, fs=fs, draws=draws,
                                surrogate_params=surrogate_params)
        real_s = None if c["uncosted"] else c["real_s"] + RUN_OVERHEAD_S
        draw_s = None if c["uncosted"] else ((c["draws_s"] / draws) if draws else 0.0) + RUN_OVERHEAD_S
        if measured_per_window_s is not None:
            real_s = draw_s = float(measured_per_window_s)
        if real_s is not None and per_window is None:
            per_window = real_s
        seconds = (0.0 if todo_real + todo_draws == 0 else
                   None if real_s is None else todo_real * real_s + todo_draws * draw_s)
        uncosted.update(c["uncosted"] if measured_per_window_s is None else [])
        if seconds is not None and total_s is not None:
            total_s += seconds
            real_total_s += (todo_real * real_s) if todo_real else 0.0
        elif seconds is None:
            total_s = None
        runs_real += todo_real
        runs_draws += todo_draws
        costs.append({"recording_id": rid, "channel_name": out[idxs[0]]["channel_name"], "samples": n_w,
                      "target": rep, "windows": len(idxs), "todo_real": todo_real, "todo_draws": todo_draws,
                      "seconds": seconds, "real_s": c["real_s"], "draws_s": c["draws_s"], "uncosted": c["uncosted"],
                      "cached": c["cached"], "draws_cached": c["draws_cached"], "draws_known": c["draws_known"],
                      "capped": c["capped"], "refused": c["refused"]})
    runs = runs_real + runs_draws
    info.update(runs=runs, done=done, per_window_s=per_window, overhead_s=runs * RUN_OVERHEAD_S)
    estimate = 0.0 if runs == 0 else total_s
    capped, memory_capped = fanout._capped(costs, "capped"), fanout._capped(costs, "refused")
    if capped or info["overhead_s"] > ceiling:
        route = "cluster"
    else:
        route = routing.route(estimate, ceiling)
    plan.update(targets=out, runnable=True, n_channels=len(chans), recipe=recipe, estimate_s=estimate,
                estimate_real_s=(0.0 if runs == 0 else (real_total_s if total_s is not None else None)),
                per_channel_s=(max((c["seconds"] for c in costs if c["seconds"] is not None), default=None)),
                uncosted=sorted(uncosted), route=route, costs=costs, capped=capped, memory_capped=memory_capped)
    return plan


def public_plan(plan):
    """A windowed plan as the page reads it: counts and costs per channel, not one entry per window (8,651 per
    channel at 10-minute windows over 721 h)."""
    out = {k: v for k, v in plan.items() if k not in ("targets", "recipe")}
    by = _channels(plan.get("targets") or [])
    out["targets"] = [{"recording_id": rid, "channel_name": plan["targets"][idxs[0]]["channel_name"],
                       "section": plan["targets"][idxs[0]]["section"], "windows": len(idxs)}
                      for rid, idxs in by.items()]
    r = plan.get("recipe")
    if r is not None:
        out["recipe"] = {"steps": r["steps"], "span": r["span"], "windows": r.get("windows"),
                         "fan_out": {"kind": KIND, "targets": len((r.get("fan_out") or {}).get("targets") or [])}}
    return out


# ── running it (fanout.start's windowed branch) ──────────────────────────────

def _link_group(conn, group_id, run_ids):
    """A run keeps the first group it joined (`fanout.start`); one UPDATE per channel, not one per run."""
    ids = [int(i) for i in run_ids if i is not None]
    for chunk in _chunks(ids):
        conn.execute("UPDATE runs SET run_group_id = ? WHERE run_group_id IS NULL AND id IN (%s)"
                     % ",".join("?" * len(chunk)), [int(group_id), *chunk])
    conn.commit()


def _refuse_locked(conn, target):
    """`execute_recipe`'s held-out guard, for the windows read rather than run: the lock is read now (a2-p1), so a
    switch turned on between the plan and the sweep refuses the channel, reused windows and all."""
    from Working.config import HELD_OUT_RECORDING_FILE
    from Working.execution import HeldOutRecordingLocked
    from Working.registration.settings import HELD_OUT_UNLOCK_HINT, held_out_locked

    if target["source_file"] == HELD_OUT_RECORDING_FILE and held_out_locked(conn):
        raise HeldOutRecordingLocked(f"Access to held-out recording '{HELD_OUT_RECORDING_FILE}' is locked: "
                                     f"{HELD_OUT_UNLOCK_HINT}.")


def start_windows(plan, *, db_path=None, on_progress=None, on_target_done=None, should_cancel=None, surrogate=False,
                  surrogate_params=None, force=False, run_kwargs=None, surrogate_draws=None, on_draw=None):
    """Run every window of a windowed plan, then stitch each channel's windows into its stitched run.

    A window whose run (and every draw) already exists is read, not run — in bulk, one connection per channel, the
    same rule `execute_recipe` reuses by — so a scope applied again computes nothing. The cancel is checked between
    windows; a channel stopped part-way is not stitched. Returns `fanout.start`'s ``{run_group_id, runs, cancelled,
    run_ids, reused}``: ``runs`` one row per channel (the stitched run, its stitched draws, the window runs it is
    made of), ``run_ids`` the stitched runs."""
    from Working.database import runs as R
    from Working.database.schema import init_db
    from Working.discovery import fanout
    from Working.run_groups import run_paired_recipe

    if not plan.get("runnable"):
        raise ValueError(f"this scope cannot run: {plan.get('reason')}")
    recipe, targets = plan["recipe"], plan["targets"]
    n = len(targets)
    if surrogate_draws is None:
        surrogate_draws = plan.get("null_draws") or None
    n_draws = (int(surrogate_draws) if surrogate_draws else 1) if surrogate else 0
    conn = init_db(db_path)
    try:
        group_id = R.create_run_group(conn)
        rows, cancelled, total = [], False, 0
        for rid, idxs in _channels(targets).items():
            first = targets[idxs[0]]
            _refuse_locked(conn, first)
            base = fanout.target_recipe(recipe, idxs[0], surrogate)
            status = None if force else lookup_windows(conn, base, [targets[i]["span"] for i in idxs], rid,
                                                       draws=n_draws, surrogate_params=surrogate_params)
            done = []
            for j, i in enumerate(idxs):
                if should_cancel is not None and should_cancel():
                    cancelled = True
                    break
                t = targets[i]
                if on_progress is not None:
                    on_progress(i, n, f"{t['channel_name']} · window {j + 1} of {len(idxs)}")
                st = status[j] if status is not None else None
                if st is not None and st["complete"]:
                    real_id, draw_ids, reused, skipped = st["real"], list(st["draws"]), True, st["skipped"]
                    n_det = conn.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (real_id,)).fetchone()[0]
                else:
                    fits = {}
                    res = run_paired_recipe(
                        with_span(base, t["span"]), db_path=db_path, force=force, run_kwargs=run_kwargs,
                        on_step_result=capture_fits(fits, recipe["steps"]), surrogate=bool(surrogate),
                        surrogate_params=surrogate_params, surrogate_draws=surrogate_draws,
                        should_cancel_draws=should_cancel,
                        on_draw=((lambda a, b, _i=i: on_draw(_i, n, a, b)) if on_draw is not None else None))
                    real_id, draw_ids = int(res["run_id"]), [int(x) for x in res["surrogate_run_ids"]]
                    reused, skipped, n_det = bool(res["reused"]), res.get("surrogate_skipped"), res["detections_written"]
                    if fits:
                        save_fits(conn, real_id, fits)
                done.append({"index": t["window"]["index"], "span": t["span"], "core": t["window"]["core"],
                             "run_id": int(real_id), "draw_ids": draw_ids, "reused": reused, "skipped": skipped,
                             "detections": int(n_det)})
                if on_target_done is not None:
                    on_target_done(i, n, {"run_id": int(real_id), "channel_name": t["channel_name"],
                                          "detections_written": int(n_det), "reused": reused, "window": j})
            _link_group(conn, group_id, [d["run_id"] for d in done] + [x for d in done for x in d["draw_ids"]])
            total += len(done)
            if cancelled:
                break
            row = write_stitched(conn, recording_id=rid, section=first["section"], steps=recipe["steps"],
                                 scope=recipe["windows"], rule=plan["windows"]["rule"], surrogate=bool(surrogate),
                                 surrogate_params=surrogate_params, n_draws=n_draws, windows=done, group_id=group_id)
            row.update({"recording_id": rid, "channel": first["channel"], "channel_name": first["channel_name"],
                        "windows": len(done), "window_run_ids": [d["run_id"] for d in done],
                        "windows_reused": sum(1 for d in done if d["reused"]),
                        "surrogate_skipped": next((d["skipped"] for d in done if d["skipped"]), None)})
            rows.append(row)
        return {"run_group_id": group_id, "runs": rows, "cancelled": cancelled,
                "run_ids": [r["run_id"] for r in rows], "reused": [r["run_id"] for r in rows if r["reused"]],
                "window_runs": total}
    finally:
        conn.close()


def _stitch_input(conn, windows, run_ids):
    from Working.discovery.spans import absolute_bounds

    by = {}
    live = [int(i) for i in run_ids if i is not None]
    span_of = {}
    for chunk in _chunks(live):
        for row in conn.execute("SELECT id, span_start FROM runs WHERE id IN (%s)" % ",".join("?" * len(chunk)), chunk):
            span_of[int(row[0])] = int(row[1])
        for row in conn.execute("SELECT run_id, start_idx, end_idx, score FROM detections WHERE run_id IN (%s) "
                                "ORDER BY run_id, start_idx, id" % ",".join("?" * len(chunk)), chunk):
            a, b = absolute_bounds(row[1], row[2], span_of.get(int(row[0]), 0))
            by.setdefault(int(row[0]), []).append((int(a), int(b), row[3]))
    return [{"index": w["index"], "span": w["span"], "core": w["core"],
             "spans": by.get(int(rid), []) if rid is not None else []} for w, rid in zip(windows, run_ids)]


def _provenance(conn, run_id):
    return [(int(r[0]), (int(r[1]) if r[1] is not None else None)) for r in conn.execute(
        "SELECT window_index, window_run_id FROM stitched_windows WHERE run_id = ? ORDER BY window_index",
        (int(run_id),))]


def _write_one(conn, recipe, recording_id, section, windows, run_ids, out, surrogate_of, elapsed_s):
    """One stitched run (or stitched draw): the newest completed one of this recipe over the section made of the
    same window runs is reused; otherwise it is written, with its detections and its provenance."""
    from Working.database import runs as R

    cfg_id, _ = R.get_or_create_config(conn, recipe)
    a, b = int(section[0]), int(section[1])
    want = [(int(w["index"]), (int(rid) if rid is not None else None)) for w, rid in zip(windows, run_ids)]
    cand = conn.execute(
        "SELECT id FROM runs WHERE config_id = ? AND recording_id = ? AND span_start = ? AND span_end = ? "
        "AND status = 'completed' AND " + ("surrogate_of_run_id IS NULL" if surrogate_of is None
                                           else "surrogate_of_run_id = ?") + " ORDER BY id DESC",
        (cfg_id, int(recording_id), a, b) + (() if surrogate_of is None else (int(surrogate_of),))).fetchall()
    for row in cand:
        if _provenance(conn, row[0]) == want:
            return int(row[0]), True
    run_id = R.insert_run(conn, cfg_id, int(recording_id), a, b, status="running")
    for s in out["spans"]:
        k = s["window"]
        pos = next(p for p, w in enumerate(windows) if int(w["index"]) == k)
        R.insert_detection(conn, run_id, s["start"], s["end"], score=s["score"], commit=False, meta_json=json.dumps({
            "window": k, "windowRunId": run_ids[pos], "windowSpan": list(windows[pos]["span"]), "owner": s["owner"],
            "members": s["members"], "cut": s["cut"]}))
    conn.executemany(
        "INSERT INTO stitched_windows (run_id, window_index, window_run_id, span_start, span_end, core_start, "
        "core_end, found, kept) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(run_id, int(w["index"]), (int(rid) if rid is not None else None), int(w["span"][0]), int(w["span"][1]),
          int(w["core"][0]), int(w["core"][1]), int(out["per_window"].get(int(w["index"]), {}).get("found", 0)),
          int(out["per_window"].get(int(w["index"]), {}).get("kept", 0))) for w, rid in zip(windows, run_ids)])
    conn.commit()
    fields = {"status": "completed", "finished_at": _now(), "duration_s": float(elapsed_s), "step_timings_json": "{}"}
    if surrogate_of is not None:
        fields["surrogate_of_run_id"] = int(surrogate_of)
    R.update_run(conn, run_id, **fields)
    return run_id, False


def write_stitched(conn, *, recording_id, section, steps, scope, rule, surrogate, surrogate_params, n_draws, windows,
                   group_id=None):
    """The stitched run of one channel and its stitched draws, from its windows (``[{index, span, core, run_id,
    draw_ids}]``). Returns ``{run_id, reused, surrogate_run_ids, surrogate_run_id, detections_written,
    surrogate_detections_written, config_hash, run_group_id, stitch}``."""
    from Working import run_groups as RG
    from Working.database import runs as R
    from Working.recipes import short_hash

    t0 = time.perf_counter()
    recipe = stitched_recipe(steps, recording_id, section, scope, rule, surrogate)
    real_ids = [w["run_id"] for w in windows]
    out = stitch(_stitch_input(conn, windows, real_ids), rule=rule)
    real_id, reused = _write_one(conn, recipe, recording_id, section, windows, real_ids, out, None,
                                 time.perf_counter() - t0)
    draw_ids, draw_counts = [], []
    for j in range(int(n_draws or 0)):
        ids_j = [(w["draw_ids"][j] if j < len(w["draw_ids"]) else None) for w in windows]
        if all(i is None for i in ids_j):
            break
        t1 = time.perf_counter()
        out_j = stitch(_stitch_input(conn, windows, ids_j), rule=rule)
        d_recipe = RG.surrogate_recipe(recipe, stitched_draw_params(surrogate_params, j))
        d_id, _ = _write_one(conn, d_recipe, recording_id, section, windows, ids_j, out_j, real_id,
                             time.perf_counter() - t1)
        draw_ids.append(d_id)
        draw_counts.append(out_j["kept"])
    if group_id is not None:
        _link_group(conn, group_id, [real_id, *draw_ids])
    group = R.get_run(conn, real_id)["run_group_id"]
    return {"run_id": real_id, "reused": reused, "surrogate_run_ids": draw_ids,
            "surrogate_run_id": (draw_ids[0] if draw_ids else None), "detections_written": out["kept"],
            "surrogate_detections_written": (draw_counts[0] if draw_counts else None),
            "config_hash": short_hash(recipe), "run_group_id": group,
            "stitch": {k: out[k] for k in ("found", "kept", "duplicates", "outside")}}


def window_totals(conn, stitched_run_ids):
    """Per stitched run: how many windows it is made of and what they found before stitching —
    ``{run_id: {windows, found, kept}}``."""
    out = {}
    for rid in stitched_run_ids:
        row = conn.execute("SELECT COUNT(*), COALESCE(SUM(found), 0), COALESCE(SUM(kept), 0) FROM stitched_windows "
                           "WHERE run_id = ?", (int(rid),)).fetchone()
        out[int(rid)] = {"windows": int(row[0]), "found": int(row[1]), "kept": int(row[2])}
    return out
