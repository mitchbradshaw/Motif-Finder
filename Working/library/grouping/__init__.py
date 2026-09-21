"""
Working.library.grouping
==========================
The grouping engine: `unit x basis x method(params) -> an assignment per
member`.

See `docs/LIBRARY_STORAGE.md` section 6, and its checklist for adding a
method. The three pieces:

`engine`    `run_grouping` and `preview` — the rules that belong to no single
            method: which items take part, `min_group`, and what does not fit.
            It takes plain dicts and never touches the database.
`bases`     the four feature computations, the histogram the editor draws,
            and which bases apply to which unit. Nothing here is stored (3.4).
`methods/`  the registered clustering methods, one class per name, registered
            exactly as `Adapters/registry.py` registers a block.
"""

from Working.library.grouping.engine import (
    Assignment,
    Family,
    GroupingPreview,
    GroupingResult,
    preview,
    run_grouping,
)

__all__ = [
    "Assignment",
    "Family",
    "GroupingPreview",
    "GroupingResult",
    "preview",
    "run_grouping",
]
