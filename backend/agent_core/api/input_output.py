"""Versioned data contracts. Envelopes describe work; they never grant authority."""
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator

INPUT_TYPES = ('TEXT', 'STRUCTURED_DATA', 'FILE', 'IMAGE', 'TABLE', 'MODEL_OBJECT',
               'SELECTION', 'EVENT', 'TRACE', 'SIMULATION_RESULT', 'USER_DECISION', 'MCP_RESULT')
SUPPORTED_INPUTS = ('TEXT', 'FILE', 'MODEL_OBJECT', 'SELECTION', 'USER_DECISION')


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class AgentInputEnvelope(Contract):
    schema_version: Literal[1] = 1
    input_id: str = Field(default_factory=lambda: str(uuid4()))
    input_type: Literal['TEXT', 'STRUCTURED_DATA', 'FILE', 'IMAGE', 'TABLE', 'MODEL_OBJECT',
                        'SELECTION', 'EVENT', 'TRACE', 'SIMULATION_RESULT', 'USER_DECISION', 'MCP_RESULT']
    content: Any
    project_ref: str = Field(min_length=1)
    run_ref: str
    operation_ref: str | None = None
    request_revision: str | None = None
    selected_objects: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    active_view: str = 'model'
    files: list[dict[str, Any]] = Field(default_factory=list, max_length=4)
    user_intent: str = ''
    constraints: list[str] = Field(default_factory=list)
    source: str = 'conversation'
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TypingResult(Contract):
    input_ref: str
    intent: str = 'INSPECT'
    engineering_type: str | None = None
    semantic_type: str | None = None
    device_type: str | None = None
    device_class: str | None = None
    data_complexity: str | None = None
    unit: str | None = None
    behavior_type: str | None = None
    matched_object_ref: str | None = None
    candidate_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    source: str = 'UNRESOLVED'
    evidence_refs: list[str] = Field(default_factory=list)
    clarification_required: bool = False


class VisualizationNode(Contract):
    id: str
    label: str
    object_type: str


class VisualizationEdge(Contract):
    source: str
    target: str
    label: str = ''
    evidence_ref: str


class VisualizationRequest(Contract):
    visualization_type: Literal['NETWORK_DIAGRAM', 'TABLE']
    purpose: str
    source_revision: str
    nodes: list[VisualizationNode] = Field(default_factory=list, max_length=200)
    relationships: list[VisualizationEdge] = Field(default_factory=list, max_length=400)
    columns: list[str] = Field(default_factory=list, max_length=12)
    rows: list[list[str]] = Field(default_factory=list, max_length=200)
    total_objects: int = Field(default=0, ge=0)
    truncated: bool = False

    @model_validator(mode='after')
    def valid_references(self):
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)) or any(e.source not in ids or e.target not in ids for e in self.relationships):
            raise ValueError('Diagramm enthält ungültige Objektbezüge.')
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError('Tabellenzeilen müssen zum Spaltenvertrag passen.')
        return self


class AgentOutputEnvelope(Contract):
    schema_version: Literal[1] = 1
    output_id: str
    output_type: Literal['CHAT', 'QUESTION', 'MODEL_CHANGE', 'FINDING', 'PROPOSAL', 'TABLE',
        'GRAPH', 'DIAGRAM', 'CHART', 'TRACE_VIEW', 'FILE', 'REPORT', 'CODE', 'SIMULATION',
        'MCP_RESPONSE', 'CALCULATION', 'VALIDATION', 'VISUALIZATION']
    status: str
    project_ref: str
    run_ref: str
    content: str = ''
    affected_objects: list[str] = Field(default_factory=list, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=500)
    visualization: VisualizationRequest | None = None
    validation: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class EngineeringReasoningResult(Contract):
    goal: str
    observations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    data_gaps: list[dict[str, Any]] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    required_decisions: list[str] = Field(default_factory=list)
    decision_type: Literal['DETERMINISTIC', 'POLICY_DEFINED', 'ENGINEERING_DECISION']
    completion_criteria: list[str] = Field(default_factory=list)
    status: str
