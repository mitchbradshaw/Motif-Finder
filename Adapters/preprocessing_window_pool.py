"""
preprocessing_window_pool.py
============================
fixup-ag: the *Window pool* block — the chain SOURCE that starts an Analyse
chain from saved window sets in place of a span (`AA`'s "§6.9 frame 0b"; RQ1
version 2, ticket `docs/prompts/fixup/AG-…` "What to build" 1).

The researcher ticks saved window sets (the Library's: `AF`'s unlabelled sets at
1, 10 and 30 minutes, earlier pools, the baseline's labelled set read as plain
windows — nothing here assumes six), sets the region plan (time blocks, exam
channels, *hold out pack*) and the overlap rule, and the block combines them
through `AF`'s `Working.training.pool.combine` — the only implementation. The
default mix is the researcher's (2026-10-05): an EQUAL number of windows per
scale, 20,000 each, one seeded setting.

The pool it builds is SAVED — a `window_sets` row with its members, plan and key
(`pool.save_pool`; files under `POOL_ROOT`, rule 4) — and the same pool built
again is re-used, never duplicated: the row is found by its content key. A saved
pool re-opens as the source (`pool`: its id or name), and the rest of the
parameters are then ignored.

The root signal is ignored: the block declares `source=True`, and the validator
refuses it anywhere but step 01. It reads the store (`conn`), so it and every
step after it bypass the step cache (`Working.execution`).

Output: a `WindowSet` whose features are the pool's per-window METADATA
(`Working.training.shape.POOL_META`: recording, channel, length, scale, role, the
set it came from) — never measures.
"""

import os

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register

#: where a pool's files are written; the bridge's sandbox redirects it (runtime.py)
POOL_ROOT = os.path.join("DATA", "derived", "window_sets")

ALL_UNLABELLED = "all unlabelled"


def _set_refs(conn, text):
    from Working.training import pool as tpool
    text = str(text or "").strip()
    if text.lower() == ALL_UNLABELLED:
        return [s["id"] for s in tpool.list_sets(conn) if s["kind"] == "unlabelled"]
    refs = [r.strip() for r in text.replace(";", ",").split(",") if r.strip()]
    return [int(r) if r.isdigit() else r for r in refs]


def _exam(text):
    out = []
    for part in str(text or "").replace(";", ",").split(","):
        part = part.strip().upper().removeprefix("CH")
        if part:
            out.append(int(part) - 1)          # one-based on the page, zero-based in the plan
    return out or None


def _meta(conn, row, pool, saved):
    from Working.training import pool as tpool
    c = pool.meta.get("counts") or tpool.pool_counts(pool)
    plan = pool.meta.get("plan") or {}
    return {"pool": {
        "window_set_id": int(row["id"]), "name": row["name"], "version": int(row["version"] or 1), "key": pool.key,
        "path": row["path"], "saved": saved, "n_windows": int(c["n_windows"]), "by": c["by"],
        "by_role": c["by_role"], "by_scale": c["by_scale"], "dropped": c.get("dropped") or {},
        "at_build": c.get("at_build") or {}, "checks": pool.meta.get("checks"), "rule": pool.meta.get("rule"),
        "rule_text": pool.meta.get("rule_text"), "sample": pool.meta.get("sample"), "seed": pool.meta.get("seed"),
        "members": [{k: m.get(k) for k in ("id", "name", "version", "kind", "key", "n_offered", "n_kept", "dropped")}
                    for m in pool.meta.get("members") or []],
        "plan": {k: plan.get(k) for k in ("n_blocks", "test_frac", "validation_frac", "gap_s", "hold_out_pack")},
        "stretches": {ident: {"exam_channels": r.get("exam_channels"), "stretches": r.get("stretches"),
                              "duration_s": r.get("duration_s")} for ident, r in (plan.get("recordings") or {}).items()},
        "summary": tpool.pool_summary(pool, row["name"], int(row["version"] or 1), pool.key),
    }}


def _run(x, t, fs, window_sets=ALL_UNLABELLED, hold_out_pack="D", exam_channels="", n_blocks=10, test_frac=0.2,
         validation_frac=0.1, gap_min=30.0, rule="within_scale", per_scale=20000, seed=0, pool="", name="",
         conn=None, recording=None):
    from Working.training import pool as tpool
    from Working.training import shape as tshape
    if conn is None:
        raise ValueError("the Window pool block reads saved window sets from the store and needs its connection")
    if str(pool or "").strip():
        ref = str(pool).strip()
        row, p = tpool.load_pool(conn, int(ref) if ref.isdigit() else ref)
        return AdapterResult(output_kind="windowset", value=tshape.pool_windowset(p), meta=_meta(conn, row, p, "re-opened"))
    refs = _set_refs(conn, window_sets)
    if not refs:
        raise ValueError("no window set is ticked: tick at least one saved window set on the Window pool block "
                         "(Library › Window sets › New window set makes them)")
    files, scales = set(), set()
    for ref in refs:
        _row, w = tpool.set_windows(conn, ref)
        files |= set(w["source_file"].unique().tolist())
        scales |= {float(v) for v in (w["length"] / w["fs"] / 60.0).round(6).unique()}
    plan = tpool.plan_for(conn, sorted(files), n_blocks=int(n_blocks), test_frac=float(test_frac),
                          validation_frac=float(validation_frac), gap_s=float(gap_min) * 60.0,
                          hold_out_pack=(hold_out_pack or None), exam_channels=_exam(exam_channels))
    # an equal share for every scale the ticked sets hold
    sample = {s: int(per_scale) for s in sorted(scales)} if int(per_scale) > 0 else None
    p = tpool.combine(conn, refs, plan, rule=rule, sample=sample, seed=int(seed))
    key = p.key
    found = conn.execute("SELECT * FROM window_sets WHERE recipe_hash = ? ORDER BY id LIMIT 1", (key,)).fetchone()
    if found is not None and tpool.set_kind(conn, found) == "pool":
        return AdapterResult(output_kind="windowset", value=tshape.pool_windowset(p), meta=_meta(conn, found, p, "reused"))
    ws_id = tpool.save_pool(conn, p, POOL_ROOT, (str(name).strip() or f"pool_{key[:8]}"))
    row = conn.execute("SELECT * FROM window_sets WHERE id = ?", (ws_id,)).fetchone()
    return AdapterResult(output_kind="windowset", value=tshape.pool_windowset(p), meta=_meta(conn, row, p, "saved"))


def _estimate(x, t, fs, **params):
    """`AF` measured `combine` at 7 s for the six sets (1.09 million windows) on this machine."""
    return 10.0


SPEC = register(AdapterSpec(
    name="preprocessing.window_pool",
    display_name="Window pool (saved window sets -> WindowSet)",
    stage="preprocessing",
    category="preprocess",
    page_name="Window pool",
    source=True,
    params=[
        ParamSpec("window_sets", str, ALL_UNLABELLED,
                  "The saved window sets to combine, by id, in order (the first listed wins a duplicate or an "
                  f"overlap) — ticked on the block's page. '{ALL_UNLABELLED}': every saved unlabelled set."),
        ParamSpec("hold_out_pack", str, "D", "A whole mushroom pack held out as the exam on every recording "
                  "(CH1–4 A, CH5–8 B, CH9–12 C, CH13–16 D); empty for none.", choices=["", "A", "B", "C", "D"]),
        ParamSpec("exam_channels", str, "", "More exam channels, one-based (e.g. 4, 8)."),
        ParamSpec("n_blocks", int, 10, "Time blocks per recording (blocked by time, as the baseline).", min=3),
        ParamSpec("test_frac", float, 0.2, "The last share of each recording is the test.", min=0.0, max=0.9),
        ParamSpec("validation_frac", float, 0.1, "The share before the test is validation.", min=0.0, max=0.9),
        ParamSpec("gap_min", float, 30.0, "Minutes of no-man's-land at every role change (at least the longest "
                  "window).", min=1.0),
        ParamSpec("rule", str, "within_scale", "within_scale: no overlap within a scale, overlap across scales "
                  "allowed (never across roles). no_overlap: none at all — the smaller scale wins.",
                  choices=["within_scale", "no_overlap"]),
        ParamSpec("per_scale", int, 20000, "Windows drawn per scale, seeded (the researcher: an equal number per "
                  "scale, 20,000 each). 0 keeps every window.", min=0),
        ParamSpec("seed", int, 0, "The sample's seed.", min=0),
        ParamSpec("pool", str, "", "Re-open a saved pool (its id or name) as the source; the parameters above "
                  "are then ignored."),
        ParamSpec("name", str, "", "The name a new pool is saved under (default pool_<key>)."),
    ],
    run=_run,
    input_kind="signal",
    output_kind="windowset",
    estimate=_estimate,
    description=("A chain source: combines saved window sets into one pool with a region-first train / validation "
                 "/ test / exam plan (Working.training.pool.combine), saves the pool, and passes its windows on "
                 "with their recording, scale and role. The root signal is ignored."),
))
