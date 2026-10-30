"""The directory demo exercises real SDK contracts with controlled transfers."""
import json
import sys
from pathlib import Path
from unittest.mock import create_autospec
import pytest
from multicloud.blob.blob_client import AsyncBucketClient, AsyncDirectoryUploadResponse, AsyncDirectoryDownloadResponse
from multicloud.blob.blob_client.async_blob.async_driver import FailedAsyncBlobUpload, FailedAsyncBlobDownload
from hrl import cli


@pytest.fixture
def bundle_demo(tmp_path, monkeypatch):
    import hrl.directory_demo as module
    root = tmp_path / 'checkout'
    source = root / 'examples/review_bundle'
    source.mkdir(parents=True)
    (source / 'knowledge.md').write_text('# DEMO ONLY\nSynthetic knowledge.\n')
    (source / 'rules').mkdir()
    (source / 'rules/conventions.json').write_text('{"demo_only":true,"rules":[]}\n')
    (source / 'reviews').mkdir()
    (source / 'reviews/comments.json').write_text('{"demo_only":true,"comments":[]}\n')
    monkeypatch.setattr(cli, 'PROJECT_ROOT', root)
    monkeypatch.chdir(tmp_path)
    client = create_autospec(AsyncBucketClient, instance=True)
    client.bucket = 'demo-bucket'
    blobs = {}
    async def upload(local_source_directory, *, prefix, **kwargs):
        files = [p for p in Path(local_source_directory).rglob('*') if p.is_file()]
        for p in files:
            blobs[prefix + p.relative_to(local_source_directory).as_posix()] = p.read_bytes()
        return AsyncDirectoryUploadResponse(total_files=len(files),successful_uploads=len(files),total_bytes_transferred=sum(map(len,blobs.values())))
    async def download(prefix, local_destination_directory, **kwargs):
        for key, content in blobs.items():
            path = Path(local_destination_directory) / key[len(prefix):]
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(content)
        return AsyncDirectoryDownloadResponse(total_files=len(blobs),successful_downloads=len(blobs),total_bytes_transferred=sum(map(len,blobs.values())))
    client.upload_directory.side_effect = upload
    client.download_directory.side_effect = download
    async def delete(prefix):
        assert prefix and prefix.endswith('/')
        for key in list(blobs):
            if key.startswith(prefix):
                del blobs[key]
    client.delete_directory.side_effect = delete
    from types import SimpleNamespace
    client.list_page.return_value = SimpleNamespace(blobs=[])
    selected = []
    def connect(provider, config):
        selected.append(provider)
        return client
    monkeypatch.setattr(module, 'connect', connect)
    return source, client, blobs, selected


def run(monkeypatch, provider='gcp', *flags):
    monkeypatch.setattr(sys,'argv',['demo','directory','--provider',provider,*flags])
    return cli.main('demo')


@pytest.mark.parametrize('provider',['aws','gcp'])
def test_native_directory_roundtrip_preserves_nested_review_bundle(bundle_demo, monkeypatch, capsys, provider):
    source, client, blobs, selected = bundle_demo
    assert run(monkeypatch,provider,'--yes') == 0
    assert selected == [provider]
    prefix = client.upload_directory.call_args.kwargs['prefix']
    assert prefix.startswith('review_bundles/demo%2Fhuman-review-learning/') and prefix.endswith('/')
    expected = {p.relative_to(source).as_posix():p.read_bytes() for p in source.rglob('*') if p.is_file()}
    assert {k[len(prefix):]:v for k,v in blobs.items()} == expected
    restored = Path(client.download_directory.call_args.args[1])
    assert {p.relative_to(restored).as_posix():p.read_bytes() for p in restored.rglob('*') if p.is_file()} == expected
    output = capsys.readouterr().out
    assert 'AsyncBucketClient.upload_directory()' in output
    assert 'AsyncBucketClient.download_directory()' in output
    assert 'Files uploaded : 3/3' in output and 'Files verified : 3/3' in output
    assert 'rules/conventions.json' in output and 'reviews/comments.json' in output
    assert 'DIRECTORY DEMO COMPLETED SUCCESSFULLY' in output
    client.close.assert_awaited_once()
    client.delete_directory.assert_not_awaited()


@pytest.mark.parametrize('failure',['upload','download','mismatch','missing','extra'])
def test_partial_or_invalid_directory_transfer_never_claims_success(bundle_demo, monkeypatch, capsys, failure):
    source, client, _, _ = bundle_demo
    if failure == 'upload':
        client.upload_directory.side_effect = None
        client.upload_directory.return_value = AsyncDirectoryUploadResponse(total_files=3,successful_uploads=2,
            failed_transfers=[FailedAsyncBlobUpload(source=source/'knowledge.md',exception=RuntimeError('upload denied'))])
    else:
        original = client.download_directory.side_effect
        async def download(prefix, destination, **kwargs):
            result = await original(prefix,destination,**kwargs)
            target = Path(destination)/'knowledge.md'
            if failure == 'download':
                return AsyncDirectoryDownloadResponse(total_files=3,successful_downloads=2,
                    failed_transfers=[FailedAsyncBlobDownload(destination=target,exception=RuntimeError('download denied'))])
            if failure == 'mismatch': target.write_text('Changed remote content')
            elif failure == 'missing': target.unlink()
            elif failure == 'extra': (Path(destination)/'unexpected.txt').write_text('extra')
            return result
        client.download_directory.side_effect = download
    assert run(monkeypatch,'gcp','--yes') == 1
    output = capsys.readouterr().out
    assert 'DIRECTORY DEMO COMPLETED SUCCESSFULLY' not in output
    assert '[PROCESS FAILED]' in output
    client.delete_directory.assert_not_awaited()
    client.close.assert_awaited_once()
    if failure == 'upload': client.download_directory.assert_not_awaited()


@pytest.mark.parametrize('stop_at',[1,2,3,4])
def test_directory_steps_wait_for_presenter_input(bundle_demo, monkeypatch, capsys, stop_at):
    _, client, _, _ = bundle_demo
    answers = iter(['yes']*(stop_at-1)+['no'])
    monkeypatch.setattr('builtins.input',lambda prompt:next(answers))
    assert run(monkeypatch) == 130
    assert client.upload_directory.await_count == (1 if stop_at>2 else 0)
    assert client.download_directory.await_count == (1 if stop_at>3 else 0)
    assert 'DIRECTORY DEMO COMPLETED SUCCESSFULLY' not in capsys.readouterr().out


def test_cleanup_targets_only_the_current_generated_bundle_prefix(bundle_demo, monkeypatch, capsys):
    _, client, blobs, _ = bundle_demo
    assert run(monkeypatch,'gcp','--yes','--cleanup') == 0
    prefix = client.upload_directory.call_args.kwargs['prefix']
    client.delete_directory.assert_awaited_once_with(prefix)
    client.list_page.assert_awaited_once_with(prefix=prefix,max_results=1)
    assert not blobs
    assert 'AsyncBucketClient.delete_directory()' in capsys.readouterr().out


def test_cancel_cleanup_preserves_uploaded_bundle(bundle_demo, monkeypatch, capsys):
    _, client, blobs, _ = bundle_demo
    answers=iter(['yes']*4+['no'])
    monkeypatch.setattr('builtins.input',lambda prompt:next(answers))
    assert run(monkeypatch,'gcp','--cleanup') == 130
    assert blobs
    client.delete_directory.assert_not_awaited()
    assert 'DIRECTORY DEMO COMPLETED SUCCESSFULLY' not in capsys.readouterr().out


def test_symlinks_are_rejected_before_any_directory_upload(bundle_demo, monkeypatch, capsys):
    source, client, _, _ = bundle_demo
    (source/'linked.md').symlink_to(source/'knowledge.md')
    assert run(monkeypatch,'gcp','--yes') == 1
    client.upload_directory.assert_not_awaited()
    assert 'symlink' in capsys.readouterr().err.lower()


def test_cleanup_is_not_reported_successful_when_objects_remain(bundle_demo, monkeypatch, capsys):
    from types import SimpleNamespace
    _, client, _, _ = bundle_demo
    client.list_page.return_value = SimpleNamespace(blobs=[SimpleNamespace(key='still-present')])
    assert run(monkeypatch,'gcp','--yes','--cleanup') == 1
    assert 'DIRECTORY DEMO COMPLETED SUCCESSFULLY' not in capsys.readouterr().out
    client.close.assert_awaited_once()
