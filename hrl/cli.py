"""Manual commands used by the agent skill and engineers."""
import argparse
import json
import sys
import tomllib
from pathlib import Path
from collections import Counter
from time import perf_counter

from hrl.console import DemoStopped, banner, event, size, step

from hrl.classification import classify, ask, fingerprint, confirm, manual_decision
from hrl.github_reviews import Gh, collect, validate_repo
from hrl.io import read_json, write_json, write_text
from hrl.knowledge import merge, render
from hrl.multicloud_store import connect, choose_existing, make_record, save_selected


PROJECT_ROOT = Path(__file__).resolve().parents[1]

def output_dir(repo, value=None):
    return Path(value) if value else Path('output') / repo.replace('/', '--')


def classify_file(directory, config, interactive):
    reviews = read_json(directory/'reviews.json')
    if not reviews or not reviews.get('complete'):
        raise ValueError('Need complete reviews.json from fetch_reviews.py')
    decisions = read_json(directory/'decisions.json', {})
    patterns = config.get('classification', {}).get('ai_patterns')
    report = []
    comments = sorted(reviews['comments'], key=lambda c:(c['pr_number'], c.get('review_id') or '', c['comment_id']))
    for c in comments:
        result = classify(c, decisions, patterns)
        if result['classification'] == 'UNCERTAIN' and result['classification_method'] != 'manual' and interactive:
            result = ask(c, decisions)
            # Persist after every answer so interruption doesn't lose decisions.
            write_json(directory/'decisions.json', decisions)
        report.append(result)
    write_json(directory/'classifications.json', report)
    print('Classification:', dict(Counter(r['classification'] for r in report)))
    pending_count = sum(r['classification'] == 'UNCERTAIN' and r['classification_method'] != 'manual' for r in report)
    print(f'Unanswered provenance confirmations: {pending_count}. '
          'Resolve with Human / AI / Skip before extraction or build.')


def classification_state(repo, directory):
    directory = Path(directory)
    reviews = read_json(directory/'reviews.json')
    if not reviews or reviews['repo_id'] != repo:
        raise ValueError('Review repository mismatch')
    reports = read_json(directory/'classifications.json', [])
    by_id = {r['comment_id']: r for r in reports}
    decisions = read_json(directory/'decisions.json', {})
    resolved = []
    for comment in reviews['comments']:
        report = by_id.get(comment['comment_id'])
        if not report or report.get('fingerprint') != fingerprint(comment):
            raise ValueError('Missing or stale classification report; rerun classify')
        # Recover if execution stopped after saving decisions but before reports.
        report = manual_decision(comment, decisions) or report
        if report.get('classification') not in ('HUMAN', 'AI', 'UNCERTAIN'):
            raise ValueError('Invalid classification label; rerun classify')
        resolved.append(report)
    return reviews, resolved, decisions


def pending_confirmations(repo, directory):
    reviews, reports, decisions = classification_state(repo, directory)
    pending = []
    for comment, report in zip(reviews['comments'], reports):
        if report['classification'] == 'UNCERTAIN' and not manual_decision(comment, decisions):
            pending.append(dict(comment, reason=report.get('reason', 'No reliable provenance'),
                                fingerprint=report['fingerprint']))
    return sorted(pending, key=lambda c: (c['pr_number'], c.get('review_id') or '', c['comment_id']))


def confirm_file(repo, directory, ids, label):
    if label not in ('HUMAN', 'AI', 'UNCERTAIN'):
        raise ValueError('Choose HUMAN, AI, or UNCERTAIN (explicit Skip)')
    directory = Path(directory)
    reviews, reports, decisions = classification_state(repo, directory)
    comments = {c['comment_id']: c for c in reviews['comments']}
    if not ids or any(cid not in comments for cid in ids):
        raise ValueError('Unknown or missing comment IDs; no decisions changed')
    selected = set(ids)
    updated = [confirm(comments[r['comment_id']], label, decisions)
               if r['comment_id'] in selected else r for r in reports]
    write_json(directory/'decisions.json', decisions)
    write_json(directory/'classifications.json', updated)
    write_json(directory/'pending_confirmations.json', pending_confirmations(repo, directory))
    print(f'Confirmed {len(selected)} comment(s) as {label}; '
          f'{len(pending_confirmations(repo, directory))} confirmation(s) remaining')


def build(repo, directory):
    directory = Path(directory)
    reviews, reports, _ = classification_state(repo, directory)
    pending = pending_confirmations(repo, directory)
    write_json(directory/'pending_confirmations.json', pending)
    if pending:
        raise ValueError(f'Developer confirmation required for {len(pending)} UNCERTAIN comment(s), '
                         'including apparently irrelevant notices. Ask Human / AI / Skip before extraction; '
                         'see pending_confirmations.json. No knowledge was generated or overwritten.')
    comments = [dict(comment, classification=report['classification'])
                for comment, report in zip(reviews['comments'], reports)]
    existing = read_json(directory/'existing.json')
    local = read_json(directory/'record.json')
    if existing is None and local:
        existing = local
    if existing and existing['repo_id'] != repo:
        raise ValueError('Existing repository mismatch')
    observations = read_json(directory/'observations.json')
    if not isinstance(observations, list):
        raise ValueError('Agent must write observations.json (a list)')
    used_ids = {cid for observation in observations for cid in observation.get('source_ids', [])}
    audit = read_json(directory/'extraction_report.json', [])
    if not isinstance(audit, list):
        raise ValueError('extraction_report.json must be a list')
    omissions = {entry.get('comment_id'): entry for entry in audit if isinstance(entry, dict)}
    for comment in comments:
        if comment['classification'] != 'HUMAN' or comment['comment_id'] in used_ids:
            continue
        explanation = omissions.get(comment['comment_id'], {})
        if (explanation.get('decision') not in ('omit', 'already_covered')
                or not isinstance(explanation.get('reason'), str)
                or not explanation['reason'].strip()
                or explanation.get('fingerprint') != fingerprint(comment)):
            raise ValueError('Every unused HUMAN comment needs a current, reasoned decision in '
                             'extraction_report.json; ask the developer about plausible tentative guidance')
    old_rules = existing.get('rules', []) if existing else []
    rules = merge(old_rules, observations, comments)
    legacy = existing.get('legacy_md', '') if existing else ''
    local_md = directory/'review_knowledge.md'
    if not existing and local_md.exists():
        legacy = local_md.read_text()
    if existing and not old_rules and not legacy:
        legacy = existing['knowledge_md']
    # No new rules means no timestamp churn and no fabricated knowledge.
    if existing and rules == old_rules:
        record = existing
    elif not rules and not legacy:
        human_count = sum(c['classification'] == 'HUMAN' for c in comments)
        print(f'No reusable rules extracted from {human_count} confirmed HUMAN comment(s); '
              'no knowledge generated or overwritten. See extraction_report.json for omissions.')
        return
    else:
        md = render(repo, rules, legacy_md=legacy)
        stats = {k:v for k,v in reviews.items() if k != 'comments'}
        stats['human_comment_count'] = sum(c['classification']=='HUMAN' for c in comments)
        record = make_record(repo, md, rules, existing, stats, legacy_md=legacy)
    write_text(directory/'review_knowledge.md',record['knowledge_md'])
    write_json(directory/'pending.json',{'base':existing,'record':record})
    write_json(directory/'record.json',record)
    print(f'Rules: {len(old_rules)} existing -> {len(rules)} merged. Generated {directory}/review_knowledge.md')


def storage_command(args, config):
    if args.provider and args.providers:
        raise ValueError('Choose --provider or --providers, not both')
    if not args.provider and not args.providers:
        raise ValueError('Select --provider aws or --provider gcp')
    providers = [args.provider] if args.provider else args.providers.split(',')
    providers = list(dict.fromkeys(p.strip().lower() for p in providers))
    if not providers or any(p not in ('aws','gcp') for p in providers):
        raise ValueError('providers must be aws,gcp')
    if args.action == 'sync' and len(providers) < 2:
        raise ValueError('sync requires explicit --providers aws,gcp')
    interactive = getattr(args, 'interactive', False)
    started = perf_counter()
    banner('MultiCloud Python SDK — Knowledge Demo', 'One source code • AWS S3 or Google Cloud Storage')
    event('Demo', 'PROCESS START', 'Human Review Learning | MultiCloud Python SDK', fields=(
        f'Selected provider: {",".join(providers)}',
        f'Action         : {args.action}',
        f'Repository     : {args.repo}',
        'Workflow       : One source code; provider selected at runtime'))
    if args.action in ('save', 'sync'):
        if args.file:
            event('Demo', 'INPUT', 'Knowledge Markdown selected', fields=(
                f'Input Markdown: {Path(args.file).resolve()}',))
        elif args.record:
            event('Demo', 'INPUT', 'Exact knowledge revision selected', fields=(
                f'Pending record : {Path(args.record).resolve()}',))
        else:
            event('Demo', 'INPUT', 'Using the existing cloud knowledge record')
        event('Demo', 'UPLOAD PLAN', 'Upload one knowledge file, download it, then verify its content.', fields=(
            f'Files planned  : 1 | Destinations: {len(providers)}',
            'Storage format : One JSON blob per destination; Markdown in knowledge_md'))
        step(1, 'Check cloud access and read the existing baseline', interactive=interactive)
    else:
        step(1, 'Read knowledge from the selected cloud', interactive=interactive, total=1)
    stores = {}
    try:
        # Read before any write. An unavailable cloud is an error, not absence.
        records = {}; failures = {}
        for p in providers:
            try:
                stores[p] = connect(p,config)
                event('Demo', 'CONFIGURATION', '📋 Configuration', fields=(
                    f'Provider       : {p}',
                    f'Bucket         : {stores[p].client.bucket}'))
                records[p] = stores[p].load(args.repo)
            except Exception as exc:
                failures[p] = f'FAILED during preflight: {exc}'
        if failures:
            for provider, failure in failures.items():
                event('Demo', 'PREFLIGHT FAILED', f'{provider}: {failure}', level='ERROR')
            raise RuntimeError('Cloud preflight failed; no writes performed. Check credentials, provider registration, bucket configuration and access.')
        if args.action == 'get':
            value = records[providers[0]] if len(providers)==1 else choose_existing(records)
            if args.output: write_json(args.output,value)
            else: print(json.dumps(value,indent=2))
            print(f'[PROCESS COMPLETE] Read finished; knowledge_files_found={int(value is not None)}', flush=True)
            return
        if args.action == 'verify':
            value = choose_existing(records)
            if value is None or any(r is None for r in records.values()):
                raise ValueError('Verification failed: record missing')
            if args.record:
                expected = read_json(args.record)
                if not expected or expected.get('record') != value:
                    raise ValueError('Verification failed: stored knowledge differs from expected record')
                print(f'{" / ".join(p.upper() for p in providers)} knowledge: VERIFIED matches expected record')
            elif len(providers) == 1:
                print(f'{providers[0].upper()} knowledge: VERIFIED readable; save performs full read-back verification')
            else:
                print('AWS / GCP knowledge: VERIFIED equivalent')
            print(f'[PROCESS COMPLETE] Verification successful; destinations_verified={len(providers)}/{len(providers)}', flush=True)
            return
        step(2, 'Prepare knowledge and preserve the retryable revision', interactive=interactive)
        if args.action == 'sync':
            value = choose_existing(records)
            if value is None: raise ValueError('No existing cloud knowledge to sync')
            target = value; base = value
        elif args.record:
            pending = read_json(args.record)
            target, base = pending['record'], pending['base']
        else:
            if not args.file: raise ValueError('save requires --record or --file')
            base = choose_existing(records)
            md = Path(args.file).read_text()
            if base and base['knowledge_md'] not in md:
                raise ValueError('Manual Markdown save must preserve existing knowledge verbatim; use the skill merge workflow for semantic changes')
            target = make_record(args.repo,md,base.get('rules',[]) if base else [],base,{},legacy_md=md)
            # Persist the retryable exact revision before any external writes.
            write_json(Path(args.file).parent/'pending.json',{'base':base,'record':target})
        if target['repo_id'] != args.repo:
            raise ValueError('Record repository mismatch')
        for p,r in records.items():
            if r is not None and r != base and r != target:
                raise ValueError(f'{p} knowledge changed since merge; inspect conflict before writing')
        event('Demo', 'PREPARED', 'Knowledge is ready for upload.', fields=(
            f'Markdown       : {size(len(target["knowledge_md"].encode("utf-8")))}',
            f'Revision       : {target["knowledge_version"]}',
            f'Structured rules: {len(target.get("rules", []))} (separate from rules written in Markdown)'))
        status = save_selected(stores,target,interactive=interactive)
        for provider, result in status.items():
            if result != 'VERIFIED':
                event('Demo', 'DESTINATION FAILED', f'{provider}: {result}', level='ERROR')
        if any(v != 'VERIFIED' for v in status.values()):
            failed = ','.join(p for p, result in status.items() if result != 'VERIFIED')
            raise RuntimeError(f'Write or read-back failed for {failed}; local files preserved. '
                               'Retry the selected provider with the same --record pending.json')
        event('Demo', 'PROCESS COMPLETE', 'Demo completed successfully.', fields=(
            f'Knowledge files: 1 | Destinations: {len(stores)}',
            f'Files uploaded : {len(stores)}/{len(stores)}',
            f'Files read back: {len(stores)}/{len(stores)}',
            f'Files verified : {len(stores)}/{len(stores)}',
            f'Elapsed        : {perf_counter() - started:.3f} s'))
        banner('DEMO COMPLETED SUCCESSFULLY',
               f'Uploaded: {len(stores)}   Downloaded: {len(stores)}   Verified: {len(stores)}')
    finally:
        for store in stores.values(): store.close()


def main(kind):
    demo = kind == 'demo'
    if demo:
        kind = 'storage'
    parser = argparse.ArgumentParser(
        description='Human Review Learning: upload, read back and verify through the MultiCloud Python SDK'
        if demo else 'Human Review Learning',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    if kind == 'storage':
        parser.add_argument('action', choices=['save','get','verify','sync'],
                            **({'nargs': '?', 'default': 'save'} if demo else {}))
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument('--provider',type=str.lower,choices=['aws','gcp'],
                               help='Run the shared application on this cloud only')
        selection.add_argument('--providers',help='Explicit optional multi-cloud mode, e.g. aws,gcp')
        parser.add_argument('--record')
        parser.add_argument('--file')
        parser.add_argument('--output')
        pacing = parser.add_mutually_exclusive_group()
        pacing.add_argument('--yes', dest='unattended', action='store_true', default=False,
                            help='Run all steps without confirmation prompts')
        pacing.add_argument('--interactive', dest='interactive', action='store_true',
                            help='Ask before each step (default for ./demo)')
        parser.set_defaults(interactive=demo)
    elif kind == 'workflow':
        parser.add_argument('action',choices=['classify','pending','confirm','build'])
        parser.add_argument('--ids', nargs='+', help='Exact comment IDs covered by the developer answer')
        parser.add_argument('--label', choices=['HUMAN','AI','UNCERTAIN'], help='Developer answer; UNCERTAIN means explicit Skip')
        parser.add_argument('--non-interactive',action='store_true')
        parser.add_argument('--output-dir')
    else:
        parser.add_argument('--days',type=int)
        parser.add_argument('--conversations',action='store_true')
        parser.add_argument('--output-dir')
    parser.add_argument('--repo', required=not demo,
                        default='demo/human-review-learning' if demo else None,
                        help='owner/name or https://github.com/owner/name')
    parser.add_argument('--config', default=str(PROJECT_ROOT / 'config.toml') if demo else 'config.toml')
    if demo:
        parser.epilog = 'Without an action, upload the bundled synthetic Markdown, then download and verify it. Use --file for your own Markdown.'
    args = parser.parse_args()
    if kind == 'storage' and args.unattended:
        args.interactive = False
    if demo and args.action == 'save' and not args.file and not args.record:
        args.file = str(PROJECT_ROOT / 'examples/review_knowledge.demo.md')
    try:
        args.repo = validate_repo(args.repo)
        config = tomllib.loads(Path(args.config).read_text()) if Path(args.config).exists() else {}
        if kind == 'storage':
            storage_command(args,config)
        else:
            directory = output_dir(args.repo,args.output_dir)
            if kind == 'fetch':
                gh = Gh(); gh.authenticate()
                result = collect(args.repo,args.days if args.days is not None else config.get('github',{}).get('default_days',30),api=gh,conversations=args.conversations)
                write_json(directory/'reviews.json',result)
                print(f'Scanned {result["scanned_pr_count"]} PRs; fetched {len(result["comments"])} comments '
                      f'across {result["pr_count"]} PRs with feedback -> {directory}/reviews.json')
            elif args.action == 'classify':
                classify_file(directory,config,not args.non_interactive)
            elif args.action == 'pending':
                pending = pending_confirmations(args.repo, directory)
                write_json(directory/'pending_confirmations.json', pending)
                print(json.dumps(pending, indent=2, ensure_ascii=False))
            elif args.action == 'confirm':
                confirm_file(args.repo, directory, args.ids, args.label)
            else:
                build(args.repo,directory)
    except DemoStopped as exc:
        event('Demo', 'PROCESS STOPPED', str(exc), fields=('Local files are preserved; no further steps will run.',))
        return 130
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        if kind == 'storage':
            event('Demo', 'PROCESS FAILED', 'Storage demo did not complete. Local files are preserved.', level='ERROR')
        print(f'HRL: {exc}',file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrupted; saved manual decisions retained.',file=sys.stderr)
        return 130
    return 0
