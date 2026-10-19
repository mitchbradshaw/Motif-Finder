"""
test_webui_night_b_fmtnum.py
============================
night-b: the per-event tables print an exact zero, and the interval table's counts, as numbers a reader reads.

Driven on the night fixture (a chain threshold -> intervals on a span with ONE event): the Inter-event intervals
table read "events 1.000 · intervals 0.00e+0". `fmtNum` sent every |v| < 0.01 to exponent form, zero included, and
printed counts with three decimals. The formatter now lives in `analyse/fmtNum.ts` (pure, no imports, run here
under Node; skips without `node`) and `EventFeatures.tsx` re-exports it, so its importers are unchanged.
"""
import io
import json
import os
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src", "analyse")
FMT_TS = os.path.join(SRC, "fmtNum.ts")


def _fmt(cases):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(FMT_TS), "webui/client/src/analyse/fmtNum.ts does not exist"
    url = "file:///" + FMT_TS.replace("\\", "/").lstrip("/")
    script = (f"import {{ fmtNum }} from {json.dumps(url)};\n"
              f"const cases = {json.dumps(cases)};\n"
              "process.stdout.write(JSON.stringify(cases.map(([v, c]) => fmtNum(v, c))));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_an_exact_zero_is_zero():
    assert _fmt([[0, ""], [0, "max_slope_mv_s"]]) == ["0", "0"]


def test_counts_are_integers():
    assert _fmt([[1, "n_events"], [0, "n_intervals"], [12, "n_events"], [1234, "n_intervals"]]) == ["1", "0", "12", "1234"]


def test_the_other_forms_are_unchanged():
    assert _fmt([[None, ""], [0.004, ""], [3.14159, ""], [42.42, ""], [5000.4, ""], [-1, "polarity"], [12.6, "onset_idx"]]) == \
        ["—", "4.00e-3", "3.142", "42.4", "5000", "drop", "13"]


def test_the_interval_table_names_its_count_columns():
    src = io.open(os.path.join(SRC, "EventFeatures.tsx"), encoding="utf-8").read()
    assert "fmtNum(s[k] as number | null, k)" in src, "the stats table passes the column so counts print as integers"
    assert "from './fmtNum'" in src
