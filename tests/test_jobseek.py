import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
import datetime as dt
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import jobseek  # noqa: E402


class JobSeekTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.original_root = jobseek.ROOT
        jobseek.ROOT = self.root
        for directory in ("config", "history", "archive/applications", "batches", "profile/cv/strategies", "profile/banks"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        for track in ("it", "part-time"):
            directory = self.root / "tracks" / track
            directory.mkdir(parents=True)
            for name in ("profile.md", "search-criteria.md", "answer-overrides.md"):
                jobseek.atomic_write(directory / name, f"# {track} {name}\n")
        jobseek.atomic_write(
            self.root / "profile/candidate-profile.md",
            "# Candidate\n\n- Preferred application email: candidate@example.com\n",
        )
        jobseek.atomic_write(
            self.root / "profile/banks/application-answers.md",
            "# Answers\n\nReferences available upon request. Never invent referee contact details.\n",
        )
        jobseek.atomic_write(self.root / "profile/banks/cover-letter-content.md", "# Cover letters\n")
        self.write_base_cv()
        jobseek.atomic_write(
            self.root / "profile/cv/strategies/general.md",
            "# General CV strategy\n\nGuidance only - not a candidate fact source.\n",
        )
        self.write_config()
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", [])
        jobseek.write_json(self.root / "history/reviewed-url-index.json", {})
        jobseek.write_jsonl(self.root / "archive/applications.jsonl", [])

    def tearDown(self):
        jobseek.ROOT = self.original_root
        self.temporary.cleanup()

    def write_config(self, score_components=None):
        jobseek.write_json(self.root / "config/workspace.json", {
            "hard_exclusions": {"work_authorisation": "Required work rights are unsupported."},
            "score_components": score_components or {"fit": 70, "logistics": 30},
            "timezone": "Australia/Perth",
            "stop_conditions": {
                "max_fully_assessed_ads": 20,
                "target_confirmed_submissions": 5,
                "max_submission_failures": 3,
                "max_manual_takeovers": 2,
            },
            "tracks": {
                "it": {"directory": "tracks/it", "scope_exclusions": ["sales"]},
                "part-time": {"directory": "tracks/part-time", "scope_exclusions": ["full-time"]},
            },
            "history": {"reviewed_jobs": "history/reviewed-jobs.jsonl", "reviewed_url_index": "history/reviewed-url-index.json"},
            "archive": {"applications_index": "archive/applications.jsonl", "applications_directory": "archive/applications"},
        })

    def write_base_cv(self, email="candidate@example.com"):
        with zipfile.ZipFile(self.root / "profile/cv/base.docx", "w") as archive:
            archive.writestr(
                "word/document.xml",
                f"<document>Email: {email} References: Available upon request.</document>",
            )

    def make_batch(self):
        batch = self.root / "batches/2026-08-03__it__001"
        (batch / "discovery").mkdir(parents=True, exist_ok=True)
        (batch / "jobs").mkdir(exist_ok=True)
        (batch / "snapshot").mkdir(exist_ok=True)
        jobseek.write_json(batch / "batch.json", {
            "batch_id": batch.name,
            "completed_at": None,
            "created_at": "2026-08-03T00:00:00Z",
            "status": "active",
            "track": "it",
        })
        snapshot = batch / "snapshot"
        shutil.copy2(self.root / "profile/cv/base.docx", snapshot / "base-cv.docx")
        text_inputs = [
            (self.root / "profile/candidate-profile.md", "candidate-profile.md", "candidate_fact_source"),
            (self.root / "tracks/it/profile.md", "track-profile.md", "candidate_fact_source"),
            (self.root / "tracks/it/search-criteria.md", "search-criteria.md", "assessment_configuration"),
            (self.root / "tracks/it/answer-overrides.md", "answer-overrides.md", "approved_content_bank"),
            (self.root / "profile/banks/application-answers.md", "answer-bank.md", "approved_content_bank"),
            (self.root / "profile/banks/cover-letter-content.md", "cover-letter-bank.md", "approved_content_bank"),
        ]
        records = [{
            "path": "base-cv.docx",
            "role": "candidate_fact_and_cv_template",
            "source": "profile/cv/base.docx",
        }]
        for source, relative, role in text_inputs:
            shutil.copy2(source, snapshot / relative)
            records.append({"path": relative, "role": role, "source": source.relative_to(self.root).as_posix()})
        shutil.copy2(self.root / "history/reviewed-jobs.jsonl", snapshot / "reviewed-jobs.jsonl")
        shutil.copy2(self.root / "history/reviewed-url-index.json", snapshot / "reviewed-url-index.json")
        records.extend([
            {"path": "reviewed-jobs.jsonl", "role": "discovery_history", "source": "history/reviewed-jobs.jsonl"},
            {"path": "reviewed-url-index.json", "role": "discovery_history", "source": "history/reviewed-url-index.json"},
        ])
        jobseek.write_json(snapshot / "assessment-policy.json", jobseek.assessment_policy(jobseek.workspace_config(), "it"))
        records.append({
            "path": "assessment-policy.json",
            "role": "assessment_configuration",
            "source": "config/workspace.json#assessment-policy",
        })
        jobseek.write_snapshot_manifest(snapshot, records)
        return batch

    def refresh_snapshot_hash(self, batch, relative):
        manifest = jobseek.read_json(batch / "snapshot/manifest.json")
        for record in manifest["files"]:
            if record["path"] == relative:
                record["sha256"] = jobseek.sha256_file(batch / "snapshot" / relative)
                break
        else:
            self.fail(f"missing manifest record: {relative}")
        jobseek.write_json(batch / "snapshot/manifest.json", manifest)

    def assessed(self, url="https://seek.com.au/job/99", company="Example"):
        return {
            "url": url,
            "company": company,
            "title": "Support Officer",
            "fully_assessed": True,
            "advertisement_markdown": "# Support Officer\n\nComplete advertisement.",
            "assessment": {
                "classification": "Eligible", "reasons": [], "unresolved_items": [], "hard_exclusions": [],
                "assessed_at": "2026-08-03T00:00:00Z", "score_total": 80,
            },
        }

    def add_assessed_job(self, batch, number):
        job_dir = batch / "jobs" / f"seek-{number}"
        job_dir.mkdir(parents=True)
        jobseek.atomic_write(job_dir / "advertisement.md", "# Complete advertisement\n")
        assessment = self.assessed(f"https://seek.com.au/job/{number}")["assessment"]
        jobseek.write_json(job_dir / "assessment.json", assessment)
        jobseek.write_json(job_dir / "job.json", {"job_id": job_dir.name, "fully_assessed": True})
        return job_dir

    def add_confirmation(self, batch, number, status, **extra):
        job_dir = batch / "jobs" / f"seek-{number}"
        (job_dir / "submission").mkdir(parents=True)
        payload = {"review_hash": f"hash-{number}", "status": status, "submitted_at": "2026-08-03T10:00:00+08:00"}
        payload.update(extra)
        jobseek.write_json(job_dir / "submission/confirmation.json", payload)

    def make_job(self, with_cv=True, with_cover=True):
        batch = self.make_batch()
        job_dir = batch / "jobs/seek-55"
        (job_dir / "materials").mkdir(parents=True)
        (job_dir / "submission").mkdir()
        jobseek.atomic_write(job_dir / "advertisement.md", "# Advertisement\n")
        attachments = []
        if with_cv:
            jobseek.atomic_write(job_dir / "materials/CV Final.pdf", "cv")
            attachments.append("materials/CV Final.pdf")
        if with_cover:
            jobseek.atomic_write(job_dir / "materials/Cover Letter Final.docx", "cover")
            attachments.append("materials/Cover Letter Final.docx")
        jobseek.write_json(job_dir / "submission/review.json", {
            "job_id": "seek-55",
            "page_url": "https://example.com/apply",
            "page_fingerprint": "page-1",
            "answers": {},
            "declarations": [],
            "selected_attachments": attachments,
            "reviewed_at": "2026-08-03T09:00:00Z",
        })
        jobseek.write_json(job_dir / "job.json", {
            "job_id": "seek-55",
            "canonical_url": "https://seek.com.au/job/55",
            "company": "Example Co",
            "title": "Support Officer",
            "track": "it",
            "source": "SEEK",
        })
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", [{
            "job_id": "seek-55", "canonical_url": "https://seek.com.au/job/55",
            "outcome": "eligible", "application_id": None,
        }])
        jobseek.rebuild_index()
        return batch, job_dir

    def approve_and_confirm(self, batch, job_dir, status="confirmed"):
        args = argparse.Namespace(batch=batch.name, job=job_dir.name)
        jobseek.command_approve(args)
        review_hash, _ = jobseek.validate_review(job_dir)
        jobseek.write_json(job_dir / "submission/confirmation.json", {
            "review_hash": review_hash, "status": status, "submitted_at": "2026-08-03T10:00:00Z",
        })
        return args, review_hash

    def test_seek_canonicalization_and_alias_identity(self):
        first = jobseek.canonicalize_url("https://www.seek.com.au/job/999000001?type=standard")
        second = jobseek.canonicalize_url("https://au.seek.com/job/999000001#apply")
        self.assertEqual(first["canonical_url"], "https://seek.com.au/job/999000001")
        self.assertEqual(first["identity_key"], second["identity_key"])

    def test_indeed_canonicalization(self):
        first = jobseek.canonicalize_url("https://au.indeed.com/viewjob?vjk=fixture123abc&utm_source=x")
        second = jobseek.canonicalize_url("https://indeed.com/viewjob?jk=fixture123abc")
        self.assertEqual(first["canonical_url"], second["canonical_url"])

    def test_generic_tracking_cleanup_and_query_order(self):
        first = jobseek.canonicalize_url("http://EXAMPLE.com/jobs/42/?b=2&utm_medium=x&a=1#top")
        second = jobseek.canonicalize_url("https://example.com/jobs/42?a=1&b=2&trackingId=no")
        self.assertEqual(first["identity_key"], second["identity_key"])

    def test_rebuild_index_is_deterministic_and_idempotent(self):
        rows = [{"job_id": "seek-2", "canonical_url": "https://seek.com.au/job/2"},
                {"job_id": "seek-1", "canonical_url": "https://seek.com.au/job/1"}]
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", rows)
        jobseek.rebuild_index()
        before = (self.root / "history/reviewed-url-index.json").read_bytes()
        jobseek.rebuild_index()
        self.assertEqual(before, (self.root / "history/reviewed-url-index.json").read_bytes())

    def test_review_missing_required_field_is_rejected(self):
        _batch, job_dir = self.make_job()
        review = jobseek.read_json(job_dir / "submission/review.json")
        del review["answers"]
        jobseek.write_json(job_dir / "submission/review.json", review)
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.validate_review(job_dir)

    def test_review_job_id_mismatch_is_rejected(self):
        _batch, job_dir = self.make_job()
        review = jobseek.read_json(job_dir / "submission/review.json")
        review["job_id"] = "seek-999"
        jobseek.write_json(job_dir / "submission/review.json", review)
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.validate_review(job_dir)

    def test_attachment_escape_is_rejected(self):
        _batch, job_dir = self.make_job()
        jobseek.atomic_write(job_dir.parent / "outside.pdf", "cv")
        review = jobseek.read_json(job_dir / "submission/review.json")
        review["selected_attachments"] = ["../outside.pdf"]
        jobseek.write_json(job_dir / "submission/review.json", review)
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.validate_review(job_dir)

    def test_duplicate_attachment_is_rejected(self):
        _batch, job_dir = self.make_job()
        review = jobseek.read_json(job_dir / "submission/review.json")
        review["selected_attachments"] = ["materials/CV Final.pdf", "./materials/CV Final.pdf"]
        jobseek.write_json(job_dir / "submission/review.json", review)
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.validate_review(job_dir)

    def test_review_without_cv_is_rejected(self):
        _batch, job_dir = self.make_job(with_cv=False)
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.validate_review(job_dir)

    def test_review_or_attachment_change_invalidates_approval(self):
        batch, job_dir = self.make_job()
        args = argparse.Namespace(batch=batch.name, job=job_dir.name)
        jobseek.command_approve(args)
        review = jobseek.read_json(job_dir / "submission/review.json")
        review["page_fingerprint"] = "page-2"
        jobseek.write_json(job_dir / "submission/review.json", review)
        self.assertFalse(jobseek.approval_is_valid(job_dir))
        jobseek.command_approve(args)
        jobseek.atomic_write(job_dir / "materials/CV Final.pdf", "changed")
        self.assertFalse(jobseek.approval_is_valid(job_dir))

    def test_confirmation_consumes_approval(self):
        batch, job_dir = self.make_job()
        self.approve_and_confirm(batch, job_dir, "confirmed")
        result = jobseek.approval_check(job_dir)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "approval_already_consumed")

    def test_unclear_confirmation_consumes_approval(self):
        batch, job_dir = self.make_job()
        self.approve_and_confirm(batch, job_dir, "unclear")
        self.assertEqual(jobseek.approval_check(job_dir)["reason"], "approval_already_consumed")

    def test_not_submitted_confirmation_consumes_approval(self):
        batch, job_dir = self.make_job()
        self.approve_and_confirm(batch, job_dir, "not_submitted")
        self.assertEqual(jobseek.approval_check(job_dir)["reason"], "approval_already_consumed")

    def test_new_review_hash_can_be_reapproved(self):
        batch, job_dir = self.make_job()
        self.approve_and_confirm(batch, job_dir, "unclear")
        review = jobseek.read_json(job_dir / "submission/review.json")
        review["page_fingerprint"] = "page-2"
        review["reviewed_at"] = "2026-08-03T11:00:00Z"
        jobseek.write_json(job_dir / "submission/review.json", review)
        jobseek.command_approve(argparse.Namespace(batch=batch.name, job=job_dir.name))
        self.assertTrue(jobseek.approval_check(job_dir)["allowed"])

    def test_fully_assessed_wins_over_earlier_observed(self):
        batch = self.make_batch()
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [{"url": "https://seek.com.au/job/99", "observed": True}])
        jobseek.write_jsonl(batch / "discovery/b.jsonl", [self.assessed(company="Winner")])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertEqual(jobseek.read_json(batch / "jobs/seek-99/job.json")["company"], "Winner")

    def test_fully_assessed_wins_over_duplicate_placeholder(self):
        batch = self.make_batch()
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [{"url": "https://seek.com.au/job/99", "result": "duplicate"}])
        jobseek.write_jsonl(batch / "discovery/b.jsonl", [self.assessed()])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertTrue((batch / "jobs/seek-99/assessment.json").is_file())

    def test_two_fully_assessed_records_create_one_job_and_history(self):
        batch = self.make_batch()
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [self.assessed("https://www.seek.com.au/job/99")])
        jobseek.write_jsonl(batch / "discovery/b.jsonl", [self.assessed("https://au.seek.com/job/99")])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertEqual(len(list((batch / "jobs").iterdir())), 1)
        self.assertEqual(len(jobseek.read_jsonl(self.root / "history/reviewed-jobs.jsonl")), 1)

    def test_observed_only_does_not_enter_history(self):
        batch = self.make_batch()
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [{"url": "https://seek.com.au/job/100", "observed": True}])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertEqual(jobseek.read_jsonl(self.root / "history/reviewed-jobs.jsonl"), [])

    def test_merge_discovery_is_idempotent(self):
        batch = self.make_batch()
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [self.assessed()])
        args = argparse.Namespace(batch=batch.name)
        jobseek.command_merge_discovery(args)
        before = (self.root / "history/reviewed-jobs.jsonl").read_bytes()
        jobseek.command_merge_discovery(args)
        self.assertEqual(before, (self.root / "history/reviewed-jobs.jsonl").read_bytes())

    def test_archive_validation_failure_leaves_no_final_directory(self):
        batch, job_dir = self.make_job()
        args = argparse.Namespace(batch=batch.name, job=job_dir.name)
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_archive(args)
        self.assertEqual(list((self.root / "archive/applications").iterdir()), [])

    def test_archive_missing_cv_leaves_no_partial_directory(self):
        batch, job_dir = self.make_job(with_cv=False)
        jobseek.write_json(job_dir / "submission/confirmation.json", {
            "review_hash": "invalid", "status": "confirmed", "submitted_at": "2026-08-03T10:00:00Z",
        })
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_archive(argparse.Namespace(batch=batch.name, job=job_dir.name))
        self.assertEqual(list((self.root / "archive/applications").iterdir()), [])

    def test_archive_copies_only_allowed_files(self):
        batch, job_dir = self.make_job()
        jobseek.atomic_write(job_dir / "submission/review-history.md", "discard")
        args, _ = self.approve_and_confirm(batch, job_dir)
        jobseek.command_archive(args)
        row = jobseek.read_jsonl(self.root / "archive/applications.jsonl")[0]
        names = sorted(path.name for path in (self.root / row["archive_path"]).iterdir())
        self.assertEqual(names, ["advertisement.md", "cover-letter.docx", "cv.pdf"])

    def test_archive_without_cover_letter_creates_no_empty_file(self):
        batch, job_dir = self.make_job(with_cover=False)
        args, _ = self.approve_and_confirm(batch, job_dir)
        jobseek.command_archive(args)
        row = jobseek.read_jsonl(self.root / "archive/applications.jsonl")[0]
        self.assertEqual(sorted(path.name for path in (self.root / row["archive_path"]).iterdir()), ["advertisement.md", "cv.pdf"])

    def test_existing_archive_without_index_is_reconciled(self):
        batch, job_dir = self.make_job()
        args, _ = self.approve_and_confirm(batch, job_dir)
        jobseek.command_archive(args)
        jobseek.write_jsonl(self.root / "archive/applications.jsonl", [])
        jobseek.command_archive(args)
        self.assertEqual(len(jobseek.read_jsonl(self.root / "archive/applications.jsonl")), 1)

    def test_duplicate_archive_does_not_duplicate_index(self):
        batch, job_dir = self.make_job()
        args, _ = self.approve_and_confirm(batch, job_dir)
        jobseek.command_archive(args)
        jobseek.command_archive(args)
        self.assertEqual(len(jobseek.read_jsonl(self.root / "archive/applications.jsonl")), 1)

    def test_archive_content_conflict_is_rejected(self):
        batch, job_dir = self.make_job()
        args, _ = self.approve_and_confirm(batch, job_dir)
        jobseek.command_archive(args)
        row = jobseek.read_jsonl(self.root / "archive/applications.jsonl")[0]
        jobseek.atomic_write(self.root / row["archive_path"] / "cv.pdf", "conflict")
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_archive(args)

    def test_stale_reviewed_index_fails_preflight(self):
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", [{"job_id": "seek-1", "canonical_url": "https://seek.com.au/job/1"}])
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_application_archive_missing_cv_fails_preflight(self):
        application_id = "2026-08-03__seek-1"
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", [{
            "job_id": "seek-1", "canonical_url": "https://seek.com.au/job/1",
            "outcome": "applied", "application_id": application_id,
        }])
        jobseek.rebuild_index()
        archive = self.root / "archive/applications/example"
        archive.mkdir()
        jobseek.atomic_write(archive / "advertisement.md", "ad")
        jobseek.write_jsonl(self.root / "archive/applications.jsonl", [{
            "application_id": application_id, "job_id": "seek-1", "canonical_url": "https://seek.com.au/job/1",
            "archive_path": "archive/applications/example",
        }])
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_score_components_must_total_100(self):
        self.write_config({"fit": 99})
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_unknown_track_fails_from_configuration(self):
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_preflight(argparse.Namespace(track="unknown"))

    def test_new_batch_freezes_assessment_policy(self):
        reviewed = {"job_id": "seek-1", "canonical_url": "https://seek.com.au/job/1", "company": "Example", "title": "Support Officer"}
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", [reviewed])
        jobseek.rebuild_index()
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        policy_path = batch / "snapshot/assessment-policy.json"
        policy = jobseek.read_json(policy_path)
        self.assertEqual(policy["score_components"], {"fit": 70, "logistics": 30})
        self.assertEqual(jobseek.read_jsonl(batch / "snapshot/reviewed-jobs.jsonl"), [reviewed])
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", [])
        self.assertEqual(jobseek.read_jsonl(batch / "snapshot/reviewed-jobs.jsonl"), [reviewed])
        config = jobseek.read_json(self.root / "config/workspace.json")
        config["score_components"] = {"future_ranking": 100}
        jobseek.write_json(self.root / "config/workspace.json", config)
        self.assertEqual(jobseek.read_json(policy_path)["score_components"], {"fit": 70, "logistics": 30})

    def test_new_batch_freezes_complete_material_inputs_with_roles_and_hashes(self):
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        manifest = jobseek.validate_snapshot_manifest(batch)
        roles = {record["path"]: record["role"] for record in manifest["files"]}
        self.assertEqual(roles["base-cv.docx"], "candidate_fact_and_cv_template")
        self.assertEqual(roles["candidate-profile.md"], "candidate_fact_source")
        self.assertEqual(roles["track-profile.md"], "candidate_fact_source")
        self.assertEqual(roles["answer-bank.md"], "approved_content_bank")
        self.assertEqual(roles["cover-letter-bank.md"], "approved_content_bank")
        self.assertEqual(roles["cv-strategies/general.md"], "cv_guidance_only")
        frozen = (batch / "snapshot/candidate-profile.md").read_text(encoding="utf-8")
        jobseek.atomic_write(
            self.root / "profile/candidate-profile.md",
            "# Candidate\n\n- Preferred application email: future@example.com\n",
        )
        self.assertEqual((batch / "snapshot/candidate-profile.md").read_text(encoding="utf-8"), frozen)
        jobseek.validate_snapshot_manifest(batch)

    def test_materials_inputs_exposes_only_frozen_snapshot_and_job_paths(self):
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        job_dir = batch / "jobs/seek-77"
        job_dir.mkdir()
        jobseek.atomic_write(job_dir / "advertisement.md", "# Complete advertisement\n")
        jobseek.write_json(job_dir / "job.json", {"job_id": "seek-77", "track": "it"})
        jobseek.write_json(job_dir / "assessment.json", {
            "classification": "Eligible",
            "reasons": [],
            "unresolved_items": [],
        })
        jobseek.atomic_write(self.root / "profile/banks/application-answers.md", "# LIVE CHANGE\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            jobseek.command_materials_inputs(argparse.Namespace(batch=batch.name, job="seek-77"))
        result = json.loads(output.getvalue())
        disclosed = result["fact_sources"] + result["guidance_only"] + result["job_inputs"]
        self.assertTrue(all(path.startswith(f"batches/{batch.name}/") for path in disclosed))
        self.assertTrue(all("/profile/" not in path and "/tracks/" not in path for path in disclosed))
        self.assertEqual(result["base_cv_template"], f"batches/{batch.name}/snapshot/base-cv.docx")
        self.assertEqual(result["guidance_only"], [f"batches/{batch.name}/snapshot/cv-strategies/general.md"])

    def test_materials_inputs_rejects_changed_snapshot(self):
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        jobseek.atomic_write(batch / "snapshot/candidate-profile.md", "tampered\n")
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.validate_snapshot_manifest(batch)

    def test_snapshot_conflict_is_rejected_even_if_manifest_hash_is_rewritten(self):
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        profile_path = batch / "snapshot/candidate-profile.md"
        jobseek.atomic_write(
            profile_path,
            "# Candidate\n\n- Preferred application email: conflict@example.com\n",
        )
        manifest = jobseek.read_json(batch / "snapshot/manifest.json")
        for record in manifest["files"]:
            if record["path"] == "candidate-profile.md":
                record["sha256"] = jobseek.sha256_file(profile_path)
        jobseek.write_json(batch / "snapshot/manifest.json", manifest)
        with self.assertRaisesRegex(jobseek.JobSeekError, "email conflict"):
            jobseek.validate_snapshot_manifest(batch)

    def test_preflight_accepts_canonical_profile_email_in_base_cv(self):
        jobseek.atomic_write(
            self.root / "profile/candidate-profile.md",
            "# Candidate\n\n- Preferred application email: hulinyi928@gmail.com\n",
        )
        self.write_base_cv("hulinyi928@gmail.com")
        jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_preflight_rejects_base_cv_without_canonical_email(self):
        self.write_base_cv("other@example.com")
        with self.assertRaisesRegex(jobseek.JobSeekError, "email conflict"):
            jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_preflight_allows_third_party_emails_in_banks(self):
        jobseek.atomic_write(
            self.root / "profile/banks/cover-letter-content.md",
            "# Contact context\n\nRecruiter: recruiter@example.com\n",
        )
        jobseek.atomic_write(
            self.root / "profile/banks/application-answers.md",
            "# Referee context\n\nA user-approved referee may later use referee@example.org.\n",
        )
        jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_preflight_rejects_explicit_conflicting_application_email_declaration(self):
        jobseek.atomic_write(
            self.root / "tracks/it/answer-overrides.md",
            "# Overrides\n\nApplication email: conflict@example.com\n",
        )
        with self.assertRaisesRegex(jobseek.JobSeekError, "email conflict"):
            jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_base_cv_may_contain_other_email_when_canonical_is_present(self):
        with zipfile.ZipFile(self.root / "profile/cv/base.docx", "w") as archive:
            archive.writestr(
                "word/document.xml",
                "<document>candidate@example.com recruiter@example.com</document>",
            )
        jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_snapshot_allows_third_party_emails_but_rejects_candidate_declaration_conflict(self):
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        bank = batch / "snapshot/answer-bank.md"
        jobseek.atomic_write(bank, "# Referee\n\nContact referee@example.org only after approval.\n")
        self.refresh_snapshot_hash(batch, "answer-bank.md")
        jobseek.validate_snapshot_manifest(batch)
        jobseek.atomic_write(bank, "# Candidate contact\n\nApplication email: conflict@example.com\n")
        self.refresh_snapshot_hash(batch, "answer-bank.md")
        with self.assertRaisesRegex(jobseek.JobSeekError, "email conflict"):
            jobseek.validate_snapshot_manifest(batch)

    def test_preflight_does_not_parse_reference_wording(self):
        jobseek.atomic_write(self.root / "profile/banks/application-answers.md", "# Referee policy in natural language\n")
        self.write_base_cv()
        jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_preflight_ignores_legacy_master_cv(self):
        masters = self.root / "profile/cv/masters"
        masters.mkdir()
        with zipfile.ZipFile(masters / "legacy.docx", "w") as archive:
            archive.writestr("word/document.xml", "<document/>")
        jobseek.command_preflight(argparse.Namespace(track="it"))

    def test_strategy_is_optional(self):
        (self.root / "profile/cv/strategies/general.md").unlink()
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        manifest = jobseek.validate_snapshot_manifest(batch)
        self.assertFalse(any(record["role"] == "cv_guidance_only" for record in manifest["files"]))

    def test_strategy_wording_is_not_parsed(self):
        jobseek.atomic_write(
            self.root / "profile/cv/strategies/general.md",
            "Put the most relevant evidence first and keep the wording concise.\n",
        )
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        manifest = jobseek.validate_snapshot_manifest(batch)
        self.assertTrue(any(record["role"] == "cv_guidance_only" for record in manifest["files"]))

    def test_new_batch_requires_no_active_batch(self):
        first = self.make_batch()
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_new_batch(argparse.Namespace(track="part-time"))
        jobseek.command_complete_batch(argparse.Namespace(batch=first.name))
        jobseek.command_new_batch(argparse.Namespace(track="part-time"))
        self.assertEqual(len(jobseek.active_batch_ids()), 1)
        self.assertTrue(jobseek.active_batch_ids()[0].endswith("__part-time__001"))

    def test_complete_batch_sets_offset_aware_marker(self):
        batch = self.make_batch()
        completed_at = dt.datetime(2026, 8, 3, 12, 0, tzinfo=jobseek.ZoneInfo("Australia/Perth"))
        with mock.patch.object(jobseek, "now_in_workspace_timezone", return_value=completed_at):
            jobseek.command_complete_batch(argparse.Namespace(batch=batch.name))
        metadata = jobseek.validate_batch_metadata(batch)
        self.assertEqual(metadata["status"], "completed")
        self.assertEqual(metadata["completed_at"], "2026-08-03T12:00:00+08:00")
        self.assertIn("batch_completed", jobseek.batch_stop_status(batch)["stop_reasons"])
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))

    def test_complete_batch_uses_frozen_batch_not_live_preflight(self):
        batch = self.make_batch()
        jobseek.atomic_write(self.root / "profile/candidate-profile.md", "changed after batch creation\n")
        (self.root / "profile/cv/base.docx").unlink()
        with mock.patch.object(jobseek, "command_preflight", side_effect=AssertionError("live preflight called")):
            jobseek.command_complete_batch(argparse.Namespace(batch=batch.name))
        self.assertEqual(jobseek.validate_batch_metadata(batch)["status"], "completed")

    def test_discovery_results_include_all_eligible_and_needs_review_jobs(self):
        batch = self.make_batch()
        eligible = self.add_assessed_job(batch, 1)
        eligible_job = jobseek.read_json(eligible / "job.json")
        eligible_job.update({
            "canonical_url": "https://seek.com.au/job/1",
            "company": "Eligible Co",
            "source": "SEEK",
            "title": "Support Officer",
        })
        jobseek.write_json(eligible / "job.json", eligible_job)
        review = self.add_assessed_job(batch, 2)
        review_job = jobseek.read_json(review / "job.json")
        review_job.update({
            "canonical_url": "https://seek.com.au/job/2",
            "company": "Review Co",
            "source": "SEEK",
            "title": "Systems Officer",
        })
        jobseek.write_json(review / "job.json", review_job)
        assessment = jobseek.read_json(review / "assessment.json")
        assessment.update({"classification": "Needs Review", "unresolved_items": ["Work rights wording"]})
        jobseek.write_json(review / "assessment.json", assessment)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            jobseek.command_status(argparse.Namespace(batch=batch.name))
        results = json.loads(output.getvalue())["priority_jobs"]
        self.assertEqual([item["outcome"] for item in results], ["Eligible", "Needs Review"])
        self.assertEqual(results[0]["canonical_url"], "https://seek.com.au/job/1")
        self.assertEqual(results[1]["unresolved_items"], ["Work rights wording"])

    def test_stop_status_at_twenty_and_nineteen_assessments(self):
        batch = self.make_batch()
        for number in range(1, 20):
            self.add_assessed_job(batch, number)
        status = jobseek.batch_stop_status(batch)
        self.assertEqual(status["remaining_assessment_capacity"], 1)
        self.assertFalse(status["discovery_should_stop"])
        self.add_assessed_job(batch, 20)
        status = jobseek.batch_stop_status(batch)
        self.assertTrue(status["discovery_should_stop"])
        self.assertIn("max_fully_assessed_ads_reached", status["stop_reasons"])

    def test_final_audit_outcomes_are_assessed(self):
        batch = self.make_batch()
        for number, outcome in enumerate(("Skipped", "Blocked", "Expired", "Withdrawn"), 1):
            job_dir = self.add_assessed_job(batch, number)
            jobseek.write_json(job_dir / "audit.json", {
                "outcome": outcome,
                "remaining_items": [],
            })
            self.assertEqual(jobseek.derive_job_status(job_dir), "assessed")

    def test_unresolved_audit_outcome_is_waiting(self):
        batch = self.make_batch()
        job_dir = self.add_assessed_job(batch, 1)
        jobseek.write_json(job_dir / "audit.json", {
            "outcome": "Needs Review",
            "remaining_items": ["Candidate fact remains unresolved."],
        })
        self.assertEqual(jobseek.derive_job_status(job_dir), "waiting audit")

    def test_observed_and_historical_duplicates_do_not_use_capacity(self):
        batch = self.make_batch()
        jobseek.write_json(batch / "snapshot/reviewed-url-index.json", {"seek:99": "seek-99"})
        self.refresh_snapshot_hash(batch, "reviewed-url-index.json")
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [
            {"url": "https://seek.com.au/job/98", "observed": True}, self.assessed(),
        ])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertEqual(jobseek.batch_stop_status(batch)["fully_assessed_ads"], 0)

    def test_confirmed_submissions_trigger_stop(self):
        batch = self.make_batch()
        for number in range(5):
            self.add_confirmation(batch, number, "confirmed")
        status = jobseek.batch_stop_status(batch)
        self.assertEqual(status["confirmed_submissions"], 5)
        self.assertIn("target_confirmed_submissions_reached", status["stop_reasons"])

    def test_only_explicit_submission_failures_count(self):
        batch = self.make_batch()
        self.add_confirmation(batch, 1, "not_submitted")
        self.add_confirmation(batch, 2, "not_submitted", reason_code="user_cancelled")
        for number in (3, 4, 5):
            self.add_confirmation(batch, number, "not_submitted", reason_code="submission_failure")
        status = jobseek.batch_stop_status(batch)
        self.assertEqual(status["submission_failures"], 3)
        self.assertIn("max_submission_failures_reached", status["stop_reasons"])

    def test_two_manual_takeovers_trigger_stop(self):
        batch = self.make_batch()
        self.add_confirmation(batch, 1, "unclear", manual_takeover=True)
        self.add_confirmation(batch, 2, "not_submitted", manual_takeover=True)
        status = jobseek.batch_stop_status(batch)
        self.assertEqual(status["manual_takeovers"], 2)
        self.assertIn("max_manual_takeovers_reached", status["stop_reasons"])

    def test_merge_allows_small_overshoot_beyond_assessment_target(self):
        batch = self.make_batch()
        rows = [self.assessed(f"https://seek.com.au/job/{number}") for number in range(1, 23)]
        jobseek.write_jsonl(batch / "discovery/a.jsonl", rows)
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertEqual(len(list((batch / "jobs").iterdir())), 22)
        report = jobseek.read_json(batch / "merge-report.json")
        self.assertNotIn("not_merged_due_to_stop_limit", report)
        self.assertTrue(jobseek.batch_stop_status(batch)["discovery_should_stop"])

    def test_submission_stop_threshold_does_not_block_existing_output_merge(self):
        batch = self.make_batch()
        for number in range(5):
            self.add_confirmation(batch, number, "confirmed")
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [self.assessed("https://seek.com.au/job/99")])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertTrue((batch / "jobs/seek-99").exists())
        self.assertTrue(jobseek.batch_stop_status(batch)["discovery_should_stop"])

    def test_snapshot_historical_duplicate_is_never_merged_or_updated(self):
        history = [{
            "job_id": "seek-99", "canonical_url": "https://seek.com.au/job/99",
            "first_reviewed_at": "2026-01-01", "last_reviewed_at": "2026-01-01",
        }]
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", history)
        jobseek.rebuild_index()
        batch = self.make_batch()
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [self.assessed()])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertFalse((batch / "jobs/seek-99").exists())
        self.assertEqual(jobseek.read_jsonl(self.root / "history/reviewed-jobs.jsonl"), history)
        report = jobseek.read_json(batch / "merge-report.json")
        self.assertEqual(report["historical_duplicates"][0]["reason"], "present_in_batch_snapshot")

    def test_merge_requires_valid_history_snapshot(self):
        for damaged in (False, True):
            with self.subTest(damaged=damaged):
                if (self.root / "batches/2026-08-03__it__001").exists():
                    import shutil
                    shutil.rmtree(self.root / "batches/2026-08-03__it__001")
                batch = self.make_batch()
                path = batch / "snapshot/reviewed-url-index.json"
                if damaged:
                    jobseek.atomic_write(path, "not json")
                else:
                    path.unlink()
                with self.assertRaises(jobseek.JobSeekError):
                    jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))

    def assert_snapshot_integrity_failure_is_atomic(self, damage):
        batch = self.make_batch()
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [self.assessed()])
        history_before = (self.root / "history/reviewed-jobs.jsonl").read_bytes()
        damage(batch)
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertEqual(list((batch / "jobs").iterdir()), [])
        self.assertEqual((self.root / "history/reviewed-jobs.jsonl").read_bytes(), history_before)
        self.assertFalse((batch / "merge-report.json").exists())

    def test_merge_rejects_changed_snapshot_before_mutation(self):
        self.assert_snapshot_integrity_failure_is_atomic(
            lambda batch: jobseek.atomic_write(batch / "snapshot/candidate-profile.md", "tampered\n")
        )

    def test_merge_rejects_missing_snapshot_file_before_mutation(self):
        self.assert_snapshot_integrity_failure_is_atomic(
            lambda batch: (batch / "snapshot/candidate-profile.md").unlink()
        )

    def test_merge_rejects_broken_snapshot_manifest_before_mutation(self):
        self.assert_snapshot_integrity_failure_is_atomic(
            lambda batch: jobseek.atomic_write(batch / "snapshot/manifest.json", "not json\n")
        )

    def test_new_batch_uses_perth_date_across_utc_boundary(self):
        perth_time = dt.datetime(2026, 8, 3, 0, 30, tzinfo=jobseek.ZoneInfo("Australia/Perth"))
        with mock.patch.object(jobseek, "now_in_workspace_timezone", return_value=perth_time):
            jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        self.assertTrue(batch.name.startswith("2026-08-03__it__"))
        self.assertEqual(jobseek.read_json(batch / "batch.json")["created_at"], "2026-08-03T00:30:00+08:00")

    def test_perth_application_date_and_naive_timestamp_rejection(self):
        timezone = jobseek.ZoneInfo("Australia/Perth")
        self.assertEqual(jobseek.local_date_for_timestamp("2026-08-02T17:30:00+00:00", timezone).isoformat(), "2026-08-03")
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.local_date_for_timestamp("2026-08-03T01:30:00", timezone)

    def test_timestamp_normalization_preserves_instant(self):
        value = "2026-08-02T17:30:00+00:00"
        normalized = jobseek.normalized_workspace_timestamp(value, jobseek.workspace_config())
        self.assertEqual(normalized, "2026-08-03T01:30:00+08:00")
        self.assertEqual(jobseek.parse_aware_timestamp(value), jobseek.parse_aware_timestamp(normalized))

    def test_archive_uses_perth_date_and_preserves_file_hashes(self):
        batch, job_dir = self.make_job()
        args, review_hash = self.approve_and_confirm(batch, job_dir)
        confirmation = jobseek.read_json(job_dir / "submission/confirmation.json")
        confirmation.update({"review_hash": review_hash, "submitted_at": "2026-08-02T17:30:00+00:00"})
        jobseek.write_json(job_dir / "submission/confirmation.json", confirmation)
        source_hashes = {path.name: jobseek.sha256_file(path) for path in (job_dir / "materials").iterdir()}
        jobseek.command_archive(args)
        row = jobseek.read_jsonl(self.root / "archive/applications.jsonl")[0]
        self.assertEqual(row["application_id"], "2026-08-03__seek-55")
        reviewed = jobseek.read_jsonl(self.root / "history/reviewed-jobs.jsonl")[0]
        self.assertEqual(reviewed["application_id"], row["application_id"])
        archived = self.root / row["archive_path"]
        self.assertEqual(source_hashes["CV Final.pdf"], jobseek.sha256_file(archived / "cv.pdf"))
        self.assertEqual(source_hashes["Cover Letter Final.docx"], jobseek.sha256_file(archived / "cover-letter.docx"))

    def test_date_only_timestamp_is_not_guessed(self):
        with self.assertRaises(jobseek.JobSeekError):
            jobseek.parse_aware_timestamp("2026-08-03")

    def assert_invalid_assessment(self, changes):
        batch = self.make_batch()
        row = self.assessed()
        row["assessment"].update(changes)
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [row])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertFalse((batch / "jobs/seek-99").exists())
        self.assertTrue(jobseek.read_json(batch / "merge-report.json")["validation_errors"])

    def test_invalid_assessment_classification_is_rejected(self):
        self.assert_invalid_assessment({"classification": "Maybe"})

    def test_eligible_low_score_is_recorded(self):
        batch = self.make_batch()
        row = self.assessed()
        row["assessment"]["score_total"] = 12
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [row])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        assessment = jobseek.read_json(batch / "jobs/seek-99/assessment.json")
        self.assertEqual(assessment["classification"], "Eligible")
        self.assertEqual(assessment["score_total"], 12)

    def test_needs_review_high_score_is_recorded(self):
        batch = self.make_batch()
        row = self.assessed()
        row["assessment"].update({
            "classification": "Needs Review",
            "score_total": 99,
            "unresolved_items": ["Mandatory work-rights wording is unclear"],
        })
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [row])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        assessment = jobseek.read_json(batch / "jobs/seek-99/assessment.json")
        self.assertEqual(assessment["classification"], "Needs Review")
        self.assertEqual(assessment["score_total"], 99)

    def test_hard_excluded_high_score_stays_skipped(self):
        batch = self.make_batch()
        row = self.assessed()
        row["assessment"].update({
            "classification": "Skipped",
            "score_total": 100,
            "hard_exclusions": ["Unsupported mandatory work authorisation"],
        })
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [row])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        assessment = jobseek.read_json(batch / "jobs/seek-99/assessment.json")
        self.assertEqual(assessment["classification"], "Skipped")

    def test_hard_exclusion_cannot_be_eligible_even_at_100(self):
        self.assert_invalid_assessment({
            "classification": "Eligible",
            "score_total": 100,
            "hard_exclusions": ["Unsupported mandatory work authorisation"],
        })

    def test_assessment_without_score_is_recorded(self):
        batch = self.make_batch()
        row = self.assessed()
        del row["assessment"]["score_total"]
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [row])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        assessment = jobseek.read_json(batch / "jobs/seek-99/assessment.json")
        self.assertNotIn("score_total", assessment)

    def test_out_of_range_score_is_rejected(self):
        self.assert_invalid_assessment({"score_total": 101})

    def test_eligible_with_unresolved_items_is_rejected(self):
        self.assert_invalid_assessment({"unresolved_items": ["mandatory condition"]})

    def test_naive_assessed_at_is_rejected(self):
        self.assert_invalid_assessment({"assessed_at": "2026-08-03T08:00:00"})

    def test_agent_configuration_has_expected_static_model_routing(self):
        project = Path(__file__).resolve().parents[1]
        config = (project / ".codex/config.toml").read_text(encoding="utf-8")
        self.assertIn('default_subagent_model = "gpt-5.6-terra"', config)
        self.assertIn('default_subagent_reasoning_effort = "medium"', config)
        self.assertIn("max_depth = 1", config)
        expected = {"jobseek_discovery_assess", "jobseek_audit", "jobseek_materials", "jobseek_submission"}
        self.assertEqual(set(__import__("re").findall(r'^\[agents\.([a-z_]+)\]$', config, __import__("re").MULTILINE)), expected)
        overrides = {
            "jobseek-discovery-assess": ("gpt-5.6-luna", "max"),
            "jobseek-audit": ("gpt-5.6-sol", "medium"),
            "jobseek-materials": ("gpt-5.6-sol", "medium"),
        }
        for name, (model, effort) in overrides.items():
            text = (project / ".codex/agents" / f"{name}.toml").read_text(encoding="utf-8")
            self.assertIn(f'model = "{model}"', text)
            self.assertIn(f'model_reasoning_effort = "{effort}"', text)
            self.assertIn("[agents]\nenabled = false", text)
        submission = (project / ".codex/agents/jobseek-submission.toml").read_text(encoding="utf-8")
        self.assertIn("[agents]\nenabled = false", submission)
        self.assertNotRegex(submission, r"(?m)^model\s*=")
        self.assertNotRegex(submission, r"(?m)^model_reasoning_effort\s*=")

    def test_reusable_control_plane_matches_template(self):
        project = Path(__file__).resolve().parents[1]
        template = project / "jobseek-template"
        if not template.is_dir():
            self.skipTest("standalone template checkout")
        singleton = {Path(".gitignore"), Path("AGENTS.md"), Path("config/workspace.json")}
        shared_directories = [Path(".agents"), Path(".codex"), Path("tools"), Path("tests"), Path("profile/cv/strategies")]
        relative_paths = set(singleton)
        for directory in shared_directories:
            relative_paths.update(
                path.relative_to(project)
                for path in (project / directory).rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            )
        template_paths = set(singleton)
        for directory in shared_directories:
            template_paths.update(
                path.relative_to(template)
                for path in (template / directory).rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            )
        self.assertEqual(relative_paths, template_paths)
        for relative in sorted(relative_paths):
            self.assertEqual(
                (project / relative).read_bytes(),
                (template / relative).read_bytes(),
                f"control-plane drift: {relative}",
            )


if __name__ == "__main__":
    unittest.main()
