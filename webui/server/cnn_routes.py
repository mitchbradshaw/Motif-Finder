"""fixup-ai: the bridge side of arm B.2's CNN and the full-pool Ward (ticket
`docs/prompts/fixup/AI-cnn-arm-slurm.md`; the core is `Working/training/shape_cnn.py`,
`cnn_job.py`, `full_ward.py`, `hpc_import.py`, and the script writers in
`Working/hpc/job_export.py`).

* ``POST /api/models/b2/cnn/slurm`` — Models › Launch, model *CNN* → *Create SLURM
  script* (a job: the windows are read from their channels): the job directory, the
  script (and the label-shuffle null's array script when asked), what must be copied
  to the cluster and how big it is, the estimate (labelled as one), the steps.
* ``POST /api/models/b2/cnn/smoke`` — *Run the local smoke* (a job): the same recipe on a
  few hundred windows, one epoch, this CPU, imported through the function the
  cluster's results return by; the run is then one of the B.2 runs.
* ``POST /api/shape/trees/{key}/ward-slurm`` — the Shape clustering page's *Create
  SLURM script · Ward over every training window*.
* ``cnn_setup(c, pool_key)`` — what ``GET /api/models/b2/setup`` adds for the CNN.

Results come back by ``python -m Working.training import-results <job>`` (and, with
`AJ`, Jobs › Manifest inbox): both call ``Working.training.hpc_import.import_results``.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import corpus

router = APIRouter()

RETURNS = ("Results come back by copying the job's out/ folder from the cluster into the same job directory here, "
           "then: python -m Working.training import-results <job directory> (Jobs › Manifest inbox will call the same "
           "function). The run then appears in Models › Results beside the forest run: same windows, same cut.")
REMOTE_HOST = "rangpur.compute.eait.uq.edu.au"


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def cnn_setup(c, pool_key):
    """The CNN block of Launch's B.2 setup: encodings, defaults, the image rule, the null, how results return."""
    from Working.training import shape_cnn as sc
    return {"encodings": list(sc.ENCODINGS), "default_encoding": sc.DEFAULT_ENCODING,
            "defaults": dict(sc.CNN_DEFAULTS), "smoke_defaults": dict(sc.SMOKE_DEFAULTS),
            "images_rule": sc.images_rule(sc.DEFAULT_ENCODING, sc.CNN_DEFAULTS["img_size"]),
            "augmentation": sc.AUGMENTATION_NOTE,
            "null": {"n": sc.NULL_SHUFFLES, "default_on": False,
                     "note": (f"the label-shuffle null for a CNN is {sc.NULL_SHUFFLES} full trainings on permuted "
                              "cluster labels (§9.4): an array job of its own, off by default — each task costs one "
                              "full training")},
            "measured": {enc: sc.latest_measurements(c, enc) for enc in sc.ENCODINGS},
            "returns": RETURNS,
            "fusion_note": ("fusion is built: the fusion training code is the GASF code with three channels; "
                            "MODELS/fusion_cnn.pth's one output class is a fact about that file (its training folder "
                            "held one class), not about the code — fusion_cnn_2 / _3 are two-class")}


class CnnBody(BaseModel):
    template: int
    pool: int
    encoding: str = "fusion"
    cnn: dict | None = None
    smoke: dict | None = None
    null: bool = False


def _recipe(request: Request, body: CnnBody, smoke=None):
    from Working.training import shape_cnn as sc
    from Working.training import shape_forest as sf
    from Working.training.store import CutFrozen
    from .shape_routes import _pool_row, _template
    c = _conn(request)
    try:
        t = _template(c, body.template)
        row, p = _pool_row(c, body.pool)
        try:
            recipe = sc.make_recipe({"id": int(row["id"]), "name": row["name"], "version": int(row["version"] or 1),
                                     "key": p.key}, {"id": int(t["id"]), "name": t["name"], "steps": t["steps"]},
                                    encoding=body.encoding, cnn=body.cnn, smoke=smoke)
        except ValueError as e:
            raise HTTPException(422, str(e))
        try:
            sf.check_frozen(c, p.key, recipe["arm"]["k"], recipe["arm"]["mapping"])
        except CutFrozen as e:
            raise HTTPException(409, str(e))
        return recipe
    finally:
        c.close()


def _steps(res, job_repo, remote_root, null=None):
    chans = [x for x in res["copy"] if x["what"] == "channel array"]
    s = [f"Put the code on the cluster at this commit: git push here, then git pull in {remote_root} (the job runs "
         "the repository's own code; nothing else is installed).",
         f"Copy the job directory and the {len(chans)} channel array(s) listed below to the SAME repo-relative paths "
         f"under {remote_root} — e.g. scp -r {job_repo} <you>@{REMOTE_HOST}:{remote_root}/{os.path.dirname(job_repo)}/ "
         "and each DATA/derived/channels/… file likewise (skip any already there).",
         "Once, on the login node (compute nodes may have no network): conda activate torch_env && python -c "
         "\"from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights as W; "
         "efficientnet_b0(weights=W.DEFAULT)\" — caches the ImageNet weights the network starts from.",
         f"From {remote_root}: {res['sbatch_command']}  — it checks the environment first, then encodes, trains and "
         "predicts, resubmitting itself every 20 minutes until done.",
         "Watch it: squeue -u $USER; the log is logs/<script name>_<job id>.out (each epoch prints its loss and images/s).",
         f"When the log says Complete: copy {job_repo}/out/ (not cache/) back into the same place on this machine.",
         f"Here: python -m Working.training import-results {job_repo} — the run appears in Models › Results beside "
         "the forest run; label it blind there like any B.2 run."]
    if null and null.get("on"):
        s.insert(4, f"Optional, the label-shuffle null: {null['sbatch_command']} ({null['note']}).")
    return s


@router.post("/api/models/b2/cnn/slurm")
def cnn_slurm(request: Request, body: CnnBody):
    """*Create SLURM script* for the B.2 CNN: a job (reading every window's raw bounds takes a minute)."""
    import Adapters.catalogue_shape_cluster as csc
    from Working.config import HPC_REMOTE_REPO_ROOT
    from Working.hpc.job_export import export_cnn_job, repo_relative
    from Working.recipes import short_hash
    from Working.training import shape_cnn as sc
    from .training_routes import _hpc_dir
    rt, manager = request.app.state.rt, request.app.state.manager
    recipe = _recipe(request, body)
    pre = short_hash(recipe)
    job_dir = os.path.join(_hpc_dir(rt), f"b2cnn_{body.encoding}_{pre}")
    tree_root = csc.RESULTS_DIR

    def work(job):
        cc = _conn(request)
        try:
            ex = sc.export_job(cc, recipe, job_dir, tree_root=tree_root,
                               progress=lambda d, t, m: job.progress(d, t, m))
            measured = sc.latest_measurements(cc, body.encoding)
        finally:
            cc.close()
        est = sc.estimate(ex, ex["recipe"], measured)
        base = f"b2cnn_{body.encoding}_{ex['recipe_hash']}"
        train_s = est["parts"]["train_s"]
        one_training = None if train_s is None else train_s / (2 if ex["recipe"]["cnn"].get("refit", True) else 1)
        sl = export_cnn_job(job_dir, base_name=base, est_seconds=est["seconds"],
                            null_shuffles=sc.NULL_SHUFFLES if body.null else 0, train_seconds=one_training,
                            model=sc.model_label(ex["recipe"]))
        job_repo = repo_relative(job_dir)
        return {"job_dir": job_dir, "job_repo": job_repo, "recipe_hash": ex["recipe_hash"],
                "model": sc.model_label(ex["recipe"]), "n_windows": ex["n_windows"], "n_train": ex["n_train"],
                "n_predict": ex["n_predict"], "by_scale": ex["by_scale"], "copy": ex["copy"],
                "total_bytes": ex["total_bytes"], "estimate": est, "script": sl["script"],
                "script_path": sl["script_path"], "sbatch_command": sl["sbatch_command"],
                "null_script": sl["null_script"], "null_script_path": sl["null_script_path"], "null": sl["null"],
                "slurm_time": sl["slurm_time"], "chain_jobs": sl["chain_jobs"], "jobs_needed": sl["jobs_needed"],
                "deadline_min": sl["deadline_min"], "warnings": sl["warnings"], "images_rule": recipe["inputs"]["images"],
                "steps": _steps({**ex, "sbatch_command": sl["sbatch_command"]}, job_repo, HPC_REMOTE_REPO_ROOT, sl["null"]),
                "returns": RETURNS}

    job = manager.start_job("training", work, meta={"stage": "B.2 CNN · SLURM script", "pool": recipe["pool"],
                                                    "k": recipe["arm"]["k"], "encoding": body.encoding,
                                                    "template": recipe["template"]["name"], "where": "HPC (script)"})
    return job.snapshot()


@router.post("/api/models/b2/cnn/smoke")
def cnn_smoke(request: Request, body: CnnBody):
    """*Run the local smoke*: the same recipe on a few hundred windows, one epoch, this CPU — a job."""
    import Adapters.catalogue_shape_cluster as csc
    from Working.training import shape_cnn as sc
    from .training_routes import _hpc_dir, _training_root
    rt, manager = request.app.state.rt, request.app.state.manager
    recipe = _recipe(request, body, smoke=body.smoke or {})
    root, tree_root, job_root = _training_root(rt), csc.RESULTS_DIR, os.path.join(_hpc_dir(rt), "smoke")

    def work(job):
        cc = _conn(request)
        try:
            out = sc.run_local_smoke(cc, recipe, job_root=job_root, root=root, tree_root=tree_root,
                                     progress=lambda d, t, m: job.progress(d, t, m), cancel=job.cancel_event.is_set)
        finally:
            cc.close()
        return {"run_id": int(out["run_id"]), "results_path": out.get("results_path"), "job_dir": out["job_dir"],
                "measured": out.get("measured"), "timings": out.get("timings"), "export_s": out.get("export_s"),
                "total_s": out.get("total_s"), "n_windows": out.get("n_windows"), "created": out.get("created")}

    job = manager.start_job("training", work, meta={"stage": "B.2 CNN · local smoke", "pool": recipe["pool"],
                                                    "k": recipe["arm"]["k"], "encoding": body.encoding,
                                                    "template": recipe["template"]["name"], "where": "local"})
    return job.snapshot()


class WardBody(BaseModel):
    seed: int | None = None


@router.post("/api/shape/trees/{key}/ward-slurm")
def ward_slurm(request: Request, key: str, body: WardBody | None = None):
    """*Create SLURM script · Ward over every training window* of the pool this tree was cut from."""
    import Adapters.preprocessing_trace_shape as tsh
    from Working.config import HPC_REMOTE_REPO_ROOT
    from Working.hpc.job_export import export_ward_job, repo_relative
    from Working.training import full_ward as fw
    from Working.training import shape_forest as sf
    from .shape_routes import tree_and_shapes
    from .training_routes import _hpc_dir
    rt = request.app.state.rt
    tree, shapes = tree_and_shapes(key)
    seed = int((body.seed if body and body.seed is not None else tree.meta.get("seed")) or 0)
    sp = os.path.join(tsh.RESULTS_DIR, str(shapes.key), "shapes.npz")
    if not os.path.isfile(sp):
        raise HTTPException(404, f"the shape vectors {shapes.key} are not on disk: re-run the Trace shape step")
    job_dir = os.path.join(_hpc_dir(rt), f"ward_full_{shapes.key}_s{seed}")
    ex = fw.export_job(sp, job_dir, seed=seed)
    sl = export_ward_job(job_dir, base_name=f"ward_full_{ex['recipe_hash']}", n=ex["n"],
                         est_seconds=ex["seconds_estimate"], memory=ex["memory"])
    c = _conn(request)
    try:
        fz = sf.frozen_for(c, ex["pool_key"]) if ex["pool_key"] else None
    finally:
        c.close()
    job_repo = repo_relative(job_dir)
    steps = [f"Put the code on the cluster at this commit (git pull in {HPC_REMOTE_REPO_ROOT}).",
             f"Copy the job directory ({ex['total_bytes'] / 2 ** 20:.0f} MB) to the same repo-relative path: scp -r "
             f"{job_repo} <you>@{REMOTE_HOST}:{HPC_REMOTE_REPO_ROOT}/{os.path.dirname(job_repo)}/",
             f"From {HPC_REMOTE_REPO_ROOT}: {sl['sbatch_command']}",
             f"When the log says Complete: copy {job_repo}/out/ back into the same place here.",
             f"Here: python -m Working.training import-results {job_repo} — the tree is kept where the Shape "
             "clustering block looks for a tree over every training window: set its sample to 0 and re-run; then "
             "choose the cut and the mapping again (a new tree numbers its clusters anew)."]
    return {"job_dir": job_dir, "job_repo": job_repo, "recipe_hash": ex["recipe_hash"], "n": ex["n"],
            "memory": ex["memory"], "seconds_estimate": ex["seconds_estimate"], "slurm_time": sl["slurm_time"],
            "partition": sl["partition"], "script": sl["script"], "script_path": sl["script_path"],
            "sbatch_command": sl["sbatch_command"], "copy": ex["copy"], "total_bytes": ex["total_bytes"],
            "steps": steps, "returns": RETURNS, "warnings": sl["warnings"],
            "frozen": fz, "frozen_note": (None if fz is None else
                                          f"run {fz['run_id']} already has a test score on this pool: the import of "
                                          "this tree will be refused (a new tree changes every cluster)")}
