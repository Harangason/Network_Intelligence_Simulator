"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listAllEngineeringObjects } from "@/lib/engineering-api";
import {
  acceptRoutingProposal,
  approveRoutes,
  createRoute,
  deleteRoute,
  generateRoutes,
  getRoutingSchema,
  importRoutes,
  listRoutes,
  listRoutingProposals,
  rejectRoutes,
  updateRoute,
  validateRoute,
} from "@/lib/routing-api";
import type {
  EngInterface,
  EngMessage,
  EngSignal,
  HardwareNode,
  RoutingEntry,
  RoutingProposal,
  RoutingSchema,
} from "@/lib/types";
import { setWorkflowContext } from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";

const VIEWS = ["Table", "Network Proposals", "Graph", "Matrix", "AI Proposals", "Validation", "Conflicts"] as const;
type RoutingView = (typeof VIEWS)[number];

const isHardware = (item: object): item is HardwareNode => "device_type" in item;
const isInterface = (item: object): item is EngInterface => "interface_type" in item;
const isMessage = (item: object): item is EngMessage => "interface_id" in item && "message_id_hex" in item;
const isSignal = (item: object): item is EngSignal => "message_id" in item && "length_bits" in item;

export function RoutingWorkbench({ initialView = "Table" }: { initialView?: RoutingView }) {
  const [routes, setRoutes] = useState<RoutingEntry[]>([]);
  const [proposals, setProposals] = useState<RoutingProposal[]>([]);
  const [schema, setSchema] = useState<RoutingSchema | null>(null);
  const [hardware, setHardware] = useState<HardwareNode[]>([]);
  const [interfaces, setInterfaces] = useState<EngInterface[]>([]);
  const [messages, setMessages] = useState<EngMessage[]>([]);
  const [signals, setSignals] = useState<EngSignal[]>([]);
  const [view, setView] = useState<RoutingView>(initialView);
  const [selected, setSelected] = useState<RoutingEntry | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [editor, setEditor] = useState<{ mode: "manual" | "ai"; route?: RoutingEntry } | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const importInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const [routeItems, proposalItems, routingSchema, nodeItems, interfaceItems, messageItems, signalItems] =
      await Promise.all([
        listRoutes(),
        listRoutingProposals(),
        getRoutingSchema(),
        listAllEngineeringObjects("hardware-nodes"),
        listAllEngineeringObjects("interfaces"),
        listAllEngineeringObjects("messages"),
        listAllEngineeringObjects("signals"),
      ]);
    setRoutes(routeItems);
    setProposals(proposalItems);
    setSchema(routingSchema);
    setHardware(nodeItems.filter(isHardware));
    setInterfaces(interfaceItems.filter(isInterface));
    setMessages(messageItems.filter(isMessage));
    setSignals(signalItems.filter(isSignal));
    setSelected((current) => routeItems.find((item) => item.id === current?.id) ?? routeItems[0] ?? null);
  }, []);

  useEffect(() => {
    refresh().catch((error) => setNotice({ type: "error", text: error instanceof Error ? error.message : "Routing konnte nicht geladen werden." }));
  }, [refresh]);

  useEffect(() => {
    void setWorkflowContext({ selected_route: selected?.id ?? null }).catch(() => undefined);
  }, [selected]);

  const nodeNames = useMemo(() => new Map(hardware.map((node) => [node.id, node.name])), [hardware]);
  const messageNames = useMemo(() => new Map(messages.map((message) => [message.id, message.name])), [messages]);
  const signalNames = useMemo(() => new Map(signals.map((signal) => [signal.id, signal.display_name || signal.name])), [signals]);
  const interfaceNetworks = useMemo(() => new Map(interfaces.map((item) => [
    item.id,
    String(item.configuration.network_id ?? item.configuration.network ?? "—"),
  ])), [interfaces]);
  const interfaceNames = useMemo(() => new Map(interfaces.map((item) => [item.id, item.name])), [interfaces]);
  const validCount = routes.filter((route) => route.validation?.valid).length;
  const approvedCount = routes.filter((route) => route.approval_state === "APPROVED").length;
  const conflictCount = routes.filter((route) => route.validation?.valid === false || route.status === "CONFLICT").length;
  const networkProposals = useMemo(
    () => routes.filter(
      (route) => route.origin === "NETWORK_EDITOR" && route.approval_state === "PENDING" && route.status !== "OUTDATED",
    ),
    [routes],
  );
  const confirmableNetworkProposals = networkProposals.filter((route) => route.validation?.valid);

  useEffect(() => {
    if (view !== "Network Proposals") return;
    setSelected((current) =>
      current && networkProposals.some((route) => route.id === current.id)
        ? current
        : networkProposals[0] ?? null,
    );
  }, [networkProposals, view]);

  async function act(label: string, operation: () => Promise<unknown>, success: string) {
    setBusy(label);
    setNotice(null);
    try {
      await operation();
      await refresh();
      notifyWorkflowChanged();
      setChecked(new Set());
      setNotice({ type: "success", text: success });
    } catch (error) {
      setNotice({ type: "error", text: error instanceof Error ? error.message : "Routing-Aktion fehlgeschlagen." });
    } finally {
      setBusy("");
    }
  }

  function toggleChecked(routeId: string) {
    setChecked((current) => {
      const next = new Set(current);
      if (next.has(routeId)) next.delete(routeId);
      else next.add(routeId);
      return next;
    });
  }

  async function handleImport(file: File | undefined) {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      const imported = Array.isArray(parsed) ? parsed : parsed.routes;
      if (!Array.isArray(imported)) throw new Error("Die JSON-Datei muss eine Route-Liste enthalten.");
      await act("import", () => importRoutes(imported), `${imported.length} Routingdefinitionen importiert.`);
    } catch (error) {
      setNotice({ type: "error", text: error instanceof Error ? error.message : "Import fehlgeschlagen." });
    } finally {
      if (importInput.current) importInput.current.value = "";
    }
  }

  return (
    <>
      <div className="routing-summary" aria-label="Routing-Kennzahlen">
        <div><span>Routen</span><strong>{routes.length}</strong></div>
        <div><span>Valide</span><strong>{validCount}</strong></div>
        <div><span>Freigegeben</span><strong>{approvedCount}</strong></div>
        <div><span>Konflikte</span><strong>{conflictCount}</strong></div>
      </div>

      <div className="routing-commandbar">
        <div className="routing-primary-actions">
          <button className="button primary" onClick={() => setEditor({ mode: "manual" })} type="button">+ Route</button>
          <button className="button secondary" onClick={() => setEditor({ mode: "ai" })} type="button">AI Generate</button>
          <button className="button secondary" onClick={() => importInput.current?.click()} type="button">Import</button>
          <input accept="application/json,.json" hidden onChange={(event) => void handleImport(event.target.files?.[0])} ref={importInput} type="file" />
        </div>
        <Link className={`button secondary ${approvedCount === 0 ? "disabled" : ""}`} href={approvedCount ? "/studio?mode=network" : "/studio/routing"}>
          Weiter zum Netzwerk-Editor →
        </Link>
      </div>

      <div className="routing-view-tabs" role="tablist" aria-label="Routing-Ansicht">
        {VIEWS.map((item) => (
          <button
            aria-selected={view === item}
            className={view === item ? "active" : ""}
            key={item}
            onClick={() => {
              setView(item);
              if (item === "Network Proposals") setSelected(networkProposals[0] ?? null);
            }}
            role="tab"
            type="button"
          >
            {item}
            {item === "AI Proposals" && proposals.length > 0 ? <span>{proposals.length}</span> : null}
            {item === "Network Proposals" && networkProposals.length > 0 ? <span>{networkProposals.length}</span> : null}
          </button>
        ))}
      </div>

      {notice && <div className={`notice ${notice.type}`}>{notice.text}</div>}

      <div className="routing-workspace">
        <section className="panel routing-main-panel">
          {(view === "Table" || view === "Network Proposals") && (
            <RoutingTable
              checked={checked}
              interfaceNames={interfaceNames}
              interfaceNetworks={interfaceNetworks}
              messageNames={messageNames}
              nodeNames={nodeNames}
              onCheck={toggleChecked}
              onDelete={(route) => void act("delete", () => deleteRoute(route.id), `${route.route_code} gelöscht.`)}
              onDuplicate={(route) => void act("duplicate", () => createRoute({
                ...route,
                id: undefined,
                route_code: undefined,
                name: `${route.name} Kopie`,
                status: "DRAFT",
                origin: "DERIVED",
                approval_state: "PENDING",
                validation: {},
                actor: "routing-ui",
              }), "Route dupliziert.")}
              onEdit={(route) => setEditor({ mode: "manual", route })}
              onApprove={(route) => void act("approve", () => approveRoutes([route.id]), `${route.route_code} bestätigt.`)}
              onReject={(route) => void act("reject", () => rejectRoutes([route.id], "Im Routing Manager abgelehnt."), `${route.route_code} abgelehnt.`)}
              onSelect={setSelected}
              onValidate={(route) => void act("validate", () => validateRoute(route.id), `${route.route_code} validiert.`)}
              routes={view === "Network Proposals" ? networkProposals : routes}
              selectedId={selected?.id}
              signalNames={signalNames}
            />
          )}
          {view === "Graph" && <RoutingGraph nodeNames={nodeNames} onSelect={setSelected} routes={routes} signalNames={signalNames} />}
          {view === "Matrix" && <RoutingMatrix nodeNames={nodeNames} onSelect={setSelected} routes={routes} />}
          {view === "AI Proposals" && (
            <RoutingProposals
              nodeNames={nodeNames}
              onAccept={(proposal, index) => void act("accept", () => acceptRoutingProposal(proposal.proposal_id, [index]), "Vorschlag als Draft übernommen.")}
              proposals={proposals}
            />
          )}
          {view === "Validation" && <RoutingValidationList onSelect={setSelected} routes={routes} />}
          {view === "Conflicts" && <RoutingValidationList conflicts onSelect={setSelected} routes={routes} />}
        </section>

        <aside className="routing-side-column">
          <RoutingDetail
            interfaceNames={interfaceNames}
            interfaceNetworks={interfaceNetworks}
            messageNames={messageNames}
            nodeNames={nodeNames}
            route={selected}
            signalNames={signalNames}
          />
          <div className="panel routing-governance">
            <p className="eyebrow">Governance</p>
            <div className="routing-bulk-actions">
              <button disabled={checked.size === 0 || Boolean(busy)} onClick={() => void act("validate-selected", () => Promise.all([...checked].map(validateRoute)), "Auswahl validiert.")} type="button">Validate Selected</button>
              <button disabled={checked.size === 0 || Boolean(busy)} onClick={() => void act("approve-selected", () => approveRoutes([...checked]), "Valide Auswahl bestätigt.")} type="button">Confirm Selected</button>
              <button disabled={checked.size === 0 || Boolean(busy)} onClick={() => void act("reject-selected", () => rejectRoutes([...checked], "Rejected in routing review"), "Auswahl abgelehnt.")} type="button">Reject Selected</button>
              <button disabled={confirmableNetworkProposals.length === 0 || Boolean(busy)} onClick={() => void act("approve-all", () => approveRoutes(confirmableNetworkProposals.map((route) => route.id)), "Alle validen Netzwerk-Vorschläge bestätigt.")} type="button">Confirm All Valid</button>
            </div>
            <p className="routing-permission-note">AI: READ · GENERATE · VALIDATE<br />Freigabe bleibt beim Menschen.</p>
          </div>
        </aside>
      </div>

      {editor && schema && (
        <RoutingEditorDialog
          hardware={hardware}
          interfaces={interfaces}
          messages={messages}
          mode={editor.mode}
          onClose={() => setEditor(null)}
          onGenerate={(payload) => act("generate", () => generateRoutes(payload), "RoutingProposal erzeugt.").then(() => setEditor(null))}
          onSave={(payload) => act("save", () => editor.route ? updateRoute(editor.route.id, payload) : createRoute(payload), editor.route ? "Neue Routing-Revision gespeichert." : "Route als Draft gespeichert.").then(() => setEditor(null))}
          route={editor.route}
          schema={schema}
          signals={signals}
        />
      )}
    </>
  );
}

function RoutingTable({ routes, checked, selectedId, nodeNames, messageNames, signalNames, interfaceNames, interfaceNetworks, onCheck, onSelect, onEdit, onValidate, onApprove, onReject, onDuplicate, onDelete }: {
  routes: RoutingEntry[];
  checked: Set<string>;
  selectedId?: string;
  nodeNames: Map<string, string>;
  messageNames: Map<string, string>;
  signalNames: Map<string, string>;
  interfaceNames: Map<string, string>;
  interfaceNetworks: Map<string, string>;
  onCheck: (id: string) => void;
  onSelect: (route: RoutingEntry) => void;
  onEdit: (route: RoutingEntry) => void;
  onValidate: (route: RoutingEntry) => void;
  onApprove: (route: RoutingEntry) => void;
  onReject: (route: RoutingEntry) => void;
  onDuplicate: (route: RoutingEntry) => void;
  onDelete: (route: RoutingEntry) => void;
}) {
  if (routes.length === 0) return <EmptyRouting text="Noch keine Routingdefinition vorhanden." />;
  return (
    <div className="routing-table-wrap">
      <table className="routing-table">
        <thead><tr><th>Select</th><th>Route ID</th><th>Producer</th><th>Source Interface</th><th>Payload</th><th>Message</th><th>Signals</th><th>Network</th><th>Gateway</th><th>Consumer</th><th>Destination Interface</th><th>Protocol</th><th>Cycle</th><th>Latency</th><th>Origin</th><th>Confidence</th><th>Validation</th><th>Approval</th><th>Actions</th></tr></thead>
        <tbody>{routes.map((route) => (
          <tr className={selectedId === route.id ? "selected" : ""} key={route.id} onClick={() => onSelect(route)}>
            <td><input aria-label={`${route.route_code} auswählen`} checked={checked.has(route.id)} onChange={() => onCheck(route.id)} onClick={(event) => event.stopPropagation()} type="checkbox" /></td>
            <td><strong>{route.route_code}</strong><span>r{route.revision}</span></td>
            <td>{nodeNames.get(route.source.node_id) ?? route.source.node_id}</td>
            <td>{interfaceNames.get(route.source.interface_id ?? "") ?? route.source.interface_id ?? "—"}</td>
            <td>{route.payload.topic ?? route.payload.data_object ?? route.payload.interface_definition_id ?? "Message"}</td>
            <td>{messageNames.get(route.payload.message_id ?? "") ?? "—"}</td>
            <td>{route.payload.signal_ids.slice(0, 2).map((id) => signalNames.get(id) ?? id).join(", ") || "—"}</td>
            <td>{route.source.network_id ?? interfaceNetworks.get(route.source.interface_id ?? "") ?? "—"}</td>
            <td>{route.route.gateways.map((item) => typeof item === "string" ? nodeNames.get(item) ?? item : item.name ?? nodeNames.get(item.node_id ?? "")).join(", ") || "—"}</td>
            <td>{route.destinations.map((item) => nodeNames.get(item.node_id) ?? item.node_id).join(", ")}</td>
            <td>{route.destinations.map((item) => interfaceNames.get(item.interface_id ?? "") ?? item.interface_id ?? "—").join(", ")}</td>
            <td>{route.source.protocol ?? "—"}</td><td>{route.timing.cycle_time_ms ?? "—"} ms</td><td>{route.timing.max_latency_ms ?? "—"} ms</td>
            <td>{route.origin === "NETWORK_EDITOR" ? <span className="routing-network-origin">Proposed from Network Editor</span> : route.origin}</td><td>{route.confidence == null ? "—" : `${Math.round(route.confidence * 100)} %`}</td>
            <td><Status value={route.validation?.valid === true ? "VALID" : route.validation?.valid === false ? "INVALID" : "PENDING"} /></td>
            <td><Status value={route.status === "OUTDATED" ? "OUTDATED" : route.approval_state} /></td>
            <td><div className="routing-row-actions">{!(["REJECTED", "OUTDATED"].includes(route.status)) && <button onClick={(event) => { event.stopPropagation(); onEdit(route); }} type="button">Edit</button>}{!(["REJECTED", "OUTDATED"].includes(route.status)) && <button onClick={(event) => { event.stopPropagation(); onValidate(route); }} type="button">Validate</button>}{route.validation?.valid && route.approval_state === "PENDING" && route.status !== "OUTDATED" && <button onClick={(event) => { event.stopPropagation(); onApprove(route); }} type="button">{route.origin === "NETWORK_EDITOR" ? "Confirm" : "Approve"}</button>}{route.approval_state === "PENDING" && route.status !== "OUTDATED" && <button onClick={(event) => { event.stopPropagation(); onReject(route); }} type="button">Reject</button>}<button onClick={(event) => { event.stopPropagation(); onSelect(route); }} type="button">Show Path</button><button onClick={(event) => { event.stopPropagation(); onSelect(route); }} type="button">Evidence</button><button onClick={(event) => { event.stopPropagation(); onDuplicate(route); }} type="button">Duplicate</button>{route.approval_state !== "APPROVED" && !(["REJECTED", "OUTDATED"].includes(route.status)) && <button onClick={(event) => { event.stopPropagation(); onDelete(route); }} type="button">Delete</button>}</div></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function RoutingGraph({ routes, nodeNames, signalNames, onSelect }: { routes: RoutingEntry[]; nodeNames: Map<string, string>; signalNames: Map<string, string>; onSelect: (route: RoutingEntry) => void }) {
  if (routes.length === 0) return <EmptyRouting text="Graph wird sichtbar, sobald Routen existieren." />;
  return <div className="routing-graph-list">{routes.map((route) => {
    const payload = route.payload.signal_ids.map((id) => signalNames.get(id) ?? id).join(", ") || route.name;
    const path = [
      { kind: "Producer", label: nodeNames.get(route.source.node_id) ?? route.source.node_id },
      { kind: "Payload", label: payload },
      ...route.route.gateways.map((gateway) => ({ kind: "Gateway", label: typeof gateway === "string" ? nodeNames.get(gateway) ?? gateway : gateway.name ?? "Gateway" })),
      ...route.destinations.map((destination) => ({ kind: "Consumer", label: nodeNames.get(destination.node_id) ?? destination.node_id })),
    ];
    return <div className="routing-graph-route" key={route.id}><button className="routing-graph-code" onClick={() => onSelect(route)} type="button">{route.route_code}</button><div className="routing-graph-path">{path.map((item, index) => <span className="routing-graph-step" key={`${item.kind}-${index}`}><button onClick={() => onSelect(route)} type="button"><small>{item.kind}</small><strong>{item.label}</strong></button>{index < path.length - 1 && <i aria-hidden="true">→</i>}</span>)}</div></div>;
  })}</div>;
}

function RoutingMatrix({ routes, nodeNames, onSelect }: { routes: RoutingEntry[]; nodeNames: Map<string, string>; onSelect: (route: RoutingEntry) => void }) {
  const sources = [...new Set(routes.map((route) => route.source.node_id))];
  const destinations = [...new Set(routes.flatMap((route) => route.destinations.map((item) => item.node_id)))];
  if (!sources.length) return <EmptyRouting text="Kommunikationsmatrix ist noch leer." />;
  return <div className="routing-table-wrap"><table className="routing-matrix"><thead><tr><th>Source</th>{destinations.map((id) => <th key={id}>{nodeNames.get(id) ?? id}</th>)}</tr></thead><tbody>{sources.map((source) => <tr key={source}><th>{nodeNames.get(source) ?? source}</th>{destinations.map((destination) => { const matches = routes.filter((route) => route.source.node_id === source && route.destinations.some((item) => item.node_id === destination)); return <td key={destination}>{matches.length ? <button onClick={() => onSelect(matches[0])} type="button">✓ <span>{matches.length}</span></button> : "—"}</td>; })}</tr>)}</tbody></table></div>;
}

function RoutingProposals({ proposals, nodeNames, onAccept }: { proposals: RoutingProposal[]; nodeNames: Map<string, string>; onAccept: (proposal: RoutingProposal, index: number) => void }) {
  if (!proposals.length) return <EmptyRouting text="Noch keine KI-Routingvorschläge vorhanden." />;
  return <div className="routing-proposals">{proposals.map((proposal) => <article className="routing-proposal" key={proposal.proposal_id}><header><div><span>{proposal.status}</span><strong>{proposal.prompt}</strong></div><b>{proposal.confidence == null ? "—" : `${Math.round(proposal.confidence * 100)} %`}</b></header>{proposal.generated_routes.map((route, index) => <div className="routing-proposal-route" key={index}><div><strong>{route.name}</strong><span>{nodeNames.get(route.source.node_id) ?? route.source.node_id} → {route.destinations.map((item) => nodeNames.get(item.node_id) ?? item.node_id).join(", ")}</span></div><Status value={route.validation?.valid ? "VALID" : "INVALID"} /><button disabled={proposal.status === "APPROVED"} onClick={() => onAccept(proposal, index)} type="button">Als Draft übernehmen</button></div>)}</article>)}</div>;
}

function RoutingValidationList({ routes, onSelect, conflicts = false }: { routes: RoutingEntry[]; onSelect: (route: RoutingEntry) => void; conflicts?: boolean }) {
  const filtered = conflicts ? routes.filter((route) => route.validation?.valid === false || route.status === "CONFLICT") : routes;
  if (!filtered.length) return <EmptyRouting text={conflicts ? "Keine Routing-Konflikte vorhanden." : "Noch keine Routen zur Validierung vorhanden."} />;
  return <div className="routing-validation-list">{filtered.map((route) => <button key={route.id} onClick={() => onSelect(route)} type="button"><div><strong>{route.route_code} · {route.name}</strong><span>{route.validation?.errors?.[0]?.message ?? route.validation?.warnings?.[0]?.message ?? "Technisch konsistent"}</span></div><Status value={route.validation?.valid ? "VALID" : route.validation?.valid === false ? "INVALID" : "PENDING"} /></button>)}</div>;
}

function RoutingDetail({ route, nodeNames, messageNames, signalNames, interfaceNames, interfaceNetworks }: {
  route: RoutingEntry | null;
  nodeNames: Map<string, string>;
  messageNames: Map<string, string>;
  signalNames: Map<string, string>;
  interfaceNames: Map<string, string>;
  interfaceNetworks: Map<string, string>;
}) {
  if (!route) return <div className="panel routing-detail"><p className="eyebrow">Route Details</p><h3>Keine Route gewählt</h3><p className="muted">Wähle eine Tabellenzeile, einen Graphknoten oder eine Matrixzelle.</p></div>;
  const unmapped = route.validation?.warnings?.some((issue) => issue.code === "UNMAPPED_ROUTE");
  const sourceInterface = interfaceNames.get(route.source.interface_id ?? "") ?? route.source.interface_id ?? "—";
  const destinationInterfaces = route.destinations
    .map((item) => interfaceNames.get(item.interface_id ?? "") ?? item.interface_id ?? "—")
    .join(", ");
  const networks = [
    route.source.network_id ?? interfaceNetworks.get(route.source.interface_id ?? ""),
    ...route.destinations.map((item) => item.network_id ?? interfaceNetworks.get(item.interface_id ?? "")),
  ].filter(Boolean).join(" → ") || "—";
  const gateways = route.route.gateways
    .map((item) => typeof item === "string" ? nodeNames.get(item) ?? item : item.name ?? nodeNames.get(item.node_id ?? ""))
    .join(", ") || "—";
  return (
    <div className="panel routing-detail">
      <p className="eyebrow">Route Details</p>
      <div className="routing-detail-title"><h3>{route.route_code}</h3><Status value={route.status} /></div>
      <strong>{route.name}</strong>
      {route.origin === "NETWORK_EDITOR" && <p className="routing-network-origin">Proposed from Network Editor</p>}
      <dl>
        <dt>Producer</dt><dd>{nodeNames.get(route.source.node_id) ?? route.source.node_id}</dd>
        <dt>Source Interface</dt><dd>{sourceInterface}</dd>
        <dt>Network</dt><dd>{networks}</dd>
        <dt>Gateway</dt><dd>{gateways}</dd>
        <dt>Consumer</dt><dd>{route.destinations.map((item) => nodeNames.get(item.node_id) ?? item.node_id).join(", ")}</dd>
        <dt>Destination Interface</dt><dd>{destinationInterfaces}</dd>
        <dt>Message</dt><dd>{messageNames.get(route.payload.message_id ?? "") ?? route.payload.topic ?? "—"}</dd>
        <dt>Signals</dt><dd>{route.payload.signal_ids.map((id) => signalNames.get(id) ?? id).join(", ") || "—"}</dd>
        <dt>Protocol</dt><dd>{route.source.protocol ?? "—"}</dd>
        <dt>Timing</dt><dd>{route.timing.cycle_time_ms ?? "—"} ms cycle · {route.timing.max_latency_ms ?? "—"} ms max</dd>
        <dt>Path</dt><dd>{route.route.hops.map((hop) => typeof hop === "string" ? nodeNames.get(hop) ?? hop : hop.name ?? nodeNames.get(hop.node_id ?? "") ?? "Hop").join(" → ") || "Direct"}</dd>
        <dt>Load</dt><dd>{route.validation?.metrics?.route_load_percent ?? "—"} %</dd>
        <dt>Evidence</dt><dd>{route.validation?.evidence?.length ?? 0} technische Nachweise</dd>
      </dl>
      {route.validation?.outdated_reason && <p className="routing-issue warning">Reason: {route.validation.outdated_reason}</p>}
      {route.validation?.errors?.map((issue) => <p className="routing-issue error" key={issue.code}>{issue.message}</p>)}
      {route.validation?.warnings?.map((issue) => <p className="routing-issue warning" key={issue.code}>{issue.message}</p>)}
      {unmapped && <Link className="button secondary routing-open-network" href="/studio?mode=network">Open Network Editor</Link>}
    </div>
  );
}

function RoutingEditorDialog({ mode, route, schema, hardware, interfaces, messages, signals, onClose, onSave, onGenerate }: {
  mode: "manual" | "ai";
  route?: RoutingEntry;
  schema: RoutingSchema;
  hardware: HardwareNode[];
  interfaces: EngInterface[];
  messages: EngMessage[];
  signals: EngSignal[];
  onClose: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
  onGenerate: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [sourceId, setSourceId] = useState(route?.source.node_id ?? hardware[0]?.id ?? "");
  const [sourceInterfaceId, setSourceInterfaceId] = useState(route?.source.interface_id ?? "");
  const [destinationIds, setDestinationIds] = useState<string[]>(route?.destinations.map((item) => item.node_id) ?? []);
  const [messageId, setMessageId] = useState(route?.payload.message_id ?? "");
  const [signalIds, setSignalIds] = useState<string[]>(route?.payload.signal_ids ?? []);
  const [gatewayId, setGatewayId] = useState(() => { const first = route?.route.gateways[0]; return typeof first === "string" ? first : first?.node_id ?? ""; });
  const [protocol, setProtocol] = useState(route?.source.protocol ?? "CAN_FD");
  const [routingType, setRoutingType] = useState(route?.routing_policy.routing_type ?? "UNICAST");
  const [priority, setPriority] = useState(route?.route.priority ?? "NORMAL");
  const [cycle, setCycle] = useState(String(route?.timing.cycle_time_ms ?? 100));
  const [timeout, setTimeoutValue] = useState(String(route?.timing.timeout_ms ?? 500));
  const [latency, setLatency] = useState(String(route?.timing.max_latency_ms ?? 20));
  const [jitter, setJitter] = useState(String(route?.timing.jitter_limit_ms ?? 5));
  const [transformations, setTransformations] = useState(route?.route.transformations.join(", ") ?? "");
  const [condition, setCondition] = useState(String(route?.routing_policy.conditions[0]?.expression ?? ""));
  const [saving, setSaving] = useState(false);
  const sourceInterfaces = interfaces.filter((item) => item.hardware_node_id === sourceId);
  const selectedSignals = signals.filter((item) => item.message_id === messageId);
  const gateways = hardware.filter((node) => node.device_type === "Gateway");

  function toggleDestination(id: string) { setDestinationIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]); }
  function toggleSignal(id: string) { setSignalIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]); }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!sourceId || destinationIds.length === 0) return;
    setSaving(true);
    const sourceNode = hardware.find((item) => item.id === sourceId);
    const destinations = destinationIds.map((nodeId) => {
      const candidate = interfaces.find((item) => item.hardware_node_id === nodeId && (!protocol || interfaceProtocol(item.interface_type) === protocol));
      return { node_id: nodeId, interface_id: candidate?.id ?? null, network_id: networkId(candidate), protocol };
    });
    const gateway = gateways.find((item) => item.id === gatewayId);
    const hops = [
      { node_id: sourceId, name: sourceNode?.name },
      ...(gateway ? [{ node_id: gateway.id, name: gateway.name }] : []),
      ...destinationIds.map((id) => ({ node_id: id, name: hardware.find((item) => item.id === id)?.name })),
    ];
    const payload = {
      name: route?.name ?? `${sourceNode?.name ?? "Producer"} → ${destinationIds.map((id) => hardware.find((item) => item.id === id)?.name).join(", ")}`,
      description: route?.description ?? (mode === "ai" ? "KI-generierter Routingvorschlag" : "Manuell konfigurierte Route"),
      source: { node_id: sourceId, port_id: null, interface_id: sourceInterfaceId || sourceInterfaces[0]?.id || null, network_id: networkId(sourceInterfaces.find((item) => item.id === sourceInterfaceId) ?? sourceInterfaces[0]), protocol },
      payload: { interface_definition_id: null, message_id: messageId || null, signal_ids: signalIds, topic: null, data_object: null },
      destinations,
      route: { hops, gateways: gateway ? [{ node_id: gateway.id, name: gateway.name }] : [], transformations: transformations.split(",").map((item) => item.trim()).filter(Boolean), priority },
      timing: { cycle_time_ms: Number(cycle), timeout_ms: Number(timeout), max_latency_ms: Number(latency), jitter_limit_ms: Number(jitter) },
      routing_policy: { routing_type: destinationIds.length > 1 && routingType === "UNICAST" ? "MULTICAST" : routingType, redundancy: "NONE", fallback_route_id: null, conditions: condition ? [{ expression: condition }] : [] },
      actor: mode === "ai" ? "engineering-agent" : "routing-ui",
      prompt: `Erzeuge Routing von ${sourceNode?.name} zu ${destinationIds.map((id) => hardware.find((item) => item.id === id)?.name).join(", ")}`,
      source_node_id: sourceId,
      destination_node_ids: destinationIds,
      message_id: messageId || null,
      signal_ids: signalIds,
    };
    try { await (mode === "ai" ? onGenerate(payload) : onSave(payload)); } finally { setSaving(false); }
  }

  return <div className="routing-dialog-backdrop" role="presentation"><form className="routing-dialog" onSubmit={submit}><header><div><p className="eyebrow">{mode === "ai" ? "AI Routing Proposal" : "Routing Editor"}</p><h2>{route ? `${route.route_code} bearbeiten` : mode === "ai" ? "Routen generieren" : "Route anlegen"}</h2></div><button aria-label="Dialog schließen" onClick={onClose} type="button">×</button></header><div className="routing-editor-grid"><fieldset><legend>01 Source</legend><label>Source Node<select onChange={(event) => { setSourceId(event.target.value); setSourceInterfaceId(""); }} value={sourceId}>{hardware.map((node) => <option key={node.id} value={node.id}>{node.name} · {node.device_type}</option>)}</select></label><label>Source Interface<select onChange={(event) => { const item = interfaces.find((candidate) => candidate.id === event.target.value); setSourceInterfaceId(event.target.value); if (item) setProtocol(interfaceProtocol(item.interface_type)); }} value={sourceInterfaceId}><option value="">Automatisch</option>{sourceInterfaces.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.interface_type}</option>)}</select></label><label>Protocol<select onChange={(event) => setProtocol(event.target.value)} value={protocol}>{schema.protocols.map((item) => <option key={item}>{item}</option>)}</select></label></fieldset><fieldset><legend>02 Payload</legend><label>Message<select onChange={(event) => { setMessageId(event.target.value); setSignalIds([]); }} value={messageId}><option value="">Topic / Data Object</option>{messages.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><div className="routing-check-list"><span>Signals</span>{selectedSignals.length ? selectedSignals.map((signal) => <label key={signal.id}><input checked={signalIds.includes(signal.id)} onChange={() => toggleSignal(signal.id)} type="checkbox" />{signal.display_name || signal.name}</label>) : <small>Message wählen oder Payload ohne Signalselektion routen.</small>}</div></fieldset><fieldset><legend>03 Destination</legend><div className="routing-check-list"><span>Consumer</span>{hardware.filter((node) => node.id !== sourceId).map((node) => <label key={node.id}><input checked={destinationIds.includes(node.id)} onChange={() => toggleDestination(node.id)} type="checkbox" />{node.name}<small>{node.device_type}</small></label>)}</div></fieldset><fieldset><legend>04 Path</legend><label>Gateway<select onChange={(event) => setGatewayId(event.target.value)} value={gatewayId}><option value="">Direkter Pfad</option>{gateways.filter((item) => item.id !== sourceId && !destinationIds.includes(item.id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Routing Type<select onChange={(event) => setRoutingType(event.target.value)} value={routingType}>{schema.routing_types.map((item) => <option key={item}>{item}</option>)}</select></label><label>Priority<select onChange={(event) => setPriority(event.target.value as typeof priority)} value={priority}>{schema.priorities.map((item) => <option key={item}>{item}</option>)}</select></label><label>Transformations<input onChange={(event) => setTransformations(event.target.value)} placeholder="CAN_SIGNAL_TO_SOMEIP_FIELD" value={transformations} /></label><label>Condition<input onChange={(event) => setCondition(event.target.value)} placeholder="BatteryFaultLevel >= CRITICAL" value={condition} /></label></fieldset><fieldset className="routing-timing"><legend>05 Timing</legend><label>Cycle Time (ms)<input min="0.001" onChange={(event) => setCycle(event.target.value)} step="any" type="number" value={cycle} /></label><label>Timeout (ms)<input min="0.001" onChange={(event) => setTimeoutValue(event.target.value)} step="any" type="number" value={timeout} /></label><label>Maximum Latency (ms)<input min="0.001" onChange={(event) => setLatency(event.target.value)} step="any" type="number" value={latency} /></label><label>Jitter (ms)<input min="0.001" onChange={(event) => setJitter(event.target.value)} step="any" type="number" value={jitter} /></label></fieldset></div><footer><span>{mode === "ai" ? "Der Agent erzeugt ausschließlich ein prüfbares Proposal." : "Speichern erzeugt einen Draft. Freigabe erfolgt separat."}</span><div><button className="button secondary" onClick={onClose} type="button">Abbrechen</button><button className="button primary" disabled={saving || !sourceId || !destinationIds.length} type="submit">{saving ? "Wird verarbeitet …" : mode === "ai" ? "Proposal erzeugen" : "Draft speichern"}</button></div></footer></form></div>;
}

function interfaceProtocol(type: string) { return ({ CAN: "CAN", CAN_FD: "CAN_FD", LIN: "LIN", FlexRay: "FLEXRAY", Ethernet: "ETHERNET", EtherCAT: "ETHERCAT", ProfiNET: "PROFINET", ModbusTCP: "MODBUS", ModbusRTU: "MODBUS", OPCUA: "OPC_UA" } as Record<string, string>)[type] ?? "CUSTOM"; }
function networkId(item?: EngInterface) { return item ? `network-${String(item.configuration?.bus ?? item.interface_type).toLowerCase()}` : null; }
function Status({ value }: { value: string }) { return <span className={`routing-status ${value.toLowerCase().replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>; }
function EmptyRouting({ text }: { text: string }) { return <div className="empty-result routing-empty"><span className="empty-icon">⌁</span><strong>{text}</strong></div>; }
