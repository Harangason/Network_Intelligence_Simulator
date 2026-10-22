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

type DocumentToolResult<T> = { success: boolean; data?: T; error?: string; findings?: { message?: string }[] };
export function documentRequestErrorMessage(error: unknown, stage: 'document' | 'reference' = 'document'): string {
  const message = error instanceof Error ? error.message : '';
  const operation = stage === 'reference' ? 'Referenzplanung' : 'Dokumentauswertung';
  if (/^(?:network error|failed to fetch|fetch failed|load failed|NetworkError(?: when attempting to fetch resource)?|The network connection was lost)[.!]?$/i.test(message.trim())) {
    return `Die Verbindung zur lokalen ${operation} wurde unterbrochen. Es wurde kein vollständiges Prüfergebnis empfangen. Datei und Eingaben bleiben erhalten. Bitte die Prüfung erneut starten.`;
  }
  return message || `Die lokale ${operation} ist fehlgeschlagen. Bitte die Prüfung erneut starten.`;
}

export async function readDocumentIntakeResponse<T = DocumentIntakeProposal>(response: Response, onProgress: (text: string) => void, maxBytes = 2_000_000, signal?: AbortSignal): Promise<T> {
  signal?.throwIfAborted();
  let result: DocumentToolResult<T> | undefined;
  if (response.headers.get('Content-Type')?.includes('application/x-ndjson') && response.body) {
    const reader = response.body.getReader();
    const abort = () => { void reader.cancel(signal?.reason).catch(() => undefined); };
    signal?.addEventListener('abort', abort, { once: true });
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
        signal?.throwIfAborted();
        if (part.done) break;
        bytes += part.value.byteLength;
        if (bytes > maxBytes) throw new Error('Die lokale Dokumentantwort ist zu groß.');
        buffer += decoder.decode(part.value, { stream: true });
        let boundary: number;
        while ((boundary = buffer.indexOf('\n')) >= 0) {
          receive(buffer.slice(0, boundary)); buffer = buffer.slice(boundary + 1);
        }
      }
      receive(buffer + decoder.decode());
    } finally {
      signal?.removeEventListener('abort', abort);
      try { await reader.cancel().catch(() => undefined); } finally { reader.releaseLock(); }
    }
  } else result = await response.json();
  signal?.throwIfAborted();
  if (!response.ok || !result?.success || !result.data) {
    throw new Error(result?.error ?? result?.findings?.[0]?.message ?? 'Die vollständige lokale Dokumentauswertung ist fehlgeschlagen.');
  }
  return result.data;
}


export type ReferenceSource = {
  id: string; name: string; role: 'REFERENCE_SUPPLEMENT' | 'USER_CLARIFICATION';
  text: string; source_sha256: string;
  allowed_fields: ('quantity' | 'device_type' | 'function_hosts' | 'ports' | 'measurements' | 'commands' | 'communication')[];
};
export type ReferenceDesignRecord = {
  schema_version: 1; design_id: string; revision: number;
  project_id: string; source_sha256: string; request_sha256: string;
  status: 'REVIEW_REQUIRED' | 'ACCEPTED'; canonical_writes: false;
  qualification?: 'UNVERIFIED'; hardware_evidence?: false;
  qualification_findings?: { target_ref: string; technology: string; parameter: string; value_role: string;
    qualification: 'UNVERIFIED'; hardware_evidence: false; finding: Record<string, unknown> }[];
  request: { mode: 'EXAMPLE_PROJECT'; prompt: string; reference_sources: ReferenceSource[]; source_request_id?: string };
  fact_id_map: Record<string, string>;
  proposal: {
    devices: { id: string; name: string; kind: string; quantity: number; rationale: string; owner_device_id?: string | null }[];
    functions: { source_fact_id: string; realization: 'ATOMIC' | 'COMPOSITE'; executor_device_ids: string[]; realized_by_fact_ids: string[]; rationale: string }[];
    ports: { id: string; device_id: string; technology: string; role: string; network_scope: string; parameters: Record<string, unknown>; rationale: string }[];
    measurements: { device_id: string; measurement_id: string; rationale: string }[];
    commands: { device_id: string; definition: Record<string, unknown>; rationale: string }[];
    communication: { id: string; producer_device_id: string; consumer_device_ids: string[]; signal_name: string; rationale: string; encoding: Record<string, unknown> }[];
    functional_dependencies: { id: string; producer_fact_id: string; consumer_fact_ids: string[]; executor_device_id: string; signal_name: string; rationale: string; encoding: Record<string, unknown> }[];
    unresolved: { code: string; target_ref: string; message: string }[];
  };
  decision_evidence: Record<string, unknown>[];
  protected_fields: Record<string, unknown>;
};

export function referenceDesignMarker(record: ReferenceDesignRecord) {
  if (record.status !== 'ACCEPTED' || record.canonical_writes !== false) throw new Error('Referenzannahmen zuerst prüfen und übernehmen.');
  return '- Dokument-Referenzentwurf: ' + JSON.stringify(Object.fromEntries([
    'schema_version', 'design_id', 'revision', 'request_sha256', 'source_sha256', 'status',
    'proposal', 'fact_id_map', 'decision_evidence', 'protected_fields',
  ].map(key => [key, record[key as keyof ReferenceDesignRecord]])));
}
