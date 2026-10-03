"""
test_analyse_null_toggle.py
============================
fixup-T, Part E (Q38). The Analyse toolbar rendered a disabled
"surrogate · not in this slice" and every run footer ended "no null". The
toggle is wired, **default off in Analyse** (the tuning loop there is seconds;
Discovery is where a claim is made), and when it is on the terminal row reads
detected-versus-surrogate.

The run manager executes the chain itself (it streams every stage to the
page), so the null is drawn for a run that already exists: `draw_paired_null`
is the second half of `run_paired_recipe`, and `null_summary` is the
detected-versus-surrogate read-out, both in the core so the bridge holds no
arithmetic of its own.

The client half is asserted at source level — there is no Node test runner in
this repo (the client's gate is `tsc -b`, `npm run build` and `webui/smoke.py`).

Runnable standalone:  python tests/test_analyse_null_toggle.py
"""

import io
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")

from Adapters.registry import discover_adapters  # noqa: E402
from Working import run_groups  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.recipes import make_recipe  # noqa: E402

discover_adapters()

SPIKE = [{"stage": "detection", "algorithm": "spike_v1", "params": {}}]


@pytest.fixture()
def db():
    tmpdir = tempfile.mkdtemp(prefix="fixup_t_e_")
    db_path = os.path.join(tmpdir, "t.sqlite")
    conn = init_db(db_path)
    npy = os.path.join(tmpdir, "CH0.npy")
    np.save(npy, np.random.default_rng(0).standard_normal(400))
    rec = q.insert_recording(conn, "fake.mat", 0, 1.0, 400, 0, npy)
    yield {"path": db_path, "conn": conn, "rec": rec}
    conn.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_a_null_is_drawn_for_a_run_that_already_exists(db):
    recipe = make_recipe(db["rec"], SPIKE, span=(0, 400))
    recipe["surrogate"] = True
    run = execute_recipe(recipe, db_path=db["path"])
    null = run_groups.draw_paired_null(recipe, run["run_id"], db_path=db["path"], draws=3)
    assert len(set(null["run_ids"])) == 3 and null["draws"] == 3 and null["skipped"] is None
    for rid in null["run_ids"]:
        assert R.get_run(db["conn"], rid)["surrogate_of_run_id"] == run["run_id"]


def test_the_summary_reads_detected_versus_surrogate(db):
    recipe = make_recipe(db["rec"], SPIKE, span=(0, 400))
    recipe["surrogate"] = True
    run = execute_recipe(recipe, db_path=db["path"])
    null = run_groups.draw_paired_null(recipe, run["run_id"], db_path=db["path"], draws=4)
    s = run_groups.null_summary(db["conn"], run["run_id"])
    found = len(R.list_detections(db["conn"], run["run_id"]))
    counts = [len(R.list_detections(db["conn"], rid)) for rid in null["run_ids"]]
    assert s["found"] == found
    assert s["null_draws"] == 4
    assert s["null_expects"] == pytest.approx(sum(counts) / 4.0)
    if sum(counts):
        assert s["x_null"] == pytest.approx(found / (sum(counts) / 4.0))
    else:
        assert s["x_null"] is None
    assert s["method"] == "phase_randomize"


def test_a_run_with_no_null_says_so_rather_than_zero(db):
    run = execute_recipe(make_recipe(db["rec"], SPIKE, span=(0, 400)), db_path=db["path"])
    s = run_groups.null_summary(db["conn"], run["run_id"])
    assert s["null_draws"] == 0 and s["null_expects"] is None and s["x_null"] is None


# ── the client ───────────────────────────────────────────────────────────────

def _read(*parts):
    path = os.path.join(CLIENT_SRC, *parts)
    if not os.path.isfile(path):
        pytest.skip(f"{path} is not in this checkout")
    return io.open(path, encoding="utf-8").read()


def test_the_toolbar_toggle_is_a_switch_not_a_disabled_placeholder():
    src = _read("analyse", "toolbar.tsx")
    assert "not in this slice" not in src and "out of slice scope" not in src
    assert 'role="switch"' in src and "aria-checked" in src
    assert 'data-testid="surrogate-toggle"' in src


def test_a_run_request_carries_the_toggle():
    assert "surrogate" in _read("api.ts").split("export const startRun")[1].split("\n\n")[0]


def test_the_footer_reads_detected_versus_surrogate():
    src = _read("analyse", "ChainPage.tsx")
    assert "null expects" in src, "with the toggle on the terminal row states what the null expects"
    assert "wall · no null" not in src, "the footer must not say 'no null' unconditionally"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
