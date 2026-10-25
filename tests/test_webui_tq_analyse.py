"""
test_webui_tq_analyse.py
========================
tq-analyse (2026-10-25, the code-quality wave): the Analyse figures' duplicated helpers and state, one of each.

  * one number format: `fmtN` lives in the pure `analyse/fmtNum.ts` (run here under Node) and `fmtNum` is its column
    rules in front of it; `views/common.tsx` no longer writes its own copy;
  * one template short name: `shortName` lives in the pure `analyse/pickTemplate.ts`; `TemplatesPopover.tsx` imports it;
  * one extent rule: `views/common.tsx::finiteRange` and `kit/plots.tsx::extent` are `charts/domain.ts::extentOf`
    (kit's `[-1, 1]` empty answer kept at its call); EventShapeFigures' overlay measures with it too;
  * one "marked event" and one "legend show / hide" state, `useMarkedEvent` / `useSeriesToggle` in MultiScatter.tsx,
    used by both the Event shape and the Intervals figures;
  * the motif overlay colours by the time order `useMotifs` already built and draws with `polylinePath`;
  * the Explore overlay: one gain row per channel (no optional read), and `fitCentre` has no dead "cannot fit" branch.

Behaviour is pinned by the tests that already cover these files; this file pins the seams.
"""
import io
import json
import os
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")


def _read(*parts):
    return io.open(os.path.join(SRC, *parts), encoding="utf-8").read()


def _node(ts_parts, expr):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    path = os.path.join(SRC, *ts_parts)
    url = "file:///" + path.replace("\\", "/").lstrip("/")
    script = f"import * as M from {json.dumps(url)};\nconst out = ({expr});\nprocess.stdout.write(JSON.stringify(out));"
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_fmtN_is_the_pure_formatter_and_fmtNum_calls_it():
    out = _node(("analyse", "fmtNum.ts"),
                "[0, -0, 0.004, 3.14159, 42.42, 5000.4, -12.25, NaN, Infinity].map(v => M.fmtN(v))")
    assert out == ["0", "0", "4.00e-3", "3.142", "42.4", "5000", "-12.3", "—", "—"]
    src = _read("analyse", "fmtNum.ts")
    assert "return fmtN(v)" in src, "fmtNum does not hand its numeric branch to fmtN"
    common = _read("analyse", "views", "common.tsx")
    assert "export const fmtN =" not in common, "views/common.tsx still writes its own fmtN"


def test_shortName_is_pure_and_imported_by_the_popover():
    out = _node(("analyse", "pickTemplate.ts"), "[M.shortName({ name: 'foo · v1 ' }), M.shortName({ name: ' bar ' })]")
    assert out == ["foo", "bar"]
    pop = _read("analyse", "TemplatesPopover.tsx")
    assert "export const shortName =" not in pop, "TemplatesPopover.tsx still writes its own shortName"


def test_one_extent_rule():
    common = _read("analyse", "views", "common.tsx")
    assert "export function finiteRange" not in common, "views/common.tsx still scans its own extent"
    plots = _read("kit", "plots.tsx")
    assert "extentOf(" in plots and "let lo = Infinity" not in plots[plots.index("function extent("):][:300], \
        "kit/plots.tsx's extent() still scans by hand"
    figs = _read("analyse", "views", "EventShapeFigures.tsx")
    assert "zlo = Infinity" not in figs, "the motif overlay still scans its own extent"


def test_one_marked_event_and_one_series_toggle():
    ms = _read("analyse", "views", "MultiScatter.tsx")
    assert "export function useMarkedEvent" in ms and "export function useSeriesToggle" in ms
    for name in ("EventShapeFigures.tsx", "IntervalFigures.tsx"):
        src = _read("analyse", "views", name)
        assert "useMarkedEvent()" in src and "useSeriesToggle(" in src, f"{name} does not use the shared state"
        assert "useState<number | null>(null)" not in src, f"{name} still keeps its own hover / picked state"


def test_motif_overlay_reuses_the_order_and_the_path():
    figs = _read("analyse", "views", "EventShapeFigures.tsx")
    assert figs.count(".sort(") == 1, "the motif overlay sorts the events by time twice"
    assert "polylinePath(" in figs, "the motif overlay writes its own polyline"


def test_overlay_gain_rows_and_fit_centre():
    ov = _read("explore", "Overlay.tsx")
    assert "g.gains[i]?." not in ov, "one gain row per channel is read as optional"
    model = _read("explore", "overlayModel.ts")
    assert "cannot fit" not in model[model.index("export function fitCentre"):][:400], "fitCentre keeps its dead branch"
    assert model.count("Math.min(gainLanes * lane, 0.9 * blockPx)") == 1, "the gain target is computed twice"
    # a lane exactly as tall as the block lands where the deleted branch put it (its top at the block's top)
    assert _node(("explore", "overlayModel.ts"), "[M.fitCentre(10, 1, 3, 100, 400), M.fitCentre(390, 3, 1, 100, 400)]") == [100, 300]
