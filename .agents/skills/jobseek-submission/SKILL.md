---
name: jobseek-submission
description: Fill one application, write its exact review, pause for user approval, validate the approval, submit once, and record confirmation.
---

# Submission

Read root `AGENTS.md`, the batch snapshot, current job files, and final materials. Do not alter materials or read `private/`. The user manually handles any sensitive upload.

Fill the current application truthfully. Before the final Submit, Apply, or Send action, write `submission/review.json` with `job_id`, `page_url`, non-empty `page_fingerprint`, `answers` object, `declarations` array, non-empty `selected_attachments` array containing a CV, and offset-aware `reviewed_at` in `Australia/Perth`. Attachment paths must be unique, existing relative paths inside the job directory. Stop and return control to the lead.

Immediately before the final click, run `python tools/jobseek.py check-approval --batch <batch-id> --job <job-id>`. Continue only when it returns `allowed: true`; any review or attachment change requires a new review and user approval.

After the click, immediately write `submission/confirmation.json` with the approved `review_hash`, offset-aware `submitted_at` in the workspace timezone, and status `confirmed`, `not_submitted`, or `unclear`. Write `unclear` before further inspection when the result is uncertain. The confirmation consumes that approval for every status. Later update the same unclear confirmation to `confirmed` or `not_submitted`; never click again with the same approval. Use optional `reason_code: "submission_failure"` only for an actual submission failure, and optional `manual_takeover: true` only when a manual takeover occurred.

Do not archive or delegate.
