import json
from argparse import Namespace
import pytest
from hrl import cli
from hrl.io import write_json, read_json
from hrl.multicloud_store import make_record


def test_storage_conflict_preflight_blocks_all_writes(monkeypatch, tmp_path):
    from unittest.mock import Mock
    a=make_record('o/r','old',[],None,{})
    b=make_record('o/r','new',[],a,{})
    stores={'aws':Mock(),'gcp':Mock()}
    stores['aws'].load.return_value=a
    stores['gcp'].load.return_value=dict(a,knowledge_md='conflict')
    monkeypatch.setattr(cli,'connect',lambda p,c:stores[p])
    path=tmp_path/'pending.json'; write_json(path,{'base':a,'record':b})
    with pytest.raises(ValueError,match='changed'):
        cli.storage_command(Namespace(action='save',repo='o/r',providers='aws,gcp',provider=None,record=str(path),file=None,output=None),{})
    assert not stores['aws'].save.called and not stores['gcp'].save.called


def test_build_empty_preserves_old_markdown(tmp_path):
    old=make_record('o/r','# Existing\nHRL-001 evidence',[],None,{})
    write_json(tmp_path/'existing.json',old)
    write_json(tmp_path/'reviews.json',{'repo_id':'o/r','comments':[]})
    write_json(tmp_path/'classifications.json',[])
    write_json(tmp_path/'observations.json',[])
    cli.build('o/r',tmp_path)
    assert (tmp_path/'review_knowledge.md').read_text()==old['knowledge_md']
    assert read_json(tmp_path/'pending.json')['record']==old


def test_changed_comment_report_rejected(tmp_path):
    write_json(tmp_path/'reviews.json',{'repo_id':'o/r','comments':[{'comment_id':'1','repo_id':'o/r','body':'changed'}]})
    write_json(tmp_path/'classifications.json',[{'comment_id':'1','classification':'HUMAN','fingerprint':'old'}])
    write_json(tmp_path/'observations.json',[])
    with pytest.raises(ValueError,match='stale'): cli.build('o/r',tmp_path)


def test_nonempty_learning_and_dual_cloud_sync_without_credentials(tmp_path,monkeypatch):
    """Controlled synthetic evidence, not a claim of live human provenance."""
    from test_workflow import comment,obs,fake_client
    from hrl.classification import confirm
    from hrl.multicloud_store import Store
    c=comment(); decisions={}; report=confirm(c,'HUMAN',decisions)
    write_json(tmp_path/'reviews.json',{'repo_id':'o/r','complete':True,'comments':[c],
        'period_start':'2026-09-25','period_end':'2026-10-25','pr_count':1})
    write_json(tmp_path/'classifications.json',[report])
    write_json(tmp_path/'observations.json',[obs()])
    cli.build('o/r',tmp_path)
    markdown=(tmp_path/'review_knowledge.md').read_text()
    assert 'HRL-001' in markdown and c['comment_url'] in markdown
    stores={p:Store(fake_client(provider=p)[0]) for p in ['aws','gcp']}
    monkeypatch.setattr(cli,'connect',lambda p,c:stores[p])
    args=Namespace(action='save',repo='o/r',providers='aws,gcp',provider=None,
                   record=str(tmp_path/'pending.json'),file=None,output=None)
    cli.storage_command(args,{})
    assert stores['aws'].load('o/r')==stores['gcp'].load('o/r')
    assert stores['aws'].load('o/r')['human_comment_count']==1
    # Retry exactly the same pending revision, then repeat the merge.
    cli.storage_command(args,{})
    write_json(tmp_path/'existing.json',stores['aws'].load('o/r'))
    write_json(tmp_path/'observations.json',[obs(merge_into='HRL-001')])
    cli.build('o/r',tmp_path)
    assert (tmp_path/'review_knowledge.md').read_text()==markdown
    assert read_json(tmp_path/'record.json')['knowledge_version']==1
