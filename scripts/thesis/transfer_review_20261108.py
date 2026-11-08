"""Prepare a blind, fixed-threshold cross-recording drop panel using existing Review machinery."""
import argparse
from collections import Counter, defaultdict
import datetime
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import numpy as np

MAIN = Path("C:/Users/mmebr/Documents/CNN")
sys.path.insert(0, str(MAIN))
from Working.review import queues
from Working.discovery.matching import match_quality, rule_from_settings
from scripts import rq2_blind

STAMP = "20261108-drop-transfer"
KEY = MAIN / "DATA/derived/rq2_blind" / STAMP
DB = MAIN / "DATA/db/annotations.sqlite"


def load_panel(conn):
    root = MAIN / "DATA/derived/hpc/rq2_drop_transfer_20261107"
    manifest = json.loads((root / "manifest.json").read_text())
    rng = np.random.default_rng(20261108)
    matches, blocked, arrays, records = [], defaultdict(list), {}, {}
    prior = defaultdict(list)
    rule = rule_from_settings(conn)
    for rid, start, end in conn.execute(
            "SELECT r.recording_id,d.start_idx+r.span_start,d.end_idx+r.span_start "
            "FROM adjudications a JOIN detections d ON d.id=a.detection_id JOIN runs r ON r.id=d.run_id "
            "WHERE a.carried_from IS NULL"):
        prior[rid].append((start, end))
    raw = 0
    excluded = Counter()
    for d in manifest["datasets"]:
        spec = json.loads((MAIN / d["spec_path"]).read_text())
        parts = (MAIN / d["spec_path"]).parent / (Path(d["spec_path"]).name.replace(".spec.json", "") + "_parts")
        for ch in spec["channels"]:
            rec = conn.execute("SELECT id,npy_path,n_samples,fs FROM recordings WHERE source_file=? AND channel=?",
                               (ch["source_file"], ch["channel"])).fetchone()
            if rec is None:
                raise ValueError("Target recording is not registered")
            rid = int(rec[0])
            records[rid] = {"recording": d["recording"], "channel": ch["name"], "fs": rec[3]}
            arrays[rid] = np.load(MAIN / rec[1], mmap_mode="r")
            p = parts / (Path(d["spec_path"]).name.replace(".spec.json", "") + "__" + ch["name"] + ".result.json")
            result = json.loads(p.read_text())
            from Working.discovery.seed_job import spec_hash
            if result["specHash"] != spec_hash(dict(spec, channels=[ch])):
                raise ValueError("Seed result/spec mismatch")
            # Real-signal matching is already complete even where surrogate draws remain partial.
            for c in result["perChannel"][0]["candidates"]:
                if c["distance"] > manifest["frozen_m2_aug_cut"]:
                    continue
                raw += 1
                start, end = int(c["index"]), int(c["index"] + c.get("length", d["match_samples"]))
                blocked[rid].append((start, end))
                if np.isfinite(arrays[rid][start:end]).mean() < 0.95:
                    excluded["unreadable"] += 1
                    continue
                if any(match_quality((start, end), p, rule=rule)["ok"] for p in prior[rid]):
                    excluded["earlier_adjudication"] += 1
                    continue
                matches.append({"group": "transfer_match", "seed": "drop30",
                                "recording": d["recording"], "recording_id": rid, "channel": ch["name"],
                                "start": start, "end": end, "length": end-start,
                                "source": {"distance": c["distance"], "frozen_cut": manifest["frozen_m2_aug_cut"]},
                                "earlier": None})
    # Match the Review resolver's manual-annotation exclusion as well.
    candidates = [(it["recording_id"], it["start"], it["end"]) for it in matches]
    annotated = rq2_blind._prior(conn, candidates)
    excluded["earlier_annotation"] = len(annotated)
    matches = [it for i, it in enumerate(matches) if i not in annotated]
    unique = {}
    for it in matches:
        unique.setdefault((it["recording_id"], it["start"], it["end"]), it)
    excluded["duplicate_span"] = len(matches)-len(unique)
    matches = list(unique.values())
    controls = []
    annotations = queues._annotations_by_recording(conn, set(records))
    for it in matches:
        rid, length = it["recording_id"], it["length"]
        x = arrays[rid]
        for _ in range(50000):
            start = int(rng.integers(0, len(x)-length+1)); end = start+length
            if any(start < b and end > a for a,b in blocked[rid]):
                continue
            if np.isfinite(x[start:end]).mean() < 0.95:
                continue
            if any(match_quality((start,end), p, rule=rule)["ok"] for p in prior[rid]):
                continue
            if any(match_quality((start,end),(a,b),rule=rule)["ok"]
                   for a,b,*_ in annotations.get(rid,[])):
                continue
            controls.append({**it, "group":"control", "seed":None, "start":start, "end":end,
                             "control_length":length, "source":{"uniform":True}, "earlier":None})
            blocked[rid].append((start,end))
            break
        else:
            raise ValueError("Could not draw a matched random control")
    first = matches + controls
    # Repeated fresh detections assess within-session judgement reliability across both sources.
    n_repeat = round(len(first) * .05)
    repeats = [{**first[int(i)], "group":"repeat",
                "source":{"repeat_of": {"recording_id":first[int(i)]["recording_id"],
                                       "start":first[int(i)]["start"],"end":first[int(i)]["end"],
                                       "group":first[int(i)]["group"]}}}
               for i in rng.choice(len(first),size=n_repeat,replace=False)]
    items = rq2_blind.shuffle(rng, first+repeats)
    composition = {"raw_fixed_threshold_matches":raw,"exclusions":dict(excluded),
                   "by_group":dict(Counter(i["group"] for i in items)),
                   "matches_by_recording":dict(Counter(i["recording"] for i in matches)),
                   "total":len(items),"duration_s":377,"random_seed":20261108}
    return items, composition


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--release-repeats", action="store_true")
    p.add_argument("--score", action="store_true")
    a=p.parse_args()
    if a.score:
        key=json.loads((KEY/"key.json").read_text())
        conn=sqlite3.connect(DB.as_uri()+"?mode=ro",uri=True)
        presentations=key["presentations"]
        verdicts=rq2_blind._verdicts(conn,[it["panel_detection_id"] for it in presentations])
        groups=defaultdict(list)
        for it in presentations:
            verdict,carried=verdicts.get(it["panel_detection_id"],(None,False))
            if verdict is not None and not carried:
                groups[(it["recording"],it["group"])].append(verdict)
        stats=[]
        for (rec,group),vs in sorted(groups.items()):
            accepted=sum(v in rq2_blind.ACCEPTED for v in vs)
            stats.append({"recording":rec,"group":group,"reviewed":len(vs),"accepted":accepted,
                          "rate":accepted/len(vs),"wilson95":rq2_blind.wilson(accepted,len(vs)),
                          "verdicts":dict(Counter(vs))})
        out={"queue_id":key["queue_id"],"planned_presentations":len(presentations),
             "own_reviews":sum(r["reviewed"] for r in stats),"results":stats}
        (KEY/"scores.json").write_text(json.dumps(out,indent=2))
        print(json.dumps(out,indent=2));conn.close()
        return
    if a.release_repeats:
        assignment=KEY/"repeat_assignment.json"
        if assignment.exists():
            print("Planned repeats are already assigned to queue",json.loads(assignment.read_text())["queue_id"])
            return
        key=json.loads((KEY/"key.json").read_text())
        conn=sqlite3.connect(DB);conn.row_factory=sqlite3.Row
        if queues.queue_counts(conn,key["queue_id"])["remaining"]:
            raise SystemExit("Finish the primary queue before releasing the repeat queue.")
        repeat_key=KEY/"retest"/"key.json"
        if repeat_key.exists():
            print("Repeat queue already exists:",json.loads(repeat_key.read_text())["queue_id"])
            return
        reserved=json.loads((KEY/"repeat_reserve.json").read_text())
        repeat_items=rq2_blind.shuffle(np.random.default_rng(20261109),reserved)
        result=rq2_blind.write_panel(conn,repeat_items,stamp=STAMP+"-repeat",key_dir=str(KEY/"retest"),
                                    make_queue=rq2_blind.bridge_queue("http://127.0.0.1:8765"),
                                    extra_key={"primary_queue_id":key["queue_id"]},db_path=str(DB))
        print(json.dumps({"repeat_queue_id":result["queue_id"],"items":len(repeat_items)}))
        return
    conn=sqlite3.connect(DB.as_uri()+"?mode=ro",uri=True)
    conn.row_factory=sqlite3.Row
    items,composition=load_panel(conn)
    print(json.dumps(composition,indent=2),flush=True)
    if not a.apply:
        conn.close()
        return
    KEY.mkdir(parents=True,exist_ok=True)
    if (KEY/"key.json").exists():
        print("Existing panel retained:",(KEY/"key.json").read_text()[:180])
        return
    backup=MAIN/"DATA/db/backups"/("before_drop_transfer_review_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".sqlite")
    backup.parent.mkdir(exist_ok=True)
    with sqlite3.connect(backup) as dest:
        conn.backup(dest)
    conn.close()
    conn=sqlite3.connect(DB)
    conn.row_factory=sqlite3.Row
    reserve=[it for it in items if it["group"]=="repeat"]
    items=[it for it in items if it["group"]!="repeat"]
    (KEY/"repeat_reserve.json").write_text(json.dumps(reserve,indent=2))
    result=rq2_blind.write_panel(conn,items,stamp=STAMP,key_dir=str(KEY),
                                make_queue=rq2_blind.bridge_queue("http://127.0.0.1:8765"),
                                extra_key={"composition":composition,"protocol":"frozen-cut cross-recording transfer",
                                           "repeat_policy":"46 repeats held outside the app until primary review is complete, avoiding automatic verdict carrying",
                                           "surrogate_calculation":"MJu26a CH6-10 incomplete at queue creation; real matching complete",
                                           "historical_exam":"Separate follow-up after the frozen 28 October M4 exam"},
                                db_path=str(DB))
    # No scores, source labels, verdicts, Library entries or promotions are written.
    counts=queues.queue_counts(conn,result["queue_id"])
    live=queues.queue_items(conn,result["queue_id"],include_judged=True,include_prior_judged=True)
    by_id={it["panel_detection_id"]:it for it in result["items"]}
    presentations=[]
    for row in live:
        anchor=by_id[row["target_id"]]
        members=row.get("members") or [row["target_id"]]
        assert len({by_id[int(d)]["group"] for d in members})==1
        presentations.append({**anchor,"represented_detection_ids":members})
    key_path=Path(result["key_path"]);key=json.loads(key_path.read_text())
    key["presentations"]=presentations
    key["presentation_count"]=len(presentations)
    key["presentation_groups"]=dict(Counter(i["group"] for i in presentations))
    key_path.write_text(json.dumps(key,indent=2))
    conn.close()
    print(json.dumps({"queue_id":result["queue_id"],"items":len(items),"counts":counts,
                      "key_path":result["key_path"],"backup":str(backup)},indent=2))


if __name__=="__main__":
    main()
