"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCatalog } from "@/lib/api";
import { listAllEngineeringObjects, syncEngineeringTopology } from "@/lib/engineering-api";
import { localCatalog } from "@/lib/local-simulator";
import { listRoutes } from "@/lib/routing-api";
import type { Catalog, EngFunction, HardwareNode, RoutingEntry, Technology, TechnologyParameterField } from "@/lib/types";
import { NetworkEditor } from "./network-editor";
import {
  busProfiles,
  collapsePhysicalEdges,
  engineeringHardwareKind,
  normalizePhysicalTopology,
  type BusType,
  type NetworkTopology,
  type TopologyEdge,
  type TopologyNode,
  type TopologyPort,
} from "@/lib/topology";
import { getWorkflow, saveWorkflowParameters, saveWorkflowTopology } from "@/lib/workflow-api";
import { defaultSimulationFormats } from "@/lib/simulation-formats";
import {
  notifyWorkflowChanged,
  notifyWorkflowDraftStatus,
  WORKFLOW_CHANGED_EVENT,
} from "./workflow-header";

const parameterNavItems = [
  ["parameter-technology", "Technologie"],
  ["parameter-values", "Parameter"],
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
const ROUTING_SUGGESTION_CHECK_DELAY_MS = 80;

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

function routeCanSuggestNetworkChange(route: RoutingEntry) {
  return route.origin !== "NETWORK_EDITOR" &&
    !inactiveRouteStatuses.has(route.status.toUpperCase()) &&
    route.approval_state.toUpperCase() === "APPROVED" &&
    route.validation.valid === true;
}

function routingSegmentKey(
  sourceId: string,
  targetId: string,
  bus: BusType,
  routeId: string,
) {
  const [left, right] = [sourceId, targetId].sort();
  return `${routeId}\u0000${bus}\u0000${left}\u0000${right}`;
}

function buildLinkedRoutingSegmentIndex(topology: NetworkTopology) {
  const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
  const linkedSegments = new Set<string>();
  for (const edge of topology.edges) {
    const sourceEngineeringId = nodesById.get(edge.source)?.engineeringId;
    const targetEngineeringId = nodesById.get(edge.target)?.engineeringId;
    if (!sourceEngineeringId || !targetEngineeringId) continue;
    const routeIds = new Set([
      ...(edge.routingEntryIds ?? []),
      ...(edge.routingEntryId ? [edge.routingEntryId] : []),
      ...Object.keys(edge.routingMetadata ?? {}),
    ]);
    for (const routeId of routeIds) {
      linkedSegments.add(routingSegmentKey(sourceEngineeringId, targetEngineeringId, edge.bus, routeId));
    }
  }
  return linkedSegments;
}

function routingRouteSignature(route: RoutingEntry) {
  return JSON.stringify({
    id: route.id,
    routeCode: route.route_code,
    revision: route.revision,
    modifiedAt: route.modified_at,
    status: route.status,
    approval: route.approval_state,
    valid: route.validation.valid,
    source: route.source,
    destinations: route.destinations,
    hops: route.route.hops,
    gateways: route.route.gateways,
  });
}

function routingHardwareSignature(hardware: HardwareNode[]) {
  return JSON.stringify(hardware.map((node) => ({ id: node.id, name: node.name })));
}

function routeLinkedSegmentSignature(route: RoutingEntry, linkedSegments: Set<string>) {
  const keys = new Set<string>();
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
      const key = routingSegmentKey(sourceId, targetId, bus, route.id);
      keys.add(`${key}:${linkedSegments.has(key) ? "1" : "0"}`);
    }
  }
  return [...keys].sort().join("\u0001");
}

function topologyRoutingLinkRevision(topology: NetworkTopology) {
  return JSON.stringify({
    nodes: topology.nodes.map((node) => ({ id: node.id, engineeringId: node.engineeringId, name: node.name })),
    edges: topology.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      bus: edge.bus,
      routingEntryId: edge.routingEntryId,
      routingEntryIds: edge.routingEntryIds,
      routingMetadataIds: Object.keys(edge.routingMetadata ?? {}).sort(),
    })),
  });
}

function buildRoutingNetworkSuggestion(
  route: RoutingEntry,
  names: Map<string, string>,
  linkedSegments: Set<string>,
): RoutingNetworkSuggestion[] {
  if (!routeCanSuggestNetworkChange(route)) return [];
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
      if (linkedSegments.has(routingSegmentKey(sourceId, targetId, bus, route.id))) continue;
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
}

type RoutingSuggestionCacheEntry = {
  signature: string;
  items: RoutingNetworkSuggestion[];
};

function useRoutingNetworkSuggestions(
  routes: RoutingEntry[],
  topology: NetworkTopology,
  hardware: HardwareNode[],
  linkRevision: string,
) {
  const [suggestions, setSuggestions] = useState<RoutingNetworkSuggestion[]>([]);
  const [checking, setChecking] = useState(false);
  const cache = useRef<Map<string, RoutingSuggestionCacheEntry>>(new Map());
  const routeRevision = useMemo(
    () => routes.map((route) => routingRouteSignature(route)).join("\u0002"),
    [routes],
  );
  const hardwareRevision = useMemo(() => routingHardwareSignature(hardware), [hardware]);

  useEffect(() => {
    let cancelled = false;
    let batchTimeout = 0;
    setChecking(true);
    const timeout = window.setTimeout(() => {
      const names = new Map([
        ...hardware.map((node) => [node.id, node.name] as const),
        ...topology.nodes
          .filter((node) => node.engineeringId)
          .map((node) => [node.engineeringId as string, node.name] as const),
      ]);
      const linkedSegments = buildLinkedRoutingSegmentIndex(topology);
      const nextCache = new Map<string, RoutingSuggestionCacheEntry>();
      const nextSuggestions: RoutingNetworkSuggestion[] = [];
      const candidateRoutes = routes.filter(routeCanSuggestNetworkChange);
      let index = 0;

      const processBatch = () => {
        const batchStarted = performance.now();
        let processed = 0;
        while (
          index < candidateRoutes.length &&
          processed < 16 &&
          performance.now() - batchStarted < 8
        ) {
          const route = candidateRoutes[index];
          index += 1;
          processed += 1;
          if (!route) continue;
        if (!routeCanSuggestNetworkChange(route)) continue;
        const signature = [
          routingRouteSignature(route),
          routeLinkedSegmentSignature(route, linkedSegments),
          hardwareRevision,
        ].join("\u0003");
        const cached = cache.current.get(route.id);
        const items = cached?.signature === signature
          ? cached.items
          : buildRoutingNetworkSuggestion(route, names, linkedSegments);
        nextCache.set(route.id, { signature, items });
        nextSuggestions.push(...items);
      }

        if (cancelled) return;
        if (index < candidateRoutes.length) {
          batchTimeout = window.setTimeout(processBatch, 0);
          return;
        }
        cache.current = nextCache;
        setSuggestions(nextSuggestions);
        setChecking(false);
      };

      processBatch();
    }, ROUTING_SUGGESTION_CHECK_DELAY_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
      if (batchTimeout) window.clearTimeout(batchTimeout);
    };
  }, [hardwareRevision, linkRevision, routeRevision]);

  return { checking, suggestions };
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

function topologyHasChanged(current: NetworkTopology, next: NetworkTopology) {
  return engineeringTopologySignature(current) !== engineeringTopologySignature(next);
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
  const [advanced, setAdvanced] = useState(false);
  const [advancedConfig, setAdvancedConfig] = useState(
    '{\n  "name": "custom_simulation",\n  "duration_s": 1,\n  "formats": ["universal-jsonl"]\n}',
  );
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [storedParameters, setStoredParameters] = useState<Record<string, unknown>>({});
  const [networkView, setNetworkView] = useState<"editor" | "hardware">("editor");
  const mode = initialMode;
  const [topology, setTopology] = useState<NetworkTopology>(() => ({ nodes: [], edges: [] }));
  const [workflowLoaded, setWorkflowLoaded] = useState(false);
  const [modelHardware, setModelHardware] = useState<HardwareNode[]>([]);
  const [modelFunctions, setModelFunctions] = useState<EngFunction[]>([]);
  const [routingEntries, setRoutingEntries] = useState<RoutingEntry[]>([]);
  const [routingLoadError, setRoutingLoadError] = useState("");
  const [applyingRoute, setApplyingRoute] = useState("");
  const [applyingAllRoutes, setApplyingAllRoutes] = useState(false);
  const [syncRequest, setSyncRequest] = useState(0);
  const [routeRefreshRequest, setRouteRefreshRequest] = useState(0);
  const [modelRefreshPending, setModelRefreshPending] = useState(false);
  const [engineeringSync, setEngineeringSync] = useState<{
    status: "idle" | "syncing" | "synced" | "warning" | "error";
    linked: number;
    error: string;
  }>({ status: "idle", linked: 0, error: "" });
  const [routingSyncMessage, setRoutingSyncMessage] = useState("");
  const [routingLinkRevision, setRoutingLinkRevision] = useState("");
  const localWorkflowChangeRef = useRef(false);
  const topologyRef = useRef(topology);

  useEffect(() => {
    topologyRef.current = topology;
  }, [topology]);

  const clearLocalWorkflowChangeSoon = useCallback(() => {
    window.setTimeout(() => {
      localWorkflowChangeRef.current = false;
    }, 0);
  }, []);

  const requestNetworkRefresh = useCallback(() => {
    setRouteRefreshRequest((request) => request + 1);
    setSyncRequest((request) => request + 1);
  }, []);

  const persistNetworkRelationships = useCallback(async (next: NetworkTopology) => {
    setEngineeringSync((current) => ({ ...current, status: "syncing", error: "" }));
    setRoutingSyncMessage("Routing-Vorschläge werden abgeglichen …");
    try {
      const state = await saveWorkflowTopology(normalizePhysicalTopology(next));
      if (Array.isArray(state.topology.nodes) && Array.isArray(state.topology.edges)) {
        const savedTopology = normalizePhysicalTopology({ nodes: state.topology.nodes, edges: state.topology.edges });
        setRoutingLinkRevision(topologyRoutingLinkRevision(savedTopology));
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
      localWorkflowChangeRef.current = true;
      setModelRefreshPending(false);
      notifyWorkflowChanged();
      return true;
    } catch (error) {
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
          const nextTopology = normalizePhysicalTopology({ nodes: storedTopology.nodes, edges: storedTopology.edges });
          setRoutingLinkRevision(topologyRoutingLinkRevision(nextTopology));
          setTopology(nextTopology);
        } else {
          setRoutingLinkRevision("");
          setTopology({ nodes: [], edges: [] });
        }
        if (typeof state.parameters.industry === "string") setDomainId(state.parameters.industry);
        if (typeof state.parameters.technology === "string") setTechnologyId(state.parameters.technology);
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
    const refreshRoutes = (event?: Event) => {
      if (event && workflowLoaded) {
        if (localWorkflowChangeRef.current) {
          clearLocalWorkflowChangeSoon();
        } else {
          setModelRefreshPending(true);
          setEngineeringSync((current) => ({
            ...current,
            status: current.status === "syncing" ? current.status : "warning",
            error: "Das Engineering-Modell wurde außerhalb des Netzwerk-Editors geändert. Bitte aktualisiere bewusst.",
          }));
          return;
        }
      }
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
  }, [clearLocalWorkflowChangeSoon, mode, routeRefreshRequest, workflowLoaded]);

  useEffect(() => {
    if (mode !== "network") return;
    let active = true;
    const loadHardware = (event?: Event) => {
      if (event && workflowLoaded && !localWorkflowChangeRef.current) return;
      if (event && localWorkflowChangeRef.current) clearLocalWorkflowChangeSoon();
      void Promise.all([
        listAllEngineeringObjects("hardware-nodes"),
        listAllEngineeringObjects("functions"),
      ])
        .then(([hardwareItems, functionItems]) => {
          if (!active) return;
          setModelHardware(hardwareItems.filter((item): item is HardwareNode => "device_type" in item));
          setModelFunctions(functionItems.filter((item): item is EngFunction => item.object_type === "Function"));
        })
        .catch(() => {
          if (!active) return;
          setModelHardware([]);
          setModelFunctions([]);
        });
    };
    loadHardware();
    window.addEventListener(WORKFLOW_CHANGED_EVENT, loadHardware);
    return () => {
      active = false;
      window.removeEventListener(WORKFLOW_CHANGED_EVENT, loadHardware);
    };
  }, [clearLocalWorkflowChangeSoon, mode, routeRefreshRequest, workflowLoaded]);

  useEffect(() => {
    if (mode !== "network" || !workflowLoaded) return;
    const topologyForSync = topologyRef.current;
    if (topologyForSync.nodes.length === 0) {
      setEngineeringSync({ status: "idle", linked: 0, error: "" });
      setModelHardware([]);
      return;
    }
    if (syncRequest === 0) return;
    let cancelled = false;
    const timeout = window.setTimeout(() => {
      setEngineeringSync((current) => ({ ...current, status: "syncing", error: "" }));
      Promise.all([
        listAllEngineeringObjects("hardware-nodes"),
        listAllEngineeringObjects("functions"),
        syncEngineeringTopology(topologyForSync),
      ])
        .then(([items, functionItems, result]) => {
          if (cancelled) return;
          setModelHardware(items.filter((item): item is HardwareNode => "device_type" in item));
          setModelFunctions(functionItems.filter((item): item is EngFunction => item.object_type === "Function"));
          const nodesById = new Map(result.nodes.map((node) => [node.topology_node_id, node]));
          const edgesById = new Map(result.edges.map((edge) => [edge.topology_edge_id, edge]));
          const currentTopology = topologyRef.current;
          const nextTopology = {
            nodes: currentTopology.nodes.map((node) => {
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
            edges: currentTopology.edges.map((edge) => ({
              ...edge,
              engineeringRelationId: edgesById.get(edge.id)?.engineering_relation_id,
            })),
          };
          setRoutingLinkRevision(topologyRoutingLinkRevision(nextTopology));
          setTopology(nextTopology);
          setEngineeringSync({
            status: "synced",
            linked: result.counts.hardware_nodes,
            error: "",
          });
          setModelRefreshPending(false);
          setSyncRequest(0);
        })
        .catch((error) => {
          if (!cancelled) {
            setEngineeringSync({
              status: "error",
              linked: 0,
              error: error instanceof Error ? error.message : "Modellabgleich fehlgeschlagen.",
            });
            setSyncRequest(0);
          }
        });
    }, 500);
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [mode, syncRequest, topology.nodes.length, workflowLoaded]);

  const domain = useMemo(
    () => (catalog?.domains ?? []).find((item) => item.id === domainId),
    [catalog, domainId],
  );
  const technology = useMemo(
    () => (domain?.technologies ?? []).find((item) => item.id === technologyId),
    [domain, technologyId],
  );
  const formats = useMemo(
    () => Array.isArray(storedParameters.formats)
      ? storedParameters.formats.map(String)
      : defaultSimulationFormats,
    [storedParameters.formats],
  );
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
  const {
    checking: routingSuggestionsChecking,
    suggestions: routingNetworkSuggestions,
  } = useRoutingNetworkSuggestions(
    routingEntries,
    topology,
    modelHardware,
    routingLinkRevision,
  );

  function chooseDomain(value: string) {
    setDomainId(value);
    const nextDomain = (catalog?.domains ?? []).find((item) => item.id === value);
    const nextTechnology = nextDomain?.technologies?.[0];
    if (nextTechnology) {
      setTechnologyId(nextTechnology.id);
    }
  }

  function chooseTechnology(value: string) {
    setTechnologyId(value);
  }

  async function applyRoutingSuggestion(suggestion: RoutingNetworkSuggestion) {
    setApplyingRoute(suggestion.route.id);
    setFormError("");
    try {
      const next = mergeRoutingSuggestionsIntoTopology(topology, [suggestion], modelHardware);
      if (!topologyHasChanged(topology, next)) {
        setRoutingSyncMessage("Keine geänderten Routing-Parameter vorhanden. Es muss nichts übernommen werden.");
        return;
      }
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
      if (!topologyHasChanged(topology, next)) {
        setRoutingSyncMessage("Keine geänderten Routing-Parameter vorhanden. Es muss nichts übernommen werden.");
        return;
      }
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
      if (mode === "network") localWorkflowChangeRef.current = true;
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
          {mode === "network" && (
            <div className="network-view-tabs" role="tablist" aria-label="Netzwerk-Darstellung">
              <button
                aria-selected={networkView === "editor"}
                className={networkView === "editor" ? "active" : ""}
                onClick={() => setNetworkView("editor")}
                role="tab"
                type="button"
              >
                Netzwerk-Editor
              </button>
              <button
                aria-selected={networkView === "hardware"}
                className={networkView === "hardware" ? "active" : ""}
                onClick={() => setNetworkView("hardware")}
                role="tab"
                type="button"
              >
                Hardware-Topologie
              </button>
            </div>
          )}
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
            <div className={`net-model-sync ${modelRefreshPending ? "warning" : engineeringSync.status}`}>
              <div className="net-model-sync-status">
                <span aria-hidden="true" className="net-model-sync-dot" />
                <div>
                  <span>Engineering-Modell</span>
                  <strong>
                    {modelRefreshPending
                      ? "Modelländerung wartet auf Aktualisierung"
                      : engineeringSync.status === "syncing"
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
                  className={`net-add net-sync-button ${modelRefreshPending ? "warning" : ""}`}
                  disabled={!workflowLoaded || topology.nodes.length === 0 || engineeringSync.status === "syncing"}
                  onClick={requestNetworkRefresh}
                  type="button"
                >
                  {modelRefreshPending && <span aria-hidden="true" className="net-sync-warning">⚠</span>}
                  {modelRefreshPending ? "Aktualisieren" : "Synchronisieren"}
                </button>
              </div>
              {engineeringSync.error && <p>{engineeringSync.error}</p>}
            </div>
            {networkView === "editor" ? (
              <NetworkEditor
                modelHardware={modelHardware}
                onChange={setTopology}
                onRelationshipsChange={persistNetworkRelationships}
                routingEntries={routingEntries}
                topology={topology}
              />
            ) : (
              <HardwareTopologyView functions={modelFunctions} topology={topology} />
            )}
            {routingSyncMessage && <p className="net-routing-sync">{routingSyncMessage}</p>}
            <section className="net-route-suggestions" aria-label="Geänderte Routing-Parameter">
              <div className="net-route-suggestions-heading">
                <div>
                  <span>Routing-Tabelle</span>
                  <strong>
                    {routingSuggestionsChecking
                      ? "Änderungen werden geprüft …"
                      : routingNetworkSuggestions.length > 0
                      ? "Geänderte Parameter bestätigen"
                      : "Keine Änderungen zu übernehmen"}
                  </strong>
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
              ) : routingSuggestionsChecking ? (
                <p className="net-route-suggestions-complete">Nur geänderte Routing-Parameter werden geprüft.</p>
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
                        <span>{suggestion.protocol} · {suggestion.segments.length} zu bestätigende Änderung(en)</span>
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
                <p className="net-route-suggestions-complete">Keine geänderten Routing-Parameter. Es muss nichts übernommen werden.</p>
              )}
            </section>
            <div className="network-output-row">
              <div>
                <span>Topologie</span>
                <strong>{topology.nodes.length} Geräte · {topology.edges.length} Verbindungen</strong>
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

type HardwareGraphEdge = {
  id: string;
  source: string;
  target: string;
  bus: BusType;
  count: number;
};

type HardwareDiagramMode = "hardware" | "functions" | "combined";
type HardwareDiagramNodeKind = TopologyNode["kind"] | "root" | "group" | "function" | "unmapped";
type HardwareDiagramLinkKind = "hierarchy" | "mapping";

type HardwareSystemCluster = {
  id: string;
  name: string;
  hardware: TopologyNode[];
  functions: EngFunction[];
};

type HardwareTreeNode = {
  id: string;
  name: string;
  kind: HardwareDiagramNodeKind;
  children: HardwareTreeNode[];
  bus?: BusType;
  connectionCount: number;
  functionRef?: EngFunction;
  mappingTargetId?: string | null;
};

type HardwareRadialNode = HardwareTreeNode & {
  angle: number;
  radius: number;
  depth: number;
  collapsed?: boolean;
  parent?: HardwareRadialNode;
};

type HardwareRadialLink = {
  id: string;
  source: HardwareRadialNode;
  target: HardwareRadialNode;
  bus: BusType;
  kind: HardwareDiagramLinkKind;
};

const HARDWARE_RADIAL_ROOT_GAP = 10;
const HARDWARE_RADIAL_CLUSTER_GAP = 5;
const HARDWARE_RADIAL_GROUP_GAP = 2.5;
const COMBINED_RADIAL_ROOT_GAP = 34;
const COMBINED_RADIAL_CLUSTER_GAP = 16;
const COMBINED_RADIAL_GROUP_GAP = 7;

function HardwareTopologyView({ functions, topology }: { functions: EngFunction[]; topology: NetworkTopology }) {
  const [zoom, setZoom] = useState(1.1);
  const [diagramMode, setDiagramMode] = useState<HardwareDiagramMode>("hardware");
  const [showLabels, setShowLabels] = useState(true);
  const [collapsedNodeIds, setCollapsedNodeIds] = useState<Set<string>>(() => new Set());
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [selectedLinkId, setSelectedLinkId] = useState("");
  const [panning, setPanning] = useState(false);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const panRef = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const panMovedRef = useRef(false);
  const graph = useMemo(() => buildHardwareRadialTree(topology, functions, diagramMode, collapsedNodeIds), [collapsedNodeIds, diagramMode, functions, topology]);
  const focus = useMemo(() => hardwareFocusSets(graph.nodes, graph.links, selectedNodeId, selectedLinkId), [graph.links, graph.nodes, selectedLinkId, selectedNodeId]);
  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId);
  const selectedLink = graph.links.find((link) => link.id === selectedLinkId);
  const selectedLabel = selectedLink
    ? `${selectedLink.source.name} -> ${selectedLink.target.name} · ${busProfiles[selectedLink.bus].label}`
    : selectedNode
      ? `${selectedNode.name} · ${hardwareNodeRole(selectedNode.kind)} · ${selectedNode.connectionCount} Verbindung(en)`
      : "";
  const width = diagramMode === "combined" ? 3000 : 2200;
  const height = diagramMode === "combined" ? 2600 : 1900;
  const cx = width * 0.5;
  const cy = height * 0.53;
  const scaledWidth = Math.round(width * zoom);
  const scaledHeight = Math.round(height * zoom);

  const focusViewport = useCallback((point: { x: number; y: number }, nextZoom = Math.max(zoom, 1.25)) => {
    const stage = stageRef.current;
    if (!stage) return;
    setZoom(nextZoom);
    window.requestAnimationFrame(() => {
      stage.scrollTo({
        left: Math.max(0, point.x * nextZoom - stage.clientWidth / 2),
        top: Math.max(0, point.y * nextZoom - stage.clientHeight / 2),
        behavior: "smooth",
      });
    });
  }, [zoom]);

  const toggleCollapsed = useCallback((node: HardwareRadialNode) => {
    if (panMovedRef.current) return;
    if (node.children.length === 0) {
      setSelectedNodeId(node.id);
      setSelectedLinkId("");
      return;
    }
    setCollapsedNodeIds((current) => {
      const next = new Set(current);
      if (next.has(node.id)) next.delete(node.id);
      else next.add(node.id);
      return next;
    });
    setSelectedNodeId(node.id);
    setSelectedLinkId("");
  }, []);

  useEffect(() => {
    if (!selectedNode && !selectedLink) return;
    if (selectedLink) {
      const source = radialPoint(selectedLink.source.angle, selectedLink.source.radius);
      const target = radialPoint(selectedLink.target.angle, selectedLink.target.radius);
      focusViewport({ x: cx + (source.x + target.x) / 2, y: cy + (source.y + target.y) / 2 });
      return;
    }
    if (selectedNode) {
      const point = radialPoint(selectedNode.angle, selectedNode.radius);
      focusViewport({ x: cx + point.x, y: cy + point.y });
    }
  }, [cx, cy, focusViewport, selectedLink, selectedNode]);

  const beginPan = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    panRef.current = {
      x: event.clientX,
      y: event.clientY,
      left: event.currentTarget.scrollLeft,
      top: event.currentTarget.scrollTop,
    };
    panMovedRef.current = false;
    event.currentTarget.setPointerCapture(event.pointerId);
  }, []);

  const movePan = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const start = panRef.current;
    if (!start) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      panMovedRef.current = true;
      setPanning(true);
    }
    event.currentTarget.scrollLeft = start.left - dx;
    event.currentTarget.scrollTop = start.top - dy;
  }, []);

  const endPan = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (panRef.current) {
      try {
        event.currentTarget.releasePointerCapture(event.pointerId);
      } catch {
        // Pointer capture may already be released when leaving the canvas.
      }
    }
    panRef.current = null;
    setPanning(false);
    window.setTimeout(() => {
      panMovedRef.current = false;
    }, 0);
  }, []);

  if (topology.nodes.length === 0 && functions.length === 0) {
    return <div className="hardware-topology-empty">Keine Hardware-Topologie vorhanden.</div>;
  }
  return (
    <section className="hardware-topology-view" aria-label="Hardware-Topologie">
      <div className="hardware-topology-header">
        <div>
          <span>Hardware-Topologie</span>
          <strong>{hardwareDiagramModeTitle(diagramMode)}</strong>
        </div>
        <div className="hardware-topology-toolbar" role="toolbar" aria-label="Hardware-Topologie Werkzeuge">
          <button className={diagramMode === "hardware" ? "active" : ""} onClick={() => { setDiagramMode("hardware"); setCollapsedNodeIds(new Set()); setSelectedNodeId(""); setSelectedLinkId(""); }} type="button">
            Hardware
          </button>
          <button className={diagramMode === "functions" ? "active" : ""} onClick={() => { setDiagramMode("functions"); setCollapsedNodeIds(new Set()); setSelectedNodeId(""); setSelectedLinkId(""); }} type="button">
            Functions
          </button>
          <button className={diagramMode === "combined" ? "active" : ""} onClick={() => { setDiagramMode("combined"); setCollapsedNodeIds(new Set()); setSelectedNodeId(""); setSelectedLinkId(""); }} type="button">
            Combined
          </button>
          <button aria-label="Verkleinern" disabled={zoom <= 0.7} onClick={() => setZoom((value) => Math.max(0.7, Number((value - 0.1).toFixed(1))))} type="button">−</button>
          <strong>{Math.round(zoom * 100)} %</strong>
          <button aria-label="Vergrößern" disabled={zoom >= 2} onClick={() => setZoom((value) => Math.min(2, Number((value + 0.1).toFixed(1))))} type="button">+</button>
          <button onClick={() => setZoom(1.1)} type="button">Fit</button>
          <button disabled={!selectedNodeId && !selectedLinkId} onClick={() => { setSelectedNodeId(""); setSelectedLinkId(""); }} type="button">Alle</button>
          <button className={showLabels ? "active" : ""} onClick={() => setShowLabels((value) => !value)} type="button">
            Labels
          </button>
        </div>
      </div>
      <div className="hardware-topology-canvas">
        <div
          className={`hardware-topology-stage ${panning ? "panning" : ""}`}
          onPointerCancel={endPan}
          onPointerDown={beginPan}
          onPointerLeave={endPan}
          onPointerMove={movePan}
          onPointerUp={endPan}
          ref={stageRef}
        >
          <svg
            className="hardware-topology-svg"
            role="img"
            style={{ height: scaledHeight, width: scaledWidth }}
            viewBox={`0 0 ${width} ${height}`}
          >
            <title>Radiale Hardware-Topologie</title>
            <g transform={`translate(${cx} ${cy})`}>
              <g className="hardware-topology-edges">
                {graph.links.map((link) => {
                  const active = focus.links.size === 0 || focus.links.has(link.id);
                  const selected = selectedLinkId === link.id;
                  return (
                    <path
                      className={`${link.kind} ${hardwareLinkTone(link)} ${active ? "active" : "dimmed"} ${selected ? "selected" : ""}`}
                      d={radialLinkPath(link.source, link.target)}
                      key={link.id}
                      onClick={() => { if (panMovedRef.current) return; setSelectedLinkId(link.id); setSelectedNodeId(""); }}
                      stroke={hardwareLinkStroke(link)}
                    >
                      <title>{`${link.source.name} -> ${link.target.name}`}</title>
                    </path>
                  );
                })}
              </g>
              <g className="hardware-topology-nodes">
                {graph.nodes.map((node) => {
                  const point = radialPoint(node.angle, node.radius);
                  const degrees = node.angle * 180 / Math.PI - 90;
                  const flip = node.angle >= Math.PI;
                  const active = focus.nodes.size === 0 || focus.nodes.has(node.id);
                  const selected = selectedNodeId === node.id;
                  const showNodeLabel = showLabels && hardwareShowNodeLabel(node, diagramMode, selected, focus.nodes.has(node.id), focus.nodes.size > 0);
                  return (
                    <g
                      className={`hardware-node hardware-node-${node.kind} ${active ? "active" : "dimmed"} ${selected ? "selected" : ""}`}
                      key={node.id}
                    onClick={() => toggleCollapsed(node)}
                    transform={`translate(${point.x} ${point.y})`}
                  >
                      <circle r={hardwareNodeRadius(node)} />
                      <text aria-hidden="true" className="hardware-node-symbol" dy="3">
                        {hardwareNodeSymbol(node.kind)}
                      </text>
                      <title>{`${node.name} · ${hardwareNodeRole(node.kind)} · ${node.connectionCount} Verbindung(en)`}</title>
                      {showNodeLabel && (
                      <text
                        className="hardware-node-label"
                          dy="0.31em"
                          textAnchor={node.children.length ? "end" : flip ? "end" : "start"}
                          transform={`rotate(${degrees}) translate(${hardwareNodeRadius(node) + 7},0) rotate(${flip ? 180 : 0})`}
                          x={node.children.length ? -12 : 6}
                      >
                        {node.children.length ? `${node.collapsed ? "[+]" : "[-]"} ${shortHardwareLabel(node.name)}` : shortHardwareLabel(node.name)}
                      </text>
                      )}
                    </g>
                  );
                })}
              </g>
            </g>
          </svg>
        </div>
        {selectedLabel && <div className="hardware-topology-selection">{selectedLabel}</div>}
        <div className="hardware-topology-legend" aria-label="Bus-Legende">
          {(Object.keys(busProfiles) as BusType[]).map((bus) => (
            <span key={bus}><i style={{ background: busProfiles[bus].color }} />{busProfiles[bus].label}</span>
          ))}
        </div>
      </div>
    </section>
  );
}

function buildHardwareRadialTree(
  topology: NetworkTopology,
  functions: EngFunction[],
  mode: HardwareDiagramMode,
  collapsedNodeIds: Set<string>,
) {
  const root = buildHardwareDiagramTree(topology, functions, mode);
  const maxDepth = Math.max(1, hardwareTreeDepth(root));
  const leafSlots = Math.max(1, hardwareVisibleLeafCount(root, collapsedNodeIds, mode));
  const radiusStep = (mode === "combined" ? 1120 : 820) / maxDepth;
  let cursor = 0;
  const nodes: HardwareRadialNode[] = [];
  const links: HardwareRadialLink[] = [];

  function place(node: HardwareTreeNode, depth: number, parent?: HardwareRadialNode): HardwareRadialNode {
    const collapsed = collapsedNodeIds.has(node.id);
    const visibleChildren = collapsed ? [] : node.children;
    const leaves = collapsed ? 1 : hardwareVisibleLeafCount(node, collapsedNodeIds, mode);
    const start = cursor;
    const sortedChildren = visibleChildren
      .sort((left, right) => hardwareHierarchyRank(left.kind) - hardwareHierarchyRank(right.kind) || left.name.localeCompare(right.name, "de-DE"));
    const childNodes = sortedChildren.map((child, index) => {
      if (index > 0) cursor += hardwareChildGap(depth, mode);
      return { child, placed: place(child, depth + 1) };
    });
    if (visibleChildren.length === 0) cursor += 1;
    const middle = visibleChildren.length === 0 ? start + 0.5 : start + leaves / 2;
    const placed: HardwareRadialNode = {
      ...node,
      angle: (middle / leafSlots) * Math.PI * 2,
      radius: depth * radiusStep,
      depth,
      collapsed,
      parent,
    };
    nodes.push(placed);
    childNodes.forEach(({ child, placed: childNode }) => {
      childNode.parent = placed;
      links.push({ id: `${node.id}->${child.id}`, source: placed, target: childNode, bus: child.bus ?? "can_fd", kind: "hierarchy" });
    });
    return placed;
  }

  place(root, 0);
  if (mode === "combined") {
    const byId = new Map(nodes.map((node) => [node.id, node]));
    nodes.forEach((node) => {
      if (node.kind !== "function" || !node.mappingTargetId) return;
      const target = byId.get(node.mappingTargetId);
      if (!target) return;
      links.push({ id: `${node.id}->mapped:${target.id}`, source: node, target, bus: "can_fd", kind: "mapping" });
    });
  }
  return {
    nodes: nodes.sort((left, right) => left.depth - right.depth),
    links: links.filter((link) => link.source && link.target),
  };
}

function buildHardwareDiagramTree(topology: NetworkTopology, functions: EngFunction[], mode: HardwareDiagramMode): HardwareTreeNode {
  const clusters = buildSystemClusters(topology, functions);
  const systemChildren = clusters.map((cluster) => buildSystemClusterTree(cluster, topology, mode));
  if (mode === "functions") {
    return {
      id: "functions-root",
      name: "Functions",
      kind: "root",
      children: systemChildren,
      connectionCount: functions.length,
    };
  }
  return {
    id: mode === "hardware" ? "hardware-root" : "combined-root",
    name: "Central Gateway",
    kind: "root",
    children: systemChildren,
    connectionCount: topology.edges.length + functions.length,
  };
}

function buildSystemClusterTree(cluster: HardwareSystemCluster, topology: NetworkTopology, mode: HardwareDiagramMode): HardwareTreeNode {
  const children: HardwareTreeNode[] = [];
  if (mode === "functions" || mode === "combined") {
    children.push(buildFunctionTree(cluster.functions, topology, `system:${cluster.id}`));
  }
  if (mode === "hardware" || mode === "combined") {
    children.push({
      id: `system:${cluster.id}:hardware`,
      name: "Hardware",
      kind: "group",
      children: buildClusterHardwareTrees(cluster.hardware, topology),
      connectionCount: cluster.hardware.length,
    });
  }
  return {
    id: `system:${cluster.id}`,
    name: cluster.name,
    kind: "group",
    children,
    connectionCount: cluster.hardware.length + cluster.functions.length,
  };
}

function buildFunctionTree(functions: EngFunction[], topology?: NetworkTopology, idPrefix = "functions"): HardwareTreeNode {
  const hardwareByEngineeringId = new Map((topology?.nodes ?? []).flatMap((node) => node.engineeringId ? [[node.engineeringId, node.id]] : []));
  const mapped: HardwareTreeNode[] = [];
  const unmapped: HardwareTreeNode[] = [];

  functions
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name, "de-DE"))
    .forEach((item) => {
      const mappingTargetId = item.hardware_node_id ? hardwareByEngineeringId.get(item.hardware_node_id) ?? null : null;
      const node: HardwareTreeNode = {
        id: `function:${item.id}`,
        name: item.name,
        kind: mappingTargetId ? "function" : "unmapped",
        children: [],
        connectionCount: mappingTargetId ? 1 : 0,
        functionRef: item,
        mappingTargetId,
      };
      if (mappingTargetId) mapped.push(node);
      else unmapped.push(node);
    });

  const children: HardwareTreeNode[] = [
    {
      id: `${idPrefix}:functions:mapped`,
      name: "Mapped Functions",
      kind: "group",
      children: mapped,
      connectionCount: mapped.length,
    },
  ];
  if (unmapped.length > 0) {
    children.push({
      id: `${idPrefix}:functions:unmapped`,
      name: "Unmapped Functions",
      kind: "unmapped",
      children: unmapped,
      connectionCount: unmapped.length,
    });
  }
  if (functions.length === 0) {
    children[0].children.push({
      id: `${idPrefix}:functions:none`,
      name: "Keine Core-Funktionen",
      kind: "unmapped",
      children: [],
      connectionCount: 0,
    });
  }
  return {
    id: `${idPrefix}:functions`,
    name: "Functions",
    kind: "group",
    children,
    connectionCount: functions.length,
  };
}

function buildSystemClusters(topology: NetworkTopology, functions: EngFunction[]): HardwareSystemCluster[] {
  const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
  const nodeIdByEngineeringId = new Map(topology.nodes.flatMap((node) => node.engineeringId ? [[node.engineeringId, node.id]] : []));
  const adjacency = topologyAdjacencyFromEdges(topology);
  const clusters = new Map<string, HardwareSystemCluster>();

  function ensureCluster(id: string, name: string) {
    const current = clusters.get(id);
    if (current) return current;
    const next: HardwareSystemCluster = { id, name, hardware: [], functions: [] };
    clusters.set(id, next);
    return next;
  }

  function ownerForNode(node: TopologyNode) {
    if (node.kind === "gateway") return { id: "gateway", name: node.name || "Central Gateway" };
    const explicitOwnerId = node.systemOwnerId ? nodeIdByEngineeringId.get(node.systemOwnerId) ?? node.systemOwnerId : undefined;
    const explicitOwner = explicitOwnerId ? nodesById.get(explicitOwnerId) : undefined;
    if (explicitOwner) return systemClusterProfile(explicitOwner.name);
    if (node.kind === "sensor" || node.kind === "actuator") {
      const connectedOwner = [...(adjacency.get(node.id) ?? [])]
        .map((id) => nodesById.get(id))
        .find((candidate): candidate is TopologyNode => Boolean(candidate && candidate.kind === "ecu"));
      if (connectedOwner) return systemClusterProfile(connectedOwner.name);
    }
    if (node.kind === "ecu") return systemClusterProfile(node.name);
    if (node.kind === "sensor" || node.kind === "actuator") return systemClusterProfile(node.name);
    return { id: "unassigned", name: "Nicht zugeordnet" };
  }

  topology.nodes
    .filter((node) => node.kind !== "gateway")
    .forEach((node) => {
      const owner = ownerForNode(node);
      ensureCluster(owner.id, owner.name).hardware.push(node);
    });

  functions.forEach((item) => {
    const mappedNodeId = item.hardware_node_id ? nodeIdByEngineeringId.get(item.hardware_node_id) : undefined;
    const mappedNode = mappedNodeId ? nodesById.get(mappedNodeId) : undefined;
    const owner = mappedNode ? ownerForNode(mappedNode) : { id: "unmapped-functions", name: "Nicht zugeordnet" };
    ensureCluster(owner.id, owner.name).functions.push(item);
  });

  if (clusters.size === 0) ensureCluster("empty", "Nicht zugeordnet");
  return [...clusters.values()]
    .map((cluster) => ({
      ...cluster,
      name: `${cluster.name} · ${cluster.hardware.length} HW · ${cluster.functions.length} F`,
    }))
    .sort((left, right) => left.name.localeCompare(right.name, "de-DE"));
}

function buildClusterHardwareTrees(clusterNodes: TopologyNode[], topology: NetworkTopology): HardwareTreeNode[] {
  const clusterIds = new Set(clusterNodes.map((node) => node.id));
  const byId = new Map(clusterNodes.map((node) => [node.id, node]));
  const treeNodes = new Map<string, HardwareTreeNode>(
    clusterNodes.map((node) => [node.id, {
      id: node.id,
      name: node.name,
      kind: node.kind,
      children: [],
      connectionCount: 0,
    }]),
  );
  const childIds = new Set<string>();

  function attach(child: TopologyNode, parentId: string | undefined) {
    if (!parentId || parentId === child.id || !clusterIds.has(parentId)) return false;
    const parent = treeNodes.get(parentId);
    const childNode = treeNodes.get(child.id);
    if (!parent || !childNode) return false;
    parent.children.push(childNode);
    childIds.add(child.id);
    return true;
  }

  clusterNodes.forEach((node) => {
    const treeNode = treeNodes.get(node.id);
    if (!treeNode) return;
    treeNode.connectionCount = topology.edges.filter((edge) => edge.source === node.id || edge.target === node.id).length;
  });

  clusterNodes.forEach((node) => {
    if (node.kind === "ecu") return;
    const explicitOwner = node.systemOwnerId && clusterIds.has(node.systemOwnerId) ? node.systemOwnerId : undefined;
    if (attach(node, explicitOwner)) return;
    const connectedEcu = topology.edges
      .flatMap((edge) => edge.source === node.id ? [edge.target] : edge.target === node.id ? [edge.source] : [])
      .find((id) => byId.get(id)?.kind === "ecu");
    attach(node, connectedEcu);
  });

  return [...treeNodes.values()]
    .filter((node) => !childIds.has(node.id))
    .sort((left, right) => hardwareHierarchyRank(left.kind) - hardwareHierarchyRank(right.kind) || left.name.localeCompare(right.name, "de-DE"));
}

function topologyAdjacencyFromEdges(topology: NetworkTopology) {
  const adjacency = new Map(topology.nodes.map((node) => [node.id, new Set<string>()]));
  topology.edges.forEach((edge) => {
    adjacency.get(edge.source)?.add(edge.target);
    adjacency.get(edge.target)?.add(edge.source);
  });
  return adjacency;
}

function systemClusterProfile(value: string) {
  const name = systemClusterName(value);
  return { id: `system-domain:${slugSystemCluster(name)}`, name };
}

function systemClusterName(value: string) {
  const cleaned = value
    .replace(/(?:[-_ ]?(?:ECU|Gateway|Sensor|Aktor|Aktuator|Actuator|Controller|Steuergeraet|Steuergerät))+([-_ ]\d+)?$/i, "$1")
    .replace(/^[-_ ]+|[-_ ]+$/g, "");
  const normalized = (cleaned || value || "System")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .toLowerCase();
  const domains: Array<[RegExp, string]> = [
    [/abgas|antrieb|motor|powertrain|getriebe|kraftstoff|inverter|elektromotor|oil|coolant|lambda|throttle|turbo|exhaust/, "Antrieb"],
    [/brems|brake|abs|esp|stabil|fahrwerk|chassis|daempfer|dampfer|lenkung|steer|reifen|wheel|suspension/, "Chassis"],
    [/airbag|crash|gurt|restraint|srs|occupant|safety/, "Sicherheit"],
    [/batterie|battery|energie|bordnetz|power|current|voltage|charge|soc|bms/, "Energie"],
    [/licht|light|wischer|scheiben|door|fenster|window|seat|mirror|body|karosserie|comfort|komfort|keyless|lock|climate|klima|thermal/, "Karosserie"],
    [/adas|assist|radar|kamera|camera|lidar|parking|park|lane|cruise|acc|front|rear|ultrasonic/, "ADAS"],
    [/infotainment|display|audio|navigation|hmi|media|connectivity|telematik|diagnose|diagnostic|ethernet|backbone|gateway/, "Connectivity"],
  ];
  return domains.find(([pattern]) => pattern.test(normalized))?.[1] ?? (cleaned || value || "System");
}

function slugSystemCluster(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ä/g, "ae")
    .replace(/ö/g, "oe")
    .replace(/ü/g, "ue")
    .replace(/ß/g, "ss")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "system";
}

function buildHardwareTree(topology: NetworkTopology): HardwareTreeNode {
  const hardwareEdges = collapseHardwareEdges(topology);
  const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
  const degree = new Map(topology.nodes.map((node) => [node.id, 0]));
  hardwareEdges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + edge.count);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + edge.count);
  });
  const parentById = new Map<string, { parentId: string; bus: BusType }>();
  hardwareEdges.forEach((edge) => {
    if (!parentById.has(edge.target)) parentById.set(edge.target, { parentId: edge.source, bus: edge.bus });
  });
  const treeNodes = new Map<string, HardwareTreeNode>();
  topology.nodes.forEach((node) => {
    treeNodes.set(node.id, {
      id: node.id,
      name: node.name,
      kind: node.kind,
      children: [],
      connectionCount: degree.get(node.id) ?? 0,
    });
  });
  treeNodes.forEach((node, id) => {
    const parent = parentById.get(id);
    if (!parent || parent.parentId === id) return;
    const parentNode = parent ? treeNodes.get(parent.parentId) : undefined;
    if (!parentNode) return;
    node.bus = parent.bus;
    parentNode.children.push(node);
  });
  const attached = new Set([...parentById.keys()]);
  const topLevel = [...treeNodes.entries()]
    .filter(([id]) => !attached.has(id))
    .map(([, node]) => node)
    .sort((left, right) => hardwareHierarchyRank(left.kind) - hardwareHierarchyRank(right.kind) || left.name.localeCompare(right.name, "de-DE"));
  if (topLevel.length === 1 && topLevel[0].kind === "gateway") return topLevel[0];
  return {
    id: "hardware-root",
    name: "Hardware",
    kind: "root",
    children: topLevel,
    connectionCount: topology.edges.length,
  };
}

function collapseHardwareEdges(topology: NetworkTopology): HardwareGraphEdge[] {
  const map = new Map<string, HardwareGraphEdge>();
  const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
  collapsePhysicalEdges(topology.edges).forEach((edge) => {
    if (edge.source === edge.target) return;
    const sourceRank = hardwareHierarchyRank(nodesById.get(edge.source)?.kind ?? "ecu");
    const targetRank = hardwareHierarchyRank(nodesById.get(edge.target)?.kind ?? "ecu");
    const [source, target] = sourceRank < targetRank
      ? [edge.source, edge.target]
      : targetRank < sourceRank
        ? [edge.target, edge.source]
        : [edge.source, edge.target].sort();
    const key = `${edge.bus}:${source}:${target}`;
    const current = map.get(key);
    if (current) {
      current.count += 1;
      return;
    }
    map.set(key, { id: key, source, target, bus: edge.bus, count: 1 });
  });
  return [...map.values()].sort((left, right) => left.id.localeCompare(right.id));
}

function hardwareHierarchyRank(kind: HardwareDiagramNodeKind) {
  if (kind === "root") return -1;
  if (kind === "group") return 0;
  if (kind === "gateway") return 0;
  if (kind === "ecu") return 1;
  if (kind === "function") return 1;
  return 2;
}

function hardwareNodeRole(kind: HardwareDiagramNodeKind) {
  if (kind === "root") return "Topologie";
  if (kind === "group") return "Gruppe";
  if (kind === "function") return "Funktion";
  if (kind === "unmapped") return "Unmapped Function";
  if (kind === "gateway") return "Gateway";
  if (kind === "sensor") return "Sensor";
  if (kind === "actuator") return "Aktor";
  return "ECU";
}

function hardwareNodeRadius(node: HardwareRadialNode) {
  if (node.kind === "root") return 15;
  if (node.kind === "group") return 12;
  if (node.kind === "gateway") return 12;
  if (node.kind === "function" || node.kind === "unmapped") return 8;
  if (node.kind === "ecu") return 8;
  return 5.5;
}

function hardwareNodeSymbol(kind: HardwareDiagramNodeKind) {
  if (kind === "root") return "HW";
  if (kind === "group") return "G";
  if (kind === "function") return "F";
  if (kind === "unmapped") return "!";
  if (kind === "gateway") return "GW";
  if (kind === "sensor") return "S";
  if (kind === "actuator") return "A";
  return "E";
}

function hardwareDiagramModeTitle(mode: HardwareDiagramMode) {
  if (mode === "functions") return "System -> Function -> Mapping-Status";
  if (mode === "combined") return "Gateway -> System plus Function-Hardware-Mapping";
  return "Gateway -> ECU -> Sensor | Aktor";
}

function hardwareLinkTone(link: HardwareRadialLink) {
  if (link.kind === "mapping") return "mapping-link";
  if (link.source.kind === "function" || link.target.kind === "function" || link.source.id.includes(":functions") || link.target.id.includes(":functions")) {
    return "function-link";
  }
  if (link.source.kind === "ecu" || link.target.kind === "ecu" || link.source.kind === "sensor" || link.target.kind === "sensor" || link.source.kind === "actuator" || link.target.kind === "actuator" || link.source.kind === "gateway" || link.target.kind === "gateway") {
    return "hardware-link";
  }
  return "system-link";
}

function hardwareLinkStroke(link: HardwareRadialLink) {
  const tone = hardwareLinkTone(link);
  if (tone === "mapping-link" || tone === "function-link") return "var(--eng-function)";
  if (tone === "hardware-link") return "var(--eng-hardware)";
  return "var(--accent)";
}

function hardwareShowNodeLabel(
  node: HardwareRadialNode,
  mode: HardwareDiagramMode,
  selected: boolean,
  focused: boolean,
  hasFocus: boolean,
) {
  if (selected || (hasFocus && focused)) return true;
  if (mode !== "combined") return true;
  if (node.children.length > 0) return true;
  return node.kind === "gateway" || node.kind === "group" || node.kind === "function";
}

function hardwareLeafCount(node: HardwareTreeNode): number {
  return node.children.length ? node.children.reduce((total, child) => total + hardwareLeafCount(child), 0) : 1;
}

function hardwareVisibleLeafCount(
  node: HardwareTreeNode,
  collapsedNodeIds: Set<string>,
  mode: HardwareDiagramMode,
): number {
  if (collapsedNodeIds.has(node.id) || node.children.length === 0) return 1;
  const childSlots = node.children.reduce((total, child) => total + hardwareVisibleLeafCount(child, collapsedNodeIds, mode), 0);
  return childSlots + Math.max(0, node.children.length - 1) * hardwareChildGap(node.kind === "root" ? 0 : node.kind === "group" ? 1 : 2, mode);
}

function hardwareChildGap(depth: number, mode: HardwareDiagramMode) {
  if (mode === "combined") {
    if (depth === 0) return COMBINED_RADIAL_ROOT_GAP;
    if (depth === 1) return COMBINED_RADIAL_CLUSTER_GAP;
    return COMBINED_RADIAL_GROUP_GAP;
  }
  if (depth === 0) return HARDWARE_RADIAL_ROOT_GAP;
  if (depth === 1) return HARDWARE_RADIAL_CLUSTER_GAP;
  return HARDWARE_RADIAL_GROUP_GAP;
}

function hardwareTreeDepth(node: HardwareTreeNode): number {
  return node.children.length ? 1 + Math.max(...node.children.map(hardwareTreeDepth)) : 0;
}

function radialPoint(angle: number, radius: number) {
  const adjusted = angle - Math.PI / 2;
  return {
    x: Math.cos(adjusted) * radius,
    y: Math.sin(adjusted) * radius,
  };
}

function radialLinkPath(source: HardwareRadialNode, target: HardwareRadialNode) {
  const middleRadius = (source.radius + target.radius) / 2;
  const start = radialPoint(source.angle, source.radius);
  const first = radialPoint(source.angle, middleRadius);
  const second = radialPoint(target.angle, middleRadius);
  const end = radialPoint(target.angle, target.radius);
  return `M${start.x},${start.y}C${first.x},${first.y} ${second.x},${second.y} ${end.x},${end.y}`;
}

function hardwareFocusSets(
  nodes: HardwareRadialNode[],
  links: HardwareRadialLink[],
  selectedNodeId: string,
  selectedLinkId: string,
) {
  const focusedNodes = new Set<string>();
  const focusedLinks = new Set<string>();
  if (selectedLinkId) {
    const selected = links.find((link) => link.id === selectedLinkId);
    if (selected) {
      focusedLinks.add(selected.id);
      focusedNodes.add(selected.source.id);
      focusedNodes.add(selected.target.id);
    }
    return { nodes: focusedNodes, links: focusedLinks };
  }
  if (!selectedNodeId) return { nodes: focusedNodes, links: focusedLinks };
  const byParent = new Map<string, HardwareRadialLink[]>();
  links.forEach((link) => byParent.set(link.source.id, [...(byParent.get(link.source.id) ?? []), link]));
  const selected = nodes.find((node) => node.id === selectedNodeId);
  let current: HardwareRadialNode | undefined = selected;
  while (current) {
    focusedNodes.add(current.id);
    if (current.parent) focusedLinks.add(`${current.parent.id}->${current.id}`);
    current = current.parent;
  }
  const visitChildren = (nodeId: string) => {
    for (const link of byParent.get(nodeId) ?? []) {
      focusedLinks.add(link.id);
      focusedNodes.add(link.target.id);
      visitChildren(link.target.id);
    }
  };
  visitChildren(selectedNodeId);
  return { nodes: focusedNodes, links: focusedLinks };
}

function shortHardwareLabel(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 22 ? `${trimmed.slice(0, 19)}...` : trimmed;
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
