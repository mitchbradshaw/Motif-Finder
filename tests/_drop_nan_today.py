"""
_drop_nan_today.py
===================
The drop detector's functions as they stood at 3d8bfbf (2026-10-14), before they were made NaN-aware: the code
lines verbatim, docstrings and full-line comments dropped. `tests/test_drop_detection_nan.py` holds the live
functions to these on finite input, bit for bit. The helpers they call that the NaN change leaves alone are
imported from the live modules. Generated, not hand-edited.
"""

import time
from dataclasses import replace

import numpy as np

from Working.Detection.drop_motifs.detect import (  # noqa: F401
    ALPHABET_SIZE, NOISE_ESTIMATORS, NOISE_GRADIENT, NOISE_SECOND_DIFFERENCE, THRESHOLD_MODE, TREND_ESTIMATOR,
    _MAD_TO_SIGMA, _NOISELESS_FLOOR_FRAC, _SMOOTH_SIGNAL_FLOOR_RATIO, DetectionResult, DropEvent, _diagnostics,
    detrend, dim_ratio_for_segments, find_drop_onset, find_trough, merge_up_runs, up_regions,
)
from Working.Detection.drop_motifs.detect5 import (  # noqa: F401
    DOWN, FAST_DOWN, FAST_UP, MORPHOLOGIES, MORPHOLOGY_SHARKFIN, MORPHOLOGY_TROUGH, STAGE_LETTERS, TRIGGER_FALL,
    TRIGGER_RISE, UP, Detect5Result, Drop5Event, TIGHTEN_STEPS, _fall_limit, _first_crossing, count_falls, fall_runs,
    refine_onset, significant_rises, up_runs, walk_back_to_shoulder,
)
from Working.Detection.sax.csax_python.ts_paa import ts_paa  # noqa: F401
from Working.Detection.sax.dsax_python.dsax import (  # noqa: F401
    _DEGENERATE_REL, _NORM_THRESH, SYMBOL_LETTERS, THRESHOLD_MODES, _all_same_cutlines, _apply_min_same_halfwidth,
    _bin_representatives, _enforce_ascending, _flat_nonzero_cutlines, _learned_cutlines, _letter, _quantile_cutlines,
    _symmetrise,
)
from Working.Detection.sax.dsax_python.trend_estimators import TREND_ESTIMATORS, compute_deltas  # noqa: F401
from Working.Detection.sax.psax_python.kmeanspp import KMEANSPP_SEED  # noqa: F401

# -- Working/Detection/sax/dsax_python/dsax.py -----------------------------------------------------------

def dsax_letters(symbols, alphabet_size=3):
    symbols = np.asarray(symbols, dtype=int).ravel()
    table = SYMBOL_LETTERS.get(int(alphabet_size))
    if table is not None:
        return "".join(table[s] if 0 <= s < len(table) else "?" for s in symbols)
    return "".join(_letter(s) for s in symbols)


def dsax(data, training_len, dim_ratio, alphabet_size=3,
         trend_estimator="ols_slope", threshold_mode="learned",
         endpoint_k=1, absolute_threshold=None, same_fraction=0.5,
         min_same_halfwidth=None, force_symmetric=True,
         normalize=True, return_details=False, random_state=KMEANSPP_SEED):
    if trend_estimator not in TREND_ESTIMATORS:
        raise ValueError(
            f"Unknown trend_estimator {trend_estimator!r} — must be one of {TREND_ESTIMATORS}"
        )
    if threshold_mode not in THRESHOLD_MODES:
        raise ValueError(
            f"Unknown threshold_mode {threshold_mode!r} — must be one of {THRESHOLD_MODES}"
        )
    alphabet_size = int(alphabet_size)
    if alphabet_size < 2:
        raise ValueError(f"alphabet_size must be at least 2, got {alphabet_size}")
    if threshold_mode == "absolute":
        if alphabet_size != 3:
            raise ValueError(
                "threshold_mode='absolute' is defined for alphabet_size=3 only "
                f"(a single +/- threshold gives exactly 3 bins), got {alphabet_size}. "
                "Use 'learned' or 'quantile' for larger alphabets."
            )
        if absolute_threshold is None:
            raise ValueError("threshold_mode='absolute' requires absolute_threshold")
        if float(absolute_threshold) <= 0:
            raise ValueError(
                f"absolute_threshold must be positive, got {absolute_threshold} — "
                "it is a half-width, and the cutlines are +/- it"
            )
    if threshold_mode == "quantile" and not 0.0 < same_fraction < 1.0:
        raise ValueError(f"same_fraction must lie strictly in (0, 1), got {same_fraction}")

    data = np.asarray(data, dtype=float).ravel()
    original_len = len(data)

    data_len = len(data)
    data_nseg = int(np.floor(dim_ratio * data_len))
    if data_nseg < 2:
        raise ValueError(
            f"dim_ratio={dim_ratio!r} over {data_len} samples yields {data_nseg} segment(s); "
            "dSAX needs at least 2. Raise dim_ratio or use a longer span."
        )
    data_len = data_len - (data_len % data_nseg)
    data = data[:data_len]
    sps = data_len // data_nseg
    if sps < 2:
        raise ValueError(
            f"dim_ratio={dim_ratio!r} yields {sps} sample(s) per segment; a trend needs at "
            "least 2. Lower dim_ratio, or raise seconds_per_symbol."
        )

    training_len = int(training_len)
    training_nseg = max(int(np.floor(dim_ratio * training_len)), 1)
    training_len = training_len - (training_len % training_nseg)

    mu1, sigma1 = 0.0, 1.0
    if normalize:
        mu1 = float(data.mean())
        sd = float(data.std())
        if sd < _NORM_THRESH:
            data = data - mu1
        else:
            sigma1 = sd
            data = (data - mu1) / sigma1

    deltas, seg_slope, theil_sen_subsampled = compute_deltas(
        data, data_nseg, sps, trend_estimator=trend_estimator, endpoint_k=endpoint_k
    )

    n_train_seg = int(np.clip(training_len // sps, 2, data_nseg))
    training_deltas = deltas[:n_train_seg]

    delta_scale = sigma1 if normalize else None
    degenerate_tol = _DEGENERATE_REL * max(float(np.max(np.abs(data))) if data.size else 0.0, 1.0)
    deltas_are_flat = float(np.ptp(deltas)) <= degenerate_tol

    deltas_are_zero = deltas_are_flat and (
        (float(np.max(np.abs(deltas))) if deltas.size else 0.0) <= degenerate_tol
    )
    learning_mode = threshold_mode in ("learned", "quantile")

    codewords = None
    if deltas_are_zero and learning_mode:
        cutlines = _all_same_cutlines(deltas, alphabet_size, degenerate_tol)
    elif deltas_are_flat and learning_mode:
        cutlines = _flat_nonzero_cutlines(deltas, alphabet_size)
    elif threshold_mode == "learned":
        codewords, cutlines = _learned_cutlines(
            training_deltas, alphabet_size, npoints=min(training_len, 1000),
            random_state=random_state,
        )
        if force_symmetric:
            cutlines = _symmetrise(cutlines)
    elif threshold_mode == "absolute":
        thr = float(absolute_threshold)
        cutlines = np.array([-thr, thr], dtype=float)
        if normalize:
            cutlines = cutlines / delta_scale
    else:  # "quantile"
        cutlines = _quantile_cutlines(training_deltas, alphabet_size, float(same_fraction))
        if force_symmetric:
            cutlines = _symmetrise(cutlines)

    cutlines, min_same_applied = _apply_min_same_halfwidth(
        cutlines, min_same_halfwidth, alphabet_size
    )
    cutlines, nudged = _enforce_ascending(cutlines, deltas)
    cutlines_degenerate = bool(
        nudged or deltas_are_zero or (deltas_are_flat and learning_mode)
    )

    str_out = np.searchsorted(cutlines, deltas, side="right")

    if not return_details:
        return str_out

    paa = ts_paa(data, data_nseg)

    if normalize:
        norm_mean = mu1
        norm_std = sigma1
    else:
        norm_mean = None
        norm_std = None

    paa_raw = paa if norm_std is None else paa * norm_std + norm_mean
    deltas_raw = deltas if delta_scale is None else deltas * delta_scale
    cutlines_raw = cutlines if delta_scale is None else cutlines * delta_scale
    seg_slope_raw = seg_slope if delta_scale is None else seg_slope * delta_scale

    if codewords is not None:
        representatives = np.asarray(codewords, dtype=float)
    else:
        representatives = _bin_representatives(deltas, cutlines, alphabet_size)
    representatives_raw = (representatives if delta_scale is None
                           else representatives * delta_scale)

    zero_symbol = int(np.searchsorted(cutlines, 0.0, side="right"))
    same_fraction_observed = float(np.mean(str_out == zero_symbol)) if len(str_out) else 0.0

    segment_starts = np.arange(data_nseg, dtype=int) * sps
    segment_ends = segment_starts + sps

    details = {
        "samples_per_symbol": sps,
        "n_symbols": data_nseg,
        "data_len_trimmed": data_len,
        "n_trimmed": original_len - data_len,
        "alphabet_size": alphabet_size,
        "norm_mean": norm_mean,
        "norm_std": norm_std,
        "paa": paa,
        "paa_raw": paa_raw,
        "representatives": representatives,
        "representatives_raw": representatives_raw,
        "cutlines": np.asarray(cutlines, dtype=float),
        "cutlines_raw": np.asarray(cutlines_raw, dtype=float),
        "cutline_domain": "delta",
        "deltas": deltas,
        "deltas_raw": deltas_raw,
        "delta_scale": delta_scale,
        "delta_mean": float(np.mean(deltas)) if deltas.size else 0.0,
        "delta_mean_raw": (float(np.mean(deltas_raw)) if deltas_raw.size else 0.0),
        "seg_slope": seg_slope,
        "seg_slope_raw": seg_slope_raw,
        "segment_starts": segment_starts,
        "segment_ends": segment_ends,
        "trend_estimator": trend_estimator,
        "threshold_mode": threshold_mode,
        "force_symmetric": bool(force_symmetric),
        "zero_symbol": zero_symbol,
        "same_fraction_observed": same_fraction_observed,
        "cutlines_degenerate": cutlines_degenerate,
        "theil_sen_subsampled": bool(theil_sen_subsampled),
        "min_same_halfwidth_applied": bool(min_same_applied),
    }
    return str_out, details


# -- Working/Detection/drop_motifs/detect.py -------------------------------------------------------------

def robust_sigma(values):
    values = np.asarray(values, dtype=float).ravel()
    if values.size == 0:
        return 0.0
    mad = float(np.median(np.abs(values - np.median(values))))
    return _MAD_TO_SIGMA * mad


def slope_noise_sigma(x, fs, estimator=NOISE_SECOND_DIFFERENCE):
    x = np.asarray(x, dtype=float).ravel()
    if x.size < 3:
        return 0.0
    if estimator not in NOISE_ESTIMATORS:
        raise ValueError(
            f"unknown noise estimator {estimator!r} - must be one of "
            f"{NOISE_ESTIMATORS}")

    fs = float(fs)
    gradient_sigma = robust_sigma(np.gradient(x)) * fs
    if estimator == NOISE_GRADIENT:
        return _floor_noise(gradient_sigma, x, fs)

    amplitude_sigma = robust_sigma(np.diff(x, 2)) / np.sqrt(6.0)
    sigma = float(amplitude_sigma / np.sqrt(2.0) * fs)

    floor = gradient_sigma * _SMOOTH_SIGNAL_FLOOR_RATIO
    return _floor_noise(max(sigma, floor), x, fs)


def _floor_noise(sigma, x, fs):
    if sigma > 0.0:
        return float(sigma)
    span = float(np.ptp(x))
    if span <= 0.0:
        return 0.0          # genuinely constant; the caller short-circuits
    return float(span * _NOISELESS_FLOOR_FRAC * fs)


def detect_drops(x, fs, params):
    started = time.time()
    x = np.asarray(x, dtype=float).ravel()
    fs = float(fs)

    counts = {
        "samples": int(len(x)),
        "segments": 0,
        "up_regions": 0,
        "candidates": 0,
        "drops_confirmed": 0,
        "rejected_no_slope": 0,
        "rejected_shallow": 0,
        "rejected_duplicate": 0,
    }

    x_detrended = detrend(x, params.detrend_window_s * fs)

    if len(x_detrended) < 4 or float(np.ptp(x_detrended)) == 0.0:
        counts["degenerate_span"] = True
        return DetectionResult(events=[], counts=counts,
                               diagnostics={"reason": "span is constant",
                                            "elapsed_s": time.time() - started},
                               x_detrended=x_detrended, params=params)

    segment_samples = max(2, int(round(params.segment_seconds * fs)))
    ratio = dim_ratio_for_segments(len(x_detrended), segment_samples)

    np.random.seed(int(params.random_seed))   # no-op in quantile mode; see header
    symbols, details = dsax(
        x_detrended, len(x_detrended), ratio,
        alphabet_size=ALPHABET_SIZE,
        trend_estimator=TREND_ESTIMATOR,
        threshold_mode=THRESHOLD_MODE,
        same_fraction=params.same_fraction,
        return_details=True,
    )
    letters = merge_up_runs(dsax_letters(symbols, ALPHABET_SIZE),
                            params.merge_gap_segments)

    sps = int(details["samples_per_symbol"])
    segment_starts = np.asarray(details["segment_starts"], dtype=int)
    segment_ends = np.asarray(details["segment_ends"], dtype=int)
    counts["segments"] = int(details["n_symbols"])

    derivative = np.gradient(x_detrended)
    sigma_slope = slope_noise_sigma(x_detrended, 1.0,
                                    estimator=params.noise_estimator)
    slope_threshold = -float(params.slope_sigma) * sigma_slope

    regions = up_regions(letters)
    counts["up_regions"] = len(regions)

    candidates = []
    for seg_start, seg_end in regions:
        up_start = int(segment_starts[seg_start])
        up_end = int(segment_ends[seg_end - 1])
        up_duration = max(up_end - up_start, sps)
        lookahead = int(round(params.lookahead_mult * up_duration))

        onset = find_drop_onset(derivative, up_end, slope_threshold, lookahead)
        if onset is None:
            counts["rejected_no_slope"] += 1
            continue

        tail = min(len(x_detrended), onset + lookahead)
        if tail <= onset + 1:
            counts["rejected_no_slope"] += 1
            continue

        trough = find_trough(derivative, onset, tail,
                             knee_frac=params.trough_knee_frac)
        depth = float(x_detrended[onset] - x_detrended[trough])
        candidates.append({
            "up_start": up_start, "up_end": up_end, "onset": onset,
            "trough": trough, "depth": depth,
            "slope": float(derivative[onset]),
        })

    counts["candidates"] = len(candidates)
    if not candidates:
        counts["slope_threshold_raw"] = slope_threshold
        return DetectionResult(events=[], counts=counts,
                               diagnostics=_diagnostics(details, sigma_slope,
                                                        slope_threshold, started),
                               x_detrended=x_detrended, params=params)

    deepest = max(c["depth"] for c in candidates)
    kept = [c for c in candidates if c["depth"] >= params.min_depth_frac * deepest]
    counts["rejected_shallow"] = len(candidates) - len(kept)

    separation = params.min_separation_s * fs
    if separation > 0:
        survivors = []
        for candidate in sorted(kept, key=lambda c: -c["depth"]):
            if all(abs(candidate["onset"] - other["onset"]) >= separation
                   for other in survivors):
                survivors.append(candidate)
        counts["rejected_duplicate"] = len(kept) - len(survivors)
        kept = survivors
    kept.sort(key=lambda c: c["onset"])

    events = [_build_event(c, x, x_detrended, fs, params, sps) for c in kept]
    counts["drops_confirmed"] = len(events)
    counts["slope_threshold_raw"] = slope_threshold

    return DetectionResult(events=events, counts=counts,
                           diagnostics=_diagnostics(details, sigma_slope,
                                                    slope_threshold, started),
                           x_detrended=x_detrended, params=params)


def _build_event(candidate, x, x_detrended, fs, params, sps):
    onset, trough = candidate["onset"], candidate["trough"]
    fall = max(trough - onset, sps)

    start = max(0, onset - int(round(params.pre_context_mult * fall)))
    end = min(len(x), trough + int(round(params.post_context_mult * fall)))

    window = x[start:end]
    peak_to_peak = float(np.ptp(window)) * 1000.0 if window.size else 0.0

    return DropEvent(
        up_region_start_idx=candidate["up_start"],
        up_region_end_idx=candidate["up_end"],
        onset_idx=onset,
        trough_idx=trough,
        onset_slope_raw=candidate["slope"],
        drop_depth_mv=candidate["depth"] * 1000.0,
        fall_duration_s=(trough - onset) / fs,
        peak_to_peak_mv=peak_to_peak,
        snippet_start_idx=start,
        snippet_end_idx=end,
        detrend_window_s=params.detrend_window_s,
        segment_seconds=params.segment_seconds,
        same_fraction=params.same_fraction,
        slope_sigma=params.slope_sigma,
    )


# -- Working/Detection/drop_motifs/detect5.py ------------------------------------------------------------

def stage_letters(x, fs, params):
    x = np.asarray(x, dtype=float).ravel()
    fs = float(fs)

    if params.detrend_window_s <= 0:
        x_detrended = x.copy()
    else:
        detrend_samples = max(3, int(round(params.detrend_window_s * fs)))
        x_detrended = detrend(x, detrend_samples)

    segment_samples = max(1, int(round(params.segment_seconds * fs)))
    dim_ratio = dim_ratio_for_segments(len(x_detrended), segment_samples)

    symbols, details = dsax(
        x_detrended,
        training_len=len(x_detrended),
        dim_ratio=dim_ratio,
        alphabet_size=3,
        threshold_mode=params.threshold_mode,
        same_fraction=params.same_fraction,
        trend_estimator=params.trend_estimator,
        return_details=True,
    )

    three = merge_up_runs(dsax_letters(symbols, 3), params.merge_gap_segments)

    segment_slopes = np.asarray(details["seg_slope_raw"], dtype=float) * fs
    sigma_slope = slope_noise_sigma(x_detrended, fs, params.noise_estimator)
    cut = params.slope_sigma * sigma_slope

    n = min(len(three), len(segment_slopes))
    letters = []
    for i in range(n):
        symbol = three[i]
        slope = segment_slopes[i]
        if symbol == DOWN and slope <= -cut:
            letters.append(FAST_DOWN)
        elif symbol == UP and slope >= cut:
            letters.append(FAST_UP)
        else:
            letters.append(symbol)

    details = dict(details)
    details.update(
        segment_slopes=segment_slopes[:n],
        sigma_slope=float(sigma_slope),
        fast_cut_raw=float(cut),
        x_detrended=x_detrended,
        samples_per_symbol=int(details["samples_per_symbol"]),
        three_stage_letters=three[:n],
    )
    return "".join(letters), details


def morphology_from_letters(letters, x_detrended, sps, params):
    if params.morphology in MORPHOLOGIES:
        return params.morphology

    falls = fall_runs(letters)
    if not falls:
        return MORPHOLOGY_SHARKFIN

    rises = up_runs(letters)
    x_detrended = np.asarray(x_detrended, dtype=float).ravel()
    last = len(x_detrended) - 1

    preceded = 0
    for start_seg, end_seg in falls:
        start = min(start_seg * sps, last)
        depth = float(x_detrended[start] - x_detrended[min(end_seg * sps, last)])
        if depth <= 0:
            continue
        for rise_start, rise_end in rises:
            if not 0 <= start_seg - rise_end <= 1:
                continue
            climb = float(x_detrended[min(rise_end * sps, last)]
                          - x_detrended[min(rise_start * sps, last)])
            if climb >= params.min_rise_frac * depth:
                preceded += 1
                break

    return (MORPHOLOGY_SHARKFIN if preceded * 2 >= len(falls)
            else MORPHOLOGY_TROUGH)


def window_bounds(onset, trough, rises, segment_samples, morphology, params,
                  x_detrended, depth, falls=None):
    n_samples = len(x_detrended)
    fall = max(trough - onset, segment_samples)
    pad = int(round(params.window_pad_frac * fall))
    cap = int(round(params.window_cap_mult * fall))

    start = onset - cap
    end = trough + cap

    if params.bracket_on_up_runs:
        real = significant_rises(rises, x_detrended, segment_samples,
                                 params.min_rise_frac * depth)

        if morphology == MORPHOLOGY_SHARKFIN:
            before = [s for s, _ in real if s <= onset]
            if before:
                start = max(max(before) - pad, onset - cap)     # own; padded
            after = [s for s, _ in real if s > trough]
            if after:
                end = min(min(after), trough + cap)             # next; hard
        else:
            before = [e for _, e in real if e <= onset]
            if before:
                start = max(max(before), onset - cap)           # prev; hard
            after = [e for _, e in real if e > trough]
            if after:
                end = min(min(after) + pad, trough + cap)       # own; padded

    if falls:
        before = [e * segment_samples for _, e in falls
                  if e * segment_samples <= onset]
        if before:
            start = max(start, max(before))
        after = [s * segment_samples for s, _ in falls
                 if s * segment_samples > trough]
        if after:
            end = min(end, min(after))

    return max(0, int(start)), min(int(n_samples), int(end))


def detect_drops5(x, fs, params):
    started = time.time()
    x = np.asarray(x, dtype=float).ravel()
    fs = float(fs)

    counts = dict(
        segments=0, up_runs=0, fall_runs=0,
        candidates=0, rejected_no_fall=0, rejected_no_rise=0,
        rejected_not_dominant=0, rejected_shallow=0, rejected_duplicate=0,
        fall_trigger_suppressed=0, drops_confirmed=0,
    )

    if x.size < 8 or float(np.ptp(x)) == 0.0:
        return Detect5Result(counts=counts, params=params,
                             morphology=params.morphology
                             if params.morphology in MORPHOLOGIES
                             else MORPHOLOGY_SHARKFIN,
                             x_detrended=np.zeros_like(x))

    letters, details = stage_letters(x, fs, params)
    x_detrended = details["x_detrended"]
    sps = int(details["samples_per_symbol"])
    morphology = morphology_from_letters(letters, x_detrended, sps, params)
    return detect_from_letters(
        x_detrended, fs, letters, sps, details["sigma_slope"], morphology, params,
        counts=counts, started=started,
        same_fraction_observed=float(details["same_fraction_observed"]))


def detect_from_letters(x_detrended, fs, letters, sps, sigma_slope, morphology, params,
                        counts=None, started=None, same_fraction_observed=float("nan")):
    started = time.time() if started is None else started
    x_detrended = np.asarray(x_detrended, dtype=float).ravel()
    fs = float(fs)
    if counts is None:
        counts = dict(
            segments=0, up_runs=0, fall_runs=0,
            candidates=0, rejected_no_fall=0, rejected_no_rise=0,
            rejected_not_dominant=0, rejected_shallow=0, rejected_duplicate=0,
            fall_trigger_suppressed=0, drops_confirmed=0,
        )
    sps = int(sps)
    slope_threshold = -params.slope_sigma * sigma_slope

    counts["segments"] = len(letters)
    rises = up_runs(letters)
    falls = fall_runs(letters)
    counts["up_runs"] = len(rises)
    counts["fall_runs"] = len(falls)

    derivative = np.gradient(x_detrended) * fs

    rise_candidates, fall_candidates = {}, {}

    for start_seg, end_seg in rises:
        rise_start = start_seg * sps
        rise_end = min(end_seg * sps, len(x_detrended) - 1)
        lookahead = max(sps, int(params.lookahead_mult * (rise_end - rise_start)))
        onset = _first_crossing(derivative, rise_end, slope_threshold, lookahead)
        if onset is None:
            counts["rejected_no_fall"] += 1
            continue
        rise_candidates[onset] = dict(onset=onset, trigger=TRIGGER_RISE,
                                      up_start=rise_start, up_end=rise_end)

    for start_seg, end_seg in falls:
        at = start_seg * sps
        onset = _first_crossing(derivative, at, slope_threshold,
                                (end_seg - start_seg + 1) * sps)
        if onset is None or onset in fall_candidates:
            continue
        fall_candidates[onset] = dict(onset=onset, trigger=TRIGGER_FALL,
                                      up_start=-1, up_end=-1)

    counts["fall_trigger_suppressed"] = sum(
        1 for onset in fall_candidates
        if any(abs(onset - other) <= sps for other in rise_candidates))

    if morphology == MORPHOLOGY_SHARKFIN:
        counts["rejected_no_rise"] += sum(
            1 for onset in fall_candidates
            if not any(abs(onset - other) <= sps for other in rise_candidates))

    candidates = (rise_candidates if morphology == MORPHOLOGY_SHARKFIN
                  else fall_candidates)
    proposals = sorted(candidates.values(), key=lambda c: c["onset"])
    counts["candidates"] = len(proposals)

    kept = []
    previous_trough = 0
    for candidate in proposals:
        onset = candidate["onset"]
        trough = find_trough(derivative, onset,
                             _fall_limit(onset, rises, sps, len(derivative),
                                         falls=(falls if
                                                params.bracket_on_fall_runs
                                                else None),
                                         min_separation_samples=(
                                             params.min_separation_s * fs),
                                         rise_separation=(
                                             params.bracket_rise_on_separation)),
                             knee_frac=params.trough_knee_frac)
        if trough <= onset:
            continue

        onset = refine_onset(derivative, onset, trough,
                             knee_frac=params.trough_knee_frac)
        if params.walk_onset_back:
            onset = walk_back_to_shoulder(
                x_detrended, onset,
                backstop=max(previous_trough,
                             onset - int(round(params.window_cap_mult
                                               * max(trough - onset, sps)))))
        candidate["onset"] = onset
        if trough <= onset:
            continue

        depth = float(x_detrended[onset] - x_detrended[trough])
        if depth <= 0:
            continue

        rise_height = 0.0
        if candidate["trigger"] == TRIGGER_RISE:
            rise_height = float(
                x_detrended[onset] - x_detrended[candidate["up_start"]])
            if rise_height < params.min_rise_frac * depth:
                counts["rejected_no_rise"] += 1
                continue

        candidate.update(trough=trough, depth=depth, rise_height=rise_height)
        kept.append(candidate)
        previous_trough = int(trough)

    if kept and params.min_depth_frac > 0:
        deepest = max(c["depth"] for c in kept)
        survivors = [c for c in kept
                     if c["depth"] >= params.min_depth_frac * deepest]
        counts["rejected_shallow"] = len(kept) - len(survivors)
        kept = survivors

    separation = params.min_separation_s * fs
    if separation > 0 and kept:
        survivors = []
        for candidate in sorted(kept, key=lambda c: -c["depth"]):
            if all(abs(candidate["onset"] - other["onset"]) >= separation
                   for other in survivors):
                survivors.append(candidate)
        counts["rejected_duplicate"] = len(kept) - len(survivors)
        kept = survivors
    kept.sort(key=lambda c: c["onset"])

    events = []
    for candidate in kept:
        if params.tighten_windows:
            start, end, rise_frac_used, _ = tighten_window(
                candidate["onset"], candidate["trough"], rises, sps,
                morphology, params, x_detrended, candidate["depth"],
                derivative, slope_threshold,
                fall_runs_segments=(falls if params.bracket_on_fall_runs
                                    else None))
        else:
            start, end = window_bounds(
                candidate["onset"], candidate["trough"], rises, sps,
                morphology, params, x_detrended, candidate["depth"],
                falls=(falls if params.bracket_on_fall_runs else None))
            rise_frac_used = params.min_rise_frac

        window = x_detrended[start:end]
        peak_to_peak = float(np.ptp(window)) if window.size else 0.0
        dominance = (candidate["depth"] / peak_to_peak
                     if peak_to_peak > 0 else 0.0)
        if dominance < params.min_fall_dominance:
            counts["rejected_not_dominant"] += 1
            continue

        onset, trough = candidate["onset"], candidate["trough"]
        events.append(Drop5Event(
            onset_idx=int(onset),
            trough_idx=int(trough),
            window_start_idx=int(start),
            window_end_idx=int(end),
            up_region_start_idx=int(candidate["up_start"]),
            up_region_end_idx=int(candidate["up_end"]),
            trigger=candidate["trigger"],
            morphology=morphology,
            onset_slope_raw=float(derivative[onset]),
            max_slope_raw=float(derivative[onset:trough + 1].min()),
            drop_depth_mv=candidate["depth"] * 1000.0,
            rise_height_mv=candidate["rise_height"] * 1000.0,
            fall_duration_s=(trough - onset) / fs,
            peak_to_peak_mv=peak_to_peak * 1000.0,
            fall_dominance=float(dominance),
            rise_frac_used=float(rise_frac_used),
            detrend_window_s=params.detrend_window_s,
            segment_seconds=params.segment_seconds,
            same_fraction=params.same_fraction,
            slope_sigma=params.slope_sigma,
        ))

    counts["drops_confirmed"] = len(events)

    return Detect5Result(
        events=events,
        counts=counts,
        letters=letters,
        morphology=morphology,
        x_detrended=x_detrended,
        params=params,
        diagnostics=dict(
            samples_per_symbol=sps,
            n_segments=len(letters),
            sigma_slope_mv_per_s=float(sigma_slope) * 1000.0,
            slope_threshold_mv_per_s=float(slope_threshold) * 1000.0,
            same_fraction_observed=same_fraction_observed,
            stage_histogram={c: letters.count(c) for c in STAGE_LETTERS},
            elapsed_s=round(time.time() - started, 3),
        ),
    )


def tighten_window(onset, trough, rises, sps, morphology, params,
                   x_detrended, depth, derivative, slope_threshold,
                   steps=TIGHTEN_STEPS, fall_runs_segments=None):
    best = None
    for factor in steps:
        trial = replace(params, min_rise_frac=params.min_rise_frac * factor)
        start, end = window_bounds(onset, trough, rises, sps, morphology,
                                   trial, x_detrended, depth,
                                   falls=fall_runs_segments)
        falls = count_falls(derivative, start, end, slope_threshold,
                            max(1, sps))
        if best is None:
            best = (start, end, trial.min_rise_frac, falls)
        if falls <= 1:
            return start, end, trial.min_rise_frac, falls
    return best
