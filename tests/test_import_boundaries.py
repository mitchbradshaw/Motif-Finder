"""
test_import_boundaries.py
=========================
Rule 1 of CLAUDE.md, enforced by walking import statements rather than trusted:

* the core imports no UI library — nothing in the repository imports the
  Panel family (`panel`, `holoviews`, `bokeh`) anywhere, at module scope or
  inside a function, since the Panel tree was retired (tag `archive/panel-ui`,
  2026-09-21);
* nothing imports the retired `UI` package — not the core, not the tests, not
  `webui/`.

`matplotlib` is deliberately NOT in the banned set: eleven adapters and about
twenty-five core modules use it for figure export, and it needs no display.

This file descends from `tests/test_ui_packages.py`'s
`test_nothing_in_working_or_adapters_imports_from_ui`, the one test of that
file that outlived the tree it described.
"""

import ast
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

PANEL_FAMILY = ("panel", "holoviews", "bokeh")

# Directories that are not this project's Python: installs, build output,
# gitignored data and run evidence, editor and agent state.
_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".vite",
    "DATA", "MODELS", "MATRICES", "Plots", "runs", "runtime", ".claude", ".vscode",
    "Reference",  # vendored third-party implementations, not ours
}


def _python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _imported_module_names(path):
    """Every dotted module name this file imports, module-scope or nested."""
    with open(path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=path)
        except SyntaxError:
            return set()  # a scratch script that does not parse cannot import anything
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def _offenders(predicate):
    found = {}
    for path in _python_files(PROJECT_ROOT):
        hits = sorted(n for n in _imported_module_names(path) if predicate(n))
        if hits:
            found[os.path.relpath(path, PROJECT_ROOT).replace(os.sep, "/")] = hits
    return found


def test_the_walk_actually_covers_the_trees_the_rule_protects():
    """A boundary test that silently walks nothing proves nothing."""
    seen = {os.path.relpath(p, PROJECT_ROOT).split(os.sep)[0] for p in _python_files(PROJECT_ROOT)}
    for required in ("Working", "Adapters", "Pipelines", "webui", "tests"):
        assert required in seen, f"{required}/ was not walked: {sorted(seen)}"


def test_nothing_in_the_repository_imports_the_retired_ui_package():
    offenders = _offenders(lambda n: n == "UI" or n.startswith("UI."))
    assert not offenders, (
        "files importing the retired Panel tree `UI` (deleted 2026-09-21, tag archive/panel-ui): "
        f"{offenders}")


def test_nothing_in_the_repository_imports_the_panel_family():
    """CLAUDE.md rule 1: the core imports no UI library and nothing in the repo
    imports Panel, HoloViews or Bokeh. Browser libraries live in
    `webui/client/` (TypeScript, not walked here); FastAPI in `webui/server/`."""
    offenders = _offenders(lambda n: n.split(".")[0] in PANEL_FAMILY)
    assert not offenders, f"files importing the Panel family: {offenders}"


def test_the_core_does_not_import_fastapi_or_uvicorn():
    """The bridge's own libraries stop at `webui/`; the core must stay runnable
    on the cluster with neither installed."""
    offenders = {}
    for root in ("Working", "Adapters", "Pipelines"):
        for path in _python_files(os.path.join(PROJECT_ROOT, root)):
            hits = sorted(n for n in _imported_module_names(path)
                          if n.split(".")[0] in ("fastapi", "uvicorn", "starlette"))
            if hits:
                offenders[os.path.relpath(path, PROJECT_ROOT).replace(os.sep, "/")] = hits
    assert not offenders, f"core modules importing the web bridge's libraries: {offenders}"
