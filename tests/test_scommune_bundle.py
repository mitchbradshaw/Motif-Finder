"""
test_scommune_bundle.py
=======================
The second unseen-recording test (2026-10-26): the rangpur sweep bundle for Adamatzky's *Schizophyllum commune*
(`docs/thesis/hpc/rq4_scommune_<date>/`, built by `scripts/thesis/scommune_bundle.py`).

Pinned:

* a recording whose source file has a space in its name ("Schizophyllum commune.txt") gets a batch sub-folder with
  no space: the pack scripts read their task lines with ``read -r SPEC OUT TASK LABEL`` and `pending` splits on
  whitespace, so a space in a path would shift every field;
* every task line of the bundle has exactly four fields and names a spec that is there;
* the bundle is the batch-3 sweep for a millivolt recording: the same 43 settings as L_LM_Jul_26_J_raw_fs2 (mV, batch
  3), each with one phase-randomised draw (seed 0), on all 7 channels, the units declared mV in every target.

Run from the project root:
    python -m pytest tests/test_scommune_bundle.py -q
"""

import glob
import importlib.util
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BUNDLES = sorted(glob.glob(os.path.join(PROJECT_ROOT, "docs", "thesis", "hpc", "rq4_scommune_*")))
BATCH3_MV = os.path.join(PROJECT_ROOT, "HPC", "Detection", "generated", "rq4_batch3", "L_LM_Jul_26_J_raw_fs2",
                         "manifest.json")


def _rq4():
    spec = importlib.util.spec_from_file_location("rq4_overnight_t", os.path.join(PROJECT_ROOT, "scripts",
                                                                                  "rq4_overnight.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_source_file_with_a_space_gets_a_folder_without_one():
    R = _rq4()
    assert R._folder_stem("Schizophyllum commune.txt") == "Schizophyllum_commune"
    assert R._folder_stem("LM_fs2.mat") == "LM_fs2"                       # the earlier batches' folders unchanged
    assert R._folder_stem("M4_aug_concat_fs1.mat") == "M4_aug_concat_fs1"


@pytest.mark.skipif(not BUNDLES, reason="the S. commune bundle has not been built")
def test_every_task_line_has_four_fields_and_a_spec():
    root = BUNDLES[-1]
    files = glob.glob(os.path.join(root, "tasks_*.txt"))
    assert len(files) == 4
    n = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                assert len(parts) == 4, line
                assert os.path.isfile(os.path.join(PROJECT_ROOT, parts[0])), parts[0]
                n += 1
    assert n == 296                                       # 42 settings x 7 channels + the matrix profile on 2


@pytest.mark.skipif(not BUNDLES, reason="the S. commune bundle has not been built")
def test_the_bundle_is_batch_3s_millivolt_sweep():
    root = BUNDLES[-1]
    with open(os.path.join(root, "batch.json"), encoding="utf-8") as fh:
        batch = json.load(fh)
    (d,) = batch["datasets"]
    assert d["source"] == "Schizophyllum commune.txt" and " " not in d["folder"]
    with open(os.path.join(PROJECT_ROOT, d["folder"], "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    assert man["unit"] == "mV" and man["volts"] is False and man["samples"] == 263_687
    labels = {j["label"] for j in man["jobs"]}
    assert len(labels) == 43 and not man["refused"]
    assert "signal_threshold" not in labels and "signal_threshold__threshold_mV_m2" in labels
    if os.path.isfile(BATCH3_MV):
        with open(BATCH3_MV, encoding="utf-8") as fh:
            assert labels == {j["label"] for j in json.load(fh)["jobs"]}
    for j in man["jobs"]:
        with open(os.path.join(PROJECT_ROOT, j["spec"]), encoding="utf-8") as fh:
            spec = json.load(fh)
        assert spec["null"]["draws"] == 1 and spec["null"]["params"] == {"method": "phase_randomize", "seed": 0}
        assert all(t["units"] == "mV" for t in spec["targets"])
        assert len(spec["targets"]) == (2 if j["label"] == "mp_threshold__backend_auto" else 7)
