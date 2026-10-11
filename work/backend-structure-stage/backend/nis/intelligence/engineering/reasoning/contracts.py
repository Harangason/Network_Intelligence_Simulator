"""Public engineering conclusions, never private model deliberations."""
from enum import StrEnum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

CAPABILITY_VERSION = "engineering-reasoning/1.1"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ObservationType(StrEnum):
    SIGNAL_ANOMALY = "SIGNAL_ANOMALY"
    STATE_CHANGE = "STATE_CHANGE"
    MESSAGE_DELAY = "MESSAGE_DELAY"
    MESSAGE_LOSS = "MESSAGE_LOSS"
    BUS_LOAD_CHANGE = "BUS_LOAD_CHANGE"
    INTERFACE_LOAD_CHANGE = "INTERFACE_LOAD_CHANGE"
    QUEUE_GROWTH = "QUEUE_GROWTH"
    ROUTE_CHANGE = "ROUTE_CHANGE"
    NODE_OFFLINE = "NODE_OFFLINE"
    GATEWAY_DELAY = "GATEWAY_DELAY"
    FAULT_ACTIVE = "FAULT_ACTIVE"
    DEADLINE_MISS = "DEADLINE_MISS"
    TIMING_JITTER = "TIMING_JITTER"
    PAYLOAD_ERROR = "PAYLOAD_ERROR"
    GOLDEN_TRACE_DEVIATION = "GOLDEN_TRACE_DEVIATION"


class EvidenceRef(Contract):
    id: str
    source_type: str
    source_id: str
    simulation_run_id: str
    timestamp: float | None = None
    object_refs: list[dict[str, str]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class Observation(Contract):
    id: str
    type: ObservationType
    timestamp: float
    description: str
    evidence_refs: list[str]
    affected_objects: list[dict[str, str]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    classification: str = "OBSERVED_EFFECT"


class Hypothesis(Contract):
    id: str
    description: str
    status: str
    evidence_refs: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    reason: str
    confidence: float = Field(ge=0, le=1)


class CausalLink(Contract):
    cause: str
    relation: str
    effect: str
    timestamp: float
    evidence_refs: list[str]
    confidence: float = Field(ge=0, le=1)


class SimulationReasoningResult(Contract):
    reasoning_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    simulation_run_id: str
    trace_session_id: str
    goal: str
    observations: list[Observation] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    tested_hypotheses: list[str] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    confirmed_causes: list[str] = Field(default_factory=list)
    causal_chain: list[CausalLink] = Field(default_factory=list)
    downstream_effects: list[dict] = Field(default_factory=list)
    data_gaps: list[dict] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    conclusion: str = "ROOT_CAUSE_UNCONFIRMED"
    confidence: float = Field(default=0, ge=0, le=1)
    confidence_factors: dict = Field(default_factory=dict)
    recommended_actions: list[dict] = Field(default_factory=list)
    findings: list[dict] = Field(default_factory=list)
    validation_status: str = "BLOCKED_BY_DATA_GAP"
    completion_status: str = "INCOMPLETE"
    completion_checks: dict[str, bool] = Field(default_factory=dict)
    lineage: dict = Field(default_factory=dict)
    time_range: dict = Field(default_factory=dict)
    evidence_plan: list[dict] = Field(default_factory=list)
    continuation: dict | None = None
    comparison: dict | None = None


class ReasoningRequest(Contract):
    job_id: str = Field(min_length=1, max_length=200)
    goal: str = Field(default="Technische Ursache im Trace-Zeitfenster untersuchen.", max_length=2000)
    focus_s: float | None = Field(default=None, ge=0)
    start_s: float = Field(default=0, ge=0)
    end_s: float = Field(default=1e15, ge=0)
    cursor: int = Field(default=0, ge=0)
    golden_job_id: str | None = Field(default=None, max_length=200)
    previous_reasoning_id: str | None = None


class ReasoningCompletionEvaluator:
    @staticmethod
    def evaluate(result, inspected):
        checks = {name: bool(inspected.get(name)) for name in (
            "route_inspected", "timing_inspected", "capacity_inspected", "faults_inspected",
            "upstream_dependencies_inspected", "downstream_effects_inspected")}
        checks.update(anomaly_localized=bool(result.observations), hypotheses_evaluated=bool(result.hypotheses),
                      evidence_sufficient=bool(result.confirmed_causes) and not any(g.get("blocking", True) for g in result.data_gaps))
        result.completion_checks = checks
        result.completion_status = "COMPLETE" if all(checks.values()) else "INCOMPLETE"
        if not result.observations and not result.continuation and not any(g.get("blocking", True) for g in result.data_gaps):
            result.completion_status = "NO_ANOMALY_IN_WINDOW"
        result.validation_status = "CURRENT" if not any(g.get("blocking", True) for g in result.data_gaps) else "BLOCKED_BY_DATA_GAP"
        result.confidence_factors = {
            "evidence_completeness": sum(checks.values()) / len(checks),
            "deterministic_validation": bool(result.confirmed_causes),
            "contradicting_evidence": sum(len(h.contradicting_evidence) for h in result.hypotheses),
            "blocking_data_gaps": sum(bool(g.get("blocking", True)) for g in result.data_gaps),
            "model_certainty": 1.0 if inspected.get("snapshot_available") else 0.5,
            "method": "RULE_BASED_EVIDENCE_SCORE_NOT_A_CALIBRATED_PROBABILITY",
        }
        strongest = max((h.confidence for h in result.hypotheses if h.id in result.confirmed_causes), default=0)
        result.confidence = round(strongest * result.confidence_factors["evidence_completeness"]
                                  * (1 if inspected.get("snapshot_available") else .75), 3)
        if result.validation_status == "BLOCKED_BY_DATA_GAP":
            result.confidence = min(result.confidence, .49)
        return result
