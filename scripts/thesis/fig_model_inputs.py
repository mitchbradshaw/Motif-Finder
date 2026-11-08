"""Vector diagram of the three classifier representations; no model is run.

The sharkfin-shaped waveform is explicitly schematic. Its four image panels
use the repository's production Gramian/recurrence encoders. The filter response
illustrates one MiniRocket-style kernel, rather than a fitted model prediction.
"""
from pathlib import Path
import sys

import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import figstyle as fs
from Working.Catalogue.gramian.gramian_calc import (
    compute_GASF, compute_GADF, compute_recurrence, compute_fusion,
)


def main():
    fs.apply()
    fs.plt.rcParams["figure.autolayout"] = False
    fig = fs.plt.figure(figsize=(fs.TEXT_WIDTH_IN, 6.0))
    blue, purple, green = fs.CATEGORICAL[0], fs.CATEGORICAL[3], fs.CATEGORICAL[2]
    t = np.linspace(0, 30, 600)
    y = np.zeros_like(t)
    rise = (t >= 6) & (t < 15)
    y[rise] = 1 - np.exp(-(t[rise] - 6) / 3.2)
    fall = t >= 15
    y[fall] = (1 - np.exp(-9 / 3.2)) * np.exp(-(t[fall] - 15) / 1.7)
    ax = fig.add_axes([0.24, 0.79, 0.52, 0.15])
    ax.plot(t, y, color=fs.INK, lw=1.6)
    ax.axvspan(5, 24, color=blue, alpha=0.10, lw=0)
    ax.set(xlabel="Time (arbitrary units)", ylabel="Relative voltage", yticks=[0, 1])
    ax.set_title("One waveform, three representations", fontsize=10)
    ax.tick_params(labelsize=7)
    ax.xaxis.label.set_size(7.5)
    ax.yaxis.label.set_size(7.5)
    centres = [0.18, 0.50, 0.82]
    colours = [blue, purple, green]
    titles = ["Image encodings", "Convolution responses", "Statistical summaries"]
    for x, colour, title in zip(centres, colours, titles):
        fig.add_artist(FancyArrowPatch((0.50, 0.715), (x, 0.685),
                       arrowstyle="-|>", mutation_scale=12, lw=1.4,
                       color=colour, transform=fig.transFigure,
                       connectionstyle="arc3,rad=0.12" if x != 0.5 else "arc3"))
        fig.text(x, 0.665, title, ha="center", fontsize=8.2, color=colour, weight="bold")
    encodings = [compute_GASF(y), compute_GADF(y), compute_recurrence(y), compute_fusion(y)]
    for i, (name, img) in enumerate(zip(["GASF", "GADF", "Recurrence", "Fusion (RGB)"], encodings)):
        x, yy = 0.05 + (i % 2) * 0.13, 0.51 - (i // 2) * 0.14
        bx = fig.add_axes([x, yy, 0.12, 0.115])
        bx.imshow(img, cmap="gray", origin="upper", interpolation="nearest")
        bx.set(xticks=[], yticks=[])
        bx.set_title(name, fontsize=6.8, pad=2)
        for spine in bx.spines.values():
            spine.set_visible(False)
    fig.text(0.18, 0.33, "Encode and resize\nto 224 × 224 pixels", ha="center", fontsize=7.5)
    # One of the 84 length-nine MiniRocket weight patterns.
    kernel = np.array([-1, -1, 2, -1, 2, -1, 2, -1, -1], dtype=float)
    kx = fig.add_axes([0.39, 0.53, 0.22, 0.08])
    kx.plot(kernel, marker="o", ms=2.7, color=purple, lw=1.2)
    kx.set(xticks=[], yticks=[])
    kx.set_title("One fixed filter", fontsize=7.5, pad=2)
    kx.grid(False)
    for spine in kx.spines.values():
        spine.set_visible(False)
    dilated = np.zeros(8 * 24 + 1)
    dilated[::24] = kernel
    response = np.convolve((y - y.mean()) / y.std(), dilated, mode="same")
    bias = float(np.quantile(response, 0.6))
    rx = fig.add_axes([0.39, 0.39, 0.22, 0.08])
    rx.plot(t, response, color=purple, lw=0.8)
    rx.axhline(bias, color=fs.INK_2, ls="--", lw=0.7)
    rx.fill_between(t, bias, response, where=response > bias, color=purple, alpha=0.3)
    rx.set(xticks=[], yticks=[])
    rx.grid(False)
    rx.set_title("Fraction above a bias → feature", fontsize=7, pad=2)
    fig.text(0.50, 0.33, "Many filter, dilation and bias\ncombinations → ~5,000 features", ha="center", fontsize=7.3)
    fx = fig.add_axes([0.72, 0.40, 0.23, 0.18])
    fx.bar(np.arange(6), [0.76, 0.42, 0.61, 0.27, 0.52, 0.20], color=green, width=0.65)
    fx.set(xticks=[], yticks=[])
    fx.set_title("A feature vector", fontsize=7.5, pad=4)
    fx.grid(False)
    for spine in fx.spines.values():
        spine.set_visible(False)
    fig.text(0.82, 0.33, "catch22 and entropy features\n24 retained initially; 26 in revision", ha="center", fontsize=7.3)
    labels = [("CNN", "EfficientNet-B0\nlearns image features"),
              ("MiniRocket", "Ridge classifier learns\nfrom response features"),
              ("Random forest", "Learned trees combine\nfeature-based decisions")]
    for x, colour, (name, description) in zip(centres, colours, labels):
        fig.add_artist(FancyArrowPatch((x, 0.30), (x, 0.265), arrowstyle="-|>",
                       mutation_scale=11, lw=1.3, color=colour, transform=fig.transFigure))
        box = FancyBboxPatch((x - 0.142, 0.125), 0.284, 0.135,
                             boxstyle="round,pad=0.007", transform=fig.transFigure,
                             facecolor=colour, edgecolor=colour, alpha=0.12)
        fig.add_artist(box)
        fig.text(x, 0.222, name, ha="center", weight="bold", fontsize=10, color=colour)
        fig.text(x, 0.153, description, ha="center", fontsize=7.5, linespacing=1.4)
    fig.text(0.5, 0.065, "Each route predicts interesting / not interesting from labelled examples",
             ha="center", fontsize=8.1)
    fig.text(0.5, 0.025, "Schematic waveform and feature bars; image encodings calculated from the waveform shown",
             ha="center", fontsize=6.8, color=fs.INK_2)
    print(fs.save(fig, "ch8_model_inputs"))


if __name__ == "__main__":
    main()
