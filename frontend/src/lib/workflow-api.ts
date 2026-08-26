import type { NetworkTopology } from "./topology";
import type { SimulationResultPayload } from "./types";
import { readActiveProjectId } from "./user-settings";

const BASE = "/api/engineering";
const LOCAL_FRONTEND_PORT = "13500";
const LOCAL_BACKEND_BASE = "http://127.0.0.1:15050/api/engineering";

function workflowBaseUrl(): string {
  if (typeof window !== "undefined" && window.location.port === LOCAL_FRONTEND_PORT) {
    return LOCAL_BACKEND_BASE;
  }
  return BASE;
}

export type WorkflowStepId =
  | "engineering_model"
  | "routing"
  | "network_editor"
  | "parameters"
  | "capacity_timing"
  | "validation"
  | "simulation"
  | "results_analysis"
  | "data_science_intelligence";

export type WorkflowStatus =
  | "EMPTY"
  | "IN_PROGRESS"
  | "COMPLETE"
  | "WARNING"
  | "ERROR"
  | "APPROVED"
  | "OUTDATED";

export type WorkflowStep = {
  id: WorkflowStepId;
  position: number;
  label: string;
  status: WorkflowStatus;
  version: number;
  reason?: string | null;
};

export type WorkflowState = {
  project_id: string;
  active_step: WorkflowStepId;
  versions: Record<WorkflowStepId, number>;
  statuses: Record<WorkflowStepId, WorkflowStatus>;
  stale_reasons: Partial<Record<WorkflowStepId, string>>;
  context: Record<string, unknown>;
  parameters: Record<string, unknown>;
  topology: Partial<NetworkTopology>;
  steps: WorkflowStep[];
  simulation_snapshots: SimulationSnapshot[];
  rule: string;
  routing_sync?: {
    counts: {
      created: number;
      outdated: number;
      unchanged: number;
      skipped: number;
    };
    skipped: Array<{ source_id: string; reason: string }>;
  };
};

const WORKFLOW_STEP_DEFINITIONS: Array<{ id: WorkflowStepId; label: string }> = [
  { id: "engineering_model", label: "Engineering-Modell" },
  { id: "routing", label: "Routing-Tabelle" },
  { id: "network_editor", label: "Netzwerk-Editor" },
  { id: "parameters", label: "Parameter" },
  { id: "capacity_timing", label: "Capacity & Timing" },
  { id: "validation", label: "Validation / Preflight" },
  { id: "simulation", label: "Simulation" },
  { id: "results_analysis", label: "Results / Analysis" },
  { id: "data_science_intelligence", label: "Data Science & Intelligence" },
];

function defaultVersions(): Record<WorkflowStepId, number> {
  return Object.fromEntries(WORKFLOW_STEP_DEFINITIONS.map((step) => [step.id, 0])) as Record<WorkflowStepId, number>;
}

function defaultStatuses(): Record<WorkflowStepId, WorkflowStatus> {
  return Object.fromEntries(WORKFLOW_STEP_DEFINITIONS.map((step) => [step.id, "EMPTY"])) as Record<WorkflowStepId, WorkflowStatus>;
}

function normalizeWorkflowState(payload: WorkflowState): WorkflowState {
  const versions = { ...defaultVersions(), ...(payload.versions ?? {}) };
  const statuses = { ...defaultStatuses(), ...(payload.statuses ?? {}) };
  const activeStep = payload.active_step ?? "engineering_model";
  const steps = WORKFLOW_STEP_DEFINITIONS.map((definition, index) => {
    const existing = payload.steps?.find((step) => step.id === definition.id);
    return {
      id: definition.id,
      label: existing?.label ?? definition.label,
      position: existing?.position ?? index + 1,
      status: existing?.status ?? statuses[definition.id],
      version: existing?.version ?? versions[definition.id],
      reason: existing?.reason ?? (payload.stale_reasons ?? {})[definition.id] ?? null,
    };
  });

  return {
    ...payload,
    project_id: payload.project_id ?? readActiveProjectId(),
    active_step: activeStep,
    versions,
    statuses,
    stale_reasons: payload.stale_reasons ?? {},
    context: payload.context ?? {},
    parameters: payload.parameters ?? {},
    topology: payload.topology ?? {},
    steps,
    simulation_snapshots: payload.simulation_snapshots ?? [],
    rule: payload.rule ?? "",
  };
}

export type AnalysisFinding = {
  severity: "ERROR" | "WARNING" | "INFO";
  code: string;
  message: string;
  recommendation?: string;
  step?: WorkflowStepId;
  object_type?: string;
  object_id?: string;
  category?: PreflightCategory;
};

export type PreflightCategory =
  | "engineering_model"
  | "routing"
  | "network"
  | "parameters"
  | "capacity"
  | "timing"
  | "reliability"
  | "synchronization";

export type PreflightResults = {
  ready_for_simulation: boolean;
  error_count: number;
  warning_count: number;
  checked_steps: WorkflowStepId[];
  capacity_snapshot_id?: string | null;
  category_statuses: Record<PreflightCategory, "PASS" | "WARNING" | "ERROR">;
  category_checks: Record<PreflightCategory, AnalysisFinding[]>;
};

export type CapacityNetwork = {
  network_id: string;
  protocol: string;
  route_count: number;
  average_load_percent: number;
  peak_load_percent: number;
  burst_load_percent: number;
  bitrate?: number;
  available_capacity_percent?: number;
  capacity_reserve_percent: number;
  capacity_margin_percent?: number;
  worst_end_to_end_latency_ms: number;
  top_contributors?: Array<{ route_id: string; name: string; load_percent: number }>;
  status: "NORMAL" | "WARNING" | "CRITICAL" | "OVERLOAD";
};

export type CapacityRoute = {
  route_id: string;
  route_code?: string;
  name: string;
  network_id: string;
  protocol: string;
  payload_bytes: number;
  cycle_ms: number;
  average_load_percent: number;
  peak_load_percent: number;
  burst_load_percent: number;
  burst_window_ms?: number;
  transmission_latency_ms?: number;
  end_to_end_latency_ms: number;
  queueing_latency_ms: number;
  gateway_latency_ms?: number;
  estimated_jitter_ms?: number;
  jitter_budget_ms?: number;
  max_latency_ms?: number | null;
  timeout_ms?: number | null;
  freshness_ms?: number | null;
  latency_status?: "PASS" | "FAIL";
  jitter_status?: "PASS" | "FAIL";
  requirement_status?: "PASS" | "FAIL";
  priority?: number;
  queue_policy?: string;
  breakdown?: Record<string, number>;
  bottleneck?: { component: string; delay_ms: number };
  status: string;
  calculation_model: string;
};

export type CapacityResults = {
  overview: {
    network_count: number;
    route_count: number;
    gateway_count: number;
    signal_count: number;
    load_status_counts: Record<"NORMAL" | "WARNING" | "CRITICAL" | "OVERLOAD", number>;
    max_peak_load_percent: number;
    max_burst_load_percent: number;
    minimum_capacity_reserve_percent: number;
    minimum_capacity_margin_percent: number;
    worst_end_to_end_latency_ms: number;
    highest_load_network?: string | null;
    status: WorkflowStatus;
  };
  networks: CapacityNetwork[];
  routes: CapacityRoute[];
  gateways: Array<Record<string, unknown>>;
  messages: Array<Record<string, unknown>>;
  signals: Array<Record<string, unknown>>;
  critical_paths: CapacityRoute[];
  bottlenecks: Array<Record<string, unknown>>;
  thresholds: Record<string, number>;
  timing?: {
    worst_end_to_end_latency_ms: number;
    worst_queueing_latency_ms: number;
    worst_estimated_jitter_ms: number;
    queue_policy: string;
    deadline_violations: number;
    jitter_violations: number;
  };
  reliability?: {
    configured_retransmission_rate: number;
    traffic_multiplier: number;
    packet_loss_probability: number;
    expected_delivery_probability: number;
    required_reliability?: number | null;
    status: "PASS" | "FAIL";
  };
  synchronization?: {
    clock_drift_ppm: number;
    sync_precision_ms: number;
    max_drift_over_observation_ms: number;
    observation_s: number;
    expected_maximum_error_ms: number;
    maximum_allowed_error_ms?: number | null;
    status: "PASS" | "FAIL";
  };
  impact?: CapacityImpact;
};

export type CapacityImpact = {
  current: CapacityResults["overview"];
  scenario: CapacityResults["overview"];
  delta: {
    peak_load_percent: number;
    burst_load_percent: number;
    capacity_reserve_percent: number;
    end_to_end_latency_ms: number;
  };
  affected: {
    networks: number;
    messages: number;
    signals: number;
    routes: number;
    gateways: number;
  };
};

export type AnalysisSnapshot = {
  id: string;
  analysis_type: "capacity_timing" | "preflight" | "intelligence";
  source_versions: Record<WorkflowStepId, number>;
  results: CapacityResults | PreflightResults | Record<string, unknown>;
  findings: AnalysisFinding[];
  provenance: Record<string, unknown>;
  status: WorkflowStatus;
  is_outdated: boolean;
  outdated_reason?: string | null;
  created_at: string;
};

export type SimulationSnapshot = {
  id: string;
  source_versions: Record<WorkflowStepId, number>;
  configuration?: Record<string, unknown>;
  calculated_metrics?: CapacityResults;
  validation_snapshot_id?: string;
  status: "READY" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELED" | "OUTDATED";
  job_id?: string | null;
  result?: SimulationResultPayload | null;
  is_outdated: boolean;
  outdated_reason?: string | null;
  created_at: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${workflowBaseUrl()}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Project-ID": readActiveProjectId(),
        ...init?.headers,
      },
      cache: "no-store",
      signal: init?.signal ?? AbortSignal.timeout(10000),
    });
  } catch (error) {
    throw new Error("Der Workflow-Dienst ist nicht erreichbar.", { cause: error });
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((payload as { error?: string }).error ?? `Workflow-Fehler ${response.status}`);
  }
  return payload as T;
}

export const getWorkflow = () => request<WorkflowState>("/workflow").then(normalizeWorkflowState);

export const setWorkflowContext = (context: Record<string, unknown>) =>
  request<WorkflowState>("/workflow/context", { method: "PATCH", body: JSON.stringify(context) }).then(normalizeWorkflowState);

export const saveWorkflowParameters = (parameters: Record<string, unknown>) =>
  request<WorkflowState>("/workflow/parameters", {
    method: "PATCH",
    body: JSON.stringify({ parameters }),
  }).then(normalizeWorkflowState);

export const saveWorkflowTopology = (topology: Pick<NetworkTopology, "nodes" | "edges">) =>
  request<WorkflowState>("/workflow/topology", {
    method: "PUT",
    body: JSON.stringify({ topology }),
  }).then(normalizeWorkflowState);

export const calculateCapacity = (overrides?: Record<string, unknown>) =>
  request<{
    snapshot_id: string;
    status: WorkflowStatus;
    results: CapacityResults;
    findings: AnalysisFinding[];
    provenance: Record<string, unknown>;
  }>("/capacity/calculate", {
    method: "POST",
    body: JSON.stringify({ overrides: overrides ?? {} }),
  });

export const calculateCapacityScenario = (overrides: Record<string, unknown>) =>
  request<{ status: WorkflowStatus; results: CapacityResults; findings: AnalysisFinding[]; impact?: CapacityImpact }>(
    "/capacity/scenario",
    { method: "POST", body: JSON.stringify({ overrides }) },
  );

export const getCapacity = () => request<AnalysisSnapshot>("/capacity");

export const runPreflight = () =>
  request<{
    status: WorkflowStatus;
    ready_for_simulation: boolean;
    error_count: number;
    warning_count: number;
    findings: AnalysisFinding[];
    snapshot_id: string;
    category_statuses: PreflightResults["category_statuses"];
    category_checks: PreflightResults["category_checks"];
  }>("/preflight", { method: "POST", body: "{}" });

export const optimizeCapacity = () =>
  request<{ proposals: Array<Record<string, unknown>> }>("/capacity/optimize", {
    method: "POST",
    body: "{}",
  });

export const getPreflight = () => request<AnalysisSnapshot>("/preflight");

export const createSimulationSnapshot = (configuration: Record<string, unknown>) =>
  request<SimulationSnapshot>("/workflow/simulation-snapshots", {
    method: "POST",
    body: JSON.stringify({ configuration }),
  });

export const getWorkflowSnapshots = () =>
  request<{
    capacity: AnalysisSnapshot | null;
    preflight: AnalysisSnapshot | null;
    simulations: SimulationSnapshot[];
  }>("/workflow/snapshots");

export type IntelligenceIssue = {
  severity: "ERROR" | "WARNING" | "INFO";
  category: string;
  code: string;
  object_type: string;
  object_id: string;
  problem: string;
  detected_cause: string;
  affected_objects: string[];
  recommendation: string;
  status: string;
  evidence: Array<Record<string, unknown>>;
};

export type IntelligenceRecommendation = {
  candidate_id: string;
  category: string;
  problem: string;
  affected_objects: string[];
  recommendation: string;
  expected_impact: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
  graph_context: Array<Record<string, unknown>>;
  rag_context: Array<Record<string, unknown>>;
  confidence: number;
  priority: number;
  priority_factors: Record<string, number>;
  implementation_effort: string;
  status: string;
  governance: string;
};

export type IntelligenceResults = {
  system_health: {
    score: number;
    counts: Record<string, number>;
    metrics: Record<string, number>;
  };
  maturity: {
    overall_score: number;
    level: string;
    level_name: string;
    target_level: string;
    target_level_name: string;
    dimensions: Record<string, number>;
    gaps: Array<{ dimension: string; current: number; target: number; gap: number }>;
    criteria: Record<string, string>;
  };
  critical_issues: IntelligenceIssue[];
  data_quality: Record<string, number | string>;
  routing_analytics: Record<string, unknown>;
  network_analytics: Record<string, unknown>;
  capacity_timing_analytics: Record<string, unknown>;
  anomalies: Array<Record<string, unknown>>;
  trends: { points: Array<Record<string, unknown>>; direction: string; comparison_modes: string[] };
  root_causes: Array<Record<string, unknown>>;
  correlations: Array<Record<string, unknown>>;
  recommendations: IntelligenceRecommendation[];
  rag_knowledge_insights: Array<Record<string, unknown>>;
  graph_insights: Record<string, unknown>;
  governance: Record<string, unknown>;
};

export type IntelligenceSnapshot = Omit<AnalysisSnapshot, "results"> & {
  results: IntelligenceResults;
};

export type OptimizationProposal = {
  proposal_id: string;
  category: string;
  problem: string;
  affected_objects: string[];
  recommendation: string;
  expected_impact: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
  graph_context: Array<Record<string, unknown>>;
  rag_context: Array<Record<string, unknown>>;
  confidence: number | null;
  priority: number;
  implementation_effort: string;
  status: "PROPOSED" | "UNDER_REVIEW" | "ACCEPTED" | "REJECTED" | "APPLIED_AS_DRAFT" | "SUPERSEDED";
};

export const getIntelligence = () => request<IntelligenceSnapshot>("/intelligence");

export const assessIntelligence = () =>
  request<IntelligenceSnapshot>("/intelligence/assess", { method: "POST", body: "{}", signal: AbortSignal.timeout(30000) });

export const listOptimizationProposals = () =>
  request<{ items: OptimizationProposal[]; count: number }>("/intelligence/proposals");

export const createOptimizationProposal = (proposal: IntelligenceRecommendation) =>
  request<OptimizationProposal>("/intelligence/proposals", {
    method: "POST",
    body: JSON.stringify(proposal),
  });

export const reviewOptimizationProposal = (proposalId: string, status: OptimizationProposal["status"], reason?: string) =>
  request<OptimizationProposal>(`/intelligence/proposals/${proposalId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, reason, actor: "intelligence-workbench" }),
  });

export const intelligenceExportUrl = (format: "json" | "csv", section = "issues") =>
  `${workflowBaseUrl()}/intelligence/export?format=${format}&section=${encodeURIComponent(section)}&project_id=${encodeURIComponent(readActiveProjectId())}`;

export type ProjectBundle = {
  format: "network-intelligence-project";
  bundle_version: number;
  project_id: string;
  generated_at: string;
  workflow: Record<string, unknown>;
  source_data: Record<string, Array<Record<string, unknown>>>;
  project_data: Record<string, Array<Record<string, unknown>>>;
};

export const exportProjectBundle = (targetProjectId?: string) => {
  const query = targetProjectId ? `?target_project_id=${encodeURIComponent(targetProjectId)}` : "";
  return request<ProjectBundle>(`/projects/export${query}`);
};

export const importProjectBundle = (bundle: ProjectBundle, targetProjectId?: string) =>
  request<{ project_id: string; report: Record<string, unknown>; workflow: WorkflowState }>("/projects/import", {
    method: "POST",
    body: JSON.stringify({ bundle, target_project_id: targetProjectId }),
    signal: AbortSignal.timeout(180000),
  }).then((result) => ({ ...result, workflow: normalizeWorkflowState(result.workflow) }));

export const resetProjectWorkspace = (projectId: string) =>
  request<{ project_id: string; cleared_tables: string[]; workflow: WorkflowState }>("/projects/reset", {
    method: "POST",
    body: JSON.stringify({ project_id: projectId }),
  }).then((result) => ({ ...result, workflow: normalizeWorkflowState(result.workflow) }));
