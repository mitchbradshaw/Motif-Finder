"""
methods/__init__.py
=====================
The clustering-method registry: a name -> method map, populated by each
method module registering itself on import.

This is deliberately the same shape as `Adapters/registry.py` — `register`
raises on a duplicate name rather than overwriting, `get` names what is
available when it fails, and `discover_methods()` imports every module in the
package so a caller need not know the list. A researcher who has added an
analysis block already knows how to add a clustering method; that is the
point of the symmetry. `docs/LIBRARY_STORAGE.md` section 6 carries the
checklist.

The method protocol
-------------------
A method is a class (registered as an instance) carrying:

    name        = "ward"                     the registered name
    label       = "Ward linkage"             what the editor shows
    description = "one line"                 what the editor shows underneath
    applies_to  = ("shape-distance", ...)    the bases it can serve
    params      = {name: {type, default, label, help}}

and implementing:

    fit(data, *, params) -> FitResult
        `data` is whatever the basis yields: waveforms for a distance basis,
        one feature value per item for a feature-bin basis, one label per
        item for a label basis. The engine does the extraction, so a method
        never touches an item dict and never touches the database.

    assign(fit, *, cut=None) -> list
        one family id per input row, in input order. `None` means omitted,
        and the method records WHY in `fit.omit_reasons[row_index]` — spec
        8.2's omitted entries are flagged, never deleted.

    merge_heights(fit) -> list of float
        the tree's merge heights for the editor's histogram, `[]` when the
        method builds no tree.

A distance method additionally offers `medoid(fit, indices)`; the engine uses
it when it is there and falls back to the first member when it is not.
"""

import importlib
import pkgutil
from dataclasses import dataclass, field

_REGISTRY = {}


@dataclass
class FitResult:
    """What a method learned from one set of inputs, before any cut is
    chosen. Kept separate from `assign` so the grouping editor can fit once
    and then redraw at a dozen cuts without refitting — which is the whole
    reason the merge heights are drawn in the first place.

    `omit_reasons` maps a row index to its omission reason and is written by
    `assign` (and, for a basis that can reject a row before any cut, by
    `fit`). It is state on the fit rather than a second return value because
    `assign`'s contract is "a family id per row"; the reasons travel beside
    it so nothing has to be inferred from a `None`.
    """
    method: str
    n: int
    distances: object = None          # square-form distance matrix, or None
    heights: list = field(default_factory=list)
    family_labels: dict = field(default_factory=dict)
    omit_reasons: dict = field(default_factory=dict)
    payload: dict = field(default_factory=dict)


def register(method):
    """Register a method instance under its own `name`. Called once, at
    module import time, by each method file. Raises if the name is taken —
    a duplicate is a copy-paste mistake, and silently replacing one
    clustering method with another would change every grouping computed
    under that name without changing its recipe hash."""
    name = getattr(method, "name", None)
    if not name:
        raise ValueError("A grouping method must carry a non-empty `name`.")
    if name in _REGISTRY:
        raise ValueError(f"Grouping method '{name}' is already registered.")
    _REGISTRY[name] = method
    return method


def get(name):
    """The registered method, discovering the built-ins first if nothing has
    been imported yet."""
    if not _REGISTRY:
        discover_methods()
    if name not in _REGISTRY:
        raise KeyError(f"Unknown grouping method '{name}'. "
                       f"Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def available():
    """name -> a small spec the grouping editor can render without importing
    anything: the name, its label, the bases it applies to, its parameters
    with types and defaults, and a one-line description."""
    if not _REGISTRY:
        discover_methods()
    return {
        name: {
            "name": name,
            "label": getattr(method, "label", name),
            "description": getattr(method, "description", ""),
            "applies_to": tuple(method.applies_to),
            "params": {k: dict(v) for k, v in method.params.items()},
        }
        for name, method in sorted(_REGISTRY.items())
    }


def methods_for(basis):
    """Every registered method that can serve `basis`, in registration-name
    order — the editor's method choice for a basis the researcher picked."""
    if not _REGISTRY:
        discover_methods()
    return [m for _, m in sorted(_REGISTRY.items()) if basis in m.applies_to]


def defaults_for(name):
    """The method's parameter defaults as a plain dict, so the engine can
    fill in what the caller left out without each method re-stating them."""
    return {k: spec["default"] for k, spec in get(name).params.items()}


def discover_methods():
    """Import every method module in this package so it self-registers.
    Safe to call more than once. Unlike `Adapters.discover_adapters`, an
    import failure is NOT swallowed: these three modules depend only on
    numpy and scipy, so a failure here is a bug in the tree and not an
    optional dependency missing."""
    for _, modname, _ in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{modname}")
    return _REGISTRY
