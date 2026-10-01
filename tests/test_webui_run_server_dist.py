"""
test_webui_run_server_dist.py
=============================
`run_server.py --dist` — serve a private client build.

`Runtime(client_dist=...)` has always existed (`server/runtime.py`) and
`run_server.py` never exposed it, so every bridge on this machine served the
one shared `webui/client/dist`. Two agents working the same checkout then
overwrite each other's bundle: in the 2026-09-30 wave, prompt `E` rebuilt the
shared dist three times with prompt `G`'s uncommitted sources compiled into
it, and `G` — which was serving that dist as its pre-change baseline for
before/after evidence — had to rebuild the old client in a scratch directory
behind a temporary `node_modules` junction to get its measurements back.

Two traps these tests pin, both of which would make the flag worse than
useless:

* **the chdir.** `Runtime.setup()` chdirs to the repo root, so a relative
  `--dist` resolved after construction points somewhere else entirely. It
  must be made absolute against the invocation's cwd, before `Runtime`;
* **the silent fallback.** `app.py` serves a JSON note instead of the client
  when `client_dist` is not a directory. A typo'd `--dist` would therefore
  start a bridge that looks alive and serves no app. `CLAUDE.md`: loud
  failure is structural here. It is refused the way a busy port is.

No FastAPI import: `run_server` pulls in `uvicorn` and `server.app` inside
`main()`, so the parser and the path resolution are reachable from the conda
suite.
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_server  # noqa: E402
from server.runtime import Runtime  # noqa: E402


def test_the_parser_takes_a_dist_and_defaults_it_to_none():
    """No --dist is today's behaviour: Runtime picks webui/client/dist itself."""
    ap = run_server.build_parser()
    assert ap.parse_args([]).dist is None
    assert ap.parse_args(["--dist", "somewhere"]).dist == "somewhere"


def test_the_default_dist_is_still_the_shared_build():
    assert Runtime(client_dist=run_server.resolve_dist(None)).client_dist \
        == os.path.join(WEBUI_DIR, "client", "dist")


def test_a_relative_dist_is_resolved_before_the_runtime_chdirs(tmp_path, monkeypatch):
    """Runtime.setup() chdirs to the repo root. A relative --dist resolved
    after that silently means a different directory — and on this repo the
    repo root is where `webui/` lives, so `client/dist` would even exist."""
    elsewhere = tmp_path / "work"
    (elsewhere / "dist-g").mkdir(parents=True)
    monkeypatch.chdir(elsewhere)

    resolved = run_server.resolve_dist("dist-g")

    assert os.path.isabs(resolved)
    assert os.path.realpath(resolved) == os.path.realpath(elsewhere / "dist-g")
    # and it survives the chdir Runtime.setup() performs
    monkeypatch.chdir(PROJECT_ROOT)
    assert os.path.isdir(resolved)


def test_a_dist_that_is_not_there_is_refused_loudly(tmp_path):
    """Not a JSON note on a bridge that looks alive — a refusal, like a busy port."""
    missing = tmp_path / "never-built"
    with pytest.raises(SystemExit) as e:
        run_server.resolve_dist(str(missing))
    assert "never-built" in str(e.value)


def test_a_dist_that_is_a_file_is_refused_too(tmp_path):
    f = tmp_path / "dist"
    f.write_text("not a directory", encoding="utf-8")
    with pytest.raises(SystemExit):
        run_server.resolve_dist(str(f))


def test_the_dist_reaches_the_runtime_and_its_description(tmp_path):
    """What app.py mounts and /api/runtime reports is the one the flag named."""
    d = tmp_path / "dist-f"
    d.mkdir()
    rt = Runtime(mode="sandbox", client_dist=run_server.resolve_dist(str(d)))
    assert os.path.realpath(rt.client_dist) == os.path.realpath(d)
    assert rt.describe()["client_dist"] == rt.client_dist


def test_a_private_dist_is_announced_in_the_banner(tmp_path):
    """Serving someone else's bundle is exactly the mistake this flag exists to
    prevent, so the bridge must say which one it is serving — the banner is the
    one line that always reaches the terminal."""
    d = tmp_path / "dist-j"
    d.mkdir()
    private = Runtime(mode="sandbox", client_dist=str(d))
    assert str(d) in private.banner()

    # the shared build is the default and says nothing extra — the banner stays
    # the two lines it has always been unless a private dist is in play.
    assert "client" not in Runtime(mode="sandbox").banner().lower()
