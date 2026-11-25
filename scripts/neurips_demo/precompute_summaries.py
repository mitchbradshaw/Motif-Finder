"""Per builder setting, the two answers a station would otherwise compute on a visit: Discovery's summary (counts,
null, where it fires, per channel) and Judge five's picks (with the researcher's verdict where one covers the event).

    webui\\.venv\\Scripts\\python.exe scripts/neurips_demo/precompute_summaries.py

Run with the webui venv (it imports the station's own functions, so the files are exactly what the station would
compute: webui/server/demo_station.py `summary_of`, `judge_items`). Writes store/summary/<combo>.json and
store/judge/<combo>.json; a station reads them when present and computes when not.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "webui" / "server"))

import demo_station as DS  # noqa: E402


def main():
    os.chdir(ROOT)
    store = DS.Store(DS.STORE)
    out_s, out_j = DS.STORE / "summary", DS.STORE / "judge"
    out_s.mkdir(exist_ok=True)
    out_j.mkdir(exist_ok=True)
    t0 = time.perf_counter()
    n = 0
    for cid in store.combos:
        try:
            s = DS.summary_of(store, cid)
        except Exception as e:          # a setting whose chains are not all there yet
            print("skip", cid, e)
            continue
        (out_s / f"{cid}.json").write_text(json.dumps(s, separators=(",", ":")))
        (out_j / f"{cid}.json").write_text(json.dumps(DS.judge_items(store, cid), separators=(",", ":")))
        n += 1
    (out_s / "auto.json").write_text(json.dumps(DS.auto_summary(store), separators=(",", ":")))
    print(f"{n} settings summarised in {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
