"""Prepare <=850 blinded looks: 750 diverse proposals, 54 controls, 46 planned repeats.

Use completed classical-detector returns and registered real runs. The unfinished
CNNs and their agreement counts do not determine selection. Human labels are
never written at preparation. Canonical physical coordinates prevent alias copies
from creating duplicate candidates. Repeat identities remain in an ignored key.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict, OrderedDict
import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks, peak_widths

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.thesis.accepted_catalogue import canonical_span,collect,connect,csv_write
from scripts.thesis.reviewed_event_hierarchy import peak_identity
from Working.database.queries import not_surrogate
from Working.discovery.spans import absolute_bounds,legacy_ambiguous
from Working.discovery.chain_job import spec_hash
from Working.interrogation.event_shape import _is_drop
from Working.review import queues
from scripts import rq2_blind

MAIN=Path('C:/Users/mmebr/Documents/CNN')
STAMP='20261108-diversity-and-repeats'
QUOTAS={'SH':200,'SO':200,'MJu26a':150,'M2_concat':75,'CO':75,'LM':25,'M4':25}
FILES={'SH':'SH_fs2.mat','SO':'SO_fs2.mat','MJu26a':'MJu26a_fs2.mat',
       'M2_concat':'M2_concat_fs1.mat','CO':'CO_fs2.mat','LM':'LM_fs2.mat','M4':'M4_aug_concat_fs1.mat'}
BY_FILE={v:k for k,v in FILES.items()}


def conflict(rid,s,e,prior):
    return any(min(e,b)>max(s,a) for a,b in prior.get(rid,()))


def raw_pool(c,recs,rng):
    raw=[];sources=Counter()
    # Registered runs: root recipe.surrogate requests a paired null; the run's
    # surrogate_of_run_id identifies which side actually produced detections.
    for run in c.execute(f"""SELECT r.*,cf.config_json,rec.source_file,rec.n_samples,
        (SELECT COUNT(*) FROM detections d WHERE d.run_id=r.id) n
        FROM runs r JOIN configs cf ON cf.id=r.config_id JOIN recordings rec ON rec.id=r.recording_id
        WHERE r.status='completed' AND r.superseded_at IS NULL AND {not_surrogate('r')}
        AND rec.source_file IN ({','.join('?' for _ in FILES)})""",list(FILES.values())):
        cfg=json.loads(run['config_json']);steps=cfg.get('steps',[])
        if not steps or any('cnn' in s['algorithm'] or 'seed_match' in s['algorithm'] for s in steps):continue
        if run['span_start']!=0 or run['span_end']<.95*run['n_samples']:continue
        if legacy_ambiguous(run['span_start'],run['span_end'],run['started_at']):continue
        stride=max(1,int(np.ceil(run['n']/100)));phase=int(rng.integers(stride))
        for d in c.execute('SELECT id,start_idx,end_idx FROM detections WHERE run_id=? AND id % ? = ? LIMIT 130',(run['id'],stride,phase)):
            a,b=absolute_bounds(d['start_idx'],d['end_idx'],run['span_start'])
            raw.append({'recording_id':run['recording_id'],'start':a,'end':b,
                        'source':{'run_id':run['id'],'detection_id':d['id']},'dataset':BY_FILE[run['source_file']]})
            sources['registered_real_run']+=1
    # Direct returned classical geometries broaden the pool beyond the three
    # settings imported previously on SH/SO. Never read a surrogate cache key.
    audit=json.loads((ROOT/'docs/thesis/data/recovery_return_20261108/audit.json').read_text())
    for row in audit['all_tasks']:
        if row['state']!='complete' or 'cnn' in row['setting']:continue
        result_path=MAIN/row['result'];spec=json.loads((MAIN/row['spec']).read_text())
        res=json.loads(result_path.read_text());assert spec_hash(spec)==res['specHash']
        target=spec['targets'][row['task']];real_keys=set(target['prefixHashes'])
        rid=target['recordingId'];rec=recs[rid]
        if rec['source_file'] not in BY_FILE:continue
        for entry in sorted(res.get('cache',[]),key=lambda r:r['step'],reverse=True):
            if entry['prefixHash'] not in real_keys:continue
            folder=(result_path.parent/entry['path']).resolve()
            if not folder.is_relative_to(result_path.parent.resolve()):raise ValueError('Cache path escape')
            p=folder/'spanset.json'
            if not p.exists():continue
            geom=json.loads(p.read_text())
            if len(geom['starts'])!=(res.get('run') or {}).get('detections'):continue
            indices=rng.choice(len(geom['starts']),min(70,len(geom['starts'])),replace=False)
            for i in indices:
                raw.append({'recording_id':rid,'start':int(geom['starts'][i]),'end':int(geom['ends'][i]),
                    'dataset':BY_FILE[rec['source_file']],
                    'source':{'result':str(result_path.relative_to(MAIN)),'specHash':res['specHash'],
                              'task':row['task'],'setting':row['setting'],'span_index':int(i),'real_cache_prefix':entry['prefixHash']}})
                sources['verified_real_return_geometry']+=1
            break
    return raw,dict(sources)


class Channels:
    def __init__(self,recs):self.recs=recs;self.cache=OrderedDict()
    def get(self,rid):
        if rid not in self.cache:
            r=self.recs[rid];self.cache[rid]=np.load(MAIN/r['npy_path'],mmap_mode='r')
            if len(self.cache)>8:self.cache.popitem(last=False)
        self.cache.move_to_end(rid);return self.cache[rid]
    def mv(self,rid,a,b):
        r=self.recs[rid]
        return np.asarray(self.get(rid)[a:b],dtype=float)*{'V':1000.,'mV':1.,'uV':.001}[r['units']]


def candidate(item,recs,channels):
    source=recs[item['recording_id']]
    rid,s,e=canonical_span(source,item['start'],item['end'],recs)
    rec=recs[rid];fs=rec['fs'];length=e-s
    if not (1.5*fs<=length<=1800*fs) or s<0 or e>rec['n_samples']:return None
    pad=max(round(60*fs),min(round(600*fs),2*length));a,b=max(0,s-pad),min(rec['n_samples'],e+pad)
    x=channels.mv(rid,a,b)
    if not np.isfinite(x).all():return None
    smooth=gaussian_filter1d(x,max(.5,.5*fs));core=smooth[s-a:e-a]
    noise=1.4826*np.median(np.abs(np.diff(x)))
    if np.ptp(core)<max(.05,8*noise):return None
    drop=_is_drop(core,'auto');polarity=-1 if drop else 1;z=-smooth if drop else smooth
    peaks,props=find_peaks(z,prominence=max(.05,6*noise),distance=max(1,round(3*fs)))
    inside=np.flatnonzero((peaks>=s-a)&(peaks<e-a))
    if not len(inside):return None
    k=int(max(inside,key=lambda j:props['prominences'][j]));peak=int(peaks[k])
    _,_,left,right=peak_widths(z,np.array([peak]),rel_height=.95,
        prominence_data=(props['prominences'][k:k+1],props['left_bases'][k:k+1],props['right_bases'][k:k+1]))
    lo,hi=int(np.floor(left[0])),int(np.ceil(right[0]))+1
    substantial=peaks[props['prominences']>=.35*props['prominences'][k]]
    previous=substantial[substantial<peak];following=substantial[substantial>peak]
    # One proposed event per review item, with adjacent events visible as
    # context. Distinct troughs must not become one joined review unit.
    if len(previous):lo=max(lo,int((previous[-1]+peak)//2)+1)
    if len(following):hi=min(hi,int((following[0]+peak)//2))
    s,e=a+lo,a+hi
    if not (3*fs<=e-s<=1200*fs):return None
    curve=smooth[lo:hi];v=np.interp(np.linspace(0,len(curve)-1,64),np.arange(len(curve)),curve)
    sd=float(v.std())
    if sd<=0:return None
    v=((v-v.mean())/sd).astype(np.float32)
    return {'recording_id':rid,'start':s,'end':e,'length':e-s,'dataset':item['dataset'],
            'channel':int(rec['channel'])+1,'group':'diversity_candidate','seed':None,'earlier':None,
            'anchor':a+peak,'polarity':polarity,'prominence_mv':float(props['prominences'][k]),
            'duration_s':(e-s)/fs,'event_identity':peak_identity(rid,a+peak,polarity),
            'source':item['source'],'_vector':v}


def pick(items,quota,rng,recs):
    if not items:return []
    amplitudes=np.quantile([x['prominence_mv'] for x in items],[1/3,2/3])
    groups=defaultdict(list)
    for it in items:
        key=(it['polarity'],int(np.searchsorted([30,180],it['duration_s'])),
             int(np.searchsorted(amplitudes,it['prominence_mv'])),it['channel'])
        groups[key].append(it)
    # Cover provisional polarity/scale/amplitude/channel strata and spread
    # times. Selection within each stratum is seeded random sampling.
    for values in groups.values():rng.shuffle(values)
    keys=list(groups);rng.shuffle(keys);chosen=[];occupied=defaultdict(list);time_bins=Counter()
    while len(chosen)<quota:
        progress=False
        for key in keys:
            values=groups[key]
            while values:
                it=values.pop();rid=it['recording_id'];fs=recs[rid]['fs'];hour=int(it['anchor']/fs/3600)
                if time_bins[(rid,hour)]>=1 or conflict(rid,it['start'],it['end'],occupied):continue
                chosen.append(it);occupied[rid].append((it['start'],it['end']));time_bins[(rid,hour)]+=1;progress=True;break
            if len(chosen)>=quota:break
        if not progress:break
    return chosen


def prepare(c,out):
    rng=np.random.default_rng(2026110802);observations,recs=collect(c);prior=defaultdict(list)
    for r in observations:
        if r['valid_bounds'] and not r.get('placement_ambiguous'):
            prior[r['canonical_recording_id']].append((r['canonical_start'],r['canonical_end']))
    # Both accepted long cases are already well represented. New MJu26a
    # candidates should broaden channels and periods rather than refill them.
    for rec in recs.values():
        if rec['source_file']=='MJu26a_fs10.mat' and rec['channel']==13:prior[rec['id']].append((13770245,17034004))
        if rec['source_file']=='MJu26a_fs10.mat' and rec['channel']==14:prior[rec['id']].append((round(206*3600*10),round(283*3600*10)))
    raw,source_counts=raw_pool(c,recs,rng);channels=Channels(recs);eligible={};rejected=Counter()
    # Canonical windows first, so a physical-copy repeat is analysed only once.
    seen=set()
    for i,it in enumerate(raw):
        rid,s,e=canonical_span(recs[it['recording_id']],it['start'],it['end'],recs)
        if (rid,s,e) in seen:continue
        seen.add((rid,s,e))
        if conflict(rid,s,e,prior):rejected['prior_review_or_selected_train']+=1;continue
        cand=candidate(it,recs,channels)
        if cand is None:rejected['shape_quality_or_extent']+=1;continue
        if conflict(cand['recording_id'],cand['start'],cand['end'],prior):rejected['expanded_extent_prior_review']+=1;continue
        eligible.setdefault(cand['event_identity'],cand)
    chosen=[]
    for dataset,n in QUOTAS.items():
        chosen+=pick([x for x in eligible.values() if x['dataset']==dataset],n,rng,recs)
    if len(chosen)<600:raise ValueError(f'Insufficient diverse proposals: {len(chosen)}; inspect the preview pool')
    blocked=defaultdict(list,{k:list(v) for k,v in prior.items()})
    for it in chosen:blocked[it['recording_id']].append((it['start'],it['end']))
    controls=[]
    for template in [chosen[int(i)] for i in rng.choice(len(chosen),54,replace=False)]:
        rid=template['recording_id'];rec=recs[rid];length=template['end']-template['start']
        for _ in range(20000):
            s=int(rng.integers(0,rec['n_samples']-length+1));e=s+length
            if conflict(rid,s,e,blocked) or not np.isfinite(channels.mv(rid,s,e)).all():continue
            controls.append({'group':'background_control','seed':None,'earlier':None,'recording_id':rid,
                'dataset':template['dataset'],'channel':template['channel'],'start':s,'end':e,'length':length,
                'source':{'uniform_control':True,'matched_duration_s':length/rec['fs']}})
            blocked[rid].append((s,e));break
        else:raise ValueError('No eligible matched control')
    keydir=MAIN/'DATA/derived/rq2_blind/20261108-drop-transfer'
    key=json.loads((keydir/'key.json').read_text());reserve=json.loads((keydir/'repeat_reserve.json').read_text())
    original={(x['recording_id'],x['start'],x['end']):x for x in key['items']}
    repeats=[]
    for it in reserve:
        first=original[(it['recording_id'],it['start'],it['end'])]
        verdict=c.execute('SELECT id,verdict FROM adjudications WHERE detection_id=? AND carried_from IS NULL ORDER BY id DESC LIMIT 1',(first['panel_detection_id'],)).fetchone()
        if verdict is None:raise ValueError('Repeat lacks a primary own answer')
        repeats.append({**it,'dataset':it['recording'],'earlier':{'verdict':verdict['verdict'],'adjudication_id':verdict['id'],
                        'primary_detection_id':first['panel_detection_id']},'group':'rq2_repeat'})
    clean=[{k:v for k,v in it.items() if not k.startswith('_')} for it in chosen]
    items=rq2_blind.shuffle(rng,clean+controls+repeats)
    summary={'planned_items':len(items),'by_group':dict(Counter(it['group'] for it in items)),
             'new_candidates_by_recording':dict(Counter(it['dataset'] for it in clean)),
             'new_candidate_polarities':dict(Counter(it['polarity'] for it in clean)),
             'candidate_pool_by_recording':dict(Counter(it['dataset'] for it in eligible.values())),
             'source_raw_sample_counts':source_counts,'exclusions':dict(rejected),
             'waiting_for_CNN':False,'selection':'fixed classical proposal pool; balanced polarity/duration/amplitude/channel strata; <=1 per channel-hour',
             'research_use':'Library diversity and blinded within-reviewer repeat check; not a representative full-sweep precision or prevalence estimate',
             'human_judgements_written':0}
    out.mkdir(parents=True,exist_ok=True)
    (out/'prepared_items.json').write_text(json.dumps(items,indent=1),encoding='utf-8')
    (out/'preparation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    csv_write(out/'new_candidates.csv',clean)
    # Internal QA only; proposal/control/repeat identities are not shown in Review.
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(7,3,figsize=(12,13),layout='constrained')
    for row,dataset in enumerate(QUOTAS):
        rr=[it for it in clean if it['dataset']==dataset]
        for ax,it in zip(axes[row],rr[:3]):
            rec=recs[it['recording_id']];fs=rec['fs'];s,e=it['start'],it['end'];pad=max(round(60*fs),e-s)
            a,b=max(0,s-pad),min(rec['n_samples'],e+pad);x=channels.mv(rec['id'],a,b);stride=max(1,len(x)//1800)
            ax.plot((np.arange(a,b,stride)-s)/fs,x[::stride],lw=.65);ax.axvspan(0,(e-s)/fs,color='orange',alpha=.2)
            ax.set_title(f'{dataset} CH{it["channel"]} · {it["polarity"]:+d}',fontsize=9);ax.tick_params(labelsize=7)
    fig.savefig(out/'internal_proposal_QA.png',dpi=110);plt.close(fig)
    print(json.dumps(summary,indent=2),flush=True)
    return items,summary


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=MAIN/'DATA/derived/library_diversity_review_20261108'
    if (out/'key.json').exists():print('Existing queue retained:',json.loads((out/'key.json').read_text())['queue_id']);return
    if args.apply:
        items=json.loads((out/'prepared_items.json').read_text());summary=json.loads((out/'preparation.json').read_text())
        assert len(items)<=1000
        db=MAIN/'DATA/db/annotations.sqlite';backup=db.parent/'backups'/('before_diversity_review_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S')+'.sqlite')
        with sqlite3.connect(db) as src,sqlite3.connect(backup) as dst:src.backup(dst)
        c=sqlite3.connect(db);c.row_factory=sqlite3.Row
        result=rq2_blind.write_panel(c,items,stamp=STAMP,key_dir=str(out),db_path=str(db),
            make_queue=rq2_blind.bridge_queue('http://127.0.0.1:8765'),extra_key={'composition':summary,
            'primary_rq2_queue':38,'note':'Source key private until adjudication; repeats retain frozen first answers.'})
        qid=result['queue_id'];c.execute('UPDATE review_queues SET name=?,note=? WHERE id=?',
            ('Library diversity · new recordings and repeat checks',
             'Diverse detector proposals, matched background windows and planned repeat checks. Sources and scores hidden. Individual-event proposals; wider context may contain neighbouring events. Selected review, not full-sweep precision.',qid));c.commit()
        q=queues.get_queue(c,qid);views=queues.queue_view(c,qid);served=queues.select_items(q,views,include_judged=True)
        index={it['panel_detection_id']:it for it in result['items']};presentations=[]
        for view in served:
            ids=view.get('members') or [view['target_id']]
            assert len({index[i]['group'] for i in ids})==1,'Different review sources were merged'
            presentations.append({**index[view['target_id']],'represented_detection_ids':ids})
        key=json.loads((out/'key.json').read_text());key.update(presentations=presentations,presentation_count=len(presentations))
        (out/'key.json').write_text(json.dumps(key,indent=1),encoding='utf-8')
        final={**summary,'queue_id':qid,'counts':queues.queue_counts(c,qid),
               'presentation_groups':dict(Counter(it['group'] for it in presentations)),'backup':str(backup)}
        (out/'queue.json').write_text(json.dumps(final,indent=2));c.close();print(json.dumps(final,indent=2),flush=True)
    else:
        c=connect(MAIN/'DATA/db/annotations.sqlite')
        try:prepare(c,out)
        finally:c.close()


if __name__=='__main__':main()
