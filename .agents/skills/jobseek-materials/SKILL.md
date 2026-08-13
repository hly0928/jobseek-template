---
name: jobseek-materials
description: Prepare and visually verify truthful CV and optional Cover Letter files for one Eligible job without unresolved items.
---

# Application materials

Read root `AGENTS.md`. Run `python3 tools/jobseek.py materials-inputs --batch <batch-id> --job <job-id>` before creating anything, then read only the returned frozen snapshot paths and that job's returned advertisement/application-state paths. Proceed only when the command succeeds. Do not read live `profile/`, live `tracks/`, another batch, or `private/`.

Treat `snapshot/base-cv.docx` as both an authoritative content/evidence source and the visual, layout and formatting template. Candidate facts may also come from the frozen candidate profile, track profile and approved answer/content banks returned by the command. If two authoritative sources conflict and the conflict cannot be resolved safely from the frozen record, stop that materials step and report the exact conflict; never choose a value arbitrarily.

Use the explicit application-email declaration in the frozen candidate profile as the candidate contact and ensure the CV retains it. Do not infer that an unrelated recruiter, referee, example, or other third-party email address is the candidate's application email.

Use an applicable file under `snapshot/cv-strategies/` when one exists; strategies are optional guidance only. A strategy may control relevance, selection, ordering, emphasis, compression and cautious wording, but it is never a candidate fact source and cannot create or override evidence. Materials generation proceeds normally without a strategy.

Tailor the CV to the complete advertisement by selecting, reordering, compressing and carefully rewording supported content. Preserve the base CV's professional DOCX visual system and structural quality; do not reduce it to a plain-text rebuild. Preserve multilevel-list semantics as well as appearance. For any nested bullet list, reuse the base CV's actual Word list hierarchy: parent items use the corresponding first-level structure and child items use the corresponding deeper level, with child text visibly indented farther than its parent. Do not simulate nesting with bullet characters or visual approximation alone. Never invent experience or represent personal, academic, open-source or project activity as commercial employment.

Default to a concise, targeted CV of about two pages. Use a third page only when important job-relevant evidence cannot reasonably fit without harming clarity or truthfulness. Treat more than three pages as an exception requiring an explicit rule or documented special reason. Do not mechanically retain all base-CV content because the base is longer.

A CV may include `References available upon request.` or a concise equivalent. Do not invent or disclose referee names, positions, phone numbers or email addresses unless the frozen sources show that the user supplied and approved them. Create only materials needed for the role. Omit a Cover Letter when it is not used.

Render and visually inspect every DOCX or PDF deliverable. Check truthfulness, clipping, overflow, page breaks, typography, list hierarchy and indentation, filenames, and readability. For multilevel lists, also verify the DOCX structure or effective paragraph formatting so that every child item has a deeper list level and effective left indent than its parent. Save final files under the job's `materials/` directory. Before returning, delete all temporary, rendered, QA, metadata, build, and other intermediate files, leaving only final application deliverables.

Do not fill forms, submit, or delegate.
