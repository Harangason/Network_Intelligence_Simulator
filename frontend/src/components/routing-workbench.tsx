"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
  RoutingValidationIssue,
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
  const search = useSearchParams();
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
  const [wizardRoute, setWizardRoute] = useState<RoutingEntry | null>(null);
  const [handledEditRoute, setHandledEditRoute] = useState("");
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
    const routeId = search.get("route");
    setSelected((current) => routeItems.find((item) => item.id === routeId) ?? routeItems.find((item) => item.id === current?.id) ?? routeItems[0] ?? null);
  }, [search]);

  useEffect(() => {
    refresh().catch((error) => setNotice({ type: "error", text: error instanceof Error ? error.message : "Routing konnte nicht geladen werden." }));
  }, [refresh]);

  useEffect(() => {
    const viewParam = search.get("view");
    const nextView = VIEWS.find((item) => item.toLowerCase().replaceAll(" ", "-") === String(viewParam ?? "").toLowerCase());
    if (nextView) setView(nextView);
  }, [search]);

  useEffect(() => {
    const routeId = search.get("route");
    if (!routeId) return;
    const route = routes.find((item) => item.id === routeId);
    if (!route) return;
    setSelected(route);
    if (search.get("edit") === "1" && schema && handledEditRoute !== routeId) {
      setEditor({ mode: "manual", route });
      setHandledEditRoute(routeId);
    }
  }, [handledEditRoute, routes, schema, search]);

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
              onSelect={setSelected}
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
            onApprove={(route) => void act("approve", () => approveRoutes([route.id]), `${route.route_code} bestätigt.`)}
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
            onReject={(route) => void act("reject", () => rejectRoutes([route.id], "Im Routing Manager abgelehnt."), `${route.route_code} abgelehnt.`)}
            onValidate={(route) => void act("validate", () => validateRoute(route.id), `${route.route_code} validiert.`)}
            onWizard={setWizardRoute}
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
      {wizardRoute && schema && (
        <RoutingRepairWizard
          hardware={hardware}
          interfaces={interfaces}
          messages={messages}
          onClose={() => setWizardRoute(null)}
          onDelete={() => act("delete", () => deleteRoute(wizardRoute.id), `${wizardRoute.route_code} gelöscht.`).then(() => setWizardRoute(null))}
          onSave={(payload) => act("route-wizard", async () => {
            const updated = await updateRoute(wizardRoute.id, payload);
            await validateRoute(updated.id);
          }, "Route gespeichert und validiert.").then(() => setWizardRoute(null))}
          route={wizardRoute}
          schema={schema}
          signals={signals}
        />
      )}
    </>
  );
}

function canDeleteRoute(route: RoutingEntry) {
  return route.approval_state !== "APPROVED" && !["APPROVED", "RELEASED"].includes(route.status);
}

function RoutingTable({ routes, checked, selectedId, nodeNames, messageNames, signalNames, interfaceNames, interfaceNetworks, onCheck, onSelect }: {
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
}) {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const tableScrollRef = useRef<HTMLDivElement | null>(null);
  const pageSize = 25;
  const columns: Array<{ key: keyof ReturnType<typeof routeCells> | "select"; label: string; filterable: boolean; filterType?: "text" | "select" }> = [
    { key: "select", label: "Select", filterable: false },
    { key: "route", label: "Route ID", filterable: true },
    { key: "producer", label: "Producer", filterable: true },
    { key: "sourceInterface", label: "Source Interface", filterable: true },
    { key: "payload", label: "Payload", filterable: true },
    { key: "message", label: "Message", filterable: true },
    { key: "signals", label: "Signals", filterable: true },
    { key: "network", label: "Network", filterable: true },
    { key: "gateway", label: "Gateway", filterable: true },
    { key: "consumer", label: "Consumer", filterable: true },
    { key: "destinationInterface", label: "Destination Interface", filterable: true },
    { key: "protocol", label: "Protocol", filterable: true, filterType: "select" },
    { key: "cycle", label: "Cycle", filterable: true },
    { key: "latency", label: "Latency", filterable: true },
    { key: "origin", label: "Origin", filterable: true, filterType: "select" },
    { key: "confidence", label: "Confidence", filterable: true },
    { key: "validation", label: "Validation", filterable: true, filterType: "select" },
    { key: "approval", label: "Approval", filterable: true, filterType: "select" },
  ];

  function routeCells(route: RoutingEntry) {
    return {
      route: `${route.route_code} r${route.revision}`,
      producer: nodeNames.get(route.source.node_id) ?? route.source.node_id,
      sourceInterface: interfaceNames.get(route.source.interface_id ?? "") ?? route.source.interface_id ?? "—",
      payload: route.payload.topic ?? route.payload.data_object ?? route.payload.interface_definition_id ?? "Message",
      message: messageNames.get(route.payload.message_id ?? "") ?? "—",
      signals: route.payload.signal_ids.slice(0, 2).map((id) => signalNames.get(id) ?? id).join(", ") || "—",
      network: route.source.network_id ?? interfaceNetworks.get(route.source.interface_id ?? "") ?? "—",
      gateway: route.route.gateways.map((item) => typeof item === "string" ? nodeNames.get(item) ?? item : item.name ?? nodeNames.get(item.node_id ?? "")).join(", ") || "—",
      consumer: route.destinations.map((item) => nodeNames.get(item.node_id) ?? item.node_id).join(", "),
      destinationInterface: route.destinations.map((item) => interfaceNames.get(item.interface_id ?? "") ?? item.interface_id ?? "—").join(", "),
      protocol: route.source.protocol ?? "—",
      cycle: `${route.timing.cycle_time_ms ?? "—"} ms`,
      latency: `${route.timing.max_latency_ms ?? "—"} ms`,
      origin: route.origin === "NETWORK_EDITOR" ? "Proposed from Network Editor" : route.origin,
      confidence: route.confidence == null ? "—" : `${Math.round(route.confidence * 100)} %`,
      validation: route.validation?.valid === true ? "VALID" : route.validation?.valid === false ? "INVALID" : "PENDING",
      approval: route.status === "OUTDATED" ? "OUTDATED" : route.approval_state,
    };
  }

  const filteredRoutes = routes.filter((route) => {
    const cells = routeCells(route);
    return columns.every((column) => {
      if (column.filterable === false || column.key === "select") return true;
      const filter = (filters[column.key] ?? "").trim().toLowerCase();
      return !filter || String(cells[column.key]).toLowerCase().includes(filter);
    });
  });
  const totalPages = Math.max(1, Math.ceil(filteredRoutes.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visibleRoutes = filteredRoutes.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  function filterOptions(key: keyof ReturnType<typeof routeCells>) {
    return [...new Set(routes.map((route) => String(routeCells(route)[key])).filter((value) => value && value !== "—"))].sort();
  }

  function updateFilter(key: string, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  useEffect(() => {
    const scrollNode = tableScrollRef.current;
    if (!scrollNode) return undefined;

    const scrollHorizontally = (delta: number) => {
      if (!delta || scrollNode.scrollWidth <= scrollNode.clientWidth) return false;
      const before = scrollNode.scrollLeft;
      scrollNode.scrollLeft += delta;
      return scrollNode.scrollLeft !== before;
    };

    const onWheel = (event: globalThis.WheelEvent) => {
      const horizontalDelta = event.deltaX || (event.shiftKey ? event.deltaY : 0);
      if (scrollHorizontally(horizontalDelta)) event.preventDefault();
    };

    const onAuxInput = (event: MouseEvent) => {
      if (event.button !== 3 && event.button !== 4) return;
      if (scrollHorizontally(event.button === 3 ? -260 : 260)) event.preventDefault();
    };

    scrollNode.addEventListener("wheel", onWheel, { passive: false });
    scrollNode.addEventListener("mousedown", onAuxInput);
    scrollNode.addEventListener("mouseup", onAuxInput);
    scrollNode.addEventListener("auxclick", onAuxInput);
    return () => {
      scrollNode.removeEventListener("wheel", onWheel);
      scrollNode.removeEventListener("mousedown", onAuxInput);
      scrollNode.removeEventListener("mouseup", onAuxInput);
      scrollNode.removeEventListener("auxclick", onAuxInput);
    };
  }, []);

  if (routes.length === 0) return <EmptyRouting text="Noch keine Routingdefinition vorhanden." />;
  return (
    <div className="routing-table-wrap" ref={tableScrollRef}>
      <table className="routing-table">
        <thead>
          <tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr>
          <tr className="routing-filter-row">
            {columns.map((column) => (
              <th key={`${column.key}-filter`}>
                {column.filterable === false ? (
                  <span />
                ) : column.filterType === "select" ? (
                  <select
                    aria-label={`${column.label} filtern`}
                    onChange={(event) => updateFilter(column.key, event.target.value)}
                    value={filters[column.key] ?? ""}
                  >
                    <option value="">Alle</option>
                    {filterOptions(column.key as keyof ReturnType<typeof routeCells>).map((option) => (
                      <option key={option} value={option}>{option}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    aria-label={`${column.label} filtern`}
                    onChange={(event) => updateFilter(column.key, event.target.value)}
                    placeholder="Filtern"
                    type="search"
                    value={filters[column.key] ?? ""}
                  />
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{visibleRoutes.map((route) => {
          const cells = routeCells(route);
          return (
          <tr className={selectedId === route.id ? "selected" : ""} key={route.id} onClick={() => onSelect(route)}>
            <td><input aria-label={`${route.route_code} auswählen`} checked={checked.has(route.id)} onChange={() => onCheck(route.id)} onClick={(event) => event.stopPropagation()} type="checkbox" /></td>
            <td><strong>{route.route_code}</strong><span>r{route.revision}</span></td>
            <td>{cells.producer}</td>
            <td>{cells.sourceInterface}</td>
            <td>{cells.payload}</td>
            <td>{cells.message}</td>
            <td>{cells.signals}</td>
            <td>{cells.network}</td>
            <td>{cells.gateway}</td>
            <td>{cells.consumer}</td>
            <td>{cells.destinationInterface}</td>
            <td>{cells.protocol}</td><td>{cells.cycle}</td><td>{cells.latency}</td>
            <td>{route.origin === "NETWORK_EDITOR" ? <span className="routing-network-origin">{cells.origin}</span> : cells.origin}</td><td>{cells.confidence}</td>
            <td><Status value={cells.validation} /></td>
            <td><Status value={cells.approval} /></td>
          </tr>
        );})}</tbody>
      </table>
      {filteredRoutes.length > 0 && (
        <div className="routing-pagination">
          <span>
            Seite {currentPage} von {totalPages} · {filteredRoutes.length} Treffer · {pageSize} pro Seite
          </span>
          <div>
            <button className="button secondary tiny" disabled={currentPage === 1} onClick={() => setPage(1)} type="button">Erste</button>
            <button className="button secondary tiny" disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))} type="button">Zurück</button>
            <button className="button secondary tiny" disabled={currentPage === totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))} type="button">Weiter</button>
            <button className="button secondary tiny" disabled={currentPage === totalPages} onClick={() => setPage(totalPages)} type="button">Letzte</button>
          </div>
        </div>
      )}
      {filteredRoutes.length === 0 && <div className="routing-filter-empty">Keine Routen passen zu den aktiven Filtern.</div>}
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

function RoutingDetail({ route, nodeNames, messageNames, signalNames, interfaceNames, interfaceNetworks, onEdit, onWizard, onValidate, onApprove, onReject, onDuplicate, onDelete }: {
  route: RoutingEntry | null;
  nodeNames: Map<string, string>;
  messageNames: Map<string, string>;
  signalNames: Map<string, string>;
  interfaceNames: Map<string, string>;
  interfaceNetworks: Map<string, string>;
  onEdit: (route: RoutingEntry) => void;
  onWizard: (route: RoutingEntry) => void;
  onValidate: (route: RoutingEntry) => void;
  onApprove: (route: RoutingEntry) => void;
  onReject: (route: RoutingEntry) => void;
  onDuplicate: (route: RoutingEntry) => void;
  onDelete: (route: RoutingEntry) => void;
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
      <div className="routing-detail-actions" aria-label="Route Aktionen">
        <button className="button primary tiny" onClick={() => onWizard(route)} type="button">Wizard</button>
        <button className="button secondary tiny" onClick={() => onEdit(route)} type="button">Edit</button>
        {!(["REJECTED", "OUTDATED"].includes(route.status)) && <button className="button secondary tiny" onClick={() => onValidate(route)} type="button">Validate</button>}
        {route.validation?.valid && route.approval_state === "PENDING" && route.status !== "OUTDATED" && <button className="button primary tiny" onClick={() => onApprove(route)} type="button">{route.origin === "NETWORK_EDITOR" ? "Confirm" : "Approve"}</button>}
        {route.approval_state === "PENDING" && route.status !== "OUTDATED" && <button className="button danger tiny" onClick={() => onReject(route)} type="button">Reject</button>}
        <button className="button secondary tiny" type="button">Show Path</button>
        <button className="button secondary tiny" type="button">Evidence</button>
        <button className="button secondary tiny" onClick={() => onDuplicate(route)} type="button">Duplicate</button>
        {canDeleteRoute(route) && <button className="button danger tiny" onClick={() => onDelete(route)} type="button">Delete</button>}
      </div>
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

const ROUTING_WIZARD_STEPS = ["Quelle", "Payload", "Ziel", "Timing", "Prüfen"] as const;

function RoutingRepairWizard({ route, schema, hardware, interfaces, messages, signals, onClose, onSave, onDelete }: {
  route: RoutingEntry;
  schema: RoutingSchema;
  hardware: HardwareNode[];
  interfaces: EngInterface[];
  messages: EngMessage[];
  signals: EngSignal[];
  onClose: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [sourceId, setSourceId] = useState(route.source.node_id ?? "");
  const [sourceInterfaceId, setSourceInterfaceId] = useState(route.source.interface_id ?? "");
  const [messageId, setMessageId] = useState(route.payload.message_id ?? "");
  const [signalIds, setSignalIds] = useState<string[]>(route.payload.signal_ids ?? []);
  const [destinationIds, setDestinationIds] = useState<string[]>(route.destinations.map((item) => item.node_id));
  const [destinationInterfaces, setDestinationInterfaces] = useState<Record<string, string>>(
    Object.fromEntries(route.destinations.map((item) => [item.node_id, item.interface_id ?? ""])),
  );
  const [gatewayId, setGatewayId] = useState(() => { const gateway = route.route.gateways[0]; return typeof gateway === "string" ? gateway : gateway?.node_id ?? ""; });
  const [protocol, setProtocol] = useState(route.source.protocol ?? "CAN_FD");
  const [routingType, setRoutingType] = useState(route.routing_policy.routing_type ?? "UNICAST");
  const [priority, setPriority] = useState(route.route.priority ?? "NORMAL");
  const [cycle, setCycle] = useState(String(route.timing.cycle_time_ms ?? 10));
  const [timeout, setTimeoutValue] = useState(String(route.timing.timeout_ms ?? 100));
  const [latency, setLatency] = useState(String(route.timing.max_latency_ms ?? 20));
  const [jitter, setJitter] = useState(String(route.timing.jitter_limit_ms ?? 5));
  const [transformations, setTransformations] = useState(route.route.transformations.join(", "));
  const sourceInterfaces = interfaces.filter((item) => item.hardware_node_id === sourceId);
  const selectedMessage = messages.find((item) => item.id === messageId);
  const selectedSignals = signals.filter((item) => item.message_id === messageId);
  const gateways = hardware.filter((node) => node.device_type === "Gateway" && node.id !== sourceId && !destinationIds.includes(node.id));
  const destinationOptions = hardware.filter((node) => node.id !== sourceId);
  const validationIssues = [...(route.validation?.errors ?? []), ...(route.validation?.warnings ?? [])];
  const hasIssue = (code: string) => validationIssues.some((issue) => issue.code === code);
  const missing = [
    !sourceId ? "Producer" : "",
    !sourceInterfaceId ? "Source Interface" : "",
    !destinationIds.length ? "Consumer" : "",
    ...destinationIds.flatMap((id) => destinationInterfaces[id] ? [] : [`Destination Interface: ${hardware.find((item) => item.id === id)?.name ?? id}`]),
    !messageId && !route.payload.topic && !route.payload.data_object ? "Payload Message oder Topic" : "",
    !cycle ? "Cycle" : "",
    !latency ? "Latency" : "",
  ].filter(Boolean);

  function interfaceLabel(item: EngInterface) {
    const hardwareNode = hardware.find((node) => node.id === item.hardware_node_id);
    return `${item.name} · ${item.interface_type}${hardwareNode ? ` · ${hardwareNode.name}` : ""} · ${item.id.slice(0, 8)}`;
  }

  function messageLabel(item: EngMessage) {
    const iface = interfaces.find((candidate) => candidate.id === item.interface_id);
    const sender = messageSender(item);
    return `${item.name}${sender ? ` · Sender ${sender}` : ""}${iface ? ` · ${iface.name}` : ""}${item.domain ? ` · ${item.domain}` : ""} · ${item.id.slice(0, 8)}`;
  }

  function messageKindRank(item: EngMessage) {
    const upper = item.name.toUpperCase();
    if (upper.startsWith("DATA")) return 0;
    if (upper.startsWith("RESP")) return 1;
    return 2;
  }

  function messageSender(item: EngMessage) {
    const iface = interfaces.find((candidate) => candidate.id === item.interface_id);
    const node = iface ? hardware.find((candidate) => candidate.id === iface.hardware_node_id) : undefined;
    if (node?.name) return node.name;
    const match = item.name.match(/^(?:DATA|RESP)[_-]?\d*[_-]?(.+?)(?:_TO_|$)/i);
    return match?.[1]?.replaceAll("_", " ") ?? "";
  }

  const sortedMessages = [...messages].sort((left, right) => (
    messageKindRank(left) - messageKindRank(right)
    || messageSender(left).localeCompare(messageSender(right), "de")
    || left.name.localeCompare(right.name, "de")
  ));

  function suggestionScore(label: string, extra = "") {
    const haystack = `${route.name} ${route.description ?? ""} ${route.route_code} ${label}`.toLowerCase();
    let score = 44;
    for (const token of haystack.split(/[^a-z0-9]+/).filter((item) => item.length > 2)) {
      if (extra.toLowerCase().includes(token)) score += 10;
    }
    if (label.toLowerCase().includes(protocol.toLowerCase().replace("_", " "))) score += 14;
    return Math.max(18, Math.min(96, score));
  }

  function topInterfaceSuggestions(options: EngInterface[]) {
    return options
      .map((item) => ({ id: item.id, label: interfaceLabel(item), confidence: suggestionScore(interfaceLabel(item), `${item.name} ${item.interface_type}`) }))
      .sort((left, right) => right.confidence - left.confidence)
      .slice(0, 3);
  }

  function topMessageSuggestions() {
    return sortedMessages
      .map((item) => ({ id: item.id, label: messageLabel(item), confidence: suggestionScore(messageLabel(item), `${item.name} ${item.description ?? ""}`) }))
      .sort((left, right) => right.confidence - left.confidence)
      .slice(0, 3);
  }

  function applySourceInterface(id: string) {
    const iface = interfaces.find((item) => item.id === id);
    setSourceInterfaceId(id);
    if (iface) setProtocol(interfaceProtocol(iface.interface_type));
  }

  function applyMessage(id: string) {
    setMessageId(id);
    setSignalIds([]);
    const msg = messages.find((item) => item.id === id);
    if (msg?.cycle_ms && (!cycle || cycle === "100")) setCycle(String(msg.cycle_ms));
    if (msg?.dlc && (!route.payload.signal_ids.length || !signalIds.length)) {
      setSignalIds(signals.filter((item) => item.message_id === id).slice(0, Math.max(1, Math.min(4, msg.dlc ?? 1))).map((item) => item.id));
    }
  }

  function toggleDestination(id: string) {
    setDestinationIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function toggleSignal(id: string) {
    setSignalIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function setDestinationInterface(nodeId: string, interfaceId: string) {
    setDestinationInterfaces((current) => ({ ...current, [nodeId]: interfaceId }));
  }

  function preferredInterfaceForNode(nodeId: string) {
    return interfaces.find((item) => item.hardware_node_id === nodeId && interfaceProtocol(item.interface_type) === protocol)
      ?? interfaces.find((item) => item.hardware_node_id === nodeId)
      ?? null;
  }

  function applyBestSourceInterface() {
    const candidate = preferredInterfaceForNode(sourceId);
    if (candidate) applySourceInterface(candidate.id);
  }

  function applyBestDestinationInterfaces() {
    setDestinationInterfaces((current) => Object.fromEntries(destinationIds.map((nodeId) => {
      const candidate = preferredInterfaceForNode(nodeId);
      return [nodeId, current[nodeId] || candidate?.id || ""];
    })));
  }

  function applyBestPayload() {
    const candidate = topMessageSuggestions()[0];
    if (candidate) applyMessage(candidate.id);
  }

  function chooseDifferentPayload() {
    const currentIndex = sortedMessages.findIndex((item) => item.id === messageId);
    const next = sortedMessages.find((item, index) => item.id !== messageId && index > currentIndex)
      ?? sortedMessages.find((item) => item.id !== messageId);
    if (next) applyMessage(next.id);
  }

  function applyBusDefaults() {
    const iface = interfaces.find((item) => item.id === sourceInterfaceId);
    const protocolName = iface ? interfaceProtocol(iface.interface_type) : protocol;
    if (protocolName === "CAN_FD") {
      if (!cycle) setCycle("10");
      if (!timeout) setTimeoutValue("100");
      if (!latency) setLatency("20");
      if (!jitter) setJitter("5");
    } else if (protocolName === "LIN") {
      if (!cycle) setCycle("20");
      if (!timeout) setTimeoutValue("200");
      if (!latency) setLatency("50");
      if (!jitter) setJitter("10");
    } else {
      if (!cycle) setCycle("10");
      if (!timeout) setTimeoutValue("100");
      if (!latency) setLatency("20");
      if (!jitter) setJitter("2");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    const sourceNode = hardware.find((item) => item.id === sourceId);
    const gateway = hardware.find((item) => item.id === gatewayId);
    const destinations = destinationIds.map((nodeId) => {
      const iface = interfaces.find((item) => item.id === destinationInterfaces[nodeId]);
      return { node_id: nodeId, port_id: null, interface_id: iface?.id ?? null, network_id: networkId(iface), protocol };
    });
    const hops = [
      { node_id: sourceId, name: sourceNode?.name },
      ...(gateway ? [{ node_id: gateway.id, name: gateway.name }] : []),
      ...destinationIds.map((id) => ({ node_id: id, name: hardware.find((item) => item.id === id)?.name })),
    ];
    const sourceInterface = interfaces.find((item) => item.id === sourceInterfaceId);
    const payload = {
      name: route.name,
      description: route.description ?? null,
      source: { node_id: sourceId, port_id: null, interface_id: sourceInterfaceId || null, network_id: networkId(sourceInterface), protocol },
      payload: { ...route.payload, message_id: messageId || null, signal_ids: signalIds },
      destinations,
      route: { ...route.route, hops, gateways: gateway ? [{ node_id: gateway.id, name: gateway.name }] : [], transformations: transformations.split(",").map((item) => item.trim()).filter(Boolean), priority },
      timing: { cycle_time_ms: Number(cycle), timeout_ms: Number(timeout), max_latency_ms: Number(latency), jitter_limit_ms: Number(jitter) },
      routing_policy: { ...route.routing_policy, routing_type: destinationIds.length > 1 && routingType === "UNICAST" ? "MULTICAST" : routingType },
      actor: "routing-wizard",
    };
    try { await onSave(payload); } finally { setSaving(false); }
  }

  function nodeName(id: string) {
    return hardware.find((item) => item.id === id)?.name ?? id;
  }

  function routePathText() {
    const gateway = hardware.find((item) => item.id === gatewayId);
    const hardwarePath = [
      nodeName(sourceId),
      gateway?.name,
      ...destinationIds.map(nodeName),
    ].filter(Boolean).join(" → ");
    return hardwarePath || "Hardwarepfad offen";
  }

  return (
    <div className="routing-dialog-backdrop" role="presentation">
      <form aria-modal="true" className="routing-dialog routing-wizard-dialog" onSubmit={submit} role="dialog">
        <header><div><p className="eyebrow">Routing Wizard</p><h2>{route.route_code}</h2><span className="routing-wizard-path">{routePathText()}</span></div><button aria-label="Dialog schließen" onClick={onClose} type="button">×</button></header>
        <div className="routing-wizard-steps">{ROUTING_WIZARD_STEPS.map((label, index) => <button className={step === index ? "active" : ""} key={label} onClick={() => setStep(index)} type="button"><span>{String(index + 1).padStart(2, "0")}</span>{label}</button>)}</div>
        {step === 0 && <div className="routing-wizard-grid"><label>Producer<select onChange={(event) => { setSourceId(event.target.value); setSourceInterfaceId(""); }} value={sourceId}>{hardware.map((node) => <option key={node.id} value={node.id}>{node.name} · {node.device_type}</option>)}</select></label><label>Source Interface<select onChange={(event) => applySourceInterface(event.target.value)} value={sourceInterfaceId}><option value="">Auswählen</option>{sourceInterfaces.map((item) => <option key={item.id} value={item.id}>{interfaceLabel(item)}</option>)}</select></label><AiSuggestionList onPick={applySourceInterface} suggestions={topInterfaceSuggestions(sourceInterfaces)} value={sourceInterfaceId} /><label>Protocol<select onChange={(event) => setProtocol(event.target.value)} value={protocol}>{schema.protocols.map((item) => <option key={item}>{item}</option>)}</select></label></div>}
        {step === 1 && <div className="routing-wizard-grid"><label>Message<select onChange={(event) => applyMessage(event.target.value)} value={messageId}><option value="">Topic / Data Object</option>{sortedMessages.map((item) => <option key={item.id} value={item.id}>{messageLabel(item)}</option>)}</select></label><AiSuggestionList onPick={applyMessage} suggestions={topMessageSuggestions()} value={messageId} /><div className="routing-check-list full-width"><span>Signals</span>{selectedSignals.length ? selectedSignals.map((signal) => <label key={signal.id}><input checked={signalIds.includes(signal.id)} onChange={() => toggleSignal(signal.id)} type="checkbox" />{signal.display_name || signal.name}<small>{signal.start_bit ?? "?"} / {signal.length_bits ?? "?"} Bit</small></label>) : <small>Message wählen, dann werden passende Signals angeboten.</small>}</div></div>}
        {step === 2 && <div className="routing-wizard-grid"><div className="routing-check-list full-width"><span>Consumer</span>{destinationOptions.map((node) => <label key={node.id}><input checked={destinationIds.includes(node.id)} onChange={() => toggleDestination(node.id)} type="checkbox" />{node.name}<small>{node.device_type}</small></label>)}</div>{destinationIds.map((nodeId) => { const options = interfaces.filter((item) => item.hardware_node_id === nodeId && (!protocol || interfaceProtocol(item.interface_type) === protocol)); return <label key={nodeId}>{hardware.find((item) => item.id === nodeId)?.name ?? nodeId} Interface<select onChange={(event) => setDestinationInterface(nodeId, event.target.value)} value={destinationInterfaces[nodeId] ?? ""}><option value="">Auswählen</option>{options.map((item) => <option key={item.id} value={item.id}>{interfaceLabel(item)}</option>)}</select></label>; })}<label>Gateway<select onChange={(event) => setGatewayId(event.target.value)} value={gatewayId}><option value="">Direkter Pfad</option>{gateways.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>}
        {step === 3 && <div className="routing-wizard-grid"><label>Routing Type<select onChange={(event) => setRoutingType(event.target.value)} value={routingType}>{schema.routing_types.map((item) => <option key={item}>{item}</option>)}</select></label><label>Priority<select onChange={(event) => setPriority(event.target.value as typeof priority)} value={priority}>{schema.priorities.map((item) => <option key={item}>{item}</option>)}</select></label><label>Cycle Time (ms)<input min="0.001" onChange={(event) => setCycle(event.target.value)} step="any" type="number" value={cycle} /></label><label>Timeout (ms)<input min="0.001" onChange={(event) => setTimeoutValue(event.target.value)} step="any" type="number" value={timeout} /></label><label>Maximum Latency (ms)<input min="0.001" onChange={(event) => setLatency(event.target.value)} step="any" type="number" value={latency} /></label><label>Jitter (ms)<input min="0.001" onChange={(event) => setJitter(event.target.value)} step="any" type="number" value={jitter} /></label><label className="full-width">Transformations<input onChange={(event) => setTransformations(event.target.value)} placeholder="CAN_SIGNAL_TO_SOMEIP_FIELD" value={transformations} /></label><button className="button secondary" onClick={applyBusDefaults} type="button">Leere Timing-Felder per Bus füllen</button></div>}
        {step === 4 && <div className="routing-wizard-review"><div className={missing.length ? "routing-wizard-verdict invalid" : "routing-wizard-verdict valid"}><strong>{missing.length ? "Noch nicht valide" : "Bereit zur Validierung"}</strong><span>{missing.length ? `${missing.length} Punkt(e) fehlen.` : "Die Route hat alle Wizard-Pflichtangaben."}</span></div>{missing.length > 0 && <div className="routing-wizard-checks">{missing.map((item) => <span key={item}>{item}</span>)}</div>}<RoutingRepairPanel applyBestDestinationInterfaces={applyBestDestinationInterfaces} applyBestPayload={applyBestPayload} applyBestSourceInterface={applyBestSourceInterface} canDelete={canDeleteRoute(route)} chooseDifferentPayload={chooseDifferentPayload} hasIssue={hasIssue} issues={validationIssues} onDelete={onDelete} setStep={setStep} />{route.validation?.errors?.length ? <div className="routing-wizard-findings"><strong>Aktuelle Findings</strong>{route.validation.errors.map((issue) => <small className="routing-issue error" key={issue.code}>{issue.message}</small>)}</div> : null}<RoutingWizardSummary destinationIds={destinationIds} destinationInterfaces={destinationInterfaces} hardware={hardware} interfaces={interfaces} message={selectedMessage} route={route} sourceId={sourceId} sourceInterfaceId={sourceInterfaceId} signals={signals.filter((item) => signalIds.includes(item.id))} timing={{ cycle, timeout, latency, jitter }} /></div>}
        <footer><button className="button secondary" disabled={step === 0} onClick={() => setStep((current) => Math.max(0, current - 1))} type="button">Zurück</button>{step < ROUTING_WIZARD_STEPS.length - 1 ? <button className="button primary" onClick={() => setStep((current) => Math.min(ROUTING_WIZARD_STEPS.length - 1, current + 1))} type="button">Weiter</button> : <button className="button primary" disabled={saving || missing.length > 0} type="submit">{saving ? "Speichert ..." : "Speichern & validieren"}</button>}</footer>
      </form>
    </div>
  );
}

function RoutingRepairPanel({ issues, hasIssue, applyBestSourceInterface, applyBestDestinationInterfaces, applyBestPayload, chooseDifferentPayload, onDelete, canDelete, setStep }: {
  issues: RoutingValidationIssue[];
  hasIssue: (code: string) => boolean;
  applyBestSourceInterface: () => void;
  applyBestDestinationInterfaces: () => void;
  applyBestPayload: () => void;
  chooseDifferentPayload: () => void;
  onDelete: () => Promise<void>;
  canDelete: boolean;
  setStep: (step: number) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const repairs = [
    hasIssue("DUPLICATE_ROUTE") ? {
      key: "duplicate",
      title: "Identische Route",
      text: "Diese Route hat dieselbe Quelle, denselben Payload und dieselben Ziele wie eine vorhandene Route.",
      actions: <>
        <button className="button secondary tiny" onClick={() => { chooseDifferentPayload(); setStep(1); }} type="button">Anderen Payload vorschlagen</button>
        <button className="button secondary tiny" onClick={() => setStep(2)} type="button">Ziel ändern</button>
        {canDelete && <button className="button danger tiny" disabled={deleting} onClick={() => { setDeleting(true); void onDelete().finally(() => setDeleting(false)); }} type="button">{deleting ? "Löscht ..." : "Duplikat löschen"}</button>}
      </>,
    } : null,
    hasIssue("SOURCE_INTERFACE_MISSING") || hasIssue("SOURCE_INTERFACE_NOT_FOUND") || hasIssue("SOURCE_INTERFACE_MISMATCH") ? {
      key: "source-interface",
      title: "Source Interface",
      text: "Der Producer braucht ein passendes Interface zum gewählten Bus, sonst kann die Route nicht sauber auf das Netzwerk gelegt werden.",
      actions: <>
        <button className="button primary tiny" onClick={applyBestSourceInterface} type="button">Passendes Interface setzen</button>
        <button className="button secondary tiny" onClick={() => setStep(0)} type="button">Quelle prüfen</button>
      </>,
    } : null,
    hasIssue("DESTINATION_INTERFACE_MISSING") || hasIssue("DESTINATION_INTERFACE_NOT_FOUND") || hasIssue("DESTINATION_INTERFACE_MISMATCH") ? {
      key: "destination-interface",
      title: "Destination Interface",
      text: "Mindestens ein Consumer hat kein passendes Ziel-Interface. Der Wizard kann die beste technische Schnittstelle vorbelegen.",
      actions: <>
        <button className="button primary tiny" onClick={applyBestDestinationInterfaces} type="button">Ziel-Interfaces setzen</button>
        <button className="button secondary tiny" onClick={() => setStep(2)} type="button">Ziele prüfen</button>
      </>,
    } : null,
    hasIssue("PAYLOAD_UNSPECIFIED") ? {
      key: "payload",
      title: "Payload fehlt",
      text: "Die Route braucht eine Message, ein Signal oder ein Topic. Der Wizard schlägt eine Message passend zu Sender, Namen und Bus vor.",
      actions: <>
        <button className="button primary tiny" onClick={applyBestPayload} type="button">Payload vorschlagen</button>
        <button className="button secondary tiny" onClick={() => setStep(1)} type="button">Payload auswählen</button>
      </>,
    } : null,
  ].filter(Boolean);

  if (!issues.length && !repairs.length) return null;

  return (
    <div className="routing-repair-panel">
      <strong>Reparaturvorschläge</strong>
      {repairs.length ? repairs.map((repair) => repair && (
        <section key={repair.key}>
          <div>
            <h3>{repair.title}</h3>
            <p>{repair.text}</p>
          </div>
          <div className="routing-repair-actions">{repair.actions}</div>
        </section>
      )) : <small>Keine automatische Reparatur erkannt. Prüfe die Route manuell in den vorherigen Schritten.</small>}
    </div>
  );
}

function AiSuggestionList({ suggestions, value, onPick }: { suggestions: Array<{ id: string; label: string; confidence: number }>; value: string; onPick: (id: string) => void }) {
  if (!suggestions.length) return null;
  return <div className="routing-ai-suggestions full-width"><span>KI-Vorschläge</span>{suggestions.map((item) => <button className={item.id === value ? "active" : ""} key={item.id} onClick={() => onPick(item.id)} type="button"><strong>{item.confidence}%</strong><span>{item.label}</span><small>Namensnähe, Protokoll und vorhandene Route</small></button>)}</div>;
}

function RoutingWizardSummary({ route, sourceId, sourceInterfaceId, destinationIds, destinationInterfaces, hardware, interfaces, message, signals, timing }: {
  route: RoutingEntry;
  sourceId: string;
  sourceInterfaceId: string;
  destinationIds: string[];
  destinationInterfaces: Record<string, string>;
  hardware: HardwareNode[];
  interfaces: EngInterface[];
  message?: EngMessage;
  signals: EngSignal[];
  timing: { cycle: string; timeout: string; latency: string; jitter: string };
}) {
  const nodeName = (id: string) => hardware.find((item) => item.id === id)?.name ?? id;
  const ifaceName = (id: string) => (interfaces.find((item) => item.id === id)?.name ?? id) || "Nicht gesetzt";
  return <div className="routing-wizard-summary"><section><h3>Pfad</h3><dl><dt>Producer</dt><dd>{nodeName(sourceId)}</dd><dt>Source Interface</dt><dd>{ifaceName(sourceInterfaceId)}</dd><dt>Consumer</dt><dd>{destinationIds.map(nodeName).join(", ") || "Nicht gesetzt"}</dd><dt>Destination Interfaces</dt><dd>{destinationIds.map((id) => `${nodeName(id)}: ${ifaceName(destinationInterfaces[id] ?? "")}`).join(" · ") || "Nicht gesetzt"}</dd></dl></section><section><h3>Payload</h3><dl><dt>Message</dt><dd>{message?.name ?? route.payload.topic ?? route.payload.data_object ?? "Nicht gesetzt"}</dd><dt>Signals</dt><dd>{signals.map((item) => item.display_name || item.name).join(", ") || "Keine Signale gewählt"}</dd></dl></section><section><h3>Timing</h3><dl><dt>Cycle</dt><dd>{timing.cycle || "Nicht gesetzt"} ms</dd><dt>Timeout</dt><dd>{timing.timeout || "Nicht gesetzt"} ms</dd><dt>Latency</dt><dd>{timing.latency || "Nicht gesetzt"} ms</dd><dt>Jitter</dt><dd>{timing.jitter || "Nicht gesetzt"} ms</dd></dl></section></div>;
}

function interfaceProtocol(type: string) { return ({ CAN: "CAN", CAN_FD: "CAN_FD", LIN: "LIN", FlexRay: "FLEXRAY", Ethernet: "ETHERNET", EtherCAT: "ETHERCAT", ProfiNET: "PROFINET", ModbusTCP: "MODBUS", ModbusRTU: "MODBUS", OPCUA: "OPC_UA" } as Record<string, string>)[type] ?? "CUSTOM"; }
function networkId(item?: EngInterface) { return item ? `network-${String(item.configuration?.bus ?? item.interface_type).toLowerCase()}` : null; }
function Status({ value }: { value: string }) { return <span className={`routing-status ${value.toLowerCase().replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>; }
function EmptyRouting({ text }: { text: string }) { return <div className="empty-result routing-empty"><span className="empty-icon">◇</span><strong>{text}</strong></div>; }
