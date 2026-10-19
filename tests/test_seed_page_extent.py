"""night (2026-10-20): the seed page's cut card did `Math.max(0, ...candidates, ...nullDistances)`. On the October
database a preview's cut sweep holds ~10^5 distances, and spreading that many values into an argument list is
`RangeError: Maximum call stack size exceeded` - the Discovery workspace's red card, seen on
`discovery.seed--fixup-ad-exclusion-zone-settable` in the night units. Min and max over data-sized lists go through
a loop (`kit/extent.ts`), and the seed page never spreads a list into Math.max / Math.min again.

Runs the TypeScript helper under Node (v22.6+ strips types natively); skips without node. Conda or venv python."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "webui", "client", "src")
EXTENT_TS = os.path.join(SRC, "kit", "extent.ts")
SEED_PAGE = os.path.join(SRC, "discovery", "SeedPage.tsx")


def _node(body: str):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(EXTENT_TS), "kit/extent.ts is missing"
    url = "file:///" + EXTENT_TS.replace("\\", "/").lstrip("/")
    script = (f"import * as M from {json.dumps(url)};\n(async () => {{ {body} }})()"
              ".then(v => console.log(JSON.stringify(v)), e => { console.error(e); process.exit(1) })")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_extent_over_three_hundred_thousand_values_is_a_loop_and_skips_non_finite():
    out = _node(
        "const xs = Array.from({length: 300000}, (_, i) => ((i * 7919) % 10007) / 10);"
        " xs[1234] = NaN; xs[99] = Infinity; xs[100] = -Infinity;"
        " return [M.extentOf(xs), M.maxOf(xs, [5000]), M.minOf([], xs), M.extentOf([]), M.maxOf([], [])]")
    assert out[0] == [0, 1000.6], out        # 7919 is coprime with the prime 10007, so every residue appears
    assert out[1] == 5000, out
    assert out[2] == 0, out
    assert out[3] == [None, None], out       # [Infinity, -Infinity] - JSON prints them as null; callers test lo <= hi
    assert out[4] is None, out               # -Infinity: Math.max(1, maxOf([])) is 1, as Math.max(1, ...[]) was


def test_the_seed_page_never_spreads_a_list_into_math_max_or_min():
    src = open(SEED_PAGE, encoding="utf-8").read()
    hits = [m.group(0) for m in re.finditer(r"Math\.(?:max|min)\([^)\n]*\.\.\.", src)]
    assert hits == [], f"spread into Math.max/min on the seed page: {hits}"
    assert "from '../kit/extent'" in src, "the seed page reads its extents through kit/extent.ts"
