import json, sys, sqlite3, urllib.request
sys.path.insert(0, r"C:/Users/mmebr/Documents/CNN")
import numpy as np
from Working.Detection.drop_motifs import store as S, gradients as G
SEED = r"C:/Users/mmebr/Documents/CNN/DATA/library_seed/drop_motifs5/motifs"
events = S.load_events(SEED); snips = S.load_snippets(SEED)
print("events.csv n =", len(events), "snippets n =", len(snips))
from collections import Counter
c = Counter((e.get("span_key") or ("r%s"%e["recording_id"])) for e in events)
print("per-family from events.csv:", dict(sorted(c.items())))
d = json.load(open(r"C:/Users/mmebr/Documents/CNN/webui/screenshots/critique-01-data/fams.json"))
route = {f["id"]: f["n_members"] for f in d["families"]}
print("route == csv:", route == dict(c), " diff:", {k:(route.get(k),c.get(k)) for k in set(route)|set(c) if route.get(k)!=c.get(k)})
man = d["manifest"]["per_span"]
print("manifest per_span vs csv:", {("id%03d"%int(k)):v for k,v in man.items()} == dict(c))
# members of id001
m = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/interrogation/families/id001/members"))
csv1 = [e for e in events if (e.get("span_key") or "") == "id001"]
print("id001 route members", len(m["members"]), "csv", len(csv1))
bad=[]
for r, e in zip(m["members"], csv1):
    for k in ("onset_idx","trough_idx","snippet_start_idx","snippet_end_idx"):
        if int(r[k]) != int(e[k]): bad.append((r["event_id"],k,r[k],e[k]))
    for k in ("drop_depth_mv","fall_duration_s","onset_h","trough_h"):
        if abs(float(r[k])-float(e[k])) > 1e-9: bad.append((r["event_id"],k,r[k],e[k]))
print("member field mismatches:", bad[:10], "count", len(bad))
print("sample member:", {k:m["members"][0][k] for k in m["members"][0] if k!="snippet"})
print("snippet n reported", m["members"][0]["snippet"]["n"], "actual", len(snips[m["members"][0]["event_id"]]["t_s"]), "decimated pts", len(m["members"][0]["snippet"]["t_s"]))
# slope
sl = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/interrogation/families/id001/slope"))
grads = G.event_gradients(csv1, snips)
bad2=[]
for r,g,e in zip(sl["members"], grads, csv1):
    for k in ("onset_slope_mv_s","max_slope_mv_s","mean_slope_mv_s","peakedness","drop_depth_mv","fall_duration_s"):
        if k in g and r.get(k) is not None and abs(float(r[k])-float(g[k]))>1e-9: bad2.append((k,r[k],g[k]))
    if r["onset_offset"] != int(e["onset_idx"])-int(e["snippet_start_idx"]): bad2.append(("onset_offset",r["onset_offset"]))
    if r["trough_offset"] != int(e["trough_idx"])-int(e["snippet_start_idx"]): bad2.append(("trough_offset",r["trough_offset"]))
print("slope mismatches:", bad2[:10], len(bad2))
print("slope rose counts sum", sum(sl["rose"]["counts"]), "n members", len(sl["members"]))
# aggregate
ag = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/interrogation/families/id001/aggregate"))
print("aggregate n", ag["n"], "iei n", ag["distributions"]["inter_event_interval_s"]["n"], "expected", len(csv1)-1)
print("depth dist n", ag["distributions"]["drop_depth_mv"]["n"], "max_slope n", ag["distributions"]["max_slope_mv_s"]["n"])
depth = np.array([float(e["drop_depth_mv"]) for e in csv1])
print("depth median route", ag["distributions"]["drop_depth_mv"]["median"], "csv", float(np.median(depth)))
print("timeline len", len(ag["timeline"]))
# timeline pairing check: route zips order-index k with members[i] but uses depth[i]/slope[i] - verify onset monotonic
ons=[t["onset_h"] for t in ag["timeline"]]
print("timeline onset monotonic:", all(ons[i]<=ons[i+1] for i in range(len(ons)-1)))
by_id={e["event_id"]:e for e in csv1}
mm=[t for t in ag["timeline"] if abs(float(by_id[t["event_id"]]["drop_depth_mv"])-t["depth_mv"])>1e-9]
print("timeline depth mismatched rows:", len(mm), mm[:3])
