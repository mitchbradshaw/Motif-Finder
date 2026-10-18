"""The report's figures, each drawn with matplotlib and returned as PNG bytes.

The Agg canvas is used directly (`matplotlib.figure.Figure` +
`FigureCanvasAgg`), never `pyplot`: pyplot keeps global state and picks a
backend for the whole process, and the bridge renders reports from worker
threads. Every figure draws numbers it is handed — the pages' own payloads —
and computes none of its own.
"""
from __future__ import annotations

import io
import math

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.patches import Patch, Rectangle

from .formatting import slice_labels

DPI = 150
#: the app's own hues (theme.css): the run blue, the human green, amber, red
BLUE = "#0a84ff"
GREEN = "#22a06b"
AMBER = "#e8900c"
RED = "#d93025"
INK = "#1f2933"
FAINT = "#d5dbe3"
NULL_HUE = "#8a94a6"
STATE_FILL = {"not_run": "#ffffff", "not_reviewed": "#ffffff", "running": "#fde7c4", "failed": "#f7c9c5",
              "discarded": "#e7dcf5"}
STATE_WORDS = {"not_run": "not run", "not_reviewed": "not reviewed", "running": "running", "failed": "failed",
               "discarded": "discarded", "covered": "covered"}


def png(fig: Figure) -> bytes:
    FigureCanvasAgg(fig)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI, facecolor="white")
    return buf.getvalue()


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(labelsize=7, colors=INK)


def _shade(hue, t):
    """`hue` blended toward white: t = 0 is white, 1 is the full hue."""
    r, g, b, _ = to_rgba(hue)
    t = max(0.0, min(1.0, t))
    return (1 - t + t * r, 1 - t + t * g, 1 - t + t * b)


def _no_data(fig, ax, text):
    ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=9, color=INK, wrap=True, transform=ax.transAxes)
    return png(fig)


# ── 1. the detection map ────────────────────────────────────────────────────

def map_figure(m) -> bytes:
    """Discovery › Map at level 2 for one recording: one panel per row (the
    human reference, then this run's row), channels down, time slices across.
    A covered cell is shaded by detections per covered hour and carries its
    count; a cell nobody looked at / no run reached is white and hatched and
    says so — "did not look" and "looked and found nothing" never share a
    shade."""
    rows, chans, n = m["rows"], m["channels"], int(m["chunks"])
    fig = Figure(figsize=(7.2, 0.5 + 0.34 * len(chans) * max(1, len(rows)) + 0.55 * len(rows)))
    if not chans or not rows:
        return _no_data(fig, fig.add_subplot(111), "no channels to map")
    axes = fig.subplots(len(rows), 1, squeeze=False)[:, 0]
    dens = [c["count"] / c["hours"] for r in rows for ch in chans for c in r["cells"].get(ch, [])
            if c.get("state") == "covered" and c.get("hours")]
    top = max(dens) if dens else 1.0
    slice_h = float(m.get("hours") or 0) / n if n else 0
    for ax, row in zip(axes, rows):
        hue = GREEN if row.get("human") else BLUE
        for j, ch in enumerate(chans):
            for i, cell in enumerate(row["cells"].get(ch, [])):
                state = cell.get("state")
                y = len(chans) - 1 - j
                if state == "covered":
                    d = cell["count"] / cell["hours"] if cell.get("hours") else 0.0
                    face = _shade(hue, 0.12 + 0.88 * (d / top if top else 0))
                    ax.add_patch(Rectangle((i, y), 1, 1, facecolor=face, edgecolor="white", linewidth=1.5))
                    dark = (0.12 + 0.88 * (d / top if top else 0)) > 0.6
                    ax.text(i + 0.5, y + 0.5, f"{cell['count']}", ha="center", va="center", fontsize=7,
                            color="white" if dark else INK)
                else:
                    ax.add_patch(Rectangle((i, y), 1, 1, facecolor=STATE_FILL.get(state, "#ffffff"),
                                           edgecolor=FAINT, hatch="///" if state in ("not_run", "not_reviewed") else None,
                                           linewidth=0.6))
                    ax.text(i + 0.5, y + 0.5, STATE_WORDS.get(state, state or ""), ha="center", va="center",
                            fontsize=5.5, color="#6b7480")
        ax.set_xlim(0, n)
        ax.set_ylim(0, len(chans))
        ax.set_yticks([len(chans) - 1 - j + 0.5 for j in range(len(chans))])
        ax.set_yticklabels(chans)
        ax.set_xticks([i + 0.5 for i in range(n)])
        ax.set_xticklabels(slice_labels(m.get("hours") or 0, n) if slice_h else [str(i + 1) for i in range(n)])
        ax.set_title(row["label"], fontsize=8, loc="left", color=hue)
        _style(ax)
        ax.tick_params(length=0)
        for side in ("left", "bottom"):
            ax.spines[side].set_visible(False)
    fig.tight_layout()
    return png(fig)


# ── 2. where the run fires ──────────────────────────────────────────────────

def fires_figure(fires, run_key, run_label) -> bytes:
    """`GET /api/discovery/fires` for the run, drawn as the page's strip: per
    channel three rows of `binH`-hour cells — this run's detections (blue),
    the human yes-verdicts (green), each shaded against its own row's busiest
    bin and labelled with its count, and the reviewed hours of each bin (pale
    green, darker = more of the bin reviewed). A bin past where an unfinished
    run has reached is marked amber."""
    chans = fires.get("channels") or []
    n = int(fires.get("nBins") or 0)
    fig = Figure(figsize=(7.2, 0.7 + 0.62 * max(1, len(chans))))
    if not chans or not n:
        return _no_data(fig, fig.add_subplot(111), "no channels")
    bin_h, first = float(fires["binH"]), int(fires["firstBin"])
    axes = fig.subplots(len(chans), 1, squeeze=False, sharex=True)[:, 0]
    label_counts = n <= 48
    for ax, ch in zip(axes, chans):
        rows = {r["run"]: r for r in ch["rows"]}
        lines = [("run", BLUE, (rows.get(run_key) or {}).get("counts") or [0] * n),
                 ("human", GREEN, (rows.get("human") or {}).get("counts") or [0] * n)]
        for y, (name, hue, counts) in zip((2, 1), lines):
            top = max(1, max(counts))
            for i, v in enumerate(counts):
                x = (first + i) * bin_h
                t = 0.08 + 0.92 * (v / top) if v else 0.0
                ax.add_patch(Rectangle((x, y), bin_h, 0.92, facecolor=_shade(hue, t) if v else "#ffffff",
                                       edgecolor=FAINT, linewidth=0.4))
                if label_counts and v:
                    ax.text(x + bin_h / 2, y + 0.46, str(v), ha="center", va="center", fontsize=5.5,
                            color="white" if t > 0.6 else INK)
        for i, rh in enumerate(ch.get("reviewed") or []):
            frac = min(1.0, float(rh) / bin_h) if bin_h else 0.0
            ax.add_patch(Rectangle(((first + i) * bin_h, 0.3), bin_h, 0.55,
                                   facecolor=_shade(GREEN, 0.12 + 0.5 * frac) if frac else "#ffffff",
                                   edgecolor=FAINT, linewidth=0.4))
        unfinished = (rows.get(run_key) or {}).get("unfinishedFrom")
        if unfinished is not None:
            ax.add_patch(Rectangle(((first + unfinished) * bin_h, 2), (n - unfinished) * bin_h, 0.92,
                                   facecolor=AMBER, alpha=0.25, edgecolor="none"))
        ax.set_xlim(first * bin_h, (first + n) * bin_h)
        ax.set_ylim(0.2, 3.0)
        ax.set_yticks([2.46, 1.46, 0.57])
        ax.set_yticklabels(["run", "human", "reviewed"], fontsize=5.5)
        ax.set_title(f"{ch['channel']} · {sum(lines[0][2])} found · {sum(lines[1][2])} human yes · "
                     f"{ch.get('reviewedH', 0):g} h reviewed", fontsize=7, loc="left", color=INK)
        _style(ax)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
    axes[-1].set_xlabel(f"hours into the recording ({bin_h:g} h bins)", fontsize=7)
    handles = [Patch(color=BLUE, label=run_label), Patch(color=GREEN, label="human yes-verdicts"),
               Patch(color=_shade(GREEN, 0.4), label="reviewed hours")]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return png(fig)


# ── 3. twelve examples ──────────────────────────────────────────────────────

def examples_figure(examples) -> bytes:
    """Each example as a small trace with the detection's span as a band,
    titled with its channel, time, score and verdict (if judged)."""
    n = len(examples)
    cols = 4
    rows = max(1, math.ceil(n / cols))
    fig = Figure(figsize=(7.2, 1.55 * rows + 0.2))
    if not n:
        return _no_data(fig, fig.add_subplot(111), "this run made no detections inside the section")
    axes = fig.subplots(rows, cols, squeeze=False).ravel()
    for k, ax in enumerate(axes):
        if k >= n:
            ax.axis("off")
            continue
        e = examples[k]
        tr = e.get("trace") or {}
        vals = np.asarray([np.nan if v is None else v for v in tr.get("values") or []], dtype=float)
        t = np.arange(len(vals)) * float(tr.get("stepS") or 1.0)
        hue = BLUE if e.get("pick") == "top" else AMBER
        if len(vals):
            ax.plot(t, vals, color=INK, linewidth=0.6)
        a, b = (tr.get("spanS") or [None, None])[:2]
        if a is not None:
            ax.axvspan(a, b, color=hue, alpha=0.18, linewidth=0)
        score = e.get("score")
        verdict = e.get("verdict") or "not judged"
        ax.set_title(f"#{k + 1} {e.get('channel')} · {e.get('atH', 0):.3f} h\n"
                     f"score {('—' if score is None else f'{score:.3g}')} · {verdict}", fontsize=6.2,
                     color=INK, loc="left")
        ax.set_xticks([])
        ax.tick_params(labelsize=5.5)
        if tr.get("unit"):
            ax.set_ylabel(tr["unit"], fontsize=5.5)
        _style(ax)
    handles = [Patch(color=_shade(BLUE, 0.4), label="top six by score"),
               Patch(color=_shade(AMBER, 0.4), label="six at random (seeded by the run key)")]
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return png(fig)


# ── 4. the null comparison ──────────────────────────────────────────────────

def null_figure(null) -> bytes:
    """A seed run: per channel, the null's match distances behind the run's
    own, with the kept cut — the Seed page's cut histogram. A template run:
    per channel, what it found beside what its paired null expects."""
    if null.get("kind") == "seed" and null.get("byChannel"):
        chans = list(null["byChannel"].items())
        cols = min(3, len(chans))
        rows = math.ceil(len(chans) / cols)
        fig = Figure(figsize=(7.2, 1.9 * rows + 0.3))
        axes = fig.subplots(rows, cols, squeeze=False).ravel()
        cut = null.get("cut")
        for k, ax in enumerate(axes):
            if k >= len(chans):
                ax.axis("off")
                continue
            name, part = chans[k]
            nd = np.asarray(part.get("null") or [], dtype=float)
            fd = np.asarray(part.get("found") or [], dtype=float)
            both = np.concatenate([nd, fd]) if len(nd) or len(fd) else np.zeros(1)
            bins = np.linspace(float(both.min()), float(both.max()) + 1e-9, 30)
            if len(nd):
                ax.hist(nd, bins=bins, color=NULL_HUE, alpha=0.45, label="null", density=True)
            if len(fd):
                ax.hist(fd, bins=bins, color=BLUE, alpha=0.8, label="this run", density=True, histtype="step",
                        linewidth=1.2)
            if cut is not None:
                ax.axvline(float(cut), color=RED, linewidth=1, label=f"kept cut d ≤ {cut:g}")
            ax.set_title(f"{name} · {len(fd)} found · null {len(nd)} distances", fontsize=7, loc="left")
            ax.set_xlabel("match distance", fontsize=6.5)
            _style(ax)
        axes[0].legend(fontsize=6, frameon=False)
        fig.tight_layout()
        return png(fig)
    rows = null.get("rows") or []
    fig = Figure(figsize=(7.2, 2.6))
    ax = fig.add_subplot(111)
    if not rows:
        return _no_data(fig, ax, null.get("missing") or "this run carries no null")
    x = np.arange(len(rows))
    found = [float(r.get("found") or 0) for r in rows]
    exp = [float(r["nullExpects"]) if r.get("nullExpects") is not None else 0.0 for r in rows]
    ax.bar(x - 0.2, found, width=0.4, color=BLUE, label="found")
    ax.bar(x + 0.2, exp, width=0.4, color=NULL_HUE, label="null expects (mean per draw)")
    for i, r in enumerate(rows):
        if r.get("xNull") is not None:
            ax.text(i, max(found[i], exp[i]) * 1.02 + 0.05, f"{r['xNull']:.1f}×", ha="center", va="bottom",
                    fontsize=6.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels([r["channel"] for r in rows], fontsize=7)
    ax.set_ylabel("detections", fontsize=7)
    ax.legend(fontsize=7, frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    _style(ax)
    fig.tight_layout()
    return png(fig)
