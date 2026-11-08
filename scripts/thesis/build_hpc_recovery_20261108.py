"""Build a self-contained recovery archive from audited local returns; never submits jobs."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

HERE = Path(__file__).resolve().parent
THESIS = HERE.parents[1]
MAIN = Path("C:/Users/mmebr/Documents/CNN")
OUT = MAIN / "DATA/derived/hpc/recovery_20261108"
REL = OUT.relative_to(MAIN).as_posix()
AUDIT = THESIS / "docs/thesis/data/hpc_return_20261108/audit.json"


def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    audit = json.loads(AUDIT.read_text())
    m = {"version": 1, "date": "2026-11-08",
         "seed_root": "DATA/derived/hpc/rq2_drop_transfer_20261107",
         "tasks": [], "seed_checkpoints": [], "backed_up_returns": [],
         "inputs": {}, "runtime_hashes": {}, "model_hashes": {},
         "packs": {"seed": {"parallel": 5, "gpu": False},
                   "cpu": {"parallel": 3, "gpu": False},
                   "cnn": {"parallel": 4, "gpu": True},
                   "mpA": {"parallel": 1, "gpu": True, "wall_budget_s": 16200,
                           "task_budget_s": 15000, "min_launch_s": 14000},
                   "mpB": {"parallel": 1, "gpu": True, "wall_budget_s": 16200,
                           "task_budget_s": 15000, "min_launch_s": 14000}}}
    runtime = OUT / "runtime"
    for folder in ("Working", "Adapters", "Pipelines"):
        for p in (MAIN / folder).rglob("*"):
            if p.is_file() and p.suffix in (".py", ".json") and "__pycache__" not in p.parts:
                dst = runtime / p.relative_to(MAIN)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dst)
                m["runtime_hashes"][dst.relative_to(OUT).as_posix()] = sha(dst)
    shutil.copy2(HERE / "hpc_recovery_worker.py", OUT / "worker.py")
    for name in ("GASF_cnn.pth", "GADF_cnn.pth", "recurrence_cnn.pth", "fusion_cnn_3.pth"):
        p = MAIN / "MODELS" / name
        m["model_hashes"][p.relative_to(MAIN).as_posix()] = sha(p)
    seedman = json.loads((MAIN / m["seed_root"] / "manifest.json").read_text())
    for d in seedman["datasets"]:
        for p in d["input_paths"]:
            m["inputs"][p] = d["samples_per_channel"]
    # Preserve all 64 checkpoints as a fallback; restore never replaces a more advanced checkpoint.
    for row in audit["seed"]:
        src = MAIN / row["path"]
        checkpoint = Path("checkpoints") / src.relative_to(MAIN / m["seed_root"])
        dst = OUT / checkpoint
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        m["seed_checkpoints"].append({"copy": checkpoint.as_posix(),
                                     "destination": src.relative_to(MAIN).as_posix()})
        if row["complete"]:
            continue
        spec = src.with_name(src.name.replace(".result.json", ".spec.json"))
        data = json.loads(spec.read_text())
        copy = Path("specs/seed") / spec.name
        dump(OUT / copy, data)
        m["tasks"].append({"id": "seed/" + row["name"], "kind": "seed", "pack": "seed",
                          "spec_copy": copy.as_posix(), "specHash": json.loads(src.read_text())["specHash"],
                          "out": src.relative_to(MAIN).as_posix()})
    for row in audit["rq4"]:
        if row["state"] != "complete":
            spec = MAIN / row["spec"]
            data = json.loads(spec.read_text())
            copy = Path("specs/rq4") / row["recording"] / spec.name
            dump(OUT / copy, data)
            for t in data["targets"]:
                m["inputs"][t["npy"]] = t["nSamples"]
            from_spec = json.loads((MAIN / row["result"]).read_text())["specHash"] if row["result"] else None
            if not from_spec:
                # Same canonical hash used by chain_job.spec_hash, without importing all adapters.
                sys.path.insert(0, str(MAIN))
                from Working.discovery.chain_job import spec_hash
                from_spec = spec_hash(data)
            pack = ("mpA" if int(row["task"]) % 2 == 0 else "mpB") if row["setting"].startswith("mp_") else ("cnn" if row["kind"] == "gpu" else "cpu")
            m["tasks"].append({"id": row["recording"] + "/" + row["setting"] + "/" + str(row["task"]),
                              "kind": "rq4", "pack": pack, "task": row["task"],
                              "spec_copy": copy.as_posix(), "specHash": from_spec,
                              "out": REL + "/rq4/" + row["recording"] + "/" + Path(row["out"]).name,
                              "original_out": row["out"]})
        elif row.get("cache_complete_on_pc") and row.get("cache_entries"):
            result = MAIN / row["result"]
            cache = result.parent / "step_cache"
            files = {p.relative_to(cache).as_posix(): sha(p) for p in cache.rglob("*") if p.is_file()}
            m["backed_up_returns"].append({"result": result.relative_to(MAIN).as_posix(),
                                           "result_sha256": sha(result), "files": files})
            if len(m["backed_up_returns"]) % 50 == 0:
                print("Verified PC backups:", len(m["backed_up_returns"]), flush=True)
    dump(OUT / "manifest.json", m)
    # Original collector is retained for the final seven-recording merge after copying results back.
    for name in ("manifest.json", "worker.py"):
        src = MAIN / m["seed_root"] / name
        dst = OUT / "original_seed_collector" / name
        dst.parent.mkdir(exist_ok=True)
        shutil.copy2(src, dst)
    from recovery_launchers import write_launchers
    write_launchers(OUT, m, REL)
    shutil.copy2(THESIS / "docs/thesis/hpc/recovery_20261108/README.md", OUT / "README.md")
    archive = OUT.parent / (OUT.name + "_upload.tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for p in sorted(OUT.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.relative_to(OUT).parts[0] not in ("rq4", "logs"):
                tar.add(p, arcname=p.relative_to(MAIN).as_posix(), recursive=False)
    digest = sha(archive)
    archive.with_suffix(".gz.sha256").write_text(digest + "  " + archive.name + "\n")
    print(json.dumps({"archive": str(archive), "sha256": digest, "bytes": archive.stat().st_size,
                      "tasks": {k: sum(t["pack"] == k for t in m["tasks"]) for k in m["packs"]},
                      "fully_backed_up_caches": len(m["backed_up_returns"])}, indent=2), flush=True)


if __name__ == "__main__":
    main()
