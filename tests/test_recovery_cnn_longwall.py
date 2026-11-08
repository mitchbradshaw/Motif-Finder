import hashlib
import json
from scripts.thesis.recovery_cnn_longwall import retry_stalled, release_verified, cnn_pack_config


def test_cnn_pack_has_a_three_hour_cap_inside_the_scheduler_wall():
    old={"parallel":4,"gpu":True,"wall_budget_s":16200,"task_budget_s":15000}
    new=cnn_pack_config(old)
    assert new["wall_budget_s"]==10800
    assert new["task_budget_s"]==9900 < new["wall_budget_s"] < 5*3600
    assert new["parallel"]==1 and new["gpu"] is True
    assert old["wall_budget_s"]==16200


def test_retry_archives_stall_state_once_without_changing_results_or_cache(tmp_path):
    folder=tmp_path/"out";work=folder/"work/task0";ret=folder/"return/task0"
    work.mkdir(parents=True);ret.mkdir(parents=True)
    state=work/"state.json";state.write_text('{"stalls":2,"mark":[0,0,0]}')
    result=ret/"result.json";result.write_text(json.dumps({"specHash":"abc","complete":False,"error":"no progress in 2 jobs in a row"}))
    cache=ret/"scores.npy";cache.write_bytes(b"preserve")
    m={"tasks":[{"id":"a","out":"out","pack":"cnn","task":0,"specHash":"abc"}]}
    assert len(retry_stalled(tmp_path,m))==1 and state.exists()
    assert len(retry_stalled(tmp_path,m,True))==1
    assert not state.exists() and len(list(work.glob('state.before_longwall_*')))==1
    assert cache.read_bytes()==b"preserve" and result.exists()
    assert retry_stalled(tmp_path,m,True)==[]


def test_release_requires_the_exact_backed_up_file_set_and_hashes(tmp_path):
    result=tmp_path/"DATA/derived/hpc/recovery_20261108/rq4/job/return/task0/result.json"
    cache=result.parent/"step_cache";cache.mkdir(parents=True)
    result.write_text('{"complete":true}');(cache/"x").write_bytes(b"backed up")
    digest=lambda v:hashlib.sha256(v).hexdigest()
    ack={"returns":[{"result":result.relative_to(tmp_path).as_posix(),
        "result_sha256":digest(result.read_bytes()),"files":{"x":digest(b"backed up")}}]}
    (cache/"x").write_bytes(b"changed")
    assert release_verified(tmp_path,ack,True)["tasks"]==0 and cache.exists()
    (cache/"x").write_bytes(b"backed up")
    assert release_verified(tmp_path,ack)["tasks"]==1 and cache.exists()
    assert release_verified(tmp_path,ack,True)["tasks"]==1
    assert not cache.exists() and result.exists()
