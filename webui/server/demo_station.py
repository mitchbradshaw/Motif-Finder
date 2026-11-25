"""One NeurIPS demo station: a private copy of the demo for one visitor (docs/neurips_demo/DECISIONS.md).

    python webui/server/demo_station.py --port 8901 --station 1 --admin-key K [--hub http://host:8900] [--dist DIR]

Run from the repo root. Every answer is read from the pre-cooked store under DATA/neurips_demo/store/ (written by
scripts/neurips_demo/) and the slice arrays; nothing a visitor does reaches the store, a database or any other
station. The visitor's own state (their runs, verdicts) is one JSON file, state/station-<n>.json, which a reset
deletes. The one computation a visitor can start is a live seed search on the 12 slices (numpy, under a second).

Loud failure: a bad request is a 4xx with a reason, a bug is a 500 with its traceback in the log. Nothing is caught
into a blank.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "DATA" / "neurips_demo" / "store"
STATE_DIR = ROOT / "DATA" / "neurips_demo" / "state"
DIST = ROOT / "webui" / "client" / "dist-neurips"

IDLE_RESET_S = 600.0          # Q3: a claimed station with no input for 10 min is reset by the hub
JUDGE_N = 5                   # Q5 / round 2 item 4


# ── the store (read only, loaded once) ───────────────────────────────────────────────────────────────────────────

class Store:
    def __init__(self, store: Path):
        self.dir = store
        self.manifest = json.loads((store / "manifest.json").read_text())
        self.slices = {s["id"]: s for s in self.manifest["slices"]}
        self.combos = {c["id"]: c for c in self.manifest["combos"]}
        self._x = {}
        self._lock = threading.Lock()
        self.library = json.loads((store / "library.json").read_text())
        self.seeds = json.loads((store / "seeds.json").read_text())
        self.researcher = json.loads((store / "researcher_events.json").read_text())
        self._auto = {sid: json.loads((store / "auto" / f"{sid}.json").read_text()) for sid in self.slices}

    def x(self, sid: int) -> np.ndarray:
        """The slice in mV (V slices x 1000), kept in memory."""
        with self._lock:
            if sid not in self._x:
                s = self.slices[sid]
                a = np.load(ROOT / s["npy"], mmap_mode="r")
                k = 1000.0 if (s["units"] or "V") == "V" else 1.0
                self._x[sid] = np.asarray(a, dtype=np.float64) * k
            return self._x[sid]

    @lru_cache(maxsize=96)
    def clean(self, look: str, window: int, sid: int) -> np.ndarray:
        s = self.slices[sid]
        a = np.load(self.dir / "clean" / f"{look}_w{window}" / f"{sid}.npy")
        k = 1000.0 if (s["units"] or "V") == "V" else 1.0
        return np.asarray(a, dtype=np.float64) * k

    @lru_cache(maxsize=256)
    def summary(self, key: str) -> dict | None:
        """Discovery's summary of a setting, pre-computed (precompute_summaries.py); None when it is not there."""
        p = self.dir / "summary" / f"{key}.json"
        return json.loads(p.read_text()) if p.exists() else None

    @lru_cache(maxsize=256)
    def judge(self, key: str) -> list | None:
        p = self.dir / "judge" / f"{key}.json"
        return json.loads(p.read_text()) if p.exists() else None

    @lru_cache(maxsize=96)
    def chain(self, combo: str, sid: int) -> dict:
        p = self.dir / "chains" / combo / f"{sid}.json"
        if not p.exists():
            raise HTTPException(404, f"no pre-computed result for {combo} on slice {sid}")
        return json.loads(p.read_text())

    def auto(self, sid: int) -> dict:
        return self._auto[sid]

    @lru_cache(maxsize=256)
    def stats(self, source: str) -> dict:
        p = (self.dir / "stats" / f"{source}.json") if source in ("library", "auto") else \
            (self.dir / "stats" / "combos" / f"{source}.json")
        if not p.exists():
            raise HTTPException(404, f"no statistics for {source}")
        return json.loads(p.read_text())

    @lru_cache(maxsize=4)
    def surrogates(self) -> dict:
        return {sid: np.load(self.dir / "surrogates" / f"{sid}.npy").astype(np.float64) for sid in self.slices}


# ── the visitor's state ──────────────────────────────────────────────────────────────────────────────────────────

class State:
    """The one mutable thing a station holds. Written atomically; a reset removes it."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.data = self._load()
        # the claim and epoch live in the file too, so a station the launcher restarts keeps its visitor
        self.claim = self.data.get("_claim")
        self.epoch = int(self.data.get("_epoch", 0))
        self.last_input = time.time()

    def _blank(self):
        return {"runs": [], "verdicts": {}, "seeds": [], "created": time.time()}

    def _load(self):
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except json.JSONDecodeError:
                pass
        return self._blank()

    def save(self):
        self.data["_claim"], self.data["_epoch"] = self.claim, self.epoch
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data))
        os.replace(tmp, self.path)

    def reset(self, claim=None):
        """Everything the last visitor did is gone; the file holds only the new claim and epoch."""
        with self.lock:
            self.data = self._blank()
            self.claim = claim
            self.epoch += 1
            self.last_input = time.time()
            self.save()


# ── reading helpers ──────────────────────────────────────────────────────────────────────────────────────────────

def envelope(x: np.ndarray, a: int, b: int, px: int):
    """min/max per bucket over x[a:b], at most px buckets: what a trace plot draws without losing a spike."""
    a, b = max(0, int(a)), min(len(x), int(b))
    if b - a < 2:
        raise HTTPException(400, "range too short")
    px = max(16, min(int(px), 4000))
    n = b - a
    step = max(1, int(math.ceil(n / px)))
    seg = x[a: a + (n // step) * step]
    if step == 1:
        lo = hi = seg
    else:
        r = seg.reshape(-1, step)
        lo, hi = r.min(axis=1), r.max(axis=1)
    return {"a": a, "b": a + len(lo) * step, "step": step, "lo": np.round(lo, 4).tolist(), "hi": np.round(hi, 4).tolist()}


def _overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def researcher_verdict(store: Store, sid: int, s: int, e: int):
    """The researcher's verdict on the span [s, e) of slice sid, if a judged span covers it (half of the shorter)."""
    best = None
    for r in store.researcher:
        if r["slice"] != sid:
            continue
        ov = _overlap(s, e, r["start"], r["end"])
        if ov <= 0:
            continue
        frac = ov / max(1, min(e - s, r["end"] - r["start"]))
        if frac >= 0.5 and (best is None or frac > best[0]):
            best = (frac, r["verdict"])
    return best[1] if best else None


def summary_of(store: Store, combo: str):
    """A builder setting across every slice: counts against the null, per slice and per dataset."""
    per, by_ds = [], {}
    for sid, s in store.slices.items():
        r = store.chain(combo, sid)
        null = r.get("null") or []
        mu = float(np.mean(null)) if null else None
        sd = float(np.std(null)) if null else None
        per.append({"slice": sid, "n": r["n"], "null_mean": mu, "null_sd": sd,
                    "spans": [[ev["s"], ev["e"]] for ev in r["events"]][:2000]})
        d = by_ds.setdefault(s["dataset"], {"n": 0, "null": 0.0})
        d["n"] += r["n"]
        d["null"] += mu or 0.0
    tot = sum(d["n"] for d in by_ds.values())
    tot_null = sum(d["null"] for d in by_ds.values())
    return {"combo": combo, "per_slice": per, "by_dataset": by_ds, "n": tot, "null": tot_null,
            "ratio": (tot / tot_null) if tot_null > 0 else None}


def auto_summary(store: Store):
    per, by_ds = [], {}
    for sid, s in store.slices.items():
        a = store.auto(sid)
        per.append({"slice": sid, "n": a["n"], "null_mean": None, "null_sd": None,
                    "spans": [[e["s"], e["e"]] for e in a["events"]]})
        d = by_ds.setdefault(s["dataset"], {"n": 0, "null": None})
        d["n"] += a["n"]
    return {"combo": None, "per_slice": per, "by_dataset": by_ds, "n": sum(d["n"] for d in by_ds.values()),
            "null": None, "ratio": None}


def judge_items(store: Store, combo: str):
    """Five of the setting's detections, one per dataset first, preferring ones the researcher has judged too, the
    same five every time for the same setting (so a reload or a second visitor sees the same quiz)."""
    rng = random.Random(combo)
    pools = {}
    for sid, s in store.slices.items():
        for ev in store.chain(combo, sid)["events"]:
            v = researcher_verdict(store, sid, ev["s"], ev["e"])
            pools.setdefault(s["dataset"], []).append((v is not None, sid, ev, v))
    picks = []
    order = [d["key"] for d in store.manifest["datasets"]]
    while len(picks) < JUDGE_N and any(pools.get(k) for k in order):
        for k in order:
            if len(picks) >= JUDGE_N:
                break
            pool = pools.get(k) or []
            if not pool:
                continue
            judged = [p for p in pool if p[0]]
            src = judged or pool          # prefer what the researcher judged too: the comparison is the point
            p = src[rng.randrange(len(src))]
            pool.remove(p)
            _, sid, ev, v = p
            picks.append({"item": len(picks), "slice": sid, "s": ev["s"], "e": ev["e"],
                          "onset": ev.get("onset_idx"), "extremum": ev.get("extremum_idx"),
                          "depth_mv": ev.get("event_amplitude_mv"), "researcher": v})
    return picks


# ── the app ──────────────────────────────────────────────────────────────────────────────────────────────────────

class Claim(BaseModel):
    token: str | None = None


class RunBody(BaseModel):
    combo: str


class Verdict(BaseModel):
    combo: str
    item: int
    verdict: str


class LiveSeed(BaseModel):
    slice: int
    a: int
    b: int


class Snips(BaseModel):
    slice: int
    spans: list[list[int]]
    px: int = 120


def create_station(*, station: int, admin_key: str, hub: str | None, dist: Path = DIST,
                   store_dir: Path = STORE, state_dir: Path = STATE_DIR, seed_worker: str | None = None) -> FastAPI:
    store = Store(store_dir)
    state = State(state_dir / f"station-{station}.json")
    app = FastAPI(title=f"MycoWave demo station {station}", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store, app.state.visitor = store, state

    def admin(request: Request):
        if request.headers.get("x-demo-admin") != admin_key:
            raise HTTPException(403, "admin only")

    def guard(token: str | None):
        """A visitor's write must carry the station's current claim, so an old tab cannot write into the next
        visitor's copy. Standalone (no hub) there is no claim and every write goes through."""
        if hub is None:
            return
        if not token or token != state.claim:
            raise HTTPException(409, "this station has been handed to someone else")

    # ── station control (the hub) ──
    @app.get("/api/demo/admin/status")
    def admin_status(request: Request):
        admin(request)
        return {"station": station, "claim": state.claim, "epoch": state.epoch,
                "idle_s": round(time.time() - state.last_input, 1), "runs": len(state.data["runs"])}

    @app.post("/api/demo/admin/claim")
    def admin_claim(body: Claim, request: Request):
        admin(request)
        state.reset(claim=body.token)
        return {"ok": True, "epoch": state.epoch}

    @app.post("/api/demo/admin/reset")
    def admin_reset(request: Request):
        admin(request)
        state.reset(claim=None)
        return {"ok": True, "epoch": state.epoch}

    # ── the visitor's session ──
    @app.post("/api/demo/ping")
    def ping(body: Claim):
        """The client calls this on real input (a click or a key, throttled): the hub's idle clock."""
        mine = hub is None or (body.token is not None and body.token == state.claim)
        if mine:
            state.last_input = time.time()
        return {"mine": mine, "station": station, "epoch": state.epoch, "hub": hub}

    @app.post("/api/demo/start-over")
    def start_over(body: Claim):
        guard(body.token)
        state.reset(claim=state.claim)
        return {"ok": True, "epoch": state.epoch}

    @app.get("/api/demo/state")
    def get_state():
        return {"station": station, "hub": hub, "epoch": state.epoch,
                **{k: v for k, v in state.data.items() if not k.startswith("_")}}

    # ── the data ──
    @app.get("/api/demo/manifest")
    def manifest():
        m = dict(store.manifest)
        m["slices"] = [{k: v for k, v in s.items() if k not in ("npy",)} for s in store.manifest["slices"]]
        m["combos"] = list(store.manifest["combos"])
        m["station"] = station
        return m

    @app.get("/api/demo/signal/{sid}")
    def signal(sid: int, a: int = 0, b: int = 0, px: int = 1200, combo: str | None = None):
        if sid not in store.slices:
            raise HTTPException(404, f"no slice {sid}")
        if combo:
            c = store.combos.get(combo)
            if c is None:
                raise HTTPException(404, f"no setting {combo}")
            x = store.clean(c["look_for"], int(round(c["window_s"])), sid)
        else:
            x = store.x(sid)
        b = b or len(x)
        return envelope(x, a, b, px)

    @app.post("/api/demo/snippets")
    def snippets(body: Snips):
        """Many short envelopes of one channel in one request (Analyse's Describe step draws up to 40 events)."""
        if body.slice not in store.slices:
            raise HTTPException(404, f"no slice {body.slice}")
        if len(body.spans) > 200:
            raise HTTPException(400, "at most 200 spans")
        x = store.x(body.slice)
        return [envelope(x, a, b, body.px) for a, b in body.spans]

    @app.get("/api/demo/auto/{sid}")
    def auto(sid: int):
        if sid not in store.slices:
            raise HTTPException(404, f"no slice {sid}")
        return store.auto(sid)

    @app.get("/api/demo/chain/{combo}/{sid}")
    def chain(combo: str, sid: int):
        if combo not in store.combos or sid not in store.slices:
            raise HTTPException(404, "unknown setting or slice")
        return store.chain(combo, sid)

    def summary(key: str):
        if key != "auto" and key not in store.combos:
            raise HTTPException(404, f"no setting {key}")
        s = store.summary(key)
        if s is None:
            s = auto_summary(store) if key == "auto" else summary_of(store, key)
        return s

    @app.get("/api/demo/discovery/{combo}")
    def discovery(combo: str):
        return summary(combo)

    @app.get("/api/demo/references")
    def references():
        out = []
        for r in store.manifest["references"]:
            s = summary("auto" if r["combo"] is None else r["combo"])
            out.append({**r, "n": s["n"], "null": s["null"], "ratio": s["ratio"], "by_dataset": s["by_dataset"]})
        return out

    @app.post("/api/demo/runs")
    def add_run(body: RunBody, token: str | None = None):
        guard(token)
        if body.combo not in store.combos:
            raise HTTPException(404, f"no setting {body.combo}")
        with state.lock:
            run = {"id": len(state.data["runs"]) + 1, "combo": body.combo, "at": time.time()}
            state.data["runs"].append(run)
            state.save()
        return run

    @app.get("/api/demo/judge/{combo}")
    def judge(combo: str):
        if combo not in store.combos:
            raise HTTPException(404, f"no setting {combo}")
        items = store.judge(combo)
        if items is None:
            items = judge_items(store, combo)
        mine = state.data["verdicts"].get(combo, {})
        return {"combo": combo, "items": items, "verdicts": mine}

    @app.post("/api/demo/judge")
    def give_verdict(body: Verdict, token: str | None = None):
        guard(token)
        if body.verdict not in ("yes", "no", "unsure"):
            raise HTTPException(400, "a verdict is yes, no or unsure")
        if body.combo not in store.combos or not (0 <= body.item < JUDGE_N):
            raise HTTPException(404, "unknown item")
        with state.lock:
            state.data["verdicts"].setdefault(body.combo, {})[str(body.item)] = body.verdict
            state.save()
        return {"ok": True, "verdicts": state.data["verdicts"][body.combo]}

    @app.get("/api/demo/library")
    def library():
        return store.library

    @app.get("/api/demo/seeds")
    def seeds():
        return store.seeds

    @app.post("/api/demo/seed/live")
    def live_seed(body: LiveSeed):
        if body.slice not in store.slices:
            raise HTTPException(404, f"no slice {body.slice}")
        s = store.slices[body.slice]
        a, b = int(body.a), int(body.b)
        n = b - a
        if n < 8:
            raise HTTPException(400, "mark a longer stretch: at least 8 samples")
        if n > int(300 * s["fs"]):
            raise HTTPException(400, "mark a shorter stretch: at most 5 minutes")
        if a < 0 or b > s["n"]:
            raise HTTPException(400, "the stretch is outside the recording")
        t0 = time.perf_counter()
        if seed_worker:
            import httpx
            r = httpx.post(f"{seed_worker}/search", json={"slice": body.slice, "a": a, "b": b},
                           headers={"x-demo-admin": admin_key}, timeout=30.0)
            if r.status_code != 200:
                raise HTTPException(r.status_code, f"seed worker: {r.text[:300]}")
            out = r.json()
        else:
            from demo_live import live_search   # standalone: the core's own match_exemplar, in this process
            out = live_search(store, body.slice, a, b)
        out["elapsed_s"] = round(time.perf_counter() - t0, 3)
        return out

    @app.get("/api/demo/stats")
    def stats(source: str):
        return store.stats(source)

    # ── the client ──
    @app.get("/{path:path}")
    def client(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, f"no route /{path}")
        f = (dist / path).resolve()
        if path and f.is_file() and dist.resolve() in f.parents:
            return FileResponse(f)
        idx = dist / "demo.html"
        if not idx.exists():
            raise HTTPException(500, f"the demo client is not built: {idx} is missing (npm run build:neurips)")
        return FileResponse(idx, headers={"Cache-Control": "no-cache"})

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--station", type=int, required=True)
    ap.add_argument("--admin-key", required=True)
    ap.add_argument("--hub", default=None)
    ap.add_argument("--dist", default=str(DIST))
    ap.add_argument("--seed-worker", default=None, help="the shared live seed search, e.g. http://127.0.0.1:8909")
    a = ap.parse_args()
    os.chdir(ROOT)
    import uvicorn
    app = create_station(station=a.station, admin_key=a.admin_key, hub=a.hub, dist=Path(a.dist),
                         seed_worker=a.seed_worker)
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
