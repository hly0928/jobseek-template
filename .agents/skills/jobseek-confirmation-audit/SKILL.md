---
name: jobseek-confirmation-audit
description: Independently audit JobSeek confirmation only when recorded evidence is missing, ambiguous, inconsistent, conflicting, timed out, abnormal, or fails deterministic validation.
---

# JobSeek Exception Confirmation Audit

Read root `AGENTS.md`, the compact submitted-role identity, recorded confirmation assessment, and relevant evidence only. Do not use private data, reopen the advertisement unless identity evidence is deficient, alter materials, submit, or resubmit.

Verify correct employer, role, successful submission, and required
identifier/state for the current `submission_attempt_id`. Reject evidence from
older attempts and wrong screenshots; preserve directly observed text and
limitations. Record exactly one structured current result with
`record-confirmation-audit`: `verified`, `not_submitted`, or `unresolved`.
`verified` records the attempt-bound gate; `not_submitted` mechanically enters
`Failed`; `unresolved` remains paused and may later be superseded for the same
attempt. No submission or normal unambiguous confirmation means no audit call.

Do not modify control/authoritative files or create/delegate to another agent. Return only the global structured worker fields.
