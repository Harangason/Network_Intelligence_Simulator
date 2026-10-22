import type { UIMessage } from "ai";
import type { InteractiveQuestion } from "./agent-response";
import type { ChatAttachment } from "./chat-attachments";

/** Transport contracts only. Engineering orchestration lives in Python Agent Core. */
export type DocumentIntakeProposal = {
  status: 'REVIEW_REQUIRED';
  source_name: string;
  source_sha256: string;
  source_request_id: string | null;
  source_chars: number;
  source_complete: boolean;
  model: string;
  provider: 'local_ollama';
  canonical_writes: false;
  interpretation: {
    summary: string;
    components: { name: string; kind: 'INSTANCE' | 'CATEGORY' | 'FUNCTION' | 'REQUIREMENT'; role: string; quantity: number | null; source_quote: string; source_context?: string[] }[];
    technologies: { name: string; kind: 'TRANSPORT' | 'DEVICE_ALIAS' | 'UNRESOLVED'; source_quote: string }[];
    proposed_task: string;
    assumptions: string[];
    open_questions: string[];
  };
};

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
    object_name?: string; object_type?: string; object_ref?: string; object_id?: string;
    technology?: string; network_id?: string; network_name?: string; node_name?: string; missing_fields?: string[]; repair_action?: string;
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

type DocumentToolResult = { success: boolean; data?: DocumentIntakeProposal; error?: string; findings?: { message?: string }[] };
export async function readDocumentIntakeResponse(response: Response, onProgress: (text: string) => void): Promise<DocumentIntakeProposal> {
  let result: DocumentToolResult | undefined;
  if (response.headers.get('Content-Type')?.includes('application/x-ndjson') && response.body) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let bytes = 0;
    const receive = (line: string) => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === 'PROGRESS' && typeof event.text === 'string') onProgress(event.text);
      if (event.type === 'RESULT') result = event.result;
    };
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        bytes += part.value.byteLength;
        if (bytes > 2_000_000) throw new Error('Die lokale Dokumentantwort ist zu groß.');
        buffer += decoder.decode(part.value, { stream: true });
        let boundary: number;
        while ((boundary = buffer.indexOf('\n')) >= 0) {
          receive(buffer.slice(0, boundary)); buffer = buffer.slice(boundary + 1);
        }
      }
      receive(buffer + decoder.decode());
    } finally { await reader.cancel(); reader.releaseLock(); }
  } else result = await response.json();
  if (!response.ok || !result?.success || !result.data) {
    throw new Error(result?.error ?? result?.findings?.[0]?.message ?? 'Die vollständige lokale Dokumentauswertung ist fehlgeschlagen.');
  }
  return result.data;
}
