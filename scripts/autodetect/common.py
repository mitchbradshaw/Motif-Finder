"""
common.py — what the auto-detect prototype scripts share: the four reference stretches, the read-only database, the
guard that refuses any write under DATA/, the seed bank, the R4 scorer and the reviewed material on a stretch.

Nothing here is imported by the core (`Working/autodetect` takes all of this as arguments).
"""

from __future__ import annotations

import builtins
import importlib.util
import json
import os
import re
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
#: v2 (2026-11-23): event boxes, the flat-drift gate, BEADS -> 10 sigma, drop detectors in 6 h windows. The first
#: version's pages stay in docs/autodetect/20261119/ for comparison; the seed bank is built once and shared.
# v4 (23 Nov, evening): the researcher's event rule (a drop: sharp, or >= 5 samples falling steadily to a significant
# bottom), the rule as a finder, returns folded with a tolerance, margins cut at neighbours, the committed whole drop
OUT = os.path.join(ROOT, "docs", "autodetect", "20261123_v4")
OUT_V3 = os.path.join(ROOT, "docs", "autodetect", "20261123_v3")
OUT_V2 = os.path.join(ROOT, "docs", "autodetect", "20261123")
OUT_V1 = os.path.join(ROOT, "docs", "autodetect", "20261119")
SEED_BANK = os.path.join(OUT_V1, "seed_bank")
R4_MODEL = os.path.join(ROOT, "DATA", "derived", "models", "rq1b_minirocket", "20261020-2343", "model.joblib")
CATALOGUE = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")

#: The four detector templates (researcher, 2026-11-19, Q8 (b)): template id -> source name.
DETECTOR_TEMPLATES = {1: "drop_detection_v1", 19: "drop_detection_v5", 18: "wavelet_encoded",
                      30: "BEADs_invert_detect_v1"}
#: Detectors also run over sliding windows (2026-11-23, Q3 (a)): 6-hour windows, half overlapping, the chain as it
#: is (6 h is within both drop detectors' bound: 4 x their 82-minute detrend). Variant ``<source>__w6h`` is one vote
#: with the whole-stretch run.
WINDOWED = {"drop_detection_v1": 6 * 3600.0, "drop_detection_v5": 6 * 3600.0}
#: BEADS -> threshold, the chain that found the MJu26a CH14 train (run 8718, 8 Nov: BEADS 7,200 s, +-3.1 mV), with
#: the cut set from the local noise instead of a fixed level (2026-11-23, Q3 (a)): BEADS with a 60 s baseline
#: (template 76's), then 10 x the robust sigma of a rolling hour, either side, at least 2 s.
BEADS_SIGMA = [
    {"stage": "preprocessing", "algorithm": "beads",
     "params": {"baseline_period_s": 60.0, "filter_order": 2, "polarity": "drop", "sparsity": 1}},
    {"stage": "detection", "algorithm": "noise_threshold",
     "params": {"direction": "either", "k_sigma": 10.0, "noise_from": "rolling", "noise_window_s": 3600.0,
                "merge_gap_s": 0.0, "min_duration_s": 2.0}},
]

#: The reference stretches (Q11 + MJu26a CH15). ``rec`` is the recording run on; ``canonical`` the physical channel
#: the catalogue's coordinates name (MJu26a's verdicts are on the 10 Hz copy, the run is on the 2 Hz copy).
REFERENCES = [
    {"key": "M2_aug_CH7_B2", "title": "M2_aug CH7_B2 (oyster), 0-528 h at 1 Hz", "rec": 7, "canonical": 7,
     "start_h": 0.0, "hours": 528.0,
     "why": "the most accepted events of any M2_aug channel, plus its 10-minute labelled windows"},
    {"key": "MJu26a_CH14", "title": "MJu26a CH14 (lion's mane), 300-564 h at 2 Hz", "rec": 705, "canonical": 663,
     "start_h": 300.0, "hours": 264.0, "why": "the 90 h train of narrow square-bottomed drops: the sequence test"},
    {"key": "MJu26a_CH15", "title": "MJu26a CH15 (lion's mane), 120-384 h at 2 Hz", "rec": 706, "canonical": 664,
     "start_h": 120.0, "hours": 264.0, "why": "the 143-member long train (loose boundaries, long members)"},
    {"key": "M4_CH1_A1", "title": "M4 CH1_A1 (oyster), whole channel, 505 h at 1 Hz", "rec": 49, "canonical": 49,
     "start_h": 0.0, "hours": None, "why": "the one recording R4 never trained on; barely analysed (read-only)"},
]

#: Pages kept for comparison in the first version's folder (v2 links to them rather than rebuilding them).
COMPARISONS_V1 = [
    {**REFERENCES[0], "key": "M2_aug_CH7_B2__every_family",
     "title": "M2_aug CH7_B2, 0-528 h — every seed family searched (the first run, kept for comparison)",
     "why": "the rule first agreed: all 64 families propose. It flooded the channel with 48,165 seed matches, "
            "which is why only families whose members are alike now propose (its run time was measured while other "
            "work ran on the machine)"},
]


# ── the write guard ─────────────────────────────────────────────────────────

_DATA = os.path.normcase(os.path.join(ROOT, "DATA")) + os.sep
_real_open = builtins.open


def _guarded_open(file, mode="r", *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)) and any(c in str(mode) for c in "wax+"):
        path = os.path.normcase(os.path.abspath(os.fsdecode(file)))
        if path.startswith(_DATA):
            raise PermissionError(f"auto-detect prototype: refusing to write under DATA/: {path}")
    return _real_open(file, mode, *args, **kwargs)


def install_write_guard():
    """Refuse any file opened for writing under DATA/ (np.save, joblib.dump and plain open all go through it)."""
    builtins.open = _guarded_open
    import io
    io.open = _guarded_open


def redirect_adapter_outputs(scratch):
    """Point the step cache and every adapter results folder the web bridge redirects at ``scratch`` (none of the
    four detector chains writes, and the in-memory runner skips the cache; this is the belt to the guard's braces)."""
    import Working.config as cfg
    cfg.STEP_CACHE_ROOT = os.path.join(scratch, "step_cache")
    for mod, attr, sub in (("Adapters.detection_matrix_profile", "RESULTS_DIR", "matrix_profile"),
                           ("Adapters.preprocessing_window_matrix", "RESULTS_DIR", "window_matrix"),
                           ("Adapters.catalogue_cluster", "RESULTS_DIR", "groupings"),
                           ("Adapters.preprocessing_trace_shape", "RESULTS_DIR", "trace_shapes"),
                           ("Adapters.catalogue_shape_cluster", "RESULTS_DIR", "shape_trees")):
        try:
            m = importlib.import_module(mod)
            setattr(m, attr, os.path.join(scratch, sub))
        except Exception:  # noqa: BLE001 — a module that is absent cannot write either
            pass


# ── database and channels ───────────────────────────────────────────────────

def connect():
    c = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def recording(conn, rid):
    return dict(conn.execute("SELECT * FROM recordings WHERE id = ?", (int(rid),)).fetchone())


def stretch(conn, ref):
    """``(rec, a, b)``: the recording row and the stretch's sample bounds on it."""
    rec = recording(conn, ref["rec"])
    a = int(round(ref["start_h"] * 3600 * rec["fs"]))
    b = rec["n_samples"] if ref["hours"] is None else min(rec["n_samples"], a + int(round(ref["hours"] * 3600 * rec["fs"])))
    return rec, a, b


def load_samples(rec, a, b):
    return np.asarray(np.load(os.path.join(ROOT, rec["npy_path"]), mmap_mode="r")[a:b], dtype=float)


def detector_steps(conn):
    out = {}
    for tid, name in DETECTOR_TEMPLATES.items():
        row = conn.execute("SELECT name, steps_json FROM templates WHERE id = ?", (tid,)).fetchone()
        if row is None or row["name"] != name:
            raise RuntimeError(f"template {tid} is not {name!r} in this database")
        out[name] = json.loads(row["steps_json"])
    return out


def detector_specs(conn):
    """The v2 line-up: the four templates over the whole stretch, drop v1 and v5 also in 6-hour windows, and
    BEADS -> 10 sigma (`Working.autodetect.pipeline.detector_specs`' shape)."""
    steps = detector_steps(conn)
    specs = [{"variant": name, "steps": st, "window_s": None, "fit": False} for name, st in steps.items()]
    specs += [{"variant": f"{name}__w{window_s / 3600:g}h", "steps": steps[name], "window_s": window_s, "fit": False}
              for name, window_s in WINDOWED.items()]
    specs.append({"variant": "beads_sigma", "steps": BEADS_SIGMA, "window_s": None, "fit": False})
    return specs


def noise_floor_mv(conn, source_file):
    """Settings › Datasets' ``meta.<stem>.noise_floor``; a derived copy (``_fs2``, ``_fs10``) reads its parent's;
    else the Library's instrument floor (`Working.library.view_filter.DEFAULT_FLOOR_MV`)."""
    from Working.library.view_filter import DEFAULT_FLOOR_MV, FLOOR_KEY, FLOOR_PAGE
    stem = os.path.splitext(os.path.basename(source_file))[0]
    for s in (stem, re.sub(r"_fs\d+(p\d+)?$", "", stem)):
        row = conn.execute("SELECT value_json FROM settings WHERE page = ? AND key = ?",
                           (FLOOR_PAGE, FLOOR_KEY.format(stem=s))).fetchone()
        if row is not None:
            try:
                v = float(json.loads(row["value_json"]))
                if v > 0:
                    return v, f"Settings › Datasets meta.{s}.noise_floor"
            except (TypeError, ValueError):
                pass
    return DEFAULT_FLOOR_MV, "the Library's instrument floor (none set for this dataset)"


def matching_rule(conn):
    from Working.discovery.matching import rule_from_settings
    return rule_from_settings(conn)


# ── the seed bank ───────────────────────────────────────────────────────────

def load_seed_bank(where=SEED_BANK):
    from Working.autodetect.seeds import SeedFamily
    with open(os.path.join(where, "seed_bank.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    arr = np.load(os.path.join(where, "seed_bank.npz"))
    fams = [SeedFamily(label=f["label"], exemplar_mv=np.asarray(arr[f["label"]], dtype=float),
                       exemplar_fs=float(f["exemplar_fs"]), durations_s=tuple(f["durations_s"]),
                       min_corr=float(f["min_corr"]), n_members=int(f["n_members"]), provenance=f["medoid"])
            for f in meta["families"]]
    return fams, meta


# ── R4 ──────────────────────────────────────────────────────────────────────

def load_r4_module():
    spec = importlib.util.spec_from_file_location("_autodetect_rq1b", os.path.join(ROOT, "scripts", "rq1b_minirocket.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_r4_scorer(conn, rec_id, offset, *, chunk=2048, model_path=R4_MODEL, invert=False):
    """``score(starts, ends) -> p`` for spans relative to ``offset`` on recording ``rec_id``: R4's own input rule
    (`rq1b_minirocket.extract`: the span plus a quarter of its length each side, mV, gaps under 5 % filled, 512
    points, the four side features) and its Platt probability. NaN where R4 could not read the span. ``invert``
    scores the spans of the inverted signal (the side features do not change sign)."""
    mr = load_r4_module()
    model = mr.load_model(model_path)

    def score(starts, ends):
        starts = np.asarray(starts, dtype=np.int64)
        ends = np.asarray(ends, dtype=np.int64)
        out = np.full(len(starts), np.nan)
        for i in range(0, len(starts), int(chunk)):
            rows = pd.DataFrame({"recording_id": int(rec_id), "start": starts[i:i + chunk] + int(offset),
                                 "end": ends[i:i + chunk] + int(offset)})
            M, side, keep = mr.extract(conn, rows)
            if keep.any():
                p = mr.probability(model, -M[keep] if invert else M[keep], side[keep].reset_index(drop=True))
                out[i:i + chunk][keep] = p
        return out

    return score


# ── the whole-drop rule a run uses ──────────────────────────────────────────

WHOLE_DROP = "Working/interrogation/whole_drop.py"


def pin_whole_drop(rev="HEAD"):
    """Load the whole-drop rule as COMMITTED at ``rev`` in place of the working copy, before anything imports it (the
    researcher, 2026-11-23: "use latest committed whole drop rule" - another session edits the working copy). Call it
    before importing `Working.autodetect`. Returns what was loaded: ``rev``, ``commit``, ``blob`` and whether the
    working copy differs."""
    import subprocess
    import types
    name = "Working.interrogation.whole_drop"
    git = lambda *a: subprocess.check_output(["git", *a], cwd=ROOT, text=True).strip()  # noqa: E731
    commit = git("rev-parse", "--short", rev)
    blob = git("rev-parse", f"{rev}:{WHOLE_DROP}")
    if name in sys.modules and getattr(sys.modules[name], "__pinned_blob__", None) != blob:
        raise RuntimeError("whole_drop was imported before it could be pinned")
    src = subprocess.check_output(["git", "show", f"{rev}:{WHOLE_DROP}"], cwd=ROOT)
    mod = types.ModuleType(name)
    mod.__file__ = os.path.join(ROOT, WHOLE_DROP)
    mod.__pinned_blob__ = blob
    exec(compile(src, f"git {commit}:{WHOLE_DROP}", "exec"), mod.__dict__)
    import Working.interrogation as pkg
    sys.modules[name] = mod
    pkg.whole_drop = mod
    return {"rev": rev, "commit": commit, "blob": blob[:12],
            "working_copy_differs": git("hash-object", WHOLE_DROP) != blob}


# ── what was reviewed on a stretch ──────────────────────────────────────────

def _load_catalogue_module():
    spec = importlib.util.spec_from_file_location("_autodetect_cat", os.path.join(ROOT, "scripts", "thesis",
                                                                                     "accepted_catalogue.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reviewed(conn, ref, rec, a, b):
    """The answer sheet on the stretch, in the run's own sample indices (relative to ``a``):

    * ``accepted`` — the 9 Nov accepted catalogue's spans on the physical channel (individual spans and accepted
      train members);
    * ``rejected`` — every own (not carried) not-interesting or artifact verdict on an event-sized span of the same
      physical channel, any copy (`accepted_catalogue.collect`, the catalogue's own reader);
    * ``windows`` — judged labelled windows (the old 10-minute labels and the blind test), interesting or not.
    """
    canon = recording(conn, ref["canonical"])
    factor = float(rec["fs"]) / float(canon["fs"])

    def to_run(s, e):
        return int(round(s * factor)) - a, int(round(e * factor)) - a

    def clip(df):
        if not len(df):
            return df
        df = df[(df["end"] > 0) & (df["start"] < (b - a))].copy()
        df["start"] = df["start"].clip(lower=0)
        df["end"] = df["end"].clip(upper=b - a)
        return df[df["end"] > df["start"]].reset_index(drop=True)

    cat = pd.read_csv(CATALOGUE)
    cat = cat[cat["recording_id"] == int(ref["canonical"])]
    acc = pd.DataFrame([dict(zip(("start", "end"), to_run(s, e))) | {"event_id": ev, "level": lv,
                                                                       "train_id": tr if isinstance(tr, str) else ""}
                        for s, e, ev, lv, tr in zip(cat["start_idx"], cat["end_idx"], cat["event_id"],
                                                    cat["acceptance_level"], cat["train_id"])],
                       columns=["start", "end", "event_id", "level", "train_id"])

    mod = _load_catalogue_module()
    c2 = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
    c2.row_factory = sqlite3.Row
    try:
        rows, _recs = mod.collect(c2)
    finally:
        c2.close()
    rej, win = [], []
    for r in rows:
        if int(r["canonical_recording_id"]) != int(ref["canonical"]) or r.get("placement_ambiguous"):
            continue
        s, e = to_run(r["canonical_start"], r["canonical_end"])
        if r["kind"] == "event_span" and r["verdict"] in ("not_interesting", "artifact"):
            rej.append({"start": s, "end": e, "ref": r["ref"], "verdict": r["verdict"]})
        elif r["kind"] == "labelled_window" and r["verdict"] in ("interesting", "not_interesting"):
            win.append({"start": s, "end": e, "ref": r["ref"], "verdict": r["verdict"]})
    rej = pd.DataFrame(rej, columns=["start", "end", "ref", "verdict"])
    win = pd.DataFrame(win, columns=["start", "end", "ref", "verdict"])
    return {"accepted": clip(acc), "rejected": clip(rej), "windows": clip(win)}
