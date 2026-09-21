"""Drive every Discovery route against a running bridge, on real data.

    "/c/ProgramData/anaconda3/python.exe" webui/drive_discovery.py --url http://127.0.0.1:8765

The evidence for stage-3 prompt 04: one real seeded search and one real
template application over a four-hour section of two channels, then the
scoreboard, the compare pages and the run acts over what they produced.
Writes `webui/screenshots/wiring/04/summary.json` and prints a table.

The default scope is chosen for what is in the database rather than for a
round number: M2_aug_concat_fs1 80–84 h on CH1_A1 and CH8_B2 has annotations
of **both** verdicts on both channels, so precision has real negatives in it,
and the drop-motif seed family `id035` sits at the same wall time on CH16_D2,
so the seed and the ground truth are the same hours of the same experiment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "screenshots", "wiring", "04")

DEFAULT_RECORDING = "M2_aug_concat_fs1"
DEFAULT_CHANNELS = ["CH1_A1", "CH8_B2"]
DEFAULT_T0, DEFAULT_T1 = 80.0, 84.0
DEFAULT_FAMILY = "id035"


class Bridge:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.calls = []

    def _req(self, method, path, body=None, timeout=900):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"content-type": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read().decode() or "null")
            self.calls.append({"method": method, "path": path, "status": 200,
                               "ms": round((time.perf_counter() - t0) * 1e3, 1)})
            return out
        except urllib.error.HTTPError as e:
            raw = e.read().decode(errors="replace")
            self.calls.append({"method": method, "path": path, "status": e.code,
                               "ms": round((time.perf_counter() - t0) * 1e3, 1), "body": raw[:400]})
            try:
                return {"__error__": e.code, **json.loads(raw)}
            except Exception:
                return {"__error__": e.code, "body": raw[:2000]}

    get = lambda self, p, **kw: self._req("GET", p, **kw)            # noqa: E731
    post = lambda self, p, b=None, **kw: self._req("POST", p, b, **kw)  # noqa: E731
    put = lambda self, p, b=None, **kw: self._req("PUT", p, b, **kw)    # noqa: E731


def qs(**kw):
    from urllib.parse import urlencode
    return "?" + urlencode({k: v for k, v in kw.items() if v is not None})


def wait_job(b, job_id, what, timeout_s=1800):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        snap = b.get(f"/api/jobs/{job_id}")
        if snap.get("__error__"):
            return snap
        p = snap.get("progress") or {}
        line = f"{p.get('done')}/{p.get('total')} {p.get('message', '')}"
        if line != last:
            print(f"    {what}: {line}")
            last = line
        if snap["status"] in ("completed", "failed", "cancelled"):
            return snap
        time.sleep(2)
    return {"status": "timeout"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("WEBUI_URL", "http://127.0.0.1:8765"))
    ap.add_argument("--recording", default=DEFAULT_RECORDING)
    ap.add_argument("--channels", default=",".join(DEFAULT_CHANNELS))
    ap.add_argument("--t0", type=float, default=DEFAULT_T0)
    ap.add_argument("--t1", type=float, default=DEFAULT_T1)
    ap.add_argument("--family", default=DEFAULT_FAMILY)
    ap.add_argument("--template", default="drop_detection_v1")
    ap.add_argument("--draws", type=int, default=20)
    ap.add_argument("--k", type=int, default=200)
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    b = Bridge(a.url)
    channels = [c for c in a.channels.split(",") if c]
    summary = {"url": a.url, "recording": a.recording, "channels": channels,
               "section_h": [a.t0, a.t1], "steps": []}

    def step(name, value):
        print(f"  {name}: {value}")
        summary["steps"].append({"step": name, "result": value})

    print("[runtime]")
    rt = b.get("/api/runtime")
    step("mode", rt.get("mode"))

    print("[scope]")
    s = b.put("/api/discovery/session", {
        "name": f"{a.recording} {a.t0:g}-{a.t1:g} h", "recording": a.recording,
        "channels": channels, "section": [a.t0, a.t1],
        "null": {"method": "phase randomisation", "n": a.draws}})
    assert not s.get("__error__"), s
    step("session", f"{s['session']['name']} · {s['session']['channels']} · "
                    f"{s['session']['section'][0]:.2f}–{s['session']['section'][1]:.2f} h · "
                    f"null {s['session']['null']['method']} {s['session']['null']['n']}x")
    step("matching rule", s["session"]["matchingRule"])

    print("[held out]")
    refused = b.put("/api/discovery/session", {"recording": "M4_aug_concat_fs1"})
    step("M4 refused", f"{refused.get('__error__')} {str(refused.get('detail', {}))[:120]}")
    b.put("/api/discovery/session", {"recording": a.recording, "channels": channels,
                                     "section": [a.t0, a.t1]})

    print("[overview]")
    ov = b.get("/api/discovery/overview" + qs(recording=a.recording, channels=",".join(channels)))
    step("overview", {k: len(v) for k, v in (ov.get("data") or {}).items()})

    print("[seeds]")
    seeds = b.get("/api/discovery/seeds")
    step("seeds", f"{len(seeds['seeds'])} · {seeds['counts']}")
    step("seed note", seeds.get("note"))
    pick = next((x for x in seeds["seeds"] if x["source"] == "medoid" and x.get("family") == a.family),
                None) or next((x for x in seeds["seeds"] if x["source"] == "medoid"), None) \
        or seeds["seeds"][0]
    step("seed", f"{pick['id']} · {pick['role']} · {pick['title']} · {pick['samples']} samples "
                 f"· {pick['recording']} {pick['channel']} · hash {pick['hash']}")

    print("[seed setup]")
    setup = b.get("/api/discovery/seed/setup" + qs(seed=pick["id"]))
    step("recommended", setup["recommended"])

    print("[seeded search]")
    body = {"seedId": pick["id"], "channels": channels, "t0": a.t0, "t1": a.t1,
            "k": a.k, "maxDistance": 0.0}
    started = b.post("/api/discovery/seed/results", body)
    if not started.get("ready"):
        snap = wait_job(b, started["job_id"], "seeded search")
        step("search job", snap["status"])
        assert snap["status"] == "completed", snap.get("error")
    res = b.get("/api/discovery/seed/results" + qs(seedId=pick["id"], channels=",".join(channels),
                                                   t0=a.t0, t1=a.t1, k=a.k, maxDistance=0.0))
    assert res.get("ready"), res
    ds = [c["d"] for c in res["candidates"]]
    step("matches", f"{len(res['candidates'])} candidates · d {min(ds):.3f}–{max(ds):.3f} · "
                    f"{sum(1 for c in res['candidates'] if c['judged'])} already judged")
    step("null", f"{res['null']['method']} · {res['null']['draws']} draws · "
                 f"{len(res['null']['distances'])} distances · "
                 f"min {min(res['null']['distances']):.3f}" if res["null"]["distances"] else "no null")
    step("recommended cut", res["recommendedCut"])
    step("per channel", res["perChannel"])
    step("exclusion", res["exclusionNote"])

    print("[distance profile]")
    prof = b.get("/api/discovery/seed/profile" + qs(seedId=pick["id"], channel=channels[0],
                                                    t0=a.t0, t1=a.t0 + 0.5))
    step("profile", f"{prof['nDistance']} distances over {prof['nSignal']} samples · m {prof['m']}")

    print("[plan]")
    plan = b.post("/api/discovery/plan", {"seedId": pick["id"], "channels": channels,
                                          "t0": a.t0, "t1": a.t1, "k": a.k})
    step("plan", f"{plan['n_channels']} channels · route {plan['route']} · "
                 f"estimate {plan['estimate_s']} · ceiling {plan['ceiling_s']} s · "
                 f"uncosted steps {plan['uncosted']}")
    step("reuse note", plan.get("reuseNote"))

    print("[preview on a sample]")
    pv = b.post("/api/discovery/preview", {"template": a.template, "channels": channels,
                                           "t0": a.t0, "t1": a.t1, "sampleHours": 1.0})
    if not pv.get("__error__"):
        step("preview", f"{pv['sample_hours']:.2f} h sample on {pv['channel']} · "
                        f"measured {pv['measured_s']:.2f} s · per channel {pv['per_channel_s']:.1f} s · "
                        f"{pv['spans_in_sample']} spans → ≈ {pv['extrapolated_spans']} over the scope · "
                        f"route {pv['route']}")
    else:
        step("preview", pv)

    print("[run the seed search]")
    run = b.post("/api/discovery/seed/run", {"seedId": pick["id"], "channels": channels, "t0": a.t0,
                                             "t1": a.t1, "k": a.k,
                                             "cut": res["recommendedCut"] or 0.0,
                                             "label": f"seed_{a.family}"})
    assert not run.get("__error__"), run
    seed_key = run["run_key"]
    if run.get("job_id"):
        snap = wait_job(b, run["job_id"], "seed run")
        step("seed run", f"{seed_key} · {snap['status']} · {snap.get('result')}")

    print("[apply a template]")
    applied = b.post("/api/discovery/templates/apply", {"templates": [a.template], "channels": channels,
                                                        "t0": a.t0, "t1": a.t1, "run": True})
    assert isinstance(applied, list), applied          # a dict here is the error envelope
    tpl_key = applied[0]["run_key"]
    if applied[0].get("job_id"):
        snap = wait_job(b, applied[0]["job_id"], a.template)
        step("template run", f"{tpl_key} · {snap['status']} · {snap.get('result')}")

    print("[runs]")
    runs = b.get("/api/discovery/runs")
    step("runs", [f"{r['key']}:{r['status']}:{r.get('found')}" for r in runs])

    print("[where each run fires]")
    fires = b.get("/api/discovery/fires" + qs(channels=",".join(channels), t0=a.t0, t1=a.t1,
                                              runs=",".join(["human", seed_key, tpl_key])))
    step("fires", f"{fires['nBins']} bins of {fires['binH']} h · " +
         " · ".join(f"{c['channel']} reviewed {c['reviewedH']:.2f} h: " +
                    ", ".join(f"{r['run']}={sum(r['counts'])}" for r in c["rows"])
                    for c in fires["channels"]))

    print("[scoreboard]")
    sb = b.get("/api/discovery/scoreboard" + qs(runs=",".join([seed_key, tpl_key]),
                                                channels=",".join(channels), t0=a.t0, t1=a.t1))
    for row in sb:
        t = row["total"]
        precision = "—" if t["precision"] is None else "{:.2f}".format(t["precision"])
        step(f"scoreboard {row['run']}",
             f"found {t['found']} · judged {t['judged']} · reviewed {t['reviewed']} · "
             f"interesting {t['interesting']} · precision {precision} · "
             f"recall {t['recall']} · null {t['nullExpects']} · x null {t['xNull']} · "
             f"pooled {row['pooledH']:.2f} h")
        for ch in row["channels"]:
            step(f"  {row['run']} {ch['channel']}",
                 f"found {ch['found']} reviewed {ch['reviewed']} interesting {ch['interesting']} "
                 f"precision {ch['precision']} recall {ch['recall']} note {ch['note']}")

    print("[browse]")
    dets = b.get("/api/discovery/detections" + qs(run=tpl_key, channel=channels[0], t0=a.t0, t1=a.t1))
    step("detections", f"{len(dets)} on {channels[0]}")
    if dets:
        d0 = dets[0]
        step("first detection", f"{d0['id']} at {d0['atH']:.3f} h · {d0['durationS']} s · "
                                f"depth {d0['depthMv']} mV · score {d0['score']} · "
                                f"prior {d0['priorVerdict']} · also {d0['alsoFoundBy']}")
        w = b.get(f"/api/discovery/detections/{d0['detectionId']}/window")
        step("detection window", f"{len(w['values'])} points from {w['t0H']:.3f} h")

    print("[compare]")
    cmp_ = b.get("/api/discovery/compare" + qs(a=tpl_key, b=seed_key, channels=",".join(channels),
                                               t0=a.t0, t1=a.t1))
    assert not cmp_.get("__error__"), cmp_
    step("compare", f"{len(cmp_['differing'])} roles differ ({cmp_['differing']}) · "
                    f"overlap {cmp_['total']} · {cmp_['disagreementsTotal']} disagreements · "
                    f"{len(cmp_['both'])} agreed")
    step("attributable", cmp_["attributionNote"] or "one role differs — attributable")
    step("stage diff", cmp_["stageDiff"][:2])
    if cmp_["disagreements"]:
        d = cmp_["disagreements"][0]
        win = b.get("/api/discovery/compare/window" + qs(a=tpl_key, b=seed_key, channel=d["channel"],
                                                         atH=d["atH"], kind=d["kind"],
                                                         detection=d["detection"]))
        step("compare window", f"{d['kind']} at {d['atH']:.3f} h · {len(win['values'])} points · "
                               f"other score {len(win['bScore'])} points · note {win['scoreNote']}")
        st = b.get("/api/discovery/compare/stages" + qs(a=tpl_key, b=seed_key, channel=d["channel"],
                                                        atH=d["atH"], kind=d["kind"], index=1,
                                                        of=cmp_["disagreementsTotal"]))
        step("compare stages", f"first differing {st['firstDiffering']} · A " +
             " ".join(f"{c['role'][:4]}:{c['badge']}" for c in st["a"]) + " · B " +
             " ".join(f"{c['role'][:4]}:{c['badge']}" for c in st["b"]))

    print("[human as a compare side]")
    ch_cmp = b.get("/api/discovery/compare" + qs(a=tpl_key, b="human", channels=",".join(channels),
                                                 t0=a.t0, t1=a.t1))
    step("vs human", f"overlap {ch_cmp['total']} · b.found {ch_cmp['b']['found']}")

    print("[slurm]")
    slurm = b.post("/api/discovery/slurm", {"template": a.template, "channels": channels,
                                            "t0": a.t0, "t1": a.t1})
    step("slurm", f"{os.path.basename(slurm.get('script_path', '?'))} · "
                  f"{len(slurm.get('script', ''))} chars · array over {plan['n_channels']} channels"
         if not slurm.get("__error__") else slurm)

    print("[run acts]")
    disc = b.post(f"/api/discovery/runs/{seed_key}/discard")
    step("discard", f"{disc['status']} · {disc['superseded']} runs · "
                    f"adjudications {disc['adjudications_written']} · annotations {disc['annotations_written']}")
    rev = b.post(f"/api/discovery/runs/{tpl_key}/review", {"limit": 500})
    step("send to review", f"{rev['queued']} of {rev['unjudged']} unjudged → '{rev['queue']}' "
                           f"(writes {rev['writes']})")
    back = b.post(f"/api/discovery/runs/{seed_key}/restore")
    step("restore", back["status"])

    print("[history]")
    hist = b.get("/api/discovery/history")
    step("history", [f"{h['id']}:{h['status']}" for h in hist[:4]])

    summary["calls"] = b.calls
    summary["errors"] = [c for c in b.calls if c["status"] >= 400 and "M4" not in str(c.get("body", ""))]
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    n_err = len(summary["errors"])
    print(f"\n{len(b.calls)} calls, {n_err} unexpected errors → {os.path.join(OUT, 'summary.json')}")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
