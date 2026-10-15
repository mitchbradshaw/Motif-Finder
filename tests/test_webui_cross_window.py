"""
test_webui_cross_window.py
==========================
fixup-AQ, the route half of Explore › Cross-channel (X3/X4): `GET /api/cross/{id}?detrend=linear` hands the core's
classifier the linearly detrended window in ONE call per pair, says which treatment it applied, keeps the
as-recorded lag and r beside it (so a page can say what the drift alone read), and prints the rule that binned
the row — the window rule, which does not claim the chance test or the noise floor it did not run.

The synthetic recording: two channels drifting in opposite directions over the window, one event on the
reference at 1500 s that reaches channel 2 twelve seconds later.

FastAPI lives only in `webui/.venv`, so this file skips under the conda pytest; run it with:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_cross_window.py
"""
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.cross_channel import ARTIFACT, INDEPENDENT_RECURRENCE, PROPAGATION  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

N = 3000
W0, W1 = 1180.0, 1820.0          # a 640 s window: a 600 s span plus 20 s each side


def _ar1(seed, phi=0.97, scale=0.0005):
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(N) * scale
    x = np.zeros(N)
    for i in range(1, N):
        x[i] = phi * x[i - 1] + e[i]
    return x


def _event(at, width=60, depth=0.03):
    u = np.zeros(N)
    u[at:at + width] = -depth * np.sin(np.pi * np.arange(width) / width)
    return u


@pytest.fixture
def client(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    ramp = np.linspace(0.0, 0.5, N)          # volts: ~0.1 V of drift across the window, as M2_aug's channels do
    chans = {0: -1.5 + ramp + _event(1500) + _ar1(1), 1: -0.4 - 0.7 * ramp + _event(1512) + _ar1(2)}
    for ch, x in chans.items():
        npy = tmp_path / f"CH{ch}.npy"; np.save(npy, x)
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                     "VALUES ('syn.mat', ?, 1.0, ?, 0, ?, 'V')", (ch, N, str(npy)))
    conn.commit(); conn.close()
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261015-cross-window", db_source=str(db),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            yield c
    finally:
        rt.restore()


def _other(body):
    return next(c for c in body["channels"] if not c["is_reference"])


def test_as_recorded_the_drift_reads_as_a_zero_lag_anticorrelation(client):
    """The X3 symptom on synthetic data: what the page showed before."""
    body = client.get("/api/cross/1", params={"t0": W0, "t1": W1}).json()
    row = _other(body)
    assert row["lag_s"] == 0.0 and row["r"] < -0.9
    assert body["detrend"] == "none"


def test_detrended_the_route_finds_the_event_at_its_lag(client):
    r = client.get("/api/cross/1", params={"t0": W0, "t1": W1, "detrend": "linear"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["detrend"] == "linear"
    row = _other(body)
    assert row["lag_s"] == pytest.approx(12.0) and row["r"] > 0.5
    assert row["classification"] == PROPAGATION
    # the as-recorded reading travels beside it, so the page can say what the drift alone read
    assert row["as_recorded"]["lag_s"] == 0.0 and row["as_recorded"]["r"] < -0.9
    assert row["as_recorded"]["classification"] in (ARTIFACT, INDEPENDENT_RECURRENCE)


def test_the_rule_printed_is_the_rule_the_window_was_binned_by(client):
    body = client.get("/api/cross/1", params={"t0": W0, "t1": W1, "detrend": "linear"}).json()
    rules = body["rules"]
    assert set(rules) == {ARTIFACT, PROPAGATION, INDEPENDENT_RECURRENCE}
    assert "detrend" in rules[ARTIFACT].lower() and "0.98" in rules[ARTIFACT]
    assert "not run" in rules[ARTIFACT], "the window is never put through the chance test; the words must not claim it"
    raw = client.get("/api/cross/1", params={"t0": W0, "t1": W1}).json()["rules"]
    assert "as recorded" in raw[ARTIFACT]


def test_an_unknown_detrend_is_refused_in_words(client):
    r = client.get("/api/cross/1", params={"t0": W0, "t1": W1, "detrend": "cubic"})
    assert r.status_code == 422 and "detrend" in r.text
