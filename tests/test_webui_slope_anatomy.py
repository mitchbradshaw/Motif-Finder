"""
test_webui_slope_anatomy.py
============================
fixup-k: the Slope page's anatomy figure stops making its marks up.

Analyse > Interrogation > 01 Slope draws one event with its onset, steepest sample,
trough, chord, tangent and depth line. Before this prompt the marks came from
`fixtures/interrogation.ts::eventMarks` - "steepest" was `duration / 2` - and from
constants in `SlopePage.tsx` (the trough drawn at `-depth`, the steepest point at
`-depth / 2`, the window opening 10 s before the onset whatever the padding said),
over the event's real trace. A drawn tangent reads as a measured one.

Two halves:

* the client pins run anywhere (they read the client's sources): the fixture marks
  are gone and the page's geometry takes its marks from the payload;
* the route tests need FastAPI, which lives only in `webui/.venv`:

      webui/.venv/Scripts/python.exe -m pytest tests/test_webui_slope_anatomy.py
"""

import os
import re
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
SLOPE_PAGE = os.path.join(CLIENT_SRC, "interrogation", "SlopePage.tsx")
SEED_DIR = os.path.join(PROJECT_ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
needs_seed = pytest.mark.skipif(not os.path.isdir(SEED_DIR), reason="seed store absent")


# ------------------------------------------------------------------ the client pins --

def _client_sources():
    for root, _dirs, files in os.walk(CLIENT_SRC):
        for fn in files:
            if fn.endswith((".ts", ".tsx")):
                path = os.path.join(root, fn)
                with open(path, encoding="utf-8") as f:
                    yield path, f.read()


def test_no_client_file_takes_an_events_marks_from_the_fixtures():
    users = [os.path.relpath(p, CLIENT_SRC) for p, src in _client_sources() if "eventMarks" in src]
    assert users == [], f"`eventMarks` (steepest = duration / 2) is still in {users}"


def test_the_anatomy_figure_draws_no_mark_at_a_constant():
    with open(SLOPE_PAGE, encoding="utf-8") as f:
        src = f.read()
    # the steepest point's height was -depth / 2, the trough's -depth, the baseline band 0.012 mV
    assert not re.search(r"depth_mV\s*/\s*2", src), "the steepest point is still drawn at -depth / 2"
    assert "0.012" not in src, "the baseline band is still a constant 0.012 mV"
    # ... and the window opened 10 s before the onset whatever the padding setting said
    assert not re.search(r"const pre = 10\b", src), "the anatomy window still opens a fixed 10 s before the onset"
    # the marks are the payload's
    for field in ("steepest_s", "trough_s", "onset_mV", "steepest_mV", "trough_mV"):
        assert field in src, f"the anatomy figure does not read `{field}` from the member's measured marks"


# ---------------------------------------------------------------------- the route --

@pytest.fixture
def client(tmp_path):
    pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
    pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")
    from fastapi.testclient import TestClient

    from Working.database.schema import init_db
    from server.app import create_app
    from server.runtime import Runtime

    db_dir = tmp_path / "db"; db_dir.mkdir()
    conn = init_db(str(db_dir / "annotations.sqlite"))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES ('syn.mat', 0, 1.0, 10, 0, 'x.npy')")
    conn.commit(); conn.close()
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261002-anatomy", db_source=str(db_dir / "annotations.sqlite"),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def _snippets():
    from Working.Detection.drop_motifs import store as S
    return S.load_snippets(SEED_DIR)


def _fs(client, family):
    return {m["event_id"]: float(m["fs"]) for m in client.get(f"/api/interrogation/families/{family}/members?snippets=false").json()["members"]}


@needs_seed
@pytest.mark.parametrize("family", ["id001", "id010"])
def test_the_slope_route_serves_where_the_steepest_sample_is(client, family):
    d = client.get(f"/api/interrogation/families/{family}/slope").json()
    snips, fs = _snippets(), _fs(client, family)
    assert d["members"], family
    for m in d["members"]:
        o, s, t = m["onset_offset"], m["steepest_offset"], m["trough_offset"]
        assert o <= s <= t, f"{m['event_id']}: steepest {s} outside [onset {o}, trough {t}]"
        # the position and the value are one measurement: d/dt AT that sample is the served max slope
        v = np.asarray(snips[m["event_id"]]["detrended_mv"], dtype=float)
        assert np.gradient(v)[s] * fs[m["event_id"]] == pytest.approx(m["max_slope_mv_s"], rel=1e-9, abs=1e-12)


@needs_seed
def test_the_steepest_sample_is_not_the_middle_of_the_fall(client):
    """The fabrication, stated as a number: on id001 (the page's default family, a sharkfin)
    the fall is front-loaded, so drawing the tangent at half the fall puts it in the wrong
    half of every event."""
    d = client.get("/api/interrogation/families/id001/slope").json()
    frac = [(m["steepest_offset"] - m["onset_offset"]) / (m["trough_offset"] - m["onset_offset"]) for m in d["members"]]
    assert len(frac) == 17
    assert max(frac) < 0.5, f"steepest at {sorted(frac)} of the fall"


@needs_seed
def test_the_slope_route_serves_the_height_of_every_mark(client):
    """A chord runs from the trace at the onset to the trace at the trough, and the tangent
    touches the trace at the steepest sample: the three heights are the snippet's own samples,
    read at full resolution (the page only holds a 400-point decimation)."""
    d = client.get("/api/interrogation/families/id001/slope").json()
    snips, fs = _snippets(), _fs(client, "id001")
    for m in d["members"]:
        v = np.asarray(snips[m["event_id"]]["detrended_mv"], dtype=float)
        assert m["onset_mv"] == pytest.approx(v[m["onset_offset"]])
        assert m["steepest_mv"] == pytest.approx(v[m["steepest_offset"]])
        assert m["trough_mv"] == pytest.approx(v[m["trough_offset"]])
        # the chord the page draws between those two heights IS the served chord slope
        fall_s = (m["trough_offset"] - m["onset_offset"]) / fs[m["event_id"]]
        assert (m["trough_mv"] - m["onset_mv"]) / fall_s == pytest.approx(m["mean_slope_mv_s"])


@needs_seed
def test_the_rule_behind_steepest_says_what_was_differentiated(client):
    d = client.get("/api/interrogation/families/id001/slope").json()
    rule = next(r for r in d["rules"] if r["name"] == "steepest")["rule"]
    assert "np.gradient" in rule and "onset" in rule and "trough" in rule, rule


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
