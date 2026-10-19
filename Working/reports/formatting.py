"""The Discovery page's own way of printing a number, in Python.

A report's table must read exactly what the page reads, so each cell here is a
port of the client's formatter for it (`discovery/RunsPage.tsx` `Scoreboard`,
`discovery/Precision.tsx` `PrecisionFigureLine`). JavaScript's `toFixed` and
`Math.round` round a half UP on the exact binary value; Python's `format`
rounds it to even, so `fixed` goes through `Decimal` to agree with the page
(0.625 prints 0.63 on both).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

#: the scoreboard's columns after the run/channel name, in the page's order
SCORE_COLUMNS = ("found", "judged", "reviewed", "interesting", "precision", "recall", "nullExpects", "xNull")
SCORE_HEADERS = ("found", "already judged", "reviewed", "interesting", "precision",
                 "recall · reviewed overlap", "null expects / draws", "× null")

#: what each column means — the page's InfoTip, as footnotes. The *reviewed*
#: rule and the matching rule are not copied here: they come from the server's
#: payload (`reviewedCriterion`, `rule`) and are printed beside these.
SCORE_DEFINITIONS = {
    "found": "detections this run made on the channel, inside the section.",
    "already judged": "detections that already carried a human verdict before the run started.",
    "reviewed": "detections a human verdict covers, by the rule below.",
    "interesting": "the reviewed detections whose covering verdict is a yes (interesting or seed).",
    "precision": ("containment: interesting ÷ reviewed, with yes/judged beside it; extent: the share whose extent "
                  "agrees with an event-shaped human row under the matching rule. Precision alone rewards timidity."),
    "recall · reviewed overlap": ("the share of the human yes-verdicts the run found, over the channel's reviewed "
                                  "hours; the total row states the hours it pooled."),
    "null expects / draws": ("the mean count the paired surrogate (null) runs found on the same scope, over the "
                             "number of draws per channel."),
    "× null": "found ÷ null expects. A null that found nothing leaves it empty: there is no ratio to take.",
}


def fixed(value, places: int) -> str:
    """`Number.prototype.toFixed`: half up on the exact value."""
    q = Decimal(1).scaleb(-places)
    return str(Decimal(float(value)).quantize(q, rounding=ROUND_HALF_UP))


def js_round(value) -> int:
    """`Math.round` for the values a report prints (non-negative ratios)."""
    return int(Decimal(float(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def js_num(value) -> str:
    """`String(n)` for a JSON number: shortest round-trip digits, no '.0' on a whole number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    v = float(value)
    return str(int(v)) if v.is_integer() and abs(v) < 1e21 else repr(v)


def percent(value) -> str:
    return f"{js_round(float(value) * 100)} %"


def precision_figure(f, short: str) -> str | None:
    """`PrecisionFigureLine` as text: '<short> 75 % (3/4)' or '<short> — nothing judged'."""
    if not f:
        return None
    if f.get("value") is None:
        return f"{short} — nothing judged"
    return f"{short} {percent(f['value'])} ({f['yes']}/{f['judged']})"


def precision_cell(row) -> str:
    if row.get("note") and row.get("precision") is None:
        return str(row["note"])
    pr = row.get("precisions")
    if not pr:
        return row.get("precisionNote") or "not yet scored"
    parts = [precision_figure(pr.get("containment"), "containment"), precision_figure(pr.get("extent"), "extent")]
    parts = [p for p in parts if p]
    return " · ".join(parts) if parts else "—"


def recall_cell(recall) -> str:
    """`fmtRecall`."""
    if recall is None:
        return "—"
    if "value" in recall:
        return f"{fixed(recall['value'], 2)} over {js_num(recall['overH'])} h"
    if "none" in recall:
        return "no reviewed overlap"
    return f"{recall.get('tooFewH')} h · too few"


def null_cell(row) -> str:
    if row.get("nullRun") is False:
        return "no null run"
    out = js_num(row.get("nullExpects"))
    draws, most = row.get("nullDraws"), row.get("nullDrawsMax")
    if draws:
        span = f"{draws}–{most}" if most and most != draws else f"{draws}"
        word = "draw" if draws == 1 and (most or 1) == 1 else "draws"
        out += f" / {span} {word}"
    return out


def x_null_cell(row) -> str:
    if row.get("xNull") is None:
        return row.get("xNullNote") or "—"
    return f"{fixed(row['xNull'], 1)}×"


def score_cells(row) -> dict:
    """One scoreboard row (the route's `_score_row` shape) as the page prints its cells."""
    return {
        "found": str(row["found"]), "judged": str(row["judged"]), "reviewed": str(row["reviewed"]),
        "interesting": str(row["interesting"]), "precision": precision_cell(row),
        "recall": recall_cell(row.get("recall")), "nullExpects": null_cell(row), "xNull": x_null_cell(row),
    }


def md_cell(text) -> str:
    """A value safe inside a Markdown table cell."""
    return str("" if text is None else text).replace("|", "\\|").replace("\n", " ")


def md_table(headers, rows) -> str:
    """GitHub-flavoured Markdown: a header row, the rule, one line per row."""
    out = ["| " + " | ".join(md_cell(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(md_cell(c) for c in r) + " |")
    return "\n".join(out)


def hours(h) -> str:
    """Hours as the report prints a time: '1.25 h', or minutes under an hour."""
    h = float(h)
    return f"{h:.2f} h" if h >= 1 else f"{h * 60:.1f} min"


def slice_labels(total_h, n) -> list[str]:
    """'0–90 h', '90–180 h' … for ``n`` equal slices of ``total_h`` hours, with
    as many decimals as the slice width needs to tell the slices apart."""
    step = float(total_h) / n if n else 0.0
    places = 0 if step >= 10 else 1 if step >= 1 else 2
    return [f"{i * step:.{places}f}–{(i + 1) * step:.{places}f} h" for i in range(n)]
