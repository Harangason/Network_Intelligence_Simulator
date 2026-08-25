"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createEngineeringObject,
  createEngineeringRelation,
  deleteEngineeringObject,
  deleteEngineeringRelation,
  getEngineeringSchema,
  listEngineeringObjects,
  listEngineeringRelations,
  RESOURCE_LABELS,
  RESOURCE_TO_OBJECT_TYPE,
  updateEngineeringObject,
} from "@/lib/engineering-api";
import type {
  EngineeringObject,
  EngineeringRelation,
  EngineeringResource,
  EngineeringSchema,
} from "@/lib/types";

const RESOURCES: EngineeringResource[] = [
  "hardware-nodes",
  "functions",
  "interfaces",
  "messages",
  "signals",
];

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
];

export function EngineeringWorkbench() {
  const [resource, setResource] = useState<EngineeringResource>("hardware-nodes");
  const [schema, setSchema] = useState<EngineeringSchema | null>(null);
  const [items, setItems] = useState<EngineeringObject[]>([]);
  const [relations, setRelations] = useState<EngineeringRelation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    getEngineeringSchema()
      .then(setSchema)
      .catch((err) => setError(err instanceof Error ? err.message : "Schema konnte nicht geladen werden."));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    setSelectedId(null);
    listEngineeringObjects(resource)
      .then(setItems)
      .catch((err) => setError(err instanceof Error ? err.message : "Backend nicht erreichbar."))
      .finally(() => setLoading(false));
  }, [resource, refreshKey]);

  const selected = useMemo(() => items.find((item) => item.id === selectedId) ?? null, [items, selectedId]);

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
        <p className="muted">Starte die Anwendung mit dem gemeinsamen Web-Launcher.</p>
      </div>
    );
  }

  return (
    <div className="workspace-grid">
      <div className="panel config-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Kanonisches Modell</p>
            <h2>{RESOURCE_LABELS[resource]}</h2>
          </div>
          <button className="button primary" onClick={() => setShowCreate((value) => !value)} type="button">
            {showCreate ? "Abbrechen" : "+ Neu anlegen"}
          </button>
        </div>

        <div className="eng-resource-tabs" role="tablist" aria-label="Objekttyp">
          {RESOURCES.map((res) => (
            <button
              aria-selected={resource === res}
              className={resource === res ? "active" : ""}
              key={res}
              onClick={() => {
                setResource(res);
                setShowCreate(false);
              }}
              role="tab"
              type="button"
            >
              {RESOURCE_LABELS[res]}
            </button>
          ))}
        </div>

        {showCreate && (
          <CreateForm
            resource={resource}
            schema={schema}
            onCreated={() => {
              setShowCreate(false);
              refresh();
            }}
          />
        )}

        {loading ? (
          <div className="loading-panel">Lädt …</div>
        ) : items.length === 0 ? (
          <div className="empty-result">
            <span className="empty-icon">⌁</span>
            <strong>Keine Objekte vorhanden</strong>
            <p>Lege das erste {RESOURCE_LABELS[resource]}-Objekt an.</p>
          </div>
        ) : (
          <table className="eng-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Domäne</th>
                <th>Lifecycle</th>
                <th>Review</th>
                <th>Version</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  className={item.id === selectedId ? "selected" : ""}
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                >
                  <td>{item.name}</td>
                  <td className="muted">{item.domain ?? "—"}</td>
                  <td>
                    <span className={`status-badge ${item.lifecycle_state === "active" ? "completed" : ""}`}>
                      {item.lifecycle_state}
                    </span>
                  </td>
                  <td className="muted">{item.review_state}</td>
                  <td className="mono muted">v{item.version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <aside className="side-column">
        {selected ? (
          <DetailPanel
            item={selected}
            resource={resource}
            relations={relations}
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
  );
}

function CreateForm({
  resource,
  schema,
  onCreated,
}: {
  resource: EngineeringResource;
  schema: EngineeringSchema | null;
  onCreated: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

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
    if (resource === "hardware-nodes") payload.device_type = form.get("device_type");
    if (resource === "interfaces") payload.interface_type = form.get("interface_type");
    if (resource === "messages") {
      payload.message_id_hex = form.get("message_id_hex") || null;
      payload.direction = form.get("direction") || null;
    }
    if (resource === "signals") {
      payload.display_name = form.get("display_name") || null;
      payload.start_bit = form.get("start_bit") ? Number(form.get("start_bit")) : null;
      payload.length_bits = form.get("length_bits") ? Number(form.get("length_bits")) : null;
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
      <div className="form-grid">
        <div className="field">
          <label htmlFor="name">Name</label>
          <input id="name" name="name" required type="text" />
        </div>
        <div className="field">
          <label htmlFor="domain">Domäne</label>
          <input id="domain" name="domain" type="text" placeholder="z. B. automotive" />
        </div>
      </div>

      {resource === "hardware-nodes" && (
        <div className="field">
          <label htmlFor="device_type">Gerätetyp</label>
          <select id="device_type" name="device_type" required>
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
        </div>
      )}

      {resource === "signals" && (
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
      )}

      <div className="field full-width">
        <label htmlFor="description">Beschreibung</label>
        <textarea id="description" name="description" rows={2} />
      </div>

      {formError && <div className="notice error">{formError}</div>}

      <div className="form-actions">
        <button className="button primary" disabled={submitting} type="submit">
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
  onChanged,
  onDeleted,
}: {
  item: EngineeringObject;
  resource: EngineeringResource;
  relations: EngineeringRelation[];
  onChanged: () => void;
  onDeleted: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [showRelationForm, setShowRelationForm] = useState(false);

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
        <p className="eyebrow">{RESOURCE_TO_OBJECT_TYPE[resource]}</p>
        <h2>{item.name}</h2>
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
