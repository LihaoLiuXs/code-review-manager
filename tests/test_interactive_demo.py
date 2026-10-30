"""Demo steps require a fresh answer before their side effects begin."""
import sys
import pytest
from hrl import cli
from hrl.multicloud_store import Store
from test_workflow import fake_client
from test_demo_command import demo_checkout


@pytest.mark.parametrize('stop_at', [1, 2, 3, 4])
def test_no_stops_before_the_selected_step(demo_checkout, monkeypatch, capsys, stop_at):
    root, _ = demo_checkout
    client, blobs = fake_client('gcp')
    monkeypatch.setattr(cli, 'connect', lambda p, c: Store(client))
    prompts = []
    def answer(prompt):
        prompts.append(prompt)
        if len(prompts) == 2:
            assert not (root / 'examples/pending.json').exists()
        if len(prompts) == 3:
            assert client.upload.call_count == 0
        if len(prompts) == 4:
            assert client.upload.call_count == 1 and client.download.call_count == 1
        return 'n' if len(prompts) == stop_at else 'y'
    monkeypatch.setattr('builtins.input', answer)
    monkeypatch.setattr(sys, 'argv', ['demo', 'save', '--provider', 'gcp'])
    assert cli.main('demo') == 130
    assert len(prompts) == stop_at
    assert all('Start next step?' in prompt for prompt in prompts)
    assert client.upload.call_count == (1 if stop_at == 4 else 0)
    assert client.download.call_count == (0 if stop_at == 1 else 1)
    assert bool(blobs) == (stop_at == 4)
    output = capsys.readouterr().out
    assert '[PROCESS STOPPED]' in output
    assert '[PROCESS COMPLETE]' not in output
    assert 'DEMO COMPLETED SUCCESSFULLY' not in output
    if stop_at == 4:
        assert 'upload remains' in output.lower()
        assert 'not verified' in output.lower()


def test_yes_at_every_step_performs_the_whole_sdk_demo(demo_checkout, monkeypatch, capsys):
    client, _ = fake_client('aws')
    monkeypatch.setattr(cli, 'connect', lambda p, c: Store(client))
    answers = iter(['yes', 'Y', 'y', 'YES'])
    prompts = []
    def answer(prompt):
        prompts.append(prompt)
        return next(answers)
    monkeypatch.setattr('builtins.input', answer)
    monkeypatch.setattr(sys, 'argv', ['demo', 'save', '--provider', 'aws'])
    assert cli.main('demo') == 0
    assert len(prompts) == 4
    assert client.upload.call_count == 1 and client.download.call_count == 2
    assert 'DEMO COMPLETED SUCCESSFULLY' in capsys.readouterr().out


@pytest.mark.parametrize('answer', ['', None])
def test_empty_answer_or_eof_does_not_start_cloud_access(demo_checkout, monkeypatch, capsys, answer):
    def forbidden(*args):
        pytest.fail('No cloud connection is permitted before the first yes')
    monkeypatch.setattr(cli, 'connect', forbidden)
    def respond(prompt):
        if answer is None:
            raise EOFError
        return answer
    monkeypatch.setattr('builtins.input', respond)
    monkeypatch.setattr(sys, 'argv', ['demo', 'save', '--provider', 'aws'])
    assert cli.main('demo') == 130
    assert '[PROCESS STOPPED]' in capsys.readouterr().out


def test_invalid_answer_reprompts_without_cloud_access(demo_checkout, monkeypatch):
    def forbidden(*args):
        pytest.fail('No cloud access before an explicit yes')
    monkeypatch.setattr(cli, 'connect', forbidden)
    answers = iter(['maybe', 'no'])
    prompts = []
    def respond(prompt):
        prompts.append(prompt)
        return next(answers)
    monkeypatch.setattr('builtins.input', respond)
    monkeypatch.setattr(sys, 'argv', ['demo', 'save', '--provider', 'aws'])
    assert cli.main('demo') == 130
    assert len(prompts) == 2


def test_explicit_yes_option_runs_without_prompts(demo_checkout, monkeypatch, capsys):
    client, _ = fake_client('gcp')
    monkeypatch.setattr(cli, 'connect', lambda p, c: Store(client))
    def forbidden(prompt):
        pytest.fail('--yes must run without prompts')
    monkeypatch.setattr('builtins.input', forbidden)
    monkeypatch.setattr(sys, 'argv', ['demo', 'save', '--provider', 'gcp', '--yes'])
    assert cli.main('demo') == 0
    assert 'DEMO COMPLETED SUCCESSFULLY' in capsys.readouterr().out
