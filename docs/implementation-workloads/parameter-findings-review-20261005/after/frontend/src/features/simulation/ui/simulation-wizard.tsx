"use client";

import { parseLosslessJson } from "../../../shared/api/lossless-json.ts";

import { booleanParameterValue, numericParameterValue, conditionalParameterDefault, confirmTechnologyParameters, technologyParameterUnverified as parameterIsUnverified, technologyParameterValues, parameterValueStatus, findingsForParameter, technologyKey, type DeclaredNetwork } from "@/features/communication/lib/technology-parameters";

import Link from "next/link";
import { engineeringContextHref } from "@/features/agent/lib/assistant-context";
import { useSearchParams } from "next/navigation";
import { NetworkRateReview } from "@/features/agent/ui/wizard-preflight-review";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCatalog } from "@/shared/api/api";
import { listAllEngineeringObjects, syncEngineeringTopology } from "@/shared/api/engineering-api";
import { localCatalog } from "@/shared/lib/local-simulator";
import { listRoutes } from "@/features/routing/lib/routing-api";
import type { Catalog, EngFunction, HardwareNode, RoutingEntry, Technology, TechnologyDomain, TechnologyParameterField } from "@/shared/api/types";
import { NetworkEditor } from "../../network/ui/network-editor";
import { HardwareTopologyView } from "../../network/ui/hardware-topology-view";
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
} from "@/features/network/lib/topology";
import { getNetworkView, saveNetworkView, renamePhysicalBus, getWorkflowSummary, getWorkflowParameters, getParameterReview, type ParameterReview, saveWorkflowParameters, saveWorkflowTopology, saveBusChange, saveNetworkAssignment, createFrameDevice, type FrameDeviceRequest, type NetworkAssignmentRequest, type BusChangeRequest } from "@/features/workflow/lib/workflow-api";
import { routingBusType as routingBus } from "@/features/communication/lib/bus-technology";
import { defaultSimulationFormats } from "@/features/simulation/lib/simulation-formats";
import { fuzzyTechnologySearch, parameterTechnologySelection, registeredTechnologies } from "@/features/communication/lib/technology-catalog-selection";
import pickerStyles from "../../communication/ui/technology-picker.module.css";
import {
  notifyWorkflowChanged,
  notifyWorkflowDraftStatus,
  WORKFLOW_CHANGED_EVENT,
} from "../../workflow/ui/workflow-header";
import { withProjectParam, readActiveProjectId } from "@/features/settings/lib/user-settings";
import type { LicenseState } from "@/features/sources/lib/source-directory";

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
  technology: "Technologiespezifische Parameter",
  communication: "Bus und Protokoll",
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
      if (!bus) { keys.add(`${route.id}:TECHNOLOGY_UNRESOLVED`); continue; }
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
      if (!bus) return []; // Never create a partially substituted route.
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

  const unresolved = useMemo(() => routes.filter(routeCanSuggestNetworkChange).filter(route =>
    !routingBus(route.source.protocol, route.source.network_id) || route.destinations.some(destination =>
      !routingBus(destination.protocol ?? route.source.protocol, destination.network_id))), [routes]);
  return { checking, suggestions, unresolved };
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
  const searchParams = useSearchParams();
  const requestedTechnology = searchParams.get("technology");
  const [parameterReview, setParameterReview] = useState<ParameterReview | null>(null);
  const [parameterReviewError, setParameterReviewError] = useState("");
  const [parameterDraftDirty, setParameterDraftDirty] = useState(false);
  const [networkConfirming, setNetworkConfirming] = useState(false);
  const [catalog, setCatalog] = useState<Catalog>(localCatalog);
  const [catalogError, setCatalogError] = useState("");
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [licenseStates, setLicenseStates] = useState<Record<string, LicenseState>>({});
  const [licenseError, setLicenseError] = useState('');
  const [domainId, setDomainId] = useState("");
  const [technologyId, setTechnologyId] = useState("");
  const [technologySearch, setTechnologySearch] = useState("");
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
    let active = true;
    setCatalogLoaded(false); setCatalogError("");
    void getCatalog({ strict: mode === "parameters" }).then(value => {
      if (active) { setCatalog(value); setCatalogLoaded(true); }
    }).catch(error => {
      if (active) setCatalogError(error instanceof Error ? error.message : "Technologiekatalog konnte nicht geladen werden.");
    });
    return () => { active = false; };
  }, [mode]);

  useEffect(() => {
    let active = true;
    setLicenseStates({}); setLicenseError('');
    const project = initialProjectId || readActiveProjectId();
    void fetch('/api/technology-licenses', {cache: 'no-store', headers: {'X-Project-ID': project}})
      .then(async response => { const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Lizenzstatus nicht erreichbar.'); return data; })
      .then(data => { if (active) setLicenseStates(data.licenses); })
      .catch(error => { if (active) setLicenseError(error instanceof Error ? error.message : 'Lizenzstatus nicht erreichbar.'); });
    return () => { active = false; };
  }, [initialProjectId]);

  useEffect(() => {
    if (mode === "parameters") {
      let active = true;
      setWorkflowLoaded(false); setFormError("");
      void Promise.all([
        getWorkflowParameters(initialProjectId),
        getWorkflowSummary(initialProjectId, { fresh: true }),
      ]).then(([state, summary]) => {
        if (!active) return;
        if (state.project_id !== summary.project_id) throw new Error("Parameter und Wizard-Auswahl gehören zu verschiedenen Projekten.");
        editTokensRef.current.parameters = state.edit_token;
        setStoredParameters(state.parameters);
        const selection = parameterTechnologySelection(state.parameters, summary.context ?? {});
        setDomainId(selection.domainId);
        setTechnologyId(requestedTechnology ? technologyKey(requestedTechnology) : selection.technologyId);
        setWorkflowLoaded(true);
      }).catch(error => { if (active) setFormError(error instanceof Error ? error.message : "Parameter konnten nicht geladen werden."); });
      return () => { active = false; };
    }
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
  }, [mode, initialProjectId, requestedTechnology]);

  useEffect(() => {
    if (mode !== "parameters" || !workflowLoaded) return;
    let active = true; setParameterReview(null); setParameterReviewError("");
    void getParameterReview(initialProjectId).then(review => {
      if (!active) return;
      if (review.edit_token !== editTokensRef.current.parameters) throw new Error("Der gespeicherte Parameterstand wurde geändert. Bitte die Ansicht neu laden.");
      setParameterReview(review);
    }).catch(error => { if (active) setParameterReviewError(error instanceof Error ? error.message : "Parameterprüfung fehlgeschlagen."); });
    return () => { active = false; };
  }, [mode, initialProjectId, workflowLoaded, syncRequest]);

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
  const allTechnologies = useMemo(() => registeredTechnologies(catalog), [catalog]);
  const matchingTechnologies = useMemo(
    () => fuzzyTechnologySearch(allTechnologies, technologySearch),
    [allTechnologies, technologySearch],
  );
  const technology = useMemo(
    () => allTechnologies.find((item) => item.id === technologyId),
    [allTechnologies, technologyId],
  );
  const displayedParameters = useMemo(() => technology ? technologyParameterValues(storedParameters, technology) : {}, [storedParameters, technology]);
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
    unresolved: unresolvedRoutingTechnologies,
  } = useRoutingNetworkSuggestions(
    routingEntries,
    topology,
    modelHardware,
    routingLinkRevision,
  );

  function chooseDomain(value: string) {
    setDomainId(value);
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
        const parsed = parseLosslessJson(advancedConfig) as Record<string, unknown>;
        const saved = await saveWorkflowParameters(parsed, editTokensRef.current.parameters, initialProjectId);
        editTokensRef.current = saved.edit_tokens ?? {};
        setStoredParameters(saved.parameters);
        setSavedMessage("Parameterkonfiguration gespeichert.");
      } else {
        if (!formElement) throw new Error("Konfigurationsformular nicht gefunden.");
        const form = new FormData(formElement);
        const dynamicParameters = Object.fromEntries(
          (technology?.parameter_schema ?? []).filter(field => !busLoadRangeKeys.has(field.key)).map((field) => {
            const raw = form.get(field.key);
            if (field.type === "number") {
              const entered = typeof raw === "string" ? raw.trim() : "";
              return [field.key, numericParameterValue(field, entered)];
            }
            if (field.type === "boolean") return [field.key, booleanParameterValue(field, raw)];
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
        if (!technology) throw new Error("Das Technologieprofil ist nicht verfügbar.");
        const parameters = { ...confirmTechnologyParameters(storedParameters, technology, dynamicParameters,
          {preserveSimulationAssumptions:true}), industry: domainId, formats };
        const saved = await saveWorkflowParameters(parameters, editTokensRef.current.parameters, initialProjectId);
        editTokensRef.current = saved.edit_tokens ?? {};
        setStoredParameters(saved.parameters);
        setSavedMessage("Technologie- und Timing-Parameter gespeichert.");
      }
      if (mode === "network") localWorkflowChangeRef.current = true;
      if (mode === "parameters") { setParameterDraftDirty(false); notifyWorkflowDraftStatus("parameters", null); setSyncRequest(value => value + 1); }
      notifyWorkflowChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Anfrage fehlgeschlagen.");
    } finally {
      setSubmitting(false);
    }
  }

  async function afterNetworkConfirmation() {
    const state = await getWorkflowParameters(initialProjectId);
    editTokensRef.current.parameters = state.edit_token;
    setStoredParameters(state.parameters);
    setSyncRequest(value => value + 1);
  }

  const currentFindings = parameterReview?.findings ?? [];
  const selectedFindings = currentFindings.filter(item => technologyKey(item.technology) === technologyKey(technologyId));
  const networkRateKeys = (technology?.parameter_schema ?? []).filter(field => field.scope === 'network' && field.unit === 'bit/s').map(field => field.key);
  const affectedNetworks = ((storedParameters.networks ?? []) as DeclaredNetwork[]).filter(network =>
    technologyKey(network.technology) === technologyKey(technologyId)
    && selectedFindings.some(finding => finding.network_id === network.id && finding.code === 'CAPACITY_UNVERIFIED'
      && finding.parameter_fields?.some(key => networkRateKeys.includes(key))));
  const affectedFieldKeys = [...new Set(selectedFindings.flatMap(finding => finding.parameter_fields ?? []))];
  const findingTechnologies = [...new Set(currentFindings.map(item => technologyKey(item.technology)))];
  const proposedFieldCount = (technology?.parameter_schema ?? []).filter(field => parameterValueStatus(storedParameters, field.key, technologyId) === 'PROPOSAL').length;
  const assumptionFieldCount = (technology?.parameter_schema ?? []).filter(field => parameterValueStatus(storedParameters, field.key, technologyId) === 'SAVED_ASSUMPTION').length;

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
  if (mode === "parameters" && (!catalogLoaded || !workflowLoaded)) {
    if (formError) return <div className="panel error-card" role="alert"><h2>Parameter konnten nicht geladen werden</h2><p>{formError}</p></div>;
    return <div className="panel loading-panel" role="status">Gespeicherte Parameter und Technologieprofile werden geladen …
      {formError && <p role="alert">{formError}</p>}
    </div>;
  }
  if (!domain || !technology) {
    return <div className="panel error-card" role="alert">
      <h2>Branche und Technologie auswählen</h2>
      <p>Für dieses Projekt ist noch keine vollständige Parameterauswahl bestätigt. Wähle den Anwendungsbereich und ein registriertes Technologieprofil.</p>
      <label>Anwendungsbereich
        <select aria-label="Anwendungsbereich auswählen" value={domain ? domainId : ""} onChange={(event) => chooseDomain(event.target.value)}>
          <option value="">Bitte auswählen</option>
          {(catalog?.domains ?? []).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
      <div className="field">
        <label htmlFor="initial-technology">Bus / Protokoll</label>
        <div className={pickerStyles.pickerRow}>
          <select aria-label="Bus / Protokoll auswählen" id="initial-technology" value={technology ? technologyId : ""} onChange={(event) => chooseTechnology(event.target.value)}>
            <option value="">Bitte auswählen</option>
            <TechnologyOptions domain={domain} technologies={allTechnologies} matches={matchingTechnologies} query={technologySearch} selectedId={technologyId} licenses={licenseStates} />
          </select>
          <input aria-label="Bus / Protokoll suchen" onChange={(event) => setTechnologySearch(event.target.value)} placeholder="Bus suchen" type="search" value={technologySearch} />
        </div>
        {technologySearch && <small role="status">{matchingTechnologies.length} Treffer</small>}
      </div>
    </div>;
  }

  return (
    <>
      {mode === 'parameters' && <section className="panel parameter-findings-panel" id="parameter-findings" aria-label="Aktuelle Parameterbefunde">
        <h3>Aktuelle Parameterprüfung</h3>
        <p>Prüfung der gespeicherten Netz- und Geräteanschlüsse. Änderungen im Formular werden nach dem Speichern erneut geprüft.</p>
        {searchParams.get('proposal') && <p>Du kommst aus einer Vorschlagsprüfung. Hier werden die aktuellen Projektwerte geprüft; frühere Vorschlagsbefunde können bereits erledigt sein.</p>}
        {!parameterReview && !parameterReviewError && <p role="status">Aktuelle Befunde werden geprüft …</p>}
        {parameterReviewError && <p className="notice error" role="alert">{parameterReviewError}</p>}
        {parameterReview && <>
          <p role="status">{currentFindings.length ? `${currentFindings.length} offene Anschlussbefunde · ${selectedFindings.length} für ${technology.label}` : 'Keine offenen Anschlussbefunde in dieser Parameterprüfung.'} Diese Prüfung ersetzt keine vollständige Preflight- oder Timing-Freigabe.</p>
          <nav aria-label="Technologien mit Parameterbefunden">{findingTechnologies.map(id => <button type="button" className="button secondary tiny" key={id} onClick={() => chooseTechnology(id)}>{allTechnologies.find(item => item.id === id)?.label ?? id} · {currentFindings.filter(item => technologyKey(item.technology) === id).length}</button>)}</nav>
          {Boolean(selectedFindings.length) && <div className="notice error" role="alert">
            <strong>{new Set(selectedFindings.map(item => item.network_id).filter(Boolean)).size} betroffene Netze · {selectedFindings.length} Anschlüsse</strong>
            <p>Ein angezeigter Profilwert oder eine gespeicherte Simulationsannahme ist noch kein bestätigter Netzparameter. Offene Bestätigungen sind im Formular markiert; Geräte- und Modellnachweise bleiben separat sichtbar.</p>
            <nav aria-label="Betroffene Parameterfelder">{affectedFieldKeys.map(key => <a key={key} href={`#parameter-field-${key}`}>{technology.parameter_schema?.find(field => field.key === key)?.label ?? key}</a>)}</nav>
            <details><summary>Betroffene Anschlüsse und Netze anzeigen</summary><ul>{selectedFindings.map((finding,index) => <li key={index}><strong>{finding.node_name} · {finding.network_name ?? finding.network_id}</strong>: {finding.message} <a href={engineeringContextHref({object_type:'HardwareNetworkInterface',id:finding.object_id ?? ''}, initialProjectId) ?? withProjectParam('/studio/engineering?resource=hardware-interfaces',initialProjectId)}>Anschluss prüfen</a>
              {!!finding.parameter_findings?.length && <ul>{finding.parameter_findings.map((detail,i) => <li key={i}>{detail.message ?? detail.code}</li>)}</ul>}
            </li>)}</ul></details>
          </div>}
          {!!affectedNetworks.length && <NetworkRateReview key={`${parameterReview.edit_token}:${technologyId}`} technology={technology} networks={affectedNetworks}
            snapshot={{project_id:parameterReview.project_id,parameters:storedParameters,edit_token:parameterReview.edit_token}}
            projectId={initialProjectId} disabled={submitting || parameterDraftDirty} fieldKeys={affectedFieldKeys} onContinue={afterNetworkConfirmation} onBusyChange={setNetworkConfirming} />}
          {!!affectedNetworks.length && parameterDraftDirty && <p role="status">Speichere zuerst die Änderungen im Parameterformular. Danach können die ausgewählten Netzwerte bestätigt werden.</p>}
        </>}
        <button className="button secondary tiny" type="button" onClick={() => setSyncRequest(value => value + 1)}>Parameterbefunde erneut prüfen</button>
      </section>}
      <div className={`workspace-grid ${mode === "network" ? "network-mode" : "parameters-mode"}`}>
      <form
        key={`${mode}:${JSON.stringify(storedParameters)}`}
        className="panel config-panel"
        inert={networkConfirming || undefined}
        onChange={() => {
          if (mode === "parameters") { setParameterDraftDirty(true); notifyWorkflowDraftStatus("parameters", "OUTDATED"); }
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
              <HardwareTopologyView functions={modelFunctions} topology={topology} routes={routingEntries} hardwareDetails={modelHardware} routingError={routingLoadError} />
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
              {unresolvedRoutingTechnologies.length > 0 && <p role="alert" className="net-route-suggestions-error">
                Für {unresolvedRoutingTechnologies.map(route => `${route.route_code} (${route.source.protocol || 'Technologie fehlt'})`).join(', ')} ist die Buszuordnung offen.
                Bitte die bestätigte Technologie und den physischen Pfad im Routing prüfen; diese Vorschläge können nicht übernommen werden.
              </p>}
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
            {(proposedFieldCount > 0 || assumptionFieldCount > 0) && <p className="notice parameter-gap-notice" role="status">
              <strong>Parameterherkunft · {assumptionFieldCount} gespeicherte Simulationsannahmen · {proposedFieldCount} Profilvorschläge</strong><br />
              Simulationsannahmen sind gespeicherte Projektwerte und enthalten keinen Hardware- oder Messnachweis. Profilvorschläge werden mit „Parameter speichern“ in das Projekt übernommen. Offene Prüfanforderungen stehen unter „Aktuelle Parameterprüfung“ und an den betroffenen Feldern.
              Geänderte Parameter werden als Nutzerwerte in der Projektdatei user_defined_values.json gespeichert. Die zentralen Technologie-Defaults bleiben unverändert.
            </p>}
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
                {parameterIsUnverified(storedParameters, "technology", technologyId) && <small>UNVERIFIED · Keine bestätigte Technologieauswahl</small>}
                <div className={pickerStyles.pickerRow}>
                  <select
                    id="technology"
                    onChange={(event) => chooseTechnology(event.target.value)}
                    value={technologyId}
                  >
                    <TechnologyOptions domain={domain} technologies={allTechnologies} matches={matchingTechnologies} query={technologySearch} selectedId={technologyId} licenses={licenseStates} />
                  </select>
                  <input
                    aria-label="Bus / Protokoll suchen"
                    onChange={(event) => { event.stopPropagation(); setTechnologySearch(event.target.value); }}
                    placeholder="Bus suchen"
                    type="search"
                    value={technologySearch}
                  />
                </div>
                {technologySearch && <small role="status">{matchingTechnologies.length} Treffer</small>}
              </div>
            </div>

            <TechnologyCard technology={technology} />
            {technology.licensing_policy?.clearance_required && <div className="notice warning" role="status">
              {licenseStates[technology.id]?.blocked === false ? '✓ Geprüfte projektbezogene Technikfreigabe vorhanden.'
                : '⚠ Ausführung gesperrt: Eine geprüfte projektbezogene Technikfreigabe fehlt.'}
              {licenseError && <p>{licenseError} Eine Freigabe wird nicht angenommen.</p>}
              <p>{technology.licensing_policy.reason}</p>
              <Link href={withProjectParam('/sources', projectIdForLinks)}>Nachweise im Quellenverzeichnis prüfen ↗</Link>
            </div>}

            <div className="section-title" id="parameter-values">
              <span>02</span>
              Technologie- und Timing-Parameter
            </div>
            {busLoadField && (
              <BusLoadParameterControl
                field={busLoadField}
                key={technology.id}
                parameters={displayedParameters}
                technology={technology}
              />
            )}
            <div className="parameter-groups">
              {parameterGroups.map(([category, fields]) => (
                <fieldset className={`parameter-group parameter-group-${category}`} key={`${technology.id}:${category}`}>
                  <legend>{parameterCategoryLabels[category]}</legend>
                  <div className="form-grid three">
                    {fields.map((field) => (
                      <div key={field.key} id={`parameter-field-${field.key}`} className={findingsForParameter(currentFindings, technologyId, field.key).length ? 'parameter-field-finding' : undefined}>
                      {findingsForParameter(currentFindings, technologyId, field.key).length > 0 && <p className="parameter-field-finding-message" role="status">Prüfbefund · {new Set(findingsForParameter(currentFindings, technologyId, field.key).map(item => item.network_id)).size} betroffene Netze: Bestätigung oder passender Nachweis fehlt. Ein vorbelegter Wert allein erledigt den Befund nicht.</p>}
                      <ParameterControl
                        field={field}
                        key={field.key}
                        value={displayedParameters[field.key]}
                        unverified={parameterIsUnverified(storedParameters, field.key, technologyId)}
                        savedAssumption={parameterValueStatus(storedParameters, field.key, technologyId) === "SAVED_ASSUMPTION"}
                        simulationAssumption={field.default === undefined && field.simulation_default !== undefined && parameterIsUnverified(storedParameters, field.key, technologyId)}
                        proposal={field.key === "bitrate" ? technology.parameter_proposals : undefined}
                      />
                      </div>
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

function ParameterControl({ field, value, unverified = false, simulationAssumption = false, savedAssumption = false, proposal }: {
  field: TechnologyParameterField;
  value: unknown;
  unverified?: boolean;
  simulationAssumption?: boolean;
  savedAssumption?: boolean;
  proposal?: Technology["parameter_proposals"];
}) {
  const [proposalError, setProposalError] = useState('');
  const label = `${field.label}${field.unit ? ` (${field.unit})` : ""}`;
  const missing = value === undefined || value === null || value === "";
  const suggestion = field.parameter_origin === 'NIS_SCENARIO' ? 'NIS-Szenariovorschlag' : 'Profilvorschlag';
  const gap = unverified ? <small>{simulationAssumption ? (savedAssumption ? 'SIMULATIONSANNAHME · Gespeichert · Kein Gerätenachweis' : 'SIMULATIONSANNAHME · Kein Gerätenachweis') : `UNVERIFIED · ${missing ? "Eingabe erforderlich" : suggestion}`}</small> : null;
  const conditionalProposal = field.conditional_defaults?.length ? <>
    <button className="button secondary" type="button" onClick={(event) => {
      const form = event.currentTarget.closest('form');
      if (!form) return;
      const raw = new FormData(form);
      const values: Record<string, unknown> = {};
      for (const proposal of field.conditional_defaults ?? []) {
        for (const [key, expected] of Object.entries(proposal.when)) {
          const entered = raw.get(key);
          const control = form.elements.namedItem(key);
          values[key] = typeof expected === 'boolean' ? control instanceof HTMLInputElement && control.type === 'checkbox' ? control.checked : booleanParameterValue({}, entered)
            : typeof expected === 'number' ? entered === null || entered === '' ? undefined : Number(entered) : entered;
        }
      }
      const suggested = conditionalParameterDefault(field, values);
      const input = form.elements.namedItem(field.key);
      if (suggested === undefined) {
        setProposalError('Zuerst die zugehörige Einstellung auswählen.');
      } else if (input instanceof HTMLInputElement || input instanceof HTMLSelectElement) {
        input.value = String(suggested);
        input.dispatchEvent(new Event('change', {bubbles: true}));
        setProposalError('');
      }
    }}>Bedingten Standardwert übernehmen</button>
    <small>{field.description}</small>
    {proposalError && <small role="status">{proposalError}</small>}
  </> : null;
  if (field.type === "select") {
    return (
      <div className="field" title={field.description}>
        <label htmlFor={field.key}>{label}</label>
        {gap}
        <select defaultValue={String(value ?? "")} id={field.key} name={field.key}>
          {missing && <option value="">Bitte auswählen</option>}
          {(field.options ?? []).map((option) => (
            <option key={option} value={option}>{option.replaceAll("_", " ")}</option>
          ))}
        </select>
        {conditionalProposal}
      </div>
    );
  }
  if (field.type === "boolean") {
    if (field.default === undefined) {
      return (
        <div className="field" title={field.description}>
          <label htmlFor={field.key}>{label}</label>
          {gap}
          <select defaultValue={missing ? '' : String(value)} id={field.key} name={field.key}>
            <option value="">Nicht bekannt</option>
            <option value="true">Ja</option>
            <option value="false">Nein</option>
          </select>
        </div>
      );
    }
    return (
      <label className="parameter-toggle" title={field.description}>
        <input defaultChecked={Boolean(value)} name={field.key} type="checkbox" />
        <span>{label}</span>
        {gap}
      </label>
    );
  }
  if (field.type === "text") {
    return (
      <div className="field" title={field.description}>
        <label htmlFor={field.key}>{label}</label>
        {gap}
        <input defaultValue={String(value ?? "")} id={field.key} name={field.key} type="text" />
        {conditionalProposal}
      </div>
    );
  }
  if (field.numeric_encoding === 'DECIMAL_STRING') {
    return <div className="field" title={field.description}>
      <label htmlFor={field.key}>{label}</label>{gap}
      <input defaultValue={String(value ?? '')} id={field.key} name={field.key} type="text" inputMode="numeric" required={field.required} />
      {conditionalProposal}
    </div>;
  }
  return (
    <div title={field.description}>
      {gap}
      <NumberField
        label={label}
        name={field.key}
        min={field.min === undefined ? undefined : String(field.min)}
        max={field.max === undefined ? undefined : String(field.max)}
        step={field.integer ? "1" : "any"}
        required={field.required}
        value={missing ? "" : String(value)}
      />
      {conditionalProposal}
      {proposal?.options?.length ? (
        <p className="muted">
          Referenz-Obergrenzen, keine bestätigte Busfrequenz: {proposal.options.map(option =>
            `${option.mode} ≤ ${option.maximum.toLocaleString("de-DE")} ${proposal.unit ?? "bit/s"}`).join(" · ")}.
          Controller, angeschlossene Geräte und Leitung müssen die gewählte Frequenz unterstützen.
          {proposal.source?.startsWith("https://") && <>
            {" "}<a href={proposal.source} rel="noreferrer" target="_blank">Spezifikation</a>
          </>}
        </p>
      ) : null}
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
  required?: boolean;
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
        {technology.max_payload_bytes === undefined || technology.max_payload_bytes === null
          ? "Payloadgrenze offen" : `max. ${technology.max_payload_bytes.toLocaleString("de-DE")} B`}
      </span>
    </div>
  );
}

function TechnologyOptions({ domain, technologies, matches, query, selectedId, licenses }: {
  domain?: TechnologyDomain;
  technologies: Technology[];
  matches: Technology[];
  query: string;
  selectedId: string;
  licenses: Record<string, LicenseState>;
}) {
  const recommended = domain?.technologies ?? [];
  const recommendedIds = new Set(recommended.map(item => item.id));
  const remaining = technologies.filter(item => !recommendedIds.has(item.id));
  const option = (item: Technology) => <option key={item.id} value={item.id}>
    {item.id.replaceAll('_', ' ').toUpperCase()}{item.implementation_status && item.implementation_status !== 'IMPLEMENTED'
      ? ` · ${item.implementation_status}` : ''}
    {item.licensing_policy?.clearance_required ? licenses[item.id]?.blocked === false ? ' · ✓ Lizenzfreigabe' : ' · ⚠ Ausführung gesperrt' : ''}
  </option>;
  if (query.trim()) {
    const selected = technologies.find(item => item.id === selectedId);
    return <>
      {selected && !matches.some(item => item.id === selectedId) && <optgroup label="Aktuelle Auswahl">{option(selected)}</optgroup>}
      {matches.length > 0 && <optgroup label="Suchtreffer">{matches.map(option)}</optgroup>}
      {matches.length === 0 && <option disabled value="__no_matches">Keine Treffer</option>}
    </>;
  }
  return <>
    {recommended.length > 0 && <optgroup label={`Im Anwendungsbereich ${domain?.label}`}>{recommended.map(option)}</optgroup>}
    {remaining.length > 0 && <optgroup label="Weitere registrierte Technologien">{remaining.map(option)}</optgroup>}
  </>;
}
