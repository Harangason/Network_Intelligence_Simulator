"use client";

import { FormEvent, Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  createEngineeringObject,
  createEngineeringRelation,
  approveAllValidEngineeringProposals,
  approveEngineeringProposal,
  deleteEngineeringObject,
  deleteEngineeringRelation,
  getEngineeringSchema,
  listEngineeringTools,
  listAllEngineeringObjects,
  listEngineeringProposals,
  listEngineeringRelations,
  rejectEngineeringProposal,
  RESOURCE_LABELS,
  RESOURCE_TO_OBJECT_TYPE,
  updateEngineeringObject,
  updateEngineeringProposal,
  validateEngineeringProposal,
} from "@/lib/engineering-api";
import { ENGINEERING_MODEL_CHANGED_EVENT } from "@/lib/engineering-events";
import {
  engineeringDeviceTypeLabel,
  engineeringObjectTypeClass,
  engineeringObjectTypeLabel,
  engineeringResourceType,
  isMergedHardwareAlias,
} from "@/lib/engineering-object-style";
import type {
  EngineeringObject,
  EngineeringProposal,
  EngineeringRelation,
  EngineeringResource,
  EngineeringSchema,
  EngineeringToolDefinition,
  EngSignal,
} from "@/lib/types";
import { getWorkflow, setWorkflowContext } from "@/lib/workflow-api";
import {
  ENGINEERING_AGENT_WIZARD_OPEN_EVENT,
  takePendingEngineeringAgentWizard,
} from "@/lib/agent-task-events";
import { readActiveProjectId } from "@/lib/user-settings";
import { EngineeringAgentWizard } from "@/components/agent-chat-core";
import { StructureTreeWorkbench } from "@/components/structure-tree-workbench";

const RESOURCES: EngineeringResource[] = [
  "hardware-nodes",
  "functions",
  "interfaces",
  "messages",
  "signals",
];
const ENGINEERING_PAGE_SIZE = 50;

const HARDWARE_PRESETS = [
  { label: "ECU", deviceType: "ECU" },
  { label: "Gateway", deviceType: "Gateway" },
  { label: "Sensor", deviceType: "SensorController" },
  { label: "Aktor", deviceType: "ActuatorController" },
] as const;

const REQUIREMENT_FIELDS = [
  { key: "cycle_time_ms", label: "Zyklus", unit: "ms" },
  { key: "deadline_ms", label: "Deadline", unit: "ms" },
  { key: "timeout_ms", label: "Timeout", unit: "ms" },
  { key: "maximum_latency_ms", label: "Max. Latenz", unit: "ms" },
  { key: "maximum_jitter_ms", label: "Max. Jitter", unit: "ms" },
  { key: "data_freshness_limit", label: "Freshness", unit: "ms" },
  { key: "event_rate", label: "Event Rate", unit: "Hz" },
  { key: "burst_rate", label: "Burst Rate", unit: "Hz" },
] as const;

function requirementPayload(form: FormData, prefix: string) {
  const values: Record<string, unknown> = {};
  for (const field of REQUIREMENT_FIELDS) {
    const raw = form.get(`${prefix}${field.key}`);
    values[field.key] = raw === null || raw === "" ? null : Number(raw);
  }
  values.priority = form.get(`${prefix}priority`) || null;
  values.reliability_requirement = form.get(`${prefix}reliability_requirement`) || null;
  return values;
}

const RESOURCE_HIERARCHY: Partial<
  Record<
    EngineeringResource,
    {
      parentResource: EngineeringResource;
      parentLabel: string;
      relationType: string;
    }
  >
> = {
  functions: {
    parentResource: "hardware-nodes",
    parentLabel: "Hardware-Knoten",
    relationType: "HAS_FUNCTION",
  },
  interfaces: {
    parentResource: "functions",
    parentLabel: "Funktion",
    relationType: "HAS_INTERFACE",
  },
  messages: {
    parentResource: "interfaces",
    parentLabel: "Interface",
    relationType: "HAS_MESSAGE",
  },
  signals: {
    parentResource: "messages",
    parentLabel: "Nachricht",
    relationType: "CONTAINS_SIGNAL",
  },
};

const RESOURCE_REFERENCES: Record<EngineeringResource, EngineeringResource[]> = {
  "hardware-nodes": [],
  functions: ["hardware-nodes"],
  interfaces: ["functions", "hardware-nodes"],
  messages: ["interfaces"],
  signals: ["messages"],
};

const RESOURCE_TABLE_HEADERS: Record<EngineeringResource, string[]> = {
  "hardware-nodes": ["Name", "Gerätetyp", "Domäne"],
  functions: ["Name", "Hardware-Knoten", "Domäne", "Beschreibung"],
  interfaces: ["Name", "Funktion", "Interface-Typ", "Hardware"],
  messages: ["Name", "Interface", "Message-ID", "Richtung", "Zyklus", "DLC"],
  signals: ["Name", "Nachricht", "Start-Bit", "Länge", "Byte-Reihenfolge", "Datentyp", "Einheit"],
};

function referenceName(names: Record<string, string>, id: string | null) {
  return id ? names[id] ?? "Unbekannt" : "—";
}

function resourceTableValues(
  resource: EngineeringResource,
  item: EngineeringObject,
  names: Record<string, string>,
): string[] {
  switch (resource) {
    case "hardware-nodes":
      return [item.name, "device_type" in item ? engineeringDeviceTypeLabel(item.device_type) : "—", item.domain ?? "—"];
    case "functions":
      return [
        item.name,
        "hardware_node_id" in item ? referenceName(names, item.hardware_node_id) : "—",
        item.domain ?? "—",
        item.description ?? "—",
      ];
    case "interfaces":
      return [
        item.name,
        "function_id" in item ? referenceName(names, item.function_id) : "—",
        "interface_type" in item ? item.interface_type : "—",
        "hardware_node_id" in item ? referenceName(names, item.hardware_node_id) : "—",
      ];
    case "messages":
      return [
        item.name,
        "interface_id" in item ? referenceName(names, item.interface_id) : "—",
        "message_id_hex" in item ? item.message_id_hex ?? "—" : "—",
        "direction" in item ? item.direction ?? "—" : "—",
        "cycle_ms" in item && item.cycle_ms !== null ? `${item.cycle_ms} ms` : "—",
        "dlc" in item && item.dlc !== null ? String(item.dlc) : "—",
      ];
    case "signals":
      return [
        item.name,
        "message_id" in item ? referenceName(names, item.message_id) : "—",
        "start_bit" in item && item.start_bit !== null ? String(item.start_bit) : "—",
        "length_bits" in item && item.length_bits !== null ? `${item.length_bits} Bit` : "—",
        "byte_order" in item ? item.byte_order ?? "—" : "—",
        "data_type" in item ? item.data_type ?? "—" : "—",
        "unit" in item ? item.unit ?? "—" : "—",
      ];
  }
}

const RELATION_TYPES = [
  "HAS_FUNCTION",
  "HAS_CAPABILITY",
  "HAS_PORT",
  "HAS_INTERFACE",
  "CONNECTED_TO",
  "COMMUNICATES_WITH",
  "PROVIDES",
  "CONSUMES",
  "SENDS",
  "RECEIVES",
  "HAS_MESSAGE",
  "CONTAINS_SIGNAL",
  "RUNS_ON",
  "MAPPED_TO",
  "USES_PROTOCOL",
  "CONNECTED_VIA",
  "DERIVED_FROM",
  "DEFINED_BY",
  "IMPORTED_FROM",
  "SUPPORTED_BY",
  "VALIDATED_BY",
  "CONFLICTS_WITH",
  "DEPENDS_ON",
  "RELATED_TO",
  "SIMULATED_IN",
  "FAILED_IN",
  "OBSERVED_IN",
  "REPLACES",
  "VERSION_OF",
];

const OBJECT_TYPE_TO_RESOURCE: Record<string, EngineeringResource> = {
  HardwareNode: "hardware-nodes",
  Function: "functions",
  Interface: "interfaces",
  Message: "messages",
  Signal: "signals",
};

const WIZARD_STEPS = ["Identität", "Zuordnung", "Details", "Prüfen"] as const;

const REQUIRED_PROPOSAL_FIELDS: Record<string, string[]> = {
  HardwareNode: ["name"],
  Function: ["name", "hardware_node_id"],
  Interface: ["name", "function_id", "interface_type"],
  Message: ["name", "interface_id"],
  Signal: ["name", "message_id"],
  Relation: ["relation_type", "source_type", "source_id", "target_type", "target_id"],
};

const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  domain: "Domäne",
  description: "Beschreibung",
  device_type: "Gerätetyp",
  hardware_node_id: "Hardware-Knoten",
  function_id: "Funktion",
  interface_id: "Interface",
  message_id: "Message",
  interface_type: "Interface-Typ",
  message_id_hex: "Message-ID",
  direction: "Richtung",
  cycle_ms: "Zyklus",
  dlc: "DLC",
  display_name: "Anzeigename",
  start_bit: "Start-Bit",
  length_bits: "Länge",
  byte_order: "Byte Order",
  data_type: "Datentyp",
  factor: "Faktor",
  offset_value: "Offset",
  unit: "Einheit",
  min_value: "Min",
  max_value: "Max",
  relation_type: "Relation",
  source_type: "Quelle-Typ",
  source_id: "Quelle",
  target_type: "Ziel-Typ",
  target_id: "Ziel",
};

const SIGNAL_BYTE_ORDERS = ["little_endian", "big_endian"];

function proposalObjectType(proposal: EngineeringProposal, item: Record<string, unknown>) {
  const direct = String(item.object_type ?? "");
  if (direct in OBJECT_TYPE_TO_RESOURCE || direct === "Relation") return direct;
  const resource = String(item.resource ?? "");
  if (resource in RESOURCE_TO_OBJECT_TYPE) return RESOURCE_TO_OBJECT_TYPE[resource as EngineeringResource];
  const target = (proposal as EngineeringProposal & { target_object?: Record<string, unknown> }).target_object;
  const targetResource = String(target?.resource ?? "");
  if (targetResource in RESOURCE_TO_OBJECT_TYPE) return RESOURCE_TO_OBJECT_TYPE[targetResource as EngineeringResource];
  if (proposal.proposal_type === "RELATION") return "Relation";
  return proposal.proposal_type || "Object";
}

function fieldValue(value: unknown) {
  return value === null || value === undefined ? "" : String(value);
}

function optionalNumberValue(value: string) {
  return value.trim() === "" ? null : Number(value);
}

function words(value: unknown) {
  return fieldValue(value).toLowerCase().split(/[^a-z0-9]+/).filter((word) => word.length > 2);
}

function shortId(id: string) {
  return id ? id.slice(0, 8) : "";
}

function objectById(references: Partial<Record<EngineeringResource, EngineeringObject[]>>, id: unknown) {
  const stringId = fieldValue(id);
  if (!stringId) return undefined;
  return Object.values(references).flatMap((items) => items ?? []).find((item) => item.id === stringId);
}

function interfaceTechnology(item: EngineeringObject | undefined) {
  if (!item || !("interface_type" in item)) return "";
  const raw = String(item.configuration?.bus ?? item.interface_type ?? "").toLowerCase();
  if (raw.includes("can_fd") || raw.includes("can fd")) return "CAN FD";
  if (raw.includes("ethernet")) return "Ethernet";
  if (raw.includes("lin")) return "LIN";
  if (raw.includes("flexray")) return "FlexRay";
  return String(item.interface_type ?? "");
}

function missingProposalFields(type: string, item: Record<string, unknown>) {
  return (REQUIRED_PROPOSAL_FIELDS[type] ?? ["name"]).filter((field) => {
    const value = item[field];
    return value === null || value === undefined || String(value).trim() === "";
  });
}

function optionLabel(item: EngineeringObject, references: Partial<Record<EngineeringResource, EngineeringObject[]>> = {}) {
  const domain = item.domain ? ` · ${item.domain}` : "";
  if ("interface_type" in item) {
    const fn = objectById(references, item.function_id);
    const hw = objectById(references, item.hardware_node_id);
    return `${item.name} · ${item.interface_type}${fn ? ` · ${fn.name}` : ""}${hw ? ` · ${hw.name}` : ""} · ${shortId(item.id)}`;
  }
  if ("interface_id" in item) {
    const iface = objectById(references, item.interface_id);
    return `${item.name}${iface ? ` · ${iface.name}` : ""}${domain} · ${shortId(item.id)}`;
  }
  if ("message_id" in item) {
    const message = objectById(references, item.message_id);
    return `${item.display_name || item.name}${message ? ` · ${message.name}` : ""}${domain} · ${shortId(item.id)}`;
  }
  if ("hardware_node_id" in item) {
    const hw = objectById(references, item.hardware_node_id);
    return `${item.name}${hw ? ` · ${hw.name}` : ""}${domain} · ${shortId(item.id)}`;
  }
  return `${item.name}${domain} · ${shortId(item.id)}`;
}

function referenceDisplay(references: Partial<Record<EngineeringResource, EngineeringObject[]>>, field: string, value: unknown) {
  const id = fieldValue(value);
  if (!id) return "Noch nicht gesetzt";
  const allReferences = Object.values(references).flatMap((items) => items ?? []);
  const item = allReferences.find((candidate) => candidate.id === id);
  return item ? optionLabel(item, references) : id;
}

type WizardSuggestion = {
  id: string;
  label: string;
  confidence: number;
  reason: string;
};

function proposalContextText(proposal: EngineeringProposal, draft: Record<string, unknown>) {
  return [proposal.prompt, draft.name, draft.description, draft.domain].map(fieldValue).join(" ");
}

function scoreReferenceOption(
  proposal: EngineeringProposal,
  draft: Record<string, unknown>,
  item: EngineeringObject,
  references: Partial<Record<EngineeringResource, EngineeringObject[]>>,
) {
  const context = new Set(words(proposalContextText(proposal, draft)));
  const candidateWords = [
    ...words(item.name),
    ...words(item.domain),
    ...words("display_name" in item ? item.display_name : ""),
    ...words("interface_type" in item ? item.interface_type : ""),
  ];
  let score = 34;
  for (const word of candidateWords) {
    if (context.has(word)) score += 16;
  }
  if (draft.domain && item.domain === draft.domain) score += 12;
  if ("interface_id" in item) {
    const iface = objectById(references, item.interface_id);
    if (iface && "interface_type" in iface && fieldValue(iface.interface_type).toLowerCase().includes("can")) score += 6;
  }
  if ("interface_type" in item && fieldValue(item.interface_type).toLowerCase().includes("can")) score += 6;
  return Math.max(12, Math.min(96, score));
}

function referenceSuggestions(
  proposal: EngineeringProposal,
  draft: Record<string, unknown>,
  options: EngineeringObject[],
  references: Partial<Record<EngineeringResource, EngineeringObject[]>>,
) {
  return options
    .map((item) => ({
      id: item.id,
      label: optionLabel(item, references),
      confidence: scoreReferenceOption(proposal, draft, item, references),
      reason: "Namensnähe, Domäne und Bus-Kontext",
    }))
    .sort((left, right) => right.confidence - left.confidence)
    .slice(0, 3);
}

function busDefaultsFor(technology: string, objectType: string) {
  const tech = technology.toLowerCase();
  if (objectType === "Message") {
    if (tech.includes("ethernet")) return { direction: "tx", cycle_ms: 10, dlc: 64 };
    if (tech.includes("lin")) return { direction: "tx", cycle_ms: 20, dlc: 8 };
    if (tech.includes("flex")) return { direction: "tx", cycle_ms: 5, dlc: 32 };
    return { direction: "tx", cycle_ms: 10, dlc: 64 };
  }
  if (objectType === "Signal") {
    if (tech.includes("ethernet")) return { start_bit: 0, length_bits: 32, byte_order: "big_endian", data_type: "float", factor: 1, offset_value: 0 };
    return { start_bit: 0, length_bits: 16, byte_order: "little_endian", data_type: "unsigned", factor: 1, offset_value: 0 };
  }
  return {};
}

export function EngineeringWorkbench() {
  const [resource, setResource] = useState<EngineeringResource>("hardware-nodes");
  const [schema, setSchema] = useState<EngineeringSchema | null>(null);
  const [items, setItems] = useState<EngineeringObject[]>([]);
  const [referenceNames, setReferenceNames] = useState<Record<string, string>>({});
  const [relations, setRelations] = useState<EngineeringRelation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [hardwarePreset, setHardwarePreset] = useState<string | null>(null);
  const [showAgentWizard, setShowAgentWizard] = useState(false);
  const [showStructureTree, setShowStructureTree] = useState(false);
  const [activeInterfaceIds, setActiveInterfaceIds] = useState<Set<string> | null>(null);
  const [showUnusedInterfaces, setShowUnusedInterfaces] = useState(false);
  const [columnFilters, setColumnFilters] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const [toolRegistry, setToolRegistry] = useState<EngineeringToolDefinition[]>([]);
  const [toolRegistryError, setToolRegistryError] = useState("");

  useEffect(() => {
    const openRequestedWizard = () => {
      if (takePendingEngineeringAgentWizard(readActiveProjectId())) setShowAgentWizard(true);
    };
    openRequestedWizard();
    window.addEventListener(ENGINEERING_AGENT_WIZARD_OPEN_EVENT, openRequestedWizard);
    return () => window.removeEventListener(ENGINEERING_AGENT_WIZARD_OPEN_EVENT, openRequestedWizard);
  }, []);

  useEffect(() => {
    getEngineeringSchema()
      .then(setSchema)
      .catch((err) => setError(err instanceof Error ? err.message : "Schema konnte nicht geladen werden."));
  }, []);

  useEffect(() => {
    let cancelled = false;
    listEngineeringTools()
      .then((result) => {
        if (cancelled) return;
        setToolRegistry(result.items);
        setToolRegistryError("");
      })
      .catch((err) => {
        if (!cancelled) setToolRegistryError(err instanceof Error ? err.message : "Tool Registry nicht erreichbar.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    Promise.all([
      listAllEngineeringObjects(resource),
      Promise.all(RESOURCE_REFERENCES[resource].map((reference) => listAllEngineeringObjects(reference))),
    ])
      .then(([nextItems, referenceGroups]) => {
        setItems(nextItems);
        setReferenceNames(
          Object.fromEntries(referenceGroups.flat().map((reference) => [reference.id, reference.name])),
        );
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Backend nicht erreichbar."))
      .finally(() => setLoading(false));
  }, [resource, refreshKey]);

  useEffect(() => {
    setSelectedId(null);
    setColumnFilters([]);
    setPage(1);
  }, [resource]);

  useEffect(() => {
    if (resource !== "interfaces") {
      setActiveInterfaceIds(null);
      return;
    }
    let cancelled = false;
    getWorkflow()
      .then((state) => {
        if (cancelled) return;
        const ids = new Set<string>();
        for (const node of state.topology.nodes ?? []) {
          for (const port of node.ports ?? []) {
            if (port.engineeringId) ids.add(port.engineeringId);
          }
        }
        setActiveInterfaceIds(ids);
      })
      .catch(() => {
        if (!cancelled) setActiveInterfaceIds(null);
      });
    return () => {
      cancelled = true;
    };
  }, [resource, refreshKey]);

  useEffect(() => {
    if (!showAgentWizard) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowAgentWizard(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [showAgentWizard]);

  useEffect(() => {
    const handleModelChanged = (event: Event) => {
      const detail = (event as CustomEvent<{ resource?: string; id?: string }>).detail;
      setRefreshKey((key) => key + 1);
      if (detail?.resource === resource && detail.id) setSelectedId(detail.id);
    };
    window.addEventListener(ENGINEERING_MODEL_CHANGED_EVENT, handleModelChanged);
    return () => window.removeEventListener(ENGINEERING_MODEL_CHANGED_EVENT, handleModelChanged);
  }, [resource]);

  const unusedNetworkInterfaces = useMemo(
    () => resource === "interfaces" && activeInterfaceIds
      ? items.filter((item) => (
          item.provenance.origin === "network-editor"
          && !activeInterfaceIds.has(item.id)
        ))
      : [],
    [activeInterfaceIds, items, resource],
  );
  const baseVisibleItems = useMemo(() => {
    const activeItems = resource === "hardware-nodes"
      ? items.filter((item) => !isMergedHardwareAlias(item))
      : items;
    return resource === "interfaces" && !showUnusedInterfaces && unusedNetworkInterfaces.length
      ? activeItems.filter((item) => !unusedNetworkInterfaces.some((unused) => unused.id === item.id))
      : activeItems;
  }, [items, resource, showUnusedInterfaces, unusedNetworkInterfaces]);
  const visibleItems = useMemo(
    () => baseVisibleItems.filter((item) => {
      const values = resourceTableValues(resource, item, referenceNames);
      return columnFilters.every((filter, index) => {
        const query = (filter ?? "").trim().toLocaleLowerCase("de-DE");
        return !query || (values[index] ?? "").toLocaleLowerCase("de-DE").includes(query);
      });
    }),
    [baseVisibleItems, columnFilters, referenceNames, resource],
  );
  const totalPages = Math.max(1, Math.ceil(visibleItems.length / ENGINEERING_PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const paginatedItems = useMemo(
    () => visibleItems.slice(
      (currentPage - 1) * ENGINEERING_PAGE_SIZE,
      currentPage * ENGINEERING_PAGE_SIZE,
    ),
    [currentPage, visibleItems],
  );
  const selected = useMemo(
    () => paginatedItems.find((item) => item.id === selectedId) ?? null,
    [paginatedItems, selectedId],
  );

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  useEffect(() => {
    void setWorkflowContext({
      selected_object: selected ? { id: selected.id, type: RESOURCE_TO_OBJECT_TYPE[resource], name: selected.name } : null,
      selected_signal: resource === "signals" && selected ? selected.id : null,
    }).catch(() => undefined);
  }, [resource, selected]);

  useEffect(() => {
    if (!selected) {
      setRelations([]);
      return;
    }
    listEngineeringRelations({ object_type: RESOURCE_TO_OBJECT_TYPE[resource], object_id: selected.id })
      .then(setRelations)
      .catch(() => setRelations([]));
  }, [selected, resource]);

  function refresh() {
    setRefreshKey((key) => key + 1);
  }

  if (error) {
    return (
      <>
        <div className="panel error-card">
          <p className="eyebrow">Engineering-API nicht erreichbar</p>
          <h2>{error}</h2>
          <p className="muted">Prüfe Backend und Datenbankverbindung oder versuche es erneut.</p>
          <div className="form-actions error-card-actions">
            <button className="button secondary" onClick={refresh} type="button">
              Erneut prüfen
            </button>
            <button className="button primary" onClick={() => setShowAgentWizard(true)} type="button">
              Projekt-Wizard öffnen
            </button>
          </div>
        </div>
        {showAgentWizard && <EngineeringAgentWizardDialog onClose={() => setShowAgentWizard(false)} />}
      </>
    );
  }

  return (
    <>
    <div className="workspace-grid engineering-workspace">
      <div className="panel config-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Kanonisches Modell</p>
            <h2 className={showStructureTree ? undefined : `eng-object-label ${engineeringObjectTypeClass(engineeringResourceType(resource))}`}>{showStructureTree ? "Structure Tree" : RESOURCE_LABELS[resource]}</h2>
          </div>
          <div className="panel-heading-actions">
            <button className="button secondary" onClick={() => setShowAgentWizard(true)} type="button">
              Agent-Auftrag
            </button>
          </div>
        </div>

        <div className="eng-resource-tabs eng-resource-flow" role="tablist" aria-label="Objekthierarchie">
          {RESOURCES.map((res, index) => (
            <Fragment key={res}>
              <button
                aria-selected={!showStructureTree && resource === res}
                className={`eng-object-accent ${engineeringObjectTypeClass(engineeringResourceType(res))} ${!showStructureTree && resource === res ? "active" : ""}`}
                onClick={() => {
                  setShowStructureTree(false);
                  setResource(res);
                  setShowCreate(false);
                  setHardwarePreset(null);
                }}
                role="tab"
                type="button"
              >
                {RESOURCE_LABELS[res]}
              </button>
              {index < RESOURCES.length - 1 && (
                <span aria-hidden="true" className="eng-resource-arrow">→</span>
              )}
            </Fragment>
          ))}
          <span aria-hidden="true" className="eng-resource-tree-divider" />
          <button
            aria-selected={showStructureTree}
            className={`eng-structure-tree-tab ${showStructureTree ? "active" : ""}`}
            onClick={() => {
              setShowStructureTree(true);
              setShowCreate(false);
              setHardwarePreset(null);
              setSelectedId(null);
            }}
            role="tab"
            type="button"
          >
            Structure Tree
          </button>
        </div>

        {showStructureTree ? (
          <StructureTreeWorkbench onChanged={refresh} />
        ) : <>
        <div className={`eng-resource-wizard-bar eng-object-surface ${engineeringObjectTypeClass(engineeringResourceType(resource))}`}>
          <div>
            <p className="eyebrow">Objekt-Wizard</p>
            <strong>{RESOURCE_LABELS[resource]} geführt anlegen</strong>
            <span>Identität → Zuordnung → technische Details → Prüfung</span>
          </div>
          <button
            className="button primary"
            onClick={() => {
              setHardwarePreset(null);
              setShowCreate(true);
            }}
            type="button"
          >
            Wizard starten
          </button>
        </div>

        {resource === "interfaces" && unusedNetworkInterfaces.length > 0 && (
          <label className="eng-unused-interface-toggle">
            <input
              checked={showUnusedInterfaces}
              onChange={(event) => {
                setShowUnusedInterfaces(event.target.checked);
                setSelectedId(null);
                setPage(1);
              }}
              type="checkbox"
            />
            <span>Verwaiste Netzwerk-Interfaces anzeigen</span>
            <small>{unusedNetworkInterfaces.length} nicht mehr in der Topologie verwendet</small>
          </label>
        )}

        {resource === "hardware-nodes" && (
          <div
            aria-label="Hardware-Typ auswählen"
            className="net-palette eng-hardware-quick-add"
            role="group"
          >
            {HARDWARE_PRESETS.map((preset) => (
              <button
                className={`net-add ${hardwarePreset === preset.deviceType && showCreate ? "active" : ""}`}
                key={preset.deviceType}
                onClick={() => {
                  setHardwarePreset(preset.deviceType);
                  setShowCreate(true);
                }}
                type="button"
              >
                + {preset.label}
              </button>
            ))}
          </div>
        )}

        {showCreate && (
          <CreateForm
            hardwarePreset={hardwarePreset}
            key={`${resource}:${hardwarePreset ?? "custom"}`}
            onClose={() => {
              setShowCreate(false);
              setHardwarePreset(null);
            }}
            resource={resource}
            schema={schema}
            onCreated={() => {
              setShowCreate(false);
              setHardwarePreset(null);
              refresh();
            }}
          />
        )}

        {loading ? (
          <div className="loading-panel">Lädt …</div>
        ) : baseVisibleItems.length === 0 ? (
          <div className="empty-result">
            <span className="empty-icon">◇</span>
            <strong>Keine Objekte vorhanden</strong>
            <p>Lege das erste {RESOURCE_LABELS[resource]}-Objekt an.</p>
          </div>
        ) : (
          <div className="eng-table-scroll">
            <table className={`eng-table ${resource}`}>
              <thead>
                <tr>
                  {RESOURCE_TABLE_HEADERS[resource].map((header) => <th key={header}>{header}</th>)}
                </tr>
                <tr className="eng-table-filter-row">
                  {RESOURCE_TABLE_HEADERS[resource].map((header, index) => (
                    <th key={`${header}:filter`}>
                      <input
                        aria-label={`${header} filtern`}
                        onChange={(event) => {
                          const value = event.target.value;
                          setColumnFilters((current) => {
                            const next = [...current];
                            next[index] = value;
                            return next;
                          });
                          setSelectedId(null);
                          setPage(1);
                        }}
                        placeholder="Filtern"
                        type="search"
                        value={columnFilters[index] ?? ""}
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleItems.length === 0 && (
                  <tr className="eng-table-filter-empty">
                    <td colSpan={RESOURCE_TABLE_HEADERS[resource].length}>
                      Keine Einträge entsprechen den Spaltenfiltern.
                    </td>
                  </tr>
                )}
                {paginatedItems.map((item) => (
                  <Fragment key={item.id}>
                    <tr
                      className={`eng-object-surface ${engineeringObjectTypeClass(item.object_type)} ${item.id === selectedId ? "selected" : ""}`}
                      onClick={() => setSelectedId(item.id)}
                    >
                      {resourceTableValues(resource, item, referenceNames).map((value, index) => (
                        <td className={index === 0 ? undefined : "muted"} key={`${item.id}:${index}`}>
                          {value}
                        </td>
                      ))}
                    </tr>
                    {item.id === selectedId && (
                      <tr className="eng-detail-row">
                        <td colSpan={RESOURCE_TABLE_HEADERS[resource].length}>
                          <DetailPanel
                            item={item}
                            referenceNames={referenceNames}
                            resource={resource}
                            relations={relations}
                            schema={schema}
                            onChanged={refresh}
                            onDeleted={() => {
                              setSelectedId(null);
                              refresh();
                            }}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            {visibleItems.length > 0 && (
              <footer className="eng-table-pagination">
                <span>
                  {(currentPage - 1) * ENGINEERING_PAGE_SIZE + 1}-{Math.min(currentPage * ENGINEERING_PAGE_SIZE, visibleItems.length)} von {visibleItems.length} Einträgen · {ENGINEERING_PAGE_SIZE} pro Seite
                </span>
                <div>
                  <button
                    className="button secondary tiny"
                    disabled={currentPage === 1}
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    type="button"
                  >
                    Zurück
                  </button>
                  <span>Seite {currentPage} von {totalPages}</span>
                  <button
                    className="button secondary tiny"
                    disabled={currentPage === totalPages}
                    onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                    type="button"
                  >
                    Weiter
                  </button>
                </div>
              </footer>
            )}
          </div>
        )}
        </>}
      </div>
      <ToolRegistryPanel error={toolRegistryError} tools={toolRegistry} />
    </div>
    {showAgentWizard && <EngineeringAgentWizardDialog onClose={() => setShowAgentWizard(false)} />}
    </>
  );
}

function ToolRegistryPanel({ tools, error }: { tools: EngineeringToolDefinition[]; error: string }) {
  const categories = Array.from(new Set(tools.map((tool) => tool.category))).sort((left, right) => left.localeCompare(right, "de"));
  const approvalCount = tools.filter((tool) => tool.requires_approval).length;
  const formatCount = new Set(tools.flatMap((tool) => tool.supported_formats)).size;
  const featuredTools = [...tools]
    .sort((left, right) => Number(right.requires_approval) - Number(left.requires_approval) || left.category.localeCompare(right.category, "de"))
    .slice(0, 8);

  return (
    <section className="panel tool-registry-panel" aria-label="Engineering Tool Registry">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Tool Registry</p>
          <h2>Systemwerkzeuge</h2>
        </div>
        <div className="tool-registry-summary" aria-label="Tool-Registry-Zusammenfassung">
          <span><b>{tools.length}</b> Tools</span>
          <span><b>{approvalCount}</b> Review-Gates</span>
          <span><b>{formatCount}</b> Formate</span>
        </div>
      </div>
      {error ? (
        <p className="muted">{error}</p>
      ) : (
        <>
          <div className="tool-registry-categories" aria-label="Tool-Kategorien">
            {categories.map((category) => (
              <span key={category}>{category}</span>
            ))}
          </div>
          <div className="tool-registry-list">
            {featuredTools.map((tool) => (
              <details key={tool.id}>
                <summary>
                  <span>
                    <strong>{tool.name}</strong>
                    <small>{tool.id} · {tool.workflow_step}</small>
                  </span>
                  <i>{tool.requires_approval ? "Freigabe" : tool.status}</i>
                </summary>
                <p>{tool.description}</p>
                <dl>
                  <div><dt>KI-Nutzung</dt><dd>{tool.ai_usage}</dd></div>
                  <div><dt>Fähigkeiten</dt><dd>{tool.capabilities.join(", ")}</dd></div>
                  {tool.supported_formats.length > 0 && (
                    <div><dt>Formate</dt><dd>{tool.supported_formats.slice(0, 12).join(", ")}{tool.supported_formats.length > 12 ? " ..." : ""}</dd></div>
                  )}
                </dl>
              </details>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function EngineeringAgentWizardDialog({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="engineering-agent-wizard-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
      role="presentation"
    >
      <section aria-labelledby="engineering-agent-wizard-title" aria-modal="true" className="engineering-agent-wizard-dialog" role="dialog">
        <header className="engineering-agent-wizard-header">
          <div>
            <p className="eyebrow">Geführte Anlage</p>
            <h2 id="engineering-agent-wizard-title">Engineering-Auftrag erstellen</h2>
            <span>Technische Vorgaben festlegen und anschließend vom Agenten ausführen lassen.</span>
          </div>
          <button aria-label="Wizard schließen" className="eng-dialog-close" onClick={onClose} type="button">×</button>
        </header>
        <EngineeringAgentWizard
          busy={false}
          mode="full"
          onFinish={onClose}
          title="Technische Vorgaben"
        />
      </section>
    </div>
  );
}

function ProposalReviewPanel({
  item,
  resource,
  onChanged,
}: {
  item: EngineeringObject;
  resource: EngineeringResource;
  onChanged: () => void;
}) {
  const [proposals, setProposals] = useState<EngineeringProposal[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [wizard, setWizard] = useState<{ proposalId: string; index: number } | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh() {
    try {
      setProposals(await listEngineeringProposals());
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Vorschläge konnten nicht geladen werden.");
    }
  }

  useEffect(() => {
    void refresh();
  }, [item.id]);

  async function act(key: string, action: () => Promise<unknown>, message: string) {
    setBusy(key);
    setNotice("");
    try {
      await action();
      setNotice(message);
      await refresh();
      onChanged();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Aktion fehlgeschlagen.");
    } finally {
      setBusy("");
    }
  }

  async function save(event: FormEvent<HTMLFormElement>, proposal: EngineeringProposal) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const updated = proposal.proposed_objects.map((item, index) => ({
      ...item,
      name: form.get(`name-${index}`) || item.name,
      description: form.get(`description-${index}`) || null,
      domain: form.get(`domain-${index}`) || null,
    }));
    await act(`save:${proposal.proposal_id}`, () => updateEngineeringProposal(proposal.proposal_id, updated), "Vorschlag gespeichert. Erneute Validierung erforderlich.");
    setEditingId(null);
  }

  async function saveWizard(proposal: EngineeringProposal, index: number, nextItem: Record<string, unknown>) {
    const updated = proposal.proposed_objects.map((item, itemIndex) => (itemIndex === index ? nextItem : item));
    await act(
      `wizard:${proposal.proposal_id}:${index}`,
      async () => {
        await updateEngineeringProposal(proposal.proposal_id, updated);
        await validateEngineeringProposal(proposal.proposal_id);
      },
      "Wizard gespeichert und Vorschlag neu validiert.",
    );
    setWizard(null);
  }

  const relevant = proposals.filter((proposal) => {
    const target = (proposal as EngineeringProposal & { target_object?: Record<string, unknown> }).target_object;
    const targetResource = String(target?.resource ?? "");
    return proposal.proposed_objects.some((candidate) => {
      const canonicalId = String(candidate.canonical_id ?? "");
      const sameObject = canonicalId === item.id
        || (targetResource === resource && String(candidate.name ?? "") === item.name);
      const relatedObject = proposal.proposal_type === "RELATION"
        && (String(candidate.source_id ?? "") === item.id || String(candidate.target_id ?? "") === item.id);
      return sameObject || relatedObject;
    });
  });
  const open = relevant.filter((proposal) => !["APPROVED", "REJECTED", "SUPERSEDED"].includes(proposal.status));
  const wizardProposal = wizard ? relevant.find((proposal) => proposal.proposal_id === wizard.proposalId) : undefined;

  return (
    <details className="eng-detail-section eng-proposal-review embedded">
      <summary>
        <span>KI-Audit</span>
        <strong>{relevant.length} {relevant.length === 1 ? "Vorgang" : "Vorgänge"}</strong>
      </summary>
      <div className="eng-detail-section-body">
      <div className="panel-heading">
        <div><p className="eyebrow">KI-Audit</p><h2>Vorschläge und Werkzeuge</h2></div>
        <div className="panel-heading-actions">
          <span className="status-badge">{open.length} offen</span>
          <button className="button secondary tiny" disabled={!open.length || Boolean(busy)} onClick={() => void act("approve-all", approveAllValidEngineeringProposals, "Alle validen Vorschlaege freigegeben.")} type="button">Alle validen freigeben</button>
        </div>
      </div>
      {notice && <div className="notice">{notice}</div>}
      {!relevant.length ? (
        <div className="eng-proposal-empty">Für dieses Objekt liegt noch keine KI-Auditspur vor.</div>
      ) : (
        <div className="eng-proposal-list">
          {relevant.map((proposal) => {
            const editing = editingId === proposal.proposal_id;
            return (
              <form className="eng-proposal-row" key={proposal.proposal_id} onSubmit={(event) => void save(event, proposal)}>
                <header>
                  <div><span>{proposal.proposal_type}</span><strong>{proposal.prompt}</strong></div>
                  <span className={`status-badge ${proposal.status.toLowerCase()}`}>{proposal.status}</span>
                </header>
                <div className="eng-proposal-objects">
                  {proposal.proposed_objects.map((item, index) => {
                    const validation = proposal.validation_results.find((candidate) => candidate.index === index);
                    return (
                      <div className={`eng-proposal-object eng-object-surface ${engineeringObjectTypeClass(proposalObjectType(proposal, item))}`} key={`${proposal.proposal_id}:${index}`}>
                        {editing ? (
                          <div className="eng-proposal-fields">
                            <label>Name<input defaultValue={String(item.name ?? "")} name={`name-${index}`} /></label>
                            <label>Domäne<input defaultValue={String(item.domain ?? "")} name={`domain-${index}`} /></label>
                            <label>Beschreibung<input defaultValue={String(item.description ?? "")} name={`description-${index}`} /></label>
                          </div>
                        ) : (
                          <div><strong>{String(item.name ?? item.relation_type ?? `Objekt ${index + 1}`)}</strong><span className={`eng-object-badge ${engineeringObjectTypeClass(proposalObjectType(proposal, item))}`}>{engineeringObjectTypeLabel(proposalObjectType(proposal, item))}</span><span>{String(item.domain ?? "generic")}</span></div>
                        )}
                        <div className="eng-proposal-object-actions">
                          {validation && <span className={`status-badge ${validation.valid ? "completed" : "outdated"}`}>{validation.valid ? "VALID" : "INVALID"}</span>}
                          <button className="button secondary tiny" disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => setWizard({ proposalId: proposal.proposal_id, index })} type="button">Wizard</button>
                          {item.canonical_id ? <span className="status-badge approved">Freigegeben</span> : <button className="button primary tiny" disabled={!validation?.valid || Boolean(busy)} onClick={() => void act(`approve:${proposal.proposal_id}:${index}`, () => approveEngineeringProposal(proposal.proposal_id, [index]), "Objekt freigegeben und versioniert gespeichert.")} type="button">Freigeben</button>}
                        </div>
                        {validation?.errors.map((error) => <small className="routing-issue error" key={error}>{error}</small>)}
                      </div>
                    );
                  })}
                </div>
                <footer>
                  <span>Evidence {proposal.evidence.length} · {proposal.model ?? "Modell nicht angegeben"}</span>
                  <div>
                    {editing ? <><button className="button secondary tiny" onClick={() => setEditingId(null)} type="button">Abbrechen</button><button className="button primary tiny" disabled={Boolean(busy)} type="submit">Speichern</button></> : <button className="button secondary tiny" disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => setEditingId(proposal.proposal_id)} type="button">Bearbeiten</button>}
                    <button className="button secondary tiny" disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => void act(`validate:${proposal.proposal_id}`, () => validateEngineeringProposal(proposal.proposal_id), "Vorschlag validiert.")} type="button">Validieren</button>
                    <button className="button danger tiny" disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => void act(`reject:${proposal.proposal_id}`, () => rejectEngineeringProposal(proposal.proposal_id), "Vorschlag abgelehnt.")} type="button">Ablehnen</button>
                  </div>
                </footer>
              </form>
            );
          })}
        </div>
      )}
      {wizard && wizardProposal && (
        <ProposalObjectWizard
          busy={Boolean(busy)}
          index={wizard.index}
          onClose={() => setWizard(null)}
          onSave={(nextItem) => void saveWizard(wizardProposal, wizard.index, nextItem)}
          proposal={wizardProposal}
        />
      )}
      </div>
    </details>
  );
}

function ProposalObjectWizard({
  busy,
  index,
  onClose,
  onSave,
  proposal,
}: {
  busy: boolean;
  index: number;
  onClose: () => void;
  onSave: (nextItem: Record<string, unknown>) => void;
  proposal: EngineeringProposal;
}) {
  const initialItem = proposal.proposed_objects[index] ?? {};
  const objectType = proposalObjectType(proposal, initialItem);
  const validation = proposal.validation_results.find((candidate) => candidate.index === index);
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Record<string, unknown>>(initialItem);
  const [schema, setSchema] = useState<EngineeringSchema | null>(null);
  const [references, setReferences] = useState<Partial<Record<EngineeringResource, EngineeringObject[]>>>({});
  const [loadError, setLoadError] = useState("");
  const missing = missingProposalFields(objectType, draft);
  const isLastStep = step === WIZARD_STEPS.length - 1;

  useEffect(() => {
    setDraft(initialItem);
    setStep(0);
  }, [initialItem, proposal.proposal_id, index]);

  useEffect(() => {
    let cancelled = false;
    setLoadError("");
    Promise.all([
      getEngineeringSchema(),
      listAllEngineeringObjects("hardware-nodes"),
      listAllEngineeringObjects("functions"),
      listAllEngineeringObjects("interfaces"),
      listAllEngineeringObjects("messages"),
      listAllEngineeringObjects("signals"),
    ])
      .then(([nextSchema, hardwareNodes, functions, interfaces, messages, signals]) => {
        if (cancelled) return;
        setSchema(nextSchema);
        setReferences({
          "hardware-nodes": hardwareNodes.filter((item) => !isMergedHardwareAlias(item)),
          functions,
          interfaces,
          messages,
          signals,
        });
        setDraft((current) => ({
          ...current,
          ...(objectType === "HardwareNode" && !current.device_type ? { device_type: nextSchema.device_types[0] ?? "ECU" } : {}),
          ...(objectType === "Interface" && !current.interface_type ? { interface_type: nextSchema.interface_types[0] ?? "CAN" } : {}),
        }));
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : "Referenzen konnten nicht geladen werden.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function updateField(field: string, value: unknown) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function updateFunction(value: string) {
    const selectedFunction = references.functions?.find((item) => item.id === value);
    setDraft((current) => ({
      ...current,
      function_id: value || null,
      hardware_node_id: selectedFunction && "hardware_node_id" in selectedFunction ? selectedFunction.hardware_node_id : current.hardware_node_id ?? null,
    }));
  }

  function fillDefaultsFrom(technology: string, type = objectType) {
    const defaults = busDefaultsFor(technology, type);
    setDraft((current) => {
      const next = { ...current };
      for (const [key, value] of Object.entries(defaults)) {
        if (fieldValue(next[key]).trim() === "") next[key] = value;
      }
      return next;
    });
  }

  function updateInterface(value: string) {
    const selectedInterface = references.interfaces?.find((item) => item.id === value);
    setDraft((current) => {
      const next: Record<string, unknown> = { ...current, interface_id: value || null };
      if (selectedInterface) {
        for (const [key, defaultValue] of Object.entries(busDefaultsFor(interfaceTechnology(selectedInterface), "Message"))) {
          if (fieldValue(next[key]).trim() === "") next[key] = defaultValue;
        }
      }
      return next;
    });
  }

  function updateMessage(value: string) {
    const selectedMessage = references.messages?.find((item) => item.id === value);
    const selectedInterface = selectedMessage && "interface_id" in selectedMessage ? objectById(references, selectedMessage.interface_id) : undefined;
    setDraft((current) => {
      const next: Record<string, unknown> = { ...current, message_id: value || null };
      if (selectedInterface) {
        for (const [key, defaultValue] of Object.entries(busDefaultsFor(interfaceTechnology(selectedInterface), "Signal"))) {
          if (fieldValue(next[key]).trim() === "") next[key] = defaultValue;
        }
      }
      return next;
    });
  }

  function objectOptions(type: string) {
    const resource = OBJECT_TYPE_TO_RESOURCE[type];
    return resource ? references[resource] ?? [] : [];
  }

  function normalizedDraft() {
    const next: Record<string, unknown> = { ...draft, object_type: objectType };
    for (const field of ["cycle_ms", "dlc", "start_bit", "length_bits", "factor", "offset_value", "min_value", "max_value"]) {
      if (field in next) next[field] = optionalNumberValue(fieldValue(next[field]));
    }
    for (const field of ["description", "domain", "hardware_node_id", "function_id", "interface_id", "message_id", "message_id_hex", "direction", "display_name", "byte_order", "data_type", "unit", "source_id", "target_id"]) {
      if (field in next && fieldValue(next[field]).trim() === "") next[field] = null;
    }
    if (objectType === "HardwareNode" && !next.device_type) next.device_type = schema?.device_types[0] ?? "ECU";
    if (objectType === "Interface" && !next.interface_type) next.interface_type = schema?.interface_types[0] ?? "CAN";
    return next;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave(normalizedDraft());
  }

  return (
    <div className="proposal-wizard-backdrop" role="presentation">
      <form aria-modal="true" className="proposal-wizard" onSubmit={submit} role="dialog">
        <header>
          <div>
            <p className="eyebrow">Proposal Wizard</p>
            <h3>{String(draft.name ?? draft.relation_type ?? `Objekt ${index + 1}`)}</h3>
            <span>{objectType} · {proposal.prompt}</span>
          </div>
          <button className="button secondary tiny" onClick={onClose} type="button">Abbrechen</button>
        </header>

        <div className="proposal-wizard-steps">
          {WIZARD_STEPS.map((label, stepIndex) => (
            <button
              className={stepIndex === step ? "active" : ""}
              key={label}
              onClick={() => setStep(stepIndex)}
              type="button"
            >
              <span>{String(stepIndex + 1).padStart(2, "0")}</span>
              {label}
            </button>
          ))}
        </div>

        {loadError && <div className="notice error">{loadError}</div>}

        {step === 0 && (
          <div className="proposal-wizard-grid">
            {objectType !== "Relation" && (
              <>
                <WizardField label="Name" required value={fieldValue(draft.name)} onChange={(value) => updateField("name", value)} />
                <WizardField label="Domäne" value={fieldValue(draft.domain)} onChange={(value) => updateField("domain", value)} placeholder="z. B. automotive" />
                <label className="field full-width">
                  <span>Beschreibung</span>
                  <textarea onChange={(event) => updateField("description", event.target.value)} rows={3} value={fieldValue(draft.description)} />
                </label>
              </>
            )}
            {objectType === "Relation" && (
              <>
                <label className="field">
                  <span>Relation</span>
                  <select required onChange={(event) => updateField("relation_type", event.target.value)} value={fieldValue(draft.relation_type)}>
                    <option value="">Auswählen</option>
                    {RELATION_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Quelle-Typ</span>
                  <select required onChange={(event) => updateField("source_type", event.target.value)} value={fieldValue(draft.source_type)}>
                    <option value="">Auswählen</option>
                    {Object.keys(OBJECT_TYPE_TO_RESOURCE).map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
                <label className="field">
                  <span>Ziel-Typ</span>
                  <select required onChange={(event) => updateField("target_type", event.target.value)} value={fieldValue(draft.target_type)}>
                    <option value="">Auswählen</option>
                    {Object.keys(OBJECT_TYPE_TO_RESOURCE).map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
              </>
            )}
          </div>
        )}

        {step === 1 && (
          <div className="proposal-wizard-grid">
            {objectType === "HardwareNode" && (
              <label className="field">
                <span>Gerätetyp</span>
                <select required onChange={(event) => updateField("device_type", event.target.value)} value={fieldValue(draft.device_type || schema?.device_types[0] || "ECU")}>
                  {(schema?.device_types ?? ["ECU"]).map((type) => <option key={type} value={type}>{engineeringDeviceTypeLabel(type)}</option>)}
                </select>
              </label>
            )}
            {objectType === "Function" && (
              <ReferenceSelect label="Hardware-Knoten" options={references["hardware-nodes"] ?? []} proposal={proposal} references={references} required value={fieldValue(draft.hardware_node_id)} onChange={(value) => updateField("hardware_node_id", value || null)} draft={draft} />
            )}
            {objectType === "Interface" && (
              <>
                <ReferenceSelect label="Funktion" options={references.functions ?? []} proposal={proposal} references={references} required value={fieldValue(draft.function_id)} onChange={updateFunction} draft={draft} />
                <label className="field">
                  <span>Interface-Typ</span>
                  <select required onChange={(event) => updateField("interface_type", event.target.value)} value={fieldValue(draft.interface_type || schema?.interface_types[0] || "CAN")}>
                    {(schema?.interface_types ?? ["CAN"]).map((type) => <option key={type} value={type}>{type}</option>)}
                  </select>
                </label>
              </>
            )}
            {objectType === "Message" && (
              <>
                <ReferenceSelect label="Interface" options={references.interfaces ?? []} proposal={proposal} references={references} required value={fieldValue(draft.interface_id)} onChange={updateInterface} draft={draft} />
                {draft.interface_id && <button className="button secondary" onClick={() => fillDefaultsFrom(interfaceTechnology(objectById(references, draft.interface_id)), "Message")} type="button">Leere Felder per Bus füllen</button>}
              </>
            )}
            {objectType === "Signal" && (
              <>
                <ReferenceSelect label="Message" options={references.messages ?? []} proposal={proposal} references={references} required value={fieldValue(draft.message_id)} onChange={updateMessage} draft={draft} />
                {draft.message_id && <button className="button secondary" onClick={() => {
                  const message = objectById(references, draft.message_id);
                  const iface = message && "interface_id" in message ? objectById(references, message.interface_id) : undefined;
                  fillDefaultsFrom(interfaceTechnology(iface), "Signal");
                }} type="button">Leere Felder per Bus füllen</button>}
              </>
            )}
            {objectType === "Relation" && (
              <>
                <ReferenceSelect label="Quelle" options={objectOptions(fieldValue(draft.source_type))} proposal={proposal} references={references} required value={fieldValue(draft.source_id)} onChange={(value) => updateField("source_id", value || null)} draft={draft} />
                <ReferenceSelect label="Ziel" options={objectOptions(fieldValue(draft.target_type))} proposal={proposal} references={references} required value={fieldValue(draft.target_id)} onChange={(value) => updateField("target_id", value || null)} draft={draft} />
              </>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="proposal-wizard-grid three">
            {objectType === "Message" && (
              <>
                <WizardField label="Message-ID" value={fieldValue(draft.message_id_hex)} onChange={(value) => updateField("message_id_hex", value)} placeholder="0x1A0" />
                <label className="field">
                  <span>Richtung</span>
                  <select onChange={(event) => updateField("direction", event.target.value || null)} value={fieldValue(draft.direction)}>
                    <option value="">Offen</option>
                    {(schema?.message_directions ?? ["tx", "rx", "bidirectional"]).map((dir) => <option key={dir} value={dir}>{dir}</option>)}
                  </select>
                </label>
                <WizardField inputMode="decimal" label="Zyklus (ms)" type="number" value={fieldValue(draft.cycle_ms)} onChange={(value) => updateField("cycle_ms", value)} />
                <WizardField inputMode="numeric" label="DLC" type="number" value={fieldValue(draft.dlc)} onChange={(value) => updateField("dlc", value)} />
              </>
            )}
            {objectType === "Signal" && (
              <>
                <WizardField label="Anzeigename" value={fieldValue(draft.display_name)} onChange={(value) => updateField("display_name", value)} />
                <WizardField inputMode="numeric" label="Start-Bit" type="number" value={fieldValue(draft.start_bit)} onChange={(value) => updateField("start_bit", value)} />
                <WizardField inputMode="numeric" label="Länge (Bit)" type="number" value={fieldValue(draft.length_bits)} onChange={(value) => updateField("length_bits", value)} />
                <label className="field">
                  <span>Byte Order</span>
                  <select onChange={(event) => updateField("byte_order", event.target.value || null)} value={fieldValue(draft.byte_order)}>
                    <option value="">Offen</option>
                    {SIGNAL_BYTE_ORDERS.map((order) => <option key={order} value={order}>{order}</option>)}
                  </select>
                </label>
                <WizardField label="Datentyp" value={fieldValue(draft.data_type)} onChange={(value) => updateField("data_type", value)} placeholder="unsigned" />
                <WizardField label="Einheit" value={fieldValue(draft.unit)} onChange={(value) => updateField("unit", value)} />
                <WizardField inputMode="decimal" label="Faktor" type="number" value={fieldValue(draft.factor)} onChange={(value) => updateField("factor", value)} />
                <WizardField inputMode="decimal" label="Offset" type="number" value={fieldValue(draft.offset_value)} onChange={(value) => updateField("offset_value", value)} />
                <WizardField inputMode="decimal" label="Min" type="number" value={fieldValue(draft.min_value)} onChange={(value) => updateField("min_value", value)} />
                <WizardField inputMode="decimal" label="Max" type="number" value={fieldValue(draft.max_value)} onChange={(value) => updateField("max_value", value)} />
              </>
            )}
            {!["Message", "Signal"].includes(objectType) && (
              <div className="proposal-wizard-help">
                <strong>Keine weiteren Pflichtdetails</strong>
                <span>Für diesen Objekttyp reichen Identität und Zuordnung aus, damit die Backend-Validierung entscheiden kann.</span>
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="proposal-wizard-review">
            <div className={missing.length ? "proposal-wizard-verdict invalid" : "proposal-wizard-verdict valid"}>
              <strong>{missing.length ? "Noch nicht valide" : "Bereit zur Validierung"}</strong>
              <span>{missing.length ? `${missing.length} Pflichtfeld(er) fehlen.` : "Alle bekannten Pflichtfelder sind gefüllt."}</span>
            </div>
            {missing.length > 0 && (
              <div className="proposal-wizard-checks">
                {missing.map((field) => <span key={field}>{FIELD_LABELS[field] ?? field}</span>)}
              </div>
            )}
            {validation?.errors.length ? (
              <div className="proposal-wizard-errors">
                <strong>Aktuelle Backend-Findings</strong>
                {validation.errors.map((error) => <small className="routing-issue error" key={error}>{error}</small>)}
              </div>
            ) : null}
            <ProposalWizardSummary objectType={objectType} references={references} values={normalizedDraft()} />
          </div>
        )}

        <footer>
          <button className="button secondary" disabled={step === 0} onClick={() => setStep((current) => Math.max(0, current - 1))} type="button">Zurück</button>
          {!isLastStep ? (
            <button className="button primary" onClick={() => setStep((current) => Math.min(WIZARD_STEPS.length - 1, current + 1))} type="button">Weiter</button>
          ) : (
            <button className="button primary" disabled={busy || missing.length > 0} type="submit">{busy ? "Speichert ..." : "Speichern & validieren"}</button>
          )}
        </footer>
      </form>
    </div>
  );
}

function ProposalWizardSummary({
  objectType,
  references,
  values,
}: {
  objectType: string;
  references: Partial<Record<EngineeringResource, EngineeringObject[]>>;
  values: Record<string, unknown>;
}) {
  const identityFields = ["name", "domain", "description"].filter((field) => field in values);
  const relationFields = objectType === "Relation"
    ? ["relation_type", "source_type", "source_id", "target_type", "target_id"]
    : [];
  const assignmentFields = {
    HardwareNode: ["device_type"],
    Function: ["hardware_node_id"],
    Interface: ["function_id", "hardware_node_id", "interface_type"],
    Message: ["interface_id"],
    Signal: ["message_id"],
  }[objectType] ?? [];
  const detailFields = {
    Message: ["message_id_hex", "direction", "cycle_ms", "dlc"],
    Signal: ["display_name", "start_bit", "length_bits", "byte_order", "data_type", "factor", "offset_value", "unit", "min_value", "max_value"],
  }[objectType] ?? [];

  const sections = [
    { title: "Identität", fields: identityFields },
    { title: objectType === "Relation" ? "Relation" : "Zuordnung", fields: relationFields.length ? relationFields : assignmentFields },
    { title: "Technische Details", fields: detailFields },
  ].filter((section) => section.fields.length > 0);

  return (
    <div className="proposal-wizard-summary">
      {sections.map((section) => (
        <section key={section.title}>
          <h4>{section.title}</h4>
          <dl>
            {section.fields.map((field) => (
              <Fragment key={field}>
                <dt>{FIELD_LABELS[field] ?? field}</dt>
                <dd>{field.endsWith("_id") ? referenceDisplay(references, field, values[field]) : fieldValue(values[field]) || "Nicht gesetzt"}</dd>
              </Fragment>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}

function WizardField({
  inputMode,
  label,
  onChange,
  placeholder,
  required,
  type = "text",
  value,
}: {
  inputMode?: "decimal" | "numeric";
  label: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  type?: string;
  value: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input inputMode={inputMode} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} required={required} type={type} value={value} />
    </label>
  );
}

function ReferenceSelect({
  draft,
  label,
  onChange,
  options,
  proposal,
  references,
  required,
  value,
}: {
  draft: Record<string, unknown>;
  label: string;
  onChange: (value: string) => void;
  options: EngineeringObject[];
  proposal: EngineeringProposal;
  references: Partial<Record<EngineeringResource, EngineeringObject[]>>;
  required?: boolean;
  value: string;
}) {
  const suggestions = referenceSuggestions(proposal, draft, options, references);
  return (
    <div className="proposal-reference-picker">
      <label className="field">
        <span>{label}</span>
        <select disabled={options.length === 0} onChange={(event) => onChange(event.target.value)} required={required} value={value}>
          <option value="">{options.length ? "Auswählen" : "Keine Referenz vorhanden"}</option>
          {options.map((item) => <option key={item.id} value={item.id}>{optionLabel(item, references)}</option>)}
        </select>
      </label>
      {options.length === 0 && (
        <p className="proposal-reference-empty">
          {referenceEmptyHint(label)}
        </p>
      )}
      {suggestions.length > 0 && (
        <div className="proposal-ai-suggestions">
          <span>KI-Vorschläge</span>
          {suggestions.map((suggestion) => (
            <button className={suggestion.id === value ? "active" : ""} key={suggestion.id} onClick={() => onChange(suggestion.id)} type="button">
              <strong>{suggestion.confidence}%</strong>
              <span>{suggestion.label}</span>
              <small>{suggestion.reason}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function referenceEmptyHint(label: string) {
  const subject = label.toLowerCase();
  if (subject.includes("message")) return "Es gibt noch keine Messages im Modell. Lege zuerst eine Message auf einem Interface an.";
  if (subject.includes("interface")) return "Es gibt noch keine Interfaces im Modell. Lege zuerst eine Function und ein Interface an.";
  if (subject.includes("funktion")) return "Es gibt noch keine Functions im Modell. Lege zuerst eine Function auf einem Hardware-Knoten an.";
  if (subject.includes("hardware")) return "Es gibt noch keine Hardware-Knoten im Modell. Lege zuerst Hardware an.";
  return "Das benötigte Elternobjekt ist noch nicht im Modell angelegt.";
}

function CreateForm({
  hardwarePreset,
  onClose,
  resource,
  schema,
  onCreated,
}: {
  hardwarePreset: string | null;
  onClose: () => void;
  resource: EngineeringResource;
  schema: EngineeringSchema | null;
  onCreated: () => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [step, setStep] = useState(0);
  const [reviewValues, setReviewValues] = useState<Record<string, unknown>>({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [deviceType, setDeviceType] = useState(
    hardwarePreset ?? schema?.device_types[0] ?? "ECU",
  );
  const [parents, setParents] = useState<EngineeringObject[]>([]);
  const [parentId, setParentId] = useState("");
  const [loadingParents, setLoadingParents] = useState(false);
  const hierarchy = RESOURCE_HIERARCHY[resource];
  const objectType = RESOURCE_TO_OBJECT_TYPE[resource];
  const references = useMemo<Partial<Record<EngineeringResource, EngineeringObject[]>>>(() => (
    hierarchy ? { [hierarchy.parentResource]: parents } : {}
  ), [hierarchy, parents]);
  const missing = missingProposalFields(objectType, reviewValues);

  useEffect(() => {
    if (!hierarchy) {
      setParents([]);
      setParentId("");
      return;
    }
    let cancelled = false;
    setLoadingParents(true);
    listAllEngineeringObjects(hierarchy.parentResource)
      .then((items) => {
        if (cancelled) return;
        const availableItems = hierarchy.parentResource === "hardware-nodes"
          ? items.filter((item) => !isMergedHardwareAlias(item))
          : items;
        setParents(availableItems);
        setParentId(availableItems[0]?.id ?? "");
      })
      .catch((err) => {
        if (!cancelled) {
          setFormError(err instanceof Error ? err.message : "Übergeordnete Objekte konnten nicht geladen werden.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingParents(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hierarchy]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !submitting) onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose, submitting]);

  function optionalFormNumber(form: FormData, name: string) {
    const value = form.get(name);
    return value === null || value === "" ? null : Number(value);
  }

  function payloadFrom(form: FormData) {
    const payload: Record<string, unknown> = {
      name: form.get("name"),
      description: form.get("description") || null,
      domain: form.get("domain") || null,
    };
    const parent = parents.find((item) => item.id === parentId);
    if (resource === "hardware-nodes") payload.device_type = form.get("device_type");
    if (resource === "functions") payload.hardware_node_id = parentId;
    if (resource === "interfaces") payload.interface_type = form.get("interface_type");
    if (resource === "interfaces" && parent) {
      payload.function_id = parentId;
      if ("hardware_node_id" in parent) payload.hardware_node_id = parent.hardware_node_id;
    }
    if (resource === "messages") {
      payload.interface_id = parentId;
      payload.message_id_hex = form.get("message_id_hex") || null;
      payload.direction = form.get("direction") || null;
      payload.cycle_ms = optionalFormNumber(form, "cycle_ms");
      payload.dlc = optionalFormNumber(form, "dlc");
      payload.configuration = requirementPayload(form, "requirement_");
    }
    if (resource === "signals") {
      payload.message_id = parentId;
      payload.display_name = form.get("display_name") || null;
      payload.start_bit = optionalFormNumber(form, "start_bit");
      payload.length_bits = optionalFormNumber(form, "length_bits");
      payload.byte_order = form.get("byte_order") || null;
      payload.data_type = form.get("data_type") || null;
      payload.factor = optionalFormNumber(form, "factor");
      payload.offset_value = optionalFormNumber(form, "offset_value");
      payload.unit = form.get("unit") || null;
      payload.min_value = optionalFormNumber(form, "min_value");
      payload.max_value = optionalFormNumber(form, "max_value");
      payload.communication = requirementPayload(form, "requirement_");
    }
    return payload;
  }

  function openStep(nextStep: number) {
    if (nextStep === WIZARD_STEPS.length - 1 && formRef.current) {
      setReviewValues(payloadFrom(new FormData(formRef.current)));
    }
    setStep(nextStep);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError("");
    const form = new FormData(event.currentTarget);
    const payload = payloadFrom(form);
    const parent = parents.find((item) => item.id === parentId);
    if (hierarchy && !parent) {
      setFormError(`Wähle zuerst eine übergeordnete ${hierarchy.parentLabel}.`);
      setSubmitting(false);
      return;
    }
    try {
      await createEngineeringObject(resource, payload);
      onCreated();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Anlegen fehlgeschlagen.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="proposal-wizard-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !submitting && onClose()} role="presentation">
    <form aria-modal="true" className="proposal-wizard eng-object-wizard" onMouseDown={(event) => event.stopPropagation()} onSubmit={submit} ref={formRef} role="dialog">
      <header>
        <div>
          <p className="eyebrow">Objekt-Wizard</p>
          <h3>{RESOURCE_LABELS[resource]} anlegen</h3>
          <span>Das Objekt wird nach der Prüfung im kanonischen Engineering-Modell gespeichert.</span>
        </div>
        <button className="button secondary tiny" disabled={submitting} onClick={onClose} type="button">Abbrechen</button>
      </header>

      <div className="proposal-wizard-steps">
        {WIZARD_STEPS.map((label, index) => (
          <button className={index === step ? "active" : ""} key={label} onClick={() => openStep(index)} type="button"><span>{String(index + 1).padStart(2, "0")}</span>{label}</button>
        ))}
      </div>

      <div className="proposal-wizard-grid" hidden={step !== 0}>
        <div className="field">
          <label htmlFor="name">Name</label>
          <input autoFocus id="name" name="name" placeholder={hardwarePreset ? `${HARDWARE_PRESETS.find((item) => item.deviceType === hardwarePreset)?.label} Name` : undefined} required type="text" />
        </div>
        <div className="field">
          <label htmlFor="domain">Domäne</label>
          <input id="domain" name="domain" placeholder="z. B. automotive" type="text" />
        </div>
        <div className="field full-width">
          <label htmlFor="description">Beschreibung</label>
          <textarea id="description" name="description" rows={3} />
        </div>
      </div>

      <div className="proposal-wizard-grid" hidden={step !== 1}>
      {hierarchy && (
        <div className="field eng-parent-field">
          <label htmlFor="parent_id">Enthalten in: {hierarchy.parentLabel}</label>
          <select
            disabled={loadingParents || parents.length === 0}
            id="parent_id"
            onChange={(event) => setParentId(event.target.value)}
            required
            value={parentId}
          >
            {loadingParents && <option value="">Wird geladen …</option>}
            {!loadingParents && parents.length === 0 && <option value="">Kein übergeordnetes Objekt vorhanden</option>}
            {parents.map((parent) => (
              <option key={parent.id} value={parent.id}>
                {parent.name}{parent.domain ? ` · ${parent.domain}` : ""}
              </option>
            ))}
          </select>
          {!loadingParents && parents.length === 0 && (
            <p className="field-hint">Lege zuerst eine {hierarchy.parentLabel} an.</p>
          )}
        </div>
      )}
      {resource === "hardware-nodes" && (
        <div className="field">
          <label htmlFor="device_type">Gerätetyp</label>
          <select
            id="device_type"
            name="device_type"
            onChange={(event) => setDeviceType(event.target.value)}
            required
            value={deviceType}
          >
            {(schema?.device_types ?? ["ECU"]).map((type) => (
              <option key={type} value={type}>
                {engineeringDeviceTypeLabel(type)}
              </option>
            ))}
          </select>
        </div>
      )}

      {resource === "interfaces" && (
        <div className="field">
          <label htmlFor="interface_type">Interface-Typ</label>
          <select id="interface_type" name="interface_type" required>
            {(schema?.interface_types ?? ["CAN"]).map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
      )}
      </div>

      <div className="proposal-wizard-grid three" hidden={step !== 2}>
      {!(["messages", "signals"] as EngineeringResource[]).includes(resource) && (
        <div className="proposal-wizard-help">
          <strong>Keine weiteren technischen Pflichtfelder</strong>
          <span>Identität und Zuordnung reichen für diesen Objekttyp aus. Zusätzliche Beziehungen können anschließend am Objekt gepflegt werden.</span>
        </div>
      )}

      {resource === "messages" && (
        <>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="message_id_hex">Message-ID (hex)</label>
            <input id="message_id_hex" name="message_id_hex" type="text" placeholder="0x1A0" />
          </div>
          <div className="field">
            <label htmlFor="direction">Richtung</label>
            <select id="direction" name="direction">
              {(schema?.message_directions ?? ["tx", "rx", "bidirectional"]).map((dir) => (
                <option key={dir} value={dir}>
                  {dir}
                </option>
              ))}
            </select>
          </div>
          <div className="field"><label htmlFor="cycle_ms">Zyklus (ms)</label><input id="cycle_ms" min="0.001" name="cycle_ms" step="0.001" type="number" /></div>
          <div className="field"><label htmlFor="dlc">DLC</label><input id="dlc" min="0" name="dlc" type="number" /></div>
        </div>
        <RequirementFields prefix="requirement_" />
        </>
      )}

      {resource === "signals" && (
        <>
        <div className="form-grid three">
          <div className="field">
            <label htmlFor="display_name">Anzeigename</label>
            <input id="display_name" name="display_name" type="text" />
          </div>
          <div className="field">
            <label htmlFor="start_bit">Start-Bit</label>
            <input id="start_bit" min="0" name="start_bit" type="number" />
          </div>
          <div className="field">
            <label htmlFor="length_bits">Länge (Bit)</label>
            <input id="length_bits" min="1" name="length_bits" type="number" />
          </div>
          <div className="field"><label htmlFor="byte_order">Byte-Reihenfolge</label><select id="byte_order" name="byte_order"><option value="">—</option>{SIGNAL_BYTE_ORDERS.map((order) => <option key={order} value={order}>{order}</option>)}</select></div>
          <div className="field"><label htmlFor="data_type">Datentyp</label><input id="data_type" list="create-signal-data-types" name="data_type" placeholder="unsigned" type="text" /><datalist id="create-signal-data-types"><option value="unsigned" /><option value="signed" /><option value="float" /><option value="boolean" /><option value="string" /><option value="bytes" /></datalist></div>
          <div className="field"><label htmlFor="factor">Faktor</label><input id="factor" name="factor" step="any" type="number" /></div>
          <div className="field"><label htmlFor="offset_value">Offset</label><input id="offset_value" name="offset_value" step="any" type="number" /></div>
          <div className="field"><label htmlFor="unit">Einheit</label><input id="unit" name="unit" type="text" /></div>
          <div className="field"><label htmlFor="min_value">Minimum</label><input id="min_value" name="min_value" step="any" type="number" /></div>
          <div className="field"><label htmlFor="max_value">Maximum</label><input id="max_value" name="max_value" step="any" type="number" /></div>
        </div>
        <RequirementFields prefix="requirement_" />
        </>
      )}
      </div>

      <div className="proposal-wizard-review" hidden={step !== 3}>
        <div className={missing.length ? "proposal-wizard-verdict invalid" : "proposal-wizard-verdict valid"}>
          <strong>{missing.length ? "Noch nicht vollständig" : "Bereit zum Anlegen"}</strong>
          <span>{missing.length ? `${missing.length} Pflichtfeld(er) fehlen.` : "Alle bekannten Pflichtfelder sind gefüllt."}</span>
        </div>
        {missing.length > 0 && <div className="proposal-wizard-checks">{missing.map((field) => <span key={field}>{FIELD_LABELS[field] ?? field}</span>)}</div>}
        <ProposalWizardSummary objectType={objectType} references={references} values={reviewValues} />
      </div>

      {formError && <div className="notice error">{formError}</div>}

      <footer>
        <button className="button secondary" disabled={step === 0 || submitting} onClick={() => openStep(Math.max(0, step - 1))} type="button">Zurück</button>
        {step < WIZARD_STEPS.length - 1 ? (
          <button className="button primary" disabled={loadingParents} onClick={() => openStep(Math.min(WIZARD_STEPS.length - 1, step + 1))} type="button">Weiter</button>
        ) : (
          <button className="button primary" disabled={submitting || missing.length > 0 || Boolean(hierarchy && !parentId)} type="submit">{submitting ? "Wird angelegt …" : "Objekt anlegen"}</button>
        )}
      </footer>
    </form>
    </div>
  );
}

function DetailPanel({
  item,
  referenceNames,
  resource,
  relations,
  schema,
  onChanged,
  onDeleted,
}: {
  item: EngineeringObject;
  referenceNames: Record<string, string>;
  resource: EngineeringResource;
  relations: EngineeringRelation[];
  schema: EngineeringSchema | null;
  onChanged: () => void;
  onDeleted: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [showRelationForm, setShowRelationForm] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  useEffect(() => {
    setShowEdit(false);
    setNotice("");
  }, [item.id]);

  async function setLifecycle(next: string) {
    setBusy(true);
    setNotice("");
    try {
      await updateEngineeringObject(resource, item.id, { lifecycle_state: next });
      onChanged();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Aktualisierung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function setReview(next: string) {
    setBusy(true);
    setNotice("");
    try {
      await updateEngineeringObject(resource, item.id, { review_state: next });
      onChanged();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Aktualisierung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setNotice("");
    try {
      await deleteEngineeringObject(resource, item.id);
      onDeleted();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Löschen fehlgeschlagen (nur 'draft' löschbar).");
    } finally {
      setBusy(false);
    }
  }

  async function removeRelation(relationId: string) {
    setBusy(true);
    try {
      await deleteEngineeringRelation(relationId);
      onChanged();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Relation konnte nicht gelöscht werden.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="eng-detail-dropdown">
      <details className="eng-detail-section" open>
        <summary>
          <span className={`eng-object-badge ${engineeringObjectTypeClass(engineeringResourceType(resource))}`}>{engineeringObjectTypeLabel(engineeringResourceType(resource))}</span>
          <strong>{item.name}</strong>
        </summary>
        <div className="eng-detail-section-body">
          <div className="panel-heading">
            <div>
              <p className={`eyebrow eng-object-label ${engineeringObjectTypeClass(engineeringResourceType(resource))}`}>{engineeringObjectTypeLabel(engineeringResourceType(resource))}</p>
              <h2>{item.name}</h2>
            </div>
            <button className="button secondary tiny" onClick={() => setShowEdit((value) => !value)} type="button">
              {showEdit ? "Abbrechen" : "Bearbeiten"}
            </button>
          </div>
          {showEdit && (
            <EditObjectForm
              item={item}
              resource={resource}
              schema={schema}
              onSaved={() => {
                setShowEdit(false);
                onChanged();
              }}
            />
          )}
          <dl className="overview-list">
            <div>
              <dt>Domäne</dt>
              <dd>{item.domain ?? "—"}</dd>
            </div>
            <div>
              <dt>Version</dt>
              <dd>v{item.version}</dd>
            </div>
            <div>
              <dt>Quelle</dt>
              <dd>{item.source}</dd>
            </div>
            <div>
              <dt>Approval</dt>
              <dd>{item.approval_state}</dd>
            </div>
          </dl>
          {resource === "signals" && "start_bit" in item && (
            <SignalParameterOverview item={item} referenceNames={referenceNames} />
          )}
          {item.description && <p className="muted" style={{ marginTop: 14, fontSize: 12 }}>{item.description}</p>}

          <div className="section-title">
            <span>Lifecycle</span>
          </div>
          <div className="eng-pill-row">
            {["draft", "active", "deprecated", "superseded"].map((state) => (
              <button
                className={`button secondary tiny ${item.lifecycle_state === state ? "active" : ""}`}
                disabled={busy}
                key={state}
                onClick={() => setLifecycle(state)}
                type="button"
              >
                {state}
              </button>
            ))}
          </div>

          <div className="section-title">
            <span>Review</span>
          </div>
          <div className="eng-pill-row">
            {["unreviewed", "in_review", "reviewed", "rejected"].map((state) => (
              <button
                className={`button secondary tiny ${item.review_state === state ? "active" : ""}`}
                disabled={busy}
                key={state}
                onClick={() => setReview(state)}
                type="button"
              >
                {state}
              </button>
            ))}
          </div>

          {notice && <div className="notice error">{notice}</div>}

          <div className="form-actions">
            <button className="button secondary" disabled={busy || item.lifecycle_state !== "draft"} onClick={remove} type="button">
              Löschen
            </button>
          </div>
        </div>
      </details>

      <details className="eng-detail-section">
        <summary>
          <span>Relations</span>
          <strong>Knowledge-Graph-Kanten</strong>
        </summary>
        <div className="eng-detail-section-body">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Relations</p>
              <h2 style={{ fontSize: 16 }}>Knowledge-Graph-Kanten</h2>
            </div>
            <button className="button secondary" onClick={() => setShowRelationForm((v) => !v)} type="button">
              {showRelationForm ? "Abbrechen" : "+ Relation"}
            </button>
          </div>

          {showRelationForm && (
            <RelationForm
              sourceType={RESOURCE_TO_OBJECT_TYPE[resource]}
              sourceId={item.id}
              onCreated={() => {
                setShowRelationForm(false);
                onChanged();
              }}
            />
          )}

          {relations.length === 0 ? (
            <p className="muted" style={{ fontSize: 12, marginTop: 14 }}>
              Noch keine Relations für dieses Objekt.
            </p>
          ) : (
            <ul className="eng-relation-list">
              {relations.map((relation) => {
                const relationName = typeof relation.attributes?.name === "string" ? relation.attributes.name : "";
                const relationDescription = typeof relation.attributes?.description === "string" ? relation.attributes.description : "";
                return <li key={relation.id}>
                  <span className="tag">{relation.relation_type}</span>
                  <span className="eng-relation-content"><strong>{relationName || relation.relation_type}</strong><small>{relation.source_type}:{relation.source_id.slice(0, 8)} → {relation.target_type}:{relation.target_id.slice(0, 8)}</small>{relationDescription && <small>{relationDescription}</small>}</span>
                  <button
                    aria-label="Relation löschen"
                    className="eng-relation-remove"
                    disabled={busy}
                    onClick={() => removeRelation(relation.id)}
                    type="button"
                  >
                    ×
                  </button>
                </li>
              })}
            </ul>
          )}
        </div>
      </details>

      <ProposalReviewPanel item={item} onChanged={onChanged} resource={resource} />
    </div>
  );
}

function signalParameterValue(value: unknown, unit?: string | null) {
  if (value === null || value === undefined || value === "") return "—";
  const suffix = unit ? ` ${unit}` : "";
  return `${String(value)}${suffix}`;
}

function SignalParameterOverview({
  item,
  referenceNames,
}: {
  item: EngSignal;
  referenceNames: Record<string, string>;
}) {
  const communication = item.communication ?? {};
  const message = item.message_id ? referenceNames[item.message_id] ?? item.message_id : "—";
  return (
    <>
      <div className="section-title signal-parameter-heading">
        <span>Signalparameter</span>
      </div>
      <dl className="overview-list eng-signal-parameter-list">
        <div><dt>Nachricht</dt><dd>{message}</dd></div>
        <div><dt>Anzeigename</dt><dd>{signalParameterValue(item.display_name)}</dd></div>
        <div><dt>Start-Bit</dt><dd>{signalParameterValue(item.start_bit)}</dd></div>
        <div><dt>Länge</dt><dd>{signalParameterValue(item.length_bits, "Bit")}</dd></div>
        <div><dt>Byte-Reihenfolge</dt><dd>{signalParameterValue(item.byte_order)}</dd></div>
        <div><dt>Datentyp</dt><dd>{signalParameterValue(item.data_type)}</dd></div>
        <div><dt>Faktor</dt><dd>{signalParameterValue(item.factor)}</dd></div>
        <div><dt>Offset</dt><dd>{signalParameterValue(item.offset_value)}</dd></div>
        <div><dt>Einheit</dt><dd>{signalParameterValue(item.unit)}</dd></div>
        <div><dt>Minimum</dt><dd>{signalParameterValue(item.min_value, item.unit)}</dd></div>
        <div><dt>Maximum</dt><dd>{signalParameterValue(item.max_value, item.unit)}</dd></div>
      </dl>

      <div className="section-title signal-parameter-heading">
        <span>Timing &amp; Qualität</span>
      </div>
      <dl className="overview-list eng-signal-parameter-list">
        {REQUIREMENT_FIELDS.map((field) => (
          <div key={field.key}>
            <dt>{field.label}</dt>
            <dd>{signalParameterValue(communication[field.key], field.unit)}</dd>
          </div>
        ))}
        <div><dt>Priorität</dt><dd>{signalParameterValue(communication.priority)}</dd></div>
        <div><dt>Reliability</dt><dd>{signalParameterValue(communication.reliability_requirement)}</dd></div>
      </dl>
    </>
  );
}

function RequirementFields({ prefix, defaults = {} }: { prefix: string; defaults?: Record<string, unknown> }) {
  return (
    <fieldset className="eng-requirement-fields">
      <legend>Timing & Quality Requirements</legend>
      <div className="form-grid three">
        {REQUIREMENT_FIELDS.map((field) => (
          <div className="field" key={field.key}>
            <label htmlFor={`${prefix}${field.key}`}>{field.label} ({field.unit})</label>
            <input defaultValue={String(defaults[field.key] ?? "")} id={`${prefix}${field.key}`} min="0" name={`${prefix}${field.key}`} step="any" type="number" />
          </div>
        ))}
        <div className="field">
          <label htmlFor={`${prefix}priority`}>Priorität</label>
          <select defaultValue={String(defaults.priority ?? "NORMAL")} id={`${prefix}priority`} name={`${prefix}priority`}>
            {['LOW', 'NORMAL', 'HIGH', 'CRITICAL'].map((value) => <option key={value}>{value}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${prefix}reliability_requirement`}>Reliability</label>
          <select defaultValue={String(defaults.reliability_requirement ?? "RELIABLE")} id={`${prefix}reliability_requirement`} name={`${prefix}reliability_requirement`}>
            <option>BEST_EFFORT</option><option>RELIABLE</option><option>SAFETY_CRITICAL</option>
          </select>
        </div>
      </div>
    </fieldset>
  );
}

function EditObjectForm({
  item,
  resource,
  schema,
  onSaved,
}: {
  item: EngineeringObject;
  resource: EngineeringResource;
  schema: EngineeringSchema | null;
  onSaved: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  function optionalNumber(form: FormData, name: string) {
    const value = form.get(name);
    return value === null || value === "" ? null : Number(value);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError("");
    const form = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = {
      name: form.get("edit_name"),
      domain: form.get("edit_domain") || null,
      description: form.get("edit_description") || null,
    };
    if (resource === "hardware-nodes") payload.device_type = form.get("edit_device_type");
    if (resource === "interfaces") payload.interface_type = form.get("edit_interface_type");
    if (resource === "messages") {
      payload.message_id_hex = form.get("edit_message_id_hex") || null;
      payload.direction = form.get("edit_direction") || null;
      payload.cycle_ms = optionalNumber(form, "edit_cycle_ms");
      payload.dlc = optionalNumber(form, "edit_dlc");
      payload.configuration = {
        ...("configuration" in item ? item.configuration : {}),
        ...requirementPayload(form, "edit_requirement_"),
      };
    }
    if (resource === "signals") {
      payload.display_name = form.get("edit_display_name") || null;
      payload.start_bit = optionalNumber(form, "edit_start_bit");
      payload.length_bits = optionalNumber(form, "edit_length_bits");
      payload.byte_order = form.get("edit_byte_order") || null;
      payload.data_type = form.get("edit_data_type") || null;
      payload.factor = optionalNumber(form, "edit_factor");
      payload.offset_value = optionalNumber(form, "edit_offset_value");
      payload.unit = form.get("edit_unit") || null;
      payload.min_value = optionalNumber(form, "edit_min_value");
      payload.max_value = optionalNumber(form, "edit_max_value");
      payload.communication = {
        ...("communication" in item ? item.communication : {}),
        ...requirementPayload(form, "edit_requirement_"),
      };
    }
    try {
      await updateEngineeringObject(resource, item.id, payload);
      onSaved();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Änderungen konnten nicht gespeichert werden.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="eng-create-form eng-edit-form" onSubmit={submit}>
      <div className="form-grid">
        <div className="field">
          <label htmlFor="edit_name">Name</label>
          <input autoFocus defaultValue={item.name} id="edit_name" name="edit_name" required type="text" />
        </div>
        <div className="field">
          <label htmlFor="edit_domain">Domäne</label>
          <input defaultValue={item.domain ?? ""} id="edit_domain" name="edit_domain" type="text" />
        </div>
      </div>

      {resource === "hardware-nodes" && "device_type" in item && (
        <div className="field">
          <label htmlFor="edit_device_type">Gerätetyp</label>
          <select defaultValue={item.device_type} id="edit_device_type" name="edit_device_type" required>
            {(schema?.device_types ?? [item.device_type]).map((type) => <option key={type} value={type}>{engineeringDeviceTypeLabel(type)}</option>)}
          </select>
        </div>
      )}

      {resource === "interfaces" && "interface_type" in item && (
        <div className="field">
          <label htmlFor="edit_interface_type">Interface-Typ</label>
          <select defaultValue={item.interface_type} id="edit_interface_type" name="edit_interface_type" required>
            {(schema?.interface_types ?? [item.interface_type]).map((type) => <option key={type}>{type}</option>)}
          </select>
        </div>
      )}

      {resource === "messages" && "message_id_hex" in item && (
        <>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="edit_message_id_hex">Message-ID</label>
            <input defaultValue={item.message_id_hex ?? ""} id="edit_message_id_hex" name="edit_message_id_hex" type="text" />
          </div>
          <div className="field">
            <label htmlFor="edit_direction">Richtung</label>
            <select defaultValue={item.direction ?? ""} id="edit_direction" name="edit_direction">
              <option value="">—</option>
              {(schema?.message_directions ?? ["tx", "rx", "bidirectional"]).map((direction) => <option key={direction}>{direction}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="edit_cycle_ms">Zyklus (ms)</label>
            <input defaultValue={item.cycle_ms ?? ""} id="edit_cycle_ms" min="0.001" name="edit_cycle_ms" step="0.001" type="number" />
          </div>
          <div className="field">
            <label htmlFor="edit_dlc">DLC</label>
            <input defaultValue={item.dlc ?? ""} id="edit_dlc" min="0" name="edit_dlc" type="number" />
          </div>
        </div>
        <RequirementFields defaults={item.configuration} prefix="edit_requirement_" />
        </>
      )}

      {resource === "signals" && "start_bit" in item && (
        <>
        <fieldset className="eng-requirement-fields eng-signal-edit-group">
          <legend>Signal-Layout &amp; Codierung</legend>
          <div className="form-grid three">
            <div className="field"><label htmlFor="edit_display_name">Anzeigename</label><input defaultValue={item.display_name ?? ""} id="edit_display_name" name="edit_display_name" type="text" /></div>
            <div className="field"><label htmlFor="edit_start_bit">Start-Bit</label><input defaultValue={item.start_bit ?? ""} id="edit_start_bit" min="0" name="edit_start_bit" type="number" /></div>
            <div className="field"><label htmlFor="edit_length_bits">Länge (Bit)</label><input defaultValue={item.length_bits ?? ""} id="edit_length_bits" min="1" name="edit_length_bits" type="number" /></div>
            <div className="field"><label htmlFor="edit_byte_order">Byte-Reihenfolge</label><select defaultValue={item.byte_order ?? ""} id="edit_byte_order" name="edit_byte_order"><option value="">—</option><option value="little_endian">little_endian</option><option value="big_endian">big_endian</option></select></div>
            <div className="field"><label htmlFor="edit_data_type">Datentyp</label><input defaultValue={item.data_type ?? ""} id="edit_data_type" list="signal-data-types" name="edit_data_type" type="text" /><datalist id="signal-data-types"><option value="unsigned" /><option value="signed" /><option value="float" /><option value="boolean" /><option value="string" /><option value="bytes" /></datalist></div>
          </div>
        </fieldset>
        <fieldset className="eng-requirement-fields eng-signal-edit-group">
          <legend>Physikalische Skalierung</legend>
          <div className="form-grid three">
            <div className="field"><label htmlFor="edit_factor">Faktor</label><input defaultValue={item.factor ?? ""} id="edit_factor" name="edit_factor" step="any" type="number" /></div>
            <div className="field"><label htmlFor="edit_offset_value">Offset</label><input defaultValue={item.offset_value ?? ""} id="edit_offset_value" name="edit_offset_value" step="any" type="number" /></div>
            <div className="field"><label htmlFor="edit_unit">Einheit</label><input defaultValue={item.unit ?? ""} id="edit_unit" name="edit_unit" type="text" /></div>
            <div className="field"><label htmlFor="edit_min_value">Minimum</label><input defaultValue={item.min_value ?? ""} id="edit_min_value" name="edit_min_value" step="any" type="number" /></div>
            <div className="field"><label htmlFor="edit_max_value">Maximum</label><input defaultValue={item.max_value ?? ""} id="edit_max_value" name="edit_max_value" step="any" type="number" /></div>
          </div>
        </fieldset>
        <RequirementFields defaults={item.communication} prefix="edit_requirement_" />
        </>
      )}

      <div className="field">
        <label htmlFor="edit_description">Beschreibung</label>
        <textarea defaultValue={item.description ?? ""} id="edit_description" name="edit_description" rows={3} />
      </div>
      {formError && <div className="notice error">{formError}</div>}
      <div className="form-actions">
        <button className="button primary" disabled={submitting} type="submit">
          {submitting ? "Wird gespeichert …" : "Änderungen speichern"}
        </button>
      </div>
    </form>
  );
}

function RelationForm({
  sourceType,
  sourceId,
  onCreated,
}: {
  sourceType: string;
  sourceId: string;
  onCreated: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError("");
    const form = new FormData(event.currentTarget);
    try {
      await createEngineeringRelation({
        source_type: sourceType,
        source_id: sourceId,
        target_type: String(form.get("target_type")),
        target_id: String(form.get("target_id")),
        relation_type: String(form.get("relation_type")),
      });
      onCreated();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Relation konnte nicht erstellt werden.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="eng-create-form" onSubmit={submit}>
      <div className="field">
        <label htmlFor="relation_type">Relationstyp</label>
        <select id="relation_type" name="relation_type" required>
          {RELATION_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor="target_type">Ziel-Typ</label>
          <select id="target_type" name="target_type" required>
            {["HardwareNode", "Function", "Interface", "Message", "Signal"].map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="target_id">Ziel-ID (UUID)</label>
          <input id="target_id" name="target_id" required type="text" placeholder="uuid" />
        </div>
      </div>
      {formError && <div className="notice error">{formError}</div>}
      <div className="form-actions">
        <button className="button primary" disabled={submitting} type="submit">
          {submitting ? "Wird verknüpft …" : "Relation anlegen"}
        </button>
      </div>
    </form>
  );
}
