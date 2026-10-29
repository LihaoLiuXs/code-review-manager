"""One application workflow; the provider flag selects its only destination."""
import sys
from unittest.mock import Mock
import pytest
from hrl import cli
from hrl.io import write_json, read_json
from hrl.multicloud_store import Store, make_record
from test_workflow import fake_client


@pytest.mark.parametrize('provider',['aws','gcp'])
def test_save_get_verify_use_only_selected_cloud(tmp_path,monkeypatch,capsys,provider):
    client,_=fake_client(provider)
    store=Store(client)
    selected=[]
    def connect(p,config):
        assert p==provider,'Must not connect to or require credentials for the other cloud'
        selected.append(p)
        return store
    monkeypatch.setattr(cli,'connect',connect)
    markdown=tmp_path/'demo.md'; markdown.write_text('# Synthetic demo\nExample content')
    def run(action,*extra):
        monkeypatch.setattr(sys,'argv',['storage.py',action,'--repo','demo/hrl',
                                      '--provider',provider,*extra])
        return cli.main('storage')
    assert run('save','--file',str(markdown))==0
    assert run('get','--output',str(tmp_path/'saved.json'))==0
    assert read_json(tmp_path/'saved.json')['knowledge_md']==markdown.read_text()
    assert run('verify','--record',str(tmp_path/'pending.json'))==0
    output=capsys.readouterr().out
    assert f'Selected provider: {provider}' in output
    assert 'matches expected record' in output
    assert 'AWS / GCP knowledge' not in output
    assert selected==[provider]*3


def test_provider_selection_is_required_before_cloud_access(monkeypatch):
    monkeypatch.setattr(sys,'argv',['storage.py','get','--repo','o/r'])
    connect=Mock(); monkeypatch.setattr(cli,'connect',connect)
    with pytest.raises(SystemExit) as exc:
        cli.main('storage')
    assert exc.value.code==2
    connect.assert_not_called()


def test_provider_and_provider_list_cannot_be_combined(monkeypatch):
    monkeypatch.setattr(sys,'argv',['storage.py','get','--repo','o/r',
        '--provider','aws','--providers','aws,gcp'])
    connect=Mock(); monkeypatch.setattr(cli,'connect',connect)
    with pytest.raises(SystemExit) as exc:
        cli.main('storage')
    assert exc.value.code==2
    connect.assert_not_called()


def test_verify_one_cloud_does_not_claim_cross_cloud_equivalence(monkeypatch,capsys):
    store=Mock(); store.load.return_value=make_record('o/r','md',[],None,{})
    monkeypatch.setattr(cli,'connect',lambda p,c:store)
    monkeypatch.setattr(sys,'argv',['storage.py','verify','--provider','aws','--repo','o/r'])
    assert cli.main('storage')==0
    output=capsys.readouterr().out
    assert 'AWS knowledge: VERIFIED readable' in output
    assert 'equivalent' not in output


def test_selected_cloud_verification_rejects_wrong_expected_record(tmp_path,monkeypatch):
    store=Mock(); record=make_record('o/r','cloud content',[],None,{})
    store.load.return_value=record
    pending=tmp_path/'pending.json'
    write_json(pending,{'base':None,'record':dict(record,knowledge_md='different expected content')})
    monkeypatch.setattr(cli,'connect',lambda p,c:store)
    monkeypatch.setattr(sys,'argv',['storage.py','verify','--provider','gcp','--repo','o/r',
                                  '--record',str(pending)])
    assert cli.main('storage')==1
    store.save.assert_not_called()


def test_sync_requires_explicit_multi_provider_selection(monkeypatch):
    monkeypatch.setattr(sys,'argv',['storage.py','sync','--provider','aws','--repo','o/r'])
    connect=Mock(); monkeypatch.setattr(cli,'connect',connect)
    assert cli.main('storage')==1
    connect.assert_not_called()


def test_single_cloud_failure_does_not_report_partial_dual_write(tmp_path,monkeypatch,capsys):
    store=Mock(); store.load.return_value=None; store.save.side_effect=RuntimeError('denied')
    monkeypatch.setattr(cli,'connect',lambda p,c:store)
    path=tmp_path/'demo.md'; path.write_text('demo')
    monkeypatch.setattr(sys,'argv',['storage.py','save','--provider','aws','--repo','demo/hrl',
                                  '--file',str(path)])
    assert cli.main('storage')==1
    output=capsys.readouterr()
    assert 'Partial write failure' not in output.err
    assert 'aws' in output.err and 'pending.json' in output.err


def test_same_pending_payload_can_be_deployed_with_either_provider(tmp_path,monkeypatch):
    clients={p:fake_client(p)[0] for p in ('aws','gcp')}
    monkeypatch.setattr(cli,'connect',lambda p,c:Store(clients[p]))
    record=make_record('demo/hrl','same portable knowledge',[],None,{})
    path=tmp_path/'pending.json';write_json(path,{'base':None,'record':record})
    for provider in ('aws','gcp'):
        monkeypatch.setattr(sys,'argv',['storage.py','save','--repo','demo/hrl',
            '--record',str(path),'--provider',provider])
        assert cli.main('storage')==0
    assert clients['aws'].upload.call_args.kwargs['payload']==clients['gcp'].upload.call_args.kwargs['payload']
