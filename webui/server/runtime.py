"""Runtime modes for the web UI bridge.

The bridge has two ways of standing over the database, chosen once per
server start and printed loudly (stage-3 wiring plan D4, fog C9):

**sandbox** (the default; what ``webui/smoke.py`` runs against)
    Never touch real data. The database is a **copy** under
    ``webui/runtime/<stamp>/`` and every path the core could write is
    redirected under that directory before any run happens:

    * ``Working.config.STEP_CACHE_ROOT`` — an absolute temp directory. The
      core reads it *at call time* inside ``_execute_recipe_with_conn``, so
      rebinding the attribute on ``Working.config`` redirects the step cache
      without editing the core. ``STEP_CACHE_WRITE_THRESHOLD_S`` is lowered
      to 0.0 so that even sub-second steps on a short span are cached and the
      "suffix re-run hits the prefix cache" checklist item is meaningful;
    * ``Adapters.detection_matrix_profile.RESULTS_DIR``,
      ``Adapters.preprocessing_window_matrix.RESULTS_DIR`` and
      ``Adapters.catalogue_classifier.MODEL_ROOT`` — the three module-level
      paths the adapters' persist hooks / run bodies read at call time.

**project**
    The REAL database is opened **in place**, in WAL journal mode, after a
    timestamped backup is written beside it (``DATA/db/backups/<stamp>.sqlite``,
    the last ten kept). The step cache, both adapter ``RESULTS_DIR``s and the
    classifier ``MODEL_ROOT`` stay exactly where the core has them. This is
    the mode in which the researcher's annotations, adjudications and runs
    accumulate; ``webui/run_server.py --project`` selects it.

In both modes ``DATA/`` recordings are only ever read
(``np.load(..., mmap_mode="r")``), and the held-out recording is refused on
every route (``HELD_OUT_FILE``) — the refusal is a property of the routes,
not of the mode.

``restore()`` puts every module attribute back; tests use it, the server
does not need to.

Nothing here imports Panel, HoloViews, Bokeh, matplotlib or FastAPI.
"""
from __future__ import annotations

import datetime as _dt
import os
import shutil
import sqlite3
import sys

WEBUI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # .../webui
PROTO_DIR = WEBUI_DIR  # historical name (prototype A), kept for importers
REPO_ROOT = os.path.dirname(WEBUI_DIR)                                      # repo root
REAL_DB = os.path.join(REPO_ROOT, "DATA", "db", "annotations.sqlite")
HELD_OUT_FILE = "M4_aug_concat_fs1.mat"

MODES = ("sandbox", "project")
BACKUPS_KEPT = 10


class Runtime:
    """One runtime per server start: a sandbox copy, or the real database in place."""

    def __init__(self, mode: str = "sandbox", stamp: str | None = None, *,
                 db_source: str | None = None, runtime_root: str | None = None,
                 client_dist: str | None = None):
        if mode not in MODES:
            raise ValueError(f"unknown runtime mode {mode!r}; expected one of {MODES}")
        self.mode = mode
        stamp = stamp or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.stamp = stamp
        self.db_source = os.path.abspath(db_source or REAL_DB)
        self.dir = os.path.join(runtime_root or os.path.join(WEBUI_DIR, "runtime"), stamp)
        self.client_dist = client_dist or os.path.join(WEBUI_DIR, "client", "dist")
        # the runtime dir always holds the server's own scratch: log, exports, meta sidecar
        self.log_path = os.path.join(self.dir, "server.log")
        self.exports_dir = os.path.join(self.dir, "exports")
        self.meta_dir = os.path.join(self.dir, "meta")
        if mode == "sandbox":
            self.db_path = os.path.join(self.dir, "annotations.sqlite")
            self.step_cache_root = os.path.join(self.dir, "step_cache")
            self.results_dir = os.path.join(self.dir, "results")
            self.models_dir = os.path.join(self.dir, "models")
            self.window_sets_root = os.path.join(self.dir, "window_sets")
        else:
            self.db_path = self.db_source
            self.window_sets_root = os.path.join(REPO_ROOT, "DATA", "derived", "window_sets")
            self.step_cache_root = None   # filled from the core's own values in setup()
            self.results_dir = None
            self.models_dir = None
        self.db_backup: str | None = None
        self.journal_mode: str | None = None
        self._originals: dict | None = None

    # ------------------------------------------------------------ setup --
    def setup(self) -> "Runtime":
        if os.getcwd().lower() != REPO_ROOT.lower():
            # recordings.npy_path is repo-relative; the core np.load()s it as-is.
            os.chdir(REPO_ROOT)
        if REPO_ROOT not in sys.path:
            sys.path.insert(0, REPO_ROOT)

        if not os.path.isfile(self.db_source):
            raise SystemExit(f"database not found at {self.db_source}; run from a checkout that has "
                             f"DATA/db/annotations.sqlite, or pass --db")

        for d in (self.dir, self.exports_dir, self.meta_dir):
            os.makedirs(d, exist_ok=True)

        import Working.config as cfg
        import Adapters.detection_matrix_profile as _mp
        import Adapters.preprocessing_window_matrix as _wm
        import Adapters.catalogue_classifier as _cc
        import Adapters.catalogue_cluster as _cl
        self._originals = {
            "STEP_CACHE_ROOT": cfg.STEP_CACHE_ROOT,
            "STEP_CACHE_WRITE_THRESHOLD_S": cfg.STEP_CACHE_WRITE_THRESHOLD_S,
            "mp.RESULTS_DIR": _mp.RESULTS_DIR,
            "wm.RESULTS_DIR": _wm.RESULTS_DIR,
            "cc.MODEL_ROOT": _cc.MODEL_ROOT,
            "cl.RESULTS_DIR": _cl.RESULTS_DIR,
        }

        if self.mode == "sandbox":
            self._setup_sandbox(cfg, _mp, _wm, _cc)
        else:
            self._setup_project(cfg, _mp, _wm, _cc)
        return self

    def _setup_sandbox(self, cfg, _mp, _wm, _cc):
        for d in (self.step_cache_root, self.results_dir, self.models_dir):
            os.makedirs(d, exist_ok=True)
        shutil.copyfile(self.db_source, self.db_path)
        self.journal_mode = _journal_mode(self.db_path)

        cfg.STEP_CACHE_ROOT = self.step_cache_root
        cfg.STEP_CACHE_WRITE_THRESHOLD_S = 0.0
        _mp.RESULTS_DIR = os.path.join(self.results_dir, "matrix_profile")
        _wm.RESULTS_DIR = os.path.join(self.results_dir, "window_matrix")
        _cc.MODEL_ROOT = self.models_dir
        import Adapters.catalogue_cluster as _cl
        _cl.RESULTS_DIR = os.path.join(self.results_dir, "groupings")
        # Critique r1 P0: an adapter executed outside these redirects writes into the real DATA
        # tree. Assert every writable path the adapters read at call time is inside this runtime.
        for label, p in self._core_paths(cfg, _mp, _wm, _cc):
            if not _inside(p, self.dir):
                raise SystemExit(f"refusing to start: {label} = {p} is outside the runtime dir {self.dir}")

    def _setup_project(self, cfg, _mp, _wm, _cc):
        # 1. backup first — a consistent copy via the sqlite backup API, so a
        #    database another process holds open in WAL mode is copied whole.
        backups_dir = os.path.join(os.path.dirname(self.db_source), "backups")
        os.makedirs(backups_dir, exist_ok=True)
        self.db_backup = os.path.join(backups_dir, f"{self.stamp}.sqlite")
        src = sqlite3.connect(self.db_source)
        try:
            dst = sqlite3.connect(self.db_backup)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        if not os.path.isfile(self.db_backup) or os.path.getsize(self.db_backup) == 0:
            raise SystemExit(f"refusing to open {self.db_source}: backup at {self.db_backup} was not written")
        self.backups_pruned = _prune_backups(backups_dir, keep=BACKUPS_KEPT)

        # 2. open the real file in WAL mode (persistent once set on the file).
        conn = sqlite3.connect(self.db_source)
        try:
            mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower()
        finally:
            conn.close()
        if mode != "wal":
            raise SystemExit(f"refusing to continue: could not put {self.db_source} into WAL mode (got {mode!r})")
        self.journal_mode = mode

        # 3. redirect nothing: report the core's own locations.
        self.step_cache_root = cfg.STEP_CACHE_ROOT
        self.results_dir = None
        self.models_dir = _cc.MODEL_ROOT
        for label, p in self._core_paths(cfg, _mp, _wm, _cc):
            if _inside(p, self.dir):
                raise SystemExit(f"refusing to start: project mode must not redirect, but {label} = {p} "
                                 f"is inside the runtime dir {self.dir}")

    @staticmethod
    def _core_paths(cfg, _mp, _wm, _cc):
        import Adapters.catalogue_cluster as _cl
        return (("STEP_CACHE_ROOT", cfg.STEP_CACHE_ROOT),
                ("matrix_profile.RESULTS_DIR", _mp.RESULTS_DIR),
                ("window_matrix.RESULTS_DIR", _wm.RESULTS_DIR),
                ("classifier.MODEL_ROOT", _cc.MODEL_ROOT),
                ("cluster.RESULTS_DIR", _cl.RESULTS_DIR))

    def restore(self) -> None:
        """Put every core module attribute back to what it was before setup()."""
        if not self._originals:
            return
        import Working.config as cfg
        import Adapters.detection_matrix_profile as _mp
        import Adapters.preprocessing_window_matrix as _wm
        import Adapters.catalogue_classifier as _cc
        o = self._originals
        cfg.STEP_CACHE_ROOT = o["STEP_CACHE_ROOT"]
        cfg.STEP_CACHE_WRITE_THRESHOLD_S = o["STEP_CACHE_WRITE_THRESHOLD_S"]
        _mp.RESULTS_DIR = o["mp.RESULTS_DIR"]
        _wm.RESULTS_DIR = o["wm.RESULTS_DIR"]
        _cc.MODEL_ROOT = o["cc.MODEL_ROOT"]
        import Adapters.catalogue_cluster as _cl
        _cl.RESULTS_DIR = o["cl.RESULTS_DIR"]
        self._originals = None

    # --------------------------------------------------------- describe --
    def banner(self) -> str:
        """One loud line for the log and the terminal."""
        if self.mode == "project":
            return (f"MODE = PROJECT: the REAL database {self.db_path} is open IN PLACE (journal_mode={self.journal_mode}); "
                    f"backup written to {self.db_backup}; step cache, results and models stay at their real locations")
        return (f"MODE = SANDBOX: the real database is NOT open; every write lands in the copy {self.db_path} "
                f"and every core path is redirected under {self.dir}")

    def describe(self) -> dict:
        sandbox = self.mode == "sandbox"
        return {
            "mode": self.mode,
            "banner": self.banner(),
            "redirected": sandbox,
            "repo_root": REPO_ROOT,
            "real_db": REAL_DB,
            "db_source": self.db_source,
            "db_path": self.db_path,
            "db_copy": self.db_path if sandbox else None,
            "db_backup": self.db_backup,
            "backups_kept": BACKUPS_KEPT if not sandbox else None,
            "journal_mode": self.journal_mode,
            "runtime_dir": self.dir,
            "step_cache_root": self.step_cache_root,
            "results_dir": self.results_dir,
            "models_dir": self.models_dir,
            "log_path": self.log_path,
            "meta_dir": self.meta_dir,
            "exports_dir": self.exports_dir,
            "window_sets_root": self.window_sets_root,
            "client_dist": self.client_dist,
            "held_out_file": HELD_OUT_FILE,
            "cwd": os.getcwd(),
        }


# ------------------------------------------------------------ helpers --
def _inside(path: str, root: str) -> bool:
    return os.path.abspath(path).lower().startswith(os.path.abspath(root).lower() + os.sep) \
        or os.path.abspath(path).lower() == os.path.abspath(root).lower()


def _journal_mode(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
    finally:
        conn.close()


def _prune_backups(backups_dir: str, keep: int) -> list[str]:
    """Keep the `keep` newest `<stamp>.sqlite` files (stamps sort lexically by time)."""
    names = sorted(n for n in os.listdir(backups_dir) if n.endswith(".sqlite"))
    pruned = names[:-keep] if len(names) > keep else []
    for n in pruned:
        os.remove(os.path.join(backups_dir, n))
    return pruned
