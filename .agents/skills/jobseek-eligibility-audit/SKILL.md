---
name: jobseek-eligibility-audit
description: Independently audit exceptional JobSeek eligibility cases when an explicit audit trigger is recorded. Do not use for ordinary candidates.
---

# JobSeek Exception Eligibility Audit

Read root `AGENTS.md`, triggered compact packets, authority registry, and identified defect only. Do not redo discovery. Reopen a full advertisement only for missing, conflicting, suspicious, changed, or threshold-material evidence.

Audit only recorded triggers: missing/conflicting/suspicious evidence, near-threshold conclusion, material supported inference, disputed exclusion/blocker, sensitive declaration, deterministic inconsistency, or explicit lead request. Referee classification has one shared reducer for packet validation and effective state. `current_supervisor_mandatory` remains `Needs Review` whenever either `alternative_permitted` or `authoritative_availability` is `unknown`, until the current audit generation explicitly resolves `referee-ambiguity`. Fixed combinations such as `mandatory_current_supervisor_unavailable` are decided by `jobseekctl`, not reinterpreted.

Record the result through `jobseekctl record-eligibility-audit` as
`pass|pass_with_warnings|fail`, with evidence and the permitted mechanical
outcome. The command appends an immutable resolution overlay and produces the
legal next state; never overwrite the original packet. `pass` may produce
`Eligible`, `pass_with_warnings` may produce `Eligible` or remain
`Needs Review`, and `fail` may produce `Skipped`, `Needs Review`, or `Blocked`.
Name every resolved `reason_id`, unknown hard-exclusion rule, unresolved item, or
standard blocker explicitly. A later reducer clears only those named targets.
No result may make a job Eligible while another review or blocker remains.

Every trigger has an immutable `trigger_id` and monotonic trigger version. The
current trigger set is the stable union of packet-native triggers and recorded
event triggers. An audit records the exact union it covers; the eligibility gate
stores that same trigger set/version. A new trigger, new evidence for a resolved
trigger, or packet/evidence hash change invalidates older gates until a new audit
covers all current unresolved triggers. Partial, failed, or unresolved audits
cannot open materials or submission.

Only the latest audit resolution covering the complete current trigger generation
is effective. It supersedes older audit overlays rather than unioning them
indefinitely. After new or conflicting evidence, explicitly restate every hard
rule, blocker, review reason, or unresolved item that remains resolved; omit any
prior resolution that the new evidence reopens. `fail -> Needs Review` is the
required correction path when the latest evidence no longer supports eligibility.

Write only the assigned batch report and audit events. Do not manufacture facts,
alter scores or claims, browse forms, prepare materials, read private details,
modify control/authoritative files, or create/delegate to another agent. Return
only the global structured worker fields.
