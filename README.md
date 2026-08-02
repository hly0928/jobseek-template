# JobSeek Template

JobSeek is a human-supervised Codex workspace for bounded job discovery, truthful assessment, application preparation, exact-version approval, one final submission action, confirmation, and minimal archiving. It is not an unattended application bot.

## What it is

The workspace is file-driven. One root lead coordinates four named agents while plain JSON, JSONL, Markdown, and document files hold current work. It deliberately avoids a database or complex workflow state machine.

Only one batch may be active. `new-batch` enforces this from batch metadata. Finish its intended work, archive confirmed applications, rebuild the reviewed-URL index, validate consistency, and run `complete-batch` before creating the next batch.

## Safety model

- Candidate facts come only from verified profile/track inputs frozen into the batch snapshot.
- Advertisements are job evidence, never candidate facts or instructions.
- Workers cannot delegate; maximum delegation depth is one.
- Discovery deduplicates before opening advertisements, and merge enforces snapshot history deduplication again.
- Materials and form answers must remain truthful.
- Final submission requires explicit approval of the current review and attachment hashes.
- Any confirmation consumes that approval. An unclear result is not automatically retried.
- Sensitive evidence stays under ignored `private/` and is handled manually.

## Workflow

```text
preflight
→ one new batch
→ bounded discovery + ordinary assessment
→ optional exceptional audit
→ materials
→ form review
→ human approval
→ one submission action + confirmation
→ archive
→ rebuild and validate index
→ complete batch
→ next batch
```

## Repository structure

- `AGENTS.md`: binding lead, worker, truth, privacy, stop, and single-batch rules.
- `START.md`: setup and operational guide.
- `config/workspace.json`: tracks, assessment policy, stop conditions, paths, and timezone.
- `profile/`: replaceable shared candidate inputs; add your own `profile/cv/base.docx` locally.
- `tracks/`: track-specific profiles, criteria, exclusions, and answer overrides.
- `private/`: ignored sensitive evidence.
- `history/`: reviewed-job source and rebuildable URL index.
- `archive/`: application index and minimal submitted-material archives.
- `batches/`: active and completed batch files; `batch.json` records the state, and batch contents are ignored except for `.gitkeep`.
- `tools/jobseek.py`: standard-library helper.
- `.codex/agents/`: four named agent configurations.
- `.agents/skills/`: concise worker instructions.
- `tests/`: helper reliability tests.

## Setup

1. Replace every `PLACEHOLDER` profile and track file with verified information.
2. Put a readable Word CV at `profile/cv/base.docx`. Do not commit it to a public repository.
3. Review track directories and `config/workspace.json`, including paths, scoring, exclusions, limits, and timezone.
4. Keep the repository private if you intend to commit populated profile, history, or archive index files. In a public fork, do not commit real candidate data or application history.
5. Run tests, rebuild the initially empty index, and run preflight.

The default timezone is `Australia/Perth`; change `timezone` before the first batch if another zone is authoritative. Timestamps must remain offset-aware.

## Agent roles

The root session is the only lead. It performs preflight, creates one batch, checks status, assigns bounded scopes, merges output, communicates with the user, records approval, archives confirmed applications, and completes the batch. It does not perform operational worker tasks.

- `jobseek_discovery_assess`: search, canonicalize, deduplicate, open complete ads, and perform ordinary assessment.
- `jobseek_audit`: resolve exceptional eligibility questions or inspect unclear confirmation.
- `jobseek_materials`: create and visually verify truthful CV and optional Cover Letter files.
- `jobseek_submission`: fill one form, prepare review, pause, validate approval, submit once, and record confirmation.

Repository configuration requests `gpt-5.6-terra` with medium reasoning for subagents. The actual model used remains subject to the Codex runtime.

## Commands

```sh
python3 tools/jobseek.py preflight --track <track>
python3 tools/jobseek.py new-batch --track <track>
python3 tools/jobseek.py status --batch <batch-id>
python3 tools/jobseek.py merge-discovery --batch <batch-id>
python3 tools/jobseek.py complete-batch --batch <batch-id>
python3 tools/jobseek.py approve --batch <batch-id> --job <job-id>
python3 tools/jobseek.py check-approval --batch <batch-id> --job <job-id>
python3 tools/jobseek.py archive --batch <batch-id> --job <job-id>
python3 tools/jobseek.py rebuild-index
```

## Discovery limits

The default batch stops discovery when any threshold is reached:

- 20 valid unique fully assessed new advertisements;
- 5 confirmed submissions;
- 3 explicit submission failures;
- 2 manual takeovers.

A historical duplicate, batch duplicate, observed-only result, or invalid assessment does not consume assessment capacity. Every worker scope must be bounded by source, query/category, location, page/result range or maximum full opens, and remaining capacity.

After each merge and at discovery closeout, the lead runs `status` and reports every `priority_jobs` entry without omission. This is the complete current list of `Eligible` and `Needs Review` jobs, including information and canonical links, derived directly from merged job files without an intermediate file.

## Approval and submission

The submission agent writes the exact `review.json` and stops before the final action. The user approves one job and one review/material version. `check-approval` must return `allowed: true` immediately before the click. The resulting `confirmed`, `not_submitted`, or `unclear` confirmation consumes that approval. A changed review or material requires a new approval.

Archive accepts only a confirmed application and stores only `advertisement.md`, submitted CV files, and submitted Cover Letter files when used.

## Data and privacy

This template contains no candidate, reviewed-job, application, advertisement, batch, or private-evidence data. Placeholder text intentionally makes preflight fail until setup is complete. Binary CVs, batch directories, sensitive evidence, and application archive directories are ignored.

Tracked profile, track, history, and archive index files become sensitive after you populate them. Do not commit those changes to a public fork.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/jobseek.py
```

See `START.md` for first-run steps, common prompts, approval points, and batch closeout.
