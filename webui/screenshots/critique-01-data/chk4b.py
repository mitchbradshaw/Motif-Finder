import json, sqlite3, sys
sys.path.insert(0, r"C:/Users/mmebr/Documents/CNN")
import numpy as np
DB = r"C:/Users/mmebr/Documents/CNN/webui/runtime/20260921-162340/annotations.sqlite"
conn = sqlite3.connect("file:"+DB+"?mode=ro", uri=True); conn.row_factory = sqlite3.Row
for r in conn.execute("SELECT id, channel, npy_path, n_samples FROM recordings WHERE source_file='M2_aug_concat_fs1.mat' ORDER BY channel"):
    a = np.load(r["npy_path"], mmap_mode="r")
    print(r["id"], "channel", r["channel"], r["npy_path"], "len", len(a), "db n_samples", r["n_samples"], "OK" if len(a)==r["n_samples"] else "LEN-MISMATCH")
d = json.load(open(r"C:/Users/mmebr/Documents/CNN/webui/screenshots/critique-01-data/cross.json"))
ch = [c for c in d["channels"] if c["id"]==4][0]
env = ch["envelope"]
print("envelope keys", list(env.keys()), "n pts", len(env["t"]))
y = np.asarray(np.load(r"DATA/derived/channels/M2_aug_concat_fs1/CH3.npy", mmap_mode="r")[1209600:1210800], dtype=float)
print("raw window min/max", y.min(), y.max())
for k in env:
    if k=="t": continue
    v=np.asarray(env[k],dtype=float)
    print(" env",k,"min",np.nanmin(v),"max",np.nanmax(v))
print("y_range", ch.get("y_range"))
