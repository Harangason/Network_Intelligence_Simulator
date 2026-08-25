import { createAgentUIStreamResponse, UIMessage } from "ai";
import { engineeringAgent } from "@/lib/agent/engineering-agent";

export const maxDuration = 60;

export async function POST(request: Request) {
  const { messages }: { messages: UIMessage[] } = await request.json();

  return createAgentUIStreamResponse({
    agent: engineeringAgent,
    uiMessages: messages,
  });
}
