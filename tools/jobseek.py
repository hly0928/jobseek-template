#!/usr/bin/env python3
"""Small file-driven helper for the JobSeek workspace."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT = Path(__file__).resolve().parents[1]
TRACKING_KEYS = {"tracking", "trackingid", "ref", "referrer", "source", "campaign"}
ASSESSMENT_CLASSIFICATIONS = {"Eligible", "Skipped", "Needs Review", "Blocked", "Expired", "Withdrawn"}


class JobSeekError(RuntimeError):
    pass


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value: object) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    atomic_write(path, text)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JobSeekError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise JobSeekError(f"Expected a JSON object in {path}")
    return value


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise JobSeekError(f"Cannot read JSONL {path}: {exc}") from exc
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JobSeekError(f"Invalid JSON at {path}:{number}: {exc}") from exc
        if not isinstance(value, dict):
            raise JobSeekError(f"Expected an object at {path}:{number}")
        rows.append(value)
    return rows


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or "unknown"


def canonicalize_url(raw_url: str) -> dict[str, str | None]:
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise JobSeekError("URL must be a non-empty string")
    candidate = raw_url.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    parsed = urlsplit(candidate)
    host = (parsed.hostname or "").lower()
    if not host:
        raise JobSeekError(f"URL has no host: {raw_url}")
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)

    seek_match = re.search(r"/job/(\d+)(?:/|$)", path, re.IGNORECASE)
    if "seek." in host and seek_match:
        listing_id = seek_match.group(1)
        return {
            "canonical_url": f"https://seek.com.au/job/{listing_id}",
            "identity_key": f"seek:{listing_id}",
            "job_id": f"seek-{listing_id}",
            "source": "SEEK",
            "listing_id": listing_id,
        }

    if "indeed." in host:
        lowered = {key.lower(): value for key, value in query_pairs}
        listing_id = lowered.get("jk") or lowered.get("vjk")
        if listing_id:
            listing_id = re.sub(r"[^A-Za-z0-9_-]", "", listing_id)
            return {
                "canonical_url": f"https://indeed.com/viewjob?jk={listing_id}",
                "identity_key": f"indeed:{listing_id}",
                "job_id": f"indeed-{listing_id}",
                "source": "Indeed",
                "listing_id": listing_id,
            }

    linkedin_match = re.search(r"/jobs/view/(?:.*?-)?(\d+)(?:/|$)", path, re.IGNORECASE)
    if "linkedin." in host and linkedin_match:
        listing_id = linkedin_match.group(1)
        canonical = f"https://linkedin.com/jobs/view/{listing_id}"
        return {
            "canonical_url": canonical,
            "identity_key": f"linkedin:{listing_id}",
            "job_id": f"linkedin-{listing_id}",
            "source": "LinkedIn",
            "listing_id": listing_id,
        }

    cleaned = []
    for key, value in query_pairs:
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_KEYS:
            continue
        cleaned.append((key, value))
    cleaned.sort(key=lambda item: (item[0].lower(), item[0], item[1]))
    normalized_path = path.rstrip("/") or "/"
    port = parsed.port
    netloc = host if port is None else f"{host}:{port}"
    canonical = urlunsplit(("https", netloc, normalized_path, urlencode(cleaned, doseq=True), ""))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    source = host.removeprefix("www.").split(".")[0].title()
    return {
        "canonical_url": canonical,
        "identity_key": f"url:{digest}",
        "job_id": f"url-{digest}",
        "source": source,
        "listing_id": None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attachment_kind(path: Path) -> str | None:
    name = path.name.lower().replace("_", "-")
    if "cover" in name and "letter" in name:
        return "cover-letter"
    if re.search(r"(^|[- ])(?:cv|resume)([- .]|$)", name):
        return "cv"
    return None


def workspace_config() -> dict:
    return read_json(ROOT / "config/workspace.json")


def workspace_timezone(config: dict) -> ZoneInfo:
    name = config.get("timezone")
    if not isinstance(name, str) or not name.strip():
        raise JobSeekError("workspace timezone must be a non-empty IANA timezone")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise JobSeekError(f"Unknown workspace timezone: {name}") from exc


def now_in_workspace_timezone(config: dict) -> dt.datetime:
    return dt.datetime.now(workspace_timezone(config))


def parse_aware_timestamp(value: object) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise JobSeekError("timestamp must be a non-empty ISO 8601 string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        timestamp = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise JobSeekError(f"Invalid ISO 8601 timestamp: {value}") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise JobSeekError("timestamp must include a UTC offset")
    return timestamp


def local_date_for_timestamp(value: object, timezone: ZoneInfo) -> dt.date:
    return parse_aware_timestamp(value).astimezone(timezone).date()


def normalized_workspace_timestamp(value: object, config: dict) -> str:
    return parse_aware_timestamp(value).astimezone(workspace_timezone(config)).isoformat()


def stop_conditions(config: dict) -> dict[str, int]:
    conditions = config.get("stop_conditions")
    required = {
        "max_fully_assessed_ads",
        "target_confirmed_submissions",
        "max_submission_failures",
        "max_manual_takeovers",
    }
    if not isinstance(conditions, dict) or set(conditions) != required:
        raise JobSeekError("stop_conditions must contain exactly the four supported thresholds")
    if any(isinstance(conditions[key], bool) or not isinstance(conditions[key], int) or conditions[key] <= 0 for key in required):
        raise JobSeekError("stop condition thresholds must be positive integers")
    return conditions


def resolve_batch(batch_id: str) -> Path:
    path = ROOT / "batches" / batch_id
    if not path.is_dir() or path.parent != ROOT / "batches":
        raise JobSeekError(f"Unknown batch: {batch_id}")
    return path


def resolve_job(batch_id: str, job_id: str) -> Path:
    batch = resolve_batch(batch_id)
    path = batch / "jobs" / job_id
    if not path.is_dir() or path.parent != batch / "jobs":
        raise JobSeekError(f"Unknown job {job_id} in batch {batch_id}")
    return path


def validate_review(job_dir: Path) -> tuple[str, dict[str, str]]:
    review_path = job_dir / "submission/review.json"
    review = read_json(review_path)
    required = {
        "job_id": str,
        "page_url": str,
        "page_fingerprint": str,
        "answers": dict,
        "declarations": list,
        "selected_attachments": list,
        "reviewed_at": str,
    }
    for field, expected_type in required.items():
        if field not in review or not isinstance(review[field], expected_type):
            raise JobSeekError(f"review.json requires {field} as {expected_type.__name__}")
    if review["job_id"] != job_dir.name:
        raise JobSeekError("review job_id does not match the job directory")
    page = urlsplit(review["page_url"])
    if page.scheme not in {"http", "https"} or not page.netloc:
        raise JobSeekError("review page_url must be an http or https URL")
    if not review["page_fingerprint"].strip():
        raise JobSeekError("review page_fingerprint must be non-empty")
    if not review["reviewed_at"].strip():
        raise JobSeekError("review reviewed_at must be non-empty")
    attachments = review.get("selected_attachments")
    if not attachments:
        raise JobSeekError("review selected_attachments must be non-empty")
    hashes: dict[str, str] = {}
    resolved_paths: set[Path] = set()
    has_cv = False
    root = job_dir.resolve()
    for item in attachments:
        if not isinstance(item, str) or not item.strip():
            raise JobSeekError("selected_attachments entries must be non-empty paths")
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            raise JobSeekError(f"Attachment must be a safe relative path: {item}")
        candidate = job_dir / relative
        source = candidate.resolve()
        if root not in source.parents or not source.is_file() or candidate.is_symlink():
            raise JobSeekError(f"Missing or unsafe selected attachment: {item}")
        if source in resolved_paths:
            raise JobSeekError(f"Duplicate selected attachment: {item}")
        resolved_paths.add(source)
        hashes[item] = sha256_file(source)
        has_cv = has_cv or attachment_kind(source) == "cv"
    if not has_cv:
        raise JobSeekError("review selected_attachments must include a CV")
    review_hash = hashlib.sha256(
        json.dumps(review, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return review_hash, hashes


def approval_matches(job_dir: Path, review_hash: str, hashes: dict[str, str]) -> bool:
    approval_path = job_dir / "submission/approval.json"
    if not approval_path.exists():
        return False
    try:
        approval = read_json(approval_path)
    except JobSeekError:
        return False
    return (
        approval.get("single_job_approval") is True
        and approval.get("job_id") == job_dir.name
        and approval.get("review_hash") == review_hash
        and approval.get("material_sha256") == hashes
    )


def approval_is_valid(job_dir: Path) -> bool:
    try:
        review_hash, hashes = validate_review(job_dir)
    except JobSeekError:
        return False
    return approval_matches(job_dir, review_hash, hashes)


def validate_confirmation(job_dir: Path) -> dict:
    confirmation = read_json(job_dir / "submission/confirmation.json")
    if not isinstance(confirmation.get("review_hash"), str) or not confirmation["review_hash"].strip():
        raise JobSeekError("confirmation review_hash must be non-empty")
    if confirmation.get("status") not in {"confirmed", "not_submitted", "unclear"}:
        raise JobSeekError("confirmation status must be confirmed, not_submitted, or unclear")
    if not isinstance(confirmation.get("submitted_at"), str) or not confirmation["submitted_at"].strip():
        raise JobSeekError("confirmation submitted_at must be non-empty")
    parse_aware_timestamp(confirmation["submitted_at"])
    if "manual_takeover" in confirmation and not isinstance(confirmation["manual_takeover"], bool):
        raise JobSeekError("confirmation manual_takeover must be boolean when present")
    return confirmation


def approval_check(job_dir: Path) -> dict:
    try:
        review_hash, hashes = validate_review(job_dir)
    except JobSeekError:
        return {"ok": False, "allowed": False, "reason": "invalid_review", "review_hash": None}
    if not approval_matches(job_dir, review_hash, hashes):
        return {"ok": True, "allowed": False, "reason": "approval_invalid", "review_hash": review_hash}
    confirmation_path = job_dir / "submission/confirmation.json"
    if confirmation_path.exists():
        try:
            confirmation = validate_confirmation(job_dir)
        except JobSeekError:
            return {"ok": False, "allowed": False, "reason": "invalid_confirmation", "review_hash": review_hash}
        if confirmation["review_hash"] == review_hash:
            return {"ok": True, "allowed": False, "reason": "approval_already_consumed", "review_hash": review_hash}
    return {"ok": True, "allowed": True, "reason": None, "review_hash": review_hash}


def assessment_policy(config: dict, track: str) -> dict:
    tracks = config.get("tracks")
    if not isinstance(tracks, dict) or track not in tracks:
        raise JobSeekError(f"Unknown track: {track}")
    track_config = tracks[track]
    if not isinstance(track_config, dict) or not isinstance(track_config.get("directory"), str):
        raise JobSeekError(f"Invalid track configuration: {track}")
    threshold = config.get("eligible_threshold")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 100:
        raise JobSeekError("eligible_threshold must be a number from 0 to 100")
    exclusions = config.get("hard_exclusions")
    if not isinstance(exclusions, dict) or not exclusions:
        raise JobSeekError("hard_exclusions must be a non-empty object")
    components = config.get("score_components")
    if not isinstance(components, dict) or not components:
        raise JobSeekError("score_components must be a non-empty object")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 for value in components.values()):
        raise JobSeekError("score_components values must be non-negative numbers")
    if sum(components.values()) != 100:
        raise JobSeekError("score_components must total 100")
    scope = track_config.get("scope_exclusions", [])
    if not isinstance(scope, list):
        raise JobSeekError("track scope_exclusions must be an array")
    return {
        "track": track,
        "eligible_threshold": threshold,
        "hard_exclusions": exclusions,
        "score_components": components,
        "track_scope_exclusions": scope,
    }


def assessment_validation_error(assessment: object, policy: dict) -> str | None:
    if not isinstance(assessment, dict):
        return "assessment must be an object"
    classification = assessment.get("classification")
    if classification not in ASSESSMENT_CLASSIFICATIONS:
        return "assessment classification is invalid"
    for field in ("reasons", "unresolved_items", "hard_exclusions"):
        if not isinstance(assessment.get(field), list):
            return f"assessment {field} must be an array"
    try:
        parse_aware_timestamp(assessment.get("assessed_at"))
    except JobSeekError as exc:
        return f"assessment assessed_at is invalid: {exc}"
    if assessment.get("eligible_threshold") != policy.get("eligible_threshold"):
        return "assessment eligible_threshold does not match the batch policy"
    if classification == "Eligible":
        score = assessment.get("score_total")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
            return "Eligible assessment score_total must be a number from 0 to 100"
        if score < policy["eligible_threshold"]:
            return "Eligible assessment score_total is below eligible_threshold"
        if assessment["unresolved_items"]:
            return "Eligible assessment cannot contain unresolved_items"
    return None


def validate_batch_policy(policy: dict, track: object) -> dict:
    required = {"track", "eligible_threshold", "hard_exclusions", "score_components", "track_scope_exclusions"}
    threshold = policy.get("eligible_threshold")
    if (
        set(policy) != required
        or policy.get("track") != track
        or isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not 0 <= threshold <= 100
        or not isinstance(policy.get("hard_exclusions"), dict)
        or not isinstance(policy.get("score_components"), dict)
        or not isinstance(policy.get("track_scope_exclusions"), list)
    ):
        raise JobSeekError("batch assessment policy is invalid")
    return policy


def command_preflight(args: argparse.Namespace) -> None:
    config = workspace_config()
    workspace_timezone(config)
    stop_conditions(config)
    assessment_policy(config, args.track)
    tracks = config["tracks"]
    track_dir = ROOT / tracks[args.track]["directory"]
    if not track_dir.is_dir():
        raise JobSeekError(f"Track directory does not exist: {tracks[args.track]['directory']}")
    index_path = ROOT / config["history"]["reviewed_url_index"]
    if not index_path.is_file():
        raise JobSeekError("Reviewed URL index is missing; run: python3 tools/jobseek.py rebuild-index")
    required = [
        ROOT / "profile/candidate-profile.md",
        ROOT / "profile/cv/base.docx",
        ROOT / "profile/banks/application-answers.md",
        ROOT / "profile/banks/cover-letter-content.md",
        ROOT / tracks[args.track]["directory"] / "profile.md",
        ROOT / tracks[args.track]["directory"] / "search-criteria.md",
        ROOT / tracks[args.track]["directory"] / "answer-overrides.md",
        ROOT / config["history"]["reviewed_jobs"],
        index_path,
        ROOT / config["archive"]["applications_index"],
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise JobSeekError("Missing required inputs: " + ", ".join(missing))
    for path in required[:7]:
        if path.suffix.lower() == ".md":
            text = path.read_text(encoding="utf-8")
            if not text.strip() or re.search(
                r"\b(?:TODO|TBD|PLACEHOLDER)\b|\{\{[^}]+\}\}|<placeholder(?:\s[^>]*)?>",
                text,
                re.IGNORECASE,
            ):
                raise JobSeekError(f"Empty or placeholder content in {path.relative_to(ROOT)}")
    try:
        with zipfile.ZipFile(ROOT / "profile/cv/base.docx") as archive:
            if "word/document.xml" not in archive.namelist():
                raise JobSeekError("base.docx is not a readable Word document")
    except (OSError, zipfile.BadZipFile) as exc:
        raise JobSeekError(f"base.docx is not readable: {exc}") from exc
    history_rows = read_jsonl(ROOT / config["history"]["reviewed_jobs"])
    application_rows = read_jsonl(ROOT / config["archive"]["applications_index"])
    identities: dict[str, dict] = {}
    job_ids: set[str] = set()
    for row in history_rows:
        canonical = canonicalize_url(row.get("canonical_url", ""))
        if row.get("canonical_url") != canonical["canonical_url"]:
            raise JobSeekError(f"History URL is not canonical: {row.get('job_id')}")
        if canonical["job_id"] != row.get("job_id"):
            raise JobSeekError(f"History job_id mismatch: {row.get('job_id')}")
        if row["job_id"] in job_ids:
            raise JobSeekError(f"Duplicate reviewed job_id: {row['job_id']}")
        if canonical["identity_key"] in identities:
            raise JobSeekError(f"Duplicate reviewed identity: {canonical['identity_key']}")
        job_ids.add(row["job_id"])
        identities[str(canonical["identity_key"])] = row
    expected_index = dict(sorted((key, row["job_id"]) for key, row in identities.items()))
    try:
        actual_index = read_json(index_path)
    except JobSeekError as exc:
        raise JobSeekError("Reviewed URL index is invalid; run: python3 tools/jobseek.py rebuild-index") from exc
    if actual_index != expected_index:
        raise JobSeekError("Reviewed URL index is stale; run: python3 tools/jobseek.py rebuild-index")
    application_ids = [row.get("application_id") for row in application_rows]
    if len(application_ids) != len(set(application_ids)):
        raise JobSeekError("Duplicate application_id in archive index")
    archive_paths = [row.get("archive_path") for row in application_rows]
    if len(archive_paths) != len(set(archive_paths)):
        raise JobSeekError("Duplicate archive_path in archive index")
    archive_root = (ROOT / config["archive"]["applications_directory"]).resolve()
    allowed_name = re.compile(r"(?:advertisement\.md|cv(?:-\d+)?\.[A-Za-z0-9]+|cover-letter(?:-\d+)?\.[A-Za-z0-9]+)")
    for row in application_rows:
        archive_value = row.get("archive_path")
        if not isinstance(archive_value, str):
            raise JobSeekError(f"Invalid archive_path for {row.get('application_id')}")
        archive_dir = (ROOT / archive_value).resolve()
        if archive_root not in archive_dir.parents or not archive_dir.is_dir():
            raise JobSeekError(f"Missing application archive: {archive_value}")
        files = [path for path in archive_dir.iterdir() if path.is_file()]
        names = {path.name for path in files}
        if "advertisement.md" not in names or not any(attachment_kind(path) == "cv" for path in files):
            raise JobSeekError(f"Application archive requires advertisement and CV: {archive_value}")
        if any(path.is_symlink() or not path.is_file() or not allowed_name.fullmatch(path.name) for path in archive_dir.iterdir()):
            raise JobSeekError(f"Unexpected file in application archive: {archive_value}")
        canonical = canonicalize_url(row.get("canonical_url", ""))
        if row.get("canonical_url") != canonical["canonical_url"]:
            raise JobSeekError(f"Application URL is not canonical: {row.get('application_id')}")
        reviewed = identities.get(str(canonical["identity_key"]))
        if reviewed is None or reviewed.get("job_id") != row.get("job_id"):
            raise JobSeekError(f"Application is missing from reviewed history: {row.get('application_id')}")
        if reviewed.get("outcome") != "applied" or reviewed.get("application_id") != row.get("application_id"):
            raise JobSeekError(f"Application history link is inconsistent: {row.get('application_id')}")
    print(f"preflight ok: {args.track} ({len(history_rows)} reviewed jobs, {len(application_rows)} applications)")


def command_new_batch(args: argparse.Namespace) -> None:
    command_preflight(args)
    config = workspace_config()
    policy = assessment_policy(config, args.track)
    created_at = now_in_workspace_timezone(config)
    today = created_at.date().isoformat()
    prefix = f"{today}__{args.track}__"
    existing = [p.name for p in (ROOT / "batches").glob(prefix + "*") if p.is_dir()]
    sequences = [int(name.rsplit("__", 1)[1]) for name in existing if name.rsplit("__", 1)[1].isdigit()]
    batch_id = prefix + f"{(max(sequences, default=0) + 1):03d}"
    batch = ROOT / "batches" / batch_id
    snapshot = batch / "snapshot"
    discovery = batch / "discovery"
    jobs = batch / "jobs"
    snapshot.mkdir(parents=True)
    discovery.mkdir()
    jobs.mkdir()
    track_dir = ROOT / config["tracks"][args.track]["directory"]
    copies = {
        ROOT / "profile/candidate-profile.md": snapshot / "candidate-profile.md",
        track_dir / "profile.md": snapshot / "track-profile.md",
        track_dir / "search-criteria.md": snapshot / "search-criteria.md",
        track_dir / "answer-overrides.md": snapshot / "answer-overrides.md",
        ROOT / "profile/banks/application-answers.md": snapshot / "answer-bank.md",
        ROOT / "profile/banks/cover-letter-content.md": snapshot / "cover-letter-bank.md",
        ROOT / "profile/cv/base.docx": snapshot / "base-cv.docx",
        ROOT / config["history"]["reviewed_url_index"]: snapshot / "reviewed-url-index.json",
    }
    for source, destination in copies.items():
        shutil.copy2(source, destination)
    write_json(snapshot / "assessment-policy.json", policy)
    write_json(batch / "batch.json", {"batch_id": batch_id, "created_at": created_at.isoformat(), "track": args.track})
    print(batch_id)


def rebuild_index() -> dict[str, str]:
    config = workspace_config()
    history_path = ROOT / config["history"]["reviewed_jobs"]
    rows = read_jsonl(history_path)
    index: dict[str, str] = {}
    for row in rows:
        canonical = canonicalize_url(row.get("canonical_url", ""))
        key = str(canonical["identity_key"])
        job_id = str(canonical["job_id"])
        if row.get("job_id") != job_id:
            raise JobSeekError(f"History job_id mismatch for {row.get('canonical_url')}")
        if key in index and index[key] != job_id:
            raise JobSeekError(f"Duplicate reviewed identity: {key}")
        index[key] = job_id
    applications = read_jsonl(ROOT / config["archive"]["applications_index"])
    reviewed_urls = {row.get("canonical_url") for row in rows}
    missing = [row.get("application_id") for row in applications if row.get("canonical_url") not in reviewed_urls]
    if missing:
        raise JobSeekError("Application URLs missing from reviewed history: " + ", ".join(map(str, missing)))
    ordered = dict(sorted(index.items()))
    write_json(ROOT / config["history"]["reviewed_url_index"], ordered)
    return ordered


def command_rebuild_index(_args: argparse.Namespace) -> None:
    index = rebuild_index()
    print(f"rebuilt {len(index)} reviewed URL identities")


def history_outcome(classification: str) -> str:
    mapping = {
        "eligible": "eligible", "skipped": "skipped", "needs review": "needs_review",
        "blocked": "blocked", "expired": "expired", "withdrawn": "withdrawn",
    }
    return mapping.get(classification.strip().lower(), "needs_review")


def discovery_priority(row: dict, policy: dict) -> int:
    advertisement = row.get("advertisement_markdown")
    assessment = row.get("assessment")
    fully_assessed = (
        row.get("fully_assessed") is True
        and isinstance(advertisement, str)
        and bool(advertisement.strip())
        and assessment_validation_error(assessment, policy) is None
    )
    if fully_assessed:
        return 0
    if row.get("full_ad_opened") is True or (isinstance(advertisement, str) and bool(advertisement.strip())):
        return 1
    duplicate_values = {str(row.get(field, "")).lower() for field in ("result", "status", "outcome", "classification")}
    if "duplicate" in duplicate_values or any(row.get(field) for field in ("duplicate_of", "history_duplicate", "batch_duplicate")):
        return 2
    if row.get("observed") is True or row.get("url") or row.get("canonical_url"):
        return 3
    return 4


def batch_stop_status(batch: Path, config: dict | None = None) -> dict:
    config = config or workspace_config()
    limits = stop_conditions(config)
    track = read_json(batch / "batch.json").get("track")
    policy = validate_batch_policy(read_json(batch / "snapshot/assessment-policy.json"), track)
    fully_assessed = confirmed = failures = takeovers = 0
    jobs_dir = batch / "jobs"
    for job_dir in sorted(jobs_dir.iterdir() if jobs_dir.is_dir() else []):
        if not job_dir.is_dir():
            continue
        try:
            job = read_json(job_dir / "job.json")
            assessment = read_json(job_dir / "assessment.json")
            advertisement = (job_dir / "advertisement.md").read_text(encoding="utf-8")
            if job.get("fully_assessed") is True and advertisement.strip() and assessment_validation_error(assessment, policy) is None:
                fully_assessed += 1
        except (JobSeekError, OSError):
            pass
        confirmation_path = job_dir / "submission/confirmation.json"
        if confirmation_path.is_file():
            try:
                confirmation = validate_confirmation(job_dir)
            except JobSeekError:
                continue
            confirmed += confirmation["status"] == "confirmed"
            failures += confirmation["status"] == "not_submitted" and confirmation.get("reason_code") == "submission_failure"
            takeovers += confirmation.get("manual_takeover") is True
    reasons = []
    if fully_assessed >= limits["max_fully_assessed_ads"]:
        reasons.append("max_fully_assessed_ads_reached")
    if confirmed >= limits["target_confirmed_submissions"]:
        reasons.append("target_confirmed_submissions_reached")
    if failures >= limits["max_submission_failures"]:
        reasons.append("max_submission_failures_reached")
    if takeovers >= limits["max_manual_takeovers"]:
        reasons.append("max_manual_takeovers_reached")
    return {
        "fully_assessed_ads": fully_assessed,
        "confirmed_submissions": confirmed,
        "submission_failures": failures,
        "manual_takeovers": takeovers,
        "remaining_assessment_capacity": max(0, limits["max_fully_assessed_ads"] - fully_assessed),
        "discovery_should_stop": bool(reasons),
        "batch_should_stop": bool(reasons),
        "stop_reasons": reasons,
    }


def command_merge_discovery(args: argparse.Namespace) -> None:
    batch = resolve_batch(args.batch)
    batch_meta = read_json(batch / "batch.json")
    track = batch_meta.get("track")
    config = workspace_config()
    if track not in config.get("tracks", {}):
        raise JobSeekError("batch.json contains an unknown track")
    policy = validate_batch_policy(read_json(batch / "snapshot/assessment-policy.json"), track)
    snapshot_index = read_json(batch / "snapshot/reviewed-url-index.json")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in snapshot_index.items()):
        raise JobSeekError("batch reviewed URL snapshot is invalid")
    candidates: list[tuple[str, int, dict, dict]] = []
    for output in sorted((batch / "discovery").glob("*.jsonl")):
        for number, row in enumerate(read_jsonl(output), 1):
            url = row.get("url") or row.get("canonical_url")
            if not url:
                continue
            canonical = canonicalize_url(url)
            candidates.append((output.name, number, row, canonical))
    candidates.sort(key=lambda item: (str(item[3]["identity_key"]), discovery_priority(item[2], policy), item[0], item[1]))
    selected: dict[str, tuple[str, int, dict, dict]] = {}
    duplicates = []
    historical_duplicates = []
    validation_errors = []
    for item in candidates:
        key = str(item[3]["identity_key"])
        if key in snapshot_index:
            historical_duplicates.append({"identity_key": key, "source_file": item[0], "reason": "present_in_batch_snapshot"})
            continue
        if item[2].get("fully_assessed") is True:
            advertisement = item[2].get("advertisement_markdown")
            error = None if isinstance(advertisement, str) and advertisement.strip() else "advertisement_markdown must be non-empty"
            error = error or assessment_validation_error(item[2].get("assessment"), policy)
            if error:
                validation_errors.append({"identity_key": key, "source_file": item[0], "line": item[1], "error": error})
        if key in selected:
            winner = selected[key]
            duplicates.append({
                "identity_key": key,
                "kept": winner[0],
                "kept_line": winner[1],
                "duplicate": item[0],
                "line": item[1],
            })
            continue
        selected[key] = item
    history_path = ROOT / config["history"]["reviewed_jobs"]
    history = read_jsonl(history_path)
    history_by_key = {str(canonicalize_url(row["canonical_url"])["identity_key"]): row for row in history}
    stop_status = batch_stop_status(batch, config)
    remaining = stop_status["remaining_assessment_capacity"]
    stop_reason = stop_status["stop_reasons"][0] if stop_status["stop_reasons"] else None
    not_merged = []
    added = 0
    for key, (filename, _number, row, canonical) in sorted(selected.items()):
        if discovery_priority(row, policy) != 0:
            continue
        job_id = str(canonical["job_id"])
        job_dir = batch / "jobs" / job_id
        try:
            existing_job = read_json(job_dir / "job.json")
            existing_assessment = read_json(job_dir / "assessment.json")
            existing_advertisement = (job_dir / "advertisement.md").read_text(encoding="utf-8")
            if (
                existing_job.get("fully_assessed") is True
                and existing_advertisement.strip()
                and assessment_validation_error(existing_assessment, policy) is None
            ):
                continue
        except (JobSeekError, OSError):
            pass
        if stop_reason or remaining <= 0:
            not_merged.append({
                "identity_key": key,
                "source_file": filename,
                "reason": stop_reason or "max_fully_assessed_ads_reached",
            })
            continue
        remaining -= 1
        job_dir.mkdir(parents=True, exist_ok=True)
        advertisement = row["advertisement_markdown"]
        atomic_write(job_dir / "advertisement.md", advertisement.rstrip() + "\n")
        assessment = dict(row["assessment"])
        assessment["job_id"] = job_id
        assessment["assessed_at"] = normalized_workspace_timestamp(assessment["assessed_at"], config)
        write_json(job_dir / "assessment.json", assessment)
        write_json(job_dir / "job.json", {
            "job_id": job_id,
            "canonical_url": canonical["canonical_url"],
            "company": row.get("company"),
            "title": row.get("title"),
            "source": row.get("source") or canonical["source"],
            "track": track,
            "status": "assessed",
            "fully_assessed": True,
        })
        reviewed_at = normalized_workspace_timestamp(assessment["assessed_at"], config)
        existing = history_by_key.get(key)
        alias_set = set(row.get("url_aliases") or []) | {str(row.get("url") or row.get("canonical_url"))}
        if existing:
            alias_set.update(existing.get("url_aliases") or [])
            existing["url_aliases"] = sorted(alias_set - {str(canonical["canonical_url"])})
            existing["last_reviewed_at"] = max(str(existing.get("last_reviewed_at") or reviewed_at), str(reviewed_at))
        else:
            history_by_key[key] = {
                "job_id": job_id,
                "canonical_url": canonical["canonical_url"],
                "url_aliases": sorted(alias_set - {str(canonical["canonical_url"])}),
                "source": row.get("source") or canonical["source"],
                "listing_id": canonical["listing_id"],
                "company": row.get("company"),
                "title": row.get("title"),
                "tracks": [track],
                "first_reviewed_at": reviewed_at,
                "last_reviewed_at": reviewed_at,
                "outcome": history_outcome(str(assessment.get("classification", "Needs Review"))),
                "reason": (assessment.get("reasons") or [None])[0],
                "application_id": None,
            }
            added += 1
    rows = sorted(history_by_key.values(), key=lambda row: row["job_id"])
    write_jsonl(history_path, rows)
    rebuild_index()
    write_json(batch / "merge-report.json", {
        "fully_assessed_jobs_added": added,
        "cross_worker_duplicates": duplicates,
        "historical_duplicates": historical_duplicates,
        "not_merged_due_to_stop_limit": not_merged,
        "validation_errors": validation_errors,
    })
    print(f"merged {len(selected)} identities; added {added} reviewed jobs; {len(duplicates)} cross-worker duplicates")


def derive_job_status(job_dir: Path) -> str:
    archive_marker = job_dir / "archived.json"
    if archive_marker.exists():
        return "archived"
    confirmation_path = job_dir / "submission/confirmation.json"
    if confirmation_path.exists():
        confirmation = read_json(confirmation_path)
        if confirmation.get("status") == "confirmed":
            return "confirmed and ready to archive"
        if confirmation.get("status") == "unclear":
            return "submitted but unclear"
        if confirmation.get("status") == "not_submitted":
            return "waiting user review"
    if approval_is_valid(job_dir):
        return "approved"
    if (job_dir / "submission/review.json").exists():
        return "waiting user review"
    materials = job_dir / "materials"
    if materials.is_dir() and any(path.is_file() for path in materials.rglob("*")):
        return "materials prepared"
    if (job_dir / "audit.json").exists():
        audit = read_json(job_dir / "audit.json")
        outcome = audit.get("outcome")
        remaining_items = audit.get("remaining_items")
        if outcome == "Eligible" and not remaining_items:
            return "ready for materials"
        if outcome in {"Skipped", "Blocked", "Expired", "Withdrawn"} and not remaining_items:
            return "assessed"
        return "waiting audit"
    assessment_path = job_dir / "assessment.json"
    if assessment_path.exists():
        assessment = read_json(assessment_path)
        if assessment.get("audit_required") or assessment.get("unresolved_items"):
            return "waiting audit"
        if assessment.get("classification") == "Eligible":
            return "ready for materials"
        return "assessed"
    return "discovered"


def command_status(args: argparse.Namespace) -> None:
    batch = resolve_batch(args.batch)
    rows = []
    for job_dir in sorted((batch / "jobs").iterdir() if (batch / "jobs").is_dir() else []):
        if job_dir.is_dir():
            rows.append({"job_id": job_dir.name, "status": derive_job_status(job_dir)})
    result = {"batch_id": args.batch, "jobs": rows, **batch_stop_status(batch)}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def command_approve(args: argparse.Namespace) -> None:
    job_dir = resolve_job(args.batch, args.job)
    review_hash, hashes = validate_review(job_dir)
    write_json(job_dir / "submission/approval.json", {
        "job_id": args.job,
        "review_hash": review_hash,
        "material_sha256": hashes,
        "approved_at": now_in_workspace_timezone(workspace_config()).isoformat(),
        "single_job_approval": True,
    })
    print(f"approved {args.job} review {review_hash}")


def command_check_approval(args: argparse.Namespace) -> None:
    job_dir = resolve_job(args.batch, args.job)
    print(json.dumps(approval_check(job_dir), ensure_ascii=False, sort_keys=True))


def archive_attachment_name(kind: str, source: Path, used: set[str]) -> str:
    extension = source.suffix.lower() or ".bin"
    base = f"{kind}{extension}"
    if base not in used:
        used.add(base)
        return base
    number = 2
    while f"{kind}-{number}{extension}" in used:
        number += 1
    name = f"{kind}-{number}{extension}"
    used.add(name)
    return name


def command_archive(args: argparse.Namespace) -> None:
    job_dir = resolve_job(args.batch, args.job)
    review_hash, hashes = validate_review(job_dir)
    confirmation = validate_confirmation(job_dir)
    if confirmation.get("status") != "confirmed":
        raise JobSeekError("Archive requires confirmation.json status == confirmed")
    if confirmation["review_hash"] != review_hash:
        raise JobSeekError("Confirmation does not match the current review")
    if not approval_matches(job_dir, review_hash, hashes):
        raise JobSeekError("Approval did not match the confirmed review and attachments")
    job = read_json(job_dir / "job.json")
    if job.get("job_id") != args.job:
        raise JobSeekError("job.json does not match the job directory")
    config = workspace_config()
    applied_date = local_date_for_timestamp(confirmation["submitted_at"], workspace_timezone(config)).isoformat()
    application_id = f"{applied_date}__{args.job}"
    index_path = ROOT / config["archive"]["applications_index"]
    applications = read_jsonl(index_path)
    archive_rel = Path(config["archive"]["applications_directory"]) / (
        f"{application_id}__{slug(str(job.get('company') or 'unknown'))}__{slug(str(job.get('title') or 'unknown'))}"
    )
    destination = ROOT / archive_rel
    advertisement = job_dir / "advertisement.md"
    if not advertisement.is_file() or advertisement.is_symlink():
        raise JobSeekError("Cannot archive without advertisement.md")
    review = read_json(job_dir / "submission/review.json")
    used = {"advertisement.md"}
    expected_files: dict[str, Path] = {"advertisement.md": advertisement}
    for item in review["selected_attachments"]:
        source = (job_dir / item).resolve()
        kind = attachment_kind(source)
        if kind is None:
            continue
        expected_files[archive_attachment_name(kind, source, used)] = source
    canonical = canonicalize_url(str(job["canonical_url"]))
    row = {
        "application_id": application_id,
        "applied_date": applied_date,
        "job_id": args.job,
        "company": job.get("company"),
        "title": job.get("title"),
        "track": job.get("track"),
        "source": job.get("source") or canonical["source"],
        "canonical_url": canonical["canonical_url"],
        "archive_path": archive_rel.as_posix(),
    }
    history_path = ROOT / config["history"]["reviewed_jobs"]
    history = read_jsonl(history_path)
    reviewed_matches = [item for item in history if item.get("job_id") == args.job]
    if len(reviewed_matches) != 1:
        raise JobSeekError("Archived application has no reviewed history record")
    reviewed = reviewed_matches[0]
    if reviewed.get("outcome") == "applied" and reviewed.get("application_id") != application_id:
        raise JobSeekError("Reviewed history is linked to a different application")
    same_id = [item for item in applications if item.get("application_id") == application_id]
    if any(item != row for item in same_id):
        raise JobSeekError("Application ID conflicts with different archive metadata")
    if any(item.get("archive_path") == row["archive_path"] and item.get("application_id") != application_id for item in applications):
        raise JobSeekError("Archive path is already linked to a different application")
    existing_index = same_id[0] if same_id else None

    def archive_matches(path: Path) -> bool:
        if not path.is_dir():
            return False
        contents = {item.name: item for item in path.iterdir()}
        if set(contents) != set(expected_files):
            return False
        return all(
            destination_file.is_file()
            and not destination_file.is_symlink()
            and sha256_file(destination_file) == sha256_file(source)
            for name, source in expected_files.items()
            for destination_file in [contents[name]]
        )

    if destination.exists():
        if not archive_matches(destination):
            raise JobSeekError("Existing application archive conflicts with the confirmed files")
    else:
        if existing_index is not None:
            raise JobSeekError("Application index exists but archive directory is missing")
        archive_root = ROOT / config["archive"]["applications_directory"]
        archive_root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".tmp-{application_id}-", dir=archive_root))
        try:
            for name, source in expected_files.items():
                shutil.copy2(source, temporary / name)
            if not archive_matches(temporary):
                raise JobSeekError("Temporary application archive validation failed")
            try:
                os.replace(temporary, destination)
            except OSError as exc:
                if not destination.exists() or not archive_matches(destination):
                    raise JobSeekError(f"Cannot finalize application archive: {exc}") from exc
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    if existing_index is None:
        applications.append(row)
        write_jsonl(index_path, sorted(applications, key=lambda item: item["application_id"]))
    if reviewed.get("outcome") != "applied" or reviewed.get("application_id") != application_id:
        reviewed["outcome"] = "applied"
        reviewed["application_id"] = application_id
        write_jsonl(history_path, sorted(history, key=lambda item: item["job_id"]))
    write_json(job_dir / "archived.json", {
        "application_id": application_id,
        "archive_path": archive_rel.as_posix(),
        "archived_at": now_in_workspace_timezone(config).isoformat(),
    })
    print(application_id)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--track", required=True)
    preflight.set_defaults(func=command_preflight)
    new_batch = sub.add_parser("new-batch")
    new_batch.add_argument("--track", required=True)
    new_batch.set_defaults(func=command_new_batch)
    rebuild = sub.add_parser("rebuild-index")
    rebuild.set_defaults(func=command_rebuild_index)
    merge = sub.add_parser("merge-discovery")
    merge.add_argument("--batch", required=True)
    merge.set_defaults(func=command_merge_discovery)
    status = sub.add_parser("status")
    status.add_argument("--batch", required=True)
    status.set_defaults(func=command_status)
    approve = sub.add_parser("approve")
    approve.add_argument("--batch", required=True)
    approve.add_argument("--job", required=True)
    approve.set_defaults(func=command_approve)
    check_approval = sub.add_parser("check-approval")
    check_approval.add_argument("--batch", required=True)
    check_approval.add_argument("--job", required=True)
    check_approval.set_defaults(func=command_check_approval)
    archive = sub.add_parser("archive")
    archive.add_argument("--batch", required=True)
    archive.add_argument("--job", required=True)
    archive.set_defaults(func=command_archive)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.func(args)
    except JobSeekError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
