# Code Review Manager

**Code Review Manager is an example application for
[multicloud-py](https://github.com/salesforce/multicloud-py) and is used as a demo
of the MultiCloud Python SDK.** It demonstrates one Python codebase running on
AWS S3 or Google Cloud Storage by changing only the provider parameter, with
interactive upload, download, and content verification.

The application's Human Review Learning (HRL) workflow extracts institutional
knowledge from historical code reviews and preserves it in a portable,
cloud-agnostic knowledge store.

**One source code, two substrates.** The same Python application stores and
retrieves review knowledge through the MultiCloud Python SDK. Select AWS S3 with
`--provider aws` or Google Cloud Storage with `--provider gcp`; no source edits
or separate AWS/GCP application implementations are required.

A run reads/writes only the selected cloud. Saving also downloads the record and
verifies its content, so one command demonstrates the SDK end to end:

```bash
./demo --provider aws

# Same command and source code; change only the provider.
./demo --provider gcp
```

The demo asks **“Start next step? [y/N]”** before each stage: downloading existing knowledge,
local preparation, upload, and read-back verification. Type `y` or `yes` to
continue. Type `n`, press Enter without an answer, or close input to stop.
Stopping returns exit code 130 and never reports successful completion. If you
stop after upload, the blob remains stored but is explicitly not verified.

For an unattended run, opt in with `./demo --provider gcp --yes`.

After the one-time installation below, run these from the checkout. The launcher
uses `.venv/bin/python` automatically, the bundled `examples/review_knowledge.demo.md`,
repository key `demo/human-review-learning`, and the checkout's `config.toml`.
Existing cloud credential and bucket configuration still applies.

```bash
# Read the saved record with the same simple command.
./demo get --provider aws

# Use your own Markdown and repository key.
./demo --provider aws --repo demo/my-reviews --file my-knowledge.md

# Show all options; the original scripts/storage.py commands still work.
./demo --help
```

The committed sample is clearly labeled synthetic demo content. See the
[demo runbook](docs/DEMO.md) for setup, logs, retrieval and verification.

This is a small, manually executed Python demo and Claude Code skill. It learns
from **confirmed human** feedback, preserves evidence, merges older conventions,
and writes one logical document per `owner/repository`. It does not execute AI
reviews, train a model, run a service, or replace human PR approval.

## Directory demo: share a review knowledge bundle

A reviewer or CI job needs the complete review context: the knowledge Markdown,
structured rules, and source comments. The directory demo uploads that folder,
downloads it into a fresh local folder, and verifies every file and relative path
through the native `multicloud-py` directory APIs.

```bash
./demo directory --provider aws
./demo directory --provider gcp
```

Both commands use the same source and synthetic three-file bundle:

```text
examples/review_bundle/
├── knowledge.md
├── reviews/comments.json
└── rules/conventions.json
```

The four prompted stages are prepare bundle, upload directory, download directory,
and verify restored files. SDK operations are `AsyncBucketClient.upload_directory()`
and `AsyncBucketClient.download_directory()`; there is no application loop that
uploads or downloads individual objects. Logs report the SDK's transfer counts,
failed transfers, bytes and each verified filename.

```bash
# Use your own explicitly selected review export folder.
./demo directory --provider gcp --directory output/my-review-export

# Optional fifth prompted stage: remove only this demo run's cloud prefix.
./demo directory --provider gcp --cleanup

# Explicit unattended presentation run.
./demo directory --provider gcp --yes
```

Each run gets a unique cloud prefix and fresh local source/download folders under
ignored `output/`. No existing knowledge or folders are overwritten. `--cleanup`
calls the SDK's native `delete_directory()` only for that run, then checks that
no objects remain. It retains the local files. See [the directory demo guide](docs/DIRECTORY_DEMO.md)
for setup, permissions, failure handling and live results.

## Two functional modules

```text
/learn-reviews owner/repo --provider aws|gcp --days 30
                         |
        Learning skill (Claude Code or Codex)
        GitHub reviews -> provenance questions -> HUMAN evidence
                         |
        Read selected-cloud baseline -> extract/merge knowledge
                         |
          Markdown + exact pending revision on disk
                         |
       ONE Python Store: upload / download / verify
                         |
      MultiCloud BucketClient(provider=PROVIDER, bucket=BUCKET)
                         |
          selected S3 (aws) OR Cloud Storage (gcp)
                         |
                 Read-back verification
```

Python handles APIs, pagination, dates, normalization, decision persistence,
merge-plan validation, Markdown rendering, and storage. The running agent handles
contextual classification, extraction, tagging, semantic deduplication, and
contradictions. No Anthropic API key or additional LLM service is needed.

## Installation

Requires Python 3.11+, Git, GitHub CLI, and Claude Code or Codex. Commands below use
a local venv; the upstream SDK is checked out separately and never modified.

```bash
git clone https://github.com/LihaoLiuXs/code-review-manager.git
cd code-review-manager
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'

git clone https://github.com/salesforce/multicloud-py.git ../multicloud-py
# This SDK commit was inspected and installed successfully for this demo:
git -C ../multicloud-py checkout 550ba3babfaefe68aaaa340f59bbfda77d123398
SDK="$(cd ../multicloud-py && pwd)"
.venv/bin/pip install \
  -e "$SDK/packages/common/multicloud-common" \
  -e "$SDK/packages/common/multicloud-aws-common" \
  -e "$SDK/packages/common/multicloud-gcp-common" \
  -e "$SDK/packages/blob/multicloud-blob" \
  -e "$SDK/packages/blob/multicloud-blob-aws[async]" \
  -e "$SDK/packages/blob/multicloud-blob-gcp[async]"
.venv/bin/pip check
.venv/bin/python -m pytest
```

Install all six packages together: local candidates satisfy the SDK's unpublished
inter-package dependencies. Do not assume its distributions are on PyPI. The
source repository uses a uv workspace; HRL's separate environment uses pip editable
installs and does not change the SDK workspace. `requirements.txt` records this
run's third-party dependency versions; editable HRL/SDK packages are excluded.
Install the SDK from source using the commands above. See [SDK details](docs/SDK.md).

## Configuration and credentials

```bash
cp config.example.toml config.toml
# Configure the bucket for the provider you plan to run; the other cloud is optional.
gh auth login --hostname github.com
gh auth status --hostname github.com
export AWS_PROFILE=your-profile
export AWS_REGION=us-west-2
export HRL_AWS_BUCKET=YOUR_S3_BUCKET
export HRL_GCP_BUCKET=YOUR_GCS_BUCKET
export GOOGLE_CLOUD_PROJECT=your-project
gcloud auth application-default login
# Alternatively, use a service-account JSON file outside this repository:
# export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
```

`.env.example` documents environment variables. Scripts do not automatically load
`.env`. SDK credential discovery supports standard AWS profiles/environment
credentials and GCP Application Default Credentials. Authenticate only the
selected provider for a single-cloud run; installing both SDK providers does
not require credentials for both. Use your organization's usual
SSO login when applicable. Do not commit tokens, service-account keys, review
exports, or configuration containing account details.

GitHub needs read access to the repository, PRs and comments; private repositories
require appropriate account access and token scopes. Errors on any API page abort
the fetch without publishing a partial `reviews.json`. A previous successful
artifact may remain on disk; only continue after a successful fetch.

### Prepare the destinations

HRL does not provision infrastructure. Create or select a bucket on the cloud
you want to run. Configure both only when demonstrating both provider choices. Bucket names
must be globally unique within each cloud.
Configure the names with `storage.aws.bucket` and `storage.gcp.bucket` in
`config.toml`, or override them using `HRL_AWS_BUCKET` and `HRL_GCP_BUCKET`.
If upgrading an older configuration, replace the table/database settings with
the bucket settings from `config.example.toml`; the learning artifacts keep
their existing format.
`GOOGLE_CLOUD_PROJECT` is useful for credentials and provisioning; runtime blob
operations address the configured GCS bucket directly and need no database.

Example one-time setup (only for buckets that do not already exist):

```bash
# S3 uses a different create request for us-east-1.
if [ "$AWS_REGION" = "us-east-1" ]; then
  aws s3api create-bucket --bucket "$HRL_AWS_BUCKET" --region "$AWS_REGION"
else
  aws s3api create-bucket --bucket "$HRL_AWS_BUCKET" --region "$AWS_REGION" \
    --create-bucket-configuration "LocationConstraint=$AWS_REGION"
fi
aws s3api wait bucket-exists --bucket "$HRL_AWS_BUCKET" --region "$AWS_REGION"

gcloud storage buckets create "gs://$HRL_GCP_BUCKET" \
  --project "$GOOGLE_CLOUD_PROJECT" --location=us-east1 \
  --uniform-bucket-level-access
```

Choose locations and access policies appropriate for your demo accounts. Runtime
permissions: S3 `GetObject`/`PutObject` on the knowledge prefix and `ListBucket`
for bucket checks and directory listing; GCS `storage.objects.get`, `storage.objects.create`, and
`storage.objects.delete` (required to overwrite existing objects), plus
`storage.buckets.get` for bucket checks. Directory downloads also require
`storage.objects.list`; optional directory cleanup requires object-delete permission
(S3 `DeleteObject`, GCS `storage.objects.delete`). Provisioning requires additional
administration permissions. Credentials and permission errors block writes.
A missing object means no knowledge yet only after the bucket is confirmed to
exist; a missing/inaccessible bucket is an error.

The selected cloud stores one UTF-8 JSON blob per repository, including Markdown,
metadata, revision, and compact rules. Default object key:

```text
review_knowledge/salesforce%2Fmulticloud-py.json
```

The full `owner/repository` is percent-encoded, preserving owner identity without
collisions. Change the shared `storage.prefix` if desired (default
`review_knowledge`). The same pending.json can be deployed unchanged to either
provider for an identical logical record. Independent --file saves may have
different timestamps/revisions; use --record to demonstrate identical payloads.
Raw reviews remain local. Local knowledge files and pending revisions from the earlier
storage design retain their format; they can be saved to blobs using the same
commands. HRL does not automatically migrate data from an old cloud database.

## Run the skill

Start Claude Code **from this checkout**, then invoke:

```text
/learn-reviews salesforce/multicloud-py --provider aws
/learn-reviews salesforce/multicloud-py --days 90 --provider gcp
/learn-reviews salesforce/multicloudj --days 90 --provider aws
/learn-reviews https://github.com/salesforce/multicloudj --days 90 --provider gcp
```

The --provider argument selects the storage substrate for this run. If omitted
from the skill invocation, the agent asks AWS / GCP before cloud access. Storage
CLI commands require --provider explicitly (or the optional --providers mode).
The repository argument is the project whose review history you want to learn.
Both `salesforce/multicloudj` and `https://github.com/salesforce/multicloudj`
select the Java repository. The installed `salesforce/multicloud-py` SDK is a
storage dependency and does not restrict the review target or its language.

All CLI `--repo` arguments accept owner/name or an HTTPS GitHub repository URL.
Homepage URLs with a trailing slash, `.git`, or README tab/fragment are supported.
Other hosts and PR/file URLs are rejected. Both input forms normalize to the same
logical repository ID, local directory and cloud object key. For multicloudj:

```text
Repository ID: salesforce/multicloudj
Local output:  output/salesforce--multicloudj/
Blob key:      review_knowledge/salesforce%2Fmulticloudj.json
```

Example collector command:

```bash
.venv/bin/python scripts/fetch_reviews.py \
  --repo https://github.com/salesforce/multicloudj --days 90 --conversations
```

The project skill is discovered at `.claude/skills/learn-reviews/SKILL.md`, a
relative symlink to the single canonical source at
`.agents/skills/learn-reviews/SKILL.md`. Codex can invoke `$learn-reviews` or be
asked to follow that canonical skill. If a platform does not follow symlinks,
copy the canonical file for installation; edit only the canonical source.
These project skills run within HRL; arbitrary accessible repositories are
supported through the `--repo` argument, without checking out their code.

The skill explains cloud destinations before writes. It fetches inline feedback,
review bodies and PR conversation candidates, reads the selected cloud, classifies
authorship, asks about every unresolved comment before relevance filtering,
extracts rules, performs semantic merging, builds local artifacts, saves
to the selected cloud and verifies the record.
Native agent question APIs vary. The Python terminal fallback supports Human,
AI, or Skip when native questions are unavailable. Without native interaction or
a usable terminal, it pauses for a chat reply. Unanswered questions stay pending.

## Manual walkthrough

```bash
R=salesforce/multicloud-py
D=output/salesforce--multicloud-py
PROVIDER=aws
.venv/bin/python scripts/fetch_reviews.py --repo "$R" --days 30
.venv/bin/python scripts/storage.py get --repo "$R" --provider "$PROVIDER" --output "$D/existing.json"
.venv/bin/python scripts/workflow.py classify --repo "$R"
```

Fetch defaults to 30 days. `--output-dir DIRECTORY` is supported by fetch and
workflow commands; default artifacts are namespaced by repository to prevent
mixing different projects. Optional `--conversations` includes PR conversation
candidates, which the agent evaluates for review content after provenance
confirmation. The learning skill includes this flag by default.

The collector enumerates all PRs (including old/closed PRs), paginates every list,
then filters inline comments by `created_at` and submissions by `submitted_at`.
A PR created years ago with recent feedback is included. Source type plus GitHub
ID prevents duplicate ingestion; inline and submission comments remain distinct
and the agent consolidates duplicated feedback. Embedded diff hunks and related
review bodies supply context without downloading a repository. Complete PR
history enumeration trades API cost for correctness; large repositories may be
slow or rate limited. Failure is explicit, with no claims of completeness.

### Authorship decisions

`user.login` and `user.type` cannot reliably identify generated comments: the same
account may post both human and AI reviews. Configurable explicit attribution
patterns classify clear AI signatures. The skill considers reliable contextual
provenance next. Writing style alone is never proof; model scores are not
calibrated probabilities. There is no claimed classification accuracy.

Without reliable evidence a comment stays `UNCERTAIN`. The developer sees its
body, source, PR and file, and selects Human / AI / Skip. This applies even to
apparently irrelevant notices: provenance and usefulness are separate decisions.
Questions are grouped by PR and review; meaningful batches can be confirmed with the native agent tool.
Terminal mode presents each comment within sorted review groups. Decisions are
cached by repository and comment ID plus a hash of body and relevant context.
Changed content invalidates a decision. Skipped unchanged comments remain skipped;
use the confirm command with a new actual answer to reconsider them. A
human-written comment and an AI-generated comment from the same account can be indistinguishable without
additional provenance; manual confirmation exists to address that limitation.

The native Claude Code question tool is preferred. These helpers provide a
repeatable checkpoint and persist answers after the developer responds:

```bash
.venv/bin/python scripts/workflow.py classify --repo "$R" --non-interactive
.venv/bin/python scripts/workflow.py pending --repo "$R"
# Only after the developer confirms the EXACT displayed comment(s):
.venv/bin/python scripts/workflow.py confirm --repo "$R" \
  --ids conversation_candidate:ACTUAL_ID --label HUMAN
# Use AI for an AI answer, or UNCERTAIN for an explicit Skip.
.venv/bin/python scripts/workflow.py pending --repo "$R"
```

The build rejects unresolved UNCERTAIN comments, including when observations.json
is empty. An explicit Skip must have a matching saved manual decision; EOF or an
unavailable question tool cannot silently clear the queue. Batch answers apply
only to the displayed IDs; never infer all comments by an account share provenance.

### Extraction and automatic merge

Use the skill for this reasoning step. It reads confirmed HUMAN input and all
existing rules, removes social feedback, extracts reusable engineering guidance,
and writes `observations.json`. One human source can support a narrowly scoped
tentative convention; if scope is unclear, the skill asks Keep as tentative /
Omit / Clarify instead of automatically discarding the comment. Source IDs must
refer to confirmed HUMAN comments with unchanged fingerprints. Python rejects AI, uncertain, or stale evidence.

For equivalent new wording, the agent sets `merge_into` to the existing stable ID,
for example HRL-001. Python preserves the old statement, appends supported
refinements, unions tags/checks/source references, and allocates IDs only to new
rules. Repeated inputs do not duplicate rules or sources. An empty observation
list preserves the previous knowledge and revision. Contradictions stop the merge
and require explicit resolution. Arbitrary older Markdown is retained verbatim
as legacy knowledge instead of being discarded.

Example **schema only** (replace every placeholder with actual human evidence):

```json
[
  {
    "title": "A principle supported by this repository's feedback",
    "tags": ["testing"],
    "rule": "A reusable instruction supported by the comment",
    "why": "The source-supported rationale",
    "checks": ["A concrete question for future reviewers"],
    "source_ids": ["inline_review:ACTUAL_ID"],
    "merge_into": "HRL-001"
  }
]
```

Omit `merge_into` for genuinely new rules. Do not use example content as extracted
knowledge. Python supplies deterministic validation, not semantic inference.

Every HUMAN comment not cited in observations must be accounted for in
`extraction_report.json`. Each entry contains its comment_id, the current
classification fingerprint, decision (`omit` or `already_covered`), and a
content-specific reason. Missing or stale explanations block build. Human
confirmation alone does not turn release announcements into engineering rules.
A zero-rule result reports the HUMAN count and omission reasons rather than
claiming that no human feedback was identified.

After the agent produces this file:

```bash
.venv/bin/python scripts/workflow.py build --repo "$R"
# Inspect the generated Markdown and pending revision before saving.
.venv/bin/python scripts/storage.py save --repo "$R" --provider "$PROVIDER" --record "$D/pending.json"
.venv/bin/python scripts/storage.py get --repo "$R" --provider "$PROVIDER"
.venv/bin/python scripts/storage.py verify --repo "$R" --provider "$PROVIDER" --record "$D/pending.json"
```

No confirmed usable human comments means no fabricated rules. Existing knowledge
is preserved, and a first empty run does not generate or upload a document. When
there is no record or newly generated pending revision, skip cloud save/verify;
a missing object is not a verification failure for an empty learning result.

### Save a Markdown file manually

```bash
.venv/bin/python scripts/storage.py save \
  --repo "$R" --file "$D/review_knowledge.md" --provider "$PROVIDER"
```

For an existing record this direct command requires its Markdown to remain
verbatim within the new file, preventing accidental destruction of accumulated
knowledge. Use the skill's structured merge for semantic changes. The command
saves an exact `pending.json` alongside the Markdown before writing.

### Cloud conflicts and retry

Every save preflights the selected provider, uploads the logical JSON record,
and downloads it for full content verification. No other cloud is accessed. A blob contains repo_id, URL, knowledge_version, timestamp,
processed window, counts, Markdown, and compact structured rules with evidence.
Raw comments remain local. HRL applies a 10 MiB serialized JSON limit as an
application memory/size guard for this small demo. It is independent of cloud
object size limits and replaces the earlier database item limit. Larger knowledge
is supported up to this guard; oversized blobs fail before uploading.

Every save opens with a boxed welcome banner and displays provider/bucket
configuration. Prominent section headings and 🔄 / ✅ / ❌ indicators make
progress visible during a presentation. A boxed completion summary appears only
after successful read-back verification. Every save uses timestamped INFO/ERROR events with clear Demo and BlobStore
components. Four numbered stages show cloud preflight, Markdown preparation,
upload, and read-back verification. The logs name the real `BucketClient.upload()`
and `BucketClient.download()` calls. Indented details show destination, readable
sizes, revision, operation duration, verified Markdown checksum and file counts.
Logs contain operation summaries, without full review bodies or credentials.

Abbreviated illustrative output:

```text
12:00:00.000 INFO  Demo       [STEP 3/4] Upload knowledge | destination 1/1 | provider=aws
12:00:00.000 INFO  BlobStore  [WRITE] [AWS S3] Uploading knowledge through BucketClient.upload()
12:00:00.300 INFO  BlobStore  [WRITE OK] [AWS S3] Uploaded knowledge successfully.
    Files uploaded : 1/1
    Elapsed        : 0.300 s
12:00:00.300 INFO  Demo       [STEP 4/4] Read back and verify the uploaded knowledge
12:00:00.300 INFO  BlobStore  [READ] [AWS S3] Downloading knowledge through BucketClient.download()
12:00:00.600 INFO  BlobStore  [VERIFIED] [AWS S3] Markdown and full JSON content match the source.
12:00:00.601 INFO  Demo       [PROCESS COMPLETE] Demo completed successfully.
    Files uploaded : 1/1
    Files read back: 1/1
    Files verified : 1/1
    Elapsed        : 0.601 s
```

The Markdown is embedded in one JSON object. An upload or read-back failure prints
ERROR / `PROCESS FAILED`; upload success followed by a failed read never reports
a completed demo. See [the demo guide](docs/DEMO.md) for the fuller log sequence.

GCS operations print the same stages with `[GCP GCS]` and `gs://` locations.
Console output contains these human-readable logs. For machine-readable JSON,
use `storage.py get --output PATH` to write a clean JSON file.

For a single-provider run, missing knowledge starts from local accumulated
knowledge when available. Selected-cloud credentials or bucket errors block
writing; another cloud's configuration has no effect. A changed baseline blocks
overwrites. Failures preserve the Markdown and pending revision; retry the same
`--record` with the selected `--provider`.

`verify --provider aws` (or gcp) checks that a valid record can be downloaded.
Add `--record PATH/pending.json` to compare it against the exact expected record.
A single-provider check never claims cross-cloud equivalence.

### Optional explicit multi-cloud comparison

The primary demo changes only --provider between runs. For optional comparison,
first deploy the same pending record separately to both providers, then run:

```bash
.venv/bin/python scripts/storage.py save --repo "$R" --provider aws --record "$D/pending.json"
.venv/bin/python scripts/storage.py save --repo "$R" --provider gcp --record "$D/pending.json"
.venv/bin/python scripts/storage.py verify --repo "$R" --providers aws,gcp
```

`--providers aws,gcp` is an explicit optional mode for operations that access both
clouds; it is mutually exclusive with --provider. `sync --providers aws,gcp` can
repair a missing copy after inspection. Different existing records stop
comparison/sync rather than selecting a winner. This mode retains partial-failure
reporting and exact-record retry support. It is never selected by default.

The application assumes one writer at a time. Preflight detects changed baselines,
but there is no distributed transaction or conditional write protecting the
interval between read and upload.

## Tests and validation

```bash
.venv/bin/python -m pytest
.venv/bin/pip check
```

Tests need no cloud or GitHub credentials. They exercise pagination, old PRs with
recent comments, timestamp filtering, duplicate IDs, empty data, API failures,
AI markers, same-account mixed provenance, manual cache persistence/invalidation,
explicit skips versus unanswered input, mandatory provenance confirmation,
native-answer persistence, omission explanations, single-source tentative
guidance, evidence validation, stable merge IDs, source deduplication, preservation,
real SDK constructor configuration, upload/download with autospecced BucketClient mocks,
read-back failures, missing objects/buckets, invalid JSON, conflicts, partial writes,
stale baselines, larger knowledge, demo progress logs, and single-provider
isolation with the same source and command workflow.
SDK packages must be installed, but no native cloud calls occur in the tests.

For live integration, configure the destinations and run the save/get/verify
commands above with real confirmed human knowledge. No cloud integration test is
claimed merely because the mocked tests pass. See [validation report](docs/VALIDATION.md)
for what actually ran during implementation.

## Files

```text
.claude/skills/learn-reviews/SKILL.md -> canonical agent skill
.agents/skills/learn-reviews/SKILL.md   extraction and semantic merge workflow
hrl/github_reviews.py                complete GitHub collector
hrl/classification.py                provenance and manual cache
hrl/knowledge.py                     evidence validation and merge/render
hrl/multicloud_store.py              ONE provider-neutral BlobStore adapter
examples/review_knowledge.demo.md    committed, synthetic storage-demo input
examples/review_bundle/              synthetic nested review context for directory transfers
hrl/directory_demo.py                native SDK directory upload/download/verification
docs/DEMO.md                        provider-parameter demo runbook
hrl/cli.py, hrl/io.py                 manual command/file helpers
scripts/fetch_reviews.py             collector entry point
scripts/workflow.py                  classify/build entry point
scripts/storage.py                   save/get/verify/sync entry point
tests/                               credential-free pytest suite
docs/                                SDK investigation and validation
output/                              ignored local artifacts
config.example.toml, .env.example     configuration templates
```

Current limits: provenance often requires a person; semantic merging depends on
the agent's judgment; GitHub history collection can cost many API calls; cloud
updates are sequential; large knowledge documents must be compacted; one writer
at a time is assumed. Useful next steps are incremental collection checkpoints,
a labeled provenance benchmark, and better conflict resolution. They are outside
this MVP. Apache-2.0; see LICENSE.
