"""Demo logs must let presenters find the exact cloud folder and each object."""
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
import pytest
from multicloud.blob.blob_client import AsyncDirectoryUploadResponse, AsyncDirectoryDownloadResponse
from hrl import cli
from test_directory_demo import bundle_demo
from test_separate_demo_operations import run


@pytest.mark.parametrize('provider,scheme,host',[
    ('aws','s3','s3.console.aws.amazon.com'),
    ('gcp','gs','console.cloud.google.com'),
])
def test_directory_logs_name_every_cloud_object_and_local_file(bundle_demo,monkeypatch,capsys,provider,scheme,host):
    from hrl import demo_operations as module
    from hrl import directory_demo
    _,client,_,_=bundle_demo
    monkeypatch.setattr(module,'connect_directory',directory_demo.connect)
    assert run(monkeypatch,'upload-directory',provider)==0
    upload_output=capsys.readouterr().out
    prefix=client.upload_directory.call_args.kwargs['prefix']
    source=Path(client.upload_directory.call_args.args[0]).absolute()
    assert f'{scheme}://demo-bucket/{prefix}' in upload_output
    assert host in upload_output
    assert 'Console URL' in upload_output
    assert upload_output.index('[UPLOADED FILE]') > upload_output.index('[WRITE OK]')
    names=['knowledge.md','reviews/comments.json','rules/conventions.json']
    for name in names:
        assert f'Object key     : {prefix}{name}' in upload_output
        assert f'Cloud file     : {scheme}://demo-bucket/{prefix}{name}' in upload_output
        assert str(source/name) in upload_output
    assert run(monkeypatch,'download-directory',provider)==0
    download_output=capsys.readouterr().out
    restored=Path(client.download_directory.call_args.args[1]).absolute()
    assert f'{scheme}://demo-bucket/{prefix}' in download_output
    assert 'Console URL' in download_output
    assert download_output.index('[DOWNLOADED FILE]') > download_output.index('[VERIFIED]')
    for name in names:
        assert f'Object key     : {prefix}{name}' in download_output
        assert f'Cloud file     : {scheme}://demo-bucket/{prefix}{name}' in download_output
        assert str(restored/name) in download_output


@pytest.mark.parametrize('provider',['aws','gcp'])
def test_console_link_preserves_literal_percent_signs_and_spaces(provider):
    from hrl.cloud_locations import directory_console_url
    prefix='demo_artifacts/team%2Frepo/run with spaces/'
    url=directory_console_url(provider,'demo-bucket',prefix)
    parsed=urlsplit(url)
    assert parsed.scheme=='https'
    if provider=='aws':
        assert parsed.netloc=='s3.console.aws.amazon.com'
        assert parse_qs(parsed.query)['prefix']==[prefix]
    else:
        assert parsed.netloc=='console.cloud.google.com'
        assert unquote(parsed.path)==f'/storage/browser/demo-bucket/{prefix}'


@pytest.mark.parametrize('operation',['upload-directory','download-directory'])
def test_failed_transfer_never_claims_all_files_transferred(bundle_demo,monkeypatch,capsys,operation):
    from hrl import demo_operations as module
    from hrl import directory_demo
    _,client,_,_=bundle_demo
    monkeypatch.setattr(module,'connect_directory',directory_demo.connect)
    if operation=='download-directory':
        assert run(monkeypatch,'upload-directory')==0
        client.download_directory.side_effect=None
        client.download_directory.return_value=AsyncDirectoryDownloadResponse(total_files=3,successful_downloads=1)
    else:
        client.upload_directory.side_effect=None
        client.upload_directory.return_value=AsyncDirectoryUploadResponse(total_files=3,successful_uploads=1)
    capsys.readouterr()
    assert run(monkeypatch,operation)==1
    output=capsys.readouterr().out
    assert '[UPLOADED FILE]' not in output
    assert '[DOWNLOADED FILE]' not in output
    assert 'Console URL' in output
