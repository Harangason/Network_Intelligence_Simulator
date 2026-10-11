from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..core.completion import CompletionDecision
from ..errors import AgentCoreValidationError


class CompletionValidator:
    """Deterministic completion decision; no language model is consulted."""

    @staticmethod
    def evaluate_total_target(workload: Mapping[str, Any], packages: Sequence[Mapping[str, Any]]) -> bool:
        requested = int(workload.get("requested_total") or workload.get("target_total") or 0)
        return sum(int(item.get("valid_count") or 0) for item in packages) == requested

    @staticmethod
    def evaluate_sub_targets(packages: Sequence[Mapping[str, Any]]) -> bool:
        return bool(packages) and all(
            int(item.get("valid_count") or 0) == int(item.get("requested_count") or 0)
            for item in packages
        )

    @staticmethod
    def evaluate_required_fields(objects: Sequence[Mapping[str, Any]]) -> bool:
        return not any(
            finding.get("code") == "MISSING_FIELD" and str(finding.get("severity") or "ERROR").upper() == "ERROR"
            for item in objects
            for finding in item.get("validation_results") or []
            if isinstance(finding, Mapping)
        )

    @staticmethod
    def evaluate_validation_status(packages: Sequence[Mapping[str, Any]]) -> bool:
        return sum(int(item.get("invalid_count") or 0) for item in packages) == 0

    @staticmethod
    def evaluate_duplicates(packages: Sequence[Mapping[str, Any]]) -> bool:
        return sum(int(item.get("duplicate_count") or 0) for item in packages) == 0

    @staticmethod
    def evaluate_dependencies(dependencies: Sequence[Mapping[str, Any]]) -> bool:
        return all(bool(item.get("satisfied")) for item in dependencies)

    @staticmethod
    def evaluate_blocking_errors(packages: Sequence[Mapping[str, Any]]) -> bool:
        return not any(
            str(item.get("status") or "").upper() == "BLOCKED"
            or any(
                str(finding.get("severity") or "ERROR").upper() == "ERROR"
                and str(finding.get("code") or "").upper().startswith("BLOCKING_")
                for finding in item.get("findings") or []
                if isinstance(finding, Mapping)
            )
            for item in packages
        )

    def evaluate(
        self,
        workload: Mapping[str, Any],
        packages: Sequence[Mapping[str, Any]],
        objects: Sequence[Mapping[str, Any]],
        dependencies: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        dependencies = dependencies or []
        requested = int(workload.get("requested_total") or workload.get("target_total") or 0)
        package_total = sum(int(item.get("requested_count") or 0) for item in packages)
        if package_total != requested:
            raise AgentCoreValidationError(
                f"WORKLOAD_CONFIGURATION_ERROR: package targets total {package_total}, expected {requested}."
            )
        generated = sum(int(item.get("generated_count") or 0) for item in packages)
        valid = sum(int(item.get("valid_count") or 0) for item in packages)
        invalid = sum(int(item.get("invalid_count") or 0) for item in packages)
        duplicates = sum(int(item.get("duplicate_count") or 0) for item in packages)
        missing = sum(max(0, int(item.get("requested_count") or 0) - int(item.get("valid_count") or 0)) for item in packages)
        valid_objects = [item for item in objects if item.get("is_valid") and not item.get("is_duplicate")]
        persisted = all(
            item.get("proposal_id")
            or item.get("canonical_id")
            or str(item.get("review_state") or "").upper() in {"DRAFT", "READY_FOR_REVIEW"}
            for item in valid_objects
        )
        approved = len(valid_objects) >= requested and all(
            item.get("canonical_id") and str(item.get("approval_state") or "").upper() == "APPROVED"
            for item in valid_objects
        )
        checks = {
            "total_target": self.evaluate_total_target(workload, packages),
            "sub_targets": self.evaluate_sub_targets(packages),
            "required_fields": self.evaluate_required_fields(objects),
            "validation_status": self.evaluate_validation_status(packages),
            "duplicates": self.evaluate_duplicates(packages),
            "dependencies": self.evaluate_dependencies(dependencies),
            "blocking_errors": self.evaluate_blocking_errors(packages),
            "objects_persisted": persisted,
        }
        ready = all(checks.values()) and len(valid_objects) >= requested
        current = str(workload.get("status") or "RECEIVED").upper()
        if current in {"PAUSED", "CANCELED", "FAILED"}:
            status = current
        elif not checks["dependencies"] or not checks["blocking_errors"]:
            status = "BLOCKED"
        elif approved and ready:
            status = "COMPLETED"
        elif ready:
            status = "READY_FOR_REVIEW"
        elif int(workload.get("attempts") or 0) >= int(workload.get("max_generation_attempts") or workload.get("max_attempts") or 3):
            status = "INCOMPLETE"
        else:
            status = "IN_PROGRESS"
        metrics = {
            "completion_coverage": 100.0 if requested == 0 else round(valid * 100 / requested, 2),
            "validation_pass_rate": 100.0 if generated == 0 else round(valid * 100 / generated, 2),
            "duplicate_rate": 0.0 if generated == 0 else round(duplicates * 100 / generated, 2),
            "missing_field_rate": 0.0 if generated == 0 else round(
                sum(
                    1
                    for item in objects
                    for finding in item.get("validation_results") or []
                    if isinstance(finding, Mapping) and finding.get("code") == "MISSING_FIELD"
                )
                * 100
                / generated,
                2,
            ),
            "review_acceptance_rate": 100.0 if approved else 0.0,
        }
        decision = CompletionDecision(
            status=status,
            ready_for_review=status == "READY_FOR_REVIEW",
            complete=status == "COMPLETED",
            requested_count=requested,
            generated_count=generated,
            valid_count=valid,
            invalid_count=invalid,
            duplicate_count=duplicates,
            missing_count=missing,
            checks=checks,
            metrics=metrics,
            reasons=[name for name, passed in checks.items() if not passed],
        )
        return decision.as_dict()
