"""FastAPI bridge for the web UI. Thin: every route is a few lines over
``server/{corpus,chain,runs,serialize}.py``. Errors are **loud**: an
unhandled exception returns a 500 whose body carries the traceback and is
logged to ``runtime/<stamp>/server.log``; the page shows it in a red card.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import traceback

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Match
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from Working.database.queries import not_surrogate
from Working.database.runs import list_runs, load_recipe

from . import chain as chain_mod
from . import corpus
from . import templates as templates_mod
from .jobs import JobManager
from .runtime import HELD_OUT_FILE, Runtime
from .analyse_routes import router as analyse_router
from .discovery import router as discovery_router
from .discovery_map import router as discovery_map_router
from .explore_routes import router as explore_router
from .interrogation_routes import router as interrogation_router
from .library import router as library_router
from .review import router as review_router
from .training_routes import router as training_router
from .shape_routes import router as shape_router
from .blind_routes import router as blind_router
from .cnn_routes import router as cnn_router
from .jobs_routes import router as jobs_router   # fixup-aj
from .registration import router as registration_router

log = logging.getLogger("webui")


class Step(BaseModel):
    stage: str
    algorithm: str
    params: dict = Field(default_factory=dict)
    side_inputs: dict = Field(default_factory=dict)


class ChainBody(BaseModel):
    recording_id: int | None = None
    span: list[int] | None = None
    steps: list[Step]
    position: int | None = None


class RunBody(BaseModel):
    recording_id: int
    span: list[int] | None = None
    steps: list[Step]
    px: int = 1200
    #: the toolbar's surrogate toggle (Q38). Off by default in Analyse: the
    #: tuning loop is seconds, and Discovery is where a claim is made.
    surrogate: bool = False


class TemplateBody(BaseModel):
    name: str
    steps: list[Step]


def _steps(body) -> list[dict]:
    return [s.model_dump() for s in body.steps]


def create_app(rt: Runtime) -> FastAPI:
    app = FastAPI(title="Underground Brains — web UI bridge", docs_url="/api/docs", openapi_url="/api/openapi.json")
    manager = JobManager(rt.db_path, meta_dir=getattr(rt, "meta_dir", None))
    app.state.rt = rt
    app.state.manager = manager
    app.state.started = time.time()

    def conn():
        return corpus.connect(rt.db_path)

    def rec_or_423(recording_id: int) -> dict:
        c = conn()
        try:
            rec = corpus.recording_row(c, recording_id)
        finally:
            c.close()
        if rec is None:
            raise HTTPException(404, f"no recording id {recording_id}")
        if rec["held_out"]:
            raise HTTPException(423, f"{HELD_OUT_FILE} is held out (spec §0 D6 / Working.config.HELD_OUT_RECORDING_FILE); the web UI refuses it")
        return rec

    # the canonical templates are rows from the first start on (prompt 01 "Templates")
    _c = conn()
    try:
        app.state.templates_seeded = templates_mod.seed_canonical(_c)
    finally:
        _c.close()

    @app.on_event("startup")
    async def _startup():
        manager.attach_loop(asyncio.get_running_loop())
        # warm STUMPY's numba JIT off the request path (first matrix_profile call otherwise pays ~30 s)
        def _warm():
            try:
                import numpy as np, stumpy
                stumpy.stump(np.random.default_rng(0).standard_normal(256), 8)
                log.info("stumpy JIT warm")
            except Exception as e:  # pragma: no cover
                log.warning("stumpy warm-up skipped: %s", e)
        import threading
        threading.Thread(target=_warm, daemon=True, name="stumpy-warm").start()

    @app.exception_handler(Exception)
    async def _loud(request: Request, exc: Exception):
        tb = traceback.format_exc()
        log.error("unhandled %s on %s %s\n%s", type(exc).__name__, request.method, request.url.path, tb)
        return JSONResponse(status_code=500, content={"error": f"{type(exc).__name__}: {exc}", "traceback": tb, "path": request.url.path})

    # ------------------------------------------------------------- meta ----
    @app.get("/api/health")
    def health():
        return {"ok": True, "uptime_s": time.time() - app.state.started, "jobs": len(manager.jobs)}

    @app.get("/api/runtime")
    def runtime_info():
        return rt.describe()

    @app.get("/api/boom")
    def boom(kind: str = "server"):
        """Deliberate failure endpoint for the loud-failure evidence."""
        raise RuntimeError("deliberate server-side failure (GET /api/boom)")

    # ---------------------------------------------------------- explore ----
    @app.get("/api/recordings")
    def get_recordings():
        c = conn()
        try:
            return corpus.recordings(c)
        finally:
            c.close()

    @app.get("/api/corpus/{source_file}/coverage")
    def get_coverage(source_file: str, bins: int = 57, verdicts: str | None = None, run: str | None = None, method: str | None = None):
        if source_file == HELD_OUT_FILE:
            raise HTTPException(423, f"{HELD_OUT_FILE} is held out; the corpus map refuses it")
        c = conn()
        try:
            vs = tuple(v for v in verdicts.split(",") if v) if verdicts else None
            run_ids = [int(r) for r in run.split(",") if r.strip()] if run else None
            return corpus.coverage(c, source_file, bins=max(4, min(400, bins)), verdicts=vs, run_ids=run_ids, method=method or None)
        except KeyError:
            raise HTTPException(404, f"unknown recording {source_file}")
        finally:
            c.close()

    @app.get("/api/channels/{recording_id}")
    def get_channel(recording_id: int):
        rec = rec_or_423(recording_id)
        c = conn()
        try:
            rec["summary"] = corpus.channel_summary(c, recording_id)
            rec["ribbons"] = corpus.ribbons(c, recording_id, rec["fs"], rec["n_samples"])
            rec["y_range"] = corpus.y_range(rec)
            return rec
        finally:
            c.close()

    @app.get("/api/channels/{recording_id}/window")
    def get_window(recording_id: int, t0: float = 0.0, t1: float | None = None, px: int = 1200):
        rec = rec_or_423(recording_id)
        if t1 is None:
            t1 = rec["duration_s"]
        if not (0 <= t0 < t1):
            raise HTTPException(422, f"window must satisfy 0 <= t0 < t1 <= {rec['duration_s']:.0f} s; got t0={t0}, t1={t1}")
        px_used = max(16, min(8000, px))
        c = conn()
        try:
            out = corpus.window(c, rec, t0, min(t1, rec["duration_s"]), px_used)
        finally:
            c.close()
        out["px_used"] = px_used
        resp = JSONResponse(out)
        resp.headers["Server-Timing"] = f"decimate;dur={out['decimate_ms']:.2f}"
        return resp

    @app.get("/api/channels/{recording_id}/spans")
    def get_spans(recording_id: int, t0: float = 0.0, t1: float | None = None):
        rec = rec_or_423(recording_id)
        if t1 is None:
            t1 = rec["duration_s"]
        if not (0 <= t0 < t1):
            raise HTTPException(422, f"window must satisfy 0 <= t0 < t1 <= {rec['duration_s']:.0f} s; got t0={t0}, t1={t1}")
        c = conn()
        try:
            return corpus.spans(c, recording_id, t0, t1, rec["fs"])
        finally:
            c.close()

    # ---------------------------------------------------------- analyse ----
    @app.get("/api/adapters")
    def get_adapters():
        return chain_mod.catalog()

    @app.post("/api/chain/validate")
    def post_validate(body: ChainBody):
        steps = _steps(body)
        out = chain_mod.validate(steps)
        if body.recording_id is not None and out["ok"] and steps:
            rec = rec_or_423(body.recording_id)
            span = tuple(body.span) if body.span else None
            try:
                recipe = chain_mod.build_recipe(body.recording_id, span, steps)
            except ValueError as e:
                out["recipe_error"] = str(e)
                return out
            n = (span[1] - span[0]) if span else rec["n_samples"]
            out["hashes"] = chain_mod.hashes(recipe)
            c = conn()
            try:
                out["cache"] = chain_mod.cache_status(recipe, c)
                # the real chain's route, before any null: over the limit, Run writes a SLURM job instead
                routed = chain_mod.route_local(recipe, n, rec["fs"], ceiling_s=chain_mod.analyse_ceiling_s(c))
            finally:
                c.close()
            out["estimate"] = chain_mod.estimate(recipe, n, rec["fs"])
            out["route"] = {k: routed[k] for k in ("route", "estimate_s", "ceiling_s", "slowest")}
            # round A_2 (P2): a step the step cache holds is served whatever its span — it is not over anything
            cached = {s["index"] for s in out["cache"] if s["cached"]}
            out["over_ceiling"] = [i for i, s in enumerate(recipe["steps"]) if i not in cached
                                   and (lambda spec: spec.max_span_samples is not None and n > spec.max_span_samples)(chain_mod.get_adapter(f"{s['stage']}.{s['algorithm']}"))]
        return out

    @app.post("/api/chain/compatible")
    def post_compatible(body: ChainBody):
        pos = body.position if body.position is not None else len(body.steps)
        return chain_mod.compatible_at(_steps(body), pos)

    @app.post("/api/chain/params")
    def post_params(body: Step):
        """Validated (defaults filled, coerced, range-checked) params for one step."""
        try:
            return {"params": chain_mod.validated_params(body.model_dump())}
        except (ValueError, KeyError) as e:
            raise HTTPException(422, str(e))

    # /api/templates lives in analyse_routes.py (rows seeded from templates.py)

    # -------------------------------------------------------------- runs ----
    @app.post("/api/runs")
    def post_run(body: RunBody):
        rec = rec_or_423(body.recording_id)
        span = tuple(body.span) if body.span else None
        steps = _steps(body)
        v = chain_mod.validate(steps)
        if not v["ok"]:
            raise HTTPException(422, {"message": "chain is invalid", "junctions": v["junctions"]})
        try:
            recipe = chain_mod.build_recipe(body.recording_id, span, steps)
        except ValueError as e:
            raise HTTPException(422, str(e))
        n = (span[1] - span[0]) if span else rec["n_samples"]
        # round A_2 (P2): the span cap guards a COMPUTATION. A step the step cache holds (a whole-span matrix
        # profile imported from the cluster) is served whatever its span. An uncached step over its cap is refused
        # here, as before P2 — fix round (F5): a TIME-capped one was written as the old one-way SLURM job
        # (`_slurm_refusal`: no return path, no resume); the refusal now names the way that comes back
        # (`_over_cap_message`)
        c = conn()
        try:
            cached = {s_["index"] for s_ in chain_mod.cache_status(dict(recipe, surrogate=True) if body.surrogate
                                                                   else recipe, c) if s_["cached"]}
        finally:
            c.close()
        over = [{"index": i, "name": f"{s['stage']}.{s['algorithm']}", "max_span_samples": chain_mod.get_adapter(f"{s['stage']}.{s['algorithm']}").max_span_samples}
                for i, s in enumerate(recipe["steps"])
                if i not in cached
                and chain_mod.get_adapter(f"{s['stage']}.{s['algorithm']}").max_span_samples is not None
                and n > chain_mod.get_adapter(f"{s['stage']}.{s['algorithm']}").max_span_samples]
        if over:
            raise HTTPException(422, {"message": _over_cap_message(over, n), "over_ceiling": over})
        null = None
        if body.surrogate:
            # the detection-chain null of Settings › Nulls: method, draws, and a fixed block if one is set
            from Working.discovery import seeded_search as ss
            c = conn()
            try:
                resolved = ss.null_from_settings(c, kind=ss.DETECTION_KIND)
            finally:
                c.close()
            if not resolved["supported"]:
                raise HTTPException(422, {"message": resolved["reason"]})
            params = {"method": resolved["method"], "seed": 0}
            if resolved["method"] == "block_shuffle" and resolved.get("block_s"):
                params["block_s"] = resolved["block_s"]
            null = {"params": params, "draws": int(resolved["draws"])}
            recipe["surrogate"] = True     # the run records that it carried a null, as a Discovery run does
        # A run that cannot finish here is refused BEFORE it starts — a job in progress cannot be stopped inside a
        # step (cancel is checked between steps), so a days-long FLUSS once left the bridge to be killed by hand
        # (2026-10-14). Over the Analyse limit the chain is written as a SLURM job instead.
        from Working.discovery import routing as _routing
        c = conn()
        try:
            routed = chain_mod.route_local(recipe, n, rec["fs"], ceiling_s=chain_mod.analyse_ceiling_s(c),
                                           draws=(null or {}).get("draws", 0))
            # round A_2 (P2): what the step cache holds costs nothing, in the real run and in each null draw — the
            # rule Discovery's plan uses
            cost = _routing.target_cost(c, recipe, samples=n, fs=rec["fs"], draws=(null or {}).get("draws", 0),
                                        surrogate_params=(null or {}).get("params"))
        finally:
            c.close()
        if cost["capped"]:
            # fix round (F5): the real chain is cached or under its caps, but a null draw would compute a step over
            # a time cap (its own profile is not cached): refused as above, never the one-way SLURM job
            # a draw's steps are its surrogate step and then the chain's: the chain's own index is one less
            caps = [{"index": (st["index"] - 1 if str(st.get("where")).startswith("draw ") else st["index"]),
                     "name": st["name"], "max_span_samples": st["cap"], "where": st.get("where")}
                    for st in cost["capped"]]
            w = str(caps[0]["where"] or "")
            say = (f" in null draw {int(w.split()[-1]) + 1}" if w.startswith("draw ")
                   else " in the null's draws" if w == "draws" else "")
            raise HTTPException(422, {"message": _over_cap_message(caps, n, where=say, null_off=True),
                                      "over_ceiling": caps})
        if cost["cached"] or cost["draws_cached"]:
            routed = dict(routed, route=_routing.route(cost["seconds"], routed["ceiling_s"]),
                          estimate_s=(cost["seconds"] if cost["seconds"] is not None else routed["estimate_s"]),
                          estimate_real_s=cost["real_s"], cached=cost["cached"])
        if routed["route"] == "cluster":
            raise HTTPException(422, _slurm_refusal(recipe, rec, routed))
        if routed.get("calibrating"):
            # W3-F fix 1: a step whose cost model is still being timed on this machine would start blind (route
            # "unknown"); every entry point (chain page, block page, a script) is held here until it lands
            steps_c = ", ".join(f"{i + 1:02d}" for i in routed["calibrating"])
            raise HTTPException(409, f"calibrating: the cost model of stage {steps_c} is being timed on this machine "
                                     f"(once per machine; most take seconds, rupture about 7 minutes) — run again "
                                     f"when the chain page shows its estimate (a run over the local limit is then "
                                     f"written as a SLURM job instead of starting here)")
        job = manager.start(recipe, rec, px=body.px, null=null)
        return job.snapshot()

    def _over_cap_message(over: list, n: int, *, where: str = "", null_off: bool = False) -> str:
        """The 422 message for a chain with an uncached step over its span cap (fix round, F5). A MEMORY cap is a
        limit wherever the step runs: shorten the span (the message before P2). A TIME cap is this machine's budget:
        the cluster computes the step, through Discovery's chain job — which comes back as a Discovery run and
        leaves the profile in the step cache, where this chain then finds it (a cached step is not over anything).
        Analyse no longer writes the old one-way SLURM job for it (`_slurm_refusal`: no return path, no resume)."""
        from Working.discovery import routing as _routing
        mem = [x for x in over if _routing.cap_kind(x["name"]) != "time"]
        x = (mem or over)[0]
        head = (f"stage {x['index'] + 1:02d} ({x['name']}){where} exceeds its local ceiling of "
                f"{x['max_span_samples']:,} samples (span is {n:,})")
        if mem:
            return head + "; shorten the span or route it to HPC (out of slice scope)"
        return (head + ": this machine does not compute it. Shorten the span"
                + (", turn the null off" if null_off else "")
                + ", or send it to the cluster from Discovery › Runs › Create SLURM script: that chain job (the null "
                  "in the same task) comes back as a Discovery run and leaves the profile in the step cache, and the "
                  "same chain over the same span then runs here")

    def _slurm_refusal(recipe: dict, rec, routed: dict) -> dict:
        """The 422 body for a run over the local limit, after writing its SLURM job (`Working.hpc.job_export`,
        the exporter Discovery's *Create SLURM script* uses). The script runs the real chain only: a paired null
        has no task in the generic job, so the wall time is the real chain's and the body says the null is not
        in it rather than implying it is."""
        from Working.hpc.job_export import export_job
        from Working.config import HPC_MAX_WALLTIME_MINUTES
        from .runtime import REPO_ROOT
        out_dir = (os.path.join(rt.dir, "hpc") if rt.mode == "sandbox"
                   else os.path.join(REPO_ROOT, "HPC", "Detection", "generated"))
        os.makedirs(out_dir, exist_ok=True)
        slow = routed["slowest"] or {"name": "the chain", "index": 0}
        span = recipe.get("span") or [0, rec["n_samples"]]
        base = f"analyse_{slow['name'].split('.')[-1]}_rec{rec['id']}_{int(span[0])}-{int(span[1])}"
        data_files = ["DATA/db/annotations.sqlite"] + ([rec["npy_path"]] if rec["npy_path"] else [])
        res = export_job(recipe, out_dir=out_dir, base_name=base, job_name=base,
                         est_seconds=routed["estimate_real_s"], data_files=data_files)
        script = ""
        if os.path.isfile(res["script_path"]):
            with open(res["script_path"], encoding="utf-8") as f:
                script = f.read()
        fmt = chain_mod.fmt_seconds
        draws = routed["draws"]
        null_note = (f"the script runs the real chain only — the {draws} null draws that pushed this run over the "
                     f"limit are not in it" if draws else None)
        # the cluster's QOS caps a job's wall time (Working.config); a non-resumable chain longer than that is
        # submittable but will be killed, so say so rather than let the script imply it will finish
        over_walltime = routed["estimate_real_s"] > HPC_MAX_WALLTIME_MINUTES * 60
        n_span = int(span[1]) - int(span[0])
        n_local = chain_mod.max_local_samples(recipe, rec["fs"], ceiling_s=routed["ceiling_s"], draws=draws,
                                              upper=n_span)
        n_cluster = chain_mod.max_local_samples(recipe, rec["fs"], ceiling_s=HPC_MAX_WALLTIME_MINUTES * 60,
                                                upper=n_span)
        msg = (f"not run: this chain needs about {fmt(routed['estimate_s'])} on this machine"
               + (f" ({draws} null draws included)" if draws else "")
               + f" — stage {slow['index'] + 1:02d} ({slow['name']}) is the slow one — over the Analyse local limit "
                 f"of {fmt(routed['ceiling_s'])}. The longest span that runs here is about "
                 f"{fmt(n_local / rec['fs'])}. A SLURM job was written instead: {res['sbatch_command']} "
                 f"(script {res['script_path']}).")
        if over_walltime:
            msg += (f" But the cluster stops a job after {HPC_MAX_WALLTIME_MINUTES} min, and the real chain alone "
                    f"needs about {fmt(routed['estimate_real_s'])} at this machine's speed, so this job will most "
                    f"likely be killed before it finishes: a span of about {fmt(n_cluster / rec['fs'])} or less fits.")
        return {"message": msg, "route": "cluster", "estimate_s": routed["estimate_s"],
                "estimate_real_s": routed["estimate_real_s"], "ceiling_s": routed["ceiling_s"],
                "slowest": routed["slowest"], "calibration": routed["calibration"],
                "max_local_samples": n_local, "max_cluster_samples": n_cluster,
                "slurm": {**{k: res[k] for k in ("script_path", "recipe_path", "sbatch_command", "slurm_time",
                                                   "job_name", "warnings")},
                          "script": script, "null_note": null_note, "over_walltime": over_walltime}}

    @app.get("/api/runs")
    def get_runs(recording_id: int | None = None, limit: int = 30):
        if recording_id is not None:
            rec_or_423(recording_id)
        c = conn()
        try:
            held = {r["id"] for r in c.execute("SELECT id FROM recordings WHERE source_file = ?", (HELD_OUT_FILE,))}
            # the run history lists results; a paired surrogate run is its parent's null, not
            # a result, and its n_detections is not a count of detections (fixup-T)
            real = {r["id"] for r in c.execute("SELECT r.id FROM runs r WHERE " + not_surrogate("r"))}
            rows = [r for r in list_runs(c, recording_id=recording_id)
                    if r["recording_id"] not in held and r["id"] in real][:limit]
            out = []
            for row in rows:
                d = dict(row)
                d["cancelled"] = bool(d["status"] == "failed" and (d.get("error_text") or "").startswith("Cancelled"))
                try:
                    recipe = load_recipe(c, d["config_id"])
                    d["steps"] = [f"{s['stage']}.{s['algorithm']}" for s in recipe["steps"]]
                    d["recipe"] = recipe
                except Exception:
                    d["steps"] = []; d["recipe"] = None
                d["step_timings"] = json.loads(d["step_timings_json"]) if d.get("step_timings_json") else None
                d["n_detections"] = c.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (d["id"],)).fetchone()[0]
                out.append(d)
            live = [j.snapshot() for j in manager.jobs.values()]
            return {"db_runs": out, "jobs": live}
        finally:
            c.close()

    def job_or_404(job_id: int):
        job = manager.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, f"no job {job_id} (jobs live in server memory for this server's lifetime)")
        return job

    @app.get("/api/runs/{job_id}")
    def get_run(job_id: int):
        return job_or_404(job_id).snapshot()

    @app.post("/api/runs/{job_id}/cancel")
    def post_cancel(job_id: int):
        job = job_or_404(job_id)
        return {"accepted": manager.cancel(job), "status": job.status,
                "note": "cancel is cooperative: the core checks it once before each step, never mid-step"}

    @app.get("/api/runs/{job_id}/steps/{index}")
    def get_step_payload(job_id: int, index: int, px: int | None = None):
        job = job_or_404(job_id)
        if index not in job.payloads:
            raise HTTPException(404, f"step {index} of job {job_id} has no payload yet (status {job.steps[index]['status'] if index < len(job.steps) else '?'})")
        return job.payloads[index]

    @app.get("/api/runs/{job_id}/steps/{index}/frames/{frame}")
    def get_step_frame(job_id: int, index: int, frame: int):
        """One frame of an image Encoding the payload did not sample (fixup-h: "scan through the rest")."""
        from .serialize import frame_payload
        job = job_or_404(job_id)
        src = (getattr(job, "frame_sources", None) or {}).get(index)
        if src is None:
            raise HTTPException(410, f"the images of step {index} of job {job_id} are no longer held in memory "
                                     f"(only the most recent runs keep them) · re-run the chain to scan its frames")
        try:
            return frame_payload(src[0], {}, src[1], frame)
        except IndexError as e:
            raise HTTPException(404, str(e))

    @app.get("/api/runs/{job_id}/log")
    def get_run_log(job_id: int):
        job = job_or_404(job_id)
        return {"job_id": job_id, "lines": job.log_lines, "error": job.error}

    @app.get("/api/runs/{job_id}/events")
    async def get_events(job_id: int, request: Request):
        job = job_or_404(job_id)
        q = manager.subscribe(job)

        async def gen():
            try:
                yield f"event: hello\ndata: {json.dumps(job.snapshot())}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        e = await asyncio.wait_for(q.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    yield f"event: {e['event']}\ndata: {json.dumps(e)}\n\n"
                    if e["event"] == "run_end":
                        break
            finally:
                manager.unsubscribe(job, q)

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/runs/{job_id}/export")
    def get_export(job_id: int):
        """Could-have: export the run as a simple self-contained JSON report (recipe, timings, summaries, payloads)."""
        job = job_or_404(job_id)
        path = os.path.join(rt.exports_dir, f"run-{job_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"snapshot": job.snapshot(), "payloads": job.payloads}, f)
        return {"path": path, "bytes": os.path.getsize(path)}

    # stage-3 Prompt 02: registry, settings, audit, about, storage (server/registration.py)
    app.include_router(registration_router)

    # ---------------------------------------------- stage-3 prompt 01 routers --
    app.include_router(analyse_router)
    app.include_router(explore_router)
    app.include_router(interrogation_router)
    app.include_router(training_router)
    app.include_router(shape_router)   # fixup-ag
    app.include_router(blind_router)   # fixup-ah
    app.include_router(cnn_router)     # fixup-ai
    app.include_router(jobs_router)    # fixup-aj

    # stage-3 prompt 04: Discovery — the session and its runs, the fan-out, the
    # scoreboard, the seeded search and the two Compare pages (server/discovery.py).
    # Registered BEFORE the /api guard below: Starlette matches in registration
    # order, so a router included after it is unreachable and every call comes
    # back as the JSON 404, which reads like a typo rather than a wiring bug.
    app.include_router(discovery_router)
    # Discovery › Map (2026-10-12): the detection map's three reads, same ordering rule
    app.include_router(discovery_map_router)

    # stage-3 prompt 03: Library — counts, groupings, recurrence, the atlas,
    # family detail, the grouping editor, import, hand edits and export
    # (server/library.py). Before the /api guard, for the reason above it.
    app.include_router(library_router)

    # stage-3 prompt 05: Review — queues, verdicts, undo, promotion, clusters
    # and event extraction (server/review.py). Before the /api guard.
    app.include_router(review_router)

    # ------------------------------------------------- /api never falls through --
    # Registered after every real /api route and before the SPA catch-all: an
    # unknown /api path is a JSON 404 (a typo used to come back as index.html with
    # a 200), and a wrong method on a real route stays a JSON 405.
    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    async def api_not_found(request: Request, rest: str):
        allowed = set()
        for route in app.router.routes:
            path = str(getattr(route, "path", "") or "")
            if path == "/api/{rest:path}" or not path.startswith("/api/"):
                continue   # only real API routes count; the SPA catch-all is not one
            match, _ = route.matches(request.scope)
            if match == Match.PARTIAL:
                allowed.update(getattr(route, "methods", None) or ())
        if allowed:
            return JSONResponse(status_code=405, headers={"Allow": ", ".join(sorted(allowed))},
                                content={"error": f"method {request.method} not allowed on {request.url.path}",
                                         "path": request.url.path, "allowed": sorted(allowed)})
        return JSONResponse(status_code=404,
                            content={"error": f"no such API route: {request.method} {request.url.path}",
                                     "path": request.url.path, "docs": "/api/docs"})

    # ------------------------------------------------------- static client --
    dist = rt.client_dist
    if os.path.isdir(dist):
        if os.path.isdir(os.path.join(dist, "assets")):
            app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")), name="assets")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            candidate = os.path.join(dist, full_path)
            if full_path and os.path.isfile(candidate):
                return FileResponse(candidate)
            # index.html is unhashed, so a browser that cached it keeps loading the
            # OLD hashed bundle after a rebuild -- make it revalidate on every load.
            return FileResponse(os.path.join(dist, "index.html"), headers={"Cache-Control": "no-cache"})
    else:
        @app.get("/")
        def no_client():
            return JSONResponse({"note": "client/dist not built; run `npm run build` in client/ or use `npm run dev` with the proxy",
                                 "api": "/api/docs"})

    return app
