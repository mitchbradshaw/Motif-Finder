"""Package operational fixes only, with hash acknowledgements of intact PC returns."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[2]
MAIN=Path("C:/Users/mmebr/Documents/CNN")
BASE=MAIN/"DATA/derived/hpc/recovery_20261108"
OUT=MAIN/"DATA/derived/hpc/recovery_20261108_cnn_resume"


def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(4*1024**2),b""):h.update(b)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    audit=json.loads((ROOT/"docs/thesis/data/recovery_return_20261108/audit.json").read_text())
    returns=[]
    for row in audit["recovery_tasks"]:
        if row["state"]!="complete" or not row["cache_ok"]:continue
        p=MAIN/row["result"];cache=p.parent/"step_cache"
        if not cache.is_dir():continue
        files={f.relative_to(cache).as_posix():sha(f) for f in sorted(cache.rglob("*")) if f.is_file()}
        returns.append({"result":p.relative_to(MAIN).as_posix(),"result_sha256":sha(p),"files":files})
    (OUT/"pc_verified_returns.json").write_text(json.dumps({"returns":returns},indent=2))
    shutil.copy2(Path(__file__).with_name("recovery_cnn_longwall.py"),OUT/"cnn_longwall.py")
    shell=(BASE/"cnn.sh").read_text()
    for old,new in [("#SBATCH --time=00:20:00","#SBATCH --time=05:00:00"),
                    ("--job-name=rec1108_cnn","--job-name=rec1108_cnnL"),
                    ("worker.py pack --pack cnn","cnn_longwall.py pack"),
                    ("/cnn.sh ","/cnn_longwall.sh ")]:
        assert old in shell,old
        shell=shell.replace(old,new)
    (OUT/"cnn_longwall.sh").write_text(shell,encoding="utf-8",newline="\n")
    readme="""# CNN recovery follow-up, 8 November

The 102 completed recovery tasks were verified on the PC. Three one-minute
fusion tasks stopped after two attempts without a completed step. CNN inference
is cancellable between batches but does not save a resumable within-step score
checkpoint, so the earlier statement that completed windows were checkpointed
was incorrect. Repeating the same short wall would restart that step.

Copy the THREE files cnn_longwall.py, cnn_longwall.sh and pc_verified_returns.json
from this PC folder into the EXISTING Rangpur folder:
/home/Student/s4699158/CNN/DATA/derived/hpc/recovery_20261108/

The new launcher requests the established five-hour A100 allocation and runs
one CNN task at a time, retaining the original worker, runtime, scientific
specifications, inputs, CNN hashes, outputs and completed step caches. It has
a three-hour pack budget (10,800 seconds), 9,900-second task budget and 40-minute minimum launch
margin. The unchanged stall guard still stops a genuinely unproductive chain.
The five-hour scheduler allocation is retained as additional margin; the pack
itself stops launching work within the three-hour budget requested by the author.

On Rangpur, after checking no old rec1108_cnn jobs are active:

    cd /home/Student/s4699158/CNN
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate torch_env
    python DATA/derived/hpc/recovery_20261108/cnn_longwall.py retry-stalled
    python DATA/derived/hpc/recovery_20261108/cnn_longwall.py retry-stalled --apply
    sbatch --test-only DATA/derived/hpc/recovery_20261108/cnn_longwall.sh
    sbatch DATA/derived/hpc/recovery_20261108/cnn_longwall.sh

The retry command archives only the three confirmed stall-state JSON files;
it does not erase any result or cached computation. Subsequent jobs chain
automatically and skip complete tasks. No seed, CPU or matrix-profile rerun
is needed based on the returned logs.

The existing 8-GiB output guard still applies. To free only caches already
copied intact to this PC, these OPTIONAL operations compare the result hash,
the exact cache file set, and every file's SHA-256 before deleting that cache:

    python DATA/derived/hpc/recovery_20261108/cnn_longwall.py release-verified
    python DATA/derived/hpc/recovery_20261108/cnn_longwall.py release-verified --apply

Changed, missing or unrecognised files are skipped. Results, work/scratch,
specifications, models and incomplete tasks are retained. PC copies remain.

WinSCP folders to bring back after completion:

* New CNN returns and their caches:
  /home/Student/s4699158/CNN/DATA/derived/hpc/recovery_20261108/rq4/
* Task diagnostics:
  /home/Student/s4699158/CNN/DATA/derived/hpc/recovery_20261108/logs/
* Slurm output/error files:
  /home/Student/s4699158/CNN/logs/rec1108_cnnL_*.out and *.err

Use the matching PC project folders. No collection command is needed.
The five seed checkpoints were subsequently copied and verified: all 64
channels now have 200 complete draws. No seed work or further seed transfer
remains. The acknowledgement covers 98 actual cache directories among the
102 complete returns; four windowed results have no returned step_cache.
"""
    (OUT/"README.md").write_text(readme,encoding="utf-8")
    archive=OUT.with_suffix(".tar.gz")
    with tarfile.open(archive,"w:gz") as tar:
        for name in ("cnn_longwall.py","cnn_longwall.sh","pc_verified_returns.json"):
            tar.add(OUT/name,arcname="DATA/derived/hpc/recovery_20261108/"+name,recursive=False)
    print(json.dumps({"folder":str(OUT),"archive":str(archive),"acknowledged_returns":len(returns),"sha256":sha(archive)}),flush=True)


if __name__=="__main__":main()
