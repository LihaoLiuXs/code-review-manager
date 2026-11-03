"""Console-friendly cloud and local paths for directory demo presentations."""
from pathlib import Path
from urllib.parse import quote, urlencode

from hrl.console import event


def directory_console_url(provider, bucket, prefix):
    if provider == 'aws':
        query = urlencode({'prefix': prefix, 'showversions': 'false'})
        return f'https://s3.console.aws.amazon.com/s3/buckets/{quote(bucket,safe="")}?{query}'
    if provider == 'gcp':
        return f'https://console.cloud.google.com/storage/browser/{quote(bucket,safe="")}/{quote(prefix,safe="/")}'
    raise ValueError('Console links support aws or gcp')


def cloud_uri(provider, bucket, key):
    scheme = {'aws': 's3', 'gcp': 'gs'}[provider]
    return f'{scheme}://{bucket}/{key}'


def log_directory_location(provider, bucket, prefix, local_root, *, direction):
    label = 'upload destination' if direction == 'upload' else 'download source'
    event('BlobStore','DIRECTORY LOCATION',f'Cloud directory {label} — open this location in the console.',fields=(
        f'Bucket         : {bucket}',
        f'Cloud directory: {cloud_uri(provider,bucket,prefix)}',
        f'Prefix (search): {prefix}',
        f'Local directory: {Path(local_root).absolute()}',
        f'Console URL    : {directory_console_url(provider,bucket,prefix)}'))


def log_directory_files(provider, bucket, prefix, names, local_root, *, direction):
    """Call only after full upload success or full download content verification."""
    action = 'UPLOADED FILE' if direction == 'upload' else 'DOWNLOADED FILE'
    root = Path(local_root).absolute()
    for name in sorted(names):
        key = prefix + name
        detail = name if direction == 'upload' else f'{name} — content verified'
        event('BlobStore',action,detail,fields=(
            f'Object key     : {key}',
            f'Cloud file     : {cloud_uri(provider,bucket,key)}',
            f'Local file     : {root/name}'))
