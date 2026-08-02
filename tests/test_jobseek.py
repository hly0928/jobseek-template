import argparse
import json
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
        for directory in ("config", "history", "archive/applications", "batches", "profile/cv", "profile/banks"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        for track in ("it", "part-time"):
            directory = self.root / "tracks" / track
            directory.mkdir(parents=True)
            for name in ("profile.md", "search-criteria.md", "answer-overrides.md"):
                jobseek.atomic_write(directory / name, f"# {track} {name}\n")
        jobseek.atomic_write(self.root / "profile/candidate-profile.md", "# Candidate\n")
        jobseek.atomic_write(self.root / "profile/banks/application-answers.md", "# Answers\n")
        jobseek.atomic_write(self.root / "profile/banks/cover-letter-content.md", "# Cover letters\n")
        with zipfile.ZipFile(self.root / "profile/cv/base.docx", "w") as archive:
            archive.writestr("word/document.xml", "<document/>")
        self.write_config()
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", [])
        jobseek.write_json(self.root / "history/reviewed-url-index.json", {})
        jobseek.write_jsonl(self.root / "archive/applications.jsonl", [])

    def tearDown(self):
        jobseek.ROOT = self.original_root
        self.temporary.cleanup()

    def write_config(self, score_components=None):
        jobseek.write_json(self.root / "config/workspace.json", {
            "eligible_threshold": 70,
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

    def make_batch(self):
        batch = self.root / "batches/2026-08-03__it__001"
        (batch / "discovery").mkdir(parents=True, exist_ok=True)
        (batch / "jobs").mkdir(exist_ok=True)
        (batch / "snapshot").mkdir(exist_ok=True)
        jobseek.write_json(batch / "batch.json", {"batch_id": batch.name, "track": "it", "created_at": "2026-08-03T00:00:00Z"})
        jobseek.write_json(batch / "snapshot/reviewed-url-index.json", {})
        jobseek.write_json(batch / "snapshot/assessment-policy.json", jobseek.assessment_policy(jobseek.workspace_config(), "it"))
        return batch

    def assessed(self, url="https://seek.com.au/job/99", company="Example"):
        return {
            "url": url,
            "company": company,
            "title": "Support Officer",
            "fully_assessed": True,
            "advertisement_markdown": "# Support Officer\n\nComplete advertisement.",
            "assessment": {
                "classification": "Eligible", "reasons": [], "unresolved_items": [], "hard_exclusions": [],
                "assessed_at": "2026-08-03T00:00:00Z", "eligible_threshold": 70, "score_total": 80,
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
        jobseek.command_new_batch(argparse.Namespace(track="it"))
        batch = next(path for path in (self.root / "batches").iterdir() if path.is_dir())
        policy_path = batch / "snapshot/assessment-policy.json"
        policy = jobseek.read_json(policy_path)
        self.assertEqual(policy["eligible_threshold"], 70)
        config = jobseek.read_json(self.root / "config/workspace.json")
        config["eligible_threshold"] = 80
        jobseek.write_json(self.root / "config/workspace.json", config)
        self.assertEqual(jobseek.read_json(policy_path)["eligible_threshold"], 70)

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

    def test_observed_and_historical_duplicates_do_not_use_capacity(self):
        batch = self.make_batch()
        jobseek.write_json(batch / "snapshot/reviewed-url-index.json", {"seek:99": "seek-99"})
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

    def test_merge_caps_fully_assessed_jobs_at_twenty(self):
        batch = self.make_batch()
        rows = [self.assessed(f"https://seek.com.au/job/{number}") for number in range(1, 22)]
        jobseek.write_jsonl(batch / "discovery/a.jsonl", rows)
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertEqual(len(list((batch / "jobs").iterdir())), 20)
        report = jobseek.read_json(batch / "merge-report.json")
        self.assertEqual(len(report["not_merged_due_to_stop_limit"]), 1)

    def test_other_stop_threshold_prevents_merge(self):
        batch = self.make_batch()
        for number in range(5):
            self.add_confirmation(batch, number, "confirmed")
        jobseek.write_jsonl(batch / "discovery/a.jsonl", [self.assessed("https://seek.com.au/job/99")])
        jobseek.command_merge_discovery(argparse.Namespace(batch=batch.name))
        self.assertFalse((batch / "jobs/seek-99").exists())

    def test_snapshot_historical_duplicate_is_never_merged_or_updated(self):
        history = [{
            "job_id": "seek-99", "canonical_url": "https://seek.com.au/job/99",
            "first_reviewed_at": "2026-01-01", "last_reviewed_at": "2026-01-01",
        }]
        jobseek.write_jsonl(self.root / "history/reviewed-jobs.jsonl", history)
        jobseek.rebuild_index()
        batch = self.make_batch()
        jobseek.write_json(batch / "snapshot/reviewed-url-index.json", {"seek:99": "seek-99"})
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

    def test_eligible_below_threshold_is_rejected(self):
        self.assert_invalid_assessment({"score_total": 69})

    def test_eligible_with_unresolved_items_is_rejected(self):
        self.assert_invalid_assessment({"unresolved_items": ["mandatory condition"]})

    def test_naive_assessed_at_is_rejected(self):
        self.assert_invalid_assessment({"assessed_at": "2026-08-03T08:00:00"})

    def test_assessment_threshold_mismatch_is_rejected(self):
        self.assert_invalid_assessment({"eligible_threshold": 80})

    def test_agent_configuration_is_terra_medium_without_overrides(self):
        project = Path(__file__).resolve().parents[1]
        config = (project / ".codex/config.toml").read_text(encoding="utf-8")
        self.assertIn('default_subagent_model = "gpt-5.6-terra"', config)
        self.assertIn('default_subagent_reasoning_effort = "medium"', config)
        self.assertIn("max_depth = 1", config)
        expected = {"jobseek_discovery_assess", "jobseek_audit", "jobseek_materials", "jobseek_submission"}
        self.assertEqual(set(__import__("re").findall(r'^\[agents\.([a-z_]+)\]$', config, __import__("re").MULTILINE)), expected)
        for path in (project / ".codex/agents").glob("*.toml"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("[agents]\nenabled = false", text)
            self.assertNotIn("model =", text)
            self.assertNotIn("reasoning_effort =", text)


if __name__ == "__main__":
    unittest.main()
