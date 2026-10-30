# SDK investigation: blob storage

SDK source: https://github.com/salesforce/multicloud-py
Verified upstream HEAD: 550ba3babfaefe68aaaa340f59bbfda77d123398
Package versions: 0.1.9. Inspected the public BlobStore client, driver response
classes, S3/GCS providers, package metadata, and examples/blob/blob_example.py.
The SDK sources are not modified.

Real import: `from multicloud.blob.blob_client import BucketClient`.
Constructor keyword arguments used by HRL: provider (`aws` or `gcp`), bucket,
and an optional configured region. The provider registry discovers distributions through the
`multicloud.blob.providers` entry-point group.

- `upload(key=..., payload=bytes, content_type="application/json")`: stores a
  complete object; HRL sends deterministic UTF-8 JSON with sorted keys.
- `download(key=...)`: returns `DownloadResponse`; `.content` holds bytes.
- `does_bucket_exist()`: checks the configured bucket. HRL invokes this after a
  download raises common `ResourceNotFoundException`, because that exception may
  mean either a missing object or a missing bucket. A missing/inaccessible bucket
  must not be treated as a first-run empty knowledge record.
- `close()`: closes owned provider resources. HRL closes constructed clients.

Provider registration classes are AwsBlobStore and GcpBlobStore; application code
uses only BucketClient and common SDK exceptions. No direct native cloud clients
are used. S3/GCS provider authentication uses standard AWS credentials/profiles
and GCP Application Default Credentials respectively.

One JSON object contains the complete logical record, including knowledge_md,
knowledge_version and rules. Object key: shared prefix plus percent-encoded full
repository ID and .json, for example review_knowledge/salesforce%2Fmulticloud-py.json.
The original repo_id remains in the JSON. There is one object per repository per
cloud and no database, partition-key configuration, or cloud-specific encoding.

HRL retains application knowledge revisions, preflight baseline conflict checks,
explicit single-provider runs, exact pending-file retries, and complete JSON
read-back verification. S3/GCS metadata and ETags are not included in the logical
record. The simple MVP still assumes one writer at a time; uploads do not use
conditional ETag/generation matching. Demo logs use timestamped INFO/ERROR events with Demo and BlobStore components,
four numbered stages, readable payload sizes, operation durations and file counts. They name BucketClient.upload() and BucketClient.download(),
mark the post-upload READ-BACK START, and report final verified object counts only
after the downloaded Markdown and full JSON match. A Markdown SHA-256 checksum
identifies the verified document. The logs use the runtime local timezone and a
monotonic timer; no artificial progress or delays are added.

Source installation: six editable distributions (three common packages,
multicloud-py-blob, multicloud-py-blob-aws and multicloud-py-blob-gcp). The final
local source checkout is .sdk/multicloud-py (ignored); README uses a sibling
checkout so its commands also work on a new machine. requirements.txt records
third-party packages; editable HRL/SDK packages are installed using README.

## One application, provider-selected execution

The short `./demo --provider aws|gcp` command delegates to the same storage
parser and operations with synthetic sample defaults. `./demo get` and
`./demo verify` also accept the explicit provider flag.
All storage commands require --provider aws or --provider gcp. Only the selected
client is constructed and only that cloud is read/written. The Store upload,
download, serialization, validation and verification methods are identical for
both providers. Factory differences are limited to configuration (bucket/region/
credentials), with no cloud-specific business operations. The same pending JSON
can be uploaded unchanged by changing only the provider flag.

An explicit --providers aws,gcp mode remains for optional comparison/sync; it is
mutually exclusive with --provider and never the default. Single-cloud verify
checks readability unless --record supplies the expected logical record, and
never claims cross-cloud equivalence. Save always performs full read-back.

Reference inspected: student-docs-manager's substrate-agnostic-storage branch,
README, SubstrateConfig.java and BlobStoreService.java. That branch separates
runtime provider configuration from shared SDK service operations. Its main
branch describes an AWS-specific version; the substrate-neutral branch is the
relevant reference. See DEMO.md for the link and matching Python commands.

## Presenter control

The short demo asks before cloud preflight, local preparation, upload, and
post-upload download/verification. Only explicit yes advances; no, empty input,
or EOF stops all remaining steps. If the presenter stops after uploading, the
blob is retained and reported as not verified. `--yes` explicitly disables
prompts. The skill's existing storage command remains unattended by default;
`--interactive` enables the same control there. Both modes use the same SDK calls.

## Native asynchronous directory APIs

The same inspected SDK commit exposes AsyncBucketClient.upload_directory(),
download_directory(), delete_directory() and list_page(). The directory demo
uses these APIs directly, preserves nested paths and checks the returned
total_files, successful_uploads/successful_downloads, failed_transfers and
total_bytes_transferred. It then verifies the restored file set and SHA-256 of
each file against a unique local snapshot. It never claims verification solely
from transfer counts. Upload failures prevent downloading; download failures and
content mismatches prevent completion and cleanup.

Install provider packages with their [async] extras: AWS uses aiobotocore; GCP
uses gcloud-aio-storage and aiohttp. These are SDK implementation dependencies,
not directly called by application code. Both clients use the same client_options
provider configuration. requirements.txt records the resolved compatible
third-party versions; the SDK source itself remains unchanged.

Every cloud prefix is review_bundles/<encoded-repository>/<generated-UUID>/,
including the trailing slash. Optional cleanup can only delete that run's prefix
and verifies absence through the SDK list_page(). Local files remain available.

## Independent audience-facing operations

hrl/demo_operations.py implements upload, download, upload-directory and
download-directory. A command makes only its named transfer call; uploads never
download automatically. The default ./demo orchestrates all four stages through run_all(); individual
commands still perform only their named transfer. The
learning skill's save workflow and legacy explicit directory round-trip remain
separate advanced workflows for compatibility.

The single-file example uploads raw Markdown through BucketClient.upload() and
downloads through BucketClient.download(). Directory commands call the native
AsyncBucketClient directory APIs once each. A local manifest records the cloud
key/prefix, bucket/provider/repository identity and per-file size/checksum. A
separate download validates that manifest, saves into a fresh folder and verifies
returned content. No operation overwrites the existing learning JSON knowledge
record. No native provider SDK calls or source SDK edits are introduced.

## Full demo orchestration

run_all() invokes the four existing operation functions in order, with prompts
numbered 1/4 through 4/4. Upload functions return their per-run manifest paths,
which are passed explicitly into their corresponding download stages. The final
summary is printed only after every stage returns successfully. Cancellation or
an SDK/content-verification error propagates immediately and prevents later stages.
No provider-specific operations or additional SDK implementations are introduced.
