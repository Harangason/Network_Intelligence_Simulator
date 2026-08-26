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

  const open = proposals.filter((proposal) => !["APPROVED", "REJECTED", "SUPERSEDED"].includes(proposal.status));

  return (
    <section className="panel eng-proposal-review">
      <div className="panel-heading">
        <div><p className="eyebrow">Human Review</p><h2>KI-Engineering-Vorschläge</h2></div>
        <div className="panel-heading-actions">
          <span className="status-badge">{open.length} offen</span>
          <button className="button secondary" disabled={!open.length || Boolean(busy)} onClick={() => void act("approve-all", approveAllValidEngineeringProposals, "Alle validen Vorschlaege freigegeben.")} type="button">Approve All Valid</button>
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
                          {item.canonical_id ? <span className="status-badge approved">Freigegeben</span> : <button disabled={!validation?.valid || Boolean(busy)} onClick={() => void act(`approve:${proposal.proposal_id}:${index}`, () => approveEngineeringProposal(proposal.proposal_id, [index]), "Objekt freigegeben und versioniert gespeichert.")} type="button">Freigeben</button>}
                        </div>
                        {validation?.errors.map((error) => <small className="routing-issue error" key={error}>{error}</small>)}
                      </div>
                    );
                  })}
                </div>
                <footer>
                  <span>Evidence {proposal.evidence.length} · {proposal.model ?? "Modell nicht angegeben"}</span>
                  <div>
                    {editing ? <><button onClick={() => setEditingId(null)} type="button">Abbrechen</button><button disabled={Boolean(busy)} type="submit">Speichern</button></> : <button disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => setEditingId(proposal.proposal_id)} type="button">Bearbeiten</button>}
                    <button disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => void act(`validate:${proposal.proposal_id}`, () => validateEngineeringProposal(proposal.proposal_id), "Vorschlag validiert.")} type="button">Validieren</button>
                    <button disabled={proposal.status === "APPROVED" || Boolean(busy)} onClick={() => void act(`reject:${proposal.proposal_id}`, () => rejectEngineeringProposal(proposal.proposal_id), "Vorschlag abgelehnt.")} type="button">Ablehnen</button>
                  </div>
                </footer>
              </form>
            );
          })}
        </div>
      )}
    </section>
  );
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
