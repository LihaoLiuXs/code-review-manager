"""Repository links and owner/name shorthand must select the same target."""
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from hrl import cli
from hrl.github_reviews import collect, validate_repo
from hrl.multicloud_store import object_key


@pytest.mark.parametrize('value', [
    'salesforce/multicloudj',
    'https://github.com/salesforce/multicloudj',
    'https://github.com/salesforce/multicloudj/',
    'https://github.com/salesforce/multicloudj.git',
    'https://github.com/salesforce/multicloudj?tab=readme-ov-file#readme',
    '  https://github.com/salesforce/multicloudj  ',
])
def test_repository_links_normalize_to_owner_and_name(value):
    assert validate_repo(value) == 'salesforce/multicloudj'


@pytest.mark.parametrize('value', [
    'https://github.com.evil.example/salesforce/multicloudj',
    'https://example.com/salesforce/multicloudj',
    'https://github.com/salesforce/multicloudj/pull/123',
    'https://github.com/salesforce',
    'https://user:password@github.com/salesforce/multicloudj',
    'http://github.com/salesforce/multicloudj',
    'salesforce/../multicloudj',
    'salesforce/..',
])
def test_invalid_links_fail_before_api_access(value):
    with pytest.raises(ValueError):
        validate_repo(value)


def test_collector_uses_requested_java_repository_for_url_input():
    api = Mock()
    def pages(endpoint):
        if '/pulls?' in endpoint:
            return [dict(number=42,title='Java SDK review')]
        if endpoint.endswith('/reviews'):
            return [dict(id=7,body='Preserve provider exception semantics',
                submitted_at='2026-10-25T12:00:00Z',user={'login':'reviewer'},
                html_url='https://github.com/salesforce/multicloudj/pull/42#pullrequestreview-7')]
        return []
    api.pages.side_effect = pages
    result = collect('https://github.com/salesforce/multicloudj',90,api=api,
                     now=datetime(2026,10,26,tzinfo=timezone.utc))
    assert result['repo_id'] == 'salesforce/multicloudj'
    assert result['comments'][0]['repo_id'] == 'salesforce/multicloudj'
    assert result['comments'][0]['pr_url'] == 'https://github.com/salesforce/multicloudj/pull/42'
    assert all(call.args[0].startswith('repos/salesforce/multicloudj/') for call in api.pages.call_args_list)


def test_fetch_cli_normalizes_before_collection_and_output_directory(tmp_path,monkeypatch):
    from hrl.io import read_json
    import sys
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys,'argv',['fetch_reviews.py','--repo',
        'https://github.com/salesforce/multicloudj','--days','90'])
    fake = Mock()
    monkeypatch.setattr(cli,'Gh',lambda:fake)
    def collect_repo(repo,days,**kwargs):
        assert repo == 'salesforce/multicloudj'
        return dict(repo_id=repo,comments=[],pr_count=0,scanned_pr_count=1,complete=True)
    monkeypatch.setattr(cli,'collect',collect_repo)
    assert cli.main('fetch') == 0
    assert read_json(tmp_path/'output/salesforce--multicloudj/reviews.json')['repo_id']=='salesforce/multicloudj'


def test_storage_cli_uses_same_logical_key_for_link_and_shorthand(monkeypatch):
    import sys
    store=Mock()
    store.load.return_value=None
    monkeypatch.setattr(cli,'connect',lambda p,c:store)
    monkeypatch.setattr(sys,'argv',['storage.py','get','--provider','aws','--repo',
        'https://github.com/salesforce/multicloudj'])
    assert cli.main('storage') == 0
    store.load.assert_called_once_with('salesforce/multicloudj')
    assert object_key(validate_repo('https://github.com/salesforce/multicloudj')) == 'review_knowledge/salesforce%2Fmulticloudj.json'
