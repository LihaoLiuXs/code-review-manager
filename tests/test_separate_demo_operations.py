"""Each audience-facing demo command performs one SDK transfer operation."""
import json
import sys
from pathlib import Path
import pytest
from hrl import cli
from test_workflow import fake_client
from test_directory_demo import bundle_demo


def run(monkeypatch, action, provider='gcp', *extra):
    monkeypatch.setattr(sys,'argv',['demo',action,'--provider',provider,'--yes',*extra])
    return cli.main('demo')


@pytest.fixture
def file_demo(tmp_path,monkeypatch):
    from hrl import demo_operations as module
    root=tmp_path/'checkout'
    (root/'examples').mkdir(parents=True)
    sample=root/'examples/review_knowledge.demo.md'
    sample.write_text('# DEMO ONLY\n\nSynthetic guidance.\n')
    monkeypatch.setattr(cli,'PROJECT_ROOT',root)
    monkeypatch.chdir(tmp_path)
    clients={p:fake_client(p)[0] for p in ('aws','gcp')}
    selected=[]
    def connect(provider,config):
        selected.append(provider)
        return clients[provider]
    monkeypatch.setattr(module,'connect_file',connect)
    return sample,clients,selected


@pytest.mark.parametrize('provider',['aws','gcp'])
def test_single_upload_and_download_are_two_independent_commands(file_demo, monkeypatch, capsys, provider):
    sample,clients,selected=file_demo
    client=clients[provider]
    assert run(monkeypatch,'upload',provider)==0
    client.upload.assert_called_once()
    client.download.assert_not_called()
    output=capsys.readouterr().out
    assert 'SINGLE FILE UPLOAD COMPLETED' in output
    assert 'SINGLE FILE DOWNLOAD' not in output
    uploaded=client.upload.call_args.kwargs['payload']
    assert uploaded==sample.read_bytes()
    sample.write_text('Changed after upload; download must use the saved manifest')
    assert run(monkeypatch,'download',provider)==0
    client.upload.assert_called_once()
    client.download.assert_called_once()
    output=capsys.readouterr().out
    assert 'SINGLE FILE DOWNLOAD COMPLETED' in output
    saved=list(Path('output').rglob('downloaded/review_knowledge.demo.md'))
    assert len(saved)==1 and saved[0].read_bytes()==uploaded
    assert selected==[provider,provider]


@pytest.mark.parametrize('provider',['aws','gcp'])
def test_directory_upload_and_download_are_independent_commands(bundle_demo, monkeypatch, capsys, provider):
    from hrl import demo_operations as module
    from hrl import directory_demo
    source,client,blobs,selected=bundle_demo
    monkeypatch.setattr(module,'connect_directory',directory_demo.connect)
    assert run(monkeypatch,'upload-directory',provider)==0
    client.upload_directory.assert_awaited_once()
    client.download_directory.assert_not_awaited()
    assert 'DIRECTORY UPLOAD COMPLETED' in capsys.readouterr().out
    assert run(monkeypatch,'download-directory',provider)==0
    client.upload_directory.assert_awaited_once()
    client.download_directory.assert_awaited_once()
    client.delete_directory.assert_not_awaited()
    output=capsys.readouterr().out
    assert 'Files verified : 3/3' in output
    assert 'DIRECTORY DOWNLOAD COMPLETED' in output
    assert selected==[provider,provider]


def test_download_without_previous_upload_does_not_touch_cloud(file_demo,monkeypatch,capsys):
    _,clients,selected=file_demo
    assert run(monkeypatch,'download')==1
    assert not selected
    assert 'upload' in capsys.readouterr().err.lower()


def test_mismatched_download_never_reports_success(file_demo,monkeypatch,capsys):
    from multicloud.blob.blob_client import DownloadResponse
    _,clients,_=file_demo
    client=clients['gcp']
    assert run(monkeypatch,'upload')==0
    client.download.side_effect=None
    client.download.return_value=DownloadResponse(key='key',content=b'wrong content',metadata=None)
    capsys.readouterr()
    assert run(monkeypatch,'download')==1
    output=capsys.readouterr().out
    assert 'SINGLE FILE DOWNLOAD COMPLETED' not in output
    assert '[PROCESS FAILED]' in output


def test_declined_upload_does_not_create_client_or_transfer(file_demo,monkeypatch,capsys):
    _,_,selected=file_demo
    monkeypatch.setattr('builtins.input',lambda prompt:'no')
    monkeypatch.setattr(sys,'argv',['demo','upload','--provider','gcp'])
    assert cli.main('demo')==130
    assert not selected
    assert '[PROCESS STOPPED]' in capsys.readouterr().out


def test_failed_upload_keeps_previous_download_manifest(file_demo,monkeypatch):
    _,clients,_=file_demo
    assert run(monkeypatch,'upload')==0
    latest=next(Path('output').rglob('single-latest.json'))
    before=latest.read_bytes()
    clients['gcp'].upload.side_effect=RuntimeError('upload denied')
    assert run(monkeypatch,'upload')==1
    assert latest.read_bytes()==before
    clients['gcp'].download.assert_not_called()


def test_download_rejects_a_different_bucket_before_reading(file_demo,monkeypatch):
    _,clients,_=file_demo
    assert run(monkeypatch,'upload')==0
    clients['gcp'].bucket='different-bucket'
    assert run(monkeypatch,'download')==1
    clients['gcp'].download.assert_not_called()


def test_directory_download_detects_same_length_corrupted_content(bundle_demo,monkeypatch,capsys):
    from hrl import demo_operations as module
    from hrl import directory_demo
    _,client,blobs,_=bundle_demo
    monkeypatch.setattr(module,'connect_directory',directory_demo.connect)
    assert run(monkeypatch,'upload-directory')==0
    key=next(iter(blobs))
    blobs[key]=b'X'+blobs[key][1:]
    capsys.readouterr()
    assert run(monkeypatch,'download-directory')==1
    assert 'DIRECTORY DOWNLOAD COMPLETED' not in capsys.readouterr().out
    client.upload_directory.assert_awaited_once()


def test_manifest_path_traversal_is_rejected_before_download(file_demo,monkeypatch):
    _,clients,selected=file_demo
    assert run(monkeypatch,'upload')==0
    latest=next(Path('output').rglob('single-latest.json'))
    state=json.loads(latest.read_text())
    metadata=next(iter(state['files'].values()))
    state['files']={'../../escaped.md':metadata}
    latest.write_text(json.dumps(state))
    assert run(monkeypatch,'download')==1
    assert selected==['gcp']
    clients['gcp'].download.assert_not_called()
    assert not Path('escaped.md').exists()


def test_demo_help_presents_the_four_independent_operations(monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['demo','--help'])
    with pytest.raises(SystemExit) as exc:
        cli.main('demo')
    assert exc.value.code==0
    output=capsys.readouterr().out
    assert 'upload|download|upload-directory|download-directory' in ''.join(output.split())
    assert 'save,get,verify,sync' not in output
    assert '--state' in output
