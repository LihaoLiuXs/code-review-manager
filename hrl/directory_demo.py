"""Share and restore a review knowledge bundle with SDK-native directory APIs."""
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from urllib.parse import quote
from uuid import uuid4
import shutil

from hrl.console import DemoStopped, banner, event, size, step
from hrl.multicloud_store import MAX_BYTES, client_options


def connect(provider, config):
    from multicloud.blob.blob_client import AsyncBucketClient
    return AsyncBucketClient(**client_options(provider, config))


def inventory(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Bundle must be a directory, not a symlink')
    files = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Bundle symlink is not allowed: {path.name}')
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = path
    if not files:
        raise ValueError('Review bundle is empty')
    if sum(p.stat().st_size for p in files.values()) > MAX_BYTES:
        raise ValueError('Review bundle exceeds the demo limit of 10 MiB')
    return files


def check_transfer(response, count, byte_count, operation):
    success = getattr(response, f'successful_{operation}s')
    event('BlobStore', 'DIRECTORY RESULT', f'Directory {operation} result from multicloud-py', fields=(
        f'Files attempted: {response.total_files}', f'Files succeeded: {success}',
        f'Failed transfers: {len(response.failed_transfers)}',
        f'Bytes transferred: {size(response.total_bytes_transferred)}'))
    for failure in response.failed_transfers:
        path = failure.source if operation == 'upload' else failure.destination
        event('BlobStore', 'TRANSFER FAILED', f'{path}: {failure.exception}', level='ERROR')
    if (response.failed_transfers or response.total_files != count or success != count
            or response.total_bytes_transferred != byte_count):
        raise ValueError(f'Directory {operation} incomplete: expected {count} files and {byte_count} bytes')


async def run(args, config):
    if not args.provider or args.providers:
        raise ValueError('Directory demo requires one explicit --provider aws or --provider gcp')
    started = perf_counter()
    total = 5 if args.cleanup else 4
    banner('MultiCloud Python SDK — Review Bundle Directory Demo',
           'Share review knowledge with another reviewer or CI job')
    event('Demo', 'PROCESS START', 'Code Review Manager | native directory operations', fields=(
        f'Provider       : {args.provider}', f'Repository     : {args.repo}',
        f'Input directory: {Path(args.directory).absolute()}',
        'SDK            : multicloud-py AsyncBucketClient'))
    def advance(number, title, section, detail='This step did not start.'):
        step(number,title,interactive=args.interactive,total=total,section=section,stop_detail=detail,label='DIRECTORY STEP')
    advance(1,'Prepare a portable review knowledge bundle','PREPARE REVIEW BUNDLE')
    source = Path(args.directory).absolute()
    inventory(source)
    run_id = uuid4().hex
    work = Path('output') / args.repo.replace('/','--') / f'directory-{run_id}'
    snapshot = work / 'source'
    restored = work / 'downloaded'
    # A unique local snapshot prevents stale downloads or later input edits from
    # masking a failed transfer; no existing files are removed or overwritten.
    shutil.copytree(source,snapshot)
    expected = {name:sha256(path.read_bytes()).hexdigest() for name,path in inventory(snapshot).items()}
    byte_count = sum(path.stat().st_size for path in inventory(snapshot).values())
    count = len(expected)
    prefix = f'review_bundles/{quote(args.repo,safe="")}/{run_id}/'
    event('Demo', 'BUNDLE READY', 'Review guidance, structured rules and source context stay together.', fields=(
        f'Files planned  : {count}', f'Total content  : {size(byte_count)}',
        f'Cloud prefix   : {prefix}', f'Download folder: {restored.absolute()}',
        *(f'File           : {name}' for name in expected)))
    advance(2,'Upload the entire review bundle through multicloud-py','UPLOAD REVIEW DIRECTORY')
    client = None
    try:
        client = connect(args.provider,config)
        event('Demo','CONFIGURATION','📋 Directory destination',fields=(
            f'Provider       : {args.provider}',f'Bucket         : {client.bucket}',f'Prefix         : {prefix}'))
        event('BlobStore','WRITE','Uploading folder through AsyncBucketClient.upload_directory()')
        transfer_started = perf_counter()
        result = await client.upload_directory(str(snapshot),prefix=prefix,
            include_sub_folders=True,follow_symbolic_links=False)
        check_transfer(result,count,byte_count,'upload')
        event('BlobStore','WRITE OK','Review directory uploaded successfully.',fields=(
            f'Files uploaded : {count}/{count}',f'Elapsed        : {perf_counter()-transfer_started:.3f} s'))
        advance(3,'Download the review bundle into a fresh local directory','DOWNLOAD REVIEW DIRECTORY',
                'The upload remains in the bucket and is not verified.')
        restored.mkdir(parents=True,exist_ok=False)
        event('BlobStore','READ','Downloading folder through AsyncBucketClient.download_directory()')
        transfer_started = perf_counter()
        result = await client.download_directory(prefix,str(restored))
        check_transfer(result,count,byte_count,'download')
        event('BlobStore','READ OK','Review directory downloaded successfully.',fields=(
            f'Files read back: {count}/{count}',f'Elapsed        : {perf_counter()-transfer_started:.3f} s'))
        advance(4,'Verify every restored review file and its folder structure','VERIFY REVIEW BUNDLE',
                'The uploaded and downloaded files are preserved but are not verified.')
        actual = inventory(restored)
        if set(actual) != set(expected):
            raise ValueError(f'Downloaded bundle file set differs: missing={sorted(set(expected)-set(actual))}, extra={sorted(set(actual)-set(expected))}')
        for name,path in actual.items():
            if sha256(path.read_bytes()).hexdigest() != expected[name]:
                raise ValueError(f'Downloaded review file content mismatch: {name}')
            event('BlobStore','VERIFIED',f'{name} — content and relative path match',fields=(
                f'SHA-256        : {expected[name]}',))
        if args.cleanup:
            advance(5,'Delete only this demo run from the cloud bucket','CLEAN UP DEMO DIRECTORY',
                    'Cleanup did not start. The verified review bundle remains in the bucket.')
            # This prefix is generated here, includes a fresh UUID and ends in /
            # so cleanup cannot target another run, the knowledge record or a bucket.
            event('BlobStore','DELETE','Removing this run through AsyncBucketClient.delete_directory()',fields=(f'Prefix         : {prefix}',))
            await client.delete_directory(prefix)
            remaining = await client.list_page(prefix=prefix,max_results=1)
            if remaining.blobs:
                raise ValueError('Directory cleanup verification failed: objects remain')
            event('BlobStore','VERIFIED','Demo prefix removed; no current objects remain. Local files retained.')
        event('Demo','PROCESS COMPLETE','Directory transfer and content verification passed.',fields=(
            f'Files uploaded : {count}/{count}',f'Files read back: {count}/{count}',
            f'Files verified : {count}/{count}',f'Elapsed        : {perf_counter()-started:.3f} s'))
        banner('DIRECTORY DEMO COMPLETED SUCCESSFULLY',
               f'Uploaded: {count}   Downloaded: {count}   Verified: {count}')
    except DemoStopped:
        raise
    except Exception as exc:
        raise RuntimeError(f'Directory demo failed: {exc}. Local files retained at {work}') from exc
    finally:
        if client is not None:
            await client.close()
