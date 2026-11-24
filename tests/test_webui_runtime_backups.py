"""
test_webui_runtime_backups.py
=============================
Project mode writes ``DATA/db/backups/<stamp>.sqlite`` on every start and keeps the newest ten of ITS OWN backups.
Other tools leave their pre-write backups in the same folder under names of their own
(``before_autodetect_queue_20261124_090532.sqlite``, ``pre-scommune-import-20261029.sqlite``); those are never the
bridge's to prune. 2026-11-24: the prune counted every ``*.sqlite`` there, so a start would have deleted its own fresh
backup and the two backups taken just before a review queue was written (they sort first by name).
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from server.runtime import _prune_backups  # noqa: E402


def _touch(d, name):
    with open(os.path.join(d, name), "wb") as fh:
        fh.write(b"x")


def test_only_the_bridges_own_stamped_backups_are_pruned(tmp_path):
    d = str(tmp_path)
    stamped = [f"202611{day:02d}-0930{sec:02d}.sqlite" for day, sec in zip(range(1, 13), range(12))]
    named = ["before_autodetect_queue_20261124_090532.sqlite", "before_autodetect_queue_20261124_091217.sqlite",
             "pre-scommune-import-20261029.sqlite", "20260922-023052-pre-library.sqlite",
             "annotations.sqlite.pre-datasets-derive-20261019-211013"]
    for n in stamped + named + ["20261026-082841.sqlite-shm", "20261026-082841.sqlite-wal"]:
        _touch(d, n)
    pruned = _prune_backups(d, keep=10)
    assert sorted(pruned) == sorted(stamped[:2])                       # the two oldest of the bridge's own
    left = set(os.listdir(d))
    assert set(stamped[2:]) <= left and set(named) <= left              # nothing of anyone else's is touched
    assert {"20261026-082841.sqlite-shm", "20261026-082841.sqlite-wal"} <= left


def test_nothing_is_pruned_while_the_bridge_has_ten_or_fewer(tmp_path):
    d = str(tmp_path)
    for n in ["20261124-093000.sqlite", "before_x_20200101.sqlite", "0-early.sqlite"]:
        _touch(d, n)
    assert _prune_backups(d, keep=10) == []
    assert len(os.listdir(d)) == 3
