"""site-x (2026-10-20): the function a block cost-model timing runs in its own process (`chain._calibrate_in_process`).

Kept in a module of its own that imports nothing of the bridge, so the spawned child pays for numpy, `Working.block_cost`
and the ONE adapter module that registered the model — not for `server.chain`'s adapter registry, views and the rest
(several seconds a timing would otherwise spend importing before it starts).

The child writes nothing the bridge shares: no database row, no cache, and not the shared calibration file. It RETURNS
the entry (`block_cost.time_model`) and the bridge stores it (`block_cost.store_entries`). tq-worker (2026-10-25): the
scratch file and the copied warm-up are gone; the core times and warms."""
import importlib
import os


def calibrate_in_child(name: str, module: str | None) -> tuple:
    """Import the adapter module that registered `name`'s cost model (a spawned interpreter starts with an empty
    `block_cost.MODELS`), time it warm (`prewarm`: a fresh interpreter's first call pays lazy imports and numba
    compile, fix round F1), and return ``(pid, key, entry)`` — the calibration file's key and value for it."""
    from Working import block_cost
    if module:
        importlib.import_module(module)
    return (os.getpid(), *block_cost.time_model(name, prewarm=True))
