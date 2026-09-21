"""
Working.registration
====================
Registering data that already exists on disk so the interface can reach it
(stage-3 Prompt 02; the standard is ``docs/DATA_REGISTRATION.md``).

    scan(kind, roots)            -> [Candidate]   what is on disk, registered or not
    check(candidate, conn)       -> Report        the checks, loudly
    register(conn, candidate)    -> row id        the row + the sidecar manifest
    unregister(conn, kind, id)                    soft: active = 0
    list_registered(conn, kind)  -> [dict]        what the UI lists

Every kind is a ``KindSpec`` in ``kinds.py``. UI-free: nothing here imports a
browser library, FastAPI or Panel. Rows are written through a ``writer``
callable so the bridge can pass its rule-5 door (``writes.write_machine``).
"""
from .core import (  # noqa: F401
    Candidate, Check, RegistrationError, Report, check, list_registered, register, scan, sidecar_path, unregister,
)
from .excerpt import find_excerpt  # noqa: F401
from .kinds import KINDS, KindSpec  # noqa: F401
