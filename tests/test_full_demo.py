"""One command runs all four SDK operations with presenter control between them."""
import sys
import pytest
from hrl import cli
from test_directory_demo import bundle_demo
from test_workflow import fake_client


@pytest.fixture
def full_demo(bundle_demo,monkeypatch):
    from hrl import demo_operations as module
    source,directory_client,_,selected=bundle_demo
    root=source.parents[1]
    (root/'examples/review_knowledge.demo.md').write_text('# DEMO ONLY\nExample guidance.\n')
    files={provider:fake_client(provider)[0] for provider in ('aws','gcp')}
    monkeypatch.setattr(module,'connect_file',lambda p,c:files[p])
    from hrl import directory_demo
    monkeypatch.setattr(module,'connect_directory',directory_demo.connect)
    events=[]
    for client in files.values():
        upload=client.upload.side_effect
        download=client.download.side_effect
        def write(*args,_fn=upload,**kwargs):
            events.append('upload'); return _fn(*args,**kwargs)
        def read(*args,_fn=download,**kwargs):
            events.append('download'); return _fn(*args,**kwargs)
        client.upload.side_effect=write
        client.download.side_effect=read
    for name in ('upload_directory','download_directory'):
        method=getattr(directory_client,name)
        original=method.side_effect
        async def transfer(*args,_fn=original,_name=name,**kwargs):
            events.append(_name.replace('_','-'))
            return await _fn(*args,**kwargs)
        method.side_effect=transfer
    return files,directory_client,events,selected


@pytest.mark.parametrize('provider',['aws','gcp'])
@pytest.mark.parametrize('explicit_all',[False,True])
def test_one_command_runs_four_operations_in_order(full_demo,monkeypatch,capsys,provider,explicit_all):
    files,directory,events,selected=full_demo
    monkeypatch.setattr(sys,'argv',['demo',*(['all'] if explicit_all else []),'--provider',provider,'--yes'])
    assert cli.main('demo')==0
    assert events==['upload','download','upload-directory','download-directory']
    assert selected==[provider,provider]
    other='aws' if provider=='gcp' else 'gcp'
    files[other].upload.assert_not_called()
    files[other].download.assert_not_called()
    output=capsys.readouterr().out
    for number in range(1,5):
        assert f'[STEP {number}/4]' in output
    assert 'DOWNLOAD EXISTING KNOWLEDGE' not in output
    assert 'PREPARE KNOWLEDGE' not in output
    assert 'FULL SDK DEMO COMPLETED' in output
    assert 'Operations     : 4/4' in output
    assert 'Next command' not in output
    assert output.index('SINGLE FILE UPLOAD COMPLETED') < output.index('SINGLE FILE DOWNLOAD COMPLETED') < output.index('DIRECTORY UPLOAD COMPLETED') < output.index('DIRECTORY DOWNLOAD COMPLETED')


@pytest.mark.parametrize('stop_at',[1,2,3,4])
def test_combined_demo_waits_before_each_operation(full_demo,monkeypatch,capsys,stop_at):
    _,_,events,_=full_demo
    prompts=[]
    def answer(prompt):
        prompts.append(prompt)
        assert len(events)==len(prompts)-1
        return 'no' if len(prompts)==stop_at else 'yes'
    monkeypatch.setattr('builtins.input',answer)
    monkeypatch.setattr(sys,'argv',['demo','--provider','gcp'])
    assert cli.main('demo')==130
    assert len(prompts)==stop_at
    assert len(events)==stop_at-1
    assert f'{stop_at}/4' in prompts[-1]
    assert 'FULL SDK DEMO COMPLETED' not in capsys.readouterr().out


def test_combined_demo_stops_on_download_failure(full_demo,monkeypatch,capsys):
    files,_,events,_=full_demo
    files['gcp'].download.side_effect=RuntimeError('download unavailable')
    monkeypatch.setattr(sys,'argv',['demo','--provider','gcp','--yes'])
    assert cli.main('demo')==1
    assert events==['upload']
    assert 'FULL SDK DEMO COMPLETED' not in capsys.readouterr().out


def test_full_demo_rejects_an_existing_download_state(full_demo,monkeypatch):
    _,_,events,_=full_demo
    monkeypatch.setattr(sys,'argv',['demo','all','--provider','gcp','--state','previous.json','--yes'])
    assert cli.main('demo')==1
    assert not events
