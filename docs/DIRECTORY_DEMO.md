# Review bundle directory demo

Code Review Manager demonstrates native directory operations in
[multicloud-py](https://github.com/salesforce/multicloud-py).

## Use case

A reviewer or CI job needs to restore an entire review knowledge bundle, including
human-readable guidance, structured rules and source context. Moving only the
Markdown loses that context. This demo transfers a folder with three explicitly
synthetic files and preserves its nested layout:

```text
examples/review_bundle/
├── knowledge.md
├── reviews/comments.json
└── rules/conventions.json
```

The sample makes no claim of actual PRs or confirmed human authorship. For real
learning, use the existing skill's provenance-confirmation workflow first.

## One-time setup

Follow the README installation, including both SDK provider packages with their
`[async]` extras. If upgrading an existing environment, use your SDK source path:

```bash
.venv/bin/pip install \
  -e "$SDK/packages/blob/multicloud-blob-aws[async]" \
  -e "$SDK/packages/blob/multicloud-blob-gcp[async]" boto3 botocore
.venv/bin/pip check
```

Select an existing bucket and configure standard credentials for that provider.
For the demonstration buckets:

```bash
export HRL_AWS_BUCKET=pr-review-content
export HRL_GCP_BUCKET=pr-review-content
```

Directory upload/download needs object write/read and listing permissions.
Optional cleanup additionally needs delete permission. Nothing provisions cloud
resources. No credentials or generated review exports belong in Git.

## Run

```bash
./demo directory --provider aws
./demo directory --provider gcp
```

Only the provider changes. At each stage, answer `y` to start or `n` to stop.
Empty input or EOF also stops; invalid answers prompt again. `--yes` explicitly
selects unattended execution.

1. **Prepare review bundle:** copy the selected folder into a fresh local snapshot,
   inventory every nested file and record its checksum.
2. **Upload review directory:** call `AsyncBucketClient.upload_directory()` once
   with recursive upload enabled and symlink following disabled. Print the SDK's
   attempted/successful/failed counts and bytes transferred.
3. **Download review directory:** call `AsyncBucketClient.download_directory()`
   once into a fresh destination. Print the SDK's download counts and bytes.
4. **Verify review bundle:** compare the complete file set, relative paths and
   SHA-256 checksums. Print a result for each file and the overall counts.

The application uses the SDK's directory APIs, rather than implementing a loop
of individual object transfers. Directory steps require the same explicit
AWS/GCP selection as single-file commands.

```bash
# Use an explicitly selected folder instead of the synthetic sample.
./demo directory --provider gcp --directory output/my-review-export

# Add an optional fifth stage using the SDK's directory-delete operation.
./demo directory --provider gcp --cleanup
```

Every run uses a new UUID prefix:
`review_bundles/<percent-encoded-repository>/<UUID>/`. Source snapshots and fresh
downloads stay under ignored `output/<repository>/directory-<UUID>/`. Nothing
removes or overwrites existing local folders or the single-file knowledge record.
A bundle must be nonempty, contain no symlinks and fit the 10 MiB demo guard.

Cleanup calls `AsyncBucketClient.delete_directory()` only with the generated
prefix including its trailing slash, then uses `list_page()` to check that no
current objects remain. Local source/download folders are retained. Stopping
before cleanup retains the cloud bundle too. Cleanup is skipped on transfer or
verification failure. No bucket-wide delete or user-supplied delete prefix exists.

## Live GCP result

The synthetic sample run produced these actual results; repetitive details are
omitted here, and timings will vary:

```text
[DIRECTORY STEP 1/4] Prepare a portable review knowledge bundle
    Files planned  : 3
    Total content  : 1.41 KiB (1,448 bytes)

[DIRECTORY STEP 2/4] Upload the entire review bundle through multicloud-py
[WRITE] Uploading folder through AsyncBucketClient.upload_directory()
[DIRECTORY RESULT] Directory upload result from multicloud-py
    Files attempted: 3
    Files succeeded: 3
    Failed transfers: 0
[WRITE OK] Review directory uploaded successfully.
    Files uploaded : 3/3
    Elapsed        : 2.535 s

[DIRECTORY STEP 3/4] Download the review bundle into a fresh local directory
[READ] Downloading folder through AsyncBucketClient.download_directory()
[DIRECTORY RESULT] Directory download result from multicloud-py
    Files attempted: 3
    Files succeeded: 3
    Failed transfers: 0
[READ OK] Review directory downloaded successfully.
    Files read back: 3/3
    Elapsed        : 2.060 s

[DIRECTORY STEP 4/4] Verify every restored review file and its folder structure
[VERIFIED] knowledge.md — content and relative path match
[VERIFIED] reviews/comments.json — content and relative path match
[VERIFIED] rules/conventions.json — content and relative path match
[PROCESS COMPLETE] Directory transfer and content verification passed.
    Files uploaded : 3/3
    Files read back: 3/3
    Files verified : 3/3
    Elapsed        : 5.889 s

DIRECTORY DEMO COMPLETED SUCCESSFULLY
```

Any failed transfer, incorrect count, missing/extra file, content mismatch or
failed cleanup returns an error and prevents the completion banner. Cancellation
returns 130 and preserves local artifacts. A successful upload is not treated as
successful verification.
