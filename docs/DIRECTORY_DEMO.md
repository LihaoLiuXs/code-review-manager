# Review bundle: separate directory upload and download

## Use case

A reviewer or CI job needs an entire review context folder: human-readable
guidance, structured conventions and the source comments. Code Review Manager
uses the native `multicloud-py` directory APIs to share and restore that folder:

```text
examples/review_bundle/
├── knowledge.md
├── reviews/comments.json
└── rules/conventions.json
```

The default files are explicitly synthetic; they claim no actual PR or confirmed
human provenance. For real learning, run the skill's provenance workflow first.

## Setup

Follow README to install the SDK source packages with `[async]` extras. Configure
an existing bucket and credentials for the selected provider. Object write/read
and listing permissions are needed. No cloud resources are provisioned.

## Include both directory stages in the full demo

`./demo --provider gcp` now runs single upload, single download, directory upload
and directory download in one command, with prompts and separate section headings.
Use `--provider aws` for AWS. Each download verifies the upload from that same run.
The standalone directory commands below remain available.

## Directory upload only

```bash
./demo upload-directory --provider gcp
```

Answer yes to the prompt. The application copies the selected folder to a fresh
local snapshot, calculates a manifest, then invokes:

```python
await client.upload_directory(
    str(snapshot), prefix=prefix,
    include_sub_folders=True, follow_symbolic_links=False)
```

The SDK response supplies total files, successful uploads, per-file failures
and bytes transferred. The app checks those values and ends after recording the
upload manifest. It makes no directory download call.

## Directory download only

```bash
./demo download-directory --provider gcp
```

Answer yes to this separate prompt. The app loads the matching upload manifest
and invokes:

```python
await client.download_directory(prefix, str(fresh_destination))
```

It prints the SDK's download counts, saves the files in a fresh local folder,
then verifies every path, size and SHA-256 against the upload manifest. It makes
no directory upload call. File mismatches or missing/extra files fail verification.

Change only the provider to aws for either command. The same asynchronous SDK
client and application code handle both providers.

## Select inputs or an earlier upload

```bash
./demo upload-directory --provider gcp --directory output/my-review-export
./demo download-directory --provider gcp --state /path/to/upload/manifest.json
```

Without --state, download uses the latest directory upload for that provider and
repository. Each upload has a fresh cloud prefix and per-run local manifest;
earlier uploads remain addressable by their manifest. The manifest contains no
credentials. All artifacts stay under ignored output/.

The bundle must be nonempty, contain no symlinks and fit the 10 MiB demo guard.
Each download checks the manifest's operation type, provider, repository and
configured bucket. Fresh destination folders avoid stale local files hiding an
incomplete transfer. These commands do not perform cleanup or deletion.

## Live GCP results from the separate commands

```text
DIRECTORY UPLOAD
AsyncBucketClient.upload_directory()
Files uploaded : 3/3
Bytes uploaded : 1.41 KiB (1,448 bytes)
Failed transfers: 0
Elapsed        : 2.147 s
DIRECTORY UPLOAD COMPLETED
```

A later, independently invoked command produced:

```text
DIRECTORY DOWNLOAD
AsyncBucketClient.download_directory()
Files downloaded: 3/3
Failed transfers: 0
VERIFIED knowledge.md
VERIFIED reviews/comments.json
VERIFIED rules/conventions.json
Files verified : 3/3
Elapsed        : 2.459 s
DIRECTORY DOWNLOAD COMPLETED
```

Both were actual GCP SDK operations against pr-review-content. Unit tests use SDK
doubles; their results are recorded separately from these live checks.
