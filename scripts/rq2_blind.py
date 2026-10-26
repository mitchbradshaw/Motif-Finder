"""
rq2_blind.py
============
RQ2, judged blind (the researcher, 2026-10-26: "more seed search results reviewed, but blind").

In plain words
--------------
The seed searches look very good: the researcher accepted almost everything they found. But each match was judged
knowing it was a match, and the 22 % "interesting" rate it is compared with came from a different, blind queue. This
script mixes seed matches, matches the researcher already accepted (to be judged again), and random windows of the
same lengths on the same channels into ONE shuffled Review queue in which nothing says what an item is. Afterwards
it scores each source against the random windows, with intervals, and checks how often the earlier "yes" survives a
blind second look.

Three commands
--------------
    build   the panel. A DRY RUN by default (reads the database read-only, prints the composition, writes nothing).
            With --apply it backs the database up, writes one machine run per channel holding fresh detections over
            the chosen spans (no score, no meta, one neutral name), creates the blind queue — through the bridge's
            own ``POST /api/review/queues`` when --url is given — and writes the key, which maps every item to its
            source, to ``DATA/derived/rq2_blind/<stamp>/key.json``: outside the database and outside anything the
            app serves.
    score   read-only. Reads the queue's verdicts (carried copies, ``adjudications.carried_from`` set, are not
            looks and are left out), and writes ``docs/rq_roundA_2/findings/rq2-blind-<date>.md`` and ``.json``:
            acceptance per source with 95 % Wilson intervals, each seed against its duration-matched controls
            (difference with Newcombe's interval, Fisher's exact p), and blind-vs-earlier agreement.
            ``--synthetic`` scores invented verdicts held in memory (a dry run of the scoring; nothing is written
            to any database, and the output goes to --out).
    nulls   read-only, needs no judging: per seed per channel, the matches under the cut against the surrogate
            matches at the same line (mean and 95th percentile over the 200 phase-randomised draws).

Why fresh detections
--------------------
An earlier-accepted match must be a fresh look, but its detection already carries the verdict (Review would serve
it judged, or not at all). A random window has no detection. And a seed run's detection names its run, which the
item card shows. So every item, of every source, is a NEW machine detection in a panel run per channel: the run id
says only the channel (which the card shows anyway), the detection ids rise with the serving order, and no score is
stored. Detections stay machine-only and verdicts human-only (CLAUDE.md rule 5): this writes no verdict.

The real database is named only with --real (`scripts/backfill_seed_entry_ids.py`'s guard). Dev tooling: nothing
under Working/, Adapters/ or Pipelines/ imports it.

    python scripts/rq2_blind.py build --real                          # dry run: composition only
    python scripts/rq2_blind.py build --real --apply --url http://127.0.0.1:8765
    python scripts/rq2_blind.py nulls --real
    python scripts/rq2_blind.py score --real --key DATA/derived/rq2_blind/<stamp>/key.json
    python scripts/rq2_blind.py score --real --key <key> --synthetic --out <scratch dir>
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import math
import os
import pathlib
import sqlite3
import sys
import urllib.request
from collections import Counter

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Working.database import runs as _runs  # noqa: E402
from Working.discovery import seeded_search as _ss  # noqa: E402
from Working.discovery.spans import absolute_bounds  # noqa: E402
from Working.review import queues as _queues  # noqa: E402


def _guard():
    spec = importlib.util.spec_from_file_location("_rq2_real_db_guard",
                                                  os.path.join(ROOT, "scripts", "backfill_seed_entry_ids.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SOURCE_FILE = "M2_aug_concat_fs1.mat"
HPC_DIR = os.path.join(ROOT, "HPC", "Detection", "generated")
KEY_ROOT = os.path.join(ROOT, "DATA", "derived", "rq2_blind")
FINDINGS = os.path.join(ROOT, "docs", "rq_roundA_2", "findings")

PANEL_KIND = "rq2-blind-panel"
PANEL_RUN_NAME = "blind panel"
VERDICTS = ["interesting", "not_interesting", "unsure", "artifact"]
ACCEPTED = ("interesting", "seed")
QUEUE_NOTE = ("A mixed, shuffled set of spans. Judge each on its own: interesting, not_interesting, unsure or "
              "artifact. What each item is stays outside the app until the panel is scored.")

#: The seeds. `discovery_run`: the Discovery run row whose `run_ids` hold the seed run's detections; `result`: the
#: cluster's result file (candidates and 200 null draws per channel); `m`: the seed's length in samples (= s at 1 Hz).
SEEDS = {
    "drop30": {"title": "drop, family 30 (Library entry 185)", "result": "drop30_allch_16ch_0-2595600",
               "discovery_run": 67, "m": 377, "cut": "line"},
    "spike37": {"title": "spike, family 37 (Library entry 289)", "result": "spike37_allch_16ch_0-2595600",
                "discovery_run": 68, "m": 148, "cut": "per_channel"},
    "longdip_id020": {"title": "long dip id020 (family 23 medoid)", "result": "dip_search_allch_16ch_0-2595600",
                      "discovery_run": 13, "m": 816, "judged_cut": 3.8668},
    "dip_id010": {"title": "dip id010 (family 24 medoid)", "result": "dip_search_3ch_0-2595600",
                  "discovery_run": 9, "m": 105, "judged_cut": 2.652},
    "s056": {"title": "seed_056a5d (family 30 medoid, Library entry 191; 5-draw preview null)",
             "result": None, "discovery_run": 311, "m": 364},
}
#: each panel group and the control length it is compared with
GROUP_SEED = {"drop30": "drop30", "spike37": "spike37", "rejudge_dip_id010": "dip_id010",
              "rejudge_longdip_id020": "longdip_id020", "s056": "s056"}
GROUP_TITLES = {
    "drop30": "drop30 matches (new, under the null's line)",
    "spike37": "spike37 matches (new, under each channel's own cut)",
    "rejudge_dip_id010": "dip id010 matches accepted earlier, judged again",
    "rejudge_longdip_id020": "long dip id020 matches accepted earlier, judged again",
    "s056": "seed_056a5d kept matches",
    "control": "random windows (all lengths)",
}


# ── statistics ───────────────────────────────────────────────────────────────

def wilson(k, n, z=1.96):
    """The 95 % Wilson score interval for k of n; (None, None) for n = 0."""
    if not n:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe(k1, n1, k2, n2):
    """p1 - p2 with Newcombe's hybrid-score interval (method 10)."""
    if not n1 or not n2:
        return (None, None, None)
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return (d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def fisher_p(k1, n1, k2, n2):
    try:
        from scipy.stats import fisher_exact
    except Exception:          # pragma: no cover - scipy is in the conda env
        return None
    if not n1 or not n2:
        return None
    return float(fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])[1])


def kappa(table):
    """Cohen's kappa of a 2 x 2 table [[yes-yes, yes-no], [no-yes, no-no]]; None when undefined."""
    (a, b), (c, d) = table
    n = a + b + c + d
    if not n:
        return None
    if 0 in (a + b, c + d, a + c, b + d):
        return None         # one look said the same thing every time: agreement beyond chance is undefined
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    return (po - pe) / (1 - pe)


def null_counts_per_draw(null, k, cut):
    """How many surrogate matches each draw gives at or below `cut`. The result file pools each draw's k
    distances in draw order, so draw i is ``distances[i*k:(i+1)*k]``."""
    ds = np.asarray(null.get("distances") or [], dtype=float)
    draws = int(null.get("draws") or 0)
    if not draws or ds.size != draws * k:
        raise ValueError(f"null has {ds.size} distances for {draws} draws of k = {k}: not one block per draw")
    return (ds.reshape(draws, k) <= float(cut)).sum(axis=1)


def null_row(distances, null, k, cut):
    if cut is None:
        return {"cut": None, "real": 0, "null_mean": None, "null_p95": None, "null_max": None, "draws": 0}
    per = null_counts_per_draw(null, k, cut)
    return {"cut": float(cut), "real": int(sum(1 for d in distances if float(d) <= float(cut))),
            "null_mean": float(per.mean()), "null_p95": float(np.percentile(per, 95)), "null_max": int(per.max()),
            "draws": int(per.size), "_per_draw": per}


# ── sampling ─────────────────────────────────────────────────────────────────

def allocate(weights, n):
    """Largest-remainder split of n over `weights` (ties to the larger weight, then the key)."""
    total = sum(weights.values())
    if not total or n <= 0:
        return {k: 0 for k in weights}
    raw = {k: n * w / total for k, w in weights.items()}
    got = {k: int(math.floor(v)) for k, v in raw.items()}
    left = n - sum(got.values())
    for k in sorted(weights, key=lambda k: (-(raw[k] - got[k]), -weights[k], str(k)))[:left]:
        got[k] += 1
    return got


def _overlaps(spans, a, b):
    return any(a < fb and fa < b for fa, fb in spans)


def sample_controls(rng, per_channel, length, n_samples, forbidden, ok, max_tries=50_000):
    """`per_channel[rid]` windows of `length` samples on each channel, uniform over the channel, none overlapping a
    span in ``forbidden[rid]`` (updated with every window chosen, so they never overlap each other) and each passing
    ``ok(rid, a, b)``. Raises if a channel cannot be filled."""
    out = []
    for rid in sorted(per_channel):
        need, tries = int(per_channel[rid]), 0
        spans = forbidden.setdefault(rid, [])
        while need > 0:
            tries += 1
            if tries > max_tries:
                raise RuntimeError(f"recording {rid}: could not place {need} more windows of {length} samples")
            a = int(rng.integers(0, int(n_samples[rid]) - length + 1))
            b = a + length
            if _overlaps(spans, a, b) or not ok(rid, a, b):
                continue
            spans.append((a, b))
            out.append((rid, a, b))
            need -= 1
    return out


def shuffle(rng, items):
    """The serving order: a seeded permutation. Each item gets `serve_rank` (1-based)."""
    order = rng.permutation(len(items))
    out = []
    for rank, i in enumerate(order, start=1):
        it = dict(items[int(i)])
        it["serve_rank"] = rank
        out.append(it)
    return out


# ── writing the panel ────────────────────────────────────────────────────────

def _core_queue(conn, name, ids):
    return int(_queues.create_queue(conn, name=name, source_kind="discovery-run",
                                    filters={"detection_ids": ids, "order": "listed"}, blind=True,
                                    verdict_options=VERDICTS, note=QUEUE_NOTE))


def bridge_queue(url):
    """A queue maker that goes through the running bridge's own route (the UI's)."""
    def make(conn, name, ids):
        body = json.dumps({"name": name, "source_kind": "discovery-run", "blind": True,
                           "verdict_options": VERDICTS, "note": QUEUE_NOTE,
                           "filters": {"detection_ids": ids, "order": "listed"}}).encode()
        req = urllib.request.Request(url.rstrip("/") + "/api/review/queues", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return int(json.loads(r.read())["queue"]["id"])
    return make


def write_panel(conn, items, *, stamp, key_dir, make_queue=None, extra_key=None, db_path=None):
    """One panel run per channel, a fresh detection per item IN SERVING ORDER (score and meta empty), one blind
    listed queue over them, and the key file. Returns ``{queue_id, key_path, items}``."""
    if conn.execute("SELECT 1 FROM configs WHERE config_json LIKE ?", (f'%"{stamp}"%{PANEL_KIND}%',)).fetchone() \
            or conn.execute("SELECT 1 FROM configs WHERE config_json LIKE ?",
                            (f'%{PANEL_KIND}%"{stamp}"%',)).fetchone():
        raise ValueError(f"a blind panel with stamp {stamp} is already in this database")
    items = sorted(items, key=lambda it: it["serve_rank"])
    cfg_id, _ = _runs.get_or_create_config(conn, {"kind": PANEL_KIND, "stamp": stamp})
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    run_of = {}
    with conn:
        for rid in sorted({int(it["recording_id"]) for it in items}):
            n = conn.execute("SELECT n_samples FROM recordings WHERE id = ?", (rid,)).fetchone()[0]
            cur = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                               "name, finished_at) VALUES (?, ?, 0, ?, ?, 'completed', ?, ?)",
                               (cfg_id, rid, int(n), now, PANEL_RUN_NAME, now))
            run_of[rid] = int(cur.lastrowid)
        out = []
        for it in items:
            cur = conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
                               "VALUES (?, ?, ?, NULL, NULL)",
                               (run_of[int(it["recording_id"])], int(it["start"]), int(it["end"])))
            out.append({**it, "panel_detection_id": int(cur.lastrowid),
                        "panel_run_id": run_of[int(it["recording_id"])]})
    ids = [it["panel_detection_id"] for it in out]
    name = f"RQ2 blind panel · {stamp}"
    qid = (make_queue or _core_queue)(conn, name, ids)
    os.makedirs(key_dir, exist_ok=True)
    key = {"version": 1, "stamp": stamp, "queue_id": qid, "queue_name": name, "created_at": now,
           "database": db_path, "panel_config_id": cfg_id, "panel_run_ids": run_of,
           "accepted_words": list(ACCEPTED), **(extra_key or {}), "items": out}
    path = os.path.join(key_dir, "key.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(key, f, indent=1)
    return {"queue_id": qid, "key_path": path, "items": out}


# ── reading the real sources ─────────────────────────────────────────────────

def load_result(name):
    with open(os.path.join(HPC_DIR, name + ".result.json"), encoding="utf-8") as f:
        return json.load(f)


def seed_cuts(result, rule):
    chans = [{"distances": [c["distance"] for c in ch["candidates"]], "null": ch["null"]}
             for ch in result["perChannel"]]
    rc = _ss.recommended_cut_corrected(chans, alpha=rule["alpha"], correction=rule["correction"])
    own = {ch["name"]: pc["cut"] for ch, pc in zip(result["perChannel"], rc["per_channel"])}
    return rc["cut"], own, rc


def _recordings(conn):
    rows = conn.execute("SELECT id, channel, n_samples, npy_path FROM recordings WHERE source_file = ?",
                        (SOURCE_FILE,)).fetchall()
    return {int(r[1]): {"id": int(r[0]), "n": int(r[2]), "npy": r[3]} for r in rows}


def _run_ids(conn, discovery_run):
    p = json.loads(conn.execute("SELECT params_json FROM discovery_runs WHERE id = ?",
                                (discovery_run,)).fetchone()[0])
    return [int(x) for x in p.get("run_ids") or []]


def _detections_of(conn, run_ids):
    """``[(detection_id, recording_id, start, end, score, verdict, carried)]`` over the runs, channel-absolute;
    the verdict is the row's latest adjudication (None when unjudged)."""
    marks = ",".join("?" * len(run_ids))
    rows = conn.execute(
        f"SELECT d.id, r.recording_id, d.start_idx, d.end_idx, d.score, r.span_start, "
        f"(SELECT a.verdict FROM adjudications a WHERE a.detection_id = d.id ORDER BY a.id DESC LIMIT 1), "
        f"(SELECT a.carried_from FROM adjudications a WHERE a.detection_id = d.id ORDER BY a.id DESC LIMIT 1) "
        f"FROM detections d JOIN runs r ON r.id = d.run_id WHERE d.run_id IN ({marks})", run_ids).fetchall()
    out = []
    for did, rid, s, e, score, s0, verdict, carried in rows:
        a, b = absolute_bounds(s, e, s0)
        out.append((int(did), int(rid), a, b, score, verdict, carried is not None))
    return out


def _prior(conn, cands):
    """Review's own rediscovery rule (`queues._prior_verdicts`): an item that is the same event as a span a person
    already judged is never served, so it cannot be in the panel. Applied alike to matches and controls."""
    rows = [{"id": i, "run_id": -1, "recording_id": c[0], "start_idx": c[1], "end_idx": c[2]}
            for i, c in enumerate(cands)]
    return set(_queues._prior_verdicts(conn, rows))


def build_items(conn, a, rng):
    rule = _ss.cut_rule_from_settings(conn)
    recs = _recordings(conn)
    rid_of = {ch: r["id"] for ch, r in recs.items()}
    n_of = {r["id"]: r["n"] for r in recs.values()}
    results = {k: load_result(v["result"]) for k, v in SEEDS.items() if v["result"]}
    name_of = {rid_of[ch["channel"]]: ch["name"] for ch in results["drop30"]["perChannel"]}
    comp = {"rule": rule, "pools": {}, "chosen": {}, "excluded_prior": {}, "seeds": {}}
    forbidden = {}

    def forbid(rid, s, e):
        forbidden.setdefault(rid, []).append((int(s), int(e)))

    # every seed's matches, whatever is chosen, are off limits to a control
    for key, seed in SEEDS.items():
        m = seed["m"]
        for det in _detections_of(conn, _run_ids(conn, seed["discovery_run"])):
            if key in ("drop30", "spike37"):
                continue        # those runs keep all 200 per channel; their matches are the cut's, below
            forbid(det[1], det[2], det[3])
        if seed["result"]:
            line, own, _ = seed_cuts(results[key], rule)
            for ch in results[key]["perChannel"]:
                lim = max([c for c in (line, own.get(ch["name"]), seed.get("judged_cut")) if c is not None],
                          default=None)
                for c in ch["candidates"]:
                    if lim is not None and c["distance"] <= lim:
                        forbid(rid_of[ch["channel"]], c["index"], c["index"] + m)
    taken = {}

    def free(rid, s, e):
        return not _overlaps(taken.get(rid, []), s, e)

    def take(rid, s, e):
        taken.setdefault(rid, []).append((s, e))

    items = []

    def seed_det_lookup(key):
        idx = {}
        for det in _detections_of(conn, _run_ids(conn, SEEDS[key]["discovery_run"])):
            idx[(det[1], det[2])] = det
        return idx

    # 1. the re-judges: earlier ACCEPTED (a person's own verdict, not a carried copy), sampled at random
    for group, key, n in (("rejudge_dip_id010", "dip_id010", a.n_rejudge_dip),
                          ("rejudge_longdip_id020", "longdip_id020", a.n_rejudge_longdip)):
        pool = [d for d in _detections_of(conn, _run_ids(conn, SEEDS[key]["discovery_run"]))
                if d[5] in ACCEPTED and not d[6]]
        # discovery runs 9-11 share one set of runs; a detection is one item
        pool = sorted({(d[1], d[2]): d for d in pool}.values())
        prior = _prior(conn, [(d[1], d[2], d[3]) for d in pool])
        comp["excluded_prior"][group] = len(prior)
        pool = [d for i, d in enumerate(pool) if i not in prior]
        comp["pools"][group] = len(pool)
        got = 0
        for i in rng.permutation(len(pool)):
            d = pool[int(i)]
            if got >= n:
                break
            if not free(d[1], d[2], d[3]):
                continue
            take(d[1], d[2], d[3])
            items.append({"group": group, "seed": key, "recording_id": d[1], "channel": name_of[d[1]],
                          "start": d[2], "end": d[3], "length": d[3] - d[2],
                          "source": {"discovery_run": SEEDS[key]["discovery_run"], "detection_id": d[0],
                                     "score": d[4]},
                          "earlier": {"verdict": d[5], "detection_id": d[0]}})
            got += 1
        comp["chosen"][group] = got

    # 2. the new matches: spike37 under each channel's own cut (all of them), drop30 under the line, by channel
    for group, n in (("spike37", a.n_spike37), ("drop30", a.n_drop30)):
        seed = SEEDS[group]
        res, m = results[group], seed["m"]
        line, own, rc = seed_cuts(res, rule)
        comp["seeds"][group] = {"line": line, "own_cuts": own, "channels_passing": rc["channels_passing"]}
        pool = []
        for ch in res["perChannel"]:
            cut = line if seed["cut"] == "line" else own.get(ch["name"])
            if cut is None:
                continue
            for rank, c in enumerate(sorted(ch["candidates"], key=lambda c: c["distance"]), start=1):
                if c["distance"] <= cut:
                    pool.append((rid_of[ch["channel"]], int(c["index"]), int(c["index"]) + m,
                                 float(c["distance"]), rank, ch["name"]))
        comp["pools"][group + "_under_cut"] = len(pool)
        prior = _prior(conn, [(p[0], p[1], p[2]) for p in pool])
        comp["excluded_prior"][group] = len(prior)
        pool = [p for i, p in enumerate(pool) if i not in prior]
        comp["pools"][group] = len(pool)
        dets = seed_det_lookup(group)
        by_ch = {}
        for p in pool:
            by_ch.setdefault(p[0], []).append(p)
        quota = allocate({rid: len(v) for rid, v in by_ch.items()}, min(n, len(pool)))
        got = 0
        for rid in sorted(by_ch):
            cand = by_ch[rid]
            k = 0
            for i in rng.permutation(len(cand)):
                if k >= quota[rid]:
                    break
                p = cand[int(i)]
                if not free(rid, p[1], p[2]):
                    continue
                take(rid, p[1], p[2])
                det = dets.get((rid, p[1]))
                earlier = None
                if det is not None and det[5] is not None and not det[6]:
                    earlier = {"verdict": det[5], "detection_id": det[0]}
                items.append({"group": group, "seed": group, "recording_id": rid, "channel": p[5],
                              "start": p[1], "end": p[2], "length": m,
                              "source": {"discovery_run": seed["discovery_run"], "result": seed["result"],
                                         "distance": p[3], "rank_in_channel": p[4],
                                         "detection_id": det[0] if det else None},
                              "earlier": earlier})
                k += 1
                got += 1
        comp["chosen"][group] = got

    # 3. optional: seed_056a5d's kept matches
    if a.n_s056:
        pool = sorted({(d[1], d[2]): d for d in _detections_of(conn, _run_ids(conn, 311))}.values())
        prior = _prior(conn, [(d[1], d[2], d[3]) for d in pool])
        comp["excluded_prior"]["s056"] = len(prior)
        pool = [d for i, d in enumerate(pool) if i not in prior]
        comp["pools"]["s056"] = len(pool)
        got = 0
        for i in rng.permutation(len(pool)):
            d = pool[int(i)]
            if got >= a.n_s056:
                break
            if not free(d[1], d[2], d[3]):
                continue
            take(d[1], d[2], d[3])
            items.append({"group": "s056", "seed": "s056", "recording_id": d[1], "channel": name_of[d[1]],
                          "start": d[2], "end": d[3], "length": d[3] - d[2],
                          "source": {"discovery_run": 311, "detection_id": d[0], "score": d[4]},
                          "earlier": ({"verdict": d[5], "detection_id": d[0]} if d[5] and not d[6] else None)})
            got += 1
        comp["chosen"]["s056"] = got

    # 4. the controls: per length, on the channels of the items of that length, in proportion; never on a match
    for rid, spans in taken.items():
        forbidden.setdefault(rid, []).extend(spans)
    lengths = {}
    for it in items:
        lengths.setdefault(int(it["length"]), Counter())[it["recording_id"]] += 1
    want = {377: a.controls_377, 148: a.controls_148, 105: a.controls_105, 816: a.controls_816,
            364: a.controls_364 if a.n_s056 else 0}
    arrays = {}

    def ok(rid, s, e):
        if _prior(conn, [(rid, s, e)]):
            return False
        ch = next(c for c, r in recs.items() if r["id"] == rid)
        if rid not in arrays:
            arrays[rid] = np.load(os.path.join(ROOT, recs[ch]["npy"]), mmap_mode="r")
        w = np.asarray(arrays[rid][s:e], dtype=float)
        return bool(np.isfinite(w).all() and np.nanstd(w) > 0)

    comp["controls"] = {}
    for length, n in want.items():
        if not n or length not in lengths:
            continue
        per = allocate(dict(lengths[length]), n)
        got = sample_controls(rng, {r: c for r, c in per.items() if c}, length, n_of, forbidden, ok)
        for rid, s, e in got:
            items.append({"group": "control", "seed": None, "control_length": length, "recording_id": rid,
                          "channel": name_of[rid], "start": s, "end": e, "length": length,
                          "source": {"uniform": True}, "earlier": None})
        comp["controls"][length] = len(got)
    comp["by_group"] = dict(Counter(it["group"] for it in items))
    comp["total"] = len(items)
    return items, comp


# ── scoring ──────────────────────────────────────────────────────────────────

def _verdicts(conn, ids):
    out = {}
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        for did, verdict, carried in conn.execute(
                "SELECT detection_id, verdict, carried_from FROM adjudications WHERE detection_id IN ({}) "
                "ORDER BY id".format(",".join("?" * len(chunk))), chunk):
            out[int(did)] = (verdict, carried is not None)
    return out


def _tally(rows):
    c = Counter(v for v in rows)
    judged = len(rows)
    acc = sum(c[w] for w in ACCEPTED)
    decided = acc + c["not_interesting"]
    lo, hi = wilson(acc, judged)
    lo2, hi2 = wilson(acc, decided)
    return {"judged": judged, "accepted": acc, "not_interesting": c["not_interesting"], "unsure": c["unsure"],
            "artifact": c["artifact"], "rate": (acc / judged) if judged else None, "ci": [lo, hi],
            "decided": decided, "rate_decided": (acc / decided) if decided else None, "ci_decided": [lo2, hi2]}


def score(conn, key, *, synthetic=None, seed=0):
    """The panel's verdicts, scored. `synthetic`: ``{group: p_accept}`` — invented verdicts held in memory, no
    database row read for them or written."""
    items = key["items"]
    if synthetic is not None:
        rng = np.random.default_rng(seed)
        got = {}
        for it in items:
            p = synthetic.get(it["group"], synthetic.get("default", 0.5))
            got[it["panel_detection_id"]] = ("interesting" if rng.random() < p else "not_interesting", False)
    else:
        got = _verdicts(conn, [int(it["panel_detection_id"]) for it in items])
    groups, carried, unjudged = {}, Counter(), Counter()
    per_group_rows = {}
    for it in items:
        g = it["group"]
        names = [g] + ([f"control@{it['control_length']}"] if g == "control" else [])
        v = got.get(int(it["panel_detection_id"]))
        for nm in names:
            per_group_rows.setdefault(nm, [])
            if v is None:
                unjudged[nm] += 1
            elif v[1]:
                carried[nm] += 1
            else:
                per_group_rows[nm].append(v[0])
    for nm, rows in per_group_rows.items():
        t = _tally(rows)
        t.update({"in_panel": len(rows) + carried[nm] + unjudged[nm], "carried_excluded": carried[nm],
                  "unjudged": unjudged[nm]})
        groups[nm] = t
    comparisons = []
    pooled = groups.get("control")
    for g, sk in GROUP_SEED.items():
        if g not in groups:
            continue
        length = SEEDS[sk]["m"]
        ctl = groups.get(f"control@{length}")
        row = {"group": g, "length": length}
        for label, c in (("matched", ctl), ("pooled", pooled)):
            if c is None:
                continue
            k1, n1, k2, n2 = groups[g]["accepted"], groups[g]["judged"], c["accepted"], c["judged"]
            d, lo, hi = newcombe(k1, n1, k2, n2)
            row[label] = {"control_accepted": k2, "control_judged": n2, "diff": d, "ci": [lo, hi],
                          "fisher_p": fisher_p(k1, n1, k2, n2),
                          "ratio": ((k1 / n1) / (k2 / n2)) if n1 and n2 and k2 else None}
        comparisons.append(row)
    # blind against the earlier, unblinded look
    pairs, by_group = [], {}
    for it in items:
        e = it.get("earlier")
        v = got.get(int(it["panel_detection_id"]))
        if not e or not e.get("verdict") or v is None or v[1]:
            continue
        pairs.append((e["verdict"] in ACCEPTED, v[0] in ACCEPTED, e["verdict"], v[0], it["group"]))
    table = [[sum(1 for p in pairs if p[0] and p[1]), sum(1 for p in pairs if p[0] and not p[1])],
             [sum(1 for p in pairs if not p[0] and p[1]), sum(1 for p in pairs if not p[0] and not p[1])]]
    for p in pairs:
        by_group.setdefault(p[4], Counter())[(p[2], p[3])] += 1
    earlier_acc = [p for p in pairs if p[0]]
    still = sum(1 for p in earlier_acc if p[1])
    agreement = {"n": len(pairs), "earlier_accepted": len(earlier_acc), "still_accepted": still,
                 "still_rate": (still / len(earlier_acc)) if earlier_acc else None,
                 "still_ci": list(wilson(still, len(earlier_acc))), "table": table, "kappa": kappa(table),
                 "by_group": {g: {f"{a} -> {b}": n for (a, b), n in c.items()} for g, c in by_group.items()}}
    return {"synthetic": synthetic is not None, "queue_id": key["queue_id"], "stamp": key["stamp"],
            "groups": groups, "comparisons": comparisons, "agreement": agreement}


# ── the null table (no judging) ──────────────────────────────────────────────

def null_tables(rule):
    out = {}
    for key, seed in SEEDS.items():
        if not seed["result"]:
            continue
        res = load_result(seed["result"])
        k = int(res["k"])
        line, own, rc = seed_cuts(res, rule)
        rows, totals = [], {}
        for ch in res["perChannel"]:
            ds = [c["distance"] for c in ch["candidates"]]
            row = {"channel": ch["name"], "closest": min(ds)}
            for label, cut in (("line", line), ("own", own.get(ch["name"])), ("judged", seed.get("judged_cut"))):
                if label == "judged" and cut is None:
                    continue
                r = null_row(ds, ch["null"], k, cut)
                per = r.pop("_per_draw", None)
                row[label] = r
                if per is not None and label != "own":
                    t = totals.setdefault(label, {"real": 0, "per": np.zeros(per.size)})
                    t["real"] += r["real"]
                    t["per"] = t["per"] + per
            rows.append(row)
        tot = {lab: {"real": int(t["real"]), "null_mean": float(t["per"].mean()),
                     "null_p95": float(np.percentile(t["per"], 95)), "null_max": int(t["per"].max())}
               for lab, t in totals.items()}
        own_real = sum(r["own"]["real"] for r in rows)
        own_null = sum(r["own"]["null_mean"] or 0 for r in rows if r["own"]["cut"] is not None)
        out[key] = {"title": seed["title"], "result": seed["result"], "specHash": res.get("specHash"),
                    "draws": int(res["null"]["draws"]), "method": res["null"]["method"], "k": k, "m": seed["m"],
                    "line": line, "judged_cut": seed.get("judged_cut"), "channels_passing": rc["channels_passing"],
                    "channels": len(rows), "rows": rows, "totals": tot,
                    "own_total": {"real": own_real, "null_mean_sum": own_null}}
    return out


# ── markdown ─────────────────────────────────────────────────────────────────

def _f(x, nd=1):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def _p(x):
    return "—" if x is None else ("< 0.0001" if x < 1e-4 else f"{x:.4f}")


def _pct(x):
    return "—" if x is None else f"{100 * x:.0f} %"


def _ci(ci):
    return "—" if not ci or ci[0] is None else f"{100 * ci[0]:.0f}–{100 * ci[1]:.0f} %"


def render_nulls(nt, rule):
    L = ["## The null at each seed's cut (needs no judging)", "",
         "In plain words: for each seed the search was also run 200 times on scrambled copies of each channel "
         "(phase randomisation keeps a channel's spectrum and destroys its shapes). If the real channel gives many "
         "more matches under the cut than a scrambled copy does, the matches are not what chance gives. "
         "\"Null mean\" is the average number of scrambled matches per draw at the same line; \"p95\" is the "
         "95th percentile over the 200 draws.", "",
         f"Cut rule: α = {rule['alpha']} per null draw, correction: {rule['correction']} "
         "(Settings › Nulls). **Line** is the one cut the Seed page draws (the strictest passing channel's); "
         "**own** is each channel's own cut; **judged** is the cut the earlier, unblinded judging used.", ""]
    for key, t in nt.items():
        L += [f"### {key}: {t['title']}", "",
              f"`HPC/Detection/generated/{t['result']}.result.json` · spec `{t['specHash']}` · {t['m']} s seed · "
              f"k = {t['k']} per channel · {t['draws']} {t['method']} draws · {t['channels_passing']} of "
              f"{t['channels']} channels beat their own null · line d ≤ {_f(t['line'], 3)}"
              + (f" · judged at d ≤ {t['judged_cut']}" if t["judged_cut"] else ""), ""]
        head = "| channel | closest | real ≤ line | null mean | null p95 | own cut | real ≤ own | null mean (own) |"
        sep = "|---|---|---|---|---|---|---|---|"
        if t["judged_cut"]:
            head += " real ≤ judged | null mean (judged) | null p95 (judged) |"
            sep += "---|---|---|"
        L += [head, sep]
        for r in t["rows"]:
            ln, ow = r["line"], r["own"]
            s = (f"| {r['channel']} | {r['closest']:.3f} | {ln['real']} | {_f(ln['null_mean'], 2)} | "
                 f"{_f(ln['null_p95'])} | {_f(ow['cut'], 3)} | {ow['real']} | {_f(ow['null_mean'], 2)} |")
            if t["judged_cut"]:
                j = r["judged"]
                s += f" {j['real']} | {_f(j['null_mean'], 2)} | {_f(j['null_p95'])} |"
            L.append(s)
        tl = t["totals"].get("line", {})
        s = (f"| **all** | | **{tl.get('real', 0)}** | **{_f(tl.get('null_mean'), 2)}** | "
             f"**{_f(tl.get('null_p95'))}** | | **{t['own_total']['real']}** | "
             f"**{_f(t['own_total']['null_mean_sum'], 2)}** |")
        if t["judged_cut"]:
            tj = t["totals"].get("judged", {})
            s += f" **{tj.get('real', 0)}** | **{_f(tj.get('null_mean'), 2)}** | **{_f(tj.get('null_p95'))}** |"
        L += [s, "", "The *all* row's null figures are per draw summed over channels (draw i of every channel is "
              "one scrambled recording); the own-cut null is the sum of the channels' means. A line and an own "
              "cut are chosen so the null gives at most α per draw on their channel, so the null column is small by "
              "construction there; the finding is how many real matches sit under the same line. The judged cut "
              "was not chosen against this null.", ""]
    return L


def render_score(res, key):
    g = res["groups"]
    L = ["## The blind panel", "",
         "In plain words: every item below was judged in one shuffled queue that did not say where it came from. "
         "*Accepted* is interesting (or seed). The rate is accepted over everything judged, unsure and artifact "
         "included; the second rate leaves unsure and artifact out (the earlier poster's way). The interval is a "
         "95 % Wilson interval. A carried verdict (a copy of another verdict, `carried_from` set) is not a look and "
         "is left out.", ""]
    if res["synthetic"]:
        L += ["> **SYNTHETIC VERDICTS** — invented in memory to dry-run this report. Nothing here is a finding.", ""]
    L += [f"Queue {res['queue_id']} · stamp `{res['stamp']}`", "",
          "| source | in panel | judged | accepted | not | unsure | artifact | rate | 95 % CI | rate (decided) | "
          "95 % CI | carried (left out) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = list(GROUP_SEED) + ["control"] + sorted(k for k in g if k.startswith("control@"))
    for nm in order:
        if nm not in g:
            continue
        t = g[nm]
        title = GROUP_TITLES[nm] if nm in GROUP_TITLES else f"random windows of {nm.split('@')[-1]} s"
        L.append(f"| {title} | {t['in_panel']} | {t['judged']} | {t['accepted']} | {t['not_interesting']} | "
                 f"{t['unsure']} | {t['artifact']} | {_pct(t['rate'])} | {_ci(t['ci'])} | "
                 f"{_pct(t['rate_decided'])} | {_ci(t['ci_decided'])} | {t['carried_excluded']} |")
    L += ["", "### Each seed against random windows (the blinded comparison)", "",
          "The difference is the seed's rate minus the controls' (percentage points) with Newcombe's 95 % interval; "
          "p is Fisher's exact test. *Matched*: random windows of the seed's own length, on the same channels in "
          "the same proportions. *Pooled*: every random window.", "",
          "| source | length | vs | control rate | difference | 95 % CI | Fisher p | ratio |",
          "|---|---|---|---|---|---|---|---|"]
    for row in res["comparisons"]:
        for label in ("matched", "pooled"):
            c = row.get(label)
            if not c:
                continue
            rate = c["control_accepted"] / c["control_judged"] if c["control_judged"] else None
            diff = "—" if c["diff"] is None else f"{100 * c['diff']:+.0f} pts"
            ci = "—" if c["ci"][0] is None else f"{100 * c['ci'][0]:+.0f} to {100 * c['ci'][1]:+.0f}"
            L.append(f"| {row['group']} | {row['length']} s | {label} ({c['control_accepted']}/{c['control_judged']})"
                     f" | {_pct(rate)} | {diff} | {ci} | {_p(c['fisher_p'])} | {_f(c['ratio'], 2)} |")
    a = res["agreement"]
    L += ["", "### Blind against the earlier, unblinded look", "",
          "Items that had a person's own verdict before (the re-judges, and any new match judged in an earlier "
          "queue) against the blind verdict now. *Still accepted* is the share of earlier yeses that stay yes.", "",
          f"- pairs: {a['n']}; earlier accepted: {a['earlier_accepted']}; still accepted blind: {a['still_accepted']}"
          f" ({_pct(a['still_rate'])}, 95 % CI {_ci(a['still_ci'])})",
          f"- table [earlier yes/no × blind yes/no]: {a['table']}; Cohen's κ: {_f(a['kappa'], 2)}"]
    for grp, c in a["by_group"].items():
        L.append(f"- {grp}: " + ", ".join(f"{k}: {v}" for k, v in sorted(c.items())))
    return L


def _composition_md(comp):
    if not comp:
        return []
    L = ["## The panel's composition", "",
         "| group | pool (eligible) | left out: already judged as a human span | in the panel |",
         "|---|---|---|---|"]
    for g, n in comp.get("by_group", {}).items():
        if g == "control":
            continue
        L.append(f"| {GROUP_TITLES.get(g, g)} | {comp['pools'].get(g, '—')} | {comp['excluded_prior'].get(g, '—')} "
                 f"| {n} |")
    for length, n in sorted((comp.get("controls") or {}).items(), key=lambda kv: int(kv[0])):
        L.append(f"| random windows of {length} s | uniform on the same channels, off every match | — | {n} |")
    L += [f"| **total** | | | **{comp.get('total')}** |", ""]
    return L


def write_findings(path_md, nt, rule, *, res=None, key=None, comp=None, synthetic=False):
    date = os.path.basename(path_md)[len("rq2-blind-"):-3]
    L = [f"# RQ2, blind: seed matches against random windows ({date})", "",
         "## In plain words", "",
         "The seed searches look very good because the researcher accepted almost everything they found, but "
         "every match was judged knowing it was a match. Two things here make that a fair test. First, the null: "
         "how many matches a scrambled recording gives at the same cut, which needs no judging. Second, a blind "
         "panel: seed matches, earlier-accepted matches and random windows of the same lengths, shuffled into one "
         "queue that does not say which is which. If the seed's matches are accepted far more often than the "
         "random windows, the seed finds something real; if earlier yeses survive the blind look, the unblinded "
         "rates were not inflated.", "",
         "Made by `scripts/rq2_blind.py` (see its docstring for the commands). Read with "
         "`docs/rq_roundA/RQ2-exemplar-seeded-search.md` and `docs/rq_roundA_2/RQ2b-second-seed.md`.", ""]
    if res is not None:
        L += render_score(res, key) + [""]
    else:
        L += ["## The blind panel", "", "Not judged yet: `score` fills this section in once the queue is judged.", ""]
    L += _composition_md(comp or (key or {}).get("composition")) + render_nulls(nt, rule)
    os.makedirs(os.path.dirname(path_md), exist_ok=True)
    with open(path_md, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    js = {"date": date, "rule": rule, "nulls": nt, "panel": res, "composition": comp or (key or {}).get("composition"),
          "synthetic": synthetic}
    with open(path_md[:-3] + ".json", "w", encoding="utf-8") as f:
        json.dump(js, f, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    return path_md


# ── command line ─────────────────────────────────────────────────────────────

def _open(a, guard, *, write=False):
    if a.db and a.real:
        raise SystemExit("give --db or --real, not both")
    db = guard.REAL_DB if a.real else a.db
    if not db:
        raise SystemExit("name a database with --db, or pass --real for the real one")
    if not a.real and guard.is_the_real_database(db, guard.REAL_DB):
        raise SystemExit(f"{db} is the real database; pass --real, and no --db, to use it deliberately")
    if write:
        conn = sqlite3.connect(db, timeout=60)
    else:
        conn = sqlite3.connect(pathlib.Path(os.path.abspath(db)).as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn, db


def _backup(conn, db, stamp):
    dest = os.path.join(os.path.dirname(db), "backups", f"{stamp}-pre-rq2-blind.sqlite")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    out = sqlite3.connect(dest)
    with out:
        conn.backup(out)
    out.close()
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "score", "nulls"):
        p = sub.add_parser(name)
        p.add_argument("--db")
        p.add_argument("--real", action="store_true")
    b = sub.choices["build"]
    b.add_argument("--apply", action="store_true", help="write the panel, the queue and the key (else a dry run)")
    b.add_argument("--url", help="the running bridge: the queue is made through its POST /api/review/queues")
    b.add_argument("--stamp", default=_dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    b.add_argument("--seed", type=int, default=20261026)
    b.add_argument("--n-drop30", type=int, default=100)
    b.add_argument("--n-spike37", type=int, default=34)
    b.add_argument("--n-rejudge-dip", type=int, default=20)
    b.add_argument("--n-rejudge-longdip", type=int, default=20)
    b.add_argument("--n-s056", type=int, default=0)
    b.add_argument("--controls-377", type=int, default=30)
    b.add_argument("--controls-148", type=int, default=16)
    b.add_argument("--controls-105", type=int, default=12)
    b.add_argument("--controls-816", type=int, default=12)
    b.add_argument("--controls-364", type=int, default=10)
    s = sub.choices["score"]
    s.add_argument("--key", required=True)
    s.add_argument("--synthetic", action="store_true", help="invented verdicts in memory: a dry run of the scoring")
    s.add_argument("--out", help="output directory (default docs/rq_roundA_2/findings; required with --synthetic)")
    n = sub.choices["nulls"]
    n.add_argument("--key", help="a built panel's key: its composition goes into the file too")
    n.add_argument("--out")
    a = ap.parse_args(argv)
    guard = _guard()
    date = _dt.date.today().isoformat()

    if a.cmd == "build":
        conn, db = _open(a, guard)
        rng = np.random.default_rng(a.seed)
        items, comp = build_items(conn, a, rng)
        items = shuffle(rng, items)
        comp.update({"seed": a.seed, "stamp": a.stamp})
        print(json.dumps({k: v for k, v in comp.items() if k != "seeds"}, indent=1, default=str))
        if not a.apply:
            print("dry run: nothing written (add --apply)")
            return 0
        conn.close()
        conn, db = _open(a, guard, write=True)
        print("backup:", _backup(conn, db, a.stamp))
        out = write_panel(conn, items, stamp=a.stamp, key_dir=os.path.join(KEY_ROOT, a.stamp),
                          make_queue=bridge_queue(a.url) if a.url else None,
                          extra_key={"composition": comp}, db_path=db)
        print(json.dumps({"queue_id": out["queue_id"], "key": out["key_path"], "items": len(out["items"])}))
        return 0

    conn, db = _open(a, guard)
    rule = _ss.cut_rule_from_settings(conn)
    nt = null_tables(rule)
    key = None
    if getattr(a, "key", None):
        with open(a.key, encoding="utf-8") as f:
            key = json.load(f)
    if a.cmd == "nulls":
        out = write_findings(os.path.join(a.out or FINDINGS, f"rq2-blind-{date}.md"), nt, rule, key=key)
        print(out)
        return 0
    if a.synthetic and not a.out:
        raise SystemExit("--synthetic writes to --out only (a scratch directory), never docs/")
    synth = ({"drop30": 0.7, "spike37": 0.8, "rejudge_dip_id010": 0.85, "rejudge_longdip_id020": 0.8,
              "s056": 0.6, "control": 0.22} if a.synthetic else None)
    res = score(conn, key, synthetic=synth)
    out = write_findings(os.path.join(a.out or FINDINGS, f"rq2-blind-{date}.md"), nt, rule, res=res, key=key,
                         synthetic=bool(synth))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
