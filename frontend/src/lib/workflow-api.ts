import type { NetworkTopology } from "./topology";
import type { SimulationResultPayload } from "./types";
import { compactProjectId, readActiveProjectId } from "./user-settings.ts";
import type { InspectionObject, InspectionSources } from "./capacity-network-inspection";
import {
  WORKFLOW_STEP_DEFINITIONS,
  type WorkflowStatus,
  type WorkflowStepId,
} from "../features/workflow/definition.ts";

export type { WorkflowStatus, WorkflowStepId } from "../features/workflow/definition.ts";

const BASE = "/api/engineering";

function workflowBaseUrl(): string {
  return BASE;
}

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
  edit_tokens?: { topology: string; parameters: string };
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
  artifact_checks?: Record<string, {
    complete?: boolean;
    counts?: Record<string, number>;
    hardware_by_type?: Record<string, number>;
    scope_mismatches?: Record<string, { actual?: number; target?: number }>;
    status?: string;
  }>;
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
  coverage?: import("./types").SimulationCoverage;
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
  evaluation?: {
    payload: { status: string; signal_count: number; errors: number; open: number };
    capacity: { status: string; load_percent: number; basis: string };
    schedule: { status: string; slot_load_percent?: number };
    stress: { status: string; peak_percent: number; burst_percent: number };
    functional: { status: string; explanation: string };
  };
    network_id: string;
    network_name?: string;
    timing_verified?: boolean;
    response_time_bound_ms?: number | null;
  protocol: string;
  route_count: number;
  capacity_applicable?: boolean;
  load_basis?: string;
  average_load_percent: number;
  peak_load_percent: number;
  burst_load_percent: number;
  bitrate?: number;
  available_capacity_percent?: number;
  capacity_reserve_percent: number;
  capacity_margin_percent?: number;
  target_bus_load_percent?: number;
  target_margin_percent?: number;
  target_status?: "PASS" | "EXCEEDED" | "NOT_APPLICABLE";
  worst_end_to_end_latency_ms: number;
  top_contributors?: Array<{ route_id: string; name: string; load_percent: number }>;
  status: "NORMAL" | "WARNING" | "CRITICAL" | "OVERLOAD" | "UNVERIFIED";
};

export type CapacityRoute = {
  capacity_applicable?: boolean;
  timing_verified?: boolean;
  response_time_bound_ms?: number | null;
  jitter_bound_ms?: number | null;
  route_id: string;
  route_code?: string;
  name: string;
  network_id: string;
  physical_network_ids?: string[];
  route_segment_index?: number;
  route_segment_count?: number;
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
  latency_status?: "PASS" | "FAIL" | "UNVERIFIED";
  jitter_status?: "PASS" | "FAIL" | "UNVERIFIED";
  requirement_status?: "PASS" | "FAIL" | "UNVERIFIED";
  priority?: number;
  queue_policy?: string;
  breakdown?: Record<string, number>;
  bottleneck?: { component: string; delay_ms: number };
  status: string;
  calculation_model: string;
};

export type CapacityResults = {
  overview: {
    peak_factor?: number;
    burst_factor?: number;
    timing_verified?: boolean;
    network_count: number;
    route_count: number;
    route_segment_count?: number;
    gateway_count: number;
    signal_count: number;
    load_status_counts: Record<"NORMAL" | "WARNING" | "CRITICAL" | "OVERLOAD", number>;
    max_peak_load_percent: number;
    max_burst_load_percent: number;
    target_bus_load_percent?: number;
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
    throw Object.assign(new Error((payload as { error?: string }).error ?? `Workflow-Fehler ${response.status}`), { status: response.status });
  }
  if (init?.method && !["GET", "HEAD"].includes(init.method) && !path.startsWith("/workflow/context") && typeof window !== "undefined") {
    window.dispatchEvent(new Event("engineering:write-completed"));
  }
  return payload as T;
}

export const getWorkflowNetworks = async () => {
  const state = await request<{parameters: {networks?: Array<{id: string; name?: string}>}}>('/workflow/parameters');
  return state.parameters.networks ?? [];
};

type WorkflowResourceRevision = {
  project_id: string;
  versions: Record<string, number>;
  edit_token: string;
};

export async function getWorkflow(projectId = readActiveProjectId()): Promise<WorkflowState> {
  // Editors need the canonical resources, but a status response must stay small.
  // Capture the project once and join only resources from the same source revision.
  const options = { signal: AbortSignal.timeout(180000), headers: { "X-Project-ID": projectId } };
  const sourceSteps = ["engineering_model", "routing", "network_editor", "parameters"] as const;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const [parameters, topology, snapshots] = await Promise.all([
      request<WorkflowResourceRevision & Pick<WorkflowState, "parameters">>("/workflow/parameters", options),
      request<WorkflowResourceRevision & Pick<WorkflowState, "topology">>("/workflow/topology", options),
      request<{ simulations: SimulationSnapshot[] }>("/workflow/snapshots", options),
    ]);
    // Never reuse an in-flight summary that may predate the detail reads.
    const state = normalizeWorkflowState(await request<WorkflowState>("/workflow?view=summary", options));
    if ([state, parameters, topology].some(item => item.project_id !== projectId)) {
      throw new Error("Der geladene Workflow gehört zu einem anderen Projekt. Bitte erneut laden.");
    }
    const consistent = ([ ["parameters", parameters], ["topology", topology] ] as const).every(([key, resource]) =>
      Boolean(resource.edit_token) && resource.edit_token === state.edit_tokens?.[key]
      && sourceSteps.every(step => resource.versions?.[step] === state.versions[step]),
    );
    if (consistent) return {
      ...state, parameters: parameters.parameters, topology: topology.topology,
      simulation_snapshots: snapshots.simulations,
    };
  }
  throw new Error("Das Modell wurde während des Ladens geändert. Bitte den aktuellen Stand erneut laden.");
}

const workflowSummaryRequests = new Map<string, Promise<WorkflowState>>();

export const getWorkflowSummary = (projectId = readActiveProjectId(), options?: { fresh?: boolean }) => {
  let pending = options?.fresh ? undefined : workflowSummaryRequests.get(projectId);
  if (!pending) {
    pending = request<WorkflowState>("/workflow?view=summary", { headers: { "X-Project-ID": projectId } })
      .then(normalizeWorkflowState)
      .finally(() => {
        if (workflowSummaryRequests.get(projectId) === pending) workflowSummaryRequests.delete(projectId);
      });
    workflowSummaryRequests.set(projectId, pending);
  }
  return pending;
};

export const setWorkflowContext = (context: Record<string, unknown>, projectId = readActiveProjectId()) =>
  request<WorkflowState>("/workflow/context?view=summary", { method: "PATCH", body: JSON.stringify(context), headers: { 'X-Project-ID': projectId } }).then(normalizeWorkflowState);

export type EngineeringWorkloadSummary = {
  workload_id: string;
  status: string;
  workload_type?: string;
  title?: string;
  updated_at?: string;
};

export const listEngineeringWorkloads = (params: { status?: string; workload_type?: string; limit?: number; offset?: number } = {}) => {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.workload_type) query.set("workload_type", params.workload_type);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<{ items: EngineeringWorkloadSummary[]; count: number }>(
    `/workloads${suffix ? `?${suffix}` : ""}`,
  );
};

export const cancelEngineeringWorkload = (workloadId: string, actor = "engineering-agent-wizard") =>
  request<EngineeringWorkloadSummary>(`/workloads/${encodeURIComponent(workloadId)}/cancel`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });

export const saveWorkflowParameters = (parameters: Record<string, unknown>, expectedToken?: string) =>
  request<WorkflowState>("/workflow/parameters", {
    method: "PATCH",
    body: JSON.stringify({ parameters, expected_token: expectedToken }),
    signal: AbortSignal.timeout(180000),
  }).then(normalizeWorkflowState);

export const saveSimulationScope = (simulationScope: import("./simulation-scope").SimulationScope) =>
  request<WorkflowState>("/workflow/simulation-scope", {
    method: "PATCH", body: JSON.stringify({ simulation_scope: simulationScope }), signal: AbortSignal.timeout(180000),
  }).then(normalizeWorkflowState);

export const saveWorkflowTopology = (topology: Pick<NetworkTopology, "nodes" | "edges">, expectedToken?: string) =>
  request<WorkflowState>("/workflow/topology", {
    method: "PUT",
    body: JSON.stringify({ topology, expected_token: expectedToken }),
    signal: AbortSignal.timeout(180000),
  }).then(normalizeWorkflowState);

export type NetworkView = { project_id: string; topology: NetworkTopology; edit_tokens: { topology: string; parameters: string }; versions: Record<string, number> };
export type NetworkAssignmentRequest = {node_ids:string[]; target_kind:'cluster'|'frame'|'bus'; target_id:string; source_network_id?:string; plan_token?:string};
export type FrameDeviceRequest = {frame_id: string; kind: 'ecu' | 'sensor' | 'actuator'; name: string};
export const createFrameDevice = (device: FrameDeviceRequest, expectedToken?: string) => request<WorkflowState>('/workflow/frame-device', {
  method: 'POST', body: JSON.stringify({...device, expected_token: expectedToken}), signal: AbortSignal.timeout(60000),
}).then(normalizeWorkflowState);
export type NetworkAssignmentPreview = {token:string; target_name:string; node_ids:string[]; routes:number; messages:number; new_objects:number; new_commands:number; new_routes:number;
  members:Array<{id:string; name:string; from_cluster:string; from_frame:string; to_cluster:string; to_frame:string}>;
  connections:Array<{device:string; from:string; to:string; technology:string}>};
export const previewNetworkAssignment = (assignment:NetworkAssignmentRequest, signal?:AbortSignal) => request<NetworkAssignmentPreview>('/workflow/network-assignment/preview', {
  method:'POST',body:JSON.stringify(assignment),signal:signal??AbortSignal.timeout(180000),
});
export const saveNetworkAssignment = (assignment:NetworkAssignmentRequest, expectedToken?:string) => request<WorkflowState>('/workflow/network-assignment', {
  method:'PUT',body:JSON.stringify({...assignment,expected_token:expectedToken}),signal:AbortSignal.timeout(180000),
}).then(normalizeWorkflowState);
export type BusChangePreview = { token: string; network_id: string; bus: string; networks: Array<{ id: string; name: string; previous_name: string }>; devices: number; messages: number; routes: number };
export type BusChangeRequest = { network_id: string; bus: string; plan_token: string; edge: NetworkTopology["edges"][number] };
export const previewBusChange = (networkId: string, bus: string) => request<BusChangePreview>("/workflow/bus-technology/preview", {
  method: "POST", body: JSON.stringify({ network_id: networkId, bus }), signal: AbortSignal.timeout(180000),
});
export const saveBusChange = (change: BusChangeRequest, expectedToken?: string) => request<WorkflowState>("/workflow/bus-technology", {
  method: "PUT", body: JSON.stringify({ ...change, expected_token: expectedToken }), signal: AbortSignal.timeout(180000),
}).then(normalizeWorkflowState);
export const renamePhysicalBus = (networkId: string, name: string, expectedToken?: string, expectedParametersToken?: string) => request<WorkflowState>('/workflow/bus-name', {
  method: 'PUT', body: JSON.stringify({network_id: networkId, name, expected_token: expectedToken, expected_parameters_token: expectedParametersToken}),
}).then(normalizeWorkflowState);
export const getNetworkView = () => request<NetworkView>("/workflow/network-view");
export const saveNetworkView = (positions: Record<string, unknown>, expectedToken?: string, reset = false, busRoutes?: NonNullable<NetworkTopology['scene']>['manualBusRoutes'], resetWires = false) =>
  request<NetworkView>("/workflow/network-view", { method: "PUT", body: JSON.stringify({ positions, expected_token: expectedToken, reset, bus_routes: busRoutes, reset_wires: resetWires }) });

export type WorkflowTopologyLayoutNode = {
  node_id: string;
  x: number;
  y: number;
  width?: number | null;
  height?: number | null;
  ports: Record<string, { side: "left" | "right" | "top" | "bottom"; offset: number }>;
  updated_at?: string;
};

export type WorkflowTopologyLayout = {
  project_id: string;
  topology_key: string;
  layout_version: number;
  nodes: WorkflowTopologyLayoutNode[];
};

export const getWorkflowTopologyLayout = (topologyKey: string, layoutVersion: number) => {
  const query = new URLSearchParams({ topology_key: topologyKey, layout_version: String(layoutVersion) });
  return request<WorkflowTopologyLayout>(`/workflow/topology-layout?${query.toString()}`);
};

export const saveWorkflowTopologyLayout = (
  topologyKey: string,
  layoutVersion: number,
  nodes: WorkflowTopologyLayoutNode[],
) => request<WorkflowTopologyLayout>("/workflow/topology-layout", {
  method: "PUT",
  body: JSON.stringify({ topology_key: topologyKey, layout_version: layoutVersion, nodes }),
});

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

const inspectionSources = new Map<string, { key: string; data: InspectionSources }>();
const inspectionRequests = new Map<string, Promise<InspectionSources>>();

export function clearWorkflowApiCaches(projectId?: string) {
  if (!projectId) {
    inspectionSources.clear();
    inspectionRequests.clear();
    return;
  }
  inspectionSources.delete(projectId);
  inspectionRequests.delete(projectId);
}

export function getCapacityInspectionSources(projectId: string): Promise<InspectionSources> {
  const pending = inspectionRequests.get(projectId);
  if (pending) return pending;
  const headers = { "X-Project-ID": projectId };
  const versionKey = (versions: Record<string, number>) => JSON.stringify([
    versions.engineering_model, versions.routing, versions.network_editor, versions.parameters,
  ]);
  const load = async () => {
    const before = await request<WorkflowState>("/workflow?view=summary", { headers });
    const key = versionKey(before.versions);
    const cached = inspectionSources.get(projectId);
    if (cached?.key === key) return cached.data;
    const all = async (resource: string) => {
      const items: InspectionObject[] = [];
      for (let offset = 0; ; offset += 500) {
        const page = await request<{ items: InspectionObject[] }>(`/${resource}?limit=500&offset=${offset}`, { headers });
        items.push(...page.items);
        if (page.items.length < 500) return items;
      }
    };
    const topology = await request<{ topology: Record<string, unknown> }>("/workflow/topology", { headers });
    const data: InspectionSources = {
      versions: before.versions, topology: topology.topology,
      hardware: await all("hardware-nodes"), functions: await all("functions"),
      interfaces: await all("interfaces"), messages: await all("messages"),
      signals: await all("signals"), routes: await all("routing"),
    };
    const after = await request<WorkflowState>("/workflow?view=summary", { headers });
    if (key !== versionKey(after.versions)) throw new Error("Modell wurde während der Signalprüfung geändert. Bitte erneut laden.");
    inspectionSources.set(projectId, { key, data });
    if (inspectionSources.size > 2) inspectionSources.delete(inspectionSources.keys().next().value!);
    return data;
  };
  const promise = load().finally(() => { inspectionRequests.delete(projectId); });
  inspectionRequests.set(projectId, promise);
  return promise;
}

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

export const getPreflightSnapshot = () => request<{
  id: string;
  findings: AnalysisFinding[];
  results: { preflight_status?: string; warning_count?: number };
}>("/preflight");

export const approvePreflightWarnings = (snapshotId: string, actor: string) => request<{
  preflight: { preflight_status: string; ready_for_simulation: boolean; warning_count: number };
}>("/preflight/warnings/approve", {
  method: "POST", body: JSON.stringify({ snapshot_id: snapshotId, actor }), signal: AbortSignal.timeout(180000),
});

export const optimizeCapacity = () =>
  request<{ proposals: Array<Record<string, unknown>> }>("/capacity/optimize", {
    method: "POST",
    body: "{}",
    });

export type CommunicationSizingPlan = {
  source_token: string; status: string; history_matches: string[];
  policy: Record<string, unknown>;
  changes: Array<{message_id: string; name: string; before_ms: number; after_ms: number; evaluation?: string}>;
  networks: Array<{network_id: string; network_name: string; protocol: string; status: string; explanation: string;
    selected_floor_ms?: number; effective_periods_ms?: number[]; schedule?: {nominal_load_percent?: number; slot_load_percent?: number; assumptions?: string[]};
    attempts: Array<{floor_ms: number; fits: boolean; load_percent?: number; slot_load_percent?: number; reasons: string[]}>}>;
};
export const dimensionCommunications = (policy?: Record<string, unknown>) =>
  request<CommunicationSizingPlan>("/capacity/dimension", {method: "POST", body: JSON.stringify({policy})});
export const applyCommunicationSizing = (plan: CommunicationSizingPlan) =>
  request<{changed_messages: number; changed_routes: number; valid_routes: number; invalid_routes: string[]}>("/capacity/dimension/apply", {
    method: "POST", body: JSON.stringify({source_token: plan.source_token, policy: plan.policy, approve_valid: true}),
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

export const getWorkflowSimulationSnapshot = (snapshotId: string) =>
  request<SimulationSnapshot>(`/workflow/simulation-snapshots/${encodeURIComponent(snapshotId)}`);

export type IntelligenceIssue = {
  severity: "ERROR" | "WARNING" | "INFO";
  original_severity?: "ERROR" | "WARNING" | "INFO";
  category: string;
  code: string;
  object_type: string;
  object_id: string;
  problem: string;
  detected_cause: string;
  affected_objects: string[];
  recommendation: string;
  status: string;
  approval_state?: "PENDING_CONFIRMATION" | "APPROVED" | "REJECTED" | string;
  review_state?: "UNREVIEWED" | "REVIEWED" | string;
  requires_user_confirmation?: boolean;
  confirmation_label?: string;
  approval_note?: string;
  approved_at?: string;
  approved_by?: string;
  issue_key?: string;
  evidence: Array<Record<string, unknown>>;
};

export type IntelligenceRecommendation = {
  review_history?: Array<{ proposal_id: string; status: string; reason?: string; previous_recommendation?: string }>;
  requires_fresh_review?: boolean;
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
  review_learning?: { reviewed_proposals: number; matched_recommendations: number };
  assessment_mode?: "DIAGNOSTIC" | "VERIFIED";
  missing_evidence?: string[];
  interpretation?: { method: string; ai_used: boolean; learning: string };
  network_distribution?: {
    status: string;
    target_load_percent: number;
    validation_scope: string;
    unresolved: string[];
    networks: Array<{
      network_id: string;
      protocol: string;
      current_load_percent: number;
      proposed_segments: number;
      additional_segments: number;
      projected_max_load_percent: number;
      segments: Array<{
        name: string;
        cluster_id: string;
        cluster_name: string;
        ownership_basis: string;
        protocol: string;
        route_ids: string[];
        projected_load_percent: number;
        load_check: string;
        alternatives: string[];
      }>;
    }>;
  };
  system_health: {
    score: number;
    counts: Record<string, number>;
    metrics: Record<string, number>;
    metric_evidence?: Record<string, string>;
    unevaluated_metrics?: string[];
    scope_coverage?: import("./types").SimulationCoverage;
    simulation_assessment?: import("./types").SimulationAssessment | null;
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

export const getIntelligence = (projectId?: string) =>
  request<IntelligenceSnapshot>("/intelligence", {
    headers: projectId ? { "X-Project-ID": projectId } : undefined,
  });

export const assessIntelligence = (projectId?: string) =>
  request<IntelligenceSnapshot>("/intelligence/assess", {
    method: "POST", body: "{}", signal: AbortSignal.timeout(30000),
    headers: projectId ? { "X-Project-ID": projectId } : undefined,
  });

export const approveIntelligenceIssue = (issue: Pick<IntelligenceIssue, "code" | "object_type" | "object_id">, projectId?: string) =>
  request<IntelligenceSnapshot>("/intelligence/issues/approve", {
    method: "POST",
    headers: projectId ? { "X-Project-ID": projectId } : undefined,
    body: JSON.stringify({
      code: issue.code,
      object_type: issue.object_type,
      object_id: issue.object_id,
      actor: "intelligence-workbench",
    }),
  });

export const approveIntelligenceIssues = (issues: Array<Pick<IntelligenceIssue, "code" | "object_type" | "object_id">>, projectId?: string) =>
  request<IntelligenceSnapshot>("/intelligence/issues/approve-all", {
    method: "POST",
    headers: projectId ? { "X-Project-ID": projectId } : undefined,
    body: JSON.stringify({
      issues: issues.map((issue) => ({
        code: issue.code,
        object_type: issue.object_type,
        object_id: issue.object_id,
        actor: "intelligence-workbench",
      })),
    }),
  });

export const listOptimizationProposals = (projectId?: string) =>
  request<{ items: OptimizationProposal[]; count: number }>("/intelligence/proposals", {
    headers: projectId ? { "X-Project-ID": projectId } : undefined,
  });

export const createOptimizationProposal = (proposal: IntelligenceRecommendation, projectId?: string) =>
  request<OptimizationProposal>("/intelligence/proposals", {
    method: "POST",
    headers: projectId ? { "X-Project-ID": projectId } : undefined,
    body: JSON.stringify(proposal),
  });

export const reviewOptimizationProposal = (proposalId: string, status: OptimizationProposal["status"], reason?: string) =>
  request<OptimizationProposal>(`/intelligence/proposals/${proposalId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, reason, actor: "intelligence-workbench" }),
  });

export const intelligenceExportUrl = (format: "json" | "csv", section = "issues") =>
  `${workflowBaseUrl()}/intelligence/export?format=${format}&section=${encodeURIComponent(section)}&project=${encodeURIComponent(compactProjectId(readActiveProjectId()))}`;

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
  }).then((result) => {
    clearWorkflowApiCaches(projectId);
    return { ...result, workflow: normalizeWorkflowState(result.workflow) };
  });
