# The drop pool's cleaner part through the 23 Nov drop plots (25 Nov 2026)

**Open [`index.html`](index.html).**

The same figures as [`../20261124_pool_plots/`](../20261124_pool_plots/index.html), drawn only over the **46,555 core
drops** that the verdict model puts at 0.8 or more. The model is a model of 4,794 past verdicts, in
`scripts/autodetect/pool_summary.py`; each drop's prediction is in
`DATA/derived/autodetect/pool_20261124/p_accept.parquet`.

**Read [`../20261124_pool_plots/README.md`](../20261124_pool_plots/README.md) first.** Its warnings apply here too.

**Use this set as the check.** A pattern that shows in both sets is not the pool's noise. A pattern that shows only in
the full core may be.

**How this set differs from the full core:**

* It keeps 35% of the core, unevenly: M2_aug, LM, CO and F2B keep the most; Cordyceps, Enoki, MJu26a and split gill
  the least.
* The model also favours drops that are clear, deep, sharp and vouched for by several sources. So this set is not a
  random sample of the real drops either: it leans to the obvious ones.

Drawn by `POOL_MIN_P_ACCEPT=0.8 scripts/autodetect/pool_plots.py`. Its event table and waveforms are
`events_p80.csv` and `event_shapes_p80.npz` beside the pool.
