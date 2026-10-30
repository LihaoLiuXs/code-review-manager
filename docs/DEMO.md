# Four independent multicloud-py demos

Code Review Manager demonstrates a single Python codebase using AWS S3 or Google
Cloud Storage. Provider selection changes configuration, while each operation
uses the same SDK call on either cloud.

## Setup

Follow the README installation, including SDK provider `[async]` extras for the
directory operations. Configure credentials only for the provider being run.
Buckets must already exist. For the demonstration account, both bucket names are
`pr-review-content`:

```bash
export HRL_AWS_BUCKET=pr-review-content
export HRL_GCP_BUCKET=pr-review-content
```

AWS uses its standard credential chain and bucket region; GCP uses Application
Default Credentials. Credentials and generated artifacts remain outside Git.

## 1. Single-file upload

```bash
./demo upload --provider gcp
```

Accept the operation prompt. The app uploads the raw synthetic Markdown through
`BucketClient.upload()` and records a local manifest. It performs no download or
preflight content read, and claims only that the SDK upload succeeded.

## 2. Single-file download

```bash
./demo download --provider gcp
```

Accept its separate prompt. The app reads the earlier upload's local manifest,
calls `BucketClient.download()` and writes the actual returned bytes into a fresh
local folder. It verifies the size and SHA-256 against the upload manifest. It
performs no upload. The command prints the saved folder and verification result.

## 3. Directory upload

```bash
./demo upload-directory --provider gcp
```

Accept its separate prompt. The app snapshots the three-file synthetic review
bundle, then calls `AsyncBucketClient.upload_directory()` once with recursive
transfer enabled. The SDK handles the file transfers. The app prints attempted,
successful and failed counts and bytes, then records a local manifest. No directory
download is started by this command.

## 4. Directory download

```bash
./demo download-directory --provider gcp
```

Accept its separate prompt. The app calls `AsyncBucketClient.download_directory()`
for the earlier upload's unique prefix. It saves into a fresh folder, checks the
SDK transfer results, and verifies the complete file set, relative paths, byte
sizes and SHA-256 of every file. It performs no upload.

## Presenter control

Every command waits for its own “Start next step? [y/N]” answer. Only `y` or `yes`
starts the selected operation. No, empty input or EOF stops with exit code 130;
invalid answers prompt again. To capture a preview without interaction, explicitly
add `--yes` to that particular command. There is no automatic next operation.
Bare `./demo --provider gcp` is shorthand for single-file upload only.

Change `--provider gcp` to `--provider aws` to run any one of these operations
on AWS with the same source. A download uses only an upload manifest for the same
provider, repository and bucket.

## Inputs and artifacts

Default input file: `examples/review_knowledge.demo.md`.
Default directory: `examples/review_bundle/`.
Use `--file` for a different Markdown file or `--directory` for an explicitly
selected review export folder.

Manifests are local under `output/<repository>/demo/<provider>/`. Uploads print
their per-run manifest path. Download commands use the latest matching manifest
by default, or a particular earlier upload with `--state PATH`. Copy that manifest
to another reviewer or CI environment if it needs to restore the same upload.
No credentials are stored in the manifest.

Cloud artifacts use fresh prefixes:
`demo_artifacts/<percent-encoded-repository>/<generated-UUID>/`.
The single-file demo stores actual Markdown bytes; the learning workflow's
separate JSON knowledge record is unchanged. Directory uploads preserve nested
paths. All snapshots, downloads and manifests are ignored by Git.

Each operation prints its own banner and result; uploads do not claim content
verification. Downloads verify actual returned data and fail on mismatch. Failures
preserve local artifacts and suppress successful completion banners.

The existing skill and explicit storage save/sync workflows retain their
preflight/merge/read-back behavior. They are distinct from these four SDK demos.
