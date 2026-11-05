"""B6 and B12 re-run with the corrected species labels (5 Nov), from the outputs already in the repo.

In plain words: two Chapter 10 studies asked whether shapes differ by species. They were run while M2_concat was
labelled lion's mane and chocolate oyster was treated as its own species. Both labels were wrong: M2_concat is
oyster, and chocolate oyster is a strain of the same species (Pleurotus ostreatus). This script repeats the two
studies' statistics, with nothing else changed, at two levels:

  species (Latin):  P. ostreatus = M2_aug, M2_concat, CO;  H. erinaceus = LM, MJu26a's five-channel copy (L_LM fs2)
  strain:           oyster = M2_aug, M2_concat;  chocolate oyster = CO;  lion's mane = LM, L_LM fs2

B6 reads docs/thesis/data/ch10_b6/family_by_recording.csv (g-11's member counts per family and recording, the
Recurrence page's payload as saved on 3 Nov) and uses b6_families_species's own shuffled-label null.
B12 reads docs/thesis/data/ch10_b12/events_shape.csv, waveforms_64.npy and intervals_by_channel.csv (the 716 judged
events and 40-45 channels measured on 3 Nov) and uses b12_shapes_intervals's own Kruskal-Wallis, PERMANOVA and BH.
Because a species difference is confounded with recording, each level is set beside the yardstick of how much
recordings of ONE species differ from each other.

Writes docs/thesis/data/ch10_b6/summary_species_5nov.json and docs/thesis/data/ch10_b12/{shape,interval}_tests_5nov.csv.
Reads no database and touches nothing else.

    python scripts/thesis/species_rerun_b6_b12.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import b6_families_species as b6  # noqa: E402
import b12_shapes_intervals as b12  # noqa: E402

D6 = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b6")
D12 = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b12")

SPECIES = {"M2_aug": "P. ostreatus", "M2_concat": "P. ostreatus", "CO_fs2": "P. ostreatus",
           "LM_fs2": "H. erinaceus", "L_LM_fs2": "H. erinaceus", "L_LM_10Hz": "H. erinaceus"}
STRAIN = {"M2_aug": "oyster", "M2_concat": "oyster", "CO_fs2": "chocolate oyster",
          "LM_fs2": "lion's mane", "L_LM_fs2": "lion's mane", "L_LM_10Hz": "lion's mane"}
# the B6 table's recording keys
B6_KEY = {"M2_aug_fs1": "M2_aug", "M2_fs1": "M2_concat", "CO_fs2": "CO_fs2", "LM_fs2": "LM_fs2"}


def rerun_b6(draws=10000, seed=20261103):
    with open(os.path.join(D6, "family_by_recording.csv"), newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    head = rows[0]
    rec_cols = [(i, h.split(" (")[0]) for i, h in enumerate(head) if " (" in h]
    fams, counts = [], []
    for r in rows[1:]:
        fams.append(r[0])
        counts.append([int(r[i]) for i, _ in rec_cols])
    counts = np.array(counts, dtype=int)
    recs = [B6_KEY[k] for _, k in rec_cols]
    fam_idx = np.repeat(np.arange(len(fams)), counts.sum(axis=1))
    member_rec = [rec for row in counts for rec, n in zip(recs, row) for _ in range(n)]
    rng = np.random.default_rng(seed)
    by = {"recording": b6._labelling(fam_idx, member_rec, len(fams), draws, rng),
          "species": b6._labelling(fam_idx, [SPECIES[r] for r in member_rec], len(fams), draws, rng),
          "strain": b6._labelling(fam_idx, [STRAIN[r] for r in member_rec], len(fams), draws, rng)}
    # within-species yardstick: P. ostreatus's three recordings only
    m = np.array([SPECIES[r] == "P. ostreatus" for r in member_rec])
    keep = np.flatnonzero(m)
    fi = fam_idx[keep]
    used = np.unique(fi)
    remap = {f: i for i, f in enumerate(used)}
    by["recordings within P. ostreatus"] = b6._labelling(np.array([remap[f] for f in fi]),
                                                          [member_rec[i] for i in keep], len(used), draws, rng)
    per_family = []
    for f, row in zip(fams, counts):
        sp = {SPECIES[r] for r, n in zip(recs, row) if n}
        st = {STRAIN[r] for r, n in zip(recs, row) if n}
        per_family.append({"family": f, "members": int(row.sum()), "recordings": int((row > 0).sum()),
                           "species": len(sp), "strains": len(st)})
    pf = pd.DataFrame(per_family)
    out = {"grouping": "g-11", "labels": {"species": SPECIES, "strain": STRAIN}, "families": len(fams),
           "members": int(counts.sum()), "draws": draws, "seed": seed,
           "families_on_2plus_recordings": int((pf["recordings"] >= 2).sum()),
           "families_on_both_species": int((pf["species"] >= 2).sum()),
           "families_on_2plus_strains": int((pf["strains"] >= 2).sum()),
           "members_per_species": {s: int(sum(1 for r in member_rec if SPECIES[r] == s)) for s in sorted(set(SPECIES.values()))},
           "by": by}
    with open(os.path.join(D6, "summary_species_5nov.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    pf.to_csv(os.path.join(D6, "families_species_5nov.csv"), index=False)
    return out


def rerun_b12_shapes():
    df = pd.read_csv(os.path.join(D12, "events_shape.csv"))
    W = np.load(os.path.join(D12, "waveforms_64.npy"))
    assert len(df) == len(W)
    df["species_5nov"] = df["recording"].map(SPECIES)
    df["strain_5nov"] = df["recording"].map(STRAIN)
    assert df["species_5nov"].notna().all(), df.loc[df["species_5nov"].isna(), "recording"].unique()
    df["band"] = pd.qcut(df["span_s"], 5, labels=False, duplicates="drop")
    ones = np.ones(len(df), bool)
    levels = {
        "species (P. ostreatus vs H. erinaceus)": (df["species_5nov"], ones),
        "strain (oyster, chocolate oyster, lion's mane)": (df["strain_5nov"], ones),
        "recordings within P. ostreatus": (df["recording"], (df["species_5nov"] == "P. ostreatus").to_numpy()),
        "recordings within H. erinaceus": (df["recording"], (df["species_5nov"] == "H. erinaceus").to_numpy()),
    }
    rows = []
    for lvl, (lab, m) in levels.items():
        lab = np.asarray(lab)[m]
        sub = df[m]
        for null in ("shuffle", "within duration bands", "duration residual"):
            block = []
            for f in b12.SCALAR:
                v = sub[f].to_numpy(float)
                if null == "duration residual":
                    if f in b12.NORMALISED or f == "span_s":
                        continue
                    v = b12.residual_on_duration(v, sub["span_s"].to_numpy(float))
                if null == "within duration bands" and f == "span_s":
                    continue
                r = b12.kw_perm(v, lab, strata=sub["band"].to_numpy() if null == "within duration bands" else None)
                block.append({"level": lvl, "null": null, "feature": f, **r})
            r = b12.permanova(W[m], lab, n_perm=2000,
                              strata=sub["band"].to_numpy() if null == "within duration bands" else None)
            block.append({"level": lvl, "null": null, "feature": "normalised waveform (64 pt)", "H": None, "eps2": None,
                          "n": r["n"], "k": r["k"], "p": r["p"], "pseudo_F": r["pseudo_F"], "R2": r["R2"]})
            for b, (qq, ok) in zip(block, b12.bh([b["p"] for b in block])):
                b["q_bh"], b["bh_pass_05"] = qq, ok
            rows.extend(block)
    st = pd.DataFrame(rows)
    st.to_csv(os.path.join(D12, "shape_tests_5nov.csv"), index=False)
    groups = df.groupby(["species_5nov", "strain_5nov", "recording"]).size().rename("n").reset_index()
    groups.to_csv(os.path.join(D12, "events_by_species_5nov.csv"), index=False)
    return st, groups


def rerun_b12_intervals():
    iv = pd.read_csv(os.path.join(D12, "intervals_by_channel.csv"))
    iv["species_5nov"] = iv["dataset"].map(SPECIES)
    iv["strain_5nov"] = iv["dataset"].map(STRAIN)
    ones = np.ones(len(iv), bool)
    rows = []
    for lvl, lab, m in (("species (P. ostreatus vs H. erinaceus)", iv["species_5nov"], ones),
                        ("strain (oyster, chocolate oyster, lion's mane)", iv["strain_5nov"], ones),
                        ("datasets within P. ostreatus", iv["dataset"], (iv["species_5nov"] == "P. ostreatus").to_numpy()),
                        ("datasets within H. erinaceus", iv["dataset"], (iv["species_5nov"] == "H. erinaceus").to_numpy())):
        block = []
        for f in ("lv", "cv2", "n_events"):
            r = b12.kw_perm(iv[f].to_numpy(float)[m], np.asarray(lab)[m], n_perm=10000)
            block.append({"level": lvl, "feature": f, **r})
        q = b12.bh([b["p"] for b in block[:2]]) + [(None, None)]
        for b, (qq, ok) in zip(block, q):
            b["q_bh_lv_cv2"], b["bh_pass_05"] = qq, ok
        rows.extend(block)
    it = pd.DataFrame(rows)
    it.to_csv(os.path.join(D12, "interval_tests_5nov.csv"), index=False)
    return it


def main():
    o6 = rerun_b6()
    print(f"B6 g-11: {o6['families']} families, {o6['members']} members")
    print(f"  on 2+ recordings {o6['families_on_2plus_recordings']}, on both species {o6['families_on_both_species']}, "
          f"on 2+ strains {o6['families_on_2plus_strains']}; members per species {o6['members_per_species']}")
    for name, b in o6["by"].items():
        o, nm = b["observed"], b["null_mean"]
        print(f"  {name:32s} shared {o['shared_families']} vs null {nm['shared_families']:.1f} "
              f"(p fewer {b['p_fewer_shared']:.4f}); MI {o['mi_bits']:.3f} vs {nm['mi_bits']:.3f} bits "
              f"(p {b['p_mi_higher']:.4f})")
    st, groups = rerun_b12_shapes()
    print(groups.to_string(index=False))
    pd.set_option("display.width", 220)
    show = st[st["null"] == "shuffle"][["level", "feature", "n", "k", "eps2", "p", "q_bh", "bh_pass_05", "R2"]]
    print(show.to_string(index=False))
    summ = st.groupby(["level", "null"])["bh_pass_05"].agg(["sum", "count"]).reset_index()
    print(summ.to_string(index=False))
    it = rerun_b12_intervals()
    print(it.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
