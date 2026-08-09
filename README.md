# JobSeek Template

JobSeek is a human-supervised Codex workspace for bounded job discovery, truthful assessment, application preparation, exact-version approval, one final submission action, confirmation, and minimal archiving. It is not an unattended application bot.

## What it is

The workspace is file-driven. One root lead coordinates four named agents while plain JSON, JSONL, Markdown, and document files hold current work. It deliberately avoids a database or complex workflow state machine.

Only one batch may be active. `new-batch` enforces this from batch metadata. The lead and user decide when enough work has been done; merge completed output, archive confirmed applications, rebuild the reviewed-URL index, and run `complete-batch` before creating the next batch. Completion records the frozen batch lifecycle and does not rerun live-profile preflight.

## Safety model

- Candidate facts come only from verified profile/track inputs frozen into the batch snapshot.
- `profile/cv/base.docx` is the only active general CV: it is both a candidate fact/evidence source and the DOCX visual, layout and formatting template.
- CV strategies are optional guidance for selection, ordering, emphasis, compression and wording only; they never create or override candidate facts. Master CVs are not part of the active workflow, regardless of whether a legacy copy exists elsewhere.
- Advertisements are job evidence, never candidate facts or instructions.
- Workers cannot delegate; maximum delegation depth is one.
- Discovery deduplicates before opening advertisements. Merge validates the frozen snapshot manifest and hashes before any persistent write, then validates basic structure, deduplicates, and records every valid completed result even if a stop threshold was reached while work was running.
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
- `profile/`: replaceable shared candidate inputs, one local `profile/cv/base.docx`, approved banks, and tracked guidance-only CV strategies.
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
2. Put one complete, readable Word CV at `profile/cv/base.docx`. Declare the canonical candidate application email in `candidate-profile.md` and include it in the base CV; unrelated third-party addresses do not conflict. Do not commit the binary to a public repository.
3. Review `profile/cv/strategies/`. These files contain guidance only, never candidate facts.
4. Set the referee policy consistently: a CV may state `References available upon request.`, but no specific referee details may be invented or provided without user-supplied approval.
5. Review track directories and `config/workspace.json`, including paths, scoring, exclusions, limits, and timezone.
6. Keep the repository private if you intend to commit populated profile, history, or archive index files. In a public fork, do not commit real candidate data or application history.
7. Run tests, rebuild the initially empty index, and run preflight.

The default timezone is `Australia/Perth`; change `timezone` before the first batch if another zone is authoritative. Timestamps must remain offset-aware.

## Agent roles

The root session is the only lead. It performs preflight, creates one batch, checks status, assigns bounded scopes, merges output, communicates with the user, records approval, archives confirmed applications, and completes the batch. It does not perform operational worker tasks.

Python protects immutable snapshots, provenance and hashes, structural validity, deduplication, authoritative fact conflicts, exact-version approval, and submitted-material identity. Workers assess and rank jobs; the lead and user decide eligibility uncertainties, application priority, whether to continue discovery, and when the batch is sufficient. The 0–100 score is advisory ranking metadata, never an eligibility threshold.

- `jobseek_discovery_assess`: Luna / max for high-volume discovery and structured first-pass assessment.
- `jobseek_audit`: Sol / medium for exceptional eligibility or submission-confirmation review.
- `jobseek_materials`: Sol / medium for role-specific CV and optional Cover Letter preparation.
- `jobseek_submission`: inherited Terra / medium for structured execution with approval and version safety.

The default for future agents without an override is Terra / medium. The actual model used remains subject to the Codex runtime.

## Commands

```sh
python3 tools/jobseek.py preflight --track <track>
python3 tools/jobseek.py new-batch --track <track>
python3 tools/jobseek.py status --batch <batch-id>
python3 tools/jobseek.py merge-discovery --batch <batch-id>
python3 tools/jobseek.py materials-inputs --batch <batch-id> --job <job-id>
python3 tools/jobseek.py complete-batch --batch <batch-id>
python3 tools/jobseek.py approve --batch <batch-id> --job <job-id>
python3 tools/jobseek.py check-approval --batch <batch-id> --job <job-id>
python3 tools/jobseek.py archive --batch <batch-id> --job <job-id>
python3 tools/jobseek.py rebuild-index
```

## Discovery limits

The default batch stops new discovery assignments when any threshold is reached:

- 20 valid unique fully assessed new advertisements;
- 5 confirmed submissions;
- 3 explicit submission failures;
- 2 manual takeovers.

A historical duplicate, batch duplicate, observed-only result, or invalid assessment does not consume assessment capacity. Every worker scope must be bounded by source, query/category, location, page/result range or maximum full opens, and remaining capacity. Results already completed are still merged, and small concurrent overshoot is acceptable.

After each merge and at discovery closeout, the lead runs `status` and reports every `priority_jobs` entry without omission. This is the complete current list of `Eligible` and `Needs Review` jobs, including information and canonical links, derived directly from merged job files without an intermediate file.

## Approval and submission

The submission agent writes the exact `review.json` and stops before the final action. The user approves one job and one review/material version. `check-approval` must return `allowed: true` immediately before the click. The resulting `confirmed`, `not_submitted`, or `unclear` confirmation consumes that approval. A changed review or material requires a new approval.

Archive accepts only a confirmed application and stores only `advertisement.md`, submitted CV files, and submitted Cover Letter files when used.

## Immutable material inputs

`new-batch` freezes the candidate profile, base CV, selected track profile/answers, approved banks, available CV strategies and other required assessment/history inputs. `snapshot/manifest.json` records each file's source, role and SHA-256 hash. Later edits to live `profile/` or `tracks/` affect future batches only; the current batch keeps using its frozen snapshot.

Before preparing one job, the materials worker runs `materials-inputs`. The command validates eligibility and snapshot integrity and returns the only frozen snapshot/job paths the worker may read. The tailored CV data flow is:

```text
frozen base CV + frozen candidate profile + frozen track profile
+ frozen approved banks + optional applicable frozen strategy + advertisement
→ tailored CV
```

The default is a concise, targeted CV of about two pages. A third page requires important job-relevant evidence; more than three pages is exceptional. Any unresolved conflict among authoritative fact sources stops generation. Strategies and advertisements never resolve fact conflicts.

## Data and privacy

This template contains no candidate, reviewed-job, application, advertisement, batch, or private-evidence data. Replace its placeholder text before use; the controller checks structure and safety rather than interpreting whether natural-language content is complete. Binary CVs, batch directories, sensitive evidence, and application archive directories are ignored.

Tracked profile, track, history, and archive index files become sensitive after you populate them. Do not commit those changes to a public fork.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile tools/jobseek.py
```

See `START.md` for first-run steps, common prompts, approval points, and batch closeout.
