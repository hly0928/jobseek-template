# JobSeek Workspace Template

JobSeek is a human-supervised Codex workspace for structured job discovery, eligibility assessment, application-material preparation, submission review, confirmation, and archival.

It provides:

* immutable per-batch input snapshots;
* append-only operational events;
* evidence-backed eligibility decisions;
* per-job materials and submission workflows;
* explicit user approval before every final submission;
* confirmation checks before an application is archived as successfully submitted.

> [!IMPORTANT]
> This is an experimental workflow template, not a fully autonomous application service.
> The user remains responsible for reviewing every application, ensuring that all information is truthful, and complying with the relevant recruitment platform and employer requirements.

## Requirements

* Python 3.9 or newer;
* a Codex environment that can read the workspace and use its project agent configuration;
* an existing logged-in browser session when browser-based search or application work is required.

`tools/jobseekctl` uses only the Python standard library.

## Workspace structure

* `Profile/`, `CV/`, `Templates/`, `JobName/Profile/`, and `JobName/Templates/` contain authoritative inputs for new batches.
* `.jobseek/config.json` is the single source of executable track configuration, assessment rules, limits, stop conditions, and snapshot inputs.
* `.jobseek/batches/` contains immutable batch inputs, manifests, append-only events, evidence packets, and operational state.
* `JobName/Tracker/` and `JobName/Logs/` are legacy compatibility and history views, not lossless batch exports.
* `JobName/Applications/` contains only applications whose submission was directly verified.
* `.codex/config.toml` defines the bounded worker configuration supplied with this template.
* `tools/jobseekctl` validates snapshots, ownership, evidence, event-derived counters, state transitions, review and approval gates, submission attempts, and confirmation.

The included Codex configuration requests `gpt-5.6-luna` with `high` reasoning for bounded workers. Only an explicit runtime report that Luna is unavailable, unloaded, or unsupported permits the root lead to retry the same bounded call once with `gpt-5.6-terra` and `medium`; ordinary task, tool, or quality failures do not permit a model switch.

## Quick start

1. Copy this template or create a repository from it.

2. Rename `JobName/` to your intended job track, such as `IT/`, `Design/`, or `Hospitality/`.

3. In `.jobseek/config.json`:

   * retain only the tracks you intend to use;
   * rename the matching track key;
   * update all track-relative `input_paths`;
   * define that track's hard exclusions, score components, and eligibility threshold.

4. Replace every placeholder in the authoritative input files.

5. Add the truthful reusable base CV as:

   ```text
   CV/CV_Plain_Base.docx
   ```

6. Run a preflight check before creating a batch:

   ```text
   tools/jobseekctl preflight --track <track-name> --new-batch --dry-run
   ```

   On systems where the script is not directly executable, use:

   ```text
   python tools/jobseekctl preflight --track <track-name> --new-batch --dry-run
   ```

7. Read [`START.md`](START.md) for detailed setup instructions and ready-to-use prompts.

## Privacy and repository hygiene

The supplied `.gitignore` excludes normal runtime batches, caches, private-detail files, generated applications, logs, trackers, and most evidence artifacts.

Before every commit, still review:

```text
git status --short
```

Do not commit passwords, verification codes, identity documents, visa documents, banking or tax records, medical information, private browser data, or generated application artifacts containing personal information.

Phone numbers and email addresses may be ordinary application contact information, but repository owners should decide deliberately whether they belong in a public repository. Prefer publishing the unfilled template and keeping populated workspaces private.

## Human submission boundary

The system may search, assess, prepare materials, and fill application forms, but it must stop before every final `Submit`, `Apply`, or `Send`.

A submission may proceed only after the user has reviewed the current:

* job and employer identity;
* application page;
* answers;
* attachments;
* declarations;
* exact submission review ID.

Any material change invalidates the existing approval and requires a new review.

A submission is archived under `Applications/` only after the result has been directly verified. An unclear confirmation must pause for investigation and must not trigger a blind retry.
