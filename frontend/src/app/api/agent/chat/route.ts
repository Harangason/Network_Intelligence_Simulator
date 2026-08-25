import { createAgentUIStreamResponse, UIMessage } from "ai";
import { engineeringAgent } from "@/lib/agent/engineering-agent";
import { runWithAgentProject } from "@/lib/agent/request-context";

export const maxDuration = 120;

export async function POST(request: Request) {
  let payload: { messages?: UIMessage[] };
  try {
    payload = await request.json();
  } catch {
    return Response.json({ error: "Ein gültiger JSON-Body wird erwartet." }, { status: 400 });
  }
  if (!Array.isArray(payload.messages) || payload.messages.length === 0) {
    return Response.json({ error: "Mindestens eine Nachricht wird erwartet." }, { status: 400 });
  }

  return runWithAgentProject(request.headers.get("X-Project-ID"), () =>
    createAgentUIStreamResponse({
      agent: engineeringAgent,
      uiMessages: payload.messages!,
    }),
  );
}
