import json, sqlite3, urllib.request, sys
sys.path.insert(0, r"C:/Users/mmebr/Documents/CNN")
DB = r"C:/Users/mmebr/Documents/CNN/webui/runtime/20260921-162340/annotations.sqlite"
conn = sqlite3.connect("file:"+DB+"?mode=ro", uri=True); conn.row_factory = sqlite3.Row
d = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/channels/4/tags"))
print("route: n_ann", len(d["annotations"]), "n_reviewed", len(d["reviewed"]), "reviewed_pct", d["reviewed_pct"])
print("route tag_counts", d["tag_counts"])
print("route vocab size", len(d["vocabulary"]))
a = conn.execute("SELECT COUNT(*) FROM annotations WHERE recording_id=4 AND deleted_at IS NULL").fetchone()[0]
rs = conn.execute("SELECT COUNT(*) FROM reviewed_spans WHERE recording_id=4").fetchone()[0]
print("sql ann", a, "sql reviewed_spans", rs)
tc = conn.execute("""SELECT v.category||':'||v.value k, COUNT(*) FROM annotation_tags t
 JOIN tag_vocabulary v ON v.id=t.tag_id JOIN annotations a ON a.id=t.annotation_id
 WHERE a.recording_id=4 AND a.deleted_at IS NULL GROUP BY k""").fetchall()
print("sql tag_counts", {r[0]:r[1] for r in tc})
vt = conn.execute("SELECT COUNT(*) FROM tag_vocabulary WHERE active=1").fetchone()[0]
print("sql active vocab", vt, "total vocab", conn.execute("SELECT COUNT(*) FROM tag_vocabulary").fetchone()[0])
from Working.database import queries as q
print("reviewed_fraction(4) =", q.reviewed_fraction(conn,4), "-> pct", q.reviewed_fraction(conn,4)*100)
# manual merge check
rows=conn.execute("SELECT start_idx,end_idx FROM reviewed_spans WHERE recording_id=4 ORDER BY start_idx").fetchall()
cov=0; cs=ce=None
for s,e in rows:
    if cs is None: cs,ce=s,e
    elif s<=ce: ce=max(ce,e)
    else: cov+=ce-cs; cs,ce=s,e
if cs is not None: cov+=ce-cs
n=conn.execute("SELECT n_samples FROM recordings WHERE id=4").fetchone()[0]
print("manual merged covered", cov, "/", n, "=", cov/n*100, "%")
