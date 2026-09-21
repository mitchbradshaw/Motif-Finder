"""Analyse routes added by stage-3 prompt 01: templates as rows, and the job model.

Mounted by ``create_app`` (``app.include_router``). Reads the runtime and the
``JobManager`` off ``request.app.state`` so the module needs nothing at import.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from Working.templates import apply_template

from . import chain as chain_mod
from . import corpus
from . import templates as T

router = APIRouter()


class Step(BaseModel):
    stage: str
    algorithm: str
    params: dict = Field(default_factory=dict)
    side_inputs: dict = Field(default_factory=dict)


class TemplateIn(BaseModel):
    name: str
    steps: list[Step]
    kind: str | None = None
    description: str = ""


class TemplateEdit(BaseModel):
    name: str | None = None
    steps: list[Step] | None = None
    description: str | None = None


class ApplyBody(BaseModel):
    recording_id: int
    span: list[int] | None = None


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def _steps(steps):
    return [s.model_dump() for s in steps]


# ------------------------------------------------------------ templates --
@router.get("/api/templates")
def list_templates(request: Request):
    c = _conn(request)
    try:
        rows = T.list_all(c)
    finally:
        c.close()
    for r in rows:
        r["id"] = r["id"]                     # int ids for every row; the old "builtin:<name>" ids are gone
        r["valid"] = chain_mod.validate(r["steps"])["ok"]
    return rows


@router.get("/api/templates/{template_id}")
def get_template(request: Request, template_id: int):
    c = _conn(request)
    try:
        return T.get(c, template_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    finally:
        c.close()


@router.post("/api/templates")
def create_template(request: Request, body: TemplateIn):
    v = chain_mod.validate(_steps(body.steps))
    if not v["ok"]:
        raise HTTPException(422, {"message": "chain is invalid", "junctions": v["junctions"]})
    c = _conn(request)
    try:
        tid = T.save(c, body.name, _steps(body.steps), kind=body.kind, description=body.description)
        row = T.get(c, tid)
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        c.close()
    row["note"] = request.app.state.rt.banner()
    return row


@router.put("/api/templates/{template_id}")
def edit_template(request: Request, template_id: int, body: TemplateEdit):
    steps = _steps(body.steps) if body.steps is not None else None
    if steps is not None:
        v = chain_mod.validate(steps)
        if not v["ok"]:
            raise HTTPException(422, {"message": "chain is invalid", "junctions": v["junctions"]})
    c = _conn(request)
    try:
        return T.update(c, template_id, steps=steps, name=body.name, description=body.description)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    finally:
        c.close()


@router.delete("/api/templates/{template_id}")
def delete_template(request: Request, template_id: int):
    c = _conn(request)
    try:
        T.delete(c, template_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    finally:
        c.close()
    return {"deleted": template_id}


@router.post("/api/templates/{template_id}/apply")
def apply_template_route(request: Request, template_id: int, body: ApplyBody):
    """The recipe a template becomes on a recording (validated by the core), ready for POST /api/runs."""
    c = _conn(request)
    try:
        tpl = T.get(c, template_id)
        recipe = apply_template(c, tpl, body.recording_id, span=tuple(body.span) if body.span else None)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        c.close()
    return {"template": {"id": tpl["id"], "name": tpl["name"], "kind": tpl["kind"], "version": tpl["version"]}, "recipe": recipe}


# ----------------------------------------------------------------- jobs --
@router.get("/api/jobs")
def list_jobs(request: Request, limit: int = 50):
    return request.app.state.manager.list_jobs(limit=max(1, min(500, limit)))


def _job_or_404(request: Request, job_id: int):
    snap = request.app.state.manager.snapshot(job_id)
    if snap is None:
        raise HTTPException(404, f"no job {job_id}")
    return snap


@router.get("/api/jobs/{job_id}")
def get_job(request: Request, job_id: int):
    return _job_or_404(request, job_id)


@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(request: Request, job_id: int):
    manager = request.app.state.manager
    job = manager.jobs.get(job_id)
    if job is None:
        snap = _job_or_404(request, job_id)
        return {"accepted": False, "status": snap["status"], "note": "the job is not in memory (finished before a restart); nothing to cancel"}
    return {"accepted": manager.cancel(job), "status": job.status, "note": "cancel is cooperative"}


@router.get("/api/jobs/{job_id}/events")
async def job_events(request: Request, job_id: int):
    manager = request.app.state.manager
    job = manager.jobs.get(job_id)
    if job is None:
        snap = _job_or_404(request, job_id)

        async def once():
            yield f"event: hello\ndata: {json.dumps(snap)}\n\n"
            yield f"event: job_end\ndata: {json.dumps({'event': 'job_end', 'job_id': job_id, 'status': snap['status'], 'restored': True})}\n\n"
        return StreamingResponse(once(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

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
                if e["event"] in ("run_end", "job_end"):
                    break
        finally:
            manager.unsubscribe(job, q)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
