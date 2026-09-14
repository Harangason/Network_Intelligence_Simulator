import { createUIMessageStream, createUIMessageStreamResponse } from "ai";
import type { EngineeringAgentUIMessage, EngineeringAgentEvent } from "@/lib/agent/engineering-agent";
import { uniqueMessagesById } from "@/lib/agent-message-history";
import { parseAgentResponse, type AgentInput } from "@/lib/agent/agent-response";
import { backendEndpoints } from "@/lib/backend-endpoints";
import { chatDocumentContext, validateChatAttachment } from "@/lib/agent/chat-attachments";
import { expandBrowserProjectId } from '@/lib/user-settings';
import { parseWizardCommand, type WizardCommand } from '@/lib/agent/wizard-protocol';

export const maxDuration = 300;
const { engineering: backend } = backendEndpoints(process.env);
class AgentServiceError extends Error {}

export async function POST(request: Request) {
  let payload: { messages?: EngineeringAgentUIMessage[]; context?: Record<string, unknown>; input?: AgentInput; wizard_command?: WizardCommand };
  try { payload = await request.json(); }
  catch { return Response.json({ error: "Ein JSON-Objekt wird erwartet." }, { status: 400 }); }
  if (payload?.wizard_command !== undefined) {
    try { payload.wizard_command = parseWizardCommand(payload.wizard_command); }
    catch { return Response.json({ error: 'Ungültiges Wizardkommando. Auftrag und Revision erneut laden.' }, { status: 400 }); }
  }
  if (!payload || (payload.messages !== undefined && (!Array.isArray(payload.messages) || payload.messages.length > 60 || payload.messages.some(message => !message || typeof message.id !== 'string' || !['user','assistant','system'].includes(message.role) || !Array.isArray(message.parts) || message.parts.some(part => !part || typeof part.type !== 'string')))))
    return Response.json({ error: 'Ungültiger Gesprächsverlauf.' }, { status: 400 });
  const messages = uniqueMessagesById(payload.messages ?? []);
  const lastUser = [...messages].reverse().find(message => message.role === "user");
  try {
    for (const message of messages) chatDocumentContext(message.parts);
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : 'Ungültiger Dokumentanhang.' }, { status: 400 });
  }
  const prompt = lastUser?.parts.filter(part => part.type === "text").map(part => part.text).join("\n").trim();
  if (!prompt && !payload.input && !payload.wizard_command) return Response.json({ error: "Eine Anforderung wird erwartet." }, { status: 400 });
  const projectId = request.headers.get("X-Project-ID") ?? "default";
  if (payload.context?.active_project_id && expandBrowserProjectId(payload.context.active_project_id) !== expandBrowserProjectId(projectId))
    return Response.json({ error: 'Das Projekt wurde gewechselt. Bitte den Assistenten im aktuellen Projekt öffnen.' }, { status: 409 });
  const previousContext = [...messages].reverse().flatMap(message => [...message.parts].reverse())
    .find(part => part.type === "data-engineering" && part.data.type === "CONTEXT");
  const history = messages.filter(message => message.id !== lastUser?.id).slice(-12).map(message => ({
    role: message.role,
    content: message.parts.flatMap(part => part.type === "text" ? [part.text]
      : part.type === "data-engineering" && part.data.type === "APPROVAL" && part.data.proposal
        ? [`Vorschlag ${part.data.proposal.proposal_id}: ${part.data.proposal.rationale}`] : []).join("\n").slice(0, 8000),
  })).filter(message => (message.role === "user" || message.role === "assistant") && message.content);
  const sourceMessage = [...messages].reverse().find(message => message.role === 'user' && message.parts.some(part => part.type === 'data-attachment'));
  const documents = sourceMessage?.parts.filter(part => part.type === 'data-attachment').map(part => validateChatAttachment(part.data)) ?? [];
  const context = { ...(previousContext?.type === "data-engineering" ? previousContext.data.context : {}),
    ...payload.context, active_project_id: projectId, document_sources: documents };
  const stream = createUIMessageStream<EngineeringAgentUIMessage>({
    originalMessages: messages,
    execute: async ({ writer }) => {
      const response = await fetch(`${backend}/agent/chat`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Project-ID": projectId },
        body: JSON.stringify({ prompt: payload.input && !payload.wizard_command ? "" : prompt, input: payload.input, wizard_command: payload.wizard_command, context, history }), cache: "no-store",
        signal: AbortSignal.any([request.signal, AbortSignal.timeout(290000)]),
      });
      if (!response.ok || !response.body) {
        const details = await response.json().catch(() => ({}));
        throw new AgentServiceError(String(details.error ?? details.findings?.[0]?.message ?? `Engineering-Agent nicht verfügbar (${response.status}).`).slice(0, 500));
      }
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let buffer = "";
      const publish = (line: string) => {
        if (!line.trim()) return;
        let raw: unknown;
        try { raw = JSON.parse(line); } catch { raw = null; }
        if ((raw as { type?: string } | null)?.type === "HEARTBEAT") return;
        const event = (raw as { type?: string } | null)?.type === "CONTEXT" ? raw as EngineeringAgentEvent : parseAgentResponse(raw) as EngineeringAgentEvent;
        writer.write({ type: "data-engineering", id: crypto.randomUUID(), data: event });
      };
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += value;
          if (buffer.length > 5_000_000) throw new AgentServiceError('Die Antwort ist zu groß für den Chat. Bitte den Auftrag eingrenzen.');
          let newline: number;
          while ((newline = buffer.indexOf("\n")) >= 0) {
            publish(buffer.slice(0, newline));
            buffer = buffer.slice(newline + 1);
          }
        }
        publish(buffer);
      } finally { reader.releaseLock(); }
    },
    onError: error => error instanceof AgentServiceError ? error.message : "Der Engineering-Agent konnte den Auftrag nicht abschließen. Bitte den Dienststatus prüfen.",
  });
  return createUIMessageStreamResponse({ stream });
}
