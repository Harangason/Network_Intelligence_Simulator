"use client";

import { useState } from "react";
import {
  createOptimizationProposal,
  type IntelligenceRecommendation,
} from "@/lib/workflow-api";

type DataRecord = Record<string, unknown>;

type FlowStep = {
  label: string;
  kind: string;
};

type ResultFlow = {
  id: string;
  title: string;
  steps: FlowStep[];
};

const FIELD_LABELS: Record<string, string> = {
  approval_state: "Freigabe",
  category: "Kategorie",
  confidence: "Konfidenz",
  count: "Anzahl",
  created: "Erstellt",
  created_at: "Erstellt am",
  created_by: "Erstellt durch",
  description: "Beschreibung",
  device_type: "Gerätetyp",
  direction: "Richtung",
  domain: "Domäne",
  error_count: "Fehler",
  interface_type: "Interface-Typ",
  message: "Meldung",
  modified_at: "Geändert am",
  modified_by: "Geändert durch",
  name: "Name",
  note: "Hinweis",
  object_type: "Objekttyp",
  origin: "Herkunft",
  priority: "Priorität",
  project_id: "Projekt",
  protocol: "Protokoll",
  recommendation: "Empfehlung",
  relation_type: "Relation",
  review_state: "Review",
  route_code: "Route",
  status: "Status",
  summary: "Zusammenfassung",
  valid: "Valide",
  warning_count: "Warnungen",
};

const TITLE_KEYS = ["name", "display_name", "route_code", "code", "relation_type", "proposal_id", "id"];
const DESCRIPTION_KEYS = ["description", "summary", "message", "problem", "recommendation", "note", "text"];
const META_KEYS = ["device_type", "interface_type", "object_type", "protocol", "status", "approval_state", "review_state", "origin", "category", "severity"];
const FLOW_COLLECTION_KEYS = ["routes", "items", "candidates", "generated_routes", "paths", "relations"];
const ACTION_COLLECTION_KEY = "action_suggestions";

function isRecord(value: unknown): value is DataRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isScalar(value: unknown) {
  return value == null || ["string", "number", "boolean"].includes(typeof value);
}

function labelFor(key: string) {
  return FIELD_LABELS[key] ?? key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatScalar(value: unknown): string {
  if (value == null || value === "") return "Nicht gesetzt";
  if (typeof value === "boolean") return value ? "Ja" : "Nein";
  if (typeof value === "number") return new Intl.NumberFormat("de-DE", { maximumFractionDigits: 3 }).format(value);
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}T/.test(text)) {
    const date = new Date(text);
    if (!Number.isNaN(date.getTime())) return date.toLocaleString("de-DE");
  }
  return text;
}

function nodeLabel(value: unknown): string {
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (!isRecord(value)) return "Unbekannt";
  return String(value.name ?? value.label ?? value.node_id ?? value.object_id ?? value.id ?? "Unbekannt");
}

function nodeKind(value: unknown, fallback: string): string {
  if (!isRecord(value)) return fallback;
  return String(value.kind ?? value.object_type ?? value.device_type ?? fallback);
}

function uniqueSteps(steps: FlowStep[]) {
  return steps.filter((step, index) => step.label && step.label !== steps[index - 1]?.label);
}

function flowFromRecord(record: DataRecord, index: number): ResultFlow | null {
  const route = isRecord(record.route) ? record.route : {};
  const source = record.source;
  const destinations = Array.isArray(record.destinations) ? record.destinations : [];
  const declaredPath = Array.isArray(record.path)
    ? record.path
    : Array.isArray(route.hops)
      ? route.hops
      : [];

  let steps: FlowStep[] = [];
  if (declaredPath.length > 1) {
    steps = declaredPath.map((item, pathIndex) => ({
      label: nodeLabel(item),
      kind: pathIndex === 0 ? "Quelle" : pathIndex === declaredPath.length - 1 ? "Ziel" : nodeKind(item, "Hop"),
    }));
  } else if (source && destinations.length > 0) {
    const gateways = Array.isArray(route.gateways) ? route.gateways : [];
    steps = [
      { label: nodeLabel(source), kind: "Quelle" },
      ...gateways.map((item) => ({ label: nodeLabel(item), kind: nodeKind(item, "Gateway") })),
      ...destinations.map((item) => ({ label: nodeLabel(item), kind: "Ziel" })),
    ];
  } else if (record.source_id && record.target_id) {
    steps = [
      { label: String(record.source_id), kind: String(record.source_type ?? "Quelle") },
      { label: String(record.target_id), kind: String(record.target_type ?? "Ziel") },
    ];
  }

  steps = uniqueSteps(steps);
  if (steps.length < 2) return null;
  return {
    id: String(record.id ?? record.route_code ?? record.relation_id ?? index),
    title: String(record.route_code ?? record.name ?? record.relation_type ?? `Pfad ${index + 1}`),
    steps,
  };
}

function extractFlows(output: unknown): ResultFlow[] {
  const records: DataRecord[] = [];
  if (isRecord(output)) {
    records.push(output);
    for (const key of FLOW_COLLECTION_KEYS) {
      const collection = output[key];
      if (Array.isArray(collection)) records.push(...collection.filter(isRecord));
    }
    if (isRecord(output.proposal)) records.push(output.proposal);
  } else if (Array.isArray(output)) {
    records.push(...output.filter(isRecord));
  }
  return records
    .map(flowFromRecord)
    .filter((flow): flow is ResultFlow => flow !== null)
    .slice(0, 6);
}

function recordTitle(record: DataRecord, index: number) {
  for (const key of TITLE_KEYS) {
    if (record[key]) return formatScalar(record[key]);
  }
  return `Eintrag ${index + 1}`;
}

function recordDescription(record: DataRecord) {
  for (const key of DESCRIPTION_KEYS) {
    if (record[key]) return formatScalar(record[key]);
  }
  return "";
}

function RecordList({ items }: { items: DataRecord[] }) {
  const visible = items.slice(0, 16);
  return (
    <div className="eng-agent-result-list">
      {visible.map((record, index) => {
        const metadata = META_KEYS
          .filter((key) => record[key] != null && record[key] !== "")
          .slice(0, 4)
          .map((key) => `${labelFor(key)}: ${formatScalar(record[key])}`);
        return (
          <article key={String(record.id ?? record.proposal_id ?? record.route_code ?? index)}>
            <strong>{recordTitle(record, index)}</strong>
            {recordDescription(record) && <p>{recordDescription(record)}</p>}
            {metadata.length > 0 && <span>{metadata.join(" · ")}</span>}
          </article>
        );
      })}
      {items.length > visible.length && <p className="eng-agent-result-more">{items.length - visible.length} weitere Einträge</p>}
    </div>
  );
}

function ValueSection({ name, value, depth = 0 }: { name: string; value: unknown; depth?: number }) {
  if (name === ACTION_COLLECTION_KEY) return null;
  if (Array.isArray(value)) {
    if (value.length === 0) return <p className="eng-agent-result-empty">{labelFor(name)}: keine Einträge</p>;
    if (value.every(isScalar)) {
      return (
        <section className="eng-agent-result-section">
          <strong>{labelFor(name)}</strong>
          <div className="eng-agent-result-tags">{value.map((item, index) => <span key={`${formatScalar(item)}-${index}`}>{formatScalar(item)}</span>)}</div>
        </section>
      );
    }
    return (
      <section className="eng-agent-result-section">
        <strong>{labelFor(name)} <small>{value.length}</small></strong>
        <RecordList items={value.filter(isRecord)} />
      </section>
    );
  }
  if (!isRecord(value)) {
    return <div className="eng-agent-result-metric"><span>{labelFor(name)}</span><strong>{formatScalar(value)}</strong></div>;
  }

  const entries = Object.entries(value).filter(([key]) => key !== ACTION_COLLECTION_KEY);
  const scalarEntries = entries.filter(([, item]) => isScalar(item));
  const nestedEntries = entries.filter(([, item]) => !isScalar(item));
  return (
    <section className="eng-agent-result-section">
      {name !== "result" && <strong>{labelFor(name)}</strong>}
      {scalarEntries.length > 0 && (
        <dl className="eng-agent-result-grid">
          {scalarEntries.slice(0, 14).map(([key, item]) => (
            <div key={key}><dt>{labelFor(key)}</dt><dd>{formatScalar(item)}</dd></div>
          ))}
        </dl>
      )}
      {depth < 2 && nestedEntries.map(([key, item]) => <ValueSection depth={depth + 1} key={key} name={key} value={item} />)}
      {depth >= 2 && nestedEntries.length > 0 && (
        <p className="eng-agent-result-more">{nestedEntries.length} weitere Datenbereiche vorhanden</p>
      )}
    </section>
  );
}

function FlowView({ flows }: { flows: ResultFlow[] }) {
  return (
    <section className="eng-agent-result-section">
      <strong>Pfadübersicht</strong>
      <div className="eng-agent-flow-list">
        {flows.map((flow) => (
          <div className="eng-agent-flow" key={flow.id}>
            <span className="eng-agent-flow-title">{flow.title}</span>
            {flow.steps.map((step, index) => (
              <div className="eng-agent-flow-step" key={`${step.label}-${index}`}>
                <i aria-hidden="true" />
                <div><small>{step.kind}</small><strong>{step.label}</strong></div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

type DiagnosticAction = {
  id: string;
  label: string;
  kind: "navigate" | "create_optimization_proposal";
  href?: string;
  proposal?: IntelligenceRecommendation;
};

function actionSuggestions(output: unknown): DiagnosticAction[] {
  if (!isRecord(output) || !Array.isArray(output[ACTION_COLLECTION_KEY])) return [];
  return output[ACTION_COLLECTION_KEY].filter((item): item is DiagnosticAction => (
    isRecord(item)
    && typeof item.id === "string"
    && typeof item.label === "string"
    && (item.kind === "navigate" || item.kind === "create_optimization_proposal")
  ));
}

function ActionSuggestions({ actions }: { actions: DiagnosticAction[] }) {
  const [busyAction, setBusyAction] = useState("");
  const [message, setMessage] = useState("");
  if (!actions.length) return null;

  async function selectAction(action: DiagnosticAction) {
    setMessage("");
    if (action.kind === "navigate" && action.href) {
      window.location.assign(action.href);
      return;
    }
    if (action.kind === "create_optimization_proposal" && action.proposal) {
      setBusyAction(action.id);
      try {
        await createOptimizationProposal(action.proposal);
        setMessage("Proposal wurde angelegt und wartet auf Human Review.");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Proposal konnte nicht angelegt werden.");
      } finally {
        setBusyAction("");
      }
    }
  }

  return (
    <section className="eng-agent-result-section">
      <strong>Auswählbare Schritte</strong>
      <div className="eng-agent-action-row">
        {actions.map((action) => (
          <button
            className={action.kind === "create_optimization_proposal" ? "button primary tiny" : "button secondary tiny"}
            disabled={busyAction === action.id}
            key={action.id}
            onClick={() => void selectAction(action)}
            type="button"
          >
            {busyAction === action.id ? "läuft ..." : action.label}
          </button>
        ))}
      </div>
      {message && <p className="eng-agent-result-more">{message}</p>}
    </section>
  );
}

export function AgentToolResult({ output }: { output: unknown }) {
  const flows = extractFlows(output);
  const actions = actionSuggestions(output);
  return (
    <div className="eng-agent-tool-output-view">
      <ActionSuggestions actions={actions} />
      {flows.length > 0 && <FlowView flows={flows} />}
      <ValueSection name="result" value={output} />
    </div>
  );
}
