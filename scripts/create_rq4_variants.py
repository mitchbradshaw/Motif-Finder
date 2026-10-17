"""Create the RQ4 sweep's variant templates through a running bridge.

One template per (base template, parameter value): the base's chain with one
parameter changed, saved under its own name, so Discovery can tick it beside the
others and the Map gives it its own row (a Map row is keyed by the executed
steps). The base template already is the default value and is not copied.

Talks to the bridge over HTTP only (stdlib; nothing from the core is imported).
Safe by default:

* Without ``--apply`` nothing is written: the plan is printed and every changed
  step is checked by the block itself (``POST /api/chain/params`` fills defaults
  and range-checks), so a wrong parameter name or an out-of-range value fails
  here, before any write.
* ``--apply`` reads ``GET /api/runtime`` first and refuses a bridge in PROJECT
  mode (the real database) unless ``--allow-project`` is also given.
* Idempotent: a variant whose name already exists is skipped, never written
  twice. The ``templates`` table does not enforce unique names, and Discovery
  applies the first template it finds with a name, so a duplicate would be
  silently shadowed.
* ``--remove`` undoes it: it deletes only the templates this script wrote (named
  by the plan below AND carrying ``MARK`` in their description).

    python scripts/create_rq4_variants.py --url http://127.0.0.1:8799                 # dry run
    python scripts/create_rq4_variants.py --url http://127.0.0.1:8799 --apply         # a sandbox bridge
    python scripts/create_rq4_variants.py --apply --allow-project                     # the real database
    python scripts/create_rq4_variants.py --url ... --remove [--apply]                # undo

Start a sandbox bridge beside a running one with
``webui/.venv/Scripts/python.exe webui/run_server.py --port 8799`` (sandbox is the default mode).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8765"
MARK = "[rq4-sweep]"

#: (base template, parameter, the blocks in the chain that carry it, values, label).
#: The base's own value is skipped at run time, so each row adds len(values) - 1 templates.
#: `label` names the variant (defaults to the parameter); signal_threshold's cut is in the
#: file's STORED units, so it gets a V copy (M2, M2_aug) and an mV copy (L_LM,
#: Schizophyllum, Dwij). Every other parameter here is unit-free or converted by the block.
SWEEP = [
    ("drop_detection_v1", "slope_sigma", ("stage_encoding", "drop_detection"), [4, 8, 12], None),
    ("drop_detection_v5", "same_fraction", ("stage_encoding",), [0.5, 0.58, 0.7], None),
    ("wavelet_encoded", "level", ("wavelet_bands",), [3, 4, 5], None),
    ("dehshibi_spikes", "epsilon_factor", ("summation_threshold",), [0.02, 0.05, 0.1], None),
    ("Wavelet_detection_prototype", "epsilon_factor", ("dehshibi_spikes",), [0.02, 0.05, 0.1], None),
    ("mp_threshold", "threshold", ("threshold",), [6, 8, 10], None),
    ("symbol_search", "seconds_per_symbol", ("sax_dsax",), [10, 20, 40], None),
    ("noise_threshold", "k_sigma", ("noise_threshold",), [3, 4, 6], None),
    ("signal_threshold", "threshold", ("signal_threshold",), [-0.002, -0.005, -0.01], "threshold_V"),
    ("signal_threshold", "threshold", ("signal_threshold",), [-2, -5, -10], "threshold_mV"),
    ("deconvolved_troughs", "recovery_half_s", ("deconvolve",), [60, 120, 240], None),
    ("OASIS_Deconvolution", "threshold", ("impulse_events",), [3, 3.848, 5], None),
    ("BEADs_invert_detect_v1", "delta_mv", ("spike_v1",), [5, 15, 25], None),
]


class BridgeError(RuntimeError):
    pass


def call(base_url, method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise BridgeError(f"{method} {path} -> HTTP {e.code}: {detail[:600]}") from None
    except urllib.error.URLError as e:
        raise BridgeError(f"{method} {path}: no bridge at {base_url} ({e.reason})") from None


def fmt(value):
    """A value as a name fragment: 0.58 -> 0p58, -0.002 -> m0p002, 12.0 -> 12."""
    return ("%g" % value).replace("-", "m").replace(".", "p")


def variant_name(base, label, value):
    return f"{base}__{label}_{fmt(value)}"


def checked_params(url, step):
    """The step's params as the block validates them: defaults filled, coerced, range-checked."""
    body = {"stage": step["stage"], "algorithm": step["algorithm"],
            "params": step.get("params") or {}, "side_inputs": step.get("side_inputs") or {}}
    return call(url, "POST", "/api/chain/params", body)["params"]


def by_name(templates):
    """Name -> the row Discovery would use (the lowest id), plus the names held more than once."""
    first, dupes = {}, set()
    for t in sorted(templates, key=lambda t: int(t["id"])):
        if t["name"] in first:
            dupes.add(t["name"])
        else:
            first[t["name"]] = t
    return first, dupes


def plan(url, templates):
    """Every variant the sweep asks for, each checked by its blocks; nothing written."""
    have, dupes = by_name(templates)
    rows, problems = [], []
    for base_name, param, algorithms, values, label in SWEEP:
        base = have.get(base_name)
        if base is None:
            problems.append(f"base template {base_name!r} is not in this database")
            continue
        if base_name in dupes:
            problems.append(f"note: {base_name!r} is held more than once; using id {base['id']}, the one Discovery applies")
        targets = [i for i, s in enumerate(base["steps"]) if s["algorithm"] in algorithms]
        missing = set(algorithms) - {base["steps"][i]["algorithm"] for i in targets}
        if missing:
            problems.append(f"{base_name}: no step {sorted(missing)} in its chain "
                            f"({[s['algorithm'] for s in base['steps']]})")
            continue
        base_values = {checked_params(url, base["steps"][i])[param] for i in targets}
        for value in values:
            name = variant_name(base_name, label or param, value)
            steps = copy.deepcopy(base["steps"])
            try:
                for i in targets:
                    trial = dict(steps[i], params={**(steps[i].get("params") or {}), param: value})
                    # store the value as the block coerces it (4 -> 4.0 for a float parameter);
                    # the step's other params stay exactly as the base wrote them
                    steps[i].setdefault("params", {})[param] = checked_params(url, trial)[param]
            except BridgeError as e:
                problems.append(f"{name}: refused by the block: {e}")
                continue
            rows.append({"name": name, "base": base, "param": param, "label": label or param,
                         "value": value, "steps": steps, "targets": [steps[i]["algorithm"] for i in targets],
                         "base_value": sorted(base_values)[0] if len(base_values) == 1 else sorted(base_values),
                         "is_base": base_values == {value}, "existing": have.get(name)})
    return rows, problems


#: what a unit-tagged label means, written into the variant's description
UNIT_NOTE = {"threshold_V": " (in volts: for recordings stored in V, e.g. M2, M2_aug)",
             "threshold_mV": " (in millivolts: for recordings stored in mV, e.g. L_LM, Schizophyllum, Dwij)"}


def describe(row):
    return (f"{MARK} RQ4 sweep variant of {row['base']['name']} (template {row['base']['id']}): "
            f"{row['param']} = {row['value']} on {' and '.join(row['targets'])}{UNIT_NOTE.get(row['label'], '')}; "
            f"the base has {row['base_value']}. Written by scripts/create_rq4_variants.py.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=DEFAULT_URL, help=f"the bridge (default {DEFAULT_URL})")
    ap.add_argument("--apply", action="store_true", help="write (without it: a dry run that writes nothing)")
    ap.add_argument("--allow-project", action="store_true",
                    help="allow --apply against a bridge in PROJECT mode (the real database)")
    ap.add_argument("--remove", action="store_true", help="delete the variants this script wrote instead")
    args = ap.parse_args(argv)

    try:
        rt = call(args.url, "GET", "/api/runtime")
        mode = rt.get("mode")
        print(f"bridge {args.url}: MODE = {str(mode).upper()}, database {rt.get('db_path')}")
        if args.apply and mode != "sandbox" and not args.allow_project:
            print(f"refused: --apply against a {mode} bridge writes to that database. "
                  f"Dry-run first, then add --allow-project to write to it on purpose.")
            return 2
        templates = call(args.url, "GET", "/api/templates")
        rows, problems = plan(args.url, templates)
    except BridgeError as e:
        print(f"error: {e}")
        return 1

    for p in problems:
        print(f"  ! {p}")

    if args.remove:
        doomed = [r["existing"] for r in rows if r["existing"] and not r["existing"].get("builtin")
                  and MARK in (r["existing"].get("description") or "")]
        print(f"{len(doomed)} variant template(s) written by this script are present")
        for t in doomed:
            if args.apply:
                call(args.url, "DELETE", f"/api/templates/{t['id']}")
                print(f"  deleted  {t['id']:5d}  {t['name']}")
            else:
                print(f"  would delete  {t['id']:5d}  {t['name']}")
        return 0

    todo = [r for r in rows if not r["is_base"] and not r["existing"]]
    print(f"\n{'variant':52s} {'value':>9s}  {'base':>9s}  status")
    for r in rows:
        if r["is_base"]:
            status = "skip: the base template is this value"
        elif r["existing"]:
            status = f"skip: already present (id {r['existing']['id']})"
        else:
            status = "create" if args.apply else "would create"
        print(f"{r['name']:52s} {r['value']:>9g}  {str(r['base_value']):>9s}  {status}")
    print(f"\n{len(todo)} to create, {sum(r['is_base'] for r in rows)} are the base, "
          f"{sum(bool(r['existing']) for r in rows)} already present, {len(problems)} note(s)")
    if not args.apply:
        print("dry run: nothing written. Add --apply to write.")
        return 1 if any(not p.startswith("note:") for p in problems) else 0

    made = 0
    for r in todo:
        try:
            out = call(args.url, "POST", "/api/templates",
                       {"name": r["name"], "steps": r["steps"], "kind": r["base"].get("kind"),
                        "description": describe(r)})
        except BridgeError as e:
            print(f"  ! {r['name']}: {e}")
            continue
        made += 1
        print(f"  created  {out['id']:5d}  {r['name']}")
    print(f"{made} of {len(todo)} created")
    return 0 if made == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
