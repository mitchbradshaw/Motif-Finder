"""The NeurIPS demo's server pieces (webui/server/demo_*.py), on a tiny synthetic store: a station answers from the
store and guards its visitor's writes with the claim; the hub hands each device its own station, returns a device
to the station it already holds, says "busy" when all are taken and frees a station that went idle; the QR encoder
round-trips through OpenCV's decoder. Run with webui/.venv (FastAPI)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webui" / "server"))

import demo_hub  # noqa: E402
import demo_station  # noqa: E402
from demo_qr import qr_matrix  # noqa: E402

KEY = "k3y"


def _store(tmp: Path) -> Path:
    """Two datasets x 2 channels, one builder setting, enough of everything for every route."""
    st = tmp / "store"
    (st / "chains" / "c1").mkdir(parents=True)
    (st / "auto").mkdir()
    (st / "stats" / "combos").mkdir(parents=True)
    (st / "surrogates").mkdir()
    (st / "clean" / "drops_w300").mkdir(parents=True)
    rng = np.random.default_rng(0)
    slices, research = [], []
    datasets = [{"key": "a", "name": "A", "latin": "a a", "channels": [0, 1], "hours": [0, 1], "blurb": ""},
                {"key": "b", "name": "B", "latin": "b b", "channels": [0, 1], "hours": [0, 1], "blurb": ""}]
    sid = 0
    for d in datasets:
        for ch in d["channels"]:
            sid += 1
            x = rng.standard_normal(3600) * 0.001
            np.save(tmp / f"s{sid}.npy", x)
            np.save(st / "clean" / "drops_w300" / f"{sid}.npy", x.astype(np.float32))
            np.save(st / "surrogates" / f"{sid}.npy", np.stack([rng.standard_normal(3600)] * 2).astype(np.float32))
            slices.append({"id": sid, "dataset": d["key"], "channel": ch, "label": f"CH{ch + 1}", "fs": 1.0, "n": 3600,
                           "units": "V", "npy": str(tmp / f"s{sid}.npy"), "t0_s": 0.0})
            evs = [{"s": 100 * k, "e": 100 * k + 20, "score": 1.0, "onset_idx": 100 * k + 2, "extremum_idx": 100 * k + 8}
                   for k in range(1, 8)]
            (st / "chains" / "c1" / f"{sid}.json").write_text(json.dumps(
                {"combo": "c1", "slice": sid, "n": len(evs), "events": evs, "null": [1, 2, 0, 1], "letters": None}))
            (st / "auto" / f"{sid}.json").write_text(json.dumps({"slice": sid, "n": 0, "events": []}))
            research.append({"slice": sid, "dataset": d["key"], "start": 100, "end": 120, "verdict": "yes"})
    combos = [{"id": "c1", "look_for": "drops", "window_s": 300.0, "detector": "noise_threshold", "knobs": {"k_sigma": 4.0}}]
    (st / "manifest.json").write_text(json.dumps({
        "datasets": datasets, "slices": slices, "combos": combos, "default_combo": "c1",
        "references": [{"key": "r", "label": "R", "combo": "c1"}, {"key": "auto", "label": "Auto", "combo": None}],
        "menu": {"look_for": [], "clean_windows_s": [300.0], "detectors": []}, "null": {"method": "x", "draws": 4}}))
    (st / "library.json").write_text(json.dumps({"events": [], "families": [], "trains": [], "totals": {}}))
    (st / "seeds.json").write_text(json.dumps({"seeds": [], "k": 25}))
    (st / "researcher_events.json").write_text(json.dumps(research))
    (st / "stats" / "library.json").write_text(json.dumps({"a": {"n": 0}}))
    return st


@pytest.fixture
def store(tmp_path):
    st = _store(tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "demo.html").write_text("<!doctype html><title>demo</title>")
    return st, dist, tmp_path / "state"


def _station(store, n=1, hub="http://hub"):
    st, dist, state = store
    return demo_station.create_station(station=n, admin_key=KEY, hub=hub, dist=dist, store_dir=st, state_dir=state)


def test_station_reads_the_store_and_hides_file_paths(store):
    c = TestClient(_station(store))
    m = c.get("/api/demo/manifest").json()
    assert len(m["slices"]) == 4 and all("npy" not in s for s in m["slices"])
    env = c.get("/api/demo/signal/1?a=0&b=3600&px=100").json()
    assert len(env["lo"]) == len(env["hi"]) <= 100 and env["step"] == 36
    assert max(env["hi"]) > 0.1, "a V slice is served in mV"
    assert c.get("/api/demo/signal/99").status_code == 404
    assert c.get("/api/demo/chain/nope/1").status_code == 404
    d = c.get("/api/demo/discovery/c1").json()
    assert d["n"] == 28 and abs(d["null"] - 4.0) < 1e-9 and abs(d["ratio"] - 7.0) < 1e-9
    refs = c.get("/api/demo/references").json()
    assert [r["key"] for r in refs] == ["r", "auto"] and refs[1]["ratio"] is None
    assert c.get("/api/demo/stats?source=library").status_code == 200
    assert c.get("/api/demo/stats?source=nope").status_code == 404


def test_snippets_answer_many_short_envelopes_in_one_request(store):
    c = TestClient(_station(store))
    r = c.post("/api/demo/snippets", json={"slice": 1, "spans": [[0, 100], [200, 260]], "px": 20})
    assert r.status_code == 200 and [len(e["lo"]) for e in r.json()] == [20, 20]
    assert c.post("/api/demo/snippets", json={"slice": 1, "spans": [[0, 10]] * 201}).status_code == 400
    assert c.post("/api/demo/snippets", json={"slice": 9, "spans": [[0, 10]]}).status_code == 404


def test_client_routes_fall_back_to_the_page_but_api_routes_never_do(store):
    c = TestClient(_station(store))
    assert c.get("/").text.startswith("<!doctype html>")
    assert c.get("/explore/anything").status_code == 200
    assert c.get("/api/demo/nothing-here").status_code == 404


def test_writes_need_the_current_claim(store):
    c = TestClient(_station(store))
    assert c.post("/api/demo/runs", json={"combo": "c1"}).status_code == 409
    assert c.post("/api/demo/admin/claim", json={"token": "T"}).status_code == 403
    assert c.post("/api/demo/admin/claim", json={"token": "T"}, headers={"x-demo-admin": KEY}).status_code == 200
    assert c.post("/api/demo/runs?token=wrong", json={"combo": "c1"}).status_code == 409
    assert c.post("/api/demo/runs?token=T", json={"combo": "c1"}).status_code == 200
    assert c.post("/api/demo/ping", json={"token": "other"}).json()["mine"] is False
    assert c.post("/api/demo/ping", json={"token": "T"}).json()["mine"] is True


def test_judge_five_is_stable_and_verdicts_persist_until_a_reset(store):
    c = TestClient(_station(store, hub=None))   # standalone: no claim needed
    j1 = c.get("/api/demo/judge/c1").json()
    j2 = c.get("/api/demo/judge/c1").json()
    assert len(j1["items"]) == 5 and j1["items"] == j2["items"]
    assert any(it["researcher"] == "yes" for it in j1["items"]), "a researcher-judged detection is preferred"
    assert c.post("/api/demo/judge", json={"combo": "c1", "item": 0, "verdict": "maybe"}).status_code == 400
    assert c.post("/api/demo/judge", json={"combo": "c1", "item": 9, "verdict": "yes"}).status_code == 404
    r = c.post("/api/demo/judge", json={"combo": "c1", "item": 0, "verdict": "yes"}).json()
    assert r["verdicts"] == {"0": "yes"}
    state_file = store[2] / "station-1.json"
    assert json.loads(state_file.read_text())["verdicts"]["c1"] == {"0": "yes"}
    assert c.post("/api/demo/admin/reset", headers={"x-demo-admin": KEY}).status_code == 200
    assert json.loads(state_file.read_text())["verdicts"] == {} and c.get("/api/demo/judge/c1").json()["verdicts"] == {}


def test_a_restarted_station_keeps_its_visitor(store):
    c = TestClient(_station(store))
    c.post("/api/demo/admin/claim", json={"token": "T"}, headers={"x-demo-admin": KEY})
    assert c.post("/api/demo/runs?token=T", json={"combo": "c1"}).status_code == 200
    again = TestClient(_station(store))          # the launcher started the process again
    assert again.post("/api/demo/ping", json={"token": "T"}).json()["mine"] is True
    assert len(again.get("/api/demo/state").json()["runs"]) == 1


def test_live_seed_refuses_stretches_it_cannot_search(store):
    c = TestClient(_station(store, hub=None))
    assert c.post("/api/demo/seed/live", json={"slice": 1, "a": 10, "b": 12}).status_code == 400
    assert c.post("/api/demo/seed/live", json={"slice": 1, "a": 0, "b": 400}).status_code == 400
    assert c.post("/api/demo/seed/live", json={"slice": 1, "a": 3590, "b": 3700}).status_code == 400
    assert c.post("/api/demo/seed/live", json={"slice": 7, "a": 0, "b": 30}).status_code == 404


# ── the hub ──

class _Ports:
    """An httpx transport that reaches in-process stations by port, as the hub reaches real ones."""

    def __init__(self, apps):
        self.clients = {port: TestClient(app) for port, app in apps.items()}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        c = self.clients[request.url.port]
        r = c.request(request.method, request.url.path, content=request.content, headers=dict(request.headers),
                      params=dict(request.url.params))
        return httpx.Response(r.status_code, content=r.content, headers=r.headers)


def _hub(store, n=2):
    apps = {8900 + k: _station(store, n=k) for k in range(1, n + 1)}
    http = httpx.Client(transport=httpx.MockTransport(_Ports(apps)))
    stations = [demo_hub.Station(k, 8900 + k) for k in range(1, n + 1)]
    hub = demo_hub.create_hub(stations=stations, admin_key=KEY, port=8900, public_url="http://booth:8900/",
                              http=http, poll=False)
    return hub, apps


def test_hub_gives_each_device_its_own_station_and_returns_a_device_to_its_own(store):
    hub, apps = _hub(store, n=2)
    d1, d2, d3 = (TestClient(hub, follow_redirects=False) for _ in range(3))
    r1 = d1.get("/claim")
    r2 = d2.get("/claim")
    assert r1.status_code == r2.status_code == 303
    p1, p2 = httpx.URL(r1.headers["location"]).port, httpx.URL(r2.headers["location"]).port
    assert {p1, p2} == {8901, 8902}
    assert d1.get("/claim").headers["location"].split("?")[0] == r1.headers["location"].split("?")[0]
    assert d3.get("/claim").headers["location"] == "/busy"
    assert "busy" in d3.get("/busy").text.lower()
    tok = httpx.URL(r1.headers["location"]).params["claim"]
    assert apps[p1].state.visitor.claim == tok


def test_an_idle_station_is_reset_and_handed_on(store):
    hub, apps = _hub(store, n=1)
    d1, d2 = TestClient(hub, follow_redirects=False), TestClient(hub, follow_redirects=False)
    assert d1.get("/claim").status_code == 303
    assert d2.get("/claim").headers["location"] == "/busy"
    apps[8901].state.visitor.last_input = time.time() - demo_hub.IDLE_RESET_S - 5
    loc = d2.get("/claim").headers["location"]
    assert httpx.URL(loc).port == 8901
    assert apps[8901].state.visitor.claim == httpx.URL(loc).params["claim"]


def test_hub_front_page_carries_the_qr_and_the_admin_page_needs_the_key(store):
    hub, _ = _hub(store, n=1)
    c = TestClient(hub)
    assert "http://booth:8900/" in c.get("/").text
    assert c.get("/qr.svg").headers["content-type"].startswith("image/svg+xml")
    assert c.get("/admin").status_code == 403
    assert "Stations" in c.get(f"/admin?key={KEY}").text


@pytest.mark.parametrize("text", ["http://192.168.137.1:8900/", "MycoWave", "http://127.0.0.1:8900/claim?x=" + "a" * 40])
def test_the_qr_code_decodes_back_to_its_text(text):
    cv2 = pytest.importorskip("cv2")
    m = np.array(qr_matrix(text), dtype=np.uint8)
    n = m.shape[0]
    img = np.full(((n + 8) * 8, (n + 8) * 8), 255, dtype=np.uint8)
    img[32:32 + n * 8, 32:32 + n * 8] = np.kron(1 - m, np.ones((8, 8), dtype=np.uint8)) * 255
    val, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
    assert val == text


def test_the_live_search_finds_what_the_core_finds():
    """demo_live's cached-FFT distance and greedy exclusion reproduce the core's match_exemplar (stumpy.match)."""
    pytest.importorskip("stumpy")
    sys.path.insert(0, str(ROOT))
    from Working.discovery import seeded_search as SS
    import demo_live as L

    rng = np.random.default_rng(3)
    x = np.cumsum(rng.standard_normal(20000)) * 0.01 - 400.0     # a drifting trace with a large offset, as in V*1000
    shape = -np.exp(-np.arange(40) / 6.0) * 3.0
    for at in (1200, 5000, 9100, 15000):
        x[at:at + 40] += shape * rng.uniform(0.5, 2.0)
    q = x[5000 - 5:5000 + 45]
    ser = L.Series(x, m_max=200)
    mine = L.top_k(ser.profile(q), 11, len(q))
    core = SS.candidates(x, q, k=11)
    assert [i for _, i in mine] == [c["index"] for c in core]
    assert np.allclose([d for d, _ in mine], [c["distance"] for c in core], atol=1e-5)
