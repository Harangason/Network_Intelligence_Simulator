import "server-only";

import type { UIMessage } from "ai";

import { uniqueMessagesById } from "@/lib/agent-message-history";
import {
  deleteProgramCache,
  pruneProgramCache,
  readProgramCache,
  writeProgramCache,
} from "@/lib/server/program-cache";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const CACHE_NAMESPACE = "agent-chat";
const MAX_MESSAGES = 60;
const MAX_CACHE_BYTES = 1_500_000;
const MAX_REQUEST_BYTES = 5_000_000;
const MAX_PROJECTS = 100;
const CACHE_TTL_MS = 24 * 60 * 60 * 1000;

type CachedHistory = {
  messages: UIMessage[];
};

function projectIdFrom(request: Request, payload?: Record<string, unknown> | null) {
  const fromQuery = new URL(request.url).searchParams.get("projectId");
  return String(payload?.projectId ?? fromQuery ?? "").trim();
}

function isMessage(value: unknown): value is UIMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Partial<UIMessage>;
  return typeof message.id === "string"
    && ["system", "user", "assistant"].includes(String(message.role))
    && Array.isArray(message.parts);
}

function compactValue(value: unknown, depth = 0): unknown {
  if (typeof value === "string") {
    return value.length > 64_000 ? `${value.slice(0, 64_000)}\n[Cache-Ausgabe gekuerzt]` : value;
  }
  if (value === null || typeof value !== "object") return value;
  if (depth >= 8) return "[Cache-Tiefe begrenzt]";
  if (Array.isArray(value)) {
    const compacted = value.slice(0, 100).map((item) => compactValue(item, depth + 1));
    if (value.length > 100) compacted.push(`[${value.length - 100} weitere Eintraege nicht gecacht]`);
    return compacted;
  }
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .slice(0, 100)
      .map(([key, item]) => [key, compactValue(item, depth + 1)]),
  );
}

function compactMessage(message: UIMessage): UIMessage {
  return compactValue(message) as UIMessage;
}

function boundedMessages(value: unknown): UIMessage[] {
  const candidates = Array.isArray(value)
    ? uniqueMessagesById(value.filter(isMessage)).slice(-MAX_MESSAGES).map(compactMessage)
    : [];
  const selected: UIMessage[] = [];
  let bytes = 2;
  for (let index = candidates.length - 1; index >= 0; index -= 1) {
    const message = candidates[index];
    const messageBytes = Buffer.byteLength(JSON.stringify(message), "utf8") + 1;
    if (messageBytes > MAX_CACHE_BYTES) continue;
    if (bytes + messageBytes > MAX_CACHE_BYTES && selected.length > 0) break;
    selected.unshift(message);
    bytes += messageBytes;
  }
  return selected;
}

function noStore(payload: unknown, init?: ResponseInit) {
  return Response.json(payload, {
    ...init,
    headers: { ...init?.headers, "Cache-Control": "no-store" },
  });
}

export async function GET(request: Request) {
  const projectId = projectIdFrom(request);
  if (!projectId) return noStore({ error: "projectId fehlt." }, { status: 400 });
  const entry = await readProgramCache<CachedHistory>(CACHE_NAMESPACE, projectId);
  return noStore({
    messages: boundedMessages(entry?.value.messages),
    updatedAt: entry?.updatedAt ?? null,
  });
}

export async function PUT(request: Request) {
  const contentLength = Number(request.headers.get("content-length") ?? 0);
  if (contentLength > MAX_REQUEST_BYTES) {
    return noStore({ error: "Agentenverlauf ist zu gross fuer den Cache." }, { status: 413 });
  }
  const payload = await request.json().catch(() => null) as Record<string, unknown> | null;
  const projectId = projectIdFrom(request, payload);
  if (!payload || !projectId || !Array.isArray(payload.messages)) {
    return noStore({ error: "projectId und messages sind erforderlich." }, { status: 400 });
  }
  const messages = boundedMessages(payload.messages);
  const entry = await writeProgramCache<CachedHistory>(
    CACHE_NAMESPACE,
    projectId,
    { messages },
    MAX_CACHE_BYTES + 2048,
    CACHE_TTL_MS,
  );
  await pruneProgramCache(CACHE_NAMESPACE, MAX_PROJECTS);
  return noStore({ ok: true, messageCount: messages.length, updatedAt: entry.updatedAt });
}

export async function DELETE(request: Request) {
  const projectId = projectIdFrom(request);
  if (!projectId) return noStore({ error: "projectId fehlt." }, { status: 400 });
  await deleteProgramCache(CACHE_NAMESPACE, projectId);
  return noStore({ ok: true });
}
