"""One renderer: a report dict as Markdown, as HTML, and as a snapshot directory.

The Markdown and the HTML are built from the same sections and tables, so the
file the researcher pastes into the thesis and the page the app shows say the
same thing. The HTML carries no script: the app renders it in a container,
and the browser's print saves it as PDF.

* ``report_html(report, inline=True)`` — the figures as data URIs (the live
  page, nothing written to disk);
* ``write_report(report, out_dir)`` — ``report.md``, ``report.html`` (its
  ``<img>`` tags name the PNG files beside it) and every ``fig-NN-*.png``.
"""
from __future__ import annotations

import base64
import html as _html
import os

from .formatting import md_table

STYLE = """
.ub-report { font-family: "Segoe UI", system-ui, sans-serif; color: #1f2933; max-width: 980px; line-height: 1.45; }
.ub-report h1 { font-size: 20px; margin: 0 0 4px; }
.ub-report h2 { font-size: 16px; margin: 26px 0 8px; border-bottom: 1px solid #d5dbe3; padding-bottom: 4px; }
.ub-report .ub-sub { color: #5b6572; font-size: 12px; margin: 0 0 12px; }
.ub-report .ub-plain { background: #eef5ff; border-left: 3px solid #0a84ff; padding: 8px 12px; font-size: 13px; }
.ub-report figure { margin: 8px 0 12px; }
.ub-report figure img { max-width: 100%; height: auto; border: 1px solid #e3e7ed; }
.ub-report figcaption { font-size: 12px; color: #5b6572; margin-top: 4px; }
.ub-report table { border-collapse: collapse; font-size: 12px; margin: 8px 0; }
.ub-report th, .ub-report td { border: 1px solid #d5dbe3; padding: 3px 7px; text-align: left; vertical-align: top; }
.ub-report th { background: #f4f6f9; }
.ub-report .ub-caption { font-size: 12px; font-weight: 600; margin: 10px 0 2px; }
.ub-report ol.ub-notes { font-size: 12px; color: #3d4752; padding-left: 20px; }
@media print { .ub-report h2 { break-after: avoid; } .ub-report figure, .ub-report table { break-inside: avoid; } }
"""


def _bold(text: str) -> str:
    """`**x**` → <b>x</b> in an already-escaped string (the only Markdown the notes use)."""
    parts = text.split("**")
    return "".join(f"<b>{p}</b>" if i % 2 else p for i, p in enumerate(parts))


def to_markdown(report) -> str:
    out = [f"# {report['title']}", "", f"_{report['subtitle']}_", "", report.get("plain") or "", ""]
    for i, sec in enumerate(report["sections"], start=1):
        out += [f"## {i}. {sec['heading']}", ""]
        if sec.get("figure"):
            out += [f"![{sec.get('caption') or sec['heading']}]({sec['figure']})", ""]
            if sec.get("caption"):
                out += [f"*{sec['caption']}*", ""]
        for t in sec.get("tables") or []:
            if t.get("caption"):
                out += [f"**{t['caption']}**", ""]
            out += [md_table(t["headers"], t["rows"]), ""]
        notes = sec.get("notes") or []
        for k, note in enumerate(notes, start=1):
            out.append(f"{k}. {note}")
        if notes:
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def _table_html(t) -> str:
    esc = _html.escape
    head = "".join(f"<th>{esc(str(h))}</th>" for h in t["headers"])
    body = "".join("<tr>" + "".join(f"<td>{_bold(esc(str(c)))}</td>" for c in r) + "</tr>" for r in t["rows"])
    cap = f'<div class="ub-caption">{esc(t["caption"])}</div>' if t.get("caption") else ""
    return f'{cap}<table data-table="{esc(t["id"])}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def report_fragment(report, *, inline=True) -> str:
    """The report's body as one ``<div class="ub-report">`` with its own style —
    what the app puts in a container (no script, no iframe)."""
    esc = _html.escape
    pngs = dict(report["figures"])
    parts = [f"<style>{STYLE}</style>", f"<h1>{esc(report['title'])}</h1>",
             f'<p class="ub-sub">{esc(report["subtitle"])}</p>']
    if report.get("plain"):
        parts.append(f'<p class="ub-plain">{esc(report["plain"])}</p>')
    for i, sec in enumerate(report["sections"], start=1):
        parts.append(f"<h2>{i}. {esc(sec['heading'])}</h2>")
        name = sec.get("figure")
        if name:
            src = ("data:image/png;base64," + base64.b64encode(pngs[name]).decode("ascii")) if inline else name
            cap = f"<figcaption>{esc(sec['caption'])}</figcaption>" if sec.get("caption") else ""
            parts.append(f'<figure><img src="{src}" alt="{esc(sec.get("caption") or sec["heading"])}" '
                         f'data-figure="{esc(name)}" />{cap}</figure>')
        for t in sec.get("tables") or []:
            parts.append(_table_html(t))
        notes = sec.get("notes") or []
        if notes:
            parts.append('<ol class="ub-notes">' + "".join(f"<li>{_bold(esc(n))}</li>" for n in notes) + "</ol>")
    return f'<div class="ub-report" data-report-kind="{esc(report["kind"])}">' + "".join(parts) + "</div>"


def report_html(report, *, inline=True) -> str:
    """A whole HTML document around the fragment, for opening in a tab and printing."""
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{_html.escape(report['title'])}</title>"
            "<style>body { background: #ffffff; margin: 24px; }</style></head><body>"
            + report_fragment(report, inline=inline) + "</body></html>\n")


def write_report(report, out_dir) -> dict:
    """Write the snapshot: ``report.md``, ``report.html`` and every figure, into
    ``out_dir`` (created). Returns the paths written."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {"dir": out_dir, "figures": []}
    for name, data in report["figures"]:
        p = os.path.join(out_dir, name)
        with open(p, "wb") as f:
            f.write(data)
        paths["figures"].append(p)
    paths["markdown"] = os.path.join(out_dir, "report.md")
    with open(paths["markdown"], "w", encoding="utf-8", newline="\n") as f:
        f.write(report["markdown"])
    paths["html"] = os.path.join(out_dir, "report.html")
    with open(paths["html"], "w", encoding="utf-8", newline="\n") as f:
        f.write(report_html(report, inline=False))
    return paths
