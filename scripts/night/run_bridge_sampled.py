"""run_bridge_sampled.py — night pass A: `webui/run_server.py` with a stack sampler beside it.

Every 0.25 s it records the innermost repo frame of every thread; every 10 s it writes the counts since the last
write (thread name, function, file:line) to SAMPLER_OUT (default webui/runtime/night/sampler.log). How the night
found what kept a sandbox bridge busy with no page open. Same arguments as run_server.py (always pass --sandbox
and a port of your own)."""
import collections
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "webui"))
OUT = os.path.abspath(os.environ.get("SAMPLER_OUT", os.path.join(ROOT, "webui", "runtime", "night", "sampler.log")))


def _where(frame):
    """The innermost frame inside the repo (not the stdlib or site-packages), and the outermost repo caller."""
    inner, outer = None, None
    f = frame
    while f is not None:
        fn = f.f_code.co_filename
        if fn.startswith(ROOT) and "site-packages" not in fn:
            here = f"{f.f_code.co_name} {os.path.relpath(fn, ROOT)}:{f.f_lineno}"
            inner = inner or here
            outer = here
        f = f.f_back
    return inner, outer


def _sample():
    counts = collections.Counter()
    last = time.monotonic()
    names = {}
    while True:
        time.sleep(0.25)
        for t in threading.enumerate():
            names[t.ident] = t.name
        for ident, frame in sys._current_frames().items():
            if ident == threading.get_ident():
                continue
            inner, outer = _where(frame)
            if inner:
                counts[(names.get(ident, str(ident)), inner, outer)] += 1
        if time.monotonic() - last >= 10:
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(f"--- {time.strftime('%H:%M:%S')} ({sum(counts.values())} samples)\n")
                for (name, inner, outer), n in counts.most_common(12):
                    f.write(f"{n:5d}  {name:28s} {inner}   <- {outer}\n")
            counts.clear()
            last = time.monotonic()


if __name__ == "__main__":
    if any(p in sys.argv for p in ("8765", "8766")):
        sys.exit("refusing 8765/8766")
    threading.Thread(target=_sample, daemon=True, name="night-sampler").start()
    import run_server
    sys.argv[0] = os.path.join(ROOT, "webui", "run_server.py")
    run_server.main()
