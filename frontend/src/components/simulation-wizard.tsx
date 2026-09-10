"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCatalog } from "@/lib/api";
import { listAllEngineeringObjects, syncEngineeringTopology } from "@/lib/engineering-api";
import { localCatalog } from "@/lib/local-simulator";
import { listRoutes } from "@/lib/routing-api";
import type { Catalog, EngFunction, HardwareNode, RoutingEntry, Technology, TechnologyParameterField } from "@/lib/types";
import { NetworkEditor } from "./network-editor";
import { HardwareTopologyView } from "./hardware-topology-view";
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
import { getNetworkView, saveNetworkView, renamePhysicalBus, getWorkflow, saveWorkflowParameters, saveWorkflowTopology, saveBusChange, saveNetworkAssignment, createFrameDevice, type FrameDeviceRequest, type NetworkAssignmentRequest, type BusChangeRequest } from "@/lib/workflow-api";
import { routingBusType as routingBus } from "@/lib/bus-technology";
import { defaultSimulationFormats } from "@/lib/simulation-formats";
import {
  notifyWorkflowChanged,
  notifyWorkflowDraftStatus,
  WORKFLOW_CHANGED_EVENT,
} from "./workflow-header";
import { withProjectParam } from "@/lib/user-settings";

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
          physicalNetworkId: port.physicalNetworkId,
          physicalNetworkName: port.physicalNetworkName,
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
      physicalNetworkId: edge.physicalNetworkId,
      physicalNetworkName: edge.physicalNetworkName,
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
  initialProjectId = "",
  initialMode = "parameters",
}: {
  initialProjectId?: string;
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
  const savedLayoutRef = useRef(topology);
  const editTokensRef = useRef<{ topology?: string; parameters?: string }>({});
  const projectIdForLinks = initialProjectId;

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

  const persistNetworkLayout = useCallback(async (next: NetworkTopology, reset = false, resetWires = false) => {
    const previous = new Map(savedLayoutRef.current.nodes.map(n => [n.id, n]));
    const positions = Object.fromEntries(next.nodes.filter(n => {
      const old = previous.get(n.id);
      return resetWires || old && (old.x !== n.x || old.y !== n.y || old.width !== n.width || old.height !== n.height || JSON.stringify(old.ports) !== JSON.stringify(n.ports));
    }).map(n => [n.id, {x:n.x, y:n.y, width:n.width, height:n.height, ports:Object.fromEntries(n.ports.map(p=>[p.id,{side:p.side,offset:p.offset}]))}]));
    const state = await saveNetworkView(positions, editTokensRef.current.topology, reset, next.scene?.manualBusRoutes, resetWires);
    editTokensRef.current.topology = state.edit_tokens.topology;
    savedLayoutRef.current = state.topology;
    setTopology(state.topology);
  }, []);

  const persistBusName = useCallback(async (networkId: string, name: string) => {
    const state = await renamePhysicalBus(networkId, name, editTokensRef.current.topology, editTokensRef.current.parameters);
    const saved = state.topology as NetworkTopology;
    editTokensRef.current = state.edit_tokens ?? {};
    savedLayoutRef.current = saved;
    topologyRef.current = saved;
    setTopology(saved);
    localWorkflowChangeRef.current = true;
    setModelRefreshPending(false);
    notifyWorkflowChanged();
    return saved;
  }, []);

  const persistNetworkRelationships = useCallback(async (next: NetworkTopology, busChange?: BusChangeRequest) => {
    setEngineeringSync((current) => ({ ...current, status: "syncing", error: "" }));
    setRoutingSyncMessage("Routing-Vorschläge werden abgeglichen …");
    try {
      const state = busChange ? await saveBusChange(busChange, editTokensRef.current.topology)
        : await saveWorkflowTopology(next.scene ? next : normalizePhysicalTopology(next), editTokensRef.current.topology);
      editTokensRef.current = state.edit_tokens ?? {};
      if (Array.isArray(state.topology.nodes) && Array.isArray(state.topology.edges)) {
        const savedTopology: NetworkTopology = state.topology.scene ? {...state.topology, nodes: state.topology.nodes, edges: state.topology.edges} : normalizePhysicalTopology({ nodes: state.topology.nodes, edges: state.topology.edges });
        setRoutingLinkRevision(topologyRoutingLinkRevision(savedTopology));
        setTopology(savedTopology);
        savedLayoutRef.current = savedTopology;
        setEngineeringSync({
          status: "synced",
          linked: savedTopology.nodes.filter((node) => node.engineeringId).length,
          error: "",
        });
      }
      const counts = state.routing_sync?.counts;
      if (busChange) {
        setRoutingSyncMessage("Bustyp im Modell gespeichert und Routing-Prüfung aktualisiert. Betroffene Routen benötigen eine erneute Freigabe.");
      } else if (!counts) {
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
      if (busChange) throw error;
      return false;
    }
  }, []);

  const persistNetworkAssignment = useCallback(async (request: NetworkAssignmentRequest) => {
    const state = await saveNetworkAssignment(request, editTokensRef.current.topology);
    if (!state.topology.nodes || !state.topology.edges) throw new Error('Die gespeicherte Zuordnung konnte nicht vollständig geladen werden. Bitte die Ansicht neu laden.');
    const saved: NetworkTopology = {...state.topology,nodes:state.topology.nodes,edges:state.topology.edges};
    editTokensRef.current = state.edit_tokens ?? {};
    savedLayoutRef.current = saved;
    topologyRef.current = saved;
    setTopology(saved);
    setRoutingLinkRevision(topologyRoutingLinkRevision(saved));
    setRoutingSyncMessage(request.target_kind === 'bus'
      ? 'Geräteanschluss auf den Zielbus umgehängt. Nachrichten und Ansicht sind gespeichert; betroffene Routen wurden validiert und können erneut freigegeben werden.'
      : 'Zuordnung, Busanschlüsse und Nachrichten gespeichert. Betroffene Routen wurden erneut validiert und können in der Routing-Tabelle freigegeben werden.');
    localWorkflowChangeRef.current = true;
    setModelRefreshPending(false);
    setEngineeringSync({status:'synced',linked:saved.nodes.filter(node=>node.engineeringId).length,error:''});
    // The assignment endpoint already synchronized and stored the scene.
    // Refresh read models only; a second topology sync would regenerate routes.
    setRouteRefreshRequest(value=>value+1);
    notifyWorkflowChanged();
  }, []);

  const persistFrameDevice = useCallback(async (request: FrameDeviceRequest) => {
    const state = await createFrameDevice(request, editTokensRef.current.topology);
    if (!state.topology.nodes || !state.topology.edges) throw new Error('Das Gerät wurde gespeichert. Bitte die Ansicht neu laden.');
    const saved: NetworkTopology = {...state.topology, nodes: state.topology.nodes, edges: state.topology.edges};
    editTokensRef.current = state.edit_tokens ?? {};
    savedLayoutRef.current = saved;
    topologyRef.current = saved;
    setTopology(saved);
    setRoutingLinkRevision(topologyRoutingLinkRevision(saved));
    setRoutingSyncMessage(`„${request.name}“ im Systemrahmen angelegt. Anschlüsse und Gerätedetails können jetzt ergänzt werden.`);
    localWorkflowChangeRef.current = true;
    setModelRefreshPending(false);
    setEngineeringSync({status: 'synced', linked: saved.nodes.filter(node => node.engineeringId).length, error: ''});
    setRouteRefreshRequest(value => value + 1);
    notifyWorkflowChanged();
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
    if (mode === "network") {
      let active = true;
      void getNetworkView().then(state => {
        if (!active) return;
        editTokensRef.current = state.edit_tokens;
        savedLayoutRef.current = state.topology;
        setTopology(state.topology);
        setRoutingLinkRevision(topologyRoutingLinkRevision(state.topology));
        setWorkflowLoaded(true);
      }).catch(error => { if (active) setFormError(error instanceof Error ? error.message : "Netzwerkansicht konnte nicht geladen werden."); });
      return () => { active = false; };
    }
    getWorkflow()
      .then((state) => {
        editTokensRef.current = state.edit_tokens ?? {};
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
  }, [mode]);

  useEffect(() => {
    if (mode !== "parameters") return;
    return () => notifyWorkflowDraftStatus("parameters", null);
  }, [mode]);

  useEffect(() => {
    if (mode !== "network" || !workflowLoaded) return;
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
    if (mode !== "network" || !workflowLoaded) return;
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
        syncEngineeringTopology(topologyForSync, editTokensRef.current.topology),
      ])
        .then(async ([items, functionItems, result]) => {
          const saved = await getNetworkView();
          if (cancelled) return;
          setModelHardware(items.filter((item): item is HardwareNode => "device_type" in item));
          setModelFunctions(functionItems.filter((item): item is EngFunction => item.object_type === "Function"));
          const nextTopology = saved.topology;
          editTokensRef.current = saved.edit_tokens;
          savedLayoutRef.current = nextTopology;
          topologyRef.current = nextTopology;
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
        const saved = await saveWorkflowTopology(topology, editTokensRef.current.topology);
        editTokensRef.current = saved.edit_tokens ?? {};
        setSavedMessage("Netzwerktopologie gespeichert. Capacity & Timing ist jetzt gegebenenfalls veraltet.");
      } else if (advanced) {
        const parsed = JSON.parse(advancedConfig) as Record<string, unknown>;
        const saved = await saveWorkflowParameters(parsed, editTokensRef.current.parameters);
        editTokensRef.current = saved.edit_tokens ?? {};
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
        const saved = await saveWorkflowParameters(parameters, editTokensRef.current.parameters);
        editTokensRef.current = saved.edit_tokens ?? {};
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
              <Link className="button secondary" href={withProjectParam("/studio/capacity", projectIdForLinks)}>
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
                  <strong
                    title={engineeringSync.error || undefined}
                  >
                    {modelRefreshPending
                      ? `Modelländerung wartet auf Aktualisierung${engineeringSync.error ? `: ${engineeringSync.error}` : ""}`
                      : engineeringSync.status === "syncing"
                      ? "Wird synchronisiert …"
                      : engineeringSync.status === "synced"
                        ? `${engineeringSync.linked}/${topology.nodes.length} Geräte verknüpft`
                      : engineeringSync.status === "error"
                          ? `Synchronisierung fehlgeschlagen: ${engineeringSync.error || "Unbekannter Fehler"}`
                          : topology.nodes.length === 0
                            ? "Keine Geräte vorhanden"
                            : `Gespeicherte Topologie: ${topology.nodes.filter(node => node.engineeringId).length}/${topology.nodes.length} Geräte mit Modellreferenz`}
                  </strong>
                </div>
              </div>
              <div className="net-model-sync-actions">
                <Link href={withProjectParam("/studio/engineering", projectIdForLinks)}>Modell öffnen ↗</Link>
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
            </div>
            {networkView === "editor" ? (
              !workflowLoaded ? <p role="status">Gespeicherte Netzwerkansicht wird geladen …</p> :
              topology.nodes.length > 0 && !topology.scene ? <div className="net-scene-missing"><p>Für dieses ältere Projekt ist noch keine vorbereitete Busansicht gespeichert.</p><button className="button primary" type="button" onClick={() => void persistNetworkLayout(topology, true).catch(error => setFormError(error.message))}>Busansicht vorbereiten</button></div> :
              <NetworkEditor
                modelHardware={modelHardware}
                onChange={setTopology}
                onLayoutChange={persistNetworkLayout}
          onAssignmentChange={persistNetworkAssignment}
          onFrameDeviceCreate={persistFrameDevice}
          onBusRename={persistBusName}
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
                  <Link href={withProjectParam("/studio/routing?view=graph", projectIdForLinks)}>Routing-Graph öffnen ↗</Link>
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
            <Link className="button secondary" href={withProjectParam("/studio?mode=parameters", projectIdForLinks)}>
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
              <div><dt>Physische Busse</dt><dd>{new Set(topology.edges.map((edge) => edge.physicalNetworkId)).size}</dd></div>
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
