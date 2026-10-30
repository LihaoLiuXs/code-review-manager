"""Provider-neutral JSON knowledge blobs through MultiCloud BucketClient."""
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import quote
import json
import os
import warnings
from time import perf_counter
from hashlib import sha256

from hrl.console import DemoStopped, event, size, step

from multicloud.common.exceptions import ResourceNotFoundException

# An application memory/size guard, independent of cloud document-store limits.
MAX_BYTES = 10 * 1024 * 1024


def object_key(repo_id: str, prefix: str = 'review_knowledge') -> str:
    """Encode the complete repository ID as one unambiguous object name."""
    name = quote(repo_id, safe='') + '.json'
    return f'{prefix.strip("/")}/{name}' if prefix.strip('/') else name


class Store:
    def __init__(self, client, *, prefix: str = 'review_knowledge'):
        self.client = client
        self.prefix = prefix
        provider = client.provider
        self.label = {'aws': 'AWS S3', 'gcp': 'GCP GCS'}.get(provider, 'BlobStore')
        self.scheme = {'aws': 's3', 'gcp': 'gs'}.get(provider, 'blob')

    def log(self, action, key, message, *, fields=()):
        location = (f'Target         : {self.scheme}://{self.client.bucket}/{key}',) if action in ('READ', 'WRITE') else ()
        event('BlobStore', action, f'[{self.label}] {message}',
              fields=(*location, *fields), level='ERROR' if 'FAILED' in action else 'INFO')

    def load(self, repo_id: str) -> dict | None:
        key = object_key(repo_id, self.prefix)
        started = perf_counter()
        self.log('READ', key, 'Downloading knowledge through BucketClient.download()')
        try:
            try:
                response = self.client.download(key=key)
            except ResourceNotFoundException:
                # The same SDK exception may mean missing bucket or object.
                # Bucket auth/config errors must block writes, not look empty.
                if not self.client.does_bucket_exist():
                    raise ValueError('Knowledge bucket does not exist; create/configure it first')
                self.log('READ MISSING', key, 'Bucket exists; no knowledge object yet. Ready for the first upload.',
                         fields=(f'Elapsed        : {perf_counter() - started:.3f} s',))
                return None
            payload = response.content
            if len(payload) > MAX_BYTES:
                raise ValueError('Knowledge blob too large (application limit: 10 MiB)')
            record = json.loads(payload.decode('utf-8'))
            if (not isinstance(record, dict) or record.get('repo_id') != repo_id
                    or not isinstance(record.get('knowledge_md'), str)
                    or type(record.get('knowledge_version')) is not int
                    or record['knowledge_version'] < 1):
                raise ValueError('Invalid knowledge JSON or repository mismatch')
            self.log('READ OK', key, 'Downloaded knowledge successfully.', fields=(
                f'Payload        : {size(len(payload))}',
                f'Markdown       : {size(len(record["knowledge_md"].encode("utf-8")))}',
                f'Revision       : {record["knowledge_version"]}',
                f'Elapsed        : {perf_counter() - started:.3f} s'))
            return record
        except Exception as exc:
            self.log('READ FAILED', key, str(exc), fields=(f'Elapsed        : {perf_counter() - started:.3f} s',))
            raise

    def save(self, record: dict, *, interactive=False) -> None:
        key = object_key(record['repo_id'], self.prefix)
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')
        if len(payload) > MAX_BYTES:
            self.log('WRITE FAILED', key, 'Knowledge too large (application limit: 10 MiB)')
            raise ValueError('Knowledge blob too large; compact it before saving')
        markdown = record['knowledge_md'].encode('utf-8')
        started = perf_counter()
        self.log('WRITE', key, 'Uploading knowledge through BucketClient.upload()', fields=(
            'Format         : JSON containing Markdown in knowledge_md',
            f'Payload        : {size(len(payload))}',
            f'Markdown       : {size(len(markdown))}',
            f'Revision       : {record["knowledge_version"]}'))
        try:
            self.client.upload(key=key, payload=payload, content_type='application/json')
        except Exception as exc:
            self.log('WRITE FAILED', key, str(exc), fields=(
                'Uploads confirmed: 0/1; read-back has not started',
                f'Elapsed        : {perf_counter() - started:.3f} s'))
            raise
        self.log('WRITE OK', key, 'Uploaded knowledge successfully.', fields=(
            'Files uploaded : 1/1',
            f'Elapsed        : {perf_counter() - started:.3f} s'))
        step(4, 'Read back and verify the uploaded knowledge', interactive=interactive)
        self.log('READ-BACK START', key, 'Starting a separate BlobStore download after upload success.')
        read_started = perf_counter()
        try:
            downloaded = self.load(record['repo_id'])
        except Exception as exc:
            self.log('READ-BACK FAILED', key, str(exc), fields=(
                'Files uploaded : 1/1', 'Files read back: 0/1', 'Files verified : 0/1'))
            raise
        if downloaded != record:
            read_count = 1 if downloaded is not None else 0
            self.log('VERIFY FAILED', key, 'Downloaded content differs from the written record.', fields=(
                'Files uploaded : 1/1', f'Files read back: {read_count}/1', 'Files verified : 0/1'))
            raise ValueError('Cloud read-back mismatch after write')
        self.log('VERIFIED', key, 'Markdown and full JSON content match the source.', fields=(
            'Files uploaded : 1/1', 'Files read back: 1/1', 'Files verified : 1/1',
            f'Markdown SHA-256: {sha256(markdown).hexdigest()}',
            f'Elapsed        : {perf_counter() - read_started:.3f} s'))

    def close(self):
        self.client.close()


def client_options(provider: str, config: dict) -> dict:
    """Shared provider configuration for synchronous and asynchronous SDK clients."""
    if provider not in ('aws', 'gcp'):
        raise ValueError('Provider must be aws or gcp')
    storage = config.get('storage', {})
    options = storage.get(provider, {})
    bucket = os.getenv(f'HRL_{provider.upper()}_BUCKET') or options.get('bucket')
    if not bucket or bucket.startswith('YOUR_'):
        raise ValueError(f'Set HRL_{provider.upper()}_BUCKET or storage.{provider}.bucket')
    kwargs = dict(provider=provider, bucket=bucket)
    region_variable = {'aws': 'AWS_REGION', 'gcp': 'GOOGLE_CLOUD_REGION'}[provider]
    region = os.getenv(region_variable) or options.get('region')
    if region:
        kwargs['region'] = region
    return kwargs


def connect(provider: str, config: dict) -> Store:
    from multicloud.blob.blob_client import BucketClient
    return Store(BucketClient(**client_options(provider, config)),
                 prefix=config.get('storage', {}).get('prefix', 'review_knowledge'))


def choose_existing(records: dict[str, dict | None]) -> dict | None:
    present = [r for r in records.values() if r is not None]
    if present and len(present) != len(records):
        warnings.warn('One cloud is missing knowledge; use storage sync to repair after inspection')
    if any(r != present[0] for r in present[1:]):
        raise ValueError('Cloud knowledge conflict: inspect both records and explicitly select a version')
    return deepcopy(present[0]) if present else None


def make_record(repo: str, markdown: str, rules: list[dict], existing: dict | None, stats: dict, *, legacy_md: str = '') -> dict:
    if existing and existing['repo_id'] != repo:
        raise ValueError('Repository mismatch')
    if existing and existing['knowledge_md'] == markdown and existing.get('rules', []) == rules:
        return deepcopy(existing)
    return dict(repo_id=repo, repo_url=f'https://github.com/{repo}',
                knowledge_version=(existing['knowledge_version'] if existing else 0)+1,
                updated_at=datetime.now(timezone.utc).isoformat(), knowledge_md=markdown,
                rules=rules, legacy_md=legacy_md, **{k:stats[k] for k in ('period_start','period_end','pr_count','human_comment_count') if k in stats})


def save_selected(stores: dict[str, Store], record: dict, *, interactive=False) -> dict[str, str]:
    results = {}
    for index, (provider, store) in enumerate(stores.items(), 1):
        step(3, f'Upload knowledge | destination {index}/{len(stores)} | provider={provider}', interactive=interactive)
        try:
            if interactive:
                store.save(record, interactive=True)
            else:
                store.save(record)
            results[provider] = 'VERIFIED'
        except DemoStopped:
            raise
        except Exception as exc:
            results[provider] = f'FAILED: {exc}'
    return results
