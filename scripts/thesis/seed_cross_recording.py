"""Prepare the fixed drop-seed transfer experiment using the existing seed-job runner.

Run from the repository root. ``build`` writes an ignored, uploadable job bundle;
``check`` validates its input caches; ``collect`` merges completed channel jobs
and reports frozen-threshold and separately recalibrated results. Nothing submits
a job, changes the database or trains a classifier from Python.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tarfile

import numpy as np

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
DEFAULT_OUT = Path("DATA/derived/hpc/rq2_drop_transfer_20261107")
TARGETS = [
    ("M2_concat", "M2_concat_fs1", 1.0),
    ("M4", "M4_aug_concat_fs1", 1.0),
    ("LM", "LM_fs2", 2.0),
    ("CO", "CO_fs2", 2.0),
    ("MJu26a", "MJu26a_fs2", 2.0),
    ("SH", "SH_fs2", 2.0),
    ("SO", "SO_fs2", 2.0),
]


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def write_shell(path, text):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build(args):
    from functools import lru_cache
    from Working.discovery import seed_job
    from Working.hpc import job_export
    from scripts import seed_job_parallel as parallel

    # Every job imports the same runner. Discover its module closure once,
    # rather than re-parsing the repository for each of the 64 channel jobs.
    job_export.repo_module_closure = lru_cache(maxsize=4)(job_export.repo_module_closure)
    out = (ROOT / args.out).resolve()
    out_rel = rel(out)
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", out_rel):
        raise ValueError("The cluster output path must not contain spaces or shell metacharacters")
    if (out / "manifest.json").exists():
        raise FileExistsError(f"A bundle already exists at {out}; use a new --out path")
    source_path = ROOT / "HPC/Detection/generated/drop30_allch_16ch_0-2595600.spec.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    seed = np.asarray(source["exemplar"], dtype=float)
    source_fs = float(source["channels"][0]["fs"])
    assert len(seed) == 377 and source_fs == 1 and np.isfinite(seed).all()
    verified = json.loads((ROOT / "docs/thesis/data/seed_null_verified_20261107.json").read_text())
    fixed_cut = next(r["common_cut_full_precision"] for r in verified["rows"] if r["seed"] == "drop")
    out.mkdir(parents=True, exist_ok=True)
    data_root = Path(args.data_root).resolve()
    manifest = {
        "experiment": "rq2_drop_transfer_20261107", "seed_id": source["seedId"],
        "seed_spec_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "seed_samples": len(seed), "seed_fs_hz": source_fs, "seed_duration_s": 377,
        "frozen_m2_aug_cut": fixed_cut, "null_draws_per_channel": 200,
        "sampling": "Native target caches; resample the seed by target_fs/source_fs. "
                    "Distances are scaled to the original 377-sample footing by the existing bank adapter. "
                    "A factor of 2 converts sampling rate and still searches 377 seconds, not 754 seconds.",
        "m4": "Included by explicit author instruction after the original classifier exam; no retraining.",
        "datasets": [], "pack_scripts": [],
    }
    for label, stem, fs in TARGETS:
        cache = data_root / "derived/channels" / stem
        files = sorted(cache.glob("CH*.npy"), key=lambda p: int(p.stem[2:]))
        if not files:
            raise FileNotFoundError(f"No channel caches in {cache}")
        arrays = [np.load(p, mmap_mode="r") for p in files]
        sizes = {len(x) for x in arrays}
        if any(x.ndim != 1 for x in arrays) or len(sizes) != 1:
            raise ValueError(f"{stem}: channels must be one-dimensional and share a length")
        n = sizes.pop()
        channels = [{"source_file": stem + ".mat", "channel": int(p.stem[2:]),
                     "name": p.stem, "fs": fs} for p in files]
        factor = fs / source_fs
        spec = seed_job.build_spec(
            seed_id=source["seedId"], exemplar=seed, channels=channels,
            span=(0, n), k=200, max_distance=None,
            null={"method": "phase_randomize", "draws": 200, "seed": 0},
            exclusion=0.5, scales=None if factor == 1 else [factor],
            overlap="lowest", label=f"drop30 transfer: {label}", cut=fixed_cut)
        for ch in spec["channels"]:
            ch["npy"] = f"DATA/derived/channels/{stem}/CH{ch['channel']}.npy"
        base = f"rq2x_1107_drop_{label}"
        job = seed_job.write_job(spec, out_dir=str(out / label), base_name=base,
                                 slurm_time="00:20:00")
        spec_path = Path(job["spec_path"])
        parallel.split(str(spec_path))
        packs, _ = parallel.pack(str(spec_path), jobs=3)
        for pack in packs:
            p = Path(pack)
            text = p.read_text(encoding="utf-8")
            text = text.replace("PIDS=()", "export NUMBA_NUM_THREADS=1 OMP_NUM_THREADS=1 "
                                "OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1\n\nPIDS=()")
            write_shell(p, text)
        manifest["pack_scripts"].extend(rel(p) for p in packs)
        manifest["datasets"].append({
            "recording": label, "source_file": stem + ".mat", "fs_hz": fs,
            "samples_per_channel": n, "channels": len(channels),
            "recording_hours": n / fs / 3600, "seed_sampling_factor": factor,
            "match_samples": round(len(seed) * factor),
            "match_duration_s": round(len(seed) * factor) / fs,
            "spec_path": rel(spec_path), "result_path": job["result_path"],
            "input_paths": [ch["npy"] for ch in spec["channels"]],
        })
    dump(out / "manifest.json", manifest)
    shutil.copy2(Path(__file__).resolve(), out / "worker.py")
    commands = "\n".join(f"sbatch {p}" for p in manifest["pack_scripts"])
    write_shell(out / "submit_all.sh", f'''#!/bin/bash
set -euo pipefail
cd /home/Student/s4699158/CNN
mkdir -p logs
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env
python {out_rel}/worker.py check --manifest {out_rel}/manifest.json
QUEUED="$(squeue -u "$(id -un)" -h -o "%j")"
if printf '%s\\n' "$QUEUED" | grep -q '^rq2x_1107_drop_'; then
    echo 'This transfer experiment already has jobs queued or running; not submitting duplicates.'
    exit 1
fi
{commands}
''')
    write_shell(out / "collect_results.sh", f'''#!/bin/bash
set -euo pipefail
cd /home/Student/s4699158/CNN
source ~/miniconda3/etc/profile.d/conda.sh
conda activate aeon-env
python {out_rel}/worker.py collect --manifest {out_rel}/manifest.json
''')
    (out / "INPUTS.txt").write_text("\n".join(p for d in manifest["datasets"] for p in d["input_paths"]) + "\n")
    readme = ROOT / "docs/thesis/hpc/rq2_drop_transfer_20261107/README.md"
    if readme.exists():
        shutil.copy2(readme, out / "README.md")
    archive = out.parent / (out.name + "_upload.tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for p in sorted(out.rglob("*")):
            if p.is_file():
                tar.add(p, arcname=rel(p))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(digest + "  " + archive.name + "\n")
    print(json.dumps({"archive": str(archive), "sha256": digest,
                      "recordings": len(manifest["datasets"]),
                      "channels": sum(d["channels"] for d in manifest["datasets"]),
                      "pack_jobs": len(manifest["pack_scripts"]), "bytes": archive.stat().st_size}))


def check(args):
    from Working.discovery import seed_job
    from Adapters.detection_seed_matches import match_exemplar_bank  # noqa: F401

    m = json.loads(Path(args.manifest).read_text())
    problems = []
    for d in m["datasets"]:
        spec = json.loads((ROOT / d["spec_path"]).read_text())
        assert len(spec["exemplar"]) == m["seed_samples"]
        assert spec["seedId"] == m["seed_id"] and spec["cut"] == m["frozen_m2_aug_cut"]
        assert d["match_duration_s"] == m["seed_duration_s"]
        assert spec["null"]["draws"] == 200 and spec["k"] == 200
        assert seed_job.spec_hash(spec)
        for name in d["input_paths"]:
            p = Path(args.data_root) / Path(name).relative_to("DATA")
            if not p.is_file():
                problems.append("missing: " + str(p))
                continue
            x = np.load(p, mmap_mode="r")
            if x.ndim != 1 or len(x) != d["samples_per_channel"]:
                problems.append("unexpected shape: " + str(p))
        print(f"{d['recording']}: {d['channels']} channels, {d['recording_hours']:.2f} h, "
              f"{d['fs_hz']:g} Hz, {d['match_samples']} samples = {d['match_duration_s']:g} s")
    if problems:
        raise SystemExit("Input check failed before submission:\n" + "\n".join(problems))
    print("Input files and fixed-duration specifications verified; no searches have run.")


def counts(result, cut):
    if cut is None:
        return 0, None, 0
    total = 0
    null = np.zeros(int(result["null"]["draws"]), dtype=int)
    capped = 0
    for ch in result["perChannel"]:
        n = sum(c["distance"] <= cut for c in ch["candidates"])
        total += n
        capped += n == result["k"]
        ds = np.asarray(ch["null"]["distances"]).reshape(len(null), result["k"])
        null += (ds <= cut).sum(axis=1)
    return total, float(null.mean()), int(capped)


def collect(args):
    from scripts.seed_job_parallel import merge
    from Working.discovery.seed_job import spec_hash
    from Working.discovery.seeded_search import recommended_cut_corrected

    path = Path(args.manifest).resolve()
    manifest = json.loads(path.read_text())
    results = []
    for d in manifest["datasets"]:
        spec = json.loads((ROOT / d["spec_path"]).read_text())
        out = ROOT / d["result_path"]
        if not out.exists() or not json.loads(out.read_text()).get("complete"):
            merge(str(ROOT / d["spec_path"]))  # refuses missing, partial or mismatched channel results
        result = json.loads(out.read_text())
        if result.get("specHash") != spec_hash(spec):
            raise ValueError(f"{out} belongs to a different search specification")
        if len(result["perChannel"]) != d["channels"]:
            raise ValueError(f"{out} does not contain every expected channel")
        results.append((d, result))
    summary, matches = [], []
    for d, result in results:
        rc = recommended_cut_corrected(
            [{"distances": [c["distance"] for c in ch["candidates"]], "null": ch["null"]}
             for ch in result["perChannel"]], alpha=0.01, correction="none")
        for protocol, cut in [("frozen_M2_aug_cut", manifest["frozen_m2_aug_cut"]),
                              ("recalibrated_target_cut", rc["cut"])]:
            real, null, capped = counts(result, cut)
            summary.append({"recording": d["recording"], "protocol": protocol,
                            "distance_cut": cut, "real_matches": real,
                            "surrogate_mean_per_draw_all_channels": null,
                            "channels_reaching_200": capped, "channels": d["channels"],
                            "recording_hours": d["recording_hours"],
                            "matches_per_channel_hour": real / d["channels"] / d["recording_hours"],
                            "human_reviewed": False})
        for ch in result["perChannel"]:
            for c in ch["candidates"]:
                length = c.get("length", manifest["seed_samples"])
                if not np.isclose(length / ch["fs"], manifest["seed_duration_s"]):
                    raise ValueError(f"{d['recording']} has a match with an unexpected physical duration")
                matches.append({"recording": d["recording"], "source_file": ch["source_file"],
                                "channel_index": ch["channel"], "start_sample": c["index"],
                                "start_s": c["index"] / ch["fs"], "duration_s": length / ch["fs"],
                                "shape_distance_original_seed_footing": c["distance"],
                                "passes_frozen_cut": c["distance"] <= manifest["frozen_m2_aug_cut"],
                                "passes_recalibrated_cut": rc["cut"] is not None and c["distance"] <= rc["cut"]})
    outputs = []
    for name, rows in [("summary.csv", summary), ("matches.csv", matches)]:
        out = path.parent / name
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        outputs.append(out)
    dump(path.parent / "summary.json", {"seed_id": manifest["seed_id"], "results": summary,
         "interpretation": "Frozen-cut transfer and target-recalibrated retrieval are distinct analyses. "
                           "These are unreviewed matches, not acceptance rates. Counts reaching the cap may be truncated."})
    archive = path.parent / "return_results.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for p in [path, path.parent / "summary.json", *outputs,
                  *(ROOT / d["result_path"] for d in manifest["datasets"])]:
            tar.add(p, arcname=rel(p))
    print(f"Wrote {archive}; bring this archive back to the PC. No database was changed.")


def main():
    if not (ROOT / "Working/discovery/seed_job.py").exists():
        raise SystemExit("Run from the CNN repository root")
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--data-root", default=str(ROOT / "DATA"))
    b.add_argument("--out", default=str(DEFAULT_OUT))
    c = sub.add_parser("check")
    c.add_argument("--manifest", required=True)
    c.add_argument("--data-root", default=str(ROOT / "DATA"))
    r = sub.add_parser("collect")
    r.add_argument("--manifest", required=True)
    args = ap.parse_args()
    {"build": build, "check": check, "collect": collect}[args.command](args)


if __name__ == "__main__":
    main()
