"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { FormEvent, useState } from "react";
import type { EngineeringAgentUIMessage } from "@/lib/agent/engineering-agent";

const SUGGESTIONS = [
  "Welche Hardware-Knoten gibt es aktuell im automotive-Bereich?",
  "Schlage eine neue Gateway-ECU namens 'Zonal_Gateway_1' vor.",
  "Liste alle Interfaces vom Typ CAN.",
];

export function AgentChatCore({ compact = false }: { compact?: boolean }) {
  const { messages, sendMessage, status, error, regenerate } = useChat<EngineeringAgentUIMessage>({
    transport: new DefaultChatTransport({ api: "/api/agent/chat" }),
  });
  const [input, setInput] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim() || status !== "ready") return;
    sendMessage({ text: input });
    setInput("");
  }

  const busy = status === "submitted" || status === "streaming";
  const suggestions = compact ? SUGGESTIONS.slice(0, 2) : SUGGESTIONS;

  return (
    <>
      <div className="eng-agent-thread" aria-live="polite">
        {messages.length === 0 && (
          <div className="empty-result" style={{ minHeight: compact ? 90 : 140 }}>
            <span className="empty-icon">⌁</span>
            <strong>Noch keine Nachricht</strong>
            <p>Frage nach Hardware, Interfaces, Signalen oder bitte um Vorschläge.</p>
          </div>
        )}

        {messages.map((message) => (
          <div className={`eng-agent-message ${message.role}`} key={message.id}>
            <span className="eng-agent-role">{message.role === "user" ? "Du" : "Agent"}</span>
            <div className="eng-agent-bubble">
              {message.parts.map((part, index) => (
                <MessagePart key={`${message.id}-${index}`} part={part} />
              ))}
            </div>
          </div>
        ))}

        {busy && (
          <div className="eng-agent-message assistant">
            <span className="eng-agent-role">Agent</span>
            <div className="eng-agent-bubble">
              <span className="spinner" /> denkt nach …
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
        <input
          disabled={busy}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Frage den Engineering-Assistenten …"
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

  return null;
}

function ToolCallCard({
  label,
  part,
}: {
  label: string;
  part: { state: string; input?: unknown; output?: unknown; errorText?: string };
}) {
  return (
    <div className="eng-agent-tool">
      <span className="tag">{label}</span>
      {(part.state === "input-streaming" || part.state === "input-available") && (
        <span className="muted"> läuft …</span>
      )}
      {part.state === "output-available" && (
        <pre className="eng-agent-tool-output">{JSON.stringify(part.output, null, 2)}</pre>
      )}
      {part.state === "output-error" && <span className="notice error">{part.errorText}</span>}
    </div>
  );
}
