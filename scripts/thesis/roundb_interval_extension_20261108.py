"""Extend the frozen B1 census with complete SH/SO default drop-v1 returns.

The accepted Library is not the sampling frame for these intervals. Keep the
historical analysis intact and recompute correction for the extended census.
"""
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2];MAIN=Path('C:/Users/mmebr/Documents/CNN')
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts/thesis'))
import b1_intervals as b1
from Working.interrogation.intervals import interval_nulls
from Working.discovery.chain_job import spec_hash
from scripts.thesis import figstyle as style
import matplotlib.pyplot as plt


def main():
    out=ROOT/'docs/thesis/data/roundb_extension_20261108';out.mkdir(parents=True,exist_ok=True)
    original=pd.read_csv(ROOT/'docs/thesis/data/ch10_b1/b1_channels.csv')
    original=original[~original['dataset'].isin(['SH_fs2','SO_fs2'])].copy()
    audit=json.loads((ROOT/'docs/thesis/data/recovery_return_20261108/audit.json').read_text())
    c=sqlite3.connect((MAIN/'DATA/db/annotations.sqlite').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    added=[];missing=[]
    for r in audit['all_tasks']:
        if r['setting']!='drop_detection_v1' or r['recording'] not in {'SH_fs2','SO_fs2'}:continue
        assert r['state']=='complete'
        spec=json.loads((MAIN/r['spec']).read_text());target=spec['targets'][r['task']]
        path=MAIN/r['result'];res=json.loads(path.read_text());assert spec_hash(spec)==res['specHash']
        starts=None;source=None
        for entry in sorted(res['cache'],key=lambda e:e['step'],reverse=True):
            if entry['prefixHash'] not in target['prefixHashes']:continue
            p=path.parent/entry['path']/'spanset.json'
            if not p.exists():continue
            geom=json.loads(p.read_text())
            if len(geom['starts'])!=res['run']['detections']:continue
            starts=np.array(geom['starts'],dtype=float);source=str(p.relative_to(MAIN));break
        if starts is None:
            run=c.execute("SELECT r.id FROM runs r JOIN configs cfg ON cfg.id=r.config_id WHERE r.recording_id=? "
                          "AND cfg.config_hash=? AND r.surrogate_of_run_id IS NULL AND r.status='completed' ORDER BY r.id DESC LIMIT 1",
                          (target['recordingId'],target['configHash'])).fetchone()
            if run is not None:
                starts=np.array([v[0] for v in c.execute('SELECT start_idx FROM detections WHERE run_id=?',(run['id'],))],dtype=float)
                assert len(starts)==res['run']['detections'];source='registered run '+str(run['id'])
            else:
                work=MAIN/r['out']/'work'/f"task{r['task']}"/'scratch.sqlite'
                if work.exists():
                    wc=sqlite3.connect(work.as_uri()+'?mode=ro',uri=True)
                    wr=wc.execute("SELECT run.id FROM runs run JOIN configs cfg ON cfg.id=run.config_id "
                                  "WHERE cfg.config_hash=? AND run.status='completed' AND run.surrogate_of_run_id IS NULL ORDER BY run.id DESC LIMIT 1",(target['configHash'],)).fetchone()
                    if wr is not None:starts=np.array([v[0] for v in wc.execute('SELECT start_idx FROM detections WHERE run_id=?',(wr[0],))],dtype=float)
                    wc.close();source=str(work.relative_to(MAIN))
                if starts is None:
                    missing.append({'recording':r['recording'],'task':r['task'],
                                    'expected_detections':res['run']['detections'],
                                    'remote_work_folder':'/home/Student/s4699158/CNN/'+r['out']+'/work/'})
                    continue
                assert len(starts)==res['run']['detections']
        fs=target['fs'];nl=interval_nulls(starts/fs,resolution_s=1/fs,n_draws=1000,seed=2003)
        row={'run':None,'recording_id':target['recordingId'],'dataset':r['recording'],
             'species':'Asian shiitake' if r['recording']=='SH_fs2' else 'snow oyster',
             'channel':target['channel'],'hours':target['nSamples']/fs/3600,
             'n_events':len(starts),'caveat':nl.get('caveat') or nl.get('note'),
             'geometry_source':source,'specHash':res['specHash']}
        for measure,null in b1.TESTS:
            v=(nl.get(null) or {}).get(measure) or {};obs,lo,hi=v.get('observed'),v.get('lo'),v.get('hi')
            row[measure]=obs
            row.update({f'{measure}_{null}_lo':lo,f'{measure}_{null}_hi':hi,f'{measure}_{null}_p':v.get('p'),
                        f'{measure}_{null}_side':None if obs is None or lo is None else 'below' if obs<lo else 'above' if obs>hi else 'inside'})
        added.append(row)
    if missing:
        report={'status':'pending exact onset geometry; counts alone are insufficient',
                'complete_new_channels_available':len(added),'missing':missing,
                'old_census_unchanged':True,
                'new_detector_computation_required':'not if retained cluster scratch folders are supplied'}
        (out/'missing_geometry.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2),flush=True);return
    assert len(added)==8
    df=b1.correct(pd.concat([original,pd.DataFrame(added)],ignore_index=True))
    result=b1.summary(df);df.to_csv(out/'b1_channels.csv',index=False);result.to_csv(out/'b1_summary.csv',index=False)
    summary={'total_channels':len(df),'measurable_channels':int(df['lv'].notna().sum()),
             'added_channels':8,'added_detections':int(sum(r['n_events'] for r in added)),
             'rows':json.loads(result.to_json(orient='records')),'uses_sampled_library_gaps':False,
             'old_channels':len(original),'protocol':'same full-channel default setting; BH recomputed over all measurable channels'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    style.apply();fig,axs=plt.subplots(2,1,figsize=(6.3,4.6),layout='constrained',sharex=True)
    order=list(dict.fromkeys(df['dataset']));offset=0;ticks=[]
    for dataset in order:
        rr=df[df['dataset']==dataset];xx=np.arange(len(rr))+offset;ticks.append((xx.mean(),style.label(dataset)))
        for ax,null in zip(axs,('poisson','shuffle')):
            ax.vlines(xx,rr[f'lv_{null}_lo'],rr[f'lv_{null}_hi'],color='#c7c6c2',lw=3)
            for x,(_,r) in zip(xx,rr.iterrows()):
                if pd.isna(r['lv']):continue
                ax.plot(x,r['lv'],'D' if r[f'lv_{null}_bh'] else 'o',ms=4 if r[f'lv_{null}_bh'] else 3,color=style.colour(dataset))
            ax.set_ylabel('LV');ax.axhline(1,color=style.MUTED,ls=':',lw=.8)
        offset+=len(rr)+2
    axs[0].set_title('Against rate-matched random timing',fontsize=9)
    axs[1].set_title('Against the same intervals shuffled',fontsize=9)
    axs[1].set_xticks([x for x,_ in ticks],[s for _,s in ticks],fontsize=8)
    style.save(fig,'ch10_b1_extended');plt.close(fig)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
