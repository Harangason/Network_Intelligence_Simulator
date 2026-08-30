import { extractEngineeringSpecification } from "../src/lib/agent/engineering-specification.ts";
import { semanticProcessorForSensor } from "../src/lib/agent/semantic-routing.ts";
import { normalizePhysicalTopology } from "../src/lib/topology.ts";

const projectId = process.argv[2]?.trim();
const backendBase = process.env.SIMULATOR_BACKEND_API_URL ?? "http://127.0.0.1:15050/api/engineering";

if (!projectId) {
  throw new Error("Projekt-ID fehlt: pnpm repair:semantic-routes <project-id>");
}

async function request(path, init = {}) {
  const response = await fetch(`${backendBase}${path}`, {
    ...init,
    signal: init.signal ?? AbortSignal.timeout(45_000),
    headers: {
      "Content-Type": "application/json",
      "X-Project-ID": projectId,
      ...init.headers,
    },
  });
  if (response.status === 204) return undefined;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${init.method ?? "GET"} ${path}: ${payload.error ?? response.status}`);
  return payload;
}

async function requestAll(path) {
  const items = [];
  const separator = path.includes("?") ? "&" : "?";
  for (let offset = 0; ; offset += 500) {
    const page = await request(`${path}${separator}limit=500&offset=${offset}`);
    items.push(...page.items);
    if (page.items.length < 500) break;
  }
  return { items, count: items.length };
}

function interfaceSupportsProtocol(item, protocol) {
  const type = String(item.interface_type ?? "").toUpperCase().replace(/[^A-Z0-9]+/g, "_");
  const normalizedProtocol = String(protocol ?? "").toUpperCase().replace(/[^A-Z0-9]+/g, "_");
  if (normalizedProtocol === "ETHERNET") return type === "ETHERNET";
  if (normalizedProtocol === "FLEXRAY") return type === "FLEXRAY";
  return type === normalizedProtocol;
}

function busForProtocol(protocol) {
  const value = String(protocol ?? "").toUpperCase();
  if (value === "LIN") return "lin";
  if (value === "ETHERNET" || value.includes("100BASE") || value.includes("1000BASE")) return "automotive_ethernet";
  if (value === "FLEXRAY") return "flexray";
  return "can_fd";
}

function kindForHardware(item) {
  if (item.device_type === "Gateway") return "gateway";
  if (item.device_type === "SensorController") return "sensor";
  if (item.device_type === "ActuatorController") return "actuator";
  return "ecu";
}

const specification = extractEngineeringSpecification(`
# Fahrzeugnetzwerk
- 100 Sensoren
- 50 Funktions-ECUs
- 1 zentrales Gateway
- LIN
- CAN-FD
- Automotive Ethernet
`);
const referenceSensors = specification.chains.filter((chain) => chain.device_type === "SensorController");
const referenceByName = new Map(specification.chains.map((chain) => [chain.hardware_name, chain]));

const [
  { items: hardware },
  { items: functions },
  { items: interfaces },
  { items: messages },
  { items: signals },
  { items: initialRoutes },
  workflow,
] = await Promise.all([
  requestAll("/hardware-nodes"),
  requestAll("/functions"),
  requestAll("/interfaces"),
  requestAll("/messages"),
  requestAll("/signals"),
  requestAll("/routing"),
  request("/workflow?view=full"),
]);
const hardwareById = new Map(hardware.map((item) => [String(item.id), item]));
const hardwareByName = new Map(hardware.map((item) => [String(item.name), item]));
const interfacesByNode = new Map();
for (const item of interfaces) {
  const nodeId = String(item.hardware_node_id ?? "");
  interfacesByNode.set(nodeId, [...(interfacesByNode.get(nodeId) ?? []), item]);
}
const functionsByNode = new Map();
for (const item of functions) {
  const nodeId = String(item.hardware_node_id ?? "");
  functionsByNode.set(nodeId, [...(functionsByNode.get(nodeId) ?? []), item]);
}
const messagesByInterface = new Map();
for (const item of messages) {
  const interfaceId = String(item.interface_id ?? "");
  messagesByInterface.set(interfaceId, [...(messagesByInterface.get(interfaceId) ?? []), item]);
}
const signalsByMessage = new Map();
for (const item of signals) {
  const messageId = String(item.message_id ?? "");
  signalsByMessage.set(messageId, [...(signalsByMessage.get(messageId) ?? []), item]);
}

function chainForHardware(item) {
  return referenceByName.get(String(item.name)) ?? {
    hardware_name: String(item.name),
    hardware_description: String(item.description ?? item.name),
    device_type: String(item.device_type),
    function_name: `${item.name} Funktion`,
    function_description: String(item.description ?? item.name),
    interface_name: `${item.name} Interface`,
    interface_type: "CAN_FD",
    message_name: `${item.name}Data`,
    signal_name: String(item.name),
    signal_display_name: String(item.name),
  };
}

const actualProcessors = hardware
  .filter((item) => item.device_type === "ECU")
  .map(chainForHardware);
const semanticTargets = new Map(referenceSensors.flatMap((sensor) => {
  const processor = semanticProcessorForSensor(sensor, actualProcessors);
  return processor ? [[sensor.hardware_name, processor.hardware_name]] : [];
}));
const gateway = hardware.find((item) => item.device_type === "Gateway");

function protocolForInterface(item) {
  const value = String(item?.interface_type ?? "CAN_FD").toUpperCase().replace(/[^A-Z0-9]+/g, "_");
  if (value.includes("ETH")) return "ETHERNET";
  if (value.includes("FLEX")) return "FLEXRAY";
  if (value === "LIN") return "LIN";
  return "CAN_FD";
}

function compatibleEndpoints(sourceNode, targetNode, preferredProtocol) {
  const sourceInterfaces = interfacesByNode.get(String(sourceNode.id)) ?? [];
  const targetInterfaces = interfacesByNode.get(String(targetNode.id)) ?? [];
  const protocols = [
    preferredProtocol,
    sourceNode.device_type === "ECU" && targetNode.device_type === "Gateway" ? "ETHERNET" : undefined,
    "CAN_FD",
    "LIN",
    "ETHERNET",
  ].filter(Boolean);
  for (const protocol of [...new Set(protocols)]) {
    const sourceInterface = sourceInterfaces.find((item) => interfaceSupportsProtocol(item, protocol));
    const targetInterface = targetInterfaces.find((item) => interfaceSupportsProtocol(item, protocol));
    if (sourceInterface && targetInterface) return { sourceInterface, targetInterface, protocol };
  }
  for (const sourceInterface of sourceInterfaces) {
    const protocol = protocolForInterface(sourceInterface);
    const targetInterface = targetInterfaces.find((item) => interfaceSupportsProtocol(item, protocol));
    if (targetInterface) return { sourceInterface, targetInterface, protocol };
  }
  return null;
}

async function ensureInterface(node, protocol) {
  const existing = (interfacesByNode.get(String(node.id)) ?? [])
    .find((item) => interfaceSupportsProtocol(item, protocol));
  if (existing) return existing;
  const engineeringFunction = (functionsByNode.get(String(node.id)) ?? [])[0];
  if (!engineeringFunction) throw new Error(`${node.name} besitzt keine Funktion für ein ${protocol}-Interface.`);
  const proposedObject = {
    name: `${node.name}_${protocol}`,
    description: `${protocol}-Schnittstelle für den kanonischen Kommunikationspfad.`,
    domain: node.domain ?? "automotive",
    interface_type: protocol,
    hardware_node_id: String(node.id),
    function_id: String(engineeringFunction.id),
    source: "ai_generated",
    review_state: "unreviewed",
    approval_state: "pending",
    provenance: { agent: "semantic-routing-repair", reason: "required protocol compatibility" },
  };
  const proposal = await request("/proposals", {
    method: "POST",
    body: JSON.stringify({
      proposal_type: "OBJECT",
      target_object: { resource: "interfaces" },
      prompt: `Erzeuge fehlendes ${protocol}-Interface für ${node.name}.`,
      model: "semantic-routing-repair",
      model_version: "1.0",
      proposed_objects: [proposedObject],
      evidence: [{ type: "ROUTING_COMPATIBILITY", node_id: String(node.id), protocol }],
      retrieved_context: [],
      validation_results: [],
      created_by: "semantic-routing-repair",
    }),
  });
  const proposalId = String(proposal.proposal_id ?? "");
  if (!proposalId) throw new Error(`Interface-Proposal für ${node.name} besitzt keine ID.`);
  await request(`/proposals/${proposalId}/validate`, {
    method: "POST",
    body: JSON.stringify({ actor: "semantic-routing-repair" }),
  });
  const approved = await request(`/proposals/${proposalId}/approve`, {
    method: "POST",
    body: JSON.stringify({ actor: "semantic-routing-repair" }),
  });
  const canonicalId = String(approved.proposed_objects?.[0]?.canonical_id ?? "");
  if (!canonicalId) throw new Error(`Interface-Proposal für ${node.name} wurde nicht kanonisch registriert.`);
  const created = await request(`/interfaces/${canonicalId}`);
  interfaces.push(created);
  interfacesByNode.set(String(node.id), [...(interfacesByNode.get(String(node.id)) ?? []), created]);
  return created;
}

async function compatibleOrCreatedEndpoints(sourceNode, targetNode, preferredProtocol) {
  const existing = compatibleEndpoints(sourceNode, targetNode, preferredProtocol);
  if (existing) return existing;
  const sourceInterfaces = interfacesByNode.get(String(sourceNode.id)) ?? [];
  const sourceInterface = sourceInterfaces.find((item) => interfaceSupportsProtocol(item, preferredProtocol))
    ?? sourceInterfaces[0];
  if (!sourceInterface) return null;
  const protocol = protocolForInterface(sourceInterface);
  const targetInterface = await ensureInterface(targetNode, protocol);
  return { sourceInterface, targetInterface, protocol };
}

async function desiredRoute(sourceNode, targetNode) {
  const sourceReference = referenceByName.get(String(sourceNode.name));
  const endpoints = await compatibleOrCreatedEndpoints(sourceNode, targetNode, sourceReference?.interface_type);
  if (!endpoints) return null;
  const message = (messagesByInterface.get(String(endpoints.sourceInterface.id)) ?? [])[0];
  const signal = message ? (signalsByMessage.get(String(message.id)) ?? [])[0] : undefined;
  const networkId = `network-${busForProtocol(endpoints.protocol)}`;
  return {
    name: `${sourceNode.name} → ${targetNode.name}`,
    description: "Kanonischer fachlicher Kommunikationspfad.",
    source: {
      node_id: String(sourceNode.id),
      interface_id: String(endpoints.sourceInterface.id),
      port_id: `engineering-port-${endpoints.sourceInterface.id}`,
      network_id: networkId,
      protocol: endpoints.protocol,
    },
    payload: {
      message_id: message ? String(message.id) : null,
      message_ids: message ? [String(message.id)] : [],
      signal_ids: signal ? [String(signal.id)] : [],
    },
    destinations: [{
      node_id: String(targetNode.id),
      interface_id: String(endpoints.targetInterface.id),
      port_id: `engineering-port-${endpoints.targetInterface.id}`,
      network_id: networkId,
      protocol: endpoints.protocol,
    }],
    route: {
      hops: [
        { node_id: String(sourceNode.id), name: String(sourceNode.name) },
        { node_id: String(targetNode.id), name: String(targetNode.name) },
      ],
      gateways: [],
      transformations: [],
      priority: "NORMAL",
    },
    timing: {
      cycle_time_ms: Number(message?.cycle_ms ?? 20),
      timeout_ms: 500,
      max_latency_ms: 20,
      jitter_limit_ms: 5,
    },
    routing_policy: {
      routing_type: "UNICAST",
      redundancy: "NONE",
      conditions: [],
    },
    confidence: 0.96,
  };
}

async function createRouteViaProposal(routeData) {
  const proposal = await request("/routing/generate", {
    method: "POST",
    body: JSON.stringify({
      prompt: `Kanonischen Pfad ${routeData.name} ergänzen.`,
      source_node_id: routeData.source.node_id,
      destination_node_ids: routeData.destinations.map((destination) => destination.node_id),
      message_id: routeData.payload.message_id,
      signal_ids: routeData.payload.signal_ids,
      routing_type: "UNICAST",
      actor: "semantic-routing-repair",
    }),
  });
  const proposalId = String(proposal.proposal_id ?? "");
  const generatedRoutes = Array.isArray(proposal.generated_routes) ? proposal.generated_routes : [];
  const validationResults = Array.isArray(proposal.validation_results) ? proposal.validation_results : [];
  const validIndexes = generatedRoutes.flatMap((route, index) => {
    const validation = route?.validation ?? validationResults[index] ?? {};
    return validation.valid === true ? [index] : [];
  });
  if (!proposalId || validIndexes.length === 0) {
    throw new Error(`RoutingProposal für ${routeData.name} ist nicht valide.`);
  }
  if (proposal.status !== "READY_FOR_REVIEW") {
    await request(`/routing/proposals/${proposalId}`, {
      method: "PATCH",
      body: JSON.stringify({ actor: "semantic-routing-repair", status: "READY_FOR_REVIEW" }),
    });
  }
  const accepted = await request(`/routing/proposals/${proposalId}/accept`, {
    method: "POST",
    body: JSON.stringify({ actor: "semantic-routing-repair", indexes: validIndexes }),
  });
  const route = accepted.items?.[0];
  if (!route) throw new Error(`RoutingProposal für ${routeData.name} lieferte keine Route.`);
  return route;
}

const desiredPairs = [];
for (const sensor of referenceSensors) {
  const sourceNode = hardwareByName.get(sensor.hardware_name);
  const targetNode = hardwareByName.get(semanticTargets.get(sensor.hardware_name));
  if (sourceNode && targetNode) desiredPairs.push({ sourceNode, targetNode });
}
if (gateway) {
  for (const processor of hardware.filter((item) => item.device_type === "ECU")) {
    desiredPairs.push({ sourceNode: processor, targetNode: gateway });
  }
}

const changedRouteIds = [];
const createdRouteIds = [];
const skipped = [];
const preparedRoutes = [];
for (const { sourceNode, targetNode } of desiredPairs) {
  const current = initialRoutes.find((route) =>
    String(route.source?.node_id ?? "") === String(sourceNode.id)
    && !["REJECTED", "OUTDATED", "SUPERSEDED", "DEPRECATED"].includes(String(route.status ?? "").toUpperCase()),
  );
  if (current && String(current.destinations?.[0]?.node_id ?? "") === String(targetNode.id)) continue;
  try {
    const routeData = await desiredRoute(sourceNode, targetNode);
    if (!routeData) {
      skipped.push({ source: sourceNode.name, target: targetNode.name, reason: "Kein kompatibles Interface-Paar" });
      continue;
    }
    preparedRoutes.push({ sourceNode, targetNode, current, routeData });
  } catch (error) {
    skipped.push({
      source: sourceNode.name,
      target: targetNode.name,
      reason: error instanceof Error ? error.message : String(error),
    });
  }
}

const routePackageSize = 2;
for (let offset = 0; offset < preparedRoutes.length; offset += routePackageSize) {
  const routePackage = preparedRoutes.slice(offset, offset + routePackageSize);
  const results = await Promise.all(routePackage.map(async ({ sourceNode, targetNode, current, routeData }) => {
    try {
      const saved = current
        ? await request(`/routing/${current.id}`, {
            method: "PATCH",
            body: JSON.stringify({
              ...routeData,
              actor: "semantic-routing-repair",
              reason: "Fachliche Sensor- oder Gateway-Zuordnung konsolidiert.",
              origin: "AI_MODIFIED",
            }),
          })
        : await createRouteViaProposal(routeData);
      const validated = await request(`/routing/${saved.id}/validate`, {
        method: "POST",
        body: JSON.stringify({ actor: "semantic-routing-repair" }),
      });
      if (validated.validation?.valid !== true) {
        throw new Error(JSON.stringify(validated.validation?.errors ?? []));
      }
      await request(`/routing/${saved.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ actor: "semantic-routing-repair" }),
      });
      return { id: String(saved.id), created: !current };
    } catch (error) {
      skipped.push({
        source: sourceNode.name,
        target: targetNode.name,
        reason: error instanceof Error ? error.message : String(error),
      });
      return null;
    }
  }));
  for (const result of results.filter(Boolean)) {
    (result.created ? createdRouteIds : changedRouteIds).push(result.id);
  }
}

const { items: currentRoutes } = await requestAll("/routing");
const approvedRoutes = currentRoutes.filter((route) =>
  route.approval_state === "APPROVED"
  && route.validation?.valid === true
  && !["REJECTED", "OUTDATED", "SUPERSEDED", "DEPRECATED"].includes(String(route.status).toUpperCase()),
);
const existingTopology = workflow.topology ?? { nodes: [], edges: [] };
const existingNodes = Array.isArray(existingTopology.nodes) ? existingTopology.nodes : [];
const existingByEngineeringId = new Map(
  existingNodes.filter((node) => node.engineeringId).map((node) => [String(node.engineeringId), node]),
);
const involvedIds = new Set(approvedRoutes.flatMap((route) => [
  String(route.source?.node_id ?? ""),
  ...(route.destinations ?? []).map((destination) => String(destination.node_id ?? "")),
  ...(route.route?.hops ?? []).map((hop) => String(hop.node_id ?? "")),
]).filter(Boolean));

const nodes = [...new Set([...existingNodes.map((node) => String(node.engineeringId ?? "")), ...involvedIds])]
  .filter(Boolean)
  .map((engineeringId, index) => {
    const item = hardwareById.get(engineeringId);
    const existing = existingByEngineeringId.get(engineeringId);
    if (!item) return existing;
    return {
      ...existing,
      id: existing?.id ?? `engineering-${engineeringId}`,
      name: String(item.name),
      kind: kindForHardware(item),
      x: existing?.x ?? 80 + (index % 4) * 280,
      y: existing?.y ?? 100 + Math.floor(index / 4) * 220,
      engineeringId,
      ports: (interfacesByNode.get(engineeringId) ?? []).map((networkInterface, portIndex) => ({
        id: `engineering-port-${networkInterface.id}`,
        name: String(networkInterface.name ?? networkInterface.interface_type),
        bus: busForProtocol(networkInterface.interface_type),
        side: portIndex % 2 === 0 ? "right" : "left",
        offset: (portIndex + 1) / ((interfacesByNode.get(engineeringId)?.length ?? 0) + 1),
        engineeringId: String(networkInterface.id),
      })),
    };
  })
  .filter(Boolean);
const topologyNodeByEngineeringId = new Map(nodes.map((node) => [String(node.engineeringId), node]));
const interfaceFor = (nodeId, explicitId, protocol) => {
  const candidates = interfacesByNode.get(nodeId) ?? [];
  return candidates.find((item) => String(item.id) === String(explicitId ?? ""))
    ?? candidates.find((item) => interfaceSupportsProtocol(item, protocol))
    ?? candidates[0];
};
const portIdFor = (nodeId, interfaceId) => topologyNodeByEngineeringId.get(nodeId)?.ports
  .find((port) => port.engineeringId === String(interfaceId))?.id ?? `engineering-port-${interfaceId}`;
const routingEdges = [];
for (const route of approvedRoutes) {
  for (const [destinationIndex, destination] of (route.destinations ?? []).entries()) {
    const sourceId = String(route.source?.node_id ?? "");
    const destinationId = String(destination.node_id ?? "");
    const path = (route.route?.hops ?? []).map((hop) => String(hop.node_id ?? "")).filter(Boolean);
    if (path.length < 2) path.push(sourceId, destinationId);
    for (let segment = 0; segment < path.length - 1; segment += 1) {
      const left = path[segment];
      const right = path[segment + 1];
      const protocol = route.source?.protocol ?? destination.protocol ?? "CAN_FD";
      const leftInterface = interfaceFor(left, segment === 0 ? route.source?.interface_id : undefined, protocol);
      const rightInterface = interfaceFor(right, segment === path.length - 2 ? destination.interface_id : undefined, protocol);
      if (!leftInterface || !rightInterface) continue;
      routingEdges.push({
        id: `route-${route.id}-${destinationIndex}-${segment}`,
        source: topologyNodeByEngineeringId.get(left)?.id ?? `engineering-${left}`,
        sourcePort: portIdFor(left, leftInterface.id),
        target: topologyNodeByEngineeringId.get(right)?.id ?? `engineering-${right}`,
        targetPort: portIdFor(right, rightInterface.id),
        bus: busForProtocol(protocol),
        routingEntryId: String(route.id),
        origin: "ROUTING_TABLE",
      });
    }
  }
}
const manualEdges = (existingTopology.edges ?? []).filter((edge) => edge.origin !== "ROUTING_TABLE");
const topology = normalizePhysicalTopology({ nodes, edges: [...manualEdges, ...routingEdges] });
await request("/workflow/topology", {
  method: "PUT",
  signal: AbortSignal.timeout(60_000),
  body: JSON.stringify({ topology, actor: "semantic-routing-repair" }),
});

for (const routeId of [...changedRouteIds, ...createdRouteIds]) {
  const validated = await request(`/routing/${routeId}/validate`, {
    method: "POST",
    body: JSON.stringify({ actor: "semantic-routing-repair" }),
  });
  if (validated.validation?.valid === true) {
    await request(`/routing/${routeId}/approve`, {
      method: "POST",
      body: JSON.stringify({ actor: "semantic-routing-repair" }),
    });
  }
}
for (const route of approvedRoutes.filter((item) => item.status !== "APPROVED")) {
  await request(`/routing/${route.id}/approve`, {
    method: "POST",
    body: JSON.stringify({ actor: "semantic-routing-repair" }),
  });
}

console.log(JSON.stringify({
  project_id: projectId,
  changed_routes: changedRouteIds.length,
  created_routes: createdRouteIds.length,
  total_routes: approvedRoutes.length,
  skipped,
  topology_nodes: topology.nodes.length,
  topology_edges: topology.edges.length,
}, null, 2));
