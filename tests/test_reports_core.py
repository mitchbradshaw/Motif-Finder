"""
test_reports_core.py
====================
`Working.reports` — the figures-and-tables report of a detection run
(docs/prompts/changes/reports.md), drawn by the core with matplotlib alone.

Runs under the conda interpreter (no FastAPI needed). What it pins:

* **the report is figures and tables, not a screenshot**: every figure is a
  real PNG file named for `\\includegraphics` (`fig-01-map.png` …), the
  Markdown carries GitHub-flavoured tables, the HTML embeds the same PNGs;
* **the formatted values are the page's**: the scoreboard cells print the way
  the Discovery page prints them, rounding half up like JavaScript's
  `toFixed`, not Python's half-to-even;
* **the twelve examples are stable**: the top six by score and six at random,
  seeded by the run key, so a re-render picks the same six;
* **a snapshot is a path in the database, never its bytes** (CLAUDE.md rule 4).
"""

import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _conn(tmp_path):
    db = tmp_path / "db.sqlite"
    conn = init_db(str(db))
    for ch in range(2):
        npy = tmp_path / f"CH{ch}.npy"
        np.save(npy, np.sin(np.linspace(0, 40, 6000)) * 0.1)
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('syn.mat', ?, 1.0, 6000, 0, ?)", (ch, str(npy)))
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


def _score_row(found, judged, reviewed, interesting, cont, recall, null_expects, draws, x_null):
    return {
        "found": found, "judged": judged, "reviewed": reviewed, "interesting": interesting,
        "precisions": {
            "containment": {"key": "containment", "label": "containment", "rule": "a human window contains it",
                            "value": cont, "yes": interesting, "judged": reviewed, "byAdjudication": 0,
                            "note": None if cont is not None else "nothing judged"},
            "extent": None},
        "recall": recall, "nullExpects": null_expects, "nullRun": null_expects is not None,
        "nullDraws": draws, "nullDrawsMax": draws, "xNull": x_null,
        "xNullNote": None if x_null is not None else "the null found nothing here",
        "precision": cont, "note": None, "precisionNote": None, "reviewedH": 0.833, "status": "done",
    }


def _scoreboard():
    return {
        "run": "mp_threshold",
        "total": _score_row(7, 1, 4, 3, 0.75, {"value": 0.625, "overH": 1.667}, 2.5, 2, 2.8),
        "channels": [
            dict(_score_row(4, 1, 4, 3, 0.75, {"value": 0.5, "overH": 0.833}, 1.5, 2, 2.67), channel="CH1"),
            dict(_score_row(3, 0, 0, 0, None, {"none": True, "note": "no reviewed overlap"}, 1.0, 2, 3.0),
                 channel="CH2"),
        ],
        "pooledH": 1.667,
        "rule": {"criterion": "reciprocal_iou_onset", "iou": 0.5, "onset": 0.25},
        "reviewedCriterion": "a human verdict covers the detection (the server's own words)",
    }


def _fires():
    return {"binH": 3, "firstBin": 0, "nBins": 1, "channels": [
        {"channel": "CH1", "reviewedH": 0.833, "reviewed": [0.833],
         "rows": [{"run": "human", "counts": [2]}, {"run": "mp_threshold", "counts": [4]}]},
        {"channel": "CH2", "reviewedH": 0.0, "reviewed": [0.0],
         "rows": [{"run": "human", "counts": [0]}, {"run": "mp_threshold", "counts": [3]}]},
    ]}


def _detections(n=40):
    rng = np.random.default_rng(1)
    return [{"id": 100 + i, "channel": "CH1" if i % 2 else "CH2", "start": 100 * i, "end": 100 * i + 60,
             "score": float(rng.random())} for i in range(n)]


def _examples(dets):
    from Working.reports import detection_run as DR
    picked = DR.pick_examples(dets, "mp_threshold")
    out = []
    for d in picked:
        out.append(dict(d, atH=d["start"] / 3600.0, durationS=60.0, verdict=("interesting" if d["id"] == 101 else None),
                        trace={"t0H": (d["start"] - 120) / 3600.0, "stepS": 1.0,
                               "values": list(np.sin(np.linspace(0, 6, 300))), "spanS": [120.0, 180.0],
                               "unit": "mV"}))
    return out


def _run():
    return {"key": "mp_threshold", "label": "mp_threshold · r-1", "kind": "template", "sourceFile": "syn.mat",
            "recording": "syn", "channels": ["CH1", "CH2"], "sectionH": [0.0, 1.667], "session": "test",
            "template": "mp_threshold", "version": 1, "status": "done", "found": 7, "runIds": [],
            "steps": [{"stage": "detection", "algorithm": "matrix_profile", "params": {"m": 60}},
                      {"stage": "postprocessing", "algorithm": "threshold", "params": {"k": 3.0}}],
            "nullRecord": {"paired": True, "draws": 2, "drawn": 2, "params": {"method": "phase randomisation"}}}


def _null():
    return {"kind": "template", "source": "paired", "draws": 2, "method": "phase randomisation",
            "rows": [{"channel": "CH1", "found": 4, "nullExpects": 1.5, "nullDraws": 2, "xNull": 2.67},
                     {"channel": "CH2", "found": 3, "nullExpects": 1.0, "nullDraws": 2, "xNull": 3.0}]}


def _provenance():
    return {"database": "C:/somewhere/annotations.sqlite", "commit": "abc1234", "date": "2026-10-19T10:00:00+00:00",
            "account": "researcher"}


def _report(conn, dets=None):
    from Working.reports import detection_run as DR
    return DR.detection_run_report(conn, _run(), scoreboard=_scoreboard(), fires=_fires(),
                                   examples=_examples(dets or _detections()), null=_null(), provenance=_provenance())


# ── formatting: the page's own way of printing a number ─────────────────────

def test_fixed_rounds_half_up_like_javascript_tofixed():
    from Working.reports import formatting as F
    assert F.fixed(0.625, 2) == "0.63"          # Python's format() gives 0.62 (half to even)
    assert F.fixed(2.25, 1) == "2.3"
    assert F.fixed(2.0, 1) == "2.0"
    assert F.percent(0.745) == "75 %"           # Math.round(0.745 * 100)


def test_the_scoreboard_cells_print_as_the_page_prints_them():
    from Working.reports import formatting as F
    sb = _scoreboard()
    cells = F.score_cells(sb["total"])
    assert cells["found"] == "7" and cells["judged"] == "1" and cells["reviewed"] == "4" and cells["interesting"] == "3"
    assert cells["precision"] == "containment 75 % (3/4)"
    assert cells["recall"] == "0.63 over 1.667 h"
    assert cells["nullExpects"] == "2.5 / 2 draws"
    assert cells["xNull"] == "2.8×"
    ch2 = F.score_cells(sb["channels"][1])
    assert ch2["recall"] == "no reviewed overlap"
    assert ch2["precision"] == "containment — nothing judged"


# ── the twelve examples ─────────────────────────────────────────────────────

def test_the_examples_are_the_top_six_by_score_and_six_at_random_stable_across_renders():
    from Working.reports import detection_run as DR
    dets = _detections()
    a = DR.pick_examples(dets, "mp_threshold")
    b = DR.pick_examples(list(reversed(dets)), "mp_threshold")
    assert [d["id"] for d in a] == [d["id"] for d in b], "a re-render picks the same twelve"
    assert len(a) == 12
    top = sorted(dets, key=lambda d: -d["score"])[:6]
    assert [d["id"] for d in a[:6]] == [d["id"] for d in top]
    assert all(d["pick"] == "top" for d in a[:6]) and all(d["pick"] == "random" for d in a[6:])
    assert not {d["id"] for d in a[:6]} & {d["id"] for d in a[6:]}
    other = DR.pick_examples(dets, "another_run")
    assert [d["id"] for d in other[6:]] != [d["id"] for d in a[6:]], "the random six are seeded by the run key"


def test_a_seed_runs_best_examples_are_its_closest_matches():
    from Working.reports import detection_run as DR
    dets = _detections()
    a = DR.pick_examples(dets, "seed_run", lower_is_better=True)
    assert [d["id"] for d in a[:6]] == [d["id"] for d in sorted(dets, key=lambda d: d["score"])[:6]]


def test_fewer_than_twelve_detections_are_all_shown_once():
    from Working.reports import detection_run as DR
    dets = _detections(8)
    a = DR.pick_examples(dets, "r")
    assert sorted(d["id"] for d in a) == sorted(d["id"] for d in dets)


# ── the report ──────────────────────────────────────────────────────────────

def test_the_report_has_its_six_sections_in_order_with_real_pngs(tmp_path):
    rep = _report(_conn(tmp_path))
    heads = [s["heading"] for s in rep["sections"]]
    assert heads == ["Detection map", "Scoreboard against the human reference", "Where the run fires",
                     "Twelve example detections", "Null comparison", "Parameters and provenance"]
    names = [n for n, _ in rep["figures"]]
    assert names == ["fig-01-map.png", "fig-02-fires.png", "fig-03-examples.png", "fig-04-null.png"]
    for _, png in rep["figures"]:
        assert png[:8] == PNG_MAGIC and len(png) > 1000


def test_the_markdown_scoreboard_carries_the_payloads_numbers_and_the_servers_rule_text(tmp_path):
    from Working.reports import formatting as F
    rep = _report(_conn(tmp_path))
    md = rep["markdown"]
    sb = _scoreboard()
    total = F.score_cells(sb["total"])
    line = next(ln for ln in md.splitlines() if ln.startswith("| **total** |"))
    cells = [c.strip() for c in line.strip("|").split("|")]
    assert cells[1:] == [total[k] for k in F.SCORE_COLUMNS]
    assert sb["reviewedCriterion"] in md, "the reviewed rule is the server's text, not a copy"
    assert "| CH2 |" in md and "no reviewed overlap" in md


def test_write_report_writes_markdown_html_and_numbered_figures(tmp_path):
    from Working.reports import render
    rep = _report(_conn(tmp_path))
    out = tmp_path / "snap"
    paths = render.write_report(rep, str(out))
    files = sorted(os.listdir(out))
    assert "report.md" in files and "report.html" in files
    for name, _ in rep["figures"]:
        assert name in files
        with open(out / name, "rb") as f:
            assert f.read(8) == PNG_MAGIC
    html = (out / "report.html").read_text(encoding="utf-8")
    assert '<img src="fig-01-map.png"' in html, "the snapshot's HTML embeds the PNG files beside it"
    assert "<table" in html
    assert paths["markdown"].endswith("report.md")
    live = render.report_html(rep, inline=True)
    assert "data:image/png;base64," in live and "<script" not in live


def test_a_snapshot_is_recorded_as_a_path_and_listed(tmp_path):
    from Working.reports import store
    conn = _conn(tmp_path)
    rid = store.record(conn, kind="detection-run", run_key="mp_threshold", session_id=1, title="t",
                       path=str(tmp_path / "snap"), note=None)
    rows = store.list_reports(conn)
    assert [r["id"] for r in rows] == [rid]
    assert rows[0]["path"] == str(tmp_path / "snap") and rows[0]["kind"] == "detection-run"
    cols = {r[1] for r in conn.execute("PRAGMA table_info(reports)")}
    assert {"id", "kind", "run_key", "run_id", "created_at", "path", "note"} <= cols
    assert not any("blob" in (r[2] or "").lower() for r in conn.execute("PRAGMA table_info(reports)"))


def test_init_db_creates_the_reports_table_idempotently(tmp_path):
    db = str(tmp_path / "x.sqlite")
    init_db(db).close()
    conn = init_db(db)
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'reports'").fetchone()[0] == 1
    conn.close()


def test_the_core_report_module_imports_no_browser_or_server_library():
    import ast
    root = os.path.join(PROJECT_ROOT, "Working", "reports")
    assert os.path.isdir(root)
    banned = ("fastapi", "uvicorn", "starlette", "server", "webui", "seaborn", "panel", "bokeh", "holoviews",
              "matplotlib.pyplot")
    for name in os.listdir(root):
        if not name.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(root, name), encoding="utf-8").read())
        for node in ast.walk(tree):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for m in mods:
                assert not any(m == b or m.startswith(b + ".") for b in banned), f"{name} imports {m}"
