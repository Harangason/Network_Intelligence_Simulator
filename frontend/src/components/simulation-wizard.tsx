"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { getCatalog } from "@/lib/api";
import { listAllEngineeringObjects, syncEngineeringTopology } from "@/lib/engineering-api";
import { localCatalog } from "@/lib/local-simulator";
import { listRoutes } from "@/lib/routing-api";
import type { Catalog, HardwareNode, RoutingEntry, Technology, TechnologyParameterField } from "@/lib/types";
import { NetworkEditor } from "./network-editor";
import {
  busProfiles,
  engineeringHardwareKind,
  initialTopology,
  type BusType,
  type NetworkTopology,
  type TopologyNode,
  type TopologyPort,
} from "@/lib/topology";
import { readUserSettings, SETTINGS_EVENT, type UserSettings } from "@/lib/user-settings";
import { getWorkflow, saveWorkflowParameters, saveWorkflowTopology } from "@/lib/workflow-api";
import { notifyWorkflowChanged } from "./workflow-header";

const universalFormats = ["universal-jsonl", "universal-csv"];
const parameterCategoryLabels: Record<TechnologyParameterField["category"], string> = {
  physical: "Netzwerk & Physik",
  timing: "Timing",
  capacity: "Capacity",
  qos: "Scheduling & QoS",
  reliability: "Reliability",
  synchronization: "Synchronisation",
  gateway: "Gateway",
  simulation: "Simulation",
};

type RoutingNetworkSegment = {
  sourceId: string;
  targetId: string;
  bus: BusType;
  sourceInterfaceId?: string | null;
  targetInterfaceId?: string | null;
};

type RoutingNetworkSuggestion = {
  route: RoutingEntry;
  path: string;
  protocol: string;
  segments: RoutingNetworkSegment[];
};

const inactiveRouteStatuses = new Set(["REJECTED", "OUTDATED", "SUPERSEDED"]);

function routingBus(protocol?: string | null, networkId?: string | null): BusType {
  const value = `${protocol ?? ""} ${networkId ?? ""}`.toUpperCase();
  if (value.includes("FLEX")) return "flexray";
  if (value.includes("LIN")) return "lin";
  if (["ETH", "SOME", "TCP", "UDP", "DDS", "IP"].some((item) => value.includes(item))) {
    return "automotive_ethernet";
  }
  return "can_fd";
}

function routeNodeId(value: string | { node_id?: string; name?: string }) {
  return typeof value === "string" ? value : value.node_id ?? "";
}

function routePath(route: RoutingEntry, destinationId: string) {
  const declaredHops = route.route.hops.map(routeNodeId).filter(Boolean);
  const destinationIndex = declaredHops.indexOf(destinationId);
  if (declaredHops[0] === route.source.node_id && destinationIndex > 0) {
    return declaredHops.slice(0, destinationIndex + 1);
  }
  const gateways = route.route.gateways.map(routeNodeId).filter(Boolean);
  return [route.source.node_id, ...gateways, destinationId].filter(
    (item, index, values) => item && item !== values[index - 1],
  );
}

function physicalPathExists(topology: NetworkTopology, sourceId: string, targetId: string) {
  const nodeIds = new Map(
    topology.nodes
      .filter((node) => node.engineeringId)
      .map((node) => [node.engineeringId as string, node.id]),
  );
  const sourceTopologyId = nodeIds.get(sourceId);
  const targetTopologyId = nodeIds.get(targetId);
  if (!sourceTopologyId || !targetTopologyId) return false;
  const adjacency = new Map<string, Set<string>>();
  for (const edge of topology.edges) {
    adjacency.set(edge.source, new Set([...(adjacency.get(edge.source) ?? []), edge.target]));
    adjacency.set(edge.target, new Set([...(adjacency.get(edge.target) ?? []), edge.source]));
  }
  const reachable = new Set([sourceTopologyId]);
  const pending = [sourceTopologyId];
  while (pending.length > 0) {
    const current = pending.shift()!;
    for (const neighbor of adjacency.get(current) ?? []) {
      if (neighbor === targetTopologyId) return true;
      if (!reachable.has(neighbor)) {
        reachable.add(neighbor);
        pending.push(neighbor);
      }
    }
  }
  return sourceTopologyId === targetTopologyId;
}

function buildRoutingNetworkSuggestions(
  routes: RoutingEntry[],
  topology: NetworkTopology,
  hardware: HardwareNode[],
): RoutingNetworkSuggestion[] {
  const names = new Map([
    ...hardware.map((node) => [node.id, node.name] as const),
    ...topology.nodes
      .filter((node) => node.engineeringId)
      .map((node) => [node.engineeringId as string, node.name] as const),
  ]);
  return routes
    .filter(
      (route) =>
        route.origin !== "NETWORK_EDITOR" &&
        !inactiveRouteStatuses.has(route.status),
    )
    .flatMap((route) => {
      const segments = new Map<string, RoutingNetworkSegment>();
      for (const destination of route.destinations) {
        const path = routePath(route, destination.node_id);
        for (let index = 0; index < path.length - 1; index += 1) {
          const sourceId = path[index];
          const targetId = path[index + 1];
          if (physicalPathExists(topology, sourceId, targetId)) continue;
          const lastSegment = index === path.length - 2;
          const bus = routingBus(
            lastSegment ? destination.protocol ?? route.source.protocol : route.source.protocol,
            lastSegment ? destination.network_id ?? route.source.network_id : route.source.network_id,
          );
          segments.set(`${sourceId}:${targetId}:${bus}`, {
            sourceId,
            targetId,
            bus,
            sourceInterfaceId: index === 0 ? route.source.interface_id : null,
            targetInterfaceId: lastSegment ? destination.interface_id : null,
          });
        }
      }
      if (segments.size === 0) return [];
      const pathNames = routePath(route, route.destinations[0]?.node_id ?? "")
        .map((id) => names.get(id) ?? id)
        .join(" → ");
      return [{
        route,
        path: pathNames || route.name,
        protocol: route.source.protocol ?? "CUSTOM",
        segments: [...segments.values()],
      }];
    });
}

export function SimulationWizard({
  initialMode = "parameters",
}: {
  initialMode?: "parameters" | "network";
}) {
  const [catalog, setCatalog] = useState<Catalog>(localCatalog);
  const [catalogError, setCatalogError] = useState("");
  const [domainId, setDomainId] = useState("automotive");
  const [technologyId, setTechnologyId] = useState("can_fd");
  const [formats, setFormats] = useState<string[]>(universalFormats);
  const [advanced, setAdvanced] = useState(false);
  const [advancedConfig, setAdvancedConfig] = useState(
    '{\n  "name": "custom_simulation",\n  "duration_s": 1,\n  "formats": ["universal-jsonl"]\n}',
  );
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [storedParameters, setStoredParameters] = useState<Record<string, unknown>>({});
  const mode = initialMode;
  const [topology, setTopology] = useState<NetworkTopology>(initialTopology);
  const [modelHardware, setModelHardware] = useState<HardwareNode[]>([]);
  const [routingEntries, setRoutingEntries] = useState<RoutingEntry[]>([]);
  const [routingLoadError, setRoutingLoadError] = useState("");
  const [applyingRoute, setApplyingRoute] = useState("");
  const [syncRequest, setSyncRequest] = useState(0);
  const [automaticModelSync, setAutomaticModelSync] = useState(true);
  const [engineeringSync, setEngineeringSync] = useState<{
    status: "idle" | "syncing" | "synced" | "error";
    linked: number;
    error: string;
  }>({ status: "idle", linked: 0, error: "" });
  const [routingSyncMessage, setRoutingSyncMessage] = useState("");

  const topologySignature = useMemo(
    () =>
      JSON.stringify({
        nodes: topology.nodes.map((node) => ({
          id: node.id,
          name: node.name,
          kind: node.kind,
          engineeringId: node.engineeringId,
          ports: node.ports.map((port) => ({ id: port.id, name: port.name, bus: port.bus })),
        })),
        edges: topology.edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          sourcePort: edge.sourcePort,
          target: edge.target,
          targetPort: edge.targetPort,
          bus: edge.bus,
        })),
      }),
    [topology],
  );

  const persistNetworkRelationships = useCallback(async (next: NetworkTopology) => {
    setRoutingSyncMessage("Routing-Vorschläge werden abgeglichen …");
    try {
      const state = await saveWorkflowTopology(next);
      if (Array.isArray(state.topology.nodes) && Array.isArray(state.topology.edges)) {
        setTopology({ nodes: state.topology.nodes, edges: state.topology.edges });
      }
      const counts = state.routing_sync?.counts;
      if (!counts) {
        setRoutingSyncMessage("Netzwerkbeziehungen gespeichert.");
      } else if (counts.created > 0 || counts.outdated > 0) {
        setRoutingSyncMessage(
          `${counts.created} Routing-Vorschlag/Vorschläge erzeugt · ${counts.outdated} Route(n) veraltet`,
        );
      } else if (counts.skipped > 0) {
        setRoutingSyncMessage("Routing-Vorschlag wartet auf eine Engineering-Verknüpfung.");
      } else {
        setRoutingSyncMessage("Routing und Netzwerk sind synchron.");
      }
      notifyWorkflowChanged();
      return true;
    } catch (error) {
      setRoutingSyncMessage(
        error instanceof Error ? error.message : "Routing-Synchronisierung fehlgeschlagen.",
      );
      return false;
    }
  }, []);

  useEffect(() => {
    getCatalog()
      .then(setCatalog)
      .catch((error) =>
        setCatalogError(
          error instanceof Error
            ? error.message
            : "Technologiekatalog konnte nicht geladen werden.",
        ),
      );
  }, []);

  useEffect(() => {
    getWorkflow()
      .then((state) => {
        setStoredParameters(state.parameters ?? {});
        const storedTopology = state.topology;
        if (Array.isArray(storedTopology.nodes) && Array.isArray(storedTopology.edges)) {
          setTopology({ nodes: storedTopology.nodes, edges: storedTopology.edges });
        }
        if (typeof state.parameters.industry === "string") setDomainId(state.parameters.industry);
        if (typeof state.parameters.technology === "string") setTechnologyId(state.parameters.technology);
        if (Array.isArray(state.parameters.formats)) {
          setFormats(state.parameters.formats.map(String));
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (mode !== "network") return;
    setRoutingLoadError("");
    listRoutes()
      .then(setRoutingEntries)
      .catch((error) => {
        setRoutingLoadError(
          error instanceof Error ? error.message : "Routing-Tabelle konnte nicht geladen werden.",
        );
      });
  }, [mode]);

  useEffect(() => {
    setAutomaticModelSync(readUserSettings().automaticModelSync);
    const update = (event: Event) => {
      setAutomaticModelSync((event as CustomEvent<UserSettings>).detail.automaticModelSync);
    };
    window.addEventListener(SETTINGS_EVENT, update);
    return () => window.removeEventListener(SETTINGS_EVENT, update);
  }, []);

  useEffect(() => {
    if (mode !== "network") return;
    if (!automaticModelSync && syncRequest === 0) {
      return;
    }
    let cancelled = false;
    const timeout = window.setTimeout(() => {
      setEngineeringSync((current) => ({ ...current, status: "syncing", error: "" }));
      Promise.all([
        listAllEngineeringObjects("hardware-nodes"),
        syncEngineeringTopology(topology),
      ])
        .then(([items, result]) => {
          if (cancelled) return;
          setModelHardware(items.filter((item): item is HardwareNode => "device_type" in item));
          const nodesById = new Map(result.nodes.map((node) => [node.topology_node_id, node]));
          const edgesById = new Map(result.edges.map((edge) => [edge.topology_edge_id, edge]));
          setTopology({
            nodes: topology.nodes.map((node) => {
              const linked = nodesById.get(node.id);
              const interfacesById = new Map(
                linked?.interfaces.map((item) => [item.topology_port_id, item.engineering_id]) ?? [],
              );
              return {
                ...node,
                engineeringId: linked?.engineering_id,
                engineeringFunctionId: linked?.function_id,
                ports: node.ports.map((port) => ({
                  ...port,
                  engineeringId: interfacesById.get(port.id),
                })),
              };
            }),
            edges: topology.edges.map((edge) => ({
              ...edge,
              engineeringRelationId: edgesById.get(edge.id)?.engineering_relation_id,
            })),
          });
          setEngineeringSync({
            status: "synced",
            linked: result.counts.hardware_nodes,
            error: "",
          });
          if (!automaticModelSync) setSyncRequest(0);
        })
        .catch((error) => {
          if (!cancelled) {
            setEngineeringSync({
              status: "error",
              linked: 0,
              error: error instanceof Error ? error.message : "Modellabgleich fehlgeschlagen.",
            });
          }
        });
    }, 500);
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [automaticModelSync, mode, syncRequest, topologySignature]);

  const domain = useMemo(
    () => catalog?.domains.find((item) => item.id === domainId),
    [catalog, domainId],
  );
  const technology = useMemo(
    () => domain?.technologies.find((item) => item.id === technologyId),
    [domain, technologyId],
  );
  const availableFormats = useMemo(
    () =>
      Array.from(
        new Set([...universalFormats, ...(technology?.native_formats ?? [])]),
      ),
    [technology],
  );
  const parameterGroups = useMemo(() => {
    const groups = new Map<TechnologyParameterField["category"], TechnologyParameterField[]>();
    for (const field of technology?.parameter_schema ?? []) {
      const category = field.category ?? "physical";
      groups.set(category, [...(groups.get(category) ?? []), field]);
    }
    return Array.from(groups.entries());
  }, [technology]);
  const routingNetworkSuggestions = useMemo(
    () => buildRoutingNetworkSuggestions(routingEntries, topology, modelHardware),
    [modelHardware, routingEntries, topology],
  );

  function chooseDomain(value: string) {
    setDomainId(value);
    const nextDomain = catalog?.domains.find((item) => item.id === value);
    const nextTechnology = nextDomain?.technologies[0];
    if (nextTechnology) {
      setTechnologyId(nextTechnology.id);
      setFormats(universalFormats);
    }
  }

  function chooseTechnology(value: string) {
    setTechnologyId(value);
    setFormats(universalFormats);
  }

  function toggleFormat(format: string) {
    setFormats((current) =>
      current.includes(format)
        ? current.filter((item) => item !== format)
        : [...current, format],
    );
  }

  async function applyRoutingSuggestion(suggestion: RoutingNetworkSuggestion) {
    setApplyingRoute(suggestion.route.id);
    setFormError("");
    const nodes: TopologyNode[] = topology.nodes.map((node) => ({
      ...node,
      ports: node.ports.map((port) => ({ ...port })),
    }));
    const edges = topology.edges.map((edge) => ({ ...edge }));
    const topologyIdByEngineering = new Map(
      nodes
        .filter((node) => node.engineeringId)
        .map((node) => [node.engineeringId as string, node.id]),
    );
    const routeKey = suggestion.route.route_code.toLowerCase().replace(/[^a-z0-9]+/g, "-");

    function ensureNode(engineeringId: string) {
      const existingId = topologyIdByEngineering.get(engineeringId);
      if (existingId) return existingId;
      const hardware = modelHardware.find((item) => item.id === engineeringId);
      if (!hardware) throw new Error(`Hardware-Knoten ${engineeringId} ist nicht im Engineering-Modell verfügbar.`);
      const index = nodes.length;
      const id = `engineering-${engineeringId}`;
      nodes.push({
        id,
        name: hardware.name,
        kind: engineeringHardwareKind(hardware),
        x: 70 + (index % 4) * 230,
        y: 100 + Math.floor(index / 4) * 145,
        ports: [],
        engineeringId,
      });
      topologyIdByEngineering.set(engineeringId, id);
      return id;
    }

    function ensurePort(
      nodeId: string,
      bus: BusType,
      side: "left" | "right",
      segmentKey: string,
      engineeringId?: string | null,
    ) {
      const node = nodes.find((item) => item.id === nodeId);
      if (!node) throw new Error(`Topologie-Knoten ${nodeId} wurde nicht gefunden.`);
      const available = node.ports.find(
        (port) =>
          port.bus === bus &&
          !edges.some((edge) => edge.sourcePort === port.id || edge.targetPort === port.id),
      );
      if (available) return available.id;
      const port: TopologyPort = {
        id: `routing-${routeKey}-${segmentKey}-${side}`,
        name: busProfiles[bus].label,
        bus,
        side,
        offset: Math.min(0.82, 0.28 + (node.ports.length % 4) * 0.18),
        engineeringId: engineeringId ?? undefined,
      };
      node.ports.push(port);
      return port.id;
    }

    try {
      suggestion.segments.forEach((segment, index) => {
        const sourceNodeId = ensureNode(segment.sourceId);
        const targetNodeId = ensureNode(segment.targetId);
        if (edges.some(
          (edge) =>
            (edge.source === sourceNodeId && edge.target === targetNodeId) ||
            (edge.source === targetNodeId && edge.target === sourceNodeId),
        )) return;
        const sourceNode = nodes.find((node) => node.id === sourceNodeId)!;
        const targetNode = nodes.find((node) => node.id === targetNodeId)!;
        const sourceOnLeft = sourceNode.x <= targetNode.x;
        const segmentKey = `${index + 1}`;
        const sourcePort = ensurePort(
          sourceNodeId,
          segment.bus,
          sourceOnLeft ? "right" : "left",
          `${segmentKey}-source`,
          segment.sourceInterfaceId,
        );
        const targetPort = ensurePort(
          targetNodeId,
          segment.bus,
          sourceOnLeft ? "left" : "right",
          `${segmentKey}-target`,
          segment.targetInterfaceId,
        );
        edges.push({
          id: `routing-${routeKey}-${segmentKey}`,
          source: sourceNodeId,
          sourcePort,
          target: targetNodeId,
          targetPort,
          bus: segment.bus,
          routingEntryId: suggestion.route.id,
          origin: "ROUTING_TABLE",
        });
      });
      const saved = await persistNetworkRelationships({ nodes, edges });
      if (saved) {
        setRoutingSyncMessage(`${suggestion.route.route_code} wurde als physischer Netzwerkpfad übernommen.`);
      }
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Routing-Vorschlag konnte nicht übernommen werden.");
    } finally {
      setApplyingRoute("");
    }
  }

  async function submit(formElement: HTMLFormElement | null) {
    setSubmitting(true);
    setFormError("");
    setSavedMessage("");
    try {
      if (mode === "network") {
        await saveWorkflowTopology(topology);
        setSavedMessage("Netzwerktopologie gespeichert. Capacity & Timing ist jetzt gegebenenfalls veraltet.");
      } else if (advanced) {
        const parsed = JSON.parse(advancedConfig) as Record<string, unknown>;
        await saveWorkflowParameters(parsed);
        setStoredParameters(parsed);
        setSavedMessage("Parameterkonfiguration gespeichert.");
      } else {
        if (!formElement) throw new Error("Konfigurationsformular nicht gefunden.");
        const form = new FormData(formElement);
        const dynamicParameters = Object.fromEntries(
          (technology?.parameter_schema ?? []).map((field) => {
            const raw = form.get(field.key);
            if (field.type === "number") return [field.key, Number(raw)];
            if (field.type === "boolean") return [field.key, raw !== null];
            return [field.key, String(raw ?? "")];
          }),
        );
        const parameters = {
          industry: domainId,
          technology: technologyId,
          ...dynamicParameters,
          formats,
        };
        await saveWorkflowParameters(parameters);
        setStoredParameters(parameters);
        setSavedMessage("Technologie- und Timing-Parameter gespeichert.");
      }
      notifyWorkflowChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Anfrage fehlgeschlagen.");
    } finally {
      setSubmitting(false);
    }
  }

  if (catalogError) {
    return (
      <div className="panel error-card">
        <p className="eyebrow">Backend nicht erreichbar</p>
        <h2>{catalogError}</h2>
        <p className="muted">
          Starte die Anwendung mit dem gemeinsamen Web-Launcher.
        </p>
      </div>
    );
  }
  if (!domain || !technology) {
    return <div className="panel loading-panel">Technologiekatalog wird geladen …</div>;
  }

  return (
    <>
      <div className={`workspace-grid ${mode === "network" ? "network-mode" : ""}`}>
      <form
        key={`${mode}:${JSON.stringify(storedParameters)}`}
        className="panel config-panel"
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          event.preventDefault();
          void submit(event.currentTarget);
        }}
      >
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Workflow-Schritt {mode === "network" ? "03" : "04"}</p>
            <h2>{mode === "network" ? "ECU-Netzwerk" : "Konfiguration"}</h2>
          </div>
          {mode === "parameters" && (
            <label className="mode-switch">
              <input
                checked={advanced}
                onChange={(event) => setAdvanced(event.target.checked)}
                type="checkbox"
              />
              <span>JSON-Modus</span>
            </label>
          )}
        </div>

        {mode === "network" ? (
          <>
            <div className={`net-model-sync ${engineeringSync.status}`}>
              <div className="net-model-sync-status">
                <span aria-hidden="true" className="net-model-sync-dot" />
                <div>
                  <span>Engineering-Modell</span>
                  <strong>
                    {engineeringSync.status === "syncing"
                      ? "Wird synchronisiert …"
                      : engineeringSync.status === "synced"
                        ? `${engineeringSync.linked}/${topology.nodes.length} Geräte verknüpft`
                        : engineeringSync.status === "error"
                          ? "Synchronisierung fehlgeschlagen"
                          : "Noch nicht synchronisiert"}
                  </strong>
                </div>
              </div>
              <div className="net-model-sync-actions">
                <Link href="/studio/engineering">Modell öffnen ↗</Link>
                <button
                  className="net-add"
                  disabled={engineeringSync.status === "syncing"}
                  onClick={() => setSyncRequest((request) => request + 1)}
                  type="button"
                >
                  Synchronisieren
                </button>
              </div>
              {engineeringSync.error && <p>{engineeringSync.error}</p>}
            </div>
            <section className="net-route-suggestions" aria-label="Vorschläge aus der Routing-Tabelle">
              <div className="net-route-suggestions-heading">
                <div>
                  <span>Routing-Tabelle</span>
                  <strong>Vorgeschlagene physische Verbindungen</strong>
                </div>
                <Link href="/studio/routing?view=graph">Routing-Graph öffnen ↗</Link>
              </div>
              {routingLoadError ? (
                <p className="net-route-suggestions-error">{routingLoadError}</p>
              ) : routingNetworkSuggestions.length > 0 ? (
                <div className="net-route-suggestion-list">
                  {routingNetworkSuggestions.map((suggestion) => (
                    <article key={suggestion.route.id}>
                      <div className="net-route-suggestion-code">
                        <strong>{suggestion.route.route_code}</strong>
                        <span>{suggestion.route.approval_state}</span>
                      </div>
                      <div className="net-route-suggestion-path">
                        <strong>{suggestion.path}</strong>
                        <span>{suggestion.protocol} · {suggestion.segments.length} fehlende Verbindung(en)</span>
                      </div>
                      <button
                        className="net-add"
                        disabled={Boolean(applyingRoute)}
                        onClick={() => void applyRoutingSuggestion(suggestion)}
                        type="button"
                      >
                        {applyingRoute === suggestion.route.id ? "Wird übernommen …" : "In Netzwerk übernehmen"}
                      </button>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="net-route-suggestions-complete">Alle aktiven Routing-Pfade sind in der Topologie abgebildet.</p>
              )}
            </section>
            <NetworkEditor
              modelHardware={modelHardware}
              onChange={setTopology}
              onRelationshipsChange={persistNetworkRelationships}
              topology={topology}
            />
            {routingSyncMessage && <p className="net-routing-sync">{routingSyncMessage}</p>}
            <div className="network-output-row">
              <div>
                <span>Topologie</span>
                <strong>{topology.nodes.length} Geräte · {topology.edges.length} Verbindungen</strong>
              </div>
              <div className="format-inline">
                {universalFormats.map((format) => (
                  <label key={format}>
                    <input checked={formats.includes(format)} onChange={() => toggleFormat(format)} type="checkbox" />
                    {format.replace("universal-", "").toUpperCase()}
                  </label>
                ))}
              </div>
            </div>
          </>
        ) : advanced ? (
          <div className="field full-width">
            <label htmlFor="advanced_config">Vollständige Konfiguration</label>
            <textarea
              className="json-editor"
              id="advanced_config"
              onChange={(event) => setAdvancedConfig(event.target.value)}
              spellCheck={false}
              value={advancedConfig}
            />
            <small>
              Der Ausgabeordner wird aus Sicherheitsgründen vom Backend festgelegt.
            </small>
          </div>
        ) : (
          <>
            <div className="section-title">
              <span>01</span>
              Technologie
            </div>
            <div className="form-grid">
              <div className="field">
                <label htmlFor="domain">Anwendungsbereich</label>
                <select
                  id="domain"
                  onChange={(event) => chooseDomain(event.target.value)}
                  value={domainId}
                >
                  {catalog.domains.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="technology">Bus / Protokoll</label>
                <select
                  id="technology"
                  onChange={(event) => chooseTechnology(event.target.value)}
                  value={technologyId}
                >
                  {domain.technologies.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id.replaceAll("_", " ").toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <TechnologyCard technology={technology} />

            <div className="section-title">
              <span>02</span>
              Technologie- und Timing-Parameter
            </div>
            <div className="parameter-groups">
              {parameterGroups.map(([category, fields]) => (
                <fieldset className={`parameter-group parameter-group-${category}`} key={category}>
                  <legend>{parameterCategoryLabels[category]}</legend>
                  <div className="form-grid three">
                    {fields.map((field) => (
                      <ParameterControl
                        field={field}
                        key={field.key}
                        value={storedParameters[field.key] ?? field.default}
                      />
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>

            <div className="section-title">
              <span>03</span>
              Ausgabeformate
            </div>
            <div className="format-grid">
              {availableFormats.map((format) => (
                <label
                  className={`format-option ${formats.includes(format) ? "selected" : ""}`}
                  key={format}
                >
                  <input
                    checked={formats.includes(format)}
                    onChange={() => toggleFormat(format)}
                    type="checkbox"
                  />
                  <span>{format}</span>
                  <small>
                    {format.startsWith("universal") ? "Universell" : "Nativ"}
                  </small>
                </label>
              ))}
            </div>
          </>
        )}

        {formError && <div className="notice error">{formError}</div>}
        {savedMessage && <div className="notice success">{savedMessage}</div>}

        <div className="form-actions">
          <Link className="button secondary" href={mode === "network" ? "/studio?mode=parameters" : "/studio/capacity"}>
            {mode === "network" ? "Weiter zu Parametern" : "Weiter zu Capacity"}
          </Link>
          <button
            className="button primary"
            disabled={submitting || (!advanced && formats.length === 0)}
            type="submit"
          >
            {submitting ? "Wird gespeichert …" : mode === "network" ? "Netzwerk speichern →" : "Parameter speichern →"}
          </button>
        </div>
      </form>

      <aside className="side-column">
        <div className="panel overview-panel">
          <p className="eyebrow">Run overview</p>
          <h2>{mode === "network" ? "ECU TOPOLOGY" : technology.id.replaceAll("_", " ").toUpperCase()}</h2>
          <dl className="overview-list">
            {mode === "network" ? (
              <>
                <div><dt>Geräte</dt><dd>{topology.nodes.length}</dd></div>
                <div><dt>Verbindungen</dt><dd>{topology.edges.length}</dd></div>
                <div><dt>Busse</dt><dd>{new Set(topology.edges.map((edge) => edge.bus)).size}</dd></div>
                <div><dt>Formate</dt><dd>{formats.length}</dd></div>
              </>
            ) : (
              <>
                <div><dt>Bereich</dt><dd>{domain.label}</dd></div>
                <div><dt>Medium</dt><dd>{technology.medium}</dd></div>
                <div><dt>Topologie</dt><dd>{technology.topology}</dd></div>
                <div><dt>Formate</dt><dd>{formats.length}</dd></div>
              </>
            )}
          </dl>
        </div>

        <div className="empty-result workflow-next-panel">
          <strong>{mode === "network" ? "Technischen Pfad sichern" : "Berechnung folgt separat"}</strong>
          <p>
            {mode === "network"
              ? "Die Topologie beschreibt den realen Kommunikationspfad. Routing bleibt die logische Quelle."
              : "Capacity & Timing berechnet Last, Reserve und Latenz vor dem Preflight."}
          </p>
          <Link href={mode === "network" ? "/studio?mode=parameters" : "/studio/capacity"}>
            Nächsten Schritt öffnen →
          </Link>
        </div>
      </aside>
      </div>
    </>
  );
}

function ParameterControl({ field, value }: { field: TechnologyParameterField; value: unknown }) {
  const label = `${field.label}${field.unit ? ` (${field.unit})` : ""}`;
  if (field.type === "select") {
    return (
      <div className="field" title={field.description}>
        <label htmlFor={field.key}>{label}</label>
        <select defaultValue={String(value ?? "")} id={field.key} name={field.key}>
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>{option.replaceAll("_", " ")}</option>
          ))}
        </select>
      </div>
    );
  }
  if (field.type === "boolean") {
    return (
      <label className="parameter-toggle" title={field.description}>
        <input defaultChecked={Boolean(value)} name={field.key} type="checkbox" />
        <span>{label}</span>
      </label>
    );
  }
  if (field.type === "text") {
    return (
      <div className="field" title={field.description}>
        <label htmlFor={field.key}>{label}</label>
        <input defaultValue={String(value ?? "")} id={field.key} name={field.key} type="text" />
      </div>
    );
  }
  return (
    <div title={field.description}>
      <NumberField
        label={label}
        name={field.key}
        min={field.min === undefined ? undefined : String(field.min)}
        max={field.max === undefined ? undefined : String(field.max)}
        step="any"
        value={String(value ?? 0)}
      />
    </div>
  );
}

function NumberField({
  label,
  name,
  value,
  ...props
}: {
  label: string;
  name: string;
  value: string;
  min?: string;
  max?: string;
  step?: string;
}) {
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <input defaultValue={value} id={name} name={name} type="number" {...props} />
    </div>
  );
}

function TechnologyCard({ technology }: { technology: Technology }) {
  return (
    <div className="technology-card">
      <div className="technology-symbol">⌁</div>
      <div>
        <strong>{technology.family}</strong>
        <span>
          {technology.kind} · {technology.medium} · {technology.topology}
        </span>
      </div>
      <span className="tag">
        max. {(technology.max_payload_bytes ?? 0).toLocaleString("de-DE")} B
      </span>
    </div>
  );
}
