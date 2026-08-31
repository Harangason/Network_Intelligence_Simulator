"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCatalog } from "@/lib/api";
import { listAllEngineeringObjects, syncEngineeringTopology } from "@/lib/engineering-api";
import { localCatalog } from "@/lib/local-simulator";
import { listRoutes } from "@/lib/routing-api";
import type { Catalog, HardwareNode, RoutingEntry, Technology, TechnologyParameterField } from "@/lib/types";
import { NetworkEditor } from "./network-editor";
import {
  busProfiles,
  collapsePhysicalEdges,
  engineeringHardwareKind,
  normalizePhysicalTopology,
  type BusType,
  type NetworkTopology,
  type TopologyNode,
  type TopologyPort,
} from "@/lib/topology";
import { readUserSettings, SETTINGS_EVENT, type UserSettings } from "@/lib/user-settings";
import { getWorkflow, saveWorkflowParameters, saveWorkflowTopology } from "@/lib/workflow-api";
import {
  defaultSimulationFormats,
  groupSimulationFormats,
  mergeSimulationFormats,
} from "@/lib/simulation-formats";
import {
  notifyWorkflowChanged,
  notifyWorkflowDraftStatus,
  WORKFLOW_CHANGED_EVENT,
} from "./workflow-header";

const parameterNavItems = [
  ["parameter-technology", "Technologie"],
  ["parameter-values", "Parameter"],
  ["parameter-formats", "Ausgabeformate"],
] as const;
const busLoadRangeKeys = new Set([
  "target_bus_load_percent",
  "warning_threshold",
  "critical_threshold",
  "overload_threshold",
]);
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

const inactiveRouteStatuses = new Set(["REJECTED", "OUTDATED", "SUPERSEDED", "DEPRECATED"]);

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

function routingSegmentIsLinked(
  topology: NetworkTopology,
  sourceId: string,
  targetId: string,
  bus: BusType,
  routeId: string,
) {
  const nodeIds = new Map(
    topology.nodes
      .filter((node) => node.engineeringId)
      .map((node) => [node.engineeringId as string, node.id]),
  );
  const sourceTopologyId = nodeIds.get(sourceId);
  const targetTopologyId = nodeIds.get(targetId);
  if (!sourceTopologyId || !targetTopologyId) return false;
  return topology.edges.some((edge) => {
    const connectsSegment = edge.bus === bus && (
      (edge.source === sourceTopologyId && edge.target === targetTopologyId)
      || (edge.source === targetTopologyId && edge.target === sourceTopologyId)
    );
    const routeIds = new Set([
      ...(edge.routingEntryIds ?? []),
      ...(edge.routingEntryId ? [edge.routingEntryId] : []),
      ...Object.keys(edge.routingMetadata ?? {}),
    ]);
    return connectsSegment && routeIds.has(routeId);
  });
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
        !inactiveRouteStatuses.has(route.status.toUpperCase()) &&
        route.approval_state.toUpperCase() === "APPROVED" &&
        route.validation.valid === true,
    )
    .flatMap((route) => {
      const segments = new Map<string, RoutingNetworkSegment>();
      for (const destination of route.destinations) {
        const path = routePath(route, destination.node_id);
        for (let index = 0; index < path.length - 1; index += 1) {
          const sourceId = path[index];
          const targetId = path[index + 1];
          const lastSegment = index === path.length - 2;
          const bus = routingBus(
            lastSegment ? destination.protocol ?? route.source.protocol : route.source.protocol,
            lastSegment ? destination.network_id ?? route.source.network_id : route.source.network_id,
          );
          if (routingSegmentIsLinked(topology, sourceId, targetId, bus, route.id)) continue;
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

function routingSuggestionRevision(
  routes: RoutingEntry[],
  topology: NetworkTopology,
  hardware: HardwareNode[],
) {
  return JSON.stringify({
    routes: routes.map((route) => ({
      id: route.id,
      status: route.status,
      approval: route.approval_state,
      valid: route.validation.valid,
      source: route.source,
      destinations: route.destinations,
      hops: route.route.hops,
      gateways: route.route.gateways,
    })),
    nodes: topology.nodes.map((node) => ({ id: node.id, engineeringId: node.engineeringId, name: node.name })),
    edges: topology.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      bus: edge.bus,
      routingEntryId: edge.routingEntryId,
      routingEntryIds: edge.routingEntryIds,
      routingMetadata: edge.routingMetadata,
      sourceInterfaceName: edge.sourceInterfaceName,
      targetInterfaceName: edge.targetInterfaceName,
      relationType: edge.relationType,
      direction: edge.direction,
    })),
    hardware: hardware.map((node) => ({ id: node.id, name: node.name })),
  });
}

function useRoutingNetworkSuggestions(
  routes: RoutingEntry[],
  topology: NetworkTopology,
  hardware: HardwareNode[],
) {
  const cache = useRef<{ revision: string; items: RoutingNetworkSuggestion[] }>({ revision: "", items: [] });
  const revision = routingSuggestionRevision(routes, topology, hardware);
  if (cache.current.revision !== revision) {
    cache.current = {
      revision,
      items: buildRoutingNetworkSuggestions(routes, topology, hardware),
    };
  }
  return cache.current.items;
}

function engineeringTopologySignature(topology: NetworkTopology) {
  const connectedPortIds = new Set(
    topology.edges.flatMap((edge) => [edge.sourcePort, edge.targetPort]),
  );
  return JSON.stringify({
    nodes: topology.nodes.map((node) => ({
      id: node.id,
      name: node.name,
      kind: node.kind,
      engineeringId: node.engineeringId,
      systemOwnerId: node.systemOwnerId,
      ports: node.ports
        .filter((port) => port.engineeringId || connectedPortIds.has(port.id))
        .map((port) => ({
          id: port.id,
          name: port.name,
          bus: port.bus,
          engineeringId: port.engineeringId,
        })),
    })),
    edges: topology.edges.map((edge) => ({
      id: edge.id,
      name: edge.name,
      sourceInterfaceName: edge.sourceInterfaceName,
      targetInterfaceName: edge.targetInterfaceName,
      relationType: edge.relationType,
      description: edge.description,
      direction: edge.direction,
      source: edge.source,
      sourcePort: edge.sourcePort,
      target: edge.target,
      targetPort: edge.targetPort,
      bus: edge.bus,
      routingMetadata: edge.routingMetadata,
    })),
  });
}

function mergeRoutingSuggestionsIntoTopology(
  topology: NetworkTopology,
  suggestions: RoutingNetworkSuggestion[],
  modelHardware: HardwareNode[],
) {
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

  for (const suggestion of suggestions) {
    const routeKey = suggestion.route.route_code.toLowerCase().replace(/[^a-z0-9]+/g, "-");

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

    const routeSourceId = ensureNode(suggestion.route.source.node_id);
    const routeSource = nodes.find((node) => node.id === routeSourceId)!;
    for (const destination of suggestion.route.destinations) {
      const destinationId = ensureNode(destination.node_id);
      const destinationNode = nodes.find((node) => node.id === destinationId)!;
      if (["sensor", "actuator"].includes(routeSource.kind) && ["ecu", "gateway"].includes(destinationNode.kind)) {
        routeSource.systemOwnerId = destinationNode.id;
      }
      if (["sensor", "actuator"].includes(destinationNode.kind) && ["ecu", "gateway"].includes(routeSource.kind)) {
        destinationNode.systemOwnerId = routeSource.id;
      }
    }

    suggestion.segments.forEach((segment, index) => {
      const sourceNodeId = ensureNode(segment.sourceId);
      const targetNodeId = ensureNode(segment.targetId);
      const sourceNode = nodes.find((node) => node.id === sourceNodeId)!;
      const targetNode = nodes.find((node) => node.id === targetNodeId)!;
      const existingEdgeIndex = edges.findIndex(
        (edge) => edge.bus === segment.bus && (
          (edge.source === sourceNodeId && edge.target === targetNodeId)
          || (edge.source === targetNodeId && edge.target === sourceNodeId)
        ),
      );
      if (existingEdgeIndex >= 0) {
        const existingEdge = edges[existingEdgeIndex];
        const edgeSourceNode = nodes.find((node) => node.id === existingEdge.source);
        const edgeTargetNode = nodes.find((node) => node.id === existingEdge.target);
        const routeIds = [...new Set([
          ...(existingEdge.routingEntryIds ?? []),
          ...(existingEdge.routingEntryId ? [existingEdge.routingEntryId] : []),
          suggestion.route.id,
        ])];
        edges[existingEdgeIndex] = {
          ...existingEdge,
          name: routeIds.length === 1 ? `${suggestion.route.route_code} · ${sourceNode.name} → ${targetNode.name}` : existingEdge.name,
          sourceInterfaceName: existingEdge.sourceInterfaceName || edgeSourceNode?.ports.find((port) => port.id === existingEdge.sourcePort)?.name,
          targetInterfaceName: existingEdge.targetInterfaceName || edgeTargetNode?.ports.find((port) => port.id === existingEdge.targetPort)?.name,
          description: routeIds.length === 1 ? (suggestion.route.description || suggestion.route.name) : existingEdge.description,
          relationType: existingEdge.relationType ?? "COMMUNICATES_WITH",
          direction: existingEdge.direction ?? "SOURCE_TO_TARGET",
          routingEntryId: existingEdge.routingEntryId ?? suggestion.route.id,
          routingEntryIds: routeIds,
          routingMetadata: {
            ...(existingEdge.routingMetadata ?? {}),
            [suggestion.route.id]: {
              routeId: suggestion.route.id,
              routeCode: suggestion.route.route_code,
              name: suggestion.route.name,
              description: suggestion.route.description,
              source: segment.sourceId,
              target: segment.targetId,
              sourceInterfaceId: segment.sourceInterfaceId,
              targetInterfaceId: segment.targetInterfaceId,
              protocol: suggestion.route.source.protocol,
              approvalState: suggestion.route.approval_state,
            },
          },
          origin: "ROUTING_TABLE",
        };
        return;
      }
      const sourceOnLeft = sourceNode.x <= targetNode.x;
      const segmentKey = `${index + 1}`;
      const sourcePort = ensurePort(sourceNodeId, segment.bus, sourceOnLeft ? "right" : "left", `${segmentKey}-source`, segment.sourceInterfaceId);
      const targetPort = ensurePort(targetNodeId, segment.bus, sourceOnLeft ? "left" : "right", `${segmentKey}-target`, segment.targetInterfaceId);
      edges.push({
        id: `routing-${routeKey}-${segmentKey}`,
        name: `${suggestion.route.route_code} · ${sourceNode.name} → ${targetNode.name}`,
        sourceInterfaceName: sourceNode.ports.find((port) => port.id === sourcePort)?.name,
        targetInterfaceName: targetNode.ports.find((port) => port.id === targetPort)?.name,
        relationType: "COMMUNICATES_WITH",
        description: suggestion.route.description || suggestion.route.name,
        direction: "SOURCE_TO_TARGET",
        source: sourceNodeId,
        sourcePort,
        target: targetNodeId,
        targetPort,
        bus: segment.bus,
        routingEntryId: suggestion.route.id,
        routingEntryIds: [suggestion.route.id],
        routingMetadata: {
          [suggestion.route.id]: {
            routeId: suggestion.route.id,
            routeCode: suggestion.route.route_code,
            name: suggestion.route.name,
            description: suggestion.route.description,
            source: segment.sourceId,
            target: segment.targetId,
            sourceInterfaceId: segment.sourceInterfaceId,
            targetInterfaceId: segment.targetInterfaceId,
            protocol: suggestion.route.source.protocol,
            approvalState: suggestion.route.approval_state,
          },
        },
        origin: "ROUTING_TABLE",
      });
    });
  }

  return normalizePhysicalTopology({ nodes, edges: collapsePhysicalEdges(edges) });
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
  const [formats, setFormats] = useState<string[]>(defaultSimulationFormats);
  const [advanced, setAdvanced] = useState(false);
  const [advancedConfig, setAdvancedConfig] = useState(
    '{\n  "name": "custom_simulation",\n  "duration_s": 1,\n  "formats": ["universal-jsonl"]\n}',
  );
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [storedParameters, setStoredParameters] = useState<Record<string, unknown>>({});
  const mode = initialMode;
  const [topology, setTopology] = useState<NetworkTopology>(() => ({ nodes: [], edges: [] }));
  const [workflowLoaded, setWorkflowLoaded] = useState(false);
  const [modelHardware, setModelHardware] = useState<HardwareNode[]>([]);
  const [routingEntries, setRoutingEntries] = useState<RoutingEntry[]>([]);
  const [routingLoadError, setRoutingLoadError] = useState("");
  const [applyingRoute, setApplyingRoute] = useState("");
  const [applyingAllRoutes, setApplyingAllRoutes] = useState(false);
  const [syncRequest, setSyncRequest] = useState(0);
  const [automaticModelSync, setAutomaticModelSync] = useState(true);
  const [engineeringSync, setEngineeringSync] = useState<{
    status: "idle" | "syncing" | "synced" | "error";
    linked: number;
    error: string;
  }>({ status: "idle", linked: 0, error: "" });
  const [routingSyncMessage, setRoutingSyncMessage] = useState("");
  const pendingPersistSignatureRef = useRef("");

  const topologySignature = useMemo(() => engineeringTopologySignature(topology), [topology]);

  const persistNetworkRelationships = useCallback(async (next: NetworkTopology) => {
    pendingPersistSignatureRef.current = engineeringTopologySignature(next);
    setEngineeringSync((current) => ({ ...current, status: "syncing", error: "" }));
    setRoutingSyncMessage("Routing-Vorschläge werden abgeglichen …");
    try {
      const state = await saveWorkflowTopology(normalizePhysicalTopology(next));
      if (Array.isArray(state.topology.nodes) && Array.isArray(state.topology.edges)) {
        const savedTopology = normalizePhysicalTopology({ nodes: state.topology.nodes, edges: state.topology.edges });
        pendingPersistSignatureRef.current = engineeringTopologySignature(savedTopology);
        setTopology(savedTopology);
        setEngineeringSync({
          status: "synced",
          linked: savedTopology.nodes.filter((node) => node.engineeringId).length,
          error: "",
        });
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
      pendingPersistSignatureRef.current = "";
      setEngineeringSync({
        status: "error",
        linked: 0,
        error: error instanceof Error ? error.message : "Modellabgleich fehlgeschlagen.",
      });
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
          setTopology(normalizePhysicalTopology({ nodes: storedTopology.nodes, edges: storedTopology.edges }));
        } else {
          setTopology({ nodes: [], edges: [] });
        }
        if (typeof state.parameters.industry === "string") setDomainId(state.parameters.industry);
        if (typeof state.parameters.technology === "string") setTechnologyId(state.parameters.technology);
        if (Array.isArray(state.parameters.formats)) {
          setFormats(state.parameters.formats.map(String));
        }
        setWorkflowLoaded(true);
      })
      .catch((error) => {
        setFormError(error instanceof Error ? error.message : "Workflow konnte nicht geladen werden.");
      });
  }, []);

  useEffect(() => {
    if (mode !== "parameters") return;
    return () => notifyWorkflowDraftStatus("parameters", null);
  }, [mode]);

  useEffect(() => {
    if (mode !== "network") return;
    let active = true;
    const refreshRoutes = () => {
      setRoutingLoadError("");
      void listRoutes()
        .then((items) => {
          if (active) setRoutingEntries(items);
        })
        .catch((error) => {
          if (!active) return;
          setRoutingLoadError(
            error instanceof Error ? error.message : "Routing-Tabelle konnte nicht geladen werden.",
          );
        });
    };
    refreshRoutes();
    window.addEventListener(WORKFLOW_CHANGED_EVENT, refreshRoutes);
    return () => {
      active = false;
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, refreshRoutes);
    };
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
    if (mode !== "network" || !workflowLoaded) return;
    if (topology.nodes.length === 0) {
      setEngineeringSync({ status: "idle", linked: 0, error: "" });
      setModelHardware([]);
      return;
    }
    if (!automaticModelSync && syncRequest === 0) {
      return;
    }
    if (syncRequest === 0 && pendingPersistSignatureRef.current === topologySignature) return;
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
          setTopology((current) => ({
            nodes: current.nodes.map((node) => {
              const linked = nodesById.get(node.id);
              const interfacesById = new Map(
                (linked?.interfaces ?? []).map((item) => [item.topology_port_id, item] as const),
              );
              return {
                ...node,
                name: linked?.engineering_name || node.name,
                engineeringId: linked?.engineering_id,
                engineeringFunctionId: linked?.function_id,
                ports: node.ports.map((port) => {
                  const linkedInterface = interfacesById.get(port.id);
                  return {
                    ...port,
                    name: linkedInterface?.engineering_name || port.name,
                    engineeringId: linkedInterface?.engineering_id,
                  };
                }),
              };
            }),
            edges: current.edges.map((edge) => ({
              ...edge,
              engineeringRelationId: edgesById.get(edge.id)?.engineering_relation_id,
            })),
          }));
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
  }, [automaticModelSync, mode, syncRequest, topology.nodes.length, topologySignature, workflowLoaded]);

  const domain = useMemo(
    () => (catalog?.domains ?? []).find((item) => item.id === domainId),
    [catalog, domainId],
  );
  const technology = useMemo(
    () => (domain?.technologies ?? []).find((item) => item.id === technologyId),
    [domain, technologyId],
  );
  const availableFormats = useMemo(
    () =>
      mergeSimulationFormats(catalog.formats, technology?.native_formats, defaultSimulationFormats),
    [catalog.formats, technology],
  );
  const formatGroups = useMemo(() => groupSimulationFormats(availableFormats), [availableFormats]);
  const parameterGroups = useMemo(() => {
    const groups = new Map<TechnologyParameterField["category"], TechnologyParameterField[]>();
    for (const field of technology?.parameter_schema ?? []) {
      if (busLoadRangeKeys.has(field.key)) continue;
      const category = field.category ?? "physical";
      groups.set(category, [...(groups.get(category) ?? []), field]);
    }
    return Array.from(groups.entries());
  }, [technology]);
  const busLoadField = useMemo(
    () => technology?.parameter_schema?.find((field) => field.key === "target_bus_load_percent"),
    [technology],
  );
  const routingNetworkSuggestions = useRoutingNetworkSuggestions(
    routingEntries,
    topology,
    modelHardware,
  );

  function chooseDomain(value: string) {
    setDomainId(value);
    const nextDomain = (catalog?.domains ?? []).find((item) => item.id === value);
    const nextTechnology = nextDomain?.technologies?.[0];
    if (nextTechnology) {
      setTechnologyId(nextTechnology.id);
      setFormats(defaultSimulationFormats);
    }
  }

  function chooseTechnology(value: string) {
    setTechnologyId(value);
    setFormats(defaultSimulationFormats);
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
    try {
      const next = mergeRoutingSuggestionsIntoTopology(topology, [suggestion], modelHardware);
      const saved = await persistNetworkRelationships(next);
      if (saved) {
        setRoutingSyncMessage(`${suggestion.route.route_code} wurde als physischer Netzwerkpfad übernommen.`);
      }
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Routing-Vorschlag konnte nicht übernommen werden.");
    } finally {
      setApplyingRoute("");
    }
  }

  async function applyAllRoutingSuggestions() {
    if (!routingNetworkSuggestions.length) return;
    setApplyingAllRoutes(true);
    setFormError("");
    try {
      const next = mergeRoutingSuggestionsIntoTopology(topology, routingNetworkSuggestions, modelHardware);
      const saved = await persistNetworkRelationships(next);
      if (saved) {
        setRoutingSyncMessage(
          `${routingNetworkSuggestions.length} Routing-Pfade wurden gemeinsam in das Netzwerk übernommen.`,
        );
      }
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Routing-Vorschläge konnten nicht übernommen werden.");
    } finally {
      setApplyingAllRoutes(false);
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
        if (form.has("warning_threshold") && form.has("overload_threshold")) {
          const warningThreshold = Number(form.get("warning_threshold"));
          const overloadThreshold = Number(form.get("overload_threshold"));
          if (
            !Number.isFinite(warningThreshold)
            || !Number.isFinite(overloadThreshold)
            || warningThreshold < 0
            || overloadThreshold > 100
            || warningThreshold >= overloadThreshold
          ) {
            throw new Error("'Gut bis' muss kleiner als 'Limit ab' sein.");
          }
          dynamicParameters.target_bus_load_percent = warningThreshold;
          dynamicParameters.warning_threshold = warningThreshold;
          dynamicParameters.critical_threshold = Math.round((warningThreshold + overloadThreshold) / 2);
          dynamicParameters.overload_threshold = overloadThreshold;
        }
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
      if (mode === "parameters") notifyWorkflowDraftStatus("parameters", null);
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
      <div className={`workspace-grid ${mode === "network" ? "network-mode" : "parameters-mode"}`}>
      <form
        key={`${mode}:${JSON.stringify(storedParameters)}`}
        className="panel config-panel"
        onChange={() => {
          if (mode === "parameters") notifyWorkflowDraftStatus("parameters", "OUTDATED");
        }}
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
            <div className="panel-heading-actions parameter-heading-actions">
              <label className="mode-switch">
                <input
                  checked={advanced}
                  onChange={(event) => setAdvanced(event.target.checked)}
                  type="checkbox"
                />
                <span>JSON-Modus</span>
              </label>
              <Link className="button secondary" href="/studio/capacity">
                Weiter zu Capacity
              </Link>
              <button
                className="button primary"
                disabled={submitting || (!advanced && formats.length === 0)}
                type="submit"
              >
                {submitting ? "Wird gespeichert …" : "Parameter speichern →"}
              </button>
            </div>
          )}
        </div>

        {mode === "parameters" && formError && <div className="notice error">{formError}</div>}
        {mode === "parameters" && savedMessage && <div className="notice success">{savedMessage}</div>}

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
                          : topology.nodes.length === 0
                            ? "Keine Geräte vorhanden"
                            : "Noch nicht synchronisiert"}
                  </strong>
                </div>
              </div>
              <div className="net-model-sync-actions">
                <Link href="/studio/engineering">Modell öffnen ↗</Link>
                <button
                  className="net-add"
                  disabled={!workflowLoaded || topology.nodes.length === 0 || engineeringSync.status === "syncing"}
                  onClick={() => setSyncRequest((request) => request + 1)}
                  type="button"
                >
                  Synchronisieren
                </button>
              </div>
              {engineeringSync.error && <p>{engineeringSync.error}</p>}
            </div>
            <NetworkEditor
              modelHardware={modelHardware}
              onChange={setTopology}
              onRelationshipsChange={persistNetworkRelationships}
              routingEntries={routingEntries}
              topology={topology}
            />
            {routingSyncMessage && <p className="net-routing-sync">{routingSyncMessage}</p>}
            <section className="net-route-suggestions" aria-label="Vorschläge aus der Routing-Tabelle">
              <div className="net-route-suggestions-heading">
                <div>
                  <span>Routing-Tabelle</span>
                  <strong>Vorgeschlagene physische Verbindungen</strong>
                </div>
                <div className="net-route-suggestions-actions">
                  <Link href="/studio/routing?view=graph">Routing-Graph öffnen ↗</Link>
                  {routingNetworkSuggestions.length > 0 && (
                    <button
                      className="net-add"
                      disabled={Boolean(applyingRoute) || applyingAllRoutes}
                      onClick={() => void applyAllRoutingSuggestions()}
                      type="button"
                    >
                      {applyingAllRoutes ? "Alle werden übernommen …" : "Alle übernehmen"}
                    </button>
                  )}
                </div>
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
                        <span>{suggestion.protocol} · {suggestion.segments.length} fehlende Routing-Beziehung(en)</span>
                      </div>
                      <button
                        className="net-add"
                        disabled={Boolean(applyingRoute) || applyingAllRoutes}
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
            <div className="network-output-row">
              <div>
                <span>Topologie</span>
                <strong>{topology.nodes.length} Geräte · {topology.edges.length} Verbindungen</strong>
              </div>
              <div className="format-inline">
                {defaultSimulationFormats.map((format) => (
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
            <nav aria-label="Parameter-Abschnitte" className="parameter-section-nav">
              {parameterNavItems.map(([id, label]) => (
                <a href={`#${id}`} key={id}>{label}</a>
              ))}
            </nav>

            <div className="section-title" id="parameter-technology">
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

            <div className="section-title" id="parameter-values">
              <span>02</span>
              Technologie- und Timing-Parameter
            </div>
            {busLoadField && (
              <BusLoadParameterControl
                field={busLoadField}
                key={technology.id}
                parameters={storedParameters}
                technology={technology}
              />
            )}
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

            <div className="section-title" id="parameter-formats">
              <span>03</span>
              Ausgabeformate
            </div>
            <div className="format-groups">
              {formatGroups.map((group) => (
                <section className="format-group" key={group.id}>
                  <h3>{group.label}</h3>
                  <div className="format-grid">
                    {group.formats.map((format) => (
                      <label
                        className={`format-option ${formats.includes(format.id) ? "selected" : ""}`}
                        key={format.id}
                      >
                        <input
                          checked={formats.includes(format.id)}
                          onChange={() => toggleFormat(format.id)}
                          type="checkbox"
                        />
                        <span>{format.id}</span>
                        <small>{format.description}</small>
                      </label>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </>
        )}

        {mode === "network" && formError && <div className="notice error">{formError}</div>}
        {mode === "network" && savedMessage && <div className="notice success">{savedMessage}</div>}

        {mode === "network" && (
          <div className="form-actions">
            <Link className="button secondary" href="/studio?mode=parameters">
              Weiter zu Parametern
            </Link>
            <button
              className="button primary"
              disabled={submitting || formats.length === 0}
              type="submit"
            >
              {submitting ? "Wird gespeichert …" : "Netzwerk speichern →"}
            </button>
          </div>
        )}
      </form>

      {mode === "network" && (
        <aside className="side-column">
          <div className="panel overview-panel">
            <p className="eyebrow">Run overview</p>
            <h2>ECU TOPOLOGY</h2>
            <dl className="overview-list">
              <div><dt>Geräte</dt><dd>{topology.nodes.length}</dd></div>
              <div><dt>Verbindungen</dt><dd>{topology.edges.length}</dd></div>
              <div><dt>Busse</dt><dd>{new Set(topology.edges.map((edge) => edge.bus)).size}</dd></div>
              <div><dt>Formate</dt><dd>{formats.length}</dd></div>
            </dl>
          </div>
        </aside>
      )}
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

function BusLoadParameterControl({
  field,
  parameters,
  technology,
}: {
  field: TechnologyParameterField;
  parameters: Record<string, unknown>;
  technology: Technology;
}) {
  const minimum = field.min ?? 0;
  const maximum = field.max ?? 100;
  const schemaDefaults = Object.fromEntries(
    (technology.parameter_schema ?? []).map((item) => [item.key, item.default]),
  );
  const initialGood = Number(
    parameters.warning_threshold
      ?? parameters.target_bus_load_percent
      ?? schemaDefaults.warning_threshold
      ?? field.default
      ?? 60,
  );
  const initialLimit = Number(
    parameters.overload_threshold
      ?? schemaDefaults.overload_threshold
      ?? 90,
  );
  const normalizedGood = Number.isFinite(initialGood)
    ? Math.min(maximum, Math.max(minimum, initialGood))
    : 60;
  const normalizedLimit = Number.isFinite(initialLimit)
    ? Math.min(maximum, Math.max(minimum, initialLimit))
    : 90;
  const [goodLimit, setGoodLimit] = useState(normalizedGood);
  const [limitStart, setLimitStart] = useState(normalizedLimit);
  const span = Math.max(1, maximum - minimum);
  const goodEnd = ((goodLimit - minimum) / span) * 100;
  const limitBegin = ((limitStart - minimum) / span) * 100;
  const boundariesValid = goodLimit < limitStart;
  const trackBackground = boundariesValid
    ? `linear-gradient(90deg, var(--accent) 0 ${goodEnd}%, var(--warning) ${goodEnd}% ${limitBegin}%, var(--danger) ${limitBegin}% 100%)`
    : "var(--danger)";

  return (
    <div className="bus-load-parameter" title={field.description}>
      <div className="bus-load-parameter-head">
        <strong>Buslast-Grenzen</strong>
        <span className={boundariesValid ? undefined : "invalid"}>{goodLimit.toFixed(0)}–{limitStart.toFixed(0)} %</span>
      </div>
      <div className="bus-load-slider-row bus-load-slider-good">
        <label htmlFor="bus_load_good_limit">Gut bis</label>
        <input
          aria-label="Obergrenze für gute Buslast"
          aria-valuetext={`Gut bis ${goodLimit.toFixed(0)} Prozent`}
          className="bus-load-range-good"
          id="bus_load_good_limit"
          max={maximum}
          min={minimum}
          name="warning_threshold"
          onInput={(event) => {
            setGoodLimit(Number(event.currentTarget.value));
            notifyWorkflowDraftStatus("parameters", "OUTDATED");
          }}
          step="1"
          style={{ "--bus-slider-position": `${goodEnd}%` } as React.CSSProperties}
          type="range"
          value={goodLimit}
        />
        <output htmlFor="bus_load_good_limit">{goodLimit.toFixed(0)} %</output>
      </div>
      <div className="bus-load-slider-row bus-load-slider-limit">
        <label htmlFor="bus_load_limit_start">Limit ab</label>
        <input
          aria-label="Beginn des Buslast-Limitbereichs"
          aria-valuetext={`Limit ab ${limitStart.toFixed(0)} Prozent`}
          className="bus-load-range-limit"
          id="bus_load_limit_start"
          max={maximum}
          min={minimum}
          name="overload_threshold"
          onInput={(event) => {
            setLimitStart(Number(event.currentTarget.value));
            notifyWorkflowDraftStatus("parameters", "OUTDATED");
          }}
          step="1"
          style={{ "--bus-slider-position": `${limitBegin}%` } as React.CSSProperties}
          type="range"
          value={limitStart}
        />
        <output htmlFor="bus_load_limit_start">{limitStart.toFixed(0)} %</output>
      </div>
      <span aria-hidden="true" className="bus-load-range-track" style={{ background: trackBackground }} />
      {boundariesValid ? (
        <div aria-hidden="true" className="bus-load-zones" style={{ gridTemplateColumns: `${Math.max(goodEnd, 1)}fr ${Math.max(limitBegin - goodEnd, 1)}fr ${Math.max(100 - limitBegin, 1)}fr` }}>
          <span>Gut · {minimum.toFixed(0)}–{goodLimit.toFixed(0)} %</span>
          <span>Mittel · {(goodLimit + 1).toFixed(0)}–{(limitStart - 1).toFixed(0)} %</span>
          <span>Limit · {limitStart.toFixed(0)}–{maximum.toFixed(0)} %</span>
        </div>
      ) : (
        <p className="bus-load-boundary-error" role="alert">"Gut bis" muss kleiner als "Limit ab" sein.</p>
      )}
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
      <div className="technology-symbol">◈</div>
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
