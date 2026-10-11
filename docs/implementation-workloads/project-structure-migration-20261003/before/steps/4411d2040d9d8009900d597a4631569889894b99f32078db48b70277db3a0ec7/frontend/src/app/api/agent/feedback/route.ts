import { recordAgentFeedback, type AgentFeedbackRating } from "@/lib/agent/feedback-store";

export async function POST(request: Request) {
  let payload: Record<string, unknown>;
  try {
    payload = await request.json() as Record<string, unknown>;
  } catch {
    return Response.json({ error: "Ein gültiger JSON-Body wird erwartet." }, { status: 400 });
  }
  const rating = String(payload.rating ?? "") as AgentFeedbackRating;
  if (!(["helpful", "incorrect"] as string[]).includes(rating)) {
    return Response.json({ error: "rating muss helpful oder incorrect sein." }, { status: 400 });
  }
  const prompt = String(payload.prompt ?? "").trim();
  const response = String(payload.response ?? "").trim();
  if (!prompt || !response) {
    return Response.json({ error: "Prompt und Antwort werden benötigt." }, { status: 400 });
  }
  const record = await recordAgentFeedback({
    projectId: request.headers.get("X-Project-ID"),
    messageId: payload.messageId,
    prompt,
    response,
    rating,
    correction: payload.correction,
  });
  return Response.json({ id: record.id, learned: true });
}
