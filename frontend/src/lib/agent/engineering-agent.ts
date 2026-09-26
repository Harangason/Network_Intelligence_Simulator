import type { UIMessage } from "ai";
import type { InteractiveQuestion } from "./agent-response";
import type { ChatAttachment } from "./chat-attachments";

/** Transport contracts only. Engineering orchestration lives in Python Agent Core. */
export type EngineeringAgentEvent = {
  outputs?: import('./input-output').AgentOutputEnvelope[];
  type: string;
  status?: string;
  text?: string;
  severity?: string;
  context?: Record<string, unknown>;
  wizard_receipt?: import('./wizard-protocol').WizardReceipt;
  proposal?: EngineeringProposal;
  workload?: Record<string, unknown>;
  options?: { id?: string; value?: string; label: string; recommended?: boolean }[];
  question_id?: string;
  id?: string;
  title?: string;
  question?: InteractiveQuestion;
  context_refs?: Record<string, string>[];
  actions?: Record<string, unknown>[];
  findings?: Record<string, unknown>[];
  progress?: Record<string, string>[];
  recommendation?: Record<string, unknown>;
  approval?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  created_at?: string;
};
export type EngineeringProposal = {
  content_state?: "REFERENCE" | "FULL";
  change_count?: number;
  canonical_count?: number;
  proposal_id: string;
  proposal_type: string;
  revision: string;
  status: "PROPOSED" | "VALIDATED" | "REJECTED" | "APPROVED" | "APPLIED" | "OUTDATED";
  rationale: string;
  assumptions: string[];
  changes: { local_ref?: string; action: string; object_type: string; object_id?: string; object_name?: string; data?: Record<string, unknown>; impact_analysis?: Record<string, unknown> }[];
  validation_result: { valid?: boolean; requested?: number; valid_count?: number; findings?: {
    message: string; code?: string; severity?: string; index?: number;
    object_name?: string; object_type?: string; object_ref?: string;
    source?: Record<string, unknown>; destinations?: Record<string, unknown>[];
  }[] };
  canonical_ids: { object_type: string; id: string }[];
  workload_id?: string;
  dependent_results?: {
    network_id: string;
    bitrate_bps: number;
    capacity_snapshot_id: string;
    capacity_status?: string;
    capacity_findings?: Record<string, unknown>[];
    preflight_snapshot_id: string;
    preflight_status?: string;
    preflight_ready_for_simulation?: boolean;
    preflight_findings?: Record<string, unknown>[];
    completion?: {
      status: string;
      completed: boolean;
      missing_outcomes: string[];
      failure?: { message: string };
    };
  };
};
export type EngineeringAgentUIMessage = UIMessage<unknown, { engineering: EngineeringAgentEvent; attachment: ChatAttachment }, Record<string, { input: Record<string, unknown>; output: unknown }>>;
