"""
rose_reference.py
=================
What 45° means on a rose (fixup-AE item 5; `QUESTIONS.md` Round 10, "Rose
reference — A: the thesis rule, restricted to accepted motifs").

**The reference** is the median steepest slope (|``max_slope_mv_s``|, the
event-shape measure every rose is drawn from) over **human-accepted Library
motifs** — accepted by the one verdict resolver (`Working/library/verdicts.py`
over `divergence.resolve_spans`) — so sharp noise and artifacts do not skew
it. The thesis figures used the pooled median over everything
(`Pipelines/drop_motifs/store11.py:175`); the researcher restricted it.

**The fallback.** Until at least N motifs are accepted (Settings › Analysis
defaults ``rose.min_accepted``, default 30) it is the median over every Library
motif **above its dataset's noise floor** (`view_filter`), and the population
is printed beside every rose. It is never silently `gradients.py:89`'s
1.0 mV/s: with nothing measured there is no reference, and the caller says so.

**Stored, not live.** ``compute`` reads; ``recompute`` stores the value with the
population it came from (n, date) as Settings › Analysis defaults keys — an
explicit act, so a rose drawn today and one drawn next week use the same 45°
unless someone chose to move it. ``current`` returns the stored value, or a
computed one marked ``stored: False`` when nothing has been stored yet.

Headless: plain SQL, no UI import (rule 1).
"""

from __future__ import annotations

import datetime
import math

import numpy as np

SETTINGS_PAGE = "analysis-defaults"
VALUE_KEY = "rose.reference_mv_s"
POPULATION_KEY = "rose.reference_population"
N_KEY = "rose.reference_n"
COMPUTED_AT_KEY = "rose.reference_computed_at"
MIN_ACCEPTED_KEY = "rose.min_accepted"
DEFAULT_MIN_ACCEPTED = 30

POP_ACCEPTED = "accepted"
POP_ABOVE_FLOOR = "above_floor"
POP_STATED = "stated"

FIELD = "max_slope_mv_s"

#: `interrogation.event_shape`'s `rose_reference_mv_s` default: 0 = this module's reference.
USE_STORED = 0.0

#: The database `resolve` reads when it is handed no connection. None — a headless run, a cluster job —
#: means there is no Library to read, and the rose says so. The web bridge points it at the database it
#: serves (its sandbox copy, or the real file in project mode), the way it redirects the step cache: an
#: adapter defaulting to `schema.DB_PATH` would read the REAL database under a sandbox bridge.
DB_PATH = None


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _min_accepted(conn):
    from Working.registration.settings import get_settings
    v = get_settings(conn, SETTINGS_PAGE).get(MIN_ACCEPTED_KEY)
    try:
        v = int(v)
    except (TypeError, ValueError):
        return DEFAULT_MIN_ACCEPTED
    return v if v >= 1 else DEFAULT_MIN_ACCEPTED


def population_text(population, n, min_accepted=None, n_accepted=None, value=None, computed_at=None, stored=True):
    if value is None:
        return "no reference: no Library motif has a measured steepest slope"
    what = {POP_ACCEPTED: f"median steepest slope over human-accepted Library motifs, n = {n}",
            POP_ABOVE_FLOOR: (f"fallback: median steepest slope over all Library motifs above the noise floor, n = {n} "
                              f"(only {n_accepted or 0} accepted; {min_accepted} needed)"),
            POP_STATED: "stated by hand for this run"}.get(population, str(population))
    when = f" · computed {computed_at[:10]}" if computed_at else ""
    return f"45° = {value:.3g} mV/s · {what}{when}" + ("" if stored else " · not stored yet (Settings › Analysis defaults)")


def compute(conn, *, min_accepted=None) -> dict:
    """The reference now, without storing it."""
    from Working.library import verdicts as V
    from Working.library import view_filter as VF
    from Working.library import features as F
    min_accepted = int(min_accepted) if min_accepted is not None else _min_accepted(conn)
    members = [{"member_id": r[0], "entry_id": r[1], "recording_id": r[2], "start_idx": r[3], "end_idx": r[4]}
               for r in conn.execute("SELECT id, entry_id, recording_id, start_idx, end_idx FROM motif_member")]
    entries = {int(r[0]): r[1] for r in conn.execute("SELECT id, content_hash FROM motif_entry")}
    hashes = sorted({h for h in entries.values() if h})
    feats = F.read_features(conn, hashes) if hashes else {}
    # the slope was measured on the store's snippet (samples x 1000, "mV" only for a volts file): converted by
    # the recording's declared unit, and left out where none is declared
    measures = VF.member_measures(conn, members) if members else {}

    def slope(m):
        v = feats.get(entries.get(int(m["entry_id"] or 0)), {}).get(FIELD)
        k = measures[int(m["member_id"])]["store_to_mv"]
        try:
            v = abs(float(v)) * k
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) and v > 0 else None

    accepted_ids = V.accepted(V.member_verdicts(conn, members)) if members else set()
    acc = [s for m in members if int(m["member_id"]) in accepted_ids for s in [slope(m)] if s is not None]
    if len(acc) >= min_accepted:
        pop, vals = POP_ACCEPTED, acc
    else:
        pop = POP_ABOVE_FLOOR
        vals = [s for m in members if measures[int(m["member_id"])]["status"] == VF.ABOVE for s in [slope(m)] if s is not None]
    value = float(np.median(vals)) if vals else None
    out = {"value_mv_s": value, "population": pop, "n": len(vals), "n_accepted": len(acc),
           "min_accepted": min_accepted, "field": FIELD, "computed_at": None, "stored": False}
    out["text"] = population_text(pop, len(vals), min_accepted, len(acc), value, stored=False)
    return out


def recompute(conn, *, actor="this installation") -> dict:
    """Compute and STORE the reference with its population (the explicit act)."""
    from Working.registration.settings import put_settings
    r = compute(conn)
    r["computed_at"] = _now()
    put_settings(conn, SETTINGS_PAGE, {VALUE_KEY: r["value_mv_s"], POPULATION_KEY: r["population"], N_KEY: r["n"],
                                       COMPUTED_AT_KEY: r["computed_at"]}, actor=actor)
    conn.commit()
    r["stored"] = True
    r["text"] = population_text(r["population"], r["n"], r["min_accepted"], r["n_accepted"], r["value_mv_s"],
                                r["computed_at"])
    return r


def current(conn) -> dict:
    """The stored reference; else the computed one, marked not stored. Reading never writes."""
    from Working.registration.settings import get_settings
    s = get_settings(conn, SETTINGS_PAGE)
    if s.get(COMPUTED_AT_KEY):
        v = s.get(VALUE_KEY)
        value = float(v) if v is not None else None
        out = {"value_mv_s": value, "population": s.get(POPULATION_KEY), "n": int(s.get(N_KEY) or 0),
               "min_accepted": _min_accepted(conn), "n_accepted": None, "field": FIELD,
               "computed_at": s.get(COMPUTED_AT_KEY), "stored": True}
        out["text"] = population_text(out["population"], out["n"], out["min_accepted"], None, value, out["computed_at"])
        return out
    return compute(conn)


def resolve(value, *, conn=None) -> dict:
    """What a rose's 45° is: ``USE_STORED`` (0) reads `current`; any other number is
    stated by hand and says so. Opens the configured database when no ``conn`` is
    given (the bridge points it at its sandbox copy)."""
    v = float(value) if value is not None else USE_STORED
    if v != USE_STORED:
        return {"value_mv_s": v, "population": POP_STATED, "n": None, "stored": False, "field": FIELD,
                "computed_at": None, "text": population_text(POP_STATED, None, value=v)}
    own = conn is None
    if own:
        if DB_PATH is None:
            return {"value_mv_s": None, "population": None, "n": 0, "stored": False, "field": FIELD,
                    "computed_at": None, "text": "no Library database to read the rose reference from"}
        from Working.database.schema import get_connection
        conn = get_connection(DB_PATH)
    try:
        return current(conn)
    finally:
        if own:
            conn.close()
