"""
b10_readout.py - the per-length table of every motif_lengths site run (b10_motif_lengths_site.py), read from the
step payloads it saved (docs/thesis/data/ch10_b10/job<id>_step1_payload.json -> row_verdict). Writes
docs/thesis/data/ch10_b10/motif_lengths_by_length.csv and prints one line per run.
"""
import json
import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b10")
NAMES = {"M2_aug_concat_fs1.mat": "M2_aug", "M2_concat_fs1.mat": "M2_concat", "CO_fs2.mat": "CO_fs2",
         "LM_fs2.mat": "LM_fs2", "MJu26a_fs2.mat": "MJu26a_fs2"}


def main():
    runs = json.load(open(os.path.join(D, "site_runs.json")))
    rows = []
    for r in runs:
        p = os.path.join(D, f"job{r['job_id']}_step1_payload.json")
        if r["status"] != "completed" or not os.path.exists(p):
            print(r["source_file"], r["frac"], r["status"])
            continue
        rv = json.load(open(p))["row_verdict"]
        h0 = r["span"][0] / r["fs"] / 3600
        print(f"{NAMES[r['source_file']]:11s} rec {r['recording_id']} {h0:6.1f}-{h0 + 8:6.1f} h  job {r['job_id']} "
              f"{r['seconds']:5.0f} s  | {rv['verdict']}")
        for x in rv["rows"]:
            rows.append({"recording": NAMES[r["source_file"]], "recording_id": r["recording_id"], "frac": r["frac"],
                         "start_h": round(h0, 2), "job_id": r["job_id"], "seconds": r["seconds"],
                         "row": x["row"], "length_s": x["length_s"], "judged": x["judged"], "clears": x["clears"], "gap": x["gap"],
                         "cut": x["cut"], "reason": x["reason_code"],
                         "strongest": x["length_s"] == rv.get("suggested_window_s")})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(D, "motif_lengths_by_length.csv"), index=False)
    t["mark"] = t.apply(lambda x: "-" if not x.judged else (f"{x.gap:.1f}*" if x.clears else f"{x.gap:.1f}"), axis=1)
    t["run"] = t.recording + "@" + t.start_h.astype(str) + "h"
    t["rung_s"] = t.groupby("row").length_s.transform("min").round(0)
    print(t.pivot_table(index=["row", "rung_s"], columns="run", values="mark", aggfunc="first")
          .sort_index().to_string())


if __name__ == "__main__":
    main()
