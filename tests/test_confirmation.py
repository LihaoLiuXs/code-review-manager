"""Regression cases for unresolved provenance being skipped before extraction."""
import pytest
from hrl import cli
from hrl.classification import ask, classify, confirm, fingerprint
from hrl.io import read_json, write_json


def setup_reviews(path, bodies):
    comments = [dict(repo_id='o/r', comment_id=f'conversation_candidate:{i}',
                     pr_number=i, pr_title=f'PR {i}', review_id='', file_path=None,
                     body=body, comment_url=f'https://github.com/o/r/pull/{i}#issuecomment-{i}')
                for i, body in enumerate(bodies, 1)]
    write_json(path/'reviews.json', dict(repo_id='o/r', complete=True, comments=comments))
    write_json(path/'classifications.json', [classify(c, {}) for c in comments])
    write_json(path/'observations.json', [])
    return comments


@pytest.mark.parametrize('body', ['LGTM', 'Created release v0.1.9',
    'Closing: internal onboarding links belong in the internal guide, not the public site.'])
def test_unanswered_uncertain_comments_block_even_empty_extraction(tmp_path, body):
    setup_reviews(tmp_path, [body])
    with pytest.raises(ValueError, match='confirmation'):
        cli.build('o/r', tmp_path)
    assert not (tmp_path/'pending.json').exists()


def test_pending_queue_includes_all_nine_comments_before_relevance_filtering(tmp_path):
    setup_reviews(tmp_path, ['Dependabot cannot update this PR']*2 + ['Created releases']*6 + ['Internal onboarding links belong in the internal guide'])
    pending = cli.pending_confirmations('o/r', tmp_path)
    assert len(pending) == 9
    assert pending[0]['comment_id'] == 'conversation_candidate:1'
    assert pending[-1]['body'] == 'Internal onboarding links belong in the internal guide'
    assert all(c['comment_url'] and c['reason'] for c in pending)


def test_native_answers_persist_selected_comments_and_leave_others_pending(tmp_path):
    setup_reviews(tmp_path, ['Looks fine', 'Is this retry safe?'])
    cli.confirm_file('o/r', tmp_path, ['conversation_candidate:2'], 'HUMAN')
    result = read_json(tmp_path/'classifications.json')
    assert result[1]['classification'] == 'HUMAN'
    assert result[1]['classification_method'] == 'manual'
    assert read_json(tmp_path/'decisions.json')['o/r:conversation_candidate:2']['classification'] == 'HUMAN'
    assert [c['comment_id'] for c in cli.pending_confirmations('o/r',tmp_path)] == ['conversation_candidate:1']


def test_explicit_skip_resolves_question_without_becoming_human(tmp_path):
    setup_reviews(tmp_path, ['Looks fine'])
    cli.confirm_file('o/r', tmp_path, ['conversation_candidate:1'], 'UNCERTAIN')
    assert cli.pending_confirmations('o/r',tmp_path) == []
    assert read_json(tmp_path/'classifications.json')[0]['classification'] == 'UNCERTAIN'
    cli.build('o/r',tmp_path)
    assert not (tmp_path/'pending.json').exists()


def test_unbacked_manual_skip_does_not_bypass_gate(tmp_path):
    comments = setup_reviews(tmp_path, ['Looks fine'])
    write_json(tmp_path/'classifications.json', [confirm(comments[0], 'UNCERTAIN', {})])
    with pytest.raises(ValueError,match='confirmation'):
        cli.build('o/r',tmp_path)


def test_edited_comment_invalidates_manual_decision(tmp_path):
    comments = setup_reviews(tmp_path, ['Looks fine'])
    cli.confirm_file('o/r', tmp_path, ['conversation_candidate:1'], 'HUMAN')
    comments[0]['body'] = 'Changed feedback'
    write_json(tmp_path/'reviews.json', dict(repo_id='o/r', complete=True, comments=comments))
    cli.classify_file(tmp_path, {}, False)
    assert len(cli.pending_confirmations('o/r',tmp_path)) == 1


def test_confirmation_rejects_unknown_ids_without_partial_updates(tmp_path):
    setup_reviews(tmp_path, ['Looks fine'])
    before = (tmp_path/'classifications.json').read_text()
    with pytest.raises(ValueError,match='Unknown'):
        cli.confirm_file('o/r',tmp_path,['conversation_candidate:1','missing'],'HUMAN')
    assert (tmp_path/'classifications.json').read_text() == before
    assert not (tmp_path/'decisions.json').exists()


def test_eof_leaves_confirmation_pending_instead_of_saving_a_skip():
    comment = dict(repo_id='o/r',comment_id='conversation_candidate:1',pr_number=1,
                   body='Looks fine',comment_url='https://github.com/o/r/pull/1')
    decisions = {}
    def no_input(_): raise EOFError
    result = ask(comment,decisions,input_fn=no_input)
    assert result['classification'] == 'UNCERTAIN'
    assert result['classification_method'] != 'manual'
    assert decisions == {}


def test_confirmed_human_cannot_be_silently_dropped(tmp_path):
    setup_reviews(tmp_path, ['Internal onboarding cross-links belong in the internal guide.'])
    cli.confirm_file('o/r',tmp_path,['conversation_candidate:1'],'HUMAN')
    with pytest.raises(ValueError,match='extraction_report'):
        cli.build('o/r',tmp_path)


def test_nonactionable_human_can_be_omitted_with_an_explicit_reason(tmp_path,capsys):
    comments = setup_reviews(tmp_path,['Created release v0.1.9'])
    cli.confirm_file('o/r',tmp_path,['conversation_candidate:1'],'HUMAN')
    write_json(tmp_path/'extraction_report.json',[dict(comment_id='conversation_candidate:1',
        decision='omit',reason='Release announcement only; no coding or review guidance.',
        fingerprint=fingerprint(comments[0]))])
    cli.build('o/r',tmp_path)
    assert not (tmp_path/'pending.json').exists()
    assert '1 confirmed HUMAN' in capsys.readouterr().out


def test_single_confirmed_comment_can_support_tentative_scoped_guidance(tmp_path):
    setup_reviews(tmp_path,['The cross-link belongs in the internal onboarding guide and points to public docs.'])
    cli.confirm_file('o/r',tmp_path,['conversation_candidate:1'],'HUMAN')
    write_json(tmp_path/'observations.json',[dict(
        title='Place internal onboarding links in the internal guide',
        tags=['documentation'], rule='Tentative convention: for this repository, place internal onboarding cross-links in the internal guide.',
        why='One confirmed human comment identifies that documentation boundary.',
        checks=['Does this link serve internal onboarding?'],source_ids=['conversation_candidate:1'])])
    cli.build('o/r',tmp_path)
    md=(tmp_path/'review_knowledge.md').read_text()
    assert 'Tentative convention' in md
    assert '#issuecomment-1' in md


def test_collection_distinguishes_scanned_prs_from_prs_with_feedback():
    from datetime import datetime,timezone
    from hrl.github_reviews import collect
    class Api:
        def pages(self,endpoint):
            return [dict(number=19,title='No comments')] if '/pulls?' in endpoint else []
    result=collect('o/r',30,api=Api(),now=datetime(2026,10,26,tzinfo=timezone.utc))
    assert result['scanned_pr_count']==1
    assert result['pr_count']==0


def test_native_confirmation_cli_roundtrip(tmp_path):
    import subprocess
    import sys
    setup_reviews(tmp_path,['Review this edge case'])
    command=[sys.executable,'scripts/workflow.py','confirm','--repo','o/r',
             '--output-dir',str(tmp_path),'--ids','conversation_candidate:1','--label','HUMAN']
    result=subprocess.run(command,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    assert '0 confirmation(s) remaining' in result.stdout
    assert read_json(tmp_path/'classifications.json')[0]['classification']=='HUMAN'


def test_omission_report_is_invalidated_when_comment_changes(tmp_path):
    comments=setup_reviews(tmp_path,['Created release'])
    cli.confirm_file('o/r',tmp_path,['conversation_candidate:1'],'HUMAN')
    write_json(tmp_path/'extraction_report.json',[dict(comment_id='conversation_candidate:1',
        fingerprint=fingerprint(comments[0]),decision='omit',reason='Only a release announcement')])
    comments[0]['body']='Also preserve public API backward compatibility.'
    write_json(tmp_path/'reviews.json',dict(repo_id='o/r',complete=True,comments=comments))
    cli.classify_file(tmp_path,{},False)
    cli.confirm_file('o/r',tmp_path,['conversation_candidate:1'],'HUMAN')
    with pytest.raises(ValueError,match='extraction_report'):
        cli.build('o/r',tmp_path)


def test_nine_comment_scenario_keeps_scoped_docs_guidance(tmp_path):
    comments=setup_reviews(tmp_path,['Dependabot cannot update this PR']*2 +
        ['Created releases']*6 + ['The cross-link belongs in the internal onboarding guide and points to the public docs.'])
    assert len(cli.pending_confirmations('o/r',tmp_path))==9
    cli.confirm_file('o/r',tmp_path,[c['comment_id'] for c in comments],'HUMAN')
    assert cli.pending_confirmations('o/r',tmp_path)==[]
    write_json(tmp_path/'extraction_report.json',[
        dict(comment_id=c['comment_id'],fingerprint=fingerprint(c),decision='omit',
             reason='Dependency update status only' if i<2 else 'Release announcement only')
        for i,c in enumerate(comments[:8])])
    write_json(tmp_path/'observations.json',[dict(title='Keep onboarding cross-links in the internal guide',
        rule='Tentative convention: in this repository, place internal onboarding cross-links in the internal onboarding guide.',
        why='A confirmed human closure note states the intended documentation location.',
        checks=['Is the proposed cross-link intended for internal onboarding?'],tags=['documentation'],
        source_ids=[comments[8]['comment_id']])])
    cli.build('o/r',tmp_path)
    record=read_json(tmp_path/'record.json')
    assert record['human_comment_count']==9
    assert len(record['rules'])==1
    assert record['rules'][0]['sources'][0]['comment_id']==comments[8]['comment_id']
    assert 'Tentative convention' in record['knowledge_md']
