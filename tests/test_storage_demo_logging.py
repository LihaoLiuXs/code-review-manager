"""The audience must see actual upload, download, counts, and honest outcomes."""
import json
import sys
import pytest
from multicloud.blob.blob_client import DownloadResponse
from hrl import cli
from hrl.multicloud_store import Store
from test_workflow import fake_client


def run_demo(tmp_path,monkeypatch,provider,client):
    source=tmp_path/'review_knowledge.md'
    source.write_text('# Knowledge demo\n\nSynthetic example guidance.\n')
    monkeypatch.setattr(cli,'connect',lambda p,c:Store(client))
    monkeypatch.setattr(sys,'argv',['storage.py','save','--provider',provider,
        '--repo','demo/logs','--file',str(source)])
    return cli.main('storage')


@pytest.mark.parametrize('provider',['aws','gcp'])
def test_demo_narrates_file_upload_and_separate_sdk_read(tmp_path,monkeypatch,capsys,provider):
    client,_=fake_client(provider)
    assert run_demo(tmp_path,monkeypatch,provider,client)==0
    output=capsys.readouterr().out
    assert '[PROCESS START]' in output
    assert 'DOWNLOAD EXISTING KNOWLEDGE' in output
    assert 'CHECK CLOUD ACCESS' not in output
    assert 'Input Markdown:' in output and 'review_knowledge.md' in output
    assert 'Files planned  : 1' in output
    assert 'BucketClient.upload()' in output
    assert 'Files uploaded : 1/1' in output
    assert 'READ-BACK START' in output
    assert 'BucketClient.download()' in output
    assert 'Files read back: 1/1' in output
    assert 'Files verified : 1/1' in output
    assert 'knowledge_md' in output and 'JSON' in output
    assert '[PROCESS COMPLETE]' in output
    assert output.index('WRITE OK') < output.index('READ-BACK START') < output.index('VERIFIED') < output.index('[PROCESS COMPLETE]')
    assert [c[0] for c in client.method_calls]==['download','does_bucket_exist','upload','download','close']


def test_upload_failure_does_not_claim_uploaded_or_read_back(tmp_path,monkeypatch,capsys):
    client,_=fake_client('aws')
    client.upload.side_effect=RuntimeError('upload denied')
    assert run_demo(tmp_path,monkeypatch,'aws',client)==1
    output=capsys.readouterr().out
    assert '[PROCESS START]' in output
    assert 'WRITE FAILED' in output
    assert '[PROCESS FAILED]' in output
    assert 'Files uploaded : 1/1' not in output
    assert 'READ-BACK START' not in output
    assert '[PROCESS COMPLETE]' not in output
    assert client.download.call_count==1  # Only the preflight read.


@pytest.mark.parametrize('failure',['different_content','read_error'])
def test_readback_failure_keeps_upload_success_but_no_completion(tmp_path,monkeypatch,capsys,failure):
    client,_=fake_client('gcp')
    download=client.download.side_effect
    def read(key):
        response=download(key)
        if failure=='read_error':
            raise RuntimeError('download unavailable after upload')
        value=json.loads(response.content)
        value['knowledge_md']='different remote content'
        return DownloadResponse(key=key,content=json.dumps(value).encode(),metadata=None)
    client.download.side_effect=read
    assert run_demo(tmp_path,monkeypatch,'gcp',client)==1
    output=capsys.readouterr().out
    assert 'Files uploaded : 1/1' in output
    assert 'READ-BACK START' in output
    assert 'Files verified : 0/1' in output
    assert '[PROCESS FAILED]' in output
    assert '[PROCESS COMPLETE]' not in output


@pytest.mark.parametrize('provider', ['aws', 'gcp'])
def test_presentation_logs_show_timed_stages_and_human_readable_summary(tmp_path, monkeypatch, capsys, provider):
    import re
    import hashlib
    client, _ = fake_client(provider)
    assert run_demo(tmp_path, monkeypatch, provider, client) == 0
    output = capsys.readouterr().out
    assert re.search(r'\d{2}:\d{2}:\d{2}\.\d{3}\s+INFO\s+BlobStore', output)
    for stage in ['[STEP 1/4]', '[STEP 2/4]', '[STEP 3/4]', '[STEP 4/4]']:
        assert stage in output
    assert 'Files uploaded : 1/1' in output
    assert 'Files read back: 1/1' in output
    assert 'Files verified : 1/1' in output
    assert re.search(r'Elapsed\s*:\s*\d+\.\d{3} s', output)
    assert 'Demo completed successfully' in output
    expected_hash = hashlib.sha256((tmp_path / 'review_knowledge.md').read_bytes()).hexdigest()
    assert expected_hash in output
    assert output.index('[STEP 1/4]') < output.index('[STEP 2/4]') < output.index('[STEP 3/4]') < output.index('[STEP 4/4]')


def test_presentation_failure_is_error_level_and_has_no_success_summary(tmp_path, monkeypatch, capsys):
    import re
    client, _ = fake_client('gcp')
    client.upload.side_effect = RuntimeError('upload denied')
    assert run_demo(tmp_path, monkeypatch, 'gcp', client) == 1
    output = capsys.readouterr().out
    assert re.search(r'ERROR\s+BlobStore\s+\[WRITE FAILED\]', output)
    assert 'Demo completed successfully' not in output
    assert 'Files uploaded : 1/1' not in output
    assert 'Files verified : 1/1' not in output


@pytest.mark.parametrize('provider', ['aws', 'gcp'])
def test_full_visual_demo_has_sections_and_success_only_after_verification(tmp_path, monkeypatch, capsys, provider):
    client, _ = fake_client(provider)
    assert run_demo(tmp_path, monkeypatch, provider, client) == 0
    output = capsys.readouterr().out
    assert '╔' in output and '╚' in output
    assert 'MultiCloud Python SDK — Knowledge Demo' in output
    assert 'UPLOAD KNOWLEDGE' in output
    assert 'READ BACK & VERIFY' in output
    assert '📋 Configuration' in output
    assert f'Bucket         : {client.bucket}' in output
    assert '✅' in output and '🔄' in output
    assert 'DEMO COMPLETED SUCCESSFULLY' in output
    assert output.index('[VERIFIED]') < output.index('DEMO COMPLETED SUCCESSFULLY')


def test_failed_visual_demo_never_displays_success_banner(tmp_path, monkeypatch, capsys):
    client, _ = fake_client('gcp')
    client.upload.side_effect = RuntimeError('upload denied')
    assert run_demo(tmp_path, monkeypatch, 'gcp', client) == 1
    output = capsys.readouterr().out
    assert '❌' in output
    assert 'DEMO COMPLETED SUCCESSFULLY' not in output
