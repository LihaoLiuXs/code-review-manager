# Demo: one source code, two substrates

The same Python application and command run on AWS S3 or Google Cloud Storage.
Only `--provider aws` versus `--provider gcp` changes. Provider-specific settings
are bucket, region and credentials configuration. The read/write business logic
is implemented once in `hrl/multicloud_store.py` using MultiCloud `BucketClient`.

## Setup

Install the application and SDK packages using README. The executable `./demo`
uses the checkout's `.venv/bin/python` automatically; no shell activation is needed. One local environment can
contain both provider packages; authenticate only the provider being demonstrated.
The same project checkout can also run in an AWS or GCP environment with its
normal credentials. There are no separate application implementations to deploy.

For this demo the selected S3 and GCS buckets are both named pr-review-content:

```bash
export HRL_AWS_BUCKET=pr-review-content
export HRL_GCP_BUCKET=pr-review-content
# Set AWS_REGION to the S3 bucket region when running on AWS.
```

AWS uses standard environment credentials, profiles or the environment's IAM
role. GCP uses Application Default Credentials. An AWS run needs no GCP login;
a GCP run needs no AWS session. Buckets must already exist and the selected
identity needs read/write and bucket-check permissions. See README for setup.

## One command: save and read back on AWS

From the HRL project directory:

```bash
./demo --provider aws
```

Before every stage the demo asks:

```text
Start next step? 1/4 — Check cloud access and read the existing baseline [y/N]:
Start next step? 2/4 — Prepare knowledge and preserve the retryable revision [y/N]:
Start next step? 3/4 — Upload knowledge | destination 1/1 | provider=aws [y/N]:
Start next step? 4/4 — Read back and verify the uploaded knowledge [y/N]:
```

Answer `y` or `yes` separately at each prompt. No, an empty answer, or EOF stops
the demo before that step. Invalid answers prompt again. Local files are preserved.
Stopping before step 4 leaves the successful upload in the bucket but does not
claim read-back verification. Cancellation returns exit code 130.

Opt in to automatic execution with `./demo --provider aws --yes` or
`./demo --provider gcp --yes`. Original `scripts/storage.py` commands remain
unattended for skill workflows; add `--interactive` to ask there too. Read-only
`./demo get` and `./demo verify` ask before their cloud read.

This reads the selected bucket's baseline, uploads the JSON record, downloads it
and verifies the complete logical content. The Markdown includes an explicit
synthetic-demo banner. It does not claim extraction from real PR feedback.

## Same command: change only the provider to GCP

```bash
./demo --provider gcp
```

Both short commands default to the synthetic Markdown at
`examples/review_knowledge.demo.md`, repository key `demo/human-review-learning`,
and the checkout's `config.toml`. Each uploads one JSON blob containing the
Markdown, then performs a separate SDK download and verifies the full record.
`examples/pending.json` retains the exact revision for retries. Only the explicitly
selected cloud is accessed. Bucket and credential setup remains a one-time step.

For your own input or a retry:

```bash
./demo --provider aws --repo demo/my-reviews --file my-knowledge.md
./demo --provider aws --record examples/pending.json
./demo --help
```

Relative `--file`, `--record`, `--config`, and `--output` arguments resolve from
your current directory. The bundled sample and default config resolve from the
checkout even when you invoke `/path/to/human-review-learning/demo` elsewhere.
The original `scripts/storage.py` interface remains available for the learning
skill and explicit storage commands.

The exact same source files perform these operations. The MultiCloud SDK selects
the provider implementation at client construction time. No AWS/GCP-specific
upload or download implementation exists in HRL.

## Show the SDK code and logs

The application constructs `BucketClient(provider=provider, bucket=bucket, ...)`
from configuration. Both providers then use these same SDK operations:

```python
self.client.upload(key=key, payload=payload, content_type='application/json')
response = self.client.download(key=key)
```

The full demo opens with a boxed welcome banner, shows provider and bucket
configuration, and separates CHECK CLOUD ACCESS, PREPARE KNOWLEDGE,
UPLOAD KNOWLEDGE, and READ BACK & VERIFY with prominent headings. 🔄 marks
SDK activity, ✅ marks successful results, and ❌ marks errors. The final boxed
DEMO COMPLETED SUCCESSFULLY banner appears only after read-back verification.
The command waits for an explicit yes before each stage. `--yes` runs without
prompts; neither mode adds artificial delays.

Logs use the Java demo's timestamp / level / component style. Four numbered
stages separate preflight, preparation, upload, and read-back verification.
File sizes, revision, destination and elapsed time appear on indented detail
lines. INFO marks progress; ERROR marks failures. Times use the runtime's local
timezone; durations use a monotonic clock. Output flushes immediately and does
not require a color-capable terminal.

Abbreviated illustrative output after accepting each prompt (timestamps, durations and the checksum below
are placeholders; live values depend on the run):

```text
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MultiCloud Python SDK — Knowledge Demo                    ║
║               One source code • AWS S3 or Google Cloud Storage               ║
╚══════════════════════════════════════════════════════════════════════════════╝

12:00:00.000 INFO  Demo       [PROCESS START] Human Review Learning | MultiCloud Python SDK
    Selected provider: gcp
    Repository     : demo/human-review-learning
12:00:00.000 INFO  Demo       [STEP 1/4] Check cloud access and read the existing baseline
12:00:00.500 INFO  Demo       [STEP 2/4] Prepare knowledge and preserve the retryable revision
    Markdown       : 6.72 KiB (6,883 bytes)
    Revision       : 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ UPLOAD KNOWLEDGE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12:00:00.501 INFO  Demo       [STEP 3/4] Upload knowledge | destination 1/1 | provider=gcp
12:00:00.501 INFO  BlobStore  [WRITE] [GCP GCS] Uploading knowledge through BucketClient.upload()
    Target         : gs://pr-review-content/review_knowledge/demo%2Fhuman-review-learning.json
    Format         : JSON containing Markdown in knowledge_md
    Payload        : 14.05 KiB (14,385 bytes)
12:00:00.800 INFO  BlobStore  [WRITE OK] [GCP GCS] Uploaded knowledge successfully.
    Files uploaded : 1/1
    Elapsed        : 0.299 s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ READ BACK & VERIFY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
12:00:00.800 INFO  Demo       [STEP 4/4] Read back and verify the uploaded knowledge
12:00:00.800 INFO  BlobStore  [READ-BACK START] [GCP GCS] Starting a separate BlobStore download after upload success.
12:00:00.800 INFO  BlobStore  [READ] [GCP GCS] Downloading knowledge through BucketClient.download()
12:00:01.100 INFO  BlobStore  [READ OK] [GCP GCS] Downloaded knowledge successfully.
    Payload        : 14.05 KiB (14,385 bytes)
    Elapsed        : 0.300 s
12:00:01.101 INFO  BlobStore  [VERIFIED] [GCP GCS] Markdown and full JSON content match the source.
    Files uploaded : 1/1
    Files read back: 1/1
    Files verified : 1/1
    Markdown SHA-256: <actual checksum printed by the run>
12:00:01.101 INFO  Demo       [PROCESS COMPLETE] Demo completed successfully.
    Knowledge files: 1 | Destinations: 1
    Files uploaded : 1/1
    Files read back: 1/1
    Files verified : 1/1
    Elapsed        : 1.101 s

╔══════════════════════════════════════════════════════════════════════════════╗
║                         DEMO COMPLETED SUCCESSFULLY                          ║
║                    Uploaded: 1   Downloaded: 1   Verified: 1                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

Present this as: **start → check cloud access → prepare the Markdown → upload
one file → upload successful → download through the SDK → verify → complete**.
The precheck is an earlier read of the baseline. READ-BACK START marks the
separate read performed after upload succeeds. No extra command triggers it.

One knowledge Markdown document is embedded in one JSON blob in `knowledge_md`.
Payload measures the complete JSON; Markdown measures the UTF-8 document. The
checksum identifies the verified Markdown, while verification compares the full
logical JSON record. The final counts represent cloud objects across the selected
destinations; per-destination counts appear immediately after each operation.

An AWS run prints `Selected provider: aws`, `[AWS S3]` and `s3://` instead.
Missing knowledge is labeled READ MISSING. Upload success alone does not complete
the demo: a failed read or mismatch prints zero verified files and ERROR /
PROCESS FAILED, with no PROCESS COMPLETE. Only claim live success when the live
command passes. Structured rules are separate from rules written in Markdown;
the manual sample has five illustrative Markdown rules and zero structured rules.

## Read and verify using the same provider selector

```bash
./demo get --provider aws
./demo get --provider gcp
```

`verify` can compare a stored record with the exact expected pending file created
by save. Use the provider on which that pending record was written:

```bash
.venv/bin/python scripts/storage.py verify --provider gcp \
  --repo demo/human-review-learning --record examples/pending.json
```

Without --record, verify checks only that the selected cloud's record is readable
and valid. It does not claim equality with another cloud.

Independent --file saves can produce different timestamps/revisions. To show
identical bytes deployed through the same app, use a fresh demo repository key
and create one pending record. The key below must be unused for a first-run demo:

```bash
.venv/bin/python scripts/storage.py save --provider aws \
  --repo demo/portable-code --file examples/review_knowledge.demo.md
```

Then deploy that EXACT pending file using commands differing only in provider:

```bash
.venv/bin/python scripts/storage.py save --provider aws \
  --repo demo/portable-code --record examples/pending.json
.venv/bin/python scripts/storage.py save --provider gcp \
  --repo demo/portable-code --record examples/pending.json
```

For an optional explicit cross-cloud comparison:

```bash
.venv/bin/python scripts/storage.py verify --repo demo/portable-code --providers aws,gcp
```

Different existing baselines stop writes rather than being overwritten. Reusing a
pending file retries that exact revision. Do not regenerate it just to retry.
Generated pending.json files are local artifacts; do not commit them.

## Learn real reviews on a selected substrate

From Claude Code in this checkout:

```text
/learn-reviews https://github.com/salesforce/multicloudj --days 90 --provider aws
/learn-reviews https://github.com/salesforce/multicloudj --days 90 --provider gcp
```

The same skill collects feedback, asks every unresolved Human / AI / Skip
question, extracts evidence-backed guidance, merges the selected cloud's baseline
and uses the same storage implementation. If --provider is omitted from the skill,
it asks which cloud to use; it does not silently access both.

## Rehearse without credentials

```bash
.venv/bin/python -m pytest -q -s tests/test_provider_selection.py
```

These are explicitly mocked tests. They check provider isolation and that the
same pending record produces identical upload bytes on AWS and GCP. They do not
claim real uploads or live infrastructure deployment.

## Java demo reference

The substrate-neutral version of the reference service is its
[substrate-agnostic-storage branch](https://github.com/sandeepvinayak/student-docs-manager/tree/substrate-agnostic-storage).
Its SubstrateConfig selects the SDK provider while BlobStoreService performs
common operations. HRL follows the same separation, with runtime --provider
selection in the Python CLI and one application package for both clouds.

## Comparison with the Java demo

The [MultiCloudJ reference branch](https://github.com/sandeepvinayak/student-docs-manager/tree/substrate-agnostic-storage)
uses short commands such as `java -jar $JAR upload stu001 /tmp/homework.txt`.
It selects provider dependencies through Maven profiles and provider IDs through
environment variables. Its main branch describes the original AWS SDK version.

HRL follows the short-command approach with `./demo --provider aws|gcp`. The
launcher supplies the demo input defaults, while the explicit provider flag
selects the SDK implementation at runtime. No rebuild or source edit is required
to switch between the installed AWS and GCP providers. HRL stores its knowledge
and metadata together in BlobStore.

Operation durations exclude the prompt before that operation. Total elapsed time
includes the presenter's time answering prompts. Prompt behavior is covered by
mocked SDK tests; these checks do not invent user answers for live cloud runs.
