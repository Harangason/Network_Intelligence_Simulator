export type Technology = {
  id: string;
  kind: string;
  family: string;
  medium: string;
  topology: string;
  default_bitrate?: number | null;
  max_payload_bytes?: number | null;
  native_formats?: string[];
  parameter_schema?: TechnologyParameterField[];
};

export type TechnologyParameterField = {
  key: string;
  label: string;
  type: "number" | "select" | "boolean" | "text";
  unit?: string;
  min?: number;
  max?: number;
  default?: string | number | boolean;
  options?: string[];
  scope: "network" | "message" | "route" | "gateway" | "analysis" | "reliability" | "simulation";
  category: "physical" | "timing" | "capacity" | "qos" | "reliability" | "synchronization" | "gateway" | "simulation";
  description?: string;
  required?: boolean;
  editable?: boolean;
  simulation_relevant?: boolean;
  validation_relevant?: boolean;
};

export type TechnologyDomain = {
  id: string;
  label: string;
  technologies: Technology[];
};

export type Catalog = {
  technology_count: number;
  domains: TechnologyDomain[];
  formats: string[];
};

export type ArtifactDownload = {
  index: number;
  name: string;
  url: string;
};

export type SimulationResultPayload = {
  status: string;
  output_dir: string;
  warnings: string[];
  hardware_validation: {
    valid: boolean;
    findings: Array<{ code?: string; message?: string; severity?: string }>;
  };
  trace: {
    events: number;
    routes?: number;
    technologies?: string[];
    duration_s?: number;
  };
  runtime_metrics?: RuntimeMetrics;
  model_simulation?: ModelSimulationTrace;
};

export type ModelSignalPoint = {
  time_s: number;
  value: number | null;
  golden_value: number | null;
  faults: string[];
};

export type ModelSignalSeries = {
  signal_id: string;
  signal: string;
  unit: string;
  minimum: number;
  maximum: number;
  resolution: number;
  cycle_ms: number;
  behavior_type: string;
  model_label: "PHYSICS_BASED" | "RULE_BASED" | "EMPIRICAL" | "SYNTHETIC" | "GENERIC_ESTIMATE";
  points: ModelSignalPoint[];
};

export type ModelSimulationTrace = {
  schema: string;
  scenario: { name: string; mode: string; duration_s: number; speed: number; seed: number; trace_formats: string[] };
  signals: ModelSignalSeries[];
  events: Array<{ time_s: number; severity: string; event_type: string; scope: string; target: string; node?: string; message?: string; signal?: string; network?: string; description: string; faults: string[] }>;
  frames: Array<{ time_s: number; route_id: string; route_name: string; network: string; status: string; sender: string; receivers: string[] }>;
  bus_load: Array<{ network_id: string; time_s: number; load_percent: number; window_ms: number }>;
  comparison: { available: boolean; changed_samples: number; rmse: number; baseline: string; candidate: string };
  model_labels: string[];
  clock: string;
};

export type RuntimeNetworkMetric = {
  network_id: string;
  technology: string;
  event_count: number;
  transmitted_count: number;
  dropped_count: number;
  corrupted_count: number;
  average_load_percent: number;
  peak_load_percent: number;
  burst_load_percent: number;
  average_queue_depth: number;
  maximum_queue_depth: number;
  average_queue_delay_ms: number;
  maximum_queue_delay_ms: number;
};

export type RuntimeRouteMetric = {
  route_id: string;
  route_name: string;
  network_id: string;
  event_count: number;
  drop_rate: number;
  corruption_rate: number;
  configured_cycle_ms: number;
  actual_average_cycle_ms: number;
  actual_min_cycle_ms: number;
  actual_max_cycle_ms: number;
  average_jitter_ms: number;
  p95_jitter_ms: number;
  p99_jitter_ms: number;
  maximum_jitter_ms: number;
  jitter_limit_ms?: number | null;
  jitter_violations: number;
  maximum_latency_limit_ms?: number | null;
  latency_violations?: number;
  freshness_limit_ms?: number | null;
  freshness_violations?: number;
  average_end_to_end_latency_ms: number;
  maximum_end_to_end_latency_ms: number;
  average_queue_delay_ms: number;
  maximum_queue_delay_ms: number;
  timeouts: number;
  status: "PASS" | "FAIL";
};

export type RuntimeMetrics = {
  available: boolean;
  reason?: string;
  calculation_model: string;
  calculation_version?: string;
  jitter_definition?: string;
  peak_window_ms?: number;
  burst_window_ms?: number;
  summary?: {
    event_count: number;
    transmitted_events: number;
    dropped_frames: number;
    corrupted_frames: number;
    timeouts: number;
    jitter_violations: number;
    latency_violations?: number;
    freshness_violations?: number;
    observed_duration_s: number;
  };
  networks?: RuntimeNetworkMetric[];
  routes?: RuntimeRouteMetric[];
  gateways?: Array<{
    gateway_id: string;
    event_count: number;
    current_throughput_bps: number;
    maximum_throughput_bps: number;
    processing_load_percent: number;
    average_queue_delay_ms: number;
    processing_delay_ms: number;
    protocol_conversion_delay_ms: number;
  }>;
  queues?: { average_depth: number; maximum_depth: number; queue_drops: number };
  reliability?: { delivery_probability: number; packet_loss_rate: number; corruption_rate: number; retransmissions: number; duplicates?: number; reordered_events?: number };
  synchronization?: { configured_clock_offset_ms?: number; clock_drift_ppm: number; sync_precision_ms: number; maximum_clock_offset_ms: number };
  bottlenecks?: Array<{ type: string; object_id: string; value: number; unit: string }>;
};

export type SimulationJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "canceled";
  validate_only: boolean;
  created_at: string;
  updated_at: string;
  error: string | null;
  cancellation_requested?: boolean;
  result: SimulationResultPayload | null;
  artifact_downloads?: ArtifactDownload[];
};

// ---------------------------------------------------------------------------
// Engineering-Modell (kanonische Objekte: HardwareNode, Function, Interface,
// Message, Signal) und Relations (Kanten des Knowledge Graphs).
// ---------------------------------------------------------------------------

export type EngineeringResource =
  | "hardware-nodes"
  | "functions"
  | "interfaces"
  | "messages"
  | "signals";

export interface EngineeringProposalValidation {
  index: number;
  object_type: string;
  valid: boolean;
  errors: string[];
}

export interface EngineeringProposal {
  proposal_id: string;
  proposal_type: string;
  prompt: string;
  model: string | null;
  confidence: number | null;
  status: string;
  evidence: Array<Record<string, unknown>>;
  proposed_objects: Array<Record<string, unknown>>;
  validation_results: EngineeringProposalValidation[];
}

export type EngineeringObjectType =
  | "HardwareNode"
  | "Function"
  | "Interface"
  | "Message"
  | "Signal";

export type LifecycleState = "draft" | "active" | "deprecated" | "superseded";
export type GovernanceSource = "manual" | "import" | "ai_generated" | "simulation_derived";
export type ReviewState = "unreviewed" | "in_review" | "reviewed" | "rejected";
export type ApprovalState = "pending" | "approved" | "rejected";

export type GovernanceFields = {
  id: string;
  object_type: EngineeringObjectType;
  name: string;
  description: string | null;
  domain: string | null;
  version: number;
  lifecycle_state: LifecycleState;
  source: GovernanceSource;
  provenance: Record<string, unknown>;
  confidence: number | null;
  review_state: ReviewState;
  approval_state: ApprovalState;
  created_at: string;
  created_by: string | null;
  modified_at: string;
  modified_by: string | null;
};

export type HardwareNode = GovernanceFields & {
  device_type: string;
  identity: Record<string, unknown>;
  product_information: Record<string, unknown>;
  hardware_information: Record<string, unknown>;
  software_information: Record<string, unknown>;
};

export type EngFunction = GovernanceFields & {
  hardware_node_id: string | null;
};

export type EngInterface = GovernanceFields & {
  hardware_node_id: string | null;
  function_id: string | null;
  interface_type: string;
  configuration: Record<string, unknown>;
};

export type EngMessage = GovernanceFields & {
  interface_id: string | null;
  message_id_hex: string | null;
  direction: "rx" | "tx" | "bidirectional" | null;
  cycle_ms: number | null;
  dlc: number | null;
  configuration: Record<string, unknown>;
};

export type EngSignal = GovernanceFields & {
  message_id: string | null;
  display_name: string | null;
  start_bit: number | null;
  length_bits: number | null;
  byte_order: "little_endian" | "big_endian" | null;
  data_type: string | null;
  factor: number | null;
  offset_value: number | null;
  unit: string | null;
  min_value: number | null;
  max_value: number | null;
  configuration: Record<string, unknown>;
  semantic: Record<string, unknown>;
  data: Record<string, unknown>;
  communication: Record<string, unknown>;
  quality: Record<string, unknown>;
  protocol_bindings: Record<string, unknown>;
};

export type EngineeringObject = HardwareNode | EngFunction | EngInterface | EngMessage | EngSignal;

export type EngineeringSchema = {
  resources: EngineeringResource[];
  device_types: string[];
  interface_types: string[];
  message_directions: string[];
};

export type EngineeringRelation = {
  id: string;
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  relation_type: string;
  attributes: Record<string, unknown>;
  created_at: string;
  created_by: string | null;
};

export type StructureSuggestion = {
  child_type: Exclude<EngineeringObjectType, "HardwareNode">;
  child_id: string;
  child_name: string;
  parent_type: EngineeringObjectType;
  parent_id: string;
  parent_name: string;
  parent_field: string;
  relation_type: string;
  confidence: number;
  reason: string;
  current_name: string;
  recommended_name: string;
  learning_key: string;
};

export type StructureEvaluation = {
  proposal_id: string;
  model: string;
  model_version: string;
  confidence: number;
  suggestions: StructureSuggestion[];
  hardware_adjustments: Array<{
    object_type: "HardwareNode";
    id: string;
    name: string;
    field: "device_type";
    current_value: string;
    suggested_value: string;
    reason: string;
  }>;
  learning: {
    accepted: number;
    rejected: number;
    reviewed: number;
  };
};

export type StructureAssignment = StructureSuggestion & {
  name: string;
};

export type EcuTransferItem = {
  object_type: Exclude<EngineeringObjectType, "HardwareNode">;
  source_id: string;
  source_name: string;
  source_parent_id: string;
  source_parent_name: string;
  target_hardware_id: string;
  target_parent_type: EngineeringObjectType;
  target_parent_id: string | null;
  target_parent_plan_key: string | null;
  target_parent_name: string;
  target_id: string | null;
  target_name: string | null;
  recommended_name: string;
  action: "reuse" | "create";
  suggested_action?: "reuse" | "create";
  similarity: number;
  confidence: number;
  reason: string;
  relation_type: string;
  parent_field: string;
  plan_key: string;
  learning_key: string;
  level: number;
};

export type EcuTransferDecision = {
  plan_key: string;
  action: "reuse" | "create" | "skip";
  recommended_name?: string;
  target_id?: string;
};

export type SystemDuplicateCandidate = {
  candidate_key: string;
  canonical_hardware: { id: string; name: string; child_count: number };
  duplicate_hardware: { id: string; name: string; child_count: number };
  name_similarity: number;
  structure_similarity: number;
  confidence: number;
  reason: string;
};

export type SystemMergeResult = {
  canonical_hardware: { id: string; name: string };
  superseded_hardware: { id: string; name: string };
  relation_id: string;
  proposal_id: string;
  confidence: number;
  reversible: boolean;
};

export type EcuTransferReview = {
  proposal_id: string;
  source_hardware: { id: string; name: string };
  target_hardware: { id: string; name: string };
  confidence: number;
  summary: {
    total: number;
    create: number;
    reuse: number;
    semantic_duplicates: number;
  };
  items: EcuTransferItem[];
};

export type EcuTransferAnalysis = {
  model: string;
  model_version: string;
  source_hardware: { id: string; name: string };
  targets: EcuTransferReview[];
  learning: {
    accepted: number;
    rejected: number;
    reviewed: number;
  };
};

export type EngineeringImportPlan = {
  import_id: string;
  file_name: string;
  format: "dbc" | "csv" | "xlsx";
  counts: {
    hardware_nodes: number;
    functions: number;
    interfaces: number;
    messages: number;
    signals: number;
  };
  mapping: Record<string, string>;
  warnings: string[];
  hardware_nodes: Array<Record<string, unknown>>;
  functions: Array<Record<string, unknown>>;
  interfaces: Array<Record<string, unknown>>;
  messages: Array<Record<string, unknown>>;
  signals: Array<Record<string, unknown>>;
};

export type EngineeringImportResult = {
  import_id: string;
  created: number;
  reused: number;
  counts: Record<string, number>;
};

// ---------------------------------------------------------------------------
// Routing Manager
// ---------------------------------------------------------------------------

export type RoutingEndpoint = {
  node_id: string;
  port_id?: string | null;
  interface_id?: string | null;
  network_id?: string | null;
  protocol?: string | null;
};

export type RoutingValidationIssue = { code: string; message: string };

export type RoutingValidation = {
  valid: boolean;
  errors: RoutingValidationIssue[];
  warnings: RoutingValidationIssue[];
  validation_timestamp: string;
  metrics?: {
    payload_bytes?: number;
    estimated_latency_ms?: number;
    route_load_percent?: number;
    hop_count?: number;
    gateway_count?: number;
    physical_path_mapped?: boolean | null;
  };
  evidence?: Array<Record<string, unknown>>;
  outdated_reason?: string;
};

export type RoutingEntry = {
  id: string;
  route_code: string;
  revision: number;
  supersedes_id?: string | null;
  name: string;
  description?: string | null;
  source: RoutingEndpoint;
  payload: {
    interface_definition_id?: string | null;
    interface_definition_ids?: string[];
    message_id?: string | null;
    message_ids?: string[];
    signal_ids: string[];
    topic?: string | null;
    data_object?: string | null;
  };
  destinations: RoutingEndpoint[];
  route: {
    hops: Array<string | { node_id?: string; network_id?: string; name?: string }>;
    gateways: Array<string | { node_id?: string; name?: string }>;
    transformations: string[];
    priority: "LOW" | "NORMAL" | "HIGH" | "CRITICAL";
  };
  timing: {
    cycle_time_ms?: number | null;
    timeout_ms?: number | null;
    max_latency_ms?: number | null;
    jitter_limit_ms?: number | null;
  };
  routing_policy: {
    routing_type: string;
    redundancy: string;
    fallback_route_id?: string | null;
    conditions: Array<Record<string, unknown>>;
  };
  validation: Partial<RoutingValidation>;
  status: string;
  origin: string;
  confidence?: number | null;
  review_state: string;
  approval_state: string;
  source_id?: string | null;
  source_version?: string | null;
  created_at: string;
  created_by?: string | null;
  modified_at: string;
  modified_by?: string | null;
  approved_at?: string | null;
  approved_by?: string | null;
};

export type RoutingProposal = {
  proposal_id: string;
  prompt: string;
  target_objects: unknown[];
  generated_routes: RoutingEntry[];
  retrieved_context: unknown[];
  evidence: Array<Record<string, unknown>>;
  confidence?: number | null;
  validation_results: RoutingValidation[];
  model?: string | null;
  model_version?: string | null;
  status: string;
  created_at: string;
};

export type RoutingSchema = {
  routing_types: string[];
  protocols: string[];
  priorities: string[];
  redundancy_modes: string[];
  permissions: string[];
  agent_permissions: string[];
};
