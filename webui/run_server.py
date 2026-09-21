"""Start the web UI bridge.

    .venv/Scripts/python.exe run_server.py [--port 8765] [--sandbox | --project] [--db PATH]

Two modes (see server/runtime.py):

* ``--sandbox`` (default): a throwaway copy of the database under runtime/<stamp>/,
  every writable core path redirected there. What webui/smoke.py runs against.
* ``--project``: the REAL DATA/db/annotations.sqlite opened in place (WAL) after a
  timestamped backup to DATA/db/backups/; nothing redirected. Where real work lands.

``--db`` (or WEBUI_DB) points either mode at a different sqlite file. Runs with
cwd = the repo root (recordings.npy_path is repo-relative).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from server.runtime import Runtime  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("WEBUI_PORT", "8765")))
    ap.add_argument("--host", default="127.0.0.1")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--sandbox", dest="mode", action="store_const", const="sandbox",
                      help="copy the database and redirect every core path (default)")
    mode.add_argument("--project", dest="mode", action="store_const", const="project",
                      help="open the REAL database in place (WAL) after a timestamped backup; redirect nothing")
    ap.add_argument("--db", default=os.environ.get("WEBUI_DB") or None,
                    help="sqlite file to use instead of DATA/db/annotations.sqlite (env WEBUI_DB)")
    ap.set_defaults(mode=os.environ.get("WEBUI_MODE", "sandbox"))
    args = ap.parse_args()

    # Fail loudly on a busy port instead of appearing to start (REPORT §8: old servers linger).
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex((args.host, args.port)) == 0:
            raise SystemExit(f"port {args.port} on {args.host} is already in use; pass --port or set WEBUI_PORT")

    rt = Runtime(mode=args.mode, db_source=args.db).setup()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(sys.stderr), logging.FileHandler(rt.log_path, encoding="utf-8")])
    log = logging.getLogger("webui")
    rule = "=" * 78
    log.warning("%s\n%s\n%s", rule, rt.banner(), rule)
    print(rule, file=sys.stderr)
    print(rt.banner(), file=sys.stderr)
    print(rule, file=sys.stderr)
    for k, v in rt.describe().items():
        if k != "banner":
            log.info("%s = %s", k, v)

    from server.app import create_app
    import uvicorn
    app = create_app(rt)
    log.info("serving on http://%s:%d  (API docs at /api/docs, mode at /api/runtime)", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
