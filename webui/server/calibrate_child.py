"""site-x (2026-10-20): the function a block cost-model timing runs in its own process (`chain._calibrate_in_process`).

Kept in a module of its own that imports nothing of the bridge, so the spawned child pays for numpy, `Working.block_cost`
and the ONE adapter module that registered the model — not for `server.chain`'s adapter registry, views and the rest
(several seconds a timing would otherwise spend importing before it starts).

The child writes nothing the bridge shares: no database row, no cache, and not the shared calibration file. It times
into a scratch file of its own (`block_cost.calibrate(path=...)` always writes the file it is given) and RETURNS the
entry; the bridge merges it into the shared file under `block_cost._FILE_LOCK`, as it did when the timing ran on its
own thread."""
import importlib
import os
import shutil
import tempfile


def calibrate_in_child(name: str, module: str | None) -> tuple:
    """Import the adapter module that registered `name`'s cost model (a spawned interpreter starts with an empty
    `block_cost.MODELS`), time it, and return ``(pid, key, entry)`` — the calibration file's key and value for it."""
    import json
    from Working import block_cost
    if module:
        importlib.import_module(module)
    scratch = tempfile.mkdtemp(prefix="ub-calibrate-")
    try:
        path = os.path.join(scratch, "block_calibration.json")
        block_cost.calibrate([name], path=path)
        key = block_cost._key(name)
        with open(path, encoding="utf-8") as f:
            return os.getpid(), key, json.load(f)[key]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
