---
name: jobseek-audit
description: Resolve an exceptional eligibility issue or inspect an unclear submission confirmation and write one current conclusion.
---

# Exceptional audit

Read root `AGENTS.md`, the batch snapshot including `snapshot/assessment-policy.json`, the complete advertisement, current assessment, and the exact question assigned by the lead. Do not read root scoring configuration or `private/`.

Audit only missing, conflicting, suspicious, near-threshold, sensitive, or explicitly disputed eligibility evidence, or an unclear result after a submission. Candidate facts still come only from the batch snapshot. Do not turn personal, academic, or project activity into employment.

For eligibility, write or replace `audit.json` with `result`, current `outcome`, `resolved_items`, `remaining_items`, `summary`, and offset-aware `audited_at` in `Australia/Perth`. For confirmation, inspect without triggering another submission and update the current `submission/confirmation.json` status to `confirmed`, `not_submitted`, or `unclear` with concise evidence while preserving its `review_hash` and `submitted_at`.

Keep only the current conclusion. Do not prepare materials, submit, or delegate.
