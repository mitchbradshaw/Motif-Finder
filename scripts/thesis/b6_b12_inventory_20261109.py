"""B6 and B12 re-read on the 9 Nov inventory (2,459 accepted single events, 12 shape families; read-only).

B6: do shape families recur across recordings and species? Mutual information between family and recording, and
between family and species, each against 1,000 label shuffles; the recording lean is split into its species part and
its within-species part (I(F;R) = I(F;S) + I(F;R|S), species being a function of recording).
B12: do the measures differ between recordings and species? Kruskal-Wallis on depth, fall time, half-recovery and
duration (log values) and a chi-squared test on the share of falls, by recording, by species, and between the five
oyster recordings alone; Benjamini-Hochberg at 0.05 within each comparison; epsilon-squared as the effect size.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b6_b12_inventory_20261109.py
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, kruskal
from sklearn.metrics import mutual_info_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = os.path.join(ROOT, "docs", "thesis", "data", "ch9_inventory_20261109")
SPECIES = {"M2_aug": "oyster", "M2_concat": "oyster", "M4": "oyster", "CO": "oyster", "SO": "oyster",
           "LM": "lions_mane", "MJu26a": "lions_mane", "SH": "shiitake"}
BITS = 1.0 / np.log(2)


def bh(p):
    p = np.asarray(p, float)
    order = np.argsort(p)
    q = np.empty_like(p)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, 1))):
        prev = min(prev, p[i] * len(p) / rank)
        q[i] = prev
    return q


def b6(fam, draws=1000, seed=20261109):
    rng = np.random.default_rng(seed)
    f = fam["family"].to_numpy()
    r = fam["dataset"].to_numpy()
    s = fam["dataset"].map(SPECIES).to_numpy()
    out = {"families": int(fam["family"].nunique()),
           "families_on_2plus_recordings": int((fam.groupby("family")["dataset"].nunique() >= 2).sum()),
           "families_on_all_8": int((fam.groupby("family")["dataset"].nunique() == 8).sum()),
           "families_on_all_3_species": int((fam.assign(sp=s).groupby("family")["sp"].nunique() == 3).sum())}
    for name, lab in (("recording", r), ("species", s)):
        obs = mutual_info_score(f, lab) * BITS
        null = np.array([mutual_info_score(rng.permutation(f), lab) * BITS for _ in range(draws)])
        out[name] = {"mi_bits": obs, "null_mean": float(null.mean()), "p": (1 + int((null >= obs).sum())) / (draws + 1)}
    out["within_species_bits"] = out["recording"]["mi_bits"] - out["species"]["mi_bits"]
    return out


def b12(m):
    m = m[m["status"] == "single"].copy()
    m["species"] = m["dataset"].map(SPECIES)
    feats = ["depth_mv", "fall_s", "half_recovery_s", "duration_s"]
    rows = []
    for level, data, col in (("recording", m, "dataset"), ("species", m, "species"),
                             ("oyster recordings", m[m["species"] == "oyster"], "dataset")):
        res = []
        for f in feats:
            groups = [np.log10(g[f].dropna().clip(lower=1e-3)) for _, g in data.groupby(col) if g[f].notna().sum() > 2]
            h, p = kruskal(*groups)
            n, k = sum(len(g) for g in groups), len(groups)
            res.append({"level": level, "feature": f, "p": float(p), "eps2": float((h - k + 1) / (n - k))})
        tab = pd.crosstab(data[col], data["polarity"] < 0)
        chi, p, dof, _ = chi2_contingency(tab)
        res.append({"level": level, "feature": "share_falls", "p": float(p),
                    "eps2": float(np.sqrt(chi / (tab.to_numpy().sum() * (min(tab.shape) - 1))))})
        q = bh([r_["p"] for r_ in res])
        for r_, qq in zip(res, q):
            r_["q"] = float(qq)
            r_["pass_bh"] = bool(qq < 0.05)
        rows += res
    return pd.DataFrame(rows)


def main():
    fam = pd.read_csv(os.path.join(D, "families.csv"))
    m = pd.read_csv(os.path.join(D, "measures.csv"))
    r6 = b6(fam)
    t12 = b12(m)
    t12.to_csv(os.path.join(D, "b12_inventory.csv"), index=False)
    with open(os.path.join(D, "b6_inventory.json"), "w", encoding="utf-8") as f:
        json.dump(r6, f, indent=2)
    print(json.dumps(r6, indent=1))
    pd.set_option("display.width", 200)
    print(t12.round(4).to_string(index=False))
    print(t12.groupby("level")["pass_bh"].agg(["sum", "count"]))


if __name__ == "__main__":
    main()
