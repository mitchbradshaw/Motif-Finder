"""Redraw Figure 9.1 (ch9_combined_catalogue) from the 9 Nov catalogue snapshot, after queue 47 was judged.

The chart is the same as `completed_review_figures.py` draws (same order, colours and labels); only its input changes,
to `docs/thesis/data/accepted_catalogue_20261109/accepted_spans.csv` written by `reviews_queue47_20261109.py`.
Read-only: no signal is loaded and nothing under DATA/ is touched.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/fig_combined_catalogue_20261109.py
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.thesis import figstyle as style  # noqa: E402
from scripts.thesis.completed_review_figures import ORDER  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

SPANS = ROOT / "docs/thesis/data/accepted_catalogue_20261109/accepted_spans.csv"


def main():
    style.apply()
    spans = pd.read_csv(SPANS)
    counts = Counter(spans.loc[spans["thesis_scope"].astype(bool), "dataset"])
    fig, ax = plt.subplots(figsize=(6.3, 2.8), layout="constrained")
    ax.barh(ORDER, [counts[r] for r in ORDER], color=[style.colour(r) for r in ORDER])
    for i, r in enumerate(ORDER):
        ax.text(counts[r] + 12, i, f"{counts[r]:,}", va="center", fontsize=9)
    ax.set_xlim(0, max(counts.values()) * 1.13)
    ax.invert_yaxis()
    ax.set_xlabel("Accepted spans after physical-copy and overlap reconciliation")
    ax.spines[["right", "top"]].set_visible(False)
    style.save(fig, "ch9_combined_catalogue")
    plt.close(fig)
    print(dict(counts), sum(counts.values()))


if __name__ == "__main__":
    main()
