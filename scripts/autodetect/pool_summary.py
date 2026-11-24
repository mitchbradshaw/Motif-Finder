"""
pool_summary.py
===============
The numbers behind the 24 Nov drop pool's write-up (`docs/autodetect/20261124_pool/README.md`), computed from what
the stages saved, so the README never carries a number nobody can recompute.

Reads `DATA/derived/autodetect/pool_20261124/` (every `raw/<rid>/run.json`, `flags/` and `pool.parquet`) and
`docs/autodetect/20261124_pool/calibration.csv`. It writes `summary.json` and `summary.md` beside the README, and each
pool drop's predicted acceptance to `p_accept.parquet` beside the pool. It reads no database, no channel and no
detector, and it takes about a minute.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_summary.py

What it measures:

* **the search**: channels, datasets, hours of recording searched, drops and rises found, worker hours, the wall
  clock from the first channel to the last, and the slowest channels;
* **the pool by dataset**: drops found, core, extended, core drops per 100 h of recording, and each dataset's
  share of the core;
* **what the verdicts say to expect**: how often the researcher accepted the judged drops that pass the core's
  settings, and the looser settings only; the same weighted to the pool's own mix of confidence; and re-weighted to
  all of the pool's measures by a small logistic model of the verdicts (`acceptance_model`). The judged drops are the
  ones the queues showed first, clearer than the pool's, so the plain share is a ceiling;
* **concentration**: how much of the core the biggest datasets and channels hold;
* **what is flagged in the pool**: finder-only, M4-like, long tail, several events in one span;
* **the drops' shapes by dataset** (core): the whole-drop rule's depth, fall, width and recovery, as medians.
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POOL = os.path.join(ROOT, "DATA", "derived", "autodetect", "pool_20261124")
DOCS = os.path.join(ROOT, "docs", "autodetect", "20261124_pool")
CONF_BANDS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0001]


def runs():
    rows = []
    for f in glob.glob(os.path.join(POOL, "raw", "*", "run.json")):
        with open(f, encoding="utf-8") as fh:
            j = json.load(fh)
        c = j.get("counts", {})
        rows.append({"recording_id": int(j["recording"]["id"]), "dataset": j["target"]["dataset"],
                     "species": j["target"]["species"], "channel": int(j["recording"]["channel"]),
                     "native_fs": float(j["recording"]["fs"]), "hours": float(j["hours"]),
                     "wall_s": float(j["wall_s"]), "finished_at": pd.Timestamp(j["finished_at"]),
                     "drops": int(c.get("drops", 0)), "rises": int(c.get("rises", 0)),
                     "drops_06": int(c.get("drops_conf_0.6", 0)), "pid": j.get("pid"),
                     "peak_gb": j.get("process_peak_wset_gb")})
    return pd.DataFrame(rows).sort_values("recording_id").reset_index(drop=True)


def band_shares(cal):
    """{band label: accepted share} from calibration.csv's confidence rows."""
    c = cal[cal["by"] == "confidence"]
    return dict(zip(c["band"], c["accepted_share"])), dict(zip(c["band"], c["judged"]))


def expected(pool_conf, shares):
    """The accepted share the verdicts would give a set of drops with these confidences (band by band)."""
    cut = pd.cut(pool_conf, CONF_BANDS)
    n = cut.value_counts()
    tot = int(n.sum())
    if not tot:
        return np.nan
    return float(sum(shares.get(str(b), np.nan) * k for b, k in n.items() if k) / tot)


#: The measures the acceptance model reads: what the pool keeps for every drop, nothing about where it was found.
#: `fast_rises` (`pool_rhythm.py`): how often the trace around the drop climbs back as fast as the drop fell.
MODEL_FEATURES = ("log clarity", "confidence", "p_r4", "log depth", "log sharpness", "sources", "finder only",
                  "fast rises")
RHYTHM = os.path.join(POOL, "rhythm.parquet")


def with_rhythm(d):
    """`d` with `fast_rises` (and `rhythm_r`) from `pool_rhythm.py`'s table; loud if that has not been run."""
    if not os.path.isfile(RHYTHM):
        raise FileNotFoundError(f"{RHYTHM} is missing: run scripts/autodetect/pool_rhythm.py after choose")
    rh = pd.read_parquet(RHYTHM, columns=["recording_id", "candidate_id", "rhythm_r", "fast_rises"])
    out = d.drop(columns=[c for c in ("rhythm_r", "fast_rises") if c in d]).merge(
        rh, on=["recording_id", "candidate_id"], how="left", validate="many_to_one")
    return out


def model_features(d):
    num = lambda k: pd.to_numeric(d[k], errors="coerce").to_numpy(float)  # noqa: E731
    X = np.column_stack([
        np.log10(np.clip(np.nan_to_num(num("clarity"), nan=10.0), 1.0, None)),
        num("confidence"), np.nan_to_num(num("p_r4"), nan=0.5),
        np.log10(np.clip(np.nan_to_num(num("depth_mv"), nan=0.01), 0.01, None)),
        np.log10(np.clip(np.nan_to_num(num("sharpness"), nan=1.0), 1.0, None)),
        np.minimum(np.nan_to_num(num("n_sources"), nan=1.0), 6.0), d["finder_only"].astype(bool).to_numpy(float),
        np.log1p(np.nan_to_num(num("fast_rises"), nan=0.0))])
    return X


#: Where the model's cross-validated predictions are checked against the verdicts, band by band: the measures in which
#: the pool differs most from the judged drops.
CHECK_BANDS = {"fast_rises": [-0.5, 0.5, 1.5, 2.5, 3.5, 5.5, 9.5, 1e6],
               "clarity": [10, 15, 20, 30, 50, 100, 300, 1e12], "depth_mv": [0, 0.25, 0.5, 1, 2, 5, 10, 1e12],
               "confidence": [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0001]}


def verdict_model():
    """The model of the researcher's verdict: shallow gradient-boosted trees. A straight logistic model of the same
    measures over-predicted the faint and shallow drops (clarity 15-20: 71 % predicted, 54 % accepted; depth under
    0.25 mV: 68 % against 40 %), where a quarter of the core sits, and a spline one still by up to 10 points; these
    trees are within 4 points in every band of fast rises, clarity, depth and confidence
    (`pool_checks/acceptance_models.py`, 25 Nov)."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=40,
                                          l2_regularization=1.0, random_state=0)


def judged_for_model(BP):
    """The judged drops of the run that pass the loosest settings (with "already judged" and "already in a queue" set
    aside), and which of them pass the core's."""
    allc = BP.load_flags()
    j = allc[allc["label"] != ""].copy()
    loose = BP.rule_mask(j.assign(reviewed=False, seen=False), with_overlap=False,
                         min_confidence=BP.MEASURE_FROM["confidence"],
                         clarity_min=BP.MEASURE_FROM["clarity"]).to_numpy(bool)
    j = j[loose]
    core_ok = BP.rule_mask(j.assign(reviewed=False, seen=False), with_overlap=False).to_numpy(bool)
    return with_rhythm(j), core_ok


def acceptance_model(pool):
    """How many of the pool's drops the researcher would accept, re-weighted to the pool's own measures.

    The judged drops are not a random sample: the queues showed the clearest, most confident drops first, so the
    judged ones are far clearer than the pool's (clarity 15-20 is a quarter of the core and 1 % of the judged). A plain
    accepted share therefore flatters the pool. This fits a model of the verdict (accepted against rejected or unsure;
    `verdict_model`) on the judged drops that pass the loosest settings, from `MODEL_FEATURES` (with `fast_rises` from
    `pool_rhythm.py`), and averages its prediction over the pool. It assumes a drop as clear, deep, sharp and well vouched for as a judged one is accepted
    as often, on every dataset: for the datasets nobody has judged (M1, L_R_Aug_26_PD, Cordyceps, Enoki, F2B, the Dwij
    loggers) that is an extrapolation. Returns the summary and each pool drop's predicted acceptance."""
    import build_pool as BP
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    j, core_ok = judged_for_model(BP)
    X, y = model_features(j), (j["label"] == "accepted").to_numpy(int)
    model = verdict_model()
    p_cv = cross_val_predict(model, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=20261124),
                             method="predict_proba")[:, 1]
    model.fit(X, y)
    dec = pd.qcut(p_cv, 10, duplicates="drop")
    calib = pd.DataFrame({"p": p_cv, "y": y}).groupby(dec, observed=True).agg(
        judged=("y", "size"), predicted=("p", "mean"), accepted=("y", "mean")).reset_index(drop=True)
    jj = j.assign(p=p_cv, y=y)
    bands = {k: jj.groupby(pd.cut(pd.to_numeric(jj[k], errors="coerce"), b), observed=True)
             .agg(judged=("y", "size"), predicted=("p", "mean"), accepted=("y", "mean"))
             .reset_index().assign(band=lambda t: t[k].astype(str)).drop(columns=k)[["band", "judged", "predicted",
                                                                                     "accepted"]]
             .to_dict(orient="records") for k, b in CHECK_BANDS.items()}
    p_pool = model.predict_proba(model_features(with_rhythm(pool)))[:, 1]
    tiers = pool["tier"].to_numpy()
    out = {"model": "HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, "
                    "min_samples_leaf=40, l2_regularization=1.0)",
           "judged_used": int(len(j)), "judged_core_settings": int(core_ok.sum()),
           "cv_auc": float(roc_auc_score(y, p_cv)), "cv_brier": float(brier_score_loss(y, p_cv)),
           "judged_accepted_share": float(y.mean()),
           "core_expected": float(p_pool[tiers == "core"].mean()),
           "extended_expected": float(p_pool[tiers == "extended"].mean()),
           "core_expected_by_dataset": {d: float(v) for d, v in
                                        pd.Series(p_pool[tiers == "core"], index=pool.loc[tiers == "core", "dataset"]
                                                  .astype(str).to_numpy()).groupby(level=0).mean().items()},
           "core_share_predicted_0.8_or_more": float((p_pool[tiers == "core"] >= 0.8).mean()),
           "core_predicted_0.8_or_more": int((p_pool[tiers == "core"] >= 0.8).sum()),
           "cv_calibration": calib.to_dict(orient="records"), "cv_by_band": bands}
    return out, p_pool


def md_table(df, floatfmt=None):
    floatfmt = floatfmt or {}
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.itertuples(index=False):
        cells = []
        for k, v in zip(cols, r):
            if isinstance(v, (float, np.floating)):
                cells.append("" if not np.isfinite(v) else format(v, floatfmt.get(k, ",.1f")))
            elif isinstance(v, (int, np.integer)):
                cells.append(f"{int(v):,}")
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def main():
    r = runs()
    pool = pd.read_parquet(os.path.join(POOL, "pool.parquet"))
    cal = pd.read_csv(os.path.join(DOCS, "calibration.csv"))
    shares, judged_n = band_shares(cal)
    core = pool[pool["tier"] == "core"]
    ext = pool[pool["tier"] == "extended"]

    # ── the search ──
    starts = r["finished_at"] - pd.to_timedelta(r["wall_s"], unit="s")
    search = {"channels": int(len(r)), "datasets": int(r["dataset"].nunique()),
              "hours_searched": float(r["hours"].sum()), "drops_found": int(r["drops"].sum()),
              "rises_found_not_used": int(r["rises"].sum()), "drops_found_conf_0.6": int(r["drops_06"].sum()),
              "worker_hours": float(r["wall_s"].sum() / 3600.0), "workers": int(r["pid"].nunique()),
              "first_start": str(starts.min()), "last_finish": str(r["finished_at"].max()),
              "wall_clock_h": float((r["finished_at"].max() - starts.min()).total_seconds() / 3600.0),
              "slowest": [{"recording_id": int(x.recording_id), "dataset": x.dataset, "channel": int(x.channel),
                           "minutes": round(x.wall_s / 60.0, 1), "hours_of_recording": round(x.hours, 1)}
                          for x in r.sort_values("wall_s", ascending=False).head(5).itertuples()]}

    # ── the pool by dataset ──
    by = r.groupby(["dataset", "species"]).agg(channels=("recording_id", "size"), hours=("hours", "sum"),
                                               drops_found=("drops", "sum")).reset_index()
    tiers = pool.groupby(["dataset", "tier"]).size().unstack(fill_value=0)
    by["core"] = by["dataset"].map(tiers.get("core", pd.Series(dtype=int))).fillna(0).astype(int)
    by["extended"] = by["dataset"].map(tiers.get("extended", pd.Series(dtype=int))).fillna(0).astype(int)
    by["core_per_100h"] = by["core"] / by["hours"] * 100.0          # per 100 hours of one channel
    by["core_share"] = by["core"] / max(1, len(core))
    by = by.sort_values("core", ascending=False).reset_index(drop=True)

    # ── what the verdicts say to expect ──
    st = cal[cal["by"] == "settings"].set_index("band")
    exp = {"judged_drops_in_calibration": int(cal[cal["by"] == "confidence"]["judged"].sum()),
           "judged_by_dataset": {b: int(n) for b, n in zip(cal[cal["by"] == "dataset"]["band"],
                                                            cal[cal["by"] == "dataset"]["judged"])},
           "accepted_share_passing_core_settings": float(st.loc["passes the queue's settings", "accepted_share"])
           if "passes the queue's settings" in st.index else None,
           "judged_passing_core_settings": int(st.loc["passes the queue's settings", "judged"])
           if "passes the queue's settings" in st.index else None,
           "accepted_share_looser_settings_only": float(st.loc["only the looser settings", "accepted_share"])
           if "only the looser settings" in st.index else None,
           "judged_looser_settings_only": int(st.loc["only the looser settings", "judged"])
           if "only the looser settings" in st.index else None,
           "core_weighted_by_confidence": expected(core["confidence"], shares),
           "extended_weighted_by_confidence": expected(ext["confidence"], shares),
           "bands": [{"band": b, "judged": int(judged_n[b]), "accepted_share": float(shares[b]),
                      "core": int((pd.cut(core["confidence"], CONF_BANDS).astype(str) == b).sum()),
                      "extended": int((pd.cut(ext["confidence"], CONF_BANDS).astype(str) == b).sum())}
                     for b in shares]}

    model, p_pool = acceptance_model(pool)
    exp["reweighted"] = model
    pd.DataFrame({"recording_id": pool["recording_id"].astype(np.int32), "candidate_id": pool["candidate_id"],
                  "tier": pool["tier"].astype("category"), "p_accept": p_pool.astype(np.float32)}) \
        .to_parquet(os.path.join(POOL, "p_accept.parquet"), index=False)

    # ── concentration ──
    ch = core.groupby(["dataset", "recording_id", "channel"]).size().sort_values(ascending=False)
    conc = {"top2_datasets": list(by["dataset"].head(2)), "top2_share": float(by["core_share"].head(2).sum()),
            "top10_channels_share": float(ch.head(10).sum() / max(1, len(core))),
            "top10_channels": [{"dataset": d, "recording_id": int(i), "channel": int(c), "core": int(n)}
                               for (d, i, c), n in ch.head(10).items()],
            "channels_with_core": int(len(ch)), "median_core_per_channel": float(ch.median()) if len(ch) else 0.0}

    # ── flags in the pool ──
    def share(df, col):
        return float(df[col].astype(bool).mean()) if len(df) and col in df else np.nan
    flags = {t: {"finder_only": share(d, "finder_only"), "m4_like": share(d, "m4_like"),
                 "wd_long_tail": share(d, "wd_long_tail"),
                 "several_events_in_span": float((pd.to_numeric(d["wd_n_events"], errors="coerce") > 1).mean())
                 if len(d) else np.nan,
                 "whole_drop_measured": share(d, "wd_ok"),
                 "confidence_median": float(d["confidence"].median()) if len(d) else np.nan}
             for t, d in (("core", core), ("extended", ext))}

    # ── shapes by dataset (core, measured drops) ──
    m = core[core["wd_ok"].astype(bool)]
    shapes = m.groupby("dataset").agg(drops=("candidate_id", "size"), depth_mv=("wd_depth_mv", "median"),
                                      fall_s=("wd_fall_s", "median"), width_s=("wd_width_s", "median"),
                                      recovery_s=("wd_recovery_s", "median"),
                                      confidence=("confidence", "median")).reset_index() \
        .sort_values("drops", ascending=False)

    out = {"search": search, "pool": {"total": int(len(pool)), "core": int(len(core)), "extended": int(len(ext))},
           "by_dataset": by.to_dict(orient="records"), "expected_acceptance": exp, "concentration": conc,
           "flags": flags, "shapes_by_dataset": shapes.to_dict(orient="records")}
    with open(os.path.join(DOCS, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)

    lines = ["# The 24 Nov drop pool: the numbers", "",
             "Written by `scripts/autodetect/pool_summary.py` from the saved results; `summary.json` holds the same.", "",
             "## The search", "",
             f"* {search['channels']} channels in {search['datasets']} datasets, "
             f"{search['hours_searched']:,.0f} hours of recording (summed over channels).",
             f"* {search['drops_found']:,} drops found ({search['drops_found_conf_0.6']:,} at confidence >= 0.6); "
             f"{search['rises_found_not_used']:,} sharp rises met on the way, not used.",
             f"* {search['worker_hours']:.1f} worker hours on {search['workers']} workers; "
             f"{search['wall_clock_h']:.1f} h of wall clock ({search['first_start'][:16]} to "
             f"{search['last_finish'][:16]}).",
             "* Slowest channels: " + "; ".join(f"{s['dataset']} CH{s['channel']} (rec {s['recording_id']}) "
                                                f"{s['minutes']:.0f} min for {s['hours_of_recording']:.0f} h"
                                                for s in search["slowest"]) + ".", "",
             "## The pool", "",
             f"**{len(pool):,} drops: {len(core):,} core, {len(ext):,} extended.**", "",
             md_table(by.rename(columns={"core_per_100h": "core per 100 h", "core_share": "share of core",
                                         "hours": "hours (all channels)", "drops_found": "drops found"}),
                      {"share of core": ".1%", "core per 100 h": ",.1f", "hours (all channels)": ",.0f"}), "",
             "## What the verdicts say to expect", "",
             f"* Judged drops that pass the core's settings (a ceiling: the queues showed the clearest first): {exp['accepted_share_passing_core_settings']:.0%} "
             f"accepted (n {exp['judged_passing_core_settings']:,}); looser settings only: "
             f"{exp['accepted_share_looser_settings_only']:.0%} (n {exp['judged_looser_settings_only']:,}).",
             f"* Weighted to the pool's own confidences: core {exp['core_weighted_by_confidence']:.0%}, extended "
             f"{exp['extended_weighted_by_confidence']:.0%}.",
             "* The verdicts come from " + ", ".join(f"{k} ({v:,})" for k, v in exp["judged_by_dataset"].items())
             + "; the pool's drops are the ones no queue picked.", "",
             md_table(pd.DataFrame(exp["bands"]).rename(columns={"accepted_share": "accepted"}),
                      {"accepted": ".0%"}), "",
             "### Re-weighted to the pool's own measures", "",
             f"A model of {model['judged_used']:,} past verdicts (accepted against rejected or unsure; shallow "
             f"gradient-boosted trees) from {', '.join(MODEL_FEATURES)}; cross-validated AUC {model['cv_auc']:.2f}, "
             f"Brier {model['cv_brier']:.3f}. Averaged over the pool: "
             f"**core {model['core_expected']:.0%}, extended {model['extended_expected']:.0%}** "
             f"(the judged drops themselves: {model['judged_accepted_share']:.0%}). "
             f"{model['core_share_predicted_0.8_or_more']:.0%} of the core "
             f"({model['core_predicted_0.8_or_more']:,} drops) is predicted at 0.8 or more. Each drop's "
             "prediction is `DATA/derived/autodetect/pool_20261124/p_accept.parquet`: a device for re-weighting and "
             "for checking a plot on a cleaner subset, not a verdict. It assumes a drop is judged by how it looks, "
             "whatever dataset it is on; six datasets have no verdicts at all.", "",
             md_table(pd.DataFrame([{"dataset": d, "core expected": v}
                                    for d, v in sorted(model["core_expected_by_dataset"].items(),
                                                       key=lambda kv: -kv[1])]), {"core expected": ".0%"}), "",
             "Cross-validated calibration (each tenth of the judged drops by predicted acceptance):", "",
             md_table(pd.DataFrame(model["cv_calibration"]), {"predicted": ".0%", "accepted": ".0%"}), ""]
    for k, rows in model["cv_by_band"].items():
        lines += [f"Cross-validated, by {k} band:", "",
                  md_table(pd.DataFrame(rows), {"predicted": ".0%", "accepted": ".0%"}), ""]
    lines += [
             "## Concentration", "",
             f"* {conc['top2_datasets'][0]} and {conc['top2_datasets'][1]} hold {conc['top2_share']:.0%} of the core; "
             f"the ten biggest channels hold {conc['top10_channels_share']:.0%}.",
             f"* {conc['channels_with_core']} channels have core drops; the median channel has "
             f"{conc['median_core_per_channel']:,.0f}.", "",
             md_table(pd.DataFrame(conc["top10_channels"])), "",
             "## Flagged in the pool", "",
             md_table(pd.DataFrame(flags).T.reset_index(names="tier"),
                      {k: ".1%" for k in ("finder_only", "m4_like", "wd_long_tail", "several_events_in_span",
                                          "whole_drop_measured")} | {"confidence_median": ".3f"}), "",
             "## The drops' shapes by dataset (core, medians)", "",
             md_table(shapes, {"depth_mv": ".2f", "fall_s": ",.1f", "width_s": ",.1f", "recovery_s": ",.1f",
                               "confidence": ".3f"}), ""]
    with open(os.path.join(DOCS, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
