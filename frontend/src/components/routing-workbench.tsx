"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listAllEngineeringObjects } from "@/lib/engineering-api";
import {
  acceptRoutingProposal,
  approveRoutes,
  createRoute,
  deleteRoute,
  generateRoutes,
  getRoutingSchema,
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
import { resumePendingEngineeringAgentTask } from "@/lib/agent-task-events";
import { routingApprovalProgress } from "@/lib/routing-approval";
import { readActiveProjectId } from "@/lib/user-settings";
import { notifyWorkflowChanged } from "./workflow-header";

const VIEWS = ["Table", "Network Proposals", "Graph", "Matrix", "AI Proposals", "Validation", "Conflicts"] as const;
type RoutingView = (typeof VIEWS)[number];
type RoutingEditorSeed = {
  sourceNodeId?: string;
  destinationNodeId?: string;
  sourceInterfaceId?: string;
  destinationInterfaceId?: string;
  name?: string;
  topic?: string;
};
const ROUTING_PROPOSAL_PAGE_SIZE = 50;

const isHardware = (item: object): item is HardwareNode => "device_type" in item;
const isInterface = (item: object): item is EngInterface => "interface_type" in item;
const isMessage = (item: object): item is EngMessage => "interface_id" in item && "message_id_hex" in item;
const isSignal = (item: object): item is EngSignal => "message_id" in item && "length_bits" in item;

async function updateRoutePatches(patches: Array<{ id: string; payload: Record<string, unknown> }>) {
  let cursor = 0;
  const workers = Array.from({ length: Math.min(4, patches.length) }, async () => {
    while (cursor < patches.length) {
      const patch = patches[cursor++];
      await updateRoute(patch.id, patch.payload);
    }
  });
  await Promise.all(workers);
}

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
  const [bulkEditor, setBulkEditor] = useState(false);
  const [editor, setEditor] = useState<{ mode: "manual" | "ai"; route?: RoutingEntry; seed?: RoutingEditorSeed } | null>(null);
  const [wizardRoute, setWizardRoute] = useState<RoutingEntry | null>(null);
  const [handledEditRoute, setHandledEditRoute] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);

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
    return routeItems;
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
  const nodeTypes = useMemo(() => new Map(hardware.map((node) => [node.id, node.device_type])), [hardware]);
  const messageNames = useMemo(() => new Map(messages.map((message) => [message.id, message.name])), [messages]);
  const signalNames = useMemo(() => new Map(signals.map((signal) => [signal.id, signal.display_name || signal.name])), [signals]);
  const interfaceNetworks = useMemo(() => new Map(interfaces.map((item) => [
    item.id,
    String(item.configuration.network_id ?? item.configuration.network ?? "—"),
  ])), [interfaces]);
  const interfaceNames = useMemo(() => new Map(interfaces.map((item) => [item.id, item.name])), [interfaces]);
  const approvalProgress = useMemo(() => routingApprovalProgress(routes), [routes]);
  const validCount = approvalProgress.routes.filter((route) => route.validation?.valid).length;
  const approvedCount = approvalProgress.approved;
  const conflictCount = approvalProgress.routes.filter(
    (route) => route.validation?.valid === false || route.status === "CONFLICT",
  ).length;
  const networkProposals = useMemo(
    () => routes.filter((route) => ["NETWORK_EDITOR", "AI_GENERATED", "AI_MODIFIED"].includes(route.origin)),
    [routes],
  );
  const confirmableRoutes = approvalProgress.routes.filter(
    (route) => route.validation?.valid
      && route.approval_state === "PENDING"
      && !["OUTDATED", "SUPERSEDED", "REJECTED", "DEPRECATED"].includes(route.status),
  );
  const checkedRoutes = useMemo(
    () => routes.filter((route) => checked.has(route.id)),
    [checked, routes],
  );

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
      const refreshedRoutes = await refresh();
      notifyWorkflowChanged();
      setChecked(new Set());
      const refreshedApprovalProgress = routingApprovalProgress(refreshedRoutes);
      const resumed = refreshedApprovalProgress.complete
        && resumePendingEngineeringAgentTask(readActiveProjectId());
      setNotice({
        type: "success",
        text: resumed ? `${success} Der Engineering-Wizard setzt den Auftrag jetzt fort.` : success,
      });
      return true;
    } catch (error) {
      setNotice({ type: "error", text: error instanceof Error ? error.message : "Routing-Aktion fehlgeschlagen." });
      return false;
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

  function setCheckedRoutes(routeIds: string[], value: boolean) {
    setChecked((current) => {
      const next = new Set(current);
      routeIds.forEach((routeId) => value ? next.add(routeId) : next.delete(routeId));
      return next;
    });
  }

  return (
    <>
      <div className="routing-summary" aria-label="Routing-Kennzahlen">
        <div><span>Aktuelle Routen</span><strong>{approvalProgress.total}</strong></div>
        <div><span>Valide</span><strong>{validCount}</strong></div>
        <div><span>Freigegeben</span><strong>{approvedCount}</strong></div>
        <div><span>Konflikte</span><strong>{conflictCount}</strong></div>
      </div>

      <div className="routing-commandbar">
        <div className="routing-primary-actions">
          <button className="button primary" onClick={() => setEditor({ mode: "manual" })} type="button">+ Route</button>
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
          {(view === "Table" || view === "Network Proposals") && checkedRoutes.length > 0 && (
            <div aria-label="Routing-Auswahl" className="routing-selection-bar" role="toolbar">
              <span><strong>{checkedRoutes.length}</strong> Routen ausgewählt</span>
              <div>
                <button className="button primary tiny" disabled={Boolean(busy)} onClick={() => setBulkEditor(true)} type="button">
                  Auswahl bearbeiten
                </button>
                <button className="button secondary tiny" disabled={Boolean(busy)} onClick={() => setChecked(new Set())} type="button">
                  Auswahl aufheben
                </button>
              </div>
            </div>
          )}
          {(view === "Table" || view === "Network Proposals") && (
            <RoutingTable
              checked={checked}
              interfaceNames={interfaceNames}
              interfaceNetworks={interfaceNetworks}
              messageNames={messageNames}
              nodeNames={nodeNames}
              onCheck={toggleChecked}
              onCheckMany={setCheckedRoutes}
              onSelect={setSelected}
              routes={view === "Network Proposals" ? networkProposals : routes}
              selectedId={selected?.id}
              signalNames={signalNames}
            />
          )}
          {view === "Graph" && <RoutingGraph nodeNames={nodeNames} onSelect={setSelected} routes={routes} signalNames={signalNames} />}
          {view === "Matrix" && (
            <RoutingMatrix
              interfaceNames={interfaceNames}
              interfaceNetworks={interfaceNetworks}
              interfaces={interfaces}
              nodeNames={nodeNames}
              nodeTypes={nodeTypes}
              onCreate={(seed) => setEditor({ mode: "manual", seed })}
              onEdit={setWizardRoute}
              onSelect={setSelected}
              routes={routes}
            />
          )}
          {view === "AI Proposals" && (
            <RoutingProposals
              interfaceNames={interfaceNames}
              interfaceNetworks={interfaceNetworks}
              messageNames={messageNames}
              nodeNames={nodeNames}
              onAccept={(proposal, index) => void act("accept", () => acceptRoutingProposal(proposal.proposal_id, [index]), "Vorschlag als Draft übernommen.")}
              onSelect={setSelected}
              proposals={proposals}
              signalNames={signalNames}
            />
          )}
          {view === "Validation" && <RoutingValidationList nodeNames={nodeNames} onSelect={setSelected} routes={routes} />}
          {view === "Conflicts" && <RoutingValidationList conflicts nodeNames={nodeNames} onSelect={setSelected} routes={routes} />}
        </section>

        <aside className="routing-side-column">
          <RoutingDetail
            interfaceNames={interfaceNames}
            interfaceNetworks={interfaceNetworks}
            messageNames={messageNames}
            nodeNames={nodeNames}
            onApprove={(route) => void act("approve", () => approveRoutes([route.id]), `${route.route_code} bestätigt.`)}
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
              <button disabled={confirmableRoutes.length === 0 || Boolean(busy)} onClick={() => void act("approve-all", () => approveRoutes(confirmableRoutes.map((route) => route.id)), "Alle validen Routing-Vorschläge bestätigt.")} type="button">Confirm All Valid</button>
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
          onDelete={editor.route ? () => act("delete", async () => {
            if (!canDeleteRoute(editor.route!)) {
              await rejectRoutes([editor.route!.id], "Freigabe vor dem Löschen zurückgezogen.");
            }
            await deleteRoute(editor.route!.id);
          }, `${editor.route!.route_code} gelöscht.`).then(() => setEditor(null)) : undefined}
          onDuplicate={editor.route ? () => act("duplicate", () => createRoute({
            ...editor.route,
            id: undefined,
            route_code: undefined,
            name: `${editor.route!.name} Kopie`,
            status: "DRAFT",
            origin: "DERIVED",
            approval_state: "PENDING",
            validation: {},
            actor: "routing-ui",
          }), "Route dupliziert.").then(() => setEditor(null)) : undefined}
          onGenerate={(payload) => act("generate", () => generateRoutes(payload), "RoutingProposal erzeugt.").then(() => setEditor(null))}
          onSave={(payload) => act("save", () => editor.route ? updateRoute(editor.route.id, payload) : createRoute(payload), editor.route ? "Route aktualisiert." : "Route als Draft gespeichert.").then(() => setEditor(null))}
          route={editor.route}
          routes={routes}
          schema={schema}
          seed={editor.seed}
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
          routes={routes}
          schema={schema}
          signals={signals}
        />
      )}
      {bulkEditor && schema && checkedRoutes.length > 0 && (
        <RoutingBulkEditDialog
          onClose={() => setBulkEditor(false)}
          onSave={async (patches) => {
            const saved = await act(
              "bulk-edit",
              () => updateRoutePatches(patches),
              `${patches.length} Routen gemeinsam aktualisiert. Auswahl bitte erneut validieren.`,
            );
            if (saved) setBulkEditor(false);
          }}
          routes={checkedRoutes}
          schema={schema}
        />
      )}
    </>
  );
}

function canDeleteRoute(route: RoutingEntry) {
  return route.approval_state !== "APPROVED" && !["APPROVED", "RELEASED"].includes(route.status);
}

function canonicalRouteLabel(route: RoutingEntry, nodeNames: Map<string, string>) {
  const producer = nodeNames.get(route.source.node_id) ?? route.source.node_id;
  const consumers = route.destinations
    .map((destination) => nodeNames.get(destination.node_id) ?? destination.node_id)
    .join(", ") || "Kein Consumer";
  return `${producer} → ${consumers}`;
}

function routeAlias(route: RoutingEntry, nodeNames: Map<string, string>) {
  const normalize = (value: string) => value.toLocaleLowerCase("de-DE").replace(/[^a-z0-9]+/g, "");
  const canonical = canonicalRouteLabel(route, nodeNames);
  return normalize(route.name) === normalize(canonical) ? "" : route.name;
}

function RoutingSelectionCheckbox({ checked, indeterminate, onChange }: { checked: boolean; indeterminate: boolean; onChange: (value: boolean) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <input
      aria-label="Sichtbare Routen auswählen"
      checked={checked}
      onChange={(event) => onChange(event.target.checked)}
      ref={ref}
      type="checkbox"
    />
  );
}

function RoutingTable({ routes, checked, selectedId, nodeNames, messageNames, signalNames, interfaceNames, interfaceNetworks, onCheck, onCheckMany, onSelect }: {
  routes: RoutingEntry[];
  checked: Set<string>;
  selectedId?: string;
  nodeNames: Map<string, string>;
  messageNames: Map<string, string>;
  signalNames: Map<string, string>;
  interfaceNames: Map<string, string>;
  interfaceNetworks: Map<string, string>;
  onCheck: (id: string) => void;
  onCheckMany: (ids: string[], value: boolean) => void;
  onSelect: (route: RoutingEntry) => void;
}) {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const tableScrollRef = useRef<HTMLDivElement | null>(null);
  const pageSize = 25;
  const columns: Array<{ key: keyof ReturnType<typeof routeCells> | "select"; label: string; filterable: boolean; filterType?: "text" | "select" }> = [
    { key: "select", label: "Select", filterable: false },
    { key: "route", label: "Route", filterable: true },
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
    const canonicalLabel = canonicalRouteLabel(route, nodeNames);
    const routeMessageIds = routingMessageIds(route);
    return {
      route: `${canonicalLabel} ${routeAlias(route, nodeNames)} ${route.route_code} r${route.revision}`,
      producer: nodeNames.get(route.source.node_id) ?? route.source.node_id,
      sourceInterface: interfaceNames.get(route.source.interface_id ?? "") ?? route.source.interface_id ?? "—",
      payload: route.payload.topic ?? route.payload.data_object ?? (routeMessageIds.length === 1 ? "Message" : routeMessageIds.length > 1 ? `${routeMessageIds.length} Messages` : "—"),
      message: routeMessageIds.map((id) => messageNames.get(id)).filter(Boolean).join(", ") || "—",
      signals: route.payload.signal_ids.slice(0, 2).map((id) => signalNames.get(id) ?? id).join(", ") || "—",
      network: route.source.network_id ?? interfaceNetworks.get(route.source.interface_id ?? "") ?? "—",
      gateway: route.route.gateways.map((item) => typeof item === "string" ? nodeNames.get(item) ?? item : item.name ?? nodeNames.get(item.node_id ?? "")).join(", ") || "Direkt",
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
  const visibleIds = visibleRoutes.map((route) => route.id);
  const checkedVisibleCount = visibleIds.filter((id) => checked.has(id)).length;

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
          <tr>{columns.map((column) => (
            <th key={column.key}>
              {column.key === "select" ? (
                <RoutingSelectionCheckbox
                  checked={visibleIds.length > 0 && checkedVisibleCount === visibleIds.length}
                  indeterminate={checkedVisibleCount > 0 && checkedVisibleCount < visibleIds.length}
                  onChange={(value) => onCheckMany(visibleIds, value)}
                />
              ) : column.label}
            </th>
          ))}</tr>
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
            <td className="routing-route-cell">
              <strong>{canonicalRouteLabel(route, nodeNames)}</strong>
              {routeAlias(route, nodeNames) && <span>{routeAlias(route, nodeNames)}</span>}
              <small>{route.route_code} · r{route.revision}</small>
            </td>
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
    return <div className="routing-graph-route" key={route.id}><button className="routing-graph-code" onClick={() => onSelect(route)} type="button"><strong>{canonicalRouteLabel(route, nodeNames)}</strong>{routeAlias(route, nodeNames) && <small>{routeAlias(route, nodeNames)}</small>}<span>{route.route_code}</span></button><div className="routing-graph-path">{path.map((item, index) => <span className="routing-graph-step" key={`${item.kind}-${index}`}><button onClick={() => onSelect(route)} type="button"><small>{item.kind}</small><strong>{item.label}</strong></button>{index < path.length - 1 && <i aria-hidden="true">→</i>}</span>)}</div></div>;
  })}</div>;
}

type RoutingMatrixMode = "ecu" | "function" | "interface";
type MatrixAxis = { key: string; label: string; type: string; nodeId?: string; interfaceId?: string; topic?: string };

const routingMatrixModes: Array<{ key: RoutingMatrixMode; label: string }> = [
  { key: "ecu", label: "ECU" },
  { key: "function", label: "Funktion" },
  { key: "interface", label: "Interface" },
];

function compareGerman(a: string, b: string) {
  return a.localeCompare(b, "de-DE", { numeric: true, sensitivity: "base" });
}

function routeNetworkLabel(route: RoutingEntry, interfaceNetworks: Map<string, string>) {
  const networks = [
    route.source.network_id ?? interfaceNetworks.get(route.source.interface_id ?? ""),
    ...route.destinations.map((destination) => destination.network_id ?? interfaceNetworks.get(destination.interface_id ?? "")),
  ].filter((value): value is string => Boolean(value && value !== "—"));
  const uniqueNetworks = [...new Set(networks)];
  return uniqueNetworks.length ? uniqueNetworks.map(readableNetworkLabel).join(" → ") : readableNetworkLabel(route.source.protocol ?? "Direkt");
}

function readableNetworkLabel(value: string) {
  const compact = value
    .replace(/^network[-_]/i, "")
    .replace(/[-_][0-9a-f]{4,}(?:[-_][0-9a-f]{4,})*$/i, "")
    .replace(/automotive[-_\s]+/i, "")
    .replace(/some[-_\s]*ip/i, "SOME/IP")
    .replace(/can[-_\s]*fd/i, "CAN FD")
    .replace(/ethernet/i, "Ethernet")
    .replace(/lin/i, "LIN")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return compact || value;
}

function routeInterfaceLabel(route: RoutingEntry, interfaceNames: Map<string, string>) {
  const source = interfaceNames.get(route.source.interface_id ?? "") ?? route.source.interface_id ?? "Quelle";
  const destinations = route.destinations
    .map((destination) => interfaceNames.get(destination.interface_id ?? "") ?? destination.interface_id)
    .filter(Boolean)
    .join(", ") || "Ziel";
  return `${source} → ${destinations}`;
}

function matrixCellTitle(route: RoutingEntry, interfaceNames: Map<string, string>, interfaceNetworks: Map<string, string>) {
  const network = routeNetworkLabel(route, interfaceNetworks);
  const iface = routeInterfaceLabel(route, interfaceNames);
  const protocol = route.source.protocol ? ` · ${route.source.protocol}` : "";
  return `${network}${protocol}\n${iface}`;
}

function systemNameForRoute(route: RoutingEntry, nodeNames: Map<string, string>) {
  return nodeNames.get(route.source.node_id) ?? route.source.node_id;
}

function functionNameForRoute(route: RoutingEntry) {
  const value = route.payload.topic ?? route.payload.data_object ?? route.name;
  return value.split(/\s*(?:→|->)\s*/)[0]?.trim() || value;
}

function sourceInterfaceAxis(route: RoutingEntry, interfaceNames: Map<string, string>, nodeNames: Map<string, string>): MatrixAxis {
  const interfaceId = route.source.interface_id;
  return {
    key: interfaceId ? `interface:${interfaceId}` : `source:${route.source.node_id}`,
    label: interfaceId ? interfaceNames.get(interfaceId) ?? interfaceId : `${nodeNames.get(route.source.node_id) ?? route.source.node_id} · ohne Interface`,
    interfaceId: interfaceId ?? undefined,
    nodeId: route.source.node_id,
    type: "",
  };
}

function destinationInterfaceAxis(route: RoutingEntry, destination: RoutingEntry["destinations"][number], interfaceNames: Map<string, string>, nodeNames: Map<string, string>): MatrixAxis {
  const interfaceId = destination.interface_id;
  return {
    key: interfaceId ? `interface:${interfaceId}` : `destination:${destination.node_id}`,
    label: interfaceId ? interfaceNames.get(interfaceId) ?? interfaceId : `${nodeNames.get(destination.node_id) ?? destination.node_id} · ohne Interface`,
    interfaceId: interfaceId ?? undefined,
    nodeId: destination.node_id,
    type: "",
  };
}

function uniqueSortedAxes(axes: MatrixAxis[]) {
  return [...new Map(axes.map((axis) => [axis.key, axis])).values()].sort((a, b) => compareGerman(a.label, b.label));
}

function RoutingMatrix({ routes, nodeNames, nodeTypes, interfaceNames, interfaceNetworks, interfaces, onCreate, onEdit, onSelect }: {
  routes: RoutingEntry[];
  nodeNames: Map<string, string>;
  nodeTypes: Map<string, string>;
  interfaceNames: Map<string, string>;
  interfaceNetworks: Map<string, string>;
  interfaces: EngInterface[];
  onCreate: (seed: RoutingEditorSeed) => void;
  onEdit: (route: RoutingEntry) => void;
  onSelect: (route: RoutingEntry) => void;
}) {
  const [mode, setMode] = useState<RoutingMatrixMode>("ecu");
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLocaleLowerCase("de-DE");
  const labelForNode = useCallback((id: string) => nodeNames.get(id) ?? id, [nodeNames]);
  const interfaceById = useMemo(() => new Map(interfaces.map((item) => [item.id, item])), [interfaces]);

  function openSeededEditor(source: MatrixAxis, destination: MatrixAxis) {
    const sourceNodeId = source.nodeId ?? (source.interfaceId ? interfaceById.get(source.interfaceId)?.hardware_node_id ?? undefined : undefined) ?? source.key;
    const destinationNodeId = destination.nodeId ?? (destination.interfaceId ? interfaceById.get(destination.interfaceId)?.hardware_node_id ?? undefined : undefined);
    const sourceInterface = source.interfaceId
      ? interfaceById.get(source.interfaceId)
      : interfaces.find((item) => item.hardware_node_id === sourceNodeId);
    const sourceProtocol = sourceInterface ? interfaceProtocol(sourceInterface.interface_type) : undefined;
    const destinationInterface = destination.interfaceId
      ? interfaceById.get(destination.interfaceId)
      : interfaces.find((item) => item.hardware_node_id === destinationNodeId && interfaceProtocol(item.interface_type) === sourceProtocol)
        ?? interfaces.find((item) => item.hardware_node_id === destinationNodeId);
    onCreate({
      sourceNodeId,
      destinationNodeId,
      sourceInterfaceId: sourceInterface?.id,
      destinationInterfaceId: destinationInterface?.id,
      name: destination.topic ? `${source.label} → ${destination.label}` : undefined,
      topic: destination.topic,
    });
  }

  const filteredRoutes = useMemo(() => {
    if (!normalizedQuery) return routes;
    return routes.filter((route) => {
      const labels = [
        canonicalRouteLabel(route, nodeNames),
        route.name,
        route.route_code,
        route.source.network_id ?? "",
        route.source.protocol ?? "",
        routeNetworkLabel(route, interfaceNetworks),
        routeInterfaceLabel(route, interfaceNames),
        systemNameForRoute(route, nodeNames),
        functionNameForRoute(route),
        ...route.destinations.map((destination) => labelForNode(destination.node_id)),
      ];
      return labels.some((label) => label.toLocaleLowerCase("de-DE").includes(normalizedQuery));
    });
  }, [interfaceNames, interfaceNetworks, labelForNode, nodeNames, normalizedQuery, routes]);
  const matrixSummary = useMemo(() => ({
    columns: new Set(filteredRoutes.flatMap((route) => route.destinations.map((item) => item.node_id))).size,
    networks: new Set(filteredRoutes.map((route) => routeNetworkLabel(route, interfaceNetworks))).size,
    rows: new Set(filteredRoutes.map((route) => route.source.node_id)).size,
  }), [filteredRoutes, interfaceNetworks]);

  if (!routes.length) return <EmptyRouting text="Kommunikationsmatrix ist noch leer." />;

  if (mode === "function") {
    const rows = uniqueSortedAxes(filteredRoutes.map((route) => ({
      key: route.source.node_id,
      label: systemNameForRoute(route, nodeNames),
      nodeId: route.source.node_id,
      type: nodeTypes.get(route.source.node_id) ?? "",
    })));
    const columns = uniqueSortedAxes(filteredRoutes.map((route) => ({
      key: functionNameForRoute(route),
      label: functionNameForRoute(route),
      topic: functionNameForRoute(route),
      type: "",
    })));
    const cellMap = new Map<string, RoutingEntry[]>();
    filteredRoutes.forEach((route) => {
      const key = `${route.source.node_id}\u0000${functionNameForRoute(route)}`;
      const current = cellMap.get(key) ?? [];
      current.push(route);
      cellMap.set(key, current);
    });
    return (
      <div className="routing-matrix-panel">
        <MatrixToolbar
          mode={mode}
          query={query}
          resultCount={filteredRoutes.length}
          setMode={setMode}
          setQuery={setQuery}
        />
        <MatrixSummary columnLabel="Funktionen" columns={columns.length} networks={matrixSummary.networks} rowLabel="Systeme" rows={rows.length} />
        <div className="routing-table-wrap routing-matrix-wrap">
          <table className="routing-matrix">
            <thead>
              <tr><th>System</th>{columns.map((item) => <th key={item.key}><MatrixAxisLabel label={item.label} type={item.type} /></th>)}</tr>
            </thead>
            <tbody>
              {rows.map((system) => (
                <tr key={system.key}>
                  <th><MatrixAxisLabel label={system.label} type={system.type} /></th>
                  {columns.map((fn) => {
                    const matches = cellMap.get(`${system.key}\u0000${fn.key}`) ?? [];
                    return <MatrixCell key={fn.key} destination={fn} interfaceNames={interfaceNames} interfaceNetworks={interfaceNetworks} matches={matches} onCreate={openSeededEditor} onEdit={onEdit} onSelect={onSelect} source={system} />;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredRoutes.length === 0 && <div className="routing-filter-empty">Keine Routen passen zur Suche.</div>}
      </div>
    );
  }

  if (mode === "interface") {
    const rows = uniqueSortedAxes(filteredRoutes.map((route) => sourceInterfaceAxis(route, interfaceNames, nodeNames)));
    const columns = uniqueSortedAxes(filteredRoutes.flatMap((route) => route.destinations.map((destination) =>
      destinationInterfaceAxis(route, destination, interfaceNames, nodeNames),
    )));
    const cellMap = new Map<string, RoutingEntry[]>();
    filteredRoutes.forEach((route) => {
      const row = sourceInterfaceAxis(route, interfaceNames, nodeNames);
      route.destinations.forEach((destination) => {
        const column = destinationInterfaceAxis(route, destination, interfaceNames, nodeNames);
        const key = `${row.key}\u0000${column.key}`;
        const current = cellMap.get(key) ?? [];
        current.push(route);
        cellMap.set(key, current);
      });
    });
    return (
      <div className="routing-matrix-panel">
        <MatrixToolbar
          mode={mode}
          query={query}
          resultCount={filteredRoutes.length}
          setMode={setMode}
          setQuery={setQuery}
        />
        <MatrixSummary columnLabel="Ziel-Interfaces" columns={columns.length} networks={matrixSummary.networks} rowLabel="Quell-Interfaces" rows={rows.length} />
        <div className="routing-table-wrap routing-matrix-wrap">
          <table className="routing-matrix">
            <thead>
              <tr><th>Quell-Interface</th>{columns.map((item) => <th key={item.key}><MatrixAxisLabel label={item.label} type={item.type} /></th>)}</tr>
            </thead>
            <tbody>
              {rows.map((source) => (
                <tr key={source.key}>
                  <th><MatrixAxisLabel label={source.label} type={source.type} /></th>
                  {columns.map((destination) => {
                    const matches = cellMap.get(`${source.key}\u0000${destination.key}`) ?? [];
                    return <MatrixCell key={destination.key} destination={destination} interfaceNames={interfaceNames} interfaceNetworks={interfaceNetworks} matches={matches} onCreate={openSeededEditor} onEdit={onEdit} onSelect={onSelect} source={source} />;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredRoutes.length === 0 && <div className="routing-filter-empty">Keine Routen passen zur Suche.</div>}
      </div>
    );
  }

  const sources = uniqueSortedAxes([...new Set(filteredRoutes.map((route) => route.source.node_id))].map((id) => ({
    key: id,
    label: labelForNode(id),
    nodeId: id,
    type: nodeTypes.get(id) ?? "",
  })));
  const destinations = uniqueSortedAxes([...new Set(filteredRoutes.flatMap((route) => route.destinations.map((item) => item.node_id)))].map((id) => ({
    key: id,
    label: labelForNode(id),
    nodeId: id,
    type: nodeTypes.get(id) ?? "",
  })));
  const cellMap = new Map<string, RoutingEntry[]>();
  filteredRoutes.forEach((route) => {
    route.destinations.forEach((destination) => {
      const key = `${route.source.node_id}\u0000${destination.node_id}`;
      const current = cellMap.get(key) ?? [];
      current.push(route);
      cellMap.set(key, current);
    });
  });
  return (
    <div className="routing-matrix-panel">
      <MatrixToolbar
        mode={mode}
        query={query}
        resultCount={filteredRoutes.length}
        setMode={setMode}
        setQuery={setQuery}
      />
      <MatrixSummary columnLabel="Ziel-ECUs" columns={destinations.length} networks={matrixSummary.networks} rowLabel="Quell-ECUs" rows={sources.length} />
      <div className="routing-table-wrap routing-matrix-wrap">
        <table className="routing-matrix">
          <thead>
            <tr><th>Quell-ECU</th>{destinations.map((item) => <th key={item.key}><MatrixAxisLabel label={item.label} type={item.type} /></th>)}</tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <tr key={source.key}>
                <th><MatrixAxisLabel label={source.label} type={source.type} /></th>
                {destinations.map((destination) => {
                  const matches = cellMap.get(`${source.key}\u0000${destination.key}`) ?? [];
                  return <MatrixCell key={destination.key} destination={destination} interfaceNames={interfaceNames} interfaceNetworks={interfaceNetworks} matches={matches} onCreate={openSeededEditor} onEdit={onEdit} onSelect={onSelect} source={source} />;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filteredRoutes.length === 0 && <div className="routing-filter-empty">Keine Routen passen zur Suche.</div>}
    </div>
  );
}

function MatrixAxisLabel({ label, type }: { label: string; type: string }) {
  const role = type === "SensorController" ? "Sensor" : type === "ActuatorController" ? "Aktor" : type === "ECU" ? "ECU" : type === "Gateway" ? "Gateway" : "";
  return (
    <span className="routing-matrix-axis-label">
      {role && <i aria-label={`Teilnehmertyp: ${role}`} className={`routing-matrix-role routing-matrix-role-${role.toLowerCase()}`} title={`Teilnehmertyp: ${role}`}>{role}</i>}
      <span>{label}</span>
    </span>
  );
}

function MatrixSummary({ rows, columns, networks, rowLabel, columnLabel }: { rows: number; columns: number; networks: number; rowLabel: string; columnLabel: string }) {
  return (
    <div className="routing-matrix-summary" aria-label="Matrix-Zusammenfassung">
      <span><b>{rows}</b> {rowLabel}</span>
      <span><b>{columns}</b> {columnLabel}</span>
      <span><b>{networks}</b> Netze</span>
    </div>
  );
}

function MatrixToolbar({ mode, query, resultCount, setMode, setQuery }: {
  mode: RoutingMatrixMode;
  query: string;
  resultCount: number;
  setMode: (mode: RoutingMatrixMode) => void;
  setQuery: (query: string) => void;
}) {
  return (
    <div className="routing-matrix-toolbar">
      <div className="routing-matrix-mode" role="tablist" aria-label="Matrix-Darstellung">
        {routingMatrixModes.map((item) => (
          <button aria-selected={mode === item.key} className={mode === item.key ? "active" : ""} key={item.key} onClick={() => setMode(item.key)} role="tab" type="button">
            {item.label}
          </button>
        ))}
      </div>
      <label>
        <span>Suche</span>
        <input
          aria-label="Matrix durchsuchen"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="z.B. Wegfahrsperre, Keyless, LIN"
          type="search"
          value={query}
        />
      </label>
      <div className="routing-matrix-count">
        <strong>{resultCount} Routen</strong>
        <span>vollständig im Scrollbereich</span>
      </div>
    </div>
  );
}

function MatrixCell({ matches, source, destination, interfaceNames, interfaceNetworks, onCreate, onEdit, onSelect }: {
  matches: RoutingEntry[];
  source: MatrixAxis;
  destination: MatrixAxis;
  interfaceNames: Map<string, string>;
  interfaceNetworks: Map<string, string>;
  onCreate: (source: MatrixAxis, destination: MatrixAxis) => void;
  onEdit: (route: RoutingEntry) => void;
  onSelect: (route: RoutingEntry) => void;
}) {
  if (!matches.length) {
    return (
      <td className="routing-matrix-empty">
        <button
          className="routing-matrix-empty-button"
          onClick={() => onCreate(source, destination)}
          title={`Route anlegen: ${source.label} → ${destination.label}`}
          type="button"
        >
          <span>+</span>
          <small>Anlegen</small>
        </button>
      </td>
    );
  }
  const first = matches[0];
  const networks = [...new Set(matches.map((route) => routeNetworkLabel(route, interfaceNetworks)))].slice(0, 2).join(", ");
  return (
    <td>
      <div className="routing-matrix-cell">
        <button
          className="routing-matrix-cell-button"
          onClick={() => onSelect(first)}
          title={matches.map((route) => `${route.route_code}: ${matrixCellTitle(route, interfaceNames, interfaceNetworks)}`).join("\n\n")}
          type="button"
        >
          <span>{matches.length}</span>
          <small>{networks}</small>
        </button>
        <button className="routing-matrix-cell-edit" onClick={() => onEdit(first)} title="Schnittpunkt im Wizard bearbeiten" type="button">
          Ändern
        </button>
      </div>
    </td>
  );
}

function RoutingProposals({
  interfaceNames,
  interfaceNetworks,
  messageNames,
  nodeNames,
  proposals,
  signalNames,
  onAccept,
  onSelect,
}: {
  interfaceNames: Map<string, string>;
  interfaceNetworks: Map<string, string>;
  messageNames: Map<string, string>;
  nodeNames: Map<string, string>;
  proposals: RoutingProposal[];
  signalNames: Map<string, string>;
  onAccept: (proposal: RoutingProposal, index: number) => void;
  onSelect: (route: RoutingEntry) => void;
}) {
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLocaleLowerCase("de-DE");
  const proposalRoutes = useMemo(() => proposals.flatMap((proposal) => proposal.generated_routes.map((route, index) => ({
    index,
    proposal,
    route,
  }))), [proposals]);
  const filtered = useMemo(() => {
    if (!normalizedQuery) return proposalRoutes;
    return proposalRoutes.filter(({ proposal, route }) => [
      proposal.status,
      proposal.model ?? "",
      canonicalRouteLabel(route, nodeNames),
      routeAlias(route, nodeNames),
      route.name,
      route.route_code,
      routeNetworkLabel(route, interfaceNetworks),
      routeInterfaceLabel(route, interfaceNames),
      ...(route.payload.message_ids ?? []).map((id) => messageNames.get(id) ?? id),
      ...route.payload.signal_ids.map((id) => signalNames.get(id) ?? id),
    ].some((label) => label.toLocaleLowerCase("de-DE").includes(normalizedQuery)));
  }, [interfaceNames, interfaceNetworks, messageNames, nodeNames, normalizedQuery, proposalRoutes, signalNames]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / ROUTING_PROPOSAL_PAGE_SIZE));
  const visible = filtered.slice((page - 1) * ROUTING_PROPOSAL_PAGE_SIZE, page * ROUTING_PROPOSAL_PAGE_SIZE);
  const validCount = proposalRoutes.filter(({ route }) => route.validation?.valid).length;
  const approvedCount = proposals.filter((proposal) => proposal.status === "APPROVED").length;
  const confidenceValues = proposals.map((proposal) => proposal.confidence).filter((value): value is number => typeof value === "number");
  const averageConfidence = confidenceValues.length
    ? Math.round((confidenceValues.reduce((sum, value) => sum + value, 0) / confidenceValues.length) * 100)
    : null;

  useEffect(() => {
    setPage(1);
  }, [normalizedQuery, proposals.length]);

  if (!proposals.length) return <EmptyRouting text="Noch keine KI-Routingvorschläge vorhanden." />;
  return (
    <div className="routing-proposals">
      <section className="routing-proposal-overview" aria-label="KI-Vorschläge Übersicht">
        <div><span>Vorschlagsrouten</span><strong>{proposalRoutes.length}</strong></div>
        <div><span>Valide</span><strong>{validCount}</strong></div>
        <div><span>Freigegebene Batches</span><strong>{approvedCount}</strong></div>
        <div><span>Konfidenz</span><strong>{averageConfidence == null ? "—" : `${averageConfidence} %`}</strong></div>
      </section>
      <div className="routing-proposal-toolbar">
        <label>
          <span>Suche</span>
          <input
            aria-label="KI-Vorschläge durchsuchen"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Quelle, Ziel, Signal, Netz ..."
            type="search"
            value={query}
          />
        </label>
        <div>
          <strong>{visible.length} von {filtered.length}</strong>
          <button disabled={page === 1} onClick={() => setPage(Math.max(1, page - 1))} type="button">Zurück</button>
          <span>Seite {page} / {pageCount}</span>
          <button disabled={page === pageCount} onClick={() => setPage(Math.min(pageCount, page + 1))} type="button">Weiter</button>
        </div>
      </div>
      <div className="routing-proposal-list">
        {visible.map(({ proposal, route, index }) => {
          const messages = (route.payload.message_ids ?? []).map((id) => messageNames.get(id) ?? id).join(", ") || "—";
          const signals = route.payload.signal_ids.map((id) => signalNames.get(id) ?? id).join(", ") || "—";
          const isAccepted = proposal.status === "APPROVED";
          return (
            <article className="routing-proposal" key={`${proposal.proposal_id}-${index}`}>
              <button className="routing-proposal-main" onClick={() => onSelect(route)} type="button">
                <span>{proposal.status}</span>
                <strong>{canonicalRouteLabel(route, nodeNames)}</strong>
                {routeAlias(route, nodeNames) && <small>{routeAlias(route, nodeNames)}</small>}
              </button>
              <dl>
                <div><dt>Netz</dt><dd>{routeNetworkLabel(route, interfaceNetworks)}</dd></div>
                <div><dt>Interface</dt><dd>{routeInterfaceLabel(route, interfaceNames)}</dd></div>
                <div><dt>Nachricht</dt><dd>{messages}</dd></div>
                <div><dt>Signal</dt><dd>{signals}</dd></div>
              </dl>
              <div className="routing-proposal-actions">
                <Status value={route.validation?.valid ? "VALID" : "PENDING"} />
                <b>{proposal.confidence == null ? "—" : `${Math.round(proposal.confidence * 100)} %`}</b>
                <button disabled={isAccepted} onClick={() => onAccept(proposal, index)} type="button">
                  {isAccepted ? "Übernommen" : "Als Draft übernehmen"}
                </button>
              </div>
            </article>
          );
        })}
      </div>
      {filtered.length === 0 && <div className="routing-filter-empty">Keine KI-Vorschläge passen zur Suche.</div>}
    </div>
  );
}

function RoutingValidationList({ routes, nodeNames, onSelect, conflicts = false }: { routes: RoutingEntry[]; nodeNames: Map<string, string>; onSelect: (route: RoutingEntry) => void; conflicts?: boolean }) {
  const filtered = conflicts ? routes.filter((route) => route.validation?.valid === false || route.status === "CONFLICT") : routes;
  if (!filtered.length) return <EmptyRouting text={conflicts ? "Keine Routing-Konflikte vorhanden." : "Noch keine Routen zur Validierung vorhanden."} />;
  return <div className="routing-validation-list">{filtered.map((route) => <button key={route.id} onClick={() => onSelect(route)} type="button"><div><strong>{canonicalRouteLabel(route, nodeNames)}</strong><small>{route.route_code}{routeAlias(route, nodeNames) ? ` · ${route.name}` : ""}</small><span>{route.validation?.errors?.[0]?.message ?? route.validation?.warnings?.[0]?.message ?? "Technisch konsistent"}</span></div><Status value={route.validation?.valid ? "VALID" : route.validation?.valid === false ? "INVALID" : "PENDING"} /></button>)}</div>;
}

function RoutingDetail({ route, nodeNames, messageNames, signalNames, interfaceNames, interfaceNetworks, onEdit, onWizard, onValidate, onApprove, onReject }: {
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
    .join(", ") || "Direkt";
  const isOutdated = route.status === "OUTDATED";
  const isApproved = route.approval_state === "APPROVED";
  const isRejected = route.approval_state === "REJECTED" || route.status === "REJECTED";
  return (
    <div className="panel routing-detail">
      <p className="eyebrow">Route Details</p>
      <div className="routing-detail-title"><h3>{route.route_code}</h3><Status value={route.status} /></div>
      <strong>{canonicalRouteLabel(route, nodeNames)}</strong>
      {routeAlias(route, nodeNames) && <span className="routing-route-alias">{route.name}</span>}
      {route.origin === "NETWORK_EDITOR" && <p className="routing-network-origin">Proposed from Network Editor</p>}
      <div className="routing-detail-actions" aria-label="Route Aktionen">
        <section aria-label="Bearbeiten">
          <span>Bearbeiten</span>
          <div>
            <button className="button primary tiny" onClick={() => onWizard(route)} type="button">Wizard</button>
            <button className="button secondary tiny" onClick={() => onEdit(route)} type="button">Edit</button>
          </div>
        </section>
        <section aria-label="Prüfen und freigeben">
          <span>Prüfen &amp; Freigeben</span>
          <div>
            <button className="button secondary tiny routing-action-wide" disabled={isRejected || isOutdated} onClick={() => onValidate(route)} type="button">Validate</button>
            <button
              className="button primary tiny"
              disabled={isApproved || isRejected || isOutdated || route.validation?.valid !== true}
              onClick={() => onApprove(route)}
              type="button"
            >
              {isApproved ? "Approved" : route.origin === "NETWORK_EDITOR" ? "Confirm" : "Approve"}
            </button>
            <button
              className="button danger tiny"
              disabled={isRejected || isOutdated}
              onClick={() => onReject(route)}
              type="button"
            >
              {isRejected ? "Rejected" : "Reject"}
            </button>
          </div>
        </section>
        <section aria-label="Nachweise">
          <span>Nachweise</span>
          <div>
            <button className="button secondary tiny" type="button">Show Path</button>
            <button className="button secondary tiny" type="button">Evidence</button>
          </div>
        </section>
      </div>
      <dl>
        <dt>Producer</dt><dd>{nodeNames.get(route.source.node_id) ?? route.source.node_id}</dd>
        <dt>Source Interface</dt><dd>{sourceInterface}</dd>
        <dt>Network</dt><dd>{networks}</dd>
        <dt>Gateway</dt><dd>{gateways}</dd>
        <dt>Consumer</dt><dd>{route.destinations.map((item) => nodeNames.get(item.node_id) ?? item.node_id).join(", ")}</dd>
        <dt>Destination Interface</dt><dd>{destinationInterfaces}</dd>
        <dt>Messages</dt><dd>{routingMessageIds(route).map((id) => messageNames.get(id)).filter(Boolean).join(", ") || route.payload.topic || "—"}</dd>
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

function routingGatewayIds(route?: RoutingEntry) {
  return route?.route.gateways
    .map((gateway) => typeof gateway === "string" ? gateway : gateway.node_id ?? "")
    .filter(Boolean) ?? [];
}

function optionalText(value: string) {
  return value.trim() || null;
}

function routingMessageIds(route?: RoutingEntry) {
  if (!route) return [];
  return [...new Set([
    ...(route.payload.message_ids ?? []),
    ...(route.payload.message_id ? [route.payload.message_id] : []),
  ].filter(Boolean))];
}

function optionalNumber(value: string) {
  return value.trim() ? Number(value) : null;
}

function routingConditionsText(route?: RoutingEntry) {
  return JSON.stringify(route?.routing_policy.conditions ?? [], null, 2);
}

function parseRoutingConditions(value: string) {
  try {
    const parsed: unknown = value.trim() ? JSON.parse(value) : [];
    if (!Array.isArray(parsed) || parsed.some((item) => !item || typeof item !== "object" || Array.isArray(item))) {
      return { conditions: [] as Array<Record<string, unknown>>, error: "Conditions müssen ein JSON-Array aus Objekten sein." };
    }
    return { conditions: parsed as Array<Record<string, unknown>>, error: "" };
  } catch {
    return { conditions: [] as Array<Record<string, unknown>>, error: "Conditions enthalten kein gültiges JSON." };
  }
}

type RoutingPayloadMode = "message" | "topic" | "data_object";

function routingPayloadMode(route?: RoutingEntry): RoutingPayloadMode {
  if (route?.payload.topic) return "topic";
  if (route?.payload.data_object) return "data_object";
  return "message";
}

type BulkEditableField =
  | "protocol"
  | "priority"
  | "routingType"
  | "redundancy"
  | "cycle"
  | "timeout"
  | "latency"
  | "jitter";

type RoutingBulkChanges = Partial<{
  protocol: string;
  priority: RoutingEntry["route"]["priority"];
  routingType: string;
  redundancy: string;
  cycle: number;
  timeout: number;
  latency: number;
  jitter: number;
}>;

function bulkRoutePayload(route: RoutingEntry, changes: RoutingBulkChanges) {
  const payload: Record<string, unknown> = { actor: "routing-ui" };
  if (changes.protocol) {
    payload.source = { ...route.source, protocol: changes.protocol };
    payload.destinations = route.destinations.map((destination) => ({
      ...destination,
      protocol: changes.protocol,
    }));
  }
  if (changes.priority) payload.route = { ...route.route, priority: changes.priority };
  if (changes.routingType || changes.redundancy) {
    payload.routing_policy = {
      ...route.routing_policy,
      ...(changes.routingType ? { routing_type: changes.routingType } : {}),
      ...(changes.redundancy ? { redundancy: changes.redundancy } : {}),
    };
  }
  if ([changes.cycle, changes.timeout, changes.latency, changes.jitter].some((value) => value != null)) {
    payload.timing = {
      ...route.timing,
      ...(changes.cycle != null ? { cycle_time_ms: changes.cycle } : {}),
      ...(changes.timeout != null ? { timeout_ms: changes.timeout } : {}),
      ...(changes.latency != null ? { max_latency_ms: changes.latency } : {}),
      ...(changes.jitter != null ? { jitter_limit_ms: changes.jitter } : {}),
    };
  }
  return payload;
}

function RoutingBulkEditDialog({ routes, schema, onClose, onSave }: {
  routes: RoutingEntry[];
  schema: RoutingSchema;
  onClose: () => void;
  onSave: (patches: Array<{ id: string; payload: Record<string, unknown> }>) => Promise<void>;
}) {
  const first = routes[0];
  const [enabled, setEnabled] = useState<Set<BulkEditableField>>(new Set());
  const [protocol, setProtocol] = useState(first.source.protocol ?? schema.protocols[0] ?? "CAN_FD");
  const [priority, setPriority] = useState<RoutingEntry["route"]["priority"]>(first.route.priority ?? "NORMAL");
  const [routingType, setRoutingType] = useState(first.routing_policy.routing_type ?? schema.routing_types[0] ?? "UNICAST");
  const [redundancy, setRedundancy] = useState(first.routing_policy.redundancy ?? schema.redundancy_modes[0] ?? "NONE");
  const [cycle, setCycle] = useState(String(first.timing.cycle_time_ms ?? 100));
  const [timeout, setTimeoutValue] = useState(String(first.timing.timeout_ms ?? 500));
  const [latency, setLatency] = useState(String(first.timing.max_latency_ms ?? 20));
  const [jitter, setJitter] = useState(String(first.timing.jitter_limit_ms ?? 5));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function toggle(field: BulkEditableField) {
    setEnabled((current) => {
      const next = new Set(current);
      if (next.has(field)) next.delete(field);
      else next.add(field);
      return next;
    });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (enabled.size === 0) {
      setError("Mindestens ein Feld muss für die Übernahme aktiviert sein.");
      return;
    }
    const numericValues: Array<[BulkEditableField, string]> = [
      ["cycle", cycle],
      ["timeout", timeout],
      ["latency", latency],
      ["jitter", jitter],
    ];
    const invalid = numericValues.find(([field, value]) => enabled.has(field) && (!Number.isFinite(Number(value)) || Number(value) <= 0));
    if (invalid) {
      setError("Aktivierte Timing-Werte müssen größer als 0 sein.");
      return;
    }
    const changes: RoutingBulkChanges = {
      ...(enabled.has("protocol") ? { protocol } : {}),
      ...(enabled.has("priority") ? { priority } : {}),
      ...(enabled.has("routingType") ? { routingType } : {}),
      ...(enabled.has("redundancy") ? { redundancy } : {}),
      ...(enabled.has("cycle") ? { cycle: Number(cycle) } : {}),
      ...(enabled.has("timeout") ? { timeout: Number(timeout) } : {}),
      ...(enabled.has("latency") ? { latency: Number(latency) } : {}),
      ...(enabled.has("jitter") ? { jitter: Number(jitter) } : {}),
    };
    setSaving(true);
    try {
      await onSave(routes.map((route) => ({ id: route.id, payload: bulkRoutePayload(route, changes) })));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="routing-dialog-backdrop" role="presentation">
      <form aria-labelledby="routing-bulk-editor-title" aria-modal="true" className="routing-dialog routing-bulk-editor-dialog" onSubmit={(event) => void submit(event)} role="dialog">
        <header>
          <div><span>Routing Manager</span><h2 id="routing-bulk-editor-title">Mehrfachbearbeitung</h2></div>
          <button aria-label="Mehrfachbearbeitung schließen" onClick={onClose} type="button">×</button>
        </header>
        <div className="routing-bulk-editor-grid">
          <BulkSelectField enabled={enabled.has("protocol")} label="Protokoll" onToggle={() => toggle("protocol")}>
            <select disabled={!enabled.has("protocol")} onChange={(event) => setProtocol(event.target.value)} value={protocol}>
              {schema.protocols.map((item) => <option key={item}>{item}</option>)}
            </select>
          </BulkSelectField>
          <BulkSelectField enabled={enabled.has("priority")} label="Priorität" onToggle={() => toggle("priority")}>
            <select disabled={!enabled.has("priority")} onChange={(event) => setPriority(event.target.value as RoutingEntry["route"]["priority"])} value={priority}>
              {schema.priorities.map((item) => <option key={item}>{item}</option>)}
            </select>
          </BulkSelectField>
          <BulkSelectField enabled={enabled.has("routingType")} label="Routing-Typ" onToggle={() => toggle("routingType")}>
            <select disabled={!enabled.has("routingType")} onChange={(event) => setRoutingType(event.target.value)} value={routingType}>
              {schema.routing_types.map((item) => <option key={item}>{item}</option>)}
            </select>
          </BulkSelectField>
          <BulkSelectField enabled={enabled.has("redundancy")} label="Redundanz" onToggle={() => toggle("redundancy")}>
            <select disabled={!enabled.has("redundancy")} onChange={(event) => setRedundancy(event.target.value)} value={redundancy}>
              {schema.redundancy_modes.map((item) => <option key={item}>{item}</option>)}
            </select>
          </BulkSelectField>
          <BulkSelectField enabled={enabled.has("cycle")} label="Zyklus (ms)" onToggle={() => toggle("cycle")}>
            <input disabled={!enabled.has("cycle")} min="0.001" onChange={(event) => setCycle(event.target.value)} step="any" type="number" value={cycle} />
          </BulkSelectField>
          <BulkSelectField enabled={enabled.has("timeout")} label="Timeout (ms)" onToggle={() => toggle("timeout")}>
            <input disabled={!enabled.has("timeout")} min="0.001" onChange={(event) => setTimeoutValue(event.target.value)} step="any" type="number" value={timeout} />
          </BulkSelectField>
          <BulkSelectField enabled={enabled.has("latency")} label="Max. Latenz (ms)" onToggle={() => toggle("latency")}>
            <input disabled={!enabled.has("latency")} min="0.001" onChange={(event) => setLatency(event.target.value)} step="any" type="number" value={latency} />
          </BulkSelectField>
          <BulkSelectField enabled={enabled.has("jitter")} label="Jitter-Limit (ms)" onToggle={() => toggle("jitter")}>
            <input disabled={!enabled.has("jitter")} min="0.001" onChange={(event) => setJitter(event.target.value)} step="any" type="number" value={jitter} />
          </BulkSelectField>
        </div>
        <div className="routing-bulk-selection-summary">
          <strong>{routes.length} Routen</strong>
          <span>{routes.map((route) => route.route_code).join(", ")}</span>
        </div>
        {error && <div className="notice error">{error}</div>}
        <footer>
          <span>{enabled.size} Felder aktiviert</span>
          <div>
            <button className="button secondary" disabled={saving} onClick={onClose} type="button">Abbrechen</button>
            <button className="button primary" disabled={saving || enabled.size === 0} type="submit">{saving ? "Wird übernommen …" : "Auf Auswahl anwenden"}</button>
          </div>
        </footer>
      </form>
    </div>
  );
}

function BulkSelectField({ enabled, label, onToggle, children }: { enabled: boolean; label: string; onToggle: () => void; children: ReactNode }) {
  return (
    <div className={`routing-bulk-field ${enabled ? "enabled" : ""}`}>
      <label><input checked={enabled} onChange={onToggle} type="checkbox" /><span>{label}</span></label>
      {children}
    </div>
  );
}

function RoutingEditorDialog({ mode, route, routes, schema, hardware, interfaces, messages, signals, seed, onClose, onSave, onGenerate, onDuplicate, onDelete }: {
  mode: "manual" | "ai";
  route?: RoutingEntry;
  routes: RoutingEntry[];
  schema: RoutingSchema;
  hardware: HardwareNode[];
  interfaces: EngInterface[];
  messages: EngMessage[];
  signals: EngSignal[];
  seed?: RoutingEditorSeed;
  onClose: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
  onGenerate: (payload: Record<string, unknown>) => Promise<void>;
  onDuplicate?: () => Promise<void>;
  onDelete?: () => Promise<void>;
}) {
  const seededSourceInterface = seed?.sourceInterfaceId ? interfaces.find((item) => item.id === seed.sourceInterfaceId) : undefined;
  const seededDestinationInterface = seed?.destinationInterfaceId ? interfaces.find((item) => item.id === seed.destinationInterfaceId) : undefined;
  const initialSourceId = route?.source.node_id ?? seed?.sourceNodeId ?? seededSourceInterface?.hardware_node_id ?? hardware[0]?.id ?? "";
  const initialDestinationNodeId = seed?.destinationNodeId ?? seededDestinationInterface?.hardware_node_id ?? "";
  const initialDestinationIds = route?.destinations.map((item) => item.node_id).filter((id) => id !== initialSourceId) ?? [];
  const initialDestinationIdsWithSeed = route ? initialDestinationIds : initialDestinationNodeId && initialDestinationNodeId !== initialSourceId ? [initialDestinationNodeId] : [];
  const initialSourceInterfaceId = route?.source.interface_id ?? seed?.sourceInterfaceId ?? "";
  const initialSourceInterface = interfaces.find((item) => item.id === initialSourceInterfaceId);
  const initialDestinationInterfaceId = seed?.destinationInterfaceId ?? "";
  const initialProtocol = route?.source.protocol ?? (initialSourceInterface ? interfaceProtocol(initialSourceInterface.interface_type) : "CAN_FD");
  const [name, setName] = useState(route?.name ?? seed?.name ?? "");
  const [description, setDescription] = useState(route?.description ?? "");
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [sourcePortId, setSourcePortId] = useState(route?.source.port_id ?? "");
  const [sourceInterfaceId, setSourceInterfaceId] = useState(initialSourceInterfaceId);
  const [sourceNetworkId, setSourceNetworkId] = useState(route?.source.network_id ?? networkId(initialSourceInterface) ?? "");
  const [destinationIds, setDestinationIds] = useState<string[]>(initialDestinationIdsWithSeed);
  const [destinationInterfaces, setDestinationInterfaces] = useState<Record<string, string>>(
    Object.fromEntries(route?.destinations.map((item) => [item.node_id, item.interface_id ?? ""]) ?? (
      initialDestinationNodeId ? [[initialDestinationNodeId, initialDestinationInterfaceId]] : []
    )),
  );
  const [destinationPorts, setDestinationPorts] = useState<Record<string, string>>(
    Object.fromEntries(route?.destinations.map((item) => [item.node_id, item.port_id ?? ""]) ?? []),
  );
  const [destinationNetworks, setDestinationNetworks] = useState<Record<string, string>>(
    Object.fromEntries(route?.destinations.map((item) => [item.node_id, item.network_id ?? ""]) ?? (
      initialDestinationNodeId ? [[initialDestinationNodeId, networkId(seededDestinationInterface) ?? ""]] : []
    )),
  );
  const [destinationProtocols, setDestinationProtocols] = useState<Record<string, string>>(
    Object.fromEntries(route?.destinations.map((item) => [item.node_id, item.protocol ?? route?.source.protocol ?? "CAN_FD"]) ?? (
      initialDestinationNodeId ? [[initialDestinationNodeId, seededDestinationInterface ? interfaceProtocol(seededDestinationInterface.interface_type) : initialProtocol]] : []
    )),
  );
  const [payloadMode, setPayloadMode] = useState<RoutingPayloadMode>(seed?.topic && !route ? "topic" : routingPayloadMode(route));
  const [messageIds, setMessageIds] = useState<string[]>(routingMessageIds(route));
  const [signalIds, setSignalIds] = useState<string[]>(route?.payload.signal_ids ?? []);
  const [interfaceDefinitionId, setInterfaceDefinitionId] = useState(route?.payload.interface_definition_id ?? messages.find((item) => routingMessageIds(route).includes(item.id))?.interface_id ?? "");
  const [topic, setTopic] = useState(route?.payload.topic ?? seed?.topic ?? "");
  const [dataObject, setDataObject] = useState(route?.payload.data_object ?? "");
  const [gatewayIds, setGatewayIds] = useState<string[]>(routingGatewayIds(route).filter((id) => id !== initialSourceId && !initialDestinationIdsWithSeed.includes(id)));
  const [protocol, setProtocol] = useState(initialProtocol);
  const [routingType, setRoutingType] = useState(route?.routing_policy.routing_type ?? "UNICAST");
  const [priority, setPriority] = useState(route?.route.priority ?? "NORMAL");
  const [redundancy, setRedundancy] = useState(route?.routing_policy.redundancy ?? "NONE");
  const [fallbackRouteId, setFallbackRouteId] = useState(route?.routing_policy.fallback_route_id ?? "");
  const [cycle, setCycle] = useState(String(route?.timing.cycle_time_ms ?? (route ? "" : 100)));
  const [timeout, setTimeoutValue] = useState(String(route?.timing.timeout_ms ?? (route ? "" : 500)));
  const [latency, setLatency] = useState(String(route?.timing.max_latency_ms ?? (route ? "" : 20)));
  const [jitter, setJitter] = useState(String(route?.timing.jitter_limit_ms ?? (route ? "" : 5)));
  const [transformations, setTransformations] = useState(route?.route.transformations.join(", ") ?? "");
  const [conditionsText, setConditionsText] = useState(routingConditionsText(route));
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const sourceInterfaces = interfaces.filter((item) => item.hardware_node_id === sourceId);
  const sourceInterfaceIds = new Set(sourceInterfaces.map((item) => item.id));
  const senderMessages = messages.filter((item) => sourceInterfaceIds.has(item.interface_id ?? "") || messageIds.includes(item.id));
  const selectedMessages = messageIds.map((id) => messages.find((item) => item.id === id)).filter((item): item is EngMessage => Boolean(item));
  const selectableSignals = messageIds.length ? signals.filter((item) => item.message_id && messageIds.includes(item.message_id)) : signals;
  const gateways = hardware.filter((node) => node.device_type === "Gateway" && node.id !== sourceId && !destinationIds.includes(node.id));
  const fallbackRoutes = routes.filter((item) => item.id !== route?.id);
  const networkAliases = useMemo(() => buildNetworkAliases(interfaces, hardware), [interfaces, hardware]);
  const selectedSourceInterface = sourceInterfaces.find((item) => item.id === sourceInterfaceId);
  const sourceNode = hardware.find((item) => item.id === sourceId);
  const sourceNetworkDisplay = friendlyNetworkLabel(sourceNetworkId || networkId(selectedSourceInterface), networkAliases, sourceNode?.name, protocol);

  function interfaceLabel(item: EngInterface) {
    const node = hardware.find((candidate) => candidate.id === item.hardware_node_id);
    return `Interface: ${item.name} | Gerät: ${node?.name ?? "nicht zugeordnet"} | Typ: ${interfaceProtocol(item.interface_type)} | Netz: ${friendlyNetworkLabel(networkId(item), networkAliases, node?.name, interfaceProtocol(item.interface_type))}`;
  }

  function toggleEditorMessage(id: string) {
    setPayloadMode("message");
    const nextIds = messageIds.includes(id) ? messageIds.filter((item) => item !== id) : [...messageIds, id];
    setMessageIds(nextIds);
    setSignalIds((current) => current.filter((signalId) => {
      const signal = signals.find((item) => item.id === signalId);
      return !nextIds.length || Boolean(signal?.message_id && nextIds.includes(signal.message_id));
    }));
    setInterfaceDefinitionId(messages.find((item) => item.id === nextIds[0])?.interface_id ?? "");
  }

  function toggleDestination(id: string) {
    if (destinationIds.includes(id)) {
      setDestinationIds((current) => current.filter((item) => item !== id));
      return;
    }
    const candidate = interfaces.find((item) => item.hardware_node_id === id && interfaceProtocol(item.interface_type) === protocol)
      ?? interfaces.find((item) => item.hardware_node_id === id);
    setDestinationIds((current) => [...current, id]);
    setDestinationInterfaces((current) => ({ ...current, [id]: current[id] || candidate?.id || "" }));
    setDestinationNetworks((current) => ({ ...current, [id]: current[id] || networkId(candidate) || "" }));
    setDestinationProtocols((current) => ({ ...current, [id]: current[id] || (candidate ? interfaceProtocol(candidate.interface_type) : protocol) }));
  }

  function toggleSignal(id: string) { setSignalIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]); }
  function toggleGateway(id: string) { setGatewayIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]); }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setFormError("");
    const parsedConditions = parseRoutingConditions(conditionsText);
    if (parsedConditions.error) {
      setFormError(parsedConditions.error);
      return;
    }
    const timingValues = [cycle, timeout, latency, jitter].map(optionalNumber);
    if (timingValues.some((value) => value != null && (!Number.isFinite(value) || value <= 0))) {
      setFormError("Timing-Werte müssen leer oder größer als 0 sein.");
      return;
    }
    if (!name.trim() || !sourceId || destinationIds.length === 0) return;
    setSaving(true);
    const destinations = destinationIds.map((nodeId) => {
      const candidate = interfaces.find((item) => item.id === destinationInterfaces[nodeId]);
      return {
        node_id: nodeId,
        port_id: optionalText(destinationPorts[nodeId] ?? ""),
        interface_id: candidate?.id ?? optionalText(destinationInterfaces[nodeId] ?? ""),
        network_id: optionalText(destinationNetworks[nodeId] ?? "") ?? networkId(candidate),
        protocol: destinationProtocols[nodeId] || (candidate ? interfaceProtocol(candidate.interface_type) : protocol),
      };
    });
    const selectedGateways = gatewayIds.map((id) => hardware.find((item) => item.id === id)).filter((item): item is HardwareNode => Boolean(item));
    const hops = [
      { node_id: sourceId, name: sourceNode?.name },
      ...selectedGateways.map((gateway) => ({ node_id: gateway.id, name: gateway.name })),
      ...destinationIds.map((id) => ({ node_id: id, name: hardware.find((item) => item.id === id)?.name })),
    ];
    const payloadMessageIds = payloadMode === "message" ? messageIds : [];
    const payloadMessageId = payloadMessageIds[0] ?? null;
    const payloadSignalIds = payloadMode === "message" ? signalIds : [];
    const payloadTopic = payloadMode === "topic" ? optionalText(topic) : null;
    const payloadDataObject = payloadMode === "data_object" ? optionalText(dataObject) : null;
    const payload = {
      name: name.trim(),
      description: optionalText(description),
      source: {
        node_id: sourceId,
        port_id: optionalText(sourcePortId),
        interface_id: optionalText(sourceInterfaceId),
        network_id: optionalText(sourceNetworkId) ?? networkId(selectedSourceInterface),
        protocol,
      },
      payload: {
        interface_definition_id: optionalText(interfaceDefinitionId),
        interface_definition_ids: [...new Set(selectedMessages.map((item) => item.interface_id).filter((id): id is string => Boolean(id)))],
        message_id: payloadMessageId,
        message_ids: payloadMessageIds,
        signal_ids: payloadSignalIds,
        topic: payloadTopic,
        data_object: payloadDataObject,
      },
      destinations,
      route: {
        hops,
        gateways: selectedGateways.map((gateway) => ({ node_id: gateway.id, name: gateway.name })),
        transformations: transformations.split(",").map((item) => item.trim()).filter(Boolean),
        priority,
      },
      timing: { cycle_time_ms: timingValues[0], timeout_ms: timingValues[1], max_latency_ms: timingValues[2], jitter_limit_ms: timingValues[3] },
      routing_policy: {
        routing_type: destinationIds.length > 1 && routingType === "UNICAST" ? "MULTICAST" : routingType,
        redundancy,
        fallback_route_id: optionalText(fallbackRouteId),
        conditions: parsedConditions.conditions,
      },
      actor: mode === "ai" ? "engineering-agent" : "routing-ui",
      prompt: `Erzeuge Routing von ${sourceNode?.name} zu ${destinationIds.map((id) => hardware.find((item) => item.id === id)?.name).join(", ")}`,
      source_node_id: sourceId,
      destination_node_ids: destinationIds,
      message_id: payloadMessageId,
      message_ids: payloadMessageIds,
      signal_ids: payloadSignalIds,
    };
    try { await (mode === "ai" ? onGenerate(payload) : onSave(payload)); } finally { setSaving(false); }
  }

  return (
    <div className="routing-dialog-backdrop" role="presentation">
      <form aria-modal="true" className="routing-dialog routing-editor-dialog" onSubmit={submit} role="dialog">
        <header>
          <div><p className="eyebrow">{mode === "ai" ? "AI Routing Proposal" : "Routing Editor"}</p><h2>{route ? `${name || route.name} · ${route.route_code}` : mode === "ai" ? "Routen generieren" : "Route anlegen"}</h2></div>
          <button aria-label="Dialog schließen" onClick={onClose} type="button">×</button>
        </header>
        {formError && <div className="notice error routing-form-error">{formError}</div>}
        <div className="routing-editor-grid">
          <fieldset className="full-width routing-field-grid">
            <legend>01 Allgemein</legend>
            <label>Name<input onChange={(event) => setName(event.target.value)} required value={name} /></label>
            <label>Beschreibung<textarea onChange={(event) => setDescription(event.target.value)} value={description} /></label>
          </fieldset>

          <fieldset className="routing-field-grid">
            <legend>02 Quelle</legend>
            <label>Source Node<select onChange={(event) => { const id = event.target.value; const allowedInterfaces = new Set(interfaces.filter((item) => item.hardware_node_id === id).map((item) => item.id)); const nextMessageIds = messageIds.filter((messageId) => allowedInterfaces.has(messages.find((item) => item.id === messageId)?.interface_id ?? "")); setSourceId(id); setSourceInterfaceId(""); setSourcePortId(""); setSourceNetworkId(""); setMessageIds(nextMessageIds); setSignalIds((current) => current.filter((signalId) => { const signal = signals.find((item) => item.id === signalId); return !nextMessageIds.length || Boolean(signal?.message_id && nextMessageIds.includes(signal.message_id)); })); setInterfaceDefinitionId(messages.find((item) => item.id === nextMessageIds[0])?.interface_id ?? ""); setDestinationIds((current) => current.filter((item) => item !== id)); setGatewayIds((current) => current.filter((item) => item !== id)); }} value={sourceId}>{hardware.map((node) => <option key={node.id} value={node.id}>{node.name} · {node.device_type}</option>)}</select></label>
            <label>Source Interface<select onChange={(event) => { const item = interfaces.find((candidate) => candidate.id === event.target.value); setSourceInterfaceId(event.target.value); if (item) { setProtocol(interfaceProtocol(item.interface_type)); setSourceNetworkId(networkId(item) ?? ""); } }} value={sourceInterfaceId}><option value="">Nicht gesetzt</option>{sourceInterfaceId && !sourceInterfaces.some((item) => item.id === sourceInterfaceId) && <option value={sourceInterfaceId}>Unbekannt · {sourceInterfaceId}</option>}{sourceInterfaces.map((item) => <option key={item.id} value={item.id}>{interfaceLabel(item)}</option>)}</select></label>
            <NetworkSegmentDisplay value={sourceNetworkDisplay} />
            <details className="routing-technical-fields full-width"><summary>Technische IDs</summary><label>Source Port ID<input onChange={(event) => setSourcePortId(event.target.value)} value={sourcePortId} /></label><label>Source Network ID<input onChange={(event) => setSourceNetworkId(event.target.value)} value={sourceNetworkId} /></label></details>
            <label>Protocol<select onChange={(event) => setProtocol(event.target.value)} value={protocol}>{schema.protocols.map((item) => <option key={item}>{item}</option>)}</select></label>
          </fieldset>

          <fieldset className="routing-field-grid">
            <legend>03 Payload</legend>
            <div aria-label="Payload-Art" className="routing-payload-mode full-width" role="group"><button className={payloadMode === "message" ? "active" : ""} onClick={() => setPayloadMode("message")} type="button">Message</button><button className={payloadMode === "topic" ? "active" : ""} onClick={() => setPayloadMode("topic")} type="button">Topic</button><button className={payloadMode === "data_object" ? "active" : ""} onClick={() => setPayloadMode("data_object")} type="button">Data Object</button></div>
            {payloadMode === "message" && <><div className="routing-check-list routing-message-check-list full-width"><span>Messages · {messageIds.length} gewählt</span>{senderMessages.length ? senderMessages.map((item) => <label key={item.id}><input checked={messageIds.includes(item.id)} onChange={() => toggleEditorMessage(item.id)} type="checkbox" />{item.name}</label>) : <small>Für den gewählten Sender sind keine Messages vorhanden.</small>}</div><div className="routing-check-list full-width"><span>Signals</span>{selectableSignals.length ? selectableSignals.map((signal) => <label key={signal.id}><input checked={signalIds.includes(signal.id)} onChange={() => toggleSignal(signal.id)} type="checkbox" />{signal.display_name || signal.name}<small>{signal.start_bit ?? "?"} / {signal.length_bits ?? "?"} Bit</small></label>) : <small>Keine Signals verfügbar.</small>}</div></>}
            {payloadMode === "topic" && <label className="full-width">Topic<input onChange={(event) => setTopic(event.target.value)} placeholder="z. B. vehicle/thermal/status" value={topic} /></label>}
            {payloadMode === "data_object" && <label className="full-width">Data Object<input onChange={(event) => setDataObject(event.target.value)} placeholder="z. B. VehicleThermalStatus" value={dataObject} /></label>}
            {payloadMode === "message" ? <div className="routing-payload-interface-summary full-width"><span>Payload-Interfaces</span><strong>{[...new Set(selectedMessages.map((message) => interfaces.find((item) => item.id === message.interface_id)?.name).filter(Boolean))].join(", ") || "Wird aus den gewählten Messages übernommen"}</strong></div> : <label className="full-width">Payload Interface ID<input onChange={(event) => setInterfaceDefinitionId(event.target.value)} placeholder="Optional" value={interfaceDefinitionId} /></label>}
          </fieldset>

          <fieldset className="full-width">
            <legend>04 Ziele</legend>
            <div className="routing-check-list"><span>Consumer</span>{hardware.filter((node) => node.id !== sourceId).map((node) => <label key={node.id}><input checked={destinationIds.includes(node.id)} onChange={() => toggleDestination(node.id)} type="checkbox" />{node.name}<small>{node.device_type}</small></label>)}</div>
            <div className="routing-endpoint-list">{destinationIds.map((nodeId) => {
              const endpointInterfaces = interfaces.filter((item) => item.hardware_node_id === nodeId);
              const selectedInterfaceId = destinationInterfaces[nodeId] ?? "";
              const selectedDestinationInterface = endpointInterfaces.find((item) => item.id === selectedInterfaceId);
              const destinationNode = hardware.find((item) => item.id === nodeId);
              const destinationNetworkDisplay = friendlyNetworkLabel(destinationNetworks[nodeId] || networkId(selectedDestinationInterface), networkAliases, destinationNode?.name, destinationProtocols[nodeId] || protocol);
              return <section className="routing-endpoint-fields" key={nodeId}><strong>{destinationNode?.name ?? nodeId}</strong><label>Interface<select onChange={(event) => { const item = interfaces.find((candidate) => candidate.id === event.target.value); setDestinationInterfaces((current) => ({ ...current, [nodeId]: event.target.value })); if (item) { setDestinationNetworks((current) => ({ ...current, [nodeId]: networkId(item) ?? "" })); setDestinationProtocols((current) => ({ ...current, [nodeId]: interfaceProtocol(item.interface_type) })); } }} value={selectedInterfaceId}><option value="">Nicht gesetzt</option>{selectedInterfaceId && !endpointInterfaces.some((item) => item.id === selectedInterfaceId) && <option value={selectedInterfaceId}>Unbekannt · {selectedInterfaceId}</option>}{endpointInterfaces.map((item) => <option key={item.id} value={item.id}>{interfaceLabel(item)}</option>)}</select></label><NetworkSegmentDisplay value={destinationNetworkDisplay} /><details className="routing-technical-fields"><summary>IDs</summary><label>Port ID<input onChange={(event) => setDestinationPorts((current) => ({ ...current, [nodeId]: event.target.value }))} value={destinationPorts[nodeId] ?? ""} /></label><label>Network ID<input onChange={(event) => setDestinationNetworks((current) => ({ ...current, [nodeId]: event.target.value }))} value={destinationNetworks[nodeId] ?? ""} /></label></details><label>Protocol<select onChange={(event) => setDestinationProtocols((current) => ({ ...current, [nodeId]: event.target.value }))} value={destinationProtocols[nodeId] || protocol}>{schema.protocols.map((item) => <option key={item}>{item}</option>)}</select></label></section>;
            })}</div>
          </fieldset>

          <fieldset className="routing-field-grid">
            <legend>05 Pfad</legend>
            <div className="routing-check-list full-width"><span>Gateways</span>{gateways.length ? gateways.map((gateway) => <label key={gateway.id}><input checked={gatewayIds.includes(gateway.id)} onChange={() => toggleGateway(gateway.id)} type="checkbox" />{gateway.name}<small>{gateway.device_type}</small></label>) : <small>Direkter Pfad</small>}</div>
            <label>Priority<select onChange={(event) => setPriority(event.target.value as typeof priority)} value={priority}>{schema.priorities.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label className="full-width">Transformations<input onChange={(event) => setTransformations(event.target.value)} placeholder="CAN_SIGNAL_TO_SOMEIP_FIELD" value={transformations} /></label>
          </fieldset>

          <fieldset className="routing-field-grid">
            <legend>06 Routing Policy</legend>
            <label>Routing Type<select onChange={(event) => setRoutingType(event.target.value)} value={routingType}>{schema.routing_types.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Redundancy<select onChange={(event) => setRedundancy(event.target.value)} value={redundancy}>{schema.redundancy_modes.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Fallback Route<select onChange={(event) => setFallbackRouteId(event.target.value)} value={fallbackRouteId}><option value="">Keine</option>{fallbackRouteId && !fallbackRoutes.some((item) => item.id === fallbackRouteId) && <option value={fallbackRouteId}>Unbekannt · {fallbackRouteId}</option>}{fallbackRoutes.map((item) => <option key={item.id} value={item.id}>{item.route_code} · {item.name}</option>)}</select></label>
            <label className="full-width">Conditions (JSON)<textarea onChange={(event) => setConditionsText(event.target.value)} spellCheck={false} value={conditionsText} /></label>
          </fieldset>

          <fieldset className="routing-timing">
            <legend>07 Timing</legend>
            <label>Cycle Time (ms)<input min="0.001" onChange={(event) => setCycle(event.target.value)} step="any" type="number" value={cycle} /></label>
            <label>Timeout (ms)<input min="0.001" onChange={(event) => setTimeoutValue(event.target.value)} step="any" type="number" value={timeout} /></label>
            <label>Maximum Latency (ms)<input min="0.001" onChange={(event) => setLatency(event.target.value)} step="any" type="number" value={latency} /></label>
            <label>Jitter (ms)<input min="0.001" onChange={(event) => setJitter(event.target.value)} step="any" type="number" value={jitter} /></label>
          </fieldset>

          {route && <fieldset className="full-width"><legend>Governance · schreibgeschützt</legend><dl className="routing-object-summary routing-governance-summary"><dt>Route Code</dt><dd>{route.route_code}</dd><dt>Revision</dt><dd>{route.revision}</dd><dt>Status</dt><dd>{route.status}</dd><dt>Origin</dt><dd>{route.origin}</dd><dt>Review</dt><dd>{route.review_state}</dd><dt>Approval</dt><dd>{route.approval_state}</dd><dt>Confidence</dt><dd>{route.confidence ?? "—"}</dd><dt>Source ID</dt><dd>{route.source_id ?? "—"}</dd><dt>Source Version</dt><dd>{route.source_version ?? "—"}</dd></dl></fieldset>}
        </div>
        {route && <section className="routing-editor-management" aria-label="Datensatz verwalten"><div><p className="eyebrow">Datensatz verwalten</p><span>Duplicate erzeugt einen neuen, unabhängigen Draft.</span><p className="routing-delete-warning"><strong>Hinweis zu Delete:</strong> Bei einer freigegebenen Route wird zuerst der Status APPROVED zurückgezogen und als REJECTED protokolliert. Danach wird die Route endgültig gelöscht.</p></div><div><button className="button secondary" disabled={saving} onClick={() => void onDuplicate?.()} type="button">Duplicate</button><button className="button danger" disabled={saving} onClick={() => { if (window.confirm(`${route.route_code} endgültig löschen? Eine bestehende Freigabe wird zuvor zurückgezogen.`)) void onDelete?.(); }} title="Route endgültig löschen" type="button">Delete</button></div></section>}
        <footer><span>{mode === "ai" ? "Der Agent erzeugt ausschließlich ein prüfbares Proposal." : "Speichern erzeugt einen Draft. Freigabe erfolgt separat."}</span><div><button className="button secondary" onClick={onClose} type="button">Abbrechen</button><button className="button primary" disabled={saving || !name.trim() || !sourceId || !destinationIds.length} type="submit">{saving ? "Wird verarbeitet …" : mode === "ai" ? "Proposal erzeugen" : "Draft speichern"}</button></div></footer>
      </form>
    </div>
  );
}

const ROUTING_WIZARD_STEPS = ["Allgemein", "Quelle", "Payload", "Ziele", "Pfad & Policy", "Timing", "Prüfen"] as const;

function RoutingRepairWizard({ route, routes, schema, hardware, interfaces, messages, signals, onClose, onSave, onDelete }: {
  route: RoutingEntry;
  routes: RoutingEntry[];
  schema: RoutingSchema;
  hardware: HardwareNode[];
  interfaces: EngInterface[];
  messages: EngMessage[];
  signals: EngSignal[];
  onClose: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const initialSourceId = route.source.node_id ?? "";
  const initialDestinationIds = route.destinations.map((item) => item.node_id).filter((id) => id !== initialSourceId);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [name, setName] = useState(route.name);
  const [description, setDescription] = useState(route.description ?? "");
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [sourcePortId, setSourcePortId] = useState(route.source.port_id ?? "");
  const [sourceInterfaceId, setSourceInterfaceId] = useState(route.source.interface_id ?? "");
  const [sourceNetworkId, setSourceNetworkId] = useState(route.source.network_id ?? "");
  const [payloadMode, setPayloadMode] = useState<RoutingPayloadMode>(routingPayloadMode(route));
  const [messageIds, setMessageIds] = useState<string[]>(routingMessageIds(route));
  const [signalIds, setSignalIds] = useState<string[]>(route.payload.signal_ids ?? []);
  const [interfaceDefinitionId, setInterfaceDefinitionId] = useState(route.payload.interface_definition_id ?? messages.find((item) => routingMessageIds(route).includes(item.id))?.interface_id ?? "");
  const [topic, setTopic] = useState(route.payload.topic ?? "");
  const [dataObject, setDataObject] = useState(route.payload.data_object ?? "");
  const [destinationIds, setDestinationIds] = useState<string[]>(initialDestinationIds);
  const [destinationInterfaces, setDestinationInterfaces] = useState<Record<string, string>>(Object.fromEntries(route.destinations.map((item) => [item.node_id, item.interface_id ?? ""])));
  const [destinationPorts, setDestinationPorts] = useState<Record<string, string>>(Object.fromEntries(route.destinations.map((item) => [item.node_id, item.port_id ?? ""])));
  const [destinationNetworks, setDestinationNetworks] = useState<Record<string, string>>(Object.fromEntries(route.destinations.map((item) => [item.node_id, item.network_id ?? ""])));
  const [destinationProtocols, setDestinationProtocols] = useState<Record<string, string>>(Object.fromEntries(route.destinations.map((item) => [item.node_id, item.protocol ?? route.source.protocol ?? "CAN_FD"])));
  const [gatewayIds, setGatewayIds] = useState<string[]>(routingGatewayIds(route).filter((id) => id !== initialSourceId && !initialDestinationIds.includes(id)));
  const [protocol, setProtocol] = useState(route.source.protocol ?? "CAN_FD");
  const [routingType, setRoutingType] = useState(route.routing_policy.routing_type ?? "UNICAST");
  const [priority, setPriority] = useState(route.route.priority ?? "NORMAL");
  const [redundancy, setRedundancy] = useState(route.routing_policy.redundancy ?? "NONE");
  const [fallbackRouteId, setFallbackRouteId] = useState(route.routing_policy.fallback_route_id ?? "");
  const [conditionsText, setConditionsText] = useState(routingConditionsText(route));
  const [cycle, setCycle] = useState(String(route.timing.cycle_time_ms ?? ""));
  const [timeout, setTimeoutValue] = useState(String(route.timing.timeout_ms ?? ""));
  const [latency, setLatency] = useState(String(route.timing.max_latency_ms ?? ""));
  const [jitter, setJitter] = useState(String(route.timing.jitter_limit_ms ?? ""));
  const [transformations, setTransformations] = useState(route.route.transformations.join(", "));
  const sourceInterfaces = interfaces.filter((item) => item.hardware_node_id === sourceId);
  const selectedMessages = messageIds.map((id) => messages.find((item) => item.id === id)).filter((item): item is EngMessage => Boolean(item));
  const selectedMessage = selectedMessages.length
    ? {
        ...selectedMessages[0],
        name: selectedMessages.map((item) => item.name).join(", "),
        message_id_hex: selectedMessages.map((item) => item.message_id_hex).filter(Boolean).join(", ") || null,
      }
    : undefined;
  const selectableSignals = messageIds.length ? signals.filter((item) => item.message_id && messageIds.includes(item.message_id)) : signals;
  const gateways = hardware.filter((node) => node.device_type === "Gateway" && node.id !== sourceId && !destinationIds.includes(node.id));
  const destinationOptions = hardware.filter((node) => node.id !== sourceId);
  const fallbackRoutes = routes.filter((item) => item.id !== route.id);
  const networkAliases = useMemo(() => buildNetworkAliases(interfaces, hardware), [interfaces, hardware]);
  const sourceInterface = interfaces.find((item) => item.id === sourceInterfaceId);
  const sourceNetworkDisplay = friendlyNetworkLabel(sourceNetworkId || networkId(sourceInterface), networkAliases, nodeName(sourceId), protocol);
  const validationIssues = [...(route.validation?.errors ?? []), ...(route.validation?.warnings ?? [])];
  const hasIssue = (code: string) => validationIssues.some((issue) => issue.code === code);
  const conditionResult = parseRoutingConditions(conditionsText);
  const invalidTiming = [cycle, timeout, latency, jitter].some((value) => value.trim() && (optionalNumber(value) == null || !Number.isFinite(optionalNumber(value)) || Number(value) <= 0));
  const missing = [
    !name.trim() ? "Name" : "",
    !sourceId ? "Producer" : "",
    !sourceInterfaceId ? "Source Interface" : "",
    !destinationIds.length ? "Consumer" : "",
    ...destinationIds.flatMap((id) => destinationInterfaces[id] ? [] : [`Destination Interface: ${hardware.find((item) => item.id === id)?.name ?? id}`]),
    payloadMode === "message" && !messageIds.length && !signalIds.length ? "Message oder Signal" : "",
    payloadMode === "topic" && !topic.trim() ? "Topic" : "",
    payloadMode === "data_object" && !dataObject.trim() ? "Data Object" : "",
    !cycle ? "Cycle" : "",
    !latency ? "Latency" : "",
    invalidTiming ? "Timing-Werte" : "",
    conditionResult.error,
  ].filter(Boolean);

  function interfaceLabel(item: EngInterface) {
    const hardwareNode = hardware.find((node) => node.id === item.hardware_node_id);
    return `Interface: ${item.name} | Gerät: ${hardwareNode?.name ?? "nicht zugeordnet"} | Typ: ${interfaceProtocol(item.interface_type)} | Netz: ${friendlyNetworkLabel(networkId(item), networkAliases, hardwareNode?.name, interfaceProtocol(item.interface_type))}`;
  }

  function messageSenderNode(item: EngMessage) {
    const iface = interfaces.find((candidate) => candidate.id === item.interface_id);
    return iface ? hardware.find((candidate) => candidate.id === iface.hardware_node_id) : undefined;
  }

  function normalizedName(value: string) {
    return value.toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function topInterfaceSuggestions(options: EngInterface[]) {
    return options
      .map((item) => {
        const reasons = ["Gerät entspricht dem Producer"];
        let confidence = 55;
        if (interfaceProtocol(item.interface_type) === protocol) { confidence += 28; reasons.push("Protokoll stimmt überein"); }
        if (item.id === sourceInterfaceId) { confidence += 10; reasons.push("aktuell zugeordnet"); }
        if (sourceNetworkId && networkId(item) === sourceNetworkId) { confidence += 6; reasons.push("Netzwerk stimmt überein"); }
        return { id: item.id, label: interfaceLabel(item), confidence: Math.min(99, confidence), reason: reasons.join(" · ") };
      })
      .sort((left, right) => right.confidence - left.confidence)
      .slice(0, 3);
  }

  function messageSuggestion(item: EngMessage) {
    const iface = interfaces.find((candidate) => candidate.id === item.interface_id);
    const sender = messageSenderNode(item);
    const source = hardware.find((candidate) => candidate.id === sourceId);
    const reasons: string[] = [];
    let confidence = 18;
    if (sender?.id === sourceId) { confidence += 50; reasons.push("Sender entspricht dem Producer"); }
    else if (sender && destinationIds.includes(sender.id)) { confidence += 5; reasons.push("Nachricht liegt in Gegenrichtung"); }
    else { confidence -= 4; reasons.push("Sender liegt außerhalb des gewählten Pfads"); }
    if (item.interface_id && item.interface_id === sourceInterfaceId) { confidence += 15; reasons.push("Source Interface stimmt überein"); }
    if (iface && interfaceProtocol(iface.interface_type) === protocol) { confidence += 12; reasons.push("Protokoll kompatibel"); }
    if (source?.name && normalizedName(item.name).includes(normalizedName(source.name))) { confidence += 12; reasons.push("Name passt zum Producer"); }
    if (sender?.id === sourceId && item.direction === "tx") { confidence += 3; reasons.push("Senderichtung TX"); }
    if (route.payload.message_id === item.id) { confidence += 2; reasons.push("bereits zugeordnet"); }
    return { id: item.id, label: item.name, confidence: Math.max(5, Math.min(99, confidence)), reason: reasons.join(" · ") };
  }

  const sortedMessages = [...messages].sort((left, right) => (
    messageSuggestion(right).confidence - messageSuggestion(left).confidence
    || left.name.localeCompare(right.name, "de")
  ));
  const senderMessages = sortedMessages.filter((item) => messageSenderNode(item)?.id === sourceId);

  useEffect(() => {
    const allowed = new Set(senderMessages.map((item) => item.id));
    setMessageIds((current) => current.filter((id) => allowed.has(id)));
    setSignalIds((current) => current.filter((id) => {
      const signal = signals.find((item) => item.id === id);
      return !signal?.message_id || allowed.has(signal.message_id);
    }));
  }, [sourceId]);

  function topMessageSuggestions() {
    return senderMessages
      .map(messageSuggestion)
      .slice(0, 3);
  }

  function applySourceInterface(id: string) {
    const iface = interfaces.find((item) => item.id === id);
    setSourceInterfaceId(id);
    if (iface) {
      setProtocol(interfaceProtocol(iface.interface_type));
      setSourceNetworkId(networkId(iface) ?? "");
    }
  }

  function applyMessage(id: string) {
    if (!id) return;
    setPayloadMode("message");
    setMessageIds((current) => current.includes(id) ? current : [...current, id]);
    const msg = messages.find((item) => item.id === id);
    setInterfaceDefinitionId((current) => current || msg?.interface_id || "");
    if (msg?.cycle_ms && !cycle) setCycle(String(msg.cycle_ms));
    if (msg?.dlc && (!route.payload.signal_ids.length || !signalIds.length)) {
      setSignalIds(signals.filter((item) => item.message_id === id).slice(0, Math.max(1, Math.min(4, msg.dlc ?? 1))).map((item) => item.id));
    }
  }

  function toggleMessage(id: string) {
    if (messageIds.includes(id)) {
      setMessageIds((current) => current.filter((item) => item !== id));
      setSignalIds((current) => current.filter((signalId) => signals.find((item) => item.id === signalId)?.message_id !== id));
      return;
    }
    applyMessage(id);
  }

  function preferredInterfaceForNode(nodeId: string) {
    return interfaces.find((item) => item.hardware_node_id === nodeId && interfaceProtocol(item.interface_type) === protocol)
      ?? interfaces.find((item) => item.hardware_node_id === nodeId)
      ?? null;
  }

  function toggleDestination(id: string) {
    if (destinationIds.includes(id)) {
      setDestinationIds((current) => current.filter((item) => item !== id));
      return;
    }
    const candidate = preferredInterfaceForNode(id);
    setDestinationIds((current) => [...current, id]);
    setDestinationInterfaces((current) => ({ ...current, [id]: current[id] || candidate?.id || "" }));
    setDestinationNetworks((current) => ({ ...current, [id]: current[id] || networkId(candidate ?? undefined) || "" }));
    setDestinationProtocols((current) => ({ ...current, [id]: current[id] || (candidate ? interfaceProtocol(candidate.interface_type) : protocol) }));
  }

  function toggleSignal(id: string) { setSignalIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]); }
  function toggleGateway(id: string) { setGatewayIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]); }

  function applyBestSourceInterface() {
    const candidate = preferredInterfaceForNode(sourceId);
    if (candidate) applySourceInterface(candidate.id);
  }

  function applyBestDestinationInterfaces() {
    for (const nodeId of destinationIds) {
      const candidate = preferredInterfaceForNode(nodeId);
      if (!candidate) continue;
      setDestinationInterfaces((current) => ({ ...current, [nodeId]: current[nodeId] || candidate.id }));
      setDestinationNetworks((current) => ({ ...current, [nodeId]: current[nodeId] || networkId(candidate) || "" }));
      setDestinationProtocols((current) => ({ ...current, [nodeId]: current[nodeId] || interfaceProtocol(candidate.interface_type) }));
    }
  }

  function applyBestPayload() {
    const candidate = topMessageSuggestions()[0];
    if (candidate) applyMessage(candidate.id);
  }

  function chooseDifferentPayload() {
    const currentId = messageIds[0] ?? "";
    const currentIndex = senderMessages.findIndex((item) => item.id === currentId);
    const next = senderMessages.find((item, index) => item.id !== currentId && index > currentIndex)
      ?? senderMessages.find((item) => item.id !== currentId);
    if (next) applyMessage(next.id);
  }

  function applyBusDefaults() {
    const iface = interfaces.find((item) => item.id === sourceInterfaceId);
    const protocolName = iface ? interfaceProtocol(iface.interface_type) : protocol;
    const defaults = protocolName === "LIN" ? ["20", "200", "50", "10"] : protocolName === "CAN_FD" ? ["10", "100", "20", "5"] : ["10", "100", "20", "2"];
    if (!cycle) setCycle(defaults[0]);
    if (!timeout) setTimeoutValue(defaults[1]);
    if (!latency) setLatency(defaults[2]);
    if (!jitter) setJitter(defaults[3]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const parsedConditions = parseRoutingConditions(conditionsText);
    if (parsedConditions.error || invalidTiming) {
      setFormError(parsedConditions.error || "Timing-Werte müssen leer oder größer als 0 sein.");
      return;
    }
    setFormError("");
    setSaving(true);
    const sourceNode = hardware.find((item) => item.id === sourceId);
    const selectedGateways = gatewayIds.map((id) => hardware.find((item) => item.id === id)).filter((item): item is HardwareNode => Boolean(item));
    const destinations = destinationIds.map((nodeId) => {
      const iface = interfaces.find((item) => item.id === destinationInterfaces[nodeId]);
      return {
        node_id: nodeId,
        port_id: optionalText(destinationPorts[nodeId] ?? ""),
        interface_id: iface?.id ?? optionalText(destinationInterfaces[nodeId] ?? ""),
        network_id: optionalText(destinationNetworks[nodeId] ?? "") ?? networkId(iface),
        protocol: destinationProtocols[nodeId] || (iface ? interfaceProtocol(iface.interface_type) : protocol),
      };
    });
    const hops = [
      { node_id: sourceId, name: sourceNode?.name },
      ...selectedGateways.map((gateway) => ({ node_id: gateway.id, name: gateway.name })),
      ...destinationIds.map((id) => ({ node_id: id, name: hardware.find((item) => item.id === id)?.name })),
    ];
    const payloadMessageIds = payloadMode === "message" ? messageIds : [];
    const payloadMessageId = payloadMessageIds[0] ?? null;
    const payloadSignalIds = payloadMode === "message" ? signalIds : [];
    const payloadTopic = payloadMode === "topic" ? optionalText(topic) : null;
    const payloadDataObject = payloadMode === "data_object" ? optionalText(dataObject) : null;
    const payload = {
      name: name.trim(),
      description: optionalText(description),
      source: { node_id: sourceId, port_id: optionalText(sourcePortId), interface_id: optionalText(sourceInterfaceId), network_id: optionalText(sourceNetworkId) ?? networkId(sourceInterface), protocol },
      payload: {
        interface_definition_id: optionalText(interfaceDefinitionId),
        interface_definition_ids: [...new Set(selectedMessages.map((item) => item.interface_id).filter((id): id is string => Boolean(id)))],
        message_id: payloadMessageId,
        message_ids: payloadMessageIds,
        signal_ids: payloadSignalIds,
        topic: payloadTopic,
        data_object: payloadDataObject,
      },
      destinations,
      route: { hops, gateways: selectedGateways.map((gateway) => ({ node_id: gateway.id, name: gateway.name })), transformations: transformations.split(",").map((item) => item.trim()).filter(Boolean), priority },
      timing: { cycle_time_ms: optionalNumber(cycle), timeout_ms: optionalNumber(timeout), max_latency_ms: optionalNumber(latency), jitter_limit_ms: optionalNumber(jitter) },
      routing_policy: { routing_type: destinationIds.length > 1 && routingType === "UNICAST" ? "MULTICAST" : routingType, redundancy, fallback_route_id: optionalText(fallbackRouteId), conditions: parsedConditions.conditions },
      actor: "routing-wizard",
    };
    try { await onSave(payload); } finally { setSaving(false); }
  }

  function nodeName(id: string) { return hardware.find((item) => item.id === id)?.name ?? id; }
  function routePathText() {
    return [nodeName(sourceId), ...gatewayIds.map(nodeName), ...destinationIds.map(nodeName)].filter(Boolean).join(" → ") || "Hardwarepfad offen";
  }

  return (
    <div className="routing-dialog-backdrop" role="presentation">
      <form aria-modal="true" className="routing-dialog routing-wizard-dialog" onSubmit={submit} role="dialog">
        <header><div><p className="eyebrow">Routing Wizard</p><h2>{route.route_code}</h2><span className="routing-wizard-path">{routePathText()}</span></div><button aria-label="Dialog schließen" onClick={onClose} type="button">×</button></header>
        {formError && <div className="notice error routing-form-error">{formError}</div>}
        <div className="routing-wizard-steps">{ROUTING_WIZARD_STEPS.map((label, index) => <button className={step === index ? "active" : ""} key={label} onClick={() => setStep(index)} type="button"><span>{String(index + 1).padStart(2, "0")}</span>{label}</button>)}</div>

        {step === 0 && <div className="routing-wizard-grid"><label>Name<input onChange={(event) => setName(event.target.value)} required value={name} /></label><label className="full-width">Beschreibung<textarea onChange={(event) => setDescription(event.target.value)} value={description} /></label><dl className="routing-object-summary routing-governance-summary full-width"><dt>Route Code</dt><dd>{route.route_code}</dd><dt>Revision</dt><dd>{route.revision}</dd><dt>Status</dt><dd>{route.status}</dd><dt>Origin</dt><dd>{route.origin}</dd><dt>Review</dt><dd>{route.review_state}</dd><dt>Approval</dt><dd>{route.approval_state}</dd><dt>Confidence</dt><dd>{route.confidence ?? "—"}</dd><dt>Source ID</dt><dd>{route.source_id ?? "—"}</dd><dt>Source Version</dt><dd>{route.source_version ?? "—"}</dd></dl></div>}

        {step === 1 && <div className="routing-wizard-grid"><label>Producer<select onChange={(event) => { const id = event.target.value; setSourceId(id); setSourceInterfaceId(""); setSourcePortId(""); setSourceNetworkId(""); setDestinationIds((current) => current.filter((item) => item !== id)); setGatewayIds((current) => current.filter((item) => item !== id)); }} value={sourceId}>{hardware.map((node) => <option key={node.id} value={node.id}>{node.name} · {node.device_type}</option>)}</select></label><label>Source Interface<select onChange={(event) => applySourceInterface(event.target.value)} value={sourceInterfaceId}><option value="">Nicht gesetzt</option>{sourceInterfaceId && !sourceInterfaces.some((item) => item.id === sourceInterfaceId) && <option value={sourceInterfaceId}>Unbekannt · {sourceInterfaceId}</option>}{sourceInterfaces.map((item) => <option key={item.id} value={item.id}>{interfaceLabel(item)}</option>)}</select></label><AiSuggestionList onPick={applySourceInterface} suggestions={topInterfaceSuggestions(sourceInterfaces)} value={sourceInterfaceId} /><NetworkSegmentDisplay value={sourceNetworkDisplay} /><details className="routing-technical-fields full-width"><summary>Technische IDs</summary><label>Source Port ID<input onChange={(event) => setSourcePortId(event.target.value)} value={sourcePortId} /></label><label>Source Network ID<input onChange={(event) => setSourceNetworkId(event.target.value)} value={sourceNetworkId} /></label></details><label>Protocol<select onChange={(event) => setProtocol(event.target.value)} value={protocol}>{schema.protocols.map((item) => <option key={item}>{item}</option>)}</select></label></div>}

        {step === 2 && (
          <div className="routing-wizard-grid">
            <div aria-label="Payload-Art" className="routing-payload-mode full-width" role="group">
              <button className={payloadMode === "message" ? "active" : ""} onClick={() => setPayloadMode("message")} type="button">Message</button>
              <button className={payloadMode === "topic" ? "active" : ""} onClick={() => setPayloadMode("topic")} type="button">Topic</button>
              <button className={payloadMode === "data_object" ? "active" : ""} onClick={() => setPayloadMode("data_object")} type="button">Data Object</button>
            </div>
            {payloadMode === "message" && (
              <>
                <div className="routing-check-list routing-message-check-list full-width">
                  <span>Messages · {messageIds.length} gewählt</span>
                  {senderMessages.length
                    ? senderMessages.map((item) => (
                        <label key={item.id}>
                          <input checked={messageIds.includes(item.id)} onChange={() => toggleMessage(item.id)} type="checkbox" />
                          {item.name}
                        </label>
                      ))
                    : <small>Für den gewählten Producer sind keine Messages vorhanden.</small>}
                </div>
                <AiSuggestionList onPick={applyMessage} suggestions={topMessageSuggestions()} value={messageIds[0] ?? ""} />
                <div className="routing-check-list full-width">
                  <span>Signals</span>
                  {selectableSignals.length
                    ? selectableSignals.map((signal) => (
                        <label key={signal.id}>
                          <input checked={signalIds.includes(signal.id)} onChange={() => toggleSignal(signal.id)} type="checkbox" />
                          {signal.display_name || signal.name}
                          <small>{signal.start_bit ?? "?"} / {signal.length_bits ?? "?"} Bit</small>
                        </label>
                      ))
                    : <small>Keine Signals verfügbar.</small>}
                </div>
              </>
            )}
            {payloadMode === "topic" && <label className="full-width">Topic<input onChange={(event) => setTopic(event.target.value)} placeholder="z. B. vehicle/thermal/status" value={topic} /></label>}
            {payloadMode === "data_object" && <label className="full-width">Data Object<input onChange={(event) => setDataObject(event.target.value)} placeholder="z. B. VehicleThermalStatus" value={dataObject} /></label>}
            <label className="full-width">Payload Interface ID<input onChange={(event) => setInterfaceDefinitionId(event.target.value)} placeholder={payloadMode === "message" ? "Wird aus den gewählten Messages übernommen" : "Optional"} value={interfaceDefinitionId} /></label>
          </div>
        )}

        {step === 3 && <div className="routing-wizard-grid"><div className="routing-check-list full-width"><span>Consumer</span>{destinationOptions.map((node) => <label key={node.id}><input checked={destinationIds.includes(node.id)} onChange={() => toggleDestination(node.id)} type="checkbox" />{node.name}<small>{node.device_type}</small></label>)}</div><div className="routing-endpoint-list full-width">{destinationIds.map((nodeId) => { const options = interfaces.filter((item) => item.hardware_node_id === nodeId); const selectedInterfaceId = destinationInterfaces[nodeId] ?? ""; const selectedInterface = options.find((item) => item.id === selectedInterfaceId); const destinationNetworkDisplay = friendlyNetworkLabel(destinationNetworks[nodeId] || networkId(selectedInterface), networkAliases, nodeName(nodeId), destinationProtocols[nodeId] || protocol); return <section className="routing-endpoint-fields" key={nodeId}><strong>{nodeName(nodeId)}</strong><label>Interface<select onChange={(event) => { const item = interfaces.find((candidate) => candidate.id === event.target.value); setDestinationInterfaces((current) => ({ ...current, [nodeId]: event.target.value })); if (item) { setDestinationNetworks((current) => ({ ...current, [nodeId]: networkId(item) ?? "" })); setDestinationProtocols((current) => ({ ...current, [nodeId]: interfaceProtocol(item.interface_type) })); } }} value={selectedInterfaceId}><option value="">Nicht gesetzt</option>{selectedInterfaceId && !options.some((item) => item.id === selectedInterfaceId) && <option value={selectedInterfaceId}>Unbekannt · {selectedInterfaceId}</option>}{options.map((item) => <option key={item.id} value={item.id}>{interfaceLabel(item)}</option>)}</select></label><NetworkSegmentDisplay value={destinationNetworkDisplay} /><details className="routing-technical-fields"><summary>IDs</summary><label>Port ID<input onChange={(event) => setDestinationPorts((current) => ({ ...current, [nodeId]: event.target.value }))} value={destinationPorts[nodeId] ?? ""} /></label><label>Network ID<input onChange={(event) => setDestinationNetworks((current) => ({ ...current, [nodeId]: event.target.value }))} value={destinationNetworks[nodeId] ?? ""} /></label></details><label>Protocol<select onChange={(event) => setDestinationProtocols((current) => ({ ...current, [nodeId]: event.target.value }))} value={destinationProtocols[nodeId] || protocol}>{schema.protocols.map((item) => <option key={item}>{item}</option>)}</select></label></section>; })}</div></div>}

        {step === 4 && <div className="routing-wizard-grid"><div className="routing-check-list full-width"><span>Gateways</span>{gateways.length ? gateways.map((gateway) => <label key={gateway.id}><input checked={gatewayIds.includes(gateway.id)} onChange={() => toggleGateway(gateway.id)} type="checkbox" />{gateway.name}<small>{gateway.device_type}</small></label>) : <small>Direkter Pfad</small>}</div><label>Routing Type<select onChange={(event) => setRoutingType(event.target.value)} value={routingType}>{schema.routing_types.map((item) => <option key={item}>{item}</option>)}</select></label><label>Priority<select onChange={(event) => setPriority(event.target.value as typeof priority)} value={priority}>{schema.priorities.map((item) => <option key={item}>{item}</option>)}</select></label><label>Redundancy<select onChange={(event) => setRedundancy(event.target.value)} value={redundancy}>{schema.redundancy_modes.map((item) => <option key={item}>{item}</option>)}</select></label><label>Fallback Route<select onChange={(event) => setFallbackRouteId(event.target.value)} value={fallbackRouteId}><option value="">Keine</option>{fallbackRouteId && !fallbackRoutes.some((item) => item.id === fallbackRouteId) && <option value={fallbackRouteId}>Unbekannt · {fallbackRouteId}</option>}{fallbackRoutes.map((item) => <option key={item.id} value={item.id}>{item.route_code} · {item.name}</option>)}</select></label><label className="full-width">Transformations<input onChange={(event) => setTransformations(event.target.value)} placeholder="CAN_SIGNAL_TO_SOMEIP_FIELD" value={transformations} /></label><label className="full-width">Conditions (JSON)<textarea onChange={(event) => setConditionsText(event.target.value)} spellCheck={false} value={conditionsText} /></label></div>}

        {step === 5 && <div className="routing-wizard-grid"><label>Cycle Time (ms)<input min="0.001" onChange={(event) => setCycle(event.target.value)} step="any" type="number" value={cycle} /></label><label>Timeout (ms)<input min="0.001" onChange={(event) => setTimeoutValue(event.target.value)} step="any" type="number" value={timeout} /></label><label>Maximum Latency (ms)<input min="0.001" onChange={(event) => setLatency(event.target.value)} step="any" type="number" value={latency} /></label><label>Jitter (ms)<input min="0.001" onChange={(event) => setJitter(event.target.value)} step="any" type="number" value={jitter} /></label><button className="button secondary" onClick={applyBusDefaults} type="button">Leere Timing-Felder per Bus füllen</button></div>}

        {step === 6 && <div className="routing-wizard-review"><div className={missing.length ? "routing-wizard-verdict invalid" : "routing-wizard-verdict valid"}><strong>{missing.length ? "Noch nicht valide" : "Bereit zur Validierung"}</strong><span>{missing.length ? `${missing.length} Punkt(e) fehlen.` : "Die Route hat alle Wizard-Pflichtangaben."}</span></div>{missing.length > 0 && <div className="routing-wizard-checks">{missing.map((item) => <span key={item}>{item}</span>)}</div>}<RoutingRepairPanel applyBestDestinationInterfaces={applyBestDestinationInterfaces} applyBestPayload={applyBestPayload} applyBestSourceInterface={applyBestSourceInterface} canDelete={canDeleteRoute(route)} chooseDifferentPayload={chooseDifferentPayload} hasIssue={hasIssue} issues={validationIssues} onDelete={onDelete} setStep={setStep} />{route.validation?.errors?.length ? <div className="routing-wizard-findings"><strong>Aktuelle Findings</strong>{route.validation.errors.map((issue) => <small className="routing-issue error" key={issue.code}>{issue.message}</small>)}</div> : null}<RoutingWizardSummary conditionsText={conditionsText} dataObject={dataObject} description={description} destinationIds={destinationIds} destinationInterfaces={destinationInterfaces} destinationNetworks={destinationNetworks} destinationPorts={destinationPorts} destinationProtocols={destinationProtocols} fallbackRouteId={fallbackRouteId} gatewayIds={gatewayIds} hardware={hardware} interfaceDefinitionId={interfaceDefinitionId} interfaces={interfaces} message={selectedMessage} name={name} networkAliases={networkAliases} payloadMode={payloadMode} priority={priority} protocol={protocol} redundancy={redundancy} route={route} routingType={routingType} sourceId={sourceId} sourceInterfaceId={sourceInterfaceId} sourceNetworkId={sourceNetworkId} sourcePortId={sourcePortId} signals={signals.filter((item) => signalIds.includes(item.id))} timing={{ cycle, timeout, latency, jitter }} topic={topic} transformations={transformations} /></div>}

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
        <button className="button secondary tiny" onClick={() => { chooseDifferentPayload(); setStep(2); }} type="button">Anderen Payload vorschlagen</button>
        <button className="button secondary tiny" onClick={() => setStep(3)} type="button">Ziel ändern</button>
        {canDelete && <button className="button danger tiny" disabled={deleting} onClick={() => { setDeleting(true); void onDelete().finally(() => setDeleting(false)); }} type="button">{deleting ? "Löscht ..." : "Duplikat löschen"}</button>}
      </>,
    } : null,
    hasIssue("SOURCE_INTERFACE_MISSING") || hasIssue("SOURCE_INTERFACE_NOT_FOUND") || hasIssue("SOURCE_INTERFACE_MISMATCH") ? {
      key: "source-interface",
      title: "Source Interface",
      text: "Der Producer braucht ein passendes Interface zum gewählten Bus, sonst kann die Route nicht sauber auf das Netzwerk gelegt werden.",
      actions: <>
        <button className="button primary tiny" onClick={applyBestSourceInterface} type="button">Passendes Interface setzen</button>
        <button className="button secondary tiny" onClick={() => setStep(1)} type="button">Quelle prüfen</button>
      </>,
    } : null,
    hasIssue("DESTINATION_INTERFACE_MISSING") || hasIssue("DESTINATION_INTERFACE_NOT_FOUND") || hasIssue("DESTINATION_INTERFACE_MISMATCH") ? {
      key: "destination-interface",
      title: "Destination Interface",
      text: "Mindestens ein Consumer hat kein passendes Ziel-Interface. Der Wizard kann die beste technische Schnittstelle vorbelegen.",
      actions: <>
        <button className="button primary tiny" onClick={applyBestDestinationInterfaces} type="button">Ziel-Interfaces setzen</button>
        <button className="button secondary tiny" onClick={() => setStep(3)} type="button">Ziele prüfen</button>
      </>,
    } : null,
    hasIssue("PAYLOAD_UNSPECIFIED") ? {
      key: "payload",
      title: "Payload fehlt",
      text: "Die Route braucht eine Message, ein Signal oder ein Topic. Der Wizard schlägt eine Message passend zu Sender, Namen und Bus vor.",
      actions: <>
        <button className="button primary tiny" onClick={applyBestPayload} type="button">Payload vorschlagen</button>
        <button className="button secondary tiny" onClick={() => setStep(2)} type="button">Payload auswählen</button>
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

function AiSuggestionList({ suggestions, value, onPick }: { suggestions: Array<{ id: string; label: string; confidence: number; reason: string }>; value: string; onPick: (id: string) => void }) {
  if (!suggestions.length) return null;
  return <div className="routing-ai-suggestions full-width"><span>Technische Vorschläge</span>{suggestions.map((item) => <button className={item.id === value ? "active" : ""} key={item.id} onClick={() => onPick(item.id)} type="button"><strong>{item.confidence}% Match</strong><span>{item.label}</span><small>{item.reason}</small></button>)}</div>;
}

function RoutingWizardSummary({ route, name, description, sourceId, sourcePortId, sourceInterfaceId, sourceNetworkId, protocol, destinationIds, destinationInterfaces, destinationPorts, destinationNetworks, destinationProtocols, hardware, interfaces, networkAliases, payloadMode, message, signals, interfaceDefinitionId, topic, dataObject, gatewayIds, transformations, priority, routingType, redundancy, fallbackRouteId, conditionsText, timing }: {
  route: RoutingEntry;
  name: string;
  description: string;
  sourceId: string;
  sourcePortId: string;
  sourceInterfaceId: string;
  sourceNetworkId: string;
  protocol: string;
  destinationIds: string[];
  destinationInterfaces: Record<string, string>;
  destinationPorts: Record<string, string>;
  destinationNetworks: Record<string, string>;
  destinationProtocols: Record<string, string>;
  hardware: HardwareNode[];
  interfaces: EngInterface[];
  networkAliases: Map<string, string>;
  payloadMode: RoutingPayloadMode;
  message?: EngMessage;
  signals: EngSignal[];
  interfaceDefinitionId: string;
  topic: string;
  dataObject: string;
  gatewayIds: string[];
  transformations: string;
  priority: string;
  routingType: string;
  redundancy: string;
  fallbackRouteId: string;
  conditionsText: string;
  timing: { cycle: string; timeout: string; latency: string; jitter: string };
}) {
  const nodeName = (id: string) => hardware.find((item) => item.id === id)?.name ?? id;
  const ifaceName = (id: string) => (interfaces.find((item) => item.id === id)?.name ?? id) || "Nicht gesetzt";
  return (
    <div className="routing-wizard-summary">
      <section><h3>Allgemein</h3><dl><dt>Name</dt><dd>{name || "Nicht gesetzt"}</dd><dt>Beschreibung</dt><dd>{description || "Nicht gesetzt"}</dd><dt>Route Code</dt><dd>{route.route_code}</dd><dt>Revision</dt><dd>{route.revision}</dd><dt>Status</dt><dd>{route.status}</dd><dt>Origin</dt><dd>{route.origin}</dd></dl></section>
      <section><h3>Quelle</h3><dl><dt>Producer</dt><dd>{nodeName(sourceId)}</dd><dt>Interface</dt><dd>{ifaceName(sourceInterfaceId)}</dd><dt>Netzsegment</dt><dd>{friendlyNetworkLabel(sourceNetworkId, networkAliases, nodeName(sourceId), protocol)}</dd><dt>Technische IDs</dt><dd>{sourcePortId || "—"} · {sourceNetworkId || "—"}</dd><dt>Protocol</dt><dd>{protocol}</dd></dl></section>
      <section><h3>Payload</h3><dl><dt>Payload-Art</dt><dd>{payloadMode === "message" ? "Message" : payloadMode === "topic" ? "Topic" : "Data Object"}</dd>{payloadMode === "message" && <><dt>Message</dt><dd>{message?.name ?? "Nicht gesetzt"}</dd><dt>Message ID</dt><dd>{message?.message_id_hex ?? "Nicht gesetzt"}</dd><dt>Signals</dt><dd>{signals.map((item) => item.display_name || item.name).join(", ") || "Keine Signals gewählt"}</dd></>}{payloadMode === "topic" && <><dt>Topic</dt><dd>{topic || "Nicht gesetzt"}</dd></>}{payloadMode === "data_object" && <><dt>Data Object</dt><dd>{dataObject || "Nicht gesetzt"}</dd></>}<dt>Payload Interface ID</dt><dd>{interfaceDefinitionId || "Nicht gesetzt"}</dd></dl></section>
      <section><h3>Ziele</h3><dl>{destinationIds.map((id) => <div className="routing-summary-endpoint" key={id}><dt>{nodeName(id)}</dt><dd>{ifaceName(destinationInterfaces[id] ?? "")} · {friendlyNetworkLabel(destinationNetworks[id], networkAliases, nodeName(id), destinationProtocols[id] || protocol)} · {destinationProtocols[id] || protocol}</dd></div>)}</dl></section>
      <section><h3>Pfad & Policy</h3><dl><dt>Gateways</dt><dd>{gatewayIds.map(nodeName).join(", ") || "Direkter Pfad"}</dd><dt>Transformations</dt><dd>{transformations || "Keine"}</dd><dt>Priority</dt><dd>{priority}</dd><dt>Routing Type</dt><dd>{routingType}</dd><dt>Redundancy</dt><dd>{redundancy}</dd><dt>Fallback Route</dt><dd>{fallbackRouteId || "Keine"}</dd><dt>Conditions</dt><dd><code>{conditionsText}</code></dd></dl></section>
      <section><h3>Timing</h3><dl><dt>Cycle</dt><dd>{timing.cycle || "Nicht gesetzt"} ms</dd><dt>Timeout</dt><dd>{timing.timeout || "Nicht gesetzt"} ms</dd><dt>Latency</dt><dd>{timing.latency || "Nicht gesetzt"} ms</dd><dt>Jitter</dt><dd>{timing.jitter || "Nicht gesetzt"} ms</dd></dl></section>
    </div>
  );
}

function compactNetworkToken(value?: string | null) {
  return String(value || "")
    .replace(/(?:[-_\s]*(?:ECU|Gateway|BCM|Sensor|Aktor|Aktuator|Actuator))+$/gi, "")
    .replace(/[\s-]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "");
}

function interfaceProtocol(type: string) { return ({ CAN: "CAN", CAN_FD: "CAN_FD", LIN: "LIN", FlexRay: "FLEXRAY", Ethernet: "ETHERNET", EtherCAT: "ETHERCAT", ProfiNET: "PROFINET", ModbusTCP: "MODBUS", ModbusRTU: "MODBUS", OPCUA: "OPC_UA" } as Record<string, string>)[type] ?? "CUSTOM"; }

function networkId(item?: EngInterface) {
  if (!item) return null;
  const configured = item.configuration?.network_id ?? item.configuration?.network ?? item.configuration?.bus;
  const value = String(configured || item.interface_type).trim();
  if (!value) return null;
  return value.startsWith("network-") ? value : `network-${value.toLowerCase()}`;
}

function buildNetworkAliases(interfaces: EngInterface[], hardware: HardwareNode[]) {
  const nodes = new Map(hardware.map((node) => [node.id, node]));
  const grouped = new Map<string, Array<{ base: string; protocol: string }>>();
  for (const item of interfaces) {
    const raw = networkId(item);
    if (!raw) continue;
    const node = nodes.get(item.hardware_node_id ?? "");
    const base = compactNetworkToken(node?.name) || compactNetworkToken(item.name) || "Netz";
    const protocol = interfaceProtocol(item.interface_type);
    grouped.set(raw, [...(grouped.get(raw) ?? []), { base, protocol }]);
  }
  const counters = new Map<string, number>();
  const aliases = new Map<string, string>();
  for (const [raw, entries] of [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right, "de"))) {
    const preferred = [...entries].sort((left, right) => left.base.localeCompare(right.base, "de"))[0];
    const stem = `${preferred.base}_${preferred.protocol}`;
    const next = (counters.get(stem) ?? 0) + 1;
    counters.set(stem, next);
    aliases.set(raw, `${stem}_${next}`);
  }
  return aliases;
}

function friendlyNetworkLabel(raw: string | null | undefined, aliases: Map<string, string>, fallbackName?: string | null, protocol?: string | null) {
  const value = String(raw || "").trim();
  if (!value) return "Nicht gesetzt";
  const known = aliases.get(value);
  if (known) return known;
  const base = compactNetworkToken(fallbackName) || "Netz";
  const suffix = compactNetworkToken(protocol) || value.replace(/^network-/i, "").split("-")[0]?.toUpperCase() || "Segment";
  return `${base}_${suffix}_1`;
}

function NetworkSegmentDisplay({ value }: { value: string }) {
  return <div className="routing-network-display"><span>Netzsegment</span><strong>{value}</strong><small>Technische ID im Hintergrund.</small></div>;
}

function Status({ value }: { value: string }) { return <span className={`routing-status ${value.toLowerCase().replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>; }
function EmptyRouting({ text }: { text: string }) { return <div className="empty-result routing-empty"><span className="empty-icon">◇</span><strong>{text}</strong></div>; }
