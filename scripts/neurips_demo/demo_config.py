"""The NeurIPS demo's single source of truth: which data, which builder menu.

Read by every script in scripts/neurips_demo/ (the precompute) and written into the store's manifest, which the
station server and the client read. Nothing here imports the UI or the core; it is plain data.

Decisions behind every number: docs/neurips_demo/DECISIONS.md (round 1 Q4/Q6, round 2 items 1-2).
"""
from __future__ import annotations

import itertools

#: The real checkout whose DATA/ the slices are cut from (read only: the database is opened ?mode=ro and the
#: channel files with np.load(mmap_mode="r")). The demo never writes there.
REAL_ROOT = r"C:\Users\mmebr\Documents\CNN"

#: Where the demo's own data lives, relative to the repo root the scripts and stations run from.
DEMO_DATA = "DATA/neurips_demo"

#: The three datasets, each a 24 h slice x 4 channels (0-based channel numbers, as stored). The first is the one
#: the tour follows. Windows chosen by accepted events per 24 h (DECISIONS round 2 item 1).
DATASETS = [
    {
        "key": "lions_mane", "name": "Lion's mane", "latin": "Hericium erinaceus",
        "source_file": "MJu26a_fs2.mat", "recording": "MJu26a", "channels": [13, 12, 14, 4], "hours": [438, 462],
        "blurb": "A 90-hour train of regular drops on CH14: the fungus 'heartbeat'.",
        # the accepted catalogue judged this recording on its 10 Hz copy; fs2 = 5-sample block means of fs10
        "verdict_source": {"source_file": "MJu26a_fs10.mat", "decimation": 5},
    },
    {
        "key": "oyster", "name": "Oyster", "latin": "Pleurotus ostreatus",
        "source_file": "M2_aug_concat_fs1.mat", "recording": "M2_aug", "channels": [1, 3, 5, 6], "hours": [402, 426],
        "blurb": "Sixteen electrodes in one oyster culture; drops come one electrode at a time.",
        "verdict_source": {"source_file": "M2_aug_concat_fs1.mat", "decimation": 1},
    },
    {
        "key": "split_gill", "name": "Split gill", "latin": "Schizophyllum commune",
        "source_file": "Schizophyllum commune.txt", "recording": "Adamatzky S. commune", "channels": [3, 6, 0, 5],
        "hours": [0, 24],
        "blurb": "Another lab's public recording (Adamatzky et al.), searched with the same tools.",
        "verdict_source": {"source_file": "Schizophyllum commune.txt", "decimation": 1},
    },
]


def channel_label(ch: int) -> str:
    """The UI's channel name: 1-based, as the site prints it (0-based 13 is CH14)."""
    return f"CH{int(ch) + 1}"


# ── the builder menu (Q6 = A: three slots, notched knobs, every combination pre-computed) ─────────────────────────

#: Slot 1, Clean. Rolling-mean drift removal (the drop detector's exact filter) x what to look for.
CLEAN_WINDOWS_S = [300.0, 1200.0, 4916.67]          # 5, 20, 82 min; 4916.67 s is drop_detection_v1's default
LOOK_FOR = ["drops", "rises"]                        # rises = the signal flipped first (the spike template's route)

#: Slot 2, Find events: one detector, each with its notched knobs. The first value of each knob list that is
#: flagged `default` is where the slider starts.
DETECTORS = {
    "drop_detector": {
        "label": "Drop detector",
        "blurb": "The thesis detector: the trace becomes letters, a steep fall becomes an event.",
        "knobs": {
            "segment_s": {"label": "Letter length", "unit": "s", "values": [5.0, 20.0, 98.33], "default": 98.33},
            "slope_sigma": {"label": "Steepness gate", "unit": "σ", "values": [4.0, 8.0, 12.0], "default": 8.0},
        },
    },
    "noise_threshold": {
        "label": "Noise threshold",
        "blurb": "Anything that dips further than k times the channel's own noise.",
        "knobs": {
            "k_sigma": {"label": "Cut", "unit": "σ", "values": [3.0, 4.0, 6.0], "default": 4.0},
            "min_duration_s": {"label": "Shortest event", "unit": "s", "values": [10.0, 30.0], "default": 30.0},
        },
    },
    "wavelet": {
        "label": "Wavelet ridges",
        "blurb": "A Mexican-hat wavelet at many sizes; an event is a ridge across the sizes.",
        "knobs": {
            "min_scale_s": {"label": "Smallest size", "unit": "s", "values": [2.0, 10.0, 30.0], "default": 10.0},
        },
    },
}

#: Slot 3, Describe: always event shape + intervals (feeds Spike statistics).

#: The paired null: noise copies (surrogates) per channel, the site's default method.
NULL_METHOD = "phase_randomize"
NULL_DRAWS = 10


def combos():
    """Every builder setting, in a stable order: dicts with an `id` and everything a recipe needs."""
    out = []
    for look, win in itertools.product(LOOK_FOR, CLEAN_WINDOWS_S):
        for det, spec in DETECTORS.items():
            names = list(spec["knobs"])
            for values in itertools.product(*(spec["knobs"][n]["values"] for n in names)):
                knobs = dict(zip(names, values))
                cid = "_".join([look, f"w{int(round(win))}", det] + [f"{n}{_num(v)}" for n, v in knobs.items()])
                out.append({"id": cid, "look_for": look, "window_s": win, "detector": det, "knobs": knobs})
    return out


def default_combo_id(detector: str = "drop_detector", look_for: str = "drops", window_s: float = 4916.67) -> str:
    """The combination a fresh builder shows: the detector's default knobs (the thesis settings)."""
    spec = DETECTORS[detector]
    knobs = {n: k["default"] for n, k in spec["knobs"].items()}
    for c in combos():
        if c["detector"] == detector and c["look_for"] == look_for and abs(c["window_s"] - window_s) < 1e-6 \
                and c["knobs"] == knobs:
            return c["id"]
    raise KeyError(detector)


def _num(v: float) -> str:
    s = f"{v:g}"
    return s.replace(".", "p")


def recipe_steps(c: dict) -> list[dict]:
    """The core recipe steps of one builder setting (stage / algorithm / params, as Working.recipes.make_recipe)."""
    steps = []
    inverted = c["look_for"] == "rises"
    if inverted:
        steps.append({"stage": "preprocessing", "algorithm": "invert", "params": {}})
    steps.append({"stage": "preprocessing", "algorithm": "detrend",
                  "params": {"mode": "rolling_mean_nearest", "window_s": float(c["window_s"])}})
    k = c["knobs"]
    if c["detector"] == "drop_detector":
        steps.append({"stage": "detection", "algorithm": "stage_encoding",
                      "params": {"segment_seconds": float(k["segment_s"]), "same_fraction": 0.6,
                                 "slope_sigma": float(k["slope_sigma"])}})
        steps.append({"stage": "detection", "algorithm": "drop_detection",
                      "params": {"slope_sigma": float(k["slope_sigma"])}})
    elif c["detector"] == "noise_threshold":
        steps.append({"stage": "detection", "algorithm": "noise_threshold",
                      "params": {"k_sigma": float(k["k_sigma"]), "direction": "below",
                                 "min_duration_s": float(k["min_duration_s"]), "merge_gap_s": 60.0}})
    elif c["detector"] == "wavelet":
        steps.append({"stage": "detection", "algorithm": "cwt_ridges",
                      "params": {"min_scale_s": float(k["min_scale_s"]), "polarity": "drop"}})
    else:
        raise ValueError(c["detector"])
    steps.append({"stage": "interrogation", "algorithm": "event_shape",
                  "params": {"polarity": "drop", "upstream_inverted": inverted}})
    steps.append({"stage": "interrogation", "algorithm": "intervals", "params": {"anchor": "onset"}})
    return steps


#: The three reference runs Discovery shows beside the visitor's (DECISIONS round 2 item 3). The first two are
#: builder settings at the thesis defaults; Auto-detect comes from the 24 Nov drop pool.
REFERENCE_RUNS = [
    {"key": "ref_drop", "label": "Thesis drop detector", "combo": "drops_w4917_drop_detector_segment_s98p33_slope_sigma8"},
    {"key": "ref_noise", "label": "Noise threshold", "combo": "drops_w300_noise_threshold_k_sigma4_min_duration_s30"},
    {"key": "ref_auto", "label": "Auto-detect", "combo": None},
]

#: Auto-detect: the 24 Nov drop pool (v4, drops only), read from the real DATA, read only.
POOL_DIR = "DATA/derived/autodetect/pool_20261124"
AUTO_MIN_CONFIDENCE = 0.5
