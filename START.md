# Start Here

## 1. Prepare your files

Replace the placeholder content in:

- `profile/candidate-profile.md`
- `profile/banks/application-answers.md`
- `profile/banks/cover-letter-content.md`
- `tracks/it/profile.md`
- `tracks/it/search-criteria.md`
- `tracks/it/answer-overrides.md`
- `tracks/part-time/profile.md`
- `tracks/part-time/search-criteria.md`
- `tracks/part-time/answer-overrides.md`

Add your own readable Word CV at `profile/cv/base.docx`. The file is ignored and must not be copied from another person's workspace. Add master CVs locally only if useful.

Do not put identity, visa, police, banking, medical, licence, or similar evidence in profile files. Keep it under ignored `private/evidence/`; workers do not read that directory and sensitive uploads are manual.

## 2. Configure tracks and limits

Review `config/workspace.json` before the first run:

- track names and directories;
- eligible threshold and score components;
- hard and track-specific exclusions;
- discovery stop conditions;
- history and archive paths;
- authoritative timezone.

The shipped defaults stop at 20 fully assessed new ads, 5 confirmed submissions, 3 explicit submission failures, or 2 manual takeovers. The default timezone is `Australia/Perth`; change it before creating the first batch if needed.

## 3. Validate the workspace

Run:

```sh
python3 -m unittest discover -s tests -v
python3 tools/jobseek.py rebuild-index
python3 tools/jobseek.py preflight --track it
```

Preflight should fail clearly until placeholders are replaced and `profile/cv/base.docx` exists. Fix the stated inputs; do not weaken validation.

## 4. Start one batch

Only one batch may be active. `new-batch` checks every `batch.json`, refuses to run while one is active, and creates `status: "active"` with `completed_at: null`. After preflight passes:

```sh
python3 tools/jobseek.py new-batch --track it
python3 tools/jobseek.py status --batch <batch-id>
```

The normal sequence is:

1. preflight;
2. create one batch;
3. bounded discovery with `jobseek_discovery_assess`;
4. merge every worker output, run `status`, and report every `priority_jobs` entry with its outcome, title, company, source, current status, reasons, unresolved items, and canonical link;
5. optional exceptional audit with `jobseek_audit`;
6. materials with `jobseek_materials` for Eligible jobs without unresolved items;
7. form filling and review with `jobseek_submission`;
8. explicit human approval of the current version;
9. one final submission action;
10. immediate confirmation recording;
11. archive confirmed applications;
12. rebuild and validate the reviewed-URL index;
13. run `complete-batch` to record `status: "completed"` and an offset-aware `completed_at`;
14. only then create the next batch.

Before each discovery assignment, run `status`. Every scope must specify source/site, query or role category, location, page/result range or maximum full opens, and remaining assessment capacity. Do not assign discovery after a configured stop threshold.

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
- run preflight to validate history/index consistency;
- report any remaining unresolved item to the user.
- run `python3 tools/jobseek.py complete-batch --batch <batch-id>`.

`Skipped`, `Blocked`, `Expired`, `Withdrawn`, and a `Needs Review` job the user abandons are final working outcomes. Not every job must be submitted. Completed batches are read-only.

## Common prompts

### First setup check

```text
Inspect this JobSeek template for first use. Do not create a batch. Tell me which placeholder candidate, CV, track, configuration, or privacy inputs must be completed before preflight can pass.
```

### Start a new batch

```text
Run preflight for the <track> track. If it passes, create a new batch; the command must confirm it is the unique active batch. Then use the named discovery-assess subagent for bounded discovery scopes. Do not perform discovery or assessment in the root thread. Follow the configured stop conditions and report every Eligible and Needs Review result with its information and canonical link before preparing any application materials.
```

### Resume the current batch

```text
Resume the current batch. Inspect its files and status first. Do not create a new batch. Delegate each remaining operational task to the matching named subagent, and tell me what requires my review or decision.
```

### Discovery only

```text
Continue discovery for the current active batch only. Check status before spawning workers, assign bounded non-overlapping scopes, and use only the jobseek_discovery_assess subagent. Stop when a configured threshold or the assigned scopes are exhausted. Merge all worker outputs when they finish, run status, and report every priority_jobs entry without omission.
```

### Prepare materials

```text
For the eligible jobs in the current batch that have no unresolved issues, use the jobseek_materials subagent to prepare the required application materials. Do not fill or submit application forms yet.
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
Complete the current batch without creating another one. Ensure all discovery outputs are merged, intended jobs have clear outcomes, confirmed applications are archived, and the reviewed URL index is rebuilt and validated. Report any remaining unresolved items, then run complete-batch so batch.json records the completed state and timestamp.
```

## Troubleshooting

- **Placeholder failure:** replace the named placeholder with verified content.
- **Missing base CV:** add a readable `profile/cv/base.docx`; never use another person's CV.
- **Stale index:** run `python3 tools/jobseek.py rebuild-index`, then preflight again.
- **Historical duplicate:** do not reopen it; merge reports the snapshot match.
- **Stop threshold reached:** stop discovery and work only on current jobs or batch closeout.
- **Approval invalid:** regenerate review after any page, answer, declaration, attachment, or material change and obtain new approval.
- **Unclear submission:** do not click again; use exceptional audit or human inspection.
- **Private evidence:** keep it ignored and upload it manually only when required.
