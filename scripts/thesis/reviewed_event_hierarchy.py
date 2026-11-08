"""Separate reviewed observations, individual peak proposals, and ordered sequences.

No acceptance or boundary judgement is invented. A reviewed parent may support
several proposed children; their extents may overlap without merging identities.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.ndimage import gaussian_filter1d

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.thesis.mju_train_catalogue import propose
from scripts.thesis.accepted_catalogue import csv_write
from Working.interrogation.event_shape import measure_events, _is_drop
from Working.interrogation.intervals import interval_nulls
from Working.Detection.drop_motifs.detect5 import refine_onset,walk_back_to_shoulder
from scripts.thesis import figstyle as style
import matplotlib.pyplot as plt


def associate(start,end,peaks,fs):
    """All distinct extrema inside a parent; conservative fragment fallback."""
    hits=[i for i,p in enumerate(peaks) if start<=p['peak_idx']<end]
    if hits:return hits
    candidates=[]
    for i,p in enumerate(peaks):
        overlap=max(0,min(end,p['end_idx'])-max(start,p['start_idx']))
        gap=max(start-p['peak_idx'],p['peak_idx']-end,0)
        if overlap>=.5*(end-start) and gap<=min(120*fs,end-start):
            candidates.append((overlap/(1+gap),i))
    return [max(candidates)[1]] if candidates else []


def peak_identity(recording_id,peak_idx,polarity):
    return 'event-proposal-'+hashlib.sha256(f'{recording_id}:{peak_idx}:{polarity}'.encode()).hexdigest()[:16]


def case_analysis(project,data,out):
    rec=data['recordings']['663'];fs=10.;a,b=13770245,17034004
    x=np.asarray(np.load(project/rec['npy_path'],mmap_mode='r')[a:b],dtype=float)*1000
    sources=[r for r in data['observations'] if r.get('run_id')==8750 and r['accepted']]
    sensitivity=[];selected=None
    for floor in (.5,1.,2.):
        pp=propose(x,fs,prominence_mv=floor,min_separation_s=3.)
        links={r['ref']:associate(r['canonical_start']-a,r['canonical_end']-a,pp,fs) for r in sources}
        used=sorted({i for ids in links.values() for i in ids})
        timing=interval_nulls([pp[i]['peak_idx']/fs for i in used],n_draws=1000,seed=20261108,resolution_s=.1)
        sensitivity.append({'prominence_mv':floor,'all_peaks':len(pp),'supported_peaks':len(used),
                            'unresolved_observations':sum(not v for v in links.values()),
                            'observations_with_several_peaks':sum(len(v)>1 for v in links.values()),
                            'lv':timing['poisson']['lv']['observed'],'cv2':timing['poisson']['cv2']['observed'],
                            'lv_poisson_p':timing['poisson']['lv']['p'],'lv_shuffle_p':timing['shuffle']['lv']['p']})
        if floor==1.:selected=(pp,links,used)
    pp,links,used=selected
    smooth=gaussian_filter1d(x,.5*fs)
    # Baseline shoulders are bounded after the preceding extremum. This keeps
    # an earlier event's long recovery from becoming the next event's identity.
    onsets=[]
    for i,p in enumerate(pp):
        peak=p['peak_idx'];back=max(pp[i-1]['peak_idx']+1 if i else 0,peak-round(300*fs))
        segment=smooth[back:peak+1]
        onset=back+int(refine_onset(np.gradient(segment),0,len(segment)-1)) if len(segment)>2 else max(0,peak-1)
        onset=walk_back_to_shoulder(smooth,onset,backstop=back)
        onsets.append(min(onset,peak-1))
    features,_=measure_events(x,onsets,[p['peak_idx']+1 for p in pp],fs,polarity='drop',to_mv=1.,
                              anchors=list(zip(onsets,[p['peak_idx'] for p in pp])),recovery_max_mult=100000.)
    ff=json.loads(features.to_json(orient='records'))
    children=[]
    for i in used:
        p=pp[i];onset=onsets[i];peak=p['peak_idx'];stop=onsets[i+1] if i+1<len(onsets) else len(x)
        target=smooth[peak]+.95*(smooth[onset]-smooth[peak])
        crossing=np.flatnonzero(smooth[peak:stop]>=target)
        end=peak+int(crossing[0])+1 if len(crossing) else stop
        children.append({'event_id':peak_identity(663,a+peak,-1),'recording_id':663,'polarity':-1,
                         'start_idx':a+onset,'end_idx':a+max(peak+1,end),'peak_idx':a+peak,
                         'peak_s':(a+peak)/fs,'onset_s':(a+onset)/fs,
                         'source_refs':[ref for ref,ids in links.items() if i in ids],
                         'boundary_status':'machine_proposed','acceptance_basis':'accepted source observations',
                         'independent_human_child_verdict':False,'recovery_95_censored':not bool(len(crossing)),
                         **ff[i]})
    # Existing core feature indices were local; expose global physical indices.
    for child in children:
        for key in ('onset_idx','extremum_idx','recovery_idx'):
            if child[key] is not None:child[key]+=a
    peaks=np.array([r['peak_s'] for r in children]);gaps=np.diff(peaks)
    null=interval_nulls(peaks,n_draws=1000,seed=20261108,resolution_s=.1)
    depths=np.array([r['event_amplitude_mv'] if r['event_amplitude_mv'] is not None else np.nan for r in children])
    recov=np.array([r['recovery_time_s'] if r['recovery_time_s'] is not None else np.nan for r in children])
    def quant(v):return dict(zip(('p05','median','p95'),map(float,np.nanpercentile(v,[5,50,95]))))
    thirds=np.array_split(np.arange(len(children)),3)
    summary={'source_positive_observations':len(sources),'proposed_individual_events':len(children),
             'source_observations_with_several_peaks':sum(len(v)>1 for v in links.values()),
             'unresolved_source_refs':[ref for ref,ids in links.items() if not ids],
             'sensitivity':sensitivity,'span_hours':(b-a)/fs/3600,'peak_interval_s':quant(gaps),
             'amplitude_mv':quant(depths),'half_recovery_s':quant(recov),
             'half_recovery_missing':int(np.isnan(recov).sum()),'recovery_95_censored':sum(r['recovery_95_censored'] for r in children),
             'first_middle_last_amplitude_medians':[float(np.nanmedian(depths[t])) for t in thirds],
             'interval_nulls':null,'counting_unit':'individual supported extrema; not merged recovery windows',
             'status':'exploratory case; proposed boundaries; not an exhaustive spike census'}
    csv_write(out/'ch14_individual_proposals.csv',children)
    (out/'ch14_case.json').write_text(json.dumps({'summary':summary,'children':children,'source_to_child_indices':links},indent=2),encoding='utf-8')
    # Separate figures for timing and anatomy, avoiding a page of unexplained box plots.
    style.apply();fig,axs=plt.subplots(2,2,figsize=(6.3,5.5),layout='constrained')
    axs[0,0].plot(peaks/3600,depths,'.',ms=2,color=style.colour('MJu26a'))
    axs[0,0].set(xlabel='Recording time (h)',ylabel='Onset-to-trough depth (mV)',title='Individual waveform amplitudes')
    axs[0,1].plot(peaks[1:]/3600,gaps/60,'.',ms=2,color=style.colour('MJu26a'))
    axs[0,1].set(xlabel='Recording time (h)',ylabel='Peak-to-peak interval (min)',title='Spacing changes along the train')
    axs[1,0].hist(gaps/60,bins=35,color=style.colour('MJu26a'),alpha=.8)
    axs[1,0].set(xlabel='Peak-to-peak interval (min)',ylabel='Number of intervals',title='The retained interval distribution')
    axs[1,1].hist(recov[np.isfinite(recov)],bins=30,color=style.colour('MJu26a'),alpha=.8)
    axs[1,1].set(xlabel='Time from trough to half recovery (s)',ylabel='Number of measured events',title=f'Half recovery ({np.isfinite(recov).sum()}/{len(recov)} measured)')
    for ax in axs.flat:ax.tick_params(labelsize=7);ax.title.set_fontsize(9)
    style.save(fig,'ch10_ch14_event_measures');plt.close(fig)
    # Show separated neighbouring events, keeping context even where extents touch.
    fig,axs=plt.subplots(3,1,figsize=(6.3,5.4),layout='constrained')
    for ax,t in zip(axs,thirds):
        mid=int(t[len(t)//2]);rr=children[max(0,mid-2):mid+3]
        lo=max(0,min(r['start_idx'] for r in rr)-a-300);hi=min(len(x),max(r['end_idx'] for r in rr)-a+300)
        tt=np.arange(lo,hi)/fs
        ax.plot(tt/60,x[lo:hi],color=style.INK,lw=.65)
        for j,r in enumerate(rr):
            ax.axvspan((r['start_idx']-a)/fs/60,(r['end_idx']-a)/fs/60,color=style.CATEGORICAL[j%len(style.CATEGORICAL)],alpha=.17)
            p=r['peak_idx']-a;ax.plot(p/fs/60,x[p],'o',ms=3,color=style.INK)
        ax.set(xlabel='Minutes from start of the 90.7-hour selection',ylabel='mV')
        ax.tick_params(labelsize=7)
    style.save(fig,'ch10_ch14_separate_events');plt.close(fig)
    return summary,children


def family_hierarchy(project,data,out):
    recs={int(k):v for k,v in data['recordings'].items()};cache={};parents=[];events={}
    for parent in [e for e in data['events'] if 46 in e['queue_ids'] and e['thesis_scope']]:
        rec=recs[parent['recording_id']];fs=rec['fs'];rid=rec['id'];s,e=parent['start_idx'],parent['end_idx']
        if rid not in cache:cache[rid]=np.load(project/rec['npy_path'],mmap_mode='r')
        arr=cache[rid];pad=max(round(300*fs),min(round(3600*fs),2*(e-s)))
        a,b=max(0,s-pad),min(len(arr),e+pad)
        x=np.asarray(arr[a:b],dtype=float)*{'V':1000.,'mV':1.,'uV':.001}[rec['units']]
        core=x[s-a:e-a];drop=_is_drop(core,'auto');sign=-1 if drop else 1
        noise=1.4826*np.median(np.abs(np.diff(core))) if len(core)>1 else 0.
        floor=max(.1,6*noise,.2*float(np.ptp(gaussian_filter1d(core,max(.5,.5*fs)))))
        pp=propose(x if drop else -x,fs,prominence_mv=floor,min_separation_s=3.)
        oriented=gaussian_filter1d(x if drop else -x,max(.5,.5*fs));onsets=[]
        for i,p in enumerate(pp):
            peak=p['peak_idx'];back=max(pp[i-1]['peak_idx']+1 if i else 0,peak-round(300*fs))
            segment=oriented[back:peak+1]
            onset=back+int(refine_onset(np.gradient(segment),0,len(segment)-1)) if len(segment)>2 else max(0,peak-1)
            onsets.append(min(walk_back_to_shoulder(oriented,onset,backstop=back),peak-1))
        ids=associate(s-a,e-a,pp,fs);children=[]
        for i in ids:
            p=pp[i];peak=a+p['peak_idx'];eid=peak_identity(rid,peak,sign);children.append(eid)
            local=p['peak_idx'];stop=onsets[i+1] if i+1<len(onsets) else len(x)
            target=oriented[local]+.95*(oriented[onsets[i]]-oriented[local])
            crossing=np.flatnonzero(oriented[local:stop]>=target)
            end=local+int(crossing[0])+1 if len(crossing) else stop
            record=events.setdefault(eid,{'event_id':eid,'recording_id':rid,'peak_idx':peak,'polarity':sign,
                'start_idx':a+onsets[i],'end_idx':a+max(local+1,end),'boundary_status':'machine_proposed',
                'recovery_95_censored':not bool(len(crossing)),
                'acceptance_basis':'accepted parent span; not independent child judgements',
                'parent_ids':[],'source_refs':[]})
            record['parent_ids'].append(parent['event_id']);record['source_refs']=sorted(set(record['source_refs']+parent['source_refs']))
        role='sequence_parent' if len(children)>1 else 'single_event_observation' if children else 'unresolved_observation'
        parents.append({**parent,'component_role':role,'individual_event_ids':children,'prominence_floor_mv':floor,
                        'boundary_status':'machine_suggestions_awaiting_explicit_check'})
    summary={'parent_observations':len(parents),'roles':dict(Counter(p['component_role'] for p in parents)),
             'distinct_individual_proposals':len(events),'source_to_child_links':sum(len(p['individual_event_ids']) for p in parents),
             'max_children_in_one_parent':max(len(p['individual_event_ids']) for p in parents),
             'database_verdicts_written':0,'rule':'distinct canonical extrema remain separate even with overlapping recoveries'}
    (out/'family_hierarchy.json').write_text(json.dumps({'summary':summary,'parents':parents,'individual_events':list(events.values())},indent=2),encoding='utf-8')
    csv_write(out/'family_individual_proposals.csv',list(events.values()))
    csv_write(out/'family_parent_observations.csv',parents)
    examples=sorted([p for p in parents if len(p['individual_event_ids'])>1],key=lambda p:len(p['individual_event_ids']))
    picked=[examples[i] for i in np.linspace(0,len(examples)-1,4,dtype=int)]
    fig,axes=plt.subplots(4,1,figsize=(6.3,7),layout='constrained')
    for ax,parent in zip(axes,picked):
        rid=parent['recording_id'];rec=recs[rid];fs=rec['fs'];s,e=parent['start_idx'],parent['end_idx']
        a,b=max(0,s-round(120*fs)),min(rec['n_samples'],e+round(120*fs))
        y=np.asarray(cache[rid][a:b],dtype=float)*{'V':1000.,'mV':1.,'uV':.001}[rec['units']]
        step=max(1,int(np.ceil(len(y)/1800)));ii=np.arange(0,len(y),step);tt=(a+ii-s)/fs/60
        lo=np.minimum.reduceat(y,ii);hi=np.maximum.reduceat(y,ii)
        ax.fill_between(tt,lo,hi,color=style.INK,lw=.4)
        ax.axvspan(0,(e-s)/fs/60,color='#e7a93d',alpha=.12)
        for j,eid in enumerate(parent['individual_event_ids']):
            child=events[eid];col=style.CATEGORICAL[j%len(style.CATEGORICAL)]
            ax.axvspan((child['start_idx']-s)/fs/60,(child['end_idx']-s)/fs/60,color=col,alpha=.2)
            p=child['peak_idx'];ax.plot((p-s)/fs/60,float(cache[rid][p])*{'V':1000.,'mV':1.,'uV':.001}[rec['units']],'.',ms=4,color=col)
        ax.set_title(f"{parent['dataset'].replace('_',' ')} CH{parent['channel']+1}: one parent observation, {len(parent['individual_event_ids'])} separate proposals",fontsize=9)
        ax.set(xlabel='Minutes from parent-observation start',ylabel='mV');ax.tick_params(labelsize=7)
    style.save(fig,'ch9_event_sequence_hierarchy');plt.close(fig)
    return summary


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project-root',required=True,type=Path)
    ap.add_argument('--out',type=Path,default=ROOT/'docs/thesis/data/event_hierarchy_20261108');args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    data=json.loads((ROOT/'docs/thesis/data/accepted_catalogue/catalogue.json').read_text())
    case,_=case_analysis(args.project_root,data,args.out);family=family_hierarchy(args.project_root,data,args.out)
    print(json.dumps({'case':case,'family':family},indent=2),flush=True)


if __name__=='__main__':main()
