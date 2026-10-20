"""site-x (2026-10-20): the function a block cost-model timing runs in its own process (`chain._calibrate_in_process`).

Kept in a module of its own that imports nothing of the bridge, so the spawned child pays for numpy, `Working.block_cost`
and the ONE adapter module that registered the model — not for `server.chain`'s adapter registry, views and the rest
(several seconds a timing would otherwise spend importing before it starts)."""
import importlib
import os


def calibrate_in_child(name: str, path: str, module: str | None) -> int:
    """Import the adapter module that registered `name`'s cost model (a spawned interpreter starts with an empty
    `block_cost.MODELS`), time it into `path`, and return this process's pid."""
    from Working import block_cost
    if module:
        importlib.import_module(module)
    block_cost.calibrate([name], path=path)
    return os.getpid()
