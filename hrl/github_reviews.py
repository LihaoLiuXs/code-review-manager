"""GitHub REST collection through gh. A failed page aborts the collection."""
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit


def validate_repo(repo: str) -> str:
    """Normalize a GitHub repository homepage URL or owner/name shorthand."""
    repo = repo.strip()
    if '://' in repo:
        parsed = urlsplit(repo)
        if (parsed.scheme != 'https' or parsed.hostname != 'github.com'
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in (None, 443)):
            raise ValueError('Use owner/name or an HTTPS github.com repository URL')
        repo = parsed.path.strip('/')
    repo = repo.removesuffix('.git')
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)
            or any(part in ('.', '..') for part in repo.split('/'))):
        raise ValueError('Use owner/name or https://github.com/owner/name (repository homepage)')
    return repo


class Gh:
    def run(self, args):
        try:
            result = subprocess.run(['gh', *args], capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise RuntimeError('Install GitHub CLI, then run gh auth login --hostname github.com') from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f'GitHub request failed (auth/access/rate limit); collection incomplete: {exc.stderr.strip()}') from exc
        return result.stdout

    def authenticate(self):
        self.run(['auth', 'status', '--hostname', 'github.com'])

    def pages(self, endpoint: str) -> list[dict]:
        result = []
        page = 1
        while True:
            separator = '&' if '?' in endpoint else '?'
            data = json.loads(self.run(['api', '--hostname', 'github.com', f'{endpoint}{separator}per_page=100&page={page}']))
            if not isinstance(data, list):
                raise RuntimeError('Expected a GitHub list response; collection incomplete')
            result.extend(data)
            if len(data) < 100:
                return result
            page += 1


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def collect(repo: str, days: int = 30, *, api=None, now: datetime | None = None, conversations: bool = False) -> dict:
    repo = validate_repo(repo)
    if days <= 0:
        raise ValueError('days must be positive')
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    api = api or Gh()
    # Enumerate ALL PRs rather than assuming reviews always advance updated_at.
    # The MVP favors complete collection over an API-call optimization.
    pulls = api.pages(f'repos/{repo}/pulls?state=all&sort=updated&direction=desc')
    comments = {}
    for pr in pulls:
        n = pr['number']
        reviews = api.pages(f'repos/{repo}/pulls/{n}/reviews')
        inline = api.pages(f'repos/{repo}/pulls/{n}/comments')
        related = {str(r['id']): r.get('body', '') for r in reviews}
        groups = [('inline_review', inline), ('review_submission', reviews)]
        if conversations:
            groups.append(('conversation_candidate', api.pages(f'repos/{repo}/issues/{n}/comments')))
        for kind, items in groups:
            for c in items:
                created = c.get('submitted_at') if kind == 'review_submission' else c.get('created_at')
                if not created or not c.get('body', '').strip() or not start <= timestamp(created) <= now:
                    continue
                cid = f'{kind}:{c["id"]}'
                rid = str(c.get('pull_request_review_id') or (c['id'] if kind == 'review_submission' else ''))
                comments[cid] = dict(comment_id=cid, repo_id=repo, pr_number=n,
                    pr_url=f'https://github.com/{repo}/pull/{n}', pr_title=pr.get('title', ''),
                    comment_url=c.get('html_url', ''), author_login=(c.get('user') or {}).get('login', ''),
                    created_at=created, file_path=c.get('path'), line=c.get('line') or c.get('original_line'),
                    comment_type=kind, body=c['body'], diff_context=c.get('diff_hunk', ''),
                    review_id=rid, related_review_body=related.get(rid, ''))
    return dict(repo_id=repo, period_start=start.isoformat(), period_end=now.isoformat(),
                scanned_pr_count=len(pulls),
                pr_count=len({c['pr_number'] for c in comments.values()}),
                comments=list(comments.values()), complete=True)
