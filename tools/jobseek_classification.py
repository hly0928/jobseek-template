#!/usr/bin/env python3
"""Order-independent classification reduction for validated assessment signals."""
from __future__ import annotations

from typing import Any


MECHANICAL_TERMINALS = {"Duplicate", "Expired", "Withdrawn"}
COMPARISON_RESULTS = {"met", "not_met", "unknown"}
REFEREE_REQUIREMENTS = {
    "none",
    "optional",
    "required_any_professional",
    "current_supervisor_preferred",
    "current_supervisor_mandatory",
    "ambiguous",
}
REFEREE_BLOCKER_REASON = "mandatory_current_supervisor_unavailable"


class ClassificationError(ValueError):
    """Raised when assessment signals cannot be reduced deterministically."""


def reduce_referee_requirement(
    referee: dict[str, Any] | None,
    *,
    ambiguity_resolved: bool = False,
) -> dict[str, Any] | None:
    """Reduce referee requirements once for packet and effective classification."""
    if referee is None:
        return None
    if not isinstance(referee, dict):
        raise ClassificationError("referee_requirement_object_required")
    requirement = referee.get("requirement")
    alternative = referee.get("alternative_permitted")
    availability = referee.get("authoritative_availability")
    if requirement not in REFEREE_REQUIREMENTS:
        raise ClassificationError("invalid_referee_requirement")
    if alternative not in {"yes", "no", "unknown"}:
        raise ClassificationError("invalid_referee_alternative")
    if availability not in {"available", "unavailable", "unknown"}:
        raise ClassificationError("invalid_referee_availability")
    if (
        requirement == "current_supervisor_mandatory"
        and alternative == "no"
        and availability == "unavailable"
    ):
        return {
            "classification": "Blocked",
            "priority": 3,
            "primary_reason": "deterministic_application_blocker",
            "reason_code": REFEREE_BLOCKER_REASON,
        }
    unresolved = (
        requirement == "ambiguous"
        or (
            requirement == "current_supervisor_mandatory"
            and (alternative == "unknown" or availability == "unknown")
        )
    )
    if unresolved and not ambiguity_resolved:
        return {
            "classification": "Needs Review",
            "priority": 4,
            "primary_reason": "referee_requirement_unknown",
            "reason_code": "current_supervisor_requirement_unresolved",
        }
    return None


def reduce_classification(signals: dict[str, Any]) -> dict[str, Any]:
    """Reduce evaluated signals without interpreting advertisements or candidate facts."""
    if not isinstance(signals, dict):
        raise ClassificationError("classification_signals_object_required")

    mechanical = signals.get("mechanical_terminal")
    if mechanical is not None:
        if mechanical not in MECHANICAL_TERMINALS:
            raise ClassificationError("invalid_mechanical_terminal")
        return {
            "classification": mechanical,
            "priority": 1,
            "primary_reason": "mechanical_terminal",
        }

    exclusions = signals.get("hard_exclusions", [])
    if not isinstance(exclusions, list):
        raise ClassificationError("hard_exclusions_array_required")
    established: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for item in exclusions:
        if not isinstance(item, dict):
            raise ClassificationError("hard_exclusion_object_required")
        result = item.get("comparison_result")
        if result not in COMPARISON_RESULTS:
            raise ClassificationError("invalid_hard_exclusion_comparison")
        if result == "not_met":
            established.append(item)
        elif result == "unknown":
            unknown.append(item)

    if established:
        winner = min(established, key=lambda item: str(item.get("rule_id", "")))
        return {
            "classification": "Skipped",
            "priority": 2,
            "primary_reason": "hard_exclusion",
            "rule_id": winner.get("rule_id"),
        }

    referee_result = reduce_referee_requirement(
        signals.get("referee_requirement"),
    )
    if referee_result is not None:
        return referee_result

    sensitive = signals.get("sensitive_review_required", False)
    if not isinstance(sensitive, bool):
        raise ClassificationError("sensitive_review_required_boolean")
    if unknown or sensitive:
        reason = "hard_exclusion_unknown" if unknown else "sensitive_review_required"
        result: dict[str, Any] = {
            "classification": "Needs Review",
            "priority": 4,
            "primary_reason": reason,
        }
        if unknown:
            winner = min(unknown, key=lambda item: str(item.get("rule_id", "")))
            result["rule_id"] = winner.get("rule_id")
        return result

    score = signals.get("score_total")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ClassificationError("score_total_number_required")
    if not 0 <= score <= 100:
        raise ClassificationError("score_total_out_of_range")
    threshold = signals.get("eligible_threshold", 70)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ClassificationError("eligible_threshold_number_required")
    if not 0 <= threshold <= 100:
        raise ClassificationError("eligible_threshold_out_of_range")
    return {
        "classification": "Eligible" if score >= threshold else "Skipped",
        "priority": 5,
        "primary_reason": "score_at_or_above_threshold" if score >= threshold else "score_below_threshold",
    }
