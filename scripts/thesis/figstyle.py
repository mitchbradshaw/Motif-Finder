"""One look for every thesis figure (5 Nov): sizes, fonts, line weights and the species colours.

Colours follow the species (and, within a species, the strain or recording), never a figure's own order:
oyster blue, lion's mane orange, reishi green, chocolate oyster brown, Asian shiitake violet, snow oyster pink. The six
were checked as a categorical palette for colour-blind separation (the dataviz skill's validator, light mode): every
adjacent pair passes; the green and pink are below 3:1 contrast on white, so where they appear they carry a direct
label too.

    import figstyle as fs
    fs.apply()
    fig, ax = fs.figure(width="full", height=2.6)
    ax.plot(t, x, color=fs.colour("M2_aug"))
    fs.save(fig, "ch6_ladder")          # -> docs/thesis/figures/new/ch6_ladder.pdf (+ .png preview)
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "docs", "thesis", "figures", "new")

TEXT_WIDTH_IN = 6.3      # A4 with 2.5 cm margins: 16 cm
INK = "#1b1b1a"
INK_2 = "#52514e"
MUTED = "#8a8985"
GRID = "#e4e3df"
NEUTRAL = "#9a9893"      # "rejected", "other", nulls

SPECIES_COLOUR = {
    "oyster": "#2a78d6",
    "lion's mane": "#eb6834",
    "reishi": "#1baf7a",
    "chocolate oyster": "#a4511c",
    "Asian shiitake": "#6250d6",
    "snow oyster": "#e87ba4",
}

# recording -> (strain, colour). Two recordings of one strain get two shades of its hue.
RECORDINGS = {
    "M2_aug": ("oyster", "#2a78d6"),
    "M2_concat": ("oyster", "#164b8f"),
    "M4": ("oyster", "#7fb0ea"),
    "CO": ("chocolate oyster", "#a4511c"),
    "SO": ("snow oyster", "#e87ba4"),
    "LM": ("lion's mane", "#eb6834"),
    "MJu26a": ("lion's mane", "#b33f12"),
    "SH": ("Asian shiitake", "#6250d6"),
    "F2A": ("reishi", "#1baf7a"),
}

# every name a recording goes by in the data files -> its thesis name
ALIASES = {
    "M2_aug": "M2_aug", "M2_aug_concat_fs1": "M2_aug", "M2_aug_concat_fs1.mat": "M2_aug", "M2_aug_fs1": "M2_aug",
    "M2_concat": "M2_concat", "M2_concat_fs1": "M2_concat", "M2_concat_fs1.mat": "M2_concat", "M2_fs1": "M2_concat",
    "M4": "M4", "M4_aug_concat_fs1": "M4", "M4_aug_concat_fs1.mat": "M4",
    "CO": "CO", "CO_fs2": "CO", "CO_fs2.mat": "CO",
    "LM": "LM", "LM_fs2": "LM", "LM_fs2.mat": "LM",
    "SH": "SH", "SH_fs2": "SH", "SO": "SO", "SO_fs2": "SO",
    "MJu26a": "MJu26a", "MJu26a_fs2": "MJu26a",
    "L_LM_fs2": "MJu26a", "L_LM_10Hz": "MJu26a", "L_LM_Jul_26_J_raw_fs2": "MJu26a", "L_LM_Jul_26_J_raw": "MJu26a",
    "Mushroom_260720": "MJu26a", "Fig2A": "F2A", "Fig2A_dt0p1": "F2A", "F2A": "F2A",
}

# how a recording is written in a figure; the five-channel copy keeps its channels so it is never mistaken for MJu26a
LABEL = {"L_LM_fs2": "MJu26a (CH10, 13–16)", "L_LM_Jul_26_J_raw_fs2": "MJu26a (CH10, 13–16)",
         "L_LM_10Hz": "MJu26a (CH10, 13–16)", "Mushroom_260720": "MJu26a CH14 (4 h)"}


def name(rec: str) -> str:
    """The thesis name of a recording, from any of its file or table names."""
    if rec in ALIASES:
        return ALIASES[rec]
    stem = rec.rsplit(".", 1)[0]
    if stem in ALIASES:
        return ALIASES[stem]
    for k in sorted(ALIASES, key=len, reverse=True):   # table keys carry a hash suffix: CO_fs2_d8362297
        if stem.startswith(k):
            return ALIASES[k]
    return rec


def label(rec: str) -> str:
    stem = rec.rsplit(".", 1)[0]
    for k in sorted(LABEL, key=len, reverse=True):
        if stem == k or stem.startswith(k + "_"):
            return LABEL[k]
    return name(rec)


CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#e87ba4", "#a4511c"]   # non-species series, in this order


def colour(rec: str) -> str:
    return RECORDINGS.get(name(rec), (None, NEUTRAL))[1]


def species_colour(strain: str) -> str:
    return SPECIES_COLOUR.get(strain, NEUTRAL)


def apply():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "axes.linewidth": 0.8,
        "axes.edgecolor": INK_2,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "text.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "lines.linewidth": 1.5,
        "lines.markersize": 5,
        "patch.linewidth": 0.8,
        "legend.frameon": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "pdf.fonttype": 42,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })


def figure(width="full", height=2.6, nrows=1, ncols=1, **kw):
    w = {"full": TEXT_WIDTH_IN, "wide": TEXT_WIDTH_IN * 0.85, "half": TEXT_WIDTH_IN * 0.49}.get(width, width)
    return plt.subplots(nrows, ncols, figsize=(w, height), **kw)


def save(fig, stem: str, png=True):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, stem + ".pdf"))
    if png:
        fig.savefig(os.path.join(OUT, stem + ".png"), dpi=150)
    plt.close(fig)
    return os.path.join(OUT, stem + ".pdf")
