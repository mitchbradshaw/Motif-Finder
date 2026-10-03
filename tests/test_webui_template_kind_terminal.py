"""
test_webui_template_kind_terminal.py
=====================================
fixup-aa item 4: the chain footer said *"terminal Grouping — add a stage to
reach a template type"* while `templates.kind_for_steps` saved that very chain
as kind `training`. The footer now prints the kind the server will save, read
off the validate payload (`template_kind`), so the two cannot disagree; a
Grouping terminal is a training template (BLOCK_INTEGRATION §4: windowset |
grouping | model -> training) — the manual-label arm saved for `AB`.

Run from the project root:
    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_webui_template_kind_terminal.py -q
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Adapters.registry import discover_adapters  # noqa: E402

discover_adapters()

from server import chain, templates  # noqa: E402

WM = {"stage": "preprocessing", "algorithm": "window_matrix", "params": {}}
LABELS = {"stage": "catalogue", "algorithm": "manual_labels", "params": {}}
CLUSTER = {"stage": "catalogue", "algorithm": "cluster", "params": {}}
DETREND = {"stage": "preprocessing", "algorithm": "detrend", "params": {}}
MP = {"stage": "detection", "algorithm": "matrix_profile", "params": {}}
THRESH = {"stage": "detection", "algorithm": "threshold", "params": {}}


def test_a_grouping_terminal_is_a_training_template():
    for steps in ([WM, LABELS], [WM, CLUSTER]):
        v = chain.validate(steps)
        assert v["ok"], v
        assert v["terminal_kind"] == "grouping"
        assert v["template_kind"] == templates.kind_for_steps(steps) == "training"


def test_the_validate_payload_carries_the_kind_the_server_saves():
    for steps in ([DETREND, MP, THRESH], [WM]):
        assert chain.validate(steps)["template_kind"] == templates.kind_for_steps(steps)
    assert chain.validate([])["template_kind"] is None


def test_the_footer_reads_the_template_kind_not_its_own_table():
    """The client's terminal chip is worded from `template_kind`; the old table
    that named only spanset and model as template types is gone."""
    path = os.path.join(PROJECT_ROOT, "webui", "client", "src", "analyse", "rowState.ts")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert "templateKind" in src
