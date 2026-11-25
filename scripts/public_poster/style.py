"""Public poster (25 Nov 2026): one look for every figure.

Figures are drawn at their printed size (millimetres on the A1 sheet) with poster-sized type, so the poster page
places them 1:1. Species colours are the thesis palette (scripts/thesis/figstyle.py), checked there for colour-blind
separation; the poster's own purples come from the thesis poster.
"""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "docs", "public_poster_20261125")
FIG = os.path.join(OUT, "figures")
DATA = os.path.join(OUT, "data")

MM = 1 / 25.4          # inches per millimetre

# the poster's own colours (thesis poster: purple header, magenta accents, lilac section bars)
PURPLE = "#4b1d73"
PURPLE_2 = "#6d2a8f"
MAGENTA = "#a3238f"
LILAC = "#efd5f5"
INK = "#1d1a24"
INK_2 = "#4a4655"
MUTED = "#8b8696"
GRID = "#e6e1ec"
HOT = "#ff6a00"        # the one highlight colour (a drop, a fall)

SPECIES_ORDER = ["oyster", "snow oyster", "chocolate oyster", "Asian shiitake", "lion's mane"]
SPECIES_COLOUR = {
    "oyster": "#2a78d6",
    "lion's mane": "#eb6834",
    "chocolate oyster": "#a4511c",
    "Asian shiitake": "#6250d6",
    "snow oyster": "#e87ba4",
}
SPECIES_LATIN = {
    "oyster": "Pleurotus ostreatus",
    "lion's mane": "Hericium erinaceus",
    "chocolate oyster": "Pleurotus sp.",
    "Asian shiitake": "Lentinula edodes",
    "snow oyster": "Pleurotus sp.",
}
SPECIES_LABEL = {"oyster": "Oyster", "lion's mane": "Lion's mane", "chocolate oyster": "Chocolate oyster",
                 "Asian shiitake": "Shiitake", "snow oyster": "Snow oyster"}

KIND_THIN = "#00a6d6"   # CH14's thin drops
KIND_WIDE = "#e0187a"   # CH14's wide drops


def apply(base=16):
    plt.rcParams.update({
        "font.family": "Segoe UI",
        "font.size": base,
        "axes.titlesize": base + 2,
        "axes.labelsize": base,
        "xtick.labelsize": base - 2,
        "ytick.labelsize": base - 2,
        "legend.fontsize": base - 2,
        "axes.linewidth": 1.4,
        "axes.edgecolor": INK_2,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "xtick.major.width": 1.3,
        "ytick.major.width": 1.3,
        "xtick.major.size": 6,
        "ytick.major.size": 6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
    })


def figure(w_mm, h_mm):
    return plt.figure(figsize=(w_mm * MM, h_mm * MM))


def save(fig, name, dpi=300, transparent=False):
    os.makedirs(FIG, exist_ok=True)
    png = os.path.join(FIG, name + ".png")
    fig.savefig(png, dpi=dpi, transparent=transparent)
    fig.savefig(os.path.join(FIG, name + ".svg"), transparent=transparent)
    plt.close(fig)
    print("wrote", os.path.relpath(png, ROOT), flush=True)
