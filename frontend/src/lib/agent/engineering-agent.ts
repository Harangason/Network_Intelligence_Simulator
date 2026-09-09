import type { UIMessage } from "ai";
import type { InteractiveQuestion } from "./agent-response";

/** Transport contracts only. Engineering orchestration lives in Python Agent Core. */
export type EngineeringAgentEvent = {
  type: string;
  status?: string;
  text?: string;
  severity?: string;
  context?: Record<string, unknown>;
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
  validation_result: { valid?: boolean; findings?: { message: string }[] };
  canonical_ids: { object_type: string; id: string }[];
  workload_id?: string;
};
export type EngineeringAgentUIMessage = UIMessage<unknown, { engineering: EngineeringAgentEvent }, Record<string, { input: Record<string, unknown>; output: unknown }>>;
