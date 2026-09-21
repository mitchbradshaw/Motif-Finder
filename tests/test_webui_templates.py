"""
test_webui_templates.py
=========================
Templates as first-class rows (stage-3 prompt 01 "Templates"): the
`templates` table gains `kind`, `version`, `builtin`, `description`,
`created_at`, `updated_at` (additive, through `init_db()`); the canonical
templates ship as code in `webui/server/templates.py` and are seeded into
the table once; a saved copy is an editable row.

No FastAPI needed — `server.templates` is plain sqlite + the core, so this
runs under the conda pytest too.

Runnable standalone:  python tests/test_webui_templates.py
"""

import os
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402
from Working.chain_validation import validate_recipe_steps  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from server import templates as T  # noqa: E402

discover_adapters()
KINDS = {"detection", "encoding", "training", "interrogation"}


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    conn = init_db(path)
    try:
        yield conn
    finally:
        conn.close()
        os.remove(path)


def test_templates_table_has_the_new_columns(db):
    cols = {r[1] for r in db.execute("PRAGMA table_info(templates)")}
    assert {"id", "name", "steps_json", "kind", "version", "builtin", "description", "created_at", "updated_at"} <= cols


def test_every_canonical_template_is_typed_and_validates():
    names = [t["name"] for t in T.CANONICAL]
    assert len(names) == len(set(names))
    for tpl in T.CANONICAL:
        assert tpl["kind"] in KINDS, tpl["name"]
        assert isinstance(tpl["version"], int) and tpl["version"] >= 1
        assert tpl["description"]
        for s in tpl["steps"]:
            get_adapter(f"{s['stage']}.{s['algorithm']}")   # KeyError = a canonical template names a block that does not exist
        ok, reason = validate_recipe_steps(tpl["steps"])
        assert ok, f"{tpl['name']}: {reason}"


def test_the_prompts_named_templates_exist():
    names = {t["name"] for t in T.CANONICAL}
    assert {"drop_detection_v1", "dehshibi_spikes", "mp_threshold", "windows_model"} <= names


def test_seed_is_idempotent_and_marks_rows_builtin(db):
    first = T.seed_canonical(db)
    second = T.seed_canonical(db)
    assert first == len(T.CANONICAL) and second == 0
    rows = T.list_all(db)
    builtin = [r for r in rows if r["builtin"]]
    assert {r["name"] for r in builtin} == {t["name"] for t in T.CANONICAL}
    assert all(r["kind"] in KINDS for r in builtin)


def test_saving_a_copy_is_an_editable_non_builtin_row(db):
    T.seed_canonical(db)
    src = T.canonical("mp_threshold")
    tid = T.save(db, "my_mp", src["steps"], kind=src["kind"], description="a copy")
    row = T.get(db, tid)
    assert row["builtin"] is False and row["kind"] == "detection" and row["version"] == 1
    T.update(db, tid, steps=src["steps"][:2], description="trimmed")
    row = T.get(db, tid)
    assert len(row["steps"]) == 2 and row["version"] == 2 and row["description"] == "trimmed"


def test_kind_is_derived_from_the_terminal_type_when_not_given():
    assert T.kind_for_steps(T.canonical("mp_threshold")["steps"]) == "detection"
    assert T.kind_for_steps(T.canonical("windows_model")["steps"]) == "training"
    assert T.kind_for_steps([{"stage": "detection", "algorithm": "sax_dsax", "params": {}}]) == "encoding"


def test_a_builtin_row_cannot_be_edited_in_place(db):
    T.seed_canonical(db)
    row = next(r for r in T.list_all(db) if r["builtin"])
    with pytest.raises(PermissionError):
        T.update(db, row["id"], steps=row["steps"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
