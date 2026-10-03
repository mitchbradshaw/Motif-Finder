"""
python -m Working.training — the paired training job from the command line
(fixup-ab, seam i): what lets RQ1 be answered before the Models pages read it.

    save-set  pool the labelled windows of a recording's channels, split, measure, save
    propose   cluster the set's training windows; silhouette and contingency per k; write a draft recipe
    run       train both arms, score the exams, record the run
    show      print a recorded run

Example (on a COPY of the database — this writes rows and files):

    python -m Working.training save-set --db sandbox.sqlite --root runs/training \\
        --source M2_aug_concat_fs1.mat --channels 0-11 --exam-channels 12-15 --name m2_pooled
    python -m Working.training propose --db sandbox.sqlite --root runs/training --set m2_pooled \\
        --k-range 2-8 --out recipe.json            # then edit k / translation in recipe.json
    python -m Working.training run --db sandbox.sqlite --root runs/training --recipe recipe.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def _ints(spec):
    out = []
    for part in str(spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def _progress(done, total, msg):
    print(f"  [{done}/{total}] {msg}", file=sys.stderr, flush=True)


def _conn(db):
    from Working.database.schema import init_db
    if not os.path.isfile(db):
        raise SystemExit(f"no database at {db}")
    return init_db(db)


def _f(v, nd=3):
    return "—" if v is None else f"{v:.{nd}f}"


def _ci(ci):
    return "—" if not ci or ci[0] is None else f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def summary(res):
    """The plain-text answer: both arms, the null, the paired difference, per exam."""
    from Working.training import paired as tp
    ws = res["window_set"]
    lines = [f"paired job · recipe {res['recipe_hash']} · window set {ws.get('name')} (key {ws['key']})",
             f"  {ws['n_windows']:,} windows · {ws['source_file']} · train channels {ws['channels']} · "
             f"exam channels {ws['exam_channels']}",
             f"  split {ws['split']}",
             f"  arm B: {res['cluster']['linkage']} k = {res['cluster']['k']} on {res['cluster']['n_windows']:,} "
             f"training windows · translation {res['cluster']['translation']} ({res['cluster']['translation_source']})"]
    for e, title in ((tp.EXAM_I, "exam (i) later time block"), (tp.EXAM_II, "exam (ii) channels never trained on"),
                     (tp.EXAM_III, "exam (iii) held-out recording")):
        ex = res["exams"][e]
        if ex["status"] != "scored":
            lines.append(f"{title}: {ex['status']} — {ex.get('reason', '')}")
            continue
        lines.append(f"{title}: {ex['n_windows']:,} windows {ex['class_counts']} · bootstrap over {ex['n_units']} "
                     f"units of {ex['unit']}")
        for arm, label in (("A", "arm A (manual)"), ("B", "arm B (cluster)")):
            a = ex["arms"][arm]
            n = a["null"]
            lines.append(f"  {label}: macro F1 {_f(a['macro_f1'])} {_ci(a['macro_f1_ci'])} · balanced acc "
                         f"{_f(a['balanced_accuracy'])} · null mean {_f(n['mean'])} q95 {_f(n['q95'])} "
                         f"p {_f(n['p'], 4)} ({len(n['draws'])} shuffles)")
            for cls, pc in a["per_class"].items():
                lines.append(f"      {cls:16s} P {_f(pc['precision'])} R {_f(pc['recall'])} F1 {_f(pc['f1'])} n {pc['n']}")
        p = ex["paired"]
        lines.append(f"  ΔF1 (A − B) {_f(p['delta_f1'])} {_ci(p['delta_f1_ci'])} · McNemar b {p['mcnemar']['b']} "
                     f"c {p['mcnemar']['c']} p {_f(p['mcnemar']['p'], 4)} · agreement {p['agreement']}")
        for r in ex["per_channel"]:
            lines.append(f"      CH{r['channel']:<3d} n {r['n']:4d} A {_f(r['A'])} B {_f(r['B'])}")
    for r in res.get("reference") or []:
        if r.get("status") != "scored":
            lines.append(f"reference {r['name']}: {r['status']} — {r.get('reason', '')}")
        else:
            bits = " · ".join(f"{e} {_f(v.get('macro_f1'))}" for e, v in r["exams"].items() if v.get("status") == "scored")
            lines.append(f"reference {r['name']} (trained differently): macro F1 {bits}")
    lines.append(f"yardstick (B): {res['yardstick_b']['status']}")
    lines.extend(f"note: {n}" for n in res["notes"])
    lines.append(f"timings {', '.join(f'{k} {v:.1f}s' for k, v in res['timings'].items())}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m Working.training", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--db", required=True, help="the database to read labels from and write rows to")
        p.add_argument("--root", required=True, help="where window sets and run outputs are written")

    p = sub.add_parser("save-set")
    common(p)
    p.add_argument("--source", required=True)
    p.add_argument("--channels", required=True, help="training channels, e.g. 0-11")
    p.add_argument("--exam-channels", default="", help="channels never trained on, e.g. 12-15")
    p.add_argument("--name", required=True)
    p.add_argument("--stages", default="catch22,fast_entropy")
    p.add_argument("--length", type=int, default=600)
    p.add_argument("--grid", type=int, default=200)
    p.add_argument("--n-blocks", type=int, default=10)
    p.add_argument("--test-frac", type=float, default=0.2)
    p.add_argument("--validation-frac", type=float, default=0.1)
    p.add_argument("--gap-windows", type=int, default=1)
    p.add_argument("--notes")

    p = sub.add_parser("propose")
    common(p)
    p.add_argument("--set", required=True, help="window set name (latest version) or id")
    p.add_argument("--k-range", default="2-8")
    p.add_argument("--k", type=int, help="the cut to write into the draft (default: best silhouette)")
    p.add_argument("--linkage", default="ward")
    p.add_argument("--out", required=True, help="the draft recipe to write")

    p = sub.add_parser("run")
    common(p)
    p.add_argument("--recipe", required=True)
    p.add_argument("--reference", action="store_true", help="also score the existing MODELS/ as a reference line")

    p = sub.add_parser("show")
    common(p)
    p.add_argument("--run", type=int, required=True)

    a = ap.parse_args(argv)
    from Working.training import paired as tp
    from Working.training import store as ts
    from Working.training import windows as tw

    conn = _conn(a.db)
    try:
        if a.cmd == "save-set":
            t0 = time.time()
            split = {"rule": "blocked_by_time", "n_blocks": a.n_blocks, "test_frac": a.test_frac,
                     "validation_frac": a.validation_frac, "gap_windows": a.gap_windows}
            ps = tw.build_pooled_set(conn, a.source, _ints(a.channels), exam_channels=_ints(a.exam_channels),
                                     length=a.length, grid=a.grid, split=split,
                                     stages=tuple(s for s in a.stages.split(",") if s), progress=_progress)
            ws_id = ts.save_window_set(conn, ps, os.path.join(a.root, "window_sets"), a.name, notes=a.notes)
            row = ts.window_set_row(conn, {"id": ws_id})
            print(f"saved window set {a.name} v{row['version']} (id {ws_id}, key {ps.key}) · {len(ps.table):,} windows "
                  f"in {time.time() - t0:.0f} s")
            for r, c in tw.role_counts(ps).items():
                print(f"  {r:10s} {c['n']:6,d} windows · interesting {c['interesting']:,} · not_interesting "
                      f"{c['not_interesting']:,}")
            return 0

        if a.cmd == "propose":
            ref = {"id": int(a.set)} if str(a.set).isdigit() else {"name": a.set}
            row, ps = ts.load_window_set(conn, ref)
            lo, hi = (_ints(a.k_range)[0], _ints(a.k_range)[-1])
            prop = tp.propose(ps, linkage=a.linkage, k_range=(lo, hi))
            print(f"{prop['n_windows_clustered']:,} training windows clustered ({a.linkage}); {prop['note']}")
            print(f"draft cut rule: {prop['suggestion_rule']}")
            for r in prop["by_k"]:
                print(f"  k {r['k']:2d} silhouette {_f(r['silhouette'])} sizes {r['sizes']} · effective k "
                      f"{r['effective_k']}" + (f" (specks: clusters {r['small_clusters']})" if r["small_clusters"] else ""))
                for p_ in r["purity"]:
                    c = r["contingency"][p_["cluster"] - 1]
                    print(f"      cluster {p_['cluster']}: not_interesting {c[0]:5d} · interesting {c[1]:5d} → "
                          f"{r['translation'][str(p_['cluster'])]}{'  (impure)' if p_['impure'] else ''}")
            k = a.k or prop["suggested_k"]
            chosen = next(r for r in prop["by_k"] if r["k"] == k)
            recipe = tp.make_recipe({"id": int(row["id"]), "name": row["name"], "version": int(row["version"]),
                                     "key": ps.key}, k=k, translation=chosen["translation"], linkage=a.linkage)
            recipe["draft_note"] = ("k and translation are a DRAFT (best silhouette, majority on training windows): "
                                    "edit them now — once a test score exists they are frozen on this set")
            with open(a.out, "w", encoding="utf-8") as f:
                json.dump(recipe, f, indent=2)
            print(f"draft recipe written to {a.out} with k = {k}, translation {chosen['translation']}")
            return 0

        if a.cmd == "run":
            with open(a.recipe, encoding="utf-8") as f:
                recipe = json.load(f)
            recipe.pop("draft_note", None)
            if a.reference:
                recipe["reference"]["enabled"] = True
            out = ts.run_and_record(conn, recipe, os.path.join(a.root, "runs"), progress=_progress)
            print(f"run {out['run_id']} · results {out['results_path']}")
            print(summary(out["results"]))
            return 0

        if a.cmd == "show":
            got = ts.get_run(conn, a.run)
            if got is None:
                print(f"no paired training run {a.run}", file=sys.stderr)
                return 1
            if not got["results"]:
                print(f"run {a.run}: {got['status']}\n{got['error'] or ''}")
                return 0 if got["status"] != "failed" else 1
            print(summary(got["results"]))
            return 0
    finally:
        conn.close()
    return 2


if __name__ == "__main__":
    sys.exit(main())
