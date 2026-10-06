"""fixup-aj walk: a copy of AI's lab sandbox (pool 712f477b262b2fd8, forest run 399, CNN smoke run 401) with run 401
taken out, so handing the smoke's job folder to the Manifest inbox is a first import, not 'already imported'."""
import os
import sqlite3

S = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(S, "..", "lab", "annotations.sqlite")
DST = os.path.join(S, "walk_src.sqlite")
if os.path.exists(DST):
    os.remove(DST)
src = sqlite3.connect(f"file:{os.path.abspath(SRC)}?mode=ro", uri=True)
dst = sqlite3.connect(DST)
src.backup(dst)
src.close()
row = dst.execute("SELECT config_id, name FROM runs WHERE id = 401").fetchone()
print("run 401:", row)
dst.execute("DELETE FROM artifacts WHERE run_id = 401")
dst.execute("DELETE FROM runs WHERE id = 401")
dst.execute("DELETE FROM configs WHERE id = ? AND NOT EXISTS (SELECT 1 FROM runs WHERE config_id = ?)", (row[0], row[0]))
dst.commit()
print("b2 runs left:", dst.execute("SELECT r.id, r.name FROM runs r JOIN configs c ON c.id = r.config_id WHERE "
                                  "json_extract(c.config_json, '$.kind') LIKE 'shape_cluster%'").fetchall())
print("templates:", dst.execute("SELECT id, name FROM templates WHERE id = 14").fetchall())
dst.close()
