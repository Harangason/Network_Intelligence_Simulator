"""Data contracts. Model facts, user authority and execution evidence are distinct."""
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class GoalType(StrEnum):
    CREATE_ARCHITECTURE = 'CREATE_ARCHITECTURE'
    CONNECT_FUNCTIONS = 'CONNECT_FUNCTIONS'
    CONNECT_HARDWARE = 'CONNECT_HARDWARE'
    ADD_NETWORK = 'ADD_NETWORK'
    CHANGE_ROUTE = 'CHANGE_ROUTE'
    OPTIMIZE_NETWORK = 'OPTIMIZE_NETWORK'
    FIX_VALIDATION = 'FIX_VALIDATION'
    SIMULATE_SCENARIO = 'SIMULATE_SCENARIO'
    ANALYZE_TRACE = 'ANALYZE_TRACE'
    FIX_TRACE_ROOT_CAUSE = 'FIX_TRACE_ROOT_CAUSE'
    COMPARE_ARCHITECTURES = 'COMPARE_ARCHITECTURES'


CONNECTION_CRITERIA = ['source_resolved', 'target_resolved', 'hosts_resolved', 'payload_identified',
    'functional_relationship', 'capability_valid', 'controller_valid', 'channel_valid', 'interface_valid',
    'port_valid', 'network_membership_valid', 'technology_binding_valid', 'transport_valid',
    'identifiers_valid', 'address_valid', 'routing_valid', 'capacity_valid', 'timing_valid',
    'preflight_valid', 'projections_current', 'stale_results_invalidated']
COMPLETION_CONTRACTS = {
    **{kind: CONNECTION_CRITERIA for kind in (GoalType.CONNECT_FUNCTIONS, GoalType.CONNECT_HARDWARE, GoalType.CHANGE_ROUTE)},
    GoalType.CREATE_ARCHITECTURE: ['model_valid', 'topology_valid', 'routing_valid', 'capacity_valid', 'timing_valid', 'preflight_valid'],
    GoalType.ADD_NETWORK: ['network_membership_valid', 'technology_binding_valid', 'capacity_valid', 'timing_valid', 'preflight_valid'],
    GoalType.OPTIMIZE_NETWORK: ['objective_improved', 'semantics_preserved', 'capacity_valid', 'timing_valid', 'preflight_valid'],
    GoalType.FIX_VALIDATION: ['target_findings_resolved', 'no_new_blockers', 'preflight_valid'],
    GoalType.SIMULATE_SCENARIO: ['preflight_valid', 'snapshot_current', 'simulation_complete', 'communication_observed'],
    GoalType.ANALYZE_TRACE: ['trace_identity_valid', 'analysis_complete', 'evidence_current'],
    GoalType.FIX_TRACE_ROOT_CAUSE: ['cause_supported', 'target_findings_resolved', 'simulation_complete', 'comparison_passed'],
    GoalType.COMPARE_ARCHITECTURES: ['baselines_valid', 'same_requirements', 'comparison_complete'],
}


class CommunicationCapability(Contract):
    id: str
    hardware_node_ref: str
    technology: str
    supported: bool
    controller_count: int = Field(ge=0)
    max_channels: int = Field(ge=0)
    max_ports: int = Field(ge=0)
    supported_bitrates: list[float] = Field(default_factory=list)
    supported_modes: list[str] = Field(default_factory=list)
    redundancy_support: bool = False
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class CommunicationController(Contract):
    id: str
    hardware_node_ref: str
    technology: str
    max_channels: int = Field(ge=0)
    active_channels: list[int] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    status: Literal['ACTIVE', 'PLANNED', 'UNAVAILABLE', 'OUTDATED'] = 'ACTIVE'
    provenance: dict[str, Any] = Field(default_factory=dict)


class PhysicalPort(Contract):
    id: str
    hardware_node_ref: str
    controller_ref: str | None
    hardware_interface_ref: str
    technology: str
    channel_index: int | None = Field(default=None, ge=1)
    direction: Literal['BIDIRECTIONAL', 'INPUT', 'OUTPUT'] = 'BIDIRECTIONAL'
    network_ref: str | None = None
    connection_status: Literal['FREE', 'CONNECTED', 'OUTDATED'] = 'FREE'
    provenance: dict[str, Any] = Field(default_factory=dict)


class NetworkConnection(Contract):
    connection_id: str
    port_ref: str
    network_ref: str
    technology_binding_ref: str
    status: Literal['ACTIVE', 'OUTDATED', 'SUPERSEDED'] = 'ACTIVE'
    created_by: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class PortDecision(Contract):
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    hardware_node_ref: str
    technology: str
    controller_ref: str | None = None
    existing_interface_ref: str | None = None
    existing_port_ref: str | None = None
    available_channels: list[int] = Field(default_factory=list)
    target_network_ref: str
    options: list[dict[str, Any]] = Field(default_factory=list)
    recommended_option: str | None = None
    engineering_impact: str = 'REQUIRED'
    status: Literal['OPEN', 'ANSWERED', 'APPLIED', 'SUPERSEDED', 'OUTDATED', 'BLOCKED'] = 'OPEN'
    findings: list[dict[str, Any]] = Field(default_factory=list)


class ModelSituation(Contract):
    project_ref: str
    project_revision: str
    target_objects: list[dict] = Field(default_factory=list)
    related_objects: list[dict] = Field(default_factory=list)
    functions: list[dict] = Field(default_factory=list)
    function_mappings: list[dict] = Field(default_factory=list)
    hardware_nodes: list[dict] = Field(default_factory=list)
    logical_node_addresses: list[dict] = Field(default_factory=list)
    hardware_interfaces: list[dict] = Field(default_factory=list)
    functional_interfaces: list[dict] = Field(default_factory=list)
    payload_elements: list[dict] = Field(default_factory=list)
    transport_units: list[dict] = Field(default_factory=list)
    networks: list[dict] = Field(default_factory=list)
    technology_bindings: list[dict] = Field(default_factory=list)
    routes: list[dict] = Field(default_factory=list)
    gateways: list[dict] = Field(default_factory=list)
    capacity_results: list[dict] = Field(default_factory=list)
    timing_results: list[dict] = Field(default_factory=list)
    open_findings: list[dict] = Field(default_factory=list)
    stale_results: list[dict] = Field(default_factory=list)
    assumptions: list[dict] = Field(default_factory=list)
    data_gaps: list[dict] = Field(default_factory=list)
    communication_capabilities: list[dict] = Field(default_factory=list)
    communication_controllers: list[dict] = Field(default_factory=list)
    physical_ports: list[dict] = Field(default_factory=list)
    network_connections: list[dict] = Field(default_factory=list)


class DesiredEngineeringState(Contract):
    goal: str
    goal_type: GoalType
    target_objects: list[str]
    required_relationships: list[dict] = Field(default_factory=list)
    required_connectivity: list[dict] = Field(default_factory=list)
    required_transport: list[dict] = Field(default_factory=list)
    required_validation: list[str] = Field(default_factory=list)
    optional_constraints: list[dict] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)


class EngineeringModelDelta(Contract):
    create: list[dict] = Field(default_factory=list)
    update: list[dict] = Field(default_factory=list)
    supersede: list[dict] = Field(default_factory=list)
    invalidate: list[dict] = Field(default_factory=list)
    recalculate: list[dict] = Field(default_factory=list)
    validate: list[dict] = Field(default_factory=list)


class ExecutionAuthorization(Contract):
    decision_id: str
    approved_goal: str
    approved_strategy: str
    allowed_change_types: list[str]
    affected_scope: list[str]
    forbidden_changes: list[str]
    expires_on_context_change: bool = True
    model_revision: str
    authorized_by: str
    plan_hash: str


class EngineeringExecutionStep(Contract):
    step_id: str
    action: str
    target_refs: list[str] = Field(default_factory=list)
    tool: str
    inputs: dict = Field(default_factory=dict)
    prerequisites: list[str] = Field(default_factory=list)
    expected_result: str
    validation: str
    rollback: str = 'TRANSACTION'
    status: Literal['PENDING', 'READY', 'RUNNING', 'SUCCEEDED', 'FAILED', 'BLOCKED', 'ROLLED_BACK', 'SKIPPED'] = 'PENDING'


class EngineeringExecutionPlan(Contract):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    goal: str
    model_revision: str
    strategy: str
    authorization_ref: str | None = None
    steps: list[EngineeringExecutionStep]
    dependencies: list[dict]
    validation_steps: list[str]
    rollback_strategy: str = 'ROLLBACK_CANONICAL_BATCH_KEEP_JOURNAL'
    completion_criteria: list[str]
    delta: EngineeringModelDelta
    followup_goals: list[str] = Field(default_factory=list)
    followup_configuration: dict = Field(default_factory=dict)


class GoalCompletionEvaluator:
    def evaluate(self, desired, evidence, *, blockers=(), decisions=(), failed=False):
        criteria = desired.completion_criteria or COMPLETION_CONTRACTS[desired.goal_type]
        missing = [key for key in criteria if evidence.get(key) is not True]
        return {'status': 'FAILED' if failed else 'BLOCKED' if blockers or decisions else 'INCOMPLETE' if missing else 'COMPLETE',
                'missing_conditions': missing, 'blocking_findings': list(blockers), 'remaining_decisions': list(decisions)}
