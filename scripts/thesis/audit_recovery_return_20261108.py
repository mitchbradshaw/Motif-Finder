"""Verify returned recovery tasks without executing any detector or touching the DB."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path("C:/Users/mmebr/Documents/CNN")
sys.path.insert(0, str(ROOT))
from Working.discovery.chain_job import spec_hash
from scripts.thesis.accepted_catalogue import csv_write


def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4*1024**2),b''):h.update(block)
    return h.hexdigest()


def seed_audit(out):
    import numpy as np
    from Working.discovery.seed_job import spec_hash as seed_hash
    from Working.discovery.seeded_search import recommended_cut_corrected
    root=MAIN/'DATA/derived/hpc/rq2_drop_transfer_20261107'
    manifest=json.loads((root/'manifest.json').read_text())
    summaries=[]
    for d in manifest['datasets']:
        p=MAIN/d['spec_path'];spec=json.loads(p.read_text());stem=p.name.replace('.spec.json','')
        parts=p.parent/(stem+'_parts');channels=[]
        for ch in spec['channels']:
            r=json.loads((parts/(stem+'__'+ch['name']+'.result.json')).read_text())
            assert r['specHash']==seed_hash(dict(spec,channels=[ch]))
            assert r['complete'] and len(r['perChannel'])==1
            result=r['perChannel'][0]
            assert result['null']['draws']==200
            assert len(result['null']['distances'])==200*200
            assert all(np.isclose(c.get('length',d['match_samples'])/result['fs'],377) for c in result['candidates'])
            channels.append(result)
        recal=recommended_cut_corrected([{'distances':[c['distance'] for c in ch['candidates']],
                                         'null':ch['null']} for ch in channels],alpha=.01,correction='none')
        row={'recording':d['recording'],'channels':len(channels),'hours':d['recording_hours']}
        for label,cut in [('fixed',manifest['frozen_m2_aug_cut']),('recalibrated',recal['cut'])]:
            real=sum(c['distance']<=cut for ch in channels for c in ch['candidates']) if cut is not None else 0
            null=sum(int((np.asarray(ch['null']['distances'])<=cut).sum()) for ch in channels) if cut is not None else 0
            row.update({label+'_cut':cut,label+'_matches':real,label+'_null_total':null,
                        label+'_null_mean_per_draw':null/200,
                        label+'_capped_channels':sum(sum(c['distance']<=cut for c in ch['candidates'])==200 for ch in channels) if cut is not None else 0})
        summaries.append(row)
    csv_write(out/'seed_summary.csv',summaries)
    (out/'seed_summary.json').write_text(json.dumps(summaries,indent=2))
    return summaries


def main():
    base = MAIN / "DATA/derived/hpc/recovery_20261108"
    out = ROOT / "docs/thesis/data/recovery_return_20261108"
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((base/"manifest.json").read_text())
    bad_runtime=[p for p,h in manifest['runtime_hashes'].items() if digest(base/p)!=h]
    bad_models=[p for p,h in manifest['model_hashes'].items() if digest(MAIN/p)!=h]
    assert not bad_runtime and not bad_models,(bad_runtime,bad_models)
    original = json.loads((ROOT/"docs/thesis/data/hpc_return_20261108/audit.json").read_text())
    recovered, bad = [], []
    for t in manifest["tasks"]:
        if t["kind"] != "rq4":
            continue
        p = MAIN/t["out"]/"return"/f"task{t['task']}"/"result.json"
        spec = json.loads((base/t["spec_copy"]).read_text())
        assert spec_hash(spec) == t["specHash"], t["id"]
        row = {**t, "state": "missing", "cache_ok": False}
        if p.exists():
            r = json.loads(p.read_text())
            assert r["specHash"] == t["specHash"] and r["task"] == t["task"], t["id"]
            row.update(state="failed" if r.get("error") else "complete" if r.get("complete") else "partial",
                       error=r.get("error"), elapsed_s=r.get("elapsedS"),
                       result=str(p.relative_to(MAIN)), real=(r.get("run") or {}).get("detections"),
                       null=(r.get("draws") or {}).get("detections"))
            if row["state"] == "complete":
                for cache in r.get("cache", []):
                    folder = (p.parent/cache["path"]).resolve()
                    assert folder.is_relative_to(p.parent.resolve()), str(folder)
                    size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
                    if not folder.is_dir() or size != cache["bytes"]:
                        bad.append({"task": t["id"], "cache": str(folder), "expected": cache["bytes"], "bytes": size})
                row["cache_ok"] = not any(b["task"] == t["id"] for b in bad)
        recovered.append(row)
    lookup = {(r["original_out"], r["task"]): r for r in recovered}
    all_tasks = []
    for old in original["rq4"]:
        new = lookup.get((old["out"].replace("\\", "/"), old["task"]))
        row = dict(old)
        if new and new["state"] == "complete" and new["cache_ok"]:
            row.update(state="complete", result=new["result"], run_detections=new["real"],
                       null_detections=new["null"], recovered=True)
        all_tasks.append(row)
    assert len(all_tasks) == 1014
    assert len({(r["spec"],r["task"]) for r in all_tasks}) == 1014
    grouped = defaultdict(list)
    for r in all_tasks:
        grouped[(r["recording"],r["setting"])].append(r)
    settings = []
    for (rec,setting), rr in sorted(grouped.items()):
        done = [r for r in rr if r["state"] == "complete"]
        settings.append({"recording":rec,"setting":setting,"complete":len(done),"total":len(rr),
                         "whole":len(done)==len(rr),
                         "real_detections":sum(r["run_detections"] or 0 for r in done),
                         "null_detections":sum(sum(r["null_detections"] or []) for r in done)})
    seeds=seed_audit(out)
    summary = {"recovery_by_pack":{p:dict(Counter(r["state"] for r in recovered if r["pack"]==p)) for p in manifest["packs"] if p!="seed"},
               "invalid_return_caches":bad,
               "overall_tasks":dict(Counter(r["state"] for r in all_tasks)),
               "by_recording":{rec:{"complete":sum(r["state"]=="complete" for r in all_tasks if r["recording"]==rec),
                                    "total":sum(r["recording"]==rec for r in all_tasks),
                                    "whole_settings":sum(s["whole"] for s in settings if s["recording"]==rec),
                                    "settings":sum(s["recording"]==rec for s in settings)} for rec in sorted({r["recording"] for r in all_tasks})},
               "seed_channels_complete_and_hash_checked":sum(r['channels'] for r in seeds),
               "seed_draws_per_channel":200,
               "frozen_science_unchanged":True}
    (out/"audit.json").write_text(json.dumps({"summary":summary,"recovery_tasks":recovered,"all_tasks":all_tasks,"settings":settings},indent=2))
    csv_write(out/"settings.csv",settings)
    csv_write(out/"pending.csv",[r for r in recovered if r["state"]!="complete"])
    print(json.dumps(summary,indent=2),flush=True)


if __name__=="__main__": main()
