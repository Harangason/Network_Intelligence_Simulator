import { createAgentUIStreamResponse, createUIMessageStream, createUIMessageStreamResponse, UIMessage } from "ai";
import {
  engineeringAgent,
  engineeringAgentModel,
  engineeringAgentOrchestrator,
  engineeringAgentProvider,
  registerEngineeringSpecification,
} from "@/lib/agent/engineering-agent";
import { AGENT_OUTPUT_RECOVERY_CONTEXT, inspectAgentText } from "@/lib/agent/agent-output-safety";
import { isStructuredEngineeringSpecification } from "@/lib/agent/engineering-specification";
import { runWithAgentProject } from "@/lib/agent/request-context";

export const maxDuration = 300;

function audit(message: string, details: Record<string, unknown> = {}) {
  const suffix = Object.entries(details)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" ");
  console.info(`[NetworkIS Agent] ${message}${suffix ? ` ${suffix}` : ""}`);
}

function uiMessageText(message: UIMessage | undefined) {
  if (!message) return "";
  const parts = Array.isArray(message.parts) ? message.parts : [];
  return parts
    .map((part) => {
      if (part && typeof part === "object" && "text" in part && typeof part.text === "string") return part.text;
      return "";
    })
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .slice(0, 180);
}

function uiMessageFullText(message: UIMessage | undefined) {
  if (!message) return "";
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("\n");
}

function sanitizeAgentHistory(messages: UIMessage[]) {
  let blockedOutputs = 0;
  const sanitized = messages.map((message) => {
    if (message.role !== "assistant") return message;
    return {
      ...message,
      parts: message.parts.map((part) => {
        if (part.type !== "text") return part;
        const safety = inspectAgentText(part.text);
        if (!safety.blocked) return part;
        blockedOutputs += 1;
        return { ...part, text: AGENT_OUTPUT_RECOVERY_CONTEXT };
      }),
    };
  });
  return { blockedOutputs, messages: sanitized };
}

function specificationSummary(result: Awaited<ReturnType<typeof registerEngineeringSpecification>>) {
  const failures = Array.isArray(result.failures) ? result.failures.length : 0;
  const registered = Number(result.registered_chains ?? 0);
  const recognized = Number(result.recognized ?? 0);
  if (failures > 0) {
    return `${registered} von ${recognized} erkannten Teilnehmern wurden vollstaendig registriert. ${failures} Teilnehmer konnten nicht angelegt werden.`;
  }
  return `${recognized} Teilnehmer erkannt. ${registered} vollstaendige Engineering-Ketten mit Hardware, Funktion, Interface, Nachricht und Signal wurden registriert.`;
}

function createSpecificationResponse(messages: UIMessage[], specificationText: string) {
  const stream = createUIMessageStream({
    originalMessages: messages,
    onError: (error) => error instanceof Error ? error.message : "Die Spezifikation konnte nicht verarbeitet werden.",
    execute: async ({ writer }) => {
      const toolCallId = crypto.randomUUID();
      writer.write({ type: "start-step" });
      writer.write({
        type: "tool-input-available",
        toolCallId,
        toolName: "createEngineeringModelFromSpecification",
        input: {},
      });
      try {
        const result = await registerEngineeringSpecification(specificationText);
        writer.write({ type: "tool-output-available", toolCallId, output: result });
        const textId = crypto.randomUUID();
        writer.write({ type: "text-start", id: textId });
        writer.write({ type: "text-delta", id: textId, delta: specificationSummary(result) });
        writer.write({ type: "text-end", id: textId });
      } catch (error) {
        const errorText = error instanceof Error ? error.message : String(error);
        writer.write({ type: "tool-output-error", toolCallId, errorText });
        throw error;
      } finally {
        writer.write({ type: "finish-step" });
      }
    },
  });
  return createUIMessageStreamResponse({ stream });
}

export async function POST(request: Request) {
  let payload: { messages?: UIMessage[] };
  try {
    payload = await request.json();
  } catch {
    audit("request rejected", { reason: "invalid-json" });
    return Response.json({ error: "Ein gültiger JSON-Body wird erwartet." }, { status: 400 });
  }
  if (!Array.isArray(payload.messages) || payload.messages.length === 0) {
    audit("request rejected", { reason: "missing-messages" });
    return Response.json({ error: "Mindestens eine Nachricht wird erwartet." }, { status: 400 });
  }

  const requestId = crypto.randomUUID();
  const projectId = request.headers.get("X-Project-ID") ?? "default";
  const sanitizedHistory = sanitizeAgentHistory(payload.messages);
  const lastUserMessage = [...payload.messages].reverse().find((message) => message.role === "user");
  const requestText = uiMessageFullText(lastUserMessage);
  audit("request started", {
    requestId,
    projectId,
    provider: engineeringAgentProvider,
    model: engineeringAgentModel,
    orchestrator: engineeringAgentOrchestrator,
    messages: payload.messages.length,
    blockedOutputs: sanitizedHistory.blockedOutputs,
    prompt: uiMessageText(lastUserMessage),
  });

  if (engineeringAgentProvider === "unconfigured") {
    audit("request failed", { requestId, reason: "missing-api-key" });
    return Response.json(
      {
        error:
          "Der Engineering-Agent ist nicht konfiguriert. Setze AI_PROVIDER auf local, openai oder nvidia und konfiguriere den gewählten Provider.",
      },
      { status: 503 },
    );
  }

  if (isStructuredEngineeringSpecification(requestText)) {
    audit("structured specification execution started", { requestId, projectId });
    return runWithAgentProject(
      request.headers.get("X-Project-ID"),
      () => createSpecificationResponse(sanitizedHistory.messages, requestText),
      requestText,
    );
  }

  return runWithAgentProject(request.headers.get("X-Project-ID"), () =>
    createAgentUIStreamResponse({
      agent: engineeringAgent,
      uiMessages: sanitizedHistory.messages,
      onStepEnd: (step) => {
        audit("step finished", {
          requestId,
          finishReason: step.finishReason,
          toolCalls: step.toolCalls.length,
          toolResults: step.toolResults.length,
        });
      },
    }), requestText,
  );
}
