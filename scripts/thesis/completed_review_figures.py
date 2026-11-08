"""Read-only figures and full-waveform proposals for the completed review audit.

Context proposals NEVER write annotations or certify an individual event extent.
The original accepted spans and all their provenance remain the counting unit.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks, peak_widths

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.thesis import figstyle as style
from scripts.thesis.accepted_catalogue import csv_write
import matplotlib.pyplot as plt

ORDER = ["M2_aug", "M2_concat", "M4", "LM", "CO", "MJu26a", "SH", "SO"]


def propose(x, start, end, fs):
    """Prominence crossings suggest missing context, including peaks outside a fragment.

    Use one-second smoothing and 95%-prominence widths in a padded view. A
    candidate must cover at least half the accepted span or peak inside it.
    Several substantial same-polarity peaks are flagged rather than split.
    """
    pad = max(round(300*fs), min(round(3600*fs), 2*(end-start)))
    a, b = max(0, start-pad), min(len(x), end+pad)
    raw = np.asarray(x[a:b], dtype=float)
    if not np.isfinite(raw).all():
        return dict(start=start, end=end, context_start=a, context_end=b,
                    flags=["nonfinite"], peaks=0, extension_s=0., peak=None)
    smooth = gaussian_filter1d(raw, max(.5, fs))
    noise = 1.4826*np.median(np.abs(np.diff(raw)))
    candidates = []
    for sign in (-1, 1):
        peaks, props = find_peaks(sign*smooth, prominence=max(.1, 6*noise),
                                  distance=max(1, round(3*fs)))
        if not len(peaks):
            continue
        _, _, left, right = peak_widths(sign*smooth, peaks, rel_height=.95,
                                        prominence_data=(props["prominences"], props["left_bases"], props["right_bases"]))
        for p, prom, l, r in zip(peaks, props["prominences"], left, right):
            overlap = max(0, min(a+r, end)-max(a+l, start))
            near = max(start-(a+p), (a+p)-end, 0) <= min(120*fs, .5*(end-start))
            if start <= a+p < end or (near and overlap >= .5*(end-start)):
                candidates.append(dict(peak=int(a+p), prominence=float(prom), sign=sign,
                                       left=int(a+np.floor(l)), right=int(a+np.ceil(r)), overlap=overlap))
    if not candidates:
        return dict(start=start, end=end, context_start=a, context_end=b,
                    flags=["no isolated prominence crossing"], peaks=0, extension_s=0., peak=None)
    best = max(candidates, key=lambda z: z["prominence"]*min(1, z["overlap"]/(end-start)))
    strong = [z for z in candidates if z["sign"] == best["sign"] and
              start <= z["peak"] < end and z["prominence"] >= .25*best["prominence"]]
    s, e = min(start, best["left"]), max(end, best["right"]+1)
    flags = []
    if len(strong) > 1:
        flags.append("multiple substantial extrema; inspect split")
    if s < start-round(2*fs) or e > end+round(2*fs):
        flags.append("additional onset/recovery proposed")
    if best["left"] <= a+fs or best["right"] >= b-fs:
        flags.append("context limit reached")
    return dict(start=s, end=e, context_start=a, context_end=b,
                peak=best["peak"], prominence_mv=best["prominence"], polarity=best["sign"],
                peaks=len(strong), flags=flags, extension_s=((start-s)+(e-end))/fs)


def acceptance(audit):
    rows = {(r["recording"], r["group"]): r for r in audit["rq2"]["scores"]}
    order = ["M2_concat", "M4", "LM", "CO", "MJu26a", "SH", "SO", "All"]
    fig, ax = plt.subplots(figsize=(6.3, 3.45), layout="constrained")
    for j, group in enumerate(("control", "transfer_match")):
        yy = np.arange(len(order))+(j-.5)*.24
        rr = [rows[(r, group)] for r in order]
        xx = np.array([r["rate"]*100 for r in rr])
        low = xx-np.array([r["wilson95"][0]*100 for r in rr])
        high = np.array([r["wilson95"][1]*100 for r in rr])-xx
        ax.errorbar(xx, yy, xerr=np.maximum(0, [low, high]), fmt="o" if j else "s",
                    ms=4, color="#2a78d6" if j else "#9a9893", capsize=2,
                    label="Seed matches" if j else "Random controls")
        for y, r in zip(yy, rr):
            ax.text(108 if j else 126, y, f"{r['accepted']}/{r['reviewed']}",
                    va="center", ha="center", fontsize=8, color=style.INK if j else style.INK_2)
    ax.set_yticks(range(len(order)), [r.replace("_", " ") for r in order])
    ax.invert_yaxis(); ax.set_xlim(-3, 138); ax.set_xticks([0,25,50,75,100])
    ax.set_xlabel("Accepted presentations (%)")
    ax.text(108, -.75, "Seed", ha="center", fontsize=8)
    ax.text(126, -.75, "Control", ha="center", fontsize=8)
    ax.legend(loc="upper center", bbox_to_anchor=(.5,-.19), ncol=2, fontsize=8)
    ax.spines[['right','top']].set_visible(False)
    style.save(fig, "ch7_transfer_acceptance")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT/"docs/thesis/data/reviews_completed_20261108")
    args = ap.parse_args(); style.apply()
    audit = json.loads((args.out/"audit.json").read_text())
    data = json.loads((args.out/"catalogue.json").read_text())
    events = [e for e in data["events"] if e["thesis_scope"]]
    recs = {int(k): v for k,v in data["recordings"].items()}
    obs = {r["ref"]: r for r in data["observations"]}
    arrays = {}
    def channel(rid):
        if rid not in arrays:
            r = recs[rid]
            arrays[rid] = np.load(args.project_root/r["npy_path"], mmap_mode="r")
        return arrays[rid]
    proposals = []
    for e in events:
        r = recs[e["recording_id"]]
        unit = {"V":1000., "mV":1., "uV":.001}[r["units"]]
        # Slice before converting units, never materialise a whole channel.
        x = channel(e["recording_id"])
        pad = max(round(300*e["fs"]), min(round(3600*e["fs"]), 2*(e["end_idx"]-e["start_idx"])))
        a,b = max(0,e["start_idx"]-pad),min(len(x),e["end_idx"]+pad)
        local = np.asarray(x[a:b],dtype=float)*unit
        p = propose(local, e["start_idx"]-a, e["end_idx"]-a, e["fs"])
        for k in ("start","end","context_start","context_end","peak"):
            if p[k] is not None: p[k] += a
        p.update(event_id=e["event_id"],dataset=e["dataset"],recording_id=e["recording_id"],
                 original_start=e["start_idx"],original_end=e["end_idx"],queue_ids=e["queue_ids"],
                 protected_human_edit=any(obs[s]["source"] in {"review-span-edit","catalogue_boundary_review"} for s in e["source_refs"]),
                 boundary_status="machine suggestion; not an adjudicated extent")
        proposals.append(p)
    csv_write(args.out/"context_proposals.csv", proposals)
    summary = {"accepted_spans":len(events),"proposals_written_to_database":0,
               "with_suggested_extension_over_2s":sum(p["extension_s"]>2 for p in proposals),
               "multiple_extrema_flags":sum(p["peaks"]>1 for p in proposals),
               "by_queue":{str(q):{"linked_spans":sum(q in p["queue_ids"] for p in proposals),
                   "extension_over_2s":sum(q in p["queue_ids"] and p["extension_s"]>2 for p in proposals),
                   "multiple_extrema":sum(q in p["queue_ids"] and p["peaks"]>1 for p in proposals)} for q in (38,45,46)}}
    (args.out/"context_summary.json").write_text(json.dumps(summary,indent=2))
    acceptance(audit)
    # A compact catalogue-composition chart, with readable labels outside bars.
    fig, ax = plt.subplots(figsize=(6.3,2.8),layout="constrained")
    counts=Counter(e["dataset"] for e in events)
    ax.barh(ORDER,[counts[r] for r in ORDER],color=[style.colour(r) for r in ORDER])
    for i,r in enumerate(ORDER): ax.text(counts[r]+12,i,f"{counts[r]:,}",va="center",fontsize=9)
    ax.set_xlim(0,max(counts.values())*1.13);ax.invert_yaxis();ax.set_xlabel("Accepted spans after physical-copy and overlap reconciliation")
    ax.spines[['right','top']].set_visible(False);style.save(fig,"ch9_combined_catalogue");plt.close(fig)
    # Examples chosen by the size of missing context, not as an unbiased gallery.
    picked=[]
    for q in (46,45):
        pool=[p for p in proposals if q in p["queue_ids"] and p["extension_s"]>5 and p["peaks"]<=1 and not p["protected_human_edit"]]
        pool.sort(key=lambda p:p["extension_s"],reverse=True)
        # Quantiles avoid showing only the most extreme failures.
        for i in np.linspace(0,len(pool)-1,min(4,len(pool)),dtype=int): picked.append(pool[i])
    fig, axes=plt.subplots(4,2,figsize=(6.3,7.3),layout="constrained")
    for ax,p in zip(axes.T.flat,picked):
        e=next(e for e in events if e["event_id"]==p["event_id"]);r=recs[e["recording_id"]];fs=e["fs"]
        a,b=p["context_start"],p["context_end"];v=np.asarray(channel(e["recording_id"])[a:b],dtype=float)*({"V":1000.,"mV":1.,"uV":.001}[r["units"]])
        stride=max(1,len(v)//3000);t=(np.arange(a,b,stride)-e["start_idx"])/fs
        ax.plot(t,v[::stride],lw=.7,color=style.INK)
        ax.axvspan(0,e["span_s"],color="#eb6834",alpha=.30,label="Accepted span")
        ax.set_title(f"{e['dataset'].replace('_',' ')} CH{e['channel']+1} · {e['start_s']/3600:.2f} h",fontsize=8)
        ax.set_ylabel("mV");ax.set_xlabel("Seconds from accepted-span start",fontsize=8)
        ax.tick_params(labelsize=7)
    axes[0,0].legend(loc="best",fontsize=6)
    style.save(fig,"ch9_context_examples");plt.close(fig)
    # The newly reviewed long train is distinct from the historical excerpt;
    # show their physical relationship explicitly instead of counting copies.
    train=[e for e in events if 45 in e["queue_ids"]]
    rid=train[0]["recording_id"];r=recs[rid];fs=r["fs"];x=channel(rid)
    fig=plt.figure(figsize=(6.3,5.2),layout="constrained")
    grid=fig.add_gridspec(2,2,height_ratios=[1,1.1]);top=fig.add_subplot(grid[0,:])
    axes=[top,fig.add_subplot(grid[1,0]),fig.add_subplot(grid[1,1])]
    excerpt=recs[385];parent=recs[excerpt["parent_recording_id"]]
    excerpt_h=(excerpt["parent_offset"] / parent["fs"])/3600
    spans=[(13770245/fs,17034004/fs),(excerpt_h*3600,(excerpt_h+4)*3600),(426.99*3600-180,426.99*3600+420)]
    for i,(ax,(s,e)) in enumerate(zip(axes,spans)):
        a,b=int(s*fs),int(e*fs);v=np.asarray(x[a:b],dtype=float)*1000
        step=max(1,int(np.ceil(len(v)/1600)));starts=np.arange(0,len(v),step)
        low=np.minimum.reduceat(v,starts);high=np.maximum.reduceat(v,starts)
        tt=(a+starts)/fs/3600 if i<2 else starts/fs
        ax.fill_between(tt,low,high,color=style.INK,alpha=.8,lw=.3)
        ax.plot(tt,(low+high)/2,color=style.INK,lw=.5)
        hits=[ev for ev in train if ev["start_s"]<e and ev["end_s"]>s]
        if i==0:
            bottom=ax.get_ylim()[0]
            ax.plot([ev["start_s"]/3600 for ev in hits],[bottom]*len(hits),"|",color="#eb6834",ms=5)
            ax.axvspan(excerpt_h,excerpt_h+4,color="#2a78d6",alpha=.15)
            ax.set_title("Newly reviewed CH14 train; blue band marks the earlier four-hour excerpt",fontsize=8)
        else:
            for ev in hits:
                left=ev["start_s"]/3600 if i==1 else ev["start_s"]-s
                right=ev["end_s"]/3600 if i==1 else ev["end_s"]-s
                ax.axvspan(left,right,color="#eb6834",alpha=.28)
            ax.set_title("Earlier excerpt on the same physical channel" if i==1 else "One local view with accepted spans",fontsize=8)
        ax.set_ylabel("mV");ax.set_xlabel("Recording time (hours)" if i<2 else "Seconds from view start")
        ax.tick_params(labelsize=7)
    style.save(fig,"ch10_mju_ch14_reviewed_train");plt.close(fig)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=="__main__": main()
