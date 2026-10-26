"""
scommune_bundle.py — PREPARE (never submit) the rangpur SLURM bundle that sweeps Adamatzky's *Schizophyllum commune*
recording (`Schizophyllum commune.txt`, recordings 600-606: 7 channels, 1 Hz, mV, 263,687 samples = 73.2 h) with the
same 43 detector settings every UQ recording got in the RQ4b sweep, each with its paired one-draw phase-randomised
surrogate (the second unseen-recording test, approved by the researcher 2026-10-26).

It is batch 3's build (`scripts/rq4_overnight.py build-batch`, the mV variant set: the three `threshold_mV` copies of
`signal_threshold` instead of the base template and its V copies, `--units <source>=mV`), run on a SANDBOX copy of
the database in the session scratchpad (`webui.server.runtime.Runtime(mode="sandbox")`: the step cache, the
adapters' RESULTS_DIRs, the classifier MODEL_ROOT and the cost calibrations are all redirected there), exactly as
`scripts/thesis/surrogates20_bundle.py` builds its bundle. Nothing is written to DATA/ or the real database; the
bundle (specs, pack scripts, task lists: a few hundred KB, no data arrays) goes to docs/thesis/hpc/rq4_scommune_<date>/.
The 7 channel arrays it reads (2.1 MB each) are NOT copied into it: they are already under DATA/derived/channels/ and
go to the cluster at the same relative paths (the bundle's README says how).

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/scommune_bundle.py [--date 20261026] [--keep-sandbox]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
SCRATCH = os.environ.get(
    "SCOMMUNE_SANDBOX",
    r"C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\ee7dfe78-0c27-48d6-91e6-dd2ef2948732"
    r"\scratchpad\scommune_sandbox")
SOURCE = "Schizophyllum commune.txt"
UNIT = "mV"
PREFIX = "rq4s"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default="20261026")
    ap.add_argument("--keep-sandbox", action="store_true", help="leave the sandbox copy of the database in place")
    a = ap.parse_args(argv)
    out_rel = os.path.join("docs", "thesis", "hpc", f"rq4_scommune_{a.date}")

    from webui.server.runtime import Runtime
    rt = Runtime(mode="sandbox", runtime_root=SCRATCH).setup()
    print("sandbox database:", rt.db_path)
    try:
        spec = importlib.util.spec_from_file_location("rq4o", os.path.join(ROOT, "scripts", "rq4_overnight.py"))
        R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(R)
        batch = R.build_batch(rt.db_path, [SOURCE], out_rel=out_rel, prefix=PREFIX, units={SOURCE: UNIT})
    finally:
        rt.restore()
        if not a.keep_sandbox:
            shutil.rmtree(rt.dir, ignore_errors=True)
    d = batch["datasets"][0]
    print(f"{d['source']}: {d['jobs']} chain jobs, {d['tasks']} tasks, unit {d['unit']}, matrix profile on "
          f"{d['mpChannels'] or 'no channels'}" + (f" ({d['mpLeftOut']})" if d["mpLeftOut"] else ""))
    for x in d.get("leftOut") or []:
        print(f"    left out: {x['label']}: {x['reason']}")
    for r in d["refused"]:
        print(f"    refused: {r['label']}: {str(r['reason'])[:200]}")
    for p in batch["packs"]:
        print(f"    {p['name']}: {p['tasks']} tasks, {p['parallel']} at a time, about "
              f"{p['estimateCoreS'] / 3600:.2f} core-hours (balancing estimate)")
    with open(os.path.join(ROOT, d["folder"], "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    print(f"    labels: {sorted(j['label'] for j in man['jobs'])}")
    print(f"    inputs the cluster needs: {sorted(set(batch['inputs']))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
