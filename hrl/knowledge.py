"""Validate agent-produced semantic merge plans; preserve older rules and evidence."""
from copy import deepcopy
from datetime import datetime, timezone


def merge(existing: list[dict], observations: list[dict], comments: list[dict]) -> list[dict]:
    rules = deepcopy(existing)
    by_id = {r['id']:r for r in rules}
    human = {c['comment_id']:c for c in comments if c.get('classification') == 'HUMAN'}
    for o in observations:
        if o.get('conflict'):
            raise ValueError(f'Conflict requires developer resolution: {o["conflict"]}')
        ids = o.get('source_ids', [])
        if not ids or any(i not in human for i in ids):
            raise ValueError('Every observation requires confirmed human evidence')
        for field in ('title','rule','why','checks','tags'):
            if not o.get(field):
                raise ValueError(f'Missing observation field: {field}')
        sources = [dict(comment_id=i,url=human[i]['comment_url'],pr_number=human[i]['pr_number']) for i in ids]
        if any(not s['url'].startswith('https://github.com/') for s in sources):
            raise ValueError('Evidence needs a GitHub source URL')
        target = o.get('merge_into')
        if target and target not in by_id:
            raise ValueError(f'Unknown merge target {target}')
        # Exact repeats are handled deterministically. Semantic equivalence is
        # decided by the agent via merge_into, without an extra LLM service.
        rule = by_id.get(target) if target else next((r for r in rules if r['rule']==o['rule'] and r['title']==o['title']), None)
        if rule is None:
            number = max([int(r['id'].split('-')[1]) for r in rules] or [0]) + 1
            rule = dict(id=f'HRL-{number:03}', title=o['title'], rule=o['rule'], why=o['why'],
                        tags=[], checks=[], sources=[], reinforcements=[])
            rules.append(rule); by_id[rule['id']] = rule
        elif o['rule'] != rule['rule']:
            # Preserve the older statement instead of silently replacing it.
            rule.setdefault('reinforcements', [])
            if o['rule'] not in rule['reinforcements']:
                rule['reinforcements'].append(o['rule'])
        for field, values in (('tags',o['tags']),('checks',o['checks']),('sources',sources)):
            for value in values:
                if value not in rule[field]: rule[field].append(value)
    return rules


def render(repo: str, rules: list[dict], date: str | None = None, legacy_md: str = '') -> str:
    date = date or datetime.now(timezone.utc).date().isoformat()
    tags = sorted({tag for r in rules for tag in r['tags']})
    lines = ['# Human Review Knowledge', '', f'Repository: {repo}', f'Last Updated: {date}', '',
             '## Overview', '', 'Review guidance supported by confirmed human feedback; apply each rule within its documented context.', '',
             '## Review Tags', '', *[f'- {t}' for t in tags], '', '## Learned Review Rules', '']
    for r in rules:
        lines.extend([f'### {r["id"]}: {r["title"]}', '', 'Tags:', *[f'- {t}' for t in r['tags']], '',
                      'Rule:', r['rule'], '', 'Why:', r['why'], '', 'What AI Reviewers Should Check:',
                      *[f'- {c}' for c in r['checks']], '', 'Sources:',
                      *[f'- [PR #{s["pr_number"]}]({s["url"]})' for s in r['sources']], ''])
        if r.get('reinforcements'):
            lines.extend(['Additional supported guidance:', *[f'- {s}' for s in r['reinforcements']], ''])
    if legacy_md:
        lines.extend(['## Preserved Existing Knowledge', '', legacy_md])
    return '\n'.join(lines).rstrip() + '\n'
