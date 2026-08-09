# Start Here

Subagent routing is fixed by `.codex`: Terra / medium by default; Luna / max for discovery and ordinary assessment; Sol / medium for exceptional audit and application materials; and inherited Terra / medium for submission.

## 1. Prepare your files

Replace the placeholder content in:

- `profile/candidate-profile.md`
- `profile/banks/application-answers.md`
- `profile/banks/cover-letter-content.md`
- `profile/cv/strategies/*.md` when useful (optional guidance only; do not put candidate facts here)
- `tracks/it/profile.md`
- `tracks/it/search-criteria.md`
- `tracks/it/answer-overrides.md`
- `tracks/part-time/profile.md`
- `tracks/part-time/search-criteria.md`
- `tracks/part-time/answer-overrides.md`

Add one complete readable Word CV at `profile/cv/base.docx`. It is ignored and must not be copied from another person's workspace. It is the only active general CV and serves as both an authoritative content/evidence source and the tailored CV's visual/format template. Master CVs are outside the active workflow; legacy copies must never be used or snapshotted.

Declare the canonical candidate application email in the explicit application-email field in `profile/candidate-profile.md`, and include it in the base CV. Recruiter, referee, example, and other third-party addresses are not candidate-email conflicts. In the referee policy, allow a CV to say `References available upon request.`, require review when a form mandates unverified specific referee details, and forbid invented referee names, positions, phone numbers or email addresses.

Do not put identity, visa, police, banking, medical, licence, or similar evidence in profile files. Keep it under ignored `private/evidence/`; workers do not read that directory and sensitive uploads are manual.

## 2. Configure tracks and limits

Review `config/workspace.json` before the first run:

- track names and directories;
- advisory 0–100 score components;
- hard and track-specific exclusions;
- discovery stop conditions;
- history and archive paths;
- authoritative timezone.

The shipped defaults stop new discovery assignments at 20 fully assessed new ads, 5 confirmed submissions, 3 explicit submission failures, or 2 manual takeovers. Completed worker results are still merged and small concurrent overshoot is acceptable. Scores rank opportunities but never determine eligibility. The default timezone is `Australia/Perth`; change it before creating the first batch if needed.

## 3. Validate the workspace

Run:

```sh
python3 -m unittest discover -s tests -v
python3 tools/jobseek.py rebuild-index
python3 tools/jobseek.py preflight --track it
```

Replace every placeholder yourself before running. Preflight verifies required inputs, structural integrity, provenance-related configuration, email consistency, history/index consistency, and archive safety; it does not interpret natural-language completeness. It fails until `profile/cv/base.docx` exists.

## 4. Start one batch

Only one batch may be active. `new-batch` checks every `batch.json`, refuses to run while one is active, and creates `status: "active"` with `completed_at: null`. After preflight passes:

```sh
python3 tools/jobseek.py new-batch --track it
python3 tools/jobseek.py status --batch <batch-id>
python3 tools/jobseek.py materials-inputs --batch <batch-id> --job <job-id>
```

`new-batch` freezes every discovery and materials input into `snapshot/` and records source paths, roles and SHA-256 hashes in `snapshot/manifest.json`. Later live-profile edits affect only future batches; the current batch continues with its frozen snapshot.

Before `merge-discovery` persists any completed worker result, it validates that frozen manifest and every recorded hash. This requires no extra user step.

Tailored CV input is the frozen base CV + candidate profile + selected track profile + approved answer/content banks + the job advertisement, plus an applicable frozen strategy when available. To change a long-term fact, update the correct live authoritative file and run preflight; the change starts with the next batch, never by editing a completed or current snapshot.

The normal sequence is:

1. preflight;
2. create one batch;
3. bounded discovery with `jobseek_discovery_assess`;
4. merge every completed worker output even after a stop threshold, run `status`, and report every `priority_jobs` entry with its outcome, title, company, source, current status, reasons, unresolved items, score when available, and canonical link;
5. optional exceptional audit with `jobseek_audit`;
6. materials with `jobseek_materials` for Eligible jobs without unresolved items; it first runs `materials-inputs`, reads only returned frozen snapshot/job paths, uses the base CV as evidence and DOCX template, and treats any applicable strategy as optional guidance only;
7. form filling and review with `jobseek_submission`;
8. explicit human approval of the current version;
9. one final submission action;
10. immediate confirmation recording;
11. archive confirmed applications;
12. rebuild and validate the reviewed-URL index;
13. run `complete-batch` to record `status: "completed"` and an offset-aware `completed_at`;
14. only then create the next batch.

Before each discovery assignment, run `status`. Every scope must specify source/site, query or role category, location, page/result range or maximum full opens, and remaining assessment capacity. Do not assign discovery after a configured stop threshold or after the lead and user decide enough has been found. Still merge all completed worker output.

## 5. Review and approve applications

The submission agent fills one application and writes `submission/review.json`, then stops. Review its page identity, answers, declarations, attachments, material hashes, and risks.

If you approve that exact version, the root lead runs:

```sh
python3 tools/jobseek.py approve --batch <batch-id> --job <job-id>
```

Immediately before the final action, the submission agent runs:

```sh
python3 tools/jobseek.py check-approval --batch <batch-id> --job <job-id>
```

Only `allowed: true` permits one click. Any review or material change invalidates approval. After the click, write confirmation immediately. An unclear result consumes approval and must not be blindly retried.

When confirmed, archive with:

```sh
python3 tools/jobseek.py archive --batch <batch-id> --job <job-id>
```

## 6. Complete the batch

Before another `new-batch`:

- merge all output from every started discovery worker;
- plan no further discovery scopes;
- give every intended job a clear working outcome;
- archive every confirmed submission;
- run `python3 tools/jobseek.py rebuild-index`;
- report any remaining unresolved item to the user;
- run `python3 tools/jobseek.py complete-batch --batch <batch-id>`.

`complete-batch` is a simple lifecycle write against the frozen batch. It does not call live-profile preflight, so changes to live profile files after batch creation cannot block completion. `Skipped`, `Blocked`, `Expired`, `Withdrawn`, and a `Needs Review` job the user abandons are final working outcomes. Not every job must be submitted. Completed batches are read-only.

## Common prompts

### First setup check

```text
Inspect this JobSeek template for first use. Do not create a batch. Tell me which placeholder candidate, CV, track, configuration, or privacy inputs must be completed before real use; do not assume preflight semantically validates natural-language completeness.
```

### Start a new batch

```text
Run preflight for the <track> track. If it passes, create a new batch; the command must confirm it is the unique active batch. Then use the named discovery-assess subagent for bounded discovery scopes. Do not perform discovery or assessment in the root thread. Treat scores as advisory ranking information, use stop conditions only to prevent new discovery assignments, merge all completed results, and report every Eligible and Needs Review result with its information and canonical link before preparing any application materials.
```

### Resume the current batch

```text
Resume the current batch. Inspect its files and status first. Do not create a new batch. Delegate each remaining operational task to the matching named subagent, and tell me what requires my review or decision.
```

### Discovery only

```text
Continue discovery for the current active batch only. Check status before spawning workers, assign bounded non-overlapping scopes, and use only the jobseek_discovery_assess subagent. Do not assign more work when a configured threshold is reached or the lead and user decide the search is sufficient. Merge all completed worker outputs, including valid overshoot, then run status and report every priority_jobs entry without omission.
```

### Prepare materials

```text
For the eligible jobs in the current batch that have no unresolved issues, use the jobseek_materials subagent to run materials-inputs and prepare materials only from the returned frozen snapshot/job paths. Use the base CV as both evidence and DOCX template, and any applicable strategy as optional relevance and emphasis guidance. Do not fill or submit application forms yet.
```

### Fill and wait for approval

```text
Use the jobseek_submission subagent for the selected job. Fill the application, generate the review record, and stop before the final submit action. Present the important answers, declarations, attachments, and any risks for my review.
```

### Approve one job

```text
I approve the current reviewed version of <job-id> only. Record approval for that job and version, then use the submission subagent to re-check the approval and perform at most one final submission action. Report the confirmation result.
```

### Check current status

```text
Inspect the current batch and run its status command. Summarize remaining assessment capacity, stop reasons, job outcomes, confirmations, archives, and the next decisions needed. Do not create another batch.
```

### Handle unclear confirmation

```text
Use jobseek_audit to inspect the unclear confirmation without clicking submit again. Update only the current confirmation when evidence supports confirmed or not_submitted; otherwise keep it unclear and ask for human review.
```

### Complete the current batch

```text
Complete the current batch without creating another one. Merge all completed discovery outputs, give intended jobs clear outcomes, archive confirmed applications, and rebuild the reviewed URL index. Report any remaining unresolved items, then run complete-batch so batch.json records the completed state and timestamp. Do not make completion depend on current live profile files or rerun live-profile preflight as part of complete-batch.
```

## Troubleshooting

- **Placeholder content:** replace it with verified content before real use; the controller intentionally does not interpret prose as a policy DSL.
- **Missing base CV:** add a readable `profile/cv/base.docx`; never use another person's CV.
- **Email conflict:** ensure the explicit candidate-profile application email is present in the base CV and that no other explicit application-email declaration contradicts it; unrelated third-party addresses are allowed.
- **Fact conflict:** resolve authoritative live sources before a future batch, or stop the current materials step; never let a strategy decide a fact.
- **Stale index:** run `python3 tools/jobseek.py rebuild-index`, then preflight again.
- **Historical duplicate:** do not reopen it; merge reports the snapshot match.
- **Stop threshold reached:** assign no new discovery, but merge every valid result already completed.
- **Approval invalid:** regenerate review after any page, answer, declaration, attachment, or material change and obtain new approval.
- **Unclear submission:** do not click again; use exceptional audit or human inspection.
- **Private evidence:** keep it ignored and upload it manually only when required.
