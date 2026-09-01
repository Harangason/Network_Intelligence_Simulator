import "server-only";

import { normalizeAgentProjectId } from "./request-context";
import { readProgramCache, writeProgramCache } from "../server/program-cache";

export type AgentFeedbackRating = "helpful" | "incorrect" | "failed";

export type AgentFeedbackRecord = {
  id: string;
  projectId: string;
  messageId: string;
  prompt: string;
  response: string;
  rating: AgentFeedbackRating;
  correction: string;
  error: string;
  createdAt: string;
};

const MAX_FIELD_LENGTH = 6000;
const MAX_CONTEXT_ITEMS = 4;
const CACHE_TTL_MS = 5000;
const CACHE_NAMESPACE = "agent-feedback";
const CACHE_KEY = "history";
const MAX_CACHE_BYTES = 8_000_000;
const PERSISTED_CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
let cachedRecords: AgentFeedbackRecord[] = [];
let cacheLoadedAt = 0;

function clean(value: unknown, maxLength = MAX_FIELD_LENGTH) {
  return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function isFeedbackRecord(value: unknown): value is AgentFeedbackRecord {
  if (!value || typeof value !== "object") return false;
  const record = value as Partial<AgentFeedbackRecord>;
  return typeof record.id === "string"
    && typeof record.projectId === "string"
    && typeof record.prompt === "string"
    && typeof record.response === "string"
    && ["helpful", "incorrect", "failed"].includes(String(record.rating));
}

async function readRecords() {
  if (Date.now() - cacheLoadedAt < CACHE_TTL_MS) return cachedRecords;
  const entry = await readProgramCache<unknown[]>(CACHE_NAMESPACE, CACHE_KEY);
  cachedRecords = Array.isArray(entry?.value)
    ? entry.value.filter(isFeedbackRecord).slice(-1000)
    : [];
  cacheLoadedAt = Date.now();
  return cachedRecords;
}

export async function recordAgentFeedback(input: {
  projectId: unknown;
  messageId?: unknown;
  prompt: unknown;
  response?: unknown;
  rating: AgentFeedbackRating;
  correction?: unknown;
  error?: unknown;
}) {
  await readRecords();
  const record: AgentFeedbackRecord = {
    id: crypto.randomUUID(),
    projectId: normalizeAgentProjectId(input.projectId),
    messageId: clean(input.messageId, 160),
    prompt: clean(input.prompt),
    response: clean(input.response),
    rating: input.rating,
    correction: clean(input.correction),
    error: clean(input.error, 1200),
    createdAt: new Date().toISOString(),
  };
  cachedRecords = [...cachedRecords, record].slice(-1000);
  await writeProgramCache(CACHE_NAMESPACE, CACHE_KEY, cachedRecords, MAX_CACHE_BYTES, PERSISTED_CACHE_TTL_MS);
  cacheLoadedAt = Date.now();
  return record;
}

function tokens(value: string) {
  return new Set(
    value
      .toLowerCase()
      .match(/[a-z0-9äöüß_-]{4,}/g)
      ?.filter((token) => !["diese", "dieser", "einen", "einer", "nicht", "bitte", "agent"].includes(token))
      ?? [],
  );
}

export async function agentLearningContext(projectId: unknown, request: string) {
  const normalizedProject = normalizeAgentProjectId(projectId);
  const requestTokens = tokens(request);
  if (requestTokens.size === 0) return "";
  const records = await readRecords();
  const relevant = records
    .filter((record) => record.projectId === normalizedProject && record.rating !== "failed")
    .map((record) => {
      const candidateTokens = tokens(`${record.prompt} ${record.correction}`);
      const score = [...requestTokens].filter((token) => candidateTokens.has(token)).length;
      return { record, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score || right.record.createdAt.localeCompare(left.record.createdAt))
    .slice(0, MAX_CONTEXT_ITEMS)
    .map(({ record }) => {
      if (record.rating === "helpful") {
        return `BEWÄHRT: Frage "${record.prompt.slice(0, 500)}"; hilfreiche Antwort "${record.response.slice(0, 900)}".`;
      }
      const correction = record.correction
        ? ` Nutzerkorrektur: "${record.correction.slice(0, 900)}".`
        : " Die frühere Antwort darf nicht als verlässlich übernommen werden.";
      return `KORREKTUR: Die Antwort auf "${record.prompt.slice(0, 500)}" wurde als falsch bewertet.${correction}`;
    });
  if (relevant.length === 0) return "";
  return [
    "Projektbezogenes, vom Nutzer validiertes Lernwissen:",
    ...relevant,
    "Nutze nur fachlich passende Einträge. Aktuelle deterministische Simulator-Daten haben Vorrang.",
  ].join("\n");
}
