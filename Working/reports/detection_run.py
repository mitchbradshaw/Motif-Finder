"""The detection-run report: one Discovery run and how it compares with the human reference.

Six sections, in the order the researcher asked for (2026-10-18):

1. the detection map for the recording — the human row and this run's row,
   per channel × time slice (`detection_map.channel_map`, read here);
2. the scoreboard against the human reference, per channel and total, the
   column definitions as footnotes and the *reviewed* rule as the server
   words it (`reviewedCriterion`);
3. where the run fires — counts per 3 h bin per channel;
4. twelve example detections — the top six by score, six at random seeded
   by the run key;
5. the null comparison the run carries;
6. parameters and provenance.

**The numbers are the pages' own.** The scoreboard, the fires strip and the
null rows are handed in as the payloads the Discovery routes serve
(`GET /api/discovery/scoreboard`, `/fires`), not recomputed: the scoreboard's
cells are shaped by the bridge (`_score_row`), and a report that recomputed
them would be a second implementation that could drift from the page it is
meant to stand behind. The map is the one core read made here, through the
same `channel_map` the Map page's route calls.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

from Working.discovery import detection_map as DM

from . import figures as FG
from . import formatting as F
from . import render

KIND = "detection-run"
N_TOP = 6
N_RANDOM = 6
MAP_CHUNKS = 8

FIG_MAP = "fig-01-map.png"
FIG_FIRES = "fig-02-fires.png"
FIG_EXAMPLES = "fig-03-examples.png"
FIG_NULL = "fig-04-null.png"


# ── the twelve examples ─────────────────────────────────────────────────────

def _seed_of(run_key: str) -> int:
    return int(hashlib.sha256(str(run_key).encode("utf-8")).hexdigest()[:16], 16)


def pick_examples(detections, run_key, *, lower_is_better=False, n_top=N_TOP, n_random=N_RANDOM):
    """The top ``n_top`` by score and ``n_random`` more at random, each a copy
    with ``pick`` set to ``"top"`` or ``"random"``.

    Stable: the input is put in detection-id order first, the best are ranked
    by (score, id), and the random draw is seeded by the run key — so a
    re-render of the same run picks the same twelve, and another run draws
    its own six. ``lower_is_better`` is for a seed run, whose score is a match
    distance (closest first). Detections with no score fill the top six only
    after every scored one, in id order."""
    ordered = sorted(detections, key=lambda d: int(d["id"]))
    scored = [d for d in ordered if d.get("score") is not None]
    sign = 1.0 if lower_is_better else -1.0
    top = sorted(scored, key=lambda d: (sign * float(d["score"]), int(d["id"])))[:n_top]
    if len(top) < n_top:
        top += [d for d in ordered if d.get("score") is None][:n_top - len(top)]
    taken = {int(d["id"]) for d in top}
    rest = [d for d in ordered if int(d["id"]) not in taken]
    picked = []
    if rest and n_random > 0:
        rng = np.random.default_rng(_seed_of(run_key))
        idx = rng.choice(len(rest), size=min(n_random, len(rest)), replace=False)
        picked = sorted((rest[int(i)] for i in idx), key=lambda d: (str(d.get("channel")), int(d["start"])))
    return [dict(d, pick="top") for d in top] + [dict(d, pick="random") for d in picked]


# ── 1. the map ──────────────────────────────────────────────────────────────

def _run_row_keys(conn, run_ids):
    """The map row keys this run's `runs` rows execute — `detection_map.steps_key`
    of their configs, the key the Map page groups rows by."""
    if not run_ids:
        return set()
    marks = ",".join(str(int(i)) for i in run_ids)
    rows = conn.execute("SELECT DISTINCT c.config_json FROM runs r JOIN configs c ON c.id = r.config_id "
                        "WHERE r.id IN (" + marks + ")").fetchall()
    return {DM.steps_key(r[0]) for r in rows}


def map_data(conn, source_file, run_ids, channels, *, chunks=MAP_CHUNKS, exclude_files=()):
    """Level 2 of the map for one recording, cut to the report's channels and
    to two rows: the human reference and this run's row (``None`` when the
    run has no row — it has not finished, or the map leaves it out)."""
    m = DM.channel_map(conn, source_file, chunks=chunks, exclude_files=exclude_files)
    keys = _run_row_keys(conn, run_ids)
    human = next(r for r in m["rows"] if r["key"] == DM.HUMAN_KEY)
    mine = next((r for r in m["rows"] if r["key"] in keys), None)
    chans = [c for c in channels if c in m["cells"].get(DM.HUMAN_KEY, {})]
    rows = [{"label": "human reference — interesting and seed verdicts, where a person looked", "human": True,
             "key": human["key"], "cells": {c: m["cells"][DM.HUMAN_KEY][c] for c in chans}}]
    if mine is not None:
        rows.append({"label": f"this run's row — {mine['label']}", "human": False, "key": mine["key"],
                     "cells": {c: m["cells"][mine["key"]].get(c, []) for c in chans}})
    return {"chunks": int(m["chunks"]), "channels": chans, "rows": rows, "hours": m["hours"],
            "dataset": m["name"], "found": mine is not None, "sessions": (mine or {}).get("sessionNames") or []}


def _map_cell(cell):
    if cell.get("state") == "covered":
        return f"{cell['count']} in {cell['hours']:g} h"
    return FG.STATE_WORDS.get(cell.get("state"), cell.get("state") or "")


# ── the report ──────────────────────────────────────────────────────────────

def _steps_table(steps):
    rows = []
    for i, st in enumerate(steps or [], start=1):
        params = st.get("params") or {}
        rows.append([str(i), f"{st.get('stage')}.{st.get('algorithm')}",
                     json.dumps(params, sort_keys=True, default=str, separators=(", ", ": "))])
    return {"id": "steps", "headers": ["#", "block", "parameters"], "rows": rows}


def _null_words(run, null):
    rec = run.get("nullRecord") or {}
    src = null.get("source")
    if src == "off":
        return "This run drew no null: Settings › Nulls was off for it, so there is no chance level to compare with."
    method = null.get("method") or (rec.get("params") or {}).get("method") or "the null"
    draws = null.get("draws")
    where = {"preview": "the null the Seed page's preview drew, reused", "hpc": "the null computed on the cluster",
             "paired": "paired surrogate runs drawn with the run"}.get(src, src or "paired surrogate runs")
    bits = [f"Null: {where}; method {method}"]
    if draws:
        bits.append(f"{draws} draws per channel")
    if rec.get("drawn") is not None and draws and rec.get("drawn") != draws:
        bits.append(f"{rec['drawn']} drawn (fewer than asked)")
    if rec.get("skipped"):
        bits.append(f"skipped: {rec['skipped']}")
    if null.get("cut") is not None:
        bits.append(f"kept cut d ≤ {null['cut']:g}")
    return "; ".join(bits) + "."


def detection_run_report(conn, run, *, scoreboard, fires, examples, null, provenance, exclude_files=(),
                         chunks=MAP_CHUNKS):
    """The report as ``{kind, title, subtitle, plain, sections, figures: [(name, png)], tables, markdown}``.

    ``run`` is the run's identity: key, label, kind, sourceFile, recording
    (its name), channels, sectionH, session, template, version, status, found,
    runIds, steps, nullRecord. ``scoreboard`` is one entry of the scoreboard
    route's list (or None: not yet scored); ``fires`` the fires route's
    payload for ``human,<key>``; ``examples`` the picked detections, each with
    its ``trace`` (the detection-window route's payload) and ``verdict``;
    ``null`` the null section's data; ``provenance`` the database, commit,
    date and account."""
    figures, sections, tables = [], [], {}
    sec_h = run.get("sectionH") or [0, 0]
    title = f"Detection run report — {run['label']}"
    subtitle = (f"{run.get('recording')} · {', '.join(run.get('channels') or [])} · section "
                f"{sec_h[0]:.2f}–{sec_h[1]:.2f} h · rendered {provenance.get('date')}")
    plain = ("What a detection algorithm found in this recording, side by side with what a person marked by hand. "
             "Think of a spell-checker run over a book a proof-reader has partly read: the map shows which pages "
             "each of them covered, the scoreboard counts where they agree on the pages both read, the strip shows "
             "where in the book the checker flagged most, and twelve example flags let you judge them by eye. "
             "The null comparison says how many flags the checker would raise on scrambled text of the same kind "
             "(chance level); the last section records everything needed to run it again.")

    # 1. the map
    md = map_data(conn, run["sourceFile"], run.get("runIds") or [], run.get("channels") or [], chunks=chunks,
                  exclude_files=exclude_files)
    figures.append((FIG_MAP, FG.map_figure(md)))
    n = md["chunks"]
    heads = ["channel"] + F.slice_labels(md["hours"], n)
    map_tables = []
    for row in md["rows"]:
        t = {"id": "map-human" if row["human"] else "map-run", "caption": row["label"], "headers": heads,
             "rows": [[c] + [_map_cell(x) for x in row["cells"].get(c, [])] for c in md["channels"]]}
        tables[t["id"]] = t
        map_tables.append(t)
    notes = ["A covered cell gives the count of detections (human row: interesting and seed verdicts) and the "
             "hours covered in that slice. 'not run' means no run of this algorithm reached the slice; "
             "'not reviewed' means nobody looked there — not the same as looking and finding nothing.",
             "The run's row is the Map page's row for this algorithm: coverage is the union of every live run of "
             "the same steps, each slice counted from the newest run that covers it."]
    if not md["found"]:
        notes.insert(0, "This run has no row on the map yet: it has not written a finished run on these channels.")
    sections.append({"heading": "Detection map", "figure": FIG_MAP,
                     "caption": f"Discovery › Map, {md['dataset']}, {n} equal time slices.",
                     "tables": map_tables, "notes": notes})

    # 2. the scoreboard
    if scoreboard:
        rows = [["**total**"] + [F.score_cells(scoreboard["total"])[k] for k in F.SCORE_COLUMNS]]
        rows += [[c["channel"]] + [F.score_cells(c)[k] for k in F.SCORE_COLUMNS] for c in scoreboard["channels"]]
        t = {"id": "scoreboard", "headers": ["channel"] + list(F.SCORE_HEADERS), "rows": rows}
        tables["scoreboard"] = t
        rule = scoreboard.get("rule") or {}
        sb_notes = [f"**{h}** — {F.SCORE_DEFINITIONS[h]}" for h in F.SCORE_HEADERS]
        sb_notes.append(f"**Reviewed** means: {scoreboard.get('reviewedCriterion')}.")
        sb_notes.append("**Matching rule** (a detection and a human span are the same event): "
                        + ", ".join(f"{k} {v}" for k, v in rule.items()) + ".")
        sb_notes.append(f"The total pools {scoreboard.get('pooledH', 0):g} reviewed hours.")
        sections.append({"heading": "Scoreboard against the human reference", "figure": None,
                         "caption": None, "tables": [t], "notes": sb_notes})
    else:
        sections.append({"heading": "Scoreboard against the human reference", "figure": None, "caption": None,
                         "tables": [], "notes": ["Not yet scored: the run has no finished channels to score."]})

    # 3. where it fires
    figures.append((FIG_FIRES, FG.fires_figure(fires, run["key"], run["label"])))
    sections.append({"heading": "Where the run fires", "figure": FIG_FIRES,
                     "caption": (f"Detections per {fires.get('binH', 3):g} h bin per channel (blue), the human "
                                 "yes-verdicts in the same bins (green), over the reviewed hours (pale underlay)."),
                     "tables": [], "notes": []})

    # 4. examples
    figures.append((FIG_EXAMPLES, FG.examples_figure(examples)))
    lower = run.get("kind") == "seed"
    ex_rows = []
    for i, e in enumerate(examples, start=1):
        s = e.get("score")
        ex_rows.append([str(i), "top" if e.get("pick") == "top" else "random", e.get("channel"),
                        f"{e.get('atH', 0):.4f}", f"{e.get('durationS', 0):g}",
                        "—" if s is None else f"{s:.4g}", e.get("verdict") or "not judged",
                        str(e.get("detectionId", e.get("id")))])
    t = {"id": "examples", "headers": ["#", "pick", "channel", "at (h)", "duration (s)",
                                       "match distance" if lower else "score", "verdict", "detection id"],
         "rows": ex_rows}
    tables["examples"] = t
    sections.append({"heading": "Twelve example detections", "figure": FIG_EXAMPLES,
                     "caption": ("The six best by score ("
                                 + ("closest match distance" if lower else "highest score")
                                 + ") and six at random, seeded by the run key so a re-render shows the same six. "
                                 "The band is the detection's span; the verdict is a human one, if it has one."),
                     "tables": [t], "notes": []})

    # 5. the null
    null_rows = [[r["channel"], str(r.get("found")), F.null_cell(r), F.x_null_cell(r)] for r in null.get("rows") or []]
    null_tables = []
    if null_rows:
        t = {"id": "null", "headers": ["channel", "found", "null expects / draws", "× null"], "rows": null_rows}
        tables["null"] = t
        null_tables.append(t)
    null_notes = [_null_words(run, null)]
    if null.get("missing"):
        null_notes.append(null["missing"])
    fig_null = None
    if null.get("source") != "off" and (null.get("rows") or null.get("byChannel")):
        figures.append((FIG_NULL, FG.null_figure(null)))
        fig_null = FIG_NULL
    sections.append({"heading": "Null comparison", "figure": fig_null,
                     "caption": ("Per channel, the null's match distances (grey) behind this run's (blue), with the "
                                 "kept cut — the Seed page's cut histogram." if null.get("kind") == "seed"
                                 and null.get("byChannel") else
                                 "Per channel, what the run found beside what its null expects by chance."),
                     "tables": null_tables, "notes": null_notes})

    # 6. provenance
    rec = run.get("nullRecord") or {}
    prov_rows = [
        ["recording", f"{run.get('recording')} ({run.get('sourceFile')})"],
        ["channels", ", ".join(run.get("channels") or [])],
        ["section", f"{sec_h[0]:.4f}–{sec_h[1]:.4f} h"],
        ["Discovery session", str(run.get("session"))],
        ["run", f"{run['key']} — {run['label']} ({run.get('status')}, {run.get('found')} found)"],
        ["template", (f"{run.get('template')} v{run.get('version')}" if run.get("template") else "—")],
        ["null", json.dumps(dict({k: rec.get(k) for k in ("paired", "source", "draws", "drawn", "method", "skipped")
                                  if k in rec}, **({"params": rec["params"]} if rec.get("params") else {})),
                            sort_keys=True, default=str) if rec else "—"],
        ["database", str(provenance.get("database"))],
        ["code commit", str(provenance.get("commit"))],
        ["rendered", str(provenance.get("date"))],
        ["account", str(provenance.get("account"))],
    ]
    if run.get("seedId"):
        prov_rows.insert(5, ["seed", f"{run['seedId']} · cut {run.get('cut')}"])
    tp = {"id": "provenance", "headers": ["", ""], "rows": prov_rows}
    ts = _steps_table(run.get("steps"))
    tables["provenance"], tables["steps"] = tp, ts
    sections.append({"heading": "Parameters and provenance", "figure": None, "caption": None,
                     "tables": [tp, ts], "notes": ["Every step parameter is the run's own recipe, as executed."]})

    report = {"kind": KIND, "title": title, "subtitle": subtitle, "plain": plain, "sections": sections,
              "figures": figures, "tables": tables}
    report["markdown"] = render.to_markdown(report)
    return report
