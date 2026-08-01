---
name: jobseek-submission
description: Prepare, pause for per-job human review and approval, submit the exact approved application through authenticated Chrome, and verify confirmation.
---

# JobSeek Submission

Read root `AGENTS.md`, the batch snapshot, compact packet/advertisement summary, and approved material checklist. Use the authenticated Chrome profile and reconfirm active status, duplicate status, employer/role/package match, required audit pass if triggered, and no unresolved questions.

Claim submission ownership through `jobseekctl`. Email, phone, and other ordinary candidate/contact facts in the batch Candidate Profile or CV may be used directly. Never open or preload `Profile/Private_Details.md`; `jobseekctl private-field` intentionally fails closed because returning a sensitive value would expose it. Ask the user to enter any truly sensitive mandatory value manually. Never persist it or automatically upload identity, visa, licence, police, banking, tax, or medical documents.

Stop for medical/criminal questions, referee requests not already deterministically blocked, identity documents, video, assessment, CAPTCHA, unusual declarations, unsupported commitments/availability/factual answers, login/password/code, or manual takeover. A prior continue decision for an experience gap does not authorise a favourable factual response.

Before the final click, ordinary new review reasons are pre-submit only. Record
them through `record-review-reason`, which re-reads the latest state under the
events lock and returns the job to `Needs Review`. If the attempt is already
`Submitted` or in its post-submit recovery state, do not add a pre-submit reason;
record confirmation evidence and use confirmation audit for that same attempt.

When submission exposes a new factual answer, document, declaration, or genuine
choice, record a distinct reason with `record-review-reason` and return the job
to `Needs Review`. Use `remain_paused` when no answer is available yet. Resolve
only that reason after recorded non-sensitive evidence is supplied; the reducer
must leave every other reason and blocker paused.

For SEEK career history, never add, relabel, or present Uber Eats or other delivery activity as employment. Select `I am new to the workforce` only when an authoritative fact explicitly supports that declaration; otherwise return `Needs Review`.

Fill and prepare, then transition to `Awaiting User Review`. Every entry creates a
new `submission_review_cycle_id`. Record the current job URL/page fingerprint,
complete answers, attachments, declarations hash, and review evidence with
`record-submission-review`. This creates a unique `submission_attempt_id`; review,
approval, submission evidence, and `Submitted` must all bind that attempt and the
current review cycle. A new review cycle supersedes every earlier review and
approval. Pause with the final action untouched so the user can inspect the live
page. Only the root lead may record that user's explicit, single-job approval. No
prior, batch, inferred, or earlier-cycle approval is valid.

After approval, revalidate that the page, answers, attachment bytes, declarations, and job identity are unchanged. Any material change or unresolved review reason requires a new review cycle and approval. Only then may the lead transition to `Submission Ready`; immediately before the final click, `submission_evidence` and the locked transition to `Submitted` re-read the latest job state and verify the current review cycle, approval, page/answer/attachment/declaration evidence hashes, and that no unresolved review or audit item has appeared. Entering `Submitted` consumes the approval. After `Submitted → Failed`, return to `Awaiting User Review`, create a new attempt, record the current page and materials again, and obtain a new approval. Never reuse the old attempt or click a final `Submit`, `Apply`, or `Send` without the current gate.

Every submitted attempt remains open and counted until confirmation records
`verified` or `not_submitted`; while any attempt is open, no second submit attempt
may be created. If a legacy batch contains `Submitted → Blocked`, treat it as a post-submit
confirmation-pending state, not an ordinary blocker. Keep the same
`submission_attempt_id`, review, approval, and submission evidence; continue
confirmation assessment/audit for that attempt. Only `verified` may reach
`Submission Verified`, and only `not_submitted` may reach `Failed` and start a
new attempt. It must never return to assessment. An `unresolved` result pauses and
cannot complete or finalize.

Write only batch-local evidence and validated events. Use `record-confirmation`
after the click; it binds the assessment and any audit trigger to the current
`submission_attempt_id`. Unambiguous correct identity, success, and identifier
may proceed to `Submission Verified`. Any uncertainty routes to confirmation
audit and never a blind retry. Only a structured `not_submitted` audit result may
enter `Failed`; historical attempt evidence cannot validate or block the current
attempt. Shared Tracker/log/archive outputs are regenerated only after
verification. If the frozen consecutive submission-failure limit is reached, do
not create another attempt merely to make the batch terminal. The lead records
explicit evidence with `terminalize-failure-limit`, which closes the affected
failed jobs as terminal `Blocked` and permits normal batch finalization.

Do not modify materials, control/authoritative files, or create/delegate to another agent. Return only the global structured worker fields.
