"""Short demo commands keep the shared SDK workflow and its safety checks."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from hrl import cli
from hrl.io import read_json, write_json
from hrl.multicloud_store import Store, make_record
from test_workflow import fake_client


@pytest.fixture
def demo_checkout(tmp_path, monkeypatch):
    root = tmp_path / 'checkout with spaces'
    sample = root / 'examples' / 'review_knowledge.demo.md'
    sample.parent.mkdir(parents=True)
    sample.write_text('# DEMO ONLY\n\nSynthetic review knowledge.\n')
    (root / 'config.toml').write_text('[storage.aws]\nbucket="aws-demo"\n[storage.gcp]\nbucket="gcp-demo"\n')
    monkeypatch.setattr(cli, 'PROJECT_ROOT', root, raising=False)
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return root, sample


@pytest.mark.parametrize('provider', ['aws', 'gcp'])
def test_short_demo_uploads_sample_and_reads_it_back_on_only_selected_cloud(demo_checkout, monkeypatch, capsys, provider):
    root, sample = demo_checkout
    client, blobs = fake_client(provider)
    def connect(selected, config):
        assert selected == provider, 'Short command must access only the selected cloud'
        assert config['storage'][selected]['bucket'] == f'{provider}-demo'
        return Store(client)
    monkeypatch.setattr(cli, 'connect', connect)
    monkeypatch.setattr(sys, 'argv', ['demo', '--yes', '--provider', provider])
    assert cli.main('demo') == 0
    stored = json.loads(next(iter(blobs.values())))
    assert stored['repo_id'] == 'demo/human-review-learning'
    assert stored['knowledge_md'] == sample.read_text()
    assert read_json(root / 'examples' / 'pending.json')['record'] == stored
    output = capsys.readouterr().out
    assert 'Files uploaded : 1/1' in output
    assert 'READ-BACK START' in output
    assert 'Files verified : 1/1' in output
    assert '[PROCESS COMPLETE]' in output


@pytest.mark.parametrize('provider', ['aws', 'gcp'])
def test_demo_accepts_custom_relative_markdown_and_repository(demo_checkout, monkeypatch, provider):
    client, blobs = fake_client(provider)
    monkeypatch.setattr(cli, 'connect', lambda p, c: Store(client))
    Path('my-knowledge.md').write_text('# Custom demo\n')
    monkeypatch.setattr(sys, 'argv', ['demo', '--yes', '--provider', provider, '--repo', 'demo/custom', '--file', 'my-knowledge.md'])
    assert cli.main('demo') == 0
    stored = json.loads(next(iter(blobs.values())))
    assert stored['repo_id'] == 'demo/custom'
    assert stored['knowledge_md'] == '# Custom demo\n'
    assert read_json('pending.json')['record'] == stored


def test_demo_get_uses_default_repository_without_uploading(demo_checkout, monkeypatch, capsys):
    client, blobs = fake_client('gcp')
    blobs['review_knowledge/demo%2Fhuman-review-learning.json'] = json.dumps(make_record('demo/human-review-learning', 'previous knowledge', [], None, {})).encode()
    monkeypatch.setattr(cli, 'connect', lambda p, c: Store(client))
    monkeypatch.setattr(sys, 'argv', ['demo', 'get', '--yes', '--provider', 'gcp', '--output', 'download.json'])
    assert cli.main('demo') == 0
    assert read_json('download.json')['knowledge_md'] == 'previous knowledge'
    assert '[PROCESS COMPLETE]' in capsys.readouterr().out
    assert client.upload.call_count == 0


def test_demo_record_retry_does_not_fall_back_to_sample(demo_checkout, monkeypatch):
    client, blobs = fake_client('aws')
    monkeypatch.setattr(cli, 'connect', lambda p, c: Store(client))
    record = make_record('demo/human-review-learning', 'exact retry content', [], None, {})
    write_json('pending.json', {'base': None, 'record': record})
    monkeypatch.setattr(sys, 'argv', ['demo', '--yes', '--provider', 'aws', '--record', 'pending.json'])
    assert cli.main('demo') == 0
    assert json.loads(next(iter(blobs.values()))) == record


def test_demo_still_requires_explicit_provider(demo_checkout, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['demo'])
    with pytest.raises(SystemExit) as exc:
        cli.main('demo')
    assert exc.value.code == 2


def test_demo_reports_failed_readback_as_failure(demo_checkout, monkeypatch, capsys):
    client, _ = fake_client('aws')
    original = client.download.side_effect
    def download(key):
        if client.upload.call_count:
            raise RuntimeError('read-back unavailable')
        return original(key)
    client.download.side_effect = download
    monkeypatch.setattr(cli, 'connect', lambda p, c: Store(client))
    monkeypatch.setattr(sys, 'argv', ['demo', '--yes', '--provider', 'aws'])
    assert cli.main('demo') == 1
    output = capsys.readouterr().out
    assert '[PROCESS FAILED]' in output
    assert '[PROCESS COMPLETE]' not in output


def test_executable_demo_launcher_runs_from_another_directory(tmp_path):
    launcher = Path(__file__).resolve().parents[1] / 'demo'
    result = subprocess.run([str(launcher), '--help'], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert '--provider' in result.stdout
    assert 'demo/human-review-learning' in result.stdout
