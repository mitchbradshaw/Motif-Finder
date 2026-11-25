"""Chapter 3 summary of the drop-motif study's resolution and species claims.

Replaces two internal analysis sheets (SPECIES_vs_RESOLUTION.png, DECODE_species.png) with one figure drawn
from the numbers in Plots/drop_motifs10/CLAIMS.md (rows 6-9 and 12-15). No new computation: every value below
is copied from that ledger, with its row number beside it.

    python scripts/thesis/fig_drop_claims.py   ->  docs/thesis/figures/new/ch3_drop_claims.pdf
"""
import numpy as np

import figstyle as fs

# Cramer's V of family membership against species and against samples per event, with the permutation-null medians.
ASSOC = [  # label, V species, V samples, null species, null samples, n, CLAIMS row
    ("oyster vs lion's mane\nexcerpt, matched rate\nand framing", 0.0873, 0.2768, 0.0527, 0.0581, 830, 6),
    ("matched-rate subset", 0.2327, 0.3181, 0.0498, 0.0506, 1086, 7),
    ("all four corpora", 0.2495, 0.2498, 0.0275, 0.0281, 3511, 8),
]
# Balanced accuracy of decoding a label from a representation of each event, with chance.
DECODE = [  # label, value, chance, CLAIMS row
    ("samples per event,\nfrom normalised shape", 0.753, 0.250, 9),
    ("species, from\nabsolute scale", 0.781, 0.333, 12),
    ("species, from\nnormalised shape", 0.614, 0.333, 13),
    ("species, from one feature:\nsamples in the fall", 0.575, 0.333, 14),
    ("species, from shape\nplus scale", 0.741, 0.333, 15),
]


def main():
    fs.apply()
    fig, (a, b) = fs.plt.subplots(1, 2, figsize=(fs.TEXT_WIDTH_IN, 3.3), gridspec_kw=dict(width_ratios=[1, 1.15]))
    fig.subplots_adjust(left=0.20, right=0.985, bottom=0.21, top=0.84, wspace=0.95)

    y = np.arange(len(ASSOC))[::-1]
    h = 0.34
    sp, sa = "#4a4a46", "#bdb9b0"   # neutral: species dark, resolution light (not species colours)
    a.barh(y + h / 2, [r[1] for r in ASSOC], h, color=sp, label="species")
    a.barh(y - h / 2, [r[2] for r in ASSOC], h, color=sa, label="samples per event")
    for yi, r in zip(y, ASSOC):
        a.plot([r[3]] * 2, [yi + 0.02, yi + h + 0.02], color=fs.INK, lw=1.2)
        a.plot([r[4]] * 2, [yi - h - 0.02, yi - 0.02], color=fs.INK, lw=1.2)
        a.text(max(r[1], r[2]) + 0.012, yi, f"n = {r[5]:,}", va="center", fontsize=7, color=fs.INK_2)
    a.set_yticks(y)
    a.set_yticklabels([r[0] for r in ASSOC], fontsize=7.5)
    a.set_xlim(0, 0.42)
    a.set_xlabel("Cramér's V with family membership")
    a.set_title("(a) What family membership follows", loc="left")
    fig.legend(handles=a.get_legend_handles_labels()[0], labels=["species", "samples per event (resolution)"], loc="upper center", ncol=2, fontsize=7.5, frameon=False, bbox_to_anchor=(0.5, 1.0))
    a.text(0.0, -0.33, "black ticks: shuffled-label null medians", transform=a.transAxes, fontsize=6.5, color=fs.INK_2)

    y2 = np.arange(len(DECODE))[::-1]
    colours = [sa, sp, sp, sa, sp]
    b.barh(y2, [r[1] for r in DECODE], 0.6, color=colours)
    for yi, r in zip(y2, DECODE):
        b.plot([r[2]] * 2, [yi - 0.36, yi + 0.36], color=fs.INK, lw=1.2, ls="--")
        b.text(r[1] + 0.012, yi, f"{r[1]:.2f}", va="center", fontsize=7.5)
    b.set_yticks(y2)
    b.set_yticklabels([r[0] for r in DECODE], fontsize=7.5)
    b.set_xlim(0, 1.0)
    b.set_xlabel("balanced accuracy (dashed: chance)")
    b.set_title("(b) What can be read back from an event", loc="left")
    return fs.save(fig, "ch3_drop_claims")


if __name__ == "__main__":
    main()
