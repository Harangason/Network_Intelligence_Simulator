"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import type { EngineeringAgentUIMessage } from "@/lib/agent/engineering-agent";
import { readActiveProjectId } from "@/lib/user-settings";
import { AgentToolResult } from "./agent-tool-result";

const SUGGESTIONS = [
  "Welche Hardware-Knoten gibt es aktuell im automotive-Bereich?",
  "Schlage eine neue Gateway-ECU namens 'Zonal_Gateway_1' vor.",
  "Liste alle Interfaces vom Typ CAN.",
  "Prüfe die aktuelle Routing-Tabelle und zeige Konflikte.",
  "Erstelle einen Routingvorschlag für Batteriestatussignale zum Display und zur Diagnose.",
];

export function AgentChatCore({ compact = false }: { compact?: boolean }) {
  const transport = useMemo(
    () => new DefaultChatTransport({
      api: "/api/agent/chat",
      headers: () => ({ "X-Project-ID": readActiveProjectId() }),
    }),
    [],
  );
  const { messages, sendMessage, status, error, regenerate } = useChat<EngineeringAgentUIMessage>({
    transport,
  });
  const [input, setInput] = useState("");
  const threadRef = useRef<HTMLDivElement>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim() || status !== "ready") return;
    sendMessage({ text: input });
    setInput("");
  }

  const busy = status === "submitted" || status === "streaming";
  const suggestions = compact ? SUGGESTIONS.slice(0, 2) : SUGGESTIONS;

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) thread.scrollTop = thread.scrollHeight;
  }, [messages, busy]);

  useEffect(() => {
    const ask = (event: Event) => {
      const question = String((event as CustomEvent<string>).detail ?? "").trim();
      if (question && status === "ready") void sendMessage({ text: question });
    };
    window.addEventListener("engineering-agent:ask", ask);
    return () => window.removeEventListener("engineering-agent:ask", ask);
  }, [sendMessage, status]);

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <>
      <div className="eng-agent-thread" aria-live="polite" ref={threadRef}>
        {messages.length === 0 && (
          <div className="empty-result" style={{ minHeight: compact ? 90 : 140 }}>
            <span className="empty-icon">◇</span>
            <strong>Noch keine Nachricht</strong>
            <p>Frage nach Hardware, Interfaces, Signalen oder bitte um Vorschläge.</p>
          </div>
        )}

        {messages.map((message) => (
          <div className={`eng-agent-message ${message.role}`} key={message.id}>
            <span aria-hidden="true" className="eng-agent-avatar">{message.role === "user" ? "DU" : "AI"}</span>
            <div className="eng-agent-message-content">
              <span className="eng-agent-role">{message.role === "user" ? "Du" : "Engineering-Agent"}</span>
              <div className="eng-agent-bubble">
                {message.parts.map((part, index) => (
                  <MessagePart key={`${message.id}-${index}`} part={part} />
                ))}
              </div>
            </div>
          </div>
        ))}

        {busy && (
          <div className="eng-agent-message assistant">
            <span aria-hidden="true" className="eng-agent-avatar">AI</span>
            <div className="eng-agent-message-content">
              <span className="eng-agent-role">Engineering-Agent</span>
              <div className="eng-agent-bubble">
                <span className="spinner" /> denkt nach …
              </div>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="notice error">
          Der Agent konnte nicht antworten.{" "}
          <button className="button secondary tiny" onClick={() => regenerate()} type="button">
            Erneut versuchen
          </button>
        </div>
      )}

      <div className="eng-agent-suggestions">
        {suggestions.map((suggestion) => (
          <button
            className="button secondary tiny"
            disabled={busy}
            key={suggestion}
            onClick={() => sendMessage({ text: suggestion })}
            type="button"
          >
            {suggestion}
          </button>
        ))}
      </div>

      <form className="eng-agent-form" onSubmit={submit}>
        <textarea
          aria-label="Nachricht an den Engineering-Assistenten"
          disabled={busy}
          onKeyDown={handleInputKeyDown}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Frage den Engineering-Assistenten …"
          rows={1}
          value={input}
        />
        <button className="button primary" disabled={busy || !input.trim()} type="submit">
          Senden
        </button>
      </form>
    </>
  );
}

function MessagePart({ part }: { part: EngineeringAgentUIMessage["parts"][number] }) {
  if (part.type === "text") {
    return <p className="eng-agent-text">{part.text}</p>;
  }

  if (part.type === "tool-listEngineeringObjects" || part.type === "tool-listEngineeringRelations") {
    return <ToolCallCard label="Suche im Engineering-Modell" part={part} />;
  }

  if (part.type === "tool-proposeEngineeringObject") {
    return <ToolCallCard label="Vorschlag: neues Objekt" part={part} />;
  }

  if (part.type === "tool-proposeEngineeringRelation") {
    return <ToolCallCard label="Vorschlag: neue Relation" part={part} />;
  }

  if (part.type.startsWith("tool-")) {
    return <ToolCallCard
      label={`Routing · ${part.type.replace("tool-", "").replaceAll("_", " ")}`}
      part={part as { state: string; input?: unknown; output?: unknown; errorText?: string }}
    />;
  }

  return null;
}

function ToolCallCard({
  label,
  part,
}: {
  label: string;
  part: { state: string; input?: unknown; output?: unknown; errorText?: string };
}) {
  const outputSummary = part.state === "output-available" ? summarizeToolOutput(part.output) : "";
  return (
    <div className="eng-agent-tool">
      <span className="tag">{label}</span>
      {(part.state === "input-streaming" || part.state === "input-available") && (
        <span className="muted"> läuft …</span>
      )}
      {part.state === "output-available" && (
        <>
          <p className="eng-agent-tool-summary">{outputSummary}</p>
          <details className="eng-agent-tool-details">
            <summary>Ergebnis anzeigen</summary>
            <AgentToolResult output={part.output} />
          </details>
        </>
      )}
      {part.state === "output-error" && <span className="notice error">{part.errorText}</span>}
    </div>
  );
}

function summarizeToolOutput(output: unknown): string {
  if (!output || typeof output !== "object") return "Analyse abgeschlossen.";
  const value = output as Record<string, unknown>;
  if (typeof value.count === "number") {
    return `${value.count} ${value.count === 1 ? "Eintrag" : "Einträge"} gefunden.`;
  }
  if (Array.isArray(value.items)) {
    return `${value.items.length} ${value.items.length === 1 ? "Eintrag" : "Einträge"} gefunden.`;
  }
  if (typeof value.status === "string") return `Status: ${value.status}.`;
  if (typeof value.valid === "boolean") return value.valid ? "Technische Prüfung bestanden." : "Technische Prüfung mit Befunden abgeschlossen.";
  if (value.proposal || value.proposal_id) return "Ein prüfbarer Vorschlag wurde erstellt.";
  return "Analyse abgeschlossen. Details sind bei Bedarf einsehbar.";
}
