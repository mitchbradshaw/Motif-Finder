import json, sqlite3, sys
sys.path.insert(0, r"C:/Users/mmebr/Documents/CNN")
import numpy as np
from Working.cross_channel import classify_waveforms
DB = r"C:/Users/mmebr/Documents/CNN/webui/runtime/20260921-162340/annotations.sqlite"
conn = sqlite3.connect("file:"+DB+"?mode=ro", uri=True); conn.row_factory = sqlite3.Row
d = json.load(open(r"C:/Users/mmebr/Documents/CNN/webui/screenshots/critique-01-data/cross.json"))
print("route stride", d["stride"], "channels", len(d["channels"]))
s0, s1 = 1209600, 1210800
paths = {r["id"]: r["npy_path"] for r in conn.execute("SELECT id, npy_path FROM recordings WHERE source_file='M2_aug_concat_fs1.mat'")}
print("ref npy", paths[4])
ref = np.asarray(np.load(paths[4], mmap_mode="r")[s0:s1], dtype=float)
for ch in d["channels"]:
    rid = ch["id"]
    if ch["is_reference"]:
        print(rid, ch["name"], "reference", ch["lag_s"], ch["r"], ch["classification"]); continue
    y = np.asarray(np.load(paths[rid], mmap_mode="r")[s0:s1], dtype=float)
    lag, corr, cls = classify_waveforms(ref, y)
    match = (abs(float(lag) - ch["lag_s"]) < 1e-9) and (abs(float(corr) - ch["r"]) < 1e-9) and cls == ch["classification"]
    print(f"{rid} {ch['name']}: route lag={ch['lag_s']} r={ch['r']:.10f} cls={ch['classification']} | recomputed lag={lag} r={corr:.10f} cls={cls} | {'OK' if match else 'MISMATCH'}")
