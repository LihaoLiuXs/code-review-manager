"""Independent single-file and directory transfers through multicloud-py."""
from hashlib import sha256
from pathlib import Path, PurePosixPath
from time import perf_counter
from urllib.parse import quote
from uuid import uuid4
import shutil

from hrl.console import banner, event, size, step
from hrl.directory_demo import connect as connect_directory, inventory, check_transfer
from hrl.io import read_json, write_json
from hrl.multicloud_store import MAX_BYTES, client_options


def connect_file(provider, config):
    from multicloud.blob.blob_client import BucketClient
    return BucketClient(**client_options(provider, config))


def describe(files):
    return {name: {'bytes': path.stat().st_size, 'sha256': sha256(path.read_bytes()).hexdigest()}
            for name,path in files.items()}


def verify_download(directory, expected):
    actual = inventory(directory)
    if set(actual) != set(expected):
        raise ValueError('Downloaded file set differs from the upload manifest')
    for name,path in actual.items():
        value = expected[name]
        content = path.read_bytes()
        if len(content) != value['bytes'] or sha256(content).hexdigest() != value['sha256']:
            raise ValueError(f'Download content mismatch: {name}')
        event('BlobStore','VERIFIED',f'{name} — content and relative path match',fields=(
            f'SHA-256        : {value["sha256"]}',))


async def run(args, config):
    if not args.provider or args.providers:
        raise ValueError('Select one --provider aws or --provider gcp')
    if args.cleanup:
        raise ValueError('Separate transfer operations do not perform cleanup')
    is_directory = args.action.endswith('-directory')
    uploading = args.action.startswith('upload')
    kind = 'directory' if is_directory else 'single'
    title = ('DIRECTORY ' if is_directory else 'SINGLE FILE ') + ('UPLOAD' if uploading else 'DOWNLOAD')
    banner('Code Review Manager — multicloud-py Demo',title)
    event('Demo','PROCESS START',f'One operation: {title}',fields=(
        f'Provider       : {args.provider}',f'Repository     : {args.repo}'))
    step(1,f'{title} through multicloud-py',interactive=args.interactive,total=1,
         section=title,stop_detail='This operation did not start.')
    started = perf_counter()
    root = Path('output') / args.repo.replace('/','--') / 'demo' / args.provider
    latest = root / f'{kind}-latest.json'
    run_id = uuid4().hex
    work = root / run_id
    restored = work / 'downloaded'
    if uploading:
        if args.state:
            raise ValueError('--state selects an existing upload for a download command')
        if is_directory:
            source = Path(args.directory).absolute()
            inventory(source)
            snapshot = work / 'source'
            shutil.copytree(source,snapshot)
            files = inventory(snapshot)
        else:
            if not args.file:
                raise ValueError('upload requires --file')
            source = Path(args.file).absolute()
            if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_BYTES:
                raise ValueError('Select a regular Markdown file of at most 10 MiB')
            payload = source.read_bytes()
            if len(payload) > MAX_BYTES:
                raise ValueError('File exceeds the 10 MiB demo guard')
            snapshot = work / 'source'
            snapshot.mkdir(parents=True)
            (snapshot/source.name).write_bytes(payload)
            files = {source.name:snapshot/source.name}
        expected = describe(files)
        prefix = f'demo_artifacts/{quote(args.repo,safe="")}/{run_id}/'
        state = dict(kind=kind,provider=args.provider,repo=args.repo,files=expected)
        state['prefix' if is_directory else 'key'] = prefix if is_directory else prefix+source.name
        event('Demo','INPUT',str(source),fields=tuple(f'File           : {name}' for name in expected))
    else:
        state_path = Path(args.state) if args.state else latest
        state = read_json(state_path)
        if not state:
            command = 'upload-directory' if is_directory else 'upload'
            raise ValueError(f'No upload manifest; run ./demo {command} --provider {args.provider} first, or pass --state')
        if state.get('kind') != kind or state.get('provider') != args.provider or state.get('repo') != args.repo:
            raise ValueError('Upload manifest does not match the operation, provider and repository')
        expected = state.get('files')
        if not isinstance(expected,dict) or not expected:
            raise ValueError('Upload manifest has no files')
        for name, metadata in expected.items():
            relative = PurePosixPath(name)
            if (relative.is_absolute() or '..' in relative.parts or not relative.parts
                    or '\\' in name or not isinstance(metadata,dict)
                    or type(metadata.get('bytes')) is not int or metadata['bytes'] < 0
                    or not isinstance(metadata.get('sha256'),str)):
                raise ValueError('Invalid upload manifest file metadata')
        if not is_directory and (len(expected)!=1 or len(PurePosixPath(next(iter(expected))).parts)!=1):
            raise ValueError('Single-file manifest must name one file')
        if not isinstance(state.get('prefix' if is_directory else 'key'),str):
            raise ValueError('Upload manifest has no cloud location')
        event('Demo','INPUT','Using the manifest from a separate upload.',fields=(f'State file     : {state_path.absolute()}',))
    count = len(expected)
    byte_count = sum(value['bytes'] for value in expected.values())
    if byte_count > MAX_BYTES:
        raise ValueError('Upload manifest exceeds the 10 MiB demo guard')
    client = None
    try:
        client = connect_directory(args.provider,config) if is_directory else connect_file(args.provider,config)
        if not uploading and state.get('bucket') != client.bucket:
            raise ValueError('Configured bucket differs from the upload manifest')
        location = state['prefix' if is_directory else 'key']
        event('Demo','CONFIGURATION','📋 Cloud destination',fields=(
            f'Bucket         : {client.bucket}',f'Object / prefix: {location}'))
        transfer_started = perf_counter()
        if uploading:
            if is_directory:
                event('BlobStore','WRITE','AsyncBucketClient.upload_directory() — uploading directory')
                response = await client.upload_directory(str(snapshot),prefix=state['prefix'],
                    include_sub_folders=True,follow_symbolic_links=False)
                check_transfer(response,count,byte_count,'upload')
            else:
                event('BlobStore','WRITE','BucketClient.upload() — uploading one Markdown file')
                client.upload(key=state['key'],payload=payload,content_type='text/markdown; charset=utf-8')
            event('BlobStore','WRITE OK','Upload confirmed by multicloud-py.',fields=(
                f'Files uploaded : {count}/{count}',f'Bytes uploaded : {size(byte_count)}',
                f'Elapsed        : {perf_counter()-transfer_started:.3f} s'))
            state['bucket'] = client.bucket
            write_json(work/'manifest.json',state)
            write_json(latest,state)
            event('Demo','MANIFEST','Upload recorded for a separate download.',fields=(
                f'State file     : {(work/"manifest.json").absolute()}',
                f'Next command   : ./demo {"download-directory" if is_directory else "download"} --provider {args.provider} --repo {args.repo}'))
        else:
            restored.mkdir(parents=True,exist_ok=False)
            if is_directory:
                event('BlobStore','READ','AsyncBucketClient.download_directory() — downloading directory')
                response = await client.download_directory(state['prefix'],str(restored))
                check_transfer(response,count,byte_count,'download')
            else:
                event('BlobStore','READ','BucketClient.download() — downloading one Markdown file')
                response = client.download(key=state['key'])
                (restored/next(iter(expected))).write_bytes(response.content)
            event('BlobStore','READ OK','Download completed through multicloud-py.',fields=(
                f'Files downloaded: {count}/{count}',f'Saved to       : {restored.absolute()}',
                f'Elapsed        : {perf_counter()-transfer_started:.3f} s'))
            verify_download(restored,expected)
            event('Demo','RESULT','Downloaded content matches the upload manifest.',fields=(f'Files verified : {count}/{count}',))
        event('Demo','PROCESS COMPLETE',f'{title} completed.',fields=(f'Elapsed        : {perf_counter()-started:.3f} s',))
        banner(f'{title} COMPLETED',f'Files: {count}/{count}')
    except Exception as exc:
        raise RuntimeError(f'{title} failed: {exc}. Local artifacts retained at {work}') from exc
    finally:
        if client is not None:
            if is_directory:
                await client.close()
            else:
                client.close()
