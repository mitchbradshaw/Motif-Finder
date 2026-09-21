"""Templates: named, versioned, typed chains (stage-3 prompt 01, "Templates").

A template is a row of the `templates` table — `name`, `steps_json`, a
`kind` (`detection | encoding | training | interrogation`, derived from the
chain's terminal type unless given), a `version` that increments on every
edit, `builtin` (seeded from the code below; never edited in place, copied
instead), a `description` and timestamps. The columns are additive
(`Working.database.schema._migrate_templates_columns`), so the two-column
table the core's `save_template` wrote still reads.

`CANONICAL` is the code copy of the templates the app ships with; `seed_canonical`
writes them into a database once (by name — a later start adds only what is
missing and never touches an existing row). Everything here is plain sqlite
over the core; no FastAPI, so the headless suite can test it.
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3

from Adapters.registry import discover_adapters, get_adapter

discover_adapters()

KINDS = ("detection", "encoding", "training", "interrogation")

# terminal output type -> template kind (spec §6.1: modes are consequences of the terminal type)
_KIND_BY_TERMINAL = {"spanset": "detection", "encoding": "encoding", "model": "training", "grouping": "training",
                     "windowset": "training", "scores": "detection", "signal": "detection"}


def _step(stage, algorithm, params=None, side_inputs=None):
    d = {"stage": stage, "algorithm": algorithm, "params": dict(params or {})}
    if side_inputs:
        d["side_inputs"] = side_inputs
    return d


CANONICAL: list[dict] = [
    {
        "name": "drop_detection_v1", "kind": "detection", "version": 1,
        "description": "The canonical drop detector (D1): baseline removal → five-stage encoding with the slope-noise "
                       "floor → drop detection (candidate onsets, trough, gates, windows). The decomposition of the "
                       "detector that produced the seed events in DATA/library_seed/drop_motifs5 (reproduced onset for onset on "
                       "the reference span id001 under the drop_motifs5-era flags; tests/test_template_drop_detection.py).",
        "steps": [
            _step("preprocessing", "detrend", {"mode": "rolling_mean_nearest", "window_s": 4916.67}),
            _step("detection", "stage_encoding", {"segment_seconds": 98.33, "same_fraction": 0.6, "slope_sigma": 8.0}),
            _step("detection", "drop_detection", {}),
        ],
    },
    {
        "name": "dehshibi_spikes", "kind": "detection", "version": 1,
        "description": "Dehshibi & Adamatzky 2021 as three blocks: Morse wavelet transform → Ω summation → "
                       "Algorithms 1–4. Replaces the monolithic detection.dehshibi_spikes adapter.",
        "steps": [
            _step("preprocessing", "wavelet_transform", {}),
            _step("detection", "wavelet_summation", {}),
            _step("detection", "summation_threshold", {}),
        ],
    },
    {
        "name": "mp_threshold", "kind": "detection", "version": 1,
        "description": "Baseline → matrix profile → threshold to spans.",
        "steps": [
            _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
            _step("detection", "matrix_profile", {"window_min": 1.0, "backend": "stump"}),
            _step("detection", "threshold", {"threshold": 8.0}),
        ],
    },
    {
        "name": "mp_motifs", "kind": "detection", "version": 1,
        "description": "Baseline → matrix profile → motif groups (seed + nearest neighbours, labelled by group).",
        "steps": [
            _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
            _step("detection", "matrix_profile", {"window_min": 1.0, "backend": "stump"}),
            _step("detection", "mp_motifs", {"max_motifs": 5, "n_neighbors": 3}),
        ],
    },
    {
        "name": "dsax_encoding", "kind": "encoding", "version": 1,
        "description": "Baseline → symbolic encoding (dSAX, alphabet 3).",
        "steps": [
            _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
            _step("detection", "sax_dsax", {"seconds_per_symbol": 20.0, "alphabet_size": 3}),
        ],
    },
    {
        "name": "symbol_search", "kind": "detection", "version": 1,
        "description": "Baseline → dSAX letters → regular-expression search over the symbol string (D2).",
        "steps": [
            _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
            _step("detection", "sax_dsax", {"seconds_per_symbol": 20.0, "alphabet_size": 3}),
            _step("detection", "symbol_search", {"pattern": "c+a+"}),
        ],
    },
    {
        "name": "windows_model", "kind": "training", "version": 1,
        "description": "Sliding windows + features → hierarchical cluster → classifier (the training chain).",
        "steps": [
            _step("preprocessing", "window_matrix", {"window_min": 1.0, "slow_entropy": False}),
            _step("catalogue", "cluster", {"k": 3}),
            _step("catalogue", "classifier", {"n_estimators": 50},
                  side_inputs={"windows": {"source_kind": "earlier_step", "step_index": 0}}),
        ],
    },
    {
        "name": "cnn_detection", "kind": "detection", "version": 1,
        "description": "Sliding windows (blocked split) → window images (fusion) → CNN score → threshold to spans: "
                       "detecting with a trained model (D2; the image stack + window set → Scores form of spec §6.8's model stage).",
        "steps": [
            _step("preprocessing", "sliding_windows", {"window_s": 600.0}),
            _step("catalogue", "window_images", {"image_type": "fusion", "img_size": 224}),
            _step("catalogue", "cnn_score", {}, side_inputs={"windows": {"source_kind": "earlier_step", "step_index": 0}}),
            _step("detection", "threshold", {"threshold": 0.5}),
        ],
    },
    {
        "name": "gramian_gasf", "kind": "encoding", "version": 1,
        "description": "Baseline → Gramian GASF image (needs a span ≤ 5000 samples).",
        "steps": [
            _step("preprocessing", "detrend", {"mode": "rolling_mean", "window_s": 600.0}),
            _step("catalogue", "gramian_gasf", {}),
        ],
    },
]


def canonical(name: str) -> dict:
    """A deep copy of one canonical template by name (KeyError if unknown)."""
    for t in CANONICAL:
        if t["name"] == name:
            return json.loads(json.dumps(t))
    raise KeyError(f"no canonical template named {name!r}; have {[t['name'] for t in CANONICAL]}")


def kind_for_steps(steps) -> str:
    """The template kind a chain's terminal type implies (spec §6.1)."""
    if not steps:
        return "detection"
    last = steps[-1]
    spec = get_adapter(f"{last['stage']}.{last['algorithm']}")
    return _KIND_BY_TERMINAL.get(spec.output_kind, "detection")


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def _dumps(steps):
    return json.dumps(steps, sort_keys=True, separators=(",", ":"))


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["steps"] = json.loads(d.pop("steps_json"))
    d["builtin"] = bool(d.get("builtin") or 0)
    d["version"] = int(d.get("version") or 1)
    d["kind"] = d.get("kind") or kind_for_steps(d["steps"])
    return d


def list_all(conn) -> list[dict]:
    return [_row(r) for r in conn.execute("SELECT * FROM templates ORDER BY builtin DESC, id")]


def get(conn, template_id: int) -> dict:
    r = conn.execute("SELECT * FROM templates WHERE id = ?", (int(template_id),)).fetchone()
    if r is None:
        raise KeyError(f"no template with id={template_id}")
    return _row(r)


def save(conn, name: str, steps, *, kind: str | None = None, description: str = "", builtin: bool = False) -> int:
    kind = kind or kind_for_steps(steps)
    if kind not in KINDS:
        raise ValueError(f"template kind must be one of {KINDS}, got {kind!r}")
    now = _now()
    cur = conn.execute(
        "INSERT INTO templates (name, steps_json, kind, version, builtin, description, created_at, updated_at) "
        "VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
        (str(name), _dumps(steps), kind, 1 if builtin else 0, str(description or ""), now, now))
    conn.commit()
    return int(cur.lastrowid)


def update(conn, template_id: int, *, steps=None, name: str | None = None, description: str | None = None) -> dict:
    """Edit a saved copy in place; the version increments. A builtin row is refused —
    copy it first (`save`), then edit the copy."""
    row = get(conn, template_id)
    if row["builtin"]:
        raise PermissionError(f"template {template_id} ({row['name']}) is builtin; save a copy to edit it")
    fields, values = ["version = ?", "updated_at = ?"], [row["version"] + 1, _now()]
    if steps is not None:
        fields.append("steps_json = ?"); values.append(_dumps(steps))
        fields.append("kind = ?"); values.append(kind_for_steps(steps))
    if name is not None:
        fields.append("name = ?"); values.append(str(name))
    if description is not None:
        fields.append("description = ?"); values.append(str(description))
    values.append(int(template_id))
    conn.execute(f"UPDATE templates SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    return get(conn, template_id)


def delete(conn, template_id: int) -> None:
    row = get(conn, template_id)
    if row["builtin"]:
        raise PermissionError(f"template {template_id} ({row['name']}) is builtin and cannot be deleted")
    conn.execute("DELETE FROM templates WHERE id = ?", (int(template_id),))
    conn.commit()


def seed_canonical(conn) -> int:
    """Insert every canonical template whose name is not yet in the table.
    Returns how many rows were written (0 on every start after the first)."""
    have = {r[0] for r in conn.execute("SELECT name FROM templates")}
    n = 0
    for t in CANONICAL:
        if t["name"] in have:
            continue
        save(conn, t["name"], t["steps"], kind=t["kind"], description=t["description"], builtin=True)
        n += 1
    return n
