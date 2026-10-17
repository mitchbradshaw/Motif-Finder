"""
test_measure_window_defaults_script.py
======================================
Round A_2, P3, fix round (the critic's m4): `scripts/measure_window_defaults.py --db` measures on a sandbox copy of
the database and refuses the real one by any name. It crashed instead (`from Working.config import DB_PATH`: the
name lives in `Working.database.schema`, relative to the repository), and its guard compared two spellings of a path.
The guard is now `scripts/backfill_seed_entry_ids.py`'s: the real database resolved against the main checkout, the
spellings compared once resolved, then the files themselves. A test hands the script a stand-in real database.

    PYTHONIOENCODING=utf-8 python -m pytest tests/test_measure_window_defaults_script.py -q -p no:cacheprovider
"""

import importlib.util
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402

SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "measure_window_defaults.py")
LONG_PREFIX = chr(92) * 2 + "?" + chr(92)


def _script():
    spec = importlib.util.spec_from_file_location("measure_window_defaults_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_real(tmp_path):
    real_dir = tmp_path / "main" / "DATA" / "db"
    real_dir.mkdir(parents=True)
    real = real_dir / "annotations.sqlite"
    init_db(str(real)).close()
    return real


def test_db_mode_runs_on_a_sandbox_copy(tmp_path):
    S = _script()
    sandbox = tmp_path / "runtime" / "annotations.sqlite"
    sandbox.parent.mkdir(parents=True)
    init_db(str(sandbox)).close()
    out = tmp_path / "out.json"
    assert S.main(["--db", str(sandbox), "--recording-ids", "", "--out", str(out)],
                  real=str(_fake_real(tmp_path))) == 0
    assert out.exists()


def test_db_mode_refuses_the_real_database_by_any_name(tmp_path, capsys):
    S = _script()
    real = _fake_real(tmp_path)
    (real.parent / "sub").mkdir()
    hard = tmp_path / "hard_link.sqlite"
    os.link(real, hard)
    aliases = [str(real), str(real).replace("\\", "/"), os.path.join(str(real.parent), "sub", "..", real.name),
               str(hard)]
    if os.name == "nt":
        aliases += [str(real).upper(), LONG_PREFIX + os.path.abspath(str(real))]
    before = real.read_bytes()
    for alias in aliases:
        with pytest.raises(SystemExit) as e:
            S.main(["--db", alias, "--recording-ids", "1"], real=str(real))
        assert e.value.code == 2, f"{alias!r} was not refused"
        assert "real database" in capsys.readouterr().err
    assert real.read_bytes() == before, "the stand-in real database was not touched"


def test_the_real_database_is_the_main_checkouts(tmp_path):
    """Resolved against the main checkout (a worktree's own tree holds no DATA), never against the current
    directory: `Working.database.schema.DB_PATH` is relative."""
    S = _script()
    assert os.path.isabs(S.REAL_DB)
    assert S.REAL_DB.replace("\\", "/").endswith("DATA/db/annotations.sqlite")
    assert ".claude" not in S.REAL_DB.replace("\\", "/").split("/"), "not the worktree's own tree"
