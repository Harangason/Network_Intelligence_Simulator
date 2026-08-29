import type { UIMessage } from "ai";
import { uniqueMessagesById } from "@/lib/agent-message-history";

const DB_NAME = "communication-simulator-agent-chat";
const STORE_NAME = "project-histories";
const FALLBACK_PREFIX = "networkis:engineering-agent-history:";
const MAX_MESSAGES = 60;
const MAX_TRANSPORT_BYTES = 4_500_000;

type StoredHistory = {
  projectId: string;
  messages: UIMessage[];
  updatedAt: number;
};

type HistoryResponse = {
  messages?: unknown;
  updatedAt?: number | null;
};

let legacyMigration: Promise<Map<string, UIMessage[]>> | null = null;

function historyKey(projectId: string) {
  return projectId.trim() || "default";
}

function historyUrl(projectId: string) {
  return `/api/agent/history?projectId=${encodeURIComponent(historyKey(projectId))}`;
}

function isStoredMessage(value: unknown): value is UIMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Partial<UIMessage>;
  return typeof message.id === "string"
    && ["system", "user", "assistant"].includes(String(message.role))
    && Array.isArray(message.parts);
}

function validatedMessages(value: unknown): UIMessage[] {
  return Array.isArray(value)
    ? uniqueMessagesById(value.filter(isStoredMessage)).slice(-MAX_MESSAGES)
    : [];
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

function transportMessages(messages: UIMessage[]) {
  const selected = uniqueMessagesById(messages)
    .slice(-MAX_MESSAGES)
    .map((message) => compactValue(message) as UIMessage);
  let body = JSON.stringify({ messages: selected });
  while (selected.length > 1 && body.length > MAX_TRANSPORT_BYTES) {
    selected.shift();
    body = JSON.stringify({ messages: selected });
  }
  return selected;
}

async function readServerHistory(projectId: string) {
  try {
    const response = await fetch(historyUrl(projectId), {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return { found: false, messages: [] as UIMessage[] };
    const payload = await response.json() as HistoryResponse;
    return {
      found: typeof payload.updatedAt === "number",
      messages: validatedMessages(payload.messages),
    };
  } catch {
    return { found: false, messages: [] as UIMessage[] };
  }
}

async function writeServerHistory(projectId: string, messages: UIMessage[]) {
  try {
    const response = await fetch("/api/agent/history", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ projectId: historyKey(projectId), messages: transportMessages(messages) }),
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

function openHistoryDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is unavailable."));
      return;
    }
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME);
      }
    };
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

async function readIndexedHistories() {
  const histories = new Map<string, UIMessage[]>();
  try {
    const db = await openHistoryDatabase();
    const stored = await new Promise<StoredHistory[]>((resolve, reject) => {
      const request = db.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).getAll();
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve((request.result as StoredHistory[] | undefined) ?? []);
    });
    db.close();
    stored.forEach((entry) => {
      const projectId = historyKey(entry.projectId);
      const messages = validatedMessages(entry.messages);
      if (messages.length) histories.set(projectId, messages);
    });
  } catch {
    // Browser persistence can be disabled; the program cache remains usable.
  }
  return histories;
}

function readFallbackHistories(histories: Map<string, UIMessage[]>) {
  if (typeof window === "undefined") return;
  try {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (!key?.startsWith(FALLBACK_PREFIX)) continue;
      const stored = JSON.parse(window.localStorage.getItem(key) ?? "null") as Partial<StoredHistory> | null;
      const projectId = historyKey(stored?.projectId ?? decodeURIComponent(key.slice(FALLBACK_PREFIX.length)));
      const messages = validatedMessages(stored?.messages);
      if (messages.length && !histories.has(projectId)) histories.set(projectId, messages);
    }
  } catch {
    // A blocked or malformed browser store is ignored.
  }
}

async function clearLegacyHistories() {
  if (typeof window !== "undefined") {
    try {
      const keys = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index))
        .filter((key): key is string => Boolean(key?.startsWith(FALLBACK_PREFIX)));
      keys.forEach((key) => window.localStorage.removeItem(key));
    } catch {
      // A blocked localStorage implementation must not break the agent.
    }
  }
  try {
    const db = await openHistoryDatabase();
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      transaction.objectStore(STORE_NAME).clear();
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
    db.close();
  } catch {
    // The migration is already complete when no legacy database exists.
  }
}

async function migrateLegacyHistories() {
  const histories = await readIndexedHistories();
  readFallbackHistories(histories);
  let complete = true;
  for (const [projectId, messages] of histories) {
    const cached = await readServerHistory(projectId);
    if (cached.found) continue;
    if (!await writeServerHistory(projectId, messages)) complete = false;
  }
  if (complete) await clearLegacyHistories();
  return histories;
}

function ensureLegacyMigration() {
  legacyMigration ??= migrateLegacyHistories();
  return legacyMigration;
}

export async function readEngineeringAgentHistory<UI_MESSAGE extends UIMessage>(
  projectId: string,
): Promise<UI_MESSAGE[]> {
  const cached = await readServerHistory(projectId);
  if (cached.found) {
    void ensureLegacyMigration();
    return cached.messages as UI_MESSAGE[];
  }
  const legacy = await ensureLegacyMigration();
  return (legacy.get(historyKey(projectId)) ?? []) as UI_MESSAGE[];
}

export async function saveEngineeringAgentHistory(
  projectId: string,
  messages: UIMessage[],
): Promise<boolean> {
  return writeServerHistory(projectId, messages);
}

export async function clearEngineeringAgentHistory(projectId: string): Promise<void> {
  await ensureLegacyMigration();
  try {
    await fetch(historyUrl(projectId), {
      method: "DELETE",
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    // Clearing remains non-fatal when the program cache is temporarily unavailable.
  }
}
