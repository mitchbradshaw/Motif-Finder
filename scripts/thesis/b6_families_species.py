"""B6 for Chapter 10: do the same shape families occur across recordings and species?

In plain words: the Library sorts events into shape families. If shapes were a property of the recording (or the
species), most families would sit on one recording; if shapes were shared, families would mix recordings as freely
as random labels would. The test keeps every family's size and every recording's number of members, shuffles which
recording each member came from, and asks whether the real families mix recordings more or less than the shuffles.

Read from the website: GET /api/library/recurrence?grouping=<g> (the Recurrence page's own payload: each family's
member count per recording and channel) and the species from GET /api/datasets (Settings › Datasets).

Null: labels shuffled across members, each family's size and each label's member count kept (seeded draws). For
each labelling (recording; species; oyster-type against lion's mane):
- shared families: families holding members of two or more labels;
- mutual information I(family; label), in bits: how much a member's family says about where it came from.
p_fewer_shared = (1 + draws with shared <= observed) / (draws + 1): families more label-specific than chance.
p_mi_higher = (1 + draws with MI >= observed) / (draws + 1): membership depends on the label beyond chance.

    python scripts/thesis/b6_families_species.py [--grouping g-11] [--url http://127.0.0.1:8765]
"""
import argparse
import csv
import json
import os
import sys
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b6")


def family_table(payload):
    """`{"families": [...], "recordings": [...], "counts": families x recordings}` from the page's cells."""
    per = []
    for fam in payload["families"]:
        c = {}
        for cell, v in (fam.get("cells") or {}).items():
            rec = cell.rsplit(":", 1)[0]
            n = int(v.get("count") or 0)
            if n:
                c[rec] = c.get(rec, 0) + n
        per.append((fam["id"], c))
    recordings = sorted({r for _, c in per for r in c})
    counts = np.array([[c.get(r, 0) for r in recordings] for _, c in per], dtype=int)
    return {"families": [fid for fid, _ in per], "recordings": recordings, "counts": counts}


def _stats(fam_idx, lab_idx, n_fam, n_lab):
    tab = np.bincount(fam_idx * n_lab + lab_idx, minlength=n_fam * n_lab).reshape(n_fam, n_lab)
    shared = int(np.sum((tab > 0).sum(axis=1) >= 2))
    p = tab / tab.sum()
    pf, pl = p.sum(axis=1, keepdims=True), p.sum(axis=0, keepdims=True)
    nz = p > 0
    mi = float(np.sum(p[nz] * np.log2(p[nz] / (pf @ pl)[nz])))
    return {"shared_families": shared, "mi_bits": mi}


def _labelling(fam_idx, labels, n_fam, draws, rng):
    names = sorted(set(labels))
    lab_idx = np.array([names.index(x) for x in labels])
    obs = _stats(fam_idx, lab_idx, n_fam, len(names))
    null = [_stats(fam_idx, rng.permutation(lab_idx), n_fam, len(names)) for _ in range(draws)]
    sh = np.array([d["shared_families"] for d in null])
    mi = np.array([d["mi_bits"] for d in null])
    k = draws + 1
    return {"labels": names, "members_per_label": {n: int(np.sum(lab_idx == i)) for i, n in enumerate(names)},
            "observed": obs,
            "null_mean": {"shared_families": float(sh.mean()), "mi_bits": float(mi.mean())},
            "null_range": {"shared_families": [int(sh.min()), int(sh.max())], "mi_bits": [float(mi.min()), float(mi.max())]},
            "p_fewer_shared": (1 + int(np.sum(sh <= obs["shared_families"]))) / k,
            "p_more_shared": (1 + int(np.sum(sh >= obs["shared_families"]))) / k,
            "p_mi_higher": (1 + int(np.sum(mi >= obs["mi_bits"] - 1e-12))) / k}


def _kind(species):
    s = species.lower()
    return "oyster-type" if "oyster" in s else species


def read_out(payload, species, draws=10000, seed=20261103):
    """The table and, per labelling, the observed statistics against the shuffled-label null."""
    t = family_table(payload)
    missing = [r for r in t["recordings"] if not species.get(r)]
    if missing:
        raise ValueError(f"no species for {missing}: set them in Settings › Datasets first")
    fam_idx = np.repeat(np.arange(len(t["families"])), t["counts"].sum(axis=1))
    recs = [r for row in t["counts"] for r, n in zip(t["recordings"], row) for _ in range(n)]
    rng = np.random.default_rng(seed)
    by = {"recording": _labelling(fam_idx, recs, len(t["families"]), draws, rng),
          "species": _labelling(fam_idx, [species[r] for r in recs], len(t["families"]), draws, rng),
          "kind": _labelling(fam_idx, [_kind(species[r]) for r in recs], len(t["families"]), draws, rng)}
    return {"table": t, "by": by, "draws": draws, "seed": seed}


def _get(url):
    with urllib.request.urlopen(url, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--grouping", default="g-11")
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--draws", type=int, default=10000)
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    payload = _get(f"{a.url}/api/library/recurrence?grouping={a.grouping}")
    files = {r["key"]: r["file"] for r in payload["recordings"]}
    sp_by_file = {d["source_file"]: d.get("species") for d in _get(f"{a.url}/api/datasets")["datasets"]}
    species = {k: sp_by_file.get(f) for k, f in files.items()}
    res = read_out(payload, species, draws=a.draws)
    t = res["table"]
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "family_by_recording.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["family"] + [f"{r} ({species[r]})" for r in t["recordings"]] + ["members", "recordings", "species"])
        for fid, row in zip(t["families"], t["counts"]):
            sp = {species[r] for r, n in zip(t["recordings"], row) if n}
            w.writerow([fid] + row.tolist() + [int(row.sum()), int((row > 0).sum()), len(sp)])
    summary = {"grouping": a.grouping, "recordings": {r: {"file": files[r], "species": species[r]} for r in t["recordings"]},
               "families": len(t["families"]), "members": int(t["counts"].sum()),
               "draws": res["draws"], "seed": res["seed"], "by": res["by"]}
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print(f"{a.grouping}: {summary['families']} families, {summary['members']} members on {len(t['recordings'])} recordings")
    for name, b in res["by"].items():
        o, nm = b["observed"], b["null_mean"]
        print(f"  {name:9s} labels {len(b['labels'])}: shared {o['shared_families']} vs null {nm['shared_families']:.1f} "
              f"(p fewer {b['p_fewer_shared']:.4f}, p more {b['p_more_shared']:.4f}); MI {o['mi_bits']:.3f} vs "
              f"{nm['mi_bits']:.3f} bits (p {b['p_mi_higher']:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
