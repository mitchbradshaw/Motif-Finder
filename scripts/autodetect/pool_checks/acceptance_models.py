"""
acceptance_models.py
====================
Which model of the researcher's verdicts can say how many of the pool's drops they would accept?

`pool_summary.py` re-weights the past verdicts to the pool's own measures, because the judged drops are clearer than
the pool's: the queues showed the clearest first. The re-weighting is only as good as the model's fit where the pool
sits, among the faint and shallow drops. This check fits three models of the verdict (accepted against rejected or
unsure) on the judged drops that pass the loosest settings, from the same measures. It compares their
cross-validated predictions with the verdicts band by band, and prints what each says of the pool's two tiers:

* `linear`: a straight logistic model of the standardised measures;
* `spline`: the same with a cubic spline of each continuous measure;
* `hgb`: shallow gradient-boosted trees (`pool_summary.verdict_model`, the one used).

Each band prints as `predicted/accepted`. The model to trust is the one whose two numbers agree where the pool's
drops are.

A side check of the 24 Nov drop pool (scripts/autodetect/run_pool.py, build_pool.py, pool_summary.py). Read-only: it
reads the pool's `flags/` and `pool.parquet`, and no database. Output:
docs/autodetect/20261124_pool/checks/acceptance_models.out.txt.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_checks/acceptance_models.py
"""
from __future__ import annotations

import os
import sys
import warnings

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repo
sys.path.insert(0, os.path.join(ROOT, "scripts", "autodetect"))
import build_pool as BP  # noqa: E402
import pool_summary as S  # noqa: E402


def main():
    warnings.simplefilter("ignore")
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import SplineTransformer, StandardScaler
    j, _core_ok = S.judged_for_model(BP)
    X, y = S.model_features(j), (j["label"] == "accepted").to_numpy(int)
    cv = StratifiedKFold(5, shuffle=True, random_state=20261124)
    spline = ColumnTransformer([("s", SplineTransformer(n_knots=5, degree=3, extrapolation="constant"),
                                 [0, 1, 2, 3, 4, 7]), ("l", StandardScaler(), [5, 6])])
    models = {"linear": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
              "spline": make_pipeline(spline, LogisticRegression(max_iter=5000)),
              "hgb": S.verdict_model()}
    pool = S.with_rhythm(pd.read_parquet(os.path.join(BP.POOL, "pool.parquet")))
    Xp = S.model_features(pool)
    tiers = pool["tier"].to_numpy()
    print(f"{len(j):,} judged drops pass the loosest settings; {y.mean():.1%} accepted. Measures: "
          f"{', '.join(S.MODEL_FEATURES)}.\n")
    for name, m in models.items():
        p = cross_val_predict(m, X, y, cv=cv, method="predict_proba")[:, 1]
        jj = j.assign(p=p, y=y)
        m.fit(X, y)
        pp = m.predict_proba(Xp)[:, 1]
        print(f"== {name}: cross-validated AUC {roc_auc_score(y, p):.3f}, Brier {brier_score_loss(y, p):.4f}; "
              f"over the pool: core {pp[tiers == 'core'].mean():.1%}, extended {pp[tiers == 'extended'].mean():.1%}")
        for key, bins in S.CHECK_BANDS.items():
            g = jj.groupby(pd.cut(pd.to_numeric(jj[key], errors="coerce"), bins), observed=True).agg(
                n=("y", "size"), pr=("p", "mean"), ac=("y", "mean"))
            print(f"   {key}: " + "  ".join(f"{i} {r.pr:.2f}/{r.ac:.2f} (n {r.n})" for i, r in g.iterrows()))
        print()


if __name__ == "__main__":
    main()
