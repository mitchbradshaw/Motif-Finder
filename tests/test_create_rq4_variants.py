"""
test_create_rq4_variants.py
===========================
``scripts/create_rq4_variants.py`` and the matrix-profile templates that read the RQ4 overnight profiles
(2026-10-18, RQ4b's decision, option 1).

The overnight sweep computed the matrix profile once, as ``mp_threshold`` with ``backend: "auto"``, on CH1_A1 and
CH2_A1 (``HPC/Detection/generated/rq4_overnight/mp_threshold__backend_auto_*.chain.json``). The other
matrix-profile templates say ``backend: "stump"``, and the backend is in the step cache's key, so they cannot read
those profiles. Their ``backend: "auto"`` copies can:

* the script plans ``mp_threshold__backend_auto`` (the overnight job's own template, until now not a row) and the
  ``backend: "auto"`` copies of ``mp_threshold__threshold_6``, ``mp_threshold__threshold_10`` and ``mp_motifs`` —
  dry by default, marked ``[rq4-sweep]``, undone by ``--remove``, a copy of a variant created in the same run;
* each copy differs from its base in the backend alone;
* their detrend → profile keys, for the real run and its null draw, are the overnight spec's, so after the import
  they read its profiles from the cache (the golden check, on the tracked spec; no channel data is read).

FastAPI lives only in ``webui/.venv``:

    "C:/Users/mmebr/Documents/CNN/webui/.venv/Scripts/python.exe" -m pytest tests/test_create_rq4_variants.py -q -p no:cacheprovider
"""

import copy
import glob
import importlib.util
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working import run_groups as RG  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import chain_job, fanout  # noqa: E402
from Working.execution import _recipe_prefix_hash  # noqa: E402
from server import templates as T  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

MP_AUTO = "mp_threshold__backend_auto"
COPIES = {"mp_threshold__threshold_6__backend_auto": "mp_threshold__threshold_6",
          "mp_threshold__threshold_10__backend_auto": "mp_threshold__threshold_10",
          "mp_motifs__backend_auto": "mp_motifs",
          MP_AUTO: "mp_threshold"}
SPECS_DIR = os.path.join(PROJECT_ROOT, "HPC", "Detection", "generated", "rq4_overnight")


def _script(name):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, os.path.join(PROJECT_ROOT, "scripts", name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


@pytest.fixture
def client(tmp_path):
    db = tmp_path / "annotations.sqlite"
    init_db(str(db)).close()
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261018-rq4-variants", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


@pytest.fixture
def V(client, monkeypatch):
    V = _script("create_rq4_variants")

    def call(base_url, method, path, body=None):
        r = client.request(method, path, json=body)
        if r.status_code >= 400:
            raise V.BridgeError(f"{method} {path} -> HTTP {r.status_code}: {r.text[:600]}")
        return r.json()

    monkeypatch.setattr(V, "call", call)
    return V


def _templates(client):
    conn = init_db(client.app.state.rt.db_path)
    try:
        return {t["name"]: t for t in T.list_all(conn)}
    finally:
        conn.close()


def test_a_dry_run_plans_the_backend_auto_copies_and_writes_nothing(client, V, capsys):
    before = set(_templates(client))
    V.main(["--url", "http://bridge"])
    out = capsys.readouterr().out
    for name in COPIES:
        line = next((l for l in out.splitlines() if l.startswith(name + " ")), None)
        assert line is not None and "would create" in line, (name, out)
    assert set(_templates(client)) == before


def test_apply_creates_them_marked_differing_only_in_the_backend_and_remove_undoes_it(client, V):
    V.main(["--url", "http://bridge", "--apply"])
    have = _templates(client)
    for name, base in COPIES.items():
        assert name in have, f"{name} was not created"
        t = have[name]
        assert t["description"].startswith(V.MARK)
        assert t["kind"] == have[base]["kind"]
        want = copy.deepcopy(have[base]["steps"])
        for s in want:
            if s["algorithm"] == "matrix_profile":
                s.setdefault("params", {})["backend"] = "auto"
        # a saved template stores every step's side inputs, `{}` when it has none (the builtin rows omit the key)
        stored = [dict(s, side_inputs=s.get("side_inputs") or {}) for s in want]
        assert t["steps"] == stored, f"{name} differs from {base} in more than the backend"
        assert have[base]["steps"][1]["params"]["backend"] == "stump"
    # idempotent: a second run creates nothing more
    n = len(_templates(client))
    V.main(["--url", "http://bridge", "--apply"])
    assert len(_templates(client)) == n
    V.main(["--url", "http://bridge", "--remove", "--apply"])
    have = _templates(client)
    assert not any(name in have for name in COPIES)
    assert "mp_threshold" in have and "mp_motifs" in have, "the builtin bases stay"


def _mp_spec():
    paths = glob.glob(os.path.join(SPECS_DIR, MP_AUTO + "_*" + chain_job.SPEC_SUFFIX))
    assert len(paths) == 1, paths
    with open(paths[0], encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def spec_conn(tmp_path):
    """A database holding the overnight MP spec's recording rows as its targets describe them (no channel data)."""
    spec = _mp_spec()
    dummy = tmp_path / "dummy.npy"
    dummy.write_bytes(b"")
    c = init_db(str(tmp_path / "spec.sqlite"))
    for t in spec["targets"]:
        c.execute("INSERT INTO recordings (id, source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (int(t["recordingId"]), t["sourceFile"], int(t["channel"]),
                                                      float(t["fs"]), int(t["nSamples"]), int(t["globalOffset"]),
                                                      str(dummy), t["units"]))
    c.commit()
    yield c
    c.close()


def _draw_prefixes(recipe, null, units, upto):
    base, skipped = RG.surrogate_draw_params(None, None, null["params"])
    assert skipped is None
    out = []
    for j in range(int(null["draws"])):
        dr = RG.surrogate_recipe(recipe, dict(base, seed=int(base["seed"]) + j))
        out.append([_recipe_prefix_hash(dr, k, units) for k in range(upto + 1)])
    return out


def test_the_backend_auto_templates_key_their_profile_as_the_overnight_spec_did(client, V, spec_conn):
    V.main(["--url", "http://bridge", "--apply"])
    have = _templates(client)
    spec = _mp_spec()
    null = spec["null"]
    ids = [int(t["recordingId"]) for t in spec["targets"]]
    mp_step = next(k for k, s in enumerate(spec["steps"]) if s["algorithm"] == "matrix_profile")
    for name in COPIES:
        plan = fanout.plan(spec_conn, steps=have[name]["steps"], recording_ids=ids, span=spec["span"],
                           ceiling_s=10 ** 9, null_draws=null["draws"], surrogate=True,
                           surrogate_params=null["params"])
        for i, t in enumerate(spec["targets"]):
            recipe = fanout.target_recipe(plan["recipe"], i, True)
            mine = [_recipe_prefix_hash(recipe, k, t["units"]) for k in range(mp_step + 1)]
            assert mine == t["prefixHashes"][:mp_step + 1], f"{name}, {t['channelName']}: the real run's profile key"
            # a draw prepends its surrogate step: its profile is step mp_step + 1
            assert _draw_prefixes(recipe, null, t["units"], mp_step + 1) == \
                _draw_prefixes(t["recipe"], null, t["units"], mp_step + 1), f"{name}, {t['channelName']}: the draw's"
            if name == MP_AUTO:
                assert recipe == t["recipe"], "the overnight job's own template is its chain exactly"
