"""
wave1.zipper — REPORT.md, MANIFEST.csv and the zip parts.

Part 01 holds only REPORT.md, MANIFEST.csv, the run log and the step statuses (so the first attachment says what
every other part holds). Parts 02.. hold the data, split at file boundaries in path order, each at most
``--max-part-mb`` (decimal MB). The size of every file inside a zip is known before it is written (already-compressed
files are stored; the rest are deflated at level 6, measured with the same zlib settings first), so no part can pass
the limit. A file that alone would not fit is split before zipping: a CSV by rows (``name.partNN.csv``, each with the
header), anything else by bytes (``name.splitNN``; join them back in order). Array files never need it: the writers
already cap an npz well under the limit.
"""
from __future__ import annotations

import glob
import json
import os
import platform
import sys
import time
import zlib
import zipfile

import numpy as np
import pandas as pd

from wave1 import common as C

STORED_EXT = (".npz", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".gz", ".parquet", ".pdf", ".webp")
LEVEL = 6


def _method(path):
    return zipfile.ZIP_STORED if path.lower().endswith(STORED_EXT) else zipfile.ZIP_DEFLATED


def zipped_size(path):
    """Bytes the file will take inside the zip (data only)."""
    if _method(path) == zipfile.ZIP_STORED:
        return os.path.getsize(path)
    co = zlib.compressobj(LEVEL, zlib.DEFLATED, -15)
    n = 0
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            n += len(co.compress(b))
    return n + len(co.flush())


def overhead(arcname):
    return 160 + 2 * len(arcname.encode("utf-8"))


def _split_csv(path, chunk_bytes):
    out = []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        header = fh.readline()
        buf, size, k = [], 0, 0
        for line in fh:
            if buf and size + len(line) > chunk_bytes:
                k += 1
                out.append(_write_part(path, k, header, buf))
                buf, size = [], 0
            buf.append(line)
            size += len(line)
        if buf or not out:
            k += 1
            out.append(_write_part(path, k, header, buf))
    os.remove(path)
    return out


def _write_part(path, k, header, lines):
    p = f"{path[:-4]}.part{k:02d}.csv"
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(header)
        fh.writelines(lines)
    return p


def _split_bytes(path, chunk_bytes):
    out = []
    with open(path, "rb") as fh:
        k = 0
        for b in iter(lambda: fh.read(int(chunk_bytes)), b""):
            k += 1
            p = f"{path}.split{k:02d}"
            with open(p, "wb") as o:
                o.write(b)
            out.append(p)
    os.remove(path)
    return out


def data_files(ctx):
    out = []
    status_dir = os.path.join(ctx.data_dir, "_status")
    for dp, _dn, fns in os.walk(ctx.data_dir):
        if os.path.abspath(dp).startswith(os.path.abspath(status_dir)):
            continue                      # the statuses go in part 01
        for fn in fns:
            p = os.path.join(dp, fn)
            if fn.endswith(".tmp"):
                continue
            out.append(p)
    return sorted(out, key=lambda p: os.path.relpath(p, ctx.out).replace("\\", "/"))


def plan_parts(ctx, limit):
    """Split what must be split, then assign every data file to a part (02, 03, ...). Returns (plan, splits) where
    plan is a list of parts, each a list of (path, arcname, zipped bytes)."""
    splits = []
    files = []
    for p in data_files(ctx):
        arc = os.path.relpath(p, ctx.out).replace("\\", "/")
        z = zipped_size(p)
        if z + overhead(arc) + 1024 > limit:
            chunk = int(limit * 0.8)
            parts = _split_csv(p, chunk) if p.lower().endswith(".csv") else _split_bytes(p, chunk)
            splits.append({"file": arc, "into": [os.path.basename(x) for x in parts],
                           "how": "rows (each part has the header)" if p.lower().endswith(".csv") else
                           "bytes: concatenate the .splitNN files in order to rebuild it"})
            ctx.warn(f"{arc} was too big for one part: split into {len(parts)}")
            for x in parts:
                files.append((x, os.path.relpath(x, ctx.out).replace("\\", "/"), zipped_size(x)))
        else:
            files.append((p, arc, z))
    files.sort(key=lambda f: f[1])
    plan, cur, size = [], [], 1024
    for f in files:
        need = f[2] + overhead(f[1])
        if cur and size + need > limit:
            plan.append(cur)
            cur, size = [], 1024
        cur.append(f)
        size += need
    if cur:
        plan.append(cur)
    return plan, splits


def write_zip(path, entries):
    with zipfile.ZipFile(path, "w", allowZip64=True) as z:
        for p, arc in entries:
            m = _method(p)
            if m == zipfile.ZIP_STORED:
                z.write(p, arc, compress_type=m)
            else:
                z.write(p, arc, compress_type=m, compresslevel=LEVEL)
    return os.path.getsize(path)


def statuses(ctx):
    out = {}
    for p in sorted(glob.glob(os.path.join(ctx.data_dir, "_status", "*.json"))):
        try:
            with open(p, encoding="utf-8") as fh:
                s = json.load(fh)
            out[s["step"]] = s
        except (OSError, ValueError, KeyError):
            continue
    return out


def report_text(ctx, *, order, args, estimate, plan=None, splits=None, part_paths=None, run_s=None):
    st = statuses(ctx)
    L = ["# Thesis export, wave 1 — REPORT", "",
         f"Written {C.now_iso()} by `scripts/thesis/wave1/run_wave1.py` (read-only on the database).", "",
         "## In plain words", "",
         "This bundle is a read-only copy of the signal excerpts and tables the thesis figures need, cut from the "
         "real database and channel files. Nothing in the database was changed. Each step below either worked (ok) "
         "or failed on its own without stopping the others; a failed step's traceback is in `wave1.log`.", "",
         "## Run", "",
         f"- database: `{ctx.db_path}` (opened `mode=ro`)",
         f"- repo root: `{ctx.root}`; output: `{ctx.out}`",
         f"- python {platform.python_version()} on {platform.platform()}; numpy {np.__version__}; "
         f"pandas {pd.__version__}",
         f"- arguments: `{' '.join(args)}`",
         f"- recordings kept: {', '.join(f'{k} = {v}' for k, v in ctx.kept.items())}",
         f"- estimated runtime before the run: about {estimate / 60:.0f} min"
         + (f"; this run took {run_s / 60:.1f} min" if run_s is not None else ""), "",
         "## Steps", "",
         "| step | status | time | output | summary |", "|---|---|---|---|---|"]
    for name in order:
        s = st.get(name)
        if s is None:
            L.append(f"| {name} | not run | | | |")
            continue
        summ = json.dumps(s.get("summary"), default=str)
        if len(summ) > 400:
            summ = summ[:400] + "..."
        L.append(f"| {name} | **{s['status']}** | {s.get('seconds', 0):.0f} s | "
                 f"{s.get('files', 0)} files, {s.get('bytes', 0) / 1e6:.1f} MB | `{summ.replace('|', '/')}` |")
    failed = [n for n in order if st.get(n, {}).get("status") not in (None, "ok")]
    if failed:
        L += ["", "## Failures (last lines of each traceback)", ""]
        for n in failed:
            tb = (st[n].get("error") or "").strip().splitlines()[-12:]
            L += [f"### {n} ({st[n]['status']})", "", "```", *tb, "```", ""]
    notes = list(ctx.notes)
    for n in order:
        notes += [f"[{n}] {w}" for w in st.get(n, {}).get("warnings", []) if f"[{n}] {w}" not in notes]
    if notes:
        L += ["", "## Warnings and fallbacks", ""] + [f"- {n}" for n in dict.fromkeys(notes)]
    L += ["", "## Reading the files", "",
          "- `*.npz` + `*.json` (same name): float32 millivolts (`Working.units.read_as_mv`: V x1000, mV x1; an "
          "undeclared unit read as volts, said in `units_note`). A series: `np.load(f)['x']` (1-D, or channels x "
          "time), time of sample i = `t0_s + i * dt_s`. A stack of windows: `values` + `offsets` "
          "(window i = `values[offsets[i]:offsets[i+1]]`), one row per window in `<stack>_index.csv`. A file split "
          "for size is `__chunkNN`, each with its own `t0_s`.",
          "- `*.csv`: tables; sample indices are channel-absolute; `*_s` columns are seconds from the recording's "
          "first sample.",
          "- `data/_status/<step>.json`: what each step reported.", ""]
    if splits:
        L += ["## Files split for size", ""] + [f"- `{s['file']}` -> {', '.join(s['into'])} ({s['how']})"
                                                for s in splits] + [""]
    if plan is not None:
        L += ["## Zip parts", "",
              "- part 01: REPORT.md, MANIFEST.csv, the log, the step statuses"]
        for i, p in enumerate(plan, start=2):
            tops = sorted({a.split("/")[1] if a.count("/") >= 1 else a for _p, a, _z in p})
            L.append(f"- part {i:02d}: {len(p)} files ({sum(z for _p, _a, z in p) / 1e6:.1f} MB): {', '.join(tops)}")
        L.append("")
    if part_paths:
        L += ["Written:", ""] + [f"- `{p}` ({os.path.getsize(p) / 1e6:.1f} MB)" for p in part_paths if os.path.isfile(p)]
    return "\n".join(L) + "\n"


def finish(ctx, *, order, args, estimate, run_s):
    """Write REPORT.md and MANIFEST.csv, zip everything into parts of at most ctx.max_part_mb, and return the part
    paths (part 01 first)."""
    limit = int(ctx.max_part_mb * 1e6)
    for old in glob.glob(os.path.join(ctx.out, "wave1_part*.zip")):
        os.remove(old)
    plan, splits = plan_parts(ctx, limit)
    paths = []
    t = time.time()
    for i, part in enumerate(plan, start=2):
        p = os.path.join(ctx.out, f"wave1_part{i:02d}.zip")
        size = write_zip(p, [(f[0], f[1]) for f in part])
        if size > limit:
            raise RuntimeError(f"{p} is {size} bytes, over the {limit}-byte limit (a planning bug)")
        paths.append(p)
        ctx.log(f"zip part {i:02d}: {len(part)} files, {size / 1e6:.1f} MB")
    ctx.log(f"zipped {len(plan)} data part(s) in {time.time() - t:.1f}s")
    rows = [{"file": f[1], "bytes": os.path.getsize(f[0]), "zip_bytes": f[2], "part": f"wave1_part{i:02d}.zip"}
            for i, part in enumerate(plan, start=2) for f in part]
    C.write_csv(os.path.join(ctx.out, "MANIFEST.csv"), pd.DataFrame(rows, columns=["file", "bytes", "zip_bytes",
                                                                                   "part"]))
    first = os.path.join(ctx.out, "wave1_part01.zip")
    all_paths = [first] + paths
    rep = os.path.join(ctx.out, "REPORT.md")
    with open(rep, "w", encoding="utf-8") as fh:
        fh.write(report_text(ctx, order=order, args=args, estimate=estimate, plan=plan, splits=splits,
                             part_paths=None, run_s=run_s)
                 + "\nParts: " + ", ".join(os.path.basename(p) for p in all_paths) + "\n")
    meta = [(rep, "REPORT.md"), (os.path.join(ctx.out, "MANIFEST.csv"), "MANIFEST.csv")]
    log = ctx.log_path
    if os.path.getsize(log) > limit * 0.5:
        tail = os.path.join(ctx.out, "wave1_log_tail.txt")
        with open(log, "rb") as fh:
            fh.seek(max(0, os.path.getsize(log) - int(limit * 0.4)))
            data = fh.read()
        with open(tail, "wb") as fh:
            fh.write(b"(the log was too big for part 01: its last part follows)\n" + data)
        meta.append((tail, "wave1_log_tail.txt"))
    else:
        meta.append((log, "wave1.log"))
    for p in sorted(glob.glob(os.path.join(ctx.data_dir, "_status", "*.json"))):
        meta.append((p, os.path.relpath(p, ctx.out).replace("\\", "/")))
    write_zip(first, meta)
    # the REPORT.md left on disk also lists the written parts with their sizes
    with open(rep, "w", encoding="utf-8") as fh:
        fh.write(report_text(ctx, order=order, args=args, estimate=estimate, plan=plan, splits=splits,
                             part_paths=all_paths, run_s=run_s))
    return all_paths


def python_info():
    return f"{sys.executable} {platform.python_version()}"
