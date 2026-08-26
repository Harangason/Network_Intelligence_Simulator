"use client";

import { FormEvent, Fragment, useEffect, useMemo, useState } from "react";
import {
  createEngineeringObject,
  createEngineeringRelation,
  commitEngineeringImport,
  approveAllValidEngineeringProposals,
  approveEngineeringProposal,
  deleteEngineeringObject,
  deleteEngineeringRelation,
  getEngineeringSchema,
  listEngineeringProposals,
  listEngineeringObjects,
  listEngineeringRelations,
  previewEngineeringImport,
  rejectEngineeringProposal,
  RESOURCE_LABELS,
  RESOURCE_TO_OBJECT_TYPE,
  updateEngineeringObject,
  updateEngineeringProposal,
  validateEngineeringProposal,
} from "@/lib/engineering-api";
import type {
  EngineeringObject,
  EngineeringProposal,
  EngineeringImportPlan,
  EngineeringImportResult,
  EngineeringRelation,
  EngineeringResource,
  EngineeringSchema,
} from "@/lib/types";
import { setWorkflowContext } from "@/lib/workflow-api";

const RESOURCES: EngineeringResource[] = [
  "hardware-nodes",
  "functions",
  "interfaces",
  "messages",
  "signals",
];

const HARDWARE_PRESETS = [
  { label: "ECU", deviceType: "ECU" },
  { label: "Gateway", deviceType: "Gateway" },
  { label: "Sensor", deviceType: "SensorController" },
] as const;

const REQUIREMENT_FIELDS = [
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
      return [item.name, "device_type" in item ? item.device_type : "—", item.domain ?? "—"];
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
  const [showImport, setShowImport] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    getEngineeringSchema()
      .then(setSchema)
      .catch((err) => setError(err instanceof Error ? err.message : "Schema konnte nicht geladen werden."));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    Promise.all([
      listEngineeringObjects(resource),
      Promise.all(RESOURCE_REFERENCES[resource].map((reference) => listEngineeringObjects(reference))),
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
  }, [resource]);

  const selected = useMemo(() => items.find((item) => item.id === selectedId) ?? null, [items, selectedId]);

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
      <div className="panel error-card">
        <p className="eyebrow">Engineering-API nicht erreichbar</p>
        <h2>{error}</h2>
        <p className="muted">Prüfe Backend und Datenbankverbindung oder versuche es erneut.</p>
        <button className="button secondary" onClick={refresh} type="button">
          Erneut prüfen
        </button>
      </div>
    );
  }

  return (
    <>
    <div className="workspace-grid">
      <div className="panel config-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Kanonisches Modell</p>
            <h2>{RESOURCE_LABELS[resource]}</h2>
          </div>
          <div className="panel-heading-actions">
            <button className="button secondary" onClick={() => setShowImport(true)} type="button">
              Importieren
            </button>
            <button
              className="button primary"
              onClick={() => {
                setHardwarePreset(null);
                setShowCreate((value) => !value);
              }}
              type="button"
            >
              {showCreate ? "Abbrechen" : "+ Neu anlegen"}
            </button>
          </div>
        </div>

        <div className="eng-resource-tabs eng-resource-flow" role="tablist" aria-label="Objekthierarchie">
          {RESOURCES.map((res, index) => (
            <Fragment key={res}>
              <button
                aria-selected={resource === res}
                className={resource === res ? "active" : ""}
                onClick={() => {
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
        </div>

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
        ) : items.length === 0 ? (
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
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    className={item.id === selectedId ? "selected" : ""}
                    key={item.id}
                    onClick={() => setSelectedId(item.id)}
                  >
                    {resourceTableValues(resource, item, referenceNames).map((value, index) => (
                      <td className={index === 0 ? undefined : "muted"} key={`${item.id}:${index}`}>
                        {value}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <aside className="side-column">
        {selected ? (
          <DetailPanel
            item={selected}
            resource={resource}
            relations={relations}
            schema={schema}
            onChanged={refresh}
            onDeleted={() => {
              setSelectedId(null);
              refresh();
            }}
          />
        ) : (
          <div className="panel overview-panel">
            <p className="eyebrow">Detailansicht</p>
            <h2>Kein Objekt gewählt</h2>
            <p className="muted" style={{ marginTop: 12, fontSize: 12 }}>
              Wähle ein Objekt aus der Liste, um Details, Governance-Status und
              Relations zu sehen.
            </p>
          </div>
        )}
      </aside>
    </div>
    {showImport && (
      <ImportWizard
        onClose={() => setShowImport(false)}
        onImported={() => {
          refresh();
        }}
      />
    )}
    <ProposalReviewPanel />
    </>
  );
}

function ProposalReviewPanel() {
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
  }, []);

  async function act(key: string, action: () => Promise<unknown>, message: string) {
    setBusy(key);
    setNotice("");
    try {
      await action();
      setNotice(message);
      await refresh();
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

  const open = proposals.filter((proposal) => !["APPROVED", "REJECTED", "SUPERSEDED"].includes(proposal.status));
  const wizardProposal = wizard ? proposals.find((proposal) => proposal.proposal_id === wizard.proposalId) : undefined;

  return (
    <section className="panel eng-proposal-review">
      <div className="panel-heading">
        <div><p className="eyebrow">Human Review</p><h2>KI-Engineering-Vorschläge</h2></div>
        <div className="panel-heading-actions">
          <span className="status-badge">{open.length} offen</span>
          <button className="button secondary tiny" disabled={!open.length || Boolean(busy)} onClick={() => void act("approve-all", approveAllValidEngineeringProposals, "Alle validen Vorschlaege freigegeben.")} type="button">Alle validen freigeben</button>
        </div>
      </div>
      {notice && <div className="notice">{notice}</div>}
      {!proposals.length ? (
        <div className="eng-proposal-empty">Keine KI-Vorschläge zur Prüfung.</div>
      ) : (
        <div className="eng-proposal-list">
          {proposals.map((proposal) => {
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
                      <div className="eng-proposal-object" key={`${proposal.proposal_id}:${index}`}>
                        {editing ? (
                          <div className="eng-proposal-fields">
                            <label>Name<input defaultValue={String(item.name ?? "")} name={`name-${index}`} /></label>
                            <label>Domäne<input defaultValue={String(item.domain ?? "")} name={`domain-${index}`} /></label>
                            <label>Beschreibung<input defaultValue={String(item.description ?? "")} name={`description-${index}`} /></label>
                          </div>
                        ) : (
                          <div><strong>{String(item.name ?? item.relation_type ?? `Objekt ${index + 1}`)}</strong><span>{String(item.object_type ?? proposal.proposal_type)} · {String(item.domain ?? "generic")}</span></div>
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
    </section>
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
      listEngineeringObjects("hardware-nodes"),
      listEngineeringObjects("functions"),
      listEngineeringObjects("interfaces"),
      listEngineeringObjects("messages"),
      listEngineeringObjects("signals"),
    ])
      .then(([nextSchema, hardwareNodes, functions, interfaces, messages, signals]) => {
        if (cancelled) return;
        setSchema(nextSchema);
        setReferences({ "hardware-nodes": hardwareNodes, functions, interfaces, messages, signals });
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
                  {(schema?.device_types ?? ["ECU"]).map((type) => <option key={type} value={type}>{type}</option>)}
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

const IMPORT_COUNT_LABELS: Array<[keyof EngineeringImportPlan["counts"], string]> = [
  ["hardware_nodes", "Hardware"],
  ["functions", "Funktionen"],
  ["interfaces", "Interfaces"],
  ["messages", "Nachrichten"],
  ["signals", "Signale"],
];

function ImportWizard({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const [plan, setPlan] = useState<EngineeringImportPlan | null>(null);
  const [result, setResult] = useState<EngineeringImportResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");

  async function chooseFile(file: File | undefined) {
    if (!file) return;
    setAnalyzing(true);
    setError("");
    setPlan(null);
    setResult(null);
    try {
      setPlan(await previewEngineeringImport(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Datei konnte nicht analysiert werden.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function runImport() {
    if (!plan) return;
    setImporting(true);
    setError("");
    try {
      const nextResult = await commitEngineeringImport(plan);
      setResult(nextResult);
      onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import fehlgeschlagen.");
    } finally {
      setImporting(false);
    }
  }

  const step = result ? 3 : plan ? 2 : 1;

  return (
    <div className="eng-import-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section aria-labelledby="import-title" aria-modal="true" className="eng-import-dialog" role="dialog">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Engineering-Import</p>
            <h2 id="import-title">Import-Wizard</h2>
          </div>
          <button aria-label="Import schließen" className="eng-dialog-close" onClick={onClose} type="button">×</button>
        </div>

        <div aria-label="Importschritte" className="eng-import-steps">
          {["Datei", "Vorschau", "Import"].map((label, index) => (
            <span className={step >= index + 1 ? "active" : ""} key={label}>
              {index + 1} {label}
            </span>
          ))}
        </div>

        {!plan && !result && (
          <label className="eng-import-dropzone">
            <input
              accept=".dbc,.csv,.xlsx"
              disabled={analyzing}
              onChange={(event) => void chooseFile(event.target.files?.[0])}
              type="file"
            />
            <strong>{analyzing ? "Datei wird analysiert …" : "Datei auswählen"}</strong>
            <span>DBC, CSV oder XLSX</span>
          </label>
        )}

        {plan && !result && (
          <>
            <div className="eng-import-file">
              <div>
                <span>{plan.format.toUpperCase()}</span>
                <strong>{plan.file_name}</strong>
              </div>
              <button className="button secondary tiny" onClick={() => setPlan(null)} type="button">
                Andere Datei
              </button>
            </div>
            <div className="eng-import-counts">
              {IMPORT_COUNT_LABELS.map(([key, label]) => (
                <div key={key}>
                  <strong>{plan.counts[key]}</strong>
                  <span>{label}</span>
                </div>
              ))}
            </div>
            {Object.keys(plan.mapping).length > 0 && (
              <div className="eng-import-mapping">
                <p className="eyebrow">Erkannte Zuordnung</p>
                <dl>
                  {Object.entries(plan.mapping).map(([field, column]) => (
                    <div key={field}>
                      <dt>{column}</dt>
                      <dd>{field}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}
            {plan.warnings.length > 0 && (
              <ul className="eng-import-warnings">
                {plan.warnings.map((warning) => <li key={warning}>{warning}</li>)}
              </ul>
            )}
          </>
        )}

        {result && (
          <div className="eng-import-result">
            <span className="status-badge completed">Import abgeschlossen</span>
            <strong>{result.created} Objekte angelegt</strong>
            <p>{result.reused} bereits vorhandene Objekte wurden wiederverwendet.</p>
          </div>
        )}

        {error && <div className="notice error">{error}</div>}

        <div className="form-actions">
          <button className="button secondary" onClick={onClose} type="button">
            {result ? "Schließen" : "Abbrechen"}
          </button>
          {plan && !result && (
            <button className="button primary" disabled={importing} onClick={() => void runImport()} type="button">
              {importing ? "Wird importiert …" : "Import bestätigen"}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

function CreateForm({
  hardwarePreset,
  resource,
  schema,
  onCreated,
}: {
  hardwarePreset: string | null;
  resource: EngineeringResource;
  schema: EngineeringSchema | null;
  onCreated: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [deviceType, setDeviceType] = useState(
    hardwarePreset ?? schema?.device_types[0] ?? "ECU",
  );
  const [parents, setParents] = useState<EngineeringObject[]>([]);
  const [parentId, setParentId] = useState("");
  const [loadingParents, setLoadingParents] = useState(false);
  const hierarchy = RESOURCE_HIERARCHY[resource];

  useEffect(() => {
    if (!hierarchy) {
      setParents([]);
      setParentId("");
      return;
    }
    let cancelled = false;
    setLoadingParents(true);
    listEngineeringObjects(hierarchy.parentResource)
      .then((items) => {
        if (cancelled) return;
        setParents(items);
        setParentId(items[0]?.id ?? "");
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setFormError("");
    const form = new FormData(event.currentTarget);
    const payload: Record<string, unknown> = {
      name: form.get("name"),
      description: form.get("description") || null,
      domain: form.get("domain") || null,
    };
    const parent = parents.find((item) => item.id === parentId);
    if (hierarchy && !parent) {
      setFormError(`Wähle zuerst eine übergeordnete ${hierarchy.parentLabel}.`);
      setSubmitting(false);
      return;
    }
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
      payload.cycle_ms = form.get("cycle_ms") ? Number(form.get("cycle_ms")) : null;
      payload.dlc = form.get("dlc") ? Number(form.get("dlc")) : null;
      payload.configuration = requirementPayload(form, "requirement_");
    }
    if (resource === "signals") {
      payload.message_id = parentId;
      payload.display_name = form.get("display_name") || null;
      payload.start_bit = form.get("start_bit") ? Number(form.get("start_bit")) : null;
      payload.length_bits = form.get("length_bits") ? Number(form.get("length_bits")) : null;
      payload.communication = requirementPayload(form, "requirement_");
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
    <form className="eng-create-form" onSubmit={submit}>
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
      <div className="form-grid">
        <div className="field">
          <label htmlFor="name">Name</label>
          <input
            autoFocus
            id="name"
            name="name"
            placeholder={hardwarePreset ? `${HARDWARE_PRESETS.find((item) => item.deviceType === hardwarePreset)?.label} Name` : undefined}
            required
            type="text"
          />
        </div>
        <div className="field">
          <label htmlFor="domain">Domäne</label>
          <input id="domain" name="domain" type="text" placeholder="z. B. automotive" />
        </div>
      </div>

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
                {type}
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
        </div>
        <RequirementFields prefix="requirement_" />
        </>
      )}

      <div className="field full-width">
        <label htmlFor="description">Beschreibung</label>
        <textarea id="description" name="description" rows={2} />
      </div>

      {formError && <div className="notice error">{formError}</div>}

      <div className="form-actions">
        <button
          className="button primary"
          disabled={submitting || Boolean(hierarchy && (loadingParents || !parentId))}
          type="submit"
        >
          {submitting ? "Wird angelegt …" : "Anlegen"}
        </button>
      </div>
    </form>
  );
}

function DetailPanel({
  item,
  resource,
  relations,
  schema,
  onChanged,
  onDeleted,
}: {
  item: EngineeringObject;
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
    <>
      <div className="panel overview-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">{RESOURCE_TO_OBJECT_TYPE[resource]}</p>
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

      <div className="panel overview-panel">
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
            {relations.map((relation) => (
              <li key={relation.id}>
                <span className="tag">{relation.relation_type}</span>
                <span className="mono muted" style={{ fontSize: 11 }}>
                  {relation.source_type}:{relation.source_id.slice(0, 8)} →{" "}
                  {relation.target_type}:{relation.target_id.slice(0, 8)}
                </span>
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
            ))}
          </ul>
        )}
      </div>
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
            {(schema?.device_types ?? [item.device_type]).map((type) => <option key={type}>{type}</option>)}
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
        <div className="form-grid three">
          <div className="field"><label htmlFor="edit_display_name">Anzeigename</label><input defaultValue={item.display_name ?? ""} id="edit_display_name" name="edit_display_name" type="text" /></div>
          <div className="field"><label htmlFor="edit_start_bit">Start-Bit</label><input defaultValue={item.start_bit ?? ""} id="edit_start_bit" min="0" name="edit_start_bit" type="number" /></div>
          <div className="field"><label htmlFor="edit_length_bits">Länge (Bit)</label><input defaultValue={item.length_bits ?? ""} id="edit_length_bits" min="1" name="edit_length_bits" type="number" /></div>
          <div className="field"><label htmlFor="edit_byte_order">Byte-Reihenfolge</label><select defaultValue={item.byte_order ?? ""} id="edit_byte_order" name="edit_byte_order"><option value="">—</option><option value="little_endian">little_endian</option><option value="big_endian">big_endian</option></select></div>
          <div className="field"><label htmlFor="edit_data_type">Datentyp</label><input defaultValue={item.data_type ?? ""} id="edit_data_type" name="edit_data_type" type="text" /></div>
          <div className="field"><label htmlFor="edit_unit">Einheit</label><input defaultValue={item.unit ?? ""} id="edit_unit" name="edit_unit" type="text" /></div>
          <div className="field"><label htmlFor="edit_factor">Faktor</label><input defaultValue={item.factor ?? ""} id="edit_factor" name="edit_factor" step="any" type="number" /></div>
          <div className="field"><label htmlFor="edit_offset_value">Offset</label><input defaultValue={item.offset_value ?? ""} id="edit_offset_value" name="edit_offset_value" step="any" type="number" /></div>
          <div className="field"><label htmlFor="edit_min_value">Minimum</label><input defaultValue={item.min_value ?? ""} id="edit_min_value" name="edit_min_value" step="any" type="number" /></div>
          <div className="field"><label htmlFor="edit_max_value">Maximum</label><input defaultValue={item.max_value ?? ""} id="edit_max_value" name="edit_max_value" step="any" type="number" /></div>
        </div>
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
