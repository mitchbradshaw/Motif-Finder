"""
test_webui_night_b_critic.py
============================
night-b, the critic's round on the night branch:

1. Signal's ‹ N / M › list re-reads the channel's spans after a write (`spansRev`). Sharing that re-read with a
   whole-channel read still in flight could hand back a read that started BEFORE the write, so the latest edit was
   missing until the next one. Only the FIRST load shares; a re-read is its own `getSpans`.
2. Interrogation's "No family X" card flashed on every valid family switch (the new id is in the URL while the old
   block is still on screen), and its button cleared `?family` — back to the default, which may itself be missing.
   It shows only once the read has settled, and the button names the family that IS shown.
3. `?template=<name>`: names are not unique and the list is sorted builtin-first, so the first loose match could be
   "foo · v1" for `foo`, and an all-digit name was read as an id. `analyse/pickTemplate.ts` (pure, run under Node):
   exact full name first, then short name; several → the newest id, said so; digits → an id only when no name has
   them.
"""
import io
import json
import os
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
PICK_TS = os.path.join(SRC, "analyse", "pickTemplate.ts")


def _src(*parts):
    return io.open(os.path.join(SRC, *parts), encoding="utf-8").read()


def test_a_reread_after_a_write_is_its_own_read():
    src = _src("explore", "SignalPage.tsx")
    assert "spansRev === 0 ? getWholeChannelSpans(ch.id, ch.duration_s) : getSpans(ch.id, 0, ch.duration_s)" in src


def test_the_unknown_family_card_waits_for_the_read_and_opens_what_is_shown():
    src = _src("interrogation", "SourcePage.tsx")
    assert "block.data && !block.loading && familyId !== block.data.family.id" in src
    assert "setQuery({ family: block.data.family.id })" in src


def _pick(templates, q):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(PICK_TS), "webui/client/src/analyse/pickTemplate.ts does not exist"
    url = "file:///" + PICK_TS.replace("\\", "/").lstrip("/")
    script = (f"import {{ pickTemplate }} from {json.dumps(url)};\n"
              f"const r = pickTemplate({json.dumps(templates)}, {json.dumps(q)});\n"
              "process.stdout.write(JSON.stringify({ id: r.template ? r.template.id : null, note: r.note }));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# the list as the bridge sorts it: builtin DESC, then id
LIST = [{"id": 1, "name": "foo · v1", "builtin": 1}, {"id": 2, "name": "bar", "builtin": 1},
        {"id": 5, "name": "foo", "builtin": 0}, {"id": 7, "name": "bar", "builtin": 0},
        {"id": 9, "name": "42", "builtin": 0}]


def test_an_exact_name_wins_over_a_short_name():
    assert _pick(LIST, "foo") == {"id": 5, "note": None}


def test_a_short_name_is_the_fallback():
    assert _pick([LIST[0]], "foo")["id"] == 1


def test_a_name_held_twice_opens_the_newest_and_says_so():
    got = _pick(LIST, "bar")
    assert got["id"] == 7 and got["note"] and "2" in got["note"]


def test_digits_are_a_name_first_then_an_id():
    assert _pick(LIST, "42")["id"] == 9
    assert _pick(LIST, "7")["id"] == 7


def test_nothing_matches():
    assert _pick(LIST, "nope") == {"id": None, "note": None}


def test_the_chain_page_resolves_through_it():
    src = _src("analyse", "ChainPage.tsx")
    assert "pickTemplate(await getTemplates(), qp.template)" in src
    assert ".find(x => x.name === qp.template || shortName(x) === qp.template)" not in src
