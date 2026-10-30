# Validation performed

Repository: /Users/barry.liu/workspace/human-review-learning
Private remote: https://git.soma.salesforce.com/chameleon/human-review-learning

## BlobStore migration

- Verified upstream SDK HEAD: 550ba3babfaefe68aaaa340f59bbfda77d123398.
- Installed actual source BlobStore packages (version 0.1.9) editable in the
  isolated environment. Replaced database operations with BucketClient uploads,
  downloads and bucket existence checks. SDK sources remain untouched. Obsolete DocStore distributions and
  google-cloud-firestore were uninstalled before the passing test run.
- `.venv/bin/python -m pytest -q`: **147 passed** including separate SDK operations, native directory transfers and presenter controls.
- Tests include conservative classification, evidence validation, semantic merge
  orchestration, stable IDs, preservation, duplicate source prevention, pagination,
  old PRs with recent feedback, and the existing end-to-end controlled fixture.
- BlobStore tests autospec the actual BucketClient; exercise identical JSON
  round trips, provider configuration, safe deterministic keys, missing objects,
  missing/inaccessible buckets, invalid JSON/repository mismatch, size guards,
  knowledge larger than the former document limit, read-back mismatch, partial
  writes, stale baselines, retry/idempotency, and visible demo progress logs.
- `.venv/bin/pip check`: **No broken requirements found**. Python compilation
  and the storage CLI help smoke check passed. The controlled end-to-end test
  was also run with `-s`, showing the S3/GCS read/write/read-back logs.
- Synthetic fixtures are test data, not a claim of actual human provenance or
  successful live cloud writes.

## Prior GitHub collection validation

GitHub authentication and live collection were verified for the SDK fork and
salesforce/multicloud-py over a 30-day window during initial implementation.
Both exports contained zero comments in that window. Classification/build
preserved the empty result without inventing knowledge. Generated exports remain
ignored in output/ and are not published.

## Remaining live validation

No live S3/GCS integration tests or uploads are claimed. The demo now needs S3
and GCS bucket names, valid cloud credentials, and runtime bucket/object access.
No cloud resources are provisioned by HRL. Configure the buckets and follow the
README save/get/verify walkthrough with actual confirmed human knowledge.

The shared Claude Code/Codex skill remains agent-driven and has not been executed
inside a separate Claude Code session here. Its instructions now reference blob
storage and require the demo's read/write logs to remain visible.

## Mandatory provenance confirmation fix

The reported Claude Code run skipped nine UNCERTAIN conversation candidates
because they appeared non-actionable. The revised skill requires all provenance
answers before relevance filtering and pauses when interaction is unavailable.
The Python build now rejects unresolved questions and unexplained omissions of
confirmed HUMAN feedback. Native answers persist through workflow confirm;
terminal EOF remains pending instead of being recorded as a manual Skip.

Regression tests reproduce empty-extraction bypasses (including notices), explicit
Skip versus unasked input, changed comments, selected/batch answers, the real CLI,
stale omission explanations, a single-source tentative convention, and total
scanned PR count versus PRs with feedback. Read-only agent scenario checks covered
the nine-comment transcript scenario before and after the skill revision. The
revised interpretation asks every provenance question, pauses without interaction,
allows scoped tentative guidance, and avoids cloud verify for an empty result.
No real developer answers were invented or applied to repository artifacts, and
no live Claude Code/cloud learning run is claimed by these regression checks.

## Repository URL input

All CLI commands and the collector normalize HTTPS GitHub repository homepage
URLs to owner/name before selecting endpoints, output directories or storage keys.
Tests cover salesforce/multicloudj as a separate target from the installed Python
SDK, trailing slashes and .git, README query/fragment links, invalid hosts/paths,
credential-bearing URLs, and consistent collector/CLI/storage identities. These
are mocked regression checks. A read-only GitHub repository metadata request
confirmed access to salesforce/multicloudj. A skill scenario check confirmed that
URL input selects the Java repository and keeps Python-SDK artifacts separate.
A full live review-history scan of multicloudj is not claimed.

## One source code, runtime provider selection

Both save/get/verify paths run through the same CLI, Store and BucketClient calls.
Tests run the same application command for aws and gcp and reject any attempt to
connect to the other cloud. A selector is mandatory; --provider and --providers
are mutually exclusive. Single-cloud verification checks readability or compares
the supplied expected record and never claims cross-cloud equivalence. Tests also
cover selected-cloud failure messages and identical upload bytes from the exact
same pending.json deployed separately to each provider.

The Java reference's substrate-agnostic-storage branch, README, SubstrateConfig
and BlobStoreService were inspected through GitHub. The shared skill was updated
to select one provider before cloud access. Static synthetic input is committed
under examples/ for reproducible demos; generated pending files stay ignored.
These checks do not claim new live uploads or infrastructure deployments.

A read-only skill scenario check confirmed that --provider aws does not permit
GCP access, missing GCP credentials do not block it, omitted provider selection
requires an AWS/GCP question before cloud access, and provenance confirmations
remain mandatory. The scenario check did not perform live operations.

## Storage demo narration

Regression tests exercise AWS and GCP through the actual SDK client interface
with mocked storage. They assert process start, input filename, upload and read
counts, named SDK operations, upload-before-read-back ordering, and completion
only after content verification. Upload errors never claim upload success; read
errors and mismatches preserve the upload success message but report zero verified
files and process failure. No live cloud uploads were performed for this change.

## Short demo command

Nine regression cases cover sample defaults on AWS/GCP, custom relative Markdown
paths and repository keys, default config/sample resolution from another working
directory, get without uploading, exact pending-record retries, mandatory provider
selection, read-back failure status, and the executable launcher's help command
from outside the checkout. Storage tests mock the actual SDK interface; launcher
help does not connect to cloud services. No live cloud writes are claimed.
The Java reference main and substrate-agnostic-storage READMEs were cross-checked
for the short CLI syntax and provider selection approach.

## Presentation logging

Cross-checked the reference branch's logback.xml, BlobStoreService and orchestration
logs. HRL now prints timestamps, log levels and components, numbered stages,
human-readable sizes, operation durations, verified Markdown SHA-256 and a final
readable count summary. New regression cases exercise AWS/GCP stage ordering,
checksums derived independently from input bytes, timing fields and ERROR output
on failed uploads. Existing upload/read-back error and mismatch cases remain.

Live follow-up: `./demo --provider gcp` successfully uploaded the unchanged
synthetic sample to `gs://pr-review-content/review_knowledge/demo%2Fhuman-review-learning.json`
and downloaded it through the SDK. Revision remained 1, JSON payload was 14,385
bytes, and Markdown was 6,883 bytes. The run reported 1/1 uploaded, read back and
verified; measured upload was 0.321 s, read-back 0.161 s, total 12.555 s including
initialization and preflight. This follow-up supersedes the earlier no-live-upload
status for this demo path; it does not validate human-review extraction or AWS.

## Full visual demo

AWS/GCP regression cases check configuration visibility, boxed banners, distinct
upload/read-back sections and success only after verification. An upload failure
shows an error indicator and never prints the successful completion banner.
The default command remains automatic and uses the same SDK upload/download calls.

The full visual `./demo --provider gcp` run also passed against pr-review-content:
1 file uploaded, read back and verified; upload 0.310 s, download 0.144 s, total
12.575 s. The complete live output is retained locally in ignored
output/demo--human-review-learning/demo-gcp.log. The synthetic sample remained at
revision 1 and its verified content was unchanged. This run did not access AWS.

## Presenter confirmation before each step

Nine new regression cases test stopping independently before each of four stages,
including no preparation-file write before step 2, no upload before step 3 and no
read-back before step 4. Further cases cover all-yes execution, empty/EOF input,
invalid-answer retries and explicit --yes unattended execution. Stopping after
upload preserves the blob and pending revision, reports not verified, skips the
success banner and returns 130. Tests use controlled SDK doubles and do not
supply invented approvals to a live cloud run. No new live upload was performed
for the interactive controls.

## Review bundle directory demo

Fifteen new regression cases exercise native async SDK interfaces on AWS/GCP,
nested three-file round trips, partial upload/download results, missing/extra
files, byte mismatches, cancellation at all four stages, symlink rejection,
optional UUID-scoped cleanup, cancelled cleanup and leftover-object detection.
Existing tests also protect the DOWNLOAD EXISTING KNOWLEDGE section title.

A live GCP run uploaded three synthetic files (1,448 bytes), downloaded them into
a fresh folder and verified every relative path and SHA-256. The SDK returned
3/3 uploads and downloads with zero failed transfers. Upload took 2.535 s, download
2.060 s and the full demo 5.889 s. The prefix was
review_bundles/demo%2Fhuman-review-learning/c175c739b6544544aa7e17b30b6efb19/.
The complete local printout is ignored at
output/demo--human-review-learning/demo-directory-gcp.log. Live deletion and AWS
directory transfers were not performed; those paths were checked with SDK doubles.

The virtual environment includes both SDK async provider extras and pip check
passes. Source SDK commit remains 550ba3babfaefe68aaaa340f59bbfda77d123398, clean
and unmodified. Resolved third-party requirements are recorded in requirements.txt.

## Four separate SDK operation commands

Thirteen regression cases exercise independent single-file and directory uploads
and downloads for AWS/GCP, exact SDK call boundaries, upload-only default behavior,
missing manifests, content corruption, refused prompts, failed-upload manifest
preservation, wrong-bucket downloads and malicious manifest paths. Existing save
round-trip tests explicitly select the advanced save workflow.

Four actual GCP commands were run separately with --yes against pr-review-content:

- upload: 1 Markdown file, 6,883 bytes; SDK upload 0.755 s.
- download: 1 file saved and SHA-256 verified; SDK download 0.582 s.
- upload-directory: 3 files, 1,448 bytes; SDK directory upload 2.147 s, zero failures.
- download-directory: 3 files restored and checksum verified; SDK directory
  download 2.459 s, zero failures.

Single key: demo_artifacts/demo%2Fhuman-review-learning/b056662e09b54e63b443aa2ecf48756d/review_knowledge.demo.md.
Directory prefix: demo_artifacts/demo%2Fhuman-review-learning/9c734e3214db497680725eb578394f9c/.

Complete logs are local and ignored under
output/demo--human-review-learning/preview/{single-upload,single-download,directory-upload,directory-download}.log.
These uploads/downloads were actual SDK calls, distinct from the mocked regression
checks. No AWS calls or deletion were performed for this validation.

## One-command full demo

Ten regression cases cover implicit/default and explicit all mode on AWS/GCP,
exact four-operation ordering, selected-provider isolation, correct section
headings and stage prompts, stopping before each of the four operations, immediate
stop on a download error and rejection of a user-provided manifest in full mode.
The old upload-only-default test was superseded; individual operation tests remain.
The full demo passes each exact upload manifest into the paired download and
prints the overall success banner only after all four operations pass.

The corrected full-command GCP capture also passed: ./demo --provider gcp --yes
ran four distinct SDK operations against pr-review-content, verified the one-file
and three-file downloads against their own upload manifests, and printed 4/4
operations completed. Total elapsed time was 7.805 s. The local ignored preview is
output/demo--human-review-learning/preview/full-demo.md. No AWS operations or
deletes were performed for this follow-up.
