# Human Review Knowledge — Synthetic Demo

> **DEMO ONLY — SYNTHETIC CONTENT**
>
> These examples were written for a demonstration. They were not extracted from
> GitHub reviews and have not been confirmed as human review feedback. The sample
> reviewer comments and source labels below are fictional; they do not refer to
> actual people, pull requests, or repository policies.

Repository key: `demo/human-review-learning`  
Prepared: 2026-10-26  
Example rules: 5

## Overview

This sample illustrates how Human Review Learning presents reusable engineering
knowledge and preserves Markdown in a portable blob. The examples cover retry
safety, exception boundaries, resource cleanup, compatibility, and tests.

Use this document for the storage portion of the demo: upload to S3 and GCS,
download each copy, display the Markdown, and verify the logical records match.
It does not demonstrate actual GitHub collection, provenance classification,
or extraction from confirmed human comments.

## Review Tags

- correctness
- retry
- error-handling
- resource-management
- backward-compatibility
- testing
- cloud-provider-consistency

## Example Review Rules

### DEMO-001: Verify Idempotency Before Retrying

**Tags:** retry, correctness

**Illustrative reviewer comment:**

> "This request creates a resource. If the response is lost, retrying could
> create a second resource. Can we use an idempotency token?"

**Rule:**

Before adding automatic retries, establish whether repeating the operation is
safe. For operations with side effects, require an appropriate idempotency
mechanism or explicit retry restrictions.

**Why:**

A timeout does not prove that the server failed to complete the first request.
Repeating an unsafe request can create duplicate resources or duplicate work.

**What AI Reviewers Should Check:**

- Does the operation change external state?
- Can the first attempt succeed even if the caller sees a timeout?
- Is an idempotency token reused across attempts?
- Are retry count, backoff, and total elapsed time bounded?

**Source:** Synthetic example DEMO-COMMENT-001. No actual PR reference.

### DEMO-002: Keep Exception Translation at the Public Client Boundary

**Tags:** error-handling, cloud-provider-consistency

**Illustrative reviewer comment:**

> "The public client already translates provider errors. Let the native failure
> reach that boundary so callers receive the common SDK exception."

**Rule:**

When the SDK contract places error translation in the public client, preserve
that boundary. Provider operations should allow native failures to propagate
unless a catch is necessary for operation control flow or cleanup.

**Why:**

A consistent translation boundary helps callers handle equivalent failures
through the same cloud-agnostic exception types.

**What AI Reviewers Should Check:**

- Is the provider catch needed for control flow or resource cleanup?
- Does the public operation preserve the original failure as its cause?
- Is request-specific normalization scoped to the operation that needs it?
- Are permission failures distinguished from missing resources?

**Source:** Synthetic example DEMO-COMMENT-002. No actual PR reference.

### DEMO-003: Close Owned Resources on Success and Failure

**Tags:** resource-management, error-handling

**Illustrative reviewer comment:**

> "The download stream is closed on success, but an exception during parsing
> leaves it open. Could we manage it with a context manager?"

**Rule:**

Make ownership explicit for streams, files, and clients. Close owned resources
on every exit path, including failures during parsing or verification.

**Why:**

Leaked connections and file handles can exhaust resources during repeated runs.
Closing resources owned by the caller can also break later operations.

**What AI Reviewers Should Check:**

- Is a context manager or finally block appropriate?
- Does cleanup run after intermediate failures?
- Does the component close only resources it owns?
- Can a cleanup error obscure the original failure?

**Source:** Synthetic example DEMO-COMMENT-003. No actual PR reference.

### DEMO-004: Preserve Public API Compatibility

**Tags:** backward-compatibility, correctness

**Illustrative reviewer comment:**

> "Existing callers omit this argument. Making it mandatory will break them;
> can the old behavior remain the default?"

**Rule:**

Review public signature changes against existing usage. Preserve documented
behavior for existing callers unless a breaking change is explicitly intended
and communicated.

**Why:**

Changes to arguments, return values, or exception behavior can disrupt users
without requiring any edits in their application code.

**What AI Reviewers Should Check:**

- Do existing calls still work with omitted optional arguments?
- Are defaults and return shapes compatible with documented behavior?
- Does an intentional breaking change include migration guidance?
- Do tests exercise representative existing callers?

**Source:** Synthetic example DEMO-COMMENT-004. No actual PR reference.

### DEMO-005: Test Failure Paths and Honest Partial Success

**Tags:** testing, error-handling, cloud-provider-consistency

**Illustrative reviewer comment:**

> "The test covers two successful uploads. What happens if S3 succeeds but the
> GCS write fails? We should retain the local file and report partial success."

**Rule:**

For workflows that update multiple destinations, test failures at each stage.
Report each destination's result, preserve retryable local artifacts, and verify
stored content before reporting full success.

**Why:**

Independent cloud writes do not form a distributed transaction. An upload
response alone does not demonstrate that both destinations contain equivalent
knowledge.

**What AI Reviewers Should Check:**

- Can one destination succeed while another fails?
- Does the final result identify the failed destination?
- Are the exact payload and application revision available for a safe retry?
- Does a read-back compare the complete logical record?
- Do demo logs distinguish upload completion from successful verification?

**Source:** Synthetic example DEMO-COMMENT-005. No actual PR reference.

## Demo Boundaries

- Store this sample under `demo/human-review-learning` to keep it separate from
  knowledge associated with a real repository.
- All reviewer comments, rule IDs, and source labels in this file are examples.
- No real review sources or measured authorship accuracy are claimed.
- The manual Markdown save stores this entire file in the `knowledge_md` field.
  It does not populate the structured `rules` list, so storage logs may show
  `rules=0` even though this Markdown contains five illustrative rules.
- A complete learning demo must separately collect real reviews, resolve
  uncertain provenance, and extract rules supported by confirmed human feedback.
