export type Technology = {
  id: string;
  kind: string;
  family: string;
  medium: string;
  topology: string;
  default_bitrate?: number | null;
  max_payload_bytes?: number | null;
  native_formats?: string[];
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
};

export type SimulationJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  validate_only: boolean;
  created_at: string;
  updated_at: string;
  error: string | null;
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
