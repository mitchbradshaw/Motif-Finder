"""What a report records to be redone: the code commit, the date and the account."""
from __future__ import annotations

import datetime as _dt
import getpass
import subprocess


def code_commit(repo_root) -> str:
    """`git rev-parse HEAD` in ``repo_root``, or "unknown" when it is not a checkout (or git is absent)."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True,
                             timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    sha = (out.stdout or "").strip()
    return sha if out.returncode == 0 and sha else "unknown"


def account() -> str:
    try:
        return getpass.getuser()
    except Exception:                       # no login name in this environment: say so, do not invent one
        return "unknown"


def provenance(repo_root, database) -> dict:
    return {"database": database, "commit": code_commit(repo_root),
            "date": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"), "account": account()}
