import { createAgentUIStreamResponse, UIMessage } from "ai";
import { engineeringAgent, engineeringAgentProvider } from "@/lib/agent/engineering-agent";
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
  const lastUserMessage = [...payload.messages].reverse().find((message) => message.role === "user");
  audit("request started", {
    requestId,
    projectId,
    provider: engineeringAgentProvider,
    messages: payload.messages.length,
    prompt: uiMessageText(lastUserMessage),
  });

  if (engineeringAgentProvider === "unconfigured") {
    audit("request failed", { requestId, reason: "missing-api-key" });
    return Response.json(
      {
        error:
          "Der Engineering-Agent ist nicht konfiguriert. Für lokale Entwicklung muss OPENAI_API_KEY oder NVIDIA_API_KEY im NetworkIS-Container gesetzt sein.",
      },
      { status: 503 },
    );
  }

  return runWithAgentProject(request.headers.get("X-Project-ID"), () =>
    createAgentUIStreamResponse({
      agent: engineeringAgent,
      uiMessages: payload.messages!,
      onStepEnd: (step) => {
        audit("step finished", {
          requestId,
          finishReason: step.finishReason,
          toolCalls: step.toolCalls.length,
          toolResults: step.toolResults.length,
        });
      },
    }),
  );
}
